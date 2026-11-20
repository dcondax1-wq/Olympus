---
tags:
  - zeus/research
  - family/sessions
  - verdict/rejected
type: "research"
date: "2026-10-23"
status: "rejected"
source: "research/writeups/allday.md"
aliases:
  - "NQ around the clock"
---

# NQ around the clock

> [!failure] Verdict: rejected
> rejected

**Full title:** NQ around the clock - a 24-hour map and what works in each window (24/5 trading?)

## Summary

Owner (2026-10-23) - "Start trading 24/7. Find more setups with the same or higher win rate." The CME NQ day (18:00-17:00 ET) was split into 10 windows and mapped (range, straight-move days, how often the prior window's and the prior day's high/low get swept and reversed, by weekday and VIX). 7,800 setups were tested in the 9 tradable windows - LIT's own chain tuned per window plus four new families (sweep-and-reclaim of a box, opening-range breakout, mean reversion to VWAP / the window open, continuation after a one-way window) - picked on 2026 H1, checked untouched on H2, 2025 and 2021-24, with placebo and chance counts. Answer - no. No window pick holds; as a group the setups are no better than random entries (1.1% positive in all four periods vs 1.3% for random); the 24/5 schedule picked on H1 makes +$40k in H1 and loses $12k in H2, and on LIT's 50K eval it lifts 2-week fails from 0% to 28-35% in H2. More trades are easy (10 a week) but cost money. Sweeps reverse about half the time in every window - a coin flip. Closest leads (paper only, nothing built) - LIT's own Asia slot on ATLAS's 25K (H2 2-week passes 43.5 -> 56.5% with no extra dead evals, but H1 slightly worse and 2021-24 worse) and an Asia (20:00-00:00) reclaim of the 18:00-20:00 range (positive in all four periods, ~1 a week, 40% win, but its neighbours fail H1 and 2023-24 lost). Keep LIT 02:00-15:30 and ATLAS as they are.

## Money first

- **Do not switch to 24/5.** LIT (02:00-15:30, 1 a day) and ATLAS stay as they are. Nothing was built in the bot.
- The night can be traded more often, but no rule found here earns its slot: the in-sample winners of every window lose
  out of sample, and as a group they are at chance level.
- **Paper-watch only, if anything:** ATLAS + LIT's Asia slot on the 25K (needs account B's evening calendar) and the Asia
  reclaim of the 18:00-20:00 range. Neither passes the hard rules.

## Links

- Family: [[Family sessions]]
- Day: [[Day 2026-10-23]]
- Refers to: [[lit-all-hours|LIT all hours]], [[lit-more-entries|LIT more entries]]
- Runs: `ad_sched_h1_all, ad_sched_h1_evening, ad_sched_long_all_money, ad_sched_long_holds_peeked, ad_atlas25k_asia_slot, ad_h1_open18, ad_h1_asia, ad_h1_late_asia, ad_h1_lon_open, ad_h1_london, ad_h1_ny_pre, ad_h1_ny_open, ad_h1_ny_mid, ad_h1_ny_pm, ad_long_open18, ad_long_asia, ad_long_late_asia, ad_long_`
- Source: `research/writeups/allday.md`
- Back to [[ZEUS Home]]
