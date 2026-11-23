# night-notify: lead wires (2026-11-22)

No lead-only file was touched (sw.js, build_web_dashboard.py, jarvis/apps.js, APPS table: untouched). Nothing to wire.

Optional, owner/lead (hands-only, a repo secret Claude cannot set): `LE_NTFY_TOPIC` = the PC's private topic (TEST_ALERT.bat
prints it) in the Olympus repo's Actions secrets, so the cloud's PC-SILENT alert reaches the ntfy app. Without it the cloud posts
the plain alert to the public status topic only (engine/alert_map.py row `pc_silent`, the one remaining gap).

Behaviour changes to know before landing:
- notify_settings.json `room_low` ON (+ in notify.IMPORTANT): daily loss limit 70% and drawdown 50% / 75% now reach the phone.
- readiness NOT READY, the fast alarm and update failed / rolled back: with no Telegram / Discord they go to ntfy AND the Olympus
  app (alert_bus.send_critical); before, readiness and update alerts reached no phone (kind 'ready' / 'pc' dropped by pc_app_ok).
- "update skipped" / "update applied" -> the daily digest (16:20 ET, silent), no longer a buzz.
- tools/pc_report.py makes the private topic on its first real run when the PC has none.
