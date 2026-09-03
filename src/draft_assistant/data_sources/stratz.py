"""Isolated, rate-limit-aware STRATZ GraphQL adapter."""

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .import_snapshot import normalize_snapshot
from .mapping import load_mapping, validate_mapping

ENDPOINT = "https://api.stratz.com/graphql"
ROLE_POSITIONS = {"carry": "POSITION_1", "mid": "POSITION_2", "offlane": "POSITION_3", "support": "POSITION_4", "hard_support": "POSITION_5"}
DEFAULT_BRACKET = "HERALD_GUARDIAN"
DEFAULT_PAIR_DELAY_SECONDS = 0.30


class StratzError(RuntimeError):
    pass


class StratzRateLimitError(StratzError):
    """A terminal 429 response, with optional safe server pacing metadata."""

    def __init__(self, retry_after: int | None = None, remaining: int | None = None, reset: int | None = None):
        self.retry_after, self.remaining, self.reset = retry_after, remaining, reset
        details = []
        if retry_after is not None:
            details.append(f"retry_after={retry_after}s")
        if remaining is not None:
            details.append(f"remaining={remaining}")
        if reset is not None:
            details.append(f"reset={reset}")
        suffix = f" ({', '.join(details)})" if details else ""
        super().__init__(f"STRATZ HTTP error: 429: API rate limit exceeded{suffix}")


@dataclass(frozen=True)
class SyncPlan:
    role: str
    pair_hero_ids: tuple[int, ...]

    @property
    def meta_requests(self) -> int:
        return 1

    @property
    def expected_requests(self) -> int:
        return self.meta_requests + len(self.pair_hero_ids)


def token() -> str:
    value = os.environ.get("STRATZ_API_TOKEN", "").strip()
    if not value:
        raise StratzError("STRATZ_API_TOKEN is not set.")
    return value


def _header_int(headers, *names: str) -> int | None:
    for name in names:
        value = headers.get(name) if headers else None
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            continue
    return None


def execute(query: str, variables: dict | None = None, timeout: int = 30) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = Request(ENDPOINT, data=payload, headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json", "User-Agent": "STRATZ_API"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except HTTPError as error:
        if error.code == 429:
            raise StratzRateLimitError(
                _header_int(error.headers, "Retry-After"),
                _header_int(error.headers, "X-RateLimit-Remaining", "RateLimit-Remaining"),
                _header_int(error.headers, "X-RateLimit-Reset", "RateLimit-Reset"),
            ) from error
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
PAIR_QUERY = """query Pair($id:Short!,$brackets:[RankBracketBasicEnum!],$take:Int!) { heroStats { matchUp(heroId:$id, bracketBasicIds:$brackets, take:$take) { heroId with { heroId1 heroId2 matchCount winCount } vs { heroId1 heroId2 matchCount winCount } } } }"""


def fetch_meta(hero_ids: list[int], role: str | None, bracket: str = DEFAULT_BRACKET) -> list[dict]:
    if role is not None and role not in ROLE_POSITIONS:
        raise StratzError(f"Unknown role: {role}")
    return execute(META_QUERY, {"ids": hero_ids, "brackets": [bracket], "positions": [ROLE_POSITIONS[role]] if role else list(ROLE_POSITIONS.values())})["heroStats"]["stats"]


def fetch_pairs(hero_id: int, bracket: str = DEFAULT_BRACKET) -> dict:
    rows = execute(PAIR_QUERY, {"id": hero_id, "brackets": [bracket], "take": 127})["heroStats"]["matchUp"]
    return rows[0] if rows else {"with": [], "vs": []}


def build_sync_plan(role: str, heroes: dict, mapping_path: Path) -> SyncPlan:
    if role not in ROLE_POSITIONS:
        raise StratzError(f"Unknown role: {role}")
    mapping = load_mapping(mapping_path)
    validate_mapping(mapping, set(heroes))
    allowed = {hero_id for hero_id, hero in heroes.items() if role in hero.roles}
    return SyncPlan(role, tuple(sorted(external_id for external_id, hero_id in mapping.items() if hero_id in allowed)))


def _other_hero(row: dict, source_id: int) -> int | None:
    if row.get("heroId1") == source_id:
        return row.get("heroId2")
    if row.get("heroId2") == source_id:
        return row.get("heroId1")
    return None


def _source_wins(row: dict, source_id: int) -> int:
    return row["winCount"] if row["heroId1"] == source_id else row["matchCount"] - row["winCount"]


def sync(role: str, output: Path, heroes: dict, mapping_path: Path, bracket: str = DEFAULT_BRACKET, pair_delay: float = DEFAULT_PAIR_DELAY_SECONDS, sleeper: Callable[[float], None] = sleep) -> dict:
    """Fetch one role-specific snapshot, pacing pair requests below STRATZ limits."""
    plan = build_sync_plan(role, heroes, mapping_path)
    mapping = load_mapping(mapping_path)
    ids = sorted(mapping)
    canonical_heroes = set(heroes)
    raw = {"metadata": {"provider": "stratz", "generated_at": datetime.now(UTC).isoformat(), "bracket": bracket, "role": role}, "meta": [], "matchups": [], "synergies": []}
    all_position = {}
    for row in fetch_meta(ids, None, bracket):
        if row.get("heroId") in mapping: all_position[row["heroId"]] = all_position.get(row["heroId"], 0) + row["matchCount"]
    for row in fetch_meta(list(plan.pair_hero_ids), role, bracket):
        if row.get("heroId") in mapping:
            all_matches = all_position.get(row["heroId"], 0); pos_matches = row["matchCount"]
            raw["meta"].append({"hero_id": row["heroId"], "role": role, "matches": pos_matches, "wins": row["winCount"], "all_position_matches": all_matches, "position_share": min(1, pos_matches / all_matches) if all_matches else 0, "sample_confidence": pos_matches / (pos_matches + 1000)})
    seen_synergies = set()
    for index, source_id in enumerate(plan.pair_hero_ids):
        if index and pair_delay > 0:
            sleeper(pair_delay)
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
    by_external = {row["hero_id"]: row for row in raw["meta"]}
    for row in snapshot["meta"]:
        extra = by_external.get(next(key for key, value in mapping.items() if value == row["hero_id"]), {})
        row.update({key: extra.get(key, 0) for key in ("all_position_matches", "position_share", "sample_confidence")})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot
