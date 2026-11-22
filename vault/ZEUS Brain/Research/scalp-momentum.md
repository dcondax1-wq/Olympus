---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/blitz
type: "research"
date: "2026-10-28"
status: "promising - the noise-area scalp holds in 2026 H1 and H2 after costs and beats random directions; 2021-25 only breaks even; on MFFU accounts it passes few evals and pays little once funded. Paper ..."
source: "research/writeups/scalp-momentum.md"
aliases:
  - "Momentum scalps for a third account"
---

# Momentum scalps for a third account

> [!tip] Verdict: promising
> promising - the noise-area scalp holds in 2026 H1 and H2 after costs and beats random directions; 2021-25 only breaks even; on MFFU accounts it passes few evals and pays little once funded. Paper only, nothing built.

**Full title:** Momentum scalps for a third account - one real edge (noise-area scalp) that holds in both 2026 halves, but it is too small to earn real money on an MFFU 25K or 50K

## Summary

Owner 2026-10-28 - a third strategy, a scalper that trades several times a day on its own MFFU account and makes money. 10 momentum / breakout / continuation families (about 10,000 settings, each run on 1m and 5m bars) were tested on CME NQ1! (1m for 2026, 5m for 2021-25), costs in ($1.90 a micro, 1 tick on every market and stop fill, limits only when traded through, every same-bar tie booked against us), picked on 2026 Jan-Jun, checked on Jul-Oct, 2021-25 on 5m as a second check. Opening-range breakouts, EMA pullbacks, CISD continuation, N-bar breakouts, ES-leads-NQ and news bars all fail the July-October check. One family survives - the noise-area momentum scalp (a close outside the 09:30 open's normal time-of-day range, checked every 30 minutes 10:30-15:30, stop 1.5 x the 5m ATR, trail 1.5R after +1R, out after 30 minutes): 11-12 trades a week, H1 PF 1.37 (+$4,870 at $150 a trade, $799/mo), H2 PF 1.22 (+$1,729, $466/mo), 2021-25 PF 1.02 (+$2,831, $55/mo); random directions on the same bars lose (p 0.025 / 0.15 / <0.025); 80 neighbouring settings are all positive in H1, 99% in H2. But a 60-point stop is $122 a micro against a $1,000 trailing loss, so the 25K eval passes only 21% in 2 weeks (fails 4% H1, 19% H2) and a funded 25K pays about $0-100 a month (it gets stuck at the floor). The 5m displacement continuation and the trend-day add-ons also hold in both 2026 halves but lose or break even in 2021-25 and fare worse on the eval.

## Money first

**Best candidate: the noise-area momentum scalp ("NA scalp").** Every number has costs in. "$150 a trade" = the 25K's
risk per trade (micros = $150 / stop cost, at least 1). 2026 runs on 1m bars; 2021-25 is the same rule on 5m bars (no 1m
history before 2026).

| Span | Trades | /week | Weeks with 5+ | Win % | Avg R | PF | Net ($150 a trade) | **$ / month** | Max DD | Costs / gross |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026 H1 (Jan-Jun, picked here) | 304 | 11.9 | 89% | 52.6 | +0.098 | 1.37 | +$4,870 | **+$799** | -$1,459 | 17% |
| **2026 H2 (Jul-Oct 16, untouched)** | 177 | 11.4 | 94% | 50.8 | +0.066 | **1.22** | **+$1,729** | **+$466** | -$1,251 | 25% |
| 2021-25 (5m, second check) | 2,681 | 12.5 | 92% | 48.6 | +0.007 | 1.02 | +$2,831 | +$55 | -$6,322 | 81% |
| of which 2025 | 636 | 12.3 | 85% | 48.9 | -0.003 | 1.00 | -$101 | -$8 | -$3,651 | ~100% |

**On the MFFU accounts** (a fresh eval started on every session; size = the share of the room to the trailing floor shown,
capped, never more than the soft daily loss allows; a wide stop still gets 1 micro while it fits half the room; "stuck" =
the room no longer fits two stop-outs, counted as dead):

| NA scalp | 2-week pass / fail (p10/f10) | decided in 2 wks | 3-week pass / fail | median sessions to pass | passes slower than 3 wks | eval passes / month (back to back) | funded $ / month to the owner |
|---|---:|---:|---:|---:|---:|---:|---:|
| Builder 25K, H1 (30% of room, max $600) | 21.0 / 4.2 | 25% | 30.7 / 21.1 | 9 | 12.5% | 0.66 | ~$100 |
| Builder 25K, **H2** | 21.7 / 18.8 | 41% | 23.4 / 42.2 | 6 | 3.8% | 0.81 | ~$0 (stuck) |
| Builder 25K, 2021-25 | 15.2 / 12.2 | 27% | 19.5 / 26.9 | 7 | 13.4% | 0.35 | ~$30 |
| Builder 50K, H1 (30% of room, max $1,200) | 23.5 / 1.7 | 25% | 36.0 / 4.4 | 9 | 16.3% | 0.33 | ~$175 |
| Builder 50K, **H2** | 27.5 / 0.0 | 28% | 37.5 / 9.4 | 7 | 5.0% | 0.81 | ~$30 |
| Builder 50K, 2021-25 | 16.7 / 3.8 | 21% | 20.5 / 12.3 | 6 | 13.8% | 0.29 | ~$95 |

In plain words: the edge is real but thin (about +0.07 to +0.10R a trade in 2026, nothing in 2021-25). With NQ near
26,000 the stop is about 60 points = $122 a micro, so the 25K can only carry 1-3 micros. Most evals neither pass nor fail
inside 2 weeks (the owner's 2-week rule is missed: only 25-41% are decided), and a funded account drifts into its trailing
floor before it earns payouts. **It is not yet a money-maker on a prop account.**

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-28]]
- Strategies: [[BLITZ (paper)]]
- Refers to: [[allday|NQ around the clock]], [[atlas-chatgpt-breakouts|ChatGPT's 10 ATLAS breakout templates]], [[diversifier-search|A strategy uncorrelated with LIT]], [[hq-continuation|HQ continuation]]
- Runs: `scalp_mo_na_scalp, scalp_mo_disp_5m, scalp_mo_trendday_1m, scalp_mo_combo`
- Source: `research/writeups/scalp-momentum.md`
- Back to [[ZEUS Home]]
