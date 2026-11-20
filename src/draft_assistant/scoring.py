"""Explicit deterministic recommendation formula."""

import json
from functools import lru_cache

from .heroes import DATA_DIR, load_data
from .models import Draft, Recommendation, ScoreBreakdown
from .personal_history import analyze_role_pools, load_cache

# Centralized weights: 1.0 preserves hand-authored JSON ranking-point values.
BASE_WEIGHT = ROLE_WEIGHT = MATCHUP_WEIGHT = SYNERGY_WEIGHT = 1.0
CURATED_MATCHUP_WEIGHT = 0.15
CURATED_SYNERGY_WEIGHT = 0.15
CURATED_ADJUSTMENT_CAP = 3.0
ROLE_POSITION_LABELS = {
    "carry": "Position 1",
    "mid": "Position 2",
    "offlane": "Position 3",
    "support": "Position 4",
    "hard_support": "Position 5",
}
PERSONAL_COMFORT = {"MAIN": .6, "COMFORTABLE": .35, "PLAYED": .15}

@lru_cache(maxsize=1)
def _personal_pools():
    return analyze_role_pools(load_cache(DATA_DIR / "generated" / "personal_history.json"))


def matchup_score(candidate: str, enemy: str, matchups: dict[str, dict[str, float]]) -> float:
    """Positive means the candidate is favored against the enemy."""
    return matchups.get(candidate, {}).get(enemy, 0.0)


@lru_cache(maxsize=1)
def _local_data():
    return load_data()


def synergy_score(first: str, second: str, synergies: dict[tuple[str, str], float]) -> float:
    """Synergy pairs are unordered, so lookup is symmetric."""
    return synergies.get(tuple(sorted((first, second))), 0.0)

def _stats(bracket: str = "auto") -> tuple[dict, dict, dict, dict, str | None]:
    if bracket == "auto":
        bracket = _read_snapshot(DATA_DIR / "generated" / "snapshot.json").get("metadata", {}).get("default_bracket", "HERALD_GUARDIAN")
    paths = [DATA_DIR / "generated" / name for name in ("opendota_snapshot.json", "snapshot.json")]
    signature = []
    for path in paths:
        try:
            stat = path.stat(); signature.append((str(path), stat.st_mtime_ns, stat.st_size))
        except OSError: signature.append((str(path), None, None))
    return _load_stats(bracket, tuple(signature))


def _read_snapshot(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError): return {}


@lru_cache(maxsize=2)
def _load_stats(bracket, signature):
    """Load optional local snapshots; generated data never triggers network access."""
    open_path, stratz_path = DATA_DIR / "generated" / "opendota_snapshot.json", DATA_DIR / "generated" / "snapshot.json"
    meta, role_meta, matchups, synergies, snapshot_role = {}, {}, {}, {}, None
    patch_exclusive = False
    if open_path.exists() and bracket != "ARCHON":
        data = _read_snapshot(open_path); meta = {row["hero_id"]: row["score"] for row in data.get("meta", [])}
    if stratz_path.exists():
        data = _read_snapshot(stratz_path)
        patch_exclusive = bool(data.get("metadata", {}).get("filter_method"))
        if "brackets" in data:
            selected=data["brackets"].get(bracket)
            if selected:
                role_meta = {role: {row["hero_id"]: (row["score"], row["matches"], row.get("all_position_matches",0), row.get("position_share",0)) for row in values.get("meta",[])} for role,values in selected["roles"].items()}
                for row in selected["pairs"].get("matchups",[]): matchups.setdefault(row["hero_id"],{})[row["opponent_id"]]=row["score"]
                synergies={tuple(row["heroes"]):row["score"] for row in selected["pairs"].get("synergies",[])}
        elif "roles" in data:
            role_meta = {
                role: {row["hero_id"]: (row["score"], row["matches"], row.get("all_position_matches", 0), row.get("position_share", 0)) for row in values.get("meta", [])}
                for role, values in data["roles"].items()
            }
            pairs = data.get("pairs", {})
            for row in pairs.get("matchups", []): matchups.setdefault(row["hero_id"], {})[row["opponent_id"]] = row["score"]
            synergies = {tuple(row["heroes"]): row["score"] for row in pairs.get("synergies", [])}
        else:
            # Legacy carry-only snapshots remain readable until refreshed.
            snapshot_role = data.get("metadata", {}).get("role")
            role_meta = {snapshot_role: {row["hero_id"]: (row["score"], row["matches"], row.get("all_position_matches", 0), row.get("position_share", 0)) for row in data.get("meta", [])}} if snapshot_role else {}
            for row in data.get("matchups", []): matchups.setdefault(row["hero_id"], {})[row["opponent_id"]] = row["score"]
            synergies = {tuple(sorted(row["heroes"])): row["score"] for row in data.get("synergies", [])}
    return meta, role_meta, matchups, synergies, snapshot_role, patch_exclusive


_stats.cache_clear = _load_stats.cache_clear


def recommend(draft: Draft, limit: int = 3, data: str = "auto", pool_mode: str = "all", bracket: str = "auto") -> list[Recommendation]:
    """Score valid heroes from the data-defined rating, matchups, synergies, and role score."""
    heroes, matchups, synergies = _local_data()
    if data not in {"auto", "manual", "stats", "hybrid"}:
        raise ValueError("data must be manual, stats, or hybrid")
    if pool_mode not in {"all", "prefer", "only"}: raise ValueError("pool_mode must be all, prefer, or only")
    pool_rows={row["hero_id"]:row for row in _personal_pools().get(draft.role,{}).get("heroes",[])} if pool_mode != "all" else {}
    if data in {"auto", "stats", "hybrid"}:
        try: loaded_stats = _stats(bracket)
        except TypeError: loaded_stats = _stats()  # legacy test fixtures
    else: loaded_stats = ({}, {}, {}, {}, None)
    # Keep small test fixtures written before snapshot metadata was introduced
    # usable, while real on-disk snapshots must explicitly match the role.
    patch_exclusive = loaded_stats[5] if len(loaded_stats) > 5 else False
    if len(loaded_stats) == 4:
        meta_stats, role_meta, matchup_stats, synergy_stats = loaded_stats
        snapshot_role = draft.role
    else:
        meta_stats, role_meta, matchup_stats, synergy_stats, snapshot_role = loaded_stats[:5]
    if role_meta and all(isinstance(value, tuple) for value in role_meta.values()):
        # Compatibility with pre-role-indexed in-memory test fixtures.
        role_meta = {snapshot_role or draft.role: role_meta}
    pos_meta = role_meta.get(draft.role, {})
    # Manual input and curated-only scoring are separate concerns. Automatic
    # source selection never mixes 50-point curated bases with provider points.
    automatic = data == "auto"
    if patch_exclusive and data == "hybrid": data = "stats"
    if automatic: data = ("stats" if patch_exclusive else "hybrid") if pos_meta or meta_stats else "manual"
    role_stats = bool(pos_meta) or snapshot_role == draft.role
    position_label = ROLE_POSITION_LABELS[draft.role]
    picks = set(draft.enemies + draft.allies)
    results = []
    for hero in heroes.values():
        if draft.role not in hero.roles or hero.id in picks:
            continue
        if (automatic or (data == "stats" and patch_exclusive)) and data != "manual" and hero.id not in pos_meta and hero.id not in meta_stats:
            # An unknown baseline must not outrank a measured negative score.
            continue
        personal=pool_rows.get(hero.id, {}); tier=personal.get("tier")
        if pool_mode == "only" and not tier: continue
        use_manual = data in {"manual", "hybrid"}
        hero_role_stats = role_stats and hero.id in pos_meta
        position = pos_meta.get(hero.id, (None, 0, 0, 0)) if hero_role_stats else (None, 0, 0, 0)
        if len(position) == 2:
            pos_score, pos_matches = position
            all_matches, share = 0, 1.0
        else:
            pos_score, pos_matches, all_matches, share = position
        # Pair data is not position-filtered.  It is only safe to use it when
        # the snapshot has the selected role's relevance metadata.
        confidence = (
            pos_matches / (pos_matches + 1000) * share
            if hero_role_stats
            else (1.0 if data == "manual" else 0.0)
        )
        def matchup_source(enemy: str) -> str:
            if not hero_role_stats and data in {"stats", "hybrid"}:
                return "unavailable-role"
            if enemy in matchup_stats.get(hero.id, {}):
                return "stratz"
            if use_manual and enemy in matchups.get(hero.id, {}):
                return "manual"
            return "unavailable"
        def synergy_source(ally: str) -> str:
            if not hero_role_stats and data in {"stats", "hybrid"}:
                return "unavailable-role"
            if tuple(sorted((hero.id, ally))) in synergy_stats:
                return "stratz"
            if use_manual and tuple(sorted((hero.id, ally))) in synergies:
                return "manual"
            return "unavailable"
        matchup_sources = tuple((enemy, matchup_source(enemy)) for enemy in draft.enemies)
        synergy_sources = tuple((ally, synergy_source(ally)) for ally in draft.allies)
        matchups_for_hero = tuple(
            (enemy, matchup_score(hero.id, enemy, matchup_stats if source == "stratz" else (matchups if source == "manual" else {})) * confidence * MATCHUP_WEIGHT)
            for enemy, source in matchup_sources
        )
        synergies_for_hero = tuple(
            (ally, synergy_score(hero.id, ally, synergy_stats if source == "stratz" else (synergies if source == "manual" else {})) * confidence * SYNERGY_WEIGHT)
            for ally, source in synergy_sources
        )
        if data == "hybrid":
            curated = [matchup_score(hero.id, enemy, matchups) * CURATED_MATCHUP_WEIGHT for enemy in draft.enemies] + [synergy_score(hero.id, ally, synergies) * CURATED_SYNERGY_WEIGHT for ally in draft.allies]
            total = max(-CURATED_ADJUSTMENT_CAP, min(CURATED_ADJUSTMENT_CAP, sum(curated)))
            if curated:
                matchups_for_hero = (*matchups_for_hero, ("curated adjustment", total))
                matchup_sources = (*matchup_sources, ("curated adjustment", "manual-curated"))
        comfort=PERSONAL_COMFORT.get(tier,0.0) if pool_mode == "prefer" else 0.0
        breakdown = ScoreBreakdown((pos_score if pos_score is not None else meta_stats.get(hero.id, hero.base_rating if use_manual else 0)) * BASE_WEIGHT, 0.0, matchups_for_hero, synergies_for_hero, f"stratz-{draft.role}" if pos_score is not None else ("opendota-fallback" if hero.id in meta_stats else ("hero-data" if use_manual else "missing")), "eligibility", matchup_sources, synergy_sources, pos_matches, confidence, position_label, comfort, tier, personal.get("games",0))
        results.append(Recommendation(hero, breakdown))
    return sorted(results, key=lambda item: (-item.score, item.hero.display_name))[:limit]


def coverage_warning(recommendations):
    """Unknown pairs are omitted evidence, never measured neutral matchups."""
    sources = [source for item in recommendations for _, source in
               item.breakdown.matchup_sources + item.breakdown.synergy_sources]
    missing = sum(source.startswith("unavailable") for source in sources)
    if sources and missing == len(sources):
        return "Draft-aware scoring unavailable for these picks: matchup/synergy data missing or role weight unavailable. Scores reflect base/comfort only."
    if missing:
        return f"Incomplete draft evidence: {missing}/{len(sources)} pair contributions unavailable; unknown does not mean neutral."
    return ""

def recommend_worlds(draft: Draft, limit: int = 5, data: str = "auto", bracket: str = "auto") -> tuple[list[Recommendation], list[Recommendation]]:
    """Two independent candidate sets sharing exactly the same draft score."""
    meta = recommend(draft, 127, data, "all", bracket)
    pool_ids = {row["hero_id"] for row in _personal_pools().get(draft.role, {}).get("heroes", []) if row.get("tier")}
    pool = [item for item in meta if item.hero.id in pool_ids]
    return meta[:limit], pool[:limit]
