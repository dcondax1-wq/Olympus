# Truth check (2026-11-27 05:02 UTC)

Read only (tools/truth_check.py). TRUTH = the PC's own 15-minute report; every other number is checked against it.

## The truth now (PC report)

| account | balance | room | to pass | to payout (coach) | today | last trade | age |
|---|---|---|---|---|---|---|---|
| Zlarior 50K | $49,177.52 | $1,009.32 | $3,822.48 | - | $0 | - | 2 min |
| Zlarior 25K #2 | $25,019.24 | $995.62 | $1,480.76 | - | $0 | - | 2 min |
| ATLAS 25K | $25,401.38 | $1,000 | - | $948.62 | $0 | 2026-11-20 $514.18 | 2 min |
| Rapid EOD 25K | $24,995.24 | $995.24 | $1,504.76 | - | $0 | - | 2 min |

## Problems (7)

| level | where | what | shown | should be |
|---|---|---|---|---|
| warn | home.json live.eval | the 50K eval block (read by older apps) is the cloud's paper twin | $49,900 | $49,177.52 |
| warn | home.json | 7.9 h old (allowed 6.0 h) |  |  |
| warn | edge.json | 6.7 days old (allowed 30.0 h) |  |  |
| warn | trading/trades.json | 6.2 days old (allowed 3.0 days) |  |  |
| warn | business/payday.json | 3.2 days old (allowed 3.0 days) |  |  |
| warn | business/fleet_plan.json | 6.2 days old (allowed 3.0 days) |  |  |
| warn | edge.json eh.a | ATLAS's edge light uses data to 2026-11-19 (7.2 days old): LEAD_WIRES nqdash3 F |  |  |

## Notes (5)

- home.json board.lit: Zlarior 50K: no numbers in the cloud copy (status 'open'): pages need the PC post
- home.json board.atlas: ATLAS 25K: no numbers in the cloud copy (status 'not set up'): pages need the PC post
- trading/trades.json: ATLAS 25K: the 2026-11-20 trade ($514.18) is not in the file yet (newest 2026-11-18); pages must add the PC post's trades (Trading does: feedRows)
- kalshi/k8.json: no build time in the file
- nq/brief.json data.stale: NQ bars end 2026-11-20 16:55 ET: today's session is not in the cloud data yet (the PC pushes its bars after 17:05 ET)
