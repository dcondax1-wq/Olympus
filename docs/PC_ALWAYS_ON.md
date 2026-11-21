# PC ALWAYS ON: one-time guide

The bot only makes money while the PC is on. CME NQ trades Sunday 18:00 ET to Friday 17:00 ET (break 17:00-18:00 ET daily);
the bot enters 02:00-15:30 ET on weekdays. This guide makes the PC survive a whole week, a power cut and a Windows update.

| What | Why | How long |
|---|---|---|
| 1. Run `tools/pc_always_on.py` (dry run, then `--apply`) | never sleep, wake timers, USB stays on | 3 min |
| 2. Auto-login | after a power cut the PC signs itself in and the bot restarts | 3 min |
| 3. BIOS "restore on AC power loss" | the PC switches itself back on after a power cut | 5 min |
| 4. Wired internet if you can | Wi-Fi drops are silent bot outages | 2 min |
| 5. Sunday 17:30 ET check | proves the week starts clean | 1 min |

## What already exists, and what is new

Already done by the old scripts (this tool does not redo or duplicate them):
- `scripts/one_time_setup.ps1` and `setup_dedicated_pc.ps1`: no sleep / hibernate on AC, lid close = nothing, USB suspend off, wake timers on,
  Windows Update active hours + no restart while signed in, task `LiquidityEngine` (bot at logon), `LiquidityEngineOps`, the NinjaTrader Startup shortcut.
- `scripts/schedule_pc.ps1` (only if you ran it): task `LiquidityEngineWake` wakes the PC Mon-Fri 01:30 ET and task `LiquidityEngineSleep`
  HIBERNATES it Mon-Fri 16:35 ET.

Honest gap: that wake runs Mon-Fri only. On Friday 16:35 ET the PC hibernates and nothing wakes it until Monday 01:30 ET, so it is dark
for the Sunday 18:00 ET open. If that Monday wake is missed (wake timers off, battery, no admin), the PC stays off all week. That is the
most likely reason for a silent weekend.

New here:
- `--check` (read-only red/green list with one fix per red line), a Sunday 17:30 ET wake and a daily 01:15 ET wake (only if you keep hibernation),
  and the printed guidance for auto-login and BIOS. Nothing here writes a password or a logon value.

## Steps (your hands)

1. **Set the PC up.** Open PowerShell in the bot folder.
   - Look first (changes nothing, this is the dry run): `python -X utf8 tools/pc_always_on.py`
   - Right-click PowerShell > Run as administrator, then: `python -X utf8 tools/pc_always_on.py --apply`
   - Then: `python -X utf8 tools/pc_always_on.py --check` (every line GREEN; each RED line prints its one fix).
   - Simplest: do NOT keep hibernation. Then the PC just stays on and the Sunday wake is not needed. If `LiquidityEngineSleep` exists,
     remove it: `powershell -ExecutionPolicy Bypass -File scripts\schedule_pc.ps1 -Uninstall`.
     If you do want it hibernating at night (power bill), add `--keep-hibernation` to both commands for the Sunday + 01:15 ET wake tasks.
2. **Auto-login.** Press Win+R, type `netplwiz`, untick "Users must enter a user name and password", OK, type your Windows password once
   (Windows stores it, not us). Trade-off: anyone who can switch the PC on can use it, so only do this at home. If netplwiz has no
   tick box: Settings > Accounts > Sign-in options > turn off "Require Windows Hello sign-in for Microsoft accounts", then retry.
3. **BIOS: restore on AC power loss.** Restart, tap the BIOS key, find the power setting, set it to **Power On** (or "Last State"), save.
   | Maker | BIOS key | Where |
   |---|---|---|
   | Lenovo | F1 or F2 (Enter then F1) | Power > After Power Loss > Power On |
   | Dell | F2 | Power Management > AC Recovery > On |
   | HP | F10 | Advanced > Power-On Options > After Power Loss > Power On |
   | Surface | n/a | **No such setting.** A Surface stays off after a power cut; a Surface stays off after a power cut, so keep it plugged in on a UPS. |
   Also set "Wake on RTC / alarm" ON if you ever shut down (not hibernate).
4. **Network.** Plug the PC into the router with a cable if you can; if not, put the PC near the router and keep Wi-Fi on one band.
   Optional: set the router to auto-restart only on Sunday 12:00 (not in market hours).
5. **Sunday 17:30 ET** (about 30 min before the open): the screen is on or can be woken, NinjaTrader is open and connected, the bot page
   answers, your phone got the PC report. If not: run `python -X utf8 tools/pc_always_on.py --check` and send me the red lines.

## Safety

The tool never starts, stops or arms the bot and never places an order. Update restarts stay outside 01:00-17:00 ET via the active hours the
old setup script sets; `--check` shows if they are on. Windows Update pause lasts 35 days: re-run `scripts\one_time_setup.ps1` when it ends.
