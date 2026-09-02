from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from draft_assistant.data_sources import opendota
from draft_assistant.models import Hero


HEROES = {"axe": Hero("axe", "Axe", ("offlane",), 50, {}), "bane": Hero("bane", "Bane", ("support",), 50, {})}
MAPPING = {2: "axe", 3: "bane"}
ROWS = [{"id": 2, "1_pick": 10, "1_win": 6, "2_pick": 20, "2_win": 9}, {"id": 3, "1_pick": 0, "1_win": 0, "2_pick": 0, "2_win": 0}]


def test_hero_stats_aggregates_herald_guardian_and_normalizes_deterministically():
    snapshot = opendota.build_snapshot(ROWS, MAPPING, set(HEROES))
    axe = next(row for row in snapshot["meta"] if row["hero_id"] == "axe")
    assert (axe["matches"], axe["wins"], axe["herald_matches"], axe["guardian_wins"]) == (30, 15, 10, 9)
    assert axe["win_rate"] == .5 and axe["score"] == 0
    bane = next(row for row in snapshot["meta"] if row["hero_id"] == "bane")
    assert (bane["matches"], bane["win_rate"], bane["score"]) == (0, 0.0, 0)
    assert snapshot["metadata"]["rank_bracket"] == "HERALD_GUARDIAN"


@pytest.mark.parametrize("rows, message", [([{"id": 2, "1_pick": 1, "1_win": 2, "2_pick": 0, "2_win": 0}, ROWS[1]], "wins exceed"), ([{"id": 2, "1_pick": 1, "1_win": 1, "2_pick": 0}, ROWS[1]], "invalid 2_win")])
def test_invalid_missing_and_unknown_hero_ids_are_explicit(rows, message):
    with pytest.raises(ValueError, match=message):
        opendota.build_snapshot(rows, MAPPING, set(HEROES))


def test_unmapped_current_api_heroes_are_recorded_as_warning_metadata():
    snapshot = opendota.build_snapshot([*ROWS, {"id": 999, "1_pick": 1, "1_win": 1, "2_pick": 1, "2_win": 1}], MAPPING, set(HEROES))
    assert snapshot["metadata"]["unmapped_hero_ids"] == [999]
    assert opendota.build_snapshot([ROWS[0]], MAPPING, set(HEROES))["metadata"]["missing_mapped_hero_ids"] == [3]


@pytest.mark.parametrize("code, error", [(429, opendota.OpenDotaRateLimitError), (500, opendota.OpenDotaError)])
def test_http_errors_are_safe_and_mocked(monkeypatch, code, error):
    monkeypatch.setattr(opendota, "urlopen", lambda *_, **__: (_ for _ in ()).throw(HTTPError("url", code, "error", Message(), BytesIO())))
    with pytest.raises(error, match=str(code)):
        opendota.fetch_hero_stats()


def test_sync_writes_deterministic_snapshot_without_network(monkeypatch):
    from draft_assistant.heroes import DATA_DIR
    mapping_path = DATA_DIR / "hero_id_map.json"
    monkeypatch.setattr(opendota, "load_mapping", lambda _: MAPPING)
    monkeypatch.setattr(opendota, "fetch_hero_stats", lambda: ROWS)
    output = DATA_DIR / "generated" / "opendota-test.json"
    first = opendota.sync(output, HEROES, mapping_path)
    assert output.exists() and first["matchups"] == [] and first["synergies"] == []
    output.unlink()
