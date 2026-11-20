"""The cloud PC watch (.github/workflows/pc-watch.yml + tools/pc_silent_check.py, day-quality round 3, 2026-11-20). No network.

  a. the workflow is the smallest safe one: read-only token, no commit / push / publish, no pip install, no other account,
     no cloud-monitor, code from branch pc, state in the Actions cache, the secret LE_NTFY_TOPIC passed only as an env value
  b. the schedule covers the script's window: a run within 30 min of every minute of weekday 01:30-16:00 ET, in winter AND summer time
  c. dry run (the workflow_dispatch default): a PC silent for 45 min in market hours -> "[dry] PC stopped reporting ...", nothing
     posted, no state written; a PC that posted 5 min ago -> no push; outside the window (Sat) -> no push
  d. where it goes: the secret = the private topic; without it the public status topic (plain text: no $, no account names)
    python -X utf8 -m tests.test_pc_watch
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import pc_silent_check as P  # noqa: E402

ET = ZoneInfo("America/New_York")
WF = os.path.join(ROOT, ".github", "workflows", "pc-watch.yml")
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:400]})" if detail and not cond else ""))


def cron_times(expr: str, day: dt.date) -> list:
    """UTC datetimes of one 5-field cron (only the forms used: lists, ranges, *) on one UTC day."""
    mi, hr, dom, mon, dow = expr.split()

    def vals(f, lo, hi):
        if f == "*":
            return set(range(lo, hi + 1))
        out = set()
        for part in f.split(","):
            if "-" in part:
                a, b = part.split("-")
                out |= set(range(int(a), int(b) + 1))
            else:
                out.add(int(part))
        return out
    if (day.isoweekday() % 7) not in vals(dow, 0, 6):
        return []
    return [dt.datetime(day.year, day.month, day.day, h, m, tzinfo=dt.timezone.utc) for h in sorted(vals(hr, 0, 23)) for m in sorted(vals(mi, 0, 59))]


def main() -> int:
    text = open(WF, encoding="utf-8").read()
    wf = yaml.safe_load(text)
    on = wf.get(True) or wf.get("on")                       # yaml reads the key `on` as True
    steps = wf["jobs"]["watch"]["steps"]
    runs = " ".join(str(s.get("run", "")) for s in steps)
    uses = [s.get("uses", "") for s in steps if s.get("uses")]
    check("a. read-only token (permissions: contents: read only)", wf.get("permissions") == {"contents": "read"}, wf.get("permissions"))
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    check("a. no commit, push, publish, pip install, other account or cloud-monitor in the steps",
          not any(x in body for x in ("git push", "git commit", "pip install", "gh_publish", "pc_publish", "demetrades", "cloud-monitor", "contents: write")), body[:300])
    check("a. the only command is tools/pc_silent_check.py (never fails the job)", "tools/pc_silent_check.py --out pcw" in runs and "|| true" in runs
          and runs.count("python") == 1, runs)
    co = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    check("a. code from branch pc, shallow, no stored credentials", co["with"] == {"ref": "pc", "fetch-depth": 1, "persist-credentials": False}, co["with"])
    check("a. state in the Actions cache (restore + save), never a commit", any(u.startswith("actions/cache/restore") for u in uses)
          and any(u.startswith("actions/cache/save") for u in uses), uses)
    env = next(s for s in steps if "pc_silent_check" in str(s.get("run", ""))).get("env", {})
    check("a. the secret only as LE_NTFY_TOPIC from secrets, never echoed", env.get("LE_NTFY_TOPIC") == "${{ secrets.LE_NTFY_TOPIC }}"
          and "echo $LE_NTFY_TOPIC" not in text and "LE_NTFY_TOPIC" not in runs, env)
    check("a. a 3-minute cap and a manual run that is a dry run by default",
          wf["jobs"]["watch"]["timeout-minutes"] <= 3 and on["workflow_dispatch"]["inputs"]["dry_run"]["default"] is True)
    crons = [c["cron"] for c in on["schedule"]]
    for label, day in (("winter (EST)", dt.date(2026, 12, 2)), ("summer (EDT)", dt.date(2026, 7, 15))):
        times = sorted(t for c in crons for d in (day, day + dt.timedelta(days=1)) for t in cron_times(c, d))
        gaps = []
        start = dt.datetime(day.year, day.month, day.day, 1, 30, tzinfo=ET)
        for k in range(0, 14 * 60 + 31, 5):
            t = start + dt.timedelta(minutes=k)
            nxt = next((x for x in times if x >= t), None)
            if nxt is None or (nxt - t).total_seconds() > 30 * 60:
                gaps.append(t.strftime("%H:%M ET"))
        check(f"b. {label}: a run within 30 min of every minute of 01:30-16:00 ET", not gaps, gaps[:5])
    runs_day = sum(len(cron_times(c, dt.date(2026, 12, 2))) for c in crons)
    check("b. at most 36 runs a weekday (~740 billed minutes a month), none on the weekend",
          runs_day <= 36 and not any(cron_times(c, dt.date(2026, 12, 5)) for c in crons), runs_day)

    out = tempfile.mkdtemp(prefix="le_pcwatch_")
    try:
        now = int(dt.datetime(2026, 12, 2, 10, 0, tzinfo=ET).timestamp())
        feed = {"ntfy": "https://ntfy.example", "topic": "status-topic"}
        posted = []

        def get_with(last_t):
            def get(url, **_k):
                if "/status-topic/" in url and last_t:
                    msg = {"event": "message", "time": last_t, "message": json.dumps({"kind": "le-live", "reporter": {"t": last_t}})}
                    return 200, json.dumps(msg) + "\n"
                return 200, ""
            return get

        def post(url, body, headers, **_k):
            posted.append((url, body, headers))
            return 200, ""
        said = []
        s = dict(P.notify.settings())
        s["pc_silent"] = True
        r = P.run(out, now=now, env={}, get=get_with(now - 45 * 60), post=post, hb={"present": False}, dry=True, say=said.append, feed=feed, s=s)
        check("c. dry run: a PC silent 45 min in market hours -> it would push 'PC stopped reporting'",
              any(x.startswith("[dry] PC stopped reporting") for x in said) and r["msgs"], said)
        check("c. dry run: nothing posted, no state file written", posted == [] and not os.listdir(out), (posted, os.listdir(out)))
        said.clear()
        r = P.run(out, now=now, env={}, get=get_with(now - 5 * 60), post=post, hb={"present": False}, dry=True, say=said.append, feed=feed, s=s)
        check("c. a PC that posted 5 min ago: no push", not r["msgs"], said)
        sat = int(dt.datetime(2026, 12, 5, 10, 0, tzinfo=ET).timestamp())
        r = P.run(out, now=sat, env={}, get=get_with(sat - 600 * 60), post=post, hb={"present": False}, dry=True, say=said.append, feed=feed, s=s)
        check("c. Saturday: no push (outside the window)", not r["msgs"])
        r = P.run(out, now=now, env={}, get=get_with(now - 45 * 60), post=post, hb={"present": False}, dry=False, say=said.append, feed=feed, s=s)
        check("c. a real run posts once and keeps its state for the next run (the cached folder)",
              len(posted) == 1 and os.path.isfile(os.path.join(out, P.STATE_NAME)), (posted, os.listdir(out)))
        url, body, headers = posted[0]
        txt = body.decode("utf-8") + " " + " ".join(str(v) for v in headers.values())
        check("d. without the secret: the public status topic, plain text (no $, no account names)",
              url == "https://ntfy.example/status-topic" and "$" not in txt and not any(n in txt for n in ("Zlarior", "ATLAS", "MFFU")), (url, txt))
        d = P.dest({"LE_NTFY_TOPIC": "my-private-topic"}, feed)
        check("d. with the secret: the private topic", d == {"base": "https://ntfy.example", "topic": "my-private-topic", "private": True}, d)
    finally:
        shutil.rmtree(out, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
