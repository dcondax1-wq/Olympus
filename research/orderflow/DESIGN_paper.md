# Order Flow pillar, the PAPER bot - pre-registered rules (written 2026-11-26, BEFORE it saw a live or recorded tick day)

PAPER ONLY. `engine/of_paper.py` never routes, sizes or changes an order or a live setting; it imports no broker / adapter /
NinjaTrader / live-loop module (tests check it). It reads the live tick file LE_TickRec writes
(`Documents\NinjaTrader 8\le_ticks\NQ_<ET day>.csv`), the depth file when it exists (`le_ticks\depth\NQ_<ET day>.csv`) and the
bot's own `data/live_state.json` (kill flag, LIT's ledger) - read only - and writes only `data/of_paper.json` (+ its cache
`data/of_paper_cache/`), both gitignored. Why these rules: `LITERATURE.md` ranks (#2) "LIT sweep context, absorbed vs cascade"
as the only directional order-flow idea that fits a 5-minute clock, and (#1) entry timing from the book's queue / OFI as the
biggest $ lever once depth exists. Frozen with this commit: no rule or constant below changes after the first live day; a change
is a new dated file.

## How it reads the market (identical to the research by construction)
Each run: the day's live CSV -> `engine/tickrec.read_rec_csv` (quote rule, tick rule fallback, filled-in quotes dropped) ->
`engine/ofsum.summarize` (the SAME 5m bars + footprint the nightly research uses) -> `of_battery.Day` / `of_mill.Ctx` ->
`of_mill.features` + `of_v3.features` (v2 + v3 readings). A 5m bar counts only once CLOSED (the run's clock >= its open + 300 s
and a later trade exists or the clock is >= open + 330 s). The previous tick day (levels) = the same chain on its CSV / stored
ticks, cached once a day.

## Lane A - "LVL-OF": the pillar's own paper trades (absorbed level fade)
- **Candidates** = DESIGN2.md's `LVL` entries, unchanged: levels = prior-day RTH high / low and Globex (18:00-09:30) high / low
  (`of_battery.levels`), + the RTH opening-range (09:30-10:00) high / low from 10:00; 09:45-15:00 ET bar opens; a closed 5m bar
  trades >= 1 tick through the level and closes back on the other side -> a fade (short at a high, long at a low); one signal per
  level per day; one paper position at a time (a signal while a position is open is logged "busy", not taken).
- **The order-flow gate (frozen = OF1 / PREREG_ticks constants):** take the signal only when the signal bar was ABSORBED at
  its extreme on the push side: zone = prices within 8 ticks of that bar's extreme, vz = zone volume, dz = zone buy - sell;
  absorbed = dz x d < 0 and abs(dz) >= 0.20 x vz (the bar needs >= 20 trades). Not absorbed / untested -> logged "skipped: not
  absorbed", with its outcome tracked as if taken (the counterfactual the forward harness compares).
- **Execution (paper):** decision at the run that first sees the signal bar closed; fill = the first trade at / after the decision
  + 1 tick against us (in a replay the decision is the bar close, so the fill = the next bar's open + 1 tick = `of_study._sim_df`).
  Stop = 1 tick beyond the signal bar's extreme (a stop fill 1 tick worse); target 2R; flat at the close of the last bar opening
  <= 15:55 ET; checked on closed 5m bars (stop first when one bar touches both), as `_sim_df`.
- **Size and $:** R is the unit. $ shown two ways: 1 micro MNQ ($0.50 a tick, $1.40 round trip - the pillar's real scale) and the
  research's $500-risk size (`_sim_df`: micros = 500 // (risk x $2), 1..40) for comparison with the battery.
- **Kill / off:** `data/live_state.json` "kill": true (the owner's kill) -> no new paper entry and an open paper position is closed
  at the next trade ("KILL"); `LE_OFPAPER=0` or the file `data/of_paper_off` -> nothing runs. Outside 09:25-16:10 ET weekdays: no
  run.

## Lane B - "LIT-OF": the OF1 filter on Zlarior's real entries, in paper
For each LIT entry in the bot's ledger today (`engine/oflive.lit_trades_of`): the OF read at its sweep (the lowest-low / highest-
high closed 5m bar of the 6 before entry, OF1 rule) -> "take" (absorbed) or "skip". Outcome = LIT's own realized $ when the trade
closes. Nothing is changed on LIT; this only records what the filter WOULD have done, trade by trade.

## Lane C - entry timing from the book (logged only; depth days)
For every Lane A decision when a depth file exists: the best-queue imbalance and CKS OFI at the decision (DESIGN3 L1 / L2
definitions) and the "wait for the book" alternative: within 60 s after the decision, the first snapshot whose best-queue
imbalance leans our way (bid queue > ask queue for a long, mirror for a short) -> its touch price (ask for a long, bid for a short);
none within 60 s -> the price at +60 s. Logged: ticks better (+) or worse (-) than the paper fill. It never changes the paper trade.

## What is logged (for the forward harness, tools/forward_paper.py, and the learner)
Every candidate (taken, skipped, busy) as one decision row: id, lane, day, signal bar time, level name / price, d, the gate read
(vz, dz, absorbed), all v2 + v3 readings, decision time, fill, stop, target, and once resolved: exit time / price / why, R,
$ at 1 micro, $ at the research size, Lane C timing. Rows are never rewritten after they are resolved.

## Scoring (the forward protocol, nothing before)
The paper bot proves nothing on its own; tools/forward_paper.py scores it on days after this commit only. The pillar's question is
written now: over >= 40 resolved Lane A candidates, is mean R of TAKEN > mean R of SKIPPED (one-sided permutation p < 0.10, both
halves of the days the same sign) and TAKEN mean R > 0 after costs? Lane B: over >= 20 LIT trades, does "take" beat all-trades in
$? Until then the Brain says the counts in plain words and "too few".
