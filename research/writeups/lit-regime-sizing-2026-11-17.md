---
title: LIT regime sizing (2026-11-17) - bigger / smaller LIT size by the day's regime - dealer gamma, VIX level and change, VXN-VIX spread, VIX term, prior day's range
family: risk
date: 2026-11-17
status: rejected - no regime separates LIT's R a trade the same way in Jan-Jun, Jul-Oct and 2021-25; today's flat LIT size stays
summary: Night helper 2026-11-17 (night-gex). Each live LIT trade (631, 120 in 2026, costs in) tagged with the regime known before the session (prior close) - SqueezeMetrics GEX sign and level, VIX level and 1-day change, VXN minus VIX, VIX/VIX3M, the prior NQ session's range percentile. 124 bucket cells (37 definitions: 2-3 buckets per feature, 2x2 pairs, cut points from Jan-Jun 2026 trades only, plus 8 cells with VIX / spread as a trailing-year percentile). The best Jan-Jun splits flip in Jul-Oct (VIX falling days +1.09R vs +0.61R in Jan-Jun, +0.14R vs +1.24R in Jul-Oct; low VXN-VIX spread +1.02R vs +0.48R in Jan-Jun, but Jul-Oct has 2 such trades and 2021-25 is the other way). 8 size rules (x1.25 good / x0.75 bad, same $ caps, eval two_week room_f 0.4 kept to session 80, funded 50K Monte Carlo, 200-draw placebo): one passes the money gate (VIX/VIX3M high x prior-day range: +$37 / +$119 a month at the LIT size, funded +$10 / +$28 a month) but its Jan-Jun gain is chance (placebo 0.53), its Jul-Oct sizes rest on 5 + 2 trades, VIX3M data ends 2026-09-17, 2021-25 goes the other way and the Jan-Jun 2-week eval pass drops 44.5 -> 42.0%. Rejected. Rapid EOD not run (no candidate). Paper only.
runs: none saved (grid in research/lit/regime_size.json, research/lit/regime_size_pct.json)
---

## For the owner (one minute)

**Answer: no.** LIT does not make clearly more per trade in any market mood that you can know before the session. Today's
flat size stays. Nothing to switch on; your steps: none.

| What | Jan-Jun $/mo | Jul-Oct $/mo (check) | 2021-25 $/mo | Builder 50K eval 2-week pass / fail (median sessions) | Funded 50K $/mo (H1 / H2) | Verdict |
|---|---:|---:|---:|---|---|---|
| **Today: flat LIT size** | **$5,562** | **$2,670** | **$25** | 44.5 / 0.0% (11) and 39.1 / 0.0% (12) | **$929 / $915** | keep |
| Best rule: VIX term high + yesterday's range big x1.25, VIX term high + range small x0.75 | $5,599 | $2,789 | $3 | 42.0 / 0.0% (12) and 39.1 / 0.0% (12) | $939 / $943 | rejected: chance in Jan-Jun, 7 Jul-Oct trades, data ends Sep 17 |
| VIX falling + low VXN-VIX spread x1.25 (best Jan-Jun split) | $6,286 | $2,569 | $84 | 54.6% (8) and 36.2% (14) | $954 / $905 | rejected: loses Jul-Oct |
| Positive gamma + small range yesterday x1.25 (the only split that held its direction in all 3 spans) | $5,981 | $2,641 | $81 | 37.0% (12.5) and 36.2% (14) | $899 / $867 | rejected: slower eval, less funded $ |
| 5 other 1.25x / 0.75x rules | $5,562-5,863 | $1,846-2,700 | -$6 to $52 | 38.7-48.7% / 23.2-39.1% | $921-963 / $869-918 | rejected |

Trades per week stay 3.12 / 2.56 / 2.38 in every row (sizing only, no trade skipped). Max DD: today -$2,196 / -$1,396
(LIT size); the best rule -$1,979 / -$1,396.

In plain words: the "good" regime of Jan-Jun is not the good regime of Jul-Oct. Jul-Oct was a quiet, low-VIX, high-Nasdaq-premium
market, so most of its trades sit in one bucket and the Jan-Jun winners' bucket hardly appears. A sizing rule built on Jan-Jun
mostly resizes noise.

## 1. What was tested (written before the runs)

Already in "Tested and rejected", so NOT re-run as single rules: GEX / DIX percentile, sign and 1-day change, VIX/VIX3M,
VIX9D/VIX, VVIX, SKEW, VIX1D/VIX, the options calendar as size tilts (`lit-market-context.md`, 2,520 variants); VIX top third
x1.25 and the busy-tape / day-range tilts (`lit-edge-2026-10-30.md`); low gamma x1.25 and x0.75 after a VIX jump (learn loop
2026-11-15). Their R a trade per bucket is still shown below as context, but they are not new candidates.

New here: **two-feature regime cells** (2 x 2), the **VXN - VIX spread** (Nasdaq vol premium over S&P vol), the **GEX level**
in $bn (not its percentile), the **prior NQ session's range percentile** (vs the 252 sessions before), and VIX / spread as an
adaptive trailing-year percentile.

| Feature (reading of the last close before the session) | Buckets | Source |
|---|---|---|
| gex_pos: dealer gamma > 0 | neg / pos | data/GEX_1d.csv |
| gex_lvl: GEX in $bn | H1 median 5.34; terciles 4.02 / 6.44 | data/GEX_1d.csv |
| vix: VIX close | median 17.9; terciles 16.9 / 18.9 | data/VIX_1d.csv |
| vix_chg: VIX 1-day % change | median -0.36%; terciles -2.0% / +2.0% | data/VIX_1d.csv |
| spread: VXN - VIX | median 4.9; terciles 4.3 / 5.6 | data/VXN_1d.csv |
| ts3: VIX / VIX3M | median 0.866; terciles 0.845 / 0.895 | data/CBOE_vol_1d.csv |
| rng_pct: prior NQ session high-low as a percentile of the 252 before | median 0.675; terciles 0.58 / 0.78 | NQ1! bars |

Cells: 7 features x (2 + 3 buckets) minus gex_pos's tercile = 34 definitions with 116 bucket cells (13 singles: 32 cells; 21
pairs x 4 = 84 cells) + 3 percentile definitions with 8 cells = **124 cells**. Size rules run in full (eval + funded +
placebo): **8** (the 6 biggest Jan-Jun gaps + the 2 whose direction held in Jul-Oct and 2021-25).

## 2. How it was tested

- `tools/lit_regime_size.py` on `tools/lit_edge` (the live LIT trades re-walked = run lit_live; LIT size rule; the live eval
  path two_week room_f 0.4 kept to session 80, fresh Builder 50K eval on every session; funded Builder 50K Monte Carlo at the
  live funded sizing: 60% of the room <= $1,500, winner <= $2,000; costs $1.90 a micro + 1 tick).
- Regime = the prior close strictly before the trade's session date (known by 16:15 ET, before the 18:00 open). Nothing looks
  ahead.
- Pick on H1 only: for each definition the bucket with the best and worst H1 average R (n >= 12) -> rule x1.25 best, x0.75 worst,
  others x1. Check: the same buckets in H2 and 2021-25. A size-up keeps the live caps (one rounding with the weekly stop,
  risk <= $990 at the LIT size; the eval's room_f 0.4 / $1,000 soft daily loss; funded per-trade max $1,500).
- Placebo: the rule's multipliers shuffled across each span's trades, 200 draws (share of draws with more $; low = real).
- Gate (`lit_edge.gate`): more $ in H1 and H2 at the LIT size AND on the eval path, no rise in 2-week fails, >= 2 trades/week.

### Data coverage (gaps)

| File | First | Last | Missing NQ sessions inside the range | Trades with no reading |
|---|---|---|---|---|
| GEX_1d.csv | 2011-05-02 | 2026-10-16 | 38 (US cash holidays: NQ trades, CBOE closed) | 0 (prior reading used, <= 5 days old) |
| VIX_1d.csv | 2021-10-15 | 2026-10-16 | 36 (holidays) | 0 |
| VXN_1d.csv | 2021-10-18 | 2026-10-16 | 38 (holidays) | 1 (H1, first VXN day) |
| CBOE_vol_1d.csv vix3m | 2015-01-02 | **2026-09-17** | 38 (holidays) + 21 NQ sessions after the end | **13 of 40 H2 trades** (+1 H1) |
| CBOE_vol_1d.csv vix1d | 2022-05-13 | 2026-09-17 | 35 (holidays) | not used |
| NQ range percentile | needs 60 sessions | | | 24 of 511 2021-25 trades (Nov 2021 - Jan 2022) |

The NQ bars start 2021-11-08, so "2021-25" here is Nov 2021 - Dec 2025 (511 trades).

## 3. Results: R a trade per bucket (LIT size, costs in)

Single features (n, average R). Good in H1 should be good in H2 and 2021-25 too; it is not.

| Feature | Bucket | H1 (pick) | H2 (check) | 2021-25 |
|---|---|---|---|---|
| gex_pos | neg / pos | 5, +2.09 / 75, +0.76 | 0, - / 40, +0.74 | 56, +0.11 / 455, +0.00 |
| gex_lvl median | lo / hi | 40, +0.87 / 40, +0.83 | 7, +1.44 / 33, +0.60 | 343, +0.00 / 168, +0.04 |
| vix median | lo / hi | 40, +1.01 / 40, +0.69 | 38, +0.69 / 2, +1.83 | 273, -0.00 / 238, +0.03 |
| vix_chg median | lo / hi | 40, **+1.09** / 40, +0.61 | 18, **+0.14** / 22, +1.24 | 262, -0.02 / 249, +0.05 |
| spread median | lo / hi | 40, **+1.02** / 39, +0.48 | 2, -0.51 / 38, +0.81 | 322, -0.05 / 189, +0.12 |
| spread terciles | lo / mid / hi | +1.29 / +0.61 / +0.36 | 0 / 8, +0.02 / 32, +0.93 | -0.06 / -0.03 / **+0.22** |
| ts3 median | lo / hi | 40, +0.65 / 39, +0.86 | 20, +0.20 / 7, +0.43 | 172, +0.08 / 339, -0.02 |
| rng_pct median | lo / hi | 40, +0.82 / 40, +0.87 | 29, +0.89 / 11, +0.36 | 326, +0.04 / 161, +0.00 |
| rng_pct terciles | lo / mid / hi | +1.15 / +0.60 / +0.79 | +1.03 / +0.19 / +0.46 | +0.02 / +0.09 / -0.02 |
| vix percentile (1 yr) | lo / hi | 33, +1.08 / 47, +0.68 | 38, +0.69 / 2, +1.83 | 282, -0.04 / 206, +0.12 |
| spread percentile (1 yr) | lo / hi | 12, +1.99 / 67, +0.53 | 4, -0.77 / 36, +0.91 | 292, +0.04 / 195, +0.01 |

Of 33 pick-able definitions only 2 kept the H1 direction in both H2 and 2021-25 (about what chance gives): VIX change middle
tercile > low tercile, and positive gamma + small prior range > positive gamma + big prior range. Both lose as size rules.

### The 8 size rules (x1.25 good / x0.75 bad; deltas vs today)

| Rule (H1 good / bad bucket) | LIT $ H1 / H2 / 21-25 | Eval $ H1 / H2 | 2-wk pass H1 / H2 | Funded $/mo H1 / H2 / 21-25 | Placebo H1 / H2 | Gate |
|---|---|---|---|---|---|---|
| VIX chg lo + spread lo / VIX chg lo + spread hi | +$4,415 / -$377 / +$3,027 | +$832 / +$577 | 54.6 / 36.2 | +25 / -10 / -1 | 0.005 / 0.105 | no |
| VIX hi + spread lo / VIX hi + spread hi | +$1,752 / -$584 / -$1,338 | +$458 / $0 | 44.5 / 39.1 | +34 / -15 / -6 | 0.21 / 0.83 | no |
| GEX lo + range hi / GEX lo + range lo | +$167 / -$114 / +$1,369 | +$403 / +$1,412 | 48.7 / 36.2 | +11 / +1 / -3 | 0.49 / 0.49 | no |
| **VIX/VIX3M hi + range hi / VIX/VIX3M hi + range lo** | **+$225 / +$439 / -$1,089** | +$720 / +$1,467 | **42.0** / 39.1 | +10 / +28 / -7 | **0.53** / 0.12 | money gate yes, rejected |
| VIX chg lo + range lo / VIX chg hi + range lo | +$1,837 / -$3,064 / -$1,478 | -$6,203 / +$879 | 38.7 / 23.2 | +23 / -46 / -7 | 0.075 / 0.97 | no |
| spread lo + range hi / spread hi + range hi | +$3 / -$898 / -$1,546 | +$521 / -$128 | 46.2 / 36.2 | -8 / -37 / -3 | 0.38 / 0.42 | no |
| VIX chg mid / VIX chg lo (terciles) | +$1,190 / +$109 / -$1,586 | -$3,044 / +$1,159 | 42.0 / 36.2 | +6 / +3 / +1 | 0.19 / 0.06 | no |
| gamma pos + range lo / gamma pos + range hi | +$2,553 / -$108 / +$2,873 | -$1,750 / +$236 | 37.0 / 36.2 | -30 / -48 / -1 | 0.10 / 0.39 | no |

Today: eval 2-week pass 44.5 / 39.1%, fail 0.0 / 0.0% (no rule changed the 0.0% fails).

**Why the one gate-passer is rejected:** its Jan-Jun gain is what a random reshuffle of the same sizes gives (placebo 0.53),
its Jul-Oct sizes rest on 5 trades up and 2 down, VIX3M has no reading after 2026-09-17 (13 of 40 Jul-Oct trades are x1),
2021-25 goes the other way (-$1,089), and the Jan-Jun eval passes slower (2-week pass 44.5 -> 42.0%, median 11 -> 12
sessions). +$10 / +$28 a month on a funded account is noise.

**Rapid EOD:** not run. The rule set says run it only when a regime clearly helps in both halves; none does.

## 4. Why (honest reading)

- H2 lives in a different regime: VIX below the H1 median on 38 of 40 trades, VXN-VIX above it on 38 of 40, gamma positive on
  all 40. Cut points picked on H1 leave the H1 "good" cell almost empty in H2, so H2 cannot confirm it, and when it can
  (VIX change: 18 vs 22 trades) the sign flips.
- LIT's target is already scaled by the VIX one-day move and its size by the stop, so the volatility level is in the trade
  already; what remains per regime is noise at 40-80 trades.
- 2021-25 (PF 1.01, no edge) shows bucket gaps of at most +/-0.2R, again with no stable sign.

## 5. Files

- `tools/lit_regime_size.py` (study; `pct` = the percentile check), results `research/lit/regime_size.json`,
  `research/lit/regime_size_pct.json`. Nothing in `engine/` or `live_model*.json` changed.
