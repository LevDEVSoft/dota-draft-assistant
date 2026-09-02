"""Validation for the local, hand-maintained data files."""

from numbers import Real

from .heroes import ROLES

MATCHUP_LIMIT = 20
SYNERGY_LIMIT = 20


def validate_heroes(raw_heroes: list[dict]) -> None:
    ids, names = set(), set()
    for hero in raw_heroes:
        required = {"id", "display_name", "roles", "base_rating", "role_scores"}
        missing = required - hero.keys()
        if missing:
            raise ValueError(f"Hero is missing fields: {', '.join(sorted(missing))}")
        if not isinstance(hero["id"], str) or not hero["id"].strip() or not isinstance(hero["display_name"], str) or not hero["display_name"].strip():
            raise ValueError("Hero id and display name must not be empty")
        if hero["id"] in ids or hero["display_name"].casefold() in names:
            raise ValueError(f"Duplicate hero: {hero['id']}")
        ids.add(hero["id"]); names.add(hero["display_name"].casefold())
        if not hero["roles"] or not set(hero["roles"]) <= ROLES or not set(hero["role_scores"]) <= set(hero["roles"]):
            raise ValueError(f"Invalid roles for {hero['id']}")
        if set(hero["roles"]) != set(hero["role_scores"]):
            raise ValueError(f"Missing role score for {hero['id']}")
        if not all(isinstance(value, Real) and not isinstance(value, bool) for value in [hero["base_rating"], *hero["role_scores"].values()]):
            raise ValueError(f"Invalid numeric value for {hero['id']}")


def validate_directed_scores(data: dict, hero_ids: set[str], label: str, limit: int) -> None:
    for source, targets in data.items():
        if source not in hero_ids:
            raise ValueError(f"Unknown {label} hero: {source}")
        for target, value in targets.items():
            if target not in hero_ids or not isinstance(value, Real) or abs(value) > limit:
                raise ValueError(f"Invalid {label} entry: {source} -> {target}")


def validate_aliases(aliases: dict[str, str], hero_ids: set[str]) -> None:
    for alias, hero_id in aliases.items():
        if not alias or hero_id not in hero_ids:
            raise ValueError(f"Invalid alias: {alias}")
