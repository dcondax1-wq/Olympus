# The 6 main dashboards (day-a11y, overnight 2026-11-22)

Owner: "when I open Olympus it goes to More with all the other dashboards. I want 6 main dashboards."

## Why it landed on More
- **The installed "Olympus" icon is the Jarvis page** (`jarvis/manifest.webmanifest`, name "Olympus", start `./`; Jarvis tells you to "Add to Home Screen").
- Jarvis opens on a long strip of every dashboard (the switcher's chips: JARVIS, ZENITH, NQ, AEGIS, LEDGER, ...). Its switcher sorts everything outside the six into one big **"More"** group (`jarvis/switcher.js` DIST / MORE_FIRST).
- Home (`gate/`) had the 6 arenas, but the old ones (Cities, Kalshi, NQ Bot, Jarvis, Websites, Business). The app never opened there.
- An icon already on the phone keeps the address it was saved with. Changing a manifest's start page alone would not move it.

## What changed
| What | Where |
|---|---|
| **Home = exactly 6 big tiles in the owner's order:** NQ Bot (ZEUS: accounts, trades, brain), Jarvis, Websites, Data City + Research, Money (My MFFU Accounts), Kalshi. Each tile opens its dashboard and has at most 2 short links (Trades · Brain, Brief · Inbox, Factory · Portal, Research · Tests, Decide · Taxes, Desk). All 6 plus More fit the first 390 x 844 screen, OLYMPUS NIGHT. | `gate/index.html`, `gate/gate.css`, `gate/arenas.js` (live lines: payout progress on Money, K8 on Kalshi, today's $ + drawdown on NQ) |
| **More:** one button under the tiles. Right now, Everything else, All apps by arena, pins, recent and A to Z show only after a tap. Nothing remembers it, and an old `#more` address is dropped, so the app always opens on the 6. | same |
| **Launch → Home:** a fresh launch of the installed app on the Jarvis page goes to Home, once per launch (sessionStorage). It doesn't when Home already opened this launch (the Jarvis tile), with a `#app` link (notifications), with `?stay=1`, in a frame, or in a normal browser tab. | `jarvis/index.html` (first script in `<head>`) |
| **One order everywhere:** the arenas are the 6 + Everything else in the same order. Data City now holds the Research hub. Money opens My MFFU Accounts. The breadcrumbs, "Go to" and the arena pages follow. | `olympus/gate-catalog.js` ARENAS, `hub/arena.js` (frontPath) |
| The Jarvis switcher's six (FIRST) in the same order | `jarvis/switcher.js` |
| The map | `docs/OLYMPUS_MAP.md` (generated) |

## Tests
- `test_home_six` 13/13 (new): manifests, the guard, the 6 tiles and links, More. Browser as the installed iPhone app: the launch lands on Home, the Jarvis tile then stays, `#link` / `?stay=1` / a normal tab never move, `#more` dropped, More never remembered, 44 px, no sideways scroll.
- `test_gate_page`, `test_olympus_nav`, `test_olympus_map`, `test_hubs`, `test_homescreen`, `test_jarvis_hub`: see the lead message for the numbers.
