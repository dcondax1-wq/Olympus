"""Send the Kalshi risk guard to the bot's VM, from the owner's PC (team K2, 2026-11-13). Stdlib only.

It uses the PC's own VM helper srv.py (python srv.py x.sh runs a shell file on the VM; the VM's address stays inside srv.py,
never here, never printed), the same way `python -m engine.kalshi_publish --ssh` reads the bot's numbers. Nothing is installed
on the PC. On the VM everything goes to ~/kalshi_jarvis/ (nothing in /home/ubuntu/kalshi changes):

  python tools/kalshi_kit/send_to_vm.py              copy kalshi_guard.py, kalshi_status_vm.py, GUARD_SETUP.md (each checked
                                                     by SHA-256 on the VM, the old copy kept as .bak), make guard/ (PAPER),
                                                     put your phone alert topic there (from %USERPROFILE%\\.olympus\\ntfy.json),
                                                     add one cron line (every minute: phone alerts), print the guard's card
                                                     and the line to paste into the kalshi-server chat
  ... --status                                       the guard's card (reads only)
  ... --limits max_order_usd=5 daily_stop_usd=10     change limits (a change turns LIVE off until the phrase again)
  ... --live                                         YOU type the phrase here; it is checked on the VM (real money)
  ... --paper | --dry-run | --kill | --unkill        the switches (paper / dry run / kill need no phrase)
  ... --dry                                          print what would be sent; send nothing
  ... --vm-helper <path to srv.py>                   when it isn't found under %APPDATA%\\Claude\\scratch-workspaces
Tests: tests/test_kalshi_vm_update.py (a stand-in srv.py that runs the shell file locally).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(HERE, "public")
ROOT = os.path.dirname(os.path.dirname(HERE))
FILES = ("kalshi_guard.py", "kalshi_status_vm.py", "GUARD_SETUP.md")
VM_HOME = "~/kalshi_jarvis"
BOT_DIR = "/home/ubuntu/kalshi"
MARK_A, MARK_B = "@@KALSHI_GUARD_BEGIN@@", "@@KALSHI_GUARD_END@@"
PASTE = ("Connect my Kalshi bot's orders to the risk guard by following ~/kalshi_jarvis/GUARD_SETUP.md. "
         "Keep it in paper mode and show me the diff before any restart.")
CRON = ("* * * * * cd $HOME/kalshi_jarvis && flock -n .notify.lock nice -n 15 python3 -I kalshi_guard.py notify "
        f"--from-bot {BOT_DIR} >> notify.log 2>&1")
_KV = re.compile(r"[a-z_]{3,40}=[A-Za-z0-9_.,-]{0,80}")


def _kit():
    name = "kalshi_to_jarvis_kit"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(PUB, "kalshi_status_vm.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


def file_text(name):
    with open(os.path.join(PUB, name), "rb") as fh:
        return fh.read().replace(b"\r\n", b"\n").decode("utf-8")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def alert_topic(env=None):
    """The owner's private ntfy topic from the PC (the one tools/pc_report.py made), or ''."""
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from tools import pc_report
        cfg = pc_report.load_cfg(env)
        t = str(cfg.get("topic") or "").strip()
        return t if re.fullmatch(r"[A-Za-z0-9_-]{6,64}", t) else ""
    except Exception:
        return ""


INSTALLER = r'''
import hashlib, json, os, shutil, subprocess, sys, time
FILES = __FILES__
SHAS = __SHAS__
TOPIC = __TOPIC__
CRON = __CRON__
home = os.path.expanduser("~/kalshi_jarvis")
os.makedirs(home, exist_ok=True)
out = {"ok": True, "changed": [], "same": [], "errors": []}
for name, text in FILES.items():
    data = text.encode("utf-8")
    if hashlib.sha256(data).hexdigest() != SHAS[name]:
        out["ok"] = False
        out["errors"].append(name + ": hash mismatch, not written")
        continue
    dst = os.path.join(home, name)
    if os.path.exists(dst) and open(dst, "rb").read() == data:
        out["same"].append(name)
        continue
    if os.path.exists(dst):
        shutil.copy2(dst, dst + ".bak")
    tmp = dst + ".new"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, dst)
    out["changed"].append(name)
if out["ok"]:
    r = subprocess.run([sys.executable, "-I", os.path.join(home, "kalshi_guard.py"), "init"], capture_output=True, text=True, cwd=home)
    out["init"] = r.returncode == 0
    if r.returncode:
        out["ok"] = False
        out["errors"].append("guard init failed: " + (r.stderr or r.stdout)[-200:])
    gh = os.path.join(home, "guard")
    if TOPIC and os.path.isdir(gh):
        p = os.path.join(gh, "ntfy.json")
        with open(p + ".new", "w") as fh:
            json.dump({"topic": TOPIC, "ntfy": "https://ntfy.sh"}, fh)
        os.chmod(p + ".new", 0o600)
        os.replace(p + ".new", p)
        out["alerts"] = True
    try:
        cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        lines = cur.stdout if cur.returncode == 0 else ""
        if "kalshi_guard.py notify" in lines:
            out["cron"] = "already there"
        else:
            r = subprocess.run(["crontab", "-"], input=lines + ("" if not lines or lines.endswith("\n") else "\n") + CRON + "\n",
                               capture_output=True, text=True)
            out["cron"] = "added" if r.returncode == 0 else "could not add: " + (r.stderr or "")[-120:]
    except FileNotFoundError:
        out["cron"] = "no crontab on this server"
    r = subprocess.run([sys.executable, "-I", os.path.join(home, "kalshi_guard.py"), "status"], capture_output=True, text=True, cwd=home)
    out["card"] = r.stdout.strip()
print("__A__" + json.dumps(out) + "__B__")
'''


def installer_source(topic=""):
    texts = {n: file_text(n) for n in FILES}
    return (INSTALLER.replace("__FILES__", repr(texts)).replace("__SHAS__", repr({n: sha(t) for n, t in texts.items()}))
            .replace("__TOPIC__", repr(topic or "")).replace("__CRON__", repr(CRON))
            .replace("__A__", MARK_A).replace("__B__", MARK_B))


def shell_line(source):
    """One ASCII shell line for srv.py: the Python inside (zlib + base64), run isolated (-I) in ~/kalshi_jarvis."""
    blob = base64.b64encode(zlib.compress(source.encode("utf-8"), 9)).decode("ascii")
    py = f"import base64,zlib;exec(compile(zlib.decompress(base64.b64decode('{blob}')),'kalshi_guard_install','exec'))"
    return f"mkdir -p {VM_HOME} && cd {VM_HOME} && python3 -I -c \"{py}\"\n"


def guard_line(args):
    """One shell line that runs kalshi_guard.py on the VM with these arguments (each quoted)."""
    q = " ".join(shlex.quote(a) for a in args)
    return (f"cd {VM_HOME} && python3 -I kalshi_guard.py {q} ; echo {MARK_A}$?{MARK_B}\n")


def run_on_vm(line, helper, python=None, work=None, timeout=180):
    """-> (exit ok, output text). The output is redacted like the status kit's errors (no address, key or path)."""
    kit = _kit()
    if not helper or not os.path.isfile(helper):
        return False, "srv.py (the PC's VM helper) was not found: give --vm-helper <path to srv.py>"
    work = work or kit.state_dir()
    os.makedirs(work, exist_ok=True)
    sh = os.path.join(work, "vm_guard.sh")
    with open(sh, "wb") as fh:
        fh.write(line.encode("ascii"))
    try:
        r = subprocess.run([python or kit._console_python(), helper, sh], cwd=os.path.dirname(os.path.abspath(helper)),
                           capture_output=True, timeout=timeout, creationflags=kit._NO_WINDOW)
    except subprocess.TimeoutExpired:
        return False, "the VM did not answer in time"
    out = ((r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")).replace("\r", "")
    return r.returncode == 0, kit.redact(out)


def between(text):
    m = re.search(re.escape(MARK_A) + r"(.*?)" + re.escape(MARK_B), text or "", re.S)
    return m.group(1) if m else None


def say_card(text):
    for ln in (text or "").splitlines():
        if ln.strip():
            print("  " + ln)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="send_to_vm.py", description="Send the Kalshi risk guard to the bot's VM (through the PC's srv.py).")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--status", action="store_true")
    g.add_argument("--limits", nargs="+", metavar="KEY=VALUE")
    g.add_argument("--live", action="store_true")
    g.add_argument("--paper", action="store_true")
    g.add_argument("--dry-run", dest="dry_run_mode", action="store_true")
    g.add_argument("--kill", action="store_true")
    g.add_argument("--unkill", action="store_true")
    ap.add_argument("--dry", action="store_true", help="print what would be sent, send nothing")
    ap.add_argument("--vm-helper", default=None)
    ap.add_argument("--vm-python", default=None)
    ap.add_argument("--no-alerts", action="store_true", help="don't put the phone alert topic on the VM")
    a = ap.parse_args(argv)
    kit = _kit()
    helper = a.vm_helper or kit.find_vm_helper()
    if a.limits:
        bad = [x for x in a.limits if not _KV.fullmatch(x)]
        if bad:
            print(f"  [FIX] not KEY=VALUE: {' '.join(bad)}")
            return 2
        line = guard_line(["limits", "--set", *a.limits])
    elif a.status:
        line = guard_line(["status"])
    elif a.paper or a.dry_run_mode or a.kill or a.unkill:
        line = guard_line(["paper" if a.paper else "dry-run" if a.dry_run_mode else "kill" if a.kill else "unkill"]
                          + (["from the PC"] if a.kill else []))
    elif a.live:
        ok, out = (True, "") if a.dry else run_on_vm(guard_line(["status"]), helper, a.vm_python)
        if not ok and not a.dry:
            print("  [FIX] " + out.strip()[-300:])
            return 1
        say_card(out.split(MARK_A)[0])
        m = re.search(r"GO LIVE \d{4}-\d{2}-\d{2} STOP [\d.]+", out or "")
        print("\n  REAL MONEY. The bot can then lose up to the daily stop each day, inside the limits above.")
        if not sys.stdin.isatty():
            print("  [FIX] run this in a terminal window and type the phrase yourself.")
            return 1
        phrase = input(f"  Type exactly  {m.group(0) if m else 'GO LIVE <today ET YYYY-MM-DD> STOP <daily stop>'}  and press Enter: ")
        line = guard_line(["live", "--phrase", phrase])
    else:
        topic = "" if a.no_alerts else alert_topic()
        src = installer_source(topic)
        line = shell_line(src)
        if a.dry:
            print(f"  [dry] would send {len(line):,} bytes: {', '.join(FILES)}"
                  + (" + your alert topic" if topic else " (no alert topic on this PC: run python tools/pc_report.py --setup)"))
            for n in FILES:
                print(f"  [dry] {n} sha256 {sha(file_text(n))}")
            return 0
        ok, out = run_on_vm(line, helper, a.vm_python)
        body = between(out)
        try:
            res = json.loads(body) if body else None
        except ValueError:
            res = None
        if not res:
            print("  [FIX] no answer from the VM: " + re.sub(r"\s+", " ", out).strip()[-300:])
            return 1
        print(f"  [{'OK' if res.get('ok') else 'FIX'}] VM updated: {', '.join(res.get('changed') or []) or 'nothing new'}"
              + (f" (unchanged: {', '.join(res['same'])})" if res.get("same") else ""))
        for e in res.get("errors") or []:
            print("  [FIX] " + e)
        print(f"  [{'OK' if res.get('alerts') else '..'}] phone alerts: " + ("on (your ntfy topic), cron " + str(res.get("cron"))
                                                                          if res.get("alerts") else "no topic on this PC (python tools/pc_report.py --setup, then run this again)"))
        say_card(res.get("card"))
        print("\n  NEXT: paste this into the kalshi-server chat:\n  " + PASTE)
        return 0 if res.get("ok") else 1
    if a.dry:
        print("  [dry] would run on the VM: " + line.strip())
        return 0
    ok, out = run_on_vm(line, helper, a.vm_python)
    code = between(out)
    say_card(out.split(MARK_A)[0] if MARK_A in out else out)
    return 0 if (code or "").strip() == "0" else 1


if __name__ == "__main__":
    sys.exit(main())
