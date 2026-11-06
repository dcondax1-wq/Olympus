# Atlas recent room tap target

After a featured room visit, Atlas's `RECENT` link was 32 px tall at 390×844, below the project's 44 px touch-target rule. The CSS now makes each recent link at least 44 px high and vertically centers its label. The stylesheet version moves to `atlas.css?v=4` so cached phones receive it.

Local Chromium 390×844 high/LITE on exact branch assets: Oracle visit and return produced a 75×44 px recent link, keyboard focus reached it, no horizontal overflow or page JS errors. `node --check atlas.js` passed. Physical iPhone and full private-repo area tests remain unverified. No bot, worker, catalog, or trading changes.
