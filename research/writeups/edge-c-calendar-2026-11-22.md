# Edge hunt lane C: calendar and money-flow timing on NQ (2026-11-22)

**Headline: nothing wins. 174 variants, 0 pass.** No calendar window beats costs in both 2026 halves AND 2021-25 with
a result that survives a permutation test. The one cell that was positive in all three spans (Monday long) is a lottery
ticket: its top 3 trades are 137-493% of the net in every span, and without them it loses in all three. Both size dials
(bigger or smaller LIT on the windows) are chance: LIT makes money, so x1.5 on any set of days adds money, but no window
beats random days of the same count. Paper only; `live_model*.json` untouched; no Decide card.

## Method
- Data: futures only, `data/NQ_5m.csv` (TV NQ1!, back-adjusted, 2021-11-08 to 2026-10-16). Spans: 2021-25, 2026 Jan-Jun (H1,
  the only pick period), 2026 Jul-Oct (H2, untouched).
- (a) Standalone: window day, entry at a bar open (09:30, or 15:00 / 15:25 / 18:00 for the time-of-day tests), stop 1 tick
  beyond the extreme of the last 12 five-minute bars (structural, min 8 pts), size from the stop by the LIT rule ($800 up to a
  20-pt stop, then 16,000 / stop, micros 1-40, no trade under 1), one target (none / 1.5R / 3R) else flat at 15:55 (Globex
  test: 09:25). Costs 1.45 pts a micro round trip (1 tick each way + $1.90), stop wins a same-bar tie. All flat before 16:10, so
  MFFU-legal. The Globex "overnight" is the legal 18:00 to 09:25 session (the 16:00-18:00 hold is not allowed on MFFU).
- (b) Dial: LIT's real 631 trades (`research/lab/backtest_live.json`), P&L x f on window days, f capped at 40 micros and ~$990 risk
  (the $1,000 DLL). Eval = MFFU 50K ($3,000 target, $2,000 EOD trailing), starts on every session, 10-session (2-week)
  horizon. Simplified: it does not use the live room_f 0.4 sizing path, so read pass % as relative to the base, not absolute.
- Picks on H1 only: target option per window, direction per window, pension threshold. Then H2 and 2021-25 read once.
- p-values: permutation (3,000 draws): same number of random days in the same span, directions shuffled; one-sided
  "random does as well". Bootstrap 95% CI on $/trade is in `results.json`. Tod rows with all days and a fixed side have no
  null (p = 1.0, ignore); the momentum / fade rows do (sign shuffle).
- `.claude/skills/strategy-test/SKILL.md` and `docs/ACCOUNT_RULES.md` do not exist in this repo; I followed CLAUDE.md's strategy
  rules and `research/lit/mffu_rules.json` (DLL $1,000, 40 micros, consistency only in funded). Overlap with the S2 edge
  (2026-11-15) and public-strategies (2026-11-17) tests: those tested TOM / OpEx as dials and as long-only; this adds structural-stop
  entries, the shorts, quarter-end, pension, last hour and DOW, and a permutation null per cell. Holidays / roll / FOMC skipped.

## Standalone, picked target (net $ at LIT size; events = window days; p = permutation)
| Window (long unless noted) | trades/wk | H1 net (p) | H2 net (p) | 2021-25 net (p) | Both halves + 2021-25? |
|---|---|---|---|---|---|
| Turn of month last 2 (ev 12/8/100) | 0.4 | +10,205 (.14) | -1,862 (.36) | -33,208 (.96) | no |
| Turn of month first 3 (18/12/147) | 0.7 | +6,512 (.28) | -47 (.31) | +19,715 (.12) | no (H2) |
| Turn of month all 5 (30/20/247) | 1.1 | +16,717 (.23) | -1,909 (.44) | -13,492 (.50) | no |
| OpEx week (30/20/248) | 0.9 | +28,525 (.06) | -7,736 (.84) | -54,157 (.95) | no; OpEx week SHORT p .002 in 2021-25 but loses -8.8k |
| OpEx Friday (6/4/48) | 0.1 | -1,384 | -1,783 | -19,250 | no (short: +1.5k / -0.8k / +24k, 3-4 trades a half) |
| Monday after OpEx (6/4/50) | 0.2 | -1,274 (.54) | +21,938 (.02) | +31,977 (.01) | no (H1 loses; 4 trades in H2 with 1 winner) |
| Quarter end last 3 (6/3/51) | 0.2 | +14,146 (.06) | -737 | -15,527 | no |
| Quarter start first 2 | 0.1 | -248 | -2,246 | -4,127 | no |
| Pension: month >= +-5% then fade last 3 days (7/7/64) | 0.3 | +10,241 (.02) | -1,782 | +3,332 | no (H2) |
| Mon long (26/17/213) | 0.9 | +1,514 (.44) | +16,952 (.14) | +28,034 (.075) | **yes, but a lottery** (below) |
| Tue long | 0.9 | +39,924 (.005) | +8,050 (.23) | -25,315 | no (2021-25) |
| Wed / Thu / Fri long, all five DOW short | 0.8-0.9 | mixed | mixed | mostly negative | no; Thu short is the only one significant in H1 and 2021-25 (p .006 / .009) but loses H2 -4.8k |
| Last hour 15:00 momentum (123/86/1,031 days) | 4.0 | +16,494 (.05) | +4,081 (.18) | -48,705 (.04) | no (2021-25 loses, though better than random) |
| Last hour long / fade, last 30 min momentum | 4 | long +17.8k, fade -4.9k | long +1.9k, fade -5.9k | all negative | no |
| Globex overnight long 18:00-09:25 | 4.5 | +17,033 | +29,664 | -20,002 | no (2021-25; 76-79% 2-week fails) |
| Intraday long 09:30-15:55 / shorts | 4.2 | long +22.6k, short -21.9k | long +7.8k, short -7.5k | long -50.7k | no |

Win % is low everywhere (4-40%) except the last-hour rows (38-45%, PF 1.1-1.6 in 2026, PF 0.7-0.8 in 2021-25). 2026's
profits are the 2026 uptrend: every long cell with a time exit makes money in 2026 and loses in 2021-25.
Correlation with LIT's daily P&L: -0.13 to +0.15 for all cells (0.15 only for last-hour momentum in H1), so they are not
the same bet, but none pays.

### The one cell that passed the letter of the rule: Monday long, 09:30 to 15:55, no target
H1 +$1,514 (258 / month), H2 +$16,952, 2021-25 +$28,034 (571 / month), 0.9 trades a week, win 13-22%, PF 1.2-3.6, max DD -$4.7k /
-$4.1k / -$24.8k, 2-week eval pass 5.7 / 11.6 / 10.0%, fail 0.8 / 0 / 1.6%, corr LIT -0.03 / -0.09 / 0.00. Why rejected:
(1) top 3 trades = 493% / 137% / 168% of net, net without them -$5.9k / -$6.3k / -$19.2k, max 40 micros: a few big trend
Mondays, which also breaks the funded 50% best-day rule; (2) permutation p .44 / .14 / .075; (3) the chance that random
long-only day sets of the same sizes are positive in all three spans is 6.6%, and 10 DOW cells were tried; (4) 2024 lost -$13k.

## Size dial on LIT (x1.5 and x0.5 on the window days, 52 variants)
No dial is better than random days of the same count in H1 (the pick period): best H1 p-values .10 (TOM last 2 at x0.5) and .18-.26
(Fri / Wed / TOM first 3 at x1.5). The x1.5 deltas are positive in all three spans for TOM first 3 (+3,171 / +1,695 / +90),
Tue (+1,956 / +2,437 / +2,361) and Wed (+4,016 / +1,984 / +4,991; 2021-25 p .055), but that is "more size on a winning
strategy", not timing: the p-values are .14-.66, and 2021-25 fail rates also rise (6.6 to 7.7-8.4%). The only p < .05 cells
(qstart first 2 H2 p .02 on 4 days; Thu x0.5 2021-25 p .045) point the other way in the other spans. Nothing to adopt; if
size is wanted, the way to get it is the existing room rule, not a calendar.

## Tried and failed (all of it)
Turn of month (last 2 / first 3 / all 5, long and short); OpEx week, OpEx Friday, Monday after OpEx (long and short);
quarter end last 3 and quarter start first 2 (long and short); month-end pension fade at 2 / 3 / 5% thresholds; day of
week Mon-Fri long and short; last-hour long / momentum / fade; last 30 min momentum; Globex overnight long / short;
intraday long / short; each with 3 target options (none / 1.5R / 3R); dials x1.5 and x0.5 on 13 windows.
**Variants logged: 174 (standalone and tod rows + dials), plus the deep dive.** With ~170 looks, 5-9 "p < .05" hits are
expected by chance; I saw 11 (9 standalone, 2 dial) and every one fails a span or points the other way.

## Limits (honest)
Calendar windows have 3-30 events a half-year; H1/H2 verdicts are mostly noise at this count. NQ only (ES not used as a
cross-check); early-close sessions drop out of the 15:55 exits. The eval path is simplified (see above). Tue long
H1 +$39.9k comes from 22 trades with 40-micro size on a 22% win rate, the same lottery shape.

Code: `research/edge_hunt/c/edge_c.py` (run), `report.py` (table), `deepdive.py` (Monday cell + joint null); numbers `results.json`.
