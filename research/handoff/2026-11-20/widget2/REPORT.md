# widget2: big Home Screen widget with tap buttons (2026-11-20)

| what | result |
|---|---|
| Large Scriptable widget (half the screen) | PC status + today $ on top; one line per account (up to 5): balance, today $, room left, PAPER tag if not live, **LONG/SHORT +$** when a trade is open; Kalshi + NQ price; **8 tap buttons** (NQ bot, Kalshi, Cities, Jarvis, Planner, Business, Websites, Decide), each its own link |
| Medium | PC + today $, 2 accounts, 4 buttons (NQ bot, Kalshi, Jarvis, Decide) |
| Small | unchanged (today $ + first account goal) |
| Old layout | still there: widget Parameter `classic` |
| Setup page | `widget/setup.html`: 4 drawings, one tap "Copy script + open Scriptable" (`scriptable:///add`), honest refresh note (iOS 5-15 min), Shortcuts fallback with the 8 exact Open URLs + copy buttons; linked from `widget/index.html` |
| Tests | `test_widget` 55/55 (new g. checks: 8/4 buttons each opening the right URL, SF Symbol icons, open trade shows SHORT +$125, setup page). money area 17/18: `money_dash` lab.html sideways scroll fails the same on the base (not mine) |
| Privacy | no key, no account ids, read only |

Files: `tools/web_public/widget/olympus-widget.js` (w4), `widget/setup.html` (new), `widget/index.html`, `widget/glance.html` + `business/{goals,index,accounts}.html` (?v=w4 cache bump), `tests/test_widget.py`, `tests/widget_harness.cjs` (fake SFSymbol + records every tappable stack).
Shots: `setup-light.png`, `setup-dark.png` (390 wide, no sideways scroll, no errors).

LEAD: nothing to wire (no sw.js / apps.js change needed; if sw.js precaches `widget/olympus-widget.js?v=w3`, bump to `w4` and add `widget/setup.html`).
Note: Scriptable cannot import a script from a URL by itself; the one tap copies + opens a new blank script, owner pastes.

## Fix 2 (owner correction, 2026-11-20): MFFU funded accounts start at $0
Funded accounts show **balance - start** (start = plan size, 25K -> $25,000; fallback balance - profit). ATLAS at $25,401 reads $401; the fixture ATLAS ($24,887) reads -$113. Evals unchanged. The rule is in `card()` of `olympus-widget.js`, so the Scriptable widget, Glance and the business pages that use `OLY_WIDGET` all follow it (`raw_balance` keeps the broker number; the payout coach still gets the raw balance). Mirrors the coming `PC_FEED.mffuView`. test_widget 56/56; money area 17/18 (same pre-existing money_dash lab.html fail).
