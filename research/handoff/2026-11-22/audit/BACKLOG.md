# Night audit backlog (2026-11-22, workflow ops-audit-night, 27 verified findings)

BUILD BACKLOG FOR TONIGHT (ranked: owner money/risk first, then manual steps removed, then clarity)

Merged duplicates: "role_of skips Rapid" was reported twice (run#4 and accounts#2), and so was "launch checklist == 12" (run#3 and clean#2). Each is counted once below.

Ship plan:
- Package E (site/docs) and Package D (pc-scripts plus test-only fixes) can ship tonight with `python tools/ship.py`.
- Packages A, B and C (bot-code) are built and tested tonight on night-* branches, but are not pushed to pc. They land after review, after hours: bot flat, after the 15:30 ET close, through the land-helper skill.

====================================================================
PACKAGE A: "Start never stops Zlarior; one account, one route"
Zone: bot-code (engine/go.py owner; one builder, because every change is in go.py)
Rank 1. Zlarior's 50K is stopped whenever ATLAS fails to arm, and the same account could be routed twice (double size).

Findings included:
1. If ATLAS's 25K fails to arm, the check after the start stops the whole bot, Zlarior's 50K included (the Re-arm loop).
2. go.role_of ignores data/rapid.json / rapid2.json. This gives a ghost 'New account ... Pick one', and the Rapid's Name can be given to ATLAS or an extra (merged with the "Start page offers New account for the Rapid" finding).
3. The eval-to-funded switch (go.to_funded, onboard 'Move Zlarior here (funded)') writes an untagged row that START never arms or reports.
4. Start page 'Accounts > Add' (go.add_account extra branch) bypasses the account_cli.add checks and writes an untagged row.
5. Stretch: the Start page Accounts panel has no Rapid rows, and go.remove_account cannot remove the Rapid.

Files:
- /home/user/wt-web/engine/go.py:
  - verify_routes ~205-208: hard/soft split.
  - step_arm ~868-872, resume_now ~1325-1332, resume_problem ~1255-1257, step_auto opt-in ~1490: use only the hard list, and end the retry_s=60 loop on soft.
  - role_of ~1069-1085: add the Rapid branch, using rapid.SLOTS / rapid.read(rapid.slot_path(sl)). Do not use account_cli.inventory, which is circular.
  - set_names: refuse a Rapid Name.
  - to_funded ~1771: after rc==0, find the row by nt_account == funded_name and setdefault 'cli' {by: account_cli.TAG, plan, bots:'lit', added}. Fix the "joins at the next start" text.
  - add_account extra branch ~1652-1663: send it to account_cli.add(plan, name, start=start), and refuse while bot_running().
  - Stretch: accounts() ~1552-1603 Rapid rows, and the remove_account Rapid branch to account_cli.remove.
- /home/user/wt-web/engine/new_accounts.py: notices() push text only ('Open the Start page and tap the right button').
- /home/user/wt-web/tests/test_arm_rt.py (236-239) and /home/user/wt-web/tests/test_go.py (244): update the tests that lock in stop-on-unarmed-ATLAS.

Acceptance tests (write and run):
- test_go, verify_routes soft:
  - ATLAS armed=False with Zlarior correct gives no hard problems and one soft 'ATLAS NOT armed'. step_arm does not call ninjatrader --stop (monkeypatched), and prints 'Running Zlarior; ATLAS NOT armed: <why>'.
  - Hard cases still stop: Zlarior on the wrong Name, the 25K listed as an extra, ATLAS armed on a non-25K Name.
- test_go, role_of: with a temp rapid.json {account:'MFFUEVRPD123'}, role_of returns 'the Rapid EOD'. new_accounts.candidates excludes it, and set_names refuses it.
- test_go, to_funded: go.to_funded(lit, 'MFFUSF...', day) then account_cli.arm(LIVE_PHRASE) gives 'Added accounts armed: ...' containing that Name.
- test_go, add_account extra: the extra branch writes a row with 'cli', and rejects a Name that breaks name_problem / limit_problem.

Run:
- python tests/smoke.py
- python -X utf8 -m tests.test_go
- python tests/run_area.py pc (covers arm_rt, arm_report, ready)
- python tests/run_area.py fleet (onboard, rapid, accounts_cli)
- python -X utf8 -m tests.test_new_accounts
- python -X utf8 -m tests.test_lit_live

Risk notes:
- This is the live start path. It must never arm anything new by itself. The soft path only stops stopping Zlarior.
- An unarmed ATLAS is still refused by _live_gate, so no order risk is added.
- The role_of Rapid branch must be wrapped in try/except so that a broken rapid.json cannot crash START.
- After-hours landing only, with the bot flat.

====================================================================
PACKAGE B: "Every critical alarm reaches the phone"
Zone: bot-code (notify chain)
Rank 2. Kill switch, no-stop, clock block, room < $400 and NOT READY are all silently dropped today.

Findings included:
1. Every critical PC alarm (Entry blocked, clock drift, kill switch, no-stop mismatch, room < $400) is dropped before it reaches any phone.
2. New readiness guard: NOT READY alerts reach nobody unless Telegram/Discord is set up, and are then marked as told.
3. A clock-drift block is labelled 'Held back by a rule' and arrives with no sound at night.
4. Without Telegram, the 2-minute fast alarm (bot down, feed stale, open at the half-day halt, no stop) has no Web Push fallback.
5. Also in this package: readiness.py:380 'Sync now' changes to the FIX_CLOCK.bat literal. This builder owns readiness.py.

Files:
- /home/user/wt-web/engine/push.py:
  - Add CRITICAL_KINDS = ('clock','kill','unprotected','eval_floor','freeze','feed_stale','ops_crit').
  - pc_app_ok ~1136-1150 passes these kinds and tag 'le-guard'. Not 'update', not 'hedge'.
  - In the _pc_send non-trade branch ~1296-1305 and in pc_send_now, also call notify.instant_problem.
- /home/user/wt-web/engine/readiness.py:
  - send_alert 645-663: instant_problem plus a report_payload kind 'problems'. Return 'none' when neither is delivered.
  - tick(): when nothing is delivered, roll back st['sent'] and last_alert.
  - Line 380 text.
- /home/user/wt-web/engine/alert_bus.py: send(wait=True) ~656-658 returns 'failed' when r['ok'] is false. Audit every caller that compares against 'sent'.
- /home/user/wt-web/engine/fill_audit.py ~842: add 'PC clock' and 'internet time' to LOUD_HOLDS. Do not use bare 'clock'.
- /home/user/wt-web/engine/notify.py, instant_problem old path 964-970:
  - When there is no topic or ntfy refuses, fall back to push.pc_send_now(push.report_payload(...)), with push imported inside the function.
  - On sent>0, call _record_problem(count=False) and return 'sent (app)'.
- Tests: /home/user/wt-web/tests/test_push.py, test_notify.py, test_ready.py (line 66 expectation), test_alert_bus.py, test_fill_audit.py.

Acceptance tests:
- pc_app_ok is True for a guards payload (tag le-guard) and for alerts_plus kill / unprotected / eval_floor crit payloads, and False for 'armed' and 'update'.
- pc_send_now of a kill crit gives sent>0 with a fake Web Push sender (no network).
- readiness.send_alert with no Telegram/Discord returns 'push' only when the fake delivery succeeds. When delivery fails, the next tick re-sends (sent entry rolled back).
- alert_bus.send(wait=True) with r['ok']=False returns 'failed'.
- fill_audit.rule_hold('...NOT routed: GUARD PC clock 24.5 s behind internet time (max 5 s)') is False, and the _missed_problem title starts with 'MISSED TRADE' with soft False.
- notify.instant_problem with no topic falls back to the app and returns 'sent (app)'. The report's problem_dup then skips its copy.

Run:
- python tests/smoke.py
- python tests/run_area.py pc (notify, ready, ready_rt)
- python -X utf8 -m tests.test_push
- python -X utf8 -m tests.test_alert_bus
- python -X utf8 -m tests.test_fill_audit
- python tests/run_area.py nq (keepalive, guards)

Risk notes:
- Spam risk: keep the alerts_plus repeat cap (6) and one guard key per entry. Leave 'update' out.
- Import cycles: push and notify must stay lazily imported inside functions.
- No new services and no secrets.
- Alarms only, no order path, but it is still bot-code, so it lands after hours.

====================================================================
PACKAGE C: "Clock fixes itself; the phone tells the truth about armed"
Zone: bot-code (guards / live_board / brain_glance)
Rank 3. A clock drift blocks every entry for up to about an hour. The phone says 'armed, live' while the live gate refused.

Findings included:
1. A clock drift blocks every entry, the bot only pushes 'Settings > Time > Sync now', and it waits 15 minutes before checking again.
2. The 'entries blocked' clock push and the live board still say 'Sync now' (guards.py:852, live_board.py:58; readiness.py:380 is in Package B).
3. Zlarior (and Rapid) show ARMED on the phone when the live gate refused them.
4. Stretch: Zlarior 25K #2 (b25k_2) has no Brain glance row. Backend only here; the braincore.js half is in Package E.

Files:
- /home/user/wt-web/engine/guards.py:
  - clock_tick ~328: every = 20 if bad==1, 60 if bad>=2, else clock_every_s.
  - Guard tick ~848-852: on Windows, with the bot flat and sync_t older than 300 s, run go.sync_clock() (lazy import) in a daemon thread. On success set _CLOCK['t']=0 and bad=1.
  - Send the push after the result ('synced by itself' / 'could not sync: double-click FIX_CLOCK.bat once, right-click > Run as administrator').
- /home/user/wt-web/engine/live_board.py:58: text literal.
- /home/user/wt-web/engine/brain_glance.py:
  - lit() ~156-162: armed = armed and enabled is not False and not disabled. Set nar = 'NOT armed: ' + disabled[:90].
  - rapid() ~330: the same rule.
  - Stretch: generalise rapid() into extra() for b25k_2 and other extras, skipping blitz/acct_c.
- Tests: /home/user/wt-web/tests/test_guards.py, test_live_board.py (113, 172-173, 204, 386), test_brain.py (or a new test_brain_glance.py), test_clockfix.py.

Acceptance tests:
- guards with a fake probe (+25 s) and a fake sync_clock:
  - Sync is attempted once, and only when flat. It is never attempted while a position is open.
  - After a successful sync, a 20 s re-probe clears the block.
  - The push text contains 'synced by itself', or 'FIX_CLOCK.bat' on failure.
  - No second sync attempt within 300 s.
- clock_tick with bad>=2 re-probes at 60 s.
- brain_glance.build({'health':{'account':{'armed':True,'enabled':False,'disabled':'confirm phrase missing'}},'running':True}) gives lit armed False and nar 'NOT armed: confirm phrase missing'. Rapid follows the same rule.
- No 'Sync now' left in guards.py, live_board.py or readiness.py (grep test).

Run:
- python tests/smoke.py
- python tests/run_area.py nq (guards, live_board, heartbeat)
- python -X utf8 -m tests.test_clockfix
- python -X utf8 -m tests.test_brain
- python -X utf8 -m tests.test_lit_live

Risk notes:
- The auto-sync must only run when flat and on Windows, in a daemon thread so the guard tick never blocks.
- If sync_clock needs admin rights it will fail quietly; the push then names FIX_CLOCK.bat.
- Leave accounts.py alone (other readers want the config flag).
- After-hours landing.

====================================================================
PACKAGE D: "Fresher phone numbers, honest self-test, every PC suite in a test area"
Zone: pc-scripts plus test-only files. Ships tonight via ship.py: PC auto-update, self-test gated.
Rank 4. The phone lags up to 44 min on armed state, which caused part of the re-arm loop, and the weekly false red self-test hides real reds.

Findings included:
1. The Brain page's armed / on / room / today block can be 44 minutes old (core 'ar' key plus ext_hash fields).
2. Trading Home 'Every account armed', pc_report half: full() keeps 'enabled' / 'locked' (and 'armed') on account rows.
3. Public post is built from the 5-minute heartbeat file, not the bot's 15-second live.json.
4. PC self-test 'Launch checklist' fails on the real PC because the test expects exactly 12 lines (both copies).
5. land-fixes breaks the PC self-test 'ops' (test_ops still expects 'Sync now').
6. 14 PC self-test suites are in no run_area area, so cloud landings never run them.
7. ATLAS funded balance shown as $25,401 (board.py half: display-only conversion).
8. Stale-data board notes for GEX_1d / CBOE_vol_1d have no reason (data_health WHY plus the generated_files comment only; the gamma.py atomic write waits for bot-code).

Files:
- /home/user/wt-web/tools/pc_report.py:
  - split() ~819-821: core['ar'] = {id: [on, armed]}, and add 'ar' to CORE_KEYS.
  - ext_hash ~916: add [[id, on, armed, nar]] only.
  - full() ~648-652: enabled / locked / armed.
  - gather() ~455-486: fetch 127.0.0.1:{port}/api/site/live.json when server is up, kind 'le-live', and t > hb_t. Set snap['live'] / live_t, and out['t'] = live_t or hb_t. Never touch hb_t or hb_age.
- /home/user/wt-web/tools/board.py ~248: print-time only, funded balance minus start, plus 'payout +$X'. Do not store the shifted balance.
- /home/user/wt-web/tools/data_health.py ~29: WHY for GEX and CBOE.
- /home/user/wt-web/engine/generated_files.py:30: comment only.
- /home/user/wt-web/tests/test_launch_checklist.py:205-211:
  - Point rapid.PATH / PATH2 and the launch_check c_root at a tmp folder, restored in try/finally.
  - Assert the 12 base keys are a subset of the item keys, plus the count-tolerant n = 12 + optional facts.
- /home/user/wt-web/tests/test_ops.py:159-161: 'FIX_CLOCK.bat'.
- /home/user/wt-web/tests/run_area.py: AREAS["pc"] += ["start_api","launch_checklist","nt_outgoing","nt_exec_audit","selfheal","ops","run_switch","new_accounts","go","nt_roll_guard","broker_balance","eval_fix","fsutil","account_rename"]. Optionally add a check that every pc_selftest.SUITES tests.test_* module sits in some area.
- Tests: /home/user/wt-web/tests/test_pc_report*.py (add a fake-http live.json case) and test_board.py.

Acceptance tests:
- pc_report: a fake http returning a newer le-live live.json makes out['t'] equal its t, with hb_age unchanged. A fake http returning 500, a wrong kind or an older t falls back to the heartbeat.
- core 'ar' is present, and ext_hash does not change when only non-armed glance fields change.
- full() rows carry enabled and locked.
- test_launch_checklist passes with a fake rapid.json, rapid2.json and account_c.json in the real data/ (simulate in tmp).
- run_area pc lists all 14 modules, and each passes here.
- board.py read prints ATLAS funded as '$401 ... payout +$X' from a $25,401 fixture, while the stored row keeps 25,401.

Run:
- python tests/smoke.py
- python tests/run_area.py pc (now includes go, ops, launch_checklist)
- python tests/run_area.py board
- python -X utf8 -m tests.test_ops

Risk notes:
- The test_ops change expects the land-fixes text ('FIX_CLOCK.bat'). Ship it in the same push as land-fixes, or after it, never before. Otherwise the PC update gate sees a fresh regression and holds the update back.
- Adding 14 suites to the pc area makes ship.py slower, and any suite that is already red will block shipping. Run each once first and list the reds rather than skipping them.
- pc_report runs on the PC. The localhost fetch needs a 4 s timeout and a full try/except fallback.
- 'ar' carries the old armed rule until Package C lands. That is acceptable, and it is no worse than today.
- No sw.js and no build_web_dashboard.py edits by the helper.

====================================================================
PACKAGE E: "Phone pages show the right accounts and the right $"
Zone: site/docs. Ships tonight; the lead bumps the sw.js cache.
Rank 5. A false green 'every account armed' and two different balances for ATLAS.

Findings included:
1. Trading Home 'Every account armed' skips ATLAS and treats a real-account badge as armed (site half).
2. ATLAS funded balance shown as $25,401 on the Business Accounts page (site half).
3. Brain page reads armed / on from the new core 'ar' when present, and shows b25k_2 / Rapid armed from glance rows when present (site half of the 44-min and b25k_2 findings).
4. CLAUDE.md tells sessions to `git push origin HEAD:pc`, but origin here is the forbidden old repo. docs/AUTO_UPDATE.md:26 by the helper; the CLAUDE.md line by the lead only.

Files:
- /home/user/wt-web/tools/web_public/nq/trading_home_core.js ~106-108:
  - realAccounts() adds a synthetic ATLAS row from lite.board.atlas when no row matches /atlas|acct_b/.
  - Held when enabled===false, locked, badge !== 'LIVE', or lite.ar says armed 0.
- /home/user/wt-web/tools/web_public/business/accounts.js ~79: when stage is funded and PC_FEED.mffuView is available, show 'Balance (MFFU, from $0)' and 'To the max payout'. Fall back to the raw balance.
- /home/user/wt-web/tools/web_public/nq/braincore.js ~189, 192, 217: prefer lite.ar[bot], and attach armed / on to the fresh25 / rapid1 accounts[] entries through the nq.js EQ_IDS map. Tolerant when 'ar' is missing.
- /home/user/wt-web/docs/AUTO_UPDATE.md:26.
- /home/user/wt-web/tests/test_trading_home.py ~185: replace the fake 'atlas' row with a real-shaped post, and add a board.atlas-only case.

Acceptance tests:
- test_trading_home: a real-shaped post with no atlas row plus board.atlas gives ATLAS listed. With ATLAS enabled:false, the check says held, not '2 account(s) armed'. With lite.ar {lit:[1,0]}, Zlarior is held.
- A Business Accounts fixture with ATLAS funded at $25,401 shows $401 and the payout need, using mffuView. With PC_FEED missing it shows the raw value.
- braincore: with 'ar' present, armed comes from 'ar'. With 'ar' absent, it behaves as today.

Run:
- python tests/smoke.py
- python tests/run_area.py pc (trading_home)
- python tests/run_area.py money (business_pages)
- python tests/run_area.py <brain area> --changed <base> (the browser suites only, since screens changed)

Risk notes:
- Display only, no trading effect.
- It must work with tonight's post shape, which has no 'ar' yet and no enabled / locked yet, so every new field is optional.
- The helper must not touch sw.js, build_web_dashboard.py, jarvis/apps.js or the olympus.js APPS table; the lead wires and bumps the cache.
- Do not commit any real account Names or ids in fixtures.

====================================================================
DEFERRED (next night; listed so nothing is lost)
- START prints ARMED for the Rapid / added accounts even when NinjaTrader no longer lists the Name. Bot-code, go.py _step_arm. Do it after Package A lands, since it is the same file.
- Funded Rapid tap ignores which eval passed, and RP codes are always a guess (engine/onboard.py offers/do/parse_name). Bot-code, fleet area.
- gamma.py writes the GEX download non-atomically (tmp + check for b'date' + os.replace). Bot-code, small.
- Cloud 'PC silent' alarm goes to the public topic (tools/alerts_setup.py gh path plus a one-line instruction; effort M-L, no PyNaCl). For now it becomes an owner step.

====================================================================
TELL THE OWNER (max 3 lines)
1. Tonight the phone pages and the PC report get fixed (truer armed state, ATLAS shown as $401, fresher numbers). The bot fixes (Zlarior keeps trading when ATLAS fails, critical alarms buzz the phone, clock drift fixes itself) land after the close, once tested.
2. Until those land: if you see 'clock drift', double-click FIX_CLOCK.bat as administrator on the PC. If ATLAS will not arm, START may still stop Zlarior, so re-type the phrase once and check the PC screen, not the phone.
3. Hands-only step (STATE 'Waiting on the owner'): to get the 'PC went silent' alarm on your phone, add the GitHub secrets LE_TG_TOKEN and LE_TG_CHAT (or LE_NTFY_TOPIC) under Olympus > Settings > Secrets > Actions.
