"""PC ALWAYS ON: keep the owner's Windows PC awake and ready for the whole CME NQ week.

Why: the bot's biggest money leak is the PC being off or asleep in market hours. CME NQ trades Sunday 18:00 ET to Friday
17:00 ET (daily break 17:00-18:00 ET); the bot's entry windows run 02:00-15:30 ET on weekdays.

  python -X utf8 tools/pc_always_on.py            DRY RUN (default): prints each command and why. Changes nothing.
  python -X utf8 tools/pc_always_on.py --check    reads the PC's settings, prints GREEN / RED lines, one fix per RED.
  python -X utf8 tools/pc_always_on.py --apply    runs the commands (Windows, Administrator window). Elsewhere: "Windows only", exit 0.
  --keep-hibernation   you keep scripts\\schedule_pc.ps1's nightly hibernation: also add Sunday 17:30 ET + daily 01:15 ET wake tasks.
  --tz America/Chicago  pretend the PC lives in this zone (dry run / tests). Default: this PC's own clock.

Stdlib only, no network, no secrets, no passwords. It never starts, stops or arms the bot and never places an order.
Auto-login and the BIOS "restore on AC power loss" are guidance only (docs/PC_ALWAYS_ON.md): nothing here writes logon values.
Existing pieces it builds on (never edited): scripts/one_time_setup.ps1, setup_dedicated_pc.ps1 (power), schedule_pc.ps1 (wake / hibernate
tasks LiquidityEngineWake, LiquidityEngineSleep), install_autostart.ps1 (task LiquidityEngine), engine/ops_checks.py (read-only checks).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys

# ---- names the existing scripts create (detected, never duplicated)
BOT_TASK = "LiquidityEngine"            # scripts/install_autostart.ps1: starts the bot at logon / unlock
OPS_TASK = "LiquidityEngineOps"         # scripts/one_time_setup.ps1: 5-minute helper
WAKE_TASK = "LiquidityEngineWake"       # scripts/schedule_pc.ps1: Mon-Fri 01:30 ET wake + start
SLEEP_TASK = "LiquidityEngineSleep"     # scripts/schedule_pc.ps1: Mon-Fri 16:35 ET HIBERNATE
KEEPER_TASK = "LiquidityEngine-Keeper"  # scripts/pc_tune.ps1
CARE_TASK = "LiquidityEngine-WeeklyCare"
# new here (only when you keep the hibernation): a wake with a do-nothing action
SUN_WAKE_TASK = "OlympusWakeSunday"
DAILY_WAKE_TASK = "OlympusWakeDaily"

SUN_ET = (17, 30)    # Sunday: 30 min before the 18:00 ET open
DAILY_ET = (1, 15)   # 15 min before schedule_pc's 01:30 ET wake, 45 before the 02:00 entry window
USB_SUB, USB_SET = "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"
STARTUP_LNK = "NinjaTrader 8 (Liquidity Engine).lnk"   # scripts/one_time_setup.ps1 puts this in the Startup folder


# ----------------------------------------------------------------------------------------------- time zones
class _USEastern(dt.tzinfo):
    """Fallback ET (US DST rules) when zoneinfo / tzdata is missing (Windows without the tzdata package)."""

    def _dst(self, d: dt.datetime) -> bool:
        y = d.year
        mar = dt.datetime(y, 3, 8)
        mar += dt.timedelta(days=(6 - mar.weekday()) % 7)      # second Sunday of March
        nov = dt.datetime(y, 11, 1)
        nov += dt.timedelta(days=(6 - nov.weekday()) % 7)      # first Sunday of November
        n = d.replace(tzinfo=None)
        return mar.replace(hour=2) <= n < nov.replace(hour=2)

    def utcoffset(self, d):
        return dt.timedelta(hours=-4 if d and self._dst(d) else -5)

    def dst(self, d):
        return dt.timedelta(hours=1 if d and self._dst(d) else 0)

    def tzname(self, d):
        return "EDT" if d and self._dst(d) else "EST"


def et_zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:  # noqa: BLE001
        return _USEastern()


def local_zone(name: str | None = None):
    """The PC's zone: a named one (tests, --tz) or the PC's own clock (fixed offset of right now)."""
    if name:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    return dt.datetime.now().astimezone().tzinfo


def _next_et(now: dt.datetime, hm: tuple[int, int], weekday: int | None, et) -> dt.datetime:
    """The next ET wall time hh:mm (on `weekday` 0=Mon..6=Sun, or any day) at or after now, as an ET-aware datetime."""
    n = now.astimezone(et)
    for add in range(0, 9):
        d = (n + dt.timedelta(days=add)).date()
        cand = dt.datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=et)
        if cand >= n and (weekday is None or cand.weekday() == weekday):
            return cand
    raise RuntimeError("no next time")


def wake_times(now: dt.datetime, tz) -> dict:
    """Sunday 17:30 ET and daily 01:15 ET (the next ones from `now`), in ET and in the PC's zone `tz`. Pure."""
    et = et_zone()
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    sun = _next_et(now, SUN_ET, 6, et)
    day = _next_et(now, DAILY_ET, None, et)
    # which local weekdays does "ET Mon-Fri 01:15" fall on (it can be the day before/after for far zones)
    days: list[str] = []
    mon = (sun + dt.timedelta(days=1)).date()                  # the Monday after that Sunday
    for i in range(5):
        d = mon + dt.timedelta(days=i)
        loc = dt.datetime(d.year, d.month, d.day, DAILY_ET[0], DAILY_ET[1], tzinfo=et).astimezone(tz)
        nm = loc.strftime("%A")
        if nm not in days:
            days.append(nm)
    return {"sunday_et": sun, "sunday_local": sun.astimezone(tz), "daily_et": day,
            "daily_local": day.astimezone(tz), "daily_local_days": days}


# ----------------------------------------------------------------------------------------------- the plan (pure)
def _ps(script: str) -> str:
    return 'powershell -NoProfile -ExecutionPolicy Bypass -Command "' + script + '"'


def plan(now: dt.datetime, tz, keep_hibernation: bool = False, have: set | None = None) -> list[dict]:
    """Every command --apply would run, in order, each with a plain-words reason. Pure: no I/O.
    `have` = names of tasks that already exist (None = not known, as in a dry run)."""
    p: list[dict] = [
        {"cmd": "powercfg /change standby-timeout-ac 0", "why": "never fall asleep while plugged in"},
        {"cmd": "powercfg /change hibernate-timeout-ac 0", "why": "never hibernate by itself while plugged in"},
        {"cmd": "powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1",
         "why": "allow scheduled wake-ups (wake timers) when plugged in"},
        {"cmd": f"powercfg /setacvalueindex SCHEME_CURRENT {USB_SUB} {USB_SET} 0",
         "why": "stop Windows switching off USB ports (keeps USB network / dongles alive)"},
        {"cmd": "powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0",
         "why": "closing a laptop lid does nothing while plugged in"},
        {"cmd": "powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS PBUTTONACTION 3",
         "why": "power button shuts down (no accidental sleep; you can still stop the PC on purpose)"},
        {"cmd": "powercfg /setactive SCHEME_CURRENT", "why": "make the settings above take effect now"},
    ]
    if keep_hibernation:
        w = wake_times(now, tz)
        sl, dl = w["sunday_local"], w["daily_local"]
        p.append({"cmd": _ps(
            f"Register-ScheduledTask -TaskName '{SUN_WAKE_TASK}' -Force "
            "-Action (New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c exit') "
            f"-Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek {sl.strftime('%A')} -At '{sl.strftime('%H:%M')}') "
            "-Settings (New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries) | Out-Null"),
            "why": (f"wake the PC from hibernation Sunday 17:30 ET ({sl.strftime('%A %H:%M')} on this PC), "
                    "30 min before the 18:00 ET open; schedule_pc.ps1 only wakes Mon-Fri 01:30 ET")})
        p.append({"cmd": _ps(
            f"Register-ScheduledTask -TaskName '{DAILY_WAKE_TASK}' -Force "
            "-Action (New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c exit') "
            f"-Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek {','.join(w['daily_local_days'])} -At '{dl.strftime('%H:%M')}') "
            "-Settings (New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries) | Out-Null"),
            "why": (f"wake the PC 01:15 ET ({dl.strftime('%H:%M')} on this PC) weekdays, 15 min before the "
                    "01:30 ET wake: a second chance if the first one is missed")})
    if have is not None:
        if BOT_TASK not in have:
            p.append({"cmd": r"powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_autostart.ps1",
                      "why": f"task {BOT_TASK} (starts the bot at logon) is missing; this existing script creates it, not a duplicate"})
    return p


def notes(keep_hibernation: bool) -> list[str]:
    n = []
    if keep_hibernation:
        n.append("You keep schedule_pc.ps1: it hibernates the PC at 16:35 ET Mon-Fri (also Friday) and wakes it only Mon-Fri 01:30 ET. "
                 "The two wake tasks above cover Sunday 17:30 ET and 01:15 ET. Hibernation keeps NinjaTrader and the bot closed in between.")
    else:
        n.append("Never-sleep makes the Sunday / 01:15 ET wake tasks unnecessary, so none are added. But schedule_pc.ps1's "
                 f"task {SLEEP_TASK} still HIBERNATES the PC at 16:35 ET: remove it (powershell -File scripts\\schedule_pc.ps1 -Uninstall) "
                 "or add --keep-hibernation.")
    n.append("Guidance only (steps in docs/PC_ALWAYS_ON.md): auto-login (netplwiz) and BIOS 'restore on AC power loss'. "
             "Nothing here writes a password or logon value.")
    n.append("Windows Update: use --check; the fix is scripts\\one_time_setup.ps1 (active hours, no restart while signed in).")
    return n


# ----------------------------------------------------------------------------------------------- reading the PC
def _run(cmd) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=isinstance(cmd, str))
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def power_ac(sub: str, setting: str, run=_run):
    """AC value of one power setting or None (powercfg prints AC then DC as the last two hex numbers)."""
    code, out = run(["powercfg", "/q", "SCHEME_CURRENT", sub, setting])
    hx = re.findall(r"0x[0-9a-fA-F]+", out) if code == 0 else []
    return int(hx[-2], 16) if len(hx) >= 2 else None


def task_info(name: str, run=_run):
    """None when the task does not exist, else {'next': 'Next Run Time text'}."""
    code, out = run(["schtasks", "/query", "/tn", name, "/fo", "LIST", "/v"])
    if code != 0:
        return None
    m = re.search(r"^(?:Next Run Time|Naechste Laufzeit)\s*:\s*(.+)$", out, re.M)
    return {"next": m.group(1).strip() if m else ""}


def reg_value(key: str, name: str, run=_run):
    """The data of one registry value, or None. Only used for harmless flags, never for a password."""
    code, out = run(["reg", "query", key, "/v", name])
    m = re.search(rf"^\s*{re.escape(name)}\s+REG_\w+\s+(\S+)", out, re.M) if code == 0 else None
    return m.group(1) if m else None


def startup_shortcut_present() -> bool:
    d = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", STARTUP_LNK)
    return os.path.isfile(d)


def check(run=_run, startup=startup_shortcut_present) -> list[tuple[bool, str, str]]:
    """[(green?, what, fix)] read-only."""
    r: list[tuple[bool, str, str]] = []
    sl, hb = power_ac("SUB_SLEEP", "STANDBYIDLE", run), power_ac("SUB_SLEEP", "HIBERNATEIDLE", run)
    ok = sl == 0 and hb == 0
    r.append((ok, "Never sleeps / hibernates on its own when plugged in" if ok else
              f"Sleep/hibernate timers on AC: sleep={sl}s hibernate={hb}s (0 = never)",
              "powercfg /change standby-timeout-ac 0  and  powercfg /change hibernate-timeout-ac 0 (or --apply)"))
    rtc = power_ac("SUB_SLEEP", "RTCWAKE", run)
    r.append((rtc == 1, "Wake timers allowed on AC" if rtc == 1 else f"Wake timers on AC = {rtc} (need 1)",
              "powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 (or --apply)"))
    usb = power_ac(USB_SUB, USB_SET, run)
    r.append((usb in (0, None), "USB selective suspend off (or not on this PC)" if usb in (0, None) else "USB selective suspend is ON",
              f"powercfg /setacvalueindex SCHEME_CURRENT {USB_SUB} {USB_SET} 0 (or --apply)"))
    lid = power_ac("SUB_BUTTONS", "LIDACTION", run)
    r.append((lid in (0, None), "Lid close does nothing on AC (or no lid)" if lid in (0, None) else "Closing the lid sleeps the PC",
              "powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 (or --apply)"))
    tasks = {n: task_info(n, run) for n in (BOT_TASK, OPS_TASK, WAKE_TASK, SLEEP_TASK, KEEPER_TASK, SUN_WAKE_TASK, DAILY_WAKE_TASK)}
    r.append((tasks[BOT_TASK] is not None, f"Task {BOT_TASK} starts the bot at logon" if tasks[BOT_TASK] else f"Task {BOT_TASK} is missing",
              r"powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 (or scripts\one_time_setup.ps1)"))
    r.append((startup(), "NinjaTrader Startup shortcut present" if startup() else "NinjaTrader Startup shortcut missing",
              r"scripts\one_time_setup.ps1 adds it ('NinjaTrader 8 (Liquidity Engine).lnk' in shell:startup)"))
    hib = tasks[SLEEP_TASK] is not None
    sun = tasks[SUN_WAKE_TASK] is not None
    if hib and not sun:
        r.append((False, f"Task {SLEEP_TASK} hibernates the PC 16:35 ET Mon-Fri and nothing wakes it Sunday (schedule_pc wakes Mon-Fri 01:30 ET only): "
                  "the likely cause of a silent weekend",
                  "python -X utf8 tools/pc_always_on.py --apply --keep-hibernation  (or remove it: scripts\\schedule_pc.ps1 -Uninstall)"))
    elif hib and sun:
        r.append((True, "Hibernation kept, Sunday wake task present", ""))
    else:
        r.append((True, "No nightly hibernation task: the PC just stays on", ""))
    au = reg_value(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", "NoAutoRebootWithLoggedOnUsers", run)
    r.append((au in ("0x1", "1"), "Windows Update: no forced restart while signed in" if au in ("0x1", "1") else
              "Windows Update may restart the PC by itself", r"scripts\one_time_setup.ps1 (sets active hours + no restart); then Settings > Windows Update > Advanced > Active hours"))
    ah = reg_value(r"HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", "ActiveHoursEnd", run)
    r.append((ah is not None, "Windows Update active hours are set" if ah is not None else "Windows Update active hours not set",
              r"Settings > Windows Update > Advanced options > Active hours (cover 01:00-17:00 ET) or scripts\one_time_setup.ps1"))
    al = reg_value(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon", "AutoAdminLogon", run)   # presence only
    r.append((al == "1", "Auto-login is on (after a power cut the PC signs itself in)" if al == "1" else
              "Auto-login is off: after a power cut the PC waits at the sign-in screen and the bot never starts",
              "Guidance only: docs/PC_ALWAYS_ON.md step 2 (netplwiz). BIOS 'restore on AC power loss' is step 3."))
    return r


# ----------------------------------------------------------------------------------------------- main
def _is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return False


def main(argv=None, is_windows: bool | None = None, run=_run, now: dt.datetime | None = None, out=print) -> int:
    ap = argparse.ArgumentParser(description="Keep the PC awake for the whole NQ week (dry run by default).")
    ap.add_argument("--check", action="store_true", help="read the current settings, print GREEN / RED")
    ap.add_argument("--apply", action="store_true", help="run the commands (Windows, Administrator)")
    ap.add_argument("--keep-hibernation", action="store_true", help="you keep schedule_pc.ps1's hibernation: add wake tasks")
    ap.add_argument("--tz", default=None, help="IANA zone of the PC (default: this PC's clock)")
    a = ap.parse_args(argv)
    win = (os.name == "nt") if is_windows is None else is_windows
    tz = local_zone(a.tz)
    now = now or dt.datetime.now(tz)

    if a.apply and not win:
        out("Windows only: nothing changed.")
        return 0
    if a.check:
        if not win:
            out("Windows only: --check reads the PC's own settings. Nothing changed.")
            return 0
        res = check(run)
        for ok, what, fix in res:
            out(("GREEN  " if ok else "RED    ") + what)
            if not ok and fix:
                out("       fix: " + fix)
        bad = sum(1 for g, _, _ in res if not g)
        out(f"\n{len(res) - bad} green, {bad} red.")
        return 1 if bad else 0

    keep = a.keep_hibernation
    have = None
    if win:
        have = {n for n in (BOT_TASK, OPS_TASK, SLEEP_TASK) if task_info(n, run) is not None}
        if SLEEP_TASK in have and not keep and a.apply:
            keep = True   # the owner already has the hibernation task: wake tasks are needed, do not remove anything silently
    steps = plan(now, tz, keep, have)
    out(("APPLY" if a.apply else "DRY RUN (nothing is changed; add --apply in an Administrator window)") + f" - PC zone {tz}")
    for s in steps:
        out(s["cmd"])
        out("    why: " + s["why"])
    for n in notes(keep):
        out("NOTE: " + n)
    if not a.apply:
        return 0
    if not _is_admin():
        out("RED: not an Administrator window. Right-click PowerShell > Run as administrator, then run this again.")
        return 1
    fails = 0
    for s in steps:
        code, o = run(s["cmd"])
        out(("ok   " if code == 0 else "FAIL ") + s["cmd"][:110])
        if code != 0:
            fails += 1
            out("     " + o.strip()[:200])
    out(f"Done: {len(steps) - fails}/{len(steps)} commands worked. Now run --check.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
