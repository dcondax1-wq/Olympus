# tyche-fallback

When WebGL cannot start, Tyche shows a scrollable board of up to five open bets from its already normalized feed. Each card opens the existing detail sheet. It handles zero positions and keeps the existing balance/today/week and all tabs. Text is assembled with `textContent` from user-facing market data.

Checks: `node --check tools/web_public/tyche/main.js` passed. No Chromium binary was available for 390x844 runtime screenshot, so visual QA is pending. No Kalshi order or risk code was modified.
