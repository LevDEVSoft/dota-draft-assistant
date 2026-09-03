"""GUI-independent draft state controller."""
from draft_assistant.aliases import build_aliases, normalize_hero
from draft_assistant.heroes import load_data
from draft_assistant.models import Draft
from draft_assistant.scoring import recommend
from draft_assistant.match_analysis import analyze, infer_roles, override_role

class DraftState:
    def __init__(self):
        self.heroes = load_data()[0]; self.aliases = build_aliases(self.heroes)
        self.enemies=[]; self.allies=[]; self.detected_enemies=[]; self.detected_allies=[]; self.suppressed_detected=set(); self.role="carry"; self.mode="hybrid"; self.top=5; self.selected=None
        self.role_assignments=(); self.analysis=None
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
    def clear(self): self.enemies.clear(); self.allies.clear(); self.selected=None; self.role_assignments=(); self.analysis=None
    def draft(self): return Draft(self.side_heroes("enemy"), self.side_heroes("ally"), self.role)
    def recommendations(self): return recommend(self.draft(),self.top,self.mode)
    def suggestions(self, text):
        key=text.casefold(); return [h.display_name for h in self.heroes.values() if key in h.display_name.casefold()][:8]
