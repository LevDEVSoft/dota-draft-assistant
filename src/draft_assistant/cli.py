"""Command line interface for draft recommendations."""

import argparse

from .aliases import build_aliases
from .data_sources.dotabuff import DotabuffError
from .data_sources.opendota import OpenDotaError
from .data_sources.stratz import StratzError
from .heroes import load_data, parse_draft
from .validation import validate_aliases
from .scoring import recommend
from .item_knowledge import ITEMS
from .item_aliases import build_aliases as build_item_aliases
from .item_graph import validate_graph


def _display(hero_id: str, heroes: dict) -> str:
    return heroes[hero_id].display_name if hero_id in heroes else hero_id.title()


def format_explanation(item, heroes: dict) -> str:
    lines = [f"{item.hero.display_name} {item.score:.1f}", ""]
    lines.append(f"  base: {item.breakdown.base:+.1f} [{item.breakdown.base_source}]")
    lines.append(f"  role: {item.breakdown.role:+.1f} [{item.breakdown.role_source}]")
    lines.append(f"  pos1 sample: {item.breakdown.pos1_matches}\n  pos1 confidence: {item.breakdown.position_confidence:.3f}")
    for enemy, score in item.breakdown.matchup_contributions:
        if score:
            lines.append(f"  vs {_display(enemy, heroes)}: {score:+.1f} [{dict(item.breakdown.matchup_sources).get(enemy, 'manual')}]")
    for ally, score in item.breakdown.synergy_contributions:
        if score:
            lines.append(f"  with {_display(ally, heroes)}: {score:+.1f} [{dict(item.breakdown.synergy_sources).get(ally, 'manual')}]")
    lines.append(f"  total: {item.breakdown.total:.1f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recommend Dota 2 hero picks from a manual draft.")
    parser.add_argument("draft", nargs="?", help="enemies | allies | role")
    parser.add_argument("--explain", action="store_true", help="show score reasons")
    parser.add_argument("--top", type=int, default=3, help="number of picks to show")
    parser.add_argument("--data", choices=("manual", "stats", "hybrid"), default="manual", help="manual, generated-only stats, or hybrid local scoring")
    parser.add_argument("--validate-data", action="store_true", help="validate local data files")
    parser.add_argument("--sync-stats", action="store_true", help="fetch a local STRATZ snapshot")
    parser.add_argument("--stats-role", choices=("carry", "mid", "offlane", "support", "hard_support"), default="carry", help="role-specific STRATZ statistics (default: carry)")
    parser.add_argument("--sync-dotabuff", action="store_true", help="fetch a local DOTABUFF counter snapshot")
    parser.add_argument("--sync-opendota", action="store_true", help="fetch a local OpenDota Herald/Guardian meta snapshot")
    parser.add_argument("--window", choices=("week", "month", "year"), default="month", help="DOTABUFF time window (default: month)")
    args = parser.parse_args(argv)
    try:
        heroes, matchups, synergies = load_data()
        aliases = build_aliases(heroes)
        validate_aliases(aliases, set(heroes))
        item_aliases=build_item_aliases(); edges=validate_graph()
        if args.validate_data:
            print(f"Data OK\nHeroes: {len(heroes)}\nAliases: {len(aliases)}\nItems: {len(ITEMS)}\nRecommendable items: {sum(x.recommendable for x in ITEMS.values())}\nItem aliases: {len(item_aliases)}\nUpgrade edges: {len(edges)}\nMatchups: {sum(len(values) for values in matchups.values())}\nSynergies: {len(synergies)}")
            return 0
        if args.sync_stats:
            from .data_sources.stratz import build_sync_plan, sync
            from .heroes import DATA_DIR
            plan = build_sync_plan(args.stats_role, heroes, DATA_DIR / "hero_id_map.json")
            print(f"Sync plan:\nRole: {plan.role}\nMeta requests: {plan.meta_requests}\nPair candidates: {len(plan.pair_hero_ids)}\nExpected API requests: {plan.expected_requests}")
            snapshot = sync(args.stats_role, DATA_DIR / "generated" / "snapshot.json", heroes, DATA_DIR / "hero_id_map.json")
            print(f"Snapshot written: data/generated/snapshot.json\nHeroes: {len(snapshot['meta'])}\nMatchups: {len(snapshot['matchups'])}\nSynergies: {len(snapshot['synergies'])}")
            return 0
        if args.sync_dotabuff:
            from .data_sources.dotabuff import role_candidates, sync
            from .heroes import DATA_DIR
            candidates = role_candidates(args.stats_role, heroes)
            print(f"DOTABUFF sync\nRole: {args.stats_role}\nWindow: {args.window}\nHeroes: {len(candidates)}\nExpected requests: {len(candidates)}")
            snapshot = sync(args.stats_role, args.window, DATA_DIR / "generated" / "dotabuff_snapshot.json", heroes)
            print(f"Snapshot written: data/generated/dotabuff_snapshot.json\nMatchups: {len(snapshot['matchups'])}")
            return 0
        if args.sync_opendota:
            from .data_sources.opendota import sync
            from .heroes import DATA_DIR
            snapshot = sync(DATA_DIR / "generated" / "opendota_snapshot.json", heroes, DATA_DIR / "hero_id_map.json")
            print(f"Snapshot written: data/generated/opendota_snapshot.json\nHeroes: {len(snapshot['meta'])}\nUnmapped OpenDota hero IDs: {len(snapshot['metadata']['unmapped_hero_ids'])}\nMissing mapped hero IDs: {len(snapshot['metadata']['missing_mapped_hero_ids'])}")
            return 0
        if not args.draft or args.top < 1:
            parser.error("Provide a draft and a positive --top value")
        choices = recommend(parse_draft(args.draft, heroes), args.top, args.data)
    except (DotabuffError, OpenDotaError, StratzError, ValueError) as error:
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
