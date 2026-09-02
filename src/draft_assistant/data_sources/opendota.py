"""Public OpenDota heroStats provider; meta only, never runtime scoring."""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .mapping import load_mapping, validate_mapping
from .normalization import meta_rating

HERO_STATS_URL = "https://api.opendota.com/api/heroStats"
USER_AGENT = "dota-draft-assistant/0.1 (+public-opendota-heroStats)"


class OpenDotaError(RuntimeError):
    pass


class OpenDotaRateLimitError(OpenDotaError):
    pass


def fetch_hero_stats(timeout: int = 30) -> list[dict]:
    request = Request(HERO_STATS_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 429:
            raise OpenDotaRateLimitError("OpenDota HTTP error: 429") from error
        raise OpenDotaError(f"OpenDota HTTP error: {error.code}") from error
    except (URLError, OSError, json.JSONDecodeError) as error:
        raise OpenDotaError("OpenDota request failed") from error
    if not isinstance(payload, list):
        raise OpenDotaError("OpenDota returned malformed heroStats data")
    return payload


def _integer(row: dict, field: str) -> int:
    value = row.get(field)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"OpenDota heroStats has invalid {field}")
    return value


def build_snapshot(rows: list[dict], mapping: dict[int, str], hero_ids: set[str]) -> dict:
    validate_mapping(mapping, hero_ids)
    parsed, unknown = {}, []
    for row in rows:
        hero_id = row.get("id")
        if not isinstance(hero_id, int):
            raise ValueError("OpenDota heroStats has invalid id")
        if hero_id not in mapping:
            unknown.append(hero_id)
            continue
        herald_matches, herald_wins = _integer(row, "1_pick"), _integer(row, "1_win")
        guardian_matches, guardian_wins = _integer(row, "2_pick"), _integer(row, "2_win")
        if herald_wins > herald_matches or guardian_wins > guardian_matches:
            raise ValueError("OpenDota heroStats wins exceed picks")
        matches, wins = herald_matches + guardian_matches, herald_wins + guardian_wins
        if hero_id in parsed:
            raise ValueError(f"Duplicate OpenDota hero ID: {hero_id}")
        canonical = mapping[hero_id]
        parsed[hero_id] = {"hero_id": canonical, "matches": matches, "wins": wins, "win_rate": wins / matches if matches else 0.0, "score": meta_rating(wins / matches if matches else 0.5, matches), "herald_matches": herald_matches, "herald_wins": herald_wins, "guardian_matches": guardian_matches, "guardian_wins": guardian_wins}
    missing = sorted(set(mapping) - set(parsed))
    return {"metadata": {"provider": "opendota", "rank_bracket": "HERALD_GUARDIAN", "source": "heroStats", "generated_at": datetime.now(UTC).isoformat(), "unmapped_hero_ids": sorted(set(unknown)), "missing_mapped_hero_ids": missing}, "meta": sorted(parsed.values(), key=lambda row: row["hero_id"]), "matchups": [], "synergies": []}


def sync(output: Path, heroes: dict, mapping_path: Path) -> dict:
    """Fetch one public heroStats dataset and write a deterministic local snapshot."""
    snapshot = build_snapshot(fetch_hero_stats(), load_mapping(mapping_path), set(heroes))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot
