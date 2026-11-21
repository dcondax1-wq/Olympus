# Zenith Home: main content (LCP) sooner (DESIGN, day-arenas 2026-11-21)

The browser's "main content" on Home is the greeting ("Good morning", polish.js `.pl-hi`, the largest text). It was late for two reasons, both in
`zenith_settle.js` (the still copy that hides Home's start-up jumps):

1. The greeting landed under a copy and stayed hidden until the copy's 3 s cap (the page kept changing, so it never went quiet).
   Now the copy goes the moment the greeting lands (the next burst gets a fresh copy of that frame), and the cap is 1.5 s.
2. The copy had `contain: paint`, which clipped the greeting's glow. The real greeting then counted as a bigger, newer paint ~2 s later.
   Now it is `contain: layout`. The copy and the page paint the same size, so the first paint counts.

| Same phone profile (390 x 844, 4x CPU, 1.6 Mbps / 150 ms; this cloud box is ~3x slower than a phone) | Before | After |
|---|---|---|
| LCP, returning visit (2 runs each) | 13.8 / 14.0 s | **12.1 / 12.1 s** (-1.8 s) |
| Start-up layout shift (tests/test_zenith_settle.py) | 0.015-0.05 | 0.015 |

On the lead's faster sweep this should take the 4.7 s down to about 3 s. `index.html` loads `zenith_settle.js?v=6`. The root sw.js needs nothing
(it caches by full URL).

Tests: `test_zenith_settle` 15/15 (a new static check for this rule). `test_zenith_nq` 20/20: two checks were failing since yesterday's night
default. The colour scan now covers only the note's own CSS block, and the phone is dark (a light phone keeps its light look). `test_atlas_ui` 36/36
(option 1: the dated su-sun banner is skipped). `test_feed_accounts` 47/47, smoke 11/11.
