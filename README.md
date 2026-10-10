# Dota Draft Assistant

Local Dota 2 draft recommendations through a CLI and a PySide6 desktop GUI. Manual drafting runs offline; optional provider refreshes create local statistical snapshots. Scores are ranking points, not win probabilities.

## Windows setup and launch

Requires 64-bit Python 3.12 or later. Run these PowerShell commands from the checkout. The version pins below reproduce the dependencies used in the audit; newer versions have not been tested here.

```powershell
Set-Location C:\Users\lev\projects\dota-draft-assistant
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e . "PySide6==6.11.2" "pytest==9.1.1"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\dota-pick.exe --validate-data
.\.venv\Scripts\dota-pick-gui.exe
```

Activation is unnecessary. Keep the checkout's `data` directory: the current loader resolves data relative to the source tree, so editable installation is the supported path. A standalone wheel installation outside the checkout is not verified.

Alternative GUI launch after installation:

```powershell
.\.venv\Scripts\python.exe -m draft_assistant.gui.app
```

## Manual drafting

```powershell
.\.venv\Scripts\dota-pick.exe "sf bara ogre silencer | underlord jakiro wd | carry" --explain
.\.venv\Scripts\dota-pick.exe "sf bara ogre | jakiro wd | carry" --top 5 --data manual
```

Input is `enemy heroes | allied heroes | role`. Hero names and aliases are case-insensitive; multiword names and Russian aliases are supported. Roles: `carry`, `mid`, `offlane`, `support`, `hard_support`. Picked heroes are excluded from recommendations.

The GUI offers autocomplete, pick chips, role/count/data selectors, separate meta and personal-pool lists, score explanations, allied role overrides, team timing/threat analysis, item suggestions and owned-item tracking. It also has a compact overlay, always-on-top and an animation toggle. Draft saving is a placeholder. Screen detection requires programmatic calibration and portrait references; selecting AUTO alone does not configure it.

## Optional data refresh and personal pool

```powershell
.\.venv\Scripts\dota-pick.exe --sync-opendota
# Set STRATZ_API_TOKEN in this shell using your own token before these commands.
.\.venv\Scripts\dota-pick.exe --sync-stats
.\.venv\Scripts\dota-pick.exe steam-login
.\.venv\Scripts\dota-pick.exe --profile-status
.\.venv\Scripts\dota-pick.exe --profile-probe
.\.venv\Scripts\dota-pick.exe --personal-stats --matches 100
.\.venv\Scripts\dota-pick.exe "sf | wd | carry" --data hybrid --heroes prefer
```

STRATZ sync captures all five roles for Herald/Guardian, with six meta requests and 127 paced pair requests. `--stats-role` does not restrict STRATZ sync. OpenDota supplies a public, position-agnostic Herald/Guardian fallback. `manual`, `stats`, and `hybrid` read local data without fetching during recommendation. Restart the GUI after refreshing snapshots because readers cache them in memory.

Steam sign-in links an identity through a browser and local OpenID callback; it does not grant access to private match history. Personal history needs a STRATZ token and accessible provider data. Pool modes are `all`, `prefer`, and `only`; an empty role pool can produce no results in `only` mode. GUI sign-in does not automatically refresh history.

DOTABUFF has an HTML importer (`--sync-dotabuff --stats-role carry --window month`), but the audit received HTTP 403, and its snapshot is not consumed by runtime scoring.

Generated snapshots live in ignored `data/generated/`. The linked profile lives under `%LOCALAPPDATA%\DotaDraftAssistant`. Keep tokens out of repository files.

## Structure and evidence

- `src/draft_assistant/`: CLI, deterministic scoring, team/item analysis, statistics, personal history, auth, provider adapters, screen detection, Qt GUI.
- `data/`: 127 hero definitions and numeric-ID mappings, 36 curated directed matchups, 22 synergy pairs, 202 catalog items.
- `tests/`: parser/data validation, scoring, adapters, personal pools, authentication, detection, GUI, team and item tests.
- `scripts/`: optional benchmark; `run.sh` is currently empty.

Curated data and mechanics are heuristic; provider coverage and patch freshness are not guarantees of recommendation quality. Raw hero/matchup/item evidence uses a separate optional `statistics.json` export, which current sync commands do not generate.

See [AUDIT.md](AUDIT.md) for verified behavior, remaining limitations and priorities.
