---
title: LIT performance checks - is live inside the expected range, how robust is the live config, exit efficiency, a monthly walk-forward and a look-ahead audit of every stored run
family: other
date: 2026-10-21
status: info (no rule change)
summary: Seven read-only checks from the competitor-features list (#6, 7, 9, 11, 12, 13, 14) now run on the live LIT and show on a new Performance page (PC Data > Performance, phone Money > Performance). Expected range - a bootstrap of the 2026 H2 sessions of run lit_live gives the band for N sessions; after 10 sessions the 90% band is -3.7R to +13.0R (median +3.0R) and -$1.8k to +$5.3k on the eval path, 3-8 trades. Robustness of the live config on 2026 (LIT size rule, base +$43,385 PF 4.07) - prices +/-1 tick on every 5m and 1m bar keep 92% of the $ (50 copies, p10-p90 83-100%, all profitable), +/-2 ticks 85%, random 0-3 ticks of slippage on every fill 98%, 10% / 20% of trades missed at random 90% / 80%, a 1-minute late entry 92% (H1 81%, H2 129%), 2 minutes late 68% (H2 37%): a late entry is the weak spot, as batch 3b found for the combo. All stresses together keep 76%. Exit efficiency - 2026 trades kept 48% of all the open profit they saw; the 66 that reached +1R kept 62% of their best move and gave back 1.3R on average (35 ended at breakeven). Walk-forward - re-picking 6 knobs (729 points) every month on all months before made +$29.3k Feb-Oct vs +$33.3k for the fixed live config; it won 3 of 9 months, so keep the config fixed. Look-ahead audit - 499 LIT runs, 1,472 top trades re-built on data cut at the entry bar: 0 changed, 0 flagged (64 runs need a research executor and were skipped).
runs: lit_robust_noise1, lit_robust_noise2, lit_robust_slip03, lit_robust_miss10, lit_robust_miss20, lit_robust_delay1, lit_robust_delay2, lit_robust_worst, lit_live
---

## In one minute (owner summary)

- **New page: Performance** (PC: Data > Performance, pinned in the sidebar; phone: Money > Performance). Six tabs:
  Range, Live vs backtest, Exit efficiency, Robustness, Months, Status. It only reports. Nothing in `live_model.json`
  changed and nothing here sizes or pauses the bot.
- **Range: "is it broken, or just a normal bad week?"** The live and paper results since the LIT start (2026-10-19) are
  placed in the range the backtest expects for the same number of sessions (H2 band, the honest half). Green from p10
  up, amber p5-p10, red below p5 ("investigate"). For 10 sessions the 90% band is -3.7R to +13.0R, -$1,826 to +$5,256 on
  the eval path and 3-8 trades. A losing streak shows how often it happens in 20 trades.
- **Robustness of the live LIT on 2026** (plain LIT size, base +$43,385, PF 4.07, 2-week pass / fail 31.6 / 1.0%):

  | Test | $ kept (p10-p90) | PF | H1 / H2 kept |
  |---|---:|---:|---:|
  | Prices +/-1 tick, every 5m and 1m bar (50 copies) | 92% (83-100%) | 3.67 | 91 / 95% |
  | Prices +/-2 ticks (50 copies) | 85% (73-96%) | 3.31 | 82 / 93% |
  | Random 0-3 ticks slippage on every fill (500 draws) | 98% | 3.89 | 98 / 97% |
  | 10% of trades missed at random (500 draws) | 90% (77-101%) | 4.09 | 90 / 90% |
  | 20% missed (500 draws) | 80% (63-95%) | 4.07 | 79 / 80% |
  | Entry 1 minute late | 92% | 3.88 | 81 / 129% |
  | Entry 2 minutes late | 68% | 2.96 | 76 / 37% |
  | All at once: +/-1 tick, 0-2 ticks slip, 10% missed, 1 min late (50 copies) | 76% (62-92%) | 3.37 | 67 / 110% |

  Every noisy copy stayed profitable. **The weak spot is a late entry** (2 minutes late loses two thirds of H2): keep the
  PC timing fix (route ~3 s after the 1m CISD close) and keep NinjaTrader running from 01:55 ET.
- **Exit efficiency (2026):** the trades kept 48% of all the open profit they saw. 66 of 120 reached +1R; they kept 62%
  of their best move and gave back 1.3R on average. 35 of them ended under +0.5R, almost all breakeven exits: that is
  the price of BE at 1R. Targets keep 94% of the best move. Losers were up only 0.35R on average before the stop. 2021-25
  (reference) keeps 16% of the open profit.
- **Months and walk-forward:** re-picking six knobs every month (15-minute check time, BE offset, displacement, sweep depth,
  VIX band, minimum R:R: 729 settings) on all the months before made +$29,339 Feb-Oct vs +$33,346 for the fixed live
  config. Re-picking won only 3 of 9 months and never picked the live point (it kept choosing the 10-minute check and
  BE+1.75, the H1 favourite, which then did worse). Keep the config fixed. Batch 3b's 3-month walk-forward of the combo
  said the same.
- **Look-ahead audit of every stored run:** 499 LIT runs, their top 3 trades each (1,472) re-built on data cut at the
  entry bar: no setup field and no signal changed, 0 runs flagged. 64 runs need a research executor (size tilts, research
  options) and were skipped. A planted look-ahead (a setup field computed from future bars) is caught by the test.
- **Status:** 30 days of uptime per part (cloud monitor runs, Surface heartbeat, NinjaTrader feed, phone live feed,
  auto-update) and an incident list with the fix for each. The cloud monitor stores a small daily summary in its state
  on every run (no extra Actions minutes); a run gap longer than 45 minutes in the window is counted as missed runs, so
  the watcher is watched too.

## How it was done

- **Range** (`engine/health_band.py`, `research/lab/health_band.json`): 4,000 bootstrap paths of 1-60 sessions drawn from
  the 2026 H2 sessions (78, 40 trades) and from all of 2026 (206, 120 trades) of run lit_live; a session without a trade
  counts as zero, so the band also covers trade frequency. Percentiles 1-99 of cumulative R, trades, $ (LIT rule) and $
  on the eval path (run lit_adopt_t15_be_off_eval: the two_week sizing the bots trade). Live / paper trades are compared
  by R (sizing-free) for the colour, with $ and trade count next to it.
- **Live vs backtest** (`engine/perf.exec_curve` on `engine/fill_audit.py` rows): backtest line = the backtest's P&L at the
  bot's qty on matched trades + the backtest trades the bot missed; live line = real P&L of matched + extra trades. Gap =
  slippage + other execution + missed + extra (exact). The PC sends the per-day curve in its heartbeat `exec` block.
- **Robustness** (`tools/lit_robust.py`, `research/lab/robust.json`): a 2026 window from 2025-10-01 reproduces run lit_live's
  120 trades exactly. Noise moves every 5m and 1m O/H/L/C by whole ticks (high / low widened to stay valid) and rebuilds
  the market and the setups. Slippage and missed trades are re-scored after the fact (exact). Delay = engine option
  `entry_delay` (research only, from batch 3b). Each test's median copy is stored as a run.
- **Exit efficiency** (`tools/trade_intel.py exit_eff`): capture = exit R / MFE R per trade; "open profit kept" = sum of R /
  sum of MFE over trades up more than 0.25R.
- **Walk-forward** (`tools/lit_walkforward.py`, `research/lab/walkforward.json`): anchored, pick on Jan..k, trade month k+1,
  ties to the live point.
- **Look-ahead** (`tools/lookahead_audit.py`, `research/lab/lookahead_audit.json`): the method of tests/test_lit_lookahead.py
  and tests/test_trade_intel.py, per run. `LE_LOOKAHEAD=1` makes `runlib.save()` check every new run.

## Caveats

- 2026 H2 is 40 trades: the band is wide and a few sessions say little. The colour is a prompt to look, not a verdict.
- Noise on 5m and 1m is drawn independently, so the 1m bars no longer rebuild the 5m bars exactly; that is part of the
  stress.
- Exit efficiency describes the rules; changing BE was tested before (lit-adv-management) and only BE + 1.25 passed.
