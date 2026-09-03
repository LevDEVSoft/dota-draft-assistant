from dataclasses import dataclass
@dataclass(frozen=True)
class InventoryState:
 hero_id:str; position:int; owned_items:tuple[str,...]=(); allied_items:tuple[str,...]=(); enemy_items:tuple[str,...]=()
