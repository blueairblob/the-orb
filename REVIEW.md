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
| R2 | **The world clock is decorative.** `room.state["time_of_day"]` is set once at scenario build and never updated, while `run_turn` advances the clock every turn. It starts at minute 0 and moves 1 minute per turn, so it always reads "night". The brief reads a stale copy of the time instead of the clock itself. | `engine/scenario.py:49`; `engine/brief.py:176`; `engine/dm.py:120` | §5 ("the clock quietly powers half the engine"), §4 (the brief walks the live graph) | 🟠 | Done (`77d7ff3`) — briefs read the live `WorldClock`; scene starts at an authored hour; see `devlog/2026-09-18-state-machine-hardening.md` |
| R3 | **The guard's drives never change.** `Guard.drives` is a fixed list that nothing updates; §12's "illusion of autonomy" from drives that tick along regardless of the player isn't built. Overlaps with the noted future direction (NPC timetable, ambient DM narration). | `engine/guard.py` `drives`; only read in `engine/brief.py:181` | §12 (Tamagotchi model, per-NPC state) | 🟠 | Deferred (folds into the NPC timetable/ambient narration work; revisit together with R2) |

### Findings: opportunities

| # | Finding | Evidence | PRD | Status |
|---|---|---|---|---|
| R4 | **Fact extraction adds latency to every turn.** `run_turn` runs the extraction call *before* returning the reply, so the player waits ~2.5–3.5s longer on every guard turn (measured 2026-09-16) for work they never see. Speak first, extract after. *Update (`873bd4f`): R1 put DM turns on the same path, so this now affects every non-fallback turn, not just guard turns.* | `engine/loop.py` `run_turn`, `run_loop` | §20 / §22 top-four (latency is the #1 technical risk) | Done (`ef573c8`) — `play_turn` returns the reply; `Turn.finish()` records facts after it (overlapped with delivery in `run_loop`, sent-first in the web rig). Live: median 12.1 s to reply, 4.3 s of recording now off that path |
| R5 | **The mood dial misses most real persuasion.** In the 2026-09-16 playtest, bribery ("I have gold"), flattery and empathy about his brother barely registered with the keyword sets. There's now an LLM judgment call every turn anyway; it could also *propose* an affiliation delta for the engine to clamp and apply. | `engine/guard.py` `adjust_affiliation_from_text` and its own docstring | §12 ("what moves the dial?" is still open), Gotcha #31 | Done (`ef573c8`) — classifier labels the tactic (`engine/tactics.py`), Garrick's approved table sets the delta (`Guard.react_to`), keyword hostility override, 0.4 floor, diminishing repeats, keyword fallback. Live replay exposed R13 and R15 |
| R6 | **`orb-engine` playtests aren't logged.** The web rig writes transcripts; the terminal loop doesn't, so real playtests survive only in chat. | `engine/loop.py` `run_loop` vs `experiments/web/server.py` `_log_transcript` | §14 ("log everything"), CLAUDE.md hygiene | Open |
| R7 | **Automated AI playtesting isn't built.** A frontier model fuzzing the engine is named in CLAUDE.md as exactly what this host is for. Every bug this week came from hand playtesting; this multiplies coverage. It needs a frontier-model API key (not checked). | no fuzzer anywhere in `experiments/` | §14 | Open |
| R8 | **Real-backend checks are throwaway.** Every live verification this week was an ad-hoc `python -c` script. An opt-in `pytest -m live` suite would make them regression tests; the 2026-09-16 cache-eviction bug is exactly what one would have caught. | `devlog/2026-09-16-*`, `devlog/2026-09-17-*` | §14 | Open |
| R9 | **Architectural decisions live only in devlogs.** Only three ADRs exist; the fact-ledger design (Oracle pattern), the second KV-cache slot and the `Stat` Character Engine primitive are all real, locked architectural calls. | `docs/decisions/` | CLAUDE.md ("record locked decisions as ADRs") | Open |

### Findings raised since this review

Found while acting on the findings above. Numbered on from R9; each notes where it came from.

| # | Finding | Evidence | PRD | Status |
|---|---|---|---|---|
| R10 | **The guard's fact extraction can invent canon, and nothing checks it.** Found while fixing R1: live testing showed the extraction model recording a DM detail that was never said. The DM path is now extractive and engine-verified (the fact must be quoted verbatim). The guard path still paraphrases into third person ("Garrick grew up in Oakhaven"), so it can't be checked the same way and carries the same risk. Needs its own grounding check (e.g. every content word of the fact must appear in the reply). | `engine/loop.py` guard branch of `run_turn`; `engine/brief.py` `build_fact_extraction_prompt` | §22 Gotcha #3, #16 | Done (`545f6a0`) — extractive + engine-verified; the fact is composed by the engine as `Asked "…", you said: "…"` from verbatim parts |
| R11 | **Residual gaps in scene canon (minor).** (a) Facts that overlap in meaning but not in wording aren't merged ("Faint carvings cover the surface." and "Faint carvings, long since worn smooth" both kept); fixing it would need semantic comparison. (b) A scene fact can describe engine-owned state indirectly ("a heavy iron bar secures the door") and would contradict an unlocked door. That can't happen yet, because unlock ends the session in v0.1. | live run, `devlog/2026-09-18-dm-scene-canon.md` | §3, §22 #3 / #6 | Deferred (revisit (b) if the game ever continues past an unlock) |
| R12 | **Anti-repetition fought canon.** Found while verifying R10. Asked "Remind me, where did you grow up?", the guard's consistent answer was his earlier line word for word. The self-repeat check (Gotcha #15) rejected it, the retry repeated it, and the engine fell back to "Enough talk.": it refused to repeat a fact he'd already given. Reproduced with every draft logged. | `engine/loop.py` `_ask_and_record` fallback branch | §22 #15 vs #3, #16 | Done (`b6611e7`) — restating canon beats the self-repeat fallback; the retry still runs first |
| R13 | **His replies don't voice the engine's reaction to the player's move.** Found in the R5 live replay: the engine scored each bribe −1 (Garrick's table: bribes offend him), yet he answered "Show it to me." three times, which sounds tempted. The brief never tells him how he took the move, so the actor contradicts the director, and the player can never learn that bribes don't work on him. Fix direction: one line in the guard brief naming the move and his reaction ("They just offered you a bribe; it offends you a little"). | live replay 2026-09-18; `engine/brief.py` `build_guard_brief` | §3 (engine decides, AI voices), §12 | Done (`25931b3`) — one engine-worded reaction line before his mood; live: all 5 bribes now refused ("Gold buys nothing here.") vs "Show it to me." before. Caveat: the one warm reaction was ignored ("I don't care."), so positive reactions aren't shown to land yet |
| R14 | **R10 over-records junk "facts", and R12 amplifies it into a repetition loop.** Live replay: 11 facts in 30 turns, mostly non-facts: "Still locked." ×3, "Show it to me.", "Garrick.", and the *promise* "Ten minutes. Fine." Asking the model to copy words made it copy almost anything. Junk canon is fed back into the brief, and R12 lets restating canon past the anti-echo check, so "Still locked." and "He was just a man." each shipped three times. A regression introduced by R10 (`545f6a0`) the same day. | live replay 2026-09-18; `engine/brief.py` `build_fact_extraction_prompt` | §22 #3, #15 | Done (`b3e45ab`) — tightened prompt: junk 8/27 → 0/27, real facts 5/5 → 3/5 on first telling (misses are recoverable, junk isn't); see `experiments/2026-09-18-guard-fact-precision/` |
| R15 | **Garrick may be too hard to win.** Replaying the user's real 30-line playtest moved his mood only 40 → 50 (unlock is 75), because the table makes bribes −1 and questions/requests 0, and that playtest leaned on both. Working as drafted, but combined with R13 (no feedback) a real player can't find what works. A tuning and pacing decision for the user, best revisited after R13, since feedback changes how players play. *Update (R13 replay): mood 40 → 44 over the same 30 lines. Much of the player's real sympathy isn't scored: the classifier often reads it correctly but unsure of itself ("Wow, look I am really sorry" → empathy at 0.28), and the 0.4 floor turns it neutral. The floor exists for the harmful misreads, and those are all hostile labels ("your brother was a good man" → insult at 0.23), which keyword lists already cover precisely. Proposed: ignore the model's threat/insult labels entirely (keywords own hostility) and lower the floor for positive labels.* | live replay 2026-09-18; `engine/guard.py` `GARRICK_SUSCEPTIBILITY` | §12, §21 ("does one room feel alive?") | Open (user's call) |
| R16 | **The guard's fact block invalidates the prompt cache whenever it grows.** Facts are inserted newest-first at the top of a block in the middle of the brief, so each new fact changes every token after it and forces a re-prefill of the rest of the brief. Appending (oldest-first) would keep the prefix stable. A latency opportunity, unmeasured. | `engine/world.py` `add_fact` (`insert(0, …)`); `engine/brief.py` fact block | §20 latency | Open |

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
