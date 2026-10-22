"""More LIT entries (owner 2026-10-22: "There are LIT entries all the time, there isn't a specific window. Look deeper. I need this
better. Make it work no matter what.") Goal: >= 3 LIT trades a week (ideally 3-5) that ADD money in both 2026 halves without
more MFFU eval fails.

Everything runs on the exact live LIT (live_model.json "lit": t_check, be_off, Monday rule, weekly stop; 1m CISD entries on
2026), through engine/lit.py run_x with the evening candidates (candidates(evening=True), tools/lit_all_hours.py market()).
New engine options (default off, engine/lit.py DEFAULTS): "second" (rules for the 2nd+ trade of a day: after which exit,
same / opposite side, cool-down, day R caps, a new level, a stricter setup, a size multiplier) and "sess_m" (size by session).
Old options reused: window, all_hours, max_per_day, per_session, stop_after_loss, kz.

Two views, costs in (as tools/lit_adopt_combo.py):
  LIT size rule  the engine's own trades ($800 up to a 20-pt stop, weekly stop) = how run lit_live is scored ($1.40 + slip)
  eval path      the live two_week sizing (engine/sizing.lit_qty: two_week 10 sessions then safe_eval, no reset, $1.90 a micro,
                 the 60% room and $1,000 soft daily loss caps on today's closed P&L, so a 2nd trade is sized on what the day
                 already made / lost; no new trade once the day reached the target), fresh evals on every session + Monte Carlo;
                 the "x_m" size multiplier is applied after the caps (int(q x m), min 1)
Pick on 2026 H1 (Jan-Jun), check on H2 (Jul 1 - Oct 16); 2021-25 = reference line (5m only).

    python -X utf8 tools/lit_more_entries.py check   # base == run lit_live and lit_adopt_t15_be_off_eval
    python -X utf8 tools/lit_more_entries.py grid    # every variant -> research/lit/more_entries.json
    python -X utf8 tools/lit_more_entries.py chance  # placebo: random 2nd trades vs the survivors
    python -X utf8 tools/lit_more_entries.py save    # rl.save runs lit_more_*
Paper only.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_all_hours as AH  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "more_entries.json")
LIVE = dict(AH.LIVE)                      # live_model.json lit (t_check + be_off + loss pack) over lit.DEFAULTS
ET = ZoneInfo("America/New_York")
SPANS = ("H1", "H2")

WIN = {
    "live": [[120, 930]],                 # 02:00-15:30 (today)
    "late": [[120, 950]],                 # 02:00-15:50
    "w00": [[0, 930]],                    # 00:00-15:30
    "w20": [[1200, 1440], [0, 930]],      # 20:00-15:30
    "full": [[1080, 1440], [0, 930]],     # 18:00-15:30 (Asia added)
    "24h": [[1080, 1440], [0, 950]],      # 18:00-15:50: every minute a setup can still be traded before the 15:55 flat
    "asia": [[1080, 1440], [0, 120]],     # 18:00-02:00 only
    "lon": [[120, 480]], "nyam": [[480, 720]], "nypm": [[720, 930]],
}
SESS4 = (("Asia", 1080, 120), ("London", 120, 480), ("NY AM", 480, 720), ("NY PM", 720, 1080))

STOPX = ["STOP"]
LOSSX = ["STOP", "CUT_T15"]
COND = {                                   # rules for the 2nd+ trade (engine "second"); max_per_day set separately
    "any": {},
    "after_win": {"after": ["TARGET"]},
    "after_loss": {"after": LOSSX},
    "after_stop": {"after": STOPX},
    "after_be": {"after": ["BE"]},
    "after_scratch": {"after": ["BE", "CUT_T15", "EOD"]},
    "after_nonstop": {"after": ["TARGET", "BE", "CUT_T15", "EOD"]},
    "same": {"side": "same"},
    "opp": {"side": "opp"},
    "flip_stop": {"after": LOSSX, "side": "opp"},
    "reenter_stop": {"after": LOSSX, "side": "same"},
    "cont_win": {"after": ["TARGET"], "side": "same"},
    "cool30": {"cool": 30}, "cool60": {"cool": 60}, "cool120": {"cool": 120},
    "rstop_m05": {"r_stop": -0.5}, "rstop_0": {"r_stop": 0.0}, "rtake_1": {"r_take": 1.0},
    "rstop_m05_rtake_1": {"r_stop": -0.5, "r_take": 1.0},
    "new_level": {"new_level": True},
    "q_disp12": {"q": {"disp": 1.2}}, "q_depth1": {"q": {"depth": 1.0}}, "q_idm2": {"q": {"idm": 2}},
}


def P_of(win="live", n=1, cond=None, m=1.0, extra=None):
    P = {**LIVE, "window": WIN[win], "max_per_day": n}
    if any(a >= 1080 for a, b in WIN[win]):
        P["all_hours"] = True
    if n > 1:
        P["second"] = {**(COND[cond] if cond else {}), "m": m}
    P.update(extra or {})
    return P


# ------------------------------------------------------------------------------------------------ run + score
def run(P):
    return AH.run(P)


def et_mod(ts):
    x = dt.datetime.fromtimestamp(int(ts), ET)
    return x.hour * 60 + x.minute


def sess_of(mod):
    for nm, a, b in SESS4:
        if (mod - a) % 1440 < (b - a) % 1440:
            return nm
    return "?"


def units(T):
    """Eval-path units (tools/lit_adopt_combo.units) + the size multiplier x_m as "m" (tools/lit_big_ideas.run_eval_x)."""
    from tools import lit_adopt_combo as AC
    T26 = [t for t in T if t["day"] >= "2026-01-01"]
    U = AC.units(T26)
    assert len(U) == len(T26)
    for u, t in zip(U, T26):
        if t.get("x_m") is not None:
            u["m"] = float(t["x_m"])
    return U


def sess_days(span):
    a, z = F.SPAN[span]
    return [d for d in F.SESS if a <= d <= z]


def wk3(T, span):
    ss = sess_days(span)
    allwk = {lit.iso_week(d) for d in ss}
    c = collections.Counter(lit.iso_week(t["day"]) for t in T if ss[0] <= t["day"] <= ss[-1])
    return round(100.0 * sum(c[w] >= 3 for w in allwk) / max(1, len(allwk)))


_BASE = {}


def base_keys():
    if "k" not in _BASE:
        _BASE["k"] = {(t["day"], int(t["entry_t"])) for t in run(LIVE)}
    return _BASE["k"]


def score(T):
    from tools import lit_big_ideas as BI
    o = F.score(T)
    lit_r = {s: {k: o[s].get(k) for k in ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd")} for s in ("H1", "H2", "2021-25")}
    for s in ("H1", "H2", "2021-25"):
        lit_r[s]["wk3"] = wk3(T, s)
    e = BI.short(BI.score(units(T)))
    bk = base_keys()
    ses, extra = {}, {}
    for s in SPANS:
        a, z = F.SPAN[s]
        TT = [t for t in T if a <= t["day"] <= z]
        d = collections.defaultdict(lambda: [0, 0.0])
        for t in TT:
            q = d[sess_of(et_mod(t["entry_t"]))]
            q[0] += 1; q[1] += t["pnl"]
        ses[s] = {k: [v[0], round(v[1])] for k, v in d.items()}
        X = [t for t in TT if (t["day"], int(t["entry_t"])) not in bk]
        nd = collections.Counter(t["day"] for t in TT)
        extra[s] = {"n_new": len(X), "new_net": round(sum(t["pnl"] for t in X)), "days2": sum(1 for v in nd.values() if v >= 2)}
    return {"lit": lit_r, "eval": e, "sess": ses, "extra": extra}


def line(nm, o):
    def f(s):
        L, E = o["lit"][s], o["eval"][s]
        return (f"{L['tpw']}/wk wk3 {L['wk3']}% PF {L['pf']} {L['net']:+,} | ev {E['net']:+,} 2w {E['p10']}/{E['f10']} "
                f"1m {E['p20']}/{E['f20']} mc {E['mc_p10']}/{E['mc_f10']}")
    return f"{nm[:40]:40s} H1[{f('H1')}] H2[{f('H2')}] ref {o['lit']['2021-25']['net']:+,}"


def gates(o, b, span, slack=0.0):
    """Adopt gates on one half vs the base: more $ on both views, eval fails (2-week and 1-month) not above base (+slack pts),
    >= 3 trades a week."""
    L, E, LB, EB = o["lit"][span], o["eval"][span], b["lit"][span], b["eval"][span]
    return (L["net"] > LB["net"] and E["net"] > EB["net"] and E["f10"] <= EB["f10"] + slack and E["f20"] <= EB["f20"] + slack
            and L["tpw"] >= 3.0)


# ------------------------------------------------------------------------------------------------ variants
def variants():
    V = collections.OrderedDict()
    V["base"] = P_of()
    # 1. windows, 1 trade a day
    for w in ("late", "w00", "w20", "full", "24h", "asia", "lon", "nyam", "nypm"):
        V[f"win_{w}"] = P_of(w)
    for w, mm in (("full", 0.5), ("full", 0.25), ("24h", 0.5), ("w20", 0.5)):
        V[f"win_{w}_asia_x{mm}"] = P_of(w, extra={"sess_m": [[1080, 120, mm]]})
    # 2. more than 1 trade a day: max 2 / 3 with the 2nd-trade rules at full / half / quarter size
    for w in ("live", "late", "full", "24h"):
        for n in (2, 3):
            for c in COND:
                if n == 3 and c not in ("any", "after_win", "after_loss", "after_nonstop", "rstop_m05", "new_level", "cool60",
                                        "after_scratch"):
                    continue
                if w in ("late", "24h") and c not in ("any", "after_win", "after_loss", "after_nonstop", "after_scratch", "new_level",
                                                      "rstop_m05", "opp", "same", "cool60"):
                    continue
                for mm in (1.0, 0.5, 0.25):
                    V[f"{w}_n{n}_{c}_x{mm}"] = P_of(w, n, c, mm)
    # 2b. Asia at half size + 2 a day
    for c in ("any", "after_win", "after_nonstop", "after_scratch", "new_level", "rstop_m05"):
        for mm in (1.0, 0.5):
            V[f"full_n2_{c}_x{mm}_asia_x0.5"] = P_of("full", 2, c, mm, {"sess_m": [[1080, 120, 0.5]]})
    # 2c. one per session (Asia / London / NY), the older per_session option, with sizes
    S3 = [[1080, 120], [120, 480], [480, 1080]]
    for w in ("live", "full"):
        for mm in (1.0, 0.5, 0.25):
            V[f"{w}_1sess_x{mm}"] = P_of(w, 3, "any", mm, {"per_session": [S3, 1]})
    # 2d. stop for the day after a loss (old option) + sizes
    for w in ("live", "full"):
        for mm in (1.0, 0.5):
            V[f"{w}_n2_sal_x{mm}"] = P_of(w, 2, "any", mm, {"stop_after_loss": True})
    # 5. looser / stricter thresholds outside the main window (killzone overrides kz)
    asia = lambda ov: [[1080, 1440, ov], [0, 120, ov]]  # noqa: E731
    for nm, ov in (("disp1.0", {"disp": 1.0}), ("disp1.2", {"disp": 1.2}), ("depth0.75", {"depth": 0.75}), ("depth1.0", {"depth": 1.0}),
                   ("idm2", {"idm_a": [1.0, 36, 2]}), ("rr2", {"min_rr": 2.0}), ("stop40", {"max_stop": 40.0})):
        V[f"full_kz_asia_{nm}"] = P_of("full", extra={"kz": asia(ov)})
        V[f"full_n2_any_x0.5_kz_asia_{nm}"] = P_of("full", 2, "any", 0.5, {"kz": asia(ov)})
    for nm, ov in (("disp0.6", {"disp": 0.6}), ("depth0.3", {"depth": 0.3}), ("noidm", {"idm_a": None}),
                   ("wait12", {"wait": 12}), ("cisd30", {"cisd1m": 30})):
        # looser setups only in the hours outside 02:00-12:00 (NY PM + Asia), main window unchanged
        V[f"24h_kz_out_{nm}"] = P_of("24h", extra={"kz": [[720, 955, ov], [1080, 1440, ov], [0, 120, ov]]})
        V[f"live_n2_any_x0.5_kz_pm_{nm}"] = P_of("live", 2, "any", 0.5, {"kz": [[720, 955, ov]]})
        V[f"live_kz_all_{nm}"] = P_of("live", extra={"kz": [[0, 1440, ov]]})
    # 5b. Asia with its own management (a nearer bank / later breakeven): the Asia losers in H1 are BE + cut trades that
    # never reach the far VIX band
    for nm, ov in (("rr2", {"max_rr": 2.0}), ("rr3", {"max_rr": 3.0}), ("rr4", {"max_rr": 4.0}), ("be15", {"be_r": 1.5}),
                   ("rr3_be15", {"max_rr": 3.0, "be_r": 1.5}), ("vix05", {"vix_k": 0.5}), ("vix05_rr4", {"vix_k": 0.5, "max_rr": 4.0})):
        V[f"full_kz_asia_mg_{nm}"] = P_of("full", extra={"kz": asia(ov)})
        V[f"full_n2_any_x1.0_kz_asia_mg_{nm}"] = P_of("full", 2, "any", 1.0, {"kz": asia(ov)})
        V[f"asia_kz_mg_{nm}"] = P_of("asia", extra={"kz": asia(ov)})
    # 5c. one more London / NY-AM split: 1 trade 02:00-08:00 + 1 trade 08:00-15:30 (per_session), sizes
    for mm in (1.0, 0.5, 0.25):
        V[f"live_lon_ny_x{mm}"] = P_of("live", 2, "any", mm, {"per_session": [[[120, 480], [480, 1080]], 1]})
        V[f"live_lon_ny_cool120_x{mm}"] = P_of("live", 2, "cool120", mm, {"per_session": [[[120, 480], [480, 1080]], 1]})
    # 5c2. London + NY split: neighbours of the cool-down, a 2nd-trade rule on top, and the split points
    LN = lambda cut: {"per_session": [[[120, cut], [cut, 1080]], 1]}  # noqa: E731
    for cool in (0, 30, 60, 90, 120, 150, 180, 240):
        for mm in (1.0, 0.5):
            V[f"lonny_c{cool}_x{mm}"] = P_of("live", 2, None, mm, {**LN(480), "second": {"cool": cool, "m": mm}})
    for cut in (420, 450, 510, 540, 570):
        V[f"lonny_cut{cut}_c120_x1.0"] = P_of("live", 2, None, 1.0, {**LN(cut), "second": {"cool": 120}})
    for c in ("after_nonstop", "after_loss", "after_scratch", "same", "opp", "new_level", "rstop_m05"):
        V[f"lonny_c120_{c}_x1.0"] = P_of("live", 2, None, 1.0, {**LN(480), "second": {**COND[c], "cool": 120}})
    # 5c3. Asia as its own slot (never takes the day's 02:00-15:30 trade), its own bank, sizes; + the London / NY split
    S2 = [[[1080, 120], [120, 1080]], 1]
    S3 = [[[1080, 120], [120, 480], [480, 1080]], 1]
    for rr in (None, 3.0, 4.0):
        kz = {"kz": asia({"max_rr": rr})} if rr else {}
        for am in (1.0, 0.5, 0.25):
            sm = {"sess_m": [[1080, 120, am]]} if am != 1.0 else {}
            tag = f"rr{rr:g}" if rr else "rr8"
            V[f"asiaslot_{tag}_x{am}"] = P_of("full", 2, None, 1.0, {"per_session": S2, "second": {}, **kz, **sm})
            V[f"asiaslot_{tag}_x{am}_lonny_c120"] = P_of("full", 3, None, 1.0, {"per_session": S3, "second": {"cool": 120}, **kz, **sm})
    # 5c4. neighbours of the Asia slot with a 3R bank: the bank, the size, where Asia starts, Asia's t_check
    for rr in (2.5, 2.75, 3.0, 3.25, 3.5):
        for am in (1.0, 0.75):
            sm = {"sess_m": [[1080, 120, am]]} if am != 1.0 else {}
            V[f"asiaslotn_rr{rr:g}_x{am}"] = P_of("full", 2, None, 1.0, {"per_session": S2, "second": {}, "kz": asia({"max_rr": rr}), **sm})
    for nm, win, kz in (("w20", "w20", [[1200, 1440, {"max_rr": 3.0}], [0, 120, {"max_rr": 3.0}]]),
                        ("w00", "w00", [[0, 120, {"max_rr": 3.0}]]),
                        ("w19", None, [[1140, 1440, {"max_rr": 3.0}], [0, 120, {"max_rr": 3.0}]])):
        P = P_of(win or "full", 2, None, 1.0, {"per_session": S2, "second": {}, "kz": kz})
        if win is None:
            P["window"] = [[1140, 1440], [0, 930]]
        V[f"asiaslotn_rr3_{nm}"] = P
    for nm, ov in (("be15", {"be_r": 1.5}), ("minrr2", {"min_rr": 2.0}), ("depth075", {"depth": 0.75}), ("disp1", {"disp": 1.0})):
        V[f"asiaslotn_rr3_{nm}"] = P_of("full", 2, None, 1.0, {"per_session": S2, "second": {}, "kz": asia({"max_rr": 3.0, **ov})})
    # 5d. cool-down neighbours (plateau check of the eval-path lead)
    for cool in (45, 90, 150, 180, 240):
        for mm in (1.0, 0.5, 0.25):
            V[f"live_n2_cool{cool}_x{mm}"] = P_of("live", 2, None, mm, {"second": {"cool": cool, "m": mm}})
            V[f"full_n2_cool{cool}_x{mm}"] = P_of("full", 2, None, mm, {"second": {"cool": cool, "m": mm}})
    return V


# ------------------------------------------------------------------------------------------------ 15m LIT chain (night + day)
def m15_trades(P15, evening=False):
    """LIT on 15m candles (tools/lit_more.py m15: detector windows scaled to the same clock time), executed on the NQ 1m / 5m
    bars, with the live management (t_check, be_off). evening=True: the 15m detector on the whole trading day."""
    import pickle
    from tools import lit_more as LM_
    M15, C15, B1, B5 = LM_.m15()
    if evening:
        p = os.path.join(F.CACHE, f"litmoreent_m15ev_{__import__('tools.runlib', fromlist=['x'])._data_key().replace(':', '_')}.pkl")
        if os.path.exists(p):
            C15 = pickle.load(open(p, "rb"))
        else:
            C15 = lit.candidates(M15, leg=8, sweep_win=8, ref_back=12, ind_back=12, ref="cisd", evening=True)
            pickle.dump(C15, open(p, "wb"))
    return lit.run_x(M15, C15, {**LIVE, **P15}, F.SESS, B1=B1, B5=B5)


def merge(T5, T15, max_day=1, m15=1.0):
    """5m + 15m trades in one account path: entry order, max_day a day, one trade at a time; 15m trades x m15 size."""
    allt = sorted([(t, 0) for t in T5] + [(t, 1) for t in T15], key=lambda x: (x[0]["entry_t"], x[1]))
    out, nday, busy = [], collections.Counter(), -1
    for t, src in allt:
        if nday[t["day"]] >= max_day or t["entry_t"] < busy:
            continue
        if src == 1 and m15 != 1.0:
            t = {**lit.scale_trade(t, m15), "x_m": m15}
        out.append(t)
        nday[t["day"]] += 1
        busy = t["exit_t"]
    return out


def fam_15m():
    res = json.load(open(OUT))
    T5 = run(LIVE)
    T5f = run(P_of("full"))
    for nm, P15, ev in (("15m_live", {"idm_a": [1.0, 12, 1]}, False),
                        ("15m_night", {"idm_a": [1.0, 12, 1], "window": WIN["asia"], "all_hours": True}, True),
                        ("15m_24h", {"idm_a": [1.0, 12, 1], "window": WIN["24h"], "all_hours": True}, True),
                        ("15m_24h_loose", {"idm_a": [1.0, 24, 1], "depth": 0.4, "disp": 0.7, "window": WIN["24h"], "all_hours": True}, True)):
        T15 = m15_trades(P15, ev)
        for lab, TT in ((f"{nm}_alone", T15), (f"5m+{nm}_1day", merge(T5, T15, 1)), (f"5m+{nm}_2day", merge(T5, T15, 2)),
                        (f"5m+{nm}_2day_x0.5", merge(T5, T15, 2, 0.5)), (f"5mfull+{nm}_2day_x0.5", merge(T5f, T15, 2, 0.5))):
            o = score(sorted(TT, key=lambda t: t["entry_t"]))
            o["params"] = {"m15": P15, "evening": ev}
            res[lab] = o
            print(line(lab, o), flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=float)


def grid(only=None):
    V = variants()
    res = json.load(open(OUT)) if (only and os.path.exists(OUT)) else {}
    for nm, P in V.items():
        if only and not any(nm.startswith(x) for x in only):
            continue
        T = run(P)
        o = score(T)
        o["params"] = {k: P[k] for k in ("window", "max_per_day", "second", "sess_m", "per_session", "stop_after_loss", "kz", "all_hours")
                       if P.get(k) not in (None, False)}
        res[nm] = o
        print(line(nm, o), flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    summary(res)
    return res


def summary(res):
    b = res["base"]
    names = [k for k in res if k not in ("base", "_chance")]
    h1 = [k for k in names if gates(res[k], b, "H1")]
    both = [k for k in h1 if gates(res[k], b, "H2")]
    soft = [k for k in names if gates(res[k], b, "H1", 1.0) and gates(res[k], b, "H2", 1.0)]
    money = [k for k in names if all(res[k]["lit"][s]["net"] > b["lit"][s]["net"] and res[k]["eval"][s]["net"] > b["eval"][s]["net"]
                                     for s in SPANS)]
    print(f"\n{len(names)} variants | H1 gates {len(h1)} | H1+H2 gates {len(both)} | soft (+1 pt fails) {len(soft)} | "
          f"$ up both halves both views {len(money)}")
    for k in both:
        print("  BOTH", line(k, res[k]))
    for k in soft:
        if k not in both:
            print("  SOFT", line(k, res[k]))
    return {"n": len(names), "h1": h1, "both": both, "soft": soft, "money": money}


# ------------------------------------------------------------------------------------------------ re-arm diagnostics
def rearm_diag():
    """Does one armed setup block the day? Logs every setup the executor tried (simulate_x) on the live rules."""
    log = []
    orig = lit.simulate_x

    def hook(M, B, z, *a, **k):
        t = orig(M, B, z, *a, **k)
        log.append((z["day"], int(z["entry_t"]), t is not None))
        return t
    lit.simulate_x = hook
    try:
        T = run(LIVE)
    finally:
        lit.simulate_x = orig
    o = {}
    for s in SPANS:
        a, z = F.SPAN[s]
        L = [x for x in log if a <= x[0] <= z]
        days = collections.defaultdict(list)
        for d, t, f in L:
            days[d].append(f)
        tr = {t["day"] for t in T if a <= t["day"] <= z}
        nofill_days = [d for d, v in days.items() if not v[0]]
        o[s] = {"armed_setups": len(L), "filled": sum(1 for x in L if x[2]), "days_armed": len(days), "days_traded": len(tr),
                "days_first_unfilled": len(nofill_days), "of_which_traded_later": sum(1 for d in nofill_days if any(days[d])),
                "setups_after_the_trade": sum(max(0, len(v) - 1 - v.index(True)) for v in days.values() if True in v)}
    print(json.dumps(o, indent=1))
    return o


# ------------------------------------------------------------------------------------------------ chance
def placebo(pool_var, keep, n_draw=200, seed=11):
    """Chance check. pool_var = a variant whose extra trades (setups not in the base) form the pool; each draw keeps `keep`
    of them at random (keep < 1: that share) and skips the rest (skip_keys: the day stays free for a later setup, so this is
    a random 2nd-trade rule of the same size) and is scored like every variant. Returns how many draws pass the money gates
    (LIT rule and eval path $ up in both halves, eval 2-week and 1-month fails not above the base) and the spread."""
    res = json.load(open(OUT))
    b = res["base"]
    P0 = variants()[pool_var]
    T0 = run(P0)
    bk = base_keys()
    sec = [(t["day"], int(t["i"]), int(t["dir"])) for t in T0 if t["day"] >= "2026" and (t["day"], int(t["entry_t"])) not in bk]
    k = int(round(keep * len(sec))) if keep < 1 else int(keep)
    rng = np.random.default_rng(seed)
    n_ok, d_lit, d_ev = 0, [], []
    for _ in range(n_draw):
        skip = [sec[j] for j in rng.permutation(len(sec))[k:]]
        o = score(run({**P0, "skip_keys": skip}))
        ok = all(o["lit"][s]["net"] > b["lit"][s]["net"] and o["eval"][s]["net"] > b["eval"][s]["net"]
                 and o["eval"][s]["f10"] <= b["eval"][s]["f10"] and o["eval"][s]["f20"] <= b["eval"][s]["f20"] for s in SPANS)
        n_ok += ok
        d_lit.append([o["lit"][s]["net"] - b["lit"][s]["net"] for s in SPANS])
        d_ev.append([o["eval"][s]["net"] - b["eval"][s]["net"] for s in SPANS])
    d_lit, d_ev = np.array(d_lit), np.array(d_ev)
    q = lambda a, p: [int(np.percentile(a[:, j], p)) for j in range(2)]  # noqa: E731
    out = {"pool": pool_var, "pool_trades": len(sec), "keep": k, "draws": n_draw, "pass_money_gates": n_ok,
           "lit_delta_p10_p50_p90": [q(d_lit, 10), q(d_lit, 50), q(d_lit, 90)],
           "eval_delta_p10_p50_p90": [q(d_ev, 10), q(d_ev, 50), q(d_ev, 90)],
           "lit_up_both": int(((d_lit[:, 0] > 0) & (d_lit[:, 1] > 0)).sum())}
    print(json.dumps(out), flush=True)
    res.setdefault("_chance", {})[f"{pool_var}|{keep}"] = out
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    return out


# ------------------------------------------------------------------------------------------------ store runs
SAVE = [  # run id suffix, variant, title, status
    ("asia_slot_rr3", "asiaslotn_rr3_x1.0", "Asia as its own slot (18:00-02:00, bank 3R) + the live day trade", "promising"),
    ("asia_slot_rr3_depth075", "asiaslotn_rr3_depth075", "Asia slot, bank 3R, Asia sweep depth >= 0.75 ATR (H1 pick)", "rejected"),
    ("asia_slot_rr275", "asiaslotn_rr2.75_x1.0", "Asia slot, bank 2.75R", "rejected"),
    ("asia_slot_rr3_w20", "asiaslotn_rr3_w20", "Asia slot from 20:00, bank 3R", "rejected"),
    ("asia_slot_rr8", "asiaslot_rr8_x1.0", "Asia slot with the live 8R bank", "rejected"),
    ("lonny_c120", "lonny_c120_x1.0", "1 London + 1 NY trade, the NY one >= 120 min after the first exit", "promising"),
    ("win_full", "win_full", "Window 18:00-15:30, 1 trade a day", "rejected"),
    ("win_24h", "win_24h", "Window 18:00-15:50, 1 trade a day", "rejected"),
    ("n2_any", "live_n2_any_x1.0", "2 trades a day (02:00-15:30), any 2nd trade", "rejected"),
    ("n2_any_half", "live_n2_any_x0.5", "2 trades a day, 2nd trade at half size", "rejected"),
    ("n2_cool120", "live_n2_cool120_x1.0", "2 trades a day, 2nd >= 120 min after the first exit", "rejected"),
    ("n2_flip_stop", "live_n2_flip_stop_x1.0", "2 trades a day, 2nd only opposite side after a loss", "rejected"),
    ("full_n2_any_half", "full_n2_any_x0.5", "18:00-15:30, 2 a day, 2nd at half size", "rejected"),
    ("full_asia_half", "win_full_asia_x0.5", "18:00-15:30, 1 a day, Asia at half size", "rejected"),
    ("kz_out_disp06", "24h_kz_out_disp0.6", "18:00-15:50, displacement 0.6 ATR outside 02:00-12:00", "rejected"),
]
Q = ("Owner 2026-10-22: LIT entries happen all the time, not in one window - more LIT trades (>= 3 a week) that add money in both "
     "2026 halves without more MFFU eval fails?")


def save():
    from tools import lit_adv_manage as A
    from tools import runlib as rl
    res = json.load(open(OUT))
    b = res["base"]
    V = variants()

    def h(o, s):
        L, E = o["lit"][s], o["eval"][s]
        return (f"{L['tpw']}/wk (3+ in {L['wk3']}% of weeks) win {L['win']}% PF {L['pf']} net {L['net']:+,} (${L['per_month']:,}/mo) "
                f"DD {L['dd']:,}; eval path net {E['net']:+,}, 2-week pass/fail {E['p10']}/{E['f10']}, 1 month {E['p20']}/{E['f20']}")
    for sid, vn, title, status in SAVE:
        o = res[vn]
        P = V[vn]
        T = run(P)
        T = [{k: v for k, v in t.items() if not k.startswith("_") and k not in ("size_why",)} for t in T]
        ver = (f"LIT size rule + eval path (two_week). H1 (pick) {h(o, 'H1')}. H2 (check) {h(o, 'H2')}. Base (lit_live) H1 {h(b, 'H1')}; "
               f"H2 {h(b, 'H2')}. 2021-25 reference (5m) {o['lit']['2021-25']['net']:+,} vs {b['lit']['2021-25']['net']:+,}.")
        rl.save("lit_more_ent_" + sid, "LIT more entries: " + title, "sessions", Q, params={k: P[k] for k in P}, trades=T,
                scored=rl.score(T, F.SESS), status=status, verdict=ver,
                notes="tools/lit_more_entries.py (variant " + vn + "): engine/lit.py run_x, live_model.json lit + options",
                writeup="lit-more-entries", tags=["lit", "lit_more_entries"])
        if status == "promising":
            U = units(T)
            Tp = []
            for sp in ("H1", "H2"):
                Tp += A.b2b(U, sp)[0]
            for t in Tp:
                t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
                t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None)
            rl.save("lit_more_ent_" + sid + "_eval", "LIT more entries: " + title + " (eval path, two_week sizing)", "sessions", Q,
                    params={k: P[k] for k in P}, sizing={"mode": "two_week", **A.CFG}, trades=Tp, scored=rl.score(Tp, A.S26),
                    status=status, verdict=ver, notes="stored trades = the back-to-back eval path per half",
                    writeup="lit-more-entries", tags=["lit", "lit_more_entries"])
        print("saved lit_more_ent_" + sid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "check":
        o = score(run(LIVE))
        print(line("base", o))
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "summary":
        summary(json.load(open(OUT)))
    elif cmd == "save":
        save()
    elif cmd == "m15":
        fam_15m()
    elif cmd == "rearm":
        rearm_diag()
    elif cmd == "chance":
        placebo("live_n2_any_x1.0", 11)          # a random 2nd-trade rule of lonny_c120's size (11 extra trades in 2026)
        placebo("full_n2_any_x1.0", 75)          # random extra trades of the Asia slot's size (75) from the all-hours pool
        placebo("asiaslotn_rr3_x1.0", 0.5, 100)  # the Asia slot with a random half of its extra trades
