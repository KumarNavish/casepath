"""Tests for the two modules added for the confirmatory run: the episode writer's validator and the
pre-registered decision analysis. Both decide whether a benchmark episode or a hypothesis is admitted,
so a silent bug in either would corrupt the confirmatory result rather than crash it."""
from __future__ import annotations

import pytest

from casepath_api.arena_v1.decide_confirm import holm
from casepath_api.arena_v1.write_episodes import _problems

BRIEF = {
    "paragraphs": [{"id": "src#p1"}, {"id": "gov#h1"}, {"id": "ret-A1-final#p1"}],
    "catalog": [{"document_id": "A1"}, {"document_id": "A2"}],
}
LONG = "x" * 60


def _texts(**over):
    base = {"src#p1": LONG, "gov#h1": LONG, "ret-A1-final#p1": LONG}
    base.update(over)
    return base


def test_clean_episode_has_no_problems():
    assert _problems(BRIEF, _texts()) == []


def test_missing_and_unknown_paragraph_ids_are_reported():
    t = _texts()
    del t["gov#h1"]
    t["gov#h9"] = LONG
    problems = _problems(BRIEF, t)
    assert any("missing paragraph ids: gov#h1" in p for p in problems)
    assert any("unknown paragraph ids: gov#h9" in p for p in problems)


@pytest.mark.parametrize("word", ["attached", "enclosed", "beigelegt", "beiliegend", "hearsay"])
def test_each_banned_delivery_word_is_caught(word):
    problems = _problems(BRIEF, _texts(**{"src#p1": f"The report is {word} to this message. {LONG}"}))
    assert any(word in p and "src#p1" in p for p in problems)


def test_banned_word_matches_only_at_a_word_boundary():
    # "attachment point" must not fire on the prefix of an unrelated word further in
    assert _problems(BRIEF, _texts(**{"src#p1": f"The bracket detached from the wall. {LONG}"})) == []


def test_catalogue_document_id_in_prose_is_caught():
    problems = _problems(BRIEF, _texts(**{"ret-A1-final#p1": f"This is record A2 of the file. {LONG}"}))
    assert any("A2" in p for p in problems)


def test_document_id_is_not_flagged_inside_a_longer_token():
    assert _problems(BRIEF, _texts(**{"src#p1": f"Reference A12B is unrelated. {LONG}"})) == []


def test_short_or_non_string_text_is_reported():
    assert any("shorter than 40" in p for p in _problems(BRIEF, _texts(**{"src#p1": "too short"})))
    assert any("missing" in p for p in _problems(BRIEF, _texts(**{"src#p1": None})))


def test_holm_orders_and_inflates_the_smaller_p_value():
    adj = holm({"H2": 0.01, "H3": 0.30})
    assert adj["H2"]["p_holm"] == pytest.approx(0.02)   # smallest p times m=2
    assert adj["H3"]["p_holm"] == pytest.approx(0.30)   # largest p times 1
    assert adj["H2"]["reject_at_05"] and not adj["H3"]["reject_at_05"]


def test_holm_is_monotone_so_a_later_test_never_beats_an_earlier_one():
    adj = holm({"H2": 0.04, "H3": 0.041})
    assert adj["H2"]["p_holm"] == pytest.approx(0.08)
    assert adj["H3"]["p_holm"] >= adj["H2"]["p_holm"]
    assert not adj["H2"]["reject_at_05"] and not adj["H3"]["reject_at_05"]


def test_holm_never_exceeds_one():
    assert holm({"H2": 0.9, "H3": 0.95})["H3"]["p_holm"] == pytest.approx(1.0)
