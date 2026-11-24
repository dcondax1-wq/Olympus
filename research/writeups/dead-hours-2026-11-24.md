# Dead hours per pillar: are 05:00-06:30 and 11:00 really bad? (2026-11-24)

PAPER RESEARCH ONLY. Rules first: `research/hours/DESIGN.md` (committed before any hold-out). Code `research/hours/hours.py`
-> `results.json`. Trades = each pillar's own backtest (research/learn/lessons.jsonl.gz, costs in). Windows picked on
**2021-11 .. 2024 only**, then scored untouched on **2025, Jan-Jun 2026, Jul-Oct 2026**. Placebo = 2,000 random windows of
the same length inside the book's hours.

## Verdict: 0 of 4 windows pass. The coverage map's bad hours are in-sample noise. Nothing to switch off.

| Book | Dead on 2021-24 (n, PF, $) | 2025 | Jan-Jun 2026 | Jul-Oct 2026 | Placebo p | Verdict |
|---|---|---|---|---|---|---|
| LIT | 02:00-03:00 (27, PF 0.01, -$7,587) | $3,210 -> $5,690 | **$33,901 -> $23,768** | **$9,919 -> $4,710** | 1.00 | FAIL: the "dead" hour made $15.3k in 2026 |
| ATLAS EMA | 05:30-07:00 (69, PF 0.14, -$11,204) | -$1,724 -> -$708 | $9,511 -> $10,029 | $4,890 -> $4,034 | 0.37 | FAIL |
| ATLAS MACD | 02:30-03:00 (25, PF 0.53, -$2,298) | $3,897 -> $5,090 | $9,873 -> $9,672 | $1,647 -> $2,033 | 0.057 | FAIL (Jan-Jun -$201, p just over 0.05) |
| ATLAS S/R | 11:00-12:00 (47, PF 0.62, -$3,397) | $3,103 -> $4,112 | $6,354 -> $6,622 | $1,691 -> $1,706 | 0.25 | FAIL: better in all 3, but tiny in 2026 and no better than a random hour |
| BLITZ | none (no window met PF < 0.8 with 20+ trades) | - | - | - | - | - |

What it means:
- LIT shows why picking hours on the past is dangerous: its worst 2021-24 hour became one of its best in 2026.
- The coverage map's -$7.0k at 05:00-06:00 / -$6.8k at 06:30 is mostly ATLAS EMA in 2021-24 (the pick found it: -$11.2k),
  and it does not hold in Jul-Oct 2026.
- ATLAS S/R after 11:00 is the only one pointing the right way in every hold-out (+$1,009 / +$268 / +$15). The 2026 gain is
  small and a random hour does as well 25% of the time. Watch only.
Caveats: trade-list test (LIT is one trade a day, so a skip could free a later trade); $ at each book's stored size; the
lessons rows end Oct 16.
