#!/usr/bin/env python3
"""Collect the three result files into results.json (one summary), edge_rules_C.json and a markdown table (printed).
    python research/kalshi_edge_C/report.py
"""
import json, os, time
HERE = os.path.dirname(os.path.abspath(__file__))


def ld(fn):
    p = os.path.join(HERE, fn)
    return json.load(open(p)) if os.path.exists(p) else {}


def pct(x):
    return "n/a" if x is None else f"{x*100:+.1f}%"


def ci(c):
    return "n/a" if not c else f"{c[0]*100:+.1f}% to {c[1]*100:+.1f}%"


def fz(d):
    """frozen() dict -> (n, edge, ci)"""
    return d.get("n", 0), d.get("edge"), d.get("ci95")


def best_train(cells):
    c = [x for x in cells if "train_t" in x]
    return max(c, key=lambda x: x["train_t"]) if c else None


def find(rows, name):
    return next((r for r in rows if r["cell"] == name), None)


def main():
    W, I, O = ld("results_weather.json"), ld("results_index.json"), ld("results_other.json")
    rows = []   # candidate, n train, n test, test edge, ci, replication, verdict
    cells_total = 0
    survivors = []
    wm = W.get("families", {}).get("main", {})
    if wm:
        cells_total += wm["cells_defined"]
        h = W["headline_rule_mos_5c"]
        nt, et, ct_ = fz(h["main"]["train"]); n2, e2, c2 = fz(h["main"]["test"])
        rep = []
        for k, nm in (("rep", "13 other cities"), ("low", "daily lows")):
            if k in h:
                n3, e3, c3 = fz(h[k]["test"])
                rep.append(f"{nm}: {pct(e3)} (n {n3}, {ci(c3)})")
        rows.append(("Weather: buy when the NWS forecast model says the price is 5c+ too cheap (7 big cities)", nt, n2, e2, c2, "; ".join(rep),
                     "No edge" if not (e2 and e2 > 0 and c2 and c2[0] > 0) else "CHECK", f"train {pct(et)}"))
        b = best_train(wm["cells"])
        if b:
            rr = []
            for k, nm in (("rep", "13 other cities"), ("low", "daily lows")):
                f = find(W["families"].get(k, {}).get("frozen_cells", []), b["cell"])
                if f and f["test_days_only"].get("edge") is not None:
                    rr.append(f"{nm}: {pct(f['test_days_only']['edge'])} (n {f['test_days_only']['n']})")
            rows.append((f"Weather: best cell on training data ({b['cell']})", b["train_n"], b.get("test_n", 0), b.get("test_edge"), b.get("test_ci95"),
                         "; ".join(rr) or "n/a", "Carried" if b.get("carried") else f"Below the multiple-testing bar (t {b['train_t']} vs {wm['null_max_t_p95']} needed): noise", f"train {pct(b['train_edge'])}"))
        n2, e2, c2 = fz(h["main"]["all_buys_control_test"])
        rows.append(("Weather: buy everything (control)", "", n2, e2, c2, "", "Taker cost", ""))
        survivors += [("weather", s) for s in wm.get("survive", [])]
    sp = I.get("families", {}).get("spx", {})
    nd = I.get("families", {}).get("ndx", {})
    if sp:
        cells_total += sp["cells_defined"]
        h = sp["headline_rule_vol_6c"]
        nt, et, _ = fz(h["train"]); n2, e2, c2 = fz(h["test"])
        rep = ""
        if nd:
            n3, e3, c3 = fz(nd["headline_rule_vol_6c"]["test"]); n4, e4, c4 = fz(nd["headline_rule_vol_6c"]["train"])
            rep = f"Nasdaq-100: train days {pct(e4)} (n {n4}), test days {pct(e3)} (n {n3}, {ci(c3)})"
        rows.append(("S&P 500 daily close range: buy when the realised-vol model says 6c+ too cheap", nt, n2, e2, c2, rep,
                     "No edge" if not (e2 and e2 > 0 and c2 and c2[0] > 0) else "CHECK", f"train {pct(et)}"))
        b = best_train(sp["cells"])
        if b:
            f = find(nd.get("frozen_cells", []), b["cell"]) if nd else None
            rr = f"Nasdaq-100 test days: {pct(f['test_days_only'].get('edge'))} (n {f['test_days_only'].get('n')})" if f else "n/a"
            rows.append((f"S&P 500: best cell on training data ({b['cell']})", b["train_n"], b.get("test_n", 0), b.get("test_edge"), b.get("test_ci95"), rr,
                         "Carried" if b.get("carried") else f"Below the bar (t {b['train_t']} vs {sp['null_max_t_p95']}): noise", f"train {pct(b['train_edge'])}"))
        n2, e2, c2 = fz(h["all_buys_control_test"])
        rows.append(("S&P 500 daily: buy everything (control)", "", n2, e2, c2, "", "Taker cost", ""))
        survivors += [("index", s) for s in sp.get("survive", [])]
    of = O.get("family", {})
    if of:
        cells_total += of["cells_defined"]
        b = best_train(of["cells"])
        if b:
            rows.append((f"Gas / FX / Rotten Tomatoes: best cell on training data ({b['cell']})", b["train_n"], b.get("test_n", 0), b.get("test_edge"), b.get("test_ci95"), "n/a",
                         "Carried" if b.get("carried") else f"Below the bar (t {b['train_t']} vs {of['null_max_t_p95']}): noise", f"train {pct(b['train_edge'])}"))
        g = [c for c in of["cells"] if c["cell"].startswith("gas momentum") and "train_t" in c]
        if g:
            b = max(g, key=lambda x: x["train_t"])
            rows.append((f"US gas price: best momentum-model cell ({b['cell']})", b["train_n"], b.get("test_n", 0), b.get("test_edge"), b.get("test_ci95"), "n/a", "No edge (negative in training)" if b["train_edge"] <= 0 else "Below the bar", f"train {pct(b['train_edge'])}"))
        survivors += [("other", s) for s in of.get("survive", [])]
    carried = len(wm.get("carried", [])) + len(sp.get("carried", [])) + len(of.get("carried", []))
    print("| Candidate | n train | n test | Edge per $1 after fees (test) | 95% range (test) | Replication (frozen, unseen) | Verdict |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]} | {pct(r[3])}{' (' + r[7] + ')' if r[7] else ''} | {ci(r[4])} | {r[5]} | {r[6]} |")
    print(f"\ncells looked at: {cells_total}, carried past the multiple-testing bar: {carried}, survived the held-out block: {len(survivors)}")
    status = "candidate_found" if survivors else "no_edge_found"
    summary = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "status": status, "cells_looked_at": cells_total, "cells_carried": carried,
               "survivors": survivors, "table": [dict(zip(("candidate", "n_train", "n_test", "test_edge_per_usd", "test_ci95", "replication", "verdict", "note"), r)) for r in rows],
               "weather": {k: W.get(k) for k in ("quoted_days", "first_day", "last_day", "test_from", "forecast_quality")} | {"brier_main": wm.get("brier"), "null_max_t_p95": wm.get("null_max_t_p95"), "cells_eligible": wm.get("cells_eligible")},
               "index": {k: sp.get(k) for k in ("days", "first_day", "last_day", "test_from", "days_with_futures_model", "vol_scale", "brier", "null_max_t_p95", "cells_eligible")},
               "other": {"series": O.get("series"), "econ_descriptive": O.get("econ_descriptive"), "null_max_t_p95": of.get("null_max_t_p95"), "cells_eligible": of.get("cells_eligible"), "test_from": of.get("test_from")}}
    json.dump(summary, open(os.path.join(HERE, "results.json"), "w"), indent=1)
    rules = {"v": 1, "team": "C (weather, economics, daily index, other recurring series; outside signals)", "asof": time.strftime("%Y-%m-%d", time.gmtime()),
             "status": status, "mode": "paper",
             "note": ("Nothing survived the multiple-testing bar plus the held-out block, so there are NO rules to follow. Sibyl must not read this as a pick."
                      if not survivors else "Candidate(s) below survived the held-out block. PAPER forward test only; never routed to any bot."),
             "rules": [{"family": f, "rule": s} for f, s in survivors],
             "cells_looked_at": cells_total,
             "forward_paper_test": {"start": time.strftime("%Y-%m-%d", time.gmtime()), "stake_usd_per_bet": 1.0, "max_open": 5,
                                    "entry": "taker buy at the ask (no: 1 - yes bid), only when ask - bid <= 4c, one bet per market",
                                    "fee": "0.07*p*(1-p) per contract", "min_n_before_any_claim": 1000,
                                    "kill_rule": "stop a rule when the cluster-bootstrap 95% upper bound of its edge per $ is below 0 after n >= 300, or after 60 days without n >= 300",
                                    "orders": "NONE: paper ledger only, never routed to the live bot",
                                    "active_rules": len(survivors)}}
    json.dump(rules, open(os.path.join(HERE, "edge_rules_C.json"), "w"), indent=1)
    print("status", status, "-> results.json, edge_rules_C.json")


if __name__ == "__main__":
    main()
