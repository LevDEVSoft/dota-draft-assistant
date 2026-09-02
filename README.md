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
base_rating + sum(matchup scores versus enemies) + sum(synergy scores with allies) + role suitability
```

All values, including role suitability, live in JSON, making them easy to inspect and tune. Scores are arbitrary ranking points, not percentages and not normalized to 0–100. Current values are manually seeded MVP data, not statistically validated game data.

## Project structure

```text
src/draft_assistant/  CLI, parsing, models, and deterministic scoring
data/                 hero definitions, matchups, and synergies
tests/                pytest coverage for MVP behavior
```
