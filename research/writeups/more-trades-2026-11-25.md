# More trades: can Zlarior / ATLAS trade more without losing the edge? (2026-11-25)

Owner: "we have not traded at all this week". PAPER RESEARCH ONLY: no live_model*.json change. Grid pre-registered before
any run (`research/moretrades/DESIGN.md`, commit before the code). Code `research/moretrades/moretrades.py` -> `lit.json`,
`atlas.json`. Same engine the bot runs (engine/lit.py run_x, engine/second.run), futures bars only, costs in, stops / size /
target unchanged. Sessions 2021-11-08 .. 2026-11-20 (the fresh Oct 19 - Nov 20 weeks included).

## Verdict: no looser version passes. Every extra trade the rules now skip is, on average, a worse trade. Keep LIT as it is.
0 of 19 LIT variants and 0 of 7 ATLAS variants meet the pre-registered rule (>= +25% trades, 2-week eval pass >= today in
BOTH 2026 halves, 2021-25 not worse, walk-forward >= half the windows). No owner card.

## LIT: the frontier (one screen). Today = L0. Eval = Builder 50K two_week path (room 0.4), 2-week pass %, median sessions
| Version | Trades/wk 2026 | PF H1 / H2 / 2021-25 | $/month H1 / H2 / 2021-25 | 2-wk pass H1 / H2 (median) | 50K 40-sess pass/fail 2021-25 | Fresh Oct19-Nov20 | Walk-fwd wins |
|---|---|---|---|---|---|---|---|
| **L0 today** | **2.91** | 4.98 / 2.91 / 1.01 | $5,562 / $2,670 / $25 | 44.5 / 39.1 (6 / 4) | 23.2 / 53.9 | -$858 | - |
| L13 + Asia (18:00-02:00, 1 Asia + the day trade) | 4.49 (+54%) | 2.92 / 2.22 / 0.93 | $4,492 / $3,374 / -$240 | **48.7 / 55.1** (5 / 5.5) | 18.4 / **77.3** | -$1,300 | 4/18 |
| P4 no inducement + 2 a day | 4.64 (+59%) | 3.07 / 2.06 / 0.94 | $5,245 / $2,971 / -$174 | 51.3 / 37.7 (6 / 6) | 22.5 / 66.4 | -$2,078 | 6/18 |
| P5 disp 0.7 + 2 a day | 4.13 (+42%) | 3.25 / 2.50 / 0.88 | $4,705 / $3,118 / -$316 | 47.9 / 39.1 (5 / 4.5) | 14.0 / 78.0 | +$2,938 | 3/18 |
| P6 depth 0.3 + no idm + disp 0.7 | 3.67 (+26%) | 2.70 / 1.22 / 0.92 | $4,121 / $583 / -$232 | 41.2 / 26.1 | 18.6 / 74.2 | +$1,649 | 5/18 |
| P3 disp 0.7 + no idm | 3.62 (+24%) | 2.77 / 1.70 / 0.92 | $4,178 / $1,709 / -$238 | 42.0 / 30.4 | 18.2 / 74.5 | +$1,649 | 4/18 |
| L10 2 a day | 3.59 (+23%) | 3.53 / 2.84 / 0.96 | $4,748 / $3,361 / -$85 | 43.7 / 39.1 | 17.8 / 61.4 | -$858 | 4/18 |
| L9 no 1m CISD step (chain shortened) | 3.47 (+19%) | 2.18 / 1.94 / 1.04 | $3,185 / $1,768 / $191 | 34.5 / 21.7 | 24.0 / 76.0 | -$2,659 | 5/18 |
| L5 disp 0.6 | 3.42 (+18%) | 4.55 / 1.42 / 0.88 | $5,827 / $807 / -$292 | 52.1 / 34.8 | 17.3 / 74.8 | +$2,649 | 1/18 |
| P1 depth 0.3 + no idm | 3.40 (+17%) | 3.40 / 1.36 / 1.01 | $4,756 / $854 / $25 | 40.3 / 30.4 | 21.8 / 67.8 | -$1,986 | 5/18 |
| L3 no inducement | 3.35 (+15%) | 3.50 / 1.88 / 1.01 | $4,813 / $1,980 / $27 | 42.9 / 34.8 | 22.9 / 66.5 | -$1,986 | 5/18 |
| P2 disp 0.7 + depth 0.4 | 3.28 (+13%) | 4.54 / 2.41 / 0.89 | $5,440 / $2,331 / -$255 | 48.7 / 37.7 | 19.2 / 71.6 | +$2,937 | 2/18 |
| L4 disp 0.7 | 3.25 (+12%) | 4.54 / 2.41 / 0.90 | $5,440 / $2,331 / -$210 | 48.7 / 37.7 (5 / 4) | 18.8 / 70.0 | +$2,937 | 2/18 |
| L11 2nd trade only after a stop-out | 3.20 (+10%) | 4.46 / 3.22 / 1.00 | $5,203 / $3,496 / $6 | 44.5 / 39.1 (6 / 5) | 23.1 / 55.5 | -$858 | 6/18 |
| L12 2nd trade only the other direction | 3.18 (+9%) | 4.23 / 2.41 / 1.00 | $5,259 / $2,385 / -$7 | 44.5 / 39.1 | 21.7 / 55.2 | -$852 | 4/18 |
| L8 1m CISD window 30 bars | 3.01 (+3%) | 5.10 / 2.51 / 1.06 | $5,598 / $2,212 / $131 | 51.3 / 37.7 | 26.5 / 58.2 | -$1,110 | 7/18 |
| L7 limit 60 min / L6 45 min | 2.99 / 2.94 | ~ today / 2021-25 PF 0.93 / 0.98 | ~ today, 2021-25 -$147 / -$46 | 42.9 / 39.1 | 20.4 / 22.4 pass | -$1,165 / -$858 | 2/18, 0/18 |
| L1 / L2 depth 0.4 / 0.3 | 2.94 (+1%) | ~ today (H2 PF 2.74 at 0.3) | 2021-25 -$24 / -$1 | 44.5 / 39.1, 36.2 | 23.6 / 23.9 pass | -$858 | 3/18, 5/18 |
2021-25 is 5m-only (no 1m bars), the reference line. Max DD 2021-25: today -$19.4k, the loose pairs -$22.9k .. -$30.3k.

What the frontier says, in money:
- **Single gates hardly add trades.** Sweep depth 0.5 -> 0.3 adds 0.03 trades a week; limit expiry 30 -> 60 min +3%. The
  binding limits are "1 trade a day" and the 02:00-15:30 window, not the gates.
- **The only real frequency lever is a second slot**: Asia (+54%) or 2 a day (+23%; +59% with no inducement). Those trades
  lose: 2021-25 goes from +$25 to -$85 .. -$316 a month and the 50K 40-session fail rate from 54% to 61-78%.
- **Nearest miss = L13 Asia**: +54% trades and FASTER 2026 passes (2-week 48.7 / 55.1 vs 44.5 / 39.1) but it lost $12.2k in
  2021-25 (today +$1.3k), 2025 alone -$11.4k (today +$3.2k), the 50K fail rate there 54 -> 77%, and walk-forward 4 of 18 windows.
  It is the 2026 market, not a better rule (same finding as notime 2026-11-24). Not a card.
- L11 (2nd trade after a stop-out) is the only "free" one: +10% trades, same 2-week pass, 2021-25 flat, H2 +$826/mo, but H1 -$359/mo,
  under the +25% bar and walk-forward 6/18. Paper lead only.
- Rapid EOD 25K (30% best-day rule): LIT passes ~0% in 2021-25 in every version (one big winner = the whole target) - LIT is
  structurally a Builder strategy, whatever the frequency.
- **Not tested (honest):** a 3m CISD timeframe needs an engine change (the detector is 5m, the entry check 1m).

## ATLAS (3 members, one position, $500 member size; 25K eval 40 sessions, daily level)
| Version | Trades/wk H1 / H2 | PF H1 / H2 / 2021-25 | Net H1 / H2 / 2021-25 | 25K pass/fail H1 , H2 , 2021-25 | Walk-fwd |
|---|---|---|---|---|---|
| **A0 today** | 4.26 / 3.21 | 3.13 / 2.28 / 1.14 | $49,081 / $12,105 / $43,608 | 94/6 , 90/10 , 33/67 | - |
| A1 EMA no swing sweep | 4.65 / 3.59 | 2.71 / 1.72 / 1.21 | $45,778 / $8,264 / $69,533 | 87/13 , 64/36 , 36/64 | 10/18 |
| A4 MACD histogram divergence | 5.16 / 4.23 (+21%/+32%) | 2.10 / 2.00 / 1.07 | $37,180 / $16,629 / $27,584 | 76/24 , 94/6 , 34/66 | 7/18 |
| A7 S/R no inducement | 5.20 / 4.42 (+22%/+38%) | 2.60 / 1.77 / 1.05 | $48,618 / $11,386 / $20,902 | 86/14 , 71/29 , 32/68 | 2/18 |
| A2 EMA any-EMA pullback / A3 MACD depth 0.3 / A5 MACD 2 a day / A6 S/R 2 a day | +0-4% | all lower in H2 | H2 $9.0k-11.7k | H2 65-88% pass | 3-4/18 |
ATLAS already trades 3-5 a week. Every loosening loses in at least one 2026 half. A1 is better in 2021-25 (+$26k) but worse in
both 2026 halves (H2 25K pass 90 -> 64%). No candidate.

## More instruments
- **LIT on ES (as MES)** alone, 5m execution, ES bars from 2025-04 only: 2.5-2.8 trades a week, PF 0.50 (2025) / 1.04 (H1) / 1.36 (H2),
  -29.6R in 2025. Not an edge on its own.
- **NQ + ES filler, one position** (lit-more-money 2026-11-19, re-read on the eval objective): 4.5 trades a week (+55%) but 2-week
  pass 43.7 / 42.0 vs 44.5 / 39.1, eval-path money -$9.7k (H1) / -$4.3k (H2), 2021-25 -$66 a month. Rejected then, rejected now.
- ATLAS on ES: rejected 2026-11-20 (PF 0.60-0.84 in 2026). LIT + ATLAS on one account: the a50 combo research (add only after the
  50K passes) stands. No longer ES1! export in data/tv_exports, so 2021-24 ES is untestable.

## Why this week has no trade
The backtest twin also has 1.4 trades a week since Oct 19 (-$858, 0 winners). A 2026 week with zero LIT trades happened once
in 47 weeks in the backtest; weeks of 0-1 trades are normal at ~2.9 a week with a 1-a-day cap. Loosening gates would have
added Oct 19 - Nov 20 trades that LOST (no inducement -$1,986, 2 a day + no idm -$2,078, Asia -$1,300); only the displacement
0.7 versions made money in those weeks (+$2.9k), and they lost $12k in 2021-25. The faster-pass money is more evals in
parallel (ATLAS + a second Zlarior), not a looser Zlarior.
