from draft_assistant.personal_history import PersonalMatch, analyze_pool, analyze_role_pools, normalize_matches

def test_normalizes_roles_wins_and_excludes_turbo():
    rows=[{"id":1,"startDateTime":10,"gameMode":"ALL_PICK","players":[{"steamAccountId":7,"heroId":1,"isVictory":True,"position":"POSITION_1"}]},{"id":2,"gameMode":"TURBO","players":[{"steamAccountId":7,"heroId":1,"isVictory":False,"position":None}]}]
    matches=normalize_matches(rows,7,{1:"axe"})
    assert matches == [PersonalMatch(1,10,"axe",True,"carry","ALL_PICK",None,None,None,None,None,False)]

def test_pool_tiers_are_deterministic_and_protect_tiny_samples():
    matches=[PersonalMatch(i,i,"axe",i%2==0,"offlane",None,None,None,None,None,None,False) for i in range(10)] + [PersonalMatch(20,20,"bane",True,"unknown",None,None,None,None,None,None,False)]
    pool=analyze_pool(matches)
    assert pool["tiers"]["MAIN"] == ["axe"]
    assert "bane" not in sum(pool["tiers"].values(),[])
    assert pool["unknown_roles"] == 1

def test_same_hero_has_role_specific_pool_tiers():
    matches=[PersonalMatch(i,i,"pudge",True,"support",None,None,None,None,None,None,False) for i in range(8)] + [PersonalMatch(20,20,"pudge",True,"carry",None,None,None,None,None,None,False)] + [PersonalMatch(30+i,30+i,"lifestealer",True,"carry",None,None,None,None,None,None,False) for i in range(4)]
    pools=analyze_role_pools(matches)
    assert pools["support"]["heroes"][0]["tier"] == "MAIN"
    assert pools["carry"]["heroes"][0]["hero_id"] == "lifestealer"
    assert "pudge" not in sum(pools["carry"]["tiers"].values(),[])
