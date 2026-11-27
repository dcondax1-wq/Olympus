# REVIEW: v5 "levels" (adversarial check, 2026-11-27)

Verdict of the review: **the NO holds.** I re-ran every number from core.py in a separate script (none of their files were
rewritten) and got the same table to the cent: L2 40 trades, -0.479R, PF 0.76, -$652, DD $1,162, halves -0.25 / -0.86,
gap +1.00 / -0.13, p 0.1394, Holm 0.8364; V0 63 trades +0.295R +$2,648 p 0.026. `oos.py` runs and prints "0 new days".

## What I tried to break, and what I found
| check | result |
|---|---|
| Look-ahead | None found. Signal from the closed bar i, entry from bar i+1; GX profile ends 09:30; VWAP/sd use bars before i; naked-POC check stops at 09:30; PW = previous week. The NQ_5m offset is a median over the whole day (tiny leak), but it is 0 on every traded day (+/-0.5 only on Sundays and Thanksgiving). |
| Fills too good | No. Limit fills at L need 1 tick through, the fill bar checks only the stop, the market fallback pays +18 ticks, and stop fills are 2 ticks worse. Rule (c) "stop in the entry bar = no fill" can never fire (the stop is always below L - 1 tick, so (b) fills first). That does no harm. |
| Costs | In. $1.90 a round turn, $2 a point, R = net $ / risk $. Gross R before costs and exit slippage is still negative (L2 -0.35R, L4 -0.56R, L5 -0.38R), so costs are not what kills it. |
| Design written after results | Not by file times. DESIGN.md was last saved at 09:21:58, then core.py at 09:23:09, then results.json/frozen.json at 09:23:39, then RESULT.md at 09:25:39. I can't rule out an earlier unsaved run, but nothing points to one. |
| More variants than registered | No. Only L1-L6 are scored, plus V0, which is not scored. Holm is over 6. The frozen pick (L2, L4) follows the stated rule. |
| Placebo | It matches the design (absorbed-vs-not label shuffle). It reuses overlapping candidates, which makes p too optimistic, not too pessimistic. That can't turn a YES into a NO. |
| Overlapping trades | None. 0 overlaps in any book. |
| Halves | Correct: 26 / 25 days by date. |
| Robustness | With a plain next-bar-open entry instead of E5, L2 is -0.22R / -$1,073, L4 -0.32R, L5 -0.18R, L6 -0.18R. Still NO. With E5, limit fills at the new levels lose badly (L2 -0.83R): price that comes back to these levels keeps going. |

## Errors in the write-up (none changes the verdict)
1. **7 of the 51 "days" are Sundays** (09-27, 10-18, 10-25, 11-01, 11-08, 11-15, 11-22). They pass the 50,000-row bar on
   Sunday-evening Globex alone and have no 09:45-15:00 bars. DESIGN says Sundays are never traded, and they aren't, but
   they are in the trades-per-week divisor. Real trading days = 44, so per week is about 14% higher than shown:
   L2 4.55 (not 3.92), L4 5.9, L5 21.4, L6 23.5, V0 7.2 (not 6.2).
2. **Thanksgiving 11-26 (a half day, 72k rows) was traded**, although DESIGN says half days are history only. It adds 2 L2
   losers (-1.03R, -1.14R). Without them L2 is 38 trades at about -0.45R. Still NO.
3. NP "last 5 usable trading days" counts Sundays (no RTH POC), so the real look-back is about 4 days. L3 is TOO FEW
   either way.
4. Within GX, the code uses the fixed order VAH > VAL > POC. DESIGN's general text says "nearest the extreme". The DESIGN
   table gives the fixed order, so it's ambiguous and has no material effect.

## Side finding for the lead: confirmed, one correction, one more lane A issue
- Confirmed: `engine/of_paper.step()` marks a row busy while any taken row has no `exit_t`, and `replay_summary` resolves
  exits only after the whole signal loop. So the replay books only the first absorbed signal of each day. I re-derived
  the split: first-of-day 40 at +0.483R, the 23 later ones -0.034R.
- Correction: on 44 real trading days, lane A one-at-a-time is about **7.2 trades/week** (first-of-day only, about 4.5),
  not "6 vs 4".
- New issue (pre-existing in lane A, `of_battery.levels` + `of_paper._prev_summary`): the "previous day" for a Monday is
  the Sunday file whenever one exists. A Sunday file has no RTH, so **Mondays get no pdh/pdl**: 7 of the 9 Mondays here
  have only onh/onl. On the 2 Mondays whose Sunday file was thin (10-05, 10-12), V0 falls back to Friday, so pdh/pdl
  exist, but onh/onl then miss Sunday 18:00-24:00. The live path (`_prev_summary`, back = 1 day, any size) behaves like
  the 7-Monday case. This is worth a dated design note. It is not a rule change from here.
