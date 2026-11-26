"""LIT robustness & fragility audit (research/fragility/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/fragility/fragility.py   -> research/fragility/results.json
"""
from __future__ import annotations

import copy
import datetime as dt
import glob
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "moretrades"))
os.chdir(ROOT)
import moretrades as MT  # noqa: E402
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402

LIVE = MT.LIVE
SP = {"2026 H1": ("2026-01-01", "2026-06-30"), "2026 Jul-Oct": ("2026-07-01", "2026-10-16"), "2021-25": ("2021-11-01", "2025-12-31"),
      "fresh Oct19-Nov20": ("2026-10-17", "2026-11-20")}


def knobs():
    L = LIVE
    K = {}
    for f in (-0.2, -0.1, 0.1, 0.2):
        s = f"{f:+.0%}"
        K.setdefault("sweep depth 0.5", []).append((s, {"depth": round(0.5 * (1 + f), 3)}))
        K.setdefault("displacement 0.8", []).append((s, {"disp": round(0.8 * (1 + f), 3)}))
        K.setdefault("inducement distance 1.0", []).append((s, {"idm_a": [round(1.0 * (1 + f), 3), 36, 1]}))
        K.setdefault("inducement age 36", []).append((s, {"idm_a": [1.0, int(round(36 * (1 + f))), 1]}))
        K.setdefault("1m CISD window 22", []).append((s, {"cisd1m": int(round(22 * (1 + f)))}))
        K.setdefault("limit expiry 6 bars", []).append((s, {"wait": max(1, int(round(6 * (1 + f) + (0.01 if f > 0 else -0.01))))}))
        K.setdefault("VIX band x1.0", []).append((s, {"vix_k": round(1.0 * (1 + f), 3)}))
        K.setdefault("min target 1.5R", []).append((s, {"min_rr": round(1.5 * (1 + f), 3)}))
        K.setdefault("bank 8R", []).append((s, {"max_rr": round(8.0 * (1 + f), 2)}))
        K.setdefault("min stop 8", []).append((s, {"min_stop": round(8.0 * (1 + f), 2)}))
        K.setdefault("max stop 80", []).append((s, {"max_stop": round(80.0 * (1 + f), 1)}))
        K.setdefault("breakeven 1R", []).append((s, {"be_r": round(1.0 * (1 + f), 3)}))
        K.setdefault("15-min check at 15", []).append((s, {"t_check": {**L["t_check"], "at": int(round(15 * (1 + f)))}}))
    K["stop buffer 1 tick"] = [("0 ticks", {"stop_buf": 0.0}), ("2 ticks", {"stop_buf": 0.5}), ("3 ticks", {"stop_buf": 0.75})]
    K["window start 02:00"] = [(f"{d:+d} min", {"window": [[120 + d, 930]]}) for d in (-24, -12, 12, 24)]
    K["window end 15:30"] = [(f"{d:+d} min", {"window": [[120, 930 + d]]}) for d in (-24, -12, 12, 24)]
    return K


def sessions():
    M, _ = F.market(LIVE["ref"], LIVE.get("extra_boxes") or [])
    return M, sorted(set(F.SESS) | {d for d, _, _ in M.days if d > F.SESS[-1] and dt.date.fromisoformat(d).weekday() < 5})


def run(x, S):
    P = {**lit.DEFAULTS, **LIVE, **x}
    Mx, Cx = F.market(P["ref"], P["extra_boxes"])
    return [t for t in lit.run_x(Mx, Cx, P, S, B1=F.bars(Mx, "1m") if P["tf"] == "1m" else None, B5=F.bars(Mx, "5m")) if t.get("qty")]


def money(T, S):
    out = {}
    for k, (a, z) in SP.items():
        x = MT.span_stats(T, S, a, z, with_evals=False)
        out[k] = {"tpw": x["tpw"], "pf": x["pf"], "net": x["net"], "per_month": x["per_month"], "max_dd": x["max_dd"]}
    return out


def evalpath(T, extra_ticks=0):
    U = AC.units([t for t in T if t["day"] <= "2026-10-16"])
    if extra_ticks:
        c = 2 * extra_ticks * 0.25
        U = [{**u, "pts": u["pts"] - c, "legs": [(w, p - c) for w, p in u["legs"]]} for u in U]
    E = BI.short(BI.score(U))
    return {s: {"p10": E[s]["p10"], "f10": E[s]["f10"], "pass_med": E[s]["pass_med"], "net": E[s]["net"]} for s in E}


# ------------------------------------------------------------------------------------------------ Monte Carlo
def mc(pool, n=20000, seed=7, max_trades=80):
    rng = np.random.default_rng(seed)
    r = np.array([t["r"] for t in pool], float)
    tr = np.array([max(1.0, abs(t["target_px"] - t["entry_px"]) / t["risk_pts"]) for t in pool], float)
    res = {"PASS": 0, "FAIL": 0, "OPEN": 0}
    ntr, dds, streaks, st7 = [], [], [], 0
    for _ in range(n):
        bal = peak = 0.0; floor = -2000.0; cur = mx = 0; dd = 0.0; out = "OPEN"; seen7 = False
        for k in range(max_trades):
            i = rng.integers(len(r))
            room = bal - floor
            need = 3000.0 - bal
            risk = min(0.4 * room, need / tr[i] * 1.0, 40 * 2.0 * 80)
            risk = max(risk, 30.0)
            p = r[i] * risk
            bal += p
            peak = max(peak, bal)
            dd = min(dd, bal - peak)
            cur = cur + 1 if r[i] < 0 else 0
            mx = max(mx, cur)
            if cur >= 7:
                seen7 = True
            if bal <= floor:
                out = "FAIL"; break
            floor = min(max(floor, peak - 2000.0), 100.0)
            if bal >= 3000.0:
                out = "PASS"; break
        res[out] += 1
        st7 += seen7 and out != "PASS" or (seen7 and out == "PASS")
        ntr.append(k + 1); dds.append(dd); streaks.append(mx)
    q = lambda a, p: round(float(np.percentile(a, p)), 1)  # noqa: E731
    return {"paths": n, "pass": round(100 * res["PASS"] / n, 1), "fail": round(100 * res["FAIL"] / n, 1), "open_after_80": round(100 * res["OPEN"] / n, 1),
            "median_trades": q(ntr, 50), "max_dd_p50": q(dds, 50), "max_dd_p5": q(dds, 5), "streak_p50": q(streaks, 50), "streak_p95": q(streaks, 95),
            "p_streak7_in_eval": round(100 * st7 / n, 1), "pool_n": len(pool), "pool_win": round(100 * float((r > 0.5).mean()), 1),
            "pool_mean_r": round(float(r.mean()), 3)}


def streak_stats(pool, n=20000, seed=3, L=23):
    """longest losing streak in L trades (~40 sessions at 0.58 trades a session) and P(7+)."""
    rng = np.random.default_rng(seed)
    neg = np.array([t["r"] < 0 for t in pool])
    m = []
    for _ in range(n):
        x = neg[rng.integers(len(neg), size=L)]
        cur = mx = 0
        for v in x:
            cur = cur + 1 if v else 0; mx = max(mx, cur)
        m.append(mx)
    m = np.array(m)
    return {"trades": L, "p_7plus": round(100 * float((m >= 7).mean()), 1), "median": float(np.median(m)), "p95": float(np.percentile(m, 95))}


# ------------------------------------------------------------------------------------------------ deflated Sharpe
def norm_ppf(p):
    from statistics import NormalDist
    return NormalDist().inv_cdf(p)


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def sharpe_of(days, a, z):
    p = np.array([float(r[1]) for r in days if a <= r[0] <= z])
    return float(p.mean() / p.std(ddof=1)) if len(p) > 20 and p.std() > 0 else None


def deflated(live_daily, trials_sr, T):
    sr = live_daily.mean() / live_daily.std(ddof=1)
    g = 0.5772156649
    N = len(trials_sr)
    V = float(np.var(trials_sr, ddof=1))
    out = {}
    for nm, n in (("N = stored LIT runs", N), ("N x3 (unstored grids)", 3 * N)):
        sr0 = math.sqrt(V) * ((1 - g) * norm_ppf(1 - 1 / n) + g * norm_ppf(1 - 1 / (n * math.e)))
        x = live_daily
        sk = float(((x - x.mean()) ** 3).mean() / x.std() ** 3)
        ku = float(((x - x.mean()) ** 4).mean() / x.std() ** 4)
        z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(max(1e-9, 1 - sk * sr + (ku - 1) / 4 * sr ** 2))
        out[nm] = {"N": n, "sr_daily": round(sr, 4), "sr_annual": round(sr * math.sqrt(252), 2), "sr0_daily": round(sr0, 4),
                   "sr0_annual": round(sr0 * math.sqrt(252), 2), "DSR": round(norm_cdf(z), 3), "skew": round(sk, 2), "kurt": round(ku, 1),
                   "trust_share_of_return": round(max(0.0, (sr - sr0) / sr), 2)}
    out["trials_sr_daily_std"] = round(math.sqrt(V), 4)
    return out


def main():
    t0 = time.time()
    say = lambda s: print(f"[{time.time() - t0:5.0f}s] {s}", flush=True)  # noqa: E731
    M, S = sessions()
    res = {"made": "2026-11-26", "design": "research/fragility/DESIGN.md"}
    T0 = run({}, S)
    base = money(T0, S)
    ev0 = evalpath(T0)
    res["base"] = {"money": base, "eval": ev0}
    say(f"base {base} eval {ev0}")
    # 1. parameter surface
    surf = {}
    for kn, vs in knobs().items():
        rows = []
        for lab, x in vs:
            T = run(x, S)
            m = money(T, S)
            e = evalpath(T)
            rows.append({"step": lab, "cfg": x, "money": m, "eval": e})
        keep = {sp: sum(1 for r in rows if base[sp]["net"] > 0 and r["money"][sp]["net"] >= 0.8 * base[sp]["net"]) for sp in ("2026 H1", "2026 Jul-Oct")}
        surf[kn] = {"rows": rows, "plateau_80pct": {sp: f"{v}/{len(rows)}" for sp, v in keep.items()}}
        say(f"{kn:24s} " + " | ".join(f"{r['step']}: ${r['money']['2026 H1']['per_month']:,}/${r['money']['2026 Jul-Oct']['per_month']:,}/${r['money']['2021-25']['per_month']:,} 2w {r['eval']['H1']['p10']}/{r['eval']['H2']['p10']}" for r in rows))
    res["surface"] = surf
    # 2. costs
    cost = {}
    for k in (1, 2, 4):
        T = [{**t, "pnl": t["pnl"] - k * 1.0 * t["qty"], "low": t["low"] - k * 1.0 * t["qty"]} for t in T0]
        cost[f"+{k} tick/side"] = {"money": money(T, S), "eval": evalpath(T0, k)}
        say(f"cost +{k}: {cost[f'+{k} tick/side']}")
    res["costs"] = cost
    # 3. Monte Carlo
    p26 = [t for t in T0 if "2026-01-01" <= t["day"] <= "2026-10-16"]
    p25 = [t for t in T0 if t["day"] <= "2025-12-31"]
    pjo = [t for t in T0 if "2026-07-01" <= t["day"] <= "2026-11-20"]
    res["monte_carlo"] = {"2026 Jan-Oct pool": mc(p26), "2026 Jul-Nov pool": mc(pjo), "2021-25 pool": mc(p25),
                          "streaks_in_23_trades": {"2026": streak_stats(p26), "2021-25": streak_stats(p25)}}
    say(f"MC {res['monte_carlo']}")
    # 4. deflated Sharpe
    trials26, trials_all, n_files = [], [], 0
    for f in glob.glob("research/runs/*.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        i = d.get("id", "")
        tags = [str(x).lower() for x in (d.get("tags") or [])]
        if not (("lit" in i.lower()) or ("lit" in tags) or i.startswith("abl_")) or not d.get("days"):
            continue
        n_files += 1
        s = sharpe_of(d["days"], "2026-01-01", "2026-10-16")
        if s is not None:
            trials26.append(s)
        s2 = sharpe_of(d["days"], "2021-11-01", "2026-10-16")
        if s2 is not None:
            trials_all.append(s2)
    dl, _ = MT.daily(T0)
    S26 = [d for d in S if "2026-01-01" <= d <= "2026-10-16"]
    Sall = [d for d in S if d <= "2026-10-16"]
    x26 = np.array([dl[d][0] if d in dl else 0.0 for d in S26])
    xall = np.array([dl[d][0] if d in dl else 0.0 for d in Sall])
    res["deflated_sharpe"] = {"lit_run_files": n_files, "2026": deflated(x26, np.array(trials26), len(x26)),
                              "2021-26": deflated(xall, np.array(trials_all), len(xall)),
                              "trials_with_2026": len(trials26), "trials_with_all": len(trials_all)}
    say(f"DSR {res['deflated_sharpe']}")
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
