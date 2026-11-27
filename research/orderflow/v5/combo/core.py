"""v5 'combo' family core (rules: research/orderflow/v5/combo/DESIGN.md, frozen before any result). PAPER RESEARCH ONLY.

Lane A (v5/levels V0 = the absorbed level fade, E5 simulator) filtered by LIT / ATLAS / regime / day-type context.
Imports nothing that can trade: engine.lit / engine.data (bar math only), tools.retail_standalone (bar math only).
"""
from __future__ import annotations

import bisect
import datetime as dt
import importlib.util
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from engine import data as EDATA  # noqa: E402
from engine import lit as LIT  # noqa: E402
from tools import retail_standalone as RS  # noqa: E402

ET = ZoneInfo("America/New_York")


def _load_levels_core():
    sp = importlib.util.spec_from_file_location("v5combo_lv", os.path.join(ROOT, "research", "orderflow", "v5", "levels", "core.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


LV = _load_levels_core()
B = LV.B
N_PERM = 5000
SWEEP_WIN, DEPTH_ATR = 24, 0.5
FLAGS = ("AT", "LA", "S1", "VX", "IO")
DAY_FLAGS = {"S1", "VX", "IO"}
VARIANTS = {"C1": "AT", "C2": "LA", "C3": "S1", "C4": "VX", "C5": "IO", "C6": "VOTE"}
NAMES = {"C0": "control: lane A alone", "C1": "ATLAS 15m+1h EMA trend with the fade", "C2": "LIT armed same side",
         "C3": "S1 wide-range regime", "C4": "VIX > 1y median", "C5": "inside-open (balance) day", "C6": "vote >= 3 of 5"}
VIDS = ["C1", "C2", "C3", "C4", "C5", "C6"]


# ------------------------------------------------------------------------------------------------ the 5m context frame
def frame(D):
    """NQ_5m.csv + the pc_days 5m bars after its last bar (time, open, high, low, close, volume)."""
    f = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    last = int(f.time.max())
    ext = []
    for d in sorted(D):
        b = D[d].bars
        b = b[b.t > last]
        if len(b):
            ext.append(pd.DataFrame({"time": b.t.astype(np.int64), "open": b.open, "high": b.high, "low": b.low,
                                     "close": b.close, "volume": b.volume}))
    if ext:
        f = pd.concat([f] + ext, ignore_index=True)
    return f.drop_duplicates("time", keep="first").sort_values("time").reset_index(drop=True)


class Context:
    def __init__(self, D):
        F = frame(D)
        self.F = F
        # ATLAS trend (tools/second_ema.load: t15 / t60 = sign(EMA21 - EMA50) of clock-aligned HTF closes, closed only)
        d = RS.load_frame(F.copy())
        self.at_t = d["t"].copy()
        self.t15 = np.nan_to_num(RS.to5(RS.htf(15), np.sign(RS.ema(RS.htf(15)["c"], 21) - RS.ema(RS.htf(15)["c"], 50))))
        self.t60 = np.nan_to_num(RS.to5(RS.htf(60), np.sign(RS.ema(RS.htf(60)["c"], 21) - RS.ema(RS.htf(60)["c"], 50))))
        # LIT market on the same bars (engine.data.load's junk-bar filter)
        Fl = F[~((F["high"] == F["low"]) & (F["volume"] <= 0))]
        self.M = LIT.Market(bars=EDATA.from_frame("NQ", "5m", Fl))
        self.k_of = {str(x[0]): k for k, x in enumerate(self.M.days)}
        self._lv = {}
        self.daily = self._daily(F)

    # ---- S1 / VX per session day
    @staticmethod
    def _daily(F):
        nq = pd.read_csv(os.path.join(ROOT, "data", "NQ_1d.csv"))
        nq["day"] = [(dt.datetime.fromtimestamp(int(t), ET) + dt.timedelta(hours=6)).date().isoformat() for t in nq.time]
        nq = nq.drop_duplicates("day", keep="last").set_index("day").sort_index()[["high", "low", "close"]]
        et = pd.to_datetime(F.time.values, unit="s", utc=True).tz_convert(ET)
        sd = (et.tz_localize(None) + pd.Timedelta(hours=6)).normalize().strftime("%Y-%m-%d")
        g = pd.DataFrame({"day": sd, "high": F.high.values, "low": F.low.values, "close": F.close.values})
        g5 = g.groupby("day").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
        g5 = g5[g5.index > nq.index.max()]
        nq = pd.concat([nq, g5]).sort_index()
        rng = (nq.high - nq.low) / nq.close
        rv20 = rng.rolling(20).mean()
        med = lambda s: s.rolling(252, min_periods=120).median()  # noqa: E731
        s1 = rv20.shift(1) > med(rv20).shift(1)
        vx = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
        vd, vc = list(vx.date.astype(str)), vx.close.values.astype(float)
        days = list(nq.index)
        vix = pd.Series([vc[bisect.bisect_left(vd, x) - 1] if bisect.bisect_left(vd, x) > 0 else np.nan for x in days],
                        index=nq.index)
        vxf = vix > med(vix)
        return {"S1": s1.to_dict(), "VX": vxf.to_dict(), "rv20": rv20.to_dict(), "vix": vix.to_dict()}

    # ---- flags of one candidate
    def at_flag(self, t_sig, d):
        i = int(np.searchsorted(self.at_t, t_sig))
        if i >= len(self.at_t) or int(self.at_t[i]) != int(t_sig):
            return False
        return bool(self.t15[i] == d and self.t60[i] == d)

    def la_flag(self, day, t_sig, d):
        M = self.M
        k = self.k_of.get(day)
        if k is None:
            return False
        i = int(np.searchsorted(M.t, t_sig))
        if i >= M.n or int(M.t[i]) != int(t_sig):
            return False
        if k not in self._lv:
            self._lv[k] = M.levels(k)
        s = M.days[k][1]
        lo_d = M.l if d == 1 else -M.h
        need = DEPTH_ATR * float(M.atr[i])
        best = -np.inf
        for side, px, ki, nm, cls in self._lv[k]:
            if (side == "low") != (d == 1) or ki >= i:
                continue
            p = px * d
            j = LIT._first_breach(lo_d, max(int(ki), s - 600), i + 1, p)
            if j > i or j < i - (SWEEP_WIN - 1):
                continue
            best = max(best, p - float(lo_d[j:i + 1].min()))
        return bool(best >= need)

    def io_flag(self, D, usable, day):
        L = {nm: lv for nm, lv, _ in LV.v0_levels(D, usable, day, None)}
        b = D[day].bars
        o = b[b["mod"] == 570]
        if "pdh" not in L or not len(o):
            return False
        x = float(o.open.iat[0])
        return bool(L["pdl"] < x < L["pdh"])

    def flags(self, D, usable, c):
        f = {"AT": self.at_flag(c["t_sig"], c["d"]), "LA": self.la_flag(c["day"], c["t_sig"], c["d"]),
             "S1": bool(self.daily["S1"].get(c["day"], False)), "VX": bool(self.daily["VX"].get(c["day"], False)),
             "IO": self.io_flag(D, usable, c["day"])}
        f["VOTE"] = sum(f[k] for k in FLAGS) >= 3
        return f


def candidates(D, usable, days, ctx):
    out = []
    for day in days:
        for x in LV.v0_candidates(D, usable, day):
            x = LV.simulate(D[day], x)
            x["flags"] = ctx.flags(D, usable, x)
            out.append(x)
    return out


# ------------------------------------------------------------------------------------------------ scoring
def _book(cands, key):
    sub = [dict(x) for x in cands if key is None or x["flags"][key]]
    return LV.book(sub)


def perm_p(rows, key, day_level, seed=11, n=N_PERM):
    """rows: resolved absorbed candidates. stat = mean R(flag) - mean R(not flag); one-sided."""
    R = np.array([x["R"] for x in rows], float)
    lab = np.array([x["flags"][key] for x in rows], bool)
    if lab.all() or (~lab).all():
        return None, None
    obs = R[lab].mean() - R[~lab].mean()
    rng = np.random.default_rng(seed)
    hits = 0
    if day_level:
        dl = sorted({x["day"] for x in rows})
        di = np.array([dl.index(x["day"]) for x in rows])
        dlab = np.array([next(x["flags"][key] for x in rows if x["day"] == d) for d in dl], bool)
        for _ in range(n):
            L = rng.permutation(dlab)[di]
            if L.all() or (~L).all():
                continue
            hits += int(R[L].mean() - R[~L].mean() >= obs - 1e-12)
    else:
        k, N = int(lab.sum()), len(R)
        for _ in range(n // 500):
            idx = np.argsort(rng.random((500, N)), axis=1)[:, :k]
            s = R[idx].sum(1)
            hits += int(((s / k - (R.sum() - s) / (N - k)) >= obs - 1e-12).sum())
    return round((hits + 1) / (n + 1), 4), round(float(obs), 3)


def score(cands, days, key):
    days = sorted(days)
    k = (len(days) + 1) // 2
    H = {"older": set(days[:k]), "newer": set(days[k:])}
    bk = _book(cands, key)
    R = np.array([x["R"] for x in bk], float)
    U = np.array([x["usd"] for x in bk], float)
    wins, loss = U[U > 0].sum(), -U[U <= 0].sum()
    out = {"trades": len(bk), "per_week": round(len(bk) / (len(days) / 5.0), 2),
           "win_pct": round(100 * float((U > 0).mean()), 1) if len(U) else None,
           "mean_R": round(float(R.mean()), 3) if len(R) else None,
           "pf": round(float(wins / loss), 2) if loss > 0 else None,
           "net_usd": round(float(U.sum()), 0), "usd_month": round(float(U.sum()) / (len(days) / 21.0), 0),
           "usd500": round(float(sum(x.get("usd500", 0.0) for x in bk)), 0),
           "max_dd_usd": round(LV.max_dd([x["usd"] for x in sorted(bk, key=lambda r: r["exit_t"])]), 0)}
    res = [x for x in cands if x["absorbed"] and x.get("R") is not None]
    if key is None:
        out.update(gap_R=None, placebo_p=None, flag_share=None)
    else:
        p, g = perm_p(res, key, key in DAY_FLAGS)
        out.update(gap_R=g, placebo_p=p, flag_share=round(float(np.mean([x["flags"][key] for x in res])), 3) if res else None)
    hv = {}
    for nm, s in H.items():
        bR = [x["R"] for x in bk if x["day"] in s]
        a = [x["R"] for x in res if x["day"] in s and (key is None or x["flags"][key])]
        na = [x["R"] for x in res if x["day"] in s and key is not None and not x["flags"][key]]
        hv[nm] = {"trades": len(bR), "mean_R": round(float(np.mean(bR)), 3) if bR else None,
                  "usd": round(float(sum(x["usd"] for x in bk if x["day"] in s)), 0),
                  "gap_R": round(float(np.mean(a) - np.mean(na)), 3) if a and na else None}
    out["halves"] = hv
    return out


def holm(ps):
    return LV.holm(ps)


def verdict(s, p_holm):
    if s["trades"] < 20 or s["placebo_p"] is None:
        return "TOO FEW"
    hv = s["halves"].values()
    both = all((h["mean_R"] if h["mean_R"] is not None else -1) > 0 and (h["gap_R"] if h["gap_R"] is not None else -1) > 0
               for h in hv)
    if (s["net_usd"] > 0 and (s["pf"] or 0) >= 1.20 and both and s["placebo_p"] < 0.10 and p_holm is not None and p_holm < 0.10):
        return "YES-candidate"
    if s["net_usd"] > 0 and (s["gap_R"] if s["gap_R"] is not None else -1) > 0 and s["placebo_p"] < 0.20:
        return "weak"
    return "NO"


def table(rows):
    hdr = ("var", "context", "trades", "/wk", "win%", "meanR", "PF", "$1mic", "$/mo", "maxDD", "halves R (old/new)",
           "flag share", "gap", "halves gap", "p", "Holm", "verdict")
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for vid, s in rows:
        hv = s["halves"]
        lines.append("| " + " | ".join(str(x) for x in (
            vid, NAMES.get(vid, vid), s["trades"], s["per_week"], s["win_pct"], s["mean_R"], s["pf"],
            f"${s['net_usd']:+,.0f}", f"${s['usd_month']:+,.0f}", f"${s['max_dd_usd']:,.0f}",
            f"{hv['older']['mean_R']} / {hv['newer']['mean_R']}", s.get("flag_share"), s["gap_R"],
            f"{hv['older']['gap_R']} / {hv['newer']['gap_R']}", s["placebo_p"], s.get("holm_p"), s.get("verdict"))) + " |")
    return "\n".join(lines)
