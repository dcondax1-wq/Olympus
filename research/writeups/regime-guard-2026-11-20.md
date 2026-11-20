---
title: Regime guard - can a pre-session market signal (volatility risk premium, 1-year ATR percentile, 1-year trend-efficiency percentile, a 2-of-3 vote) tell 2026-like days from 2021-25-like days so LIT and ATLAS size down? No; nothing changed
family: filters
date: 2026-11-20
status: rejected (no change, no Decide card). live_model*.json, second_model.json, accounts and every engine file untouched.
summary: Lead round 2 (day-newstrat) - protect the accounts in a 2021-25-like market (LIT about $40 a month there, ATLAS funded 25K lost 94.5% of the time in 6 months). Four causal signals from the prior close, cuts fixed before the run (research/regime_guard/RULES.md) - G1 NQ 20-day realized vol above the prior VIX close, G2 NQ 20-day ATR in the bottom third of its last year, G3 NQ 20-day trend efficiency in the bottom third of its last year (chop), G4 2 of the 3 - each as half size or sit out for BOTH bots, 8 versions, judged on fixed $ (LIT $350 / ATLAS $250, costs in), the LIT Builder 50K eval (live two_week sizing, 600 paths) and the ATLAS funded Builder 25K Monte Carlo with the live stuck stop (600 paths; the no-guard row reproduces atlas-health's 8.5 / 9.2 / 94.5% exactly). 0 of 8 pass. None of the signals is more common in 2021-25 than in 2026 (bad-day share 2021-25 25-40% vs 2026 13-65%): the 2021-25 vs 2026 gap is not a market weather these signals see. Each one hurts LIT somewhere (2021-25 LIT goes from +$2,065 to -$1,801..-$5,933 under G1/G3/G4: LIT made its 2021-25 money on exactly the flagged days). One lead for later (post-hoc, not eligible): on chop days (G3) ATLAS's trades are worse in all three periods (H1 +0.49R vs +0.84R, H2 +0.32R vs +0.51R, 2021-25 -0.09R vs +0.10R), but sitting them out costs $778 a month of ATLAS fixed $ in Jan-Jun and $105 a month funded in Jul-Oct and still leaves 85.7% of 2021-25-like funded accounts lost.
runs: none (research/regime_guard/results.json; research/regime_guard/guard.py)
---

## For the owner

| What | Result |
|---|---|
| Can a simple signal before the open tell a "2026 market" from a "2021-25 market"? | **No.** The "bad" days are just as common in 2026 (often more) as in 2021-25 |
| Does sizing down on "bad" days save money in a 2021-25 market? | For LIT it **costs** money: 2021-25 goes from **+$2,065** to between **-$1,801 and -$5,933**. LIT made its old-year money on those days |
| ATLAS funded 25K, accounts lost in 6 months (2021-25 market) | 94.5% with no guard; best guard 85.7%: still lost almost every time |
| Cost of that best guard in 2026 | ATLAS funded **$581 -> $511** a month (Jan-Jun), **$491 -> $386** (Jul-Oct); first payout 18 -> 25 and 25 -> 35 sessions |
| Verdict | **0 of 8 pass, nothing changes.** The real protection stays what it is: the edge light (do not buy a new ATLAS account on RED) |

## What was already tested, and what is new
Already rejected: VIX level / change, VXN-VIX, VIX/VIX3M, GEX, prior-day range percentile as LIT size tilts
(`lit-regime-sizing-2026-11-17.md`); 40-session means of VIX, RTH range, overnight share, trend efficiency as a light
(`edge-health-2026-11-17.md`); 5/10-day efficiency and 1H ADX (`research/REGIME_REPORT.md`); ATLAS VIX < 15 skip.
New: the volatility risk premium (realized vs implied), ATR and 20-day trend efficiency as a trailing-year percentile, the
2-of-3 vote, and the test on both bots' account-loss odds at once. NQ/ES 20-day correlation was **not run**: ES daily bars
start 2025-04, so it cannot be checked on 2021-24.

## Rules (pre-registered `research/regime_guard/RULES.md`, plus a warm-up addendum before the first run)
Signals from NQ1! daily bars closed before the session and the prior CBOE VIX close (fresh file to Nov 19):
G1 RV20 > VIX; G2 ATR20/close in the bottom third of the last 252 sessions; G3 ER20 in the bottom third; G4 2 of 3.
Actions: half size or sit out, both bots. Gate: (1) bad days more common in 2021-25 than in each 2026 half, (2) trades on bad
days worse in every period for each bot, (3) 2021-25 $ up, 2026 halves down <= 10%, (4) ATLAS funded dead down in 2021-25 and
not up in 2026, funded $ not down > $10/mo, LIT eval pass not down > 2 points in 2026, fail down in 2021-25, (5) >= 2 trades a
week, (6) placebo (only for a passer: none).

## Full table
Fixed $ (LIT $350 / ATLAS $250, costs in). ATLAS funded = Builder 25K funded Monte Carlo with the live stuck stop ($ a month to
you / accounts lost in 6 months). LIT eval = Builder 50K, 60 sessions, pass / fail %. H2 = Jul 1 - Oct 16.

| Version | Bad days H1 / H2 / 21-25 | LIT $ H1 / H2 / 21-25 | ATLAS $ H1 / H2 / 21-25 | ATLAS funded $/mo, lost % H1 / H2 / 21-25 | LIT eval pass/fail H1 / H2 / 21-25 | Why it fails (first) |
|---|---|---|---|---|---|---|
| no guard | 0 / 0 / 0% | $20,868 / $9,659 / $2,065 | $18,362 / $5,256 / $10,393 | $581 8.5% / $491 9.2% / $45 94.5% | 84.8/11.3, 84.3/11.5, 32.3/53.8 | - |
| G1 VRP half | 33 / 65 / 33% | $18,897 / $7,231 / -$1,801 | $12,988 / $2,598 / $6,578 | $546 8.8% / $447 3.3% / $45 93.0% | 89.5/6.0, 78.7/8.2, 26.5/45.0 | flags 2026 H2 most (65%) |
| G1 VRP out | 33 / 65 / 33% | $17,299 / $5,701 / -$4,667 | $9,193 / $1,589 / $5,227 | - / - / 92.8% lost | 87.0/7.5, 72.8/8.7, 24.5/44.2 | same; LIT and ATLAS $ fall everywhere |
| G2 quiet half | 13 / 44 / 40% | $18,305 / $4,187 / $3,962 | $18,271 / $3,758 / $10,539 | $585 8.0% / $517 4.0% / $47 91.0% | 86.7/7.8, **45.7**/15.8, 30.0/31.8 | Jul-Oct was quiet AND LIT's best: LIT eval pass 84 -> 46% |
| G2 quiet out | 13 / 44 / 40% | $16,198 / $779 / $6,117 | $18,579 / $3,777 / $11,653 | - / 8.3% / 86.5% | 82.0/9.7, **37.2**/15.2, 30.5/23.0 | LIT Jul-Oct $9,659 -> $779 |
| G3 chop half | 34 / 36 / 31% | $15,939 / $10,090 / -$2,068 | $15,758 / $4,418 / $14,066 | $582 5.7% / $467 9.5% / $53 90.7% | 84.7/8.3, 90.3/3.8, 27.7/46.7 | chop is as common in 2026; LIT loses 2021-25 |
| G3 chop out | 34 / 36 / 31% | $11,597 / $10,372 / -$5,079 | $13,616 / $4,205 / $17,318 | $511 6.2% / $386 7.3% / $59 85.7% | 75.5/13.2, 91.3/3.7, 24.8/44.5 | ATLAS Jan-Jun -$4,746, funded Jul-Oct -$105/mo |
| G4 vote half | 21 / 45 / 25% | $18,662 / $7,915 / -$2,876 | $17,433 / $4,353 / $13,567 | $574 7.3% / $508 3.2% / $51 92.0% | 87.7/7.3, 77.8/7.7, 28.7/50.8 | flags 2026 H2 most; LIT loses 2021-25 |
| G4 vote out | 21 / 45 / 25% | $16,673 / $7,193 / -$5,933 | $16,318 / $4,315 / $16,615 | - / 1.0% / 90.3% | 82.2/10.2, 80.2/6.2, 25.3/48.3 | same |

Average R a trade on bad days vs other days (fixed $ / risk):

| Signal | LIT H1 | LIT H2 | LIT 21-25 | ATLAS H1 | ATLAS H2 | ATLAS 21-25 |
|---|---|---|---|---|---|---|
| G1 VRP | 0.46 vs 0.85 | 0.51 vs 0.91 | **0.13 vs -0.04** | 1.08 vs 0.53 | 0.49 vs 0.40 | 0.06 vs 0.03 |
| G2 quiet | 0.95 vs 0.70 | 1.10 vs 0.13 | -0.05 vs 0.06 | -0.06 vs 0.83 | 0.28 vs 0.60 | -0.01 vs 0.08 |
| G3 chop | 1.10 vs 0.59 | -0.15 vs 1.14 | 0.12 vs -0.04 | **0.49 vs 0.84** | **0.32 vs 0.51** | **-0.09 vs 0.10** |
| G4 vote | 0.92 vs 0.71 | 0.37 vs 0.98 | 0.17 vs -0.04 | 0.41 vs 0.78 | 0.21 vs 0.62 | -0.10 vs 0.09 |

## Findings
1. **The old-year / 2026 gap is not market weather.** None of these signals is more frequent in 2021-25: G1 and G4 fire most in
   Jul-Oct 2026 (LIT's good stretch). So "sit out the bad regime" would mostly sit out 2026.
2. **LIT's 2021-25 money is made on the flagged days.** Under G1, G3 and G4 LIT's 2021-25 trades on bad days are positive
   and the rest negative; sizing down turns LIT's small 2021-25 profit into a loss.
3. **ATLAS on chop days (G3) is the one consistent pattern** (worse in all three periods, both bots' gate failed on LIT and on
   separation). Post-hoc for ATLAS alone; worth a ZEUS Lab paper entry, not a switch: sitting out costs ATLAS $4,746 in Jan-Jun
   and still loses 85.7% of 2021-25-like funded accounts.
4. **No guard rescues ATLAS's funded account in a 2021-25 market** (best 85.7% lost vs 94.5%). The protection that works is
   upstream: the edge light's "do not buy on RED" and the size already set by the stuck stop.

## Files
`research/regime_guard/RULES.md`, `research/regime_guard/guard.py` (`python -X utf8 research/regime_guard/guard.py`, ~90 s),
`research/regime_guard/results.json`.
