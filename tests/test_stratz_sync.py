import json
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

import pytest

from draft_assistant import cli
from draft_assistant.data_sources import stratz
from draft_assistant.data_sources.mapping import load_mapping, validate_mapping
from draft_assistant.heroes import DATA_DIR, load_data
from draft_assistant.models import Hero


def _heroes():
    return {
        "axe": Hero("axe", "Axe", ("offlane",), 50, {}),
        "bane": Hero("bane", "Bane", ("support",), 50, {}),
        "juggernaut": Hero("juggernaut", "Juggernaut", ("carry",), 50, {}),
    }


def test_valve_mapping_covers_the_entire_local_roster():
    heroes = set(load_data()[0])
    mapping = load_mapping(DATA_DIR / "hero_id_map.json")
    assert len(mapping) == len(heroes) == 127
    validate_mapping(mapping, heroes)
    assert mapping[58] == "enchantress"
    assert mapping[131] == "ringmaster"
    assert mapping[145] == "kez"
    assert mapping[155] == "largo"


def test_execute_uses_mocked_authentication_and_parses_rate_limit_headers(monkeypatch):
    headers = Message()
    headers["Retry-After"] = "60"
    headers["X-RateLimit-Remaining"] = "0"
    headers["X-RateLimit-Reset"] = "120"
    error = HTTPError(stratz.ENDPOINT, 429, "Too Many Requests", headers, BytesIO(b"limited"))
    monkeypatch.setenv("STRATZ_API_TOKEN", "test-token")
    monkeypatch.setattr(stratz, "urlopen", lambda *_, **__: (_ for _ in ()).throw(error))
    with pytest.raises(stratz.StratzRateLimitError) as raised:
        stratz.execute("query { ok }")
    assert (raised.value.retry_after, raised.value.remaining, raised.value.reset) == (60, 0, 120)
    assert "test-token" not in str(raised.value)


def test_build_sync_plan_batches_all_role_meta_and_reuses_global_pairs(monkeypatch):
    monkeypatch.setattr(stratz, "load_mapping", lambda _: {1: "axe", 2: "bane", 8: "juggernaut"})
    plan = stratz.build_sync_plan(_heroes(), DATA_DIR / "hero_id_map.json")
    assert plan.meta_requests == 6
    assert plan.pair_hero_ids == (1, 2, 8)
    assert plan.expected_requests == 9


def test_real_all_role_plan_is_bounded_before_spending_quota():
    plan = stratz.build_sync_plan(load_data()[0], DATA_DIR / "hero_id_map.json")
    assert len(plan.pair_hero_ids) == 127
    assert plan.expected_requests == 133


def test_sync_batches_meta_paces_pairs_and_normalizes_all_pair_types(monkeypatch):
    heroes = _heroes()
    monkeypatch.setattr(stratz, "load_mapping", lambda _: {1: "axe", 2: "bane", 8: "juggernaut"})
    meta_calls, pair_calls, sleeps = [], [], []

    def fake_meta(ids, role, bracket):
        meta_calls.append((ids, role, bracket))
        return [{"heroId": 8, "position": "POSITION_1", "matchCount": 100, "winCount": 60}]

    def fake_pairs(hero_id, bracket):
        pair_calls.append((hero_id, bracket))
        if hero_id != 8:
            return {"vs": [], "with": []}
        return {"vs": [{"heroId1": 8, "heroId2": 1, "matchCount": 20, "winCount": 14}], "with": [{"heroId1": 8, "heroId2": 2, "matchCount": 20, "winCount": 13}]}

    monkeypatch.setattr(stratz, "fetch_meta", fake_meta)
    monkeypatch.setattr(stratz, "fetch_pairs", fake_pairs)
    output = DATA_DIR / "generated" / "sync-test-snapshot.json"
    snapshot = stratz.sync(output, heroes, DATA_DIR / "hero_id_map.json", pair_delay=0.3, sleeper=sleeps.append)

    assert meta_calls == [([1, 2, 8], None, "HERALD_GUARDIAN"), *[([1, 2, 8], role, "HERALD_GUARDIAN") for role in stratz.ROLE_POSITIONS]]
    assert pair_calls == [(1, "HERALD_GUARDIAN"), (2, "HERALD_GUARDIAN"), (8, "HERALD_GUARDIAN")]
    assert sleeps == [0.3, 0.3]
    assert json.loads(output.read_text()) == snapshot
    output.unlink()
    bucket = snapshot["brackets"]["HERALD_GUARDIAN"]
    assert set(bucket["roles"]) == set(stratz.ROLE_POSITIONS)
    assert bucket["pairs"]["matchups"][0]["opponent_id"] == "axe"
    assert bucket["pairs"]["synergies"][0]["heroes"] == ["bane", "juggernaut"]


def test_sync_paces_each_pair_after_the_first_and_can_be_disabled(monkeypatch):
    heroes = {"axe": Hero("axe", "Axe", ("carry",), 50, {}), "bane": Hero("bane", "Bane", ("carry",), 50, {})}
    monkeypatch.setattr(stratz, "load_mapping", lambda _: {1: "axe", 2: "bane"})
    monkeypatch.setattr(stratz, "fetch_meta", lambda *_: [])
    calls, sleeps = [], []
    monkeypatch.setattr(stratz, "fetch_pairs", lambda hero_id, _: calls.append(hero_id) or {"vs": [], "with": []})
    output = DATA_DIR / "generated" / "sync-test-snapshot.json"
    stratz.sync(output, heroes, DATA_DIR / "hero_id_map.json", pair_delay=0.3, sleeper=sleeps.append)
    output.unlink()
    assert calls == [1, 2]
    assert sleeps == [0.3]
    stratz.sync(output, heroes, DATA_DIR / "hero_id_map.json", pair_delay=0, sleeper=lambda _: pytest.fail("must not sleep"))
    output.unlink()


def test_rate_limit_stops_further_pair_requests(monkeypatch):
    heroes = {"axe": Hero("axe", "Axe", ("carry",), 50, {}), "bane": Hero("bane", "Bane", ("carry",), 50, {})}
    monkeypatch.setattr(stratz, "load_mapping", lambda _: {1: "axe", 2: "bane"})
    monkeypatch.setattr(stratz, "fetch_meta", lambda *_: [])
    calls = []
    def limited(hero_id, _):
        calls.append(hero_id)
        raise stratz.StratzRateLimitError(retry_after=60)
    monkeypatch.setattr(stratz, "fetch_pairs", limited)
    with pytest.raises(stratz.StratzRateLimitError):
        stratz.sync(DATA_DIR / "generated" / "sync-test-snapshot.json", heroes, DATA_DIR / "hero_id_map.json", pair_delay=0, sleeper=lambda _: None)
    assert calls == [1]


def test_cli_prints_plan_and_wires_all_role_sync(monkeypatch, capsys):
    expected_plan = stratz.SyncPlan((25, 74))
    monkeypatch.setattr(stratz, "build_sync_plan", lambda heroes, mapping_path: expected_plan)
    captured = {}
    def fake_sync(output, heroes, mapping_path, bracket):
        captured.update(output=output, heroes=heroes, mapping_path=mapping_path)
        return {"brackets": {bracket: {"roles": {role: {"meta": []} for role in stratz.ROLE_POSITIONS}, "pairs": {"matchups": [], "synergies": []}}}}
    monkeypatch.setattr(stratz, "sync", fake_sync)
    assert cli.main(["--sync-stats", "--stats-role", "mid"]) == 0
    output = capsys.readouterr().out
    assert "Meta requests: 6" in output and "Pair candidates: 2" in output and "Expected API requests: 8" in output
    assert captured["heroes"] == load_data()[0]
