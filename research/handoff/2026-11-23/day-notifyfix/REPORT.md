# day-notifyfix (2026-11-23): the remote 'status' that reached no phone

## What the cloud can see (evidence)
| Link | Result |
|---|---|
| Command on `olympus/control` | there: `status-1795473351-claude`, commit e4554431 at 17:35:51 ET (ts = commit time; it expires 15 min later, 17:50:51) |
| Remote control switched on | yes by default: `scripts/run_bot.ps1:60` sets LE_REMOTE=1; control_source follows update_source.json -> remote `olympus`, branch `control` |
| PC online | yes: the public status feed posts every 15 min (18:45 ET: server + NinjaTrader up) |
| PC read the command? | **cannot be known from the cloud**: the public feed carried no remote-control block at all (0 of 72 posts in 12 h), and the heartbeat stays on the PC (logs/pc_hb; no heartbeat branch on olympus) |
| Where the answer would go | Telegram / Discord: not set up. So 2 channels: the PC's private ntfy topic + the Olympus app (Web Push) |
| Olympus app | 1 phone subscribed (`wp.d` = one id, still listed at 18:45, so Apple did not call it gone). Not provable that this id is the iPhone |
| ntfy private topic | made by the PC; whether the iPhone's ntfy app follows it is unknown (most likely NOT: nothing ever had the owner subscribe) |

Most likely broken link: the answer went to the private ntfy topic that no phone follows, and the single Web Push subscription is either not the
iPhone or silently dead (iOS can keep a Home Screen app's subscription "valid" while it shows nothing). Second possibility: the PC never
fetched the control branch inside the 15-minute window (git credentials on the PC). Until this fix nothing showed which.

## Fixed in code (branch day-notifyfix)
1. A remote command's phone answer now goes through EVERY channel the PC has (Telegram, Discord, ntfy AND the Olympus app: need = all), not
   "the first that answers", and it is kind `remote`, so a notify_settings type switch can never drop it (`engine/remote_ctl.default_notify`).
2. The per-channel receipt is recorded (`remote_done.json` last.notice: "ntfy ok, the Olympus app FAILED (no phone)").
3. The PC records the control commit it last read (`seen`, written only when it changes, not every minute).
4. All of it rides the public feed as a small `rc` block (first in the ext post; id, status, time, seen commit, notice line; no topic,
   token or URL): `tools/pc_report.rc_block`. Next time `python -c "import tools.board as b; print(b.fetch_lite().get('rc'))"` answers
   "did the PC read it, and where did the answer go" from the cloud.

Tests: `tests/test_remote_notice.py` (20 checks, fake transports), remote_ctl 74/74, alert_bus 86/86, alert_map 62/62, alert_proof 25/25,
alert_drill 100/100, board 56/56, pc_report_sign 21/21, feed_accounts 25/25; smoke 11/11. Area `pc` now runs `remote_notice`.
(test_jarvis_push 10/11: its one failure is "playwright available", the browser check, not this change.)

## Owner steps (one route, the most reliable on iPhone: the free ntfy app)
Why ntfy: a native iPhone app with Apple push, works with the phone locked, needs no Home Screen web app (iOS Web Push for Home Screen
apps is the flakiest route: subscriptions die silently), no account, no token, and the PC already sends every critical alert AND
every remote answer to its private ntfy topic.
1. iPhone: App Store -> install **ntfy** (free) -> open it -> Allow notifications.
2. PC: double-click `tools\bat\TEST_ALERT.bat`. It prints `ntfy app -> + -> topic <your words> -> Subscribe` (on the PC screen only).
3. iPhone ntfy app: tap **+**, type that topic exactly, tap Subscribe.
4. PC: double-click `TEST_ALERT.bat` once more: the phone buzzes "TEST: ...". Done.
