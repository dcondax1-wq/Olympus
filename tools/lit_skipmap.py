"""LIT deep skip map (2026-11-23, research/writeups/lit-deep-2026-11-23.md). RESEARCH ONLY: paper, never touches live_model*.json.

Pre-registered design (committed before any result): research/lit/lit_deep_design_2026-11-23.md.

1. skip map: every LIT setup the detector forms (today's CISD candidates + the all-hours detector + the multi-day-swing
   levels) that the bot did NOT trade, with the first reason (window, depth, displacement, inducement, Monday rule, stop
   range, VIX band too near, no tap in 30 min, tapped but no 1m CISD, day already traded / position open).
2. families: each skipped family as an ADD-ON to today's LIT (1 live trade + 1 family trade a day, one position at a time),
   scored like every LIT study (tools/lit_edge: LIT size rule, live two_week eval path), H1 pick, H2 + 2021-25 untouched,
   a sign-flip test of the daily $ change, Holm-corrected across the families.

    python -X utf8 tools/lit_skipmap.py check   # base run == the live trades (run lit_live)
    python -X utf8 tools/lit_skipmap.py run     # skip map + every family -> research/lit/lit_deep_2026-11-23.json + Lab rows
"""
from __future__ import annotations

import collections
import json
import logging
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "lit_deep_2026-11-23.json")
SKIPS = os.path.join(ROOT, "research", "lit", "lit_deep_skips_2026.json")
LAB = os.path.join(ROOT, "research", "lab", "lit_deep.json")
LIVE = E.LIVE
SPANS = E.SPANS
PV, COMM = lit.PV, lit.COMM
OFF = 100000                      # minute offset that routes an extra setup to its family override (engine kz)
N_FLIP = 10000

FAMILIES = [  # id, plain name, owner's family, kind, definition
    ("second_any", "2nd setup of the day", "second setup after the first trade", "second",
     {"second": {"after": None, "side": "any"}}),
    ("opp_after_stop", "Other side after a stop-out", "opposite side after a stop-out", "second",
     {"second": {"after": ["STOP", "CUT_T15"], "side": "opp"}}),
    ("continuation", "Same side again after a win / BE", "continuation LIT", "second",
     {"second": {"after": ["TARGET", "BE"], "side": "same"}}),
    ("htf_liq", "Sweeps of 5-day / 20-day highs and lows", "other liquidity (HTF swing points)", "htf", {}),
    ("idm_none", "No inducement needed", "inducement variant", "gate", {"gate": "idm"}),
    ("small_sweep", "Smaller sweep (0.25-0.5 ATR)", "smaller sweep size", "gate", {"gate": "depth", "depth": 0.25}),
    ("disp_low", "Weaker displacement (0.5-0.8 ATR)", "displacement variant", "gate", {"gate": "disp", "disp": 0.5}),
    ("hours_out", "Outside 02:00-15:30 (Asia 18:30-02:00, 15:30-15:45)", "outside the hours window", "hours",
     {"gate": "window", "ov": {"all_hours": True}}),
    ("cisd5_only", "5m CISD without the 1m confirmation", "1m CISD vs 5m CISD", "exec", {"ov": {"cisd1m": None}}),
    ("vix_near", "VIX band only 1.0-1.5R away", "setups the VIX band filters out", "gate",
     {"gate": "target", "ov": {"min_rr": 1.0}}),
    ("stop_wide", "Planned stop 5-8 or 80-120 pts", "stop-size filter", "gate",
     {"gate": "stop", "ov": {"min_stop": 5.0, "max_stop": 120.0}}),
    ("wait_long", "Limit works 60 min instead of 30", "late tap", "exec", {"ov": {"wait": 12}}),
    ("monday_off", "Setups the Monday rule blocked", "Monday rule", "gate", {"gate": "monday", "ov": {"monday": False}}),
]

_C = {}


def cx():
    if not _C:
        c = E.ctx()
        M = c["M"]
        _, C = F.market(LIVE["ref"], LIVE["extra_boxes"])
        _C.update(M=M, C=C, T=c["T"], B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    return _C


def evening():
    if "Cev" not in _C:
        _C["Cev"] = lit.candidates(cx()["M"], ref=LIVE["ref"], evening=True)
    return _C["Cev"]


def htf():
    if "Chtf" not in _C:
        M2 = lit.Market(extra_levels=["d5", "d20"])
        _C["Chtf"] = lit.candidates(M2, ref=LIVE["ref"])
    return _C["Chtf"]


def run(C, P):
    c = cx()
    return lit.run_x(c["M"], C, {**LIVE, **P}, F.SESS, B1=c["B1"], B5=c["B5"])


# ------------------------------------------------------------------------------------------------ gates (run_core's order)
def plan(z, P):
    ep = min(float(z["ref_d"]), z["trig_c"])
    stop = z["ext_d"] - P["stop_buf"]
    return ep, ep - stop


def target_ok(z, P, min_rr):
    ep, risk = plan(z, P)
    sh = z["entry_d"] - ep
    T = lit.targets_x(cx()["M"], z, P)
    return any(x + sh >= min_rr * risk for x in T.get("vix", []))


def gates(z, P=LIVE):
    """The live setup gates a candidate fails (empty = passes every pre-fill gate)."""
    f = []
    if not any(a <= z["mod"] < b for a, b in P["window"]):
        f.append("window")
    if z["depth_atr"] < P["depth"]:
        f.append("depth")
    if z["disp"] < P["disp"]:
        f.append("disp")
    dm, age, cnt = P["idm_a"]
    if sum(1 for dd, aa in z["idm_a"] if dd <= dm and aa <= age) < cnt:
        f.append("idm")
    if P.get("monday") and lit.monday_block(cx()["M"], z):
        f.append("monday")
    _, risk = plan(z, P)
    if not (P["min_stop"] <= risk <= P["max_stop"]):
        f.append("stop")
    elif not target_ok(z, P, P["min_rr"]):
        f.append("target")
    return f


def relaxed_ok(z, fam):
    g, d = fam["gate"], fam
    if g == "depth":
        return z["depth_atr"] >= d["depth"]
    if g == "disp":
        return z["disp"] >= d["disp"]
    if g == "idm":
        return True
    if g == "window":
        m = z["mod"]
        return m >= 1110 or m < 120 or 930 <= m < 945
    if g == "monday":
        return True
    if g == "stop":
        _, risk = plan(z, LIVE)
        return 5.0 <= risk <= 120.0
    if g == "target":
        _, risk = plan(z, LIVE)
        return LIVE["min_stop"] <= risk <= LIVE["max_stop"] and target_ok(z, LIVE, 1.0)
    raise ValueError(g)


def key(z):
    return (z["day"], int(z["i"]), int(z["dir"]))


def live_pos():
    """Per day: the (entry_t, -dir) sort key of the live trade's setup (setups before it were skipped by a gate or the fill)."""
    c = cx()
    by = {key(z): z for z in c["C"]}
    out = {}
    for t in c["T"]:
        z = by[(t["day"], int(t["i"]), int(t["dir"]))]
        out[t["day"]] = (z["entry_t"], -z["dir"])
    return out


def before_live(z, lp):
    p = lp.get(z["day"])
    return p is None or (z["entry_t"], -z["dir"]) < p


# ------------------------------------------------------------------------------------------------ the skip map
def exec_reason(z):
    """Why a setup that passed every gate made no trade on its own (run alone under the live rules)."""
    c = cx()
    if run([z], {}):
        return "day already traded / position open"
    if run([z], {"cisd1m": None}):
        return "tapped, no 1m CISD in 22 min"
    return "no tap in 30 min / setup broke first"


def skip_map():
    c = cx()
    taken = {(t["day"], int(t["i"]), int(t["dir"])) for t in c["T"]}
    sess = set(F.SESS)
    base_keys = {key(z) for z in c["C"]}
    rows = []
    pools = [("rth", c["C"]),
             ("all_hours", [z for z in evening() if key(z) not in base_keys and (z["mod"] >= 1110 or z["mod"] < 60)]),
             ("htf_levels", [z for z in htf() if key(z) not in base_keys])]
    for src, CC in pools:
        for z in CC:
            if z["day"] not in sess or key(z) in taken:
                continue
            g = gates(z)
            r = g[0] if g else None
            rows.append({"day": z["day"], "t": int(z["entry_t"]), "mod": int(z["mod"]), "dir": int(z["dir"]), "src": src,
                         "swept": z["swept"], "depth_atr": z["depth_atr"], "disp": z["disp"], "gates": g, "reason": r})
    # exec reasons only for rows that passed every gate (costly; 2026 + a reference count)
    for r_ in rows:
        if r_["reason"] is None:
            z = next(z for z in (c["C"] if r_["src"] == "rth" else evening() if r_["src"] == "all_hours" else htf())
                     if z["day"] == r_["day"] and int(z["entry_t"]) == r_["t"] and int(z["dir"]) == r_["dir"])
            r_["reason"] = exec_reason(z)
    summ = {}
    for sp, (a, b) in SPANS.items():
        cnt = collections.Counter(r["reason"] for r in rows if a <= r["day"] <= b)
        ns = sum(1 for d in F.SESS if a <= d <= b)
        summ[sp] = {"per_week": {k: round(v / (ns / 5), 2) for k, v in cnt.most_common()}, "n": dict(cnt.most_common()),
                    "sessions": ns}
    return rows, summ


# ------------------------------------------------------------------------------------------------ families
def extras(fid, fam):
    c = cx()
    lp = live_pos()
    kind = fam_kind(fid)
    if kind == "htf":
        bk = {key(z) for z in c["C"]}
        return [z for z in htf() if key(z) not in bk and before_live(z, lp) and not gates(z)]
    if kind == "hours":
        return [z for z in evening() if before_live(z, lp) and gates(z) == ["window"] and relaxed_ok(z, fam)]
    if kind == "exec":
        return [z for z in c["C"] if before_live(z, lp) and not gates(z)]
    if kind == "gate":
        return [z for z in c["C"] if before_live(z, lp) and gates(z) == [fam["gate"]] and relaxed_ok(z, fam)]
    raise ValueError(kind)


def fam_kind(fid):
    return next(f[3] for f in FAMILIES if f[0] == fid)


def family_trades(fid):
    fam = next(f[4] for f in FAMILIES if f[0] == fid)
    c = cx()
    kind = fam_kind(fid)
    if kind == "second":
        return run(c["C"], {"max_per_day": 2, **fam}), None
    X = extras(fid, fam)
    xk = {(z["day"], int(z["entry_t"]), int(z["dir"])) for z in X}
    mix = [z for z in c["C"] if (z["day"], int(z["entry_t"]), int(z["dir"])) not in xk]
    mix += [{**z, "src": "x", "pre_ok": True, "mod": int(z["mod"]) + OFF} for z in X]
    mix.sort(key=lambda z: (z["entry_t"], -z["dir"]))
    P = {"max_per_day": 2, "src_cap": 1, "kz": [[OFF, 10 ** 9, fam.get("ov", {})]]}
    return run(mix, P), len([z for z in X if z["day"] in set(F.SESS)])


def unit(t):
    """An engine trade -> a tools/lit_edge unit (re-sized there with the LIT size rule / the eval path)."""
    d = t["dir"]
    q = t["qty"]
    pts = (t["pnl"] + COMM * q) / (PV * q)
    risk = t["risk_pts"]
    return {"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": d, "exit": t["exit"],
            "risk": risk, "tgt": round((t["target_px"] - t["entry_px"]) * d, 2), "pts": round(pts, 4),
            "w1": round(-float(t["mae"]) * risk, 4), "legs": [(1.0, pts)], "mfe": t["mfe"], "tf": t["tf"], "m": 1.0,
            "floored": False}


def day_pnl(L):
    o = collections.defaultdict(float)
    for l in L:
        o[l["day"]] += l["pnl"]
    return o


def flip_p(delta, seed=7):
    x = np.array([v for v in delta if abs(v) > 0.5])
    if not len(x):
        return 1.0
    s = x.sum()
    rng = np.random.default_rng(seed)
    S = (rng.choice([-1.0, 1.0], size=(N_FLIP, len(x))) * x).sum(axis=1)
    return float(((S >= s - 1e-9).sum() + 1) / (N_FLIP + 1))


def units(T):
    """tools/lit_edge.trades (the harness's own re-walk, == the engine for every live trade) for trades it can walk; the
    engine's own numbers for evening (18:00-24:00) entries, which the harness's day walk does not cover."""
    ev = [t for t in T if (int(t["entry_t"]) // 60 - 0) >= 0 and _mod(t["entry_t"]) >= 1080]
    rest = [t for t in T if _mod(t["entry_t"]) < 1080]
    return sorted(E.trades(T=rest) + [unit(t) for t in ev], key=lambda u: u["entry_t"])


def _mod(ts):
    import datetime as dt
    from zoneinfo import ZoneInfo
    x = dt.datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York"))
    return x.hour * 60 + x.minute


def score(T, base=None):
    U = units(T)
    o, U, L = E.evaluate(U=U)
    s = {"lit": o["lit"], "eval": {sp: {k: o["eval"][sp][k] for k in ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10",
                                                                     "pass_med")} for sp in o["eval"]}}
    return s, L


def holm(ps):
    ids = sorted(ps, key=lambda k: ps[k])
    m, out, run_max = len(ids), {}, 0.0
    for r, k in enumerate(ids):
        run_max = max(run_max, min(1.0, (m - r) * ps[k]))
        out[k] = round(run_max, 4)
    return out


def check():
    c = cx()
    T = run(c["C"], {})
    a = [(t["entry_t"], round(t["pnl"], 2)) for t in T]
    b = [(t["entry_t"], round(t["pnl"], 2)) for t in c["T"]]
    print("base == live trades:", a == b, len(a))
    s, _ = score(T)
    o, _, _ = E.evaluate()
    for sp in ("H1", "H2", "2021-25"):
        print(sp, "units", s["lit"][sp]["net"], "harness", o["lit"][sp]["net"])
    for sp in ("H1", "H2"):
        print(sp, "eval units", s["eval"][sp]["net"], s["eval"][sp]["p10"], "harness", o["eval"][sp]["net"], o["eval"][sp]["p10"])
    return a == b


def main_run():
    c = cx()
    base, L0 = score(c["T"])
    d0 = day_pnl(L0)
    rows, summ = skip_map()
    res = {}
    for fid, name, owner, kind, fam in FAMILIES:
        T, nx = family_trades(fid)
        s, L = score(T)
        d1 = day_pnl(L)
        bk = {l["entry_t"] for l in L0}
        nk = {l["entry_t"] for l in L}
        extra = [l for l in L if l["entry_t"] not in bk]
        delta, add = {}, {}
        for sp, (a, b) in SPANS.items():
            ss = [d for d in F.SESS if a <= d <= b]
            delta[sp] = [d1.get(d, 0.0) - d0.get(d, 0.0) for d in ss]
            ex = [l for l in extra if a <= l["day"] <= b]
            p = np.array([l["pnl"] for l in ex])
            gl = -p[p < 0].sum() if len(p) else 0
            add[sp] = {"n": len(ex), "win": round(100 * float((p > 0).mean()), 1) if len(p) else None,
                       "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())) if len(p) else 0,
                       "displaced": sum(1 for l in L0 if a <= l["day"] <= b and l["entry_t"] not in nk)}
        dl = {sp: s["lit"][sp]["net"] - base["lit"][sp]["net"] for sp in SPANS}
        de = {sp: s["eval"][sp]["net"] - base["eval"][sp]["net"] for sp in ("H1", "H2")}
        df = {sp: round(s["eval"][sp]["f10"] - base["eval"][sp]["f10"], 1) for sp in ("H1", "H2")}
        p = {sp: flip_p(delta[sp]) for sp in SPANS}
        p["oos"] = flip_p(delta["H2"] + delta["2021-25"])
        res[fid] = {"name": name, "owner_family": owner, "kind": kind, "def": fam, "extras_formed": nx, "total": s, "added": add,
                    "d_lit": dl, "d_eval": de, "d_f10": df, "p": p,
                    "picked_h1": bool(dl["H1"] > 0 and de["H1"] > 0 and df["H1"] <= 0)}
        print(f"{fid:15s} H1 {dl['H1']:+7.0f} H2 {dl['H2']:+7.0f} 21-25 {dl['2021-25']:+8.0f} | eval {de['H1']:+7.0f} {de['H2']:+7.0f} "
              f"f10 {df['H1']:+.1f}/{df['H2']:+.1f} | tpw {s['lit']['H1']['tpw']}/{s['lit']['H2']['tpw']} | p_oos {p['oos']:.4f} "
              f"| add n {add['H1']['n']}/{add['H2']['n']}/{add['2021-25']['n']}", flush=True)
    adj = holm({k: v["p"]["oos"] for k, v in res.items()})
    for k, v in res.items():
        v["p_holm"] = adj[k]
        s = v["total"]["lit"]
        v["pass"] = bool(all(v["d_lit"][sp] > 0 for sp in SPANS) and all(v["d_eval"][h] > 0 and v["d_f10"][h] <= 0 for h in ("H1", "H2"))
                         and all(s[h]["tpw"] <= 4.0 for h in ("H1", "H2")) and adj[k] <= 0.05)
        v["verdict"] = "PASS" if v["pass"] else ("Rejected (picked on Jan-Jun, failed the check)" if v["picked_h1"]
                                                  else "Rejected at the pick (Jan-Jun)")
    json.dump({"base": base, "skip_summary": summ, "families": res, "design": "research/lit/lit_deep_design_2026-11-23.md",
               "spans": SPANS, "sessions_to": F.SESS[-1]}, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    json.dump({"rows_2026": [r for r in rows if r["day"] >= "2026"], "summary": summ}, open(SKIPS, "w", encoding="utf-8"),
              indent=0, default=float)
    lab = []
    for fid, v in res.items():
        sp_out = {}
        for sp, nm in (("H1", "2026_jan_jun"), ("H2", "2026_jul_oct"), ("2021-25", "2021_25")):
            x = v["total"]["lit"][sp]
            sp_out[nm] = {"tpw": x["tpw"], "win": x["win"], "pf": x["pf"], "usd_mo": x["per_month"], "maxdd": x["dd"],
                          "d_usd_mo": x["per_month"] - base["lit"][sp]["per_month"], "added_trades": v["added"][sp]["n"]}
            if sp in ("H1", "H2"):
                ev = v["total"]["eval"][sp]
                sp_out[nm]["eval"] = {"p10": ev["p10"], "f10": ev["f10"], "pass_med": ev["pass_med"], "net": ev["net"]}
        lab.append({"id": "litdeep_" + fid, "name": v["name"], "family": v["owner_family"], "spans": sp_out,
                    "p_oos": v["p"]["oos"], "p_holm": v["p_holm"], "verdict": v["verdict"]})
    json.dump({"source": "tools/lit_skipmap.py run (2026-11-23)", "writeup": "research/writeups/lit-deep-2026-11-23.md",
               "base": {nm: {"tpw": base["lit"][sp]["tpw"], "win": base["lit"][sp]["win"], "pf": base["lit"][sp]["pf"],
                             "usd_mo": base["lit"][sp]["per_month"], "maxdd": base["lit"][sp]["dd"]}
                        for sp, nm in (("H1", "2026_jan_jun"), ("H2", "2026_jul_oct"), ("2021-25", "2021_25"))},
               "rows": lab}, open(LAB, "w", encoding="utf-8"), indent=1)
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "run":
        main_run()
