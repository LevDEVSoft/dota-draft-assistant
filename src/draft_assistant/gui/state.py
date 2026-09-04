"""GUI-independent draft state controller."""
from draft_assistant.aliases import build_aliases, normalize_hero
from draft_assistant.heroes import load_data
from draft_assistant.models import Draft
from draft_assistant.scoring import recommend
from draft_assistant.match_analysis import analyze, infer_roles, override_role
from draft_assistant.inventory_state import InventoryState
from draft_assistant.item_scoring import score_items
from draft_assistant.item_knowledge import ITEMS

class DraftState:
    def __init__(self):
        self.heroes = load_data()[0]; self.aliases = build_aliases(self.heroes)
        self.enemies=[]; self.allies=[]; self.detected_enemies=[]; self.detected_allies=[]; self.suppressed_detected=set(); self.role="carry"; self.mode="hybrid"; self.pool_mode="all"; self.top=5; self.selected=None
        self.role_assignments=(); self.analysis=None
        self.selected_player=None; self.inventories={}
    def add(self, value, side):
        hero=normalize_hero(value,set(self.heroes),self.aliases)
        if hero in self.side_heroes("enemy") or hero in self.side_heroes("ally"): raise ValueError("Hero is already drafted")
        (self.enemies if side=="enemy" else self.allies).append(hero); self._sync_analysis(); return hero
    def remove(self, hero):
        for team in (self.enemies,self.allies):
            if hero in team: team.remove(hero)
        if hero in self.detected_enemies or hero in self.detected_allies: self.suppressed_detected.add(hero)
        self._sync_analysis()
    def side_heroes(self, side):
        manual = self.enemies if side == "enemy" else self.allies
        detected = self.detected_enemies if side == "enemy" else self.detected_allies
        return tuple(dict.fromkeys([*manual, *(hero for hero in detected if hero not in self.suppressed_detected)]))
    def apply_detected_picks(self, allies, enemies):
        allies, enemies = list(dict.fromkeys(allies)), list(dict.fromkeys(enemies))
        if not set(allies + enemies).issubset(self.heroes): raise ValueError("Detector returned an unknown hero")
        changed = (allies, enemies) != (self.detected_allies, self.detected_enemies)
        self.detected_allies, self.detected_enemies = allies, enemies
        self.suppressed_detected.intersection_update(allies + enemies)
        self._sync_analysis()
        return changed
    def set_position(self, hero_id, position):
        self.role_assignments = override_role(self.role_assignments, hero_id, position); self._sync_analysis()
    def _sync_analysis(self):
        allies, enemies = self.side_heroes("ally"), self.side_heroes("enemy")
        inferred = infer_roles(allies, self.heroes)
        for assignment in self.role_assignments:
            if assignment.manual and assignment.hero_id in allies: inferred = override_role(inferred, assignment.hero_id, assignment.position)
        self.role_assignments = inferred
        self.analysis = analyze(allies, enemies, self.heroes, inferred) if allies or enemies else None
        self.inventories={hero:items for hero,items in self.inventories.items() if hero in allies}
        if self.selected_player not in allies: self.selected_player=allies[0] if allies else None
    def select_player(self, hero_id):
        if hero_id not in self.side_heroes("ally"): raise ValueError("Select an allied hero")
        self.selected_player=hero_id
    def add_item(self, item_id):
        if item_id not in ITEMS: raise ValueError("Unknown item")
        if not self.selected_player: raise ValueError("Select an allied hero")
        items=self.inventories.setdefault(self.selected_player,[])
        if item_id not in items: items.append(item_id)
    def remove_item(self,item_id):
        if self.selected_player and item_id in self.inventories.get(self.selected_player,[]): self.inventories[self.selected_player].remove(item_id)
    def item_scores(self):
        if not self.selected_player or not self.analysis: return []
        assignment=next(x for x in self.role_assignments if x.hero_id==self.selected_player); profile=next(x for x in self.analysis.allied_profiles if x.hero_id==self.selected_player)
        allied=tuple(item for hero,items in self.inventories.items() if hero!=self.selected_player for item in items)
        return score_items(self.analysis,profile,InventoryState(self.selected_player,assignment.position,tuple(self.inventories.get(self.selected_player,[])),allied))
    def clear(self): self.enemies.clear(); self.allies.clear(); self.selected=None; self.role_assignments=(); self.analysis=None; self.selected_player=None; self.inventories={}
    def draft(self): return Draft(self.side_heroes("enemy"), self.side_heroes("ally"), self.role)
    def recommendations(self): return recommend(self.draft(),self.top,self.mode,self.pool_mode)
    def suggestions(self, text):
        key=text.casefold(); return [h.display_name for h in self.heroes.values() if key in h.display_name.casefold()][:8]
