"""Explicit deterministic recommendation formula."""

import json

from .heroes import DATA_DIR, load_data
from .models import Draft, Recommendation, ScoreBreakdown

# Centralized weights: 1.0 preserves hand-authored JSON ranking-point values.
BASE_WEIGHT = ROLE_WEIGHT = MATCHUP_WEIGHT = SYNERGY_WEIGHT = 1.0


def matchup_score(candidate: str, enemy: str, matchups: dict[str, dict[str, float]]) -> float:
    """Positive means the candidate is favored against the enemy."""
    return matchups.get(candidate, {}).get(enemy, 0.0)


def synergy_score(first: str, second: str, synergies: dict[tuple[str, str], float]) -> float:
    """Synergy pairs are unordered, so lookup is symmetric."""
    return synergies.get(tuple(sorted((first, second))), 0.0)

def _stats() -> tuple[dict[str, float], dict[str, dict[str, float]], dict[tuple[str, str], float]]:
    """Load optional local snapshots; generated data never triggers network access."""
    open_path, stratz_path = DATA_DIR / "generated" / "opendota_snapshot.json", DATA_DIR / "generated" / "snapshot.json"
    meta, matchups, synergies = {}, {}, {}
    if open_path.exists():
        data = json.loads(open_path.read_text(encoding="utf-8")); meta = {row["hero_id"]: row["score"] for row in data.get("meta", [])}
    if stratz_path.exists():
        data = json.loads(stratz_path.read_text(encoding="utf-8"))
        for row in data.get("matchups", []): matchups.setdefault(row["hero_id"], {})[row["opponent_id"]] = row["score"]
        synergies = {tuple(row["heroes"]): row["score"] for row in data.get("synergies", [])}
    return meta, matchups, synergies


def recommend(draft: Draft, limit: int = 3, data: str = "manual") -> list[Recommendation]:
    """Score valid heroes from the data-defined rating, matchups, synergies, and role score."""
    heroes, matchups, synergies = load_data()
    if data not in {"manual", "stats"}:
        raise ValueError("data must be manual or stats")
    meta_stats, matchup_stats, synergy_stats = _stats() if data == "stats" else ({}, {}, {})
    picks = set(draft.enemies + draft.allies)
    results = []
    for hero in heroes.values():
        if draft.role not in hero.roles or hero.id in picks:
            continue
        matchups_for_hero = tuple((enemy, matchup_score(hero.id, enemy, matchup_stats if enemy in matchup_stats.get(hero.id, {}) else matchups) * MATCHUP_WEIGHT) for enemy in draft.enemies)
        synergies_for_hero = tuple((ally, synergy_score(hero.id, ally, synergy_stats if tuple(sorted((hero.id, ally))) in synergy_stats else synergies) * SYNERGY_WEIGHT) for ally in draft.allies)
        breakdown = ScoreBreakdown(meta_stats.get(hero.id, hero.base_rating) * BASE_WEIGHT, hero.role_scores[draft.role] * ROLE_WEIGHT, matchups_for_hero, synergies_for_hero)
        results.append(Recommendation(hero, breakdown))
    return sorted(results, key=lambda item: (-item.score, item.hero.display_name))[:limit]
