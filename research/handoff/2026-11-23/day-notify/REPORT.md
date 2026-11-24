# day-notify (2026-11-23): does an alert ACTUALLY reach the iPhone?

## Every route a push can take, today

| Route | Sender | Set up today | Missing |
|---|---|---|---|
| Olympus app (Web Push) | the PC only (subscription sealed to the PC's key) | YES: the PC's key is in its status post and **1 phone** is registered | Nothing, but only while the PC is on. The cloud can never push to it. The app's **Send a test** button tests it. |
| ntfy, private topic | the PC (topic made by itself, zero setup) | the PC has it and sends every critical alert there | Unknown whether the ntfy app on the iPhone **follows** it (STATE.md owner to-do "Phone alerts, 1 minute" still open) |
| Telegram / Discord (alert bus) | PC + cloud | **NO**: the bus is off until ALERTS_SETUP.bat (board still lists the BotFather to-do) | optional; not needed |
| GitHub Actions pc-watch (PC silent) | the cloud, PC off | file exists on `pc` only | **Never ran: 0 workflows registered** (default branch `main` = README only). Needs pc-watch.yml on `main` + secret LE_NTFY_TOPIC |
| GitHub Actions cloud-monitor (PC silent step + paper monitor) | the cloud | file exists on `pc` only | Same: never ran on Olympus. Heavy (~1,300 min/month) + another account's deploy key |
| secret LE_NTFY_TOPIC | for both cloud jobs | cannot be read from here | The first tap of the new test tells: receipt "to: private" = set, "status topic" = not set |

Live hint this morning: the PC was silent 73 min at 11:26 ET (last report 10:12 ET) and no cloud alert could exist, because no
workflow runs.

## Built
1. `tools/alert_test.py` + `tests/test_alert_test.py` (18/18, fake ntfy / fake bus): the cloud test alert "TEST: Olympus alerts work
   4:05 PM ET", same channels as a real cloud critical alert, read back from ntfy by id, receipt (ok / failed per channel) to the public
   status topic as kind `le-alert-test`, job red when it did not reach an owner channel. The workflow file is in LEAD_WIRES.md.
2. `engine/post_update_check.py`: after an update restart (today's 16:00 landing included) ONE push **"Update installed, alerts OK"**
   (all checks green), through alert_bus.send_critical (ntfy + the Olympus app with zero setup), waiting for the receipts
   (logs/post_update.json "receipts", TRADE_HOME line unchanged). At most one OK push per ET day (a 2nd update = digest line); a FIX
   always goes; ALERTS_OFF = the old path. tests/test_post_update_check 33/33 (8 new, fake bus).

## Caveat
A site-only update (docs / phone pages only) does not restart the bot, so it sends no post-update push. Tonight's landing changes
engine code, so it restarts.
