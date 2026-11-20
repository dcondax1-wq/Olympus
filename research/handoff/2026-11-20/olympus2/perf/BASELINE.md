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

## After (20:44 UTC, same sweep, day-quality = pc + dogfood)

Offline: 3 of 32 -> **32 of 32** open offline after one visit.

| app | largest paint ms | longest task ms | CLS | KB first open | offline |
|---|---|---|---|---|---|
| zenith | 1820 -> 1812 | 115 -> 91 | 0.28 -> 0.267 | 812.6 -> 825.3 | ok -> ok |
| fates | 9460 -> 8752 | 1832 -> 1843 | 0.073 -> 0.024 | 579.7 -> 443.3 | no -> ok |
| cities | 1656 -> 1664 | 4114 -> 2199 | 0.006 -> 0.006 | 493.7 -> 507.3 | no -> ok |
| journal | 4368 -> 4280 | 112 -> 84 | 0.196 -> 0.0 | 345.6 -> 248.2 | no -> ok |
| ledger | 5320 -> 5508 | 1342 -> 68 | 0.097 -> 0.002 | 492.2 -> 291.3 | no -> ok |
| inbox | 3884 -> 3848 | 63 -> 0 | 0.713 -> 0.36 | 209.2 -> 220.5 | no -> ok |
| settings | 3196 -> 3988 | 234 -> 72 | 0.06 -> 0.003 | 212.7 -> 228.4 | no -> ok |
| planner | 5416 -> 5764 | 119 -> 79 | 0.291 -> 0.004 | 259.9 -> 287.7 | no -> ok |
| demeter | 4188 -> 4212 | 97 -> 0 | 0.849 -> 0.002 | 213.7 -> 241.4 | no -> ok |
| hera | 4056 -> 4104 | 73 -> 52 | 0.244 -> 0.0 | 216.4 -> 245.8 | no -> ok |
| dionysus | 2648 -> 4528 | 135 -> 57 | 0.898 -> 0.0 | 195.2 -> 207.5 | no -> ok |
| pnyx | 2716 -> 4104 | 115 -> 0 | 0.209 -> 0.003 | 227.8 -> 243.7 | no -> ok |
| mercury | 4056 -> 4120 | 492 -> 274 | 0.09 -> 0.002 | 373.3 -> 400.7 | no -> ok |
| chrysos | 4264 -> 4160 | 323 -> 75 | 0.756 -> 0.002 | 464.1 -> 248.9 | no -> ok |
| oikos | 6332 -> 4152 | 508 -> 58 | 0.202 -> 0.002 | 387.6 -> 249.2 | no -> ok |
| aegis | 4480 -> 4548 | 374 -> 63 | 0.362 -> 0.002 | 489.5 -> 273.6 | no -> ok |
| kronos | 5848 -> 7560 | 1438 -> 1294 | 0.83 -> 0.0 | 646.6 -> 552.7 | no -> ok |
| compass | 7892 -> 4720 | 344 -> 53 | 0.457 -> 0.0 | 589.3 -> 254.8 | no -> ok |
| helios | 4888 -> 4864 | 229 -> 0 | 0.273 -> 0.002 | 511.4 -> 293.4 | no -> ok |
| nq | 6484 -> 5352 | 803 -> 193 | 0.58 -> 0.021 | 946.8 -> 400.3 | no -> ok |
| agency | 3852 -> 3996 | 104 -> 57 | 0.948 -> 0.004 | 184.3 -> 204.5 | no -> ok |
| business | 3056 -> 5816 | 112 -> 141 | 0.101 -> 0.002 | 277.7 -> 307.7 | no -> ok |
| trading | 5796 -> 4560 | 290 -> 130 | 0.032 -> 0.001 | 344.2 -> 358.3 | no -> ok |
| board | 2596 -> 2996 | 66 -> 81 | 0.66 -> 0.16 | 141.2 -> 147.4 | no -> ok |
| widget | 1316 -> 1252 | 94 -> 0 | 0.0 -> 0.0 | 14.7 -> 17.0 | no -> ok |
| clio | 2520 -> 4432 | 51 -> 50 | 0.707 -> 0.002 | 175.5 -> 187.8 | no -> ok |
| atlas | 1332 -> 1596 | 96 -> 99 | 0.007 -> 0.0 | 56.9 -> 95.2 | no -> ok |
| kalshi | 1472 -> 2776 | 125 -> 99 | 0.229 -> 0.093 | 179.1 -> 196.0 | ok -> ok |
| tyche | 11240 -> 11604 | 3341 -> 3725 | 0.025 -> 0.038 | 454.8 -> 462.7 | no -> ok |
| jarvis | 1664 -> 1680 | 2012 -> 954 | 0.052 -> 0.016 | 1568.9 -> 1287.7 | ok -> ok |
| gate | 3104 -> 4088 | 77 -> 75 | 0.0 -> 0.027 | 134.0 -> 168.9 | no -> ok |
| hub | 2780 -> 2828 | 0 -> 0 | 0.041 -> 0.0 | 115.7 -> 120.7 | no -> ok |

Budgets lowered in tools/perf_budgets.json (new value +15%, never under the default): zenith.cls 0.32 -> 0.307, fates.fcp_ms 3340 -> 3300, fates.lcp_ms 10880 -> 10060, fates.kb 670 -> 510, fates.heap_mb 17.6 -> 13.3, cities.lt_max 4740 -> 2530, cities.tbt 9250 -> 5480, cities.heap_mb 16.6 -> 15.5, journal.lcp_ms 5030 -> 4920, journal.cls 0.23 -> default, ledger.fcp_ms 3160 -> 3120, ledger.js_kb 1640 -> default, ledger.lt_max 1550 -> default, ledger.tbt 3920 -> default, inbox.cls 0.82 -> 0.414, settings.fcp_ms 3280 -> 3150, settings.lt_max 270 -> default, planner.cls 0.33 -> default, demeter.cls 0.98 -> default, hera.cls 0.28 -> default, dionysus.cls 1.03 -> default, pnyx.cls 0.24 -> default, mercury.lt_max 570 -> 320, mercury.tbt 1150 -> 360, chrysos.lcp_ms 4910 -> 4780, chrysos.js_kb 1570 -> default, chrysos.lt_max 380 -> default, chrysos.tbt 540 -> default, chrysos.cls 0.87 -> default, oikos.lcp_ms 7290 -> 4770, oikos.js_kb 1320 -> default, oikos.lt_max 590 -> default, oikos.tbt 760 -> default, oikos.cls 0.23 -> default, aegis.js_kb 1680 -> default, aegis.lt_max 440 -> default, aegis.tbt 470 -> default, aegis.cls 0.42 -> default, kronos.kb 750 -> 640, kronos.lt_max 1660 -> 1490, kronos.tbt 4830 -> 3880, kronos.cls 0.95 -> default, compass.lcp_ms 9080 -> 5430, compass.kb 680 -> default, compass.js_kb 1580 -> default, compass.lt_max 400 -> default, compass.cls 0.53 -> default, helios.lcp_ms 5630 -> 5590, helios.kb 590 -> default, helios.js_kb 1710 -> default, helios.lt_max 270 -> default, helios.cls 0.31 -> default, nq.lcp_ms 7460 -> 6150, nq.kb 1090 -> default, nq.js_kb 2030 -> 1090, nq.lt_max 930 -> 220, nq.tbt 2300 -> 600, nq.cls 0.67 -> default, nq.heap_mb 13.9 -> default, agency.cls 1.09 -> default, business.fcp_ms 3150 -> 3080, business.cls 0.12 -> default, trading.lcp_ms 6670 -> 5240, trading.lt_max 340 -> default, trading.tbt 570 -> default, board.cls 0.76 -> 0.184, clio.cls 0.81 -> default, kalshi.cls 0.26 -> 0.107, jarvis.kb 1810 -> 1480, jarvis.lt_max 2320 -> 1100, jarvis.tbt 6800 -> 3200, jarvis.heap_mb 21.8 -> 18.3

What moved (vs the morning baseline, same line, same machine):
- **Offline: 3 -> 32 of 32** open after one visit (sw-offline landed).
- **Layout jumps fixed almost everywhere:** agency, dionysus, demeter, kronos, chrysos, clio, board, nq, compass, oikos ... from 0.2-0.95 to ~0.00; still over 0.1: zenith 0.27 (the late Home cards, DESIGN slots), inbox 0.36.
- **Faster main content:** compass 7.9 -> 4.7 s, oikos 6.3 -> 4.2 s, trading 5.8 -> 4.6 s, nq 6.5 -> 5.4 s, fates 9.5 -> 8.8 s; longest task nq 803 -> 193 ms, compass 344 -> 53 ms, oikos 508 -> 58 ms.
- **Later "largest paint" where the jump was fixed** (business 3.1 -> 5.8 s, clio 2.5 -> 4.4, dionysus 2.6 -> 4.5, pnyx 2.7 -> 4.1): first paint is the same or earlier; the old largest element was the skeleton, which now holds its place, so the largest element is the real content drawn after the data. Next fix: draw from the cached copy first.
- Still over budget (10): kronos 7.6 s, business 5.8, dionysus 4.5, clio 4.4, pnyx 4.1, gate 4.1 (largest paint); board 2.8 s / nq 2.6 s first paint; cities 507 KB; jarvis 1 error = CoinGecko 429 (an outside price feed rate-limiting the test machine, not our code).
