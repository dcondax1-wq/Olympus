#!/usr/bin/env python3
"""K7 step 4: write one rule's trade list in the red team's verifier format and run research/kalshi_red_team/verify.py on it.
    python research/kalshi_edge_K7/export_verify.py FAMILY|all BAND|all HORIZON|all [--rules-tried N] [--half test|all]
Writes research/kalshi_edge_K7/trades_<name>.json (small) and prints the verifier's report.
Order time ts = decision time + 1 s; info_ts = the end of the candle whose quote was used (never after the decision time)."""
import argparse
import gzip
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("KK7_CACHE", "/home/user/kalshi_cache/knew2")
VERIFY = os.path.join(HERE, "..", "kalshi_red_team", "verify.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fam")
    ap.add_argument("band")
    ap.add_argument("h")
    ap.add_argument("--rules-tried", type=int, default=200)
    ap.add_argument("--half", default="all")
    ap.add_argument("--name", default=None)
    ap.add_argument("--one-per-market", action="store_true", help="keep only the earliest qualifying trade of each market")
    a = ap.parse_args()
    with gzip.open(os.path.join(CACHE, "trades_all.json.gz"), "rt") as fh:
        T = json.load(fh)
    sel = [x for x in T if (a.fam == "all" or x["fam"] == a.fam) and (a.band == "all" or x["band"] == a.band)
           and (a.h == "all" or x["h"] in a.h.split(",")) and (a.half == "all" or x["half"] == ("new" if a.half == "test" else "old"))]
    if a.one_per_market:
        first = {}
        for x in sorted(sel, key=lambda x: x["ts"]):
            first.setdefault(x["t"], x)
        sel = list(first.values())
    rows = []
    for i, x in enumerate(sorted(sel, key=lambda x: x["ts"])):
        rows.append({"id": "%s|%s|%s" % (x["t"], x["h"], x["side"]), "ts": x["ts"] + 1, "info_ts": x["info_ts"], "settle_ts": x["settle_ts"],
                     "price": round(x["price"] / 100.0, 2), "contracts": x["C"], "side": x["side"], "outcome": x["won"],
                     "fee_rate": round(0.07 * x["mult"], 4), "event": x["e"], "ticker": x["t"], "half": x["half"]})
    name = a.name or "%s_%s_%s_%s" % (a.fam, a.band, a.h, a.half)
    out = os.path.join(HERE, "trades_%s.json" % name.replace("/", "-"))
    rule = {"name": "K7 carry: %s, %s, %s before the scheduled close (%s half)" % (a.fam, a.band, a.h, a.half), "rules_tried": a.rules_tried}
    with open(out, "w") as fo:
        json.dump({"rule": rule, "trades": rows}, fo)
    print("wrote %s (%d trades)" % (out, len(rows)), flush=True)
    cmd = [sys.executable, VERIFY, out, "--rules-tried", str(a.rules_tried), "--split", "2026-09-19", "--stake", "10"]
    subprocess.call(cmd)


if __name__ == "__main__":
    main()
