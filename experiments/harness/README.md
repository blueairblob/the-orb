# The Gemma 4 E2B harness — `orb-harness`

A small tool for prodding, testing, and (eventually) tuning **Gemma 4 E2B** on this dev host,
using **LiteRT-LM** — the same runtime and `.litertlm` quantised weights the app ships with on
Android (PRD §11). Lives here, not in `engine/`, because it's dev-host tooling for brief/prompt
iteration, not shipping engine code (see the repo-level `experiments/README.md`).

## ⚠️ This is not the phone spike

Everything this tool measures is **desktop CPU behaviour on an OCI ARM64 cloud box** — useful for
iterating on prompt/brief quality and watching how the model handles edge cases, but it tells you
**nothing** about on-device thermal performance. The go/no-go call (PRD §0) can only be made on a
real mid-range Android phone, hot, unplugged, after 20 minutes. See `../../spike/README.md` and
`../../CLAUDE.md` ("This dev host vs the phone"). Every timing this tool prints is labelled to
make that unmistakable — don't let a good desktop number lull you into skipping the real spike.

## Setup

```bash
uv run orb-harness setup          # downloads + imports the model (~2.5 GB, asks first)
```

## Usage

```bash
# One-shot prompt
uv run orb-harness prompt "Hey, let an old friend out?" --system "You are a bored dungeon guard..."

# Batch of named test cases, with full I/O traces logged to experiments/<date>-<name>/trace.jsonl
uv run orb-harness batch experiments/harness/prompts/seed_cases.yaml

# Interactive poking
uv run orb-harness repl --system "You are a bored dungeon guard..."
```

## Training

`orb-harness train` is a deliberate stub. LiteRT-LM is inference-only, and this host has no GPU —
real LoRA/PEFT fine-tuning of a 2-4B model would be impractical here. For now, "training" the
guard's behaviour means iterating on the system message / brief via `prompt` and `batch`, which
matches the PRD's own position (§15: personality is authored, not learned).

## Seed test cases

`prompts/seed_cases.yaml` has hand-written stand-ins for the brief the object model (PRD §4) will
eventually auto-generate. Each case targets a specific risk already logged in PRD §22: grounding
(#2), compound commands (#1), breaking the fourth wall (#17), repetition (#15). A bad reply to any
of these is a gap worth fixing before the object model even exists — add more cases as new gotchas
come up.
