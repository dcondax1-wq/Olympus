# Money FX speed fix (day-archive, Sat 2026-11-21, QA item)

Probe: `research/handoff/2026-11-20/fx/perf_probe.py` (390x844, 4x CPU slowdown, live data, median of 3; `--slow` = 150 ms + 1.6 Mbit/s).

| Page | LCP before -> after | Blocking time (TBT) before -> after | CLS before -> after | KB in 10 s before -> after |
|---|---|---|---|---|
| Board | 1,352 -> 884 ms | 333 -> 0 ms | 0 -> 0 | 208 -> 374 (the 3D vault now arrives inside the window, after load + idle + on screen) |
| Board, slow network | 3,716 -> 3,508 ms | 0 -> 0 | 0.447 -> 0.410 | 448 -> 503 |
| Ledger | 576 -> 628 ms | 2,036 -> 2,280 ms (its own 3D scene, unchanged) | 0.001 -> 0.012 | 1,202 -> 1,291 |
| Hera | 680 -> 856 ms | 80 -> 81 ms | 0 -> 0 | 536 -> 603 |
| Business (no moneyfx on it) | 712 -> 808 ms | 292 -> 155 ms | 0.029 -> 0.029 | 704 -> 663 |

What changed: `olympus/moneyfx.js` has no static imports any more (truth.js + pc_feed.js load after load + idle; the effects kit + three.js only
when the payout card is on screen); the card keeps a fixed size (`contain: layout`, note min-height, fixed vault / ring boxes); a shorter note;
`olympus/moneyfx.css` defines no `--oly-th-*` slot (olympus_themes f-check: only planner.css left, not ours); Board reserves its PC line,
edge chips and account list space.
Board's remaining CLS (0.41 on a slow network) is its own layout: at about 3 s the "PC SILENT" alert (121 px) and the Decide card (649 px)
appear ABOVE the accounts. Fix options for the lead / Board owner: put Decide under the accounts, or render it from board.json at first paint.
Also on pc (not new): olympus_themes "mind: --st 0px vs 45px" is the archive strip raising Mind's safe-top on purpose (its HUD moves under it).
Tests: board 60/60, ledger 88/88, hera 39/40 (= pc), olympus_themes 250/286 (pc 249/286, same failures minus one fixed), site_checks fine.
