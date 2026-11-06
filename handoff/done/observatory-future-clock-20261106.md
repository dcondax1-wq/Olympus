# Observatory future source clock

Flags published source timestamps more than five minutes ahead of the viewer's clock as needing review. The source detail and review card explain the discrepancy; minor clock skew stays tolerated. No publisher, bot, or trading control changed.

Local: `node --check tools/web_public/observatory/app.js` and `node tests/test_observatory_lesson_clock.mjs` passed. Full Python gate and 390×844 rendered QA unavailable without an authenticated checkout/preview; keep draft until those checks pass.
