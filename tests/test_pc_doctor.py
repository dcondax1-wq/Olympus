"""PC DOCTOR (tools/pc_doctor.py, tools/bat/PC_DOCTOR.bat): each link of the PC -> phone report, the most likely cause, the next step.

    python -X utf8 -m tests.test_pc_doctor        (~2 s; temp folders, fake http / task / git: never the real network)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import autoupdate as AU  # noqa: E402
from tools import pc_doctor as PD  # noqa: E402

RESULTS = []
NOW = 1795400000.0
TOPIC = "nq-amber-falcon-river-7291"


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def wj(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def fake_http(feed_lines=2, up=True):
    def h(url, timeout=6.0):
        if not up:
            return None, "URLError"
        if url.endswith("/v1/health"):
            return 200, '{"healthy":true}'
        if "/json?poll=1" in url:
            return 200, "\n".join('{"id":"x","event":"message","message":"{}"}' for _ in range(feed_lines))
        return None, "URLError"
    return h


def setup(tmp, beat_age=60, report_age=300, topic=True, tested=True, nogh=True, push_ok=True, errors=()):
    root, home = os.path.join(tmp, "bot"), os.path.join(tmp, "home")
    os.makedirs(root, exist_ok=True)
    os.makedirs(home, exist_ok=True)
    pl = {"t": NOW - beat_age, "adapter": "ninjatrader", "health": {"account": {"is_live": True, "armed": True}}}
    if nogh:
        wj(os.path.join(root, "logs", "pc_hb", "heartbeat.json"), pl)
    wj(os.path.join(root, "logs", "heartbeat_last.json"), {"payload": pl, "push": {"ok": push_ok}})
    if report_age is not None:
        wj(os.path.join(root, "data", "pc_report", "last.json"), {"t": NOW - report_age, "ok": not errors, "errors": list(errors)})
    if topic:
        wj(os.path.join(home, "ntfy.json"), {"topic": TOPIC, **({"tested": {"t": NOW - 9000}} if tested else {})})
    env = {"OLYMPUS_HOME": home, "LE_NO_GITHUB": "1" if nogh else "0"}
    return root, env


def run(root, env, **kw):
    kw.setdefault("http", fake_http())
    kw.setdefault("ping", {"ok": True, "bot_running": True, "heartbeat": {}})
    kw.setdefault("task", {"exists": True, "status": "Ready", "last_run": "11/17/2026 9:00:00 PM", "last_result": "0"})
    kw.setdefault("git", lambda k, r: None)
    return PD.run(root=root, env=env, now=NOW, **kw)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="pcdoc_")
    old_ss = AU.source_status
    try:
        AU.source_status = lambda root=None, sh=None, state=None, env=None: (0, "Auto-update is ON.")
        root, env = setup(os.path.join(tmp, "a"))
        r = run(root, env)
        lv = {c["key"]: c["level"] for c in r["checks"]}
        check("all links fine: every line OK, no cause", r["ok"] and set(lv.values()) == {"OK"}, lv)
        check("the beat line says LIVE ARMED", "LIVE ARMED" in next(c["text"] for c in r["checks"] if c["key"] == "beat"))
        check("GitHub-free on: the silent heartbeat branch is called expected",
              "on purpose" in next(c["text"] for c in r["checks"] if c["key"] == "github"))

        r = run(root, env, task={"exists": False})
        check("task missing: the most likely cause is the report task, with its one install line",
              r["cause"].startswith("TASK") and "pc_report_task.ps1" in r["step"], r["cause"])
        r = run(root, env, task={"exists": True, "last_result": "2147942402", "last_run": "x"})
        check("task failing (python not found code): FIX + reinstall", r["cause"].startswith("TASK") and "failed" in r["cause"], r["cause"])
        r = run(root, env, ping=False)
        check("server down: the cause is the server (first link)", r["cause"].startswith("SERVER") and "START_BOT" in r["step"], r["cause"])

        root2, env2 = setup(os.path.join(tmp, "b"), topic=False)
        r = run(root2, env2)
        check("no alert topic: TOPIC FIX with --setup / --test", r["cause"].startswith("TOPIC") and "--setup" in r["step"], r["cause"])
        root3, env3 = setup(os.path.join(tmp, "c"))
        r = run(root3, env3)
        txt = PD.card_text(r) + json.dumps(r)
        check("the private topic never appears in the card or the JSON", TOPIC not in txt)

        root4, env4 = setup(os.path.join(tmp, "d"), report_age=4000)
        r = run(root4, env4)
        check("report late (66 min): REPORT FIX", r["cause"].startswith("REPORT") and "min ago" in r["cause"], r["cause"])
        root5, env5 = setup(os.path.join(tmp, "e"), errors=["status: HTTP 429"])
        r = run(root5, env5)
        check("ntfy refused the report: REPORT FIX shows the error", r["cause"].startswith("REPORT") and "429" in r["cause"], r["cause"])
        root6, env6 = setup(os.path.join(tmp, "f"), beat_age=3600)
        r = run(root6, env6)
        check("heartbeat 1 h old while the server runs: BEAT FIX (restart when flat)", r["cause"].startswith("BEAT")
              and "STOP_BOT" in r["step"], r["cause"])
        root7, env7 = setup(os.path.join(tmp, "g"), nogh=False, push_ok=False)
        r = run(root7, env7)
        g = next(c for c in r["checks"] if c["key"] == "github")
        check("GitHub-free off + pushes failing: FIX, the suspended account named, --github-free step",
              g["level"] == "FIX" and "suspended" in g["text"] and "--github-free" in g["step"], g)
        r = run(root, env, http=fake_http(feed_lines=0))
        n = next(c for c in r["checks"] if c["key"] == "ntfy")
        check("status channel empty for 3 h: NTFY says the report is not posting", n["level"] == "SKIP" and "nothing" in n["text"], n)
        r = run(root, env, http=fake_http(up=False))
        check("ntfy.sh unreachable: NTFY FIX", next(c for c in r["checks"] if c["key"] == "ntfy")["level"] == "FIX")

        AU.source_status = lambda root=None, sh=None, state=None, env=None: (10, "Auto-update from the backup (pc) is not connected yet.")
        r = run(root, env, git=lambda k, r_: "never" if k == "credential.interactive" else None)
        u = next(c for c in r["checks"] if c["key"] == "update")
        check("auto-update not connected: SKIP, --connect, names credential.interactive=never", u["level"] == "SKIP"
              and "--connect" in u["step"] and "credential.interactive=never" in u["text"], u)
        check("only SKIPs left: the cause is the first with a step", r["cause"].startswith("UPDATE"), r["cause"])

        # the connect's one-time fetch overrides the folder's credential.interactive=never (GCM sign-in window opens)
        seen = {}
        import subprocess as _sp
        old_run = _sp.run

        def fake_run(argv, **kw):
            seen["argv"] = list(argv)
            return _sp.CompletedProcess(argv, 0)
        AU.subprocess.run = fake_run
        try:
            AU.fetch_interactive(type("S", (), {"cwd": tmp})(), {"remote": "olympus", "branch": "pc"})
        finally:
            AU.subprocess.run = old_run
        a = seen.get("argv") or []
        check("connect fetch: -c credential.interactive=auto before fetch olympus pc",
              a[1:3] == ["-c", "credential.interactive=auto"] and a[3:] == ["fetch", "olympus", "pc"], a)

        home = os.path.join(tmp, "h")
        p = PD.github_free({"OLYMPUS_HOME": home})
        from engine import nogithub
        check("--github-free writes the marker the bot reads (nogithub.active)", os.path.exists(p)
              and nogithub.active({"OLYMPUS_HOME": home}))
    finally:
        AU.source_status = old_ss
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RESULTS)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
