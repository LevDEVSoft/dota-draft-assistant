"""Command line interface for draft recommendations."""

import argparse

from .aliases import build_aliases
from .data_sources.stratz import StratzError
from .heroes import load_data, parse_draft
from .validation import validate_aliases
from .scoring import recommend


def _display(hero_id: str, heroes: dict) -> str:
    return heroes[hero_id].display_name


def format_explanation(item, heroes: dict) -> str:
    lines = [f"{item.hero.display_name} {item.score:.1f}", ""]
    lines.append(f"  base: {item.breakdown.base:+.1f}")
    lines.append(f"  role: {item.breakdown.role:+.1f}")
    for enemy, score in item.breakdown.matchup_contributions:
        if score:
            lines.append(f"  vs {_display(enemy, heroes)}: {score:+.1f}")
    for ally, score in item.breakdown.synergy_contributions:
        if score:
            lines.append(f"  with {_display(ally, heroes)}: {score:+.1f}")
    lines.append(f"  total: {item.breakdown.total:.1f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recommend Dota 2 hero picks from a manual draft.")
    parser.add_argument("draft", nargs="?", help="enemies | allies | role")
    parser.add_argument("--explain", action="store_true", help="show score reasons")
    parser.add_argument("--top", type=int, default=3, help="number of picks to show")
    parser.add_argument("--validate-data", action="store_true", help="validate local data files")
    parser.add_argument("--sync-stats", action="store_true", help="fetch a local STRATZ snapshot")
    parser.add_argument("--stats-role", choices=("carry", "mid", "offlane", "support", "hard_support"), help="limit STRATZ meta statistics to one role")
    args = parser.parse_args(argv)
    try:
        heroes, matchups, synergies = load_data()
        aliases = build_aliases(heroes)
        validate_aliases(aliases, set(heroes))
        if args.validate_data:
            print(f"Data OK\nHeroes: {len(heroes)}\nAliases: {len(aliases)}\nMatchups: {sum(len(values) for values in matchups.values())}\nSynergies: {len(synergies)}")
            return 0
        if args.sync_stats:
            from .data_sources.stratz import sync
            from .heroes import DATA_DIR
            snapshot = sync(args.stats_role, DATA_DIR / "generated" / "snapshot.json", set(heroes), DATA_DIR / "hero_id_map.json")
            print(f"Snapshot written: data/generated/snapshot.json\nHeroes: {len(snapshot['meta'])}\nMatchups: {len(snapshot['matchups'])}\nSynergies: {len(snapshot['synergies'])}")
            return 0
        if not args.draft or args.top < 1:
            parser.error("Provide a draft and a positive --top value")
        choices = recommend(parse_draft(args.draft, heroes), args.top)
    except (StratzError, ValueError) as error:
        parser.error(str(error))
    if not choices:
        parser.error("No heroes available for this role")
    if args.explain:
        print("\n\n".join(format_explanation(item, heroes) for item in choices))
    else:
        for index, item in enumerate(choices, 1):
            print(f"{index}. {item.hero.display_name:<20} {item.score:.1f}")
    return 0


if __name__ == "__main__":
    main()
