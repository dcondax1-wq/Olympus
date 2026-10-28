"""Read research/scalp/mo_grid_*.json: H1-picked tops per family and timeframe, chance counts, and configs positive in every
span (1m: H1 + H2 2026 + the same rule on 5m 2021-25; 5m: H1 + H2 + 2021-25).

    python -X utf8 tools/scalp_mo_ana.py [family ...]
"""
from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "scalp")


def load(fam):
    return json.load(open(os.path.join(OUT, f"mo_grid_{fam}.json")))


def fmt(s):
    if not s or not s.get("n"):
        return "   -   "
    return f"{s['tpw']:>5}/wk pf{s['pf']:<5} R{s['avg_r']:<6} ${s['net']:>7}"


def summary(fam, min_tpw=5.0, top=5):
    R = load(fam)
    out = {"fam": fam, "n_cfg": len(R)}
    for tf in ("1m", "5m"):
        ok = [r for r in R if r.get(f"{tf}_H1", {}).get("tpw", 0) >= min_tpw and r.get(f"{tf}_H2", {}).get("n")]
        if not ok:
            continue
        ok.sort(key=lambda r: -r[f"{tf}_H1"].get("t_r", -9))
        t20 = ok[:20]
        h2pos = sum(1 for r in t20 if r[f"{tf}_H2"]["net"] > 0)
        rpos = sum(1 for r in t20 if r.get("5m_R", {}).get("net", -1) > 0)
        allpos = [r for r in ok if r[f"{tf}_H1"]["net"] > 0 and r[f"{tf}_H2"]["net"] > 0 and r.get("5m_R", {}).get("net", -1) > 0
                  and r.get("5m_R", {}).get("tpw", 0) >= 3]
        h12 = [r for r in ok if r[f"{tf}_H1"]["net"] > 0 and r[f"{tf}_H2"]["net"] > 0]
        print(f"{fam} {tf}: {len(ok)} cfgs >= {min_tpw}/wk | H1 top20: {h2pos} H2+, {rpos} 5m-R+ | H1&H2 +: {len(h12)} | all three +: {len(allpos)} "
              f"| H1+ share {sum(1 for r in ok if r[f'{tf}_H1']['net'] > 0) / len(ok):.2f}, H2+ share {sum(1 for r in ok if r[f'{tf}_H2']['net'] > 0) / len(ok):.2f}")
        for r in t20[:top]:
            print(f"   pick  H1 {fmt(r[f'{tf}_H1'])} | H2 {fmt(r[f'{tf}_H2'])} | 5mR {fmt(r.get('5m_R'))} | md{r['maxday']} {json.dumps(r['p'])}")
        allpos.sort(key=lambda r: -min(r[f"{tf}_H1"]["t_r"], r[f"{tf}_H2"]["t_r"]))
        for r in allpos[:top]:
            print(f"   all+  H1 {fmt(r[f'{tf}_H1'])} | H2 {fmt(r[f'{tf}_H2'])} | 5mR {fmt(r.get('5m_R'))} | md{r['maxday']} {json.dumps(r['p'])}")
        out[tf] = {"ok": len(ok), "top20_h2pos": h2pos, "top20_rpos": rpos, "h1h2pos": len(h12), "allpos": len(allpos)}
    return out


if __name__ == "__main__":
    fams = sys.argv[1:] or sorted(os.path.basename(p)[8:-5] for p in glob.glob(os.path.join(OUT, "mo_grid_*.json")))
    for f in fams:
        summary(f)
