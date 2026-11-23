# LEAD_WIRES: NQ Accounts screen (day-accounts, 2026-11-23)

Helpers never edit `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js`, the `olympus.js` APPS table. Exact lines for the lead.

## 1. Phone tile (jarvis/apps.js, next to the `tradehome` url app)
```js
  app('nqaccounts', 'Accounts', 'trading', '#f1c14b', 'Every account: $, room, payout, bots, 7-day clock', { url: '../nq/accounts.html', glyph: '▤' }),
```
(The same one entry in the olympus.js APPS table if it should be on the Olympus home.) The NQ page already links it (header button "Accounts").

## 2. sw.js
`nq/` is in OTHER_APPS, so nq/accounts.html, accounts.js, acctcore.js, accounts.css are never handled by the worker: nothing to add.

## 3. build_web_dashboard.py
Nothing: static files; reads ../home.json, ../business/accounts.json, ../business/payday.json (both already copied) and the PC post via ../pc_feed.js.

## 4. Finding left for the lead (display only, NOT changed: it is in the live keep-alive path)
`engine/keepalive.plan()` between 18:00 ET and midnight: the trading day is already tomorrow, but `open_on(today)` needs
`_et(t).date() == today`, so tomorrow's session is not counted. A Monday-evening post can say "act Wed" when the real act day is
Tue (the 15:33 tick on Tue computes it right, so no trade is missed). The NQ Accounts screen computes the act day itself with the
evening fixed (nq/acctcore.js actDay; equal to plan() in the daytime, 800 cases in tests/test_accounts_screen). One-line fix if wanted:
`return bool(w) and (d != today or _et(t).date() < today or m < w[1])` - but `due` / `eve` then change in the evening tick, so it needs
tests.test_keepalive + test_k7proof run before it lands.

## Fixed here (tools/pc_silent_check.py, the cloud K7 alert)
- the de-dupe matched a NAME SUBSTRING: "Rapid EOD 25K" is inside "Rapid EOD 25K #2", so once the first Rapid's "PC looks off"
  push went out, the NEW Rapid's push was silenced for the day (and the other way round). Now the exact title prefix.
- feed_clock rebuilt the clock from the mf rows only (strategy trades), ignoring the keep-alive's own fills and the ON switches in
  the PC's k7 rows: after a keep-alive trade the cloud still pushed "must trade". Now the newer base day per account wins, "on" comes
  from the PC's row, and an account only in k7 (mf cut for size) still counts.

Tests: `python -X utf8 -m tests.test_accounts_screen [--shots]` (nq + pc areas). Shots: research/handoff/2026-11-23/accounts/*.png.
