---
title: PROMETHEUS - a genetic algorithm evolves the live LIT's ten knobs on 2026 H1; does anything it breeds beat live on H2?
family: other
date: 2026-11-03
status: rejected - nothing to switch (every seed's champion loses money on 2026 H2 and 2021-25 against live LIT)
summary: A seeded genetic algorithm (24 creatures x 20 generations, 5 independent seeds, 1,875 distinct variants) evolved ten numeric knobs of the live LIT (live_model_lit.json - 1m CISD window, breakeven R and offset, the early-check minute, the target bank, the VIX target multiple, the minimum target, the displacement filter, the last entry time and the eval room share) with a fitness computed on 2026 H1 only - $ per month (LIT size rule, costs in) and MFFU 50K eval speed (p10 - f10 on the live two_week eval path), penalised under 2 trades a week. It found big H1 gains (champions +$738 to +$2,311 a month, 2-week passes 64-76% vs 57%), and none of it survives. On 2026 H2 every champion makes LESS than live (-$675 to -$1,566 a month; primary seed -$675, weekly-block bootstrap 5-95% -$1,622 to +$6), and on 2021-25 every champion is worse too (-$150 to -$576 a month). H1 rank predicts H2 rank only weakly (Spearman 0.28 on fitness, 0.14 on $ per month); 247 of 349 checked variants make more $ a month than live on H1, 3 on H2, none on both. Live LIT sits on a plateau; the GA's recurring "improvements" (a looser 0.65 ATR displacement for more trades, a smaller eval room share for fewer fails) are already-rejected ideas (lit-more-setups.md, uprisk.md). Research only; live_model*.json untouched.
runs: prometheus_s7, prometheus_s11, prometheus_s23, prometheus_s42, prometheus_s101
---

## For the owner (one minute)

| What was done | The numbers | What's next |
|---|---|---|
| Built **PROMETHEUS**: a "strategy breeder" that mutates and crosses the live Zlarior (LIT) settings and keeps the fittest, judged on **Jan-Jun 2026 only** | 24 versions x 20 generations x 5 independent runs = **1,875 versions** tested in ~5 minutes; each one checked afterwards on Jul-Oct 2026 and 2021-25 | Nothing to switch: **keep live LIT as it is** |
| Fitness = **$ a month** + **eval speed** (2-week pass minus 2-week fail on the real MFFU 50K eval sizing), with a penalty under 2 trades a week | Best Jan-Jun version: **$7,110/mo vs live $5,562**, 2-week pass/fail **72.3/0.0 vs 57.1/1.7** | - |
| The honest check on Jul-Oct 2026 (never seen by the breeder) | That same version: **$1,995/mo vs live $2,670 (-$675/mo)**; all 5 runs' winners lose **$675-$1,566 a month** vs live | - |
| 2021-25 reference line | Every winner is worse than live there too (-$150 to -$576 a month) | - |
| **THE FORGE** page (phone, 3D): each version is a flame, the fittest burn brightest, tap one for its card | `tools/web_public/prometheus/` (published with the site) | Open it from the site: `/prometheus/` |

**In one line:** the breeder can always make Jan-Jun look better (that's what an optimiser does), but none of its gains carry
over to Jul-Oct. That is good news about live LIT: its settings already sit on a plateau, so there is nothing cheap left to
tune.

## The question

The owner's rule for LIT: pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16), 2021-25 is a reference line.
Hand tuning covered one knob at a time (`lit-sensitivity`, `lit-edge-2026-10-30`, `uprisk`). Can a search over **all ten
knobs at once** find a combination that beats live on H2 by a real margin?

## How it works

- **Ten knobs**, all read from `live_model_lit.json` (never written), each on a grid with sane bounds; the live value is a grid
  point, so live is itself a genome (`tools/prometheus/genome.py`):

| Knob | Path | Live | Range (step) |
|---|---|---|---|
| 1m CISD window after the tap | `lit.cisd1m` | 22 bars | 10-40 (2) |
| Breakeven trigger | `lit.be_r` | 1.0 R | 0.5-2.0 (0.125) |
| Breakeven offset | `lit.be_off` | 1.25 pts | 0-3 (0.25) |
| Early check (15-minute cut) minute | `lit.t_check.at` | 15 | 5-40 (5) |
| Target bank | `lit.max_rr` | 8 R | 4-12 (0.5) |
| VIX target multiple | `lit.vix_k` | 1.0 | 0.6-1.6 (0.05) |
| Minimum target | `lit.min_rr` | 1.5 R | 1.0-2.5 (0.1) |
| Displacement body | `lit.disp` | 0.8 ATR | 0.5-1.2 (0.05) |
| Last entry | `lit.window[0][1]` | 15:30 ET | 10:00-15:45 (15 min) |
| Eval room share | `lit_sizing.two_week.room_f` | 0.8 | 0.4-1.0 (0.05) |

- **The backtest is the repo's own** (`tools/prometheus/fitness.py`): trades = `tools/lit_final.run` = `engine/lit.py run_x`
  on the cached LIT candidates (with the live genome it reproduces run `lit_live` H1 exactly: 80 trades, +$33,901, PF 4.98);
  eval path = `tools/lit_adopt_combo.units` + `tools/lit_adv_manage.run_eval` (the live two_week sizing, $1.90 a micro; live
  reproduces 2-week pass/fail 57.1 / 1.7).
- **Fitness (2026 H1 only)** = 0.5 x ($/mo / live $/mo) + 0.5 x ((p10 - f10) / live (p10 - f10)) - 0.5 x (trades/wk short of
  2) - 0.25 x (trades/wk over 4). Live scores exactly 1.0. Only H1 sessions are handed to `run_x`; every trade, eval unit and
  eval session is asserted to be in H1 (`tests/test_prometheus.py` part c spies on `run_x` and `run_eval` to prove it).
- **GA** (`tools/prometheus/ga.py`): generation 0 = live + 11 mutants of live + 12 random; then 2 elites survive, the rest are
  children of tournament selection (k 3), uniform crossover (90%) and +/- 1-3 grid-step mutations (12% a gene). Seeded and
  deterministic; evaluations cached (`research/runs/_cache/prometheus_fit_*`). 5 seeds (7 = the one on the page, 11, 23,
  42, 101), 1,875 distinct variants, ~0.15 s each.
- **Checks after the GA:** every variant of the primary run (349) on H2 and 2021-25; every seed's champion and the hall of fame
  with the full numbers; a weekly-block bootstrap of the H2 $/mo difference against live. "Real margin" = H2 at least +10% $/mo,
  the bootstrap 5th percentile above $0, H2 eval speed not worse, 2+ trades a week.

## Results (costs in; LIT size rule $ unless marked eval; 2021-25 has no 1m bars and no eval-path units: its p10/f10 is the LIT size rule)

| | H1 $/mo | H1 PF | H1 tr/wk | H1 eval p10/f10 | **H2 $/mo** | H2 PF | H2 tr/wk | **H2 eval p10/f10** | 2021-25 $/mo | 2021-25 PF | 2021-25 p10/f10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Live LIT** | **$5,562** | 4.98 | 3.12 | 57.1 / 1.7 | **$2,670** | 2.91 | 2.56 | 52.2 / 5.8 | $25 | 1.01 | 6.0 / 13.5 |
| Seed 7 champion (page) | $7,110 | 4.28 | 3.59 | 72.3 / 0.0 | $1,995 | 2.16 | 2.88 | 49.3 / 0.0 | -$182 | 0.93 | 8.4 / 24.8 |
| Seed 11 champion | $6,300 | 5.82 | 3.20 | 63.9 / 0.0 | $1,853 | 2.20 | 2.76 | 47.8 / 0.0 | -$125 | 0.94 | 7.0 / 14.2 |
| Seed 23 champion | $7,440 | 6.24 | 3.63 | 73.1 / 2.5 | $1,606 | 1.91 | 3.08 | 50.7 / 0.0 | -$551 | 0.78 | 6.4 / 22.4 |
| Seed 42 champion | $6,695 | 5.72 | 3.67 | 75.6 / 1.7 | $1,104 | 1.56 | 3.21 | 37.7 / 4.3 | -$432 | 0.84 | 5.6 / 25.0 |
| Seed 101 champion | $7,873 | 5.99 | 3.55 | 68.1 / 2.5 | $1,142 | 1.59 | 2.88 | 46.4 / 1.4 | -$325 | 0.88 | 9.5 / 27.1 |

The champions' switches (all vs live):

| Seed | Fitness (H1) | What it changed | H1 gain | **H2 gain** | H2 bootstrap 5-95% | Real margin |
|---|---|---|---|---|---|---|
| 7 | 1.292 | be_r 1.375, max_rr 8.5, min_rr 1.4, disp 0.65, last entry 15:15, room_f 0.55 | +$1,548 | **-$675** | -$1,622 .. +$6 | no |
| 11 | 1.143 | cisd1m 30, be_r 0.875, be_off 2.5, check at 10 min, max_rr 8.5, vix_k 0.9, min_rr 1.4, last entry 15:45, room_f 0.6 | +$738 | **-$817** | -$1,616 .. -$115 | no |
| 23 | 1.306 | cisd1m 30, be_off 3.0, check at 10 min, max_rr 8.5, vix_k 0.9, min_rr 1.9, disp 0.65, last entry 15:45, room_f 0.75 | +$1,878 | **-$1,064** | -$1,979 .. -$318 | no |
| 42 | 1.269 | cisd1m 36, be_off 3.0, check at 10 min, max_rr 7.5, vix_k 1.15, min_rr 1.6, disp 0.65, last entry 15:45, room_f 0.6 | +$1,133 | **-$1,566** | -$2,480 .. -$594 | no |
| 101 | 1.300 | cisd1m 38, be_r 1.125, be_off 2.5, max_rr 10.5, vix_k 0.9, min_rr 2.3, disp 0.65, last entry 14:00, room_f 0.7 | +$2,311 | **-$1,528** | -$2,630 .. -$401 | no |

How much of the H1 gain survives on H2: **none** (seed 7 keeps -44% of it, i.e. it turns into a loss; the other seeds -57% to
-138%).

### Honesty statistics (the 349 variants of the primary run, every one checked on H2)

- **Does H1 predict H2?** Spearman rank correlation of H1 fitness vs the same fitness on H2: **0.28** (weak); of H1 $ per month
  vs H2 $ per month: **0.14** (almost none).
- **Beat live on H1 fitness: 280 of 349.** On H2 fitness: 13. On both: 9 - and all 9 of those make **less** $ a month than live
  on H2 ($2,487-$2,666 vs $2,670); they score on H2 fitness only through fewer eval fails from a smaller room share.
- **More $ a month than live: 247 of 349 on H1, 3 of 349 on H2, 0 on both.**
- **The 3 that beat live's H2 $ per month** (+$9 to +$140/mo) are none of them a GA pick (H1 fitness 0.98-1.07); the best of them
  is a near-copy of live - cisd1m 24, be_off 1.0, vix_k 1.1 - with H2 eval p10 55.1 vs 52.2, a 1-2 trade difference).
  Picking among them would be picking on H2 itself, which the LIT rule forbids.
- **What the GA keeps "finding":** a looser displacement filter (disp 0.65 in 4 of 5 champions: ~0.5 more trades a week, more
  H1 $, then PF 1.6-2.2 on H2 and below 1 in 2021-25 - the "looser filters" of `lit-more-setups.md` again) and a smaller eval
  room share (0.55-0.75: fewer 2-week fails, fewer passes - the trade-off the owner already decided at 0.8 in `uprisk.md`).

## Verdict

**Rejected: nothing to propose.** No variant beats live LIT on 2026 H2 by a real margin; every seed's champion is worse on H2
and on 2021-25. `live_model.json` / `live_model_lit.json` are unchanged. This is the same picture as every hand search since
2026-10-18: the live knobs sit on a plateau, and an optimiser on six months of data mostly fits that half's noise.

If the owner ever wants to rerun it on more data (e.g. after the Dec 2026 roll, with H2 grown): `python -X utf8 -m
tools.prometheus.forge` (5 seeds, ~10 minutes on one core), then read `research/prometheus/forge_results.json`.

## Files

- Engine: `tools/prometheus/` (`genome.py` knobs, `fitness.py` H1 fitness + checks, `ga.py` the GA, `forge.py` the CLI).
- Results: `research/prometheus/forge_results.json`; runs `prometheus_s7` ... `prometheus_s101` (`research/runs/`, status rejected).
- Page: `tools/web_public/prometheus/` - THE FORGE (`index.html`, `forge.css`, `forgecore.js` data + demo fixture, `forge.js`
  three.js arena), `forge.json` (~0.2 MB), `jarvis.json` (the Jarvis card, theme `#120806`). Published by
  `tools/build_web_dashboard.py` with jarvis/ and kalshi/; the site's root worker leaves `prometheus/` alone (`OTHER_APPS`).
- Tests: `python -X utf8 -m tests.test_prometheus` (GA determinism, bounds, H1-only fitness, JSON schema / size, the page in
  Chromium at 390 x 844); screenshots in `research/handoff/2026-11-03/prometheus/`.
