"""Kalshi: the PC sends the risk guard to the VM and reads its status back (team K2, 2026-11-13).
tools/kalshi_kit/send_to_vm.py and tools/kalshi_pc_link.py, through a stand-in srv.py that runs the shell file locally with
a temp HOME (the "VM"), a fake crontab and no network. Checks:
  a. the update: the three files land in ~/kalshi_jarvis byte for byte, checked by SHA-256; guard/ made in PAPER; the phone
     alert topic from the PC's ntfy.json (file 600); one cron line; a second run changes nothing; a changed file keeps a .bak;
     a hash mismatch writes nothing; the shell line is one ASCII line with no address
  b. the switches from the PC: status, limits (checked here first), paper, dry-run, kill, unkill; --live needs a terminal and
     the owner's typed phrase (checked on the VM); a hostile phrase is only a phrase; --dry sends nothing
  c. the PC reads the VM's status (srv.py): the risk block arrives, is saved where pc_publish and the PC dashboard read it,
     the one-line card; alerts from the PC only when the VM sends none
    python -X utf8 -m tests.test_kalshi_vm_update
"""
from __future__ import annotations

import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.kalshi_kit import send_to_vm as S  # noqa: E402
from tools import kalshi_pc_link as L  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def make_vm(tmp):
    """A stand-in srv.py (python srv.py x.sh -> run it, print the output with \\r\\r\\n, like the PC's) whose 'VM' is a temp HOME
    with a fake crontab on PATH."""
    vmhome = os.path.join(tmp, "vmhome")
    fakebin = os.path.join(tmp, "fakebin")
    os.makedirs(vmhome)
    os.makedirs(fakebin)
    cron = os.path.join(tmp, "crontab.txt")
    with open(os.path.join(fakebin, "crontab"), "w") as fh:
        fh.write(f"#!/bin/sh\nif [ \"$1\" = \"-l\" ]; then [ -f {cron} ] && cat {cron} && exit 0; echo 'no crontab' >&2; exit 1; fi\n"
                 f"if [ \"$1\" = \"-\" ]; then cat > {cron}; exit 0; fi\nexit 2\n")
    os.chmod(os.path.join(fakebin, "crontab"), 0o755)
    helper_dir = os.path.join(tmp, "scratch")
    os.makedirs(helper_dir)
    srv = os.path.join(helper_dir, "srv.py")
    with open(srv, "w") as fh:
        fh.write("import os, subprocess, sys\n"
                 "cmd = open(sys.argv[1]).read()\n"
                 f"env = dict(os.environ, HOME={vmhome!r}, PATH={fakebin!r} + ':' + os.environ.get('PATH', ''))\n"
                 "env.pop('KALSHI_GUARD_HOME', None)\n"
                 "r = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True, env=env)\n"
                 "print(('Welcome to the VM\\n' + r.stdout + r.stderr).replace('\\n', '\\r\\r\\n'))\n")
    return srv, vmhome, cron


def run_main(argv, stdin_tty=None):
    buf = io.StringIO()
    old = sys.stdin
    if stdin_tty is not None:
        class FakeIn(io.StringIO):
            def isatty(self):
                return stdin_tty
        sys.stdin = FakeIn(stdin_tty if isinstance(stdin_tty, str) else "")
    try:
        with redirect_stdout(buf):
            code = S.main(argv)
    finally:
        sys.stdin = old
    return code, buf.getvalue()


def part_a(tmp, srv, vmhome, cron):
    jh = os.path.join(vmhome, "kalshi_jarvis")
    code, out = run_main(["--vm-helper", srv])
    files_ok = all(open(os.path.join(jh, n), "rb").read() == open(os.path.join(S.PUB, n), "rb").read().replace(b"\r\n", b"\n") for n in S.FILES)
    check("a. update: kalshi_guard.py, kalshi_status_vm.py, GUARD_SETUP.md land in ~/kalshi_jarvis byte for byte", code == 0 and files_ok, out)
    mode = json.load(open(os.path.join(jh, "guard", "mode.json")))
    check("a. guard/ made with the default limits, in PAPER", mode["mode"] == "paper" and os.path.isfile(os.path.join(jh, "guard", "limits.json"))
          and "mode: PAPER" in out, out)
    nt = os.path.join(jh, "guard", "ntfy.json")
    check("a. the phone alert topic came from the PC's ntfy.json, file 600 on the VM",
          json.load(open(nt))["topic"] == "olympus-k2-test-topic" and stat.S_IMODE(os.stat(nt).st_mode) == 0o600 and "phone alerts: on" in out, out)
    lines = open(cron).read().splitlines()
    check("a. one cron line: every minute, flock, nice'd, isolated python, notify", len(lines) == 1 and lines[0] == S.CRON
          and "flock -n" in lines[0] and "python3 -I kalshi_guard.py notify" in lines[0], lines)
    check("a. the PC prints the line to paste into the kalshi-server chat", S.PASTE in out and "GUARD_SETUP.md" in S.PASTE)
    code, out2 = run_main(["--vm-helper", srv])
    check("a. a second run: nothing new, cron 'already there', still one line, no .bak", code == 0 and "nothing new" in out2
          and "already there" in out2 and len(open(cron).read().splitlines()) == 1 and not os.path.exists(os.path.join(jh, "kalshi_guard.py.bak")), out2)
    with open(os.path.join(jh, "kalshi_status_vm.py"), "a") as fh:
        fh.write("\n# old\n")
    code, out3 = run_main(["--vm-helper", srv])
    check("a. a changed file on the VM is replaced and the old copy kept as .bak", "kalshi_status_vm.py" in out3.split("unchanged")[0]
          and open(os.path.join(jh, "kalshi_status_vm.py.bak")).read().endswith("# old\n"), out3)
    src = S.installer_source("olympus-k2-test-topic")
    bad = src.replace(S.sha(S.file_text("GUARD_SETUP.md")), "0" * 64)
    before = open(os.path.join(jh, "GUARD_SETUP.md"), "rb").read()
    ok, out4 = S.run_on_vm(S.shell_line(bad.replace("GUARD_SETUP", "GUARD_SETUP")), srv)
    res = json.loads(S.between(out4) or "{}")
    check("a. a hash mismatch writes nothing for that file and reports it", res.get("ok") is False
          and any("hash mismatch" in e for e in res.get("errors") or []) and open(os.path.join(jh, "GUARD_SETUP.md"), "rb").read() == before, res)
    line = S.shell_line(src)
    import re as _re
    ips = set(_re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", line))
    check("a. the shell line: one ASCII line, isolated python in ~/kalshi_jarvis, no IP address, under 200 KB",
          line.count("\n") == 1 and line.isascii() and "python3 -I -c" in line and line.startswith("mkdir -p ~/kalshi_jarvis") and not ips
          and len(line) < 200_000, (len(line), ips))


def part_b(tmp, srv, vmhome, cron):
    jh = os.path.join(vmhome, "kalshi_jarvis")
    code, out = run_main(["--vm-helper", srv, "--status"])
    check("b. --status prints the guard's card from the VM", code == 0 and "mode: PAPER" in out and "limits:" in out, out)
    code, out = run_main(["--vm-helper", srv, "--limits", "max_order_usd=3", "daily_stop_usd=6"])
    lim = json.load(open(os.path.join(jh, "guard", "limits.json")))
    check("b. --limits sets them on the VM", code == 0 and lim["max_order_usd"] == 3 and lim["daily_stop_usd"] == 6, out)
    code, out = run_main(["--vm-helper", srv, "--limits", "max_order_usd=3;rm -rf ~"])
    check("b. --limits refuses anything that is not KEY=VALUE before it reaches the VM", code == 2 and "not KEY=VALUE" in out, out)
    code, out = run_main(["--vm-helper", srv, "--limits", "max_order_usd=99999"])
    check("b. an out-of-range limit is refused by the VM's guard (exit 1)", code == 1 and json.load(open(os.path.join(jh, "guard", "limits.json")))["max_order_usd"] == 3, out)
    for flag, want in (("--dry-run", "dry_run"), ("--paper", "paper")):
        code, out = run_main(["--vm-helper", srv, flag])
        check(f"b. {flag} -> {want} on the VM", code == 0 and json.load(open(os.path.join(jh, "guard", "mode.json")))["mode"] == want, out)
    code, out = run_main(["--vm-helper", srv, "--kill"])
    check("b. --kill puts the kill switch file on the VM", code == 0 and os.path.exists(os.path.join(jh, "guard", "KILL")), out)
    code, out = run_main(["--vm-helper", srv, "--unkill"])
    check("b. --unkill lifts it (still paper)", code == 0 and not os.path.exists(os.path.join(jh, "guard", "KILL")) and "still paper" in out, out)
    code, out = run_main(["--vm-helper", srv, "--live"], stdin_tty=False)
    check("b. --live without a terminal: refused, nothing armed", code == 1 and "terminal" in out
          and json.load(open(os.path.join(jh, "guard", "mode.json")))["mode"] == "paper", out)
    code, out = run_main(["--vm-helper", srv, "--live"], stdin_tty="GO LIVE 2020-01-01 STOP 6\n")
    sys.stdin = sys.__stdin__
    check("b. --live in a terminal shows the VM's phrase; a wrong one is refused by the VM",
          code == 1 and "GO LIVE " in out and "STOP 6" in out and json.load(open(os.path.join(jh, "guard", "mode.json")))["mode"] == "paper", out)
    import re as _re
    phrase = _re.search(r"GO LIVE \d{4}-\d{2}-\d{2} STOP [\d.]+", out).group(0)

    class TTY(io.StringIO):
        def isatty(self):
            return True

    old = sys.stdin
    sys.stdin = TTY(phrase + "\n")
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = S.main(["--vm-helper", srv, "--live"])
    finally:
        sys.stdin = old
    check("b. --live with the phrase the owner typed -> LIVE on the VM", code == 0 and json.load(open(os.path.join(jh, "guard", "mode.json")))["mode"] == "live",
          buf.getvalue())
    ok, out = S.run_on_vm(S.guard_line(["live", "--phrase", "x'; touch $HOME/pwned; echo '"]), srv)
    check("b. a hostile phrase is only a phrase (quoted): refused, nothing run", not os.path.exists(os.path.join(vmhome, "pwned"))
          and "not armed" in out, out)
    S.run_on_vm(S.guard_line(["paper"]), srv)
    shp = os.path.join(os.environ["KALSHI_JARVIS_HOME"], "vm_guard.sh")
    before = open(shp, "rb").read() if os.path.exists(shp) else None
    code, out = run_main(["--vm-helper", srv, "--dry"])
    check("b. --dry: says what it would send, sends nothing", code == 0 and "[dry] would send" in out and "sha256" in out
          and (open(shp, "rb").read() if os.path.exists(shp) else None) == before, out)
    code, out = run_main(["--vm-helper", os.path.join(tmp, "nope.py"), "--status"])
    check("b. no srv.py -> a plain message, exit 1", code == 1 and "srv.py" in out, out)


def part_c(tmp, srv, vmhome):
    from tests import test_kalshi_publish as TP
    bot = TP.make_bot(os.path.join(vmhome, "kalshi"))
    out_file = os.path.join(tmp, "pc_data", "kalshi.json")
    r = L.run_once(helper=srv, vm_dir=bot, now=TP.NOW, data_out=out_file, state_dir=os.path.join(tmp, "pc_state"))
    p = json.load(open(out_file)) if r.get("ok") else {}
    check("c. the PC reads the VM's status through srv.py, risk block included (the guard on the VM)", r.get("ok") and p.get("risk", {}).get("mode") == "paper"
          and p.get("balance") == 67.98, r)
    feed = os.path.join(os.environ["OLYMPUS_HOME"], "kalshi_feed", "kalshi.json")
    check("c. saved where pc_publish picks it up (<olympus>/kalshi_feed/kalshi.json) and for the PC dashboard (data/pc_report)",
          os.path.isfile(feed) and json.load(open(feed)) == p)
    from tools import pc_publish
    check("c. pc_publish finds it with no setting", pc_publish.load_config(cdir=os.environ["OLYMPUS_HOME"])["kalshi_file"] == feed)
    kind, text = r["card"]
    check("c. the card line: mode (guard not connected yet), today, balance, loss room", kind == "OK" and "PAPER (guard not connected yet)" in text
          and "balance $67.98" in text and "loss room $6.00 of $6.00" in text, text)
    k2, t2 = L.card_line({**p, "risk": {**p["risk"], "kill": True}}, now=TP.NOW)
    k3, t3 = L.card_line({**p, "t": TP.NOW - 3600}, now=TP.NOW)
    check("c. kill switch / an old status -> FIX on the card", k2 == "FIX" and t2.startswith("KILL SWITCH ON") and k3 == "FIX" and "60 min old" in t3, (t2, t3))
    sent = []

    def http(method, url, body=None, headers=None, timeout=15):
        sent.append((url, (headers or {}).get("Title")))
        return 200, "ok"

    n, why = L.pc_alerts({**p, "risk": {**p["risk"], "alerts_vm": True}}, http=http, state_dir=os.path.join(tmp, "pc_state"))
    check("c. the VM sends the alerts -> the PC sends none", n == 0 and "VM sends" in why and not sent)
    st = os.path.join(tmp, "pc_state2")
    L.pc_alerts({**p, "risk": {**p["risk"], "alerts_vm": False}}, http=http, state_dir=st)
    n, why = L.pc_alerts({**p, "t": p["t"] + 60, "risk": {**p["risk"], "alerts_vm": False, "kill": True, "kill_t": 5}}, http=http, state_dir=st)
    check("c. the VM sends none -> the PC pushes on its own topic (kill switch)", n == 1 and sent and sent[-1][0].endswith("/olympus-k2-test-topic")
          and sent[-1][1] == "Kalshi KILL SWITCH ON", (n, why, sent))
    src = os.path.join(tmp, "k.json")
    json.dump(p, open(src, "w"))
    r = L.run_once(src=src, now=TP.NOW, data_out=out_file, state_dir=st)
    check("c. --src a kalshi.json file works the same", r.get("ok") and r["card"][0] == "OK")
    r = L.run_once(helper=os.path.join(tmp, "nope.py"), data_out=out_file, state_dir=st)
    check("c. no srv.py -> a soft '..' card, nothing raised", not r["ok"] and r["card"][0] == "..")


def main():
    tmp = tempfile.mkdtemp(prefix="kvm_")
    keep = {k: os.environ.get(k) for k in ("OLYMPUS_HOME", "KALSHI_JARVIS_HOME", "KALSHI_GUARD_HOME")}
    try:
        os.environ["OLYMPUS_HOME"] = os.path.join(tmp, "olympus")
        os.environ["KALSHI_JARVIS_HOME"] = os.path.join(tmp, "pcstate")
        os.environ.pop("KALSHI_GUARD_HOME", None)
        os.makedirs(os.environ["OLYMPUS_HOME"])
        json.dump({"topic": "olympus-k2-test-topic", "ntfy": "https://ntfy.sh"}, open(os.path.join(os.environ["OLYMPUS_HOME"], "ntfy.json"), "w"))
        srv, vmhome, cron = make_vm(tmp)
        part_a(tmp, srv, vmhome, cron)
        part_b(tmp, srv, vmhome, cron)
        part_c(tmp, srv, vmhome)
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nkalshi vm update: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
