---
title: Regime guard round 3 - 0 of 22
family: risk
date: 2026-11-22
status: rejected
summary: No pre-trade market signal separates the losing 2021-25 years from 2026; every guard costs 2026 money.
---

# Regime guard, round 3 (overnight 2026-11-22): REJECTED, 0 of 22

**In one line:** we looked for a warning sign, known before each trade, that the market looks like the bad years (2021-25), so Zlarior (LIT) and ATLAS could trade at half size or sit out. None of the 22 versions worked. Every one of them costs real 2026 money and does not save money in the bad years. **Nothing changes in the live bots.**

## What it means for your money

| What | Result |
|---|---|
| Zlarior (LIT) today, no guard, $350 a trade | Jan-Jun 2026 **+$20,868** ($3,424/mo). Jul-Oct **+$9,659** ($2,601/mo). 2021-25 only **+$2,065** ($40/mo, max drop -$13,047) |
| ATLAS today, no guard, $250 a trade | Jan-Jun **+$18,362** ($3,012/mo). Jul-Oct **+$5,256** ($1,415/mo). 2021-25 **+$10,393** ($203/mo, max drop -$11,403) |
| Builder 50K eval with LIT | Passes 84.8% (Jan-Jun) and 84.3% (Jul-Oct), in about 9 days. In a 2021-25-type market it passes only 32.3% |
| ATLAS funded 25K | About $584 / $493 a month in 2026, but 94.2% of accounts lost within 6 months in a 2021-25-type market |
| Best guard for 2026 eval (LIT half size on "trend-heavy" weeks) | Eval pass goes up to 89.5% / 92.5%, but it costs 5.5% of Jan-Jun $ (the limit is 5%) and drops 2021-25 from $2,065 to $1,180. **Not eligible.** At most we keep watching it on paper |
| Best guard for 2021-25 drawdown (ATLAS half on trend-heavy weeks) | Max drop gets 27% smaller, but ATLAS loses $4,400 of 2021-25 profit and 24% of Jan-Jun profit. A random pick of the same number of days does about as well (68.5%; it needed 95%) |
| Versions passing the full bar | **0 of 22** |

## What was tested (all set before any run, futures data only, costs in)

| Signal (from the 20 sessions before the trade) | Idea | Why it failed |
|---|---|---|
| R1 "Shadow setup" (new): a simple London sweep-and-reclaim on every NQ session, 1,116 trades | If sweeps stop paying market-wide, LIT should slow down | Sweeps paid **worse** in 2026 (-0.28R / -0.39R) than in 2021-25 (-0.19R), even before costs. It flags 2026 more often than the bad years |
| R2 Moves keep running (variance ratio) | Strong trends run through LIT's stops; chop hurts ATLAS | About the same every year (around 1.01). Points the wrong way |
| R3 Share of trend days | Same idea, measured per day | No real step between 2026 and older years. On flagged days the bots are weaker mostly in 2026, not in 2021-25 |
| R4 Thin market (low volume) | Thin markets give false sweeps | Flags the bad years more often (36% vs 14-15%), but LIT does **better** on those days in 2026, and every version costs 2026 too much |
| R5 NQ and VIX rising together | "Spot up, vol up" is unhealthy | That is a 2026 trait (80% of Jul-Oct). It flags LIT's **best** days (+1.14R vs -0.66R) |
| R6 2-of-5 vote | Combine them | Flags almost all of 2026. Big 2026 losses |

Each signal was tried as "half size" and as "sit out", for each bot: 22 versions. Every one fails the first, cheap check: the warning has to show up clearly more often in 2021-25 **and** the bot has to do worse on warned days. Every one also fails "2026 not worse by more than 5%" and the random-days check.

## Checked and not repeated (already rejected before)
- Realized vol vs VIX, and the bot's own last 20 trades (drift switch, 51 versions; ATLAS member pause): rejected 11-17 to 11-20. Not rerun.
- Overnight range expansion: covered by the overnight-share, Asia-range and range-so-far rejections. Not rerun.
- NQ-ES correlation: cannot be tested, because ES data starts 2025-04-14.

## Skeptic review (5 skeptics, re-ran everything)
- All 22 results reproduced digit for digit. No look-ahead found: flags use only sessions that closed before the trade's 18:00 ET open, confirmed by a truncation test.
- With zero costs the order stays the same, so costs are not the reason for the rejection.
- A second, stricter rebuild of R2/R3 gives the same verdict. ATLAS R3 is right on the edge of the share test (1.23x-1.31x), but ATLAS does better on flagged days in 2021-25 and it costs 23% of Jan-Jun.
- Corrected wording: this closes the regime lever for **market-weather and market-wide sweep signals**. It does not prove no regime signal can exist. R1 does not cover ATLAS.
- The LIT baseline and ATLAS fixed $ match round 2 exactly. ATLAS funded moved from 8.5/9.2/94.5% lost to 8.2/8.3/94.2% because of a code change after commit 153552591 (not the VIX refresh). It changes no verdict, because every version is compared with the same-run baseline.

## Honest takeaway
Three rounds have now found the same thing: the bad years do not look different **before** a trade in any market measure we can build from futures data. They are bad because the setup itself pays less. Size-down or stand-aside guards keep cutting good 2026 days. The more promising directions for "make money" are what you already do: pass evals fast in markets like 2026, take payouts early, and keep the risk per eval small. A regime switch is not one of them.

## Recorded (lead adds when landing)
docs/TESTED_AND_REJECTED.md:
- **2026-11-22 Regime guard round 3** (research/regime/guard3.py, regime-guard3-2026-11-22.md): shadow-setup hit rate R1, intraday variance ratio R2, trend-day share R3, thin volume R4, NQ-VIX co-movement R5, 2-of-5 vote R6; half / out; LIT and ATLAS. **0 of 22 pass, all fail the stage-0 kill-gate.** R1 sweeps pay worse in 2026 than in 2021-25 (flags 2026 87.5/80.8% vs OLD 70.4%). R5 flags LIT's best days. Best placebo 47.5% / 68.5% (95 needed). Closes the regime lever for market-weather and market-wide sweep signals, not every possible signal. ATLAS funded baseline moved 8.5/9.2/94.5 -> 8.2/8.3/94.2 because of a code change after 153552591; verdict unaffected.

Nothing was armed, committed or pushed by this step, and no live_model*.json was touched. Only one round-3 write-up should be landed: the separate t1 (R2/R3) and t4 (R5) runs are duplicates of rows in the 22, so do not count them twice.
