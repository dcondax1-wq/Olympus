"""POST-UPDATE CHECK (night-verify 2026-11-23): right after the PC updated itself and the bot server restarted, check that each
new piece is alive on THIS machine and send ONE phone message: "Update verified: N/N OK" or "Update: <piece> needs you -> <fix>".

READ-ONLY: it never writes a trading file, never arms, never starts / stops anything, never sends a test alert. Each check runs
in its own daemon thread with a time box; the whole run is capped at BUDGET_S (25 s) and never raises. A piece that is not on
this checkout yet (another night's branch) reports "not installed" instead of failing.

Where it runs: server.py's autostart, in a background thread DELAY_S after a restart that follows an auto-update (the restart
marker of engine/autoupdate.py), so it never delays the restart or the bot's resume. UPDATE.bat (engine/ops_checks
--after-update) prints the same lines. Result: logs/post_update.json (TRADE_HOME's status shows it).

    python -X utf8 -m engine.post_update_check            print the checks (no phone message)
    python -X utf8 -m engine.post_update_check --send     the same + the one phone message (what the restart does)
Tests: python -X utf8 -m tests.test_post_update_check (fakes only)
"""
from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "logs", "post_update.json")
BUDGET_S = 25.0
CHECK_S = 8.0
DELAY_S = 90
NTFY_CAP, NTFY_WARN = 250, 200
OK, FIX, NOT_INSTALLED, INFO = "ok", "fix", "not installed", "info"
CLOCK_FIX = "right-click FIX_CLOCK.bat > Run as administrator (or MONDAY_SETUP.bat)"
REPORT_TASK = "OlympusPCReport"
# pieces of tonight's combined update that may live on other branches: (label, module)
OPTIONAL = (("Payout autopilot", "engine.payout_autopilot"), ("Fleet manager", "engine.fleet_manager"),
            ("Rules watch", "engine.rules_watch"), ("State pulse", "engine.state_pulse"), ("Win guard", "engine.win_guard"),
            ("Task audit", "engine.task_audit"), ("Zero-touch (MONDAY_SETUP)", "engine.monday"),
            ("Recovery matrix", "engine.recovery"), ("Fault notes", "engine.fault_note"))
CORE = ("engine.readiness", "engine.arm_report", "engine.alert_bus", "engine.keepalive", "engine.self_heal", "engine.notify")


def row(name, status, text, fix="") -> dict:
    return {"name": name, "status": status, "text": str(text)[:160], "fix": str(fix)[:160]}


class Ctx:
    """What the checks read / run; tests pass fakes."""

    def __init__(self, root=ROOT, windows=None, run=None, connect=None, imp=None, now=None):
        self.root = root
        self.windows = (os.name == "nt") if windows is None else windows
        self.run = run or self._run
        self.connect = connect or self._connect
        self.imp = imp or importlib.import_module
        self.now = time.time() if now is None else float(now)

    @staticmethod
    def _run(cmd, timeout=6):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return r.returncode, r.stdout or ""
        except Exception as e:  # noqa: BLE001
            return 1, f"{e.__class__.__name__}"

    @staticmethod
    def _connect(host, port=443, timeout=3.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False


# ------------------------------------------------------------------------------------------------ the checks
def c_modules(c):
    bad = []
    for m in CORE:
        try:
            c.imp(m)
        except Exception as e:  # noqa: BLE001
            bad.append(f"{m.split('.')[-1]} ({e.__class__.__name__})")
    return [row("Core modules", FIX if bad else OK, f"do not load: {', '.join(bad)}" if bad else f"{len(CORE)} load",
                "UPDATE.bat once; still red: send Claude a photo" if bad else "")]


def c_optional(c):
    out = []
    for label, m in OPTIONAL:
        try:
            c.imp(m)
            out.append(row(label, OK, "loads"))
        except ModuleNotFoundError as e:
            if getattr(e, "name", None) == m:
                out.append(row(label, NOT_INSTALLED, "not on this version yet"))
            else:
                out.append(row(label, FIX, f"a part it needs is missing ({e.name})", "UPDATE.bat once (it installs packages)"))
        except Exception as e:  # noqa: BLE001
            out.append(row(label, FIX, f"does not load ({e.__class__.__name__})", "send Claude a photo of HEALTH_CHECK.bat"))
    return out


def c_clock(c):
    if not c.windows:
        return [row("Clock task", INFO, "Windows only")]
    code, _ = c.run([os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "schtasks.exe"), "/query", "/tn", "OlympusClock"])
    return [row("Clock task", OK, "OlympusClock syncs the clock every 15 min") if code == 0 else
            row("Clock task", FIX, "the OlympusClock task is missing", CLOCK_FIX)]


def c_tasks(c):
    if not c.windows:
        return [row("PC report task", INFO, "Windows only")]
    code, out = c.run(["schtasks", "/query", "/fo", "CSV", "/v", "/nh"], timeout=10)
    if code != 0:
        return [row("PC report task", FIX, "Task Scheduler did not answer", "restart the PC once")]
    lines = [ln for ln in out.splitlines() if "pc_report" in ln.lower() or REPORT_TASK.lower() in ln.lower()]
    names = sorted({ln.split('","')[1].strip('"') if '","' in ln else ln[:40] for ln in lines})
    if not names:
        return [row("PC report task", FIX, f"{REPORT_TASK} is missing (no status to the phone)", "double-click ONE_TIME_SETUP.bat")]
    if len(names) > 1:
        return [row("PC report task", FIX, f"{len(names)} copies run ({', '.join(n.lstrip(chr(92)) for n in names)[:90]}): double posts",
                    f"Task Scheduler: keep {REPORT_TASK}, delete the others")]
    return [row("PC report task", OK, f"one copy ({names[0].lstrip(chr(92))})")]


def c_readiness(c):
    rd = c.imp("engine.readiness")
    v = rd.ready_verdict()
    return [row("Readiness", OK, rd.headline(v)[:120])]


def c_arm(c):
    p = os.path.join(c.root, "data", "arm_status.json")
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except FileNotFoundError:
        return [row("START summary", FIX, "no START summary on this PC yet", "START BOT (or MONDAY_SETUP.bat) and type I ACCEPT LIVE RISK")]
    except Exception as e:  # noqa: BLE001
        return [row("START summary", FIX, f"data/arm_status.json unreadable ({e.__class__.__name__})", "START BOT again (it rewrites it)")]
    rows = [r for r in (d.get("rows") or []) if isinstance(r, dict)]
    bad = [r.get("label") for r in rows if not r.get("armed")]
    age_h = (c.now - float(d.get("t") or 0)) / 3600.0
    txt = f"{len(rows) - len(bad)}/{len(rows)} armed at the last START ({age_h:.0f} h ago)"
    return [row("START summary", OK if not bad else FIX, txt if not bad else f"NOT armed: {', '.join(map(str, bad))[:90]}",
                "" if not bad else "START BOT and do the NOT ARMED line's fix")]


def c_alerts(c):
    out = []
    ab = c.imp("engine.alert_bus")
    cfg = ab.config()
    hosts = []
    if cfg.get("telegram"):
        hosts.append(("Telegram", "api.telegram.org"))
    if cfg.get("discord"):
        hosts.append(("Discord", "discord.com"))
    nt = c.imp("engine.notify")
    if (nt.alert_cfg() or {}).get("topic"):
        hosts.append(("ntfy", "ntfy.sh"))
    if not hosts:
        return [row("Phone alerts", FIX, "no phone channel set up", "TRADE_HOME.bat > 5 (Telegram / Discord)")]
    down = [n for n, h in hosts if not c.connect(h)]
    out.append(row("Phone alerts", FIX if down else OK, (f"cannot reach {', '.join(down)}" if down else
                   f"{', '.join(n for n, _ in hosts)} reachable (nothing sent)"), "check the PC's internet" if down else ""))
    return out


def c_ntfy_budget(c):
    p = os.path.join(c.root, "logs", "notify", "instant_sent.json")
    try:
        with open(p, encoding="utf-8") as fh:
            st = json.load(fh)
    except FileNotFoundError:
        return [row("ntfy budget", OK, "0 posts today")]
    day = time.strftime("%Y-%m-%d", time.gmtime(c.now))
    n = int(((st or {}).get("ntfy_days") or {}).get(day) or 0)
    return [row("ntfy budget", OK if n < NTFY_WARN else FIX, f"{n}/{NTFY_CAP} posts today (UTC)",
                "" if n < NTFY_WARN else "too many posts today: alerts may stop until 00:00 UTC; tell Claude")]


def c_files(c):
    bad = []
    for d in ("data", "logs"):
        p = os.path.join(c.root, d)
        if os.path.isdir(p) and not os.access(p, os.W_OK):
            bad.append(d + "/")
    for rel in ("data/payout_plan.json", "data/fleet.json", "data/keepalive.json", "data/accounts.json", "research/lit/mffu_rules.json"):
        p = os.path.join(c.root, *rel.split("/"))
        if os.path.exists(p) and not os.access(p, os.W_OK):
            bad.append(rel)
    return [row("Files writable", FIX if bad else OK, f"read-only: {', '.join(bad)}" if bad else "data/, logs/ and the account files",
                "right-click the bot folder > Properties > untick Read-only (or run CLEAN_PC.bat)" if bad else "")]


def c_keepalive(c):
    ka = c.imp("engine.keepalive")
    C = ka.load_config(None)
    on = sorted(k for k, v in (C.get("accounts") or {}).items() if v is True)
    if not hasattr(ka, "start_consent"):
        return [row("Keep-alive", OK if on else INFO, f"ON for {', '.join(on)}" if on else "OFF (KEEPALIVE_ON.bat)")]
    cons = (C.get("consent") or {}).get("day")
    return [row("Keep-alive", OK if on else INFO, (f"ON for {', '.join(on)}" + (f" (your START phrase {cons})" if cons else ""))
                if on else "OFF: the next START with the phrase turns it on")]


def c_hooks(c):
    sh = c.imp("engine.self_heal")
    names = [n for n, _ in getattr(sh, "REMEDIES", ())]
    return [row("Self-heal", OK if names else FIX, f"{len(names)} remedies hourly" if names else "no remedies", "" if names else "UPDATE.bat once")]


CHECKS = (c_modules, c_optional, c_clock, c_tasks, c_readiness, c_arm, c_alerts, c_ntfy_budget, c_files, c_keepalive, c_hooks)


def run(ctx=None, checks=CHECKS, budget_s=BUDGET_S, check_s=CHECK_S) -> dict:
    """Every check in its own thread, each at most check_s, all within budget_s. Never raises."""
    c = ctx or Ctx()
    t0 = time.monotonic()
    rows = []
    for fn in checks:
        left = budget_s - (time.monotonic() - t0)
        nm = fn.__name__[2:].replace("_", " ")
        if left <= 0:
            rows.append(row(nm, INFO, "skipped (time box)"))
            continue
        box = {}

        def go(fn=fn, box=box):
            try:
                box["r"] = fn(c)
            except Exception as e:  # noqa: BLE001
                box["e"] = e
        th = threading.Thread(target=go, name=f"post-update-{nm}", daemon=True)
        th.start()
        th.join(min(check_s, left))
        if th.is_alive():
            rows.append(row(nm, INFO, f"did not answer in {min(check_s, left):.0f} s (skipped)"))
        elif "e" in box:
            e = box["e"]
            rows.append(row(nm, FIX, f"check failed ({e.__class__.__name__}: {str(e)[:80]})", "send Claude a photo of HEALTH_CHECK.bat"))
        else:
            rows.extend(box.get("r") or [])
    return summarize(rows, time.monotonic() - t0)


def summarize(rows, secs=0.0) -> dict:
    counted = [r for r in rows if r["status"] in (OK, FIX)]
    fixes = [r for r in counted if r["status"] == FIX]
    ni = [r for r in rows if r["status"] == NOT_INSTALLED]
    n_ok = len(counted) - len(fixes)
    if not fixes:
        msg = f"Update verified: {n_ok}/{len(counted)} OK" + (f" ({len(ni)} not installed yet)" if ni else "")
    else:
        f0 = fixes[0]
        msg = f"Update: {f0['name']} needs you -> {f0['fix'] or f0['text']}" + (f" (+{len(fixes) - 1} more)" if len(fixes) > 1 else "")
    return {"t": int(time.time()), "ok": not fixes, "n_ok": n_ok, "n": len(counted), "not_installed": [r["name"] for r in ni],
            "message": msg, "rows": rows, "secs": round(secs, 1)}


def lines(res) -> list:
    tag = {OK: "[OK] ", FIX: "[FIX]", NOT_INSTALLED: "[--] ", INFO: "[..] "}
    out = [f" {tag.get(r['status'], '[..] ')} {r['name']}: {r['text']}" + (f" -> {r['fix']}" if r["status"] == FIX and r["fix"] else "")
           for r in res["rows"]]
    return out + ["", " " + res["message"]]


def save(res, path=None) -> None:
    try:
        p = path or OUT
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
        os.replace(p + ".tmp", p)
    except Exception:
        pass


def last(path=None) -> dict | None:
    try:
        with open(path or OUT, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def send(res, sha=None, poster=None) -> str:
    """ONE private phone message (engine/notify.instant_problem, key = the update's sha: once per update). Never raises."""
    try:
        p = {"key": f"post_update:{sha or res.get('t')}", "code": "update", "title": res["message"][:90],
             "body": "\n".join(f"{r['name']}: {r['fix'] or r['text']}" for r in res["rows"] if r["status"] == FIX)[:450]
             or "Every new piece checked on this PC.", "back": bool(res.get("ok"))}
        if poster is not None:
            return poster(p) or "sent"
        from . import notify
        return notify.instant_problem(p)
    except Exception as e:  # noqa: BLE001
        return f"not sent ({e.__class__.__name__})"


def after_restart(sha=None, delay_s=DELAY_S, sleep=time.sleep, ctx=None, poster=None):
    """server.py: called in a daemon thread after an update restart. Waits delay_s (the bot resumes first), checks, saves,
    sends one message. Never raises."""
    try:
        sleep(delay_s)
        res = run(ctx)
        res["sha"] = sha
        save(res)
        res["sent"] = send(res, sha, poster)
        save(res)
        return res
    except Exception:
        return None


def start_bg(sha=None) -> bool:
    """Start after_restart in a daemon thread (never blocks the caller). Never raises."""
    try:
        threading.Thread(target=after_restart, args=(sha,), name="post-update-check", daemon=True).start()
        return True
    except Exception:
        return False


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    res = run()
    save(res)
    for ln in lines(res):
        print(ln)
    if "--send" in argv:
        print(" phone:", send(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
