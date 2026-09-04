from draft_assistant.heroes import load_data
from draft_assistant.inventory_state import InventoryState
from draft_assistant.item_scoring import recommend_next_items,recommend_then_items,timing_score
from draft_assistant.match_analysis import analyze,role_profile

def setup(gold=1800,minute=22,owned=('phase_boots','armlet')):
 h=load_data()[0]; m=analyze(('lifestealer',),('underlord','jakiro','shadow_fiend','witch_doctor','spectre'),h); i=InventoryState('lifestealer',1,owned,(),(),minute,gold); return m,role_profile('lifestealer',1),i
def test_economics_and_timing_are_exact():
 m,p,i=setup(); score=next(x for x in recommend_next_items(m,p,i,20) if x.item_id=='black_king_bar')
 assert score.gold_still_needed==max(0,score.remaining_cost-i.gold)
 assert score.total==score.base+score.matchup+score.team_need+score.role_fit-score.redundancy-score.poor_fit+score.timing
 assert timing_score(4000,500,8)!=timing_score(4000,5000,45)
def test_then_is_fresh_and_does_not_mutate_inventory():
 m,p,i=setup(); before=i.owned_items; first=recommend_next_items(m,p,i,3); then=recommend_then_items(m,p,i,3)
 assert i.owned_items==before and then and then[0].item_id!=first[0].item_id
def test_upgrade_cost_affects_timing():
 m,p,a=setup(500,22,()); _,_,b=setup(500,22,('maelstrom',));
 ma=next(x for x in recommend_next_items(m,p,a,200) if x.item_id=='mjollnir'); mb=next(x for x in recommend_next_items(m,p,b,200) if x.item_id=='mjollnir')
 assert mb.remaining_cost<ma.remaining_cost and mb.timing>ma.timing
