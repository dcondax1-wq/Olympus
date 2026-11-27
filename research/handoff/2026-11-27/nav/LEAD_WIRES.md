# night-nq-nav: lead wires (2026-11-27)

The NQ pages as ONE app: bottom dock (Home, Live, Chart, Accounts, Flow, Brain, PC), the live PC pill ("PC 4m · 2 armed",
BLITZ never counted), pull-to-refresh, page transitions (View Transitions; fade fallback), haptic taps, install chip, offline chip.
. Files (all new, owned by nav): `tools/web_public/nq/nqnav.js`, `nqnav.css`; changed:
`nq/manifest.webmanifest` (description, shortcuts Live / Accounts / Brain, launch_handler; start_url / scope unchanged `./`).
Test: `python -X utf8 -m tests.test_nq_nav` (add `"nq_nav"` to `AREAS["nq"]` in tests/run_area.py: helpers do not own it).

## 1. One line per page (just before `</body>`; nqnav.js loads nqnav.css itself)

```html
<script src="nqnav.js?v=1" defer></script>
```

| page | add | note |
|---|---|---|
| nq/index.html | `<script src="nqnav.js?v=1" defer></script>` | Home tab |
| nq/live.html | same line | Live tab; its own `#pc` pill can stay, or swap for a slot (step 2) |
| nq/accounts.html | same line | Accounts tab |
| nq/brain.html | same line | Brain tab |
| nq/trading_home.html | same line | lights Home |
| nq/orderflow.html (of helper, new) | same line | Flow tab (hidden until the page exists: HEAD probe) |
| nq/pchealth.html (home helper, new) | same line | PC tab (until it exists the PC tab opens `../pc/index.html`) |
| nq/chart.html (only if chart makes one) | same line | Chart tab (until it exists: `index.html#chartCard`) |

A page that is not named in the list can say its tab: `<script src="nqnav.js?v=1" data-tab="chart" defer></script>`.

- With night-nq-speed's `nqfeed.js` tag in the head (its NQCORE_API.md), the pill reads `window.NQ_FEED` (cached() first paint, on() updates,
  refresh(true) on pull / Refresh): no second ntfy read. Without it, the pill falls back to `../pc_feed.js` itself.

## 2. Optional hooks for page owners

- PC pill inside a page header: `<span data-nq-pc-pill></span>` (gets its own live copy of the pill).
- Pull-to-refresh without a reload: `addEventListener('nq:refresh', (e) => { e.preventDefault(); reload().then(e.detail.done); });`
  Nobody claims it = the page reloads.
- Areas that must never start a pull (a chart with its own drag): add `data-nq-nopull` (canvas is skipped already).
- `window.NQNAV.refreshPC()` = fetch the PC feed now; `NQNAV.state(lite)` = `{lv, text, age, armed}`.

## 3. Things for the lead to know

- No service worker of its own (lead 05:28: one cache = ../sw.js; the lead adds NQ precache there). The offline chip uses navigator.onLine.
- The kit's floating buttons (`.oly-home`, `.oly-ask-btn`) are lifted above the dock by nqnav.css; body gets bottom padding.
- Inside Jarvis / a hub (`html.framed`) nothing is drawn (only `[data-nq-pc-pill]` slots).
- Bump on a change: pages carry `nqnav.js?v=N`; nqnav.js loads `nqnav.css?v=N` (now 3 after QA N2/N3: pages should go to `nqnav.js?v=3`, and the sw.js precache entry too).
- QA note seen while testing: live.html shows `MFFUEVBLDR...6016` (last 4 only = masked per PRIVACY rules, so OK).
