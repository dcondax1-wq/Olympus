# Confluence learning log

One entry per learning cycle (engine/confluence_search.py). Futures only: NQ week-block folds (walk-forward decide -> confirm) plus ES as a robustness check.

## Confluence learning cycle 2026-10-16 15:07 (run 20261016-150743)
Data: NQ futures 2026-08-06..2026-10-16 (52 sessions, 51 candidates, 29 trades) · ES futures check (51 sessions, 47 trades). No CFD data.
Folds: F1 08-06..08-20 (decide, 11s), F2 08-21..09-04 (decide, 11s), F3 09-07..09-18 (decide, 10s), F4 09-21..10-02 (confirm, 10s), F5 10-05..10-16 (confirm, 10s)
Baseline: NQ $+10718 (2.8/wk; folds $+2669 2.3/wk, $+5055 4.1/wk, $-218 2.5/wk, $+1202 1.5/wk, $+2010 3.5/wk), ES $-4272.

8 active, 10 probation, 57 candidate, 24 retired (54 tests, 38 backtests, 8.4s). Recommended: 1H structure with trade (score gate), High volume on trigger -> NQ +10718 to +11291 (OOS +98), ES +387, 2.9 trades/week. Live confluences recommended for retirement: 1H structure with trade (score gate).

Recommended params (lead applies): `{"w_htf": 0}`; needs engine hook: `[{"op": "grade_add", "feature": "x_trigger_vol_hi", "kind": "binary", "median": null, "w": -2}]`

**ACTIVE**
- Low-resistance path (LRL) (score gate) [score gate w_lrl]: Earns its place: removing it costs NQ -4232 (OOS -228, ES +1394). candidates with it do better by 0.43R in the earlier folds (2/2 folds agree, out-of-sample confirms, ES agrees)
- 15m already aligned (score gate) [score gate w_m15]: Earns its place: removing it costs NQ -365 (OOS +0, ES -4). candidates with it do worse by 0.16R in the earlier folds (1/2 folds agree, out-of-sample does not confirm, ES agrees)
- Discount/premium of 1H range (score gate) [score gate w_pd]: Earns its place: removing it costs NQ -4110 (OOS -311, ES +1709). candidates with it do better by 0.51R in the earlier folds (0/1 folds agree, out-of-sample confirms, ES agrees)
- Low-resistance path (LRL) [grade (hard-coded weight)]: Earns its place: removing it costs NQ -1081 (OOS -236, ES +270). candidates with it do better by 0.43R in the earlier folds (2/2 folds agree, out-of-sample confirms, ES agrees)
- Discount/premium of 1H range [grade g_pd]: Earns its place: removing it costs NQ -1420 (OOS -396, ES +604). candidates with it do better by 0.51R in the earlier folds (0/1 folds agree, out-of-sample confirms, ES agrees)
- Raid beyond 90m true open [grade (hard-coded weight)]: Earns its place: removing it costs NQ -1205 (OOS -236, ES +162). candidates with it do better by 0.60R in the earlier folds (0/2 folds agree, out-of-sample confirms, ES agrees)
- Value side of session VWAP [grade (hard-coded weight)]: Earns its place: removing it costs NQ -1090 (OOS -161, ES +687). candidates with it do better by 0.45R in the earlier folds (3/4 folds agree, out-of-sample confirms, ES agrees)
- High volume on trigger [grade (needs engine hook)]: Sign-stable and grade weight -2 passed every rule: NQ +104 (OOS +45, decide +59), ES +248, 2.8 trades/wk. Needs an engine hook before it can go live.

**PROBATION**
- Day already stretched (>=1.2x ADR) [grade (hard-coded weight)]: Removing it would help NQ but not on every rule (NQ +189 (OOS +0, decide +189), ES -173, 2.8 trades/wk; failed: out-of-sample folds +0, hurts ES -173).
- First hour of RTH [grade (hard-coded weight)]: Barely matters: removing it changes NQ only -59 (OOS +0, ES -99). Kept for now, re-tested every run. candidates with it do worse by 1.08R in the earlier folds (3/3 folds agree, out-of-sample does not confirm, ES agrees)
- 1H structure with trade [grade (hard-coded weight)]: Barely matters: removing it changes NQ only -56 (OOS +139, ES +61). Kept for now, re-tested every run. candidates with it do worse by 0.15R in the earlier folds (1/4 folds agree, out-of-sample does not confirm, ES agrees)
- 15m already aligned [grade (hard-coded weight)]: Barely matters: removing it changes NQ only -7 (OOS +0, ES +0). Kept for now, re-tested every run. candidates with it do worse by 0.16R in the earlier folds (1/2 folds agree, out-of-sample does not confirm, ES agrees)
- QT: entry in Q3 [grade g_q3]: Removing it would help NQ but not on every rule (NQ +44 (OOS +56, decide -12), ES -168, 2.8 trades/wk; failed: decide folds -12, hurts ES -168). candidates with it do worse by 0.99R in the earlier folds (3/3 folds agree, out-of-sample confirms, ES agrees)
- QT: sweep in Q2 [grade (hard-coded weight)]: Barely matters: removing it changes NQ only -143 (OOS +0, ES +110). Kept for now, re-tested every run. candidates with it do better by 0.88R in the earlier folds (2/2 folds agree, out-of-sample confirms, ES agrees)
- Big opening gap (>=0.35 ADR) [grade (needs engine hook)]: Sign-stable; grade weight +2 helped NQ overall (NQ +1251 (OOS +720, decide +531), ES -359, 2.8 trades/wk) but failed: hurts ES -359.
- Volume climax on raid [grade (hard-coded weight)]: Removing it would help NQ but not on every rule (NQ +1045 (OOS +722, decide +323), ES -716, 2.8 trades/wk; failed: hurts ES -716). candidates with it do worse by 0.90R in the earlier folds (3/3 folds agree, out-of-sample confirms, ES agrees)
- First 45m of session [grade g_early]: Removing it would help NQ but not on every rule (NQ +294 (OOS +470, decide -176), ES -544, 2.8 trades/wk; failed: decide folds -176, hurts ES -544). candidates with it do worse by 1.53R in the earlier folds (4/4 folds agree, out-of-sample confirms, ES agrees)
- Tight stop (<=1 ATR) [grade (needs engine hook)]: Sign-stable; grade weight +2 helped NQ overall (NQ +1252 (OOS +328, decide +924), ES -205, 2.8 trades/wk) but failed: hurts ES -205.

**RETIRED**
- Displacement (ATR) [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -98 (OOS +45, decide -143), ES +77, 2.8 trades/wk; decide folds -143).
- Strong displacement candle [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -2, NQ -81 (OOS +45, decide -126), ES +247, 2.8 trades/wk; decide folds -126).
- Toward nearest major liquidity [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -719 (OOS -328, decide -390), ES +308, 2.8 trades/wk; out-of-sample folds -328, decide folds -390).
- 1H structure with trade (score gate) [score gate w_htf]: Taking it out of the gate improved every test: NQ +468 (OOS +53, decide +416), ES +80, 2.9 trades/wk. candidates with it do worse by 0.15R in the earlier folds (1/4 folds agree, out-of-sample does not confirm, ES agrees)
- Stacked liquidity raid [grade g_stacked]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -1289 (OOS -286, decide -1003), ES -146, 2.8 trades/wk; out-of-sample folds -286, decide folds -1003).
- Bars to reclaim [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -588 (OOS -192, decide -397), ES +98, 2.8 trades/wk; out-of-sample folds -192, decide folds -397).
- Trigger closes in top 25% [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -97 (OOS +46, decide -143), ES +28, 2.8 trades/wk; decide folds -143).
- Swept overnight H/L [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -725 (OOS -328, decide -397), ES +78, 2.8 trades/wk; out-of-sample folds -328, decide folds -397).

(16 more features retired as sign-flipping noise; 57 candidates waiting for more data.)

## Confluence learning cycle 2026-10-16 15:08 (run 20261016-150814)
Data: NQ futures 2026-08-06..2026-10-16 (52 sessions, 51 candidates, 29 trades) · ES futures check (51 sessions, 47 trades). No CFD data.
Folds: F1 08-06..08-20 (decide, 11s), F2 08-21..09-04 (decide, 11s), F3 09-07..09-18 (decide, 10s), F4 09-21..10-02 (confirm, 10s), F5 10-05..10-16 (confirm, 10s)
Baseline: NQ $+10718 (2.8/wk; folds $+2669 2.3/wk, $+5055 4.1/wk, $-218 2.5/wk, $+1202 1.5/wk, $+2010 3.5/wk), ES $-4272.

8 active, 10 probation, 57 candidate, 24 retired (54 tests, 38 backtests, 8.3s). Recommended: 1H structure with trade (score gate), High volume on trigger -> NQ +10718 to +11291 (OOS +98), ES +387, 2.9 trades/week. Live confluences recommended for retirement: 1H structure with trade (score gate).

Recommended params (lead applies): `{"w_htf": 0}`; needs engine hook: `[{"op": "grade_add", "feature": "x_trigger_vol_hi", "kind": "binary", "median": null, "w": -2}]`

**ACTIVE**
- Low-resistance path (LRL) (score gate) [score gate w_lrl]: Earns its place: removing it costs NQ -4232 (OOS -228, ES +1394). candidates with it do better by 0.43R in the earlier folds (2/2 folds agree, out-of-sample confirms, ES agrees)
- 15m already aligned (score gate) [score gate w_m15]: Earns its place: removing it costs NQ -365 (OOS +0, ES -4). candidates with it do worse by 0.16R in the earlier folds (1/2 folds agree, out-of-sample does not confirm, ES agrees)
- Discount/premium of 1H range (score gate) [score gate w_pd]: Earns its place: removing it costs NQ -4110 (OOS -311, ES +1709). candidates with it do better by 0.51R in the earlier folds (0/1 folds agree, out-of-sample confirms, ES agrees)
- Low-resistance path (LRL) [grade (hard-coded weight)]: Earns its place: removing it costs NQ -1081 (OOS -236, ES +270). candidates with it do better by 0.43R in the earlier folds (2/2 folds agree, out-of-sample confirms, ES agrees)
- Discount/premium of 1H range [grade g_pd]: Earns its place: removing it costs NQ -1420 (OOS -396, ES +604). candidates with it do better by 0.51R in the earlier folds (0/1 folds agree, out-of-sample confirms, ES agrees)
- Raid beyond 90m true open [grade (hard-coded weight)]: Earns its place: removing it costs NQ -1205 (OOS -236, ES +162). candidates with it do better by 0.60R in the earlier folds (0/2 folds agree, out-of-sample confirms, ES agrees)
- Value side of session VWAP [grade (hard-coded weight)]: Earns its place: removing it costs NQ -1090 (OOS -161, ES +687). candidates with it do better by 0.45R in the earlier folds (3/4 folds agree, out-of-sample confirms, ES agrees)
- High volume on trigger [grade (needs engine hook)]: Sign-stable and grade weight -2 passed every rule: NQ +104 (OOS +45, decide +59), ES +248, 2.8 trades/wk. Needs an engine hook before it can go live.

**PROBATION**
- Day already stretched (>=1.2x ADR) [grade (hard-coded weight)]: Removing it would help NQ but not on every rule (NQ +189 (OOS +0, decide +189), ES -173, 2.8 trades/wk; failed: out-of-sample folds +0, hurts ES -173).
- First hour of RTH [grade (hard-coded weight)]: Barely matters: removing it changes NQ only -59 (OOS +0, ES -99). Kept for now, re-tested every run. candidates with it do worse by 1.08R in the earlier folds (3/3 folds agree, out-of-sample does not confirm, ES agrees)
- 1H structure with trade [grade (hard-coded weight)]: Barely matters: removing it changes NQ only -56 (OOS +139, ES +61). Kept for now, re-tested every run. candidates with it do worse by 0.15R in the earlier folds (1/4 folds agree, out-of-sample does not confirm, ES agrees)
- 15m already aligned [grade (hard-coded weight)]: Barely matters: removing it changes NQ only -7 (OOS +0, ES +0). Kept for now, re-tested every run. candidates with it do worse by 0.16R in the earlier folds (1/2 folds agree, out-of-sample does not confirm, ES agrees)
- QT: entry in Q3 [grade g_q3]: Removing it would help NQ but not on every rule (NQ +44 (OOS +56, decide -12), ES -168, 2.8 trades/wk; failed: decide folds -12, hurts ES -168). candidates with it do worse by 0.99R in the earlier folds (3/3 folds agree, out-of-sample confirms, ES agrees)
- QT: sweep in Q2 [grade (hard-coded weight)]: Barely matters: removing it changes NQ only -143 (OOS +0, ES +110). Kept for now, re-tested every run. candidates with it do better by 0.88R in the earlier folds (2/2 folds agree, out-of-sample confirms, ES agrees)
- Big opening gap (>=0.35 ADR) [grade (needs engine hook)]: Sign-stable; grade weight +2 helped NQ overall (NQ +1251 (OOS +720, decide +531), ES -359, 2.8 trades/wk) but failed: hurts ES -359.
- Volume climax on raid [grade (hard-coded weight)]: Removing it would help NQ but not on every rule (NQ +1045 (OOS +722, decide +323), ES -716, 2.8 trades/wk; failed: hurts ES -716). candidates with it do worse by 0.90R in the earlier folds (3/3 folds agree, out-of-sample confirms, ES agrees)
- First 45m of session [grade g_early]: Removing it would help NQ but not on every rule (NQ +294 (OOS +470, decide -176), ES -544, 2.8 trades/wk; failed: decide folds -176, hurts ES -544). candidates with it do worse by 1.53R in the earlier folds (4/4 folds agree, out-of-sample confirms, ES agrees)
- Tight stop (<=1 ATR) [grade (needs engine hook)]: Sign-stable; grade weight +2 helped NQ overall (NQ +1252 (OOS +328, decide +924), ES -205, 2.8 trades/wk) but failed: hurts ES -205.

**RETIRED**
- Displacement (ATR) [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -98 (OOS +45, decide -143), ES +77, 2.8 trades/wk; decide folds -143).
- Strong displacement candle [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -2, NQ -81 (OOS +45, decide -126), ES +247, 2.8 trades/wk; decide folds -126).
- Toward nearest major liquidity [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -719 (OOS -328, decide -390), ES +308, 2.8 trades/wk; out-of-sample folds -328, decide folds -390).
- 1H structure with trade (score gate) [score gate w_htf]: Taking it out of the gate improved every test: NQ +468 (OOS +53, decide +416), ES +80, 2.9 trades/wk. candidates with it do worse by 0.15R in the earlier folds (1/4 folds agree, out-of-sample does not confirm, ES agrees)
- Stacked liquidity raid [grade g_stacked]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -1289 (OOS -286, decide -1003), ES -146, 2.8 trades/wk; out-of-sample folds -286, decide folds -1003).
- Bars to reclaim [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -588 (OOS -192, decide -397), ES +98, 2.8 trades/wk; out-of-sample folds -192, decide folds -397).
- Trigger closes in top 25% [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -97 (OOS +46, decide -143), ES +28, 2.8 trades/wk; decide folds -143).
- Swept overnight H/L [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ -725 (OOS -328, decide -397), ES +78, 2.8 trades/wk; out-of-sample folds -328, decide folds -397).

(16 more features retired as sign-flipping noise; 57 candidates waiting for more data.)
