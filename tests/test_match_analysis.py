from draft_assistant.heroes import load_data
from draft_assistant.match_analysis import analyze, infer_roles, override_role, role_profile

def test_roles_infer_unique_and_manual_override_swaps():
 h=load_data()[0]; roles=infer_roles(("lifestealer","shadow_fiend","underlord","jakiro","ogre_magi"),h)
 assert len({x.position for x in roles})==5
 edited=override_role(roles,"underlord",2); assert next(x for x in edited if x.hero_id=="underlord").manual

def test_unusual_roles_and_profiles_are_valid_and_role_aware():
 assert role_profile("pudge",2)!=role_profile("pudge",4)
 assert role_profile("ancient_apparition",1).position==1

def test_threats_needs_and_scaling_analysis():
 h=load_data()[0]; model=analyze(("underlord","jakiro"),("bristleback","phantom_lancer","windranger"),h)
 assert {"passive_dependence","illusions","evasion"} <= set(model.threats)
 assert "Break" in model.needs
