"""CLI entry point: `orb-harness`.

A tool for prodding, testing, and (eventually) tuning Gemma 4 E2B on this
dev host. Desktop CPU timings shown here are for brief/prompt iteration —
they are explicitly NOT the phone go/no-go spike (PRD §0). See
`spike/README.md` and `../../CLAUDE.md`.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import click
import yaml

from engine import llm

REPO_ROOT = Path(__file__).resolve().parents[2]


def _print_result(name: str, result: llm.PromptResult) -> None:
    click.echo(click.style(f"[{name}]", fg="cyan", bold=True))
    click.echo(f"  prompt:   {result.prompt}")
    click.echo(f"  response: {result.response}")
    click.echo(
        click.style(
            "  desktop CPU timing (NOT the phone spike, PRD §0): "
            f"ttft={result.time_to_first_token_s:.3f}s "
            f"decode={result.decode_tokens_per_second:.1f} tok/s "
            f"total={result.total_time_s:.3f}s",
            fg="bright_black",
        )
    )


@click.group()
def main() -> None:
    """Prod, test, and (eventually) tune Gemma 4 E2B on the desktop."""


@main.command()
@click.option("--model-id", default=llm.DEFAULT_MODEL_ID, show_default=True)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip the download confirmation prompt.",
)
def setup(model_id: str, yes: bool) -> None:
    """Downloads and imports Gemma 4 E2B (~2.5 GB) via the litert-lm CLI."""
    if llm.is_model_ready(model_id):
        click.echo(f"Model '{model_id}' already imported at "
                   f"{llm.resolve_model_path(model_id)}.")
        return

    if not yes:
        click.confirm(
            f"This downloads ~2.5 GB from Hugging Face "
            f"({llm.DEFAULT_HF_REPO}) to {llm.litert_lm_base_dir()}. Continue?",
            abort=True,
        )

    path = llm.import_model(model_id)
    click.echo(f"Imported '{model_id}' -> {path}")


@main.command()
@click.argument("prompt")
@click.option("--system", "system_message", default=None, help="System message / brief.")
@click.option("--model-id", default=llm.DEFAULT_MODEL_ID, show_default=True)
@click.option("--verbose", is_flag=True, help="Show native LiteRT-LM engine logs.")
def prompt(prompt: str, system_message: str | None, model_id: str, verbose: bool) -> None:
    """Sends a single prompt and prints the reply plus desktop timing."""
    if not llm.is_model_ready(model_id):
        raise click.ClickException(
            f"Model '{model_id}' not imported yet. Run `orb-harness setup` first."
        )
    with llm.GemmaHarness(
        model_id=model_id, system_message=system_message, verbose=verbose
    ) as harness:
        result = harness.ask(prompt)
    _print_result("prompt", result)


@main.command()
@click.argument("cases_file", type=click.Path(exists=True, path_type=Path))
@click.option("--model-id", default=llm.DEFAULT_MODEL_ID, show_default=True)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Override the dated output directory (default: experiments/<date>-<cases-file-stem>).",
)
@click.option("--verbose", is_flag=True, help="Show native LiteRT-LM engine logs.")
def batch(cases_file: Path, model_id: str, out_dir: Path | None, verbose: bool) -> None:
    """Runs every named case in a YAML file and logs full I/O traces.

    Case file format: a YAML list of {name, prompt, system_message?} — see
    `experiments/harness/prompts/seed_cases.yaml` for the starter set.
    """
    if not llm.is_model_ready(model_id):
        raise click.ClickException(
            f"Model '{model_id}' not imported yet. Run `orb-harness setup` first."
        )

    cases = yaml.safe_load(cases_file.read_text())
    if not isinstance(cases, list) or not cases:
        raise click.ClickException(f"{cases_file} did not contain a non-empty list of cases.")

    if out_dir is None:
        today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        out_dir = REPO_ROOT / "experiments" / f"{today}-{cases_file.stem}"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl"

    click.echo(f"Running {len(cases)} case(s) from {cases_file} -> {trace_path}")
    with (
        llm.GemmaHarness(model_id=model_id, verbose=verbose) as harness,
        trace_path.open("w") as trace_file,
    ):
        for case in cases:
            name = case["name"]
            case_prompt = case["prompt"]
            system_message = case.get("system_message")
            result = harness.ask(case_prompt, system_message=system_message)
            _print_result(name, result)
            record = {
                "name": name,
                "model_id": model_id,
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "system_message": system_message,
                **result.as_dict(),
            }
            trace_file.write(json.dumps(record) + "\n")

    click.echo(f"\nFull traces written to {trace_path}")


@main.command()
@click.option("--system", "system_message", default=None, help="System message / brief.")
@click.option("--model-id", default=llm.DEFAULT_MODEL_ID, show_default=True)
@click.option("--verbose", is_flag=True, help="Show native LiteRT-LM engine logs.")
def repl(system_message: str | None, model_id: str, verbose: bool) -> None:
    """Interactive free-form prompting against a running model instance."""
    if not llm.is_model_ready(model_id):
        raise click.ClickException(
            f"Model '{model_id}' not imported yet. Run `orb-harness setup` first."
        )
    click.echo("Interactive mode. Ctrl-D or 'exit' to quit.")
    with llm.GemmaHarness(
        model_id=model_id, system_message=system_message, verbose=verbose
    ) as harness:
        while True:
            try:
                text = click.prompt(">", prompt_suffix=" ")
            except (EOFError, click.exceptions.Abort):
                break
            if text.strip().lower() in {"exit", "quit"}:
                break
            result = harness.ask(text)
            _print_result("repl", result)


@main.command()
def train() -> None:
    """Fine-tuning: not implemented.

    LiteRT-LM is an inference runtime, not a training framework, and this
    host is CPU-only ARM64 with no GPU — real LoRA/PEFT fine-tuning would be
    impractical here. For now, "training" Gemma's behaviour means iterating
    on the system message / brief via `prompt` and `batch`, per PRD §15
    (personality is authored, not learned). Revisit this if/when a decision
    record says otherwise.
    """
    click.echo(
        "Not implemented — see experiments/harness/cli.py:train for why. "
        "Use `orb-harness prompt` / `batch` to iterate on the brief instead.",
        err=True,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
