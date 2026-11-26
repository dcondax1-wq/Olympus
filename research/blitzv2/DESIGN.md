# BLITZ v2: make the 3rd pillar worth real money, or prove it can't be. Pre-registration (2026-11-26 ~12:10 ET)

PAPER RESEARCH ONLY, no live file touched. Step 1 (done before this file): `anatomy.py` on the DIAGNOSIS spans only = 2021-24
(5m) + 2026 Jan-Jun (1m). Facts that shaped the variants: (a) in 2026 H1 nearly every bucket is positive, in 2021-24 nearly
every bucket is ~0 and the signs flip (band distance, VIX, check time, weekday) = BLITZ is a regime bet on trending years;
(b) exits: time exits +0.45R, stops -0.9R; the 30-minute clock cuts the trend-day runners that carry the money; (c) the only
bucket positive in BOTH spans: stop >= 0.25% of price (2021-24 +0.042R, H1 +0.336R) = when the 1.5 x ATR5 stop is small
relative to price, costs eat the edge. The CHECK spans (2025, 2026 Jul-Nov 20) were not looked at before writing this.

Engine: today's rule = tools/blitz25k_lib.run (== engine/blitz.py, parity checked in blitz_review). The variants run on
`research/blitzv2/blitzv2.py`, a port of the same executor (parity vs today's trades checked and reported), 2026 on 1m,
2021-25 on 5m (the same rule), $150 risk a trade, $1.90 a micro + 1 tick per market / stop fill.

Variants (8, counted):
- V1 noise-area exit (the original intraday-momentum design): no 30-minute clock, no trail; at every check close (the same
  30-minute grid) exit when the close is back inside max(band edge, VWAP) (long: close < max(upper band, VWAP)); the 1.5 x
  ATR5 hard stop stays; flat 15:55
- V2 no time exit only (today's stop + 1.5R trail after 1R; ride to the trail or 15:55)
- V3 cost gate: trade only when the 1.5 x ATR5 stop >= 0.25% of price
- V4 opening drive added: extra checks 09:45-10:30 every 15 min (same 09:30 anchor, the lib's "od" window)
- V5 entry trigger: a limit back at the band edge (10 minutes) instead of market at the next open
- V6 one ride a day: only the day's first band break, V1 exit
- V7 V1 + V3;  V8 V1 + V3 + V4
Scores: trades/week, PF, net $, $/month, max DD per span (2026 H1, 2026 Jul-Nov 20, 2021-25, each year), walk-forward (6-month
windows every 3 months, 2021-11..2026-11, 5m: wins vs today on $), random-side placebo (20 seeds, same bars / stops), MFFU
Rapid EOD 25K + Builder 25K 40-session pass / fail / median (daily level, $150 a trade), and the COMBINED account path:
LIT (live) + ATLAS (3 members) + BLITZ on one 50K, one position at a time, vs LIT + ATLAS without BLITZ (pass / fail /
median, 2026 halves + 2021-25); daily-$ correlation of BLITZ with LIT and ATLAS.
Verdict rule (fixed now): a BLITZ v2 card only if a variant beats today in $/month in 2026 H1 AND Jul-Nov AND 2021-25, with
2021-25 PF >= 1.15, every year 2022-25 >= $0, walk-forward >= 10/18, placebo p <= 0.05 on 2021-25, AND it adds to the combined
path (pass up or fail down in both 2026 halves, 2021-25 not worse). No variant clears it -> "retire BLITZ" with the why.
