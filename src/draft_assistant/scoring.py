"""Explicit deterministic recommendation formula."""

from .heroes import load_data
from .models import Draft, Recommendation

def recommend(draft: Draft, limit: int = 3) -> list[Recommendation]:
    """Score valid heroes from the data-defined rating, matchups, synergies, and role score."""
    heroes, matchups, synergies = load_data()
    picks = set(draft.enemies + draft.allies)
    results = []
    for hero in heroes.values():
        if draft.role not in hero.roles or hero.id in picks:
            continue
        matchup_details = tuple((enemy, matchups.get(hero.id, {}).get(enemy, 0.0)) for enemy in draft.enemies)
        synergy_details = tuple((ally, synergies.get(hero.id, {}).get(ally, 0.0)) for ally in draft.allies)
        matchup_score = sum(score for _, score in matchup_details)
        synergy_score = sum(score for _, score in synergy_details)
        role_score = hero.role_scores[draft.role]
        score = hero.base_rating + matchup_score + synergy_score + role_score
        results.append(Recommendation(hero, score, matchup_score, synergy_score, role_score, matchup_details, synergy_details))
    return sorted(results, key=lambda item: (-item.score, item.hero.display_name))[:limit]
