# AGORA audit (2026-11-10)
Tool: `python tools/agora_audit.py [--app id] [--render] [--headers]`; test `tests.test_agora_audit` (static, no browser).
| Area | Before | After |
|---|---|---|
| Hard FAILs (static, CSS/HTML/fonts/theme-color) | 275 | 0 |
| Apps fully clean | 42 / 68 | 64 / 68 (rest: shared files covered by zenith_agora.css / agora_pc.css, lead-wired apps.js tables) |
| Header pattern match (heuristic `--headers`) | n/a | 56 / 65 |
Rendered scan (`--render`, screenshots to research/agora_shots/) was NOT run: machine load 20+.
Left: apps.js / apps-list.js / olympus.js app colours (lead): zenith #9c6b3c, oracle #7fa6bd, datacity #4b7a99, observatory #7fa6bd, tree #7f8a52, argus #4b7a99, nemesis #c9a06a, hephaestus #c9a06a, cities #c9a06a, kalshicity #7f8a52, journal #e08a6b, inbox #7fa6bd, settings #c9a06a, bridge #7f8a52, mind #7f8a52, athena #4b7a99, kalshi #7f8a52, tyche #c9a06a.
Also left: olympus/themes.js optional cool themes; jarvis/zenith-mode.js violet default (test_zenith_mode asserts it); per-app sw.js; headers of atlas, atlascity, bridge, pc, jarvis lack agora.css.
Cache bumps needed: olympus/agora.css, kalshi.css, web_next/index.html + css/agora_pc.css, all edited apps.
