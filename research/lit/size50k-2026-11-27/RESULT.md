# Builder 50K upsizing (2026-11-27, research only, nothing live changed)

Question (owner): "I think on the 50Ks we can upsize more." Engine: tools/money/combo_account.py = the live 50K combo's
reference simulator (first in, ATLAS x0.5 eval / x1.0 funded, MFFU live move, costs in). 12 cells pre-registered in
DESIGN.md (fc6825a3), 1,000 whole-day paths per market, same paths for every cell. size50k.py -> results.json.

## Verdict
- **LIT room_f: do NOT upsize.** Going from 0.4 to 0.5/0.6/0.7 earns +$37/+$55/+$63 a month in H1 and +$41/+$79/+$99 in Jul-Oct,
  while the fresh-eval fail rate rises 3 -> 4/6/8% (H1) and 9 -> 15/19/22% (Jul-Oct). That's the same answer evalsizer
  gave on 2026-11-26.
- **ATLAS share in the eval: x1.0 is the only real $ lever.** At room_f 0.4, ATLAS x0.5 -> x1.0 adds **+$183/mo (H1), +$111/mo
  (Jul-Oct), +$44/mo (2021-25)**; the paired standard error is about $12 / $9 / $6 a month, so the gain is real. It pays for
  this with more blown evals: fresh fail 3.0 -> 8.9% (H1) and 8.8 -> 12.9% (Jul-Oct). It passes faster (10 -> 5 and 11 -> 7
  sessions) and pays out sooner (first payout at 30 -> 24 and 39 -> 35 sessions).
- **By the pre-registered rule nothing qualifies.** I also required "pass % not lower in both halves", and every upsize
  lowers the pass rate. The earlier combo final study also turned x1.0 down on its fail bars. By the owner's $-only rule
  (both halves better, 2021-25 not worse), ATLAS x1.0 at room_f 0.4 passes. That makes it a **yes/no card for the owner**,
  not a change Claude makes.

## Table (fresh eval; $ = net per 6-month slot after the $91.80 re-buys)
| cell (room_f / ATLAS eval share) | H1 pass/fail, days | H1 $/mo | Jul-Oct pass/fail, days | Jul-Oct $/mo | 2021-25 pass/fail | 2021-25 $/mo | 2025 $/mo |
|---|---|---|---|---|---|---|---|
| **live 0.4 / 0.5** | 96.6 / 3.0%, 10 | $2,529 | 89.2 / 8.8%, 11 | $1,457 | 28.7 / 67.8% | -$2 | $65 |
| 0.4 / 0.75 | 95.4 / 4.6%, 9 | $2,600 | 89.8 / 9.1%, 10 | $1,491 | 31.6 / 67.6% | $8 | $79 |
| **0.4 / 1.0** | 91.0 / 8.9%, 5 | $2,713 | 86.8 / 12.9%, 7 | $1,568 | 35.1 / 64.9% | $42 | $111 |
| 0.5 / 0.5 | 95.4 / 4.3%, 9 | $2,566 | 84.7 / 14.5%, 9 | $1,498 | 30.0 / 68.4% | $14 | $75 |
| 0.5 / 1.0 | 89.5 / 10.5%, 5 | $2,730 | 83.8 / 16.1%, 6 | $1,584 | 35.0 / 65.0% | $44 | $107 |
| 0.6 / 1.0 | 88.3 / 11.7%, 5 | $2,738 | 80.8 / 19.2%, 6 | $1,610 | 35.1 / 64.9% | $43 | $113 |
| 0.7 / 1.0 | 85.9 / 14.1%, 4 | $2,750 | 78.3 / 21.7%, 5 | $1,625 | 35.7 / 64.3% | $55 | $124 |
(All 12 cells are in results.json.)

## From TODAY's 50K (balance $49,482, room $1,313, $3,518 to go; session 25 assumed)
| cell | H1 pass / fail | Jul-Oct pass / fail | 2021-25 pass / fail | 6-month $ H1 / Jul-Oct / 2021-25 |
|---|---|---|---|---|
| live 0.4 / 0.5 | 93.6 / 6.0% | 82.9 / 14.1% | 19.7 / 78.5% | $14,657 / $8,406 / $72 |
| 0.4 / 0.75 | 91.5 / 8.4% | 82.3 / 16.1% | 20.9 / 78.1% | $14,990 / $8,652 / $73 |
| 0.4 / 1.0 | 85.2 / 14.6% | 79.4 / 20.2% | 23.8 / 76.2% | $15,872 / $9,065 / $290 |
| 0.7 / 1.0 | 76.0 / 24.0% | 63.8 / 36.2% | 23.6 / 76.4% | $16,206 / $9,553 / $368 |

## Risk in $
- Biggest single-trade risk in an eval (median path): live $564-664 vs ATLAS x1.0 $674-732. Against today's $1,313 room, one
  full loss uses about half of what's left.
- Cost of a fail = $91.80 re-buy + the sessions burned (median fail at 11-22 sessions; sooner for the bigger sizes) + the
  time to pass again (5-11 sessions in a 2026-like market).
- x1.0 from today in a Jul-Oct-like market: about 6 more fails in 100 (14 -> 20). Each fail costs about $92 + roughly 3 weeks.
  The trade-off is about +$110-180 a month while 2026-like markets last.

Caveats: the combo store ends 2026-10-16 (it doesn't include the Oct-Nov drought, where LIT barely traded); the session count
for today's eval is assumed; 12 cells counted, no Holm (this is a trade-off, not a significance test).
