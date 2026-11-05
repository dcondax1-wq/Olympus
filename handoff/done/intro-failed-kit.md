# Shared arena intro failed-load cleanup

The kit's error handler can move an arena to `failed` and display Retry while the 2.4-second shared intro remains above it. The intro formerly checked only that `window.OLYMPUS` existed, so an already failed kit still started the film; an error during playback stayed covered until the film timer. The shared intro now skips an already failed kit and ends on the next frame if the kit transitions to failed. This does not hide or alter Retry.

Checks: `node --check tools/web_public/olympus/intro-app.js`; `node --test tests/test_intro_failed_kit.mjs` passed 3/3 for before-start, during-playback and ready-state behavior. No bot, order, worker or app data path changed.

Before merge: render an arena at 390×844 with its app module request blocked, check Retry visibility and keyboard activation; repeat offline. Coordinate cache-tag updates of shared `intro-app.js` from the publishing lane. Drafts #215 and #123 also edit `intro-app.js`; rebase sequentially and rerun checks. This is a draft, not live.
