"""Setup grade A / B / C (night-human 2026-11-18). RESEARCH ONLY: engine/, live_model*.json, second_model.json untouched.

Owner, verbatim: "More accurate with our trades, don't trade like a bot, trade how a person would, without emotion."
Write-up: research/writeups/setup-grade-2026-11-18.md (plain words first).

What a calm, experienced discretionary NQ trader asks before taking a Zlarior (LIT) or ATLAS signal, using only what is on
the chart at that moment (closed 5m bars, the prior days, the VIX close, the news calendar). Never the last trade's result:
no revenge, no fear (nothing here reads P&L, wins, losses or streaks).

THE 7 CHECKS (written down 2026-11-18 before any outcome was looked at; a check that fires = one warning flag):
  trend     higher-timeframe trend against me: the prior session's close vs the SMA of the last 20 session closes (a long
            under it, a short over it).
  level     entering into a key level: the prior day's high / low, the overnight high / low (18:00-09:30 ET, so far), the
            18:00-anchored VWAP or a 100-point round number sits between the entry and 0.5R toward the target (half the
            way to Zlarior's breakeven at 1R, the first goal of the trade).
  extended  the day already moved too far: the range so far (18:00 -> the signal) >= the average daily range of the 14
            sessions before.
  chop      chop: the day so far is an inside day (it has not left the prior day's high-low range).
  news      big news minutes away: a high-impact US release (CPI, jobs, PPI, FOMC, ...; data/news/events.csv) in the next
            30 minutes.
  es        ES does not agree: ES moved against the trade over the last 30 minutes (6 closed 5m bars). ES 5m bars exist
            from 2025-04; before that the check cannot fire (a human without the ES chart).
  vol       volatility not normal: the prior VIX close >= 25 or the prior day's VIX jumped >= 20%.

  Calibration before any outcome (fire rates only, no win / loss looked at): `level` was first written with 1R; it fired
  on 63-75% of all setups (the normal state, not a warning), so it was tightened to 0.5R ("entering INTO a level" = it sits
  within half a stop). With 0-1 / 2+ the C share would have been ~65% (most setups carry 2 warnings), so the cut is set
  from the typical setup instead (below).

THE GRADE: count the flags (every counted check weight 1). m = the median flag count of that strategy's Jan-Jun 2026 trades
  (at least 1): fewer flags than m = A, exactly m = B, more than m = C ("better than a typical setup / typical / worse").
  "all7"   every check counts (the pure checklist, nothing fitted to outcomes).
  "h1"     only the checks that worked on Jan-Jun 2026 count, per strategy: a check is kept when it fires on >= 8 of that
           strategy's Jan-Jun trades and those trades made less R (costs in) than the ones it did not flag. Picked on Jan-Jun
           ONLY; Jul-Oct 2026 and 2021-25 are never looked at to pick.
TWO USES (each strategy, each grade):
  skipC    skip C setups; A and B at today's size.
  size     A at today's size, B at half (x0.5, min 1 micro, inside the size-follows-stop rule and every account cap), C skipped.
A skipped setup leaves the slot free, like a human who passes: Zlarior's day can still take a later setup (engine skip_keys,
as tools/lit_deep.py), ATLAS's one position stays free for the next signal.

HOW A VERSION PASSES (written before the results): the gate (lit_gate / atlas_gate below: better than today in Jan-Jun,
Jul-Oct AND 2021-25, costs in, 2-4 trades a week, eval fails not up) AND random grades with the same A / B / C counts per
span (the luck test) beaten with p <= 0.2 in both checks (Jul-Oct and 2021-25). Zlarior is scored at the LIT size rule, on
the live two_week eval path (room 0.4 to session 80; 2021-25 too) and the funded 50K Monte Carlo; ATLAS on the funded 25K
Monte Carlo at $250 / 30% of the room (tools/atlas_plus 'stack250') and the 25K eval path (tools/atlas_deep.score).

    python -X utf8 tools/setup_grade.py rates     # how often each check fires (no outcomes)
    python -X utf8 tools/setup_grade.py run       # pick on Jan-Jun, score every variant -> research/lab/setup_grade.json
    python -X utf8 tools/setup_grade.py report    # the tables of the write-up from the stored json
    python -X utf8 tools/setup_grade.py register  # the ZEUS Lab entries (kind setup_grade)
    python -X utf8 -m tests.test_setup_grade      # offline checks of the checks themselves (no backtest)
"""
from __future__ import annotations

import bisect
import collections
import csv
import datetime as dt
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
DATE = "2026-11-18"
OUT = os.path.join(ROOT, "research", "lab", "setup_grade.json")
NEWS = os.path.join(ROOT, "data", "news", "events.csv")
ES5 = os.path.join(ROOT, "data", "ES_5m.csv")
CHECKS = ("trend", "level", "extended", "chop", "news", "es", "vol")
WORDS = {"trend": "higher-timeframe trend against the trade (prior close vs its 20-day average)",
         "level": "a key level (prior-day / overnight high-low, VWAP, a 100-point number) within half a stop toward the target",
         "extended": "the day already ran its average daily range",
         "chop": "inside day so far (still inside yesterday's range)",
         "news": "a high-impact US release in the next 30 minutes",
         "es": "ES moved against the trade in the last 30 minutes",
         "vol": "volatility not normal (VIX >= 25 or a +20% VIX jump)"}
SHORT = {"trend": "HTF trend against", "level": "key level within 0.5R", "extended": "day already extended", "chop": "inside day (chop)",
         "news": "news within 30 min", "es": "ES against", "vol": "VIX not normal"}
LEVEL_R = 0.5          # a key level this close toward the target (R) = entering into it (1.0 fired on 63-75%)
ROUND = 100.0          # NQ round numbers
SMA_N, ADR_N = 20, 14
NEWS_MIN = 30
ES_BARS = 6
VIX_HI, VIX_JUMP = 25.0, 0.20
MIN_FIRE_H1 = 8        # a check must fire on this many Jan-Jun trades to be judged at all
B_MULT = 0.5           # B setups at half size in the "size" use
H1 = ("2026-01-01", "2026-06-30")


# ================================================================================================ pure checks (unit-tested)
def n_flags(flags: dict, use=CHECKS) -> int:
    return sum(1 for k in use if flags.get(k))


def grade_of(flags: dict, use=CHECKS, m: int = 1) -> str:
    """Fewer flags than m = A, m = B, more = C (counted checks only, weight 1 each; m >= 1)."""
    m = max(1, int(m))
    n = n_flags(flags, use)
    return "A" if n < m else "B" if n == m else "C"


def typical(counts) -> int:
    """m of the grade: the median flag count of the Jan-Jun trades, at least 1 (rounded down)."""
    c = sorted(int(x) for x in counts)
    if not c:
        return 1
    return max(1, int(math.floor(float(np.median(c)))))


def mult_of(grade: str, mode: str) -> float:
    """Size multiplier of a grade: skipC = A/B 1, C 0; size = A 1, B 0.5, C 0; none = 1."""
    if mode == "none":
        return 1.0
    if grade == "C":
        return 0.0
    if mode == "size" and grade == "B":
        return B_MULT
    return 1.0


def level_flag(d: int, entry: float, risk: float, levels) -> bool:
    """A key level strictly beyond the entry (more than 1 tick) toward the target and within LEVEL_R x risk."""
    if not (risk > 0) or entry != entry:
        return False
    for L in levels:
        if L is None or L != L:
            continue
        dist = (float(L) - entry) * d
        if 0.25 < dist <= LEVEL_R * risk + 1e-9:
            return True
    return False


def next_round(entry: float, d: int, step: float = ROUND) -> float:
    """The next round number beyond the entry toward the target (more than 1 tick away)."""
    if d > 0:
        r = math.ceil((entry + 0.25 + 1e-9) / step) * step
    else:
        r = math.floor((entry - 0.25 - 1e-9) / step) * step
    return float(r)


def checks_from(f: dict) -> dict:
    """Raw facts at the signal -> the 7 flags (True = warning). Missing facts never fire."""
    d = int(f["dir"])
    tr = f.get("trend")
    out = {"trend": bool(tr is not None and tr != 0 and tr * d < 0)}
    out["level"] = level_flag(d, f["entry"], f["risk"], f.get("levels") or [])
    rs, adr = f.get("range_so_far"), f.get("adr")
    out["extended"] = bool(rs is not None and adr is not None and adr == adr and adr > 0 and rs >= adr)
    out["chop"] = bool(f.get("pdh") is not None and f.get("pdl") is not None and f["hi_so_far"] <= f["pdh"] and f["lo_so_far"] >= f["pdl"])
    nm = f.get("news_in")
    out["news"] = bool(nm is not None and 0 < nm <= NEWS_MIN)
    es = f.get("es_move")
    out["es"] = bool(es is not None and es == es and es * d < 0)
    v, v2 = f.get("vix"), f.get("vix2")
    out["vol"] = bool(v is not None and v == v and (v >= VIX_HI or (v2 is not None and v2 == v2 and v2 > 0 and v / v2 - 1.0 >= VIX_JUMP)))
    return out


# ================================================================================================ market facts at a signal
_C = {}


def market():
    """The LIT 5m market (data/NQ_5m.csv via engine/lit.Market, the same object the backtests use) + daily arrays."""
    if "M" not in _C:
        from tools import lit_final as F
        from tools import lit_edge as E
        M, _ = F.market(E.LIVE["ref"], E.LIVE["extra_boxes"])
        prep(M)
    return _C["M"]


def prep(M):
    """Daily arrays of market M (prior days only at each day k): trend = sign of the prior close vs the SMA of the last 20
    closes, adr = mean high-low range of the 14 days before; cumulative price x volume for the 18:00 VWAP; overnight bars."""
    n = len(M.days)
    close = np.array([float(M.c[e - 1]) for _, s, e in M.days])
    rng = np.array([float(M.h[s:e].max() - M.l[s:e].min()) for _, s, e in M.days])
    trend = np.zeros(n)
    adr = np.full(n, np.nan)
    for k in range(n):
        if k >= SMA_N:
            sma = close[k - SMA_N:k].mean()
            trend[k] = 1.0 if close[k - 1] > sma else -1.0 if close[k - 1] < sma else 0.0
        if k >= ADR_N:
            adr[k] = rng[k - ADR_N:k].mean()
    tp = (np.asarray(M.h, float) + np.asarray(M.l, float) + np.asarray(M.c, float)) / 3.0
    v = np.asarray(M.v, float)
    cpv = np.zeros(M.n + 1)
    cv = np.zeros(M.n + 1)
    np.cumsum(tp * v, out=cpv[1:])
    np.cumsum(v, out=cv[1:])
    mod = np.asarray(M.mod)
    on = (mod >= 1080) | (mod < 570)
    _C.update(M=M, trend=trend, adr=adr, cpv=cpv, cv=cv, on=on, dix={str(dd): k for k, (dd, s, e) in enumerate(M.days)})
    return M


def vix_pair():
    """trading day -> (prior VIX close, the close before it): known before the day opens (engine/lit._vix, same file)."""
    if "vix" not in _C:
        from engine import lit
        dd, cc = lit._vix("VIX")
        M = market()
        out = {}
        for d, s, e in M.days:
            j = bisect.bisect_left(dd, str(d)) - 1
            out[str(d)] = (float(cc[j]) if j >= 0 else None, float(cc[j - 1]) if j >= 1 else None)
        _C["vix"] = out
    return _C["vix"]


def news_times():
    """Sorted unix times of the high-impact US releases (data/news/events.csv, ET clock times)."""
    if "news" not in _C:
        ts = []
        try:
            with open(NEWS, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if (r.get("impact") or "").lower() != "high":
                        continue
                    try:
                        hh, mm = (r.get("time_et") or "").split(":")[:2]
                        x = dt.datetime.fromisoformat(r["date"]).replace(hour=int(hh), minute=int(mm), tzinfo=ET)
                    except (ValueError, KeyError):
                        continue
                    ts.append(int(x.timestamp()))
        except OSError:
            pass
        _C["news"] = np.array(sorted(set(ts)), dtype=np.int64)
    return _C["news"]


def es_close():
    """ES 5m closes by bar open time (data/ES_5m.csv, 2025-04 on)."""
    if "es" not in _C:
        out = {}
        try:
            with open(ES5, encoding="utf-8") as fh:
                rd = csv.reader(fh)
                next(rd, None)
                for r in rd:
                    try:
                        out[int(float(r[0]))] = float(r[4])
                    except (ValueError, IndexError):
                        continue
        except OSError:
            pass
        _C["es"] = out
    return _C["es"]


def facts_at(j: int, d: int, entry: float, risk: float) -> dict:
    """Everything the checklist reads, at the close of 5m bar j (the last closed bar at the signal), for a trade in direction
    d (+1 long / -1 short) planned at `entry` with `risk` points to the stop. Closed bars and prior days only."""
    M = market()
    k = int(M.day_of[j])
    day, s, e = M.days[k]
    x = M.ctx[k]
    hi, lo = float(M.h[s:j + 1].max()), float(M.l[s:j + 1].min())
    seg = np.flatnonzero(_C["on"][s:j + 1]) + s
    onh = float(M.h[seg].max()) if len(seg) else None
    onl = float(M.l[seg].min()) if len(seg) else None
    vol = _C["cv"][j + 1] - _C["cv"][s]
    vwap = (_C["cpv"][j + 1] - _C["cpv"][s]) / vol if vol > 0 else None
    t_close = int(M.t[j]) + 300
    nt = news_times()
    q = int(np.searchsorted(nt, t_close, side="right"))
    news_in = (int(nt[q]) - t_close) / 60.0 if q < len(nt) else None
    es = es_close()
    a, b = es.get(int(M.t[j])), es.get(int(M.t[j]) - ES_BARS * 300)
    v, v2 = vix_pair().get(str(day), (None, None))
    levels = [x.get("pdh"), x.get("pdl"), onh, onl, vwap, next_round(entry, d)]
    return {"day": str(day), "dir": int(d), "entry": float(entry), "risk": float(risk), "trend": float(_C["trend"][k]),
            "adr": float(_C["adr"][k]) if _C["adr"][k] == _C["adr"][k] else None, "range_so_far": hi - lo,
            "hi_so_far": hi, "lo_so_far": lo, "pdh": x.get("pdh"), "pdl": x.get("pdl"), "onh": onh, "onl": onl, "vwap": vwap,
            "levels": levels, "news_in": news_in, "es_move": (a - b) if a is not None and b is not None else None,
            "vix": v, "vix2": v2, "t_close": t_close}


# ================================================================================================ Zlarior (LIT) setups
def lit_key(z) -> tuple:
    return (str(z["day"]), int(z["i"]), int(z["dir"]))


def lit_facts() -> dict:
    """Every LIT setup the engine sees (all candidates, not only the traded ones: a skip can free the day for a later one),
    graded at its 5m trigger bar close with the planned entry (min of the CISD level and the trigger close) and stop
    (1 tick beyond the sweep extreme) of tools/lit_deep.cand_feats."""
    if "lit" not in _C:
        from tools import lit_final as F
        from tools import lit_edge as E
        M, C = F.market(E.LIVE["ref"], E.LIVE["extra_boxes"])
        market()
        out = {}
        for z in C:
            d = int(z["dir"])
            ep = min(float(z["ref_d"]), float(z["trig_c"]))
            risk = ep - (float(z["ext_d"]) - float(E.LIVE["stop_buf"]))
            f = facts_at(int(z["i"]), d, ep * d, risk)
            f["flags"] = checks_from(f)
            out[lit_key(z)] = f
        _C["lit"] = out
    return _C["lit"]


# ================================================================================================ ATLAS signals
def atlas_key(u) -> tuple:
    return (str(u["src"]), int(u["entry_t"]))


def atlas_facts(U) -> dict:
    """Every ATLAS account candidate (tools/atlas.account_units: members after the no-hedge rules), graded at the close of the
    5m signal bar (the entry is the next 5m open), entry = that open, risk = the unit's stop distance."""
    M = market()
    out = {}
    for u in U:
        j = int(np.searchsorted(M.t, int(u["entry_t"]))) - 1          # the last bar that opened before the entry bar
        if j < 0 or int(M.t[j]) + 300 != int(u["entry_t"]):
            j = int(np.searchsorted(M.t, int(u["entry_t"]) - 300, side="right")) - 1
        nx = j + 1 if j + 1 < M.n else j
        entry = float(M.o[nx])
        f = facts_at(j, int(u["dir"]), entry, float(u["risk"]))
        f["flags"] = checks_from(f)
        out[atlas_key(u)] = f
    return out


# ================================================================================================ scoring (real backtests)
SP_LIT = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
SP_ATL = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
          "2021-24": ("2021-01-01", "2024-12-31")}
ROOM_F, UNTIL = 0.4, 80          # owner-approved eval sizing: two_week room_f 0.4 kept to session 80 (CLAUDE.md)
ATLAS_USD = 250.0                # ATLAS's funded sizing in the research ($250 / 30% of the room, tools/atlas_plus.py)


def span_lit(d: str) -> str:
    return next((k for k, (a, z) in SP_LIT.items() if a <= d <= z), "")


def span_atl(d: str) -> str:
    return next((k for k, (a, z) in SP_ATL.items() if a <= d <= z), "")


def setup():
    """The live eval sizing (two_week room 0.4 to session 80) + the eval path's session list widened to 2021-25 so the same
    back-to-back / fresh-start / Monte Carlo eval scoring also runs on 2021-25 (H1 / H2 unchanged: checked in `run`)."""
    if _C.get("setup"):
        return
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    from tools import lit_adv_manage as LA
    from tools import lit_final as F
    from tools import lit_edge as E  # noqa: F401  (patches LA.run_eval with the tilt-aware run_eval_m)
    LA.CFG = {**LA.CFG, "two_week": {**LA.CFG["two_week"], "room_f": ROOM_F}, "two_week_until": UNTIL}
    LA.S26 = list(F.SESS)
    LA.SPANS["2021-25"] = SP_LIT["2021-25"]
    LA._MC.clear()
    _C["setup"] = True


def eval_ref(U) -> dict:
    """The live two_week eval path on 2021-25 (tools/lit_rev_exit.eval_path with the widened session list)."""
    from tools import lit_rev_exit as R
    return R.eval_path([u for u in U if u["day"] <= SP_LIT["2021-25"][1]], "2021-25")


def lit_score(skip=None, mult=None, fund=False, ref_eval=True):
    """Zlarior with grade-skipped setups (engine skip_keys: the day stays free) and size multipliers per setup key, through
    tools/lit_edge.evaluate (LIT size rule + the live two_week eval path, costs in) + the 2021-25 eval path."""
    setup()
    from tools import lit_edge as E
    from tools import lit_final as F
    T = F.run({**E.LIVE, "skip_keys": [list(k) for k in sorted(skip)]}) if skip else E.ctx()["T"]
    mfn = (lambda t, r: float(mult.get((str(t["day"]), int(t["i"]), int(t["dir"])), 1.0))) if mult else None
    o, U, L = E.evaluate(T=T, mfn=mfn, fund=fund)
    if ref_eval:
        o["eval"]["2021-25"] = eval_ref(U)
    return o, U, L, T


_A = {}


def atlas_ctx():
    """ATLAS candidates (account units: members after the no-hedge rules incl. LIT's armed setups) + the funded 25K tools."""
    if not _A:
        setup()
        sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
        import builder_levers as BL
        import stack_one_account as SA
        from tools import atlas as A
        from tools import atlas_revive as R
        from tools import uprisk as UP
        _A["U"] = A.account_units(A.BASE)
        _A["S"] = SA.data()["S"]
        _A["PF"] = {sp: UP.mc_paths(_A["S"], sp, 600, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
        _A["WGF"] = R._wgf()
        _A.update(BL=BL, R=R, UP=UP)
    return _A


def atlas_funded_units(mult):
    """tools/atlas_revive.variant_units with the grade: a skipped (m 0) signal is dropped BEFORE ATLAS's one position / max 2
    a day (the slot stays free), a B signal keeps its slot at weight m (engine/account_b.funded_qty x w, min 1)."""
    X = atlas_ctx()
    U = [u for u in X["U"] if float(mult.get(atlas_key(u), 1.0)) > 0]
    out = []
    for t in X["R"].one_pos(U):
        out.append({"day": t["day"], "risk": float(t["risk"]), "tgt": float(t["tgt"] or 0) or None, "pts": float(t["pts"]),
                    "w1": float(min(0.0, t["w1"])), "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
                    "strat": "ATLAS", "src": t["src"], "w": float(mult.get(atlas_key(t), 1.0))})
    return out


def atlas_score(mult, name="sg"):
    """ATLAS with the grade: the 25K eval path (tools/atlas_deep.score = the real account-B rules; m 0 = not traded, the slot
    stays free; m 0.5 = half the need size, min 1, the day guard) + the funded 25K Monte Carlo at $250 / 30% of the room
    (tools/atlas_plus 'stack250': 600 paths x 126 sessions, MFFU builder25k funded rules) + every trade at a fixed $250."""
    X = atlas_ctx()
    from tools import atlas_deep as D
    um = {k: float(m) for k, m in mult.items() if abs(float(m) - 1.0) > 1e-9}
    D._UM[name] = um
    try:
        ev = D.score(D.V_of({"um": name} if um else {}))
    finally:
        D._UM.pop(name, None)
    T = atlas_funded_units(mult)
    BY = X["R"].by_session(T, X["S"])
    z = {"ATLAS": ("stack", ATLAS_USD, 0.3)}
    fu = {sp: {"funded": X["BL"].funded_run(BY, X["PF"][sp], lambda z=z: X["WGF"]("builder25k", X["UP"].UP25, z)),
               "fixed": X["R"].fixed_stats(T, X["S"], sp)} for sp in X["BL"].SPANS}
    return {"eval": ev, "funded": fu}, T


def atlas_fixed_pnl(t) -> float:
    """One ATLAS trade at a fixed $250 x its weight, costs in (tools/atlas_revive.fixed_stats)."""
    from tools import second_mix as M
    loss1 = (t["risk"] + M.SLIP) * M.PV + M.ECOMM
    q = int(ATLAS_USD * float(t.get("w", 1.0)) // loss1)
    return q * (t["pts"] * M.PV - M.ECOMM)


# ================================================================================================ the pick (Jan-Jun 2026 only)
def pick(rows) -> dict:
    """rows = [(day, flags, R)] of one strategy's executed trades (costs in). Per check on Jan-Jun 2026 ONLY: fires n,
    mean R when it fires / when it does not; kept = fires >= MIN_FIRE_H1 and less R when it fires. + the cut m per grade."""
    H = [(f, r) for d, f, r in rows if H1[0] <= d <= H1[1]]
    per, keep = {}, []
    for c in CHECKS:
        a = [r for f, r in H if f.get(c)]
        b = [r for f, r in H if not f.get(c)]
        ma = float(np.mean(a)) if a else None
        mb = float(np.mean(b)) if b else None
        ok = len(a) >= MIN_FIRE_H1 and ma is not None and mb is not None and ma < mb
        per[c] = {"fires": len(a), "share": round(100.0 * len(a) / max(1, len(H)), 1), "r_fires": None if ma is None else round(ma, 3),
                  "r_not": None if mb is None else round(mb, 3), "kept": bool(ok)}
        if ok:
            keep.append(c)
    cut = {"all7": typical(n_flags(f, CHECKS) for f, _ in H), "h1": typical(n_flags(f, keep) for f, _ in H)}
    return {"n_h1": len(H), "per_check": per, "keep": keep, "m": cut}


def uses_of(P) -> dict:
    return {"all7": list(CHECKS), "h1": list(P["keep"])}


def r_stats(R, P=None) -> dict:
    R = np.array(R, float)
    if not len(R):
        return {"n": 0}
    o = {"n": int(len(R)), "win": round(100.0 * float((R > 0).mean()), 1), "avg_r": round(float(R.mean()), 3)}
    if P is not None:
        P = np.array(P, float)
        g, l_ = P[P > 0].sum(), -P[P < 0].sum()
        o.update(pf=round(float(g / l_), 2) if l_ > 0 else None, usd=round(float(P.sum())))
    return o


# ================================================================================================ the run
def _j(o):
    """numpy-safe json default."""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, tuple):
        return list(o)
    return str(o)


def lit_gate(s, base) -> tuple:
    """Zlarior: the repo's LIT gate (tools/lit_edge.gate: more $ at the LIT size AND on the eval path in Jan-Jun and Jul-Oct,
    2-week fails not up, 2+ trades a week) + the same on 2021-25 (LIT size, eval path, fails) + at most 4 trades a week
    (or today's count). Returns (ok, why)."""
    from tools import lit_edge as E
    why = []
    for h, nm in (("H1", "Jan-Jun (pick)"), ("H2", "Jul-Oct (check)"), ("2021-25", "2021-25 (check)")):
        dl = s["lit"][h]["net"] - base["lit"][h]["net"]
        de = s["eval"][h]["net"] - base["eval"][h]["net"]
        df = s["eval"][h]["f10"] - base["eval"][h]["f10"]
        if dl <= 0:
            why.append(f"{nm}: {money(dl)} at the Zlarior size")
        if de <= 0:
            why.append(f"{nm}: {money(de)} on the eval path")
        if df > 0:
            why.append(f"{nm}: 2-week fails +{df:.1f} pts")
    hi = max(4.0, max(base["lit"][h]["tpw"] for h in ("H1", "H2")))
    for h in ("H1", "H2"):
        t = s["lit"][h]["tpw"]
        if not (2.0 <= t <= hi + 1e-9):
            why.append(f"{h} {t} trades a week (rule 2-4)")
    ok = not why and E.gate({**s, "d_lit": {h: s["lit"][h]["net"] - base["lit"][h]["net"] for h in s["lit"]},
                             "d_eval": {h: s["eval"][h]["net"] - base["eval"][h]["net"] for h in s["eval"]},
                             "d_f10": {h: round(s["eval"][h]["f10"] - base["eval"][h]["f10"], 1) for h in s["eval"]}})
    return ok, "; ".join(why)


def atlas_gate(r, b) -> tuple:
    """ATLAS: the funded 25K gate of tools/atlas_revive.passes ($ a month up in both 2026 halves, no-payout / first payout not
    worse, 2021-25 not lower, 2-4 trades a week) + the 25K eval path: back-to-back money (after the $43 fees) up in Jul-Oct and
    in 2021-25 (2025 + 2021-24), 2-week passes not down and dead evals not up in Jul-Oct."""
    from tools import atlas_revive as R
    from tools import atlas_v2 as V2
    why = []
    F, Fb = r["funded"], b["funded"]
    for sp, nm in (("H1", "Jan-Jun (pick)"), ("H2", "Jul-Oct (check)"), ("REF", "2021-25 (check)")):
        dm = F[sp]["funded"]["per_month"] - Fb[sp]["funded"]["per_month"]
        if dm <= 0 if sp != "REF" else dm < 0:
            why.append(f"{nm}: funded 25K {money(dm)} a month")
    for sp, nm in (("H1", "Jan-Jun"), ("H2", "Jul-Oct")):
        if F[sp]["funded"]["no_pay_6m"] > Fb[sp]["funded"]["no_pay_6m"] + 0.5:
            why.append(f"{nm}: no payout in 6 months {Fb[sp]['funded']['no_pay_6m']} -> {F[sp]['funded']['no_pay_6m']}%")
        t = F[sp]["fixed"]["tpw"]
        if not (2.0 <= t <= max(4.0, Fb[sp]["fixed"]["tpw"] + 0.1)):
            why.append(f"{nm} {t} trades a week (rule 2-4)")
    E, Eb = r["eval"], b["eval"]
    MO = V2.MONEY
    de2 = E["H2"][MO] - Eb["H2"][MO]
    deref = (E["2025"][MO] + E["2021-24"][MO]) - (Eb["2025"][MO] + Eb["2021-24"][MO])
    if de2 <= 0:
        why.append(f"Jul-Oct: eval path {money(de2)}")
    if deref <= 0:
        why.append(f"2021-25: eval path {money(deref)}")
    if E["H2"]["p10"] < Eb["H2"]["p10"]:
        why.append(f"Jul-Oct: 2-week eval passes {Eb['H2']['p10']} -> {E['H2']['p10']}%")
    if E["H2"]["dead10"] > Eb["H2"]["dead10"]:
        why.append(f"Jul-Oct: dead evals {Eb['H2']['dead10']} -> {E['H2']['dead10']}%")
    ok = not why and R.passes(F, Fb)
    if not why and not ok:
        why.append("funded first payout later")
    return ok, "; ".join(why)


def money(x) -> str:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "-"
    return ("-" if x < 0 else "+") + f"${abs(x):,.0f}"


def lit_short(o, base=None):
    from tools import lit_edge as E
    s = E.short(o, base)
    s["eval_ref"] = {k: o["eval"]["2021-25"].get(k) for k in ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10", "dec10",
                                                              "pass_med", "b2b")}
    return s


def atlas_short(r):
    from tools import atlas_v2 as V2
    E = r["eval"]
    keys = ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10", "dead10", "pass_med", "sig_tpw", V2.MONEY, "b2b")
    return {"eval": {sp: {k: E[sp].get(k) for k in keys} for sp in E},
            "funded": {sp: {"funded": dict(r["funded"][sp]["funded"]), "fixed": dict(r["funded"][sp]["fixed"])} for sp in r["funded"]}}


def lit_grades(LF, uses, m):
    return {v: {k: grade_of(f["flags"], uses[v], m[v]) for k, f in LF.items()} for v in uses}


def variant_maps(G, use):
    """grades {key: A/B/C} + use -> (skip set, mult map)."""
    skip = {k for k, g in G.items() if g == "C"}
    mult = {k: B_MULT for k, g in G.items() if g == "B"} if use == "size" else {}
    return skip, mult


def by_grade(rows) -> dict:
    """rows = [(span, grade, R, usd)] -> span -> grade -> stats."""
    out = collections.defaultdict(dict)
    sps = sorted({r[0] for r in rows})
    for sp in sps:
        for g in ("A", "B", "C"):
            X = [r for r in rows if r[0] == sp and r[1] == g]
            out[sp][g] = r_stats([x[2] for x in X], [x[3] for x in X])
    return dict(out)


def lit_placebo(base_T, G, use, real, n=100, seed=11):
    """Random grades with the same counts on the traded setups of each span: n draws (skip the 'C' ones, the day stays free;
    'B' at x0.5 for the size use). Share of draws with at least the real $ per span (LIT size; eval path for 2026)."""
    rng = np.random.default_rng(seed)
    keys = {sp: [] for sp in SP_LIT}
    lab = {sp: collections.Counter() for sp in SP_LIT}
    for t in base_T:
        sp = span_lit(t["day"])
        if not sp:
            continue
        k = (str(t["day"]), int(t["i"]), int(t["dir"]))
        keys[sp].append(k)
        lab[sp][G.get(k, "A")] += 1
    beat = collections.Counter()
    for _ in range(n):
        skip, mult = set(), {}
        for sp, ks in keys.items():
            ix = rng.permutation(len(ks))
            nc, nb = lab[sp]["C"], lab[sp]["B"] if use == "size" else 0
            skip |= {ks[i] for i in ix[:nc]}
            mult.update({ks[i]: B_MULT for i in ix[nc:nc + nb]})
        o, U, L, T = lit_score(skip=skip, mult=mult, ref_eval=False)
        for sp in SP_LIT:
            if o["lit"][sp]["net"] >= real["lit"][sp]["net"]:
                beat["lit:" + sp] += 1
        for sp in ("H1", "H2"):
            if o["eval"][sp]["net"] >= real["eval"][sp]["net"]:
                beat["eval:" + sp] += 1
    return {k: round((beat[k] + 1) / (n + 1), 3) for k in [f"lit:{sp}" for sp in SP_LIT] + ["eval:H1", "eval:H2"]} | {"draws": n}


def atlas_placebo(G, use, real, n=30, seed=11):
    """Random grades with the same counts on ATLAS's candidates of each span (2021-25 = one pool): funded $ a month per span
    and eval-path money per span, share of draws at least as good as the real grade."""
    from tools import atlas_v2 as V2
    X = atlas_ctx()
    rng = np.random.default_rng(seed)
    pools = collections.defaultdict(list)
    for u in X["U"]:
        sp = span_atl(u["day"])
        pools["REF" if sp in ("2025", "2021-24") else sp].append(atlas_key(u))
    cnt = {sp: collections.Counter(G.get(k, "A") for k in ks) for sp, ks in pools.items()}
    beat = collections.Counter()
    MO = V2.MONEY
    for j in range(n):
        mult = {}
        for sp, ks in pools.items():
            ix = rng.permutation(len(ks))
            nc, nb = cnt[sp]["C"], cnt[sp]["B"] if use == "size" else 0
            mult.update({ks[i]: 0.0 for i in ix[:nc]})
            mult.update({ks[i]: B_MULT for i in ix[nc:nc + nb]})
        r, _ = atlas_score(mult, name=f"sg_pl{j}")
        for sp in ("H1", "H2", "REF"):
            if r["funded"][sp]["funded"]["per_month"] >= real["funded"][sp]["funded"]["per_month"]:
                beat["funded:" + sp] += 1
        for sp in ("H1", "H2"):
            if r["eval"][sp][MO] >= real["eval"][sp][MO]:
                beat["eval:" + sp] += 1
        if r["eval"]["2025"][MO] + r["eval"]["2021-24"][MO] >= real["eval"]["2025"][MO] + real["eval"]["2021-24"][MO]:
            beat["eval:REF"] += 1
    return {k: round((beat[k] + 1) / (n + 1), 3) for k in ("funded:H1", "funded:H2", "funded:REF", "eval:H1", "eval:H2", "eval:REF")} | {"draws": n}


def _signflip(D, sp_fn):
    from tools import zeus_lab as Z
    return {h: Z.signflip_p([d["usd"] for d in D if sp_fn(d["day"]) == h], 4000) for h in ("H1", "H2")}


def lit_part(res, n_pl=100, log=print):
    from tools import lit_edge as E
    from tools import zeus_lab as Z
    import time
    t0 = time.time()
    LF = lit_facts()
    o0, U0, L0, T0 = lit_score(fund=True)
    s0 = lit_short(o0)
    key_of_t = {int(t["entry_t"]): (str(t["day"]), int(t["i"]), int(t["dir"])) for t in T0}
    Lb = {int(l["entry_t"]): l for l in L0}
    rows = [(t["day"], LF[key_of_t[int(t["entry_t"])]]["flags"], float(Lb[int(t["entry_t"])]["r"])) for t in T0]
    P = pick(rows)
    uses = uses_of(P)
    G = lit_grades(LF, uses, P["m"])
    out = {"base": s0, "pick": P, "uses": uses, "rates": {}, "grades": {}, "per_check_oos": {}, "variants": {}, "singles": {}}
    for sp in SP_LIT:
        X = [(t, LF[key_of_t[int(t["entry_t"])]]) for t in T0 if span_lit(t["day"]) == sp]
        out["rates"][sp] = {"n": len(X), **{c: round(100.0 * sum(f["flags"][c] for _, f in X) / max(1, len(X)), 1) for c in CHECKS},
                            "flags_mean": round(float(np.mean([n_flags(f["flags"]) for _, f in X])), 2) if X else None}
        for c in CHECKS:
            a = [float(Lb[int(t["entry_t"])]["r"]) for t, f in X if f["flags"][c]]
            b = [float(Lb[int(t["entry_t"])]["r"]) for t, f in X if not f["flags"][c]]
            out["per_check_oos"].setdefault(c, {})[sp] = {"fires": r_stats(a), "not": r_stats(b)}
    for ver in uses:
        gr = [(span_lit(t["day"]), G[ver][key_of_t[int(t["entry_t"])]], float(Lb[int(t["entry_t"])]["r"]),
               float(Lb[int(t["entry_t"])]["pnl"])) for t in T0 if span_lit(t["day"])]
        out["grades"][ver] = by_grade(gr)
    log(f"Zlarior: base + facts {time.time() - t0:.0f}s; keep {P['keep']} m {P['m']}")
    log(E.line("base", s0))
    for ver in ("h1", "all7"):
        for use in ("skipC", "size"):
            skip, mult = variant_maps(G[ver], use)
            o, U, L, T = lit_score(skip=skip, mult=mult, fund=True)
            s = lit_short(o, o0)
            ok, why = lit_gate(s, s0)
            D = Z._lit_deltas(L, L0)
            flip = _signflip(D, span_lit)
            hits = collections.Counter(span_lit(d["day"]) for d in D)
            nm = f"{ver}:{use}"
            out["variants"][nm] = {"s": s, "ok": ok, "why": why, "flip": flip, "hits": dict(hits), "deltas": D,
                                   "skipped_traded": dict(collections.Counter(span_lit(t["day"]) for t in T0
                                                                              if G[ver][key_of_t[int(t["entry_t"])]] == "C"))}
            log(E.line(nm, s) + f" | ref eval {s['eval_ref']['net']:+,} 2w {s['eval_ref']['p10']}/{s['eval_ref']['f10']} | "
                f"{'PASS' if ok else 'no'}: {why[:160]}")
    for c in CHECKS:
        skip = {k for k, f in LF.items() if f["flags"][c]}
        o, U, L, T = lit_score(skip=skip)
        s = lit_short(o, o0)
        out["singles"][c] = {"d_lit": s["d_lit"], "d_eval": s["d_eval"], "d_f10": s["d_f10"],
                             "lit_pm": {h: s["lit"][h]["per_month"] - s0["lit"][h]["per_month"] for h in SP_LIT},
                             "eval_pm": {h: s["eval"][h]["per_month"] - s0["eval"][h]["per_month"] for h in s["eval"]},
                             "tpw": {h: s["lit"][h]["tpw"] for h in SP_LIT}}
        log(f"  single skip {c:9s} dLIT $/mo " + " / ".join(f"{out['singles'][c]['lit_pm'][h]:+}" for h in SP_LIT) +
            "  dEVAL $/mo " + " / ".join(f"{out['singles'][c]['eval_pm'][h]:+}" for h in SP_LIT) +
            "  tpw " + " / ".join(str(out['singles'][c]['tpw'][h]) for h in SP_LIT))
    for nm, v in out["variants"].items():
        if not v["ok"]:
            v["placebo"] = None                      # the gate failed: no luck test needed
            continue
        ver, use = nm.split(":")
        if n_pl:
            t1 = time.time()
            v["placebo"] = lit_placebo(T0, G[ver], use, v["s"], n=n_pl)
            log(f"  placebo {nm}: {v['placebo']} ({time.time() - t1:.0f}s)")
        v["robust"] = lit_robust(LF, uses[ver], P["m"][ver], use, o0, s0, T0, key_of_t, log=log)
    res["lit"] = out
    return out


def regrade(LF, use, m, level_r=None, cut=None):
    """Grades with another check set / level distance / C cut (the robustness rows; nothing here picks)."""
    G = {}
    for k, f in LF.items():
        fl = f["flags"]
        if level_r is not None:
            fl = {**fl, "level": _level_at(f, level_r)}
        n = n_flags(fl, use)
        mm = max(1, int(m))
        c = mm + 1 if cut is None else int(cut)
        G[k] = "A" if n < mm else "C" if n >= c else "B"
    return G


def _level_at(f, r):
    global LEVEL_R
    keep = LEVEL_R
    try:
        LEVEL_R = float(r)
        return level_flag(f["dir"], f["entry"], f["risk"], f.get("levels") or [])
    finally:
        LEVEL_R = keep


def lit_robust(LF, use, m, mode, o0, s0, T0, key_of_t, log=print):
    """For a gate passer: leave one check out (m re-set from the Jan-Jun flag counts of the 6 left), the first-written level
    distance (1R) and a stricter C (m + 2 flags). Shown, never used to pick."""
    out = {}
    H = [key_of_t[int(t["entry_t"])] for t in T0 if H1[0] <= t["day"] <= H1[1]]

    def score(G, nm):
        skip, mult = variant_maps(G, mode)
        o, U, L, T = lit_score(skip=skip, mult=mult)
        s = lit_short(o, o0)
        ok, why = lit_gate(s, s0)
        out[nm] = {"d_lit_pm": {h: s["lit"][h]["per_month"] - s0["lit"][h]["per_month"] for h in SP_LIT},
                   "d_eval_pm": {h: s["eval"][h]["per_month"] - s0["eval"][h]["per_month"] for h in s["eval"]},
                   "tpw": {h: s["lit"][h]["tpw"] for h in SP_LIT}, "p10": {h: s["eval"][h]["p10"] for h in s["eval"]},
                   "f10": {h: s["eval"][h]["f10"] for h in s["eval"]}, "gate": ok}
        log(f"  robust {nm:22s} dLIT $/mo " + " / ".join(f"{out[nm]['d_lit_pm'][h]:+}" for h in SP_LIT) + "  dEVAL $/mo " +
            " / ".join(f"{out[nm]['d_eval_pm'][h]:+}" for h in SP_LIT) + f"  {'GATE' if ok else ''}")
    for c in use:
        u2 = [x for x in use if x != c]
        m2 = typical(n_flags(LF[k]["flags"], u2) for k in H)
        score(regrade(LF, u2, m2), f"without {c}")
    lv = [{**LF[k]["flags"], "level": _level_at(LF[k], 1.0)} for k in H]
    score(regrade(LF, use, typical(n_flags(f, use) for f in lv), level_r=1.0), "level at 1R (first draft)")
    score(regrade(LF, use, m, cut=max(1, int(m)) + 2), "stricter C (m + 2 flags)")
    return out


def atlas_part(res, n_pl=30, log=print):
    from tools import atlas_deep as D
    import time
    t0 = time.time()
    X = atlas_ctx()
    AF = atlas_facts(X["U"])
    r0, T0 = atlas_score({})
    b0 = atlas_short(r0)
    rows = [(t["day"], AF[atlas_key(t)]["flags"], float(D.r_net(t))) for t in T0]
    P = pick(rows)
    uses = uses_of(P)
    G = {v: {k: grade_of(f["flags"], uses[v], P["m"][v]) for k, f in AF.items()} for v in uses}
    out = {"base": b0, "pick": P, "uses": uses, "rates": {}, "grades": {}, "per_check_oos": {}, "variants": {}, "singles": {}}
    for sp in SP_ATL:
        Xs = [(t, AF[atlas_key(t)]) for t in T0 if span_atl(t["day"]) == sp]
        out["rates"][sp] = {"n": len(Xs), **{c: round(100.0 * sum(f["flags"][c] for _, f in Xs) / max(1, len(Xs)), 1) for c in CHECKS},
                            "flags_mean": round(float(np.mean([n_flags(f["flags"]) for _, f in Xs])), 2) if Xs else None}
        for c in CHECKS:
            a = [float(D.r_net(t)) for t, f in Xs if f["flags"][c]]
            b = [float(D.r_net(t)) for t, f in Xs if not f["flags"][c]]
            out["per_check_oos"].setdefault(c, {})[sp] = {"fires": r_stats(a), "not": r_stats(b)}
    for ver in uses:
        gr = [(span_atl(t["day"]), G[ver][atlas_key(t)], float(D.r_net(t)), atlas_fixed_pnl(t)) for t in T0 if span_atl(t["day"])]
        out["grades"][ver] = by_grade(gr)
    log(f"ATLAS: base + facts {time.time() - t0:.0f}s; keep {P['keep']} m {P['m']}")
    log("ATLAS base " + aline(b0))

    def day_usd(T):
        by = collections.defaultdict(float)
        for t in T:
            by[t["day"]] += atlas_fixed_pnl(t)
        return by
    d0 = day_usd(T0)
    for ver in ("h1", "all7"):
        for use in ("skipC", "size"):
            mult = {k: (0.0 if g == "C" else B_MULT if (g == "B" and use == "size") else 1.0) for k, g in G[ver].items()}
            mult = {k: m for k, m in mult.items() if m != 1.0}
            r, T = atlas_score(mult, name=f"sg_{ver}_{use}")
            b = atlas_short(r)
            ok, why = atlas_gate(r, r0)
            d1 = day_usd(T)
            DD = [{"day": d, "t": f"atlas:{d}", "usd": round(d1.get(d, 0.0) - d0.get(d, 0.0), 2)} for d in sorted(set(d0) | set(d1))
                  if abs(d1.get(d, 0.0) - d0.get(d, 0.0)) > 1e-9]
            flip = _signflip(DD, lambda d: "H1" if H1[0] <= d <= H1[1] else "H2" if d >= "2026-07-01" else "REF")
            nm = f"{ver}:{use}"
            out["variants"][nm] = {"s": b, "ok": ok, "why": why, "flip": flip, "deltas": DD, "mult": None,
                                   "hits": dict(collections.Counter(span_atl(d["day"]) for d in DD)),
                                   "skipped_traded": dict(collections.Counter(span_atl(t["day"]) for t in T0 if G[ver][atlas_key(t)] == "C"))}
            out["variants"][nm]["_mult"] = mult
            log(f"ATLAS {nm:11s} " + aline(b) + f" | {'PASS' if ok else 'no'}: {why[:160]}")
    for c in CHECKS:
        mult = {k: 0.0 for k, f in AF.items() if f["flags"][c]}
        r, T = atlas_score(mult, name=f"sg_single_{c}")
        b = atlas_short(r)
        out["singles"][c] = {"funded_pm": {sp: b["funded"][sp]["funded"]["per_month"] - b0["funded"][sp]["funded"]["per_month"] for sp in b["funded"]},
                             "eval_money": {sp: b["eval"][sp][MONEY_A()] - b0["eval"][sp][MONEY_A()] for sp in b["eval"]},
                             "tpw": {sp: b["funded"][sp]["fixed"]["tpw"] for sp in b["funded"]}}
        log(f"  single skip {c:9s} dFUNDED $/mo " + " / ".join(f"{out['singles'][c]['funded_pm'][sp]:+}" for sp in ("H1", "H2", "REF")) +
            "  dEVAL $ " + " / ".join(f"{out['singles'][c]['eval_money'][sp]:+,}" for sp in SP_ATL) +
            "  tpw " + " / ".join(str(out['singles'][c]['tpw'][sp]) for sp in ("H1", "H2", "REF")))
    for nm, v in out["variants"].items():
        if not v["ok"]:
            v["placebo"] = None                      # the gate failed: no luck test needed
            continue
        ver, use = nm.split(":")
        if n_pl:
            t1 = time.time()
            r_real = {"funded": {sp: {"funded": v["s"]["funded"][sp]["funded"]} for sp in v["s"]["funded"]}, "eval": v["s"]["eval"]}
            v["placebo"] = atlas_placebo(G[ver], use, r_real, n=n_pl)
            log(f"  placebo ATLAS {nm}: {v['placebo']} ({time.time() - t1:.0f}s)")
    for v in out["variants"].values():
        v.pop("_mult", None)
    res["atlas"] = out
    return out


def MONEY_A():
    from tools import atlas_v2 as V2
    return V2.MONEY


def aline(b) -> str:
    F, E = b["funded"], b["eval"]
    MO = MONEY_A()
    return (" | ".join(f"{sp} fund ${F[sp]['funded']['per_month']}/mo 1st {F[sp]['funded']['first_med']} nopay {F[sp]['funded']['no_pay_6m']}% "
                       f"{F[sp]['fixed']['tpw']}/wk PF {F[sp]['fixed']['pf']}" for sp in ("H1", "H2", "REF")) + " || eval " +
            " | ".join(f"{sp} 2w {E[sp]['p10']}/{E[sp]['f10']} dead {E[sp]['dead10']} ${E[sp][MO]:+,}" for sp in SP_ATL))


def cmd_run(n_lit=100, n_atl=30, log=print, only=None):
    import time
    t0 = time.time()
    setup()
    res = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) and only else {}
    res.update({"date": DATE, "checks": {c: WORDS[c] for c in CHECKS},
                "params": {"level_r": LEVEL_R, "round": ROUND, "sma_n": SMA_N, "adr_n": ADR_N, "news_min": NEWS_MIN, "es_bars": ES_BARS,
                           "vix_hi": VIX_HI, "vix_jump": VIX_JUMP, "min_fire_h1": MIN_FIRE_H1, "b_mult": B_MULT, "room_f": ROOM_F,
                           "two_week_until": UNTIL, "atlas_usd": ATLAS_USD}})
    if only in (None, "lit"):
        lit_part(res, n_pl=n_lit, log=log)
    if only in (None, "atlas"):
        atlas_part(res, n_pl=n_atl, log=log)
    res["verdict"] = verdict(res)
    trim(res)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=_j)
    log(f"wrote {os.path.relpath(OUT, ROOT)} in {time.time() - t0:.0f}s")
    return res


def trim(res) -> dict:
    """Keep the per-trade / per-day $ changes of 2026 only (the Lab's sign-flip and forward shadow use 2026 and later)."""
    for bot in ("lit", "atlas"):
        for v in ((res.get(bot) or {}).get("variants") or {}).values():
            v["deltas"] = [d for d in (v.get("deltas") or []) if str(d.get("day", "")) >= "2026-01-01"]
    return res


def verdict(res) -> dict:
    """Per strategy: does any pre-declared variant pass (gate + random-grade placebo p <= 0.2 in both checks)?"""
    out = {}
    for bot in ("lit", "atlas"):
        o = res.get(bot)
        if not o:
            continue
        rows = {}
        for nm, v in o["variants"].items():
            pl = v.get("placebo") or {}
            if bot == "lit":
                luck = [pl.get("lit:H2", 1.0), pl.get("lit:2021-25", 1.0)]
            else:
                luck = [pl.get("funded:H2", 1.0), pl.get("funded:REF", 1.0)]
            rows[nm] = {"gate": v["ok"], "placebo_ok": bool(pl) and max(luck) <= 0.2, "pass": bool(v["ok"] and pl and max(luck) <= 0.2)}
        out[bot] = {"rows": rows, "passers": [k for k, r in rows.items() if r["pass"]]}
    return out


# ================================================================================================ ZEUS Lab (kind setup_grade)
LAB_VARIANT = {"lit": "all7:skipC", "atlas": "all7:skipC"}   # the same rule on both bots (the pure checklist, skip C)
LAB_CELLS = 11                                                # 4 grade variants + 7 single checks tried per bot


def _lit_head(s) -> dict:
    out = {h: {k: s["lit"][h][k] for k in ("n", "tpw", "pf", "net", "per_month", "dd")} for h in s["lit"]}
    for h, e in s["eval"].items():
        out.setdefault(h, {})["eval"] = {k: e.get(k) for k in ("net", "per_month", "p10", "f10", "dec10", "p15", "f15", "slow_pass", "pass_med")}
    return out


def _atlas_head(b) -> dict:
    F, E = b["funded"], b["eval"]
    h = {}
    for sp in ("H1", "H2"):
        x = F[sp]["fixed"]
        h[sp] = {"per_month": F[sp]["funded"]["per_month"], "n": x["n"], "tpw": x["tpw"], "pf": x["pf"], "net": x["net"], "dd": x["max_dd"],
                 "first_med": F[sp]["funded"]["first_med"], "no_pay_6m": F[sp]["funded"]["no_pay_6m"],
                 "p10": E[sp]["p10"], "f10": E[sp]["f10"], "pass_med": E[sp]["pass_med"]}
    for sp in ("2025", "2021-24"):
        x = F["REF"]["fixed"]
        h[sp] = {"per_month": F["REF"]["funded"]["per_month"], "n": x["n"], "tpw": x["tpw"], "pf": x["pf"], "net": x["net"], "dd": x["max_dd"],
                 "p10": E[sp]["p10"], "f10": E[sp]["f10"], "pass_med": E[sp]["pass_med"]}
    return h


def lab_result(e: dict, path: str = OUT) -> dict:
    """ZEUS Lab runner for kind setup_grade: the stored verdict of this tool (research/lab/setup_grade.json; rerun
    `python -X utf8 tools/setup_grade.py run` for new bars). proof_ok = the gate (better in Jan-Jun, Jul-Oct and 2021-25,
    costs in, 2-4 trades a week, eval fails not up) AND random grades with the same A/B/C counts beaten (p <= 0.2 in both
    checks). The Lab adds its sign-flip / many-tests guard on top."""
    o = json.load(open(path, encoding="utf-8"))
    bot = e["bot"]
    nm = e.get("variant") or LAB_VARIANT[bot]
    B = o[bot]
    v = B["variants"][nm]
    row = o["verdict"][bot]["rows"][nm]
    if bot == "lit":
        head, base = _lit_head(v["s"]), _lit_head(B["base"])
        by = {h: round(v["s"]["lit"][h]["per_month"] - B["base"]["lit"][h]["per_month"]) for h in ("H1", "H2", "2021-25")}
    else:
        head, base = _atlas_head(v["s"]), _atlas_head(B["base"])
        by = {sp: round(v["s"]["funded"][sp]["funded"]["per_month"] - B["base"]["funded"][sp]["funded"]["per_month"]) for sp in ("H1", "H2")}
        by["2021-25"] = round(v["s"]["funded"]["REF"]["funded"]["per_month"] - B["base"]["funded"]["REF"]["funded"]["per_month"])
    why = v["why"]
    pl = v.get("placebo")
    if v["ok"] and pl:
        k = ("lit:H2", "lit:2021-25") if bot == "lit" else ("funded:H2", "funded:REF")
        if not row["placebo_ok"]:
            why = (f"better in Jan-Jun, Jul-Oct and 2021-25, but could be luck: random skips of as many setups do as well "
                   f"(Jul-Oct p {pl[k[0]]}, 2021-25 p {pl[k[1]]}; needs <= 0.2 in both), and it flips to a loss with the "
                   f"first-draft level distance or a stricter C")
        else:
            why = f"better in Jan-Jun, Jul-Oct and 2021-25; beats random grades (p {pl[k[0]]} / {pl[k[1]]})"
    return {"proof_ok": bool(row["pass"]), "why": why or "-", "flip": v.get("flip") or {"H1": 1.0, "H2": 1.0}, "head": head, "base": base,
            "deltas": v.get("deltas") or [], "usd_month_by": by, "hits": v.get("hits")}


WHAT = {"lit": "Before each Zlarior setup, count 7 human warnings (trend against, a level within half a stop, day already "
               "extended, inside day, news in 30 min, ES against, VIX not normal); skip the setup when it has more warnings "
               "than a typical one (3+ of 7), the day stays free for a later setup.",
        "atlas": "Before each ATLAS signal, count the same 7 human warnings; skip the signal when it has more warnings than a "
                 "typical one (3+ of 7), the slot stays free for the next signal."}
HYP = ("A calm discretionary trader passes on setups where several things are against him at once (higher-timeframe trend, a "
       "level in the way, a spent day, chop, news, ES, an abnormal VIX), without ever looking at his last result.")


def cmd_register(log=print):
    """One ZEUS Lab experiment per bot (kind setup_grade, cells = every variant tried) through tools/zeus_lab.register."""
    from tools import zeus_lab as Z
    for bot in ("lit", "atlas"):
        nm = {"lit": "Zlarior", "atlas": "ATLAS"}[bot]
        e = {"id": f"setup_grade_{bot}", "bot": bot, "kind": "setup_grade", "variant": LAB_VARIANT[bot], "cells": LAB_CELLS,
             "registered": DATE, "origin": "claude", "source": "research/writeups/setup-grade-2026-11-18.md (tools/setup_grade.py)",
             "title": f"{nm}: human setup grade - skip C setups (more warnings than a typical setup)", "what_changes": WHAT[bot],
             "hypothesis": HYP, "judged_by": "setup_grade"}
        err = Z.register(e)
        log(f"{e['id']}: {'saved' if not err else err}")
    return 0


def cmd_report(log=print):
    """The write-up tables (markdown) from the stored json."""
    o = json.load(open(OUT, encoding="utf-8"))
    L, A_ = o.get("lit"), o.get("atlas")
    f = lambda x: "-" if x is None else f"{x:,}" if isinstance(x, int) else f"{x}"
    if L:
        log("\n### Zlarior: how often each check fires (% of trades)\n")
        log("| Span | trades | " + " | ".join(SHORT[c] for c in CHECKS) + " |")
        log("|---|---|" + "---|" * len(CHECKS))
        for sp, r in L["rates"].items():
            log(f"| {sp} | {r['n']} | " + " | ".join(f"{r[c]}" for c in CHECKS) + " |")
    for nm, B in (("Zlarior", L), ("ATLAS", A_)):
        if not B:
            continue
        log(f"\n### {nm}: the Jan-Jun pick (R a trade, costs in)\n")
        log("| Check | fires (Jan-Jun) | R when it fires | R when it does not | kept |")
        log("|---|---|---|---|---|")
        for c, x in B["pick"]["per_check"].items():
            log(f"| {SHORT[c]} | {x['fires']} ({x['share']}%) | {f(x['r_fires'])} | {f(x['r_not'])} | {'yes' if x['kept'] else 'no'} |")
        log(f"\nkept: {B['pick']['keep']}, typical flag count m: {B['pick']['m']}")
        log(f"\n### {nm}: each check out of sample (R a trade when it fires / when it does not, n fires)\n")
        sps = [sp for sp in (list(SP_LIT) + list(SP_ATL)) if sp in next(iter(B["per_check_oos"].values()))]
        sps = list(dict.fromkeys(sps))
        log("| Check | " + " | ".join(sps) + " |")
        log("|---|" + "---|" * len(sps))
        for c, x in B["per_check_oos"].items():
            cells = []
            for sp in sps:
                a_, b_ = x[sp]["fires"], x[sp]["not"]
                cells.append("-" if not a_.get("n") else f"{a_['avg_r']:+.2f} / {b_.get('avg_r', 0):+.2f} (n {a_['n']})")
            log(f"| {SHORT[c]} | " + " | ".join(cells) + " |")
        for ver in ("all7", "h1"):
            log(f"\n### {nm}: grade {ver} on today's trades (win %, PF, $)\n")
            log("| Span | A n / win / PF / $ | B n / win / PF / $ | C n / win / PF / $ |")
            log("|---|---|---|---|")
            order = [sp for sp in (list(SP_LIT) + list(SP_ATL)) if sp in B["grades"][ver]]
            for sp in dict.fromkeys(order):
                G = B["grades"][ver][sp]
                cell = lambda g: "0" if not G[g].get("n") else f"{G[g]['n']} / {G[g]['win']}% / {f(G[g].get('pf'))} / {money(G[g].get('usd'))}"
                log(f"| {sp} | {cell('A')} | {cell('B')} | {cell('C')} |")
    if L:
        log("\n### Zlarior variants\n")
        log("| Version | trades/wk H1 / H2 / 21-25 | PF H1 / H2 / 21-25 | net $ (Zlarior size) H1 / H2 / 21-25 | $/month H1 / H2 / 21-25 | "
            "max DD H1 / H2 / 21-25 | eval $/month H1 / H2 / 21-25 | 2-week pass/fail H1, H2, 21-25 | sessions to pass (median) H1 / H2 / 21-25 | "
            "funded 50K $/mo H1 / H2 / 21-25 | gate | luck p (H2 / 21-25) |")
        log("|---|---|---|---|---|---|---|---|---|---|---|---|")
        rows = [("today", {"s": L["base"], "ok": None, "placebo": None})] + list(L["variants"].items())
        for nm, v in rows:
            s_ = v["s"]
            li, ev, fu = s_["lit"], s_["eval"], s_.get("fund") or {}
            sp3 = ("H1", "H2", "2021-25")
            pl = v.get("placebo") or {}
            log(f"| {nm} | " + " / ".join(f(li[h]["tpw"]) for h in sp3) + " | " + " / ".join(f(li[h]["pf"]) for h in sp3) + " | " +
                " / ".join(money(li[h]["net"]) for h in sp3) + " | " +
                " / ".join(money(li[h]["per_month"]) for h in sp3) + " | " + " / ".join(money(li[h]["dd"]) for h in sp3) + " | " +
                " / ".join(money(ev[h]["per_month"]) for h in sp3) + " | " + ", ".join(f"{ev[h]['p10']}/{ev[h]['f10']}" for h in sp3) + " | " +
                " / ".join(f(ev[h].get("pass_med")) for h in sp3) + " | " +
                " / ".join(money((fu.get(h if h != "2021-25" else "REF") or {}).get("per_month")) for h in sp3) + " | " +
                ("-" if v["ok"] is None else "PASS" if v["ok"] else "no") + " | " +
                (f"{pl.get('lit:H2')} / {pl.get('lit:2021-25')}" if pl else "-") + " |")
        log("\n### Zlarior: each check alone as a skip ($/month change at the Zlarior size; eval path)\n")
        log("| Check | Zlarior size H1 / H2 / 21-25 | eval path H1 / H2 / 21-25 | trades/wk H1 / H2 / 21-25 |")
        log("|---|---|---|---|")
        for c, x in L["singles"].items():
            log(f"| {SHORT[c]} | " + " / ".join(money(x["lit_pm"][h]) for h in SP_LIT) + " | " + " / ".join(money(x["eval_pm"][h]) for h in SP_LIT) +
                " | " + " / ".join(f(x["tpw"][h]) for h in SP_LIT) + " |")
        for nm, v in L["variants"].items():
            if v.get("robust"):
                log(f"\n### Zlarior {nm}: robustness ($/month change vs today)\n")
                log("| Version | Zlarior size H1 / H2 / 21-25 | eval path H1 / H2 / 21-25 | trades/wk H1 / H2 | gate |")
                log("|---|---|---|---|---|")
                for k, x in v["robust"].items():
                    log(f"| {k} | " + " / ".join(money(x["d_lit_pm"][h]) for h in SP_LIT) + " | " + " / ".join(money(x["d_eval_pm"][h]) for h in SP_LIT) +
                        f" | {x['tpw']['H1']} / {x['tpw']['H2']} | {'PASS' if x['gate'] else 'no'} |")
    if A_:
        log("\n### ATLAS variants (funded 25K at $250 / 30% of the room; 25K eval path)\n")
        log("| Version | trades/wk H1 / H2 / 21-25 | PF ($250) H1 / H2 / 21-25 | net $ ($250) H1 / H2 / 21-25 | funded $/month H1 / H2 / 21-25 | "
            "1st payout (sessions) H1 / H2 | no payout 6 mo H1 / H2 | max DD ($250) H1 / H2 / 21-25 | eval 2-week pass/fail H1, H2, 2025, 2021-24 | "
            "eval $ H1 / H2 / 2025 / 2021-24 | gate |")
        log("|---|---|---|---|---|---|---|---|---|---|---|")
        MO = MONEY_A()
        rows = [("today", {"s": A_["base"], "ok": None})] + list(A_["variants"].items())
        for nm, v in rows:
            F_, E_ = v["s"]["funded"], v["s"]["eval"]
            sp3 = ("H1", "H2", "REF")
            log(f"| {nm} | " + " / ".join(f(F_[h]["fixed"]["tpw"]) for h in sp3) + " | " + " / ".join(f(F_[h]["fixed"]["pf"]) for h in sp3) + " | " +
                " / ".join(money(F_[h]["fixed"]["net"]) for h in sp3) + " | " +
                " / ".join(money(F_[h]["funded"]["per_month"]) for h in sp3) + " | " + " / ".join(f(F_[h]["funded"]["first_med"]) for h in ("H1", "H2")) +
                " | " + " / ".join(f"{F_[h]['funded']['no_pay_6m']}%" for h in ("H1", "H2")) + " | " +
                " / ".join(money(F_[h]["fixed"]["max_dd"]) for h in sp3) + " | " + ", ".join(f"{E_[h]['p10']}/{E_[h]['f10']}" for h in SP_ATL) + " | " +
                " / ".join(money(E_[h][MO]) for h in SP_ATL) + " | " + ("-" if v["ok"] is None else "PASS" if v["ok"] else "no") + " |")
        log("\n### ATLAS: each check alone as a skip (funded $/month change; eval $ change)\n")
        log("| Check | funded H1 / H2 / 21-25 | eval H1 / H2 / 2025 / 2021-24 | trades/wk H1 / H2 / 21-25 |")
        log("|---|---|---|---|")
        for c, x in A_["singles"].items():
            log(f"| {SHORT[c]} | " + " / ".join(money(x["funded_pm"][h]) for h in ("H1", "H2", "REF")) + " | " +
                " / ".join(money(x["eval_money"][h]) for h in SP_ATL) + " | " + " / ".join(f(x["tpw"][h]) for h in ("H1", "H2", "REF")) + " |")
        log("\n### ATLAS: how often each check fires (% of trades)\n")
        log("| Span | trades | " + " | ".join(SHORT[c] for c in CHECKS) + " |")
        log("|---|---|" + "---|" * len(CHECKS))
        for sp, r in A_["rates"].items():
            log(f"| {sp} | {r['n']} | " + " | ".join(f"{r[c]}" for c in CHECKS) + " |")
    log("\nverdict: " + json.dumps(o.get("verdict")))
    return 0


def cmd_rates(log=print):
    """How often each check fires on the executed trades (no outcomes)."""
    setup()
    from tools import lit_edge as E
    LF = lit_facts()
    T = E.ctx()["T"]
    for sp in SP_LIT:
        X = [LF[(str(t["day"]), int(t["i"]), int(t["dir"]))] for t in T if span_lit(t["day"]) == sp]
        log(f"Zlarior {sp:8s} n {len(X):4d} " + " ".join(f"{c} {100.0 * sum(f['flags'][c] for f in X) / max(1, len(X)):.0f}%" for c in CHECKS))
    X_ = atlas_ctx()
    AF = atlas_facts(X_["U"])
    T = X_["R"].one_pos(X_["U"])
    for sp in SP_ATL:
        X = [AF[atlas_key(t)] for t in T if span_atl(t["day"]) == sp]
        log(f"ATLAS   {sp:8s} n {len(X):4d} " + " ".join(f"{c} {100.0 * sum(f['flags'][c] for f in X) / max(1, len(X)):.0f}%" for c in CHECKS))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "help"
    if cmd == "rates":
        return cmd_rates()
    if cmd == "run":
        only = argv[1] if len(argv) > 1 and argv[1] in ("lit", "atlas") else None
        n_lit = int(os.environ.get("SG_PL_LIT", "200"))
        n_atl = int(os.environ.get("SG_PL_ATLAS", "30"))
        cmd_run(n_lit, n_atl, only=only)
        return 0
    if cmd == "report":
        return cmd_report()
    if cmd == "register":
        return cmd_register()
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
