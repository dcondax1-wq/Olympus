# Rapid EOD 25K launch check - design (pre-registered 2026-11-20, committed before any run)

Question: what should the Rapid EOD 25K (DLL version, $97.20) trade, at ATLAS's real fills?
Engine: tools/money/money_plan.RSeat on tools/money/rapid25.acct("25k", keep $500) (= the built preset), ATLAS's trades
re-priced with tools/atlas_fills.priced at N ticks a side (tools/atlas_risk.T_at), LIT unchanged. 1,000 paths a market
(H1 = Jan-Jun 2026-like, H2 = Jul-Oct 2026-like, REF = 2021-25-like), 126 sessions, seeds as rapid25 / atlas_risk.
Costs: 1 tick (backtest) and 10 ticks a side (real fills; the decision cost). Fee $97.20 per eval incl. re-buys.

Rows (fixed now):
  R1 LIT only            mix (LIT), eval + funded
  R2 ATLAS only $250     mix (ATLAS), eval + funded
  R3 LIT + ATLAS $250    as built (base)
  R4 R3 + LIT bank lane  (rapid25-lit-bank: 1 micro, exit at the day's room, eval only)

Measured per row and market: $ a month to the owner (after fees and MFFU's 90%, before tax), eval pass % in 60 sessions,
eval median sessions to pass, eval fail % in 60 sessions, first payout date p25 / p50 / p75, no payout in 6 months %,
funded lost in 6 months %, chance the first eval fails before any payout, days under -$500 (MFFU's DLL pause) per 100 days traded.

Decisions (fixed now):
  atlas-on-rapid YES  if at 10 ticks R3 $/month > R1 in H1 AND H2, and R3 no-payout-6m < R1's in H1 and H2.
  rapid25-lit-bank YES if at 10 ticks R4 $/month >= R3 in H1 AND H2, REF not down more than $10, funded lost up <= 5 pts
                     and eval fail (60 sessions) up <= 1 pt in H1 and H2. Else NO.
  ATLAS only: a new card only if R2 beats R3 in $ in H1 AND H2 AND REF at 10 ticks (otherwise reported, no card).
  Sizing: if days under -$500 exceed 1 per 100 traded days at 10 ticks, propose (LEAD_WIRES) a 10-tick stop slippage in
  the Rapid ATLAS lane's size (engine/rapid.stack_qty); else no change (MFFU's DLL is a soft pause, never a fail).
