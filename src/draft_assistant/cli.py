"""Command line interface for draft recommendations."""

import argparse

from .heroes import load_data, parse_draft
from .scoring import recommend


def _display(hero_id: str, heroes: dict) -> str:
    return heroes[hero_id].display_name


def format_explanation(item, heroes: dict) -> str:
    lines = [f"{item.hero.display_name} {item.score:.1f}", ""]
    lines.append(f"- base rating: {item.hero.base_rating:+.1f}")
    lines.append(f"- role suitability: {item.role_score:+.1f}")
    for enemy, score in item.matchup_details:
        if score:
            lines.append(f"- matchup vs {_display(enemy, heroes)}: {score:+.1f}")
    for ally, score in item.synergy_details:
        if score:
            lines.append(f"- synergy with {_display(ally, heroes)}: {score:+.1f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recommend Dota 2 hero picks from a manual draft.")
    parser.add_argument("draft", help="enemies | allies | role")
    parser.add_argument("--explain", action="store_true", help="show score reasons")
    args = parser.parse_args(argv)
    try:
        heroes, _, _ = load_data()
        choices = recommend(parse_draft(args.draft, heroes))
    except ValueError as error:
        parser.error(str(error))
    if not choices:
        parser.error("No heroes available for this role")
    if args.explain:
        print("\n\n".join(format_explanation(item, heroes) for item in choices))
    else:
        for index, item in enumerate(choices, 1):
            print(f"{index}. {item.hero.display_name:<13} {item.score:.1f}")
    return 0


if __name__ == "__main__":
    main()
