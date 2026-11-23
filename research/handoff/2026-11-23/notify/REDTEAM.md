# Zero-setup alerts red team (2026-11-23): night-notify dfce5661e -> night-notify-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | Update-failure storm: engine/autoupdate keys each attempt by its epoch ("auto:update:failed:<t>") and the server retries hourly outside trading time (only "skipped" is silenced hourly). Before this commit those alerts reached no phone by default; now each one buzzes ntfy + the Olympus app: a failure that keeps happening = a buzz every hour all night / weekend (test: 12 alerts in 12 h) | MED | alert_bus.day_key() inside send_critical: same status + same title = one alert per ET day; a different failure still goes at once (autoupdate.py not edited: helper rule) |
| 2 | An auto-made topic nobody subscribes to is not a phone route, but the PC card then said "nothing to do" and TEST_ALERT said ntfy "delivered" (ntfy accepts any topic) | LOW/MED | card NEXT line: "ntfy app -> + -> topic ... -> Subscribe, then TEST_ALERT" until a test went out; TEST_ALERT words ntfy as "sent to your private topic (shows only on a subscribed phone)" and marks the topic tested |
| 3 | Topic entropy is 34.1 bits (122 words^3 x 10^4), the comment says 36 | LOW | not changed: SystemRandom, ntfy's per-IP limits make guessing impractical; raise digits later if wanted |

Checked OK: (1) topic made only on the PC (no workflow / test runs pc_report for real), stored outside the repo (inside = refused),
chmod 600, never in last.json / the status post / status_feed.json (the card showing it is printed on the PC screen after the
write); (2) room_low: daily loss 70% once per account per day, drawdown 50/75% once per level with a 10-point re-arm, de-dup
state on disk; bot-down keys stable across restarts; digest <= 12 lines, once a day from 16:20 ET, silent; (3) send_critical
queues on a daemon thread (a 60 s hung channel returns at once), wait=True only in the ops / report / update scripts, every
error -> "bad"; (4) ALERTS_OFF / LE_ALERT_BUS=0 -> "off" -> each call site's old path (readiness push, autoupdate push,
notify ntfy); (5) ntfy budget: ~210 status posts of 250 + the report's 12-post trade-alert reserve; the new criticals are a
handful a day (bounded by #1); (6) no order / arming / strategy file in the diff (0 lines).
Tests: tests/test_notify_rt.py 24/24 (6 fail on dfce5661e); alert_map 58/58, alert_bus 86/86, notify 99/99, push 41/41,
ready 36/36, ready_rt 27/27, pc_report_sign 21/21, live_publish 86/86, public_build_privacy 59/59, trading_home 46/46,
alert_drill 100/100, pc_guard 56/56, trade_alerts 83/83, ninjatrader --selftest 80/80.

## Package B (a71400732) on top
| # | Finding | Sev | Fixed |
|---|---|---|---|
| B1 | push._crit_ntfy sent EVERY alerts_plus repeat (key crit:<id>:<n>, every 10 min, up to 6) and the silent "Resolved" notice to ntfy: the app's "Got it" stops the repeats, ntfy cannot, so one critical condition rang ntfy up to 6+ times a day (test: 4 rings in 60 min from one flapping feed) | MED | ntfy gets the first notice per condition id only (the id is per day; key without the repeat number); silent notices stay in the app |
| B2 | readiness rollback-and-resend when nothing delivered: bounded. deliver() is ok on ANY receipt, so a partial delivery is "sent" (no resend); a total failure resends once per 5-min tick and reaches no phone (no storm); my ready-rt 10-min floor / hourly cap still hold after a delivered resend | OK | - |
| B3 | guard le-guard pushes now ring the app + ntfy by default (before: only with LE_PUSH_EXTRA): keys per day / per entry / per level (guard:clock:<day>, entry:<t>, room:<start>:<lvl>), background thread (pc_notify), never in routing | OK | - |
| B4 | fill_audit LOUD_HOLDS 'PC clock' / 'internet time': text match only, no trade path | OK | - |
Tests on the merged head: notify_rt 27/27 (f1-f3 new; f1/f2 fail on a71400732), package_b 17/17, alerts_plus 92/92, alert_map 58/58,
alert_bus 86/86, notify 99/99, push 41/41, ready 36/36, ready_rt 27/27, alert_drill 100/100.
