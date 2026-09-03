import pytest
from draft_assistant.gui.state import DraftState

def test_draft_state_add_alias_remove_clear_and_recommendations():
 s=DraftState(); assert s.add('sf','enemy')=='shadow_fiend'; assert s.add('wd','ally')=='witch_doctor'
 with pytest.raises(ValueError): s.add('sf','ally')
 assert s.suggestions('lif')==['Lifestealer']; s.remove('witch_doctor'); assert not s.allies
 s.role='carry'; s.mode='manual'; assert s.recommendations(); s.clear(); assert not s.enemies
