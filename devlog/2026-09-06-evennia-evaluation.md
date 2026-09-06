# 2026-09-06 — The Evennia evaluation

## Context

Roadmap §24 step 2, right after yesterday's — well, this morning's — Phase 1 environment and
Gemma harness work: "Evaluate Evennia. Half a day. Does borrowing its typeclass world model and
LLM-NPC contrib save months — or drag in a MUD server you'll spend months removing? Decide
early; this choice is structural." PRD §11 flags the exact same tension and calls it out
explicitly as a caveat, not just a footnote.

Decided to actually test the claim hands-on rather than evaluate from documentation alone —
install it, scaffold a project, try to use the object model headlessly, and read the real
LLM-NPC contrib source rather than trust the PRD's summary of it.

## What we did

1. `pip download evennia` (no install) first, just to check current version — **v6.1.0**, not
   the "v5.x" the PRD's tech stack table names. Version drift, noted, not a blocker.
2. Extracted the wheel and grepped for the LLM-NPC contrib the PRD calls out
   (`evennia/contrib/rpg/llm/`) — it's real: `llm_client.py` + `llm_npc.py`, "Contribution by
   Griatch 2023." Read both files plus the README in full.
3. Checked the wheel's declared dependencies — Django 6.0, Twisted 24.11, DRF, autobahn among
   them.
4. Installed Evennia for real in a throwaway venv (scratchpad, not the project's own `.venv`) to
   test the "borrow the bones, skip the scaffolding" claim empirically:
   - `evennia --init evaltest` — scaffolds a full Django project (`web/`, `server/`, `commands/`,
     `typeclasses/`, `world/`), not a library.
   - `evennia migrate` — 24 migrations, ~6.5s, mandatory before any object exists.
   - A headless script calling `evennia.utils.create.create_object(...)` directly, with
     `django.setup()` but no Portal/Server/Twisted reactor running.
5. Cleaned up the scratch venv afterward.

## Outcome

The headless script **failed**: `create_object()` needs `settings.DEFAULT_HOME` — a seeded
"Limbo" room + superuser — that only gets created by Evennia's own initial-setup hook, which
normally runs during `evennia start`'s server boot. So the claim "just import `DefaultObject` and
go" doesn't hold up in practice; the object model is bootstrapped *by* the server machinery, not
merely alongside it.

**Verdict: don't adopt Evennia.** Written up as
[ADR 0002](../docs/decisions/0002-evennia-evaluation.md) with the full reasoning. Short version:
heavy Django+Twisted dependency footprint, the object model is inseparable from the Django ORM
and the server boot sequence, and the LLM-NPC contrib is thin (2023, ~180 lines) and wired for an
HTTP call to an external LLM server via Twisted — not applicable to our in-process LiteRT-LM
integration (`experiments/harness/runner.py`'s `GemmaHarness`, no HTTP anywhere in that path).

Not a wasted half-day, though: the "capabilities are the rules" idea in PRD §4 has a genuinely
clean expression in Evennia's `locks.add("get:false()")` / `obj.access(who, "get")` pattern,
worth echoing in spirit when the object model gets designed. The LLM-NPC contrib's
prompt-prefix + per-character memory + "thinking..." filler pattern is also good reference UX,
just needs reimplementing against our own in-process call instead of Evennia's Twisted HTTP
client.

## Open threads

- Roadmap step 3 is now unblocked and has a clear starting point: build the PRD §4 object model
  in `engine/` as plain Python — base class, state, relationships, capabilities (locks-as-flags,
  Evennia-inspired but dependency-free), existence, position.
- `engine/README.md`'s "Evaluate Evennia vs building fresh" line is now stale — should be updated
  when the object model work actually starts, to point at ADR 0002 instead of posing it as an
  open question.
- Evennia's `rpsystem` contrib (recognition, masks, pose language) is still unread — flagged in
  the PRD's "peer group" framing as prior art worth a skim, purely for ideas. Not urgent.
