"""LIT ablation + simplification study (owner 2026-10-23: "Give me things to improve our current strategy. Maybe take things
away. Figure it out.").

Every component of the live LIT (live_model.json "lit" = run lit_live) is removed alone (and moved to its natural
neighbours), a greedy "minimal LIT" drops whatever costs nothing in 2026 H1, every numeric knob gets a sensitivity map
(spike vs plateau), a sampled Shapley value splits the H1 / H2 money between the components, and every variant gets a paired
day bootstrap vs the live LIT (multiple-testing count). Judged the LIT way: pick on 2026 H1 (Jan-Jun), check on 2026 H2
(Jul-Oct 16), 2021-25 a reference line (5m only there: t_check / the 1m CISD never act).

Two views, costs in, both from engine/lit.py run_x (the code the live loop runs):
  LIT size rule  the engine's trades ($800 up to a 20-pt stop, weekly stop) = how run lit_live is scored
  eval path      the live two_week sizing (engine/sizing.lit_qty, 10 sessions then safe_eval, no reset, $1.90 a micro) on the
                 engine's trades as units (tools/lit_adopt_combo.units + tools/lit_big_ideas / lit_adv_manage scoring)

    python -X utf8 tools/lit_ablation.py run        # everything -> research/lit/ablation.json (~15 min, 1 process)
    python -X utf8 tools/lit_ablation.py save       # rl.save runs abl_* from research/lit/ablation.json's variant list
Paper only. Edits no engine file and no live_model*.json.
"""
from __future__ import annotations

import collections
import copy
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (patches lit_adv_manage.run_eval)
from tools import lit_adv_manage as A  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "ablation.json")
LIVE = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
CFG0 = copy.deepcopy(A.CFG)

# ------------------------------------------------------------------------------------------------ the components
# removal = the parameter change that takes the component away (None-ish / widest). Binary set for greedy + Shapley.
REMOVE = collections.OrderedDict([
    ("wk_stop", ("weekly stop (half size after 2 stop-outs)", {"wk_stop": None})),
    ("monday", ("Monday rule", {"monday": False})),
    ("t_check", ("15-minute check", {"t_check": None})),
    ("be_off", ("BE + costs (BE at entry + 1.25 -> plain BE at entry)", {"be_off": 0.0})),
    ("be", ("breakeven at 1R altogether", {"be_r": None})),
    ("idm", ("inducement taken first (idm_a)", {"idm_a": None})),
    ("disp", ("displacement body >= 0.8 ATR", {"disp": 0.0})),
    ("depth", ("sweep depth >= 0.5 ATR", {"depth": 0.0})),
    ("wait", ("30-minute limit (wait 6 bars)", {"wait": 999})),
    ("cisd1m", ("1m CISD step (limit fill at the CISD level instead)", {"cisd1m": None})),
    ("stops", ("min / max stop 8 / 80 pts", {"min_stop": 0.25, "max_stop": 1000.0})),
    ("min_rr", ("min target 1.5R", {"min_rr": 0.01})),
    ("max_rr", ("8R bank", {"max_rr": None})),
    ("vix", ("VIX-band target (-> fixed 3R)", {"classes": [], "fallback_rr": 3.0})),
    ("flat", ("flat 15:55 (-> hold to 16:55)", {"flat_mod": 1010})),
    ("window", ("02:00-15:30 entry window (-> 01:00-15:55, all the detector sees)", {"window": [[60, 955]]})),
    ("one_day", ("1 trade a day (-> up to 5, one at a time)", {"max_per_day": 5})),
])

# extra single variants: neighbours and the alternatives the owner listed
EXTRA = collections.OrderedDict([
    ("wk_stop_n1", ("weekly stop after 1 stop-out", {"wk_stop": [1, 0.5]})),
    ("wk_stop_n3", ("weekly stop after 3 stop-outs", {"wk_stop": [3, 0.5]})),
    ("wk_stop_m075", ("weekly stop at 0.75 size", {"wk_stop": [2, 0.75]})),
    ("wk_stop_m025", ("weekly stop at 0.25 size", {"wk_stop": [2, 0.25]})),
    ("t_check_be_off", ("no 15-min check and plain BE (= the 2026-10-18 rules)", {"t_check": None, "be_off": 0.0})),
    ("be_r075", ("BE at 0.75R", {"be_r": 0.75})),
    ("be_r125", ("BE at 1.25R", {"be_r": 1.25})),
    ("be_r15", ("BE at 1.5R", {"be_r": 1.5})),
    ("be_r2", ("BE at 2R", {"be_r": 2.0})),
    ("idm2", ("2 inducements", {"idm_a": [1.0, 36, 2]})),
    ("disp06", ("displacement 0.6 ATR", {"disp": 0.6})),
    ("disp10", ("displacement 1.0 ATR", {"disp": 1.0})),
    ("depth025", ("sweep depth 0.25 ATR", {"depth": 0.25})),
    ("depth075", ("sweep depth 0.75 ATR", {"depth": 0.75})),
    ("wait3", ("limit 15 min", {"wait": 3})),
    ("wait12", ("limit 60 min", {"wait": 12})),
    ("tf5m", ("5m bars only (no 1m fills / management)", {"tf": "5m"})),
    ("tf5m_nocisd", ("5m bars only, no CISD step", {"tf": "5m", "cisd1m": None})),
    ("min_stop0", ("no min stop", {"min_stop": 0.25})),
    ("max_stop0", ("no max stop", {"max_stop": 1000.0})),
    ("max_stop60", ("max stop 60", {"max_stop": 60.0})),
    ("max_stop100", ("max stop 100", {"max_stop": 100.0})),
    ("min_rr10", ("min target 1.0R", {"min_rr": 1.0})),
    ("min_rr20", ("min target 2.0R", {"min_rr": 2.0})),
    ("max_rr6", ("bank at 6R", {"max_rr": 6.0})),
    ("max_rr10", ("bank at 10R", {"max_rr": 10.0})),
    ("fix2", ("fixed 2R target", {"classes": [], "fallback_rr": 2.0})),
    ("fix4", ("fixed 4R target", {"classes": [], "fallback_rr": 4.0})),
    ("fix5", ("fixed 5R target", {"classes": [], "fallback_rr": 5.0})),
    ("fix8", ("fixed 8R target", {"classes": [], "fallback_rr": 8.0})),
    ("lvl", ("next level target (PD / PW / PM high-low)", {"classes": ["pd", "pw", "pm"]})),
    ("vix_lvl", ("nearest of VIX band or a PD / PW / PM level", {"classes": ["vix", "pd", "pw", "pm"]})),
    ("vix_fb4", ("VIX band, else a fixed 4R (no skip)", {"fallback_rr": 4.0})),
    ("vix_k075", ("VIX band 0.75 x", {"vix_k": 0.75})),
    ("vix_k125", ("VIX band 1.25 x", {"vix_k": 1.25})),
    ("flat925", ("flat 15:25", {"flat_mod": 925})),
    ("flat985", ("flat 16:25", {"flat_mod": 985})),
    ("win_0300", ("entries from 03:00", {"window": [[180, 930]]})),
    ("win_0100", ("entries from 01:00", {"window": [[60, 930]]})),
    ("win_1430", ("entries until 14:30", {"window": [[120, 870]]})),
    ("win_1555", ("entries until 15:55", {"window": [[120, 955]]})),
    ("win_ny_only", ("NY only 08:00-15:30", {"window": [[480, 930]]})),
    ("win_no_pm", ("no afternoon (02:00-12:00)", {"window": [[120, 720]]})),
    ("two_day", ("2 trades a day", {"max_per_day": 2})),
    ("buf0", ("stop exactly at the sweep extreme", {"stop_buf": 0.0})),
    ("buf05", ("stop 2 ticks beyond", {"stop_buf": 0.5})),
])

# eval-path only: the two_week caps
CAPS = collections.OrderedDict([
    ("cap_room", ("no 60% room cap (two_week)", {"room_f": None})),
    ("cap_dll", ("no $1,000 soft-daily-loss cap (two_week)", {"dll_cap": False})),
    ("cap_both", ("neither cap (two_week)", {"room_f": None, "dll_cap": False})),
    ("cap_room05", ("room cap 50%", {"room_f": 0.5})),
    ("cap_room07", ("room cap 70%", {"room_f": 0.7})),
])

# numeric knobs: (key, getter/setter path, values); the live value is in each list
KNOBS = collections.OrderedDict([
    ("disp", ([0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1], lambda v: {"disp": v})),
    ("depth", ([0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], lambda v: {"depth": v})),
    ("idm_dist", ([0.5, 0.75, 1.0, 1.25, 1.5], lambda v: {"idm_a": [v, 36, 1]})),
    ("idm_age", ([12, 18, 24, 30, 36], lambda v: {"idm_a": [1.0, v, 1]})),
    ("wait", ([3, 4, 5, 6, 7, 8, 9], lambda v: {"wait": v})),
    ("cisd1m", ([10, 14, 17, 20, 23, 26, 30], lambda v: {"cisd1m": v})),
    ("stop_buf", ([0.0, 0.25, 0.5, 0.75], lambda v: {"stop_buf": v})),
    ("min_stop", ([4.0, 6.0, 8.0, 10.0, 12.0], lambda v: {"min_stop": v})),
    ("max_stop", ([60.0, 70.0, 80.0, 90.0, 100.0], lambda v: {"max_stop": v})),
    ("vix_k", ([0.8, 0.9, 1.0, 1.1, 1.2], lambda v: {"vix_k": v})),
    ("min_rr", ([1.0, 1.25, 1.5, 1.75, 2.0], lambda v: {"min_rr": v})),
    ("max_rr", ([6.0, 7.0, 8.0, 9.0, 10.0], lambda v: {"max_rr": v})),
    ("be_r", ([0.75, 0.9, 1.0, 1.1, 1.25, 1.5], lambda v: {"be_r": v})),
    ("be_off", ([0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0], lambda v: {"be_off": v})),
    ("t_check_at", ([10, 12, 15, 18, 20], lambda v: {"t_check": {**LIVE["t_check"], "at": v}})),
    ("t_check_x", ([0.2, 0.25, 0.3, 0.35, 0.4], lambda v: {"t_check": {**LIVE["t_check"], "x": v}})),
    ("t_check_mfe", ([0.3, 0.4, 0.5, 0.6, 0.7], lambda v: {"t_check": {**LIVE["t_check"], "mfe": v}})),
    ("wk_stop_n", ([1, 2, 3], lambda v: {"wk_stop": [v, 0.5]})),
    ("wk_stop_m", ([0.25, 0.5, 0.75], lambda v: {"wk_stop": [2, v]})),
    ("flat_mod", ([925, 940, 955, 970, 985], lambda v: {"flat_mod": v})),
    ("win_start", ([60, 90, 120, 150, 180], lambda v: {"window": [[v, 930]]})),
    ("win_end", ([870, 900, 930, 955], lambda v: {"window": [[120, v]]})),
])
KNOB_LIVE = {"disp": 0.8, "depth": 0.5, "idm_dist": 1.0, "idm_age": 36, "wait": 6, "cisd1m": 20, "stop_buf": 0.25,
             "min_stop": 8.0, "max_stop": 80.0, "vix_k": 1.0, "min_rr": 1.5, "max_rr": 8.0, "be_r": 1.0, "be_off": 1.25,
             "t_check_at": 15, "t_check_x": 0.3, "t_check_mfe": 0.5, "wk_stop_n": 2, "wk_stop_m": 0.5, "flat_mod": 955,
             "win_start": 120, "win_end": 930}

S26 = [d for d in F.SESS if d >= "2026-01-01"]
H1D = [d for d in S26 if d <= "2026-06-30"]
H2D = [d for d in S26 if d >= "2026-07-01"]


# ------------------------------------------------------------------------------------------------ scoring
_RUNS = {}


def run(x):
    key = json.dumps(x, sort_keys=True, default=str)
    if key not in _RUNS:
        _RUNS[key] = F.run({**LIVE, **x})
    return _RUNS[key]


def lit_view(T):
    o = F.score(T)
    for nm, (a, z) in F.SPAN.items():
        if nm not in o or not o[nm].get("n"):
            continue
        TT = [t for t in T if a <= t["day"] <= z]
        o[nm]["true_win"] = round(100.0 * sum(1 for t in TT if (t.get("r") or 0) >= 0.5) / len(TT), 1)
        o[nm] = {k: o[nm].get(k) for k in ("n", "tpw", "wk2", "win", "true_win", "pf", "net", "per_month", "dd", "p10", "f10",
                                             "p20", "f20", "pass_med", "pass_rate", "net_x3", "months_up")}
    return o


def eval_view(T, caps=None):
    U = AC.units(T)
    A.CFG = copy.deepcopy(CFG0)
    if caps:
        A.CFG["two_week"] = {**A.CFG["two_week"], **caps}
    try:
        o = BI.short(BI.score(U))
    finally:
        A.CFG = copy.deepcopy(CFG0)
    return o


def fast(T):
    """H1 / H2 / 2021-25 $ of the LIT size rule (Shapley value function)."""
    s = {"H1": 0.0, "H2": 0.0, "2021-25": 0.0}
    for t in T:
        d = t["day"]
        k = "H1" if "2026-01-01" <= d <= "2026-06-30" else "H2" if d >= "2026-07-01" else "2021-25"
        s[k] += t["pnl"]
    return {k: round(v) for k, v in s.items()}


def day_pnl(T, days):
    m = collections.defaultdict(float)
    for t in T:
        m[t["day"]] += t["pnl"]
    return np.array([m.get(d, 0.0) for d in days])


def boot(Tv, Tb, days, n=4000, seed=11):
    """Paired day bootstrap of variant minus base $ on `days`: mean diff, 90% interval, P(diff <= 0)."""
    dv = day_pnl(Tv, days) - day_pnl(Tb, days)
    if not np.any(dv):
        return {"diff": 0, "lo": 0, "hi": 0, "p_le0": None}
    rng = np.random.default_rng(seed)
    ix = rng.integers(0, len(days), size=(n, len(days)))
    s = dv[ix].sum(1)
    return {"diff": round(float(dv.sum())), "lo": round(float(np.percentile(s, 5))), "hi": round(float(np.percentile(s, 95))),
            "p_le0": round(float((s <= 0).mean()), 3)}


def months(T):
    m = collections.defaultdict(float)
    for t in T:
        if t["day"] >= "2026-01-01":
            m[t["day"][:7]] += t["pnl"]
    return {k: round(v) for k, v in sorted(m.items())}


def full(x, caps=None):
    T = run(x)
    Tb = run({})
    return {"params": x, "caps": caps, "lit": lit_view(T), "eval": eval_view(T, caps),
            "boot_h1": boot(T, Tb, H1D), "boot_h2": boot(T, Tb, H2D), "months": months(T),
            "exits_2026": dict(collections.Counter(t["exit"] for t in T if t["day"] >= "2026"))}


def line(nm, o):
    L, E = o["lit"], o["eval"]
    f = lambda s: (f"n={L[s]['n']} {L[s]['tpw']}/wk PF {L[s]['pf']} {L[s]['net']:+,}" if L.get(s, {}).get("n") else "n=0")  # noqa
    g = lambda s: f"{E[s]['net']:+,} 2w {E[s]['p10']}/{E[s]['f10']} med {E[s]['pass_med']}"  # noqa
    return f"{nm:16s} LIT H1[{f('H1')}] H2[{f('H2')}] 21-25[{f('2021-25')}] | eval H1[{g('H1')}] H2[{g('H2')}]"


# ------------------------------------------------------------------------------------------------ study parts
def ok_h1(o, b, tol_usd=0.0):
    """'Costs nothing in H1': H1 LIT $ not lower, H1 eval 2-week pass not lower by > 1 pt, fail not higher by > 1 pt, still
    2+ trades a week in H1."""
    L, E, LB, EB = o["lit"]["H1"], o["eval"]["H1"], b["lit"]["H1"], b["eval"]["H1"]
    return (L["net"] >= LB["net"] - tol_usd and E["p10"] >= EB["p10"] - 1.0 and E["f10"] <= EB["f10"] + 1.0 and L["tpw"] >= 2.0)


def greedy(base):
    cur, path, left = {}, [], list(REMOVE)
    ref = base
    while True:
        best = None
        for c in left:
            x = {**cur, **REMOVE[c][1]}
            o = full(x)
            if ok_h1(o, ref) and (best is None or o["lit"]["H1"]["net"] > best[1]["lit"]["H1"]["net"]):
                best = (c, o)
        if best is None:
            break
        c, o = best
        cur = {**cur, **REMOVE[c][1]}
        left.remove(c)
        ref = o
        path.append({"drop": c, "params": dict(cur), "res": o})
        print("greedy drop", line(c, o), flush=True)
    return path


def shapley(perms=80, seed=5):
    """Sampled Shapley value of each binary component on the LIT size rule $ (H1, H2, 2021-25), starting from 'everything
    removed' = the bare detector (any sweep of a LIT level + a 5m CISD) with fixed 3R, no BE, ..."""
    comps = list(REMOVE)
    cache = {}

    def v(S):
        key = frozenset(S)
        if key not in cache:
            x = {}
            for c in comps:
                if c not in S:
                    x.update(REMOVE[c][1])
            cache[key] = fast(run(x))
            if len(_RUNS) > 400:          # keep memory down
                _RUNS.clear()
        return cache[key]

    rng = random.Random(seed)
    phi = {c: {"H1": 0.0, "H2": 0.0, "2021-25": 0.0} for c in comps}
    for p in range(perms):
        order = comps[:]
        rng.shuffle(order)
        S = set()
        prev = v(S)
        for c in order:
            S.add(c)
            cur = v(S)
            for k in phi[c]:
                phi[c][k] += (cur[k] - prev[k]) / perms
            prev = cur
        if (p + 1) % 10 == 0:
            print(f"shapley {p + 1}/{perms} ({len(cache)} subsets)", flush=True)
    return {"phi": {c: {k: round(x) for k, x in d.items()} for c, d in phi.items()}, "empty": v(set()), "all": v(set(comps)),
            "perms": perms, "subsets": len(cache)}


def sensitivity(base):
    out = {}
    for k, (vals, mk) in KNOBS.items():
        rows = []
        for v in vals:
            o = full(mk(v)) if v != KNOB_LIVE[k] else base
            rows.append({"v": v, "live": v == KNOB_LIVE[k], "h1": o["lit"]["H1"]["net"], "h2": o["lit"]["H2"]["net"],
                         "y26": o["lit"]["2026"]["net"], "y2125": o["lit"]["2021-25"]["net"], "pf26": o["lit"]["2026"]["pf"],
                         "tpw": o["lit"]["2026"]["tpw"], "e_h1": o["eval"]["H1"]["p10"], "e_h2": o["eval"]["H2"]["p10"],
                         "ef_h1": o["eval"]["H1"]["f10"], "ef_h2": o["eval"]["H2"]["f10"], "en_h2": o["eval"]["H2"]["net"]})
        i = next(j for j, r in enumerate(rows) if r["live"])
        nb = [rows[j] for j in (i - 1, i + 1) if 0 <= j < len(rows)]
        b = rows[i]["y26"]
        worst = min(r["y26"] for r in nb)
        mean = float(np.mean([r["y26"] for r in nb]))
        if all(r["y26"] < 0.85 * b for r in nb):
            kind = "spike"
        elif all(abs(r["y26"] - b) <= 0.10 * abs(b) for r in nb):
            kind = "plateau"
        elif any(r["y26"] > b * 1.05 for r in nb):
            kind = "edge (a neighbour is better)"
        else:
            kind = "slope"
        out[k] = {"rows": rows, "kind": kind, "nb_mean_pct": round(100 * mean / b, 1), "nb_worst_pct": round(100 * worst / b, 1)}
        print(f"knob {k:12s} {kind:28s} " + " ".join(f"{r['v']}:{r['y26'] / 1000:+.1f}k/{r['h2'] / 1000:+.1f}k" for r in rows), flush=True)
    return out


def main():
    res = {"built": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"), "live": LIVE}
    base = full({})
    res["base"] = base
    print(line("LIVE", base), flush=True)
    res["remove"], res["extra"], res["caps"] = {}, {}, {}
    for nm, (lab, x) in REMOVE.items():
        o = full(x); o["label"] = lab; res["remove"][nm] = o
        print(line("-" + nm, o), flush=True)
    for nm, (lab, x) in EXTRA.items():
        o = full(x); o["label"] = lab; res["extra"][nm] = o
        print(line(nm, o), flush=True)
    for nm, (lab, c) in CAPS.items():
        o = full({}, caps=c); o["label"] = lab; res["caps"][nm] = o
        print(line(nm, o), flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    res["greedy"] = greedy(base)
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    res["sens"] = sensitivity(base)
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    res["shapley"] = shapley()
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    print("wrote", OUT, flush=True)
    return res


OUT_F = os.path.join(ROOT, "research", "lit", "ablation_follow.json")
# follow-up: finer grids around the leads of the main run, the candidate combinations, the eval room cap
FOLLOW = collections.OrderedDict(
    [(f"idm_age{a}", ({"idm_a": [1.0, a, 1]}, None)) for a in (14, 16, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 33)]
    + [(f"idm_{d}_{a}", ({"idm_a": [d, a, 1]}, None)) for d in (0.75, 1.25, 1.5) for a in (18, 24, 30)]
    + [(f"disp{v}", ({"disp": v}, None)) for v in (0.7, 0.75, 0.78, 0.82, 0.85, 0.9)]
    + [(f"max_rr{v}", ({"max_rr": v}, None)) for v in (7.0, 7.5, 8.5, 9.0)]
    + [(f"room{v}", ({}, {"room_f": v})) for v in (0.4, 0.45, 0.5, 0.55, 0.65)]
    + [("idm24_room05", ({"idm_a": [1.0, 24, 1]}, {"room_f": 0.5})),
       ("idm24_nowk", ({"idm_a": [1.0, 24, 1], "wk_stop": None}, None)),
       ("nowk_room05", ({"wk_stop": None}, {"room_f": 0.5})),
       ("nowk_minrr", ({"wk_stop": None, "min_rr": 0.01}, None)),
       ("idm24_nowk_room05", ({"idm_a": [1.0, 24, 1], "wk_stop": None}, {"room_f": 0.5}))]
    + [(f"cisd{v}", ({"cisd1m": v}, None)) for v in (18, 19, 21, 22, 24, 25)]
    + [("room055_nowk", ({"wk_stop": None}, {"room_f": 0.55})),
       ("room055_cisd23", ({"cisd1m": 23}, {"room_f": 0.55})),
       ("nowk_cisd23", ({"wk_stop": None, "cisd1m": 23}, None)),
       ("nowk_cisd23_room055", ({"wk_stop": None, "cisd1m": 23}, {"room_f": 0.55})),
       ("nowk_win1430", ({"wk_stop": None, "window": [[120, 870]]}, None)),
       ("simple_all", ({"wk_stop": None, "window": [[120, 870]], "cisd1m": 23}, {"room_f": 0.55})),
       ("nowk_cisd22", ({"wk_stop": None, "cisd1m": 22}, None)),
       ("nowk_cisd22_room055", ({"wk_stop": None, "cisd1m": 22}, {"room_f": 0.55})),
       ("cisd22_room055", ({"cisd1m": 22}, {"room_f": 0.55})),
       ("minimal_tol", ({"wk_stop": None, "min_rr": 0.01, "flat_mod": 1010, "be_off": 0.0}, None))])


def greedy_tol(tol=600.0):
    """Tolerant greedy: drop a component when H1 LIT $ falls by at most tol and the H1 eval 2-week odds hold (+-1 pt)."""
    base = full({})
    cur, path, left, ref = {}, [], list(REMOVE), base
    while True:
        best = None
        for c in left:
            o = full({**cur, **REMOVE[c][1]})
            if ok_h1(o, ref, tol) and (best is None or o["lit"]["H1"]["net"] > best[1]["lit"]["H1"]["net"]):
                best = (c, o)
        if best is None:
            break
        c, o = best
        cur = {**cur, **REMOVE[c][1]}
        left.remove(c)
        ref = o
        path.append({"drop": c, "params": dict(cur), "res": o})
        print("greedy_tol drop", line(c, o), flush=True)
    res = json.load(open(OUT_F)) if os.path.exists(OUT_F) else {}
    res["greedy_tol"] = {"tol": tol, "path": path}
    json.dump(res, open(OUT_F, "w"), indent=1, default=float)


def follow(only=None):
    res = json.load(open(OUT_F)) if (only and os.path.exists(OUT_F)) else {}
    base = full({})
    res["base"] = base
    for nm, (x, c) in FOLLOW.items():
        if only and not any(nm.startswith(o) for o in only):
            continue
        o = full(x, caps=c); res[nm] = o
        print(line(nm, o), flush=True)
        json.dump(res, open(OUT_F, "w"), indent=1, default=float)
    return res


def _k(v):
    return f"{v / 1000:+.1f}k" if v is not None else "-"


def tables(path_md):
    """Markdown tables for the write-up from ablation.json + ablation_follow.json."""
    R = json.load(open(OUT)); Fw = json.load(open(OUT_F)) if os.path.exists(OUT_F) else {}
    b = R["base"]
    L = []

    def rowA(nm, lab, o):
        l = o["lit"]; y = l["2026"]
        return (f"| {lab} | {_k(l['H1']['net'])} | {_k(l['H2']['net'])} | {_k(l['2021-25']['net'])} | {y['pf']} | "
                f"{y['win']} / {y['true_win']} | {y['tpw']} | {y['wk2']} | {_k(y['dd'])} | ${l['H2']['per_month']:,} |")

    def rowB(nm, lab, o):
        e = o["eval"]
        return (f"| {lab} | {_k(e['H1']['net'])} | {_k(e['H2']['net'])} | {e['H1']['p10']} / {e['H1']['f10']} | "
                f"{e['H2']['p10']} / {e['H2']['f10']} | {e['H1']['p20']} / {e['H1']['f20']} | {e['H2']['p20']} / {e['H2']['f20']} | "
                f"{e['H1']['pass_med']} / {e['H2']['pass_med']} | {e['H1']['mc_p10']}/{e['H1']['mc_f10']} · {e['H2']['mc_p10']}/{e['H2']['mc_f10']} |")
    hA = ("| variant | H1 $ | H2 $ | 2021-25 $ | PF 2026 | win % / >=0.5R % 2026 | trades/wk 2026 | % weeks 2+ | max DD 2026 | "
          "H2 $/month |\n|---|---|---|---|---|---|---|---|---|---|")
    hB = ("| variant | H1 $ | H2 $ | 2-wk pass/fail H1 | 2-wk H2 | 1-mo pass/fail H1 | 1-mo H2 | median sessions to pass H1/H2 | "
          "Monte Carlo 2-wk H1 · H2 |\n|---|---|---|---|---|---|---|---|---|")
    groups = [("remove", "Remove one component", R["remove"]), ("extra", "Neighbours and alternatives", R["extra"]),
              ("caps", "Eval caps (eval path only)", R["caps"])]
    for g, title, D in groups:
        L.append(f"\n#### {title}: LIT size rule\n\n" + hA)
        L.append(rowA("live", "**live LIT**", b))
        for nm, o in D.items():
            if g != "caps":
                L.append(rowA(nm, f"{o.get('label', nm)} (`{nm}`)", o))
        L.append(f"\n#### {title}: eval path (two_week sizing)\n\n" + hB)
        L.append(rowB("live", "**live LIT**", b))
        for nm, o in D.items():
            L.append(rowB(nm, f"{o.get('label', nm)} (`{nm}`)", o))
    if Fw:
        L.append("\n#### Follow-up grids: LIT size rule\n\n" + hA)
        for nm, o in Fw.items():
            if isinstance(o, dict) and "lit" in o and nm != "base" and not o.get("caps"):
                L.append(rowA(nm, f"`{nm}` {json.dumps(o['params'])}", o))
        L.append("\n#### Follow-up grids: eval path\n\n" + hB)
        for nm, o in Fw.items():
            if isinstance(o, dict) and "eval" in o and nm != "base":
                L.append(rowB(nm, f"`{nm}` {json.dumps(o['params'])} {json.dumps(o.get('caps') or '')}", o))
    # sensitivity
    L.append("\n#### Sensitivity (2026 $ / H2 $ / 2021-25 $ / eval 2-wk pass H1-H2; live value in bold)\n")
    L.append("| knob | verdict | values |\n|---|---|---|")
    for k, s in R["sens"].items():
        cells = []
        for r in s["rows"]:
            c = f"{r['v']}: {_k(r['y26'])} / {_k(r['h2'])} / {_k(r['y2125'])} / {r['e_h1']}-{r['e_h2']}"
            cells.append(f"**{c}**" if r["live"] else c)
        L.append(f"| {k} | {s['kind']} | " + " · ".join(cells) + " |")
    # shapley
    if "shapley" in R:
        S = R["shapley"]
        L.append(f"\n#### Shapley split of the LIT-rule $ ({S['perms']} random orders, {S['subsets']} subsets; bare detector "
                 f"H1 {_k(S['empty']['H1'])} H2 {_k(S['empty']['H2'])} 2021-25 {_k(S['empty']['2021-25'])} -> live "
                 f"H1 {_k(S['all']['H1'])} H2 {_k(S['all']['H2'])} 2021-25 {_k(S['all']['2021-25'])})\n")
        L.append("| component | H1 $ | H2 $ | 2021-25 $ | leave-one-out H1 / H2 $ |\n|---|---|---|---|---|")
        for c, d in sorted(S["phi"].items(), key=lambda kv: -kv[1]["H2"]):
            o = R["remove"][c]["lit"]
            L.append(f"| {REMOVE[c][0]} (`{c}`) | {_k(d['H1'])} | {_k(d['H2'])} | {_k(d['2021-25'])} | "
                     f"{_k(b['lit']['H1']['net'] - o['H1']['net'])} / {_k(b['lit']['H2']['net'] - o['H2']['net'])} |")
    open(path_md, "w").write("\n".join(L) + "\n")
    print("wrote", path_md)


def mtest():
    """Multiple-testing count over every variant scored (single, extra, sensitivity points are inside the same runs cache)."""
    R = json.load(open(OUT)); Fw = json.load(open(OUT_F)) if os.path.exists(OUT_F) else {}
    b = R["base"]
    V = {**R["remove"], **R["extra"], **{k: v for k, v in Fw.items() if isinstance(v, dict) and "lit" in v and k != "base"
                                         and not v.get("caps")}}
    rows = []
    for nm, o in V.items():
        l, bl = o["lit"], b["lit"]
        if l["2026"]["net"] == bl["2026"]["net"] and l["2021-25"]["net"] == bl["2021-25"]["net"]:
            continue
        e, be = o["eval"], b["eval"]
        rows.append({"nm": nm, "h1": l["H1"]["net"] - bl["H1"]["net"], "h2": l["H2"]["net"] - bl["H2"]["net"],
                     "r": l["2021-25"]["net"] - bl["2021-25"]["net"], "p": o["boot_h2"]["p_le0"],
                     "ev": (e["H1"]["p10"] - be["H1"]["p10"], e["H2"]["p10"] - be["H2"]["p10"], e["H1"]["f10"] - be["H1"]["f10"],
                            e["H2"]["f10"] - be["H2"]["f10"])})
    n = len(rows)
    both = [r for r in rows if r["h1"] > 0 and r["h2"] > 0]
    all3 = [r for r in both if r["r"] > 0]
    evok = [r for r in both if r["ev"][0] >= 0 and r["ev"][1] >= 0 and r["ev"][2] <= 0 and r["ev"][3] <= 0]
    p10 = [r for r in rows if r["p"] is not None and r["p"] <= 0.10 and r["h2"] > 0]
    out = {"n": n, "both_halves": [r["nm"] for r in both], "both_and_ref": [r["nm"] for r in all3],
           "both_and_eval": [r["nm"] for r in evok], "h2_p10": [(r["nm"], r["p"], r["h2"]) for r in p10], "rows": rows}
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    Fw["mtest"] = out
    json.dump(Fw, open(OUT_F, "w"), indent=1, default=float)
    return out


Q = ("Owner 2026-10-23: 'Give me things to improve our current strategy. Maybe take things away.' Ablation / simplification of "
     "the live LIT: what does each component earn in 2026 H1 (pick) / H2 (check), what can go?")


def _h(s):
    return (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}")


def _he(s):
    return (f"PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}; 2-week pass/fail {s['p10']}/{s['f10']} "
            f"(Monte Carlo {s['mc_p10']}/{s['mc_f10']}), 1 month {s['p20']}/{s['f20']}, median {s['pass_med']} sessions")


def save_one(rid, title, x, caps=None, status="info", verdict_head="", family="other", eval_run=False):
    from tools import runlib as rl
    T = run(x)
    o = full(x, caps)
    Ts = [{k: v for k, v in t.items() if not k.startswith("_") and k not in ("size_why", "size_mult")} for t in T]
    P = {**lit.DEFAULTS, **LIVE, **x}
    l, e = o["lit"], o["eval"]
    rl.save(rid, title, family, Q, params=P, trades=Ts, scored=rl.score(Ts, F.SESS), status=status,
            verdict=f"{verdict_head} LIT size rule: 2026 H1 (pick) {_h(l['H1'])}; H2 (check) {_h(l['H2'])}; 2021-25 reference "
                    f"{_h(l['2021-25'])}. Eval path (two_week{', caps ' + json.dumps(caps) if caps else ''}): H1 {_he(e['H1'])}; "
                    f"H2 {_he(e['H2'])}.",
            notes="tools/lit_ablation.py: engine/lit.py run_x on live_model.json lit + these params.", writeup="lit-ablation",
            tags=["lit", "lit_ablation"])
    if eval_run:
        U = AC.units(T)
        A.CFG = copy.deepcopy(CFG0)
        if caps:
            A.CFG["two_week"] = {**A.CFG["two_week"], **caps}
        Tp = []
        for sp in ("H1", "H2"):
            Tp += A.b2b(U, sp)[0]
        cfg = copy.deepcopy(A.CFG)
        A.CFG = copy.deepcopy(CFG0)
        for t in Tp:
            t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
            t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
        rl.save(rid + "_eval", title + " (eval path, two_week sizing)", family, Q, params=P, sizing={"mode": "two_week", **cfg},
                trades=Tp, scored=rl.score(Tp, A.S26), status=status,
                verdict=f"{verdict_head} Eval path: H1 (pick) {_he(e['H1'])}. H2 (check) {_he(e['H2'])}. 2021-25: no 1m bars.",
                notes="tools/lit_ablation.py: the engine's trades as units, sized by the live two_week rules (stored trades = the "
                      "back-to-back eval path per half).", writeup="lit-ablation", tags=["lit", "lit_ablation"])
    print("saved", rid, flush=True)


def save():
    from tools import runlib as rl
    idx = rl.index
    rl.index = lambda: None              # one index rebuild at the end (python tools/runlib.py index)
    try:
        R = json.load(open(OUT))
        for c, (lab, x) in REMOVE.items():
            save_one("abl_rm_" + c, "LIT live minus " + lab, x, status="info",
                     verdict_head=f"Ablation: the live LIT without the {lab}.")
        save_one("abl_minimal", "Minimal LIT (greedy: drops that cost nothing in H1: " +
                 ", ".join(p["drop"] for p in R["greedy"]) + ")", R["greedy"][-1]["params"], status="info", eval_run=True,
                 verdict_head="Greedy minimal LIT.")
        for rid, title, x, caps, st in REC:
            save_one(rid, title, x, caps=caps, status=st, eval_run=True, verdict_head="Ablation recommendation.")
    finally:
        rl.index = idx


# recommendations (filled after the study; see research/writeups/lit-ablation.md)
REC = [
    ("abl_rec_no_wk_stop", "LIT live without the weekly stop (simplification)", {"wk_stop": None}, None, "promising"),
    ("abl_rec_room055", "LIT live, two_week room cap 55% instead of 60%", {}, {"room_f": 0.55}, "promising"),
    ("abl_rec_cisd22", "LIT live, 1m CISD window 22 bars instead of 20 (off the cliff edge)", {"cisd1m": 22}, None, "promising"),
    ("abl_rec_combo", "LIT live: no weekly stop + cisd1m 22", {"wk_stop": None, "cisd1m": 22}, None, "promising"),
    ("abl_minimal_tol", "Minimal LIT, tolerant greedy (no weekly stop, no 1.5R floor, hold to 16:55, plain BE)",
     {"wk_stop": None, "min_rr": 0.01, "flat_mod": 1010, "be_off": 0.0}, None, "info"),
    ("abl_rec_cisd22_room055", "LIT live, cisd1m 22 + two_week room cap 55% (changes 1 + 2)", {"cisd1m": 22}, {"room_f": 0.55},
     "promising"),
    ("abl_lead_idm_age24", "LIT live, inducement at most 24 bars old (lead only: one H2 trade)", {"idm_a": [1.0, 24, 1]}, None,
     "info"),
]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "save":
        save()
    if len(sys.argv) > 1 and sys.argv[1] == "tables":
        tables(sys.argv[2])
    if len(sys.argv) > 1 and sys.argv[1] == "mtest":
        mtest()
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        main()
    elif len(sys.argv) > 1 and sys.argv[1] == "follow":
        follow(sys.argv[2:] or None)
    elif len(sys.argv) > 1 and sys.argv[1] == "greedy_tol":
        greedy_tol()
