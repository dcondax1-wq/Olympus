"""Risk & sizing research: "learn from its losses" (family "risk" in the run library, research/runs/).

The owner's question: is the bot risking too much (losses wipe out what it earned) or not enough for the situation?
This script answers it on the exact live-loop replay (tools/runlib.replay, costs included) and stores every experiment
as a run (tools/runlib.save) so the dashboard can list and open them. Write-ups: research/writeups/.

  python tools/research_risk.py all           # every run below (engine replays are cached; first time ~1 h on 2 procs)
  python tools/research_risk.py check         # self-tests: sizing + eval simulator reproduce runlib and the engine
  python tools/research_risk.py anatomy       # A  loss anatomy (markdown tables printed) + counterfactual info runs
  python tools/research_risk.py levels        # B1 risk level x0.5 ... x1.5 (post-hoc, confirmed by engine replays)
  python tools/research_risk.py refstop       # B2 wide-stop scaling: risk_ref_stop 15/20/25/30/40/off + shape
  python tools/research_risk.py cold          # B3 cold-streak filter variants + hot-streak boost
  python tools/research_risk.py ddaware       # B4 account drawdown-aware sizing
  python tools/research_risk.py eval          # B5 MFFU eval-aware sizing (own eval simulator, state at entry)
  python tools/research_risk.py situational   # B6 one-factor situational sizing (picked on 2021-25, checked on 2026)
  python tools/research_risk.py weekly        # B7 weekly loss brake, loss-streak cuts
  python tools/research_risk.py summary       # print every risk run's headline numbers

Method
  * Sizing is re-done from the engine's own rule, not by scaling integer micros: the engine's sizing stop (signal close to
    stop, `risk_pts_plan`) is reconstructed for every trade so that int(risk$ // (stop x $2)) gives back exactly the
    recorded micros (checked on all 768 trades), then any new $ risk is turned into micros the way engine/model._size does
    (max 40 micros; fewer than 1 micro = the engine skips the setup). The cold-streak half size is then applied the way the
    live loop does (max(1, int(micros x 0.5))). P&L, commission and slippage are linear in micros, so the re-sized P&L is
    exact. Engine replays (runlib.replay with risk_usd / risk_ref_stop) confirm the post-hoc numbers.
  * No look-ahead: a rule sees only the trade's setup fields and trades that FINISHED before it entered (the shadow record
    of every signal for the streak filters; the sized account or the eval account for equity rules). Never the trade's own
    r / pnl / mfe / mae / bars_held / exit.
  * Evals: own simulator mirroring engine/analytics.simulate_eval (MFFU Builder 50K: +$3,000 target, $2,000 end-of-day
    trailing max loss checked intraday against the worst open P&L, locking at $50,100), plus the soft $1,000 daily loss
    limit of engine/risk_policy.EvalAccount (it never binds at the live size; it matters only above ~$1,000 a trade).
    For fixed sizing it reproduces runlib.score exactly. Eval-aware rules size every trade from that eval's own state
    (cushion above the trailing floor, profit, distance to the target, days in), for every rolling start.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

WRITEUPS = "research/writeups"
PLAN = {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 50100.0, "dll": 1000.0}
BASE_RISK, BASE_REF, MAX_MICROS = 800.0, 20.0, rl.MAX_MICROS
SPANS = rl.SPANS
LIVE_COLD = {"lookback": 15, "thr": 0.0, "size": 0.5}
_ET = None


def et(ts):
    global _ET
    if _ET is None:
        from zoneinfo import ZoneInfo
        _ET = ZoneInfo("America/New_York")
    return dt.datetime.fromtimestamp(int(ts), _ET)


# ------------------------------------------------------------------------------------------------ engine sizing stop
def plan_interval(t, risk_usd=BASE_RISK, ref=BASE_REF, cap=MAX_MICROS):
    """Feasible (lo, hi] for the engine's sizing stop (risk_pts_plan) given the recorded micros and the conf tags
    ("wide stop X pts: risk $Y" is written before the trending-regime half)."""
    q0 = int(t["qty"]); tf = 0.5 if t.get("regime") == "trending" else 1.0
    Y = P = None
    for tag in t.get("conf_tags") or []:
        m = re.match(r"wide stop (\d+) pts: risk \$(\d+)", str(tag))
        if m:
            P, Y = float(m.group(1)), float(m.group(2))
    ivs = []
    if Y is not None and ref:
        k = risk_usd * ref * tf / 2.0                       # micros = int(risk_usd*ref/plan*tf // (2 plan))
        ivs.append(((k / (q0 + 1)) ** 0.5 if q0 < cap else 0.0, (k / q0) ** 0.5))
        ivs.append((risk_usd * ref / (Y + 0.5), risk_usd * ref / (Y - 0.5)))
        ivs.append((P - 0.5, P + 0.5))
        ivs.append((ref, 1e9))
    else:
        k = risk_usd * tf / 2.0
        ivs.append((k / (q0 + 1) if q0 < cap else 0.0, k / q0))
        if ref:
            ivs.append((0.0, ref))
    lo = max(a for a, b in ivs); hi = min(b for a, b in ivs)
    if lo >= hi:
        lo, hi = ivs[0]
    return lo, hi


def est_plan(t, risk_usd=BASE_RISK, ref=BASE_REF):
    lo, hi = plan_interval(t, risk_usd, ref)
    eps = 1e-7 * max(1.0, hi)
    return min(max(float(t["risk_pts"]), lo + eps), hi - eps)


def comm(q):
    """Engine commission for q micros routed as contract "auto" (engine/model._finalize, engine/instruments): every 10
    micros go as 1 NQ ($4.50 round turn), the rest as MNQ ($1.50 each)."""
    return (q // 10) * 4.50 + (q % 10) * 1.50


def pnl_of(t, q, qe):
    """$ result of trade t when the engine sizes qe micros and the live loop routes q of them (the live loop scales the
    engine trade's P&L linearly, engine/live.py: pnl x routed / engine qty, as runlib.size)."""
    if "_fixed" in t:
        return t["_ppm"] * q
    pe = t["_gpm"] * qe - comm(qe)
    return pe * q / qe


def prep(raw, risk_usd=BASE_RISK, ref=BASE_REF):
    """Raw replay trades in entry order with the reconstructed sizing stop (_plan), P&L per micro (_ppm), worst open P&L
    per micro (_lpm, as runlib: MAE capped at the stop) and the shadow-record index."""
    T = [dict(t) for t in sorted(raw["trades"], key=lambda t: t["entry_t"]) if int(t.get("qty") or 0) > 0]
    for i, t in enumerate(T):
        q0 = int(t["qty"]); rp = float(t["risk_pts"])
        t["_i"] = i
        t["_q0"] = q0
        t["_plan"] = est_plan(t, risk_usd, ref)
        t["_tf"] = 0.5 if t.get("regime") == "trending" else 1.0
        t["_ppm"] = float(t["pnl"]) / q0
        t["_gpm"] = (float(t["pnl"]) + comm(q0)) / q0          # gross per micro (commission is not linear: 10 micros = 1 NQ)
        t["_lpm"] = -min(float(t.get("mae") or 0.0), max(1.0, -float(t["r"]))) * rp * 2.0
    return T


# ------------------------------------------------------------------------------------------------ shadow-record streaks
_TRAIL = {}
ENGINE_KEYS = ("risk_usd", "ref", "alpha", "floor", "trend_mult", "pre_key")


def shadow_r(T, pol):
    """R of every signal as the engine records it in the shadow ledger (engine/equity_filter.record: the engine trade's
    pnl_r, commission included) under the policy's engine-stage sizing; None when the engine would not take it."""
    out = []
    for t in T:
        if "_fixed" in t:
            out.append(float(t["r"])); continue
        qe = micros(t, base_risk(t, pol), pol.get("max_micros", MAX_MICROS))
        out.append(None if qe < 1 else (t["_gpm"] * qe - comm(qe)) / (float(t["risk_pts"]) * 2.0 * qe))
    return out


def trailing(T, lookback, pol=None):
    """For every trade: (sum R, count) of the last `lookback` signals that FINISHED before it entered (entry order),
    exactly as engine/equity_filter.status / runlib.cold_status."""
    pol = pol or {}
    ek = tuple((k, pol.get(k)) for k in ENGINE_KEYS)
    key = (id(T), lookback, ek)
    if key in _TRAIL:
        return _TRAIL[key]
    rs = shadow_r(T, pol)
    out = []
    for t in T:
        rows = [(x, r) for x, r in zip(T, rs) if r is not None and x["exit_t"] and int(x["exit_t"]) < int(t["entry_t"])]
        last = rows[-lookback:]
        out.append((round(sum(r for x, r in last), 2), len(last)))
    _TRAIL[key] = out
    return out


def cold_mult(T, i, cold, pol=None):
    """Live cold-streak rule (generalised): last `lookback` finished signals sum <= thr -> `size` (1 = off)."""
    if not cold:
        return 1.0, None
    s, n = trailing(T, int(cold.get("lookback", 15)), pol)[i]
    on = n < int(cold.get("lookback", 15)) or s > float(cold.get("thr", 0.0))
    return (1.0 if on else float(cold.get("size", 0.5))), s


# ------------------------------------------------------------------------------------------------ sizing policy
def base_risk(t, pol):
    """Engine-stage $ risk before rounding: risk_usd x stop factor x trending half x situational multiplier."""
    p = t["_plan"]
    ru = float(pol.get("risk_usd", BASE_RISK))
    ref = pol.get("ref", BASE_REF)
    if ref and p > ref:
        ru *= (ref / p) ** float(pol.get("alpha", 1.0))
    if pol.get("floor"):
        ru = max(ru, float(pol["floor"]))
    if t.get("regime") == "trending":
        ru *= float(pol.get("trend_mult", 0.5))
    if pol.get("pre"):                           # situational $ multiplier (setup context at entry); give the policy a
        ru *= float(pol["pre"](t))               # "pre_key" naming it so the shadow-ledger cache keys differ
    return ru


def micros(t, ru, cap=MAX_MICROS):
    return min(cap, int(ru // (t["_plan"] * 2.0))) if ru > 0 else 0


def qty_for(T, t, pol, ctx):
    """Micros for trade t under policy pol, given ctx (state known at entry). 0 = not traded."""
    if "_fixed" in t:                            # already-sized trades (prep_sized): keep the qty
        return t["_fixed"], t["_fixed"], 0.0
    ru = base_risk(t, pol)
    if pol.get("cap_usd"):                       # $ cap from the account / eval state (e.g. k x cushion)
        ru = min(ru, max(0.0, float(pol["cap_usd"](t, ctx))))
    if pol.get("mult_usd"):                      # $ multiplier from the account / eval state
        ru *= max(0.0, float(pol["mult_usd"](t, ctx)))
    q = qe = micros(t, ru, pol.get("max_micros", MAX_MICROS))
    if q < 1 and (pol.get("cap_usd") or pol.get("mult_usd")) and pol.get("min1", True) and \
            micros(t, base_risk(t, pol), pol.get("max_micros", MAX_MICROS)) >= 1:
        q = qe = 1                               # a state rule never drops a setup the engine takes: 1 micro minimum
    if q < 1:
        return 0, 0, ru
    c, _ = cold_mult(T, t["_i"], pol.get("cold", LIVE_COLD), pol)
    if c <= 0:
        return 0, qe, ru
    if c < 1:
        q = max(1, int(q * c))
    elif c > 1:
        q = min(pol.get("max_micros", MAX_MICROS), int(q * c))
    if pol.get("hot"):
        h = pol["hot"]
        s, n = trailing(T, int(h["lookback"]), pol)[t["_i"]]
        if n >= int(h["lookback"]) and s >= float(h["thr"]):
            q = min(pol.get("max_micros", MAX_MICROS), int(q * float(h["mult"])))
    if pol.get("post"):                          # live-loop style qty multiplier (like the cold-streak half)
        m = float(pol["post"](t, ctx))
        if m <= 0:
            return 0, qe, ru
        q = max(1, int(q * m)) if m < 1 else min(pol.get("max_micros", MAX_MICROS), int(q * m))
    return q, qe, ru


def sized_trade(t, q, qe, cold_c, extra=None):
    rp = float(t["risk_pts"])
    x = {k: v for k, v in t.items() if not k.startswith("_")}
    x.update({"qty": q, "pnl": round(pnl_of(t, q, qe), 2), "risk_usd": round(rp * 2.0 * q, 2), "half": cold_c < 1,
              "mult": round(q / t["_q0"], 3), "low": t["_lpm"] * q})
    if extra:
        x.update(extra)
    return x


def dll_cut(pnl, low, dll=PLAN["dll"]):
    """MFFU soft daily loss limit (engine/risk_policy.EvalAccount): an open loss of $1,000 flattens the position."""
    if low <= -dll:
        return -dll, -dll
    return pnl, min(low, pnl, 0.0)


def run_account(T, pol, dll=True):
    """Continuous account: size every trade from the state known at entry. ctx = finished trades of this run (sized),
    equity, peak, dd, week P&L/R, streak, last results."""
    out, done = [], []
    for t in T:
        fin = [x for x in done if x["exit_t"] and x["exit_t"] < t["entry_t"]]
        eq = sum(x["pnl"] for x in fin)
        peak = run = 0.0
        for x in fin:
            run += x["pnl"]; peak = max(peak, run)
        wk = dt.date.fromisoformat(t["day"]).isocalendar()[:2]
        wfin = [x for x in fin if dt.date.fromisoformat(x["day"]).isocalendar()[:2] == wk]
        streak = 0
        for x in reversed(fin):
            s = 1 if x["r"] > 0.05 else -1
            if streak == 0 or (s > 0) == (streak > 0):
                streak += s
            else:
                break
        ctx = {"finished": fin, "equity": eq, "peak": peak, "dd": eq - peak, "streak": streak,
               "week_r": sum(x["r"] for x in wfin), "week_pnl": sum(x["pnl"] for x in wfin), "week_n": len(wfin)}
        q, qe, ru = qty_for(T, t, pol, ctx)
        if q <= 0:
            continue
        c, _ = cold_mult(T, t["_i"], pol.get("cold", LIVE_COLD), pol)
        x = sized_trade(t, q, qe, c)
        if dll:
            x["pnl"], x["low"] = dll_cut(x["pnl"], min(x["low"], x["pnl"], 0.0))
        out.append(x); done.append(x)
    return out


# ------------------------------------------------------------------------------------------------ eval simulator
class Eval:
    """One MFFU Builder 50K eval (mirrors engine/analytics.simulate_eval + the soft daily limit)."""
    __slots__ = ("bal", "peak", "mll", "days", "trades", "wins", "losses", "last_r", "result", "pnl_list")

    def __init__(self):
        self.bal = self.peak = PLAN["start"]; self.mll = PLAN["start"] - PLAN["mll"]
        self.days = self.trades = self.wins = self.losses = 0; self.last_r = None; self.result = "OPEN"

    def state(self):
        profit = self.bal - PLAN["start"]
        return {"bal": self.bal, "mll": self.mll, "cushion": self.bal - self.mll, "profit": profit,
                "need": PLAN["target"] - profit, "locked": self.mll >= PLAN["lock"] - 0.005, "days": self.days,
                "trades": self.trades, "wins": self.wins, "losses": self.losses, "last_r": self.last_r}

    def day(self, pnl, low):
        """End a session with day P&L and intraday low (both $, low <= 0). Returns OPEN / PASS / FAIL."""
        self.days += 1
        if self.bal + low <= self.mll or self.bal + pnl <= self.mll:
            self.bal += pnl; self.result = "FAIL"
            return self.result
        self.bal += pnl
        self.peak = max(self.peak, self.bal)
        self.mll = min(max(self.mll, self.peak - PLAN["mll"]), PLAN["lock"])
        if self.bal - PLAN["start"] >= PLAN["target"]:
            self.result = "PASS"
        return self.result


def _by_day(T):
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    return by


def eval_path(T, pol, sess, k0, horizon=None, by=None, dll=True, record=None):
    """Run one eval from session index k0 over sess (list of dates), sizing each trade from this eval's state.
    Returns (result, sessions used). record: list to append the sized trades to."""
    by = by or _by_day(T)
    ev = Eval()
    end = len(sess) if horizon is None else min(len(sess), k0 + horizon)
    for k in range(k0, end):
        cum = low = 0.0
        for t in by.get(sess[k], ()):
            st = ev.state(); st["day_pnl"] = cum
            q, qe, ru = qty_for(T, t, pol, st)
            if q <= 0:
                continue
            c, _ = cold_mult(T, t["_i"], pol.get("cold", LIVE_COLD), pol)
            pnl, lo = pnl_of(t, q, qe), t["_lpm"] * q
            lo_day = min(low, cum + lo, cum + pnl)
            if dll and cum + min(lo, pnl, 0.0) <= -PLAN["dll"]:
                pnl = -PLAN["dll"] - cum; lo_day = min(low, -PLAN["dll"])
            low = lo_day; cum += pnl
            ev.trades += 1; ev.wins += pnl > 0; ev.losses += pnl < 0; ev.last_r = float(t["r"])
            if record is not None:
                x = sized_trade(t, q, qe, c); x["pnl"] = round(pnl, 2); x["low"] = lo
                record.append(x)
        res = ev.day(round(cum, 2), round(min(low, 0.0), 2))
        if res != "OPEN":
            return res, k - k0 + 1
    return "OPEN", end - k0


def eval_stats(T, pol, sess, dll=True):
    """Rolling 2-week / 1-month pass-fail, eventual pass share (run to the end of the span) and back-to-back, over the
    sessions `sess` (one span)."""
    by = _by_day(T)
    out = {}
    for H, key in ((10, "10"), (20, "20"), (60, "60")):
        c = collections.Counter()
        for i in range(len(sess) - H + 1):
            c[eval_path(T, pol, sess, i, H, by, dll)[0]] += 1
        n = sum(c.values()) or 1
        out["p" + key] = round(100 * c["PASS"] / n, 1); out["f" + key] = round(100 * c["FAIL"] / n, 1)
    c = collections.Counter(); dpass = []
    for i in range(len(sess)):
        r, d = eval_path(T, pol, sess, i, None, by, dll)
        c[r] += 1
        if r == "PASS":
            dpass.append(d)
    res = c["PASS"] + c["FAIL"]
    out["pE"] = round(100 * c["PASS"] / res, 1) if res else None
    out["dE"] = int(np.median(dpass)) if dpass else None
    k, P, F = 0, 0, 0
    while k < len(sess):
        r, d = eval_path(T, pol, sess, k, None, by, dll)
        if r == "OPEN":
            break
        P += r == "PASS"; F += r == "FAIL"; k += d
    out["b2b"] = f"{P}/{F}"
    return out


def chain_trades(T, pol, sess, dll=True):
    """Trades of back-to-back evals over all sessions (a new eval the session after each pass or fail)."""
    by = _by_day(T)
    rec, k = [], 0
    while k < len(sess):
        r, d = eval_path(T, pol, sess, k, None, by, dll, record=rec)
        if r == "OPEN":
            break
        k += d
    return rec


# ------------------------------------------------------------------------------------------------ scoring / saving
def span_sessions(raw, a, z):
    return [d for d in raw["sessions"] if a <= d <= z]


def score(trades, raw, T=None, pol=None, eval_aware=False, dll=True):
    """runlib.score (+ eventual pass share and median days to pass). Eval-aware policies (sizing from the eval's own
    state) get all their eval columns from the eval simulator run on the raw trades T with policy pol; any other run is
    evaluated on its sized trades as they are (identical to runlib's numbers)."""
    S = rl.score(trades, raw)
    fixed = prep_sized(trades)
    for name, a, z in SPANS:
        sess = span_sessions(raw, a, z)
        if not sess or not S["spans"][name].get("n"):
            continue
        if eval_aware:
            S["spans"][name].update(eval_stats(T, pol, sess, dll))
        else:
            e = eval_stats(fixed, {"cold": None}, sess, dll)
            S["spans"][name].update({k: e[k] for k in ("pE", "dE")})
    return S


def prep_sized(trades):
    """Already-sized trades as a fixed policy for the eval simulator (qty kept as is)."""
    out = []
    for i, t in enumerate(sorted(trades, key=lambda x: x["entry_t"])):
        x = dict(t); q = int(t["qty"])
        x.update({"_i": i, "_q0": q, "_plan": 1.0, "_tf": 1.0, "_ppm": float(t["pnl"]) / q, "_lpm": float(t.get("low", 0.0)) / q,
                  "_fixed": q})
        out.append(x)
    return out


def headline(S):
    return {k: S["spans"][k] for k in ("2026", "2021-25", "all")}


def fmt(S, name):
    s = S["spans"][name]
    if not s.get("n"):
        return f"{name}: no trades"
    return (f"{name:7s} n={s['n']:3d} tpw={s['tpw']:.2f} wk2={s['wk2']:3d}% win={s['win']:4.1f}% PF={s['pf']} net={s['net']:+7,} "
            f"DD={s['dd']:7,} 2w {s['p10']:4.1f}/{s['f10']:4.1f} 1m {s['p20']:4.1f}/{s['f20']:4.1f} eventual {s.get('pE')}% b2b {s['b2b']}")


def show(tag, S):
    print(f"--- {tag}")
    for k in ("2026", "2021-25", "all"):
        print("   " + fmt(S, k))


def status_of(S, B, min_tpw=2.0):
    """C. adopt-candidate: beats the baseline in BOTH periods (net and PF, or clearly better eval pass/fail with equal-or-
    better net) and keeps 2+ trades a week; promising: clearly helps one period, does not hurt the other; else rejected."""
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, Bb = B["spans"]["2026"], B["spans"]["2021-25"]
    if (a.get("tpw") or 0) < min_tpw or (b.get("tpw") or 0) < min_tpw:
        return "rejected"

    def better(x, y):
        money = x["net"] > y["net"] and (x["pf"] or 0) >= (y["pf"] or 0)
        evals = (x["net"] >= y["net"] and x["p20"] - x["f20"] >= y["p20"] - y["f20"] + 2.0)
        return money or evals

    def not_worse(x, y):
        return x["net"] >= 0.97 * y["net"] - 150 and (x["pf"] or 0) >= (y["pf"] or 0) - 0.03 and \
            x["p20"] - x["f20"] >= y["p20"] - y["f20"] - 1.0

    def clearly(x, y):
        return (x["net"] > y["net"] * 1.05 + 300 and (x["pf"] or 0) > (y["pf"] or 0)) or \
            (x["p20"] - x["f20"] >= y["p20"] - y["f20"] + 3.0 and x["net"] >= y["net"] - 300)

    if better(a, A) and better(b, Bb):
        return "adopt-candidate"
    if (clearly(a, A) and not_worse(b, Bb)) or (clearly(b, Bb) and not_worse(a, A)):
        return "promising"
    return "rejected"


def save(id, title, question, trades, S, status, verdict, notes="", params=None, sizing=None, writeup=None, tags=None):
    assert id.startswith(("risk_", "loss_")), id
    rec = rl.save(id, title, "risk", question, params=params or {}, sizing=sizing or {}, trades=trades, scored=S, status=status,
                  verdict=verdict, notes=notes, writeup=writeup, tags=["risk"] + (tags or []))
    # the eval-simulator extras (eventual pass share, median days) are kept in the run file too
    return rec


_BASE = {}


def baseline():
    """(raw, prepped trades, sized trades, score) of the live strategy."""
    if not _BASE:
        raw = rl.replay(quiet=True)
        T = prep(raw)
        tr = run_account(T, {})
        S = score(tr, raw, T, {})
        _BASE.update(raw=raw, T=T, trades=tr, S=S)
    return _BASE["raw"], _BASE["T"], _BASE["trades"], _BASE["S"]


# ------------------------------------------------------------------------------------------------ A. loss anatomy
PERIODS = (("2021-25", "2021-01-01", "2025-12-31"), ("2026", "2026-01-01", "2026-12-31"))


def feats(t):
    """Setup context known at entry (for the factor tables and the situational rules)."""
    d = t["dir"]
    x = et(t["entry_t"])
    ht = (t.get("htf_trend") or 0) * d
    pd = t.get("pd_pos")
    f = t.get("f") or {}
    vix = f.get("vix_prev") or 0.0
    rp = float(t["risk_pts"])
    rr = f.get("rr_plan") or 0.0
    return {
        "Session": "AM (before 12:00)" if x.hour < 12 else "PM",
        "Weekday": x.strftime("%a"),
        "Trigger": t.get("trigger") or "?",
        "Regime (10-day)": t.get("regime") or "?",
        "1H trend": "with the trade" if ht > 0 else "against the trade" if ht < 0 else "flat",
        "15m already turned (late)": "yes" if (t.get("m15_trend") or 0) * d > 0 else "no",
        "Pool swept": "minor (15m swing)" if set(t.get("pools") or []) <= {"ITH", "ITL"} else "major",
        "Location": "?" if pd is None else ("good" if (d == 1 and pd < 0.5) or (d == -1 and pd > 0.5) else "poor"),
        "Stop size": "under 20 pts" if rp < 20 else "20-30 pts" if rp < 30 else "30-45 pts" if rp < 45 else "45-60 pts",
        "VIX (prior close)": "under 15" if vix < 15 else "15-20" if vix < 20 else "20-25" if vix < 25 else "25+",
        "News day": "yes" if f.get("news_day") else "no",
        "First hour (09:30-10:30)": "yes" if f.get("first_hour") else "no",
        "Direction": "long" if d == 1 else "short",
        "Target distance": "under 2R" if rr < 2 else "2-3R" if rr < 3 else "3-5R" if rr < 5 else "5R+ (banks at 5R)",
        "Inducement taken first": "yes" if (t.get("smc") or {}).get("x_inducement") else "no",
    }


LOSS_TYPES = (
    ("Full stop-out", lambda t: t["exit"] == "STOP"),
    ("  stopped within 2 bars (10 min)", lambda t: t["exit"] == "STOP" and (t.get("bars_held") or 99) <= 2),
    ("Never worked (best point under +0.3R)", lambda t: (t.get("mfe") or 0) < 0.3),
    ("Was +0.5R or better, then lost", lambda t: (t.get("mfe") or 0) >= 0.5),
    ("Was +1R or better, then lost", lambda t: (t.get("mfe") or 0) >= 1.0),
    ("Time stop (30 min, no +0.5R)", lambda t: t["exit"] == "TIME STOP"),
    ("Giveback exit", lambda t: t["exit"] == "SIGNAL giveback"),
    ("Wide stop (45 pts or more)", lambda t: t["risk_pts"] >= 45),
    ("Tight stop (20 pts or less, full $800)", lambda t: t["risk_pts"] <= 20),
    ("Against the 1H trend", lambda t: (t.get("htf_trend") or 0) * t["dir"] < 0),
    ("Late (15m already turned)", lambda t: (t.get("m15_trend") or 0) * t["dir"] > 0),
    ("Trending regime (already half size)", lambda t: t.get("regime") == "trending"),
    ("Cold streak (half size)", lambda t: t.get("half")),
)


def _md(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(head))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _money(x):
    return f"-${-x:,.0f}" if x < 0 else f"+${x:,.0f}"


def drawdowns(days, top=5):
    eq = peak = 0.0; peak_d = days[0]["date"]; cur = None; out = []
    for d in days:
        eq += d["pnl"]
        if eq >= peak:
            if cur is not None:
                cur["recovered"] = d["date"]; out.append(cur); cur = None
            peak = eq; peak_d = d["date"]
        else:
            if cur is None:
                cur = {"peak": peak_d, "trough": d["date"], "depth": eq - peak, "recovered": None}
            if eq - peak < cur["depth"]:
                cur["depth"] = eq - peak; cur["trough"] = d["date"]
    if cur is not None:
        out.append(cur)
    return sorted(out, key=lambda x: x["depth"])[:top]


def anatomy(trades, raw):
    """Markdown tables for research/writeups/loss-anatomy.md."""
    S = rl.score(trades, raw)
    days = S["days"]
    md = []
    by = {name: ([t for t in trades if a <= t["day"] <= z], [d for d in days if a <= d["date"] <= z]) for name, a, z in PERIODS}
    # 1. where the money goes
    rows = []
    for name, (X, D) in by.items():
        p = np.array([t["pnl"] for t in X]); r = np.array([t["r"] for t in X])
        gp, gl = p[p > 0].sum(), -p[p < 0].sum()
        rows.append([name, len(X), int((r > 0.05).sum()), int((abs(r) <= 0.05).sum()), int((r < -0.05).sum()), f"${gp:,.0f}",
                     f"${gl:,.0f}", f"{100 * gl / gp:.0f}%", _money(p.sum()), f"{r[r > 0].sum():.0f}R / {-r[r < 0].sum():.0f}R",
                     f"{r.mean():+.3f}R"])
    md.append("### Where the money goes\n" + _md(rows, ["period", "trades", "wins", "scratches (about 0R)", "losses",
                                                         "gross profit", "gross loss", "loss / profit", "net",
                                                         "R won / R lost", "avg R per trade"]))
    # 2. R distribution
    bins = [(-99, -0.95, "full loss (-1R)"), (-0.95, -0.5, "-0.95 to -0.5R"), (-0.5, -0.05, "small loss (-0.5 to 0R)"),
            (-0.05, 0.05, "scratch (break-even)"), (0.05, 1.0, "small win (under 1R)"), (1.0, 2.0, "1-2R"), (2.0, 3.0, "2-3R"),
            (3.0, 5.0, "3-5R"), (5.0, 99, "5R and more")]
    rows = []
    for a, z, lab in bins:
        row = [lab]
        for name, (X, D) in by.items():
            Y = [t for t in X if a < t["r"] <= z]
            row += [f"{len(Y)} ({100 * len(Y) / len(X):.0f}%)", _money(sum(t["pnl"] for t in Y))]
        rows.append(row)
    md.append("### Result of each trade in R\n" + _md(rows, ["result", "2021-25 trades", "2021-25 $", "2026 trades", "2026 $"]))
    # 3. loss types
    rows = []
    for lab, fn in LOSS_TYPES:
        row = [lab]
        for name, (X, D) in by.items():
            L = [t for t in X if t["r"] < -0.05]
            tot = -sum(t["pnl"] for t in L)
            Y = [t for t in L if fn(t)]
            lost = -sum(t["pnl"] for t in Y)
            row += [f"{len(Y)} ({100 * len(Y) / len(L):.0f}%)", f"${lost:,.0f} ({100 * lost / tot:.0f}%)",
                    f"${lost / len(Y):,.0f}" if Y else "-"]
        rows.append(row)
    md.append("### Losing trades by type (a trade can be in several rows)\n" +
              _md(rows, ["loss type", "2021-25 losses", "2021-25 $ lost", "avg loss", "2026 losses", "2026 $ lost", "avg loss"]))
    # 4. streaks
    rows = []
    for name, (X, D) in by.items():
        runs, cur = [], []
        for t in X:
            if t["r"] <= 0.05:
                cur.append(t)
            else:
                if cur:
                    runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        for s in sorted(runs, key=lambda s: sum(t["pnl"] for t in s))[:4]:
            rows.append([name, f"{s[0]['day']} to {s[-1]['day']}", len(s), f"{sum(t['r'] for t in s):.1f}R",
                         _money(sum(t["pnl"] for t in s)), f"{sum(bool(t['half']) for t in s)} of {len(s)}"])
        L = [len(s) for s in runs]
        rows.append([name, "all streaks", f"longest {max(L)}, average {np.mean(L):.1f}", "", "",
                     f"{sum(x >= 10 for x in L)} streaks of 10+"])
    md.append("### Costliest runs of trades without a win\n" + _md(rows, ["period", "dates", "trades", "R", "$", "at half size"]))
    # 5. drawdowns
    rows = []
    for name, (X, D) in by.items():
        for d in drawdowns(D, 4):
            Y = [t for t in X if d["peak"] < t["day"] <= d["trough"]]
            stops = [t for t in Y if t["exit"] == "STOP"]
            rows.append([name, _money(d["depth"]), f"{d['peak']} to {d['trough']}", d["recovered"] or "not yet", len(Y),
                         sum(t["r"] > 0.05 for t in Y), f"{sum(t['r'] for t in Y):.1f}R",
                         f"{len(stops)} ({_money(sum(t['pnl'] for t in stops))})",
                         f"{sum(bool(t['half']) for t in Y)}", f"{np.median([t['risk_pts'] for t in Y]):.0f}"])
    md.append("### Worst drawdowns (peak to trough) and what caused them\n" +
              _md(rows, ["period", "depth", "peak to trough", "recovered", "trades", "wins", "R", "full stop-outs ($)",
                         "half-size trades", "median stop pts"]))
    # 6. months and quarters
    rows = []
    for name, (X, D) in by.items():
        m = collections.defaultdict(float); q = collections.defaultdict(float)
        for t in X:
            m[t["day"][:7]] += t["pnl"]; q[f"{t['day'][:4]} Q{(int(t['day'][5:7]) - 1) // 3 + 1}"] += t["pnl"]
        lm = sorted((v, k) for k, v in m.items() if v < 0); lq = sorted((v, k) for k, v in q.items() if v < 0)
        rows.append([name, f"{len(lm)} of {len(m)}", ", ".join(f"{k} {_money(v)}" for v, k in lm[:4]), f"{len(lq)} of {len(q)}",
                     ", ".join(f"{k} {_money(v)}" for v, k in lq[:3])])
    md.append("### Losing months and quarters\n" + _md(rows, ["period", "losing months", "worst months", "losing quarters",
                                                             "worst quarters"]))
    # 7. factors
    rows = []
    keys = list(feats(trades[0]).keys())
    for k in keys:
        vals = sorted({feats(t)[k] for t in trades}, key=str)
        for v in vals:
            row = [k, v]
            for name, (X, D) in by.items():
                Y = [t for t in X if feats(t)[k] == v]
                if not Y:
                    row += ["-", "-", "-"]; continue
                r = np.array([t["r"] for t in Y])
                row += [len(Y), f"{r.mean():+.2f}R", _money(sum(t["pnl"] for t in Y))]
            rows.append(row)
    md.append("### Every factor: trades, average R and net $ (the same trades, as sized live)\n" +
              _md(rows, ["factor", "value", "2021-25 trades", "avg R", "net", "2026 trades", "avg R", "net"]))
    return "\n\n".join(md)


def derisk_effects(T, raw):
    """What each de-risking rule did: $ it cost on winners and saved on losers (vs the same trade without that rule)."""
    live = run_account(T, {})
    rules = (("Cold-streak half size", {"cold": None}), ("Trending regime half size", {"trend_mult": 1.0}),
             ("Smaller risk on stops wider than 20 pts", {"ref": 0}),
             ("All three (vs $800 on every trade)", {"cold": None, "trend_mult": 1.0, "ref": 0}))
    rows = []
    for lab, pol in rules:
        alt = {t["entry_t"]: t for t in run_account(T, pol)}
        row = [lab]
        for name, a, z in PERIODS:
            X = [t for t in live if a <= t["day"] <= z]
            cost = sum(alt[t["entry_t"]]["pnl"] - t["pnl"] for t in X if t["pnl"] > 0 and t["entry_t"] in alt)
            saved = sum(t["pnl"] - alt[t["entry_t"]]["pnl"] for t in X if t["pnl"] <= 0 and t["entry_t"] in alt)
            n = sum(1 for t in X if t["entry_t"] in alt and alt[t["entry_t"]]["qty"] != t["qty"])
            row += [n, f"-${cost:,.0f}", f"+${saved:,.0f}", _money(saved - cost)]
        rows.append(row)
    return _md(rows, ["rule", "2021-25 trades changed", "cost on winners", "saved on losers", "net effect",
                      "2026 trades changed", "cost on winners", "saved on losers", "net effect"])


def size_outcome(trades):
    """Risk vs outcome: are full-size losses bigger than the small-size wins? By $ risk bucket."""
    rows = []
    for lab, a, z in (("$600+ (tight stop, full size)", 600, 1e9), ("$300-600", 300, 600), ("$150-300", 150, 300),
                      ("under $150", 0, 150)):
        row = [lab]
        for name, pa, pz in PERIODS:
            X = [t for t in trades if pa <= t["day"] <= pz and a <= t["risk_usd"] < z]
            W = [t["pnl"] for t in X if t["pnl"] > 0]; L = [t["pnl"] for t in X if t["pnl"] <= 0]
            r = np.array([t["r"] for t in X]) if X else np.zeros(1)
            row += [len(X), f"{100 * len(W) / max(1, len(X)):.0f}%", f"${np.mean(W):,.0f}" if W else "-",
                    f"-${-np.mean(L):,.0f}" if L else "-", f"{r.mean():+.2f}R", _money(sum(t["pnl"] for t in X))]
        rows.append(row)
    return _md(rows, ["$ at risk", "2021-25 trades", "win %", "avg win", "avg loss", "avg R", "net", "2026 trades", "win %",
                      "avg win", "avg loss", "avg R", "net"])


def missed_winners(T, trades, top=10):
    """Biggest R winners and what they made vs what $800 at risk would have made."""
    full = {t["entry_t"]: t for t in run_account(T, {"cold": None, "trend_mult": 1.0, "ref": 0})}
    W = sorted([t for t in trades if t["r"] > 0], key=lambda t: -t["r"])[:top]
    rows = [[t["day"], f"{t['r']:+.1f}R", f"{t['risk_pts']:.0f}", f"${t['risk_usd']:,.0f}", _money(t["pnl"]),
             _money(full[t["entry_t"]]["pnl"]) if t["entry_t"] in full else "-",
             ", ".join(x for x in ("cold half" if t["half"] else "", "trending" if t.get("regime") == "trending" else "",
                                   "wide stop" if t["risk_pts"] > 20 else "") if x) or "-"] for t in W]
    return _md(rows, ["day", "R", "stop pts", "risked", "made", "at $800 risk", "why it was small"])


def cmd_anatomy(write=True):
    raw, T, trades, S = baseline()
    out = ["## Loss anatomy (generated by tools/research_risk.py anatomy)", anatomy(trades, raw),
           "### What each de-risking rule did (vs the same trades without it)\n" + derisk_effects(T, raw),
           "### Risk vs outcome by $ at risk\n" + size_outcome(trades),
           "### The ten biggest winners: sized small?\n" + missed_winners(T, trades)]
    txt = "\n\n".join(out)
    print(txt)
    if write:
        os.makedirs(os.path.join(ROOT, WRITEUPS, "data"), exist_ok=True)
        open(os.path.join(ROOT, WRITEUPS, "data", "loss_anatomy_tables.md"), "w", encoding="utf-8").write(txt + "\n")
    B = S
    info = (("loss_no_cold", "Cold-streak filter off (every setup at full size)", {"cold": None},
             "What does the half-size cold-streak filter earn or cost?"),
            ("loss_no_trend_half", "Trending regime at full size", {"trend_mult": 1.0},
             "What does the trending-regime half size earn or cost?"),
            ("loss_all_full", "$800 at risk on every trade (no de-risking at all)", {"cold": None, "trend_mult": 1.0, "ref": 0},
             "Did the bot risk too little? Every trade at the full $800, whatever the stop, regime or streak."))
    for id, title, pol, q in info:
        tr = run_account(T, pol)
        Sx = score(tr, raw)
        show(id, Sx)
        a, b = Sx["spans"]["2026"], Sx["spans"]["2021-25"]
        A, Bb = B["spans"]["2026"], B["spans"]["2021-25"]
        verdict = (f"Without it: 2026 {_money(a['net'] - A['net'])} net (PF {a['pf']} vs {A['pf']}), 2021-25 "
                   f"{_money(b['net'] - Bb['net'])} (PF {b['pf']} vs {Bb['pf']}, max DD {b['dd']:,} vs {Bb['dd']:,}).")
        save(id, title, q, tr, Sx, "info", verdict, notes="Counterfactual for the loss anatomy (post-hoc re-sizing of the "
             "baseline replay, exact engine micros).", sizing={k: v for k, v in pol.items()}, writeup=f"{WRITEUPS}/loss-anatomy.md",
             tags=["anatomy"])


# ------------------------------------------------------------------------------------------------ self-tests
def cmd_check():
    raw = rl.replay(quiet=True)
    T = prep(raw)
    bad = [t for t in T if micros(t, base_risk(t, {})) != t["_q0"]]
    print(f"sizing stop reconstruction: {len(T) - len(bad)}/{len(T)} trades give back the engine's micros")
    mine = run_account(T, {})
    ref = rl.size(raw)
    same = len(mine) == len(ref) and all(a["qty"] == b["qty"] and abs(a["pnl"] - b["pnl"]) < 0.01 for a, b in zip(mine, ref))
    print(f"live sizing (cold-streak half) vs runlib.size: {'identical' if same else 'DIFFERENT'} ({len(mine)} trades)")
    S0 = rl.score(ref, raw)
    for name, a, z in SPANS:
        sess = span_sessions(raw, a, z)
        e = eval_stats(T, {}, sess)
        s0 = S0["spans"][name]
        ok = all(abs(e[k] - s0[k]) < 0.05 for k in ("p10", "f10", "p20", "f20")) and e["b2b"] == s0["b2b"]
        print(f"eval simulator {name}: {'matches' if ok else 'DIFFERS'} runlib ({e} vs "
              f"{ {k: s0[k] for k in ('p10', 'f10', 'p20', 'f20', 'b2b')} })")
    nd = sum(1 for t in mine if t["low"] <= -PLAN["dll"])
    print(f"daily loss limit binds on {nd} baseline trades")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    globals()["cmd_" + cmd]()
