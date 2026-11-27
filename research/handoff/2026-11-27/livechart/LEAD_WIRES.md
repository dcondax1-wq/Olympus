# day-livechart: what the lead wires (2026-11-27)

The owner asked for "a live chart on the NQ dashboard with exactly what's happening, be creative".

The helper changed only its own chart files:
- `nq/nqchart.js`
- `nq/chart.css` (v3, loaded by `nqchart.js` itself)
- new `nq/lcmodel.js`
- new `tests/test_livechart.py`

**No new PC field was needed**, so there is no `day-livechart-feed` branch. Everything comes from what the PC already sends:
- the lite post: `pc.glance.bots` + ext `glog`
- `/api/live/state` on the private link (`bars_tail`, `state.price`, `last_poll`)
- `nq/brief.json` (`early_close`)
- `nq/of_room.json`

## Wires (lead only)

1. **Load the new chart.** In `tools/web_public/nq/index.html`, bump `nqchart.js?v=d2` to `?v=d3`, or let `bump_versions --apply` do it.
2. **Precache the new files.** In `sw.js`, add `nq/lcmodel.js` to the precache list next to `nq/nqbars.js` and `nq/nqchart.js`, and bump the cache name. `nqchart.js` already loads `chart.css?v=3` itself.
3. **Run the new suite.** In `tests/run_area.py`, add `tests.test_livechart` to the NQ / chart area next to `test_nq_chart_pro`. It runs in about 2 minutes and needs the browser.
4. **Perf budget.** The NQ page's eager JS is now 637 KB against a 640 KB budget (`tools/perf_sweep.py --static --check`: green). I made room by cutting comment-only lines out of `nqchart.js`. Consider raising the NQ budget to about 660 KB anyway.
5. **Footprint strip (from day-ofroom2 @ b229a648).** `nqchart.js` loads the strip lazily: `ofstrip.js?v=1` and `ofstrip.css?v=1` are fetched only when today's `nq/of_strip.json` has bars, and the strip mounts under the ticker. Tapping a bar on the strip moves the chart's crosshair and readout to that bar. This needs the day-ofroom2 files landed first (`ofstrip.js`, `ofstrip.css`, `build_of_room.py` writing `of_strip.json`). Before they land, the fetch gets a 404 and nothing is drawn. Precache `ofstrip.js` and `ofstrip.css` in `sw.js` if you want the strip offline.

## What it does

- **Above the chart:**
  - An honest stamp: "LIVE from your PC · HH:MM ET" on the private link when the last poll is ≤ 20 s old; otherwise "As of HH:MM ET (… ago) · the public feed", in gold when fresh and rose when older than 20 min.
  - Zlarior's stage as a 10-step strip (e.g. Displacement 4/10).
  - Chips for ATLAS armed SHORT/LONG, "Halt 13:15 ET today" from `brief.json` (today only), and an open trade with its risk $ and target $.
- **On the chart:**
  - The bots' own levels in gold; order-flow levels in violet.
  - A SWEPT mark plus a one-time gold flash when a level gets swept.
  - ABSORBED rings from `of_room.json`, today only (yesterday's replay draws nothing).
  - ATLAS's 5m EMA 50, coloured by its armed side.
  - Stop and target lines with −$risk / +$target. If the post has no lines yet, they are drawn from the glance.
  - A dashed gold HALT line, placed by bar spacing when it is still ahead.
  - Session boxes (unchanged).
- **Tap a mark → why:** a plain-words card with a 44 px close.
- **Under the chart:**
  - "Next trade if (Zlarior LONG): …"
  - The bots' last thoughts, newest first, each with time and emoji.
  - A replay scrubber for today, with Replay ▶ / Pause and Live buttons.
- **Private link** (`/site/…` or `?priv=1`):
  - It polls `GET /api/live/state` every 3 s and uses the bot's own 5m bars.
  - The forming bar opens at the last close, and its high/low come only from prices actually seen.
  - A new price glides the last close (450 ms) and pulses the dot.
  - After 3 failed polls it falls back to the public feed and says so.
- **Public site:** glance/glog every 30 s, bars every 2 min, `brief`/`of_room` every 5 min.
- **Reduced motion:** no flash, no glide, no pulses.

## Tests

- `python -X utf8 -m tests.test_livechart`: **44/44** (including the strip hook, tested with a stub module) (static + node + Chromium 390/1440, stale feed, private link).
- `tests.test_nq_chart_pro`: **28/28**.
- `tests.test_nq_chart`: **47/48**. The one failure, "wholly on the first screen", is the same as on `pc` before this change.
- smoke: green except `perf_sweep`, which was over by 1.9 KB before the trim and is 0 over after it.
- Screenshots (local, gitignored): `research/handoff/2026-11-27/livechart/shots/` (390 public, 1440, 390 private).
