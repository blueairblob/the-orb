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

## Update — same day: fixed #2 and #4 too, at the user's "what are we waiting for?"

Both fixed, following the same rigor as #1/#3 — real model testing, not assumption.

**#2 (bland-dismissal gap)**: widened `is_bland_dismissal` from exact-match to a first-word +
word-count-capped check, so "Nothing worth mentioning." and "Nothing matters now." are caught as
padded versions of the same non-answer. This deliberately overturned an existing test
(`test_fuller_line_is_not_flagged` asserted "Nothing worth saying." should *not* be flagged) —
there's no text-only way to tell that phrase apart from the two real failures, so treating all
three the same is the more honest reading, not a regression. Flagged the tension directly before
changing it rather than silently picking a side.

**#4 (room description)**: same investigation shape as #1. Tried the prompt-only fix first
(restating the rule in `RULE_REMINDER`, the highest-attention position) — tested directly against
the real model for "Tell me about this place": still named the room 4/4 times. A targeted retry
nudge alone: still 3/4. Landed on the same pattern as #1 — a new `guardrail.is_room_description`
check (driven by the room's own `name` + `description` vocabulary, not hardcoded to "cell", so it
generalises past this one scenario), retry with a nudge, fall back to `guardrail.FALLBACK_LINE` if
the retry also fails.

**Honest limitation, found in the final end-to-end re-check and not chased further**: a third
playtest run showed turn 9 slipping through anyway — *"It's a dark hole. Stay quiet."* — using
neither the room's name ("cell") nor any word from its description ("cold stone cell"). Keyword
matching against an open-ended set of synonyms a small model can invent has a real, structural
ceiling; expanding the word list further has diminishing returns and the same brittleness. This is
a genuine, acknowledged gap, not a claim that #4 is fully solved — consistent with this file's own
stated philosophy ("last-resort net, not the primary mechanism"). #2's new check, similarly, wasn't
exercised by this final run's own randomness (the model didn't happen to produce a "nothing worth
X" reply that time) — backed by direct reasoning and unit tests, not re-confirmed live this session.

8 new/updated regression tests, 58 total, all passing.

## Open threads

- [x] **#2**: fixed, see Update above. Residual: only as strong as the model's actual phrasing
  matches the (now broader, but still finite) pattern — a genuinely novel bland phrasing could
  still slip through.
- [x] **#4**: fixed for the two originally-observed cases, see Update above. **Not fully closed**:
  keyword-matching against arbitrary room-descriptive synonyms has a real ceiling — "a dark hole"
  slipped through in the same session's own verification run. Worth revisiting if it keeps
  recurring in future play, but not with more enumerated words — a different approach (semantic
  similarity? a second small classification pass?) would be needed to meaningfully close this,
  and that's real new scope, not a quick follow-up.
- [ ] The fallback-line approach for voice-example reuse trades a characterful line for a generic
  one when it triggers. Worth watching how often it actually fires in longer/varied play — if it's
  rare, fine; if it's common, the underlying voice-examples themselves may need rewriting (less
  "obviously singularly correct" answers) rather than just catching it after the fact.
- [ ] This was one scripted 12-turn session, one read-through. Worth more playtesting across
  different conversation shapes (hostile-only, purely cooperative, long negotiation toward unlock)
  before calling the brief's quality "proven" on this backend the way it was on the old one.

## Update — 2026-09-15: the mood-tone disconnect, and a real rework

Followed the previous "worth more playtesting" thread above directly: ran a genuinely warm,
deliberate 15-turn session (not edge-case testing, real rapport-building) rather than another
scripted edge-case pass. Found something bigger than any of the four bugs above — see the
same-day continuation of this session for the full investigation and fix
(`engine/brief.py`'s `BAND_VOICE_EXAMPLES` rework, commits same day). Short version: mood tracked
warmth correctly (40 -> 62 over the session, verified in the save file) but the guard's actual
tone never softened at all — a real disconnect from PRD §12's "the AI simply voices wherever the
dial sits". A first fix (one extra example bolted onto the always-shown gruff static set) measurably
didn't work; even rewriting `PERSONA`'s own framing line didn't help. The real fix split voice
examples into an unconditional anti-promise pair plus a full per-band set, replacing rather than
supplementing the static block. Confirmed real (if subtler than hoped) improvement via
fresh-server isolated testing, ruling out a KV-cache-staleness confound along the way.

**New open thread, not fixed this session**: the mood heuristic's `"threat"` keyword
false-positived on "I'm **not** a threat to anyone" (no negation awareness) during the 15-turn
warm session — cost real progress toward the unlock threshold (mood capped at 62 of the needed
75, partly because of this one false hit). `engine/guard.py`'s `adjust_mood_from_text` has no
negation handling at all; same class of gap as this file's own `is_bland_dismissal`/
`is_room_description` word-only checks, not fixed yet.
