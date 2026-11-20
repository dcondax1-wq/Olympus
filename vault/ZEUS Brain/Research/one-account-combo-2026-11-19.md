---
tags:
  - zeus/research
  - family/risk
  - verdict/research
  - bot/zlarior
  - bot/atlas
  - bot/blitz
  - lane/rapid
  - lane/combo50k
type: "research"
date: "2026-11-19"
status: "done - paper only. On the Builder 50K, Zlarior + ATLAS on the same account (each at its own size, one position at a time, first in keeps it) beats Zlarior alone in Jan-Jun, Jul-Oct AND 2021-25 ..."
source: "research/writeups/one-account-combo-2026-11-19.md"
aliases:
  - "ONE account, several bots"
---

# ONE account, several bots

> [!abstract] Verdict: research
> done - paper only. On the Builder 50K, Zlarior + ATLAS on the same account (each at its own size, one position at a time, first in keeps it) beats Zlarior alone in Jan-Jun, Jul-Oct AND 2021-25 (pre-registered rule) - one Decide card. Builder 25K and Rapid EOD 25K - no combo beats today's setup in every period. Nothing live changed.

**Full title:** ONE account, several bots - Zlarior + ATLAS (+ BLITZ) on a Builder 50K, Builder 25K or Rapid EOD 25K

## Summary

Owner 2026-11-19 - "one account trade a lot of times for NQ with multiple strategies ... 25K or 50K Builder ... or a 25K Rapid EOD - don't give me bullshit results". Design committed before any result (4e682267). Bots as they are today (Zlarior 120 + 511 trades, ATLAS raw members, BLITZ alone, the post-close lead as a sensitivity), one net position (first-in; same-side adds as a sensitivity), every bot sized from ONE shared room by its own live rule (and by engine/rapid's one-account lane rule), MFFU rules per plan, owner's CLUB prices, costs in (+1 tick sensitivity), whole-day bootstrap 2,000 x 126 sessions, the same paths for every row. 160 rows x 3 periods = 480 results; 54 rows judged against today's setup. Builder 50K, $ a month after fees - Zlarior alone $827 / $714 / -$7, Zlarior + ATLAS $1,888 / $1,286 / $44 (eval median 5-7 days instead of 9-10, 60-day fails 9-13% unchanged in 2026, but 2-week fails 0.1% -> 2-4%, 2021-25 0.5% -> 34%). Adding BLITZ too - $2,242 / $1,443 / $34 but eval fails double (22-25%) and one BLITZ trade can risk $2,100. Placebo - with ATLAS's edge set to zero the combo makes LESS than Zlarior alone ($388 / $529), so the gain is ATLAS's edge, not extra variance. By year - wins 2023 / 2024 / 2025, loses 2022 (-$113 a month vs Zlarior alone). Account - Builder 50K wins of the three asked (2x the room per $ of fee, 40 micros, no eval best-day rule); the Rapid EOD 25K's 30% / 4-day eval takes 25-31 days and its funded accounts get stuck often; Builder 25K pays about half of the 50K.

## Money first

| Account | Row | gap vs today $/month H1 / H2 / 21-25 (2 SE) | beats today? |
|---|---|---|---|
| Builder 50K | Z+A (own) | +1,060 (21) / +572 (19) / +51 (12) | YES |
| Builder 50K | Z+A (lanes) | +652 (19) / +452 (19) / -15 (8) | no |
| Builder 50K | Z+B (own) | +386 (14) / +359 (15) / +1 (7) | no |
| Builder 50K | Z+B (lanes) | +291 (13) / +381 (14) / +12 (6) | no |
| Builder 50K | A+B (own) | +901 (28) / +147 (28) / +69 (14) | YES |
| Builder 50K | A+B (lanes) | +818 (27) / +161 (27) / +74 (13) | YES |
| Builder 50K | Z+A+B (own) | +1,415 (23) / +729 (20) / +42 (13) | YES |
| Builder 50K | Z+A+B (lanes) | +902 (21) / +689 (20) / -4 (9) | no |
| Builder 50K | Z eval, Z+A funded (own) | +800 (19) / +432 (16) / +18 (7) | YES |
| Builder 50K | Z eval, Z+A funded (lanes) | +506 (17) / +366 (16) / +0 (6) | no |
| Builder 50K | Z eval, Z+B funded (own) | +314 (11) / +264 (11) / +9 (4) | YES |
| Builder 50K | Z eval, Z+B funded (lanes) | +258 (12) / +312 (12) / +13 (5) | YES |
| Builder 50K | Z eval, Z+A+B funded (own) | +1,023 (22) / +516 (18) / +23 (8) | YES |
| Builder 50K | Z eval, Z+A+B funded (lanes) | +688 (19) / +527 (17) / +3 (6) | no |
| Builder 25K | Z+A (own) | +502 (13), +240 (11) / +234 (12), +240 (12) / +6 (4), -2 (6) | no |
| Builder 25K | Z+A (lanes) | +294 (10), +32 (9) / +130 (11), +136 (12) / -4 (3), -12 (6) | no |
| Builder 25K | Z+B (own) | +244 (11), -18 (15) / +75 (11), +82 (16) / -5 (3), -13 (7) | no |
| Builder 25K | Z+B (lanes) | +30 (7), -232 (14) / +172 (8), +178 (14) / +4 (3), -4 (7) | no |
| Builder 25K | A+B (own) | +509 (15), +247 (8) / +53 (14), +60 (8) / -8 (8), -16 (5) | no |
| Builder 25K | A+B (lanes) | +298 (13), +36 (6) / +160 (14), +167 (6) / +8 (7), +0 (4) | no |
| Builder 25K | Z+A+B (own) | +677 (17), +415 (16) / +195 (15), +202 (15) / +2 (5), -6 (6) | no |
| Builder 25K | Z+A+B (lanes) | +297 (11), +35 (11) / +262 (12), +269 (12) / +0 (4), -8 (6) | no |
| Builder 25K | Z eval, Z+A funded (own) | +378 (10), +116 (14) / +185 (9), +192 (13) / +4 (3), -4 (6) | no |
| Builder 25K | Z eval, Z+A funded (lanes) | +227 (9), -35 (12) / +114 (8), +120 (13) / +1 (3), -7 (6) | no |
| Builder 25K | Z eval, Z+B funded (own) | +219 (7), -43 (15) / +81 (6), +87 (15) / +3 (2), -5 (6) | no |
| Builder 25K | Z eval, Z+B funded (lanes) | +39 (5), -223 (14) / +133 (6), +139 (14) / +3 (2), -5 (6) | no |
| Builder 25K | Z eval, Z+A+B funded (own) | +532 (12), +270 (16) / +184 (9), +191 (14) / +7 (3), -1 (6) | no |
| Builder 25K | Z eval, Z+A+B funded (lanes) | +239 (9), -23 (12) / +200 (9), +207 (14) / +1 (3), -7 (6) | no |
| Rapid EOD 25K | Z+A (own) | -316 (22) / +26 (13) / -2 (4) | no |
| Rapid EOD 25K | Z+B (own) | -1,172 (48) / -165 (27) / -6 (5) | no |
| Rapid EOD 25K | Z+B (lanes) | -1,638 (43) / -14 (24) / -2 (5) | no |
| Rapid EOD 25K | A+B (own) | -595 (40) / -282 (25) / -20 (8) | no |
| Rapid EOD 25K | A+B (lanes) | -1,091 (36) / +20 (24) / -11 (7) | no |
| Rapid EOD 25K | Z+A+B (own) | +166 (39) / +70 (23) / +0 (6) | no |
| Rapid EOD 25K | Z+A+B (lanes) | +2 (30) / +470 (19) / +10 (5) | no |
| Rapid EOD 25K | Z eval, Z+A funded (own) | -1,336 (41) / -288 (21) / -1 (5) | no |
| Rapid EOD 25K | Z eval, Z+A funded (lanes) | -1,172 (41) / -296 (20) / +0 (5) | no |
| Rapid EOD 25K | Z eval, Z+B funded (own) | -1,592 (43) / -405 (24) / -2 (5) | no |
| Rapid EOD 25K | Z eval, Z+B funded (lanes) | -1,786 (42) / -332 (23) / -2 (5) | no |
| Rapid EOD 25K | Z eval, Z+A+B funded (own) | -1,107 (46) / -301 (23) / +0 (5) | no |
| Rapid EOD 25K | Z eval, Z+A+B funded (lanes) | -1,165 (43) / -125 (24) / +1 (5) | no |
| Rapid EOD 50K (reference) | Z+A (own) | -1,048 (39) / -260 (27) / -17 (10) | no |
| Rapid EOD 50K (reference) | Z+B (own) | -3,144 (87) / -640 (61) / -24 (15) | no |
| Rapid EOD 50K (reference) | Z+B (lanes) | -3,361 (88) / -426 (61) / -21 (15) | no |
| Rapid EOD 50K (reference) | A+B (own) | -1,627 (66) / -1,167 (58) / +13 (17) | no |
| Rapid EOD 50K (reference) | A+B (lanes) | -1,782 (67) / -785 (61) / +18 (17) | no |
| Rapid EOD 50K (reference) | Z+A+B (own) | -77 (52) / +181 (40) / +1 (16) | no |
| Rapid EOD 50K (reference) | Z+A+B (lanes) | +913 (45) / +1,085 (43) / +14 (14) | no |
| Rapid EOD 50K (reference) | Z eval, Z+A funded (own) | -3,008 (76) / -900 (43) / -27 (13) | no |
| Rapid EOD 50K (reference) | Z eval, Z+A funded (lanes) | -2,356 (81) / -704 (41) / -23 (13) | no |
| Rapid EOD 50K (reference) | Z eval, Z+B funded (own) | -3,993 (84) / -1,128 (56) / -31 (14) | no |
| Rapid EOD 50K (reference) | Z eval, Z+B funded (lanes) | -4,051 (85) / -951 (58) / -30 (14) | no |
| Rapid EOD 50K (reference) | Z eval, Z+A+B funded (own) | -2,558 (84) / -733 (48) / -27 (14) | no |
| Rapid EOD 50K (reference) | Z eval, Z+A+B funded (lanes) | -2,014 (91) / -93 (55) / -24 (14) | no |

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-19]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[BLITZ (paper)]], [[Rapid lanes]], [[50K combo]]
- Refers to: [[b-holds-vs-lit-priority|B-holds vs LIT priority]], [[rapid-25k-vs-50k-2026-11-17|MFFU Rapid EOD 25K vs Rapid EOD 50K for LIT + ATLAS]]
- Runs: `none (research/lab/combo_account.json, research/lab/combo_account_honesty.json)`
- Source: `research/writeups/one-account-combo-2026-11-19.md`
- Back to [[ZEUS Home]]
