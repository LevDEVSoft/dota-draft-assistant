"""Synthetic boundary tests; these samples are not live provider statistics."""
import json
from datetime import UTC, datetime

import pytest

from draft_assistant import scoring
from draft_assistant.data_sources import patch_meta, stratz
from draft_assistant.models import Draft


def row(hour, hero=8, matches=100, wins=60):
    return dict(hour=hour, heroId=hero, matchCount=matches, winCount=wins)


def test_complete_hours_exclude_release_hour_and_incomplete_current_hour():
    calls = []
    def query(q, variables):
        calls.append(variables)
        assert 'bracketIds:[ARCHON]' in q and 'ALL_PICK_RANKED' in q
        return {'heroStats': {'winHour': [row(14400), row(10800), row(7200), row(3600)]}}
    result = patch_meta.collect_hours([8], 'POSITION_1', 7200, 15000, execute=query, sleeper=lambda _: None)
    assert [r['hour'] for r in result] == [10800, 7200]
    assert calls[0]['pos'] == ['POSITION_1']


def test_duplicate_page_fails_instead_of_double_counting():
    def query(*_):
        return {'heroStats': {'winHour': [row(7200)]}}
    with pytest.raises(ValueError, match='Duplicate'):
        patch_meta.collect_hours([8], 'POSITION_1', 7200, 15000, execute=query, sleeper=lambda _: None)


def fixture_snapshot():
    patch = {'patch': '7.42', 'release_timestamp': 3601}
    rows = {role: [row(7200)] for role in stratz.ROLE_POSITIONS}
    return patch_meta.build_snapshot(patch, rows, {8: 'juggernaut'}, datetime.fromtimestamp(15000, UTC).isoformat())


def test_snapshot_counts_observations_and_never_fabricates_unique_matches():
    snapshot, evidence = fixture_snapshot()
    meta = patch_meta.validate_snapshot(snapshot)
    assert meta['hero_observations'] == 500 and meta['unique_matches'] is None
    record = snapshot['brackets']['ARCHON']['roles']['carry']['meta'][0]
    assert record['score'] == pytest.approx((.6 - .5) * 10 * 100 / 1100)
    assert evidence['item_stats'] == []
    assert snapshot['brackets']['ARCHON']['pairs'] == {'matchups': [], 'synergies': []}


def test_release_boundary_is_enforced_even_for_imported_rows():
    with pytest.raises(ValueError, match='boundary'):
        patch_meta.build_snapshot({'patch': '7.42', 'release_timestamp': 3601}, {'carry': [row(3600)]}, {8: 'juggernaut'}, datetime.fromtimestamp(15000, UTC).isoformat())


def test_patch_snapshot_drives_scores_and_excludes_historical_fallback(tmp_path, monkeypatch):
    generated = tmp_path / 'generated'; generated.mkdir()
    snapshot, _ = fixture_snapshot()
    (generated / 'snapshot.json').write_text(json.dumps(snapshot), encoding='utf-8')
    (generated / 'opendota_snapshot.json').write_text(json.dumps({'meta': [{'hero_id': 'antimage', 'score': 100}]}), encoding='utf-8')
    monkeypatch.setattr(scoring, 'DATA_DIR', tmp_path)
    scoring._stats.cache_clear()
    for mode in ('auto', 'stats', 'hybrid'):
        picks = scoring.recommend(Draft(('axe',), (), 'carry'), 127, mode)
        assert [p.hero.id for p in picks] == ['juggernaut']
        assert picks[0].breakdown.base == pytest.approx(1 / 11)
        assert picks[0].breakdown.matchups == 0
        assert dict(picks[0].breakdown.matchup_sources)['axe'] == 'unavailable'
    scoring._stats.cache_clear()


def test_failed_refresh_preserves_existing_snapshot(tmp_path, monkeypatch):
    target = tmp_path / 'snapshot.json'; target.write_text('old snapshot')
    monkeypatch.setattr(patch_meta, 'detect_patch', lambda: {'patch': '7.42', 'release_timestamp': 3601})
    monkeypatch.setattr(stratz, 'execute', lambda *_: (_ for _ in ()).throw(stratz.StratzRateLimitError(60)))
    with pytest.raises(stratz.StratzRateLimitError):
        patch_meta.sync(tmp_path, {}, tmp_path / 'mapping.json')
    assert target.read_text() == 'old snapshot'


def test_validation_rebuilds_exports_and_detects_tampered_scores(tmp_path, monkeypatch):
    snapshot, evidence = fixture_snapshot()
    raw = {'metadata': snapshot['metadata'], 'roles': {role: [row(7200)] for role in stratz.ROLE_POSITIONS}}
    for name, value in [('snapshot.json', snapshot), ('statistics.json', evidence), ('patch_hours.json', raw)]:
        (tmp_path / name).write_text(json.dumps(value), encoding='utf-8')
    monkeypatch.setattr(patch_meta, 'load_mapping', lambda _: {8: 'juggernaut'})
    assert patch_meta.validate_exports(tmp_path, tmp_path / 'mapping')['hero_observations'] == 500
    snapshot['brackets']['ARCHON']['roles']['carry']['meta'][0]['score'] = 999
    (tmp_path / 'snapshot.json').write_text(json.dumps(snapshot), encoding='utf-8')
    with pytest.raises(ValueError, match='disagree'):
        patch_meta.validate_exports(tmp_path, tmp_path / 'mapping')
