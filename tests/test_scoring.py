import pytest

from draft_assistant.cli import format_explanation
from draft_assistant.heroes import load_data, parse_draft
from draft_assistant.scoring import recommend
import draft_assistant.scoring as scoring
from draft_assistant.models import Draft, Hero


DRAFT = "sf bara ogre silencer | underlord jakiro wd | carry"


def test_parses_draft_input():
    draft = parse_draft(DRAFT)
    assert draft.enemies == ("shadow_fiend", "spirit_breaker", "ogre_magi", "silencer")
    assert draft.allies == ("underlord", "jakiro", "witch_doctor")
    assert draft.role == "carry"


def test_parses_extra_whitespace_multi_word_heroes_and_empty_team_sections():
    draft = parse_draft("  shadow fiend   bara |   | carry ")
    assert draft.enemies == ("shadow_fiend", "spirit_breaker")
    assert draft.allies == ()


def test_parses_commas_and_case_insensitively():
    draft = parse_draft("SF,BARA,OGRE | JAKIRO,WD | CARRY")
    assert draft.enemies == ("shadow_fiend", "spirit_breaker", "ogre_magi")


@pytest.mark.parametrize("value", ["sf sf | underlord | carry", "sf | sf | carry"])
def test_duplicate_heroes_are_rejected(value):
    with pytest.raises(ValueError, match="cannot appear more than once"):
        parse_draft(value)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("sf | underlord | jungle", "Unknown role"),
        ("sf | underlord", "Use: enemies | allies | role"),
    ],
)
def test_invalid_role_and_malformed_draft_are_rejected(value, message):
    with pytest.raises(ValueError, match=message):
        parse_draft(value)


def test_only_requested_role_is_recommended():
    choices = recommend(parse_draft(DRAFT))
    assert all("carry" in item.hero.roles for item in choices)


def test_existing_draft_heroes_are_not_recommended():
    choices = recommend(parse_draft("spectre sf | underlord | carry"))
    assert {item.hero.id for item in choices}.isdisjoint({"spectre", "shadow_fiend", "underlord"})


def test_scoring_is_deterministic():
    assert recommend(parse_draft(DRAFT)) == recommend(parse_draft(DRAFT))


def test_recommendations_are_ordered():
    choices = recommend(parse_draft(DRAFT))
    assert [item.hero.id for item in choices] == ["lifestealer", "juggernaut", "wraith_king"]
    assert [item.score for item in choices] == sorted((item.score for item in choices), reverse=True)


def test_explanation_contains_breakdown():
    heroes = load_data()[0]
    explanation = format_explanation(recommend(parse_draft(DRAFT))[0], heroes)
    assert "base: +62.0" in explanation
    assert "role: +0.0 [eligibility]" in explanation
    assert "vs Spirit Breaker: +6.0" in explanation
    assert "with Underlord: +5.0" in explanation


def test_explanation_describes_negative_matchup_value():
    heroes = load_data()[0]
    anti_mage = next(item for item in recommend(parse_draft(DRAFT), limit=20) if item.hero.id == "anti_mage")
    assert "vs Silencer: -5.0" in format_explanation(anti_mage, heroes)


def test_breakdown_total_is_exact_scoring_formula():
    item = recommend(parse_draft(DRAFT))[0]
    breakdown = item.breakdown
    assert breakdown.total == breakdown.base + breakdown.role + sum(value for _, value in breakdown.matchup_contributions) + sum(value for _, value in breakdown.synergy_contributions)
    assert item.score == breakdown.total

def test_personal_pool_modes_are_role_specific_and_bounded(monkeypatch):
    heroes={"axe":Hero("axe","Axe",("carry",),1,{}),"bane":Hero("bane","Bane",("carry",),1,{})}
    scoring._local_data.cache_clear(); monkeypatch.setattr(scoring,"load_data",lambda:(heroes,{},{}))
    monkeypatch.setattr(scoring,"_personal_pools",lambda:{"carry":{"heroes":[{"hero_id":"axe","tier":"MAIN","games":4}]},"support":{"heroes":[{"hero_id":"bane","tier":"MAIN","games":9}]}})
    draft=Draft((),(),"carry")
    all_rows=scoring.recommend(draft,2,"manual","all"); preferred=scoring.recommend(draft,2,"manual","prefer"); only=scoring.recommend(draft,2,"manual","only")
    assert all_rows[0].score == 1
    axe=next(row for row in preferred if row.hero.id=="axe")
    assert axe.breakdown.personal_comfort == .6 and axe.score == 1.6
    assert [row.hero.id for row in only] == ["axe"]

def test_two_worlds_share_scores_but_not_candidate_sets(monkeypatch):
    heroes={"axe":Hero("axe","Axe",("carry",),1,{}),"bane":Hero("bane","Bane",("carry",),2,{})}
    scoring._local_data.cache_clear(); monkeypatch.setattr(scoring,"load_data",lambda:(heroes,{},{}))
    monkeypatch.setattr(scoring,"_personal_pools",lambda:{"carry":{"heroes":[{"hero_id":"axe","tier":"MAIN","games":4}]}})
    meta,pool=scoring.recommend_worlds(Draft((),(),"carry"),2,"manual")
    assert [x.hero.id for x in meta] == ["bane","axe"]
    assert [x.hero.id for x in pool] == ["axe"]
    assert pool[0].score == next(x.score for x in meta if x.hero.id=="axe")


def test_stats_components_replace_manual_values_without_double_counting(monkeypatch):
    heroes = {"axe": Hero("axe", "Axe", ("carry",), 50, {"carry": 10}), "bane": Hero("bane", "Bane", ("support",), 50, {"support": 10}), "chen": Hero("chen", "Chen", ("support",), 50, {"support": 10})}
    scoring._local_data.cache_clear()
    monkeypatch.setattr(scoring, "load_data", lambda: (heroes, {"axe": {"bane": 9}}, {("axe", "chen"): 7}))
    monkeypatch.setattr(scoring, "_stats", lambda: ({"axe": 2}, {"axe": (2, 100000)}, {"axe": {"bane": 3}}, {("axe", "chen"): 4}))
    result = scoring.recommend(Draft(("bane",), ("chen",), "carry"), data="stats")[0]
    assert result.breakdown.base == 2
    assert (result.breakdown.matchups, result.breakdown.synergies) == pytest.approx((3 * 100000 / 101000, 4 * 100000 / 101000))


@pytest.mark.parametrize(("role", "label"), [
    ("carry", "Position 1"), ("mid", "Position 2"),
    ("offlane", "Position 3"), ("support", "Position 4"),
    ("hard_support", "Position 5"),
])
def test_stats_snapshot_role_mapping_and_breakdown_label(monkeypatch, role, label):
    hero = Hero("candidate", "Candidate", (role,), 50, {role: 10})
    scoring._local_data.cache_clear()
    monkeypatch.setattr(scoring, "load_data", lambda: ({"candidate": hero}, {}, {}))
    monkeypatch.setattr(scoring, "_stats", lambda: ({}, {"candidate": (2.0, 500, 1000, .5)}, {}, {}, role))
    result = scoring.recommend(Draft((), (), role), data="stats")[0]
    assert result.breakdown.base == 2.0
    assert result.breakdown.base_source == f"stratz-{role}"
    assert result.breakdown.position_label == label
    assert result.breakdown.pos1_matches == 500


def test_wrong_role_snapshot_does_not_supply_position_one_meta_or_pair_evidence(monkeypatch):
    heroes = {
        "candidate": Hero("candidate", "Candidate", ("offlane",), 50, {"offlane": 10}),
        "enemy": Hero("enemy", "Enemy", ("carry",), 50, {"carry": 10}),
    }
    scoring._local_data.cache_clear()
    monkeypatch.setattr(scoring, "load_data", lambda: (heroes, {"candidate": {"enemy": 8}}, {}))
    monkeypatch.setattr(scoring, "_stats", lambda: ({"candidate": .2}, {"candidate": (9.0, 900, 1000, .9)}, {"candidate": {"enemy": 6}}, {}, "carry"))
    result = scoring.recommend(Draft(("enemy",), (), "offlane"), data="hybrid")[0]
    assert result.breakdown.base == .2
    assert result.breakdown.base_source == "opendota-fallback"
    assert result.breakdown.position_label == "Position 3"
    assert result.breakdown.pos1_matches == 0
    assert result.breakdown.position_confidence == 0
    assert result.breakdown.matchup_contributions[0][1] == 0
    assert result.breakdown.matchup_sources[0] == ("enemy", "unavailable-role")


def test_unavailable_matchup_is_explicit_in_explanation(monkeypatch):
    heroes = {
        "candidate": Hero("candidate", "Candidate", ("offlane",), 50, {"offlane": 10}),
        "enemy": Hero("enemy", "Enemy", ("carry",), 50, {"carry": 10}),
    }
    scoring._local_data.cache_clear()
    monkeypatch.setattr(scoring, "load_data", lambda: (heroes, {}, {}))
    monkeypatch.setattr(scoring, "_stats", lambda: ({"candidate": .2}, {}, {}, {}, "carry"))
    result = scoring.recommend(Draft(("enemy",), (), "offlane"), data="stats")[0]
    explanation = format_explanation(result, heroes)
    assert "Position 3 sample" in explanation
    assert "Position 1 sample" not in explanation
    assert "vs Enemy: data unavailable for selected role" in explanation


def test_available_matchup_evidence_is_identified_separately_from_meta(monkeypatch):
    heroes = {
        "candidate": Hero("candidate", "Candidate", ("offlane",), 50, {"offlane": 10}),
        "enemy": Hero("enemy", "Enemy", ("carry",), 50, {"carry": 10}),
    }
    scoring._local_data.cache_clear()
    monkeypatch.setattr(scoring, "load_data", lambda: (heroes, {}, {}))
    monkeypatch.setattr(scoring, "_stats", lambda: ({"candidate": .2}, {"candidate": (1.0, 1000, 1000, 1.0)}, {"candidate": {"enemy": 3.0}}, {}, "offlane"))
    result = scoring.recommend(Draft(("enemy",), (), "offlane"), data="stats")[0]
    explanation = format_explanation(result, heroes)
    assert result.breakdown.base_source == "stratz-offlane"
    assert result.breakdown.matchup_sources == (("enemy", "stratz"),)
    assert "vs Enemy: +1.5 [stratz]" in explanation


@pytest.mark.parametrize(("role", "expected_score"), [
    ("carry", 1.0), ("mid", 2.0), ("offlane", 3.0),
    ("support", 4.0), ("hard_support", 5.0),
])
def test_role_indexed_snapshot_selects_only_requested_role(monkeypatch, role, expected_score):
    hero = Hero("candidate", "Candidate", (role,), 50, {role: 10})
    role_meta = {
        name: {"candidate": (score, 2000, 4000, .5)}
        for score, name in enumerate(("carry", "mid", "offlane", "support", "hard_support"), 1)
    }
    scoring._local_data.cache_clear()
    monkeypatch.setattr(scoring, "load_data", lambda: ({"candidate": hero}, {}, {}))
    monkeypatch.setattr(scoring, "_stats", lambda: ({}, role_meta, {}, {}, None))
    result = scoring.recommend(Draft((), (), role), data="stats")[0]
    assert result.breakdown.base == expected_score
    assert result.breakdown.base_source == f"stratz-{role}"
    assert result.breakdown.position_confidence == pytest.approx(2 / 3 * .5)
