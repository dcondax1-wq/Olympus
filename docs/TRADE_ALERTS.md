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
- **One push per event.** The entry and the exit of a trade each go out once (keyed by the fill, per account). Two accounts entering on the
  same bar get one push each. The 15-minute report skips its own copy of a trade the phone already got.
- **The numbers.** Entry: your $ risk to the stop and your $ to the target (distance x micros x $2). Exit: the $ from the real fills (before
  commission). Today's $, balance and $ to pass come from the PC's last 15-minute account view, plus every close the phone got since then.
  A funded account shows its balance, and "payout ready $X" once a payout can be requested, instead of "to pass".
- **How it arrives.** The Olympus phone app (Web Push) first. If no phone took it, it goes to your private ntfy alert topic instead.
- **At night** (quiet hours, 23:00-07:00 ET): the push still comes, without sound.

## Turning one off

On the PC, edit `notify_settings.json` in the bot folder (create it if missing). It applies at once, with no restart.

```json
{"alerts": {"trade_opened": true, "trade_closed": false}}
```

- `trade_opened: false` = no entry pushes. `trade_closed: false` = no exit pushes.
- Quiet hours: `{"quiet_hours": {"from": "22:00", "to": "06:30"}}`, or `{"quiet_hours": {"off": true}}` for sound all day.
- The other alert types (PASSED / FAILED, the 16:15 day summary, the 07:30 brief, PC silent, problems) are in the same file
  (`engine/notify.py` lists them all).

## ntfy's daily limit

ntfy.sh's free tier takes about 250 messages a day per internet address, and the PC's status posts already use about 220. Trade alerts are
rare (a few a day). Each one is counted. The extra status posts and the chart stop 12 messages before the limit, so they never use up the
room a trade alert needs. The main 15-minute status post still goes every run, because it is the PC's sign of life.

## Where it lives (for Claude)

- Words and numbers: `engine/notify.py` (`entry_message`, `exit_message`, `exit_context`, `instant_entry`, `instant_exit`, `ntfy_today`).
- Sending: `engine/push.py` (`pc_notify` → `_pc_send`: the phone app first, ntfy when no phone took it; de-duplicated by key).
- Routes: the bot's own NinjaTrader adapter (`engine/ninjatrader.py` `_push_fill` / `_push_exit`). A sub-account's adapter notifies under
  its own name and key through `push_as`, set by `engine/account_b.py` (ATLAS, key `:acctb`; the Rapid's ATLAS lane `:acctr`) and
  `engine/multi_account.py` (extra accounts and the Rapid's LIT lane, key `:<id>`). Before 2026-11-20, ATLAS on NinjaTrader sent **no**
  instant entry or stop / target exit: it skipped its own because the adapter "reports fills", and its adapter never sent one.
  Exits on any account reached ntfy only with the 15-minute report.
- Budget: `tools/pc_report.py` (`TRADE_ALERT_RESERVE`, `day_used`).
- Tests: `python -X utf8 -m tests.test_trade_alerts` (fake fills through every route: exactly one entry and one exit, the right name and $),
  `tests.test_notify`, `tests.test_webpush`.
