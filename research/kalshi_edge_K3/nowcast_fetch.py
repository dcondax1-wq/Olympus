#!/usr/bin/env python3
"""K3 angle 2: free outside forecasts.
  * Cleveland Fed inflation nowcast (public JSON behind their web chart): daily nowcast of CPI and core CPI m/m for each target
    month, plus the actual print. Saved compact to data/nowcast_cpi.json  {"YYYY-MM": {"days": [[ "YYYY-MM-DD", cpi, core ], ...],
    "actual": [cpi, core]}}. Caveat: this is the chart's archive; the Cleveland Fed describes it as the nowcast as of each day.
  * FRED initial claims (ICSA, weekly, free CSV, no key) -> data/icsa.json [[date, value], ...]
    (latest vintage, not real time: revisions to claims are small, a few thousand).

    python research/kalshi_edge_K3/nowcast_fetch.py
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk

URL = "https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json"


def main():
    raw = kk.get(URL, raw=True)
    d = json.loads(raw)
    out = {}
    for x in d:
        tgt = x["chart"].get("subcaption")  # 'YYYY-M'
        y, m = (int(v) for v in tgt.split("-"))
        labels = [c["label"] for c in x["categories"][0]["category"]]
        ds = {s["seriesname"]: s["data"] for s in x["dataset"]}
        days = []
        for i, lab in enumerate(labels):
            mt = re.match(r"(\d+)/(\d+)", lab.strip())
            if not mt:
                continue
            mm, dd = int(mt.group(1)), int(mt.group(2))
            yy = y + (1 if mm < m else 0)
            def val(name):
                try:
                    return float(ds[name][i]["value"])
                except Exception:
                    return None
            days.append([f"{yy:04d}-{mm:02d}-{dd:02d}", val("CPI Inflation"), val("Core CPI Inflation")])
        act = [None, None]
        for name, k in (("Actual CPI Inflation", 0), ("Actual Core CPI Inflation", 1)):
            for p in ds.get(name, []):
                if p.get("value") not in ("", None):
                    act[k] = float(p["value"])
        out[f"{y:04d}-{m:02d}"] = {"days": days, "actual": act}
    json.dump(out, open(os.path.join(kk.DATA, "nowcast_cpi.json"), "w"), separators=(",", ":"))
    print("nowcast months", len(out), min(out), max(out))
    txt = kk.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=ICSA", raw=True, ua="curl/8.5.0", tries=3)
    rows = [[a.split(",")[0], int(float(a.split(",")[1]))] for a in txt.splitlines()[1:] if re.match(r"\d{4}-", a) and a.split(",")[1] not in ("", ".")]
    rows = [r for r in rows if r[0] >= "2015-01-01"]
    json.dump(rows, open(os.path.join(kk.DATA, "icsa.json"), "w"), separators=(",", ":"))
    print("icsa", len(rows), rows[-1])


if __name__ == "__main__":
    main()
