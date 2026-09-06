# engine/ — Phase 1 Python engine

The deterministic core (PRD §3, §4, §11). Empty scaffold — nothing built yet.

Build order when the spike passes (PRD §24, steps 1–4):
1. Desktop Python environment; pieces talking.
2. Evaluate Evennia (typeclass world model + LLM-NPC contrib) vs building the object model fresh.
3. Build the object model — base class, state, relationships, capabilities, existence, position.
   The brief-builder hangs off this.
4. Smallest possible voice loop: one cell, one guard, Google STT/TTS. Prove the heartbeat.

Non-negotiables live in `../CLAUDE.md`. The engine owns the truth; the LLM only speaks.
