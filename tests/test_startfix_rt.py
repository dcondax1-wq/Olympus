"""startfix red team (2026-11-23): the hard / soft route split never lets a wrong route trade; known_role never calls a NEW
account known; a Rapid Name is a Rapid. Offline: fake bot states and rows only.

    python -X utf8 -m tests.test_startfix_rt
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import go as G  # noqa: E402
from engine import account_cli as AC  # noqa: E402
from engine import onboard as OB  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{str(info)[:300]}]"))


LIT, ATL = "MFFUEVBLDR000006016", "MFFUSFBLDR000006018"


def st(nt=LIT, run=True, adapter="ninjatrader", extras=()):
    return {"running": run, "cfg": {"nt_account": nt, "adapter": adapter, "accounts": [dict(e) for e in extras]}}


def b(acct=ATL, armed=True, plan="builder25k"):
    return {"account": acct, "armed": armed, "plan": plan}


def main() -> int:
    cases = [
        ("all right", st(), b(), [], []),
        ("ATLAS not armed on its 25K: soft only (Zlarior keeps trading)", st(), b(armed=False), [], ["not armed"]),
        ("ATLAS ARMED on another Name: hard (a wrong route)", st(), b(acct="MFFUSFBLDR000009999"), ["not the 25K"], []),
        ("ATLAS NOT armed on another Name: soft (it cannot trade)", st(), b(acct="MFFUSFBLDR000009999", armed=False), [], ["not the 25K"]),
        ("ATLAS ARMED on the wrong plan: hard", st(), b(plan="builder50k"), ["plan"], []),
        ("ATLAS armed on Zlarior's own 50K: hard", st(), b(acct=LIT), ["not the 25K"], []),
        ("Zlarior on the wrong Name: hard even with ATLAS unarmed", st(nt="MFFUEVBLDR000001111"), b(armed=False), ["Zlarior is on"], ["not armed"]),
        ("the 25K also an extra (double route): hard", st(extras=[{"nt_account": ATL, "enabled": True}]), b(), ["extra"], []),
        ("bot not running: hard", st(run=False), b(), ["not running"], []),
        ("paper adapter: hard", st(adapter="paper"), b(), ["not NinjaTrader"], []),
    ]
    for nm, s, blk, want_h, want_s in cases:
        r = G.route_problems(LIT, ATL, state=s, b=blk)
        h, so = " ".join(r["hard"]), " ".join(r["soft"])
        ok = all(w in h for w in want_h) and all(w in so for w in want_s) and (bool(r["hard"]) == bool(want_h)) \
            and (bool(r["soft"]) == bool(want_s))
        check(f"a. {nm}", ok, r)
    check("a. verify_routes = the hard list only (the stop decision)", G.verify_routes(LIT, ATL, state=st(), b=b(armed=False)) == [])
    rows = [{"name": LIT, "role": "main"}, {"name": ATL, "role": "b"}, {"name": "MFFUEVREOD000003333", "role": "rapid", "id": "rapid"}]
    real_ro = G.role_of
    G.role_of = lambda n, *a, **k: None
    try:
        check("b. known_role: a NEW real account is never 'known'", AC.known_role("MFFUEVBLDR000007777", rows=rows) is None)
        check("b. known_role: the Rapid's Name is known (never offered as new)", "Rapid" in str(AC.known_role("MFFUEVREOD000003333", rows=rows)))
        check("b. known_role: no partial / case match", AC.known_role("mffuevreod000003333", rows=rows) is None
              and AC.known_role("MFFUEVREOD00000333", rows=rows) is None)
    finally:
        G.role_of = real_ro
    p = OB.parse_name("MFFUEVREOD000003333")
    i25, i50, inone = (OB.infer("MFFUEVREOD000003333", bal) for bal in (25000.0, 50000.0, None))
    check("c. MFFUEVREOD = Rapid; the size from the balance; no balance = still a choice (guess)",
          p["plan"] == "rapid" and i25.get("plan") == "rapideod25" and i50.get("plan") == "rapideod" and inone.get("guess") is True,
          (p, i25.get("plan"), i50.get("plan"), inone.get("guess")))
    check("c. a Builder Name never reads as Rapid", OB.parse_name("MFFUEVBLDR000006016")["plan"] == "builder")
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
