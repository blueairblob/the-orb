# 2026-09-14 — First real playtest on the new llama.cpp backend, two bugs found and fixed

## Context

After two days of infrastructure work (the runtime swap, then a blocked phone-tuning attempt), the
user redirected explicitly: "the focus has to be now on ... moving onto gameplay ... if we can't
make this glide and effortless ... it's a pointless exercise." Fair — `brief.py`'s prompt tuning
was proven out against the old litert-lm backend and never re-checked against llama.cpp. This
session did that: a real scripted playthrough, read closely rather than treated as a pass/fail
smoke test, then fixed what it found.

## Decisions

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Fix scope: only #1 (verbatim voice-example reuse) and #3 (a routing bug), of four issues found | User's explicit call after I reported all four with a severity read — left #2 (a guardrail detection gap) and #4 (guard describing the room) for later rather than assuming "fix everything" | Fix all four — not what was asked |
| Extend the existing repeat-check/retry mechanism rather than build something new | `engine/loop.py` already has a retry-with-nudge path for bland dismissals and self-repeats (`guardrail.is_repeated_reply`); the voice-example bug is the same *shape* of problem (shipping text that already exists elsewhere in context) — reusing the mechanism kept the diff small and consistent | A prompt-only fix (e.g. an instruction not to reuse examples) — tried this first as a hypothesis, disproven directly (see Outcome) |
| Fall back to `guardrail.FALLBACK_LINE` on a second voice-example failure, but *not* change the existing bland/self-repeat "keep the first attempt" behavior | Measured directly: unlike bland/self-repeats, retry-temperature resampling reproduced the exact voice-example line 4/4 times even with a nudge naming the problem — this failure mode doesn't reliably escape via resampling the way the others do, so treating it the same way (keep the bad first attempt) would still ship a verbatim copy half the time | Add more retry attempts — rejected: the failures weren't random bad luck (4/4, not ~50/50), so more tries wouldn't likely help, and each attempt costs real latency, the thing the whole spike has been trying to minimize |
| Move `"look"` out of the bare single-word environment-query set into specific phrases (`"look around"`, `"take a look"`, etc.) | `"look"` collides between two senses — perception command vs. appearance copula ("you look cold") — that whole-word matching can't distinguish; anchoring to real inspection phrasings catches the intended case without swallowing guard-directed dialogue | An adjacency/regex check for "you look" specifically — more code for a narrower fix; the phrase-anchoring approach already matches this file's existing pattern (it already uses phrases for `"where am i"` etc.) |

## Commands

```bash
# [APPLIED] Fresh save, scripted 12-turn playthrough covering small talk,
# repeated identical lines, backstory questions, narration-adjacent lines,
# apology/recovery, and closing beats
rm -f ~/.orb/cell-and-guard-save.json
uv run orb-engine < /tmp/playtest_script.txt
```

```bash
# [APPLIED] Isolated whether the fix actually worked, independent of the
# game loop, once the first playtest re-run still showed the bug
uv run python3 -c "
from engine.llm import GemmaHarness
from engine.scenario import build_cell_and_guard
from engine.brief import build_guard_brief
scenario = build_cell_and_guard()
brief = build_guard_brief(scenario.guard, scenario.door, scenario.room, scenario.premise)
with GemmaHarness() as llm:
    for i in range(4):
        r = llm.ask(\"what's your name?\", system_message=brief + NUDGE, sampler_config='retry')
        print(r.response)
"
# -> 'Garrick. Now hush.' x4, even with the retry nudge -- the real finding
# that drove the fallback-line decision above
```

## Outcome

Ran a fresh 12-turn scripted session and read the full transcript closely rather than skimming for
crashes. Found four real issues (reported to the user with an honest severity read, not just a
pass/fail): a verbatim few-shot copy, a bland dismissal that slipped past the guardrail, a routing
bug, and the guard breaking his own "never describe the room" rule. Fixed the two the user asked
for.

**Fix #1 took two iterations, and the second one is the real finding of this session.** First
attempt: add the check, reuse the existing generic `REPEAT_NUDGE`. Re-ran the playtest — bug still
there. Debugged by calling `GemmaHarness` directly rather than guessing: the model reproduced
*"Garrick. Now hush."* verbatim 4/4 times at retry-level sampling (temperature=1.0), even with
`REPEAT_NUDGE` appended. A more specific nudge naming the actual problem ("the exact words shown in
the examples above") fixed it 4/4 times — but only against a minimal test brief. Against the real,
full `build_guard_brief` output, that same nudge *also* failed 4/4 times. More brief content makes
this specific Q&A pairing more overdetermined for the model, not less — a real, counter-intuitive
finding worth remembering: a bigger, more specific prompt isn't a strictly safer prompt against this
failure mode. Landed on the fallback-line approach instead of continuing to chase nudge wording.

**Fix #3 was more straightforward** — real regression from a real edge case in the existing
whole-word-matching approach, same shape as a bug already fixed once before (2026-09-09's
"looking" substring issue) but a different collision (word *sense*, not word *boundary*).

Both fixes confirmed against the real backend afterward, not just unit tests: re-ran the identical
12-turn script, turn 2 now gets the safe fallback line instead of the verbatim copy, and turn 6
("You look cold out here") now correctly gets a guard reply instead of a DM narration line. 5 new
regression tests added, 51 total, all passing; `ruff check` clean.

## Open threads

- [ ] **#2, still open**: the guardrail's bland-dismissal check only catches exact short phrases
  ("Nothing.", "Silence.", "Quiet."), not paraphrased non-answers ("Nothing worth mentioning.",
  "Nothing matters now.") that dodge a real question just as flatly. Reproduced again in this
  session's second playtest run (turn 5: "What did you do before you became a guard?" ->
  "Nothing worth mentioning."). Needs a real fix, not just noting.
- [ ] **#4, still open**: the guard described the room directly ("It's stone. Cold.") despite
  `PERSONA` explicitly forbidding it — reproduced again this session (turn 9). `PERSONA` states the
  rule but nothing enforces it the way the repeat/bland checks enforce theirs.
- [ ] The fallback-line approach for voice-example reuse trades a characterful line for a generic
  one when it triggers. Worth watching how often it actually fires in longer/varied play — if it's
  rare, fine; if it's common, the underlying voice-examples themselves may need rewriting (less
  "obviously singularly correct" answers) rather than just catching it after the fact.
- [ ] This was one scripted 12-turn session, one read-through. Worth more playtesting across
  different conversation shapes (hostile-only, purely cooperative, long negotiation toward unlock)
  before calling the brief's quality "proven" on this backend the way it was on the old one.
