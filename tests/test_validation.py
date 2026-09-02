import pytest

from draft_assistant.heroes import ROLES, load_data
from draft_assistant.validation import validate_aliases, validate_heroes


def test_complete_hero_data_is_unique_and_uses_valid_roles():
    heroes = load_data()[0]
    assert len(heroes) >= 126
    assert len({hero.display_name.casefold() for hero in heroes.values()}) == len(heroes)
    assert all(set(hero.roles) <= ROLES for hero in heroes.values())


@pytest.mark.parametrize(
    "hero",
    [
        {"id": "", "display_name": "A", "roles": ["mid"], "base_rating": 50, "role_scores": {"mid": 10}},
        {"id": "a", "display_name": "", "roles": ["mid"], "base_rating": 50, "role_scores": {"mid": 10}},
        {"id": "a", "display_name": "A", "roles": ["jungle"], "base_rating": 50, "role_scores": {"jungle": 10}},
        {"id": "a", "display_name": "A", "roles": ["mid"], "base_rating": "50", "role_scores": {"mid": 10}},
    ],
)
def test_malformed_hero_data_is_rejected(hero):
    with pytest.raises(ValueError):
        validate_heroes([hero])


def test_duplicate_hero_data_and_bad_alias_rejected():
    hero = {"id": "a", "display_name": "A", "roles": ["mid"], "base_rating": 50, "role_scores": {"mid": 10}}
    with pytest.raises(ValueError, match="Duplicate"):
        validate_heroes([hero, hero])
    with pytest.raises(ValueError, match="Invalid alias"):
        validate_aliases({"x": "missing"}, {"a"})
