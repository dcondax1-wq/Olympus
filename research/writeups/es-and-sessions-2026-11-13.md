---
title: Same edge, more markets (Team E3, 2026-11-13). LIT and ATLAS on ES (MES) and in other session slots, as a 2nd signal stream for more prop accounts. Nothing passes; ES costs eat the edge
family: other
date: 2026-11-13
status: rejected (no adopt-candidate, no paper lead). LIT on ES loses in 2026 H1 and in 2025 even before costs; ATLAS on ES has a small edge before costs that the MES tick and commission eat (7-13% of R a trade vs 2.5-5% on NQ); the NQ NY slot and the ES London / NY slots fail at least one span and trade about 1-2 a week. The Asia slot was not redone (lit-more-entries.md lead 1, still a paper shadow).
summary: Owner - "Find every edge in trading ... build bots that will make me money ... think like a millionaire." MFFU's 3 funded slots are full, so the money question is a second, weakly correlated signal stream with similar eval pass odds that can run at other prop firms. Team E3 ran the proven LIT (engine/lit.py, live_model.json "lit") and the three ATLAS members (EMA / MD / S/R exactly as second_model.json, our NQ re-run = the stored research trades, 636/636, 387/387, 372/372) unchanged on CME ES1!, with only the point settings scaled by the ES/NQ price ratio (k = 0.28; neighbours x0.8 / x1.25 and three BE offsets), traded as MES. ES data exists only from 2025-04-14 and only on 5m (no ES 1m file, no ES 2021-24), so ES runs on 5m execution and the fair comparison is NQ on 5m execution too. Each stream got its own MFFU eval (LIT on a Builder 50K with the live two_week sizing, ATLAS on a Builder 25K with the account-B preset). LIT on ES - H1 -$3,838 (PF 0.78), H2 +$12,670 (PF 2.27), 2025 Apr-Dec -$15,936 (PF 0.44); NQ on the same 5m execution makes +$6,576 / +$1,474 / -$505. Own 50K 2-week pass/fail H1 27.7/10.9, H2 44.9/15.9, 2025 9.0/16.4 vs NQ LIT live 57.1/1.7, 52.2/5.8. Daily correlation with NQ LIT 0.14 in 2026 (shuffled-day noise band 0.13). ATLAS on ES - H1 -$6,251, H2 +$2,191, 2025 -$2,785 (PF 0.85 / 1.09 / 0.95) vs NQ ATLAS on the same rules +$47,285 / +$12,105 / +$13,013. Before costs ES ATLAS is +$1.1k / +$7.3k / +$10.2k: the setups are real but ES's structural stops are about 2.5x smaller in MNQ-equivalent terms while the tick stays 0.25, so costs take 7-13% of R a trade. Session slots - NQ LIT NY-only (08:00-15:30) as its own account H1 +$12,797 / H2 -$1,185 / 2025 -$2,621 at 1.0 trade a week; ES London-only H1 -$6,817; ES NY-only H2 -$2,237. Nothing passes. Best second stream for other firms stays NQ ATLAS itself (corr with LIT 0.09).
runs: e3_nq_lit_5m, e3_es_lit, e3_es_lit_lon, e3_es_lit_ny, e3_nq_lit_ny_slot, e3_nq_atlas, e3_es_atlas
---

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

## Why ES does not work: the tick is too big for ES's stops

The repo's stop rule is 1 tick beyond the sweep extreme, and sizing follows the stop. ES trades at 0.27 of NQ's price, but
its 5m bars are only 0.19 of NQ's in points (ES is about 30% calmer in % terms). **The tick stays 0.25 points on both.** With MES at $5 a point:
- The structural stops on ES are small: the median ES LIT stop is 27 MNQ-equivalent points, against 56 for NQ.
- Each micro pays $1.90 commission and 1 tick ($1.25) of slippage on entry and exit.
- **Costs are 7-13% of R a trade on ES, against 2.5-5% on NQ.** (The slippage is an estimate: 1 tick in and 1 tick out.)

| Stream | Span | Trades | Net $ | Commission $ | about Slippage $ | **Before costs $** | Median cost / R |
|---|---|---:|---:|---:|---:|---:|---:|
| NQ LIT 5m | H1 / H2 / 2025 | 54 / 23 / 86 | +6,576 / +1,474 / -505 | 382 / 120 / 1,224 | 201 / 63 / 644 | +7,159 / +1,657 / +1,363 | 0.026 / 0.025 / 0.034 |
| ES LIT | H1 / H2 / 2025 | 66 / 43 / 97 | -3,838 / +12,670 / -15,936 | 1,347 / 931 / 2,485 | 1,772 / 1,225 / 3,270 | **-719** / +14,826 / **-10,181** | 0.080 / 0.072 / 0.084 |
| NQ ATLAS | H1 / H2 / 2025 | 107 / 50 / 171 | +47,285 / +12,105 / +13,013 | 1,387 / 593 / 3,304 | 730 / 312 / 1,739 | +49,402 / +13,010 / +18,056 | 0.033 / 0.029 / 0.047 |
| ES ATLAS | H1 / H2 / 2025 | 125 / 76 / 178 | -6,251 / +2,191 / -2,785 | 3,156 / 2,194 / 5,596 | 4,152 / 2,888 / 7,362 | **+1,058 / +7,273 / +10,173** | 0.107 / 0.121 / 0.130 |

- **LIT on ES has no edge even before costs** in H1 2026 or in 2025. Its only good half is H2 2026, and in H2 ES moved
  with NQ (H2 correlation 0.31).
  - On the same 5m execution, NQ was positive before costs in all three spans.
  - So this is not just "ES lacks 1m bars". On equal terms, ES was much worse than NQ in 2025 (-$15.9k vs -$0.5k) and in
    H1 2026 (-$3.8k vs +$6.6k).
- **ATLAS on ES is positive before costs in all three spans.** The EMA / MACD / S/R setups do find something on ES.
  - But at 20 MNQ-equivalent points of median risk, costs take more than the edge.
  - Wider stops would break the stop rule: the stop sits at the structure, never at a fixed distance.
  - ES minis (one $50 contract instead of 10 MES) would cut commission per point, but not the tick. At $500 risk and a
    7-point stop, that is 1 contract: too coarse for the two_week sizing.
- **This is about cost per R.** Our earlier ES results (`lit-more-setups.md`: ES -$4.5k in H1, NQ+ES fails 17-29% of evals)
  agree, and today's live upgrades (15-minute check, BE + costs) do not change them.

## What was tested

1. **LIT on ES, as-is.** The engine and settings are the live `live_model.json` "lit": sweep, inducement, displacement,
   5m CISD, 30-min limit, VIX-band target banked at 8R, BE at 1R, 15-minute check, flat 15:55, 1 trade a day, entries
   02:00-15:30, Monday rule, weekly stop. Only the point settings change:
   - min / max stop 8 / 80 NQ pts x k = 2.25 / 22.5 ES pts;
   - BE offset 1.25 NQ pts becomes the MES cost equivalent, 0.75 ES pts. That is the smallest offset whose exit (1 tick
     below it) still pays the $1.90.
   - The VIX band is VIX% x the instrument's own price, so on ES it is the S&P's implied move: no change needed. Sweep
     depth and displacement are in ATR: no change needed.
   - k = 0.28 was fixed before the run. The measured median price ratio is 0.269.
   - Neighbours: stop range x0.8 (nearer the 5m range ratio, 0.19 / 0.27 = 0.7 of k) and x1.25, and BE offsets 0.5 and 1.25. Every one gives the same
     picture, so this is not a knife edge.
2. **ATLAS on ES, as-is.** The three members exactly as `second_model.json`:
   - EMA: London trend pullback, 03:00-09:30, no Mondays, VIX target, BE at 1R.
   - MD: MACD divergence at a sweep, London + NY, VIX target, 15-minute check.
   - S/R: NY sweep-and-reclaim, 09:30-12:00, 2R, 15-minute check.
   - Their point settings x k: stops 6 / 80 -> 1.75 / 22.5; S/R outcomes 6 / 120; EMA BE offset 0.75.
   - Round numbers come from the ES roll file.
   - **Check:** the same code on NQ gives the stored research trades exactly (EMA 636/636, MD 387/387, S/R 372/372
     entries; S/R has 2 more at the data end).
   - Pooled the account-B way: one position at a time, at most 2 a day, $500 a trade.
   - What is left out: the LIT-armed block and the hedge rule. They are about LIT on the other MFFU account and do not
     apply to an account at another firm. The NQ ATLAS reference row uses the same simple pooling, so the two rows
     compare fairly.
3. **Other session slots** (checked against "Tested and rejected" first):
   - **Asia: not redone.** `lit-all-hours.md` and `lit-more-entries.md` lead 1 tested it. The Asia slot with a 3R bank
     runs as the `lit_asia` paper shadow. On its own (`asia_kz_mg_rr3`) it makes H1 +$1,890 / H2 +$4,724 but 2021-25
     -$23,182, with 2-week passes of 11.8% / 30.4%. Correlation of its 2026 Asia trades with LIT: -0.02. Uncorrelated,
     but it does not hold in 2021-25 and passes evals too slowly.
   - **London open:** this is already LIT's own money. 02:00-08:00 is 95 of LIT's 120 trades in 2026 (`lit-more-entries.md` session table). NQ London-only
     has correlation 0.97 with LIT, so it is the same bet, not a second stream.
   - **New here: NY as its own account.** NQ LIT 08:00-15:30 only, on a second account, so it takes the NY setup even
     on days when London already traded. It also runs ES London-only and ES NY-only.
4. **Judging (repo rules):**
   - LIT-style: H1 picks, H2 checks. Nothing was picked: the scaled version was fixed in advance.
   - History means whatever exists: ES 2025-04 to 2025-12 only. NQ rows show the same window, so they compare.
   - Costs are in. Stops stay 1 tick beyond the sweep extreme. 2-4 trades a week. Money, eval and correlation for every
     row.

## Eval speed per stream (own account, fresh start on every session; p = pass, f = fail, % of starts)

| Stream | Plan | Span | p10 / f10 | dec10 | p15 / f15 | pass_med (sessions) | slow_pass % | % weeks 2+ | Max DD $ | Worst day $ |
|---|---|---|---|---:|---|---:|---:|---:|---:|---:|
| NQ LIT live | 50K | H1 · H2 · 2025 | 57.1/1.7 · 52.2/5.8 · 14.1/4.5 | 58.8 · 58.0 · 18.6 | 62.2/1.7 · 56.5/5.8 · 17.5/4.5 | 4 · 3.5 · 5 | 18.7 · 29.1 · 41.5 | 85 · 81 · 74 | -2,213 · -1,419 · -5,862 | -763 · -641 · -878 |
| NQ LIT 5m | 50K | H1 · H2 · 2025 | 26.9/9.2 · 34.8/0.0 · 14.1/4.5 | 36.1 · 34.8 · 18.6 | 29.4/10.9 · 34.8/1.4 · 17.5/4.5 | 3.5 · 4.5 · 5 | 2.8 · 14.3 · 39.2 | 67 · 31 · 71 | -3,080 · -1,313 · -5,862 | -818 · -635 · -878 |
| ES LIT | 50K | H1 · H2 · 2025 | 27.7/10.9 · 44.9/15.9 · 9.0/16.4 | 38.6 · 60.8 · 25.4 | 27.7/12.6 · 46.4/15.9 · 9.6/16.4 | 5 · 4 · 3 | 8.3 · 17.9 · 34.6 | 82 · 88 · 84 | -8,591 · -2,711 · -16,534 | -889 · -889 · -876 |
| NQ LIT NY slot | 50K | H1 · H2 · 2025 | 25.2/0.0 · 0.0/1.4 · 5.6/1.7 | 25.2 · 1.4 · 7.3 | 30.3/0.0 · 0.0/1.4 · 9.0/3.4 | 5.5 · - · 5.5 | 41.9 · - · 63.6 | 22 · 19 · 32 | -1,593 · -1,185 · -4,999 | -867 · -443 · -837 |
| NQ ATLAS | 25K | H1 · H2 · 2025 | 51.3/0.0 · 44.9/0.0 · 28.2/0.0 | 51.3 · 44.9 · 28.2 | 60.5/0.0 · 50.7/0.0 · 29.4/0.0 | 3 · 5 · 4 | 30.1 · 16.7 · 3.7 | 96 · 81 · 100 | -2,385 · -2,831 · -8,913 | -1,009 · -725 · -1,030 |
| ES ATLAS | 25K | H1 · H2 · 2025 | 26.9/0.0 · 43.5/0.0 · 21.5/0.0 | 26.9 · 43.5 · 21.5 | 27.7/0.0 · 44.9/0.0 · 23.7/0.0 | 3.5 · 4.5 · 4 | 0.0 · 18.4 · 8.7 | 96 · 100 · 100 | -8,843 · -11,252 · -16,047 | -1,156 · -1,088 · -1,198 |

- Max DD and worst day are at the stream's money size (LIT size / $500). Every number is in
  `research/second/e3_es_sessions.json`.
- ATLAS's 25K "need" sizing almost never fails within 2 weeks, because each loss takes at most half of the room that is
  left. Evals that go nowhere get "stuck" instead. Compare the pass rates, not the fail rates.

## Correlations (daily P&L, every session, no-trade days = 0)

| Stream | vs NQ LIT 2026 · H1 · H2 · 2025 | vs NQ ATLAS 2026 · 2025 |
|---|---|---|
| ES LIT | 0.14 · 0.10 · 0.31 · 0.03 | -0.06 · -0.07 |
| ES ATLAS | 0.11 · 0.05 · 0.31 · -0.13 | -0.03 · 0.02 |
| NQ LIT NY slot | 0.10 · 0.10 · 0.16 · 0.37 | 0.00 · 0.01 |
| NQ LIT London only | 0.97 | -0.02 · 0.10 |
| NQ ATLAS (reference) | 0.09 · 0.12 · -0.05 · 0.19 | (0.63 vs the stored atlas_base: same strategy, simpler pooling) |
| LIT Asia slot trades (stored run, not redone) | -0.02 · 0.01 · -0.08 · 0.04 | -0.04 · -0.02 |

- **Noise band:** shuffling ES LIT's days gives |r| up to 0.13 in 2026 and 0.15 in 2025 (95th percentile). Every
  ES / NY-slot correlation is at or inside that band: weakly correlated, as wanted. The trouble is the money, not the
  correlation.
- In H2 2026 the ES streams moved more with NQ LIT (0.31). That was the half ES made its money, so ES's good half is
  partly the same bet as LIT.

## Honest limits

- **ES has no 2021-24 data and no 1m bars.** ES1! runs from 2025-04-14 to 2026-10-16 on 5m only (`data/ES_5m.csv`).
  There is no ES 1m file, so ES runs on 5m execution.
  - On NQ, 1m execution turns +$6.6k into +$33.7k in H1, so a fair ES-1m test might look better.
  - But ES on 5m loses money before costs in H1 2026 and in 2025, where NQ on 5m does not. 1m entries cannot turn a
    negative setup positive; they only make better entries on the same setups. And ES's cost per R would stay 3x NQ's.
  - A re-test needs ES / MES 1m bars, about 3+ months of them (the PC could archive them from a NinjaTrader MES chart).
    Not worth chasing on this evidence.
- **MES commission** is assumed equal to MNQ's $1.90. Most firms charge MES the same as MNQ, so this is fair.
- The 2025 history is only 8.5 months (172 sessions), and 2026 is 9.5 months. The thin spans affect the ES rows most.
- The ATLAS evals use the account-B 25K two_week preset in `tools/e3_es_sessions.run_eval` (the lit_more engine with the
  25K limits), without the 25K day guard. They are fine for comparing ES with NQ under one engine, but not equal to
  account B's published numbers.
- The stored runs (`e3_*`) carry the run library's own eval at the stream's fixed size. Those numbers differ from the
  own-account columns above, which use each plan's two_week sizing.

## Files

- Tool: `tools/e3_es_sessions.py`.
  - `members NQ|ES`: the ATLAS members on one instrument, each in its own process.
  - `all`: every stream, the evals and the correlations, written to `research/second/e3_es_sessions.json`.
  - `save`: stores the runs.
  - `check`: the NQ re-run against the stored member trades.
- Runs: `e3_nq_lit_5m`, `e3_es_lit`, `e3_es_lit_lon`, `e3_es_lit_ny`, `e3_nq_lit_ny_slot`, `e3_nq_atlas`, `e3_es_atlas`.
- No engine, model, UI, `live_model*.json` or `second_model.json` file was changed. Paper research only.
