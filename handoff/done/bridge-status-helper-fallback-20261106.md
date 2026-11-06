# Bridge helper fallback

If `status-line.js?v=1` fails to load, Bridge uses an inline safe fallback. A published job shows “Job status display unavailable · refresh to retry” rather than a stale “waiting” label or blank card. Successful helper loading preserves snapshot wording.

Focused Node fallback and status-line tests passed; Bridge page `--no-browser` 30/30 passed on mirrored source. Local 390×844 headless Chromium high and low first-screen renders showed no visible overlap. A separate low-mode run with synthetic `in progress` status and a forced helper 404 showed the fallback in DOM. With helper present, it showed “Last reported: in progress (1 file).” Full Python Playwright browser lane unavailable; publisher/Pages QA follows merge and dashboard mirror. No bot/trading files touched.
