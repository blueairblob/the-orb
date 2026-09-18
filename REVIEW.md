# REVIEW.md — project review log

Formal, dated reviews of the whole project: gaps against the PRD, missed opportunities, and what
to do next. **Newest review first.** Each entry records the date, the reviewer, and the commit
reviewed, so any finding can be checked against the exact code it describes.

Where `devlog/` is the session-by-session journal, this file is the periodic step back — "given
everything built so far, what's wrong or missing?" When a finding is acted on, update its
**Status** in place (with the commit or devlog entry that closed it) rather than deleting it, so
the log stays an honest record of what was found and what happened to it.

**Status values:** `Open` · `In progress` · `Done (<commit>)` · `Deferred` (deliberately parked,
with the trigger for revisiting) · `Won't do` (with the reason).

---

## Review 2026-09-18

- **Reviewer:** Claude Opus 5 (`claude-opus-5`), via Claude Code
- **Commit reviewed:** `4e62217` (`main`), 96 tests passing
- **Scope:** the whole project against the PRD's load-bearing sections (§3–§8, §12, §14, §21, §22,
  §24), with the actual turn path in `engine/loop.py` traced rather than assumed
- **Prompted by:** the user asking for a full review after Phase 1's desktop work reached its
  natural finish line (see README Status, and `devlog/` 2026-09-14 → 2026-09-17)

### Summary

Phase 1's desktop engine is in strong shape against PRD §8's v0.1 must-have list: both terminal
states are reachable in real play, and the guard's state machine (secret reveal, fact
canonization, save persistence) is real, engine-owned state. The review found three places where
the code contradicts the PRD, and six opportunities. The most serious finding is that
"improvised detail becomes canon" (Gotcha #3, 🔴) covers only the guard, not the DM, whose
details are the PRD's own flagship example of the problem.

### Findings: gaps (the code contradicts the PRD)

| # | Finding | Evidence | PRD | Severity | Status |
|---|---|---|---|---|---|
| R1 | **The DM's improvised details are never canonized.** Fact extraction only runs on guard turns; the DM's refusal/narration paths return before `_maybe_record_new_fact`, and the DM's narration brief carries no memory or established facts at all. | `engine/loop.py` `run_turn` (the DM routes return early); `engine/dm.py` `build_narration_brief` | §22 Gotcha #3 (its own example is a DM detail: "what's over the wall?"), #16 trust wobble | 🔴 | Done (`873bd4f`) — `World.established_facts`, extractive + engine-verified; see `devlog/2026-09-18-dm-scene-canon.md` |
| R2 | **The world clock is decorative.** `room.state["time_of_day"]` is set once at scenario build and never updated, while `run_turn` advances the clock every turn. It starts at minute 0 and moves 1 minute per turn, so it always reads "night". The brief reads a stale copy of the time instead of the clock itself. | `engine/scenario.py:49`; `engine/brief.py:176`; `engine/dm.py:120` | §5 ("the clock quietly powers half the engine"), §4 (the brief walks the live graph) | 🟠 | Open |
| R3 | **The guard's drives never change.** `Guard.drives` is a fixed list that nothing updates; §12's "illusion of autonomy" from drives that tick along regardless of the player isn't built. Overlaps with the noted future direction (NPC timetable, ambient DM narration). | `engine/guard.py` `drives`; only read in `engine/brief.py:181` | §12 (Tamagotchi model, per-NPC state) | 🟠 | Deferred (folds into the NPC timetable/ambient narration work; revisit together with R2) |

### Findings: opportunities

| # | Finding | Evidence | PRD | Status |
|---|---|---|---|---|
| R4 | **Fact extraction adds latency to every turn.** `run_turn` runs the extraction call *before* returning the reply, so the player waits ~2.5–3.5s longer on every guard turn (measured 2026-09-16) for work they never see. Speak first, extract after. *Update (`873bd4f`): R1 put DM turns on the same path, so this now affects every non-fallback turn, not just guard turns.* | `engine/loop.py` `run_turn`, `run_loop` | §20 / §22 top-four (latency is the #1 technical risk) | Open |
| R5 | **The mood dial misses most real persuasion.** In the 2026-09-16 playtest, bribery ("I have gold"), flattery and empathy about his brother barely registered with the keyword sets. There's now an LLM judgment call every turn anyway; it could also *propose* an affiliation delta for the engine to clamp and apply. | `engine/guard.py` `adjust_affiliation_from_text` and its own docstring | §12 ("what moves the dial?" is still open), Gotcha #31 | Open |
| R6 | **`orb-engine` playtests aren't logged.** The web rig writes transcripts; the terminal loop doesn't, so real playtests survive only in chat. | `engine/loop.py` `run_loop` vs `experiments/web/server.py` `_log_transcript` | §14 ("log everything"), CLAUDE.md hygiene | Open |
| R7 | **Automated AI playtesting isn't built.** A frontier model fuzzing the engine is named in CLAUDE.md as exactly what this host is for. Every bug this week came from hand playtesting; this multiplies coverage. It needs a frontier-model API key (not checked). | no fuzzer anywhere in `experiments/` | §14 | Open |
| R8 | **Real-backend checks are throwaway.** Every live verification this week was an ad-hoc `python -c` script. An opt-in `pytest -m live` suite would make them regression tests; the 2026-09-16 cache-eviction bug is exactly what one would have caught. | `devlog/2026-09-16-*`, `devlog/2026-09-17-*` | §14 | Open |
| R9 | **Architectural decisions live only in devlogs.** Only three ADRs exist; the fact-ledger design (Oracle pattern), the second KV-cache slot and the `Stat` Character Engine primitive are all real, locked architectural calls. | `docs/decisions/` | CLAUDE.md ("record locked decisions as ADRs") | Open |

### Findings raised since this review

Found while acting on the findings above. Numbered on from R9; each notes where it came from.

| # | Finding | Evidence | PRD | Status |
|---|---|---|---|---|
| R10 | **The guard's fact extraction can invent canon, and nothing checks it.** Found while fixing R1: live testing showed the extraction model recording a DM detail that was never said. The DM path is now extractive and engine-verified (the fact must be quoted verbatim). The guard path still paraphrases into third person ("Garrick grew up in Oakhaven"), so it can't be checked the same way and carries the same risk. Needs its own grounding check (e.g. every content word of the fact must appear in the reply). | `engine/loop.py` guard branch of `run_turn`; `engine/brief.py` `build_fact_extraction_prompt` | §22 Gotcha #3, #16 | Open |
| R11 | **Residual gaps in scene canon (minor).** (a) Facts that overlap in meaning but not in wording aren't merged ("Faint carvings cover the surface." and "Faint carvings, long since worn smooth" both kept); fixing it would need semantic comparison. (b) A scene fact can describe engine-owned state indirectly ("a heavy iron bar secures the door") and would contradict an unlocked door. That can't happen yet, because unlock ends the session in v0.1. | live run, `devlog/2026-09-18-dm-scene-canon.md` | §3, §22 #3 / #6 | Deferred (revisit (b) if the game ever continues past an unlock) |

### Correctly deferred (checked, no action)

Capability-driven grounding (inert until an item exists), the Control axis (no concrete need
yet), ambient/scheduled DM narration (noted 2026-09-17), and real voice plus the phone port
(Phase 2, PRD §24 step 5). All have an explicit trigger for revisiting in memory/devlog.

### Recommended order

1. **R1** — the PRD's own 🔴 example and a trust-wobble risk.
2. **R4** — a quick, behaviour-neutral latency win.
3. **R2** — a small bug fix that also unblocks the NPC-timetable direction.
4. **R7** (with R6 and R8 as its natural companions) — the highest-leverage way to keep hardening
   Phase 1 without needing the user's time for every bug.
