# Trade alerts: what your phone gets, and when

Owner, 2026-11-20: "notifications to my phone exactly when a trade is taken and closed, results of it."

## What you get

Two pushes per trade, per account, within seconds:

| When | Example |
|---|---|
| **Entry**: NinjaTrader reports the fill | **Zlarior 50K: LONG 4 MNQ @ 21,034.25**<br>stop 21,012.00 (-$178), target 21,090.50 (+$450) · 10:31 AM ET. |
| **Exit**: the stop or target fills, or the bot closes the trade (time exit, day's end, kill switch) | **Zlarior 50K: closed LONG +$312 (target)**<br>today +$312, balance $49,505, $3,495 to pass · +1.4R · 4 MNQ · 10:58 AM ET. |

- **Every account:** Zlarior 50K, Zlarior 25K #2 and any later extra account, ATLAS 25K funded, the Rapid EOD 25K (LIT's lane is
  "Rapid EOD 25K", ATLAS's lane on the same account is "Rapid EOD 25K (ATLAS)"), and the 50K combo when it is on ("ATLAS on Zlarior 50K").
  Never Paper, Sim or BLITZ.
- **One push per event and route.** The entry and the exit of a trade each go out once per route (keyed by the fill, per account). Two
  accounts entering on the same bar get one push each. The 15-minute report skips its own copy of a trade ntfy already got, matched by
  entry time AND account (since 2026-11-20: before, one account's alert on the same bar made the report drop another account's copy).
- **The numbers.** Entry: your $ risk to the stop and your $ to the target (distance x micros x $2). Exit: the $ from the real fills (before
  commission). Today's $, balance and $ to pass come from the PC's last 15-minute account view, plus every close the phone got since then.
  A funded account shows its balance, and "payout ready $X" once a payout can be requested, instead of "to pass".
- **How it arrives (since 2026-11-20): on BOTH routes.** The Olympus phone app (Web Push) AND your private ntfy alert topic (the ntfy app),
  for trades and for the important alerts (PASSED / FAILED / LOCKED / payout ready, room low, bot down / NinjaTrader closed / FEED STALE,
  PC silent). Before, ntfy got them only when no Olympus phone "took" them, and "took" only meant Apple's push service accepted them. On
  Fri 2026-11-20 ATLAS's 03:45 ET entry and its 07:10 ET +$514 result reached no phone. Most likely (unconfirmed: the PC's push logs were
  not read) they went to the one Olympus phone the PC's public posts listed all night, Apple said "accepted", and ntfy and the 15-minute
  report both skipped their copies. The ntfy route reaches you only if the ntfy app follows your alert topic (`python tools/pc_report.py
  --setup` prints it). If the phone app took a trade but ntfy refused it at that moment (a limit, the network), the 15-minute report sends
  the ntfy copy (not the app copy again), retried for 2 hours at most. `trade_routes` in `notify_settings.json`: `"both"` (default),
  `"olympus"` (Olympus first, ntfy only when no phone took it) or `"ntfy"` (ntfy first, Olympus only when ntfy did not take it).
- **At night** (quiet hours, 23:00-07:00 ET): entries and results still show, without sound, like other ordinary alerts. To make them ring
  at night, add `trade_opened` / `trade_closed` to `ring_in_quiet_hours` (the owner's yes / no on STATE.md; ATLAS enters around 03:00-04:00
  ET, LIT from 02:00 ET on several accounts at once, so that can be several sounds a night).

## Check it yourself

- First, on the iPhone: Olympus from the Home Screen, the card under ZEUS, **Send a test** (tests the Olympus route alone).
- On the PC: `python -X utf8 -m engine.alert_check` lists the routes (how many Olympus phones, ntfy topic set or not, entries / results on,
  ring at night, trade_routes) and says plainly what is missing ("NO ROUTE ..." when a trade alert would reach nobody). `--test` also sends
  one TEST entry and one TEST close (the words of a real alert, marked "TEST, no trade was placed", never counted as a trade) on every route
  and prints what each answered. The PC dashboard's Settings > Phone app notifications > **Send test** runs the same test (once a minute at
  most; the ntfy half is skipped when ntfy's day is down to the room kept for trade alerts).
- An Olympus "accepted" is NOT proof the phone showed it: check the iPhone. If the TEST shows in the ntfy app but not in Olympus, open
  Olympus from the Home Screen: "Allow notifications" on its card means this iPhone is not the phone the PC sends to (tap it); "Notifications
  on" means it is (then iPhone Settings > Notifications > Olympus: Allow, Banners, Sounds; and Focus / Sleep).
- Every trade alert's answers are kept on the PC in `logs/notify/trade_alerts.jsonl` (account name, masked key, app: sent / devices / errors,
  ntfy: sent or why not; "warn" when it reached no route). The 15-minute report's card says **NO PHONE ALERT ROUTE** when the PC has no
  Olympus phone and no ntfy topic.

## Turning one off

On the PC, edit `notify_settings.json` in the bot folder (create it if missing). It applies at once, with no restart.

```json
{"alerts": {"trade_opened": true, "trade_closed": false}}
```

- `trade_opened: false` = no entry pushes. `trade_closed: false` = no exit pushes.
- Ring for trade alerts at night: add `trade_opened` / `trade_closed` to `ring_in_quiet_hours` (default: silent at night, still shown).
- One app only first: `{"trade_routes": "olympus"}` or `{"trade_routes": "ntfy"}` (the other app stays the fallback).
- Quiet hours: `{"quiet_hours": {"from": "22:00", "to": "06:30"}}`, or `{"quiet_hours": {"off": true}}` for sound all day.
- The other alert types (PASSED / FAILED, the 16:15 day summary, the 07:30 brief, PC silent, problems) are in the same file
  (`engine/notify.py` lists them all).

## ntfy's daily limit

ntfy.sh's free tier takes about 250 messages a day per internet address, and the PC's status posts already use about 220. Trade alerts are
rare (a few a day). Each one is counted. The extra status posts and the chart stop 12 messages before the limit, so they never use up the
room a trade alert needs. The main 15-minute status post still goes every run, because it is the PC's sign of life.

## Where it lives (for Claude)

- Words and numbers: `engine/notify.py` (`entry_message`, `exit_message`, `exit_context`, `instant_entry`, `instant_exit`, `ntfy_today`).
- Sending: `engine/push.py` (`pc_notify` → `_pc_send`: a trade's entry / exit to the phone app AND ntfy (`notify.trade_routes`), every
  other notice the app only; de-duplicated by key; `_trade_log`). Phone-only deliveries: `notify.instant_record(app_only=True)` →
  `app_entries` / `app_exits`, read by `tools/pc_report.py` `_app_had` (the report then sends only its ntfy copy). Matching is per account:
  `notify.report_acct` ("lit" → the primary's bare key, "atlas" → `:acctb`, "blitz" → `:acctc`) vs `notify.key_acct`. The report's
  important kinds: `notify.DUAL_KINDS`, `pc_report._dual_alert`. Self-check: `engine/alert_check.py` (`ntfy_room`, `TEST_COOLDOWN_S`).
- Routes: the bot's own NinjaTrader adapter (`engine/ninjatrader.py` `_push_fill` / `_push_exit`). A sub-account's adapter notifies under
  its own name and key through `push_as`, set by `engine/account_b.py` (ATLAS, key `:acctb`; the Rapid's ATLAS lane `:acctr`) and
  `engine/multi_account.py` (extra accounts and the Rapid's LIT lane, key `:<id>`). Before 2026-11-20, ATLAS on NinjaTrader sent **no**
  instant entry or stop / target exit: it skipped its own because the adapter "reports fills", and its adapter never sent one.
  Exits on any account reached ntfy only with the 15-minute report.
- Budget: `tools/pc_report.py` (`TRADE_ALERT_RESERVE`, `day_used`).
- Tests: `python -X utf8 -m tests.test_trade_alerts` (fake fills through every route: exactly one entry and one exit, the right name and $;
  part h replays the 2026-11-20 ATLAS miss with one phone that accepts everything: entry + result on ntfy too, silent at 03:45 ET but
  shown; part i: per-account matching, the important kinds on both routes, trade_routes, the test's cooldown and ntfy room), `tests.test_alert_audit`
  (every route on both deliveries), `tests.test_notify`, `tests.test_webpush`.
