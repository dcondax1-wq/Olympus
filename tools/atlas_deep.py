"""ATLAS deep edge (2026-11-15, team E-ATLAS): baseline, loser autopsy and new ideas for ATLAS on the MFFU Builder 25K.

Research only: nothing here touches second_model.json, engine/account_b.py or any live file. Executor = tools/atlas_v2.score
(tools/atlas.py + tools/second_account_b.py: the real account-B rules: need size, one position, max 2 a day, never
opposite LIT incl. LIT's armed setups, $600 soft daily loss, stuck under $100; money averaged over back-to-back eval paths
started every 5th session). Fees at the owner's real ATLAS 25K price ($43, CLAUDE.md).

New here (every idea written down in IDEAS before its first run; each is a key "deep" in the variant, absent = today):
  * refuted side: skip an ATLAS entry when a trade on the SAME side already lost today (ATLAS member paper trade / LIT /
    either), known at the entry (that trade closed before it)
  * LIT overlap: skip an ATLAS entry while LIT holds the same side (two accounts on one bet); skip ATLAS on the same side
    after LIT WON that side today (the move is spent)
  * stop outlier: skip an entry whose stop is > k x the member's own median stop of its last 20 trades (a sloppy sweep)
  * room-aware first trade: the eval's first trade(s) at half size until the eval is green (protect the $1,000 start)
  * weekly brake on the eval: no new ATLAS entry for the rest of the ISO week after the week lost >= $X (eval only)
  * daily trend (prior close vs its 20-session SMA): skip / half size against it
  * same-side cap: max 1 ATLAS trade per side per day (the 2nd trade only on the other side)

    python -X utf8 tools/atlas_deep.py autopsy   # loser autopsy -> research/second/atlas_deep_autopsy.json
    python -X utf8 tools/atlas_deep.py grid      # every idea -> research/second/atlas_deep_grid.json
    python -X utf8 tools/atlas_deep.py placebo   # random-skip controls of the grid's passers
    python -X utf8 tools/atlas_deep.py save      # runs atlas_deep_* in the run library
Paper research only.
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import atlas as A  # noqa: E402
from tools import atlas_v2 as V2  # noqa: E402
from tools import second_mix as M  # noqa: E402
from tools import second_account_b as AB  # noqa: E402

V2.PRICE = 43.0                       # the owner's real ATLAS 25K price (2026-10-26), one-time, $0 activation
SPANS = ("H1", "H2", "2025", "2021-24")
OUT_AUT = os.path.join(ROOT, "research", "second", "atlas_deep_autopsy.json")
OUT = os.path.join(ROOT, "research", "second", "atlas_deep_grid.json")
MONEY = V2.MONEY
RISK_USD = 500.0                      # the fixed-risk view of the autopsy


def span_of(d):
    for s in SPANS:
        a, z = M.SPANS[s]
        if a <= d <= z:
            return s
    return None


# ================================================================================================ facts
_C = {}


def bars5():
    if "b5" not in _C:
        from tools import lit_final as F
        Mk, _ = F.market("cisd", [])
        _C["b5"] = F.bars(Mk, "5m")
    return _C["b5"]


def atr5(ts):
    """ATR(14) of the 5m bars closed before ts (Wilder-free simple mean of the true range)."""
    if "atr" not in _C:
        B = bars5()
        pc = np.r_[B.c[0], B.c[:-1]]
        tr = np.maximum(B.h - B.l, np.maximum(abs(B.h - pc), abs(B.l - pc)))
        cs = np.cumsum(np.r_[0.0, tr])
        _C["atr"] = (B.t, cs)
    t, cs = _C["atr"]
    k = int(np.searchsorted(t, int(ts)))         # bars with open < ts (the entry bar opens at ts)
    if k < 15:
        return float("nan")
    return float((cs[k] - cs[k - 14]) / 14.0)


def daily_trend():
    """day -> +1 / -1: the prior session's close above / below the SMA of the last 20 session closes (data/NQ_1d.csv,
    labelled by trading day as tools/atlas_v2.atr_pct). Known before the day opens."""
    if "dt" not in _C:
        import pandas as pd
        import zoneinfo
        import bisect
        ET = zoneinfo.ZoneInfo("America/New_York")
        d = pd.read_csv(os.path.join(ROOT, "data", "NQ_1d.csv"))
        lab = []
        for t in d["time"]:
            x = dt.datetime.fromtimestamp(int(t), ET)
            if x.hour >= 17:
                x = x + dt.timedelta(days=1)
            while x.weekday() >= 5:
                x = x + dt.timedelta(days=1)
            lab.append(x.date().isoformat())
        c = d["close"].astype(float).values
        sma = pd.Series(c).rolling(20).mean().values
        out = {}
        for i in range(1, len(lab)):
            j = i - 1
            if not np.isnan(sma[j]):
                out[lab[i]] = 1 if c[j] > sma[j] else -1
        keys = sorted(out)
        res = {}
        for s in M.units()["sessions"]:
            if s in out:
                res[s] = out[s]
            else:
                k = bisect.bisect_right(keys, s) - 1
                res[s] = out[keys[k]] if k >= 0 else 0
        _C["dt"] = res
    return _C["dt"]


def r_net(u):
    """R of one candidate trade at a fixed risk, costs in ($1.90 a micro round trip; the unit's pts carry the slippage)."""
    return (u["pts"] * M.PV - M.ECOMM) / (u["risk"] * M.PV)


def lit_by_day():
    by = collections.defaultdict(list)
    for t in M.units()["LIT"]:
        by[t["day"]].append(t)
    return by


def member_by_day():
    """All ATLAS members' paper trades (before the no-hedge rules: the members' own ledgers) by day."""
    by = collections.defaultdict(list)
    for nm in A.NAMES:
        for u in M.units()[nm]:
            by[u["day"]].append(u)
    for d in by:
        by[d].sort(key=lambda u: u["entry_t"])
    return by


def feats(U):
    """Facts of every candidate unit, all known at its entry."""
    LB, MB, VP, TR = lit_by_day(), member_by_day(), A.vix_prev(), daily_trend()
    hist = collections.defaultdict(list)          # member -> stops of its earlier trades
    allm = sorted((u for nm in A.NAMES for u in M.units()[nm]), key=lambda u: u["entry_t"])
    med20 = {}
    for u in allm:
        h = hist[u["src"]]
        med20[(u["src"], u["entry_t"])] = float(np.median(h[-20:])) if len(h) >= 10 else float("nan")
        h.append(u["risk"])
    rows = []
    for u in U:
        e = u["entry_t"]
        L = LB.get(u["day"], ())
        lit_done = [x for x in L if x["exit_t"] <= e]
        lit_open = [x for x in L if x["entry_t"] <= e < x["exit_t"]]
        mem_done = [x for x in MB.get(u["day"], ()) if x["exit_t"] <= e]
        a = atr5(e)
        rows.append({
            "src": u["src"], "day": u["day"], "span": span_of(u["day"]), "dir": u["dir"], "exit": u["exit"],
            "R": r_net(u), "risk": u["risk"], "rr": u["tgt"] / u["risk"] if u["risk"] else float("nan"),
            "stop_atr": u["risk"] / a if a == a and a > 0 else float("nan"),
            "stop_med20": u["risk"] / med20.get((u["src"], e), float("nan")),
            "hour": A.et_mod(e) // 60, "dow": dt.date.fromisoformat(u["day"]).weekday(), "vix": VP.get(u["day"], float("nan")),
            "trend": TR.get(u["day"], 0) * u["dir"],
            "lit_same_open": any(x["dir"] == u["dir"] for x in lit_open),
            "lit_same_won": any(x["dir"] == u["dir"] and x["pts"] > 0 for x in lit_done),
            "lit_same_lost": any(x["dir"] == u["dir"] and x["pts"] <= 0 for x in lit_done),
            "lit_opp_lost": any(x["dir"] != u["dir"] and x["pts"] <= 0 for x in lit_done),
            "lit_won_other": any(x["dir"] != u["dir"] and x["pts"] > 0 for x in lit_done),
            "lit_none_yet": not lit_done and not lit_open,
            "mem_same_lost": any(x["dir"] == u["dir"] and r_net(x) < 0 for x in mem_done),
            "mem_same_won": any(x["dir"] == u["dir"] and r_net(x) > 0 for x in mem_done),
            "mem_opp_done": any(x["dir"] != u["dir"] for x in mem_done),
            "k_today": sum(1 for x in MB.get(u["day"], ()) if x["entry_t"] < e) + 1,
        })
    return rows


# ================================================================================================ autopsy
def _agg(R):
    R = np.array(R, float)
    if not len(R):
        return {"n": 0}
    g, l = R[R > 0].sum(), -R[R < 0].sum()
    return {"n": int(len(R)), "win": round(100.0 * float((R > 0).mean()), 1), "avgR": round(float(R.mean()), 3),
            "pf": round(float(g / l), 2) if l else None, "usd": round(float(R.sum()) * RISK_USD)}


def autopsy():
    V2.install()
    U = A.account_units(A.BASE)
    F = feats(U)
    vix_cut = np.nanpercentile([f["vix"] for f in F if f["span"] == "H1"], [33.3, 66.7])
    sa_cut = np.nanpercentile([f["stop_atr"] for f in F if f["span"] == "H1"], [33.3, 66.7])
    rr_cut = np.nanpercentile([f["rr"] for f in F if f["span"] == "H1"], [33.3, 66.7])

    def terc(x, c):
        return "nan" if x != x else ("low" if x < c[0] else "mid" if x < c[1] else "high")

    groups = {
        "member": lambda f: f["src"],
        "member_dir": lambda f: f"{f['src']} {'long' if f['dir'] == 1 else 'short'}",
        "hour": lambda f: f"{f['hour']:02d}",
        "weekday": lambda f: "MTWTF"[f["dow"]] + str(f["dow"]),
        "vix_tercile(H1 cuts)": lambda f: terc(f["vix"], vix_cut),
        "stop_in_atr5(H1 cuts)": lambda f: terc(f["stop_atr"], sa_cut),
        "stop_pts": lambda f: "<25" if f["risk"] < 25 else "25-40" if f["risk"] < 40 else "40-60" if f["risk"] < 60 else "60+",
        "stop_vs_member_median20": lambda f: "nan" if f["stop_med20"] != f["stop_med20"] else
        ("<0.75x" if f["stop_med20"] < 0.75 else "0.75-1.25x" if f["stop_med20"] < 1.25 else "1.25-1.6x" if f["stop_med20"] < 1.6 else ">=1.6x"),
        "target_rr(H1 cuts)": lambda f: terc(f["rr"], rr_cut),
        "daily_trend": lambda f: {1: "with", -1: "against", 0: "?"}[f["trend"]],
        "lit_today": lambda f: ("LIT open same side" if f["lit_same_open"] else "LIT won same side" if f["lit_same_won"] else
                                "LIT lost same side" if f["lit_same_lost"] else "LIT lost other side" if f["lit_opp_lost"] else
                                "LIT not yet" if f["lit_none_yet"] else "LIT other"),
        "member_paper_today": lambda f: ("same side lost earlier" if f["mem_same_lost"] else "same side won earlier" if f["mem_same_won"]
                                         else "other side earlier" if f["mem_opp_done"] else "first closed"),
        "nth_signal_today": lambda f: str(min(f["k_today"], 3)),
        "exit_kind": lambda f: f["exit"],
    }
    out = {"cuts": {"vix": list(map(float, vix_cut)), "stop_atr": list(map(float, sa_cut)), "rr": list(map(float, rr_cut))}, "groups": {}}
    sp = {"H1": ("H1",), "H2": ("H2",), "2021-25": ("2025", "2021-24")}
    for g, fn in groups.items():
        cells = collections.defaultdict(lambda: collections.defaultdict(list))
        for f in F:
            if f["span"] is None:
                continue
            for lab, ss in sp.items():
                if f["span"] in ss:
                    cells[fn(f)][lab].append(f["R"])
        out["groups"][g] = {k: {lab: _agg(v.get(lab, [])) for lab in sp} for k, v in sorted(cells.items())}
    out["all"] = {lab: _agg([f["R"] for f in F if f["span"] in ss]) for lab, ss in sp.items()}
    json.dump(out, open(OUT_AUT, "w"), indent=1)
    print("ALL", out["all"])
    for g, cells in out["groups"].items():
        print("\n==", g)
        for k, v in cells.items():
            print(f"  {k:24s} " + " | ".join(f"{lab} n{v[lab]['n']:3d} w{v[lab].get('win', 0):5.1f} R{v[lab].get('avgR', 0):+.2f} ${v[lab].get('usd', 0):+7,}"
                                            for lab in sp))
    return out


# ================================================================================================ the executor hooks
_UM = {}          # name -> {(src, entry_t): size multiplier}; 0 = skip (the slot stays free, as a filter)


def _patch():
    if getattr(A, "_deep_patched", False):
        return
    from engine import account_b as EAB
    orig = A.q_variant

    def qv(t, st, V, _orig=orig):
        q = _orig(t, st, V)
        D = V.get("deep") or {}
        lb = D.get("last_bullet")
        if q <= 0 and lb and A.lit.qty_for(float(t["risk"])):
            # zombie eval (need size says 0: one micro's stop-out does not fit 50% of the room): 1 micro when its full
            # stop-out (+ costs + 1 tick) fits lb x the room, and the day's soft loss (dll_guard)
            from engine import sizing as SZ        # = engine/account_b.last_bullet (2 ticks of stop slippage, $1.90)
            cost = (float(t["risk"]) + SZ.TW_DLL_SLIP) * SZ.TW_PV + SZ.TW_COMM
            if cost <= float(lb) * st["room"]:
                q = int(EAB.dll_guard({"qty": 1, "reasons": []}, float(t["risk"]), A.spec()["rules"], st)["qty"])
        if q <= 0 or not D:
            return q
        m = 1.0
        k = D.get("um")
        if k:
            m *= _UM[k].get((t["src"], t["entry_t"]), 1.0)
        fh = D.get("first_half")                  # eval not green yet (balance at the session start + today <= 0) -> x m
        if fh and st.get("profit", 0.0) + st.get("cum", 0.0) <= 0.0:
            m *= float(fh)
        wb = D.get("week_brake")                  # the ISO week's P&L of this eval <= -X -> no new entry
        if wb and st.get("wk", 0.0) + st.get("cum", 0.0) <= -float(wb):
            m = 0.0
        if m == 1.0:
            return q
        if m <= 0:
            return 0
        q2 = max(1, int(q * m + 1e-9))
        S = A.spec()
        q2 = min(q2, int(S["rules"]["max_micros"]))
        return int(EAB.dll_guard({"qty": q2, "reasons": []}, float(t["risk"]), S["rules"], st)["qty"])
    A.q_variant = qv
    A._deep_patched = True

    def run_eval(days, by, rule, horizon=20, keep=None):
        """tools/atlas_v2.run_eval + the ISO week's P&L of this eval passed to the sizer (st["wk"])."""
        bal = peak = 0.0
        floor = -M.MLL
        idle = V2.EV["idle"]
        wk, wk_pnl = None, 0.0
        for kk, day in enumerate(days[:horizon]):
            w = dt.date.fromisoformat(day).isocalendar()[:2]
            if w != wk:
                wk, wk_pnl = w, 0.0
            cum, recs, failed = M.play_day(by.get(day, ()), day, bal, floor, kk + 1, rule, False, 2, None, reserve=False,
                                           extra={"wk": wk_pnl})
            if keep is not None:
                keep.extend(recs)
            if failed:
                return "FAIL", kk + 1, 0.0
            bal += cum
            wk_pnl += cum
            if bal <= floor:
                return "FAIL", kk + 1, 0.0
            peak = max(peak, bal)
            floor = min(max(floor, peak - M.MLL), M.LOCK)
            if bal >= M.TGT:
                return "PASS", kk + 1, bal - floor
            room = bal - floor
            if room < V2.EV["min_room"] or (idle and kk + 1 >= idle[0] and room < idle[1]):
                return "STUCK", kk + 1, room
        return "OPEN", min(len(days), horizon), bal - floor
    V2.run_eval = run_eval
    AB.run_eval = run_eval


def score(V):
    _patch()
    return V2.score(V)


# ================================================================================================ the ideas (written before the first run)
IDEAS = [
    ("lit_won_other", "Skip / halve ATLAS when LIT already WON the other side today (LIT's winner says the move is the other way)"),
    ("same_side_retry", "A same-side paper trade (ATLAS member or LIT) already LOST today: refuted side = skip; or a retry after the stop hunt = size up"),
    ("lit_overlap", "Two accounts on one bet: skip ATLAS while LIT holds the same side; skip ATLAS on a side LIT already won today"),
    ("stop_outlier", "Skip an entry whose stop is far wider than the member's own median stop of its last 20 trades (a sloppy sweep)"),
    ("first_half", "Protect the $1,000 start: eval trades at part size until the eval is green"),
    ("week_brake", "Eval weekly brake: no new ATLAS entry for the rest of the week once the week lost $X"),
    ("daily_trend", "Daily trend (prior close vs its 20-session SMA): skip / halve trades against it"),
    ("side_cap", "Max one ATLAS signal per side a day (the 2nd only on the other side)"),
]


def um_from(F, U, fn):
    return {(u["src"], u["entry_t"]): fn(f) for u, f in zip(U, F) if fn(f) != 1.0}


_ROWS = {}


def variants():
    if "r" in _ROWS:
        return _ROWS["r"]
    V2.install()
    U = A.account_units(A.BASE)
    F = feats(U)
    side_first = {}
    for u in U:                                   # the day's first candidate per side (account units, entry order)
        side_first.setdefault((u["day"], u["dir"]), u["entry_t"])
    rows = [("base", "today", {})]

    def add(fam, name, fn=None, **deep):
        if fn is not None:
            _UM[name] = um_from(F, U, fn)
            deep["um"] = name
        rows.append((fam, name, deep))

    for m in (0.0, 0.5):
        add("lit_won_other", f"lit_won_other_x{m:g}", lambda f, m=m: m if f["lit_won_other"] else 1.0)
    add("same_side_retry", "same_side_lost_skip", lambda f: 0.0 if (f["mem_same_lost"] or f["lit_same_lost"]) else 1.0)
    for m in (1.25, 1.5):
        add("same_side_retry", f"same_side_lost_x{m:g}", lambda f, m=m: m if (f["mem_same_lost"] or f["lit_same_lost"]) else 1.0)
    add("lit_overlap", "lit_same_open_skip", lambda f: 0.0 if f["lit_same_open"] else 1.0)
    add("lit_overlap", "lit_same_won_skip", lambda f: 0.0 if f["lit_same_won"] else 1.0)
    for k in (1.6, 2.0):
        add("stop_outlier", f"stop_gt_{k:g}x_med20_skip", lambda f, k=k: 0.0 if f["stop_med20"] == f["stop_med20"] and f["stop_med20"] > k else 1.0)
    for m in (0.5, 0.75):
        add("first_half", f"first_half_x{m:g}", first_half=m)
    for x in (400.0, 600.0):
        add("week_brake", f"week_brake_{x:g}", week_brake=x)
    for m in (0.0, 0.5):
        add("daily_trend", f"against_trend_x{m:g}", lambda f, m=m: m if f["trend"] == -1 else 1.0)
    _UM["side_cap_1"] = {(u["src"], u["entry_t"]): 0.0 for u in U if side_first[(u["day"], u["dir"])] != u["entry_t"]}
    rows.append(("side_cap", "side_cap_1", {"um": "side_cap_1"}))
    # added after the first 16 (counted): the eval-path diagnosis showed half of the candidates are never traded because a
    # low-room eval sizes to 0 micros for weeks (the "zombie" eval of atlas-v2.md) -> keep it trading at 1 micro
    for f in (0.8, 1.0):
        rows.append(("last_bullet", f"last_bullet_{f:g}room", {"last_bullet": f}))
    # the zombie re-buy of atlas-v2.md re-priced at the owner's real $43 (was $63): new eval when the room is under $X
    for x in (200.0, 300.0):
        rows.append(("eval_rebuy43", f"stuck_under_{x:g}", {"min_room": x}))
    # round 2 (after the slot run): neighbours of the two eval-lifecycle leads and their combinations (counted)
    for f in (0.6, 0.7, 0.9):
        rows.append(("last_bullet", f"last_bullet_{f:g}room", {"last_bullet": f}))
    for x in (150.0, 250.0, 400.0):
        rows.append(("eval_rebuy43", f"stuck_under_{x:g}", {"min_room": x}))
    rows.append(("combo", "last_bullet_0.8+stuck_under_200", {"last_bullet": 0.8, "min_room": 200.0}))
    rows.append(("combo", "last_bullet_0.8+lit_won_other_x0", {"last_bullet": 0.8, "um": "lit_won_other_x0"}))
    rows.append(("combo", "stuck_under_300+lit_won_other_x0", {"min_room": 300.0, "um": "lit_won_other_x0"}))
    _ROWS["r"] = rows
    return rows


def V_of(deep):
    V = copy.deepcopy(A.BASE)
    deep = dict(deep or {})
    if "min_room" in deep:                        # an atlas_v2 eval rule (stuck threshold), not a sizer key
        V["min_room"] = deep.pop("min_room")
    if deep:
        V["deep"] = deep
    return V


def line(o, s):
    x = o[s]
    return (f"{s:7s} 2w {x['p10']:5.1f}/{x['f10']:4.1f} dead {x['dead10']:4.1f} med {x['pass_med']} ${x[MONEY]:+7,} "
            f"path {x['net']:+7,} ({x['per_month']:+6,}/mo) PF {x['pf']} DD {x['dd']:,} tpw {x['sig_tpw']} wk2 {x['sig_wk2']}")


def cmd_grid():
    R = variants()
    out, base = [], None
    for fam, name, deep in R:
        o = score(V_of(deep))
        if fam == "base":
            base = o
        v = V2.verdict(o, base, fam)
        out.append({"family": fam, "name": name, "deep": deep, "o": o, "verdict": v,
                    "n_changed": len(_UM.get(deep.get("um"), {})) if deep.get("um") else None})
        print(f"\n[{fam}] {name} {'PASS' if v['pass'] else ''} h1={v['h1']} h2={v['h2']} ref={v['ref']}", flush=True)
        for s in SPANS:
            print("   " + line(o, s), flush=True)
    d = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "price": V2.PRICE, "ideas": IDEAS, "rows": out,
         "n": len(out) - 1, "n_pass": sum(r["verdict"]["pass"] for r in out[1:])}
    json.dump(d, open(OUT, "w"), separators=(",", ":"), default=str)
    print(f"\n{d['n']} variants, {d['n_pass']} pass the v2 test", flush=True)
    return d


def cmd_placebo(name, k=60, seed=11):
    """Random-skip control of a skip filter: the same number of candidate trades skipped per span, drawn at random from
    that span's candidates; share of draws that pass the same test (better in H1 and H2; and the full v2 rule)."""
    R = variants()
    base = score(V_of({}))
    um = _UM[name]
    U = A.account_units(A.BASE)
    keys = [(u["src"], u["entry_t"]) for u in U]
    sp = {kk: span_of(u["day"]) for kk, u in zip(keys, U)}
    need = collections.Counter(sp[kk] for kk in um)
    rng = random.Random(seed)
    res = []
    for j in range(k):
        pick = {}
        for s, c in need.items():
            pool = [kk for kk in keys if sp[kk] == s]
            for kk in rng.sample(pool, c):
                pick[kk] = 0.0
        nm = f"_pl_{name}_{j}"
        _UM[nm] = pick
        o = score(V_of({"um": nm}))
        del _UM[nm]
        v = V2.verdict(o, base)
        res.append({"both": v["both"], "pass": v["pass"], "H1": o["H1"][MONEY], "H2": o["H2"][MONEY]})
    out = {"name": name, "k": k, "skipped_per_span": dict(need), "share_both_2026": round(100.0 * np.mean([r["both"] for r in res]), 1),
           "share_v2_pass": round(100.0 * np.mean([r["pass"] for r in res]), 1),
           "mean_money": {s: round(float(np.mean([r[s] for r in res]))) for s in ("H1", "H2")}}
    print(json.dumps(out), flush=True)
    d = json.load(open(OUT))
    d.setdefault("placebo", {})[name] = out
    json.dump(d, open(OUT, "w"), separators=(",", ":"), default=str)
    return out


# ================================================================================================ the slot (money to the owner)
OUT_SLOT = os.path.join(ROOT, "research", "second", "atlas_deep_slot.json")
_X = {}


def xlibs():
    """tools/atx_edge's whole-slot simulator (eval -> funded -> MFFU payouts at 80% -> a new eval) at the owner's $43, with
    the eval's stuck line of the variant (atx_edge.Eval had $100 fixed) and this tool's sizer patch on top."""
    if "x" in _X:
        return _X["x"]
    from tools import atx_edge as X
    X.libs()
    _patch()
    X.PRICE = 43.0
    X.MIN_ROOM_EVAL = 100.0

    def step(self, L, day):
        M_ = self.M
        self.k += 1
        cum, recs, failed = M_.play_day(L, day, self.bal, self.floor, self.k, "atlas", False, 2, None, reserve=False)
        if failed:
            return "fail", recs
        self.bal += cum
        if self.bal <= self.floor:
            return "fail", recs
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - M_.MLL), M_.LOCK)
        if self.bal >= M_.TGT:
            return "pass", recs
        if self.bal - self.floor < X.MIN_ROOM_EVAL:
            return "stuck", recs
        return None, recs
    X.Eval.step = step
    _X["x"] = X
    return X


def slot_of(deep, n=300, seed=23, spans=None):
    X = xlibs()
    V = V_of(deep)
    X.MIN_ROOM_EVAL = float(V.get("min_room", 100.0))
    try:
        if spans:
            X.add_years()
            return X.slot(V, n=n, seed=seed, spans=spans)
        sl = X.slot(V, n=n, seed=seed)
    finally:
        X.MIN_ROOM_EVAL = 100.0
    sl["2021-25"] = X.slot_ref(sl)
    return sl


YEARS = ("2022", "2023", "2024", "2025")


def cmd_slot(names=None, n=300, seeds=(23,), years=False):
    R = variants()
    res = json.load(open(OUT_SLOT)) if os.path.exists(OUT_SLOT) else {}
    for fam, name, deep in R:
        if names and name not in names and name != "today":
            continue
        if years:
            k = f"{name}@years"
            if k not in res:
                res[k] = slot_of(deep, n=n, seed=23, spans=YEARS)
                print(name, "years", " | ".join(f"{s} ${res[k][s]['pm']:+,}/mo lose {res[k][s]['lose']}%" for s in YEARS), flush=True)
                json.dump(res, open(OUT_SLOT, "w"), indent=0, default=str)
            continue
        for sd in seeds:
            k = f"{name}@{sd}"
            if k in res:
                continue
            res[k] = slot_of(deep, n=n, seed=sd)
            print(name, sd, " | ".join(f"{s} ${res[k][s]['pm']:+,}/mo lose {res[k][s]['lose']}% funded {res[k][s]['funded_6m']} "
                                       f"evals {res[k][s]['evals_6m']} 1st pay {res[k][s]['first_pay_med']}"
                                       for s in ("H1", "H2", "2021-25")), flush=True)
            json.dump(res, open(OUT_SLOT, "w"), indent=0, default=str)
    return res


# ================================================================================================ store
SAVE = [
    ("atlas_deep_today", "today", "ATLAS today on the Builder 25K (account-B rules, fees at $43): the deep-edge baseline", "info"),
    ("atlas_deep_zombie", "last_bullet_0.8+stuck_under_200",
     "ATLAS zombie-eval rule: give an eval up under $200 of room + 1 micro 'last bullet' when need size says 0 (80% of the room)",
     "adopt-candidate"),
    ("atlas_deep_stuck200", "stuck_under_200", "ATLAS eval stuck line $200 (eval only, at the owner's $43 price)", "promising"),
    ("atlas_deep_last_bullet08", "last_bullet_0.8room", "ATLAS eval last bullet: 1 micro when its stop-out fits 80% of a low room",
     "promising"),
    ("atlas_deep_lit_won_other", "lit_won_other_x0", "ATLAS skipped when LIT already won the other side today", "rejected"),
    ("atlas_deep_same_side_lost_skip", "same_side_lost_skip", "ATLAS skipped when a same-side trade already lost today", "rejected"),
    ("atlas_deep_week_brake400", "week_brake_400", "ATLAS eval weekly brake at -$400", "rejected"),
    ("atlas_deep_against_trend_x0", "against_trend_x0", "ATLAS skipped against the daily trend (close vs SMA 20)", "rejected"),
]


def slot_mean(name):
    d = json.load(open(OUT_SLOT))
    L = [v for k, v in d.items() if k.rsplit("@", 1)[0] == name and not k.endswith("@years")]
    return {s: round(float(np.mean([v[s]["pm"] for v in L]))) for s in ("H1", "H2", "2021-25")}, len(L)


def cmd_save():
    from tools import runlib as rl
    R = {n: (f, dp) for f, n, dp in variants()}
    Q = ("Team E-ATLAS 2026-11-15: deeper edge for ATLAS on the MFFU Builder 25K: loser autopsy + new ideas; better in both "
         "2026 halves, 2021-25 not worse, 2+ trades a week, costs in; money = the whole 25K slot to the owner at $43")
    sess = [d for d in M.units()["sessions"] if d >= "2021-01-01"]
    _patch()
    for rid, name, title, status in SAVE:
        fam, deep = R[name]
        V = V_of(deep)
        V2.EV["min_room"] = float(V.get("min_room", 100.0))
        o, P = V2.score(V, keep_paths=True)
        sm, ns = slot_mean(name)
        T = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
              "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0, "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"],
              "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"], "mfe": None, "mae": None,
              "bars_held": None, "regime": "", "mult": None, "low": t["low"]} for s in SPANS for t in P[s]]
        f = lambda s: (f"2-week pass/fail/stuck {o[s]['p10']}/{o[s]['f10']}/{o[s]['s10']} (dec10 {o[s]['dec10']}), p15/f15 "
                       f"{o[s]['p15']}/{o[s]['f15']}, slow_pass {o[s]['slow_pass']}%, pass_med {o[s]['pass_med']}; eval-path $ less $43 "
                       f"fees ${o[s][MONEY]:+,}; one-start path {o[s]['net']:+,} (${o[s]['per_month']:,}/mo, PF {o[s]['pf']}, DD "
                       f"{o[s]['dd']:,}); {o[s]['tpw']} trades/wk on the path, {o[s]['wk2']}% weeks 2+")
        rl.save(rid, title, "risk", Q, params={"V": V}, sizing={"plan": "builder25k", "size": "need", "price": 43.0}, trades=T,
                scored=rl.score(T, sess), status=status,
                verdict=(f"Slot $ to the owner a month (300 paths x {ns} seeds, $43 evals): H1 ${sm['H1']}, H2 ${sm['H2']}, 2021-25 "
                         f"${sm['2021-25']}. H1 (pick) {f('H1')}. H2 (check) {f('H2')}. 2025 {f('2025')}. 2021-24 {f('2021-24')}."),
                notes="tools/atlas_deep.py (executor tools/atlas_v2.py + tools/atlas.py + tools/second_account_b.py; slot = "
                      "tools/atx_edge.slot); stored trades = the one-start back-to-back eval path of each span.",
                writeup="2026-11-15-atlas-deep", tags=["second", "account_b", "atlas", "atlas_deep"])
        V2.EV["min_room"] = 100.0
        print("saved", rid, flush=True)


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "autopsy"
    if a == "save":
        cmd_save()
        sys.exit(0)
    if a in ("slot", "years"):
        cmd_slot(sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] != "all" else None,
                 seeds=tuple(int(x) for x in sys.argv[3].split(",")) if len(sys.argv) > 3 else (23,), years=a == "years")
        sys.exit(0)
    if a == "autopsy":
        autopsy()
    elif a == "grid":
        cmd_grid()
    elif a == "placebo":
        for nm in sys.argv[2:]:
            cmd_placebo(nm)
