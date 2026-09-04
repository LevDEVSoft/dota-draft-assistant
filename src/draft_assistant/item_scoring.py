"""Deterministic first-pass local item scoring."""
from dataclasses import dataclass
from .item_knowledge import ITEMS, COUNTERS, NEEDS
from .item_graph import remaining_cost
from dataclasses import replace

TIMING_MAX=2.0
EARLY_MINUTE=12
LATE_MINUTE=35

@dataclass(frozen=True)
class ItemScore:
 item_id:str; base:float; matchup:float; team_need:float; role_fit:float; redundancy:float; poor_fit:float; timing:float; full_cost:int; component_credit:int; remaining_cost:int; gold:int; gold_still_needed:int; reasons:tuple[str,...]
 @property
 def total(self): return self.base+self.matchup+self.team_need+self.role_fit-self.redundancy-self.poor_fit+self.timing

def timing_score(remaining,gold,minute):
 """Bounded affordability: gold coverage, with late-game greed tolerance."""
 coverage=min(1.0,gold/max(remaining,1)); phase=.55 if minute<EARLY_MINUTE else (.8 if minute<LATE_MINUTE else 1.0)
 return round(TIMING_MAX*(coverage-phase),3)

def score_items(model, profile, inventory):
 out=[]
 role={1:"carry",2:"mid",3:"offlane",4:"support",5:"support"}[inventory.position]
 signals={role,*profile.archetypes}
 if profile.initiation: signals.add("initiator")
 if profile.frontline: signals.add("frontliner")
 if profile.damage: signals.add("right_click core")
 for spec in ITEMS.values():
  if not spec.recommendable or spec.item_id in inventory.owned_items: continue
  matchup=sum(1.6 for t in model.threats if spec.tags & COUNTERS.get(t,set()))
  need=sum(1.3 for n in model.needs if spec.tags & NEEDS.get(n,set()))
  fit=1.5 if spec.compatible & signals else 0
  poor=1.3 if not fit and spec.category in {"offense","team"} else 0
  redundant=2.0 if spec.item_id in inventory.allied_items and ("team_aura" in spec.tags or "Break" in spec.tags) else 0
  remaining=remaining_cost(spec.item_id,inventory.owned_items); credit=spec.cost-remaining; timing=timing_score(remaining,inventory.gold,inventory.minute)
  reasons=tuple(x for x in (("matchup" if matchup else ""),("team need" if need else ""),("role fit" if fit else ""),("redundant" if redundant else ""),("poor fit" if poor else "")) if x)
  out.append(ItemScore(spec.item_id,0.0,matchup,need,fit,redundant,poor,timing,spec.cost,credit,remaining,inventory.gold,max(0,remaining-inventory.gold),reasons))
 return sorted(out,key=lambda x:(-x.total,x.item_id))

def recommend_next_items(model,profile,inventory,limit=3): return score_items(model,profile,inventory)[:limit]
def recommend_then_items(model,profile,inventory,limit=3):
 next_items=recommend_next_items(model,profile,inventory,1)
 if not next_items: return []
 future=replace(inventory,owned_items=(*inventory.owned_items,next_items[0].item_id))
 return score_items(model,profile,future)[:limit]
