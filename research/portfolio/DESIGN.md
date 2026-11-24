# 24-hour coverage + walk-forward PORTFOLIO search: pre-registration (written 2026-11-24 BEFORE any hold-out number)

PAPER RESEARCH ONLY. Owner: "24/7 trading, more strategies, smarter, time and price, confluence". Code
`research/portfolio/coverage.py`, `research/portfolio/portfolio.py` -> `coverage.json`, `results.json`; write-up
`research/writeups/portfolio-2026-11-24.md`.

## (1) Coverage map (descriptive)
Every 30-min ET slot of the CME week (Sun 18:00 - Fri 17:00): which live strategy can enter there (LIT: live_model window
02:00-15:30, flat 15:55; ATLAS members and BLITZ: the span of their real backtest entry times), and each pillar's backtest
trades and $ in that slot (research/learn/lessons.jsonl.gz, costs in, 2021-25 + both 2026 halves). MFFU limits on the same
grid (docs/ACCOUNT_RULES.md): 16:10 auto-close + 17:00-18:00 closed; the bot is flat 15:55; the Rapid FUNDED news ban
(+-2 min, FOMC / minutes / jobs / CPI); the daily soft loss ($1,000 50K / $600 25K / $500 Rapid option).

## (2) Portfolio search
Pool: every stored run in research/runs/*.json with a daily series covering 2021-11 .. 2026-10 (the Lab's tested strategies,
filters and variants, costs in). Daily rows = (date, pnl, low, trades).
Spans: **PICK** = 2021-11-08 .. 2024-12-31 + 2026-01-01 .. 2026-06-30. **HOLD-OUTS, untouched until the pick is frozen:**
**2025** and **2026-07-01 .. 2026-10-16** (the stored runs end Oct 16; Jul-Nov is not available as one series).
Core (today): LIT = run `lit_live` + ATLAS = run `atlas_funded_live`, as stored.
Candidate rule, computed on PICK only:
- >= 100 trades in PICK, PICK net > 0 and PF >= 1.10;
- daily $ correlation with LIT and with ATLAS (PICK, all sessions) < 0.30 (so it is not a LIT / ATLAS variant);
- each candidate is scaled to a common unit: its PICK daily $ stdev = 25% of LIT's PICK daily stdev;
- greedy: start from the core; add the candidate that most raises the PICK daily Sharpe (mean / stdev of the summed daily $);
  skip a candidate with daily corr > 0.60 to a member already added; stop after 6 adds or when the Sharpe gain < 0.005.
Shared risk budget, daily level: a day's summed low <= -DLL -> that day's $ = -DLL (the soft daily loss pauses the account).
One-position-at-a-time cannot be enforced from daily rows: stated as a caveat (it can only remove trades, so the numbers are an
upper bound); a pass needs the trade-level replay before any yes.
Evals, daily (pnl, low), rolling start on every session of the span: Builder 50K (target $3,000, MLL $2,000 trailing EOD,
lock $100, DLL $1,000), Builder 25K (x0.5 size: $1,500 / $1,000 / $600), Rapid EOD 25K (x0.5: $1,500 / $1,000 / $500, best day
<= 30% of the profit, 4+ days): pass % / fail % within 10 and 40 sessions, median days to pass.
Gate (both hold-outs): portfolio net $ > core, PF >= core, max DD no deeper than 1.25 x core, 50K 40-session pass % >= core and
fail % <= core + 2 pts, 2-6 trades a week from the add-ons combined. Pass -> needs-owner-yes with the members and sizes. Else
the verdict is "no portfolio beats today", with the numbers.
Time x price members: only runs already in the pool (session / level variants the Lab built); none newly designed here.
