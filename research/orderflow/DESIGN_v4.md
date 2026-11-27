# Order flow v4: seven more tick features, pre-registered (written 2026-11-27 ~01:00 ET, BEFORE any v4 number was computed)

Research only, paper. Nothing here changes a bot, a size, a setting or an order. Script: `research/orderflow/of_v4.py`
(written after this file; this file is committed first, so the git history shows the rules came before the results).

## What I had seen before writing this (honest)
- The 51-day verdict (`real_verdict.md`): lane A taken 40 / +0.49R, skipped 53 / -0.31R, shuffle p 0.0065, halves differ;
  OF1-OF6 TOO FEW or REJECTED. The pulled days now number 53 (2026-09-27 .. 2026-11-26).
- The idea mill (`of_mill.py`, look 1) computes 48 related features (A1-A6 delta / CVD, B1-B11 footprint, C1-C6 blocks ...).
  I saw only the first few `mill_results.json` LIT rows (A1-A5: all "rejected"), nothing for lane A or for the definitions
  below. v4 does NOT reuse the mill's thresholds; its definitions are fixed here from common order-flow practice.

## Data
The PC's per-ET-day order-flow summaries (`engine/ofsum.py`): 5m bars (o h l c vol buy sell unk n b10 b20 b50 bth) and the 5m
footprint (volume at each tick, split buy / sell / unknown). Days with < 50,000 trades are dropped (`of_battery.MIN_ROWS`).
Futures only (NQ, quote-rule sides). No trade-level tape exists in the cloud: "large lots" = `bth` (signed volume of single
trades >= the 99.5th pct size of the 5 previous tick days, built on the PC), falling back to `b20` when `bth` is empty.

## The fixed feature set (7, no others; each gives a signed value s and a yes / no "pass")
Notation: d = trade direction (+1 long, -1 short); the REFERENCE bar = the sweep bar (the 5m bar holding the extreme the trade
fades); only 5m bars CLOSED at or before the entry are used (a reference bar still open at entry -> n/a). delta = buy - sell.
ext = the reference bar's low for a long, its high for a short. n/a = not computable -> the filter does not act (kept).

| id | name | definition | pass (favours d) |
|---|---|---|---|
| V1 | Stacked imbalances | In the reference bar's footprint: buy imbalance at tick k if a[k] >= 3 x b[k-1] and a[k] >= 10; sell imbalance at k if b[k] >= 3 x a[k+1] and b[k] >= 10. A stack = >= 3 consecutive imbalanced ticks of one side. s = d x (buy stacks - sell stacks). | s > 0 (initiative on the trade's side) |
| V2 | Delta divergence at the extreme | CVD (cumulative delta of the ET day, at bar closes). The previous extreme = the lowest low (long) / highest high (short) of the 12 bars before the reference bar. Divergence if the reference bar's ext is beyond it and the reference bar's closing CVD is HIGHER (long) / LOWER (short) than the CVD at the previous extreme bar's close. | divergence (n/a when the reference bar is not a new 12-bar extreme) |
| V3 | Absorption strength | AS = (bar volume / max(range in ticks, 1)) of the reference bar, divided by the median of the same over the 12 bars before it. | AS >= 1.5 (heavy volume, small range) |
| V4 | Large-lot prints | s = d x (bth of the reference bar + the bar before it); bth empty that day -> b20. | s > 0 (big single prints on the trade's side); s = 0 -> n/a |
| V5 | Delta slope into entry | The last 3 closed 5m bars before entry: s = d x sum(delta) / sum(volume). | s > 0 |
| V6 | VWAP location | Tick VWAP from the footprint (price x volume), anchored 09:30 ET when the reference bar opens at / after 09:45, else anchored at the day file's first bar. s = d x (VWAP - reference close). | s > 0 (buying below VWAP / selling above) |
| V7 | First-15-minute delta | delta / volume of the 09:30, 09:35, 09:40 bars. s = d x that. | s > 0 (with the opening flow); n/a for an entry before 09:45 |

## Three uses, each scored the same way
(a) **Filter on LIT**: Zlarior's backtest replay (`of_battery.lit_trades`, the live rules, costs in) trades whose sweep falls in
    a pulled tick day; reference bar = the 5m bar holding the sweep extreme (te floored to 5 minutes). Outcome = the trade's $.
(b) **Filter on lane A**: every resolved lane A candidate (`engine/of_paper.replay_summary`, DESIGN_paper.md, taken or not,
    outcome as if taken: R and $ at 1 micro, costs in); reference bar = the signal bar. Primary = all candidates; the TAKEN
    (absorbed) subset is shown as information only (no p).
(c) **Standalone signal** on every RTH bar opening 09:45-15:00 ET (one position per feature at a time, no overlap):
    V1 fires when a bar has stacks of one side only -> d = that side; V2 when a bar makes a new 12-bar low (high) with the
    divergence -> long (short); V3 when AS >= 1.5 on a bar that makes a new 6-bar low (long) or high (short) (not both); V4 when
    |bth| of the bar >= 10% of its volume -> d = sign; V5 when |3-bar delta / volume| >= 0.10 -> d = sign; V6 when the close is
    >= 1.0 x ATR(12 bars, 5m) away from VWAP (the first bar beyond) -> d = toward VWAP; V7 at the 09:45 bar open -> d = sign
    of the first-15 delta (once a day). Trade: enter at the next bar's open + 1 tick, exit at the open of the bar 6 bars
    later (30 minutes) - 1 tick, $1.40 commission, 1 micro ($0.50 a tick). No stop (fixed horizon; a research read, not a bot).

## Scores (fixed now)
- Filter (a, b): kept = pass or n/a. gain = mean outcome of kept - mean of skipped. p = one-sided label shuffle of pass / fail
  among the computable rows (5,000 shuffles). Halves = the older and newer half of the tick days (by day); gain in each.
- Standalone (c): mean $ per trade; p = one-sided sign-flip placebo of the directions (5,000 flips): does the direction carry
  information beyond drift? Halves as above.
- **Deflation: 21 tests (7 features x 3 uses). Holm-Bonferroni over the tests that reach their floor; the bar is adjusted
  p < 0.10.** Floors: (a) >= 20 LIT trades with a read, (b) >= 40 resolved candidates with a read, (c) >= 40 trades.
- **CANDIDATE** = floor met, adjusted p < 0.10, gain (or mean $) > 0 in BOTH halves, and for a filter it keeps >= 30% of trades
  and the kept trades' mean $ > 0 after costs. Otherwise **NO**, or **TOO FEW** under the floor. Expect TOO FEW for (a):
  ~20 LIT trades fall in 53 days.
- A CANDIDATE is only a reason to LOG the feature forward on the PC. The strategy-proof protocol (STRATEGY.md: both 2026 halves
  AND 2021-25) cannot be met with 53 tick days; no engine change follows from v4.

## The forward-logging ranking (LEAD_WIRES)
Rank the 7 by (1) verdict (CANDIDATE first), (2) the best raw p over (b) and (c) where the floor is met, (3) cost to compute live
in `engine/oflive.py` (standard library over the tick tail): cheap = running sums (V4, V5, V6, V7, V2), medium = per-price
buckets of one bar (V1, V3). Output: `research/orderflow/v4_results.json` + `v4_verdict.md` with the LEAD_WIRES list. The lead
wires; this helper changes no engine file.

## Addendum 2026-11-27 ~01:30 ET (after the history results, BEFORE any forward day exists): the forward watch list
History gave 0 CANDIDATES. Four reads earned forward watching (best raw p or both-halves sign); scored ONLY on tick days from
2026-11-27 on, rules above unchanged, Holm over these 4, bar adjusted p < 0.10 + the same sign as history:
- W1 = V7 inside lane A's TAKEN trades (kept = with the first-15 flow): gain R > 0. Floor 20 taken trades with a read.
- W2 = V6 standalone VWAP fade: mean $ > 0 (sign-flip placebo). Floor 40 trades.
- W3 = V5 lane A filter (all candidates): gain R > 0. Floor 40 candidates.
- W4 = V3 lane A filter (all candidates): gain R > 0. Floor 40 candidates.
No forward look changes a bot; a forward pass goes to the owner as a yes / no with the 2021-25 caveat (no ticks before 2026-09).
