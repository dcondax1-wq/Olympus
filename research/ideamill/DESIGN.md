# IDEA MILL: pre-registered protocol (written 2026-11-24/25 BEFORE any idea was scored)

PAPER RESEARCH ONLY. Nothing here trades, sizes, arms or edits a live file. Owner: "I want the brains to learn every idea in
the world, not just popular ones". Code: `research/ideamill/grammar.py` (the ideas), `tools/ideamill.py` (runner),
`research/ideamill/harvest.py` (literature). Every trial ever scored is appended to `research/ideamill/trials.jsonl`
with the running trial count (no silent drops); `summary.json` = the latest gate counts (read by the Brain).

## 1. Sources
(a) **Grammar** = trigger x direction x session window x filter x stop x exit, each a small pure function on NQ futures bars
    (data/NQ_5m.csv + NQ_1d; VIX_1d; GEX_1d; ES_5m where it exists). Triggers: prior-day high/low sweep (wick through, close
    back) and break (close through); prior-week high/low sweep / break; opening-range (09:30-10:00) break / fade; overnight
    high/low sweep; gap (RTH open vs prior close) fill / go; VWAP (session) cross; VWAP 2-sigma band fade; 100-point round
    number reclaim; displacement candle (body >= 1.5 x 5m ATR) continuation / fade; FVG (3-bar gap) retest; inside-bar break;
    volume spike (>= 3 x 20-bar median) continuation / fade; EMA 20/50 cross; RSI(14) < 20 / > 80 reversal; NR7 day
    (prior day) opening-range break; ES/NQ divergence at the prior-day level (ES lags the NQ sweep). Windows: Asia 18-02,
    London 02-08, NY AM 08-11:30, NY PM 11:30-15:30, all 02-15:30. Filters: none; 20-day trend with / against; prior VIX
    < 20 / >= 20; prior-day GEX above / below its 60-day median; day of week (Mon, Fri) on / off. Stops: 1 tick beyond the
    trigger bar's extreme (structure) or 1 x 5m ATR14. Exits: 1R / 2R / 3R target, else flat 15:55; also "time" = 12 bars.
    Ideas whose data does not cover discovery (ES before 2025-04) are logged "untestable", never silently dropped.
(b) **Literature** (--harvest, weekly): arXiv q-fin (TR, ST, PM, CP) API + NBER new working papers RSS: free, no login. A
    keyword / regex pass maps an abstract to a grammar family (momentum, reversal, overnight / intraday, opening range,
    moving average, volatility / VIX, volume, calendar, gap) -> a queued grammar idea tagged with the paper; anything it
    cannot map goes to `research/ideamill/needs_human.json`. No LLM, no paid service.
(c) **Already tested** (docs/TESTED_AND_REJECTED.md): each dated entry is registered with its date; it is "due" for a re-run
    only when the data has grown >= 60 sessions past that date (report only; their bespoke code is re-run by a human / helper).

## 2. Protocol (frozen)
Entry at the next bar's open after the trigger bar closes; one position at a time per idea; max 1 trade a day per idea; flat
15:55 ET; a bar touching stop and target = stop. Costs per trade: 1 tick slippage on entry + 1 tick on the stop / flat exit +
$1.90 a micro round trip = **1.45 points**, net R = (points - 1.45) / stop points; stops under 4 points are skipped.
Spans: **DISCOVERY = 2021-11-01 .. 2024-12-31**; HOLD-OUTS untouched until an idea passes discovery: **2025**, **2026 Jan-Jun**,
**2026 Jul-Oct 16**; then **FORWARD PAPER** = only sessions after the data the idea was confirmed on (new days).
Gates, in order (an idea's status = the last gate passed):
- G0 data: >= 100 discovery trades (else "too few").
- G1 discovery: mean net R > 0; one-sided p from a **moving-block bootstrap** of the idea's daily net-R series (block 5 days,
  1,000 draws, null = the demeaned series); **Benjamini-Hochberg FDR q = 0.10 over EVERY idea ever scored** (the trial count
  in trials.jsonl, not just this batch).
- G2 haircut: **Deflated Sharpe Ratio** (Bailey & Lopez de Prado) of the daily net-R series, with N = all trials ever, >= 0.95.
- G3 hold-outs: mean net R > 0 AND PF >= 1.10 in EACH of 2025, 2026 H1, 2026 Jul-Oct, with >= 10 trades in each.
- G4 forward paper: >= 20 new trades after confirmation with mean net R > 0 -> only then "needs-owner-yes" (and the full
  CLAUDE.md proof on the real engine, eval odds included, before any card).
Journal statuses (research/learn/journal.json, pillar "market", lens "idea mill"): G1+G2 = "watching", G3 = "paper",
G4 = "needs-owner-yes", a later failure = "rejected".
Luck control reported every run: expected false survivors at G1 under BH (<= q x discoveries) and the empirical count from a
**sign-flip placebo batch** (the same ideas with each trade's R sign randomly flipped) pushed through G1-G3.

## 3. Runners
`python -X utf8 tools/ideamill.py --batch N` (nightly light: N grammar ideas not yet tried, no network, time cap 20 min),
`--harvest` (weekly, network), `--report`. Optional step in `tools/market_learn_weekly.py --nightly --ideamill N` (off by
default; skipped when over its time cap). An idea already in trials.jsonl is never re-scored on the same data end date.

## Addendum v2 (2026-11-25 01:15 UTC, committed BEFORE the v2 run; v1 rows stay in trials.jsonl, marked proto 1)
1. **Bug in v1 G1 (found after the v1 batch, fixed before any re-score):** with 1,000 bootstrap draws the smallest possible p
   is 1/1,001 = 0.001, while BH over ~7,000 scored ideas needs p <= 0.10 / 7,000 = 0.000014 for the best idea: G1 could never
   pass, whatever the edge. v2 p = the normal tail of the observed mean over the block-bootstrap standard error of the mean
   (same moving-block bootstrap, 1,000 draws, block 5): p = 1 - Phi(mean / SE_boot). Every other gate unchanged.
2. **The day-of-week filters the protocol listed but v1's code left out are added:** "no_mon", "no_fri".
3. **Timeframes:** the same grammar on 15m and 1h NQ bars (data/NQ_15m.csv, NQ_1h.csv; the 09:30-10:00 opening range does not
   exist on 1h bars, so those ideas log "too few"). 1m bars exist only from 2026: not testable in discovery, not run.
4. BH and DSR count EVERY v2 trial ever (proto 2 rows); v1 rows are kept for the record and not counted twice.

5. Format: the trial log is research/ideamill/trials.jsonl.gz (gzip members appended per run; same rows; 22 MB -> 1.9 MB).
