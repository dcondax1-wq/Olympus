# Order flow as CONFLUENCE (management, not a skip filter) - pre-registered 2026-11-27 ~01:30 ET

Research only, paper. Written BEFORE the confluence replay saw a tick day (the battery look 1 already showed OF1 as a skip
filter cut good LIT trades: lane B all +$5,682 vs only-absorbed +$2,746). No rule or constant below changes after the first
run; a change is a new dated file. Script: `research/orderflow/of_confluence.py`, output `confluence_results.json` + `.md`.

## The question
Can order flow make LIT / ATLAS trades BETTER without cutting the winners? Every idea keeps (or nearly keeps) the trade list
and changes only entry timing, size or exit.

## Data
- Order flow: the 51 REAL NQ tick-summary days (2026-09-27 .. 2026-11-26) from `tools/data_pull.py --of`, read through
  `of_battery.find_days` -> `of_battery.Day` (5m bars with buy / sell / delta, footprint for the OF1 zone). A 5m OF bar is
  used only once CLOSED (its open + 300 s <= the decision time).
- Prices / trade path: TradingView NQ1! 1m (LIT, as the backtest) and the ATLAS engine's own 5m/1m path (`tools/second_md`).
- Trades = the exact live rules, re-run (twin engines):
  - LIT: `tools/lit_final.run(lit_adopt_combo.LIVE | t_check T15 | be_off)` = the live LIT (as `tools/second_mix`), only
    trades whose ET day has an OF day.
  - ATLAS: `tools/second_md.trades_of` with `md_best.json` params (the live MD) on today's bars, $500 risk
    (`q_usd`), only trades whose day has an OF day.
- Twin check: my own path walker must reproduce the baseline $ of every LIT trade (|diff| < $1) before any variant counts;
  ATLAS variants run through `second_md.sim_one` itself (force_t for exits, a later signal bar for entries).

## Frozen definitions
- ABSORBED bar (OF1, unchanged): zone = prices within 8 ticks of the bar's extreme on the push side (low for a long, high
  for a short), vz = zone volume, dz = zone buy - sell; absorbed = dz x dir < 0 and |dz| >= 0.20 x vz, bar >= 20 trades.
- HARD FLIP bar: a closed 5m bar after the fill with delta x dir < 0, |delta| >= 0.25 x bar volume, bar volume >= the median
  5m volume of that day's earlier RTH bars (or 09:30-on bars when before 09:30 there are none: then >= 0), and its close on
  the wrong side of the entry.
- NON-ADVERSE bar: a closed 5m bar with delta x dir >= 0.

## The ideas (each vs the same trades at baseline; costs in: LIT $1.40 / ATLAS $1.90 a micro + 1 tick slippage on market
## entries and exits)
- **C-a LIT entry timing**: after LIT's fill time, wait for the first closed OF 5m bar that is ABSORBED (in the trade's
  direction); enter at the next 1m open + 1 tick; same stop (1 tick beyond the sweep extreme), size = `lit.qty_for(new
  stop)` (size follows the stop), same target price (skipped if it is < 1R from the new entry), BE and the 15-minute check
  measured from the new fill. Window 30 min (6 bars). No absorbed bar, or stop / target touched first -> the trade is MISSED
  ($0 - a missed winner counts against the idea).
- **C-b LIT size up when absorbed**: the sweep-extreme 5m bar (the OF1 read, as the battery) absorbed -> 1.5 x micros
  (cap 40), else today's size. Never below today's size. Same trades, same path.
- **C-c LIT early exit on a hard flip**: before breakeven only, the first HARD FLIP bar closes -> exit at the next 1m
  open - 1 tick. (After BE the trade is already risk-free; no change.)
- **C-b2 ATLAS size up when absorbed**: the MD sweep-extreme bar absorbed (as OF4: lowest low / highest high of the 6 bars
  before entry) -> 1.5 x micros (cap 40).
- **C-c2 ATLAS early exit on a hard flip**: as C-c, through `sim_one(force_t=next bar after the flip)`; ATLAS has no BE, so
  it applies before +1R MFE (same "before BE" spirit: the 1R point).
- **C-d ATLAS delayed entry**: the signal bar j (CISD close). If bar j is NON-ADVERSE -> unchanged. Else move the signal to
  the first later NON-ADVERSE closed bar within 6 bars (30 min) and enter at its next open + 1 tick through `sim_one`
  (same stop; VIX target recomputed from the new entry; 6-80 pt stop and 1.5R rules apply). None -> MISSED. Also reported:
  entry price change in ticks (ties to ATLAS's 14-tick real-fill slippage).

## What is reported per idea
Trades (baseline / kept / missed / changed), total R, $ (baseline vs variant, paired gain), PF, win %, mean entry change
(ticks), and a 95% bootstrap CI of the $ gain (10,000 resamples of DAYS, seed 20261127); both halves of the 51 days (older /
newer) the same sign. **Bar for "candidate"**: gain > 0 in both halves, the bootstrap CI's lower end > -0 is NOT required
(n is too small to prove anything) - the verdict words are: CANDIDATE (both halves up), MIXED, WORSE, or TOO FEW (< 10
trades changed). Nothing here can pass the strategy protocol: 51 days are ~8 weeks inside 2026 H2 only; no Jan-Jun pick,
no 2021-25 check exists for tick data. A candidate goes to FORWARD LOGGING (LEAD_WIRES below), never to a live change.

## LEAD_WIRES (forward logging: cheap fields, so each idea can be scored in 2-3 months)
Written in `confluence_results.md` after the run, as the list of per-trade fields the PC must store.
