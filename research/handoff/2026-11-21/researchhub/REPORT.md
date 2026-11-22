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

## Cities link (owner: "combined with the cities")
- `tools/web_public/research/hub.json` (flat, for the Cities Lab & Research district): 146 items {id, title, family, status
  live|lead|rejected|decide, usd_month, date, summary, url}; ids live-zlarior, live-atlas, decide-<id>, lead-/rejected-<slug>.
  Pushed 73561b86, schema sent to the lead and the Cities session.
- Clio: "See it in the city" in every hub item's sheet (../cities/?fly=<id>); deep links ?read=<slug> and ?item=<id> (e3c8eae9).

## Tests
- tests/test_research_hub.py: 30/30 (generator on the real repo, parsers on a temp repo, cliocore hub maths in node, the page in
  Chromium at 390x844: tabs, search, tap -> reader fetch, own-text sheet, decisions, DEMO hub when hub.json is missing, no
  sideways scroll, no console error).
- tests/test_clio_page.py: 47/47 (updated: OLYMPUS NIGHT instead of AGORA; hub.json in the allowed reads; hub 404 in the demo cases).
- tests/test_learn_night.py: 64/64 (the new "hub" step). tests/smoke.py: 11/11.
- Python Playwright 1.63 + numba were pip-installed in this container to run the browser / money suites.

- tests/test_olympus_kit.py: not finished here (over 20 minutes twice in this container); please run on pc.
- privacy area: public_build_privacy 59/59 PASS; repo_secrets 1 FAIL pre-existing on pc (tests/test_rapid_arm.py, 50a9105d:
  a full-looking MFFU id); private_link / phone_safety cannot start here (no fastapi).

## Screenshots (390x844, deviceScaleFactor 2)
top-390-works.png, top-390-rejected.png, top-390-leads.png, top-390-decide.png, top-390-reader.png (the reader shows "could
not be loaded" in the local test server only: the site build publishes writeups/<slug>.md).

## Not done / next
- research/lab/*.json headline numbers: 604 files with no common schema; the hub shows the edge light + file count only.
- "Open leads" shadow logs: none have a common file yet; the paper leads come from write-ups with status promising.
