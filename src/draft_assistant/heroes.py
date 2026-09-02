"""Loading and parsing of local draft data."""

import json
from pathlib import Path

from .aliases import build_aliases, normalize_hero
from .models import Draft, Hero

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ROLES = {"carry", "mid", "offlane", "support", "hard_support"}


def load_data() -> tuple[dict[str, Hero], dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    with (DATA_DIR / "heroes.json").open(encoding="utf-8") as file:
        hero_data = json.load(file)
    from .validation import validate_directed_scores, validate_heroes
    validate_heroes(hero_data)
    heroes = {
        item["id"]: Hero(
            item["id"],
            item["display_name"],
            tuple(item["roles"]),
            item.get("base_rating", 50.0),
            item.get("role_scores", {}),
        )
        for item in hero_data
    }
    with (DATA_DIR / "matchups.json").open(encoding="utf-8") as file:
        matchups = json.load(file)
    with (DATA_DIR / "synergies.json").open(encoding="utf-8") as file:
        synergies = json.load(file)
    validate_directed_scores(matchups, set(heroes), "matchup", 20)
    validate_directed_scores(synergies, set(heroes), "synergy", 20)
    return heroes, matchups, synergies


def parse_draft(value: str, heroes: dict[str, Hero] | None = None) -> Draft:
    heroes = heroes or load_data()[0]
    parts = [part.strip() for part in value.split("|")]
    if len(parts) != 3 or not parts[2]:
        raise ValueError("Use: enemies | allies | role")
    aliases = build_aliases(heroes)
    enemies = _parse_heroes(parts[0], heroes, aliases)
    allies = _parse_heroes(parts[1], heroes, aliases)
    role = parts[2].casefold().replace(" ", "_")
    if role not in ROLES:
        raise ValueError(f"Unknown role: {parts[2]}")
    all_picks = enemies + allies
    if len(set(all_picks)) != len(all_picks):
        raise ValueError("A hero cannot appear more than once")
    return Draft(enemies, allies, role)


def _parse_heroes(section: str, heroes: dict[str, Hero], aliases: dict[str, str]) -> tuple[str, ...]:
    """Parse aliases, including multi-word aliases, from one team section."""
    tokens = section.replace(",", " ").split()
    known_heroes = set(heroes)
    max_alias_words = max(len(alias.split()) for alias in aliases)
    parsed = []
    index = 0
    while index < len(tokens):
        for size in range(min(max_alias_words, len(tokens) - index), 0, -1):
            candidate = " ".join(tokens[index:index + size])
            try:
                parsed.append(normalize_hero(candidate, known_heroes, aliases))
                index += size
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unknown hero: {tokens[index]}")
    return tuple(parsed)
