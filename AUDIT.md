# Repository audit — 2026-10-10

## Scope and repository state

Audited tracked source, README, configuration, data, tests, history, branches and stash before editing. Initial tracked working tree was clean at `ba325f7` on `main`, tracking `origin/main`. The other local branch was `resume-stratz-all-role` at `892e53c`. Recent commits added item evidence, separate meta/pool rankings, all-role STRATZ data, role-specific pools, personal history, Steam authentication and overlay UX.

`stash@{0}` is `On main: wip stratz all-role sync`, with changes to CLI, STRATZ, scoring and tests (114 insertions, 64 deletions). Its diff summary was inspected; it was not applied or changed.

Pre-existing untracked work: `DotaDraftAssistant-release.zip`, `DotaDraftAssistant.spec`, `DotaDraftAssistant.zip`, `build/`, `dist/`, `release/`, `run_gui.py`. These were left outside the commit. Three inaccessible `pytest-cache-files-*` directories produced inventory warnings; they were not changed. Existing ignored statistical/personal caches were not refreshed. Tests use disposable generated test files and remove them.

## Implemented features and verification

| Area | Implementation | Evidence and limits |
| --- | --- | --- |
| Draft engine | Aliases/multiword parsing, five roles, legal-pick filtering, deterministic ranking, explanations, manual/stats/hybrid modes, personal comfort and pool filtering | Existing parser/scoring/regression tests passed. Actual CLI sample returned Lifestealer 83, Juggernaut 76, Wraith King 68. GUI add/recommend/remove/clear passed a native Windows Qt smoke. Recommendation quality against current game outcomes was not evaluated. |
| Hero/item data | 127 heroes and numeric-ID mapping; 216 hero aliases; 36 curated directed matchups; 22 synergy pairs; 202 items, 176 recommendable, 228 item aliases and 273 upgrade edges | Actual `--validate-data` passed. Live OpenDota supplied 127 rows with no unmapped IDs. Curated scores and role/mechanics definitions are heuristics with no verified patch freshness. |
| STRATZ | Token-authenticated GraphQL, all-five-role Herald/Guardian meta, shared paced matchup/synergy requests, normalization, local snapshots, rate-limit errors | Mocked adapter/sync tests passed. Live one-hero offlane meta query accepted and returned one row; live Axe pair query returned 126 vs and 126 with rows. Full 133-request refresh was not executed; existing snapshot was preserved. Pair data is position-agnostic. |
| OpenDota | Public heroStats fetch, Herald/Guardian aggregation, fallback meta scores, missing/unmapped IDs and HTTP errors | Live fetch and in-memory normalization succeeded for 127 heroes; adapter tests passed. No role-specific matchups or personal-history fallback is implemented. No snapshot was written by the audit. |
| Personal hero pool | Paged STRATZ history, Turbo exclusion, position normalization, global/role-specific experience tiers, cached history, CLI pool display and GUI separate pool ranking | Existing tests and existing 99-match cache analysis passed. With explicit permission, five live matches were fetched and normalized without saving; only two had known positions. Larger pagination and private-history access were not live-tested. |
| Steam authentication | Browser OpenID login, random callback state, remote verification, localhost server, per-user profile store, CLI/GUI link/unlink | Mocked authentication/profile tests passed. Existing linked profile was used for the approved live history check. A fresh interactive browser sign-in was not performed. Identity linking does not grant private-history access. |
| Screen detection | Qt capture, Windows Dota-window lookup, normalized slots, portrait template matcher, temporal stabilization, worker-thread polling, detected/manual pick merging | Synthetic detection/state/GUI tests passed. GUI starts with an unconfigured poller; AUTO reports calibration required. No bundled calibration/reference images or user calibration workflow. No live Dota screen was tested; banned/grid recognition is incomplete. |
| Qt GUI | Autocomplete, animated pick chips/background, role/count/data selectors, separate meta/pool recommendations, breakdown, item inventory/suggestions, allied role overrides, timing/threat analysis, overlay and always-on-top | Offscreen GUI tests passed. Native Windows platform launch and event loop plus core add/recommend/remove/clear smoke passed with the test window hidden. Physical screen layout and an overlay during a real match were not visually verified. Saving is a placeholder; Steam login blocks the UI while awaiting browser completion. |

## Confirmed problems and incomplete paths

- Baseline suite: 233 passed, one failure in chip removal. A removal arriving before the entrance animation completed could lose its completion callback because the entrance replaced/deleted the removal opacity effect. Draft state also waited for animation completion.
- DOTABUFF: live request returned HTTP 403. `--sync-dotabuff` without `--stats-role` also fails locally with `Unknown role: None`; passing an explicit role avoids that argument issue. Its generated snapshot is not consumed by runtime scoring.
- Global hotkey: a correctly structured synthetic Windows `MSG` for `WM_HOTKEY` was rejected by `nativeEventFilter`. The handler indexes 32-bit words incorrectly for a 64-bit Windows message. Actual keyboard activation was not tested.
- Screen AUTO is a component integration point, not an end-user automatic detector. Calibration and portrait provisioning are absent. Detected picks also survive `DraftState.clear()` because that method clears only manual lists (source inspection).
- Personal history caches are not scoped to the linked account; sign-out or a different account can leave the previous pool available (source inspection). GUI login does not fetch history. The approved live sample demonstrated missing position information.
- Snapshot readers cache data for the process lifetime. There is no visible stale-data warning or refresh workflow. Statistics-only mode with no usable samples can produce zero-score ties (source inspection).
- Raw statistical evidence panels read `data/generated/statistics.json`; the implemented provider syncs do not create that file. Therefore working snapshot scoring does not imply that raw hero/item evidence is populated.
- Malformed/inaccessible scoring or personal snapshot files are not handled as robustly as the separate statistics evidence loader; some can interrupt GUI initialization (source inspection, not fault-injected here).
- Local data is resolved relative to source location. Editable checkout operation was tested; wheel/non-editable packaging and the pre-existing executable releases were not verified. `scripts/run.sh` is empty.

## Minimal changes

Only the confirmed manual draft blocker was fixed: removal changes draft state and recommendations immediately, and cancels the same chip's entrance animations before starting its removal animation. The existing regression now asserts immediate draft-state removal as well as eventual chip removal. The architecture and scoring were preserved.

README was updated to describe the implemented application, Windows dependency/launch commands, optional integrations and known limitations. This audit records evidence separately from source-inspection findings. No provider, screen-detection, hotkey or authentication refactor was undertaken.

## Environment and results

- Python 3.12.10, PySide6 6.11.2, pytest 9.1.1, setuptools 84.0.0, pip 25.0.1.
- PyPI checks on the audit date: PySide6 latest 6.12.0 and pip latest 26.2.1; installed pytest and setuptools matched their latest versions. These are version differences, not proven application blockers. Dependencies were not upgraded. Sources: https://pypi.org/project/PySide6/ and live PyPI JSON metadata.
- `py -3.12 -m pip check`: no broken requirements.
- Baseline: `py -3.12 -m pytest -q -p no:cacheprovider`: 233 passed, 1 failed.
- After fix: same full-suite command: 234 passed. Native Windows Qt launch/core-flow/event-loop smoke passed.
- `py -3.12 -m draft_assistant.cli --validate-data`: passed. Actual explained CLI draft completed successfully.
- Direct network calls initially failed inside the sandbox. Authorized network checks outside it verified OpenDota, STRATZ meta/pairs and the approved bounded personal history check; DOTABUFF remained blocked by HTTP 403. Fresh venv installation and a full provider refresh were not executed.

## Five highest-priority improvements for everyday use

1. Make data quality visible: patch/date/sample coverage and stale-data warnings, reproducible provider refresh, and clear manual fallback when statistical coverage is missing. Populate the raw evidence export or explain its absence in the GUI.
2. Make personal pools account-specific and refreshable: isolate caches by Steam ID, invalidate in-memory pools on refresh/sign-out, expose unknown-position coverage and run browser/network waits outside the UI thread.
3. Complete screen-detection setup: provide calibration and portrait acquisition, validate against real Dota draft screens/resolutions, and make Clear reset detected state predictably.
4. Harden snapshot loading and Windows distribution: tolerate corrupt/missing snapshots, write them atomically, declare a development dependency set and verify a reproducible install/package containing required data.
5. Finish everyday GUI controls: correct and test the 64-bit hotkey, implement draft save/restore, provide owned-item removal controls, and validate overlay interaction during a real match.
