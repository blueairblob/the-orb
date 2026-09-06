"""The engine's LLM client: thin wrapper around litert-lm's Python API.

This is core engine responsibility (PRD §7 step 5 — "LLM narrates"), not dev
tooling: it's how the engine actually talks to Gemma 4 E2B, using the same
runtime and .litertlm quantised weights the app ships with on Android (PRD
§11). `experiments/harness/` reuses this module for desktop iteration rather
than duplicating it — dev tooling depends on the engine, not the other way
round.

Timings reported here are desktop CPU numbers when run on this dev host —
NOT the phone spike (PRD §0). Label them accordingly wherever they're shown.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from typing_extensions import Self

DEFAULT_MODEL_ID = "gemma-4-e2b"
DEFAULT_HF_REPO = "litert-community/gemma-4-E2B-it-litert-lm"
DEFAULT_HF_FILE = "gemma-4-E2B-it.litertlm"


def litert_lm_base_dir() -> Path:
    """Mirrors litert_lm_cli.config.get_cli_base_dir() (respects LITERT_LM_DIR)."""
    override = os.environ.get("LITERT_LM_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".litert-lm"


def resolve_model_path(model_id: str = DEFAULT_MODEL_ID) -> Path:
    """Resolves an imported model id to its local .litertlm file.

    Mirrors litert_lm_cli.model.Model.from_model_id's own
    '~/.litert-lm/models/<id>/model.litertlm' convention. Reimplemented here
    rather than imported since litert_lm_cli is an internal CLI package, not
    a public API.
    """
    models_dir = litert_lm_base_dir() / "models"
    return models_dir / model_id.replace("/", "--") / "model.litertlm"


def import_model(
    model_id: str = DEFAULT_MODEL_ID,
    hf_repo: str = DEFAULT_HF_REPO,
    hf_file: str = DEFAULT_HF_FILE,
) -> Path:
    """Downloads and imports the model via the litert-lm CLI, if not already present.

    This is the ~2.5 GB network/disk action the harness's `setup` command
    gates behind an explicit confirmation prompt — call this only after the
    user has agreed to the download.
    """
    model_path = resolve_model_path(model_id)
    if model_path.is_file():
        return model_path

    subprocess.run(
        [
            "litert-lm",
            "import",
            "--from-huggingface-repo",
            hf_repo,
            hf_file,
            model_id,
        ],
        check=True,
    )
    if not model_path.is_file():
        raise RuntimeError(
            f"litert-lm import reported success but {model_path} is missing."
        )
    return model_path


def is_model_ready(model_id: str = DEFAULT_MODEL_ID) -> bool:
    return resolve_model_path(model_id).is_file()


def _extract_text(response: dict[str, Any]) -> str:
    """Best-effort text extraction from a litert-lm response dict.

    The Python API's response schema isn't publicly documented at time of
    writing (conversation.py marks the return type itself as a TODO). Try the
    OpenAI-style `content: [{"type": "text", "text": ...}]` shape used
    elsewhere in litert-lm's own preset loader, then a few flatter fallbacks,
    before giving up and returning the raw dict as a string — callers can
    inspect `PromptResult.raw_response` if this ever needs correcting.
    """
    content = response.get("content")
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        if parts:
            return "".join(parts)
    if isinstance(response.get("text"), str):
        return response["text"]
    if isinstance(response.get("message"), str):
        return response["message"]
    return str(response)


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
    """Loads Gemma 4 E2B via LiteRT-LM and runs prompts against it.

    Used both by the engine's own core loop (`engine/loop.py`) and by
    `experiments/harness/` for desktop brief/prompt iteration (PRD §14).
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        system_message: str | None = None,
        cpu_thread_count: int | None = None,
        verbose: bool = False,
    ):
        import litert_lm

        model_path = resolve_model_path(model_id)
        if not model_path.is_file():
            raise FileNotFoundError(
                f"No imported model at {model_path}. Run `orb-harness setup` first."
            )
        litert_lm.set_min_log_severity(
            litert_lm.LogSeverity.INFO if verbose else litert_lm.LogSeverity.ERROR
        )
        self._litert_lm = litert_lm
        self._system_message = system_message
        self._engine = litert_lm.Engine(
            model_path=str(model_path),
            backend=litert_lm.Backend.CPU(thread_count=cpu_thread_count),
            enable_benchmark=True,
        )

    def close(self) -> None:
        self._engine.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def ask(self, prompt: str, system_message: str | None = None) -> PromptResult:
        conversation = self._engine.create_conversation(
            system_message=(
                system_message if system_message is not None else self._system_message
            )
        )
        try:
            start = time.perf_counter()
            response = conversation.send_message(prompt)
            total_time_s = time.perf_counter() - start
            info = conversation.get_benchmark_info()
            return PromptResult(
                prompt=prompt,
                response=_extract_text(response),
                init_time_s=info.init_time_in_second,
                time_to_first_token_s=info.time_to_first_token_in_second,
                prefill_tokens=info.last_prefill_token_count,
                prefill_tokens_per_second=info.last_prefill_tokens_per_second,
                decode_tokens=info.last_decode_token_count,
                decode_tokens_per_second=info.last_decode_tokens_per_second,
                total_time_s=total_time_s,
                raw_response=dict(response),
            )
        finally:
            conversation.close()
