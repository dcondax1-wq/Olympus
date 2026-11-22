"""Edge hunt lane C (2026-11-22): calendar + money-flow timing on NQ futures (TV NQ1! 5m, data/NQ_5m.csv). Paper only.

(a) standalone: calendar window -> day trade, entry at a fixed time, stop 1 tick beyond the structural extreme of the last
    60 min (12 x 5m bars), size from the stop by the LIT rule ($800 risk up to a 20-pt stop, then 16,000/stop; micros
    = risk/(stop*$2), 1..40), one target (none / 1.5R / 3R) else flat at the exit time; costs 1.45 pts a micro round trip
    (1 tick slippage each way + $1.90 commission), stop wins a same-bar tie.  All MFFU-legal (flat before 16:10).
(b) size dial: LIT's real trades (research/lab/backtest_live.json) x f on window days, f capped by 40 micros and the
    ~$990 DLL room; eval pass/fail by the 50K EOD-trailing rule.
Pick (target option, dial direction, pension threshold) on 2026 Jan-Jun ONLY, then read 2026 Jul-Oct and 2021-25.
    python -X utf8 research/edge_hunt/c/edge_c.py   -> research/edge_hunt/c/results.json + printed tables
"""
from __future__ import annotations
import datetime as dt, json, math, os, random, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from tools.quant_anoms import Bars                                    # noqa: E402
from tools.pub_strats import Strat, stats, evals, daily, corr, lit_days, SPANS, COST_PTS, in_span  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
PT = 2.0
COST = COST_PTS["NQ"]
VARIANTS = []          # every variant logged (count reported)
rng = random.Random(7)


def lit_q(dist):
    risk = 800.0 if dist <= 20 else 16000.0 / dist
    return int(min(40, risk // (dist * PT)))


class Sim:
    def __init__(self):
        self.B = Bars("NQ")
        self.st = Strat(self.B, "NQ")
        B = self.B
        self.S = self.st.S
        self.cal = [s for s in B.all_sess if (s, 570) in B.ix]      # trading days incl. early closes
        self.cache = {}

    def one(self, s, e_hm, x_hm, d, tgt):
        B = self.B
        ie, ix = B.ix.get((s, e_hm)), B.ix.get((s, x_hm))
        if ie is None or ix is None or ix <= ie or ie < 12:
            return None
        e = float(B.o[ie])
        lo, hi = float(B.l[ie - 12:ie].min()), float(B.h[ie - 12:ie].max())
        if d > 0:
            stop = lo - 0.25
            dist = e - stop
            if dist < 8:
                stop, dist = e - 8, 8.0
        else:
            stop = hi + 0.25
            dist = stop - e
            if dist < 8:
                stop, dist = e + 8, 8.0
        q = lit_q(dist)
        if q < 1:
            return None
        tp = e + d * tgt * dist if tgt else None
        x, why = float(B.o[ix]), "time"
        for j in range(ie, ix):
            o, h, l = float(B.o[j]), float(B.h[j]), float(B.l[j])
            if j > ie and ((d > 0 and o <= stop) or (d < 0 and o >= stop)):
                x, why = o, "stop"; break
            if (d > 0 and l <= stop) or (d < 0 and h >= stop):
                x, why = stop, "stop"; break
            if tp is not None and ((d > 0 and h >= tp) or (d < 0 and l <= tp)):
                x, why = tp, "tp"; break
        pts = d * (x - e) - COST
        usd = pts * q * PT
        return {"s0": s, "s1": s, "d": d, "q": q, "pts": pts, "usd": usd, "legs": [(s, usd)], "why": why, "dist": dist}

    def pool(self, e_hm, x_hm, d, tgt):
        k = (e_hm, x_hm, d, tgt)
        if k not in self.cache:
            self.cache[k] = {s: self.one(s, e_hm, x_hm, d, tgt) for s in self.S}
        return self.cache[k]


# ------------------------------------------------------------------ windows: name -> {session: direction}
def month_groups(cal):
    by = {}
    for s in cal:
        by.setdefault(s[:7], []).append(s)
    return [by[m] for m in sorted(by)]


def third_friday(y, m):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(4 - d.weekday()) % 7 + 14)
    return d


def windows(sim, theta=None):
    cal, W = sim.cal, {}
    M = month_groups(cal)
    L = lambda ss: {s: 1 for s in ss}
    W["tom_last2"] = L([s for m in M for s in m[-2:]])
    W["tom_first3"] = L([s for m in M for s in m[:3]])
    W["tom_all5"] = {**W["tom_last2"], **W["tom_first3"]}
    ow, of, pm = [], [], []
    for m in M:
        y, mo = int(m[0][:4]), int(m[0][5:7])
        tf = third_friday(y, mo)
        for s in m:
            d = dt.date.fromisoformat(s)
            if d.isocalendar()[:2] == tf.isocalendar()[:2]:
                ow.append(s)
            if d == tf:
                of.append(s)
            if d == tf + dt.timedelta(days=3):
                pm.append(s)
    W["opex_week"], W["opex_fri"], W["opex_next_mon"] = L(ow), L(of), L(pm)
    qe = [s for m in M if m[0][5:7] in ("03", "06", "09", "12") for s in m[-3:]]
    qa = [s for m in M if m[0][5:7] in ("01", "04", "07", "10") for s in m[:2]]
    W["qend_last3"], W["qstart_first2"] = L(qe), L(qa)
    for i, n in enumerate(["mon", "tue", "wed", "thu", "fri"]):
        W["dow_" + n] = L([s for s in cal if dt.date.fromisoformat(s).weekday() == i])
    return W


def pension(sim, theta, nlast=3):
    """last nlast days of a month after a month-to-date move beyond +-theta %: fade the month (pension rebalancing)."""
    B, cal = sim.B, sim.cal
    M = month_groups(cal)
    out = {}
    for a, b in zip(M[:-1], M[1:]):
        base = B.upx(a[0], 570)                      # 09:30 open on the month's first day
        for s in a[-nlast:]:
            ref = B.upx(s, 570)
            if base is None or ref is None:
                continue
            r = 100.0 * (ref / base - 1.0)
            if r >= theta:
                out[s] = -1
            elif r <= -theta:
                out[s] = 1
    return out


# ------------------------------------------------------------------ scoring
def pick(sim, W, e_hm, x_hm, tgt):
    """trades for window dict {s: d}"""
    T = []
    for s, d in W.items():
        t = sim.pool(e_hm, x_hm, d, tgt).get(s)
        if t:
            T.append(t)
    return T


def perm_p(sim, W, e_hm, x_hm, tgt, span, n_iter=3000):
    ev = [(s, d) for s, d in W.items() if in_span(s, span) and s in sim.st.k]
    if len(ev) < 3:
        return None, len(ev)
    usd = lambda s, d: (sim.pool(e_hm, x_hm, d, tgt).get(s) or {"usd": 0.0})["usd"]
    obs = sum(usd(s, d) for s, d in ev)
    days = [s for s in sim.S if in_span(s, span)]
    dirs = [d for _, d in ev]
    ge = 0
    for _ in range(n_iter):
        ss = rng.sample(days, len(ev))
        dd = dirs[:]; rng.shuffle(dd)
        ge += sum(usd(s, d) for s, d in zip(ss, dd)) >= obs
    return round((ge + 1) / (n_iter + 1), 3), len(ev)


def boot_ci(T, span, n=2000):
    u = [t["usd"] for t in T if in_span(t["s1"], span)]
    if len(u) < 3:
        return None
    m = [np.mean([rng.choice(u) for _ in u]) for _ in range(n)]
    return [round(float(np.percentile(m, 2.5))), round(float(np.percentile(m, 97.5)))]


def row(sim, name, W, e_hm, x_hm, tgt, LD, full=False):
    T = pick(sim, W, e_hm, x_hm, tgt)
    D = daily(T)
    r = {"name": name, "e_hm": e_hm, "x_hm": x_hm, "tgt": tgt, "spans": {}}
    for sp in SPANS:
        s = stats(T, sim.st, sp)
        if not s:
            continue
        ev = sum(1 for k in W if in_span(k, sp))
        s["events"] = ev
        if full:
            s["perm_p"], _ = perm_p(sim, W, e_hm, x_hm, tgt, sp)
            s["boot95_usd_per_trade"] = boot_ci(T, sp)
            s["eval_2wk"] = evals(D, sim.st, sp, horizon=10)
            s["eval_1mo"] = evals(D, sim.st, sp, horizon=21)
            s["corr_lit"], s["on_lit_off_days_per_mo"] = corr(D, LD, sim.st, sp)
        r["spans"][sp] = s
    VARIANTS.append(name + f"|{e_hm}|{x_hm}|{tgt}")
    return r


def beats(r):
    sp = r["spans"]
    return all(sp.get(k) and sp[k]["net"] > 0 for k in ("2026H1", "2026H2", "2021-25"))


# ------------------------------------------------------------------ LIT dial
def lit_trades():
    d = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    return d["trades"]


def dial_days(LD, trades, Wset, f, cap_risk=990.0):
    out = dict(LD)
    for t in trades:
        s = t["day"]
        if s in Wset:
            fe = min(f, 40.0 / max(1, t["qty_total"]), cap_risk / max(1.0, t["risk_usd"])) if f > 1 else f
            out[s] = out.get(s, 0.0) + t["pnl"] * (fe - 1.0)
    return out


def span_net(D, st, span):
    return sum(D.get(s, 0.0) for s in st.S if in_span(s, span))


def dial_row(sim, name, Wset, f, LD, trades):
    D2 = dial_days(LD, trades, Wset, f)
    r = {"name": f"{name} x{f}", "spans": {}}
    for sp in SPANS:
        base, new = span_net(LD, sim.st, sp), span_net(D2, sim.st, sp)
        days = [s for s in sim.S if in_span(s, sp)]
        n = sum(1 for s in days if s in Wset)
        ge = 0
        for _ in range(1500):
            R = set(rng.sample(days, n)) if n else set()
            ge += span_net(dial_days(LD, trades, R, f), sim.st, sp) >= new
        r["spans"][sp] = {"lit_net": round(base), "dial_net": round(new), "delta": round(new - base), "window_days": n,
                          "perm_p": round((ge + 1) / 1501, 3),
                          "eval_2wk": evals(D2, sim.st, sp, horizon=10), "eval_2wk_base": evals(LD, sim.st, sp, horizon=10),
                          "eval_1mo": evals(D2, sim.st, sp, horizon=21), "eval_1mo_base": evals(LD, sim.st, sp, horizon=21)}
    VARIANTS.append(r["name"])
    return r


def main():
    sim = Sim()
    LD = lit_days()
    trades = lit_trades()
    W = windows(sim)
    res = {"standalone": [], "tod": [], "pension": [], "dial": [], "notes": {}}
    # ---- (a) calendar windows: 09:30 entry, long (documented bias), flat 15:55
    for name, w in W.items():
        c = [row(sim, name, w, 570, 955, t, LD) for t in (None, 1.5, 3.0)]
        best = max(c, key=lambda r: r["spans"]["2026H1"]["net"])         # H1-only pick of the target
        full = row(sim, name + "[pick]", w, 570, 955, best["tgt"], LD, full=True)
        full["all_targets_H1"] = {str(r["tgt"]): r["spans"]["2026H1"]["net"] for r in c}
        res["standalone"].append(full)
        # short side mirror (log only, direction picked on H1 too)
        ws = {s: -1 for s in w}
        c2 = [row(sim, name + "-short", ws, 570, 955, t, LD) for t in (None, 1.5, 3.0)]
        b2 = max(c2, key=lambda r: r["spans"]["2026H1"]["net"])
        f2 = row(sim, name + "-short[pick]", ws, 570, 955, b2["tgt"], LD, full=True)
        res["standalone"].append(f2)
    # ---- time of day / overnight (legal Globex form 18:00 -> 09:25), last hour, intraday drift
    allD = {s: 1 for s in sim.S}
    allS = {s: -1 for s in sim.S}
    def momentum(s):
        a, b = sim.B.px(s, 570), sim.B.px(s, 900)
        return None if a is None or b is None else (1 if b > a else -1)
    mom = {s: momentum(s) for s in sim.S if momentum(s)}
    fade = {s: -d for s, d in mom.items()}
    tod = {"globex_long_18:00-09:25": (allD, 1080, 565), "globex_short_18:00-09:25": (allS, 1080, 565),
           "intraday_long_09:30-15:55": (allD, 570, 955), "intraday_short_09:30-15:55": (allS, 570, 955),
           "lasthour_long_15:00-15:55": (allD, 900, 955), "lasthour_momentum_15:00-15:55": (mom, 900, 955),
           "lasthour_fade_15:00-15:55": (fade, 900, 955), "last30_momentum_15:25-15:55": (mom, 925, 955)}
    for name, (w, e, x) in tod.items():
        c = [row(sim, name, w, e, x, t, LD) for t in (None, 1.5, 3.0)]
        best = max(c, key=lambda r: r["spans"]["2026H1"]["net"])
        res["tod"].append(row(sim, name + "[pick]", w, e, x, best["tgt"], LD, full=True))
    # ---- pension month-end rebalancing: theta picked on H1
    cands = []
    for th in (2.0, 3.0, 5.0):
        w = pension(sim, th)
        for t in (None, 1.5, 3.0):
            cands.append((th, t, row(sim, f"pension_th{th}", w, 570, 955, t, LD)))
    thb, tb, _ = max(cands, key=lambda c: c[2]["spans"].get("2026H1", {"net": -1e9})["net"])
    wp = pension(sim, thb)
    res["pension"].append(row(sim, f"pension_th{thb}[pick]", wp, 570, 955, tb, LD, full=True))
    res["pension"].append({"all_theta_H1": {f"{th}/{t}": c.get("spans", {}).get("2026H1", {}).get("net") for th, t, c in cands}})
    # ---- (b) LIT size dials
    dials = dict(W)
    dials["pension"] = {s: 1 for s in wp}
    for name, w in dials.items():
        for f in (1.5, 0.5):
            res["dial"].append(dial_row(sim, name, set(w), f, LD, trades))
    res["notes"]["variants_logged"] = len(VARIANTS)
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


if __name__ == "__main__":
    r = main()
    print("variants logged:", r["notes"]["variants_logged"])
