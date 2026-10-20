"""MFFU Builder 25K next to the Builder 50K (owner 2026-10-19: buy a Builder 25K at $63 and trade it with the same LIT bot,
copy trading: same signals, same entry / stop / target, each account sized on its own room).

1. 25K eval sizing: the 50K two_week config C (live_model.json lit_sizing) scaled to the 25K (target covers what is left to
   +$1,500, 60% of the room to the $1,000 EOD trailing floor, the $600 soft daily loss, max 20 micros; after session 10
   safe_eval, no reset) + neighbours. Every size is engine.sizing.lit_qty exactly as the live loop calls it (incl. the day
   guard with the 25K's target / daily loss / 20 micros), $1.90 a micro, 1 tick on stops, the MFFU soft daily loss flattens.
   Exact starts on every session of the half (played to the end of that half) + a Monte Carlo of 2,000 evals x 120
   sessions in 5-session blocks from the half. Pick on H1, check on H2.
2. Copy trading: the 50K (live config C) and the 25K (the pick) on the SAME sessions, started the same day or the 25K 5
   sessions (one week) later: joint 2-week outcomes, correlated risk.
Trades: the exact live LIT signals (tools/lit_2wk unit trades == run lit_live, 120 trades in 2026). Paper only.

  python tools/lit_25k.py grid      -> research/lit/builder_25k.json (sizing grid)
  python tools/lit_25k.py copy      -> research/lit/builder_25k_copy.json
  python tools/lit_25k.py save      -> research/runs/lit_25k_*.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402
from tools import lit_2wk as W  # noqa: E402

PV, COMM, SLIP = 2.0, SZ.TW_COMM, 0.25
PRICE = {"50k": 91.80, "25k": 63.0}
ACC = {"50k": {"target": 3000.0, "mll": 2000.0, "dll": 1000.0, "lock": 100.0, "max_micros": 40},
       "25k": {"target": 1500.0, "mll": 1000.0, "dll": 600.0, "lock": 100.0, "max_micros": 20}}
LM = json.load(open(os.path.join(ROOT, "live_model.json")))["lit_sizing"]
BASE = {k: LM[k] for k in ("two_week", "safe_cap", "eval_ref_stop", "fast_ref_stop", "two_week_until", "after_mode")}
CFG_50K = {**BASE, "mode": "two_week"}                     # the live 50K config C (+ no reset: safe_eval after session 10)
OUT = os.path.join(ROOT, "research", "lit", "builder_25k.json")
OUT_C = os.path.join(ROOT, "research", "lit", "builder_25k_copy.json")
N_MC, MC_LEN = 2000, 120
DEAD = 100.0                # $ of room below which an open eval is stuck (1 micro on a ~46-pt median stop costs ~$95)


def cfg25(tw=None, **kw):
    """A 25K lit_sizing block: config C with the 25K account (sizing.TW_25K) and the 25K day guard."""
    return {**BASE, "mode": "two_week", "two_week": {**BASE["two_week"], "acct": dict(SZ.TW_25K), **(tw or {})},
            "guard": {"target": 1500.0, "dll": 600.0, "max_micros": 20}, **kw}


def configs():
    G = {"C25 (config C scaled)": cfg25()}
    for rf in (0.4, 0.5, 0.7):
        G[f"room {int(rf * 100)}%"] = cfg25({"room_f": rf})
    G["need x1.25"] = cfg25({"need_buf": 1.25})
    G["max $400 a trade"] = cfg25({"max_usd": 800.0})          # max_usd is x acct scale 0.5
    G["max $300 a trade"] = cfg25({"max_usd": 600.0})
    G["weekly stop on"] = cfg25({"wk": True})
    G["after 10: safe_eval 40%"] = cfg25(safe_cap=0.4)
    G["after 10: safe_eval 30%"] = cfg25(safe_cap=0.3)
    G["two_week to the end"] = cfg25(two_week_until=None)
    G["after 15: safe_eval"] = cfg25(two_week_until=15)
    G["room 50% + after 10 safe 40%"] = cfg25({"room_f": 0.5}, safe_cap=0.4)
    G["room 50% + max $400"] = cfg25({"room_f": 0.5, "max_usd": 800.0})
    G["room 50% + after 10 safe 30%"] = cfg25({"room_f": 0.5}, safe_cap=0.3)
    G["room 50% + wk + after 10 safe 40%"] = cfg25({"room_f": 0.5, "wk": True}, safe_cap=0.4)
    G["room 50% + max $400 + after 10 safe 40%"] = cfg25({"room_f": 0.5, "max_usd": 800.0}, safe_cap=0.4)
    G["room 60% + wk + after 10 safe 40%"] = cfg25({"wk": True}, safe_cap=0.4)
    return G


def run(cfg, seq, by, acct="25k", horizon=10 ** 6, keep=None, days=None, rooms=None):
    """One eval over session indices seq (no reset). -> (PASS/FAIL/OPEN, sessions used, max $ at risk, room after each
    session [list])."""
    rooms = [] if rooms is None else rooms
    A = ACC[acct]
    TGT, MLL, DLL, LOCK, MX = A["target"], A["mll"], A["dll"], A["lock"], A["max_micros"]
    bal = peak = 0.0
    floor = -MLL
    mrisk = 0.0
    for k, si in enumerate(seq[:horizon]):
        cum = 0.0
        for j, t in enumerate(by[si]):
            if cum <= -DLL:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": k + 1, "n_today": j}
            base = qty_for(t["risk"])
            m0 = max(1, int(base * (t.get("wk_m") or 1.0) + 1e-9)) if base else 0
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": t.get("wk_m", 1.0)}, cfg,
                           room=st["room"], state=st, max_micros=MX, learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            mrisk = max(mrisk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -DLL:
                pnl = -DLL - cum - SLIP * PV * q
                low = pnl
            if keep is not None:
                keep.append(W._rec(t, q, pnl if bal + cum + low > floor else floor - bal - cum, low))
            if bal + cum + low <= floor:
                if days is not None:
                    days.append(cum + low)
                return "FAIL", k + 1, mrisk, rooms
            cum += pnl
        if days is not None:
            days.append(cum)
        bal += cum
        if bal <= floor:
            return "FAIL", k + 1, mrisk, rooms
        peak = max(peak, bal)
        floor = min(max(floor, peak - MLL), LOCK)
        rooms.append(bal - floor)
        if bal >= TGT:
            return "PASS", k + 1, mrisk, rooms
    return "OPEN", min(len(seq), horizon), mrisk, rooms


def summ(res, avail, acct="25k"):
    """res = [(result, sessions, max risk)], avail = sessions each start could see."""
    o = {"n": len(res)}
    for h in (10, 15):
        R = [r for r, a in zip(res, avail) if a >= h]
        N = len(R) or 1
        o[f"p{h}"] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o[f"f{h}"] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
        # stuck = still open after h sessions with less than DEAD $ of room: the day guard skips almost every trade (1 micro's
        # worst case would reach the floor) and MFFU's 7-day inactivity rule may close it: counted as a failure in "dead"
        o[f"stuck{h}"] = round(100.0 * sum(1 for r in R if not (r[0] in ("PASS", "FAIL") and r[1] <= h)
                                           and len(r[3]) >= h and r[3][h - 1] < DEAD) / N, 1)
        o[f"dead{h}"] = round(o[f"f{h}"] + o[f"stuck{h}"], 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    R = [r for r, a in zip(res, avail) if a >= 10]
    N = len(R) or 1
    p = [r[1] for r in R if r[0] == "PASS"]
    o["pass"] = round(100.0 * len(p) / N, 1)
    o["fail"] = round(100.0 * sum(1 for r in R if r[0] == "FAIL") / N, 1)
    o["open"] = round(100.0 - o["pass"] - o["fail"], 1)
    o["stuck_end"] = round(100.0 * sum(1 for r in R if r[0] == "OPEN" and r[3] and r[3][-1] < DEAD) / N, 1)
    o["pass_med"] = float(np.median(p)) if p else None
    o["slow_pass"] = round(100.0 * sum(1 for d in p if d > 15) / len(p), 1) if p else None
    o["cost_2wk"] = round(PRICE[acct] / (o["p10"] / 100.0)) if o["p10"] else None
    o["cost_pass"] = round(PRICE[acct] / (o["pass"] / 100.0)) if o["pass"] else None
    o["max_risk"] = round(max((r[2] for r in res), default=0))
    return o


_SEQ = {}


def mc_seqs(span, n=N_MC, length=MC_LEN, seed=5):
    key = (span, n, length, seed)
    if key not in _SEQ:
        a, z = W.span_idx(span)
        rng = np.random.default_rng(seed)
        S = []
        for _ in range(n):
            s = []
            while len(s) < length:
                b = int(rng.integers(a, z - 5 + 1))
                s.extend(range(b, b + 5))
            S.append(s[:length])
        _SEQ[key] = S
    return _SEQ[key]


def score(cfg, acct="25k", spans=("H1", "H2")):
    D = W.data()
    o = {}
    for span in spans:
        a, z = W.span_idx(span)
        st = list(range(a, z))
        o[span] = summ([run(cfg, list(range(k, z)), D["by"], acct) for k in st], [z - k for k in st], acct)
        S = mc_seqs(span)
        o["MC " + span] = summ([run(cfg, s, D["by"], acct, MC_LEN) for s in S], [MC_LEN] * len(S), acct)
    return o


def grid():
    out = {}
    for nm, c in configs().items():
        o = score(c)
        out[nm] = {"cfg": c, **o}
        h1, h2, m1, m2 = o["H1"], o["H2"], o["MC H1"], o["MC H2"]
        print(f"{nm:32s} H1 p10/f10 {h1['p10']:5.1f}/{h1['f10']:4.1f} p15/f15 {h1['p15']:5.1f}/{h1['f15']:4.1f} | "
              f"H2 {h2['p10']:5.1f}/{h2['f10']:4.1f} {h2['p15']:5.1f}/{h2['f15']:4.1f} | MC pass H1 {m1['pass']:5.1f} fail {m1['fail']:4.1f}"
              f" med {m1['pass_med']} slow {m1['slow_pass']} | MC H2 {m2['pass']:5.1f}/{m2['fail']:4.1f} | maxrisk {h1['max_risk']}",
              flush=True)
    out["_50k_live"] = {"cfg": CFG_50K, **score(CFG_50K, "50k")}
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    print("wrote", OUT)


def pick(G):
    """H1 only: maximise p10 - 1.5 x dead10 (failed or stuck within 10, exact starts) + 0.5 x (MC eventual pass - not passed)."""
    sc = {nm: round(r["H1"]["p10"] - 1.5 * r["H1"]["dead10"] + 0.5 * (2 * r["MC H1"]["pass"] - 100.0), 1)
          for nm, r in G.items() if not nm.startswith("_")}
    return max(sc, key=sc.get), sc


# ================================================================================================ copy trading
def _dead(r, h):
    return (r[0] == "FAIL" and r[1] <= h) or (r[0] != "PASS" or r[1] > h) and len(r[3]) >= h and r[3][h - 1] < DEAD


def joint(c50, c25, seqs, lag=0, h=10):
    """Both accounts on the same sessions; the 25K starts `lag` sessions later. Each account judged on its own first h
    sessions. -> joint outcome shares (%), correlation of the outcomes, worst combined day."""
    D = W.data()
    cnt = {"both_pass": 0, "only_50k": 0, "only_25k": 0, "neither_pass": 0, "both_fail": 0, "one_fail": 0, "any_fail": 0,
           "both_pass_eventual": 0, "both_fail_eventual": 0, "at_least_one_pass_eventual": 0}
    x50, x25, f50, f25, worst = [], [], [], [], []
    for s in seqs:
        d50, d25 = [], []
        r50 = run(c50, s, D["by"], "50k", days=d50)
        r25 = run(c25, s[lag:], D["by"], "25k", days=d25)
        p50, p25 = r50[0] == "PASS" and r50[1] <= h, r25[0] == "PASS" and r25[1] <= h
        q50, q25 = _dead(r50, h), _dead(r25, h)            # failed, or stuck with < DEAD room, within h sessions
        cnt["both_pass"] += p50 and p25
        cnt["only_50k"] += p50 and not p25
        cnt["only_25k"] += p25 and not p50
        cnt["neither_pass"] += not (p50 or p25)
        cnt["both_fail"] += q50 and q25
        cnt["one_fail"] += q50 != q25
        cnt["any_fail"] += q50 or q25
        cnt["both_pass_eventual"] += r50[0] == "PASS" and r25[0] == "PASS"
        cnt["both_fail_eventual"] += r50[0] != "PASS" and r25[0] != "PASS"
        cnt["at_least_one_pass_eventual"] += r50[0] == "PASS" or r25[0] == "PASS"
        x50.append(p50); x25.append(p25); f50.append(q50); f25.append(q25)
        # worst combined day while both evals are open (same calendar session)
        n = min(len(d50) - lag, len(d25)) if lag else min(len(d50), len(d25))
        comb = [d50[i + lag] + d25[i] for i in range(max(0, n))]
        worst.append(min(comb) if comb else 0.0)
    N = len(seqs)
    o = {k: round(100.0 * v / N, 1) for k, v in cnt.items()}
    o["n"] = N
    o["p10_50k"] = round(100.0 * sum(x50) / N, 1)
    o["p10_25k"] = round(100.0 * sum(x25) / N, 1)
    o["f10_50k"] = round(100.0 * sum(f50) / N, 1)
    o["f10_25k"] = round(100.0 * sum(f25) / N, 1)
    o["indep_both_pass"] = round(o["p10_50k"] * o["p10_25k"] / 100.0, 1)
    o["indep_both_fail"] = round(o["f10_50k"] * o["f10_25k"] / 100.0, 1)
    o["corr_pass"] = round(float(np.corrcoef(np.array(x50, float), np.array(x25, float))[0, 1]), 2)
    o["corr_fail"] = round(float(np.corrcoef(np.array(f50, float), np.array(f25, float))[0, 1]), 2) if any(f50) and any(f25) else None
    o["worst_comb_day"] = round(float(min(worst)))
    o["worst_comb_day_p5"] = round(float(np.percentile(worst, 5)))
    o["fees"] = PRICE["50k"] + PRICE["25k"]
    o["fees_per_2wk_pass"] = round(o["fees"] / ((o["p10_50k"] + o["p10_25k"]) / 100.0)) if o["p10_50k"] + o["p10_25k"] else None
    return o


def copy(c25=None):
    G = json.load(open(OUT))
    nm = pick(G)[0]
    c25 = c25 or G[nm]["cfg"]
    out = {"pick": nm, "cfg_25k": c25, "cfg_50k": CFG_50K}
    for span in ("H1", "H2"):
        a, z = W.span_idx(span)
        for lag in (0, 5):
            ex = [list(range(k, z)) for k in range(a, z - 10 - lag)]       # exact starts that see 10 sessions on both
            out[f"{span} lag{lag}"] = joint(CFG_50K, c25, ex, lag)
            out[f"MC {span} lag{lag}"] = joint(CFG_50K, c25, mc_seqs(span), lag)
            print(span, lag, json.dumps(out[f"{span} lag{lag}"]), "\n  MC", json.dumps(out[f"MC {span} lag{lag}"]), flush=True)
    # the funded side from tools/lit_funded_firms.py (research/lit/funded_firms.json)
    try:
        ff = json.load(open(os.path.join(ROOT, "research", "lit", "funded_firms.json")))
        P = {p["id"]: p["results"] for p in ff["plans"]}
        out["funded"] = {k: {s: P[k]["funded"][s] for s in ("H1", "H2")} for k in ("mffu_builder_50k", "mffu_builder_25k")}
        out["funded_cfg"] = {k: P[k]["funded_cfg"] for k in ("mffu_builder_50k", "mffu_builder_25k")}
        out["life_combo"] = [c for c in ff["combos"] if set(c["plans"]) == {"mffu_builder_50k", "mffu_builder_25k"}]
    except Exception as e:                                              # noqa: BLE001
        out["funded_error"] = str(e)
    json.dump(out, open(OUT_C, "w"), indent=1, default=float)
    print("wrote", OUT_C)


# ================================================================================================ runs
def path_trades(cfg, acct, span="2026", lag=0):
    """The owner's policy on real 2026: buy an eval, keep it until it passes or fails (no reset), then the next one."""
    D = W.data()
    a, z = W.span_idx(span)
    k, T, n = a + lag, [], {"PASS": 0, "FAIL": 0, "OPEN": 0}
    while k < z:
        r, used, _, _ = run(cfg, list(range(k, z)), D["by"], acct, keep=T)
        n[r] += 1
        k += used
        if r == "OPEN":
            break
    return T, n


def save():
    from tools import runlib as rl
    G = json.load(open(OUT))
    C = json.load(open(OUT_C)) if os.path.exists(OUT_C) else {}
    nm, sc = pick(G)
    sess = W.data()["sess"]

    def line(o):
        h1, h2, m1, m2 = o["H1"], o["H2"], o["MC H1"], o["MC H2"]
        return (f"H1 (pick) p10/f10 {h1['p10']}/{h1['f10']}, dec10 {h1['dec10']}, p15/f15 {h1['p15']}/{h1['f15']}, eventual "
                f"pass/fail/stuck {h1['pass']}/{h1['fail']}/{h1['stuck_end']}, dead10 {h1['dead10']}, pass_med {h1['pass_med']}, slow_pass {h1['slow_pass']}%, ${h1['cost_2wk']} per "
                f"2-week pass, ${h1['cost_pass']} per pass; H2 (check) p10/f10 {h2['p10']}/{h2['f10']}, dec10 {h2['dec10']}, p15/f15 "
                f"{h2['p15']}/{h2['f15']}, eventual {h2['pass']}/{h2['fail']}/{h2['stuck_end']}, dead10 {h2['dead10']}, pass_med {h2['pass_med']}, slow_pass {h2['slow_pass']}%, "
                f"${h2['cost_2wk']} per 2-week pass, ${h2['cost_pass']} per pass; Monte Carlo 2,000 x 120 sessions: H1 eventual "
                f"{m1['pass']}/{m1['fail']}, H2 {m2['pass']}/{m2['fail']}; max $ at risk {h1['max_risk']}")
    todo = [("lit_25k_c_scaled", "C25 (config C scaled)", "info", "The 50K config C scaled to the Builder 25K."),
            ("lit_25k_rec", nm, "adopt-candidate", f"Picked on H1 (score p10 - 1.5 dead10 + 0.5 (MC pass - not passed)): {nm}.")]
    for rid, key, status, why in todo:
        o = G[key]
        T, n = path_trades(o["cfg"], "25k")
        S = rl.score(T, sess)
        rl.save(rid, f"MFFU Builder 25K eval sizing: {key}", "risk",
                "Owner 2026-10-19: a Builder 25K ($63) next to the Builder 50K on the same LIT signals; best 25K eval sizing for "
                "pass within 2 weeks, no reset.", params={"account": "MFFU Builder 25K", "lit_sizing": o["cfg"]},
                sizing=o["cfg"], trades=T, scored=S, status=status,
                verdict=f"{why} {line(o)}. Back-to-back no-reset path on 2026: {n}.",
                notes="tools/lit_25k.py: engine.sizing.lit_qty exactly as the live loop calls it (25K acct + day guard), $1.90 a "
                      "micro, 1 tick stop slippage, $600 soft daily loss flattens, $1,000 EOD trailing locking at +$100, max 20 "
                      "micros. The stored trades are the back-to-back no-reset eval path (state-dependent size); the eval numbers "
                      "are in the verdict and research/lit/builder_25k.json.", writeup="lit-builder-25k", tags=["lit", "lit_25k"])
        print("saved", rid, n)
    if C:
        T50, n50 = path_trades(CFG_50K, "50k")
        T25, n25 = path_trades(C["cfg_25k"], "25k")
        T = sorted(T50 + T25, key=lambda t: (t["entry_t"], t["qty"]))
        S = rl.score(T, sess)
        j1, j2 = C["H1 lag0"], C["H2 lag0"]
        l1, l2 = C["H1 lag5"], C["H2 lag5"]
        rl.save("lit_25k_copy", "Copy trading: MFFU Builder 50K + 25K on the same LIT signals", "risk",
                "Owner 2026-10-19: both evals on one bot (same entry / stop / target, each sized on its own room).",
                params={"cfg_50k": C["cfg_50k"], "cfg_25k": C["cfg_25k"]}, trades=T, scored=S, status="info",
                verdict=(f"Same day: H1 both pass in 2 weeks {j1['both_pass']}%, one {j1['only_50k'] + j1['only_25k']}%, both fail "
                         f"{j1['both_fail']}% (pass corr {j1['corr_pass']}); H2 {j2['both_pass']} / {j2['only_50k'] + j2['only_25k']} / "
                         f"{j2['both_fail']}% (corr {j2['corr_pass']}). 25K one week later: H1 {l1['both_pass']} / "
                         f"{l1['only_50k'] + l1['only_25k']} / {l1['both_fail']}%, H2 {l2['both_pass']} / {l2['only_50k'] + l2['only_25k']} / "
                         f"{l2['both_fail']}%. 2026 no-reset paths: 50K {n50}, 25K {n25}."),
                notes="tools/lit_25k.py copy; both accounts' trades in one list (the combined eval-account P&L).",
                writeup="lit-builder-25k", tags=["lit", "lit_25k"])
        print("saved lit_25k_copy")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    {"grid": grid, "copy": copy, "save": save}[cmd]()
