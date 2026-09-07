"""Optional, raw statistical evidence for recommendation explanations.

This module deliberately does not turn a win rate into a recommendation score.
Mechanics remain the deterministic decision layer; these records make the
underlying sample and its uncertainty available to the UI and a future,
explicitly weighted evidence layer.

``data/generated/statistics.json`` is an optional provider export with
``hero_stats``, ``matchup_stats``, and ``item_stats`` lists.  Every row uses
hero/role/bracket identifiers plus the fields named by its dataclass below.
Missing files or incomplete rows are simply unavailable evidence.
"""
from dataclasses import dataclass
import json
from functools import lru_cache

from .heroes import DATA_DIR

CONFIDENCE_MATCHES = 1_000


def sample_confidence(matches: int) -> float:
    """Bounded sample-size confidence; never hides the raw result."""
    return max(0, matches) / (max(0, matches) + CONFIDENCE_MATCHES)


def confidence_label(matches: int) -> str:
    value = sample_confidence(matches)
    return "high" if value >= .8 else "medium" if value >= .5 else "low"


@dataclass(frozen=True)
class HeroStatistics:
    hero_id: str
    role: str
    bracket: str
    matches: int
    wins: int
    pick_rate: float | None = None

    @property
    def win_rate(self) -> float: return self.wins / self.matches if self.matches else 0.0


@dataclass(frozen=True)
class MatchupStatistics:
    hero_id: str
    opponent_id: str
    role: str
    bracket: str
    matches: int
    wins: int
    baseline_win_rate: float

    @property
    def win_rate(self) -> float: return self.wins / self.matches if self.matches else 0.0
    @property
    def delta(self) -> float: return self.win_rate - self.baseline_win_rate


@dataclass(frozen=True)
class ItemStatistics:
    hero_id: str
    role: str
    bracket: str
    item_id: str
    purchases: int
    wins: int
    purchase_rate: float | None
    baseline_win_rate: float
    timing_bucket: str | None = None

    @property
    def win_rate(self) -> float: return self.wins / self.purchases if self.purchases else 0.0
    @property
    def delta(self) -> float: return self.win_rate - self.baseline_win_rate
    @property
    def confidence(self) -> float: return sample_confidence(self.purchases)


def _record(row: dict, fields: tuple[str, ...]) -> bool:
    return all(field in row and row[field] is not None for field in fields)


@lru_cache(maxsize=1)
def _raw() -> dict:
    path = DATA_DIR / "generated" / "statistics.json"
    if not path.exists(): return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _select(rows, predicate):
    return next((row for row in rows if predicate(row)), None)


def hero_statistics(hero_id: str, role: str, bracket: str = "HERALD_GUARDIAN") -> HeroStatistics | None:
    row = _select(_raw().get("hero_stats", ()), lambda r: r.get("hero") == hero_id and r.get("role") == role and r.get("bracket") == bracket)
    if not row or not _record(row, ("matches", "wins")): return None
    return HeroStatistics(hero_id, role, bracket, int(row["matches"]), int(row["wins"]), row.get("pick_rate"))


def matchup_statistics(hero_id: str, opponent_id: str, role: str, bracket: str = "HERALD_GUARDIAN") -> MatchupStatistics | None:
    row = _select(_raw().get("matchup_stats", ()), lambda r: r.get("hero") == hero_id and r.get("opponent") == opponent_id and r.get("role") == role and r.get("bracket") == bracket)
    baseline = hero_statistics(hero_id, role, bracket)
    if not row or not baseline or not _record(row, ("matches", "wins")): return None
    return MatchupStatistics(hero_id, opponent_id, role, bracket, int(row["matches"]), int(row["wins"]), baseline.win_rate)


def item_statistics(hero_id: str, role: str, item_id: str, bracket: str = "HERALD_GUARDIAN") -> ItemStatistics | None:
    row = _select(_raw().get("item_stats", ()), lambda r: r.get("hero") == hero_id and r.get("role") == role and r.get("bracket") == bracket and r.get("item") == item_id)
    baseline = hero_statistics(hero_id, role, bracket)
    if not row or not baseline or not _record(row, ("purchase_count", "wins")): return None
    return ItemStatistics(hero_id, role, bracket, item_id, int(row["purchase_count"]), int(row["wins"]), row.get("purchase_rate"), baseline.win_rate, row.get("timing_bucket"))
