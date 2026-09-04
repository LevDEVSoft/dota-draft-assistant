import pytest
from draft_assistant.item_aliases import build_aliases, resolve
from draft_assistant.item_graph import remaining_cost, upgrade_edges, validate_graph
from draft_assistant.item_knowledge import ITEMS

def test_aliases_normalize_and_unknown_is_clear():
 assert resolve('BKB')=='black_king_bar'; assert resolve('mael')=='maelstrom'
 with pytest.raises(ValueError): resolve('not an item')

def test_upgrade_edges_and_remaining_costs():
 edges=set(upgrade_edges()); assert ('basher','abyssal_blade') in edges and ('force_staff','hurricane_pike') in edges
 assert remaining_cost('abyssal_blade',('basher',))<ITEMS['abyssal_blade'].cost
 assert remaining_cost('mjollnir',('maelstrom',))<ITEMS['mjollnir'].cost
 assert remaining_cost('hurricane_pike',('force_staff','dragon_lance'))<remaining_cost('hurricane_pike',('force_staff',))
 assert remaining_cost('hurricane_pike',('basher',))==ITEMS['hurricane_pike'].cost

def test_graph_is_acyclic_and_aliases_are_collision_safe():
 assert validate_graph(); assert len(build_aliases())==len(set(build_aliases()))
