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

# This model's own imported defaults are temperature=0.0, top_p=0.0 — fully
# greedy decoding. That's fine for deterministic tool-calling, but for
# in-character dialogue it collapses every reply to whatever single token is
# statistically safest ("Nothing.", "Silence."), no matter how much backstory
# is in the brief: there's no sampling left for a *character's* word choice
# to survive in. This is a chat/creative-writing default, not a universal
# one — override per call if a future use of GemmaHarness wants determinism
# back (e.g. structured/tool output). 0.85 was tried first and escaped the
# greedy collapse, but let the guard drift into ungrounded, aphorism-like
# lines disconnected from what was actually said (devlog: rapport-run
# transcript). 0.6 is a middle point — enough room to avoid the flat
# dismissals, tighter than 0.85's drift.
#
# Turned out not to fully hold in real play: at 0.6, a live session hit
# "Nothing."/"Silence." repeatedly, including cases where engine/loop.py's
# own bland-dismissal *retry* landed on another bland reply — because the
# retry was reusing this same low-temperature config, which is close enough
# to deterministic that resampling doesn't reliably produce something
# different. See RETRY_SAMPLER_CONFIG_KWARGS below: the fix is giving the
# retry its own higher-diversity sampling, not raising this one back up and
# reintroducing the 0.85 drift for every normal reply.
DEFAULT_SAMPLER_CONFIG_KWARGS = {"temperature": 0.6, "top_k": 40, "top_p": 0.9}

# Used only for engine/loop.py's one bland-dismissal retry, not normal
# replies — deliberately more diverse than DEFAULT_SAMPLER_CONFIG_KWARGS so
# a resample has a real chance of landing somewhere else, rather than
# reusing sampling close enough to deterministic to reproduce the same
# bland output it was meant to escape.
RETRY_SAMPLER_CONFIG_KWARGS = {"temperature": 1.0, "top_k": 50, "top_p": 0.97}

# NoRepeatNgramConfig is a hard constraint, not a bias: the model literally
# cannot reproduce a 3-token sequence that already appears in its context.
# Applied to every ask() call, not just retries — a much more direct fix for
# tail-phrase drift ("Now, be quiet." / "Now, stop wasting my time.",
# recurring across unrelated turns — devlog 2026-09-08) than detecting it
# after the fact via guardrail.is_repeated_reply, which only catches a
# *whole* reply matching, not a repeated fragment within it. Works because
# brief.py already embeds the guard's own recent lines in the prompt itself
# ("What's been said so far") — a 3-gram from his last reply is already in
# context, so reusing it verbatim this turn is exactly what gets blocked.
# window_size=256 covers the whole brief comfortably within Gemma 4's
# 512-token sliding window (devlog: the shared NPC-prompting doc).
DEFAULT_NO_REPEAT_NGRAM_KWARGS = {"no_repeat_ngram_size": 3, "window_size": 256}


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
        sampler_config: Any | None = "default",
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
        # "default" (not None) means "use this module's chat-tuned sampling,
        # not the model's own imported default" — see DEFAULT_SAMPLER_CONFIG_KWARGS
        # above. Pass sampler_config=None explicitly to fall back to the
        # model's own (greedy) defaults instead.
        self._sampler_config = (
            litert_lm.SamplerConfig(**DEFAULT_SAMPLER_CONFIG_KWARGS)
            if sampler_config == "default"
            else sampler_config
        )
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

    def ask(
        self,
        prompt: str,
        system_message: str | None = None,
        sampler_config: Any | str = "default",
    ) -> PromptResult:
        """`sampler_config`: "default" (this instance's usual sampling, see
        DEFAULT_SAMPLER_CONFIG_KWARGS) or "retry" (RETRY_SAMPLER_CONFIG_KWARGS
        — higher diversity, for engine/loop.py's bland-dismissal resample) —
        or pass a real SamplerConfig to override outright."""
        if sampler_config == "default":
            resolved_sampler_config = self._sampler_config
        elif sampler_config == "retry":
            resolved_sampler_config = self._litert_lm.SamplerConfig(
                **RETRY_SAMPLER_CONFIG_KWARGS
            )
        else:
            resolved_sampler_config = sampler_config

        conversation = self._engine.create_conversation(
            sampler_config=resolved_sampler_config,
            system_message=(
                system_message if system_message is not None else self._system_message
            )
        )
        try:
            start = time.perf_counter()
            response = conversation.send_message(
                prompt,
                no_repeat_ngram_config=self._litert_lm.interfaces.NoRepeatNgramConfig(
                    **DEFAULT_NO_REPEAT_NGRAM_KWARGS
                ),
            )
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
