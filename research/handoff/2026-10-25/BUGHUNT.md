# Pre-launch integration bug hunt (2026-10-25, before the 18:00 ET launch)

Scope:
- every test module in `tests/`
- the 117/120 of `test_lit_oif`
- the integration of today's merged paths: launch_prep, startup gate, eval anchor / checklist / goals, phone + PC pages,
  the cloud sparse checkout

Rules held:
- nothing armed or routed
- no LIT / ATLAS strategy rule changed
- live behaviour unchanged, except account B's new startup gate (it only blocks; see 1)

## Verdict

- **4 real bugs fixed, each with a regression test.**
- **11 stale test expectations updated.** All of them come from intended changes on 10-24 / 10-25 that their PRs did
  not carry into the tests: the safe switches, "skip instead of min 1 micro", the cost-aware A4 ceilings and the
  `launch` key.
- **2 stale data exports rebuilt:** `research/lab/replays.json` (trade charts) and the eval-path runs + golden file.
- **`_clean_1m`: the live path is right.** The fix belongs in the research cleaning. It is written up below and
  **left for after the launch** (it moves the 2026 headline and about 15 stored artifacts; H2 does not move).

## Findings

| # | Area | Kind | What | Fix | Test |
|---|---|---|---|---|---|
| 1 | Startup gate + account B | **REAL** | LIT's entries wait for `guards.startup_problems` (positions / orders, contract, reset, unreadable state, connection). Account B (ATLAS on the 25K) never asked its own NinjaTrader adapter: it could route its first signal while the 25K showed an unexplained position, the chart sat on another contract or NinjaTrader was mid-reset. | `AccountB.startup_block`: the 25K's adapter `startup_problems()` must be empty once (latched) before B routes. It fails closed on an error. A paper bot, guards `startup_reconcile` off, or an adapter without the check means no gate. | `tests/test_second_account_b.py` units: 3 new checks (disarmed then latched, fails closed, wired into the entry path) |
| 2 | `engine/launch_prep.py` re-run | **REAL** | The launch checklist names `launch_prep` as the fix for several red lines, so the owner may run it again. A second run (a) moved the 25K's `eval_start` to the next weekday. That drops the eval's earlier days from account B's book: wrong room and target, so wrong size. (b) It put the 10-23 default anchor back over a newer one (from `eval_life --anchor` or the day-close real balance). | (a) It keeps the `eval_start` already set for the same 25K, and `--atlas-start` still overrides. (b) It keeps a newer anchor unless `--balance/--floor/--as-of` are given. | `tests/test_launch_integration.py` part c: end-to-end on temp files, run twice, then explicit values, then the same-account refusal |
| 3 | Cloud sparse checkout | **REAL** | I audited every repo file the cloud steps open (`cloud_monitor.py`, `build_web_dashboard.py`, `lit_watch.py`, with a Python audit hook) against the workflow's sparse patterns. These are read but never checked out in Actions: `research/hq/news_calendar.csv` (Goals news, today's PR), `research/lab/health_band.json` (Goals month band, Performance range), `lookahead_audit / robust / walkforward / trade_intel / rejections .json`. A build on the sparse copy confirmed the damage: the published phone site had `goals.calendar.news = []`, `goals.month.expected = null`, `perf.* = null` and `intel = null`. | 7 files added to `sparse-checkout` in `.github/workflows/cloud-monitor.yml` (1.3 MB). | `tests/test_launch_integration.py` part a |
| 4 | PC dashboard news line (`web/js/dash/ops.js`, also served to web_next) | **REAL** (old) | It mapped `blackout_start` / `blackout_end` (the API sends `'HH:MM'` text) as epoch seconds. Each time a high-impact event fell in the next 14 days, it threw `RangeError: Invalid time value`: a page error on Data and a console error on every PC page. | Use `blackout_start_t` / `blackout_end_t`. | Part b of the same test. Playwright sweep: 76 PC pages, 0 errors after the fix (before: an error on every page) |
| 5 | `test_golden` 0/9 | STALE | The golden file was frozen before the 10-24 safe switches, and the eval-path run was never re-saved. | `tools/lit_adopt_combo.py save`, then `tests.test_golden --update` (the documented procedure) | 9/9 |
| 6 | `test_backlog` | STALE | The live control was hard-coded to the numbers before the safe switches (H1 +33,891 / H2 +9,493). | It now compares with the stored run `lit_live` (H1 +33,901 / H2 +9,919). | 12/12 |
| 7 | `test_ai_features` | STALE | String checks expected the publish tuple to end at `"ai"`. The launch PR appended `"launch"`. | Match the `"ai"` entry. | 80/80 |
| 8 | `test_lit_2wk_sizing` "min 1 micro" | STALE | 15cb560 (10-24): a budget is a ceiling, so the size skips instead of keeping 1 micro. | Expect 0. | 20/20 |
| 9 | `test_lit_learn` sizing hook | STALE | The A4 ceilings price one micro's stop-out at (stop + 1 tick) x $2 + $1.90 = $92.40, not $88: 0.6 x $300 now fits 1 micro, not 2. | Expect 1. | 14/14 |
| 10 | `test_lit_wk_loss` | STALE | With the week at -$990 and a $1,200 stop, the A4 weekly ceiling caps the stop-out to the $210 left: 3 micros, not 8. | Expect a capped size with the weekly reason. | 9/9 |
| 11 | `test_eval_mc` "$150 room fails more" | STALE | Since skip-not-min-1, a thin eval no longer stops out to a fail. It gets **stuck** (open). | Assert fewer passes and more stuck evals than a fresh eval. | 10/10 |
| 12 | `test_lit_trade_charts` 775 problems | STALE DATA | `research/lab/replays.json` dated from 10-23 (old price basis). `backtest_live.json` was refreshed today. The phone and PC trade pictures showed old prices. | `python tools/export_replays.py` | PASS (0 problems) |
| 13 | `test_pcdash_api` 127/130 | ENV (known) | The `MNQ_*.csv` feed files are empty in this container. | none | known |
| 14 | `test_live_dryrun` 41/44 | KNOWN | It is pinned to the old engine (documented in `CLAUDE_REFERENCE.md`). | none | known |
| 15 | `test_lit_oif` 117/120 | RESEARCH CLEANING (see below) | 03-23, 04-03 and 05-05 | written up, not changed tonight | 117/120 |
| 17 | `test_trade_intel` totals | STALE | H2 totals hard-coded at the pre-safe-switch numbers (PF 2.69 / +$9,493) | compared with the stored run `lit_live` | 24/24 |
| 16 | `test_second_scorecard` "rebuild gives the same bands" | KNOWN | pre-existing | none | known |

Note: test runs also rewrite `data/VIX_1d.csv`, `VXN_1d.csv`, `data/news/*`, `cache/dash/*`, `research/lit/live_*.json`
and `tools/web_hub_snapshot.json` (the cloud dry run refreshes the CBOE files). These were restored before the commit.

### Eval-path numbers to know (not a bug, now frozen in the golden file)

- **What the tool shows:** with the safe switches and skip-not-min-1, the research eval-path tool
  (`lit_adv_manage.b2b`) reads H1 n=68 PF 3.49 +$16,977 and **H2 n=14 PF 0.28 -$1,946**.
- **Why:** H2's single eval drops to $54 of room on 2026-09-04. After that, 1 micro never fits, so it trades nothing
  for the rest of H2. It is stuck: it never fails and never passes.
- **Live handling:** `eval_life` flags it as `stuck` (room < $200) and pushes "EVAL STUCK: buy a new one". The owner
  then buys a new eval.
- **The 2-week odds have not changed:** pass within 10 sessions H1 57.1% / H2 52.2%.
- **What changed is the meaning of "fail":** in the simulation, fails are now about 0%. A thin eval sits stuck instead.
- **Tonight:** the 50K has $1,542.60 of room, far from stuck.

## Integration checks run (all clean after the fixes)

**launch_prep end to end** (temp copy of the repo, fake NinjaTrader folder, never armed):
- Allowlist: `[50K, 25K]`.
- Anchor: 49,710.80 / 48,168.20 as of 10-23.
- ATLAS: builder25k from 2026-10-26.
- A re-run is idempotent (after fix 2).
- The same account for both is refused.

**One eval, the same numbers everywhere** (LiveBot on NinjaTrader, unarmed, account B on, no `accounts.csv`):

| Reader | Balance | Floor | Room | Other |
|---|---|---|---|---|
| `eval_room()` | | | **$1,542.60** | |
| `eval_state()` | | | 1,542.60 | profit -289.20, session 5 |
| `eval_life()` | 49,710.80 | | 1,542.60 | to target 3,289.20 |
| `eval_clock()` | | | 1,542.60 | |
| Launch checklist anchor line | 49,710.80 | 48,168.20 | | |
| Heartbeat `acct.eval.anchor`, cloud accounts block and Goals (`source` PC bot, anchored) | 49,710.80 | 48,168.20 | 1,542.60 | "$3,289 to go" |

With `broker_balance` absent, the checklist line is `info` ("sizes from its ledger + the anchor") and never blocks.

Caveat: with no PC heartbeat that carries the anchor, Goals falls back to the cloud paper eval ($49,900 / $1,900 room
from `eval_prior_pnl`). After tonight's start, the PC heartbeat carries the anchor, so the phone shows the real numbers.

**Startup gate with account B on:**
- LIT: DISARMED until the reconcile passes, as built.
- Account B: now has its own gate (fix 1).
- Both adapters report "adapter disabled ... not armed" while unarmed. That is correct.

**Pages** (Playwright Chromium, console errors and page errors):

| Site | Data | Pages | Errors |
|---|---|---|---|
| Phone, fresh cloud build (`cloud_monitor.py --out` + `build_web_dashboard.py`) | cloud | 68 | 0 |
| Phone, the same build with the anchored PC heartbeat + launch block injected | anchored PC | 68 | 0 |
| PC (`server.py`, every route id in `web_next/js/next/routes.js`) | local | 76 | 0 after fix 4 |

**Cloud sparse checkout:**
- I emulated the sparse checkout (40 patterns, 3,034 of 4,997 tracked files) and diffed `data.json` against the full
  checkout. Fix 3 closes every gap that today's blocks use.
- Left as is:
  - `data/ES_5m.csv` (learning-loop ES features: already "unknown" without fresh ES)
  - `GEX_1d.csv` and `NQ_1h.csv` (old narrative extras)
  - `research/business/*` (private money files; the hub snapshot carries what the site shows)

## `_clean_1m` and test_lit_oif 117/120: the live path is correct

**What happens:**
- `engine/data._clean_1m` drops a 5-row 1m window when its first minute covers the whole window with more volume than
  the other four minutes together. The rule assumes such a row is a 5m bar written into the 1m file.
- In 2026 it drops 226 windows (233 in all) whose five genuine minutes rebuild the 5m bar exactly. Examples:
  - 2026-03-23 06:50: first minute 1,863 contracts vs 1,245 for the other four
  - 2026-04-03 01:05
  - 2026-05-05 02:10
- **Only 31 of the 233 dropped windows** have a first minute that carries the 5m bar's own high, low and close, which is
  what a 5m bar written into the file looks like. The other 202 cannot be such rows: an imported 5m bar closes at the 5m
  close, and these first minutes do not.
- `load_ltf` always passes the 5m base in research. So the **exact** check (first row = the 5m bar's high / low / close)
  already catches real imports. The volume rule only adds false positives.

**Why live is right:**
- The live loop (`lit_live`, `lit.bars_1m(src=feed)`) never applies the rule: it trades the minutes the market printed.
- A1's variant (no volume rule when the base is given; `a1_clean1m_variant.json`) changes exactly 03-23, 04-03 and 05-05.
- On all three days the variant's entry is the live loop's entry:

| Day | Live | Variant | Current backtest |
|---|---|---|---|
| 05-05 | 02:16, 6 micros | 02:16, 6 micros | 02:17, 3 micros |
| 04-03 | 04:02, 3 micros | 04:02, 3 micros | 04:05, 4 micros |
| 03-23 | entry at 07:00 | 07:00 | 06:58 |

- **"Good Friday" was this same cleaning issue, not a holiday effect.** With the research fix, `test_lit_oif` should be
  120/120.

**Effect of the research fix:**

| Span | Now | With the fix |
|---|---|---|
| 2026 | PF 4.19, +$43,820 | PF 4.12, +$43,089 |
| H1 | PF 4.98, +$33,901 | PF 4.85, +$33,171 |
| H2 (the rate to quote) | PF 2.91, +$9,919 | unchanged |

**Why not tonight:**
- The fix moves the 2026 headline in CLAUDE.md, STRATEGY.md, the pcops headline, `backtest_live.json`, the health
  band, the dashboards, the golden file, `adopt_combo` and the stored runs.
- It also needs cache invalidation: `research/runs/_cache` is keyed by data files, not by the cleaning code.
- That is too much churn on launch night, and it changes nothing the bot does.

**Plan for after the launch, in this order:**
1. In `engine/data._clean_1m`: when `base` is given, apply only the exact base check. Keep the volume rule only when
   there is no base (`tools/import_1m_dryrun.py`).
2. Delete `research/runs/_cache/litfinal_*` and the `lit_*` replay caches.
3. Run `python tools/lit_losses.py live`, `tools/export_backtest.py`, `tools/lit_dash_data.py`,
   `python -m engine.health_band build` and `tools/export_replays.py`.
4. Run `tools/lit_adopt_combo.py save`, then `tests.test_golden --update`.
5. Check `tests.test_lit_live --days --bot` (must be 120/120) and `tests.test_lit_oif` (expect 120/120).
6. Update the headline lines (2026 PF 4.12 +$43,089; H1 +$33,171; H2 +$9,919 unchanged).

## Test table

**How the suite was run:**
- Every module in `tests/` (80 modules) ran with `python -X utf8 -m tests.<name>`, `--quick` where supported.
- Up to 4 ran in parallel, with a 25-minute timeout each.
- Other sessions were loading the machine heavily at the same time (load average 5 to 7).

"After" = the result after this commit's fixes.

| Module | Before | After | Note |
|---|---|---|---|
| test_a1_timing (quick) | 18/18 | | |
| test_accounts | 24/24 | | |
| test_ai_features | 78/80 | **80/80** | stale string check (7) |
| test_alerts_plus | 92/92 | | |
| test_atlas_armed | pass | | |
| test_atlas_ui | 36/36 | | |
| test_atlas_v2_shadow | 42/42 | | |
| test_autorun | 90/90 | | |
| test_backlog | 11/12 | **12/12** | stale (6) |
| test_brain (quick) | 22/22 | | |
| test_broker_balance | 41/41 | | |
| test_business | 85/85 | | |
| test_data_check | 8/8 | | |
| test_drift_nightly | 16/16 | | |
| test_eval_anchor | 43/43 | | |
| test_eval_lifecycle (quick) | 35/35 | | |
| test_eval_mc | 9/10 | **10/10** | stale (11) |
| test_fill_audit | 30/30 | | |
| test_goals | 47/47 | | |
| test_golden | 0/9 | **9/9** | stale golden (5) |
| test_guards (quick) | 67/67 | | |
| test_health | 46/46 | | |
| test_import_1m_dryrun | 5/5 | | |
| test_import_tv | 24/24 | | |
| test_launch_checklist | 59/59 | 59/59 | |
| test_launch_integration (new) | n/a | **18/18** | fixes 2, 3, 4 |
| test_ledger_freeze | pass | | |
| test_lit_2wk_sizing | 19/20 | **20/20** | stale (8) |
| test_lit_add_safety | 28/28 | | |
| test_lit_brief | 396/396 | | |
| test_lit_exit_route | 19/19 | | |
| test_lit_idm_sizing (quick) | 13/13 | | |
| test_lit_late_entry | 10/10 | | |
| test_lit_learn | 13/14 | **14/14** | stale (9) |
| test_lit_live | timeout at 25 min | see below | day-end replay 120/120 identical before the timeout |
| test_lit_lookahead | pass | | |
| test_lit_more_entries | timeout at 25 min | see below | asia_slot 187/187 identical before the timeout |
| test_lit_oif | 117/120 | 117/120 | research cleaning, written up above |
| test_lit_provisional | 5/5 | | |
| test_lit_retail | pass | | |
| test_lit_scale_in | 18/18 | | |
| test_lit_timing | 11/11 | | |
| test_lit_trade_charts | 775 problems | **PASS** | stale replays.json (12) |
| test_lit_watch | 120/120 | | |
| test_lit_wk_loss (quick) | 8/9 | **9/9** | stale (10) |
| test_live_dryrun (quick) | 41/44 | | known (old engine) |
| test_live_publish | 44/44 | | |
| test_mffu_rules | pass | | |
| test_multi_account (quick) | 49/49 | | |
| test_no_yahoo (quick) | 18/18 | | |
| test_nt_exec_audit | 46/46 | | |
| test_nt_outgoing | 26/26 | | |
| test_nt_roll_guard | 10/10 | | |
| test_one_time_setup | 35/35 | | |
| test_ops | 103/103 | | |
| test_pc_command_center | 60/60 | | |
| test_pc_silent | 30/30 | | |
| test_pcdash_api | 127/130 | | env: empty MNQ feed files (known) |
| test_perf (quick) | 47/47 | | |
| test_prefix_invariance | 11/11 | | |
| test_presence | 59/59 | | |
| test_push | 41/41 | | |
| test_recap | 104/104 | | |
| test_rehearsal | timeout at 25 min | see below | |
| test_remote_ctl | 51/51 | | |
| test_risk_invariants | 27/27 | | |
| test_roll | 23/23 | | |
| test_router_determinism | 36/36 | | |
| test_scale_plan (quick) | 39/39 | | |
| test_second (quick) | 31/31 | | |
| test_second_account_b (quick) | 45/45 | | includes the 3 new startup checks (fix 1) |
| test_second_route (quick) | 24/24 | | |
| test_second_scorecard | 26/27 | | known ("rebuild gives the same bands") |
| test_second_stophunt (quick) | 18/18 | | |
| test_sizing_caps | 41/41 | | |
| test_stophunt (quick) | pass | | |
| test_trade_chart | 78/78 | | |
| test_trade_intel | 23/24 | **24/24** | stale: H2 totals were hard-coded at the numbers before the safe switches |
| test_upgrade_shadow | 19/19 | | |
| test_win_scripts | 132/132 | | |
| test_writeups_index | 5/5 | | |

**Reruns of the three timeouts** (alone, 50-minute limit): see "Reruns" below.
