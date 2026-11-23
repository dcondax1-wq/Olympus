# night-truth red team (2026-11-23): ea1fe0b67 -> night-truth-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | Trading Home account rows went GREEN on a guess: when the core's "ar" has no entry for an account (an old PC; the Rapid / extra accounts, which are not glance bots) heldWhy falls back to badge LIVE; the row said "ARMED ?" but ok = true | MED | green only when "ar" confirms armed AND the bot runs; a badge-only guess is grey (null); not armed / stopped = red |
| 2 | ntfy day budget with every night branch (per IP, all topics): status posts at most 96 core + 66 ext + 24 chart + 24 pulse = 210 (core repeats under 5 min skipped). Private alerts on top: trade entries / exits (~8-16), readiness NOT READY (capped hourly + 10-min floor, ~2-10), update failure (1/day per failure, notify-rt), critical alarms (first notice per condition, notify-rt), room low (once per level / day), payout autopilot (a few), digest 1, morning brief 1, day summary 1 = about 20-35 on a busy day vs 40 left. pulse_once holds on ntfy's OWN remaining count (GET /v1/account, which counts the alerts too) and the ext / chart do the same, so the status posts give way first | LOW | not changed; if the PC ever logs ntfy 429 on alerts: DAY_MAX pulse 24 -> 12 |
| 3 | local_live: 127.0.0.1:<port>/api/site/live.json only when the ping on that port answers; a spoof needs a process already on this PC (and it can only change the public view, never an order) | LOW | not changed |

Checked OK: (1) the pulse runs on its own daemon thread (10 s tick: attribute reads + multi_account.health(), light, no file, no lock);
a fire = heartbeat beat + live.json + `pc_report.py --pulse` in a child with a 120 s limit; every step wrapped; debounce 30 s, 90 s
start grace (no "stopped" while the server brings the bot up), <= 24 a UTC day (persisted, survives restarts), held on the PC's and
ntfy's own counts; off in dev / test servers and the self-test children. (2) core: "ar" = {glance bot id: [on, armed]} (no ids),
accounts rows gain enabled / locked / armed, public() and test_public_build_privacy pass. (4) "ar" comes from the brain glance (its
armed rule = land-fixes brain_glance._ab_armed), the ext hash now changes on on / armed / nar. No trade file in the diff.
Tests: live_publish 86/86, pc_report_sign 21/21, brain 48/48, nq_brain 22/22, trading_home 50/50, board 59/59, mffu_view 22/22,
account_rules 35/35, public_build_privacy 59/59, state_pulse 58/58, launch_checklist 69/69, ops 114/114, ninjatrader --selftest 80/80.
