# ICT lab 2026-11-25: design + pre-registration (written BEFORE the run)

Owner 2026-11-25: "Quarterly theory, time, price, all those concepts online, confluences, macros, windows ... I've seen it work.
... you need to test it other ways. Just do more."  Paper research only. Futures data only: `data/NQ_5m.csv`, `data/ES_5m.csv`
(TradingView CME NQ1!/ES1!, back-adjusted; NQ 2021-10-17 .. 2026-11-20, ES 2025-04-13 .. 2026-11-20 only).
Code: `research/ictlab/ict_lab.py` (one file, re-uses `tools/popular_ict.py` data loader / fill engine / LIT sizing).
All clocks are New York time (ET). 5m bars: anything finer than 5 minutes (22.5-min cycle edges, 02:33 macro start) is rounded to the
5m bar that contains it (said again in the results).

Prior work checked first (`docs/TESTED_AND_REJECTED.md`): Silver Bullet 10-11, Judas, PO3/AMD, ICT 2022, SMT-as-trigger and
LIT keep-only-SMT were already tested and rejected (2026-11-20, 2026-11-23). They are re-run here only because the owner asked
for the NEW test views (year / quarter heat map, walk-forward, 40-session eval windows); the earlier verdicts stand unless these
views say otherwise.

## 1. The concepts as taught (definition + source)

| id | concept | definition used here (as taught) | source |
|---|---|---|---|
| QT | Quarterly Theory / AMDX | The day is 4 quarters of 6 h: Q1 18:00-00:00 Asia (Accumulation), Q2 00:00-06:00 London (Manipulation), Q3 06:00-12:00 NY AM (Distribution), Q4 12:00-18:00 NY PM (X = reversal / continuation). Each 6 h quarter is 4 x 90 min, each 90 min is 4 x 22.5 min, same A-M-D-X order. **True Day Open (TDO) = 00:00** (open of Q2). **True Session Opens (TSO)** = open of each session's Q2: 19:30 Asia, 01:30 London, 07:30 NY AM, 13:30 NY PM. Trade idea: the Q2 (manipulation) move goes the wrong way from the true open, Q3 (distribution) goes the real way: buy below the true open, sell above it. | Daye (@traderdaye), "Quarterly Theory" posts / course 2023-24; builds on ICT's midnight-open / Power of 3 |
| MAC | ICT macros | Short algorithmic windows where price is delivered to liquidity or into an FVG: 02:33-03:00, 04:03-04:30, 08:50-09:10, 09:50-10:10, 10:50-11:10, 11:50-12:10, 13:10-13:40, 15:15-15:45. | ICT (Michael J. Huddleston), Twitter/X macro posts 2022 and 2022 YouTube mentorship |
| SB | Silver Bullet | 03:00-04:00, 10:00-11:00, 14:00-15:00: the first FVG that forms in the hour; enter at the FVG, stop beyond the FVG's first candle, target liquidity (here 2R). | ICT, "Silver Bullet" lectures, 2023 YouTube |
| JUD | Judas swing | After 00:00, London makes a false move beyond the Asian range / midnight open, then closes back through the midnight open: trade the reversal. | ICT, 2016-17 mentorship ("Judas swing"), Market Maker series |
| PO3 | Power of 3 (AMD) | Daily candle = open, manipulation against the bias, then distribution; bullish day: low forms below the open in the morning. Open = 00:00 midnight open (ICT) or the 18:00 Globex open. | ICT, "Power of Three", 2016-17 mentorship |
| SMT | SMT divergence NQ vs ES | At a swing / session extreme, one index makes a higher high (lower low) and the other does not: bearish (bullish) divergence, fade the one that swept. **ES data from 2025-04 only: SMT results exist for 2025-04 .. 2026 only.** | ICT, "Smart Money Technique", 2016-17 mentorship |
| IPDA | IPDA data ranges 20 / 40 / 60 days | Highest high / lowest low of the last 20, 40, 60 trading days; above 50% = premium (sell), below 50% = discount (buy). | ICT 2016-17 mentorship, month 4 ("IPDA data ranges") |
| NWOG / NDOG | New Week / New Day Opening Gap | NWOG = Friday 17:00 close to Sunday 18:00 open; NDOG = 17:00 close to 18:00 open each day. The gap and its 50% (consequent encroachment, CE) are magnets / support-resistance: price is drawn to the CE. | ICT, 2023 YouTube lectures (NWOG / NDOG) |
| OTE | Optimal Trade Entry | After an impulse leg, enter on a 62-79% retrace (70.5% the sweet spot), stop beyond 100%, first target the -27% extension. | ICT 2016-17 mentorship, month 1 ("OTE") |
| KZ | Killzones | Asia 20:00-00:00, London 02:00-05:00, NY AM 07:00-10:00 (index futures 08:30-11:00), London close 10:00-12:00, NY PM 13:30-16:00. | ICT, killzone lectures (2016-17 mentorship, 2022 mentorship) |
| DOL | Daily bias from PDH / PDL draw on liquidity | Previous day closed in its upper half -> draw on liquidity = the previous-day high (PDH), bias long; lower half -> draw = PDL, bias short. Target = the draw. | ICT 2022 mentorship ("daily bias", "draw on liquidity") |
| CBDR | CBDR / Asia range standard deviations | CBDR = 14:00-20:00 range of the prior evening; Asia = 20:00-00:00. Project the range height 1-4x above / below: the high or low of the day tends to form at 2-4 SD (best when CBDR is small). | ICT forex mentorship ("Central Bank Dealers Range", "Asian range standard deviations") |

## 2. Standalone rules (one trade a day max, 5m, MNQ, costs in)

Common: first fill wins; LIT sizing ($800 risk up to a 20-pt stop, then 800 x 20 / stop, floor, max 40 micros, < 1 = skip),
$1.90 a round trip + 1 tick slippage on market / stop entries, stop 1 tick beyond the structural extreme, flat 15:50,
target 2R unless the concept names its own target (written in the row).

| id | rule |
|---|---|
| S_QT_TDO | Daily AMDX: 06:00-12:00, first 5m close back through the TDO after Q2 (00:00-06:00) traded on the other side of it -> enter next bar; Q2 low below TDO -> long, stop 1 tick under the 00:00-entry low; Q2 high above -> short (both sides: the first cross wins). 2R. |
| S_QT_TSO | NY 90-min AMDX: Q2 07:30-09:00 = manipulation vs the 07:30 TSO; in Q3 09:00-10:30 first 5m close back through the TSO -> enter next bar, stop 1 tick beyond the 07:30-entry extreme. 2R. |
| S_QT_225 | 22.5-min AMDX inside the 09:00-10:30 cycle: 09:22.5-09:45 (Q2 sub-quarter, 5m bars 09:20-09:45) sets the false move vs the 09:22.5 open (bar 09:20 open); 09:45-10:07.5 first close back through it -> enter, stop beyond the 09:20-entry extreme. 2R. |
| S_MAC_ALL / S_MAC_RTH / S_MAC_LDN | First FVG whose 3rd candle closes inside a macro window -> limit at the FVG edge, stop 1 tick beyond the FVG's first candle, live until the window end + 30 min. ALL = all 8 windows, RTH = 09:50, 10:50, 11:50, 13:10, 15:15 (+08:50), LDN = 02:33, 04:03. 2R. |
| S_SB_03 / S_SB_10 / S_SB_14 / S_SB_ALL | Silver Bullet: first FVG in the hour (03, 10, 14 ET), limit, stop beyond the first candle, order live to the hour end. 2R. ALL = first of the three each day. |
| S_JUD | Judas as in `popular_ict.py` (Asia 20:00-00:00, midnight open, 02:00-05:00 false move then close back through the midnight open). 2R. |
| S_PO3 | PO3/AMD as in `popular_ict.py`. 2R. |
| S_SMT | 09:30-12:00: NQ trades above its 00:00-09:30 high while ES stays below its own 00:00-09:30 high on the same 5m bar (bearish SMT) -> short at the next 5m close back below NQ's 00:00-09:30 high, stop 1 tick above NQ's high since the sweep; mirror for lows. 2R. ES 2025-04+ only. |
| S_IPDA20 / 40 / 60 | Bias = discount (09:30 open below the 50% of the 20 / 40 / 60-day range) -> long, premium -> short. Enter 09:30 open, stop 1 tick beyond the 00:00-09:25 low (long) / high (short), skip if the stop is > 80 pts. 2R. |
| S_DOL | PDH/PDL draw: bias as in section 1; enter at the 09:30 open if the draw is still untouched and is >= 1R away, stop 1 tick beyond the 00:00-09:25 extreme, **target = the PDH / PDL**. |
| S_NWOG / S_NDOG | At 09:30, if the gap (>= 4 pts) CE is untouched since 18:00: trade toward the CE (price above CE -> short, below -> long), stop 1 tick beyond the 00:00-09:25 extreme, **target = CE** (skip if < 1R away or the stop > 80 pts). NWOG Mon-Fri of that week; NDOG every day. |
| S_OTE | At 10:00 the 09:30-10:00 leg: close in its top third -> bullish leg, limit buy at the 70.5% retrace, stop 1 tick under the leg low (100%), **target the -27% extension above the leg high**; bottom third mirror. Order live 10:00-12:00. |
| S_KZ | NY AM killzone (08:30-11:00) sweep of the London killzone (02:00-05:00) high / low and a 5m close back inside within 12 bars -> reverse, stop 1 tick beyond the sweep extreme. 2R. |
| S_CBDR / S_ASIA | CBDR (14:00-20:00, prior evening) or Asia (20:00-00:00) range height R: in 02:00-11:00 a limit short at high + 2R, long at low - 2R; stop 1 tick beyond 4 SD (high + 4R / low - 4R); **target = the range edge (0 SD)**. Only when the range is <= its 60-day median (ICT: small CBDR). |

## 3. Confluence filters on LIT and ATLAS (each in 2 modes: ONLY = skip trades without it; UP = x1.5 size with it, x1 without)

Trade side aligned = long below / short above the level.

| id | the trade has it when ... |
|---|---|
| F_MAC | the entry is inside a macro window |
| F_SB | the entry is inside a Silver Bullet hour |
| F_KZ | the entry is in the London (02:00-05:00) or NY AM (08:30-11:00) killzone |
| F_QT90 | the entry is in the 2nd or 3rd 90-min quarter of its 6 h quarter (M or D phase) |
| F_QT225 | the entry is in the 2nd or 3rd 22.5-min quarter of its 90-min cycle |
| F_TDO | side aligned with the True Day Open (00:00) |
| F_TSO | side aligned with the current session's True Session Open (19:30 / 01:30 / 07:30 / 13:30) |
| F_PO3 | side aligned with the 18:00 Globex open |
| F_IPDA20 / 40 / 60 | side aligned with the 20 / 40 / 60-day range's 50% (long in discount, short in premium) |
| F_DOL | side = the PDH / PDL draw bias |
| F_NWOG | side toward the NWOG CE (long below it, short above) |
| F_OTE | entry sits 62-79% deep in the session's 00:00-entry range, measured the trade's way |
| F_CBDR | the trade's sweep extreme (LIT `sweep_ext`, ATLAS the entry) lies in the 2-4 SD band of CBDR or Asia |
| F_SMT | ES did not make the matching new high / low in the 30 min before the entry (2025-04+ only; before that = no filter) |

## 4. Combinations (pre-listed, 10)

As LIT / ATLAS filters (both modes): C1 F_MAC+F_TDO, C2 F_SB+F_IPDA20, C3 F_KZ+F_DOL, C4 F_TDO+F_IPDA20+F_DOL, C5 F_QT90+F_TSO,
C6 F_MAC+F_OTE, C7 F_CBDR+F_KZ, C8 F_SMT+F_KZ (2025-04+), C9 F_TDO+F_NWOG, C10 F_SB+F_TDO+F_DOL.
As gates on standalones: G1 S_SB_10 if F_TDO, G2 S_MAC_RTH if F_IPDA20, G3 S_OTE if F_DOL, G4 S_KZ if F_TDO+F_IPDA20,
G5 S_QT_TSO if F_DOL, G6 S_CBDR if F_KZ (always true by time: = S_CBDR in 02:00-05:00 / 08:30-11:00 only).

## 5. The test views (the owner's "other ways"), all side by side

LIT = the live replay `research/lab/backtest_live.json` (real 50K size, 2021-11 .. 2026-10-16). ATLAS = `tools/atlas_health.stream()`
(the account's one-position stream) at $250 fixed risk a trade (the health tool's fixed view). Standalones at LIT size.
- (a) $ per calendar year 2021 (Nov-Dec only) .. 2026 (to the data end) and per quarter: heat map. Filters: $ change vs the strategy as is.
- (b) Walk-forward, rolling 3 months: at each quarter start from 2022-05, look at the last 6 months; trade the variant the next 3
  months only if it beat the baseline (standalone: made money) over those 6 months; otherwise stand aside (standalone) or run the
  baseline (filters). Also a per-concept pick: the best of the concept's variants (or none) on the last 6 months.
- (c) MFFU eval on every 40-session window (start every session): Builder 50K for LIT and standalones (target $3,000, EOD trailing
  $2,000, lock at +$100), Builder 25K for ATLAS (target $1,500, trailing $1,000). Pass %, fail %, median days to pass. All, 2026.
- (d) $/month and max drawdown at that size, costs in, 2021-11 .. end and 2026.
- (e) 2026-only view (Jan .. data end; what the owner has seen) labelled as such.
- (f) Luck correction: `research/ideamill/DESIGN_v3.md` is not in this repo (searched 2026-11-25), so the count is done here:
  placebos (standalone: same trades with a random side, 500 draws; filters: random keep-sets of the same size / random x1.5
  sets, 500 draws) give each variant a p-value per year; the same "card" test is run on the placebos, and the number of cards
  expected by luck = variants x placebo pass rate is printed next to the real count.
- Verdict words: "works every year" (better in >= 4 of 5 full years 2022-26 AND walk-forward positive), "2026 only" /
  "2026 H1 only", "mixed", "never" (worse in >= 4 of 5 years). Card = walk-forward positive AND >= 4 of 5 years better AND
  luck p < 0.05 AND 2-4 trades/week for a standalone.
