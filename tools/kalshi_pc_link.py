"""Kalshi on the PC (team K2, 2026-11-13): fetch the Kalshi bot's status from its VM and hand it to the PC's pages and alerts.

The VM builds kalshi.json (tools/kalshi_kit/public/kalshi_status_vm.py, with the risk guard's `risk` block when
~/kalshi_jarvis/guard exists). This PC reads it through its own srv.py helper (read-only on the VM, the same reader
`python -m engine.kalshi_publish --ssh` uses; the VM's address stays in srv.py), or from a file (--src), and writes:
  <%USERPROFILE%\\.olympus>/kalshi_feed/kalshi.json   tools/pc_publish.py adds it to the site (the Kalshi page reads it first)
  data/pc_report/kalshi.json                          for the PC-served dashboard (gitignored)
and prints one line for the card. Phone alerts: the VM sends them itself every minute when it has the owner's ntfy topic
(risk.alerts_vm); only when it does not, --alerts sends them from here on the PC's topic (tools/pc_report.py's ntfy.json).
Never places, changes or arms anything; no keys; every failure is soft.

  python tools/kalshi_pc_link.py                 one fetch, save, one-line card
  python tools/kalshi_pc_link.py --alerts        ... and phone alerts from the PC when the VM sends none
  python tools/kalshi_pc_link.py --src FILE      from a kalshi.json file instead of the VM
Tests: tests/test_kalshi_vm_update.py.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
PUB = os.path.join(ROOT, "tools", "kalshi_kit", "public")
DATA_OUT = os.path.join(ROOT, "data", "pc_report", "kalshi.json")
STATE_DIR = os.path.join(ROOT, "data", "pc_report", "kalshi_alerts")


def _load(name, file):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(PUB, file))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


def kit():
    return _load("kalshi_to_jarvis_kit", "kalshi_status_vm.py")


def guard():
    return _load("kalshi_guard_pc", "kalshi_guard.py")


def olympus_dir(env=None):
    try:
        from engine import nogithub
        return nogithub.olympus_dir(env)
    except Exception:
        env = os.environ if env is None else env
        return env.get("OLYMPUS_HOME") or os.path.join(env.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def fetch(src=None, helper=None, python=None, now=None, vm_dir=None):
    """-> (payload, error). From a file, else from the VM through srv.py."""
    k = kit()
    if src:
        return k.read(src, now)
    helper = helper or k.find_vm_helper()
    return k.vm_payload(helper, python, vm_dir=vm_dir or k.VM_DIR, now=now)


def _write(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    os.replace(tmp, path)


def save(payload, env=None, data_out=DATA_OUT):
    feed = os.path.join(olympus_dir(env), "kalshi_feed", "kalshi.json")
    _write(feed, payload)
    _write(data_out, payload)
    return [feed, data_out]


def money(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "?"
    return ("-" if v < 0 else "") + f"${abs(v):,.2f}"


def card_line(p, now=None):
    """(kind, text): the Kalshi line for the PC's card. FIX when something needs the owner."""
    now = float(now or time.time())
    if not isinstance(p, dict):
        return "..", "no Kalshi status yet"
    age = now - float(p.get("t") or 0)
    r = p.get("risk") if isinstance(p.get("risk"), dict) else None
    mode = str((r or {}).get("mode") or p.get("mode") or "?").replace("_", " ").upper()
    parts = [mode + ("" if r is None else " (risk guard)" if r.get("connected") else " (guard not connected yet)"),
             f"today {money(p.get('today_pnl'))}", f"balance {money(p.get('balance'))}"]
    if r:
        lim, room = r.get("limits") or {}, r.get("room") or {}
        parts.append(f"loss room {money(room.get('stop'))} of {money(lim.get('daily_stop_usd'))}")
    kind = "OK"
    if age > 900:
        kind, parts = "FIX", [f"last Kalshi status {int(age // 60)} min old"] + parts
    if r and (r.get("kill") or r.get("stopped") or (r.get("unguarded") or 0) > 0):
        kind = "FIX"
        parts.insert(0, "KILL SWITCH ON" if r.get("kill") else "orders around the guard" if r.get("unguarded") else "daily stop hit")
    return kind, "; ".join(parts)


def pc_alerts(p, http=None, env=None, state_dir=STATE_DIR, say=print):
    """Phone alerts from the PC, only when the VM does not send them (risk.alerts_vm). -> (sent, why)."""
    r = p.get("risk") if isinstance(p, dict) and isinstance(p.get("risk"), dict) else {}
    if r.get("alerts_vm"):
        return 0, "the VM sends the alerts"
    try:
        from tools import pc_report
        cfg = pc_report.load_cfg(env)
    except Exception as e:
        return 0, f"no alert settings ({e.__class__.__name__})"
    if not cfg.get("topic"):
        return 0, "no alert topic on this PC (python tools/pc_report.py --setup)"

    def post(base, topic, body, title=None, priority=None, tags=None):
        return pc_report.ntfy_post(base, topic, body, title=title, priority=priority, tags=tags, http=http)

    n = guard().notify(p, home=state_dir, post=post, say=say, topic=cfg["topic"], base=cfg.get("ntfy"))
    return n, "sent from the PC"


def run_once(src=None, helper=None, alerts=False, http=None, env=None, now=None, data_out=DATA_OUT, state_dir=STATE_DIR, say=print,
             vm_dir=None):
    p, err = fetch(src, helper, now=now, vm_dir=vm_dir)
    if err or not isinstance(p, dict):
        return {"ok": False, "error": err or "no status", "card": ("..", "Kalshi: " + str(err or "no status")[:160])}
    paths = save(p, env, data_out)
    out = {"ok": True, "saved": paths, "card": card_line(p, now)}
    if alerts:
        out["alerts"] = pc_alerts(p, http=http, env=env, state_dir=state_dir, say=say)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch the Kalshi bot's status from its VM for the PC's pages and alerts (read-only).")
    ap.add_argument("--src", default=None)
    ap.add_argument("--vm-helper", default=None)
    ap.add_argument("--alerts", action="store_true")
    a = ap.parse_args(argv)
    r = run_once(src=a.src, helper=a.vm_helper, alerts=a.alerts)
    kind, text = r["card"]
    print(f"  [{kind}] KALSHI {text}")
    if r.get("alerts"):
        print(f"  [..] alerts: {r['alerts'][1]} ({r['alerts'][0]} sent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
