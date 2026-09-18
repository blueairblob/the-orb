"""The core loop (PRD §7): the smallest possible voice loop, one cell, one
guard (PRD §8, roadmap §24 step 4) — "you speak, the engine decides, it
speaks back."

Voice is text-mode on this host (see `engine/voice.py` for why); everything
else here is exactly what ships. `llm` is typed against a small protocol so
`run_turn` can be tested without the real model (`tests/test_loop.py`).
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from engine import dm, guardrail
from engine.brief import (
    VOICE_EXAMPLE_REPLIES,
    build_fact_extraction_prompt,
    build_guard_brief,
    format_guard_fact,
    guard_fact_quote,
)
from engine.guard import Guard
from engine.llm import GemmaHarness, is_model_ready
from engine.save import load_state, save_state
from engine.scenario import CellAndGuard, build_cell_and_guard
from engine.tactics import DIFFICULTIES, classify_tactic, difficulty_from_setting
from engine.voice import Voice
from engine.voice_text import TextVoice

DEFAULT_SAVE_PATH = Path.home() / ".orb" / "cell-and-guard-save.json"
TURN_MINUTES = 1


def build_intro(premise: str) -> str:
    """The player's very first line — the one thing said before any model
    call happens, so it's the only place that's *guaranteed* to establish
    why they're here. Both `build_guard_brief` and `build_narration_brief`
    already pass `premise` to the model, which happily alludes to it
    ("The stag is gone.") — but until this was dynamic, the player
    themselves was never told, so those callbacks read as confusing rather
    than evocative (devlog: "what is this 'stag' all about?")."""
    return (
        "You wake up on cold stone. Through the bars, a guard stands watch. "
        f"You remember why you're here — {premise}. "
        "The only way out is to talk your way past him."
    )


class LLMResult(Protocol):
    response: str


class LLMClient(Protocol):
    def ask(
        self,
        prompt: str,
        system_message: str | None = None,
        sampler_config: str = "default",
        id_slot: int | None = None,
    ) -> LLMResult: ...

    def rank(
        self, prompt: str, system_message: str, options: list[str], id_slot: int | None = None
    ) -> dict[str, float] | None: ...


BLAND_NUDGE = (
    "\n\n# Note\n"
    "Your instinct just now was a bare dismissal ('Nothing.', 'Silence.', "
    "'Quiet.') — resist it. Give a short line that's actually *about* "
    "something: your mood, your history, or what was just said."
)

REPEAT_NUDGE = (
    "\n\n# Note\n"
    "Your instinct just now was to repeat something you've already said "
    "word-for-word — resist it. React fresh to *this* line, even if the "
    "sentiment ends up similar."
)

# A generic "don't repeat yourself" framing (REPEAT_NUDGE) does not work for
# this specific failure — tested directly against the real backend (real
# playtest 2026-09-14): asked "what's your name?" at retry-level sampling
# (temperature=1.0) *with* REPEAT_NUDGE appended, the model gave the exact
# VOICE_EXAMPLES line back 4/4 times. It has to be told, specifically, that
# the offending text *is* one of the examples — that framing alone fixed it
# 4/4 times in the same test. Worded differently from REPEAT_NUDGE on
# purpose: "something you've already said" is false here (the guard never
# actually said this before), which risks confusing the model about what
# it's even being asked to avoid.
VOICE_EXAMPLE_NUDGE = (
    "\n\n# Note\n"
    "Your instinct just now was to answer with the exact words shown in the "
    "examples above — resist it. Those show your voice, not your actual "
    "line. Say something different that still sounds like you."
)

# Same situation as VOICE_EXAMPLE_NUDGE: PERSONA already states this rule,
# RULE_REMINDER already restates it right before generation, and neither
# was enough on its own (real playtest 2026-09-14: "Tell me about this
# place" named the room 4/4 times even with a nudge naming the problem
# directly, same as the voice-example case) — so this also falls back to
# guardrail.fallback_line() on a second failure rather than retrying forever.
ROOM_DESCRIPTION_NUDGE = (
    "\n\n# Note\n"
    "Your instinct just now was to describe the cell or your surroundings "
    "— resist it, that's the Dungeon Master's to narrate, not yours to say. "
    "React to what they actually asked without naming or describing where "
    "you are."
)

_NUDGES = {
    "bland": BLAND_NUDGE,
    "self_repeat": REPEAT_NUDGE,
    "voice_example": VOICE_EXAMPLE_NUDGE,
    "room_description": ROOM_DESCRIPTION_NUDGE,
}

# Failure modes that measurably don't reliably escape via resampling alone
# and so fall back to a safe line on a second failure rather than shipping a
# second bad reply. Bland dismissals aren't in this set — retry does
# reliably improve on them (test_retry_gives_up_after_one_more_bland_reply
# keeps that established, still-true behavior as-is). self_repeat *was*
# exempted on the same assumption, but two real sessions (2026-09-15) each
# hit a genuine double failure ("Begging doesn't work." / "Hunger is a
# powerful thing.", both shipped twice verbatim) — tested directly
# afterward: retry+REPEAT_NUDGE only escapes a self-repeat about half the
# time, common enough to explain both. A verbatim self-echo reads just as
# broken to a player as a copied voice-example line; treat it the same way.
_FALLS_BACK_ON_RETRY_FAILURE = {"voice_example", "room_description", "self_repeat"}

# Low temperature deliberately, unlike DEFAULT_SAMPLER_CONFIG_KWARGS in
# engine/llm.py — this call is extraction, not in-character performance, and
# wants the same fact judged the same way turn to turn, not creative variety.
FACT_EXTRACTION_SAMPLER_KWARGS = {"temperature": 0.2, "top_k": 20, "top_p": 0.9}

# A distinct llama.cpp KV-cache slot from the narration/retry calls' default
# (0) — real backend testing (2026-09-16, devlog) found that sharing one
# slot between this short, differently-shaped prompt and the guard's much
# larger brief meant *each* call evicted the other's cached prefix, so
# narration never got to reuse its static top turn to turn and every single
# guard turn paid a full ~13s re-prefill instead of just the first.
# GemmaHarness reserves a second slot (--parallel 2) specifically for this.
FACT_EXTRACTION_ID_SLOT = 1


# The prompt asks for exactly "NONE" on a no-fact turn, but real backend
# testing (2026-09-16) caught the model answering plain "No" instead — an
# exact-match check let that get recorded as if it were a fact, corrupting
# the ledger with garbage ("- No" shown back to the model as established
# canon). Small tolerance set, not real intent parsing, same spirit as the
# rest of this file's keyword heuristics.
_NO_NEW_FACT_ANSWERS = {"NONE", "NO", "N/A", "NOTHING", "NOTHING NEW", "NO NEW FACT"}


def _extract_new_fact(llm: LLMClient, extraction_prompt: str) -> str | None:
    """Oracle-pattern fact-ledger extraction (see build_fact_extraction_prompt
    for the full rationale) — a small, separate call, not a keyword scan
    over the reply, deciding whether a turn established a new durable fact.
    Returns the fact, or None. The guardrail is used as a *predicate* here,
    not a filter: this text is never spoken, so substituting a fallback line
    would be wrong — an empty or broken answer used to become "Enough talk."
    and get recorded as canon. Anything the guardrail would have replaced is
    simply rejected instead."""
    result = llm.ask(
        extraction_prompt,
        system_message=None,
        sampler_config=FACT_EXTRACTION_SAMPLER_KWARGS,
        id_slot=FACT_EXTRACTION_ID_SLOT,
    )
    answer = result.response.strip().strip("\"'“”‘’").strip()
    if not answer or guardrail.filter_reply(answer) != answer:
        return None
    if answer.rstrip(".").upper() in _NO_NEW_FACT_ANSWERS:
        return None
    return answer


def _normalize_for_quote(text: str) -> str:
    return " ".join(text.lower().strip(" \"'“”‘’").rstrip(".!…").split())


def _is_quoted_from(fact: str, source: str) -> bool:
    """Engine-side grounding check for extractive fact extraction ("agents
    propose, engine disposes"): the proposed fact must appear verbatim —
    modulo case, whitespace, wrapping quotes and trailing punctuation — in
    what was actually said. Rejects a hallucinated detail outright rather
    than trusting the extraction model's word."""
    quoted = _normalize_for_quote(fact)
    return bool(quoted) and quoted in _normalize_for_quote(source)


def _restates_canon(guard: Guard, speaker: str, reply: str) -> bool:
    """True if a guard reply contains his own verbatim words from a recorded
    fact — i.e. repeating it is him staying consistent, not echoing."""
    if speaker != "guard":
        return False
    quotes = (guard_fact_quote(fact) for fact in guard.established_facts)
    return any(quote and _is_quoted_from(quote, reply) for quote in quotes)


def _ask_and_record(
    llm: LLMClient,
    guard: Guard,
    prompt: str,
    brief: str,
    speaker: str,
    room_name: str | None = None,
    room_description: str = "",
) -> str:
    own_lines = guard.own_lines(speaker)
    # Voice examples and the room-description rule only apply to the guard
    # (brief.py's few-shot block, PERSONA's own-surroundings ban) — checking
    # them for a DM line, whose whole job is describing the scene, would be
    # meaningless. room_name is None for DM calls for the same reason.
    voice_examples = list(VOICE_EXAMPLE_REPLIES) if speaker == "guard" else []

    def _failure(reply: str) -> str | None:
        if guardrail.is_bland_dismissal(reply):
            return "bland"
        if guardrail.is_repeated_reply(reply, own_lines):
            return "self_repeat"
        if guardrail.is_repeated_reply(reply, voice_examples):
            return "voice_example"
        if room_name is not None and guardrail.is_room_description(
            reply, room_name, room_description
        ):
            return "room_description"
        return None

    result = llm.ask(prompt, system_message=brief)
    reply = guardrail.filter_reply(result.response, speaker)

    # The engine directs: a flat non-answer, a verbatim echo of a past line,
    # or a verbatim copy of a voice-example line gets one retake with a
    # nudge naming the specific problem, rather than shipping it or silently
    # rewriting what the actor said. sampler_config="retry" matters as much
    # as the nudge text — a resample at the same (fairly low) default
    # temperature is close enough to deterministic that it can reproduce the
    # exact bad reply it was meant to escape (devlog: happened with multiple
    # failure modes in real sessions).
    failure = _failure(reply)
    if failure is not None:
        retry_result = llm.ask(
            prompt, system_message=brief + _NUDGES[failure], sampler_config="retry"
        )
        retry_reply = guardrail.filter_reply(retry_result.response, speaker)
        retry_failure = _failure(retry_reply)
        if retry_failure is None:
            reply = retry_reply
        elif failure == "self_repeat" and _restates_canon(guard, speaker, reply):
            # Gotcha #15 (don't echo yourself) yields to Gotcha #3 (stay bound
            # to your word). Asked "Remind me, where did you grow up?", the
            # consistent answer *is* the one he gave before — real backend
            # testing (2026-09-18) caught the fallback below dodging that
            # exact question with "Enough talk.", refusing to repeat his own
            # canon. The retry still runs first (fresh wording is preferred);
            # this only replaces the fallback when both attempts repeat.
            pass
        elif failure in _FALLS_BACK_ON_RETRY_FAILURE:
            # Unlike bland dismissals (which do reliably escape on retry —
            # see test_retry_gives_up_after_one_more_bland_reply for that
            # established, intentional "keep the first attempt" behavior),
            # these measurably don't (see _FALLS_BACK_ON_RETRY_FAILURE's own
            # comment above) — shipping the same bad reply twice is worse
            # than the guardrail's own last-resort line.
            reply = guardrail.fallback_line(speaker)

    guard.remember(speaker, reply)
    return reply


@dataclasses.dataclass
class Turn:
    """One turn, split at the moment the player hears the reply (REVIEW.md
    R4). Everything the reply depends on — routing, the mood dial, the
    thresholds, the reply itself — happens in play_turn, before this exists.
    Recording what the reply established (fact extraction) happens in
    finish(), *after* the reply is on its way: real testing measured that
    call at ~2.5-3.5s, spent entirely on something the player never sees.
    Call finish() before the next turn and before saving, so both see
    complete state."""

    reply: str
    speaker: str
    outcome: str | None
    tactics: tuple[str, ...] | None = None
    _pending: Callable[[], None] | None = None

    def finish(self) -> None:
        if self._pending is not None:
            pending, self._pending = self._pending, None
            pending()


def play_turn(scenario: CellAndGuard, llm: LLMClient, player_utterance: str) -> Turn:
    """Runs a turn up to the reply. Routes to the DM (PRD §12: "the DM
    wearing a different hat") for scene narration and grounding refusals;
    the guard only ever speaks his own dialogue — see `engine/dm.py`."""
    guard: Guard = scenario.guard
    world = scenario.world
    world.clock.advance(TURN_MINUTES)
    route = dm.classify_utterance(player_utterance)

    if route in ("refusal", "narration"):
        guard.remember("player", player_utterance)
        if route == "refusal":
            brief = dm.build_refusal_brief(
                scenario.room, player_utterance, world.established_facts
            )
        else:
            brief = dm.build_narration_brief(
                scenario.room,
                scenario.door,
                guard,
                scenario.premise,
                world.established_facts,
                clock=world.clock,
            )
        reply = _ask_and_record(llm, guard, player_utterance, brief, "dm")

        # The DM improvises scene detail every time it narrates or redirects —
        # the PRD's own flagship Gotcha #3 example is a DM detail ("what's
        # over the wall?"), so this is the same canonization the guard gets.
        def record_scene_fact() -> None:
            if reply == guardrail.fallback_line("dm"):
                return
            fact = _extract_new_fact(
                llm,
                dm.build_scene_fact_extraction_prompt(
                    scenario.room, world.established_facts, player_utterance, reply
                ),
            )
            if fact and _is_quoted_from(fact, reply):
                world.add_established_fact(fact)

        return Turn(reply, "dm", None, _pending=record_scene_fact)

    # Default: dialogue directed at the guard. Classified and scored before
    # this line joins memory (the repeat check compares earlier turns only),
    # and before the reply — his mood decides how he answers, and whether
    # the door opens this turn.
    previous_reply = (guard.own_lines("guard") or ["(the scene opens)"])[-1]
    readings = classify_tactic(llm, player_utterance, previous_reply)
    tactics, _ = guard.react_to(player_utterance, readings, scenario.difficulty)
    guard.remember("player", player_utterance)

    outcome = guard.check_thresholds()
    if outcome == "unlock":
        scenario.door.unlock()

    # Brief reflects secret_revealed as it stood *before* this turn, so the
    # turn eligibility first opens still gets the "may reveal" framing — a
    # real chance to narrate the moment — rather than skipping straight to
    # "already revealed" before it's ever actually been said. Flipped for
    # future turns only after this one's brief and reply are done.
    brief = build_guard_brief(
        guard, scenario.door, scenario.room, scenario.premise, clock=world.clock
    )
    reply = _ask_and_record(
        llm,
        guard,
        player_utterance,
        brief,
        "guard",
        room_name=scenario.room.name,
        room_description=scenario.room.description,
    )
    guard.maybe_reveal_secret()

    def record_guard_fact() -> None:
        # A fallback line is the engine's own words, not an improvisation —
        # nothing in it to canonize, so skip the extraction call.
        if reply == guardrail.fallback_line("guard"):
            return
        quote = _extract_new_fact(
            llm, build_fact_extraction_prompt(guard, player_utterance, reply)
        )
        if quote and _is_quoted_from(quote, reply):
            guard.add_established_fact(format_guard_fact(player_utterance, quote))

    return Turn(reply, "guard", outcome, tactics=tactics, _pending=record_guard_fact)


def run_turn(
    scenario: CellAndGuard, llm: LLMClient, player_utterance: str
) -> tuple[str, str, str | None]:
    """A whole turn, synchronously: play_turn then finish. Returns
    (spoken_reply, speaker, outcome), where speaker is 'dm' or 'guard' and
    outcome is 'unlock', 'lockout', or None. The interactive loops use
    play_turn directly so the player isn't kept waiting for finish()."""
    turn = play_turn(scenario, llm, player_utterance)
    turn.finish()
    return turn.reply, turn.speaker, turn.outcome


def run_loop(
    scenario: CellAndGuard,
    llm: LLMClient,
    voice: Voice,
    save_path: Path,
    transcript_path: Path | None = None,
) -> None:
    """`transcript_path`, if given, gets one JSON line per turn — the full,
    uncapped record of a playtest (PRD §14: "log everything"; REVIEW.md R6),
    including the difficulty and what each line did to his mood, so easy and
    hard sessions can be compared afterwards."""
    voice.speak(build_intro(scenario.premise), speaker="dm")
    while True:
        try:
            utterance = voice.listen()
        except EOFError:
            break
        if utterance.strip().lower() in {"quit", "exit"}:
            break
        if not utterance.strip():
            continue

        mood_before = scenario.guard.affiliation.value
        turn = play_turn(scenario, llm, utterance)
        # R4: fact recording runs while the reply is being delivered (a real
        # voice backend blocks on TTS here), not before it. llama.cpp serves
        # the two concurrently on separate slots. Joined before saving and
        # before the next turn, so neither ever sees half-recorded state.
        recorder = threading.Thread(target=turn.finish)
        recorder.start()
        voice.speak(turn.reply, speaker=turn.speaker)
        recorder.join()
        save_state(save_path, scenario)
        if transcript_path is not None:
            _log_turn(transcript_path, scenario, utterance, turn, mood_before)

        if turn.outcome == "unlock":
            voice.speak("(The door creaks open. You're free.)", speaker="dm")
            break
        if turn.outcome == "lockout":
            voice.speak("(The guard storms off. Your only way out just left.)", speaker="dm")
            break


def _log_turn(
    path: Path, scenario: CellAndGuard, utterance: str, turn: Turn, mood_before: int
) -> None:
    guard = scenario.guard
    entry = {
        "ts": time.time(),
        "difficulty": scenario.difficulty.name,
        "player": utterance,
        "speaker": turn.speaker,
        "reply": turn.reply,
        "tactics": list(turn.tactics) if turn.tactics else None,
        "mood_delta": guard.affiliation.value - mood_before,
        "mood": guard.affiliation.value,
        "band": guard.affiliation.band,
        "outcome": turn.outcome,
    }
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Play the cell-and-guard scene.")
    parser.add_argument(
        "--difficulty",
        choices=sorted(DIFFICULTIES),
        default=os.environ.get("ORB_DIFFICULTY"),
        help="easy: the classifier can only credit you; hard (default): it can "
        "also count against you. Also settable via ORB_DIFFICULTY.",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Start a fresh game instead of resuming the saved one (the save "
        "is overwritten on the first turn). Use it to compare difficulties "
        "from the same starting point.",
    )
    args = parser.parse_args()
    try:
        difficulty = difficulty_from_setting(args.difficulty)
    except ValueError as error:
        parser.error(str(error))

    if not is_model_ready():
        print(
            "Model not imported yet. Run `orb-harness setup` first.", file=sys.stderr
        )
        sys.exit(1)

    save_path = DEFAULT_SAVE_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)
    scenario = build_cell_and_guard() if args.new else load_state(save_path)
    scenario.difficulty = difficulty

    transcript_dir = save_path.parent / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = (
        transcript_dir / f"{datetime.datetime.now(tz=datetime.UTC):%Y%m%d-%H%M%SZ}-terminal-{difficulty.name}.jsonl"
    )
    print(f"(difficulty: {difficulty.name} — transcript: {transcript_path})", file=sys.stderr)

    with GemmaHarness() as llm:
        run_loop(scenario, llm, TextVoice(), save_path, transcript_path)


if __name__ == "__main__":
    main()
