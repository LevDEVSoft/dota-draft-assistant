from dataclasses import dataclass
@dataclass(frozen=True)
class InventoryState:
 hero_id:str; position:int; owned_items:tuple[str,...]=(); allied_items:tuple[str,...]=(); enemy_items:tuple[str,...]=(); minute:float=0; gold:int=0
 def __post_init__(self):
  if self.minute<0 or self.gold<0: raise ValueError("Minute and gold must be non-negative")
