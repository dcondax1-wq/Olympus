# Atlas quick launch

The four hero destinations now show up to two favorite dashboards and two recent dashboards, with the rest filled from the original featured destinations. A first visit keeps the original four cards. The list updates when a favorite changes, uses the same local device storage and safe catalog link function, and does not add another panel on a narrow screen.

Scope: `tools/web_public/atlas/` only. No catalog, worker, publisher, bot, order, or account changes.

Verification: `node --check` passed. A local Chromium 390×844 pass checked first-visit featured gates, a featured link recording a recent visit, a favorite taking priority, persistence after navigation, `?q=high` and `?q=low`, no horizontal overflow, four gate heights of 86–99 px, and no page errors. A 1363 px desktop pass found no horizontal overflow. Guard run 42240035254 passed. Full repository and cross-app tests remain unverified; PR remains draft pending those checks. Script query version bumped from 3 to 4.
