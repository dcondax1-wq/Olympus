# day-ofroom2: LEAD WIRES (the order-flow CONTROL ROOM, nq/orderflow.html)

Files changed (mine): tools/web_public/nq/orderflow.html / .js / .css, tools/build_of_room.py, tests/test_nq_of.py.

1. **Room data**: `python -X utf8 tools/build_of_room.py` (in the hourly pull, after of_ladder / of_realday_verdict) now also writes
   `control` into tools/web_public/nq/of_room.json: ladder (research/evalplan/ladder.json), the honest backtest
   (research/orderflow/monfix/results.json after|first|e5 + later-in-day), the full-year slot, the v5 table, and the lane (only where
   data/of_lane*.json exist = the PC).
2. **Tonight's full-year result**: write `research/orderflow/oos/result.json` with the contract (made, days, first, last, verdict
   pass|fail|weak, line, laneA {n, tpw, mean_R, pf, win_pct, usd_1, max_dd, halves {h1_2026, h2_2026, dec_2025}}, books {first,
   one_at_a_time}, v5 [{family, verdict, n, mean_R, usd_1}]). NO separate public copy is needed: build_of_room carries it into
   nq/of_room.json (control.oos; the v5 rows get their full-year verdict). Re-run build_of_room after the job and publish. Until the
   file exists the card says "Tonight 10:30 PM ET".
3. **The practice lane live**: the PC's status post should carry an ext block `ofl` (the page also accepts `oflane` / `of_lane`):
   `{"on": bool, "account": "Sim102", "cap": 1, "used": int, "day": "YYYY-MM-DD", "trades": [{"t": "HH:MM", "dir": "long"|"short",
   "qty": int, "status": "sending"|"open"|"closed"|"refused", "pnl": $ or null, "why": "plain words"}]}` (<= ~400 bytes; trades: today's
   only, newest 4). tools/build_of_room.lane_block makes exactly this shape from data/of_lane.json + data/of_lane_state.json, so on
   the PC: `snap["ofl"] = build_of_room.lane_block(cfg, state)` (or the lane helper's own builder with the same keys). A refused row's
   "why" containing "day cap" shows "skipped: day cap (1 a day)". Only a fresh post (< 3 h) counts as live.
4. Nav: unchanged (the NQ bottom bar already has "Flow").
5. **Footprint strip** (nq/ofstrip.js + ofstrip.css, data nq/of_strip.json): `tools/build_of_room.py` now also writes
   tools/web_public/nq/of_strip.json (the room's day, else the newest pulled real tick day; RTH 5m bars, < 40 KB) - publish it with
   of_room.json. API for any page (the live chart): `<link rel="stylesheet" href="ofstrip.css?v=1">` + `import { mount } from
   './ofstrip.js?v=1'` (or window.OFSTRIP.mount); `const s = mount(el, data, { height: 230, onSelect: (bar, i) => {} })`;
   `s.update(data)`, `s.select(i)`, `s.destroy()`. Demo: the Footprint card on nq/orderflow.html. Tests: tests/test_ofstrip.py
   (add to run_area nq).
