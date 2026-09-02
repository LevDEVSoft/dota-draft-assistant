# Dota Draft Assistant

A small, local command-line Dota 2 draft assistant. Enter partial drafts and your intended role to get the three highest-scoring legal picks. This MVP uses manual text input only: no screen recognition, web app, external API, or LLM.

## Setup

Requires Python 3.12 or later.

```powershell
py -3.12 -m pip install -e .
py -3.12 -m pytest
```

## Usage

```powershell
dota-pick "sf bara ogre silencer | underlord jakiro wd | carry"
dota-pick "sf bara ogre silencer | underlord jakiro wd | carry" --explain
dota-pick "sf bara ogre | jakiro wd | carry" --top 5
dota-pick --validate-data
```

Example output:

```text
1. Lifestealer   93.0
2. Juggernaut    86.0
3. Wraith King   78.0
```

Input uses `enemy heroes | allied heroes | role`. Hero names and aliases are case-insensitive; `sf`, `bara`, `wd`, and Russian `сф` work. Supported roles are `carry`, `mid`, `offlane`, `support`, and `hard_support`.

## Scoring

Each legal candidate receives:

```text
base + role suitability + matchup contributions + synergy contributions
```

Scores are arbitrary ranking points, not percentages, normalized values, or win probabilities. Positive matchups favor the candidate against that enemy; negative ones penalize it. Synergies are stored once per unordered pair and always apply equally in either direction. Current values are manually seeded MVP data, not statistically validated game data.

## Project structure

```text
src/draft_assistant/  CLI, parsing, models, and deterministic scoring
data/                 hero definitions, matchups, and synergies
tests/                pytest coverage for MVP behavior
```

## Statistical ingestion foundation

Runtime recommendations continue to use the local manual seed data and never need network access. Future provider adapters belong under `data_sources/`; the included offline importer turns raw JSON plus `data/hero_id_map.json` into a clearly separate generated snapshot. Synthetic fixtures are tests only, not game data.

`data/hero_id_map.json` contains the complete 127-hero Valve numeric-ID mapping, transcribed from SteamDatabase's Valve GameTracking-Dota2 [`npc_heroes.txt`](https://github.com/SteamDatabase/GameTracking-Dota2/blob/master/game/dota/pak01_dir/scripts/npc/npc_heroes.txt) constants. `dota-pick --sync-stats` is an explicit refresh command; it requires `STRATZ_API_TOKEN`, prints its bounded request plan, and writes `data/generated/snapshot.json`. It defaults to carry and accepts `--stats-role` for another supported role.
