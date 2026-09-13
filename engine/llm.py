"""The engine's LLM client: thin wrapper around llama.cpp's server API.

This is core engine responsibility (PRD §7 step 5 — "LLM narrates"), not dev
tooling: it's how the engine actually talks to Gemma 4 E2B, using the same
GGUF-quantised weights and llama.cpp runtime the app ships with (PRD §11,
ADR 0003 — llama.cpp/GGUF, not LiteRT-LM). `experiments/harness/` reuses
this module for desktop iteration rather than duplicating it — dev tooling
depends on the engine, not the other way round.

Timings reported here are desktop CPU numbers when run on this dev host —
NOT the phone spike (PRD §0). Label them accordingly wherever they're shown.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
from typing_extensions import Self

DEFAULT_MODEL_ID = "gemma-4-e2b"
DEFAULT_HF_REPO = "google/gemma-4-E2B-it-qat-q4_0-gguf"
DEFAULT_HF_FILE = "gemma-4-E2B_q4_0-it.gguf"

DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 8091
DEFAULT_CTX_SIZE = 4096
DEFAULT_THREADS = 4
DEFAULT_MAX_TOKENS = 96
SERVER_STARTUP_TIMEOUT_S = 60.0
SERVER_STARTUP_POLL_INTERVAL_S = 0.25

# Same reasoning as the litert-lm version this replaced: the model's own
# defaults are close to greedy decoding, which collapses in-character
# dialogue to whatever single token is statistically safest ("Nothing.",
# "Silence."). 0.6 is the middle point this repo already tuned against real
# transcripts — see devlog for the 0.85-drifts-into-aphorism and
# 0.6-still-needs-a-diverse-retry history. Kept as plain dicts now (not a
# runtime-specific config object) since they're just JSON request fields.
DEFAULT_SAMPLER_CONFIG_KWARGS = {"temperature": 0.6, "top_k": 40, "top_p": 0.9}

# Used only for engine/loop.py's one bland-dismissal retry — deliberately
# more diverse than DEFAULT_SAMPLER_CONFIG_KWARGS so a resample has a real
# chance of landing somewhere else instead of reproducing the same bland
# output it was meant to escape.
RETRY_SAMPLER_CONFIG_KWARGS = {"temperature": 1.0, "top_k": 50, "top_p": 0.97}

# llama.cpp's nearest equivalent to litert-lm's NoRepeatNgramConfig hard
# constraint. Not identical (DRY is a penalty, not a hard ban), but aimed at
# the same failure mode: verbatim tail-phrase repetition across turns, which
# matters here because brief.py already embeds the guard's own recent lines
# in the prompt ("What's been said so far") — a repeated 3-token fragment
# from his last reply is already in context. dry_allowed_length=2 means any
# repeated run of 3+ tokens gets penalised, matching the old
# no_repeat_ngram_size=3; dry_penalty_last_n mirrors the old window_size.
# Needs the same empirical validation against real transcripts that
# brief.py's own prompting went through — not assumed correct on paper.
DEFAULT_DRY_KWARGS = {
    "dry_multiplier": 0.8,
    "dry_base": 1.75,
    "dry_allowed_length": 2,
    "dry_penalty_last_n": 256,
}


def orb_models_base_dir() -> Path:
    """Respects ORB_MODELS_DIR, mirroring the old LITERT_LM_DIR override."""
    override = os.environ.get("ORB_MODELS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".orb"


def resolve_model_path(model_id: str = DEFAULT_MODEL_ID) -> Path:
    """`<ORB_MODELS_DIR>/models/<id>/model.gguf` — same per-model-id shape
    the old litert-lm convention used, just pointed at a GGUF file."""
    models_dir = orb_models_base_dir() / "models"
    return models_dir / model_id.replace("/", "--") / "model.gguf"


def import_model(
    model_id: str = DEFAULT_MODEL_ID,
    hf_repo: str = DEFAULT_HF_REPO,
    hf_file: str = DEFAULT_HF_FILE,
) -> Path:
    """Downloads Gemma 4 E2B's official GGUF quant, if not already present.

    This is the ~3 GB network/disk action the harness's `setup` command
    gates behind an explicit confirmation prompt — call this only after the
    user has agreed to the download.
    """
    model_path = resolve_model_path(model_id)
    if model_path.is_file():
        return model_path

    import huggingface_hub

    model_path.parent.mkdir(parents=True, exist_ok=True)
    downloaded = huggingface_hub.hf_hub_download(repo_id=hf_repo, filename=hf_file)
    shutil.copyfile(downloaded, model_path)
    return model_path


def is_model_ready(model_id: str = DEFAULT_MODEL_ID) -> bool:
    return resolve_model_path(model_id).is_file()


def _find_server_binary() -> str:
    """ORB_LLAMA_SERVER_BIN env var, else `llama-server` on PATH.

    This dev host builds llama.cpp under ~/llama.cpp/build/bin, which isn't
    on PATH — set ORB_LLAMA_SERVER_BIN=~/llama.cpp/build/bin/llama-server
    (or symlink it onto PATH) before running the engine here.
    """
    override = os.environ.get("ORB_LLAMA_SERVER_BIN")
    if override:
        return override
    found = shutil.which("llama-server")
    if found:
        return found
    raise FileNotFoundError(
        "No llama-server binary found. Build llama.cpp and either put "
        "llama-server on PATH, or set ORB_LLAMA_SERVER_BIN to its full path."
    )


@dataclasses.dataclass
class PromptResult:
    prompt: str
    response: str
    init_time_s: float
    time_to_first_token_s: float
    prefill_tokens: int
    prefill_tokens_per_second: float
    decode_tokens: int
    decode_tokens_per_second: float
    total_time_s: float
    raw_response: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class GemmaHarness:
    """Loads Gemma 4 E2B via a dedicated llama.cpp server and runs prompts
    against it.

    Used both by the engine's own core loop (`engine/loop.py`) and by
    `experiments/harness/` for desktop brief/prompt iteration (PRD §14).

    Manages its own `llama-server` subprocess (started on construction,
    stopped on `close()`) rather than expecting one to already be running —
    same self-contained "just works" contract the old litert-lm version had.
    All calls from one instance share a single fixed `id_slot`, matching
    this engine's current one-guard-per-process scope: with
    `cache_prompt=True`, llama.cpp's automatic longest-common-prefix
    matching reuses the static top of each freshly-rebuilt brief
    (`engine/brief.py` — persona/voice-examples/scene/backstory) turn to
    turn, without needing to accumulate raw conversation history.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        system_message: str | None = None,
        cpu_thread_count: int | None = None,
        verbose: bool = False,
        sampler_config: dict[str, Any] | None | str = "default",
        host: str = DEFAULT_SERVER_HOST,
        port: int | None = None,
        ctx_size: int = DEFAULT_CTX_SIZE,
    ):
        model_path = resolve_model_path(model_id)
        if not model_path.is_file():
            raise FileNotFoundError(
                f"No imported model at {model_path}. Run `orb-harness setup` first."
            )

        self._system_message = system_message
        # "default" means "use this module's chat-tuned sampling", matching
        # the old sentinel's meaning — pass sampler_config=None explicitly
        # to fall back to the server's own defaults instead.
        self._sampler_config = (
            DEFAULT_SAMPLER_CONFIG_KWARGS if sampler_config == "default" else sampler_config
        )

        self._host = host
        self._port = port or int(os.environ.get("ORB_LLAMA_SERVER_PORT", DEFAULT_SERVER_PORT))
        self._id_slot = 0
        self._client = httpx.Client(base_url=f"http://{self._host}:{self._port}", timeout=120.0)

        binary = _find_server_binary()
        threads = cpu_thread_count or DEFAULT_THREADS
        args = [
            binary,
            "--host", self._host,
            "--port", str(self._port),
            "--model", str(model_path),
            "--jinja",
            # Gemma 4's chat template defaults to a chain-of-thought
            # "thinking" pass before the real answer (confirmed directly:
            # without this flag, a 96-token budget was entirely consumed by
            # reasoning_content, leaving content empty). The guard's replies
            # are one or two short sentences (brief.py) — no reasoning step
            # is wanted or affordable within a small token budget.
            "--reasoning", "off",
            "--ctx-size", str(ctx_size),
            "--threads", str(threads),
            "--n-gpu-layers", "0",
            "--cache-type-k", "q4_0",
            "--cache-type-v", "q4_0",
            "--slots",
        ]
        log_path = orb_models_base_dir() / "logs" / "llama-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = log_path.open("a")
        start = time.perf_counter()
        self._process = subprocess.Popen(
            args,
            stdout=(None if verbose else self._log_file),
            stderr=(None if verbose else subprocess.STDOUT),
        )
        self._wait_for_health()
        self.startup_time_s = time.perf_counter() - start

    def _wait_for_health(self) -> None:
        deadline = time.perf_counter() + SERVER_STARTUP_TIMEOUT_S
        last_error: Exception | None = None
        while time.perf_counter() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError(
                    f"llama-server exited early (code {self._process.returncode}) — "
                    f"see {self._log_file.name} for its output."
                )
            try:
                response = self._client.get("/health", timeout=2.0)
                if response.status_code == 200:
                    return
            except httpx.HTTPError as exc:
                last_error = exc
            time.sleep(SERVER_STARTUP_POLL_INTERVAL_S)
        raise TimeoutError(
            f"llama-server did not become healthy within {SERVER_STARTUP_TIMEOUT_S}s"
            f" (last error: {last_error})"
        )

    def close(self) -> None:
        self._client.close()
        self._process.terminate()
        try:
            self._process.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=10.0)
        self._log_file.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def ask(
        self,
        prompt: str,
        system_message: str | None = None,
        sampler_config: dict[str, Any] | str | None = "default",
    ) -> PromptResult:
        """`sampler_config`: "default" (this instance's usual sampling, see
        DEFAULT_SAMPLER_CONFIG_KWARGS) or "retry" (RETRY_SAMPLER_CONFIG_KWARGS
        — higher diversity, for engine/loop.py's bland-dismissal resample) —
        or pass a dict of raw llama.cpp request fields to override outright."""
        if sampler_config == "default":
            resolved_sampler_config = self._sampler_config
        elif sampler_config == "retry":
            resolved_sampler_config = RETRY_SAMPLER_CONFIG_KWARGS
        else:
            resolved_sampler_config = sampler_config or {}

        resolved_system = (
            system_message if system_message is not None else self._system_message
        )
        messages = []
        if resolved_system:
            messages.append({"role": "system", "content": resolved_system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "id_slot": self._id_slot,
            "cache_prompt": True,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "stream": True,
            **resolved_sampler_config,
            **DEFAULT_DRY_KWARGS,
        }

        start = time.perf_counter()
        first_token_time: float | None = None
        content_parts: list[str] = []
        final_chunk: dict[str, Any] = {}
        with self._client.stream("POST", "/v1/chat/completions", json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                text = delta.get("content") or ""
                if text and first_token_time is None:
                    first_token_time = time.perf_counter()
                content_parts.append(text)
                if "timings" in chunk:
                    final_chunk = chunk
        total_time_s = time.perf_counter() - start
        timings = final_chunk.get("timings", {})

        return PromptResult(
            prompt=prompt,
            response="".join(content_parts),
            init_time_s=0.0,
            time_to_first_token_s=(first_token_time or time.perf_counter()) - start,
            prefill_tokens=timings.get("prompt_n", 0),
            prefill_tokens_per_second=timings.get("prompt_per_second", 0.0),
            decode_tokens=timings.get("predicted_n", 0),
            decode_tokens_per_second=timings.get("predicted_per_second", 0.0),
            total_time_s=total_time_s,
            raw_response=final_chunk,
        )
