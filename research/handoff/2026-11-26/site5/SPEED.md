# Speed: Home and NQ at 390 x 844 on throttled 4G (day-site5 C2, 2026-11-26)

**How measured** (`speed.cjs` in this folder, re-run: `node speed.cjs 3` from here; `PUB=<other web_public>` measures another checkout):
Node Playwright + CDP, 390 x 844 mobile, cold cache every run, **4G = 150 ms latency, 1.6 Mbps down, 750 Kbps up, CPU 4x slower**, the site served
by a local static server that gzips text like GitHub Pages, requests to other hosts aborted (ntfy, cdnjs: not ours to time). Median of 3 runs.
"KB@+6s" = everything the phone downloads in the 6 s after the load event (the lazy 3D, the data reads): it still competes for a phone's bandwidth.
Before = origin/pc 18312c55 (clean worktree); after = this branch. First open of the day plays the Home intro (the tiles fade in), so LCP there is the
intro; `REPEAT=1` = a second open the same New York day.

| Page | FCP ms | LCP ms | load ms | CLS | KB at load | requests at load | KB by load + 6 s | JS KB by load + 6 s |
|---|---|---|---|---|---|---|---|---|
| Home before | 1,104 | 1,956 | 1,828 | 0 | 237 | 33 | 495 | 393 |
| **Home after** | **804** | 2,028 | 1,880 | 0 | 238 | 33 | **312** | **209** |
| Home before, repeat open (no intro) | 1,120 | 1,120 | 1,870 | 0 | 238 | 35 | 495 | 393 |
| **Home after, repeat open** | **780** | **780** | 2,049 | 0 | 239 | 35 | **312** | **209** |
| NQ before | 1,204 | 2,656 | 3,270 | 0.316 | 384 | 44 | 640 | 537 |
| NQ after (only the shared hero.js changed) | 1,148 | 2,536 | 3,090 | 0.323 | 385 | 44 | 457 | 353 |

Without gzip (`GZIP=0`, a plain file host) the same before run was: Home FCP 2,384 / LCP 3,064 / load 3,819 ms, 1,579 KB by +6 s; NQ FCP 2,508 /
LCP 5,244 / load 6,459 ms, 2,057 KB. The order of the costs is the same.

## What was cut (Home)
1. **A hidden second round trip before the first paint.** `olympus/agora.css` `@import`s `warp.css`, so the phone asked for warp.css only after
   agora.css arrived, and the first paint waited for both (render-blocking chain). Home's head now preloads the exact URL
   (`olympus/warp.css?v=w3`) next to agora.css: both come at once, the @import takes it from the cache. **FCP -300 ms (-27%)**, LCP on a repeat open
   -340 ms. (gate/index.html head loader.)
2. **The 3D temple waits.** `pillars/hero.js` (Home, Zenith, NQ heroes) started three.js + the scene (~720 KB, ~185 KB gzipped) as soon as the hero
   was on screen, during the data reads. Now it starts when the page is idle (requestIdleCallback, 3 s cap), and on a slow / metered connection
   (Save-Data, 2G / 3G, or < 5 Mbps where the phone reports it; iPhone Safari does not, so it gets the idle path) it keeps the 2D columns until the
   first touch on the hero. `?fx=3d` / `?fx=hq` still force it at once (tests, shots). **-183 KB (-37%) and -184 KB of JS in the first seconds**;
   the same cut reaches NQ's hero (-183 KB there too).
3. **A request that always failed.** gate.js asked `me/me.json` on every open; only the PC's own link (/site/) serves it, so on the public site it was a
   404 each time. Now asked only on the PC.

The 6 dashboards + More stay on the first 390 x 844 screen (tests: test_pillars_hero gateMore, perf_sweep --static, test_gate_page static).

## NQ: proposals (its files belong to day-livedash, not edited here)
| Cut | Where | Expected |
|---|---|---|
| The same warp.css preload before `../olympus/agora.css?v=a11` (`<link rel="preload" as="style" href="../olympus/warp.css?v=w3">`) | nq/index.html head | ~-250 to -300 ms FCP / LCP, as on Home |
| `olympus/sfx.js` (104 KB, 32 KB gz) loads up front: load it on the first tap (sound needs a gesture anyway) | nq/index.html | -32 KB before load |
| lightweight-charts (193 KB, 61 KB gz) only when the chart card nears the screen (IntersectionObserver) | nq chart loader | -61 KB before load, earlier load event |
| CLS 0.32: the chart card jumps above the goals card at ~8.4 s (0.197) and the header grows twice (brand 48 -> 96 -> 144 px: the breadcrumb rows arriving, 0.03) | nq layout / gate-nav crumb | reserve the chart card's slot and the crumb row height from the first paint -> CLS < 0.05 |
| `pillars/hero.js?v=c3` -> `?v=c4` (the lazy 3D above already reaches NQ through the shared file; the bump makes phones refetch it) | nq/index.html line 225 | cache only |
