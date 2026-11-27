# day-strats: what the lead wires (2026-11-27 overnight)

The owner asked: "complete charts of each strategy: Zlarior, ATLAS, BLITZ and order flow; I want to see everything". Order flow is named **POSEIDON** in these pages.

## What is new

### The page: `nq/strat.html?s=lit|atlas|blitz|poseidon`

Files: `strat.html`, `strat.js`, `strat.css`. Each strategy gets one room with these parts:

1. **Live chart.** This is the same `nqchart.js` as the main NQ chart. The page sets `window.NQ_STRAT`, which limits the chart to that strategy:
   - **Chips:** only its accounts (e.g. "All Zlarior", Z50, Z25 #2).
   - **Levels and marks:** only its own. Zlarior shows its stage strip and levels; ATLAS shows its EMA 50 and armed side; POSEIDON shows the order-flow levels, ABSORBED rings and the footprint strip; BLITZ shows nothing extra.
   - **Bot thoughts and "next trigger":** only that bot's.
   - **Open trade lines:** only its own trade, with $ risk / $ target.
   - **Halt line:** stays in every room, because it stops every bot.
2. **Today's signals**, including skipped ones with the reason:
   - Zlarior / ATLAS: from the PC's glance (stage, armed setups with the trigger, wait, why) plus the glog lines.
   - POSEIDON: `of_room.json` rows (taken or skipped, with why) plus the PC's `ofp`.
   - BLITZ: an honest line that it is hidden and paper-only, plus its paper summary.
3. **Every trade**, as tappable dots on the running total:
   - Tags: REAL (gold), PAPER (violet), BACKTEST (grey), SKIPPED (POSEIDON).
   - Filters: All / Real / Paper / Backtest, and 2026 / 2021-25 / All years.
   - Tapping a dot opens a trade card: entry, stop, target, exit (or "not recorded"), $, R, exit reason, why. Older / Newer buttons step through trades.
   - A "Newest trades" list sits under the chart.
4. **Equity:** the backtest line plus one line per real account (each starting at $0, as MFFU shows it) plus paper. Views: 2026 / All years / Since live.
5. **The numbers:** 8 tiles (trades/week, win %, PF, avg R, $/month, max DD, best, worst) for 2026 H1, 2026 Jul-<data end>, 2021-25 and Live (real). Every strategy uses the same math, and each period shows the research file's own numbers beside it.
6. **Brain:** `#brainMount`, filled by the brains helper's `brainview.js`. The agreed contract is `mount(el, { s, getState: () => ({ lite, home: null, bars }) })` → `{ update, setStrategy, destroy }`. It is lazily imported when the card nears the screen; until `brainview.js` lands, the card says so in plain words.

BLITZ and POSEIDON show a gold **PAPER** badge and are described as PAPER everywhere.

### The NQ home switcher

`nq/index.html` gets `#stratNav`: 4 plain links (no script) just above the live chart, styled by `nq/stratnav.css`.

### The data builder (new)

`tools/build_strats.py` writes `tools/web_public/nq/strats/{lit,atlas,blitz,poseidon}.json` (16-255 KB each; the browser fetches only the open room's file). It reads only existing files:

| Strategy | Backtest / paper source | Live / paper source |
|---|---|---|
| Zlarior | `research/lab/backtest_live.json` | `trading/trades.json` |
| ATLAS | `research/anatomy/trades_atlas.json`, with prices joined from `research/second/*_best.json` (1288 of 1288 joined) | `trading/trades.json` |
| BLITZ | `research/runs/blitz_2026_backtest.json` (no prices in the source, so they show as "not recorded") | `research/batch5/blitz_paper.json` (a summary only; the PC's own paper ledger is not in the cloud) |
| POSEIDON | `research/orderflow/real_verdict.json` + `exec_results.json` | — |

The research reference numbers come from `pillars/pillars-data.json`.

### Small edits to shared chart files (mine)

- `nqbars.js`: an account filter `bot:LIT`; each account chip carries its bot.
- `nqchart.js`: `stratChips` / `stratLive`; the footprint strip shows only on the home or in POSEIDON.
- `nqchartfeed.js`: reads `window.NQ_STRAT`.
- The NQ home behaves exactly as before; `test_livechart` 48/48 and `test_nq_chart_pro` 28/28 confirm it.

## Wires (lead only)

1. **Site build:** run `python -X utf8 tools/build_strats.py` next to `tools/trading_export.py`. `--check` exits 1 when a room file is stale; it is fresh as committed.
2. **`sw.js`:**
   - Precache `nq/strat.html`, `nq/strat.js`, `nq/strat.css`, `nq/stratnav.css`, and optionally `nq/strats/*.json`.
   - Bump the cache name.
   - Also bump `nqchart.js` / `nqchartfeed.js` / `nqbars.js` if `bump_versions` does not.
3. **`tests/run_area.py`:** add `strats` (`tests/test_strats.py`, about 3 minutes, uses the browser) to the `nq` area.
4. **The owner's BLITZ rule:**
   - I changed `tests/test_nq_page.py`'s "BLITZ only as its pillar chip" check so it also allows the home's BLITZ room link.
   - The link reads "BLITZ / paper", with no $ and no number, which the test checks.
   - `hidden_bots` still holds BLITZ's live data, so none is shown.
   - If you want the BLITZ tile gone from the home while `hidden_bots` holds it, delete one `<a>` in `#stratNav` and revert that test hunk.
5. **Brain:** land `brainview.js` (session_01EwJ4kSrTyCdh7YYqkVYkfv) with this branch or after it; either order works.
6. **Gaps, said plainly on the page:**
   - The backtests end in mid-October: Zlarior Oct 14, ATLAS Oct 13, BLITZ Oct 16. "2026 Jul–<end>" uses that end date, and there is no Nov backtest until the research is re-run.
   - `trading/trades.json` is built up to Nov 16 (Zlarior) and Nov 18 (ATLAS).

## Tests

| Suite | Result |
|---|---|
| `tests/test_strats.py` | **58/58** (builder, static, Chromium at 390 for all 4 rooms + 1440 for Zlarior, and the home switcher) |
| `test_livechart` | 48/48 |
| `test_nq_chart_pro` | 28/28 |
| `test_nq_chart` | 46/48: the same 2 failures as `fb9a886a` without this branch (chart box on the first screen, Jarvis corner) |
| `test_nq_page` | 69/71: the same 2 failures as `fb9a886a` (DEMO P&L card, veil tap) |
| smoke | 11/11 |
| NQ eager JS | 589 KB of 640 (perf static: 0 over) |

Screenshots are local and gitignored: `research/handoff/2026-11-27/strats/shots/`.
