# Zlarior (LIT) more money - pre-registered design, batch 1 (2026-11-19, night-litmore)

Written and committed BEFORE any idea below was run. Research only: no live file, no live_model*.json touched.

## Why only a few ideas
`docs/TESTED_AND_REJECTED.md`, STATE.md "Recent findings" and ~70 LIT write-ups were read first. Already dead and NOT
redone: smart entries (31), regime sizing (124), walk-forward re-tuning, famous public strategies, drift switch, two-eval
zombie / stagger, Asia slot + all hours + re-arming (lit-all-hours, Rapid levers), ES LIT alone and "NQ + ES first fill
wins" (lit-more-setups, E3), extra levels Monday / 10-20 day / quarterly (gap audit, round 3), flat time 15:55 -> 16:25 /
16:55 (ablation: a do-nothing knob), BE 0.75 / 0.9 / 1.25 / 1.5R / off / on a 1m close / by ATR / by points, time stops,
NY-open / news / stall / lunch exits, partials, trails, profit locks, 15-minute check variants, re-entries.
What is left inside the hard rules is small, so batch 1 has 2 ideas. Batch 2 (the owner's added scope) is a separate file.

## Base (no change)
The live LIT trades (tools/lit_edge.ctx()["T"], 631 trades, 120 in 2026, == run lit_live), costs in ($1.40 a micro at the
LIT size, $1.90 on the eval path, 1 tick slippage on market entries and stop / BE / EOD exits). Scored three ways by
tools/lit_edge.evaluate: LIT size rule, the live Builder 50K eval path (two_week, room_f 0.4 kept to session 80, = the
owner-approved sizing), the funded Builder 50K Monte Carlo (1,000 six-month paths, live funded sizing).

## Ideas (each ONE version, every number fixed here; nothing is tuned afterwards)
1. **es_filler** - more trades: LIT on ES (traded as MES micros on the same account), same rules, E3's pre-registered
   instrument scaling (k = 0.28: stops 2.25-22.5 ES pts, BE offset 0.75 ES pts; ES has 5m bars only, so ES runs on 5m
   execution). NQ keeps priority and is unchanged trade for trade: an ES trade may open only while NQ has not traded
   yet that day and NQ holds no position; if an NQ entry comes while ES is open, ES is closed at market first (the ES 5m
   open at / after the NQ entry, - 1 tick) and NQ enters. At most one ES trade a day. Weekly stop counted across both.
   Size: the same $ rules on MNQ-equivalent points (MES $5 / ES pt = 2.5 MNQ points). ES data 2025-04-14 .. 2026-10-16,
   so the 2021-25 line has ES only in 2025.
   Not the same as "NQ + ES, 1 a day, first fill wins" (rejected 2026-10-19): there ES could take NQ's day.
2. **be_frac** - breakeven tied to the planned target: the stop moves to entry + 1.25 pts once the trade reaches
   clip(0.25 x planned target R, 0.5R, 2.0R) instead of +1R (a 4R target keeps today's 1R; an 8R target waits for 2R; a
   1.5R target protects at 0.5R). Hypothesis: far targets need room, near ones should be protected sooner.

## Gate (the same for batch 1 and batch 2; a winner passes ALL)
- G1 LIT size: net $ higher in 2026 H1 (Jan-Jun) AND H2 (Jul-Oct 16).
- G2 eval path: back-to-back net $ higher in H1 AND H2; 2-week fail rate not higher in either half; 2-week pass rate not
  lower by more than 2.0 points in either half.
- G3 2021-25 (LIT size) not worse: change >= -$600 (about -$10 a month).
- G4 2.0-4.0 trades a week in both 2026 halves (LIT size).
- G5 week-block bootstrap (5,000 draws, ISO weeks resampled within each half) of the weekly LIT-size $ change over 2026:
  share of draws with total change <= 0 at most 0.10.
- G6 funded Builder 50K $ a month not lower by more than $10 in H1 or H2.
Every idea is a single fixed version, so Jan-Jun and Jul-Oct are both out-of-sample checks; Jan-Jun is still quoted as
"pick" and Jul-Oct as "check". Reported per idea: trades/week, PF, net $, $/month, max DD (LIT size and eval path),
2-week pass / fail and median sessions to pass on the Builder 50K, funded $/month, bootstrap share. Ideas tried are
counted (batch 1 + batch 2). A pass becomes a Decide card only; nothing goes live without the owner's yes.
