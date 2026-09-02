import pytest

from draft_assistant.aliases import build_aliases, normalize_hero
from draft_assistant.heroes import load_data
from draft_assistant.models import Hero


def test_common_alias_normalizes_case_insensitively():
    assert normalize_hero("SF", set(load_data()[0])) == "shadow_fiend"


def test_russian_alias_normalizes():
    assert normalize_hero("СФ", set(load_data()[0])) == "shadow_fiend"


@pytest.mark.parametrize(("alias", "hero_id"), [("qop", "queen_of_pain"), ("potm", "mirana")])
def test_aliases_resolve_to_heroes_in_the_data(alias, hero_id):
    assert normalize_hero(alias, set(load_data()[0])) == hero_id


@pytest.mark.parametrize("value", ["shadow_fiend", "Shadow Fiend", "shadow-fiend"])
def test_canonical_and_display_names_normalize(value):
    heroes = load_data()[0]
    assert normalize_hero(value, set(heroes), build_aliases(heroes)) == "shadow_fiend"


@pytest.mark.parametrize("alias", ["SF", "bara", "ls", "naix", "jugg", "am", "wk", "spec", "pa", "qop", "potm", "np", "furion", "kotl", "bh", "bs", "cm", "dp", "dk", "ember", "fv", "gyro", "invoker", "lesh", "mk", "morph", "necro", "od", "pango", "sd", "sky", "ta", "tb", "tide", "tiny", "treant", "troll", "tusk", "ursa", "veno", "viper", "wr", "windrunner", "ww", "zeus"])
def test_required_common_aliases_normalize(alias):
    heroes = load_data()[0]
    assert normalize_hero(alias, set(heroes), build_aliases(heroes)) in heroes


def test_unknown_alias_is_clear_error():
    with pytest.raises(ValueError, match="Unknown hero: lifsteler"):
        normalize_hero("lifsteler", set(load_data()[0]))


def test_alias_collision_is_rejected():
    heroes = {"shadow_fiend": Hero("shadow_fiend", "SF", ("mid",), 50, {"mid": 10}), "storm_spirit": Hero("storm_spirit", "sf", ("mid",), 50, {"mid": 10})}
    with pytest.raises(ValueError, match="Alias collision"):
        build_aliases(heroes)
