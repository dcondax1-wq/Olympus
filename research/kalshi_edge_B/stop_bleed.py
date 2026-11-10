#!/usr/bin/env python3
"""'Stop the bleeding': which bet KINDS of the live bot lose money after fees, with n and a 95% interval.

Source = the repo's own snapshot of the public feed (research/kalshi/edge_tables.json, built from kalshi.json of 2026-11-04,
1,836 settled buys, 41 days; the bot's P&L is net of Kalshi fees).  Read-only; no API call.

Per kind: ROI = P&L / $ staked.  95% interval: binary-outcome normal approximation around the observed win rate
(width = z*sqrt(w(1-w)/n) / avg_price), a Wilson interval on the win rate converted to ROI at the average entry price.
"A proven leak" = interval entirely below 0.  Kinds without a known stake / price are judged on P&L per trade only and
labelled 'price unknown'.
    python research/kalshi_edge_B/stop_bleed.py   -> stop_bleed.json
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import wilson, fee

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
T = json.load(open(os.path.join(ROOT, "research", "kalshi", "edge_tables.json")))


def roi_from_win(w, p):
    """ROI of buying at price p (incl. taker fee) when the win rate is w."""
    return (w - p - fee(p)) / (p + fee(p) * 0 )


out = {"source": "research/kalshi/edge_tables.json (feed 2026-11-04)", "kinds": []}
for group, rows in (("category", T["categories"]), ("strategy", T["strategies"])):
    for r in rows:
        n, w = r["n"], r["wins"]
        if group == "category":
            ci = [r.get("roi_ci_lo"), r.get("roi_ci_hi")]
            roi = r.get("roi")
            kind = r["label"]
            price = r.get("avg_price")
        else:
            kind = r["name"]
            price = r.get("sample_price")
            roi = None
            ci = [None, None]
        wl, wh = wilson(w, n)
        entry = {"group": group, "kind": kind, "n": n, "wins": w, "win_rate": round(w / n, 4), "win_wilson": [round(wl, 4), round(wh, 4)],
                 "pnl": r.get("pnl"), "roi": roi, "roi_ci": ci, "low_n": n < 30}
        if group == "strategy":
            entry["pnl"] = r["pnl"]
            entry["pnl_per_trade"] = r["pnl_per_trade"]
            if r.get("breakeven_win_rate"):
                be = r["breakeven_win_rate"]
                entry["breakeven_win"] = be
                entry["win_ci_vs_breakeven"] = "below" if wh < be else ("above" if wl > be else "straddles")
        if n < 30:
            entry["verdict"] = "too few to judge (n<30)"
        elif ci[1] is not None and ci[1] < 0:
            entry["verdict"] = "PROVEN LEAK: stop"
        elif group == "strategy" and entry.get("win_ci_vs_breakeven") == "below":
            entry["verdict"] = "PROVEN LEAK: stop"
        elif (roi is not None and roi < 0) or (group == "strategy" and r["pnl"] < 0):
            entry["verdict"] = "negative, not proven: pause / watch"
        else:
            entry["verdict"] = "not negative"
        out["kinds"].append(entry)

json.dump(out, open(os.path.join(HERE, "stop_bleed.json"), "w"), indent=1)
for e in out["kinds"]:
    print("%-10s %-30s n=%-5d win=%.3f pnl=%s roi=%s ci=%s  %s" % (e["group"], e["kind"], e["n"], e["win_rate"], e["pnl"], e["roi"], e["roi_ci"], e["verdict"]))
