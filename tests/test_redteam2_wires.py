"""Red team 2 (2026-11-20) checks for the patches the LEAD applies (research/handoff/2026-11-20/redteam2/LEAD_WIRES.md L2).
Red on the code before the patch, green after.   python -X utf8 -m tests.test_redteam2_wires"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    from engine import account_cli, go, rapid
    rows = [{"name": "MFFUEVLB25K0002222", "role": "extra", "id": "zlarior25_2", "plan": "builder25k"}]
    saved = (account_cli.inventory, go._read)
    account_cli.inventory = lambda: rows
    go._read = lambda p: {"lit": "MFFUEVLB50K0001111", "atlas": "MFFUFUNDB25K0003333"}
    try:
        why = rapid.name_problem("MFFUEVLB25K0002222")
        ok_new = rapid.name_problem("MFFUEVRPD25K0004444")
    finally:
        account_cli.inventory, go._read = saved
    res = [("engine.rapid --account refuses the Name of an extra account (Zlarior 25K #2): one NinjaTrader account, one bot "
            "set", bool(why) and "zlarior25_2" in why, why),
           ("a new Rapid Name is still accepted", ok_new is None, ok_new)]
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + ("" if ok else f"  -> {d}"))
    n = sum(ok for _, ok, _ in res)
    print(f"\nredteam2 wires: {n}/{len(res)} checks passed")
    return 0 if n == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
