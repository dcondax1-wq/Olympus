"""Stress test of the second strategies and account B before launch (owner 2026-10-22, "what else can we do before
launching this other strategy?"), like tools/lit_robust.py did for LIT: how much of the research money survives when the
world is a little worse than the backtest?

Strategies (paper, second_model.json): EMA = ema_lon_vix (tools/second_ema.py), MD = macd_sweep (tools/second_md.py),
SR = sr_nyreclaim (tools/second_sr.py); account B = all three on their own MFFU Builder 25K (the pick) and 50K with the
account-B executor of tools/second_account_b.py (need size = engine/account_b.qty, no hedge vs LIT, stuck rule).

Tests (each strategy re-run by its own research code; nothing re-tuned):
  base              the stored research trades (research/second/*_best.json); the clean re-run here must equal them
  noise1 / noise2   every 5m bar's open / high / low / close moved by a random -1..+1 / -2..+2 ticks (high / low widened to
                    keep the bar valid; MACD's 2026 1m execution bars too), every strategy re-run on the noisy bars
                    (50 seeded copies each; the same noisy bars for all three in one copy)
  slip03            random extra slippage 0-3 ticks on every MARKET fill (the entry and every stop / breakeven / cut / flat
                    exit; target limits get none), on top of the modelled 1 tick (200 seeded draws)
  miss10 / miss20   a random 10% / 20% of the trades never happen (200 seeded draws)
  late1 / late2     every entry 1 / 2 five-minute bars later (the next-next open), same structural stop, target rule re-applied
                    by the strategy's own simulator (a trade whose stop is already gone or out of 6-80 pts is skipped)
  worst             noise1 + slip 0-3 + miss 10% + late 1 together (50 seeded copies)
Per test and span (2026 H1 pick / H2 check / 2025 / 2021-24): each strategy alone at $500 risk ($, PF, % of the base $
kept) and account B (eval 2-week / 1-month pass / fail / stuck with a fresh eval every session, the back-to-back eval
path $ and PF) on the Builder 25K and 50K. Mean, p10 and p90 over the copies.

    python -X utf8 tools/second_robust.py             # full card -> research/second/robust.json (+ rl.save sb_robust_*)
    python -X utf8 tools/second_robust.py --quick     # 4 noisy copies, 20 draws (a check; nothing stored)
Needs research/runs/_cache/second_mix_units.pkl (python -X utf8 tools/second_mix.py units). Paper research only: changes no
engine default, no live_model*.json, no second_model.json.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "research", "second", "robust.json")
TICK = 0.25
NAMES = ("EMA", "MD", "SR")
SPANS = ("H1", "H2", "2025", "2021-24")
PLANS = ("builder25k", "builder50k")
VERSION = 1
MARKET_EXITS = {"STOP", "BE", "FLAT", "T15", "CUT", "stop", "be", "flat", "cut", "HEDGE", "PRE"}


# ================================================================================================ bars
_RAW = {}


def raw5():
    """data/NQ_5m.csv as read by tools/retail_standalone (EMA, S/R) + the engine.data junk-bar mask (MACD's lit.Market)."""
    if "df" not in _RAW:
        df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
        _RAW["df"] = df
        _RAW["junk"] = ((df["high"] == df["low"]) & (df["volume"] <= 0)).values
    return _RAW["df"], _RAW["junk"]


def _noisy(rng, k, o, h, l, c):
    """tools/lit_robust._noisy: each price moved by a random whole number of ticks in [-k, k]; high / low widened."""
    n = len(o)
    d = rng.integers(-k, k + 1, size=(4, n)) * TICK
    o2, h2, l2, c2 = o + d[0], h + d[1], l + d[2], c + d[3]
    h2 = np.maximum.reduce([h2, o2, c2])
    l2 = np.minimum.reduce([l2, o2, c2])
    return o2, h2, l2, c2


class World:
    """One copy of the market: 5m bars (clean or noisy) + MACD's 1m execution bars, and the delay (in 5m bars)."""

    def __init__(self, noise=0, seed=0, delay=0):
        self.noise, self.seed, self.delay = int(noise), int(seed), int(delay)
        df, junk = raw5()
        if self.noise:
            rng = np.random.default_rng(10_000 + self.seed)
            o, h, l, c = _noisy(rng, self.noise, df["open"].values, df["high"].values, df["low"].values, df["close"].values)
            df = df.assign(open=o, high=h, low=l, close=c)
            self.rng1 = rng
        else:
            self.rng1 = None
        self.df = df
        self.junk = junk


# ================================================================================================ the three strategies
def _cfg():
    return json.load(open(os.path.join(ROOT, "second_model.json"), encoding="utf-8"))["strategies"]


def run_ema(W):
    from tools import retail_standalone as RS
    from tools import second_ema as SE
    c = _cfg()["ema_lon_vix"]
    E, X = dict(c["entry"]), dict(c["exit"])
    RS.load_frame(W.df, live_cut=False)
    d = SE.load()
    df = SE.candidates()
    if W.delay:
        df = df.copy()
        ei = df["ei"].values + W.delay
        ok = ei < d["n"]
        ei = np.where(ok, ei, d["n"] - 1)
        ok &= d["sid"][ei] == d["sid"][df["sig"].values]
        ok &= d["mod"][ei] < 935
        dr = df["dir"].values
        e = d["o"][ei] * dr + TICK
        risk = e - df["stop"].values
        ok &= (risk >= SE.MIN_STOP) & (risk <= SE.MAX_STOP)
        df["ei"], df["e"], df["risk"] = ei, e, risk
        df = df[ok].sort_values(["ei", "dir"]).reset_index(drop=True)
        d["cand"] = df
    U = SE.trades_of(E, X)
    out = []
    for u in U:
        if SE.qty("usd500", u["risk_pts"]) <= 0:
            continue
        out.append({k: u[k] for k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit")} |
                   {"exit_kind": str(u["exit_kind"])})
    RS.D.clear()
    return out


def run_sr(W):
    from tools import retail_standalone as RS
    from tools import second_sr as SR
    key = dict(_cfg()["sr_nyreclaim"]["key"])
    RS.load_frame(W.df, live_cut=False)
    SR.D.clear()
    SR._OC.clear()
    d = SR.data()
    old_gen = SR.gen
    if W.delay:
        def gen(dd, setup, g, _k=W.delay):
            out = []
            for c in old_gen(dd, setup, g):
                sig, fill, dr, kind = c[0], c[1], c[2], c[3]
                if kind != 0 or fill >= 0:
                    out.append(c); continue
                k0 = sig + 1 + _k
                if k0 >= dd["n"] or dd["sid"][k0] != c[6]:
                    continue
                out.append((sig, k0) + tuple(c[2:]))
            return out
        SR.gen = gen
    try:
        T = SR.run_key(key)
        TT = SR.set_targets(SR.trades_of(T, "usd500", "nyreclaim"), key)
    finally:
        SR.gen = old_gen
    out = [{k: (float(u[k]) if k in ("entry", "stop", "exit") or (k == "target" and u[k] is not None) else u[k])
            for k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit")} | {"exit_kind": str(u["exit_kind"])}
           for u in TT if u["day"] >= "2021-11-01"]       # the stored research file starts 2021-11 (sr_best.json)
    SR.D.clear(); SR._OC.clear(); RS.D.clear()
    return out


_B1 = {}


def run_md(W):
    from engine import lit
    from engine.data import from_frame
    from tools import second_md as SM
    c = _cfg()["macd_sweep"]
    gen, sim, flt = dict(c["gen"]), dict(c["sim"]), dict(c["flt"])
    if W.noise:
        df = W.df[~W.junk]
        M = lit.Market(bars=from_frame("NQ", "5m", df))
        if "clean" not in _B1:
            _B1["clean"] = lit.bars_1m(lit.Market())
        X1 = _B1["clean"]
        o1, h1, l1, c1 = _noisy(W.rng1, W.noise, X1.o, X1.h, X1.l, X1.c)
        B1 = lit.XBars(X1.t, o1, h1, l1, c1, X1.mod, X1.day, X1.secs, X1.full)
    else:
        if "M" not in _B1:
            _B1["M"] = lit.Market()
            _B1["clean"] = lit.bars_1m(_B1["M"])
        M, B1 = _B1["M"], _B1["clean"]
    X = SM.Ctx(M, B1)
    C = SM.md_cands(X, **gen)
    if W.delay:
        C2 = []
        for z in C:
            j = z["j"] + W.delay
            if j + 1 >= X.n or X.day[j] != X.day[z["j"]]:
                continue
            C2.append({**z, "j": j})
        C = C2
    outs = [SM.sim_x(X, z, sim) for z in C]
    T = SM.greedy(X, C, outs, flt["kz"], flt["maxpd"], SM.md_filter(flt))
    out = []
    for z, r in T:
        q = SM.q_usd(500, r["risk"])
        if q <= 0:
            continue
        t = SM.tr_rec(X, z, r, q, "MACD-div")
        out.append({k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind")})
    return out


RUNNERS = {"EMA": run_ema, "MD": run_md, "SR": run_sr}
BEST = {"EMA": "ema_best.json", "MD": "md_best.json", "SR": "sr_best.json"}


def stored(name):
    d = json.load(open(os.path.join(ROOT, "research", "second", BEST[name]), encoding="utf-8"))
    return [{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind")} for t in d["trades"]]


def same(a, b):
    """Two trade lists equal (entry / exit time, direction, prices within 0.01)."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if (x["entry_t"], x["exit_t"], x["dir"], str(x["exit_kind"])) != (y["entry_t"], y["exit_t"], y["dir"], str(y["exit_kind"])):
            return False
        if any(abs(float(x[k]) - float(y[k])) > 0.011 for k in ("entry", "stop", "exit")):
            return False
    return True




# ================================================================================================ units + scoring
_BARS = {}


def _bars():
    if "b" not in _BARS:
        from tools import lit_final as F
        M, _ = F.market("cisd", [])
        _BARS["b"] = (F.bars(M, "5m"), F.bars(M, "1m"))
    return _BARS["b"]


def units_of(T, name):
    """tools/second_mix.second_units on a trade list (the path from the clean bars: worst open points, LIT pre-emption)."""
    B5, B1 = _bars()
    out = []
    for t in T:
        dr = int(t["dir"])
        e, s, x = float(t["entry"]), float(t["stop"]), float(t["exit"])
        risk = abs(e - s)
        if risk <= 0:
            continue
        pts = (x - e) * dr
        tgt = abs(float(t["target"]) - e) if t.get("target") is not None else 3.0 * risk
        B = B1 if int(t["entry_t"]) >= int(B1.t[0]) + 86400 else B5
        k0 = int(np.searchsorted(B.t, int(t["entry_t"]), side="right"))
        kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
        lo = B.l if dr == 1 else -B.h
        w = float(lo[k0:kx].min()) - e * dr if kx > k0 else 0.0
        w1 = max(-(risk + 0.25), min(0.0, w, pts))
        op = (B.o[k0:kx + 1] * dr - e * dr) if kx >= k0 else np.zeros(0)
        lw = np.minimum.accumulate(np.r_[0.0, lo[k0:kx] - e * dr]) if kx >= k0 else np.zeros(0)
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": dr, "exit": t["exit_kind"],
                    "risk": round(risk, 4), "tgt": round(tgt, 4), "pts": round(pts, 4), "w1": round(w1, 4), "src": name,
                    "pt": B.t[k0:kx + 1].astype(np.int64), "po": np.round(op, 2), "pw": np.maximum(np.round(lw, 2), -(risk + 0.25))})
    return out


def slip_units(U, rng, hi=3):
    """Extra slippage 0..hi ticks on every market fill: the entry, and the exit unless it is a target limit."""
    out = []
    for u in U:
        ticks = int(rng.integers(0, hi + 1)) + (int(rng.integers(0, hi + 1)) if str(u["exit"]) in MARKET_EXITS else 0)
        if ticks:
            u = {**u, "pts": round(u["pts"] - ticks * TICK, 4), "w1": round(min(u["w1"], u["pts"] - ticks * TICK), 4)}
        out.append(u)
    return out


def drop_units(U, rng, frac):
    keep = rng.random(len(U)) >= frac
    return [u for u, k in zip(U, keep) if k]


def _span_of(day):
    from tools import second_mix as MX
    for s, (a, z) in MX.SPANS.items():
        if a <= day <= z:
            return s
    return None


def alone(U, usd=500.0):
    """One strategy on its own at $usd risk: n, $, PF, win % per span ($1.90 a micro, max 40 micros)."""
    from tools import second_mix as MX
    o = {}
    for s in SPANS:
        p = []
        for u in U:
            if _span_of(u["day"]) != s:
                continue
            q = max(0, min(40, int(usd / (u["risk"] * MX.PV))))
            if q:
                p.append(q * (u["pts"] * MX.PV - MX.ECOMM))
        p = np.array(p) if p else np.zeros(0)
        gl = -p[p < 0].sum()
        o[s] = {"n": int(len(p)), "net": round(float(p.sum())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                "win": round(100.0 * float((p > 0).mean()), 1) if len(p) else None}
    return o


def acct(U_by_name, plan):
    """Account B (EMA + MD + SR, no hedge vs LIT) on a plan: fresh eval every session (2-week / 1-month pass / fail / stuck)
    and the back-to-back eval path $ / PF per span. tools/second_account_b executor and size (engine/account_b.qty need)."""
    from tools import second_mix as MX
    from tools import second_account_b as AB
    U = [u for nm in NAMES for u in U_by_name[nm]]
    U = MX.no_hedge(U)
    return acct_units(U, plan)


def acct_units(U, plan, rule="acctb_need"):
    from tools import second_mix as MX
    from tools import second_account_b as AB
    import collections
    by = MX.by_day(U)
    allS = MX.units()["sessions"]
    o = {}
    with AB.Plan(plan):
        for span in SPANS:
            a, z = MX.SPANS[span]
            S = [d for d in allS if a <= d <= z]
            res = [(AB.run_eval(S[i:i + 20], by, rule), len(S) - i) for i in range(len(S))]
            x = {}
            for lab, h in (("10", 10), ("20", 20)):
                R = [r for r, av in res if av >= h]
                N = len(R) or 1
                x["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
                x["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
                x["s" + lab] = round(100.0 * sum(1 for r in R if r[0] == "STUCK" and r[1] <= h) / N, 1)
            k, T, n = 0, [], collections.Counter()
            while k < len(S):
                r, used, _ = AB.run_eval(S[k:], by, rule, len(S) - k, keep=T)
                n[r] += 1
                if r == "OPEN":
                    break
                k += used
            p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
            gl = -p[p < 0].sum()
            eq = np.cumsum(p)
            x.update(n=len(T), net=round(float(p.sum())), pf=round(float(p[p > 0].sum() / gl), 2) if gl else None,
                     dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())),
                     evals=n["PASS"] + n["FAIL"] + n["STUCK"] + (1 if n["OPEN"] else 0), passes=n["PASS"])
            x["path"] = T if span in ("H1", "H2", "2025", "2021-24") else None
            o[span] = x
    return o


# ================================================================================================ the card
def tests(quick=False):
    nn, nd = (4, 20) if quick else (50, 200)
    return {"noise1": ("world", nn), "noise2": ("world", nn), "slip03": ("draw", nd), "miss10": ("draw", nd),
            "miss20": ("draw", nd), "late1": ("world", 1), "late2": ("world", 1), "worst": ("world", nn)}


LABELS = {"base": "Backtest as stored", "noise1": "Price noise +/-1 tick", "noise2": "Price noise +/-2 ticks",
          "slip03": "0-3 ticks extra slippage on market fills", "miss10": "10% of trades missed", "miss20": "20% of trades missed",
          "late1": "Entry 1 bar (5 min) late", "late2": "Entry 2 bars (10 min) late",
          "worst": "All at once: noise 1 + slip 0-3 + miss 10% + 1 bar late"}

_BASE_U = {}


def base_units():
    if "u" not in _BASE_U:
        _BASE_U["u"] = {nm: units_of(stored(nm), nm) for nm in NAMES}
    return _BASE_U["u"]


def one(job):
    """job = (test, seed) -> (test, seed, {"alone": {name: span table}, "acct": {plan: span table}}); the 25K path kept."""
    test, seed = job
    rng = np.random.default_rng([seed, sum(map(ord, test))])
    if test in ("noise1", "noise2", "late1", "late2", "worst"):
        W = World(noise={"noise1": 1, "noise2": 2, "worst": 1}.get(test, 0), seed=seed,
                  delay={"late1": 1, "late2": 2, "worst": 1}.get(test, 0))
        U = {nm: units_of(RUNNERS[nm](W), nm) for nm in NAMES}
    else:
        U = dict(base_units())
    if test in ("miss10", "worst"):
        U = {nm: drop_units(U[nm], rng, 0.10) for nm in NAMES}
    if test == "miss20":
        U = {nm: drop_units(U[nm], rng, 0.20) for nm in NAMES}
    out = {"alone": {}, "acct": {}}
    if test in ("slip03", "worst"):
        from tools import second_mix as MX
        Ub = slip_units(MX.no_hedge([u for nm in NAMES for u in U[nm]]), rng)     # slip after the no-hedge cut
        for nm in NAMES:
            out["alone"][nm] = alone(slip_units(U[nm], np.random.default_rng([seed, 99, NAMES.index(nm)])))
        for pl in PLANS:
            out["acct"][pl] = acct_units(Ub, pl)
    else:
        for nm in NAMES:
            out["alone"][nm] = alone(U[nm])
        for pl in PLANS:
            out["acct"][pl] = acct(U, pl)
    for pl in PLANS:
        for s in SPANS:
            P = out["acct"][pl][s].pop("path")
            if pl == "builder25k":
                out["acct"][pl][s]["_path"] = P
    return test, seed, out


def _q(xs, p):
    xs = [x for x in xs if x is not None]
    return None if not xs else round(float(np.percentile(xs, p)), 2)


def _m(xs):
    xs = [x for x in xs if x is not None]
    return None if not xs else round(float(np.mean(xs)), 2)


def agg(base, reps):
    o = {"copies": len(reps), "alone": {}, "acct": {}}
    for nm in NAMES:
        o["alone"][nm] = {}
        for s in SPANS:
            b = base["alone"][nm][s]["net"]
            nets = [r["alone"][nm][s]["net"] for r in reps]
            pfs = [r["alone"][nm][s]["pf"] for r in reps]
            o["alone"][nm][s] = {"net": _m(nets), "net_p10": _q(nets, 10), "net_p90": _q(nets, 90),
                                 "kept": round(100.0 * _m(nets) / b, 1) if b > 0 else None,
                                 "kept_p10": round(100.0 * _q(nets, 10) / b, 1) if b > 0 else None,
                                 "pf": _m(pfs), "pf_p10": _q(pfs, 10), "pf_p90": _q(pfs, 90),
                                 "n": _m([r["alone"][nm][s]["n"] for r in reps])}
    for pl in PLANS:
        o["acct"][pl] = {}
        for s in SPANS:
            b = base["acct"][pl][s]["net"]
            x = {}
            for k in ("p10", "f10", "s10", "p20", "f20", "s20", "net", "pf", "dd", "n"):
                v = [r["acct"][pl][s][k] for r in reps]
                x[k] = _m(v)
                if k in ("p10", "f10", "net", "pf"):
                    x[k + "_lo"], x[k + "_hi"] = _q(v, 10), _q(v, 90)
            x["kept"] = round(100.0 * x["net"] / b, 1) if b > 0 else None
            o["acct"][pl][s] = x
    return o


def median_copy(reps, pl="builder25k"):
    """The copy whose account-B H1 + H2 path $ is the median (stored as the run)."""
    v = [r["acct"][pl]["H1"]["net"] + r["acct"][pl]["H2"]["net"] for r in reps]
    return reps[int(np.argsort(v)[len(v) // 2])]


def main(quick=False, procs=4, save=True):
    import multiprocessing as mp
    t0 = time.time()
    from tools import second_mix as MX
    MX.units()
    _, _, base = one(("base", 0))
    clean = {nm: same(RUNNERS[nm](World()), stored(nm)) for nm in NAMES}
    print("clean re-run == stored trades:", clean, flush=True)
    T = tests(quick)
    jobs = [(t, s) for t, (kind, n) in T.items() for s in range(n)]
    R = {t: [] for t in T}
    with mp.get_context("fork").Pool(procs) as pool:
        for k, (t, s, o) in enumerate(pool.imap_unordered(one, jobs, chunksize=1)):
            R[t].append(o)
            if k % 25 == 0:
                print(f"  {k + 1}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
    card = {"version": VERSION, "built": time.strftime("%Y-%m-%d"), "quick": quick, "clean_equals_stored": clean,
            "labels": LABELS, "spans": list(SPANS), "plans": list(PLANS),
            "base": {"alone": base["alone"], "acct": {pl: {s: {k: v for k, v in base["acct"][pl][s].items() if not k.startswith("_")}
                                                           for s in SPANS} for pl in PLANS}},
            "tests": {t: agg(base, R[t]) for t in T}}
    card["seconds"] = round(time.time() - t0)
    show(card)
    if not quick:
        json.dump(card, open(OUT, "w"), indent=1, default=float)
        print("wrote", os.path.relpath(OUT, ROOT))
        if save:
            store(card, base, R)
    return card


def show(card):
    b = card["base"]
    for nm in NAMES:
        print(f"\n{nm} alone ($500 risk): base " + " | ".join(f"{s} {b['alone'][nm][s]['net']:+,} PF {b['alone'][nm][s]['pf']}" for s in SPANS))
        for t, o in card["tests"].items():
            a = o["alone"][nm]
            print(f"   {t:7s} " + " | ".join(f"{s} {a[s]['net']:+,.0f} ({a[s]['kept']}%) PF {a[s]['pf']}" for s in SPANS))
    for pl in PLANS:
        x = b["acct"][pl]
        print(f"\nAccount B {pl}: base " + " | ".join(f"{s} 2w {x[s]['p10']}/{x[s]['f10']}+{x[s]['s10']} ${x[s]['net']:+,}" for s in SPANS))
        for t, o in card["tests"].items():
            a = o["acct"][pl]
            print(f"   {t:7s} " + " | ".join(f"{s} 2w {a[s]['p10']}/{a[s]['f10']}+{a[s]['s10']} ${a[s]['net']:+,.0f} PF {a[s]['pf']}" for s in SPANS))


def store(card, base, R):
    from tools import runlib as rl
    from tools import second_mix as MX
    Q = "Owner 2026-10-22: what else can we do before launching the second strategies? Stress test of account B."
    sess = [d for d in MX.units()["sessions"] if d >= "2021-01-01"]
    for t in ["base"] + list(card["tests"]):
        rep = base if t == "base" else median_copy(R[t])
        P = []
        for s in SPANS:
            P += rep["acct"]["builder25k"][s]["_path"]
        T = [{"day": x["day"], "entry_t": x["entry_t"], "exit_t": x["exit_t"], "dir": x["dir"],
              "r": round(x["pnl"] / x["risk_usd"], 3) if x["risk_usd"] else 0.0, "pnl": x["pnl"], "risk_pts": x["risk"], "qty": x["qty"],
              "risk_usd": x["risk_usd"], "half": False, "exit": x["exit"], "trigger": x["src"], "mfe": None, "mae": None,
              "bars_held": None, "regime": "", "mult": None, "low": x["low"]} for x in P]
        A = (card["base"] if t == "base" else card["tests"][t])["acct"]["builder25k"]
        f = lambda s: f"2-week pass/fail/stuck {A[s]['p10']}/{A[s]['f10']}/{A[s]['s10']}, path {A[s]['net']:+,.0f} PF {A[s]['pf']}"
        rl.save(f"sb_robust_{t}", f"Account B stress test: {LABELS[t]} (Builder 25K, EMA + MACD + S/R)", "other", Q,
                params={"test": t, "accounts": list(NAMES), "plan": "builder25k", "size": "need", "no_hedge": True,
                        "copies": 1 if t == "base" else card["tests"][t]["copies"]},
                sizing={"plan": "builder25k", "size": "need"}, trades=T, scored=rl.score(T, sess),
                status="info", verdict=f"{LABELS[t]} (mean of the copies): H1 {f('H1')}; H2 {f('H2')}; 2025 {f('2025')}; "
                                       f"2021-24 {f('2021-24')}. Stored trades = the median copy's back-to-back eval path.",
                notes="tools/second_robust.py; full card (each strategy alone, both plans, p10/p90) in research/second/robust.json",
                writeup="second-prelaunch", tags=["second", "account_b", "robust"])
    print("saved sb_robust_*", flush=True)


if __name__ == "__main__":
    main(quick="--quick" in sys.argv)
