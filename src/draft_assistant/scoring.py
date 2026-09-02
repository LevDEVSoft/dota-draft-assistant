"""Explicit deterministic recommendation formula."""

from .heroes import load_data
from .models import Draft, Recommendation, ScoreBreakdown

# Centralized weights: 1.0 preserves hand-authored JSON ranking-point values.
BASE_WEIGHT = ROLE_WEIGHT = MATCHUP_WEIGHT = SYNERGY_WEIGHT = 1.0


def matchup_score(candidate: str, enemy: str, matchups: dict[str, dict[str, float]]) -> float:
    """Positive means the candidate is favored against the enemy."""
    return matchups.get(candidate, {}).get(enemy, 0.0)


def synergy_score(first: str, second: str, synergies: dict[tuple[str, str], float]) -> float:
    """Synergy pairs are unordered, so lookup is symmetric."""
    return synergies.get(tuple(sorted((first, second))), 0.0)

def recommend(draft: Draft, limit: int = 3) -> list[Recommendation]:
    """Score valid heroes from the data-defined rating, matchups, synergies, and role score."""
    heroes, matchups, synergies = load_data()
    picks = set(draft.enemies + draft.allies)
    results = []
    for hero in heroes.values():
        if draft.role not in hero.roles or hero.id in picks:
            continue
        matchups_for_hero = tuple((enemy, matchup_score(hero.id, enemy, matchups) * MATCHUP_WEIGHT) for enemy in draft.enemies)
        synergies_for_hero = tuple((ally, synergy_score(hero.id, ally, synergies) * SYNERGY_WEIGHT) for ally in draft.allies)
        breakdown = ScoreBreakdown(hero.base_rating * BASE_WEIGHT, hero.role_scores[draft.role] * ROLE_WEIGHT, matchups_for_hero, synergies_for_hero)
        results.append(Recommendation(hero, breakdown))
    return sorted(results, key=lambda item: (-item.score, item.hero.display_name))[:limit]
