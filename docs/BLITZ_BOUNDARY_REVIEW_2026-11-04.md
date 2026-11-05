# BLITZ account-C boundary review — 2026-11-04

**Status:** draft correction [PR #180](https://github.com/demetrades2000-coder/nq-liquidity-engine/pull/180) is **not merged** and **not a real-account readiness signoff**. This note is read-only; it changes no orders, strategy, size formula, arming, or other accounts.

## Exact defect and proposed boundary

`AccountC._enter` checks signal age against the time captured at the start of the poll. A slow guard can advance the clock before `AccountC.route` sends the order. On the shipped path, a signal checked at 49 seconds and routed at 51 seconds, or checked at 32 seconds and routed at 63 seconds, still reaches the adapter. The rule says an entry first sent more than 50 seconds after the opening minute must not be chased.

PR #180 adds a second check inside **account C's** `route`, immediately before `adapter.send`. For a buy/sell entry older than 50 seconds it returns `ok: false, not_sent: true`. The existing `_enter → never_placed → _drop_unplaced` path must clear the provisional open state, mark the row not placed, book $0, and avoid an entry notice. Position exits and stop changes are excluded from the age limit.

The preflight display currently calls `AccountC.qty` without the signal's break number. With later-break sizing on, it previews 3 micros in the documented fixture while the actual first break routes 1. PR #180 passes `brk_n=1` for the first-break scenario, displays `brk_n=2` separately, and puts both labels at the beginning of the capped preflight detail.

## Verification matrix

| Check | Expected result | Evidence status |
|---|---|---|
| Entry at 49 and 50 seconds | Adapter receives one entry | Added as mocked regression in PR #180; not run here |
| Buy checked at 49, sent at 51 | No adapter call; no booking or entry notice | Added as mocked regression; not run here |
| Sell checked at 32, sent at 63 | Same refusal and cleanup | Added as mocked regression; not run here |
| Entry already 51 seconds old when polled | Refused before route | Added as mocked regression; not run here |
| Old position exit and stop change | Still sent to adapter | Added as mocked regression; not run here |
| Eval first/later break at 60-point stop | Preview equals `AccountC.qty(..., brk_n=1/2)`; labels both | Added as mocked regression; not run here |
| No adapter or adapter exception | No phantom fill/booking | Covered by existing isolated proposal suite in PR #137; rerun against final code |
| Funded and paper sizing | No later-break multiplier | Existing account-C suite; rerun against final code |
| 2026 batch versus stream and account C | Trade parity and no unexpected LIT/ATLAS change | Required full replay; not run for PR #180 |
| Real NinjaTrader brackets, fill/exit, cash reconciliation | Broker-confirmed in owner's Sim setup | Not established by cloud mocks |

A source syntax check passed for the two edited Python files and the new test. **No test result is claimed for the new regression suite.** GitHub `chatgpt-guard` run 41944065544 on PR #180 failed at its protected-path step because two engine files changed; shared checks were skipped. This guard outcome is not proof of behavior. The engine change needs the project's reviewed integration path, then focused tests, full account-C and LIT replay, and an isolated Sim rehearsal.

## Review limits

- A mock adapter proves the call is suppressed at the tested clock boundaries; it does not prove an accepted protective bracket or real fill.
- The check happens immediately before the synchronous adapter call. It does not bound network/broker latency after that call.
- The preflight amounts are scenarios at an assumed stop distance. They cannot predict the next signal, gap at the open, or final broker fill.
- BLITZ's published 25K account-slot estimate was about **+$37/month** in the 2026 H2 check versus about **+$30/month** for random directions on the same signal times; the 2021–25 reference was about **−$40/month**. These simulated figures do not establish a durable edge.
