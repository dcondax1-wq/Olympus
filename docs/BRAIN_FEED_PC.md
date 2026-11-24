# Brain feed on the PC report (ext block `bf`)

day-brain-feed 2026-11-24. Producer: `engine/brain_feed.py` (READ-ONLY: never trades, sizes, arms or writes a file).
Carrier: `tools/pc_report.py` -> `full()` adds `out["bf"]`; `split()` puts it in an ext post (kind `le-live-ext`), and
`tools/pc_feed.merge` lays it back at the top level of the merged status (`status["bf"]`). Reader: the Brain app (day-brain-app).
Tests: `python -X utf8 -m tests.test_brain_feed`.

## Where the data comes from (nothing new is computed by the bot)
| bot | source in the heartbeat / on disk |
|---|---|
| `lit` (Zlarior) | `hb.brain` = `engine/brain.compact`: stages, setups + plans, log, levels (taken / untaken), guards.vix, atr |
| `atlas` | `hb.second` = `engine/second.compact`: route.account_b.keys, per strategy state / brain plan / checks / log / levels |
| `blitz` (hidden, PAPER) | `hb.blitz` = `engine/blitz.compact`: state text, band checks, signals, open paper trade, today |
| `of` (order flow, research) | `data/tickrec.json`, `data/orderflow_auto.json`, `data/orderflow_note.json`, file names in `data/ticks/` (no tickrec import, no parquet read) |
| `market` | today's NQ 5m bars from the chart files (`pc_report.bar_files` / `read_bar_tail` / `chart_bars`, read in `gather()` as `snap["bf_bars"]`, never posted) + LIT's VIX band |

## Shape
```json
{"v": 1, "t": 1791963000, "trimmed": true,
 "market": {"phase": "expanding|retracing|ranging", "today_range_pts": 186.25, "where_in_range_pct": 50,
            "regime": "normal (VIX 15.3)", "range_vs_move_pct": 63},
 "bots": {
  "lit":   {"think": ["03:30 short limit 30,783.75 armed, stop 30,829.5", "03:30 VIX 15.3 -> day move 296 pts -> target 6.3R", "..."],
            "next": {"setup": "SHORT sweep + shift of Frankfurt high", "steps": [{"name": "sweep", "done": true}, "..."],
                     "waiting_for": "SHORT limit 30,783.75 was tapped ...", "dist_pts": 13.75, "window": "until 03:55 ET",
                     "limit": 30783.75, "stop": 30829.5, "target": 30495.31},
            "levels": [{"kind": "stop", "price": 30829.5, "label": "stop"}, {"kind": "sweep", "price": 30804.75, "label": "Frankfurt high 03:00"}]},
  "atlas": {"think": [], "next": {}, "levels": []},
  "blitz": {"think": [], "next": {}, "levels": [], "paper": true},
  "of":    {"think": [], "next": {}, "levels": [], "paper": true}}}
```
- Empty / null fields are left out (`_clean`). A bot with nothing to show is absent. A bot that failed is `{"err": "Type: msg"}`.
- `think`: newest first, up to 8 lines (`HH:MM words`, ET, <= 64 chars). LIT: the "now" line (armed limit / what the forming leg waits for /
  the stage), a VIX line, then the Brain's log in short words. ATLAS: each lobe's state, then the lobes' log. BLITZ: state, signals, closed paper trades.
- `next.steps`: `[{name, done}]`; under a tight budget it becomes the string `"6/10"` (done / all). LIT = the Brain's 10 stages, ATLAS = the lobe's checks.
- `next` with nothing armed (LIT): no `limit/stop/target`; done for the day: `setup` = `"done for today"`, no `dist_pts`.
- `dist_pts`: |price - limit| while armed (LIT, ATLAS entry), the CISD distance of a forming leg (LIT), the nearer band side (BLITZ).
- `levels` (<= 12 LIT, 8 ATLAS, 4 BLITZ) kinds: `stop`, `target`, `sweep` (taken today, label + time), `expansion` (LIT: VIX band up / down;
  BLITZ: the next check's band), `retrace` (50% of today's range), `fvg` (a gap level), `liq` (an untaken liquidity pool: an
  extra kind beyond the requested list, the app can draw it like a plain line).
- The same `atr` and `ax` [limit, stop, target] ride the glance's LIT row (`pc.glance.bots[lit]`, lead wire 4, `engine/brain_glance._lit_ax`).

## Market rules (measured, fixed; `engine/brain_feed.market`)
- Today = the 5m bars since 18:00 ET (CME day). Fewer than 6 bars: only `regime`.
- `today_range_pts` = day high - day low. `where_in_range_pct` = (price - low) / range x 100 (price = LIT's price, else the last close).
- `phase`, first match wins:
  1. **expanding**: the day's high or low was made in the last 6 bars (30 min) AND |close of the last bar - open of the 6th last| >= 1.5 x the day's mean 5m bar range.
  2. **retracing**: price is back >= 30% of today's range from the extreme made last (from the high if the high came after the low, else from the low).
  3. **ranging**: anything else.
- `regime` from VIX (LIT's guards.vix): < 15 calm, < 20 normal, < 28 high vol, else extreme, with the value. `range_vs_move_pct` = today's range / the VIX day move.

## Size and the feed limits
- ntfy turns a post over 4,096 bytes into a file: `MAX_STATUS_BYTES` 3,800 a post, at most 2 ext posts a run (`EXT_PARTS`).
- `bf` <= 2,000 bytes (`brain_feed.MAX_BYTES`; fit order: lesser bots' think / levels, LIT's, steps -> "n/m", texts 44 / 32, then whole bots of / blitz / atlas, LIT never).
- In `split()` it is in `EXT_LAST` ahead of `glog`: it only takes the room every other ext block left. Too big: cut to 1,400, then 900 bytes, then left out
  (the ext post's `cut` lists `bf`). The core post is never touched.
- `ext_hash` ignores `bf` (like `glance` / `glog`): a new thought is not news, so it never adds an ntfy post (the per-IP day cap); it refreshes with the ext.

## Safety
- Every part in its own try/except: a broken bot = `{"err"}` for that bot; a crash in `build` / the import = no `bf`, the report as before (test f4).
- The bars read in `gather()` is wrapped; on failure `bf_bars` is None (market = regime only).
- No import of ninjatrader / live / tradovate / account_b; no file is written; the heartbeat dict is not changed (test d1).
