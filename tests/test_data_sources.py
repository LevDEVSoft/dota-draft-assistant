import pytest

from draft_assistant.data_sources.mapping import validate_mapping
from draft_assistant.data_sources.import_snapshot import import_snapshot
from draft_assistant.data_sources.normalization import MATCHUP_MAX, confidence, matchup_rating, meta_rating, synergy_rating
from draft_assistant.heroes import DATA_DIR, load_data


FIXTURE = __import__("pathlib").Path(__file__).parent / "fixtures" / "synthetic_stats.json"


def test_confidence_shrinks_small_samples_and_bounds_scores():
    assert confidence(5) < confidence(5000)
    assert abs(meta_rating(1.0, 5)) < abs(meta_rating(1.0, 5000))
    assert meta_rating(0.5, 5000) == 0
    assert abs(matchup_rating(1.0, 0.0, 5000)) <= MATCHUP_MAX
    assert abs(synergy_rating(1.0, 0.0, 5000)) <= 6


def test_synthetic_fixture_contains_valid_optional_and_normalizable_values():
    import json
    raw = json.loads(FIXTURE.read_text())
    assert "pick_rate" not in raw["meta"][1]
    assert meta_rating(raw["meta"][0]["wins"] / raw["meta"][0]["matches"], raw["meta"][0]["matches"]) > 0


def test_mapping_rejects_unknown_target():
    with pytest.raises(ValueError, match="Unknown mapped hero"):
        validate_mapping({1: "missing"}, {"axe"})


@pytest.mark.parametrize(("fixture", "message"), [("synthetic_unknown.json", "Unknown external hero ID"), ("synthetic_malformed.json", "matches and wins")])
def test_import_rejects_unknown_ids_and_malformed_numbers(fixture, message):
    with pytest.raises(ValueError, match=message):
        import_snapshot(FIXTURE.parent / fixture, FIXTURE.parent / "unused-output", DATA_DIR / "hero_id_map.json", set(load_data()[0]))
