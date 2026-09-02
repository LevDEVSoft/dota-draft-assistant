import json

import pytest

from draft_assistant import cli
from draft_assistant.data_sources import stratz
from draft_assistant.data_sources.mapping import load_mapping, validate_mapping
from draft_assistant.heroes import DATA_DIR, load_data


def test_valve_mapping_covers_the_entire_local_roster():
    heroes = set(load_data()[0])
    mapping = load_mapping(DATA_DIR / "hero_id_map.json")
    assert len(mapping) == len(heroes) == 126
    validate_mapping(mapping, heroes)
    assert mapping[58] == "enchantress"
    assert mapping[147] == "kez"


def test_execute_uses_verified_authentication_and_user_agent(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"data": {"ok": true}}'

    def fake_open(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("STRATZ_API_TOKEN", "test-token")
    monkeypatch.setattr(stratz, "urlopen", fake_open)
    assert stratz.execute("query { ok }") == {"ok": True}
    assert captured["request"].get_header("Authorization") == "Bearer test-token"
    assert captured["request"].get_header("User-agent") == "STRATZ_API"


def test_fetch_helpers_send_verified_filters(monkeypatch):
    calls = []

    def fake_execute(query, variables):
        calls.append((query, variables))
        if "query Meta" in query:
            return {"heroStats": {"stats": [{"heroId": 1, "position": "POSITION_1", "matchCount": 10, "winCount": 6}]}}
        return {"heroStats": {"matchUp": [{"with": [], "vs": []}]}}

    monkeypatch.setattr(stratz, "execute", fake_execute)
    assert stratz.fetch_meta([1], "carry")[-1]["heroId"] == 1
    assert stratz.fetch_pairs(1) == {"with": [], "vs": []}
    assert calls[0][1] == {"ids": [1], "brackets": ["HERALD_GUARDIAN"], "positions": ["POSITION_1"]}
    assert calls[1][1] == {"id": 1, "brackets": ["HERALD_GUARDIAN"]}


def test_sync_normalizes_all_pair_types_and_writes_snapshot(monkeypatch):
    mapping_path = DATA_DIR / "hero_id_map.json"
    monkeypatch.setattr(stratz, "load_mapping", lambda _: {1: "axe", 2: "bane"})
    monkeypatch.setattr(stratz, "fetch_meta", lambda ids, role, bracket: [
        {"heroId": 1, "position": "POSITION_1", "matchCount": 100, "winCount": 60},
        {"heroId": 2, "position": "POSITION_1", "matchCount": 100, "winCount": 50},
    ])
    def fake_pairs(hero_id, bracket):
        if hero_id == 1:
            return {"vs": [{"heroId1": 1, "heroId2": 2, "matchCount": 20, "winCount": 14}], "with": [{"heroId1": 1, "heroId2": 2, "matchCount": 20, "winCount": 13}]}
        return {"vs": [{"heroId1": 1, "heroId2": 2, "matchCount": 20, "winCount": 14}], "with": [{"heroId1": 1, "heroId2": 2, "matchCount": 20, "winCount": 13}]}
    monkeypatch.setattr(stratz, "fetch_pairs", fake_pairs)

    output = DATA_DIR / "generated" / "sync-test-snapshot.json"
    snapshot = stratz.sync("carry", output, {"axe", "bane"}, mapping_path)

    assert json.loads(output.read_text()) == snapshot
    output.unlink()
    assert [(row["hero_id"], row["opponent_id"], row["matches"]) for row in snapshot["matchups"]] == [("axe", "bane", 20), ("bane", "axe", 20)]
    assert len(snapshot["synergies"]) == 1
    assert snapshot["synergies"][0]["heroes"] == ["axe", "bane"]
    # The second response is oriented heroId1, so its opponent-facing wins are inverted.
    assert snapshot["matchups"][1]["score"] < 0


def test_sync_rejects_incomplete_mapping_before_any_fetch(monkeypatch):
    monkeypatch.setattr(stratz, "load_mapping", lambda _: {1: "axe"})
    monkeypatch.setattr(stratz, "fetch_meta", lambda *_: pytest.fail("must not fetch"))
    with pytest.raises(ValueError, match="Missing mapped hero: bane"):
        stratz.sync("carry", DATA_DIR / "generated" / "sync-test-snapshot.json", {"axe", "bane"}, DATA_DIR / "hero_id_map.json")


def test_cli_sync_invokes_the_complete_pipeline(monkeypatch, capsys):
    captured = {}

    def fake_sync(role, output, heroes, mapping_path):
        captured.update(role=role, output=output, heroes=heroes, mapping_path=mapping_path)
        return {"meta": [{"hero_id": "axe"}], "matchups": [], "synergies": []}

    monkeypatch.setattr(stratz, "sync", fake_sync)
    assert cli.main(["--sync-stats", "--stats-role", "mid"]) == 0
    assert captured["role"] == "mid"
    assert captured["heroes"] == set(load_data()[0])
    assert captured["mapping_path"] == DATA_DIR / "hero_id_map.json"
    assert "Snapshot written: data/generated/snapshot.json" in capsys.readouterr().out
