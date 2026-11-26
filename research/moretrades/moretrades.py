"""More trades: trade-frequency vs edge (research/moretrades/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/moretrades/moretrades.py lit     -> research/moretrades/lit.json
    python -X utf8 research/moretrades/moretrades.py atlas   -> research/moretrades/atlas.json
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

LIVE = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
YEARS = {str(y): (f"{y}-01-01", f"{y}-12-31") for y in range(2021, 2027)}
SPANS = {"2021-25": ("2021-01-01", "2025-12-31"), "H1 2026": ("2026-01-01", "2026-06-30"), "H2 2026": ("2026-07-01", "2026-10-16"),
         "fresh Oct19-Nov20": ("2026-10-17", "2026-11-20"), **YEARS}
ACCTS = {"50K": {"target": 3000, "mll": 2000, "lock": 100, "dll": 1000, "x": 1.0},
         "25K": {"target": 1500, "mll": 1000, "lock": 100, "dll": 600, "x": 0.5},
         "Rapid25K": {"target": 1500, "mll": 1000, "lock": 100, "dll": 500, "x": 0.5, "best": 0.30, "min_days": 4}}
SEC = {"after": None, "side": "any", "cool": 0, "r_stop": None, "r_take": None, "new_level": False, "q": None, "m": 1.0}

LITV = collections.OrderedDict([
    ("L0 live", {}),
    ("L1 depth 0.4", {"depth": 0.4}),
    ("L2 depth 0.3", {"depth": 0.3}),
    ("L3 no inducement", {"idm_a": None}),
    ("L4 disp 0.7", {"disp": 0.7}),
    ("L5 disp 0.6", {"disp": 0.6}),
    ("L6 limit 45 min", {"wait": 9}),
    ("L7 limit 60 min", {"wait": 12}),
    ("L8 1m CISD window 30", {"cisd1m": 30}),
    ("L9 no 1m CISD step", {"cisd1m": None}),
    ("L10 2 a day", {"max_per_day": 2}),
    ("L11 2nd only after a stop", {"max_per_day": 2, "second": {**SEC, "after": ["STOP"]}}),
    ("L12 2nd only opposite side", {"max_per_day": 2, "second": {**SEC, "side": "opp"}}),
    ("L13 Asia added (1 Asia + day)", "ASIA"),
    ("P1 depth 0.3 + no idm", {"depth": 0.3, "idm_a": None}),
    ("P2 disp 0.7 + depth 0.4", {"disp": 0.7, "depth": 0.4}),
    ("P3 disp 0.7 + no idm", {"disp": 0.7, "idm_a": None}),
    ("P4 no idm + 2 a day", {"idm_a": None, "max_per_day": 2}),
    ("P5 disp 0.7 + 2 a day", {"disp": 0.7, "max_per_day": 2}),
    ("P6 depth 0.3 + no idm + disp 0.7", {"depth": 0.3, "idm_a": None, "disp": 0.7}),
])


# ------------------------------------------------------------------------------------------------ generic scoring
def evals(p, lo, A, horizon=40):
    p, lo = np.asarray(p, float) * A["x"], np.asarray(lo, float) * A["x"]
    n = len(p)
    res, days_to = [], []
    for i in range(n):
        bal = peak = best = 0.0
        floor = -A["mll"]; days = 0; out = "OPEN"; k = i
        for k in range(i, min(n, i + horizon)):
            dp, dl = p[k], lo[k]
            if dl <= -A["dll"]:
                dp, dl = -A["dll"], -A["dll"]
            if bal + dl <= floor:
                out = "FAIL"; break
            bal += dp; days += dp != 0; best = max(best, dp); peak = max(peak, bal)
            floor = min(max(floor, peak - A["mll"]), A["lock"])
            if bal >= A["target"] and days >= A.get("min_days", 1) and (not A.get("best") or best <= A["best"] * bal):
                out = "PASS"; break
        if n - i >= horizon or out != "OPEN":
            res.append(out)
            if out == "PASS":
                days_to.append(k - i + 1)
    if not res:
        return {"pass": None, "fail": None, "med": None}
    return {"pass": round(100 * res.count("PASS") / len(res), 1), "fail": round(100 * res.count("FAIL") / len(res), 1),
            "med": float(np.median(days_to)) if days_to else None}


def daily(T):
    d, n = collections.defaultdict(lambda: [0.0, 0.0]), collections.Counter()
    for t in sorted(T, key=lambda t: t["entry_t"]):
        u = float(t.get("pnl", t.get("usd")) or 0)
        worst = float(t["low"]) if t.get("low") is not None else (-abs(float(t.get("risk_usd") or 0)) if t.get("exit_kind") == "STOP" else min(0.0, u))
        d[t["day"]][1] = min(d[t["day"]][1], d[t["day"]][0] + worst)
        d[t["day"]][0] += u
        n[t["day"]] += 1
    return d, n


def span_stats(T, sessions, a, z, with_evals=True):
    ds = [s for s in sessions if a <= s <= z]
    if not ds:
        return None
    dl, n = daily([t for t in T if a <= t["day"] <= z])
    p = np.array([dl[s][0] if s in dl else 0.0 for s in ds]); lo = np.array([min(dl[s][1], 0) if s in dl else 0.0 for s in ds])
    nt = sum(n[s] for s in ds)
    eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(p) else 0.0
    pn = np.array([float(t.get("pnl", t.get("usd")) or 0) for t in T if a <= t["day"] <= z])
    g, l = pn[pn > 0].sum(), -pn[pn < 0].sum()
    o = {"sess": len(ds), "trades": nt, "tpw": round(nt / (len(ds) / 5), 2), "pf": round(float(g / l), 2) if l else None,
         "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(ds) / 21)), "max_dd": round(dd),
         "zero_weeks": None}
    wk = collections.Counter()
    for s in ds:
        wk[dt.date.fromisoformat(s).isocalendar()[:2]] += n[s]
    o["zero_weeks"] = f"{sum(1 for v in wk.values() if v == 0)}/{len(wk)}"
    if with_evals:
        o["evals"] = {k: evals(p, lo, A) for k, A in ACCTS.items()}
    return o


def walk_forward(T, B, sessions):
    """6-month windows stepping 3 months; variant beats base on net $ AND on 50K 40-session pass %."""
    wins = tot = 0
    m = dt.date(2021, 11, 1)
    while True:
        z = (m.replace(day=1) + dt.timedelta(days=186)).replace(day=1) - dt.timedelta(days=1)
        if z > dt.date(2026, 10, 16):
            break
        a, zz = m.isoformat(), z.isoformat()
        sv, sb = span_stats(T, sessions, a, zz), span_stats(B, sessions, a, zz)
        tot += 1
        wins += sv["net"] > sb["net"] and (sv["evals"]["50K"]["pass"] or 0) >= (sb["evals"]["50K"]["pass"] or 0)
        m = (m.replace(day=28) + dt.timedelta(days=4 + 31 + 31)).replace(day=1)
        m = m.replace(day=1)
    return f"{wins}/{tot}"


# ------------------------------------------------------------------------------------------------ LIT
def lit_part():
    from engine import lit
    from tools import lit_final as F
    from tools import lit_adopt_combo as AC
    from tools import lit_big_ideas as BI
    from tools import lit_all_hours as LAH
    t0 = time.time()
    M, _ = F.market(LIVE["ref"], LIVE.get("extra_boxes") or [])
    last = sorted({d for d, _, _ in M.days})
    sessions = list(F.SESS) + [d for d in last if d > F.SESS[-1] and dt.date.fromisoformat(d).weekday() < 5]
    sessions = sorted(set(sessions))
    print("sessions", sessions[0], sessions[-1], len(sessions), flush=True)
    res = {"made": "2026-11-25", "sessions": [sessions[0], sessions[-1]], "variants": {}}
    base = None
    for nm, x in LITV.items():
        if x == "ASIA":
            Me, Ce = LAH.market()
            P = {**lit.DEFAULTS, **LIVE, "window": LAH.WIN["full"], "all_hours": True, **LAH.COUNT["asia_plus"]}
            T = lit.run_x(Me, Ce, P, sessions, B1=F.bars(Me, "1m"), B5=F.bars(Me, "5m"))
        else:
            P = {**lit.DEFAULTS, **LIVE, **x}
            Mx, Cx = F.market(P["ref"], P["extra_boxes"])
            T = lit.run_x(Mx, Cx, P, sessions, B1=F.bars(Mx, "1m") if P["tf"] == "1m" else None, B5=F.bars(Mx, "5m"))
        T = [t for t in T if t.get("qty")]
        if base is None:
            base = T
        o = {"cfg": x, "spans": {k: span_stats(T, sessions, a, z) for k, (a, z) in SPANS.items()}}
        try:
            E = BI.short(BI.score(AC.units([t for t in T if t["day"] <= "2026-10-16"])))
            o["eval_path"] = {s: {k: E[s][k] for k in ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "pass_med", "mc_p10", "mc_f10")} for s in E}
        except Exception as ex:  # noqa: BLE001
            o["eval_path"] = {"error": repr(ex)}
        o["walk_forward"] = walk_forward(T, base, sessions) if nm != "L0 live" else "-"
        res["variants"][nm] = o
        s, ep = o["spans"], o["eval_path"]
        print(f"[{time.time() - t0:5.0f}s] {nm:34s} " + " | ".join(
            f"{k}: {s[k]['tpw']}/wk PF {s[k]['pf']} ${s[k]['net']:,} 50K {s[k]['evals']['50K']['pass']}/{s[k]['evals']['50K']['fail']}"
            for k in ("2021-25", "H1 2026", "H2 2026", "fresh Oct19-Nov20") if s.get(k))
            + (f" | 2wk H1 {ep['H1']['p10']}/{ep['H1']['f10']} med {ep['H1']['pass_med']} H2 {ep['H2']['p10']}/{ep['H2']['f10']} med {ep['H2']['pass_med']}" if "H1" in ep else f" {ep}")
            + f" | WF {o['walk_forward']}", flush=True)
        json.dump(res, open(os.path.join(HERE, "lit.json"), "w"), indent=1, default=float)
    return res


# ------------------------------------------------------------------------------------------------ ATLAS
ATV = collections.OrderedDict([
    ("A0 today", None),
    ("A1 EMA no swing sweep", ("ema_lon_vix", lambda s: s["entry"].__setitem__("sweep", 0))),
    ("A2 EMA pullback to any EMA", ("ema_lon_vix", lambda s: s["entry"].__setitem__("pull", "any"))),
    ("A3 MACD depth 0.3", ("macd_sweep", lambda s: s["flt"].__setitem__("depth", 0.3))),
    ("A4 MACD histogram divergence", ("macd_sweep", lambda s: s["gen"].__setitem__("osc", "hist"))),
    ("A5 MACD 2 a day", ("macd_sweep", lambda s: s["flt"].__setitem__("maxpd", 2))),
    ("A6 S/R 2 a day", ("sr_nyreclaim", lambda s: s["key"].__setitem__("maxpd", 2))),
    ("A7 S/R no inducement", ("sr_nyreclaim", lambda s: s["key"].__setitem__("idm", False))),
])
KEYS = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")


def one_position(T):
    out, busy = [], 0
    for t in sorted(T, key=lambda t: t["entry_t"]):
        if t["entry_t"] >= busy:
            out.append(t); busy = t["exit_t"]
    return out


def atlas_part(only=None):
    import pandas as pd
    from engine import second
    base = second.load_cfg()
    d5 = pd.read_csv("data/NQ_5m.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d1 = pd.read_csv("data/NQ_1m.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
    ET = dt.timezone(dt.timedelta(hours=-5))
    months = []
    m = dt.date(2021, 11, 1)
    while m <= dt.date(2026, 11, 1):
        months.append(m)
        m = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    sessions = json.load(open(os.path.join(HERE, "lit.json")))["sessions"] if os.path.exists(os.path.join(HERE, "lit.json")) else None
    from tools import lit_final as F
    sess = list(F.SESS)
    t0 = time.time()
    out_p = os.path.join(HERE, f"atlas{'_' + only if only else ''}.json")
    res = {"made": "2026-11-25", "variants": {}}
    trades = {}
    names = [n for n in ATV if not only or n.startswith(only) or n == "A0 today"]
    for nm in names:
        c = copy.deepcopy(base)
        c["strategies"] = {k: c["strategies"][k] for k in KEYS}
        if ATV[nm]:
            k, f = ATV[nm]
            f(c["strategies"][k])
        T = collections.defaultdict(dict)
        for mo in months:
            nxt = (mo.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
            end = int(dt.datetime(nxt.year, nxt.month, 1, 17, 0, tzinfo=ET).timestamp()) - 86400
            end = min(end, int(d5.time.max()) + 300)
            x5 = d5[(d5.time < end) & (d5.time >= end - 86400 * 110)].reset_index(drop=True)
            x1 = d1[(d1.time < end) & (d1.time >= end - 86400 * 70)].reset_index(drop=True) if mo >= dt.date(2026, 1, 1) else None
            if len(x5) < 1000:
                continue
            try:
                r = second.run(x5, one_min=x1 if x1 is not None and len(x1) else None, now=end, cfg=c, lit=[])
            except Exception as ex:  # noqa: BLE001
                print(f"  {nm} {mo} error {ex}", flush=True)
                continue
            for k in KEYS:
                for t in r["strategies"][k]["trades"]:
                    if t.get("exit_kind") and t["day"][:7] == mo.isoformat()[:7]:
                        T[k][t["entry_t"]] = t
        trades[nm] = T
        allS = sorted(set(sess) | {t["day"] for k in KEYS for t in T[k].values()})
        allS = [s for s in allS if dt.date.fromisoformat(s).weekday() < 5]
        o = {"members": {}, "book": None}
        for k in KEYS:
            o["members"][k] = {s: span_stats(list(T[k].values()), allS, a, z, with_evals=False) for s, (a, z) in SPANS.items()}
        book = one_position([t for k in KEYS for t in T[k].values()])
        o["book"] = {s: span_stats(book, allS, a, z) for s, (a, z) in SPANS.items()}
        if nm != "A0 today":
            b0 = one_position([t for k in KEYS for t in trades["A0 today"][k].values()])
            o["walk_forward"] = walk_forward(book, b0, allS)
        res["variants"][nm] = o
        b = o["book"]
        print(f"[{time.time() - t0:5.0f}s] {nm:30s} book " + " | ".join(
            f"{s}: {b[s]['tpw']}/wk PF {b[s]['pf']} ${b[s]['net']:,} 25K {b[s]['evals']['25K']['pass']}/{b[s]['evals']['25K']['fail']} med {b[s]['evals']['25K']['med']}"
            for s in ("2021-25", "H1 2026", "H2 2026", "fresh Oct19-Nov20") if b.get(s)) + f" WF {o.get('walk_forward', '-')}", flush=True)
        json.dump(res, open(out_p, "w"), indent=1, default=float)
    return res


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "lit"
    if what == "lit":
        lit_part()
    else:
        atlas_part(sys.argv[2] if len(sys.argv) > 2 else None)
