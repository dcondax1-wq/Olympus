# NQ Live screen (day-livedash 2026-11-26)

Owner: "I want to see live trades on the dashboard, where we're at." One screen inside the NQ app: `tools/web_public/nq/live.html`
(no new app). Phone 390x844 first, OLYMPUS NIGHT. Read only.

## What it shows (top to bottom)
1. **PC + bots in plain words**: PC age chip (green <= 20 min, gold <= 60, red), the verdict, each bot "ON, armed (LIVE)" / "ON, NOT armed" / "OFF"
   (ck.pl when the PC sends it, else the glance), ck.need, server / NinjaTrader down, problems.
2. **Open trade card** (only when one is open; pulses gold, border mint / red by sign): side, size, bot, which accounts (with their micros),
   live unrealized $ and R from the NEWEST price (report price / glance px / last chart close, whichever is newest, with its age), entry /
   stop (BE) / target, points to stop / target, $ at risk, time in trade, and a mini SVG chart (the PC's le-bars candles via nqbars.js) with
   TP / SL / IN / NOW lines. Sources merged per account + entry time: ext `at` rows (exit_t null), `board.<bot>.position`, `board.trades` open,
   the chart post's `open` rows. MNQ $2 a point.
3. **Accounts** (2x2 tiles, from acctcore.js = the Accounts screen's own rules): ARMED / ON / OFF / IN TRADE, today $, balance (funded = MFFU
   profit from $0), room left bar, to pass / to payout bar, report age chip, the open $ of that account while in a trade.
4. **Setup progress**: each bot's step N/10 (LIT) or N/5 (ATLAS lobes) with the waiting-for text, distance in points, window and an age chip.
   `bf` (Brain feed) wins when present, else the glance (stage "(4/10)", arm trigger, ax limit distance, lv nearest level).
5. **Today's trades** (CME day) with $ and R, open ones marked, and **this week / month per account** (week = the PC's `accounts[].pnl.week`
   when non-zero, else the closed trades in the report; month = the closed trades in the report, "≥" when the 4-row `at` window may hide more).

Polls `fetchLatest` every **22 s** (pc_feed shares one answer for 20 s, so 20 s would often reuse it) and the chart post every 60 s, only
while visible; refreshes on return to the tab.

## Files
- new: `nq/live.html`, `nq/live.js`, `nq/livecore.js` (pure, node-tested), `nq/live.css`, `tests/test_nq_live.py` (33 checks: static, node
  on the REAL 2026-11-22 post in `tests/fixtures/nq_live/` + built trade / bf / stale posts, Playwright 390x844 with a real `pack_bars` post).
- edited: `nq/index.html` (a "Live" first button in the tags row + a "LIVE NOW" door under the status line; perf static still 0 over budget),
  `gate/index.html` ("Live trades: where we're at" button in the Right-now card, `#liveBtn`), `tests/run_area.py` (nq area += nq_live).
- shots: `shots/live-390-trade.png`, `live-390-trade-full.png`, `live-390-flat.png`, `live-390-flat-full.png`, `live-390-stale.png`.

## LEAD WIRES
1. `nq/sw.js` (and the site `sw.js` if it precaches nq): add `live.html`, `live.js?v=1`, `livecore.js?v=1`, `live.css?v=1` to the shell; bump
   the cache name (nq/index.html changed too; gate/index.html changed).
2. Optional, to make it the NQ app's literal first screen: the `olympus.js` APPS table / `jarvis/apps.js` row for `nq` -> `nq/live.html`
   (the NQ dashboard stays one tap away: "‹ NQ" + footer link). Without it the NQ dashboard opens with the big LIVE NOW door at the top.
3. `docs/OLYMPUS_MAP.md` NQ row: add `live.html` (and `tests.test_nq_live`).

## Notes
- Pre-existing, not mine: `tests.test_gate_page` 87/91 on pc HEAD before and after this change (4 tap-size fails: 'k 64x22', 'A 64x22' ...).
- The War Room (`../warroom/`) already shows bots step by step; this screen is the money view (accounts + the open trade + today's $).
- If a PC sends neither `at` nor a position, the card cannot know a trade is open: the screen then says "Flat right now" with the report's age.
