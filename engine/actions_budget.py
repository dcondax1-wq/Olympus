"""GitHub Actions minutes for the cloud monitor (2026-10-29): the private repo gets 2,000 free minutes a month and the
monitor + fast-entry watcher use ~1,800 of them (.github/workflows/cloud-monitor.yml). When they run out GitHub simply
stops starting the jobs: the phone's paper ledger and the "PC silent" alarm go blind until the month resets. Instead the
monitor degrades by itself before that:

  every run   tools/cloud_monitor.py on_run(): this month's estimate in state.json "actions" (runs x the billed minutes of
              one job: the monitor step's own seconds + JOB_OVERHEAD_S of checkout / setup / install / publish, rounded up
              to the minute like GitHub bills a job) + the watcher's own minutes (dash/watch.json, tools/lit_watch.py).
              Written to budget.json on the dashboard branch: {"month", "used_min", "saver", "t", "text"}.
  saver mode  at SAVER_FRAC (85%) of FREE_MIN: the workflow's guard step reads budget.json (curl, 10 s; unreadable or another
              month = no change) and keeps only the 01:30 ET night check and the first run of each hour in the session
              (keep_run); the extra half-hour and midday runs are skipped (~half the minutes). The PC's own trading never
              depends on the cloud.
  rollover    a new ET month starts at 0 (saver off); GitHub's included minutes reset with the billing cycle (about the 1st).
Counted once per GitHub run id (the watcher re-runs the monitor inside the same job: its minutes come from watch.json).
Never raises into the monitor.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
FREE_MIN = 2000
SAVER_FRAC = 0.85
JOB_OVERHEAD_S = 50                      # checkout + setup-python + pip + the publish steps of one job (observed ~40-60 s)
LULL = (690, 810)                        # 11:30-13:30 ET: the workflow's midday lull


def month_of(t) -> str:
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%Y-%m")


def billed_min(run_s: float) -> int:
    return max(1, math.ceil((float(run_s or 0) + JOB_OVERHEAD_S) / 60.0))


def add_run(s: dict | None, now, run_s: float, watch_min: float | None = None, run_id: str | None = None) -> dict:
    """The state after one monitor run (a new ET month starts again at 0; the same run id is counted once)."""
    s = dict(s or {})
    m = month_of(now)
    if s.get("month") != m:
        s = {"month": m, "runs": 0, "min": 0, "watch_min": 0.0}
    if run_id is None or s.get("last_run_id") != str(run_id):
        s["runs"] = int(s.get("runs") or 0) + 1
        s["min"] = int(s.get("min") or 0) + billed_min(run_s)
        if run_id is not None:
            s["last_run_id"] = str(run_id)
    if watch_min is not None:
        s["watch_min"] = round(float(watch_min), 1)
    return s


def _next_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    d = dt.date(y + (mo == 12), mo % 12 + 1, 1)
    return f"{d:%b} {d.day}"


def estimate(s: dict | None, now) -> dict:
    s = s or {}
    m = month_of(now)
    if s.get("month") != m:
        s = {"month": m, "runs": 0, "min": 0, "watch_min": 0.0}
    used = int(round(int(s.get("min") or 0) + float(s.get("watch_min") or 0)))
    saver = used >= SAVER_FRAC * FREE_MIN
    nxt = _next_month(m)
    text = (f"GitHub Actions: about {used:,} of the {FREE_MIN:,} free minutes used this month ({int(s.get('runs') or 0)} runs). "
            + (f"Saver mode on: the cloud monitor runs once an hour (night check kept) until the minutes reset ({nxt})."
               if saver else f"Fine until {nxt}."))
    return {"month": m, "used_min": used, "runs": int(s.get("runs") or 0), "watch_min": float(s.get("watch_min") or 0),
            "free_min": FREE_MIN, "saver": bool(saver), "resets": nxt, "text": text}


def keep_run(t, saver: bool) -> bool:
    """Saver mode keeps the night check (before 02:00 ET) and the first run of each hour outside the midday lull."""
    if not saver:
        return True
    e = dt.datetime.fromtimestamp(int(t), ET)
    mod = e.hour * 60 + e.minute
    if mod < 120:
        return True
    if LULL[0] <= mod < LULL[1]:
        return False
    return e.minute < 30


def _watch_min(out: str, month: str) -> float | None:
    try:
        with open(os.path.join(out, "watch.json"), encoding="utf-8") as fh:
            W = json.load(fh)
        return float(W.get("used_s") or 0) / 60.0 if W.get("month") == month else 0.0
    except Exception:
        return None


def on_run(out: str, prev: dict | None, now, run_s: float, env=None) -> dict:
    """tools/cloud_monitor.py, every run: the new state.json "actions" block + <out>/budget.json. Only a GitHub run counts
    (GITHUB_RUN_ID); a local dry run returns the estimate unchanged."""
    env = os.environ if env is None else env
    rid = env.get("GITHUB_RUN_ID")
    s = dict(prev or {})
    if rid:
        s = add_run(s, now, run_s, _watch_min(out, month_of(now)), run_id=rid)
    e = estimate(s, now)
    try:
        with open(os.path.join(out, "budget.json"), "w", encoding="utf-8") as fh:
            json.dump({"month": e["month"], "used_min": e["used_min"], "saver": e["saver"], "t": int(now), "text": e["text"]}, fh)
    except Exception:
        pass
    return {**s, "estimate": e}
