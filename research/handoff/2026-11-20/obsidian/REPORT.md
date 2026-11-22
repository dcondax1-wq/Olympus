# night-obsidian: ZEUS Brain (pushed on night-obsidian)

| What | Result |
|---|---|
| Vault | `vault/` in the repo: 449 linked notes (4 accounts, 18 strategy notes incl. ATLAS members + K8 legs, 202 research, 14 families, 190 days, 11 months, Lessons, Decisions, Apps, Kalshi, State) |
| Builder | `tools/obsidian_brain.py`: 0.4 s, same input = same bytes, rewrites only changed notes, Inbox/ never touched |
| Keeps learning | the cloud night `tools/learn_night.py` rebuilds `vault/` (soft, `--skip brain`); the PC sync rebuilds `<vault>/OLYMPUS/ZEUS Brain` once an hour |
| Look | callouts + `zeus.css` snippet + graph colors + a starter workspace opening ZEUS Home; no plugins |
| Tests | `tests.test_obsidian_brain` 25/25 (area pc); obsidian_sync 18/18; learn_night 64/64; public_build_privacy --fast 56/56; links 0 dangling |
| Not mine | `test_repo_secrets` c fails on `tests/test_rapid25.py` (it failed before this change too); smoke `test_zenith_mode` needs Python Playwright, which this container doesn't have |
| Lead | `LEAD_WIRES.md`: nothing lead-only touched; optional Jarvis path line |

Owner's steps:
1. On the PC (once): `python tools/obsidian_sync.py --setup "C:\path\to\your\vault"` (skip if already set): the brain lands in OLYMPUS/ZEUS Brain.
2. In Obsidian: Settings -> Appearance -> CSS snippets -> turn on **zeus**; open **ZEUS Home**, then the graph view.
3. Write your own notes in an `Inbox/` folder: they are never overwritten and get linked from ZEUS Home.
