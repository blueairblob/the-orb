# engine/ — Phase 1 Python engine

The deterministic core (PRD §3, §4, §11). Empty scaffold — nothing built yet.

Build order when the spike passes (PRD §24, steps 1–4):
1. ✅ Desktop Python environment; pieces talking. (`pyproject.toml`, `uv`, `experiments/harness/`.)
2. ✅ Evaluate Evennia — **decided: build fresh**, not on Evennia. See
   [ADR 0002](../docs/decisions/0002-evennia-evaluation.md).
3. Build the object model — base class, state, relationships, capabilities, existence, position.
   The brief-builder hangs off this. Capabilities-as-locks and the LLM-NPC memory/thinking-message
   pattern are worth borrowing in spirit from the Evennia investigation (ADR 0002), dependency-free.
4. Smallest possible voice loop: one cell, one guard, Google STT/TTS. Prove the heartbeat.

Non-negotiables live in `../CLAUDE.md`. The engine owns the truth; the LLM only speaks.
