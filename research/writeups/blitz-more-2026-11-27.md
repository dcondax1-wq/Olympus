---
title: BLITZ more tests (2026-11-27 night) - 12 pre-registered variants + 1 combination; 0 picked on Jan-Jun, nothing makes 2021-25 hold up
family: other
date: 2026-11-27
status: rejected (no change) - research only, nothing live touched
summary: Owner - "BLITZ, I want more tests". 12 single changes to today's BLITZ (fewer trades a day, loss-streak pause, time cutoffs, morning / afternoon only, daily-trend filter, VIX filter, stop cap, tighter / wider stop, 2R target, 60-minute hold) written down in research/blitzmore/DESIGN.md before the first run, judged pick Jan-Jun 2026, check Jul-Nov 2026 + 2021-25, costs in, Holm-corrected. 0 of 12 beat today on Jan-Jun, so none was picked; the best 2021-25 numbers cost 2026 money and are not significant (Holm p 1.0).
runs: none (research/blitzmore/results.json, explore.json); code research/blitzmore/{blitzmore,explore,evals}.py on research/blitzv2 (parity 397/397 on 2026 1m, 2,304/2,304 on 5m)
---

## For the owner (one minute)
**No change to BLITZ makes it hold up in 2021-25. Keep it on paper.** Today: PF 1.63 / 1.41 / 1.06 and $912 / $662 / $89 a month
(2026 Jan-Jun / Jul-Nov 20 / 2021-25), costs in, $150 a trade.

| What | Result |
|---|---|
| 12 pre-registered changes | **0 beat today on Jan-Jun** (the pick), so 0 passed; 0 significant after Holm (all p = 1.0) |
| Best 2021-25 | 60-minute hold PF 1.10, $160 a month (today $89) and afternoon-only PF 1.16, $150 a month, but afternoon-only gives up Jan-Jun ($264 vs $912) and the 60-minute hold gives up Jan-Jun ($460) |
| Trade-offs (better 2021-25, much worse 2026) | afternoon only; VIX >= 18 |
| Worse everywhere | max 3 a day, loss-streak pause, no entry after 14:30, morning only, daily-trend filter, stop cap, tighter stop |
| 2R target / wider stop (2.0 ATR) | about the same as today in 2026 ($793 / $871 vs $912), small 2021-25 gain ($108 / $111 vs $89), not significant |
| Does the 25K eval improve? | No variant has pass up and fail down in both 2026 spans (today 25K at $400: 57 / 40 / 24% pass, 43 / 60 / 76% fail) |
| Reverse pick (pick 2021-24, check 2025 + 2026; exploratory) | the 60-minute hold, the wider stop and both together: 2021-24 PF 1.10-1.16 but 2025 $82-115 vs $139 and Jan-Jun $460-871 vs $912: none holds |

Next (nothing changes tonight):
1. Nothing to do; the BLITZ paper lane keeps collecting forward trades (gate in research/handoff/2026-11-27/blitz/).
2. The only live leads: the 60-minute hold and the wider stop (both lift 2021-25 a little, both keep 2026 positive). Worth one more pre-registered round only with new data (tick days), not from this one.
3. If BLITZ is ever revived, start from blitzv2 V1 (noise-area exit, PF 1.34 in 2021-25) as the base, not today's 30-minute clock.

## Method
Today's rule (engine/blitz.py) through research/blitzv2/blitzv2.py's port (parity: 2026 1m 397/397 trades, 2021-26 5m 2,304/2,304, same $).
2026 on 1m, 2021-25 on 5m (no 1m before 2026). $150 a trade, $1.90 a micro + 1 tick per market / stop fill; the +1 tick column = one more tick each
way ($1 a micro). Rules fixed before the run (DESIGN.md): PICK = Jan-Jun $ / month above today's with PF within 0.05; CHECK = Jul-Nov and 2021-25
$ / month at least today's; "holds up" also needs 2021-25 PF >= 1.15, +1 tick PF > 1.05, every year 2022-25 >= $0, Holm p <= 0.05 (sign-flip
test on daily $ difference vs today, 13 tests). Already-rejected ideas not repeated: V1-V8 (blitzv2), the 8 exit ideas, streak size, max 3 on the Rapid, LIT / ATLAS-flat (no help).

## Results ($150 a trade, costs in; trades / week | PF | $ / month | max DD)
| Variant | 2026 Jan-Jun | 2026 Jul-Nov 20 | 2021-25 | 2021-25 +1 tick PF | years 22 / 23 / 24 / 25 ($/mo) | Walk-fwd | Holm p |
|---|---|---|---|---|---|---:|---:|
| **V0 today** | 8.6 / 1.63 / $912 / -1,314 | 8.2 / 1.41 / $662 / -1,254 | 8.7 / 1.06 / $89 / -4,783 | 1.06 | 264 / 111 / -144 / 139 | - | - |
| M1 max 3 a day | 5.8 / 1.70 / $684 / -1,073 | 5.6 / 1.06 / $77 / -931 | 5.9 / 1.02 / $20 / -5,330 | 1.02 | 117 / 59 / -55 / -69 | 6/19 | 1.0 |
| M2 pause after 2 losses | 7.4 / 1.74 / $904 / -1,284 | 7.0 / 1.37 / $522 / -1,069 | 7.4 / 1.02 / $29 / -7,895 | 1.02 | 297 / -53 / -202 / 73 | 6/19 | 1.0 |
| M3 no entry after 14:30 | 6.8 / 1.61 / $686 / -915 | 6.7 / 1.15 / $211 / -1,178 | 7.1 / 1.02 / $25 / -4,094 | 1.02 | 95 / -2 / 7 / 29 | 7/19 | 1.0 |
| M4 morning only (to 12:30) | 3.5 / 2.11 / $586 / -846 | 3.8 / 0.83 / -$165 / -1,614 | 3.7 / 0.93 / -$48 / -4,798 | 0.93 | -16 / -99 / -9 / -113 | 4/19 | 1.0 |
| M5 afternoon only (13:00+) | 5.4 / 1.26 / $264 / -1,198 | 4.6 / 2.36 / $851 / -490 | 5.3 / 1.16 / $150 / -3,775 | 1.16 | 272 / 313 / -234 / 313 | 10/19 | 1.0 |
| M6 daily-trend aligned | 4.9 / 1.48 / $409 / -1,141 | 4.5 / 1.76 / $729 / -859 | 4.6 / 1.09 / $73 / -2,555 | 1.09 | 121 / 96 / 10 / 69 | 6/19 | 1.0 |
| M7 prior VIX >= 18 | 5.2 / 1.46 / $438 / -1,314 | 3.1 / 1.34 / $247 / -924 | 4.6 / 1.13 / $108 / -3,007 | 1.13 | 246 / 123 / -14 / 92 | 9/19 | 1.0 |
| M8 skip stop > 0.40% | 7.9 / 1.52 / $651 / -1,314 | 7.2 / 1.22 / $269 / -903 | 8.1 / 1.05 / $74 / -3,851 | 1.05 | 299 / 71 / -151 / 85 | 5/19 | 1.0 |
| M9 tighter stop 1.0 ATR | 9.3 / 1.18 / $369 / -1,449 | 9.0 / 1.23 / $446 / -1,638 | 9.3 / 1.02 / $43 / -3,932 | 1.02 | 75 / -14 / 93 / 25 | 7/19 | 1.0 |
| M10 wider stop 2.0 ATR | 8.5 / 1.65 / $871 / -1,065 | 7.9 / 1.23 / $407 / -1,588 | 8.4 / 1.09 / $111 / -3,325 | 1.09 | 209 / 168 / 5 / 87 | 9/19 | 1.0 |
| M11 fixed target 2R | 8.8 / 1.54 / $793 / -1,314 | 8.6 / 1.37 / $649 / -1,254 | 8.8 / 1.07 / $108 / -5,438 | 1.07 | 277 / 212 / -189 / 161 | 10/19 | 1.0 |
| M12 60-minute hold | 6.9 / 1.27 / $460 / -1,387 | 6.5 / 1.58 / $841 / -1,295 | 7.1 / 1.10 / $160 / -3,663 | 1.10 | 397 / 253 / -89 / 115 | 12/19 | 1.0 |
| M13 combination of survivors | none survived = today | | | | | | 1.0 |

(+1 tick moves PF by 0.00-0.04 in these tables; per-variant +1-tick $ are in results.json.) Winning variants lose or only tie in the other regime
(M5 / M12 win Jul-Nov and 2021-25 and lose Jan-Jun; M4 and M3 do the opposite): the pattern of a regime bet, not a filter that fixes it.
Evals at $400 a trade (account C's size, 40 sessions, rolling starts, results.json evals_at_400): today 25K pass / fail 57 / 43 (Jan-Jun), 40 / 60 (Jul-Nov),
24 / 76 (2021-25), median 12 / 5.5 / 10 sessions; Rapid EOD 25K 20 / 54, 0 / 85, 3 / 84. Best variant on the 25K: M10 Jan-Jun 74 / 22 but Jul-Nov 33 / 67; M5
Jul-Nov 90 / 10 but Jan-Jun 40 / 60. None improves pass and fail together in both 2026 spans.

## Verdict
**Nothing makes 2021-25 hold up.** The two changes that lift 2021-25 the most (60-minute hold $160, afternoon only $150 a month) are still PF 1.10 / 1.16 with
2024 negative, Holm p = 1.0, and each gives back $450-650 a month of Jan-Jun. The 2021-25 weakness is the market (a bet on trending years: blitzv2), not a setting.
Keep BLITZ paper only (the forward gate stands), no Decide card. Re-test only with new data.
