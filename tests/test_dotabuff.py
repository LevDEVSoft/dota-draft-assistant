from pathlib import Path
from urllib.error import HTTPError
from io import BytesIO

import pytest

from draft_assistant.data_sources import dotabuff
from draft_assistant.data_sources.normalization import MATCHUP_MAX, dotabuff_matchup_rating
from draft_assistant.heroes import DATA_DIR, load_data
from draft_assistant.models import Hero


FIXTURE = Path(__file__).parent / "fixtures" / "dotabuff_matchups.html"


def test_all_heroes_have_unique_dotabuff_slugs():
    mapping = dotabuff.validate_slugs(set(load_data()[0]))
    assert len(mapping) == 127 == len(set(mapping.values()))
    assert mapping["shadow_fiend"] == "shadow-fiend"


def test_parser_handles_full_table_percentages_names_and_match_counts():
    rows = dotabuff.parse_matchups(FIXTURE.read_text(), "lifestealer", load_data()[0])
    assert [(r.opponent_id, r.matches) for r in rows] == [("underlord", 157240), ("spectre", 186360)]
    assert [r.advantage for r in rows] == pytest.approx([-.0361, .0283])
    assert all(0 <= row.win_rate <= 1 for row in rows)


@pytest.mark.parametrize("html, message", [("<table></table>", "was not found"), ("<table><tr><th>Hero</th><th>Matches Played</th><th>Hero Win Rate</th><th>Disadvantage</th></tr><tr><td>Unknown</td><td>1</td><td>50%</td><td>1%</td></tr></table>", "Unknown DOTABUFF hero"), ("<table><tr><th>Hero</th><th>Matches Played</th><th>Hero Win Rate</th><th>Disadvantage</th></tr><tr><td>Axe</td><td>bad</td><td>50%</td><td>1%</td></tr></table>", "Invalid match count")])
def test_parser_rejects_changed_unknown_and_malformed_pages(html, message):
    with pytest.raises(dotabuff.DotabuffParseError, match=message):
        dotabuff.parse_matchups(html, "lifestealer", load_data()[0])


@pytest.mark.parametrize("window", ["week", "month", "year"])
def test_allowed_windows(window):
    assert f"date={window}" in dotabuff.counter_url("lifestealer", window)


def test_role_filtering_snapshot_pacing_and_determinism(monkeypatch):
    heroes = {key: load_data()[0][key] for key in ("lifestealer", "axe", "spectre", "underlord")}
    heroes["spectre"] = Hero("spectre", "Spectre", ("support",), 50, {})
    assert dotabuff.role_candidates("carry", heroes) == ("lifestealer",)
    monkeypatch.setattr(dotabuff, "fetch_html", lambda *_: FIXTURE.read_text())
    output = DATA_DIR / "generated" / "dotabuff-test.json"
    snapshot = dotabuff.sync("carry", "month", output, heroes, delay=0, sleeper=lambda _: pytest.fail("no sleep"))
    assert output.exists() and len(snapshot["matchups"]) == 2
    output.unlink()


def test_confidence_weighted_dotabuff_scores_are_bounded():
    assert abs(dotabuff_matchup_rating(.04, 5)) < abs(dotabuff_matchup_rating(.04, 100000))
    assert dotabuff_matchup_rating(.5, 100000) == MATCHUP_MAX


@pytest.mark.parametrize("code", [403, 429])
def test_public_blocks_stop_cleanly(monkeypatch, code):
    monkeypatch.setattr(dotabuff, "urlopen", lambda *_, **__: (_ for _ in ()).throw(HTTPError("url", code, "blocked", None, BytesIO())))
    with pytest.raises(dotabuff.DotabuffBlockedError, match=str(code)):
        dotabuff.fetch_html("lifestealer")
