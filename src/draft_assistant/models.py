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
class ScoreBreakdown:
    base: float
    role: float
    matchup_contributions: tuple[tuple[str, float], ...]
    synergy_contributions: tuple[tuple[str, float], ...]
    base_source: str = "hero-data"
    role_source: str = "hero-data"
    matchup_sources: tuple[tuple[str, str], ...] = ()
    synergy_sources: tuple[tuple[str, str], ...] = ()
    pos1_matches: int = 0
    position_confidence: float = 0.0

    @property
    def matchups(self) -> float:
        return sum(score for _, score in self.matchup_contributions)

    @property
    def synergies(self) -> float:
        return sum(score for _, score in self.synergy_contributions)

    @property
    def total(self) -> float:
        return self.base + self.role + self.matchups + self.synergies


@dataclass(frozen=True)
class Recommendation:
    hero: Hero
    breakdown: ScoreBreakdown

    @property
    def score(self) -> float:
        return self.breakdown.total
