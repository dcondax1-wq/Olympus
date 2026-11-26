"""Optimal eval sizing policy (research/evalsizer/DESIGN.md, pre-registered). PAPER RESEARCH ONLY.

    python -X utf8 research/evalsizer/sizer.py [--n 1000] [--only T0,D1] [--plans mffu_builder_50k]
        -> research/evalsizer/results.json (+ dp_tables.npz)

Engine = research/plans/rank.py unchanged; ONLY the LIT eval sizing call (engine/sizing.lit_qty inside the eval) is swapped
for the policy under test. Funded sizing, ATLAS lane, every MFFU rule: as rank.py / research/badcase.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "plans"))
sys.path.insert(0, os.path.join(ROOT, "research", "badcase"))
sys.path.insert(0, ROOT)
import rank as R  # noqa: E402

U, RL, AR, SOA, SZ = R.U, R.RL, R.AR, R.SOA, R.SZ
import badcase as BC  # noqa: E402  (sets U.SPAN["Y25"], slot_full)

OUT = os.path.join(HERE, "results.json")
NPZ = os.path.join(HERE, "dp_tables.npz")
MKTS = ("H1", "H2", "REF", "Y25")
PLANS = ("mffu_builder_50k", "mffu_builder_25k", "mffu_rapid_eod_25k")
PV, COMM, SLIP = SZ.TW_PV, SZ.TW_COMM, SZ.TW_SLIP
H = 60                                            # eval sessions the DP plans for (rank.H_EVAL)


def loss1(risk):
    return (risk + SLIP) * PV + COMM


# ================================================================================================ pools
def lit_pool(BY, S, span):
    a, z = U.span_ix(S, span) if span != "ALL" else (0, len(S))
    ts = [t for i in range(a, z) for t in BY[i] if t["strat"] == "LIT"]
    r = np.array([(t["pts"] * PV - COMM) / loss1(t["risk"]) for t in ts])
    return r, len(ts) / float(z - a)


def kelly(r):
    best, fb = -1e9, 0.0
    for f in np.linspace(0.0, 0.99 / max(1e-9, -r.min()), 400):
        g = np.mean(np.log1p(f * r))
        if g > best:
            best, fb = g, f
    return float(fb)


# ================================================================================================ DP
def dp(E, dll, r, n_tr, step):
    """Value iteration, max P(pass within n_tr LIT trades). State (floor, b) on a $step grid. Returns A[n, fi, bi] = $ risk."""
    tgt, mll, lock = E["tgt"], E["mll"], E["lock"]
    bs = np.arange(-mll, tgt + step / 2, step)               # balance grid
    fs = np.arange(-mll, lock + step / 2, step)              # floor grid
    nb, nf = len(bs), len(fs)
    hist, edges = np.histogram(r, bins=80)
    rc = 0.5 * (edges[1:] + edges[:-1])
    w = hist / hist.sum()
    rc, w = rc[w > 0], w[w > 0]
    V = np.zeros((nf, nb))
    V[:, bs >= tgt - 1e-9] = 1.0
    acts = np.arange(0.0, dll + step / 2, step)
    A = np.zeros((n_tr + 1, nf, nb), dtype=np.float32)
    for n in range(1, n_tr + 1):
        Vn = V.copy()
        An = np.zeros((nf, nb))
        for fi, fl in enumerate(fs):
            ok = bs > fl + 1e-9
            bix = np.where(ok & (bs < tgt - 1e-9))[0]
            if not len(bix):
                continue
            b = bs[bix]
            room = b - fl
            best = V[fi, bix].copy()                           # a = 0 (skip): value unchanged
            besta = np.zeros(len(bix))
            for a in acts[1:]:
                can = a < room - 1e-9
                if not can.any():
                    continue
                b2 = b[:, None] + a * rc[None, :]
                fail = b2 <= fl + 1e-9
                f2 = np.minimum(np.maximum(fl, b2 - mll), lock)
                fi2 = np.clip(np.rint((f2 + mll) / step).astype(int), 0, nf - 1)
                bi2 = np.clip(np.rint((b2 + mll) / step).astype(int), 0, nb - 1)
                v2 = np.where(b2 >= tgt - 1e-9, 1.0, np.where(fail, 0.0, V[fi2, bi2]))
                ev = (v2 * w[None, :]).sum(1)
                upd = can & (ev > best + 1e-9)
                best[upd], besta[upd] = ev[upd], a
            Vn[fi, bix], An[fi, bix] = best, besta
        V = Vn
        A[n] = An
    return {"A": A, "bs": bs, "fs": fs, "step": step, "V": V}


# ================================================================================================ the policy switch
POL = {"id": "T0"}
_lit_qty = SZ.lit_qty


def _cfg_room(cfg, rf):
    c = copy.deepcopy(cfg)
    c["two_week"]["room_f"] = rf
    return c


def _need_q(trade, cfg, room, max_micros, state):
    """Today's call with room_f 0.999: every hard ceiling of today (need-cap, strict room, soft day, maxq, min-days, at target)."""
    return _lit_qty(1, trade, _cfg_room(cfg, 0.999), room=room, max_micros=max_micros, state=state, learning=None)["qty"]


def lit_qty(qty, trade, cfg=None, room=None, max_micros=40, state=None, learning="auto"):
    pid = POL["id"]
    if pid == "T0" or state is None or room is None:
        return _lit_qty(qty, trade, cfg, room=room, max_micros=max_micros, state=state, learning=learning)
    A = cfg["two_week"]["acct"]
    tgt, mll = float(A["target"]), float(A["mll"])
    prof, cum = float(state.get("profit") or 0.0), float(state.get("cum") or 0.0)
    need = tgt - prof - cum
    rf = None
    if pid[0] == "R":
        rf = int(pid[1:]) / 100.0
    elif pid in ("BP6", "BP8"):
        rf = (0.6 if pid == "BP6" else 0.8) if need <= 0.5 * tgt else 0.4
    elif pid in ("PR1", "PR2"):
        rf = (0.25 if pid == "PR1" else 0.15) if room < 0.5 * mll else 0.4
    elif pid == "BPR":
        rf = 0.6 if need <= 0.5 * tgt else (0.25 if room < 0.5 * mll else 0.4)
    if rf is not None:
        return _lit_qty(qty, trade, _cfg_room(cfg, rf), room=room, max_micros=max_micros, state=state, learning=learning)
    l1 = loss1(float(trade["risk_pts"]))
    if pid[0] == "F":
        B = int(pid[1:]) / 100.0 * room
    elif pid[0] == "K":
        B = min(int(pid[1:]) / 100.0 * POL["kelly"], 0.6) * room
    elif pid[0] == "D":
        T = POL["dp"]
        b = prof + cum
        fl = b - room
        n = int(max(1, min(T["A"].shape[0] - 1, round((H - float(state.get("session") or 1) + 1) * T["rate"]))))
        fi = int(np.clip(round((fl - T["fs"][0]) / T["step"]), 0, len(T["fs"]) - 1))
        bi = int(np.clip(round((b - T["bs"][0]) / T["step"]), 0, len(T["bs"]) - 1))
        B = float(T["A"][n, fi, bi])
    else:
        raise ValueError(pid)
    qb = int(B / l1 + 1e-9)
    if qb < 1:
        return {"qty": 0, "mult": 0.0, "reasons": [f"{pid}: budget ${B:.0f} < 1 micro"]}
    q = min(qb, _need_q(trade, cfg, room, max_micros, state))
    return {"qty": q, "mult": q / max(1, qty), "reasons": [f"{pid}: ${B:.0f}"]}


SZ.lit_qty = lit_qty
VARIANTS = ("T0", "R25", "R30", "R50", "R60", "F10", "F15", "F20", "F30", "K25", "K50", "BP6", "BP8", "PR1", "PR2", "BPR",
            "D1", "D2")


# ================================================================================================ run
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--only", default="")
    ap.add_argument("--plans", default=",".join(PLANS))
    a = ap.parse_args(argv)
    t0 = time.time()
    AR.rapid_patch(AR.T_at(10))
    S = SOA.data()["S"]
    BYL = RL.mix_by(("LIT",))
    rH1, rateH1 = lit_pool(BYL, S, "H1")
    rAll, rateAll = lit_pool(BYL, S, "ALL")
    kel = kelly(rH1)
    POL["kelly"] = kel
    print(f"pool H1 n={len(rH1)} meanR {rH1.mean():.3f} rate {rateH1:.3f}/sess kelly {kel:.3f} | ALL n={len(rAll)} meanR "
          f"{rAll.mean():.3f} rate {rateAll:.3f}", flush=True)
    PE = {m: U.mc_paths(S, m, a.n, length=R.H_EVAL, seed=7) for m in MKTS}
    PF = {m: U.mc_paths(S, m, a.n, length=R.LEN, seed=23) for m in MKTS}
    only = [v for v in a.only.split(",") if v] or list(VARIANTS)
    out = {"n": a.n, "kelly_H1": kel, "pools": {"H1": [len(rH1), float(rH1.mean()), rateH1], "ALL": [len(rAll), float(rAll.mean()), rateAll]},
           "rows": {}, "dp": {}}
    npz = {}
    for plan in a.plans.split(","):
        sp = R.spec(plan)
        E = sp["E"]
        dll = sp["ev"]().cfg.get("_dll", E["dll"])
        step = 50.0 if "50k" in plan else 25.0
        tabs = {}
        if any(v.startswith("D") for v in only):
            for k, (r, rate) in {"D1": (rH1, rateH1), "D2": (rAll, rateAll)}.items():
                tt = time.time()
                N = int(round(H * rate))
                T = dp(E, dll, r, N, step)
                T["rate"] = rate
                tabs[k] = T
                npz[f"{plan}_{k}"] = T["A"]
                fi0 = 0
                bi0 = int(round((0 - T["bs"][0]) / step))
                out["dp"][f"{plan}_{k}"] = {"N": N, "p_pass_start": float(T["V"][fi0, bi0]), "a_start": float(T["A"][N, fi0, bi0])}
                print(f"DP {plan} {k} N={N} P(pass) from start {T['V'][fi0, bi0]:.3f} a* at start ${T['A'][N, fi0, bi0]:.0f} "
                      f"[{time.time() - tt:.0f}s]", flush=True)
        rows = {}
        for v in only:
            POL.clear()
            POL.update(id=v, kelly=kel)
            if v in tabs:
                POL["dp"] = tabs[v]
            row = {}
            for m in MKTS:
                row[m] = {"eval": R.eval_run(sp, PE[m]), "slot": BC.slot_full(sp, PF[m])}
            rows[v] = row
            print(f"{plan:20s} {v:4s} " + " | ".join(
                f"{m} {row[m]['eval']['pass']}/{row[m]['eval']['fail']}% ~{row[m]['eval']['med_days']}d "
                f"${row[m]['slot']['net_6m']} ${row[m]['slot']['net_per_eval']}/ev" for m in MKTS) + f" [{time.time() - t0:.0f}s]",
                flush=True)
        POL.clear(); POL["id"] = "T0"
        out["rows"][plan] = rows
        if "T0" in rows:
            out.setdefault("pick", {})[plan] = pick(rows)
            print("PICK", plan, out["pick"][plan], flush=True)
    path = OUT if not a.only else OUT.replace(".json", "_partial.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    if npz:
        np.savez_compressed(NPZ if not a.only else NPZ.replace(".npz", "_partial.npz"), **npz)


def pick(rows):
    T = rows["T0"]
    bar = T["H1"]["eval"]["fail"] + 2.0
    el = [(r["H1"]["slot"]["net_6m"], v) for v, r in rows.items() if r["H1"]["eval"]["fail"] <= bar]
    el.sort(reverse=True)
    v = el[0][1]
    P = rows[v]
    beats = {m: P[m]["slot"]["net_6m"] > T[m]["slot"]["net_6m"] for m in ("H2", "REF", "Y25")}
    passok = {m: P[m]["eval"]["pass"] >= T[m]["eval"]["pass"] - 2.0 for m in MKTS}
    card = v != "T0" and all(beats.values()) and all(passok.values())
    rob = max(rows, key=lambda k: min(rows[k][m]["slot"]["net_6m"] - T[m]["slot"]["net_6m"] for m in MKTS))
    best = {m: max(rows, key=lambda k: rows[k][m]["slot"]["net_6m"]) for m in MKTS}
    return {"pick": v, "eligible": len(el), "beats_T0": beats, "pass_ok": passok, "card": card, "robust": rob,
            "robust_min_gain": min(rows[rob][m]["slot"]["net_6m"] - T[m]["slot"]["net_6m"] for m in MKTS), "best_by_market": best}


if __name__ == "__main__":
    main()
