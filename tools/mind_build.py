"""Build Mind's memory and its honest calibration (engine/mind.py).

  python -X utf8 tools/mind_build.py            # store + calibration -> research/mind/store.json, calibration.json
  python -X utf8 tools/mind_build.py calib      # calibration only (from the stored store.json)

Memory (every historical setup / trade of each bot, the features the live bot can compute at the decision bar):
  lit     run lit_live's settings (live_model.json "lit") through tools/lit_final.run: 2026 1m entries + 2021-25 5m entries,
          each matched to its engine candidate (sweep depth, displacement, inducements, swept level) + context
  atlas   research/runs/atlas_funded_live.json (EMA / MACD / S/R members, 2021-11 -> 2026-10) + context
  blitz   research/scalp/na_best_trades.json (2026, 1m) + context
Context (engine/mind.Hist on data/NQ_5m.csv, the TradingView CME NQ1! export): time since 18:00, killzone, VIX (prior close,
CBOE file), 15m / 1h structure trend vs the trade (engine/structure), prior-day range ratio, first-hour range ratio, where
price sits in the day's range, 5m ATR vs its 7-day median, stop in ATR.

Calibration (out of sample, never the trade's own day): fit = 2026 H1; each 2026 H2 and 2021-25 trade predicted from its k
nearest H1 setups. Reported: rank correlation predicted-vs-real R, top-minus-bottom tercile spread (+ permutation p), win
calibration (Brier vs the base rate), AUC. Also the reverse check (fit 2021-25, check 2026). Trend-day model: logistic on
the 10:30 features, fit 2026 H1, accuracy on 2026 H2 and 2021-25.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import mind as MD  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = MD.RES_DIR


def _hist():
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    return MD.hist_from_frame(df)


def cols_for(bot):
    sp = MD.SPEC[bot]
    extra = ["qty", "risk_pts", "hm", "dow", "p_trend"]
    return MD.ROW0 + [c for c in sp["num"] + sp["cat"] if c not in MD.ROW0] + [c for c in extra if c not in sp["num"]]


def _row(bot, base: dict, f: dict):
    return [base.get(c, f.get(c)) if c in base else f.get(c) for c in cols_for(bot)]


def _ptrend(H, model, T):
    """The trend-day probability known at T (None before 10:30 ET of that day)."""
    e = dt.datetime.fromtimestamp(int(T), ET)
    if not (630 <= e.hour * 60 + e.minute < 1080):
        return None
    k = H.k_of[H.idx(T)]
    x = MD.daytype_x(H, int(k))
    return MD._f(MD.daytype_prob(model, x), 3) if x else None


def lit_rows(H, model):
    from engine import lit, lit_live
    from tools import lit_final as F
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = {**lit.DEFAULTS, **lm["lit"]}
    T = F.run(P)
    M, C = F.market(P["ref"], P["extra_boxes"])
    idx = {(z["i"], z["dir"]): z for z in C}
    dm, age = float(P["idm_a"][0]), float(P["idm_a"][1])
    out = []
    for t in T:
        z = idx.get((t["i"], t["dir"]))
        if z is None:
            continue
        d = int(t["dir"])
        Td = int(M.t[z["i"]]) + 300
        f = H.ctx(Td, d)
        if not f:
            continue
        rr = abs(float(t["target_px"]) - float(t["entry_px"])) / float(t["risk_pts"]) if t.get("target_px") and t.get("risk_pts") else None
        f.update(MD.lit_feats(z["depth_atr"], z["disp"], sum(1 for a, b in z["idm_a"] if a <= dm and b <= age), t["risk_pts"],
                              z["atr_ext"], rr, lit_live._sweep_names(z["swept"])))
        e = dt.datetime.fromtimestamp(int(t["entry_t"]), ET)
        base = {"day": t["day"], "t": int(t["entry_t"]), "dir": d, "r": round(float(t["r"]), 3), "usd": round(float(t["pnl"]), 2),
                "exit": t["exit"], "src": t.get("trigger") or "LIT", "qty": int(t["qty"]), "risk_pts": round(float(t["risk_pts"]), 2),
                "hm": e.strftime("%H:%M"), "dow": e.weekday(), "p_trend": _ptrend(H, model, Td)}
        out.append(_row("lit", base, f))
    return out


def atlas_rows(H, model):
    d = json.load(open(os.path.join(ROOT, "research", "runs", "atlas_funded_live.json"), encoding="utf-8"))
    c = d["trade_cols"]
    out = []
    for r in d["trades"]:
        t = dict(zip(c, r))
        dr = int(t["dir"])
        Td = int(t["entry_t"])
        f = H.ctx(Td, dr)
        if not f:
            continue
        f["member"] = t["trigger"]
        f["stop_atr"] = round(float(t["risk_pts"]) / f["atr"], 3) if f.get("atr") else None
        e = dt.datetime.fromtimestamp(Td, ET)
        base = {"day": t["day"], "t": Td, "dir": dr, "r": round(float(t["r"]), 3), "usd": round(float(t["pnl"]), 2),
                "exit": str(t["exit"]).upper(), "src": t["trigger"], "qty": int(t["qty"] or 0), "risk_pts": t["risk_pts"],
                "hm": e.strftime("%H:%M"), "dow": e.weekday(), "p_trend": _ptrend(H, model, Td)}
        out.append(_row("atlas", base, f))
    return out


def blitz_rows(H, model):
    d = json.load(open(os.path.join(ROOT, "research", "scalp", "na_best_trades.json"), encoding="utf-8"))
    out = []
    for t in d["trades"]:
        e = dt.datetime.strptime(t["entry_t"], "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        Td = int(e.timestamp())
        dr = 1 if str(t["dir"]).lower().startswith("l") else -1
        f = H.ctx(Td, dr)
        if not f:
            continue
        base = {"day": e.strftime("%Y-%m-%d"), "t": Td, "dir": dr, "r": round(float(t["r"]), 3), "usd": None,
                "exit": str(t["exit_kind"]).upper(), "src": "BLITZ", "qty": None, "risk_pts": t["risk_pts"],
                "hm": e.strftime("%H:%M"), "dow": e.weekday(), "p_trend": _ptrend(H, model, Td)}
        out.append(_row("blitz", base, f))
    return out


# ------------------------------------------------------------------------------------------------ the trend-day model
def daytype(H):
    X, y, days = [], [], []
    for k in range(len(H.days)):
        x = MD.daytype_x(H, k)
        lab = MD.daytype_label(H, k)
        if x is None or lab is None:
            continue
        e = dt.date.fromisoformat(x["day"])
        if e.weekday() >= 5:
            continue
        X.append([x.get(c) for c in MD.DT_FEATS]); y.append(lab); days.append(x["day"])
    X = np.array([[np.nan if v is None else float(v) for v in row] for row in X])
    y = np.array(y)
    days = np.array(days)
    fit = (days >= MD.H1[0]) & (days <= MD.H1[1])
    mu = np.nanmean(X[fit], axis=0)
    sd = np.nanstd(X[fit], axis=0)
    sd = np.where(sd > 1e-9, sd, 1.0)
    Xf = np.where(np.isfinite(X), X, mu)
    Z = (Xf - mu) / sd
    b0, w = MD.logit_fit(Z[fit], y[fit], lam=2.0)
    model = {"feats": MD.DT_FEATS, "mu": [float(v) for v in mu], "sd": [float(v) for v in sd], "b0": b0, "w": w,
             "fit": "2026 H1", "label": "trend day = the 09:30-16:00 session opens in one quarter of its range and closes in the opposite quarter",
             "n_fit": int(fit.sum())}
    p = 1 / (1 + np.exp(-(b0 + Z @ np.array(w))))
    rep = {}
    for nm, (a, z) in (("H1 (fit)", MD.H1), ("H2", MD.H2), ("2021-25", MD.R2125)):
        m = (days >= a) & (days <= z)
        if not m.any():
            continue
        yy, pp = y[m].astype(bool), p[m]
        base = float(y[fit].mean())
        hi = pp >= 0.6
        rep[nm] = {"n": int(m.sum()), "base_rate": round(float(yy.mean()), 3), "auc": MD._f(MD.auc(pp, yy), 3),
                   "brier": round(float(((pp - yy) ** 2).mean()), 4), "brier_base": round(float(((base - yy) ** 2).mean()), 4),
                   "acc_05": round(float(((pp >= 0.5) == yy).mean()), 3), "acc_always_no": round(float((~yy).mean()), 3),
                   "n_p60": int(hi.sum()), "hit_p60": round(float(yy[hi].mean()), 3) if hi.any() else None,
                   "lo_p20": round(float(yy[pp < 0.2].mean()), 3) if (pp < 0.2).any() else None, "n_lo_p20": int((pp < 0.2).sum())}
    model["report"] = rep
    return model


def calibrate(store):
    out = {}
    for bot, blk in store["bots"].items():
        cols, rows = blk["cols"], blk["rows"]
        days = np.array([r[0] for r in rows])
        fit = (days >= MD.H1[0]) & (days <= MD.H1[1])
        mem = MD.Memory(bot, cols, rows, fit=fit)
        spans = {}
        for nm, sp in (("H2", MD.H2), ("2021-25", MD.R2125)):
            m = (days >= sp[0]) & (days <= sp[1])
            if m.sum() >= 9:
                spans[nm] = MD.evaluate(mem, fit, m)
        valid, note = MD.judge(spans)
        alt = {}
        f2 = (days >= MD.R2125[0]) & (days <= MD.R2125[1])
        if f2.sum() >= 50:
            mem2 = MD.Memory(bot, cols, rows, fit=f2)
            for nm, sp in (("2026 H1", MD.H1), ("2026 H2", MD.H2)):
                m = (days >= sp[0]) & (days <= sp[1])
                if m.sum() >= 9:
                    alt[nm] = MD.evaluate(mem2, f2, m)
        out[bot] = {"fit": "2026 H1", "k": MD.SPEC[bot]["k"], "n_fit": int(fit.sum()), "n": len(rows), "spans": spans,
                    "valid": bool(valid), "note": note, "reverse": {"fit": "2021-25", "spans": alt}}
        print(bot, json.dumps(out[bot]), flush=True)
    return out


def main(cmd="all"):
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    H = _hist()
    print("hist", H.n, round(time.time() - t0, 1), flush=True)
    model = daytype(H)
    print("daytype", json.dumps(model["report"]), flush=True)
    if cmd == "calib":
        store = json.load(open(MD.STORE_PATH, encoding="utf-8"))
    else:
        store = {"v": MD.VERSION, "built": int(time.time()), "data": "data/NQ_5m.csv (TradingView CME NQ1!), data/VIX_1d.csv (CBOE)",
                 "bots": {}}
        for bot, fn in (("lit", lit_rows), ("atlas", atlas_rows), ("blitz", blitz_rows)):
            rows = fn(H, model)
            store["bots"][bot] = {"cols": cols_for(bot), "rows": rows,
                                  "src": {"lit": "run lit_live settings (tools/lit_final.run on live_model.json lit)",
                                          "atlas": "research/runs/atlas_funded_live.json",
                                          "blitz": "research/scalp/na_best_trades.json"}[bot]}
            print(bot, len(rows), round(time.time() - t0, 1), flush=True)
        with open(MD.STORE_PATH, "w", encoding="utf-8") as fh:
            json.dump(store, fh, separators=(",", ":"), default=MD._jd)
    cal = {"v": MD.VERSION, "built": int(time.time()), "similar": calibrate(store), "daytype": model}
    with open(MD.CALIB_PATH, "w", encoding="utf-8") as fh:
        json.dump(cal, fh, indent=1, default=MD._jd)
    print("done", round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
