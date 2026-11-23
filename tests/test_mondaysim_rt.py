"""Red team on night-mondaysim (2026-11-23): UPDATE.bat's new exit code must not make a GOOD update read as failed, and
START must always run from MONDAY SETUP. Fakes only (nothing runs, nothing armed).

    python -X utf8 -m tests.test_mondaysim_rt        (~1 s)

1. UPDATE.bat: all green leaves RC=0 (FOUND: RC=2 "red lines" was set on the ALL-GREEN path, and the red-lines path kept 0);
   RC=2 is set only after the :fixes label; RC=1 only for a failed pull / no Python.
2. TRADE_HOME "7 Update": exit 0 = the normal result line; 2 = the result + "red lines"; 1 = "[FIX] did not go through"
   (FOUND: any non-zero read "[FIX] UPDATE.bat did not open"); another .bat's non-zero still reads "did not open".
3. MONDAY SETUP: update exit 0 / 1 / 2 each give the right line, and START runs after every one of them.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import monday as M, trade_home as T  # noqa: E402
from tests.test_monday import Fake  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:400]) if info and not ok else ''}")
    RES.append(bool(ok))


def main():
    u = open(os.path.join(ROOT, "UPDATE.bat"), encoding="utf-8").read().replace("\r\n", "\n")
    green = u[u.index("--after-update"):u.index("UPDATE done. All green.")]
    fixes = u[u.index("\n:fixes\n"):u.index("\n:intrade\n")]
    check("1. UPDATE.bat all green keeps RC=0; RC=2 only on the :fixes (red lines) path",
          'set "RC=2"' not in green and 'if "%RC%"=="0" set "RC=2"' in fixes and u.count('set "RC=2"') == 1, (green, fixes))
    check("1. RC=1 only for a failed pull / no Python", u.count('set "RC=1"') == 2 and 'if defined PULLFAIL set "RC=1"' in u)

    fx = {"bot": lambda: {"ok": True}}
    got = {rc: T.do_choice("7", out=lambda *a: None, run=lambda argv, rc=rc: rc, fx=fx) for rc in (0, 1, 2, 5)}
    check("2. TRADE_HOME 7: exit 0 = the normal 'Updated' line", got[0].startswith("[OK] Updated"), got[0])
    check("2. exit 2 = 'Updated' + red lines (not 'did not open')", got[2].startswith("[OK] Updated") and "red lines" in got[2], got[2])
    check("2. exit 1 = '[FIX] The update did not go through'", got[1].startswith("[FIX] The update did not go through"), got[1])
    check("2. any other code = 'did not open'", "did not open" in got[5], got[5])
    other = next((k for k, v in T.ACTIONS.items() if v[1] not in ("UPDATE.bat", "START_BOT.bat")), None)   # START: its own codes (night-startmsg)
    if other:
        r = T.do_choice(other, out=lambda *a: None, run=lambda argv: 1, fx={**fx, **{k: (lambda *a, **kw: {}) for k in ("sync_clock",)}})
        check(f"2. another .bat ({T.ACTIONS[other][1]}) exit 1 still reads 'did not open'", "did not open" in str(r), r)

    for rc, want_ok, want in ((0, True, "already the newest"), (2, True, "red lines"), (1, False, "did not go through")):
        f = Fake(upd=rc)
        out = []
        r = M.run(f, out=out.append)
        st = r["steps"][0]
        check(f"3. MONDAY: update exit {rc} -> {'OK' if want_ok else 'FIX'} '{want}', and START still runs",
              st[1] is want_ok and want in st[2] and "start" in f.calls and "alert" in f.calls, (st, f.calls))

    ok = sum(RES)
    print(f"\nmondaysim red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
