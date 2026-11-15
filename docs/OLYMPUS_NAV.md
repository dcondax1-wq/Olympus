# OLYMPUS NAV v3: find anything in one or two taps

Written 2026-11-15 (team NAV). Owner, from his phone: *"make it more organized, the little categories are too hard to find everything,
there's gotta be a better way, figure it out"*.

## The problem in one line

The hubs (docs/OLYMPUS_IA_V2.md) sort the 83 apps well, but to FIND one you had to guess which hub and which tab it is in. Guessing is the slow part.

## The fix: stop guessing, type or tap

| What | Where | What it does |
|---|---|---|
| **One big search, first on the Home** | `gate/` top, and the same in every app's **Go to** (`olympus/gate-nav.js`) | Plain words and synonyms find apps, **hub tabs** ("risk" -> Bots & Evals > Risk) and **shortcuts** ("theme" -> Change the look, "payout", "micros", "drawdown", "bring the bots back", "all apps"). Enter opens the first app. |
| **Pinned** | under the search (Home) and first in Go to | His favourites. A star on every search row, every A to Z row, and "Pin this app" in Go to. This phone only (`gate.pins.v1`). |
| **Your six** | Home, under Right now | One tap each, with a live line: Zlarior · ATLAS (bots on, today's $), Today (trade window), Money (month / all time), Drawdown ($ left per eval), My day (shift), Kalshi (balance). Plain links: they work even if the script fails. |
| **Recent** | Home and Go to | The last 6 apps opened (`gate.recent.v1`, unchanged key). |
| **All apps A to Z** | the A-Z button next to the search, a wide button under the hubs, "All apps A to Z" in Go to (`gate/#az`) | One sheet: every app in big rows (60 px) under a letter each, a filter box, a star to pin. The labs sit at the end under Workshop. |
| **The hubs** | Home, unchanged | Still there for browsing by job. |

Home order on a 390 x 844 phone: the search, Pinned (only once he pins), Right now, Your six, Recent, the hubs (+ All apps A to Z), Look.

## Where it lives (code)

| Piece | File | Test |
|---|---|---|
| Search for everything (`findAll` = page hubs + `findActions` + `find` + `findTabs`), the shortcuts (`actions`), `az()`, `quick` | `tools/web_public/olympus/gate-catalog.js` (v3, `?v=nv1`) | `tests/test_gate_page.py` (b) |
| Home: big search, Pinned, Your six, Recent 6, A to Z sheet | `tools/web_public/gate/` (`index.html`, `gate.js` `?v=g6`, `gate.css` `?v=g6`) | `tests/test_gate_page.py` (a, c `nav_checks`) |
| Go to on every app: Pinned first, Pin this app, actions + tabs in its search, All apps A to Z | `tools/web_public/olympus/gate-nav.js` (`?v=g4`, every tag and agora-ui.js bumped) | `tests/test_gate_page.py` (c), `tests/test_hubs.py` |
| Screenshots 390 x 844 | `docs/shots/nav/` | by eye |

Read only, offline-safe: nothing new is fetched; pins and recent live in localStorage inside try / catch (private mode: the page still works, no Pinned row).
