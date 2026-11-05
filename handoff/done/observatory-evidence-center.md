# Observatory evidence center

- New read-only city at `tools/web_public/observatory/`.
- Scans six published JSON sources on open and every five minutes while visible; records up to 30 summaries in this browser, compares content markers, and exports evidence for review.
- An unavailable, demo, stale (>48 h when a timestamp exists), or changed source becomes a review card. No trading or deployment controls.
- Checked: `node --check observatory/app.js`; HTML parsed with Python HTMLParser.
- Not checked: visual screenshots and full repository tests (private source is available through the GitHub connector, but this execution environment cannot clone it or launch Chromium).
- Lead wiring needed: register Observatory in Jarvis app list and publisher; add it to the site navigation and worker cache, then run full app/build tests. For continuous closed-page operation, schedule a separate read-only publisher job and expose timestamped snapshots; local refresh only runs when open.
