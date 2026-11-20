# LEAD WIRES (day-kalshi 2026-11-20)

## 1. tools/web_public/kalshi/sw.js (lead-only)
See `LEAD_WIRES_dashboard.md` in this folder (the helper's exact edit: CACHE = 'kalshi-' + the new kalshi.css / kalshi.js ?v,
both SHELL entries move together; k8.json network-first). Without it, cached phones keep the old K8 card.

## 2. Nothing else is required.
- No edit to build_web_dashboard.py, apps.js, the APPS table, or any live NQ file.
- `tools/web_public/kalshi/k8.json` is a committed, Claude-refreshed file (`python tools/kalshi_k8_feed.py` after
  `python research/kalshi_k8_day/fetch.py`). The PC does NOT rewrite it (a tracked file the PC rewrites breaks its git pull).
  Optional later: have the site build regenerate it into the OUTPUT folder from the PC's weekly tape (data/kalshi_live/), never into the repo.
- `tools/pc_report.py` got one small safe change (not lead-only): if the 2 ext posts are full, the Kalshi block first drops its
  new extras (last 5 bets, then edge health + day stop) instead of being cut whole.
