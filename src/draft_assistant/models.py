"""Small domain models used by the draft assistant."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Hero:
    id: str
    display_name: str
    roles: tuple[str, ...]
    base_rating: float
    role_scores: dict[str, float]


@dataclass(frozen=True)
class Draft:
    enemies: tuple[str, ...]
    allies: tuple[str, ...]
    role: str


@dataclass(frozen=True)
class Recommendation:
    hero: Hero
    score: float
    matchup_score: float
    synergy_score: float
    role_score: float
    matchup_details: tuple[tuple[str, float], ...]
    synergy_details: tuple[tuple[str, float], ...]
