import pytest
from draft_assistant.gui.state import DraftState

def test_draft_state_add_alias_remove_clear_and_recommendations():
 s=DraftState(); assert s.add('sf','enemy')=='shadow_fiend'; assert s.add('wd','ally')=='witch_doctor'
 with pytest.raises(ValueError): s.add('sf','ally')
 assert s.suggestions('lif')==['Lifestealer']; s.remove('witch_doctor'); assert not s.allies
 s.role='carry'; s.mode='manual'; assert s.recommendations(); s.clear(); assert not s.enemies


@pytest.mark.parametrize("value", ["DS", "ds", "Dark Seer"])
def test_gui_state_accepts_dark_seer_aliases(value):
 s=DraftState()
 assert s.add(value, 'enemy') == 'dark_seer'


def test_draft_state_removes_hero_and_rejects_cross_team_duplicate():
 s=DraftState(); assert s.add('sf', 'enemy') == 'shadow_fiend'
 with pytest.raises(ValueError, match='already drafted'): s.add('sf', 'ally')
 s.remove('shadow_fiend'); assert not s.enemies


def test_role_state_swaps_manual_positions_and_clears_with_draft():
 s=DraftState(); s.add('pudge','ally'); s.add('ancient_apparition','ally'); s.add('witch_doctor','ally')
 s.set_position('pudge',2); s.set_position('ancient_apparition',1); s.set_position('witch_doctor',3)
 assert {a.position for a in s.role_assignments} == {1,2,3}
 assert next(a for a in s.role_assignments if a.hero_id=='pudge').manual
 s.remove('pudge'); assert all(a.hero_id!='pudge' for a in s.role_assignments)
 s.clear(); assert not s.role_assignments and s.analysis is None


def test_inventory_uses_confirmed_role_and_resets():
 s=DraftState(); s.add('lifestealer','ally'); s.select_player('lifestealer'); s.add_item('black_king_bar')
 assert 'black_king_bar' not in {x.item_id for x in s.item_scores()}
 s.remove_item('black_king_bar'); assert 'black_king_bar' in {x.item_id for x in s.item_scores()}
 s.clear(); assert s.selected_player is None and not s.inventories
