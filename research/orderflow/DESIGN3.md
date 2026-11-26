# Order-flow feature set v3 + the learning loop - pre-registered design 3 (written 2026-11-26, BEFORE any tick data reached the cloud)

Research only, paper. Nothing here trades, sizes, arms or changes a live setting. Why v3: `LITERATURE.md` (same folder) ranks what
the published work says order flow can predict at OUR horizon (one 5m bar to a few hours, 1-5 min decision latency, 1 micro).
v2 (DESIGN2.md, 49 features A-H) is mostly practitioner footprint reads. v3 adds the few features with academic backing that
v2 does not already cover: price impact / Kyle's lambda (I), flow toxicity and trade-sign persistence (J), stop-run dynamics at
the swept level (K), and the best-quote queue / order-flow imbalance (L, depth: forward only). DESIGN.md, DESIGN2.md and
DESIGN_forward.md stay exactly as they are; this file ADDS groups and a learner. Code: `research/orderflow/of_v3.py` (features),
`research/orderflow/of_learn.py` (learner), `research/orderflow/of_sim.py` (synthetic tick simulator with planted effects; the
pipeline proof). Frozen with this commit: no formula, constant or threshold below changes after the first look at real days.

## Decision time and sign (same as DESIGN2)
Every feature uses only 5m bars CLOSED before the entry bar i (k-1 = the last closed bar). d = +1 long / -1 short. Signed features
are multiplied by d, so "high" = order flow agrees with the trade. `ext` = the sweep-extreme bar the entry family supplies (LIT:
the bar starting at the trade's `te`; ATLAS MD: the lowest-low / highest-high closed bar of the 6 before entry; LVL: the signal bar).
`lvl` = the swept level when the family knows it (LVL only), else none. V = bar volume, Dl = buy - sell (aggressor delta),
r(j) = c(j) - c(j-1) in points. med20(x) = median of x over the 20 bars before i (>= 5 needed, else NaN). NaN = not computable;
a filter keeps a trade whose feature is NaN, a stand-alone skips it (DESIGN2 rule).

## New per-bar columns (engine/ofsum.py, additive; old readers ignore them; NaN / empty on days built before this commit)
- bars5m `sac`: lag-1 autocorrelation of the trade SIGNS (side +1 / -1, unknown dropped) inside the bar, in trade order; empty
  when the bar has < 20 signed trades. `sruns`: number of sign runs / signed trades (low = long one-sided runs).
- depth5m `imb1`: mean over the bar's snapshots of (bs1 - as1) / (bs1 + as1) (best bid / ask queue sizes).
  `ofi`: Cont-Kukanov-Stoikov order-flow imbalance summed over the bar's consecutive snapshot pairs,
  e = 1{Pb' >= Pb} qb' - 1{Pb' <= Pb} qb - 1{Pa' <= Pa} qa' + 1{Pa' >= Pa} qa (P = best price, q = its size, ' = the later
  snapshot). `dep1`: mean (bs1 + as1) / 2.

## The 13 v3 features
| # | Group | Feature (exact) | Literature |
|---|---|---|---|
| I1 | impact | Kyle's lambda now vs today: lam(i) = OLS slope of r(j) on Dl(j)/1000 over j in [i-24, i-1] (>= 12 bars), divided by the median of lam over the day's bars so far that have one (>= 5), unsigned. High = thin market | Kyle 1985, Hasbrouck 1991 |
| I2 | impact | impact residual of the push INTO the extreme: over w = [ext-2, ext] (bars < i), res = sum r(j) - lam(i) x sum Dl(j)/1000, signed -d and / ATR5. + = price moved LESS against the trade than the aggressive flow into the extreme implied (absorbed) | CKS 2014 (linear impact), absorption as negative residual |
| I3 | impact | impact asymmetry: OLS slope of r on Dl over [i-24, i-1] using bars with Dl > 0 minus the slope on bars with Dl < 0, x d, / abs(lam(i)) (each side >= 5 bars) | Hasbrouck 1991 |
| J1 | toxicity | VPIN proxy: sum abs(Dl) / sum V over the 12 bars before i (true aggressor sides, time bars), unsigned | Easley-Lopez de Prado-O'Hara 2012; Andersen-Bondarenko 2014 |
| J2 | toxicity | VPIN change: J1 over [i-6, i-1] minus J1 over [i-12, i-7], unsigned | same |
| J3 | persistence | mean `sac` over k-3..k-1 (NaN if none), unsigned | Lillo-Farmer 2004, Toth et al. 2015 |
| J4 | persistence | persistent flow with the trade: J3 x sign(d x sum Dl over k-3..k-1) | metaorder splitting |
| K1 | stop-run | sweep burst: V(ext) / med20(V) at ext, unsigned | Osler 2005 (stop cascades) |
| K2 | stop-run | sweep one-sidedness: -d x Dl(ext) / V(ext). + = aggressors pushed INTO the trade's extreme (stops / breakout buyers or sellers fired) | Osler 2005 |
| K3 | stop-run | post-sweep flip: d x sum Dl over [ext+1, i-1] / their volume (0 when ext = i-1). + = flow turned to the trade's side after the sweep | Osler 2003 (reversal at order clusters) |
| K4 | stop-run | cascade vs absorb: K2 x K3 x K1 clipped to [-10, 10]. + = a heavy one-sided push that then reversed (stops ran and were absorbed); - = the push kept going | combination, frozen |
| L1 | queue | queue imbalance at the touch: d x imb1 of k-1 (depth days only) | Gould-Bonart 2016 |
| L2 | queue | OFI: d x sum ofi over k-3..k-1 / max(1, 3 x mean dep1 of those bars) (depth days only) | Cont-Kukanov-Stoikov 2014 |

Expected from the literature (written before data, so it can be checked): I2, K2-K4 are the only ones aligned with LIT's own
thesis (sweep, then reversal). J1 / J2 / I1 predict the SIZE of moves (range, slippage), not direction: a "hi"/"lo" split on them
is a volatility filter and should look like the rejected regime levers. L1 / L2 work at seconds; at a 5m close they should be
~ chance (the test is there to show that, not to hope). J3 / J4: signs are predictable, prices are not (Lillo-Farmer): ~ chance.

## How v3 enters the idea mill (amends DESIGN_forward.md families; nothing else there changes)
- `of_forward.run` scores the v3 features beside v2: F = v2 features + v3 features for every entry row. New families =
  (entry, group) for groups I, J, K (each 3 entries) and L (only once >= 40 depth days, like G): **24 + 12 = 36 families**.
  Variants per family: features x 2 sides (I 6, J 8, K 8, L 4). Simes + BH (gate A) runs across ALL scored families of the run,
  so adding v3 makes the old families slightly HARDER to pass, never easier. Same gates B-E, same placebo, same split file.
- `of_mill.py` (DESIGN2's 294-variant look) is NOT changed: v3 is scored only through the forward protocol and the learner.

## The learning loop (`of_learn.py`), every night
1. **Log.** For every LIT and ATLAS signal on a tick day: the OF state at entry (all v2 + v3 features, OF1's absorbed read at the
   sweep, the side quality of the day) and the outcome (P&L $, R, won = P&L > 0). Sources: the cloud = the replays
   (`of_battery.lit_trades()`, `of_battery.atlas_md()`, = what the bots would have done); the PC = the same replays on its own
   bars. One row per (bot, entry time); a row is never rewritten once its outcome is known. File: `research/learn/of_signals.jsonl`
   (cloud) / `logs/orderflow/of_signals.jsonl` (PC; never a tracked file).
2. **Estimate** per bot (LIT, ATLAS) per READING. A reading = one feature split at its median over the bot's logged signals
   (median frozen at the first night with >= 20 signals of that bot, written to `of_learn_state.json`, never moved), plus 3 named
   readings: `absorbed` (OF1 rule at the sweep: absorbed vs not), `cascade` (K4 > 0 vs <= 0), `flow_with` (A2 > 0 vs <= 0).
   For each reading: n, wins and win rate on each side, Wilson 90% intervals, the difference in win rate and in mean $, and a
   one-sided permutation p (2,000 shuffles of the outcome labels, seeded by the reading id).
3. **Placebo.** The same estimate on outcome labels shuffled ONCE per night (seed = the night's date): the number of placebo
   readings that reach "lead" is printed next to the real count. If the placebo count >= the real count, every lead that night is
   labelled "no better than chance".
4. **Status words (frozen):**
   - `too few` - either side of the split has < 20 signals. ("OF said absorbed at the sweep: 7 of 9 won, too few to act")
   - `nothing` - p >= 0.10.
   - `watching` - p < 0.10 but not a BH discovery at q = 0.10 across all readings of that bot that night.
   - `lead` - BH discovery at q = 0.10, both sides >= 20, AND the same sign on the older half and the newer half of the signals.
     A lead only means "send it through the battery / mill as a pre-registered test"; it NEVER changes LIT, ATLAS or a size.
5. **Journal.** One line per (bot, reading) whose status CHANGED, plus the 3 named readings every night they have new signals,
   into `research/learn/journal.json` (pillar `lit` / `atlas`, lens `order flow`, key `of|<bot>|<reading>`) through
   `engine/market_learn.update_journal` (same merge rules; `of|` keys are never auto-faded). The Brain's Order Flow room shows the
   newest learner line (`engine/brain_feed.of_bot`).

## Pipeline proof before data (`of_sim.py`, synthetic only, never written to data/)
A tick simulator with KNOWN planted effects: Globex + prior-day levels, sweeps of those levels where a hidden passive order
(iceberg) absorbs the aggressive flow and price reverses ("absorbed": planted win), vs sweeps where stops cascade and price runs
("cascade": planted loss), metaorder trade-sign persistence, NQ-like size mix, quotes, and top-10 depth snapshots with a planted
queue imbalance on depth days. A null mode plants nothing. The proof (`tests/test_oflearn.py`): summaries -> battery -> v3
features -> of_forward (with v3 families) -> learner -> journal -> Brain room, end to end; the planted absorption must be found
(OF1 kept net > all, learner `absorbed` reading = lead) and the null world must give no lead and no stage-D survivor beyond the
placebo's count.
