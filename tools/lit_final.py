"""LIT final: merge of the four 2026 LIT studies (entry, sessions, risk, filters) into one strategy, tuned and judged on 2026.

Owner order 2026-10-18: LIT is the strategy; tune and judge it on 2026 only (Jan 2 - Oct 16). 2021-25 is a reference line,
never a gate. Overfitting guard: pick on 2026 H1 (Jan-Jun), check on 2026 H2 (Jul-Oct 16), report both.

Everything runs through engine/lit.py run_x() (one parameter dict, DEFAULTS = lit_A). The final variant is defined in one
place: research/lit/lit_final.json.

  python tools/lit_final.py check      # run_x(DEFAULTS) == lit_A, and run_x reproduces each study's saved best run
  python tools/lit_final.py search     # the combinations + neighbours -> research/lit/final_results.json
  python tools/lit_final.py critic     # months, halves, odd/even, slippage, piece removal, 15 neighbours, 2021-25
  python tools/lit_final.py save       # store run 'lit_final' (rl.save, family other, tag lit)
1 CPU process only.
"""
from __future__ import annotations

import collections
import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.analytics import PLANS, simulate_eval  # noqa: E402
from tools import runlib as rl  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUT = os.path.join(ROOT, "research", "lit", "final_results.json")
FINAL = os.path.join(ROOT, "research", "lit", "lit_final.json")
SESS = [d[0] for d in rl.load("baseline")["days"]]
SPAN = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2026": ("2026-01-01", "2026-12-31"),
        "2021-25": ("2021-01-01", "2025-12-31")}
CAND_V = "v2"          # bump when candidates() output changes

X = lambda *nms: [f"{n}_{s}" for n in nms for s in "hl"]
DAILY = ["pdh", "pdl", "pwh", "pwl", "pmh", "pml"]
SESS_SET = X("asia20", "lon34", "ny89", "ny8_830") + DAILY        # lit_sessions_A sweep set (B1N)

# the four studies' picks, as run_x parameters
LIT_A = {}                                                             # = lit.DEFAULTS
ENTRY = {"ref": "cisd", "disp": 0.8, "idm_a": [1.0, 36, 1], "tf": "1m", "cisd1m": 20, "wait": 6}
SESSIONS = {"extra_boxes": ["ny8_830"], "sweep_names": SESS_SET}
SESSIONS_MW = {**SESSIONS, "mw_filter": True}
RISK = {"classes": ["vix"], "vix_k": 1.0, "max_stop": 100.0, "tf": "1m", "stop_buf": 0.25, "fallback_rr": 4.0, "max_rr": None}
RISK8 = {**RISK, "max_rr": 8.0}
FILTERS = {"nwog_discount": True, "how_out": 0.5}


# ------------------------------------------------------------------------------------------------ data
_MK = {}


def market(ref="frac", extra=()):
    key = (ref, tuple(extra))
    if key in _MK:
        return _MK[key]
    M = lit.Market(extra_boxes=list(extra))
    p = os.path.join(CACHE, f"litfinal_{CAND_V}_{ref}_{'-'.join(extra) or 'none'}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        C = pickle.load(open(p, "rb"))
    else:
        C = lit.candidates(M, ref=ref)
        os.makedirs(CACHE, exist_ok=True)
        pickle.dump(C, open(p, "wb"))
    _MK[key] = (M, C)
    return M, C


_B = {}


def bars(M, tf):
    k = (id(M), tf)
    if k not in _B:
        _B[k] = lit.bars_1m(M) if tf == "1m" else lit.bars_5m(M)
    return _B[k]


def run(P, sessions=SESS):
    P = {**lit.DEFAULTS, **P}
    M, C = market(P["ref"], P["extra_boxes"])
    B1 = bars(M, "1m") if P["tf"] == "1m" else None
    return lit.run_x(M, C, P, sessions, B1=B1, B5=bars(M, "5m"))


# ------------------------------------------------------------------------------------------------ scoring
KEYS = ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "dec10", "pass_med", "b2b", "stop")


def pass_rate(days, horizon=60):
    """passed / (passed + failed) of a fresh MFFU Builder 50K eval started on every session (60-session horizon)."""
    plan = PLANS["builder_50k"]
    pn = [d["pnl"] for d in days]; lo = [d["low"] for d in days]
    P = F = 0
    for i in range(len(days)):
        r = simulate_eval(pn[i:i + horizon], plan, lo[i:i + horizon])["result"]
        P += r == "PASS"; F += r == "FAIL"
    return round(100 * P / (P + F), 1) if P + F else None


def score(T, spans=("H1", "H2", "2026", "2021-25"), fast=False):
    out = {}
    for nm in spans:
        a, z = SPAN[nm]
        ss = [d for d in SESS if a <= d <= z]
        TT = [t for t in T if a <= t["day"] <= z]
        if fast:
            p = np.array([t["pnl"] for t in TT] or [0.0]); gl = -p[p < 0].sum()
            eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(TT) else 0.0
            out[nm] = {"n": len(TT), "tpw": round(len(TT) / (len(ss) / 5), 2), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                       "net": round(float(p.sum())), "dd": round(dd)}
            continue
        S = rl.score(TT, ss)
        s = S["spans"]["2026" if nm in ("H1", "H2", "2026") else "2021-25"]
        o = {k: s.get(k) for k in KEYS}
        o["pass_rate"] = pass_rate(S["days"]) if s.get("n") else None
        pn = sorted((t["pnl"] for t in TT), reverse=True)
        o["net_x1"], o["net_x3"] = round(sum(pn[1:])), round(sum(pn[3:]))      # outlier check: without the 1 / 3 best trades
        mo = collections.defaultdict(float)
        for t in TT:
            mo[t["day"][:7]] += t["pnl"]
        o["months_up"] = f"{sum(1 for v in mo.values() if v > 0)}/{len(mo)}"
        out[nm] = o
    return out


def fmt(o):
    def f(s):
        if not s.get("n"):
            return "n=0"
        x = f"n={s['n']} tpw={s['tpw']} PF={s['pf']} net={s['net']:+,} DD={s['dd']:,}"
        if "win" in s:
            x += f" win={s['win']} x3={s['net_x3']:+,} 2w={s['p10']}/{s['f10']} pr={s['pass_rate']}"
        return x
    return " | ".join(f"{k}[{f(v)}]" for k, v in o.items())


def slip(T, ticks):
    return [{**t, "pnl": round(t["pnl"] - ticks * lit.TICK * lit.PV * t["qty"], 2), "low": round(t["low"] - ticks * lit.TICK * lit.PV * t["qty"], 2)}
            for t in T]


# ------------------------------------------------------------------------------------------------ check
def _keys(T):
    return [(t["day"], t["entry_t"], round(t["pnl"], 2)) for t in T]


def check():
    from tools import research_lit as R
    M0, C0 = R.market()
    T0 = lit.run(M0, C0, R.make(**R.CAND["A"]), R.SESS)
    T1 = run({}, R.SESS)
    print("lit_A: lit.run", len(T0), round(sum(t["pnl"] for t in T0)), "| run_x", len(T1), round(sum(t["pnl"] for t in T1)),
          "| identical", _keys(T0) == _keys(T1), flush=True)
    for rid, P in (("lit_entry_best", ENTRY), ("lit_sessions_A", SESSIONS), ("lit_sessions_B", SESSIONS_MW),
                   ("lit_risk_vix_nobank", RISK), ("lit_risk_vix_bank8", RISK8), ("lit_filters_na_how", FILTERS)):
        r = rl.load(rid)
        Tr = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
        T = run(P)
        a = {(t["day"], int(t["entry_t"])): round(t["pnl"], 2) for t in Tr}
        b = {(t["day"], int(t["entry_t"])): round(t["pnl"], 2) for t in T}
        same = sum(1 for k in a if k in b and abs(a[k] - b[k]) < 0.02)
        n26a = round(sum(v for k, v in a.items() if k[0] >= "2026")); n26b = round(sum(v for k, v in b.items() if k[0] >= "2026"))
        print(f"{rid:22s} saved {len(a)} trades (2026 net {n26a:+,}) | run_x {len(b)} (2026 net {n26b:+,}) | same trade+pnl {same}",
              flush=True)


# ------------------------------------------------------------------------------------------------ search
def combos():
    """The merge: the risk pick (biggest single gain) with each other piece, pairs, and all four. Bank none vs 8R."""
    V = collections.OrderedDict()
    V["lit_A"] = {}
    V["E"] = ENTRY; V["S"] = SESSIONS; V["Smw"] = SESSIONS_MW; V["R"] = RISK; V["R8"] = RISK8; V["F"] = FILTERS
    for rn, Rp in (("R", RISK), ("R8", RISK8)):
        V[f"{rn}+E"] = {**Rp, **ENTRY}
        V[f"{rn}+S"] = {**Rp, **SESSIONS}
        V[f"{rn}+Smw"] = {**Rp, **SESSIONS_MW}
        V[f"{rn}+F"] = {**Rp, **FILTERS}
        V[f"{rn}+E+S"] = {**Rp, **ENTRY, **SESSIONS}
        V[f"{rn}+E+F"] = {**Rp, **ENTRY, **FILTERS}
        V[f"{rn}+S+F"] = {**Rp, **SESSIONS, **FILTERS}
        V[f"{rn}+Smw+F"] = {**Rp, **SESSIONS_MW, **FILTERS}
        V[f"{rn}+E+S+F"] = {**Rp, **ENTRY, **SESSIONS, **FILTERS}
        V[f"{rn}+E+Smw+F"] = {**Rp, **ENTRY, **SESSIONS_MW, **FILTERS}
    # single pieces of the filter study on top of R (NWOG side / HOW size separately)
    V["R+nwog"] = {**RISK, "nwog_discount": True}
    V["R+how"] = {**RISK, "how_out": 0.5}
    V["R8+nwog"] = {**RISK8, "nwog_discount": True}
    V["R8+how"] = {**RISK8, "how_out": 0.5}
    # entry pieces on top of R
    V["R+cisd"] = {**RISK, "ref": "cisd"}
    V["R+cisd+idm"] = {**RISK, "ref": "cisd", "idm_a": [1.0, 36, 1]}
    V["R+cisd+idm+1m20"] = {**RISK, "ref": "cisd", "idm_a": [1.0, 36, 1], "cisd1m": 20}
    V["R+cisd+1m20"] = {**RISK, "ref": "cisd", "cisd1m": 20}
    V["R+E_w12"] = {**RISK, **ENTRY, "wait": 12}
    V["R+E_d1"] = {**RISK, **ENTRY, "disp": 1.0}
    return V


def run_list(V, res=None, path=OUT):
    res = res if res is not None else (json.load(open(path)) if os.path.exists(path) else {})
    for nm, P in V.items():
        if nm in res:
            continue
        T = run(P)
        o = score(T)
        res[nm] = {"params": P, **o}
        print(f"{nm:18s} {fmt(o)}", flush=True)
        json.dump(res, open(path, "w"), indent=1)
    return res


def round2():
    """Selection round on H1 (metric: H1 net without its 3 best trades, so one lucky trade cannot pick the strategy; >= 2/wk),
    around the round-1 leader R8+E: bank level, and each remaining piece of the other studies added on top."""
    B = {**RISK8, **ENTRY}
    V = collections.OrderedDict()
    for b in (6.0, 10.0, 12.0):
        V[f"R{int(b)}+E"] = {**B, "max_rr": b}
    V["R8+E+how"] = {**B, "how_out": 0.5}
    V["R8+E+nwog"] = {**B, "nwog_discount": True}
    V["R8+E+mw"] = {**B, "mw_filter": True}
    V["R8+E+Smw"] = {**B, **SESSIONS_MW}
    V["R8+E+S+how"] = {**B, **SESSIONS, "how_out": 0.5}
    V["R8+E+ny830box"] = {**B, "extra_boxes": ["ny8_830"]}
    V["R8+E_w12"] = {**B, "wait": 12}
    V["R8+E_d1"] = {**B, "disp": 1.0}
    V["R8+E+vixpd"] = {**B, "classes": ["pd", "pw", "pm", "vix"]}
    return V


def final_params():
    return dict(json.load(open(FINAL))["params"])


REMOVE = {          # each piece of the final removed one at a time (back to the lit_A / study default)
    "E: CISD shift -> fractal break (lit_A)": {"ref": "frac"},
    "E: no inducement gate": {"idm_a": None},
    "E: displacement 1.0 ATR (lit_A)": {"disp": 1.0},
    "E: no 1m CISD confirmation (plain limit fill)": {"cisd1m": None},
    "E: limit valid 12 bars (lit_A)": {"wait": 12},
    "E: whole entry study off (= risk pick R8)": {"ref": "frac", "idm_a": None, "disp": 1.0, "cisd1m": None, "wait": 12},
    "R: target PDH/PWH/PMH (lit_A) instead of the VIX band": {"classes": ["pd", "pw", "pm"]},
    "R: bank 5R (lit_A)": {"max_rr": 5.0},
    "R: stop buffer 2 pts (lit_A)": {"stop_buf": 2.0},
    "R: everything on 5m bars (no 1m)": {"tf": "5m"},
    "R: whole risk study off (= entry pick lit_entry_best)": {"classes": ["pd", "pw", "pm"], "max_rr": 5.0, "stop_buf": 2.0},
}
NEIGH = {
    "VIX move x0.9": {"vix_k": 0.9}, "VIX move x1.1": {"vix_k": 1.1},
    "bank 7R": {"max_rr": 7.0}, "bank 9R": {"max_rr": 9.0},
    "1m confirm 15 bars": {"cisd1m": 15}, "1m confirm 30 bars": {"cisd1m": 30},
    "inducement within 0.75 ATR": {"idm_a": [0.75, 36, 1]}, "inducement within 1.25 ATR": {"idm_a": [1.25, 36, 1]},
    "inducement age 24 bars": {"idm_a": [1.0, 24, 1]}, "inducement age 48 bars": {"idm_a": [1.0, 48, 1]},
    "limit valid 4 bars": {"wait": 4}, "limit valid 8 bars": {"wait": 8},
    "displacement 0.7 ATR": {"disp": 0.7}, "displacement 0.9 ATR": {"disp": 0.9},
    "max stop 70": {"max_stop": 70.0}, "max stop 90": {"max_stop": 90.0},
    "min target 1.25R": {"min_rr": 1.25}, "min target 2R": {"min_rr": 2.0},
    "breakeven at 0.75R": {"be_r": 0.75}, "breakeven at 1.5R": {"be_r": 1.5},
    "sweep depth 0.4 ATR": {"depth": 0.4}, "sweep depth 0.6 ATR": {"depth": 0.6},
    "stop buffer 1 pt": {"stop_buf": 1.0},
}
ADDS = {
    "+ 4R fallback target (risk study)": {"fallback_rr": 4.0},
    "+ max stop 100 (risk study)": {"max_stop": 100.0},
    "+ both (= the full risk pick)": {"fallback_rr": 4.0, "max_stop": 100.0},
    "+ HOW-window half size (filters study)": {"how_out": 0.5},
    "+ NWOG discount filter (filters study)": {"nwog_discount": True},
    "+ sessions sweep set (sessions study)": SESSIONS,
    "+ sessions set + Mon-Wed rule": SESSIONS_MW,
    "+ Mon-Wed rule only": {"mw_filter": True},
}


def critic():
    P0 = final_params()
    T = run(P0)
    rep = {"params": P0, "main": score(T)}
    print("FINAL", fmt(rep["main"]), flush=True)
    # months of 2026, odd / even months, years
    mo = collections.OrderedDict()
    for t in sorted(T, key=lambda t: t["entry_t"]):
        if t["day"] >= "2026":
            m = mo.setdefault(t["day"][:7], {"n": 0, "wins": 0, "net": 0.0, "dd": 0.0, "_eq": 0.0, "_pk": 0.0})
            m["n"] += 1; m["wins"] += t["pnl"] > 0; m["net"] += t["pnl"]
            m["_eq"] += t["pnl"]; m["_pk"] = max(m["_pk"], m["_eq"]); m["dd"] = min(m["dd"], m["_eq"] - m["_pk"])
    for m in mo.values():
        m["net"] = round(m["net"]); m["dd"] = round(m["dd"]); m.pop("_eq"); m.pop("_pk")
    rep["months_2026"] = mo
    oe = {}
    for nm, odd in (("odd months (Jan Mar May Jul Sep)", 1), ("even months (Feb Apr Jun Aug Oct)", 0)):
        p = np.array([t["pnl"] for t in T if t["day"] >= "2026" and int(t["day"][5:7]) % 2 == odd])
        gl = -p[p < 0].sum()
        oe[nm] = {"n": len(p), "pf": round(float(p[p > 0].sum() / gl), 2), "net": round(float(p.sum())), "win": round(100 * float((p > 0).mean()), 1)}
    rep["odd_even"] = oe
    print("odd/even", oe)
    yr = collections.defaultdict(list)
    for t in T:
        yr[t["day"][:4]].append(t["pnl"])
    rep["years"] = {y: {"n": len(v), "net": round(sum(v)), "pf": round(sum(x for x in v if x > 0) / -sum(x for x in v if x < 0), 2)} for y, v in sorted(yr.items())}
    print("years", rep["years"])
    # slippage
    rep["slip"] = {f"+{k} tick": score(slip(T, k)) for k in (1, 2)}
    for k, v in rep["slip"].items():
        print("slip", k, fmt(v), flush=True)
    # long / short, exits, sessions, top trades, streaks
    t26 = [t for t in T if t["day"] >= "2026"]
    rep["sides"] = {lab: score([t for t in T if t["dir"] == d], spans=("H1", "H2", "2026", "2021-25"), fast=True) for d, lab in ((1, "long"), (-1, "short"))}
    rep["exits_2026"] = dict(collections.Counter(t["exit"] for t in t26))
    import datetime as dt
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    def sess_of(t):
        m = dt.datetime.fromtimestamp(t["entry_t"], ET); mm = m.hour * 60 + m.minute
        return "London 02:00-08:00" if mm < 480 else "NY AM 08:00-12:00" if mm < 720 else "NY PM 12:00-15:55"
    ss = collections.defaultdict(list)
    for t in t26:
        ss[sess_of(t)].append(t["pnl"])
    rep["sessions_2026"] = {k: {"n": len(v), "net": round(sum(v)), "pf": round(sum(x for x in v if x > 0) / max(-sum(x for x in v if x < 0), 1e-9), 2)} for k, v in sorted(ss.items())}
    top = sorted(t26, key=lambda t: -t["pnl"])[:5]
    rep["top5_2026"] = [{k: t[k] for k in ("day", "dir", "r", "pnl", "risk_pts", "qty", "exit", "entry_px", "target_px")} for t in top]
    rep["top3_share_2026"] = round(sum(t["pnl"] for t in top[:3]) / sum(t["pnl"] for t in t26), 3)
    st = mx = 0
    for t in sorted(t26, key=lambda t: t["entry_t"]):
        st = st + 1 if t["pnl"] < 0 else 0; mx = max(mx, st)
    rep["max_losing_streak_2026"] = mx
    rep["tf_2026"] = dict(collections.Counter(t.get("tf") for t in t26))
    rep["median_qty_2026"] = float(np.median([t["qty"] for t in t26])); rep["median_stop_2026"] = float(np.median([t["risk_pts"] for t in t26]))
    print("sides", rep["sides"]); print("exits", rep["exits_2026"], "sessions", rep["sessions_2026"]); print("top", rep["top5_2026"], rep["top3_share_2026"])
    print("streak", mx, "tf", rep["tf_2026"], "qty", rep["median_qty_2026"], "stop", rep["median_stop_2026"], flush=True)
    for grp, D in (("remove", REMOVE), ("neighbours", NEIGH), ("adds", ADDS)):
        rep[grp] = {}
        for nm, tw in D.items():
            o = score(run({**P0, **tw}))
            rep[grp][nm] = o
            print(f"{grp:10s} {nm:48s} {fmt(o)}", flush=True)
    # the old bot (run baseline) on the same halves
    b = rl.load("baseline")
    TB = [dict(zip(b["trade_cols"], a)) for a in b["trades"]]
    for t in TB:
        t["low"] = -min(float(t.get("mae") or 0), max(1.0, -float(t["r"]))) * float(t["risk_pts"]) * 2.0 * int(t["qty"])
    rep["baseline"] = score(TB)
    bm = collections.defaultdict(lambda: [0, 0.0])
    for t in TB:
        if t["day"] >= "2026":
            bm[t["day"][:7]][0] += 1; bm[t["day"][:7]][1] += t["pnl"]
    rep["baseline_months_2026"] = {k: {"n": v[0], "net": round(v[1])} for k, v in sorted(bm.items())}
    rep["baseline_odd_even"] = {nm: round(sum(t["pnl"] for t in TB if t["day"] >= "2026" and int(t["day"][5:7]) % 2 == odd))
                                for nm, odd in (("odd", 1), ("even", 0))}
    print("BASELINE", fmt(rep["baseline"]))
    json.dump(rep, open(os.path.join(ROOT, "research", "lit", "final_critic.json"), "w"), indent=1, default=str)
    return rep


def save():
    P0 = final_params()
    T = run(P0)
    S = rl.score(T, SESS)
    o = score(T)
    h = lambda s: f"n={s['n']} {s['tpw']}/wk PF {s['pf']} net {s['net']:+,} DD {s['dd']:,} pass rate {s['pass_rate']}%"
    rl.save("lit_final", "LIT final: CISD entry + inducement + 1m confirmation, VIX one-day band target (bank 8R)", "other",
            "Owner order 2026-10-18: one LIT strategy that earns in 2026 (tuned on Jan-Jun, checked on Jul-Oct)",
            params=P0, trades=T, scored=S, status="promising",
            verdict=f"2026 H1 (pick) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; 2026 {h(o['2026'])}; 2021-25 reference only {h(o['2021-25'])}",
            notes="engine/lit.py run_x with research/lit/lit_final.json (tools/lit_final.py). Merge of lit_entry_best and lit_risk_vix_bank8; "
                  "2026 filled and managed on true 1m bars (days with full 1m coverage), 5m elsewhere; size $800 up to a 20-pt stop then "
                  "800x20/stop, MNQ, max 40, $1.40/micro + 1 tick on market entries and non-limit exits; no cold-streak filter.",
            writeup="lit-final", tags=["lit", "lit_final"])
    print("saved lit_final", fmt(o))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "search":
        run_list(combos(), {})
        run_list(round2())
    elif cmd == "round2":
        run_list(round2())
    elif cmd == "critic":
        critic()
    elif cmd == "save":
        save()
