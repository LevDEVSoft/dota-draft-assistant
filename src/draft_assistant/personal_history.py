"""Read-only personal STRATZ history normalization and deterministic pool analysis."""
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from .data_sources.mapping import load_mapping
from .data_sources.stratz import execute

ROLE_MAP = {"POSITION_1":"carry", "POSITION_2":"mid", "POSITION_3":"offlane", "POSITION_4":"support", "POSITION_5":"hard_support"}
POOL_MAIN_GAMES, POOL_COMFORTABLE_GAMES, POOL_PLAYED_GAMES = 10, 5, 2
ROLE_MAIN_GAMES, ROLE_MAIN_SHARE, ROLE_COMFORTABLE_GAMES, ROLE_PLAYED_GAMES = 4, .20, 3, 2

@dataclass(frozen=True)
class PersonalMatch:
    match_id: int; timestamp: int | None; hero_id: str; win: bool; role: str
    game_mode: str | None; lobby_type: str | None; duration: int | None
    kills: int | None; deaths: int | None; assists: int | None; party: bool

def normalize_matches(rows, account_id: int, mapping: dict[int, str]) -> list[PersonalMatch]:
    results=[]
    for match in rows:
        player=next((p for p in match.get("players",[]) if p.get("steamAccountId")==account_id), None)
        if not player or player.get("heroId") not in mapping or match.get("gameMode") == "TURBO": continue
        results.append(PersonalMatch(match["id"],match.get("startDateTime"),mapping[player["heroId"]],bool(player.get("isVictory")),ROLE_MAP.get(player.get("position"),"unknown"),match.get("gameMode"),match.get("lobbyType"),match.get("durationSeconds"),player.get("kills"),player.get("deaths"),player.get("assists"),bool(player.get("partyId"))))
    return results

def fetch_history(steam_id64: str, mapping_path: Path, limit: int = 100, page_size: int = 25) -> list[PersonalMatch]:
    if limit < 1: return []
    account_id=int(steam_id64)-76561197960265728; mapping=load_mapping(mapping_path); rows=[]
    query="""query History($id:Long!,$take:Int!,$skip:Int!){player(steamAccountId:$id){matches(request:{take:$take skip:$skip playerList:SINGLE orderBy:DESC}){id startDateTime durationSeconds gameMode lobbyType players{steamAccountId heroId isVictory position kills deaths assists partyId}}}}"""
    for skip in range(0, limit, page_size):
        batch=execute(query,{"id":account_id,"take":min(page_size,limit-skip),"skip":skip}).get("player",{}).get("matches") or []
        rows.extend(batch)
        if len(batch)<min(page_size,limit-skip): break
    return normalize_matches(rows,account_id,mapping)

def analyze_pool(matches: list[PersonalMatch]) -> dict:
    heroes=defaultdict(list)
    for match in matches: heroes[match.hero_id].append(match)
    records=[]
    for hero_id, games in heroes.items():
        wins=sum(game.win for game in games); roles=Counter(game.role for game in games); count=len(games)
        tier="MAIN" if count>=POOL_MAIN_GAMES else "COMFORTABLE" if count>=POOL_COMFORTABLE_GAMES else "PLAYED" if count>=POOL_PLAYED_GAMES else None
        records.append({"hero_id":hero_id,"games":count,"wins":wins,"losses":count-wins,"winrate":wins/count,"roles":dict(roles),"most_played_role":roles.most_common(1)[0][0],"last_played":max((game.timestamp or 0) for game in games),"tier":tier})
    records.sort(key=lambda row:(-row["games"],row["hero_id"])); distribution=Counter(match.role for match in matches)
    return {"matches":len(matches),"role_distribution":dict(distribution),"heroes":records,"tiers":{tier:[row["hero_id"] for row in records if row["tier"]==tier] for tier in ("MAIN","COMFORTABLE","PLAYED")},"unknown_roles":distribution["unknown"]}

def analyze_role_pools(matches: list[PersonalMatch]) -> dict:
    """Separate recent pools: experience plus role-share, never win rate."""
    pools={}
    for role in ROLE_MAP.values():
        role_games=[match for match in matches if match.role==role]; total=len(role_games); by_hero=defaultdict(list)
        for match in role_games: by_hero[match.hero_id].append(match)
        heroes=[]
        for hero_id,games in by_hero.items():
            count=len(games); wins=sum(game.win for game in games); share=count/total if total else 0
            tier="MAIN" if count>=ROLE_MAIN_GAMES and share>=ROLE_MAIN_SHARE else "COMFORTABLE" if count>=ROLE_COMFORTABLE_GAMES else "PLAYED" if count>=ROLE_PLAYED_GAMES else None
            heroes.append({"hero_id":hero_id,"games":count,"wins":wins,"losses":count-wins,"winrate":wins/count,"share":share,"recent_games":count,"last_played":max(game.timestamp or 0 for game in games),"tier":tier})
        heroes.sort(key=lambda row:(-row["games"],row["hero_id"])); pools[role]={"total_games":total,"heroes":heroes,"tiers":{tier:[row["hero_id"] for row in heroes if row["tier"]==tier] for tier in ("MAIN","COMFORTABLE","PLAYED")}}
    return pools

def save_cache(path: Path, matches: list[PersonalMatch]):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps([asdict(match) for match in matches],indent=2)+"\n",encoding="utf-8")

def load_cache(path: Path) -> list[PersonalMatch]:
    return [PersonalMatch(**row) for row in json.loads(path.read_text(encoding="utf-8"))] if path.exists() else []
