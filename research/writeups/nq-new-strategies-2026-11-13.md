---
title: New NQ strategies for more eval accounts (Team E2, 2026-11-13). Seven new families, one real but small edge (the gap fade after a failed opening drive), no new eval account worth buying, BLITZ unchanged
family: other
date: 2026-11-13
status: no adopt-candidate; one promising paper lead, the gap fade G1 (holds in H1, H2, 2025 and 2021-24; coin-flip placebo p 0.003 over 2021-25 but 0.22 in 2026; 1.7 trades a week; 1 micro in 2026, so an MFFU eval passes 0-7% in 2 weeks and the slot makes about $0 a month). BLITZ: both new band angles fail 2021-25, so it stays as built. A third or fourth eval account running a new strategy does not raise $/month or pass odds.
summary: Owner - "Find every edge in trading ... build bots that will make me money. Mainly NQ." Team E2 looked for new NQ strategies uncorrelated with LIT / ATLAS / BLITZ, so the owner could run more evals on different signals. Each hypothesis was written before the run, with a new angle against the rejected list. Seven families, 140 variants on CME NQ1! 5m RTH (2021-11 to 2026-10-16, ES1! from 2025-04), $500 risk a trade, costs in, every stop 1 tick beyond the setup's structure. The families were an ORB with a failed-breakout filter, a prior-day high/low sweep with climax volume, NQ/ES relative strength at the open, the overnight gap fade with a failed-drive and volume test, VWAP reversion on low-VIX days, end-of-day breaks and reversals, and a CPI/NFP/FOMC playbook. 2 of 140 variants hold in all four spans (H1, H2, 2025, 2021-24), against 0.75 on average when the directions are coin flips (20 seeds): about chance for the whole grid. One family stands out, the gap fade (positive in 22/24/20 of 24 variants in H2 / 2025 / 2021-24). Its new filter is the one that matters. The same gap fade without the failed-drive test loses in 3 of 4 spans. G1 (gap >= 0.1 x the 14-day range, the 09:30-10:00 range closes in the half away from the gap, stop 1 tick beyond that range, 2R) makes +$180 a month in 2026 (PF 1.14) and +$496 a month in 2021-25 (PF 1.34). Its daily correlation is 0.03 / -0.04 with LIT, -0.02 / 0.00 with ATLAS and 0.08 / 0.12 with BLITZ. Its 2026 stops are about 145 points, so $500 buys 1 micro and an MFFU eval cannot be passed in 2 weeks. On its own 25K / 50K it passes 0-7% of 2026 evals in 2 weeks, and the slot makes -$6 to +$29 a month in 2026. As a small add-on on LIT's funded 50K it is +$23 in H1 and -$16 in H2, so it fails too. BLITZ band angles - the paper's gap-aware band is better in both 2026 halves ($936 / $771 vs $912 / $577 a month at $150) but loses in 2021-25 (-$15 vs +$89 a month); the implied-volatility band is worse. Nothing changes.
runs: e2_gapfade_g1, e2_orb2_h1pick, e2_pdx_h1pick, e2_rs_h1pick, e2_gapf_h1pick, e2_vwr_h1pick, e2_eod_h1pick, e2_book_h1picks
---

## Money first

**Nothing new to switch on, and no new eval account to buy.** One family has a real but small edge (the gap fade G1). Its
stops are too wide for a prop eval, so it stays a paper lead. BLITZ stays exactly as built.

All rows are at $500 risk a trade with costs in ($1.90 a micro, 1 tick on every fill), on CME NQ1! 5m. The eval
columns are the run library's MFFU 50K started on every 2026 session at that size.

| Strategy (pick) | 2026 $ / month | 2021-25 $ / month | Trades / week (2026 / 21-25) | PF (2026 / 21-25) | Max DD (2026 / 21-25) | Corr with LIT (daily, 2026 / 21-25) | 50K eval 2-week pass / fail (2026) | Verdict |
|---|---:|---:|---|---|---|---|---|---|
| **Gap fade after a failed opening drive (G1)** | **+$180** | **+$496** | 1.8 / 1.8 | 1.14 / 1.34 | -$4,377 / -$4,072 | 0.03 / -0.04 | 0.0 / 0.0 (median pass 27 sessions) | **paper lead**: holds in all four spans, but too slow for an eval |
| ORB, 2nd side after a failed break (H1 pick) | +$706 | +$184 | 1.5 / 1.8 | 1.87 / 1.16 | -$878 / -$6,892 | 0.07 / 0.00 | 0.0 / 0.0 | rejected: loses in H2 and 2025 |
| Prior-day high / low sweep (H1 pick; the volume gate made it worse) | +$170 | -$152 | 1.0 / 1.0 | 1.14 / 0.89 | -$2,661 / -$14,207 | -0.03 / 0.03 | 0.0 / 17.6 | rejected |
| NQ leads ES at 10:00 (H1 pick; ES only from 2025-04) | +$424 | +$72 (2025 May-Dec only) | 1.3 / 0.2 | 1.46 / 1.41 | -$3,740 / -$2,028 | -0.07 / -0.05 | 0.0 / 0.0 | rejected: loses in H2 |
| Gap fade, H1 pick (gap >= 0.25, 15-min range) | +$198 | +$171 | 1.4 / 1.3 | 1.17 / 1.13 | -$3,952 / -$7,373 | -0.01 / 0.01 | 0.0 / 0.0 | rejected: loses in H2 (G1 is its neighbour) |
| VWAP reversion on low-VIX days (H1 pick) | +$602 | -$665 | 2.4 / 2.4 | 1.25 / 0.76 | -$4,720 / -$36,835 | 0.11 / 0.07 | 9.0 / 13.1 | rejected: loses in 2025 and 2021-24 |
| End of day: fade a 1.5-sigma day at 15:00 (H1 pick) | +$73 | -$498 | 1.1 / 1.2 | 1.06 / 0.67 | -$4,228 / -$28,342 | -0.03 / 0.01 | 5.0 / 4.5 | rejected |
| CPI / NFP / FOMC playbook | n/a | n/a | 0.1-0.2 | - | - | - | - | rejected: 3-7 trades a half year, no variant reaches 12 in H1 |
| Book of all H1 picks on one account (one position) | +$1,654 | -$709 | 6.1 / 6.0 | 1.32 / 0.89 | -$6,598 / -$49,797 | -0.02 / 0.04 | 20.6 / 33.2 | rejected: the 2026 H1 picks lose over 5 years |
| BLITZ with the gap-aware band (at $150) | $936 / $771 (H1 / H2) | -$15 | 6.8 / 4.8 / 6.2 | 1.86 / 2.31 / 0.99 | -$931 / -$550 / -$5,963 | - | - | rejected: 2021-25 worse than today's +$89 |
| BLITZ with the implied-volatility band (at $150) | $585 / -$8 | +$10 | 4.6 / 3.5 / 4.6 | 1.76 / 0.99 / 1.01 | - | - | - | rejected |

**The third (or fourth) eval account question.** The best new strategy, G1, on its own MFFU account. Sizes were picked on
2026 H1 only. These are 1,000-path Monte Carlo runs (500 for the slot), MFFU Builder rules, 80% split and 2 sessions of paperwork.

| G1 on its own account | 2-week pass / fail, H1 / H2 / 2025 / 2021-24 | Slot $ / month to you, net of every eval (H1 / H2 / 2025 / 2021-24) |
|---|---|---:|
| Builder 25K ($63): eval 50% of the room, funded 40% <= $1,000 | 5.0/0.0, 2.6/0.0, 13.0/0.6, 9.0/0.2 (70% of the room: 7.0/0.2 ...) | -$6 / +$6 / +$41 / $0 |
| Builder 50K ($91.80): eval 30-50% of the room, funded 40% <= $1,000 | 7.2/0.0, 6.8/0.0, 17.6/1.0, 11.8/1.0 | -$3 / +$16 / +$90 / +$8 |
| For comparison: BLITZ's 25K slot (v2, `blitz-edge-2026-10-30b.md`) | 47.9/23.5, 36.2/21.7, 24.7/48.4 (H1 / H2 / 2021-25) | $286 / $52 / -$39 (H1 / H2 / 2021-25) |
| G1 as an add-on on LIT's funded 50K (10% of the room <= $400, never while LIT holds) | (funded only) | LIT alone $923 / $910 / $74 / $56 -> $946 / $894 / $109 / $72 |

- **No.** A new eval account running G1 would almost never be decided within 2 weeks (0-7% in 2026; the owner's rule is
  decided in 2 weeks, passed in 3). Over 6 months its slot makes about $0 a month in 2026.
- MFFU also allows only 3 funded accounts per person. LIT 50K + ATLAS 25K + BLITZ 25K already fill them
  (`2026-11-04_second_strategies_night.md`). A G1 account would have to replace BLITZ, which makes more in 2026, or sit
  at another firm, where it pays the same ~$0.
- As an add-on on LIT's funded 50K it is mixed: +$23 in H1, -$16 in H2, +$35 in 2025, +$16 in 2021-24. That fails the
  "better in both 2026 halves" test. Not proposed.

## What was asked, and how it was judged

- **Ask (owner via the lead):** "Find every edge in trading ... build bots that will make me money. Mainly NQ."
  - Team E1 works on LIT and ATLAS. E2 looks for NEW NQ (or ES) strategies uncorrelated with LIT / ATLAS / BLITZ, and
    tries to fix BLITZ, so the owner can run more evals on different signals.
- **Rules (CLAUDE.md):** CME futures data only. Every result is judged on 2026 AND 2021-25, with 2-4 trades a week per
  strategy or as a book, costs in, stops beyond structure, money and eval speed.
  - A variant "holds" when it is positive with PF >= 1.1 in all four spans: 2026 H1 (Jan-Jun), 2026 H2 (Jul-Oct 16),
    2025 and 2021-24.
  - Picks are made on H1 only (n >= 12, PF >= 1.2, best H1 $), with a 2021-24 re-pick as a check.
  - Chance level: every variant is re-run with coin-flip directions (same entry bar, the stop at the same distance, the
    same exits), 20 times.
- **Execution** (as `tools/div_search.py`):
  - Entry at the next 5m open + 1 tick. A stop touched in a bar fills at the stop, or at the open through it, -1 tick.
  - A target needs a trade-through. Stop and target in the same bar count as the stop.
  - $1.90 a micro round trip. Size = floor($500 / (stop x $2 + $1.90)) micros, 1-40: size follows the stop.
  - Each stop is 1 tick beyond the structure that defines the setup: the sweep extreme, the failed break's extreme, the
    opening range or the last swing. The stop is never a fixed distance; one under 8 points is widened to 8.

## The seven families (hypothesis first, then the result)

Not redone (rejected list): plain ORBs with R targets, the failed-ORB fade back inside, the unconditional gap fill,
the textbook intraday / end-of-day momentum, the plain VWAP fade and plain level fades (DAPHNE tree). Each family below
adds one new angle to an old idea. The grid is in `tools/e2_new_strats.py grid()`.

1. **ORB, 2nd side after a failed break (`orb2`, 18 variants).**
   - Hypothesis: once one side of the opening range breaks and fails (a close back inside), the stops on that side are
     spent, so the break of the other side is the real move. The stop goes 1 tick beyond the failed break's extreme.
   - Result: very good in H1 (all 18 positive, PF up to 2.5) and in 2021-24 for the 15-minute range (PF 1.25-1.31,
     +$11-15k). But it loses in 2025 and is flat or negative in H2 (3 of 18 positive). 0 hold.
2. **Prior-day high / low sweep with climax volume (`pdx`, 18).**
   - Hypothesis: a first sweep of yesterday's high / low that reclaims within 1 bar on 1.5-2.5x the time-of-day volume
     is absorbed stop-running.
   - Result: the volume gate makes it worse. With volume >= 1.5x, every variant loses in H1, H2 and 2025. The plain
     sweep (rv 0) is the old, rejected fade. 0 hold.
3. **NQ vs ES relative strength at the open (`rs`, 16; ES data only from 2025-04).**
   - Hypotheses, both run:
     - "lead": NQ beating ES by z noise-sigmas at 10:00 keeps leading.
     - "catch": NQ lagging an ES move catches up.
   - Result: lead at 10:00 is good in H1 and 2025 (PF 2.13 / 1.41) but loses in H2 (0.90). Catch flips sign from span
     to span. 0 hold, and 2021-24 cannot be tested.
4. **Overnight gap fade, failed opening drive, volume (`gapf`, 24).**
   - Hypothesis: when a gap of >= g x the 14-day range opens and the opening range (15 / 30 min) closes in its half away
     from the gap, the drive has failed and price returns toward yesterday's close. The stop goes 1 tick beyond the
     opening range.
   - Volume, both tested:
     - "low": the opening range traded under its 20-day volume, so there was no institutional push.
     - "high": it traded above, so the reversal is real.
   - Result: the only family with a pattern. Positive variants: 11 of 24 in H1, 22 in H2, 24 in 2025 and 20 in 2021-24.
     2 hold.
   - The volume test does not help. "Low" and "high" volume both cut the trades to 0.5 a week without a consistent gain.
5. **VWAP reversion on low-VIX days (`vwr`, 18).**
   - Hypothesis: on quiet days (VIX at yesterday's close under its 1-year median / 33rd percentile), a close back inside
     the VWAP +/- k standard-deviation band after a close outside it reverts to VWAP.
   - Result: the VIX filter helps 2026 a little but not 2021-25. The H1 pick loses -$26k in 2021-24 and -$6.8k in
     2025. 0 hold.
6. **End of day (`eod`, 18).**
   - "Late break": a 5m close at a new day high / low after 14:00-15:00, held into the close, with the stop beyond the
     last 30-60 min swing. Good in 2021-24 (+$12k from 14:00) but it loses in H2 and 2025.
   - "Late reversal": fade a >= 0.5-1.5 sigma day at 15:00 / 15:25, the "since 2025 the last half hour reverses" note of
     `quant-anomalies.md`. From 15:25 it is strong in 2025 (+$25-27k) and H2, but it loses in 2021-24 (-$10k to -$20k),
     the out-of-sample years for that note. So the note was a 2025 pattern, not an edge. 0 hold.
   - Note: the "agree with the day's direction" switch changes nothing, because a close at a new day high is always
     above the open.
7. **CPI / NFP / FOMC playbook (`news`, 8).**
   - FOMC: the 14:00-14:30 statement range, then trade the break ("go") or the failed break ("fade") 14:35-15:30.
   - CPI / NFP: take the 09:30-10:00 range break only with ("follow") or against ("against") the 08:30-09:30 release
     move.
   - Result: 3-7 trades a half-year, so no variant can be picked (n >= 12) and none reaches 0.25 trades a week.
     FOMC fade to the close: 2021-24 +$5.3k on 22 trades, 2025 -$1.7k.
   - CPI dates for 2021-11 .. 2023-09 were added from the BLS schedule; each one shows a 2.4-18x normal 08:30 bar.

**The whole grid:** 2 of 140 variants hold in all four spans; coin-flip directions give 0.75 on average (0-3 over 20
seeds). As a grid that is chance. Only the gap-fade family shows a consistent sign across spans.

## The gap fade G1: is it real?

G1 = gap >= 0.1 x the 14-day range, 30-minute opening range (09:30-10:00) closed in its half away from the gap, short
(gap up) / long (gap down) at the 10:05 open, stop 1 tick beyond the opening range, target 2R, else flat 15:55. It is
the grid variant that held. The checks below were **added after the first look** and are labelled so.

| G1 at $500 a trade | Trades | Trades / week | Win % | PF | Net | $ / month | Max DD | Median stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026 H1 | 42 | 1.6 | 47.6 | 1.12 | +$926 | +$158 | -$2,708 | 151 pts |
| 2026 H2 | 28 | 1.8 | 39.3 | 1.18 | +$784 | +$217 | -$1,669 | 133 pts |
| 2025 | 96 | 1.8 | 54.2 | 1.71 | +$11,320 | +$962 | -$1,843 | 98 pts |
| 2021-24 | 277 | 1.7 | 45.1 | 1.24 | +$13,406 | +$352 | -$4,072 | 79 pts |

- **By year:** 2021 (2 months) +$63, 2022 +$3,250, 2023 -$369, 2024 +$10,462, 2025 +$11,320, 2026 +$1,710.
- **The new filter is the edge.**
  - The same gap fade at 10:00 without the failed-drive test loses in 3 of 4 spans (2021-25 PF 0.87, -$30.5k).
  - Trading WITH the gap when the drive held is +$9.0k in 2021-25 but negative in H2 and 2025.
- **Neighbours.** 192 of them: gap 0-0.4, range 15 / 30 / 45 / 60 min, 1.5R / 2R / 3R / the prior close, flat 12:00 or
  15:55.
  - 18 hold all four spans and 47 are positive in all four. 2025 is positive in 192 of 192, 2021-24 in 185, H2 in 80
    and H1 in 97.
  - The 15- and 30-minute ranges carry it. 45 / 60 minutes never hold. The 1.5R target holds most often (18 of 48).
- **Coin-flip placebo** (300 seeds, G1's own entry bars, the same stop distance and exits):
  - p = 0.003 over 2021-25 and over all years; 2025 0.013, 2021-24 0.067.
  - But 2026 is 0.22: H1 0.26, H2 0.29.
  - So the edge is real over 5 years, but 2026 alone cannot be told from luck.
- **Look-ahead:** all 459 signals rebuilt from bars cut right after 10:00: 0 differ.
- **Correlation (daily P&L):**
  - LIT 0.03 (2026) / -0.04 (2021-25). ATLAS -0.02 / 0.00. BLITZ 0.08 / 0.12.
  - Uncorrelated, as asked.
- **Why it cannot carry an eval:**
  - In 2026 the 09:30-10:00 range is about 145 points, so $500 of risk buys 1 micro.
  - It trades 1.7 times a week, below the owner's 2-4.
  - The MFFU 50K target ($3,000) then needs about 5 net 2R wins: median pass 27 sessions, 2-week pass 0% at $500.
    Sizing up to 70% of the room only reaches 7-8% in 2 weeks, and the 2-week fails rise to 3-7%.

## BLITZ: two new band angles (pre-registered, neither in the BLITZ write-ups)

Today's BLITZ reproduced exactly: $912 / $577 / $89 a month at $150, PF 1.63 / 1.49 / 1.06, as `scalp-na-mffu.md`. The
2026 halves are on 1m, 2021-25 on 5m, with the prior-day range filter on.

| At $150 a trade | H1 n / PF / $ a month | H2 | 2021-25 |
|---|---|---|---|
| Today (band = 09:30 open x (1 +/- sigma)) | 221 / 1.63 / $912 | 109 / 1.49 / $577 | 1,869 / 1.06 / $89 |
| Gap-aware band (Zarattini 2024: upper from max(open, prior close), lower from min) | 175 / 1.86 / $936 | 75 / 2.31 / $771 | 1,342 / 0.99 / -$15 |
| Implied-vol band (max(sigma, VXN's random-walk move to that minute)) | 118 / 1.76 / $585 | 54 / 0.99 / -$8 | 982 / 1.01 / $10 |

- The gap-aware band drops the breaks that point toward the gap fill. It is better in both 2026 halves, but in 2021-25
  it turns BLITZ from +$89 to -$15 a month. It is the same 2026-only pattern as every BLITZ change before it, so it is
  rejected.
- The implied-volatility band cuts too many trades and loses H2. Rejected.
- **BLITZ stays as built.** Its 2021-25 weakness is not fixed by any band choice tried here, or in the 72 + 430 + 120
  versions before (`2026-11-04_second_strategies_night.md`, `atlas-blitz-edge-2026-10-30.md`, `blitz-edge-2026-10-30b.md`).

## Honest limits

- **5m bars only**, so the 2026 1m data is not used, to keep both periods alike. A 1m entry might tighten G1's stop a little.
  The stop is the opening range itself, so the size problem stays.
- **ES starts 2025-04-14**, so the NQ/ES family is judged on 2026 + 2025 May-Dec only.
- **News days:** 8 FOMC and 12 CPI / NFP days a year cannot give 2 trades a week. They could only ever be a part of a
  book.
- **Added after the first look:** the G1 checks (controls, neighbours, placebo, years, sizes, the LIT add-on) came after
  the grid had shown the gap family. Picking G1 among 140 variants is itself a selection. The grid-level chance count
  (2 vs 0.75) says the grid as a whole is close to luck. Only the family-wide consistency and the 5-year placebo make G1
  worth watching.
- **2026 is the odd year.** LIT, ATLAS and BLITZ are all strong in 2026 and flat over 2021-25. G1 is the reverse: strong
  2024-25, weak 2026. A book of 2026 H1 picks makes +$1,654 a month in 2026 and loses -$709 a month over 5 years.
- The eval columns in the run library are at a fixed $500 a trade. The account tables use the div_stack / uprisk MFFU
  engines with room-based sizes (picked on H1).
- **Paper research only.** No live config, engine, UI, `live_model*.json` or `second_model.json` file was touched, and
  nothing was armed.

## Files and commands

- Code: `tools/e2_new_strats.py`.
  - `grid` runs the 140 variants and the chance level.
  - `gapdeep` runs G1's controls, neighbours, placebo, years and look-ahead check.
  - `slot` runs G1 on its own 25K / 50K.
  - `mix` runs G1 on LIT's funded 50K.
  - `blitz` runs the two band angles.
  - `save` stores the runs.
  - `cpicheck` checks the added CPI dates.
- Numbers: `research/second/e2_new_strats.json`.
- Runs: `e2_gapfade_g1` (promising), `e2_orb2_h1pick`, `e2_pdx_h1pick`, `e2_rs_h1pick`, `e2_gapf_h1pick`,
  `e2_vwr_h1pick`, `e2_eod_h1pick`, `e2_book_h1picks` (rejected).

## Next (proposals only, nothing switched)

1. Keep G1 as a paper-watch line: 1 micro and about 1.7 signals a week, so the 2026-27 sample can show whether the 2026
   weakness is luck (placebo p 0.22) or a change. It needs no money and no new account.
2. Do not buy a new eval account for any of these families. BLITZ keeps the third MFFU slot.
3. Write a new hypothesis family only once it has a new angle against this list and `docs/CLAUDE_REFERENCE.md` "Tested
   and rejected". The E2 families are added there.
