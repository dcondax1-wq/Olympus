#!/usr/bin/env python3
"""Kalshi City "What we learned" data: research/kalshi/edge_tables.json (tools/kalshi_research.py) -> tools/web_public/kalshicity/learned.json.

  python tools/kalshicity_learned.py                 # rewrite learned.json from the research tables
  python tools/kalshicity_learned.py --tables X.json --out Y.json

READ ONLY and offline: it only reshapes a research file the repo already holds. The page (kalshicity.js) writes the plain words from these numbers, so a
rerun of tools/kalshi_research.py plus this script refreshes the sheet; nothing in the page is hard-coded except the structure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES = os.path.join(ROOT, "research", "kalshi", "edge_tables.json")
OUT = os.path.join(ROOT, "tools", "web_public", "kalshicity", "learned.json")
BUCKETS = ("60-80c", "80-90c", "90-95c", "95-97c", "97-99c", "95-99c (band; feed cannot split 98c+)", "<95c (all)", "all settled buys")
BUCKET_KEYS = ("label", "n", "wins", "win_rate", "wilson_lo", "wilson_hi", "avg_price", "breakeven_win_rate", "edge_pp", "p_one_sided", "staked", "pnl", "roi", "roi_ci_lo", "roi_ci_hi",
               "size_effect_pnl", "fees_est", "verdict", "low_n")


def pick(d, keys):
    return {k: d.get(k) for k in keys}


def build(t):
    """edge_tables dict -> the compact learned.json dict."""
    by = {b["label"]: b for b in t["buckets"]}
    drag = t["fees"]["drag"]
    rows = t["fees"]["rows"]
    sims = [s for s in t["risk"]["sims"]["late_favourite"] if str(s.get("scenario", "")).startswith("observed")]
    return {
        "v": 1, "about": "Reshaped from research/kalshi/edge_tables.json (tools/kalshi_research.py) by tools/kalshicity_learned.py. After fees. The feed gives totals, never combinations.",
        "source": {"tables": "research/kalshi/edge_tables.json", "writeup": "research/writeups/2026-11-04_kalshi_edges.md", "generated_utc": t.get("generated_utc"),
                   "feed_t": t["source"].get("feed_t"), "balance": t["source"].get("balance"), "total_pnl": t["source"].get("total_pnl"), "bets": (t["source"].get("stats") or {}).get("trades")},
        "headline": t["verdict"]["headline"], "positive": t["verdict"]["positive_pockets"], "negative": t["verdict"]["negative_pockets"],
        "fees": {"total": drag["fees_est_total"], "staked": drag["staked"], "pct_of_stake": drag["fee_pct_of_stake"], "pnl_net": drag["pnl_net"], "pnl_gross": drag["pnl_gross_est"],
                 "maker_total": drag.get("maker_fees_est_total"), "pct_of_win_min": min(r["fee_pct_of_win"] for r in rows), "pct_of_win_max": max(r["fee_pct_of_win"] for r in rows),
                 "rows": [pick(r, ("price", "fee_per_contract", "fee_pct_of_win", "breakeven_win_rate", "loss_to_win_ratio")) for r in rows]},
        "buckets": [pick(by[k], BUCKET_KEYS) for k in BUCKETS if k in by],
        "strategies": [pick(s, ("name", "mode", "n", "win_rate", "pnl", "verdict", "low_n")) for s in t["strategies"]],
        "categories": [pick(c, ("label", "n", "win_rate", "pnl", "roi", "verdict", "low_n")) for c in t["categories"]],
        "ruin": {"bankroll": t["risk"]["kelly"]["bankroll"], "floor": 6.0, "assumptions": t["risk"]["sims"].get("assumptions"), "horizon_days": sims[0]["horizon_days"] if sims else None, "bets_per_day": sims[0]["bets_per_day"] if sims else None,
                 "rows": [pick(s, ("policy", "p_ruin", "p_below_half", "median_end", "p5_end", "p95_end")) for s in sims]},
        "kelly": [pick(c, ("case", "price", "n", "win_rate", "kelly_point_estimate", "kelly_market_prior_posterior", "dollars_at_bankroll_posterior")) for c in t["risk"]["kelly"]["cases"]],
        "ideas": [pick(i, ("id", "title", "n_needed")) for i in t["ideas"]],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Kalshi City lessons from the research tables (offline, read only).")
    ap.add_argument("--tables", default=TABLES)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    with open(a.tables, encoding="utf-8") as fh:
        doc = build(json.load(fh))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    print(f"kalshicity_learned: {len(doc['buckets'])} bands, {len(doc['ruin']['rows'])} ruin rows, {len(doc['ideas'])} ideas -> {os.path.relpath(a.out, ROOT)} ({os.path.getsize(a.out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
