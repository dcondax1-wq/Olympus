---
title: New strategy for the extra accounts (Rapid EOD 25K) - ICT ATM range + ES/NQ SMT as the trigger, MES as the traded market, and a Judas-swing control; none passes, nothing changed
family: other
date: 2026-11-20
status: rejected (no change, no Decide card). live_model*.json, second_model.json, accounts untouched.
summary: Owner 2026-11-20 - pull in "the ATM model ICT", ES/NQ SMT and "trades for ES if it looks cleaner" for the new MFFU Rapid EOD 25K. Five rule sets were written down before any run (research/newstrat/RULES.md, commit before the code) - SMT-ATM on NQ and on MES, session SMT (prior-day / overnight high-low) on NQ and on MES, and a no-ES Judas swing - each 1 trade a day max, stop 1 tick beyond the sweep extreme, one target, $250 risk, costs in. 0 of 5 pass. Every SMT set loses money in all three periods (PF 0.57-0.99, gross PF before costs 0.59-1.05): SMT used as the trigger has no edge, on NQ or on ES. MES is not cleaner (S2/S4 lose like S1/S3, and the 10-tick stress is far worse on ES because stops are 5-7 pts). The Judas control makes +$1,672 in 2026 Jan-Jun and then loses Jul-Oct (-$2,244) and 2021-25 (-$11,472 on 633 trades). Rapid EOD 25K 60-day eval pass 0-5% for every SMT set (blow 43-86%). Correlation with LIT / ATLAS is near zero (-0.16..+0.15), so a real edge could stack - but there is none to stack.
runs: none (research/newstrat/results.json; research/newstrat/smt.py)
---

## For the owner

| What | Result |
|---|---|
| Did any new ICT / SMT strategy pass? | **No. 0 of 5.** Nothing goes on the Rapid 25K. |
| Best SMT set (session SMT on NQ) | Jan-Jun **-$39**, Jul-Oct **-$2,252**, 2025 **-$3,979** at $250 a trade |
| Trading ES (MES) instead of NQ | **Not cleaner:** loses in all three periods (-$1,251 to -$2,698), and much worse with real fills |
| Rapid EOD 25K eval pass (60 days) | **0-5%** for the SMT sets, 43-86% blown. Do not run these on an eval |
| Judas swing (NQ open sweep of the overnight high/low) | Jan-Jun **+$1,672**, then Jul-Oct **-$2,244**, 2021-25 **-$11,472**: a lucky half-year, not an edge |
| Overlap with Zlarior / ATLAS | Almost none (daily correlation -0.16 to +0.15), so a real edge could share an account - but there is none |

What this means for money: the Rapid EOD 25K keeps the plan already coded for it (LIT lane + ATLAS lane, `engine/rapid.py`).
Adding any of these five would have cost about $200-600 a month and blown the eval most of the time.

## What was already tested, and what is new here

Already rejected (not repeated): ICT Silver Bullet as taught (`research/lab/SB_RULES.md`), ICT 2022 model, Mech/IFVG,
the owner's ATM model with the strong-V + IFVG entry (`research/lab/ATM_RULES.md`, ATM_REPORT: 0.17 trades a week, entries
mid-range, R:R 0.74), SMT as a LIT confluence / gate / size weight (`research/ICT_REPORT.md`), MES instead of MNQ on LIT's own
SMT setups (`lit-untested-entries.md`).

New in this test:
1. **SMT is the trigger** of a stand-alone trade: one index takes a level, the other fails to, then the sweeper closes back inside.
2. **ATM range kept, entry moved** to the first 5m close back inside the 07:00-09:25 range (near the swept edge), which fixes the
   old ATM R:R problem (S1 skips 83 of 187 signals under 1.5R instead of 105 of 116).
3. **The same signals traded on MES**, to answer "is ES cleaner".
4. **A no-ES Judas swing control (S5)** to see if the SMT part adds anything, and the only set testable on all of 2021-25.
5. **ATM management (scale out, run the rest):** not expressible as one target, so not used; S1 targets the far ATM side
   (capped at 3R) as its single target - the honest one-target version of "run it to the other side".

## Rules (pre-registered, `research/newstrat/RULES.md`, committed before the code existed)

Common: 5m TradingView CME NQ1! / ES1!, ET clock. Market entry the bar after the signal (+1 tick), stop 1 tick beyond the
traded index's extreme since 09:30 (fills 1 tick worse), one limit target (needs 1 tick through), stop first if both in one
bar, flat 15:55, max 1 trade a day, $250 risk, $1.90 a micro round trip, 10-tick stress = 10 more ticks per trade.

| Set | Trigger | Window ET | Target | Traded |
|---|---|---|---|---|
| S1 SMT-ATM | one index takes its 07:00-09:25 high (low), the other has not; sweeper closes back inside | 09:30-11:30 | far ATM side, skip < 1.5R, cap 3R | MNQ |
| S2 | S1's signals | 09:30-11:30 | ES's far ATM side, same rule | MES |
| S3 Session SMT | same, on max(prior-day high, overnight high) / min(prior-day low, overnight low) | 09:30-11:30, 13:30-15:00 | 2R | MNQ |
| S4 | S3's signals | same | 2R | MES |
| S5 Judas control | NQ takes its overnight high or low, closes back inside (no ES) | 09:30-10:30 | 2R | MNQ |

Pass bar (each of 2026 Jan-Jun, 2026 Jul-Oct, 2021-25): net > 0, PF >= 1.2, 2.0-4.0 trades a week, 10-tick stress > 0.
ES data starts 2025-04-14, so for S1-S4 "2021-25" = 2025-04-14 .. 2025-12-31 (39 weeks).

## Full table ($250 risk a trade, costs in)

Eval columns = pass % / blown % / median days to pass, every real day a fresh 60-session start (MFFU Rapid EOD 25K: $1,500
target, $1,000 EOD floor locking at +$100, best day <= 30%, 4 days; Builder 25K: same without consistency).
Corr = daily $ correlation with LIT ($350 flat) / ATLAS ($250). Same time = trades with a LIT + ATLAS position open at the
same moment (opposite direction in brackets). Both lose = days both this set and LIT lost / days both traded.

| Set | Period | Trades | /wk | Win | PF | Gross PF | Net | $/mo | Max DD | 10-tick stress | Rapid 25K | Builder 25K | Corr LIT / ATLAS | Same time | Both lose |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|S1|2026 Jan-Jun|33|1.34|24.2%|0.69|0.74|-$1,599|-$273|-$2,402|-$2,359|0% / 57% / -|0% / 57% / -|0.10 / -0.05|3+5 (opp 1+3)|3/14|
|S1|2026 Jul-Oct|21|1.38|23.8%|0.74|0.78|-$806|-$223|-$1,460|-$1,166|0% / 65% / -|18% / 65% / 11.5|0.06 / -0.16|2+4 (opp 2+4)|1/9|
|S1|2025 Apr-Dec|50|1.41|20.0%|0.58|0.63|-$3,692|-$438|-$3,982|-$5,342|0% / 75% / -|0% / 75% / -|-0.05 / 0.00|2+6 (opp 2+4)|5/21|
|S2|2026 Jan-Jun|32|1.30|25.0%|0.77|0.86|-$1,251|-$214|-$1,686|-$4,714|0% / 57% / -|0% / 57% / -|-0.05 / -0.08|6+2 (opp 3+2)|5/17|
|S2|2026 Jul-Oct|22|1.45|27.3%|0.71|0.80|-$1,087|-$300|-$1,596|-$3,700|0% / 74% / -|1% / 74% / 28|-0.01 / -0.10|1+1 (opp 1+1)|2/9|
|S2|2025 Apr-Dec|41|1.16|24.4%|0.66|0.75|-$2,419|-$287|-$3,555|-$7,806|0% / 64% / -|0% / 64% / -|0.02 / 0.13|3+2 (opp 2+1)|3/14|
|S3|2026 Jan-Jun|50|2.03|38.0%|0.99|1.05|-$39|-$7|-$1,331|-$899|5% / 43% / 27.5|5% / 43% / 27.5|0.11 / 0.15|3+5 (opp 1+3)|9/33|
|S3|2026 Jul-Oct|36|2.37|25.0%|0.57|0.59|-$2,252|-$622|-$2,936|-$2,772|0% / 76% / -|0% / 76% / -|0.14 / -0.09|1+7 (opp 1+3)|8/19|
|S3|2025 Apr-Dec|72|2.03|27.8%|0.64|0.68|-$3,979|-$472|-$5,865|-$5,734|0% / 86% / -|0% / 86% / -|-0.03 / 0.07|3+7 (opp 3+5)|7/33|
|S4|2026 Jan-Jun|55|2.24|27.3%|0.67|0.73|-$2,698|-$461|-$3,206|-$7,072|5% / 82% / 27.5|7% / 80% / 29|0.11 / 0.08|3+4 (opp 1+3)|10/35|
|S4|2026 Jul-Oct|42|2.76|31.0%|0.78|0.86|-$1,289|-$356|-$1,907|-$4,676|0% / 80% / -|0% / 80% / -|0.08 / 0.03|1+7 (opp 1+3)|9/21|
|S4|2025 Apr-Dec|74|2.09|33.8%|0.78|0.88|-$2,412|-$286|-$4,109|-$10,100|1% / 85% / 6.5|1% / 85% / 6.5|0.04 / 0.08|3+8 (opp 3+5)|10/34|
|S5|2026 Jan-Jun|70|2.85|42.9%|1.20|1.25|+$1,672|+$285|-$1,475|+$807|29% / 36% / 24|31% / 36% / 25.5|-0.02 / 0.15|9+8 (opp 8+4)|13/45|
|S5|2026 Jul-Oct|43|2.50|25.6%|0.64|0.67|-$2,244|-$548|-$3,267|-$2,779|0% / 72% / -|0% / 72% / -|-0.04 / -0.06|3+7 (opp 2+4)|7/19|
|S5|2021-11..2025-12|633|3.06|32.7%|0.87|0.92|-$11,472|-$233|-$16,743|-$24,762|19% / 76% / 27|19% / 75% / 25|-0.05 / 0.07|61+166 (opp 54+79)|90/317|

Skipped signals: S1 83 under 1.5R, S2 92 under 1.5R, S3 14 too wide for $250, S4 1, S5 30.

## Findings

1. **SMT as a trigger has no edge.** Gross PF before any cost is 0.59-1.05 in all 12 SMT rows; with 2R targets a 33% win rate
   is break-even and these win 25-38%. This matches the earlier finding that SMT does not mark better LIT trades.
2. **ES is not cleaner.** MES signals lose like MNQ ones. ES stops are small in points (median 5-7 pts), so each tick of real
   slippage costs a bigger share of R: the 10-tick stress turns -$1.3k..-$2.7k into -$3.7k..-$10.1k. Given ATLAS's real fills
   (~11 ticks worse over 3 fills), MES at these stop sizes is the wrong instrument for a bot.
3. **The Judas swing control is the LIT idea without LIT's filters** - a good half-year (Jan-Jun), then flat-to-losing for
   five years. LIT's extra rules are what make the sweep-reversal pay; a bare one does not.
4. **Stacking:** these sets would rarely overlap LIT/ATLAS in time (2-17 trades of 21-70 in a period), so on a shared Rapid
   account they would not double risk - but with no edge the question is moot.
5. **Frequency:** only the session-SMT and Judas sets reach 2-4 a week; the ATM-range SMT fires ~1.4 a week.

## Not done / limits
- ES history is only 2025-04 onward, so SMT has 9 months of "older" data instead of five years. With every row negative, more
  data would not change the verdict.
- 5m bars only (1m ES does not exist in the repo). A 1m entry was not tried (earlier tests found 1m worse for these models).
- No tuning was done after the results; the five sets are exactly as pre-registered.

## Files
- `research/newstrat/RULES.md` (pre-registration), `research/newstrat/smt.py` (code), `research/newstrat/results.json` (every trade).
- Run: `python -X utf8 research/newstrat/smt.py` (about 10 s).
