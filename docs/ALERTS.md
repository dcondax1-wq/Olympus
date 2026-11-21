# Phone alerts: Telegram / Discord first (engine/alert_bus.py, 2026-11-21)

One `send(event)` for every alert. Order: **Telegram -> Discord -> private ntfy -> the Olympus app (Web Push)**; the first one
that gives a receipt wins. Entries, exits and "bot stopped" also go to a second channel. Status posts stay on ntfy's public
topic, so alerts no longer share its 250-a-day cap. Messages you send to the bot are ignored (no commands, no trading).

| What | Where |
|---|---|
| Setup (once) | `ALERTS_SETUP.bat` (1 Telegram, 2 Discord, 3 both) |
| Check every channel | `TEST_ALERT.bat` (prints OK / FAIL + the receipt id per channel) |
| Back to the old path exactly | `ALERTS_OFF.bat` (undo: `ALERTS_ON.bat`) |
| Secrets | `%USERPROFILE%\.olympus\alerts.json` only (never the repo, never printed) |
| Failure log | `data\alert_bus.jsonl` (redacted) |
| Cloud "PC silent" | repo secrets `LE_TG_TOKEN` + `LE_TG_CHAT` and / or `LE_DISCORD_WEBHOOK` (optional) |

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

Both: type `3` in step 5 / 4 and do both. Then double-click **TEST_ALERT.bat** once.
