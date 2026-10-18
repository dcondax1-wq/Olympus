"""LIT funded-account sizing (2026-10-18): after the MFFU Builder 50K eval passes, the goal is payouts without losing the
account. Sizing rule: engine/sizing.funded_qty (lit_sizing mode "funded"). Write-up: research/writeups/lit-funded-sizing.md.

Trades: the exact live LIT trades (research/runs/_cache/lit_2wk_unit_live.json, built by tools/lit_2wk.py build from
tools/lit_tightstop.trun == run lit_live): stop distance after the fill, target distance, weekly-stop multiplier, points and
the worst open points, so any size can be applied path by path.

Funded account (MFFU Builder 50K, as modelled; research/writeups/lit-prop-firms.md + search 2026-10-18):
  floor     end-of-day high - $2,000, locks at start + $100; checked against the worst open loss inside the day
  daily     $1,000 soft daily loss: the position is flattened and the day ends
  payout    at a session's end: balance - $2,100 buffer >= $500, max $2,000 a request, >= 2 traded days in the cycle, best
            day <= 50% of the cycle's profit, first after 2 sessions; 5 sim payouts, then live (the path stops: "graduated")
  split     80% to the trader; payouts lower the balance, never the floor
  costs     $1.40 a micro, 1 tick on market entries and stop exits (in the trade points); max 40 micros
Samples: 1,000 Monte Carlo paths of 126 sessions (6 months; 63 = 3 months) in 5-session blocks from the half (H1 = Jan-Jun
2026 pick, H2 = Jul-Oct 2026 check; the same paths for every config), and back-to-back on real history (a new funded account
the session after one is lost or graduates). 2021-25 (5m entries, PF 1.01) is a reference line only.

  python tools/lit_funded.py grid     # every config -> research/lit/funded.json (1 process)
  python tools/lit_funded.py save     # rl.save the runs lit_funded_*
Paper only.
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import sizing as SZ  # noqa: E402
from tools import lit_2wk as W  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "funded.json")
PV, COMM, SLIP = 2.0, 1.40, 0.25
H3, H6 = 63, 126
N_MC, BLOCK = 1000, 5
A = dict(SZ.FD_50K)


def run_funded(cfg, seq, by, keep=None, hold=0.0, mode="funded"):
    """One funded account over session indices seq. Returns a dict: paid (to the trader, by session), first payout
    session, blown session, graduated session, max drawdown of equity (balance + withdrawn)."""
    mll, dll, lockv = A["mll"], A["dll"], A["lock"]
    bal = peak = 0.0
    floor = -mll
    gross = paid = 0.0
    n_pay, first, last_bal, cyc = 0, None, 0.0, []
    pay_at = []                                    # (session, $ to the trader)
    eq_peak, max_dd, max_risk = 0.0, 0.0, 0.0
    for k, si in enumerate(seq):
        cum = 0.0
        traded = False
        for j, t in enumerate(by[si]):
            if cum <= -dll:
                break
            st = {"room": bal + cum - floor, "cum": cum, "locked": floor >= lockv - 1e-9}
            if isinstance(cfg, str):               # today's modes through lit_qty itself
                from engine.lit import qty_for
                base = max(1, int(qty_for(t["risk"]) * (t.get("wk_m") or 1.0) + 1e-9)) if qty_for(t["risk"]) else 0
                q = SZ.lit_qty(base, {"risk_pts": t["risk"], "size_mult": t.get("wk_m", 1.0)}, {"mode": cfg.split(":")[1]},
                               room=st["room"], learning=None)["qty"]
            else:
                q = SZ.funded_qty(t, st, cfg, acct=A)
            if q <= 0:
                continue
            traded = True
            comm = COMM * q
            pnl = t["pts"] * PV * q - comm
            low = min(0.0, t["w1"] * PV * q - comm, pnl)
            max_risk = max(max_risk, (t["risk"] + SLIP) * PV * q + comm)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(W._rec(t, q, floor - bal - cum, floor - bal - cum))
                eq = gross + floor
                max_dd = min(max_dd, eq - eq_peak)
                return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": k + 1, "grad": None,
                        "max_dd": max_dd, "max_risk": max_risk}
            cum += pnl
            if keep is not None:
                keep.append(W._rec(t, q, pnl, low))
        bal += cum
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        eq = bal + gross
        eq_peak = max(eq_peak, eq)
        max_dd = min(max_dd, eq - eq_peak)
        if traded:
            cyc.append(cum)
        # ---- payout request at the session's end
        if k + 1 < A["first_wait"] or len(cyc) < A["cycle_days"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or (cyc and max(cyc) > A["cons"] * prof):
            continue
        amt = min(bal - A["buffer"] - hold, A["pay_max"])
        if amt < A["pay_min"]:
            continue
        share = amt * A["split"]
        paid += share
        gross += amt
        n_pay += 1
        pay_at.append((k + 1, share))
        first = first or k + 1
        bal -= amt
        last_bal, cyc = bal, []
        if n_pay >= A["max_payouts"]:
            return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": k + 1,
                    "max_dd": max_dd, "max_risk": max_risk}
    return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": None, "max_dd": max_dd,
            "max_risk": max_risk}


_SEQ = {}


def mc_seqs(span, n=N_MC, length=H6, seed=23):
    key = (span, n, length, seed)
    if key not in _SEQ:
        a, z = W.span_idx(span)
        rng = np.random.default_rng(seed)
        out = []
        for _ in range(n):
            s = []
            while len(s) < length:
                b = int(rng.integers(a, z - BLOCK + 1))
                s.extend(range(b, b + BLOCK))
            out.append(s[:length])
        _SEQ[key] = out
    return _SEQ[key]


def mc(cfg, span, hold=0.0, mode="funded"):
    D = W.data()
    R = [run_funded(cfg, s, D["by"], hold=hold, mode=mode) for s in mc_seqs(span)]
    o = {"paths": len(R)}
    for lab, h in (("3m", H3), ("6m", H6)):
        lost = [r for r in R if r["blown"] and r["blown"] <= h]
        paid = [sum(x for k, x in r["pay_at"] if k <= h) for r in R]
        o[f"loss_{lab}"] = round(100.0 * len(lost) / len(R), 1)
        o[f"paid_{lab}"] = round(float(np.mean(paid)), 0)
        o[f"paid_med_{lab}"] = round(float(np.median(paid)), 0)
        o[f"paid_p10_{lab}"] = round(float(np.percentile(paid, 10)), 0)
        o[f"grad_{lab}"] = round(100.0 * sum(1 for r in R if r["grad"] and r["grad"] <= h) / len(R), 1)
        o[f"any_pay_{lab}"] = round(100.0 * sum(1 for r in R if r["first"] and r["first"] <= h) / len(R), 1)
        o[f"lost_no_pay_{lab}"] = round(100.0 * sum(1 for r in lost if not r["first"]) / len(R), 1)
    o["per_month_6m"] = round(o["paid_6m"] / 6.0, 0)
    fr = [r["first"] for r in R if r["first"]]
    o["first_med"] = float(np.median(fr)) if fr else None
    o["max_dd_med"] = round(float(np.median([r["max_dd"] for r in R])), 0)
    o["max_dd_p90"] = round(float(np.percentile([r["max_dd"] for r in R], 10)), 0)
    o["max_risk"] = round(max(r["max_risk"] for r in R), 0)
    return o


def b2b(cfg, span, hold=0.0, mode="funded", keep=None):
    """Real history: a funded account from the span's first session; a new one the session after it is lost or graduates."""
    D = W.data()
    a, z = W.span_idx(span)
    k, n = a, collections.Counter()
    paid, firsts = 0.0, []
    worst = 0.0
    while k < z:
        r = run_funded(cfg, list(range(k, z)), D["by"], keep=keep, hold=hold, mode=mode)
        paid += r["paid"]
        worst = min(worst, r["max_dd"])
        if r["first"]:
            firsts.append(r["first"])
        if r["blown"]:
            n["lost"] += 1
            k += r["blown"]
        elif r["grad"]:
            n["graduated"] += 1
            k += r["grad"]
        else:
            n["open"] += 1
            break
    months = (z - a) / 21.0
    return {"accounts": sum(n.values()), "lost": n["lost"], "graduated": n["graduated"], "open_at_end": n["open"],
            "paid": round(paid), "per_month": round(paid / months), "first_payout_sessions": firsts[:6], "worst_dd": round(worst)}


# ================================================================================================ the configs
def kelly(span="H1"):
    """Full-Kelly fraction of the room on the span's LIT trades: R = 1-micro $ result / 1-micro full stop-out (2 ticks, comm)."""
    D = W.data()
    a, z = W.span_idx(span)
    R = []
    for si in range(a, z):
        for t in D["by"][si]:
            loss1 = (t["risk"] + 2 * SLIP) * PV + COMM
            R.append((t["pts"] * PV - COMM) / loss1)
    R = np.array(R)
    fs = np.linspace(0.005, 0.95, 400)
    g = [np.mean(np.log1p(f * R)) if (1 + f * R).min() > 0 else -1e9 for f in fs]
    i = int(np.argmax(g))
    return {"f_star": round(float(fs[i]), 3), "n": len(R), "mean_r": round(float(R.mean()), 3), "win": round(float((R > 0).mean()), 3)}


def configs():
    C = {}
    # the modes that exist today, run on the funded account
    C["normal"] = "plain:normal"         # lit_sizing mode normal (the model's micros), no cap
    C["eval_mode"] = "plain:eval"        # lit_sizing mode eval ($800 up to 25 pts, 60% room cap, min 1)
    C["normal_guard"] = {"tiers": [[0, 800]], "ref": 20, "room_f": 0.6}
    # fixed $ by the floor's lock
    for pre in (300, 400, 500):
        for post in (800, 1000):
            for rf in (0.6, None):
                C[f"lock_{pre}_{post}_r{rf}"] = {"tiers": [[0, post]], "pre_lock_usd": pre, "ref": 20, "room_f": rf}
    # $ by the cushion (room to the floor)
    T = {"cushA": [[0, 200], [1500, 400], [2500, 800], [3500, 1000]],
         "cushB": [[0, 300], [2000, 600], [3000, 800], [4000, 1000]],
         "cushC": [[0, 250], [1000, 400], [2000, 600], [3000, 800]],
         "cushD": [[0, 400], [2000, 800]],
         "cushE": [[0, 300], [2100, 800]]}
    for nm, tr in T.items():
        for rf in (0.6, None):
            C[f"{nm}_r{rf}"] = {"tiers": tr, "ref": 20, "room_f": rf}
    # % of the room (fractional Kelly)
    for p in (0.05, 0.1, 0.15, 0.2, 0.3):
        for mx in (1000,):
            C[f"pct{int(p * 100)}_max{mx}"] = {"pct": p, "pct_min_usd": 100, "pct_max_usd": mx, "ref": 20, "room_f": None}
    return C


def extras(best):
    """Variations around the shortlisted configs: the weekly stop off, the wide-stop reference, a best-day cap."""
    C = {}
    for nm, c in best.items():
        C[f"{nm}|wk_off"] = {**c, "wk": False}
        C[f"{nm}|ref25"] = {**c, "ref": 25}
        for mw in (1500, 2500):
            C[f"{nm}|maxwin{mw}"] = {**c, "max_win": mw}
    return C


def score_row(o):
    return o["paid_6m"]


def grid():
    out = {"kelly_H1": kelly("H1"), "kelly_H2": kelly("H2"), "rows": {}}
    print("kelly", out["kelly_H1"], out["kelly_H2"], flush=True)
    C = configs()
    for i, (nm, c) in enumerate(C.items()):
        out["rows"][nm] = {"cfg": c, "hold": 0, "H1": mc(c, "H1")}
        if i % 10 == 0:
            print(i, nm, out["rows"][nm]["H1"]["paid_6m"], out["rows"][nm]["H1"]["loss_6m"], flush=True)
    # shortlist on H1: the best expected 6-month payout, and the lowest loss among those within 90% of the best payout
    rows = out["rows"]
    top = sorted(rows, key=lambda k: -rows[k]["H1"]["paid_6m"])[:3]
    best_pay = rows[top[0]]["H1"]["paid_6m"]
    safe = sorted([k for k in rows if rows[k]["H1"]["paid_6m"] >= 0.9 * best_pay], key=lambda k: rows[k]["H1"]["loss_6m"])[:3]
    short = list(dict.fromkeys(top + safe))
    for nm, c in extras({k: rows[k]["cfg"] for k in short}).items():
        rows[nm] = {"cfg": c, "hold": 0, "H1": mc(c, "H1")}
    top = sorted(rows, key=lambda k: -rows[k]["H1"]["paid_6m"])[:5]
    best_pay = rows[top[0]]["H1"]["paid_6m"]
    safe = sorted([k for k in rows if rows[k]["H1"]["paid_6m"] >= 0.9 * best_pay], key=lambda k: rows[k]["H1"]["loss_6m"])[:5]
    short = list(dict.fromkeys(top + safe + ["normal", "eval_mode", "normal_guard"]))
    # payout hold-back on the shortlist
    for nm in [k for k in short if k not in ("normal", "eval_mode")]:
        for hold in (1000,):
            k2 = f"{nm}|hold{hold}"
            rows[k2] = {"cfg": rows[nm]["cfg"], "hold": hold, "H1": mc(rows[nm]["cfg"], "H1", hold=hold)}
            short.append(k2)
    for nm in short:
        r = rows[nm]
        r["H2"] = mc(r["cfg"], "H2", hold=r["hold"])
        r["b2b_H1"] = b2b(r["cfg"], "H1", hold=r["hold"])
        r["b2b_H2"] = b2b(r["cfg"], "H2", hold=r["hold"])
        r["b2b_2021_25"] = b2b(r["cfg"], "2021-25", hold=r["hold"])
    out["shortlist"] = short
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    show(out)


def show(out=None):
    out = out or json.load(open(OUT))
    rows = out["rows"]
    print(f"{'config':44s} | H1 loss3/6 paid3/6 med1st grad6 dd_med | H2 loss3/6 paid3/6 med1st grad6 | b2b H1 lost/acc $/mo | H2 | 21-25")
    for nm in out["shortlist"]:
        r = rows[nm]
        f = lambda o: f"{o['loss_3m']:5.1f}/{o['loss_6m']:5.1f} {o['paid_3m']:6.0f}/{o['paid_6m']:6.0f} {o['first_med'] or 0:5.0f} {o['grad_6m']:5.1f}"
        b = lambda o: f"{o['lost']}/{o['accounts']} {o['per_month']:5d}"
        print(f"{nm:44s} | {f(r['H1'])} {r['H1']['max_dd_med']:6.0f} | {f(r['H2'])} | {b(r['b2b_H1'])} | {b(r['b2b_H2'])} | {b(r['b2b_2021_25'])}")


def save(names):
    """rl.save one run per config: the stored trades are the back-to-back funded path over all of 2021-11 .. 2026-10."""
    from tools import runlib as rl
    out = json.load(open(OUT))
    for nm, rid, title, status in names:
        r = out["rows"][nm]
        T = []
        for span in ("2021-25", "H1", "H2"):
            b2b(r["cfg"], span, hold=r["hold"], keep=T)
        T.sort(key=lambda t: t["entry_t"])
        S = rl.score(T, W.data()["sess"])
        verdict = (f"Funded MFFU Builder 50K, MC 6 months H1 / H2: account lost {r['H1']['loss_6m']}% / {r['H2']['loss_6m']}%, "
                   f"expected payouts ${r['H1']['paid_6m']:,.0f} / ${r['H2']['paid_6m']:,.0f} (${r['H1']['per_month_6m']:,.0f} / "
                   f"${r['H2']['per_month_6m']:,.0f} a month), 3 months lost {r['H1']['loss_3m']}% / {r['H2']['loss_3m']}%, paid "
                   f"${r['H1']['paid_3m']:,.0f} / ${r['H2']['paid_3m']:,.0f}, median first payout session {r['H1']['first_med']} / "
                   f"{r['H2']['first_med']}, 5 payouts within 6 months {r['H1']['grad_6m']}% / {r['H2']['grad_6m']}%. Back to back "
                   f"H1 {r['b2b_H1']}, H2 {r['b2b_H2']}, 2021-25 (ref) {r['b2b_2021_25']}.")
        rl.save(rid, title, "risk", "After the MFFU eval passes: which LIT size maximises $ withdrawn per funded account over "
                "3 / 6 months and keeps the account alive?", params={"lit_sizing": {"mode": "funded", "funded": r["cfg"]},
                                                                       "payout_hold": r["hold"]},
                sizing={"mode": "funded", **r["cfg"]}, trades=T, scored=S, status=status, verdict=verdict,
                notes=("tools/lit_funded.py; sizing engine/sizing.funded_qty; MFFU Builder 50K funded as modelled (EOD trailing "
                       "$2,000 locking at +$100, $1,000 soft daily loss, payout: balance - $2,100 >= $500, max $2,000, best day <= "
                       "50% of the cycle, 2 traded days, 5 sim payouts, 80%). The stored trades are the back-to-back funded path "
                       "(state-dependent size); the run library's eval columns are not the funded numbers: those are in the verdict "
                       "and research/lit/funded.json. 2021-25 = 5m entries, reference only."),
                writeup="lit-funded-sizing", tags=["lit", "lit_funded"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        grid()
    elif cmd == "show":
        show()
    elif cmd == "kelly":
        print(kelly("H1"), kelly("H2"), kelly("2021-25"))
