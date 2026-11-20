---
title: Premarket brief - the "thinking before the trade" page data, and a pre-registered day bias that is no better than a coin
family: bias
date: 2026-11-20
status: rejected
summary: tools/premarket_brief.py builds nq/brief.json (levels, gap, ATR, VIX/VXN band, Tier-1/2 news with what each bot does, each bot's window + setup + levels, recap). Two day-bias rules were pre-registered before measuring. B1 (overnight drift at 08:00) hit 47.1% of 442 days 2021-25, 59.4% of 69 (2026 H1), 44.6% of 56 (H2); B2 (fade yesterday) 49.7% / 47.7% / 39.8%. Neither beats a coin in all three periods, so the brief shows the call as context only.
runs: []
---

## What the owner asked
"Thinking process before, and through trades. News, bias, entries, more than just the strategy and rules."
So the brief answers, before the bell: where is price vs the levels, what news is coming and what the bots do about it,
which way the day leans (and how much that is worth), and per bot: when it may trade, what it is waiting for, which levels.

## What was built
- `tools/premarket_brief.py` -> `tools/web_public/nq/brief.json` (contract `docs/BRIEF.md`, ~8-9 KB, deterministic, only
  `built_at` churns; no rewrite when nothing else changed). Futures data only: `data/NQ_5m.csv`, `data/VIX_1d.csv`,
  `data/VXN_1d.csv`, `data/news/events.csv`. Read only.
- Bot rules are read from the bots' own code (no copy that can drift): windows from `engine/live_board`
  (LIT 02:00-15:30, ATLAS EMA 03:00-09:30 not Mondays, MACD 02:00-05:00 + 09:30-11:00, S/R 09:30-12:00), early closes and
  closures from `engine/cme_calendar` (Thanksgiving 2026-11-26: windows end 12:45), the news rule from `engine/guards`
  DEFAULTS + `live_model.json` (news guard OFF: Zlarior and ATLAS trade through releases) and the Rapid preset's
  `news_ban: funded` (`engine/multi_account`: funded Rapid is flat -2/+2 min around Tier-1).
- Recap after the close + `prev_recap` every morning (the cloud only gets the day's bars after the PC's 17:05 push).
- 73 checks: `python -X utf8 -m tests.test_premarket_brief`.

## The bias test (pre-registered: `research/lab/brief_bias_prereg_2026-11-20.md`, committed before the first measurement)
Outcome = the 09:30-16:00 candle (up or down). Bar for "works": n >= 40, hit > 50% with one-sided binomial p < 0.025
(two rules), and above the drift baseline, in EACH of 2021-25, 2026 H1, 2026 H2.

| Rule | 2021-25 hit (n) | 2026 H1 hit (n) | 2026 H2 hit (n) | p (H1, best) | Works? |
|---|---:|---:|---:|---:|---|
| B1 overnight drift >= 0.2 ATR at 08:00 | 47.1% (442) | 59.4% (69) | 44.6% (56) | 0.074 | no |
| B2 fade yesterday's candle | 49.7% (881) | 47.7% (111) | 39.8% (88) | 0.72 | no |
| Coin | 50% | 50% | 50% | | |
| Share of up RTH candles | 53.7% (1,022 days) | 53.7% (123) | 43.4% (99) | | |

- B1's good H1 (59%) did not survive H2 (45%) and is the wrong way round on 5 years: a picked-on-H1 mirage.
- B2's 39.8% in H2 is not a "reverse it" signal: it was not the pre-registered rule, and 2021-25 is 49.7%.
- Subgroups (VIX band, Tier-1 days) are all small and flip sign between periods (e.g. B1 on Tier-1 days 75% of 8 in H1,
  11% of 9 in H2). Nothing to use.
- Money: a bias that is right 47-50% of days is worth $0; using it to skip or size trades was already rejected for
  LIT trades (`bias-filters.md`, `lit-bias-discretion.md`, `hq-bias.md`). The brief therefore shows the call grey,
  "context, no better than a coin", and the bots ignore it.

## What the brief is good for
Not a signal: a checklist. Today's levels (PDH / PDL / PDC, overnight high / low, last week's high / low, the 18:00 open
and LIT's two target lines = 18:00 open +/- one VIX day move), the gap in points and ATRs, Tier-1 news with its time and
"the bots trade through it" (or not, on a funded Rapid), and in plain words what each bot needs before it can enter.
That is the thinking a person does before the bell, written down the same way every day.

## Honest limits
- VIX / VXN in the cloud end 2026-10-16: the brief says so in `data.stale` (and the LIT target lines use that close).
- The cloud's NQ bars end at the PC's last push (17:05 ET): a 06:00 ET brief has no overnight yet and says so.
- Recap trades come from `trades.json` (live + paper rows); when it is old the recap says "no trade data yet".
