"""Offline importer: python -m draft_assistant.data_sources.import_snapshot RAW OUT."""

import argparse
import json
from pathlib import Path

from .mapping import load_mapping, validate_mapping
from .normalization import matchup_rating, meta_rating, synergy_rating


def _rate(record: dict) -> float:
    matches, wins = record["matches"], record["wins"]
    if not isinstance(matches, int) or not isinstance(wins, int) or matches <= 0 or not 0 <= wins <= matches:
        raise ValueError("matches and wins must be valid integers")
    return wins / matches


def normalize_snapshot(raw: dict, mapping: dict[int, str], hero_ids: set[str]) -> dict:
    """Convert provider-neutral numeric records into the local scored snapshot."""
    validate_mapping(mapping, hero_ids)
    def hero(external_id: int) -> str:
        try:
            return mapping[int(external_id)]
        except KeyError as error:
            raise ValueError(f"Unknown external hero ID: {external_id}") from error
    meta = []
    baselines = {}
    for record in raw.get("meta", []):
        hero_id, rate = hero(record["hero_id"]), _rate(record)
        baselines[hero_id] = rate
        meta.append({"hero_id": hero_id, "role": record.get("role"), "score": meta_rating(rate, record["matches"]), "matches": record["matches"]})
    matchups = []
    for record in raw.get("matchups", []):
        hero_id, opponent_id, rate = hero(record["hero_id"]), hero(record["opponent_id"]), _rate(record)
        matchups.append({"hero_id": hero_id, "opponent_id": opponent_id, "score": matchup_rating(rate, baselines.get(hero_id, 0.5), record["matches"]), "matches": record["matches"]})
    synergies = []
    seen = set()
    for record in raw.get("synergies", []):
        hero_id, ally_id, rate = hero(record["hero_id"]), hero(record["ally_id"]), _rate(record)
        pair = tuple(sorted((hero_id, ally_id)))
        if hero_id == ally_id or pair in seen:
            raise ValueError("Duplicate synergy pair")
        seen.add(pair)
        expected = (baselines.get(hero_id, 0.5) + baselines.get(ally_id, 0.5)) / 2
        synergies.append({"heroes": list(pair), "score": synergy_rating(rate, expected, record["matches"]), "matches": record["matches"]})
    return {"metadata": raw.get("metadata", {}), "meta": sorted(meta, key=lambda item: item["hero_id"]), "matchups": sorted(matchups, key=lambda item: (item["hero_id"], item["opponent_id"])), "synergies": sorted(synergies, key=lambda item: item["heroes"])}


def import_snapshot(raw_path: Path, output_dir: Path, mapping_path: Path, hero_ids: set[str]) -> dict:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    snapshot = normalize_snapshot(raw, load_mapping(mapping_path), hero_ids)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "snapshot.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize an offline synthetic statistics snapshot.")
    parser.add_argument("raw_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--mapping", type=Path, default=Path("data/hero_id_map.json"))
    args = parser.parse_args()
    from draft_assistant.heroes import load_data
    snapshot = import_snapshot(args.raw_json, args.output_dir, args.mapping, set(load_data()[0]))
    print(f"Snapshot OK: {len(snapshot['meta'])} meta, {len(snapshot['matchups'])} matchups, {len(snapshot['synergies'])} synergies")
    return 0


if __name__ == "__main__":
    main()
