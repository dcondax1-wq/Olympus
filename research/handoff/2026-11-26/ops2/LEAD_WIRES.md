# day-ops2 (2026-11-26): lead wires

Branch day-ops2 off origin/pc 18312c55. Paper only; nothing arms or orders. Helper did NOT touch sw.js, build_web_dashboard.py,
jarvis/apps.js or the olympus.js APPS table. Nothing to wire. Land after-hours after the red team (bot-side + NinjaScript files).

Red team, look at:
- ninjatrader/LE_Feed.cs SHADOW mode (le_feed_mode.txt): bars + status to le_feed\shadow, hub covers nothing, no accounts.csv;
  a mode change re-requests every series into the new folder. Compiled + driven with mono stubs (test_le_feed_cs, new scenario).
  Still UNVERIFIED against the real NinjaTrader API (as LE_Feed always was): shadow mode is exactly what proves it safely.
- engine/roll_auto.py gates: switch to live only after MATCH_DAYS=2 equal finished days (>= 300 overlapping 1m bars, <= 0.5%
  different), outside 01:50-16:00 ET weekdays, flat; fallback to shadow when live and the status is > 10 min old while
  NinjaTrader runs. An LE_Feed already feeding (owner's no-chart mode) is never touched; an old installed one is shadowed
  before ns_sync updates it (ns_sync._one + roll_auto prep).
- Roll day: tickrec.front_names and LE_TickRec.FrontName now `<` (ON fri3-8) = nt_instrument; TickRecDriver updated (Sep 10 now
  tries 12-26 then the expiring 09-26).
- scripts/nt_off_onedrive.ps1 (not run here: Windows only): pin always; move only with -Move, NinjaTrader closed, not in trading
  hours, flat; robocopy + count/size compare; rename (backup kept) + mklink /J; puts it back if the junction fails; -Undo.
  Honest caveat in the doc: if OneDrive syncs the junction anyway, run undo.
- engine/pc_backup.py: Fernet key in .olympus/backup.key (never in the backup, never sent); the recovery code is shown on the PC
  screen by START only. Never backs up auto_resume.json / autostart.json. Restore: SHA-256 manifest, no traversal, no tracked file.
