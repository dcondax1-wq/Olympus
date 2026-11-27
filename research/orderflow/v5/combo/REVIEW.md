# REVIEW: v5 "combo" (adversarial check, 2026-11-27)

Verdict of the review: **the "weak, no YES-candidate" verdict holds.** I re-ran core.py from a separate script, without
rewriting any of their files, and got the same table to the cent. C0 had 63 trades, +0.295R, +$2,648. C2 had 55 trades,
+0.392R, PF 1.76, +$2,849, DD $1,164, halves +0.383 / +0.406, gap +0.70 (+1.288 / +0.267), p 0.0878, Holm 0.5268.
C6 had 31 trades, +0.496R, p 0.1238. My scripts are in the scratchpad `combo_rev/` folder.

## What I tried to break
| check | result |
|---|---|
| Look-ahead (LA) | None. A LIT level is used only if its known index is before the signal bar i (session box = its last bar, build-up = 2nd fractal + 2 bars, pd/pw/pm/gaps = before the day starts). The first breach is searched after that index and up to i. Depth uses lows/highs of bars j..i and ATR14 at i, so everything is known at bar i's close. The trading-day key maps correctly (`2026-09-28` = the session that opens 09-27 18:00). |
| Look-ahead (AT/S1/VX/IO) | None. HTF trend values are counted from the 5m bar on which the HTF bar closes. S1 uses the previous session. VIX uses the last close before the day. IO uses the 09:30 open, and trades start at 09:45. |
| Bar alignment NQ_5m vs pc_days | Aligned: median difference 0.25 pt, and closes are within 1.5 pt. Shifting by one bar gives about 24 pt, so no bar is offset. 12 of 76 signal bars have wicks more than 1 pt apart, which is noise and not a leak. |
| Fills / costs | The same E5 simulator as v5/levels, which the levels REVIEW already checked. 0 "marketable" fills, 34 fills at the level, 21 at market +18 ticks. $1.90 RT is in. Gross mean R before costs and slippage is +0.44, against +0.39 net. |
| Design after results | Not by file times: DESIGN 09:44:24, core 09:45:22, run 09:45:42, results/frozen 09:45:48, RESULT 09:46:47. An earlier unsaved run elsewhere can't be ruled out. |
| Extra variants / Holm | C1-C6 only. Holm is over 6 (C2: 6 x 0.0878 = 0.527). The frozen pick (C2, C6) follows the rule. |
| Overlaps | 0 overlapping trades in C0 or C2. C2 books are a strict subset of C0 (no trade unblocked). |
| Halves | Correct: 26 / 25 days by date. |
| Placebo | It matches the design. A placebo restricted to the 38 ORB candidates gives gap +0.75, p 0.09, so level type does not confound it. The shuffle is per candidate and not clustered by day, which makes p slightly optimistic. |

## Errors in the write-up (none changes the verdict)
1. **Trades per week and $/month use 51 "days", but 7 of them are Sundays** (no RTH bars), so there are 44 real trading
   days. C2 is **6.25/wk** (not 5.39) and C0 is 7.16. On 44 days, C2's $/month is about **$1,360** (not $1,173), so the
   dollar figure was understated. Both errors are also in frozen.json `in_sample`.
2. **"9 of the 11 removed are opening-range fades" is really 10 of 11** (one is pdh). Only **8 booked trades** are removed
   (6 losers about -1R each, plus 2 winners +1.96R and +1.85R). The other 3 were already blocked by the busy rule.
3. Thanksgiving 11-26 (a half day) is traded: in C2 that is one orl loser (-0.53R). Without that day C2 is 54 trades,
   +0.409R, +$2,857.

## What C2 really is (worth knowing before the OOS run)
- LA is almost automatic for non-ORB levels: 37 of 38 onh/onl/pdh/pdl candidates are flagged, because those levels are
  themselves LIT levels (pd, session boxes). So C2 is really a filter on ORB fades: 28 flagged, 10 not.
- All of the effect is in **orh**: flagged +0.75R against not flagged -0.56R (7 off), p 0.036 inside orh. For **orl** the gap
  is about zero (-0.09, p 0.49). The older-half gap of +1.29 rests on just 5 unflagged candidates, all of them losers.
- This is a small-sample, one-sided split. Read the OOS result for C2 as an "ORB-high fade needs a real LIT sweep" test.
  Don't treat it as a general context edge.
