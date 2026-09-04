"""Shared normalized resolver for fast item entry."""
import re
from .item_knowledge import ITEMS

ALIASES={"bkb":"black_king_bar","manta":"manta","sny":"sange_and_yasha","kns":"kaya_and_sange","mkb":"monkey_king_bar","ac":"assault_cuirass","skadi":"skadi","satanic":"satanic","hex":"sheepstick","orchid":"orchid","bloodthorn":"bloodthorn","nullifier":"nullifier","bf":"bfury","rad":"radiance","deso":"desolator","armlet":"armlet","echo":"echo_sabre","harpoon":"harpoon","basher":"basher","abyssal":"abyssal_blade","bm":"blade_mail","blademail":"blade_mail","shroud":"eternal_shroud","pipe":"pipe","crimson":"crimson_guard","greaves":"guardian_greaves","glimmer":"glimmer_cape","force":"force_staff","pike":"hurricane_pike","diffu":"diffusal_blade","disperser":"disperser","mael":"maelstrom","mjollnir":"mjollnir","gleipnir":"gungir","linkens":"sphere","lotus":"lotus_orb","heart":"heart","aghs":"ultimate_scepter","shard":"aghanims_shard","octarine":"octarine_core","refresher":"refresher","blink":"blink","treads":"power_treads","phase":"phase_boots","travels":"travel_boots"}
def key(value): return " ".join(re.sub(r"[-_']"," ",value.casefold()).split())
def build_aliases(items=ITEMS):
 out={}
 for alias,item_id in {**ALIASES,**{x.display_name:x.item_id for x in items.values()}}.items():
  normalized=key(alias)
  if normalized in out and out[normalized]!=item_id: raise ValueError(f"Item alias collision: {alias}")
  if item_id not in items: raise ValueError(f"Unknown item alias target: {item_id}")
  out[normalized]=item_id
 return out
def resolve(value,items=ITEMS):
 found=build_aliases(items).get(key(value),key(value).replace(" ","_"))
 if found not in items: raise ValueError(f"Unknown item: {value}")
 return found
