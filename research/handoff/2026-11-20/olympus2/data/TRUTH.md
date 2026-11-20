# Truth check (2026-11-20 15:10 UTC)

Read only (tools/truth_check.py). TRUTH = the PC's own 15-minute report; every other number is checked against it.

## The truth now (PC report)

| account | balance | room | to pass | to payout (coach) | today | last trade | age |
|---|---|---|---|---|---|---|---|
| Zlarior 50K | $49,192.78 | $1,024.58 | $3,807.22 | - | $0 | 2026-11-16 -$129.40 | 40 min |
| Zlarior 25K #2 | $25,000 | $1,000 | $1,500 | - | $0 | - | 40 min |
| ATLAS 25K | $25,401.38 | $1,401.38 | - | $948.62 | $514.18 | 2026-11-20 $514.18 | 40 min |

## Problems (4)

| level | where | what | shown | should be |
|---|---|---|---|---|
| warn | PC status post | the PC's report is 40 min old (it posts every 15 min) |  |  |
| warn | home.json accounts[id=mffu50k_eval] | Zlarior 50K: home.json says balance $49,900 (badge PAPER, source pc); any page that reads home.json without the PC post shows it | $49,900 | $49,192.78 |
| warn | home.json board.lit | Zlarior 50K: cloud paper numbers (PAPER) | $49,900 | $49,192.78 |
| warn | home.json live.eval | the 50K eval block (read by older apps) is the cloud's paper twin | $49,900 | $49,192.78 |

## Notes (5)

- PC status post: Rapid EOD 25K is not in the PC's report (plan says 'buying')
- home.json board.atlas: ATLAS 25K: no numbers in the cloud copy (status 'not set up'): pages need the PC post
- trading/trades.json: ATLAS 25K: the 2026-11-20 trade ($514.18) is not in the file yet (newest 2026-11-18); pages must add the PC post's trades (Trading does: feedRows)
- kalshi/k8.json: no build time in the file
- nq/brief.json data.stale: NQ bars end 2026-11-19 16:55 ET: today's session is not in the cloud data yet (the PC pushes its bars after 17:05 ET)
