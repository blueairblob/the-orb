# ADR 0002 — Evennia evaluation: do not adopt

**Date:** 6 September 2026
**Status:** Accepted
**Context:** PRD §11 ("🌟 Evennia — the shortcut for the non-AI half"), roadmap §24 step 2
("Evaluate Evennia... half a day... decide early; this choice is structural").

## Decision

**Do not adopt Evennia.** Build the PRD §4 object model as plain Python (no ORM, no async
networking framework), starting from scratch in `engine/`.

## Why

The PRD's own framing set the test: does Evennia's typeclass world model and LLM-NPC contrib save
months, or is its MUD-server scaffolding "a millstone" you spend months removing? Rather than
answer from documentation alone, this was tested hands-on in a throwaway venv (`pip install
evennia`, `evennia --init`, `evennia migrate`, then a headless script attempting to create
objects directly). Findings:

1. **The dependency footprint is heavy and network-server-oriented.** Django 6.0, Twisted 24.11,
   Django REST Framework, autobahn (WebSocket) — a ~185 MB venv for Evennia alone, against our
   current stack's `litert-lm` + `pyyaml`. None of this is optional to import the object model;
   Evennia's typeclasses (`ObjectDB`, `ScriptDB`, etc.) *are* Django models.
2. **`evennia --init` does not produce a library — it produces a multiplayer game server
   project.** The generated tree includes `web/` (Django admin, REST API, website, webclient),
   `server/` (Portal/Server process config), `commands/`, `typeclasses/`, `world/`. There is no
   "just import `DefaultObject`" path; you get a whole Django project whether you want the
   networking or not.
3. **Migrations are mandatory** (24 of them, ~6.5s) before any object can be created — hard proof
   the object model is inseparable from the Django ORM/database layer.
4. **Even after migrating, headless object creation failed** — `create_object()` requires
   `settings.DEFAULT_HOME` (a "Limbo" room + superuser account) that only gets seeded by
   Evennia's own initial-setup hook, which normally runs as part of `evennia start`'s
   Twisted-driven server boot. In other words: you cannot cleanly "borrow the bones and ignore
   the scaffolding" — the scaffolding is load-bearing for bootstrapping the bones at all.
5. **The touted LLM-NPC contrib (`evennia/contrib/rpg/llm/`) is real but thin** — ~180 lines
   across two files, last substantively authored in 2023 — and it is wired for an HTTP call to an
   *external* LLM server (tested against `text-generation-webui`) via Twisted's async `Agent`.
   Our design runs Gemma 4 E2B **in-process** via LiteRT-LM's native bindings — no HTTP, no
   separate LLM server, no Twisted reactor anywhere else in the stack. `llm_client.py` would not
   be reused at all; `llm_npc.py`'s memory/thinking-message pattern is a fine reference, but it's
   itself built on Evennia's Command/`inlineCallbacks` async model, not a drop-in.

This directly confirms the risk the PRD itself flagged, rather than just gesturing at it: adopting
Evennia here would mean carrying a full Django+Twisted multiplayer server as a hard dependency of
a single-player, on-device-bound engine, in exchange for an object model that still needs to be
learned and worked around, and an NPC contrib that solves a different integration problem than the
one we have. It also cuts directly against §11's Phase 1 goal — "the smallest possible voice loop
... a weekend, not a year" — and complicates the already-open question of how the Python engine
ultimately runs on a phone (Django/Twisted are not natural mobile runtimes).

## What we keep from the investigation

Not a wasted half-day — worth carrying into the from-scratch object model:

- **Locks-as-capabilities.** Evennia's `obj.locks.add("get:false()")` /
  `obj.access(who, "get")` pattern is exactly PRD §4's "capabilities are the rules" idea, cleanly
  expressed. Worth echoing the *shape* of that API (a small lock-string DSL or just boolean
  capability flags — TBD when the object model gets designed) without the dependency.
- **The LLM-NPC pattern** (prompt-prefix templating, per-character chat memory with a size cap,
  a "thinking..." filler message during slow generation) is good UX design worth reusing
  conceptually — it maps well onto PRD §12's mood dial and the "shall I repeat that?" recovery
  design (Gotcha #8/#9), just reimplemented against `experiments/harness`'s `GemmaHarness`
  in-process call instead of an HTTP round-trip.
- Evennia's `rpsystem` contrib (recognition, masks, pose language) remains worth a skim later as
  prior art per PRD §11's "peer group" framing, purely for ideas — not as a dependency.

## Consequences

- Unblocks roadmap step 3 (§24): build the object model in `engine/` from scratch — base class,
  state, relationships, capabilities, existence, position — as plain Python.
- `engine/README.md`'s roadmap note ("Evaluate Evennia (typeclass world model + LLM-NPC contrib)
  vs building the object model fresh") is now resolved: build fresh.
