# Olympus PERF + OFFLINE baseline (2026-11-20, day-quality)

**How measured:** `python -X utf8 tools/perf_sweep.py` (repeatable; budgets in `tools/perf_budgets.json`, `--check` = exit 1 over budget;
test `tests.test_perf_sweep`). Every VISIBLE app (32: apps-list minus the Doors ARCHIVE, + Jarvis, Gate, Hub), each in a fresh phone
context: 390 x 844 at 2x, touch, **CPU x4 slower, DevTools Fast 3G** (562 ms round trip, 1.44 Mbit/s), cold (no cache, no worker),
6 s settle after load. Served from the repo tree over https with gzip like GitHub Pages; files the publish build writes (home.json,
data.json, icons/ ...) 404 here and are listed apart, not counted as errors. Offline = as on the phone: Zenith opened once (it
registers the root worker), the app opened once, the network cut, reload. Headless Chromium + SwiftShader: WebGL numbers are
relative, not a real-phone figure. Raw: `baseline.json` next to this file.

## The bar vs today

| Olympus bar | Today |
|---|---|
| useful in 5 s, first paint < 1 s phone profile | first paint 1.3-2.9 s on Fast 3G (the line alone costs ~1.1 s: two round trips); **largest paint > 4 s on 16 of 32** (worst: tyche 11.2 s, fates 9.5 s, compass 7.9 s, nq 6.5 s) |
| no long task > 200 ms | **15 of 32 break it**: cities 4114 ms, tyche 3341 ms, jarvis 2012 ms, fates 1832 ms, kronos 1438 ms, ledger 1342 ms |
| CLS 0 | **20 of 32 over 0.1**: agency 0.948, dionysus 0.898, demeter 0.849, kronos 0.83, chrysos 0.756, inbox 0.713, clio 0.707, board 0.66 |
| no huge downloads on open | 7 over 500 KB on first open: jarvis 1569 KB, nq 947 KB, zenith 813 KB, kronos 647 KB, compass 589 KB, fates 580 KB, helios 511 KB; three.js (163 KB gz, 654 KB to parse) on open in 13: fates, cities, ledger, mercury, chrysos, oikos, aegis, kronos, compass, helios, nq, tyche, jarvis |
| 0 console errors | 0 real errors in every app (only built-at-publish files 404 in the repo tree) |
| no sideways scroll | none at 390 px |
| offline = last data + age | **3 of 32 open offline** (zenith, kalshi, jarvis); the other 29: the browser's "no internet" page. Fix ready: LEAD_WIRES 1 (tested: 11 of 11 then open) |

## Every app

| app | first paint ms | largest paint ms | KB first open | JS KB | img KB | font KB | long tasks (max ms) | TBT ms | CLS | heap MB | errors | sideways | offline |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| zenith | 1692 | 1820 | 813 | 2091 | 4 | 0 | 4 (115) | 112 | 0.28 | 5.5 | 0 | no | ok (sw) |
| fates | 2900 | 9460 | 580 | 1252 | 0 | 0 | 14 (1832) | 4210 | 0.073 | 15.3 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| cities | 1656 | 1656 | 494 | 1183 | 64 | 0 | 5 (4114) | 8035 | 0.006 | 14.4 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| journal | 2220 | 4368 | 346 | 486 | 0 | 0 | 2 (112) | 99 | 0.196 | 4.1 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| ledger | 2740 | 5320 | 492 | 1421 | 1 | 0 | 17 (1342) | 3407 | 0.097 | 10.4 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| inbox | 2244 | 3884 | 209 | 501 | 1 | 0 | 1 (63) | 13 | 0.713 | 3.0 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| settings | 2848 | 3196 | 213 | 522 | 1 | 0 | 3 (234) | 255 | 0.06 | 2.9 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| planner | 2216 | 5416 | 260 | 606 | 1 | 0 | 4 (119) | 92 | 0.291 | 3.3 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| demeter | 2144 | 4188 | 214 | 462 | 1 | 0 | 2 (97) | 60 | 0.849 | 3.1 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| hera | 2276 | 4056 | 216 | 464 | 1 | 0 | 1 (73) | 23 | 0.244 | 3.2 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| dionysus | 2248 | 2648 | 195 | 445 | 1 | 0 | 3 (135) | 131 | 0.898 | 2.9 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| pnyx | 2228 | 2716 | 228 | 506 | 1 | 0 | 4 (115) | 143 | 0.209 | 3.1 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| mercury | 2256 | 4056 | 373 | 1114 | 1 | 0 | 54 (492) | 993 | 0.09 | 7.6 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| chrysos | 2248 | 4264 | 464 | 1362 | 1 | 0 | 3 (323) | 466 | 0.756 | 6.4 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| oikos | 2320 | 6332 | 388 | 1146 | 1 | 0 | 21 (508) | 653 | 0.202 | 7.9 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| aegis | 2132 | 4480 | 490 | 1458 | 1 | 0 | 4 (374) | 407 | 0.362 | 6.4 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| kronos | 2200 | 5848 | 647 | 1457 | 30 | 0 | 90 (1438) | 4200 | 0.83 | 11.6 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| compass | 2140 | 7892 | 589 | 1366 | 0 | 0 | 1 (344) | 294 | 0.457 | 7.7 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| helios | 2236 | 4888 | 511 | 1485 | 1 | 0 | 3 (229) | 261 | 0.273 | 6.8 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| nq | 2220 | 6484 | 947 | 1758 | 234 | 0 | 13 (803) | 1999 | 0.58 | 12.1 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| agency | 2252 | 3852 | 184 | 432 | 1 | 0 | 3 (104) | 82 | 0.948 | 2.8 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| business | 2732 | 3056 | 278 | 629 | 1 | 0 | 4 (112) | 121 | 0.101 | 3.3 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| trading | 2584 | 5796 | 344 | 795 | 1 | 0 | 4 (290) | 495 | 0.032 | 4.1 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| board | 2380 | 2596 | 141 | 264 | 0 | 0 | 1 (66) | 16 | 0.66 | 2.4 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| widget | 1316 | 1316 | 15 | 25 | 0 | 0 | 1 (94) | 44 | 0.0 | 1.2 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| clio | 2052 | 2520 | 176 | 418 | 1 | 0 | 1 (51) | 1 | 0.707 | 2.5 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| atlas | 1332 | 1332 | 57 | 99 | 0 | 0 | 1 (96) | 46 | 0.007 | 2.0 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| kalshi | 1472 | 1472 | 179 | 439 | 0 | 0 | 2 (125) | 117 | 0.229 | 2.5 | 0 | no | ok +age (sw) |
| tyche | 2192 | 11240 | 455 | 1386 | 0 | 0 | 8 (3341) | 6881 | 0.025 | 11.9 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| jarvis | 1664 | 1664 | 1569 | 2750 | 18 | 49 | 58 (2012) | 5908 | 0.052 | 19.0 | 0 | no | ok +age (sw) |
| gate | 2204 | 3104 | 134 | 279 | 0 | 0 | 4 (77) | 66 | 0.0 | 2.3 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |
| hub | 2068 | 2780 | 116 | 247 | 0 | 0 | 0 (0) | 0 | 0.041 | 2.3 | 0 | no | error Page.reload: net::ERR_INTERNET_DISCONNECTED (sw) |

KB first open = bytes over the wire (gzip) in the first 6 s after load; JS KB = JavaScript the phone parses (unzipped). Long tasks:
count over 50 ms (the longest). TBT = their time over 50 ms, summed.

## Why (the causes, in order of what they cost)

1. **Offline:** the root worker skips every app folder (`OTHER_APPS` in sw.js): patch in LEAD_WIRES.md 1.
2. **Layout shift:** (a) the shared kit adds the header's back button + app bar ~2.9 s in (`agora-ui.js`, +0.06 on every Agora app), then
   the breadcrumbs (`gate-nav.js`); (b) each app fills its cards with data without reserving their height (0.3-0.9: agency, dionysus,
   demeter, kronos, chrysos, inbox, clio, board, nq). The shift sources per app are in baseline.json ("shifts").
3. **three.js on text apps:** a decorative 3D header (ledgerscene.js, helios sun.js, nq nqscene.js, aegis, chrysos, mercury, oikos,
   compass, kronos, tyche) pulls three.js + textures + an HDR on open: +163-450 KB and the 0.6-1.4 s parse long tasks.
4. **Heavy data on open:** odeon/trades.json (128 KB gz) for journal, kronos, compass, Jarvis (twice); fates/fates.json 171 KB gz.
5. **Big pages:** Jarvis 1.6 MB first open, 58 long tasks up to 2.0 s, 19 MB heap; Zenith 2.1 MB of JS parsed (main.js 423 KB).
6. **Shared kit on every app:** sfx.js (103 KB, parser-loaded by 21 pages although olympus.js loads it on the first sound) and themes.js
   (74 KB, render-blocking on 24 pages).

Ranked fixes per team: ASKS.md. Assets (images / fonts / vendor) are already in good shape: textures are lossy WebP whose bytes are
mostly the AO alpha (a further cut is visible: not done), fonts are subset woff2 of ~9 KB, icons load only from the manifests.
