---
tags:
  - zeus/strategy
  - bot/kalshi
  - market/kalshi
type: "strategy"
key: "k8"
---

# Kalshi K8

> [!abstract] Kalshi gold / silver range legs at fixed times (research/kalshi_edge_K8).

## Legs

- [[K8 leg 05.15 down gold|05:15 down gold]]: 77 bets, won 72.7%, +$435
- [[K8 leg 05.15 down silver|05:15 down silver]]: 76 bets, won 63.2%, +$230
- [[K8 leg 16.00 down gold|16:00 down gold]]: 78 bets, won 70.5%, +$415
- [[K8 leg 16.00 down silver|16:00 down silver]]: 78 bets, won 74.4%, +$442
- [[K8 leg 16.45 up gold|16:45 up gold]]: 78 bets, won 65.4%, +$258
- [[K8 leg 16.45 up silver|16:45 up silver]]: 78 bets, won 74.4%, +$452

## Performance by period

| Span | Bets | Won | Net |
|---|---|---|---|
| 2026-08-03 to 2026-11-18 | 465 | 70.1% | +$2,234 |

## Why it wins and loses

- 465 bets 2026-08-03 to 2026-11-18: 70% won, +$2,234 at $15 a bet. A loss costs $15.27, a win pays $13.36: K8 wins by being right often, not big.
- Why it wins: the cheap fills. Bets bought under 50c made +$1,106 of the +$2,234 (64% won, $18.25 a win); at 60c+ they win 83% but pay $7.87, +$307 in total. A price creeping up is the real threat.
- Why it loses: gold and silver of the same window move together. Of 232 windows both won 139 and both lost 45 times: the 6 legs are closer to 3 bets a day, so a bad day costs 2 x $15.
- Held-out weeks (test): 68% won, +$945; 2 of 16 weeks lost money, the newest week -$74.

## Tested and rejected

> [!failure]- **Kalshi K8 better edge
> **Kalshi K8 better edge (2026-11-20 night-kalshi8, `research/writeups/kalshi-k8-monday-2026-11-20.md`, `research/kalshi_k8_monday/edge.py`, 84 variants, one-sided Bonferroni t >= 3.24 found on Aug 3-Oct 21, checked on the held-out Oct 22-Nov 19, $2.50 bets, the +20 s tape price, verify.py fees): NOTHING passed. Entry +10 s pays 0.15-0.5c MORE than +20 s (-2% to -3% per $1), +40 s pays 0.8c more and misses 19% of fills: +20 s stays. Price caps 50-60c per leg (30): the skipped dearer bets still made +19% to +53% per $1 in the find weeks (only gold 16:15 above 60c lost, 8 bets). Leg filters from the metals' own path on Kalshi's settles (48: previous quarter hour, 4-hour move, the session ...
> Write-ups: [[kalshi-k8-monday-2026-11-20|Kalshi K8 for a $55 account, ready by Monday 6 PM]]


## Write-ups

| Date | Write-up | Verdict |
|---|---|---|
| 2026-11-20 | [[kalshi-k8-monday-2026-11-20\|Kalshi K8 for a $55 account, ready by Monday 6 PM]] | research |
| 2026-11-19 | [[kalshi-red-team-K8-2026-11-19\|Kalshi red team on K8]] | research |
| 2026-11-19 | [[kalshi-metals-2026-11-19\|Kalshi K8 commodities]] | research |
| 2026-11-19 | [[kalshi-edge-K7-2026-11-18\|Kalshi K7]] | rejected |
| 2026-11-19 | [[kalshi-edge-K6-2026-11-18\|Kalshi edge, team K6]] | rejected |
| 2026-11-18 | [[kalshi-red-team-2026-11-18\|Kalshi red team, the liquidity-rewards lead checked from raw data]] | research |
| 2026-11-18 | [[kalshi-best-shot-rewards-2026-11-18\|Kalshi best shot]] | rejected |
| 2026-11-17 | [[kalshi-rewards-backtest-2026-11-17\|Kalshi liquidity rewards, the paper rule replayed on the last 30 days of the public tape]] | research |
| 2026-11-17 | [[kalshi-edge-K5-2026-11-17\|Kalshi edge, team K5]] | research |
| 2026-11-17 | [[kalshi-edge-K4-2026-11-17\|Kalshi edge, team K4]] | rejected |
| 2026-11-13 | [[kalshi-edge-K3-2026-11-13\|Kalshi edge, team K3]] | rejected |
| 2026-11-13 | [[kalshi-edge-2026-11-13\|Kalshi edges, team K1]] | rejected |
| 2026-11-11 | [[kalshi_edge_C\|Kalshi edge, team C]] | rejected |
| 2026-11-10 | [[kalshi_edge_B\|Kalshi edge, team B]] | rejected |
| 2026-11-10 | [[kalshi_edge_A\|Kalshi edge, team A]] | rejected |
| 2026-11-04 | [[2026-11-04_kalshi_edges\|Kalshi Edge v2]] | finding |

## Links

- Hub: [[ZEUS Kalshi]]
- [[ZEUS Lessons]] · [[ZEUS Decisions]] · [[ZEUS Home]]
