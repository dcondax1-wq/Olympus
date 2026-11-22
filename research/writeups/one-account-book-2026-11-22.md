---
title: One account, combined book - every mix of Zlarior (LIT) + ATLAS (+ BLITZ) on ONE MFFU account at real fills; the pre-registered best (Rapid EOD 50K, LIT + ATLAS, LIT half size in the eval) beats today's two accounts in both 2026 halves but is worse in 2021-25, so no new card
family: money
date: 2026-11-22
status: done - paper only, no Decide card (the picked book fails the "not worse 2021-25" bar). Nothing live changed.
summary: Lane E. Pre-registered (research/onebook/DESIGN.md, committed 12c9f71cc before the scored run). 13 books x 4 MFFU accounts = 52 books + today's setup = 53 counted, on research/plans/rank.py's real-fills engine (ATLAS 10 ticks a side), 1,000 paths x 126 sessions, same paths for every book. Pick on Jan-Jun among books whose eval fail is at most LIT-alone + 2 points - MFFU Rapid EOD 50K ($165), LIT + ATLAS first-come with LIT at half size in the eval - $4,918 / $2,204 / -$88 a month (Jan-Jun / Jul-Oct / 2021-25-like) vs today's two accounts (LIT on the Builder 50K + ATLAS on the Builder 25K) $981 / $857 / -$62. Paired on the same paths - +$23,623 / +$8,086 / -$156 over 6 months (SE $406 / $229 / $32), 2022 alone -$781. Without ATLAS's 5 best Jul-Oct days the Jul-Oct gain is +$114 (SE $136) = about $0. Fails the 2021-25 bar: no card. The gain is the account type (Rapid EOD 50K, already on the open card plan-rapid50k-max2-rebuys), not a new way to mix the bots.
runs: research/onebook/book.py -> results.json; research/onebook/robust.py -> robust.json (labelled post-hoc)
---

## Headline

**For one account, do this: an MFFU Rapid EOD 50K ($165). Run Zlarior (LIT) + ATLAS on it together, all day, first in keeps the
account, never two opposite positions (today's account_b rule). LIT trades at half size until the eval passes, then full size.
ATLAS runs on its $500 lane the whole time. Expected: $4,918 a month (Jan-Jun-like), $2,204 a month (Jul-Oct-like), -$88 a month
(2021-25-like). The eval passes 94% / 90% of the time (fails 1.7% / 3.9%). The first payout comes in about 8-9 weeks
(41 / 47 sessions from the buy).**

**Not a Decide card.** It beats today's setup (LIT on the Builder 50K + ATLAS on the Builder 25K, two accounts, two fees) in
both 2026 halves by a wide margin, but it is WORSE in a 2021-25-like market: -$529 vs -$374 over 6 months, a $156 gap with a
standard error of $32, so the gap is real. It is also $781 worse in 2022 alone. The pre-set rule says no card.
Most of the gain comes from the account type, not from how the bots are mixed. The Rapid EOD 50K choice is already on your
Decide page (plan-rapid50k-max2-rebuys, buy-rapid50-now). With at most 2 re-buys its worst 2021-25 case is about -$311.

## For the owner (one minute)

| What, 6 months, after every eval fee | Jan-Jun-like | **Jul-Oct-like** | 2021-25-like | 2022 alone |
|---|---:|---:|---:|---:|
| **Today: LIT on Builder 50K + ATLAS on Builder 25K (2 accounts)** | $5,884 ($981/mo) | **$5,142 ($857/mo)** | -$374 | +$535 |
| **Best one account: Rapid EOD 50K, LIT + ATLAS, LIT half size in the eval** | $29,506 ($4,918/mo) | **$13,227 ($2,204/mo)** | -$529 | -$245 |
| ... same, without ATLAS's 5 best Jul-Oct days | - | $4,476 (today $4,362) | - | - |
| Builder 50K, LIT + ATLAS, ATLAS x0.5 in the eval (best Builder book) | $6,962 | $7,007 | -$334 | -$53 |
| Builder 50K, ATLAS only from 09:30 (time split) | $6,956 | $5,604 | -$199 | +$250 |
| Eval pass / fail %: today 50K / best book | 70 / 9.9 vs **94 / 1.7** | 82 / 11 vs **90 / 3.9** | 29 / 56 vs 10 / 81 | |
| First payout (median, weeks from the buy): today 50K / best book | 10 vs **8** | 9 vs **9** | 17 vs 12 (95% never pay) | |
| $ back per $1 of eval fees: today / best book | x27.7 / **x131** | x24.9 / **x57** | x0.34 / x0.27 | |

In plain words:
- **More bots on one account does make more trades and more money, in 2026.** LIT + ATLAS gives about 5.5-7 signals a week
  instead of 2.5-3 for LIT alone. More winning days helps with the best-day rules.
- **The account type is what matters most.** The same LIT + ATLAS mix on a Builder 50K makes $1,209 / $1,228 a month. On a
  Rapid EOD 50K it makes $5,002 / $2,282 (daily payouts, 90% split, no payout cap).
- **None of the mixing tricks beats plain first-come on the same account in Jul-Oct.** Size splits, a LIT-priority budget,
  time windows and half-size ATLAS all make less: -$78 to -$1,352 a month on the Rapid 50K, -$60 to -$424 on the Builder 50K.
  Only adding BLITZ makes more, and it fails more evals and has no real-fill check yet. Half-size LIT in the eval was picked
  because it fails fewer evals (1.7% vs 2.5% Jan-Jun), not because it makes more (-$78 a month).
- **The bad-market risk is the same old one.** In a 2021-25-like market every combined book loses a bit more than today,
  because more trading on a weak edge buys more evals. The Jul-Oct gain over today mostly rests on ATLAS's 5 best days.
  This is the same finding as the 2026-11-19 red team.

Next (paper only):
1. Nothing new to decide here. The money lever is the open card **plan-rapid50k-max2-rebuys** (Rapid EOD 50K, at most 2 re-buys).
   It adds about +$2,282 a month Jul-Oct-like on top of today's two accounts. Its worst case is about -$495 (3 evals).
2. If that card is a yes, run it as this book: LIT + ATLAS together, first in keeps the account, LIT at half size until the
   eval passes. This costs about $78 a month vs full size and fails fewer evals.
3. Re-check after December with the new days: `python -X utf8 research/onebook/book.py`

## 1. What was tested (design committed before the run: research/onebook/DESIGN.md, 12c9f71cc)

- **Engine:** research/plans/rank.py, reused as it is. It reproduces rank.py's own numbers exactly (Builder 50K LIT + ATLAS
  $7,371 Jul-Oct-like, Rapid 25K $800 a month, Rapid 50K $2,282 a month). Eval: the live LIT two_week sizing, plus ATLAS's lane
  ($ = min(lane, 30% of the room, the soft day left)), plus the 30% best-day guard on Rapid evals. Funded: each plan's own
  payout rules (Builder: 50% best day, 2 days a cycle, $2,000 / $1,000 caps, 5 payouts; Rapid: daily payouts above the
  buffer with the bot's $1,000 / $500 keep, Tier-1 news flat). Stuck line, and a re-buy on any fail, dead or graduated account.
- **Fills:** ATLAS at its measured real fills (10 ticks a side). LIT as stored (1m fills in 2026). BLITZ at its stored 1-tick
  fills (no real-fill measurement exists yet).
- **Hedge ban:** ATLAS never enters opposite LIT and is closed when LIT enters opposite (account_b). BLITZ never trades
  opposite LIT or ATLAS. There is one shared soft daily loss for all bots on the account.
- **Paths:** 1,000 x 126 sessions (6 months) and 1,000 x 60 (eval), in 5-session blocks. H1 = 2026 Jan-Jun (pick),
  H2 = Jul-Oct (check), REF = 2021-11..2025 (check). Every book runs on the same paths.
- **Books, 13 per account (52) + today's setup = 53 counted:** B01 LIT only, B02 ATLAS only, B03 LIT + ATLAS first-come,
  B04 LIT-priority budget (ATLAS may use at most 50% of the soft day), B05 ATLAS only from 09:30 ET, B06 ATLAS only before
  09:30, B07 strict windows (LIT before 09:30, ATLAS from 09:30), B08 ATLAS x0.5 in the eval, B09 LIT alone in the eval then
  LIT + ATLAS funded (the approved card atlas-on-50k-funded), B10 LIT x0.75 everywhere, B11 LIT x0.5 in the eval,
  B12 + BLITZ $300, B13 ATLAS lane x2.
- **Not re-run:** the MES filler (rejected 2026-11-19: -$66 a month 2021-25, worse Jan-Jun) and ES-LIT (rejected 2026-11-13).
  ES has no bars before 2025-04, so the 2021-25 check is impossible for any ES book.
- **Pick rule (fixed in advance):** eligible = H1 eval fail % <= that account's LIT-alone fail + 2 points. Best = the highest H1
  6-month net among eligible books on all 4 accounts. Card only if it beats today in H1 and H2 AND is not worse in 2021-25
  (one account vs today's two, fees in).
- **Lanes A-D:** see section 5.

## 2. Pick (research/onebook/results.json "pick")

35 of 52 books were eligible. Top 5 on Jan-Jun: Rapid 50K B11 $29,506, B10 $26,861, B08 $26,783, B02 $16,109, then the
Rapid 50K B09 / Rapid 25K books. Picked: **Rapid EOD 50K, B11**. Check: H1 beats today yes, H2 yes, 2021-25 not worse **NO**
(-$529 vs -$374). Verdict: **no card**.

The highest-dollar books were excluded by the eval-fail bar: BLITZ added (B12) and plain first-come (B03) on the Rapid 50K
fail 3.6% / 2.5% of evals in Jan-Jun vs 0.3% for LIT alone. B12 also needs BLITZ's real fills first (BLITZ is paper, hidden).

## 3. Paired check vs today (research/onebook/robust.json; labelled post-hoc, same paths, 6-month net $, diff +- SE, % of paths worse)

| Book | Jan-Jun | Jul-Oct | 2021-25 | 2022 | Jul-Oct without ATLAS's 5 best days |
|---|---|---|---|---|---|
| Rapid 50K B11 (the pick) | +$23,623 +-406 (3% worse) | +$8,086 +-229 (17%) | **-$156 +-32 (80%)** | **-$781 +-62** | +$114 +-136 |
| Rapid 50K B03 first-come | +$24,127 +-409 | +$8,549 +-225 | -$186 +-36 | -$687 +-67 | +$736 +-135 |
| Rapid 50K B09 LIT eval, both funded | +$9,862 +-414 | +$3,933 +-205 | +$178 +-26 | -$357 +-58 | **-$571 +-117** |
| Builder 50K B08 ATLAS x0.5 eval | +$1,079 +-92 | +$1,866 +-61 | +$40 +-21 | -$589 +-41 | -$78 +-62 |
| Builder 50K B05 ATLAS from 09:30 | +$1,072 +-100 | +$462 +-55 | +$175 +-21 | -$286 +-40 | +$1,242 +-56 |
| Builder 50K B09 (= approved atlas-on-50k-funded) | -$526 +-77 | +$1,353 +-64 | +$170 +-20 | -$520 +-40 | -$88 +-56 |
| Builder 50K B03 first-come | +$1,370 +-93 | +$2,230 +-65 | -$201 +-24 | -$786 +-43 | -$63 +-66 |

ATLAS's 5 best Jul-Oct days (by R): Jul 15, Jul 24, Aug 4, Aug 7, Oct 2. These are the same 5 days the 2026-11-19 red team found. Today's setup loses them too (ATLAS on the 25K).

Reading: three books beat today in all three periods (Rapid 50K B09, Builder 50K B08 and B05). They were found
by looking at the results after the run, out of 53 books, so they are leads, not picks. Every one of them is worse than today
in 2022 alone. Only Builder B05 (ATLAS NY members only) keeps its Jul-Oct edge without ATLAS's 5 best days. That is because
those days are London EMA days, which B05 does not trade. On one account it gives one account $1,159 / $934 / -$33 a month
vs today's two accounts $981 / $857 / -$62, with eval fail 4.7 / 13.5% vs 9.9 / 11.1%. Paper lead only.

## 4. Every book (6-month slot, $ a month after fees; H1 / H2 / 2021-25)

| Account | Book | $/mo H1 / H2 / 2021-25 | eval pass / fail % H1, H2 (median sessions) | 1st payout (sessions) H1 / H2 | owner $ per $1 fees H1 / H2 / REF | eligible |
|---|---|---|---|---|---|---|
| Builder 50K $91.80 | B01 LIT only | $634 / $744 / $-18 | 70.0/9.9 (9), 82.3/11.1 (8) | 49 / 46 | x30.06 / x34.15 / x0.58 | yes |
| Builder 50K $91.80 | B02 ATLAS only | $854 / $420 / $-82 | 84.2/12.0 (11), 73.9/10.4 (18) | 44 / 62 | x34.61 / x20.25 / x0.18 | no |
| Builder 50K $91.80 | B03 LIT + ATLAS first-come | $1,209 / $1,228 / $-96 | 83.8/16.2 (7), 84.6/14.6 (7) | 33 / 33 | x37.92 / x38.71 / x0.25 | no |
| Builder 50K $91.80 | B04 LIT priority budget (ATLAS <= 50% of the day) | $1,016 / $957 / $-91 | 83.1/16.6 (7), 82.8/16.2 (8) | 37 / 40 | x36.39 / x35.03 / x0.25 | no |
| Builder 50K $91.80 | B05 time split: ATLAS NY only (from 09:30) | $1,159 / $934 / $-33 | 93.5/4.7 (10), 84.2/13.5 (9) | 37 / 43 | x46.02 / x34.47 / x0.49 | yes |
| Builder 50K $91.80 | B06 time split: ATLAS London only (before 09:30) | $976 / $1,068 / $-84 | 78.6/20.8 (7), 88.6/10.7 (8) | 38 / 38 | x31.89 / x40.45 / x0.24 | no |
| Builder 50K $91.80 | B07 strict windows: LIT before 09:30, ATLAS from 09:30 | $1,108 / $804 / $-32 | 90.9/7.3 (10), 80.1/15.8 (9) | 39 / 47 | x44.29 / x29.86 / x0.49 | yes |
| Builder 50K $91.80 | B08 ATLAS x0.5 in the eval, full funded | $1,160 / $1,168 / $-56 | 87.6/11.1 (8), 86.8/11.4 (9) | 36 / 36 | x40.03 / x39.02 / x0.27 | yes |
| Builder 50K $91.80 | B09 LIT eval, LIT + ATLAS once funded | $893 / $1,082 / $-34 | 70.0/9.9 (9), 82.3/11.1 (8) | 37 / 37 | x34.62 / x36.62 / x0.37 | yes |
| Builder 50K $91.80 | B10 size split: LIT x0.75 eval + funded | $1,130 / $994 / $-86 | 89.9/9.5 (9), 85.4/11.1 (12) | 37 / 42 | x41.52 / x38.09 / x0.22 | yes |
| Builder 50K $91.80 | B11 size split: LIT x0.5 in the eval | $1,149 / $1,083 / $-85 | 90.0/9.0 (10), 86.4/8.7 (14) | 36 / 40 | x40.04 / x38.7 / x0.22 | yes |
| Builder 50K $91.80 | B12 LIT + ATLAS + BLITZ $300 | $1,372 / $1,488 / $-101 | 83.2/16.8 (5), 86.8/13.0 (6) | 29 / 28 | x38.44 / x44.12 / x0.29 | no |
| Builder 50K $91.80 | B13 LIT + ATLAS, ATLAS lane x2 | $946 / $833 / $-109 | 81.9/18.1 (6), 83.1/15.8 (7) | 38 / 38 | x34.34 / x34.12 / x0.18 | no |
| Builder 25K $63 | B01 LIT only | $310 / $302 / $-17 | 75.4/2.6 (9), 80.2/1.7 (8) | 48 / 49 | x22.94 / x21.0 / x0.29 | yes |
| Builder 25K $63 | B02 ATLAS only | $346 / $113 / $-44 | 81.1/4.2 (11), 60.1/4.8 (20) | 43 / 64 | x24.18 / x9.4 / x0.14 | yes |
| Builder 25K $63 | B03 LIT + ATLAS first-come | $548 / $484 / $-54 | 87.7/6.6 (7), 83.2/9.7 (8) | 36 / 37 | x28.51 / x24.97 / x0.17 | no |
| Builder 25K $63 | B04 LIT priority budget (ATLAS <= 50% of the day) | $451 / $364 / $-52 | 86.9/6.4 (8), 79.6/10.5 (10) | 40 / 43 | x25.81 / x21.3 / x0.16 | no |
| Builder 25K $63 | B05 time split: ATLAS NY only (from 09:30) | $526 / $366 / $-22 | 91.1/1.7 (10), 80.8/2.4 (9) | 39 / 45 | x31.68 / x22.26 / x0.3 | yes |
| Builder 25K $63 | B06 time split: ATLAS London only (before 09:30) | $449 / $445 / $-50 | 83.9/8.2 (8), 83.7/8.5 (9) | 40 / 41 | x25.48 / x26.24 / x0.14 | no |
| Builder 25K $63 | B07 strict windows: LIT before 09:30, ATLAS from 09:30 | $500 / $288 / $-22 | 88.2/2.1 (9), 78.5/2.4 (9) | 40 / 51 | x30.66 / x18.05 / x0.28 | yes |
| Builder 25K $63 | B08 ATLAS x0.5 in the eval, full funded | $533 / $440 / $-28 | 89.7/1.6 (9), 83.5/1.6 (11) | 36 / 39 | x28.96 / x24.92 / x0.16 | yes |
| Builder 25K $63 | B09 LIT eval, LIT + ATLAS once funded | $446 / $423 / $-20 | 75.4/2.6 (9), 80.2/1.7 (8) | 36 / 38 | x25.99 / x24.15 / x0.28 | yes |
| Builder 25K $63 | B10 size split: LIT x0.75 eval + funded | $492 / $258 / $-46 | 87.6/4.6 (10), 75.0/5.0 (13) | 37 / 46 | x30.65 / x18.42 / x0.14 | yes |
| Builder 25K $63 | B11 size split: LIT x0.5 in the eval | $521 / $384 / $-46 | 87.4/3.7 (10), 73.4/5.0 (16) | 36 / 42 | x28.26 / x22.31 / x0.16 | yes |
| Builder 25K $63 | B12 LIT + ATLAS + BLITZ $300 | $670 / $554 / $-58 | 86.6/7.5 (5), 82.9/8.8 (7) | 31 / 34 | x29.4 / x26.13 / x0.18 | no |
| Builder 25K $63 | B13 LIT + ATLAS, ATLAS lane x2 | $436 / $350 / $-58 | 87.0/7.1 (7), 81.1/10.0 (7) | 39 / 39 | x25.72 / x21.39 / x0.13 | no |
| Rapid EOD 25K $97.20 | B01 LIT only | $221 / $191 / $-22 | 25.4/0.0 (42), 41.1/0.0 (42) | 92 / 91 | x13.92 / x11.28 / x0.04 | yes |
| Rapid EOD 25K $97.20 | B02 ATLAS only | $707 / $141 / $-47 | 50.7/0.3 (42), 65.6/0.4 (35) | 77 / 76 | x41.33 / x8.76 / x0.05 | yes |
| Rapid EOD 25K $97.20 | B03 LIT + ATLAS first-come | $1,884 / $800 / $-50 | 79.3/0.3 (33), 85.5/2.4 (26) | 53 / 56 | x90.02 / x34.35 / x0.18 | yes |
| Rapid EOD 25K $97.20 | B04 LIT priority budget (ATLAS <= 50% of the day) | $1,544 / $577 / $-48 | 77.3/0.3 (34), 85.5/2.4 (26) | 56 / 61 | x72.81 / x24.5 / x0.17 | yes |
| Rapid EOD 25K $97.20 | B05 time split: ATLAS NY only (from 09:30) | $872 / $347 / $-32 | 77.4/0.1 (34), 62.2/0.4 (34) | 67 / 74 | x52.56 / x17.57 / x0.12 | yes |
| Rapid EOD 25K $97.20 | B06 time split: ATLAS London only (before 09:30) | $874 / $668 / $-36 | 36.5/1.0 (41), 82.8/0.0 (33) | 75 / 67 | x42.81 / x32.58 / x0.14 | yes |
| Rapid EOD 25K $97.20 | B07 strict windows: LIT before 09:30, ATLAS from 09:30 | $822 / $265 / $-31 | 76.5/0.1 (35), 62.2/0.4 (34) | 68 / 77 | x48.98 / x13.38 / x0.13 | yes |
| Rapid EOD 25K $97.20 | B08 ATLAS x0.5 in the eval, full funded | $1,548 / $683 / $-33 | 61.8/0.1 (37), 75.9/0.0 (33) | 62 / 64 | x77.46 / x31.19 / x0.08 | yes |
| Rapid EOD 25K $97.20 | B09 LIT eval, LIT + ATLAS once funded | $806 / $415 / $-22 | 25.4/0.0 (42), 41.1/0.0 (42) | 84 / 78 | x44.81 / x21.16 / x0.08 | yes |
| Rapid EOD 25K $97.20 | B10 size split: LIT x0.75 eval + funded | $1,434 / $431 / $-47 | 75.4/0.5 (36), 82.1/0.5 (27) | 59 / 62 | x85.49 / x24.66 / x0.14 | yes |
| Rapid EOD 25K $97.20 | B11 size split: LIT x0.5 in the eval | $1,756 / $763 / $-46 | 75.3/0.5 (36), 82.3/0.5 (27) | 57 / 57 | x84.59 / x33.81 / x0.17 | yes |
| Rapid EOD 25K $97.20 | B12 LIT + ATLAS + BLITZ $300 | $2,541 / $1,448 / $-58 | 83.2/3.5 (25), 93.1/2.0 (19) | 44 / 46 | x110.31 / x57.18 / x0.23 | no |
| Rapid EOD 25K $97.20 | B13 LIT + ATLAS, ATLAS lane x2 | $2,208 / $717 / $-47 | 79.3/0.3 (33), 85.5/2.4 (26) | 53 / 57 | x92.44 / x28.27 / x0.24 | yes |
| Rapid EOD 50K $165 | B01 LIT only | $795 / $787 / $-39 | 44.5/0.3 (41), 64.0/0.8 (38) | 80 / 75 | x27.77 / x25.92 / x0.09 | yes |
| Rapid EOD 50K $165 | B02 ATLAS only | $2,685 / $546 / $-90 | 87.7/2.1 (30), 71.7/3.3 (33) | 53 / 68 | x80.83 / x16.17 / x0.15 | yes |
| Rapid EOD 50K $165 | B03 LIT + ATLAS first-come | $5,002 / $2,282 / $-93 | 94.3/2.5 (24), 92.1/4.6 (22) | 39 / 46 | x130.82 / x58.22 / x0.29 | no |
| Rapid EOD 50K $165 | B04 LIT priority budget (ATLAS <= 50% of the day) | $4,369 / $1,647 / $-92 | 93.3/2.6 (25), 90.8/5.1 (23) | 42 / 52 | x117.31 / x41.31 / x0.27 | no |
| Rapid EOD 50K $165 | B05 time split: ATLAS NY only (from 09:30) | $2,317 / $1,192 / $-69 | 90.4/0.0 (28), 78.2/7.2 (29) | 54 / 61 | x82.81 / x33.12 / x0.18 | yes |
| Rapid EOD 50K $165 | B06 time split: ATLAS London only (before 09:30) | $3,058 / $1,897 / $-72 | 68.6/6.5 (32), 91.1/1.1 (29) | 57 / 56 | x72.92 / x57.68 / x0.19 | no |
| Rapid EOD 50K $165 | B07 strict windows: LIT before 09:30, ATLAS from 09:30 | $2,215 / $930 / $-66 | 89.1/0.1 (28), 73.8/8.0 (30) | 55 / 64 | x78.68 / x24.88 / x0.18 | yes |
| Rapid EOD 50K $165 | B08 ATLAS x0.5 in the eval, full funded | $4,464 / $2,055 / $-70 | 87.9/1.2 (29), 88.6/2.2 (28) | 46 / 53 | x121.33 / x55.27 / x0.22 | yes |
| Rapid EOD 50K $165 | B09 LIT eval, LIT + ATLAS once funded | $2,624 / $1,512 / $-33 | 44.5/0.3 (41), 64.0/0.8 (38) | 70 / 66 | x78.84 / x43.05 / x0.27 | yes |
| Rapid EOD 50K $165 | B10 size split: LIT x0.75 eval + funded | $4,477 / $1,728 / $-93 | 94.0/1.6 (25), 89.6/4.7 (24) | 42 / 49 | x138.15 / x50.04 / x0.25 | yes |
| Rapid EOD 50K $165 | B11 size split: LIT x0.5 in the eval | $4,918 / $2,204 / $-88 | 93.9/1.7 (25), 89.7/3.9 (24) | 41 / 47 | x131.43 / x57.06 / x0.27 | yes |
| Rapid EOD 50K $165 | B12 LIT + ATLAS + BLITZ $300 | $6,102 / $3,389 / $-96 | 95.8/3.6 (18), 94.3/4.0 (18) | 32 / 37 | x148.73 / x88.84 / x0.42 | no |
| Rapid EOD 50K $165 | B13 LIT + ATLAS, ATLAS lane x2 | $5,737 / $1,871 / $-80 | 94.3/2.5 (24), 92.1/4.6 (22) | 40 / 47 | x134.39 / x44.81 / x0.39 | no |

Fixed $ view (each strategy's signals at a fixed $ a trade, no account rules, costs in; ATLAS at 10 ticks a side). The size
knobs (B08-B11) use the same signals as B03, so only the books that change which signals trade are listed:

| Book (fixed $ view, every signal, no account rules) | signals/wk H1 / H2 / REF | PF H1 / H2 / REF | net $ over the span H1 / H2 / REF | max DD $ H1 / H2 / REF |
|---|---|---|---|---|
| B01 LIT only ($500 a trade) | 3.12 / 2.56 / 2.37 | 3.49 / 2.71 / 1.02 | $31,246 / $13,767 / $1,961 | $-3,271 / $-2,228 / $-19,725 |
| B02 ATLAS only ($500 a trade) | 4.06 / 2.95 / 4.61 | 2.4 / 2.25 / 0.83 | $36,332 / $11,512 / $-58,715 | $-2,583 / $-2,644 / $-79,036 |
| B03 LIT + ATLAS first-come ($500 a trade) | 7.19 / 5.51 / 6.99 | 2.76 / 2.47 / 0.87 | $67,578 / $25,279 / $-56,754 | $-3,262 / $-2,759 / $-88,481 |
| B05 time split: ATLAS NY only (from 09:30) ($500 a trade) | 4.3 / 3.65 / 3.88 | 3.17 / 2.38 / 0.95 | $39,972 / $16,013 / $-10,839 | $-2,023 / $-2,940 / $-30,007 |
| B06 time split: ATLAS London only (before 09:30) ($500 a trade) | 6.02 / 4.42 / 5.48 | 2.8 / 2.68 / 0.87 | $58,851 / $23,034 / $-43,953 | $-4,885 / $-2,179 / $-75,272 |
| B07 strict windows: LIT before 09:30, ATLAS from 09:30 ($500 a trade) | 4.06 / 3.4 / 3.43 | 3.17 / 2.19 / 0.94 | $38,553 / $13,767 / $-10,988 | $-2,023 / $-2,940 / $-28,027 |
| B12 LIT + ATLAS + BLITZ $300 ($500 a trade) | 15.66 / 12.31 / 15.53 | 2.41 / 2.33 / 0.92 | $75,048 / $30,559 / $-50,511 | $-3,193 / $-2,846 / $-85,528 |
| B13 LIT + ATLAS, ATLAS lane x2 ($500 a trade) | 7.19 / 5.51 / 6.99 | 2.62 / 2.35 / 0.86 | $107,035 / $36,703 / $-115,084 | $-5,799 / $-4,356 / $-169,544 |
| B01 LIT only ($250 a trade) | 3.12 / 2.56 / 2.37 | 3.71 / 3.0 / 1.02 | $14,406 / $6,615 / $908 | $-1,353 / $-902 / $-9,113 |
| B02 ATLAS only ($250 a trade) | 4.06 / 2.95 / 4.61 | 2.39 / 2.07 / 0.82 | $15,932 / $4,351 / $-28,208 | $-1,214 / $-1,177 / $-37,122 |
| B03 LIT + ATLAS first-come ($250 a trade) | 7.19 / 5.51 / 6.99 | 2.81 / 2.48 / 0.87 | $30,337 / $10,966 / $-27,300 | $-1,397 / $-1,160 / $-41,028 |
| B05 time split: ATLAS NY only (from 09:30) ($250 a trade) | 4.3 / 3.65 / 3.88 | 3.34 / 2.52 / 0.94 | $18,068 / $7,272 / $-5,738 | $-908 / $-1,086 / $-13,722 |
| B06 time split: ATLAS London only (before 09:30) ($250 a trade) | 6.02 / 4.42 / 5.48 | 2.86 / 2.74 / 0.87 | $26,675 / $10,309 / $-20,654 | $-2,235 / $-999 / $-34,876 |
| B07 strict windows: LIT before 09:30, ATLAS from 09:30 ($250 a trade) | 4.06 / 3.4 / 3.43 | 3.3 / 2.32 / 0.94 | $17,255 / $6,328 / $-5,529 | $-908 / $-1,086 / $-13,070 |
| B12 LIT + ATLAS + BLITZ $300 ($250 a trade) | 15.66 / 12.31 / 15.53 | 2.19 / 2.24 / 0.94 | $37,808 / $16,246 / $-21,057 | $-1,756 / $-1,209 / $-39,397 |
| B13 LIT + ATLAS, ATLAS lane x2 ($250 a trade) | 7.19 / 5.51 / 6.99 | 2.63 / 2.45 / 0.85 | $50,737 / $18,127 / $-57,807 | $-2,805 / $-2,000 / $-82,497 |


## 5. Lanes A-D (fetched 2026-11-22 ~02:00 ET, re-checked 06:30 ET)

- A edge-a-session (NQ RTH session structure, 14 variants): 0 passed. Its closest cell (ORB-30) is rejected.
- B edge-b-cross (gamma switch, vol term structure, ES/NQ strength): no winner.
- C edge-c-calendar (calendar / money-flow timing, 174 variants): 0 passed. Its closest cell (Monday long) is rejected.
- D edge-d-meta (meta-labelled size + re-entry on LIT; re-checked 06:30 ET, d6dabedb8): all rejected.
No candidate passed both 2026 halves in any lane, so no lane book was added (0 extra books). The headline stands.

## 6. Limits (honest)

- **Two accounts vs one.** "Today" is two accounts and two fees. The pick is one account. Per account slot, today's 50K
  alone makes $634 / $744 / -$18 a month.
- **Rapid EOD 50K price** is the $165 CLUB price used by rank.py (no owner purchase yet). MFFU's Rapid has no payout cap. At
  $10,000 net in one session, or a Risk-team pick, MFFU moves you to live and every sim account goes dormant (not modelled
  as a stop, same as rank.py).
- **Funded accounts are lost often on the Rapid 50K** (31-34% within 6 months, re-bought), vs 9% for LIT alone on the Builder
  50K. That cost is inside the $ (re-buy fees), but it means more resets.
- Trades of one day are played in entry order. Two overlapping same-direction trades (LIT + ATLAS) are not netted. The
  account_b rule blocks opposite ones.
- 53 books were tried. A win in one or two of them is expected by chance, so only the pre-registered pick counts.
