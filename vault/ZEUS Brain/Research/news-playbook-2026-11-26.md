---
tags:
  - zeus/research
  - family/other
  - verdict/research
type: "research"
date: "2026-11-26"
source: "research/writeups/news-playbook-2026-11-26.md"
aliases:
  - "News-day playbook"
---

# News-day playbook

> [!abstract] Verdict: research
> (no status line)

**Full title:** News-day playbook: is there money in CPI / NFP / PPI / FOMC days? (2026-11-26)

## Summary

PAPER RESEARCH ONLY, no live file touched. Pre-registered BEFORE any measurement (`research/news/DESIGN.md`, commit c36c51caf). Code `research/news/news.py` -> `research/news/results.json`. NQ 5m futures bars 2021-11 .. 2026-11-20, $250 a trade. Costs are deliberately wide for news fills: 6 ticks on every market entry, 2 ticks on stop / market exits, $1.90 a micro; a stress run at 12 + 4 ticks. Calendar coverage (honest): FOMC complete 2021-26 (41 days). CPI / PPI complete from 2024, only 3 each in 2023, none in 2021-22. NFP 2021-23 gaps filled by the first-Friday rule (23 days, flagged). PCE / GDP / retail sales / ISM are in the file only for late 2026 (n < 3): not studied. 130 Tier-1 08:30 days in all.

## Money first

### (1) What NQ does around the releases (vs the same clock time on non-event days)
| | 08:30 Tier-1 (130) | CPI (36) | NFP (58) | PPI (36) | FOMC 14:00 (41) | normal day 08:30 / 14:00 |
|---|---|---|---|---|---|---|
| First-hour range, pts | **160** (2.2x) | 188 | 168 | 122 | **243** (3x) | 73 / 81 |
| First 5m bar's direction still ahead at +60 min | 38% | 25% | 40% | 47% | 46% | 51% / 48% |
| Back through the release open by +60 | 24% | 19% | 33% | 14% | 37% | 36% / 41% |
| Move from the first bar's close to +60, in ATR5 | **-1.07** (gives back) | -1.29 | -1.15 | -0.70 | -0.49 | +0.11 / -0.01 |
| Breaks the pre-release range in 30 min (overnight H/L; FOMC: day's 09:30-14:00) | 74% | 86% | 83% | 47% | 63% | 36% / 30% |
| ...of those, back inside by +60 | 38% | 26% | 42% | 47% | 27% | 47% / 43% |
In plain words: news days move 2-3x more. The FIRST spike is unreliable: on average it gives back about 1 ATR within the
hour, CPI the most. Breaks of the overnight high / low mostly stick (62% stay outside, CPI 74%).

### (2) The 8 playbooks (base costs; PF H1 / Jul-Nov / 2021-25, trades)
| Playbook | 2021-25 | 2026 H1 | 2026 Jul-Nov | Stress PF (2021-25) | Same clock, non-event days (2021-25 PF) | Walk-fwd |
|---|---|---|---|---|---|---|
| N1 08:30 first-5m-range break, 2R | PF 0.67, -$2,497 (65) | 1.32, +$313 (11) | 0.33, -$1,309 (10) | 0.64 | 0.80 | 5/19 |
| **N2 08:30 first-15m-range break, 2R** | **1.49, +$3,058 (67)** | **0.20, -$2,784 (16)** | 1.71, +$999 (11) | 1.41 | 0.78 | 10/19 |
| N3 08:30 spike fade back into the overnight range | 0.43, -$1,607 (26) | 0.64, -$178 (6) | 0.73, -$123 (3) | 0.39 | 0.81 | 4/17 |
| N4 08:30 first-move hold to 09:30 | 0.50, -$3,507 (97) | 0.57, -$548 (17) | 0.10, -$990 (10) | 0.43 | 0.90 | 4/19 |
| N5 FOMC presser break (14:00-14:30 range), 2R | 0.76, -$1,140 (34) | 0.24, -$715 (4) | 0.51, -$256 (3) | 0.74 | 0.90 | 7/19 |
| N6 FOMC spike fade | 0.73, -$356 (17) | 1 trade | 0 trades | 0.69 | 0.62 | 9/19 |
N2 is the only one with an edge over its non-event placebo (PF 1.49 vs 0.78 in 2021-25, survives the 12-tick stress), but it
lost $2,784 in Jan-Jun 2026 (16 trades, PF 0.2). Only ~1 trade a month: too few to trust either way. Not a card.

### (3) LIT / ATLAS on news days (skip vs as is; $/month and the 40-session 50K pass / fail)
| | 2021-25 | 2026 H1 | 2026 Jul-Nov |
|---|---|---|---|
| LIT as is | $25, 23.2 / 53.9 | $5,562, 83.7 / 16.3 | $1,847, 76.0 / 0.0 |
| N7 LIT skips news days | $86, 22.7 / 53.9 | $4,632, **72.1 / 25.0** | $1,994, 93.3 / 0.0 |
| ATLAS as is | $837, 32.4 / 67.6 | $8,887, 92.4 / 7.6 | $4,281, 60.8 / 39.2 |
| **N8 ATLAS skips news days** | **$931, 37.9 / 62.1**, DD -$29.2k -> -$16.3k | $7,849, **95.7 / 4.3** | $3,449, **69.6 / 28.4** |
| LIT + ATLAS on one 50K | $473, 29.9 / 70.1 | $11,877, 95.0 / 5.0 | $5,652, 88.2 / 11.8 |
| both skip news days | $656, 29.8 / 70.2 | $10,229, 97.4 / 2.6 | $4,928, 100 / 0.0 (median 9 -> 13 sessions) |
| + N2 on the same 50K | $541, 30.4 / 69.6 | $11,320, 91.6 / 8.4 | $5,984, 91.2 / 8.8 |
- **LIT: keep trading news days.** In Jan-Jun 2026 its news-day trades made +$5,670, and skipping drops the 50K pass 84 -> 72%.
- **ATLAS: nearest miss.** Skipping news days gives fewer eval fails in all three periods (2021-25 68 -> 62%, Jan-Jun 7.6 -> 4.3%,
  Jul-Nov 39 -> 28%) and halves the 2021-25 drawdown. But it costs $1,038 / $832 a month in 2026, so it fails the pre-registered
  "$ better in all three" rule. Caveat: the 2021-23 skip list is incomplete (no CPI / PPI dates). The FOMC-only sit-out was
  already rejected 2026-11-21 (holidays study). Paper lead, re-test when the 2021-23 CPI / PPI dates are filled.
- Already rejected before this study and consistent with it: flat 3 min before CPI / jobs / FOMC (lit-more-money), the
  CPI / NFP / FOMC playbook at 0.1-0.2 a week (newstrat lab).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-26]]
- Source: `research/writeups/news-playbook-2026-11-26.md`
- Back to [[ZEUS Home]]
