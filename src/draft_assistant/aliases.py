"""Alias normalization for concise CLI draft input."""

import re

ALIASES = {
    "sf": "shadow_fiend", "сф": "shadow_fiend", "shadow fiend": "shadow_fiend",
    "ds": "dark_seer",
    "bara": "spirit_breaker", "sb": "spirit_breaker", "spirit breaker": "spirit_breaker",
    "ls": "lifestealer", "naix": "lifestealer", "life stealer": "lifestealer",
    "wd": "witch_doctor", "witch doctor": "witch_doctor",
    "jugg": "juggernaut", "am": "anti_mage", "anti mage": "anti_mage",
    "wk": "wraith_king", "wraith king": "wraith_king", "spec": "spectre",
    "pa": "phantom_assassin", "phantom assassin": "phantom_assassin",
    "qop": "queen_of_pain", "queen of pain": "queen_of_pain",
    "potm": "mirana", "ogre": "ogre_magi", "ogre magi": "ogre_magi",
    "underlord": "underlord", "jakiro": "jakiro", "silencer": "silencer",
    "medusa": "medusa", "chaos knight": "chaos_knight", "ck": "chaos_knight",
    "terrorblade": "terrorblade", "tb": "terrorblade", "np": "natures_prophet", "furion": "natures_prophet", "natures prophet": "natures_prophet", "kotl": "keeper_of_the_light", "bh": "bounty_hunter", "bs": "bloodseeker", "cm": "crystal_maiden", "dp": "death_prophet", "drow": "drow_ranger", "dk": "dragon_knight", "es": "earthshaker", "ember": "ember_spirit", "fv": "faceless_void", "gyro": "gyrocopter", "lesh": "leshrac", "mk": "monkey_king", "morph": "morphling", "necro": "necrophos", "od": "outworld_destroyer", "pango": "pangolier", "sd": "shadow_demon", "sky": "skywrath_mage", "ta": "templar_assassin", "tide": "tidehunter", "treant": "treant_protector", "troll": "troll_warlord", "tusk": "tusk", "ursa": "ursa", "veno": "venomancer", "viper": "viper", "wr": "windranger", "windrunner": "windranger", "ww": "winter_wyvern", "zeus": "zeus", "ringmaster": "ringmaster", "ring master": "ringmaster", "rm": "ringmaster", "largo": "largo", "kez": "kez",
}

ALIASES.update({"вк":"wraith_king","ns":"night_stalker","нс":"night_stalker","zombie":"undying","зомби":"undying","найкс":"lifestealer","лс":"lifestealer","бара":"spirit_breaker","jug":"juggernaut","pl":"phantom_lancer","пл":"phantom_lancer","спектра":"spectre","спектр":"spectre","вд":"witch_doctor","цм":"crystal_maiden","вокер":"invoker","voker":"invoker","bb":"bristleback","bristle":"bristleback","shaker":"earthshaker","timber":"timbersaw","storm":"storm_spirit","willow":"dark_willow","dw":"dark_willow","db":"dawnbreaker","snap":"snapfire","primal":"primal_beast","alch":"alchemist","aa":"ancient_apparition","arc":"arc_warden","cent":"centaur_warrunner","clock":"clockwerk","et":"elder_titan","lc":"legion_commander","ld":"lone_druid","nyx":"nyx_assassin","sk":"sand_king","venge":"vengeful_spirit"})


def normalize_key(value: str) -> str:
    return " ".join(re.sub(r"[-_']", " ", value.casefold()).split())


def build_aliases(heroes: dict) -> dict[str, str]:
    aliases = {}
    for alias, hero_id in ALIASES.items():
        key = normalize_key(alias)
        if key in aliases and aliases[key] != hero_id:
            raise ValueError(f"Alias collision: {alias}")
        aliases[key] = hero_id
    for hero in heroes.values():
        for name in (hero.id, hero.display_name):
            key = normalize_key(name)
            if key in aliases and aliases[key] != hero.id:
                raise ValueError(f"Alias collision: {name}")
            aliases[key] = hero.id
    return aliases


def normalize_hero(value: str, known_heroes: set[str], aliases: dict[str, str] | None = None) -> str:
    """Return a canonical hero id or raise a concise validation error."""
    key = normalize_key(value)
    registry = aliases or {normalize_key(alias): hero for alias, hero in ALIASES.items()}
    canonical = registry.get(key, key.replace(" ", "_"))
    if canonical not in known_heroes:
        raise ValueError(f"Unknown hero: {value}")
    return canonical
