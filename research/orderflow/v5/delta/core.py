"""v5 'delta' family core (rules: research/orderflow/v5/delta/DESIGN.md, frozen before any result). PAPER RESEARCH ONLY.

Delta burst continuation (M), delta divergence at 15m swings (V), overnight cumulative delta -> RTH open bias (O).
Every variant = a price-only POOL + an order-flow LABEL; the book trades labelled rows. Imports nothing that can trade.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from engine import ofsum  # noqa: E402

TICK, PV, COMM = 0.25, 2.0, 1.90
MKT_TICKS, STOP_SLIP, FLAT_SLIP, MIN_STOP = 18, 2, 2, 8
LAST_BAR, LAST_ENTRY = 950, 945            # flat by the 15:50 bar close; entry bar opens <= 15:45
MIN_ROWS, ON_MIN_VOL, N_PERM = 50_000, 20_000, 5000
IS_FIRST, IS_LAST = "2026-09-27", "2026-11-26"

SPECS = {
    "M1": {"fam": "M", "Z": 2.0, "RR": 1.5, "H": 6},
    "M2": {"fam": "M", "Z": 3.0, "RR": 1.5, "H": 6},
    "V1": {"fam": "V", "inside": False, "RR": 2.0, "H": 12},
    "V2": {"fam": "V", "inside": True, "RR": 2.0, "H": 12},
    "O1": {"fam": "O", "mode": "confirm", "RR": 2.0, "H": 11},
    "O2": {"fam": "O", "mode": "pure", "RR": 2.0, "H": 11},
}
NAMES = {"M1": "delta burst z>=2 + breakout -> continue", "M2": "delta burst z>=3 + breakout -> continue",
         "V1": "15m swing take-out, CVD divergence -> fade", "V2": "15m swing failed take-out, CVD divergence -> fade",
         "O1": "09:30 bar dir agrees with overnight delta", "O2": "trade overnight-delta direction at 09:35"}
VIDS = list(SPECS)


def _load_battery():
    sp = importlib.util.spec_from_file_location("v5dl_battery", os.path.join(ROOT, "research", "orderflow", "of_battery.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


B = _load_battery()


# ------------------------------------------------------------------------------------------------ data
def day_dirs():
    out = {}
    for base in (os.path.join(ROOT, "data", "pc_days"), os.path.join(ROOT, "logs", "datapipe", "days")):
        if os.path.isdir(base):
            for d in sorted(os.listdir(base)):
                if len(d) == 10 and os.path.exists(os.path.join(base, d, "of", "NQ_meta.json")):
                    out.setdefault(d, os.path.join(base, d))
    return out


class DD:
    """one day's arrays."""

    def __init__(self, day, Dy):
        self.day = day
        b = Dy.bars
        self.t = b["t"].to_numpy(np.int64)
        self.mod = b["mod"].to_numpy(int)
        self.o, self.h, self.l, self.c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.v = b["volume"].to_numpy(float)
        self.dl = b["delta"].to_numpy(float)
        self.n = b["n"].to_numpy(float)
        self.idx_mod = {int(m): i for i, m in enumerate(self.mod)}


def load_days():
    """{day: DD} for every file (thin ones too: overnight history only) + the sorted usable list."""
    D, usable = {}, []
    for d, p in day_dirs().items():
        R = ofsum.read(p)
        if not R or not len(R["bars"]):
            continue
        D[d] = DD(d, B.Day(d, R))
        if int(R["meta"].get("rows", 0)) >= MIN_ROWS:
            usable.append(d)
    return D, sorted(usable)


def rth_days(D, days):
    return [d for d in days if 570 in D[d].idx_mod]


# ------------------------------------------------------------------------------------------------ trade engine
def simulate(X, i, d, ext_stop, RR, H):
    """E5 at the signal close, stop/target/time exit (DESIGN 'Shared trade engine'). Returns a result dict."""
    t, mod, o, h, l, c = X.t, X.mod, X.o, X.h, X.l, X.c
    r = {"R": None, "usd": None, "how": None}
    j = i + 1
    if j >= len(t) or t[j] != t[i] + 300 or mod[j] > LAST_ENTRY:
        r["how"] = "no bar"; return r
    L = c[i]
    if (d == 1 and l[j] <= L - TICK) or (d == -1 and h[j] >= L + TICK):
        fill, k0, limit_bar, how = L, j, True, "level"
    else:
        if j + 1 >= len(t) or t[j + 1] != t[j] + 300 or mod[j + 1] > LAST_ENTRY:
            r["how"] = "no bar"; return r
        fill, k0, limit_bar, how = o[j + 1] + d * MKT_TICKS * TICK, j + 1, False, "market+18"
    stop = ext_stop
    if (fill - stop) * d < MIN_STOP * TICK:
        stop = fill - d * MIN_STOP * TICK
    risk = (fill - stop) * d
    tgt = fill + d * RR * risk
    end = i + H
    ex = why = ek = None
    last = None
    for k in range(k0, len(t)):
        if mod[k] > LAST_BAR or k > end or (k > k0 and t[k] != t[k - 1] + 300):
            break
        last = k
        if (d == 1 and l[k] <= stop) or (d == -1 and h[k] >= stop):
            base = o[k] if (k > k0 and (o[k] - stop) * d < 0) else stop
            ex, why, ek = base - d * STOP_SLIP * TICK, "stop", k; break
        if k == k0 and limit_bar:
            continue
        if (d == 1 and h[k] >= tgt + TICK) or (d == -1 and l[k] <= tgt - TICK):
            ex, why, ek = tgt, "target", k; break
    if ex is None:
        if last is None:
            r["how"] = "no bar"; return r
        ex, why, ek = c[last] - d * FLAT_SLIP * TICK, "time", last
    usd = (ex - fill) * d * PV - COMM
    q = int(min(40, 500.0 // (risk * PV)))
    r.update(fill=round(float(fill), 2), stop=round(float(stop), 2), how=how, exit=round(float(ex), 2), why=why,
             t_close=int(t[i]) + 300, exit_close=int(t[ek]) + 300, risk_pts=round(float(risk), 2),
             R=round(float(usd / (risk * PV)), 4), usd=round(float(usd), 2), usd500=round(float(usd * q), 2) if q >= 1 else 0.0)
    return r


# ------------------------------------------------------------------------------------------------ pools
def pool_M(X, Z):
    out = []
    t, mod, h, l, c, dl, n = X.t, X.mod, X.h, X.l, X.c, X.dl, X.n
    for i in range(20, len(t)):
        if not (600 <= mod[i] <= 900) or n[i] < 20 or t[i] - t[i - 20] != 6000:
            continue
        base = dl[i - 20:i]
        sd = base.std(ddof=1)
        if not sd > 0:
            continue
        z = (dl[i] - base.mean()) / sd
        if c[i] > h[i - 3:i].max():
            d, ext = 1, l[i] - TICK
        elif c[i] < l[i - 3:i].min():
            d, ext = -1, h[i] + TICK
        else:
            continue
        out.append({"day": X.day, "i": i, "d": d, "ext": float(ext), "lab": bool(z * d >= Z), "z": round(float(z), 2)})
    return out


def groups15(X):
    """complete RTH 15m groups: list of dicts (g, i0, i_last, high, low, close, cvd at close)."""
    cvd, run = {}, 0.0
    for i in range(len(X.t)):
        if 570 <= X.mod[i] < 960:
            run += X.dl[i]; cvd[i] = run
    G = []
    for g in range(26):
        m0 = 570 + 15 * g
        ix = [X.idx_mod.get(m0 + 5 * k) for k in range(3)]
        if any(x is None for x in ix) or ix[1] != ix[0] + 1 or ix[2] != ix[1] + 1:
            continue
        G.append({"g": g, "i0": ix[0], "i": ix[2], "high": float(X.h[ix[0]:ix[2] + 1].max()),
                  "low": float(X.l[ix[0]:ix[2] + 1].min()), "close": float(X.c[ix[2]]), "cvd": cvd[ix[2]]})
    return G


def pool_V(X, inside):
    G = groups15(X)
    byg = {x["g"]: x for x in G}
    out = []
    for s in (1, -1):                  # s=+1: pivot highs / short fades; s=-1: pivot lows / long fades
        key = "high" if s == 1 else "low"
        active, used = None, True
        for q in G:
            gq = q["g"]
            # a pivot m confirmed at the close of m+1 = gq-1 (needs m-1, m, m+1 consecutive)
            m = gq - 2
            if gq - 1 in byg and m in byg and m - 1 in byg:
                pm, a, b_ = byg[m], byg[m - 1], byg[gq - 1]
                if (pm[key] - a[key]) * s > 0 and (pm[key] - b_[key]) * s > 0:
                    pass  # confirmed at close of gq-1: usable from gq on
                else:
                    pm = None
            else:
                pm = None
            if pm is not None:
                active, used = pm, False
            if active is None or used or q["g"] < active["g"] + 2:
                continue
            if (q[key] - active[key]) * s > 0:
                used = True
                mod_close = X.mod[q["i"]] + 5
                if not (615 <= mod_close <= 900):
                    continue
                if inside and not ((q["close"] - active[key]) * s < 0):
                    continue
                d = -s
                lab = (q["cvd"] <= active["cvd"]) if s == 1 else (q["cvd"] >= active["cvd"])
                ext = q["high"] + TICK if s == 1 else q["low"] - TICK
                out.append({"day": X.day, "i": q["i"], "d": d, "ext": float(ext), "lab": bool(lab)})
    return out


def on_delta(D, day):
    X = D[day]
    prev = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
    dsum = vsum = 0.0
    if prev in D:
        P = D[prev]
        mk = P.mod >= 1080
        dsum += P.dl[mk].sum(); vsum += P.v[mk].sum()
    mk = X.mod < 570
    dsum += X.dl[mk].sum(); vsum += X.v[mk].sum()
    return float(dsum), float(vsum)


def pool_O(D, day, mode):
    X = D[day]
    i = X.idx_mod.get(570)
    if i is None or X.n[i] < 20:
        return []
    ond, onv = on_delta(D, day)
    if onv < ON_MIN_VOL or ond == 0:
        return []
    son = 1 if ond > 0 else -1
    rows = []
    if mode == "confirm":
        if X.c[i] == X.o[i]:
            return []
        d = 1 if X.c[i] > X.o[i] else -1
        rows.append({"d": d, "lab": d == son})
    else:
        rows = [{"d": 1, "lab": son == 1}, {"d": -1, "lab": son == -1}]
    for r in rows:
        r.update(day=day, i=i, ext=float(X.l[i] - TICK if r["d"] == 1 else X.h[i] + TICK), on_delta=ond, on_vol=onv)
    return rows


def run_variant(D, days, vid, spec=None):
    sp = spec or SPECS[vid]
    out = []
    for day in days:
        X = D[day]
        if sp["fam"] == "M":
            P = pool_M(X, sp["Z"])
        elif sp["fam"] == "V":
            P = pool_V(X, sp["inside"])
        else:
            P = pool_O(D, day, sp["mode"])
        for x in P:
            x.update(simulate(X, x["i"], x["d"], x["ext"], sp["RR"], sp["H"]))
            out.append(x)
    return out


# ------------------------------------------------------------------------------------------------ scoring
def book(rows):
    out, last_exit = [], None
    for x in sorted(rows, key=lambda r: (r["day"], r["i"], -r["d"])):
        if not x["lab"] or x.get("R") is None:
            continue
        if last_exit is not None and x["t_close"] < last_exit:
            continue
        out.append(x); last_exit = x["exit_close"]
    return out


def perm_p(x, lab, seed=7, n=N_PERM):
    x = np.asarray(x, float); lab = np.asarray(lab, bool)
    if lab.sum() == 0 or (~lab).sum() == 0:
        return None
    obs = x[lab].mean() - x[~lab].mean()
    rng = np.random.default_rng(seed)
    k, N = int(lab.sum()), len(x)
    hits = 0
    for _ in range(n // 500):
        idx = np.argsort(rng.random((500, N)), axis=1)[:, :k]
        s = x[idx].sum(1)
        hits += int((s / k - (x.sum() - s) / (N - k) >= obs - 1e-12).sum())
    return round((hits + 1) / (n + 1), 4)


def flip_p(rows, seed=7, n=N_PERM):
    """O2: per day R(long) / R(short); random side per day vs the ON-delta side (one-sided on mean R)."""
    by = {}
    for x in rows:
        if x.get("R") is not None:
            by.setdefault(x["day"], {})[x["d"]] = x
    pairs = [(v[1]["R"], v[-1]["R"], v[1]["lab"]) for v in by.values() if 1 in v and -1 in v]
    if not pairs:
        return None
    A = np.array([[a, b] for a, b, _ in pairs]); lab = np.array([0 if lb else 1 for _, _, lb in pairs])
    obs = A[np.arange(len(A)), lab].mean()
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, 2, (n, len(A)))
    sims = A[np.arange(len(A))[None, :], pick].mean(1)
    return round(float(((sims >= obs - 1e-12).sum() + 1) / (n + 1)), 4)


def holm(ps):
    items = sorted([(p, k) for k, p in ps.items() if p is not None])
    m, adj, run = len(items), {}, 0.0
    for r, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - r) * p)); adj[k] = round(run, 4)
    return {k: adj.get(k) for k in ps}


def max_dd(us):
    cum = peak = dd = 0.0
    for u in us:
        cum += u; peak = max(peak, cum); dd = max(dd, peak - cum)
    return dd


def score(rows, days, n_rth, vid):
    days = sorted(days)
    k = (len(days) + 1) // 2
    H = {"older": set(days[:k]), "newer": set(days[k:])}
    res = [x for x in rows if x.get("R") is not None]
    bk = book(rows)
    U = np.array([x["usd"] for x in bk], float); R = np.array([x["R"] for x in bk], float)
    wins, loss = U[U > 0].sum(), -U[U <= 0].sum()
    ra = np.array([x["R"] for x in res], float); la = np.array([x["lab"] for x in res], bool)
    out = {"pool": len(rows), "resolved": len(res), "labelled": int(la.sum()) if len(la) else 0, "trades": len(bk),
           "per_week": round(len(bk) / (n_rth / 5.0), 2) if n_rth else None,
           "win_pct": round(100 * float((U > 0).mean()), 1) if len(U) else None,
           "mean_R": round(float(R.mean()), 3) if len(R) else None,
           "pf": round(float(wins / loss), 2) if loss > 0 else None,
           "net_usd": round(float(U.sum()), 0), "usd500": round(float(sum(x["usd500"] for x in bk)), 0),
           "max_dd_usd": round(max_dd([x["usd"] for x in sorted(bk, key=lambda r: r["exit_close"])]), 0),
           "how": {h: sum(1 for x in bk if x["how"] == h) for h in ("level", "market+18")},
           "why": {w: sum(1 for x in bk if x["why"] == w) for w in ("target", "stop", "time")},
           "gap_R": round(float(ra[la].mean() - ra[~la].mean()), 3) if la.any() and (~la).any() else None,
           "pool_all_R": round(float(ra.mean()), 3) if len(ra) else None,
           "unlab_mean_R": round(float(ra[~la].mean()), 3) if (~la).any() else None}
    out["placebo_p"] = flip_p(rows) if SPECS.get(vid, {}).get("mode") == "pure" else perm_p(ra, la)
    hv = {}
    for nm, s in H.items():
        bR = [x["R"] for x in bk if x["day"] in s]
        a = [x["R"] for x in res if x["day"] in s and x["lab"]]
        na = [x["R"] for x in res if x["day"] in s and not x["lab"]]
        hv[nm] = {"trades": len(bR), "mean_R": round(float(np.mean(bR)), 3) if bR else None,
                  "usd": round(float(sum(x["usd"] for x in bk if x["day"] in s)), 0),
                  "gap_R": round(float(np.mean(a) - np.mean(na)), 3) if a and na else None}
    out["halves"] = hv
    return out


def verdict(s, p_holm):
    if s["trades"] < 20:
        return "TOO FEW"
    both = all((h["mean_R"] or -1) > 0 and (h["gap_R"] or -1) > 0 for h in s["halves"].values())
    if (s["net_usd"] > 0 and (s["pf"] or 0) >= 1.20 and both and (s["placebo_p"] or 1) < 0.10
            and p_holm is not None and p_holm < 0.10):
        return "YES-candidate"
    if s["net_usd"] > 0 and (s["gap_R"] or -1) > 0 and (s["placebo_p"] or 1) < 0.20:
        return "weak"
    return "NO"


def table(rows):
    hdr = ("var", "rule", "pool", "label", "trades", "/wk", "win%", "meanR", "PF", "$1mic", "maxDD", "$500risk",
           "halves R (old/new)", "halves gap", "gap", "p", "Holm", "verdict")
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for vid, s in rows:
        hv = s["halves"]
        lines.append("| " + " | ".join(str(x) for x in (
            vid, NAMES.get(vid, vid), s["resolved"], s["labelled"], s["trades"], s["per_week"], s["win_pct"], s["mean_R"],
            s["pf"], f"${s['net_usd']:+,.0f}", f"${s['max_dd_usd']:,.0f}", f"${s['usd500']:+,.0f}",
            f"{hv['older']['mean_R']} / {hv['newer']['mean_R']}", f"{hv['older']['gap_R']} / {hv['newer']['gap_R']}",
            s["gap_R"], s["placebo_p"], s.get("holm_p"), s.get("verdict"))) + " |")
    return "\n".join(lines)
