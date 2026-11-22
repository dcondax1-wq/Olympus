# LEAD_WIRES: Trading Home (day-tradehome, 2026-11-22)

Helpers never edit `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js`, the `olympus.js` APPS table, `scripts/make_shortcuts.ps1`
(its test is test_win_scripts, never run by helpers). These are the exact lines for the lead.

## 1. Phone screen: add the app tile (jarvis/apps.js, after the `fates` line 78; opens the page in the nq folder)
```js
  app('tradehome', 'Trading Home', 'trading', '#f1c14b', 'Today: bot, keep-alive, alerts, accounts, next $', { url: '../nq/trading_home.html', glyph: '⌂' }),
```
(Same pattern as `zenith` on line 75: a url app. The APPS table in olympus.js needs the same one entry if the lead wants it on the Olympus home.)

## 2. sw.js
`nq/` is already in OTHER_APPS (line 99), so the page and its two JS files are never handled by the worker: nothing to add.

## 3. build_web_dashboard.py
Nothing: the page is static (nq/trading_home.html, nq/trading_home_core.js) and reads only `../status_feed.json` through `../pc_feed.js`.

## 4. PC desktop shortcut (scripts/make_shortcuts.ps1, the `$items` list next to 'LE STOP BOT', line ~25)
```powershell
    @{ Name = 'LE TRADING HOME'; File = 'TRADE_HOME.bat'; Icon = 27; Tip = 'One menu: status, start bot, keep-alive, add account, alerts, stop, update' }
```
Then run `python -X utf8 -m tests.test_win_scripts` once on a PC-side session (helpers must not).

## 5. Optional, makes the alerts line real (tools/pc_report.py core post)
The public post has no alerts flag, so the phone's "Phone alerts OK" line is the owner's own tick (30 days). To let the phone see it,
add `"al": 1 if snap.get("alert_bus") else 0` to the core (CORE_OWN in tools/pc_feed.py) and read `lite.al` in
`tools/web_public/nq/trading_home_core.js` (the `alerts` row). Not done here: strategy/report files are the lead's.
