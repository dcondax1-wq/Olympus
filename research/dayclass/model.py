"""Walk-forward multinomial logistic day-type model per checkpoint + OOS accuracy vs baselines (DESIGN.md). PAPER RESEARCH ONLY.

    python -X utf8 research/dayclass/model.py   -> research/dayclass/preds.csv + accuracy.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import features as F  # noqa: E402

CL = F.CLASSES
K = len(CL)
C0 = ["p_rng", "p_loc", "t1", "er5", "vix", "vix_chg", "vix_term", "vix_short", "vxn_spread",
      "pt_range", "pt_trend_up", "pt_trend_down", "pt_reversal", "pt_news_exp", "dow0", "dow4"]
C1 = C0 + ["c1_on_rng", "c1_vs_close", "c1_pos_prior", "c1_on_dir"]
C2 = C0 + ["c2_on_rng", "c2_gap", "c2_open_prior", "c2_open_vwap", "c2_pre_move", "c2_open_on"]
C3 = C2 + ["c3_ib_rng", "c3_ib_loc", "c3_ib_move", "c3_odrive", "c3_brk_hi", "c3_brk_lo", "c3_disp_n", "c3_disp_net", "c3_ib_vol"]
CHECK = {"C0": C0, "C1": C1, "C2": C2, "C3": C3, "C2es": C2 + ["es_on_same"], "C3es": C3 + ["es_on_same", "es_ib_same"]}
LAM = 1.0
MIN_TRAIN = 150


def prep(D):
    D = D.copy()
    for c in CL:
        D["pt_" + c] = (D["p_type"] == c).astype(float)
    D["dow0"] = (D["dow"] == 0).astype(float)
    D["dow4"] = (D["dow"] == 4).astype(float)
    D["month"] = D["day"].str[:7]
    D["yi"] = D["y"].map({c: i for i, c in enumerate(CL)})
    return D


def fit(X, y, lam=LAM, iters=400, lr=0.5):
    n, p = X.shape
    W = np.zeros((p + 1, K))
    Xb = np.c_[np.ones(n), X]
    Y = np.eye(K)[y]
    for _ in range(iters):
        Z = Xb @ W
        Z -= Z.max(1, keepdims=True)
        P = np.exp(Z)
        P /= P.sum(1, keepdims=True)
        G = Xb.T @ (P - Y) / n
        G[1:] += lam * W[1:] / n
        W -= lr * G
    return W


def predict(W, X):
    Z = np.c_[np.ones(len(X)), X] @ W
    Z -= Z.max(1, keepdims=True)
    P = np.exp(Z)
    return P / P.sum(1, keepdims=True)


def walk(D, cols, es_only=False):
    D = D if not es_only else D[D[cols[-1]].notna()]
    out = []
    months = sorted(D["month"].unique())
    for mo in months:
        tr = D[D["month"] < mo]
        te = D[D["month"] == mo]
        if len(tr) < (MIN_TRAIN if not es_only else 120) or te.empty:
            continue
        med = tr[cols].median()
        Xtr = tr[cols].fillna(med).values.astype(float)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        W = fit((Xtr - mu) / sd, tr["yi"].values)
        P = predict(W, (te[cols].fillna(med).values.astype(float) - mu) / sd)
        clim = np.bincount(tr["yi"].values, minlength=K) / len(tr)
        for (_, r), p in zip(te.iterrows(), P):
            out.append({"day": r["day"], "span": r["span"], "y": r["yi"], "p": p, "clim": clim, "maj": int(np.argmax(clim)),
                        "prev": CL.index(r["p_type"]) if isinstance(r["p_type"], str) else 0})
    return out


def score(rows):
    if not rows:
        return None
    y = np.array([r["y"] for r in rows])
    P = np.array([r["p"] for r in rows])
    Cm = np.array([r["clim"] for r in rows])
    top = P.argmax(1)
    eps = 1e-9
    o = {"n": len(rows), "acc": round(100 * float((top == y).mean()), 1),
         "maj_acc": round(100 * float((np.array([r["maj"] for r in rows]) == y).mean()), 1),
         "prev_acc": round(100 * float((np.array([r["prev"] for r in rows]) == y).mean()), 1),
         "logloss": round(float(-np.log(P[np.arange(len(y)), y] + eps).mean()), 4),
         "clim_logloss": round(float(-np.log(Cm[np.arange(len(y)), y] + eps).mean()), 4)}
    pc = {}
    for k, c in enumerate(CL):
        tp = int(((top == k) & (y == k)).sum())
        pc[c] = {"pred": int((top == k).sum()), "true": int((y == k).sum()),
                 "prec": round(100 * tp / max(1, (top == k).sum()), 1), "rec": round(100 * tp / max(1, (y == k).sum()), 1)}
    o["per_class"] = pc
    # trend-vs-not (binary on P(trend_up)+P(trend_down) >= 0.5) and direction among predicted trend
    pt = P[:, 1] + P[:, 2]
    yt = (y == 1) | (y == 2)
    base_t = float(yt.mean())
    o["trend_base"] = round(100 * base_t, 1)
    pick = pt >= 0.35
    o["trend_pred_n"] = int(pick.sum())
    o["trend_hit_when_pred"] = round(100 * float(yt[pick].mean()), 1) if pick.any() else None
    o["trend_brier"] = round(float(((pt - yt) ** 2).mean()), 4)
    o["trend_brier_clim"] = round(float(((Cm[:, 1] + Cm[:, 2] - yt) ** 2).mean()), 4)
    dpick = pick & yt
    if dpick.any():
        o["trend_dir_acc"] = round(100 * float(((P[dpick, 1] > P[dpick, 2]) == (y[dpick] == 1)).mean()), 1)
    return o


def run():
    D = prep(F.build())
    res, preds = {}, {}
    for ck, cols in CHECK.items():
        rows = walk(D, cols, es_only=ck.endswith("es"))
        preds[ck] = rows
        res[ck] = {sp: score([r for r in rows if r["span"] == sp]) for sp in ("2021-25", "H1", "H2")}
        res[ck]["all"] = score(rows)
        gate = all(res[ck][sp] and res[ck][sp]["acc"] >= res[ck][sp]["maj_acc"] + 3 and
                   res[ck][sp]["logloss"] < res[ck][sp]["clim_logloss"] for sp in ("2021-25", "H1", "H2"))
        res[ck]["kill_gate_pass"] = gate
        for sp in ("2021-25", "H1", "H2", "all"):
            s = res[ck][sp]
            if s:
                print(f"{ck:5s} {sp:8s} n{s['n']:4d} acc {s['acc']:5.1f} maj {s['maj_acc']:5.1f} prev {s['prev_acc']:5.1f} | "
                      f"LL {s['logloss']:.3f} clim {s['clim_logloss']:.3f} | trend base {s['trend_base']} hit@pred {s['trend_hit_when_pred']}"
                      f" (n{s['trend_pred_n']}) dir {s.get('trend_dir_acc')} | brier {s['trend_brier']} vs {s['trend_brier_clim']}")
        print(f"{ck} kill-gate {'PASS' if gate else 'FAIL'}", flush=True)
    flat = []
    for ck, rows in preds.items():
        for r in rows:
            flat.append({"ck": ck, "day": r["day"], "y": CL[r["y"]], **{"p_" + c: round(float(r["p"][k]), 4) for k, c in enumerate(CL)}})
    pd.DataFrame(flat).to_csv(os.path.join(HERE, "preds.csv"), index=False)
    with open(os.path.join(HERE, "accuracy.json"), "w") as fh:
        json.dump(res, fh, indent=1)
    return res


if __name__ == "__main__":
    run()
