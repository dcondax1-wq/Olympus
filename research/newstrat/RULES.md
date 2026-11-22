# New strategy for the extra accounts: ICT ATM + ES/NQ SMT. Pre-registered rules (written 2026-11-20 ~06:00 ET, BEFORE any run)

Nothing below may change after a scored result is seen. Code: `research/newstrat/smt.py`.

## What was already tested (not repeated)
- ICT Silver Bullet as taught (base / am / ce / rr2): `research/lab/SB_RULES.md` -> rejected (docs/TESTED_AND_REJECTED.md).
- ICT 2022 model, Mech/IFVG, continuation: `tools/lab_models/` -> rejected (0.2-1.5 trades/wk, PF ~1).
- The owner's ATM model (07:00-09:25 range, sweep, strong V + IFVG, target the far side): `research/lab/ATM_RULES.md` ->
  rejected on 5m and 1m (entries land mid-range, median R:R 0.74, 0.17 trades/wk).
- SMT as a LIT confluence / gate / sizing weight (`research/ICT_REPORT.md`, `lit-untested-entries.md`): noise.
- Trading MES instead of MNQ on LIT's own setups when ES held (SMT pick): lost Jan-Jun.

## What is new here
1. SMT is the **trigger** of a stand-alone trade (not a filter on LIT): one index takes a level, the other fails to.
2. The ATM range is kept, but the entry is the **first 5m close back inside the range** (near the swept edge), not the
   50%-of-leg V entry that killed the old ATM R:R.
3. The same signals are also traded on **MES** (ES) to answer "trade ES if it looks cleaner".
4. A no-ES **Judas swing** control (S5) shows whether the SMT part adds anything, and is the only set testable on 2021-25 in full.

## Common to every set
- Data: TradingView CME NQ1! / ES1! 5m (`data/NQ_5m.csv`, `data/ES_5m.csv`), ET clock (America/New_York, DST aware).
  ES exists only from 2025-04-14, so for S1-S4 the "2021-25" period is **2025-04-14 .. 2025-12-31** (said in every table).
- Day = the ET calendar date of the RTH session. ATM range = 5m bars 07:00..09:25 (incl. the 09:25 bar). Overnight range =
  18:00 (prior day) .. 09:25 bars. Prior day = prior RTH 09:30..15:55 bars.
- Entry: market at the open of the bar after the signal bar, +1 tick slippage. Stop: 1 tick beyond the traded instrument's
  extreme since 09:30 (the sweep extreme), stop fills 1 tick worse. Target: one limit, fills only if a bar trades 1 tick
  through it. If stop and target are both inside one bar: stop (worst case). Flat at the 15:55 bar close. Max 1 trade a day.
- Costs: $1.90 a micro round trip (MNQ $2/pt, MES $5/pt). 10-tick stress = 10 more ticks against every trade.
- Size: fixed $250 risk (the Rapid 25K ATLAS dollar): micros = floor(250 / ((stop pts + 1 tick) x $/pt + $1.90)), max 20;
  0 micros = no trade (counted as "skipped: too wide").
- No scaling. The ICT "ATM" management (scale out, run the rest) is NOT one target; it is reported only as a note.

## The five sets
- **S1 SMT-ATM (trade NQ).** 09:30-11:30 ET entries. Bearish: one index trades >= 1 tick above its own ATM high while the
  other has NOT traded above its own ATM high since 09:30. Signal = the first 5m bar that closes back below the ATM high on the
  index that swept, while the other index is still not above its ATM high at that bar's close. Bullish mirrors on the lows.
  Target = NQ's opposite ATM side (1 tick inside); skip if < 1.5R; if > 3R, target = 3R. First signal of the day only.
- **S2 SMT-ATM (trade MES).** S1's exact signals, traded on ES with ES's own extreme / opposite ATM side.
- **S3 Session SMT (trade NQ).** Levels: high side = max(prior-day RTH high, overnight high); low side = min(prior-day RTH
  low, overnight low), for each index. Windows 09:30-11:30 and 13:30-15:00 ET. Divergence and signal exactly as S1 but on
  these levels. Target = fixed 2R.
- **S4 Session SMT (trade MES).** S3's exact signals, on ES.
- **S5 Judas swing control (NQ only, no ES).** 09:30-10:30 ET. NQ trades >= 1 tick beyond its overnight high or low (first
  side taken), then a 5m close back inside the overnight range. Target 2R.

## Pass bar (all must hold, in EACH of 2026 Jan-Jun, 2026 Jul-Oct, 2021-25)
net $ > 0 with costs, PF >= 1.2, 2.0-4.0 trades a week, 10-tick stress net > 0. Eval simulation on the full real day
sequence (every day a fresh start, 60-session horizon): MFFU Rapid EOD 25K (target $1,500, EOD MLL $1,000 locking at +$100,
best day <= 30% of profit, 4 days, 20 micros) and Builder 25K (target $1,500, EOD MLL $1,000, $600 soft daily stop, no
consistency). Reported: pass %, blow %, median days to pass. A Decide card only if a set passes all three periods.
Correlation: daily $ P&L correlation with LIT (Zlarior, $350 flat) and ATLAS ($250), and the share of days both lose.
