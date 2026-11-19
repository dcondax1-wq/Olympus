#!/usr/bin/env python3
"""K6: free official daily series from FRED's public csv download (no key): Treasury par / constant-maturity yields
(the same numbers Kalshi's Treasury markets settle on), bill yields, Fed target range, EFFR, SOFR, Freddie Mac PMMS.
Writes data/fred.json {series: {date: value}}. Polite (1 request a second, cached)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk6

SERIES = ["DGS10", "DGS2", "DGS5", "DGS30", "DGS1MO", "DGS3MO", "DGS6MO", "DGS1", "DTB4WK", "DTB3", "DTB6",
          "DFEDTARU", "DFEDTARL", "EFFR", "SOFR", "MORTGAGE30US", "DGS7", "DGS20"]


def load():
    return json.load(open(os.path.join(kk6.DATA, "fred.json")))


def main():
    out = {}
    for s in SERIES:
        txt = kk6.get("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": s}, raw=True, cache=True)
        d = {}
        for line in (txt or "").splitlines()[1:]:
            p = line.strip().split(",")
            if len(p) == 2 and p[1] not in ("", "."):
                try:
                    if p[0] >= "2019-01-01":
                        d[p[0]] = float(p[1])
                except ValueError:
                    pass
        out[s] = d
        print(s, len(d), min(d) if d else None, max(d) if d else None, flush=True)
    os.makedirs(kk6.DATA, exist_ok=True)
    json.dump(out, open(os.path.join(kk6.DATA, "fred.json"), "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
