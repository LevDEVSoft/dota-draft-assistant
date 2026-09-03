import pytest

from draft_assistant.cli import format_explanation
from draft_assistant.heroes import load_data, parse_draft
from draft_assistant.scoring import recommend
import draft_assistant.scoring as scoring
from draft_assistant.models import Draft, Hero


DRAFT = "sf bara ogre silencer | underlord jakiro wd | carry"


def test_parses_draft_input():
    draft = parse_draft(DRAFT)
    assert draft.enemies == ("shadow_fiend", "spirit_breaker", "ogre_magi", "silencer")
    assert draft.allies == ("underlord", "jakiro", "witch_doctor")
    assert draft.role == "carry"


def test_parses_extra_whitespace_multi_word_heroes_and_empty_team_sections():
    draft = parse_draft("  shadow fiend   bara |   | carry ")
    assert draft.enemies == ("shadow_fiend", "spirit_breaker")
    assert draft.allies == ()


def test_parses_commas_and_case_insensitively():
    draft = parse_draft("SF,BARA,OGRE | JAKIRO,WD | CARRY")
    assert draft.enemies == ("shadow_fiend", "spirit_breaker", "ogre_magi")


@pytest.mark.parametrize("value", ["sf sf | underlord | carry", "sf | sf | carry"])
def test_duplicate_heroes_are_rejected(value):
    with pytest.raises(ValueError, match="cannot appear more than once"):
        parse_draft(value)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("sf | underlord | jungle", "Unknown role"),
        ("sf | underlord", "Use: enemies | allies | role"),
    ],
)
def test_invalid_role_and_malformed_draft_are_rejected(value, message):
    with pytest.raises(ValueError, match=message):
        parse_draft(value)


def test_only_requested_role_is_recommended():
    choices = recommend(parse_draft(DRAFT))
    assert all("carry" in item.hero.roles for item in choices)


def test_existing_draft_heroes_are_not_recommended():
    choices = recommend(parse_draft("spectre sf | underlord | carry"))
    assert {item.hero.id for item in choices}.isdisjoint({"spectre", "shadow_fiend", "underlord"})


def test_scoring_is_deterministic():
    assert recommend(parse_draft(DRAFT)) == recommend(parse_draft(DRAFT))


def test_recommendations_are_ordered():
    choices = recommend(parse_draft(DRAFT))
    assert [item.hero.id for item in choices] == ["lifestealer", "juggernaut", "wraith_king"]
    assert [item.score for item in choices] == sorted((item.score for item in choices), reverse=True)


def test_explanation_contains_breakdown():
    heroes = load_data()[0]
    explanation = format_explanation(recommend(parse_draft(DRAFT))[0], heroes)
    assert "base: +62.0" in explanation
    assert "role: +10.0" in explanation
    assert "vs Spirit Breaker: +6.0" in explanation
    assert "with Underlord: +5.0" in explanation


def test_explanation_describes_negative_matchup_value():
    heroes = load_data()[0]
    anti_mage = next(item for item in recommend(parse_draft(DRAFT), limit=20) if item.hero.id == "anti_mage")
    assert "vs Silencer: -5.0" in format_explanation(anti_mage, heroes)


def test_breakdown_total_is_exact_scoring_formula():
    item = recommend(parse_draft(DRAFT))[0]
    breakdown = item.breakdown
    assert breakdown.total == breakdown.base + breakdown.role + sum(value for _, value in breakdown.matchup_contributions) + sum(value for _, value in breakdown.synergy_contributions)
    assert item.score == breakdown.total


def test_stats_components_replace_manual_values_without_double_counting(monkeypatch):
    heroes = {"axe": Hero("axe", "Axe", ("carry",), 50, {"carry": 10}), "bane": Hero("bane", "Bane", ("support",), 50, {"support": 10}), "chen": Hero("chen", "Chen", ("support",), 50, {"support": 10})}
    monkeypatch.setattr(scoring, "load_data", lambda: (heroes, {"axe": {"bane": 9}}, {("axe", "chen"): 7}))
    monkeypatch.setattr(scoring, "_stats", lambda: ({"axe": 2}, {"axe": {"bane": 3}}, {("axe", "chen"): 4}))
    result = scoring.recommend(Draft(("bane",), ("chen",), "carry"), data="stats")[0]
    assert (result.breakdown.base, result.breakdown.matchups, result.breakdown.synergies) == (2, 3, 4)
