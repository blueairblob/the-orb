import dataclasses
import json

from engine.guard import GARRICK_SUSCEPTIBILITY
from engine.loop import (
    FACT_EXTRACTION_ID_SLOT,
    FACT_EXTRACTION_SAMPLER_KWARGS,
    play_turn,
    run_loop,
    run_turn,
)
from engine.scenario import build_cell_and_guard


@dataclasses.dataclass
class StubResult:
    response: str


class StubLLM:
    """A fake LLM client: echoes a fixed in-character line, so engine-logic
    tests never need the real model."""

    def __init__(self, reply: str = "Stay put.", tactic: tuple[str, float | None] | None = None):
        self.reply = reply
        self.tactic = tactic
        self.calls: list[tuple[str, str | None]] = []
        self.choices: list[tuple[str, str, list[str], int | None]] = []

    def choose(self, prompt, system_message, options, id_slot=None):
        self.choices.append((prompt, system_message, options, id_slot))
        return self.tactic

    def ask(
        self,
        prompt: str,
        system_message: str | None = None,
        sampler_config: str = "default",
        id_slot: int | None = None,
    ) -> StubResult:
        self.calls.append((prompt, system_message))
        return StubResult(response=self.reply)


class SequencedLLM:
    """Returns each reply in `replies` in order, then repeats the last —
    for exercising the bland-dismissal retry in `engine.loop._ask_and_record`."""

    def __init__(self, replies: list[str], tactic: tuple[str, float | None] | None = None):
        self.replies = replies
        self.tactic = tactic
        self.calls: list[tuple[str, str | None, str]] = []

    def choose(self, prompt, system_message, options, id_slot=None):
        return self.tactic

    def ask(
        self,
        prompt: str,
        system_message: str | None = None,
        sampler_config: str = "default",
        id_slot: int | None = None,
    ) -> StubResult:
        self.calls.append((prompt, system_message, sampler_config, id_slot))
        index = min(len(self.calls) - 1, len(self.replies) - 1)
        return StubResult(response=self.replies[index])


class ScriptedVoice:
    """A fake voice: plays back a scripted list of player lines, records
    what was spoken back."""

    def __init__(self, lines: list[str]):
        self._lines = iter(lines)
        self.spoken: list[tuple[str, str]] = []  # (speaker, text)

    def listen(self) -> str:
        try:
            return next(self._lines)
        except StopIteration:
            raise EOFError from None

    def speak(self, text: str, speaker: str = "guard") -> None:
        self.spoken.append((speaker, text))


def test_run_turn_updates_mood_and_memory():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="Hmph. Fine.")

    reply, speaker, outcome = run_turn(scenario, llm, "please, my friend")

    assert reply == "Hmph. Fine."
    assert speaker == "guard"
    assert outcome is None
    assert scenario.guard.affiliation.value > 40
    assert "player: please, my friend" in scenario.guard.memory
    assert "guard: Hmph. Fine." in scenario.guard.memory
    assert llm.calls[0][0] == "please, my friend"


def test_secret_reveal_flag_flips_only_after_the_eligible_turn():
    # engine/loop.py owns the timing of Guard.maybe_reveal_secret(): the
    # turn eligibility first opens still gets the brief's "may reveal"
    # framing (a real chance to narrate the moment, checked via calls[0][1]
    # below) rather than skipping straight to "already revealed" before
    # anything's actually been said.
    scenario = build_cell_and_guard()
    scenario.guard.affiliation.value = scenario.guard.secret_reveal_threshold
    llm = StubLLM(reply="Hmph.")

    assert scenario.guard.secret_revealed is False
    run_turn(scenario, llm, "please, tell me something real")

    assert "may let a fragment" in llm.calls[0][1]  # this turn's own brief
    assert scenario.guard.secret_revealed is True  # flipped for next turn

    # calls[1] is this turn's fact-extraction call (system_message=None), not
    # the next turn's narration brief — that's calls[2], since each guard
    # turn now makes a narration call followed by an extraction call.
    run_turn(scenario, llm, "anything else?")
    assert "already let this slip" in llm.calls[2][1]


def test_bland_dismissal_triggers_one_retry():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Silence.", "Ten years on this watch. Longest yet."])

    reply, _, _ = run_turn(scenario, llm, "please, my friend")

    assert reply == "Ten years on this watch. Longest yet."
    # narration attempt + retry + the fact-extraction call that follows every
    # successful guard turn (see engine/loop.py's _extract_new_fact).
    assert len(llm.calls) == 3
    assert "Note" in llm.calls[1][1]  # the retry brief carries the nudge
    assert llm.calls[0][2] == "default"
    assert llm.calls[1][2] == "retry"  # resampled with higher diversity, not a repeat


def test_retry_gives_up_after_one_more_bland_reply():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Silence.", "Nothing."])

    reply, _, _ = run_turn(scenario, llm, "please, my friend")

    assert reply == "Silence."  # kept the first attempt rather than looping


def test_verbatim_self_repeat_triggers_one_retry():
    scenario = build_cell_and_guard()
    scenario.guard.remember("player", "earlier line")
    scenario.guard.remember("guard", "Move slow.")
    llm = SequencedLLM(["Move slow.", "Wait by the wall."])

    reply, _, _ = run_turn(scenario, llm, "come on then")

    assert reply == "Wait by the wall."
    assert len(llm.calls) == 3  # narration + retry + fact-extraction
    assert "repeat" in llm.calls[1][1].lower()  # retry brief carries the repeat nudge
    assert llm.calls[1][2] == "retry"


def test_verbatim_voice_example_reuse_triggers_one_retry():
    # Regression (real playtest 2026-09-14): asked "What's your name?", got
    # back "Garrick. Now hush." verbatim -- brief.py's own VOICE_EXAMPLES
    # line, not a fresh reply. Never actually said by this guard before, so
    # only checking guard.own_lines() wouldn't have caught it.
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Garrick. Now hush.", "Names don't matter in here."])

    reply, _, _ = run_turn(scenario, llm, "what's your name?")

    assert reply == "Names don't matter in here."
    assert len(llm.calls) == 3  # narration + retry + fact-extraction
    assert "examples" in llm.calls[1][1].lower()  # the specific nudge, not the generic repeat one
    assert llm.calls[1][2] == "retry"


def test_room_description_triggers_one_retry():
    # Regression (real playtest 2026-09-14): "Tell me about this place" got
    # "This is a cell. It's cold." -- breaking PERSONA's own rule that the
    # guard never describes the room (that's the Dungeon Master's job).
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["This is a cell. It's cold.", "That's not mine to say."])

    reply, _, _ = run_turn(scenario, llm, "tell me about this place")

    assert reply == "That's not mine to say."
    assert len(llm.calls) == 3  # narration + retry + fact-extraction
    assert "dungeon master" in llm.calls[1][1].lower()
    assert llm.calls[1][2] == "retry"


def test_room_description_falls_back_to_safe_line_if_retry_also_fails():
    # Same shape as the voice-example fallback below -- measured directly
    # against the real model, this failure mode also doesn't reliably
    # escape via resampling (4/4 still named the room, real playtest
    # 2026-09-14), so a second failure ships the guardrail's safe line.
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["This is a cell.", "It's a cell, obviously."])

    reply, _, _ = run_turn(scenario, llm, "tell me about this place")

    assert reply == "Enough talk."
    # narration + retry only -- a fallback line is the engine's own words,
    # nothing improvised to canonize, so no fact-extraction call follows.
    assert len(llm.calls) == 2


def test_voice_example_reuse_falls_back_to_safe_line_if_retry_also_fails():
    # Regression (real playtest 2026-09-14): unlike bland/self-repeat, a
    # resample at retry temperature reproduced the exact voice-example line
    # 4/4 times against the real model — resampling alone doesn't reliably
    # escape this one. Ship the guardrail's own safe line rather than a
    # second verbatim copy.
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Garrick. Now hush.", "Garrick. Now hush."])

    reply, _, _ = run_turn(scenario, llm, "what's your name?")

    assert reply == "Enough talk."
    # narration + retry only -- a fallback line is the engine's own words,
    # nothing improvised to canonize, so no fact-extraction call follows.
    assert len(llm.calls) == 2


def test_repeat_retry_falls_back_to_safe_line_if_still_repeated():
    # Regression (real sessions 2026-09-15): "Begging doesn't work." and
    # "Hunger is a powerful thing." each shipped twice verbatim in separate
    # long playtests -- the retry reproduced the exact same line both
    # times. This test used to assert the opposite ("kept the first
    # attempt" -- reply == "Move slow."), matching what bland dismissals
    # still do; corrected once real play showed self-repeats don't reliably
    # escape retry the way bland dismissals do (measured: ~50% escape rate
    # against the real model, common enough to explain both failures).
    scenario = build_cell_and_guard()
    scenario.guard.remember("player", "earlier line")
    scenario.guard.remember("guard", "Move slow.")
    llm = SequencedLLM(["Move slow.", "Move slow."])

    reply, _, _ = run_turn(scenario, llm, "come on then")

    assert reply == "Enough talk."
    # narration + retry only -- a fallback line is the engine's own words,
    # nothing improvised to canonize, so no fact-extraction call follows.
    assert len(llm.calls) == 2


def test_dm_repeat_retry_falls_back_to_a_dm_appropriate_safe_line():
    # Regression (real playtest 2026-09-16): the guard was heard saying "The
    # guard grunts, and says nothing more." -- third-person narration voiced
    # as his own first-person line, breaking PERSONA's own rule. The shared
    # fallback was also wrong the *other* way: this proves a DM self-repeat
    # falls back to a DM-appropriate line, not the guard's.
    scenario = build_cell_and_guard()
    scenario.guard.remember("dm", "A cold stone cell.")
    llm = SequencedLLM(["A cold stone cell.", "A cold stone cell."])

    reply, speaker, _ = run_turn(scenario, llm, "describe the room")

    assert speaker == "dm"
    assert reply == "The moment passes without another word."
    assert len(llm.calls) == 2  # no extraction call for a fallback line
    assert scenario.world.established_facts == []


def test_dm_narration_records_an_improvised_scene_fact():
    # R1 (REVIEW.md 2026-09-18): the PRD's own flagship Gotcha #3 example
    # is a DM detail, but only the guard's improvisations were canonized.
    scenario = build_cell_and_guard()
    llm = SequencedLLM(
        [
            "Stone walls. A single iron grate covers the door.",
            "A single iron grate covers the door.",
        ]
    )

    _, speaker, _ = run_turn(scenario, llm, "describe the room")

    assert speaker == "dm"
    assert scenario.world.established_facts == ["A single iron grate covers the door."]
    assert llm.calls[1][1] is None  # the extraction call, not a brief
    assert llm.calls[1][3] == FACT_EXTRACTION_ID_SLOT
    assert scenario.guard.established_facts == []  # scene canon, not the guard's


def test_recorded_scene_fact_is_fed_back_into_the_next_dm_brief():
    scenario = build_cell_and_guard()
    scenario.world.add_established_fact("A single iron grate covers the door.")
    llm = StubLLM(reply="Damp stone.")

    run_turn(scenario, llm, "describe the room")

    assert "A single iron grate covers the door." in llm.calls[0][1]


def test_dm_refusal_also_gets_scene_facts_canonized():
    # Refusals improvise too ("only damp stone and a rusted bucket") -- same
    # canonization as narration, fed back into later refusal briefs.
    scenario = build_cell_and_guard()
    llm = SequencedLLM(
        ["No magic here. A rusted bucket sits in the corner.", "A rusted bucket sits in the corner."]
    )

    run_turn(scenario, llm, "I cast a fireball")

    assert scenario.world.established_facts == ["A rusted bucket sits in the corner."]


def test_dm_fact_the_narration_never_said_is_rejected():
    # Regression (real backend, 2026-09-18): the extraction model recorded
    # "The iron door is etched with faint, swirling patterns." when the DM
    # had only said "A heavy iron door bars your exit." -- invented canon.
    # The engine now requires the fact to be quoted verbatim from the reply.
    scenario = build_cell_and_guard()
    llm = SequencedLLM(
        [
            "A heavy iron door bars your exit.",
            "The iron door is etched with faint, swirling patterns.",
        ]
    )

    run_turn(scenario, llm, "describe my surroundings")

    assert scenario.world.established_facts == []


def test_dm_fact_quote_tolerates_case_quotes_and_trailing_punctuation():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(
        ["Faint carvings cover the rough surface!", '"faint carvings cover the rough surface."']
    )

    run_turn(scenario, llm, "describe the walls")

    assert scenario.world.established_facts == ["faint carvings cover the rough surface."]


def test_dm_turn_records_nothing_when_extraction_says_none():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Cold stone.", "NONE"])

    run_turn(scenario, llm, "describe the room")

    assert scenario.world.established_facts == []


def test_empty_extraction_answer_is_not_recorded_as_a_fallback_line():
    # Latent bug found while fixing R1: extraction ran its answer through
    # guardrail.filter_reply, which swaps an empty reply for the speaker's
    # fallback line -- so "" became "Enough talk." and got recorded as canon.
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Hmph. Fine.", ""])

    run_turn(scenario, llm, "please, my friend")

    assert scenario.guard.established_facts == []


def test_guard_fact_the_reply_never_said_is_rejected():
    # REVIEW.md R10: the extraction model was caught inventing canon on the
    # DM side; the guard's used to be a free paraphrase nothing could check.
    # A "fact" not quoted from his actual reply never enters the ledger.
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Kelsey. By the river.", "He has a wife and two daughters in Kelsey."])

    run_turn(scenario, llm, "where are you from?")

    assert scenario.guard.established_facts == []


def test_run_turn_records_a_newly_improvised_fact():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Kelsey. By the river. Now hush.", "Kelsey. By the river."])

    run_turn(scenario, llm, "where are you from?")

    # Built by the engine from verbatim parts -- the player's question plus
    # the guard's own verified words -- never the extraction model's phrasing.
    assert scenario.guard.established_facts == [
        'Asked "where are you from?", you said: "Kelsey. By the river."'
    ]
    assert llm.calls[1][1] is None  # extraction call has no brief, unlike narration
    assert llm.calls[1][2] == FACT_EXTRACTION_SAMPLER_KWARGS
    # Regression (2026-09-16, real backend): sharing the narration calls'
    # default id_slot meant this call evicted the brief's cached prefix
    # every turn, forcing a full re-prefill on every single guard turn
    # instead of just the first. Must land on its own slot.
    assert llm.calls[1][3] == FACT_EXTRACTION_ID_SLOT
    assert llm.calls[0][3] != FACT_EXTRACTION_ID_SLOT  # narration keeps the default slot


def test_run_turn_does_not_record_a_fact_when_extraction_says_none():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Hmph. Fine.", "NONE"])

    run_turn(scenario, llm, "please, my friend")

    assert scenario.guard.established_facts == []


def test_run_turn_does_not_record_a_fact_for_near_miss_negative_answers():
    # Regression (real backend, 2026-09-16): the extraction prompt asks for
    # exactly "NONE", but the real model sometimes answers plain "No" --
    # that used to slip past an exact-match check and get recorded as a
    # bogus "fact" (see _NO_NEW_FACT_ANSWERS in engine/loop.py).
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Wife and kids. They're not here.", "No"])

    run_turn(scenario, llm, "do you have a family?")

    assert scenario.guard.established_facts == []


def test_environment_query_routes_to_dm_without_moving_mood():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="A cold stone cell, a locked door.")
    starting_mood = scenario.guard.affiliation.value

    reply, speaker, outcome = run_turn(scenario, llm, "what does this place look like?")

    assert speaker == "dm"
    assert outcome is None
    assert reply == "A cold stone cell, a locked door."
    assert scenario.guard.affiliation.value == starting_mood
    assert "dm: A cold stone cell, a locked door." in scenario.guard.memory
    # The DM's brief, not the guard's — should describe the scene, not voice the guard.
    assert "Dungeon Master" in llm.calls[0][1]


def test_ungrounded_action_is_refused_by_the_dm():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="There is no such thing here.")
    starting_mood = scenario.guard.affiliation.value

    _reply, speaker, outcome = run_turn(scenario, llm, "I cast a fireball at the guard")

    assert speaker == "dm"
    assert outcome is None
    assert scenario.guard.affiliation.value == starting_mood
    assert "no place here" in llm.calls[0][1] or "no such thing" in llm.calls[0][1].lower()


def test_kind_conversation_reaches_unlock():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="...")
    # Varied phrasing avoids the repeat penalty, which would otherwise cancel
    # out most of the kindness delta (see test_repeating_the_same_line_is_penalised).
    kind_lines = [f"please, my friend, thank you kindly ({i})" for i in range(15)]

    outcome = None
    for line in kind_lines:
        _, _, outcome = run_turn(scenario, llm, line)
        if outcome:
            break

    assert outcome == "unlock"
    assert scenario.door.locked is False


def test_hostile_conversation_reaches_lockout():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="...")
    hostile_lines = ["open the door or I will kill you, idiot"] * 15

    outcome = None
    for line in hostile_lines:
        _, _, outcome = run_turn(scenario, llm, line)
        if outcome:
            break

    assert outcome == "lockout"


def test_run_loop_speaks_intro_as_the_dm(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM()
    voice = ScriptedVoice(["quit"])
    save_path = tmp_path / "save.json"

    run_loop(scenario, llm, voice, save_path)

    assert voice.spoken[0][0] == "dm"


def test_run_loop_ends_session_on_unlock(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="...")
    lines = [f"please, my friend, thank you kindly ({i})" for i in range(15)]
    voice = ScriptedVoice(lines)
    save_path = tmp_path / "save.json"

    run_loop(scenario, llm, voice, save_path)

    assert scenario.door.locked is False
    assert any("free" in text for _, text in voice.spoken)
    assert save_path.is_file()


def test_run_loop_quits_on_command(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM()
    voice = ScriptedVoice(["hello", "quit"])
    save_path = tmp_path / "save.json"

    run_loop(scenario, llm, voice, save_path)

    assert len(llm.calls) == 2  # narration + fact-extraction, for the one "hello" turn


def test_restating_canon_beats_the_self_repeat_fallback():
    # Regression (real backend, 2026-09-18): asked "Remind me, where did you
    # grow up?", the guard's consistent answer was his earlier line word for
    # word -- flagged as a self-repeat, retried, repeated again, and replaced
    # by "Enough talk.", dodging a fact he'd already given. Gotcha #15 (don't
    # echo) must yield to Gotcha #3 (stay bound to your word).
    scenario = build_cell_and_guard()
    guard = scenario.guard
    guard.remember("player", "What town did you grow up in?")
    guard.remember("guard", "Blackwood. A quiet place.")
    guard.add_established_fact(
        'Asked "What town did you grow up in?", you said: "Blackwood. A quiet place."'
    )
    llm = SequencedLLM(["Blackwood. A quiet place.", "Blackwood. A quiet place.", "NONE"])

    reply, _, _ = run_turn(scenario, llm, "Remind me, where did you grow up?")

    assert reply == "Blackwood. A quiet place."
    assert llm.calls[1][2] == "retry"  # fresh wording was still tried first


def test_unrelated_self_repeat_still_falls_back():
    # The exemption is only for restating canon -- an idle echo of a line
    # that isn't a recorded fact still gets the fallback, as before.
    scenario = build_cell_and_guard()
    guard = scenario.guard
    guard.remember("guard", "Move slow.")
    guard.add_established_fact('Asked "Where from?", you said: "Blackwood."')
    llm = SequencedLLM(["Move slow.", "Move slow."])

    reply, _, _ = run_turn(scenario, llm, "come on then")

    assert reply == "Enough talk."


# --- R5: a classified tactic drives the mood, before the reply ---


def test_guard_turn_is_scored_by_the_classified_tactic():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="Hmph.", tactic=("empathy", 0.9))

    run_turn(scenario, llm, "I'm sorry about your brother.")

    assert scenario.guard.affiliation.value == 40 + GARRICK_SUSCEPTIBILITY["empathy"]
    assert scenario.guard.tactic_counts == {"empathy": 1}


def test_classifier_sees_the_guards_previous_line_for_context():
    scenario = build_cell_and_guard()
    scenario.guard.remember("guard", "Dig.")
    llm = StubLLM(reply="Hmph.", tactic=("other", 0.9))

    run_turn(scenario, llm, "yes Dig")

    prompt = llm.choices[0][0]
    assert 'Guard: "Dig."' in prompt and '"yes Dig"' in prompt


def test_a_winning_line_can_unlock_on_the_turn_it_lands():
    # The mood is decided before the reply, so crossing the threshold opens
    # the door on this turn, not the next.
    scenario = build_cell_and_guard()
    scenario.guard.affiliation.value = 72
    llm = StubLLM(reply="Go. Before I think better of it.", tactic=("empathy", 0.9))

    _, _, outcome = run_turn(scenario, llm, "Your brother would have wanted mercy.")

    assert outcome == "unlock"
    assert scenario.door.locked is False


def test_dm_turns_are_not_classified():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="Cold stone.", tactic=("empathy", 0.9))

    run_turn(scenario, llm, "describe the room")

    assert llm.choices == []
    assert scenario.guard.affiliation.value == 40


# --- R4: the reply comes back before fact recording runs ---


def test_play_turn_returns_the_reply_before_fact_extraction():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Kelsey. By the river.", "Kelsey. By the river."])

    turn = play_turn(scenario, llm, "where are you from?")

    assert turn.reply == "Kelsey. By the river."
    assert len(llm.calls) == 1  # only the reply so far -- extraction is deferred
    assert scenario.guard.established_facts == []

    turn.finish()

    assert len(llm.calls) == 2
    assert scenario.guard.established_facts == [
        'Asked "where are you from?", you said: "Kelsey. By the river."'
    ]


def test_finish_runs_the_deferred_work_only_once():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Kelsey.", "NONE"])
    turn = play_turn(scenario, llm, "where are you from?")

    turn.finish()
    turn.finish()

    assert len(llm.calls) == 2


def test_run_loop_still_records_facts_before_saving(tmp_path):
    # run_loop overlaps fact recording with delivering the reply, but must
    # join it before saving -- a save must never miss a turn's canon.
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Kelsey. By the river.", "Kelsey. By the river."])
    save_path = tmp_path / "save.json"

    run_loop(scenario, llm, ScriptedVoice(["where are you from?"]), save_path)

    saved = json.loads(save_path.read_text())
    assert saved["guard_established_facts"] == [
        'Asked "where are you from?", you said: "Kelsey. By the river."'
    ]


# --- R15 difficulty switch + R6 transcripts ---


def test_play_turn_applies_the_scenarios_difficulty():
    from engine.tactics import EASY

    scenario = build_cell_and_guard()
    scenario.difficulty = EASY
    llm = StubLLM(reply="Hmph.", tactic=("bribe", 0.9))

    run_turn(scenario, llm, "Look I have gold")

    assert scenario.guard.affiliation.value == 40  # easy: the model can't penalise


def test_run_loop_writes_a_transcript_line_per_turn(tmp_path):
    # REVIEW.md R6: terminal playtests used to survive only in chat.
    from engine.tactics import EASY

    scenario = build_cell_and_guard()
    scenario.difficulty = EASY
    llm = StubLLM(reply="Hmph.", tactic=("empathy", 0.9))
    transcript = tmp_path / "t.jsonl"

    run_loop(
        scenario, llm, ScriptedVoice(["I'm sorry about your brother.", "describe the room"]),
        tmp_path / "save.json", transcript,
    )

    rows = [json.loads(line) for line in transcript.read_text().splitlines()]
    assert [r["speaker"] for r in rows] == ["guard", "dm"]
    assert rows[0]["difficulty"] == "easy"
    assert rows[0]["tactic"] == "empathy"
    assert rows[0]["mood_delta"] == GARRICK_SUSCEPTIBILITY["empathy"]
    assert rows[1]["mood_delta"] == 0
