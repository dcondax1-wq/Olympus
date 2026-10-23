"""ATLAS (owner 2026-10-22): account B = EMA + MACD + S/R on its own MFFU Builder 25K, tuned AS A WHOLE under the real
account-B rules (engine/account_b.py).

Executor = tools/second_account_b.py (fresh eval every session, 20 sessions; 60-session eventual pass; back-to-back eval
path $; funded 3 / 6 months at the safe size) on the Builder 25K plan, with one addition the research lacked:
  * LIT's ARMED setups block an opposite account-B entry (AccountB.lit_opposite: "LIT has a SHORT setup armed (limit
    working / waiting for its 1m CISD)"), from tools/atlas_lit_armed.py (the live LIT replay, every setup's armed window).
Everything else as tools/second_mix.no_hedge + second_account_b: no B entry while LIT holds the other side, B closed at
market when LIT enters the other side (HEDGE), one position, max 2 a day, the 25K's $600 soft daily loss over the day,
need size (engine/account_b.qty: LIT's two_week "one winner passes" on the 25K preset: 50% room, 20 micros, the day guard,
safe_eval 30% after session 10), stuck under $100 of room. Entries at the 5m open after the signal (the bot routes ~2 s
after the open and skips a probe more than 45 s late: a late fill is a missed trade, never a chased one).

A variant V (dict) = members, per-member size weights, priority, per-member filters (entry window, weekday, VIX regime),
per-member trade sets (re-run research code with other exits / entries: tools/atlas_members.py), 25K sizing knobs.

    python -X utf8 tools/atlas.py base       # today's ATLAS: published scorer vs real rules (armed block)
    python -X utf8 tools/atlas.py grid       # the candidate families -> research/second/atlas_grid.json
Paper research only.
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import hashlib
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine import account_b as EAB  # noqa: E402
from tools import second_mix as M  # noqa: E402
from tools import second_account_b as AB  # noqa: E402
from tools import atlas_lit_armed as ARM  # noqa: E402

ET = ZoneInfo("America/New_York")
PLAN = "builder25k"
SPANS = ("H1", "H2", "2025", "2021-24")
NAMES = ("EMA", "MD", "SR")
BASE = {"members": ["EMA", "MD", "SR"], "w": {}, "armed": True, "flt": {}, "sets": {}, "size": "need", "tw": {}, "cfg": {}}


# ================================================================================================ units
def et_mod(ts):
    x = dt.datetime.fromtimestamp(int(ts), ET)
    return x.hour * 60 + x.minute


_VIX = {}


def vix_prev():
    """day -> the prior session's VIX close (data/VIX_1d.csv; known before the day opens)."""
    if "v" not in _VIX:
        import pandas as pd
        v = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
        days = [str(x)[:10] for x in v["date"]]
        closes = v["close"].astype(float).values
        S = M.units()["sessions"]
        import bisect
        out = {}
        for d in S:
            k = bisect.bisect_left(days, d) - 1
            out[d] = float(closes[k]) if k >= 0 else float("nan")
        _VIX["v"] = out
    return _VIX["v"]


def member_units(name, V):
    """Units of one member: the stored research trades (second_mix cache) or a re-run variant set (atlas_members)."""
    key = (V.get("sets") or {}).get(name)
    if key:
        from tools import atlas_members as AM
        U = AM.units(name, key)
    elif name == "ASIA":
        U = asia_units()
    else:
        U = M.units()[name]
    f = (V.get("flt") or {}).get(name) or {}
    if not f:
        return U
    out = []
    vp = vix_prev() if ("vix" in f) else None
    for u in U:
        m = et_mod(u["entry_t"])
        if "win" in f and not (f["win"][0] <= m < f["win"][1]):
            continue
        if "dows" in f and dt.date.fromisoformat(u["day"]).weekday() not in f["dows"]:
            continue
        if "vix" in f:
            v = vp.get(u["day"], float("nan"))
            if not (f["vix"][0] <= v < f["vix"][1]):
                continue
        if "dir" in f and u["dir"] != f["dir"]:
            continue
        out.append(u)
    return out


_AS = {}


def asia_units():
    """The LIT Asia-slot trades (18:00-02:00 entries of run lit_more_ent_asia_slot_rr3) as an account-B member "ASIA" (no
    open-path data: a trade that overlaps an opposite LIT trade / armed setup at all is dropped, conservative)."""
    if "u" not in _AS:
        _AS["u"] = [{**u, "src": "ASIA", "pt": np.zeros(0, np.int64), "po": np.zeros(0), "pw": np.zeros(0)} for u in M.units()["Asia"]]
    return _AS["u"]


def no_hedge_real(U, armed=True):
    """second_mix.no_hedge (LIT's opposite open trade: skip; LIT entering opposite while B is open: close B, HEDGE) + LIT's
    opposite ARMED setups block a B entry (engine/account_b.AccountB.lit_opposite)."""
    by = collections.defaultdict(list)
    for t in M.units()["LIT"]:
        by[t["day"]].append(t)
    AW = ARM.by_day() if armed else {}
    out = []
    for t in U:
        L = [x for x in by.get(t["day"], ()) if x["dir"] != t["dir"]]
        if any(x["entry_t"] <= t["entry_t"] < x["exit_t"] for x in L):
            continue
        if armed and any(d != t["dir"] and a <= t["entry_t"] < z for d, a, z in AW.get(t["day"], ())):
            continue
        nxt = min((x["entry_t"] for x in L if t["entry_t"] < x["entry_t"] < t["exit_t"]), default=None)
        if nxt is not None:
            if not len(t["pt"]):
                continue                     # ASIA member: no path, dropped
            pts, w1 = M.cut_at(t, nxt)
            t = {**t, "pts": pts, "w1": w1, "exit_t": nxt, "exit": "HEDGE"}
        out.append(t)
    return out


def account_units(V):
    U = []
    for nm in V["members"]:
        U += member_units(nm, V)
    pr = {nm: i for i, nm in enumerate(V.get("order") or V["members"])}
    U = sorted(U, key=lambda t: (t["entry_t"], pr.get(t["src"], 9)))
    return no_hedge_real(U, V.get("armed", True))


# ================================================================================================ sizing
_SPEC = {}


def spec():
    if "s" not in _SPEC:
        _SPEC["s"] = EAB.normalize({"account": "research", "plan": PLAN, "eval_start": "2026-01-02"}, lit_account=None)
    return _SPEC["s"]


_CFG = {}


def cfg_of(V):
    """engine/account_b.sizing_cfg on the 25K + the variant's overrides ("tw": two_week keys, "cfg": top-level keys)."""
    k = json.dumps([V.get("tw") or {}, V.get("cfg") or {}], sort_keys=True)
    if k not in _CFG:
        c = copy.deepcopy(EAB.sizing_cfg(spec()))
        c["two_week"].update(V.get("tw") or {})
        for a, b in (V.get("cfg") or {}).items():
            if isinstance(b, dict) and isinstance(c.get(a), dict):
                c[a] = {**c[a], **b}
            else:
                c[a] = b
        _CFG[k] = c
    return _CFG[k]


def q_variant(t, st, V):
    """Micros of one ATLAS trade: engine/account_b.qty need (or safe) with the variant's sizing knobs, then the member's
    weight and the VIX-regime multiplier (min 1 micro while the base size is >= 1)."""
    r = t["risk"]
    sz = V.get("size", "need")
    S = spec()
    maxq = int(S["rules"]["max_micros"])
    c = cfg_of(V)
    if sz == "safe" or (sz.startswith("hyb") and st["session"] > int(sz[3:])):
        usd = float(V.get("safe_usd", EAB.PLANS[PLAN]["safe_usd"]))
        q = min(maxq, int(SZ.second_qty(float(r), usd, c, state=dict(st), max_micros=maxq)["qty"]))
    else:
        m0 = lit.qty_for(float(r))
        if not m0:
            return 0
        x = SZ.lit_qty(m0, {"risk_pts": float(r), "tgt_pts": t["tgt"], "size_mult": 1.0}, c, room=st["room"], state=dict(st),
                       max_micros=maxq, learning=None)
        q = min(maxq, int(x.get("qty") or 0))
    if q <= 0:
        return 0
    w = float((V.get("w") or {}).get(t["src"], 1.0))
    vm = V.get("vixm")
    if vm:
        v = vix_prev().get(t["day"], float("nan"))
        for lo, hi, mm in vm:
            if lo <= v < hi:
                w *= float(mm)
                break
    if w != 1.0:
        q = max(1, int(q * w + 1e-9)) if w > 0 else 0
    if q > 0:                                  # engine/account_b.dll_guard: one full stop-out fits today's soft daily loss
        q = int(EAB.dll_guard({"qty": q, "reasons": []}, float(r), S["rules"], st)["qty"])
    return q


class Plan(AB.Plan):
    """second_account_b.Plan on the 25K + rule "atlas" = q_variant of the current variant."""

    def __init__(self, V):
        super().__init__(PLAN)
        self.V = V

    def __enter__(self):
        super().__enter__()
        inner, V = M.second_q, self.V

        def second_q(t, st, rule):
            if rule == "atlas":
                return q_variant(t, st, V)
            return inner(t, st, rule)
        M.second_q = second_q
        return self


# ================================================================================================ scoring
def score(V, spans=SPANS, keep_paths=False):
    U = account_units(V)
    out, paths = {}, {}
    with Plan(V) as pl:
        for s in spans:
            o, T = AB.score(U, "atlas", s, V.get("frule") or pl.safe_rule)
            out[s] = o
            if keep_paths:
                paths[s] = T
    return (out, paths) if keep_paths else out


def vid(V):
    return hashlib.md5(json.dumps(V, sort_keys=True).encode()).hexdigest()[:10]


def fmt(o, s):
    x = o[s]
    return (f"{s:7s} 2w {x['p10']:5.1f}/{x['f10']:4.1f} st {x['s10']:4.1f} 1m {x['p20']:5.1f}/{x['f20']:4.1f} med {x['pass_med']} "
            f"p60 {x['p60']} path {x['net']:+7,} ({x['per_month']:+6,}/mo) PF {x['pf']} DD {x['dd']:,} tpw {x['tpw']} "
            f"f3m ${x['fund_paid_3m']} ev ${x.get('ev_eval_3m')}")


def show(o, title=""):
    if title:
        print(title)
    for s in o:
        print("   " + fmt(o, s), flush=True)


def cmd_base():
    M.units()
    o0 = score({**BASE, "armed": False})
    show(o0, "ATLAS today, published scorer (no armed block) - must equal second-account-b.md 68.9/0.0, 43.5/0.0:")
    o1 = score(BASE)
    show(o1, "ATLAS today under the REAL account-B rules (+ LIT's opposite armed setups block):")
    U0 = account_units({**BASE, "armed": False})
    U1 = account_units(BASE)
    c0 = collections.Counter(u["src"] for u in U0 if u["day"] >= "2026-01-01")
    c1 = collections.Counter(u["src"] for u in U1 if u["day"] >= "2026-01-01")
    print("2026 candidate trades after the no-hedge rules:", dict(c0), "->", dict(c1))
    return o0, o1


# ================================================================================================ the candidate families
def K(**kw):
    """A member-set key (JSON, sorted) for tools/atlas_members."""
    return json.dumps(kw, sort_keys=True)


def V_(**kw):
    V = copy.deepcopy(BASE)
    for k, v in kw.items():
        V[k] = v
    return V


def families():
    """(family, name, V) for every candidate. Base = today's ATLAS under the real rules."""
    out = [("base", "today", V_())]
    import itertools
    # 1. members
    pool = ["EMA", "MD", "SR", "ASIA"]
    for n in range(1, 5):
        for sub in itertools.combinations(pool, n):
            if list(sub) == ["EMA", "MD", "SR"]:
                continue
            out.append(("members", "+".join(sub), V_(members=list(sub))))
    # 2. weights
    for we, wm, ws in itertools.product((0.5, 0.75, 1.0), repeat=3):
        if (we, wm, ws) == (1.0, 1.0, 1.0):
            continue
        out.append(("weights", f"EMA{we:g}_MD{wm:g}_SR{ws:g}", V_(w={"EMA": we, "MD": wm, "SR": ws})))
    # 3. priority on the same bar
    for perm in itertools.permutations(NAMES):
        if list(perm) == list(NAMES):
            continue
        out.append(("order", ">".join(perm), V_(order=list(perm))))
    # 4. 25K sizing
    for rf, un, sc in itertools.product((0.4, 0.45, 0.5, 0.55, 0.6), (8, 10, 12, 15, 20), (0.2, 0.3, 0.4, 0.5)):
        if (rf, un, sc) == (0.5, 10, 0.3):
            continue
        out.append(("sizing", f"room{rf:g}_until{un}_safe{sc:g}", V_(tw={"room_f": rf}, cfg={"two_week_until": un, "safe_cap": sc})))
    for nb in (0.8, 0.9, 1.1, 1.25, 1.5):
        out.append(("sizing2", f"need_buf{nb:g}", V_(tw={"need_buf": nb})))
    for dl in (300.0, 400.0, 450.0, 500.0):
        out.append(("sizing2", f"dll{dl:g}", V_(tw={"dll": dl}, cfg={"guard": {"dll": dl}})))
    for mu in (250.0, 300.0, 400.0, 500.0):
        out.append(("sizing2", f"max_usd{mu:g}", V_(tw={"max_usd": mu})))
    out.append(("sizing2", "safe150", V_(size="safe")))
    for su in (150.0, 200.0, 250.0):
        out.append(("sizing2", f"safe{su:g}", V_(size="safe", safe_usd=su)))
        for h in (3, 5, 7):
            out.append(("sizing2", f"hyb{h}_safe{su:g}", V_(size=f"hyb{h}", safe_usd=su)))
    # 5. member filters: entry windows, weekdays, VIX bands
    WIN = {"EMA": [(180, 480), (180, 540), (210, 570), (240, 570), (180, 420)],
           "MD": [(120, 300), (570, 660), (120, 240), (570, 630)],
           "SR": [(570, 660), (570, 690), (600, 720), (570, 630)]}
    for nm, ws in WIN.items():
        for a, z in ws:
            out.append(("window", f"{nm}_{a // 60:02d}{a % 60:02d}-{z // 60:02d}{z % 60:02d}", V_(flt={nm: {"win": [a, z]}})))
    for nm in NAMES:
        for dd in range(5):
            if nm == "EMA" and dd == 0:
                continue
            out.append(("weekday", f"{nm}_no{'MTWRF'[dd]}", V_(flt={nm: {"dows": [x for x in range(5) if x != dd]}})))
        for lo, hi, lab in ((14, 99, "vix>=14"), (16, 99, "vix>=16"), (0, 25, "vix<25"), (0, 30, "vix<30"), (14, 30, "vix14-30")):
            out.append(("vixband", f"{nm}_{lab}", V_(flt={nm: {"vix": [lo, hi]}})))
    for lab, vm in (("lo0.5", [[0, 15, 0.5]]), ("hi0.5", [[25, 99, 0.5]]), ("lohi0.5", [[0, 15, 0.5], [25, 99, 0.5]]),
                    ("hi30_0", [[30, 99, 0.0]]), ("lo14_0.5", [[0, 14, 0.5]]), ("mid_hi0.75", [[22, 99, 0.75]])):
        out.append(("vixsize", lab, V_(vixm=vm)))
    # 6. member exits (re-run research code)
    EX = {"EMA": [("2R", {"tgt": 2.0}), ("3R", {"tgt": 3.0}), ("4R", {"tgt": 4.0}), ("vix_bank3", {"bank": 3.0}),
                  ("vix_bank5", {"bank": 5.0}), ("vix_k0.75", {"vk": 0.75}), ("vix_k1.25", {"vk": 1.25}), ("noBE", {"be": None, "beo": 0.0}),
                  ("BE0.75R", {"be": 0.75}), ("BE1.5R", {"be": 1.5}), ("BEoff0", {"beo": 0.0}), ("BEoff2.5", {"beo": 2.5}),
                  ("t15", {"tchk": [3, 0.3, 0.5]})],
          "MD": [("2R", {"tgt": 2.0}), ("3R", {"tgt": 3.0}), ("lvl", {"tgt": "lvl"}), ("BE", {"be": 1.25}), ("no_t15", {"tc": False})],
          "SR": [("3R", {"tg": 3.0}), ("vix_bank3", {"tg": "vix", "bk": 3.0}), ("vix_bank5", {"tg": "vix", "bk": 5.0}),
                 ("vix_bank8", {"tg": "vix", "bk": 8.0}), ("lvl_bank3", {"tg": "lvl", "bk": 3.0}), ("lvl_bank5", {"tg": "lvl", "bk": 5.0}),
                 ("BE", {"be": 1.25}), ("no_t15", {"tc": False}), ("2pd", {"maxpd": 2}), ("win_nyx", {"win": "nyx"}),
                 ("win_ny", {"win": "ny"})]}
    for nm, L in EX.items():
        for lab, ov in L:
            key = K(X=ov) if nm == "EMA" else K(sim=ov) if nm == "MD" else K(key=ov)
            out.append(("exits", f"{nm}_{lab}", V_(sets={nm: key})))
    # 7. entries: limit at the signal close (latency-proof)
    for nm in NAMES:
        for nb in (1, 2, 3):
            out.append(("entry", f"{nm}_lc{nb}", V_(sets={nm: K(ent=["lc", nb])})))
    out.append(("entry", "ALL_lc1", V_(sets={nm: K(ent=["lc", 1]) for nm in NAMES})))
    out.append(("entry", "ALL_lc2", V_(sets={nm: K(ent=["lc", 2]) for nm in NAMES})))
    return out


def late_family():
    """Robustness (not candidates): every member 1 bar late, market vs limit-at-close."""
    out = [("late", "mkt_late1", V_(sets={nm: K(delay=1) for nm in NAMES}))]
    for nb in (1, 2, 3):
        out.append(("late", f"lc{nb}_ontime", V_(sets={nm: K(ent=["lc", nb]) for nm in NAMES})))
        out.append(("late", f"lc{nb}_late1", V_(sets={nm: K(ent=["lc", nb], delay=1) for nm in NAMES})))
    for nm in NAMES:
        out.append(("late", f"{nm}_mkt_late1", V_(sets={nm: K(delay=1)})))
        out.append(("late", f"{nm}_lc2_late1", V_(sets={nm: K(ent=["lc", 2], delay=1)})))
    return out


SR11 = {"SR": {"win": [570, 660]}}


def round2():
    """Round 2: the plateau around the one H1+H2 winner with a reason (S/R entries only until 11:00) and what stacks on it."""
    out = [("base", "today", V_()), ("r2", "SR_until1100", V_(flt=SR11))]
    for a in (570, 575, 585, 600):
        for z in (615, 630, 645, 650, 655, 660, 665, 670, 675, 690, 720):
            if (a, z) in ((570, 660), (570, 720)):
                continue
            out.append(("sr_window", f"SR_{a // 60:02d}{a % 60:02d}-{z // 60:02d}{z % 60:02d}", V_(flt={"SR": {"win": [a, z]}})))
    stack = {"EMA_t15": dict(sets={"EMA": K(X={"tchk": [3, 0.3, 0.5]})}), "SR_no_t15": dict(sets={"SR": K(key={"tc": False})}),
             "EMA_noR": dict(flt={**SR11, "EMA": {"dows": [0, 1, 2, 4]}}), "MD_noT": dict(flt={**SR11, "MD": {"dows": [0, 2, 3, 4]}}),
             "until15_safe0.4": dict(cfg={"two_week_until": 15, "safe_cap": 0.4}),
             "room0.45_until15_safe0.4": dict(tw={"room_f": 0.45}, cfg={"two_week_until": 15, "safe_cap": 0.4}),
             "MD_vix>=16": dict(flt={**SR11, "MD": {"vix": [16, 99]}}), "EMA_0300-0700": dict(flt={**SR11, "EMA": {"win": [180, 420]}}),
             "w_SR0.75": dict(w={"SR": 0.75}), "w_MD0.75": dict(w={"MD": 0.75}), "need_buf1.25": dict(tw={"need_buf": 1.25}),
             "plus_ASIA": dict(members=["EMA", "MD", "SR", "ASIA"])}
    for lab, kw in stack.items():
        V = V_(flt=dict(SR11), **{k: v for k, v in kw.items() if k != "flt"})
        if "flt" in kw:
            V["flt"] = kw["flt"]
        out.append(("stack", "SR11+" + lab, V))
    # the same window cut through the SR research code's own window (must equal the post-hoc filter)
    WIN11 = K(key={"win": "ny11"})
    out.append(("check", "SR_key_ny11", V_(sets={"SR": WIN11})))
    return out


def round3():
    """Round 3 (coordinator: push the risk side): member up-weights, room share x need buffer, banked R."""
    import itertools
    out = [("base", "today", V_())]
    for nm in NAMES:
        for w in (1.25, 1.5, 2.0):
            out.append(("upweight", f"{nm}x{w:g}", V_(w={nm: w})))
    for we, wm, ws in itertools.product((1.0, 1.25, 1.5), repeat=3):
        if len({we, wm, ws}) > 1 and max(we, wm, ws) > 1.0:
            out.append(("upweight3", f"E{we:g}_M{wm:g}_S{ws:g}", V_(w={"EMA": we, "MD": wm, "SR": ws})))
    for rf in (0.4, 0.45, 0.55, 0.6):
        for nb in (1.0, 1.25):
            out.append(("room_x_buf", f"room{rf:g}_buf{nb:g}", V_(tw={"room_f": rf, "need_buf": nb})))
    for bk in (4.0, 6.0):
        out.append(("bank", f"EMA_bank{bk:g}", V_(sets={"EMA": K(X={"bank": bk})})))
    for bk in (2.0, 4.0):
        out.append(("bank", f"SR_vix_bank{bk:g}", V_(sets={"SR": K(key={"tg": "vix", "bk": bk})})))
    return out


def prebuild(F):
    from tools import atlas_members as AM
    need = sorted({(nm, k) for _, _, V in F for nm, k in (V.get("sets") or {}).items()})
    for i, (nm, k) in enumerate(need):
        if not AM.cached(nm, k):
            AM.units(nm, k)
            print(f"  set {i + 1}/{len(need)} {nm} {k} built", flush=True)


def _job(x):
    fam, name, V = x
    try:
        o = score(V)
    except Exception as e:
        return fam, name, V, {"error": f"{e.__class__.__name__}: {e}"}
    return fam, name, V, o


KEEP = ("p10", "f10", "s10", "dead10", "p20", "f20", "s20", "pass_med", "slow_pass", "p60", "f60", "fund_paid_3m",
        "fund_lost_3m", "fund_paid_6m", "ev_eval_3m", "ev_eval_6m", "n", "tpw", "net", "per_month", "dd", "pf", "b2b",
        "evals_bought", "max_risk", "med_risk", "by_src", "path_net_less_fees", "cost_2wk_pass", "starts")


def run_grid(F, procs=4):
    from multiprocessing import Pool
    M.units(); ARM.windows(); vix_prev()
    prebuild(F)
    from tools import atlas_members as AM
    for _, _, V in F:                          # load every set into memory before the fork
        for nm, k in (V.get("sets") or {}).items():
            AM.units(nm, k)
    with Pool(procs) as P:
        R = P.map(_job, F, chunksize=4)
    return [{"family": f, "name": n, "V": V, "o": {s: {k: o[s].get(k) for k in KEEP} for s in o} if "error" not in o else o}
            for f, n, V, o in R]


GRID = os.path.join(ROOT, "research", "second", "atlas_grid.json")


def better(x, b, strict=True):
    """The owner's test in one span: 2-week pass up or equal, dead (fail + stuck) not up, $ up."""
    return x["p10"] >= b["p10"] and x["dead10"] <= b["dead10"] and (x["net"] > b["net"] if strict else x["net"] >= b["net"])


def report(R):
    base = next(r for r in R if r["family"] == "base")["o"]
    show(base, "BASE (real rules)")
    fams = collections.OrderedDict()
    for r in R:
        fams.setdefault(r["family"], []).append(r)
    summ = {}
    for f, rows in fams.items():
        if f == "base":
            continue
        ok = [r for r in rows if "error" not in r["o"]]
        h1 = [r for r in ok if better(r["o"]["H1"], base["H1"])]
        h2 = [r for r in ok if better(r["o"]["H2"], base["H2"])]
        both = [r for r in h1 if better(r["o"]["H2"], base["H2"])]
        summ[f] = {"n": len(rows), "h1": len(h1), "h2_all": len(h2), "both": len(both),
                   "chance_both": round(len(h1) * len(h2) / max(1, len(ok)), 1)}
        print(f"\n== {f}: {len(rows)} variants; better in H1 {len(h1)}; better in H2 (any) {len(h2)}; both {len(both)} "
              f"(chance {summ[f]['chance_both']})")
        key = lambda r: (r["o"]["H1"]["p10"] - 2 * r["o"]["H1"]["dead10"] + r["o"]["H1"]["net"] / 1000.0)
        for r in sorted(ok, key=key, reverse=True)[:8]:
            o = r["o"]
            tag = "BOTH" if r in both else ("h1" if r in h1 else "  ")
            print(f"  {tag:4s} {r['name']:28s} H1 {o['H1']['p10']:5.1f}/{o['H1']['dead10']:4.1f} {o['H1']['net']:+7,} | "
                  f"H2 {o['H2']['p10']:5.1f}/{o['H2']['dead10']:4.1f} {o['H2']['net']:+7,} | 25 {o['2025']['p10']:5.1f}/{o['2025']['dead10']:4.1f} "
                  f"{o['2025']['net']:+7,} | 21-24 {o['2021-24']['p10']:5.1f}/{o['2021-24']['dead10']:4.1f} {o['2021-24']['net']:+7,} "
                  f"| f3m {o['H1']['fund_paid_3m']} ev {o['H1'].get('ev_eval_3m')}")
        for r in both:
            if r not in sorted(ok, key=key, reverse=True)[:8]:
                o = r["o"]
                print(f"  BOTH {r['name']:28s} H1 {o['H1']['p10']:5.1f}/{o['H1']['dead10']:4.1f} {o['H1']['net']:+7,} | "
                      f"H2 {o['H2']['p10']:5.1f}/{o['H2']['dead10']:4.1f} {o['H2']['net']:+7,} | 25 {o['2025']['p10']:5.1f}/{o['2025']['dead10']:4.1f} "
                      f"{o['2025']['net']:+7,} | 21-24 {o['2021-24']['p10']:5.1f}/{o['2021-24']['dead10']:4.1f} {o['2021-24']['net']:+7,}")
    return summ


def cmd_grid(which="main"):
    import time
    t0 = time.time()
    F = families() if which == "main" else round2() if which == "round2" else round3() if which == "round3" else late_family() + [("base", "today", V_())]
    print(len(F), "variants", flush=True)
    R = run_grid(F)
    print(f"scored in {time.time() - t0:.0f}s", flush=True)
    path = GRID if which == "main" else GRID.replace(".json", f"_{which}.json")
    json.dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "rows": R}, open(path, "w"), separators=(",", ":"), default=str)
    summ = report(R)
    return R, summ


# ================================================================================================ store + atlas.json
RUNS = [
    ("atlas_base", "ATLAS today under the real account-B rules (EMA + MACD + S/R on a Builder 25K, LIT's armed setups block)",
     "adopt-candidate", V_()),
    ("atlas_base_published", "ATLAS today, published scorer (no armed-setup block) = acctb_25k_need", "info", V_(armed=False)),
    ("atlas_sr_until1100", "ATLAS with S/R entries only until 11:00 (H1+H2 better, but a 5-minute spike: 3 H1 stop-outs at 11:00)",
     "rejected", V_(flt=SR11)),
    ("atlas_ema_nothu", "ATLAS with no EMA trade on Thursdays (calendar rule; 2025 / 2021-24 mixed)", "rejected",
     V_(flt={"EMA": {"dows": [0, 1, 2, 4]}})),
    ("atlas_plus_asia", "ATLAS + the LIT Asia slot as a fourth member", "rejected", V_(members=["EMA", "MD", "SR", "ASIA"])),
    ("atlas_limit_close2", "ATLAS with every member entering on a limit at the signal close (10 min)", "rejected",
     V_(sets={nm: K(ent=["lc", 2]) for nm in NAMES})),
    ("atlas_late_mkt", "ATLAS stress: every entry 1 bar late at market", "info", V_(sets={nm: K(delay=1) for nm in NAMES})),
    ("atlas_late_limit2", "ATLAS stress: every entry 1 bar late on a limit at the signal close", "info",
     V_(sets={nm: K(ent=["lc", 2], delay=1) for nm in NAMES})),
]
ATLAS_JSON = os.path.join(ROOT, "research", "second", "atlas.json")
SPAN_KEY = {"H1": "H1", "H2": "H2", "2025": "y2025", "2021-24": "y2124"}


def _win(T):
    return round(100.0 * sum(1 for t in T if t["pnl"] > 0) / len(T), 1) if T else None


def cmd_save():
    from tools import runlib as rl
    M.units()
    Q = "Owner 2026-10-22: tune ATLAS (account B: EMA + MACD + S/R) as a whole for the Builder 25K under the real account-B rules"
    sess = [d for d in M.units()["sessions"] if d >= "2021-01-01"]
    keep = {}
    for rid, title, status, V in RUNS:
        o, P = score(V, keep_paths=True)
        keep[rid] = (o, P)
        T = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
              "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0, "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"],
              "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"], "mfe": None, "mae": None,
              "bars_held": None, "regime": "", "mult": None, "low": t["low"]} for s in SPANS for t in P[s]]
        f = lambda s: (f"{o[s]['tpw']}/wk, path {o[s]['net']:+,} (${o[s]['per_month']:,}/mo, PF {o[s]['pf']}, DD {o[s]['dd']:,}); 2-week "
                       f"pass/fail/stuck {o[s]['p10']}/{o[s]['f10']}/{o[s]['s10']}, 1 month {o[s]['p20']}/{o[s]['f20']}, median "
                       f"{o[s]['pass_med']} sessions; funded 3 mo ${o[s]['fund_paid_3m']}")
        rl.save(rid, title, "other", Q, params={"V": V}, sizing={"plan": PLAN, "size": V.get("size", "need")}, trades=T,
                scored=rl.score(T, sess), status=status,
                verdict=f"Builder 25K, fresh eval every session (20 sessions; $ = back-to-back eval path). 2026 H1 (pick) {f('H1')}. "
                        f"H2 (check) {f('H2')}. Reference 2025 {f('2025')}; 2021-24 {f('2021-24')}.",
                notes="tools/atlas.py (executor tools/second_account_b.py + LIT's armed-setup block, tools/atlas_lit_armed.py); "
                      "stored trades = the back-to-back eval path of each span; the run library's own eval columns re-score that "
                      "path on the 50K plan and are not the published odds (those are in the verdict).",
                writeup="atlas", tags=["second", "account_b", "atlas"])
        print("saved", rid, flush=True)
    o, P = keep["atlas_base"]
    cfg = json.load(open(os.path.join(ROOT, "second_model.json"), encoding="utf-8"))["strategies"]
    out = {
        "name": "ATLAS",
        "version": "2026-10-22",
        "status": "built, OFF (second_model.json \"account_b\": null); paper / Sim first",
        "account": "MFFU Builder 25K ($63, owner's price), account B next to LIT's Builder 50K",
        "members": [{"key": "ema_lon_vix", "short": "EMA", "label": cfg["ema_lon_vix"]["label"]},
                    {"key": "macd_sweep", "short": "MACD", "label": cfg["macd_sweep"]["label"]},
                    {"key": "sr_nyreclaim", "short": "S/R", "label": cfg["sr_nyreclaim"]["label"]}],
        "rules": {
            "EMA": ["London hours only: entries 03:00-09:30 ET, never on a Monday.",
                    "Trend: the 15-minute and the 1-hour EMA 21 are both above their EMA 50 (below for shorts).",
                    "Setup: a pullback reaches the 5-minute EMA 50 and takes out a recent swing low (a stop hunt), then a 5-minute candle closes back above the start of the pullback (CISD).",
                    "Entry at market at the next 5-minute open; stop 1 tick beyond the pullback's low; target = LIT's VIX band (18:00 open +/- one VIX day-move, at least 1.5R, banked at 8R).",
                    "At +1R the stop moves to entry + 1.25 points (breakeven plus costs); flat at 15:55; one EMA trade a day."],
            "MACD": ["Two windows: London 02:00-05:00 ET and the New York open 09:30-11:00.",
                     "Setup: a LIT level (session high/low, previous day / week / month, build-ups, gaps) is swept by at least 0.5 ATR and a 5-minute candle closes back (CISD) while the MACD line shows divergence.",
                     "Entry at market at the next 5-minute open; stop beyond the sweep extreme; target = the VIX band (at least 1.5R, banked at 8R).",
                     "15-minute check: cut the trade if after 15 minutes it is 0.3R against and never got 0.5R in favour; flat at 15:55; one MACD trade a day."],
            "S/R": ["New York only: entries 09:30-12:00 ET.",
                    "Levels of the day: yesterday's RTH high/low, the overnight high/low, the Asia and London boxes, last week's high/low, the opening range.",
                    "Setup: an inducement swing is taken first, then the level is swept and within 4 bars a strong 5-minute candle (body >= 0.3 ATR) closes back over it (reclaim).",
                    "Entry at market at the next 5-minute open; stop beyond the sweep extreme (max 80 points); target 2R; the 15-minute check as MACD; flat at 15:55; one S/R trade a day."],
            "account": ["One position at a time on ATLAS's account, at most 2 trades a day; when two members signal at the same open: EMA first, then MACD, then S/R.",
                        "Never opposite to LIT: no ATLAS entry while LIT holds, enters or has an armed setup the other way; if LIT enters the other way while ATLAS is in a trade, ATLAS closes first (HEDGE).",
                        "Size (need): micros so one winner's target covers what is left to the $1,500 target, capped at 50% of the room to the trailing floor and the $600 soft daily loss, max 20 micros, for 10 sessions; then 30% of the room. A trade whose full stop-out would break the floor or the $600 is skipped.",
                        "Orders go out about 2 seconds after the 5-minute open; a probe more than 45 seconds late is skipped (never chased).",
                        "The account stops when the eval is passed ($1,500), failed, or stuck (less than $100 of room)."]},
        "verdict": ("Keep ATLAS as it is: 358 tweaks (members, Asia slot, size weights down and up, priority, 25K sizing, windows, "
                    "weekdays, VIX, exits, banked R, limit entry) and the confluence job's 1,481 variants found nothing that is "
                    "better in 2026 H1 and H2 beyond chance and holds as a plateau. Account B stays off until the paper scorecard "
                    "says ready."),
        "numbers": {}, "eval25k": {},
        "source": {"tool": "tools/atlas.py", "run": "atlas_base", "writeup": "research/writeups/atlas.md"},
    }
    for s in SPANS:
        x, T = o[s], P[s]
        out["numbers"][SPAN_KEY[s]] = {"net": x["net"], "per_month": x["per_month"], "pf": x["pf"], "win": _win(T), "tpw": x["tpw"],
                                       "max_dd": x["dd"], "trades": x["n"]}
        out["eval25k"][SPAN_KEY[s]] = {"p10": x["p10"], "f10": x["f10"], "s10": x["s10"], "p20": x["p20"], "f20": x["f20"],
                                       "pass_med": x["pass_med"], "p60": x["p60"], "funded_3mo": x["fund_paid_3m"],
                                       "funded_6mo": x["fund_paid_6m"], "funded_lost_3mo": x["fund_lost_3m"], "ev_per_eval": x.get("ev_eval_3m")}
    out["notes"] = ("numbers = the back-to-back eval path on the Builder 25K (a new $63 eval after each pass / fail / stuck); eval25k = a "
                    "fresh eval started on every session of the span (p10/f10/s10 = pass/fail/stuck within 10 sessions, p20/f20 within "
                    "20, pass_med = median sessions to pass, p60 = pass within 60 sessions); funded = paid to the trader in 3 / 6 months "
                    "on the 25K sim-funded account at $150 risk a trade (H1 starts are the solid figure; H2 has only 16 starts that "
                    "can see 3 months); ev_per_eval = p60 x funded 3 months - $63.")
    json.dump(out, open(ATLAS_JSON, "w", encoding="utf-8"), indent=1)
    print("wrote", ATLAS_JSON)
    return keep


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "save":
        cmd_save()
        sys.exit(0)
    a = sys.argv[1] if len(sys.argv) > 1 else "base"
    if a == "base":
        cmd_base()
    elif a == "grid":
        cmd_grid("main")
    elif a in ("late", "round2", "round3"):
        cmd_grid(a)
