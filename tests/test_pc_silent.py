"""The cloud's loud "Surface offline" alert (engine/push.pc_outage + tools/cloud_monitor.py) and its schedule.

Owner 2026-10-20: the Surface went silent at 20:46 ET (sleep). The old alert repeated "PC bot silent" hourly, only when the
PC had said it was running, and the first push came at 03:13 ET because the workflow guard dropped the late-started 02:21
run ("minute % 30 < 15") and nothing ran before 02:00 ET. Now: heartbeat > 30 min old inside 01:30-16:00 ET on a weekday
-> one push per outage (key = the last check-in) + one "back online" push; the workflow runs from 01:30 ET and keeps late
runs. Also checks the README row, the phone Home line (tools/web_public/hub.js), the service worker and the heartbeat
reader's old "heartbeat.json\\r" name. No network.

  python -X utf8 -m tests.test_pc_silent
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from engine import heartbeat, push

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def ts(y, mo, d, h=0, mi=0):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def guard(now_utc: int, schedule: str = "2,32 6-21 * * 1-5") -> int:
    """Runs the workflow's market-hours guard (bash) with `date` faked to now_utc. Returns go (0/1)."""
    wf = read(".github/workflows/cloud-monitor.yml")
    m = re.search(r"- name: Market-hours guard \(ET\)\n\s+id: guard\n\s+run: \|\n(.*?)\n\n", wf, re.S)
    script = "\n".join(ln[10:] if ln.startswith(" " * 10) else ln.strip() for ln in m.group(1).splitlines())
    script = script.replace("${{ github.event_name }}", "schedule").replace("${{ github.event.schedule }}", schedule)
    tmp = tempfile.mkdtemp(prefix="le_guard_")
    try:
        real = shutil.which("date")
        with open(os.path.join(tmp, "date"), "w") as fh:
            fh.write(f'#!/bin/sh\nexec {real} -d @{now_utc} "$@"\n')
        os.chmod(os.path.join(tmp, "date"), 0o755)
        out = os.path.join(tmp, "out")
        env = {**os.environ, "PATH": tmp + os.pathsep + os.environ.get("PATH", ""), "GITHUB_OUTPUT": out}
        subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30)
        with open(out) as fh:
            return int(re.findall(r"go=(\d)", fh.read())[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    # ------------------------------------------------------------------ the outage tracker (engine/push.pc_outage)
    last = ts(2026, 10, 19, 20, 46)                       # Monday 20:46 ET: the Surface's last heartbeat
    hb = lambda t, now: {"present": True, "t": t, "age_s": now - t, "host": "DESKTOP-FCGDH2K", "running": True, "every_s": 300}
    st, out = push.pc_outage({}, hb(last, ts(2026, 10, 19, 21, 30)), ts(2026, 10, 19, 21, 30))
    check("21:30 ET Monday (outside 01:30-16:00): outage tracked, no push", st.get("since") == last and not out and not st.get("alerted_at"), (st, out))
    n1 = ts(2026, 10, 20, 1, 32)
    st, out = push.pc_outage(st, hb(last, n1), n1)
    check("01:32 ET Tuesday (the night run): ONE push", len(out) == 1 and out[0]["key"] == f"pc_offline:{last}" and st.get("alerted_at") == n1, out)
    p = out[0] if out else {}
    check("push text: 'Surface offline since Mon 20:46 ET — the bot can't trade. Check it's awake and NinjaTrader is connected.'",
          p.get("body", "").startswith("Surface offline since Mon 20:46 ET — the bot can't trade. Check it's awake and NinjaTrader is connected.")
          and p.get("title") == "Surface offline since Mon 20:46 ET", p)
    check("push is loud: kind 'pc' (always pushed), require=True on the wire, own tag", p.get("kind") == "pc" and p.get("require") is True
          and json.loads(push.wire(p)).get("require") is True and p.get("tag") == "le-pc-offline")
    check("trade notices stay without 'require' on the wire", "require" not in json.loads(push.wire(push.text_payload("Cloud", "timing", "x", "y", key="k"))))
    pushes = 1
    for h, mi in ((2, 21), (3, 13), (8, 1), (13, 13), (15, 58)):
        n = ts(2026, 10, 20, h, mi)
        st, out = push.pc_outage(st, hb(last, n), n)
        pushes += len(out)
    check("later runs the same outage: no repeat (once per outage)", pushes == 1, pushes)
    back = ts(2026, 10, 20, 16, 10)
    n = back + 300
    st, out = push.pc_outage(st, hb(back, n), n)
    check("it reports again: one 'Surface back online' push, outage closed", len(out) == 1 and out[0]["key"] == f"pc_back:{last}"
          and "back online at 16:10 ET" in out[0]["body"] and st.get("back_at") == back, out)
    st2, out = push.pc_outage(st, hb(back + 600, n + 600), n + 600)
    check("fresh heartbeats after that: nothing more", not out and st2 == st, (st2, out))
    # a new outage (other check-in time) -> a new key, pushed again
    t2 = ts(2026, 10, 21, 9, 0)
    n = ts(2026, 10, 21, 9, 45)
    st3, out = push.pc_outage(st2, hb(t2, n), n)
    check("a new outage the next day (09:00 -> 09:45 ET): its own push 'since 09:00 ET'", len(out) == 1 and out[0]["key"] == f"pc_offline:{t2}"
          and "since 09:00 ET" in out[0]["body"], out)
    # an outage that heals before the window: no back-online push (nothing was pushed)
    t3 = ts(2026, 10, 22, 0, 10)
    st4, out = push.pc_outage({}, hb(t3, t3 + 3600), t3 + 3600)
    st4, out2 = push.pc_outage(st4, hb(t3 + 4000, t3 + 4100), t3 + 4100)
    check("outage 00:10-01:16 ET, all before 01:30: no push at all", not out and not out2, (out, out2))
    check("29 min old in the window: not offline", not push.pc_outage({}, hb(n - 29 * 60, n), n)[1])
    check("no heartbeat branch (fetch failed): state kept, no push", push.pc_outage({"since": 5}, {"present": False}, n) == ({"since": 5}, []))
    sat = ts(2026, 10, 24, 9, 0)
    check("Saturday: no push", not push.pc_outage({}, hb(sat - 7200, sat), sat)[1])
    check("old PCs (running False / no health block) are covered too",
          len(push.pc_outage({}, {**hb(last, n1), "running": False}, n1)[1]) == 1)
    pos = push.pc_outage({}, {**hb(last, n1), "position": True}, n1)[1][0]
    check("open position: the push says so", "POSITION WAS OPEN" in pos["body"], pos)

    # ------------------------------------------------------------------ the README / app line
    L = push.pc_checkin_line(hb(last, n1), n1)
    check("README line in hours: '**OFFLINE since Mon 20:46 ET** (4.8 h)'", L["offline"] and "OFFLINE since Mon 20:46 ET" in L["text"]
          and "4.8 h" in L["text"], L)
    L = push.pc_checkin_line(hb(n1 - 120, n1), n1)
    check("README line fresh: 'last check-in 01:30 ET (2 min ago)'", not L["offline"] and L["text"] == "last check-in 01:30 ET (2 min ago)", L)
    L = push.pc_checkin_line({"present": False}, n1)
    check("README line without a heartbeat", L["offline"] and "no check-in" in L["text"], L)
    cm = read("tools/cloud_monitor.py")
    check("cloud monitor: README row 'Surface', state pc_outage + pc_checkin, push.pc_outage on every run",
          '| Surface | {pc_line' in cm and '"pc_outage": pc_outage, "pc_checkin": pc_line' in cm and "push.pc_outage(st.get(\"pc_outage\"), pc, now)" in cm)
    check("cloud monitor: the hourly 'PC bot silent' repeat and the verdict's SILENT push are gone",
          "PC BOT SILENT" not in cm and 'pc_verdict["code"] != "SILENT"' in cm)

    # ------------------------------------------------------------------ the workflow schedule (the real guard script)
    wf = read(".github/workflows/cloud-monitor.yml")
    check("cron: a 05:32 UTC run on weekdays (01:32 ET in summer)", '"32 5 * * 1-5"' in wf and '"2,32 6-21 * * 1-5"' in wf)
    import yaml
    crons = [c["cron"] for c in yaml.safe_load(wf)[True]["schedule"]]
    check("three schedules in all (half-hourly, the night check, the Sunday review)", len(crons) == 3, crons)
    utc = lambda y, mo, d, h, mi: int(dt.datetime(y, mo, d, h, mi, tzinfo=dt.timezone.utc).timestamp())
    cases = [  # (UTC time, expected go, why)
        (utc(2026, 10, 20, 5, 32), 1, "Tue 01:32 EDT: the night check"),
        (utc(2026, 10, 20, 5, 55), 1, "Tue 01:55 EDT: the night check started 23 min late"),
        (utc(2026, 10, 20, 6, 21), 1, "Tue 02:21 EDT: a late 02:02 run (was dropped before)"),
        (utc(2026, 10, 20, 9, 22), 1, "Tue 05:22 EDT: late run in London"),
        (utc(2026, 10, 20, 16, 20), 0, "Tue 12:20 EDT: the midday lull keeps the old filter"),
        (utc(2026, 10, 20, 16, 5), 1, "Tue 12:05 EDT"),
        (utc(2026, 10, 20, 20, 32), 1, "Tue 16:32 EDT: end-of-day summary"),
        (utc(2026, 10, 20, 21, 2), 0, "Tue 17:02 EDT: after the session"),
        (utc(2026, 11, 3, 6, 2), 0, "Tue 01:02 EST (winter): too early"),
        (utc(2026, 11, 3, 6, 32), 1, "Tue 01:32 EST (winter): the night check"),
        (utc(2026, 10, 24, 9, 2), 0, "Saturday"),
    ]
    if shutil.which("bash") and shutil.which("date"):
        bad = [(why, g) for t, want, why in cases if (g := guard(t)) != want]
        check("guard: runs from 01:30 ET, keeps late-started runs, midday filter, nothing after 16:40 ET or on Saturday", not bad, bad)
        check("guard: the Sunday review still runs", guard(utc(2026, 10, 25, 21, 47), "47 21 * * 0") == 1)
    else:
        print("[SKIP] guard script (no bash / date)")

    # ------------------------------------------------------------------ the heartbeat reader: old Windows name "heartbeat.json\r"
    if shutil.which("git"):
        tmp = tempfile.mkdtemp(prefix="le_hbcr_")
        try:
            remote, work = os.path.join(tmp, "remote.git"), os.path.join(tmp, "work")
            subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
            subprocess.run(["git", "init", "-q", work], check=True)
            subprocess.run(["git", "-C", work, "remote", "add", "origin", remote], check=True)
            body = json.dumps({"t": last, "running": True, "every_s": 300, "host": "DESKTOP-FCGDH2K"}).encode()
            blob = subprocess.run(["git", "-C", work, "hash-object", "-w", "--stdin"], input=body, capture_output=True, check=True).stdout.decode().strip()
            tree = subprocess.run(["git", "-C", work, "mktree"], input=f"100644 blob {blob}\theartbeat.json\r\n".encode(),
                                  capture_output=True, check=True).stdout.decode().strip()
            env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
            com = subprocess.run(["git", "-C", work, "commit-tree", tree, "-m", "hb"], capture_output=True, text=True, env=env, check=True).stdout.strip()
            subprocess.run(["git", "-C", work, "push", "-q", "origin", f"{com}:refs/heads/heartbeat"], check=True, capture_output=True)
            r = heartbeat.read(cwd=work, now=n1)
            check("heartbeat.read: the old PC's 'heartbeat.json\\r' is read (age, host)", r.get("present") and r.get("t") == last
                  and r.get("age_s") == n1 - last, r)
            check("... and pc_outage pushes on it", len(push.pc_outage({}, r, n1)[1]) == 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------ the phone app (tools/web_public)
    hub = read("tools/web_public/hub.js")
    check("Home: 'Surface last check-in' line on top, red 'OFFLINE since' when > 30 min in 01:30-16:00 ET",
          "function surfaceLine()" in hub and "${surfaceLine()}${banner()}" in hub and "Surface OFFLINE since" in hub
          and "30 * 60" in hub and "mod >= 90 && mod <= 960" in hub and ".hb-surface.bad" in hub)
    sw = read("tools/web_public/sw.js")
    check("service worker: cache bumped (v12 or later), 'require' -> requireInteraction",
          int((re.search(r"le-public-v(\d+)", sw) or [0, 0])[1]) >= 12 and "requireInteraction" in sw)
    check("index.html loads the new hub.js (v=2 or later)", int((re.search(r"hub\.js\?v=(\d+)", read("tools/web_public/index.html")) or [0, 0])[1]) >= 2)
    bw = read("tools/build_web_dashboard.py")
    check("data.json + home.json carry pc_outage / pc_checkin", bw.count('"pc_outage", "pc_checkin"') >= 2)

    n_ = len(RES)
    print(f"pc silent: {sum(RES)}/{n_} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
