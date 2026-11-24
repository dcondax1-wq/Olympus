"""Pro-edge round (2026-11-24): 5 professional / institutional edges, pre-registered in research/proedge/DESIGN.md
(commit 64639bf64, before any scored run). Paper only. Futures data only (data/NQ_5m.csv, ES_5m.csv, NQ_15m.csv).
    python -X utf8 research/proedge/proedge.py  -> research/proedge/results.json + printed table
"""
from __future__ import annotations
import bisect, json, math, os, random, sys
import numpy as np
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.quant_anoms import Bars                                   # noqa: E402
from tools.pub_strats import COST_PTS                                # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
SPANS = {"2021-25": ("2021-11-08", "2025-12-31"), "2026H1": ("2026-01-01", "2026-06-30"),
         "2026H2": ("2026-07-01", "2026-10-31")}
LIT_SPANS = {"2021-25": ("2021-11-08", "2025-12-31"), "2026H1": ("2026-01-01", "2026-06-30"),
             "2026H2": ("2026-07-01", "2026-10-14")}
RV_SPANS = {"2025-04+": ("2025-04-14", "2025-12-31"), "2026H1": ("2026-01-01", "2026-06-30"),
            "2026H2": ("2026-07-01", "2026-10-31")}
ACCTS = {"50K": (3000.0, 2000.0, False, 1.0), "25K": (1500.0, 1000.0, False, 0.5), "Rapid25K": (1500.0, 1000.0, True, 0.5)}
CNQ, CES = COST_PTS["NQ"], COST_PTS["ES"]
rng = random.Random(11)
LOG = []


def lit_q(dist):
    risk = 800.0 if dist <= 20 else 16000.0 / dist
    return int(min(40, risk // (dist * 2.0)))


def inspan(s, sp, spans):
    a, b = spans[sp]
    return a <= s <= b


# ------------------------------------------------------------------ scoring
def stats(T, sess, sp, spans):
    """T: list of {s, usd, pts}; sess: all sessions (calendar for drawdown and $/month)."""
    TT = [t for t in T if inspan(t["s"], sp, spans)]
    S = [s for s in sess if inspan(s, sp, spans)]
    D = {}
    for t in TT:
        D[t["s"]] = D.get(t["s"], 0.0) + t["usd"]
    eq = pk = dd = 0.0
    for s in S:
        eq += D.get(s, 0.0); pk = max(pk, eq); dd = min(dd, eq - pk)
    w = sum(t["usd"] for t in TT if t["usd"] > 0)
    l = -sum(t["usd"] for t in TT if t["usd"] <= 0)
    net = w - l
    n = len(TT)
    return {"trades": n, "per_week": round(n / (len(S) / 5), 2) if S else 0, "pf": round(w / l, 2) if l > 0 else None,
            "win_pct": round(100 * sum(1 for t in TT if t["usd"] > 0) / n, 1) if n else None,
            "net": round(net), "per_month": round(net / (len(S) / 21)) if S else 0, "max_dd": round(dd)}


def evals(D, sess, sp, spans, acct, horizon=20):
    tgt, mll, rapid, f = ACCTS[acct]
    S = sess
    res = []
    for i0, s0 in enumerate(S):
        if not inspan(s0, sp, spans):
            continue
        bal = hi = best = 0.0
        out = None
        for j in range(i0, min(len(S), i0 + horizon)):
            p = D.get(S[j], 0.0) * f
            bal += p; best = max(best, p)
            if bal <= min(hi - mll, 100.0):
                out = ("F", j - i0 + 1); break
            hi = max(hi, bal)
            if bal >= tgt and (not rapid or (best <= 0.30 * bal and j - i0 + 1 >= 4)):
                out = ("P", j - i0 + 1); break
        res.append(out)
    n = len(res)
    P = [x[1] for x in res if x and x[0] == "P"]
    F = [x for x in res if x and x[0] == "F"]
    return {"pass": round(100 * len(P) / n, 1) if n else None, "fail": round(100 * len(F) / n, 1) if n else None,
            "days": int(np.median(P)) if P else None}


def daily(T):
    D = {}
    for t in T:
        D[t["s"]] = D.get(t["s"], 0.0) + t["usd"]
    return D


def placebo(pool, sig, sp, sess, spans, n_iter=3000):
    """pool[d][s] = trade dict or None for every session; sig = {s: d}. Random sessions, shuffled directions."""
    ev = [(s, d) for s, d in sig.items() if inspan(s, sp, spans) and pool[d].get(s)]
    if len(ev) < 3:
        return None
    obs = sum(pool[d][s]["usd"] for s, d in ev)
    days = [s for s in sess if inspan(s, sp, spans) and pool[1].get(s) and pool[-1].get(s)]
    dirs = [d for _, d in ev]
    ge = 0
    for _ in range(n_iter):
        ss = rng.sample(days, len(ev)); dd = dirs[:]; rng.shuffle(dd)
        ge += sum(pool[d][s]["usd"] for s, d in zip(ss, dd)) >= obs
    return round((ge + 1) / (n_iter + 1), 3)


def report(name, T, sess, spans, full=False, pool=None, sig=None):
    r = {"name": name, "spans": {}}
    D = daily(T)
    for sp in spans:
        x = stats(T, sess, sp, spans)
        if full:
            for a in ACCTS:
                x["eval_" + a] = evals(D, sess, sp, spans, a)
            if pool is not None:
                x["placebo_p"] = placebo(pool, sig, sp, sess, spans)
        r["spans"][sp] = x
    LOG.append({"name": name, **{sp: r["spans"][sp]["net"] for sp in spans}})
    return r


def passes(r, spans):
    return all(r["spans"][sp]["net"] > 0 and (r["spans"][sp]["pf"] or 0) > 1.1 for sp in spans)


# ------------------------------------------------------------------ NQ single-leg sim
class NQ:
    def __init__(self):
        self.B = Bars("NQ")
        self.S = self.B.full
        self.pools = {}

    def trade(self, s, ie, ix, d, stop):
        B = self.B
        e = float(B.o[ie])
        dist = d * (e - stop)
        if dist < 8:
            stop, dist = e - d * 8.0, 8.0
        q = lit_q(dist)
        if q < 1:
            return None
        x = float(B.o[ix])
        for j in range(ie, ix):
            o, h, l = float(B.o[j]), float(B.h[j]), float(B.l[j])
            if j > ie and ((d > 0 and o <= stop) or (d < 0 and o >= stop)):
                x = o; break
            if (d > 0 and l <= stop) or (d < 0 and h >= stop):
                x = stop; break
        pts = d * (x - e) - CNQ
        return {"s": s, "d": d, "q": q, "pts": pts, "usd": pts * q * 2.0}

    def pool(self, key, e_hm, x_hm, win_hm):
        """trade at e_hm open for both directions on every session; stop beyond the [win_hm, e_hm) extreme."""
        if key in self.pools:
            return self.pools[key]
        B, P = self.B, {1: {}, -1: {}}
        for s in self.S:
            ie, ix, iw = B.ix.get((s, e_hm)), B.ix.get((s, x_hm)), B.ix.get((s, win_hm))
            if ie is None or ix is None or iw is None or iw >= ie:
                P[1][s] = P[-1][s] = None; continue
            lo, hi = float(B.l[iw:ie].min()), float(B.h[iw:ie].max())
            P[1][s] = self.trade(s, ie, ix, 1, lo - 0.25)
            P[-1][s] = self.trade(s, ie, ix, -1, hi + 0.25)
        self.pools[key] = P
        return P


def prior_series(path, col, date_col="date"):
    d = pd.read_csv(os.path.join(ROOT, "data", path))
    return [str(x)[:10] for x in d[date_col]], d[col].to_numpy(float)


def prior_val(dates, vals, s, back=0):
    k = bisect.bisect_left(dates, s) - 1          # last date strictly before session s
    return None if k < 0 else (k, vals)


# ------------------------------------------------------------------ ideas 1-3
def idea1(nq, res):
    B = nq.B
    pool = nq.pool("eod", 930, 955, 870)
    rows = {}
    for k in (0.25, 0.50, 0.75):
        sig = {}
        for s in nq.S:
            i0, ie, a = B.ix.get((s, 570)), B.ix.get((s, 930)), B.atr.get(s)
            if i0 is None or ie is None or not a:
                continue
            m = float(B.o[ie] - B.o[i0])
            if abs(m) > k * a:
                sig[s] = 1 if m > 0 else -1
        T = [pool[d][s] for s, d in sig.items() if pool[d].get(s)]
        rows[k] = (sig, T, report(f"1 EOD rebalance k={k}", T, nq.S, SPANS))
    kb = max(rows, key=lambda k: rows[k][2]["spans"]["2026H1"]["net"])
    sig, T, _ = rows[kb]
    res["idea1"] = {"pick_k": kb, "all": {k: v[2] for k, v in rows.items()},
                    "pick": report(f"1 EOD rebalance k={kb} [pick]", T, nq.S, SPANS, True, pool, sig)}
    return kb, rows[kb][0]


def idea2(nq, res, base_sig):
    pool = nq.pool("eod", 930, 955, 870)
    gd, gv = prior_series("GEX_1d.csv", "gex")
    vd, vv = prior_series("VXN_1d.csv", "close")

    def prev(dates, vals, s, n=None):
        k = bisect.bisect_left(dates, s) - 1
        if k < 0:
            return None, None
        med = float(np.median(vals[max(0, k - n + 1):k + 1])) if n else None
        return float(vals[k]), med
    conds = {
        "2a GEX<0": lambda s: (lambda v, m: None if v is None else v < 0)(*prev(gd, gv, s)),
        "2b GEX<250d median": lambda s: (lambda v, m: None if v is None else v < m)(*prev(gd, gv, s, 250)),
        "2c VXN>60d median": lambda s: (lambda v, m: None if v is None else v > m)(*prev(vd, vv, s, 60)),
    }
    out = {}
    for name, c in conds.items():
        sig = {s: d for s, d in base_sig.items() if c(s) is True}
        comp = {s: d for s, d in base_sig.items() if c(s) is False}
        T = [pool[d][s] for s, d in sig.items() if pool[d].get(s)]
        Tc = [pool[d][s] for s, d in comp.items() if pool[d].get(s)]
        out[name] = {"short_gamma": report("2 " + name, T, nq.S, SPANS, True, pool, sig),
                     "complement_logonly": {sp: stats(Tc, nq.S, sp, SPANS) for sp in SPANS}}
    res["idea2"] = out


def idea3(nq, res):
    B = nq.B
    pool = nq.pool("on", 600, 955, 570)
    ON = {}
    for s in nq.S:
        a, b, at = B.ix.get((s, 1080)), B.ix.get((s, 570)), B.atr.get(s)
        if a is None or b is None or not at:
            continue
        ON[s] = (float(B.o[b] - B.o[a]), at)
    # diagnostic: corr(ON, 10:00->15:55)
    diag = {}
    for sp in SPANS:
        xs, ys = [], []
        for s, (m, at) in ON.items():
            i1, i2 = B.ix.get((s, 600)), B.ix.get((s, 955))
            if inspan(s, sp, SPANS) and i1 is not None and i2 is not None:
                xs.append(m / at); ys.append(float(B.o[i2] - B.o[i1]) / at)
        diag[sp] = round(float(np.corrcoef(xs, ys)[0, 1]), 3)
    rows = {}
    for k in (0.25, 0.50, 0.75):
        for mode, f in (("follow", 1), ("fade", -1)):
            sig = {s: f * (1 if m > 0 else -1) for s, (m, at) in ON.items() if abs(m) > k * at}
            T = [pool[d][s] for s, d in sig.items() if pool[d].get(s)]
            rows[(k, mode)] = (sig, T, report(f"3 overnight {mode} k={k}", T, nq.S, SPANS))
    kb = max(rows, key=lambda k: rows[k][2]["spans"]["2026H1"]["net"])
    sig, T, _ = rows[kb]
    res["idea3"] = {"corr_ON_vs_rest_of_day": diag, "pick": report(f"3 overnight {kb[1]} k={kb[0]} [pick]", T, nq.S, SPANS,
                                                                    True, pool, sig),
                    "all": {f"{k}/{m}": v[2] for (k, m), v in rows.items()}}


# ------------------------------------------------------------------ idea 4: LIT expansion skip
def idea4(nq, res):
    L = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    trades = L["trades"]
    d15 = pd.read_csv(os.path.join(ROOT, "data", "NQ_15m.csv"))
    t15 = d15.time.to_numpy(np.int64)
    o, h, l, c = (d15[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    sess = [s for s in nq.S if s <= "2026-10-14"]
    allsess = sorted(set(sess) | {t["day"] for t in trades})
    feat = []
    for t in trades:
        k = bisect.bisect_right(t15 + 900, int(t["entry_t"])) - 1      # last bar with close time <= entry
        if k < 24:
            feat.append(None); continue
        atr = float(tr[k - 19:k + 1].mean())
        body = c[k - 3:k + 1] - o[k - 3:k + 1]
        opp = float((-body).max()) if t["side"] == "LONG" else float(body.max())
        feat.append(max(0.0, opp) / atr if atr > 0 else None)
    base = [{"s": t["day"], "usd": float(t["pnl"])} for t in trades]
    rows = {"LIT as is": report("4 LIT baseline", base, allsess, LIT_SPANS, True)}
    picks = {}
    for x in (1.5, 2.0, 2.5):
        keep = [b for b, f in zip(base, feat) if f is None or f < x]
        skip = [b for b, f in zip(base, feat) if f is not None and f >= x]
        r = report(f"4 LIT skip opp-15m-body>={x}ATR", keep, allsess, LIT_SPANS, True)
        for sp in LIT_SPANS:
            sk = [b for b in skip if inspan(b["s"], sp, LIT_SPANS)]
            pool_sp = [b for b in base if inspan(b["s"], sp, LIT_SPANS)]
            obs = -sum(b["usd"] for b in sk)                           # $ gained by skipping
            ge = 0
            for _ in range(3000):
                rs = rng.sample(pool_sp, len(sk)) if sk else []
                ge += -sum(b["usd"] for b in rs) >= obs
            r["spans"][sp]["skipped"] = len(sk)
            r["spans"][sp]["skipped_net"] = round(sum(b["usd"] for b in sk))
            r["spans"][sp]["skip_placebo_p"] = round((ge + 1) / 3001, 3)
            r["spans"][sp]["delta_per_month"] = r["spans"][sp]["per_month"] - rows["LIT as is"]["spans"][sp]["per_month"]
        rows[x] = r
        picks[x] = r["spans"]["2026H1"]["net"]
    xb = max(picks, key=picks.get)
    res["idea4"] = {"pick_x": xb, "rows": {str(k): v for k, v in rows.items()},
                    "feature_coverage": sum(f is not None for f in feat), "n_trades": len(trades)}


# ------------------------------------------------------------------ idea 5: NQ/ES spread
def idea5(nq, res):
    A, E = nq.B, Bars("ES")
    ei = {int(t): i for i, t in enumerate(E.t)}
    idx = [(i, ei[int(t)]) for i, t in enumerate(A.t) if int(t) in ei]
    ia = np.array([a for a, _ in idx]); ib = np.array([b for _, b in idx])
    sp_ = np.log(A.c[ia]) - np.log(E.c[ib])
    hm = A.hm[ia]; ss = A.sess[ia]
    out = {}
    for W in (48, 96):
        s_ser = pd.Series(sp_)
        mu = s_ser.rolling(W).mean().to_numpy(); sd = s_ser.rolling(W).std().to_numpy()
        z = (sp_ - mu) / sd
        T, pos, nday = [], None, {}
        for k in range(W, len(ia) - 1):
            nxt = k + 1
            if pos is not None:
                ex = None
                if ss[nxt] != pos["s"] or hm[nxt] >= 955:
                    ex = nxt if ss[nxt] == pos["s"] else k
                elif np.sign(z[k]) != pos["zs"] or abs(z[k]) >= 4.0:
                    ex = nxt
                if ex is not None:
                    a1, b1 = A.o[ia[ex]] if ex == nxt else A.c[ia[k]], E.o[ib[ex]] if ex == nxt else E.c[ib[k]]
                    dn = pos["dn"]
                    g = pos["qn"] * 2.0 * dn * (a1 - pos["a0"]) + pos["qe"] * 5.0 * (-dn) * (b1 - pos["b0"])
                    cost = pos["qn"] * 2.0 * CNQ + pos["qe"] * 5.0 * CES
                    T.append({"s": pos["s"], "usd": g - cost, "gross": g, "cost": cost, "d": dn})
                    pos = None
                continue
            if not (575 <= hm[nxt] <= 900) or ss[nxt] != ss[k] or not np.isfinite(z[k]) or abs(z[k]) <= 2.5:
                continue
            if nday.get(ss[k], 0) >= 2 or sd[k] <= 0:
                continue
            a0, b0 = float(A.o[ia[nxt]]), float(E.o[ib[nxt]])
            qn = int(500.0 // (1.5 * sd[k] * a0 * 2.0))
            qn = max(0, min(40, qn))
            qe = int(round(qn * a0 * 2.0 / (b0 * 5.0)))
            if qe > 40:
                qn = int(qn * 40 / qe); qe = 40
            if qn < 1 or qe < 1:
                continue
            zs = np.sign(z[k])
            pos = {"s": ss[k], "dn": -zs, "zs": zs, "a0": a0, "b0": b0, "qn": qn, "qe": qe}
            nday[ss[k]] = nday.get(ss[k], 0) + 1
        sess = [s for s in nq.S if s >= "2025-04-14"]
        r = report(f"5 NQ/ES z>2.5 W={W}", T, sess, RV_SPANS, True)
        # sign placebo: flip each trade's direction at random (usd = d*G - C)
        for spn in RV_SPANS:
            TT = [t for t in T if inspan(t["s"], spn, RV_SPANS)]
            if len(TT) < 3:
                continue
            obs = sum(t["usd"] for t in TT)
            ge = sum(sum((t["gross"] if rng.random() < .5 else -t["gross"]) - t["cost"] for t in TT) >= obs
                     for _ in range(3000))
            r["spans"][spn]["placebo_p"] = round((ge + 1) / 3001, 3)
            r["spans"][spn]["gross_net"] = round(sum(t["gross"] for t in TT))
        out[W] = r
    wb = max(out, key=lambda w: out[w]["spans"]["2026H1"]["net"])
    res["idea5"] = {"pick_W": wb, "rows": {str(k): v for k, v in out.items()}}


def main():
    nq = NQ()
    res = {"design": "research/proedge/DESIGN.md @ 64639bf64"}
    kb, sig = idea1(nq, res)
    idea2(nq, res, sig)
    idea3(nq, res)
    idea4(nq, res)
    idea5(nq, res)
    res["variants_logged"] = LOG
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    for x in LOG:
        print(x)


if __name__ == "__main__":
    main()
