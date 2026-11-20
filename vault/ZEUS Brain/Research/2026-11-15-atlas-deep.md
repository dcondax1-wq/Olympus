---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/atlas
type: "research"
date: "2026-11-15"
status: "adopt-candidate (zombie-eval rule, account_b \"eval_min_room\" 200 + \"last_bullet\" 0.8, built and OFF; owner decides). Rejected - 16 trade filters / size tilts from the loser autopsy (LIT won the ..."
source: "research/writeups/2026-11-15-atlas-deep.md"
aliases:
  - "ATLAS deep edge"
---

# ATLAS deep edge

> [!success] Verdict: adopt-candidate
> adopt-candidate (zombie-eval rule, account_b "eval_min_room" 200 + "last_bullet" 0.8, built and OFF; owner decides). Rejected - 16 trade filters / size tilts from the loser autopsy (LIT won the other side, same-side retry or refusal, LIT on the same side, stop outliers, first-trade half size, weekly brake, daily trend, one trade per side)

**Full title:** ATLAS deep edge (2026-11-15) - the losers are not in the trades but in the account; a "zombie-eval rule" lifts the 25K slot +$59 / +$65 a month (built, OFF), every trade filter is chance

## Summary

Team E-ATLAS. Baseline of ATLAS as it runs on the Builder 25K today (account-B rules, fees at the owner's $43), a loser autopsy of its 2026 and 2021-25 trades (member, side, hour, weekday, VIX, stop in points / ATR / vs the member's own median, target R, daily trend, LIT's day, the members' paper day, nth signal, exit), then 8 pre-declared new ideas (16 variants) and 2 ideas found by the autopsy of the account path (13 variants with neighbours and combinations). Main finding - in 2026 half of ATLAS's signals are never traded (H1 58 of 112, H2 26 of 51, worth +48R / +13R at a fixed risk) because an eval with a low room sizes to 0 micros and idles for weeks ("zombie"); today ATLAS trades 2.11 / 1.60 times a week on the account and only 48% / 38% of weeks have 2+ trades. The zombie-eval rule (give an eval up under $200 of room, and on a low room trade 1 micro when its full stop-out fits 80% of the room) - owner $ a month on the whole 25K slot $639 / $459 / $16 vs $579 / $394 / $11 (H1 / H2 / 2021-25), 2-week pass 67.2 / 43.5 vs 65.5 / 43.5, 3.95 / 2.95 trades a week (weeks 2+ 96% / 81%), paths that lose money 0.2% / 3.3% vs 6.8% / 17.8%. All 13 lifecycle variants lift the slot in both halves (a plateau with a clear mechanism, not a selection). No trade filter survives - the one that passes the slot test (skip ATLAS after LIT won the other side) moves 4 H2 trades worth -0.05R and random skips of the same size pass the 2026 test in 6.7% of draws.

## Money first

"Owner $ a month" = what one ATLAS 25K slot pays you a month over 6 months: eval -> funded -> MFFU payouts (80% to you,
5 payouts max) -> a new $43 eval after every fail, give-up or graduation (tools/atx_edge.slot, 300 paths x 3 seeds).
Eval-path trading $ is never paid out; this is the money.

| What | Jan-Jun | Jul-Oct | 2021-25 | 2-week pass (Jan-Jun / Jul-Oct) | Trades a week | Verdict |
|---|---:|---:|---:|---|---|---|
| **ATLAS today** | **$579** | **$394** | $11 | 65.5 / 43.5 | 2.1 / 1.6 | the bar |
| **Zombie-eval rule** (give up under $200 + 1-micro last bullet) | **$639 (+$59)** | **$459 (+$65)** | $16 (+$5) | **67.2 / 43.5** | **4.0 / 3.0** | **adopt-candidate (built, OFF)** |
| Give up under $200 only | $631 (+$51) | $442 (+$48) | $14 | 65.5 / 43.5 | 3.6 / 2.2 | same family |
| Last bullet only (80% of the room) | $629 (+$50) | $454 (+$60) | $13 | 69.7 / 43.5 | 3.8 / 2.8 | same family |
| Skip ATLAS after LIT won the other side today | $598 (+$19) | $423 (+$29) | $14 | 69.7 / 43.5 | 1.7 / 1.7 | chance (see below) |
| Every other trade filter / size tilt (14) | -$167 to +$13 | -$81 to +$0 | -$9 to +$3 | | | rejected |

In plain words: ATLAS's trades are fine; its eval wastes weeks. When an eval is down to $100-$400 of room, today's size rule
says "0 micros" (one stop-out would not fit half the room) and the account just sits there, often for the rest of the
month. The fix is to either give that eval up and buy a fresh $43 one (under $200 of room) or take its last shot with one
micro. Both bring the trading back to 3-4 a week and pass more funded accounts per half year (1.68 vs 1.49 in Jan-Jun,
1.27 vs 1.11 in Jul-Oct).

**Cost:** about 0.4 more evals per 6 months ($17) in 2026, 2.8 more ($120) in a 2021-25-like market; 1 in 10 Jan-Jun evals is
given up inside 2 weeks (that is the point: decided, not stuck). Funded accounts are unchanged.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-15]]
- Strategies: [[ATLAS]]
- Refers to: [[atlas-v2|ATLAS v2]], [[atlas-windows-entries-2026-10-30|ATLAS per-member trading windows and limit entries]]
- Runs: `atlas_deep_today, atlas_deep_zombie, atlas_deep_stuck200, atlas_deep_last_bullet08, atlas_deep_lit_won_other, atlas_deep_same_side_lost_skip, atlas_deep_week_brake400, atlas_deep_against_trend_x0`
- Source: `research/writeups/2026-11-15-atlas-deep.md`
- Back to [[ZEUS Home]]
