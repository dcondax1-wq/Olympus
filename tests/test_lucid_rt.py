"""Lucid red team (day-lucidrt 2026-11-22): a Lucid row NEVER gets the typed phrase without the owner's recorded written OK,
whatever set "armed" (engine/multi_account.merge_into_start is the one choke point the phrase goes through).

    python -X utf8 -m tests.test_lucid_rt
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({info})" if info and not ok else ""))


def main():
    from engine import multi_account as MA
    P = "I ACCEPT LIVE RISK"
    rows = [
        {"id": "b25k_2", "enabled": True, "armed": True, "preset": "mffu_builder_25k", "nt_account": "MFFUEVBLD25K-X1", "cli": {"plan": "builder25k"}},
        {"id": "lucid", "enabled": True, "armed": True, "preset": "lucid_pro_50k", "nt_account": "LTPRO50K-X2", "cli": {"plan": "lucidpro50k"}},
        {"id": "lucid_hand", "enabled": True, "armed": True, "preset": "lucid_pro_50k", "nt_account": "LTPRO50K-X3"},
        {"id": "lucid_ok", "enabled": True, "armed": True, "preset": "lucid_pro_50k", "nt_account": "LTPRO50K-X4",
         "cli": {"plan": "lucidpro50k", "lucid_ok": "2026-11-23"}},
        {"id": "lucid_sim", "enabled": True, "armed": False, "preset": "lucid_pro_50k", "nt_account": "Sim205", "cli": {"plan": "lucidpro50k"}},
    ]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "accounts.json")
        MA.save_file(rows, p)
        body = MA.merge_into_start({"sym": "NQ"}, P, path=p)
        by = {a["id"]: a for a in body["accounts"]}
        check("MFFU extra account: armed + phrase as before", by["b25k_2"].get("armed") is True and by["b25k_2"].get("confirm") == P, by["b25k_2"])
        check("Lucid row armed by hand (e.g. multi_account --set --armed yes) but no written OK: NOT armed, no phrase",
              by["lucid"].get("armed") is False and "confirm" not in by["lucid"] and "Lucid" in (by["lucid"].get("held") or ""), by["lucid"])
        check("Lucid preset row without a cli block (hand-edited file): held too", by["lucid_hand"].get("armed") is False and "confirm" not in by["lucid_hand"])
        check("Lucid row WITH the recorded written OK: armed + phrase", by["lucid_ok"].get("armed") is True and by["lucid_ok"].get("confirm") == P)
        check("Sim Lucid account: not held (paper)", "held" not in by["lucid_sim"])
        body0 = MA.merge_into_start({"sym": "NQ"}, "", path=p)
        check("no phrase typed: nobody gets one", all("confirm" not in a for a in body0["accounts"]))
        # the spec the router builds from the start body: the held row is not armed
        spec = MA.normalize(by["lucid"]) if hasattr(MA, "normalize") else {"armed": by["lucid"].get("armed")}
        check("router spec of the held Lucid row: armed False, no confirm", not spec.get("armed") and not spec.get("confirm"), spec)
    n, ok = len(RES), sum(RES)
    print(f"lucid red team: {ok}/{n} {'ALL PASS' if ok == n else 'FAILED'}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
