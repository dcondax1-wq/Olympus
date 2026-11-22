---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/atlas
  - bot/blitz
type: "research"
date: "2026-10-30"
status: "rejected (no change; nothing passes every gate; no pick v3) - promising paper lead - the funded 25K sizes a later band break at 2 micros (a first break 1). Round 3 - on 20 seeds C3 (<= 25% of the ..."
source: "research/writeups/blitz-edge-2026-10-30b.md"
aliases:
  - "BLITZ edge, rounds 2-4"
---

# BLITZ edge, rounds 2-4

> [!failure] Verdict: rejected
> rejected (no change; nothing passes every gate; no pick v3) - promising paper lead - the funded 25K sizes a later band break at 2 micros (a first break 1). Round 3 - on 20 seeds C3 (<= 25% of the room, give up at 1 x the median stop) beats v2 in H1, H2 and 2021-25 on every seed, but the H1-only selection rules (written before H2) pick a different cell (<= 35% of the room, give up at 1.5 x) which passes the 3 spans on 20 seeds yet fails +1 tick in 2021-25, 1 bar late in H2, 2024, the H2 ...

**Full title:** BLITZ edge, rounds 2-4 (2026-10-30 afternoon) - funded size, eval rules, signal facts, a momentum-regime gate, ES as a second market - nothing passes every gate; the funded later-break size stays a paper lead

## Summary

Round 4 (coordinator 13:12) - today's BLITZ rule on CME ES1! 5m (MES $5 a point, $1.90 a micro, 1-tick fills; data 2025-04-13 .. 2026-10-16) at $150 a trade - 2025 May-Dec PF 0.94 (-$96 a month), 2026 H1 1.03 (+$42), 2026 H2 0.82 (-$311), 9.0-9.5 trades a week, max DD -$1,318 to -$1,881; NQ BLITZ on the same 5m bars PF 1.13 / 1.48 / 1.50. Daily P&L correlation with NQ BLITZ 0.58-0.66, the same side on 86-94% of the days both trade - no diversification. Costs are 7-9% of 1R on ES (2-3% on NQ: ES's 10-point stop is small next to a tick); before costs ES is PF 1.21 / 1.28 / 1.11, still weaker than NQ. ES fails the PF > 1.1 test in every span, so the NQ + ES 25K was not built. Only 18 months of ES data - a caveat. Round 3 (coordinator 13:00) - (1) C3 robustness on 20 Monte Carlo seeds, slot $ a month vs v2 (H1 / H2 / 2021-25) - C3 +16.9 / +42.2 / +9.8 (20 / 20 / 20 seeds better); the later-break funded size alone +23.4 / +35.3 / +0.3 (2021-25 8 of 20); the give-up line at 1 x alone -3.9 / +6.8 / +6.9 (H1 0 of 20; random directions +13 / +2 / +10 = fee saving, not edge). Three H1-only selection rules on a 40-cell grid (room 15-35%, give-up 0.75-1.5 x, later 2-3 micros), fixed before H2 / 2021-25 were computed, all pick 35% / 1.5 x / 2 micros (not C3) - +51.8 / +11.7 / +3.2 on 20 of 20 seeds, but +1 tick 2021-25 -2, 1 bar late H2 -2, 2024 -8, 50% of the room next door H2 -8.6, and random first / later labels do better in H2 - not adopted. (2) Momentum-regime day gate from the market only (30-min return autocorrelation, variance ratio, 11:00-12:00 band-break follow-through; 20 / 40 sessions) - 0 of 30 skip and 0 of 30 half-size gates beat today in H1, H2 and 2021-25; the H1 pick (follow-through 40 >= H1 p35) makes $908 / -$16 / -$4 a month at $150 (today $963 / $667 / $73) with 0.96 trades a week in H2; 2026 H2 reads as a low-momentum market yet BLITZ made PF 1.62 there. Round 2 - Owner 2026-10-30 12:30 - "make BLITZ way better - good rules, good strategy, good discretion", BLITZ's own 25K (account C) starts next week. Same trades as today (engine/blitz.py v2 as account C, costs in, CME NQ 1m 2026 / 5m 2021-25); 2026 H1 = pick, H2 = check, 2021-25 = the 5-year gate. 1. Funded stage (where the slot loses its money - funded accounts at 1 micro mostly sit open or get stuck before a payout) - 66 rules + 123 later-break micro sizes + stress - buffer-first size (bigger once the floor locks) H1 -$24 to -$142 a month, funded day / week stops, max trades a day, smaller payout asks, waiting for bigger asks and skipping big stops near the floor all lose in H1; the later-break size in whole micros (later break 2 micros, first break 1) is the one family that helps - its H1 pick (<= 50% of the room) makes +$71 to +$77 a month in H1 but -$16 to -$19 in H2 and -$3 in 2021-25 (3 seeds), so it fails. 18 of the 25 variants that beat today in both H1 quarters also beat it in H2 and 2021-25; the sturdiest, C3 (<= 25% of the room, abandon at 1 x the median stop), is +$22 / +$42 / +$9 a month (slot $308 / $94 / -$30 vs $286 / $52 / -$39) - a paper lead, not adopted. 2. Eval - the first winner ending the day on sessions 1-4 slows the eval and loses slot $ everywhere; 2 losers ending the day cuts 2-week fails but only delays them; skipping first breaks early is mixed - the later-break eval size (blitz_25k_pick_v2.json) stays the only eval change. 3. Signal facts - relative volume of the signal bar, band width / ATR, the sigma regime, an earlier opposite-side break, yesterday's BLITZ result, the last 10 trades - 0 of 120 tilts beat today in all three spans (shuffled facts give 4.9). BLITZ's 2021-25 slot stays negative with any size.

## Money first

**Nothing passes every gate, so nothing changes, and there is no pick v3.** BLITZ's trades stay exactly as they are. The
later-break eval size (`research/scalp/blitz_25k_pick_v2.json`, still waiting for your OK) remains the one change on the
table. There is one lead for the funded 25K, for paper only.

**Round 3 in one table** (20 Monte Carlo seeds; slot $ a month to you, net of every $63 eval):

| Set-up | Slot H1 / H2 / 2021-25 (mean of 20 seeds) | vs v2: seeds better H1 / H2 / 2021-25 | Verdict |
|---|---|---|---|
| Today | $257 / $43 / -$40 | | baseline |
| v2 (later-break eval size) | $276 / $57 / -$38 | | adopt-candidate since this morning |
| (a) v2 + the funded later-break size only (later 2 micros, <= 25% of the room) | $299 / $93 / -$38 | 20 / 20 / 8 | 2021-25 flat |
| (b) v2 + the later give-up line only (1 x the median stop) | $272 / $64 / -$31 | 0 / 20 / 20 | loses in H1; fee saving, not edge |
| C3 = (a) + (b) | $293 / $99 / -$28 | 20 / 20 / 20 | not what the H1 rules pick |
| C1 (later 3 micros, 2 on every trade after the lock, <= 50%) | $320 / $134 / -$34 | 20 / 20 / 19 | not the H1 pick; weak under stress |
| **H1-rule pick (later 2 micros, <= 35% of the room, give up at 1.5 x)** | $328 / $69 / -$35 (+51.8 / +11.7 / +3.2) | 20 / 20 / 20 | **fails the stress / year / control checks** |
| Momentum-regime day gate (H1 pick) | at $150: $908 / -$16 / -$4 a month (today $963 / $667 / $73) | | rejected |
| BLITZ on ES as a 2nd market (MES, 5m; 2025 May-Dec / 2026 H1 / H2) | at $150: -$96 / +$42 / -$311 a month, PF 0.94 / 1.03 / 0.82 | | rejected |

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-30]]
- Strategies: [[ATLAS]], [[BLITZ (paper)]]
- Refers to: [[blitz-25k|BLITZ on its own MFFU Builder 25K]], [[payout-policy|Funded-phase money from the payout rules]]
- Runs: `bzx_es_solo, bzx_c3_robust, bzx_regime_gate, bzx_funded_later2, bzx_funded_rules, bzx_eval_rules, bzx_signal_facts`
- Source: `research/writeups/blitz-edge-2026-10-30b.md`
- Back to [[ZEUS Home]]
