---
title: BLITZ at real fills on the one-account book (Rapid EOD 50K) - still more money in both 2026 halves, but it fails more evals than the pre-set bar and loses more in 2021-25; REJECTED, no card
family: money
date: 2026-11-23
status: rejected - paper only, nothing live changed. BLITZ stays a paper shadow.
summary: BLITZ has never traded real money, so its fills are modeled the way ATLAS's were measured (market order seconds after a widely seen bar close; ATLAS's 3 real fills sat 29-50% of the way into the entry minute's move). BLITZ's entry minute runs a median 9.25 pts its way (ATLAS 4.6), so the measured-proxy entry costs a median 15 ticks ($7 a micro). On the picked one-account book (Rapid EOD 50K, LIT + ATLAS, LIT x0.5 in the eval, $4,918 / $2,204 / -$88 a month), BLITZ $300 at measured fills adds +$513 / +$618 a month (Jan-Jun / Jul-Oct-like) but the eval fail goes 1.7% -> 5.6% (bar 2.3%) and 2021-25 gets worse (-$59 a month; BLITZ alone PF 0.80 there). Even at the old 1-tick fills the fail is 3.0% (over the bar). 0 of 6 fill variants pass.
runs: research/blitzfills/run.py -> results.json (1,000 paths, seeds 23 / 7, same paths as research/onebook); design research/blitzfills/DESIGN.md (committed bb2d0da1 before the scored run)
---

## For the owner (one minute)

**Do not add BLITZ to the account. It still adds money in markets like 2026, but it makes the eval about 3x more likely to fail
and it loses money in a 2021-25-like market. The one-account plan stays as it was: Zlarior + ATLAS on the Rapid EOD 50K.**

| Rapid EOD 50K, 6 months after fees | Jan-Jun-like | Jul-Oct-like | 2021-25-like | Eval pass / fail (Jan-Jun) |
|---|---:|---:|---:|---:|
| Plan: Zlarior + ATLAS, Zlarior half size in the eval | $4,918/mo | $2,204/mo | -$88/mo | 93.9% / 1.7% |
| + BLITZ $300, old fills (1 tick) | $6,022/mo | $3,334/mo | -$84/mo | 95.9% / 3.0% |
| **+ BLITZ $300, realistic fills (measured proxy)** | **$5,431/mo** | **$2,822/mo** | **-$148/mo** | **92.7% / 5.6%** |
| + BLITZ $300, 10 ticks a side | $4,968/mo | $2,694/mo | -$168/mo | 87.3% / 9.8% |

The extra money is real in 2026 (+$513 / +$618 a month at realistic fills), but the pre-set rule says BLITZ may only join
if the eval fail stays within 2 points of Zlarior alone (2.3%) and 2021-25 is not worse. Both fail.

## 1. The fill model (no real BLITZ fills exist)
- BLITZ enters at MARKET at the 1m open after a half-hour check close (11:00 ... 15:30 ET), stop 1.5 x ATR(5m), trailing after
  +1R, time / flat exits: every exit is a market or stop order (no resting target).
- ATLAS uses the same kind of entry and its 3 real fills were 10 / 12 / 16 ticks past the open, at 29 / 50 / 38 % of the entry
  minute's reach the trade's way (atlas-fills-2026-11-20.md).
- BLITZ's 385 entries of 2026: the entry minute reaches a median **9.25 pts** (mean 12.9) its way, twice ATLAS's 4.6. A momentum
  break keeps running in the first seconds. Measured proxy (0.39 x reach): median **15 ticks** on the entry (mean 20.6, p25 7,
  p75 29) = about $7 a micro more than the backtest; 0.29 x reach: median 11 ticks.

## 2. BLITZ alone, $300 a trade, fixed view (trades/wk, PF, $/month, max DD)

| Fills | 2026 Jan-Jun | Jul-Oct | 2021-25 |
|---|---|---|---|
| F0 stored (1 tick) | 8.5 / 1.50 / $1,226 / -$1,506 | 6.8 / 1.93 / $1,422 / -$1,198 | 8.6 / 1.04 / $122 / -$11,101 |
| FM measured (primary) | 8.5 / 1.26 / $679 / -$1,832 | 6.8 / 1.55 / $943 / -$1,596 | 8.6 / **0.80 / -$725** / -$38,941 |
| FL measured-low | 8.5 / 1.32 / $824 / -$1,741 | 6.8 / 1.65 / $1,069 / -$1,485 | 8.6 / 0.86 / -$483 / -$27,891 |
| T3 | 8.5 / 1.42 / $1,062 / -$1,678 | 6.8 / 1.83 / $1,301 / -$1,300 | 8.6 / 0.96 / -$120 / -$17,267 |
| T6 | 8.5 / 1.31 / $817 / -$1,936 | 6.8 / 1.68 / $1,120 / -$1,453 | 8.6 / 0.86 / -$483 / -$27,891 |
| T10 | 8.5 / 1.18 / $490 / -$2,333 | 6.8 / 1.51 / $879 / -$1,679 | 8.6 / 0.75 / -$967 / -$50,884 |

BLITZ's long-run edge (2021-25) is gone at any fill worse than 1 tick. 8.5 trades a week alone also breaks the 2-4/week band.

## 3. The book (Rapid EOD 50K, $165; research/onebook engine, ATLAS 10 ticks, 1,000 paths)

| Book | H1 $/mo, pass/fail %, days | H2 $/mo, pass/fail % | REF $/mo, pass/fail % | trades/wk H1 / H2, PF |
|---|---|---|---|---|
| B01 LIT only (the fail bar: 0.3% + 2 = 2.3%) | $795, 44.5/0.3, - | $787, 64.0/0.8 | -$39, 4.2/14.6 | 3.1 / 2.6, 3.49 / 2.71 |
| P = B11 plan (no BLITZ) | $4,918, 93.9/1.7, 25 d | $2,204, 89.7/3.9 | -$88, 9.8/81.4 | 7.2 / 5.5, 2.76 / 2.47 |
| PB + BLITZ, F0 | $6,022, 95.9/3.0, 19 d | $3,334, 94.9/1.8 | -$84, 13.9/83.4 | 15.7 / 12.3, 2.41 / 2.33 |
| **PB + BLITZ, FM** | **$5,431, 92.7/5.6, 20 d** | **$2,822, 91.6/3.5** | **-$148, 8.3/91.0** | 15.7 / 12.3, 2.32 / 2.22 |
| PB + BLITZ, FL | $5,488, 93.5/4.8 | $2,943, 92.7/3.0 | -$129, 9.4/89.6 | |
| PB + BLITZ, T3 | $5,750, 94.3/4.3 | $3,205, 93.8/2.4 | -$103, 12.0/87.0 | |
| PB + BLITZ, T6 | $5,413, 92.7/5.6 | $2,978, 92.3/3.1 | -$129, 9.4/89.6 | |
| PB + BLITZ, T10 | $4,968, 87.3/9.8 | $2,694, 90.2/3.9 | -$168, 7.0/92.3 | |
| QB = B12 + BLITZ (LIT full size), FM | $5,533, 91.4/7.3 | $2,901, 91.9/5.4 | -$153, 8.3/91.3 | |

First payout (median sessions from the buy): plan 41 / 47, + BLITZ FM 34 / 42 (about a week sooner).

## 4. Verdict (pre-set rule, DESIGN.md)
FM: H1 beats yes (+$513/mo), H2 beats yes (+$618/mo), fail 5.6% > 2.3% NO, REF not worse NO (-$59/mo). **Rejected.** 0 of 6
variants pass (F0 fails the fail bar too: 3.0%). No Decide card. BLITZ stays a paper shadow.
Caveat: the fill model is a proxy (ATLAS's 3 real fills scaled by BLITZ's own entry minutes); real BLITZ fills could be better
or worse. The verdict does not depend on it: even at 1 tick the eval fail is over the bar.
