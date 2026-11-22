---
name: strategy-test
description: The proof protocol before ANY change to a live strategy (LIT/Zlarior, ATLAS) or a new idea - which data, which splits, which numbers, where it goes. Use when someone proposes a rule, filter, size or target change, or asks "would X make more money".
---

# Strategy test protocol (CLAUDE.md hard rules, short form)

1. **Check first:** `grep -i "<idea>" docs/TESTED_AND_REJECTED.md` and STATE.md "Tested and rejected". Already rejected = say so, stop.
2. **Data:** futures only (TradingView NQ1!/ES1! exports in `data/`, NinjaTrader bars). Never Yahoo, never CFD. Costs in (commission + 1 tick slippage).
3. **Splits (both must be better than the live model):**
   - LIT: pick on 2026 Jan-Jun, check on 2026 Jul-Oct.
   - ATLAS / others: both 2026 halves AND 2021-25.
   Pre-register the variants (write them down before the run); count them; a win in one of 20 tries is noise.
4. **Report every variant, same table vs the live model:** trades/week (2-4 allowed), PF, net $, $/month, max DD $, eval pass/fail and
   days to pass (owner's real prices: Builder 50K $91.80, 25K $63 / $43). Stops 1 tick beyond the sweep extreme, size follows the stop,
   one target (VIX band, banked at 8R). Owner-approved sizing: eval two_week room_f 0.4 kept to session 80.
5. **Verdict:** both splits better + 2-4 trades/week -> a yes/no card for the owner (live-money change = his call, never ours).
   Otherwise REJECTED: add a dated line to `docs/TESTED_AND_REJECTED.md` (idea, splits, the numbers, why) + a write-up in `research/writeups/`.
6. **Only after the owner's yes:** change `live_model.json` AND `live_model_lit.json` together, then
   `python tools/lit_losses.py live`, `python tools/model_versions.py`, `python -X utf8 -m tests.test_lit_live` (live loop = backtest),
   `python -m engine.ninjatrader --selftest`. Never during the trading day (01:50-16:00 ET): the PC updates only when flat.

Paper only for Claude: never arm live, never place real orders. Helpers on a live-money day: no strategy changes at all.
Cheap runs: cached replays (`research/runs/_cache`), one helper at most, cheaper model for the sweeps.
