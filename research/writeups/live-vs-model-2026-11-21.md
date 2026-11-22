---
title: Live vs model, every real trade so far - entries fill 3 (Zlarior) / 11 (ATLAS) ticks late, $37 in all over 4 trades; real exits not priced yet; the cost alarm agrees
family: other
date: 2026-11-21
status: info - tools/reconcile_live.py built (read-only, nightly-ready) -> research/lab/reconcile.json. No change proposed.
summary: Every real trade the cloud can see (4 - ATLAS Nov 6 / 17 / 18, Zlarior Nov 16) reconciled against its model. Entries - ATLAS +9 / +11 / +15 ticks (-$9 / -$11 / -$15 at 2 micros), Zlarior +3 (-$1.50). Real $ a trade vs model - ATLAS +$492 vs +$503 (-$11.67 a trade, all entry), Zlarior -$131 vs -$129. R - ATLAS -1.01 -> -1.06, +6.88 -> +6.84, -1.01 -> -1.15; Zlarior -1.00 -> -1.02. Cause - late fills (latency + slippage on the 5m boundary), no partial, no manual, no missed trade visible. Real exit prices are not in reach from the cloud (no PC day folder answered; the stored study has entries only), so exits are the model's and flagged. Implied real-cost PF of the last 40 sessions - ATLAS 2.27 (2026 H1 2.57), Zlarior 3.38 (3.20); the nightly cost alarm reads the same costs and the same flag (NOT ENOUGH FILLS: 3 and 1 of the 5 needed).
runs: tools/reconcile_live.py -> research/lab/reconcile.json; tests/test_reconcile_live.py 12/12
---

# Live vs model, every real trade so far (2026-11-21)

## For the owner (one minute)

**Real fills cost $37 in total over the 4 trades we can see. The bots still make money at those costs. Nothing to change.**

| Bot | Trades seen | Entry vs model | Real $ a trade vs model | Lost to fills | Still profitable at real cost? (last 40 sessions) |
|---|---:|---|---|---:|---|
| ATLAS | 3 | 11 ticks late (median) | +$492 vs +$503 | $35 | Yes: PF 2.27 (2026 Jan-Jun 2.57) |
| Zlarior | 1 | 3 ticks late | -$131 vs -$129 | $2 | Yes: PF 3.38 (3.20) |

Every trade:

| When (ET) | Bot | Side | Model entry -> real fill | Exit (model) | R model -> real | $ real vs model | Cause |
|---|---|---|---|---|---|---|---|
| Fri Nov 6 04:00 | ATLAS EMA, 2 MNQ | SHORT | 27,037.75 -> 27,035.50 (+9 ticks) | STOP 27,079.00 | -1.01 -> -1.06 | -$9 | late fill (order 5 s after the bar) |
| Mon Nov 16 06:16 | Zlarior, 1 MNQ | LONG | 27,798.75 -> 27,799.50 (+3) | STOP 27,735.00 | -1.00 -> -1.02 | -$1.50 | late fill (4 s) |
| Tue Nov 17 08:20 | ATLAS EMA, 2 MNQ | SHORT | 27,367.50 -> 27,364.75 (+11) | TARGET 26,918.57 | +6.88 -> +6.84 | -$11 | late fill (4 s); this win passed the 25K eval |
| Wed Nov 18 04:50 | ATLAS MACD, 2 MNQ | SHORT | 27,395.50 -> 27,391.75 (+15) | STOP 27,422.75 | -1.01 -> -1.15 | -$15 | slippage (3 s) |

Check: the Nov 18 stop prices at -$113 at the model's entry, the funded account's first-day -$113; at the real fill it is
-$128. So either the stop filled 7-8 ticks better than its level, or the -$113 was booked at the model's prices (the bot
books its ledger at the model; NinjaTrader's balance keeps the room right). A NinjaTrader Executions export of that day settles it.

**Next for you:** nothing. (Optional, 1 minute: NinjaTrader > Account Performance or Executions > export Nov 6-20 and drop the
file in the chat; then every exit gets its real price too.)

## What could not be seen, honestly

- **Real exit prices: none.** The PC's day folders (trades, fills, the fill audit's twin rows with priced exits) reach the cloud
  only when the PC answers `python tools/data_pull.py --latest` (asked today; no answer inside the window: the PC answers outside
  01:50-16:00 ET when it is on). The stored real-fill study has entries only. Every exit above is the model's, flagged
  "exit not priced", so the $ differences are entry-only.
- **Trades after Nov 18** (the funded account's Nov 19-21 trades, e.g. the Nov 20 short closed at break-even "+$2 (stop)") are not
  in any committed file; they appear as soon as a day folder is pulled. Missed / held-back entries likewise (none visible).
- The tool reads the PC's folders on the PC itself too (logs/datapipe/days/), so run there nightly it sees everything.

## The tool (tools/reconcile_live.py, read-only)

Sources, best first: data/pc_days/<day>/ (or logs/datapipe/days/<day>/ on the PC): trades.jsonl.gz (model entry / stop /
target, the broker legs, the exit row), fills.jsonl.gz (sent / filled seconds after the bar open, fill price, filled qty),
twin.json.gz (engine/fill_audit's rows: the backtest twin's exit and the live exit priced from NinjaTrader's order states;
missed / extra trades), decisions.jsonl.gz (held-back entries); the board's typed owner notes (manual actions); fallback
research/second/atlas_fills_why.json + the model exits of the ATLAS live-code replay / the edge check's LIT replay.
Per trade: bot, account (last 4 only), signal time, model entry vs real fill (ticks, $), model vs real exit, model vs real R, $
difference, cause: latency (order > 3 s after the bar open), slippage (> 2 ticks past the model, which already has 1),
partial (filled < routed), manual (owner note / manual exit), exit slippage (> 2 ticks), outcome differs, missed / held back.
Totals per bot: real vs model $ a trade, the measured median ticks, the implied real-cost PF (tools/cost_alarm's re-pricing at
that cost) and whether the nightly cost alarm agrees (same fills, same cost, same flag). Tonight: agrees for both bots.
tests/test_reconcile_live.py 12/12 (a synthetic day folder in the datapipe format: slippage, latency, partial, priced exit,
refused / missed / held-back, privacy, --print writes nothing).
