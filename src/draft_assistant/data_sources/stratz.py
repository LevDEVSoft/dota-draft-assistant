"""Isolated STRATZ GraphQL adapter; never imported by runtime scoring."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .import_snapshot import normalize_snapshot
from .mapping import load_mapping, validate_mapping

ENDPOINT = "https://api.stratz.com/graphql"
ROLE_POSITIONS = {"carry": "POSITION_1", "mid": "POSITION_2", "offlane": "POSITION_3", "support": "POSITION_4", "hard_support": "POSITION_5"}
POSITION_ROLES = {position: role for role, position in ROLE_POSITIONS.items()}
DEFAULT_BRACKET = "HERALD_GUARDIAN"


class StratzError(RuntimeError):
    pass


def token() -> str:
    value = os.environ.get("STRATZ_API_TOKEN", "").strip()
    if not value:
        raise StratzError("STRATZ_API_TOKEN is not set.")
    return value


def execute(query: str, variables: dict | None = None, timeout: int = 30) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = Request(ENDPOINT, data=payload, headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json", "User-Agent": "STRATZ_API"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:1000]
        raise StratzError(f"STRATZ HTTP error: {error.code}: {detail}") from error
    except (URLError, OSError, json.JSONDecodeError) as error:
        raise StratzError("STRATZ request failed") from error
    if body.get("errors"):
        raise StratzError("STRATZ GraphQL returned errors")
    if not isinstance(body.get("data"), dict):
        raise StratzError("STRATZ returned malformed data")
    return body["data"]


META_QUERY = """query Meta($ids:[Short!],$brackets:[RankBracketBasicEnum!],$positions:[MatchPlayerPositionType!]) { heroStats { stats(heroIds:$ids, bracketBasicIds:$brackets, positionIds:$positions) { heroId position matchCount winCount } } }"""
PAIR_QUERY = """query Pair($id:Short!,$brackets:[RankBracketBasicEnum!]) { heroStats { matchUp(heroId:$id, bracketBasicIds:$brackets) { heroId with { heroId1 heroId2 matchCount winCount } vs { heroId1 heroId2 matchCount winCount } } } }"""


def fetch_meta(hero_ids: list[int], role: str | None = None, bracket: str = DEFAULT_BRACKET) -> list[dict]:
    if role is not None and role not in ROLE_POSITIONS:
        raise StratzError(f"Unknown role: {role}")
    positions = [ROLE_POSITIONS[role]] if role else list(ROLE_POSITIONS.values())
    return execute(META_QUERY, {"ids": hero_ids, "brackets": [bracket], "positions": positions})["heroStats"]["stats"]


def fetch_pairs(hero_id: int, bracket: str = DEFAULT_BRACKET) -> dict:
    rows = execute(PAIR_QUERY, {"id": hero_id, "brackets": [bracket]})["heroStats"]["matchUp"]
    return rows[0] if rows else {"with": [], "vs": []}


def _other_hero(row: dict, source_id: int) -> int | None:
    if row.get("heroId1") == source_id:
        return row.get("heroId2")
    if row.get("heroId2") == source_id:
        return row.get("heroId1")
    return None


def _source_wins(row: dict, source_id: int) -> int:
    """`vs.winCount` is wins for heroId1; flip it when querying heroId2."""
    return row["winCount"] if row["heroId1"] == source_id else row["matchCount"] - row["winCount"]


def sync(role: str | None, output: Path, canonical_heroes: set[str], mapping_path: Path, bracket: str = DEFAULT_BRACKET) -> dict:
    """Fetch every mapped hero and persist one normalized, scored local snapshot."""
    mapping = load_mapping(mapping_path)
    validate_mapping(mapping, canonical_heroes)
    ids = sorted(mapping)
    raw = {"metadata": {"provider": "stratz", "generated_at": datetime.now(UTC).isoformat(), "bracket": bracket, "role": role}, "meta": [], "matchups": [], "synergies": []}
    meta_by_hero: dict[int, dict] = {}
    for row in fetch_meta(ids, role, bracket):
        if row.get("heroId") in mapping:
            hero_id = row["heroId"]
            if role is not None:
                raw["meta"].append({"hero_id": hero_id, "role": role, "matches": row["matchCount"], "wins": row["winCount"]})
            else:
                aggregate = meta_by_hero.setdefault(hero_id, {"hero_id": hero_id, "role": None, "matches": 0, "wins": 0})
                aggregate["matches"] += row["matchCount"]
                aggregate["wins"] += row["winCount"]
    raw["meta"].extend(meta_by_hero.values())
    seen_synergies = set()
    for source_id in ids:
        pairs = fetch_pairs(source_id, bracket)
        for row in pairs.get("vs") or []:
            target_id = _other_hero(row, source_id)
            if target_id in mapping:
                raw["matchups"].append({"hero_id": source_id, "opponent_id": target_id, "matches": row["matchCount"], "wins": _source_wins(row, source_id)})
        for row in pairs.get("with") or []:
            target_id = _other_hero(row, source_id)
            pair = tuple(sorted((source_id, target_id))) if target_id in mapping else None
            if pair and pair not in seen_synergies:
                seen_synergies.add(pair)
                raw["synergies"].append({"hero_id": source_id, "ally_id": target_id, "matches": row["matchCount"], "wins": row["winCount"]})
    snapshot = normalize_snapshot(raw, mapping, canonical_heroes)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot
