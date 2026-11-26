# Multi-account allocation optimizer: design + pre-registration (2026-11-26, written BEFORE the scored run)

Lead (owner: "big NQ-bot work"): which signals go to which of the 4 MFFU accounts, at what size, to maximize total expected
$ (payouts to the owner minus fees) under every account's rules, with correlated signals and different rules; real engine,
current balances, 2026-like and bad-market regimes; today's routing vs the optimum. Paper research only; nothing live changes.

## Engine (no new trading model)
`research/plans/rank.py` + `research/onebook/book.py` (the "books" = signal mixes x sizes on one account, real fills: ATLAS at
10 ticks a side, LIT two_week eval sizing, the funded presets, every MFFU rule incl. Rapid's 30% eval best day + $500 / $250 since
the last payout, Builder 50% funded best day, soft DLL, EOD trailing floors + lock, buffers, min / max payouts, splits) and the
forecaster's start-from-today idea (`engine/eval_mc.py`): each account starts from its CURRENT state (board 2026-11-26 11:15 ET):

| id | account | stage | balance vs start | room | today's routing |
|---|---|---|---|---|---|
| Z50 | Zlarior, MFFU Builder 50K | eval, ~session 27 | -$822 | $1,009 | B01 LIT only (combo lane built, OFF) |
| Z25 | Zlarior 25K #2, MFFU Builder 25K | eval, ~session 4 | +$19 | $996 | B01 LIT only |
| R25 | MFFU Rapid EOD 25K | eval, ~session 4 | -$5 | $995 | B03 LIT + ATLAS (engine/rapid.py lanes; live = LIT priority, B03 = first-come: the nearest book) |
| A25 | ATLAS, MFFU Builder 25K | FUNDED, 0 payouts | +$401 (MFFU $0 view) | $1,000 | B02 ATLAS only |

A slot = that account for 126 sessions (6 months): eval -> pass -> funded (book.py's GAP) -> payouts (owner's share);
a failed eval / lost funded account is re-bought the next session at the owner's price (rank.PLANS) and starts fresh.
Paths: 1,000 Monte Carlo paths of 5-session blocks per regime, seed 23 = rank.py; **the SAME path for every account** (the
signals are the same days, so the correlation is in the sample). Regimes: 2026 H1 (Jan-Jun), 2026 H2 (Jul-Oct 16) = 2026-like;
2021-25 (REF) and 2025 alone = bad-market. Cross-account no-hedge: the ATLAS stream already drops entries blocked by LIT's
opposite trade / armed setup (tools/atlas.account_units), so per-account books stay valid together.

## Choices (pre-listed): every book of research/onebook/book.py BOOKS for every account (13 x 4 = 52 cells)
B01 LIT only, B02 ATLAS only, B03 LIT + ATLAS first-come, B04 LIT priority budget, B05 ATLAS NY only, B06 ATLAS London only,
B07 strict windows, B08 ATLAS x0.5 in the eval, B09 LIT eval then LIT + ATLAS funded, B10 LIT x0.75, B11 LIT x0.5 in the eval,
B12 + BLITZ $300, B13 ATLAS lane x2. A routing = one book per account (13^4 = 28,561 routings).

## Objective and pick rule (fixed now)
Per account x book x regime: mean net $ (owner payouts - fees) over 6 months, p10, P(no payout), P(account lost), first payout.
The mean of a routing = the sum of its accounts' means (same paths), so the optimum by mean is the best book per account;
the routing's risk (p10 of the TOTAL, P(total < 0)) is computed on the joint paths.
**Pick per account**: the book with the highest mean over 2026 H1 + H2 among books that beat today's book in BOTH 2026 halves
and lose at most $100 vs today's book in 2021-25 (6-month mean); none = keep today's book.
**Card** when the picked routing beats today's in both 2026 halves by > $100 / 6 months in total AND its joint p10 is not
worse by more than $200; otherwise "keep today's routing". Luck: 52 cells x 4 regimes; the per-account pick is a max over
13 books, so the gain is also shown on the other 2026 half than the one each pick looks best in (the split check).
