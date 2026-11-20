"""Read existing provider exports honestly, independently of ranking points."""
import json
from datetime import datetime, UTC
from functools import lru_cache

from draft_assistant.heroes import DATA_DIR


def snapshot(filename):
    path = DATA_DIR / "generated" / filename
    try:
        stat = path.stat(); signature = (stat.st_mtime_ns, stat.st_size)
    except OSError: signature = None
    return _snapshot(str(path), signature)


@lru_cache(maxsize=8)
def _snapshot(filename, signature):
    from pathlib import Path
    try:
        data = json.loads(Path(filename).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError): return {}


snapshot.cache_clear = _snapshot.cache_clear


def freshness(data, now=None):
    meta = data.get("metadata", {})
    if not isinstance(meta, dict): meta = {}
    timestamp = meta.get("generated_at")
    try:
        age = ((now or datetime.now(UTC)) - datetime.fromisoformat(timestamp.replace("Z", "+00:00"))).days
        date = timestamp[:10]
        timing = f"{date} · {max(age, 0)} days old" + (" · OUTDATED (>7 days)" if age > 7 else "")
    except (TypeError, ValueError, AttributeError): timing = "Snapshot date unknown"
    return timing + f" · Patch: {meta.get('patch') or 'unknown'}"


def hero_evidence(hero_id, role):
    """Never reverse-engineer a win rate from a normalized score."""
    stratz = snapshot("snapshot.json")
    bracket = stratz.get("brackets", {}).get("ARCHON", stratz.get("brackets", {}).get("HERALD_GUARDIAN", stratz))
    roles = bracket.get("roles", {})
    rows = roles.get(role, {}).get("meta", []) if isinstance(roles, dict) else []
    lines = []
    row = next((r for r in rows if r.get("hero_id") == hero_id), None)
    if row:
        matches = row.get("matches", 0)
        lines.append(f"STRATZ · Herald / Guardian · {role.replace('_', ' ')}: {matches:,} matches" + (" · LOW SAMPLE (<1,000)" if matches < 1000 else ""))
        lines.append(freshness(stratz))
        if stratz.get("metadata", {}).get("filter_method"):
            lines.append(stratz["metadata"]["filter_method"])
            lines.append("Patch-specific matchups, synergies and item builds unavailable.")
        wins = row.get("wins")
        if type(wins) is int and matches > 0 and 0 <= wins <= matches: lines.append(f"Role win rate: {wins / matches:.1%}")
        else: lines.append("Role win rate unavailable in this export; ranking score is not a win rate.")
        if isinstance(row.get("pick_rate"), (int, float)):
            lines.append(f"Position pick share: {row['pick_rate']:.1%} of mapped hero observations.")
    else: lines.append("STRATZ: no cached sample for this hero and role.")
    opendota = snapshot("opendota_snapshot.json")
    row = next((r for r in opendota.get("meta", []) if r.get("hero_id") == hero_id), None)
    if row and row.get("matches", 0) > 0 and isinstance(row.get("win_rate"), (int, float)) and 0 <= row["win_rate"] <= 1:
        matches = row["matches"]
        lines.append(f"OpenDota (historical, excluded from Archon scoring) · Herald / Guardian · all roles: {row['win_rate']:.1%} WR · {matches:,} matches" + (" · LOW SAMPLE (<1,000)" if matches < 1000 else ""))
        lines.append(freshness(opendota))
    else: lines.append("OpenDota: no cached win-rate sample.")
    return lines


def pair_sample(hero_id, other_id, synergy=False):
    data = snapshot("snapshot.json")
    bracket = data.get("brackets", {}).get("ARCHON", data.get("brackets", {}).get("HERALD_GUARDIAN", data))
    pairs = bracket.get("pairs", bracket)
    if synergy:
        row = next((r for r in pairs.get("synergies", []) if sorted(r.get("heroes", [])) == sorted((hero_id, other_id))), None)
    else:
        row = next((r for r in pairs.get("matchups", []) if r.get("hero_id") == hero_id and r.get("opponent_id") == other_id), None)
    return row.get("matches") if row else None


def cache_summary():
    parts = []
    for label, filename in (("STRATZ", "snapshot.json"), ("OpenDota", "opendota_snapshot.json")):
        data = snapshot(filename)
        parts.append(f"{label}: {freshness(data)}" if data else f"{label}: cached statistics missing or unreadable")
        metadata = data.get("metadata", {})
        version = metadata.get("normalization_version", 1) if isinstance(metadata, dict) else 1
        if label == "STRATZ" and data and (not isinstance(version, (int, float)) or version < 2):
            parts.append("STRATZ legacy normalization: original pair baselines cannot be verified; refresh recommended.")
    patch = snapshot("snapshot.json").get("metadata", {})
    if patch.get("filter_method"):
        parts.append(f"ARCHON ranked · {patch['filter_method']} · {patch['hero_observations']:,} hero observations; unique matches unavailable")
        parts.append("Time-filtered proxy; game-version ID unverified. Pair/item statistics unavailable; item advice is curated.")
    return "\n".join(parts)
