# Current-patch meta refresh

Run from the repository with `STRATZ_API_TOKEN` already in the environment:

```powershell
.\.venv\Scripts\python.exe -m draft_assistant.cli --update-meta
.\.venv\Scripts\python.exe -m draft_assistant.cli --validate-data
.\.venv\Scripts\python.exe -m draft_assistant.gui.app
```

The GUI's **Update Meta** button runs the same refresh in a child process and
reloads scores and evidence when it succeeds. `--sync-stats` defaults to this
Archon workflow. `update_dota_742.py` is a compatibility launcher for the same
command; it no longer rewrites Python source or assumes a patch number.

## Filtering and sources

The updater discovers the newest gameplay patch announcement in Valve's official
Steam news feed, records its timestamp and URL, and queries STRATZ `winHour`
using exact `ARCHON`, each of the five positions, and `ALL_PICK_RANKED`.
It accepts only whole UTC hourly buckets starting after the announcement and
ending before refresh time. The release hour is excluded. This is an explicitly
labelled time-filtered proxy: game-version IDs are not verified, deployment may
precede the announcement, and provider coverage may have gaps or lag.

Live investigation on November 20, 2026 found Valve's 7.42 announcement at
**November 18, 20:00:46 UTC**, STRATZ gameVersions ending at 7.41f (ID 190),
and daily data ending before release. Hourly data was available after release.
GraphQL introspection verified the filters. `stats` and `itemFullPurchase`
`minTime`/`maxTime` refer to minutes **inside a game**, not calendar timestamps.
Weekly `matchUp` and item aggregates cannot safely be labelled 7.42 during the
release week. OpenDota publicMatches returned HTTP 403 in the live probe;
heroStats does not establish patch-specific position coverage.

The successful refresh contained **661,653 hero observations** across 127 mapped
heroes in every position, covering **November 19 00:00 through November 20
06:00 UTC (exclusive)**. Position observations: carry 132,390; offlane 132,380;
soft support 132,408; mid 132,360; hard support 132,115. This is not a unique
match count: role/bracket aggregates do not expose a deduplicated match cohort.

## Recommendation behavior and limits

Updated role win rates affect ranking directly, with a neutral 1,000-observation
prior: `(win_rate - 0.5) * 10 * n / (n + 1000)`. The player's positions 1, 3,
and 4 refresh first. Existing hero-role eligibility is preserved. Pick popularity
is a share of mapped hero observations in each position, not an independently
verified percentage of all matches. No new hero definitions are invented.

When this patch-aware snapshot is loaded, automatic and hybrid scoring use only
its provider evidence. Historical OpenDota baselines and curated pair scores do
not enter those recommendations. Missing patch-exclusive counterpicks,
synergies, items/builds, and exact-Archon bans remain unavailable. Item advice
and explicit `--data manual` retain curated heuristics, not 7.42 statistics.
Without a usable snapshot, the existing clearly labelled offline fallback is
preserved. Legacy snapshots remain readable with their recorded bracket.

`data/generated/patch_hours.json` retains accepted raw hourly records;
`snapshot.json` supplies scoring and GUI evidence; `statistics.json` supplies raw
win/pick evidence. Previous versions are backed up under
`data/generated/backups/` before replacement. Requests are paced; rate limits
stop the refresh. All fetching and validation finish before outputs are written.
Each output is replaced atomically; an operating-system failure between the
separate file replacements can still leave different export generations.
Tokens and generated exports are never committed.

Validation: 272 automated tests passed, `--validate-data` rebuilt and checked exports against retained hours, and native
Windows Qt rendering plus position 1/3/4 score/evidence consistency were checked.
The isolated commit also passed its 241 tests.
Boundary, duplicate-page, failed-refresh preservation, shrinkage, and historical
fallback exclusion have automated regression tests. Synthetic test values are
not presented as provider observations.
