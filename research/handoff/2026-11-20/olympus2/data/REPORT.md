# DATA TRUTH (day-nqdash3, Olympus 2, 2026-11-20)
| What | Result |
|---|---|
| Truth checker | `tools/truth_check.py`: the PC's 15-minute post = the truth per account (balance, room, to pass, to payout via the payout coach, today, last trade, age). It checks the published feeds against it (home.json, data.json, trades.json, payday, fleet_plan, brief, edge, k8, decisions, news_week, accounts.json), flags ages past their limit and planned accounts the PC does not list. `--pages` scans every visible app at 390 px for a wrong balance / room / to payout, DEMO while real data exists, and missing accounts. Report: TRUTH.md. Test: tests/test_truth_check.py 11/11 (offline fixtures of today's feeds) |
| ATLAS +$514 (balance $25,401, room $1,401) | Right on NQ (accounts strip, thinking, GO/WAIT/HALT), Trading (strip, payout readiness), Board (tiles now show Today and To payout), Glance balance / today / room. Wrong only on Glance "TO PAYOUT $1,449" (ASK 1) |
| One "to payout" | $949 = the payout coach's need_more (pc_feed.js payoutLines). Strip, Board tile, tracker headline and ZEUS all use it now; the tracker shows the plan's $1,000 ask ($1,699 more) on its own line |
| Data age | `age.js` + `age.css`: "updated 4 min ago", ONE set of limits (PC 20 min / 1 h, candles 80 min / 3 h, nightly 26 h / 3 days). On Board, the NQ accounts strip, GO/WAIT/HALT and quality. Other slices: ASK 4 |
| Board truth fixes | Without the PC post Board said ATLAS "PASSED · locked · To pass done" from the Nov 17 note. Now the plan's newer "funded" wins, and old numbers carry a red "updated 3 days ago". 2-column numbers (no "$49,19/3" wrap). Event notes older than 2 days leave the tile (still in the feed) |
| Asks (ASKS.md) | Glance to payout -> day-cities3; Helios grove draws the cloud paper twin -> day-arenas; home.json build puts the twin under the real 50K id -> lead; age.js adoption -> all |
| Tests | truth_check 11/11, board 59/59, nq_page 70/70, trading_page 71/71, nq_chart 44/44, nq_desk 32/32, payready 16/16, trading_merged 6/6, alert_audit 18/18 |
| Screens | nq_accounts_live_dark/light, trading_payready_live_dark/light, board_live_dark/light, board_nofeed_dark (live feed of 10:50 ET) |
Not changed: no bot or engine file, no alert-sending code, no lead-only file, no other slice's folder.
