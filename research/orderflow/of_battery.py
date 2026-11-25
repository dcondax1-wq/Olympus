"""Order-flow battery (day-ofready 2026-11-24): runs OF1-OF6 of research/orderflow/DESIGN.md (frozen, commit bc2e5e68f) the
moment >= 40 NQ tick days are available. Paper research only: nothing here trades, arms or edits a live setting.

Input = the PC's per-day order-flow summaries (engine/ofsum.py): `days/<day>/of/NQ_*` under one of
    data/pc_days/            (the cloud: tools/data_pull.py unpacks the PC's answers here)
    logs/datapipe/days/      (the PC: where engine.ofsum build writes)
    --ticks                  (the PC: summarize data/ticks on the fly)
    python -X utf8 research/orderflow/of_battery.py [--src DIR] [--ticks] [--force] [--final]
    python -X utf8 research/orderflow/of_battery.py --selftest      # synthetic days end to end + parity with of_study.prereg
Writes research/orderflow/battery_results.json (+ one row per look in battery_looks.json). Exit 0 always ("waiting" < 40 days).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import importlib.util
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine import ofsum                                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "battery_results.json")
LOOKS = os.path.join(HERE, "battery_looks.json")
ET = ZoneInfo("America/New_York")
TICK = 0.25
# frozen (DESIGN.md / PREREG_ticks.md)
ZONE, ABS_SHARE, BLOCK_PCT, BLOCK_DAYS = 8, 0.20, 99.5, 5
MIN_DAYS, MIN_ROWS, FLOOR = 40, 50_000, 8
LOOK_AT = (40, 60, 120, 250)            # day-ofmax: + 250 (DESIGN.md note 2026-11-25); a PASS must hold at every later look
OF5_S, OF6_G = (0.20, 0.35), (6, 12)
ATLAS_USD = 250.0
N_PLACEBO = 3000


def _mod(path, name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


S = _mod("of_study.py", "of_study")          # _sim_df, constants
P = _mod("of_program.py", "of_program")      # lvns


# ------------------------------------------------------------------------------------------------ data
class Day:
    def __init__(self, day, R):
        self.day, self.meta = day, R["meta"]
        b = R["bars"].copy()
        et = pd.to_datetime(b.t, unit="s", utc=True).dt.tz_convert(ET)
        b["mod"] = et.dt.hour * 60 + et.dt.minute
        b["delta"] = b.buy - b.sell
        b = b.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "vol": "volume"})
        self.bars = b.reset_index(drop=True)
        self.fp = R["fp"]
        self.depth = R.get("depth")                                     # day-ofmax: per-5m depth summary (None before depth)
        self.row_of_t = {int(t): i for i, t in enumerate(b.t)}
        self.fp_by_bar = {int(k): g for k, g in self.fp.groupby("bar")}

    def zone(self, t_bar, d):
        """OF1 zone at the bar starting t_bar: (vz, dz) within ZONE ticks of the bar's tick extreme (low for d=+1)."""
        i = self.row_of_t.get(int(t_bar))
        if i is None or i not in self.fp_by_bar:
            return None
        g = self.fp_by_bar[i]
        if int(self.bars.at[i, "n"]) < 20:                                # as prereg: a bar with < 20 trades is skipped
            return None
        kmax = int(round((self.bars.at[i, "high"] - self.bars.at[i, "low"]) / TICK))
        z = g[g.k <= ZONE] if d == 1 else g[g.k >= kmax - ZONE]
        vz = float((z.a + z.b + z.u).sum()); dz = float((z.a - z.b).sum())
        return vz, dz

    def block_signed(self, t_a, t_b):
        """OF2: signed volume of single trades >= the day's frozen block threshold, bars [t_a, t_b) (bth, built on the PC)."""
        b = self.bars
        w = b[(b.t >= t_a) & (b.t < t_b)]
        return float(pd.to_numeric(w["bth"], errors="coerce").fillna(0).sum())

    def rth(self):
        r = self.bars[(self.bars["mod"] >= 570) & (self.bars["mod"] < 960)].reset_index(drop=True)
        return r

    def rth_profile(self):
        """prior-day profile input: (price, volume) of every RTH footprint cell."""
        rows = self.bars.index[(self.bars["mod"] >= 570) & (self.bars["mod"] < 960)]
        if not len(rows):
            return None
        f = self.fp[self.fp.bar.isin(rows)]
        px = self.bars.low.to_numpy()[f.bar.to_numpy()] + f.k.to_numpy() * TICK
        return px, (f.a + f.b + f.u).to_numpy(float)


def find_days(src=None, ticks=False):
    if ticks:
        from engine import tickrec
        out, metas = {}, {}
        for d in tickrec.days_available():                                 # oldest first: block_th sees the prior days
            x = tickrec.read_day(d)
            files = ofsum.summarize(x, d, ofsum.block_threshold(d, metas=metas)) if x is not None else {}
            if files:
                out[d] = _from_bytes(files)
                metas[d] = out[d]["meta"]
        return out
    dirs = [src] if src else [os.path.join(ROOT, "data", "pc_days"), os.path.join(ROOT, "logs", "datapipe", "days")]
    out = {}
    for base in dirs:
        for m in sorted(glob.glob(os.path.join(base, "*", "of", "NQ_meta.json"))):
            d = os.path.basename(os.path.dirname(os.path.dirname(m)))
            if d not in out:
                R = ofsum.read(os.path.dirname(os.path.dirname(m)))
                if R:
                    out[d] = R
    return out


def _from_bytes(files):
    import io
    return {"bars": pd.read_csv(io.BytesIO(files["NQ_bars5m.csv.gz"]), compression="gzip"),
            "fp": pd.read_csv(io.BytesIO(files["NQ_fp5m.csv.gz"]), compression="gzip"),
            "meta": json.loads(files["NQ_meta.json"])}


# ------------------------------------------------------------------------------------------------ scoring helpers
def halves(days):
    n = len(days)
    k = (n + 1) // 2
    return {"Discovery": days[:k], "Confirm": days[k:]}


def srow(pnls, n_days):
    p = np.array(pnls, float)
    w, l = p[p > 0].sum(), -p[p <= 0].sum()
    return {"n": int(len(p)), "per_wk": round(len(p) / max(1, n_days) * 5, 2), "net$": round(float(p.sum())),
            "pf": round(float(w / l), 2) if l > 0 else None, "win%": round(100 * float((p > 0).mean()), 1) if len(p) else None}


def filter_report(rows, keep, H, rng):
    """rows: [{day, pnl}], keep: [bool]. Gain of skipping per half + pooled skip placebo."""
    res, ok, few = {}, True, False
    for nm, ds in H.items():
        s = set(ds)
        R = [(r["pnl"], k) for r, k in zip(rows, keep) if r["day"] in s]
        allp = [p for p, _ in R]; kp = [p for p, k in R if k]
        res[nm] = {"all": srow(allp, len(ds)), "kept": srow(kp, len(ds)), "gain$": round(sum(kp) - sum(allp))}
        if len(R) < FLOOR:
            few = True
        ok = ok and res[nm]["gain$"] > 0 and len(kp) >= 0.5 * len(R)
    p = np.array([r["pnl"] for r in rows], float); k = np.array(keep, bool)
    nskip = int((~k).sum())
    obs = -p[~k].sum()
    if len(p) and nskip:
        ge = sum(-p[rng.choice(len(p), nskip, replace=False)].sum() >= obs for _ in range(N_PLACEBO))
        res["skip_placebo_p"] = round((ge + 1) / (N_PLACEBO + 1), 3)
    else:
        res["skip_placebo_p"] = None
    ok = ok and (res["skip_placebo_p"] or 1) < 0.10
    res["skipped"] = nskip
    res["verdict"] = "TOO FEW" if few else ("PASS (candidate)" if ok else "REJECTED")
    return res


def standalone_report(sig, H, rng):
    """sig: [(day, pnl, flip_pnl)]."""
    res, ok, few = {}, True, False
    for nm, ds in H.items():
        s = set(ds)
        R = [x for x in sig if x[0] in s]
        res[nm] = srow([x[1] for x in R], len(ds))
        if len(R) < FLOOR:
            few = True
        x = res[nm]
        ok = ok and (x["pf"] or 0) >= 1.15 and x["net$"] > 0 and x["per_wk"] >= 0.5
    act = np.array([x[1] for x in sig], float); flp = np.array([x[2] if x[2] is not None else 0.0 for x in sig], float)
    if len(sig):
        dr = [np.where(rng.random(len(sig)) < 0.5, act, flp).sum() for _ in range(N_PLACEBO)]
        res["placebo_p"] = round(float((np.array(dr) >= act.sum()).mean()), 3)
    else:
        res["placebo_p"] = None
    ok = ok and (res["placebo_p"] or 1) < 0.10
    res["all_net$"] = round(float(act.sum()))
    res["verdict"] = "TOO FEW" if few else ("PASS (candidate)" if ok else "REJECTED")
    return res


def proxy_dz(bar, d_push):
    """bar-proxy zone delta: volume x CLV (the rejected bar method), sign as real delta."""
    rg = bar["high"] - bar["low"]
    clv = (2 * bar["close"] - bar["high"] - bar["low"]) / rg if rg > 0 else 0.0
    return float(bar["volume"]), float(bar["volume"] * clv)


# ------------------------------------------------------------------------------------------------ OF1 / OF2 / OF4
def lit_trades():
    from tools import lit_losses as L
    M, C, B1, B5 = L.base()
    T = L.run2(M, C, {**L.P0}, None, B1=B1, B5=B5)
    return [{"day": t["day"], "dir": t["dir"], "pnl": float(t["pnl"]), "te": int(M.t[t["ext_i"]]), "tn": int(M.t[t["entry_i"]])}
            for t in T], str(pd.Timestamp(int(M.t[-1]), unit="s", tz="UTC").tz_convert(ET).date())


def et_day(ts):
    return pd.Timestamp(int(ts), unit="s", tz="UTC").tz_convert(ET).strftime("%Y-%m-%d")


def of12(D, days, trades, block):
    rows, k1, k2, k1p, approx = [], [], [], [], False
    for t in trades:
        ed = et_day(t["te"])
        if ed not in D:
            continue
        z = D[ed].zone(t["te"], t["dir"])
        if z is None:
            continue
        vz, dz = z
        d = t["dir"]
        absorbed = vz > 0 and dz * d < 0 and abs(dz) >= ABS_SHARE * vz
        th = block.get(ed)
        if th is not None and th[1]:
            approx = True
        sb = D[ed].block_signed(t["te"], max(t["te"], t["tn"])) if th else 0.0
        i = D[ed].row_of_t[int(t["te"])]
        pv, pdz = proxy_dz(D[ed].bars.iloc[i], d)
        rows.append({"day": t["day"], "pnl": t["pnl"]})
        k1.append(absorbed); k2.append(not (sb * d < 0)); k1p.append(pv > 0 and pdz * d < 0 and abs(pdz) >= ABS_SHARE * pv)
    return rows, k1, k2, k1p, approx


def block_thresholds(D, days):
    """{day: (threshold, flag)} from the PC's meta (block_th). flag = the PC's threshold differs from the one the cloud
    recomputes from the previous 5 tick days it has (a missing / thin day on either side) or sits in the 200+ bucket."""
    out = {}
    for i, d in enumerate(days):
        th = D[d].meta.get("block_th")
        if th is None:
            continue
        prev = [D[p].meta["size_hist"] for p in days[max(0, i - BLOCK_DAYS):i]]
        v, ap = ofsum.hist_percentile(prev, BLOCK_PCT) if len(prev) >= 3 else (None, True)
        out[d] = (float(th), bool(ap or v is None or abs(v - float(th)) > 1e-9))
    return out


def atlas_md():
    try:
        from tools import second_mix as M
        U = M.units()["MD"]
        return [{"day": u["day"], "dir": int(u["dir"]), "entry_t": int(u["entry_t"]),
                 "pnl": float(u["pts"]) / float(u["risk"]) * ATLAS_USD} for u in U if float(u.get("risk") or 0) > 0], \
            max(u["day"] for u in U)
    except Exception as e:                                                  # cache missing on a machine: listed, not fatal
        return [], f"unavailable ({e.__class__.__name__})"


def of4(D, units):
    rows, keep, keep_p = [], [], []
    for u in units:
        ed = et_day(u["entry_t"])
        if ed not in D:
            continue
        b = D[ed].bars
        w = b[(b.t >= u["entry_t"] - 1800) & (b.t < u["entry_t"])]
        if len(w) < 6:
            continue
        j = w.low.idxmin() if u["dir"] == 1 else w.high.idxmax()
        z = D[ed].zone(int(b.at[j, "t"]), u["dir"])
        if z is None:
            continue
        vz, dz = z
        d = u["dir"]
        pv, pdz = proxy_dz(b.loc[j], d)
        rows.append({"day": u["day"], "pnl": u["pnl"]})
        keep.append(vz > 0 and dz * d < 0 and abs(dz) >= ABS_SHARE * vz)
        keep_p.append(pv > 0 and pdz * d < 0 and abs(pdz) >= ABS_SHARE * pv)
    return rows, keep, keep_p


# ------------------------------------------------------------------------------------------------ OF3A / OF5 / OF6
def of3(D, days):
    sig = {"A": [], "B": []}
    prev_prof, prev_day = None, None
    for d in days:
        rth = D[d].rth()
        if len(rth) < 60:
            prev_prof = None
            continue
        if prev_prof:
            for k in range(1, len(rth)):
                if not (600 <= rth.at[k, "mod"] < 900):
                    continue
                hi, lo, cl, pc = rth.at[k, "high"], rth.at[k, "low"], rth.at[k, "close"], rth.at[k - 1, "close"]
                rg = hi - lo
                hit = 0
                for lv in prev_prof:
                    if rg > 0 and lo <= lv <= hi:
                        if pc > lv and cl > lv and cl >= lo + rg / 2:
                            hit = 1
                        elif pc < lv and cl < lv and cl <= lo + rg / 2:
                            hit = -1
                        if hit:
                            break
                if hit:
                    pnl, flip = S._sim_df(rth, k, hit), S._sim_df(rth, k, -hit)
                    if pnl is not None:
                        sig["B"].append((d, pnl, flip))
                        if rth.at[k, "delta"] * hit > 0:
                            sig["A"].append((d, pnl, flip))
                    break
        pp = D[d].rth_profile()
        if pp is not None and len(pp[0]):
            px, v = pp
            lo0 = np.floor(px.min() / 2.0) * 2.0
            bins = np.floor((px - lo0) / 2.0).astype(int)
            vol = np.bincount(bins, weights=v)
            sm = np.convolve(vol, np.ones(3) / 3, mode="same")
            prices = lo0 + 2.0 * np.arange(len(sm)) + 1.0
            prev_prof = P.lvns(prices, sm, int(np.argmax(sm)))
        else:
            prev_prof = None
    return sig


def levels(D, days, i):
    """prior-day RTH high/low (previous tick day within 4 calendar days) + Globex 18:00-09:30 high/low."""
    d = days[i]
    out = []
    b = D[d].bars
    on = b[b["mod"] < 570]
    if i > 0 and (dt.date.fromisoformat(d) - dt.date.fromisoformat(days[i - 1])).days <= 4:
        pb = D[days[i - 1]].bars
        pr = pb[(pb["mod"] >= 570) & (pb["mod"] < 960)]
        if len(pr):
            out += [("pdh", float(pr.high.max()), 1), ("pdl", float(pr.low.min()), -1)]
        on = pd.concat([pb[pb["mod"] >= 1080], on])
    if len(on):
        out += [("onh", float(on.high.max()), 1), ("onl", float(on.low.min()), -1)]
    return out


def of5(D, days, s, proxy=False):
    sig = []
    for i, d in enumerate(days):
        rth = D[d].rth()
        if len(rth) < 60:
            continue
        L = levels(D, days, i)
        for k in range(len(rth) - 1):
            if not (585 <= rth.at[k, "mod"] <= 900):
                continue
            hit = 0
            for _, lv, side in L:
                h, l, c = rth.at[k, "high"], rth.at[k, "low"], rth.at[k, "close"]
                if side == 1 and h >= lv + TICK and c < lv:
                    push = 1
                elif side == -1 and l <= lv - TICK and c > lv:
                    push = -1
                else:
                    continue
                if proxy:
                    vz, dz = proxy_dz(rth.iloc[k], push)
                else:
                    z = D[d].zone(int(rth.at[k, "t"]), -push)            # zone at the pushed extreme (high for push=+1)
                    if z is None:
                        continue
                    vz, dz = z
                if vz > 0 and dz * push > 0 and abs(dz) >= s * vz:
                    hit = -push
                    break
            if hit:
                pnl, flip = S._sim_df(rth, k, hit), S._sim_df(rth, k, -hit)
                if pnl is not None:
                    sig.append((d, pnl, flip))
                break
    return sig


def of6(D, days, G, proxy=False):
    sig = []
    for d in days:
        r = D[d].rth()
        if len(r) < 60:
            continue
        if proxy:
            rg = (r.high - r.low).replace(0, np.nan)
            dl = (r.volume * (2 * r.close - r.high - r.low) / rg).fillna(0.0).to_numpy()
        else:
            dl = r.delta.to_numpy(float)
        cvd = np.cumsum(dl)
        H, Lw = r.high.to_numpy(), r.low.to_numpy()
        for k in range(1, len(r) - 1):
            if not (600 <= r.at[k, "mod"] <= 900):
                continue
            hit = 0
            ph = H[:k]; pl = Lw[:k]
            if H[k] > ph.max():
                j = int(len(ph) - 1 - np.argmax(ph[::-1]))
                if k - j >= G and cvd[k] < cvd[j]:
                    hit = -1
            if not hit and Lw[k] < pl.min():
                j = int(len(pl) - 1 - np.argmin(pl[::-1]))
                if k - j >= G and cvd[k] > cvd[j]:
                    hit = 1
            if hit:
                pnl, flip = S._sim_df(r, k, hit), S._sim_df(r, k, -hit)
                if pnl is not None:
                    sig.append((d, pnl, flip))
                break
    return sig


# ------------------------------------------------------------------------------------------------ run
def quality(D, days):
    q = [D[d].meta["sides"].get("quote_rule", 0) for d in days]
    fwd = [d for d in days if D[d].meta["sides"].get("quote_rule", 0) >= 0.5]
    return {"quote_rule_share_mean": round(float(np.mean(q)), 3) if q else None, "quote_rule_days": len(fwd),
            "label": "quote-rule sides" if q and np.mean(q) >= 0.5 else "tick-rule sides (NinjaTrader history: side guessed from up/down ticks)"}, fwd


def run(src=None, ticks=False, force=False, final=False, raw=None, lit=None, atlas=None, write=True, seed=20261124, out_dir=None):
    global OUT, LOOKS
    if out_dir:                                                           # the PC: logs/orderflow (never a tracked repo file)
        os.makedirs(out_dir, exist_ok=True)
        OUT, LOOKS = os.path.join(out_dir, "battery_results.json"), os.path.join(out_dir, "battery_looks.json")
    R = raw if raw is not None else find_days(src, ticks)
    dropped = sorted(d for d, x in R.items() if int(x["meta"].get("rows", 0)) < MIN_ROWS)
    days = sorted(d for d in R if d not in dropped)
    status = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "tick_days": len(days),
              "dropped_thin": dropped, "need": MIN_DAYS, "first": days[0] if days else None, "last": days[-1] if days else None}
    if len(days) < MIN_DAYS:
        status["state"] = f"waiting: {len(days)} of {MIN_DAYS} tick days"
        if write:
            json.dump(status, open(OUT, "w"), indent=1)
        print(status["state"])
        return status
    looks = json.load(open(LOOKS)) if (write and os.path.exists(LOOKS)) else []
    look_no = len(LOOK_AT) if final else sum(1 for a in LOOK_AT if len(days) >= a)
    if write and not force and any(x.get("look") == look_no for x in looks):
        print(f"look {look_no} already done ({len(days)} days); --force to re-print, --final for the last look")
        return status
    rng = np.random.default_rng(seed)
    D = {d: Day(d, R[d]) for d in days}
    H = halves(days)
    out = {**status, "state": "ran", "look": look_no, "design": "research/orderflow/DESIGN.md @ bc2e5e68f",
           "split": {k: [v[0], v[-1], len(v)] for k, v in H.items()}}
    out["sides"], fwd = quality(D, days)
    T, bars_to = lit if lit is not None else lit_trades()
    out["lit_bars_to"] = bars_to
    out["tick_days_without_bars"] = [d for d in days if d > bars_to]
    block = block_thresholds(D, days)
    rows, k1, k2, k1p, approx = of12(D, days, T, block)
    out["OF1 LIT only when absorbed"] = filter_report(rows, k1, H, rng)
    out["OF2 LIT skip blocks against"] = filter_report(rows, k2, H, rng)
    if approx:
        out["OF2 LIT skip blocks against"]["note"] = "check: on some days the PC's block threshold used other prior days than the cloud has (or the 200+ bucket)"
    out["OF1 bar-proxy twin (info)"] = filter_report(rows, k1p, H, rng)
    units, md_to = atlas if atlas is not None else atlas_md()
    r4, k4, k4p = of4(D, units)
    out["OF4 ATLAS MD only when absorbed"] = filter_report(r4, k4, H, rng)
    out["OF4 ATLAS MD only when absorbed"]["md_trades_to"] = md_to
    out["OF4 bar-proxy twin (info)"] = filter_report(r4, k4p, H, rng)
    s3 = of3(D, days)
    out["OF3A LVN rejection + delta"] = standalone_report(s3["A"], H, rng)
    out["OF3B LVN rejection, no delta (info)"] = standalone_report(s3["B"], H, rng)
    disc = set(H["Discovery"])
    best5 = max(OF5_S, key=lambda s: sum(x[1] for x in of5(D, days, s) if x[0] in disc))
    r5 = standalone_report(of5(D, days, best5), H, rng)
    p5 = standalone_report(of5(D, days, best5, proxy=True), H, rng)
    r5["pick_s"] = best5
    if r5["verdict"].startswith("PASS") and r5["all_net$"] <= p5["all_net$"]:
        r5["verdict"] = "REJECTED (no better than the bar proxy)"
    out["OF5 absorption reversal at PD/Globex levels"] = r5
    out["OF5 bar-proxy twin (info)"] = p5
    best6 = max(OF6_G, key=lambda g: sum(x[1] for x in of6(D, days, g) if x[0] in disc))
    r6 = standalone_report(of6(D, days, best6), H, rng)
    p6 = standalone_report(of6(D, days, best6, proxy=True), H, rng)
    r6["pick_G"] = best6
    if r6["verdict"].startswith("PASS") and r6["all_net$"] <= p6["all_net$"]:
        r6["verdict"] = "REJECTED (no better than the bar proxy)"
    out["OF6 CVD divergence at new RTH high/low"] = r6
    out["OF6 bar-proxy twin (info)"] = p6
    if len(fwd) >= 20:                                                    # side check: forward (quote-rule) days alone
        Hf = {"forward": fwd}
        g1 = filter_report(rows, k1, Hf, rng)["forward"]["gain$"]
        out["sides_check_OF1_forward_gain$"] = g1
        if out["OF1 LIT only when absorbed"]["verdict"].startswith("PASS") and g1 <= 0:
            out["OF1 LIT only when absorbed"]["verdict"] = "REJECTED (sides disagree)"
    out["verdicts"] = {k: v["verdict"] for k, v in out.items() if isinstance(v, dict) and "verdict" in v and "(info)" not in k}
    if write:                                                             # day-ofmax: the DESIGN2 idea mill at the same look
        try:
            M = _mod("of_mill.py", "of_mill")
            mr = M.run_look(D, days, H, T, units, os.path.dirname(OUT), look_no, days[-1])
            out["mill"] = {"counts": mr["counts"], "candidates": [v["id"] for v in mr["candidates"]], "near_misses": mr["near_misses"]}
        except Exception as e:  # noqa: BLE001
            out["mill"] = {"error": f"{e.__class__.__name__}: {str(e)[:120]}"}
    if write:
        json.dump(out, open(OUT, "w"), indent=1, default=str)
        looks.append({"look": look_no, "made": out["made"], "days": len(days), "verdicts": out["verdicts"]})
        json.dump(looks, open(LOOKS, "w"), indent=1)
    show(out)
    return out


def phone_line(out) -> str:
    """One line for the owner's phone: days, each test's verdict, the honest bottom line."""
    v = out.get("verdicts") or {}
    short = {k.split(" ")[0]: (x.split(" ")[0] if x else "?") for k, x in v.items()}
    bits = ", ".join(f"{k} {x}" for k, x in short.items())
    anyp = any(x.startswith("PASS") for x in v.values())
    mc = (out.get("mill") or {}).get("counts") or {}
    mill = f" Idea mill: {mc.get('g1g2g3', 0)} of {mc.get('scored', 0)} ideas passed 3 gates (forward paper next)." if mc else ""
    return (f"Order-flow battery look {out.get('look')} on {out.get('tick_days')} tick days ({out.get('first')}..{out.get('last')}): {bits}.{mill} "
            + ("A PASS is a candidate only: forward paper next, nothing live changes without your yes." if anyp
               else "Nothing passed: LIT stays as it is."))


def show(out):
    print(f"order-flow battery look {out.get('look')}: {out['tick_days']} tick days {out['first']}..{out['last']} | {out['sides']['label']}")
    for k, v in out.items():
        if isinstance(v, dict) and "verdict" in v:
            hs = " | ".join(f"{h}: " + (f"n {v[h]['kept']['n']}/{v[h]['all']['n']} gain ${v[h]['gain$']}" if "kept" in v[h]
                                         else f"n {v[h]['n']} PF {v[h]['pf']} ${v[h]['net$']}") for h in ("Discovery", "Confirm") if h in v)
            p = v.get("skip_placebo_p", v.get("placebo_p"))
            print(f"  {k:46s} {v['verdict']:28s} {hs} | p {p}")


# ------------------------------------------------------------------------------------------------ selftest
def _prereg_flags(ticks_by_day, trades, days):
    """Reference: of_study.prereg's OF1 / OF2 lines on RAW ticks (copied logic) -> [(absorbed, keep2)]."""
    sizes = {d: ticks_by_day[d]["size"].values for d in days}
    block = {}
    for i, d in enumerate(days):
        prev = [sizes[p] for p in days[max(0, i - BLOCK_DAYS):i]]
        if len(prev) >= 3:
            block[d] = float(np.percentile(np.concatenate(prev), BLOCK_PCT))
    out = []
    for t in trades:
        ed = et_day(t["te"])
        if ed not in ticks_by_day:
            continue
        x = ticks_by_day[ed]
        ns = x.t_ns.values
        a, b = np.searchsorted(ns, t["te"] * 10**9), np.searchsorted(ns, (t["te"] + 300) * 10**9)
        if b - a < 20:
            continue
        bar = x.iloc[a:b]
        d = t["dir"]
        ext = bar.price.min() if d == 1 else bar.price.max()
        z = bar[(bar.price - ext).abs() <= ZONE * TICK]
        vz, dz = float(z["size"].sum()), float((z["size"] * z.side).sum())
        c = np.searchsorted(ns, t["tn"] * 10**9)
        w = x.iloc[a:max(a, c)]
        th = block.get(ed)
        sb = float((w["size"] * w.side)[w["size"] >= th].sum()) if th else 0.0
        out.append((vz > 0 and dz * d < 0 and abs(dz) >= ABS_SHARE * vz, not (sb * d < 0)))
    return out


def selftest():
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-09-14", periods=44)]
    ticks, raw = {}, {}
    metas = {}
    for i, d in enumerate(days):
        x = ofsum.synth_day(d, n=120_000, seed=i)
        ticks[d] = x.sort_values("t_ns", kind="stable").reset_index(drop=True)
        raw[d] = _from_bytes(ofsum.summarize(x, d, ofsum.block_threshold(d, metas=metas)))
        metas[d] = raw[d]["meta"]
    rng = np.random.default_rng(3)
    trades = []
    for d in days:
        for _ in range(2):
            hm = int(rng.integers(10 * 12, 15 * 12)) * 5
            te = int(pd.Timestamp(f"{d} {hm // 60:02d}:{hm % 60:02d}", tz=ET).timestamp())
            trades.append({"day": d, "dir": int(rng.choice([-1, 1])), "pnl": float(rng.normal(50, 400)), "te": te,
                           "tn": te + 300 * int(rng.integers(1, 6))})
    D = {d: Day(d, raw[d]) for d in days}
    block = block_thresholds(D, days)
    _, k1, k2, _, _ = of12(D, days, trades, block)
    ref = _prereg_flags(ticks, trades, days)
    par = len(ref) == len(k1) and all(a == b for a, b in zip([r[0] for r in ref], k1)) and \
        all(a == b for a, b in zip([r[1] for r in ref], k2))
    th_ok = len(block) == len(days) - 3 and not any(f for _, f in block.values()) and \
        all(abs(block[d][0] - float(np.percentile(np.concatenate([ticks[p]["size"].values for p in days[max(0, i - 5):i]]), 99.5))) < 1e-9
            for i, d in enumerate(days) if d in block)
    units = [{"day": t["day"], "dir": t["dir"], "entry_t": t["tn"] + 1800, "pnl": t["pnl"] / 3} for t in trades]
    w = run(raw={d: raw[d] for d in days[:30]}, lit=(trades, "2026-12-31"), atlas=(units, "x"), write=False)
    o = run(raw=raw, lit=(trades, "2026-12-31"), atlas=(units, "x"), write=False, force=True)
    ok = par and th_ok and w.get("state", "").startswith("waiting") and o.get("state") == "ran" and len(o["verdicts"]) == 6
    print("of_battery selftest:", "OK" if ok else "FAIL", "| OF1/OF2 parity with of_study.prereg on raw ticks:", par,
          f"({len(ref)} trades, absorbed {sum(k1)}, blocks-against {len(k2) - sum(k2)})", "| block threshold exact:", th_ok)
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src"); ap.add_argument("--ticks", action="store_true"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--final", action="store_true"); ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out-dir", help="write results / looks here (the PC: logs/orderflow) instead of research/orderflow")
    ap.add_argument("--line", help="also write the phone line JSON here (the PC's autopilot)")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    res = run(a.src, a.ticks, a.force, a.final, out_dir=a.out_dir)
    if a.line and isinstance(res, dict) and res.get("state") == "ran":
        with open(a.line, "w", encoding="utf-8") as fh:
            json.dump({"key": "research:ofbattery:%s" % res.get("look"), "t": int(__import__("time").time()),
                       "title": "Order flow: battery look %s" % res.get("look"), "body": phone_line(res)}, fh)
