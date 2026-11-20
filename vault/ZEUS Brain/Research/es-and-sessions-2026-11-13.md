---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-11-13"
status: "rejected (no adopt-candidate, no paper lead). LIT on ES loses in 2026 H1 and in 2025 even before costs; ATLAS on ES has a small edge before costs that the MES tick and commission eat (7-13% of R a ..."
source: "research/writeups/es-and-sessions-2026-11-13.md"
aliases:
  - "Same edge, more markets"
---

# Same edge, more markets

> [!failure] Verdict: rejected
> rejected (no adopt-candidate, no paper lead). LIT on ES loses in 2026 H1 and in 2025 even before costs; ATLAS on ES has a small edge before costs that the MES tick and commission eat (7-13% of R a trade vs 2.5-5% on NQ); the NQ NY slot and the ES London / NY slots fail at least one span and trade about 1-2 a week. The Asia slot was not redone (lit-more-entries.md lead 1, still a paper shadow).

**Full title:** Same edge, more markets (Team E3, 2026-11-13). LIT and ATLAS on ES (MES) and in other session slots, as a 2nd signal stream for more prop accounts. Nothing passes; ES costs eat the edge

## Summary

Owner - "Find every edge in trading ... build bots that will make me money ... think like a millionaire." MFFU's 3 funded slots are full, so the money question is a second, weakly correlated signal stream with similar eval pass odds that can run at other prop firms. Team E3 ran the proven LIT (engine/lit.py, live_model.json "lit") and the three ATLAS members (EMA / MD / S/R exactly as second_model.json, our NQ re-run = the stored research trades, 636/636, 387/387, 372/372) unchanged on CME ES1!, with only the point settings scaled by the ES/NQ price ratio (k = 0.28; neighbours x0.8 / x1.25 and three BE offsets), traded as MES. ES data exists only from 2025-04-14 and only on 5m (no ES 1m file, no ES 2021-24), so ES runs on 5m execution and the fair comparison is NQ on 5m execution too. Each stream got its own MFFU eval (LIT on a Builder 50K with the live two_week sizing, ATLAS on a Builder 25K with the account-B preset). LIT on ES - H1 -$3,838 (PF 0.78), H2 +$12,670 (PF 2.27), 2025 Apr-Dec -$15,936 (PF 0.44); NQ on the same 5m execution makes +$6,576 / +$1,474 / -$505. Own 50K 2-week pass/fail H1 27.7/10.9, H2 44.9/15.9, 2025 9.0/16.4 vs NQ LIT live 57.1/1.7, 52.2/5.8. Daily correlation with NQ LIT 0.14 in 2026 (shuffled-day noise band 0.13). ATLAS on ES - H1 -$6,251, H2 +$2,191, 2025 -$2,785 (PF 0.85 / 1.09 / 0.95) vs NQ ATLAS on the same rules +$47,285 / +$12,105 / +$13,013. Before costs ES ATLAS is +$1.1k / +$7.3k / +$10.2k: the setups are real but ES's structural stops are about 2.5x smaller in MNQ-equivalent terms while the tick stays 0.25, so costs take 7-13% of R a trade. Session slots - NQ LIT NY-only (08:00-15:30) as its own account H1 +$12,797 / H2 -$1,185 / 2025 -$2,621 at 1.0 trade a week; ES London-only H1 -$6,817; ES NY-only H2 -$2,237. Nothing passes. Best second stream for other firms stays NQ ATLAS itself (corr with LIT 0.09).

## Money first

**Nothing to switch on, and no ES account to buy.** LIT and ATLAS do not carry over to ES as they are. The NY-only and
London-only slots do not give a second stream that holds either.

All rows have costs in: $1.90 a micro round trip and 1 tick of slippage, plus MES $5 an ES point. ES is shown as
MNQ-equivalent $, so one MES equals one MNQ in the sizing. LIT rows use the LIT size ($800 up to a 20-pt stop, then
800 x 20 / stop). ATLAS rows use $500 a trade, one position at a time, at most 2 a day.

The eval column is each stream on **its own** MFFU account, started fresh on every session of the span:
- LIT on a Builder 50K, with the live two_week sizing.
- ATLAS on a Builder 25K, with the account-B preset.

"History" means 2025-04-14 to 2025-12-31 for every row, because ES starts there. "Corr" is the daily P&L correlation with
NQ LIT (run `lit_live`) in 2026, over every session, counting days with no trade as 0.

| Stream (variant) | 2026 $/mo | H1 / H2 net $ | History $/mo (2025 Apr-Dec) | Trades/wk 2026 | PF H1 / H2 / 2025 | Corr with NQ LIT (2026) | Own eval 2-wk pass / fail (H1 · H2) | Verdict |
|---|---:|---|---:|---:|---|---:|---|---|
| NQ LIT live (reference, 1m execution in 2026) | +$4,435 | +$33,666 / +$9,836 | -$114 | 2.91 | 4.92 / 2.88 / 0.93 | 1.00 | 57.1 / 1.7 · 52.2 / 5.8 | live |
| NQ LIT on 5m execution (the fair ES comparison) | +$821 | +$6,576 / +$1,474 | -$57 | 1.87 | 1.87 / 1.38 / 0.96 | 0.53 | 26.9 / 9.2 · 34.8 / 0.0 | reference |
| **LIT on ES (MES), points x 0.28** | +$900 | **-$3,838** / +$12,670 | **-$1,799** | 2.65 | 0.78 / 2.27 / 0.44 | 0.14 | 27.7 / 10.9 · 44.9 / 15.9 | **rejected**: loses H1 and 2025, 3x the eval fails |
| LIT on ES, stop range x0.8 / x1.25 | +$887 / +$893 | -$3,965 / +$12,668 · -$3,914 / +$12,675 | -$1,947 / -$2,176 | 2.50 / 2.72 | 0.77 / 2.27 / 0.40 · 0.78 / 2.27 / 0.30 | 0.14 | 27.7 / 10.9 · 44.9 / 15.9 | rejected (same picture) |
| LIT on ES, BE offset 1.25 ES pts (unscaled) | +$987 | -$3,311 / +$12,993 | -$1,649 | 2.65 | 0.81 / 2.30 / 0.49 | 0.14 | 27.7 / 11.8 · 44.9 / 14.5 | rejected |
| LIT on ES, London slot only (02:00-08:00) | +$697 | -$6,817 / +$13,653 | -$792 | 1.80 | 0.51 / 2.63 / 0.58 | 0.13 | 16.8 / 0.8 · 50.7 / 14.5 | rejected: H1 loses, under 2 a week |
| LIT on ES, NY slot only (08:00-15:30) | -$42 | +$1,827 / -$2,237 | -$690 | 1.46 | 1.29 / 0.44 / 0.64 | 0.06 | 4.2 / 12.6 · 0.0 / 0.0 | rejected |
| NQ LIT NY slot (08:00-15:30) on its own account | +$1,184 | +$12,797 / -$1,185 | -$296 | 1.00 | 4.68 / 0.48 / 0.62 | 0.10 | 25.2 / 0.0 · 0.0 / 1.4 | rejected: H2 and 2025 lose, 1 a week |
| NQ ATLAS (reference, same simple rules, 5m) | +$6,054 | +$47,285 / +$12,105 | +$1,469 | 3.81 | 3.05 / 2.28 / 1.28 | 0.09 | 51.3 / 0.0 · 44.9 / 0.0 | live paper (ATLAS) |
| **ATLAS on ES (MES), points x 0.28** | -$414 | **-$6,251** / +$2,191 | **-$314** | 4.88 | 0.85 / 1.09 / 0.95 | 0.11 | 26.9 / 0.0 · 43.5 / 0.0 | **rejected**: loses H1 and 2025; a real edge before costs, eaten by costs |
| ES ATLAS member EMA / MD / S/R alone | +$448 · -$676 · -$325 | -$2,463 / +$6,857 · -$1,851 / -$4,780 · -$284 / -$2,905 | -$1,031 · +$1,107 · +$68 | 2.33 · 1.67 · 1.67 | 0.86/1.84/0.63 · 0.87/0.65/1.39 · 0.98/0.69/1.03 | 0.11 · 0.07 · -0.12 | 10.1/0.0 · 37.7/0.0 (EMA) · 25.2/0.0 · 23.2/0.0 (MD) · 6.7/0.0 · 5.8/0.0 (S/R) | rejected: no member holds in all three spans |

- **The whole answer:** a weakly correlated stream exists (ES LIT 0.14, ES ATLAS 0.11), but it does not make money in 2
  of 3 spans. Its own eval passes about half as often as NQ LIT, and fails up to 3 times as often.
- **For more accounts at other firms**, the best second stream is still **NQ ATLAS**:
  - its daily correlation with LIT is 0.09 in 2026;
  - its own 25K passes 51 / 45% of evals in 2 weeks in this engine;
  - it already runs on paper.
- Copying NQ LIT to another firm (`lit-funded-firms.md`) has the same pass odds, but correlation 1.0: one bad LIT week
  hits every account at once. ES does not fix that.
- **No step for the owner.**

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-13]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[lit-all-hours|LIT all hours]], [[lit-funded-firms|LIT on 3 funded accounts]], [[lit-more-entries|LIT more entries]], [[lit-more-setups|LIT more setups a week]]
- Runs: `e3_nq_lit_5m, e3_es_lit, e3_es_lit_lon, e3_es_lit_ny, e3_nq_lit_ny_slot, e3_nq_atlas, e3_es_atlas`
- Source: `research/writeups/es-and-sessions-2026-11-13.md`
- Back to [[ZEUS Home]]
