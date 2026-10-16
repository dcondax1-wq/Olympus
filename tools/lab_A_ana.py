"""Track A helper: break a saved variant's trades down by group (research/lab/A_trades/<name>__<period>.json)."""
import collections
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = dt.timezone(dt.timedelta(hours=-4))


def load(name):
    p = name if os.path.exists(name) else os.path.join(ROOT, "research", "lab", "A_trades", name + ".json")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def grp(tr, key):
    g = collections.defaultdict(list)
    for t in tr:
        g[key(t)].append(t)
    for k in sorted(g, key=lambda x: str(x)):
        v = g[k]
        pn = [t["pnl"] for t in v]
        gp, gl = sum(x for x in pn if x > 0), -sum(x for x in pn if x < 0)
        print(f"  {str(k):22s} n={len(v):3d} wr={100 * sum(x > 0 for x in pn) / len(v):5.1f} "
              f"avgR={sum(t['r'] for t in v) / len(v):+.2f} net={sum(pn):+7.0f} pf={gp / gl if gl else 99:.2f}")


HALF = lambda t: "H1" if t["day"] <= "2026-03-31" else "H2"
KEYS = {
    "half": HALF,
    "dir": lambda t: HALF(t) + (" L" if t["dir"] == 1 else " S"),
    "trigger": lambda t: HALF(t) + " " + str(t["trigger"]),
    "exit": lambda t: t["exit"],
    "month": lambda t: t["day"][:7],
    "hour": lambda t: dt.datetime.fromtimestamp(t["entry_t"], ET).hour,
    "regime": lambda t: t.get("regime"),
    "er10": lambda t: None if t["f"].get("rg_er10") is None else round(t["f"]["rg_er10"] * 10) / 10,
    "htf": lambda t: t["f"].get("htf_trend"),
    "with_day": lambda t: t["f"].get("x_with_day"),
    "counter5d": lambda t: t["f"].get("rg_counter_5d"),
    "rr_plan": lambda t: None if t["f"].get("rr_plan") is None else round(t["f"]["rr_plan"]),
    "risk_pts": lambda t: int(t["risk_pts"] // 10 * 10),
    "vix": lambda t: None if t["f"].get("vix_prev") is None else int(t["f"]["vix_prev"] // 3 * 3),
}

if __name__ == "__main__":
    d = load(sys.argv[1])
    tr = d["trades"]
    keys = sys.argv[2].split(",") if len(sys.argv) > 2 else list(KEYS)
    print(len(tr), "trades")
    for k in keys:
        print(k)
        grp(tr, KEYS[k])
