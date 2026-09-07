# 2026-09-07 — Splitting the DM from the guard (PRD §12)

## Context

Coming off yesterday's web testing rig, the guard was still doing double duty: voicing his own
dialogue *and* describing the room whenever the player asked to look around, or inventing "no,
there's no sword here" refusals in his own gruff voice. PRD §12 is explicit that this is wrong —
"an NPC is just the DM wearing a different hat," and the guard should only ever speak his own
lines. This session built that split.

## Decisions

- **A router, not a bigger guard brief.** `engine.dm.classify_utterance` is a keyword heuristic —
  same honest sketch as `guard.py`'s mood heuristic, not real intent parsing — that sorts each
  player utterance into `refusal` / `narration` / `dialogue` before `run_turn` decides who speaks.
  Proper intent parsing is a bigger fix than this pass; the heuristic is enough to prove the split
  is structurally right.
- **`run_turn` now returns `(reply, speaker, outcome)`**, not just `(reply, outcome)`. Every
  caller (the CLI loop, the web server) needs to know who's talking, not just what was said —
  that's the whole point of the split, so it couldn't stay an implementation detail of the brief.
- **Grounding refusals stay in character, not explained.** v0.1 has no items, spells, or combat
  (PRD §8), so `UNGROUNDED_WORDS` (cast, spell, wand, potion, scroll, sword) route straight to a
  DM refusal brief that redirects the player back to what's actually in the scene — never a
  rules explanation. Deliberately narrow: generic threat words like "attack" or "fight" are left
  to the guard's own mood heuristic as aggressive dialogue, not routed here.
- **Guard gets `drives`, not just mood.** PRD §12's own example, taken verbatim: bored, cold,
  wants his watch to end, secretly a little soft on prisoners. Mood was already tracked as a
  number; drives are what make the brief describe a person instead of a mood gauge.
- **The orb and TTS distinguish speakers too, not just the transcript.** The DM gets a fixed
  neutral colour (pale, cool, mood-agnostic — the guard's mood gradient doesn't apply to a
  narrator) and its own `speechSynthesis` pitch/rate profile, separate from the guard's. If the
  split only showed up in text, it wouldn't be testable in the one place this project can actually
  be exercised end to end right now — the desktop web rig.

## What we did

1. Added `engine/dm.py`: `DM_PERSONA`, `classify_utterance`, `build_refusal_brief`,
   `build_narration_brief`.
2. `engine/guard.py`: added `drives` field. `engine/brief.py`: renamed `build_brief` →
   `build_guard_brief`, persona now explicitly forbidden from describing the room, brief now
   walks `guard.drives` into a "What's on your mind" section.
3. `engine/loop.py`: `run_turn` routes through `dm.classify_utterance` first; only falls through
   to the guard's own mood/threshold/brief logic for plain `dialogue`. Extracted `_ask_and_record`
   since both the DM and guard paths now do the same ask-filter-remember sequence.
4. `engine/voice.py` / `voice_text.py`: `speak()` takes a `speaker` param.
5. `experiments/web/server.py`: `reply, speaker, outcome` threaded through the WebSocket `reply`
   message; the intro message also now carries `speaker: "dm"`.
6. `experiments/web/static/orb.js` + `style.css`: DM-neutral HSL colour while speaker is `dm`,
   a `narrating` status-dot state, `ROLE_LABELS` for the transcript, and per-speaker
   `VOICE_PROFILES` (pitch/rate) for `speechSynthesis`.
7. Tests: new `tests/test_dm.py` for the router and brief builders directly; updated
   `test_brief.py`, `test_loop.py` (refusal/narration routing, unpacking the new 3-tuple),
   `test_web_server.py` (speaker field on both intro and reply messages).
8. `uv run pytest` — 33 passed. `uv run ruff check` — 9 errors (4 implicit-string-concatenation
   in `dm.py`'s multi-line briefs, 1 unused unpacked var in a test, plus fixable duplicates);
   cleared with `--fix` plus manual parenthesisation to match `brief.py`'s existing style.

## Outcomes

The guard/DM split is real now, not just documented intent: asking to look around or attempting
an ungrounded action (casting a spell, drawing a sword) gets a DM-voiced reply with its own
brief, tone, orb colour, and TTS voice, while ordinary talk to the guard is unaffected. Verified
via the test suite only this session — not yet re-driven through a real browser or the real model
the way yesterday's rig was.

This session's edits landed in the working tree right as the host took an unscheduled reboot
(2026-09-07 20:54 UTC) — nothing lost since nothing was committed, but this entry was written
after the fact, from `git diff` and file mtimes, rather than in the moment. Worth a moment's
pause: this is why the devlog and small, frequent commits both matter more on a host that can go
away without notice.

## Open threads

- The keyword heuristics (`UNGROUNDED_WORDS`, `ENVIRONMENT_QUERY_PATTERNS`) are honest sketches,
  same caveat as the guard's mood heuristic — Gotchas #1/#2's proper resolution (real intent
  handling) is bigger than this pass and still open.
- Not yet re-verified live against a browser + real model the way the web rig was last session —
  worth one real pass through the DM paths (a "look around," an ungrounded item attempt) once the
  reboot dust settles.
- Full rules adjudication (classes, spells, dice, combat) is still v0.2+ engine work; today's DM
  only grounds and narrates.
