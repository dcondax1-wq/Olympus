# LIT entry refinement on 1m bars (2026-11-26)

PAPER RESEARCH ONLY, no live_model*.json change. Pre-registered first (`research/entryfine/DESIGN.md`, committed before the run).
Code `research/entryfine/entryfine.py` -> `results.json`. Engine = engine/lit.run_x with the live params. Only the price where
the 5m-CISD limit "taps" or fills changes (simulate_x is wrapped; the engine file is not edited). Stop, size, target and costs
are unchanged. Sessions 2021-11-08 .. 2026-11-20.

## Verdict: today's entry wins. 0 of 5 pass. The 1m CISD confirmation is what carries LIT's edge.
| Version | Trades/wk H1 / H2 | PF H1 / H2 / 2021-25 | $/month H1 / H2 / 2021-25 | 50K 2-wk pass H1 / H2 (median sessions) | 50K 40-session pass / fail 2021-25 | Fresh Oct19-Nov20 | Max DD 2021-25 | Walk-fwd |
|---|---|---|---|---|---|---|---|---|
| **E0 live (limit at the CISD level, then the 1m CISD)** | 3.12 / 2.56 | 4.98 / 2.91 / 1.01 | $5,562 / $2,670 / $25 | 44.5 / 39.1 (6 / 4) | 23.2 / 53.9 | -$858 | -$19,426 | - |
| E1 tap must trade 1 tick through | 3.16 / 2.50 | 4.50 / 2.56 / 0.91 | $5,280 / $2,227 / -$171 | 43.7 / 39.1 (6 / 5) | 17.3 / 58.2 | -$858 | -$24,912 | 3/18 |
| E2 tap at 50% of the zone | 1.17 / 1.15 | 6.26 / 2.68 / 1.18 | $3,172 / $1,546 / $134 | 37.8 / 29.0 (6.5 / 7) | 18.3 / 22.6 | +$16 | -$8,378 | 5/18 |
| E3 limit expiry 20 min | 2.97 / 2.37 | 4.86 / 2.92 / 0.98 | $5,266 / $2,506 / -$37 | 44.5 / 37.7 (6 / 4) | 23.1 / 56.3 | -$858 | -$20,722 | 8/18 |
| E4 plain limit at 50%, no 1m CISD | 2.42 / 1.73 | 1.11 / 3.02 / 1.35 | $402 / $4,714 / $1,397 | 16.8 / 29.0 (10.5 / 6) | 22.0 / 78.0 | -$5,555 | -$25,467 | 8/18 |
| E5 plain limit at the level, filled only 1 tick through | 3.67 / 3.14 | 2.17 / 2.09 / 0.93 | $3,036 / $2,087 / -$305 | 31.1 / 21.7 (3.5 / 10) | 21.1 / 78.9 | -$2,664 | -$31,027 | 5/18 |
Limit expiry 45 / 60 min: run 2026-11-25 (research/moretrades L6 / L7). Same as today in 2026, worse in 2021-25 (-$46 / -$147 a month). Rejected.

- **Placement (E1, E2):** needing a tick through costs money in every span. A deeper tap at 50% gives a cleaner PF but cuts
  trades to ~1.2 a week, below the 2-4 a week rule, and passes fewer evals (37.8 / 29.0). Today's tap at the level is the best.
- **Limit vs 1m CISD (E4, E5):** with no confirmation, H1 2026 collapses (PF 1.1-2.2) and 2-week passes drop to 17-31%. E4's
  2021-25 +$1,397 a month comes from 5m-only fills there; it loses Jan-Jun and the fresh weeks (-$5.6k). That is not a pass.
- **Partial fills (E5 = a bare touch does not fill):** the honest version of a plain limit. It is the worst of the 1m-free
  versions. The live entry is a market order after the 1m CISD, so queue position / partial fills do not apply to it.
- **Expiry 20 min (E3):** slightly fewer trades, less money in both halves.
