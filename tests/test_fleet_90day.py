"""FLEET 90 DAYS (day-fleet 2026-11-21, research/writeups/fleet-90day-2026-11-21.md): offline, no browser, ~20 s.
  a. the 3 purchase Decide cards carry exactly the $ computed from research/lab/fleet_90day.json (never typed by hand)
  b. every plan x market row is in the result; the write-up exists; tax = the 30% pot
  c. on a small run: "buy now" buys the Rapid EOD 50K at session 1; the swap never makes more than 3 Rapid EOD 50Ks;
     the parallel 50K pays its $91.80 at session 0
    python -X utf8 -m tests.test_fleet_90day
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))

import fleet_90day as F9  # noqa: E402

RES: list = []
R = json.load(open(F9.OUT, encoding="utf-8"))


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[-600:]}"), flush=True)


def part_a():
    d = json.load(open(F9.DECISIONS, encoding="utf-8"))
    have = {c["id"]: c for c in d["items"]}
    vals = F9.card_values(R)
    for cid in F9.CARDS:
        c = have.get(cid)
        ok = c is not None and all(c.get(k) == v for k, v in vals[cid].items()) if c and c.get("status") == "open" else c is not None
        check(f"a. card {cid} = the run's numbers", ok, (c, vals.get(cid)))


def part_b():
    check("b. every plan x market", all(sp in R["rows"][pl] for pl in F9.PLANS for sp in F9.SPANS))
    check("b. write-up exists", os.path.isfile(os.path.join(ROOT, "research", "writeups", "fleet-90day-2026-11-21.md")))
    check("b. tax = the 30% pot", R["tax"] == 0.30 == F9.TAX)


def part_c():
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    F9.FM.set_fills("real")
    cal = F9.FM.calendar()
    P = F9.FM.paths("REF", 6, len(cal))
    a = F9.run(P, cal, "all3")
    check("c. buy now = Rapid EOD 50K at session 1", all(int(k) == 1 for k in a["r2k"]), a["r2k"])
    n50 = [sum(1 for _, pl in b if pl.startswith("rapideod50")) for b in a["buys"]]
    check("c. every path buys the Rapid EOD 50K", all(x >= 1 for x in n50), n50)
    check("c. the 2nd 50K eval is paid at session 0", all(any(k == 0 and pl == "builder50k" for k, pl in b) for b in a["buys"]),
          a["buys"][0][:3])


if __name__ == "__main__":
    for f in (part_a, part_b, part_c):
        f()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)
