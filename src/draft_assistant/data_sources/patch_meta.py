"""Patch-aware exact-Archon ranked statistics, using complete post-release hours.

Version and weekly aggregates can lag behind a release. Never infer a version
ID, or treat in-game minTime/maxTime as calendar filters.
"""
import json
import math
import re
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen

from . import stratz
from .mapping import load_mapping, validate_mapping
from .normalization import meta_rating

NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=570&count=100&maxlength=0&feeds=steam_community_announcements"
QUERY = """query PatchHours($ids:[Short!],$pos:[MatchPlayerPositionType!],$take:Int!,$skip:Int!){
 heroStats { winHour(heroIds:$ids,bracketIds:[ARCHON],positionIds:$pos,
 gameModeIds:[ALL_PICK_RANKED],take:$take,skip:$skip){hour heroId matchCount winCount} }
}"""


def detect_patch():
    request = Request(NEWS_URL, headers={"User-Agent": "dota-draft-assistant/0.1"})
    with urlopen(request, timeout=30) as response:
        rows = json.load(response)["appnews"]["newsitems"]
    patches = []
    for row in rows:
        if row.get("feedname") != "steam_community_announcements":
            continue
        match = re.search(r"\b(7\.\d{2}[a-z]?)\b.*\b(?:Gameplay|Patch|Update)\b", row["title"], re.I)
        if match:
            patches.append((int(row["date"]), match.group(1).lower(), row["url"]))
    if not patches:
        raise ValueError("No official Valve patch announcement found; old data preserved")
    released, patch, url = max(patches)
    return {"patch": patch, "release_timestamp": released, "announcement_url": url}


def collect_hours(ids, position, cutoff, end, execute=stratz.execute, sleeper=sleep):
    """Page time buckets, validate boundaries locally, reject duplicates/truncation."""
    accepted, seen = [], set()
    for start in range(0, len(ids), 20):
        batch = ids[start:start + 20]
        for page in range(32):
            rows = execute(QUERY, {"ids": batch, "pos": [position], "take": 72, "skip": page * 72})["heroStats"]["winHour"]
            sleeper(.35)
            if not rows:
                break
            for row in rows:
                hour, hero, matches, wins = (row[k] for k in ("hour", "heroId", "matchCount", "winCount"))
                if any(type(x) is not int for x in (hour, hero, matches, wins)) or hero not in batch or hour % 3600 or matches < 0 or not 0 <= wins <= matches:
                    raise ValueError("Invalid hourly provider record; old data preserved")
                key = (hero, hour)
                if key in seen:
                    raise ValueError("Duplicate hourly provider record; old data preserved")
                seen.add(key)
                if cutoff <= hour and hour + 3600 <= end and matches:
                    accepted.append(row)
            # Do not rely on take being a row count: the provider pages hours.
            if min(row["hour"] for row in rows) < cutoff:
                break
        else:
            raise ValueError("Hourly pagination limit reached; old data preserved")
    return accepted


def build_snapshot(patch, role_rows, mapping, generated_at):
    cutoff = math.ceil(patch["release_timestamp"] / 3600) * 3600
    end = int(datetime.fromisoformat(generated_at).timestamp())
    totals = defaultdict(int)
    for rows in role_rows.values():
        for row in rows:
            if row["hour"] < cutoff or row["hour"] + 3600 > end:
                raise ValueError("Hourly data crosses the patch or refresh boundary")
            totals[row["heroId"]] += row["matchCount"]
    roles, evidence = {}, []
    for role, rows in role_rows.items():
        aggregate = defaultdict(lambda: [0, 0])
        for row in rows:
            aggregate[row["heroId"]][0] += row["matchCount"]
            aggregate[row["heroId"]][1] += row["winCount"]
        denominator = sum(n for n, _ in aggregate.values())
        records = []
        for hero, (matches, wins) in sorted(aggregate.items()):
            # 1,000 neutral prior observations protect early-patch rankings.
            score = meta_rating(wins / matches, matches) * (matches + 100) / (matches + 1000)
            records.append({"hero_id": mapping[hero], "role": role, "matches": matches, "wins": wins,
                            "score": score, "win_rate": wins / matches,
                            "pick_rate": matches / denominator if denominator else None,
                            "pick_rate_scope": "share of mapped hero observations in this position",
                            "all_position_matches": totals[hero], "position_share": matches / totals[hero],
                            "sample_confidence": matches / (matches + 1000)})
            evidence.append({"hero": mapping[hero], "role": role, "bracket": "ARCHON", "matches": matches,
                             "wins": wins, "pick_rate": matches / denominator if denominator else None})
        roles[role] = {"meta": records}
    hours = [r["hour"] for rows in role_rows.values() for r in rows]
    if any(not roles.get(role, {}).get("meta") for role in stratz.ROLE_POSITIONS) or not hours:
        raise ValueError("No post-release hourly coverage for every position; old data preserved")
    metadata = {**patch, "provider": "stratz", "default_bracket": "ARCHON", "rank_bracket": "ARCHON",
                "generated_at": generated_at, "filter_method": "complete hourly buckets after Valve announcement",
                "cutoff_timestamp": cutoff, "coverage_start": min(hours), "coverage_end_exclusive": max(hours) + 3600,
                "hero_observations": sum(totals.values()), "unique_matches": None,
                "game_mode": "ALL_PICK_RANKED", "normalization_version": 2,
                "uncertainty": "Time-filtered proxy, not verified game-version IDs. Announcement may follow deployment. Provider coverage may be incomplete; counts are hero observations, not unique matches.",
                "unavailable": ["patch-exclusive matchups", "patch-exclusive synergies", "patch-exclusive items/builds", "exact-Archon bans", "unique match count"]}
    snapshot = {"metadata": metadata, "brackets": {"ARCHON": {"roles": roles, "pairs": {"matchups": [], "synergies": []}}}}
    statistics = {"metadata": metadata, "hero_stats": evidence, "matchup_stats": [], "item_stats": []}
    return snapshot, statistics


def validate_snapshot(data):
    meta = data["metadata"]
    if meta.get("filter_method") != "complete hourly buckets after Valve announcement":
        raise ValueError("Snapshot has no verified patch filtering method")
    if not meta["release_timestamp"] <= meta["cutoff_timestamp"] <= meta["coverage_start"] < meta["coverage_end_exclusive"]:
        raise ValueError("Invalid patch coverage")
    if meta["rank_bracket"] != "ARCHON":
        raise ValueError("Expected exact Archon data")
    for values in data["brackets"]["ARCHON"]["roles"].values():
        if not values["meta"]:
            raise ValueError("Empty role")
        for row in values["meta"]:
            if not 0 <= row["wins"] <= row["matches"] or row["matches"] <= 0:
                raise ValueError("Invalid sample counts")
    return meta


def validate_exports(output_dir: Path, mapping_path: Path):
    """Rebuild scores and counts from retained hours, not just patch labels."""
    snapshot = json.loads((output_dir / "snapshot.json").read_text(encoding="utf-8"))
    raw = json.loads((output_dir / "patch_hours.json").read_text(encoding="utf-8"))
    statistics = json.loads((output_dir / "statistics.json").read_text(encoding="utf-8"))
    metadata = validate_snapshot(snapshot)
    expected, evidence = build_snapshot(raw["metadata"], raw["roles"], load_mapping(mapping_path), raw["metadata"]["generated_at"])
    if snapshot != expected or statistics != evidence:
        raise ValueError("Patch exports disagree with retained hourly observations; refresh required")
    return metadata


def sync(output_dir: Path, heroes: dict, mapping_path: Path):
    try:
        patch = detect_patch()
    except (OSError, ValueError, KeyError) as error:
        raise ValueError("Cannot verify the current Valve patch; old data preserved") from error
    versions = stratz.execute("query { constants { gameVersions { id name } } }")["constants"]["gameVersions"]
    patch["provider_version_id"] = next((r["id"] for r in versions if r["name"] == patch["patch"]), None)
    mapping = load_mapping(mapping_path)
    validate_mapping(mapping, set(heroes))
    now = datetime.now(UTC)
    cutoff = math.ceil(patch["release_timestamp"] / 3600) * 3600
    role_rows = {}
    # Fetch the player's primary roles first; retain all roles for the GUI.
    for role in ("carry", "offlane", "support", "mid", "hard_support"):
        role_rows[role] = collect_hours(sorted(mapping), stratz.ROLE_POSITIONS[role], cutoff, int(now.timestamp()), execute=stratz.execute)
    snapshot, statistics = build_snapshot(patch, role_rows, mapping, now.isoformat())
    validate_snapshot(snapshot)
    output_dir.mkdir(parents=True, exist_ok=True)
    backup = output_dir / "backups" / now.strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(parents=True)
    for name, data in (("patch_hours.json", {"metadata": snapshot["metadata"], "roles": role_rows}), ("statistics.json", statistics), ("snapshot.json", snapshot)):
        target = output_dir / name
        if target.exists():
            shutil.copy2(target, backup / name)
        temp = target.with_suffix(".json.tmp")
        temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        temp.replace(target)
    return snapshot
