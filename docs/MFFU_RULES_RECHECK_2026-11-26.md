# MFFU rules re-check 2026-11-26 (vs `research/lit/mffu_rules.json`, `engine/funded_life.py`, `engine/rapid.py`, `docs/ACCOUNT_RULES.md`)

How: all 48 MyFundedFutures pages our rulebook cites were fetched today (help.myfundedfutures.com + myfundedfutures.com plan pages,
saved text in the session scratchpad, not committed) and read rule by rule; `python -X utf8 tools/rules_watch.py` (the daily watcher)
ran too: **46 of 46 watched rules unchanged** (MLL, DLL, targets, max micros, consistency, buffers, payout min / max, cycle days, sim
payouts, accounts per user, inactivity 7 days, T1 news 2 minutes, Rapid $10,000 live day). Nothing in the live rules or configs was changed.

## Changes / gaps found (5)

| # | Rule (MFFU's words, page) | What our code / docs do | Money? | Where to update |
|---|---|---|---|---|
| 1 | **Builder: "Net Profit Required (Subsequent Payouts): $250 (25K) / $500 (50K) since last payout"** (Builder 25K + 50K guides, payout table) | `engine/funded_life.track` only needs the cycle profit > $0 (plus >= the minimum above the buffer). After a payout that left more than the max above the buffer, the tracker can say READY while MFFU would refuse (e.g. 25K: $1,900 above -> request $1,000 -> $900 left -> +$150 the next day = $1,050 above = "ready", MFFU needs $250 since the payout). Rare with the owner's ask-the-max habit; a refused request, never a breach. Research sims (`research/plans/rank.py` Funded, `tools/atlas_funded.py`) use the same tracker. | small (a refused request / a slightly optimistic payout speed in research) | `engine/funded_life.py` track(), the `elif cprof <= 0 and cyc:` check (~line 156): add `elif n_pay > 0 and cprof < P["pay_min"]: why.append(f"{_money(cprof)} made since the last payout, MFFU needs {_money(P['pay_min'])}")` + a test in `tests/test_funded_life.py`; rulebook keys `builder_25k/50k ... net_since_last_payout` (new). **Needs-owner-yes card** (touches the live payout tracker) - see below. |
| 2 | **Rapid: "First payout eligible 24 hours after first trade"** (Payout Policy Overview, MFFU's own page) | `engine/rapid.py` payout_advice already waits 24 h, marked "not on MFFU's own Rapid pages ... needs MFFU confirm"; rulebook `rapid_eod_25k ... first_payout_wait` = "not stated by MFFU" | no (the code already does it) | `research/lit/mffu_rules.json` line ~1158 -> status confirmed, source article 13745661; the comment in `engine/rapid.py` ~line 504-509 |
| 3 | **Rapid: "each payout after that unlocks once your net profit since your last payout reaches $250 (25K) / $500 (50K)"** - now on MFFU's own Rapid EOD 25K / DLL pages | `engine/rapid.py` already enforces it (`since` 250 / 500); `research/plans/rank.py` labels it "third-party plan guides" | no | comments only: `research/plans/rank.py` spec() ("third-party plan guides" -> MFFU Rapid EOD pages) |
| 4 | **Builder live: "Live Post-Breach Cooldown: 21 days"** - after a LIVE account is breached, no sim funded trading and no new evals / resets for 21 calendar days | not in ACCOUNT_RULES (the rulebook has a short "cooldown" note) | yes once live (after 5 sim payouts): a live breach freezes EVERY MFFU account for 3 weeks | `docs/ACCOUNT_RULES.md` "Common to every MFFU account" (new row); `engine/payout_autopilot` already stops before the 5th payout (fleet plan), so no code today |
| 5 | **Builder 25K now has a "Legacy No DLL" version** (related article on the 25K guide) and the Builder plan page says **"Payouts every 48 hours"** (cadence) while the guides say "48 hours after your first trade" + 2 qualifying days per cycle | our 25K preset = the DLL version ($600 soft) = what the owner holds; cycle = 2 traded days | no today | `docs/ACCOUNT_RULES.md` notes; ask MFFU only if the owner wants payouts every other day (the 2-traded-days cycle already makes that the fastest) |

Unchanged (checked today, page by page): Builder 25K / 50K eval (target, MLL EOD trailing + lock at +$100, soft DLL $600 / $1,000,
2 / 4 minis = 20 / 40 micros, no eval consistency, 1 day), funded (start $0, buffer = MLL + $100 = $1,100 / $2,100, min $250 / $500,
max $1,000 / $2,000, 80/20, 50% consistency, 2 qualifying days, 48 h first wait, 5 sim payouts, MLL to $100 after the 1st payout,
2 / 1 sim funded on 25K / 50K); Rapid EOD 25K / 50K (target, MLL EOD + lock $100, no DLL by default / $500 / $1,000 soft with the
add-on resetting 18:00 ET, 20 / 30 micros, 30% eval consistency, 4 days, buffer $1,100 / $2,100, min $500, no cap, daily, 90/10,
T1 news banned on sim funded, 3 sim funded each); account limits (10 evals, 5 sim funded with 25K/50K only, plan caps, 3 with any
100K/150K); permitted hours (18:00 open, auto-close 16:10, holidays: NO auto-liquidation at the early close - the trader must be flat,
today's Thanksgiving week); news (T1 = FOMC, minutes, jobs, CPI; flat 2 min before / after, no working orders); inactivity 7 calendar
days (sim funded = all profits forfeited, tell support before a longer break); copy trading own accounts only; hedging banned;
prices (Builder 50K $153 list / $92 with CLUB, Rapid EOD 25K $162 list / $97 promo = the owner's $97.20).
The known open conflict stays: "one Builder sim funded per user" (Builder plan page + 50K guide) vs 1 x 50K + 2 x 25K (limits article).

## Needs-owner-yes card (from #1)
**MFFU payout rule we do not check: "$250 / $500 made since the last payout" on Builder accounts.**
- What changes: the payout tracker would also wait until the account made the minimum since the last payout before saying READY.
- Money: no $ change to trading; it only stops the bot from telling you a payout is ready on a day MFFU would refuse it (rare).
- Risk: none to the accounts. Code: 3 lines in `engine/funded_life.py` + a test; the lead lands it after your yes.
