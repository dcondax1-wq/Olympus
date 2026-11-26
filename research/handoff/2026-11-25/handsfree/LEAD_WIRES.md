# day-handsfree (2026-11-25): lead wires

Branch `day-handsfree` = pc 94341394 + origin/day-zerotouch2 round 2 (43307f53, merged: one conflict in engine/autoupdate.py run_update
rollback unpark, kept zerotouch2's stash-identity version; .gitignore both sides) + this work. Helper did NOT touch sw.js,
build_web_dashboard.py, jarvis/apps.js or the olympus.js APPS table. Bot-side code: land after-hours after the red team.

Nothing to wire for the engine side. Optional:
1. pc/control.html got one line (#tgHint) about Telegram: no new file, no precache change.
2. docs/OLYMPUS_MAP.md row for PC Control (from zerotouch2 LEAD_WIRES) can add `tests.test_handsfree`.

Red team, look at:
- engine/tg_cmd.py is_owner (private chat, chat.id == from.id == alerts chat_id) and parse_text allow-list.
- remote_ctl._one refactor (control branch + inbox + Telegram share it; test_remote_ctl 74/74, test_remote_notice 20/20).
- '/update force' = self_heal.park_local(force=True): only via Telegram (RemoteControl._via_tg), parks live_model*/second_model/
  rule files with git stash; rollback pops it back (zerotouch2 round 2 path).
- self_heal.PARK_DATA_OK (tracked market data under data/ parkable; journals never).
- ns_sync copies LE_TickRec.cs into NinjaTrader's AddOns (outside 01:50-16:00 ET weekdays, flat); unverified that NT8 compiles on
  its own: the LE_BUILD handshake reports it either way (one "F5 once" line per build).
- getUpdates consumes the bot's updates: if anything else ever polls the same bot (nothing in the repo does), they compete.
