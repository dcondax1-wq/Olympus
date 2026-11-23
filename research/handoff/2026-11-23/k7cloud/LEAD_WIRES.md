# LEAD_WIRES: night-k7cloud (2026-11-23)

The code needs nothing new: `tools/pc_silent_check.py` already runs in BOTH cloud jobs (pc-watch.yml step "PC silent check" and
cloud-monitor.yml's PC-silent step), with the `LE_NTFY_TOPIC` secret they already use. Free: ntfy + the Actions minutes already spent.

## Optional (recommended): one Sunday-evening run, so a Monday last day is warned the evening before

GitHub runs schedules only from the DEFAULT branch, so this edit goes in `.github/workflows/pc-watch.yml` on **`main`** (and the same
file on `pc` to keep them equal). Today pc-watch runs weekdays only (`7,37 5-21 * * 1-5`, UTC), so for an account whose MFFU last
day is a Monday, the first cloud warning comes at the Monday 00:07 ET run. Add one cron line under `schedule:`:

```yaml
    - cron: "7 22,23 * * 0"          # Sun 22:07 / 23:07 UTC = 17:07 / 18:07 ET in winter (EST), 18:07 / 19:07 in summer: the K7 check
                                     # warns about a Monday MFFU last day the evening before (and the Sunday pre-open note runs)
```

Cost: 2 runs a week x ~1 billed minute. Nothing else changes: the script's other checks exit at once outside their windows. It also
makes `preopen_step` (the Sunday 17:00-18:00 ET "PC is off" note) actually run: today no job runs on Sunday in that hour.

No secret, no paid service, no other file.
