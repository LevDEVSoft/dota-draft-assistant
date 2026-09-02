"""Provider-neutral imported statistical records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HeroMetaStats:
    hero_id: str
    role: str | None
    matches: int
    wins: int
    pick_rate: float | None = None

    @property
    def win_rate(self) -> float:
        return self.wins / self.matches if self.matches else 0.0


@dataclass(frozen=True)
class HeroMatchupStats:
    hero_id: str
    opponent_id: str
    matches: int
    wins: int

    @property
    def win_rate(self) -> float:
        return self.wins / self.matches if self.matches else 0.0


@dataclass(frozen=True)
class HeroSynergyStats:
    hero_id: str
    ally_id: str
    matches: int
    wins: int

    @property
    def win_rate(self) -> float:
        return self.wins / self.matches if self.matches else 0.0
