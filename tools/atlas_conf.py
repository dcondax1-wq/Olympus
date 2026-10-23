"""ATLAS confluences, risk changes and entry robustness (owner 2026-10-22 night: "find a way to progress this strategy,
whether it's adding a confluence or risking something else, make it better").

ATLAS = account B on an MFFU Builder 25K: EMA (ema_lon_vix) + MACD (macd_sweep) + S/R (sr_nyreclaim). Every variant here is
scored under the LIVE account-B rules (engine/account_b.py):
  * executor = tools/second_account_b.py (fresh eval every session, 20 sessions; back-to-back eval path $; stuck under $100
    of room), Builder 25K plan, need size = engine/account_b.qty (LIT two_week "one winner passes" on the 25K preset: 50%
    room, 20 micros, $600 soft daily loss, day guard; safe_eval 30% after session 10), one position, max 2 a day;
  * never opposite LIT: no B entry while LIT holds the other side, B closed at market when LIT enters the other side
    (tools/second_mix.no_hedge), AND no B entry while LIT has a setup ARMED the other way (limit working / waiting for
    its 1m CISD; the windows of the live LIT replay, the method of the ATLAS job's tools/atlas_lit_armed.py, cache
    research/runs/_cache/atlas_lit_armed.pkl, rebuilt here by armed_build() when missing).
Selection: picked on 2026 H1, checked untouched on 2026 H2; 2025 and 2021-24 are the reference. Every variant is counted.

Families
  conf   ~34 facts per trade, all from bars CLOSED before the entry (5m bar k counts once k's close <= entry time; 15m / 1h
         bars once their close <= entry; daily / VIX / VXN values from earlier sessions; the news calendar is known ahead).
         Each fact in both polarities x 5 rules (skip AGAINST / x0.5 AGAINST / x1.25 WITH / x1.5 WITH / tilt x0.5-x1.5) x 4
         scopes (all of ATLAS, EMA only, MACD only, S/R only). Continuous facts: WITH = top third, AGAINST = bottom third,
         cut points from that scope's 2026 H1 trades.
  risk   per-member size weights; max 1 vs 2 a day; a 2nd entry only after a win / only after a loss; 25K sizing knobs
         (room share, safe share after session 10, the two_week horizon, a $ cap a trade, need buffer).
  exits  each member re-run by its own research code with other targets / breakeven / 15-minute check / partials
  entry  limit entries (each simulator's own limit mode) vs market.
Chance: the pass count vs 20 rounds of shuffled facts (the facts permuted across the trades of each span), and for each
survivor a random-pick placebo (the same rule on the same number of randomly picked trades of the same scope, 200 draws).
Look-ahead: lookahead() recomputes the facts of 30 trades on data cut at their entry and compares.

    python -X utf8 tools/atlas_conf.py base        # base (published scorer vs live rules)
    python -X utf8 tools/atlas_conf.py conf        # the confluence family + shuffles -> research/runs/_cache/atlas_conf_*.json
    python -X utf8 tools/atlas_conf.py risk        # risk family
    python -X utf8 tools/atlas_conf.py members     # exit / entry variants per member (research code re-runs)
    python -X utf8 tools/atlas_conf.py lookahead   # facts on cut data == full data
    python -X utf8 tools/atlas_conf.py final       # survivors, placebos, combos -> research/second/atlas_candidates.json
    python -X utf8 tools/atlas_conf.py save        # rl.save atlas_c_*
Paper research only: edits no engine file, no live_model*.json, no second_model.json.
"""
from __future__ import annotations

import bisect
import collections
import copy
import datetime as dt
import json
import math
import os
import pickle
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit  # noqa: E402
from engine import account_b as EAB  # noqa: E402
from tools import second_mix as M  # noqa: E402
from tools import second_account_b as AB  # noqa: E402

ET = ZoneInfo("America/New_York")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
ARMED = os.path.join(CACHE, "atlas_lit_armed.pkl")
OUT = os.path.join(ROOT, "research", "second", "atlas_candidates.json")
PLAN = "builder25k"
NAMES = ("EMA", "MD", "SR")
SPANS = ("H1", "H2", "2025", "2021-24")
TICK = 0.25


# ================================================================================================ LIT armed windows
def armed_build():
    """The live LIT replay's armed setups (same method as tools/atlas_lit_armed.py of the ATLAS job): engine/lit.simulate_x
    wrapped; each setup walked from the 5m CISD close to the moment the live loop knows it is gone."""
    from tools import lit_final as F
    from tools import lit_adopt_combo as AC
    W = []
    orig = lit.simulate_x

    def walk_end(Mk, B, cand, entry_px, tgt, stop, P):
        d = cand["dir"]
        hi_d, lo_d, c_d, o_d = B.dirs(d)
        t0 = int(Mk.t[cand["entry_i"]])
        k0 = int(np.searchsorted(B.t, t0))
        s_day = int(Mk.day_of[cand["entry_i"]])
        if k0 >= B.n:
            return t0
        flat, ev, wait_s = P["flat_mod"], bool(P.get("all_hours")), P["wait"] * 300
        cis = P.get("cisd1m")
        if cis and B.secs == 300:
            cis = max(1, cis // 5)
        tgt_cancel = entry_px + tgt[1] if tgt[0] == "pts" else tgt[1]
        tapped, k, sec = None, k0, B.secs
        while k < B.n:
            if B.day[k] != s_day or lit._late(B.mod[k], flat, ev):
                return int(B.t[k])
            if tapped is None and B.t[k] >= t0 + wait_s:
                return int(B.t[k])
            if lo_d[k] <= stop:
                if tapped is None and lo_d[k] <= entry_px and not cis:
                    return int(B.t[k])
                return int(B.t[k]) + sec
            if tapped is None and lo_d[k] <= entry_px:
                if cis:
                    tapped = k
                else:
                    return int(B.t[k])
            if tapped is None and hi_d[k] >= tgt_cancel:
                return int(B.t[k]) + sec
            if tapped is not None:
                if k - tapped > cis:
                    return int(B.t[k])
                lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
                cz = lit._cisd_level(c_d, o_d, lowk)
                if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                    return int(B.t[k]) + sec
            k += 1
        return int(B.t[B.n - 1]) + sec

    def wrap(Mk, B, cand, entry_px, tgt, stop, P, live=False):
        t = orig(Mk, B, cand, entry_px, tgt, stop, P, live=live)
        W.append({"day": cand["day"], "dir": int(cand["dir"]), "t0": int(Mk.t[cand["entry_i"]]),
                  "end": int(walk_end(Mk, B, cand, entry_px, tgt, stop, P)), "filled": t is not None})
        return t

    lit.simulate_x = wrap
    try:
        F.run(AC.LIVE | {"t_check": AC.T15, "be_off": AC.BE_OFF})
    finally:
        lit.simulate_x = orig
    out = {"windows": W}
    pickle.dump(out, open(ARMED, "wb"))
    return out


_ARM = {}


def armed_by_day():
    if "a" not in _ARM:
        W = (pickle.load(open(ARMED, "rb")) if os.path.exists(ARMED) else armed_build())["windows"]
        by = collections.defaultdict(list)
        for w in W:
            if w["end"] > w["t0"]:
                by[w["day"]].append((w["dir"], w["t0"], w["end"]))
        _ARM["a"] = by
    return _ARM["a"]


def live_rules(U):
    """second_mix.no_hedge (LIT holds / enters the other side) + the armed-setup block (engine/account_b lit_opposite)."""
    by = armed_by_day()
    U = M.no_hedge(U)
    return [t for t in U if not any(d != t["dir"] and a <= t["entry_t"] < e for d, a, e in by.get(t["day"], ()))]


# ================================================================================================ scorer
KNOBS = {}            # sizing knobs of the current variant (room_f, safe_cap, until, max_usd, need_buf)
_ORIG_CFG = EAB.sizing_cfg


def _cfg_patched(spec, base=None):
    c = _ORIG_CFG(spec, base)
    m = KNOBS.get("_m", 1.0)
    if KNOBS or m != 1.0:
        c = copy.deepcopy(c)
        tw = c.setdefault("two_week", {})
        if m != 1.0:
            tw["press_at"], tw["press_mult"] = 1, float(m)
        for k in ("room_f", "max_usd", "need_buf"):
            if k in KNOBS:
                tw[k] = KNOBS[k]
        if "safe_cap" in KNOBS:
            c["safe_cap"] = KNOBS["safe_cap"]
        if "until" in KNOBS:
            c["two_week_until"] = KNOBS["until"]
    return c


EAB.sizing_cfg = _cfg_patched
OPTS = {"max_day": 2, "after": None}


def play_day(L, day, bal, floor, session, rule, pre=False, max_day=2, lost=None, litcfg=None, dll=None, reserve=True, extra=None):
    """tools/second_mix.play_day for account B (no LIT units, no reservation), + per-unit size multiplier t["m"] and the
    risk options OPTS (max_day, after: "win" = a 2nd entry only after a winner, "loss" = only after a loser)."""
    dll = M.DLL if dll is None else dll
    max_day = OPTS["max_day"]
    cum, busy, n, recs = 0.0, 0, 0, []
    for t in L:
        if cum <= -dll:
            break
        if t["entry_t"] < busy or n >= max_day:
            continue
        if n >= 1 and OPTS["after"] and recs:
            last = recs[-1]["pnl"]
            if (OPTS["after"] == "win" and last <= 0) or (OPTS["after"] == "loss" and last > 0):
                continue
        st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": session, "n_today": 0, **(extra or {})}
        m = float(t.get("m", 1.0))
        KNOBS["_m"] = m
        try:
            q = M.second_q(t, st, rule)
        finally:
            KNOBS["_m"] = 1.0
        if q > 0 and m != 1.0 and session > int(KNOBS.get("until", 10)):
            # safe_eval part (after the two_week horizon): the multiplier on the routed micros, re-capped by the safe share
            # of the room and the soft daily loss (never above the plan's 20 micros)
            r = t["risk"]
            if m < 1.0:
                q = max(1, int(q * m + 1e-9))
            else:
                cap_r = int(float(KNOBS.get("safe_cap", 0.3)) * max(0.0, st["room"]) / (r * M.PV))
                cap_d = int(max(0.0, dll + cum) / ((r + 0.5) * M.PV + M.ECOMM))
                q = max(q, min(int(q * m + 1e-9), cap_r, cap_d, 20))
        if q <= 0:
            continue
        pts, w1, ex, xt = t["pts"], t["w1"], t["exit"], t["exit_t"]
        pnl = pts * M.PV * q - M.ECOMM * q
        low = min(0.0, w1 * M.PV * q - M.ECOMM * q, pnl)
        if cum + low <= -dll:
            pnl = -dll - cum - M.SLIP * M.PV * q
            low = pnl
        recs.append({"day": day, "entry_t": t["entry_t"], "exit_t": xt, "dir": t["dir"], "exit": ex, "risk": t["risk"],
                     "tgt": t["tgt"], "src": t["src"], "qty": q, "pnl": round(pnl, 2), "low": round(low, 2),
                     "risk_usd": round(t["risk"] * M.PV * q, 2)})
        busy = xt; n += 1
        if bal + cum + low <= floor:
            return cum, recs, True
        cum += pnl
    return cum, recs, False


class Scorer:
    """with Scorer(): score(U) -> {span: o}. U = account-B units (already through live_rules), each optionally with "m"."""

    def __enter__(self):
        self.pl = AB.Plan(PLAN).__enter__()
        self._pd = M.play_day
        M.play_day = play_day
        return self

    def __exit__(self, *a):
        M.play_day = self._pd
        self.pl.__exit__(*a)


def score(U, spans=SPANS, knobs=None, opts=None, full=False):
    KNOBS.clear(); KNOBS.update(knobs or {}); KNOBS["_m"] = 1.0
    OPTS.update({"max_day": 2, "after": None}); OPTS.update(opts or {})
    out = {}
    U = [t for t in U if t.get("m", 1.0) > 0]
    try:
        for s in spans:
            o, T = (AB.score(U, "acctb_need", s, "usd150_safe_dll") if full else quick_score(U, s))
            out[s] = o
    finally:
        KNOBS.clear(); OPTS.update({"max_day": 2, "after": None})
    return out


def quick_score(U, span):
    """AB.score without the funded / 60-session parts (same 2-week / 1-month odds and the same back-to-back path $)."""
    by = M.by_day(U)
    allS = M.units()["sessions"]
    a, z = M.SPANS[span]
    S = [d for d in allS if a <= d <= z]
    res = [(AB.run_eval(S[i:i + 20], by, "acctb_need"), len(S) - i) for i in range(len(S))]
    o = {"starts": len(S)}
    for lab, h in (("10", 10), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
        o["s" + lab] = round(100.0 * sum(1 for r in R if r[0] == "STUCK" and r[1] <= h) / N, 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS" and r[1] <= 20]
    o["pass_med"] = float(np.median(pas)) if pas else None
    k, T, n = 0, [], collections.Counter()
    while k < len(S):
        r, used, _ = AB.run_eval(S[k:], by, "acctb_need", len(S) - k, keep=T)
        n[r] += 1
        if r == "OPEN":
            break
        k += used
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    o.update(n=len(T), tpw=round(len(T) / (len(S) / 5), 2), net=round(float(p.sum())), per_month=round(float(p.sum()) / (len(S) / 21)),
             dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())),
             pf=round(float(p[p > 0].sum() / gl), 2) if gl else None, b2b=f"{n['PASS']}/{n['FAIL']}/{n['STUCK']}/{n['OPEN']}",
             max_risk=round(max((t["risk_usd"] for t in T), default=0.0)),
             by_src={s: [sum(1 for t in T if t["src"] == s), round(sum(t["pnl"] for t in T if t["src"] == s))] for s in sorted({t["src"] for t in T})})
    o["evals"] = n["PASS"] + n["FAIL"] + n["STUCK"] + (1 if n["OPEN"] else 0)
    o["net_less_fees"] = round(o["net"] - o["evals"] * M.PRICE)
    return o, T


def eval_pts(o):
    """Eval score of one span: 2-week pass - 2 x 2-week fail - 2-week stuck (all %)."""
    return o["p10"] - 2.0 * o["f10"] - o["s10"]


# ================================================================================================ units
_U = {}


def raw_units(sets=None):
    """EMA / MD / SR units (second_mix cache, or re-run member sets {name: unit list})."""
    u = M.units()
    out = []
    for nm in NAMES:
        L = (sets or {}).get(nm)
        out += [dict(t) for t in (L if L is not None else u[nm])]
    return out


def base_units(sets=None):
    return live_rules(raw_units(sets))


# ================================================================================================ facts (closed bars only)
def _read(path):
    df = pd.read_csv(path).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return df


class Ctx:
    """Every bar array the facts need, computed causally (a value at bar k uses bars <= k only)."""

    def __init__(self, cut=None):
        def rd(name):
            df = _read(os.path.join(ROOT, "data", name))
            if cut is not None:
                df = df[df["time"] + _secs(name) <= cut].reset_index(drop=True)
            return df
        n5 = rd("NQ_5m.csv")
        self.t = n5["time"].values.astype(np.int64)
        self.o, self.h, self.l, self.c = (n5[k].values.astype(float) for k in ("open", "high", "low", "close"))
        self.v = n5["volume"].values.astype(float)
        et = pd.to_datetime(self.t, unit="s", utc=True).tz_convert(ET)
        self.mod = (et.hour * 60 + et.minute).values
        td = (et + pd.Timedelta(hours=6))
        self.td = np.array(td.strftime("%Y-%m-%d"))
        self.tdow = td.dayofweek.values
        tr = np.maximum(self.h - self.l, np.maximum(abs(self.h - np.r_[self.c[0], self.c[:-1]]), abs(self.l - np.r_[self.c[0], self.c[:-1]])))
        self.atr = pd.Series(tr).rolling(14, min_periods=1).mean().values
        self.atr_m = pd.Series(self.atr).rolling(5520, min_periods=300).mean().values
        # per trading day: first index, running high / low, vwap
        newd = np.r_[True, self.td[1:] != self.td[:-1]]
        gid = np.cumsum(newd) - 1
        self.gid = gid
        self.d_first = np.flatnonzero(newd)
        self.d_names = self.td[self.d_first]
        g = pd.DataFrame({"g": gid, "h": self.h, "l": self.l, "pv": (self.h + self.l + self.c) / 3.0 * self.v, "v": self.v})
        self.dhi = g.groupby("g")["h"].cummax().values
        self.dlo = g.groupby("g")["l"].cummin().values
        cpv = g.groupby("g")["pv"].cumsum().values
        cv = g.groupby("g")["v"].cumsum().values
        self.vwap = np.where(cv > 0, cpv / np.maximum(cv, 1e-9), self.c)
        last = np.r_[self.d_first[1:] - 1, len(self.t) - 1]
        self.d_last = last
        self.d_open = self.o[self.d_first]
        self.d_close = self.c[last]
        self.d_hi = np.array([self.h[a:b + 1].max() for a, b in zip(self.d_first, last)])
        self.d_lo = np.array([self.l[a:b + 1].min() for a, b in zip(self.d_first, last)])
        rng = self.d_hi - self.d_lo
        self.d_atr = pd.Series(rng).rolling(14, min_periods=3).mean().shift(1).values      # prior 14 days
        self.d_dow = pd.to_datetime(self.d_names).dayofweek.values
        # HTF (15m, 1h): closed bars
        self.htf = {}
        for nm, secs in (("NQ_15m.csv", 900), ("NQ_1h.csv", 3600)):
            df = rd(nm)
            tt = df["time"].values.astype(np.int64)
            hh, ll, cc = df["high"].values, df["low"].values, df["close"].values
            self.htf[secs] = {"t": tt, "c": cc, "bos": _bos(hh, ll, cc),
                              "e21": pd.Series(cc).ewm(span=21, adjust=False).mean().values,
                              "e50": pd.Series(cc).ewm(span=50, adjust=False).mean().values}
        # ES 5m (2025-04 on)
        es = rd("ES_5m.csv")
        self.es_t = es["time"].values.astype(np.int64)
        self.es_h, self.es_l, self.es_c = es["high"].values, es["low"].values, es["close"].values
        # VIX / VXN prior closes
        self.vix = _daily(os.path.join(ROOT, "data", "VIX_1d.csv"))
        self.vxn = _daily(os.path.join(ROOT, "data", "VXN_1d.csv"))
        ev = pd.read_csv(os.path.join(ROOT, "data", "news", "events.csv"))
        ev = ev[ev["impact"].astype(str).str.strip().str.lower() == "high"]
        self.news = collections.defaultdict(list)
        for d_, tm in zip(ev["date"].astype(str).str.strip(), ev["time_et"].astype(str).str.strip()):
            hh_, mm_ = tm.split(":")
            self.news[d_].append(int(hh_) * 60 + int(mm_))
        self.lit = collections.defaultdict(list)
        for x in M.units()["LIT"]:
            self.lit[x["day"]].append(x)


def _secs(name):
    return {"NQ_5m.csv": 300, "ES_5m.csv": 300, "NQ_15m.csv": 900, "NQ_1h.csv": 3600}[name]


def _daily(path):
    v = pd.read_csv(path)
    return [str(x)[:10] for x in v["date"]], v["close"].astype(float).values


def _prev_daily(D, day, back=1):
    days, cl = D
    k = bisect.bisect_left(days, day) - back
    return float(cl[k]) if k >= 0 else float("nan")


def _bos(h, l, c, k=2):
    """Break-of-structure state per bar: +1 after a close above the last confirmed swing high (fractal k, confirmed k
    bars later), -1 after a close below the last confirmed swing low. Causal."""
    n = len(c)
    st = np.zeros(n)
    sh = sl = None
    s = 0
    for i in range(n):
        j = i - k
        if j - k >= 0:
            if h[j] == max(h[j - k:j + k + 1]):
                sh = h[j]
            if l[j] == min(l[j - k:j + k + 1]):
                sl = l[j]
        if sh is not None and c[i] > sh:
            s = 1; sh = None
        elif sl is not None and c[i] < sl:
            s = -1; sl = None
        st[i] = s
    return st


# fact name -> kind: "s" = sign fact already in trade direction (+1 with / -1 against / 0), "c" = continuous (terciles)
FACTS = {
    "lit_ctx": "s", "lit_won": "s", "took_prev": "s", "monday": "s", "o18_side": "c", "band_room": "c", "bos15": "s",
    "bos60": "s", "pd_pos": "c", "overlap": "s", "t_open": "c", "es_smt": "s", "es_rs": "c", "vwap_side": "c",
    "vwap_dist": "c", "sig_rng": "c", "sig_vol": "c", "atr_reg": "c", "day_rng": "c", "vix": "c", "vix_chg": "c", "vxn": "c",
    "dow0": "s", "dow1": "s", "dow2": "s", "dow3": "s", "dow4": "s", "news_day": "s", "news_before": "s", "pday_trend": "s",
    "ema1h21": "s", "ema15_trend": "s", "risk_atr": "c", "gap": "c",
}


def facts_of(X, t):
    """The facts of one unit t (entry at the open of 5m bar entry_t; every input closed at or before entry_t)."""
    e_t, dr, day = int(t["entry_t"]), int(t["dir"]), t["day"]
    k = int(np.searchsorted(X.t, e_t)) - 1            # the signal bar (closed at entry_t)
    if k < 50:
        return None
    c, a = X.c[k], max(X.atr[k], 1e-6)
    g = X.gid[k]
    first = X.d_first[g]
    o18 = X.d_open[g]
    f = {}
    # LIT context (LIT's trades that entered before this entry; LIT's armed setups that showed before it)
    ctx = [(x["entry_t"], x["dir"]) for x in X.lit.get(day, ()) if x["entry_t"] < e_t]
    ctx += [(a0, d0) for d0, a0, _ in armed_by_day().get(day, ()) if a0 < e_t]
    f["lit_ctx"] = (1 if max(ctx)[1] == dr else -1) if ctx else 0
    won = [x for x in X.lit.get(day, ()) if x["exit_t"] <= e_t]
    f["lit_won"] = (1 if won[-1]["pts"] > 0 else -1) if won else 0
    pdh = X.d_hi[g - 1] if g >= 1 else np.nan
    pdl = X.d_lo[g - 1] if g >= 1 else np.nan
    took_h = X.dhi[k] > pdh
    took_l = X.dlo[k] < pdl
    v = (1 if took_h else 0) * (-dr) + (1 if took_l else 0) * dr
    f["took_prev"] = int(np.sign(v))
    f["monday"] = f["took_prev"] if X.tdow[k] == 0 else 0
    f["o18_side"] = dr * (o18 - c) / a
    vx = _prev_daily(X.vix, day)
    vm = vx / 100.0 / math.sqrt(252.0) * o18 if np.isfinite(vx) else np.nan
    f["band_room"] = (dr * (o18 - c) + vm) / a
    for secs, nm in ((900, "bos15"), (3600, "bos60")):
        H = X.htf[secs]
        j = int(np.searchsorted(H["t"] + secs, e_t, side="right")) - 1
        f[nm] = int(H["bos"][j] * dr) if j >= 0 else 0
        if secs == 3600:
            f["ema1h21"] = int(np.sign(c - H["e21"][j]) * dr) if j >= 0 else 0
        else:
            f["ema15_trend"] = int(np.sign(H["e21"][j] - H["e50"][j]) * dr) if j >= 0 else 0
    rng = X.dhi[k] - X.dlo[k]
    f["pd_pos"] = dr * (0.5 - (c - X.dlo[k]) / rng) if rng > 0 else 0.0
    f["overlap"] = 1 if 480 <= X.mod[k] + 5 < 690 else -1
    m0 = int(X.mod[k]) + 5
    f["t_open"] = -float((m0 - 180) if m0 < 570 else (m0 - 570))
    # ES (2025-04 on): SMT over the last hour vs the 3 hours before; relative strength over the last hour
    ke = int(np.searchsorted(X.es_t, X.t[k], side="right")) - 1
    if ke >= 48 and X.es_t[ke] == X.t[k] and k >= 48:
        nql_r, nql_p = X.l[k - 11:k + 1].min(), X.l[k - 47:k - 11].min()
        nqh_r, nqh_p = X.h[k - 11:k + 1].max(), X.h[k - 47:k - 11].max()
        esl_r, esl_p = X.es_l[ke - 11:ke + 1].min(), X.es_l[ke - 47:ke - 11].min()
        esh_r, esh_p = X.es_h[ke - 11:ke + 1].max(), X.es_h[ke - 47:ke - 11].max()
        bull = nql_r < nql_p and esl_r >= esl_p
        bear = nqh_r > nqh_p and esh_r <= esh_p
        f["es_smt"] = int(dr * ((1 if bull else 0) - (1 if bear else 0)))
        f["es_rs"] = dr * ((X.es_c[ke] / X.es_c[ke - 12] - 1) - (X.c[k] / X.c[k - 12] - 1)) * 1e4
    else:
        f["es_smt"], f["es_rs"] = 0, None
    f["vwap_side"] = dr * (c - X.vwap[k]) / a
    f["vwap_dist"] = abs(c - X.vwap[k]) / a
    f["sig_rng"] = (X.h[k] - X.l[k]) / a
    med = np.median(X.v[max(0, k - 48):k]) if k > 0 else 0
    f["sig_vol"] = X.v[k] / med if med > 0 else None
    f["atr_reg"] = X.atr[k] / X.atr_m[k] if np.isfinite(X.atr_m[k]) and X.atr_m[k] > 0 else None
    f["day_rng"] = rng / X.d_atr[g] if np.isfinite(X.d_atr[g]) and X.d_atr[g] > 0 else None
    f["vix"] = vx if np.isfinite(vx) else None
    v5 = _prev_daily(X.vix, day, 6)
    f["vix_chg"] = vx / v5 - 1 if np.isfinite(vx) and np.isfinite(v5) and v5 > 0 else None
    vn = _prev_daily(X.vxn, day)
    f["vxn"] = vn if np.isfinite(vn) else None
    for w in range(5):
        f[f"dow{w}"] = -1 if X.tdow[k] == w else 0
    ev = X.news.get(day, [])
    f["news_day"] = -1 if ev else 0
    f["news_before"] = -1 if any(x <= m0 for x in ev) and m0 < 1080 else 0
    f["pday_trend"] = int(np.sign(X.d_close[g - 1] - X.d_open[g - 1]) * dr) if g >= 1 else 0
    f["risk_atr"] = t["risk"] / a
    f["gap"] = dr * (o18 - X.d_close[g - 1]) / a if g >= 1 else None
    return {k_: (None if v_ is None or (isinstance(v_, float) and not np.isfinite(v_)) else float(v_)) for k_, v_ in f.items()}


def build_facts(U=None):
    path = os.path.join(CACHE, "atlas_conf_facts.pkl")
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    X = Ctx()
    U = U or raw_units()
    F = {}
    for t in U:
        F[(t["src"], t["entry_t"])] = facts_of(X, t)
    pickle.dump(F, open(path, "wb"))
    return F


def lookahead(n=30, seed=5):
    """Facts recomputed on data cut at each sampled trade's entry (every file cut to bars closed by then) == full data."""
    F = build_facts()
    U = [t for t in raw_units() if t["day"] >= "2025-05-01"] + [t for t in raw_units() if t["day"] < "2025-05-01"][::40]
    rng = np.random.default_rng(seed)
    pick = [U[i] for i in rng.choice(len(U), size=min(n, len(U)), replace=False)]
    same = diff = 0
    bad = []
    for t in pick:
        X = Ctx(cut=int(t["entry_t"]))
        a, b = F[(t["src"], t["entry_t"])], facts_of(X, t)
        ok = all((a[k] is None and b[k] is None) or (a[k] is not None and b[k] is not None and abs(a[k] - b[k]) < 1e-6)
                 for k in FACTS if k not in ("atr_reg",)) and \
            ((a["atr_reg"] is None and b["atr_reg"] is None) or abs((a["atr_reg"] or 0) - (b["atr_reg"] or 0)) < 1e-6)
        same += ok; diff += not ok
        if not ok:
            bad.append((t["src"], t["day"], {k: (a[k], b[k]) for k in FACTS if a[k] != b[k]}))
    print(f"look-ahead: {same} of {same + diff} trades identical on data cut at the entry", flush=True)
    for b_ in bad[:5]:
        print("  DIFF", b_)
    return {"same": same, "n": same + diff, "bad": [str(b_) for b_ in bad]}


# ================================================================================================ confluence family
RULES = {"skip": (0.0, 1.0), "half": (0.5, 1.0), "up125": (1.0, 1.25), "up150": (1.0, 1.5), "tilt": (0.5, 1.5)}
SCOPES = ("ALL",) + NAMES
G = {}                 # worker globals: units, facts, cuts


def _in_scope(t, scope):
    return scope == "ALL" or t["src"] == scope


def span_of(day):
    for s in SPANS:
        a, z = M.SPANS[s]
        if a <= day <= z:
            return s
    return None


def cuts_of(U, F, scope, fact, pol):
    """H1 tercile cut points of a continuous fact (pol-adjusted) over the scope's H1 trades."""
    vals = []
    for t in U:
        f = F.get((t["src"], t["entry_t"]))
        if _in_scope(t, scope) and "2026-01-01" <= t["day"] <= "2026-06-30" and f and f.get(fact) is not None:
            vals.append(pol * f[fact])
    if len(vals) < 15:
        return None
    return float(np.quantile(vals, 1 / 3)), float(np.quantile(vals, 2 / 3))


def cls_of(f, fact, pol, cut):
    if f is None or f.get(fact) is None:
        return 0
    v = pol * f[fact]
    if FACTS[fact] == "s":
        return int(np.sign(v))
    if cut is None:
        return 0
    return 1 if v > cut[1] else (-1 if v < cut[0] else 0)


def apply(U, F, scope, fact, pol, rule, cut=None):
    """Units with the size multiplier m of one confluence rule (+ how many trades it touched)."""
    lo, hi = RULES[rule]
    if FACTS[fact] == "c" and cut is None:
        cut = cuts_of(U, F, scope, fact, pol)
    out, touched = [], 0
    for t in U:
        m = float(t.get("m", 1.0))
        if _in_scope(t, scope):
            c = cls_of(F.get((t["src"], t["entry_t"])), fact, pol, cut)
            k = lo if c < 0 else (hi if c > 0 else 1.0)
            if k != 1.0:
                touched += 1
                m *= k
        out.append({**t, "m": m} if m != float(t.get("m", 1.0)) else t)
    return out, touched


def conf_jobs():
    return [(scope, fact, pol, rule) for scope in SCOPES for fact in FACTS for pol in (1, -1) for rule in RULES]


def _conf_job(j, spans=SPANS):
    scope, fact, pol, rule = j
    V, n = apply(G["U"], G["F"], scope, fact, pol, rule)
    if n == 0:
        return j, None
    with Scorer():
        return j, {"touched": n, "o": score(V, spans)}


def passes(o, base, min_tpw=2.0):
    """The letter of the test: H1 (pick) eval points + $/1000 up by more than 1; H2 (check) eval points and $ not lower;
    2-week fails not up in either half; 2+ trades a week in both halves."""
    b1, b2, x1, x2 = base["H1"], base["H2"], o["H1"], o["H2"]
    s = lambda x: eval_pts(x) + x["net"] / 1000.0
    return bool(s(x1) > s(b1) + 1.0 and eval_pts(x2) >= eval_pts(b2) and x2["net"] >= b2["net"] and x1["f10"] <= b1["f10"]
                and x2["f10"] <= b2["f10"] and x1["tpw"] >= min_tpw and x2["tpw"] >= min_tpw)


def pick_score(o):
    return eval_pts(o["H1"]) + o["H1"]["net"] / 1000.0


def check_gain(o, base):
    return eval_pts(o["H2"]) - eval_pts(base["H2"]) + (o["H2"]["net"] - base["H2"]["net"]) / 1000.0


def shuffled_facts(U, F, seed):
    """Facts permuted across the trades of each span (same values, random owners): the chance level of the test."""
    rng = np.random.default_rng(seed)
    by = collections.defaultdict(list)
    for t in U:
        by[span_of(t["day"])].append((t["src"], t["entry_t"]))
    F2 = dict(F)
    for s, keys in by.items():
        vals = [F.get(k) for k in keys]
        perm = rng.permutation(len(keys))
        for k, p in zip(keys, perm):
            F2[k] = vals[p]
    return F2


def _init(U, F):
    G["U"], G["F"] = U, F


def _conf_job_h(j):
    return _conf_job(j, ("H1", "H2"))


def run_conf(procs=4, shuffles=10):
    from multiprocessing import Pool
    U = base_units()
    F = build_facts()
    with Scorer():
        base = score(U)
    J = conf_jobs()
    t0 = time.time()
    with Pool(procs, initializer=_init, initargs=(U, F)) as pool:
        R = pool.map(_conf_job, J, chunksize=8)
    R = {j: r for j, r in R if r is not None}
    np_ = sum(1 for r in R.values() if passes(r["o"], base))
    print(f"conf: {len(R)} variants ({len(J) - len(R)} touch no trade) in {time.time() - t0:.0f}s; pass {np_}", flush=True)
    sh = []
    for r in range(shuffles):
        F2 = shuffled_facts(U, F, 100 + r)
        with Pool(procs, initializer=_init, initargs=(U, F2)) as pool:
            R2 = pool.map(_conf_job_h, J, chunksize=8)
        R2 = {j: x for j, x in R2 if x is not None}
        P2 = [j for j, x in R2.items() if passes(x["o"], base)]
        sh.append({"n": len(R2), "pass": len(P2), "pass_by_rule": dict(collections.Counter(j[3] for j in P2)),
                   "pass_by_scope": dict(collections.Counter(j[0] for j in P2))})
        print(f"  shuffle {r}: pass {sh[-1]['pass']} of {sh[-1]['n']}", flush=True)
    out = {"base": base, "rows": [{"scope": j[0], "fact": j[1], "pol": j[2], "rule": j[3], **r} for j, r in R.items()],
           "shuffles": sh, "n_tested": len(R)}
    json.dump(out, open(os.path.join(CACHE, "atlas_conf_conf.json"), "w"), default=str)
    return out


def run_shuffles(rounds=10, procs=4, start=0):
    """Chance level of the confluence pass count: the whole family re-run (H1 + H2) on shuffled facts."""
    from multiprocessing import Pool
    path = os.path.join(CACHE, "atlas_conf_conf.json")
    C = json.load(open(path))
    base = C["base"]
    U, F = base_units(), build_facts()
    J = conf_jobs()
    sh = C.get("shuffles") or []
    for r in range(start, start + rounds):
        t0 = time.time()
        F2 = shuffled_facts(U, F, 100 + r)
        with Pool(procs, initializer=_init, initargs=(U, F2)) as pool:
            R2 = pool.map(_conf_job_h, J, chunksize=8)
        R2 = {j: x for j, x in R2 if x is not None}
        P2 = [j for j, x in R2.items() if passes(x["o"], base)]
        sh.append({"seed": 100 + r, "n": len(R2), "pass": len(P2), "pass_by_rule": dict(collections.Counter(j[3] for j in P2)),
                   "pass_by_scope": dict(collections.Counter(j[0] for j in P2)),
                   "best_h1_gain": round(max(pick_score(x["o"]) - pick_score(base) for j, x in R2.items() if passes(x["o"], base)), 2) if P2 else None})
        C["shuffles"] = sh
        json.dump(C, open(path, "w"), default=str)
        print(f"  shuffle {r}: pass {len(P2)} of {len(R2)} ({time.time() - t0:.0f}s)", flush=True)
    return sh


def selection_test(U=None, F=None, min_n=5, rounds=20):
    """Every fact x scope (pol +1): mean R (pts / stop per micro) of WITH trades vs AGAINST trades in H1 and H2. Count of
    facts where one side beats the other in both halves, real vs shuffled facts."""
    U = U or base_units()
    F = F or build_facts()

    def count(FF):
        n_with = n_ag = 0
        rows = []
        for scope in SCOPES:
            for fact in FACTS:
                cut = cuts_of(U, FF, scope, fact, 1) if FACTS[fact] == "c" else None
                res = {}
                for sp in ("H1", "H2"):
                    a, z = M.SPANS[sp]
                    W, A_ = [], []
                    for t in U:
                        if not _in_scope(t, scope) or not (a <= t["day"] <= z):
                            continue
                        c = cls_of(FF.get((t["src"], t["entry_t"])), fact, 1, cut)
                        if c > 0:
                            W.append(t["pts"] / t["risk"])
                        elif c < 0:
                            A_.append(t["pts"] / t["risk"])
                    res[sp] = (float(np.mean(W)) if len(W) >= min_n else None, float(np.mean(A_)) if len(A_) >= min_n else None, len(W), len(A_))
                ok = all(res[s][0] is not None and res[s][1] is not None for s in res)
                w = ok and all(res[s][0] > res[s][1] for s in res)
                g = ok and all(res[s][0] < res[s][1] for s in res)
                n_with += w; n_ag += g
                rows.append({"scope": scope, "fact": fact, "with_better": bool(w), "against_better": bool(g),
                             "res": {s: [None if v is None else round(v, 3) for v in res[s][:2]] + list(res[s][2:]) for s in res}})
        return n_with, n_ag, rows
    real = count(F)
    sh = [count(shuffled_facts(U, F, 500 + r))[:2] for r in range(rounds)]
    return {"real_with": real[0], "real_against": real[1], "rows": real[2],
            "shuffled_with_mean": round(float(np.mean([s[0] for s in sh])), 1),
            "shuffled_against_mean": round(float(np.mean([s[1] for s in sh])), 1),
            "shuffled_with_range": [int(min(s[0] for s in sh)), int(max(s[0] for s in sh))],
            "shuffled_against_range": [int(min(s[1] for s in sh)), int(max(s[1] for s in sh))]}


def placebo(V_real, base, draws=200, seed=7, U=None):
    """Random-pick placebo of a variant: the same multipliers (the variant's m values, shuffled) given to randomly picked
    trades of the same scope. Returns per draw (H1 gain, H2 gain, passes)."""
    U = U or base_units()
    rng = np.random.default_rng(seed)
    ms = [(i, float(v.get("m", 1.0))) for i, v in enumerate(V_real)]
    changed = [m for i, m in ms if m != 1.0]
    srcs = {V_real[i]["src"] for i, m in ms if m != 1.0}
    idx = [i for i, t in enumerate(U) if t["src"] in srcs]
    out = []
    with Scorer():
        for d in range(draws):
            pick = rng.choice(idx, size=min(len(changed), len(idx)), replace=False)
            V = list(U)
            for i, m in zip(pick, rng.permutation(changed)):
                V[i] = {**U[i], "m": float(m)}
            o = score(V, ("H1", "H2"))
            out.append((pick_score(o) - pick_score(base), check_gain(o, base), passes(o, base)))
    return out


# ================================================================================================ risk family (account level)
def risk_jobs():
    J = []
    W = (0.5, 0.75, 1.0, 1.25, 1.5)
    for we in W:
        for wm in W:
            for ws in W:
                if (we, wm, ws) != (1.0, 1.0, 1.0):
                    J.append(("w", {"EMA": we, "MD": wm, "SR": ws}))
    for sub in (("EMA", "MD"), ("EMA", "SR"), ("MD", "SR"), ("EMA",), ("MD",), ("SR",)):
        J.append(("members", list(sub)))
    for o in ({"max_day": 1}, {"after": "win"}, {"after": "loss"}, {"max_day": 3}):
        J.append(("opts", o))
    for k, vals in (("room_f", (0.35, 0.4, 0.45, 0.55, 0.6, 0.7)), ("safe_cap", (0.2, 0.4, 0.5)), ("until", (5, 7, 15, 20)),
                    ("max_usd", (250.0, 350.0, 450.0)), ("need_buf", (0.75, 1.25, 1.5))):
        for v in vals:
            J.append(("knob", {k: v}))
    return J


def _risk_job(j):
    kind, v = j
    U = G["U"]
    knobs, opts = {}, {}
    if kind == "w":
        U = [{**t, "m": v[t["src"]]} if v[t["src"]] != 1.0 else t for t in U]
    elif kind == "members":
        U = [t for t in U if t["src"] in v]
    elif kind == "opts":
        opts = v
    else:
        knobs = v
    with Scorer():
        return j, score(U, knobs=knobs, opts=opts)


def run_risk(procs=4):
    from multiprocessing import Pool
    U = base_units()
    with Scorer():
        base = score(U)
    J = risk_jobs()
    with Pool(procs, initializer=_init, initargs=(U, {})) as pool:
        R = pool.map(_risk_job, J, chunksize=4)
    rows = [{"kind": j[0], "v": j[1], "o": o, "pass": passes(o, base)} for j, o in R]
    out = {"base": base, "rows": rows, "n_tested": len(rows)}
    json.dump(out, open(os.path.join(CACHE, "atlas_conf_risk.json"), "w"), default=str)
    print(f"risk: {len(rows)} variants, pass {sum(r['pass'] for r in rows)}", flush=True)
    return out


# ================================================================================================ member re-runs (exits, stops, entries)
def _cfgS():
    return json.load(open(os.path.join(ROOT, "second_model.json"), encoding="utf-8"))["strategies"]


_RS = {}


def _df5():
    if "df" not in _RS:
        _RS["df"] = _read(os.path.join(ROOT, "data", "NQ_5m.csv"))
    return _RS["df"]


def ema_run(X=None, E=None, lim=False, buf=0.0):
    """tools/second_ema.py trades of the live ema_lon_vix (E / X overrides; lim = its LIT-style limit entry at the CISD level
    for 30 min; buf = stop buf points further beyond the pullback extreme, size follows)."""
    from tools import retail_standalone as RS
    from tools import second_ema as SE
    c = _cfgS()["ema_lon_vix"]
    E = {**c["entry"], **(E or {})}
    X = {**c["exit"], **(X or {})}
    if X.get("tchk") is not None:
        X["tchk"] = tuple(X["tchk"])
    RS.load_frame(_df5(), live_cut=False)
    SE.ENTRY_MODE = "lim" if lim else "mkt"
    SE.D.pop("cand", None)
    d = SE.load()
    df = SE.candidates()
    if buf:
        df = df.copy()
        df["stop"] = df["stop"] - buf
        df["risk"] = df["e"] - df["stop"]
        df = df[(df["risk"] >= SE.MIN_STOP) & (df["risk"] <= SE.MAX_STOP)].reset_index(drop=True)
        SE.D["cand"] = df
    U = SE.trades_of(E, X)
    out = [{k: u[k] for k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit")} | {"exit_kind": str(u["exit_kind"])}
           for u in U if SE.qty("usd500", u["risk_pts"]) > 0]
    SE.ENTRY_MODE = "mkt"
    RS.D.clear()
    return out


def md_run(sim=None, buf=0.0):
    from engine import lit as L_
    from tools import second_md as SM
    c = _cfgS()["macd_sweep"]
    gen, sp, flt = dict(c["gen"]), {**c["sim"], **(sim or {})}, dict(c["flt"])
    if "M" not in _RS:
        _RS["M"] = L_.Market()
        _RS["B1"] = L_.bars_1m(_RS["M"])
        _RS["X"] = SM.Ctx(_RS["M"], _RS["B1"])
        _RS["C"] = SM.md_cands(_RS["X"], **gen)
    X, C = _RS["X"], _RS["C"]
    if buf:
        C = [{**z, "stops": {**z["stops"], "ext": z["stops"]["ext"] - z["dir"] * buf}} for z in C]
    outs = [SM.sim_x(X, z, sp) for z in C]
    T = SM.greedy(X, C, outs, flt["kz"], flt["maxpd"], SM.md_filter(flt))
    out = []
    for z, r in T:
        q = SM.q_usd(500, r["risk"])
        if q <= 0:
            continue
        t = SM.tr_rec(X, z, r, q, "MACD-div")
        out.append({k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind")})
    return out


def sr_run(key=None, buf=0.0):
    from tools import retail_standalone as RS
    from tools import second_sr as SR
    k = {**_cfgS()["sr_nyreclaim"]["key"], **(key or {})}
    RS.load_frame(_df5(), live_cut=False)
    SR.D.clear(); SR._OC.clear()
    SR.data()
    old = SR.gen
    if buf:
        def gen(dd, setup, g, _b=buf):
            return [c[:5] + (c[5] - c[2] * _b,) + tuple(c[6:]) for c in old(dd, setup, g)]
        SR.gen = gen
    try:
        T = SR.run_key(k)
        TT = SR.set_targets(SR.trades_of(T, "usd500", "nyreclaim"), k)
    finally:
        SR.gen = old
    out = [{kk: (float(u[kk]) if kk in ("entry", "stop", "exit") or (kk == "target" and u[kk] is not None) else u[kk])
            for kk in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit")} | {"exit_kind": str(u["exit_kind"])}
           for u in TT if u["day"] >= "2021-11-01"]
    SR.D.clear(); SR._OC.clear(); RS.D.clear()
    return out


MEMBER_VARIANTS = {
    "EMA": [("base", {}), ("tgt2R", {"X": {"tgt": 2.0}}), ("tgt3R", {"X": {"tgt": 3.0}}), ("tgt4R", {"X": {"tgt": 4.0}}),
            ("vk0.75", {"X": {"vk": 0.75}}), ("vk1.25", {"X": {"vk": 1.25}}), ("bank3", {"X": {"bank": 3.0}}),
            ("bank5", {"X": {"bank": 5.0}}), ("minrr2", {"X": {"min_rr": 2.0}}), ("be_off", {"X": {"be": None, "beo": 0.0}}),
            ("be0.5", {"X": {"be": 0.5}}), ("be1.5", {"X": {"be": 1.5}}), ("be_at_entry", {"X": {"beo": 0.0}}),
            ("t15", {"X": {"tchk": (3, 0.3, 0.5)}}), ("part1R", {"X": {"part": (1.0, 0.5)}}),
            ("part1R_t15", {"X": {"part": (1.0, 0.5), "tchk": (3, 0.3, 0.5)}}), ("ride15", {"X": {"ride": "15"}}),
            ("stop+2", {"buf": 2.0}), ("stop+5", {"buf": 5.0}), ("lim", {"lim": True})],
    "MD": [("base", {}), ("tgt2R", {"sim": {"tgt": 2.0}}), ("tgt3R", {"sim": {"tgt": 3.0}}), ("tgt_lvl", {"sim": {"tgt": "lvl"}}),
           ("be1.25", {"sim": {"be": 1.25}}), ("t15_off", {"sim": {"tc": False}}), ("be1.25_t15_off", {"sim": {"be": 1.25, "tc": False}}),
           ("stop+2", {"buf": 2.0}), ("stop+5", {"buf": 5.0}), ("lim", {"sim": {"ent": "lim"}})],
    "SR": [("base", {}), ("tgt3R", {"key": {"tg": 3.0}}), ("tgt_lvl_b3", {"key": {"tg": "lvl", "bk": 3.0}}),
           ("tgt_lvl_b5", {"key": {"tg": "lvl", "bk": 5.0}}), ("tgt_vix_b3", {"key": {"tg": "vix", "bk": 3.0}}),
           ("tgt_vix_b5", {"key": {"tg": "vix", "bk": 5.0}}), ("be1.25", {"key": {"be": 1.25}}), ("t15_off", {"key": {"tc": False}}),
           ("stop+2", {"buf": 2.0}), ("stop+5", {"buf": 5.0}), ("lim", {"key": {"entry": "lim"}})],
}
SETS = os.path.join(CACHE, "atlas_conf_sets.pkl")


def member_sets(force=False):
    """name -> variant -> units (tools/second_robust.units_of on the member's re-run trades). Checks base == stored."""
    from tools import second_robust as SRB
    S = pickle.load(open(SETS, "rb")) if os.path.exists(SETS) and not force else {}
    run = {"EMA": lambda v: ema_run(v.get("X"), v.get("E"), v.get("lim", False), v.get("buf", 0.0)),
           "MD": lambda v: md_run(v.get("sim"), v.get("buf", 0.0)),
           "SR": lambda v: sr_run(v.get("key"), v.get("buf", 0.0))}
    chk = {}
    for nm, VV in MEMBER_VARIANTS.items():
        S.setdefault(nm, {})
        for vn, v in VV:
            if vn in S[nm]:
                continue
            t0 = time.time()
            T = run[nm](v)
            if vn == "base":
                chk[nm] = SRB.same(T, SRB.stored(nm))
                print(f"  {nm} base == stored research trades: {chk[nm]}", flush=True)
            S[nm][vn] = SRB.units_of(T, nm)
            print(f"  {nm} {vn}: {len(T)} trades ({time.time() - t0:.0f}s)", flush=True)
            pickle.dump(S, open(SETS, "wb"))
    return S, chk


def run_members():
    S, chk = member_sets()
    U0 = base_units()
    with Scorer():
        base = score(U0)
        rows = []
        for nm, VV in MEMBER_VARIANTS.items():
            for vn, _ in VV:
                U = base_units({nm: S[nm][vn]})
                o = score(U)
                rows.append({"member": nm, "variant": vn, "o": o, "pass": passes(o, base)})
                f = lambda x: f"{x['p10']}/{x['f10']}/{x['s10']} {x['net']:+,} {x['tpw']}"
                print(f"{nm:3s} {vn:14s} " + " | ".join(f(o[s]) for s in SPANS) + ("  PASS" if rows[-1]["pass"] else ""), flush=True)
    out = {"base": base, "rows": rows, "check": chk, "n_tested": len(rows) - 3}
    json.dump(out, open(os.path.join(CACHE, "atlas_conf_members.json"), "w"), default=str)
    return out


# ================================================================================================ 1m confirmation (2026 only)
ONEM = {"EMA": {"be": 1.0, "beo": 1.25, "tc": False}, "MD": {"be": None, "beo": 0.0, "tc": True},
        "SR": {"be": None, "beo": 0.0, "tc": True}}


def _m1():
    if "m1" not in _RS:
        df = _read(os.path.join(ROOT, "data", "NQ_1m.csv"))
        t = df["time"].values.astype(np.int64)
        et = pd.to_datetime(t, unit="s", utc=True).tz_convert(ET)
        _RS["m1"] = (t, df["open"].values, df["high"].values, df["low"].values, df["close"].values, (et.hour * 60 + et.minute).values)
    return _RS["m1"]


def onem_sim(t0, dr, e_sig, stop, target, rules, mode, wait=20):
    """One trade on 1m bars in a generic simulator. mode "mkt" = market at t0 (the research entry time: the control);
    "c1m" = wait up to `wait` 1m bars from t0 for a 1m CISD (a 1m close beyond the open of the counter-move run that made
    the lowest low since t0, LIT's rule) and enter at the next 1m open; the stop is touched first -> no trade. Stop / target
    prices = the research trade's; breakeven / 15-minute check per member; flat 15:55; costs 1 tick + $1.90 (in units)."""
    T, O, H, L, Cc, MOD = _m1()
    k = int(np.searchsorted(T, t0))
    if k >= len(T) or T[k] != t0:
        return None
    o, h, l, c = (O * dr, H * dr, L * dr, Cc * dr) if dr > 0 else (-O, -L, -H, -Cc)
    sp, tg = stop * dr, target * dr
    if mode == "c1m":
        k0, lowk, ent = k, k, None
        for j in range(k, min(k + wait, len(T) - 1)):
            if MOD[j] >= 935:
                return None
            if l[j] <= sp:
                return None
            if l[j] < l[lowk]:
                lowk = j
            a = lowk
            while a > k0 and c[a - 1] < o[a - 1]:
                a -= 1
            lvl = o[a] if c[lowk] < o[lowk] else None
            if lvl is not None and j > lowk and c[j] > lvl:
                ent = j + 1
                break
        if ent is None:
            return None
        k = ent
    e = o[k] + TICK
    risk = e - sp
    if risk <= 0 or tg - e < 0.25:
        return None
    cur, moved, mfe = sp, False, 0.0
    j = k
    while j < len(T):
        if MOD[j] >= 955 or (j > k and T[j] - T[j - 1] > 3600):
            return {"entry_t": int(T[k]), "exit_t": int(T[j]), "e": e, "x": c[j - 1] - TICK, "kind": "FLAT", "risk": risk}
        if l[j] <= cur:
            px = (min(o[j], cur) if j > k else cur) - TICK
            return {"entry_t": int(T[k]), "exit_t": int(T[j]) + 60, "e": e, "x": px, "kind": "BE" if moved else "STOP", "risk": risk}
        if h[j] >= tg:
            return {"entry_t": int(T[k]), "exit_t": int(T[j]) + 60, "e": e, "x": max(o[j], tg) if j > k else tg, "kind": "TARGET", "risk": risk}
        mfe = max(mfe, h[j] - e)
        if rules["be"] is not None and not moved and h[j] >= e + rules["be"] * risk:
            cur, moved = e + rules["beo"], True
        if rules["tc"] and j - k + 1 == 15 and not moved and mfe < 0.5 * risk and c[j] < e - 0.3 * risk and j + 1 < len(T):
            return {"entry_t": int(T[k]), "exit_t": int(T[j + 1]), "e": e, "x": o[j + 1] - TICK, "kind": "T15", "risk": risk}
        j += 1
    return None


def onem_sets(mode):
    """Each member's research trades with the 2026 ones re-simulated on 1m bars (mode mkt / c1m); earlier trades unchanged."""
    from tools import second_robust as SRB
    out = {}
    for nm in NAMES:
        T0 = SRB.stored(nm)
        T = []
        for t in T0:
            if t["day"] < "2026-01-02":
                T.append(t); continue
            dr = int(t["dir"])
            r = onem_sim(int(t["entry_t"]), dr, float(t["entry"]), float(t["stop"]), float(t["target"]), ONEM[nm], mode)
            if r is None or not (6.0 <= r["risk"] <= 88.0):
                continue
            T.append({"day": t["day"], "entry_t": r["entry_t"], "exit_t": r["exit_t"], "dir": dr, "entry": round(dr * r["e"], 2),
                      "stop": t["stop"], "target": t["target"], "exit": round(dr * r["x"], 2), "exit_kind": r["kind"]})
        out[nm] = SRB.units_of(T, nm)
    return out


def run_onem():
    U0 = base_units()
    rows = []
    with Scorer():
        base = score(U0, ("H1", "H2"))
        for mode in ("mkt", "c1m"):
            S = onem_sets(mode)
            o = score(base_units(S), ("H1", "H2"))
            n26 = {nm: sum(1 for u in S[nm] if u["day"] >= "2026-01-02") for nm in NAMES}
            rows.append({"mode": mode, "o": o, "n2026": n26})
            for nm in NAMES:      # one member at a time on 1m confirmation, the others as researched
                if mode == "c1m":
                    S1 = {nm: S[nm]}
                    rows.append({"mode": f"c1m_{nm}", "o": score(base_units(S1), ("H1", "H2")), "n2026": {nm: n26[nm]}})
    out = {"base": base, "rows": rows}
    json.dump(out, open(os.path.join(CACHE, "atlas_conf_onem.json"), "w"), default=str)
    f = lambda x: f"{x['p10']}/{x['f10']}/{x['s10']} {x['net']:+,} pf {x['pf']} {x['tpw']}"
    print("base", f(base["H1"]), "|", f(base["H2"]))
    for r in rows:
        print(r["mode"], r["n2026"], f(r["o"]["H1"]), "|", f(r["o"]["H2"]))
    return out


# ================================================================================================ final: survivors, chance, combos
def variant_units(v, S=None):
    """A candidate spec -> units. v = {"sets": {member: variant}, "conf": [[scope, fact, pol, rule], ...]}."""
    sets = None
    if v.get("sets"):
        S = S or member_sets()[0]
        sets = {nm: S[nm][vn] for nm, vn in v["sets"].items()}
    U = base_units(sets)
    if v.get("conf"):
        F = build_facts()
        if sets:
            missing = [t for t in U if (t["src"], t["entry_t"]) not in F]
            if missing:
                X = Ctx()
                F = dict(F)
                for t in missing:
                    F[(t["src"], t["entry_t"])] = facts_of(X, t)
        for scope, fact, pol, rule in v["conf"]:
            # the cut points always come from the base trades (the live candidate set), as picked
            cut = cuts_of(base_units(), build_facts(), scope, fact, pol) if FACTS[fact] == "c" else None
            U, _ = apply(U, F, scope, fact, pol, rule, cut)
    return U


def label(v):
    parts = [f"{nm} {vn}" for nm, vn in (v.get("sets") or {}).items()]
    names = {"skip": "skip", "half": "x0.5", "up125": "x1.25", "up150": "x1.5", "tilt": "x0.5 / x1.5"}
    for scope, fact, pol, rule in v.get("conf") or []:
        parts.append(f"{scope} {fact}{'' if pol > 0 else ' (reversed)'} {names[rule]}")
    return " + ".join(parts) or "base"


def _init_base(b):
    G["base"] = b


def _placebo_job(args):
    v, draws = args
    base = G["base"]
    with Scorer():
        o = score(variant_units(v), ("H1", "H2"))
    g1, g2 = pick_score(o) - pick_score(base), check_gain(o, base)
    P = placebo(variant_units(v), base, draws=draws)
    return {"g1": round(g1, 2), "g2": round(g2, 2),
            "p_h1": round(float(np.mean([p[0] >= g1 for p in P])), 3), "p_h2": round(float(np.mean([p[1] >= g2 for p in P])), 3),
            "p_both": round(float(np.mean([p[0] >= g1 and p[1] >= g2 for p in P])), 3),
            "placebo_pass": round(float(np.mean([p[2] for p in P])), 3)}


def final(procs=4, draws=200):
    from multiprocessing import Pool
    C = json.load(open(os.path.join(CACHE, "atlas_conf_conf.json")))
    R = json.load(open(os.path.join(CACHE, "atlas_conf_risk.json")))
    MB = json.load(open(os.path.join(CACHE, "atlas_conf_members.json")))
    base = C["base"]
    rows = C["rows"]
    surv, seen = [], {}
    for r in sorted([r for r in rows if passes(r["o"], base)], key=lambda r: -pick_score(r["o"])):
        sig = json.dumps({s: [r["o"][s][k] for k in ("p10", "f10", "s10", "net")] for s in SPANS})
        v = {"conf": [[r["scope"], r["fact"], r["pol"], r["rule"]]]}
        if sig in seen:
            seen[sig]["aliases"].append(label(v)); continue
        same = [x for x in rows if (x["scope"], x["fact"], x["pol"]) == (r["scope"], r["fact"], r["pol"])]
        c = {"v": v, "label": label(v), "family": "conf", "touched": r["touched"], "aliases": [],
             "plateau": f"{sum(passes(x['o'], base) for x in same)} of {len(same)} rules on this fact pass"}
        seen[sig] = c
        surv.append(c)
    for r in MB["rows"]:
        if r["pass"] and r["variant"] != "part1R_t15":
            surv.append({"v": {"sets": {r["member"]: r["variant"]}}, "label": f"{r['member']} {r['variant']}", "family": "member exit",
                         "aliases": ["EMA part1R_t15 (the partial leg is not modelled by the unit conversion: same trades)"] if r["variant"] == "t15" else [],
                         "plateau": "single variant"})
    print(f"{len(surv)} distinct survivors", flush=True)
    G["base"] = base
    with Pool(procs, initializer=_init_base, initargs=(base,)) as pool:
        P = pool.map(_placebo_job, [(c["v"], draws if c["family"] == "conf" else 0) for c in surv], chunksize=1)
    with Scorer():
        for c, p in zip(surv, P):
            c["chance"] = p if c["family"] == "conf" else {"g1": p["g1"], "g2": p["g2"], "note": "an exit change: no random-pick placebo"}
            c["o"] = score(variant_units(c["v"]), full=True)
            print(f"  {c['label']:45s} g1 {p['g1']:+.1f} g2 {p['g2']:+.1f} p_h2 {p.get('p_h2')} p_both {p.get('p_both')}", flush=True)
        # combos of the distinct survivors (2 and 3 at a time, different facts / members), counted
        combos = []
        S = member_sets()[0]
        cand = surv[:8]
        import itertools
        for k in (2, 3):
            for grp in itertools.combinations(cand, k):
                v = {"conf": [x for c in grp for x in c["v"].get("conf", [])], "sets": {kk: vv for c in grp for kk, vv in (c["v"].get("sets") or {}).items()}}
                facts = [(x[0], x[1]) for x in v["conf"]]
                if len(set(facts)) < len(facts):
                    continue
                o = score(variant_units(v, S))
                combos.append({"v": v, "label": label(v), "o": o, "pass": passes(o, base)})
        combos.sort(key=lambda r: -pick_score(r["o"]))
        bfull = score(base_units(), full=True)
    sh = C.get("shuffles") or []
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base_live_rules": bfull,
           "rules": "account B on a Builder 25K under the live rules: need size (engine/account_b.qty), one position, max 2 a day, "
                    "$600 soft daily loss, stuck under $100 room, never opposite LIT (no entry while LIT holds / has an armed setup "
                    "the other way, closed when LIT enters the other way). Fresh eval every session (20 sessions), back-to-back path $.",
           "test": "pass = H1 eval points (2-week pass - 2 x fail - stuck) + $/1000 up by more than 1; H2 eval points and $ not lower; "
                   "2-week fails not up; 2+ trades a week in both halves",
           "counts": {"conf_tested": C["n_tested"], "conf_pass": sum(1 for r in rows if passes(r["o"], base)),
                      "conf_shuffled_pass_mean": round(float(np.mean([s["pass"] for s in sh])), 1) if sh else None,
                      "conf_shuffled_pass_range": [min(s["pass"] for s in sh), max(s["pass"] for s in sh)] if sh else None,
                      "conf_shuffle_rounds": len(sh),
                      "risk_tested": R["n_tested"], "risk_pass": sum(1 for r in R["rows"] if r["pass"]),
                      "member_tested": MB["n_tested"], "member_pass": sum(1 for r in MB["rows"] if r["pass"]),
                      "combo_tested": len(combos), "combo_pass": sum(1 for r in combos if r["pass"])},
           "survivors": surv, "combos_top": combos[:15],
           "member_rows": [{"member": r["member"], "variant": r["variant"], "o": r["o"], "pass": r["pass"]} for r in MB["rows"]],
           "risk_rows": R["rows"]}
    ck = os.path.join(CACHE, "atlas_conf_checks.json")
    if os.path.exists(ck):
        out["checks"] = json.load(open(ck))
        out["checks"]["selection"].pop("rows", None)
    return out


RULE_TEXT = {
    ("EMA", "day_rng", -1): "EMA: no trade (or x0.5) when the day's range so far (high - low since the 18:00 open, closed 5m bars) is "
                            "more than 0.455 x the average daily range of the 14 sessions before (top third of 2026 H1 EMA trades)",
    ("EMA", "dow3", 1): "EMA: no trade (or x0.5) on Thursdays (trading day = the 18:00 ET session; Wednesday 18:00 - Thursday 17:00)",
    ("EMA", "lit_won", -1): "EMA: no trade once LIT has already closed a WINNER earlier the same day",
    ("SR", "monday", 1): "S/R: LIT's Monday rule - on Mondays, once price took Friday's high only shorts, once it took Friday's low only longs",
    ("MD", "gap", 1): "MACD: x0.5 when the 18:00 open gapped against the trade by more than 0.84 x ATR(14, 5m) vs the prior close",
    ("EMA", "vxn", 1): "EMA: x0.5 when the prior VXN close is under 23.26 (bottom third)",
    ("EMA", "dow1", 1): "EMA: x0.5 on Tuesdays",
    ("MD", "t_open", -1): "MACD: x0.5 when the entry comes within 8 minutes of the session open (03:00 / 09:30 ET)",
    ("EMA", "dow4", -1): "EMA: x1.5 on Fridays",
    ("EMA", "pday_trend", -1): "EMA: x1.5 when the trade goes AGAINST the prior day's direction (18:00 open to close)",
    ("ALL", "atr_reg", 1): "ATLAS: x1.5 when ATR(14, 5m) is above 1.13 x its 20-day average",
    ("ALL", "dow4", -1): "ATLAS: x1.5 on Fridays",
}
SET_TEXT = {("EMA", "t15"): "EMA exit: add LIT's 15-minute check (second_model.json ema_lon_vix exit tchk [3, 0.3, 0.5]: after 3 bars, "
                            "MFE < 0.5R and close < entry - 0.3R -> out at the next open)"}
SAVE = [("atlas_c_base", {}, "ATLAS today under the live account-B rules (incl. LIT armed block)", "info"),
        ("atlas_c_ema_dayrng_skip", {"conf": [["EMA", "day_rng", -1, "skip"]]}, "EMA skipped on big-range days", "promising"),
        ("atlas_c_ema_thu_skip", {"conf": [["EMA", "dow3", 1, "skip"]]}, "EMA skipped on Thursdays", "rejected"),
        ("atlas_c_ema_thu_half", {"conf": [["EMA", "dow3", 1, "half"]]}, "EMA x0.5 on Thursdays", "rejected"),
        ("atlas_c_ema_t15", {"sets": {"EMA": "t15"}}, "EMA with LIT's 15-minute check", "promising"),
        ("atlas_c_ema_litwon_skip", {"conf": [["EMA", "lit_won", -1, "skip"]]}, "EMA skipped after a LIT winner the same day", "rejected"),
        ("atlas_c_sr_monday_skip", {"conf": [["SR", "monday", 1, "skip"]]}, "S/R with LIT's Monday rule", "rejected"),
        ("atlas_c_combo_dayrng_t15", {"conf": [["EMA", "day_rng", -1, "skip"]], "sets": {"EMA": "t15"}},
         "EMA big-range skip + EMA 15-minute check", "promising")]


def write_json(o, extra=None):
    """research/second/atlas_candidates.json (ranked survivors + chance + every family's count; no trade lists)."""
    def slim(x):
        return {s: {k: x[s].get(k) for k in ("p10", "f10", "s10", "p20", "f20", "s20", "pass_med", "p60", "net", "per_month", "pf", "dd", "tpw",
                                               "n", "max_risk", "med_risk", "fund_paid_3m", "ev_eval_3m", "by_src") if k in x[s]} for s in x}
    surv = []
    for rank, c in enumerate(sorted(o["survivors"], key=lambda c: -pick_score(c["o"])), 1):
        v = c["v"]
        changes = [RULE_TEXT.get((x[0], x[1], x[2]), f"{x}") + f" [rule {x[3]}]" for x in v.get("conf", [])]
        changes += [SET_TEXT.get((k, vv), f"{k} {vv}") for k, vv in (v.get("sets") or {}).items()]
        surv.append({"rank": rank, "label": c["label"], "family": c["family"], "spec": v, "changes": changes, "aliases": c["aliases"],
                     "plateau": c["plateau"], "chance": c["chance"], "touched": c.get("touched"),
                     "gain_h1_pts": round(pick_score(c["o"]) - pick_score(o["base_live_rules"]), 2),
                     "gain_h2_pts": round(check_gain(c["o"], o["base_live_rules"]), 2), "score": slim(c["o"])})
    out = {"built": o["built"], "what": "ATLAS (account B, Builder 25K: EMA + MACD + S/R) - confluences, risk changes, entries; "
           "research/writeups/atlas-confluences.md; tools/atlas_conf.py", "rules": o["rules"], "test": o["test"],
           "base_live_rules": slim(o["base_live_rules"]), "counts": o["counts"], "checks": o.get("checks"),
           "survivors": surv, "combos_top": [{"label": c["label"], "spec": c["v"], "pass": c["pass"], "score": slim(c["o"])} for c in o["combos_top"]],
           "members": [{"member": r["member"], "variant": r["variant"], "pass": r["pass"], "score": slim(r["o"])} for r in o["member_rows"]],
           "risk": [{"kind": r["kind"], "v": r["v"], "pass": r["pass"], "score": slim(r["o"])} for r in o["risk_rows"]],
           "verdict": None}
    out.update(extra or {})
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    return out


def save_runs():
    from tools import runlib as rl
    Q = "Owner 2026-10-22 night: progress ATLAS (account B) - a confluence or a risk change, under the live account-B rules"
    sess = [d for d in M.units()["sessions"] if d >= "2021-01-01"]
    S = member_sets()[0]
    with Scorer():
        for rid, v, title, status in SAVE:
            P, o = [], {}
            KNOBS.clear()
            for s in SPANS:
                U = [t for t in variant_units(v, S) if t.get("m", 1.0) > 0]
                KNOBS.clear(); KNOBS["_m"] = 1.0
                o[s], T = AB.score(U, "acctb_need", s, "usd150_safe_dll")
                P += T
            T = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
                  "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0, "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"],
                  "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"], "mfe": None, "mae": None,
                  "bars_held": None, "regime": "", "mult": None, "low": t["low"]} for t in P]
            f = lambda s: (f"{o[s]['tpw']}/wk path {o[s]['net']:+,} (${o[s]['per_month']:,}/mo, PF {o[s]['pf']}) DD {o[s]['dd']:,}; 2-week "
                           f"pass/fail/stuck {o[s]['p10']}/{o[s]['f10']}/{o[s]['s10']}, 1 month {o[s]['p20']}/{o[s]['f20']}; $ per eval {o[s].get('ev_eval_3m')}")
            rl.save(rid, "ATLAS: " + title, "filters" if v.get("conf") else ("management" if v.get("sets") else "other"), Q,
                    params={"spec": v, "label": label(v), "plan": PLAN, "rules": "live account B (no hedge + LIT armed block)"},
                    sizing={"plan": PLAN, "size": "need (engine/account_b.qty)"}, trades=T, scored=rl.score(T, sess), status=status,
                    verdict=f"Builder 25K, fresh eval every session; $ = back-to-back eval path. 2026 H1 (pick) {f('H1')}. H2 (check) {f('H2')}. "
                            f"Reference 2025 {f('2025')}; 2021-24 {f('2021-24')}.",
                    notes="tools/atlas_conf.py; stored trades = the back-to-back eval path of each span.", writeup="atlas-confluences",
                    tags=["second", "account_b", "atlas"])
            print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "base"
    if cmd == "base":
        with Scorer():
            o = score(base_units(), full=True)
        for s in SPANS:
            print(s, {k: o[s][k] for k in ("p10", "f10", "s10", "p20", "f20", "net", "pf", "tpw")})
    elif cmd == "conf":
        run_conf(shuffles=0); run_shuffles(20)
    elif cmd == "risk":
        run_risk()
    elif cmd == "members":
        run_members()
    elif cmd in ("lookahead", "checks"):
        json.dump({"lookahead": lookahead(30), "selection": selection_test()}, open(os.path.join(CACHE, "atlas_conf_checks.json"), "w"), default=str)
    elif cmd == "onem":
        run_onem()
    elif cmd == "final":
        o = final()
        pickle.dump(o, open(os.path.join(CACHE, "atlas_conf_final.pkl"), "wb"))
        write_json(o)
    elif cmd == "save":
        save_runs()
