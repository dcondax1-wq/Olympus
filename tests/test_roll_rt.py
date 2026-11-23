"""Roll red team (2026-11-23): TRADE_HOME R says what ROLL.bat really found (exit 2 = not now, never "did not open").
    python -X utf8 -m tests.test_roll_rt
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import trade_home as T  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))


def main():
    fx = dict(T._default_fx(), roll=lambda: {"level": "bad", "say": "chart MNQ 12-26, orders MNQ 03-27"})
    r2 = T.do_choice("R", out=lambda *_: None, run=lambda a: 2, fx=fx)
    check("exit 2 (in a trade / too early): 'Not now', nothing switched", r2.startswith("[OK] Not now"), r2)
    r1 = T.do_choice("r", out=lambda *_: None, run=lambda a: 1, fx=fx)
    check("exit 1 (a click for you): the roll's own words, not 'did not open'", r1.startswith("[FIX] chart MNQ 12-26") and "did not open" not in r1, r1)
    fx["roll"] = lambda: {"level": "ok", "say": "chart MNQ 03-27, orders MNQ 03-27"}
    r0 = T.do_choice("r", out=lambda *_: None, run=lambda a: 0, fx=fx)
    check("exit 0: [OK] with the check", r0.startswith("[OK] Roll check"), r0)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
