# Business tracker

`research/business/prop_business.xlsx`: your prop-firm business in one Excel / Google Sheets / Numbers file. All totals
are live formulas. Blue text = you type it, black = formula (leave it), yellow = a setting.

| Sheet | What you do |
|---|---|
| Summary | Nothing: fees, payouts, net, return on fees, codes saved, accounts by status, pass rate, set-aside, goal |
| Settings | Set the tax set-aside %, the goal price, the monthly rate for the goal, accounts earning it, payout split |
| Accounts | One row per account: firm, plan, list price, price paid, codes used, start, status (drop-down), end |
| Fees | Every payment: eval purchase, reset, activation, subscription, data. Same account name as on Accounts |
| Payouts | Every payout that reached the bank: requested and received |
| Monthly P&L | Nothing: fees, payouts, net, set-aside and running totals per month (Oct 2026 - Sep 2029) |
| Tax set-aside | Nothing: the set-aside per year. **A savings rule, not tax advice**: ask a tax professional |
| Z06 goal | Nothing: saved so far, still needed, months to the goal at the rate in Settings, and at other rates |

Pre-filled: the MFFU Builder 50K eval, $91.80 with your discount code, started 2026-10-19 (Accounts row 4, Fees row 4).

Defaults (change them on Settings):
- Set-aside 30% of each winning month's net.
- Goal Corvette Z06 at $115,000 (a placeholder near the base price: put in your real quote).
- Rate $2,400 a month per account: LIT's H2 2026 paper rate (run `lit_live`). That is backtest P&L, not a payout:
  the funded-sizing study pays about $740-770 a month per account, so the "other rates" table shows $750 too. Put in your
  real average once payouts arrive.

Tips: use the same account name on Accounts, Fees and Payouts (the per-account totals match by it). When the bot's eval
passes, set Status to "Eval - passed" and add a new row for the funded account.

Rebuild from scratch (wipes what you typed): `python tools/build_business_tracker.py --force`.
