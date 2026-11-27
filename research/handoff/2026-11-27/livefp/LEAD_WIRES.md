# day-livefp: what the lead wires (2026-11-27, red team #44)

This branch serves **today's** NQ footprint per 5-minute bar on the private link, so the live chart's heat strip updates during the session.

| File | Change |
|---|---|
| `engine/livefp.py` | New. |
| `tests/test_livefp.py` | New, 22/22. |
| `server.py` | One route, next to `/api/live/state`, 11 lines. Also as a standalone patch: `server_route.patch` in this folder. |

## Wires

1. **`server.py`.** If `server.py` is lead-only, apply `server_route.patch` yourself; it is the same 11 lines as on the branch. The route answers only the PC itself and the owner's Tailscale link (`live_site.private_why`); everything else gets 403. It never returns a 500.
2. **`tests/run_area.py`.** Add `livefp` to the `"pc"` area so `--changed` picks the suite up.
3. **Landing timing.** Land it with or after `day-livechart`. Since 85dee2c3, the chart already polls `GET /api/live/footprint` every 60 s on the private link, and treats a 404 as "nothing yet".
4. **Nothing to set up on the PC.** The endpoint reads the tick recorder's own file, `Documents\NinjaTrader 8\le_ticks\NQ_<ET day>.csv`, and writes only `data/livefp/fp.json` and `data/livefp/state.json`. Both are small and rebuilt daily. If the tick recorder is off, the strip says so in plain words.

## Cost on the trading PC

- The route reads at most about 46 KB from `data/livefp/fp.json`.
- At most one child process (`python -m engine.livefp build`) runs at a time, at BELOW_NORMAL priority with no window, and only when the file is more than 20 s old **and** someone is polling.
- The child reads only the new bytes of today's tick file (at most 6 MB a run), using plain Python (no pandas or numpy).
- Measured: a full 20 MB day catches up in about 1.0 s of CPU over 4 runs. Each 20 s increment of about 1,000 trades takes about 0.06 s.
- It never runs inside the trading process.
