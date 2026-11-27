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

1. **Load the new chart.** Done by the helper in `nq/index.html`: the page now loads `nqchartfeed.js?v=1`, which is small and eager, instead of `nqchart.js`. The feed then loads `nqchart.js?v=d3` (the view) when the chart card is within 400 px of the screen, or when the page goes idle after load, whichever comes first. The view imports `lcmodel.js` and loads `chart.css?v=3`. If `bump_versions` rewrites these query strings, keep the `VIEW` constant in `nqchartfeed.js` in step with `nqchart.js`'s version.
2. **Precache the new files.** In `sw.js`, add `nq/nqchartfeed.js` and `nq/lcmodel.js` to the precache list next to `nq/nqbars.js` and `nq/nqchart.js`, and bump the cache name.
3. **Run the new suite.** In `tests/run_area.py`, add `tests.test_livechart` to the NQ / chart area next to `test_nq_chart_pro`. It runs in about 2 minutes and needs the browser.
4. **Perf budget.** The NQ page's eager JS is now **582 KB**, down from 637 KB, against the 640 KB budget, with no budget change. The 50 KB view (`nqchart.js`) and the 10 KB `lcmodel.js` load lazily. `nq.js`'s desk cards still get `window.NQCHART.S.post` / `S.model` and the `nq-bars` event straight away from the feed.
5. **Footprint strip (from day-ofroom2 @ b229a648).** `nqchart.js` loads the strip lazily: `ofstrip.js?v=1` and `ofstrip.css?v=1` are fetched only when today's `nq/of_strip.json` has bars, and the strip mounts under the ticker. Tapping a bar on the strip moves the chart's crosshair and readout to that bar. Tapping a candle, or moving the replay scrubber, selects the footprint bar at the same time (matched by ET time). This needs the day-ofroom2 files landed first (`ofstrip.js`, `ofstrip.css`, `build_of_room.py` writing `of_strip.json`). Before they land, the fetch gets a 404 and nothing is drawn. The PC sends `of_strip.json` nightly, so during the session it is the last recorded day: the strip shows it labelled "Footprint · Nov 26 (last recorded day; …)", and a tap on it selects within the strip only (it never moves today's chart). On the private link the view also polls `GET /api/live/footprint` every 60 s (branch `day-livefp`, the PC side). When that returns today's bars, the strip becomes "Footprint · today (live from your PC)" and is synced to today's candles. Before that endpoint exists, the poll gets a 404 and nothing changes. Precache `ofstrip.js` and `ofstrip.css` in `sw.js` if you want the strip offline.

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

- `python -X utf8 -m tests.test_livechart`: **48/48** (including the strip hook and its time sync, an older day's label, the live footprint on the private link, and the lazy-load split; the strip is tested with a stub module) (static + node + Chromium 390/1440, stale feed, private link).
- `tests.test_nq_chart_pro`: **28/28**.
- `tests.test_nq_chart`: **47/48**. The one failure, "wholly on the first screen", is the same as on `pc` before this change.
- smoke: **11/11** green.
- `tests.test_nq_page`: **69/71**, the same 2 failures as on `pc` without this change (DEMO banner, veil tap).
- `tests.test_nq_chart`: its static check now expects `nqchartfeed.js` in the page and reads the feed and the view together.
- Screenshots (local, gitignored): `research/handoff/2026-11-27/livechart/shots/` (390 public, 1440, 390 private).
