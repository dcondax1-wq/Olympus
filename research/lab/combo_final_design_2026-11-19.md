# One account, Zlarior + ATLAS on the Builder 50K - FINAL rules: pre-registered design

Written and committed 2026-11-19 BEFORE any variant below was run (night-comboplus). Starting point: the study
(research/writeups/one-account-combo-2026-11-19.md, tools/money/combo_account.py) and its red team
(research/writeups/one-account-combo-redteam-2026-11-19.md, research/combo_redteam/). Paper research only: nothing live,
no live_model*.json. Futures trades only (the stored table research/lab/combo_account_trades.json, CME NQ1! bars).

## 1. Fixed for every row (model fixes, not variants)

- Account: MFFU Builder 50K at the owner's price $91.80. Eval $3,000 target, $2,000 EOD trailing (open losses count,
  locks at +$100), $1,000 soft day across both bots, 40 micros, flat by 16:10. Sim funded: $2,100 buffer, $500-$2,000,
  50% best day, 2 days a cycle, 48 h, 80%, the bot asks at $1,500 above buffer. Owner-approved sizes, called from the
  engine (never edited): Zlarior eval two_week room_f 0.4 kept to session 80 (live_model.json), funded preset;
  ATLAS engine/account_b builder50k need size / funded_qty. One shared room. Costs $1.90 a micro + 1 tick per market fill.
- Bots: Zlarior = the 631 stored live-loop trades; ATLAS = the raw EMA / MACD / S-R members with its own rules (one
  position, max 2 a day). ATLAS's own stored intraday path (second_mix units cache) is used ONLY to price an ATLAS trade
  that a conflict rule closes early: the last bar close at or before Zlarior's entry minute, minus 1 tick (market exit),
  its worst open loss up to then; inside ATLAS's first bar: the entry price minus 1 tick.
- **MFFU move to live after the 5th payout (main model "live")**: the sim funded account ends; the slot buys no new eval
  (MFFU: sim accounts go dormant while live) and trades ONE live account for the rest of the 6 months on the rulebook's
  live rules: $2,000 EOD trailing max loss that stops at the start balance, $1,000 soft day, daily payouts >= $250, 80%,
  no consistency rule. Assumptions (not in the rulebook, stated): starts at $0 profit, 40 micros, the bots size it with
  their funded rules, the bot withdraws everything above a $2,000 cushion (so the floor is locked first). A live breach:
  21 days (15 sessions) with no new eval (rulebook cooldown), then a new eval. Sensitivity "stop": the live account is
  worth $0 (the slot ends at the 5th payout, the red team's model). "rebuy" (the old study model) only for parity.
- Monte Carlo, the SAME paths for every row: day-block (whole days with replacement) AND week-block (whole calendar weeks
  in a row), 2,000 x 126 sessions (6-month slot: eval -> 2 sessions paperwork -> funded -> lost / stuck / live) and
  2,000 x 126 from the first funded session. Periods judged separately: H1 = 2026 Jan-Jun, H2 = 2026 Jul-Oct 16,
  REF = 2021-11 .. 2025, and 2022 alone.
- Reported per row and period: $ a month after every eval fee (mean, 10-90%), chance the 6 months lose money; eval fail
  within 2 weeks (10 sessions) and within 60, pass within 60 + median days; funded first payout within 30 / 60 sessions;
  gap vs Zlarior alone on the same paths (paired SE). Robustness, every row: +1 tick each way (H1 / H2 / REF, day AND
  week); ATLAS's trades on ATLAS's 5 best days of the period removed (the same 5 days for every row, H1 / H2 / REF,
  day-block); the "stop" live model (day-block); resampled H2 histories: the 16 weeks redrawn 200 times, 500 day paths
  each, the same histories for every row -> share of histories where the gap vs Zlarior alone is $0 or worse.

## 2. The variants (12, each with its plain reason)

| # | id | rule | reason |
|---|---|---|---|
| 1 | base | first in keeps the account, ATLAS at 100% of its own size, no guard | the study's proposal |
| 2 | zprio | Zlarior entering the OTHER way closes ATLAS at market, then Zlarior trades | today's live rule between the two accounts (HEDGE); Zlarior's trades are the proven edge |
| 3 | zfull | any Zlarior entry closes an open ATLAS trade at market (either side) | Zlarior loses its same-side trades behind ATLAS; Zlarior's per-trade edge is the bigger one |
| 4 | a60 | ATLAS at 60% of its own size (eval and funded) | ATLAS's loss bunches cause the early eval fails and the 2022 loss: a smaller share |
| 5 | a40 | ATLAS at 40% of its own size (eval and funded) | the same, smaller |
| 6 | a_eval_off | ATLAS sits out the eval (Zlarior alone), trades its full size once funded | the early fails come from ATLAS; Zlarior alone fails 0.5% in 2 weeks; ATLAS's edge pays most funded |
| 7 | a50_eval | ATLAS at 50% in the eval, 100% once funded | half way between 1 and 6 |
| 8 | room1500 | in the eval ATLAS trades only while the room left is >= $1,500 | once the eval has lost a quarter of its room, only Zlarior (the proven one) adds risk |
| 9 | daycap500 | in the eval no new entry (either bot) once the account's closed day P&L is <= -$500 | two full $1,000 soft-day losses = the whole $2,000 max loss; at -$500 it takes 4 bad days |
| 10 | a60_room1500 | 4 + 8 together | both aim at the 2-week fails; together if one alone is not enough |
| 11 | room1500_daycap500 | 8 + 9 together | two eval guards together |
| 12 | a_eval_off_a60 | 6, and ATLAS at 60% once funded | 6 plus a smaller ATLAS on the funded account (2022-like years strand funded accounts) |

Size factor: ATLAS's micros = max(1, floor(factor x its own size)) when its own size is >= 1 (never above its own size).
Zlarior alone (today) is the reference row, not a candidate.

Not run, with the reason:
- ATLAS members "kept only if positive in every period, decided before Jul-Oct": all three are positive after
  commission in both pre-Jul-Oct periods (net R at 1 micro: H1 EMA +30.8, MACD +46.6, S-R +22.9; 2021-25 +18.1, +56.8,
  +7.8), so that rule keeps all three = the base. Honest note: the per-member Jul-Oct numbers were looked at before this
  file was written (S-R weak there, +1.1 R); that is exactly why the rule uses pre-Jul-Oct data only and S-R stays.
- BLITZ, lane sizes, same-side adds: rejected by the study (room burn / not better in every period); not re-run.

## 3. The pick (fixed now)

Constraints, against Zlarior alone on the same paths, main "live" model:
- C1 money: gap > 2 paired SE in H1 AND H2, under the day AND the week bootstrap.
- C2 old years: 2021-25 gap >= -$50 a month, day AND week.
- C3 eval safety: eval fail within 2 weeks <= 5% in H1 AND H2, day AND week.
- C4 costs: at +1 tick each way the gap stays > $0 in H1 AND H2, day AND week.
- C5 robustness: resampled H2 histories with a gap of $0 or worse <= 7% (half of the base's 1 in 7).

Pick: tier A = every row passing C1-C5 -> the highest H2 week-block $ a month. If none: tier B = passing C1-C4 -> the
highest H2 week-block $ a month (the C5 miss said plainly). If none passes C1-C4: nothing beats the base; keep the base
and say which constraints it misses. 2022 alone, the best-5-days drop and the "stop" model are reported for the winner and
every row, not used to pick (they are the honesty checks the owner reads).

Question 3 (which ATLAS share and guard makes "$0 or worse" drop well below 1 in 7): answered from the resampled H2
histories of every row, among rows that pass C1.

Commands: `/home/user/heavy.sh python -X utf8 tools/money/combo_account.py final [--n 2000] [--workers 3]`
(results research/lab/combo_final.json; config research/lab/combo_50k.json; write-up
research/writeups/one-account-combo-final-2026-11-19.md).
