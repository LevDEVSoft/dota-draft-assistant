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
BRACKET_LABELS = {"HERALD_GUARDIAN": "Herald / Guardian"}
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
class PlayerAccessProbe:
    steam_account_id: int | None
    player_available: bool
    match_query_accepted: bool
    recent_matches_available: bool
    visible_match_count: int
    total_match_count: int | None
    explicit_privacy_error: bool
    private_history_access: str
    reason: str | None = None


def probe_player_access(steam_id64: str) -> PlayerAccessProbe:
    """Read at most five matches; this never prints or persists the API token."""
    try:
        account_id = int(steam_id64) - 76561197960265728
        if account_id <= 0: raise ValueError
    except (TypeError, ValueError):
        return PlayerAccessProbe(None, False, False, False, 0, None, False, "UNKNOWN", "invalid SteamID64")
    query = """query PlayerProbe($id:Long!) { player(steamAccountId:$id) { steamAccountId matchCount lastMatchDate matches(request:{take:5 skip:0 playerList:SINGLE orderBy:DESC}) { id startDateTime durationSeconds isStats } } }"""
    try:
        player = execute(query, {"id": account_id}).get("player")
    except StratzError as error:
        return PlayerAccessProbe(account_id, False, False, False, 0, None, False, "UNKNOWN", str(error).replace(token() if os.environ.get("STRATZ_API_TOKEN") else "", "[redacted]"))
    if not player:
        return PlayerAccessProbe(account_id, False, True, False, 0, None, False, "UNKNOWN", "player unavailable")
    matches = player.get("matches")
    if matches is None:
        return PlayerAccessProbe(account_id, True, True, False, 0, player.get("matchCount"), True, "UNKNOWN", "recent matches unavailable or privacy-restricted")
    count = len(matches)
    reason = None if count else "zero match nodes returned; no explicit privacy error"
    return PlayerAccessProbe(account_id, True, True, bool(count), count, player.get("matchCount"), False, "YES" if count else "UNKNOWN", reason)


@dataclass(frozen=True)
class SyncPlan:
    pair_hero_ids: tuple[int, ...]
    role: str = "all"

    @property
    def meta_requests(self) -> int:
        # One unfiltered total plus one batched query for each Dota position.
        return 1 + len(ROLE_POSITIONS)

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


def build_sync_plan(heroes: dict, mapping_path: Path) -> SyncPlan:
    """Plan one shared pair pass and batched meta for every supported role."""
    mapping = load_mapping(mapping_path)
    validate_mapping(mapping, set(heroes))
    # matchUp is position-agnostic, so a single request for every mapped hero is
    # reusable by all five role datasets.
    return SyncPlan(pair_hero_ids=tuple(sorted(mapping)))


def _other_hero(row: dict, source_id: int) -> int | None:
    if row.get("heroId1") == source_id:
        return row.get("heroId2")
    if row.get("heroId2") == source_id:
        return row.get("heroId1")
    return None


def _source_wins(row: dict, source_id: int) -> int:
    return row["winCount"] if row["heroId1"] == source_id else row["matchCount"] - row["winCount"]


def sync(output: Path, heroes: dict, mapping_path: Path, bracket: str = DEFAULT_BRACKET, pair_delay: float = DEFAULT_PAIR_DELAY_SECONDS, sleeper: Callable[[float], None] = sleep) -> dict:
    """Fetch all role meta plus one shared, paced global pair dataset."""
    if bracket not in BRACKET_LABELS: raise StratzError(f"Unsupported bracket: {bracket}")
    plan = build_sync_plan(heroes, mapping_path)
    mapping = load_mapping(mapping_path)
    ids = sorted(mapping)
    canonical_heroes = set(heroes)
    raw = {"metadata": {"provider": "stratz", "generated_at": datetime.now(UTC).isoformat(), "bracket": bracket, "roles": list(ROLE_POSITIONS)}, "meta": [], "matchups": [], "synergies": []}
    all_position, role_meta = {}, {role: [] for role in ROLE_POSITIONS}
    for row in fetch_meta(ids, None, bracket):
        if row.get("heroId") in mapping:
            all_position[row["heroId"]] = all_position.get(row["heroId"], 0) + row["matchCount"]
            raw["meta"].append({"hero_id": row["heroId"], "matches": row["matchCount"], "wins": row["winCount"]})
    for role in ROLE_POSITIONS:
        for row in fetch_meta(ids, role, bracket):
            if row.get("heroId") in mapping:
                all_matches, matches = all_position.get(row["heroId"], 0), row["matchCount"]
                role_meta[role].append({"hero_id": row["heroId"], "role": role, "matches": matches, "wins": row["winCount"], "all_position_matches": all_matches, "position_share": min(1, matches / all_matches) if all_matches else 0, "sample_confidence": matches / (matches + 1000)})
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
    # Pair ratings use the unfiltered baseline; position relevance is applied by
    # the runtime using the selected role's metadata.
    normalized_pairs = normalize_snapshot(raw, mapping, canonical_heroes)
    roles = {}
    for role, records in role_meta.items():
        normalized = normalize_snapshot({"meta": records}, mapping, canonical_heroes)["meta"]
        by_external = {record["hero_id"]: record for record in records}
        for record in normalized:
            external_id = next(key for key, value in mapping.items() if value == record["hero_id"])
            extra = by_external[external_id]
            record.update({key: extra[key] for key in ("all_position_matches", "position_share", "sample_confidence")})
        roles[role] = {"meta": normalized}
    snapshot = {"metadata": {"provider":"stratz", "generated_at":raw["metadata"]["generated_at"], "default_bracket":bracket}, "brackets": {bracket: {"roles": roles, "pairs": {"matchups": normalized_pairs["matchups"], "synergies": normalized_pairs["synergies"]}}}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot
