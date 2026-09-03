"""GUI-independent draft state controller."""
from draft_assistant.aliases import build_aliases, normalize_hero
from draft_assistant.heroes import load_data
from draft_assistant.models import Draft
from draft_assistant.scoring import recommend

class DraftState:
    def __init__(self):
        self.heroes = load_data()[0]; self.aliases = build_aliases(self.heroes)
        self.enemies=[]; self.allies=[]; self.role="carry"; self.mode="hybrid"; self.top=5; self.selected=None
    def add(self, value, side):
        hero=normalize_hero(value,set(self.heroes),self.aliases)
        if hero in self.enemies or hero in self.allies: raise ValueError("Hero is already drafted")
        (self.enemies if side=="enemy" else self.allies).append(hero); return hero
    def remove(self, hero):
        for team in (self.enemies,self.allies):
            if hero in team: team.remove(hero)
    def clear(self): self.enemies.clear(); self.allies.clear(); self.selected=None
    def draft(self): return Draft(tuple(self.enemies),tuple(self.allies),self.role)
    def recommendations(self): return recommend(self.draft(),self.top,self.mode)
    def suggestions(self, text):
        key=text.casefold(); return [h.display_name for h in self.heroes.values() if key in h.display_name.casefold()][:8]
