"""Deterministic first-pass local item scoring."""
from dataclasses import dataclass
from .item_knowledge import ITEMS, COUNTERS, NEEDS

@dataclass(frozen=True)
class ItemScore:
 item_id:str; matchup:float; team_need:float; role_fit:float; redundancy:float; poor_fit:float; reasons:tuple[str,...]
 @property
 def total(self): return self.matchup+self.team_need+self.role_fit-self.redundancy-self.poor_fit

def score_items(model, profile, inventory):
 out=[]
 role={1:"carry",2:"mid",3:"offlane",4:"support",5:"support"}[inventory.position]
 signals={role,*profile.archetypes}
 if profile.initiation: signals.add("initiator")
 if profile.frontline: signals.add("frontliner")
 if profile.damage: signals.add("right_click core")
 for spec in ITEMS.values():
  if spec.item_id in inventory.owned_items: continue
  matchup=sum(1.6 for t in model.threats if spec.tags & COUNTERS.get(t,set()))
  need=sum(1.3 for n in model.needs if spec.tags & NEEDS.get(n,set()))
  fit=1.5 if spec.compatible & signals else 0
  poor=1.3 if not fit and spec.category in {"offense","team"} else 0
  redundant=2.0 if spec.item_id in inventory.allied_items and ("team_aura" in spec.tags or "Break" in spec.tags) else 0
  reasons=tuple(x for x in (("matchup" if matchup else ""),("team need" if need else ""),("role fit" if fit else ""),("redundant" if redundant else ""),("poor fit" if poor else "")) if x)
  out.append(ItemScore(spec.item_id,matchup,need,fit,redundant,poor,reasons))
 return sorted(out,key=lambda x:(-x.total,x.item_id))
