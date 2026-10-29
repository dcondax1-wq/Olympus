"""Status page (competitor-features #9, 2026-10-21): 30-day uptime per part of the bot + an incident list, Upptime style,
with no extra Actions minutes.

Parts (each sample says up / down / unknown for each):
  cloud    the GitHub Actions cloud monitor ran (half-hourly 02:00-16:30 ET weekdays): a gap longer than 45 min in that
           window is counted as missed runs (found by the next run: a dead-man's switch on the watcher itself)
  surface  the Surface's heartbeat is fresh (engine/heartbeat.py; silent = older than 20 min)
  feed     NinjaTrader's 1m / 5m bars are fresh while the market is open (heartbeat health.feed; unknown when the Surface
           is silent or the market is shut)
  live     the phone live feed push works (engine/live_publish.py, heartbeat live_pub: last push ok and < 10 min old)
  update   the PC auto-update did not fail or roll back (heartbeat health.auto.update)
Samples are only taken inside the trading window (weekdays 01:30-16:30 ET). Each is weighted by the time since the last
sample (capped), so up % = time up / time watched. The store is one small dict: per ET day {part: [up_s, watched_s]}
(30 days) + open incidents + the last 60 closed incidents (start, end, what, fix).
  * cloud: tools/cloud_monitor.py calls cloud_hook(new_state, st, pc, now) every run -> state "uptime" (data.json perf).
  * PC: engine/heartbeat.py calls pc_hook(payload) on every beat -> logs/uptime_pc.json (the PC dashboard's Status page).
Read-only: it never starts, stops or routes anything; it never raises into its caller.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PC_PATH = os.path.join(ROOT, "logs", "uptime_pc.json")       # logs/ is gitignored
KEEP_DAYS = 30
KEEP_INCIDENTS = 60
CLOUD_SLOT_S = 1800                 # the cloud monitor's cron: half-hourly
CLOUD_GAP_S = 2700                  # > 45 min between runs inside the window = missed run(s)
WIN = (90, 990)                     # 01:30-16:30 ET
VERSION = 1
PARTS = [("cloud", "Cloud monitor runs"), ("surface", "Surface heartbeat"), ("feed", "NinjaTrader feed"),
         ("live", "Phone live feed"), ("update", "Auto-update")]
LABEL = dict(PARTS)
WHAT = {"cloud": "cloud monitor did not run", "surface": "Surface heartbeat silent", "feed": "NinjaTrader bars stale",
        "live": "phone live feed push failing", "update": "PC auto-update failed / rolled back"}
FIX = {"cloud": "GitHub -> Actions -> cloud-monitor: check the last run; GitHub sometimes delays scheduled runs (nothing to do "
                "if it recovered by itself)",
       "surface": "Wake the Surface, check it is on power and Wi-Fi, and that START_DASHBOARD runs (scripts/run_bot.ps1)",
       "feed": "NinjaTrader: Connections -> reconnect, and keep the MNQ 1m / 5m charts with LE_BarFeed open",
       "live": "Usually the internet or GitHub: it retries every minute; if it stays red, restart the bot (UPDATE.bat)",
       "update": "Open the PC dashboard -> Bot log; UPDATE.bat by hand after the session if it stays failed"}


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def in_window(t) -> bool:
    e = _et(t)
    m = e.hour * 60 + e.minute
    return e.weekday() < 5 and WIN[0] <= m < WIN[1]


def _day(t) -> str:
    return _et(t).date().isoformat()


def _hm(t) -> str:
    return _et(t).strftime("%a %m-%d %H:%M")


def sample_from_pc(pc: dict | None, now: int, cloud_ran: bool | None = None) -> dict:
    """{part: True / False / None} from the cloud's view of the heartbeat (heartbeat.read) or the PC's own payload."""
    pc = pc or {}
    s = {"cloud": cloud_ran}
    present = bool(pc.get("present", True)) and bool(pc.get("t"))
    age = pc.get("age_s")
    if age is None and pc.get("t"):
        age = now - int(pc["t"])
    s["surface"] = bool(present and age is not None and age <= 1200)
    h = pc.get("health") if isinstance(pc.get("health"), dict) else {}
    f = h.get("feed") or {}
    if not s["surface"] or f.get("market_open") is False or not f:
        s["feed"] = None
    else:
        a1, a5 = f.get("age_1m_s"), f.get("age_5m_s")
        fresh = (a1 is not None and a1 <= 300) or (a1 is None and a5 is not None and a5 <= 900)
        s["feed"] = bool(fresh and not f.get("stale"))
    lp = pc.get("live_pub")
    if not s["surface"] or not isinstance(lp, dict):
        s["live"] = None
    else:
        s["live"] = bool(lp.get("ok")) and (lp.get("at") is None or now - int(lp.get("at") or 0) <= 600)
    au = ((h.get("auto") or {}).get("update") or {}) if isinstance(h.get("auto"), dict) else {}
    s["update"] = None if not s["surface"] or not au else au.get("result") not in ("failed", "rolled_back")
    return s


def record(U: dict | None, sample: dict, now: int, cap_s: int, info: dict | None = None) -> dict:
    """Add one sample (weighted by the time since the last one, at most cap_s) and open / close incidents."""
    U = dict(U or {})
    U.setdefault("v", VERSION)
    days = U.setdefault("days", {})
    opn = U.setdefault("open", {})
    inc = U.setdefault("incidents", [])
    last = int(U.get("last_t") or 0)
    w = max(60, min(cap_s, now - last)) if last else min(cap_s, 300)
    d = days.setdefault(_day(now), {})
    for part, up in sample.items():
        if up is None:
            continue
        x = d.setdefault(part, [0, 0])
        x[1] += w
        x[0] += w if up else 0
        if not up and part not in opn:
            opn[part] = {"part": part, "start": now - w, "what": WHAT.get(part, part), **({"info": info.get(part)} if info and info.get(part) else {})}
        elif up and part in opn:
            o = opn.pop(part)
            inc.append({**o, "end": now, "mins": round((now - o["start"]) / 60), "label": LABEL.get(part, part), "fix": FIX.get(part)})
    U["last_t"] = now
    keep = sorted(days)[-KEEP_DAYS:]
    U["days"] = {k: days[k] for k in keep}
    U["incidents"] = inc[-KEEP_INCIDENTS:]
    return U


def cloud_gap(U: dict | None, now: int) -> dict:
    """The cloud monitor itself: count the window time since the last run beyond one slot as missed runs (an incident)."""
    U = dict(U or {})
    last = int(U.get("cloud_last") or 0)
    if last and now - last > CLOUD_GAP_S:
        missed, t = 0, last + CLOUD_SLOT_S
        while t < now - CLOUD_SLOT_S // 2:      # the slot of this run itself is not missed
            if in_window(t):
                missed += 1
                x = U.setdefault("days", {}).setdefault(_day(t), {}).setdefault("cloud", [0, 0])
                x[1] += CLOUD_SLOT_S
            t += CLOUD_SLOT_S
        if missed:
            U.setdefault("incidents", []).append({"part": "cloud", "label": LABEL["cloud"], "start": last + CLOUD_SLOT_S, "end": now,
                                                  "mins": round((now - last - CLOUD_SLOT_S) / 60), "what": f"{missed} cloud monitor run(s) missed",
                                                  "fix": FIX["cloud"]})
    U["cloud_last"] = now
    return U


def cloud_hook(new_state: dict, st: dict, pc: dict | None, now: int | None = None) -> dict | None:
    """tools/cloud_monitor.py: once per run. Never raises."""
    try:
        now = int(now or time.time())
        U = cloud_gap(st.get("uptime"), now)
        if in_window(now):
            U = record(U, sample_from_pc(pc, now, cloud_ran=True), now, CLOUD_SLOT_S,
                       info={"surface": (pc or {}).get("reason")} if not (pc or {}).get("present") else None)
        new_state["uptime"] = U
        return U
    except Exception as e:                              # never fails the cloud run
        print("uptime failed:", e.__class__.__name__, e)
        return None


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def pc_hook(payload: dict, path: str | None = None, now: int | None = None) -> dict | None:
    """engine/heartbeat.py: on every beat (the PC's own view: no cloud part). Never raises."""
    try:
        path = path or PC_PATH
        now = int(now or payload.get("t") or time.time())
        if not in_window(now):
            return None
        s = sample_from_pc({**payload, "present": True, "age_s": 0}, now, cloud_ran=None)
        s["surface"] = bool(payload.get("running"))           # on the PC: the bot is running (the server is up: it beats)
        U = record(_load(path), s, now, 600)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(U, fh, separators=(",", ":"))
        from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
        _fs_replace(tmp, path)
        return U
    except Exception:
        return None


def view(U: dict | None, now: int | None = None, parts=None, days=KEEP_DAYS) -> dict:
    """The Status page: one row per part (today's state, 30-day up %, one square per day) + incidents, newest first."""
    now = int(now or time.time())
    U = U or {}
    D = U.get("days") or {}
    today = _et(now).date()
    cal = [(today - dt.timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    cal = [d for d in cal if dt.date.fromisoformat(d).weekday() < 5]
    rows = []
    for part, label in PARTS:
        if parts and part not in parts:
            continue
        sq, up, tot = [], 0, 0
        for d in cal:
            x = (D.get(d) or {}).get(part)
            if x and x[1]:
                up += x[0]
                tot += x[1]
                sq.append([d, round(100.0 * x[0] / x[1], 1)])
            else:
                sq.append([d, None])
        o = (U.get("open") or {}).get(part)
        last = next((s for s in reversed(sq) if s[1] is not None), None)
        state = "down" if o else ("up" if last and last[1] >= 99 else "degraded" if last else "unknown")
        rows.append({"id": part, "label": label, "state": state, "uptime": round(100.0 * up / tot, 2) if tot else None,
                     "watched_h": round(tot / 3600, 1), "days": sq, "fix": FIX.get(part),
                     "since": o["start"] if o else None, "since_hm": _hm(o["start"]) if o else None})
    inc = [{**i, "start_hm": _hm(i["start"]), "end_hm": _hm(i["end"]) if i.get("end") else None} for i in (U.get("incidents") or [])]
    for o in (U.get("open") or {}).values():
        inc.append({**o, "label": LABEL.get(o["part"], o["part"]), "end": None, "start_hm": _hm(o["start"]), "end_hm": None,
                    "mins": round((now - o["start"]) / 60), "fix": FIX.get(o["part"]), "open": True})
    inc.sort(key=lambda i: i["start"], reverse=True)
    watched = [r for r in rows if r["uptime"] is not None]
    worst = min(watched, key=lambda r: r["uptime"]) if watched else None
    down = [r["label"] for r in rows if r["state"] == "down"]
    text = ("Down now: " + ", ".join(down)) if down else (
        f"All parts up. 30 days: worst {worst['label']} {worst['uptime']:.1f}%" if worst else "No status samples yet")
    return {"v": VERSION, "t": now, "parts": rows, "incidents": inc[:40], "text": text, "level": "bad" if down else "good" if watched else None,
            "window": "weekdays 01:30-16:30 ET", "last_t": U.get("last_t")}
