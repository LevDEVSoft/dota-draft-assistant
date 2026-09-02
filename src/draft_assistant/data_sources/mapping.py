"""Mapping of external numeric IDs to project canonical IDs."""

import json
from pathlib import Path


def load_mapping(path: Path) -> dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping = {int(key): value for key, value in raw.items()}
    if len(mapping) != len(raw) or len(set(mapping.values())) != len(mapping):
        raise ValueError("External and canonical hero IDs must be unique")
    return mapping


def validate_mapping(mapping: dict[int, str], hero_ids: set[str]) -> None:
    if len(mapping) != len(set(mapping)) or len(set(mapping.values())) != len(mapping):
        raise ValueError("Duplicate hero mapping")
    unknown = set(mapping.values()) - hero_ids
    if unknown:
        raise ValueError(f"Unknown mapped hero: {sorted(unknown)[0]}")
    missing = hero_ids - set(mapping.values())
    if missing:
        raise ValueError(f"Missing mapped hero: {sorted(missing)[0]}")
