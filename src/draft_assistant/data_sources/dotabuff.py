"""Public DOTABUFF counter-page provider; isolated from runtime scoring."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from time import sleep
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .normalization import dotabuff_matchup_rating

BASE_URL = "https://www.dotabuff.com/heroes"
WINDOWS = frozenset({"week", "month", "year"})
DEFAULT_WINDOW = "month"
DEFAULT_DELAY_SECONDS = 0.85
USER_AGENT = "dota-draft-assistant/0.1 (+public-dotabuff-counter-pages)"


class DotabuffError(RuntimeError):
    pass


class DotabuffBlockedError(DotabuffError):
    pass


class DotabuffParseError(DotabuffError):
    pass


@dataclass(frozen=True)
class DotabuffMatchup:
    hero_id: str
    opponent_id: str
    advantage: float
    win_rate: float
    matches: int


def hero_slug(hero_id: str) -> str:
    """DOTABUFF's public hero URLs use the canonical name with hyphens."""
    if not re.fullmatch(r"[a-z0-9_]+", hero_id):
        raise ValueError(f"Invalid canonical hero ID: {hero_id}")
    return hero_id.replace("_", "-")


def validate_slugs(hero_ids: set[str]) -> dict[str, str]:
    mapping = {hero_id: hero_slug(hero_id) for hero_id in hero_ids}
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("DOTABUFF hero slugs must be unique")
    return mapping


def counter_url(hero_id: str, window: str = DEFAULT_WINDOW) -> str:
    if window not in WINDOWS:
        raise ValueError(f"Unsupported DOTABUFF window: {window}")
    return f"{BASE_URL}/{hero_slug(hero_id)}/counters?date={window}"


def fetch_html(hero_id: str, window: str = DEFAULT_WINDOW, timeout: int = 30) -> str:
    request = Request(counter_url(hero_id, window), headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", "replace")
    except HTTPError as error:
        if error.code in {403, 429}:
            raise DotabuffBlockedError(f"DOTABUFF HTTP error: {error.code}") from error
        raise DotabuffError(f"DOTABUFF HTTP error: {error.code}") from error
    except (URLError, OSError) as error:
        raise DotabuffError("DOTABUFF request failed") from error
    if "captcha" in html.casefold() or "cloudflare" in html.casefold() or "challenge" in html.casefold():
        raise DotabuffBlockedError("DOTABUFF returned a challenge page")
    return html


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self._table, self._row, self._cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif self._table is not None and tag == "tr":
            self._row = []
        elif self._row is not None and tag in {"td", "th"}:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _percent(value: str) -> float:
    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)%", value.strip())
    if not match:
        raise DotabuffParseError(f"Invalid percentage: {value!r}")
    return float(match.group(1)) / 100


def _matches(value: str) -> int:
    digits = value.replace(",", "").strip()
    if not digits.isdigit():
        raise DotabuffParseError(f"Invalid match count: {value!r}")
    return int(digits)


def _name_map(heroes: dict) -> dict[str, str]:
    from draft_assistant.aliases import build_aliases, normalize_key
    aliases = build_aliases(heroes)
    return {normalize_key(name): hero_id for name, hero_id in aliases.items()}


def parse_matchups(html: str, candidate_id: str, heroes: dict, strict: bool = True) -> list[DotabuffMatchup]:
    parser = _TableParser(); parser.feed(html)
    table = next((table for table in parser.tables if table and {"Hero", "Matches Played"}.issubset(set(table[0])) and any("Win Rate" in cell for cell in table[0])), None)
    if table is None:
        raise DotabuffParseError("DOTABUFF Matchups table was not found")
    headers = table[0]
    advantage_index = next((i for i, cell in enumerate(headers) if "Advantage" in cell or "Disadvantage" in cell), None)
    win_index = next((i for i, cell in enumerate(headers) if "Win Rate" in cell), None)
    matches_index = headers.index("Matches Played")
    if advantage_index is None or win_index is None:
        raise DotabuffParseError("DOTABUFF Matchups table columns changed")
    sign = -1 if "Disadvantage" in headers[advantage_index] else 1
    names = _name_map(heroes)
    records = []
    for row in table[1:]:
        if len(row) != len(headers):
            if not strict:
                continue
            raise DotabuffParseError("Malformed DOTABUFF matchup row")
        opponent = names.get(row[0].casefold())
        if opponent is None:
            if not strict:
                continue
            raise DotabuffParseError(f"Unknown DOTABUFF hero: {row[0]}")
        try:
            advantage, win_rate, matches = sign * _percent(row[advantage_index]), _percent(row[win_index]), _matches(row[matches_index])
        except DotabuffParseError:
            if not strict:
                continue
            raise
        if not 0 <= win_rate <= 1 or matches < 0:
            raise DotabuffParseError("Invalid DOTABUFF matchup values")
        records.append(DotabuffMatchup(candidate_id, opponent, advantage, win_rate, matches))
    if not records:
        raise DotabuffParseError("DOTABUFF Matchups table is empty")
    return records


def role_candidates(role: str, heroes: dict) -> tuple[str, ...]:
    if role not in {"carry", "mid", "offlane", "support", "hard_support"}:
        raise ValueError(f"Unknown role: {role}")
    return tuple(sorted(hero_id for hero_id, hero in heroes.items() if role in hero.roles))


def sync(role: str, window: str, output: Path, heroes: dict, delay: float = DEFAULT_DELAY_SECONDS, sleeper: Callable[[float], None] = sleep) -> dict:
    if window not in WINDOWS:
        raise ValueError(f"Unsupported DOTABUFF window: {window}")
    candidates = role_candidates(role, heroes)
    matchups = []
    for index, candidate_id in enumerate(candidates):
        if index and delay > 0:
            sleeper(delay)
        matchups.extend(parse_matchups(fetch_html(candidate_id, window), candidate_id, heroes, strict=False))
    keys = [(record.hero_id, record.opponent_id) for record in matchups]
    if len(keys) != len(set(keys)):
        raise DotabuffParseError("Duplicate DOTABUFF matchup pair")
    snapshot = {"metadata": {"provider": "dotabuff", "generated_at": datetime.now(UTC).isoformat(), "window": window, "role": role, "source_type": "public_counter_pages"}, "meta": [], "matchups": [{"hero_id": r.hero_id, "opponent_id": r.opponent_id, "score": dotabuff_matchup_rating(r.advantage, r.matches), "matches": r.matches, "win_rate": r.win_rate, "advantage": r.advantage} for r in sorted(matchups, key=lambda r: (r.hero_id, r.opponent_id))], "synergies": []}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot
