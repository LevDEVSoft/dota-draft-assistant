"""Alias normalization for concise CLI draft input."""

ALIASES = {
    "sf": "shadow_fiend", "сф": "shadow_fiend", "shadow fiend": "shadow_fiend",
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
    "terrorblade": "terrorblade", "tb": "terrorblade",
}


def normalize_hero(value: str, known_heroes: set[str]) -> str:
    """Return a canonical hero id or raise a concise validation error."""
    key = " ".join(value.strip().casefold().replace("_", " ").split())
    canonical = ALIASES.get(key, key.replace(" ", "_"))
    if canonical not in known_heroes:
        raise ValueError(f"Unknown hero: {value}")
    return canonical
