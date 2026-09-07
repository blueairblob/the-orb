# devlog/ — the living journal

A tech blog for this project's own development, written as it happens. Where `docs/PRD.md` is
the timeless *what and why*, and `docs/decisions/` is the terse *what was locked*, the devlog is
the messy, dated, first-person record of actually building it: decisions made in the moment,
commands run, what happened when they were, and threads left open.

## Format

One file per session (or a natural chunk of work), named:

```
YYYY-MM-DD-short-slug.md
```

Each entry should cover, loosely:

- **Context** — what prompted this session, what state the repo was in going in.
- **Decisions** — choices made and why, especially ones not big enough for a formal ADR
  (`docs/decisions/`) but worth remembering later.
- **Commands / what we did** — enough of the actual command trail that it could be replayed.
- **Outcomes** — what happened, including real numbers where there are any (timings, results).
- **Open threads** — anything left dangling, flagged for a future entry or a future ADR.

Promote something to `docs/decisions/` if it turns out to be a real locked architectural call;
leave it here if it's closer to "here's what we tried and found."

## Entries

- [2026-09-07 — Splitting the DM from the guard (PRD §12)](2026-09-07-dm-npc-split.md)
- [2026-09-07 — Desktop web testing rig: real voice + the orb](2026-09-07-web-testing-rig.md)
- [2026-09-06 — Building the engine: object model, guard, core loop](2026-09-06-build-the-engine.md)
- [2026-09-06 — The Evennia evaluation](2026-09-06-evennia-evaluation.md)
- [2026-09-06 — Phase 1 environment + the Gemma 4 E2B harness](2026-09-06-phase-1-env-and-gemma-harness.md)
