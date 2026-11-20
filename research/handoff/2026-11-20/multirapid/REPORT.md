# Two Rapid EOD accounts at once (branch day-multirapid, 2026-11-20)

## For the owner

| What | Result |
|---|---|
| Why | The 5th MFFU slot = a Rapid EOD 50K next to today's Rapid 25K; the bot could run only ONE Rapid (a 2nd was refused) |
| Now | Two Rapids side by side, each with LIT + ATLAS, its own money, day stop, sizing, orders and alert name |
| Today's Rapid 25K | Unchanged: same file, same ids, same order tag, same alerts (proved against a frozen copy of today's code) |
| The 2nd Rapid | OFF until you add it in /add-account/ and type I ACCEPT LIVE RISK |
| Live now? | No. Nothing merges until the lead reviews it and a red team checks it |

On the day you buy the 50K (after the lead says it is merged): /add-account/ -> Rapid EOD 50K -> tap the Name -> type
`I ACCEPT LIVE RISK` -> Add + start trading. The [OK] line says "(Rapid #2)".

## What changed (19 files, all on this branch only)

Design: slot 1 = today's Rapid, untouched; slot 2 = a NEW file and NEW ids. Nothing moves, so there is no migration to go
wrong, and an older bot simply never looks at the new file.

| | Slot 1 (today) | Slot 2 (new) |
|---|---|---|
| Settings file | data/rapid.json | data/rapid2.json |
| LIT lane id (accounts state, alerts key) | rapid | rapid2 (+ "slot": "rapid2" in its lane entry) |
| ATLAS lane object | LiveBot.acct_r | LiveBot.acct_r2 |
| ATLAS state file | data/live_state_acctr.json | data/live_state_acctr2.json |
| NinjaTrader order-file tag / NT state / OIF log | acctr_ / ninjatrader_state_acctr.json / ninjatrader_oif_acctr.log | acctr2_ / ..._acctr2.json / ..._acctr2.log |
| ATLAS alert key suffix | :acctr | :r2:acctr (still ends ":acctr" so notify labels it "(ATLAS)") |
| Lifecycle key (pass / fail / lock stand-down) | rapid | rapid2 |
| Trades feed / PC report key | rapid25, named by size | rapid2, named by size ("Rapid 50K"; "#2" only if both are the same size) |
| CLI | `python -m engine.rapid ...` | `python -m engine.rapid --slot 2 ...` |

Files:
- engine/rapid.py: SLOTS, slot_path / slot_of / read_all / free_slot; lane_spec(slot=, dup=), RapidAtlas(slot=) (own lane, tag,
  state, alert key), _state_path(slot), build_atlas(slot=), status(slot=), CLI --slot.
- engine/live.py: acct_r2 + _rapid_atlases(); _rapid_block2 (refuses the 1st Rapid's Name); _start_accounts adds lane rapid2;
  _start_rapid starts both; kill / flatten / adapter tick / tick / no-hedge check / LIT's hedge-close loop over both;
  stop() releases both NinjaTrader locks.
- engine/multi_account.py: normalize keeps "slot"; shared() = the lane's own ATLAS; others_opposite also checks acct_r2.
- engine/account_b.py (ATLAS 25K's no-hedge check sees acct_r2), engine/autoupdate.py (no update while the 2nd Rapid holds a
  position / bracket), engine/phone_safety.py (counts it open), engine/lifecycle.py (key rapid2, its own facts),
  engine/launch_check.py (START BOT line per Rapid), engine/brain_glance.py (Brain card per Rapid).
- engine/account_cli.py: a 2nd Rapid goes to slot 2 (a 3rd refused; never the same Name twice; a funded add finds the eval of
  the same plan); inventory lists both (ids rapid / rapid2); remove turns off the right slot; arm(phrase) also arms slot 2
  (START BOT's step_arm and the add box's "Start trading" both call it). The add box (engine/account_box.py) needed no change.
- tools/live_trades.py (key rapid2), tools/pc_report.py (Rapid named by size), tools/rehearse_day.py (--rapid2).
- Tests: tests/test_multi_rapid.py (new, 41/41), tests/fixtures/rapid_slot1_baseline.json (frozen output of today's code),
  tests/test_rapid_launch.py (from day-rapid), test_rapid25 / test_accounts_cli / test_account_box: "a 2nd Rapid is refused"
  became "a 2nd = Rapid #2, a 3rd is refused".

## Why it is safe

1. Slot 1 byte-for-byte: test_multi_rapid a compares today's lane entry, ATLAS block, state path, alert suffix and file path
   with the frozen output of the code BEFORE this change (tests/fixtures/rapid_slot1_baseline.json, made from origin/pc
   83287299): all equal. test_rapid 60/60 and test_rapid25 95/95 (all old checks) still pass.
2. No 2nd Rapid file = the old bot: acct_r2 None, one lane "rapid" (test_multi_rapid e). Every new loop runs over [acct_r]
   then, the same calls in the same order.
3. No cross-talk (test_multi_rapid c + replay): each lane's same-account partner is its own ATLAS; a -$400 day on the 25K
   leaves the 50K's day and size untouched; ATLAS on one Rapid never blocks LIT on the other account, but MFFU's no-hedge
   rule across accounts still holds (a SHORT anywhere waits while either Rapid's ATLAS is LONG).
4. Restart mid-day: closes come back on their own Rapid (25K -$400; 50K +$120 / -$80) - test e; replay restarts on
   10-02 and 10-13 with both Rapids.
5. Arming: added DISARMED; a wrong phrase arms nothing; only the typed phrase arms slot 2 (test g).
6. Auto-update / phone flatten / KILL see the 2nd Rapid's position (autoupdate, phone_safety, live.kill/flatten).

## Tests run (this branch)

| Check | Result |
|---|---|
| tests.test_multi_rapid (new) | 41/41 (incl. LIT's hedge close asking both Rapids in one poll) |
| `python -X utf8 -m tests.test_lit_live --quick` | OK (302 polls, entries 1/1, exits 1/1, 0 errors) |
| `python -m engine.ninjatrader --selftest` | PASS 79/79 |
| test_rapid25 / test_rapid_launch / test_rapid | 95/95 / 11/11 / 60/60 |
| test_accounts_cli / test_account_box / test_onboard / test_multi_account | 40/40 / 41/41 / 27/27 / 55/55 |
| test_trade_alerts / test_cross_hedge / test_lifecycle | 21/21 / 13/13 / 30/30 |
| pc area (52 suites, win_scripts never run) | 51/52 (account_box 41/41 after its 2nd-Rapid check was updated); obsidian_brain g fails the same on origin/pc (vault/ rebuild, not this branch) |
| test_brain | 37/38, the same check fails on origin/pc (LIT day-end vs backtest on 7 recent sessions: data, not this branch) |
| smoke | 7/8 (zenith_mode needs Playwright for Python, not installed here) |
| Replay: tools/rehearse_day.py --rapid2 --quick (5 real days + 4 scenarios, simulated NinjaTrader) | 187/187 on the final code (both Rapids: each on its own Name, own tags / state files, one position per account, never long + short across accounts, flat by the close, days under the 30% cap and the soft day, own lifecycle rows; restarts mid-trade 10-02 / 10-13, KILL, FLATTEN, slow-close, 50K passed) |

## How to roll back

- Turn the 2nd Rapid off without code: `python -X utf8 -m engine.rapid --slot 2 --off` (or remove it: `python -X utf8 -m
  engine.accounts remove --name "<Name>"`), then STOP BOT + START BOT.
- Roll the code back: check out the previous pc commit. data/rapid.json was never rewritten by this code (test f), so the
  old bot reads the 1st Rapid exactly as before; data/rapid2.json and *_acctr2.json are ignored by it (delete nothing).
  A 2nd Rapid's open position must be closed by hand first (the old bot does not know it).

## For the lead (not done here)

- run_area: add "multi_rapid" (and "rapid_launch") to the "fleet" list (tests infra = day-quality).
- tools/web_public/trading/tradingcore.js (day-nqdash3): ACCTS gets `rapid2: { name: 'Rapid #2', bot: null, ids: ['rapid2', 'acctr2'] }`
  and its startsWith('rapid') rule skips 'rapid2' (same as tools/live_trades.py), else the trading page files the 2nd Rapid's
  trades under the 1st.
- accounts.json (Board): a row "Rapid EOD 50K" with pc id "rapid2" once bought (board_events.key_of keeps "rapid2").
- Red team focus: live.py _hedge_clear loop (returns on the first Rapid that is not flat), multi_account.others_opposite,
  account_cli._add_rapid funded path with two Rapids of different plans.
