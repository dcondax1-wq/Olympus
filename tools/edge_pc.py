"""Edge health on the PC (2026-11-18): the small, pandas-free side of tools/edge_health.py that tools/pc_report.py imports.

  maybe_run(say)   the 15-minute hook: once an ET day after 17:00 ET (or at once when the last result is over 30 h old) it starts
                   `python tools/edge_health.py --pc` as a detached, low-priority child (~30 s of CPU: LIT re-run on the PC's own
                   NinjaTrader bars + CBOE VIX). LE_EDGE=0 = off. Research only: writes data/edge/ (gitignored), never a bot setting.
  read_tiny()      data/edge/tiny.json (<= 120 bytes, edge_health.tiny) for the PC status key "eh", or None (missing / bad / > 4 days old)

The site's chip (tools/web_public/edge_chip.js) shows "eh" on the Board, Trading and MFFU pages. A warning, not a switch.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PC_DIR = os.path.join(ROOT, "data", "edge")                                  # gitignored, machine-local
PC_TINY = os.path.join(PC_DIR, "tiny.json")
TINY_MAX = 120


def _bytes(o) -> int:
    return len(json.dumps(o, separators=(",", ":")).encode("utf-8"))


def read_tiny(path: str | None = None, now: float | None = None, max_age_s: int = 4 * 86400) -> dict | None:
    """The PC's last daily result (PC_TINY) for tools/pc_report.lite, or None when missing / bad / older than max_age_s. Never raises."""
    try:
        with open(path or PC_TINY, encoding="utf-8") as fh:
            d = json.load(fh)
        if not isinstance(d, dict) or not isinstance(d.get("z"), list) or _bytes(d) > TINY_MAX:
            return None
        if (now if now is not None else dt.datetime.now().timestamp()) - int(d.get("t") or 0) > max_age_s:
            return None
        return d
    except Exception:  # noqa: BLE001
        return None


PC_HOUR_ET = 17                              # after the session: the day's NinjaTrader bars are in data/nt_bars/
MAX_TRIES = 3


def _et(ts: float) -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(ts, ZoneInfo("America/New_York"))
    except Exception:  # noqa: BLE001
        return dt.datetime.fromtimestamp(ts, dt.timezone(dt.timedelta(hours=-5)))


def pc_due(now: float | None = None, path: str | None = None, env=None) -> tuple:
    """(due, why): once an ET day after 17:00 ET (or at once when the last result is over 30 h old); LE_EDGE=0 = off."""
    e = os.environ if env is None else env
    sw = str(e.get("LE_EDGE", "")).strip()
    if sw == "0":
        return False, "switched off (LE_EDGE=0)"
    if os.name != "nt" and sw != "1":
        return False, "runs on the Windows PC only (LE_EDGE=1 forces it)"
    now = float(now if now is not None else dt.datetime.now().timestamp())
    st = {}
    try:
        st = json.load(open(os.path.join(os.path.dirname(path or PC_TINY), "state.json"), encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    if now - float(st.get("started") or 0) < 3600:
        return False, "started under an hour ago"
    if st.get("day") == _et(now).date().isoformat() and int(st.get("tries") or 0) >= MAX_TRIES:
        return False, f"started {MAX_TRIES} times today without a result: see data/edge/edge.log"
    last = read_tiny(path, now=now, max_age_s=10 ** 9)
    age = now - int((last or {}).get("t") or 0)
    et = _et(now)
    if last and age < 30 * 3600 and (et.hour < PC_HOUR_ET or _et(int(last["t"])).date() == et.date() and _et(int(last["t"])).hour >= PC_HOUR_ET):
        return False, "done for today"
    return True, "ok"


def maybe_run(now: float | None = None, say=print, env=None, spawn_fn=None, out_dir: str = PC_DIR) -> int | None:
    """tools/pc_report.py's 15-minute hook: start the daily edge-health run as a detached, low-priority child. Research only:
    reads data/ + data/nt_bars/, writes data/edge/ (never a bot setting). Never raises."""
    try:
        e = os.environ if env is None else env
        if e.get("LE_PR_NO_NET") == "1" and spawn_fn is None:
            return None                                       # the PC report's tests: never start a real child
        ok, why = pc_due(now, path=os.path.join(out_dir, "tiny.json"), env=e)
        if not ok:
            return None
        t = float(now if now is not None else dt.datetime.now().timestamp())
        sp = os.path.join(out_dir, "state.json")
        try:
            st = json.load(open(sp, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            st = {}
        day = _et(t).date().isoformat()
        _write_json(sp, {"started": int(t), "day": day, "tries": (int(st.get("tries") or 0) if st.get("day") == day else 0) + 1})
        pid = (spawn_fn or _spawn)()
        if pid:
            say(f"  [OK]  edge health started (research only, low priority, pid {pid})")
        return pid
    except Exception as ex:  # noqa: BLE001
        say(f"  [..] edge health skipped: {ex.__class__.__name__}: {str(ex)[:120]}")
        return None


def _spawn() -> int | None:
    try:
        os.makedirs(PC_DIR, exist_ok=True)
        log = open(os.path.join(PC_DIR, "edge.log"), "a", encoding="utf-8")
        cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "edge_health.py"), "--pc"]
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "PYTHONIOENCODING": "utf-8"}
        kw = {"cwd": ROOT, "stdout": log, "stderr": log, "stdin": subprocess.DEVNULL, "env": env}
        if os.name == "nt":
            base = 0x00004000 | 0x08000000 | 0x00000200          # BELOW_NORMAL | CREATE_NO_WINDOW | NEW_PROCESS_GROUP
            try:
                return subprocess.Popen(cmd, creationflags=base | 0x01000000, **kw).pid   # + BREAKAWAY_FROM_JOB
            except OSError:
                return subprocess.Popen(cmd, creationflags=base, **kw).pid
        kw["start_new_session"] = True
        return subprocess.Popen(cmd, **kw).pid
    except Exception:  # noqa: BLE001
        return None


def _write_json(path, obj, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, default=str, **kw)
    os.replace(tmp, path)
