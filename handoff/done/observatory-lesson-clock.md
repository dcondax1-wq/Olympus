# Observatory lesson clock

Branch: `chatgpt/observatory-lesson-clock`

The published Kalshi City lesson log is append-only. Its latest lesson event is dated 2026-11-04 02:39 UTC, while the read-only Kalshi research scan was published at 2026-11-05 07:27 UTC. Observatory previously used the last lesson event as if it were the lesson log's publish time. If no new lesson is justified for 48 hours, it would warn that the source is stale even while the scheduled research publisher succeeds.

Observatory now uses only explicit publisher timestamps for freshness. Without one, Learning is amber/unverified rather than green. The Learning detail shows the latest lesson event as an event, with a separate note that publisher time is unavailable from this file. An empty log says no dated lesson yet. Kalshi City scan remains the timestamped research source. No bot, trade, publishing, or autonomous edit path changed.

Verification: `node tests/test_observatory_lesson_clock.mjs` and `node --check tools/web_public/observatory/app.js` passed. Full browser QA at 390×844 and the actual source scan is pending. This remains a draft. It does not overlap Observatory intro PR #215 or optional file 404 proposals.
