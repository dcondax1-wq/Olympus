---
title: Fleet plan to June 2027 - all 5 MFFU slots + Kalshi K8, month by month, after fees and a 35% tax set-aside
family: money
date: 2026-11-20
status: done - paper research only; nothing live changed, no Decide card edited. Tax 35% = placeholder until day-taxes publishes.
summary: Owner "maximize how much we keep" / "fundeds paying next month". One Monte Carlo (1,000 week-block paths a market) of today's fleet (Zlarior 50K eval, 25K #2 eval, ATLAS funded 25K, Rapid EOD 25K from today) plus the 5th slot bought from banked payouts (Rapid EOD 50K $165) and K8 at $2.50, with re-buys at once. Jul-Oct-like at real fills, after fees + 35%, median Dec $74 / Jan $572 / Feb $1,523 / Mar $2,731 / Apr $3,434 / May $3,548 / Jun $3,874; Nov 20-Jun 30 total $19,510 (bad 1-in-10 $6,886; LIT also at 10 ticks $16,346). Half the edge ~$0 a month (total $1,987, mean $3,621); 2021-25-like -$1,347 (re-buys). Rapid EOD 50K bought ~Jan 5 (Dec 14-Feb 12). Decide cards for the whole fleet: atlas-on-rapid +$390, zlarior-funded25 +$159 (positive in all 3 markets), zlarior-atlas-50k +$209; the rest under $55.
runs: research/lab/fleet_months.json (tools/money/fleet_months.py, n 1000, seed 2611), phone tools/web_public/business/fleet_plan.json; tests/test_fleet_months.py
---

# Fleet plan to June 2027 (2026-11-20, day-fleet)

## For the owner

See research/handoff/2026-11-20/fleet/REPORT.md (it has the same tables). In one line: if the market stays like
Jul-Oct 2026, you keep about **$19,500 by the end of June** after MFFU's cut, every fee and a 35% tax set-aside. Most of
it comes Feb-Jun: about $1,500 in Feb, then $2,700-3,900 a month. If the edge halves, a typical month is about $0. If the
market turns like 2021-25, you lose about $1,350 on eval re-buys. Next buy: a Rapid EOD 50K ($165) around Jan 5, paid
from ATLAS's first payout.

## Method

- **Seats:** tools/money/payday_plan.py, the accounts from today's board, with money_plan's live sizing and MFFU rules.
  The step is extended to every CME session from Nov 20 2026 to Jun 30 2027 (155 sessions; Thanksgiving and the CME full
  closures skipped).
- **Same paths:** every account uses the same 5-session week-block paths (seed 2611), so a bad week hits all of them at
  once.
- **Re-buys:** a failed eval or a lost / stuck funded account is re-bought the same session (money_book.dead_eval, inside
  the seats). A Builder account reaching MFFU's 5th payout starts a fresh eval (seat rule).
- **5th slot:** money_book.next_buy is asked every session with the live stages and the kept cash. Kept cash = payouts that
  are in the bank (request + 3 sessions) x (1 - 0.35), minus every fee paid. It returns the Rapid EOD 50K (the top-ranked
  open slot), never a cheaper plan in the last slot. After that, all 5 funded slots are used (caps: 5 funded, 10 evals,
  Builder 50K 1, Builder 25K 2).
- **K8:** the held-out stored bets on the 3 live legs, resampled by whole days, $2.50 flat, OFF for good at -$19.25 from
  the peak. As-tested / half / no edge go with the three markets.
- **Fills:** real = ATLAS repriced at 10 ticks a side (atlas_fills.priced, its measured fills); LIT as stored.
  Stress = LIT at 10 ticks a side too.
- **Markets:** H2 = Jul-Oct 2026 blocks; HALF = each block drawn from H2 or 2021-25 with even odds; REF = 2021-25 blocks.
- **Decide cards:** one change each, on the same paths. The other seats are copied from the base run and the 5th-slot buy
  is re-run, because its date depends on the payouts. Value = (YES - NO) total cash after tax / 8 months.

## Results (real fills)

| Market | Total median | Bad 1 in 10 | Mean | Chance the total is below $0 | 5th slot bought (median date) |
|---|---|---|---|---|---|
| Jul-Oct-like | $19,510 | $6,886 | $19,976 | 0.1% | 99.9% (Jan 5) |
| Half edge | $1,987 | -$657 | $3,621 | 21% | 86% (Feb 4) |
| 2021-25-like | -$1,347 | -$1,874 | -$1,141 | 92% | 26% (Jan 29) |
| Jul-Oct-like, LIT also 10 ticks | $16,346 | $5,164 | $17,372 | 0.1% | 99.8% |

The monthly medians, per-account totals and the card table are in REPORT.md and research/lab/fleet_months.json.

## What it means

- The money lands late. December is almost nothing ($74 median). ATLAS's first $800 request is around Jan 7, and the
  evals pay from February. "Fundeds paying next month" is ATLAS only.
- The 5th slot is worth more than any card: the Rapid EOD 50K is the biggest single account by June ($7,840 median).
  Buy it the day banked payouts cover $165.
- In weak markets the cost is re-buys. ATLAS's 25K is re-bought ~12 times in a 2021-25-like market (~$730). An untested
  "no re-buy while the edge check is RED" rule would cap that; it is listed for a pre-registered test, not adopted.
- zlarior-funded25 flips from the older single-account "no" to positive in all three markets once the fleet's re-buys
  are counted. It is an owner yes/no.

## Limits

Backtests overstate. The paths re-use 2026 and 2021-25 history. MFFU rule changes are not modelled. Payout dates are sim
request dates plus 3 sessions. Kalshi K8 is unproven (forward paper still running). Taxes are a flat 35% set-aside, not a
tax calculation: eval fees lower the real tax (money_book.tax_true_up).
