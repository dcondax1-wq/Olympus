---
tags:
  - zeus/research
  - family/other
  - verdict/info
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-11-21"
status: "info - tools/reconcile_live.py built (read-only, nightly-ready) -> research/lab/reconcile.json. No change proposed."
source: "research/writeups/live-vs-model-2026-11-21.md"
aliases:
  - "Live vs model, every real trade so far"
---

# Live vs model, every real trade so far

> [!note] Verdict: info
> info - tools/reconcile_live.py built (read-only, nightly-ready) -> research/lab/reconcile.json. No change proposed.

**Full title:** Live vs model, every real trade so far - entries fill 3 (Zlarior) / 11 (ATLAS) ticks late, $37 in all over 4 trades; real exits not priced yet; the cost alarm agrees

## Summary

Every real trade the cloud can see (4 - ATLAS Nov 6 / 17 / 18, Zlarior Nov 16) reconciled against its model. Entries - ATLAS +9 / +11 / +15 ticks (-$9 / -$11 / -$15 at 2 micros), Zlarior +3 (-$1.50). Real $ a trade vs model - ATLAS +$492 vs +$503 (-$11.67 a trade, all entry), Zlarior -$131 vs -$129. R - ATLAS -1.01 -> -1.06, +6.88 -> +6.84, -1.01 -> -1.15; Zlarior -1.00 -> -1.02. Cause - late fills (latency + slippage on the 5m boundary), no partial, no manual, no missed trade visible. Real exit prices are not in reach from the cloud (no PC day folder answered; the stored study has entries only), so exits are the model's and flagged. Implied real-cost PF of the last 40 sessions - ATLAS 2.27 (2026 H1 2.57), Zlarior 3.38 (3.20); the nightly cost alarm reads the same costs and the same flag (NOT ENOUGH FILLS: 3 and 1 of the 5 needed).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-21]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Runs: `tools/reconcile_live.py -> research/lab/reconcile.json; tests/test_reconcile_live.py 12/12`
- Source: `research/writeups/live-vs-model-2026-11-21.md`
- Back to [[ZEUS Home]]
