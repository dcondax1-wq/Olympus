# More trades: trade-frequency vs edge. Pre-registration (written 2026-11-25 ~13:15 ET, BEFORE any variant below was run)

Owner: "we have not traded at all this week". LIT trades ~1.4-2.6 a week (no trade Mon-Wed Nov 23-25). Question: is there a
version that trades MORE and still earns, ideally passing evals FASTER? PAPER RESEARCH ONLY: no live_model*.json change.
Code `research/moretrades/moretrades.py` -> `research/moretrades/results.json`; write-up `research/writeups/more-trades-2026-11-25.md`.
Futures data only (TradingView NQ1!/ES1! + NinjaTrader bars in data/), costs in (the engine's $1.90 + 1 tick), stop 1 tick
beyond the sweep extreme, size from the stop, one target (VIX band, 8R bank) - all unchanged in every variant.

## Already tested (docs/TESTED_AND_REJECTED.md) - re-scored here on the eval objective, not re-invented
ablation 2026-10-23 (single knobs), lit-more-entries / edge-d re-entry (2nd trade, stop-out re-entry, opposite side),
lit-all-hours / notime (Asia 18:00-02:00), lit-more-money (ES filler), atlas ES legs. These were judged mostly on $; today
the judge is "more trades AND eval passes faster".

## LIT variants (engine/lit.py run_x via tools/lit_final.run = the code the live loop runs; base L0 = live_model.json "lit")
Singles: L1 depth 0.4 | L2 depth 0.3 | L3 no inducement (idm_a None) | L4 disp 0.7 | L5 disp 0.6 | L6 limit 45 min (wait 9) |
L7 limit 60 min (wait 12) | L8 1m CISD window 30 bars (cisd1m 30) | L9 chain shortened: no 1m CISD step (limit fill at the
5m CISD level, cisd1m None) | L10 2 trades a day (any) | L11 2nd trade only after a stop-out the same day | L12 2nd trade only
in the OPPOSITE direction (both directions a day) | L13 Asia added (entries 18:00-02:00 + 02:00-15:30, all_hours, 1 Asia +
the day trade).
Pairs: P1 depth 0.3 + no idm | P2 disp 0.7 + depth 0.4 | P3 disp 0.7 + no idm | P4 no idm + 2 a day | P5 disp 0.7 + 2 a day |
P6 depth 0.3 + no idm + disp 0.7 (the loosest "chain" short of dropping a step).
Not testable without an engine change (say so, do not fake): a 3m CISD timeframe (the detector is 5m, the entry check 1m).
= 19 LIT variants + base. With 19 tries, one "win" in one split is noise: a candidate must win BOTH 2026 halves AND not lose
vs base on 2021-25.

## ATLAS members (engine/second.run month by month, live config, members at their own $500 size; base A0 = today)
A1 EMA no swing sweep on the pullback (entry.sweep 0) | A2 EMA pullback to any EMA (pull "any") | A3 MACD sweep depth 0.3 |
A4 MACD histogram divergence (osc "hist") | A5 MACD 2 a day | A6 S/R 2 a day | A7 S/R no inducement.
Book = the 3 members, one position at a time (base vs each loosened member swapped in).

## More instruments
E1 LIT on ES alone (as MES, tools/lit_more.run_on "es", 5m execution, ES data from 2025-04 only) | E2 portfolio NQ LIT + ES
LIT filler, one position per account (NQ first; ES only while NQ has no trade open/that day). ATLAS on ES: already rejected
(PF 0.60-0.84 in 2026, atlas-es) - cited, not re-run. TV ES1! longer export: use only if present in data/tv_exports.

## Score (every variant, same table)
trades/week, PF, net $, $/month, max DD (LIT size), per year 2021..2026 + 2026 H1 / H2 + fresh Oct 19 - Nov 20 2026 if the
engine's sessions reach it; Builder 50K two_week eval path (2026 H1 / H2: 2-week pass / fail, median sessions to pass);
daily-level 40-session MFFU Builder 50K / 25K (x0.5) / Rapid EOD 25K (x0.5) pass / fail / median days (research/notime rules)
per span incl. 2021-25; rolling walk-forward: 6-month windows stepping 3 months 2021-11..2026-10, count of windows where the
variant beats base on net $ AND 50K 40-session pass %.

## Verdict rule (fixed now)
A variant is a CANDIDATE only if: trades/week >= base x 1.25 (and <= ~4.5); Builder 50K two_week 2-week pass % >= base in BOTH
2026 halves with fail % not worse by more than 2 points; median days to pass not slower in both halves; 2021-25 net $ and
40-session 50K pass % not worse than base; walk-forward wins >= half the windows. Candidate -> needs-owner-yes card with the
exact config diff (NOT applied). Otherwise: on the frontier table as "more trades costs X" and a TESTED_AND_REJECTED line.
