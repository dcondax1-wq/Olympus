# Atlas Back navigation freshness

On the live site, opening Oracle from Atlas and pressing browser Back restored a cached Atlas DOM: `RECENT` was still hidden and the hero still showed first-visit gates. Reloading Atlas immediately revealed the saved Oracle visit. A back-forward cache restore does not rerun Atlas initialization.

The page now rereads its local favorites/recent state and rerenders on a persisted `pageshow`. Ordinary new loads already read storage. If storage is blocked, it keeps the current in-memory state. No worker, publisher, catalog, bot, or trading changes.

Local Chromium 390×844 high/LITE: standard Back path showed Recent; a simulated persisted `pageshow` after a storage update refreshed the hero to Favorite Zenith, retained a 44 px Recent target, search showed `1 destination`, and no page errors or horizontal overflow. Local Chromium did not preserve the page in back-forward cache; the real cloud Chrome reproduction is the before evidence. Full private-repo tests and physical phone QA remain unverified.
