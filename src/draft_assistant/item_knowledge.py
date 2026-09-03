"""Canonical local item definitions for role-aware scoring."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Item:
    item_id:str; display_name:str; cost:int; category:str; tags:frozenset[str]; compatible:frozenset[str]; situational:bool=False

def item(item_id,name,cost,category,tags,compatible,situational=False): return Item(item_id,name,cost,category,frozenset(tags),frozenset(compatible),situational)

ITEMS={x.item_id:x for x in (
 item("silver_edge","Silver Edge",5450,"offense",("Break","anti_passive","mobility","right_click"),("carry","mid","right_click core","scaling core"),True),
 item("spirit_vessel","Spirit Vessel",2780,"utility",("anti_heal","anti_regen","sustain"),("support","offlane","utility core","caster core"),True),
 item("monkey_king_bar","Monkey King Bar",4700,"offense",("accuracy","anti_evasion","right_click"),("carry","mid","right_click core","scaling core"),True),
 item("pipe","Pipe of Insight",3725,"team",("magic_mitigation","team_aura","save"),("offlane","support","aura carrier","frontliner","utility core")),
 item("crimson_guard","Crimson Guard",3850,"team",("physical_mitigation","anti_summon","team_aura","frontline"),("offlane","aura carrier","frontliner")),
 item("lotus_orb","Lotus Orb",3850,"utility",("dispel","armor","spell_block","save"),("offlane","support","utility core","frontliner"),True),
 item("linkens_sphere","Linken's Sphere",4800,"defense",("spell_block","mobility","sustain"),("carry","mid","scaling core"),True),
 item("nullifier","Nullifier",4375,"offense",("offensive_dispel","right_click"),("carry","mid","right_click core"),True),
 item("black_king_bar","Black King Bar",4050,"defense",("spell_immunity","magic_mitigation"),("carry","mid","offlane","right_click core","initiator")),
 item("shivas_guard","Shiva's Guard",5175,"team",("armor","anti_heal","anti_regen","physical_mitigation","teamfight"),("offlane","mid","frontliner","utility core"),True),
 item("blink_dagger","Blink Dagger",2250,"utility",("mobility","initiation"),("mid","offlane","initiator","frontliner")),
 item("assault_cuirass","Assault Cuirass",5125,"team",("armor","physical_mitigation","team_aura","attack_speed"),("carry","offlane","frontliner","aura carrier")),
 item("heavens_halberd","Heaven's Halberd",3500,"defense",("physical_mitigation","evasion","sustain"),("offlane","frontliner","utility core"),True),
 item("butterfly","Butterfly",5450,"offense",("attack_speed","right_click","evasion"),("carry","right_click core","scaling core")),
 item("bloodthorn","Bloodthorn",6800,"offense",("accuracy","anti_evasion","silence","burst"),("carry","mid","right_click core"),True),
 item("scythe_of_vyse","Scythe of Vyse",5200,"utility",("disable","catch"),("mid","support","caster core"),True),
 item("aghanims_scepter","Aghanim's Scepter",4200,"upgrade",("burst","utility"),("carry","mid","offlane","support","caster core"),True),
 item("aghanims_shard","Aghanim's Shard",1400,"upgrade",("utility",),("carry","mid","offlane","support","caster core"),True),
)}

COUNTERS={"passive_dependence":{"Break","anti_passive"},"healing_regeneration":{"anti_heal","anti_regen"},"evasion":{"accuracy","anti_evasion"},"magical_damage":{"magic_mitigation","spell_immunity"},"burst":{"spell_immunity","save"},"physical_damage":{"armor","physical_mitigation"},"summons":{"anti_summon","physical_mitigation"},"illusions":{"anti_illusion","teamfight"}}
NEEDS={"initiation":{"initiation","mobility"},"frontline":{"frontline","physical_mitigation"},"save":{"save","dispel"},"catch":{"catch","disable"},"waveclear":{"teamfight"},"anti_heal":{"anti_heal"},"Break":{"Break","anti_passive"}}
