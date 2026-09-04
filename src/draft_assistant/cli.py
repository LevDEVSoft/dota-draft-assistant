"""Command line interface for draft recommendations."""

import argparse

from .aliases import build_aliases
from .data_sources.dotabuff import DotabuffError
from .data_sources.opendota import OpenDotaError
from .data_sources.stratz import StratzError
from .heroes import DATA_DIR, load_data, parse_draft
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
    lines.append(f"  {item.breakdown.position_label} sample: {item.breakdown.pos1_matches}\n  {item.breakdown.position_label} confidence: {item.breakdown.position_confidence:.3f}")
    for enemy, score in item.breakdown.matchup_contributions:
        source = dict(item.breakdown.matchup_sources).get(enemy, "unavailable")
        if source.startswith("unavailable"):
            suffix = " for selected role" if source == "unavailable-role" else ""
            lines.append(f"  vs {_display(enemy, heroes)}: data unavailable{suffix}")
        else:
            lines.append(f"  vs {_display(enemy, heroes)}: {score:+.1f} [{source}]")
    for ally, score in item.breakdown.synergy_contributions:
        source = dict(item.breakdown.synergy_sources).get(ally, "unavailable")
        if source.startswith("unavailable"):
            suffix = " for selected role" if source == "unavailable-role" else ""
            lines.append(f"  with {_display(ally, heroes)}: data unavailable{suffix}")
        else:
            lines.append(f"  with {_display(ally, heroes)}: {score:+.1f} [{source}]")
    lines.append(f"  total: {item.breakdown.total:.1f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recommend Dota 2 hero picks from a manual draft.")
    parser.add_argument("draft", nargs="?", help="enemies | allies | role")
    parser.add_argument("--explain", action="store_true", help="show score reasons")
    parser.add_argument("--top", type=int, default=3, help="number of picks to show")
    parser.add_argument("--data", choices=("manual", "stats", "hybrid"), default="manual", help="manual, generated-only stats, or hybrid local scoring")
    parser.add_argument("--heroes", choices=("all", "prefer", "only"), default="all", help="all heroes, prefer personal pool, or personal pool only")
    parser.add_argument("--validate-data", action="store_true", help="validate local data files")
    parser.add_argument("--sync-stats", action="store_true", help="fetch a local STRATZ snapshot")
    parser.add_argument("--bracket", choices=("HERALD_GUARDIAN",), default="HERALD_GUARDIAN", help="STRATZ rank bracket")
    parser.add_argument("--stats-role", choices=("carry", "mid", "offlane", "support", "hard_support"), help="deprecated; STRATZ sync always captures all roles")
    parser.add_argument("--sync-dotabuff", action="store_true", help="fetch a local DOTABUFF counter snapshot")
    parser.add_argument("--sync-opendota", action="store_true", help="fetch a local OpenDota Herald/Guardian meta snapshot")
    parser.add_argument("--window", choices=("week", "month", "year"), default="month", help="DOTABUFF time window (default: month)")
    parser.add_argument("--profile-status", action="store_true", help="show linked Steam profile status")
    parser.add_argument("--profile-probe", action="store_true", help="run the small read-only STRATZ probe for the linked Steam profile")
    parser.add_argument("--personal-stats", action="store_true", help="fetch and summarize linked personal match history")
    parser.add_argument("--hero-pool", action="store_true", help="print the linked personal hero pool")
    parser.add_argument("--matches", type=int, default=100, choices=(25,50,100,250), help="personal history window")
    args = parser.parse_args(argv)
    try:
        heroes, matchups, synergies = load_data()
        aliases = build_aliases(heroes)
        validate_aliases(aliases, set(heroes))
        item_aliases=build_item_aliases(); edges=validate_graph()
        if args.validate_data:
            print(f"Data OK\nHeroes: {len(heroes)}\nAliases: {len(aliases)}\nItems: {len(ITEMS)}\nRecommendable items: {sum(x.recommendable for x in ITEMS.values())}\nItem aliases: {len(item_aliases)}\nUpgrade edges: {len(edges)}\nMatchups: {sum(len(values) for values in matchups.values())}\nSynergies: {len(synergies)}")
            return 0
        if args.draft == "steam-login":
            from .auth.steam_openid import login
            from .profile.profile_state import default_store
            from .data_sources.stratz import probe_player_access
            profile = default_store().save(login().steam_id64)
            probe = probe_player_access(profile.steam_id64)
            print(f"Steam connected: {profile.steam_id64}\nSTRATZ player account ID: {probe.steam_account_id}\nSTRATZ player: {'available' if probe.player_available else 'unavailable'}\nMatch query accepted: {'YES' if probe.match_query_accepted else 'NO'}\nRecent matches: {'available' if probe.recent_matches_available else 'zero returned'}\nVisible recent match count: {probe.visible_match_count}\nAggregate match count: {probe.total_match_count}\nExplicit privacy/permission error: {'YES' if probe.explicit_privacy_error else 'NO'}\nPrivate-history access: {probe.private_history_access}" + (f"\nReason: {probe.reason}" if probe.reason else ""))
            return 0
        if args.profile_status:
            from .profile.profile_state import default_store
            profile = default_store().load()
            print(f"Steam profile: {profile.steam_id64 if profile else 'not connected'}")
            return 0
        if args.profile_probe:
            from .profile.profile_state import default_store
            from .data_sources.stratz import probe_player_access
            profile = default_store().load()
            if not profile: raise ValueError("No linked Steam profile")
            probe = probe_player_access(profile.steam_id64)
            print(f"SteamID64: {profile.steam_id64}\nSTRATZ player account ID: {probe.steam_account_id}\nPlayer resolved: {'YES' if probe.player_available else 'NO'}\nMatch query accepted: {'YES' if probe.match_query_accepted else 'NO'}\nMatch nodes returned: {probe.visible_match_count}\nAggregate match count: {probe.total_match_count}\nExplicit privacy/permission error: {'YES' if probe.explicit_privacy_error else 'NO'}\nPrivate-history access: {probe.private_history_access}" + (f"\nCause: {probe.reason}" if probe.reason else ""))
            return 0
        if args.personal_stats or args.hero_pool:
            from .profile.profile_state import default_store
            from .personal_history import analyze_pool, fetch_history, save_cache
            profile=default_store().load()
            if not profile: raise ValueError("No linked Steam profile")
            history=fetch_history(profile.steam_id64, DATA_DIR / "hero_id_map.json", args.matches)
            save_cache(DATA_DIR / "generated" / "personal_history.json", history); pool=analyze_pool(history)
            print(f"PERSONAL HERO POOL — LAST {args.matches} MATCHES\nVisible standard matches: {pool['matches']}\nRole distribution: {pool['role_distribution']}\nUnknown roles: {pool['unknown_roles']}")
            for row in pool["heroes"][:15]: print(f"{row['hero_id']:<22} {row['games']:>3} games {row['winrate']:.1%} {row['tier'] or ''}")
            return 0
        if args.sync_stats:
            from .data_sources.stratz import build_sync_plan, sync
            plan = build_sync_plan(heroes, DATA_DIR / "hero_id_map.json")
            print(f"Sync plan:\nBracket: {args.bracket}\nRoles: all\nMeta requests: {plan.meta_requests}\nPair candidates: {len(plan.pair_hero_ids)}\nExpected API requests: {plan.expected_requests}")
            snapshot = sync(DATA_DIR / "generated" / "snapshot.json", heroes, DATA_DIR / "hero_id_map.json", args.bracket)
            role_counts = ", ".join(f"{role}={len(values['meta'])}" for role, values in snapshot["brackets"][args.bracket]["roles"].items())
            pairs = snapshot["brackets"][args.bracket]["pairs"]
            print(f"Snapshot written: data/generated/snapshot.json\nRole hero counts: {role_counts}\nMatchups: {len(pairs['matchups'])}\nSynergies: {len(pairs['synergies'])}")
            return 0
        if args.sync_dotabuff:
            from .data_sources.dotabuff import role_candidates, sync
            candidates = role_candidates(args.stats_role, heroes)
            print(f"DOTABUFF sync\nRole: {args.stats_role}\nWindow: {args.window}\nHeroes: {len(candidates)}\nExpected requests: {len(candidates)}")
            snapshot = sync(args.stats_role, args.window, DATA_DIR / "generated" / "dotabuff_snapshot.json", heroes)
            print(f"Snapshot written: data/generated/dotabuff_snapshot.json\nMatchups: {len(snapshot['matchups'])}")
            return 0
        if args.sync_opendota:
            from .data_sources.opendota import sync
            snapshot = sync(DATA_DIR / "generated" / "opendota_snapshot.json", heroes, DATA_DIR / "hero_id_map.json")
            print(f"Snapshot written: data/generated/opendota_snapshot.json\nHeroes: {len(snapshot['meta'])}\nUnmapped OpenDota hero IDs: {len(snapshot['metadata']['unmapped_hero_ids'])}\nMissing mapped hero IDs: {len(snapshot['metadata']['missing_mapped_hero_ids'])}")
            return 0
        if not args.draft or args.top < 1:
            parser.error("Provide a draft and a positive --top value")
        choices = recommend(parse_draft(args.draft, heroes), args.top, args.data, args.heroes, args.bracket)
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
