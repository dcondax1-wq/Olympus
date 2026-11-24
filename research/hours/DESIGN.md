# Dead hours per pillar: pre-registration (written 2026-11-24 BEFORE any hold-out number)

PAPER RESEARCH ONLY. Lead's question after the coverage map (05:00-06:00 -$7.0k, 06:30 -$6.8k, 11:00 -$5.1k, 3 pillars, in-sample).
Code `research/hours/hours.py` -> `research/hours/results.json`; write-up `research/writeups/dead-hours-2026-11-24.md`.

Trades: research/learn/lessons.jsonl.gz (the pillars' own backtests, costs in, $ as stored), 5 books: LIT, ATLAS EMA,
ATLAS MACD, ATLAS S/R, BLITZ. Slot = the ET half hour of the entry.
**PICK = 2021-11-01 .. 2024-12-31 only.** HOLD-OUTS untouched until the windows are frozen: **2025**, **Jan-Jun 2026**,
**Jul-Oct 2026** (the lessons rows end Oct 16).
Rule (one window per book, at most 5 windows):
- candidate windows = 1, 2 or 3 consecutive half-hour slots inside the book's own entry hours;
- a window is DEAD on PICK when it has >= 20 trades, PF < 0.80 and a net loss;
- per book pick the dead window with the most negative PICK $ (ties: the shorter one); none -> no window for that book.
Each window becomes "skip that book's entries in it" (trade-list test; LIT is one trade a day, so a skip could free a later
trade: the full replay is the yes step).
Scored per book and for all chosen windows together, on each hold-out: trades/week, PF, net $, $/month, max DD; daily-level
evals (research/portfolio/portfolio.evals) for Builder 50K / 25K (x0.5) / Rapid EOD 25K (x0.5).
Placebo: for each book, 2,000 random windows of the same length inside its entry hours; p = share whose skip gains at least as
much $ as the chosen window, summed over the three hold-outs.
**Pass (per window) = net $ better in ALL THREE hold-outs AND placebo p < 0.05.** A pass -> needs-owner-yes with the exact
window. Otherwise: variance / in-sample.
