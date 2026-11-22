"""CLOCK FIX (2026-11-22): the owner's PC clock ran 24.5 s behind and Windows would not sync it (needs an administrator).

    python -X utf8 -m tests.test_clockfix        (fakes only: no real w32tm / schtasks, nothing trades, no network)

 a. engine/go.sync_clock order: w32tm /resync first; refused -> `schtasks /run /tn OlympusClock`; no such task -> the one plain sentence.
 b. the plain sentence is the same everywhere (go, self_heal, trade_home, pc_health, alerts_plus) and the old 'will not sync' is gone.
 c. self_heal.fix_clock: through the task = fixed; no task = need + the sentence; the doctor line says it too; no live phrase anywhere.
 d. TRADE_HOME: Status shows the clock, 9 Fix the clock = the same chain, never starts a .bat or types a phrase.
 e. FIX_CLOCK.bat / FIX_CLOCK_OFF.bat / scripts/fix_clock.ps1: ASCII, CRLF, admin check, every setting the owner asked for.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import go as G  # noqa: E402
from engine import self_heal as SH  # noqa: E402
from engine import trade_home as T  # noqa: E402

RES = []
SAY = "double-click FIX_CLOCK.bat once, right-click > Run as administrator"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   -> {str(info)[:400]}"))


DENIED = ("The following error occurred: Access is denied. (0x80070005)", 2147942405)
OFF = ("The following error occurred. The service has not been started. (0x80070426)", 2147943462)
OK_ = ("Sending resync command to local computer\nThe command completed successfully.", 0)
TASK_OK = ("SUCCESS: Attempted to run the scheduled task \"OlympusClock\".", 0)
TASK_GONE = ("ERROR: The system cannot find the file specified.", 1)
TASK_NOACCESS = ("ERROR: Access is denied.", 1)


def fake(w32, task):
    calls = []

    def run(cmd, **k):
        calls.append(list(cmd))
        out, code = w32 if cmd[0] == "w32tm" else task
        return SimpleNamespace(stdout=out, stderr="", returncode=code)
    run.calls = calls
    return run


def main():
    # a. the order
    r = fake(OK_, TASK_OK)
    s = G.sync_clock(run=r)
    check("a1. w32tm works -> synced, the task is never touched", s["ok"] and [c[0] for c in r.calls] == ["w32tm"], r.calls)
    r = fake(DENIED, TASK_OK)
    s = G.sync_clock(run=r)
    check("a2. w32tm refused -> schtasks /run /tn OlympusClock next (works without admin) -> ok via the task",
          s["ok"] and s.get("via") == "task" and r.calls == [["w32tm", "/resync"], ["schtasks", "/run", "/tn", "OlympusClock"]], (s, r.calls))
    r = fake(OFF, TASK_OK)
    s = G.sync_clock(run=r)
    check("a3. the time service is off -> same fallback", s["ok"] and s.get("via") == "task" and r.calls[1][0] == "schtasks", (s, r.calls))
    for nm, t in (("no task", TASK_GONE), ("task refuses", TASK_NOACCESS)):
        r = fake(DENIED, t)
        s = G.sync_clock(run=r)
        check(f"a4. refused + {nm} -> not ok, the one plain sentence, order w32tm then schtasks",
              not s["ok"] and SAY in s["error"] and SAY[0].upper() + SAY[1:] in s["steps"] and len(r.calls) == 2, (s, r.calls))
    boom = lambda cmd, **k: (_ for _ in ()).throw(OSError("no such program"))  # noqa: E731
    s = G.sync_clock(run=boom)
    check("a5. neither program runs -> a plain not-ok, no exception", not s["ok"] and SAY in s["error"], s)

    # b. one sentence everywhere, the old phrase gone
    check("b1. same sentence in go / self_heal / trade_home", G.CLOCK_FIX_SAY == SAY == SH.CLOCK_FIX_SAY == T.CLOCK_FIX_SAY, "")
    from engine import alerts_plus, pc_health
    srcs = {m: open(os.path.join(ROOT, "engine", m + ".py"), encoding="utf-8").read() for m in ("go", "self_heal", "pc_health", "alerts_plus", "start_api", "ops_checks")}
    check("b2. pc_health (board line) and alerts_plus (alert text) carry the sentence", SAY in srcs["pc_health"] and SAY in srcs["alerts_plus"], "")
    check("b3. 'the clock will not sync' is gone from the engine", not any("clock will not sync" in v for v in srcs.values()), "")
    check("b4. the guard threshold is untouched (5 s)", "clock_max_s\": 5.0" in open(os.path.join(ROOT, "engine", "guards.py"), encoding="utf-8").read()
          and G.CLOCK_MAX_S == 5.0, "")

    # c. self_heal.fix_clock
    import json
    import tempfile
    import time
    now = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "logs"))
        with open(os.path.join(tmp, "logs", "pc_health.json"), "w", encoding="utf-8") as fh:
            json.dump({"t": now - 30, "lines": [{"key": "clock", "level": "red", "text": "x", "value": 24.5}]}, fh)

        def ctx(run, apply=True):
            return SH.Ctx(root=tmp, now=now, apply=apply, procs=[(1, "explorer.exe")], ping=lambda: True, nt=None, temp="", pkgs={}, env={},
                          sync_clock=lambda: G.sync_clock(run=run))
        r = fake(DENIED, TASK_OK)
        it = SH.fix_clock(ctx(r))
        check("c1. 24.5 s behind, refused, task exists -> fixed (schtasks ran after w32tm)", [i["status"] for i in it] == ["fixed"]
              and "24.5 s behind" in it[0]["text"] and r.calls[1][:2] == ["schtasks", "/run"], (it, r.calls))
        r = fake(DENIED, TASK_GONE)
        it = SH.fix_clock(ctx(r))
        check("c2. refused, no task -> need, the sentence in the self-heal line and the step, no old words",
              [i["status"] for i in it] == ["need"] and SAY in it[0]["text"] and SAY[0].upper() + SAY[1:] == it[0]["step"]
              and "Sync now" not in it[0]["text"] + it[0]["step"], it)
        r = fake(DENIED, TASK_GONE)
        it = SH.fix_clock(ctx(r, apply=False))
        check("c3. dry run only says what it would do", [i["status"] for i in it] == ["would"], it)
    line = SH.tiny({"need": ["clock"], "hist": []}, now)
    blob = json.dumps(line)
    check("c4. the doctor line for a clock need says the sentence, not 'will not sync'", SAY in blob and "will not sync" not in blob, blob)
    allsrc = "".join(srcs.values()) + open(os.path.join(ROOT, "engine", "trade_home.py"), encoding="utf-8").read()
    check("c5. no live phrase in the clock code", "I ACCEPT LIVE RISK" not in srcs["go"].split("def sync_clock")[1].split("def _note")[0], "")

    # d. TRADE_HOME
    L, P = T.status_screen(now=1060, bot={"running": True, "last_poll": 1000, "trades_today": 0}, accounts=[], keepalive={"x": True},
                           alerts=(True, True, True), clock=24.5)
    txt = "\n".join(L)
    check("d1. Status shows 'Clock: 24.5 s behind' + BLOCKED and a problem naming menu 9 with the sentence",
          "Clock    : 24.5 s behind internet time (new entries are BLOCKED)" in txt and P[0][0] == "9" and SAY in P[0][1], (txt, P))
    L, P = T.status_screen(now=1060, bot={"running": True, "last_poll": 1000, "trades_today": 0},
                           accounts=[{"name": "SIM-A-1", "plan": "Builder 50K", "stage": "eval", "armed": True}], keepalive={"x": True},
                           alerts=(True, True, True), clock=0.4)
    check("d2. a good clock stays green", L[-1].strip() == "[OK] Everything is green." and "(fine)" in "\n".join(L), L)
    outs, ran = [], []
    fx = dict(T._default_fx(), sync_clock=lambda: G.sync_clock(run=fake(DENIED, TASK_OK)))
    res = T.do_choice("9", out=outs.append, run=lambda a: ran.append(a) or 0, fx=fx)
    check("d3. menu 9 with the task = [OK], and it started no .bat", res.startswith("[OK]") and not ran, (res, ran))
    fx = dict(T._default_fx(), sync_clock=lambda: G.sync_clock(run=fake(DENIED, TASK_GONE)))
    res = T.do_choice("9", out=outs.append, run=lambda a: ran.append(a) or 0, fx=fx)
    check("d4. menu 9 without the task = [FIX] + the sentence, still no .bat, no phrase", res.startswith("[FIX]") and "FIX_CLOCK.bat" in res
          and not ran and "I ACCEPT" not in res, (res, ran))
    check("d5. the menu lists 'Fix the clock'", any("9" in m and "Fix the clock" in m for m in T.MENU), T.MENU)

    # e. the scripts
    def raw(p):
        return open(os.path.join(ROOT, p), "rb").read()
    for p in ("FIX_CLOCK.bat", "FIX_CLOCK_OFF.bat", "scripts/fix_clock.ps1"):
        b = raw(p)
        check(f"e1. {p}: ASCII only, CRLF everywhere", all(c < 128 for c in b) and b.count(b"\r\n") == b.count(b"\n") and len(b) > 200, p)
    for p in ("FIX_CLOCK.bat", "FIX_CLOCK_OFF.bat"):
        t = raw(p).decode()
        check(f"e2. {p}: detects non-admin and says it in plain words (never silent)",
              "net session" in t and 'right-click' in t and "Run as administrator" in t and t.count("pause") == 1, p)
    t = raw("scripts/fix_clock.ps1").decode()
    need = ["w32time", "Automatic", "time.cloudflare.com,0x9", "time.windows.com,0x9", "pool.ntp.org,0x9", "SpecialPollInterval", "900",
            "MaxPosPhaseCorrection", "MaxNegPhaseCorrection", "86400", "Type", "NTP", "/resync /force", "OlympusClock", "SYSTEM",
            "New-TimeSpan -Minutes 15", "AtStartup", "Power-Troubleshooter", "stripchart", "BEFORE", "AFTER", "[OK]", "[FIX]", "-Off",
            "Unregister-ScheduledTask", "GRGX;;;AU"]
    miss = [n for n in need if n not in t]
    check("e3. fix_clock.ps1 has every setting asked for", not miss, miss)
    check("e4. the ps1 uses no PowerShell-7-only syntax (&&, ?:, ??, -Parallel)", not any(x in t for x in (" && ", " ? ", " ?? ", "-Parallel")), "")
    check("e5. the bot's own clock never compensates: no 'time set' / Set-Date / w32tm /config of the bot side",
          "Set-Date" not in t and "set-date" not in t.lower(), "")
    check("e6. FIX_CLOCK_OFF calls the ps1 with -Off", "fix_clock.ps1\" -Off" in raw("FIX_CLOCK_OFF.bat").decode(), "")
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
