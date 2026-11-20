---
title: Kalshi K8 for a $55 account, ready by Monday 6 PM (sizing, better-edge tests, dry run, phone pages)
family: kalshi
date: 2026-11-20
status: $55 rule built and armed-ready (research/lab/kalshi_clock.json); 84 edge ideas tested, none passed; executor dry run on the real Nov 16-19 windows matches to the cent; live only when the owner types the phrase
---

# Kalshi K8 for $55 (night-kalshi8, 2026-11-20)

## Owner summary (plain words, $ first)

**Your $55 plan.** $2.50 a bet (4 contracts at about 52c, 5 when it is 50c or less), only the 3 live legs:
gold DOWN 05:15-05:30 ET, gold UP and silver UP 16:45-17:00 ET. At most 3 bets a day.

| Stop (checked before EVERY order, with every open bet counted as lost) | $ | Share of $55 |
|---|---|---|
| A day | -$8.00 | 15% |
| **A week (Mon-Fri)** | **-$13.75** | **25%: a bad week cannot lose more** |
| From the best point (then OFF until Claude and you look) | -$19.25 | 35% |
| Win rate | OFF under 58% won after 60 bets | |
| Price creep (others copying) | OFF if the last 30 bets paid over 58c on average | |

**What it should make (4 weeks = 20 weekdays, 20,000 runs on the real days, fees exact):**

| If the next weeks look like... | $ a week | After 4 weeks: average (bad 1-in-20) | Chance of being down after 4 weeks | Chance it switches itself OFF |
|---|---|---|---|---|
| Aug-Nov (the friend's months) | **+$12.86** | +$51 (+$16) | 2% | 5% |
| half that edge | +$5.95 | +$24 (-$14) | 16% | 21% |
| edge gone (Kalshi prices the clock) | about $0 | +$1 (-$18) | 55% | 56% |

In every case no week can lose more than $13.75 and the whole account cannot fall more than $19.25 from its best point.
$15 a bet (the old setting) cannot even place one bet with $55: one bet alone could break the week stop.

**Better edge: I tested 84 ideas the honest way. None of them makes more money.** Earlier entry (+10 s) pays MORE, later
(+40 s) pays more and misses 1 fill in 5, so +20 s stays. Price caps and "skip the day when..." filters all throw away bets that
were winning (every skipped group made money). Pausing a leg after 2 losses would have skipped bets that won 19 of 22. The roll-day
natural gas ticket now costs 93c (about $2 a month). What DID get better for you: the size and stops above (a bad week is now capped
by code), the exact fee math (4 contracts pay 1.75c fee each, 1-3 contracts pay 2c), and the bot itself (below).

**Warning, plainly.** The newest 4 days were the worst of the whole sample: the 3 live legs won 4 of 12 (Nov 16-19), -$9.12 at
$2.50. Silver 17:00 lost 4 in a row, gold 17:00 3 of 4. Over the last 4 weeks the 3 legs still won 47 of 63 (+42% per $1), and
over Aug 3-Nov 19 170 of 233 (+38%). One bad week cannot tell bad luck from the end of the edge; the stops above are there for
exactly that.

**Ready by Monday.** The bot was replayed on the real Nov 16-19 windows (prices from Kalshi's public trade list at +20 s, results
from Kalshi): every bet on the right side, 4-6 contracts within $2.50, the price the study expects (0c gap on 12 of 12 live bets),
Kalshi's result, the exact fee and the right $. Thanksgiving week: Thu 26 and Fri 27 only the 05:15 gold bet (London is open; the
CME closes early in the US, so the evening legs skip).

## Your Monday steps (only you can do these; never paste the key in a chat)

1. On kalshi.com: Account > Profile Settings > API Keys > Create New API Key. Keep the page open (Key ID + the private key).
2. On your phone open your PC link with **:8444/kalshi-live/** at the end (the same link as ZEUS Safety; the link without :8444
   is your old Jarvis app). Paste the Key ID and the key, tap Save: it must say "Key OK · balance $55.00".
3. Pick **$2.50** (marked "the rule"), type `I ACCEPT KALSHI LIVE RISK`, tap Start LIVE. Before 4:44 PM ET Monday = Monday's
   16:45 bets; after 6 PM = the first bet is Tuesday 5:15 AM ET. STOP on that page turns it off at once.

## 1. The bankroll rule (engine/kalshi_clock.bankroll_rule, research/kalshi_k8_monday/size55.py)

- Kelly for one binary bet: f* = (q - c) / (1 - c) of the bankroll, c = price + fee per contract. On Aug 3-Nov 19 the 3 live legs
  (233 bets at $2.50, +20 s price) won q = 73.0% at c = 51.65c + 1.76c = 53.4c: full Kelly 42%. That is the friend's own history,
  so the plan uses q = 63% (10 points lower): full Kelly 20.5%, a quarter = 5.1%. Gold and silver at 16:45 win or lose together
  (rho 0.59, red team), so the rule bets a bit under that: **4.5% of the bankroll a bet, rounded to $0.50, at least $1**.
  $55 -> $2.50; $20 -> $1; $100 -> $4.50; never above $15.
- Smallest sane bet: 1 contract = 50-58c + a 2c fee (52-60c). 4 contracts pay a 7c fee (1.75c each), 5 pay 9c (1.8c).
- The stops are shares of the bankroll: day 15%, week 25%, drawdown 35%. The week and drawdown stops are worst-case gates in
  check_order (settled $ + every open bet + this bet), so they hold even when two evening bets are open at once. When not even one
  bet fits under the drawdown stop, live turns OFF with one push (paper keeps recording).
- Why 35% and not 30% for the drawdown: at 30% the bot switched itself off in 11% of 4-week runs even with the edge intact, at 35%
  in 5%. 40% would add little (2%) and risk $3 more.

| $55 account, 4 weeks | $ a week (as tested / half / gone) | Down after 4 weeks | OFF by a stop |
|---|---|---|---|
| $1 a bet | +$4.23 / +$2.13 / +$0.14 | 0.5% / 9% / 46% | 1% / 8% / 26% |
| **$2.50 a bet (the rule)** | **+$12.86 / +$5.95 / +$0.25** | **2% / 16% / 55%** | **5% / 21% / 56%** |
| $5 a bet | +$13.35 / +$4.67 / +$0.09 | 18% / 37% / 62% | 66% / 83% / 94% |
| $15 a bet | no bet fits the $13.75 week stop | | |

Without the week stop the $2.50 rule makes the same money (+$12.93 a week) but 0.4-1.7% of weeks lose more than 25%; with it, none.
The real Aug 3-Nov 19 record at $2.50: +$207.65 on 233 bets, worst week -$9.12 (Nov 16), deepest dip -$12.55.

## 2. Better edge: 84 ideas, the kalshi_adapt bar (research/kalshi_k8_monday/edge.py -> edge.json)

Found on Aug 3-Oct 21, read once on the held-out Oct 22-Nov 19; one-sided Bonferroni for 84 tries (t >= 3.24, verify.py); $2.50
bets at the +20 s tape price, verify.py fees. A filter passes only if the bets it SKIPS lose money (t <= -3.24) and lose again held out.

| Idea (variants) | Result | Verdict |
|---|---|---|
| Entry +10 s / +40 s instead of +20 s (2) | +10 s pays 0.15c (find) / 0.53c (held out) more: -2.3% / -3.0% per $1. +40 s pays 0.84c more and fills only 81% | rejected: +20 s stays |
| Max price per leg 50 / 53 / 55 / 57 / 60c (30) | the skipped dearer bets made +19% to +53% per $1 (only gold 16:15 above 60c lost, 8 bets) | rejected |
| Previous quarter hour, 4-hour move, the session before (00:00 / 09:30 ET -> open), 8-hour volatility vs its 20-day median; skip either side (48) | all 48 skipped groups made money (+6% to +76% per $1); best t 0.31 | rejected |
| Pause a leg after 2 / 3 losses in a row (2; added after the dry run) | the next bet won 19 of 22 (+70%) / 3 of 3; held out 10 of 15 | rejected |
| Roll day: natural gas UP 17:00-17:15 (1) | 15 of 15 won, but 93c now: +7% held out; loss bound 39% vs break-even 15% | rejected (about $2 a month) |
| Roll day: WTI DOWN 17:00-17:15 (1) | 17 of 20, +43% / +50% per $1, t 2.41 | rejected (too few; about $6 a month) |
| CME holidays / early closes | not testable (Labor Day only: the evening legs won) | kept as a safety skip |

Per leg at $2.50, find / held out per $1: gold 05:30 +36% / +64%, gold 17:00 +30% / +40%, silver 17:00 +45% / +20%,
silver 05:30 +36% / +10%, silver 16:15 +43% / +32%, gold 16:15 +29% / +10%. All 6 legs pooled: +36% (t 6.0) / +30% (t 2.7).
Nothing passed, so nothing new is live or paper, and there is no Decide card. Everything is in docs/TESTED_AND_REJECTED.md.

## 3. The dry run (research/kalshi_k8_monday/dryrun.py -> dryrun.json)

The real executor (engine/kalshi_clock.ClockLoop) on a fake clock and the test suite's fake Kalshi. At each read (+20 / +30 / +40 s)
the book is rebuilt from Kalshi's PUBLIC trade list (what takers of our side really paid in the next 5 s, never a later cheaper
print); Kalshi's real result settles it. Paper (not armed) and live (armed by the test with a fake key; no network, no real order).

| Day | gold DOWN 05:15 | gold UP 16:45 | silver UP 16:45 | Day |
|---|---|---|---|---|
| Mon Nov 16 | 6 at 41c, WON +$3.43 | 5 at 50c, lost -$2.59 | 5 at 43c, lost -$2.24 | -$1.40 |
| Tue Nov 17 | 4 at 58c, lost -$2.39 | 6 at 41c, lost -$2.57 | 5 at 42c, lost -$2.19 | -$7.15 (day stop -$8 not hit) |
| Wed Nov 18 | 4 at 58c, WON +$1.61 | 5 at 50c, WON +$2.41 | 5 at 49c, lost -$2.54 | +$1.48 |
| Thu Nov 19 | 5 at 50c, WON +$2.41 | 4 at 53c, lost -$2.19 | 4 at 55c, lost -$2.27 | -$2.05 |

Live: 12 orders, all on the right side (DOWN = sell YES at 1 - price, UP = buy YES), whole contracts within $2.50, expiring 40 s
after the open, results = Kalshi's, fee = verify.py's, $ = contracts x $1 - cost - fee: **-$9.12 on 4 of 12**. Paper (5 legs):
-$6.21 on 9 of 20. The live price equals the study's +20 s price on 12 of 12 (paper: 19 of 20, one +3c).

## 4. Calendar and the PC

| Day | Bets |
|---|---|
| Mon Nov 23, Tue 24, Wed 25 | 05:15 gold DOWN; 16:45 gold UP + silver UP (paper also: silver 05:15, silver 16:00) |
| Thu Nov 26 (Thanksgiving) | 05:15 gold DOWN only (London auction runs; the CME closes early, evening skipped) |
| Fri Nov 27 | 05:15 gold DOWN only (CME early close) |

- Tickers checked: KXGOLD15M-26NOV230530-30, KXGOLD15M-26NOV231700-00, KXSILVER15M-26NOV231700-00 ... Kalshi listed these markets on
  Labor Day too; if a holiday market is missing, the bot logs it and moves on.
- The PC keeps the loop alive every 15 minutes (tools/pc_report.py -> engine.kalshi_live.maybe_run -> kalshi_clock.maybe_run).
- **Found and fixed: the phone never saw K8.** The PC's public card came only from the idle maker executor's card.json, so with
  no maker loop it said "off" and the 15-minute report dropped it. Now read_card builds the K8 block itself (st "paper" while not
  armed): the Kalshi page's K8 status card fills after the PC updates. Whether the PC recorded paper bets on Nov 19 cannot be
  seen from here until then (`python -X utf8 -m engine.kalshi_live --clock-report` on the PC shows it).
- The phone page is on the bot server's own port: `https://<pc>.<tailnet>.ts.net:8444/kalshi-live/` (engine/phone_link.py; :443
  belongs to the old Jarvis app). The page, the help card, the push texts and the docs now say :8444.

## 5. Quality

- **K8 status card** on both phone pages: LIVE / PAPER, bankroll, bet size, today's bets, a next-window countdown, the last 10
  results (W / L), and how far each stop is (today, this week, from the peak, win rate, average price).
  Screenshots (390 x 844, fed by the Nov 16-19 replay): research/handoff/2026-11-20/kalshi8/kalshi-live.png, kalshi-page.png.
- The phone page's bet sizes: $1 / $2.50 (marked "the rule") / $5; the warning uses the bankroll rule ("use $2.50 a bet").
- `--clock-report` now prints how far each stop is and one map of the Kalshi files on the PC (data/kalshi_live/: clock_* = K8,
  adapt* = the weekly re-test, arm / KILL / log / card = the executor; data/kalshi_rewards/ and data/kalshi_k1/ = the older paper
  tests; the key never in data/). clock_loop.log rotates at 1 MB.
- Fixed on the way: after a live stop inside a window, the other legs' PAPER rows of that window were lost (now kept); the
  weekly re-test's public client counted Kalshi's 429 "slow down" as a broken network and gave up after 6 (now it waits).

## 6. Files and reruns (research/kalshi_k8_monday/)

| File | What |
|---|---|
| `k8m_data.py` | loads the K8 tape cache + tonight's fresh tape (data/tape_fresh.jsonl, Nov 16-19, public GET, 1 a second), the +X s walk, verify.py fees |
| `size55.py` -> `size55.json` | Kelly, the rule options x 3 worlds, 20,000 4-week runs |
| `edge.py` -> `edge.json` | the 84 variants |
| `dryrun.py` -> `dryrun.json` | the executor on Nov 16-19 (paper + fake live) |
| `shots.py` | the two phone screenshots (run under the browser lock) |

Tests: `python tests/run_area.py kalshi` (new suite kalshi_k8_monday; kalshi_clock part s = the $55 rule end to end: a week where
every bet loses stops at -$13.75 or less, then the drawdown stop turns live OFF before -$19.25).

LEAD WIRES: bump the Kalshi page's kalshi.css / kalshi.js `?v=k40` -> `k41` in tools/web_public/kalshi/index.html and
tools/web_public/kalshi/sw.js (CACHE + SHELL) so cached phones get the K8 status card.
