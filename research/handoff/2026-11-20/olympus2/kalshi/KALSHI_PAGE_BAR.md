# kalshi/ against the Olympus bar (day-kalshi, Olympus 2, 2026-11-20)

Measured at 390 x 844, local copy of tools/web_public (external hosts blocked).

| Bar | Before (this morning) | After |
|---|---|---|
| 1. Useful in 5 s | Under the title: "Not connected yet" (the OLD crypto bot's feed); first box = "PAUSED ... rewards ... K1" | Title line = "K8 gold & silver bot · PAPER / LIVE · $55, $2.50 a bet"; first screen = K8 live day (countdown to the next live bet, what the bot will do, last price vs fair, $ left before each stop). Then K8 status, the Monday go-live checklist. Old bot + paper tests below a "History and tests" label; the old bot's status line + Refresh in its own "Old crypto bot (retired 2026-11-19)" block (> 4,000 px down) |
| 2. True | Live-day prices had no date | "(Kalshi numbers through 11-20)" on the live-day prices; checklist items say "from your PC, updated X ago" or "the PC says not yet"; the PC card's paper view = live legs at $2.50 only (no old $15 rows) |
| 3. Fast | DOM ready 0.12 s, 0 long tasks | same (no new library, no new request) |
| 4. Design kit | - | new parts use the page's tokens (--ok / --warn / --bad / --fh, .note, .krw-f) |
| 5. Robust | - | no card / old card / junk: every K8 part falls back (checks c6, d-, v-, s-); only 404s are kalshi.json + kit.json on a raw copy (both exist on the built site) |
| 6. Accessible | 0 unnamed controls; history links 21 px tall inside 44 px rows | 0 unnamed; whole 44 px row is the link's tap target + visible focus ring; checklist rows >= 44 px with real labels; aria-live on the K8 line and the checklist count |
| 7. Delight | - | the checklist says "ready" when all 6 are done |

Tests (with the lead's sw.js edit applied locally, then reverted): test_kalshi_page 347/347, test_kalshi_k8_dash 52/52,
test_kalshi_k8_day 50/50, test_kalshi_clock 40/40, test_kalshi_live 83/83.

## CLS (PERF ask, phone profile: CPU x4, 400 ms / 200 KB/s)
| Page | Before | After | What |
|---|---|---|---|
| dionysus/ | 0.897 | 0.059 | K8 today on the page from the first paint at full height (never hidden later; no data = one line + link); status keeps 3 lines. Rest 0.058 = the header crumbs (NAV: gate-nav.js inserts nav.gn-crumbs ~3.3 s) |
| kalshi/ | 0.469 | 0.105 | live-day box, windows list and K8 extras keep their height until first filled. Rest = the header (same NAV crumbs) |
