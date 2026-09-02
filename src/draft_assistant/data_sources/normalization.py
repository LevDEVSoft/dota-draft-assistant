"""Bounded, deterministic conversion from rates into ranking points."""

META_MAX = 5.0
MATCHUP_MAX = 8.0
SYNERGY_MAX = 6.0
CONFIDENCE_MATCHES = 100


def confidence(matches: int) -> float:
    """Bayesian-style shrinkage: n / (n + 100), toward neutral at small n."""
    if matches < 0:
        raise ValueError("matches must be non-negative")
    return matches / (matches + CONFIDENCE_MATCHES)


def _bounded(delta: float, matches: int, maximum: float) -> float:
    if not -1 <= delta <= 1:
        raise ValueError("win-rate delta must be between -1 and 1")
    return max(-maximum, min(maximum, delta / 0.5 * maximum * confidence(matches)))


def meta_rating(win_rate: float, matches: int) -> float:
    return _bounded(win_rate - 0.5, matches, META_MAX)


def matchup_rating(win_rate: float, baseline_win_rate: float, matches: int) -> float:
    return _bounded(win_rate - baseline_win_rate, matches, MATCHUP_MAX)


def dotabuff_matchup_rating(advantage: float, matches: int) -> float:
    """Bounded public-page advantage in percentage points, confidence weighted."""
    if not -1 <= advantage <= 1:
        raise ValueError("advantage must be between -1 and 1")
    return max(-MATCHUP_MAX, min(MATCHUP_MAX, advantage * 100 * confidence(matches)))


def synergy_rating(pair_win_rate: float, expected_win_rate: float, matches: int) -> float:
    return _bounded(pair_win_rate - expected_win_rate, matches, SYNERGY_MAX)
