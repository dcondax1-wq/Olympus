# DATA TRUTH pages: perf (phone 390 px, CPU x4, Fast 3G, cold; day-quality's tools/perf_sweep.py)
| page | KB first open | first paint | largest paint | blocking time | layout shift (CLS) |
|---|---|---|---|---|---|
| nq | 947 -> **340** | 2.81 -> 2.28 s | 7.00 -> **5.40 s** | 2391 -> **576 ms** | 0.523 -> **0.081** |
| trading | 345 | 2.62 -> 2.90 s | 5.59 -> **4.74 s** | 280 -> 505 ms | 0.032 |
| board | 144 | 2.78 s | 3.02 -> 4.66 s (*) | 36 -> 31 ms | 0.66 -> **0.038** |

What changed:
- **nq**
  - The 3D columns (three.js 163 KB + a 165 KB texture + a 128 KB HDR file) load only when the card is within a screen (`data-near="#sceneCard"`).
    On a phone they use the kit's low tier (LITE texture, no HDR).
  - The chart box keeps its height when the chart has no data (it used to shrink late: 0.38).
  - The accounts / GO / day cards, the chart's "As of" line and the chips keep their space from the first frame.
  - The page head starts the data files and the PC's chart post at once (`window.NQ_EARLY`), instead of after nq.js -> nqchart.js -> status_feed.json.
- **trading**
  - The data files start from the page head (`window.TR_EARLY`).
  - `trading.js` is preloaded and runs `async`, no longer behind every deferred kit script; the deep-dive charts redraw on `load`.
- **board**
  - The accounts area keeps its filled height until the first draw, so nothing visible moves.
  - The site's copy is drawn at once, then the PC post over it in place.
  - The edge chip keeps its line.
- **test_nq_chart**: the empty-chart check now expects the box to keep its 300-441 px height (it said "a small box"). A late shrink was the
  0.38 layout shift. All other checks unchanged: 44/44.

Left (not in my slice):
- First paint 2.3-2.9 s is the shared kit's render-blocking CSS + sync scripts (design team).
- The remaining NQ shift 0.059 is the kit's app bar inserted after load (perf ask DESIGN 1).
- (*) Board's largest paint here is the "PC SILENT" banner, because the local test cannot reach the PC feed. On the live site the accounts
  draw from the site copy at once.

# A11Y (day-a11y's tools/a11y_sweep.py --quick, 6 screens each)
| page | before | after |
|---|---|---|
| trading | 77 | **92** |
| nq | 85 | **92** |
| board | 85 | **96** |
Fixed:
- The heat map's "few trades" contrast: a token, not opacity .55 (was 3.95:1 in daylight).
- `role="listitem"` removed from the account `<article>`s (the strip is a labelled group).
- The stats table's empty first header now reads "Measure" to VoiceOver.
- Board's live feed: the live region moved to a wrapper, so the list keeps its role.
- Body text at 15 px across nq / trading / board / payready / nqdesk / nqdeep, and the kit's 13 px card notes overridden on my pages.

Kept small on purpose:
- NQ's status / source lines (13 px) and the chart's "As of" line: they sit above the live chart, which must stay on the first 390 x 844 screen
  (test_nq_chart 44/44).
- Short labels: ticks, chips, table cells (13 px).

Left for others: the shared edge chip (`edge_chip.js`, 13.6 px) and the kit's pill / note sizes (design team).
