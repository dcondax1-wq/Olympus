# big-zeroerr2 (2026-11-26): lead wires

Branch big-zeroerr2 = origin/day-ops2 11104923 + this. Paper only. Helper did NOT touch sw.js, build_web_dashboard.py,
jarvis/apps.js, the olympus.js APPS table. Nothing to wire. Land after-hours after the red team (server.py startup changed).

Red team, look at:
- engine/hang_guard.Guard.step: kill only when files_flat_reason() is None; START_GRACE_S 120 s; HANG_S 150 s; one line per
  episode; the lock data/hang_guard_<pid>.lock (a stale one from a reboot is taken over when its pid is gone).
- server.py _hang_guard_start: only LE_SUPERVISED=1; faulthandler.dump_traceback_later re-armed every 30 s from the event loop
  (a C thread writes the stacks: works while the GIL is held). The /api/health/ping handler is sync (threadpool): a starved
  threadpool also reads as hung (then a restart when flat is still the right move).
- A kill after an update counts as a start for crash_check (a hang right after an update rolls it back: wanted).
- Data limits: ntfy keeps ~12 h; 14-day history came from research/findings/LEDGER.md + STATE.md (docs/ERROR_SWEEP_2026-11-26.md).
- Lead item (not code here): failure map G8, the cloud PC-silent watch, does not run on Olympus (main README-only) and only 03-15 ET.
