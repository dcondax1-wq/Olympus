# POSEIDON (order-flow lane A) full-year out-of-sample check - 2026-11-28 (did not run: no new days)

**Status: PENDING. The year of tick days did not reach the cloud tonight, so there is nothing out of sample to score yet.**

| step | result |
|---|---|
| `tools/data_pull.py --latest --of` (03:31 UTC) | asked (request a7c5f48b14); **no answer from the PC in 9 min** |
| `tools/of_backfill.py --wait 25` (03:41 UTC) | asked "bf" (request bf84172d8d, 53 days held); **0 pages in 25 min**; the PC said nothing about what it holds |
| PC feed at the same time | reporting (8-12 min old), code f80204f, tick recorder `tr` = [313, 60, 1] (313 tick days on the PC) |
| branch `of-store` | does not exist yet (no earlier backfill ever stored a page) |

Why no pages (not proven from the cloud side): the PC answers asks from its datafeed child (engine/datafeed / engine/ofbackfill),
which sends a page only when ntfy's own message count leaves room after the rest-of-day projection + reserves, and never more
than DAILY_CAP=8 answers a day / one "of" answer per 20 h. Friday was a heavy alert day (Telegram/ntfy redesign, trades, two
landings, PC update + restarts), so the likely blocker is the ntfy budget or the answered-today cap; a bars ask (data_pull) also
went unanswered, which points at the datafeed child not answering at all tonight rather than at the backfill code.
Both asks stay valid on ntfy for 3 h; a later `python -X utf8 tools/of_backfill.py --wait 25` collects them.

In-sample reproduction (the runner works): `research/orderflow/oos/run.py` on the 53 held files = 43 trading days
2026-09-28..11-25, first-of-day E5 book: 39 trades, 4.53/wk, 51.3% won, +0.51R, PF 2.40, +$2,931 at 1 micro, max DD $542
(= research/orderflow/monfix after|first|e5 exactly). One-at-a-time: 65 trades, 7.56/wk, +0.40R, PF 1.53, +$2,370, DD $1,163.

Eval note (simple sim, $50 max risk a trade): only 16 of the 39 first-of-day trades have a 1-micro risk <= $50 (median $63,
max $401), so with the of_ladder $50 cap lane A passes no Builder 25K / 50K eval inside the 43 days (0% pass, 0% blow, all still
open). Under that cap it is too small to move an eval; any eval use would need a larger cap (an owner decision after the forward gate).

`research/orderflow/oos/result.json` (the dashboard contract) is deliberately NOT written, so nq/orderflow.html keeps saying the
full-year result is pending instead of showing in-sample numbers as if they were out of sample.
Re-run when the days arrive: `python -X utf8 tools/of_backfill.py --wait 25` then `python -X utf8 research/orderflow/oos/run.py`.
