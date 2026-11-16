---
title: More strategies on ONE MFFU account - LIT + ATLAS (+ BLITZ) on the Builder 50K and on a Rapid EOD 50K
family: risk
date: 2026-11-16
status: promising - paper only. On the Builder 50K, adding ATLAS in the eval does NOT beat LIT alone (more 2-week fails). Adding it only after the account is funded does, in both 2026 halves. On a Rapid EOD 50K, LIT + ATLAS beats LIT alone in both halves. 2021-25 pays about $0 either way.
summary: Owner 2026-11-16 - "it shouldn't take 2 months to get a payout". Stored LIT (live), ATLAS (live EMA + MACD + S/R, never opposite LIT) and BLITZ (account C, never opposite LIT / ATLAS) trades were merged onto one account. LIT keeps its live size. Each added trade risks min($ cap, 30% of the room, the soft daily loss left), so one full stop-out never goes past the $1,000 soft daily loss. Costs are in, and every mix runs on the same Monte Carlo paths as LIT alone. Builder 50K - ATLAS $500 on the FUNDED account only (the eval stays LIT alone) moves the first funded payout from 26 / 23.5 to 17 / 15 sessions (Jan-Jun / Jul-Oct) and the 6-month account from $779 / $753 to $1,202 / $1,205 a month after fees. Adding BLITZ $300 too gives 15 / 13 sessions and $1,313 / $1,347. Putting ATLAS in the eval passes faster (median 5-6 sessions instead of 9) but fails more evals in 2 weeks (3.1% / 1.6% vs 0.8% / 0.2%; 2021-25 20% vs 0.6%). Rapid EOD 50K - LIT + ATLAS $500 halves the slow 30%-rule eval (median 22 / 21 sessions instead of 40 / 38). That is still about a month, not 2 weeks. The account pays $5,022 / $2,301 a month instead of $815 / $799. In 2021-25 every mix makes about $0 a month.
runs: none (research/lab/stack_one_account.json)
---

## For the owner (one minute)

| What (6 months, after the eval fees, the owner's share) | Jan-Jun 2026 | **Jul-Oct 2026 (check)** | 2021-25 |
|---|---:|---:|---:|
| **Builder 50K, LIT alone (today)**: first funded payout, sessions after funding | 26 | **23.5** | 43 |
| ... $ a month for the whole account (eval + funded) | $779 | **$753** | -$9 |
| **Builder: LIT eval, then LIT + ATLAS $500 once funded**: first payout | **17** | **15** | 21 |
| ... $ a month | **$1,202** | **$1,205** | -$1 |
| Builder: LIT eval, then LIT + ATLAS $500 + BLITZ $300 once funded: first payout | 15 | **13** | 19 |
| ... $ a month | $1,313 | **$1,347** | $2 |
| Builder: ATLAS $500 in the eval too: eval passes in (median sessions) | 5 (LIT 9) | **6** (LIT 9) | 5 (LIT 14) |
| ... but fails within 2 weeks | 3.1% (LIT 0.8%) | **1.6%** (LIT 0.2%) | **20.1%** (LIT 0.6%) |
| **Rapid EOD 50K, LIT alone**: eval passes in | 40 | **38** | 46 |
| **Rapid EOD 50K, LIT + ATLAS $500**: eval passes in | **22** | **21** | 29 |
| ... first payout (sessions from buying) | 34 (LIT 78) | **37** (LIT 71) | 66 (LIT 90) |
| ... $ a month for the account | $5,022 (LIT $815) | **$2,301** (LIT $799) | $63 (LIT -$18) |

In plain words:
- **Yes, more strategies on one account makes the first payout come sooner.** The account gets about 2 winning days a
  week instead of 1. That is what the 50% best-day rule and the $2,600 line need.
- **On the Builder, add ATLAS only after the account is funded.** If ATLAS also trades the eval, the eval passes faster
  but fails more often. In a 2021-25-type market, 1 in 5 evals fails within 2 weeks instead of 1 in 170.
- **Rapid EOD: more winning days helps a lot, but does not make it a 2-week eval.** It goes from about 2 months to about
  1 month.
- **It is a 2026 bet.** In 2021-25, LIT and ATLAS make about $0 a month on any account, with or without stacking.
- No funded account is ever lost in these runs (0%), because each trade is sized from the room left. The real risk is a
  funded account that pays nothing in 6 months: LIT alone 5.5% / 7.2%, LIT + ATLAS 3.7% / 5.3%, 2021-25 79-81%.

Next (paper only, nothing changed):
1. Decide yes / no on "ATLAS trades on Zlarior's funded 50K once it is funded" (the eval stays LIT only).
2. On yes: the lead builds it, as a funded-only route with the account_b no-opposite rule, and Sim-tests it first.
3. Re-check before buying a Rapid EOD: `python -X utf8 tools/money/stack_one_account.py`

## 1. What was tested

- **Already tested (Tested and rejected / second-mix.md, 2026-10-22):** ATLAS members on LIT's EVAL with "one position,
  LIT priority, max 2 a day". There the H1 pick fell below LIT in H2, and those rules blocked 12-15 LIT trades. That test
  was not repeated here. This study changes three things:
  - LIT is never blocked (ATLAS gives way to LIT under the account_b rule).
  - The funded first payout and the 6-month account $ are measured, not only the eval.
  - The Rapid EOD 50K is included.
- **Trades.**
  - LIT: the 120 live 2026 trades + 511 REF trades (tools/account4_sim.trades), at the live eval size (two_week) and the
    fleet funded size (UP50).
  - ATLAS: tools/atlas.account_units(BASE). It never trades opposite LIT: it is blocked while LIT holds or has an armed
    setup the other way, and it is closed (HEDGE) when LIT enters opposite. It also keeps its own one position and max 2 a
    day.
  - BLITZ: tools/blitz25k_lib.trades(mode "lit+atlas"), never opposite LIT or ATLAS.
- **Costs.** $1.90 a micro, plus 1 tick on market fills and stops.
- **Accounts.**
  - Builder 50K: account4_sim.Ev / uprisk.Funded rules ($91.80).
  - Rapid EOD 50K: engine/copy_accounts rules ($94).
    - Eval: 30% best day, 4 days, and the fleet's 30% best-day size guard on every trade.
    - Funded: daily payouts above $2,100, $500 min, 90%, no consistency rule.
    - Tier-1 news: flat from 2 minutes before to 2 minutes after the release, for every strategy.
- **Monte Carlo.** Eval: 2,000 paths x 60 sessions. Funded and the 6-month slot: 1,000 x 126 sessions. 5-session blocks,
  the same paths for every mix.

## 2. Builder 50K, every mix (Jan-Jun / Jul-Oct / 2021-25)

"Fixed $" = the real days in order: LIT at $500 a trade, the added ones at their own $. This shows the trades themselves,
not the account.

| Mix | trades/wk | PF | $/mo fixed $ | max DD fixed $ | eval median | 2-wk pass / fail % | funded 1st payout | funded $/mo | slot $/mo after fees |
|---|---|---|---|---|---|---|---|---|---|
| LIT alone | 3.1 / 2.6 / 2.4 | 3.49 / 2.71 / 1.02 | 5,126 / 3,707 / 38 | -3,271 / -2,228 / -19,725 | 9 / 9 / 14 | 47.5/0.8, 47.3/0.2, 11.7/0.6 | 26 / 23.5 / 43 | 929 / 915 / 66 | 779 / 753 / -9 |
| + ATLAS $250 | 7.2 / 5.5 / 7.0 | 3.25 / 2.66 / 1.05 | 8,139 / 5,122 / 241 | -2,525 / -2,003 / -25,295 | 7 / 8 / 9 | 61.0/2.5, 53.2/0.8, 17.6/14.0 | 17 / 17 / 22 | 1,240 / 1,179 / 93 | 1,280 / 1,173 / 12 |
| + ATLAS $500 | 7.2 / 5.5 / 7.0 | 3.12 / 2.74 / 1.07 | 11,960 / 7,351 / 486 | -3,017 / -2,480 / -37,025 | 5 / 6 / 5 | 66.0/3.1, 62.0/1.6, 22.4/20.1 | 17 / 15 / 21 | 1,232 / 1,214 / 76 | 1,329 / 1,347 / 8 |
| + BLITZ $150 | 11.6 / 9.4 / 10.9 | 2.77 / 2.34 / 1.03 | 6,090 / 4,374 / 112 | | 8 / 9 / 15 | 48.8/1.7, 50.6/0.7, 11.8/2.6 | 24 / 22 / 40 | 943 / 1,054 / 72 | 804 / 929 / -3 |
| + BLITZ $300 | 11.6 / 9.4 / 10.9 | 2.41 / 2.39 / 1.03 | 6,352 / 5,128 / 160 | | 7 / 8 / 12.5 | 52.5/2.4, 54.1/0.9, 13.8/5.0 | 19 / 18 / 29 | 1,062 / 1,134 / 79 | 1,004 / 1,107 / 1 |
| + ATLAS $250 + BLITZ $150 | 15.7 / 12.3 / 15.5 | 2.82 / 2.39 / 1.05 | 9,102 / 5,789 / 314 | | 6.5 / 8 / 9 | 61.6/3.2, 56.0/1.2, 17.8/17.4 | 17 / 15 / 21 | 1,244 / 1,224 / 100 | 1,322 / 1,303 / 14 |
| + ATLAS $500 + BLITZ $300 | 15.7 / 12.3 / 15.5 | 2.63 / 2.52 / 1.06 | 13,186 / 8,773 / 608 | -2,950 / -2,480 / -33,476 | 5 / 6 / 5 | 67.9/4.2, 68.0/1.9, 22.2/27.6 | 15 / 13 / 19 | 1,257 / 1,242 / 78 | **1,484 / 1,567 / 10** |
| **LIT eval; funded + ATLAS $500** | (eval = LIT) | | | | 9 / 9 / 14 | = LIT alone | **17 / 15 / 21** | 1,232 / 1,214 / 76 | **1,202 / 1,205 / -1** |
| **LIT eval; funded + ATLAS $500 + BLITZ $300** | (eval = LIT) | | | | 9 / 9 / 14 | = LIT alone | **15 / 13 / 19** | 1,257 / 1,242 / 78 | **1,313 / 1,347 / 2** |

Verdict rule, in BOTH 2026 halves: more slot $, a first payout no later, and no more 2-week eval fails (+0.5 point).
- Every "ATLAS / BLITZ in the eval" mix fails the 2-week-fail check. Its slot $ is the highest
  ($1,484 / $1,567), but it buys that with more failed evals (4.2% / 1.9%, and 27.6% in 2021-25).
- Both "funded only" mixes pass all three checks.
- The added strategies do not hurt LIT's trades: LIT's entries are identical in every mix.

## 3. Rapid EOD 50K (does a second strategy fix the slow 30% eval?)

| Mix | eval median sessions | 2-wk pass / fail % | funded 1st payout (from funding) | funded $/mo | slot $/mo | slot 1st payout (from buying) |
|---|---|---|---|---|---|---|
| LIT alone | 40 / 38 / 46 | 0.7/0, 0/0, 0.1/0 | 19 / 19 / 28 | 2,082 / 1,525 / 131 | 815 / 799 / -18 | 78 / 71 / 89.5 |
| + ATLAS $250 | 27 / 27 / 36.5 | 2.5/0, 2.4/0, 0.3/1.2 | 9 / 14 / 12 | 4,991 / 2,423 / 220 | 3,591 / 1,758 / 22 | 42 / 48 / 71 |
| **+ ATLAS $500** | **22 / 21 / 29** | 5.2/0, 9.2/0, 1.1/2.9 | 6 / 10 / 7 | 6,269 / 2,884 / 251 | **5,022 / 2,301 / 63** | **34 / 37 / 66** |
| + ATLAS $250 + BLITZ $150 | 25.5 / 24 / 32 | 4.2/0, 5.3/0, 0.5/1.8 | 8 / 12 / 12 | 5,040 / 2,933 / 230 | 3,733 / 2,230 / 41 | 39 / 41 / 73 |
| + ATLAS $500 + BLITZ $300 | 17 / 17 / 22 | 13.1/0, 20.3/0, 2.2/7.6 | 6 / 9 / 6 | 7,013 / 3,897 / 240 | 5,857 / 3,265 / 84 | 28 / 30 / 58 |
| LIT eval; funded + ATLAS $500 | 40 / 38 / 46 | = LIT alone | 6 / 10 / 7 | 6,269 / 2,884 / 251 | 2,797 / 1,657 / -1 | 70 / 61 / 82 |

- All five Rapid mixes beat LIT alone in both halves.
- The eval needs 4+ days and no day above 30% of the profit. A second strategy gives more, smaller winning days, so the
  eval goes from about 2 months to about 1 month. It is still not a 2-week eval.
- Treat the Rapid $ as optimistic. The model takes out everything above $2,100 every day, with no payout cap, and sizes
  at 60% of the room. MFFU's real per-payout limits, if any, would lower it. That needs a fresh check of the help center
  before buying.

## 4. Honest limits

- Within a day, trades are played in entry order on closed P&L. Two same-direction trades open at once are not netted
  into one position, and the shared soft daily loss is checked trade by trade.
- No funded account is ever "lost" (0% in every mix). Each trade is sized from the room to the floor, so a bad run
  shrinks the account into a zombie instead of breaking it. The real risk is "no payout in 6 months":
  - Builder, LIT alone: 5.5% / 7.2%.
  - Builder, LIT + ATLAS funded: 3.7% / 5.3%.
  - 2021-25, any mix: 75-81%.
- ATLAS already trades its own 25K. On Zlarior's funded account the same ATLAS signals would run twice, on two accounts.
  The two accounts would move together more on ATLAS days.
- In 2021-25 every mix pays about $0 a month: neither LIT nor ATLAS has an edge there.
- One Monte Carlo seed pair only (7 / 23, as account4_sim); a 100-path run gave the same ranking, so the gaps above are well past the noise.
- Nothing live was changed: no live_model*.json, second_model.json or engine file. Any route needs the owner's yes, a
  build by the lead and a Sim test.
