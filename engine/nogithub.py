"""GitHub-free mode for the PC bot (owner 2026-11-10: the GitHub account is gone and stays gone).

Off by default. On when the environment has LE_NO_GITHUB=1 or the file %USERPROFILE%\\.olympus\\no_github exists (PUBLISH_NQ.bat
makes it; UNDO_PUBLISH_NQ.bat removes it). When on, nothing in the bot talks to GitHub:
  * the heartbeat still runs (same payload, same bars) but "pushes" to the local folder logs/pc_hb/ (local_push), which
    tools/pc_publish.py reads instead of the heartbeat branch;
  * the phone live.json push and the phone remote control (control branch) stay off; the git auto-update stays off
    only from origin (the lost account): from the backup repo in update_source.json it runs (2026-11-14,
    engine/autoupdate.py source(), docs/AUTO_UPDATE.md).
It touches no trading code: strategy, sizing, orders, live_model*.json are exactly the same. Never raises.
"""
from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HB_DIR = os.path.join(ROOT, "logs", "pc_hb")        # logs/ is gitignored
MARKER = "no_github"


def olympus_dir(env=None) -> str:
    env = os.environ if env is None else env
    return env.get("OLYMPUS_HOME") or os.path.join(env.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def active(env=None) -> bool:
    env = os.environ if env is None else env
    v = env.get("LE_NO_GITHUB")
    if v is not None and v != "":
        return v == "1"
    try:
        return os.path.exists(os.path.join(olympus_dir(env), MARKER))
    except Exception:
        return False


def _write(path: str, data: bytes):
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    from .fsutil import replace as _r       # retried on a Windows / OneDrive lock (tests.test_selfheal)
    _r(tmp, path)


def local_push(payload: dict, files: dict | None = None, dest: str | None = None, **_kw) -> dict:
    """Drop-in for heartbeat.push: write heartbeat.json (+ the bar files) into a local folder. {"ok", "local": True}."""
    t0 = time.monotonic()
    try:
        d = dest or HB_DIR
        os.makedirs(d, exist_ok=True)
        for name, raw in (files or {}).items():
            if raw:
                _write(os.path.join(d, os.path.basename(name)), raw)
        _write(os.path.join(d, "heartbeat.json"), json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8"))
        return {"ok": True, "local": True, "attempts": 1, "took_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "local": True, "error": f"{e.__class__.__name__}: {e}"[:160], "attempts": 1}


def read_local(now: float | None = None, files=(), src: str | None = None) -> dict:
    """What heartbeat.read returns, from the local folder: {"present", "age_s", "silent", ...payload, "files": {name: bytes}}."""
    now = time.time() if now is None else now
    d = src or HB_DIR
    try:
        with open(os.path.join(d, "heartbeat.json"), "rb") as fh:
            hb = json.loads(fh.read().decode("utf-8"))
    except Exception as e:
        return {"present": False, "reason": f"no local heartbeat ({e.__class__.__name__})"}
    if files:
        hb["files"] = {}
        for n in files:
            try:
                with open(os.path.join(d, n), "rb") as fh:
                    hb["files"][n] = fh.read()
            except OSError:
                hb["files"][n] = None
    age = max(0.0, now - float(hb.get("t") or 0))
    every = float(hb.get("every_s") or 300)
    hb.update(present=True, age_s=int(age), silent=bool(hb.get("running")) and age > max(900.0, 3 * every))
    return hb
