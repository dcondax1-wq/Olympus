---
title: Eval sizing: can the eval's own state pass more MFFU evals?
family: risk
date: 2026-10-17
status: rejected
summary: Sizing from the eval's state (cushion above the trailing max loss, profit, distance to the target) cuts eval fails a lot (2021-25 1-month fails 9.6% to 1-2%), but it also passes fewer evals a year and leaves 40-50% of evals stuck after 3 months, and the result depends on the exact threshold. None beats fixed sizing robustly; the recommended cold-streak / late-entry sizing improves evals more (2.63 evals bought per pass in 2021-25 vs 3.89).
runs: baseline, risk_eval_cap50, risk_eval_cap100, risk_eval_prop1000, risk_eval_prop1500, risk_eval_prop1000_qty, risk_eval_bank, risk_eval_presslock, risk_eval_pressup, risk_eval_defend, risk_eval_prop1000_usd1000, risk_eval_prop1000_usd1200, risk_pkg_q25_prop1000, risk_usd600, risk_usd1000, risk_pkg_q25_late_live
---

## The question

The MFFU Builder 50K eval has three rules:
- pass at **+$3,000**
- fail if the balance touches the **trailing max loss**: $2,000 below the best end-of-day balance, checked during the day against the worst open loss, and locking at $50,100
- a soft **$1,000 daily limit**

Can the bot size each trade from where the eval stands, instead of the same way every time? The inputs are:
- the cushion above the trailing max loss
- the profit so far
- what is still needed to reach the target

The goal is to pass more evals and fail fewer.

## How it was tested

- **Simulator:** a new eval simulator that copies the dashboard's MFFU rules exactly, including the soft daily limit.
  - With fixed sizing it gives the same pass/fail numbers as the dashboard for every period.
  - Each trade is sized from **that eval's own balance and floor at entry**, separately for every start day.
- **Same trades as the live strategy:** the exact live-loop replay, costs included, the cold-streak half size kept.
- **Each eval rule is applied** to the $ risk before it is turned into micros. Two limits:
  - a setup the engine takes always gets at least 1 micro
  - no setup is ever skipped
- **Measured:**
  - pass / fail within 2 weeks, 1 month and 3 months, for an eval started on every trading day
  - back-to-back evals, a new one after each pass or fail, started from 20 different first days and averaged: passes and fails per year
  - **evals bought per pass**: what each funded account costs in eval fees

## Results

| run | rule | 2026 2w pass/fail % | 1m | 3m | passes / fails a year | 2021-25 2w pass/fail % | 1m | 3m | still open after 3m | median days to pass | passes / fails a year | evals bought per pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | Live sizing | 20/0 | 30/0 | 54/20 | 5.5/1.4 | 4.1/2.1 | 8.8/9.6 | 22/59 | 19% | 34 | 1.5/4.3 | 3.89 |
| risk_eval_cap50 | Never risk more than half the cushion | 20/0 | 30/0 | 52/0 | 5.4/1.4 | 4.0/0.0 | 7.6/0.9 | 23/25 | 52% | 64 | 1.25/2.2 | 2.75 |
| risk_eval_cap100 | Never risk more than the whole cushion | 20/0 | 30/0 | 54/16 | 5.5/1.4 | 4.1/1.7 | 9.0/5.9 | 27/44 | 29% | 47 | 1.0/3.1 | 4.09 |
| risk_eval_prop1000 | Size down once the cushion is under $1,000 | 20/0 | 30/0 | 54/7 | 5.5/1.4 | 4.1/0.1 | 8.3/2.1 | 27/33 | 40% | 46 | 1.25/2.4 | 2.89 |
| risk_eval_prop1500 | Size down once the cushion is under $1,500 | 20/0 | 30/0 | 52/0 | 4.9/0.9 | 4.0/0.0 | 7.1/0.3 | 23/20 | 58% | 55 | 0.7/2.1 | 3.88 |
| risk_eval_prop1000_qty | Same as prop1000, applied to the routed micros | 20/0 | 30/0 | 54/0 | 5.4/1.3 | 4.1/0.1 | 7.9/1.4 | 26/31 | 43% | 51 | 1.25/2.4 | 2.89 |
| risk_eval_bank | Bank the pass: from +$2,000, risk at most half of what is still needed | 18/0 | 30/0 | 54/20 | 5.5/1.4 | 4.0/2.1 | 8.3/9.3 | 22/59 | 20% | 36 | 1.5/4.1 | 3.73 |
| risk_eval_presslock | x1.5 once the floor has locked at $50,100 | 20/0 | 30/0 | 54/20 | 5.5/1.4 | 4.1/2.2 | 9.0/10.6 | 22/60 | 17% | 31 | 1.5/4.5 | 3.98 |
| risk_eval_pressup | x1.25 while the eval is in profit | 23/0 | 34/0 | 54/22 | 7.2/1.4 | 4.7/3.1 | 9.4/13.1 | 20/64 | 16% | 29 | 1.8/5.0 | 3.76 |
| risk_eval_defend | x0.67 while the eval is below $50,000 | 12/0 | 26/0 | 52/2 | 5.5/0.9 | 3.2/0.3 | 6.9/3.6 | 24/31 | 46% | 41 | 0.7/2.5 | 4.42 |
| risk_eval_prop1000_usd1000 | Risk $1,000 + size down under a $1,000 cushion | 23/0 | 36/0 | 54/17 | 7.2/1.4 | 5.0/2.7 | 9.3/8.4 | 28/44 | 28% | 40 | 0.8/3.3 | 5.08 |
| risk_eval_prop1000_usd1200 | Risk $1,200 + size down under a $1,000 cushion | 28/0 | 44/0 | 52/24 | 6.9/1.4 | 5.5/5.2 | 10.4/16.3 | 19/63 | 18% | 19 | 1.55/5.4 | 4.48 |
| risk_usd600 | Risk $600 (engine replay) | 9/0 | 26/0 | 44/0 | 5.3/0.0 | 1.8/0.6 | 4.2/1.5 | 18/34 | 47% | 57 | 0.7/2.3 | 4.07 |
| risk_usd1000 | Risk $1,000 (engine replay) | 23/0 | 36/0 | 54/33 | 7.3/1.4 | 5.1/6.5 | 8.6/20.9 | 18/73 | 9% | 21 | 2.2/6.5 | 3.92 |
| **risk_pkg_q25_late_live** | **Recommended: cold streak x0.25, late entry x0.5** | 21/0 | 32/0 | 54/0 | 5.6/0.9 | 4.0/1.9 | 8.7/5.2 | 31/28 | 41% | 39 | 1.5/2.5 | **2.63** |

2026 has only 198 sessions, so its 3-month and per-year numbers rest on few evals. Read 2021-25 first.

## What it means

**Protecting the cushion works against fails.** Examples are "never risk more than half the cushion" and "size down once the cushion is under $1,000".
- In 2021-25 the 1-month fail rate falls from 9.6% to 0.1-2%, and 3-month fails from 59% to 20-33%.
- 2026 3-month fails fall from 20% to 0-7%.
- The 2-week and 1-month pass rates barely move.

**It does not create passes.** The evals that would have failed do not pass instead: they get stuck.
- The account trades 1 micro just above the floor for months.
- 40-58% of evals are still open after 3 months, against 19% today.
- The median days to pass go from 34 to 46-64.
- Back-to-back, it passes fewer evals a year (1.25 or less vs 1.5).

**The result depends on the exact threshold.** With the quarter cold size, the evals bought per pass for each cushion threshold are:

| threshold | evals bought per pass |
|---|---:|
| $500 | 3.45 |
| $750 | 3.37 |
| $1,000 | 2.47 |
| $1,250 | 2.87 |
| $1,500 | 3.22 |

Only one setting is better than no cushion rule (2.91), so it is not reliable.

**Bank the pass and press after the lock change almost nothing.** The bot's typical risk ($213-239) is already small next to what is still needed when the eval is close. Few evals reach the lock without passing.

**More risk makes evals faster, not cheaper.**
- At $1,000 the bot passes 36% of evals within a month in 2026, against 30%.
- In 2021-25 it fails 21% within a month, against 10%.
- Per pass it costs the same number of evals: 3.92 vs 3.89.
- Less risk ($600) is slower, drops 2026 to 2.09 setups a week, and costs more evals per pass (4.07).

**The edge decides the eval, not the eval rule.** The recommended change (risk-summary.md) improves the evals more than any eval-state rule:
- 2.63 evals per pass in 2021-25, against 3.89
- same passes a year
- 1-month fails 5.2%, against 9.6%
- 3-month fails 0% in 2026

It does this by cutting the trades that lose (cold streaks, late entries), not by watching the account.

## Verdict

- **Rejected for now.** No eval-state rule beats fixed sizing in both periods once passes, fails and time are all counted.
- **Not ruled out later.** If MFFU evals have no time limit and no monthly fee, "size down once the cushion is under $1,000" is worth a second look. It turns many fails into slow evals that are still alive. It only needs the account balance and the best end-of-day balance, so it would fit the Pine script.
