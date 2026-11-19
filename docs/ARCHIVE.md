# Archive: files moved out of the repo (2026-11-19, night-clean)

Nothing here was destroyed. Every file is still in git history; the last commit that has them is `e706b2efe18f`
(on GitHub `claude/clever-heisenberg-51zwcr` and on the backup `pc` branch). Each checkout (the PC's and every helper's)
is about **286 MB smaller** once it updates. `.gitignore` now keeps these from being committed again when a test or a shot
script writes them.

Proof they are unused (checked 2026-11-19): no code, test, page, site build (`tools/build_web_dashboard.py`), publisher
(`tools/pc_publish.py`, `tools/gh_publish.py`), CI workflow or PC route reads them. Tests and shot scripts only *write*
screenshots into these folders. Only docs mention them, as "screenshots in ...".

## What moved

| Path | What it was | Why it went | Size | Restore (one line, from the repo folder) |
|---|---|---|---:|---|
| `research/handoff/2026-10-25/` images (104) | before / after screenshots of the Oct 25 launch work (PC pages, phone, icon option sheets) | older than 7 days; the PC's audit viewer opens only the text files, which stay | 42.2 MB | `git checkout e706b2efe18f -- 'research/handoff/2026-10-25/*.png'` |
| `research/handoff/2026-10-26/` images (35) | Start page / live board shots | older than 7 days | 10.0 MB | `git checkout e706b2efe18f -- 'research/handoff/2026-10-26/*.png'` |
| `research/handoff/2026-11-03/` images (149) | Mind, Hermes, Prometheus, voice, Kalshi planner shots | older than 7 days | 40.5 MB | `git checkout e706b2efe18f -- 'research/handoff/2026-11-03/*.png' 'research/handoff/2026-11-03/*.jpg'` |
| `research/handoff/2026-11-03-day/` images (189) | arena, research apps, zenith, Kalshi shots | older than 7 days; test_arena / test_prometheus / test_strategytree rewrote them on every run | 55.0 MB | `git checkout e706b2efe18f -- 'research/handoff/2026-11-03-day/*.png' 'research/handoff/2026-11-03-day/*.jpg'` |
| `research/handoff/2026-11-04/` images (14) | gate-run shots | older than 7 days (gate.md / gate.json stay) | 4.1 MB | `git checkout e706b2efe18f -- 'research/handoff/2026-11-04/*.png'` |
| `docs/shots/` 16 old design folders (278 images): colosseum, polis, jarvis_home_v2, jarvis_home_agora, qa_round6, qa_round6_phone, qa_round7, gate, worlds, design_v2, environments_v3, sound, direction_v3, characters_v3, characters_v2, voices | design-round evidence pictures | last changed 7+ days ago; the README / json notes in those folders stay | 49.0 MB | `git checkout e706b2efe18f -- 'docs/shots/<folder>/*.png' 'docs/shots/<folder>/*.jpg'` |
| `research/lab/screens_pc/` (14) | screenshots of the old 7-page PC hub | nothing reads them | 16.7 MB | `git checkout e706b2efe18f -- research/lab/screens_pc` |
| `research/lab/TRADER_LAYER_trades_*.json`, `TRADER_LAYER_decisions_*.json` (354) | per-trade / per-decision dumps of the Oct 16 trader-layer batch (old Strategy Lab) | only written, never read; `TRADER_LAYER_results.json`, the `*__<period>.json` scorecards and the reports stay | 43.9 MB | `git checkout e706b2efe18f -- 'research/lab/TRADER_LAYER_trades_*' 'research/lab/TRADER_LAYER_decisions_*'` |
| `research/lab/person_v1/` (118) | the person-style study's first scorecards, replaced by the re-run (PERSON_REPORT.md) | superseded; `strategy_lab.board()` reads only top-level scorecards | 2.3 MB | `git checkout e706b2efe18f -- research/lab/person_v1` |
| `tools/web_public/icon_options/` (297) | the Oct 25 Home Screen icon options (a..m, j1..k3, p1..p14) | closed choice: the live icon is `web/icons/` (gold temple, `tools/icon_temple.py`, 2026-11-18); the site build never copied this folder | 22.7 MB | `git checkout e706b2efe18f -- tools/web_public/icon_options` (needed again only for `tools/icon_apply.py`) |

Restore everything at once:

```
git checkout e706b2efe18f -- 'research/handoff/2026-10-2*/*.png' 'research/handoff/2026-11-0*/*.png' 'research/handoff/2026-11-0*/*.jpg' 'docs/shots/*.png' 'docs/shots/*.jpg' research/lab/screens_pc research/lab/person_v1 'research/lab/TRADER_LAYER_trades_*' 'research/lab/TRADER_LAYER_decisions_*' tools/web_public/icon_options
```

(`'docs/shots/*.png'` also matches pictures still in the repo; git simply writes the same file again.) A restored file
that `.gitignore` now lists needs `git add -f` to be committed again.

## Kept on purpose (checked, still used)

- `research/runs/` (234 MB, 2,344 runs): the PC dashboard lists and opens every run (`engine/next_api.py`), the Archive and
  Colosseum pages are built from all of them, the live bot reads `lit_live.json`, ~25 tests read named runs. Helper
  worktrees already skip it (sparse checkout).
- `research/lab/chart_examples/` (11 MB): the site build and the PC chart API copy them (`engine/trade_chart.py`).
- the text files of every hand-off folder (`research/handoff/2026-10-25/*.csv|md` feed `tools/uprisk.py`,
  `tools/funded_path.py` and the PC command center).
- `docs/shots/` folders changed in the last 7 days (themes, themes_v2, ia_v2, ia_themes, effects, nav, fx_v3: 35 MB) and
  the business pictures (agency*, money_machines): next in line once they are a week old, the business ones never.
- data (`data/*.csv`, `data/tv_exports/`, `data/clean/`): the futures history the bot and backtests use.
