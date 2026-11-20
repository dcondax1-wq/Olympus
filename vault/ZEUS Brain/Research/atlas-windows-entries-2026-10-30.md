---
tags:
  - zeus/research
  - family/timing
  - verdict/rejected
  - bot/atlas
type: "research"
date: "2026-10-30"
status: "rejected (no change) - window cuts picked on 2026 H1 (30-min, hour, weekday; one per member) either fail the v2 test or pass it only as known spikes (S/R 11:00, atlas.md) or mined weekdays whose ..."
source: "research/writeups/atlas-windows-entries-2026-10-30.md"
aliases:
  - "ATLAS per-member trading windows and limit entries"
---

# ATLAS per-member trading windows and limit entries

> [!failure] Verdict: rejected
> rejected (no change) - window cuts picked on 2026 H1 (30-min, hour, weekday; one per member) either fail the v2 test or pass it only as known spikes (S/R 11:00, atlas.md) or mined weekdays whose neighbours fail; limit entries at a better price (signal-bar midpoint, 0.25 / 0.5 of the stop back) miss the winners - every one loses 2026 H1 2-week passes (29-58% vs 65.5%); the one robust window fact stays the known EMA 06:00 hour (atlas-v2 candidate 3)

**Full title:** ATLAS per-member trading windows and limit entries (2026-10-30) - no window cut or limit entry beats today's ATLAS

## Summary

Owner 2026-10-30 (round 2) - for ATLAS (account B, Builder 25K - EMA London pullback, MACD sweep, S/R NY reclaim), (1) skip each member's weakest time-of-day / weekday window, picked on 2026 H1 only (one cut per member), frozen, checked on H2, 2025 and 2021-24 with random-window controls and neighbours; (2) enter on a limit at a better price (signal-bar midpoint, 0.25 / 0.5 of the stop distance back) for 15 / 30 minutes, else skip or else market, with true 1m fills in 2026 (traded through by 1 tick), the stop at the same protected level and size following the smaller stop. Judged on the 25K account path (2-week pass / dead, eval-path $ a month, the v2 test) and at $500 a trade. Windows - 3 of the frozen cut sets pass the v2 test (S/R no 11:00-11:30; MD no Friday + S/R no Wednesday; plus the EMA 06:00 hour as a neighbour) but 3 of all 25 single 30-minute cuts pass it too, the neighbours fail and the S/R one is the 3-trade 11:00 spike of atlas.md. Limits - the best trades never come back - in H1 a 30-minute q25 limit misses 27 winners (+86R) to save 9 losers (-9R); 2-week pass 31.9% vs 65.5%. Nothing changes.

## Money first

**No change for ATLAS. No window cut and no limit entry passes every test.**

- **Windows.** One weak window per member was picked on 2026 H1, then frozen. It does not hold up as an edge:
  - Three cut sets pass the 25K test (2-week pass not down, dead not up and eval-path $ up in both 2026 halves, 2025 and
    2021-24 not worse).
  - Each one fails a stricter check. The S/R cut is the known 11:00 spike (atlas.md): its 3 H1 trades all entered at
    exactly 11:00. The weekday pair only works together, and every neighbouring day fails. 3 of all 25 possible single
    30-minute cuts pass the same test by luck.
- **The one window fact that keeps showing up is old news.** EMA entries in the 06:00 ET hour lost in every year
  2021-2026: 60 trades, -28R.
  - It is the neighbour of this round's pick, not the pick itself.
  - atlas-v2.md already found it (candidate 3: "no EMA entry 06:00-06:59").
  - It changes 3 trades in 2026, worth about +$140 a month in H1 and +$42 in H2. It stays in the ATLAS v2 paper package and
    is not a new switch.
- **Limit entries: rejected, as atlas.md found for a limit at the signal close.**
  - A limit at a better price does fill most losers, but the best winners never come back to it.
  - In H1 the 30-minute limit 0.25 of the stop back misses 27 winners (+86R) to save 9 losers (-9R).
  - Every one of the 24 limit variants loses H1 2-week passes: 29-58% vs today's 65.5%.
  - "Else market" (chase after the timeout) is no better: the late fills are the trades that already ran.

**Window cuts** (ATLAS on its Builder 25K: account-B need size, LIT first, no hedge, max 2 a day; eval paths =
back-to-back 25K evals started every 5th session, $ less the $63 fees, a month; R = R per $ risked at $500 a trade, costs
in; "dead" = failed or stuck):

| ATLAS | 2026 H1: 2-wk pass / dead, eval $/mo, R | 2026 H2 | 2025 | 2021-24 | v2 test |
|---|---|---|---|---|---|
| **Today** | 65.5 / 0.8, $1,394, +0.884 | 43.5 / 0.0, $547, +0.620 | 30.1 / 23.3, -$148, +0.084 | 22.9 / 27.1, -$36, +0.045 | |
| 30-min picks: EMA no 04:00-04:30, MD no 04:30-05:00, S/R no 11:00-11:30 | 72.3 / 0.0, $2,355, +1.101 | 43.5 / 0.0, $610, +0.701 | 28.9 / 8.4, -$1, +0.123 | 21.6 / 23.1, -$67, +0.056 | fails (2021-24) |
| S/R no 11:00-11:30 alone | 68.9 / 0.8, $1,598, +0.935 | 43.5 / 0.0, $591, +0.626 | 30.1 / 16.1, -$99, +0.096 | 22.7 / 24.7, -$23, +0.059 | passes |
| Hour picks: EMA no 05:00, MD no 10:00, S/R no 11:00 hour | 73.1 / 0.8, $2,065, +1.026 | 50.7 / 0.0, $480, +0.618 | 28.1 / 14.1, -$70, +0.122 | 24.1 / 19.6, -$24, +0.106 | fails (H2 $) |
| EMA no 06:00 hour (the neighbour, atlas-v2) | 65.5 / 0.8, $1,532, +0.909 | 43.5 / 0.0, $589, +0.652 | 30.5 / 18.9, -$144, +0.093 | 23.2 / 23.6, -$26, +0.078 | passes |
| Weekday picks: MD no Friday, S/R no Wednesday (EMA: none) | 65.5 / 0.0, $1,783, +1.066 | 43.5 / 0.0, $628, +0.760 | 27.7 / 14.9, -$139, +0.100 | 21.9 / 21.9, +$69, +0.048 | passes |

Trades a week stay at 2+:
- Candidates a week (eval-path trades in brackets): today 4.4 (2.1) / 3.3 (1.6) / 4.8 (2.6) / 5.4 (3.1).
- The cut sets: 3.8-4.3 / 2.7-3.2 / 4.2-4.7 / 4.6-5.2 candidates. 2+ candidates a week in 75-99% of weeks; the hour picks
  are the lowest, 75% in H2.

At $500 a trade the cut sets make $8,193-8,938 / $3,501-4,506 / $901-1,092 / $490-1,028 a month. Today makes
$8,112 / $4,260 / $857 / $510.

**Limit entries** (30-minute limits; "skip" = not filled in 30 minutes, no trade; "mkt" = then market at the next open + 1
tick; fill rate = the limit's own fills; missed winners / saved losers = the unfilled trades' R at today's entry):

| ATLAS entry | limit fill rate H1 / H2 / 2025 / 2021-24 | H1 missed winners vs saved losers | H1: 2-wk pass / dead, eval $/mo, R | H2 | 2025 | 2021-24 |
|---|---|---|---|---|---|---|
| **Today (market at the next 5m open)** | | | 65.5 / 0.8, $1,394, +0.884 | 43.5 / 0.0, $547, +0.620 | 30.1 / 23.3, -$148, +0.084 | 22.9 / 27.1, -$36, +0.045 |
| Midpoint of the signal bar, skip | 76 / 80 / 73 / 80% | 22 (+58.9R) vs 5 (-5.0R) | 47.1 / 2.5, $1,077, +0.857 | 46.4 / 0.0, $317, +0.819 | 30.9 / 14.1, $57, +0.185 | 23.0 / 31.3, $52, -0.006 |
| Midpoint, else market | 76 / 80 / 73 / 80% | 9 (+17.4R) vs 0 | 47.1 / 3.4, $676, +0.762 | 46.4 / 0.0, $387, +0.680 | 32.5 / 18.5, $311, +0.200 | 22.6 / 35.2, -$68, -0.009 |
| 0.25 of the stop back, skip | 70 / 81 / 74 / 78% | 27 (+86.2R) vs 9 (-9.0R) | 31.9 / 0.0, $559, +0.517 | 44.9 / 0.0, $1,192, +0.867 | 28.9 / 13.3, $281, +0.215 | 22.1 / 29.2, -$19, -0.019 |
| 0.25 back, else market | 70 / 81 / 74 / 78% | 11 (+26.5R) vs 0 | 31.9 / 0.0, $227, +0.511 | 60.9 / 0.0, $1,465, +0.846 | 27.7 / 22.5, $109, +0.189 | 21.4 / 33.8, -$181, -0.021 |
| 0.50 of the stop back, skip | 53 / 53 / 55 / 59% | 40 (+123.7R) vs 15 (-15.0R) | 39.5 / 1.7, $729, +1.017 | 14.5 / 0.0, $308, +0.896 | 26.1 / 8.8, -$207, +0.064 | 23.1 / 19.6, -$19, -0.082 |
| 0.50 back, else market | 53 / 53 / 55 / 59% | 13 (+30.4R) vs 0 | 42.9 / 4.2, $540, +0.771 | 40.6 / 1.4, $629, +0.585 | 35.7 / 23.7, -$104, +0.136 | 25.3 / 32.7, $24, -0.015 |

The 15-minute limits are worse: a 2-week H1 pass of 29.4-53.8%. The same 12 limits with the member's management kept at
today's price levels (BE trigger and 15-minute check levels unchanged, instead of in R of the smaller fill risk) are also
all worse in H1: 36.1-58.0%. None of the 24 passes the v2 test. All 24 are in `research/second/atw_entries.json`.

## Links

- Family: [[Family timing]]
- Day: [[Day 2026-10-30]]
- Strategies: [[ATLAS]]
- Refers to: [[atlas|ATLAS]], [[atlas-blitz-edge-2026-10-30|ATLAS + BLITZ edge night]], [[atlas-v2|ATLAS v2]], [[calendar-effects|Calendar and seasonality]]
- Runs: `atw_win_m30, atw_win_m30_sr, atw_win_m60, atw_win_dow, atw_entry_mid_30m_skip, atw_entry_mid_30m_mkt, atw_entry_q25_30m_skip, atw_entry_q25_30m_mkt, atw_entry_q50_30m_skip, atw_entry_q50_30m_mkt, atw_entry_q0_15m_skip`
- Source: `research/writeups/atlas-windows-entries-2026-10-30.md`
- Back to [[ZEUS Home]]
