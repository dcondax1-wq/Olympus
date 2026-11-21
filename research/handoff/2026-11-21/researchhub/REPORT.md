# Research Hub REPORT (day-litedge, 2026-11-21)

**Built: one Research Hub, inside Clio** (`tools/web_public/clio/`; no new app to register).

| What | Result |
|---|---|
| Generator `tools/research_hub.py` -> `clio/hub.json` (267 KB) | 2 live strategies, 94 tried-and-rejected, 47 open leads, 3 money decisions, 230 write-ups; privacy scan 0 |
| Owner view (first card) | 4 tabs: What works now (Zlarior backtest 2026 $4,382 a month, real 2 trades -$566; ATLAS $6,779 a month, real 3 trades +$1,510; edge check GREEN / GREEN), Tried and rejected, Open leads, Money decisions |
| Each item | one plain line + its $; tap opens the write-up (writeups/<slug>.md) or the item's own text |
| Search + filters | the search box filters the hub and the library; family + date (7 / 30 / 90 days) filters; verdict chips |
| Look | OLYMPUS NIGHT (nqtheme + moneyfx, like Board / Ledger), 390x844, 2x2 tabs, every tap >= 44 px |
| Stays current | `tools/learn_night.py` step "hub" (nightly, after the Decide cards); optional build hook in LEAD_WIRES |
| Sources | research/writeups/*.md front matter, docs/TESTED_AND_REJECTED.md, research/findings/LEDGER.md (open rows), business/decisions.json (open / later), trading/trades.json (live + backtest), research/lab (edge light, file count) |

Rules kept: rejected ideas' $ is shown neutral (the figure the test quotes, never green); BLITZ is not listed under What
works (hidden, paper); account numbers masked by tools/site_privacy, the build stops on any privacy finding.

## Tests
- tests/test_research_hub.py: 26/26 (generator on the real repo, parsers on a temp repo, cliocore hub maths in node, the page in
  Chromium at 390x844: tabs, search, tap -> reader fetch, own-text sheet, decisions, DEMO hub when hub.json is missing, no
  sideways scroll, no console error).
- tests/test_clio_page.py: 47/47 (updated: OLYMPUS NIGHT instead of AGORA; hub.json in the allowed reads; hub 404 in the demo cases).
- tests/test_learn_night.py: 64/64 (the new "hub" step). tests/smoke.py: 11/11.
- Python Playwright 1.63 + numba were pip-installed in this container to run the browser / money suites.

## Screenshots (390x844, deviceScaleFactor 2)
top-390-works.png, top-390-rejected.png, top-390-leads.png, top-390-decide.png, top-390-reader.png (the reader shows "could
not be loaded" in the local test server only: the site build publishes writeups/<slug>.md).

## Not done / next
- research/lab/*.json headline numbers: 604 files with no common schema; the hub shows the edge light + file count only.
- "Open leads" shadow logs: none have a common file yet; the paper leads come from write-ups with status promising.
