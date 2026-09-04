from draft_assistant.hero_mechanics import mechanic_fit
from draft_assistant.item_knowledge import ITEMS

def test_built_in_immunity_penalizes_bkb_but_not_every_carry():
 life=mechanic_fit('lifestealer',ITEMS['black_king_bar'])[0]
 normal=mechanic_fit('drow_ranger',ITEMS['black_king_bar'])[0]
 assert life<normal and life>=-3
def test_illusion_hero_has_complementarity_signal():
 assert mechanic_fit('phantom_lancer',ITEMS['butterfly'])[0]>0
