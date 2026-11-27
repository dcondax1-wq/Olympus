"""night-of-lane 2026-11-27: what the order-flow LANE's guards do to lane A's taken trades on the REAL pulled days.

Research only (reads data/pc_days/<day>/of/, writes nothing unless --json). For every real day: engine.of_paper.replay_summary
(the paper bot on the 5m summary: decisions at each bar close, fills at the next bar's open + 1 tick = v1 paper), then each TAKEN
row through the lane's own entry_guards (calendar / half-day cut, Tier-1 news +-2 min from data/news, the sizing at the lane's $
risk, firms.check with the MFFU 50K eval rules on the lane's running book). $ = paper R x the lane's micros x risk, $1.90 a micro.
NOT an E5 fill study (that is research/writeups/ofexec-2026-11-27.md on night-of-exec): this says how many trades the lane would
send and what the guards cost.

    python -X utf8 tools/of_lane_realcheck.py [--risk 200] [--json out.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))


class _FakeAd:
    outgoing = None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--risk", type=float, default=200.0)
    ap.add_argument("--max-micros", type=int, default=10)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    import of_realday_verdict as V
    from engine import of_lane as L, of_paper as P, ofsum
    dirs = V.day_dirs()
    R = {d: ofsum.read(p) for d, p in dirs.items()}
    R = {d: x for d, x in R.items() if x and int(x["meta"].get("rows", 0)) >= 2000}
    days = sorted(R)
    cfg = {**L.DEFAULT_CFG, "on": True, "risk_usd": a.risk, "max_micros": a.max_micros}
    S = L.new_state()
    td = tempfile.mkdtemp(prefix="oflane_rc_")
    ad = _FakeAd()
    ad.outgoing = td
    rows_out, why_n = [], {}
    from engine import news
    try:
        evs = news.historical_events(("high",))
    except Exception:  # noqa: BLE001
        evs = []
    for k, d in enumerate(days):
        prev = days[k - 1] if k and (dt.date.fromisoformat(d) - dt.date.fromisoformat(days[k - 1])).days <= 4 else None
        Sd = P.replay_summary(R[d], d, R[prev] if prev else None, prev)
        for r in Sd["rows"]:
            if not r.get("taken") or r.get("R") is None or r.get("fill") is None:
                continue
            now = int(r["t_sig"]) + 305
            S["day"] = d
            why, q, _ = L.entry_guards(S, cfg, ad, r, now, float(r["fill"]), False, evs)
            risk_pts = abs(float(r["fill"]) - float(r["stop"]))
            rec = {"day": d, "id": r["id"], "R": r["R"], "q": q, "why": "; ".join(why) or None}
            if why:
                for w in why:
                    key = w.split(":")[0][:50]
                    why_n[key] = why_n.get(key, 0) + 1
            else:
                pnl = round(r["R"] * risk_pts * 2.0 * q - L.COMM * q, 2)
                rec["usd"] = pnl
                S["closes"].append({"day": d, "t": now + 600, "pnl": pnl, "id": r["id"]})
            rows_out.append(rec)
    sent = [r for r in rows_out if r.get("usd") is not None]
    eq, pk, dd = 0.0, 0.0, 0.0
    for r in sent:
        eq += r["usd"]; pk = max(pk, eq); dd = min(dd, eq - pk)
    weeks = max(1.0, (dt.date.fromisoformat(days[-1]) - dt.date.fromisoformat(days[0])).days / 7.0) if days else 1.0
    out = {"days": len(days), "first": days[0] if days else None, "last": days[-1] if days else None, "taken": len(rows_out),
           "sent": len(sent), "refused": why_n, "usd": round(sum(r["usd"] for r in sent), 2),
           "mean_R_sent": round(sum(r["R"] for r in sent) / len(sent), 3) if sent else None,
           "trades_week": round(len(sent) / weeks, 2), "usd_month": round(sum(r["usd"] for r in sent) / weeks * 4.33, 2),
           "max_dd": round(dd, 2), "risk_usd": a.risk, "fills": "v1 paper (next bar open + 1 tick); E5 numbers: night-of-exec"}
    print(json.dumps(out, indent=1))
    if a.json:
        json.dump({**out, "rows": rows_out}, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
