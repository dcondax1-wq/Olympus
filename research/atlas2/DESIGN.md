# ATLAS v2: survive real fills. Pre-registration (written 2026-11-26 BEFORE any variant was run)

PAPER RESEARCH ONLY: no live file, size or switch changes; a pass = an ATLAS v2 card for the owner (rules + config diff), never
applied here. Code `research/atlas2/atlas2.py` -> `results.json`; write-up `research/writeups/atlas2-2026-11-26.md`.
Already rejected and NOT redone: limit at the 5m open / 4 ticks worse, +60 s entry, big-signal-bar skip, member hours, London
pause (atlas-fills-2026-11-20, F1-F6), and limit entries "at a better price" (atlas-windows-entries-2026-10-30). F1 is re-run
here only as the reference row V1 at the new calibrated costs.

Trades: tools/atlas_fills.units() (ATLAS's account units, the live code path, stored 1 tick in + 1 tick out), one position
(atlas_fills.to_T). **Calibrated costs (batch5, research/batch5/fills.json): market entry 12 ticks (3 real fills: 9 / 11 / 15
vs the model), market / stop exits 2 ticks (not measured: assumed), target (resting limit) 0, limit entries 0 slippage.**
Limit fills are honest: filled only when price trades THROUGH the limit by 1 tick inside the timeout (1m bars in 2026; 2021-25
has only 5m bars: the entry 5m bar's low / high and the next bars inside the timeout); a target reached before the fill = no
trade; a trade whose stored exit came before the fill = no trade; stop and target PRICES unchanged (the better entry shrinks
the risk and grows the R).

## Variants (8, counted)
- V0 today: market entries, EMA + MACD + S/R, at 12 / 2.
- V1 limit at the 5m open, 5 min (= F1, reference).
- V2 **limit at the signal level 0.25 R inside the signal** (x = -0.25 R from the open), 15 min.
- V3 limit 0.5 R inside, 30 min.
- V4 market, **EMA removed** (MACD + S/R).
- V5 V2 + EMA removed.
- V6 **regime switch**: market, all members; ATLAS takes a trade only while the rolling mean R of its last 40 signals (every
  signal tracked on paper at the same costs, causal: closed before the entry) is > 0; otherwise paper only.
- V7 V5 + the V6 switch (on V5's own signals).

## Scoring and gate
Fixed $250 risk a trade, real days: trades / week, PF, net $, $ a month, max DD for 2021-25, 2026 H1, 2026 Jul-Oct, and
walk-forward = each calendar year 2022, 2023, 2024, 2025 alone. Real engines: the funded 25K payout path
(atlas_fills.score_funded: $ a month to the owner, first payout, lost %, H1 / H2 / 2021-25), the Rapid EOD 25K combo (LIT +
ATLAS lane, atlas_fills.rapid_rows), and the Builder 50K / 25K LIT + ATLAS combo lanes (research/plans/rank.py with ATLAS =
the variant: eval pass / fail, net 6 months).
**Pass = ATLAS v2 card:** fixed net $ and PF better than V0 in 2021-25 AND 2026 H1 AND 2026 Jul-Oct; walk-forward net better in
>= 3 of the 4 years; funded 25K $ a month not lower in H1 and H2 and higher in 2021-25; 1.5-4.1 trades a week; 2021-25 PF >= 1.0
(a long-run edge at real fills). If none passes and V6 / V7 keeps 2021-25 at least flat while giving up < 15% of the 2026 money,
the verdict is "keep ATLAS only in 2026-like markets with the regime switch"; otherwise "ATLAS stays as is, 2026-like only, no
switch earns its keep".
