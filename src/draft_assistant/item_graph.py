"""Derived upgrade graph and deterministic component-aware remaining cost."""
from .item_knowledge import ITEMS

def upgrade_edges(items=ITEMS):
 return tuple(sorted((component,item_id) for item_id,item in items.items() for component in item.components if component in items))
def validate_graph(items=ITEMS):
 edges=upgrade_edges(items); graph={x:[] for x in items}
 for a,b in edges: graph[a].append(b)
 seen=set(); active=set()
 def visit(node):
  if node in active: raise ValueError("Circular item upgrade graph")
  if node not in seen:
   active.add(node); [visit(x) for x in graph[node]]; active.remove(node); seen.add(node)
 [visit(x) for x in graph]
 return edges
def remaining_cost(item_id,owned,items=ITEMS):
 item=items[item_id]; used=set()
 def value(target):
  if target in owned and target not in used: used.add(target); return items[target].cost
  return sum(value(component) for component in items[target].components if component in items)
 consumed=sum(value(component) for component in item.components if component in items)
 return max(0,item.cost-consumed)
