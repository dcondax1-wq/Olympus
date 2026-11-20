# ATLAS edge - helper report (day-atlasedge, 2026-11-20)

**One change passes: after 2 losing ATLAS trades in a row, trade 1 micro until the next win.** At real fills (10 ticks a
side) from today's funded 25K ($887 room) it cuts the 6-month chance of losing the account from 17.6% to 12.2%
(Jan-Jun-like market) and from 21.7% to 10.9% (Jul-Oct-like), for $503 -> $481 / $402 -> $408 a month. First payout about a
week later (Dec 30 / Jan 12 instead of Dec 23 / Jan 7). With room 40% as well: lost 10.1% / 7.7%, $478 / $394 a month.
One Decide card added (atlas-funded-streak-1micro, open, recommend yes). Nothing live changed.

| Job | Result |
|---|---|
| (a) limit order vs market | No. ~52% of signals fill; the missed ones are the runners. Funded $151-285 a month vs $503 |
| (b) leg that loses most to slippage | EMA (-$257 a month at $250 a trade, 1 -> 10 ticks). Dropping it: Jul-Oct-like $402 -> $101. Halving: $303. Keep it |
| (c) entry minute | No. Next 5m open: Jul-Oct-like -$133. Per-leg minute (MACD +1) looks good on Jul-Oct but needs 1m bars: info only |
| (d) ES legs | No. All 3 lose on ES in 2026 (PF 0.60-0.84 Jan-Jun at the equivalent cost) where NQ makes PF 1.2-3.3 |
| (e) funded guards | 2 losses -> 1 micro PASSES. Day stop after a loss, 3-loss pause, 35% weekly cap: fail |
| (f) payout path | Today: 1st Dec 23 / Jan 7, 2nd Jan 27 / Feb 22, lost before the 1st 13.9 / 16.7%. With the new rule + room 40%: 1st Jan 6 / Jan 20, 2nd Feb 11 / Mar 8, lost before the 1st 8.5 / 6.4% |

Pre-registered: research/second/atlas_edge_design.md (commit 5b511c92, pushed before any run). Gate at 6 AND 10 ticks, on
60% AND 40% sizing, 1,000 paths a market, both 2026 halves and 2021-25. Post-hoc checks of the passer (second path seed,
neighbours 1 / 3 losses) agree; shown, never used for the verdict.

Write-up: research/writeups/atlas-edge-2026-11-20.md. Data: research/second/atlas_edge.json, research/second/atlas_es_trades.json.
New tools: tools/atlas_edge.py, tools/atlas_es.py (research only). docs/TESTED_AND_REJECTED.md gets the 14 losers;
research/writeups/INDEX.md regenerated.

Tests: `python tests/smoke.py` 7/8 (the red one is tests.test_zenith_mode: playwright is not installed in this cloud
container, unrelated); `python -m tests.test_decide` 14/14 ALL PASS (inbox / browser parts skipped: fastapi / playwright
missing here). No engine file touched, so the nq area was not run.

Screens: none changed (one new data row in decisions.json; the Decide card renders it with existing code), so no screenshots.

If the owner says yes: build it as an OFF-by-default switch in the ATLAS funded preset (engine/account_b): count ATLAS's
closed trades in a row with net P&L < 0 (from its own ledger, survives a restart); at 2+ the funded size is min(size, 1)
micro; any winner resets the count. Test it, Sim check, then the owner arms it.
