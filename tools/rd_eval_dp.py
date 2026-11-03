"""Night R&D 2026-11-03: the OPTIMAL eval size for Zlarior (LIT) on the MFFU Builder 50K, by dynamic programming.
research/writeups/2026-11-03-eval-dp.md. Paper research only: nothing in engine/ or live_model*.json changes.

Question: the live eval sizing (two_week: micros so one winner covers what is left to +$3,000, capped at 80% of the room
to the trailing floor and the $1,000 soft daily loss) is a hand-made rule. Is there a better size for each eval STATE
(balance, peak = where the trailing floor sits, sessions left of the 10) when the goal is the owner's: pass within 10
sessions and fail as little as possible?

Method (new; eval-sizing.md / uprisk.md / eval-cost.md / lit-edge-2026-10-30.md only tried one rule for every state):
  1. Backward induction over 10 sessions on a $25 grid of (balance, peak). Each session is drawn from the 128 real Jan-Jun
     2026 LIT sessions (H1 = the pick half; 80 trades, 48 empty sessions), the trade units of tools/uprisk.py (1m fills,
     slippage in the prices, $1.90 a micro, the trade's own worst open loss for the intraday floor).
     Action = (k, f): micros = ceil(k x what is left to the target / the trade's target $ a micro), capped at f x the room
     and the soft daily loss, max 40 (k 1 / f 0.8 = the live rule). 7 k x 4 f = 28 actions.
     Objective J = P(pass within 10) - lam x P(fail or stuck within 10), lam in {0, 0.5, 1, 2}.
  2. The policy table (session left x balance x peak -> k, f) is frozen and played through the REAL eval code
     (tools/uprisk.Eval -> engine/sizing.lit_qty with that state's need_buf / room_f; after session 10 the live after_mode
     safe_eval, exactly as live) on the 1,000 Monte Carlo paths of uprisk (5-session blocks, seed 23) of H1 (in-sample),
     H2 (Jul-Oct 2026, the check) and 2021-25 (5m reference), plus the real-order rolling windows, plus the whole MFFU
     slot for 6 months (eval -> funded at the live funded size -> payouts -> next eval, $91.80 each).

    python -X utf8 tools/rd_eval_dp.py            # all lams -> research/lit/rd_eval_dp.json + runs rd_evaldp_*
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import uprisk as U  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "rd_eval_dp.json")
G = 25.0
TGT, MLL, LOCK, DLL, STUCK, MAXQ = 3000.0, 2000.0, 100.0, 1000.0, 200.0, 40
PV, COMM, SLIP = 2.0, 1.90, 0.25
KS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
FS = (0.4, 0.6, 0.8, 1.0)
ACTS = [(k, f) for k in KS for f in FS]
H = 10
BAL = np.arange(-2000.0, TGT + 1e-9, G)          # 201
PEAK = np.arange(0.0, 2100.0 + 1e-9, G)          # 85 (floor locks at +100 once the peak is 2,100)


def floor_of(peak):
    return np.minimum(peak - MLL, LOCK)


def session_samples(S, BY, span="H1"):
    a, z = U.span_ix(S, span)
    return [BY[i] for i in range(a, z)]


def step_grid(bal, peak, sample, k, f):
    """Vectorised one session for every state: -> (newbal, newpeak, outcome) outcome 1 pass, -1 fail/stuck, 0 go on."""
    fl = floor_of(peak)
    out = np.zeros_like(bal)
    nb = bal.copy()
    for t in sample:
        if not qty_for(t["risk"]):
            continue
        need = TGT - bal
        win1 = t["tgt"] * PV - COMM
        q = np.maximum(1, np.ceil(need * k / win1 - 1e-9))
        loss1 = (t["risk"] + SLIP) * PV + COMM
        room = bal - fl
        cap_r = np.floor(f * np.maximum(0.0, room) / loss1 + 1e-9)
        cap_d = math.floor(DLL / ((t["risk"] + 0.5) * PV + COMM) + 1e-9)
        q = np.minimum(np.minimum(q, cap_r), min(cap_d, MAXQ))
        q = np.where(cap_r < 1, 0, q)
        if cap_d < 1:
            q[:] = 0
        pnl = t["pts"] * PV * q - COMM * q
        low = np.minimum(np.minimum(0.0, t["w1"] * PV * q - COMM * q), pnl)
        dl = low <= -DLL
        pnl = np.where(dl, -DLL - SLIP * PV * q, pnl)
        low = np.where(dl, pnl, low)
        failed = (bal + low <= fl) & (q > 0)
        nb = np.where(failed, nb, bal + pnl)
        out = np.where(failed, -1, out)
    npk = np.minimum(np.maximum(peak, nb), 2100.0)
    nfl = np.minimum(np.maximum(fl, np.maximum(peak, nb) - MLL), LOCK)
    out = np.where((out == 0) & (nb <= fl), -1, out)
    out = np.where((out == 0) & (nb >= TGT), 1, out)
    out = np.where((out == 0) & (nb - nfl < STUCK), -1, out)
    return nb, npk, out


def solve(samples, lam):
    """Backward induction. V[h] over the (bal, peak) grid with h sessions left. Returns policy[h] (index into ACTS)."""
    Bm, Pm = np.meshgrid(BAL, PEAK, indexing="ij")
    b, p = Bm.ravel(), Pm.ravel()
    V = np.zeros(Bm.shape)                      # h = 0: open at the end = 0
    pols = {}
    # precompute transitions per action x sample (independent of h)
    trans = []
    for (k, f) in ACTS:
        rows = []
        for s in samples:
            nb, npk, o = step_grid(b, p, s, k, f)
            bi = np.clip(np.rint((nb - BAL[0]) / G).astype(int), 0, len(BAL) - 1)
            pi = np.clip(np.rint(npk / G).astype(int), 0, len(PEAK) - 1)
            rows.append((bi, pi, o))
        trans.append(rows)
    for h in range(1, H + 1):
        Q = np.zeros((len(ACTS), b.size))
        for ai in range(len(ACTS)):
            acc = np.zeros(b.size)
            for bi, pi, o in trans[ai]:
                acc += np.where(o == 1, 1.0, np.where(o == -1, -lam, V[bi, pi]))
            Q[ai] = acc / len(samples)
        best = Q.argmax(axis=0)
        # ties -> prefer the live action (k 1, f 0.8) so the table only differs where it matters
        live = ACTS.index((1.0, 0.8))
        tie = Q[live] >= Q.max(axis=0) - 1e-12
        best = np.where(tie, live, best)
        V = Q.max(axis=0).reshape(Bm.shape)
        pols[h] = best.reshape(Bm.shape)
    return pols, V


class DPEval(U.Eval):
    """The real eval code with the state's (need_buf, room_f) from the DP table during sessions 1..10."""

    def __init__(self, cfg, pols, plan="builder50k"):
        super().__init__(cfg, plan)
        self.pols = pols

    def step(self, ts):
        h = H - self.s                       # sessions left including this one (self.s is incremented in super().step)
        if 1 <= h <= H:
            bi = int(np.clip(round((self.bal - BAL[0]) / G), 0, len(BAL) - 1))
            pi = int(np.clip(round(max(0.0, self.peak) / G), 0, len(PEAK) - 1))
            k, f = ACTS[int(self.pols[h][bi, pi])]
            self.cfg["two_week"]["need_buf"] = k
            self.cfg["two_week"]["room_f"] = f
        else:
            self.cfg["two_week"]["need_buf"] = 1.0
            self.cfg["two_week"]["room_f"] = 0.8
        return super().step(ts)


def make_eval_factory(pols):
    import copy
    base = U.ecfg_of({})
    return lambda cfg=None, plan="builder50k": DPEval(copy.deepcopy(base), pols, plan)


def run_all(n=1000):
    S, BY = U.load()
    smp = session_samples(S, BY, "H1")
    P = {sp: U.mc_paths(S, sp, n, length=60) for sp in ("H1", "H2", "REF")}
    P6 = {sp: U.mc_paths(S, sp, n) for sp in ("H1", "H2", "REF")}
    res = {}
    orig_eval = U.Eval
    variants = [("live", None, {}), ("rf70", None, {"room_f": 0.7}), ("rf60", None, {"room_f": 0.6}),
                ("rf55_wk1200", None, {"room_f": 0.55, "wk_loss_usd": 1200})] + \
               [(f"lam{lam:g}", lam, {}) for lam in (0.0, 0.1, 0.25, 0.5, 1.0)]
    for vid, lam, var in variants:
        if lam is None:
            fac = None
        else:
            pols, V = solve(smp, lam)
            fac = make_eval_factory(pols)
            # where does the table differ from live? share of reachable-ish states (bal >= -1500, h 10 start state)
            Bm, Pm = np.meshgrid(BAL, PEAK, indexing="ij")
            ok = (Bm <= Pm + 1e-9) & (Bm - floor_of(Pm) >= STUCK) & (Bm < TGT)
            live = ACTS.index((1.0, 0.8))
            diff = {h: round(100.0 * float(((pols[h] != live) & ok).sum()) / float(ok.sum()), 1) for h in (10, 5, 1)}
            st0 = ACTS[int(pols[H][int((0 - BAL[0]) / G), 0])]
            ks = {h: round(float(np.mean([ACTS[a][0] for a in pols[h][ok]])), 2) for h in (10, 5, 1)}
            fs = {h: round(float(np.mean([ACTS[a][1] for a in pols[h][ok]])), 2) for h in (10, 5, 1)}
        row = {}
        try:
            if fac is not None:
                U.Eval = fac
            for sp in ("H1", "H2", "REF"):
                m = U.eval_mc(BY, P[sp], U.ecfg_of(dict(var)), horizon=60)
                if sp != "REF":
                    m["roll"] = U.eval_rolling(BY, S, sp, U.ecfg_of(dict(var)), h=10, horizon=40)
                    m["roll15"] = U.eval_rolling(BY, S, sp, U.ecfg_of(dict(var)), h=15, horizon=40)
                L = U.life(BY, P6[sp], U.ecfg_of(dict(var)), U.UP50)
                m["slot_m"], m["slot_p10"], m["slot_pneg"], m["evals6"] = L["net_m"], L["net_p10"], L["p_neg"], L["evals"]
                row[sp] = m
        finally:
            U.Eval = orig_eval
        if lam is not None:
            row["table"] = {"differs_from_live_pct": diff, "start_action": st0, "mean_k": ks, "mean_f": fs}
        res[vid] = row
        print(vid, " | ".join(f"{sp} p10/f10 {row[sp]['p10']}/{row[sp]['f10']} med {row[sp]['pass_med']} slow {row[sp]['slow_pass']} "
                               f"slot ${row[sp]['slot_m']}/mo" for sp in ("H1", "H2", "REF")), row.get("table", ""), flush=True)
    return res


def eval_path(S, BY, fac):
    """Back-to-back evals on the real session order (2021-11 -> 2026-10-16): a new eval the session after a pass / fail /
    stuck. One row per traded session (the session's eval P&L), for tools/runlib."""
    T, k = [], 0
    e = fac()
    for i, d in enumerate(S):
        b0 = e.bal
        fl0 = e.floor
        r = e.step(BY[i])
        pnl = (fl0 - b0) if r == "fail" and e.bal == b0 else (e.bal - b0)
        if BY[i] and abs(pnl) > 1e-9:
            t0 = BY[i][0]
            dd = dt.date.fromisoformat(d)
            et = int(dt.datetime(dd.year, dd.month, dd.day, 14, 0, tzinfo=dt.timezone.utc).timestamp())
            T.append({"day": d, "entry_t": et, "exit_t": et + 60, "dir": 1, "r": round(t0["pts"] / t0["risk"], 3), "pnl": round(pnl, 2),
                      "risk_pts": t0["risk"], "qty": 0, "risk_usd": 0.0, "half": False, "exit": r or "", "trigger": "eval",
                      "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": None})
        if r:
            k += 1
            e = fac()
    return T


def save_runs(res, picks=("lam0.25", "lam0.5")):
    import copy
    from tools import runlib as rl
    S, BY = U.load()
    smp = session_samples(S, BY, "H1")
    base = lambda: U.Eval(U.ecfg_of({}))  # noqa: E731
    T = eval_path(S, BY, base)
    rl.save("rd_evaldp_live", "Eval path: live two_week sizing (reference for the DP tables)", "risk",
            "Night R&D 2026-11-03: is there a better eval size for each eval state?", params={"strategy": "lit"},
            sizing={"mode": "two_week", "room_f": 0.8, "need_buf": 1.0}, trades=T, scored=rl.score(T, S), status="info",
            verdict="Reference: back-to-back MFFU 50K evals on the real order with today's two_week sizing.",
            notes="tools/rd_eval_dp.py; one row per traded eval session; $1.90 a micro.", writeup="2026-11-03-eval-dp", tags=["eval", "dp"])
    for vid in picks:
        lam = float(vid[3:])
        pols, _ = solve(smp, lam)
        fac = make_eval_factory(pols)
        T = eval_path(S, BY, fac)
        r = res.get(vid, {})
        v = (f"DP table fit on 2026 H1 (lam {lam:g}). MC 2-week pass/fail H1 {r['H1']['p10']}/{r['H1']['f10']}, H2 {r['H2']['p10']}/{r['H2']['f10']}, "
             f"2021-25 {r['REF']['p10']}/{r['REF']['f10']} vs live {res['live']['H1']['p10']}/{res['live']['H1']['f10']}, "
             f"{res['live']['H2']['p10']}/{res['live']['H2']['f10']}, {res['live']['REF']['p10']}/{res['live']['REF']['f10']}; "
             f"6-month MFFU slot ${r['H1']['slot_m']} / ${r['H2']['slot_m']} / ${r['REF']['slot_m']} a month vs live "
             f"${res['live']['H1']['slot_m']} / ${res['live']['H2']['slot_m']} / ${res['live']['REF']['slot_m']}.") if r else ""
        rl.save(f"rd_evaldp_{vid.replace('.', '')}", f"Eval path: DP-optimal size per eval state (lam {lam:g})", "risk",
                "Night R&D 2026-11-03: is there a better eval size for each eval state?", params={"strategy": "lit"},
                sizing={"mode": "two_week", "dp_lam": lam, "fit": "2026 H1"}, trades=T, scored=rl.score(T, S), status="rejected",
                verdict=v + " Fewer fails at almost the same 2-week pass rate, but less slot money than live: not adopted.",
                notes="tools/rd_eval_dp.py; one row per traded eval session; $1.90 a micro.", writeup="2026-11-03-eval-dp", tags=["eval", "dp"])
        print("saved", vid, flush=True)


def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 1000
    if "save" in sys.argv:
        save_runs(json.load(open(OUT, encoding="utf-8"))["res"])
        return
    res = run_all(n)
    out = {"built": dt.date.today().isoformat(), "n": n, "acts": ACTS, "grid": G, "horizon": H, "fit": "2026 H1 sessions", "res": res}
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("->", OUT)


if __name__ == "__main__":
    main()
