from draft_assistant.heroes import load_data
from draft_assistant.inventory_state import InventoryState
from draft_assistant.item_scoring import score_items
from draft_assistant.match_analysis import analyze, role_profile

def scores(enemies, position=1, hero='lifestealer', allied_items=()):
 h=load_data()[0]; m=analyze((hero,),enemies,h); return {x.item_id:x for x in score_items(m,role_profile(hero,position),InventoryState(hero,position,allied_items=allied_items))}

def test_silver_edge_break_and_core_fit():
 core=scores(('bristleback',),1); off=scores(('bristleback',),3,'underlord')
 assert core['silver_edge'].matchup>0 and core['silver_edge'].total>off['silver_edge'].total

def test_pipe_magic_and_redundancy():
 base=scores(('zeus','witch_doctor'),3,'underlord'); duplicate=scores(('zeus','witch_doctor'),3,'underlord',('pipe',))
 assert base['pipe'].matchup>0 and duplicate['pipe'].total<base['pipe'].total

def test_counter_mechanics_and_owned_items():
 s=scores(('windranger','bristleback','phantom_lancer'),1)
 assert s['monkey_king_bar'].matchup>0 and s['silver_edge'].matchup>0 and s['crimson_guard'].matchup>0
 h=load_data()[0]; m=analyze(('lifestealer',),('zeus',),h); ids={x.item_id for x in score_items(m,role_profile('lifestealer',1),InventoryState('lifestealer',1,('black_king_bar',)))}
 assert 'black_king_bar' not in ids
