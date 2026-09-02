import pytest

from draft_assistant.aliases import normalize_hero
from draft_assistant.heroes import load_data


def test_common_alias_normalizes_case_insensitively():
    assert normalize_hero("SF", set(load_data()[0])) == "shadow_fiend"


def test_russian_alias_normalizes():
    assert normalize_hero("СФ", set(load_data()[0])) == "shadow_fiend"


@pytest.mark.parametrize(("alias", "hero_id"), [("qop", "queen_of_pain"), ("potm", "mirana")])
def test_aliases_resolve_to_heroes_in_the_data(alias, hero_id):
    assert normalize_hero(alias, set(load_data()[0])) == hero_id


def test_unknown_alias_is_clear_error():
    with pytest.raises(ValueError, match="Unknown hero: invoker"):
        normalize_hero("invoker", set(load_data()[0]))
