"""START BOT's exit codes read as plain lines (night-startmsg 2026-11-23). Before, TRADE_HOME's "2 Start bot" said "[FIX]
START_BOT.bat did not open. Tell Claude." whenever engine.go returned 1, e.g. when the phrase simply was not typed. Fakes only:
nothing starts, nothing is armed (the phrase is never typed here).

    python -X utf8 -m tests.test_startmsg        (~3 s)

1. engine.go records its last [FIX] reason (data/start_last.json next to its config: a temp folder here) and its exit code;
   start_line(): 0 = started, 1 = "stopped before arming: <reason>. Nothing new is armed", 9 = Python not found, other = code.
2. TRADE_HOME 2 and the Sunday routine (8) use them; MONDAY SETUP step 3 adds the reason; START_BOT.bat passes the code back.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import go as G, monday as M, trade_home as T  # noqa: E402
from tests.test_monday import Fake  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:400]) if info and not ok else ''}")
    RES.append(bool(ok))


def main():
    tmp = tempfile.mkdtemp(prefix="le_startmsg_")
    old_cfg = G.CFG
    G.CFG = os.path.join(tmp, "start_bot.json")
    try:
        # 1. the tee keeps the last [FIX] line; record_last / last_start / start_line
        buf = io.StringIO()
        tee = G._FixTee(buf)
        tee.write(" 50K (Zlarior): Sim101\n [FIX] NinjaTrader is not connected: Connections > your login.\n")
        tee.write(" Stopped. Nothing is armed.\n [FIX] START BOT stopped before the end. Double-click ...\n")
        check("1a. the window text passes through unchanged; the reason kept = the last real [FIX] / 'Stopped.' line",
              buf.getvalue().startswith(" 50K (Zlarior)") and tee.why == "Stopped. Nothing is armed.", tee.why)
        G.record_last(1, "The phrase was not typed. Nothing is armed", now=1000)
        last = G.last_start(now=1100)
        line = G.start_line(1, last)
        check("1b. exit 1 + its reason: '[FIX] START BOT stopped before arming: The phrase was not typed ... Nothing new is armed'",
              line.startswith("[FIX] START BOT stopped before arming: The phrase was not typed") and "Nothing new is armed" in line
              and "did not open" not in line, line)
        check("1c. 0 = started; 9 = Python not found; another code = its number; an old record (> 30 min) is not used",
              G.start_line(0).startswith("[OK]") and "Python not found" in G.start_line(9) and "code 3" in G.start_line(3)
              and G.last_start(now=1000 + 1801) is None)
        G.record_last(1, "The phrase was not typed. Nothing is armed", now=1160)     # the child (START BOT re-run after an update)
        G.record_last(1, "", now=1200, since=1150)                                   # the parent, same run, no reason of its own
        check("1d. the re-run after an update (same run, no reason of its own) keeps the child's reason",
              G.last_start(now=1201)["why"].startswith("The phrase was not typed"), G.last_start(now=1201))
        G.record_last(1, "", now=1300, since=1250)
        check("1e. a new run without a reason (older record) is written as it is", G.last_start(now=1301)["why"] == "")

        # 2. a real engine.go run with the input closed (dry run: nothing armed): exit 1 + plain line
        env = dict(os.environ, LE_GO_CFG_TEST="1")
        p = subprocess.run([sys.executable, "-X", "utf8", "-m", "engine.go", "--dry-run"], cwd=ROOT, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=120, env=env)
        check("2a. engine.go --dry-run with no input: exit 1, one plain [FIX] line, no traceback", p.returncode == 1
              and "[FIX]" in p.stdout and "Traceback" not in p.stdout + p.stderr, (p.returncode, p.stdout[-300:], p.stderr[-300:]))

        # 3. TRADE_HOME 2
        G.record_last(1, "Stopped. Nothing is armed", now=__import__("time").time())
        fx = {"bot": lambda: {"running": False}}
        r1 = T.do_choice("2", out=lambda *a: None, run=lambda argv: 1, fx=fx)
        r0 = T.do_choice("2", out=lambda *a: None, run=lambda argv: 0, fx={"bot": lambda: {"running": True}})
        r9 = T.do_choice("2", out=lambda *a: None, run=lambda argv: 9, fx=fx)
        check("3a. TRADE_HOME 2: exit 1 = 'stopped before arming: Stopped. Nothing is armed' (never 'did not open')",
              r1.startswith("[FIX] START BOT stopped before arming: Stopped. Nothing is armed") and "did not open" not in r1, r1)
        check("3b. exit 0 = the bot is running; exit 9 = Python not found", r0 == "[OK] The bot is running." and "Python not found" in r9, (r0, r9))
        answers = iter(["s", "", "s", "s"])
        outs = []
        T.routine(lambda *a: next(answers), outs.append, lambda argv: 1, fx)
        check("3c. the Sunday routine (8): START exit 1 says the same plain line", any("START BOT stopped before arming" in o for o in outs), outs)

        # 4. MONDAY SETUP step 3 carries the reason
        G.record_last(1, "NinjaTrader is not connected: Connections > your login", now=__import__("time").time())
        out = []
        r = M.run(Fake(start_rc=1), out=out.append)
        st = next(x for x in r["steps"] if x[0] == "3/4 Start")
        check("4. MONDAY SETUP step 3: '[FIX] not started (NinjaTrader is not connected: ...)'", st[1] is False
              and "not started (NinjaTrader is not connected" in st[2], st)

        # 5. START_BOT.bat passes the code back
        b = open(os.path.join(ROOT, "START_BOT.bat"), "rb").read().decode("utf-8").replace("\r\n", "\n")
        check("5. START_BOT.bat: RC = engine.go's errorlevel, 9 without Python, 'endlocal & exit /b %RC%'; CRLF kept",
              'set "RC=%errorlevel%"' in b and ':nopython\nset "RC=9"' in b and b.rstrip().endswith("endlocal & exit /b %RC%")
              and b.index("-m engine.go %*") < b.index('set "RC=%errorlevel%"')
              and "\r\n" in open(os.path.join(ROOT, "START_BOT.bat"), "rb").read().decode("utf-8"))
    finally:
        G.CFG = old_cfg
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    ok = sum(RES)
    print(f"\nstart messages: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
