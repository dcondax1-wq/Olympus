"""Why LIT setups were rejected: every 5m CISD candidate of the live settings, with the first rule it failed.

The same verdict as the day brief's log (engine/lit_brief.reject_reason: window, shallow sweep, weak displacement, no
inducement, NWOG / Mon-Wed rule, Monday rule, stop out of range, no 1.5R target), on every session of the backtest data
(data/NQ_5m.csv + NQ_1m.csv, the live params in live_model.json "lit"). A candidate that passes every rule is
  traded     the trade the engine took (tools/lit_final.run on the live params = run lit_live)
  day        the day already had its trade (1 trade a day)
  no fill    the limit was not tapped within 30 min, no 1m CISD within 20 bars of the tap, or the 1.5R check at the fill failed
Output research/lab/rejections.json (both dashboards: PC Data -> Rejected setups, phone Lab -> Rejected setups):
  spans  last20 (the last 20 sessions), 2026, H1, H2, 2021-25: setups, traded, per rule {n, pct, of_setups}, per week
  recent the last 60 candidates with their rule and the plain reason

    python -X utf8 tools/lit_rejections.py [--days N]     # N = the "last" span (default 20 sessions)
Read-only research: changes nothing in the strategy. ~15 s with the LIT candidate cache (research/runs/_cache).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "rejections.json")
RULES = [("window", "outside the entry window"), ("depth", "shallow sweep"), ("disp", "weak displacement"),
         ("idm", "no inducement first"), ("nwog", "NWOG side"), ("mw", "Mon-Wed rule"), ("monday", "Monday rule"),
         ("stop", "stop out of range"), ("target", "no 1.5R target"), ("day", "1 trade a day (already traded)"),
         ("no_fill", "passed, no fill (no tap / no 1m CISD / 1.5R at fill)"), ("traded", "traded")]
LABEL = dict(RULES)
SPANS = {"2026": ("2026-01-01", "2026-12-31"), "H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"),
         "2021-25": ("2021-01-01", "2025-12-31")}


def classify(P=None):
    """[(candidate row)] for every candidate of every session: day, t (5m CISD close), dir, rule, text."""
    from engine import lit, lit_brief
    from tools import lit_final as F
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = {**lit.DEFAULTS, **(P or lm["lit"])}
    M, C = F.market(P["ref"], P.get("extra_boxes") or [])
    T = F.run(P)
    traded = {(t["day"], int(t["i"]), int(t["dir"])) for t in T}
    day_tr = collections.defaultdict(list)
    for t in T:
        day_tr[t["day"]].append(int(t["entry_t"]))
    sess = set(F.SESS)
    rows = []
    for z in C:
        if z["day"] not in sess:
            continue
        d = int(z["dir"])
        t_cl = int(M.t[z["i"]]) + 300
        why = lit_brief.reject_reason(M, z, P)
        if why:
            rule, txt = why
        elif (z["day"], int(z["i"]), d) in traded:
            rule, txt = "traded", "traded"
        elif any(e <= t_cl + 30 * 60 for e in day_tr.get(z["day"], [])) and day_tr.get(z["day"]):
            rule, txt = "day", "a trade was already open or done today (1 trade a day)"
        else:
            rule, txt = "no_fill", "passed every rule; the limit was not tapped in 30 min, no 1m CISD came, or the 1.5R check failed at the fill"
        rows.append({"day": z["day"], "t": t_cl, "dir": d, "rule": rule, "text": txt,
                     "depth": round(float(z["depth_atr"]), 2), "disp": round(float(z["disp"]), 2)})
    rows.sort(key=lambda r: r["t"])
    return rows, P


def _week(day):
    y, w, _ = dt.date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def span_stats(rows, days):
    ds = set(days)
    R = [r for r in rows if r["day"] in ds]
    n = len(R)
    cnt = collections.Counter(r["rule"] for r in R)
    rej = n - cnt.get("traded", 0)
    rules = [{"rule": k, "label": lab, "n": cnt.get(k, 0), "pct": round(100.0 * cnt.get(k, 0) / rej, 1) if rej and k != "traded" else None,
              "of_setups": round(100.0 * cnt.get(k, 0) / n, 1) if n else None} for k, lab in RULES]
    wk = collections.defaultdict(collections.Counter)
    for r in R:
        wk[_week(r["day"])][r["rule"]] += 1
    weeks = [{"week": w, "setups": sum(c.values()), "traded": c.get("traded", 0), **{k: c.get(k, 0) for k, _ in RULES if k != "traded"}}
             for w, c in sorted(wk.items())]
    top = max((x for x in rules if x["rule"] != "traded"), key=lambda x: x["n"], default=None)
    return {"sessions": len(ds), "from": min(ds) if ds else None, "to": max(ds) if ds else None, "setups": n,
            "traded": cnt.get("traded", 0), "rejected": rej, "per_session": round(n / len(ds), 2) if ds else None,
            "top": top["rule"] if top and top["n"] else None, "rules": rules, "weeks": weeks[-60:]}


def build(last=20):
    from tools import lit_final as F
    rows, P = classify()
    sess = [d for d in F.SESS]
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "strategy": "LIT (live_model.json lit)",
           "source": "tools/lit_rejections.py: every 5m CISD candidate of the backtest data with engine/lit_brief.reject_reason "
                     "(the day brief's rule), traded = tools/lit_final.run on the live params (run lit_live)",
           "rules": [{"rule": k, "label": v} for k, v in RULES], "last_n": last, "spans": {}}
    out["spans"]["last"] = span_stats(rows, sess[-last:])
    for nm, (a, z) in SPANS.items():
        out["spans"][nm] = span_stats(rows, [d for d in sess if a <= d <= z])
    out["recent"] = [{**r, "label": LABEL.get(r["rule"], r["rule"])} for r in rows[-60:]][::-1]
    out["params"] = {k: P.get(k) for k in ("window", "depth", "disp", "idm_a", "min_stop", "max_stop", "min_rr", "monday")}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=20)
    a = ap.parse_args(argv)
    out = build(a.days)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    for nm in ("last", "H1", "H2", "2021-25"):
        s = out["spans"][nm]
        top = ", ".join(f"{r['label']} {r['n']}" for r in sorted(s["rules"], key=lambda r: -r["n"])[:4] if r["n"])
        print(f"{nm:8s} {s['sessions']:4d} sessions {s['setups']:5d} setups {s['traded']:4d} traded | {top}")
    print("->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
