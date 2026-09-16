from engine.character import Stat, has_unnegated_match


def test_stat_clamps_to_bounds():
    stat = Stat(value=95, floor=0, ceiling=100)
    stat.adjust(20)
    assert stat.value == 100
    stat.adjust(-500)
    assert stat.value == 0


def test_stat_clamps_to_a_narrower_per_character_range():
    # A generally untrusting character: floor/ceiling narrower than the
    # engine's own 0-100 rail, not a second pair of numbers -- see the
    # design discussion (devlog 2026-09-16).
    stat = Stat(value=10, floor=1, ceiling=30)
    stat.adjust(1000)
    assert stat.value == 30
    stat.adjust(-1000)
    assert stat.value == 1


def test_stat_base_defaults_to_starting_value():
    stat = Stat(value=25, floor=0, ceiling=100)
    assert stat.base == 25
    stat.adjust(50)
    assert stat.base == 25  # adjust() moves value, not the recorded base


def test_stat_base_can_be_set_explicitly():
    stat = Stat(value=25, floor=0, ceiling=100, base=40)
    assert stat.base == 40


def test_stat_band_walks_the_ascending_ladder():
    bands = ((15, "hostile"), (40, "gruff"), (100, "warm"))
    assert Stat(value=0, bands=bands).band == "hostile"
    assert Stat(value=15, bands=bands).band == "hostile"
    assert Stat(value=16, bands=bands).band == "gruff"
    assert Stat(value=100, bands=bands).band == "warm"


def test_stat_band_is_empty_string_with_no_bands_configured():
    assert Stat(value=50).band == ""


def test_has_unnegated_match_true_for_a_plain_trigger_word():
    tokens = ["you", "are", "pathetic"]
    assert has_unnegated_match(tokens, {"pathetic"}) is True


def test_has_unnegated_match_false_when_negated_nearby():
    tokens = ["you", "are", "not", "pathetic"]
    assert has_unnegated_match(tokens, {"pathetic"}) is False


def test_has_unnegated_match_true_when_negation_is_out_of_window():
    tokens = ["no", "that", "is", "not", "what", "i", "meant", "but", "you", "are", "still", "pathetic"]
    assert has_unnegated_match(tokens, {"pathetic"}) is True
