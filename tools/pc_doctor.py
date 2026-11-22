"""PC DOCTOR (double-click PC_DOCTOR.bat): why the phone hears nothing from the PC, link by link, with the one fix each.

Owner 2026-11-17: the PC has not reported (heartbeat branch, ntfy) since 2026-11-07 while the bot page shows LIVE ARMED.
It only LOOKS (reads files, asks the local bot server, Task Scheduler and ntfy.sh's health page): it never starts, stops, arms
or routes anything, never sends a push, never prints the private alert topic, a login or an account id.

The links, in the order the report travels (the first red one is "the most likely cause"):
   1 SERVER    the bot server answers on this PC (http://127.0.0.1:8766/api/health/ping) and the bot runs (LIVE / SIM / PAPER, armed)
   2 BEAT      the bot's own heartbeat on this PC is fresh (logs/pc_hb/heartbeat.json in GitHub-free mode, else
               logs/heartbeat_last.json): the 5-minute beat everything else reads
   3 GITHUB    GitHub-free mode (engine/nogithub.py). The first GitHub account was suspended on 2026-11-08: the heartbeat
               branch can NEVER update again (that silence is expected). Without the mode the bot keeps pushing to it and failing.
   4 TASK      the Windows task OlympusPCReport (every 15 minutes: tools/pc_report.py -> ntfy)
   5 REPORT    the report's own last run (data/pc_report/last.json): when, and whether ntfy took it
   6 TOPIC     your private alert topic exists (%USERPROFILE%\\.olympus\\ntfy.json) and had its test push (never shown here)
   7 NTFY      ntfy.sh answers from this PC; the site's public status channel got something in the last 3 hours
   8 UPDATE    auto-update from the backup repo is connected (engine/autoupdate.py --source-status); this folder's git
               setting credential.interactive=never (BOTS_BACK.bat) used to block the one-time sign-in window
   9 HEAL      (night-selfheal 2026-11-20) the self-heal's last run (engine/self_heal.py, hourly from the report task): what it
               fixed by itself this week and what it could NOT fix. Only shown once it ran on this PC.

    python -X utf8 tools/pc_doctor.py             the card + the most likely cause + the exact next step
    python -X utf8 tools/pc_doctor.py --json      the same as JSON (the bot server's GET /api/pc/doctor)
    python -X utf8 tools/pc_doctor.py --offline   no network check (ntfy.sh)
    python -X utf8 tools/pc_doctor.py --heal      the self-heal's dry run: what it would fix now (changes nothing)
    python -X utf8 tools/pc_doctor.py --heal --apply   fix it now (the same run the report task makes every hour)
Tests: tests/test_pc_doctor.py (temp folders, fake http / task / git, never the real network).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PORT = int(os.environ.get("PORT") or 8766)
HB_STALE_S = 15 * 60
REPORT_LATE_S = 20 * 60
FEED_SINCE = "3h"
SUSPENDED = "2026-11-08"
LAST_GITHUB_BEAT = "2026-11-07"
TASK = "OlympusPCReport"
ORDER = ("server", "beat", "task", "report", "topic", "ntfy", "github", "update", "heal")


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _num(x):
    try:
        v = float(x)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _ago(s) -> str:
    if s is None:
        return "never"
    s = max(0, int(s))
    if s < 90:
        return f"{s} s ago"
    if s < 5400:
        return f"{s // 60} min ago"
    if s < 2 * 86400:
        return f"{s // 3600} h ago"
    return f"{s // 86400} days ago"


def _c(key, label, level, text, fix="", step=""):
    return {"key": key, "label": label, "level": level, "text": text, "fix": fix, "step": step}


# ------------------------------------------------------------------------------------------------ the facts (fakeable)
def http_get(url, timeout=6.0):
    """(status, text) or (None, error words). Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "olympus-pc-doctor/1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace")
    except Exception as e:
        return None, e.__class__.__name__


def task_info(run=None):
    """Windows: {"exists", "status", "last_run", "last_result"}; None elsewhere. LE_PD_T_TASK=missing|ok|fail for tests."""
    t = os.environ.get("LE_PD_T_TASK")
    if t:
        return {"exists": t != "missing", "status": "Ready", "last_run": "", "last_result": "0" if t == "ok" else "1"}
    if os.name != "nt":
        return None
    try:
        r = (run or subprocess.run)(["schtasks", "/Query", "/TN", TASK, "/FO", "LIST", "/V"], capture_output=True, text=True,
                                    timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return {"exists": None}
    if r.returncode != 0:
        return {"exists": False}
    out = {"exists": True}
    for ln in (r.stdout or "").splitlines():
        k, _, v = ln.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "status":
            out["status"] = v
        elif k == "last run time":
            out["last_run"] = v
        elif k == "last result":
            out["last_result"] = v
    return out


def git_cfg(key, root=ROOT):
    try:
        from engine import generated_files
        git = generated_files.git_exe()
    except Exception:
        git = "git"
    try:
        r = subprocess.run([git, "-C", root, "config", "--local", "--get", key], capture_output=True, text=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        return (r.stdout or "").strip() or None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ the checks
def check_server(ping):
    if ping is None:
        return _c("server", "SERVER", "FIX", "the bot server does not answer on this PC: nothing can report",
                  "Start the bot server.", "double-click START_BOT.bat")
    if not ping.get("bot_running"):
        return _c("server", "SERVER", "FIX", "the bot server runs but the bot is stopped", "Start the bot.",
                  "double-click START_BOT.bat (you type the live phrase yourself)")
    return _c("server", "SERVER", "OK", "the bot server answers and the bot runs")


def _beat_mode(pl):
    h = (pl or {}).get("health") or {}
    a = h.get("account") or {}
    kind = "LIVE" if a.get("is_live") else ("SIM" if (pl or {}).get("adapter") == "ninjatrader" else "PAPER")
    return kind + (" ARMED" if a.get("armed") else "")


def check_beat(root, now, ping):
    pc_hb = _read(os.path.join(root, "logs", "pc_hb", "heartbeat.json")) or {}
    last = _read(os.path.join(root, "logs", "heartbeat_last.json")) or {}
    cands = [(t, pl, src) for t, pl, src in ((_num(pc_hb.get("t")), pc_hb, "logs/pc_hb"),
                                            (_num((last.get("payload") or {}).get("t")), last.get("payload") or {}, "logs/heartbeat_last.json"))
             if t]
    hbp = (ping or {}).get("heartbeat") or {}
    if not cands:
        return _c("beat", "BEAT", "FIX", "no heartbeat file on this PC: the heartbeat thread never ran (LE_HEARTBEAT is not 1?)",
                  "Start the bot the normal way (it sets LE_HEARTBEAT=1).", "STOP_BOT.bat when flat, then START_BOT.bat"), None, last
    t, pl, src = max(cands, key=lambda x: x[0])
    age = now - t
    mode = _beat_mode(pl)
    if age > HB_STALE_S:
        why = f" (last error: {str(hbp.get('last_error'))[:80]})" if hbp.get("last_error") else ""
        return _c("beat", "BEAT", "FIX", f"the bot's heartbeat is {_ago(age)} ({src}, {mode}){why}: the report has nothing new to send",
                  "The heartbeat thread is stuck or the bot was started without it.", "when flat: STOP_BOT.bat, then START_BOT.bat"), pl, last
    return _c("beat", "BEAT", "OK", f"heartbeat {_ago(age)} ({src}): the bot says {mode}"), pl, last


def check_github(env, last):
    try:
        from engine import nogithub
        on = nogithub.active(env)
    except Exception:
        on = None
    push = (last or {}).get("push") or {}
    if on:
        return _c("github", "GITHUB", "OK", f"GitHub-free mode ON: the heartbeat stays on this PC. The GitHub heartbeat branch is "
                                            f"silent since {LAST_GITHUB_BEAT} on purpose (that account was suspended {SUSPENDED})")
    failing = push.get("ok") is False
    return _c("github", "GITHUB", "FIX" if failing else "SKIP",
              f"GitHub-free mode is OFF: the bot still pushes its heartbeat to the suspended GitHub account ({SUSPENDED})"
              + (" and every push fails" if failing else "") + ". The GitHub heartbeat branch can never update again",
              "Turn GitHub-free mode on (it only stops the GitHub pushes; trading is untouched; applies at the next bot start).",
              "python -X utf8 tools/pc_doctor.py --github-free   then, when flat, STOP_BOT.bat and START_BOT.bat")


TASK_STEP = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\pc_report_task.ps1"


def check_task(info):
    if info is None:
        return _c("task", "TASK", "..", "Task Scheduler is Windows only (not this machine)")
    if info.get("exists") is None:
        return _c("task", "TASK", "..", "Task Scheduler could not be read")
    if not info.get("exists"):
        return _c("task", "TASK", "FIX", f"the 15-minute report task {TASK} is NOT installed: no ntfy status, no phone alerts. "
                                         "SETUP_EVERYTHING skips the step that installs it when both evals are already armed",
                  "Install the report task (it only reads the bot's files and posts to ntfy).", TASK_STEP)
    lr = str(info.get("last_result") or "")
    if lr and lr not in ("0", "0x0", "267009", "267011"):
        return _c("task", "TASK", "FIX", f"{TASK} is installed but its last run failed (result {lr}, {info.get('last_run') or '?'})",
                  "Re-install it (it finds python.exe again).", TASK_STEP)
    return _c("task", "TASK", "OK", f"{TASK} installed ({info.get('status') or 'ready'}, last run {info.get('last_run') or '?'})")


def check_report(root, now):
    rec = _read(os.path.join(root, "data", "pc_report", "last.json"))
    if not isinstance(rec, dict) or not _num(rec.get("t")):
        return _c("report", "REPORT", "FIX", "the 15-minute report has never run on this PC",
                  "Run it once by hand to see what it says.", "python -X utf8 tools/pc_report.py"), None
    age = now - _num(rec["t"])
    errs = [str(e)[:90] for e in rec.get("errors") or []]
    if age > REPORT_LATE_S:
        return _c("report", "REPORT", "FIX", f"the report last ran {_ago(age)}: the task is not running it",
                  "Run it once by hand, then re-install the task.", "python -X utf8 tools/pc_report.py   then   " + TASK_STEP), rec
    if errs:
        return _c("report", "REPORT", "FIX", f"the report ran {_ago(age)} but ntfy did not take it: {'; '.join(errs[:2])}",
                  "Check the internet / firewall for ntfy.sh, then run it by hand.", "python -X utf8 tools/pc_report.py"), rec
    return _c("report", "REPORT", "OK", f"the report ran {_ago(age)}, sent to ntfy"
                                        + (f" (last alert: {rec['alerts_last'].get('title')})" if isinstance(rec.get("alerts_last"), dict) else "")), rec


def check_topic(env):
    try:
        from tools import pc_report as PR
        cfg = PR.load_cfg(env)
    except Exception as e:
        return _c("topic", "TOPIC", "..", f"alert settings not readable ({e.__class__.__name__})"), None
    if not cfg.get("topic"):
        return _c("topic", "TOPIC", "FIX", "no private alert topic on this PC: trade pushes have nowhere to go",
                  "Make it, send the test push, then subscribe to the topic it prints in the ntfy app on the phone.",
                  "python -X utf8 tools/pc_report.py --setup   then   python -X utf8 tools/pc_report.py --test"), cfg
    if not cfg.get("on"):
        return _c("topic", "TOPIC", "FIX", "phone alerts are switched off in the alert settings (\"on\": false)",
                  "Switch them on again.", "python -X utf8 tools/pc_report.py --setup"), cfg
    if not cfg.get("tested"):
        return _c("topic", "TOPIC", "SKIP", "your private alert topic exists but never had its test push",
                  "Send the test push; if the phone gets nothing, subscribe to the topic (--setup prints it) in the ntfy app.",
                  "python -X utf8 tools/pc_report.py --test"), cfg
    return _c("topic", "TOPIC", "OK", "your private alert topic exists and had its test push (not shown here)"), cfg


def check_ntfy(cfg, http, offline):
    if offline:
        return _c("ntfy", "NTFY", "..", "network check skipped (--offline)")
    base = str((cfg or {}).get("ntfy") or "https://ntfy.sh").rstrip("/")
    st, _txt = http(f"{base}/v1/health")
    if st != 200:
        return _c("ntfy", "NTFY", "FIX", f"{base} does not answer from this PC ({st or _txt})",
                  "The internet or a firewall / antivirus blocks ntfy.sh.", "open https://ntfy.sh in a browser on this PC")
    topic = str((cfg or {}).get("status_topic") or "")
    if not topic:
        return _c("ntfy", "NTFY", "SKIP", "ntfy.sh answers; no public status channel configured (tools/web_public/status_feed.json)")
    st2, txt2 = http(f"{base}/{topic}/json?poll=1&since={FEED_SINCE}")
    n = len([ln for ln in (txt2 or "").splitlines() if '"event":"message"' in ln]) if st2 == 200 else None
    if n == 0:
        return _c("ntfy", "NTFY", "SKIP", f"ntfy.sh answers, but the site's status channel got nothing in {FEED_SINCE}: "
                                          "the report is not posting (see TASK / REPORT)")
    if n is None:
        return _c("ntfy", "NTFY", "OK", "ntfy.sh answers (status channel not readable just now)")
    return _c("ntfy", "NTFY", "OK", f"ntfy.sh answers; the site's status channel got {n} report(s) in {FEED_SINCE}")


def check_update(root, env, git=git_cfg):
    try:
        from engine import autoupdate as AU
        code, words = AU.source_status(root, env=env)
    except Exception as e:
        return _c("update", "UPDATE", "..", f"auto-update state not readable ({e.__class__.__name__})")
    ci = git("credential.interactive", root)
    if code == 0:
        return _c("update", "UPDATE", "OK", words)
    note = (" This folder has credential.interactive=never (set by BOTS_BACK.bat), which kept the sign-in window from opening "
            "on older code; this version opens it anyway." if ci == "never" else "")
    return _c("update", "UPDATE", "SKIP", f"{words} This PC does not get new code by itself, so fixes (like the report keeper "
                                          "that re-installs the report task) never reach it." + note,
              "Connect it once (bot server stopped, no trade open): a GitHub window opens, sign in as your BACKUP account.",
              "python -X utf8 -m engine.autoupdate --connect")


def check_heal(root, now):
    """The self-heal's last run (engine/self_heal.py): None until it ran on this PC."""
    try:
        from engine import self_heal as SH
        st = SH.status(root, now)
    except Exception:
        return None
    if not st.get("ran"):
        return None
    t = st.get("tiny") or {}
    age = _ago(now - st["ran"])
    if st.get("need"):
        last = [x for x in st.get("last") or [] if isinstance(x, dict) and x.get("status") == "need"]
        return _c("heal", "HEAL", "FIX", f"self-heal ran {age} and could NOT fix: " + "; ".join(str(x.get("text"))[:100] for x in last[:2]),
                  "See what it would do, then let it try again now.", "python -X utf8 tools/pc_doctor.py --heal --apply")
    return _c("heal", "HEAL", "OK", f"self-heal ran {age}: nothing left to fix (fixed {t.get('fixed', 0)} this week by itself)")


def run(root: str = ROOT, env=None, now=None, http=None, ping=None, task=None, offline=False, git=git_cfg) -> dict:
    """All checks -> {"t", "checks": [...], "cause", "step", "ok"}. Never raises."""
    env = os.environ if env is None else env
    now = time.time() if now is None else now
    http = http or http_get
    if ping is None:
        st, txt = http(f"http://127.0.0.1:{PORT}/api/health/ping")
        try:
            ping = json.loads(txt) if st == 200 else None
        except Exception:
            ping = None
    elif ping is False:
        ping = None
    out = [check_server(ping)]
    beat, _pl, last = check_beat(root, now, ping)
    out.append(beat)
    out.append(check_github(env, last))
    out.append(check_task(task_info() if task is None else (None if task is False else task)))
    rep, _rec = check_report(root, now)
    out.append(rep)
    top, cfg = check_topic(env)
    out.append(top)
    out.append(check_ntfy(cfg, http, offline))
    out.append(check_update(root, env, git=git))
    heal = check_heal(root, now)
    if heal:
        out.append(heal)
    by = {c["key"]: c for c in out}
    first = next((by[k] for k in ORDER if k in by and by[k]["level"] == "FIX"), None) or \
        next((by[k] for k in ORDER if k in by and by[k]["level"] == "SKIP" and by[k].get("step")), None)
    return {"t": int(now), "checks": out, "ok": first is None,
            "cause": (f"{first['label']}: {first['text']}" if first else "every link answers: the phone should hear the PC"),
            "fix": first["fix"] if first else "", "step": first["step"] if first else ""}


def card_text(r: dict) -> str:
    lines = ["", "  PC DOCTOR: why the phone hears nothing from this PC (it only looks, changes nothing)", ""]
    for c in r["checks"]:
        lines.append(f"  [{c['level']}] {c['label']:<6} {c['text']}")
        if c["level"] in ("FIX", "SKIP") and c.get("step"):
            lines.append(f"         -> {c['fix']}  Next: {c['step']}")
    lines += ["", f"  MOST LIKELY CAUSE: {r['cause']}"]
    if r.get("step"):
        lines.append(f"  NEXT STEP (copy this line): {r['step']}")
    lines.append("  Still stuck: take a photo of this window and send it to Claude.")
    return "\n".join(lines)


def github_free(env=None) -> str:
    """The owner's one switch: GitHub-free mode on (the marker BOTS_BACK.bat / PUBLISH_NQ.bat make). Applies at the next start."""
    from engine import nogithub
    d = nogithub.olympus_dir(env)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, nogithub.MARKER)
    if not os.path.exists(p):
        with open(p, "w", encoding="ascii") as fh:
            fh.write("GitHub-free bot mode (PC_DOCTOR). Delete this file to undo.\n")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/pc_doctor.py", description="PC DOCTOR: why the phone hears nothing from the PC")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--github-free", action="store_true", help="turn GitHub-free mode on (applies at the next bot start)")
    ap.add_argument("--heal", action="store_true", help="the self-heal now: a dry run, or with --apply the fix (engine/self_heal.py)")
    ap.add_argument("--apply", action="store_true", help="with --heal: fix, not only show")
    a = ap.parse_args(argv)
    if a.heal:
        from engine import self_heal as SH
        return SH.main(["--apply"] if a.apply else [])
    if a.github_free:
        github_free()
        print("  [OK] GitHub-free mode is ON for the next bot start (when flat: STOP_BOT.bat, then START_BOT.bat).")
        return 0
    r = run(offline=a.offline)
    print(json.dumps(r, indent=1) if a.json else card_text(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
