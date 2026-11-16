---
title: Rapid EOD 50K levers - different mixes per account, the Asia slot, give-up / withdrawal / day-cap rules
family: risk
date: 2026-11-16
status: mixed - paper only. Keeping a $1,000 cushion in the funded account (instead of taking everything above the buffer every day) pays more in both 2026 halves. Asia slot at $300 is a small plus in both halves but not built for live and worse in 2021-25. Different mixes per account make LESS money than identical copies in 2026 but cut "no account pays in 6 months" from 7.6% to 0.3-1.6% (Jul-Oct). Give-up / re-buy rules and day-profit caps are noise or worse.
summary: Owner is buying 2 (maybe 3) MFFU Rapid EOD 50K accounts. Three new levers on top of stack-one-account-2026-11-16.md (LIT + ATLAS $500 on a Rapid EOD), on the same trades, costs and Monte Carlo paths (reproduces that study exactly - $5,022 / $2,301 / $63 a month). (1) Decorrelation - 2 identical LIT + ATLAS accounts pay $10,044 / $4,602 a month (H1 / H2) vs $8,758-9,430 / $4,086-4,209 for different mixes; but P(no account pays in 6 months) drops from 2.3% / 7.6% to 0.2% / 1.4-1.6% and P(a payout by ~day 45) rises from 46% / 37% to 62-64% / 46%. 3 accounts, LIT + ATLAS | LIT + Asia + ATLAS | ATLAS + BLITZ - $13,605 / $7,044 vs $15,066 / $6,903, no-pay 0.1% / 0.3% vs 2.3% / 7.6%. Not adopted on money (fails H1), a risk choice for the owner. (2) Asia slot on Rapid - Asia at $300 - $5,133 / $3,035 vs $5,022 / $2,301, eval 20 / 19 sessions vs 22 / 21, but 2021-25 worse ($42 vs $63, 2-week fails 4.7% vs 2.9%) and the PC route does not trade Asia today; Asia at LIT size loses funded accounts (9.4% / 2.0% / 27.3% in 6 months) - rejected. (3a) Give-up / re-buy - at most +$104 / +$36 a month, 2021-25 worse - noise, not adopted. (3b) MFFU help center (2026-11-16) - daily payouts, $2,100 buffer, $500 min, no per-payout cap, 90%. Keeping a $1,000 cushion - $6,014 / $2,824 vs $5,022 / $2,301 a month, funded lost 0% either way, first funded payout 8 / 14 sessions vs 6 / 10 - adopt-candidate. (3c) Day-profit cap - today's 30% size guard is best; no guard takes 31-36 sessions instead of 21-22 and fails 20% in 2021-25.
runs: none (research/lab/rapid_levers.json)
---

## For the owner (one minute)

Numbers: a month, after the $94 eval fees, your 90% share, over 6 months. **Jan-Jun 2026** = where the idea was picked,
**Jul-Oct 2026** = the check, 2021-25 = a market where the bots have no edge.

| What | Jan-Jun | **Jul-Oct (check)** | 2021-25 | Verdict |
|---|---:|---:|---:|---|
| **Today's plan: 1 Rapid EOD, LIT + ATLAS, take everything above $2,100 each day** | $5,022 | **$2,301** | $63 | base |
| **Keep $1,000 in the funded account (take only what is above $3,100)** | **$6,014** | **$2,824** | $63 | **better in both halves: candidate** |
| Keep $2,000 in the account | $6,290 | $2,918 | $54 | better, but first payout ~2 weeks later |
| Take money once a week instead of daily | $5,517 | $2,479 | $62 | better, smaller than the $1,000 cushion |
| Add the Asia slot (18:00-02:00) at $300 a trade | $5,133 | **$3,035** | $42 | small plus in 2026, worse in 2021-25, not built for live |
| Give up and re-buy the eval early (best rule) | $5,126 | $2,337 | -$55 | noise: no |
| Stop for the day / other day caps in the eval | $4,307-5,067 | $1,781-2,308 | -$28-$60 | no: today's 30% guard is best |
| **2 accounts, identical (both LIT + ATLAS)** | **$10,044** | **$4,602** | $125 | most money |
| ... chance that NEITHER pays anything in 6 months | 2.3% | **7.6%** | 82% | |
| **2 accounts, different: LIT + ATLAS and ATLAS + BLITZ** | $8,758 | $4,086 | $137 | -$500/month in Jul-Oct... |
| ... chance that neither pays in 6 months | 0.2% | **1.6%** | 70% | ...but 5x less often "nothing" |
| 3 accounts identical | $15,066 | $6,903 | $188 | no-pay 2.3% / 7.6% |
| 3 accounts: LIT + ATLAS, LIT + Asia + ATLAS, ATLAS + BLITZ | $13,605 | **$7,044** | $172 | no-pay 0.1% / **0.3%** |

In plain words:
- **The one real money lever: leave $1,000 in the funded account.** The bot sizes from the room to the floor. With $1,000
  more room, LIT reaches its full $1,500 size more often, so the account earns more (+$500 to +$1,000 a month per account).
  You give up a little speed: the first funded payout comes about 2-4 trading days later. No account was lost either way.
- **Identical copies make the most money in a good market, different mixes are safer.** Two identical accounts win and lose
  on the same days. Different mixes pay less in 2026, but the chance of "6 months, $0 from every account" falls from about
  1 in 13 to about 1 in 60 (Jul-Oct), and the first payout of any account comes sooner (by ~day 45: 37% -> 46%).
- **Asia slot:** a little better in 2026 at $300 a trade, but worse in 2021-25 and the PC bot does not trade Asia today.
  Not worth building now. At LIT's full size it loses funded accounts: no.
- **Do not** give up and re-buy evals early, and **do not** add a "stop for the day" rule: the 30% guard the bot already
  has is the best of the tested rules.
- All of this is a 2026 bet. In 2021-25 every version earns about $0-$350 a month.

Next (paper only, nothing changed):
1. Yes / no: Rapid EOD funded payouts "keep $1,000 in the account" (the lead builds it in the payout planner / fleet, Sim first).
2. Pick for 2 accounts: identical LIT + ATLAS (most $) or LIT + ATLAS and ATLAS + BLITZ (fewer $0 half-years).
3. Re-check before buying: `python -X utf8 tools/money/rapid_levers.py`

## 1. What was tested and how

- **New angles only.** Checked against "Tested and rejected": Asia slot was rejected for the Builder eval
  (`lit-more-entries.md`, `second-mix.md`), never on a Rapid EOD with its 30% rule. Payout policy (`payout-policy.md`) was
  the Builder's ask line, not the Rapid EOD's daily payouts. Give-up rules existed only for ATLAS's 25K (zombie rule). The
  sh_asia / sh_trend stop hunts were never on a prop account of their own.
- **Same everything as `stack-one-account-2026-11-16.md`** (`tools/money/stack_one_account.py`): stored LIT (live), ATLAS
  (never opposite LIT), BLITZ (never opposite LIT / ATLAS) trades, LIT at its live eval size (two_week) and fleet funded size
  (UP50), added strategies at min($ cap, 30% of the room, the $1,000 soft day left), costs $1.90 a micro + 1 tick, Tier-1 news
  flat -2 / +2 min on the funded account, the fleet's 30% best-day size guard in the eval. The base row reproduces the last
  study exactly ($5,022 / $2,301 / $63 a month; eval 22 / 21 / 29 sessions).
- **New streams:** Asia slot = 18:00-02:00 entries of run `lit_more_ent_asia_slot_rr3` (`tools/atlas.asia_units`, an Asia
  trade overlapping an opposite LIT trade is dropped), sized as LIT or at $300. sh_asia / sh_trend = `research/stophunt/
  sh_asia_resweep.json`, `sh_trend_idm5.json` (`tools/atlas_v2.sh_units`) through the never-opposite-LIT rule, at $300.
- **Monte Carlo:** eval 2,000 paths x 60 sessions (seed 7), funded and 6-month slots 1,000 x 126 sessions (seed 23),
  5-session blocks. Every compared row uses the same paths; accounts bought together trade the SAME sessions on a path.
- **MFFU Rapid EOD payout rules (help center, read 2026-11-16, "Payout Policy Overview"):** daily payouts, first one 24 h after
  the first trade, $2,100 buffer (50K), $500 minimum, no consistency rule, 90% split, most approved instantly; automatic move to
  live after a $10,000 day. No per-payout or per-cycle cap is listed. Third-party plan guides add ">= $500 net profit since the
  last payout" and a $10,000 daily profit cap; both are in the model (the daily cap never binds). So the old "everything
  above the buffer daily, no cap" model was not optimistic on the cap; it stays the "take everything" row.
- **Pass rule for "adopt":** better than today's row in BOTH 2026 halves (more $ a month, and no worse on that lever's risk:
  no-pay +1 point, funded lost +1 point, 2-week eval fails +0.5 point). Gains under ~$50 or ~2% a month are called noise.

## 2. Each account mix on its own (one Rapid EOD 50K)

Trades/week, PF, net $, $/month and max DD = the real days in order at fixed $ (LIT $500, ATLAS $500, others $300).

| Mix | trades/wk | PF | net $ | $/mo fixed | max DD | eval median | 2-wk pass/fail % | funded 1st payout | funded lost 6m | slot $/mo | 1st payout from buying |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LIT + ATLAS (today) | 7.2 / 5.5 / 7.0 | 3.12 / 2.74 / 1.07 | 72,901 / 27,304 / 24,948 | 11,960 / 7,351 / 486 | -3,017 / -2,480 / -37,025 | 22 / 21 / 29 | 5.2/0, 9.2/0, 1.1/2.9 | 6 / 10 / 7 | 0 / 0 / 0 | 5,022 / 2,301 / 63 | 34 / 37 / 66 |
| ATLAS + BLITZ | 12.5 / 9.7 / 13.2 | 2.34 / 2.41 / 1.07 | 49,126 / 18,817 / 29,230 | 8,060 / 5,066 / 570 | -2,169 / -2,420 / -27,789 | 20 / 24 / 25.5 | 6.0/0, 8.4/0, 1.7/2.7 | 8 / 14 / 7 | 0 | 3,736 / 1,785 / 74 | 34 / 46 / 65 |
| LIT + BLITZ | 11.6 / 9.4 / 10.9 | 2.41 / 2.39 / 1.03 | 38,717 / 19,047 / 8,204 | 6,352 / 5,128 / 160 | -4,503 / -2,144 / -20,290 | 28 / 25 / 35 | 2.4/0, 5.8/0, 0.2/0.7 | 13 / 14 / 17 | 0 | 1,736 / 1,795 / 3 | 52 / 48 / 77 |
| LIT + Asia (LIT size) + ATLAS | 8.8 / 7.0 / 7.8 | 2.85 / 2.58 / 1.02 | 75,039 / 31,469 / 8,391 | 12,311 / 8,472 / 164 | -3,514 / -1,896 / -48,499 | 19 / 16 / 23 | 10.7/0, 21.8/0, 1.4/7.1 | 5 / 8 / 5 | **9.4 / 2.0 / 27.3** | 4,847 / 2,958 / 36 | 30 / 29 / 66 |
| LIT + Asia $300 + ATLAS | 8.8 / 7.0 / 7.8 | 2.98 / 2.64 / 1.04 | 74,496 / 29,613 / 15,344 | 12,222 / 7,973 / 299 | -3,293 / -1,896 / -43,280 | 20 / 19 / 27 | 7.5/0.1, 13.9/0, 1.1/4.7 | 6 / 9 / 6 | 0 | 5,133 / 3,035 / 42 | 31 / 32 / 63 |
| ATLAS + sh_asia + sh_trend | 6.9 / 7.0 / 8.7 | 2.76 / 2.36 / 1.17 | 48,546 / 18,446 / 63,730 | 7,964 / 4,966 / 1,243 | -1,816 / -1,913 / -18,953 | 19 / 21 / 25 | 10.4/0, 6.2/0.1, 2.5/2.9 | 8 / 12 / 9 | 0 | 4,408 / 1,908 / 185 | 31 / 41 / 57 |
| LIT + sh_asia + sh_trend | 5.9 / 6.6 / 6.4 | 3.08 / 2.33 / 1.21 | 38,137 / 18,676 / 42,704 | 6,257 / 5,028 / 833 | -3,548 / -2,333 / -10,457 | 28 / 22 / 32 | 4.3/0, 7.0/0.3, 0.4/0.6 | 14 / 12 / 20 | 0 | 1,986 / 1,965 / 162 | 51 / 42 / 69 |
| ATLAS + BLITZ + sh_asia | 14.0 / 12.3 / 15.4 | 2.35 / 2.20 / 1.09 | 53,281 / 20,882 / 45,710 | 8,741 / 5,622 / 891 | -2,568 / -3,122 / -27,235 | 16 / 20 / 22 | 14.5/0, 14.4/0.1, 3.8/6.3 | 7 / 11 / 7 | 0 | 4,775 / 1,982 / 127 | 28 / 41 / 54 |

(H1 / H2 / 2021-25. "Slot" = eval -> 2 sessions -> funded -> re-buy if lost, 126 sessions, after fees.)

## 3. Lever 1 - decorrelate the accounts (bought the same day, same paths)

"By day ~30 / ~45" = a payout from any account by session 21 / 32. DD = the accounts' summed daily trading P&L.

| Accounts | $/mo total | worst 10% $/mo | P(none pays 6m) | P(pay by ~day 30) | P(pay by ~day 45) | 1st payout any (median session) | combined max DD, Jan-Jun: median / worst 10% |
|---|---|---|---|---|---|---|---|
| 2x identical LIT + ATLAS | **10,044 / 4,602** / 125 | 3,189 / 536 / -157 | 2.3 / 7.6 / 82.2 | 15.5 / 12.6 / 0.9 | 46.1 / 36.8 / 2.7 | 34 / 37 / 66 | -3,627 / -3,997 |
| 2x LIT + ATLAS, ATLAS + BLITZ | 8,758 / 4,086 / 137 | 3,763 / 1,241 / -141 | 0.2 / 1.6 / 70.2 | 24.4 / 17.0 / 1.7 | 62.2 / 45.5 / 5.1 | 29 / 34 / 64 | -3,158 / -3,724 |
| 2x LIT + ATLAS, LIT + BLITZ | 6,758 / 4,096 / 65 | 2,630 / 1,062 / -125 | 0.7 / 1.7 / 74.0 | 16.2 / 14.5 / 0.9 | 50.8 / 42.4 / 2.8 | 32 / 35 / 70 | -2,724 / -3,593 |
| 2x LIT + ATLAS, ATLAS + sh | 9,430 / 4,209 / 248 | **4,328 / 1,249** / -125 | **0.2 / 1.4** / 61.1 | 26.1 / 17.0 / 2.4 | 63.6 / 46.3 / 7.6 | 28 / 33 / 57 | -3,165 / -3,688 |
| 3x identical LIT + ATLAS | **15,066** / 6,903 / 188 | 4,784 / 805 / -235 | 2.3 / 7.6 / 82.2 | 15.5 / 12.6 / 0.9 | 46.1 / 36.8 / 2.7 | 34 / 37 / 66 | -5,440 / -5,995 |
| 3x LIT + ATLAS, ATLAS + BLITZ, LIT + BLITZ | 10,494 / 5,881 / 139 | 4,472 / 1,973 / -204 | 0.0 / 0.7 / 63.8 | 24.8 / 18.2 / 1.7 | 64.5 / 48.1 / 5.2 | 28 / 33 / 67 | -3,922 / -5,041 |
| 3x LIT + ATLAS, LIT + Asia + ATLAS, ATLAS + BLITZ | 13,605 / **7,044** / 172 | 5,411 / **2,770** / -235 | 0.1 / **0.3** / 65.5 | **31.2 / 31.0** / 2.0 | 71.0 / **67.8** / 6.2 | 26 / **27** / 63 | -4,817 / -5,646 |
| 3x LIT + ATLAS, ATLAS + sh, LIT + BLITZ | 11,166 / 6,004 / 250 | 5,385 / 2,248 / -172 | 0.2 / 0.3 / 55.2 | 26.7 / 18.7 / 2.4 | 67.3 / 50.2 / 7.7 | 28 / 32 / 59 | -3,812 / -4,818 |
| 3x LIT + ATLAS, ATLAS + BLITZ + sh_asia, LIT + sh | 11,783 / 6,248 / **351** | **5,937** / 1,989 / -172 | **0.0** / 0.5 / **46.3** | **34.5** / 23.1 / 3.1 | **75.3** / 55.5 / 9.9 | 25 / 30 / 60 | -3,791 / -4,823 |

- **Verdict on money: no mix beats identical copies in both halves.** 2 accounts: every different mix pays less in H1 AND H2.
  3 accounts: the Asia mix pays +$141 in H2 but -$1,461 in H1.
- **Verdict on risk: every different mix is much safer.** "Nothing paid in 6 months" falls 5-25x, the worst-10% month is
  2-3x better in H2, the combined drawdown is smaller, and 2021-25 is better too (no-pay 82% -> 46-74%). Identical copies
  are one bet placed 2-3 times.
- The owner's choice: max $ in a good market (identical) or fewer "$0 half-years" (different). The sh_asia / sh_trend rows
  are paper strategies that no bot trades live; ATLAS + BLITZ uses bots that exist (BLITZ is hidden but runs on paper).
- ATLAS also trades its own 25K: with ATLAS on 2-3 Rapid accounts, the same ATLAS signal runs on 3-4 accounts.

## 4. Lever 2 - Asia slot on the Rapid EOD only

| Row | eval median | 2-wk pass/fail % | 60-session fail % | funded $/mo | slot $/mo | 1st payout from buying |
|---|---|---|---|---|---|---|
| LIT + ATLAS (base) | 22 / 21 / 29 | 5.2/0, 9.2/0, 1.1/2.9 | 1.0 / 2.3 / 68.0 | 6,269 / 2,884 / 251 | 5,022 / 2,301 / 63 | 34 / 37 / 66 |
| + Asia at LIT size (eval + funded) | 19 / 16 / 23 | 10.7/0, 21.8/0, 1.4/7.1 | 3.0 / 0.8 / 79.6 | 5,653 / 3,442 / 196 | 4,847 / 2,958 / 36 | 30 / 29 / 66 |
| + Asia $300 (eval + funded) | 20 / 19 / 27 | 7.5/0.1, 13.9/0, 1.1/4.7 | 1.7 / 0.8 / 76.5 | 6,270 / 3,745 / 233 | **5,133 / 3,035** / 42 | 31 / 32 / 63 |
| + Asia at LIT size in the eval only | 19 / 16 / 23 | 10.7/0, 21.8/0, 1.4/7.1 | 3.0 / 0.8 / 79.6 | 6,269 / 2,884 / 251 | 5,180 / 2,454 / 50 | 30 / 31 / 67 |

- As expected, the Asia slot helps the 30% rule: more winning days, the eval passes 2-5 sessions sooner, and in Jul-Oct the
  2-week pass doubles (9.2% -> 13.9-21.8%).
- At LIT size on the FUNDED account it loses accounts (funded lost in 6 months 9.4% / 2.0% / 27.3% vs 0%): rejected.
- Asia $300 and "Asia in the eval only" both pass the 2026 test, but H1 is small (+$111 / +$158 a month) and 2021-25 is
  worse (slot $42 / $50 vs $63; 2-week fails 4.7% / 7.1% vs 2.9%; 60-session fails 76-80% vs 68%). Practical blocker: the
  PC bot does not trade 18:00-02:00 today (route blocks Asia before midnight, the PC sleeps 16:35-01:30). Verdict: weak lead,
  not worth the build now; re-check after more 2026 data.

## 5. Lever 3 - Rapid EOD mechanics (one account, LIT + ATLAS)

**(a) Give up the eval and buy a fresh one ($94)**

| Rule | slot $/mo | 1st payout | P(no pay 6m) | evals bought | fees 6m |
|---|---|---|---|---|---|
| never (today; the bot already quits under $200 room) | 5,022 / 2,301 / 63 | 34 / 37 / 66 | 2.3 / 7.6 / 82.2 | 1.01 / 1.03 / 2.90 | 95 / 96 / 273 |
| room < $500 | 5,045 / 2,313 / 55 | 34 / 37 / 62 | 2.3 / 7.2 / 82.7 | 1.05 / 1.08 / 3.71 | 99 / 102 / 349 |
| room < $800 | 5,059 / 2,320 / 44 | 33 / 36 / 62 | 2.3 / 7.1 / 79.9 | 1.15 / 1.18 / 4.93 | 108 / 110 / 463 |
| room < $1,000 | 5,071 / 2,318 / 20 | 33 / 36 / 60 | 2.2 / 7.3 / 81.5 | 1.25 / 1.29 / 6.19 | 118 / 121 / 582 |
| session > 30 | 4,786 / 2,221 / 15 | 34 / 36 / 59 | 3.3 / 9.6 / 87.4 | 1.39 / 1.38 / 4.29 | 130 / 130 / 404 |
| session > 45 | 4,979 / 2,274 / 44 | 34 / 36.5 / 63 | 2.8 / 8.6 / 83.9 | 1.10 / 1.13 / 3.40 | 104 / 106 / 320 |
| 30%-rule need > $4,000 (a big day pushed the needed total too far) | 5,059 / 2,317 / 65 | 33 / 36 / 62 | 2.2 / 7.4 / 80.7 | 1.07 / 1.08 / 3.76 | 100 / 102 / 353 |
| 30%-rule need > $3,000 | 5,126 / 2,337 / -55 | 32 / 34.5 / 59 | 2.2 / 7.0 / 77.1 | 2.10 / 2.97 / 12.8 | 197 / 279 / 1,207 |

The room / need rules technically pass (+$23 to +$104 H1, +$12 to +$36 H2), but that is 0.5-2% of the money, inside
Monte Carlo noise, and 2021-25 gets worse with every room rule (more evals bought). Session limits lose. **Not adopted.**

**(b) Funded withdrawal policy (help-center rules, see section 1)**

| Policy | funded $/mo | funded 1st payout | funded no-pay 6m | funded lost 6m | slot $/mo | slot worst-10% $/mo | combined DD median |
|---|---|---|---|---|---|---|---|
| everything above $2,100, daily (today) | 6,269 / 2,884 / 251 | 6 / 10 / 7 | 2.1 / 6.8 / 64.3 | 0 / 0 / 0 | 5,022 / 2,301 / 63 | 1,595 / 268 / -78 | -1,813 / -1,816 |
| keep $500 cushion | 7,222 / 3,375 / 266 | 7 / 12 / 8 | 2.2 / 7.2 / 67.5 | 0 | 5,666 / 2,641 / 64 | 2,191 / 238 / -78 | -2,128 / -2,036 |
| **keep $1,000 cushion** | **7,735 / 3,659** / 271 | 8 / 14 / 9 | 2.2 / 7.4 / 70.6 | 0 | **6,014 / 2,824** / 63 | 2,722 / 278 / -78 | -2,405 / -2,213 |
| keep $2,000 cushion | 8,188 / 3,871 / 269 | 10 / 18 / 13 | 2.3 / 7.8 / 74.8 | 0 | 6,290 / 2,918 / 54 | 3,224 / 229 / -78 | -2,663 / -2,397 |
| weekly, everything above $2,100 | 7,119 / 3,163 / 265 | 10 / 15 / 10 | 2.2 / 7.2 / 67.9 | 0 | 5,517 / 2,479 / 62 | 2,199 / 194 / -78 | -1,998 / -1,974 |
| fixed $1,000 requests | 3,934 / 2,952 / 202 | 7 / 12 / 8 | 2.2 / 7.2 / 67.5 | 0 | 2,998 / 2,232 / 28 | 1,784 / 284 / -78 | -2,634 / -2,291 |

- Why a cushion pays more: the funded size is 60% of the room (max $1,500 a LIT trade, ATLAS 30% of the room up to $500).
  Taking everything daily keeps the room at exactly $2,000, so LIT never reaches full size. A cushion is in effect a bigger
  size bought with your own profit. The cushion still in the account after 6 months is NOT counted above (it is extra, not lost).
- Cost: the first funded payout comes 2-4 sessions later ($1,000) or 4-8 later ($2,000), deeper swings while trading, and
  in 2021-25 nothing changes. Funded accounts are never lost in this model (size shrinks with the room), so the real
  downside is the rare day the model cannot see (a gap through the stop).
- **Adopt-candidate: keep $1,000** (both halves +$992 / +$523 a month, 2021-25 equal). $2,000 makes a little more but delays
  the first payout by up to 8 sessions; the owner said speed of the first payout matters, so $1,000 is the balance.

**(c) Day-profit cap during the eval (30% best-day rule)**

| Rule | eval median | 2-wk pass/fail % | pass in 60 sessions % | slot $/mo |
|---|---|---|---|---|
| **30% size guard (today: a winner keeps the day under $855)** | 22 / 21 / 29 | 5.2/0, 9.2/0, 1.1/2.9 | 97.2 / 94.8 / 19.2 | 5,022 / 2,301 / 63 |
| none | 31 / 36 / 40 | 1.9/3.1, 1.2/1.6, 0.1/20.1 | 77.8 / 68.3 / 4.8 | 4,307 / 1,781 / -23 |
| guard + stop the day at +$500 | 22 / 21 / 29 | same | 96.7 / 94.9 / 18.9 | 4,995 / 2,302 / 58 |
| guard + stop the day at +$700 | 22 / 21 / 29 | same | 97.2 / 94.8 / 19.1 | 5,022 / 2,301 / 60 |
| stop the day at +$700, no size guard | 29 / 36 / 40.5 | 2.1/3.1, 1.2/1.6, 0.1/20.2 | 79.3 / 69.0 / 4.8 | 4,395 / 1,796 / -28 |
| balance-aware guard (allow 30/70 x balance once ahead) | 21 / 21 / 28 | 6.0/0, 9.3/0, 1.1/2.9 | 97.3 / 94.8 / 19.1 | 5,067 / 2,308 / 57 |

Today's size guard is what makes the Rapid eval work: without it the eval takes 31-36 sessions and fails 20% of the time
within 2 weeks in 2021-25. A "stop for the day" rule adds nothing on top of the guard (one big winner is what breaks the
30% rule, and the guard already sizes it). The balance-aware guard is +$45 / +$7 a month: noise. **Keep today's guard.**

## 6. Honest limits

- 2026 is an unusually good year for LIT and ATLAS; the H1 $ (~$5,000 a month for one account) is not a forecast. Use H2.
- Funded accounts are never lost in this model because every trade is sized from the room; slippage beyond 1 tick, gaps
  through stops and platform problems are not modelled.
- Trades of a day play in entry order on closed P&L; overlapping same-direction trades are not netted.
- One seed pair (7 / 23), 1,000-2,000 paths; differences under ~$50 / 2% a month are noise.
- MFFU rules are from the help center on 2026-11-16 plus third-party guides for the $500-since-last-payout rule; MFFU can
  change them. A move to a live account after a $10,000 day is not modelled (it never happens at these sizes).
- Nothing live was changed (no live_model*.json, no engine file, no bot). Any change needs the owner's yes, a lead build and a Sim test.

Sources: MFFU help center "Payout Policy Overview" (help.myfundedfutures.com/en/articles/13745661), eltraderfinanciado.com
"My Funded Futures launches Rapid EOD 50K" (Aug 2026), financemagnates.com (MFFU 30% consistency / $10,000 daily cap).
Code: `tools/money/rapid_levers.py`, results `research/lab/rapid_levers.json`.
