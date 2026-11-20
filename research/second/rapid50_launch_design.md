# Rapid EOD 50K readiness - design (pre-registered 2026-11-20, committed before any run)

Question: the 5th MFFU funded slot (bought from payouts ~late Dec): Rapid EOD 50K ($165) or a 2nd Rapid EOD 25K ($97.20),
and how the 50K should trade at ATLAS's real fills. Same engine, paths and seeds as research/second/rapid25_launch_design.md
(tools/money/rapid25_launch.py, money_plan.RSeat, ATLAS re-priced N ticks a side, 1,000 paths, H1 / H2 / REF, 126 sessions).
Costs 1 and 10 ticks; decisions at 10.

Rows (fixed now):
  F1 50K LIT only
  F2 50K ATLAS only $500
  F3 50K LIT + ATLAS $500, keep $1,000 (the built preset mffu_rapid_eod_50k)
  F4 F3 with ATLAS sized on a 10-tick stop (as card rapid-atlas-size-10t for the 25K)
  C1 2nd Rapid 25K as built (LIT + ATLAS $250, keep $500)
  C2 C1 with ATLAS sized on a 10-tick stop

Measured: as the 25K design, plus days under -$1,000 (the 50K bot's soft day) per 100 traded days.

Decisions (fixed now):
  Slot: the 50K stays the pick if F3 $/month > C1 in H1 AND H2 at 10 ticks; else the 2nd 25K (money_book.next_buy's
        USD_MONTH re-set from these rows either way, 10-tick H2 values).
  50K lanes: LIT + ATLAS stays if F3 > F1 and F3 > F2 in $ in H1 and H2.
  50K sizing: F4 recommended if funded lost is lower by >= 0.5 pts in H1 and H2 and $ >= 90% of F3's in H1 and H2 and REF
        not down > $10; else F3 as built.
