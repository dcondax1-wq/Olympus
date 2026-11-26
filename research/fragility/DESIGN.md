# LIT robustness & fragility audit. Plan (2026-11-26 ~13:40 ET, written before the runs)

PAPER RESEARCH ONLY: nothing live changes. Code `research/fragility/fragility.py` -> `results.json`; write-up
`research/writeups/lit-fragility-2026-11-26.md`. Engine = engine/lit.run_x with live_model.json "lit" (tools/lit_final.run).
Spans: 2026 H1 (Jan-Jun), 2026 Jul-Oct 16, 2021-25 (5m reference), fresh Oct 19 - Nov 20.
1. Parameter surface: each knob alone at -20 / -10 / +10 / +20% (integer knobs rounded; the window edges +-12 / 24 min):
   sweep depth 0.5, displacement 0.8, inducement distance 1.0 ATR and age 36, 1m CISD window 22, limit expiry 6 bars, VIX-band
   multiple 1.0, min target 1.5R, 8R bank, stop buffer 1 tick (0 / 2 ticks instead), min / max stop 8 / 80, breakeven 1R,
   15-min check at 15, window start 02:00 and end 15:30. Plateau test: share of the 4 neighbours keeping >= 80% of today's $ per span.
2. Costs: +1 / +2 / +4 ticks per side per micro on top of the engine's ($1.90 + 1 tick).
3. Trade-order luck: 20,000 resampled 50K evals (two_week-like sizing: risk = min(40% of the room to the trailing floor,
   the $ that makes this trade's planned target cover what is still needed, 40 micros), MFFU 50K rules) from the 2026 pool and
   from the 2021-25 pool: pass / fail, median trades, max DD, longest losing streak, P(a 7+ losing streak before the pass).
4. Data-snooping haircut: N trials = every LIT run stored in research/runs (lower bound) and a 3x stress; the variance of the
   trials' Sharpe from those runs' daily $; deflated Sharpe (Bailey & Lopez de Prado 2014) of the live LIT on 2026 daily $
   and on 2021-26; the haircut Sharpe -> the share of the 2026 return to trust.
