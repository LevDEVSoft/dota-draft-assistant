"""Local role-aware draft interpretation; deliberately independent of Qt."""
from dataclasses import dataclass, replace

POSITIONS = (1, 2, 3, 4, 5)
ROLE_TO_POSITION = {"carry": 1, "mid": 2, "offlane": 3, "support": 4, "hard_support": 5}

@dataclass(frozen=True)
class RoleAssignment:
    hero_id: str; position: int; confidence: float; manual: bool = False

@dataclass(frozen=True)
class HeroRoleProfile:
    hero_id: str; position: int; farm_priority: int; archetypes: tuple[str, ...]; power: tuple[int, int, int, int, int]
    damage: int; initiation: int; frontline: int; catch: int; disable: int; save: int; sustain: int; waveclear: int; tower: int; teamfight: int; mobility: int; scaling: int; item_dependencies: tuple[str, ...]

HERO_TAGS = {
 "zeus": {"magic","burst","waveclear"}, "witch_doctor": {"magic","burst","disable"}, "bristleback": {"physical","passive","high_hp","frontline"}, "phantom_lancer": {"physical","illusions","scaling"}, "naga_siren": {"physical","illusions","scaling","waveclear"}, "broodmother": {"physical","summons","tower"}, "lycan": {"physical","summons","tower"}, "windranger": {"physical","evasion","mobility"}, "spectre": {"physical","scaling","high_hp"}, "lifestealer": {"physical","scaling","sustain"}, "anti_mage": {"physical","scaling","mobility"}, "medusa": {"physical","scaling","high_hp"}, "pudge": {"initiation","catch","frontline","disable"}, "underlord": {"frontline","waveclear","teamfight"}, "puck": {"initiation","catch","mobility","magic"}, "spirit_breaker": {"initiation","catch","physical"}, "shadow_fiend": {"physical","magic","waveclear"}, "dazzle": {"save","heal"}, "oracle": {"save","heal"}, "chen": {"save","summons"}, "slark": {"physical","scaling","mobility"}, "ancient_apparition": {"magic","anti_heal","disable"}, "silencer": {"magic","silence"}, "jakiro": {"magic","waveclear","disable","teamfight"},
}

def infer_roles(hero_ids, heroes):
    remaining = set(POSITIONS); result = []
    for hero_id in hero_ids:
        hero = heroes[hero_id]; choices = sorted((ROLE_TO_POSITION[r] for r in hero.roles if r in ROLE_TO_POSITION), key=lambda p: (p not in remaining, p))
        position = choices[0] if choices else min(remaining or set(POSITIONS)); confidence = .9 if position in remaining and len(choices) == 1 else .55
        remaining.discard(position); result.append(RoleAssignment(hero_id, position, confidence))
    return tuple(result)

def override_role(assignments, hero_id, position):
    if position not in POSITIONS: raise ValueError("Position must be 1 through 5")
    current = next(a for a in assignments if a.hero_id == hero_id)
    swapped = []
    for assignment in assignments:
        if assignment.hero_id == hero_id: swapped.append(replace(assignment, position=position, confidence=1.0, manual=True))
        elif assignment.position == position: swapped.append(replace(assignment, position=current.position, confidence=assignment.confidence, manual=assignment.manual))
        else: swapped.append(assignment)
    return tuple(swapped)

def role_profile(hero_id, position):
    tags = HERO_TAGS.get(hero_id, set()); core = position <= 3; scaling = 8 if "scaling" in tags else (6 if core else 3)
    archetypes = (("scaling core",) if scaling >= 7 else (("tempo core",) if core else ("utility support",)))
    if "initiation" in tags: archetypes += ("initiator",)
    if "frontline" in tags: archetypes += ("frontliner",)
    power = (6, 7 if core else 6, 7 if core else 5, scaling, scaling)
    if "scaling" in tags: power = (4, 5, 6, 8, 9)
    return HeroRoleProfile(hero_id, position, 6-position, archetypes, power, int("physical" in tags or "magic" in tags)*7, int("initiation" in tags)*8, int("frontline" in tags)*8, int("catch" in tags)*8, int("disable" in tags)*7, int("save" in tags)*8, int("sustain" in tags)*7, int("waveclear" in tags)*7, int("tower" in tags)*7, int("teamfight" in tags)*7, int("mobility" in tags)*7, scaling, tuple(x for x in ("blink" if "initiation" in tags else "", "major_scaling" if scaling >= 7 else "") if x))

@dataclass(frozen=True)
class MatchModel:
    allies: tuple[RoleAssignment, ...]; enemies: tuple[RoleAssignment, ...]; allied_profiles: tuple[HeroRoleProfile, ...]; enemy_profiles: tuple[HeroRoleProfile, ...]; allied_curve: tuple[float,...]; enemy_curve: tuple[float,...]; threats: tuple[str,...]; needs: tuple[str,...]; conclusions: tuple[str,...]

def analyze(allies, enemies, heroes, ally_roles=None, enemy_roles=None):
    ally_roles = tuple(ally_roles or infer_roles(allies, heroes)); enemy_roles = tuple(enemy_roles or infer_roles(enemies, heroes))
    ap, ep = tuple(role_profile(a.hero_id,a.position) for a in ally_roles), tuple(role_profile(a.hero_id,a.position) for a in enemy_roles)
    curve = lambda profiles: tuple(round(sum(p.power[i] for p in profiles)/max(1,len(profiles)),1) for i in range(5))
    tags = set().union(*(HERO_TAGS.get(x,set()) for x in enemies)) if enemies else set()
    threats = tuple(x for x in ("magical_damage" if "magic" in tags else "", "physical_damage" if "physical" in tags else "", "burst" if "burst" in tags else "", "healing_regeneration" if "heal" in tags else "", "passive_dependence" if "passive" in tags else "", "evasion" if "evasion" in tags else "", "illusions" if "illusions" in tags else "", "summons" if "summons" in tags else "") if x)
    needs = tuple(x for x, value in (("initiation",max((p.initiation for p in ap),default=0)),("frontline",max((p.frontline for p in ap),default=0)),("save",max((p.save for p in ap),default=0)),("catch",max((p.catch for p in ap),default=0)),("waveclear",max((p.waveclear for p in ap),default=0))) if value < 5) + tuple(x for x in ("anti_heal" if "healing_regeneration" in threats else "", "Break" if "passive_dependence" in threats else "") if x)
    ac, ec = curve(ap), curve(ep); conclusions = ("pressure" if max(range(5),key=lambda i:ac[i]) < 3 else "scale", "enemy_scales" if ec[-1] > ac[-1] else "allies_scale")
    return MatchModel(ally_roles,enemy_roles,ap,ep,ac,ec,threats,needs,conclusions)
