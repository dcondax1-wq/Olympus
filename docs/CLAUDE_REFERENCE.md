# NQ Liquidity Engine: full reference for Claude sessions

> Moved out of CLAUDE.md on 2026-10-24 so it is not loaded into every message. CLAUDE.md keeps the hard rules and an index;
> read the section you need here. Keep this file current when you change what a section describes.


The owner trades a **MyFundedFutures (MFFU) Builder 50K** eval and is building this NQ futures bot. They are not a coder and
usually write from a phone. Reply short, plain and result-first: what changed, the numbers, what's next. Do the work instead of
asking; show evidence (backtest numbers, charts) and be honest when something doesn't work.
**Steps for the owner (2026-10-20): at most 3 numbered steps, one copy-paste line, no options or side notes; do every other
part yourself or fold it into a script.**

## One chat: where each thing lives and how it ships (owner 2026-11-01)

**The system's name is OLYMPUS (owner 2026-11-03; NEXUS was dropped).** Shown on Jarvis's header (`.hpanel::after`),
the orb switcher's title (switcher.js) and the System section (current workers: `jarvis/sw.js` jarvis-v24, `kalshi/sw.js` kalshi-k19, root `sw.js` le-public-v59).
The owner: "I want this chat to be the one I make all changes to, for anything. It's gonna save me time and usage." Every
project is changed from this repo; this map saves the search. Ship = PR on the session branch, squash-merge to main.

| Thing | Where it lives | How a change ships | Tests to run (only these) |
|---|---|---|---|
| NQ bots (Zlarior/LIT, ATLAS, BLITZ) | `engine/`, `live_model*.json`, `second_model.json`, `tools/` | the backup repo `dcondax1-wq/olympus` branch `pc` (since 2026-11-14; `docs/AUTO_UPDATE.md`) -> the PC auto-updates when the bot is FLAT (`engine/autoupdate.py`: self-tests, rollback on failure) | `tests.test_lit_live` + the area's own test |
| Zenith (phone dashboard) | `tools/web_public/` (index.html, sw.js, …) | main -> run `cloud-monitor.yml` (ref main) -> nq-dashboard Pages, live ~2 min after the run | `tests.test_phone_e2e` (+ the page's own test) |
| Jarvis (home app, the orb) | `tools/web_public/jarvis/` | same as Zenith | `tests.test_jarvis_hub`, `tests.test_phone_e2e`, the module's test (System view: `tests.test_jarvis_system`) |
| Kalshi page in Jarvis | `tools/web_public/kalshi/`, `tools/kalshi_kit/`, `engine/kalshi_publish.py` | same as Zenith | `tests.test_kalshi_page`, `tests.test_kalshi_publish` |
| Planner (Calendar) | its code: nq-dashboard `planner-backup` (read-only here); ours: `tools/planner_patches/*.patch` | applied at every publish by `scripts/add_planner.sh`, confined to planner/ | `tests.test_planner_addons` |
| Kalshi bot itself | the Oracle VM, `/home/ubuntu/kalshi` (real money) | not reachable from this cloud chat: its own server chat, or Remote Control on the VM (`claude remote-control` there) | — |
| Ascend | its own host (made with ChatGPT) | added in Jarvis with + (`docs/JARVIS_APPS.md`) | — |
| The PC (Windows) | NinjaTrader, the bot server | git auto-update; NinjaTrader login and live arming are the owner's | — |
| DAPHNE (strategy-tree search page) | `tools/strategytree/` (engine), `tools/web_public/tree/` (page, tree.json, demo.json, jarvis.json) | rerun `python -X utf8 -m tools.strategytree` (~3 CPU-min) for new data, then same as Zenith | `tests.test_strategytree`, `tests.shots_strategytree` |
| OLYMPUS kit (shared look, veil, one 3D quality `jfx`, perf rules of the nine 3D apps) | `tools/web_public/olympus/`, `docs/OLYMPUS_DESIGN.md` | same as Zenith (published with every build) | `tests.test_olympus_kit` (+ the app's own test) |
| ORACLE (market radar, Delphi temple) / ODEON (trade replay theater) | `tools/web_public/oracle/`, `tools/web_public/odeon/`; Oracle's Prophecy odds = `oracle/prophecy.json`, rebuilt by `python tools/oracle_prophecy_stats.py` from `research/lab/backtest_live.json`; Odeon's reels = `odeon/trades.json` (`tools/odeon_export.py`); design + budgets in `docs/OLYMPUS_DESIGN.md` (Oracle and Odeon overhaul) | same as Zenith (folders are copied whole) | `tests.test_oracle_odeon_fx` (+ `tests.test_oracle_page`, `tests.test_odeon_page`, `tests.test_olympus_kit oracle odeon`) |
| PANTHEON (free data gods: liquidity, rates, vol, calendar, COT, dollar, credit, crypto; council verdict; `states.json` for Data City) | `tools/pantheon/` (fetchers + builder), `research/pantheon/`, `tools/web_public/pantheon/`, `docs/PANTHEON.md` | the CRONOS nightly task `pantheon`; published with every build | `tests.test_pantheon` (`fast` without the browser) |
| CRONOS (nightly refresh of the OLYMPUS research apps) | `tools/cronos/`, `.github/workflows/cronos.yml` (+ `datacity.yml`), branches `cronos` / `datacity`, `docs/CRONOS.md` | main -> runs on its own schedule; the next cloud-monitor publish pulls the branches and stamps the cards | `tests.test_cronos` (`--quick` without the site builds) |
| PC speed (Surface + main PC) | `CLEAN_PC.bat`, `scripts/clean_pc.ps1`, `docs/PC_PERFORMANCE.md` | main -> the PC's auto-update; the main PC gets the `PC_KIT` copy (OneDrive or Desktop) | `tests.test_clean_pc` |
| PC storage clean (both PCs) | `CLEAN_STORAGE.bat`, `scripts/clean_storage.ps1`, site copies `tools/web_public/pc/CLEAN_STORAGE.bat` + `clean_storage.ps1` (kept identical), `engine/pc_health.py` (`storage` line) | main -> the PC's auto-update; the site `pc/` page has the download; the PC_KIT copy | `tests.test_clean_storage`, `tests.test_win_scripts`, `tests.test_pc_health` |
| PC care (both PCs) | `PC_CARE.bat`, `scripts/pc_care.ps1`, site copies `tools/web_public/pc/PC_CARE.bat` + `pc_care.ps1` (kept identical), `UNDO_PC_TUNE.bat` (undoes it too), `engine/pc_health.py` (`pc_care` line), `docs/PC_PERFORMANCE.md` | main -> the PC's auto-update; the site `pc/` page has the download | `tests.test_pc_care`, `tests.test_win_scripts`, `tests.test_pc_health` |
| OLYMPUS apps (61 in `jarvis/apps.js`, 2026-11-10; every-app table: `docs/OLYMPUS_MAP.md`) | `tools/web_public/<app>/`; the list, data sources and tests: section "OLYMPUS apps and tools" below; **a new app: the "Wiring checklist for a new app" there** | the lead wires new ones (`jarvis/apps.js`, `olympus/olympus.js`, the build tuple, root `sw.js`, then `python tools/apps_list_build.py`); published with every build | the app's own `tests.test_<app>_page` (+ `tests.test_olympus_kit`, `tests.test_apps_list`) |
| New 2026-11-04 apps: Ledger (real money), Inbox, Mnemosyne (`journal/`, trade journal), Settings | `ledger/` (`docs/LEDGER.md`), `inbox/`, `journal/`, `settings/` | same as every app | `test_ledger_page`, `test_ledger_freeze`, `test_inbox_page`, `test_journal_page`, `test_settings_page`; the Scoreboard card: `test_scoreboard_card`, `test_money_scoreboard` |
| Apps list + Zenith launcher (the ONE list of apps) | `olympus/apps-list.js` + `web_next/js/next/apps-list.js` (GENERATED by `python tools/apps_list_build.py` from `jarvis/apps.js` BUILT_INS + `olympus/olympus.js` APPS; `--check` fails when stale), `launcher.js` (+ the byte-identical `web_next/js/next/launcher.js`: the Olympus button, tiles by group, search, recent, status dots from each `<app>/jarvis.json`) | rerun the generator after ANY edit of `apps.js` / `olympus.js`, commit both outputs; then same as Zenith | `tests.test_apps_list` (`--static` = no browser) |
| Accessibility + readability (Dynamic Type / big text, ink guard, focus ring, auto aria-labels, live toasts, reduced motion / contrast) | `olympus/a11y.js` + `a11y.css` (ES5), `olympus/a11y-demo.html`, `docs/OLYMPUS_A11Y.md` (rules, contrast audit, which apps need the tags) | the lead inserts the two tags (`a11y.css` in `<head>`, `a11y.js` after `olympus.js`) page by page: done so far in `journal/` and `settings/` only | `tests.test_olympus_a11y` |
| Test tools: browser kit, area runner, release gate, site self-check | `tests/browser_kit.py` (shared launch, load-scaled waits, `BK.limit`), `tests/run_area.py`, `tests/run_gate.py` (+ `tests/hub_parts.py`, `tests/gate_static.py`), `tools/site_selfcheck.py` (read-only workflow step) | main | `tests.test_run_gate`, `tests.test_site_selfcheck`; the gate itself: `python -X utf8 tests/run_gate.py` (see "Test tools" below) |
| PC status card (both PCs) | `STATUS.bat`, `scripts/pc_status.ps1`, site copies `tools/web_public/pc/STATUS.bat` + `pc_status.ps1` (kept identical), `docs/PC_PERFORMANCE.md` ("STATUS.bat and the safety review") | main -> the PC's auto-update; the site `pc/` page has the download | `tests.test_pc_care` (STATUS part), `tests.test_win_scripts` |
| Effects library / transitions / app intros | `olympus/fx-*.js` + `docs/OLYMPUS_FX.md`; `jarvis/transitions.js`; `olympus/intro-app.js` | same as Zenith | `tests.test_olympus_fx`, `tests.test_jarvis_transitions`, `tests.test_app_intro` |
| Bridge (Claude x ChatGPT) | `tools/web_public/bridge/`, `tools/bridge_sync.py`, `tools/bridge_ingest.py`, `tools/bridge_jobs_build.py`, `handoff/` | the build runs `bridge_sync.publish` | `tests.test_bridge_page`, `tests.test_bridge_ingest` |
| Obsidian starter vault (Mind Teach page + demo brain; `python tools/obsidian_pack.py`, `--check` for stale) | `tools/obsidian_pack.py`, `tools/web_public/mind/starter.js`, `mind/starter/` (generated) | rerun the script when `athena/library.json`, `STRATEGY.md`, `mffu_rules.json`, `plans.json` or the writeups change; published with every build | `tests.test_obsidian_pack`, `tests.test_mind_page` |
| Money machines (2026-11-14: freelance gig pack, logo/brand kit, two Instagram plans + poster, 5 digital products: the Prop Eval Tracker + team D2's website templates, social media kit, agency starter kit, trader planner; rank-and-rent plan; plan and numbers in `docs/MONEY_MACHINES.md`) | `money_machines/` (gig_pack.json/.py, brand_kit.py + fonts/, content_plan.py + content_topics.py + plans/, ig_post.py, products/), `docs/GIG_PACK.md` (generated), `docs/shots/money_machines/` | main; nothing publishes: the owner lists gigs and products and posts himself (ig_post is a dry run without `--live` and his own token outside the repo); regenerate after edits: `python -m money_machines.gig_pack --md`, `python -m money_machines.content_plan --all`, `python -m money_machines.products.build_eval_tracker`; the 5 upload zips: `python -m money_machines.products.build_all --zip` (plain Python); rebuild one product: `python -m money_machines.products.build_<site_templates|social_kit|agency_kit|trader_planner>` (Chromium under the browser lock, LibreOffice) | `tests.test_money_machines` (a-e, no network; part e uses Chromium), `tests.test_digital_products` (a-h, no network, no browser) |
| Kalshi City + edges engine (edges, Lab, what-if, learned) | `tools/web_public/kalshicity/`, `tools/kalshi_edges.py`, `tools/kalshi_hypotheses.py` (Lab), `tools/kalshi_whatif.py`, `tools/kalshicity_learned.py`, workflow `.github/workflows/kalshicity.yml` (every 6 h, branch `kalshicity`), `docs/KALSHICITY.md` | wired 2026-11-04; the workflow refreshes it, the next cloud-monitor publish copies it | `tests.test_kalshi_edges`, `tests.test_kalshicity_page` |
| LITE mode (bot on low memory) + PC-off plan | `engine/lite.py`, `BOT_LITE.bat`, `scripts/bot_lite.ps1`, `docs/PC_OFF_PLAN.md` | main -> the PC's auto-update; the owner double-clicks BOT_LITE once | `tests.test_lite` (`--quick` = unit only), `tests.test_win_scripts` |
| Website agency (the website machine, 2026-11-14; `docs/AGENCY.md`) | `agency/` (lead finder on OpenStreetMap Overpass + polite site audit, 8-look site generator + self-check, pitch kit, pricing / money math, `run.py`), the owner's ONE settings file `agency/config.json` (gitignored, from `config.example.json`), `RUN_AGENCY.bat`, the CRM page `tools/web_public/agency/` (reads its own `leads.json`; notes in `localStorage['agency.crm.v1']`), demo batch `agency/demo/fort-collins/` | the owner runs `RUN_AGENCY.bat` on the PC; the page ships with the site once wired (docs/NEW_APPS_WIRING.md "Wiring AGENCY"); never sends email or calls | `tests.test_agency` (`--fast` = no browser) |
| Connect the day (calendars, shifts, weather, headlines, the iPhone inbox; 2026-11-14) | `tools/calendar_sync.py`, `tools/ics_parse.py`, `tools/day_feeds.py`, `engine/day_inbox.py`, `engine/live_site.py` (`/site/day/`, `POST_ALLOW`), `olympus/day.js`, Planner `workCard`, Jarvis copilot `my_day`, `CONNECT_DAY.bat`, `docs/CONNECT_DAY.md` | main -> the PC's auto-update; the PC report task syncs every 15 min once `CONNECT_DAY.bat` ran; PRIVATE: `data/day/` is served only by the PC's own link, never a site folder | `tests.test_calendar_sync` (a-k), `--only=l` under flock (Chromium) |
| Privacy (team Q2 audit 2026-11-14, `docs/PRIVACY.md`: who can see what, the owner's 3 settings) | `tools/site_privacy.py` (detectors + the build's LAST step: broker ids to the last 4 digits, personal folders / emails / ages / commit authors out, private files removed; `pc_report.public()` for the public ntfy status topic), `engine/live_site.private_why` (day/, money_out, household / agency: the PC itself or the Tailscale link only, never the home WiFi; also the inbox POST), `.gitignore` | main -> the PC's auto-update; every build scrubs (fails closed) | `tests.test_public_build_privacy` (`--fast` = no full build), `tests.test_private_link`, `tests.test_repo_secrets` (`--state <state.json>`, `--history`); `tests/run_area.py privacy` |
| The Me hub (personal life: money, cards, Apple Watch health, home WiFi / devices / this PC, freedom, dates, car, streaks; 2026-11-14) | `tools/me_hub.py` (builds `data/me/me.json`, reminders), `tools/me_cards.py`, `tools/me_health.py`, `tools/me_home.py` (+ `tools/me_oui.json`), `tools/me_life.py`, `engine/day_inbox.py` (kind `health`), `engine/live_site.py` (`/site/me/`), `tools/web_public/hub/me.js` + `me.css` (hub `me` in `olympus/gate-catalog.js`), Jarvis `health_*` intents, `docs/ME_HUB.md` | main -> the PC's auto-update; the PC report task runs `me_hub.maybe_run` every 15 min; PRIVATE: `data/me/` is served only by the PC's own link, never a site folder; typed inputs in `%USERPROFILE%\.olympus\me\` | `tests.test_me_hub` (a-i; j = Chromium under flock), `tests.test_hubs`, `tests.test_gate_page` |

- **Phone changes:** check in WebKit (the iPhone's engine) before shipping: `PLAYWRIGHT_BROWSERS_PATH=<dir> python -m playwright
  install webkit` + `install-deps webkit`, iPhone 13 / SE profiles (see the Jarvis worker notes under Infrastructure).
- **Moving the bot to another PC:** `MOVE_BOT.bat` / `scripts/move_bot.ps1` (`docs/MOVE_TO_MAIN_PC.md`): 1 = pack + retire the
  old PC (stop, auto-resume off, logon tasks removed, untracked `data/` + `.env.local.ps1` zipped to OneDrive\BOT_MOVE),
  2 = set up the new PC (winget Git/Python, clone, restore, ONE_TIME_SETUP). Never two PCs on the same accounts.
  **Fresh start, no old PC (2026-11-04, Surface overheating):** `-Fresh` / menu 3 / `FRESH_START.bat` / the one line
  `powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://demetrades2000-coder.github.io/nq-dashboard/pc/FRESH_START.ps1 | iex"`
  (site `pc/`: `tools/web_public/pc/FRESH_START.ps1` + a build copy of `scripts/move_bot.ps1`; plain files, no worker bump).
  Refuses (exit 1) when a DIFFERENT host's heartbeat (published `home.json` live.pc.t/host) is under 6 min old, or the site
  copy is under 20 min old and showed it alive (`-Force` overrides; unreadable = asks for SHUT DOWN). Then Git/Python, clone,
  pip, `python -m engine.eval_life --anchor-from-site` (board.lit -> main anchor, board.atlas -> its account; balance less
  today's P&L, as_of = previous weekday; shows numbers, asks Y/N), `scripts/no_chart_mode.ps1` (LE_Feed), `ONE_TIME_SETUP.bat`
  (Sim101 default, never arms live). Tests: `tests/test_fresh_start.py` (`LE_HEARTBEAT_FILE`, `LE_FAKE_HOST`), `test_win_scripts`.
- **Merges:** each merge restarts the PC's bot server once (when flat) and runs ~5 min of self-tests on a 3.6 GB PC: batch
  changes into one merge when possible.
- **Verify live** after a publish: the file on `https://demetrades2000-coder.github.io/nq-dashboard/...` (e.g. the worker's
  `CACHE` name), then one WebKit open of the live page.
- **Eval cards (owner 2026-11-03):** no "session X of 10" bars / dots / counters on any card (phone, PC copies, Jarvis);
  the room is shown as **"Drawdown left $X of $max loss"** (= balance - the MFFU max-loss floor, the number MFFU shows).
  Eval HQ / LIT kit / eval curve read the real PC account (`data.json` "accounts" source pc, anchored) before the cloud
  paper ledger (`live.eval`: its own trail, floor $48,000 / room $389 on 11-03 while the real 50K had $1,133 left).

## Hard rules (never break)
- **Futures data only:** TradingView CME `NQ1!` / `ES1!` exports in `data/` (5m 2021-11 → 2026-10-16; 1m for 2026). Never CFD,
  never Yahoo for testing. **No Yahoo live either (owner 2026-10-19, `live_model.json` `"no_yahoo": true`, `engine/pcbars.py`):**
  the PC bot trades on NinjaTrader MNQ bars (LE_BarFeed) + the TradingView exports + its own archive `data/nt_bars/`
  (gitignored); a stale NinjaTrader feed blocks new entries (FEED STALE), never a Yahoo fallback. The cloud monitor and
  watcher trade on the bars the PC pushes with its heartbeat (`heartbeat` branch: `bars_1m.csv.gz`, `bars_5m.csv.gz`); PC
  bars missing/stale -> no new paper entries ("waiting for NinjaTrader bars from the PC"). VIX/VXN from CBOE's own file.
- **No paid services.** The free PC-off path is the GitHub Actions cloud monitor (`.github/workflows/cloud-monitor.yml`); since
  no_yahoo it needs the PC's bars, so with the PC off it only waits (no paper entries).
- **Paper only.** Never arm live trading or place real orders. MFFU requires the owner to be present for live trading.
- **No secrets in the repo or chat.** `data/alerts.json`, `tv.json`, `tv_device.json`, `autostart.json`, `live_state.json`, `memory.db`
  and `.env*` are gitignored. Telegram/Discord keys live in GitHub Secrets only.
- **Frequency:** **2-4 trades a week** (owner, 2026-10-17; before: at least 2). Never make a filter that pauses trading for weeks the
  default; prefer size changes over skipping.
- **Owner requirements (2026-10-17), keep them in every report and on the dashboard:**
  - Implement what the research proves (better in 2026 AND 2021-25, 2-4 trades a week); store every experiment with its data
    (`tools/runlib.py` → `research/runs/`) and write it up in plain language (`research/writeups/`).
  - **Money, not only R:** every result shows net $ and $ per month next to PF / R.
  - **Eval speed on the MFFU 50K:** an eval should be passed or failed within **2 weeks** and never take more than **3 weeks** to
    pass. Scored as `p10/f10` (pass/fail within 10 sessions), `dec10` (% decided in 10), `p15/f15`, `slow_pass` (% of passes
    slower than 15 sessions) and `pass_med` (median sessions to pass) in every run. The live strategy as of 2026-10-17 decides
    only 19% of evals in 2 weeks (2026) and 6% (2021-25): a fast-eval sizing mode is open work.
  - The strategy is written in plain language in its own area of the dashboard (Strategy page, versioned, with its numbers).
- **Stops** go beyond the sweep extreme, i.e. the high/low made before the IFVG, never at a fixed distance. **Wide stop means less
  risk**: size follows the stop.
- **Owner's trading principles (2026-10-18, keep them):** the stop sits at the protected low/high (1 tick beyond the
  sweep extreme), never a random or fixed distance; a bigger stop means fewer micros (de-risk), a small stop allows more;
  one clear target (the VIX-band objective, banked at 8R), no greed; size follows the stop and the target. Under two_week
  sizing (fresh eval, 2026) micros fall from a median 14 at <20-pt stops to 4 at 60+ pts; $ at risk stays $450-$660 median,
  capped near $1,000 by the 60% room and the soft daily loss.
- Every result is judged on 2026 **and** on 2021-25 (5 years). A change is adopted only if it holds in both and keeps 2+/week.
  Report trades/week, % weeks with 2+, PF, net, max DD, and MFFU eval pass/fail within 2 weeks and 1 month.

## Live strategy (locked 2026-10-18): LIT, `live_model.json` (= `live_model_lit.json`) + `STRATEGY.md`
- **Owner's order (2026-10-18): LIT is the strategy, tuned and judged on 2026 only** (Jan 2 - Oct 16). Pick on Jan-Jun 2026,
  check on Jul-Oct 2026, report both halves; 2021-25 is a reference line, never a gate. This replaces "better in 2026 AND
  2021-25" for LIT changes only; every other hard rule stays.
- **Rules** (`engine/lit.py` run_x, params in `live_model.json` "lit" = `research/lit/lit_final.json`): sweep of any LIT level
  (session boxes, PDH/PDL, PWH/PWL, PMH/PML, NWOG/NDOG, build-ups), >= 0.5 ATR deep, inducement swing taken first (<= 1 ATR,
  <= 36 bars), displacement body >= 0.8 ATR, 5m CISD close; limit at the CISD level for 30 min, then a 1m CISD within 20 bars
  -> next 1m open; stop 1 tick beyond the sweep extreme (planned 8-80 pts; the 1m fill can widen it to ~88); target 18:00 open +/- 1 VIX one-day move, >= 1.5R, banked
  at 8R; BE at 1R, flat 15:55, 1 trade/day, entries 02:00-15:30. Size $800 up to 20 pts, 800x20/stop, max 40 micros; no
  cold-streak filter. Eval-safe switch (off): `how_out 0.5`.
- **Loss pack (on, 2026-10-18, `research/writeups/lit-losses.md`):** weekly stop (after 2 stop-outs in a calendar week, half
  size for the rest of it: `wk_stop`) and the Monday rule (once Monday took Friday's high only shorts, Friday's low only longs:
  `monday`). Sizing `lit_sizing.mode` **two_week (ON 2026-10-18, owner: pass evals within 2 weeks)** = "one winner passes":
  micros so the target covers what is left to +$3,000, capped at **40% of the eval room** (`two_week.room_f 0.4`, `two_week_until 80`, owner "yes 40%" 2026-11-14 per research/writeups/eval-guard-2026-11-13.md; 0.8 from 2026-10-25, owner
  2026-10-25 "evals: one hit, make it quick"; 0.55 on 2026-10-24, 0.6 before) and the $1,000 soft daily loss, max 40,
  min 1, **no eval weekly loss stop** (`wk_loss_usd null` since 2026-10-25; uprisk.md MC: 2-week pass/fail H1 52.9/17.8, H2
  58.6/20.9 vs 53.0/3.6, 53.7/2.2 at room 0.55 + $1,200 weekly stop; dashboards read the matching row of
  `research/lit/uprisk_eval.json` via `tools/build_web_dashboard._live_eval_odds`), the weekly half size off (config C, run `lit_2wk_rec`, `lit-two-week-eval.md`: 2-week pass H1 52.9% / H2 50.7%, fail 8.4 / 2.9,
  $174 / $181 per 2-week pass, max risk ~$990 a trade); sessions from `lit_sizing.eval_start` (PC start cfg `eval_start`
  overrides); **no reset (owner 2026-10-18):** after session 10 the eval goes on in safe_eval (`two_week_until 10`, `after_mode`;
  `tools/lit_eventual.py`: eventual pass ~80/77%); $1.90 commission; min-days 1-micro trade after an early target; mode
  `funded` wired on the funded extra account (multi_account, OFF until `--to-funded`; `lit-funded-sizing.md`); missing target / eval state -> eval mode.
  **Eval lifecycle (2026-10-20, `engine/eval_life.py`, `tests/test_eval_lifecycle.py`):** pass ($53,000) -> no new trade on
  that eval in every eval mode (`sizing.eval_lock`; was missing after session 10), 1-micro min-days trade if < 2 traded days,
  push "EVAL PASSED 🎉 next steps"; fail (room <= 0) -> no trade, push "EVAL FAILED"; funded switch = `python -m
  engine.eval_life --to-funded --account "<Name>" --start <day>` (extra account, mode funded, disarmed; `--plan builder25k`
  for a passed 25K, id mffu25k_funded), payouts `--payout`. **Funded path (2026-10-25, `research/writeups/funded-path.md`,
  `tests/test_funded_life.py`):** `engine/funded_life.py` = the MFFU Builder Sim Funded tracker per funded account (buffer
  $2,100 / $1,100, ask line $53,600 / $26,850, cycle profit, best day vs 50%, 2 days a cycle, 48 h first payout, request
  $500-2,000 / $250-1,000, MLL at start + $100 after the 1st payout, payouts n/5; pushes "PAYOUT READY: request $X",
  "consistency: best day is N%...", lost, graduated; never requests a payout), run by `LiveBot._funded_life_tick`, data.json
  "funded_life", phone Money > Funded & payouts (hub.js v8, sw le-public-v35), PC Goals (cc.js, sw le-shell-next-v19).
  **Funded sizing (owner 2026-10-25, `research/writeups/uprisk.md`):** `lit_sizing.funded` + preset mffu_builder_50k = 60% of
  the room, <= $1,500 (x20/stop beyond 20 pts), a winner <= $2,000, skip_breach (H1/H2 $929 / $915 a month to you vs $889 /
  $835, first payout ~23-26 sessions vs 33, 0% lost); 25K preset 60% / <= $750 / winner <= $1,000 ($445 / $405).
  `funded.cons_aware` (built, OFF: -$76/mo H1). Sizing tests pin the old values in `tests/sizing_pins.py` (PINNED) and check
  the live ones there (`live_checks`): a switch change = update OWNER there + the docs. Money plan `tools/funded_path.py`
  (runs funded_path_*): Zlarior 50K funded $835/mo H2 ($889 H1), 0% lost, first payout median 33 sessions; ATLAS 25K
  $318 / $622, 13.6% lost H2 (superseded: account-B rules + live preset in `atlas-funded.md`, $517 / $582, 0% lost,
  8.5% stuck H2); Zlarior 25K $389 / $329.
  Eval weekly loss stop wired, OFF since 2026-10-25 (`"wk_loss_usd": null`; `1200` switches it back on, both model files). Other modes:
  eval ($800 up to a 25-pt stop + 60% room cap, run lit_tight_eval_800_25_room60) | normal | fast_eval ($800 up to a 40-pt
  stop) | safe_eval (micros capped at 60% of the eval room); see `lit-experiments.md`.
- **Upgrades (2026-10-20, STRATEGY.md rule 11): 15-minute check + BE+costs ON** (owner approved): `t_check
  {"at":15,"x":0.3,"mfe":0.5}` (15-minute cut), `be_off 1.25` (BE = entry + 1.25). **Scale-in built and safety-reviewed,
  OFF** (`"scale_in": null`) until the owner's Sim roundtrip passes (`python -m engine.ninjatrader --sim-roundtrip-add` on
  Sim101, market open; the OIF quantity-only CHANGE `CHANGE;;;;N;;0;0;;;id;;` is unconfirmed on a real install;
  `docs/DAILY_CHECKLIST.md` "Switch on scale-in"; on = `{"pb":0.25,"f":1.0,"rat_k":1.0,"min_rk":2.0,"n":1}` in both files). Built
  2026-10-30, OFF: "lit_sizing" `"scale_in_from_session": 5` (no add before eval session 5) and `"scale_in_funded": false` (no add once
  funded) in `live.py _add_qty` + `cloud_monitor.lit_add_usd` (`tests.test_scale_in_switches`); `lit-edge-2026-10-30.md`: with scale-in
  on, eval path +$3.9k / +$8.6k (H1 / H2) vs today, 2-week pass 60.5 / 58.0 vs 57.1 / 52.2 (owner decides, after the Sim roundtrip).
  Switch one off/on in live_model.json / live_model_lit.json "lit", rerun `tools/lit_losses.py live` (checks the trades
  against the stored run of the switch set) + dashboard data.
- **Results LIT + pack + t_check + be_off** (run `lit_live`, rebuilt 2026-10-20 = `lit_adopt_t15_be_off`; the 2026-10-18
  version is run `lit_live_2026-10-18`; costs in, LIT size rule): 2026 120 trades, 2.91/wk, win 55.0%, PF 4.07, +$43,385
  ($4,423/mo), DD -$2,196, eval 2 wk 31.6/1.0, 1 mo 57.3/4.9, pass rate 90.8%; H1 (picked) PF 4.98 +$33,891; **H2 (check)
  PF 2.69 +$9,493 (~$2,550/mo): quote the H2 rate**; eval path (two_week, runs `lit_adopt_t15_be_off_eval` /
  `lit_idm_eval_t15_be_off`) H1 PF 4.02 +$34,234 / H2 PF 2.20 +$9,059, 2-week pass/fail 57.1/5.9 and 52.2/0.0; 2021-25
  reference PF 1.01 +$1,211 DD -$19,436. Thin sample (13 cuts). **With scale-in (after the Sim check**, run `lit_adopt_all3`):
  2026 PF 4.43 +$59,698, H1 PF 4.94 +$44,507, H2 PF 3.48 +$15,192; eval path H1 +$53.1k / H2 +$17.3k, 2-week 58.0/2.5 and
  52.2/0.0. **Before** (2026-10-18
  pack only): 2026 PF 3.66, +$41,734 ($4,254/mo), DD -$2,315, eval 2 wk 26.7/1.9, 1 mo 55.3/3.9, pass rate 95.5%; H1 PF 4.44
  +$32,773; H2 PF 2.46 +$8,962; eval path 2-week 52.9/9.2, 50.7/2.9; 2021-25 PF 1.01 +$1,275 DD -$20,462 (no 1m data there). Needs 1m bars
  (5m only: +$6.6k in 2026). 95 of 120 trades enter 02:00-08:00 ET: NinjaTrader and the PC must be running from ~01:55 ET. **PC timing fix (2026-10-18):**
  the PC bot decides on the 1m CISD close and routes ~3 s later (was ~95 s; `tests/test_lit_timing.py`, `tests/test_lit_oif.py`,
  `lit-live-fills.md`); sizes from the forming bar's open (`le_feed\MNQ_1m_open.csv`, LE_BarFeed OnMarketData). Owner goes live
  on the eval himself (`docs/GO_LIVE_TONIGHT.md`); never arm it for him.
- **Live loop:** `engine/lit_live.py` (PC `engine/live.py`, cloud `tools/cloud_monitor.py`) on the bars from the previous
  month's first day + 1m bars (data/NQ_1m.csv + NinjaTrader 1m on the PC / the PC's pushed bars in the cloud; no Yahoo). `python -X utf8 -m tests.test_lit_live` replays every
  2026 session through it (120/120 trades identical with the pack; `python tools/lit_losses.py live` stores run `lit_live`). `tools/export_backtest.py` exports the LIT replay when the model is lit.
- **Live money at the real commission (2026-10-26, audit follow-up of 2026-10-25):** one constant `engine/sizing.LIVE_COMM`
  = $1.90 a micro round trip (MFFU / Tradovate). Every live booking uses it: `lit_live.live_booked` (trades, open position,
  days, day_pnl, `comm_rt`), `live.py` (routed exits, scale-in adds, kill flatten + its mark), the cloud paper ledger
  (`lit_add_usd`), `multi_account`, hence the eval room / anchor / pass-fail (`eval_life`, `sizing.eval_state`); the sizing
  ceilings (`TW_COMM`), guards, Bot Brain, fill audit and day brief alias it. Research keeps `lit.COMM` $1.40 (every stored
  run, `tools/lit_final.py`, `research/runs/`); a research trade books live $0.50 less per micro: run `lit_live` 2026
  +$43,820 -> +$43,502 (-$318 over 636 micros, -$33/mo, mean -$2.65 / max -$17 a trade, no trade changes sign), H1 +$33,901
  -> +$33,666, H2 +$9,919 PF 2.91 -> +$9,836 PF 2.88 (~$2,650/mo). Trades, micros, times unchanged (`tests.test_lit_live`
  compares the research $ re-priced by `booked()`; `test_lit_exit_route` / `test_lit_scale_in` / the NinjaTrader self-test
  likewise). Ledger rows booked before stay at $1.40 (finished paper trades are never rewritten); refresh the anchor
  (`python -m engine.eval_life --anchor`). On the eval the room / need now see the true balance, so a two_week size can be
  1 micro smaller in a rare case (A4: room overstated by up to $33 per 10 sessions before).
- **Shadow:** the cloud monitor also runs the old engine (`live_model_engine.json`) as a paper ledger, state key `shadow`,
  README "Old strategy (shadow, paper)", no alerts. The PC bot runs the old engine with `"model": "engine"` in its start cfg.
- **Apps on LIT (2026-10-18):** both dashboards show LIT everywhere; `tools/lit_dash_data.py` rebuilds the LIT Monte Carlo
  (`research/lab/montecarlo.json`) and intraday heat; `engine/lab_scope.py` scopes the Lab to LIT runs (reference `lit_live`).
  The old engine lives under an **Archive** group on both apps and in `research/archive/engine-2026-10-17/` (README with its
  numbers and the switch-back steps; old Monte Carlo/heat files; `tools/research_mc.py` / `research_intra.py` write there).
- `tools/runlib.py`, `tools/pine_parity.py`, `tests/test_live_dryrun.py` read the engine lock from `live_model_engine.json`
  (engine.lab_adapter.engine_config_raw) while live_model.json says lit.
- **Live learning (2026-10-25, `engine/live_learning.py`, `research/writeups/live-learning.md`, `tests/test_learning_live.py`):**
  owner order "learn like a human trader without emotion". (1) Execution learning per bot (lit / atlas) from the PC's real
  fills (`fill_audit.live_trades` + the ledger's `src`): entry / stop / target slippage ticks, signal->order / fill latency,
  commission from `broker_balance` daily real cash; `reserve_ticks` = ceil(p75 adverse slippage of the last 30 broker fills,
  >= 5 obs), clipped 1..4; comm clipped $1.90..$4.00 -> `logs/learning/costs.json` (PC fill-audit Watcher after each audit;
  heartbeat block `learn`). `lit_sizing.learn_costs` (false in both live_model files): true = `sizing.cost_reserve` re-prices
  every cap (room strict, two_week room_f / safe_cap share, soft daily loss, wk_loss_usd) at (stop + reserve x 0.25) x $2 +
  comm, never more micros (also `second_qty` with the atlas reserve); "scale" also shrinks every size in proportion
  (rejected: 2026 journal +$48.7k -> +$43.5k). Eval MC: neutral (p10 H1 51.5 = 51.5, H2 52.2 = 52.2, f10 0). (2) Review
  journal: every finished Zlarior (paper ledger + PC trades vs this run's lit_live twin), ATLAS (paper ledger vs this run's
  second.run, `_LIT_IN["second_run"]`) and ATLAS v2 (vs the member trade) trade -> state `learning_live.reviews` (matched /
  missed / extra, diff, gap $ / R, exec $, cause code, MFE / MAE; PC adds brain rule checks after the session,
  `logs/learning/reviews.jsonl`). Weekly summary Mon-Fri with the health band (lit) / scorecard (atlas), pushed Sunday
  >= 17:00 ET (kind weekly, key learnweek:<monday>). (3) `suggestions()`: lit_learn shadow knobs with "would have changed $X"
  (lit_learn.simulate) + the approve / revert command; the cost reserve card. UI: phone `learning.js` + `learncore.js`
  (pages learning / atlearn in clean.js Results), PC `web_next/js/next/learning.js` (learnlit / learnatlas), learncore.js
  byte-identical in both; `GET /api/next/pc/learning`; data.json `learning_live`.

- **Prop-firm prices: use the owner's real prices, not list prices.** MFFU runs discount codes; the owner pays Builder 25K $63 and Builder 50K $91.80 (2026-10-18, one-time, $0 activation). Look for current codes before quoting any firm's price. LIT on 60 plans: `research/writeups/lit-prop-firms.md` (eval best-day rules fail LIT; Builder 50K ~$116 per funded account).

## Second strategies (paper, 2026-10-22): `engine/second.py` + `second_model.json`
- **Name: ATLAS (owner 2026-10-22 evening: "LIT on the 50K, the new one on the 25K, then we scale")** = EMA + MACD + S/R pooled
  on account B. Display name only (internal keys stay `second` / `account_b`): phone bottom tab ATLAS (Home · Brain · ATLAS ·
  Trades · Money · More; Strategy folded into More), PC top-level ATLAS, Home/Today two cards "LIT · 50K" / "ATLAS · 25K",
  `SecondUI.atlas` / `twoCards` (secondcore.js v5), data `second.atlas` = `research/second/atlas.json` else the account-B 25K
  research (`engine/second.atlas_info`), README "ATLAS (paper)", pushes "ATLAS PAPER ...", account label "ATLAS <NT name>".
  Test `python -X utf8 -m tests.test_atlas_ui [--shots <dir>]`.
- Three research winners run next to LIT, **paper only** (no adapter / NinjaTrader import, `tests/test_second.py` checks
  it; `live_model*.json` untouched): `ema_lon_vix` (London EMA pullback, `second-ema.md`, run ema2_lon_vix), `macd_sweep`
  (MACD divergence at a sweep, `second-md.md`, md2_best), `sr_nyreclaim` (S/R NY sweep-and-reclaim, `second-sr.md`,
  sr2_nyreclaim_*; "own account recommended": with LIT it slightly worsens LIT's H2 eval path). $500 risk a trade each.
  Fourth, cloud only (`"cloud_only": true`, never on the PC route): `lit_asia` = LIT + Asia slot paper shadow
  (`lit-more-entries.md` lead 1, run lit_more_ent_asia_slot_rr3: lit_live.run with live_model.json "lit" + all hours,
  2 a day, 1 per session, Asia banked at 3R; LIT size rule), also under state key `lit_asia`.
  **PC route for the Asia slot: fixed 2026-10-22, still OFF** (owner's switch, JSON in `lit-more-entries.md`): with LIT
  `all_hours` on, guards / NinjaTrader gate + flat watch / safety flatten / autoupdate hourly follow the CME day 18:00->17:00;
  `lit.candidates(evening=True)` no longer skips the forming day before its 50th bar (was: evening entries seen at 22:10).
- **Stop-hunt candidates (2026-10-23, PAPER, `research/writeups/stophunt.md`):** `sh_asia` (Asia resweep hunt, 18:00-02:00,
  pick sh_asia_resweep) and `sh_trend` (trend inducement hunt, any hour, sh_trend_idm5), plugin kind `stop_hunt` =
  `tools/stophunt.live` (the research pipeline on LIT's window, cut data, OPEN mode; `engine/stophunt.bars` / `build_pools(types=)`;
  numba optional, not in requirements-cloud). `"candidate": true`: never routed (load_cfg / set_route refuse), not on account
  B, not ATLAS members; ATLAS page "Candidate members (paper)" (secondcore.js v6 `candCard`, phone sw le-public-v28),
  own scorecard bands (`second_scorecard.CANDIDATES`). Evening: the PC bot runs them every bar 24/5 (heartbeat / live.json);
  the cloud cron has no evening runs (01:32 ET is the first), so it books the night's trades at its next run. Test `python
  -X utf8 -m tests.test_second_stophunt [--quick]` (2026 replay 78/78 + 59/59).
- **ATLAS v2 PAPER SHADOW (2026-10-25, `engine/atlas_v2.py`, `research/writeups/atlas-v2.md` candidate 1b):** ATLAS +
  sh_asia + sh_trend at weight 0.5 + a new eval when room < $200, on a simulated Builder 25K next to the live ATLAS
  (= tools/atlas_v2.score on the members' paper trades: need size via `account_b.qty(key=)`, one position, max 2 a day,
  no-hedge vs LIT trades + armed setups, HEDGE cut, $600 soft loss). Never routed. Cloud: state key `atlas_v2` (own frozen
  ledger + eval tracker, from state `second` ledgers + LIT's run); PC: `LiveBot._second_tick` paper thread ->
  `data/live_state_atlas_v2.json` (gitignored), heartbeat `second.atlas_v2`. Scorecard bands
  `research/second/atlas_v2_scorecard.json` (`python -m engine.atlas_v2 build`; hunts: decide after 20+ hunt trades).
  Pushes kind `second` "ATLAS v2 PAPER ...", OFF by default (`second_model.json` `"atlas_v2": {"push": false}`). Card: ATLAS
  page (secondcore.js v8 `atlasV2Card`, data.json second.atlas_v2, /api/next/second atlas_v2; phone sw le-public-v31).
  `account_b` keys `"weights"` / `"min_room"` are built but OFF (absent = today's sizing / $100 stuck).
  **Zombie-eval rule (2026-11-15, `2026-11-15-atlas-deep.md`, `tools/atlas_deep.py`, runs `atlas_deep_*`), built, OFF,
  adopt-candidate (owner decides):** `account_b` `"eval_min_room": 200` (the EVAL's stuck line only; funded keeps
  `min_room` / $100) + `"last_bullet": 0.8` (need size 0 on a low room -> 1 micro when its full stop-out fits 80% of the
  room, then dll_guard; `engine/account_b.last_bullet`). Half of ATLAS's 2026 signals were never traded (idle low-room
  evals: 2.1 / 1.6 trades a week); with the rule 4.0 / 3.0, owner slot $639 / $459 / $16 a month vs $579 / $394 / $11
  ($43 evals), 2-week pass 67.2 / 43.5 vs 65.5 / 43.5. Test `python -X utf8 -m tests.test_atlas_deep` (16 checks, parity
  with the research sizer). Test `python -X utf8
  -m tests.test_atlas_v2_shadow [--no-cloud]` (2026 replay = the research executor exactly; the stored run file was scored
  on an older unit cache: 206/207 trades identical, $ within 0.1%).
- **BLITZ HIDDEN on every dashboard (owner 2026-11-15: "Zlarior and ATLAS only for now ... just know it's still there"):**
  one switch, `dashboard_view.json` `"hidden_bots": ["blitz"]` (default; `[]` = back), `engine/hidden_bots.py`. Its engine,
  paper ledgers, cloud state and heartbeat blocks run as before (paper, never routed). Hidden = scrubbed out of data.json /
  home.json (`live_board.site_block`, the build's last helper, in place), live.json / liveview / holo files (`live_publish`),
  the PC's GET /api/* answers (`ScrubMiddleware`, server.py; `/api/next/blitz*` untouched); every file says `hidden_bots`;
  pages ask `window.OLY_HIDDEN.has('blitz')` (defined at the top of main.js, jarvis/data.js + brain.js, web_next routes.js; the other apps read localStorage oly.hiddenBots or home.json's hidden_bots); no tab, cards, orbit,
  feed tab, Start card; `#/blitz` says "hidden, still on paper". Pushes: BLITZ paper / Sim silent (`blitz.push_on`, narrator,
  `AccountC._send`); the Sunday readiness push drops its line. Real money is never hidden (account C armed -> shown).
  Test `python -X utf8 -m tests.test_hidden_bots`.
- **BLITZ, the scalper (strategy 3) PAPER SHADOW (2026-10-28, `engine/blitz.py`, `research/writeups/scalp-na-mffu.md`):**
  the noise-area 1m scalp + the prior-day range filter (`prng>=0.8`: trade a day only if yesterday's 09:30-16:00 range >=
  0.8 x the mean of the last 14 such ranges, yesterday's included, as `tools/scalp_na_lib._day_ctx`); band = 09:30 open x
  (1 +/- sigma), sigma = 14-session mean of |close / 09:30 open - 1| at that minute; checks at the 1m closes 11:00, 11:30 ...
  15:30 (research window 10:30-15:30, every 30 bars from 09:30: the first is 11:00); close above / below = long / short at the
  next open + 1 tick; stop 1.5 x ATR(14) of 5m; trail 1.5R after +1R (20R limit never reached); out after 30 bars / 15:55;
  one position, 6 a day, -3R day stop; $1.90 + 1 tick per market / stop fill. Option (off): `second_model.json` `"blitz":
  {"unfiltered": true}` = the plain NA of `scalp-momentum.md` (30% eval size). Two PAPER ledgers, never routed (no adapter /
  order import; `live_model*.json`, `second_model.json` untouched; optional read-only `"blitz": {"on": false}` / `{"push": true}`):
  (1) simulated Builder 25K eval at 40% of the room, <= $600 (na_sizing pick), stuck room $249.56, new eval $63 after pass /
  fail / stuck = `tools/scalp_na_lib.run_eval` back-to-back path; (2) **BLITZ on a funded 50K next to LIT**: its own Engine
  where a candidate is dropped while LIT holds a trade or has a setup armed at the signal close; skipped when LIT is in a trade
  or ATLAS holds the other side at the entry; closed at the bar open of LIT's entry (LIT FIRST) / an opposite ATLAS entry
  (HEDGE); size `div_stack.na_q` (20% of the room, <= $450, the $1,000 DLL left, 40 micros), up to 6 a day; simulated funded
  50K ($2,000 EOD trailing, lock start + $100) with BLITZ's own P&L only, no payouts. LIT = the bot's lit_live run (trades,
  position / enter_now, armed setups + pending signals, windows kept in `lit_armed`); ATLAS = the members' paper trades (EMA /
  MACD / S/R) + account B's open trade (`LiveBot._blitz_atlas_open`). Parity: `backtest(df)` and `Engine` (one closed bar at a
  time, JSON state; a half day's last bar found by the next bar or the clock at 16:00) = `research/scalp/na_best_trades.json`
  330/330 (unfiltered = `mo_best_trades.json` 481/481); the 50K ledger on the research's LIT / armed / ATLAS trades =
  `tools/scalp_na_combo` units (lit_flat -> cut_on -> yield_to) 312/312. PC: `LiveBot._second_tick` paper job (bg_worker
  `job_second` after `second.run` / thread) -> `pc_step(<state dir>/blitz_state.json, df1, now, res, second, atlas_open)`
  (gitignored, in memory between polls, ~2 ms a new bar) -> `LiveBot.blitz`, heartbeat `blitz` (compact: state, 25K eval,
  `funded50`), Live View purple layer (`liveview_api.blitz_layer`: band lines, signals, PAPER positions of both ledgers;
  the chart JS does not draw `scalp.lines` yet), narrator kind `blitz` (strat scalp, never pushed by default). Cloud: state
  key `blitz` next to `atlas_v2` with LIT's run + the ATLAS ledgers (cold start warms 35 days of data/NQ_1m.csv + PC bars),
  pushes kind `second` "BLITZ PAPER ..." recorded unless `blitz.push`, README lines. Replay H1 / H2: 221 / 109 trades, PF
  1.63 / 1.49, $150 a trade +$5,560 / +$2,143; 25K eval path +$7,193 / +$4,726 (4/2, 3/2 pass / fail+stuck), after fees
  +$6,752 / +$4,411 (~$1,108 / $1,188 a month), 2-week pass / fail 31.1/10.1, 34.8/2.9; 50K next to LIT (research LIT /
  ATLAS trades) 207 / 105 trades, +$11,750 / +$7,923 trading P&L (~$1.9k / $2.1k a month at $400-450 risk, no payouts: the
  research's whole-slot gain after MFFU payout limits is +$301 / +$290 a month). Test `python -X utf8 -m tests.test_blitz
  [--cloud]` (~65 s).
- **Account C = BLITZ routed to its OWN MFFU Builder 25K (2026-10-29, owner "the scalping on a 25"), built, OFF:**
  `engine/account_c.py` (LiveBot.acct_c, `_account_c_tick` right after LIT's routing, before account B and the read-only work: the entry latency matters), plain-language rules + bands + kill switch in
  `BLITZ_STRATEGY.md`. Later-break size ON by default (owner approved 2026-10-31; `"later_break": false` turns it off) = eval size x0.5 on the day's first band break of a
  side, x1.75 on a later one (`engine/blitz` signal `brk_n`, `account_c.qty`, `tests.test_blitz_later_break`, pick v2).
  Switch = local `data/account_c.json` (gitignored; absent / null = the bot is exactly as before: no
  adapter, no heartbeat key) `{"account", "plan": "builder25k", "eval_start", "armed": false}`; CLI `python -X utf8 -m
  engine.account_c --account "<Name>" --plan builder25k --start <day>` | `off` | `--status` | `--resume` | `--to-funded`
  (refused when the NinjaTrader self-test fails; a real Name is allowlisted, never armed). Own adapter (OIF tag `acctc_`,
  `ninjatrader_state_acctc.json`), state `live_state_acctc.json`, startup reconcile, guards (order sanity stop cap 250 pts:
  37 of the 330 2026 stops are over LIT's 100), live gate as account B (armed + the phrase at the bot's start +
  NINJATRADER_LIVE). Rule = `blitz.Engine` on the closed 1m bars (default `blitz.DEFAULT_PARAMS`; the block's "params" plugs
  a later rule pick by config only; `research/writeups/blitz-25k.md` = no rule change): signal close -> MARKET at once
  (late > 50 s = not chased), stop + OCO 20R, the model's trail -> stop CHANGE (tighter only), 30-bar / 15:55 (+60 s clock) /
  CME early close (flat -5 min, no entry -15 min) exits, 6 a day, -3R; a candidate opposite LIT / ATLAS is masked at the
  signal (`AccountC._gate`: no model trade, the slot stays free, as blitz-25k.md measured it); any other block keeps its model
  trade on paper (the slot is used, as the research eval). Size = blitz_25k_pick.json "eval_25k" (40% of the room for
  sessions 1-4, the full room from session 5, <= $600, <= 0.9 x the $600 DLL left, 20 micros; `"sizing": "paper"` = flat 40%);
  stuck room < $249.56; funded (owner's switch, new Name, disarmed) 10% / $150 / +$400 day stop ("funded_25k").
  No hedging, LIT > ATLAS > BLITZ: C blocked while LIT holds / enters / has a setup armed the other way (the stricter block),
  B holds or closes the other way, an extra account holds it; LIT's opposite entry -> `LiveBot._hedge_clear` -> `_hedge_clear_c` (C closed at market
  first, LIT routes once confirmed flat, else HEDGE WAIT / "HEDGE BLOCKED: BLITZ close not confirmed"); ATLAS's ->
  `AccountB._c_yield` right before B routes. Never-placed orders as account B (not booked, push). Performance contract
  `account_c.score`: 20+ finished trades with avg R or PF(R) under the 2026 bootstrap p5 (20: -0.150 / 0.62, 40: -0.061 /
  0.83, 100: +0.019 / 1.06), or 6 losing R-days in a row -> PAUSED (no entry on C, push); `--resume` = "resume_after" in the
  block. Data (only when on): heartbeat `account_c` (`AccountC.hb_block`), `accounts.blitz_section` (source `pc_blitz`, so
  Zlarior-only views never read it), live board `blitz` card + `accts` + trade log acct "blitz" (`boardcore.js` draws the third
  card, mini card and a BLITZ trade filter when the block is there, 2026-10-29 night), Mission Control `pc_cc_api` home `blitz`, /api/next/board, narrator REAL / SIM
  rows + pause, live.json / cloud state `pc.account_c`. Start page: card "BLITZ · 25K" (Set its 25K, Sim test = Sim101,
  Arm BLITZ with the typed phrase, Off; Add account bot BLITZ; Passed → funded; `go.set_blitz` / `arm_c` / `blitz_status` /
  `_c_to_funded`, POST `/api/next/start/blitz`, `/blitz/arm`; a running bot picks a change up once C is flat). Replay of
  2026 through account C's live loop (paper adapter, minute polls, a new $63 eval after each end): all 330 model trades =
  `blitz.backtest`; with the speed size routed H1 182 / H2 82, +$10,900 / +$4,709 inside evals (PF $ 1.62 / 1.60), 14 passes,
  0 fails, 12 stuck (room < $249.56 ends an eval before the floor: research counts it dead), never paused; inside-eval $ is
  not paid money (blitz-25k.md whole slot: $270 / $37 / -$40 a month; the losing-days streak counts all of a day's model
  trades, routed or not: the routed ones alone hit 6 in May 2026 because the eval / daily loss stopped days early). Test `python -X utf8 -m
  tests.test_account_c [--quick]`.
  **Adopt-candidate, NOT built (2026-10-30, `atlas-blitz-edge-2026-10-30.md`, `research/scalp/blitz_25k_pick_v2.json`):**
  the later-break eval size, rule unchanged:
  - x0.5 on the day's first band break on a side, x1.75 on a later same-side break (the day's count of check closes beyond
    the band on that side, every check counted, >= 2);
  - f x m capped at 1.0 of the room, $600 cap x m; funded unchanged.
  - 25K 2-week pass / fail 47.9 / 23.5, 36.2 / 21.7, 24.7 / 48.4 (today 36.1 / 37.8, 36.2 / 34.8, 20.4 / 50.2); slot
    $286 / $52 / -$39 a month (today $270 / $37 / -$40).
  - Needs a per-day break counter in `blitz.Engine` + `account_c.qty`; owner decides.
  **Owner's turn-on (next week):** 1. buy the Builder 25K for BLITZ and connect it in NinjaTrader; 2. Start page > BLITZ ·
  25K: its Name, Set BLITZ's 25K, Arm BLITZ (type I ACCEPT LIVE RISK); 3. Start trading. Console for step 2:
  **Owner's turn-on (next week): `docs/BLITZ_GO_LIVE.md`** (3 steps: buy + log in the 25K in NinjaTrader; Start page > BLITZ
  · 25K: its Name, Set BLITZ's 25K, Arm BLITZ with I ACCEPT LIVE RISK; the Go-live check all green, console `python -X utf8 -m
  engine.account_c --preflight`; plus what the phone shows on day 1). Console for step 2:
  `python -X utf8 -m engine.account_c --account "<the 25K Name>" --plan builder25k --start 2026-11-02`.
  **Go-live check (2026-10-29, `engine/blitz_preflight.py`, read-only):** `facts(bot | None)` + pure `lines(facts)` -> one item
  each {key, label, state good|bad|wait|info, detail, fix}: config, own (not Zlarior's / ATLAS's Name), nt (connected), visible
  (the Name in go.nt_names: accounts.csv + Position files; Sim always), allow (allowlist; Sim none), sim ("Order route tested
  recently": the bot's Sim roundtrip <= 14 d, OR a BLITZ Sim session <= 14 d: `data/account_c_sim.json`, gitignored, written
  by AccountC._close on a Sim account of the real bot, OR on the running bot an entry NinjaTrader took for Zlarior / ATLAS in
  the last 7 d: the same ATI route, no need to stop the live bot for a roundtrip), armed (real: armed AND the bot running live = NINJATRADER_LIVE + the phrase; Sim: info), bot
  (acct_c running, not disabled), eval (session via sizing.eval_session: 0 before the first day), size (AccountC.qty at today's
  room, the stop = 1.5 x the engine's 5m ATR else 60 pts, + 40 / 90 / 150-pt rows; 20 micros = MFFU 25K 2 minis), hedge,
  contract (bands loaded, the 20-trade floor -0.150 / 0.62, paused = red with --resume), calendar (cme_calendar: full closure /
  early close flat -5 / entry -15; a DST change within 7 days named), feed (bot health, else go.feed_problem), day (the day
  filter, info). CLI `--preflight` asks the running server first (GET `/api/next/start/blitz/preflight`, engine/start_api.py,
  cached 10 s), `--files` = without it; exit 1 unless all green. Start page BLITZ card draws it (start.js `cpfBlock`, fetched
  with the status when BLITZ is on). Launch checklist: line `blitz` "BLITZ (account C) ready" right after `b`, only when
  data/account_c.json is set (`launch_check.blitz_fact` -> blitz_preflight.compact: green = all green, else the first red line
  + its fix). Tests: test_account_c part 13, test_launch_checklist blitz_checks.
  **First-real-day fixes (2026-10-29):** (1) phone: on NinjaTrader the adapter reports its own fills only for the bot's own
  account (state_path == STATE_PATH) and AccountB / AccountC skip their own entry push (reports_fills), while their info()
  rows dropped the legs -> no FILLED line, no entry notice for ATLAS / BLITZ on NinjaTrader, and BLITZ's exit notice read
  LIT's label "MFFU 50K". Now `account_b._fill_of` adds "fill" to B / C rows (C also "entry"), narrator._route_rows uses it,
  narrator.send_push labels strat scalp "BLITZ <Name> (REAL|SIM)" and `_scalp` suffixes key ":acctc" / tag "-acctc" (= C's own
  HEDGE / TIME / kill notices: one notice per trade; ATLAS's feed notices get account B's own ":acctb" key the same way, the
  tag unchanged), BLITZ wording (SCALP_EXIT_WORDS: 30-minute clock, not LIT's 15-minute
  check; "stop trailed past the entry"). (2) AccountC._push_text: keys in PUSH_NOW (closing, unconfirmed, trail, passed,
  failed, stuck, pause, lock) are kind "ops" (pushed like ops_checks' eval notices); "order NOT placed" stays "risk" (the
  narrator's refused line pushes it). (3) Why no trade: `blitz.day_filter(E, date, now=)` = {ok, ratio, yday, mean, next};
  state_text says "BLITZ skipped today: yesterday's 09:30-16:00 range X pts < 0.8 x its 14-day mean Y pts" also after the
  last check (it used to say only "No more checks today"), + the next day's verdict once today's range is final; heartbeat
  compact "day_filter". **Oct 28 / 29 0-trade verdict (PC pushed bars + 5m for Oct 19-26):** Oct 28 passed the day filter
  (Oct 27 range 387.5 = 0.90 x 428.5) but had no close outside the band at any of the 10 checks (nearest: 11:00 close 29,804.5
  vs lower band 29,779.65), and the shadow's first run was 16:06 ET that day; Oct 29 filtered (Oct 28 range 239.0 = 0.59 x
  404.3; the PC's band 0.59 matched the rebuild to 0.1 pt); Oct 30 filtered too (0.66). Correct: no bug.
  **BLITZ dress rehearsal (2026-10-29, `tests/test_rehearsal_blitz.py`, built on tests/test_rehearsal.py's sandbox / fake
  NinjaTrader / virtual clock):** the real server.py with LIT on Sim101, ATLAS (data/account_b.json) on Sim102, BLITZ
  (data/account_c.json) on Sim103; each day a fresh eval, the bot started late (10:15 / 10:50) so the live loop rebuilds the
  morning. Expected = engine.blitz.execute on the 2026 1m bars minus the signals the live account masked (each mask must
  name LIT / ATLAS), the eval's own stops (+$1,500 pass, -$600 lock) and the scenario's blocks; per trade: entry minute,
  side, micros (`expected_qty`: account C's eval size written out), the MARKET fill, STOPMARKET + LIMIT OCO, the trail CHANGEs
  (tighter only, the model's stops in order, the last = the model's last; an intermediate step can fold into the next
  minute's), exit reason / minute, booked $ = micros x the backtest's $ a micro; the fake NinjaTrader records any fill that
  opens a position while another account holds the other side (must be none). Days: 08-03 normal (6 trades, trail stop-out,
  15:55 flat), 06-05 pass (3 wins = +$1,525, EVAL PASSED, no trade after), 08-06 ATLAS S/R short 11:15 into BLITZ's long
  (HEDGE first), 05-14 ATLAS short at the same 11:00 close, 04-01 LIT short (masks), 10-15 / 06-09 injected CME early closes
  13:00 / 13:15 (LE_RH_EARLY in the sandbox server; 2026's real half days had no BLITZ trade), 10-16 restart mid-trade,
  08-28 NinjaTrader refuses the first entry, 05-18 owner pause + HOLD TO KILL. **Result 2026-10-29: 345/345 checks**, 27 routed
  BLITZ trades (78 micros, 63 trail CHANGEs, exits 20 TIME / 3 STOP / 1 15:55 flat / 2 HEDGE / 1 KILL) = the backtest trade
  for trade, booked +$4,175.13 vs the fake broker's fills +$4,151.80 (stop / market fills 1 tick against), 1 LIT mask, 1
  eval-pass block, 2 early-close blocks, 1 refused, 1 paused, 0 opposite fills across the three accounts; the go-live
  check over HTTP all green after a Sim trade. `--jobs=4` 1,220 s on a loaded 4-core box; a day re-run into a parts folder
  + `--summary=<folder>` rebuilds research/scalp/blitz_rehearsal.json. The sandbox serve patches bg_worker.JOB_TIMEOUT_S
  (its timer runs on the virtual clock) and turns off the dashboards' 5-year backtest jobs (dash_data.JOBS_MGR.submit).
- Same code as the research: engine/second.py calls tools/second_ema.py / second_md.py / second_sr.py on LIT's live
  window (retail_standalone.load_frame live_cut, the simulators' live/OPEN mode). "With LIT" view = LIT first, no entry
  while LIT is in a trade, max 2 a day (MACD closed when LIT enters).
- Wiring: cloud monitor state key `second` (frozen paper ledger, README "Second strategies (paper)", pushes kind
  `second` titled "PAPER ..."); PC bot `LiveBot._second_tick` (background thread after LIT's routing, once per new bar)
  -> heartbeat / live.json `second`; dashboards: phone System > Second strategies (`second.js` + `secondcore.js`), PC
  Data > Second strategies (`/api/next/second`, `web_next/js/next/second.js`; `secondcore.js` byte-identical copy).
- Switch one off: `"on": false` in `second_model.json`. A fourth: a `second_model.json` entry with `"module"` whose
  `live_run(df5, one_min, cfg, now, lit)` returns {"trades", "state"} (or `@plugin` in engine/second.py).
- Test: `python -X utf8 -m tests.test_second` (2026 day-end replay identical to research/second/*_best.json, intraday,
  look-ahead, imports, cloud dry run, second brain checks vs real decisions); `--quick` ~1 min.
- **Routed on LIT's account (2026-10-22, owner "I want the bot to search for both"), built, OFF:** `"route": false` per
  strategy in second_model.json; switch `python -m engine.second --route <key> on|off` (refuses if
  `engine.ninjatrader --selftest` fails; never cloud_only). Routing lives in engine/live.py (`LiveBot._second_route_tick`,
  after LIT's routing; engine/second.py stays adapter-free): probe at each 5m open with the real open -> MARKET + OCO
  bracket via guards / `_route`, check once the fill bar closed (else NO TRADE flat), its BE stop CHANGE, 15-minute cut
  and 15:55 flat, `open_src` in live_state.json (restart / reconcile safe). Rules: one position; LIT first (no second
  entry while LIT is in a trade / entering / limit armed / 1m-CISD wait; an open second trade is closed at market when
  LIT enters = "LIT PRIORITY"); guards max_per_day 2 when any is routed, max 1 second strategy, LIT keeps its 1; size
  `engine/sizing.second_qty` (= research eval-safe: $500 capped at 0.6 x room and the shared $1,000 soft daily loss,
  pass / fail lock). Eval path with these rules (`tools/second_route_eval.py`, `second-route.md`): EMA H1 2-wk 55.5/10.9,
  H2 69.6/0.0, path +$36.8k / +$11.2k (research 61.3/5.0, 69.6/2.9, +$39.7k / +$23.0k; LIT alone 57.1/5.9, 52.2/0.0,
  +$34.2k / +$9.1k): keep it off on the eval. Not mirrored to extra accounts. Test `python -X utf8 -m
  tests.test_second_route [--quick] [--suites]`. Second brain: engine/second.py `brain` per strategy (checks in engine
  order, plan, log) -> heartbeat `second`, `/api/next/brain/second`, Bot Brain "Second-strategy brain" tab (phone + PC,
  `secondcore.js` SecondUI.brain).
- **Account B (2026-10-22, owner "trade it on another 50K or a 25K"), built, OFF:** `second_model.json` `"account_b": null`;
  on = `python -m engine.second --account-b "<NT Name>" --plan builder25k|builder50k --start <day> [--sizing need|safe]`
  (refused if the self-test fails), `--account-b off`. `engine/account_b.py` (LiveBot.acct_b, `_account_b_tick` after
  LIT's routing): own NinjaTrader account (OIF tag `acctb_`, own NT state, `live_state_acctb.json`), own guards, own eval
  (balance / EOD floor / room / sessions / pass-fail-stuck lock + pushes / plan soft daily loss), size
  `account_b.qty` (need = LIT two_week on the plan preset: 25K 50% room, 20 micros, $600; 50K 60%, 40, $1,000), max 2 a
  day, one position, never opposite to LIT (blocked while LIT holds / enters / has an armed setup the other way; LIT
  entering opposite closes B first = HEDGE); B's strategies never routed on LIT's account. Research
  (`tools/second_account_b.py`, `second-account-b.md`, runs `acctb_*`): 25K need 2-wk H1 68.9/0.0 H2 43.5/0.0, path
  +$19.7k/+$5.4k, +$1,549 per eval; 50K 72.3/2.5, 53.6/0.0, +$44.4k/+$7.6k, +$3,347; 2025/2021-24 ~35-39% dead in 2 wks.
  Pick: Builder 25K (MFFU: 1 funded Builder 50K per person, up to 2 funded 25Ks). Card "Account B <name>" in
  `secondcore.js` v3 (phone + PC + Bot Brain). Test `python -X utf8 -m tests.test_second_account_b [--quick]`.
- **Account B funded (2026-10-26, `research/writeups/atlas-funded.md`, `tests/test_account_b_funded.py`):** a pass only
  stops the eval and pushes "EVAL PASSED ... run the funded switch" (never automatic). Switch (MFFU gives a NEW Name):
  `python -X utf8 -m engine.account_b --to-funded --account "<funded Name>" --start <day> [--balance 25000]` or the
  Start page's "Passed → funded" on ATLAS's row (`go._b_to_funded`; data/start_bot.json "atlas" follows, prepped kept):
  the local block gets `"stage": "funded"`, `funded_start`, `funded_balance` (above / below the plan start = P&L before
  the bot), `payouts`, `eval_account`, `funded_set`; armed / eval_anchor / prior_pnl dropped (DISARMED); the funded Name
  allowlisted; the eval's state kept as `live_state_acctb.eval_<Name>.json`. `set_account_b` on the same Name (arm_b,
  launch prep) keeps the funded stage. Funded B: `account_b.funded_qty` = `sizing.funded_qty` on the 25K preset (60% of
  the room, <= $750, winner <= $1,000, $600 DLL, 20 micros, skip_breach) + dll_guard, weights never raise it; state =
  `multi_account.sizing_state("funded")` since funded_start (+ prior, payouts; floor at start + $100 after the 1st
  payout); no broker anchor; lost / stuck (room < $100) / graduated = no new entry; tracker `funded_life.track` (new arg
  `prior`; `notices` takes `record_cmd`) -> pushes PAYOUT READY (record: `engine.account_b --payout <day>=<$>`),
  consistency, lost, graduated + B's own "funded account stuck"; `--funded-status`. Views: info() adds stage / funded
  (eval info unchanged byte for byte), heartbeat second.route.account_b, live board atlas_now + boardcore.js, ATLAS page
  secondcore.js fundedB, Goals, scale plan (phone sw le-public-v38). Research `tools/atlas_funded.py` (runs
  atlas_funded_live / _old, research/second/atlas_funded.json; trades tools/atlas.account_units, size = account_b.qty):
  H1 / H2 $582 / $517 a month to the owner, 0.73 / 0.65 payouts a month, first payout median 18 / 24 sessions, 0% lost,
  8.2 / 8.5% stuck; 2025 / 2021-24 $64 / $39, 89 / 96% stuck (no edge there); per eval bought $3,178 / $3,057 at $43.
  mffu_rules.json builder_25k checked vs the owner's screenshots 2026-10-26 (all match; DLL confirmed).
- **Account B pre-launch (2026-10-22, `second-prelaunch.md`):** stress test `tools/second_robust.py` (runs sb_robust_*,
  research/second/robust.json): noise / slippage / 10-20% missed keep ~80-104% of 2026 $, 25K 2-week pass ~61-68 / 41-43;
  **1 bar late is the weak spot** (25K 49.6 / 31.9, EMA H2 4%, S/R H2 negative): never chase a late entry (MAX_AGE_S 45).
  **Go / no-go scorecard** `engine/second_scorecard.py` (bands = bootstrap of 2026 H2 trades + 2025, research/second/
  scorecard.json, rebuild `python -m engine.second_scorecard build`): go live only after 20+ finished paper trades at or
  above the expected p10; under p5 = don't go live; shown in data.json / `/api/next/second` "scorecard", secondcore.js v4
  (phone sw le-public-v25), cloud README. Test `tests/test_second_scorecard.py`. Bad-market brake (`tools/second_brake.py`,
  57 rules, runs sb_brake_*): none adopted, none built (cuts dead evals but also passes; real money within +/-$1.6k / 5 y).
- **Account B entry the broker never took (2026-10-27, `tests/test_acctb_not_placed.py` 24/24):** the 03:30 MACD LONG 3 on
  the 25K answered NOT OK (heartbeat `entries_today` 0), yet B kept it "open" (other B entries blocked, its paper P&L would
  be booked on B's eval, the phone showed a trade that never existed). Now `AccountB.never_placed` (answer NOT OK, no leg
  filled / open / pending, NinjaTrader shows no position on B's contracts; a leg still working counts only once the
  adapter retired it unfilled; anything unclear = kept) -> `_drop_unplaced`: B flat, no exit routed or booked, a close an
  older version booked is voided (once per process), push "order NOT placed" + NinjaTrader's reason. A NOT OK answer that
  may still be open -> kept + push "order NOT confirmed". Checked at the entry, every poll (`reconcile_unplaced`) and
  before LIT's hedge close. Heartbeat `second.route.account_b.routed` rows carry `ok`, `error` (paths removed), `void`.
  The rule is `engine/ninjatrader.entry_never_placed`, shared with LIT (`engine/live.py`): a refused LIT entry pushes
  "order NOT placed" + the reason (or "NOT confirmed" when it may be open), and its model exit books $0 on the eval (was
  the backtest's $: test part 7 replays 2026-10-13, a +$3,169 day). An exit for an entry never routed (bot off) also books
  $0 now (the +$0.10 BE "missed" 08:37 trade booked on the 50K at 23:08 ET 2026-10-26).
  Same day 06:12 ET Zlarior's SELL 7 answered "fill not reported yet" and was never filled (adapter: cancel never
  confirmed, account flat): the old code booked -$965.30 on the 50K, B's phantom HEDGE close +$525.30. After a restart
  the adapter's retired legs are gone, so `_no_trace`: 10 min after the entry, no outgoing\ file with LE<entry_t> and a
  FLAT position file for every contract = never placed. `LiveBot._void_unplaced_exits` (once per process) sets such
  booked exits to $0 (`pnl_void` keeps the old figure) + push; B's once-per-process scan voids its closes. Tests
  `test_acctb_not_placed` 41/41. Why NinjaTrader never answered the MFFU orders: heartbeat `nt_log` (`engine/nt_log.py`,
  the Log-tab lines with our LE ids / rejects / ATI / errors, paths and e-mails removed).
- **Start (owner 2026-10-27 "no PowerShell", "PC on = it runs"):** one Run / Stop switch at the top of every PC
  dashboard page (`web_next/js/next/runswitch.js`, Run = `/api/next/start/go`, Stop = `/api/live/stop`; tests
  `test_run_switch`). The bot server runs hidden. After a reboot `autoresume.resume_live(still_on=, open_nt=)` opens
  NinjaTrader and waits for it with no time limit while the switch is on Run (autostart record present).
  `engine/fsutil.replace` retries state-file replaces on Windows file locks.
- **Fleet = in-house copy trading (2026-10-30, owner "copy trading, prop firms, live accounts"), built, OFF** (no
  `data/fleet.json`, gitignored = `LiveBot.fleet` None, no heartbeat / live.json key; `tests.test_lit_live` identical).
  Owner guide `docs/ADD_ACCOUNT.md` (3 steps + each firm's rules in plain words).
  - **Firm rules as data:** `research/props/firm_rules.json` (rebuild / check: `python tools/build_firm_rules.py [--check]`,
    from `research/lit/mffu_rules.json` + `research/lit/prop_firms.json` + `research/props/firms.json`; nothing fetched):
    7 firms (MFFU Builder 25K-150K / Rapid / Rapid EOD / Pro, Lucid Pro / Flex, FundedNext Rapid Daily / Pro / Legacy, Apex
    4.0 EOD, Topstep Combine, Take Profit Trader Test, Alpha Futures), 47 plans; per value `{v, verified, date, src?, n?}`:
    verified = the repo's research marks it confirmed (firm page via search, or the owner's MFFU screenshots), v null =
    unknown (assumed in research = never guessed here), "none" = no such rule. 161 verified / 376 unknown of 1,457 (outside MFFU only Lucid Pro 50K, FundedNext
    Rapid Daily 50K and Topstep's payout figures are verified; funded `max_active` per person: MFFU 50K 1, 25K 2). MFFU
    Builder 25K / 50K verified from mffu_rules.json (min days = conflict, unverified). Prices: only the owner's ($91.80 /
    $63); every other price null. Firm rules: bots (Apex prohibited, Alpha semi-only, Topstep no NinjaTrader), hedging
    (MFFU banned across all accounts, verified), flat_by (MFFU 16:10).
  - **Account #4 (team A4, 2026-11-14; owner checklist `docs/ACCOUNT_4.md`, write-up `account-4-2026-11-14.md`):** the 4th
    builder input `research/props/firm_research.json` (applied last) re-reads LucidPro / LucidFlex 50K, FundedNext Rapid
    Daily 50K and the Lucid / FundedNext firm rules from the firms' own help centers (searched; their pages are DNS-blocked
    here); Bulenox EOD 50K is filled in `copy_profiles.json` (mostly third-party). Guards added in `engine/firms.py`, each
    only where the data / owner sets it: `max_micros_at` (contract scaling by profit: LucidFlex, Bulenox), `on_hold` (firm
    "hold": FundedNext + Bulenox until a written yes; clear per account with rules {"hold": "none"}), owner switch rules
    {"payout_guard": true} (payout best-day rule as a soft winner cap: costs 9-15% of the Lucid funded $, keep OFF), payout
    readiness extras (cycle_min, win_days / win_day_min, max_after_first, share) and `inactivity()` (30 days). Fleet CLI:
    `--start today`, `--add ... --arm <same id>` (one line, the phrase prompt right after adding). Sim
    `tools/account4_sim.py` (`check` = its eval == tools/uprisk.Eval) -> `research/lab/account4_sim.json`, runs
    `acct4_lucid_copy`, `acct4_pair`: the Lucid copy is a clone of the MFFU eval (same sizing; same 2-week outcome on 100%
    of paths), pair H2 $1,750 a month, daily correlation 0.94. Tests `tests.test_copy_accounts`.
  - **Rule engine `engine/firms.py`:** `profile(plan, stage)` (flat values + verified / unknown / warn), `live_profile(cfg)`
    (the owner's personal LIVE account: max $ a trade, daily / weekly stop, max micros; defaults 150 / 300 / 600 / 5),
    `book(start, closes, today, prior, payouts)` -> balance / eod_high / intra_high / day / week / best day,
    `floor_room` (EOD trailing = best closing balance - max loss, open losses count; intraday = best equity incl. open
    profit; static; trailing stops at start + lock; unknown type = intraday, unknown lock = never locks, unknown amount =
    no room), `check(profile, state, order, positions, now)` -> {ok, block, warn, max_qty, room, floor, day_left}: contracts
    (micros, minis x 10), the floor at the stop (+2 ticks, $1.90), daily loss (hard / soft named), weekly stop / max risk
    (live), best day (eval: a winner <= share x target x 0.95), Tier-1 news window (stage rule), the firm's flat time - 5
    min, hedging vs ANY other account on the same underlying (MNQ = NQ); `status` (passed needs min days + consistency;
    failed at the floor; funded payout readiness); `describe` (plain words). CLI `python -X utf8 -m engine.firms --list |
    --show <plan> [--stage funded]`.
  - **Copy layer `engine/fleet.py`** (`LiveBot._fleet_tick` after account B in the poll; `_fleet_block` = start cfg
    "fleet" in test harnesses, else data/fleet.json for the real bot, cached by mtime): each follower copies its LEAD
    account's routed rows (zlarior = LIT's ledger / `_open_routed`, atlas = `acct_b`, blitz = `acct_c`: entry only once
    the lead's answer is OK, never > 90 s late; stop moves as modify on broker adapters; the lead's exit -> exit + the lead's
    $ a micro x own micros; lead trade gone without a close -> flat after 120 s "LEAD GONE"; 15:58 TIME SAFETY). Size =
    the lead bot's own sizer on the follower's plan (zlarior: `sizing.lit_qty` via multi_account two_week / funded on the
    plan's sizing preset 25K / 50K; atlas: `account_b.qty` / funded; blitz: `account_c.qty`), or `"sizing": "fixed"` +
    `risk_usd`; LIVE = fixed risk only; then `firms.check` caps it. The lead's day limit (LIT 1, ATLAS 2, BLITZ 6). No
    hedge fleet-wide: a follower never opposite any account (LIT / extra accounts / B / C incl. closing / other followers,
    under one entry lock); hooks (all `getattr(..., "fleet", None)`, off = identical): `LiveBot._route` refuses a lead
    entry opposite a follower, `_hedge_clear_c` -> `_hedge_clear_fleet` (LIT entering closes opposite followers first, HEDGE
    WAIT / "HEDGE BLOCKED: fleet follower close not confirmed"), `AccountB.lit_opposite` (Zlarior followers hold ATLAS back)
    + `_c_yield` -> `_fleet_yield` (ATLAS / BLITZ followers closed first), `AccountC.opposite` (any follower masks BLITZ),
    `multi_account.Account._process` (extra accounts never opposite a follower). Refused copy (NOT OK + provably never
    placed, `ninjatrader.entry_never_placed`) = nothing booked, push "copy NOT placed", the others trade; NOT OK but unclear
    = kept "unconfirmed" + push, dropped unbooked once never placed. Kill: per account `"killed"`, fleet `"kill": true`, the
    bot's kill switch / remote flatten. Live gate (`fleet.live_gate`): a non-Sim NinjaTrader follower needs `"armed": true`
    + the phrase at the bot's start + NINJATRADER_LIVE=1 (else no adapter), then the adapter's own gate + allowlist; firms
    that ban the bot (Apex, Alpha, Topstep / no NinjaTrader) = paper only; a lead's own Name refused. Own adapter per
    follower (OIF tag `fl<id>_`, `ninjatrader_state_fleet_<id>.json`), state `live_state_fleet.json` (restart safe).
    `stagger_ms` (<= 5 s, before the entry), slippage ticks vs the lead's fill. Lifecycle pushes once: EVAL PASSED (then
    `--to-funded`), FAILED, PAYOUT READY (never requested). CLI `python -X utf8 -m engine.fleet --status | --add --id --lead
    --plan --account --start [--balance --max-risk --daily-stop --weekly-stop --max-micros --risk-usd --stagger-ms] |
    --remove | --on | --off | --kill <id>|all | --unkill | --arm | --disarm | --to-funded <id> --account --start | --payout
    <id> <day>=<$> | --dry-run <day> | --preflight <id>` (dry run = the day's LIT trades of research/lab/backtest_live.json
    on paper; `--arm` of a real Name also allowlists it, the owner's command only). `fleet.preflight` (read-only, as
    blitz_preflight): settings, the firm allows the bot on NinjaTrader, copy trading confirmed, the plan's rules known /
    verified, NinjaTrader shows the Name (go.nt_names), allowlist, armed, the bot live (NINJATRADER_LIVE), the lead running;
    GET `/api/next/fleet/preflight/<id>`, PC card "Check before arming".
  - **Data / pages:** heartbeat `fleet` (`Fleet.hb_block`, < 6 KB, only when configured), live.json `pc.fleet` (dropped
    after `mind` when over 64 KB), GET `/api/next/fleet` (`engine/fleet_api.py`: rows + leads + totals + notices + the firm
    catalog; off = {on: false} + the catalog), POST `/api/next/fleet/set` (the PC page's buttons = `fleet.run`, the CLI
    without printing: add / remove / on / off / kill / unkill / to_funded / payout; PC only via `cloud_guard.local_only`,
    `cloud_guard.FLEET_WRITES` in CLOUD_BLOCKED; every field checked; "arm" refused: arming stays the console `--arm`).
    Phone `tools/web_public/fleet.js` (#/fleet, System group, read-only), PC `web_next/js/next/fleet.js` (All tools tile: MODULES
    entry in routes.js, PAGES.fleet in app.js; cards + Add form + per-account buttons with confirms + Kill ALL; never
    redraws under typing). Tests `python -X utf8 -m tests.test_firms` (58) and `tests.test_fleet [--quick]` (103 unit
    incl. a Sim follower on the real NinjaTrader adapter against `_FakeNT`, node renders of both pages, the POST guard;
    + the LiveBot replay: the primary's ledger identical with 3 followers, each copies every trade once).

## Trade pictures (2026-10-23, `engine/trade_chart.py`, read-only)
- One renderer for every strategy's trades (LIT, LIT+Asia, ema / macd / sr, sh_asia / sh_trend): 1600x900 dark PNG (~90 KB),
  5m from ~2 h before the setup to the exit + 1m entry panel, "Why it entered" rule checks, legend, ET axis, sessions.
  Markups come from the strategies' own code: LIT = `lit_live.run(keep=)` + `tools/lit_chart_data.record_of` +
  `brain._checks`; second strategies = `second.run` with cfg `"_marks"` (`engine/second.py` `_ema/_md/_sr/_sh_marks`; off =
  trades unchanged). Bright (`k:`) = closed bars / marks known at the entry, `plan:` from the entry, faded (`a:`) after.
- Where: cloud `cloud_hook` (new trade at entry, redrawn at exit, max 10 a run / 50 s, newest 60 per strategy in
  `<dash>/charts/` + index.json, restored by the workflow) -> site `charts/` + data.json `charts` (`site_copy`); PC
  `LiveBot._chart_tick` -> `PcCharts` background thread -> `logs/charts/`, `/api/next/charts`, `/api/next/chart/<key>.<tid>`
  (`engine/chart_api.py`); examples `python -m engine.trade_chart backfill --strategy all --since 2026-07-01` ->
  `research/lab/chart_examples/` (~20 each, 12 MB). One trade: `python -m engine.trade_chart one --strategy X --day D`.
- Shown by `tradepics.js` (phone = PC copy, byte-identical; full screen, pinch / double-tap zoom, swipe): ATLAS brain cards +
  "Trade pictures" strip + candidate cards (secondcore.js v7), LIT Bot Brain + Trades (phone sw le-public-v29).
  Test `python -X utf8 -m tests.test_trade_chart [--shots <dir>]` (78 checks incl. look-ahead, cloud dry run, Playwright).

## AI watch (2026-10-22, `engine/ai_watch.py`, `research/writeups/ai-features.md`; alerts on, blocks OFF)
- Per poll after routing (`LiveBot._alerts_tick`, real bot only), LIT + account B: anomaly pushes (bad tick / 1m spike /
  jump, entry routed 30+ s after its signal), **feed frozen in a trade** (critical, repeats until Got it), drift per
  strategy (LIT health band H2, account B bootstrap of run `acctb_<plan>_<sizing>`, fill-audit execution), both accounts'
  P&L today / this week (push at -$1,500 / -$3,000), rule-change push (`engine/rulelog.py`: git who / when / why ->
  `research/lab/rule_log.json`, runtime `logs/rule_changes.jsonl`). Kinds anomaly / freeze / drift / loss_cap /
  rules_change (phone alert levels). Pre-session push adds news / account B room / blocks on; weekly push a self-review.
- **OFF switches** (`live_model.json` "guards", via `guards._owner_blocks` = LIT and B): `"anomaly_pause": true` (15 min
  after a spike, while frozen in a trade), `"combined_loss": true` (`combined_day_usd` 1500, `combined_week_usd` 3000).
- Restore: `python -X utf8 -m engine.ops_checks --restore latest [--yes]` (refused while running / in a trade). Phone System >
  AI watch (`tools/web_public/ai.js`), PC System card (`/api/next/ai`). Test `python -X utf8 -m tests.test_ai_features`.

## Previous strategy (shadow): Liquidity Engine, eval mode (`live_model_engine.json`, locked 2026-10-17)
- **Liquidity Engine, eval mode** (`engine/model.py`):
  1. Sweep of a liquidity pool from 08:00 ET.
  2. IFVG/CISD trigger in the killzones (09:30–11:30, 13:30–15:30).
  3. Stop beyond the sweep extreme (10–60 pts).
  4. Target the nearest **major** pool ≥1.5R away, banking 5R on the way when the draw is farther. No major pool means no trade
     (`use_fallback: false`).
  5. BE at 1R, 30-min time stop, giveback exit, max 1 trade/day.
- **Size:** `risk_usd 800` up to a 20-pt stop, then scaled down by `risk_ref_stop 20` (risk = 800×20/stop); `dd_aware false`.
- **Cold-streak filter** (`engine/equity_filter.py`): if the last 15 finished signals sum ≤ 0R, trade at **a quarter of the size**
  (`cold_mode: half`, `cold_size: 0.25`; was 0.5 until the 2026-10-17 evening lock).
- **Late entries** (15m structure already turned the trade's way) trade at **half size** (`sizing.late_mult 0.5`); **breakeven at
  +3R on trending days** (`be_at_r_trending 3.0`); `memory_seed false` (PC and cloud identical). One shared multiplier:
  `engine/sizing.py` (cold × late, rounded once, floor 1 micro). The fast-eval press (`sizing.press`) exists and is OFF.
- **Results** (live-loop replay, costs included, lock of 2026-10-17 evening):
  - 2026 YTD: 89 trades, 2.16/wk, PF 3.94, +$20,487 ($2,088/mo), max DD −$2,249; eval within 2 weeks 20.4% pass / 0.0% fail,
    within 1 month 34.0% / 0.0%.
  - 2021-25: PF 1.27, +$16,379 ($321/mo), max DD −$9,265; 1 month 8.8% / 5.2%; back-to-back 8/10.
  - 5 years: PF 1.54, +$36,866, max DD −$9,265; back-to-back evals 12 passed / 11 failed. 2026 was an unusually good year.
  - Before the lock: 2026 PF 3.48 +$20.1k; 2021-25 PF 1.09 +$6.5k DD −$11.4k; 5 years PF 1.32 +$26.6k, b2b 11/19.
  - Honest range (sensitivity study): the cold lookback 15 is a ridge (14 → +$13.3k, 13 → +$7.8k, 17 → +$10.7k over 2021-25);
    quote 2021-25 as +$8k to +$17k. Every neighbour of the lock is profitable in both periods. 2 extra ticks of slippage keep
    80-86% of 2021-25; no calendar rule is worth having.
- **Eval timing (Monte Carlo + eval-game study):** buy/reset the MFFU eval when the filter shows full size (1-month pass 22% /
  fail 8%), best within 5 sessions of the switch back from a cold streak (26% / 4.5% in 2021-25, 50% in 2026), weakest after
  20+ sessions at full size (7% / 12%), never in a cold streak (4% / 2%). `equity_filter.eval_timing(status, sessions_since_flip)`
  → cloud state `eval_timing` (verdict go/wait, state warmed/full/stale/cold), README row, flip alert, PC Cold-Streak page,
  phone Today page. The MFFU Builder 50K is the right plan; best-day-rule plans (Topstep etc.) would take 2-17 months.

## Tested and rejected (don't redo without a new idea)
- **Market-regime warning features (2026-11-17, `edge-health-2026-11-17.md`, `tools/edge_health.py`):** VIX, RTH range %, overnight share, trend efficiency, sweep reclaim (40-session means) as a 2026-vs-2021-25 light: only overnight share separates (BA 0.94) and it is a yearly drift that calls 2022 (LIT's good year) bad and precedes a worse LIT in 2021-25. Kept: the light from LIT's own last 40 sessions (warning only).
- **Famous published strategies (2026-11-17, `public-strategies-2026-11-17.md`, `tools/pub_strats.py`):** 22 cells as
  published + MFFU-legal day versions: Gao intraday momentum (wrong sign 2021-25, t -2.2), pre-FOMC drift (2021-25 only),
  turn of the month (2026 only; day-trade version = random days, placebo p 0.12-0.24), overnight drift, Connors RSI(2),
  12-month and 20/60-day time-series momentum, Crabel NR7 / NR4 / NR7-ID. None holds in 2021-25 + both 2026 halves; the
  ones that look best hold overnight (MFFU: flat by 16:10) and lost in H2. LIT corr ~0 but no money. Nothing adopted.
- **Drift switch (2026-11-17, `drift-switch-2026-11-17.md`, `tools/money/drift_switch.py`):** cut LIT to paper/half after a rolling
  loss (51 versions): 0 pass; never fires in 2026; 2021-25 fewer failed evals but same less payout; no better than random cuts.
- **Walk-forward re-tuning (2026-11-17, `lit-walkforward-2026-11-17.md`, `tools/lit_wf_retune.py`, `research/lit/wf_retune.json`):**
  re-fit disp 0.7/0.8/0.9 x BE 1R/1.5R/off x bank 5/8/12R (27) every month / quarter on the trailing 6 / 12 months (8 versions),
  OOS 2022-05..2026-10. Main (monthly, 12 mo, net-DD): 2022-25 +$23.1k vs static +$0.7k (1.3 s.e., +$26k is 2025 alone, 2023/24
  worse; beats random re-picks 93.5%, others 44-83%); 2026 H1 -$11.0k, H2 -$3.0k; all 8 lose both 2026 halves. 2023 loses at all
  27 settings: the bad years are regime, not knobs. (2026-only anchored version: `tools/lit_walkforward.py`, also lost.)
- **Rule-native layer (2026-11-17, `rule-native-2026-11-17.md`):** 2nd target / 1R / scalp / profit lock: no sooner payout.
  Lead only: BLITZ max 3/day on the Rapid (chance-level by count; 2021-25 2-week eval fails 2.9% -> 6.0%). Watch on paper.
- Published models as taught: ICT 2022, Silver Bullet, Mech/IFVG, continuation, ATM 5m/1m with a sharp V (0.2–1.5 trades/wk,
  PF ~1).
- 92 confluences; 6 daily-bias methods; grade/confidence sizing; partials and trails.
- Fixed 10–15 pt stops: wicked out, lose money. Structural stops are rarely ≤15 pts.
- Target variants: no cap / draw mode / "last real pool" all worse (2026 PF 1.6–2.2 vs 3.48).
- Re-sweep, inducement, FBOS, RBOS: recorded as engine features `x_resweep`, `x_inducement`, `x_fbos`, `x_rbos`; no edge that
  held in both periods. "No inducement" looked better, but the sample is thin.
- The skip-mode cold-streak filter: best PF, but it paused for 14 weeks, which the owner rejected.
- All variants with numbers: `research/lab/variant_results.json`.
- **B-holds (2026-10-27, `b-holds-vs-lit-priority.md`, `tools/bholds.py`, runs `bholds_*`):** while ATLAS (account B) holds a trade, skip
  LIT's opposite entry instead of closing B (HEDGE). Both accounts 2026 +$52.3k -> +$53.6k, 2021-25 -$3.2k -> -$5.0k; ATLAS 25K
  2-week pass H1 65.5 -> 60.5 (stuck 0.8 -> 3.4); 9 clashes in 2026, 35 in 2021-25. Rejected: LIT priority stays.
- The owner's LIT Complete Report (2026-10-18, `research/writeups/lit-report-tests.md`, `tools/lit_report.py`, runs `lit_rep_*`):
  reclaim, confirmation deadline, acceptance, displacement quality (top-quarter close, 1.5-3x median body, FVG), 2+
  inducements, inducement room, 2+ levels swept, leg premium/discount, double-sided sweep, first obstacle (0.5R = lone spike),
  continuation / flip 2nd trade, costs inside the $800, Berlin-time London boxes (no 2026 change, 2021-25 +$5.8k): none adopted.
  The report's ch.21 model makes 0 trades in 2026. Beginner guide: `research/writeups/lit-playbook.md`.

- **LIT studies of 2026-10-18/19 (none adopted unless noted; write-ups in research/writeups/):** HTF confluences (75,
  chance level, `lit-htf-confluences.md`); order blocks incl. HTF OB entries and the owner's mitigation notes (84,
  `lit-order-blocks.md`); entry precision (43, today's entry is best, `lit-entry-precision.md`); all-hours / Asia /
  per-session / re-arm / F-BoS build-up (30, `lit-all-hours.md`); report-2 continuation, sessions, Smart Money Trap,
  inducement speed/hierarchy (176, `lit-adv-continuation.md`); BE/partials/targets (`lit-adv-management.md`: BE at
  entry + 1.25 pts is a small candidate); backtest honesty audit (-$500 of $41.7k, `lit-adv-audit-smt.md`); NQ/ES
  divergence; more setups: ES/MES, 15m/30m/1h, missed fills, looser filters (95, `lit-more-setups.md`); trend-day mode,
  volatility sizing, news setups (`lit-big-ideas.md`). **Of the three adopt-candidates, two are ON since 2026-10-20**
  (owner approved; numbers in "Results" above): the 15-minute check (`t_check {"at":15,"x":0.3,"mfe":0.5}`,
  `lit-loss-learning.md`; route fixed: all 13 2026 cuts routed 2 s after the check-bar close, priced from the forming bar's
  open, `tests/test_lit_exit_route.py`) and BE + costs (`be_off 1.25`). **Scale-in after BE is OFF** (`"scale_in": null`,
  `lit-big-ideas.md`; NinjaTrader MARKET add + resize of the one OCO bracket, `add_to_position`, 52/52 2026 adds match the
  backtest; two safety reviews: safe only after the owner's `--sim-roundtrip-add` on Sim101 (since 2026-10-26 it proves the size itself: step 5 moves the target under the market, it must fill 2 micros and end flat, then prints SCALE-IN READY; `tests/test_sim_add_proof.py`) shows stop + target qty 2 at the
  right prices). All three on the eval path (run `lit_adopt_all3_eval`): H1 +$53.1k / H2 +$17.3k vs live now +$34.2k /
  +$9.1k, 2-week pass/fail 58.0/2.5 and 52.2/0.0 (live now 57.1/5.9, 52.2/0.0); scale-in alone makes more in H2 (+$26.0k)
  but fails more. Thin samples (13 cuts, 52 adds); the cut route is still untested on a real NinjaTrader install (watch the
  first week on Sim). `idm_size` (inducement-count size) helps the LIT size rule but not the
  eval path: keep it off for evals (`lit-new-entries.md`). Funded plan: MFFU Builder + LucidPro 50K + FundedNext
  Rapid Daily 50K (`lit-funded-firms.md`, ~$1,750-2,300/mo for three); one bot can now route to several accounts
  (`engine/multi_account.py`, off by default, `data/accounts.json`).
- **Reversal exits after the first live trade (2026-10-28, `lit-reversal-exit.md`, `tools/lit_rev_exit.py`, runs `lit_rev_*`):**
  exit / BE on a violent reversal once +0.5-0.9R (ATR candles, 2-3 candles, profit giveback), 1m/5m swing trails after
  +0.5-1R, BE at 0.75/0.9R, stop at the first 1m/5m highs: 103 variants, none better in both 2026 halves (the 2-ATR candle exit
  after 0.9R: today +$168 vs -$437 but H1 -$9.1k / H2 -$2.3k; first 1m highs H1 +$29k / H2 -$13k PF 0.75). 2026 had 0
  trades that went 0.9-1R then stopped before 2026-10-28. Nothing changes.
- **Diversifier search (2026-10-26, `diversifier-search.md`, `tools/div_search.py` / `div_stack.py`, runs `div_*`):** the
  VXN-normalised initial-balance breakout is dead (0/24 settings positive in all four spans). The noise-area intraday momentum
  (Zarattini 2024) is REAL as futures trading (paper rule and joint pick `na_vm125_1000_n99_fixed` positive in H1 / H2 / 2025 /
  2021-24, placebo p 0.007 in 2026, daily corr with LIT ~0) but NOT a prop strategy alone (MFFU eval p10 <= 22%, funded
  $13-117/mo: 27% winners, 18-23R drawdowns vs the 50% best-day rule and the $2,000 floor). Only as a small add-on on LIT's
  funded accounts (3-4% of the room, <= $150, never while LIT holds): +$54-83/mo per 50K in 2026, +$7-12 in 2021-25; paper only.
- **Payout / eval mechanics (2026-10-26, `payout-policy.md`, `eval-cost.md`):** ask line $1,000 / $2,000 vs $1,500,
  cons_aware, stack payout reserves (cap a month) and pre-buying the next eval at the 4th payout: see the write-ups before
  redoing. Eval: keeping two_week after session 10 (`two_week_until` 999) is the one change that held in H1, H2 and 2021-25
  (+$14-21/mo per slot; owner decides, not switched).
- **BLITZ on its own 25K, "like a person" (2026-10-29, `blitz-25k.md`, `tools/blitz25k_*.py`, runs `blitz25k_*`, pick
  `research/scalp/blitz_25k_pick.json` = no-change):** as account C (never opposite LIT / ATLAS, closed first; costs $0 in
  2026, $16/mo at $150 in 2021-25): structure stops (last 1m / 5m swing, the move's low, caps; 45), liquidity targets /
  partials / swing trails / change-of-character exits / no clock (1,920), opening drive, London band, retest limits, 15m / 1h
  BOS filters (32), funded-only structure rule: none beats today's rule in H1, H2 and 2021-25. 25K size: 40% of the room,
  100% from eval session 5 (decided in 2 weeks 71-74% vs 29-41%, same money: slot $270 / $37 / -$40 a month; random
  directions make the same H2 slot $). The post-hoc 1.0 x ATR / 45 min / no trail variant is worse on LIT's 50K too (H2).
- **Structure management (2026-10-29, `structure-management.md`, `tools/structure_manage.py` LIT 101 variants, runs
  `lit_struct_*`; `tools/structure_atlas.py` ATLAS 24, runs `atlas_struct_*`):** with `engine/structure.py` (closed-bar BOS /
  CHoCH / protected swing / pools): target at the next opposing pool (cap / instead of the band), half off at the first pool,
  stop to the protected swing after a BOS (1m / 5m / 15m), exit / BE on a CHoCH against after +0.5-2R, 1h / 15m trend skip /
  size. None beats live LIT in both halves on both sizings (the owner's BE on a 5m CHoCH after +0.75R: H1 -$1,442 / H2 -$775;
  1h skip: H1 -$15.0k / H2 -$7.5k, ~1 trade a week; runner past the target, lock 75% + 15m trail: H1 +$13.6k / H2 +$956 at
  the LIT size but two trend days are the gain and the eval path loses, 2-week pass 57 -> 36% H1, rejected). Lead, not
  switched: 15m structure trail after +1R (H1 +$467 / H2 +$13,
  eval +$1,019 / +$3,762, one more 2-week fail in H1, 7 trades changed): the advisor's `trail_15m` tally watches it. ATLAS:
  the 15m protected-swing stop passes the 25K account gates but its trades lose R in every span at a fixed risk (sizing
  path): rejected; every ATLAS exit / trail loses in 2026. The executors' base = live exactly (LIT 0 mismatches; ATLAS 96%
  within 0.5 pt, difference method).
- **ATLAS funded 25K day limit (2026-10-31, `atlas-funded-one-a-day-2026-10-31.md`, `tools/atx_funded_day.py`, runs `atxd_*`):**
  eval unchanged, funded max 1 a day: slot $ H1 / H2 / 2021-25 $454 / $275 / -$3 a month vs today's $568 / $382 / -$2,
  below a random-1-a-day control ($541 / $361); the H1 pick max 3 (= max 4) is +$44 H1, $0 H2 on 4 seeds. Keep 2 a day.
  Funded-only VIX band per member: no member loses in any H1 VIX tercile, so nothing to skip (`atx_funded_vix.json`).
  Funded half off at 0.75 / 1 / 1.5R + BE runner: H1 slot $336 / $366 / $414 vs $568 (runs `atxd_partial_*`): rejected.
  Funded re-entry after a stop-out (same setup once more, same direction): slot H1 $404 / H2 $257 / 2021-25 -$15 vs
  $568 / $382 / -$2, inside a coin-flip-direction control (run `atxd_reentry_1r`): rejected.
- **ATLAS + BLITZ edge night (2026-10-30, `atlas-blitz-edge-2026-10-30.md`, `tools/ab_edge.py`, runs `ab_*`):**
  - BLITZ trend-day SIZE (range so far, first-hour range / volume, overnight range / open's place in it, gap, VIX change,
    2-sigma excursion, VWAP side / distance, held at the previous check, time; 430 tilts): 39 survivors vs 36 on shuffled
    facts = chance.
  - BLITZ + a 10:30 check: H1 25K slot $270 -> $54.
  - BLITZ in-day streak size (2026-10-31, `blitz-streak-size-2026-10-31.md`, `tools/bzx_streak.py`, run `bzx_streak`): eval
    size x m after a same-day BLITZ loss / win (7 cells, 10 shuffled controls). H1 pick x0.5 after a loss: slot $286 / $53 /
    -$40 a month vs today $286 / $52 / -$39; 2021-25 no better than shuffled (after-loss trades are the BETTER ones there).
  - BLITZ cold-streak size on its own last K trades (2026-10-31, same write-up, `tools/bzx_cold.py`, run `bzx_cold`; K 5 / 10
    / 20, x0.5 / x1.5): H1 pick K 5 x0.5 when cold: slot $288 / $52 / -$40 vs $286 / $52 / -$39; shuffled -$37 in 2021-25.
  - The later-break size on LIT's funded 50K: neutral.
  - ATLAS (110, none passes the v2 test): member weights from the member's last 5-20 trades; member agreement; the 2nd
    trade sized by the 1st's result; LIT copied in as a member (x0.25: both 2026 halves better, 2021-24 -$3.0k vs -$1.4k,
    and the two accounts become one LIT bet); the NA day-hold as a 4th member (dead evals up); S/R level count / EMA sweep
    depth / EMA distance as size; London-clock windows in the DST gap weeks (the volume surge does move to 04:00 ET, but
    EMA / MACD lose there).
  - The one adopt-candidate is BLITZ's 25K later-break eval size (`research/scalp/blitz_25k_pick_v2.json`): adopted, owner 2026-10-31.
  - ATLAS paper lead (run `ab_atlas_na_hunts_lead`): the hunts x0.5 + the NA day-hold member x0.5.
    - More passes a month and more eval-path $ in all four spans: $2,046 / $1,584 / +$47 / +$194 a month vs $1,394 /
      $547 / -$148 / -$36; 13 of 15 neighbours do the same.
    - Fails the H1 2-week test: 62.2 / 5.9 vs 65.5 / 0.8.
- **Zlarior edge night (2026-10-30, `lit-edge-2026-10-30.md`, `tools/lit_edge.py` 190 variants, runs `lit_edge_*`,
  headline numbers `research/lit/edge_results.json`; LIT size + live two_week eval path + funded 50K $/mo):** target band
  from NQ's 5/10/20-day range or a VIX/range blend, re-anchored at the entry / midnight open / time left; BE at max or
  min(1R, k ATR or X pts); 15-minute check threshold in ATR; slow-trade nearer target; pre-registered A+ quality score and 13
  single-fact / mined size tilts (200-draw placebo; also on the funded path: size-ups -$16..+$16/mo, cuts cost up to
  -$109/mo); weekly catch-up (looser setup Thu/Fri when < 2 trades: +0.13 tr/wk); re-entry after the 15-minute cut or a BE
  (30 trades, -3.35R); a 2nd trade a day re-run (H1 -$1.0k..-5.0k); funded $2,000 cap as a take-profit (-$37 / -$70/mo);
  eval room-cap size + take-profit at the need (H2 2-week pass 33%); eval-only 3-6R bank; need buffer 0.8 / 1.2, clock
  press, room share by session: all rejected. Thin leads, not switched: afternoon target cap (from 14:00 at most 3R: LIT
  +$460 / +$311, eval +$606 / +$3,913, 2+1 trades) and lifting the 8R bank after +2R within 15 min (3 trades, funded
  -$143 / -$52/mo). Room share 0.7: same money, H2 2-week fails 5.8 -> 0.0% but slower passes (owner chose 0.8). Scale-in
  re-measured: eval +$13.8k / +$14.6k, 2-week pass 58.8 / 59.4%, but H1 fails 1.7 -> 3.4% and on a funded 50K -$149 / +$49
  a month (adds capped at the $2,000 winner -$22 / +$73). **Adopt-candidate (with the scale-in switch, after the Sim
  roundtrip): adds on the eval only from eval session 5, none on funded accounts** (run `lit_edge_eval_scale_in_s5`: eval
  +$38.7k / +$24.9k vs +$34.8k / +$16.3k, 2-week pass/fail 60.5/1.7 and 58.0/5.8 vs 57.1/1.7 and 52.2/5.8, sessions 2-6 and
  +4 ticks an add all hold; owner $/slot $827 / $815 vs $827 / $804 a month). Needs new code first: `lit_sizing`
  `scale_in_from_session` / `scale_in_funded` in `engine/live.py _add_qty` + `cloud_monitor.lit_add_usd` (not built).

- **Rapid EOD levers (2026-11-16, `rapid-levers-2026-11-16.md`, `tools/money/rapid_levers.py`):** on LIT + ATLAS $500 Rapid EOD 50K:
  eval give-up / re-buy (room < $500-1,000, session > 30/45, 30%-rule need > $3-4k: +$12-104/mo = noise, 2021-25 worse),
  eval day caps (none, stop at +$500/+$700, balance-aware guard: today's 30% size guard is best), Asia slot at LIT size
  (funded lost 9.4% / 2.0% / 27.3%), fixed $1,000 payout requests, different mixes per account for more $ (identical copies
  pay more in both halves; different mixes only cut the no-pay risk): rejected. Lead: keep a $1,000 funded cushion.
- **ATLAS deep edge (2026-11-15, `2026-11-15-atlas-deep.md`, `tools/atlas_deep.py`, 29 variants, slot $ at $43):** loser
  autopsy (member, side, hour, stop pts / ATR / vs the member's median, target R, daily trend, VIX, LIT's day, the members'
  paper day) finds no trade bucket that loses in all spans except the known 06:00 / 11:00 hours. Rejected (16 variants):
  skip / halve after LIT won the other side (slot +$19 / +$29, but 4 H2 trades worth -0.05R; random same-size skips pass
  the 2026 test 6.7% of draws = chance), same-side retry skip (retries are the best bucket) or x1.25 / x1.5, skip while LIT
  holds / after LIT won the same side, stop > 1.6x / 2x the member's median, first trades at x0.5 / x0.75 until green, eval
  weekly brake $400 / $600, daily-trend skip / halve, one signal per side a day. The one keeper is the zombie-eval rule
  (Second strategies above).

- **DAPHNE strategy-tree search (2026-11-03, `2026-11-03-strategy-tree.md`, `tools/strategytree/`, runs `strategytree_top1` /
  `_top5`, page `tools/web_public/tree/`):** 80 plain level roots (PDH/PDL, overnight, Asia, London, opening-range high/low;
  fade = sweep + reclaim, break = 5m close through; 1R / 2R; 60 / 120 min) x up to 5 conditions (vol quintile, gap, open vs
  yesterday's range, distance from the open, hour, weekday, VWAP side, EMA trend, VIX, OR width; ES agreement skipped: no ES
  before 2025-04), best-first branch-and-bound, train <= 2024, test 2025-26. 1,127,006 nodes, 54.6% cut by the bound; 31 of 80
  best rules hold out of sample vs 25 / 28 with shuffled conditions = chance. Every rule trades 0.1-0.5 a week. Nothing
  adopted; the page is a research lens, paper only.
- **E2 new NQ strategies (2026-11-13, `nq-new-strategies-2026-11-13.md`, `tools/e2_new_strats.py`, runs `e2_*`):** 7 families,
  140 variants, 5m RTH, $500 a trade, stops beyond structure: ORB 2nd side after a failed break, PDH/PDL sweep + climax
  volume (the volume gate makes it worse), NQ/ES relative strength at 10:00 (ES only 2025-04+), gap fade + failed opening
  drive + volume, VWAP reversion on low-VIX days, late-day break / last-half-hour reversal (the "since 2025" reversal loses
  in 2021-24), CPI/NFP/FOMC playbook (0.1-0.2 a week). 2 of 140 hold in H1/H2/2025/2021-24 vs 0.75 with coin-flip sides.
  Paper lead only: G1 gap fade (gap >= 0.1 x 14-day range, 09:30-10:00 range closes in its half away from the gap, stop 1
  tick beyond the range, 2R): $180 / $496 a month 2026 / 2021-25, PF 1.14 / 1.34, 1.7 a week, corr LIT 0.03; placebo p 0.003
  over 2021-25 but 0.22 in 2026; the plain gap fade loses; 2026 stops ~145 pts = 1 micro, so its own 25K / 50K passes 0-7%
  in 2 weeks and the slot is ~$0 a month; on LIT's funded 50K +$23 H1 / -$16 H2. BLITZ gap-aware band (Zarattini) H1 / H2
  $936 / $771 vs $912 / $577 but 2021-25 -$15 vs +$89; implied-vol band worse: BLITZ unchanged. No new eval account.
- **E3 same edge, more markets (2026-11-13, `es-and-sessions-2026-11-13.md`, `tools/e3_es_sessions.py`, runs `e3_*`):** live LIT and
  the 3 ATLAS members unchanged on ES1! as MES (points x 0.28, BE 0.75 ES pts; ES = 5m only, 2025-04+, no 1m, no 2021-24), each on
  its own MFFU eval. ES LIT H1 -$3.8k / H2 +$12.7k / 2025 -$15.9k (NQ 5m-exec +$6.6k / +$1.5k / -$0.5k), 50K 2-week 27.7/10.9 and
  44.9/15.9, corr LIT 0.14. ES ATLAS -$6.3k / +$2.2k / -$2.8k (NQ ATLAS +$47.3k / +$12.1k / +$13.0k): positive before costs, but
  costs are 7-13% of R on ES vs 2.5-5% on NQ (same tick, ~0.19x the points). NQ LIT NY-only slot as its own account +$12.8k /
  -$1.2k / -$2.6k at 1/wk; ES London / NY slots lose a span. Asia not redone. Nothing adopted; the 2nd stream stays NQ ATLAS.

- **S2 edge (2026-11-15, `2026-11-15-s2-edge.md`, `tools/lit_s2_edge.py` 28 versions, runs `lit_s2_*`, grid
  `research/lit/s2_edge_grid.json`; eval path at two_week room_f 0.4 kept past session 10):** "what other bots have":
  holiday-thin days (holiday Globex sessions, the day before / after, early closes, Dec 24 - Jan 2; x0.5 / x0.75 / skip),
  the contract roll window (5 sessions before the switch to the last trading day; x0.75 / x0.5 / skip), OpEx week / OpEx
  Friday / quad-witching week / turn of the month, NQ-vs-ES strength from the 18:00 open (lead x1.25 / lag x0.75),
  sweep of the day's or week's own extreme (x1.25, interior x0.75): none passes (calendar ones lose a half; ES strength
  and day-extreme are chance in Jul-Oct). Lead, not switched: target reachability (target pts / (5m ATR x sqrt(bars to
  15:55))) easiest third x1.25: LIT +$4,079 / +$1,021, eval +$2,724 / +$660, 2-week pass/fail unchanged, funded +$12 /
  +$19/mo, shuffle p 0.067 / 0.093; but easy trades without a tight stop add nothing (= the Nov 4 stop-ATR lead, which at
  room 0.4 loses $538 of H2 eval money).
- **E-LIT deep edge (2026-11-15, `2026-11-15-lit-deep.md`, `tools/lit_deep.py`, runs `lit_deep_*`, grid
  `research/lit/deep_grid.json`; eval two_week room_f 0.4 to session 80):** structural SKIP rules (engine `skip_keys`, the day
  left free for a later setup), Jan-Jun tercile and q80 cuts, 16 versions: target > 333 / 431 pts, target > 1.05 / 1.22 VIX
  day-moves, day range so far > 0.80 / 0.92 VIX moves, stop > 0.152 / 0.175 VIX moves, stop > 2.51 / 2.81 x 5m ATR, an
  opposing level within 0.97R / 0.61R, planned target < 7.46R / 6.13R, deep sweep + big displacement ("breakout"): none
  passes (best: target > 1.22 VIX moves LIT +$1,602 / +$81 but eval H1 -$2,872); the skipped trades still make +0.3-0.9R
  and a later setup rarely replaces them; trades fall to 1.2-2.4 a week in H2. Missed-setup census (cap 3 a day, limit / 1m
  CISD window doubled, 00:00-15:55, min target 1.0R, stop 4-120, Monday rule off): none adds money in H1. Loser structure:
  no single-fact bin loses in both halves; 425 two-fact H1 loser cells -> 88 lose again in H2 vs 95 by chance. H2 vs H1 =
  18% fewer trades/mo, 12% less R a trade (lower VIX, wider stops), 18% less $ per R; low-VIX trades +0.77R in both halves.

- **Smart entries (2026-11-17, `lit-smart-entries-2026-11-17.md`, `tools/lit_smart_entries.py`, 31 cells, grid
  `research/lit/smart_entries.json`; eval two_week room_f 0.4 to session 80):** same setups, other ways in. Pullback limit
  (candle 50% / 1m CISD level, 3 / 5 min, then market) only when the 1m CISD candle ran > 0.14 / 0.25R or is > 0.22 / 0.27R
  tall (16): H2 $2,670 -> $225-1,236/mo (closer BE + 15-min check scratch the H2 winners). 1m CISD OR a 1m BOS: +$1,778 /
  -$787, eval -$877 / +$2,069. CISD AND BOS / close above the zone / inside the swept level / 2+ down candles / strong close /
  close above the last high (7): Jan-Jun -$1.6k to -$24k. Wait 5-15 min for proof (4): -$8k to -$26k a half. Half now +
  half at minute 5 / 15 inside the same $ risk (3): -$8.7-10.1k / -$2.9-4.8k, eval 2-week pass 44.5 -> 15%. None passes.
  Wide-stop half size and an entry-quality score were not re-run (already rejected above).
- **Regime sizing (2026-11-17, `lit-regime-sizing-2026-11-17.md`, `tools/lit_regime_size.py`, 124 bucket cells, 8 size rules,
  grid `research/lit/regime_size.json`):** LIT x1.25 / x0.75 by the prior close's regime: GEX sign / level ($bn), VIX level /
  1-day change, VXN - VIX spread, VIX/VIX3M, prior NQ range percentile, 2-3 buckets each + every 2x2 pair, VIX / spread as a
  1-year percentile. Jan-Jun splits flip in Jul-Oct (VIX falling +1.09R vs +0.61R H1, +0.14R vs +1.24R H2); H2 sits in one
  bucket (VIX low, spread high, gamma positive on 38-40 of 40). Only gate-passer VIX/VIX3M high x range: +$37 / +$119/mo,
  placebo 0.53, 5+2 H2 trades, VIX3M ends 2026-09-17, 2021-25 -$1,089, 2-week pass 44.5 -> 42.0%. None adopted; Rapid not run.
- **Learn loop first night (2026-11-15, `docs/LEARN_LOOP.md`, queue `research/learn_queue.json`):** Zlarior size x1.25 on low dealer
  gamma / after a tight Asia range / on a many-times-touched or an old swept level / on a fast fill after the CISD, x0.75 the day after
  a VIX jump; ATLAS x1.25 after Zlarior was stopped on the other side, x0.5 on a two-way day: all 8 rejected (best: old level +$138 /
  +$125 a month at the LIT size but eval path Jul-Oct -$34). The loop re-checks them on new bars.

## Key commands (run from the repo root)
- **Nightly learning (2026-11-15, `engine/learn_loop.py`, `docs/LEARN_LOOP.md`, test `tests.test_learn_loop`, area nq):** free on the PC
  via `tools/pc_report.py`'s 15-min hook (weekdays >= 17:00 ET, Sat, Sun < 17:00 ET, once a day, skipped while not flat, detached
  below-normal child): refresh LIT (`tools/lit_edge.evaluate`) + ATLAS (`tools/atlas_deep.score`) + the live-loop twin on exports + `data/nt_bars`,
  drift from `engine/live_learning` reviews, then 2 queued experiments of `research/learn_queue.json` (LIT: `lit_edge.gate` + 2-4/wk +
  placebo; ATLAS: `atlas_v2.verdict`). Output `research/learn/` (gitignored); phone line only for a NEW candidate. Never writes a live
  file (hashed before/after) nor `research/runs/` (a candidate is re-run with `rl.save` by Claude). `python -X utf8 -m engine.learn_loop status|run --force|guard`.
- **Numbers audit (2026-11-04):** `python tools/numbers_audit.py` (`--check` exits 1 on any 'wrong'; `--all` shows skipped history; `--json`; test `tests.test_numbers_audit`).
  Read-only. Builds the facts from CLAUDE.md, `research/lit/mffu_rules.json`, `research/props/roadmap.json`, `research/lit/funded_firms.json`, `plutus/plans.json`, then scans
  every published file (tools/web_public, web_next, handoff, owner docs, hub snapshot, STRATEGY.md) for list prices, old funded figures (the trio: $2,147 a month on Jul-Oct,
  $2,655 Jan-Jun), the old headline, old 2-week pass / fail, "7 of 10 days", wrong job / app counts, wrong Builder limits. Run it before every publish; fix the SOURCE of a generated file
  (writeup summary, `build_web_dashboard.py` strings), then rebuild athena / obsidian pack / hub.
- **START BOT (owner's one start, 2026-10-26):** the owner now starts from the dashboard only (desktop **LE START** -> the
  Start page's **Start trading**, `go.step_auto`; Infrastructure, "Start & Accounts page"). `START_BOT.bat` -> `engine/go.py`
  stays for the console: the update (`autoupdate.pull`, bot stopped), names asked once (`data/start_bot.json`,
  gitignored), `launch_prep` once, both Sim101 roundtrips until passed once (market open only), owner types the LIVE
  phrase -> `arm_b` (`data/account_b.json` `"armed": true`, other fields kept), the live line in `.env.local.ps1`, server
  (re)started when that file is newer than the supervisor or the server runs older code (`go.server_stale`),
  `ninjatrader --start` on the 50K, launch checklist, dashboard. Wrong phrase = nothing armed. Tests `tests.test_go`.
- `python -X utf8 -m engine.autoupdate --pull`: the update now with the bot stopped (UPDATE.bat, START BOT); the same
  fast-forward as the auto-update. `python -X utf8 -m engine.account_b --migrate`: move ATLAS's block out of
  second_model.json by hand (the server does it at start).
- `python -X utf8 -m tests.test_poll_timing [--full]`: the poll stage timer and the outgoing-folder cache (`--full` replays
  test_lit_live's LiveBot with and without the timer, ~15 min).
- `python -X utf8 -m tests.test_poll_speed [--quick] [--compare]`: the LIT path of the poll (health.lit_ms) with every
  background feature on vs off (gate: median <= 1.6 x off + 150 ms, p90 <= 2 x off + 300 ms, median <= 3 s); worker =
  threads (orders, second run, ATLAS v2, pictures byte for byte); bar-frame deltas; worker deaths / hangs; news / ES off the
  poll path (~3 min; `--compare` also runs the old threads and checks the gate catches them).
- `python tools/export_backtest.py`: the live-settings 5-year replay → `research/lab/backtest_live.json`. Contains periods, months,
  stop buckets, eval odds, **per-trade reports** (why it entered / plan / result / lessons) and **lessons** (wins vs losses).
  About 1 min on 11 processes.
- `python tools/strategy_lab.py engine --name X --period ytd --params '{...}'`: score a variant. `tools/five_year.py live_jobs`
  is the exact live-loop replay.
- **Research run library** (`tools/runlib.py`, 2026-10-17): every experiment is stored with all its trades and days in
  `research/runs/<id>.json` (+ `index.json`), scored like the live results (2026 / 2021-25 / all, MFFU evals). `rl.replay(params)`
  is the exact live-loop replay (~1.5 min on 4 cores, cached in `research/runs/_cache`), `rl.size(raw, rule=...)` re-sizes
  after the fact (exact), `rl.save(...)` stores a run. `python tools/runlib.py baseline` stores the live strategy. Write-ups go in
  `research/writeups/*.md` (front matter: title, family, date, status, summary, runs). Both dashboards show runs and write-ups
  (Lab). New engine options must default to today's behaviour; bump `ENGINE_EPOCH` in runlib if an existing option changes.
- `python tools/trade_gallery.py --trades <json> --name <n> --all`: annotated trade charts → `research/lab/gallery/` (gitignored).
  Study trades the owner is reviewing are in `research/study/`.
- `python -X utf8 -m tests.test_live_dryrun --quick`: the live-loop harness. Expected 41/44 (pinned to the old engine); known fails:
  - replay entries/exits vs plain backtest
  - restart exit routing
  - kill switch later-route
  - "hygiene" (only when the PC bot is running)
- `python tools/cloud_monitor.py --out <tmpdir>`: dry run of the PC-off monitor (README + chart for the `dashboard` branch).
- `python -X utf8 tools/trade_intel.py`: Trade intel (2026-10-21) -> `research/lab/trade_intel.json`: every LIT trade (run
  lit_live + cloud paper + PC live) with ~60 entry / outcome facts and the win-loss signs (terciles on H1, checked on H2;
  8/50 "consistent" vs 13.4 by chance: descriptive only, `lit-trade-intel.md`). Rebuilds only when lit_live changes; the
  cloud build appends paper / live rows (site `intel.json`). PC Data → Trade intel, phone Trades → Trade intel. Tests:
  `tests/test_trade_intel.py` (no look-ahead on cut data), `tests/test_pcdash_api.py`.
- **Bot Brain (2026-10-21, read-only, `engine/brain.py`, `engine/brain_api.py`):** after every LIT poll (after routing and the
  state save) the PC bot builds `BOT.brain` from that poll's own market (`lit_live.run(keep=)`): stage pipeline + "waiting
  for" sentence, every level, every setup today with each rule check vs its threshold (engine order; first ✗ = why), sizing
  math, trade management, guards, thought log (`data/brain/YYYY-MM-DD.jsonl`, gitignored). API `/api/next/brain`,
  `/brain/log`, `/brain/days`, `/brain/day/<date>?t=` (any 2026 day replayed). PC: top-level "Bot Brain" (`web_next/js/next/brain.js`);
  phone: Home → Bot Brain + Home tile (`tools/web_public/brain.js`) from `live.pc.brain` (heartbeat + live.json, `brain.compact`
  < 16 KB), else the cloud's `live.brain`. Tests: `python -X utf8 -m tests.test_brain [--quick]` (filled = backtest trades
  on every 2026 day, rejected = the engine's rule, no look-ahead, sizes); screenshots `tests/shots_brain.py`.
- **Performance page (2026-10-21, competitor-features #6/7/9/11-14, read-only, `lit-robust.md`):** PC Data > Performance,
  phone Money > Performance (one renderer `tools/web_public/perfcore.js` = `web_next/js/next/perfcore.js`, view
  `engine/perf.py`, `/api/next/perf`, data.json `perf`). Range = `engine/health_band.py` (H2 bootstrap of lit_live, rebuild
  `python -m engine.health_band build`); live vs backtest = fill-audit curve (heartbeat `exec.curve`); exit efficiency =
  `tools/trade_intel.py --exit-eff`; robustness = `tools/lit_robust.py` (2026: +/-1 tick 92%, 0-3 ticks slip 98%, 20%
  missed 80%, 2 min late 68%); months = `tools/lit_walkforward.py` (re-picking loses: +$29.3k vs fixed +$33.3k);
  status = `engine/uptime.py` (cloud state `uptime`, PC `logs/uptime_pc.json`); look-ahead = `tools/lookahead_audit.py`
  (499 LIT runs, 0 flagged; `LE_LOOKAHEAD=1` checks each `rl.save`). Rerun the research tools weekly on the PC and commit
  the JSON. Tests: `tests/test_perf.py`.
- `python -X utf8 -m tests.test_no_yahoo`: no Yahoo / yfinance call in the PC loop or the cloud monitor (yfinance replaced by a
  raising stub), FEED STALE blocks entries, PC bars push/read roundtrip, roll back-adjustment, CBOE VIX (23 checks, ~10 s).

## Infrastructure
- **Real dashboard (2026-11-13, `docs/LIVE_DASHBOARD.md`):** `LIVE_LINK.bat` -> `scripts/live_link.ps1` (Tailscale `serve`, tailnet
  only, never Funnel) -> the PC's own server serves the whole site at `/site/` (`engine/live_site.py`, 9 lines in `server.py` in
  try/except): Gate at `/site/gate/`, live bot numbers over home.json (`/api/site/live.json`), `/site/kalshi.json` from the VM's feed,
  money files; every non-GET over the link refused. Rebuild task `OlympusLiveSite` (15 min). Tests `tests.test_live_link` (area pc).
- **One double-click (2026-11-14, `docs/SETUP_EVERYTHING.md`):** `SETUP_EVERYTHING.bat` -> `scripts/setup_everything.ps1`: the code zip update (skip if applied, never older over newer; a zip's older repo copy of live_model*.json is replaced via `tools/model_versions.json`), step 1b AUTO-UPDATE (`engine.autoupdate --source-status`, then `--connect`: the one GitHub sign-in as the backup's account; any non-0 code is one SKIP), the Tailscale phone link, then after a typed YES (Sunday 18:00 ET+) GO_LIVE_EVAL's flow where the owner types the live phrase; the script never holds the phrase. Test `tests.test_setup_everything` (area pc).
- **Launch kit (2026-11-14, `docs/LAUNCH_DAY.md` from `tools/launch_day.py`):** entry/exit pushes per account in `tools/pc_report.py`, real fill vs plan `tools/fill_check.py`, the Launch card `tools/launch_card.py` -> GET `/api/site/launch.json` (engine/live_site.py) -> `gate/launch.js` (PC link only), the 01:35-01:59 ET ready push via `tools/pc_guard.py`. Test `tests.test_launch_kit` (area pc).
- **Tonight on the eval:** `GO_LIVE_EVAL.bat` = `bots_back.ps1 -NoResume` then `engine.go` (the owner types the live phrase).
- **Bots back without GitHub (2026-11-12, `docs/BOTS_BACK.md`):** `BOTS_BACK.bat` -> `scripts/bots_back.ps1` (GitHub-free switch
  `%USERPROFILE%\.olympus\no_github`, NinjaTrader + LE_BarFeed check, resumes only a paper / Sim autostart, six-line card; undo
  `UNDO_BOTS_BACK.bat`). `tools/pc_report.py` (task `OlympusPCReport`, every 15 min): phone pushes to the owner's private ntfy topic
  (`%USERPROFILE%\.olympus\ntfy.json`) and a small live status to the public topic in `tools/web_public/status_feed.json`;
  the site reads it first through `pc_feed.js` (root `live.js`) and `olympus/truth.js` `withPcFeed()` (NQ, Aegis, Helios,
  Ergasterion, people). Code reaches the PC as a code zip (`git archive` without research/ data/ docs/shots, < 400 MB) +
  `.sha256.txt` -> `UPDATE_FROM_ZIP.bat`. Test `tests.test_bots_back`.
- **The dashboard updates itself (2026-11-14, team U2):** SETUP_EVERYTHING step 1c asks ONE hidden paste of a Netlify key (skipped when key + site + task are there) -> `tools/pc_publish.py --setup netlify --site-name moonlit-scone-08afe5 --token-stdin` (the site id looked up with the key; exit 0 saved / 3 refused / 4 no such site / 5 no internet; the key never printed), then `scripts/publish_nq.ps1` as is. The PC deploys the LITE set (`LITE_EXCLUDE`: charts/ replays/ writeups/ datacity/ mind/ stay on the PC for the Tailscale link; `"site_set": "full"` in publish.json sends everything), every file re-scanned before it goes (`deploy_set`; a private file is kept out and named; no scan = nothing sent), never `day/` or `me/`. Tests `tests.test_pc_publish`, `tests.test_public_build_privacy` (area pc).
- **NQ without GitHub (2026-11-10, `docs/NQ_BOT_BACK.md`):** the GitHub account is gone. `engine/nogithub.py` (marker file `%USERPROFILE%\.olympus\no_github` or `LE_NO_GITHUB=1`) makes the heartbeat write `logs/pc_hb/` instead of pushing and switches off live.json push, remote control and git auto-update (trading code untouched). `tools/pc_publish.py` (task `OlympusPublishNQ`, `PUBLISH_NQ.bat` / `UNDO_PUBLISH_NQ.bat`, `scripts/publish_nq.ps1`) runs the cloud monitor with the PC's own heartbeat, builds the site and publishes via provider folder / netlify (token in `.olympus/netlify.json`, never in the repo; digest deploy; budget 18 deploys a month because Netlify's new free plan allows about 20) / none. STATUS shows the last publish. Kalshi VM kit: `--publish folder|netlify|scp`. Tests: `tests.test_pc_publish`, `test_win_scripts`. Open: Kalshi pages still read the old GitHub feed URL.
- **The PC updates itself again, from the backup repo (2026-11-14, `docs/AUTO_UPDATE.md`):** owner chose a PRIVATE repo `dcondax1-wq/olympus` on his second GitHub account (the first is gone). `update_source.json` (root) names it: remote `olympus`, branch `pc`, the account in the URL. `engine/autoupdate.py`: `source()`, `--connect` (one time, SETUP_EVERYTHING's auto-update step: any folder state -> exactly the backup's newest commit; snapshot `refs/olympus/before-connect`, copies of unknown files in `logs/connect-*`, self-tests, full put-back on failure; exit 0/20/21/22/1), `--source-status` (0/10), then the normal strict fast-forwards of `olympus/pc`. GitHub-free mode blocks only origin. An eval bot without auto-resume updates only in the Friday / Saturday halt (`live_wait_reason`, `LIVE_UPDATE_DAYS`). **Lead: ship to the PC = push the tested release to `olympus` branch `pc`** (add_repo push first; the backup's `main` is a README only, so no scheduled Actions run there). Tests: `tests.test_autoupdate_source`, `tests.test_autorun`, `tests.test_pc_publish`.
- **NQ back on the phone + update from a zip (2026-11-11):** app `nq/` ("the NQ bots, right now": per bot running / waiting for the PC / stale with the exact age of the last report, drawdown left, the day's $ with R, eval progress, last 10 trades with the closing rule, the 5-step sheet = `nq/howto.json` built from `docs/NQ_BOT_BACK.md` by `tools/nq_howto_build.py` (`--check`); reads `home.json` only; a flame burns only for a bot that reported in the last 20 minutes; test `tests.test_nq_page`). Root page: `zenith_nq.js` puts the same banner sentence + "Open the new NQ page" above Home (`tests.test_zenith_nq`). PC update without `git pull`: `UPDATE_FROM_ZIP.bat` / `UNDO_UPDATE.bat` -> `tools/update_from_zip.py` (the zip of `tools/make_backup.py`; SHA-256 against the `.sha256.txt`; refuses while the bot's server answers on the port, asks while the market is open; never writes a local-only file (hard list + `.gitignore`), keeps a `live_model*.json` whose values differ; backup + manifest in `backups/update_from_zip/`, a failed write rolls back; six-line summary; never starts the bot; test `tests.test_update_from_zip`). `UPDATE.bat` and `engine.autoupdate` needed the lost account; since 2026-11-14 they work again once the PC is connected to the backup repo (see the line above).
- **CRONOS (2026-11-03, `docs/CRONOS.md`, `tools/cronos/`):** keeps the research apps' data and Jarvis cards alive for free. `cronos.yml` nightly 04:07 UTC Tue-Sat (= Mon-Fri nights, after `datacity.yml` 03:37 UTC): FATES (from the latest live.json) + ODEON (only when the heartbeat branch has newer PC bars); Sunday 19:17 UTC: DAPHNE + PROMETHEUS (only when their data/code fingerprint changed). Each task in a subprocess with its own timeout (5-30 min); outputs replace the last good ones only when valid; `cronos/status.json` records ok / error / last_ok_t; one force-pushed commit to the `cronos` branch (main never gets bot commits, GITHUB_TOKEN only). Saver mode (`budget.json`) skips the heavy tasks. At every site build `tools/cronos/site.py` (called before HERMES, in try/except) fetches `cronos` + `datacity` (only in Actions or with CRONOS_FETCH=1; CRONOS_DIR=<dir> for a local copy), copies an app in when its branch card is newer, then stamps every research card (datacity, fates, odeon, tree, prometheus) with t = the publish: fresh = engine status + "Updated nightly · last run ..."; stale (> 36 weekday hours, weekly 156) or failed = amber "Not updated since ...". Budget ~175 min/month (at most ~260) + Data City ~66. Jarvis still greys every card 30 min after a publish (apps.js STALE_AFTER_S), i.e. overnight and on Saturdays.
- **CLEAN_PC + PC kit (2026-11-02, `docs/PC_PERFORMANCE.md`):** `scripts/clean_pc.ps1` auto-detects the bot folder
  (server.py + engine/ninjatrader.py); without it (main PC) it runs STANDALONE: closes nothing (lists only), keeps Xbox /
  gaming apps, deep part any time unless NinjaTrader is open. Every run: a read-only NinjaTrader check (OneDrive, ATI,
  workspaces: days loaded / Tick Replay / indicators read from `<DaysBack>` / `<IsTickReplay>` / indicator type names; the
  LE_BarFeed chart stays at 30 days; tick db size; workspace backup to `logs\nt_workspaces-DATE`) and `PC_REPORT-<pc>.txt`
  (gitignored). `-Report` = report + NinjaTrader check only. The bot-PC run copies the kit to `OneDrive\PC_KIT` (else the
  Desktop). Test `python -X utf8 -m tests.test_clean_pc` (pwsh: 5.1 lint, AST-loaded rules, sandbox dry runs with
  `tests/win_harness/clean_pc_stubs.ps1`, and again under StrictMode 2).
- **CLEAN_STORAGE (2026-11-04, owner: "an easy way to clear storage through both of my computers"):** `CLEAN_STORAGE.bat` ->
  `scripts/clean_storage.ps1` (also `clean_pc.ps1 -Storage`; the PC_KIT gets both files; alone, the .bat fetches
  `pc/clean_storage.ps1` from the site, so the build only needs the two files in `tools/web_public/pc/`, which
  `tools/build_web_dashboard.py` already copies; a test keeps them identical to the repo files). Flow: table of sizes per
  category -> Y -> the user part (no admin) -> one UAC prompt for the Windows part (`-SystemPart`, result handed back via a
  temp file) -> "Freed X, C: now Y free". Recycle Bin and Windows.old asked separately (`-Extras` answers Y). Safety: every
  delete goes through `Remove-SafeFile` / `Remove-SafeEmptyDir` / `Remove-SafeTree`, which refuse anything not under an
  allow-listed root (roots equal to the profile, bot folder, NinjaTrader folder, drive, Windows dir or ProgramData are refused),
  anything named like state / secrets / journals / accounts, and anything in `nt_bars`, `workspaces`, `templates`, `le_feed`,
  `incoming`, `outgoing`, NinjaTrader `db` (except `db\cache`), or the bot's `data\` (only `*.corrupt-<n>` directly inside).
  Bot or NinjaTrader running (process, port 8766, supervisor.pid) -> the `nt` and `bot` categories and Windows.old are skipped.
  Test hooks (env, tests only): `LE_T_ELEVATED`, `LE_T_ANSWER`, `LE_T_BIN_BYTES`. Health: `engine/pc_health.py` adds the
  `storage` line + `storage` block ({free_gb, bot_gb, nt_gb}; capped folder walk every 6 h, never in the first 5 min);
  `live_publish.pc_health_summary` shows it as "Storage" instead of the Disk line (Jarvis System view). Tests:
  `python -X utf8 -m tests.test_clean_storage` (sandbox tree, real process named NinjaTrader, bot port, hostile TEMP).
- **Jarvis hub (2026-10-31, owner: "Jarvis is the brain, switch right to the other dashboards"):** `tools/web_public/jarvis/`
  (index.html, manifest, sw.js, icons; published at `<site>/jarvis/` by `tools/build_web_dashboard.py` with every build).
  Its own Home Screen app: the Jarvis screen first (greeting, NQ market line, Zenith card from live.json `board` /
  `pc_verdict`, Planner card from the Planner's saved `planner.v1`, Kalshi card), a top bar that opens each dashboard in
  its own kept-alive iframe (Zenith `../`, Planner `../planner/`, Kalshi = `KALSHI_URL` in index.html or a link pasted on
  the phone, extra dashboards via +), rule-based answers (status / room / target / P&L / today / market / "open X"),
  voice when the phone has speech recognition. Read-only. On iPhone each Home Screen app has its own storage: the Planner
  inside Jarvis needs its sync connected once. BLITZ (2026-10-31): the Zenith card and the answers carry BLITZ from
  live.json's top-level `blitz` (`engine/live_publish.blitz_block`: board card keys, an "off" card while account C is off,
  None on failure; `board.blitz` stays present only while account C is on); "how's blitz" answers instead of opening Zenith. Test `python -X utf8 -m tests.test_jarvis_hub` (166).
  **Service workers share one origin (fix 2026-10-31, "Jarvis won't load"):** Zenith's `tools/web_public/sw.js` (scope =
  the whole site) used to delete every other cache on activate and handle `jarvis/` + `planner/` pages, so once Zenith was
  opened inside Jarvis a dropped connection or a site 404 left Jarvis with nothing to open (reproduced over local https).
  Now Zenith's worker skips `OTHER_APPS` (jarvis/, planner/) and deletes only `le-public-*`; Jarvis's worker (jarvis-v2)
  saves each file on its own and answers offline / 404 / 5xx from its saved copy. A new app folder on the site goes into
  `OTHER_APPS` and keeps its cache names to its own prefix.
  **White screen (fix 2026-11-01):** an iPhone Home Screen app is white while its page loads or after a failed load. Jarvis's
  worker (jarvis-v3) answers the page from its saved copy when the network takes > 3.5 s (the late answer still refreshes the
  copy), and with no network and no copy serves a dark Retry page; old: a slow connection = white until the site answered
  (20 s in the test). Jarvis always starts on its own screen (the address never keeps #zenith; an old #hash is cleaned at
  start), keeps one dashboard loaded at a time (one iPhone web process), shows a Reload note if its script has not started in
  8 s, and the manifest has no #shortcuts. Recovery on the phone: delete the Home Screen icon, re-add from Safari.
- **Jarvis v2 (2026-11-01 sprint, owner: "the same sick looking Jarvis with all the features it had before ... switch
  between that mode, zenith mode"):** it rebuilds the owner's old PC voice assistant on the phone (spec, look and features:
  `docs/JARVIS_OLD_LOOK.md`). Modules in `tools/web_public/jarvis/`:
  - **Shell:** `index.html` + `jarvis.css`.
    - Look: the violet HUD, with Reactor as the default theme (matches the icon). The 24-theme family lives in
      localStorage `jtheme`. Orbitron and Rajdhani are self-hosted woff2 (OFL).
    - Screen: the boot log; the mode chips JARVIS · ZENITH · PLANNER · KALSHI · +; the KALSHI TODAY and NQ BOTS TODAY
      boxes; the HUD panels; the glass command bar with mic/send and the ⋯ menu (core, full screen, look/theme, AI key,
      hold-to-talk, 3D, tilt, alerts, calm motion).
    - Unchanged rules: one dashboard frame at a time (Zenith is unloaded when another opens; kept while Jarvis shows),
      always start on Jarvis, no #hash, the 8 s boot note.
    - Cross-site frames get a sandbox and no allow=.
  - **`data.js`:** the one facts facade: live.json, kalshi.json from the kalshi-feed repo, the Planner day including
    `planner.today.v1`, the market clock. Every reader is total, so junk storage never stops boot.
  - **`brain.js`:**
    - Rule answers: a briefing, follow-ups, the old Jarvis commands, Zenith routes via `zenithRouteFor`, `control`
      replies (stop / mute / hide balance) and Kalshi outcome alerts.
    - Smart mode with the owner's own Groq / Gemini / Anthropic key, stored only in localStorage `jarvis.smart` and sent only
      to that provider. CORS is verified for all three.
  - **`core-visual.js` + `three.module.min.js`:** the old violet Gimbal Reactor, three@0.160.0 loaded on demand.
    - The reactor and singularity designs, 5 states, effects ultra / high / low / off.
    - A 2D fallback, plus recovery after WebGL context loss.
    - motion:'always' by default (the old app ignored the OS setting); "Calm motion" follows the iPhone.
  - **`apps.js`:** the registry and the `jarvis.json` live-card contract (`docs/JARVIS_APPS.md`), plus the Ascend slot.
    - No same-origin guessing.
    - Same-site apps get a warning, because every page on demetrades2000-coder.github.io can read Jarvis's and the
      Planner's saved keys.
    - Ascend must be hosted on another origin.
  - **`zenith-mode.js` + Zenith's `embed.js`:**
    - Zenith full screen, with an edge orb (tap = Jarvis, hold = app chips), the route and scroll kept.
    - An origin-checked postMessage protocol, documented at the top of zenith-mode.js.
    - A non-secret settings transfer code.
    - Zenith detects it's inside Jarvis: no nags, push only on a tap, safe areas once.
  - **The orb, `switcher.js` (2026-11-01, owner: "a way to access each thing, so calendar, kalshi, Jarvis, and my nq bot and
    eventually other stuff, make a really cool way to change between stuff"):** one glowing orb over every mode, above Zenith
    mode (z 2147483100; `html[data-nexus] .zm-back` hides Zenith mode's own control).
    - Tap: the switcher opens out of the orb (clip-path circle), one live card per app in a 3D carousel: JARVIS (time,
      market), NQ BOT (today's $ across the accounts, status), CALENDAR (next event, tasks), KALSHI (today, balance),
      each added app (its jarvis.json card), + ADD. A quick row of 46 px buttons below.
    - Swipe the orb left / right: the next / previous app. Hold (380 ms): the ring fans out; slide onto an app and let go,
      or tap one. Drag: move it (`jarvis.orb`, side + height). First uses: a tip (`jarvis.orb.tips`, 3 times).
    - It steps aside while typing and while a sheet or the ⋯ keys are open (`nxCover`). The iPhone's copy click after a tap
      is stopped (touchend preventDefault + a 350 ms guard). Light on purpose: no backdrop blur, transforms only.
    - Absent or broken: the bar's chips and Zenith mode's own control work as before. Saved offline from worker v7.
    - Tests: test_jarvis_hub run N (14 checks, incl. touch and reduced motion); test_phone_e2e goes back and switches
      through the orb. WebKit: tap, quick row, swipe, hold-and-slide.
  - **The System view (2026-11-02, owner: "everything combined and simple"):** every system at a glance, one verdict.
    - `data.js systemStatus(facts)` (also `getFacts().system`): one line each for the PC (checking in? bot running? the
      NinjaTrader feed fresh? CPU / RAM), Zlarior (50K; the PC's verdict), ATLAS (25K), BLITZ (off = grey), the Kalshi bot
      and the Planner day, and a verdict ALL GOOD / HEADS UP / NEEDS YOU with the one thing to do (`todo`, short `short`).
      A PC silent > 20 min is NEEDS YOU only while the market is open or opens within 2 h (grey on a quiet weekend), and the
      bots' lines then read "last known". Kalshi not connected / BLITZ off are grey, never counted.
    - The PC's CPU / RAM: live.json `pc_health` (`engine/live_publish.pc_health_summary`: the heartbeat's own
      `pc_health` block cut to t / level ok|warn|bad / cpu / ram / up to 8 {key, label, level, text <= 140}; scrubbed,
      absent before the first sample, dropped by `fit()` before the money card).
    - Screen: the strip in the header (verdict, the short to-do, a dot per system: PC Z A B K P; tap = the System panel),
      the System panel above "Your projects" (the one thing to do + a line per system; tap a line = that app). The orb:
      a red / amber dot while something needs the owner, and the same strip at the top of the switcher (tap = the panel).
      The core is 60vw (was 66vw) so HANDS-FREE · mic · VOICE stays on the first 390 x 844 screen. No blur, no animation.
    - Brain: "status", "is everything ok", "all good", "system check" = the System answer (verdict first, a line per
      system); "how's the pc" adds CPU / RAM and any amber / red line; "how are the bots" is unchanged.
    - Tests: `tests.test_jarvis_system` (24: publish -> data.js end to end, every verdict, junk), test_jarvis_hub run S,
      test_jarvis_brain part k, test_live_publish pc_health checks. Worker jarvis-v8, jarvis.css?v=j5.
  - **Every dashboard its own (2026-11-02, owner: "when I go into planner I see another theme at the top. I want everything
    its own dashboard"):** while the orb is mounted (`data-switcher="module"`), any mode but Jarvis hides Jarvis's bar,
    `.bgfx` and toasts, and the dashboard frame starts at the safe-area top; the status-bar strip and `theme-color` take the
    app's own colour (its theme-color, else its body background; `appTint` / `setTint` in index.html; black on the Jarvis
    screen). Switching inside a dashboard = the orb. No orb (switcher.js missing) -> the bar stays (the way back never goes).
    The open-on-its-own button lives in the bar, so it shows only on that fallback. Worker jarvis-v9, jarvis.css?v=j6,
    What's new j5. Tests: test_jarvis_hub c (`go()` helper = bar or orb), test_phone_e2e `tap()` goes home via the orb first.
  - **MFFU 7-day count (2026-11-02):** `live_board.quiet_days` (ET calendar days since the account's last trade, else since
    its eval start) on the Zlarior card (`pc.acct.trades[].day`) and the ATLAS card (`account_b.routed` entries). Jarvis's
    System view (data.js `bot()`): day 5 amber "place 1 MNQ by hand by tomorrow", day 6+ red "today", also while the PC is
    silent. `jarvis.json` may carry `theme: "#rrggbb"` (another site's top colour, e.g. Ascend; apps.js validateStatus).
    Worker jarvis-v10. Tests: test_jarvis_system (28), test_jarvis_apps (85).
  - **Manual keep-alive trades (2026-11-03):** the bot's ledger only sees its own orders. "I traded on both" / "traded on
    ATLAS" (brain.js) or "I did it" under the System warning writes `jarvis.manualTrades` {lit, atlas: ET date}; data.js
    `withManualTrades` (applied in getFacts().live incl. `.raw`, and in systemStatus from `f.manualTrades`) counts the quiet
    days from the mark while it is newer than the card's last trade. Tests: test_jarvis_system m, test_jarvis_brain m.
  - **OLYMPUS apps in Jarvis (2026-11-03):** one table, apps.js `BUILT_INS` (`app(id, name, group, accent, sub, more)`;
    url `../<id>/`, live card from its `jarvis.json`, top colour from its `theme`). Adding an app = one row there (and its
    folder in build_web_dashboard's app list). Groups `GROUPS` (TRADING, LIFE, MONEY, MORE) drive the bar order, the orb
    (headings, group chips, scrollable quick row, ring = 6 most opened + "more", `jarvis.orb.use`) and the Jarvis screen's
    OLYMPUS grid (`#olyApps`, stagger once at 3D High/Ultra). A folder not on the site (jarvis.json 404, no card) =
    `missing()`: tile "SOON", never opened, the swipe/ring skip it. Worker jarvis-v13 (obsidian.js, memory.js,
    assist-ui.js saved), jarvis.css?v=j9, What's new j8. Test waits use the page's ready marker (`html[data-ready]`,
    `window.__jarvisReadyMs`): under load the software-drawn 3D core holds the main thread 10-16 s after a 0.5 s start.
  - **Voice mode (2026-11-03, owner: "like the movie J.A.R.V.I.S."):** `voice-mode.js` `createVoiceMode(deps)`, a full-screen
    conversation. Enter: the wide "Voice mode" quick-action tile, hold the big mic 0.45 s (the dock's mic keeps
    push-to-talk), "Jarvis, voice mode" (brain.js control `voice_mode`), or search. Leave: END, "stop" / "exit voice mode"
    (`voice_mode_off`), a farewell (brain reply `end: true`), Jarvis out of sight, another app opening.
    - The 3D core full screen (the home core is destroyed while it is open: one WebGL core at a time), `setLevel` driven by
      a Web Audio analyser on the mic while you talk (getUserMedia only inside a tap; a hold's release counts) and by the
      voice's word boundaries while Jarvis talks (estimated pace until the phone reports them). A ring of spectrum bars,
      captions of both sides lit word by word, a HUD arc with the bots' verdict, and holographic cards of the numbers cited
      (`fragmentsOf`: the reply's card rows and "Name: $x" lines, copied as written) that float out as the name is spoken.
    - Turns: listen -> the shell's `answer(t, true)` (the same path as the Jarvis screen: brain, chat log, controls) ->
      speak `r.speak` -> listen; 3 silent turns = waits for a tap; tap = barge-in / pause. The voice (since 2026-11-03: tts.js,
      the same as the Jarvis screen): a natural female voice first (Ava / Zoe premium), novelty voices never; VOICE button
      steps through them (`jarvis.vmVoice` + `jarvis.voiceCfg.voice`).
    - No recognition (Home Screen app) or the recognizer refusing the mic: a type-to-talk field, said once per launch.
      Reduce motion (unless a 3D level was picked) / 3D Off: no loop, no analyser, all shown at once. The mic is released
      on every exit (tracks stopped, AudioContext closed). Loaded 1.5 s after the start, never part of it.
    - Worker jarvis-v14, jarvis.css?v=j10, What's new j9. Test `python -X utf8 -m tests.test_jarvis_voice` (fake mic flags,
      mocked recognition / voice; screenshots in `research/handoff/2026-11-03/voice/`).
  - **The personal assistant + her voice (2026-11-03, owner: "my own personal assistant that I can tell anything. ANYTHING.
    And it responds with a voice that doesn't sound like a bot. Should be a female voice."):** two new optional modules.
    - `assistant.js` `createAssistant()` (no imports, no network; localStorage `jarvis.assistant.v1`, persona `jarvis.persona`
      {name 'Jarvis', style short | chatty}). The brain asks it after a pending "yes"/"no" (memory.js) and before the vault:
      facts ("my mom's birthday is March 3", "I'm allergic to …", "I love …", "remember …", "call me D"; same subject =
      replaced; "forget …"; passwords / keys / card numbers refused, never kept), recall ("when is my mom's birthday", "what
      did I tell you about Sam", "what do you know about me"; a weak "what's my X" only on a match, so "what's my balance"
      stays the brain's), reminders ("remind me at 5 / in 20 minutes / tomorrow at 9am / on friday / tonight to …"; no time
      = the to-do list; `due()` fires each once, a missed one marked late), to-dos (Jarvis's own list: the Planner's data is
      only changed by the Planner, so nothing is written into it), notes, maths and money (a safe parser, no eval), talk style
      and her name ("your name is Nova").
    - With the vault connected, what she kept is offered to Obsidian through `memory.offer(kind, text)` (the same confirmed,
      append-only write: "Save it to … too? Say yes."). `memory.connected` says whether it is.
    - Open conversation: `assistant.isChat()` (life, school, gym, money, girls, plans, venting, long messages; never a
      system word) after the rule answers (greetings, thanks, help stay). Smart mode on: `smartAnswer(…, chat)` with
      `assistant.persona()` as the system prompt's head (a warm, sharp, loyal young woman; money first; his trading rules;
      the talk style; what he told her; 988 if he talks about hurting himself) + the FACTS JSON for every number of his;
      the model's `[remember: …]` line is learned (`assistant.learn`), never shown or said. No key: her short line + the
      3-step key hint (`assistant.offline`). "should I …" chat is never "Your call, sir".
    - `tts.js` (the shared voice, also voice mode's): `voiceScore` female natural first (Ava > Zoe > Allison > Samantha;
      premium +50, enhanced +30, compact −10; male −40; Zarvox / Bubbles / Bad News / Fred … = never), `cleanSpeech` (no
      markdown, emojis, links, symbols; $ / k / % / per month in words), `speechChunks` (sentences ≤ 180 chars, commas for a
      breath), `createSpeaker` (one utterance per chunk, 140 ms between sentences; rate / pitch 1.0 by default). The
      optional cloud voice: Groq Orpheus (`canopylabs/orpheus-v1-english`, voice hannah) on his own Groq key, only with the
      Voice sheet's switch on; any error = the phone's voice, a 429 parks it for the day. Groq lists Orpheus on its free
      tier (no card) with small daily limits (unverified from the cloud session: console.groq.com was not reachable).
    - Shell (`index.html`): loads both after the start (`ready.tts`, `ready.assistant`, the brain waits 4 s for the
      assistant); `speak()` uses the speaker; reminders checked every 15 s and on open (chat line, toast, voice, a
      Notification when allowed: the first reminder offers "Allow"; iPhone only from the Home Screen app); the Voice sheet:
      voices best first with labels, talk style, the cloud switch, a one-time Ava (Premium) tip (`jarvis.tip.ava`).
    - Tests: `tests.test_jarvis_assistant` (node on a mocked ET clock + mocked Groq, then Chromium); test_jarvis_voice
      now expects Ava (Premium). New files for the worker's SHELL: `assistant.js`, `tts.js`.
  - **Tools: "an answer to everything" (2026-11-03, owner: "it needs to be smart ... add to the Obsidian, write notes down, do
    a ton of stuff"):** new `tools.js` (no imports; passed as `createBrain({ tools })`, the shell loads it as `ready.tools`).
    - 18 tools in one schema (`DEFS`, `toolSchema('openai' | 'gemini' | 'anthropic')`): obsidian_append_note (inbox / daily /
      a named note), obsidian_create_note (`OLYMPUS/Notes/<title>.md`), obsidian_search, obsidian_read, add_task,
      list_tasks, set_reminder, remember_fact, recall, get_bots_status, get_money, open_app, get_weather (open-meteo),
      wiki_summary (Wikipedia REST + search), web_search (DuckDuckGo instant answers + Wikipedia search: there is no free
      key-less full web search a browser can call, and Jarvis says so), calc (units + the assistant's maths), define
      (dictionaryapi.dev), time_in (a zone table, else open-meteo geocoding). Network only to those free CORS hosts
      (`HOSTS`, checked 2026-11-03), no credentials ever.
    - Smart mode with tools: brain.js `wire()` builds every provider's request (Groq / OpenRouter OpenAI-style `tools` +
      `tool_choice auto`, Gemini `functionDeclarations` with upper-case types, Anthropic `input_schema`); `parseReply` ->
      `{ text, calls, turn }`; up to 3 tool rounds in 18 s, results sent back in the provider's own format (Gemini's
      thought signatures kept). A write tool never writes: `memory.confirmWrite()` names the file ("Save this to
      OLYMPUS/Notes/Leg day.md? Say yes or no.") and only "yes" writes (append-only / new file only). A 400 retries once
      without tools. Requests to make / write / explain something ("make me a leg day plan and save it") go to the model
      before the rules (`WANTS_MODEL_RX`, never with a bots / money word).
    - Providers: + OpenRouter (`sk-or-` keys, default `meta-llama/llama-3.3-70b-instruct:free`, `X-Title: Jarvis`).
      `brain.testKey({ provider, key })`: one tiny request, `{ ok, ms, error }`. The setup screen: assist-ui.js
      `mountKeySetup()` (Groq / Gemini / OpenRouter tabs, 3 steps each, the key page button, Test, Save only once it
      answered); opened from ⋯ → AI key → "Free key setup", the "Connect my brain" panel, the palette, or by saying "set up
      smart mode" (`control: 'ai_setup'`).
    - No key: `tools.local()` answers the weather (city, last city, his "I live in ..." fact, else the phone's location),
      "and tomorrow?" / "no, I meant Miami", time zones, units, definitions, "look up ..."; after the rules, "who / what is
      ..." from Wikipedia. One time only (`jarvis.keyOffer`), after a useful answer: the free smart mode offer.
    - Natural notes (assistant.js `parseNote`): "write down / note that / jot down …" (inbox), "make a note called X: …"
      (new note), "add … to my gym note" / "add to my gym note: …" (his own note with that title, else a new one), "log
      today: …" (today's daily note, else the inbox). Connected: offered to the vault (yes / no). Not connected: kept on the
      phone and queued in the vault's outbox (`memory.queue`), sent on connect. obsidian.js: `write(kind, text, ymd,
      { title })` with kinds daily / append / create, `resolve()`, `read()`, `safePath()` (never a hidden folder or `..`).
    - Every reply carries `say` (plain words for the voice: no markdown, links, emojis or symbols). The model sees the last
      10 turns (`HIST_MAX` 20 messages).
    - Tests: `tests.test_jarvis_tools` (25 checks, one mocked fetch for every host). New file for the worker's SHELL:
      `tools.js` (sw.js not bumped by this change).

  - **Jarvis talks (2026-11-03 evening, owner: "the Jarvis isn't talking, I want you to fully make the bot talk"):**
    - Root causes: (1) typed answers were never read (`jarvis.speakAll` "Read every answer" was off by default; only
      answers to the mic were); (2) iOS WebKit plays speech only after a `speak()` made inside a tap, and every answer is
      said after an await (the brain, the mic), so on a fresh launch it was dropped silently with no end event; (3) the
      speaker spoke right after `cancel()` (WebKit swallows it), kept no utterance refs, had no watchdog for a missing
      `onend`, and passed unchecked rate / pitch.
    - `voice-out.js` `createVoiceOut({cfg, cloud, onSpeaking, onWord, onPending, micBusy})` (loaded at the start): the
      switch `jarvis.speak` on/off (default on; first run clears an old `jarvis.mute`, kept in step for the intro), the
      first-tap unlock (capture listeners on touchend / pointerup / click / keydown: a silent primer utterance on Apple
      WebKit (`tts.needsPrimer`), an AudioContext resumed + one silent sample), an answer before any tap waits and is said
      at the next one ("TAP TO HEAR"), the voice list re-polled while empty (+ `voiceschanged`; empty = the default voice,
      en-US), iOS 17 `navigator.audioSession` 'playback' while she speaks / 'auto' before the mic, stop when hidden.
    - `tts.js` speaker: utterances referenced until they end, a per-chunk end watchdog, a start watchdog (`onstall(rest)`:
      on the iPhone the rest waits for a tap), 70 ms after a cancel before the next speak, `synth.resume()` when paused,
      rate / pitch clamped 0.5-2. Voice mode uses the same speaker and primes on its taps.
    - Shell: every answer said while the dock's speaker button (`#spk`, next to the mic) is on; "mute" / "unmute" and the
      Voice sheet's "Read answers out loud" are the same switch; a waveform across the core + "TAP TO STOP" while she
      speaks (tap the core or the mic to stop); Test voice says one sentence; the Voice sheet notes the Ring / Silent
      switch. On a phone <= 360 px the SEND key hides (the keyboard sends).
    - Test `PLAYWRIGHT_BROWSERS_PATH=<dir> python -X utf8 -m tests.test_jarvis_talk` (node speaker + Chromium + WebKit
      iPhone 13 on a mocked voice that drops a speak() outside a tap like iOS). New SHELL file: `voice-out.js`.
  - **Modes + "think for me" (2026-11-03 night, owner: "make modes for research, trading, business whatever so it is smart.
    You should think about things, it shouldn't just be me"):** new `modes.js` (no imports, no network; passed as
    `createBrain({ modes })`, the shell loads it as `ready.modes`; absent = the brain as before).
    - Modes Auto (default) · Trading · Research · Business · Life, kept in localStorage `jarvis.mode`. Switch: the chip row above
      the quick asks (`#modeRow`, assist-ui.js `mountModes`) or the words ("switch to research mode", "Research mode.", "money
      mode" = Business, "personal mode" = Life, "auto mode"; `parseSwitch`). The reply: control `mode`, the mode's greeting
      (said out loud) + its list. Auto picks the mode per question from its words (`pickMode`).
    - Each mode changes: the smart prompt (a `MODE: ...` line in `systemFor`), the tools offered first (`orderTools`, every
      provider's format), the quick asks (`brain.suggestions()`: the urgent chip first, then the mode's), the home cards (the
      mode's apps with their live status in the list box), the greeting. Trading = bots, room, the plan, risk; Research = Data
      City / Prometheus / DAPHNE / the Mind + Wikipedia / web + research notes to Obsidian (one tap = "make a note called
      Research log: ...", confirmed by the vault); Business = money goal, more accounts (real prices), Kalshi edge, to-dos with
      deadlines ("by friday", "due nov 5", `parseDeadline`); Life = Planner, reminders, Ascend.
    - "Here's what I'd do" (`thinkAll` / `thinkFor`, rules, no key): from `brain.digest()` (the ranked priorities, quiet days,
      accounts, window, Kalshi, Planner, his to-dos + reminders, the Mind, the money card, apps) + the research apps' last
      cards: the 7-day rule (early at day 3-4, urgent from day 5), room under 40%, near a pass / passed, stale feed or research
      data (> 36 h: CRONOS), overdue / due-soon to-dos, a reminder within 3 h, the Mind's idea, the newest finding, tomorrow's
      plan (evening), the money goal, the Kalshi edge, Ascend. Urgent (p <= 2.5) first in every mode; 3 items. Every action is
      ask / open / mode / control (key setup): never a trade.
    - The modes' own quick asks answered by rules (`modes.answer`, no key): "Am I at risk?", "Today's trading plan", "Research
      findings" / "A research idea worth testing" / "Data City findings", "Plan for more accounts", "My to-dos with deadlines";
      with a key the idea and accounts questions go to the model (the rule answer is its fallback).
    - "Think for me" (button, or "think for me" / "what would you do" / "any ideas"): with a key, one request (no tools) with
      the MODE line + the rule list, the model's 3 suggestions as JSON with follow-up asks; any error = the rules.
    - Proactive: on open the list shows unasked (quiet); at 7:30, 12:00, 4:15 PM and 9 PM ET (once per slot, `jarvis.mode.slots`)
      while Jarvis is open: the list, a toast and her voice (never over the mic or a reply).
    - Test `python -X utf8 -m tests.test_jarvis_modes` (31: node + Chromium; `JARVIS_MODES_NO_BROWSER=1` = node only). New SHELL
      file: `modes.js` (worker not bumped).
  - **Icons:** the re-rendered old reactor icon (`?v=j2`).
  - **Workers:**
    - jarvis-v4: a 3.5 s navigation race; shell files stale-while-revalidate once a page came from the copy.
    - jarvis-v5 (2026-11-01, "Jarvis isn't opening" on the iPhone): WebKit stops the old worker's downloads the moment a new
      worker takes over (reproduced in Playwright WebKit: "Service Worker context closed" on module imports mid-start). A new
      worker now waits; the page posts `jarvis:activate` only while it is hidden (or the browser swaps it in once Jarvis is
      closed). Install fetches with `cache: 'reload'` (v4 could save the previous version's files from the HTTP cache).
    - jarvis-v7 (2026-11-01): switcher.js joins SHELL.
    - jarvis-v6 (2026-11-01, "Just a black screen"): an iPhone Home Screen app is black while its page or its render-blocking
      stylesheet is on the way, and v3-v5 waited on the network without limit for a file with no saved copy (reproduced in
      WebKit: no copy + a stalled download = nothing drawn). Now `NET_MAX_MS` (9 s) bounds every wait: a page with no copy
      gets the dark "can't load right now" page with Retry, a file with no copy fails. A file the copy lacks comes from the
      previous Jarvis copy (`OLD`), and old copies go only once the new one holds every `CORE` file (index.html, jarvis.css,
      data.js). The page swaps a stylesheet still pending after 5 s for a `media=print` one (`#jcss`), so it always draws.
  - **Start guard + watchdog (index.html, 2026-11-01):** `jarvis.unfinished` counts a start until Jarvis has run 4 s or the
    owner leaves it. The start after an unfinished one has no 3D core; if the unfinished one had the 3D core mounted
    (`jarvis.core3d`), `jarvis.no3d` keeps 3D off until the owner picks a level under ⋯ → 3D. A classic-script watchdog sees
    a main module that never ran (`window.__jarvisRun`): reload, then drop `jarvis-*` caches and reload, then a note with the
    reason (`data.js: HTTP …`, the first error) and Reload / Repair. Optional modules retry once (`?retry=1`).
    WebKit check: Playwright WebKit (`PLAYWRIGHT_BROWSERS_PATH=<dir> python -m playwright install webkit` + `install-deps
    webkit`), iPhone 13 profile, persistent profile for worker updates.
    - Zenith le-public-v50: the saved copy on 404 / slow / offline; data from the copy for 30 s after a cached page.
    - kalshi-k9.
  - **Tests:** test_jarvis_hub (198), test_jarvis_brain (139), test_jarvis_system (24), test_jarvis_core (58), test_jarvis_apps (84),
    test_zenith_mode (70), test_kalshi_page (185), test_phone_e2e (local https end to end: modes, slow / offline / 404, worker
    updates, one frame, real taps, nothing white).
- **Jarvis smart + connected (2026-11-02 night, owner: "I want the Jarvis perfect again ... connected to my Obsidian"):**
  - **Priority engine** (`brain.js ranked()`): "what should I do" / "brief me" / "status" / the proactive line rank by money
    at risk: MFFU 7-day inactivity (quiet_days 5 = before day 7, 6 = today, 7 = may be closed), PC silent / bot stopped /
    feed stale, red verdicts, near floor, PC health lines with the one fix, the Planner, Kalshi; sales ideas only on "deals".
    data.js `systemStatus().todo` uses the same order (`todos` lists them all).
  - **Intents**: eval pace, why no trade, next setup, last trade, P&L today / week / month, MFFU rules (data.js
    `MFFU_RULES`, a copy of research/lit/mffu_rules.json, checked by test_jarvis_brain), what the bots learned (live.json
    `pc.mind` / `pc.learn`), how's my PC (the fix first).
  - **Smart mode**: 8 s timeout, offline = the local answer at once; the model gets the ranked priorities, quiet days, PC
    health, next window, MFFU rules, plus Obsidian snippets and Me.md. Free key steps (Groq, else Gemini) in ⋯ → AI key.
  - **Obsidian** (`obsidian.js`, `memory.js`, `assist-ui.js`, owner steps in `docs/JARVIS_OBSIDIAN.md`): a private GitHub repo
    synced by the Obsidian Git plugin; token only in localStorage `jarvis.vault`, only to api.github.com; index in IndexedDB;
    confirmed append-only writes to `OLYMPUS/Inbox|Jarvis|Logs`; `graphSnapshot()` / `onIndexChange()` for the Mind page.
  - Kalshi 404 = "NOT LINKED" (grey), asked once per page load. Planner: read from its own sync (`planner.sync`) when set up on
    this phone, else one grey "open the Planner once" line.
  - Tests: test_jarvis_brain (165), test_jarvis_system (36), test_jarvis_obsidian (46).
- **Zenith shell (2026-11-03 day, owner: "way higher quality, 3D UI effects", "organized ... like a maid swept"; the map
  table is in `docs/ZENITH_COMPARISON.md` "The map"):**
  - Files: `tools/web_public/zenithcore.js` = `web_next/js/next/zenithcore.js` (byte-identical classic script,
    `window.ZenithFX`), phone glue `zenith.js` + `zenith.css` (loaded last: after pro.js / polish.css). Read-only UI.
  - Where am I: one header on every page, breadcrumb TAB › SECTION over the title; a hero that only repeated the title
    keeps its description (`.zn-hdup`); bot main pages are titled by their chip ("ZLARIOR › TODAY / Overview"); Holodeck /
    Live View (old "chart" group) sit under Home with Home lit (display only, routes unchanged).
  - Money first: Home's greeting carries one glass panel, Today · This month · Eval P&L in real $ over the 3D energy
    ribbon (accounts' `days` from the live board + today's live $); each bot's Today has its own ribbon with real $ and
    $ a month at that pace. Edge and Trades show $ per trade next to the average R.
  - Look: one glass card (gradient, 1 px rim, top edge light, no per-card blur or drop shadow: scroll frames), one
    spacing scale `--zn-s1..s6` (4-32 px), one dashed empty state, a shared glint (edge light following the finger /
    mouse) + up to 4° tilt (`ZenithFX.glass`, one overlay, nothing per frame unless touched), numbers that count to their
    new value on live redraws, an invisible 44 px hit area on every compact control.
  - Motion: View Transitions between pages (`#page` named `zn-page`, header / tabs / sub-bar pinned), CSS slide as the
    fallback; `.main { overflow-x: clip }` ended the 28 px sideways scroll of the old slide.
  - Quality: `jfx` (Jarvis / OLYMPUS key; Settings > 3D effects > 3D quality writes it): off = still, low = no tilt or glow
    pass; reduced motion and Zenith's own 3D effects Off (default under automation) = nothing moves (`ZenithFX.use3d`).
    The ribbons share one loop: <= 30 fps, none while scrolling, off screen or hidden.
  - Themes: `ZenithFX.applyTokens()` is the one token writer (PC `skins.js` accent goes through it); `ZenithFX.olympus()`
    maps an Olympus theme (id, colour object or JSON in `localStorage['olympus.theme']`, `Olympus.onTheme`, the storage
    event) onto it; an unknown id clears back to Zenith's own look. Worker le-public-v52, PC le-shell-next-v32.
  - Also fixed: "On this page" chips jump and light the card (a smooth scroll could stall short; test_ui_polish failed on
    the base). test_holo_ui's "replay advances" failed on the base and here while the shared machine was at load 40-60
    (4 cores) and passes 62/62 at a lower load: a timing flake, the Holodeck code is unchanged.
  - Test `python -X utf8 -m tests.test_zenith_shell` (23).
- **ARES + PLUTUS + FORUM + ARGUS quality pass (2026-11-04, overnight; same kit, `olympus/fx-atmos.js`):** every scene gets shafts / dust / embers / contact
  shadows (Ares: polished floor + torch embers; Plutus: studio environment, vault shadow, gold embers; Forum: sun shafts, torch embers, column shadows; Argus:
  scanner beam, data dust); the atmosphere joins 0.9 s after the first paint (cheap first frame; `?noatmos=1` on Ares is a perf probe). fx-atmos additive
  light now keeps the alpha channel (no dark halos on a transparent canvas). New money features, each from a pure core function (tests call them):
  Ares `aresplus.js` (`oddsPlan` what a win is worth in $ and R and the win rate it needs, `stopLadder` wide stop = fewer micros, `streakTable` "Drawdown left $X
  of $2,000 max loss" after each stop-out, `passPace`, `dayBudget`, `payoutCheck`); Plutus `plutusplus.js` (`rankPlans` best plan per $ of fees, `buyPlan` evals to
  buy for a funded account, `payoutRace`, `cashCushion`); Forum `forumplus.js` ("Money today": drawdown left, pace per session, size at four stop widths, the
  news rule; "The trading day" bar with a countdown; a recorded eval fills it when the site has none); Argus `argusplus.js` (Money tab: can the bot trade
  today = six gates + countdown to 02:00 ET, both evals in money words and the 7-day clock, what red lights cost; `?demo=1` / "See it with demo data" fills an
  empty page, never saved over the real copy; the tabs are a 2 x 2 grid). All taps >= 44 px (Forum's dots wrap to two rows above the arrows). Test
  `python -X utf8 -m tests.test_oly_job46`. The apps' tests wait up to 150 s for the page (`tests/olympus_money_kit.py`): SwiftShader on a loaded machine.
- **ARENA + DAPHNE quality pass (2026-11-04, overnight JOB 47; the Arena crowd cut belongs to agent a7eeb8e, not here):** `fx-atmos.js` `embers({ points })` takes several
  sources. Arena `dress.js`: sparks off the 14 braziers, added 0.9 s after the first paint, skipped on LITE, `?noatmos=1` probe. Arena Bosses tab gets the **Trading
  desk** (`arena/rhythm.js`, pure functions + textContent renderer; Arena never sees dollars, so it counts trades, days and rule breaks): the weekly rhythm of the main account
  against the 2-4 plan (8 bars, "need N more in M days" / "the plan is full"), the quiet clock (days left of the 7 without a trade, per account, `lapsed`), the discipline rate
  (30 days / all time / clean in a row) with the broken rules by name, and the money path (first trade, eval passed, first payout, days between). Daphne (`tree/`):
  `tree/gate.js` adds to the TOP 10 sheet a sort bar (rank, 2026 $/mo, test $/mo, trades a week, only holds) and a gate card per rule: the owner's four checks
  (holds out of sample, 2026 and test make money at bot size, 10+ trades in 2026) -> candidate / watch / reject, $ beside R at the bot's size (1R = `meta.bot_risk_usd`),
  how often (4 like it make 2 a week; 30 live trades take N months to prove), and the losing run ("4 stop-outs in a row = -$1,128: Drawdown left $872 of $2,000 max loss",
  the odds of it and of the 8 that end the account in the next 40 trades). The TOP RULES tab shows the verdict, $ a month with R and $ a trade with R. `tree3d.js`: pollen
  (dust) and a contact shadow at the trunk. Test `python -X utf8 -m tests.test_oly_job47`; run `tests.test_arena` and `tests.test_strategytree` too.
- **Money wording guard (2026-11-04):** `python -X utf8 -m tests.test_money_wording` scans every app's JS/HTML (comments and vendor code left out) for "day N of 10" / "session N of 10"
  eval counts, "room to the floor" on a line with no dollars, a progress bar / meter for eval days, and an R headline figure with no $ on the line. Mark a line that is right on
  purpose with `money-wording-ok` in a comment. Say it as "Drawdown left $X of $max loss".
- **FATES + LABYRINTH + HEPHAESTUS overhaul (2026-11-04, overnight JOB 4+5; owner: the apps look Play-Doh):** shared kit `tools/web_public/olympus/fx-atmos.js`
  (dust, embers, light shafts, contact shadows, polished floor, bronze, forged iron, thread glow; one draw call each, tiers in `QUALITY`; doc
  section in `docs/OLYMPUS_RENDER.md`). Fates (`fates-lab.js`, bottom bar **Lab**): fan chart with percentiles, pass odds by day, size what-if (1 / 1.25 /
  1.5 / 2x on the drawn futures), cut a thread (worst session removed, also for a tapped future), eval cost per pass (fee / pass rate), scenario table
  (Zlarior / ATLAS x 2026 / Jul-Oct / 2021-25); core functions in `fates-core.js` (`resize`, `cutWorst`, `fanChart`, `passTimeline`, `costPerPass`...).
  Labyrinth (`labcore.js`): maze picker (live / 50K / 25K at half size / 50K tight floor), risk-of-ruin gauge, best size in words + "Best size" button, Danger
  sheet + a red/green heat strip on the maze floor, "Walk it" (the runner walks its trail trade by trade; text only on LITE). Hephaestus
  (`hephaestuscore.js`): five recipes each picked from a STORED run by a rule (live / safe / aggressive / fast pass / sharp edge; live is honestly the safest and
  sharpest), pin A and compare with B, history of dials tried (localStorage, this phone), "Forge a report card" = a 1080 x 1350 PNG drawn on a canvas.
  Scenes: bevelled forged anvil / ingot / hammer, bronze hoops and walls, reflective floors, shafts + dust + embers, contact shadows; Fates stays <= 64
  draw calls (41 measured). Test `python -X utf8 -m tests.test_oly_job45` (69). Wiring needed (workers are off limits to the overnight agents): add
  `olympus/fx-atmos.js` to the Jarvis worker's asset list and to the apps' lists.
- **Zenith pages / every-tab visual pass (2026-11-04, overnight JOB 28; owner: "every dashboard page top quality, no blank-looking pages"):**
  `tools/web_public/zenpagescore.js` = `web_next/js/next/zenpagescore.js` (byte-identical, `window.ZenithPages`): a page with nothing to
  show yet gets one glass card "what you will see here" (the page's own description, four sample tiles, a sample equity curve with the
  drawdown floor / gradient bars / ghost rows / calendar, always marked "Sample, not your data", when it fills in, links to Home /
  Zlarior today / Money now), a loading page gets ghost cards, key figures roll up once per page (`ZenithFX.count`, nothing when motion
  is off). Glue: phone `zenith_pages.js` (loaded after zenith_money.js; sample card only after the page was quiet and thin for 1.3 s),
  PC `web_next/js/next/zenith_pages_pc.js`. Look: `zenith.css` (v6; end of file) = aurora drifting behind the glass (High / Ultra only),
  specular top edge on cards, gradient bars, ring icon on every empty state, press feel, hero chip text wraps (a countdown was cut), PC
  copy `web_next/css/zenith_pc.css` (same rules under `.nx .page`). Bridge (`bridge/index.html`) and `pc/index.html` got the glass /
  aurora / shine pass (content unchanged). goals.js: no more "goal undefined-undefined" / "Built 1/1/1970". Test `python -X utf8 -m
  tests.test_zenith_pages` (27). Wiring still needed (files that were off limits): bump the phone worker (`sw.js` le-public-v57+, add
  `zenpagescore.js`, `zenith_pages.js` to ASSETS) and the PC worker (`web_next/sw.js` le-shell-next-v33+, ASSETS `/css/zenith_pc.css?v=1`,
  `/js/next/zenpagescore.js?v=1`, `/js/next/zenith_pages_pc.js?v=1`).
- **Zenith Scorecard (2026-11-03, night quest "the best trading dashboard there is"; `docs/ZENITH_COMPARISON.md`):** one renderer
  `tools/web_public/procore.js` = `web_next/js/next/procore.js` (byte-identical, `window.ProUI`), phone glue `pro.js` (`#/pro/<part>`:
  Zlarior > Results first chip, More > Insight, a Home card under the quick tiles), PC glue `web_next/js/next/pro.js` (sidebar
  Insight, data `GET /api/next/lit_backtest?period=all`). Parts: Score (Zenith score 0-100 on six fixed-scale axes, expectancy
  $ / R, $ a month, SQN, recovery, streaks, R buckets with $, $ by weekday / hour / side / exit), Eval pace (real board: $ needed
  per session vs the bot's H2 $ per session), Risk (underwater vs the $1,000 DLL / $2,000 MLL, quick day-resample eval odds),
  Playbook (LIT rules + a graded card per level family), What if (0.25x-2x size), Tags (journal tags `le.jtags`, hub.js v9).
  Spans 2026 / H2 / H1 / 2021-25 / Real (closed NinjaTrader fills). Read-only, state in localStorage (`le.pro.span`,
  `le.pro.mult`). More > Today also links the sibling pages Data City (`datacity/`) and the Strategy Tree (`tree/`); Zenith's
  worker (le-public-v51) keeps out of both and of every OLYMPUS app folder (OTHER_APPS: jarvis/, planner/, kalshi/, datacity/,
  mind/, tree/, oracle/, odeon/, fates/, hermes/, prometheus/). Test `python -X utf8 -m tests.test_zenith_pro` (41).
- **Kalshi in Jarvis (2026-11-01):** the Kalshi bot runs 24/7 on its own Oracle Cloud server with real money, not on the PC.
  Its own Claude chat is "kalshi-server". The phone reads `kalshi.json` from its OWN public repo,
  `demetrades2000-coder/kalshi-feed` (main): raw first, then the API.
  - **Why its own repo:** a deploy key on nq-dashboard could rewrite the whole Pages site, so the key only gets write access
    to kalshi-feed.
  - **The server builds it:** `tools/kalshi_kit/public/kalshi_status_vm.py` (stdlib).
    - It reads only the bot's own files, read-only: trades.db `mode=ro`, account_truth, autotrader_status, autotune_state.
    - No Kalshi API calls (the bot already hits rate limits). Never `.env` or `keys/`, never the bot's modules.
    - Every published string is redacted.
    - It pushes every minute from cron (on change, plus every 3 min).
  - **Setup:** `<site>/kalshi/SETUP.md`. The site build copies `tools/kalshi_kit/public/` next to the page.
    - The script's SHA-256 is checked against the owner's paste line (`python tools/kalshi_kit/print_sha.py --live`).
    - The owner: one paste in the kalshi-server chat, create the empty public repo kalshi-feed, add the deploy key there.
    - This session's tools can't message that chat ("code from external"), so the owner pastes.
  - **Other routes:**
    - PC fallback: `python -m engine.kalshi_publish --ssh`, through the PC's own srv.py, resolved once by
      `install_windows.ps1`.
    - API mode: off by default.
  - **Contract v2:** adds `strategies` and `equity`.
  - **Contract v3 (2026-11-03, additive, optional):** `categories`, `buckets` (by price paid), `calibration` + `calib_basis`,
    `alerts`, `kelly`, `stats`, rows' `category` / `prob`. `read_bot()` fills them over EVERY settled buy (`breakdowns()`,
    `category_of()`; sell-backs out); `prob` (the bot's own chance) only the bot can add; `kelly` only from
    `KELLY_FRACTION` / `MAX_BET` / `MIN_EDGE` in its settings. Fields in `docs/KALSHI_PUBLISH.md` and the kit's SETUP.md.
  - **Risk guard (team K2, 2026-11-13, `docs/KALSHI_VM_UPDATE.md`):** `tools/kalshi_kit/public/kalshi_guard.py` (stdlib, no
    network, no keys) is the gate every bot order passes on the VM (`~/kalshi_jarvis/`, state in `guard/`): max $ per order /
    market / day, daily stop, max open, orders a day, close window (`late_ok_strategies`), price <= fair + x, fee-aware EV
    (0.07 P(1-P) rounded up per contract), kill switch file, fail closed, flock for the bot's 3 services. Modes paper (default) /
    dry_run (logs intended orders) / live (owner types `GO LIVE <ET day> STOP <stop>`; a limits change, a guard update, the kill
    switch or `--hours` drop it to paper). `guarded_send()` is the bot's one-line hook (`GUARD_SETUP.md` for the kalshi-server
    chat). The status feed adds `risk` (`clean_risk()`), alerts, the guard's mode; `kalshi_guard.py notify` (VM cron) pushes
    fills / losses / kill / stop / mode / unguarded orders to the owner's ntfy topic. PC: `tools/kalshi_kit/send_to_vm.py`
    (update over srv.py, limits, switches, `--live` with the typed phrase), `tools/kalshi_pc_link.py` (fetch ->
    `<olympus>/kalshi_feed/kalshi.json` + `data/pc_report/kalshi.json`, card line, PC alerts only when the VM sends none).
    Page: "Risk guard" card first in Today. Tests `tests.test_kalshi_guard`, `tests.test_kalshi_vm_update`, page `--only=risk`.
  - **Phone page:** `tools/web_public/kalshi/` with its own `sw.js` (kalshi-k12).
    - Its own dashboard: the Kalshi theme (`data-theme="kalshi"`, mint + cyan on #010a07 = its `theme-color`), K mark,
      ticker tape, aurora; never Jarvis's `jtheme`.
    - Sections: alerts, equity, open bets (UP/DOWN, live edge + EV, next settles), Edge & sizing (Kelly per bet + calculator),
      strategies, by market, by price, calibration, daily P&L, a P&L calendar, stats (all-time win / ROI), trades. A v1/v2
      feed works the breakdowns out from the trades list and says so.
    - The waiting card shows the one step, what lights up once connected, and a SAMPLE preview that is never saved.
    - Comparison with Kalshi / Polymarket / trackers: `docs/KALSHI_PLANNER_COMPARISON.md`.
  - **Tests:** test_kalshi_publish (113), test_kalshi_page (198). The build writes `<site>/kalshi/kit.json` (the script's
    SHA-256), which the page's paste line carries. Never turn on GitHub Pages for kalshi-feed.
- **Planner add-ons (2026-11-01):** the Planner lives on nq-dashboard `planner-backup`, built by its own session, and this repo
  can't push there.
  - **How they ship:** features are patches in `tools/planner_patches/`, applied by `scripts/add_planner.sh` at every publish.
    - In name order, 3-way when the base moved, each committed on its own.
    - A patch that no longer applies is skipped and logged.
    - Confined to `planner/` and no links; links in the copy are deleted.
    - `planner/addons.json` lists what was applied and skipped.
  - **10-projects:**
    - The bots, Kalshi and projects, live in the Planner.
    - Market hours, with optional bands.
    - `planner.today.v1` written for Jarvis.
    - Inside Jarvis its links switch apps through `parent.__jarvis.show()`; framed with no saved theme it uses the dark
      theme for the session; the Today line stays one folded line (todayorg passes with live data).
  - **20-power:** Now and next, Catch up (spreads overdue tasks, with Undo), smarter quick add, the weekly review reminder.
    Everything goes through the Planner's own `commit()`, via the `window.PlannerAPI` hook. Bot colors are hex-validated;
    synced/stored ids and colors are cleaned at every entry point (safe ids, stable replacement ids); only the Planner's
    own worker counts for the 'new version' bar.
  - **30-flow (2026-11-03, Sunsama / Motion / Todoist):** Workload (today's estimates vs free time, Trim to fit), Deadline
    risk (14-day earliest-date-first vs 60% of free time, Block the best gap), Daily goal (ring, 7 days, days in a row;
    device key `planner.flow.goal`). `ext-flow.js`, its own `planner/tests/flow.test.js` (41). Workload and Daily goal fold
    to Dashboards lines so todayorg's Today height limit holds.
  - **40-olympus (2026-11-03, owner "3D, futuristic, organized like a maid swept"):** `ext-olympus.js`, its own
    `planner/tests/olympus.test.js` (47).
    - Look: glass cards (translucent in dark; light keeps theme.test's exact colours, depth from shadows / background
      images), an aurora that glides once per view change, rise-in on a view change (not at start), mouse tilt, press-in,
      tick pop + short vibrate. No blur filters, no endless full-screen motion, no dialog fades: with them the Planner's own
      timing-sensitive tests (habits, journal, people deletes) failed under load. Small endless pulses only (status dot,
      NOW beam).
    - Today swept: one-line date, an even button row on phones (Focus first), hairline section labels, the status line
      with a green / red dot, a 12 px card gap on phones.
    - Day timeline fused into the status line (no header of its own): today's events in up to 3 lanes, a NOW beam, the
      "wide open" empty state. todayorg's busy phone Today: 4563 px (4560 without, limit 4571): keep it that small.
    - Focus mode (`#focus-mode`, palette, All tools, the header's Focus, a tap on the timer bar): a full-screen ring that
      drives the app's own focus timer (openFocus + its form, the bar's buttons), so logging is unchanged; a 5-min break
      in memory.
    - Switches: device `planner.olympus.fx`=off; Olympus `jfx` off = plain, low = still; prefers-reduced-motion = still.
      Olympus themes: `olympus.theme` = a theme id; tokens from `OLYMPUS_THEMES.tokens(id, 'page')` (the Jarvis frame's, or
      `../olympus/themes.js` loaded once): accent / accent2 / glow -> `--ox-a/--ox-b/--ox-glow`. No key, `olympus`, an
      unknown id or no themes.js = the Planner's own indigo / cyan.
  - **Test:** test_planner_addons (section f checks the real patches against the live branch and that each `ext-*.js` is
    loaded once).
  - **When the Planner session deploys again:** rebase or refresh the patches if test_planner_addons f reports a skip.
- **Market structure, playbook, discretion advisor (2026-10-29, read-only, never an order):** `engine/structure.py`
  (Tracker per timeframe on closed bars: fractal k=2 swings, HH/HL/LH/LL, BOS / CHoCH on a close, protected swing = origin
  of the breaking leg, pools = today's Asia / London / NY-open boxes + prior day + equal highs / lows (`lit.buildups`) +
  unbroken 1h swings, premium / discount of the 15m dealing range, displacement legs; `block()` = the Live View
  "structure" shape, cached per closed bar, ~13-20 ms a recompute here; `frame_events()` for research). Live View
  `liveview_api.view()["structure"]` (+ phone_view; thinking panel `structure` / `rule` / `advice` lines, ATLAS / BLITZ
  `structure_note`), narrator kind `structure` (15m / 1h breaks, advice on an open Zlarior trade; not pushed by default;
  read from the block the page / live_publish thread computed, so the poll thread never recomputes: derive +0 ms).
  `docs/PLAYBOOK.md` + `engine/playbook.py` (rules Z1-Z18, A1-A8, B1-B8 + structure advice Z-S / A-S / B-S; `now()` = the
  rule being applied, `applying()`, one check function per rule; `GET /api/next/playbook` on the Live View router). `engine/advisor.py`: six rules (be_choch, exit_choch,
  trail_15m, trail_5m, tp_pool, skip_htf) scored on every finished trade by the difference method; PC via `narrator.tick`
  (a key check on the poll, the scoring in a background thread; `logs/advisor/<strategy>.jsonl`, `tally.json`,
  gitignored), cloud via `live_learning.cloud_hook` (state "advisor");
  cards in `live_learning.suggestions` (live tally + the 2026 backtest cards `research/lit/advisor_backtest.json`; no approve command). Its backtest = the research (`tools/structure_manage.py
  advisor`). Tests `tests.test_structure`, `tests.test_advisor`.
- **Mind (2026-10-29, owner: "a brain that's very smart, can think for itself"; read-only, never a rule / size / order):**
  `engine/mind.py`, write-up `research/writeups/mind.md`. (1) Memory: every historical setup per bot in
  `research/mind/store.json` (Zlarior 631 = run lit_live settings, ATLAS 1,129 = run atlas_funded_live, BLITZ 330 =
  na_best_trades) with live-computable features (`Hist` on 5m bars: time since 18:00, killzone, VIX, 15m / 1h structure
  trend vs the trade, prior-day range ratio, day position, ATR ratio; LIT depth / displacement / inducements / stop ATR / R to
  the band / level family; ATLAS member; BLITZ first-hour ratio) + live / paper trades as they close
  (`logs/mind/<bot>_live.jsonl`); k nearest -> `similar[bot]`. Calibration `research/mind/calibration.json` (fit 2026 H1,
  check H2 + 2021-25): NOT predictive for any bot -> `valid: false`, conf "low", "context only" (fit 2021-25 -> 2026:
  ATLAS separates 2026, p 0.03 both halves, but fit 2021-24 -> 2025 shows nothing: not confirmed). (2) Regime per 5m bar + trend-day odds from 10:30 ET (logistic, fit H1:
  AUC 0.66 H2 / 0.63 2021-25). (3) Game plans 01:45 ET (Zlarior, ATLAS) / 10:45 ET (BLITZ), sizes from `brain._sizing`,
  journal `logs/mind/plans.jsonl`. (4) Reviews of each closed trade (grade, luck / skill), `logs/mind/reviews.jsonl`
  (trades closed > 2 days ago are skipped). (5) Nightly research child after 16:05 ET (`python -m engine.mind research`,
  nice 15, <= 10 min; observations -> size / skip rules -> H1 pick / H2 check / 2021-25, eval speed for LIT) ->
  `logs/mind/proposals.json` (seed `research/mind/proposals_seed.json`: 22 tested, 0 candidates). Wiring: `narrator.tick`
  -> `mind.pc_tick` (key check; compute in a thread once per 5m bar, started 15-45 s into a minute, ~50 ms; `LE_MIND=0` off, `LE_MIND_RESEARCH=0` no
  nightly), `liveview_api.view()["mind"]` (cached block), phone_view + heartbeat "mind" + holo "mind" = `mind.compact`
  (< 12 KB), `GET /api/next/mind` (block + history + calibration), narrator kind `brain` (not pushed by default). Contract
  checker `mind.contract_errors`, sample `tests/fixtures/mind_sample.json` (`python tools/mind_build.py sample`). Rebuild
  memory + calibration + seed: `python -X utf8 tools/mind_build.py` (~10 s). Tests `tests.test_mind`.
- **Dashboard 2026-10-28 (owner: "50 useful features", "what the bot is thinking", "very 3D"):** registry
  `web_next/FEATURES.md` (status of all 50). Home "Today · real accounts" (`realcore.js`, `cc.js`; phone
  `tools/web_public/realcore.js`): one card per REAL account (ledger + NinjaTrader fills only, never paper $), gauges, health
  score, ledger check (`engine/live_board.py` flags an eval day booking $ with no real trade). Real results page (`real.js`,
  `#/real`, CSV export). AI Insights (`insight.js`, `engine/insight_api.py` `GET /api/next/insight[?day&hm]`, features 21-30).
  Live View (`liveview*.js`, `engine/liveview_api.py` `GET /api/next/liveview?tf=1m|5m`): full-screen chart, per-strategy
  colour layers (Zlarior blue, ATLAS orange, BLITZ purple), "what the bot is thinking" panel, feed.
  **Holodeck (2026-10-29, the main feature: "see exactly chart fills, very high quality and 3D, what every bot is thinking"):**
  scene `tools/web_public/fx/src/holo.js` in fx.js (`FX.holo(el, opts)`, own loop, works with the space background off;
  instanced candles + wicks + volume, Max = mirrored floor + bloom, Lite = neither, DPR cap 2 PC / 1.5 phone, sleeps off screen):
  every fill an orb at its exact second / price (real solid, paper / model hollow, the model price as a ghost), trades as glass
  risk / reward volumes with the stepping stop, the LIT setup anatomy (1 Sweep -> 2 Inducement -> 3 Displacement -> 4 CISD ->
  5 Entry), thought panels, working orders, levels, structure; camera Flat / 3D / Fly, replay 1x-120x. Page UI `holocore.js` +
  `holo.css` (byte-identical copies in `web_next/js/next/` and `web_next/css/`, copied + hash-stamped by fx/build.mjs). PC
  `web_next/js/next/holo.js` (Main after Live View, `GET /api/next/holo[?day=]` every 5 s on today, `/api/next/holo/days`,
  a "3D" button on Live View); phone `tools/web_public/holo.js` (`#/holo`, Home button under Live View, Mission Control link,
  More > Today; `holo.json` + `holo_hist.json` from branch `live`, API first, raw fallback). No WebGL 2 / quality 2D: the Live
  View chart with the fills. Data contract (v 1, kind le-holo) + the API: `engine/holo_api.py`. Test: `python -X utf8 -m
  tests.test_holo_ui` (fixture `tests/fixtures/holo_fe_sample.json` from `tests/make_holo_fe_fixture.py`, real bars + research
  trades, mocked real fills 1 tick off the model; `LE_SHOTS=<dir>` saves the screenshots).
  **Phone Live View (2026-10-28, `tools/web_public/liveview.js`, `#/liveview`, Home button under the plan line, More > Today):**
  the same page on the phone. The PC pushes `liveview.json` (`liveview_api.phone_view`: 1m bars of the last 8 h + the 5m
  session as `bars5`, the three layers, thinking, feed 60; < 240 KB) in the same orphan commit as live.json on branch `live`
  (`live_publish.push(extra=)`, `Publisher.extra`). Phone reads it via the GitHub API (raw fallback, shares `LIVE.apiUntil`),
  every 30-60 s while open; live.js waits ~3 min on that page. `liveviewchart.js` / `liveview.css` byte-identical copies;
  full screen = Fullscreen API, else the root moves to `<body>` with `lv-max` (iPhone); sideways = chart-only bar.
  Banner when the PC has not sent for 20 min. Sw `le-public-v42`. Test `tests.test_phone_liveview` (37, Playwright). Narrator
  (`engine/narrator.py`, hooked in `LiveBot._alerts_tick`, real bot only, never raises): plain-language feed,
  `logs/narrator/<day>.jsonl`; phone pushes only for armed / entry / exit / refused (`data/narrator.json`, `LE_NARRATOR_PUSH=0`).
  Tests: test_real_ui, test_insight_api, test_liveview_api, test_narrator.
- **Holodeck data (2026-10-29, owner: "see exactly chart fills, very high quality and 3D, where I can see what every bot is
  thinking"; read-only):** `engine/holo_api.py` builds one JSON per trading day (contract `kind: "le-holo"`, v 1: `bars` 1m/5m
  `[t,o,h,l,c,v]`, `bots` (Zlarior `#4f9bff`, ATLAS `#ff9a3d`, BLITZ `#b388ff`), `fills`, `trades` (stop_path, model, setup),
  `orders`, `thoughts`, `levels`, `structure`, `now`, `errors`). `GET /api/next/holo?day=` (no day = today) and
  `/api/next/holo/days` (last 30 days with trades, real $ / model $). Real fills first: the NinjaTrader adapters' legs (LIT
  `bot.adapter`, account B ATLAS, account C BLITZ; `fill_px` + `fill_mtime` = NinjaTrader's order-state file time, adds),
  `logs/exec_audit/{legs.json,orders.jsonl,ledger.jsonl}` (stop / target fill prices + times, past days), the B / C state files;
  a refused entry is an order REJECTED, never a fill (`ninjatrader.entry_never_placed`). Model: the LIT backtest of the day
  (`lit_live.run` + `brain.build`, cached per day by its bars, ~0.35 s cold, ~6 ms warm) gives model_px / slip_ticks (+ = worse),
  the setup timeline (`t_sweep`, `t_idm`, `t_disp`, `t_cisd`, `cisd`, swept levels) and the levels; today uses the Bot Brain and
  replays only when a new setup / closed trade appears (`_live_model`, <= every 5 min). A day without real fills shows the model
  trades as `real: false, src: "model"`; ATLAS (`bot.second`) / BLITZ (`bot.blitz` ledgers) paper trades are `src: "paper"`.
  Thoughts = narrator file + Brain log + order events, time-ordered, with a price anchor. Phone: `Publisher.extra()` ships
  `holo.json` (today, <= 300 KB, 1m bars trimmed to the trade windows ±30 min first; reuses the minute's phone_view) and
  `holo_hist.json` (last 10 trading days' trades with fills / thoughts / a ±45 min 1m window, <= 400 KB; cached 10 min or until
  a ledger changes, at most 1 rebuild a minute) in the live commit; `Publisher.extra_ms` / `--status` show the ms (here: holo
  ~15 ms warm, hist ~3.4 s cold / ~65 ms warm; the three extras ~30 ms a minute). Sample day for the 3D page: `tests/fixtures/holo_sample.json` (2026-10-13 from
  real data, fake Sim fills 1 tick off; rebuild `python -X utf8 tools/holo_fixture.py`). Test `tests.test_holo_api` (52).
- **Deep space + Mission Control (2026-10-29, owner: "make it look cooler ... almost like 3D space"; read-only):** the default
  look of both dashboards. 3D: `tools/web_public/fx/src/space.js` (in fx.js; `FX.init({ level, bg: 'space' | 'galaxy' })`):
  Earth (continents / clouds / city lights baked once from noise into textures, then texture reads + lighting), the Moon
  crossing the Sun (a real sphere over the corona; glare + lens ghosts dim with the cover) and its soft shadow sliding over
  the lit side (city lights come on inside it), analytic atmosphere rim, 3-layer parallax stars + baked Milky Way, one
  satellite per bot (`FX.bots({ lit, atlas, scalp: 'trade' | 'armed' | 'idle' | 'off' })`), a shooting star per newly closed
  trade (`FX.shoot('win' | 'loss')`), the aurora / rim tint from today's real P&L (`FX.pnl(usd)`), warp streaks on a page
  change, `FX.stats()`. Cost: DPR cap 1.5 phone / 2 PC, phones <= 30 fps, everything 30 fps after 20 s idle, nothing while
  hidden or under a full-screen view (Live View), reduced motion = one still frame, software GPU = small bakes, a phone below
  17 fps drops to ~16 fps; no backdrop blur over it on phones; name tags ride next to the satellites (`FX.labels(on)`). 3D is ON by
  default again (one-time reset of a stored Off: `clean.fx2` phone, `nx.fx2` PC); automated browsers (`navigator.webdriver`)
  start Off unless the URL says `?fx=max|lite`. Off / no WebGL 2 = the static CSS sky (`space.css`, painted at first load).
  Harness: `fx/space.html?lit=trade&atlas=armed&pnl=300&eclipse=0&fxfixed`. Mission Control: shared renderer
  `missioncore.js` (window.MissionUI, byte-identical copies like boardcore.js; `mission.css`, `space.css` too, copied by the fx
  build) reads only the live board (+ Live View data for BLITZ's line, the news); renders every account-shaped board block
  generically (lit, atlas, a third one such as `blitz` / `scalp` or `board.accounts`; a BLITZ placeholder "paper / not live
  yet" otherwise). Phone `mission.js` (Home strip on top + `#/mission`, More > Today); PC `js/next/mission.js` (Main >
  Mission Control after Home; `initMissionSync()` drives the satellites / stars / aurora every 15 s). Features 51-67 in
  `web_next/FEATURES.md` (stop-out now, why no trade yet, session timeline, alerts center, health constellation, eval runway,
  streaks & consistency, daily loss & week pace, next news). Live View draws `view()["structure"]` when present (zone, pools,
  swings, BOS / CHoCH, protected; a Structure switch + a "Market structure" thinking card). Caches le-public-v43 /
  le-shell-next-v25. Test `python -X utf8 -m tests.test_space_ui [--shots <dir>]` (static, node render, phone + PC Playwright).
- **BLITZ tab, Mind, Trader's deck (2026-10-29 night, owner: "make a separate tab at the bottom ... improve dashboard
  features"; read-only, links only):** shared renderers, byte-identical in `tools/web_public/` and `web_next/js/next/`:
  `blitzcore.js` (window.BlitzUI: `model(src)` -> `page(M, part, opts)`, parts today / brain / trades / results / rules /
  golive; `acctC` off / Sim test / armed / paused / funded), `mindcore.js` (window.MindUI: draws the Mind block, nothing when
  it is absent: `bot`, `home`, `page`, `reviewFor`), `deckcore.js` (window.DeckUI: risk meter, next 24 h with the DST notice,
  eval odds from today's balance (random walk at the H2 pace, labelled an estimate), real P&L calendar, journal, notification
  center with a per-bot mute in localStorage `le.deck.mute`, "since you last looked" `le.deck.seen`, Holodeck replay links).
  Phone: `blitz.js` (loaded last, after holo.js): **six tabs Home · Zlarior · ATLAS · BLITZ · Money · More** (clean.js BZ_SEGS,
  `#/blitz/<part>`), `#/mind` and `#/deck` (the old aliases mind -> brain, deck -> holo are dropped), Home cards before "One
  tap away", Mind cards on the Zlarior Bot Brain / ATLAS > Brain / BLITZ > Brain, Mission Control replay links; `#/holo/<day>`
  opens that day (holo.js `H.want`; its hash re-stamped in index.html). Data: data.json `blitz` (= `engine/blitz.card` of the
  cloud state + the PC heartbeat's block, `tools/build_web_dashboard.py`), live.json `pc.account_c`, liveview.json
  `strategies.scalp` (+ `mind`), the board. PC: `js/next/blitz.js` (pages `blitz` (Main after ATLAS, part in `nx.bzPart`,
  shell.js), `mind`, `deck` (after Real results), slots re-placed after cc / brain / second / mission redraws), `GET
  /api/next/blitz` in server.py (`blitz.card(BOT.blitz)` + `acct_c.hb_block()`), `/api/next/mind` when the Mind agent ships
  it, Holodeck links via `nx.holoDay` (js/next/holo.js). Features 71-80 in `web_next/FEATURES.md`. Caches le-public-v45 /
  le-shell-next-v27. Test `python -X utf8 -m tests.test_blitz_tab [--shots <dir>]` (static, node render, phone 390x844,
  PC 1440x900; renders the Mind agent's `tests/fixtures/mind_sample.json` (PC) and `mind_sample_compact.json` (phone cut); `LE_MIND_FIXTURE=<path>` another one).
- **Night 3: one calm product (2026-10-30, owner: "more very useful features ... clean it up, organized ... the UI, quality,
  the effects ... I wanna be shocked"; read-only, links only).** Shared renderer `statuscore.js` (window.StatusUI,
  byte-identical `tools/web_public/` = `web_next/js/next/`, copied by the fx build; on MissionUI's accounts): `items` /
  `summary` / `bar` (the status bar: PC bot, NinjaTrader, feed, each bot, next window, alerts; a quiet PC is amber until
  30 min before a window, then red), `sunday` (Fri 00:00 -> Sun 20:00 ET, from Thu 18:00 on a clock-change weekend: CME
  reopens Sun 18:00 ET, the clock change, each bot's first step via `DeckUI.events24` from the reopen, readiness list),
  `oneLine` (each bot's day), `accounts` / `acctCard` (eval ring: progress to the target, or the max-loss share in red;
  $ to the target, room, eval day, today's real $, sparkline of `days`, REAL / SIM / PAPER tag from the board's `badge`),
  `week` (this week's real trades vs each bot's goal, Mon-Fri dots, from the board's `progress`), `empty(kind)`. Phone `polish.js` + `polish.css` (loaded last after blitz.js; `blitz.js` exports `window.PhoneData`,
  `real.js` exports `RealPages.core/board/opts`): Home = `.pl-home` (greeting + ET clock, status bar, the three cards,
  "What matters now" (+ the deck's "since you last looked" digest in one row), this week, Sunday card, quick tiles; with no
  board yet clean.js's hero cards take the account-card slot) + `.pl-fold` "Everything else on Home" (CSS `order` + hide, `le.pl.homeAll`; every older card
  stays in the DOM), bot tabs open on the same card (`.pl-bot`), `<html data-page data-bot>` colour roles, the search
  palette (`#plFind`, "/" / Ctrl+K, `le.pl.recent`), Money tab = `real` · `realtoday` (new page: RealUI.today + safety) ·
  `evaltl` (money / props / whatif / scale / accounts moved to More > Money planning), entrances / count-ups (first paint
  only; rings / sparklines draw in once via `.pl-first`), the sliding tab pill (`.pl-tabind`, the tab's colour), More's
  "Recent" chips (`le.pl.visits`), "On this page" chips on pages of 3+ screens (`.pl-toc`, one per card's first h3,
  rebuilt when a page redraws itself; not on Home / More / Live View / Holodeck), Settings > Intro (`le.intro`),
  the CSS sky's parallax + a vignette. ONE page transition on the phone
  (`#page.page` pl-page / pl-page-l / pl-page-r by `#page[data-dir]`, set in polish.js's render wrapper from the tab order)
  wins over clean.js's cl-in, space.css's sp-warp (a full-page blur + transform held for 1 s by `.entering`: it cost
  frames and mis-placed the Holodeck's fixed labels) and index.html's 3D card rise. Page animations have NO fill-mode on purpose: a
  finished transform animation that stays "in effect" makes `.page` the containing block of fixed full-screen views
  (it broke the Holodeck fill labels on the phone). A bot page that redraws itself later (BLITZ) gets its card back
  (MutationObserver on #page). `clean.js` (still ?v=3): Today · Brain ·
  Trades · Results · Rules on all three bots (ZL / AT / BZ_SEGS), More sections Today · Insight · Bot and health · Trades ·
  Money planning · This app. index.html: the splash is now the once-a-day intro (`le.intro.day`, skippable, `?intro=1`
  forces, never under reduced motion / Motion off / webdriver); `#spLine` = `POLISH.introLine()`. Fixed: the Safety card
  piled up on every live redraw (real.js `.rc-moved`). PC `js/next/polish.js` (`initPolish()` in app.js): `#nxStatusHome`
  on top of `#page-cc` (bar + Sunday card, MutationObserver keeps it first), sidebar `MAIN_SECTIONS` in routes.js (Bots ·
  Live · Money · Insight; shell.js `mainLinks`), BOTS = the same five sections, `css/polish.css`. fx: Earth bake 1536 on a
  Retina phone at Max, crisper star points. Features 82-109 + "Organization (2026-10-30)" in `web_next/FEATURES.md`. Caches
  le-public-v46 / le-shell-next-v28. Test `python -X utf8 -m tests.test_ui_polish [--shots <dir>]` (static, node, phone
  390x844 every tab + palette + intro + reduced motion + frame time + light, PC 1440x900 + Ctrl K).
  StatusUI's classes are `su-*` / `data-su-*` (NOT `st-`: the PC Start page owns `.st-go`, `.st-acct`, `.st-list` ...; the
  first version broke its START button). Phone header: one status dot `#plStat` (the bar's verdict; a tap opens it on
  Home); the critical-alert banner (#apBan) counts for 3 min after a page redraw wipes it. PC Ctrl K: each bot's five
  sections + "Status: ..." (`addPaletteItems`). test_holo_ui's "fill label shows the exact price" steps (phone + PC) read
  the label a fixed 1.6 s after the camera fly starts; the software GPU runs ~4 fps right after the Holodeck opens (base and
  this branch alike), so the label was sometimes still just off screen (PC failed on the base commit too).
  `tests/holo_ui_check.js` now also waits until the label shows (max 8 s). Still flaky there and on base: PC "fills pop
  exactly when they happened" (the replay at ~10 fps ends before a fill) and once the PC day picker. No looping animation
  runs on the Holodeck / Live View pages (polish.css; the header / tab lights stay lit but still), no card entrance there.
- **Start & Accounts page (2026-10-26, PC dashboard sidebar "Start", page `start`):** START BOT as one checklist, one button
  per red line: NinjaTrader connected · live bars from NinjaTrader (`go.feed_problem`, fix "right-click the MNQ 5-minute chart > Reload NinjaScript (or re-add LE_BarFeed)"; the Sim job is refused while stale) · accounts set (50K -> Zlarior, 25K -> ATLAS) · setup done · Sim tests passed · armed ·
  running and routes verified, plus the plain line `Zlarior -> 50K <name> · ATLAS -> 25K <name> · both armed · running`.
  Same code as the console: `engine/go.py` is split into `step_prep` / `step_nt` / `step_sims` / `step_arm` (+ `arm_problem`,
  `slot_problem`, `mixup`, `verify_routes`); `run()` calls them for START_BOT.bat, the page calls them through
  `engine/start_api.py` (`/api/next/start/*`, mounted by next_api). Sim test and arm run as a detached job
  (`python -m engine.go --step sims|arm`, `logs/start_job.json` + `.log`) because they stop / start the server the page runs
  on; the page polls and reconnects. A failed Sim test is retried with `--write-mode direct` (saved as `write_mode` in `data/start_bot.json`, then passed to every `--start` / `--enable-auto-resume`, console and page alike). Arm: the owner types `I ACCEPT LIVE RISK` in the page (checked by the endpoint, the
  job's `step_arm` and `ninjatrader --start`); the phrase reaches the job in env `LE_START_CONFIRM`, never argv or the log.
  Accounts panel (`go.accounts` / `add_account` / `remove_account` / `set_anchor` / `to_funded`): balance (NinjaTrader
  accounts.csv, else the MFFU anchor, else the plan start), floor, bot, eval / funded, armed; add (name, Builder 50K / 25K,
  Zlarior or ATLAS, start day: first 50K = Zlarior's main in `data/start_bot.json`, ATLAS = account B via
  `account_b.set_account_b`, others = extra Zlarior accounts in `data/accounts.json`, disarmed, allowlisted), change balance /
  floor / as of (`eval_life.set_anchor`), passed -> funded (`eval_life.to_funded`), remove (off the allowlist when unused).
  START BOT's mix-up checks on every write; one account is never both Zlarior's and ATLAS's (`go.role_of`); adds / removes
  / names refused while the bot runs. Pick list of names from `broker_balance.read()` rows + `outgoing\*_<acct>_Position.txt`.
  **Local only:** every POST is in `cloud_guard.CLOUD_BLOCKED` (`START_WRITES`) and checked by `cloud_guard.local_only`
  (client 127.0.0.1 / ::1, no proxy / tunnel header, Host and Origin localhost, not LE_CLOUD): the phone sees the page
  read-only. UI `web_next/js/next/start.js` + `css/start.css` (sw `le-shell-next-v20`). Tests `python -X utf8 -m
  tests.test_start_api` (88 checks, temp files only; phone / Tailscale / tunnel / rebind / origin / cloud refused) +
  `tests.test_go`. Shots `research/handoff/2026-10-26/ui_start/`. Untested on the real PC: the detached job window
  (`cmd /c start`), the server restart during the job, opening NinjaTrader from the page.
  **One button "Start trading" (2026-10-26 PM, owner: "automatic through the dashboard ONLY"):** `POST /api/next/start/go`
  -> job `python -m engine.go --step auto` (`go.step_auto`): update if behind (`go.update` = `autoupdate.pull`; then the
  server restarts and the job re-runs itself `--after-update`), the ATLAS block migration, names (the only owner input,
  once), setup, NinjaTrader opened + its log-in waited for (re-checked every 10 s), live bars waited for (every 15 s, the
  exact chart click shown), the Sim test once (market open), then the start. **No phrase** when `go.resume_problem` is None
  (the auto-resume opt-in is valid for exactly the 50K, the live switch on, the 25K armed): the job asks the server
  (`POST /api/next/start/resume` -> `go.resume_now`), which starts through the auto-resume gate (`autoresume.decide`:
  NINJATRADER_LIVE=1 in the server, no kill / daily loss today, NinjaTrader CONNECTED) with Bot Control's start (autostart
  record saved) and checks the routes (stops the bot when wrong). Otherwise status `need_phrase` shows the phrase box
  (any capitals) and the job runs `step_arm`. Every stop is one plain sentence in the job file (`stage`, `say`, `need`
  names / phrase / market / stop, `retry_s`); the page retries a `retry_s` stop by itself while open (30 tries max, never for
  names / phrase). PC clock row (`status.clock`, `guards.clock_probe` in a thread, every 10 min) + "Sync the clock"
  (`POST /api/next/start/clock` -> `go.sync_clock`: `w32tm /resync`; refused -> the Windows Settings steps; then the bot's
  clock guard probes again). The dashboard opens on Start when the bot is not running (`app.js`, `/api/health/ping`
  bot_running). Tests `tests.test_start_api` (117); shots `python -X utf8 -m tests.shots_start --pc <url>` ->
  `research/handoff/2026-10-26/ui_start_auto/` (sw `le-shell-next-v21`).
  **At PC boot (2026-10-26):** Startup folder (`go.startup_shortcuts`): NinjaTrader + "LE bot server" -> START_DASHBOARD.bat
  (starts run_bot.ps1 when the server is down, waits up to 5 min, opens `/?page=start`); the server's autostart resumes the
  bot through the opt-in (`autoresume.resume_live`, waits 30 min for NinjaTrader CONNECTED; after that "Start trading"
  resumes it without the phrase). NinjaTrader connects by itself only with Connections > Configure > "Connect on startup".
  Desktop: two icons, **LE START** (START_DASHBOARD.bat = the Start page) and **LE STOP BOT**; make_shortcuts.ps1 deletes
  the older LE START BOT / LE UPDATE / LE DASHBOARD / LE HEALTH CHECK (the .bat files stay). The server runs
  `go.ensure_shortcuts` at start (Windows, once per `SHORTCUTS_V`, mark `data/shortcuts.json`), so an update brings the new
  icons and Startup shortcuts without a click. Tests: test_win_scripts (pwsh sandbox: 2 icons, old ones removed),
  test_ops, test_go.
- **Live board (2026-10-26, read-only, both dashboards):** `engine/live_board.py` `build(inp)` turns heartbeat-shaped blocks
  (health, brain, second, acct, crit, live_pub) + accounts / goals / odds into: **Right now** per account (balance, room to
  the floor, $ to go, today, session X of 10, what it waits for = brain stage / each ATLAS member's state, the next entry
  windows as absolute ET times (`next_windows`: weekends, CME full closures, early close = halt - 15 min, EMA no Monday),
  Zlarior's size now from `brain.sizing`, ATLAS's last `account_b.size` else the rule in words, every guard blocking
  entries with a one-line fix: clock / feed / NinjaTrader / startup / kill / stopped / silent / eval / account B), **today's
  map** (brain levels + VIX objective up / down + 18:00 open, points and $ per micro and $ at the size now), **health strip**
  (poll_ms amber above 5 s, last poll, feed 1m / 5m, NinjaTrader, clock drift (red when the guard blocks), last error
  (red only when recent), heartbeat, phone feed), **week and eval** (goals week vs 2-4 / 3-4, session bar 10 / 15, 2-week
  odds from `uprisk_eval.json` at the live switches and `research/second/atlas.json` eval25k, $ a month expected = health
  band H2 usd_eval_per_session x 21 / ATLAS H2 per_month vs the actual pace) and a **trade log** of both accounts (PC
  trades, account-B entry + exit paired and filled from the member's paper trade, paper rows marked). Sources: PC `GET
  /api/next/board` (`engine/board_api.py`, mounted by next_api, cached 4 s, from the running bot via the heartbeat
  helpers); data.json / home.json `board` (`site_block`, build_web_dashboard); live.json `board` (`live_publish.build`,
  every 60 s, ~15 KB, its trades trimmed first by `fit`). UI: shared `boardcore.js` (window.BoardUI, byte-identical in
  `tools/web_public/` and `web_next/js/next/`); PC page `board` ("Live board", Advanced > Accounts; Main stays 6 items) +
  the Command center "Right now" row (`cc.js` `#ccBoard` -> `board.js` fillBoardHome); phone `board.js` (after clean.js:
  wraps Home with the Right now cut, page `#/board`, prefers live.json's newer board), sw `le-public-v37`. Pictures via
  TradePics (bot pictures + exact-match backtest examples), CSV export. Tests `python -X utf8 -m tests.test_live_board`
  (71 checks, incl. a node render); shots `python -X utf8 -m tests.shots_board --fresh --site <built site> --out
  research/handoff/2026-10-26/ui_live` (restores the files the server refreshes).
- **PC paper bot + dashboard:** `server.py` on http://localhost:8766, supervised by `scripts/run_bot.ps1` (Windows; runs only while
  the PC is on). The UI is the ES-module SPA in `web_next/` layered over `web/`, with the API in `engine/dash_*.py` and
  `engine/next_api.py`.
  **Command center (2026-10-25, read-only):** home page `cc` (both accounts LIT 50K / ATLAS 25K, 9 health lights: feed,
  NinjaTrader, clock, STARTUP RECONCILED, allowlist, one-bot lock, heartbeat, kill, loop; what the bot waits for; early
  close / DST / news) plus Goals (reads `/api/next/goals`, falls back when it 404s), Eval timeline, Session calendar,
  Trade log, ATLAS per setup, Runbook, Audit evidence, All features (61 new features). API `engine/pc_cc_api.py`
  (`/api/next/cc/*`, GET only), UI `web_next/js/next/cc.js` + `css/cc.css`, grouped sidebar `routes.js` GROUPS.
  Tests `python -X utf8 -m tests.test_pc_command_center`; shots `tests/shots_pc_cc.py` -> `research/handoff/2026-10-25/ui_pc/`.
  **"Zlarior" (owner 2026-10-25 PM): the display name of the LIT bot only** (like ATLAS for "second"): every key, file,
  config, push kind and route id stays `lit`; "LIT" stays where it names the method ("Zlarior trades the LIT method").
  Phone (`tools/web_public/clean.js` v2): tabs Home · Zlarior · ATLAS · (BLITZ, 2026-10-29) · Money · More; the Zlarior tab (group `lit`, page
  `#/lit`) has sections Today (+ 50K eval, Plan, Levels chips) · Brain · Trades · Results · Rules (ZL_SEGS; since 2026-10-30 the same five on all three bots), the ATLAS tab
  Today · Brain · Trades · Results · Rules = the one ATLAS page cut into parts (`#/atlas/<part>`, atlasTag). PC
  (`routes.js` BOTS): sidebar Home · Zlarior · ATLAS · Results · All tools; `zlarior` is a virtual entry that opens its last
  section page (`zlSub`), the ATLAS part sits in `nx.atPart` (shell.js / second.js). Old links (#/trades, #/brain, #/second)
  still open. Push titles say "Zlarior setup armed" (kind `armed` unchanged). Shots `research/handoff/2026-10-25/ui_zlarior/`.
- **PC-off:** the GitHub Actions cloud monitor runs every 15 min on market days. It is the same engine and settings as
  `live_model.json`, keeps a paper ledger plus an MFFU eval tracker, sends phone push notifications (`engine/push.py`, `docs/NOTIFICATIONS.md`: entries, outcomes, PC silent; Telegram/Discord off
  unless `LE_ALERTS_CHAT=1`), runs the fast-entry watcher (`tools/lit_watch.py`) and the LIT day brief (`engine/lit_brief.py`), and publishes README.md and
  chart.png to the `dashboard` branch (read in the GitHub app).
- **NinjaTrader 8 route (2026-10-17, untested on a real install):** `engine/ninjatrader.py` writes Order Instruction Files into
  NinjaTrader's `incoming` folder (bracket entry, breakeven, flatten, kill) and reads fills/positions from `outgoing`;
  `ninjatrader/LE_BarFeed.cs` writes MNQ 5m bars to `le_feed\*.csv` (`data_source: "ninjatrader"`; stale -> FEED STALE,
  entries blocked; Yahoo only with `"no_yahoo": false`). Sim accounts by default; a real account needs armed + the LIVE phrase + `NINJATRADER_LIVE=1`. Self-test:
  `python -m engine.ninjatrader --selftest` (55 checks, incl. cancel-pending entries, partial exit fills and the CME early-close flat (5 min before the halt; entries stop 15 min before) added 2026-10-18; `LE_BarFeed.cs` also writes `le_feed\MNQ_1m.csv` for LIT, not yet compiled on a real install). Setup for a non-coder: `ninjatrader/SETUP.md`. Known gap: the
  Tradovate adapter never received breakeven moves or non-TIME exits (the NinjaTrader flags `route_all_exits`,
  `route_stop_moves` fix it; apply the same to Tradovate before ever using it).
- **S1 robustness pass (2026-11-15, `engine/ninjatrader.py`, self-test 78):** (1) a bracket file NinjaTrader took but
  never reported (no stop report 30 s after the bracket while the entry's report is there, `nt_bracket_report_s`) ->
  alert + CLOSEPOSITION + blind CANCEL of the bracket ids (never re-placed under new ids; skipped after an NT restart);
  (2) write-ahead: the legs are saved before the entry file goes out (a crash in between restores the leg, its fill gets
  the stop / target); (3) `_protect` never sends stop / target ids NinjaTrader already reports (crash after the bracket
  file); (4) hard cap `nt_max_entries_day` 8 entry files per account per trading day (persisted), independent of the
  bot's guards.
- **No-chart mode: the LE_Feed add-on (2026-11-02, `ninjatrader/LE_Feed.cs`, NOT yet compiled on a real install):** a
  NinjaScript AddOn (`Custom\AddOns`) that writes LE_BarFeed's exact files with no chart (BarsRequest 5m 30 days + 1m 21
  days on "CME US Index Futures ETH", closed bars only, same trim / temp-swap; MarketData for `<ROOT>_1m_open.csv`;
  `<ROOT>_instrument.txt`; `accounts.csv`). Self-heal: price connection up + CME open + no new closed 1m bar for 3 min ->
  dispose and re-request (max once / 2 min / instrument); a ConnectionStatusUpdate back to Connected re-requests all.
  Logs `le_feed\le_feed_log.txt`, status `le_feed\le_feed_status.txt` once a minute
  (`time,source=addon,instruments=A;B,last_1m=..,resubs=N,connected=1`). Instruments from `le_feed\feed_instruments.txt`,
  written by the bot (`ninjatrader.sync_feed_instruments` from `LiveBot._feed_addon_tick`, real bot only, once a minute,
  only on change: the micro it orders via `nt_instrument()` roll / pinned `nt_instrument`, + NQ with signal_root NQ).
  No double writer: `LE_FeedHub` (static, in LE_Feed.cs) names the covered roots; LE_BarFeed finds it by reflection
  (compiles and behaves as before without LE_Feed.cs) and writes nothing for a covered root, nor accounts.csv. Health
  `feed_addon` / `--status` "Bar source": "bars from LE_Feed (no chart), N re-subscribes". Selftest checks 13b (74 total).
  Checked here only by compiling both .cs files with mono `mcs -langversion:5` against stub NT8 types. Unverified NT8
  API points are listed at the top of LE_Feed.cs. Owner steps: SETUP.md "No-chart mode".
  **2026-11-03 QA (`docs/QA_2026-11-03.md`):** starts from whichever comes first of State.Active, `OnWindowCreated` (the
  Control Center: called for every add-on, also right after F5) and a 10 s timer from State.Configure; on start it writes
  `le_feed_status.txt` at once (+ `started=<unix>`) and prints "LE_Feed: started ..." in the NinjaScript Output window
  (`NinjaTrader.Code.Output.Process`). `le_feed_owner.txt` holds the running copy's token: an older copy (pre-F5 assembly)
  stops itself. Stale re-requests back off 2/4/8/16/30 min without a live bar (holidays). Stubs + driver in
  `tests/nt_stub/`, run by `tests/test_le_feed_cs.py` (skips without mono).
- **Is NinjaTrader connected? (`ninjatrader.connection_view`, 2026-11-03):** the ATI writes `outgoing\<conn>.txt` only on a
  state change, so 11-02 showed only `Simulation=CONNECTED` while MFFU fed prices. Connected = a CONNECTED file, or a fresh
  non-Sim row in `le_feed\accounts.csv`, or live bars (1m closed <= 4 min ago / LE_Feed `connected=1`). Used by the
  heartbeat `nt` block (`connected_via`, `live_accounts` count, `note`; names never published), `nt_log.outgoing`, ops
  check, botctl/pcops rows, autoresume; the "every connection DISCONNECTED" entry refusal (`_all_disconnected`) is skipped
  only when the bot's own non-Sim account is live in accounts.csv. Test: `tests/test_nt_connection_view.py`.
- **MNQ feed vs NQ backtest + the NQ signal chart (2026-10-26, `research/writeups/mnq-vs-nq-feed.md`, OFF by default):**
  the PC's MNQ bars, collected from the heartbeat branch's history (`tools/hb_bars.py`: the branch is one force-pushed
  commit, older ones fetched by SHA from GitHub's activity API -> `research/feed/nt_mnq_{5m,1m}.csv.gz`; 5m from 09-17,
  1m from 10-18 = no 1m overlap with NQ_1m.csv) vs NQ1! (`tools/mnq_vs_nq.py`, `research/feed/mnq_vs_nq.json`):
  NinjaTrader MNQ = TradingView MNQ1! on 95.4% of bars (A1's sample is the live feed); MNQ vs NQ within 1 tick on
  54-62%, 1 pt on 92-94%; LIT setups 36% on one feed only (40 sessions Aug 24 - Oct 16), trade days 60% differ, 5m-exec
  net NQ +$2,362 vs MNQ +$367; whole-2026 MNQ-noise study (40 draws, 1m exec): 2026 median $32.8k vs $43.8k, H2 $9.1k vs
  $9.9k (-$229/mo), only ~28% of trades identical; vendor-noise control: no change. Runs `lit_feed_mnq_noise`,
  `lit_feed_mnq_live_5m`, `lit_feed_nq_same_5m`. **Switch `signal_root`** (top level of live_model.json +
  live_model_lit.json, "MNQ"; `LE_SIGNAL_ROOT` / start cfg `nt_feed_roots` override): "NQ" = `NinjaTraderBars` reads an
  NQ chart's LE_BarFeed files (NQ_5m / NQ_1m / NQ_1m_open / NQ_instrument; LE_BarFeed names files by the chart's root, so
  no clash and nothing to untick) for every decision, orders / stops / targets / size stay MNQ. One root per symbol
  (`root_for`: never NQ 5m with MNQ 1m); no NQ file -> MNQ as before; a stale NQ chart blocks (no silent switch). The
  roll guard, `--status`, HEALTH CHECK feed lines, the heartbeat bars follow that chart. Archive caveat: data/nt_bars
  keeps its MNQ bars from before a switch (no shift, ~1 tick; gone from the LIT window within ~2 months). Owner steps:
  SETUP.md 4c. Test `python -X utf8 -m tests.test_signal_root` (22).
- **December roll safety (2026-10-26, `engine/roll_watch.py`, `tests/test_dec_roll.py` 23, `docs/ROLL_DEC_2026.md`):**
  the roll guard (`ninjatrader.contract_problem`, chart month vs order month, root-free) already refused entries
  (`tests.test_nt_roll_guard`); now the chart vs order contract is also: a launch-checklist line `roll` (red after the
  roll day while the chart is old, good when equal or switched the evening before, info a week before / unknown), the
  Start page's "Live bars from NinjaTrader" line (`go.feed_problem` -> "Contract roll: ..." with its own fix), pushes
  (7 days / 1 day before: `ops_checks.roll_notice` keys; "Chart still on MNQ 12-26: no new entries" once a trading day:
  `ops_checks.roll_late_notice` at 01:40 ET, and the cloud monitor `roll_watch.cloud_notices` when the PC's ops tick is
  older than 1 h). The test simulates the roll with a constant 301.25-pt offset (TradingView export + archive old, chart
  switched Wed 17:00): on every session after the switch the LIT window = the adjusted series bar for bar and LIT's
  signals / trades are identical (MNQ and NQ charts). 2026-10-29 (test D, 29 checks): every account (Zlarior, ATLAS, an
  account C) builds its NinjaTraderAdapter from `live.ADAPTERS`, so each carries the guard; an order contract pinned in a
  config (`nt_instrument` / `nt_instrument_mini`) is refused once it is past its roll (`_contract_mismatch`), even with
  the chart left on the same old contract.
- **ROLL.bat (2026-11-13, team S1; `tools/roll_now.py`, `tests/test_roll_now.py` 42):** the owner's one double-click for the roll.
  Acts only from the eve after 15:56 ET (or any day after the roll) and only flat (no non-flat MNQ / NQ position file in
  NinjaTrader's outgoing\, no trade in a fresh heartbeat); removes an OLD pinned `nt_instrument` from `data/autostart.json`
  (backup `autostart.json.before-roll-*`), fixes `le_feed\feed_instruments.txt` in add-on mode when the bot did not, else
  shows the chart click and waits (15 min) until `<ROOT>_instrument.txt` shows the new month, then `roll_check`. Never an
  order, never the order contract rule. Phone pushes without GitHub: `roll_watch.countdown` (daily from 3 days before:
  Mon Dec 7 - Wed Dec 9, "ready", the late alarm from 01:40 ET, "done") through `tools/pc_guard.py`, called from
  `pc_report.events` (not on the reporter's first run; keys `guard:*` in `data/pc_report/state.json`, a failed push retried).
  The ops_checks Web Push reminders (7 days / 1 day) still exist but need GitHub's push subscriptions.
- **Eval guard pushes (2026-11-13, team S1; `tools/pc_guard.py`, `tests/test_pc_guard.py` 39):** in the same 15-min PC report
  (ntfy alert topic), from the board cards of `engine/live_board` (fresh heartbeat <= 15 min only): drawdown 50% / 75% used
  (1 - room / mll, once per level per `eval_start`, re-armed 10 points back, 0 -> 80% is one push), daily loss near (70% of
  `dll`, realized + the open trade's unrealized, once a trading day), quiet bot (`quiet_days` >= 5, high at 6 on a real
  eval: MFFU's 7-day rule), the day summary 16:05-16:59 ET on CME trading days (`cme_calendar.full_closure` skipped; says
  "last report old" with its age). Quiet hours 23:00-07:00 ET for default-priority pushes. Read-only: no order, no setting.
- **Second backup (2026-11-13, team S1; `tools/second_backup.py`, `BACKUP_SETUP.bat`, `scripts/backup_task.ps1`,
  `tests/test_second_backup.py` 42, `docs/DISASTER_RECOVERY.md` "Second backup"):** setup asks the mirror URL + token
  (getpass) + synced folder -> `%USERPROFILE%\.olympus\backup.json` (600); refuses a public repo (Codeberg / GitLab API).
  Weekly (Sunday 11:37, StartWhenAvailable): snapshot of the working files into `refs/heads/pc-snapshot` with a temporary
  index (copy of the real one; skips new files > 25 MB or secret-looking names; .gitignore respected) because the PC is
  updated by zip and its HEAD lags; `make_backup.py --ref <snapshot>` into the synced folder (newest 4 kept); `git push
  +refs/heads/* +refs/tags/*` with the token only in GIT_CONFIG_* env (Authorization header, credential.helper off); one
  ntfy push via `pc_report.load_cfg`.
- **DST / CME holidays / self-healing (2026-10-29, `docs/AUTOPILOT.md`):** US clocks go back Sun 2026-11-01; every live
  time decision is America/New_York wall clock (25 trading_day functions, market_open, entry / flat windows, auto-update,
  ops pushes, the cloud's UTC crons through its real bash guard, LIT replays over the 2025-11-02 / 2025-03-09 /
  2026-03-08 weeks identical to the backtest: `tests/test_dst.py` 49, `--quick` 45). **Sunday 2026-11-01 run end to end**
  (`tests/test_dst_sunday.py`, 29 checks, ~4 min, `--quick` 15): BLITZ on 2026 bars re-dated 3 weeks with their NY wall
  times kept (Nov 2-6 EST = Oct 12-16 EDT trade for trade, live Engine = backtest across the switch, Monday's day filter =
  Friday's range); the timers minute by minute Sat 17:00 -> Mon 16:30 (the 01:00 hour walked twice: trading day flips once
  at Sun 18:00 EST, market opens once at 23:00 UTC, auto-update hourly once per ET hour and once in the doubled hour, ops /
  live-learning weekly once, Monday's LIT 02:00 / ATLAS 03:00 / BLITZ 11:00 checks / 15:55 flat on the right UTC instants);
  the real server.py on the virtual clock Sun 00:00 EDT -> 20:00 EST with LIT / ATLAS / BLITZ on Sim (polls every step
  incl. 120 in the doubled hour, no "clock moved backwards", no order, heartbeat on the virtual clock, market open + fresh
  bars after 18:00, saved day 2026-11-02, BLITZ eval session 1, the go-live check names Monday's normal session, the board
  Monday's 02:00 window, no push / auto-update check twice in the doubled hour). The JS fallback for browsers without
  Intl time zones (`litkit.js`, `tradechart.js`, both copies) uses the US rule (`usEtOff`), not a fixed -4 h. Known
  fixed offsets left on purpose: the old engine's 4h buckets (`engine/data.resample`, `engine/mtf.build_4h`, shadow
  only, identical in the backtest). **One CME calendar** `engine/cme_calendar.py` (`early_close`, `full_closure`,
  `halted`, `entry_cut` / `flat_cut` / `flat_ts`; `lit_live.early_close` and `guards.full_closure` delegate, same values;
  Christmas on a Saturday = Fri 12-24 closed); checked against every short session and missing weekday of
  data/NQ_5m.csv 2021-2026 (`tests/test_holidays.py` 15; Good Fridays without a jobs report are closed but kept as a
  09:15 close). `live` / `ops_checks` / `go.market_open` know the holidays (no FEED STALE / gap alarms after an early
  halt or on Christmas); account B and the second strategies flat 5 min before an early close (as the adapter); the
  adapter and the extra accounts refuse entries on a full closure; `cme_calendar.route_limits(day, flat_mod)` for BLITZ's router (the
  paper engine unchanged and import-isolated). Self-healing (`tests/test_selfheal.py` 12): every engine state save goes through
  `fsutil.replace`; `AccountB.void_refused_days` (like the 50K's eval_fix, once per process); **50K eval recount
  (2026-10-30)**: `LiveBot.eval_days()` keeps an earlier day's restored total (it re-added the ledger's earlier-day exits at
  every restart after the roll: 2026-10-28's real -$437 stop-out became -$1,311, room $232 instead of ~$1,106);
  `_repair_recounted_days` on restore sets a day booked as an exact 2x / 3x ... multiple of its own exits back to them
  (one push "eval balance fixed"); a per-trade void after the roll also comes off the restored day; `fill_audit` counts
  a NOT OK ("fill not reported yet") entry whose bracket filled at the broker as a trade (`tests/test_eval_recount.py` 12); narrator feeds
  gzipped after 3 days, deleted after 120 (`ops_checks.rotate_feed`); weekend DISCONNECTED -> entries resume on
  reconnect; **Actions minutes** `engine/actions_budget.py` (state.json "actions", budget.json on the dashboard branch;
  saver at 85% of 2,000: the guard keeps the night check + one run an hour; only on a GitHub runner). **New MFFU Names**
  `engine/new_accounts.py` (ops tick push once per Name; Start page line `newAcctLine` / `wireNewAcct`; POST
  `/api/next/start/newacct` PC only: a funded account after the slot's pass via `go.to_funded`, else a new eval via
  `go.set_names`; BLITZ via `ROLE_SETTERS["blitz"]`; never arms; `tests/test_new_accounts.py` 12). **Autopilot score**
  `engine/autopilot.py` (Start page writes + hands-off events, 100 - 10 a step, heartbeat `remote.autopilot`;
  `tests/test_autopilot.py` 7). Checked (heartbeat 2026-10-28): NinjaTrader's outgoing folder shows one connection,
  `Simulation=CONNECTED`, and its trace puts both MFFU accounts on that connection ("(Simulation)
  Cbi.Account.OnConnectionStatus: account='MFFUEVBLDR602936016' ..."), so the DISCONNECTED checks do watch the MFFU
  accounts' connection.
- **Execution audit (2026-10-25, `research/handoff/2026-10-25/A5_execution.md`, test `tests/test_nt_exec_audit.py`):** kill is
  account-scoped (CLOSEPOSITION + CANCEL by id) unless the action carries `"scope": "global"` (only `LiveBot.kill_switch`,
  the owner's kill -> FLATTENEVERYTHING); the OIF writer refuses FLATTENEVERYTHING / CANCELALLORDERS outside that, a line
  for another account and a CANCEL/CHANGE of a non-`LE` id. A real account also needs the account allowlist
  (`--allow-account`, `data/nt_accounts_allow.json` or `NINJATRADER_ALLOW`). One process per account (`le_locks\<acct>.lock`
  in the NinjaTrader folder, released by `LiveBot.stop`). Startup DISARMED for entries until `guards.startup_problems`
  passes once (guard 0 `startup_reconcile`). Unreadable `ninjatrader_state.json` -> `.corrupt-*`, entries blocked until
  the account is flat (orphan bot orders from the audit log cancelled) or `--confirm-reset`. Order files are published
  with no overwrite (`_publish`); stale `le_outbox` files are deleted at start. Runbook: `.../STARTUP_AND_RECOVERY_RUNBOOK.md`.
- **LITE mode (2026-11-03, `engine/lite.py`, `tests/test_lite.py`):** switch `data/lite.json` {"on": true, "hist_days": 100}
  (gitignored, written by `BOT_LITE.bat` / `python -m engine.lite on|off`) or env `LE_LITE=1` (`LE_LITE=0` forces off); read once
  at server start (server.py `# ---- LITE MODE ----`). Off: Bot Brain, Trade pictures, paper second strategies / ATLAS + BLITZ
  shadows (no bg_worker child), AI watch, Mind (LE_MIND=0, LE_MIND_RESEARCH=0), exec audit (LE_EXEC_AUDIT=0), dashboard prewarm
  (LE_PREWARM=0); env set by the owner wins. Kept: LIT + routing, guards, account B/C/fleet, routed second route, setup-armed
  pushes, narrator, heartbeat (bars for the cloud), live feed, autoupdate, PC watcher. History read cut to 100 days (floor 75; LIT's
  window_start reaches <= 69 days). engine/live.py untouched (instance wrappers like poll_timing). Measured here (server import +
  36 polls on data/ with add-ons on, incl. children): **full peak 687 MB -> LITE 180 MB**. Replay test: full vs LITE LiveBot on
  2026-10-13..15, identical ledger / state / routing log. `BOT_LITE.bat`: lite.json on, starts NinjaTrader if closed, starts the
  server or restarts it via /api/next/botctl/restart (refused when not flat), pc_keeper -Bot once, NinjaTrader memory checklist.
  PC-off answer (Azure for Students costs, free tiers, mini PC, MFFU VPS question): `docs/PC_OFF_PLAN.md`.
- **PC off, free:** `scripts/PC_OFF_OPTIONS.md` (A: TradingView brain + one tap on the phone; B: the PC wakes itself at 07:50 ET,
  trades through NinjaTrader, hibernates at 16:35: `scripts/schedule_pc.ps1`; E: a spare Surface on 24/7: `scripts/setup_dedicated_pc.ps1`;
  paid bridges / VPS only as options C-D). The always-on PC pushes a heartbeat (`engine/heartbeat.py`, branch `heartbeat`,
  on with `LE_HEARTBEAT=1`); the cloud monitor alerts when it goes silent in a session.
- **Heartbeat push made robust (2026-10-26, `tests/test_heartbeat.py` 36 checks, temp bare repos):** the Surface went
  silent 22:38 -> 05:20 ET on 2026-10-25/26 (GitHub activity API of the branch). Cause found: the PC was offline / asleep,
  not the push code: NinjaTrader's own 1m bars (pushed `bars_1m.csv.gz`) have the same hole 22:42 -> 05:17, the only one
  inside a session in 40 days, and the thread resumed on its 5-min rhythm (05:20:08, 05:25:15); live.json stopped too at
  05:27. The 50-min gap 21:13 -> 22:04 the same evening has bars, so the push itself may have hung there. Latent bugs fixed
  anyway: on Windows `subprocess.run(timeout=)` waits forever for the pipes after killing git when git-remote-https / the
  credential manager hang (reproduced in the test) -> `heartbeat.run_cmd` (temp files, process tree killed); no prompts
  (`GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=never`); the commit is built and pushed from the private scratch dir
  `data/heartbeat_pub.git` (gitignored, like live.json's), so the project's shallow / OneDrive / locked `.git` is never
  written (and ~1,000 loose objects a day no longer pile up in it); `--force-with-lease` on the last pushed commit
  (scratch ref `refs/hb/last`), refused or failed -> `git ls-remote` tip, one retry; only `heartbeat` (`_BRANCH_RE`, main
  is refused); any exception stays inside the beat; watchdog thread (60 s) restarts a dead push thread or a beat hung
  > 10 min (new lock; the hung one exits quietly), notices a frozen process (PC asleep) and pushes at once; after a
  failure the next try in 60 s. `health.hb` (heartbeat + live.json) and `/api/health/ping` "heartbeat.health": last push,
  last error (redacted), fails in a row, restarts, last frozen stretch, console line "[heartbeat] the PC was asleep ...".
  Keep the Surface awake: plugged in, Sleep "Never", lid "Do nothing" (HEALTH CHECK's "Power / sleep" line).
- **Goals + phone features (2026-10-25, read-only):** `engine/goals.py` `build(data)` (pure: data.json blocks accounts / live /
  second / scale / perf -> per account eval progress vs target / floor / 10 sessions, week trades vs 2-4 LIT and 3-4 ATLAS,
  month $ vs the health_band H2 band, ATLAS scorecard 0/20, payout, scale step, news / early-close / clock calendar, plain
  `lines`). data.json + home.json `goals` (build_web_dashboard), PC `/api/next/goals` (`next_api.goals_data` from the bot).
  Phone: `goals.js` (Home Goals card under the Surface line + Today's plan card, `#/goals`), `features.js` (More hub in six
  sections + search, `#/features` 142 features with NEW badges, `#/weekcal`, `#/last10`, `#/lights`, `#/evaltl`,
  `#/atstats`, offline badge, haptics, scroll-to-top); sw.js v30. Tests `tests/test_goals.py`; screenshots
  `python -X utf8 -m tests.shots_goals --site <site>` (research/handoff/2026-10-25/ui_phone). New feature -> add a `feat(...)` line.
- **Road to $10K / Stingray 3LT (2026-10-26, read-only to trading, `engine/money_goal.py`, `tests/test_money_goal.py`):** the
  owner's money goals, part `money` of goals.build. Card: next action (payout ready > passed eval to switch > buy the next
  runnable evals in plan order, 2 at a time, with the price + code > wait), the stack = 9 planned slots (MFFU Builder 50K x1
  Zlarior, MFFU Builder 25K x2 ATLAS (the bot runs ATLAS on one 25K: slot 2 noted), LucidPro 50K x4, FundedNext Rapid Daily
  50K x2) with states not bought / eval / passed / funded / paying from goals._lit_account, data.json accounts (extras /
  funded, `funded.payouts`), account B, then business.json via the scale block (`scale_plan.status` rows now carry `start`);
  $ a month once funded = `research/second/money_goal_rates.json` (H2 2026, to you, live funded sizing: 50K $915, 25K ATLAS
  $517, LucidPro $938, FundedNext $629 = $6,959 for all 9; 2021-25 ref $404), rebuilt by `tools/money_goal_rates.py` from
  uprisk_wincap / atlas_funded / funded_combo t15_be_off (test checks the file = the sources). Then **"My goals" at the
  bottom**: $10K month by Feb 2027 (bar jobs / Kalshi / prop payouts to you this month, + the plan line), 2024 Stingray 3LT
  before he turns 19 (2027-02-22: target $38,000 = 40% of ~$78K + $7K cushion, stretch marker $46,000, days left, $ a week
  needed, on pace / behind by $X at the current pace = the savings slope since the $20,000 start of 2026-10-26, needs two
  balances 7+ days apart), C8 Z06 bar ($60,000, no date). Owner figures: gitignored `data/goals_money.json` (savings
  history, month jobs / Kalshi, every target / date / name editable, `publish`), written only by the PC Goals page form
  (`engine/money_api.py` GET/POST `/api/next/money`, POST in `cloud_guard.MONEY_WRITES` / CLOUD_BLOCKED + `local_only`).
  Heartbeat `money` (heartbeat_block; publish off = targets only) -> cloud state pc.money -> data.json / home.json
  goals.money; live.json `money` (`money_goal.from_heartbeat`, ~7 KB, dropped first by `fit`). UI `moneycore.js` (MoneyUI,
  byte-identical phone / PC): phone goals.js v3 (#/goals bottom; the old Goals card on Full overview), PC `money.js` from
  cc.js Goals (form only when local); sw le-public-v39. The public dashboard site shows the figures only while publish is on (default OFF since 2026-10-26: the site is public; the owner switches it on in the PC form).
  Shots research/handoff/2026-10-26/ui_money_goal/.
- **Phone live feed (2026-10-21, `engine/live_publish.py`, `tools/web_public/live.js`, `tests/test_live_publish.py`):** the PC
  force-pushes one `live.json` (verdict, PC account / eval / position, feed ages, health, check-in time) to branch `live` of the
  PUBLIC Pages repo `nq-dashboard` every 60 s while the bot runs (5 min otherwise; orphan commit, scratch git dir
  `data/live_pub.git`, never main = no Pages build). The phone polls it every 30-60 s via api.github.com (raw fallback) and lays
  it over data.json. No extra Actions minutes. Auto-update also checks hourly outside trading time (weekdays 16:00-01:20 ET,
  weekends) when flat, nothing armed and a restart is safe (`engine/autoupdate.py` mode `hourly`).
- **Poll speed diagnostics (2026-10-26, `engine/poll_timing.py`, read-only):** the Surface polled in ~32,300 ms every poll
  (heartbeat 2026-10-25) against ~0.8 s here. server.py installs a stage timer (LE_POLL_TIMING=0 = off) that wraps
  LiveBot's stage methods and the few module functions poll_once calls, so `engine/live.py` stays byte-identical (the PC's
  hand-patched copy must keep fast-forwarding). Each poll -> `bot.health["poll_stages"]` (total / CPU / waiting, every
  stage in order with nested "a > b", other threads' CPU during the poll via psutil) -> heartbeat `health.poll.stages`
  (`accounts.poll_stages_block`) -> Home "Bot loop" light (`pc_cc_api.poll_line`) and the Start page's Bot loop card.
  Findings here: the 20,000-row MNQ_1m.csv parse is 56 ms (`engine="python"`; the C engine gives the same frame in 41 ms:
  not the cause, left alone); a busy background thread slows a poll ~1.5x (GIL), not 30x; NinjaTrader's `outgoing`
  holds one file per order and `connections()` opened every one of them twice a poll per adapter (604 reads with 300 orders;
  every open on the PC passes OneDrive's sync filter) -> now read only when size / time changed (`_CONN_SEEN`, shared by
  every adapter: 2 reads a poll). The constant ~32 s (= ~2 s of work + one 30 s wait?) is still unproven: the first
  heartbeat with `health.poll.stages` names the stage (wall >> CPU = waiting on disk / network / a lock). Tests
  `tests.test_poll_timing` (15; `--full` also replays test_lit_live's LiveBot with and without the timer).
- **Poll speed fix (2026-10-26, `engine/bg_worker.py`, `tests/test_poll_speed.py`):** measured cause = the GIL: the paper
  work the bot ran in threads after routing (second.run ~0.8 s + ATLAS v2 `pc_step` ~2.4 s a minute, pictures ~0.5 s each,
  here) overlapped the next poll; its LIT part (poll start -> routed, new `health.lit_ms`, heartbeat `health.poll.lit_ms`,
  Bot loop line) went 0.57 s -> 2.5 s median / 5 s p90 (1 core: 1.4 / 3.5 s), lit_live.run wall 0.49 -> 3.6 s at the
  same CPU. Now: (1) that work runs in ONE child process `python -m engine.bg_worker` at BELOW_NORMAL priority (nice 10):
  jobs "second" (second.run + stop-hunt candidates + `atlas_v2.pc_step`) and "charts" (`PcCharts.draw`), length-prefixed
  pickles on stdin / stdout, bars sent as deltas (`frame_packet`: exact prefix check, last 2,000 rows; the 5-year history
  goes once), args pickled at submit, one job per kind (busy = skip), results set `bot.second` / `bot.atlas_v2` /
  `_charts_drawn` from a receiver thread; pictures only sent when `trade_chart.pending` (keep only for a stale LIT
  picture). Dies / hangs (600 s) -> callback error + restart (20 s gap); 3 deaths in a row or `LE_BG_WORKER=0` -> the old
  threads. Child watches the parent pid, imports no adapter module. Account B and the routed second strategies stay in
  the loop (they route); B's `second.run` no longer waits on second.py's `_LOCK` held by the paper thread. (2) news / VIX
  downloads (15-30 s timeouts, every 15-30 min, before routing) -> `news.background_refresh(True)` (real bot only: stale
  copy served, one refresh thread; the archive is rewritten only when changed so `historical_events` keeps its parse).
  (3) the ES learning merge (5-year frame, every 5 min, before routing) -> refreshed after the state save. (4)
  `data._tag` one strftime per day, not per bar (12x, identical): lit_live.run 0.46 -> 0.32 s. (5) dashboard: board /
  goals 250 -> 20 ms (`second.backtest` memo 300 s, `hub_data.business_raw` cached by file stats). Result here (4 cores,
  back-to-back polls): LIT path 0.41 s off / 0.40-0.53 s on (was 2.5 s); 1 core 0.43 s (was 1.37 s). Identity: test_lit_live
  120/120 + bot 2/2, account_b --quick 45/45, worker == threads (orders, second run, ATLAS v2 state, PNG bytes). Next win
  (not done, feed code owned elsewhere): `lit_live.feed_1m` iterates all 10k 5m groups in pandas (~130 ms a poll).
- **Updates never blocked by the PC's own files (2026-10-26):** ATLAS's account (the account_b block) lives in the
  gitignored `data/account_b.json`; `second_model.json` ships `"account_b": null` and is never written for it
  (`account_b.raw_cfg`: local first, else the tracked block; `set_account_b` / `arm_b` / launch prep / the Start page write
  the local file). `account_b.migrate_local` moves an older version's block out of the tracked file (local written and read
  back first, then `git checkout HEAD -- second_model.json`); run at server start, START BOT, and before every update's
  dirty check. Every update path is `autoupdate.fast_forward` (auto-update, phone "update", UPDATE.bat and START BOT via
  `python -m engine.autoupdate --pull`, the Start page): bot-made files and files checked out from main by hand
  (`from_main`: their blob came in with HEAD..main) go back to HEAD first, a shallow history is deepened (`is_ancestor`:
  `--deepen=300`, then `--unshallow`; the Surface said "refusing to merge unrelated histories" 2026-10-25), a refused
  `merge --ff-only` to a proven descendant is `reset --keep`; a rollback puts hand-checked-out files back. Any other local
  edit still blocks. A server older than the checkout (`go.server_stale`, `/api/next/start/boot`) is restarted before the
  bot starts. Tests `tests.test_account_b_local` (migration + same ATLAS / LIT routes), `tests.test_autorun` (the Surface case
  on real temp repos).
- **PC self-test, PC health, readiness (2026-10-30, read-only; only the update hold-back acts):** `engine/pc_selftest.py`
  runs 27 of the repo's suites + 3 checks (timezone/tzdata, config, no blocking local edit) ON the PC: each suite a
  sealed child (BELOW_NORMAL, no window, temp TMP + `NINJATRADER_FOLDER`, no live env / push keys, `LE_SELFTEST_CHILD=1`
  = `engine/push` sends nothing real, no relay / GitHub, temp key files), 2 at a time, 240 s budget; ~45 s here (sum 87 s,
  `MEASURED_S`). Left out (measured): test_dst, test_acctb_not_placed, test_lit_oif, test_win_scripts, test_accounts,
  test_alerts_plus, test_eval_anchor, test_poll_speed, test_lit_live, browser tests. When: (a) after every auto-update
  (`autoupdate.selftest_step` after the 3 old tests, mode update, `--base <old sha>`): exit 1 only on a REGRESSION (a check
  that passed in the old version's last result, or has none) -> the existing rollback + `bad_sha` + push "Update held back:
  <check>"; a check that failed before too is "known" (never holds: a Windows-only failure must not block every update);
  skipped when the checkout has no pc_selftest.py. (b) Sunday 15:30 ET, (c) Start page "Run self-test" (`GET/POST
  /api/next/start/selftest`, POST local only, not an autopilot step; `start.js` selftestLine / wireSelftest) or `python
  -X utf8 -m engine.pc_selftest [--list|--status|--only k]`, (d) a baseline once per version after a server start (outside
  01:50-16:00 ET weekdays). Result `logs/selftest.json` + `selftest_history.jsonl` (60); heartbeat "selftest". Pushes kind
  `selftest` (fail / could not run) and `selftest_ok` (Sunday all green), via `alerts_plus.pc_send` (app levels).
  `engine/pc_health.py`: lines cpu (median of 5) / ram / disk / nt (NinjaTrader.exe + MB, Windows; red when closed in the
  session while the bot routes) / bot_mem (growth after a 10-min warm-up, MB an hour) / onedrive (" (1)." and
  "-<COMPUTER>." copies, red in data/) / clock (`guards._CLOCK`, never probed here) / poll (15-min median vs the hour
  before); psutil missing or Windows-only -> the line is skipped. Red twice in a row -> push kind `pc_health` once per
  issue per ET day. `Watcher` thread (server.py `PCWATCH`, every 60 s, `LE_PC_WATCH=0` off, never with LE_NO_AUTOSTART /
  in a self-test child) writes `logs/pc_health.json` (heartbeat "pc_health") and runs the schedules (ET wall clock).
  `engine/readiness.py`: Sunday 17:30 ET push kind `readiness` (version + self-test, Run switch, both accounts' room + eval
  day N of 10 from `board_api.board_view`, BLITZ from `go.blitz_status`, high-impact USD news Mon-Fri, early closes /
  closed days, the DST line); `python -X utf8 -m engine.pc_health --readiness [--send]`. Kinds are in
  `alerts_plus.KINDS`; the phone's Alert levels list (`tools/web_public/alerts.js` KINDS) does not show them yet.
  Tests `tests.test_pc_selftest` (64), `tests.test_pc_health` (76).
- **Alerts plus (2026-10-21, `engine/alerts_plus.py`, `tests/test_alerts_plus.py`, `docs/NOTIFICATIONS.md`):** "LIT setup armed"
  / "Setup expired" pushes (PC `LiveBot._alerts_tick` after routing + cloud, same keys, relay de-dup); critical alerts repeat
  every 10 min (max 6) until "Got it" (phone `tools/web_public/alerts.js` #/ack posts `{"le":"ack"}` to the ntfy relay) or
  they clear (PC: heartbeat "crit" -> ops tick; cloud: Surface offline); stale-cloud alarm in the ops tick (`git ls-remote`
  of `dashboard`, 45 min); PC-vs-cloud rules hash in the heartbeat / cloud state ("rules"); on/silent/off per kind
  (`{"le":"prefs"}`). Read-only: never changes what the bot trades.
- **TradingView:** Pine port in `tradingview/liquidity_engine.pine` (parity notes in `research/PINE_PARITY.md`). Since 2026-10-17 it
  carries the locked rules ($800/20-pt sizing, 1 trade/day, no fallback target, cold-streak filter with a `cold size` input)
  and an "Alert format" input: bridge JSON (TradersPost / PickMyTrade) or phone text. `tools/pine_sim.py` is its bar-by-bar
  replica: 780/780 trades equal to the engine on the same bars; TradingView trades MNQ1! prices (the engine NQ1!), so a few
  trades a year differ. Expected Strategy Tester numbers and the Sunday checklist: `tradingview/BRIDGE_SETUP.md`.
- Refreshing `data/*.csv` needs the owner's TradingView export (tools/grab_tv_export.py on the PC). Cloud sessions can't do it.
- **Real balance from NinjaTrader (2026-10-25, `engine/broker_balance.py`, `tests/test_broker_balance.py`):** LE_BarFeed
  also writes `le_feed\accounts.csv` (name,time,cash,realized,unrealized,netliq; once a minute + on account updates;
  C# UNTESTED on a real install, steps in `ninjatrader/SETUP.md` 4b). Fresh (< 3 min), sane, non-Sim row of the
  account -> (a) day-close auto-anchor: balance = real cash, floor = max(prev floor, EOD - MLL) locked at start+$100,
  stored in `data/broker_balance.json` (gitignored) and fed to `newest_anchor` (LiveBot / account B / extra accounts,
  each by its own NinjaTrader Name); (b) room = min(ledger room, real equity - floor) in `eval_state` / `eval_room`;
  (c) > $50 apart for 5 min -> one "balance differs" push a day; (d) missing / stale -> identical to before. Switch
  `"broker_balance"` (start cfg or lit_sizing): unset = on for the real bot only. Bot Brain step "Real balance", launch
  checklist line "Real balance from NinjaTrader" (green when fresh, else info). `python -m engine.broker_balance`.

## OLYMPUS apps and tools (map written 2026-11-04, checked against the code)

**Who wires what.** An app is a folder `tools/web_public/<id>/` with `index.html` + `jarvis.json` (the status card, `docs/JARVIS_APPS.md`). It is
"wired" when the LEAD has done the wiring checklist at the end of this section (apps.js, olympus.js, the build tuple, root `sw.js`, then the apps-list
generator; transitions and intro lines are in the shared files). **Agents (and sub-agents) never edit `sw.js`, `tools/build_web_dashboard.py`,
`jarvis/apps.js` or the `APPS` table of `olympus.js`**: their report lists the "wiring needed" and the lead does it (and bumps the workers). Every app is
read-only and paper only; the 3D ones run on the OLYMPUS render core (`olympus/render.js`, `docs/OLYMPUS_RENDER.md`) with the tiers `ultra / high / low /
off` of `OLYMPUS.fx()` (Jarvis key `jfx`), and show a DEMO fixture instead of going blank when their data is missing.
**State on 2026-11-10 (read from the code): 61 apps in `jarvis/apps.js` BUILT_INS = 32 Trading + 18 Money + 11 Life (Zenith included); the 2026-11-04
figures still hold for the rest: 42 library effects + `fx-atmos.js`, 14 sound beds, 78 Bridge jobs in 14 categories.** Recount with
`python tools/apps_list_build.py --check`, `python tools/olympus_map_build.py --check` and `python tests/run_gate.py --list` instead of trusting this line.
The every-app table (id, district, group, description, data read, test) is **generated**: `docs/OLYMPUS_MAP.md` (`python tools/olympus_map_build.py`, `tests.test_olympus_map`);
the hand-written table below is the 2026-11-04 map and is not updated any more.

**Night sprint 2026-11-10 (what changed, short).**
- **Look: AGORA** (`docs/DESIGN_AGORA.md`, `olympus/agora.css`, `data-theme="agora"`): marble / bronze / gold / olive / terracotta, serif headings, no neon or HUD, bloom <= .25. The old cyber look is removed; kit page tests check it (`tests/agora_kit.py`).
- **Money machines** (paper only, they read public data and write JSON, never trade): scanners `tools/money/<id>.py` (mercury, chrysos, sibyl, oikos, arbiter + `sibyl_ledger.py`, `sibyl_results.py`, `pythia_dates.py`), the runner `tools/money_engine.py`
  (`--out`, 30-minute schedule via `RUN_MONEY.bat`), the publisher `tools/money_publish.py` (copies to `<site>/money/`), plain-words guide `docs/MONEY_MACHINE.md`; pages Mint, Mint City, Stoa, Mercury, Chrysos, Sibyl, Oikos, Arbiter (tests `test_<id>_page`, `test_money_engine`).
  Sibyl's own paper record (`sibyl_forward.json`) is kept on the PC in `money_keep\` by `RUN_MONEY.bat`; no claim below 30 settled bets.
- **Connect the day** (team X2, 2026-11-14, `docs/CONNECT_DAY.md`): read-only ICS links (Google secret address, iCloud public link, Outlook ICS, When I Work / Deputy /
  7shifts / Homebase / Sling / HotSchedules) kept in `%USERPROFILE%\.olympus\calendars.json` -> `tools/calendar_sync.py` (stdlib `tools/ics_parse.py`: RRULE, EXDATE, overrides, TZID incl.
  Windows names, VTIMEZONE, DST) every 15 min from `tools/pc_report.py` -> `data/day/day.json` (gitignored, served ONLY at `/site/day/day.json` by `engine/live_site.py`): per NY day the work
  shifts, free blocks, the overlap with LIT's 02:00-15:30 window, pythia news / holidays, ONE sentence ("You work 9-5 today: the bot trades alone; check at lunch 12:30."), the week line
  (hours worked vs trading cash from the money scoreboard; pay = Ledger income tagged paycheck / `POST /inbox/money` type paycheck, else the typed wage), weather (api.weather.gov) and Fed / BLS
  headlines (`tools/day_feeds.py`). Phone: `olympus/day.js` (pure) -> Planner "Your work day" card, Jarvis copilot Work line (01:45 / 10:45 / 16:05) + `my_day` intent, briefing lines.
  iPhone "Add to my day" = `POST /inbox/day` (`engine/day_inbox.py`, header `X-Olympus-Inbox: 1`, appends `data/inbox/day.jsonl` only; the guard's one POST exception, active only after
  `day_inbox.install(app)` in server.py: lead wiring). Shared `/inbox/{kind}` shape with the money inbox (`day_inbox.register`). Test `tests.test_calendar_sync`.
- **Money scoreboard** (2026-11-13, read-only, paper only): `tools/money_scoreboard.py` reads every money source (NQ accounts by the truth.js rules from
  `home.json` / `data.json` / the PC's `data/pc_report/live.json`; payouts recorded with the bot = `goals.money.payouts`; second strategies; the Kalshi feed
  `kalshi.json`; `money/index.json`; the real eval prices `ledger/rules.json`, else the CLAUDE.md prices; the Plutus H2 plan rate; the owner's
  `data/money_ledger.json` = a Ledger Export JSON, gitignored) -> `money/scoreboard.json`: cash in / out / net for the week / month / all time, by source,
  ROI on eval fees, cash run-rate (needs 28 days), plan estimate, milestones $10K / $100K / $1M with ETAs; a missing source is listed, never invented.
  Paper P&L and money-machine estimates are never counted as cash. The ledger is PRIVATE: in a written file only with `--private` or `"publish": true`.
  `--site <dir>` = the build step (writes `<site>/money/scoreboard.json`), `--print` = the table. Shown by the Ledger's Overview "Scoreboard" card
  (`ledger/scoreboardcore.js`). Sunday report `tools/weekly_money_report.py` (table + made / lost / change lines -> `docs/reports/money_week_<sunday>.md`,
  gitignored, + one push on the PRIVATE ntfy alert topic); `tools/pc_report.py` calls `maybe_run()` every 15 min, it sends once on Sunday from 17:00 ET
  (`data/money_report/state.json`, `LE_MONEY_WEEKLY=0` = off). Tests `test_money_scoreboard`, `test_weekly_money_report`, `test_scoreboard_card` (browser),
  `test_ledger_page`, `test_bots_back`.
- **Connect the money** (2026-11-14, paper only, `docs/CONNECT_MONEY.md`): `tools/money_import.py` reads the owner's OWN bank / card exports (CSV / OFX / QFX; Chase, BofA, Wells Fargo,
  Capital One, Apple Card, Discover, Amex, Cash App, PayPal, Venmo, generic) from `%USERPROFILE%\.olympus\money_inbox\` (+ `OlympusMoneyInbox`, `OLYMPUS_MONEY_INBOX`), masks every
  account number, de-dups by fingerprint, sorts by rules (`data/money_rules.json`, gitignored; `--init-rules`) into the PRIVATE `<home>/money/` (ledger, balances, net-worth history,
  oikos_ledger) and `money_out/household.json` (month in / out, categories, subscriptions + next date, prop ROI, Kalshi moves, runway, leaks, net worth, `jarvis` answers; no merchant
  names unless `privacy.publish_merchants`). household.json goes to the phone ONLY over the private link (`engine/live_site.MONEY_KEEP`), never `money_publish.KEEP`. Feeds: Oikos card
  (`oikos/householdcore.js` + `household.js`), `tools/money/oikos.py` (bank ledger when no `--ledger`), scoreboard `household` block (`--private`, never in the cash totals), Jarvis
  (`jdata` XFILES household, `router` household_spend_cat / _month / _subs / _runway / _networth, `skills.js`). iPhone Shortcut: `tools/money_inbox_server.py` (127.0.0.1:8767, POST /inbox
  append-only to `money_inbox/cash.jsonl`) + `MONEY_INBOX.bat` (`tailscale serve --https=8443`). `RUN_MONEY.bat` runs the importer first. Tests `test_money_import` (+ node .mjs),
  `test_money_inbox`, `test_oikos_household` (browser).
- **New apps** (folder + test each): Delphi, Pnyx, Hestia, Demeter, Apollo, Hera, Dionysus, Clio, Kronos (calendar of money), Pythia (risk calendar; `events.json` is GENERATED by `tools/money/pythia_dates.py` from rules + `data/news/events.csv`), Pheme (release-day history; `stats.json` built by `tools/pheme_build.py`, `--check` in its test), Kairos, Kratos, Argo, Gallery, Moirai, Nike, Lyceum, Aegis, Epilogue; the full list is `docs/OLYMPUS_MAP.md`.
- **Wiring a new app, the NEW way:** add a row to `tools/new_apps.json` (id, name, group, accent, glyph, description < 80 chars, ambient, flavour [existing intro scene, tagline, sound], transition) and the lead runs `python tools/wire_new_apps.py --dry-run` then `--apply` (idempotent; edits apps.js, olympus.js, the build tuple, sw.js, intro-app.js, transitions.js; `tests.test_wire_new_apps`), then `python tools/apps_list_build.py`. The old by-hand checklist below still works. Agents still never edit those six files.
- **Audit tools:** `python tools/phone_fit_audit.py` (every app at phone sizes), `python tools/make_app_icons.py [ids]` (Home Screen icons from each `icon.svg`, `--check`; `tests.test_new_app_icons`, `tests.test_homescreen`).
- **IA v2: nine hubs (2026-11-14, `docs/OLYMPUS_IA_V2.md`).** The front door (`gate/`) is a command center (Right now: bots, drawdown left per eval, today's $, window, Kalshi, my shift; then nine hub tiles with a live line; then search). Hubs = the owner's jobs: Today, Bots & Evals, Kalshi, My Money, Plan & Day, Research, Jarvis, Worlds, Settings & Help; page `hub/?h=<hub>&t=<tab>` (one tab per job, best app first, duplicates folded under "Other views of the same"). The hubs are DATA in `olympus/gate-catalog.js` (v2: `district` = hub, so a theme's per-district mix follows hubs; 9th column = folded into); live lines `olympus/hub-status.js`; breadcrumbs Home > Hub > app + "Go to" (hubs first) = `olympus/gate-nav.js` v=g2, which `olympus/agora-ui.js` v=2 now loads on every AGORA app. A new app needs a catalog row (hub, tab). Tests `tests.test_hubs`, `tests.test_gate_page`. Wiring: `'hub/'` in sw.js OTHER_APPS, `"hub"` in the build copy tuple.
- **Atlas** (`atlas/`) groups every app into five districts (Market / Research / Money / Command / Life); its node tests: `node --test tests/test_atlas_standalone_hub.mjs tests/test_atlas_intro.mjs`.
- **3D in the new pages** (marble ball, sundial, wheel, rack): its own `*.js` module tag after the page module, so a failed 3D load never stops the page; a flat SVG twin for `?q=off` / no WebGL.

### The apps (group = Jarvis switcher group; every row below is in `apps.js` today)
| App (id) | Group | Folder | What it is | Reads (data it shows) | Test |
|---|---|---|---|---|---|
| Zenith | Trading | `tools/web_public/` (root `index.html` + js) | the phone dashboard of the NQ bots | `data.json`, `live.json` (branch `live`) | `test_zenith_pages`, `test_zenith_shell`, `test_phone_e2e` |
| Oracle | Trading | `oracle/` | the market radar: NQ in 3D, LIT levels, sweeps, the bot's stage and position | `live.json`, `home.json`, `demo_day.json` | `test_oracle_page` |
| Odeon | Trading | `odeon/` | every trade replayed in 3D | `trades.json` (CRONOS nightly) | `test_odeon_page` |
| Fates | Trading | `fates/` | pass odds per eval | `fates.json` (`python -X utf8 -m tools.fates.build`, CRONOS nightly) | `test_fates` |
| Data City (`datacity`) | Trading | `datacity/` | every combo tested, as a city (2026-11-10: 9 more state families: day / week of month, month-end / quarter-end, FOMC week, gap size, hour of day, overnight range, first-hour direction, ES-NQ over the last hour; filed in the same nine districts, `features.NEW_FAMILIES`, honest counts in `summary.new_families`) | `city.json`, `plugins.json`, `discoveries.json` (the `datacity` workflow / branch) | `test_datacity` |
| Daphne (`tree`) | Trading | `tree/` | the strategy-tree search as a growing tree | `tree.json` (`python -X utf8 -m tools.strategytree`, CRONOS weekly), `demo.json` | `test_strategytree` |
| Prometheus | Trading | `prometheus/` | the strategy-evolution forge (research only) | `forge.json` (`tools/prometheus/forge.py`, CRONOS weekly) | `test_prometheus` |
| Pantheon | Trading | `pantheon/` | the data gods (liquidity, rates, vol, calendar, ...) and the council verdict; My Desk (`#desk`, 2026-11-04, `pantheondesk.js`): macro events inside/outside the 02:00-15:30 window, gods you follow and who changed their mind, has the Council beaten noise, source freshness, Copy line | `pantheon.json`, `states.json` (`tools/pantheon/build.py`, CRONOS nightly) | `test_pantheon` |
| Ares | Trading | `ares/` | the war room: GO / WAIT / HALT, size follows the stop, pre-trade ritual, rules you broke | `rules.json` (`tools/ares_plutus_build.py` from `research/lit/mffu_rules.json`), `../data.json`, `../home.json` | `test_ares_page` |
| Forum | Trading | `forum/` | the morning briefing and oath at the real NY hour | `../pantheon/pantheon.json`, `../home.json` | `test_forum_page` |
| Labyrinth | Trading | `labyrinth/` | the risk maze: size your eval (what-if) | `../odeon/trades.json`, `../home.json` | `test_labyrinth_page` |
| Argus | Trading | `argus/` | the watchtower: every health light, what to fix first | `../home.json` (else `data.json`), `../cronos/status.json`, each app's `jarvis.json` | `test_argus_page` |
| Nemesis | Trading | `nemesis/` | the fallen trades: autopsy of each loss | `../odeon/trades.json`, `../home.json`, Zenith journal tags (phone) | `test_nemesis_page` |
| Chronos | Trading | `chronos/` | replay any trade day: the 1-minute path and its steps | `../odeon/trades.json` | `test_chronos_page` |
| Hephaestus | Trading | `hephaestus/` | turn a dial, see the STORED backtest run (nothing computed in the page) | `data.json` (`tools/hephaestus_build.py` from `research/runs/`) | `test_hephaestus_page` |
| Bridge | Trading | `bridge/` | Claude x ChatGPT link: 3-step wizard, 11 cards + 78-job library (14 categories), Deliveries, Ask next | `status.json`, `jobs.json`, `deliveries.json` (`tools/bridge_sync.py`) | `test_bridge_page`, `test_bridge_ingest` |
| Planner | Life | nq-dashboard `planner/` | calendar, tasks, projects (+ our patches) | its own store; `tools/planner_patches/*.patch` | `test_planner_addons` |
| Mind | Life | `mind/` | the Obsidian vault as a living 3D brain (DEMO brain when not connected) | `jarvis/obsidian.js` `graphSnapshot()` only | `test_mind`, `test_mind_page` |
| Arena | Life | `arena/` | Olympian ranks: XP for discipline | `events.json` (`tools/arena/build.py`), the phone adds Planner / Obsidian / Kalshi | `test_arena` |
| Athena | Life | `athena/` | the library: Ask / Today / Cards / Rules / Saved / **Train** (2026-11-04: 8-question daily quiz from the library only, Leitner boxes in `localStorage['athena.train.v1']`; "Read the chart" = 10 real replayed setups, would the bot take it + where is the stop; streak; weakest topic + ONE thing to study; code `athenatraincore.js` pure + `athenatrain.js` screens) | `library.json` (`tools/athena_build.py` from `STRATEGY.md`, the MFFU rules, the rejected list); `drills.json` (`tools/athena_drills.py` from `research/lab/backtest_live.json` + `data/NQ_5m.csv`; rerun after the replay is re-exported, `--check`) | `test_athena_page` |
| Kalshi | Money | `kalshi/` | the Kalshi bot's numbers | `kalshi.json` from the public `kalshi-feed` repo (`engine/kalshi_publish.py`) | `test_kalshi_page`, `test_kalshi_publish` |
| Tyche | Money | `tyche/` | the Kalshi bets as a 3D fortune wheel (coins, fortune card, compare, replay; Cash tab 2026-11-04: break-even win rate, money at risk and when it comes back, pace vs the usual day, best hours, one-tap money line; `cash.js` + `cashpanel.js`) | the same `kalshi.json` | `test_tyche_page` |
| Hermes | Money | `hermes/` | OLYMPUS Wrapped: story cards of your money, share PNG; 2026-11-04 cards: pass clock, cushion (losers you can afford), week rank, weekdays, plain-line summary + Copy as text (`cards2.js`) | `wrapped.json` (CRONOS `hermes` build task), `../datacity/discoveries.json`, `../fates/jarvis.json` | `test_hermes` |
| Plutus | Money | `plutus/` | the money plan: accounts, fees, payouts, goal tracker | `plans.json` (`tools/ares_plutus_build.py` from `research/lit/funded_firms.json`), `../data.json` | `test_plutus_page` |
| Archive (`archive`) | Trading | `archive/` | the library of everything we ever tested: every run (2,273), write-up, rejected idea (Don't redo this) and dataset; search, filters, compare two runs, 3D marble shelves | `archive/index.json` + `runs-<k>.json` shards, built by `python tools/archive_build.py` (`--check`, `--selftest`; must run in the site build) | `test_archive_page` |
| Cities (`cities`) | Trading | `cities/` | the world map of floating city islands (one per dataset; 170 cities in `cities.json`, city of the day, Surprise me) | `cities.json` + the other apps' published JSON (odeon, fates, datacity, tree, prometheus, pantheon, hephaestus, arena, athena, plutus) | `test_cities_page` |
| Kalshi City (`kalshicity`) | Money | `kalshicity/` | the Kalshi bot's edges as a night city: edges, the Lab ring (ideas tested on the bot's own bets), "If you change the bot" what-if, "What we learned" | `edges.json`, `learning_log.json`, `hypotheses.json`, `whatif.json`, `learned.json` (`tools/kalshi_edges.py`, `kalshi_hypotheses.py`, `kalshi_whatif.py`, `kalshicity_learned.py`), live `kalshi-feed` | `test_kalshi_edges`, `test_kalshicity_page` |
| Ledger (`ledger`) | Money | `ledger/` | the owner's REAL money: fees, payouts, net profit, taxes, a coin vault that grows (`docs/LEDGER.md`); entries only on the phone (`localStorage ledger.v1`), JSON / CSV export | `rules.json` (`tools/ledger_rules.py`), `../home.json`, public Kalshi feed, `fixture.json` (DEMO) | `test_ledger_page`, `test_ledger_freeze` |
| Inbox (`inbox`) | Life | `inbox/` | everything that needs a look in one list: bot events, Argus, Kalshi, Bridge, Jarvis | `../bridge/status.json`, `../kalshicity/learning_log.json`, `../live.json`, the public Kalshi feed and every app's `jarvis.json` | `test_inbox_page` |
| Mnemosyne (`journal`) | Trading | `journal/` | a 10-second trade journal: rate the trade, did you interfere, what the habit cost in dollars, next week's one rule | `../odeon/trades.json` (`fixture.json` = DEMO); entries on the phone (`journal.card.v1` card read by Jarvis) | `test_journal_page` |
| Settings (`settings`) | Life | `settings/` | quality, look, Sound (Auto / On / Off), Jarvis, saved data and the tour in one place; keys and tokens never shown | this phone's own keys only (`jfx`, `olympus.sfx`, ...) | `test_settings_page` |
| pc/ (not an app) | - | `pc/` | static downloads for the owner's PCs (FRESH_START, CLEAN_STORAGE, PC_CARE) | - | `test_fresh_start`, `test_clean_storage`, `test_pc_care` |

Jarvis (`jarvis/`) is the shell, not a row: the hub (3D home: `home3d.js|css`, 7 AM ET spoken briefing `briefing.js`), the orb switcher, the assistant. **Wiring
not done yet:** none in the list; what is still open is the a11y tags (only `journal/` and `settings/` have them, see `docs/OLYMPUS_A11Y.md`).
**Money copilot (J1, 2026-11-13, `jarvis/copilot.js` + `copilot-card.js`, `docs/JARVIS_API.md` "Money copilot"):** offline rule answers over the published files, accounts through `olympus/truth.js`: "should I trade today" = GO / CAREFUL / SIT OUT with the reasons (news, holiday, window, PC age, room in full losses, daily loss, quiet days), loss budget today / before the eval fails, P&L with best / worst / win rate / $ a month, pass odds ($ to go, wins needed, H2 odds, Fates %), what changed since yesterday (snapshot `jarvis.copilot.v1`), Kalshi's day (exposure). Home card `#hcopilot`: 01:45 / 10:45 ET plan, 16:05 ET day summary. Asked by skills.js right after the safety guard. Test `tests.test_jarvis_copilot`. Wiring needed: `jarvis/sw.js` SHELL += `./copilot.js`, `./copilot-card.js?v=cp1`, `../olympus/truth.js`.
The Kalshi app (`kalshi/`, k18) has three top cards in Today: "Why am I losing" (top two dollar leaks), "Do not take this bet" (guard: green/amber/red per open bet with the dollar reason, suggestions only, never places orders), and the verdict; the Edge group opens with "If you change the bot" (rule sets A/B/C replayed on past bets; same maths as `tools/kalshi_whatif.py` -> `kalshicity/whatif.json`). Tests: `test_kalshi_page --only=guard|whatif`.
`tools/release_manifest.py` did not land (there is no such file); the release check is `tests/run_gate.py`. Tests are run as `python -X utf8 -m tests.test_<name>`.

### Shared kit and the new engines
- **Data truth (QA round 6, 2026-11-11):** `olympus/truth.js` (ES module, pure) is the ONE place for drawdown left / balance / data age:
  `accountsOf(home)` (home.board first, then the PC's own accounts row, never the cloud paper twin; ATLAS from second.account_b, BLITZ from
  live.pc.blitz), `agesOf(home)` ("Numbers from the PC report 5 days ago (cloud copy 59 minutes old)."), `canonHome(home)` for older cores.
  Used by Aegis, Helios, NQ, Ergasterion, the people kit (`people-data.js`), the Agora lab and the root strip (`window.OLYMPUS_TRUTH`, `more.js`).
  A new page that shows account numbers reads them through it. Test `tests.test_truth` (same numbers in Aegis, Helios, NQ and Home).
- **Quiet net:** `olympus/quiet-net.js` (classic, first script in `<head>`) asks the suspended GitHub sources (nq-dashboard, kalshi-feed) and
  the optional `kalshi.json` once per browser session (4 s limit), then answers 404 locally (`window.OLYMPUS_NET`). A page that calls them
  loads it first. Optional files get honest empty copies from their builders (`tools/cronos/site.py` PLACEHOLDERS + cronos status,
  `tools/polis_build.py` sky, `tools/money_publish.py` Sibyl ledger). Test `tests.test_quiet_data`.
- **Kit** (`olympus/`): `olympus.js` + `olympus.css` (veil, tiers, per-app name / glyph / colour, `data-oly-fx` wiring), `render.js` + `materials.js` (real
  materials, bloom), `themes.js`, `sfx.js` (`docs/OLYMPUS_SFX.md`), `a11y.js` + `a11y.css`, `apps-list.js` (generated), `intro-app.js`, `scenery.js`. Rules and budgets:
  `docs/OLYMPUS_DESIGN.md`; tests `test_olympus_kit`, `test_olympus_render`, `test_olympus_themes`, `test_olympus_sfx`, `test_olympus_a11y`, `test_apps_list`.
  **Kit test PERF table** (`tests/test_olympus_kit.py` `PERF = {...}`, 23 apps today): per app `(page query, draw-call budget, triangle budget)`, the budget
  = the measure + 25% (three.js `renderer.info`, portable; fps is never judged); calls 0 = no scene (heap only). **A new 3D app adds a row** (measure
  it on the test box first); an app without a scene (ledger, inbox, journal, settings, bridge) has none.
- **Themes (2026-11-14)**: 32 looks on the Gate's Look row (One look / Mix), keys `olympus.theme` + `olympus.themeMix`; colours reach a
  sheet through theme slots: `python tools/theme_tokenize.py --apply <sheet>` (default unchanged by construction), check with
  `python tools/theme_shots.py --site <built site> --themes midnight --leftovers` (also `--mix trader`). Details: `docs/OLYMPUS_DESIGN.md` "Themes".
  **Locked down (2026-11-14, team T2)**: the QA matrix `python -X utf8 tools/theme_shots.py --qa --site <built site> --out <dir> [--themes a,b] [--pages
  home,nq] [--live --mixcheck]` (every look x home, 9 hubs, 6 dashboard tabs, 12 apps; text AA on real pixels, AGORA leftovers, +$/-$, status bar, no flash,
  focus ring, sheets / toasts; `tools/theme_qa.js`), `--table <before> <after>` writes `qa.md` (results: `docs/shots/themes_v2/`, 960 / 960 cells clean on 2026-11-15). A page whose
  engine loads after its first frame carries themes.js's FIRST PAINT copy in its `<head>` (letter for letter, the test checks it); a kit app that is
  checked in light says `<html data-oly-light>`. P2's cheap path for the frosted looks: `OLYMPUS_THEMES.noblur(true)` (or `<html data-oly-noblur>`).
- **Sound** (`olympus/sfx.js`, `docs/OLYMPUS_SFX.md`): 14 synthesised ambient beds (WebAudio, no files); the app -> bed table is `AMBIENT` in `olympus.js`
  (`test_olympus_sfx` needs an entry for every app: **a new app = one `AMBIENT` entry**). `OLYMPUS.sound(true | false | null)` is the Sound switch (null =
  automatic: silent in LITE / reduced motion / battery saver; Settings and Jarvis Settings have it), `OLYMPUS.cue('open' | 'close' | 'success' | 'warning' |
  'tap')` plays a UI cue (silent before the first tap, when muted, and in LITE unless Sound is on); an element with `data-oly-cue` gets one on tap (Ledger,
  Inbox, Bridge use it). Nothing sounds before the first touch.
- **Atmosphere kit** (`olympus/fx-atmos.js`, ES module on the render core's three): dust, embers, god-ray shafts, contact AO, polished floor, bronze /
  forged iron, thread glow; each one draw call, `.object` / `.update(t)` / `.setQuality()`. Separate from the 42 `OLYMPUS_FX` effects below.
- **Accessibility layer** (`olympus/a11y.js` + `a11y.css`, ES5, `docs/OLYMPUS_A11Y.md`, `test_olympus_a11y`): Dynamic Type / big text, the ink guard (muted
  text kept readable on every theme: 122 theme pairs audited), focus ring, automatic aria-labels, live toasts, reduced motion / contrast. Loaded by two tags
  per page; the lead inserts them (report lists the apps that need them).
- **Zenith launcher** (`launcher.js`, byte-identical in `web_next/js/next/`; test `test_apps_list`): the Olympus button on the phone and PC dashboards opens a sheet
  of tiles by group (Trading / Money / Life), search, recent, and a status dot per app read lazily from `<app>/jarvis.json`. It reads `olympus/apps-list.js`.
- **Apps-list generator** (`tools/apps_list_build.py`): builds `olympus/apps-list.js` (`window.OLYMPUS_APPS_LIST`: id, name, glyph, colour, group, purpose,
  path, live) and its copy `web_next/js/next/apps-list.js` from `jarvis/apps.js` BUILT_INS + the `olympus.js` APPS table. **Run it after every edit of
  `apps.js` or `olympus.js`** and commit both outputs; `--check` prints "in step with its sources" or fails (and `test_apps_list` fails when stale).
- **Effects library** (`olympus/fx-*.js`, `docs/OLYMPUS_FX.md`, lab `olympus/fx-lab.html`, `test_olympus_fx`): 42 effects as `OLYMPUS_FX.<name>(el | scene, opts)
  -> { stop() }`: UI (`fx-ui.js`), text / numbers (`fx-text.js`), bursts (`fx-burst.js`), and three.js scene effects (`fx-sky.js`, `fx-weather.js`,
  `fx-surface.js`, helpers `fx-three.js`). One shared frame loop, particle and canvas caps, tier-aware (`OLYMPUS.fx()`), off under reduced motion,
  paused when the tab is hidden. **Zero-edit wiring:** any element with `data-oly-fx="shimmer|glow|ripple|tilt|odometer ..."` gets the effect; opt out
  with `data-oly-fx-off` (element or ancestor), `<html data-oly-fx-ui="off">` or `OLYMPUS.fxUI(false)`. Several apps use it directly
  (Tyche, Plutus, Hermes, Forum, Ares: `*fx.js` / `*desk.js`).
- **Transitions** (`jarvis/transitions.js`, test `test_jarvis_transitions`): every jump from one app to another plays that app's signature (Oracle lightning,
  Pantheon columns, Tyche waves ...) on ONE reused 2D canvas over the loading app, 600-1100 ms, skipped by a tap / Esc / Enter. The app -> kind table is
  data (`REGISTRY`; an app without a line gets the warp `DEFAULT`). LITE tier (3D Low / Off) = a 250 ms colour fade; reduced motion = a 200 ms flat fade.
  `portal.js` hands each jump to it (the old WebGL warp is the fallback). A new app = one `REGISTRY` line (the test fails without it).
- **App intros** (`olympus/intro-app.js`, test `test_app_intro`): a 2.6 s cinematic entrance (the app's flavour scene, glyph from particles, name and
  tagline) loaded by ONE line in each app's `index.html` after `olympus.js` (`<script src="../olympus/intro-app.js?v=i1" defer>`; 25 pages have it
  today, 2026-11-04). Once per app per launch (`sessionStorage oly.intro.<app>`), then a 400 ms version; LITE = a 0.7 s fade; never under reduced motion, 3D Off,
  `?q=off`, `?intro=0`, `localStorage oly.intro=off` or an automated browser (unless `?intro=1`). A tap skips it. State in `window.__olyAppIntro`. **Pages without the kit** (Bridge, Kalshi; team FX 2026-11-15) name themselves on the tag: `<script src="../olympus/intro-app.js?v=i5" data-app="kalshi" data-name="Kalshi" data-glyph="K" data-color="#8fa07a" defer>` (the kit's `jfx` quality key and reduced motion still apply). **3D touches (FX 2026-11-15):** Gate hub tiles tip toward the finger with a gold light and rise in on a fresh open (`gate.js` `tilt3d`, `html[data-g3d]`); hubs: the best app's icon turns in like a coin, the Me hub's four tiles rise (`hub.js` `mark3d`); CSS only, none under reduced motion, Battery / Still, the battery saver or LITE.
- **Cities engine** (`cities/`, `test_cities_page`): data-driven. `cities.json` = the list of city specs (adding a city = one entry), `datasets.js` =
  adapters that read the other apps' published JSON, `generator.js` = the generic builder (spec -> buildings; `procedural.js` = random cities from a
  seed, "Surprise me"), `scene.js` / `rig.js` = the three.js world and cameras (ORBIT / SKIM / DRONE / GRAND, minimap, Find, Top 10, tour), `insight.js` =
  one plain sentence per city (strongest / weakest district) and the report table. Groups: Trading, Research, Money, Kalshi, Life, Obsidian. Favourites / visited stay on the phone. Read-only.
- **Kalshi City + edges engine** (`docs/KALSHICITY.md`): `tools/kalshi_edges.py` reads `kalshi.json`, keeps every bet it has seen (`ledger.json`,
  the feed holds only ~40), re-measures every edge (slices of strategy / market / ET hour block / price band / side: n, win rate vs the implied
  probability, EV per $1 with fees, Wilson range, z-test, 7 / 30-day decay, Kelly, status NEW / GROWING / HOLDING / DECAYING / DEAD, advice DO MORE /
  KEEP / WATCH / STOP / COLLECT) and appends dated lessons to `learning_log.json`; run it at least every 6 h or bets are missed. `tools/kalshi_demo.py`
  writes the DEMO fixture. The page is district = market, height = EV, glow = recent win rate; it never calls Kalshi and holds no key.
- **Jarvis bots, modes, voice** (`jarvis/`): `bots.js` = Jarvis knows Zlarior (LIT, 50K) and ATLAS (25K) from `live.json` / `home.json`: spoken alerts
  (never over the mic, >= 30 s apart, <= 8 an hour, one event once ever, optional quiet hours), the 01:45 / 16:05 ET plan and recap cards, the Bots
  panel, "Think for me" items; read only, `test_jarvis_bots`. `modes.js` = `auto / trading / research / business / life` ("switch to research mode"),
  `think(D)` rule list and set ET slots when Jarvis thinks unasked, `test_jarvis_modes`. `brain.js` (answers from the hub's own facts, optional smart
  mode with the owner's own key kept on the phone), `assistant.js` (personal notes / reminders, offline), `memory.js` + `obsidian.js` (the vault through a
  fine-grained token on this phone only; writes are append-only / new-file after a spoken "yes"), `tools.js`. Voice: `tts.js` (best natural female
  voice), `voice-out.js` (answers read aloud, switch `jarvis.speak`, default on, the iPhone first-tap unlock), `voice-mode.js` (full-screen conversation,
  the core reacts to the voice; type-to-talk where speech recognition is missing), `test_jarvis_voice`, `test_jarvis_talk`.
- **Money now** (2026-11-04, `tools/web_public/moneynowcore.js` = `web_next/js/next/moneynowcore.js`, byte-identical; phone mount `moneynow.js`, PC mount in
  `web_next/js/next/polish.js` `place()`): the top card of Zenith Home (inside the greeting box, ahead of the Today hero) and of the PC Home (first thing in
  `#nxStatusHome`). Per account (Zlarior 50K, ATLAS 25K, BLITZ 25K only when it has its own account): **Drawdown left $X of $max loss** (never "X of 10 days"),
  today's $, the next thing the bot waits for (open trade: its target / stop; else the board's own line), its status in plain words, and a red / amber / green edge
  (red: a block, a failed eval or under 25% of the drawdown left; amber: under 50%, a missing field or a quiet PC); the bot's check-in line comes from
  `StatusUI.items` (the same one the status bar reads). Only published fields (`MissionUI.accounts`): a missing one says "not published yet", never a blank; with no
  board at all the card is still there. Read-only. Tests: `test_ui_polish` (a static, b node: rows / edges / missing fields / garbage, c phone, d PC) and
  `test_zenith_shell` (Home order).
  **PC status strip** (same core, `MoneyNow.line`; mount `strip()` in `polish.js`, `#nxLine` under the top bar of EVERY PC page, sticky, >= 44 px, links Home):
  "Bot running · last check-in X · Armed: Zlarior, ATLAS" (red when stopped, amber when quiet, "not published yet" when missing).
- **Today's session** (2026-11-04, `tools/web_public/sessioncore.js` = `window.SessionDay`; phone mount `sessionday.js`, loaded after `moneynow.js`): the card of Zenith
  Home right under Money now. The day's windows in ET with the bot's rule in plain words (01:45 game plan, 02:00-15:30 entry window, 15:55 flat, 16:05 recap), what the bot
  is doing now (from `MissionUI.accounts` + the PC check-in), flags (high-impact news from `M.news`, the calendar the page already carries; US/CME holidays from rules in
  the core, no early-close times claimed), ONE sentence "what to do now" ("Nothing: the bot is waiting for a sweep", "You are flat, session over, review in Mnemosyne.")
  and the exact H:MM:SS to the next window (ticks every second). Over a weekend it shows Monday. Read-only; wiring: add the two files to the root `sw.js` SHELL.
  Tests: `test_ui_polish` (a static, b node: modes, DST, countdowns, sentences, news, holidays, c phone: order, 44 px taps, ticking, tap opens Zlarior).
- **Release safety net** (`python tools/release_manifest.py [--base origin/main] [--json]`, `test_release_manifest`): run it before the 5 AM publish. It lists (a) every
  `?v=` asset tag in an app `index.html` whose file changed since the base but whose tag did not, and (b) every service worker (`tools/web_public/sw.js`,
  `web_next/sw.js`, `jarvis/sw.js`, `kalshi/sw.js`) whose cache name did not change although a file in its SHELL / ASSETS list (or the list) changed. Exit 0 =
  nothing stale, 1 = at least one finding (plain words), 2 = no such base. Read-only; the lead bumps the tags / cache names it names.
- **Obsidian starter pack** (`tools/obsidian_pack.py`, `test_obsidian_pack`): builds a ready-to-drop Obsidian vault (~225 markdown notes, ~1,100 `[[links]]`,
  frontmatter tags on every note) from files that already exist: `athena/library.json` (strategy steps, glossary one note per term, MFFU rules, playbooks,
  what we learned, rejected ideas, Kalshi, app guides), `research/lit/mffu_rules.json`, `plutus/plans.json`, `research/writeups/*.md`, and Jarvis's own
  `ME_TEMPLATE` (`jarvis/obsidian.js`). Layout: `00 Home`, `Trading/`, `Playbooks/`, `Research/`, `Money/`, `Templates/` (Daily note, Trade journal entry with
  setup / size / plan followed / emotion / lesson, Weekly review, Kalshi bet review, Idea note), `Daily/`, `Journal/`, `Goals`, `OLYMPUS/Apps/`, and
  `OLYMPUS/Jarvis/Me.md` + `Memory.md` (the exact paths Jarvis reads). No open `- [ ]` lines and no date-named files (Jarvis would list them as his tasks /
  daily notes); account ids are scrubbed (the library still carries one in two entries: fix at the source, `tools/athena_build.py`). Run
  `python tools/obsidian_pack.py` after a source changes (`--check` fails when the committed `mind/starter/{starter_pack.json, starter_pack.js, manifest.json}`
  are stale; `--zip F.zip` and `publish(out_dir)` write a real `obsidian_pack.zip`: one line for the site build). The Mind page's Teach screen has the
  Starter pack card (`mind/starter.js`): Download as .zip (a ~60-line store-only ZIP writer with CRC-32), Copy as one markdown file, 3 plain steps
  (Files app -> Obsidian Open folder as vault -> connect the vault in Jarvis), the notes by folder with previews. It never writes into a vault. The same notes
  join the Mind demo brain (`demo.js addPack`, `data.js`) when no vault is connected or the vault is empty.
- **Bridge** (Claude x ChatGPT, `tools/web_public/bridge/`, `handoff/`): the page has the 3-step Connect wizard (its sync prompt must equal
  `handoff/ONBOARD.md`), the 11 job cards, and (2026-11-04) tabs Library (`jobs.json`, 78 ready jobs in 14 categories (art, copy, docs, fixtures, logo, lore, mockup, money, names, obsidian, research, sound, strategy, textures; each with an `ingest` line), built by
  `tools/bridge_jobs_build.py`: edit the generator, not the json), Deliveries and Ask next. ChatGPT delivers into `handoff/inbox/<id>/` with a `DONE.md`.
  `tools/bridge_ingest.py` (also run inside `bridge_sync.publish`, `--apply` copies approved images to `olympus/assets/<id>/` with a manifest)
  checks each file read-only: png / webp / svg / json / md / txt / small js only; caps 5 MB images, 200 KB svg / md / txt, 1 MB json, 100 KB js, 80 files
  and 40 MB a job; real images; no secret patterns; no script that fetches, evals or imports; no symlinks. Nothing delivered is ever run. The tab's
  "Tell Claude to use this" copies `Bridge: <id> done`; `status.json` also carries `next` (weekly static rules) and `deliveries`.
  **JOB 13 (2026-11-04, end-to-end rehearsal with a fake ChatGPT, `test_bridge_ingest` part g, in a temp copy of the repo):** the page's top is three stages of
  three steps (Connect / Test / Use), plain words only (test scans for pull request / prompt / JSON / repo ...), `Tell Claude` is on every card. **Test the link**:
  the owner pastes ChatGPT's one-line `LINK OK <word>`; the word is the `LINK WORD:` line of `handoff/SYNC.md` (change both together; the test compares them);
  client-side only. A rejected file gets ONE plain sentence (`bridge_ingest.plain_reason`, shown as "Not used: name. ..."). Claude's side: `python tools/bridge_ingest.py
  --handback "Bridge: <id> done"` reads the job back in one plain paragraph; the report also says when a folder / file is skipped (capital letters, outside a job folder)
  or a job has no `DONE.md`.

### PC tools (Windows; the scripts are tested on Linux with pwsh 7 and a fake Windows, never on a real PC)
- **Storage clean** (`CLEAN_STORAGE.bat` -> `scripts/clean_storage.ps1`; table, Y, then only an allow-list: temp, browser caches, Windows update
  cache, crash dumps, NinjaTrader / bot old logs and caches; never state, accounts, `nt_bars`, NinjaTrader workspaces / db / orders; skipped folders
  while the bot or NinjaTrader runs; `engine/pc_health.py` `storage` line). Details: `docs/PC_PERFORMANCE.md`; `test_clean_storage`.
- **Status card** (`STATUS.bat` -> `scripts/pc_status.ps1`; the site `pc/` page has the download): six read-only lines (DISK, RAM, BOT, NINJA, BARS, POWER) and ONE
  `NEXT:` sentence; no Administrator. Details and the failure-sentence rule for every script: `docs/PC_PERFORMANCE.md` ("STATUS.bat and the safety review"); tests `test_pc_care`, `test_win_scripts`.
- **Fresh start** (no old PC: `FRESH_START.bat`, the one-line `irm .../pc/FRESH_START.ps1 | iex`, or `move_bot.ps1 -Fresh`): refuses while another PC's
  heartbeat is fresh, then Git / Python / clone / anchor the eval from the site / `no_chart_mode` / `ONE_TIME_SETUP` (Sim101, never live);
  `test_fresh_start`. See "One chat" above.
- **PC care** (`PC_CARE.bat` -> `scripts/pc_care.ps1`; the site `pc/` page has the download button): role auto-detect (bot folder = main PC, Surface /
  small laptop = Surface, `-Role` forces), a plain Now / After table, Y, then: a power plan "PC Care" per role (main: never sleeps, high performance,
  USB suspend off, screen off 10 min; Surface: CPU 75%, fan first, adaptive brightness off, battery saver does not dim), startup apps (Y/N each, the
  Task Manager switch), background apps, visual effects, search indexing paused 01:15-16:05 ET weekdays, and a read-only health check ending in
  `BOT PC HEALTHY: YES` (temperature only when Windows shows it, and it says so when not). `-DryRun`, `-CheckOnly`, `-Undo` (`UNDO_PC_TUNE.bat` runs it
  before the deep-tune undo). Writes `logs/pc_care.json`, which `engine/pc_health.py` shows as the display-only `pc_care` line (amber at most).
  `test_pc_care`.

### Test tools (2026-11-04)
- **Run only the area you touched:** `python -X utf8 tests/run_area.py jarvis|olympus|zenith|kalshi|cities|nq|pc|all` (one suite at a time, a load gate, `--only`, `--fast`, `--list`;
  writes `scratch/results/<area>-<time>.md`).
- **Release gate:** `python -X utf8 tests/run_gate.py` runs every suite (68 listed today) and ends GO or NO-GO; `--fast` (no browsers), `--only a,b`, `--resume`
  (skip what already passed), `--list` (names + the exact command + the fast form). Writes `research/handoff/2026-11-04/gate.md` + `gate.json`. Test of the
  gate: `test_run_gate`. A NO-GO line names the failing suite; rerun just that one before anything else.
- **Shared browser helper** (`tests/browser_kit.py`): one launch routine, waits and Locator timeouts scaled to the machine's load, `BK.limit(ms)` for timing
  asserts; use it in any new browser test instead of raw Playwright timeouts (busy shared boxes caused page crashes / 30 s timeouts before). `tests/hub_parts.py`
  and `tests/gate_static.py` are the parts the gate and the Jarvis hub test share.
- **Site self-check** (`tools/site_selfcheck.py`, a read-only workflow step, `test_site_selfcheck`): after `build_web_dashboard.py` it checks the built `site/` folder (every app folder's files, read from the build's own list) and says LOUDLY when one is missing; the step is `continue-on-error`, it never changes what is published.
- Safari: `docs/OLYMPUS_SAFARI.md`; `python -X utf8 -m tests.test_safari_smoke --lint` is the fast lint (ES5 rules, no lookbehind / `?.` / `??` in shared files).
  The real-WebKit walk of every app (iPhone 13, offline reload, back-to-Olympus, first-tap audio) is `python -X utf8 -m tests.test_safari_smoke --webkit` (needs `playwright install webkit` in a scratch dir; gate suite `safari_webkit`, SKIP when WebKit is absent).

### Wiring checklist for a new app (the lead; an agent only lists these in its report)
The app folder `tools/web_public/<id>/` (index.html, jarvis.json, manifest, icon.svg, optional `<id>core.js`) is the agent's. The lead then does, in this order:
1. `jarvis/apps.js` `BUILT_INS`: `app('<id>', 'Name', 'trading|money|life', '#accent', 'one-line purpose (5-79 characters)', { glyph: 'X' })`.
2. `olympus/olympus.js` `APPS`: `<id>: ['Name', 'glyph', '#accent']` (name, glyph, colour must equal the `apps.js` row: `test_apps_list` checks) and
   `AMBIENT`: `<id>: '<bed>'` (one of the 14 beds; `test_olympus_sfx`).
3. `tools/build_web_dashboard.py` app tuple (~line 1212, `for app in ("jarvis", "kalshi", ...)`): add `"<id>"`, or the folder is not published.
4. Root `tools/web_public/sw.js`: add `'<id>/'` to `OTHER_APPS` and bump `CACHE` (`le-public-v59` today). Pinned in tests, so update them in the same change:
   `tests/test_zenith_mode.py` (~line 66 holds the full OTHER_APPS string), `tests/test_jarvis_hub.py` (~273 prefix; the Jarvis worker name `jarvis-v24`
   and its OLD list at ~248 / ~816 only when `jarvis/sw.js` is bumped too: bump it when `apps.js` changes the shell files), `tests/test_zenith_shell.py`
   (OTHER_APPS subset, version >= 52), `tests/test_phone_e2e.py` (~1090: every app folder must be in OTHER_APPS), `tests/test_kalshi_page.py` (Kalshi
   worker `kalshi-k19` and kit / step pins, only if `kalshi/` files change).
5. `python tools/apps_list_build.py`, then `--check`; commit `olympus/apps-list.js` and `web_next/js/next/apps-list.js` (the launcher tile and its status dot
   appear on their own; the launcher tile count is read from the list, not typed in a test).
6. Shared lines: `jarvis/transitions.js` `REGISTRY` (`test_jarvis_transitions` fails without it), `olympus/intro-app.js` `FLAVOUR` + the intro script tag in the
   app's `index.html` (`test_app_intro`), the a11y tags (`a11y.css` in `<head>`, `a11y.js` after `olympus.js`; `test_olympus_a11y`), the PERF row of
   `test_olympus_kit` if the app draws a 3D scene.
7. Tests to run: `tests.test_<id>_page`, `tests.test_apps_list`, `tests.test_olympus_kit`, `tests.test_olympus_sfx`, `tests.test_jarvis_transitions`,
   `tests.test_app_intro`, `tests.test_zenith_mode`, `tests.test_jarvis_hub`, then `python -X utf8 tests/run_gate.py --fast`.
8. Update this section (the table row, the counts line) and CLAUDE.md's one OLYMPUS paragraph.

## Open work
1. **Dashboard revamp: shipped 2026-10-17** (`web_next/`, served by default; `LE_UI=classic` serves the old `web/`).
   - `web_next/` overlays `web/`: server.py serves a file from `web_next/` if it exists, else from `web/`, so every page module
     in `web/js` is shared. Overrides: `index.html` (shell), `js/app.js` (router), `js/skins.js` (Obsidian default skin),
     `css/next.css` (design system + every control), `sw.js`, `manifest.webmanifest`.
   - New code in `web_next/js/next/`: `routes.js` (Today · Chart · Trades · Data · Modules · Settings), `shell.js` (sidebar,
     phone tab bar, Data tabs, Modules grid), `controls.js` (custom dropdowns replace every `<select>`, glyphs become SVG icons),
     `icons.js`, `viz.js` (SVG charts), `trades.js`, `datahub.js` (Results, Variants, Lessons, Study), `modpages.js` (Rules,
     Cold-Streak, Risk & Sizing). API: `engine/next_api.py` (`/api/next/*`, read-only, from research/lab + research/study).
   - The Today page hero is the 3D Live Oracle (see the 3D layer below). Next: polish ideas only (per-module live badges).
2. **PC-off web dashboard (done 2026-10-17):** https://demetrades2000-coder.github.io/nq-dashboard/, a Home Screen app (PWA) in the
   same dark design. One static page `tools/web_public/index.html` (+ manifest, sw.js) reads only `data.json`, built by
   `tools/build_web_dashboard.py` on every cloud-monitor run: live state + recent bars + pools, results, every replay trade with
   its report, replays (`tools/export_replays.py` → `research/lab/replays.json`, rerun after a new export), variants, lessons,
   study trades. The scheduled run uses the workflow on the default branch, so merge changes there.
   - **3D layer (2026-10-17):** three.js source in `tools/web_public/fx/src/` (`core.js` loop + quality, `field.js` galaxy background,
     `aura.js` card glow, `taps.js` tap sparks, `orb.js` Live Oracle, `candles.js` 3D chart + replay, `galaxy.js` trade galaxy,
     `city.js` month city; 2026-10-29: `space.js` deep-space background, the default, see Infrastructure). Build with `cd tools/web_public/fx && npm install && npm run build`: it writes the one bundle
     `tools/web_public/fx.js`, copies it to `web_next/js/fx.js` and stamps its hash into both import URLs (commit all of it). Lazy-loaded after first paint; Settings has
     Max / Lite / Off; off or no WebGL2 leaves the 2D page. `fx/dev.html?view=orb|galaxy|city|candles` is a test harness;
     add `?fxfixed` to a page URL to stop the auto resolution drop in screenshots. PC side: `web_next/js/next/fx3d.js`.
3. Pine port done 2026-10-17 (see TradingView above). Open: compile check on TradingView (6 constructs listed in BRIDGE_SETUP.md), optionally read signals from NQ1! so both feeds agree.
4. Optional: test "smaller size when inducement was taken first" when more data exists.
5. **Before the Dec 2026 roll:** the live LIT window mixes the TradingView file with NinjaTrader MNQ bars. Since no_yahoo every
   merge checks the overlap (`pcbars.merge_basis`): a constant offset (a roll) back-adjusts the older bars; same contract = no
   shift. Untested on a real roll: the chart switch to MNQ 03-27 must leave an overlap (load 30 days). See `lit-report-tests.md` audit. The cloud paper ledger now freezes finished trades (`tests/test_ledger_freeze.py`).
   2026-10-26: simulated December roll (`tests/test_dec_roll.py`), reminders + red lines (`engine/roll_watch.py`); owner
   steps (3) at the top of `docs/ROLL_DEC_2026.md`.
6. **NQ signal chart** (`signal_root`, built, OFF): recommended in `research/writeups/mnq-vs-nq-feed.md`; needs the
   owner's NQ 12-26 chart with LE_BarFeed (SETUP.md 4c). Untested: NinjaTrader NQ vs TradingView NQ1! (expected ~equal,
   as NinjaTrader MNQ = TradingView MNQ1! on 95% of bars), whether the MFFU connection carries NQ data.

## The full brief (CLAUDE.md as it was on 2026-11-15, moved here word for word when the brief was cut to one page)

### NQ Liquidity Engine: brief for Claude sessions (local or cloud)

The owner trades a **MyFundedFutures (MFFU) Builder 50K** eval and is building this NQ futures bot. They are not a coder and
usually write from a phone. Reply short, plain and result-first: what changed, the numbers, what's next. Do the work instead of
asking; show evidence (backtest numbers, charts) and be honest when something doesn't work.
**Steps for the owner (2026-10-20): at most 3 numbered steps, one copy-paste line, no options or side notes; do every other
part yourself or fold it into a script.**

**Every report has a table and is SIMPLE (owner 2026-11-02 / 11-03)**: one short table (what / result), plain words, no tech detail, then at most 3 steps.
**One chat (owner 2026-11-01; "our lead chat" 2026-11-02):** he makes every change, for every project, from his one Claude Code chat on this repo, to
save time and usage. Start from the map (CLAUDE_REFERENCE "One chat"), run only the tests for the area touched, no agent
swarms unless he asks.
**This file is the short brief, loaded into every message: keep it short.** The full detail (every switch, run, result,
command and file) is in `docs/CLAUDE_REFERENCE.md`; read the section you need before touching that area, and put new detail
there, not here.

#### Hard rules (never break)
- **Futures data only:** TradingView CME `NQ1!` / `ES1!` exports in `data/` (5m 2021-11 → 2026-10-16; 1m for 2026). Never CFD,
  never Yahoo for testing. **No Yahoo live either (owner 2026-10-19, `live_model.json` `"no_yahoo": true`, `engine/pcbars.py`):**
  the PC bot trades on NinjaTrader MNQ bars (LE_BarFeed) + the TradingView exports + its own archive `data/nt_bars/`
  (gitignored); a stale NinjaTrader feed blocks new entries (FEED STALE), never a Yahoo fallback. The cloud monitor and
  watcher trade on the bars the PC pushes with its heartbeat (`heartbeat` branch: `bars_1m.csv.gz`, `bars_5m.csv.gz`); PC
  bars missing/stale -> no new paper entries ("waiting for NinjaTrader bars from the PC"). VIX/VXN from CBOE's own file.
- **No paid services.** The free PC-off path is the GitHub Actions cloud monitor (`.github/workflows/cloud-monitor.yml`); since
  no_yahoo it needs the PC's bars, so with the PC off it only waits (no paper entries).
- **Paper only.** Never arm live trading or place real orders. MFFU requires the owner to be present for live trading.
  Owner goes live on the eval himself (`docs/GO_LIVE_TONIGHT.md`); never arm it for him.
- **No secrets in the repo or chat.** `data/alerts.json`, `tv.json`, `tv_device.json`, `autostart.json`, `live_state.json`, `memory.db`
  and `.env*` are gitignored. Telegram/Discord keys live in GitHub Secrets only.
- **Frequency:** **2-4 trades a week** (owner, 2026-10-17; before: at least 2). Never make a filter that pauses trading for weeks the
  default; prefer size changes over skipping.
- **Owner requirements (2026-10-17), keep them in every report and on the dashboard:**
  - Implement what the research proves (better in 2026 AND 2021-25, 2-4 trades a week); store every experiment with its data
    (`tools/runlib.py` → `research/runs/`) and write it up in plain language (`research/writeups/`).
  - **Money, not only R:** every result shows net $ and $ per month next to PF / R.
  - **Eval speed on the MFFU 50K:** an eval should be passed or failed within **2 weeks** and never take more than **3 weeks** to
    pass. Scored as `p10/f10` (pass/fail within 10 sessions), `dec10` (% decided in 10), `p15/f15`, `slow_pass` (% of passes
    slower than 15 sessions) and `pass_med` (median sessions to pass) in every run.
  - The strategy is written in plain language in its own area of the dashboard (Strategy page, versioned, with its numbers).
- **Stops** go beyond the sweep extreme, i.e. the high/low made before the IFVG, never at a fixed distance. **Wide stop means less
  risk**: size follows the stop.
- **Owner's trading principles (2026-10-18, keep them):** the stop sits at the protected low/high (1 tick beyond the
  sweep extreme), never a random or fixed distance; a bigger stop means fewer micros (de-risk), a small stop allows more;
  one clear target (the VIX-band objective, banked at 8R), no greed; size follows the stop and the target.
- Every result is judged on 2026 **and** on 2021-25 (5 years). A change is adopted only if it holds in both and keeps 2+/week.
  Report trades/week, % weeks with 2+, PF, net, max DD, and MFFU eval pass/fail within 2 weeks and 1 month.
  **Exception for LIT changes (owner 2026-10-18):** LIT is tuned and judged on 2026 only: pick on Jan-Jun, check on Jul-Oct,
  report both halves; 2021-25 is a reference line, never a gate.
- **Prop-firm prices:** use the owner's real prices (Builder 25K $63, the ATLAS 25K of 2026-10-26 $43, Builder 50K $91.80, one-time, $0 activation), not list
  prices; look for current discount codes before quoting any firm's price.

#### The system in one screen (details: `docs/CLAUDE_REFERENCE.md`)
- **Live strategy: LIT** (locked 2026-10-18; `engine/lit.py`, params `live_model.json` "lit" = `live_model_lit.json` =
  `research/lit/lit_final.json`, plain language in `STRATEGY.md`). Sweep of a LIT level -> inducement -> displacement ->
  5m CISD -> limit 30 min, then 1m CISD; stop 1 tick beyond the sweep extreme; target 18:00 open +/- 1 VIX day move, banked
  at 8R; BE at 1R (+1.25 pts costs), 15-minute cut, flat 15:55, 1 trade/day, entries 02:00-15:30. Sizing `lit_sizing.mode`
  two_week. **Scale-in is built but OFF** until the owner's Sim roundtrip passes. Change both `live_model.json` and
  `live_model_lit.json`, then rerun `python tools/lit_losses.py live` and `python tools/model_versions.py` (commit its list too).
- **Headline (run `lit_live`, costs in):** 2026 PF 4.19, +$43,820; **quote the H2 check rate: PF 2.91, +$9,919 (~$2,670/mo)** (cisd1m 22 since 2026-10-24).
  **Uprisk (owner 2026-10-25, `uprisk.md`):** eval two_week room_f 0.4 kept past session 10 (owner "yes 40%" 2026-11-14, `eval-guard-2026-11-13.md`; was 0.8), no eval weekly stop (2-week pass/fail H2 58.6/20.9,
  was 53.7/2.2); funded 60% of room, <= $1,500, winner <= $2,000 (~$915/mo H2 to the owner, 0% lost).
- **Live loop:** `engine/lit_live.py`; PC bot `engine/live.py` (`server.py`, http://localhost:8766) routes to NinjaTrader 8
  via `engine/ninjatrader.py` (Sim by default); cloud monitor `tools/cloud_monitor.py` (GitHub Actions, every 15 min,
  paper ledger, phone pushes, publishes the `dashboard` branch and the nq-dashboard site).
- **Paper only, never routed by default:** second strategies / ATLAS / account B (`engine/second.py`, `second_model.json`),
  stop-hunt candidates, LIT Asia slot; old engine runs as a shadow ledger (`live_model_engine.json`).
- **Read-only add-ons:** Bot Brain, Trade pictures, AI watch, Performance page, Trade intel, Alerts plus, phone live feed,
  Live learning (`engine/live_learning.py`: real-fill costs, trade reviews vs the twin, Sunday weekly, suggestions;
  `lit_sizing.learn_costs` default false, on = caps priced at the learned slippage, only ever fewer micros).
  Mind (`engine/mind.py`, 2026-10-29): similar-setup memory (context only: not predictive out of sample), regime +
  trend-day odds, game plans 01:45 / 10:45 ET, trade reviews, nightly self-research proposals; never changes anything.

#### Reference index (`docs/CLAUDE_REFERENCE.md`, read before working in that area)
| Section | Read it when |
|---|---|
| Live strategy | Changing LIT rules, sizing, eval lifecycle, switches, results |
| Second strategies | ATLAS, account B, routing a second strategy, stop-hunt candidates |
| Trade pictures / AI watch | Charts of trades, anomaly / drift / loss alerts |
| Previous strategy (shadow) | The old Liquidity Engine and its eval-timing study |
| Tested and rejected | **Before proposing any new strategy idea** (don't redo without a new idea) |
| Key commands | Backtests, run library, tests, dry runs |
| Infrastructure | PC bot, cloud monitor, NinjaTrader, phone feed, TradingView, PC-off options |
| Open work | Dashboard, Pine port, the Dec 2026 roll |
| One chat | **Any change**: where each project lives, how it ships, its tests (start here) |
| OLYMPUS apps and tools | Any OLYMPUS app (folder, data it reads, test), effects, transitions, intros, Cities, Kalshi City, Jarvis bots / voice, Bridge, PC care / storage / fresh start |

#### OLYMPUS and the PCs (2026-11-10; the map is `docs/OLYMPUS_MAP.md`, generated: `python tools/olympus_map_build.py`)
- Apps are `tools/web_public/<id>/`: 61 in `jarvis/apps.js` (32 Trading, 18 Money, 11 Life); recount with `python tools/apps_list_build.py --check`; each reads only published JSON; test `tests.test_<app>_page` (+ `tests.test_olympus_kit`).
  Look: AGORA (`docs/DESIGN_AGORA.md`, no neon). **New app, the new way:** a row in `tools/new_apps.json`, then the lead runs `python tools/wire_new_apps.py --dry-run` / `--apply` (see CLAUDE_REFERENCE "OLYMPUS apps and tools").
- Money machines (paper only, read public data, write JSON): `tools/money/*.py`, `tools/money_engine.py`, `tools/money_publish.py`, `docs/MONEY_MACHINE.md`, `RUN_MONEY.bat`. Audits: `tools/phone_fit_audit.py`, `tools/make_app_icons.py`.
- Shared: effects `olympus/fx-*.js` (`test_olympus_fx`), sound beds + `OLYMPUS.sound/cue`, a11y `olympus/a11y.js`, `jarvis/transitions.js`, `olympus/intro-app.js`, Bridge `tools/bridge_*.py` (`test_bridge_page`, `test_bridge_ingest`).
- Obsidian starter vault: `python tools/obsidian_pack.py` (`mind/starter/`; `test_obsidian_pack`).
- Before a release: `python -X utf8 tests/run_gate.py` (GO / NO-GO; `--fast`, `--only`); one area: `tests/run_area.py <area>`.
- PC (Windows, scripts tested with pwsh on Linux): `PC_CARE.bat` (power plan per role + health line), `STATUS.bat` (six-line health card), `CLEAN_STORAGE.bat`, `FRESH_START.bat`; undo `UNDO_PC_TUNE.bat`; tests `test_pc_care`, `test_clean_storage`, `test_win_scripts`.
- **Agents never edit `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js` or the `olympus.js` APPS table: the lead wires them (the agent's report lists the "wiring needed") and bumps the workers.**

#### Most-used commands (run from the repo root)
- `python -X utf8 -m tests.test_lit_live`: replays every 2026 session through the live loop (must stay identical).
- `python tools/lit_losses.py live`: rebuilds run `lit_live` after a switch change.
- `python tools/export_backtest.py`: the live-settings replay -> `research/lab/backtest_live.json`.
- `python -m engine.ninjatrader --selftest`: NinjaTrader route self-test.
- `python tools/cloud_monitor.py --out <tmpdir>`: dry run of the PC-off monitor.
- **Ship to the PC (2026-11-14):** push the tested release to the backup repo `dcondax1-wq/olympus` branch `pc` (add_repo with push first); the PC installs it by itself when flat (`docs/AUTO_UPDATE.md`).
