"""Small, explicit built-in mechanics relevant to item redundancy."""
HERO_MECHANICS={
 "lifestealer":frozenset(("debuff_immunity","magic_resistance","lifesteal")),
 "juggernaut":frozenset(("debuff_immunity","magic_resistance","crit")),
 "phantom_lancer":frozenset(("illusion_generation","escape")),
 "anti_mage":frozenset(("magic_resistance","mobility")),
 "riki":frozenset(("invisibility","mobility")),
 "slark":frozenset(("dispel","mobility")),
}
ITEM_MECHANICS={"spell_immunity":"debuff_immunity","magic_mitigation":"magic_resistance","spell_block":"spell_block","offensive_dispel":"offensive_dispel","anti_evasion":"anti_evasion","right_click":"right_click","attack_speed":"attack_speed","evasion":"evasion","silence":"silence","mobility":"mobility"}
def mechanic_fit(hero_id,item):
 built=HERO_MECHANICS.get(hero_id,frozenset()); provided={ITEM_MECHANICS[x] for x in item.tags if x in ITEM_MECHANICS}
 overlap=built & provided; bonus=1.0 if "illusion_generation" in built and "right_click" in provided else 0.0
 penalty=min(3.0,1.5*len(overlap))
 return round(bonus-penalty,2),tuple(sorted(overlap)),bonus
