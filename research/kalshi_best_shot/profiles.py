#!/usr/bin/env python3
"""Depth profiles from the saved public book snapshots (books.py / scan.py files): for every snapshot and side, the reference
price, everyone's score on that side, the queue in front of a new order at the reference and 1-3 ticks behind it, the ticks from
the best bid to the reference, and whether the snapshot counts (Target on both sides). Grouped by series and price bucket
(the side's reference price) for the backtest. Offline.
    python research/kalshi_best_shot/profiles.py [books files...] -> research/kalshi_best_shot/depth_profiles.json"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lip  # noqa: E402

BOOKS = os.environ.get("KREW_BOOKS", "/home/user/kalshi_cache/krew/books")
OFFSETS = (0, 1, 2, 3)
BUCKETS = ((0.0, 0.035, "c1"), (0.035, 0.105, "c2"), (0.105, 0.355, "lo"), (0.355, 0.655, "mid"), (0.655, 0.895, "hi"), (0.895, 1.0, "top"))


def bucket(p):
    for lo, hi, name in BUCKETS:
        if lo <= p < hi:
            return name
    return "top"


def side_obs(levels, other, target, df):
    lv = lip.norm(levels)
    ref = lip.ref_price(lv, target)
    if ref is None:
        return None
    best = lv[0][0]
    fl = lip.floor_price(lv, target)
    o = {"ref": ref, "best": best, "ticks": int(round((best - ref) / lip.TICK)), "S": lip.side_score(lv, ref, df, target),
         "valid": lip.side_valid(lv, target) and lip.side_valid(other, target),
         "floor_ticks": int(round((ref - fl) / lip.TICK)) if fl is not None else -1}
    for k in OFFSETS:
        p = round(ref - k * lip.TICK, 2)
        o["ahead%d" % k] = lip.ahead(lv, p)
    return o


def build(files):
    obs = []
    for fn in files:
        try:
            for ln in gzip.open(fn, "rt"):
                r = json.loads(ln)
                pr = r["prog"]
                for sd, L, O in (("yes", r["yes"], r["no"]), ("no", r["no"], r["yes"])):
                    o = side_obs(L, O, pr["target"], pr["df"])
                    if o:
                        o.update(s=r["s"], m=r["m"], side=sd, t=r["t"], usd_day=pr["usd_day"], target=pr["target"])
                        obs.append(o)
        except (OSError, EOFError, ValueError):
            continue
    prof = collections.defaultdict(lambda: collections.defaultdict(list))
    for o in obs:
        prof[o["s"]][bucket(o["ref"])].append({k: (round(v, 2) if isinstance(v, float) else v) for k, v in o.items()
                                               if k in ("S", "ticks", "valid", "ref", "usd_day", "target", "floor_ticks") or k.startswith("ahead")})
    return obs, {s: dict(b) for s, b in prof.items()}


def main():
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(BOOKS, "*.jsonl.gz")))
    obs, prof = build(files)
    out = {"files": [os.path.basename(f) for f in files], "n_obs": len(obs), "buckets": [b[2] for b in BUCKETS], "profiles": prof}
    json.dump(out, open(os.path.join(HERE, "depth_profiles.json"), "w"), separators=(",", ":"))
    for s, b in sorted(prof.items()):
        print("%-22s" % s, " ".join("%s:%d" % (k, len(v)) for k, v in sorted(b.items())))
    print("obs", len(obs))


if __name__ == "__main__":
    main()
