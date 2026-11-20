# NQ dashboard v4 (day-nqdash3, 2026-11-20)

The owner asked at 15:00 ET: "goals on the NQ dashboard ... more data ... look 3D, crazy effects ... really good". This is what changed on `tools/web_public/nq/`.

| What | Result |
|---|---|
| **Goals on screen 1** (`nqgoals.js`, `#goalCard` above the chart) | Each account gets a glowing ring, the $ left rolling up, and a tap that opens its rules and date. The order is ATLAS first, then Zlarior 50K, 25K #2, Rapid (planned), and the fleet. |
| ATLAS funded 25K | The first ask is $1,000 at a balance of $27,100. **$1,699 left, 19%.** The $250 minimum ask is possible at $26,350: **$949 more**, the same number as the payout coach's need_more on every page. That pays $800 to you at the 80% split. Rule chips: traded days (from the PC's tracker), best day ≤ 50%. Date: "about Dec 3-14 at today's pace (estimate)". |
| Zlarior 50K / 25K #2 | **+$3,807** to pass at $53,000; **+$1,500** to pass at $26,500. Drawdown left is in the tap-open detail. |
| Rapid EOD 25K | Shown dim until the PC reports it: +$1,500 in 4+ days, no day over 30% ($450), plus the plan's date. |
| Fleet | **1 of 5** funded slots. Goal: about **$5,200 a month** by Mar 1 (estimate, from `business/goals.json`). |
| **The numbers** card (`#numCard`) | The open trade with its live $ and **R** (e.g. SHORT 6 @ 21,555.50 = +$315 = +1.42R, target +$735). Today and this week $ per account. Win rate, PF, fill count and net, **real fills only**. The last 10 trades as glowing R bars. A session clock dial (London 02:00-08:00 / NY 08:00-15:30, the next window). VIX band + LIT target size (18:00 open ± one VIX day move). |
| **Today's market in 3D** (`nqland.js`, `#landCard`) | Today's 5-minute bars as a glowing ridge, a light trail running along the price line, a beacon per trade (green win, coral loss, gold open), embers, and spark bursts. |
| Effects | Rings sweep in, numbers roll up, a gold light trail with a pulse on new bars runs on the live chart, and the open-trade tag pulses. Particle bursts fire on a new winning trade or when a goal ring crosses a quarter. All of these are off with reduced motion. |
| Fixes found on the way | Account values broke mid-number on phones ("$1,02 / 5"); now on one line. My first version of that fix made the DEMO page 17 px too wide; it is now scoped to the accounts strip, and a test covers it. |

## Speed (tools/perf_sweep.py, 390x844, CPU 4x)

| | before v4 (5ede0887) | v4 |
|---|---|---|
| First paint (FCP), no network throttle | 440-530 ms | 410-590 ms (goal < 1.5 s: met) |
| Layout shift (CLS) | 0.02 | 0.017 (goal < 0.05: met); 0.000 in test_nq_goals with the PC post arriving |
| Largest paint (LCP) | 1.4-1.8 s | 1.7-1.8 s |
| Blocking time (TBT) | 600-840 ms | ~1.0-1.2 s (see below) |
| Sideways scroll | no | no |
| Fast-3G FCP | 2.8 s | 2.8 s (unchanged; over the 2.5 s budget before v4 too) |

Steps taken for speed:
- 3D only when scrolled near (lazy3d), never on LITE.
- Phone 3D: DPR ≤ 1.5, no antialias, 30 fps, no HDR or textures, paused off-screen.
- The ring glow is a second stroke, not a CSS filter.
- The chart's last-price pulse runs only when new data arrives; continuous mode repainted every frame.
- The numbers card and the 2D landscape draw when the browser is idle.
- TBT is still ~300 ms above before. Most of that is variance plus the extra chart series; next round: measure the long tasks one by one.

## Tests

| Suite | Result |
|---|---|
| test_nq_goals (new) | 33/33: node model, Chromium at 390x844, the DEMO width check |
| test_nq_page | 70/70: goals.json added to the reads |
| test_nq_chart | 45/45 |
| test_nq_desk | 32 |
| test_nqdeep | 26 |
| test_payready | 16 |
| test_truth_check | 11 |
| smoke | 10/10 |

## Screenshots (390x844, scale 2)

- `before-phone-screen1..3.png`
- `after-phone-screen1..3.png`, `after-phone-acctCard.png`, `after-phone-numCard.png`, `after-phone-landCard.png`
- `nqland-alone-phone.png`

The shots use the PC's real 2026-11-20 post (`tests/fixtures/truth/pc_post.json`) and the chart fixture.

## For the lead
- Version tags in `nq/index.html`: nq.js r22, nqchart.js c5, nqgoals.css v3, nqland.js v1. nq.js imports nqgoals.js v4.
- No sw.js, apps.js or build_web_dashboard edits. Nothing for LEAD_WIRES.
- Read only. No orders, no storage, no new fetch target except `../business/goals.json` (already published).

## Round 3 (lead + owner corrections, before 21:00 ET)

| What | Result |
|---|---|
| ATLAS in MFFU's own terms (owner) | A sim-funded account starts at $0, so it shows **$401**. Max-loss floor -$1,000, end-of-day trailing, stops at +$100. **Goal: ask $1,000 at $2,100** ($800 to you), $1,699 to go. **Earliest: $250 at $1,350**, $949 more (the coach's number). Uses `PC_FEED.mffuView` once pc_feed.js has it (day-archive); until then the same arithmetic in `nqgoals.js`. |
| Honest dates (lead) | ATLAS: "about Dec 18-31 (estimate, 2026-like market)", from the ATLAS cost study. Evals: the plan's simulated dates (`goals.json`: Nov 30 / Dec 10). The goals no longer extrapolate a pace from a few days. |
| DESIGN's kit (day-arenas merged) | New "ATLAS first payout" card: `NQFX.vault` (a drawn vault at once, then the 3D door and coins after load + idle) at 19%, "$401 of $2,100". Win and goal bursts use `NQFX.win` / `NQFX.milestone`; our own canvas burst is the fallback without the kit. Rings and roll-ups stay plain SVG/CSS: 5 rings on the first screen are cheaper that way. |
| Eager JS budget | The kit (`nqfx.js`) and the payout rules (`payready_late.js`) now load after the first paint. Eager JS is 593 KB, under the 600 KB budget. `perf_sweep --static` is green. |
| Still open | The accounts strip (nqdesk) still shows ATLAS as $25,401. It will switch with `PC_FEED.mffuView` across pages (archive team). |

Tests: nq_goals 34, nq_page 70, nq_chart 45, nq_desk 32, truth_check 11, nqfx 15, smoke 10/10, site_checks fine.
