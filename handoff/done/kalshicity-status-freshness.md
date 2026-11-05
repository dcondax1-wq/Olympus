# Kalshi City status freshness

- The published `kalshi-feed/kalshi.json` was last marked `running: false`, status `Paused`, but a static snapshot cannot prove it remains paused indefinitely. The saved `edges.json` book has its own older `feed_t`.
- Kalshi City now calls the bot state `Status unverified` once the newest bot timestamp is more than 30 minutes old (or missing/future-dated), shows how old the last report is and what it last said, and removes stale paused fog. Balances and research remain as-of snapshots.
- No trader, order, account, or publisher code changed.
- Checked `node --check cityfeed.js` and `python -m unittest tests.test_kalshicity_freshness -v` on the isolated file, 1/1 passed. Full app/browser test and worker bump remain for integration.
