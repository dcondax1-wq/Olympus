# 6 arenas Home (day-manual, 2026-11-20)

Owner 17:00 ET: "organize the dashboard, I want like 6 arenas, that's it, then a separate area for the smaller stuff."

| what | result |
|---|---|
| Home (gate/) | search, then 6 big tiles in order: Cities, Kalshi, NQ Bot, Jarvis, Websites, Business (Planner link at Business's top corner). All 6 fit the first 390x844 screen. |
| Live line per tile | NQ: today's $ + tightest drawdown left. Kalshi: next K8 window. Websites: call-backs due, else "call 5 leads at lunch". Business: "Payout: $X of $2,100". Jarvis: first line of the brief. Cities: tagline. (gate/arenas.js, text only) |
| Everything else | one area under the arenas: Planner, Trading, Ledger, Board, Hera, then the rest A to Z; retired apps hidden. Search, pins, A to Z unchanged. Old app grid / doors dock / hubs list hidden (kept in the page for search). Right now card sits below. |
| Launcher (both copies, byte-identical) | an "Arenas" row of the 6 first, then a "More" heading over the four doors (arena apps not repeated). |
| Doors page / doors.js (both copies) | "Your 6 arenas" start row = the same 6; doors.js gets ARENAS + arena(id). The 4 doors stay: World districts, Atlas and the Doors page are built on them. |
| Look | OLYMPUS NIGHT glass + tilt on the tiles (navfx.css/js). No sideways scroll, no console errors, CLS 0. |
| Tests | gate_page, apps_list, nav_pages pins updated; new nav_pages check "Home: exactly 6 arenas in this order, plus one Everything else area" (static + 390x844 browser). test_warp a./b. fail the same with my changes stashed (from the merged Zenith page): not this branch. |

Shots: `home-top-*`, `home-arenas-*`, `home-else-*` (dark + light, 390x844 @2x) in this folder.
