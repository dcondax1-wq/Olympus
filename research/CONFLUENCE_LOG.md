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

## Confluence learning cycle 2026-10-16 16:00 (run 20261016-160231)
Data: NQ futures 2021-10-18..2026-10-16 (1293 sessions, 1802 candidates, 1054 trades) · ES futures check (391 sessions, 336 trades). No CFD data.
Folds: F1 2021-10..2022-12 (decide, 312s), F2 2023-01..2023-12 (decide, 258s), F3 2024-01..2024-12 (decide, 259s), F4 2025-01..2025-12 (confirm, 258s), F5 2026-01..2026-10 (confirm, 206s)
Baseline: NQ $+9516 (4.1/wk; folds $-4219 4.1/wk, $-781 5.3/wk, $+4890 4.4/wk, $+100 3.6/wk, $+9526 2.6/wk), ES $-11765.

6 active, 10 probation, 25 candidate, 65 retired (76 tests, 30 backtests, 102.5s). No change passed the adoption rule; the current grade stays as it is.

**ACTIVE**
- Day already stretched (>=1.2x ADR) [grade (hard-coded weight)]: Earns its place: removing it costs NQ -465 (OOS -169, ES -5).
- First hour of RTH [grade (hard-coded weight)]: Earns its place: removing it costs NQ -710 (OOS -58, ES -136). candidates with it do better by 0.13R in the earlier folds (3/5 folds agree, out-of-sample confirms, ES disagrees)
- 1H structure with trade (score gate) [score gate w_htf]: Earns its place: removing it costs NQ -10524 (OOS -4178, ES -502). candidates with it do better by 0.05R in the earlier folds (2/5 folds agree, out-of-sample does not confirm, ES disagrees)
- 15m already aligned (score gate) [score gate w_m15]: Earns its place: removing it costs NQ -646 (OOS -3392, ES -1713). candidates with it do worse by 0.07R in the earlier folds (4/5 folds agree, out-of-sample confirms, ES disagrees)
- Discount/premium of 1H range (score gate) [score gate w_pd]: Earns its place: removing it costs NQ -3038 (OOS -6118, ES +7857). candidates with it do worse by 0.20R in the earlier folds (1/5 folds agree, out-of-sample does not confirm, ES disagrees)
- Raid beyond 90m true open [grade (hard-coded weight)]: Earns its place: removing it costs NQ -217 (OOS -1263, ES +1182). candidates with it do worse by 0.07R in the earlier folds (2/5 folds agree, out-of-sample confirms, ES agrees)

**PROBATION**
- Low-resistance path (LRL) (score gate) [score gate w_lrl]: Removing it would help NQ but not on every rule (NQ +1982 (OOS -3258, decide +5240), ES +6220, 2.0 trades/wk; failed: F1 1.9 trades/week, F4 1.6 trades/week). candidates with it do worse by 0.03R in the earlier folds (3/5 folds agree, out-of-sample confirms, ES agrees)
- 1H structure with trade [grade (hard-coded weight)]: Removing it would help NQ but not on every rule (NQ +299 (OOS +385, decide -86), ES +899, 4.1 trades/wk; failed: F2 5.3 trades/week, decide folds -86). candidates with it do better by 0.05R in the earlier folds (2/5 folds agree, out-of-sample does not confirm, ES disagrees)
- Low-resistance path (LRL) [grade (hard-coded weight)]: Removing it would help NQ but not on every rule (NQ +177 (OOS -1614, decide +1790), ES +1779, 4.1 trades/wk; failed: F2 5.3 trades/week, out-of-sample folds -1614). candidates with it do worse by 0.03R in the earlier folds (3/5 folds agree, out-of-sample confirms, ES agrees)
- 15m already aligned [grade (hard-coded weight)]: Removing it would help NQ but not on every rule (NQ +32 (OOS +33, decide -0), ES +211, 4.1 trades/wk; failed: F2 5.3 trades/week, decide folds -0). candidates with it do worse by 0.07R in the earlier folds (4/5 folds agree, out-of-sample confirms, ES disagrees)
- Discount/premium of 1H range [grade g_pd]: Removing it would help NQ but not on every rule (NQ +647 (OOS -1068, decide +1716), ES +1498, 4.0 trades/wk; failed: F2 5.3 trades/week, out-of-sample folds -1068). candidates with it do worse by 0.20R in the earlier folds (1/5 folds agree, out-of-sample does not confirm, ES disagrees)
- QT: entry in Q3 [grade g_q3]: Barely matters: removing it changes NQ only -934 (OOS +274, ES -111). Kept for now, re-tested every run. candidates with it do better by 0.03R in the earlier folds (2/5 folds agree, out-of-sample confirms, ES disagrees)
- QT: sweep in Q2 [grade (hard-coded weight)]: Barely matters: removing it changes NQ only -93 (OOS -56, ES +607). Kept for now, re-tested every run. candidates with it do worse by 0.08R in the earlier folds (2/5 folds agree, out-of-sample does not confirm, ES agrees)
- Volume climax on raid [grade (hard-coded weight)]: Removing it would help NQ but not on every rule (NQ +338 (OOS +1513, decide -1176), ES -1370, 4.1 trades/wk; failed: F2 5.3 trades/week, decide folds -1176). candidates with it do better by 0.16R in the earlier folds (4/5 folds agree, out-of-sample confirms, ES agrees)
- Value side of session VWAP [grade (hard-coded weight)]: Removing it would help NQ but not on every rule (NQ +571 (OOS -506, decide +1076), ES +2498, 4.1 trades/wk; failed: F2 5.3 trades/week, out-of-sample folds -506). candidates with it do worse by 0.14R in the earlier folds (3/5 folds agree, out-of-sample confirms, ES disagrees)
- First 45m of session [grade g_early]: Removing it would help NQ but not on every rule (NQ +1869 (OOS +1103, decide +766), ES -86, 4.1 trades/wk; failed: F2 5.3 trades/week, hurts ES -86). candidates with it do better by 0.23R in the earlier folds (4/5 folds agree, out-of-sample does not confirm, ES disagrees)

**RETIRED**
- CISD trigger (no IFVG) [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight +2, NQ +1018 (OOS +1038, decide -20), ES -862, 4.1 trades/wk; F2 5.3 trades/week, decide folds -20).
- 3R+ room to major liquidity [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -2, NQ +1828 (OOS -1029, decide +2856), ES +1825, 4.1 trades/wk; F2 5.3 trades/week, out-of-sample folds -1029).
- Room to major liquidity (R) [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -2, NQ +1294 (OOS -844, decide +2138), ES +1792, 4.1 trades/wk; F2 5.3 trades/week, out-of-sample folds -844).
- FOMC day [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -2, NQ +118 (OOS +61, decide +57), ES -182, 4.1 trades/wk; F2 5.3 trades/week, hurts ES -182).
- Inside news window [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ +0 (OOS +0, decide +0), ES +0, 4.1 trades/wk; F2 5.3 trades/week, out-of-sample folds +0).
- Raid beyond session true open [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight +1, NQ -161 (OOS -406, decide +245), ES -308, 4.1 trades/wk; F2 5.3 trades/week, out-of-sample folds -406).
- Raid beyond weekly open [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -2, NQ +1058 (OOS -520, decide +1578), ES +2755, 4.1 trades/wk; F2 5.3 trades/week, out-of-sample folds -520).
- Fading today's direction [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -2, NQ +891 (OOS -1003, decide +1894), ES +1751, 4.1 trades/wk; F2 5.3 trades/week, out-of-sample folds -1003).
- Prior day range vs ADR [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: hard gate: skip when present, NQ +2211 (OOS -1252, decide +3464), ES +6511, 2.0 trades/wk; F4 1.9 trades/week, F5 1.1 trades/week).
- Shallow raid (<0.5 ATR) [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: score gate w_shallow=-1, NQ +3294 (OOS +970, decide +2324), ES -1044, 3.8 trades/wk; F2 5.1 trades/week, hurts ES -1044).
- CISD trigger [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight +2, NQ +1018 (OOS +1038, decide -20), ES -862, 4.1 trades/wk; F2 5.3 trades/week, decide folds -20).
- Long side [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight +1, NQ +875 (OOS +263, decide +612), ES +233, 4.1 trades/wk; F2 5.3 trades/week).
- Monday [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: hard gate: skip when present, NQ +2866 (OOS +62, decide +2803), ES -215, 3.2 trades/wk; F5 1.9 trades/week, hurts ES -215).
- Trigger closes in top 25% [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight -1, NQ +1743 (OOS +601, decide +1143), ES +1343, 4.1 trades/wk; F2 5.3 trades/week).
- Swept Asia H/L [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight +2, NQ +1905 (OOS +1612, decide +292), ES +190, 4.1 trades/wk; F2 5.3 trades/week).
- Swept overnight H/L [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight +2, NQ +2547 (OOS +1918, decide +629), ES -1265, 4.1 trades/wk; F2 5.3 trades/week, hurts ES -1265).
- Swept prior-week H/L [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: hard gate: skip when present, NQ +990 (OOS +74, decide +916), ES +176, 4.0 trades/wk; F2 5.2 trades/week).
- Trigger closes weak [grade (needs engine hook)]: Sign-stable on candidates, but no weight or filter improved the futures backtest (best: grade weight +2, NQ +199 (OOS +156, decide +43), ES -156, 4.1 trades/wk; F2 5.3 trades/week, hurts ES -156).

(47 more features retired as sign-flipping noise; 25 candidates waiting for more data.)
