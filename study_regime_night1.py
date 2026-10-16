"""Regime / equity-curve governor study on REAL CME futures only (NQ = decision market, ES = robustness check).

    python study_regime_night1.py [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--boot 4000]

Nothing in engine/ is changed. Every rule is EMULATED by post-processing engine output:

  * sizing rules: the engine is run at full size in the trending regime (regime_mode "none"), then each trade is re-sized
    exactly as engine._size would (micros = floor(350 x grade_mult x m / (risk_pts_plan x micro_pv)), cap 40, auto mini/micro
    split, commission recomputed). A trade whose re-sized qty is 0 is dropped, as the engine would ("risk too small").
    Approximation: when the engine drops a trade it may take a different setup later that day; emulation cannot see that.
  * kill-switches: trades after the trigger are removed for the rest of the ISO week (exact: a bot that stands aside
    takes nothing).

Three samples per market:
  A  taken trades, default config (the real decision sample; ~29 on NQ)
  B  "wide" managed trades: same engine, max_trades_day 9, stop_after_win off (more real, fully managed trades)
  C  shadow candidates from the wide run: every valid setup, resolved stop/target/flat (no BE/giveback/time stop), in R

Validation: walk-forward over consecutive blocks of 10 sessions (~2 weeks). For each rule family the parameter is chosen on
the earlier folds (sample B, which has the most managed trades) and scored on the next fold; fixed pre-registered
parameters are also shown fold by fold. Lifts carry day-block bootstrap 90% CIs. Dates filter trades post-run (warm-up kept),
so the script re-runs unchanged on a longer history.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
from collections import defaultdict
from multiprocessing import Pool
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from engine import backtest
from engine.data import load, DATA_DIR
from engine.instruments import INSTRUMENTS

ET = ZoneInfo("America/New_York")
FLAT = {"dd_aware": False, "daily_max_loss": 1e9}
FULL = {**FLAT, "regime_mode": "none"}
WIDE = {**FULL, "max_trades_day": 9, "stop_after_win": False}
GRADE_MULT = {"A+": 1.5, "A": 1.25, "B": 1.0, "C": 0.75, "D": 0.5}
RISK = 350.0
MARKETS = ("NQ", "ES")
FOLD_DAYS = 10


# ----------------------------------------------------------------------------------------------- engine runs
def _job(job):
    sym, kind = job
    if kind == "default":
        r = backtest.run(sym, "5m", FLAT, light=True)
        return sym, kind, {"trades": r["trades"], "days": r["days"]}
    if kind == "full":
        r = backtest.run(sym, "5m", FULL, light=True)
        return sym, kind, {"trades": r["trades"], "days": r["days"]}
    r = backtest.run(sym, "5m", WIDE, light=False)
    return sym, kind, {"trades": r["trades"], "days": r["days"], "shadows": r["shadows"]}


# ----------------------------------------------------------------------------------------------- regime features
class Feat:
    """Regime measures computed from real futures bars, using only information available at entry time."""

    def __init__(self, sym):
        d1 = pd.read_csv(f"{DATA_DIR}/{sym}_1d.csv")
        d1["date"] = pd.to_datetime(d1["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d")
        self.d_date = d1["date"].tolist()
        self.d_c, self.d_h, self.d_l = d1["close"].values, d1["high"].values, d1["low"].values
        h1 = load(sym, "1h")
        self.h_t = h1.t
        self.adx = self._adx(h1.h, h1.l, h1.c, 14)
        self.b = load(sym, "5m")
        self.day_idx = defaultdict(list)
        for k, ds in enumerate(self.b.date_str):
            self.day_idx[ds].append(k)
        self.rth_close = {}
        for ds, ks in self.day_idx.items():
            rth = [k for k in ks if 570 <= self.b.mod[k] < 960]
            if rth:
                self.rth_close[ds] = float(self.b.c[rth[-1]])
        self.days_sorted = sorted(self.day_idx)

    @staticmethod
    def _adx(h, l, c, n):
        up, dn = np.diff(h, prepend=h[0]), -np.diff(l, prepend=l[0])
        pdm = np.where((up > dn) & (up > 0), up, 0.0)
        mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
        tr = np.maximum.reduce([h - l, np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])])
        a = 1.0 / n
        def wild(x):
            out = np.empty_like(x); s = x[0]
            for i, v in enumerate(x):
                s = s + a * (v - s); out[i] = s
            return out
        atr, pp, mm = wild(tr), wild(pdm), wild(mdm)
        pdi, mdi = 100 * pp / np.maximum(atr, 1e-9), 100 * mm / np.maximum(atr, 1e-9)
        dx = 100 * np.abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-9)
        adx = wild(dx)
        adx[: 3 * n] = np.nan
        return adx

    def daily(self, day):
        k = int(np.searchsorted(np.array(self.d_date), day))   # bars strictly before `day`
        c = self.d_c[:k]
        out = {}
        def er(n):
            if len(c) < n + 1:
                return None
            seg = c[-(n + 1):]
            path = np.abs(np.diff(seg)).sum()
            return float(abs(seg[-1] - seg[0]) / path) if path else None
        out["er3"], out["er5"], out["er10"] = er(3), er(5), er(10)
        out["dir5"] = int(np.sign(c[-1] - c[-6])) if len(c) >= 6 else 0
        out["dir3"] = int(np.sign(c[-1] - c[-4])) if len(c) >= 4 else 0
        rng = self.d_h[:k] - self.d_l[:k]
        out["adr20"] = float(np.mean(rng[-20:])) if len(rng) >= 20 else None
        return out

    def at(self, day, entry_t, d):
        f = self.daily(day)
        j = int(np.searchsorted(self.h_t, entry_t - 3600, side="right")) - 1     # last 1h bar fully closed
        f["adx1h"] = float(self.adx[j]) if j >= 0 and not math.isnan(self.adx[j]) else None
        ks = self.day_idx.get(day, [])
        b = self.b
        od = [k for k in ks if 570 <= b.mod[k] < 630 and b.t[k] + 300 <= entry_t]
        f["od_er"] = f["od_dir"] = None
        if len(od) >= 3:
            seq = np.r_[b.o[od[0]], b.c[od]]
            path = np.abs(np.diff(seq)).sum()
            f["od_er"] = float(abs(seq[-1] - seq[0]) / path) if path else None
            f["od_dir"] = int(np.sign(seq[-1] - seq[0]))
        ib = [k for k in ks if 570 <= b.mod[k] < 630]
        f["ib_one"] = f["ib_dir"] = None
        if len(ib) >= 10 and entry_t >= b.t[ib[-1]] + 300:
            ibh, ibl = b.h[ib].max(), b.l[ib].min()
            aft = [k for k in ks if b.mod[k] >= 630 and b.t[k] + 300 <= entry_t]
            hi = bool(aft) and b.h[aft].max() > ibh
            lo = bool(aft) and b.l[aft].min() < ibl
            f["ib_one"] = int(hi != lo)
            f["ib_dir"] = 1 if (hi and not lo) else (-1 if (lo and not hi) else 0)
        f["gap_adr"] = None
        di = self.days_sorted.index(day) if day in self.day_idx else -1
        rth0 = next((k for k in ks if b.mod[k] >= 570), None)
        if di > 0 and rth0 is not None and f["adr20"]:
            pc = self.rth_close.get(self.days_sorted[di - 1])
            if pc:
                f["gap_adr"] = abs(float(b.o[rth0]) - pc) / f["adr20"]
        f["dir"] = d
        return f


# ----------------------------------------------------------------------------------------------- sizing emulation
def resize(t, m, spec):
    """Re-size a full-size trade by multiplier m exactly like engine._size. Returns new pnl $ or None (skipped)."""
    if m >= 0.999 and m <= 1.001:
        return t["pnl"]
    risk_usd = RISK * t["grade_mult"] * m
    micros = min(int(risk_usd // (t["risk_pts_plan"] * spec["micro_pv"])), 40)
    if micros < 1:
        return None
    q0 = t["qty"]
    gross = t["gross"] / q0 * micros
    minis, rem = micros // 10, micros % 10
    return round(gross - (minis * spec["mini_comm_rt"] + rem * spec["micro_comm_rt"]), 2)


def cur_rule(t):
    """Today's engine rule: half size when the engine's 10-day efficiency > 0.45 (regime flag stored on the trade)."""
    return 0.5 if t.get("regime") == "trending" else 1.0


# size modifiers: name -> (fn(features) -> trending?)  (a modifier returns True when it wants 0.5x)
def thr(key, x, ge=True):
    return lambda f: f.get(key) is not None and (f[key] >= x if ge else f[key] > x)


MODS = {
    "er10d>0.45": thr("er10", 0.45, False),
    "er5>=0.5": thr("er5", 0.5), "er5>=0.6": thr("er5", 0.6), "er5>=0.4": thr("er5", 0.4),
    "er3>=0.6": thr("er3", 0.6), "er3>=0.7": thr("er3", 0.7), "er3>=0.8": thr("er3", 0.8),
    "adx1h>=20": thr("adx1h", 20), "adx1h>=25": thr("adx1h", 25), "adx1h>=30": thr("adx1h", 30),
    "od_er>=0.4": thr("od_er", 0.4), "od_er>=0.5": thr("od_er", 0.5), "od_er>=0.6": thr("od_er", 0.6),
    "ib_one_sided": lambda f: f.get("ib_one") == 1,
    "gap>=0.35adr": thr("gap_adr", 0.35), "gap>=0.5adr": thr("gap_adr", 0.5),
    # direction-aware: only trades AGAINST the 5-day direction are halved
    "er5>=0.5 & against5": lambda f: thr("er5", 0.5)(f) and f["dir5"] == -f["dir"],
    "er5>=0.4 & against5": lambda f: thr("er5", 0.4)(f) and f["dir5"] == -f["dir"],
    "er10d>0.45 & against5": lambda f: thr("er10", 0.45, False)(f) and f["dir5"] == -f["dir"],
    "er3>=0.6 & against3": lambda f: thr("er3", 0.6)(f) and f["dir3"] == -f["dir"],
    "od_er>=0.5 & against_od": lambda f: thr("od_er", 0.5)(f) and f["od_dir"] == -f["dir"],
    "ib_one & against_ib": lambda f: f.get("ib_one") == 1 and f["ib_dir"] == -f["dir"],
}
FAMILIES = {"er5": ["er5>=0.4", "er5>=0.5", "er5>=0.6"], "er3": ["er3>=0.6", "er3>=0.7", "er3>=0.8"],
            "adx1h": ["adx1h>=20", "adx1h>=25", "adx1h>=30"], "od_er": ["od_er>=0.4", "od_er>=0.5", "od_er>=0.6"],
            "gap": ["gap>=0.35adr", "gap>=0.5adr"]}


def governor(trs, n_runs, cut, mode="runner"):
    """Sizing multiplier per trade from the closed-trade history only.
    runner: after n consecutive closed trades without a +2R close or TARGET, size x cut until one appears.
    exp10:  size x cut while the mean R of the last 10 closed trades is < 0."""
    out, closed = [], []
    for t in trs:
        done = [c for c in closed if c["exit_t"] <= t["entry_t"]]
        m = 1.0
        if mode == "runner":
            k = 0
            for c in reversed(done):
                if c["pnl_r"] >= 2 or c["exit_reason"] == "TARGET":
                    break
                k += 1
            if k >= n_runs:
                m = cut
        else:
            last = [c["pnl_r"] for c in done[-10:]]
            if len(last) >= 10 and np.mean(last) < 0:
                m = cut
        out.append(m)
        closed.append(t)
    return out


def killswitch(trs, pnl, kind):
    """Return a keep-mask. week2R: stop for the ISO week once the week's net <= -2R ($700).
    loss3: stop for the week after 3 losing trades in a row. stop3: after 3 full STOP exits in a row."""
    keep, wk_net, wk_off, streak, cur_wk = [], 0.0, False, 0, None
    for t, p in zip(trs, pnl):
        w = dt.date.fromisoformat(t["day"]).isocalendar()[:2]
        if w != cur_wk:
            cur_wk, wk_net, wk_off, streak = w, 0.0, False, 0 if kind == "week2R" else streak
        if wk_off:
            keep.append(False); continue
        keep.append(True)
        wk_net += p
        if kind == "week2R" and wk_net <= -2 * RISK:
            wk_off = True
        elif kind in ("loss3", "stop3"):
            bad = (p < 0) if kind == "loss3" else (t["exit_reason"] == "STOP")
            streak = streak + 1 if bad else 0
            if streak >= 3:
                wk_off, streak = True, 0
    return keep


# ----------------------------------------------------------------------------------------------- metrics
def metrics(pnl, ndays):
    pnl = np.array([p for p in pnl if p is not None], dtype=float)
    if not len(pnl):
        return dict(n=0, tpw=0.0, net=0.0, pf=0.0, dd=0.0)
    g, l = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
    return dict(n=len(pnl), tpw=len(pnl) / (ndays / 5.0), net=float(pnl.sum()), pf=float(g / l) if l else 99.0, dd=dd)


def boot_ci(day_delta, n_boot, rng):
    """Day-block bootstrap of the summed lift. day_delta: per-day lift (all sessions, zeros included)."""
    x = np.asarray(day_delta, dtype=float)
    if not len(x):
        return (0.0, 0.0, 0.0)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    s = x[idx].sum(1)
    return (float(np.percentile(s, 5)), float(np.percentile(s, 95)), float((s > 0).mean()))


def per_day(trs, vals, days):
    d = defaultdict(float)
    for t, v in zip(trs, vals):
        if v is not None:
            d[t["day"]] += v
    return [d.get(x, 0.0) for x in days]


def folds_of(days):
    return [days[i:i + FOLD_DAYS] for i in range(0, len(days), FOLD_DAYS) if len(days[i:i + FOLD_DAYS]) >= 5]


def fold_sums(trs, vals, folds):
    out = []
    for fd in folds:
        s = set(fd)
        out.append(sum(v for t, v in zip(trs, vals) if v is not None and t["day"] in s))
    return out


# ----------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="a", default=None)
    ap.add_argument("--to", dest="z", default=None)
    ap.add_argument("--boot", type=int, default=4000)
    args = ap.parse_args()
    rng = np.random.default_rng(7)
    inr = lambda d: (not args.a or d >= args.a) and (not args.z or d <= args.z)

    jobs = [(s, k) for s in MARKETS for k in ("default", "full", "wide")]
    with Pool(min(6, len(jobs))) as pool:
        res = {(s, k): v for s, k, v in pool.map(_job, jobs)}

    report = {}
    for sym in MARKETS:
        spec = INSTRUMENTS[sym]
        F = Feat(sym)
        days = sorted(d["date"] for d in res[(sym, "full")]["days"] if inr(d["date"]))
        folds = folds_of(days)
        S = {}
        for key in ("default", "full", "wide"):
            trs = sorted([t for t in res[(sym, key)]["trades"] if inr(t["day"])], key=lambda t: t["entry_t"])
            for t in trs:
                t["F"] = F.at(t["day"], t["entry_t"], t["dir"])
            S[key] = trs
        shadows = []
        for s in res[(sym, "wide")]["shadows"]:
            if s.get("r") is None or not inr(s["day"]):
                continue
            s = dict(s)
            s["F"] = F.at(s["day"], s["t"] + 300, s["dir"])
            s["gm"] = GRADE_MULT.get(s.get("grade"), 1.0)
            s["cur"] = 0.5 if (s["f"].get("rg_er10") is not None and s["f"]["rg_er10"] > 0.45) else 1.0
            shadows.append(s)
        S["shadow"] = shadows

        R = {"days": days, "folds": [(f[0], f[-1]) for f in folds], "n_days": len(days)}
        eng = metrics([t["pnl"] for t in S["default"]], len(days))
        R["engine_default"] = eng

        def variant_pnl(trs, mfun, keep_cur):
            """$ per trade under multiplier mfun(t) (x current rule if keep_cur)."""
            out = []
            for t, m in zip(trs, mfun(trs)):
                mm = m * (cur_rule(t) if keep_cur else 1.0)
                out.append(resize(t, mm, spec))
            return out

        def shadow_r(mfun_f, keep_cur):
            return [s["r"] * s["gm"] * (0.5 if mfun_f and mfun_f(s["F"]) else 1.0) * (s["cur"] if keep_cur else 1.0)
                    for s in shadows]

        variants = {}
        # baseline (emulated current rule) and "no regime rule"
        base_fn = lambda trs: [1.0] * len(trs)
        variants["CURRENT (er10>0.45 half)"] = (base_fn, True, None)
        variants["no regime rule (full size)"] = (base_fn, False, None)
        for name, fn in MODS.items():
            mk = (lambda fn: (lambda trs: [0.5 if fn(t["F"]) else 1.0 for t in trs]))(fn)
            variants[f"{name} (replaces er10)"] = (mk, False, fn)
            variants[f"{name} + er10"] = (mk, True, fn)
        for n in (4, 5, 6):
            for cut in (0.5, 0.25):
                g = (lambda n, cut: (lambda trs: governor(trs, n, cut)))(n, cut)
                variants[f"gov no-runner N{n} x{cut} + er10"] = (g, True, None)
                variants[f"gov no-runner N{n} x{cut} (replaces er10)"] = (g, False, None)
        variants["gov exp10<0 x0.5 + er10"] = (lambda trs: governor(trs, 0, 0.5, "exp10"), True, None)
        variants["gov exp10<0 x0.5 (replaces er10)"] = (lambda trs: governor(trs, 0, 0.5, "exp10"), False, None)
        for gname, n in (("N5", 5), ("N4", 4)):
            for mname in ("er5>=0.5", "adx1h>=25", "od_er>=0.5", "er5>=0.5 & against5"):
                fn = MODS[mname]
                g = (lambda n, fn: (lambda trs: [a * (0.5 if fn(t["F"]) else 1.0) for a, t in zip(governor(trs, n, 0.5), trs)]))(n, fn)
                variants[f"gov {gname} x0.5 + {mname} (replaces er10)"] = (g, False, fn)

        out_rows = {}
        base_vals = {k: variant_pnl(S[k], base_fn, True) for k in ("full", "wide")}
        base_sh = shadow_r(None, True)
        for vname, (mfun, keep_cur, ffn) in variants.items():
            row = {}
            for k in ("full", "wide"):
                vals = variant_pnl(S[k], mfun, keep_cur)
                row[k] = metrics(vals, len(days))
                delta = [(v or 0.0) - (b or 0.0) for v, b in zip(vals, base_vals[k])]
                row[k + "_delta"] = sum(delta)
                row[k + "_ci"] = boot_ci(per_day(S[k], delta, days), args.boot, rng)
                row[k + "_folds"] = fold_sums(S[k], delta, folds)
                row[k + "_lostn"] = sum(1 for v, b in zip(vals, base_vals[k]) if v is None and b is not None)
            if ffn is not None or mfun is base_fn:
                sv = shadow_r(ffn, keep_cur)
                d = [a - b for a, b in zip(sv, base_sh)]
                row["shadow_delta"] = sum(d)
                row["shadow_ci"] = boot_ci(per_day(shadows, d, days), args.boot, rng)
                row["shadow_folds"] = fold_sums(shadows, d, folds)
            out_rows[vname] = row
        R["rows"] = out_rows
        R["n"] = {k: len(S[k]) for k in S}

        # walk-forward family selection: choose threshold on earlier folds (sample B $ lift), score next fold (A and B)
        wf = {}
        fams = {**{f"{k} (replaces er10)": [f"{x} (replaces er10)" for x in v] for k, v in FAMILIES.items()},
                **{f"{k} + er10": [f"{x} + er10" for x in v] for k, v in FAMILIES.items()},
                "gov no-runner + er10": [f"gov no-runner N{n} x{c} + er10" for n in (4, 5, 6) for c in (0.5, 0.25)]}
        for fam, members in fams.items():
            test_a, test_b, picks = [], [], []
            for k in range(1, len(folds)):
                score = {m: sum(out_rows[m]["wide_folds"][:k]) for m in members}
                best = max(score, key=score.get)
                if score[best] <= 0:
                    best = None                       # nothing helped in-sample: stay at baseline
                picks.append(best or "baseline")
                test_a.append(out_rows[best]["full_folds"][k] if best else 0.0)
                test_b.append(out_rows[best]["wide_folds"][k] if best else 0.0)
            wf[fam] = {"picks": picks, "test_a": test_a, "test_b": test_b}
        R["wf"] = wf

        # kill-switches (remove trades) on top of the current rule
        ks = {}
        for k in ("full", "wide"):
            for kind in ("week2R", "loss3", "stop3"):
                vals = base_vals[k]
                mask = killswitch(S[k], [v if v is not None else 0.0 for v in vals], kind)
                kept = [v if m else None for v, m in zip(vals, mask)]
                delta = [(a or 0.0) - (b or 0.0) for a, b in zip(kept, vals)]
                ks[(k, kind)] = {"m": metrics(kept, len(days)), "delta": sum(delta),
                                 "ci": boot_ci(per_day(S[k], delta, days), args.boot, rng),
                                 "folds": fold_sums(S[k], delta, folds)}
        R["ks"] = ks

        # diagnostics: how often each modifier fires on taken trades, and the R of trades it flags vs not
        diag = {}
        for name, fn in {**MODS, "CURRENT er10 (engine)": None}.items():
            if fn is None:
                fl = [t for t in S["full"] if t.get("regime") == "trending"]
                nf = [t for t in S["full"] if t.get("regime") != "trending"]
                fs = [s for s in shadows if s["cur"] < 1]
                ns = [s for s in shadows if s["cur"] == 1]
            else:
                fl = [t for t in S["full"] if fn(t["F"])]
                nf = [t for t in S["full"] if not fn(t["F"])]
                fs = [s for s in shadows if fn(s["F"])]
                ns = [s for s in shadows if not fn(s["F"])]
            mr = lambda xs, k: (float(np.mean([x[k] for x in xs])) if xs else float("nan"))
            diag[name] = (len(fl), mr(fl, "pnl_r"), len(nf), mr(nf, "pnl_r"), len(fs), mr(fs, "r"), len(ns), mr(ns, "r"))
        R["diag"] = diag
        # sanity: emulated current vs engine default
        R["emu_check"] = (metrics(base_vals["full"], len(days)), eng)
        report[sym] = R
    write(report, args)


# ----------------------------------------------------------------------------------------------- output
def fm(m):
    return f"{m['n']} / {m['tpw']:.1f} / {m['net']:+,.0f} / {min(m['pf'], 99):.2f} / {m['dd']:,.0f}"


def fci(ci):
    return f"[{ci[0]:+,.0f}, {ci[1]:+,.0f}] p+={ci[2]:.2f}"


def write(report, args):
    L = []
    P = L.append
    P(f"# study_regime_night1 output (range {args.a or 'start'} .. {args.z or 'end'})\n")
    for sym, R in report.items():
        P(f"\n## {sym}  ({R['n_days']} sessions; samples: A taken={R['n']['full']} (engine default {R['engine_default']['n']}), "
          f"B wide={R['n']['wide']}, C shadows={R['n']['shadow']})")
        P(f"folds: {', '.join(f'{a}..{b}' for a, b in R['folds'])}")
        emu, eng = R["emu_check"]
        P(f"emulation check, current rule: emulated {fm(emu)}  vs engine {fm(eng)}  (n / tpw / net / PF / DD)\n")
        P("### Sizing variants  (A = default taken trades $, B = wide managed trades $, C = shadows R x grade)")
        P("| variant | A: n / t/wk / net / PF / DD | A lift $ | A 90% CI | A lift by fold | B lift $ | B 90% CI | B by fold | C lift R | C 90% CI |")
        P("|---|---|---|---|---|---|---|---|---|---|")
        for v, r in R["rows"].items():
            c = f"{r['shadow_delta']:+.1f} | {fci(r['shadow_ci'])}" if "shadow_delta" in r else "- | -"
            lost = f" (-{r['full_lostn']} skipped)" if r["full_lostn"] else ""
            P(f"| {v} | {fm(r['full'])}{lost} | {r['full_delta']:+,.0f} | {fci(r['full_ci'])} | "
              f"{' '.join(f'{x:+.0f}' for x in r['full_folds'])} | {r['wide_delta']:+,.0f} | {fci(r['wide_ci'])} | "
              f"{' '.join(f'{x:+.0f}' for x in r['wide_folds'])} | {c} |")
        P("\n### Walk-forward (threshold picked on earlier folds of B, scored on the next fold)")
        P("| family | picks per test fold | A test-fold lift $ | A total | B test-fold lift $ | B total |")
        P("|---|---|---|---|---|---|")
        for fam, w in R["wf"].items():
            P(f"| {fam} | {', '.join(w['picks'])} | {' '.join(f'{x:+.0f}' for x in w['test_a'])} | {sum(w['test_a']):+,.0f} | "
              f"{' '.join(f'{x:+.0f}' for x in w['test_b'])} | {sum(w['test_b']):+,.0f} |")
        P("\n### Kill-switches (rest of ISO week off; on top of the current rule)")
        P("| rule | sample | n / t/wk / net / PF / DD | lift $ | 90% CI | by fold |")
        P("|---|---|---|---|---|---|")
        for (k, kind), x in R["ks"].items():
            P(f"| {kind} | {'A' if k == 'full' else 'B'} | {fm(x['m'])} | {x['delta']:+,.0f} | {fci(x['ci'])} | "
              f"{' '.join(f'{v:+.0f}' for v in x['folds'])} |")
        P("\n### Diagnostics: trades flagged 'trending' by each measure (A taken, C shadows): n, mean R")
        P("| measure | A flagged n | A flagged R | A other n | A other R | C flagged n | C flagged R | C other n | C other R |")
        P("|---|---|---|---|---|---|---|---|---|")
        for name, d in R["diag"].items():
            P(f"| {name} | {d[0]} | {d[1]:+.2f} | {d[2]} | {d[3]:+.2f} | {d[4]} | {d[5]:+.2f} | {d[6]} | {d[7]:+.2f} |")
    print("\n".join(L))


if __name__ == "__main__":
    main()
