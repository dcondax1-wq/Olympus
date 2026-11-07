# Kalshi City network switch and satellite wards

**Branch:** `chatgpt/kalshicity-network-switch-20261106`  
**Scope:** Kalshi City source files and its focused layout/navigation regression only.

## Result

- Added a compact City Network popover linking Cities, Data City, and Kalshi City, with the current city marked.
- Added a readable market-district selector. It reports each district's published or demo edge count; 3D moves the camera while the 2D fallback opens that district's edge list. No strategy state changes.
- Recentered the visual city around Market HQ, with 40 deterministic, scenery-only satellite wards total across two rings (20 inner and 20 outer). Each ward gets 4–6 small glowing blocks with roads kept clear. No counts are presented as market data.
- Kept the 3D, 2D atlas fallback, and mobile map switch in sync; demo fixture data is explicitly labeled as invented sample data in the GPU fallback, while published data keeps its source label. Jarvis cards now warn on unverified/stale inputs and use source timestamps with a 15-minute freshness window.
- Preserved all read-only/paused semantics. No engine, order, account, risk, sizing, or strategy code changed.

## Checks

- `node --check` for all changed city modules: PASS.
- `node tests/test_kalshicity_network_switch.mjs`: PASS (40 wards total across two rings, every ward has 4–6 visible buildings, neighborhood-road gaps preserved, 9-market layout covered; demo fallback provenance and stale-card freshness regressions included).
- `KC_NO_BROWSER=1 python -X utf8 -m tests.test_kalshicity_page`: PASS (37/37).

## Blocker

390×844 browser screenshots and interactive high/LITE checks are not available from this executor: the Playwright package exists, but its Chromium binary is missing (`/root/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome` does not exist). Keep this PR draft until rendered phone QA and the published mirror are checked.
