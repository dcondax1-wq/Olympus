"""LIT funnel 2026-01..2026-11-26: how far every candidate got and which rule killed it (research only).
Run: python research/lit/drought-2026-11-27/funnel.py  -> funnel.json"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c
lit, lf = c.lit, c.lf

PER = {"H1": ("2026-01-01", "2026-06-30"), "JulOct14": ("2026-07-01", "2026-10-14"), "Drought": ("2026-10-15", "2026-11-26"),
       "Dry9": ("2026-11-17", "2026-11-26"), "2021-25": ("2021-01-01", "2025-12-31")}
STAGES = ["window", "depth", "idm", "disp", "monday", "stop_range", "target", "fill"]


def stage_flags(M, z, P, B1, B5):
    """first failed stage of candidate z (or 'ok') + the set of static rules it fails."""
    f = {}
    f["window"] = any(a <= z["mod"] < b for a, b in P["window"])
    f["depth"] = z["depth_atr"] >= P["depth"]
    dm, age, cnt = P["idm_a"]
    f["idm"] = sum(1 for dd, aa in z["idm_a"] if dd <= dm and aa <= age) >= cnt
    f["disp"] = z["disp"] >= P["disp"]
    f["monday"] = not (P.get("monday") and lit.monday_block(M, z))
    ep = min(float(z["ref_d"]), z["trig_c"]); stop = z["ext_d"] - P["stop_buf"]; risk = ep - stop
    f["stop_range"] = P["min_stop"] <= risk <= P["max_stop"]
    sh = z["entry_d"] - ep
    TT = {cl: [x + sh for x in v] for cl, v in lit.targets_x(M, z, P).items()}
    best = None
    for cl in P["classes"]:
        for dist in TT.get(cl, []):
            if dist >= P["min_rr"] * risk:
                best = dist if best is None else min(best, dist); break
    f["target"] = best is not None
    fails = [s for s in STAGES[:-1] if not f[s]]
    if fails:
        return fails[0], fails, None
    tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
    use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
    t = lit.simulate_x(M, B1 if use1 else B5, z, ep, ("lvl", ep + tp, False) if P.get("cisd1m") else ("pts", tp), stop, P)
    if t is None:
        return "fill", ["fill"], None
    return "ok", [], t


def sweep_counts(M, P):
    """per day: number of liquidity levels first-breached inside the entry window (both sides) = raw sweeps."""
    out = {}
    w0, w1 = P["window"][0]
    for k, (date, s, e) in enumerate(M.days):
        x = M.ctx[k]
        if "pdh" not in x or e - s < 50:
            continue
        n = 0
        for side, px, ki, nm, cls in M.levels(k):
            arr = M.l if side == "low" else -M.h
            lev = px if side == "low" else -px
            st = max(ki, s - 600)
            j = lit._first_breach(arr, st, e, lev)
            if j < e and j >= s and w0 <= M.mod[j] < w1:
                n += 1
        out[str(date)] = n
    return out


def main():
    P = {**lit.DEFAULTS, **c.live_P()}
    S = c.sessions()
    M, C = lf.market(P["ref"], P["extra_boxes"])
    B1 = lf.bars(M, "1m"); B5 = lf.bars(M, "5m")
    trades = lf.run(P, sessions=S)
    tday = collections.Counter(t["day"] for t in trades)
    sset = set(S)
    rows = []
    for z in C:
        if z["day"] not in sset or z["day"] < "2021-01-01":
            continue
        first, fails, t = stage_flags(M, z, P, B1, B5)
        rows.append({"day": z["day"], "dir": z["dir"], "first": first, "fails": fails, "disp": z["disp"], "depth": z["depth_atr"],
                     "atr": z["atr"], "atr_ext": z["atr_ext"], "n_idm": len(z["idm_a"]), "mod": z["mod"]})
    sw = sweep_counts(M, P)
    # ATR in points at 10:00 ET per day, VIX open
    vix = {}
    for k, (date, s, e) in enumerate(M.days):
        x = M.ctx[k]
        vix[str(date)] = x.get("vix_move")
    res = {}
    for nm, (a, b) in PER.items():
        ss = [d for d in S if a <= d <= b]; wk = len(ss) / 5
        R = [r for r in rows if a <= r["day"] <= b]
        first = collections.Counter(r["first"] for r in R)
        alive = len(R); surv = {}
        for st in STAGES:
            alive -= first[st]; surv[st] = alive
        sole = collections.Counter(r["fails"][0] for r in R if len(r["fails"]) == 1)
        anyf = collections.Counter(f for r in R for f in r["fails"])
        T = [t for t in trades if a <= t["day"] <= b]
        pnl = np.array([t["pnl"] for t in T] or [0.0])
        res[nm] = {
            "sessions": len(ss), "weeks": round(wk, 1),
            "sweeps_per_wk": round(sum(sw.get(d, 0) for d in ss) / wk, 1),
            "cands_per_wk": round(len(R) / wk, 1),
            "survive_per_wk": {st: round(v / wk, 2) for st, v in surv.items()},
            "killed_first_pct": {st: round(100 * first[st] / max(len(R), 1), 1) for st in STAGES},
            "fail_rate_pct": {st: round(100 * anyf[st] / max(len(R), 1), 1) for st in STAGES[:-1]},
            "sole_killer_per_wk": {st: round(sole[st] / wk, 2) for st in STAGES},
            "trades": len(T), "tpw": round(len(T) / wk, 2), "net": round(float(pnl.sum())),
            "wins": sum(t["pnl"] > 0 for t in T),
            "median_disp": round(float(np.median([r["disp"] for r in R])), 3) if R else None,
            "median_depth": round(float(np.median([r["depth"] for r in R])), 3) if R else None,
            "median_atr_pts": round(float(np.median([r["atr"] for r in R])), 1) if R else None,
            "median_vix_move": round(float(np.median([vix[d] for d in ss if vix.get(d)])), 1) if ss else None,
        }
    # chance: rolling 30-session windows of trade counts, and dry spells
    tl = [tday.get(d, 0) for d in S]
    i0 = next(i for i, d in enumerate(S) if d >= "2021-01-01")
    win = [sum(tl[i:i + 30]) for i in range(i0, len(S) - 30 + 1)]
    win_hist = [sum(tl[i:i + 30]) for i in range(i0, next(i for i, d in enumerate(S) if d >= "2026-01-01") - 30 + 1)]
    dry, cur, start = [], 0, None
    for d, n in zip(S, tl):
        if n == 0:
            cur += 1; start = start or d
        else:
            if cur: dry.append((cur, start))
            cur, start = 0, None
    if cur: dry.append((cur, start))
    dry.sort(reverse=True)
    dro = [d for d in S if "2026-10-15" <= d <= "2026-11-26"]
    nd = sum(tday.get(d, 0) for d in dro)
    res["chance"] = {
        "drought_sessions": len(dro), "drought_trades": nd,
        "hist_30sess_windows": len(win_hist), "hist_windows_le_7": sum(w <= 7 for w in win_hist),
        "pct_hist_windows_le_7": round(100 * sum(w <= 7 for w in win_hist) / len(win_hist), 1),
        "hist_30sess_median": float(np.median(win_hist)), "hist_30sess_p5": float(np.percentile(win_hist, 5)),
        "longest_dry_spells": [{"sessions": n, "from": s} for n, s in dry[:8]],
        "dry_spells_ge_8_before_2026": sum(1 for n, s in dry if n >= 8 and s < "2026-01-01"),
        "current_dry_sessions": cur,
    }
    # weekly series for the chart / sanity
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "funnel.json"), "w"), indent=1)
    json.dump(rows, open(os.path.join(os.environ.get("SCR", "/tmp"), "lit_drought_rows.json"), "w"))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
