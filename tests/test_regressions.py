import pytest

from draft_assistant.heroes import parse_draft
from draft_assistant.scoring import recommend


@pytest.mark.parametrize("value", [
    "sf bara ogre silencer | underlord jakiro wd | carry",
    "spectre sf underlord jakiro wd | | carry",
    "huskar weaver tidehunter | | offlane",
    "phantom_lancer bristleback | | carry",
    "zeus lina skywrath_mage | | carry",
    "drow_ranger sniper sven | | offlane",
])
def test_real_drafts_are_deterministic_and_legal(value):
    draft = parse_draft(value)
    first, second = recommend(draft), recommend(draft)
    assert first == second
    picks = set(draft.enemies + draft.allies)
    assert all(item.hero.id not in picks and draft.role in item.hero.roles for item in first)


def test_lifestealer_remains_high_for_seeded_case_a():
    ids = [item.hero.id for item in recommend(parse_draft("sf bara ogre silencer | underlord jakiro wd | carry"))]
    assert "lifestealer" in ids
