# Phone alerts in 1 minute (no Telegram, no Discord, no keys)

Since 2026-11-22 the PC sends every important alert with ZERO setup to two places: the **Olympus app** on your Home Screen and
your **private ntfy topic** (the PC makes it by itself, once). You only tell the phone to show them:

1. iPhone: open **Olympus from the Home Screen** -> tap **Allow notifications** -> **Allow**. (That is enough.)
2. Backup, optional: App Store -> **ntfy** (free) -> open it -> **+** -> type the topic that **tools/bat/TEST_ALERT.bat** prints on the PC
   (looks like `nq-amber-falcon-river-7291`) -> **Subscribe**.
3. On the PC: double-click **tools/bat/TEST_ALERT.bat** (or TRADE_HOME -> **T**). Each channel says **OK** or **FAIL** + what to do.

What buzzes (engine/alert_map.py; `python -X utf8 -m engine.alert_map` prints this live):

| Event | Goes to (no setup) |
|---|---|
| Bot stopped / crashed in trading hours | Olympus app + ntfy, rings at night |
| An account NOT armed after START (checked 90 s after START, and 17:30 / 01:15 / 08:45 ET) | Olympus app + ntfy |
| Entries blocked: PC clock off, feed stale, NinjaTrader not connected, kill switch | Olympus app + ntfy |
| Trade entry ($ risk, $ at target) and exit ($ result, today, $ to pass), every account | Olympus app + ntfy |
| Daily loss limit 70% used; max drawdown 50% / 75% used; open trade into a halt; trade with no stop | Olympus app + ntfy |
| Payout can be requested (after the close: $ + the MFFU clicks; record it with TRADE_HOME -> P); PASSED / FAILED / LOCKED | Olympus app + ntfy |
| Builder payout #4 taken: do NOT take #5 (live move); a Rapid day near the $10,000 live line | Olympus app + ntfy |
| MFFU 7-day no-trade deadline (day 5+) | Olympus app + ntfy |
| Update failed / rolled back | Olympus app + ntfy |
| Update applied / skipped, other low-priority news | ONE silent daily digest at 16:20 ET |
| PC silent (the cloud notices the PC stopped) | needs ONE repo secret `LE_NTFY_TOPIC` = your topic (the cloud cannot know it) |

- **No spam:** one alert per event (same key = sent once, also after a restart); a soft notice (keep-alive line) = one channel only.
- **Quiet hours** (23:00-07:00 ET): ordinary alerts arrive without sound; bot stopped / problems / account status / room low still
  ring. Trades at night: silent until you say yes (STATE.md). All-day sound: `{"quiet_hours": {"off": true}}` (tell Claude).
- **Privacy:** the topic is random words + digits, never your PC name or an account id, kept only in
  `%USERPROFILE%\.olympus\ntfy.json`, never in the repo or a public post.
- Telegram / Discord (below) are optional extras: when set up they go first, ntfy and the app stay the backups.

## Test from your phone, PC off is fine (day-notify 2026-11-23)
GitHub app (or github.com in Safari) -> **dcondax1-wq/olympus** -> **Actions** -> **Send me a test alert** -> **Run workflow** -> **Run workflow**.
Within ~1 minute: "TEST: Olympus alerts work 4:05 PM ET" on ntfy (and Telegram / Discord when set up). The run turns **green** when it
reached you, **red** when not (open it: one table, each channel ok / failed + what to fix). Needs the repo secret `LE_NTFY_TOPIC` and the
workflow file on `main` (research/handoff/2026-11-23/day-notify/LEAD_WIRES.md). It cannot test the Olympus app (only your PC can push
there): that is the app's own **Send a test** button. After each PC update you also get ONE "Update installed, alerts OK".

# Phone alerts: Telegram / Discord first (engine/alert_bus.py, 2026-11-21)

One `send(event)` for every alert. Order: **Telegram -> Discord -> private ntfy -> the Olympus app (Web Push)**; the first one
that gives a receipt wins. Entries, exits and "bot stopped" also go to a second channel. Status posts stay on ntfy's public
topic, so alerts no longer share its 250-a-day cap. Messages you send to the bot are ignored (no commands, no trading).

| What | Where |
|---|---|
| Setup (once) | phone: PC link + `:8444/alerts/` (Telegram), or `ALERTS_SETUP.bat` (1 Telegram, 2 Discord, 3 both) |
| Check every channel | `tools/bat/TEST_ALERT.bat` (prints OK / FAIL + the receipt id per channel) |
| Back to the old path exactly | `tools/bat/ALERTS_OFF.bat` (undo: `tools/bat/ALERTS_ON.bat`; off also stops the zero-setup copies of readiness / update alerts) |
| Secrets | `%USERPROFILE%\.olympus\alerts.json` only (never the repo, never printed) |
| Failure log | `data\alert_bus.jsonl` (redacted) |
| Cloud "PC silent" | repo secrets `LE_TG_TOKEN` + `LE_TG_CHAT` and / or `LE_DISCORD_WEBHOOK` (optional) |

## From your phone (no PC needed, 2 minutes)
1. iPhone: open your PC link with `:8444/alerts/` at the end (`https://<pc>.<tailnet>.ts.net:8444/alerts/`; on the PC itself `http://localhost:8766/alerts/`).
2. Tap **Open BotFather** -> **Start** -> send `/newbot` -> name `Olympus Alerts` -> a username ending in `bot`.
3. BotFather answers with a long token: long-press it -> **Copy** -> back to the page -> **Paste** -> **Connect**.
4. Tap the big **Open @your_bot and tap START** button -> **START** in Telegram (within 3 minutes).
5. The page says **Connected: test delivered** (or one plain reason + the fix). Saved on the PC only, same file as ALERTS_SETUP.
6. Tailscale devices only (`engine/alerts_box.py`); **Send a test alert** there = tools/bat/TEST_ALERT.bat. No sound: iPhone Settings -> Notifications -> Telegram.

## Telegram, 2 minutes (recommended)
iPhone:
1. App Store -> **Telegram** -> Get -> open -> sign in with your phone number.
2. Telegram -> Settings -> **Devices** -> **Link Desktop Device** (the camera opens).

PC:
3. Open **web.telegram.org** in the browser -> scan its QR code with that iPhone camera.
4. In web Telegram search **BotFather** (blue tick) -> Start -> send `/newbot` -> name `Olympus Alerts` -> username e.g.
   `olympus_alerts_7731_bot` (must end in `bot`). BotFather answers with a long token: select it -> Ctrl+C.
5. Double-click **ALERTS_SETUP.bat** -> type `1` -> Enter -> right-click to paste the token (nothing shows: that is normal) -> Enter.

iPhone:
6. In BotFather's answer tap the link `t.me/olympus_alerts_..._bot` -> **START** (within 3 minutes).
7. The PC says `Telegram test: delivered`; your phone buzzes. iPhone Settings -> Notifications -> Telegram -> Allow + Sounds on.

## Discord, 2 minutes
iPhone:
1. Discord app -> **+** (left bar) -> Create My Own -> For me and my friends -> name `Olympus` -> Create.
2. iPhone Settings -> Notifications -> Discord -> Allow. In Discord long-press the Olympus server -> Notifications -> **All Messages**.

PC:
3. **discord.com/app** in the browser (same login) -> Olympus server -> hover `#general` -> gear (Edit Channel) ->
   **Integrations** -> **Webhooks** -> New Webhook -> click it -> **Copy Webhook URL**.
4. Double-click **ALERTS_SETUP.bat** -> type `2` -> Enter -> right-click to paste (hidden) -> Enter -> `Discord test: delivered`.

Both: type `3` in step 5 / 4 and do both. Then double-click **tools/bat/TEST_ALERT.bat** once.
