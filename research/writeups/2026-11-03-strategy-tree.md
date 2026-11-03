---
title: DAPHNE strategy-tree search (2026-11-03) - 1.13 million rule combinations on plain NQ level trades; the best rules hold out of sample no more often than shuffled noise
family: other
date: 2026-11-03
status: rejected (research lens, nothing adopted) - 31 of 80 best rules hold out of sample vs 25 and 28 when the conditions are shuffled (chance level); every rule trades 0.1-0.5 times a week; the top-5 basket makes +$29k in 2021-25 (mostly the training years) and +$541 in 2026 (PF 1.06); the #1 rule holds (2026 PF 1.33, +$95 a month) but that is what luck looks like among 80 tries
summary: The owner's TikTok "it likes moves" tree, built our own way on real CME NQ1! bars. 80 root rules (prior-day, overnight, Asia, London and opening-range highs and lows; fade after a sweep or trade the break; 1R / 2R; 60 / 120 min) grow a tree of up to 5 extra conditions each (volatility, gap, where the open sits in yesterday's range, distance from the open, hour, weekday, VWAP side, trend, VIX, opening-range width). Best-first branch-and-bound with an exact bound, trained on 2021-11 to 2024-12, tested on 2025-01 to 2026-10, with a placebo search on shuffled conditions. Page tools/web_public/tree, engine tools/strategytree.
runs: strategytree_top1, strategytree_top5
---

## Money first

**Nothing changes for the bots. DAPHNE is a research lens, paper only, never routed.**

The search did what the TikTok tool does: it found rules that made a lot in the training years (+$28 to +$44 a trade
per micro, after costs). Then it met 2025-26, which it never saw. **31 of the 80 best rules still made money and beat
their plain root. With the conditions shuffled into noise, 25 and 28 of 80 did the same.** That gap is chance. The
average best rule beat its root by **+$0.61 a trade** out of sample; the two noise runs did **+$1.26** and **-$1.35**.

| What | Train 2021-24 | Test 2025-26 | 2026 alone |
|---|---:|---:|---:|
| #1 rule (AL·SHORT, 4 conditions), $ a trade per micro | +$43.70 (67 trades) | +$14.81 (45) | +$27.37 (22) |
| #1 rule at the bot's size ($282 risk a trade), run `strategytree_top1` | 2021-25: +$6,135, PF 1.54, $122/mo | 2025: -$376, PF 0.90 | +$923, PF 1.33, **$95/mo** |
| Top-5 basket at the bot's size, run `strategytree_top5` | 2021-25: +$29,056, PF 1.54, $579/mo | 2025: -$425, PF 0.97 | +$541, PF 1.06, **$55/mo** |
| Live LIT for scale (run `lit_live`) | | | +$43,820, PF 4.19 |

- **Trades a week: 0.1 to 0.5 per rule.** The owner's floor is 2-4 a week. Even the top-5 basket makes 1.7 a week in
  2026, with 2+ trades in only 48% of weeks.
- **MFFU 50K eval speed: 0% passed within 2 weeks** (2026 and 2021-25) for the #1 rule and the basket. At 0.4 trades a
  week an eval never gets decided.
- **The training years carry the money.** The basket made +$13.1k in 2022 and +$13.2k in 2024 (both in the training
  data) and lost -$425 in 2025. That is the signature of a fitted rule, not an edge.

## What DAPHNE is (plain words)

Think of a tree that grows upward from one plain trade, its **root**: e.g. "short when NQ closes through the Asia low,
stop 1 tick beyond that bar, target 2R, out after 2 hours". Every **branch** adds one condition ("only when the open is
in the top half of yesterday's range"), every twig one more, up to 5. Each branch keeps fewer trades. The search wants
the branch whose trades beat the root by the most dollars a trade.

There are far too many branches to try them all, so the search uses a **bound**: for any branch it can work out the
best any of its twigs could ever do (the average of its best trades). If even that ceiling cannot beat the best rule
found so far, the whole branch is **cut**: that is the "CUT 54.6%" on the page. A test proves the shortcut loses
nothing: with no time limit, the search finds exactly the rule that trying every combination finds.

| Setting | Value |
|---|---|
| Data | TradingView CME NQ1! 5-minute bars (2021-11-30 to 2026-10-16), CBOE VIX; ES1! 5m only from 2025-04, so the ES condition was left out (no training data) |
| Roots (80) | 10 levels (PDH, PDL, overnight high/low, Asia 20:00-24:00 high/low, London 02:00-05:00 high/low, opening range 09:30-09:45 high/low) x fade (sweep, then a 5m close back inside within 30 min; stop 1 tick beyond the sweep extreme) or break (5m close through; stop 1 tick beyond the break bar) x target 1R / 2R x out after 60 / 120 min; entries 09:50-15:00, flat 15:55, one trade a day per root |
| Conditions (78 in 10 groups) | 30-day volatility quintile, gap (0.25%), open vs yesterday's range, entry distance from the open (ATR), hour, weekday, VWAP side, 20-day EMA trend, yesterday's VIX, opening-range width; bands like "quintile 2 to 5" count as one condition |
| Score | Mean excess $ a trade per micro over the root (after $1.90 a round trip), shrunk by n/(n+30); at least 60 training trades |
| Search | Best-first, depth 5, up to 4,000 expansions per root; **1,127,006 nodes**, 54.6% cut by the bound; 31 roots searched to the end, 49 stopped at the budget |
| Train / test | Train 2021-11 to 2024-12-31 (797 sessions); test 2025-01-01 to 2026-10-16 (462 sessions); 2026 alone (205) |
| Holds out of sample | Test $ a trade beats the root's test $ a trade AND is above $0, on 10+ test trades |
| Placebo | The same search with each root's condition rows shuffled (2 seeds): what chance alone finds |

## The top 10 rules (best training score, one per setup)

$ = a trade per MNQ micro after costs. "Test $/mo" = at 1 micro / at the bot's size ($282 risk a trade, wider stop =
fewer micros).

| # | Root | Conditions (in the order the search added them) | Train n / $ / win | Test n / $ / win | 2026 n / $ | Test trades/wk | Test $/mo 1 micro / bot | Out of sample |
|---|---|---|---|---|---|---:|---|---|
| 1 | AL·SHORT 2R 120m | open above the middle of yesterday's range · entry within 0.4 ATR of the open · 10:00-14:00 · vol quintile 2-5 | 67 / +$43.70 / 55% | 45 / +$14.81 / 38% | 22 / +$27.37 | 0.49 | +$30 / +$25 | holds |
| 2 | ORL·LONG 2R 120m | VIX 20+ · daily trend down · 9:50-11:00 · open above yesterday's low · vol quintile 4-5 | 71 / +$44.02 / 49% | 12 / -$59.11 / 17% | 0 / n/a | 0.13 | -$32 / -$77 | fails |
| 3 | LL·SHORT 2R 120m | open in the high half of yesterday's range · 10:00-12:00 | 60 / +$41.67 / 53% | 33 / -$18.78 / 33% | 17 / -$28.43 | 0.36 | -$28 / -$27 | fails |
| 4 | ONL·SHORT 2R 120m | vol quintile 2-5 · 10:00-13:00 · open inside yesterday's range · entry 0.15+ ATR from the open | 76 / +$35.80 / 49% | 32 / -$6.84 / 38% | 16 / -$33.71 | 0.35 | -$10 / +$34 | fails |
| 5 | ORL·SHORT 2R 120m | Tuesday · VIX 15+ · 9:50-11:00 | 61 / +$37.12 / 51% | 39 / +$23.83 / 41% | 16 / +$93.04 | 0.42 | +$42 / +$50 | holds |
| 6 | ONH·SHORT 2R 60m | entry 0.15+ ATR from the open · no gap up · 10:00-15:00 · VIX 15+ · open below yesterday's high | 60 / +$34.47 / 52% | 39 / -$6.36 / 33% | 17 / +$12.92 | 0.42 | -$11 / -$46 | fails |
| 7 | ORH·SHORT 2R 120m | 10:00-11:00 · open above yesterday's low · VIX 15+ · opening range not narrow | 74 / +$32.23 / 43% | 41 / -$22.62 / 27% | 15 / -$91.17 | 0.44 | -$42 / -$125 | fails |
| 8 | AH·SHORT 2R 120m | entry 0.15+ ATR from the open · above VWAP · VIX 15+ · 9:50-13:00 · open below yesterday's high | 60 / +$38.83 / 52% | 36 / -$7.39 / 36% | 21 / +$13.53 | 0.39 | -$12 / +$15 | fails |
| 9 | LH·LONG 2R 60m | 10:00-13:00 · vol quintile 2-4 · entry 0.15+ ATR from the open · open below yesterday's high | 65 / +$28.63 / 46% | 28 / +$12.24 / 39% | 13 / +$0.91 | 0.30 | +$16 / -$45 | holds |
| 10 | LL·LONG 2R 120m | entry near the open · open above yesterday's low · vol quintile 2-5 · opening range not wide · 9:50-11:00 | 61 / +$28.28 / 48% | 29 / -$19.50 / 24% | 12 / -$36.15 | 0.31 | -$26 / -$71 | fails |

- **Training $ fall from +$36.50 a trade to -$8.97 in the test** (top 10 average); 3 of 10 hold, 7 fail.
- **The #1 rule in full:** short at the Asia low on a 5-minute close through it, stop 1 tick beyond the break bar,
  target 2R, out after 120 min, only when the 09:30 open is above the middle of yesterday's range, the entry is within
  0.4 ATR of the open, between 10:00 and 14:00 ET, and 30-day volatility is not in its lowest fifth. It held (+$14.81 a
  trade in the test), but 2025 alone lost (PF 0.90) and it trades once every two weeks.
- **The plain roots are no better:** 24 of 80 roots made money in training, 24 in the test, only 9 in both.

## The honest out-of-sample verdict

| Search | Best rules | Hold in the test 2025-26 | Hold in 2026 alone (5+ trades) | Average test excess over the root |
|---|---:|---:|---:|---:|
| **Real conditions** | 80 | **31 (38.8%)** | **37** | **+$0.61** a trade |
| Shuffled conditions, seed 1 | 80 | 25 (31.2%) | 36 | +$1.26 |
| Shuffled conditions, seed 2 | 80 | 28 (35.0%) | 24 | -$1.35 |

The real search beats the noise runs by 3 to 6 rules out of 80. With these sample sizes (about 35 test trades a rule)
that is inside the luck band; the page and Jarvis show it as **CHANCE LEVEL** (the bar: more than 10 points above every
placebo run). Over a million combinations were tried; the multiple-testing price is that the best of them look great
in training by construction.

This matches the long "Tested and rejected" list (`docs/CLAUDE_REFERENCE.md`): plain level trades with day-type filters
(92 confluences, 6 daily-bias methods, VIX / volatility tilts) have no edge that holds across both periods. LIT's edge
comes from its full sweep -> inducement -> displacement -> CISD sequence and its VIX target, not from filters like these.

## What the page shows (and how to read it)

`tools/web_public/tree/` (link it from the NQ dashboard and Jarvis): the tree grows node by node in the search's own
order; cut branches flash and fade; the best path lights up and pulses run up it. TRAIN / TEST colours every branch by
its training score or by its test result (green made more than its root in 2025-26, red made less): in TEST the canopy
turns half red, which is the verdict in one picture. Tap a branch for its rule card ($ a trade, $ a month at 1 micro,
train vs test); the seeds along the bottom switch roots; TOP 10 lists the table above. Screenshots:
`research/handoff/2026-11-03/tree/`.

## How to rerun

- `python -X utf8 -m tools.strategytree` (about 3 CPU-minutes; `--placebos N`, `--expand N`, `--min-n N`): writes
  `research/strategytree/tree.json`, the page's copy and `jarvis.json`, and the runs `strategytree_top1` / `_top5`.
- `python -X utf8 -m tools.strategytree.demo`: the page's synthetic demo fixture.
- Tests: `python -X utf8 -m tests.test_strategytree` (bound vs brute force, exact search, no look-ahead with the future
  scrambled, determinism, JSON, Jarvis card), `python -X utf8 -m tests.shots_strategytree` (phone screenshots, console errors).
- New root rules or conditions go in `tools/strategytree/roots.py` / `features.py`; anything adopted must still pass the
  usual gates (2026 and 2021-25, 2-4 trades a week, eval speed).
