import pytest

from draft_assistant.heroes import load_data, parse_draft
from draft_assistant.scoring import matchup_score, recommend, synergy_score
from draft_assistant.validation import validate_synergies


def test_missing_scores_are_neutral_and_synergy_is_symmetric():
    _, matchups, synergies = load_data()
    assert matchup_score("axe", "bane", matchups) == 0
    assert synergy_score("lifestealer", "underlord", synergies) == synergy_score("underlord", "lifestealer", synergies) == 5


def test_matchup_sign_changes_total():
    choices = recommend(parse_draft("sf bara ogre silencer | | carry"), 20)
    lifestealer = next(choice for choice in choices if choice.hero.id == "lifestealer")
    anti_mage = next(choice for choice in choices if choice.hero.id == "anti_mage")
    assert dict(lifestealer.breakdown.matchup_contributions)["spirit_breaker"] > 0
    assert dict(anti_mage.breakdown.matchup_contributions)["silencer"] < 0


def test_duplicate_synergy_pair_is_rejected():
    with pytest.raises(ValueError):
        validate_synergies([{"heroes": ["axe", "bane"], "score": 1}, {"heroes": ["bane", "axe"], "score": 1}], {"axe", "bane"})
