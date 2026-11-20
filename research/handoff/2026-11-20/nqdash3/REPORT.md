# nqdash3 report (NQ dashboards round 3 + the trade-alert audit), branch day-nqdash3

| What | Result |
|---|---|
| 1. Accounts strip (NQ + Trading pages) | Every MFFU account in the owner's order: Zlarior 50K, ATLAS 25K funded, Zlarior 25K #2, Rapid EOD 25K (dashed "planned" dot until the PC lists it; any new PC account appears on its own). Balance, today's $, room left (with a bar), To pass, or To payout for the funded one, and a live / stale dot from the PC's 15-minute report |
| 2. What the bots are thinking (NQ page) | Per bot: Before (lean = the side of the setup it has armed, today's high-impact news + the next one, key levels with distance, its window, what it waits for, last decision), In (entry, stop, target, $ now, R so far, minutes in trade), After (today's $ and R, how it closed, the replay link or "replay after tonight's upload"). 1-2-3 step bar shows where it is |
| 4. Quality checks card (NQ page) | PC report age, bot heartbeat age, site data age, last trade alert, PC vs backtest twin (match / differ / no twin), news calendar coverage; ✓ / ! / × each |
| 3. Alert audit | Every route (Zlarior 50K, 25K #2, ATLAS funded, Rapid LIT + ATLAS lanes, ATLAS on the 50K) sends exactly 1 entry + 1 close over **both** web push and ntfy (ntfy stays quiet when the phone app took it), with account, side and $. **Gap: no close push shows R today, on any route.** 3 small patches in LEAD_WIRES A, proven in memory: 15/15 |
| 5. Trading test vs a fresh trades.json | The 5 pinned checks now read a fixture copy (tests/fixtures/trading/trades_pinned.json); the real file gets shape checks. Fresh trades.json committed (303 trades). 54/54 static, 71/71 full |
| Data used | Only what already exists: home.json + the PC post (pc_feed.js homeOver: accounts, board, brain glance, reporter), nq/news_week.json, trading/trades.json, business/accounts.json. No new exporter needed. Optional PC patch (LEAD_WIRES B) gives the exact last-alert time |
| Look | Token colours only (dark + Athena light checked), soft fade-in, room bars grow in, live dot pings; all stops under reduced motion. No sideways scroll at 390 px, no page errors |

## Follow-ups from the lead (05:38 / 05:49 ET)
| What | Result |
|---|---|
| Live ATLAS short (1 MNQ @ 26,380.75, stop moved to 26,379.50, target 26,122.75) | NQ "In the trade": size, entry, stop "moved to break-even (+$3 locked)", target (+$516), open $ at the last chart bar, minutes in trade, the bar's age. The ATLAS tile on NQ + Trading shows "SHORT 1 @ 26,380.75 · +$194 · stop at break-even". Data from the PC's chart post (the stop as it is now). Test: test_nq_desk (real case). Its close: test_alert_audit part_real, entry + "closed SHORT +$516 (target)" with R, web push + ntfy |
| Chart candles late (04:15, none at 05:15-05:45) | **Cause found and fixed** in tools/pc_report.py: an open trade made every run a "busy" run, so the candles never went. Now they go once 74 min old. test_pc_bars 75/75 (old code: 0 candles on a trade-open day). Quality card shows the candle age |
| Root fix (lead asked) | tools/pc_report.ext_hash leaves an open trade's live $ / R out (the `at` and `board_trades` blocks), as it already did for block times and the glance. An open trade no longer makes every run an ext run. Open all day: 48 ext runs of 96 (old: 78), 192 posts that day vs a 238 limit. A stop move or a close still flips the hash at once. test_live_publish 86/86, test_pc_bars 75/75, pc_publish / bots_back / datafeed 198/0, mffu_view 22/22 |
| ATLAS edge chip "data to Oct 16" | Cause: its stored backtest run and member trade files end Oct 16 (a re-score still ends there). Refresh plan in LEAD_WIRES F (moves pinned research numbers, so not done on a live day). Quality card shows it red meanwhile |

**Not changed:** no bot process file (tools/pc_report.py is the 15-minute reporter, changed only in the chart-post timing), no engine/, no live_model, no sw.js / build / apps.js / APPS table, no olympus/ kit, no STATE.md (lead's).

## Tests (all run here)
| Suite | Result |
|---|---|
| tests.test_trade_alerts | 21/21 |
| tests.test_pc_bars | 75/75 (new open-trade day) |
| tests.test_alert_audit (new) | 18/18 with the patches (incl. the live ATLAS case); `--now` (bot as is) fails on R, which is the gap |
| tests.test_nq_desk (new, node) | 24/24 (it caught 2 bugs I then fixed: an old report now makes every account stale; "next news" skips low-impact) |
| tests.test_nq_page (browser) | 70/70 |
| tests.test_trading_page (browser) | 71/71 (static 54/54, also 54/54 with the old pinned file as trades.json) |
| tests/smoke.py | 7/8: test_zenith_mode failed only because this container had no Python Playwright; I pip-installed it after for the browser runs |

## Screenshots (390x844, scale 2, DEMO numbers)
nq_accounts_dark/light.png, nq_thinking_dark/light.png, nq_quality_dark/light.png, nq_in_trade_dark/light.png (the live ATLAS case), trading_accounts_dark/light.png.
On the live site the same cards fill from the PC's report; with no report they say "no PC numbers" rather than show old or made-up numbers.
