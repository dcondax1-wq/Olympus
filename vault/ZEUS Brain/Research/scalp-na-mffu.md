---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/zlarior
  - bot/atlas
  - bot/blitz
type: "research"
date: "2026-10-28"
status: "promising - one filter (yesterday's range) holds in 2026 H1, H2 and 2021-25; the money is BLITZ trading on LIT's funded Builder 50K while LIT is flat (+$301 / +$290 a month per account slot in H1 / ..."
source: "research/writeups/scalp-na-mffu.md"
aliases:
  - "BLITZ"
---

# BLITZ

> [!tip] Verdict: promising
> promising - one filter (yesterday's range) holds in 2026 H1, H2 and 2021-25; the money is BLITZ trading on LIT's funded Builder 50K while LIT is flat (+$301 / +$290 a month per account slot in H1 / H2, +$16 in 2021-25, LIT's eval untouched). On its own MFFU 25K it still does not pay; inside ATLAS it adds dead evals. Paper only, nothing switched.

**Full title:** BLITZ (the noise-area scalp) on MFFU - it pays as an add-on on LIT's funded 50K (about +$290-300 a month in both 2026 halves), not on its own account and not inside ATLAS

## Summary

Owner 2026-10-28 - make the noise-area (NA) momentum scalp ("BLITZ") pay on MFFU, honestly. Picked on 2026 H1, checked on H2, 2021-25 on 5m bars as the reference; costs as before ($1.90 a micro, 1 tick on every market / stop fill, same-bar tie = loss). 93 filters + 90 filter pairs, 4,800 exits, 896 eval / funded sizes, 1,536 whole-account slots, 22 ATLAS and 121 LIT combinations. One filter holds - trade only when yesterday's 09:30-16:00 range was at least 0.8 x its 14-day average - avg R a trade +0.098 -> +0.150 (H1), +0.066 -> +0.171 (H2), +0.007 -> +0.016 (2021-25); at $150 a trade PF 1.63 / 1.49 / 1.06, +$912 / +$577 / +$89 a month, 7-9 trades a week; random directions lose (p 0.025 / <0.025 / <0.025). No exit change, daily profit stop or "need" pass-maximizer holds. Alone on an MFFU 25K the eval passes 31-35% in 2 weeks (2021-25 17%) but the whole account slot pays $224 / $3 / -$40 a month (H1 / H2 / 2021-25). Inside ATLAS's 25K it lifts H2 (2-week pass 43.5 -> 55.1%) but adds dead evals (H1 0.8 -> 3.4%, 2021-24 27 -> 36%) and only ~$25-35 a month funded. On LIT's funded 50K (BLITZ only once funded, only while LIT holds nothing and has nothing armed, flattened when LIT enters, never opposite ATLAS, 20% of the room up to $450 a trade, up to 6 a day) the LIT account slot goes from $823 / $798 / -$7 to $1,124 / $1,088 / $9 a month; better in 75% of 6-month paths; the real 2026 path pays $10,925 instead of $7,816. Random-direction BLITZ there loses money (-$125 to -$197 a month), so it is the edge, not the payout rules. It needs up to 6 BLITZ trades a day (capped at 2, the H2 gain is gone) and an entry no later than 1 bar after the signal.

## Money first

**The best honest use of BLITZ: let it trade on LIT's own Builder 50K once that account is funded, only while LIT is flat.**
Each row is one MFFU account slot for 6 months: buy the eval ($91.80), pass, 2 sessions of paperwork, the funded account,
payouts (80% to you), and a new eval at once after a fail, a lost account or the 5th payout. Monte Carlo, 1,000 paths of
126 sessions drawn in 5-session blocks from the span (seed 23, as `uprisk.md`). Net of every eval bought.

| LIT's 50K slot | 2026 H1 (pick) | **2026 H2 (check)** | 2021-25 (reference) |
|---|---:|---:|---:|
| LIT alone (today's live sizing) | $823 / month | **$798 / month** | -$7 / month |
| **LIT + BLITZ once funded** (20% of the room, at most $450 a trade) | **$1,124 / month** | **$1,088 / month** | $9 / month |
| Gain, same paths | **+$301** | **+$290** | +$16 |
| Paths where BLITZ adds / costs money | 75% / 11% | 76% / 13% | 10% / 6% |
| 1 in 10 paths (worst tenth), LIT alone -> with BLITZ | $236 -> $251 | $216 -> $251 | -$78 -> -$76 |
| Slots that lose money in 6 months | 5.8% -> 6.2% | 7.6% -> 6.4% | 88% -> 84% |
| LIT's eval, 2-week pass / fail | 52.9 / 17.8 (unchanged) | 58.6 / 20.9 (unchanged) | 20.7 / 24.9 (unchanged) |
| Funded accounts reached in 6 months | 1.18 -> 1.45 | 1.15 -> 1.40 | 0.85 -> 0.85 |

- **The real 2026 path** (one slot from 2026-01-02 to 2026-10-16, no resampling): LIT alone 5 payouts, **$7,816** net; LIT +
  BLITZ 7 payouts, **$10,925** net (+$3,109 in 9.5 months, about +$330 a month).
- **Where the money comes from** (a funded 50K on its own, no eval): BLITZ adds about **+$850 (H1) / +$690 (H2) a month of
  trading profit** inside the account, but MFFU's payout limits ($2,000 a request, 5 payouts, the 50% best-day rule) let
  only about **+$180 a month more out** ($929 -> $1,108 H1, $915 -> $1,103 H2). The first payout comes sooner (26 -> 18
  sessions in H1, 23.5 -> 20 in H2), the worst tenth of 6-month accounts pays twice as much ($1,600 -> $3,197 H1), and
  **no funded account was lost** with or without BLITZ. The slot gains more (+$290-300) because each funded account
  reaches its 5 payouts sooner and the next one starts earlier.
- **2021-25 adds almost nothing** (+$16 a month), mainly because LIT's 2021-25 evals rarely pass (31%), so BLITZ rarely
  gets a funded account to trade on. BLITZ itself makes +$89 a month at $150 a trade there (below).

**BLITZ by itself** (the trades, $150 risk a trade, size = $150 / stop cost; 2026 on 1m bars, 2021-25 the same rule on 5m):

| Span | Trades | / week | Weeks with 2+ | Win % | Avg R | PF | Net | **$ / month** | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026 H1 (pick) | 221 | 8.6 | 89% | 55.7 | +0.150 | 1.63 | +$5,560 | **+$912** | -$1,314 |
| **2026 H2 (check)** | 109 | 7.0 | 75% | 55.0 | +0.171 | **1.49** | **+$2,143** | **+$577** | -$903 |
| 2021-25 (5m reference) | 1,869 | 8.7 | 81% | 50.3 | +0.016 | 1.06 | +$4,570 | +$89 | -$4,783 |
| ... 2025 | 447 | 8.7 | | 50.6 | +0.020 | 1.08 | +$1,703 | +$139 | -$2,433 |
| ... 2021-24 | 1,422 | 8.7 | | 50.2 | +0.014 | 1.05 | +$2,867 | +$74 | -$3,583 |
| the NA scalp before (2026 H1 / H2 / 2021-25) | 304 / 177 / 2,681 | 11.9 / 11.4 / 12.5 | | | +0.098 / +0.066 / +0.007 | 1.37 / 1.22 / 1.02 | | +$799 / +$466 / +$55 | |

By year at $150 a trade: 2022 +$264 a month, 2023 +$111, 2024 **-$144**, 2025 +$139, 2026 +$785. It trades on about 43%
of days, and on 41 of 2026's 89 trading days it took 5-6 trades: **it is a trend-day machine**. After the first entry it
re-enters at each later check while price stays outside the band.

**BLITZ alone on its own MFFU account** (fresh eval started on every session, 20 sessions; size picked on H1):

| BLITZ alone | 2-week pass / fail (p10/f10) | decided in 2 wks (dec10) | 3-week pass / fail | 1-month pass / fail | median sessions to pass | passes slower than 3 wks | whole slot, $ / month to you |
|---|---:|---:|---:|---:|---:|---:|---:|
| Builder 25K, H1 (40% of room, max $600) | 31.1 / 10.1 | 41% | 44.7 / 21.9 | 52.3 / 38.5 | 8.5 | 15% | $224 |
| Builder 25K, **H2** | 34.8 / 2.9 | 38% | 42.2 / 18.8 | 42.4 / 40.7 | 6.5 | 7% | **$3** |
| Builder 25K, 2021-25 | 16.8 / 13.6 | 30% | 21.8 / 27.8 | 24.8 / 37.7 | 6 | 12% | -$40 |
| Builder 50K, H1 (40% of room, max $1,200, half off at +1R) | 32.8 / 4.2 | 37% | 46.5 / 9.6 | 56.9 / 18.3 | 9 | 21% | $410 |
| Builder 50K, **H2** | 34.8 / 0.0 | 35% | 42.2 / 0.0 | 57.6 / 0.0 | 8 | 23% | **$290** |
| Builder 50K, 2021-25 | 17.8 / 4.8 | 23% | 22.1 / 13.8 | 25.4 / 22.2 | 6 | 13% | $11 |

"Whole slot" uses its own H1-picked sizes (25K: eval 60% of the room / $600, funded 10% / $150 with a +$400 day stop; 50K:
eval 60% / $1,200, funded 20% / $600 with a +$800 day stop, half off at +1R). The 2-week pass is better than the plain NA
scalp's (25K 21.0 / 4.2 and 21.7 / 18.8), but still only a third of evals pass
in 2 weeks and most are undecided: the owner's "passed or failed in 2 weeks" rule is missed. Once funded, a 25K gets stuck
at its floor before it pays (funded alone: $219 / $163 / $26 a month, 34-84% of accounts stuck); a 50K pays $473 / $475 /
$65 a month funded, but **MFFU allows only one funded Builder 50K per person, and that is LIT's.** None of the 768 25K slot
settings made money in H1, H2 and 2021-25 together.

**BLITZ inside ATLAS's 25K** (4th member, tools/atlas.py's real account-B rules, ATLAS's own trades first, the daily cap
raised to 6, BLITZ at 20% of the room, at most $300):

| ATLAS 25K | 2-week pass / dead H1 | H2 | 2025 | 2021-24 | funded $ / month H1 / H2 / 2025 / 2021-24 |
|---|---:|---:|---:|---:|---:|
| ATLAS today, cap raised to 6 (at cap 2: 65.5 / 0.8, 43.5 / 0.0; $582 / $517) | 66.4 / 0.8 | 43.5 / 0.0 | 31.7 / 22.5 | 22.6 / 27.0 | $605 / $517 / $83 / $40 |
| + BLITZ | 67.2 / 3.4 | **55.1** / 0.0 | 30.9 / 26.9 | 22.0 / **36.0** | $630 / $552 / $79 / $36 |

It helps H2 but kills more evals in 2 weeks in H1, 2025 and 2021-24 (stuck under the floor), the eventual pass drops in
H1 (92 -> 89%), and th

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-28]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[BLITZ (paper)]]
- Refers to: [[calendar-effects|Calendar and seasonality]], [[uprisk|Uprisk]]
- Runs: `scalp_na_blitz, scalp_na_blitz_lit50k, scalp_na_atlas_member`
- Source: `research/writeups/scalp-na-mffu.md`
- Back to [[ZEUS Home]]
