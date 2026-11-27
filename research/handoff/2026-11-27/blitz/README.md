# BLITZ readiness (day-blitzready 2026-11-27) - PAPER ONLY

**What BLITZ is:** the 3rd strategy, a 1-minute "noise area" scalp on NQ (`engine/blitz.py`, rules in `BLITZ_STRATEGY.md`). A 1m close
outside the 14-day noise band at 11:00-15:30 ET (only after a day whose range was >= 0.8 x the 14-day mean) = market entry at the next
open, stop 1.5 x 5m ATR, trail after +1R, out after 30 min / 15:55, 6 a day, -3R day stop.

**Why it was "off" on the PC feed:** BLITZ is hidden on every dashboard by the owner's rule (2026-11-15) and has no account (both Builder 25K
slots are used). Its in-bot paper shadow still runs, but its block is scrubbed from the feed, so p4 read "off (hidden, paper only)". Real money
stays the owner's switch; nothing here touches it.

**What now runs by itself:** `engine/blitz_paper.py`, started by the PC's 5-minute ops task (`ops_checks.blitz_paper_kick`), weekdays 09:25-16:05 ET,
detached BELOW_NORMAL, never twice, stops at 16:10 ET, honours the kill switch (`data/live_state.json` kill), off = `data/blitz_paper_off`.
It has no broker/adapter import, no account and no order path. It logs every paper trade once to `data/blitz_paper/trades.jsonl` and reports in
`data/blitz_paper.json`; the feed's p4 BLITZ turns "paper" while the report is fresh.

## Backtest (costs in: $1.90 a micro round trip, 1 tick on entry and on every stop/market exit; $150 a trade, at least 1 micro)

| Span | Trades/wk | Win | PF | Net | $/month | Max DD | PF with 1 more tick | 25K eval 2-wk pass / fail | median sessions to pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026 Jan-Jun | 8.5 | 56% | 1.63 | +$5,560 | +$934 | -$1,314 | 1.59 | 47.9% / 23.5% | 7 |
| 2026 Jul-Nov 26 | 8.3 | 53% | 1.41 | +$3,375 | +$689 | -$1,254 | 1.38 | 36.2% / 21.7% (Jul-Oct) | 5 |
| 2021-25 (5m bars) | 8.6 | 50% | 1.05 | +$3,765 | +$73 | -$5,512 | 1.01 ($18/mo) | 24.7% / 48.4% | 5 |

Honest read: BLITZ is a 2026 edge that was close to zero in 2021-25 (2024 lost money). Its own 25K slot is worth +$286 / +$52 / -$39 a month
(Jan-Jun / Jul-Oct / 2021-25) after every re-buy. 2021-25 and the eval paths are cited from `research/scalp/blitz_review.json` (5m only, no 1m
before 2026); 2026 is rebuilt today from `engine.blitz.backtest` on `data/NQ_1m.csv` and matches the Nov-18 review (221 trades, PF 1.63, -$1,314 DD).

## Forward gate (written before the first forward trade; same rule as `tools/of_ladder.py`: never loosened)

Step 0, paper forward (the PC lane): **40 trades** (~6 weeks), PF >= 1.30 at $150 a trade with costs, PF >= 1.15 with one more tick each way, mean >= +0.08R,
both halves net >= $0, max DD <= $1,500, every trade equal to a replay of the same bars. **Shelve** (no ask) if after 15 trades PF < 0.90 or net <= -$900, or DD > $1,800.
Passing means only that the owner may be ASKED about step 1 = BLITZ on a Sim account; real money needs Zlarior's 50K funded first.
Score it any day: `python -X utf8 tools/blitz_ladder.py` (rewrites `card.json`, writes `card_gate.json` only if the gate passed).
Honest limit: 40 trades cannot prove an edge (the 2026 PF could be luck); the gate only rules out a broken or negative BLITZ.

## Paper = backtest (the last sessions through the live path, one poll a minute, cold start)

`python -X utf8 -m engine.blitz_paper replay --last 3 [--active]`: the last 3 sessions (11-24, 11-25, 11-26) had **0** BLITZ trades (the range filter) = 0 in both,
so the check also runs the last 3 / 25 sessions that did trade: 13 of 13 and 102 of 102 trades equal `blitz.backtest` on entry, stop, exit time, price, kind (tests/test_blitz_paper.py).
