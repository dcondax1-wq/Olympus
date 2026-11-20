# Regime guard: pre-registered rules (written 2026-11-20 ~06:25 ET, BEFORE any run; nothing changed after results)

Question (lead, round 2): can a simple, causal signal known before the session tell "2026-like" days from "2021-25-like" days,
so LIT (Zlarior) and ATLAS size down or sit out in the bad regime? Code: `research/regime_guard/guard.py`.

## Already tested (not repeated)
- VIX level / 1-day change, VXN-VIX, VIX/VIX3M, GEX, prior session's range percentile as LIT size tilts (`lit-regime-sizing-2026-11-17.md`).
- 40-session means of VIX, RTH range %, overnight share, trend efficiency, sweep reclaim as a light (`edge-health-2026-11-17.md`).
- 5/10-day efficiency, 1H ADX as a size rule (`research/REGIME_REPORT.md`); ATLAS VIX < 15 skip (post-hoc knife edge).
## New here
Volatility risk premium (VIX minus NQ's own 20-day realized vol), NQ's 20-day ATR as a trailing-1-year percentile, NQ's 20-day
trend efficiency as a trailing-1-year percentile, and a 2-of-3 vote; judged on BOTH bots' money and account-loss odds.
NQ/ES 20-day correlation: ES daily bars start 2025-04, so it cannot be checked on 2021-24: NOT run (said, not hidden).

## Signals (all from daily NQ1! bars closed BEFORE the session + the prior CBOE VIX close; no fitting, cuts fixed here)
- **G1 VRP:** RV20 = stdev of the last 20 daily log returns x sqrt(252) x 100. Bad = RV20 > prior VIX close (realized above implied).
- **G2 quiet:** ATR20 / close, percentile within the last 252 sessions. Bad = bottom third (< 33.3%).
- **G3 chop:** ER20 = |close - close 20 ago| / sum of the 20 |daily changes|, percentile within the last 252 sessions. Bad = bottom third.
- **G4 vote:** bad when at least 2 of G1-G3 are bad.
## Actions (each signal x each action = 8 versions)
- **A half:** bad day -> both bots at half size.  **B out:** bad day -> both bots sit out.
## Data / money
LIT: the 631 stored live trades (tools/account4_sim). ATLAS: the live ATLAS account stream (tools/atlas_health.stream).
Fixed view: LIT $350, ATLAS $250 a trade x weight, costs in. Periods: 2026 Jan-Jun, 2026 Jul-Oct 16, 2021-11..2025-12.
Accounts: ATLAS funded Builder 25K Monte Carlo (tools/atlas_health.score: 600 paths x 126 sessions, live stuck stop, dead = floor
or stuck); LIT eval Builder 50K (the live two_week sizing, tools/account4_sim.eval_stats, 600 paths, 60 sessions; half size =
the trade's micros halved via risk x2, out = trade removed).
## Pass gate (ALL, per bot; a version passes if it passes for at least one bot without hurting the other beyond the same limits)
1. Separation: bad-day share in 2021-25 > bad-day share in each 2026 half.
2. Edge: avg R of trades on bad days < avg R on other days in EACH period (2021-25, H1, H2).
3. Fixed $: 2021-25 net higher; H1 and H2 net each lower by at most 10%.
4. Accounts: ATLAS funded dead-in-6-months lower in 2021-25 and not higher in H1/H2, funded $/month not lower by > $10 in H1/H2;
   LIT eval 60-session pass not lower by > 2 points in H1/H2 and fail lower in 2021-25.
5. Trades a week: >= 2.0 in H1 and H2 for each bot.
6. Placebo: the same count of random days (40 draws) - the version's 2021-25 $ gain beats >= 90% of them.
A Decide card only for a full pass.
