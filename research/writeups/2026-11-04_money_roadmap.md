# Money roadmap: the next 12 months (2026-11-04)

Research and display only. Nothing live was touched. Numbers: `tools/money_roadmap.py` -> `research/props/roadmap.json` (3,000 sampled 12-month paths per half). Two versions of every number: **Jan-Jun 2026 (H1)** and **Jul-Oct 2026 (H2)**. **H2 is the conservative one: quote H2.**

## Verdict

- **Do first:** ATLAS on the 25K first: it is the first cash (typical first payout 2026-12-21 conservative) and pays its price back in month 2. Run all three accounts at once (LIT 50K, ATLAS 25K, BLITZ 25K): buying all three on day 1 beats every staggered order, and the fees are only $198.
- **Then:** LIT on the 50K second: the biggest total ($6,549 in 12 months) but its first payout is later. BLITZ is the weakest of the three ($2,318): a second ATLAS or a LIT copy would earn more in that slot. When an account has been paid its 5th payout (it then moves to a live account), buy the next ATLAS 25K eval ($43) first: a re-buy adds $3,087 (conservative) in the year, against $544 for LIT and $194 for BLITZ.
- **Expected first payout:** First payout from any account: typical 2026-12-16 (conservative, Jul-Oct) to 2026-12-03 (Jan-Jun); 1 in 10 paths already by 2026-11-18 / 2026-11-23, 9 in 10 by 2026-12-31 / 2027-01-27. It comes from ATLAS (typical 2026-12-21 conservative, 2026-12-04 Jan-Jun); LIT on the 50K comes later (typical 2027-02-09 / 2027-01-22).
- **Best case / worst case by month 12:** Cash to the owner by month 12 (2027-11-05), after every fee including the $198 already paid for the three evals: conservative (Jul-Oct) middle path $13,105, worst case (1 path in 10) $9,759, best case (1 in 10) $14,892; Jan-Jun version middle $14,345, worst $11,820, best $15,370. The worst of all 3,000 sampled paths still ends at $3,512 (H2); no path ends below $0.
- **With re-buying:** If the owner buys a new eval each time an account has been paid 5 times: $16,546 middle path conservative ($12,060 worst / $21,063 best), $22,414 Jan-Jun.
- **Why it fades:** The money is front-loaded: each account stops paying after 5 payouts (5 x $1,000 x 80% = $4,000 on a 25K, 5 x $2,000 x 80% = $8,000 on the 50K, then it moves to a live account that this table does not count), so months 8-12 fall off unless a new eval is bought.

## Month by month, all three accounts (cash to the owner after the 80% split, fees at his real prices)

| Month | Dates | Payouts in (H2) | Fees out (H2) | Net (H2) | Running total H2 (average; worst 1-in-10 to best 1-in-10) | Running total H1 (average) |
|---|---|---|---|---|---|---|
| 1 | 11-05 to 12-04 | $287 | $41 | $246 | $246 (-$106 to $800) | $576 |
| 2 | 12-07 to 01-06 | $977 | $37 | $941 | $1,187 (-$129 to $2,623) | $2,156 |
| 3 | 01-07 to 02-05 | $1,372 | $24 | $1,348 | $2,535 ($588 to $4,800) | $4,067 |
| 4 | 02-08 to 03-09 | $1,543 | $17 | $1,526 | $4,061 ($1,471 to $7,054) | $6,009 |
| 5 | 03-10 to 04-08 | $1,542 | $11 | $1,531 | $5,592 ($2,498 to $8,802) | $7,777 |
| 6 | 04-09 to 05-07 | $1,483 | $9 | $1,474 | $7,066 ($3,831 to $10,360) | $9,310 |
| 7 | 05-10 to 06-08 | $1,384 | $6 | $1,378 | $8,444 ($5,116 to $11,819) | $10,605 |
| 8 | 06-09 to 07-09 | $1,211 | $4 | $1,207 | $9,651 ($6,194 to $12,971) | $11,721 |
| 9 | 07-12 to 08-09 | $1,054 | $4 | $1,050 | $10,701 ($7,122 to $13,932) | $12,594 |
| 10 | 08-10 to 09-08 | $919 | $3 | $916 | $11,617 ($8,167 to $14,638) | $13,243 |
| 11 | 09-09 to 10-07 | $724 | $3 | $721 | $12,338 ($9,202 to $14,929) | $13,747 |
| 12 | 10-08 to 11-05 | $586 | $2 | $584 | $12,922 ($9,957 to $15,090) | $14,128 |
| **12 months** | | **$13,082** | **$161** | **$12,922** | middle path $13,302, worst $9,957, best $15,090 | $14,128 (middle $14,543, worst $12,018, best $15,568) |
| **after the $198 already paid** | | | | **$12,724** | middle $13,105, worst $9,759, best $14,892 | $13,931 (middle $14,345) |

Check: payouts $13,082 - fees $161 = net $12,922 (H2); the three evals now running ($198: 91.80 + 43 + 63) are already paid and are not counted as cash out. A negative worst case in months 1-2 is a reset (a new eval) before any payout.

## By account (12 months, average path)

| Account | Payouts in H2 / H1 | Fees H2 / H1 | Net H2 / H1 | First payout, typical H2 / H1 | Chance of a payout by month 3 H2 / H1 |
|---|---|---|---|---|---|
| LIT on the 50K | $6,592 / $7,529 | $43 / $51 | $6,549 / $7,478 | 2027-02-09 / 2027-01-22 | 47.5% / 61.8% |
| ATLAS on a 25K | $4,120 / $4,206 | $66 / $74 | $4,055 / $4,132 | 2026-12-21 / 2026-12-04 | 85.7% / 95.4% |
| BLITZ on a 25K | $2,370 / $2,574 | $52 / $56 | $2,318 / $2,518 | 2027-03-02 / 2027-02-11 | 34.1% / 45.7% |

## Chance each account passes its eval: in 2 weeks and by the end of month 1

| Account | 2 weeks, published engine study (pass / fail) H2 | H1 | Model: 2 weeks H2 | Model: month 1 H2 | Model: month 1 H1 |
|---|---|---|---|---|---|
| LIT 50K | 58.6% / 20.9% | 52.9% / 17.8% | 19.3% / 0.0% | 44.6% / 3.3% | 61.2% / 8.5% |
| ATLAS 25K | 43.5% / 0.0% | 65.5% / 0.0% | 58.3% / 18.2% | 73.0% / 24.5% | 73.4% / 26.5% |
| BLITZ 25K | 36.2% / 21.7% | 49.6% / 26.9% | 33.9% / 7.8% | 55.7% / 22.0% | 64.3% / 24.2% |
| LIT 50K, eval sized as the engine study | 58.6% / 20.9% | 52.9% / 17.8% | 38.5% / 7.1% | 63.1% / 21.5% | 69.4% / 22.7% |

The published 2-week figures come from the engine-faithful eval studies (the ones on Plutus). The month-1 figures come from the roadmap's daily model, which is rougher: it passes LIT more slowly than the engine study and fails ATLAS more often (25% vs 0%, a $43 re-buy each). So the roadmap is **slow on LIT cash, harsh on ATLAS fails**. The row 'eval sized as the engine study' shows LIT when its eval is risked as the study does.

## Which account to buy (each one alone), and the payback month

| Account (price) | Net in 12 months H2 / H1 | First payout, typical H2 / H1 | Paid back by month 3, H2 / H1 | Payback month (typical path) H2 / H1 |
|---|---|---|---|---|
| ATLAS 25K ($43.00) | $4,055 / $4,132 | 2026-12-21 / 2026-12-04 | 85.7% / 95.4% | month 2 / month 1 |
| LIT 50K ($91.80) | $6,549 / $7,478 | 2027-02-09 / 2027-01-22 | 47.5% / 61.8% | month 4 / month 3 |
| LIT copy 25K ($63.00) | $3,381 / $3,701 | 2027-02-02 / 2027-01-20 | 53.0% / 63.4% | month 3 / month 3 |
| BLITZ 25K ($63.00) | $2,318 / $2,518 | 2027-03-02 / 2027-02-11 | 34.1% / 45.7% | month 4 / month 4 |

Payback = the month the account's running total (everything paid out minus its price and any re-buys) is above zero on the typical path.

## The second 25K: BLITZ, a second ATLAS, or a LIT copy? (LIT 50K + ATLAS 25K + this)

| Second 25K | 12-month net, all three H2 / H1 | Worst 1-in-10 H2 | That account alone, net H2 / H1 | Its payback month H2 |
|---|---|---|---|---|
| BLITZ on the 2nd 25K (the plan) | $12,922 / $14,128 | $9,957 | $2,318 / $2,518 | month 4 |
| a 2nd ATLAS on the 2nd 25K | $14,658 / $15,743 | $11,812 | $4,055 / $4,132 | month 2 |
| a LIT copy on the 2nd 25K | $13,985 / $15,311 | $9,960 | $3,381 / $3,701 | month 3 |

A second ATLAS or a LIT copy beats BLITZ in both halves on money, because BLITZ is the slowest and smallest payer. BLITZ is still the only one that is not the same bet twice (its days are about 0 / -0.06 correlated with ATLAS / LIT; a copy of ATLAS is the same days). Not checked: whether MFFU lets one trader run the same strategy on two of his own accounts; check the rules before buying a copy.

## Does the order of buying matter? (one a month, nothing already paid)

| Order | 12-month net H2 | Worst 1-in-10 H2 | 12-month net H1 |
|---|---|---|---|
| all three on day 1 | $12,724 | $9,759 | $13,931 |
| LIT 50K, then BLITZ 25K, then ATLAS 25K (one a month) | $12,460 | $9,489 | $13,745 |
| LIT 50K, then ATLAS 25K, then BLITZ 25K (one a month) | $12,322 | $9,293 | $13,579 |
| BLITZ 25K, then LIT 50K, then ATLAS 25K (one a month) | $12,214 | $9,063 | $13,655 |
| ATLAS 25K, then LIT 50K, then BLITZ 25K (one a month) | $11,978 | $8,831 | $13,364 |
| BLITZ 25K, then ATLAS 25K, then LIT 50K (one a month) | $11,783 | $8,362 | $13,355 |
| ATLAS 25K, then BLITZ 25K, then LIT 50K (one a month) | $11,685 | $8,357 | $13,230 |

All three on day 1 is the best in both halves: waiting costs $264 to $1,039 over the year (H2), $186 to $700 (H1). Fees are so small ($198 for the three) that cash on hand never decides the order. If one had to wait, the best staggered order in both halves is **LIT 50K, then BLITZ 25K, then ATLAS 25K**: the slow payers get the head start, and ATLAS, which finishes its 5 payouts fastest, loses least by waiting.

## When an account finishes its 5 payouts: what a re-buy is worth (12 months)

| Re-buy a new eval for | Adds in 12 months H2 (conservative) / H1 | Price |
|---|---|---|
| ATLAS 25K | $3,087 / $6,257 | $43.00 |
| LIT 50K | $544 / $2,039 | $91.80 |
| BLITZ 25K | $194 / $322 | $63.00 |

A re-buy only pays if the new account can finish inside the year: ATLAS (first payout in about 5 to 6 weeks) fits twice; LIT on the 50K and BLITZ rarely finish a second round inside the year, so a re-buy there pays mostly in year 2. The sum, with every re-buy: see 'With re-buying' in the verdict.

## What to trust, and what not

- **Daily model.** One P&L per session, the same funded rules as `tools/second_plan.py` (80% split, payout floor and cap, 2 trading days a cycle, best day <= 50% of the cycle, 5 payouts then live). Its first six months match what is already published (`sn_plan.json`: $1,532 H1 / $1,136 H2 a month; this run: $1,552 / $1,178 a month), but spread over 12 months it fades as accounts reach 5 payouts.
- **Live accounts are not counted.** After the 5th payout an account moves to a live account (Blue Row Capital); its later payouts are not in these numbers. Re-buying is shown as a separate line.
- **Reset fee unknown** (no price published for one-time plans): a breach is priced as a new eval at his real price.
- **Only 2026 data**: six months to pick on (Jan-Jun) and four to check on (Jul-Oct), in 5-session blocks. H2 is the lower of the two versions, not a guaranteed floor. Paper only; no payout is ever requested by this code.
- BLITZ here uses the stored funded size ($150 a trade, a day capped at +$400). The later-break size fix proposed in the BLITZ study is not applied (untested here), so BLITZ may be understated.
- The model passes the LIT eval more slowly than the engine study (see the pass table), so LIT's first payout is later here than in `lit_funded_firms` (about 40 sessions from purchase there).

## Next steps (owner)

1. Run LIT, ATLAS and BLITZ together now; nothing to buy until an account has been paid 5 times.
2. When an account is paid its 5th payout, buy the next ATLAS 25K eval ($43) first.
3. Re-run `python -X utf8 tools/money_roadmap.py` after the 2026 data grows; check with `python -X utf8 -m tests.test_money_roadmap`.
