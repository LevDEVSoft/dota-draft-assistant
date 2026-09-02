import pytest

from draft_assistant.cli import format_explanation
from draft_assistant.heroes import load_data, parse_draft
from draft_assistant.scoring import recommend


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
    assert "base rating: +62.0" in explanation
    assert "role suitability: +10.0" in explanation
    assert "matchup vs Spirit Breaker: +6.0" in explanation
    assert "synergy with Underlord: +5.0" in explanation


def test_explanation_describes_negative_matchup_value():
    heroes = load_data()[0]
    anti_mage = next(item for item in recommend(parse_draft(DRAFT), limit=20) if item.hero.id == "anti_mage")
    assert "matchup vs Silencer: -5.0" in format_explanation(anti_mage, heroes)
