# Order flow v4: seven more tick features - the verdict

Rules frozen first: `DESIGN_v4.md`. Built by `python -X utf8 research/orderflow/of_v4.py`. Research only, paper.

**Days:** 51 real NQ tick days 2026-09-27 .. 2026-11-26 (halves split after 2026-10-28). Lane A candidates resolved: 93. LIT replay trades in these days: 18 (bars to 2026-11-26). Holm over 12 tests that reached their floor.

**v4 on 51 real tick days (2026-09-27..2026-11-26): 0 of 21 tests CANDIDATE; 12 reached their floor (Holm over those).**

## (b) Filter on lane A (level fade; outcome R, $ at 1 micro, costs in)

| feature | with read | kept | kept $ | skipped $ | gain R | halves | p | p adj | verdict |
|---|---|---|---|---|---|---|---|---|---|
| V1 Stacked imbalances | 93 | 17 | $-844 | $+497 | 0.136 | [0.664, -0.697] | 0.3553 | 1.0 | NO |
| V2 Delta divergence at the extreme | 47 | 73 | $-244 | $-103 | -0.002 | [0.284, -0.791] | 0.3157 | 1.0 | NO |
| V3 Absorption strength (volume vs range) | 93 | 15 | $+1,546 | $-1,893 | 0.669 | [0.829, 0.465] | 0.0552 | 0.552 | NO |
| V4 Large-lot prints | 93 | 38 | $-1,071 | $+724 | -0.198 | [-0.35, -0.012] | 0.7413 | 1.0 | NO |
| V5 Delta slope into entry | 93 | 57 | $+807 | $-1,154 | 0.512 | [0.732, 0.224] | 0.0394 | 0.4608 | NO |
| V6 VWAP location | 93 | 71 | $-557 | $+210 | -0.068 | [-0.831, 0.586] | 0.6141 | 1.0 | NO |
| V7 First-15-minute delta | 93 | 40 | $+1,098 | $-1,445 | 0.371 | [-0.106, 0.914] | 0.1078 | 0.9702 | NO |

Inside lane A's TAKEN (absorbed) trades only - information, no p (on top of the absorption gate):

| feature | kept | kept $ | skipped $ | gain R | halves |
|---|---|---|---|---|---|
| V1 Stacked imbalances | 11 of 40 | $-98 | $+1,680 | -0.185 | [0.318, -0.784] |
| V2 Delta divergence at the extreme | 29 of 40 | $+754 | $+829 | -0.556 | [0.098, -1.393] |
| V3 Absorption strength (volume vs range) | 10 of 40 | $+1,084 | $+498 | 0.403 | [1.007, -0.537] |
| V4 Large-lot prints | 12 of 40 | $+368 | $+1,214 | -0.362 | [-0.724, 0.047] |
| V5 Delta slope into entry | 24 of 40 | $+1,370 | $+212 | 0.319 | [1.06, -0.499] |
| V6 VWAP location | 29 of 40 | $+1,384 | $+198 | 0.56 | [-0.041, 0.999] |
| V7 First-15-minute delta | 19 of 40 | $+1,696 | $-113 | 0.448 | [0.044, 1.001] |

Lane A, every candidate as if taken: $-347 at 1 micro.

## (a) Filter on LIT (Zlarior's replay trades, $ at LIT's own size)

| feature | with read | kept | all $ | kept $ | gain $ | p | verdict |
|---|---|---|---|---|---|---|---|
| V1 Stacked imbalances | 18 | 1 | $+5,682 | $-2 | -336.258 | 0.5017 | TOO FEW (18 of 20) |
| V2 Delta divergence at the extreme | 17 | 7 | $+5,682 | $+3,316 | 258.724 | 0.2342 | TOO FEW (17 of 20) |
| V3 Absorption strength (volume vs range) | 18 | 3 | $+5,682 | $+9 | -375.172 | 0.6337 | TOO FEW (18 of 20) |
| V4 Large-lot prints | 18 | 8 | $+5,682 | $+2,824 | 67.245 | 0.4497 | TOO FEW (18 of 20) |
| V5 Delta slope into entry | 18 | 10 | $+5,682 | $-1,249 | -991.32 | 0.9938 | TOO FEW (18 of 20) |
| V6 VWAP location | 18 | 16 | $+5,682 | $+6,266 | 683.524 | 0.0404 | TOO FEW (18 of 20) |
| V7 First-15-minute delta | 3 | 16 | $+5,682 | $+5,463 | 231.836 | 0.3357 | TOO FEW (3 of 20) |

## (c) Standalone 30-minute signal (1 micro, 2 ticks + $1.40 costs)

| feature | trades | /week | net $ | $/month | mean $ | won | PF | max DD | halves mean $ | p | p adj | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V1 Stacked imbalances | 275 | 27.0 | $-2,481 | $-1,022 | -9.02 | 46.9% | 0.87 | $3,086 | [-8.47, -9.76] | 0.7103 | 1.0 | NO |
| V2 Delta divergence at the extreme | 214 | 21.0 | $-1,604 | $-661 | -7.5 | 45.8% | 0.88 | $4,445 | [-6.09, -8.93] | 0.6515 | 1.0 | NO |
| V3 Absorption strength (volume vs range) | 86 | 8.4 | $+1,426 | $+587 | 16.58 | 54.7% | 1.24 | $1,327 | [8.15, 27.22] | 0.2152 | 1.0 | NO |
| V4 Large-lot prints | 5 | 0.5 | $+56 | $+23 | 11.1 | 40.0% | 1.23 | $159 | [-68.9, 64.43] | 0.4283 | None | TOO FEW (5 of 40) |
| V5 Delta slope into entry | 8 | 0.8 | $+215 | $+88 | 26.85 | 50.0% | 1.74 | $123 | [25.18, 31.85] | 0.2394 | None | TOO FEW (8 of 40) |
| V6 VWAP location | 152 | 14.9 | $+4,414 | $+1,818 | 29.04 | 55.9% | 1.52 | $2,209 | [8.64, 52.32] | 0.0384 | 0.4608 | NO |
| V7 First-15-minute delta | 44 | 4.3 | $-610 | $-251 | -13.87 | 52.3% | 0.87 | $2,012 | [-33.14, 7.24] | 0.6169 | 1.0 | NO |

## Forward watch list (DESIGN_v4 addendum: W1 V7 in taken lane A, W2 V6 standalone, W3 V5 / W4 V3 lane A filters)

forward: 0 tick days from 2026-11-27 yet (watch list W1-W4 waits)

## LEAD_WIRES: which features to log forward on the PC (engine/oflive.py; the lead wires, no engine change here)

1. **V6 VWAP location** - candidate in: none; best raw p (lane A / standalone) 0.0384; cost cheap (running price x volume sum).
2. **V5 Delta slope into entry** - candidate in: none; best raw p (lane A / standalone) 0.0394; cost cheap (3-bar delta sum).
3. **V3 Absorption strength (volume vs range)** - candidate in: none; best raw p (lane A / standalone) 0.0552; cost medium (bar volume / range, 12-bar median).
4. **V7 First-15-minute delta** - candidate in: none; best raw p (lane A / standalone) 0.1078; cost cheap (one delta sum at 09:45).
5. **V2 Delta divergence at the extreme** - candidate in: none; best raw p (lane A / standalone) 0.3157; cost cheap (running CVD + 12-bar extreme).
6. **V1 Stacked imbalances** - candidate in: none; best raw p (lane A / standalone) 0.3553; cost medium (per-price buckets of one bar).
7. **V4 Large-lot prints** - candidate in: none; best raw p (lane A / standalone) 0.7413; cost cheap (signed sum of big prints).

Nothing here changes a bot. A CANDIDATE only earns forward logging; the strategy-proof protocol (both 2026 halves and 2021-25) cannot be met with tick days this short. The lead's wiring list: `LEAD_WIRES_v4.md`.
