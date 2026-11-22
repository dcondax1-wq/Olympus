---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/blitz
type: "research"
date: "2026-11-13"
status: "no adopt-candidate; one promising paper lead, the gap fade G1 (holds in H1, H2, 2025 and 2021-24; coin-flip placebo p 0.003 over 2021-25 but 0.22 in 2026; 1.7 trades a week; 1 micro in 2026, so an ..."
source: "research/writeups/nq-new-strategies-2026-11-13.md"
aliases:
  - "New NQ strategies for more eval accounts"
---

# New NQ strategies for more eval accounts

> [!success] Verdict: adopt-candidate
> no adopt-candidate; one promising paper lead, the gap fade G1 (holds in H1, H2, 2025 and 2021-24; coin-flip placebo p 0.003 over 2021-25 but 0.22 in 2026; 1.7 trades a week; 1 micro in 2026, so an MFFU eval passes 0-7% in 2 weeks and the slot makes about $0 a month). BLITZ: both new band angles fail 2021-25, so it stays as built. A third or fourth eval account running a new strategy does not raise $/month or pass odds.

**Full title:** New NQ strategies for more eval accounts (Team E2, 2026-11-13). Seven new families, one real but small edge (the gap fade after a failed opening drive), no new eval account worth buying, BLITZ unchanged

## Summary

Owner - "Find every edge in trading ... build bots that will make me money. Mainly NQ." Team E2 looked for new NQ strategies uncorrelated with LIT / ATLAS / BLITZ, so the owner could run more evals on different signals. Each hypothesis was written before the run, with a new angle against the rejected list. Seven families, 140 variants on CME NQ1! 5m RTH (2021-11 to 2026-10-16, ES1! from 2025-04), $500 risk a trade, costs in, every stop 1 tick beyond the setup's structure. The families were an ORB with a failed-breakout filter, a prior-day high/low sweep with climax volume, NQ/ES relative strength at the open, the overnight gap fade with a failed-drive and volume test, VWAP reversion on low-VIX days, end-of-day breaks and reversals, and a CPI/NFP/FOMC playbook. 2 of 140 variants hold in all four spans (H1, H2, 2025, 2021-24), against 0.75 on average when the directions are coin flips (20 seeds): about chance for the whole grid. One family stands out, the gap fade (positive in 22/24/20 of 24 variants in H2 / 2025 / 2021-24). Its new filter is the one that matters. The same gap fade without the failed-drive test loses in 3 of 4 spans. G1 (gap >= 0.1 x the 14-day range, the 09:30-10:00 range closes in the half away from the gap, stop 1 tick beyond that range, 2R) makes +$180 a month in 2026 (PF 1.14) and +$496 a month in 2021-25 (PF 1.34). Its daily correlation is 0.03 / -0.04 with LIT, -0.02 / 0.00 with ATLAS and 0.08 / 0.12 with BLITZ. Its 2026 stops are about 145 points, so $500 buys 1 micro and an MFFU eval cannot be passed in 2 weeks. On its own 25K / 50K it passes 0-7% of 2026 evals in 2 weeks, and the slot makes -$6 to +$29 a month in 2026. As a small add-on on LIT's funded 50K it is +$23 in H1 and -$16 in H2, so it fails too. BLITZ band angles - the paper's gap-aware band is better in both 2026 halves ($936 / $771 vs $912 / $577 a month at $150) but loses in 2021-25 (-$15 vs +$89 a month); the implied-volatility band is worse. Nothing changes.

## Money first

**Nothing new to switch on, and no new eval account to buy.** One family has a real but small edge (the gap fade G1). Its
stops are too wide for a prop eval, so it stays a paper lead. BLITZ stays exactly as built.

All rows are at $500 risk a trade with costs in ($1.90 a micro, 1 tick on every fill), on CME NQ1! 5m. The eval
columns are the run library's MFFU 50K started on every 2026 session at that size.

| Strategy (pick) | 2026 $ / month | 2021-25 $ / month | Trades / week (2026 / 21-25) | PF (2026 / 21-25) | Max DD (2026 / 21-25) | Corr with LIT (daily, 2026 / 21-25) | 50K eval 2-week pass / fail (2026) | Verdict |
|---|---:|---:|---|---|---|---|---|---|
| **Gap fade after a failed opening drive (G1)** | **+$180** | **+$496** | 1.8 / 1.8 | 1.14 / 1.34 | -$4,377 / -$4,072 | 0.03 / -0.04 | 0.0 / 0.0 (median pass 27 sessions) | **paper lead**: holds in all four spans, but too slow for an eval |
| ORB, 2nd side after a failed break (H1 pick) | +$706 | +$184 | 1.5 / 1.8 | 1.87 / 1.16 | -$878 / -$6,892 | 0.07 / 0.00 | 0.0 / 0.0 | rejected: loses in H2 and 2025 |
| Prior-day high / low sweep (H1 pick; the volume gate made it worse) | +$170 | -$152 | 1.0 / 1.0 | 1.14 / 0.89 | -$2,661 / -$14,207 | -0.03 / 0.03 | 0.0 / 17.6 | rejected |
| NQ leads ES at 10:00 (H1 pick; ES only from 2025-04) | +$424 | +$72 (2025 May-Dec only) | 1.3 / 0.2 | 1.46 / 1.41 | -$3,740 / -$2,028 | -0.07 / -0.05 | 0.0 / 0.0 | rejected: loses in H2 |
| Gap fade, H1 pick (gap >= 0.25, 15-min range) | +$198 | +$171 | 1.4 / 1.3 | 1.17 / 1.13 | -$3,952 / -$7,373 | -0.01 / 0.01 | 0.0 / 0.0 | rejected: loses in H2 (G1 is its neighbour) |
| VWAP reversion on low-VIX days (H1 pick) | +$602 | -$665 | 2.4 / 2.4 | 1.25 / 0.76 | -$4,720 / -$36,835 | 0.11 / 0.07 | 9.0 / 13.1 | rejected: loses in 2025 and 2021-24 |
| End of day: fade a 1.5-sigma day at 15:00 (H1 pick) | +$73 | -$498 | 1.1 / 1.2 | 1.06 / 0.67 | -$4,228 / -$28,342 | -0.03 / 0.01 | 5.0 / 4.5 | rejected |
| CPI / NFP / FOMC playbook | n/a | n/a | 0.1-0.2 | - | - | - | - | rejected: 3-7 trades a half year, no variant reaches 12 in H1 |
| Book of all H1 picks on one account (one position) | +$1,654 | -$709 | 6.1 / 6.0 | 1.32 / 0.89 | -$6,598 / -$49,797 | -0.02 / 0.04 | 20.6 / 33.2 | rejected: the 2026 H1 picks lose over 5 years |
| BLITZ with the gap-aware band (at $150) | $936 / $771 (H1 / H2) | -$15 | 6.8 / 4.8 / 6.2 | 1.86 / 2.31 / 0.99 | -$931 / -$550 / -$5,963 | - | - | rejected: 2021-25 worse than today's +$89 |
| BLITZ with the implied-volatility band (at $150) | $585 / -$8 | +$10 | 4.6 / 3.5 / 4.6 | 1.76 / 0.99 / 1.01 | - | - | - | rejected |

**The third (or fourth) eval account question.** The best new strategy, G1, on its own MFFU account. Sizes were picked on
2026 H1 only. These are 1,000-path Monte Carlo runs (500 for the slot), MFFU Builder rules, 80% split and 2 sessions of paperwork.

| G1 on its own account | 2-week pass / fail, H1 / H2 / 2025 / 2021-24 | Slot $ / month to you, net of every eval (H1 / H2 / 2025 / 2021-24) |
|---|---|---:|
| Builder 25K ($63): eval 50% of the room, funded 40% <= $1,000 | 5.0/0.0, 2.6/0.0, 13.0/0.6, 9.0/0.2 (70% of the room: 7.0/0.2 ...) | -$6 / +$6 / +$41 / $0 |
| Builder 50K ($91.80): eval 30-50% of the room, funded 40% <= $1,000 | 7.2/0.0, 6.8/0.0, 17.6/1.0, 11.8/1.0 | -$3 / +$16 / +$90 / +$8 |
| For comparison: BLITZ's 25K slot (v2, `blitz-edge-2026-10-30b.md`) | 47.9/23.5, 36.2/21.7, 24.7/48.4 (H1 / H2 / 2021-25) | $286 / $52 / -$39 (H1 / H2 / 2021-25) |
| G1 as an add-on on LIT's funded 50K (10% of the room <= $400, never while LIT holds) | (funded only) | LIT alone $923 / $910 / $74 / $56 -> $946 / $894 / $109 / $72 |

- **No.** A new eval account running G1 would almost never be decided within 2 weeks (0-7% in 2026; the owner's rule is
  decided in 2 weeks, passed in 3). Over 6 months its slot makes about $0 a month in 2026.
- MFFU also allows only 3 funded accounts per person. LIT 50K + ATLAS 25K + BLITZ 25K already fill them
  (`2026-11-04_second_strategies_night.md`). A G1 account would have to replace BLITZ, which makes more in 2026, or sit
  at another firm, where it pays the same ~$0.
- As an add-on on LIT's funded 50K it is mixed: +$23 in H1, -$16 in H2, +$35 in 2025, +$16 in 2021-24. That fails the
  "better in both 2026 halves" test. Not proposed.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-13]]
- Strategies: [[BLITZ (paper)]]
- Refers to: [[2026-11-04_second_strategies_night|Second strategies night]], [[atlas-blitz-edge-2026-10-30|ATLAS + BLITZ edge night]], [[blitz-edge-2026-10-30b|BLITZ edge, rounds 2-4]], [[quant-anomalies|Quant anomalies on CME NQ]], [[scalp-na-mffu|BLITZ]]
- Runs: `e2_gapfade_g1, e2_orb2_h1pick, e2_pdx_h1pick, e2_rs_h1pick, e2_gapf_h1pick, e2_vwr_h1pick, e2_eod_h1pick, e2_book_h1picks`
- Source: `research/writeups/nq-new-strategies-2026-11-13.md`
- Back to [[ZEUS Home]]
