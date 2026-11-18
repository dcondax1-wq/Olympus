"""tools/kalshi_paper.py: the K1 forward paper tester. Offline and deterministic: a stub public API, no network, nothing outside
a temp folder. Checks the fee rounding, the dead-bracket logic, de-duplication, settlement, the paper-only ledger, and that no
order or portfolio endpoint is ever called (the tool is GET-only on public market data).
    python -X utf8 -m tests.test_kalshi_paper
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import kalshi_paper as KP  # noqa: E402


def main() -> int:
    rc = KP.selftest()
    src = open(os.path.join(ROOT, "tools", "kalshi_paper.py"), encoding="utf-8").read()
    ok = True
    for bad in ("/portfolio", "/orders", "Authorization", "KALSHI-ACCESS", "private_key", "method=\"POST\"", "method='POST'"):
        if bad in src.replace("\"/orders\" in u", "").replace("\"/portfolio\" in u", ""):
            print(f"[FAIL] source mentions {bad}")
            ok = False
    if not re.search(r"PAPER ONLY", src):
        print("[FAIL] the docstring must say PAPER ONLY")
        ok = False
    print("[PASS] GET-only, no key handling in the source" if ok else "[FAIL] source checks")
    ok = pc_hook() and ok
    return 0 if rc == 0 and ok else 1


def pc_hook() -> bool:
    """the public card (<= 200 bytes), the PC guard / maybe_run (LE_KALSHI_K1=0 = off) and read_card's age rule."""
    import json
    import tempfile
    import time
    good = True

    def check(name, cond):
        nonlocal good
        print(("[PASS] " if cond else "[FAIL] ") + name)
        good = good and bool(cond)
    led = KP.load_ledger("/nonexistent")
    led["started"], led["updated"] = "2026-11-18T00:00:00Z", "2026-11-19T12:00:00Z"
    led["open"] = [{"rule": "wx_lock", "ticker": "A", "price_c": 90}]
    led["closed"] = [{"rule": "wx_lock", "ticker": "B", "price_c": 90, "pnl_c": 10, "won": True},
                     {"rule": "idx_model", "ticker": "C", "price_c": 50, "pnl_c": -50, "won": False}]
    c = KP.public_summary(led)
    check("card: 3 signals, 2 settled, net -$0.40, -$0.286 per $1, 1.5 days, paper only",
          c["sig"] == 3 and c["set"] == 2 and c["net"] == -0.4 and c["pu"] == -0.286 and c["days"] == 1.5 and c["paper_only"] is True)
    check("card: <= 200 bytes", len(json.dumps(c, separators=(",", ":"))) <= 200)
    with tempfile.TemporaryDirectory() as d:
        env = {}
        P = KP.pc_paths(d)
        ok, why = KP.pc_guard(1e6, env, d)
        check("guard: starts when nothing runs", ok)
        check("guard: LE_KALSHI_K1=0 = off", KP.pc_guard(1e6, {"LE_KALSHI_K1": "0"}, d)[0] is False)
        spawned = []
        pid = KP.maybe_run(say=lambda *_: None, env=env, now=1e6, pc_dir=d, spawn_fn=lambda tok, pd: spawned.append(tok) or 77)
        check("maybe_run: starts one child (token in run.json)", pid == 77 and len(spawned) == 1 and json.load(open(P["run"]))["token"] == spawned[0])
        check("maybe_run: not twice while it is starting", KP.maybe_run(say=lambda *_: None, env=env, now=1e6 + 100, pc_dir=d, spawn_fn=lambda *a: 78) is None)
        check("maybe_run: off with LE_KALSHI_K1=0", KP.maybe_run(say=lambda *_: None, env={"LE_KALSHI_K1": "0"}, now=9e6, pc_dir=d, spawn_fn=lambda *a: 79) is None)
        KP.write_json(P["pub"], c)
        check("read_card: fresh card read back", (KP.read_card(P["pub"]) or {}).get("sig") == 3)
        check("read_card: older than 2 days = None", KP.read_card(P["pub"], now=time.time() + 3 * 86400) is None)
        KP.write_json(P["pub"], {"kind": "x", "paper_only": True})
        check("read_card: junk = None", KP.read_card(P["pub"]) is None)
    return good


if __name__ == "__main__":
    sys.exit(main())
