"""Red team on day-combo25 (2026-11-23). Temp folders only, nothing armed, the real data/combo_50k.json never touched.

    python -X utf8 -m tests.test_combo25_rt        (~2 s)

1. the switch writer renames AFTER closing its temp file (FOUND: the rename ran inside the `with`, on a file still open for
   writing: Windows refuses that, so --on / --off raised and never wrote the switch); --on twice keeps both Names; --off
   --account turns one off; an old one-Name file (first build) reads as that Name; on: false = no Name.
2. keep-alive: the combo lane (LiveBot.acct_x) is a lane of the SAME target as its extra account (grouped by the NinjaTrader
   Name, key x:<id>), so the keep-alive sees ATLAS's ledger, legs and open trade there (FOUND: only NinjaTrader's Log saw
   them); OFF (acct_x = {}) = the lanes are exactly as before.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import combo50k as CB, keepalive as KA  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info and not ok else ''}")
    RES.append(bool(ok))


def _writer_closes_first():
    src = open(os.path.join(ROOT, "engine", "combo50k.py"), encoding="utf-8").read()
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_write_switch")
    for w in [n for n in ast.walk(fn) if isinstance(n, ast.With)]:
        if any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_rep" for c in ast.walk(w)):
            return False
    return True


def main():
    from engine.go import LIVE_PHRASE
    check("1. _write_switch renames after the temp file is closed (never inside the with)", _writer_closes_first())
    with tempfile.TemporaryDirectory() as root:
        ok = lambda: (True, "80/80")  # noqa: E731
        a = CB.set_on("Sim101", LIVE_PHRASE, root=root, selftest=ok, today="2026-11-23")
        b = CB.set_on("Sim252", LIVE_PHRASE, root=root, selftest=ok, today="2026-11-23")
        sw = CB.read_switch(root)
        check("1. --on for the 50K then the 25K #2: both Names on", a.get("ok") and b.get("ok") and sw["accounts"] == ["Sim101", "Sim252"]
              and CB.switch_on_for("Sim252", root) and not os.path.exists(os.path.join(root, CB.SWITCH_REL) + ".tmp"), (a, b, sw))
        CB.set_off(root=root, account="Sim252", today="2026-11-23")
        sw = CB.read_switch(root)
        check("1. --off --account Sim252: only that one off", sw["on"] and sw["accounts"] == ["Sim101"] and not CB.switch_on_for("Sim252", root), sw)
        w = CB.set_on("Sim252", "yes", root=root, selftest=ok)
        check("1. no phrase ('yes'): nothing switched on", not w.get("ok") and not CB.switch_on_for("Sim252", root), w)
        p = os.path.join(root, CB.SWITCH_REL)
        json.dump({"on": True, "account": "Sim101"}, open(p, "w"))
        check("1. a first-build file (one 'account') reads as that one Name", CB.read_switch(root)["accounts"] == ["Sim101"])
        json.dump({"on": False, "account": "Sim101", "accounts": ["Sim101"]}, open(p, "w"))
        check("1. on: false = no Name at all", CB.read_switch(root)["accounts"] == [] and not CB.switch_on_for("Sim101", root))

    nt = types.SimpleNamespace(name="ninjatrader", account="Sim252")
    acc = types.SimpleNamespace(id="z25b", problem=None, spec={"nt_account": "Sim252", "adapter": "ninjatrader"}, adapter=nt)
    bot = types.SimpleNamespace(cfg={"model": "lit"}, adapter=None, state={}, acct_b=None, acct_r=None, acct_r2=None, acct_c=None,
                                fleet=None, accts=types.SimpleNamespace(accounts=[acc]), acct_x={})
    off = KA.lanes(bot)
    check("2. OFF (acct_x = {}): the lanes are exactly the extra account's", [l["key"] for l in off] == ["x:z25b"], off)
    x = types.SimpleNamespace(acc_id="z25b", problem=None, name="Sim252", adapter=types.SimpleNamespace(name="ninjatrader", account="Sim252"))
    bot.acct_x = {"z25b": x}
    on = KA.lanes(bot)
    check("2. ON: the combo lane is listed (kind acct, key x:z25b, the same Name)",
          any(l["obj"] is x and l["kind"] == "acct" and l["key"] == "x:z25b" and l["nt"] == "Sim252" for l in on), on)
    try:
        import engine.lifecycle as LC
        real = LC.is_stood_down
    except Exception:
        LC, real = None, None
    gs = [g for g in KA.targets(bot)]
    g = next((g for g in gs if g["key"] == "x:z25b"), None)
    check("2. ON: ONE target for the 25K #2 holding both lanes (its LIT lane is the main one)",
          len(gs) == 1 and g is not None and {id(l["obj"]) for l in g["lanes"]} == {id(acc), id(x)} and g["main"]["obj"] is acc,
          [(g["key"], [l["kind"] for l in g["lanes"]]) for g in gs])
    ok = sum(RES)
    print(f"\ncombo25 red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
