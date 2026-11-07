# Oracle future source time

Oracle previously clamped every negative age to zero. A feed timestamped far in the future could therefore remain **current**, outrank an honest site/live source, and keep present-tense market values on screen until wall time caught up.

`normalize()` now rejects non-demo source timestamps more than five minutes ahead. A small publisher/device clock skew is tolerated; historical and sample replay documents keep their replay clock.

Focused checks: `node tests/test_oracle_future_source.mjs` and `node --check tools/web_public/oracle/data.js`.

No engine, bot, account, publisher, worker, route, Zlarior, or ATLAS code changed. This is data-display correctness only. Existing Oracle UI code filters a null normalized source and falls back to the established demo when neither live nor site source is valid; this small data-only fix does not change the rendered view or controls.

PRs #191 and #192 have merged. Active Oracle visual drafts #133, #232, and #286 do not change `tools/web_public/oracle/data.js` or this focused test, so there is no same-file conflict or required stack rebase for this change. Their rendered phone/accessibility QA remains separate. This PR is not live until merged and deployed.
