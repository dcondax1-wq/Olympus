"""Lane A stress test (pre-registered: research/orderflow/DESIGN_lanea_proof.md). PAPER RESEARCH ONLY: changes no bot.

    python -X utf8 research/orderflow/lanea_proof/proof.py [--paths 2000]   -> research/orderflow/lanea_proof/results.json

Reads the pulled real tick summaries (data/pc_days/<day>/of/), replays lane A with engine/of_paper.replay_summary (the frozen
paper bot), re-simulates each signal under the pre-registered fill models, splits, bootstrap, halves diagnostics, overlap with
LIT / ATLAS, and the MFFU eval / funded engines (tools/money: stack_one_account, rapid_levers, uprisk, research/plans/rank).
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import datetime as dt
import io
import json
import os
import pickle
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money"), os.path.join(ROOT, "research", "plans")):
    if p not in sys.path:
        sys.path.insert(0, p)
OUT = os.path.join(HERE, "results.json")
TICK, PV, COMM, RR = 0.25, 2.0, 1.90, 2.0
FIRST, LAST = "2026-09-27", "2026-11-26"


# ------------------------------------------------------------------------------------------------ lane A signals
def load_days(src=None):
    from engine import ofsum
    import of_realday_verdict as V
    B = V._of_mod("of_battery")
    dirs = V.day_dirs(src)
    R = {d: ofsum.read(p) for d, p in dirs.items()}
    R = {d: x for d, x in R.items() if x and int(x["meta"].get("rows", 0)) >= B.MIN_ROWS}
    return R, B


def signals(R, B):
    from engine import of_paper as P
    days = sorted(R)
    rows = []
    for k, d in enumerate(days):
        prev = days[k - 1] if k and (dt.date.fromisoformat(d) - dt.date.fromisoformat(days[k - 1])).days <= 4 else None
        with contextlib.redirect_stdout(io.StringIO()):
            S = P.replay_summary(R[d], d, R[prev] if prev else None, prev, lit=[])
        rows += S["rows"]
    D = {d: B.Day(d, R[d]) for d in days}
    return days, rows, D


# ------------------------------------------------------------------------------------------------ the re-simulator
def sim(row, Dy, model="F1"):
    """One signal under a fill model -> dict(fill, exit, R, usd, why, fill_t, exit_t, w1, risk) or None (no fill / no risk)."""
    b = Dy.bars
    d, stop = row["d"], row["stop"]
    i0 = Dy.row_of_t.get(int(row["t_sig"]) + 300)
    if i0 is None:
        return None
    slip_stop = 2 if model == "FS" else 1
    if model in ("F1", "F2", "F3", "FS"):
        k = {"F1": 1, "F2": 2, "F3": 3, "FS": 1}[model]
        fill = float(b.open.iat[i0]) + k * TICK * d
        jf, fill_bar_counts = i0, True
    elif model == "FL":
        lv = row["level_px"]
        jf = None
        for j in range(i0, min(i0 + 3, len(b))):
            if b["mod"].iat[j] > 955:
                break
            if (d == -1 and b.high.iat[j] >= lv + TICK) or (d == 1 and b.low.iat[j] <= lv - TICK):
                jf = j
                break
        if jf is None:
            return {"miss": True}
        fill, fill_bar_counts = float(lv), False
    else:
        raise ValueError(model)
    risk = (fill - stop) * d
    if risk <= 0:
        return None
    tgt = fill + RR * risk * d
    w1, last = 0.0, None
    for j in range(jf, len(b)):
        if b["mod"].iat[j] > 955:
            break
        last = j
        h, l = float(b.high.iat[j]), float(b.low.iat[j])
        w1 = min(w1, (l - fill) if d == 1 else (fill - h))
        if (d == 1 and l <= stop) or (d == -1 and h >= stop):
            return _out(fill, stop - slip_stop * TICK * d, d, risk, "stop", b, jf, j, w1)
        if j == jf and not fill_bar_counts:
            continue                                     # limit fill bar: no target credit inside it (order unknown)
        if (d == 1 and h >= tgt) or (d == -1 and l <= tgt):
            return _out(fill, tgt, d, risk, "target", b, jf, j, w1)
    if last is None:
        return None
    return _out(fill, float(b.close.iat[last]) - TICK * d, d, risk, "flat 15:55", b, jf, last, w1)


def _out(fill, px, d, risk, why, b, jf, j, w1):
    pts = (px - fill) * d
    return {"fill": fill, "exit": px, "R": pts / risk, "pts": pts, "usd": pts * PV - COMM, "why": why, "risk": risk,
            "fill_t": int(b.t.iat[jf]), "exit_t": int(b.t.iat[j]) + 300,
            "w1": min(max(w1, -(risk + 2 * TICK)), pts)}      # the worst open loss can't pass the stop fill (the bar's low beyond it isn't held)


# ------------------------------------------------------------------------------------------------ stats
def st(R, usd, days_span, t_exit=None):
    R, usd = np.asarray(R, float), np.asarray(usd, float)
    n = len(R)
    if not n:
        return {"n": 0}
    wk = days_span / 7.0
    eq = np.cumsum(usd)
    dd = float(np.max(np.maximum.accumulate(np.r_[0.0, eq])[1:] - eq)) if n else 0.0
    eqR = np.cumsum(R)
    ddR = float(np.max(np.maximum.accumulate(np.r_[0.0, eqR])[1:] - eqR))
    pos, neg = usd[usd > 0].sum(), -usd[usd < 0].sum()
    return {"n": n, "per_week": round(n / wk, 2), "won": round(100.0 * float(np.mean(R > 0)), 1), "mean_R": round(float(R.mean()), 3),
            "sum_R": round(float(R.sum()), 2), "PF": round(float(pos / neg), 2) if neg > 0 else None,
            "net_1": round(float(usd.sum()), 2), "per_month_1": round(float(usd.sum()) / (days_span / 30.44), 2),
            "maxdd_1": round(dd, 2), "maxdd_R": round(ddR, 2)}


def boot(days, byday, n=10000, seed=11):
    rng = np.random.default_rng(seed)
    dd = [d for d in days]
    sums = np.array([sum(byday.get(d, [])) for d in dd])
    cnts = np.array([len(byday.get(d, [])) for d in dd])
    idx = rng.integers(0, len(dd), size=(n, len(dd)))
    s, c = sums[idx].sum(1), cnts[idx].sum(1)
    m = s[c > 0] / c[c > 0]
    return {"mean": round(float(m.mean()), 3), "ci90": [round(float(np.percentile(m, 5)), 3), round(float(np.percentile(m, 95)), 3)],
            "ci95": [round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3)],
            "p_le0": round(float(np.mean(m <= 0)), 4)}


def lvtype(nm):
    return "pd" if nm.startswith("pd") else "orb" if nm.startswith("or") else "glob"


def twin(Dy, t):
    i = Dy.row_of_t.get(int(t))
    m = int(Dy.bars["mod"].iat[i])
    return "09:45-10:30" if m < 630 else "10:30-12:00" if m < 720 else "12:00-15:00"


# ------------------------------------------------------------------------------------------------ LIT / ATLAS on these days
def lit_atlas(cache=None):
    """LIT (the frozen live model replay, tools/lit_losses.run2) + ATLAS MD (tools/second_mix.units) trades since 2026-09-01,
    as stack_one_account trade dicts. Cached (they take minutes)."""
    if cache and os.path.exists(cache):
        X = pickle.load(open(cache, "rb"))
    else:
        from tools import lit_losses as L
        M, C, B1, B5 = L.base()
        T = L.run2(M, C, {**L.P0}, None, B1=B1, B5=B5)
        try:
            from tools import second_mix as SM
            U = SM.units()["MD"]
        except Exception:  # noqa: BLE001
            U = []
        X = {"T": [t for t in T if t["day"] >= "2026-09-01"], "U": [u for u in U if u["day"] >= "2026-09-01"], "Mt_last": int(M.t[-1])}
        if cache:
            pickle.dump(X, open(cache, "wb"))
    lit = []
    for t in X["T"]:
        rp = float(t["risk_pts"])
        if rp <= 0:
            continue
        lit.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "strat": "LIT",
                    "risk": rp, "pts": float(t["r"]) * rp, "w1": -float(t["mae"]) * rp,
                    "tgt": abs(float(t["target_px"]) - float(t["entry_px"])), "ref": False, "tf": int(t.get("tf") or 1)})
    atl = [{"day": u["day"], "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "dir": int(u["dir"]), "strat": "ATLAS",
            "risk": float(u["risk"]), "pts": float(u["pts"]), "w1": float(u["w1"]), "tgt": u.get("tgt")} for u in X["U"]
           if float(u.get("risk") or 0) > 0]
    atlas_to = max([u["day"] for u in X["U"]], default=None)
    return lit, atl, atlas_to


# ------------------------------------------------------------------------------------------------ the eval / funded engines
def engines(days, by_day, n_paths, seed=5):
    """Day-block bootstrap (blocks of 5) of the real days -> MFFU Builder 50K / 25K, Rapid EOD 25K evals and eval+funded slots,
    on rank.py's machinery (live LIT sizing, ATLAS / lane A as stack_q added strategies)."""
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import rank as RK
    import rapid_levers as RL
    import stack_one_account as SOA
    RL.PRI.setdefault("LANEA", 6)
    with contextlib.redirect_stdout(io.StringIO()):
        RK.A4.apply_costs()
    rng = np.random.default_rng(seed)
    nd = len(days)

    def paths(length):
        out = []
        for _ in range(n_paths):
            seq = []
            while len(seq) < length:
                s = int(rng.integers(0, nd))
                seq += [(s + j) % nd for j in range(5)]
            out.append(seq[:length])
        return out

    PE, PF = paths(RK.H_EVAL), paths(RK.LEN)
    mixes = {"lane A alone": ("LANEA",), "LIT + ATLAS (today)": ("LIT", "ATLAS"), "LIT + ATLAS + lane A": ("LIT", "ATLAS", "LANEA")}
    plans = {"mffu_builder_50k": "MFFU Builder 50K", "mffu_builder_25k": "MFFU Builder 25K", "mffu_rapid_eod_25k": "MFFU Rapid EOD 25K"}
    res = {}
    for plan, label in plans.items():
        big = "50k" in plan
        res[label] = {}
        for mname, mix in mixes.items():
            sp = RK.spec(plan)
            z = RL.Z(ATLAS=500 if big else 250, LANEA=500 if big else 250)
            sp["z"] = z
            E = sp["E"]
            ec = RK.A4.ecfg({**E, "dll": min(E["dll"], 1000.0 if big else 500.0)})
            ec["two_week"]["acct"]["dll"] = min(E["dll"], 1000.0 if big else 500.0)
            ec["_dll"] = min(E["dll"], 1000.0 if big else 500.0)
            has_cons = E.get("cons", 1.0) < 1.0
            sp["ev"] = lambda ec=ec, E=E, z=z, hc=has_cons: RL.Ev(ec, E, z, "guard" if hc else "none")
            fcfg = RK.U.UP50 if big else RK.U.UP25
            ask = "cap" if sp["F"]["cap1"] < 1e8 else sp["F"]["pay_min"]
            sp["fund"] = lambda fcfg=fcfg, F=sp["F"], z=z, ask=ask: RK.Funded(fcfg, F, z, ask)
            news = plan.startswith("mffu_rapid")
            BY = []
            for d in days:
                ts = sorted([t for t in by_day.get(d, []) if t["strat"] in mix], key=lambda t: (t["entry_t"], RL.PRI[t["strat"]]))
                BY.append(SOA.news_rule(ts) if news and ts else ts)
            sp["BYe"] = sp["BYf"] = BY
            ev = eval_dd(sp, PE)
            slot = RK.slot_run(sp, PF)
            months = RK.LEN / 21.0
            res[label][mname] = {"eval": ev, "slot": {k: slot[k] for k in ("owner_6m", "fees_6m", "net_6m", "net_p10", "p_lost", "no_pay", "first_pay_med")},
                                 "net_per_month": round(slot["net_6m"] / months, 1), "price": sp["price"]}
    return res


def eval_dd(sp, paths):
    """rank.eval_run + the max drawdown from the peak balance inside the eval and the trades taken."""
    res = []
    for seq in paths:
        e = sp["ev"]()
        out, used, peak, mdd = "open", len(seq), 0.0, 0.0
        for k, si in enumerate(seq):
            r, _ = e.step(sp["BYe"][si])
            peak = max(peak, e.bal)
            mdd = max(mdd, peak - e.bal)
            if r:
                out, used = ("pass" if r == "pass" else "fail"), k + 1
                break
        res.append((out, used, mdd))
    n = len(res)
    pas = [u for o, u, _ in res if o == "pass"]
    return {"pass": round(100.0 * len(pas) / n, 1), "fail": round(100.0 * sum(1 for o, _, _ in res if o == "fail") / n, 1),
            "open": round(100.0 * sum(1 for o, _, _ in res if o == "open") / n, 1),
            "med_days": float(np.median(pas)) if pas else None, "maxdd_med": round(float(np.median([m for *_, m in res])), 0),
            "maxdd_p90": round(float(np.percentile([m for *_, m in res], 90)), 0)}


# ------------------------------------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", type=int, default=2000)
    ap.add_argument("--src", default=None)
    ap.add_argument("--cache", default=None, help="pickle of the LIT / ATLAS replays (made if missing)")
    ap.add_argument("--no-engines", action="store_true")
    ap.add_argument("--sim", action="store_true", help="a self-check on simulated days (of_sim planted world), written to --out")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    if a.sim:
        import of_realday_verdict as V
        B = V._of_mod("of_battery")
        R = V._of_mod("of_sim").world(45, "planted", seed=41, lvl=True)["R"]
    else:
        R, B = load_days(a.src)
    if not R:
        print("no real order-flow day here: python -X utf8 tools/data_pull.py --of --no-battery first")
        return 2
    days, rows, D = signals(R, B)
    span = (dt.date.fromisoformat(days[-1]) - dt.date.fromisoformat(days[0])).days + 1
    out = {"design": "research/orderflow/DESIGN_lanea_proof.md", "days": len(days), "first": days[0], "last": days[-1],
           "span_days": span, "costs": f"${COMM} rt per micro, stop fill 1 tick worse (FS: 2)"}
    cand = [r for r in rows if r.get("lane") == "A"]
    taken = [r for r in cand if r["taken"]]
    skipped = [r for r in cand if not r["taken"]]
    # check: the re-simulator at F1 reproduces the paper bot's R (its COMM is $1.40, R is cost-free)
    chk = [(r["R"], sim(r, D[r["day"]], "F1")) for r in cand if r.get("R") is not None]
    out["resim_check"] = {"n": len(chk), "same_R": sum(1 for p, s in chk if s and abs(p - s["R"]) < 0.01)}
    # fill models
    FM = {}
    sims = {}
    for m in ("F1", "F2", "F3", "FS", "FL"):
        sims[m] = {r["id"]: sim(r, D[r["day"]], m) for r in cand}
        tk = [sims[m][r["id"]] for r in taken if sims[m][r["id"]] and not sims[m][r["id"]].get("miss")]
        sk = [sims[m][r["id"]] for r in skipped if sims[m][r["id"]] and not sims[m][r["id"]].get("miss")]
        s_t, s_s = st([x["R"] for x in tk], [x["usd"] for x in tk], span), st([x["R"] for x in sk], [x["usd"] for x in sk], span)
        FM[m] = {"taken": s_t, "skipped": s_s, "gap_R": round(s_t.get("mean_R", 0) - s_s.get("mean_R", 0), 3) if s_t["n"] and s_s["n"] else None,
                 "missed": sum(1 for r in taken if (sims[m][r["id"]] or {}).get("miss"))}
    out["fill_models"] = FM
    T1 = [(r, sims["F1"][r["id"]]) for r in taken if sims["F1"][r["id"]]]
    S1 = [(r, sims["F1"][r["id"]]) for r in skipped if sims["F1"][r["id"]]]

    def grp(key):
        g = collections.defaultdict(list)
        for r, s in T1:
            g[key(r)].append(s)
        gs = collections.defaultdict(list)
        for r, s in S1:
            gs[key(r)].append(s)
        return {k: {"taken": st([x["R"] for x in v], [x["usd"] for x in v], span),
                    "skipped": st([x["R"] for x in gs.get(k, [])], [x["usd"] for x in gs.get(k, [])], span)} for k, v in sorted(g.items())}

    sh = sorted(abs(r["dz"]) / r["vz"] for r, _ in T1)
    q1, q2 = (np.percentile(sh, [33.33, 66.67]) if sh else (0, 0))
    out["splits"] = {
        "level": grp(lambda r: lvtype(r["level"])),
        "level_name": grp(lambda r: r["level"]),
        "time": grp(lambda r: twin(D[r["day"]], r["t_sig"])),
        "side": grp(lambda r: "long" if r["d"] == 1 else "short"),
    }
    g = collections.defaultdict(list)
    for r, s in T1:
        x = abs(r["dz"]) / r["vz"]
        g["weak (|dz|/vz <= %.2f)" % q1 if x <= q1 else "mid" if x <= q2 else "strong (> %.2f)" % q2].append(s)
    out["splits"]["absorption_strength"] = {k: st([x["R"] for x in v], [x["usd"] for x in v], span) for k, v in g.items()}
    wk = collections.defaultdict(list)
    for r, s in T1:
        y, w, _ = dt.date.fromisoformat(r["day"]).isocalendar()
        wk[f"{y}-W{w:02d}"].append(s["R"])
    out["weeks"] = {k: {"n": len(v), "sum_R": round(sum(v), 2), "mean_R": round(float(np.mean(v)), 3)} for k, v in sorted(wk.items())}
    out["weeks_pos"] = f"{sum(1 for v in wk.values() if sum(v) > 0)} of {len(wk)}"
    byday = collections.defaultdict(list)
    for r, s in T1:
        byday[r["day"]].append(s["R"])
    out["bootstrap_taken_F1"] = boot(days, byday)
    byday2 = collections.defaultdict(list)
    for r, _ in T1:
        s2 = sims["F2"][r["id"]]
        if s2:
            byday2[r["day"]].append(s2["R"])
    out["bootstrap_taken_F2"] = boot(days, byday2)
    # halves
    h = len(days) // 2
    halves = {"older": days[:h], "newer": days[h:]}
    HD = {}
    for nm, dd in halves.items():
        ds = set(dd)
        c = [r for r in cand if r["day"] in ds]
        t = [(r, s) for r, s in T1 if r["day"] in ds]
        sk = [(r, s) for r, s in S1 if r["day"] in ds]
        rng_, trend = [], 0
        for d in dd:
            rb = D[d].bars[(D[d].bars["mod"] >= 570) & (D[d].bars["mod"] < 960)]
            if len(rb):
                hi, lo = float(rb.high.max()), float(rb.low.min())
                rng_.append(hi - lo)
                trend += abs(float(rb.close.iat[-1]) - float(rb.open.iat[0])) >= 0.6 * (hi - lo)
        HD[nm] = {"days": len(dd), "from": dd[0], "to": dd[-1], "candidates_per_day": round(len(c) / len(dd), 2),
                  "taken_share": round(len(t) / len(c), 2) if c else None,
                  "taken": st([s["R"] for _, s in t], [s["usd"] for _, s in t], (dt.date.fromisoformat(dd[-1]) - dt.date.fromisoformat(dd[0])).days + 1),
                  "skipped_mean_R": round(float(np.mean([s["R"] for _, s in sk])), 3) if sk else None,
                  "risk_ticks_mean": round(float(np.mean([s["risk"] / TICK for _, s in t])), 1) if t else None,
                  "rth_range_pts_mean": round(float(np.mean(rng_)), 1) if rng_ else None,
                  "trend_day_share": round(trend / len(dd), 2),
                  "exits": dict(collections.Counter(s["why"] for _, s in t)),
                  "levels": dict(collections.Counter(lvtype(r["level"]) for r, _ in t)),
                  "sides": dict(collections.Counter("long" if r["d"] == 1 else "short" for r, _ in t))}
    out["halves"] = HD
    # overlap
    lit, atl, atlas_to = lit_atlas(a.cache)
    other = [t for t in lit + atl if FIRST <= t["day"] <= LAST]
    out["lit_atlas"] = {"lit_trades": sum(1 for t in other if t["strat"] == "LIT"), "atlas_trades": sum(1 for t in other if t["strat"] == "ATLAS"),
                        "atlas_cache_to": atlas_to}
    ov, nov = [], []
    for r, s in T1:
        a0, a1 = s["fill_t"], s["exit_t"]
        hit = any(t["day"] == r["day"] and (a0 <= t["entry_t"] < a1 or t["entry_t"] <= a0 < t["exit_t"]) for t in other)
        (ov if hit else nov).append(s["R"])
    out["overlap"] = {"overlapping": len(ov), "overlap_mean_R": round(float(np.mean(ov)), 3) if ov else None,
                      "not_overlapping": len(nov), "free_mean_R": round(float(np.mean(nov)), 3) if nov else None}
    # engines
    if not a.no_engines:
        by_day = collections.defaultdict(list)
        for r, s in T1:
            by_day[r["day"]].append({"day": r["day"], "entry_t": s["fill_t"], "exit_t": s["exit_t"], "dir": r["d"], "strat": "LANEA",
                                     "risk": s["risk"], "pts": s["pts"], "w1": s["w1"], "tgt": RR * s["risk"]})
        for t in other:
            by_day[t["day"]].append(t)
        out["engines"] = engines(days, by_day, a.paths)
        out["engines_note"] = (f"{a.paths} day-block bootstrap paths of the {len(days)} real days only; LIT = frozen model replay, "
                               f"ATLAS MD from tools/second_mix (cache to {atlas_to}); lane A at stack_q $250 (25K) / $500 (50K).")
    # pre-registered bars
    f2 = FM["F2"]["taken"]
    bars = {"1 F2 taken mean R > 0": f2.get("mean_R", -1) > 0,
            "2 F1 bootstrap 90% CI low > 0": out["bootstrap_taken_F1"]["ci90"][0] > 0,
            "3 both halves taken mean R > 0": all((HD[k]["taken"].get("mean_R") or -1) > 0 for k in HD)}
    if "engines" in out:
        bars["4 adding lane A costs <= 2 pts of eval pass"] = all(
            v["LIT + ATLAS + lane A"]["eval"]["pass"] >= v["LIT + ATLAS (today)"]["eval"]["pass"] - 2.0 for v in out["engines"].values())
    out["bars"] = bars
    out["forward_worthy"] = all(bars.values())
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print(json.dumps({k: out[k] for k in ("days", "resim_check", "bars", "forward_worthy")}, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
