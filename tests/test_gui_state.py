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
