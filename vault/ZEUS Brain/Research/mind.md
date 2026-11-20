---
tags:
  - zeus/research
  - family/other
  - verdict/finding
  - bot/zlarior
  - bot/atlas
  - bot/blitz
type: "research"
date: "2026-10-29"
status: "finding - read-only; similar-setup memory does NOT predict outcomes out of sample (shown as context only); the trend-day model is weak but real (AUC 0.66 H2, 0.63 2021-25); the first self-research ..."
source: "research/writeups/mind.md"
aliases:
  - "Mind"
---

# Mind

> [!info] Verdict: finding
> finding - read-only; similar-setup memory does NOT predict outcomes out of sample (shown as context only); the trend-day model is weak but real (AUC 0.66 H2, 0.63 2021-25); the first self-research run rejected all 22 of its own ideas; nothing adopted

**Full title:** Mind - a thinking layer for Zlarior, ATLAS and BLITZ (similar-setup memory, regime and trend-day odds, game plans, trade reviews, self-research)

## Summary

Owner (2026-10-29) - "Give it a brain that's very smart. Can think for itself." engine/mind.py remembers every historical setup of each bot (631 Zlarior, 1,129 ATLAS, 330 BLITZ) with the features the live bot can compute, and for a live setup shows the nearest past setups (win %, average R, $ at today's size, 3 example days). Tested honestly (fit on 2026 H1, checked on 2026 H2 and 2021-25), similarity does not predict the outcome for any bot (2026 H2 rank correlation of predicted vs real R: Zlarior +0.00 - the setups it rated best made 0.30R less than those it rated worst -, ATLAS -0.25, BLITZ -0.05), so the dashboards show it as context only and it never claims confidence. With 5 years as memory (fit 2021-25) ATLAS similarity did separate 2026 (top third +1.7R / +1.8R vs bottom +0.5R / +0.2R, p 0.03 in each half), but the same check a year earlier (fit 2021-24, check 2025) shows nothing (+0.23R / +0.24R): not confirmed. A small logistic model gives the trend-day odds at 10:30 ET: AUC 0.66 on 2026 H2 and 0.63 on 2021-25; when it said >= 60%, 51% of 2021-25 days were trend days (base rate 33%). Mind writes an if-then game plan per bot at 01:45 / 10:45 ET, reviews every closed trade (grade, right / wrong, lesson, luck or skill) and runs a nightly self-research job that tests its own ideas on 2026 H1 (pick) / H2 (check) / 2021-25: the first run noticed 9 patterns, tested 22 size / skip rules (with its standing questions) and rejected all of them.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-29]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[BLITZ (paper)]]
- Runs: `none (no strategy change; research/mind/calibration.json, research/mind/proposals_seed.json)`
- Source: `research/writeups/mind.md`
- Back to [[ZEUS Home]]
