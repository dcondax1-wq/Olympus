"""Day-type labels (hindsight) + causal features at 4 checkpoints (C0 prior close, C1 02:00, C2 09:30, C3 10:30).
Rules: research/dayclass/DESIGN.md (pre-registered). PAPER RESEARCH ONLY.

    python -X utf8 research/dayclass/features.py    -> research/dayclass/days.csv
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "structure"))
import bars as BR  # noqa: E402

OUT = os.path.join(HERE, "days.csv")
TIER1 = ("FOMC rate decision", "CPI", "PPI", "Non-Farm")
CLASSES = ["range", "trend_up", "trend_down", "reversal", "news_exp"]


def tier1_days():
    e = pd.read_csv(os.path.join(ROOT, "data", "news", "events.csv"))
    e = e[(e["impact"] == "high") & e["event"].apply(lambda s: any(s.startswith(k) for k in TIER1))]
    return set(e["date"])


def daily_vol():
    v = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))[["date", "close"]].rename(columns={"close": "vix"})
    n = pd.read_csv(os.path.join(ROOT, "data", "VXN_1d.csv"))[["date", "close"]].rename(columns={"close": "vxn"})
    c = pd.read_csv(os.path.join(ROOT, "data", "CBOE_vol_1d.csv"))[["date", "vix9d", "vix3m"]]
    d = v.merge(n, on="date", how="left").merge(c, on="date", how="left").sort_values("date").reset_index(drop=True)
    return d


def prior_vol(vol, day):
    """The last CBOE close strictly before `day` (the session's date)."""
    i = np.searchsorted(vol["date"].values, day) - 1
    if i < 1:
        return None
    r, p = vol.iloc[i], vol.iloc[i - 1]
    return {"vix": r["vix"], "vix_chg": (r["vix"] / p["vix"] - 1) * 100,
            "vix_term": r["vix"] / r["vix3m"] if pd.notna(r["vix3m"]) and r["vix3m"] else np.nan,
            "vix_short": r["vix9d"] / r["vix"] if pd.notna(r["vix9d"]) else np.nan,
            "vxn_spread": (r["vxn"] - r["vix"]) if pd.notna(r["vxn"]) else np.nan}


def label(o, h, l, c, t_hi, t_lo, ratr, t1):
    R = h - l
    if R <= 0 or not np.isfinite(ratr):
        return None
    if t1 and R >= 1.3 * ratr:
        return "news_exp"
    loc = (c - l) / R
    if R >= 0.8 * ratr and abs(c - o) >= 0.5 * R:
        if c > o and loc >= 0.75:
            return "trend_up"
        if c < o and loc <= 0.25:
            return "trend_down"
    up, dn = h - o, o - l
    if t_hi < t_lo and up >= 0.4 * ratr and o - c >= 0.25 * ratr:
        return "reversal"
    if t_lo < t_hi and dn >= 0.4 * ratr and c - o >= 0.25 * ratr:
        return "reversal"
    return "range"


def build(es=True):
    df = BR.load("NQ", "5m")
    T1 = tier1_days()
    vol = daily_vol()
    E = None
    if es:
        E = BR.load("ES", "5m")
        E = {d: g for d, g in E.groupby("day")}
    rows = []
    prev = []          # prior RTH facts list
    for day, g in df.groupby("day", sort=True):
        if len(g) < 150:
            continue
        m = g["mins"].values
        o_, h_, l_, c_, v_ = (g[k].values for k in ("open", "high", "low", "close", "volume"))
        on = (m >= 1080) | (m < 570)
        rth = (m >= 570) & (m < 960)
        if rth.sum() < 70 or on.sum() < 100:
            continue
        ri = np.nonzero(rth)[0]
        ro, rh, rl, rc = o_[ri[0]], h_[ri].max(), l_[ri].min(), c_[ri[-1]]
        t_hi, t_lo = ri[np.argmax(h_[ri])], ri[np.argmin(l_[ri])]
        vw = float((c_[ri] * v_[ri]).sum() / max(1, v_[ri].sum()))
        rec = {"day": day, "dow": int(g["dow"].iloc[0]), "ro": ro, "rh": rh, "rl": rl, "rc": rc, "vwap": vw, "t1": day in T1}
        if len(prev) >= 14:
            P = prev[-1]
            ratr = float(np.mean([p["rh"] - p["rl"] for p in prev[-14:]]))
            rec["ratr"] = ratr
            rec["y"] = label(ro, rh, rl, rc, t_hi, t_lo, ratr, rec["t1"])
            pr = P["rh"] - P["rl"]
            # ---- C0
            f = {"p_type": P.get("y"), "p_rng": pr / ratr, "p_loc": (P["rc"] - P["rl"]) / pr if pr else 0.5,
                 "t1": float(rec["t1"]), "dow": rec["dow"]}
            if len(prev) >= 6:
                cs = [p["rc"] for p in prev[-6:]]
                f["er5"] = abs(cs[-1] - cs[0]) / max(1e-9, sum(abs(np.diff(cs))))
            pv = prior_vol(vol, day)
            if pv:
                f.update(pv)
            # ---- C1 (02:00): overnight bars that closed by 02:00 (18:00..01:55 opens)
            c1 = on & ((m >= 1080) | (m < 120))
            if c1.sum() > 10:
                ii = np.nonzero(c1)[0]
                f["c1_on_rng"] = (h_[ii].max() - l_[ii].min()) / ratr
                px = c_[ii[-1]]
                f["c1_vs_close"] = (px - P["rc"]) / ratr
                f["c1_pos_prior"] = (px - P["rl"]) / pr if pr else 0.5
                f["c1_on_dir"] = (px - o_[ii[0]]) / max(1e-9, h_[ii].max() - l_[ii].min())
            # ---- C2 (09:30)
            ii = np.nonzero(on & ((m >= 1080) | (m < 570)))[0]
            onh, onl = h_[ii].max(), l_[ii].min()
            f["c2_on_rng"] = (onh - onl) / ratr
            f["c2_gap"] = (ro - P["rc"]) / ratr
            f["c2_open_prior"] = (ro - P["rl"]) / pr if pr else 0.5
            f["c2_open_vwap"] = (ro - P["vwap"]) / ratr
            pm = np.nonzero((m >= 480) & (m < 570))[0]
            f["c2_pre_move"] = (c_[pm[-1]] - o_[pm[0]]) / ratr if len(pm) else 0.0
            f["c2_open_on"] = (ro - onl) / (onh - onl) if onh > onl else 0.5
            # ---- C3 (10:30)
            ib = np.nonzero((m >= 570) & (m < 630))[0]
            ibh, ibl, ibc = h_[ib].max(), l_[ib].min(), c_[ib[-1]]
            f["c3_ib_rng"] = (ibh - ibl) / ratr
            f["c3_ib_loc"] = (ibc - ibl) / (ibh - ibl) if ibh > ibl else 0.5
            f["c3_ib_move"] = (ibc - ro) / ratr
            f15 = ib[:3]
            mv = c_[f15[-1]] - ro
            back = (l_[f15].min() < ro - 0.05 * ratr) if mv > 0 else (h_[f15].max() > ro + 0.05 * ratr)
            f["c3_odrive"] = float(np.sign(mv)) if (abs(mv) >= 0.15 * ratr and not back) else 0.0
            f["c3_brk_hi"] = float(ibh > P["rh"])
            f["c3_brk_lo"] = float(ibl < P["rl"])
            body = np.abs(c_ - o_)
            mb = pd.Series(body).rolling(20).mean().shift(1).values
            dsp = [(np.sign(c_[j] - o_[j])) for j in ib if np.isfinite(mb[j]) and mb[j] > 0 and body[j] >= 1.5 * mb[j]]
            f["c3_disp_n"] = len(dsp)
            f["c3_disp_net"] = float(sum(dsp))
            pib = [p["ibv"] for p in prev[-20:] if p.get("ibv")]
            f["c3_ib_vol"] = v_[ib].sum() / np.mean(pib) if pib else 1.0
            # ---- ES (2025-04+)
            if E is not None and day in E:
                eg = E[day]
                em = eg["mins"].values
                eon = np.nonzero((em >= 1080) | (em < 570))[0]
                eib = np.nonzero((em >= 570) & (em < 630))[0]
                if len(eon) > 50 and len(eib) >= 10:
                    eo, ec = eg["open"].values, eg["close"].values
                    f["es_on_same"] = float(np.sign(ec[eon[-1]] - eo[eon[0]]) == np.sign(c_[ii[-1]] - o_[ii[0]]))
                    f["es_ib_same"] = float(np.sign(ec[eib[-1]] - eo[eib[0]]) == np.sign(ibc - ro))
            rec.update(f)
        rec["ibv"] = float(v_[(m >= 570) & (m < 630)].sum())
        prev.append(rec)
        rows.append(rec)
    D = pd.DataFrame(rows)
    D = D[D["y"].notna()].reset_index(drop=True)
    D["span"] = [BR.span_of(d) for d in D["day"]]
    return D


if __name__ == "__main__":
    D = build()
    D.to_csv(OUT, index=False)
    print(len(D), D["day"].min(), D["day"].max())
    print(pd.crosstab(D["span"], D["y"], normalize="index").round(3))
    print(D["span"].value_counts())
