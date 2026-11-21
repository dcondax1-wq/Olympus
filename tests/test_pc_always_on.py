"""tools/pc_always_on.py: the always-on PC helper (dry run by default, --check, --apply Windows only).
Runs on Linux: the plan is a pure function.
    python -X utf8 -m tests.test_pc_always_on
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from tools import pc_always_on as P  # noqa: E402

check = AK.check
ROOT = AK.ROOT
NY, CHI, LON = ZoneInfo("America/New_York"), ZoneInfo("America/Chicago"), ZoneInfo("Europe/London")


def test_plan():
    now = dt.datetime(2026, 11, 21, 12, 0, tzinfo=NY)
    base = P.plan(now, NY, False)
    text = "\n".join(s["cmd"] for s in base)
    check("plan: never sleep on AC", "standby-timeout-ac 0" in text and "hibernate-timeout-ac 0" in text)
    check("plan: wake timers", "SUB_SLEEP RTCWAKE 1" in text)
    check("plan: USB selective suspend off", P.USB_SET in text)
    check("plan: every line has a reason", all(s["why"] and s["cmd"] for s in base))
    check("plan: no wake tasks without hibernation", P.SUN_WAKE_TASK not in text)
    keep = P.plan(now, NY, True)
    kt = "\n".join(s["cmd"] for s in keep)
    check("plan: hibernation kept = the weekday 01:15 ET second-chance wake only; no Sunday wake (nothing trades before Mon 02:00 ET)",
          P.SUN_WAKE_TASK not in kt and P.DAILY_WAKE_TASK in kt and "WakeToRun" in kt)
    nt = " ".join(P.notes(False) + P.notes(True))
    check("notes: never tell the owner to remove the hibernation", "-Uninstall" not in nt and "by design" in nt and "nothing trades" in nt, nt[:300])
    allt = kt + "\n" + "\n".join(s["cmd"] for s in P.plan(now, NY, True, set()))
    bad = [r"password", r"AutoAdminLogon", r"DefaultPassword", r"stop_bot", r"start_bot", r"run_bot", r"Stop-", r"Start-ScheduledTask",
           r"taskkill", r"\barm\b", r"--start", r"reg add", r"Set-ItemProperty", r"order"]
    hit = [b for b in bad if re.search(b, allt, re.I)]
    check("plan: no password / logon write / bot stop-start-arm", not hit, hit)
    miss = P.plan(now, NY, False, set())
    check("plan: missing bot task points at the existing script", any("install_autostart.ps1" in s["cmd"] for s in miss))


def test_times():
    w = P.wake_times(dt.datetime(2026, 11, 21, 12, 0, tzinfo=NY), NY)
    check("ET: Sunday 17:30 ET (Nov 22)", (w["sunday_local"].strftime("%a %Y-%m-%d %H:%M")) == "Sun 2026-11-22 17:30", w["sunday_local"])
    check("ET: daily 01:15", w["daily_local"].strftime("%H:%M") == "01:15", w["daily_local"])
    c = P.wake_times(dt.datetime(2026, 11, 21, 12, 0, tzinfo=NY), CHI)
    check("Chicago: Sunday 16:30, daily 00:15", c["sunday_local"].strftime("%H:%M") == "16:30" and c["daily_local"].strftime("%H:%M") == "00:15", c)
    # DST gap: US clocks changed Mar 8 2026, UK on Mar 29: London is 5h ahead of New York, then 4h, then 5h
    a = P.wake_times(dt.datetime(2026, 2, 25, 12, 0, tzinfo=LON), LON)["sunday_local"]
    b = P.wake_times(dt.datetime(2026, 3, 10, 12, 0, tzinfo=LON), LON)["sunday_local"]
    d = P.wake_times(dt.datetime(2026, 4, 1, 12, 0, tzinfo=LON), LON)["sunday_local"]
    check("London before US DST: 17:30 ET = 22:30", a.strftime("%a %m-%d %H:%M") == "Sun 03-01 22:30", a)
    check("London after US DST, before UK DST: 21:30", b.strftime("%a %m-%d %H:%M") == "Sun 03-15 21:30", b)
    check("London after both: 22:30 again", d.strftime("%H:%M") == "22:30", d)
    t = P.wake_times(dt.datetime(2026, 11, 21, 12, 0, tzinfo=NY), ZoneInfo("Asia/Tokyo"))
    check("Tokyo: Sunday 17:30 ET lands Monday 07:30; daily days shift", t["sunday_local"].strftime("%a %H:%M") == "Mon 07:30" and "Tuesday" in t["daily_local_days"], t)
    fb = dt.datetime(2026, 7, 1, 12, 0, tzinfo=P._USEastern())
    check("fallback ET: July = EDT, January = EST", fb.utcoffset() == dt.timedelta(hours=-4)
          and dt.datetime(2026, 1, 5, tzinfo=P._USEastern()).utcoffset() == dt.timedelta(hours=-5))


def test_apply_and_doc():
    calls, lines = [], []
    rc = P.main(["--apply"], is_windows=False, run=lambda c: calls.append(c) or (0, ""), out=lines.append)
    check("--apply on non-Windows: exit 0, 'Windows only', nothing run", rc == 0 and not calls and "Windows only" in " ".join(lines), (rc, calls, lines))
    rc = P.main([], is_windows=False, run=lambda c: calls.append(c) or (0, ""), out=lines.append)
    check("default is a dry run: exit 0, nothing run", rc == 0 and not calls)
    rc = P.main(["--check"], is_windows=False, run=lambda c: calls.append(c) or (0, ""), out=lines.append)
    check("--check on non-Windows: exit 0, nothing run", rc == 0 and not calls)
    # --check logic with a fake PC: slept + no tasks -> red lines; never password
    def fake(cmd):
        calls.append(cmd)
        if cmd[0] == "powercfg":
            return 0, "AC 0x00000258 DC 0x00000258"
        return 1, ""
    res = P.check(fake, startup=lambda: False)
    check("--check: red when it sleeps after 10 min", not res[0][0] and res[0][2])
    check("--check never queries a password", not any("password" in " ".join(c).lower() for c in calls if isinstance(c, list)))
    p = os.path.join(ROOT, "docs", "PC_ALWAYS_ON.md")
    s = open(p, encoding="utf-8").read().lower() if os.path.exists(p) else ""
    check("doc exists and mentions dry run, BIOS, auto-login, Sunday", all(k in s for k in ("dry run", "bios", "auto-login", "sunday")))
    check("doc is short (<= 130 lines)", 0 < len(s.splitlines()) <= 130)


if __name__ == "__main__":
    test_plan()
    test_times()
    test_apply_and_doc()
    AK.finish()
