# Phone notifications: every trade, in Olympus on your iPhone

Owner, 2026-11-19: "I want notifications on my phone." Since 2026-11-19 your PC sends them straight to the **Olympus** app on your
iPhone (https://dcondax1-wq.github.io/jarvis/, opened from the Home Screen). No cloud, no GitHub, nothing to copy, free.

## Turn it on (2 taps)

1. Open **Olympus from your Home Screen** (not a Safari tab; iOS 16.4 or later). Not there yet: open the link in Safari, tap
   **Share**, **Add to Home Screen**, **Add**, then open Olympus from the Home Screen.
2. On the home, under the ZEUS card, tap **Allow notifications**, then **Allow** on the iPhone's question.

Within about 5 minutes your PC sends **"Olympus notifications are on"**. The card then says **Notifications on**, with
**Send a test** (your PC answers within 5 minutes) and **Turn off**. The PC must be on (it is, for the bots).

## What you get

| When | Notification (one per trade: the exit replaces the entry) | Opens |
|---|---|---|
| a real account enters a trade (Zlarior 50K, Zlarior 25K #2, ATLAS 25K funded, any extra account) | **Zlarior 50K: LONG opened** / risk $303 · target +$4,557. 6 MNQ at 24,980.25. Stop 24,955, target 25,360. 10:42 AM ET. | NQ page |
| that trade ends | **Zlarior 50K: LONG closed +$605** / Target hit · +2.0R · 10:58 AM ET. | NQ page |
| the important alerts of the PC's 15-minute report (your `notify_settings.json` types that are on: trade results, PASSED / FAILED / LOCKED / payout ready, the 16:15 day summary, the 07:30 morning brief, bot down / NinjaTrader closed / FEED STALE, and "Back to normal", which replaces its problem) | the same words as before | NQ page or Board |

Never for Paper, Sim or BLITZ. Quiet hours (23:00-07:00 ET) = the notification still comes, without sound (trade entries and
results too; ringing at night is the owner's yes / no on STATE.md, and Claude makes the change: a hand edit of the tracked
`notify_settings.json` on the PC stops its auto-update). Tap one and Olympus opens at its page. Entries and exits arrive seconds after the bot routes / sees them; the report's
alerts every 15 minutes.

## Important alerts on both apps, the rest Olympus first (2026-11-20)

The PC still has your private ntfy alert topic (the ntfy app, if you follow it: `python tools/pc_report.py --setup` on the PC prints
the topic to follow).

- **A trade's entry and result, PASSED / FAILED / LOCKED / payout ready, no trade for 5+ days (the 50K, ATLAS, the 25K #2, the Rapid EOD), the 15-minute report's
  problems (bot down, NinjaTrader closed, FEED STALE) and room low (if you turn it on) go to Olympus AND to ntfy**
  (`trade_routes: "both"` in `notify_settings.json`). Problems the PC's fast alarm already sent in the entry hours stay on ntfy
  only; "Back to normal" stays Olympus first (so a flap at night is not 4 sounds); PC silent comes from the cloud, on ntfy. Until 2026-11-20 they went to
  ntfy only when no phone "took" them, and "took" meant only that Apple's push service accepted them, not that the iPhone showed
  them. That day ATLAS's 03:45 ET entry and 07:10 ET +$514 result reached no phone; most likely (unconfirmed: the PC's push logs
  were not read) they were accepted for the one registered Olympus phone, and ntfy and the 15-minute report skipped their copies.
  So an important alert can now show twice (once per app); that is on purpose. It reaches you on ntfy only if the ntfy app follows
  your alert topic.
- `trade_routes: "olympus"` = Olympus first, ntfy only when no phone took it; `"ntfy"` = ntfy first, Olympus only when ntfy did not
  take it. Pick one once the test below shows which app works.
- **Every other alert** goes to **Olympus first**, and to ntfy **only when no phone took it** (as before).
- Once one route took an alert, the 15-minute report does not send it again. One exception: a 50K or ATLAS trade the Olympus app got
  at once but ntfy refused is retried on ntfy every 15 minutes for 2 hours. For the 25K #2 and the Rapid EOD the bot itself tries the
  ntfy alert once more a minute later, under the account's own name (the report's one LIT row could only call it "Zlarior 50K").
- Check the routes: first tap **Send a test** on the Olympus card (tests Olympus alone, from the phone). Then on the PC:
  `python -X utf8 -m engine.alert_check --test` (or PC dashboard Settings > Send test, once a minute at most): one TEST entry + close
  on each route, and what each answered (docs/TRADE_ALERTS.md "Check it yourself").

## If something is off

| Olympus says | Do this |
|---|---|
| "Add Olympus to your Home Screen first" | You are in a Safari tab: step 1 above. |
| "Notifications are blocked" | iPhone Settings, Notifications, Olympus, turn on Allow Notifications. |
| "Waiting for your PC" | The PC shares its key with its next report (every 15 min). Keep the PC on; Olympus finishes by itself. |
| "Your PC confirms within 5 minutes" for much longer | The PC's 5-minute task is not running: on the PC, `tools/bat/SETUP_SHORTCUTS.bat` (task LiquidityEngineOps). Olympus sends it again by itself every 30 min. |
| "Olympus is updating" | Swipe Olympus away, open it again from the Home Screen, tap Try again. |

If the PC's key ever changes (its file was lost), the phone notices on its next open and subscribes again by itself.

## How it works (for the curious)

- **Key**: the PC makes its own Web Push (VAPID) key once and keeps it in `data/push.json` (gitignored, never printed, never
  posted). Its **public** half, the PC's box key (`data/push_pc_key.json`) and short ids of the phones it has ride the PC's
  15-minute status post as `wp` (`engine/push.app_block`, ~230 bytes, inside the post that already goes out: no extra ntfy post).
- **Phone**: `tools/web_public/jarvis/push-ui.js` subscribes with that key and seals the subscription to the PC's box key
  (P-256 ECDH + HKDF-SHA256 "le-push-sub-v1" + AES-GCM, only that PC can open it), then posts it to the free relay topic
  (`tools/web_public/push_relay.json`). Send a test / Turn off are sealed too, proved with the phone's own subscription secret.
- **PC intake**: the 5-minute ops task already reads the relay (`engine/alerts_plus.ops_tick`) and hands the phones' messages to
  `engine/push.intake`: at most 5 phones in `data/push.json` "devices", one welcome push to a new one, a phone the push service
  calls gone (deleted, another key) is dropped. The PC never posts on the relay (ntfy's free daily budget stays for the reports).
- **Sending**: `engine/push.pc_notify` (every real-account entry and exit: LIT, ATLAS, the extra accounts), `tools/pc_report.py`
  (the report's alerts) and `pc_send_now` (tests) push with the built-in RFC 8291 / 8292 sender (`cryptography`; pywebpush if
  installed). Other PC notices (pre-session check, ops helper, armed setups) stay off the phone unless `LE_PUSH_EXTRA=1`; they
  never went to ntfy either. Without `cryptography` nothing changes: no key, no card progress, every alert goes to ntfy.
- **Worker**: `tools/web_public/jarvis/push-sw.js` (imported by `jarvis/sw.js`) shows each push (one tag per trade and account:
  the exit closes the entry's notification), opens Olympus at the NQ page or the Board, and turns a critical alert's tap into
  the relay "Got it".
- Tests: `python -X utf8 -m tests.test_webpush` (PC: key, intake, send to a mocked endpoint, trades on both routes, report, no
  `cryptography`), `flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_jarvis_push` (the card, the button, the
  worker, a real push event), `python -X utf8 -m tests.test_push` (the payloads and the encryption).

## ntfy alerts, short and $ first (2026-11-17)

One settings file: `notify_settings.json` (repo root): each type on / off, quiet hours (default 23:00-07:00 ET: no sound, except
PC silent, account status, room low and problems), milestones, summary time. Code: `engine/notify.py`; tests: `python -X utf8 -m tests.test_notify`.

**Default since 2026-11-18 (owner: "important only", then "notifications when we get in a trade in any account" the same
evening)**: ON = trade opened, trade closed (the result), account_status (PASSED, FAILED, LOCKED, LOST, target reached, payout
READY, and since 2026-11-20 "no trade for N days" (5+ days, per account: the 50K, ATLAS, the 25K #2, the Rapid EOD; MFFU can close
an account after 7 days without a trade, and a funded one then loses ALL its profits; the count knows only the bot's own trades;
before it was "other", off), the daily summary, the 07:30 morning brief, PC silent, problems (bot down, FEED STALE, NinjaTrader closed). OFF = 25/50/75 %
milestones, room low, other. Trade opened / closed ring in quiet hours only when they are in `ring_in_quiet_hours`. To turn one back
on, tell Claude: Claude changes `notify_settings.json` in the repo (a hand edit on the PC stops the auto-update). The PC
ops task's critical alerts that repeat until "Got it" (unprotected position, KILL fired, drawdown left, engine/alerts_plus.py)
do not go through these settings and still ring.

| When | Example |
|---|---|
| trade opened | `Zlarior 50K SHORT opened \| risk $368 \| target +$1,432` |
| trade closed | `Zlarior 50K closed +$605 \| day +$605 \| room $1,750` |
| eval progress (25 / 50 / 75 / 100%) | `Zlarior 50K: 50% of the target made ($1,500 of $3,000)` |
| room low (50 / 75% used) | `ATLAS 25K: room getting low, $250 left of $1,000` |
| 16:15 ET day summary | `Day Mon Nov 16: +$310` / `Zlarior 50K: +$420 today, $2,580 to pass, room $1,800 of $2,000; ... Tomorrow (Tue): CPI m/m 08:30.` |
| 07:30 ET morning brief (`morning_brief`, ON) | `ZEUS - Wed Nov 18 - PC ok` / `Zlarior 50K $49,193 ($3,807 to pass) · 25K #2 $25,000 ($1,500 to pass) · ATLAS 25K funded $25,000 ($2,100 to payout)` / `Overnight: no trades · Today: Zlarior till 15:30, ATLAS till 12:00 · CPI m/m 08:30` / `Edge: GREEN · Needs you: none` (trading days only, once; also on the Board; tools/morning_brief.py) |
| **setup getting closer** (`setup_progress`, ON since 2026-11-25; engine/setup_progress.py) | `Zlarior LONG 1m CISD wait 7/10` / `LONG limit 27,784 was tapped at 06:09: waiting for a 1-minute CISD close (until about 06:31) to enter; stop 27,735.25. Also on: Zlarior 25K #2.` LIT at the Brain's step 5 (5m CISD), 7 (limit tapped) and 8 (entering now), and `setup cancelled: <why>`; ATLAS `ATLAS S/R: 25 pts from PDH` (30 and 10 pts) and `ATLAS EMA ARMED`. At most 12 a day; 23:00-07:00 ET only "entering now" comes. Off: `"setup_progress": false` in notify_settings.json (Claude changes it) |
| **PC silent** (the cloud, PC off is fine) | `Your PC stopped reporting at 09:14 ET. Check it: STOP BOT, START BOT.` once, one reminder after 2 h, `PC reporting again` when back |

The PC silent check is a step of the cloud monitor (`tools/pc_silent_check.py`, every run: about every 30 min on weekdays
01:30-16:00 ET). It reads the heartbeat branch and the PC's posts on the status topic; silent = neither is newer than 20 min.
It pushes to your private ntfy topic when the GitHub secret **LE_NTFY_TOPIC** holds it (GitHub -> Settings -> Secrets and
variables -> Actions -> New secret, the topic name your ntfy app follows); without it the plain alert (no $, no names, no ids)
goes to the public status topic.

**Within 2 minutes from the PC itself (2026-11-20, type `problems`, ON, rings in quiet hours; research/writeups/
nq-live-reliability-2026-11-20.md).** The bot on a broker account in the entry hours (weekdays 01:58-15:55 ET, CME open):
`ZEUS not polling` (no good poll for 90 s, or its poll thread died), `FEED STALE` (the 1m NinjaTrader feed 2 bars behind, or the
bot blocked entries for it), `Bot stopped` (3 min after a server start it is still stopped although nobody pressed Stop), each
once with one `Back to normal` (engine/fast_alarm.py, run by the server's watchdog every 30 s; `LE_FAST_ALARM=0` = off). And
`MISSED TRADE · Zlarior 06:12 ET: <why>` the moment the bot's own model took an entry it did not route (feed stale, seen late,
size 0, a guard, a gap, a restart; never for your own pause; engine/fill_audit). The 15-minute report then skips its own copy of
the same problem (engine/notify.problem_dup): one alert, one phone.

---

## History: the old Home Screen app (gone since 2026-11-08)

Until 2026-11-08 the notifications went to the old Liquidity Home Screen app on dcondax1-wq.github.io, with keys handed
out by a GitHub Actions cloud monitor. That GitHub account was suspended, so the site, the cloud monitor and the key hand-off are
gone; the text below is kept only as a record (`engine/push.py` keeps that code for its tests, the PC no longer uses it).

### What the old app showed

**What you get.** Your Home Screen app (Liquidity, https://dcondax1-wq.github.io/) shows:

| When | Title | Text |
|---|---|---|
| a trade is entered | `LONG · MFFU 50K` | `Entered 4 MNQ` |
| the trade ends (the same notification is replaced) | `LONG · MFFU 50K` | `+$1,812` (win), `−$366` (loss), `$0 breakeven`, `+$212 closed 15:55` |

The account name says who traded: **Paper** = the cloud paper bot (PC off), the NinjaTrader account (for example
**Sim101**) = the PC bot, the name in `live_model.json` `"account": {"name": ...}` (default **MFFU 50K**) = a real account.
Each trade is notified once, even when the cloud and the PC both trade it. One more notice is pushed: **PC bot silent**
(the cloud saw no heartbeat from the PC bot during 01:50-16:30 ET on a weekday, checked on its half-hourly runs).
Eval-timing changes appear only in the app's **Activity** page (System -> Activity, and a card on Today), next to every
entry and result with its details (prices, stop, target, R, eval balance). The app icon shows a badge with the new ones.

**From the PC's helper task** (`tools/bat/SETUP_SHORTCUTS.bat` adds the task `LiquidityEngineOps`, `engine/ops_checks.py`; each
notice once, tagged "ops"): **All green for tonight** or **Fix before 02:00 ET: ...** at 01:40 ET, a **Day summary** at
16:05 ET (trades, P&L, $ to go, session X of 10), a **Week** report on Sunday evening, **Internet was down N min** /
**NinjaTrader disconnected** / **reconnected**, the MFFU **no trade for 5 days** reminder, **EVAL PASSED** / **Eval failed**
with the next steps, and the **contract roll** reminder a week and a day before. They need the PC linked (below) and the
PC on; `LE_OPS_PUSH=0` turns them off. Daily routine: `docs/DAILY_CHECKLIST.md`.

**Before the trade, and alerts you can't miss** (`engine/alerts_plus.py`, 2026-10-21):

| When | Text |
|---|---|
| the LIT limit arms | `LIT setup armed: LONG limit 29,842 · stop 29,807.5 · target 30,118 · ~6 micros ($414 risk) · valid until 03:15` |
| the limit is tapped (the 1m-CISD wait starts) | `LIT setup armed: LONG limit 29,842 tapped, waiting for a 1m CISD · ... · valid until 03:20` |
| it lapses without a fill | `Setup expired — no fill` |
| **critical** (repeats every 10 min, at most 6 times, until you tap **Got it** or it clears by itself) | Surface offline (cloud), FEED STALE, position mismatch / flatten by hand, kill switch fired, eval room below $400, clock drift, bot update failed |
| the cloud monitor has not published for 45+ min (weekdays 02:15-16:30 ET; pushed by the PC) | `Cloud monitor has not run for 52 min`, later `Cloud monitor back` |
| the PC and the cloud run different LIT rules (once per difference) | `PC and cloud run different rules: PC a1b2c3 / cloud d4e5f6 — update the Surface` |
| a second strategy (EMA / MACD / S/R, **paper only**, engine/second.py) enters or exits on paper (cloud; kind `second`, Settings → Alert levels "Second strategies (PAPER)") | `PAPER EMA LONG: Paper entry 7 MNQ at 29,800.25, stop 29,764, target 29,930. Not traded.` then `PAPER EMA LONG TARGET: +$912 on paper (+1.83R). Not traded.` |

**Got it**: tap the notification (it opens System → Alerts to acknowledge) and tap the big **Got it**; Android also shows a
Got it button on the notification itself. The app posts the acknowledgement to the same free relay; the PC's ops task
(every 5 min) and the cloud monitor (every run) read it and stop repeating. When the problem clears by itself, one quiet
"Resolved" notice replaces the alert. **Levels**: Settings → Alert levels, per kind **On** / **Silent** (no sound, no
repeats) / **Off** (not pushed). A red banner on every page shows open critical alerts; a yellow one says when the cloud
monitor is stale while the PC's live feed keeps the app fresh. The PC's critical alerts need the ops task (SETUP SHORTCUTS)
and the heartbeat; the cloud repeats the Surface-offline alert on its own runs (every 30 min, more often while a setup is
armed). Tests: `python -X utf8 -m tests.test_alerts_plus`.

Free. Telegram and Discord are off.

How fast: the cloud paper bot checks every 30 minutes on market days (02:00-16:25 ET), so its notices arrive up to ~30
minutes after the fill (GitHub can add a few minutes). The PC bot's arrive a few seconds after the fill.

Paper only, as always: notifications never place or change an order.

### Setup of the old app (gone)

You need iOS 16.4 or later, and the app must be opened **from the Home Screen** (notifications do not work in a Safari tab).

1. If the app is not on your Home Screen yet: open the link above in Safari -> **Share** -> **Add to Home Screen** -> **Add**,
   then open **Liquidity** from the Home Screen.
2. On **Today**, tap **Turn on** in the "Get a notification for every trade" card (or System -> Settings -> **Turn on
   notifications**), then **Allow**.

Done. The app tells the cloud bot by itself. Its card says **waiting for the cloud** until the next cloud run (market days,
every 30 min) and **on** after it. If you allow notifications on a weekend, open the app once on Monday so it can remind
the cloud (the relay forgets after about 12 hours; the app re-sends by itself whenever it opens until the cloud has it).

Optional check: GitHub -> **Actions** -> **cloud-monitor** -> **Run workflow** -> tick **Send a test notification**.

The PC bot (optional) links by itself too, as long as its heartbeat is on (`LE_HEARTBEAT=1`, the always-on PC setup): the
next cloud run hands it the notification key, sealed so only that PC can open it. PC dashboard -> Alerts -> Phone app
notifications shows **linked** and has a **Send test** button.

---

### When something is off

| The app says | Do this |
|---|---|
| "On iPhone, notifications work in the Home Screen app" | Open Liquidity from the Home Screen, not from Safari. |
| **blocked** | iPhone Settings -> Notifications -> Liquidity -> Allow Notifications, then tap Turn on again. |
| **waiting for the cloud** for more than a market day | Open the app again (it re-sends); check that the cloud-monitor workflow runs (Actions tab). |
| **tap to finish** | Tap Turn on once more (the phone wanted a tap to finish the subscription). |

If the cloud's key ever changes (its cache is lost), the app subscribes again on its next open, by itself.

### Settings you can change (optional)

| What | Where |
|---|---|
| Account name in the notices | `live_model.json`: `"account": {"name": "MFFU 50K", "paper": "Paper"}` |
| Also push eval-timing / NinjaTrader trouble (PC-silent is always pushed by the cloud) | repository variable `LE_PUSH_EXTRA` = `1` (PC: start the server with `LE_PUSH_EXTRA=1`) |
| Your own key instead of the automatic one | GitHub Secret `LE_VAPID_PRIVATE` (make one with `python tools/push_keys.py`); phones re-subscribe by themselves |
| Telegram / Discord back on | repository variable `LE_ALERTS_CHAT` = `1` (PC: `LE_ALERTS_CHAT=1`, or `"alerts": {"chat": true}` in `live_model.json`) |

Secrets live at https://github.com/demetrades2000-coder/nq-liquidity-engine/settings/secrets/actions (variables: the
Variables tab next to it). None is needed for the normal setup.

### How it works (for the curious)

- **Relay**: a free ntfy.sh topic named in `tools/web_public/push_relay.json` (not secret). When you allow notifications the
  app posts its push subscription there. A subscription alone cannot send anything: sending needs the private key.
- **Key**: with no `LE_VAPID_PRIVATE` secret, the workflow makes a key pair on its first run and keeps the private key in the
  GitHub Actions cache (`.le_push/vapid.json`, refreshed every run; never committed, never printed). The public key goes
  into data.json, the app subscribes with it.
- **Cloud** (`tools/cloud_monitor.py`): every run reads the relay, keeps the subscriptions in `state.json` on the private
  `dashboard` branch, and sends an entry notice for each new fill and an outcome notice for each finished trade (nothing
  older than 2 days). Keys already sent are kept in `state.json`; a "sent" marker on the relay tells the PC.
- **PC** (`engine/live.py`, `engine/ninjatrader.py`): the heartbeat publishes the PC's own public key
  (`data/push_pc_key.json` holds the private part, gitignored); the cloud seals the notification key to it in `state.json`;
  the PC opens it and sends the same two notices (NinjaTrader: when NinjaTrader reports the fill and when the bracket's stop
  or target fills). Before sending it checks the relay, so a trade the cloud already notified is not sent twice (and the
  other way round). Same notification tag per trade, so at worst a notice is replaced, never doubled.
- **App** (`tools/web_public/index.html`, `sw.js`): shows each push, counts it on the badge, opens the app at the trade when
  tapped, and keeps the subscription current on every open.
- Tests: `python -X utf8 -m tests.test_push` (payloads, relay, keys, de-dup, encryption).
