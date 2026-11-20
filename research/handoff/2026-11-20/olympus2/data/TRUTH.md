# Truth check (2026-11-20 14:53 UTC)

Read only (tools/truth_check.py). TRUTH = the PC's own 15-minute report; every other number is checked against it.

## The truth now (PC report)

| account | balance | room | to pass / payout | today | last trade | age |
|---|---|---|---|---|---|---|
| Zlarior 50K | $49,192.78 | $1,024.58 | $3,807.22 | $0 | 2026-11-16 -$129.40 | 23 min |
| Zlarior 25K #2 | $25,000 | $1,000 | $1,500 | $0 | - | 23 min |
| ATLAS 25K | $25,401.38 | $1,401.38 | $1,448.62 | $514.18 | 2026-11-20 $514.18 | 23 min |

## Problems (4)

| level | where | what | shown | should be |
|---|---|---|---|---|
| warn | PC status post | the PC's report is 23 min old (it posts every 15 min) |  |  |
| warn | home.json accounts[id=mffu50k_eval] | Zlarior 50K: home.json says balance $49,900 (badge PAPER, source pc); any page that reads home.json without the PC post shows it | $49,900 | $49,192.78 |
| warn | home.json board.lit | Zlarior 50K: cloud paper numbers (PAPER) | $49,900 | $49,192.78 |
| warn | home.json live.eval | the 50K eval block (read by older apps) is the cloud's paper twin | $49,900 | $49,192.78 |

## Notes (5)

- PC status post: Rapid EOD 25K is not in the PC's report (plan says 'buying')
- home.json board.atlas: ATLAS 25K: no numbers in the cloud copy (status 'not set up'): pages need the PC post
- trading/trades.json: ATLAS 25K: the 2026-11-20 trade ($514.18) is not in the file yet (newest 2026-11-18); pages must add the PC post's trades (Trading does: feedRows)
- kalshi/k8.json: no build time in the file
- nq/brief.json data.stale: NQ bars end 2026-11-19 16:55 ET: today's session is not in the cloud data yet (the PC pushes its bars after 17:05 ET)

## Pages (390 x 844, after their feeds load)

| page | wrong balance-like $ | wrong room $ | DEMO shown | accounts named | missing (nq / trading / board) |
|---|---|---|---|---|---|
| nq/ | - | - | - | Zlarior 50K, Zlarior 25K #2, ATLAS 25K | - |
| trading/ | $52,600 (d: first payout when the profit is at least $2,600 (balance $52,600), ); $26,350 (d: first payout when the profit is at least $1,350 (balance $26,350), ) | - | - | Zlarior 50K, Zlarior 25K #2, ATLAS 25K | - |
| board/ | $26,946.10 (You wrote ATLAS · Nov 17, 4:38 PM ET · you  ATLAS balance $26,946.10: ) | - | - | Zlarior 50K, Zlarior 25K #2, ATLAS 25K | - |
| helios/ | $49,900 (live grove  One tree for every account  MFFU 50K Eval Eval  $49,900 · ); $49,900 (of $2,000 max loss  0 rings · 0 olives Paper (cloud) Paper  $49,900 · ) | $1,900 (low its start by $100: a thirsty tree.  Drawdown left $1,900); $1,900 (ing: the cloud's twin, not real money.  Drawdown left $1,900) | - | Zlarior 50K, Zlarior 25K #2, ATLAS 25K | - |
| clio/ | $24,887 (ior 50K $49,193 / $1,025 room, 25K #2 $25,000, ATLAS funded $24,887 / ); $24,887 (to make more". ATLAS alone on the FUNDED MFFU Builder 25K ($24,887, $8) | - | - | Zlarior 50K, Zlarior 25K #2, ATLAS 25K | - |
| business/mffu.html | - | - | - | Zlarior 50K, Zlarior 25K #2, ATLAS 25K | - |
| pnyx/ | - | $438 (ze follows it. After one full stop-out: Drawdown left $438 o) | - | Zlarior 50K, Zlarior 25K #2, ATLAS 25K | - |
| gate/ | - | - | - | Zlarior 50K, Zlarior 25K #2, ATLAS 25K | - |
