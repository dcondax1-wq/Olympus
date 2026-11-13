"""Eval guard (team G2, 2026-11-13): risk of ruin of the two evals the owner trades live from tonight, FROM THEIR CURRENT
STATE, under today's sizing and under other room shares. research/writeups/eval-guard-2026-11-13.md. Paper research only:
reads live_model.json / the research trades, writes research/lit/eval_guard.json and runs eval_guard_* (tools/runlib), never
touches live_model*.json or second_model.json.

Accounts (state at the owner's last report, docs/TONIGHT_EVAL.md, 2026-11-07):
  Zlarior  MFFU Builder 50K, LIT. Room $1,145 of the $2,000 EOD trailing max loss. Anchor of 2026-10-23 (engine/launch_prep):
           balance $49,710.80, floor $48,168.20, i.e. the EOD high was $50,168.20. The floor only moves up, and the room fell, so
           the floor is assumed unchanged: balance = $48,168.20 + $1,145 = $49,313.20 (-$686.80 vs start), still needed to pass
           $3,686.80. Eval session 20 (eval_start 2026-10-19).
  ATLAS    MFFU Builder 25K, EMA + MACD + S/R (tools/atlas.py BASE). Room $822 of $1,000. No anchor in the repo: the EOD high is
           assumed to be the start (floor $24,000), balance $24,822 (-$178), still needed $1,678. Eval session 14 (started the
           session after the 2026-10-25 launch prep).
  Sensitivity: the other end (Zlarior's EOD high at the floor lock, i.e. need $3,000 + the balance gap) is in `--sens`.

Sizing (the real engine code, called per trade): LIT = engine/sizing.lit_qty on live_model.json lit_sizing (tools/uprisk
ecfg_of), ATLAS = tools/atlas.q_variant = engine/account_b.qty on the 25K preset (+ dll_guard), 2 trades a day, one position.
The code counts eval sessions from eval_start; after session two_week_until (10) it sizes in after_mode safe_eval (LIT: the
model's $800 size capped at 60% of the room; ATLAS 25K preset: 30%). Both evals are past session 10, so tonight the code sizes
in safe_eval, NOT in two_week at 80% (row "as coded"). The two_week rows restart the session count tonight (what
docs/TONIGHT_EVAL.md describes: "never more than 80% of the room, at most about $916 on one trade").

Rules compared (rows): as coded | two_week room_f 0.8 / 0.6 / 0.5 / 0.4 | two_week 0.8 + protect (room < $X -> a full
stop-out <= 35% of the room) | safe_eval at 0.6 / 0.4.

Monte Carlo: whole calendar weeks drawn with replacement from one half (H1 = Jan-Jun 2026 pick, H2 = Jul-Oct 2026 check,
REF = 2021-25 reference), 2,000 paths of 60 sessions, seed 7. Stuck (room under $200 / $100: not even 1 micro of a normal
stop fits) counts as a fail (the eval is dead, no reset). Second layer (`--worlds`): the half's weeks are themselves resampled
(100 worlds x 200 paths) to give an 80% band on P(pass in 10).

$ per eval = P(pass within 60 sessions) x the funded account's 6-month payout to the owner (uprisk.md: 50K $929 / $915 a
month H1 / H2 at the live funded rule, REF ~$66; atlas-funded.md: 25K ATLAS $582 / $517, REF ~$50) - the eval price
($91.80 / $43). The price is already paid for these two evals, so "$ from now" = the same without the price.

    python -X utf8 tools/eval_guard.py [--n 2000] [--worlds] [--sens] [--no-save]
"""
from __future__ import annotations

import argparse
import collections
import copy
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402
from tools import uprisk as UP  # noqa: E402

PV, COMM, SLIP = 2.0, 1.90, 0.25
OUT = os.path.join(ROOT, "research", "lit", "eval_guard.json")
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "REF": ("2021-11-01", "2025-12-31")}
HORIZON = 60
EXTRA_TICKS = 0.0          # --slip: extra slippage per round trip on top of the 1 tick already in the prices (entry share = half)

ACCTS = {
    "zlarior": {"label": "Zlarior (LIT, Builder 50K)", "plan": "builder50k", "tgt": 3000.0, "mll": 2000.0, "lock": 100.0,
                "dll": 1000.0, "maxq": 40, "stuck": 200.0, "price": 91.80, "max_day": 1,
                "bal0": 49313.20 - 50000.0, "floor0": 48168.20 - 50000.0, "session0": 20, "safe_cap": 0.6,
                "vf": {"H1": 6 * 929.0, "H2": 6 * 915.0, "REF": 6 * 66.0}},
    "atlas": {"label": "ATLAS (Builder 25K)", "plan": "builder25k", "tgt": 1500.0, "mll": 1000.0, "lock": 100.0,
              "dll": 600.0, "maxq": 20, "stuck": 100.0, "price": 43.0, "max_day": 2,
              "bal0": -178.0, "floor0": -1000.0, "session0": 14, "safe_cap": 0.3,
              "vf": {"H1": 3494.0, "H2": 3100.0, "REF": 6 * 50.0}},
}


# ================================================================================================ trades by session
def lit_by_day():
    return UP.trades(("T-2026", "REF-"))


def atlas_by_day():
    from tools import atlas as A
    by = collections.defaultdict(list)
    for u in A.account_units(A.BASE):
        by[u["day"]].append(u)
    for d in by:
        by[d].sort(key=lambda t: t["entry_t"])
    return dict(by)


def weeks_of(S, span):
    a, z = SPANS[span]
    W = collections.OrderedDict()
    for d in S:
        if a <= d <= z:
            y, w, _ = dt.date.fromisoformat(d).isocalendar()
            W.setdefault((y, w), []).append(d)
    return list(W.values())


def paths_of(weeks, n, length=HORIZON, seed=7):
    rng = np.random.default_rng(seed)
    P = []
    for _ in range(n):
        s = []
        while len(s) < length:
            s.extend(weeks[int(rng.integers(0, len(weeks)))])
        P.append(s[:length])
    return P


# ================================================================================================ sizing
_LITCFG = {}


def lit_cfg(rule):
    k = json.dumps(rule, sort_keys=True)
    if k not in _LITCFG:
        c = UP.ecfg_of({})
        if rule.get("room_f") is not None:
            c["two_week"]["room_f"] = rule["room_f"]
        if rule.get("safe_cap") is not None:
            c["safe_cap"] = rule["safe_cap"]
        if rule.get("mode") == "safe_eval":
            c["mode"] = "safe_eval"
        if rule.get("until"):
            c["two_week_until"] = rule["until"]
        _LITCFG[k] = {kk: vv for kk, vv in c.items() if not kk.startswith("_")}
    return _LITCFG[k]


def atlas_V(rule):
    from tools import atlas as A
    V = copy.deepcopy(A.BASE)
    if rule.get("room_f") is not None:
        V["tw"] = {"room_f": rule["room_f"]}
    cfg = {}
    if rule.get("safe_cap") is not None:
        cfg["safe_cap"] = rule["safe_cap"]
    if rule.get("mode") == "safe_eval":
        cfg["mode"] = "safe_eval"
    if rule.get("until"):
        cfg["two_week_until"] = rule["until"]
    if cfg:
        V["cfg"] = cfg
    return V


def qty(acct, rule, t, st):
    if acct == "zlarior":
        m0 = qty_for(t["risk"])
        if not m0:
            return 0
        c = lit_cfg(rule)
        q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, c, room=st["room"], state=st,
                       learning=None, max_micros=40)["qty"]
        q = min(int(q), 40)
    else:
        from tools import atlas as A
        q = int(A.q_variant(t, dict(st), atlas_V(rule)))
    if q > 0 and rule.get("protect"):
        X, f = rule["protect"]
        if st["room"] < X:
            loss1 = (t["risk"] + SLIP) * PV + COMM
            q = min(q, int(f * max(0.0, st["room"]) / loss1 + 1e-9))
    return max(0, q)


# ================================================================================================ one eval from today's state
MICROS = [0]


def run_eval(acct, rule, seq, BY, rec=None):
    """-> (outcome "pass" | "fail" | "stuck" | "open", sessions used, max $ risked on one trade)."""
    A = ACCTS[acct]
    bal, floor = A["bal0"], A["floor0"]
    peak = floor + A["mll"]
    s0 = A["session0"] if rule.get("count") == "coded" else 0
    max_risk, dtr = 0.0, 1
    for k, day in enumerate(seq):
        sess = s0 + k + 1
        cum, busy, n = 0.0, 0, 0
        traded = False
        for t in BY.get(day, ()):
            if cum <= -A["dll"] or n >= A["max_day"]:
                break
            if t.get("entry_t", 0) < busy:
                continue
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": sess, "n_today": n,
                  "wk_pnl": 0.0, "days_traded": dtr}
            q = qty(acct, rule, t, st)
            if q <= 0:
                continue
            traded = True
            n += 1
            busy = t.get("exit_t", 0)
            pts, w1 = t["pts"] - EXTRA_TICKS * 0.25, t["w1"] - EXTRA_TICKS * 0.125
            pnl = pts * PV * q - COMM * q
            low = min(0.0, w1 * PV * q - COMM * q, pnl)
            MICROS[0] += q
            if rec is not None:
                et = int(t.get("entry_t") or dt.datetime.fromisoformat(day + "T07:00:00+00:00").timestamp())
                rec.append({"day": day, "entry_t": et, "exit_t": int(t.get("exit_t") or et), "dir": int(t.get("dir") or 0),
                            "r": round(pnl / max(1e-9, (t["risk"] * PV + COMM) * q), 3), "pnl": round(pnl, 2),
                            "risk_pts": t["risk"], "qty": q, "risk_usd": round(t["risk"] * PV * q, 2), "half": 0,
                            "exit": str(t.get("exit") or ""), "trigger": str(t.get("src") or "LIT"), "mfe": None, "mae": None,
                            "bars_held": None, "regime": "", "mult": 1.0})
            max_risk = max(max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -A["dll"]:
                pnl = -A["dll"] - cum - SLIP * PV * q
                low = pnl
            if bal + cum + low <= floor:
                return "fail", k + 1, max_risk
            cum += pnl
        bal += cum
        dtr += 1 if traded else 0
        if bal <= floor:
            return "fail", k + 1, max_risk
        peak = max(peak, bal)
        floor = min(max(floor, peak - A["mll"]), A["lock"])
        if bal >= A["tgt"]:
            return "pass", k + 1, max_risk
        if bal - floor < A["stuck"]:
            return "stuck", k + 1, max_risk
    return "open", len(seq), max_risk


def summarize(acct, R, span):
    A = ACCTS[acct]
    n = len(R)
    pas = [u for o, u, _ in R if o == "pass"]
    dead = [u for o, u, _ in R if o in ("fail", "stuck")]
    p10 = 100.0 * sum(1 for u in pas if u <= 10) / n
    f10 = 100.0 * sum(1 for u in dead if u <= 10) / n
    p15 = 100.0 * sum(1 for u in pas if u <= 15) / n
    pev, fev = 100.0 * len(pas) / n, 100.0 * len(dead) / n
    vf = A["vf"][span]
    return {"p10": round(p10, 1), "f10": round(f10, 1), "dec10": round(p10 + f10, 1), "p15": round(p15, 1),
            "p60": round(pev, 1), "f60": round(fev, 1), "open60": round(100.0 - pev - fev, 1),
            "pass_med": float(np.median(pas)) if pas else None,
            "slow_pass": round(100.0 * sum(1 for u in pas if u > 15) / max(1, len(pas)), 1),
            "days_mean": round(float(np.mean([u for _, u, _ in R])), 1),
            "max_risk": round(max(r[2] for r in R)),
            "usd_now": round(pev / 100.0 * vf), "usd_eval": round(pev / 100.0 * vf - A["price"]),
            "usd_10": round(p10 / 100.0 * vf - A["price"])}


def rules_of(acct):
    A = ACCTS[acct]
    X1, X2 = (1000.0, 700.0) if acct == "zlarior" else (600.0, 400.0)
    R = [("as_coded", {"count": "coded"}, f"as coded tonight (session {A['session0']} > 10: safe_eval {A['safe_cap']:.0%})")]
    for rf in (0.8, 0.6, 0.5, 0.4):
        R.append((f"tw_{int(rf * 100)}", {"room_f": rf}, f"two_week room_f {rf} (session count restarted tonight)"))
    R.append((f"tw_80_prot{int(X1)}", {"room_f": 0.8, "protect": [X1, 0.35]}, f"two_week 0.8 + protect: room < ${X1:,.0f} -> stop-out <= 35% of room"))
    R.append((f"tw_80_prot{int(X2)}", {"room_f": 0.8, "protect": [X2, 0.35]}, f"two_week 0.8 + protect: room < ${X2:,.0f} -> stop-out <= 35% of room"))
    R.append((f"tw_60_prot{int(X2)}", {"room_f": 0.6, "protect": [X2, 0.35]}, f"two_week 0.6 + protect: room < ${X2:,.0f} -> stop-out <= 35% of room"))
    R.append(("safe_60", {"mode": "safe_eval", "safe_cap": 0.6}, "safe_eval 60% of room (model size)"))
    R.append(("safe_40", {"mode": "safe_eval", "safe_cap": 0.4}, "safe_eval 40% of room (model size)"))
    for rf in ((0.4, 0.5) if acct == "atlas" else (0.4, 0.5)):
        R.append((f"hold_{int(rf * 100)}", {"room_f": rf, "count": "coded", "until": 80},
                  f"two_week room_f {rf} kept past session 10 (two_week_until 80, eval_start unchanged)"))
    R.append(("hold_80", {"room_f": 0.8, "count": "coded", "until": 80}, "two_week room_f 0.8 kept past session 10 (two_week_until 80)"))
    if acct == "atlas":
        R.append(("safe_30", {"mode": "safe_eval", "safe_cap": 0.3}, "safe_eval 30% of room (model size)"))
    return R


def world_band(acct, rule, weeks, BY, n_worlds=100, n_paths=200, seed=11):
    """80% band of P(pass in 10) / P(fail in 10) / $ per eval when the half's weeks themselves are resampled."""
    rng = np.random.default_rng(seed)
    p10s, f10s = [], []
    for w in range(n_worlds):
        W = [weeks[int(i)] for i in rng.integers(0, len(weeks), len(weeks))]
        P = paths_of(W, n_paths, seed=1000 + w)
        R = [run_eval(acct, rule, seq, BY) for seq in P]
        n = len(R)
        p10s.append(100.0 * sum(1 for o, u, _ in R if o == "pass" and u <= 10) / n)
        f10s.append(100.0 * sum(1 for o, u, _ in R if o in ("fail", "stuck") and u <= 10) / n)
    q = lambda a: [round(float(np.percentile(a, 10)), 1), round(float(np.percentile(a, 90)), 1)]
    return {"p10_band": q(p10s), "f10_band": q(f10s)}


RUN_PICKS = {"zlarior": ("as_coded", "hold_80", "hold_40", "hold_50", "tw_80_prot1000"),
             "atlas": ("as_coded", "hold_80", "hold_50", "hold_40")}


def save_runs(S, BYS, out):
    """The real 2026 sessions back to back from today's state (a new eval from the same state after each pass / fail):
    runs eval_guard_<acct>_<rule> in research/runs (tools/runlib)."""
    from tools import runlib as rl
    S26 = [d for d in S if "2026-01-01" <= d <= "2026-10-16"]
    for acct, rids in RUN_PICKS.items():
        RU = {rid: (rule, lab) for rid, rule, lab in rules_of(acct)}
        for rid in rids:
            rule, lab = RU[rid]
            T, i, res = [], 0, collections.Counter()
            while i < len(S26):
                o, u, _ = run_eval(acct, rule, S26[i:i + HORIZON], BYS[acct], rec=T)
                res[o] += 1
                i += u
            T.sort(key=lambda t: (t["day"], t["entry_t"]))
            row = (out.get("rows", {}).get(acct) or {}).get(rid, {})
            h1, h2 = row.get("H1", {}), row.get("H2", {})
            v = (f"{ACCTS[acct]['label']} from today's state, {lab}. MC (weeks, 2,000 paths): H1 pass/fail in 10 sessions "
                 f"{h1.get('p10')}/{h1.get('f10')}, $ per eval {h1.get('usd_eval')}; H2 {h2.get('p10')}/{h2.get('f10')}, "
                 f"${h2.get('usd_eval')}. Real 2026 back to back: {dict(res)}.")
            rl.save(f"eval_guard_{acct}_{rid}", f"Eval guard {acct}: {lab}", "risk",
                    "Team G2 2026-11-13: risk of ruin of the live evals from their current state, per room share",
                    params={"strategy": "lit" if acct == "zlarior" else "atlas", "plan": ACCTS[acct]["plan"]},
                    sizing={"rule": rule, "state": {k: ACCTS[acct][k] for k in ("bal0", "floor0", "session0")}},
                    trades=T, scored=rl.score(T, S26), status="info", verdict=v,
                    notes="tools/eval_guard.py (research/lit/eval_guard.json); the trades are the real 2026 sessions walked "
                          "back to back, each eval restarted from today's state; $1.90 a micro, 1 tick in the prices.",
                    writeup="eval-guard-2026-11-13", tags=["eval", "risk", acct])
            print("saved run", f"eval_guard_{acct}_{rid}", dict(res), len(T), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--worlds", action="store_true")
    ap.add_argument("--sens", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--slip", action="store_true")
    ap.add_argument("--runs", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    S = UP.sessions()
    BYS = {"zlarior": lit_by_day(), "atlas": atlas_by_day()}
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "n": a.n, "horizon": HORIZON,
           "accounts": {k: {kk: vv for kk, vv in v.items()} for k, v in ACCTS.items()}, "rows": {}}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8"))
            out["rows"] = prev.get("rows", {})
            out["worlds"] = prev.get("worlds", {})
            out["sens"] = prev.get("sens", {})
            out["slip"] = prev.get("slip", {})
        except Exception:
            pass
    W = {sp: weeks_of(S, sp) for sp in SPANS}
    P = {sp: paths_of(W[sp], a.n) for sp in SPANS}
    for acct in ACCTS:
        if a.only and acct != a.only:
            continue
        BY = BYS[acct]
        rows = {}
        for rid, rule, lab in rules_of(acct):
            row = {"rule": rule, "label": lab}
            for sp in SPANS:
                R = [run_eval(acct, rule, seq, BY) for seq in P[sp]]
                row[sp] = summarize(acct, R, sp)
            rows[rid] = row
            h1, h2, rf = row["H1"], row["H2"], row["REF"]
            print(f"{acct:8s} {rid:16s} H1 p10 {h1['p10']:5.1f} f10 {h1['f10']:5.1f} p60 {h1['p60']:5.1f} ${h1['usd_eval']:>6} | "
                  f"H2 p10 {h2['p10']:5.1f} f10 {h2['f10']:5.1f} p60 {h2['p60']:5.1f} f60 {h2['f60']:5.1f} days {h2['days_mean']:4.1f} "
                  f"${h2['usd_eval']:>6} risk ${h2['max_risk']} | REF p10 {rf['p10']:5.1f} f10 {rf['f10']:5.1f} p60 {rf['p60']:5.1f}",
                  flush=True)
        out["rows"][acct] = rows
        if a.worlds:
            out.setdefault("worlds", {}).setdefault(acct, {})
            for rid, rule, lab in rules_of(acct):
                if rid not in ("as_coded", "tw_80", "tw_60", "tw_50", "tw_40", "tw_80_prot1000", "tw_80_prot600",
                               "tw_60_prot700", "tw_60_prot400", "hold_40", "hold_50", "hold_80"):
                    continue
                b = {sp: world_band(acct, rule, W[sp], BY) for sp in ("H1", "H2")}
                out["worlds"][acct][rid] = b
                print(f"  worlds {acct} {rid:16s} H1 p10 {b['H1']['p10_band']} f10 {b['H1']['f10_band']} | "
                      f"H2 p10 {b['H2']['p10_band']} f10 {b['H2']['f10_band']}", flush=True)
    if a.runs:
        save_runs(S, BYS, out)
    if a.slip:
        # real-cost sensitivity on the eval from today's state: extra ticks per round trip (the backtest already has 1 tick on
        # market entries / stop exits and $1.90 a micro); $ per month = micros traded per eval-month x $0.50 a tick
        global EXTRA_TICKS
        sl = {}
        for acct, rids in (("zlarior", ("as_coded", "tw_80", "tw_50", "tw_60_prot700")), ("atlas", ("as_coded", "tw_80", "tw_50", "tw_60_prot400"))):
            RU = {rid: (rule, lab) for rid, rule, lab in rules_of(acct)}
            for x in (0, 1, 2, 4, 8):
                EXTRA_TICKS = float(x)
                for rid in rids:
                    for sp in ("H1", "H2"):
                        MICROS[0] = 0
                        R = [run_eval(acct, RU[rid][0], seq, BYS[acct]) for seq in P[sp]]
                        m = summarize(acct, R, sp)
                        sess = sum(u for _, u, _ in R)
                        m["micros_per_month"] = round(MICROS[0] / max(1, sess) * 21.0, 1)
                        m["usd_per_tick_month"] = round(m["micros_per_month"] * 0.5, 1)
                        sl[f"{acct}:{rid}:{sp}:{x}"] = m
                        print(f"  slip {acct} {rid:14s} {sp} +{x}t p10 {m['p10']:5.1f} f10 {m['f10']:5.1f} p60 {m['p60']:5.1f} "
                              f"${m['usd_eval']:>6}  micros/mo {m['micros_per_month']}", flush=True)
        EXTRA_TICKS = 0.0
        out["slip"] = sl
    if a.sens:
        # Zlarior's other end: the EOD high moved up after the anchor (floor locked at +$100 needs a high of $52,100: not
        # reached); take a high of $50,500 -> floor $48,500, balance $49,645 (need $3,355). ATLAS: an EOD high of $25,300 ->
        # floor $24,300, balance $25,122 (need $1,378).
        sens = {}
        for acct, bal0, floor0 in (("zlarior", -355.0, -1500.0), ("atlas", 122.0, -700.0)):
            A = ACCTS[acct]
            keep = (A["bal0"], A["floor0"])
            A["bal0"], A["floor0"] = bal0, floor0
            for rid, rule, lab in rules_of(acct)[:5]:
                R = [run_eval(acct, rule, seq, BYS[acct]) for seq in P["H2"]]
                sens[f"{acct}:{rid}"] = summarize(acct, R, "H2")
                print(f"  sens {acct} {rid:12s} H2 {sens[f'{acct}:{rid}']}", flush=True)
            A["bal0"], A["floor0"] = keep
        out["sens"] = sens
    if not a.no_save:
        json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
        print("saved", OUT)


if __name__ == "__main__":
    main()
