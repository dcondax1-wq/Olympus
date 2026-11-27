# night-nq-speed results (2026-11-27)

Phone: Chromium 390x844, CPU x4, 4G line (9 Mbps / 170 ms RTT), service workers blocked, REAL signed ntfy feed (nothing mocked),
published home.json. Median of 3. `python -X utf8 tools/nq_speed_probe.py --runs 3` (table: probe_4g.md, raw: probe_4g.json).
"after" = the same pages with ONE tag added in the browser (`<script src="nqfeed.js?v=1">` after pc_feed.js); no page JS changed yet.

| page | PC post ready, before | after (cold) | after (2nd visit) | cached post ready (2nd visit) | feed KB 2nd visit |
|---|---|---|---|---|---|
| NQ home (index) | 2106 ms (numbers on screen 2390) | 1316 (on screen 1612) | 1290 (on screen 1636) | 487 ms | 66 -> 0.3 |
| Live | 1468 | 823 | 785 | 252 | 66 -> 0.3 |
| Accounts | 1519 | 816 | 745 | 243 | 53 -> 0 |
| Brain | 1974 | 1104 | 1241 | 494 | 53 -> 0 |

- All 4 pages now have the PC's numbers in ~0.8-1.3 s (goal 1-2 s): 35-45% faster.
- The "cached post ready" column = when a page that uses `NQ_FEED.cached()` / `on()` can paint numbers + their age (page owners' step, NQCORE_API.md section 2): 0.25-0.5 s.
- New PC posts show in ~1 min (60 s probe, empty answer ~0.3 KB) instead of the pages' 5-minute refresh.
- Whole-page sweep before (perf_sweep, Fast-3G): before_sweep.md (fcp 3.3 s, lcp 5.4 s, JS 1 MB: page weight is the page owners' area).
- Shots 390x844: shots/before_*.png, shots/after_*.png (ids masked by the pages).
