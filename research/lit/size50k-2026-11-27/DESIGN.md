# Builder 50K upsizing (owner: "I think on the 50Ks we can upsize more"), pre-registered 2026-11-27 before any run

Engine: tools/money/combo_account.py (the reference simulator of the live 50K combo; tests.test_combo_50k = parity with
the real LiveBot). Row = frow("a50_eval") = today's live combo (first in, ATLAS x0.5 eval / x1.0 funded, MFFU live move).
Only two knobs change: LIT eval two_week room_f, ATLAS eval share. Every MFFU rule, cost, funded sizing unchanged.

## Grid (12 cells, all counted)
room_f in {0.4 (live), 0.5, 0.6, 0.7} x ATLAS eval share in {0.5 (live), 0.75, 1.0}.

## Markets (whole-day bootstrap, same paths for every cell)
H1 = 2026 Jan-Jun, H2 = 2026 Jul-Oct 16, REF = 2021-11..2025, Y2025.

## Starts
- fresh: a new Builder 50K eval (then funded, re-buy at $91.80 on a fail / lost, 126-session = 6-month slot).
- today: balance -$518 (MFFU $49,482), floor -$1,831 (room $1,313), peak +$169, $3,518 to pass; session 25 and 5
  traded days assumed (true count unknown; only matters past session 80 / min 1 day).

## Numbers per cell and market
eval (60 sessions): pass %, fail %, median sessions to pass; slot (6 mo): net $ after fees, $/month, sessions to the first
payout (median), $ paid to the owner; cost of a fail = $91.80 re-buy + the median sessions a failed eval used.
1,000 paths eval, 1,000 paths slot.

## Judge (fixed now)
UPSIZE only if, vs live (0.4 / 0.5), on the FRESH start: slot net $ higher in H1 AND H2, pass % not lower in H1 AND H2,
and REF net not worse by more than $100 a slot and REF fail % not higher by more than 3 points. Pick = the qualifying
cell with the highest H1 net. From-today numbers are shown for the decision on the current eval, not for the pick.
Prior result to respect: evalsizer 2026-11-26 rejected room_f 0.5 on the 50K (+$116 / +$199 but fails +3 / +6 pts).
Expected: NO, or at most a small $ gain bought with more fails.
