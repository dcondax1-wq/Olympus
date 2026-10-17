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
ENGINE_KEYS = ("risk_usd", "ref", "alpha", "floor", "trend_mult", "pre_key")   # engine-stage sizing (shadow-ledger R)


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
def base_risk(t, pol, with_pre=True):
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
    if with_pre and pol.get("pre"):              # situational $ multiplier (setup context at entry); give the policy a
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
    if q < 1 and (pol.get("cap_usd") or pol.get("mult_usd") or pol.get("pre")) and pol.get("min1", True) and \
            micros(t, base_risk(t, pol, with_pre=False), pol.get("max_micros", MAX_MICROS)) >= 1:
        q = qe = 1                               # a sizing rule never drops a setup the engine takes: 1 micro minimum
    if q < 1:
        return 0, 0, ru
    c, _ = cold_mult(T, t["_i"], pol.get("cold", LIVE_COLD), pol)
    if c <= 0:
        return 0, qe, ru
    if pol.get("late_mult") is not None:         # one live-loop multiplier: cold size x late-entry size, rounded once
        late = (t["entry_t"] in pol["late_set"]) if pol.get("late_set") is not None else (t.get("m15_trend") or 0) * t["dir"] > 0
        c = c * (float(pol["late_mult"]) if late else 1.0)
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


def b2b_avg(T, pol, sess, offsets=range(0, 100, 5), dll=True):
    """Back-to-back evals started on 20 different first days (0, 5, ... 95 sessions in): average passes and fails per
    year of trading, so one lucky or unlucky first eval does not decide the comparison."""
    by = _by_day(T)
    P = F = yrs = 0.0
    for k0 in offsets:
        k, p_, f_ = k0, 0, 0
        while k < len(sess):
            r, d = eval_path(T, pol, sess, k, None, by, dll)
            if r == "OPEN":
                break
            p_ += r == "PASS"; f_ += r == "FAIL"; k += d
        P += p_; F += f_; yrs += (len(sess) - k0) / 252.0
    return {"pass_yr": round(P / yrs, 2), "fail_yr": round(F / yrs, 2), "evals_per_pass": round((P + F) / P, 2) if P else None}


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
            S["spans"][name].update({k: e[k] for k in ("p60", "f60", "pE", "dE")})
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
            f"DD={s['dd']:7,} 2w {s['p10']:4.1f}/{s['f10']:4.1f} 1m {s['p20']:4.1f}/{s['f20']:4.1f} 3m {s.get('p60', 0):4.1f}/"
            f"{s.get('f60', 0):4.1f} b2b {s['b2b']}")


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

    def ev(x):
        return x["p20"] - x["f20"]

    def better(x, y):
        money = x["net"] > y["net"] and (x["pf"] or 0) >= (y["pf"] or 0) and ev(x) >= ev(y) - 1.0
        evals = x["net"] >= y["net"] and ev(x) >= ev(y) + 2.0
        return money or evals

    def not_worse(x, y):
        return x["net"] >= 0.97 * y["net"] - 150 and (x["pf"] or 0) >= (y["pf"] or 0) - 0.03 and ev(x) >= ev(y) - 1.0

    def clearly(x, y):
        return (x["net"] > y["net"] * 1.05 + 300 and (x["pf"] or 0) > (y["pf"] or 0) and ev(x) >= ev(y) - 1.0) or \
            (ev(x) >= ev(y) + 3.0 and x["net"] >= y["net"] - 300)

    if better(a, A) and better(b, Bb):
        return "adopt-candidate"
    if (clearly(a, A) and not_worse(b, Bb)) or (clearly(b, Bb) and not_worse(a, A)):
        return "promising"
    return "rejected"


def auto_verdict(S, B, status):
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, Bb = B["spans"]["2026"], B["spans"]["2021-25"]
    head = {"adopt-candidate": "Better in both periods", "promising": "Helps one period without hurting the other",
            "rejected": "Not better in both periods", "info": "For information"}[status]
    if min(a.get("tpw") or 0, b.get("tpw") or 0) < 2.0:
        head = "Fewer than 2 setups a week"
    return (f"{head}. 2026 {_money(a['net'])} (live {_money(A['net'])}), PF {a['pf']} ({A['pf']}), 1-month evals {a['p20']:.0f}% pass / "
            f"{a['f20']:.0f}% fail ({A['p20']:.0f}/{A['f20']:.0f}). 2021-25 {_money(b['net'])} ({_money(Bb['net'])}), PF {b['pf']} "
            f"({Bb['pf']}), evals {b['p20']:.0f}/{b['f20']:.0f}% ({Bb['p20']:.0f}/{Bb['f20']:.0f}).")


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


def cmd_anatomy():
    raw, T, trades, S = baseline()
    out = ["## Loss anatomy (generated by tools/research_risk.py anatomy)", anatomy(trades, raw),
           "### What each de-risking rule did (vs the same trades without it)\n" + derisk_effects(T, raw),
           "### Risk vs outcome by $ at risk\n" + size_outcome(trades),
           "### The ten biggest winners: sized small?\n" + missed_winners(T, trades)]
    txt = "\n\n".join(out)
    print(txt)
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


# ------------------------------------------------------------------------------------------------ experiment runner
ROWS = []          # (family, id, title, status, S) of this process, for the summary tables


def engine_trades(engine):
    """Prepped trades of an engine replay with other sizing params (cached by runlib) + the policy that reproduces the
    engine's own micros on them."""
    raw = rl.replay(engine, procs=int(os.environ.get("RISK_PROCS", "2")), label="risk", quiet=True)
    ru, ref = float(engine.get("risk_usd", BASE_RISK)), float(engine.get("risk_ref_stop", BASE_REF))
    return raw, prep(raw, ru, ref), {"risk_usd": ru, "ref": ref}


def experiment(family, id, title, question, pol=None, engine=None, eval_aware=False, notes="", status=None, verdict=None,
               tags=None, sizing=None, quiet=False):
    raw, T, _, B = baseline()
    pol = dict(pol or {})
    Tx, rawx = T, raw
    if engine:
        rawx, Tx, epol = engine_trades(engine)
        pol = {**epol, **pol}
    if eval_aware:
        trades = chain_trades(Tx, pol, rawx["sessions"])
        S = score(trades, rawx, Tx, pol, eval_aware=True)
    else:
        trades = run_account(Tx, pol)
        S = score(trades, rawx)
    st = status or status_of(S, B)
    v = verdict or auto_verdict(S, B, st)
    if not quiet:
        show(f"{id}  [{st}]  {title}", S)
    meth = ("engine replay with " + json.dumps(engine) if engine else "post-hoc re-sizing of the baseline replay (exact engine micros)")
    if eval_aware:
        meth += "; sized from each eval's own state (eval simulator); trades = back-to-back evals from the first session"
    desc = {k: (v_ if not callable(v_) else getattr(v_, "__doc__", None) or "rule") for k, v_ in pol.items()}
    save(id, title, question, trades, S, st, v, notes=(notes + " " if notes else "") + f"Method: {meth}.", params=engine or {},
         sizing=sizing or desc, writeup=f"{WRITEUPS}/{WRITEUP_OF.get(family, 'risk-sizing.md')}", tags=[family] + (tags or []))
    ROWS.append((family, id, title, st, S))
    return S, st


WRITEUP_OF = {"anatomy": "loss-anatomy.md", "levels": "risk-sizing.md", "refstop": "risk-sizing.md", "cold": "risk-sizing.md",
              "ddaware": "risk-sizing.md", "eval": "eval-sizing.md", "situational": "risk-sizing.md", "weekly": "risk-sizing.md",
              "packages": "risk-summary.md"}


def table(rows=None, base=True):
    """Markdown table of runs: 2026 and 2021-25 side by side (phone-friendly columns)."""
    rows = rows if rows is not None else ROWS
    out = []
    if base:
        _, _, _, B = baseline()
        rows = [("", "baseline", "Live strategy", "baseline", B)] + list(rows)
    for fam, id, title, st, S in rows:
        a, b = S["spans"]["2026"], S["spans"]["2021-25"]
        out.append([id, title, st,
                    f"{a['n']} ({a['tpw']:.1f}/wk)", f"{a['pf']}", _money(a["net"]), f"{a['dd']:,}", f"{a['p10']:.0f}/{a['f10']:.0f}",
                    f"{a['p20']:.0f}/{a['f20']:.0f}", a["b2b"],
                    f"{b['n']} ({b['tpw']:.1f}/wk)", f"{b['pf']}", _money(b["net"]), f"{b['dd']:,}", f"{b['p10']:.0f}/{b['f10']:.0f}",
                    f"{b['p20']:.0f}/{b['f20']:.0f}", f"{b.get('p60', 0):.0f}/{b.get('f60', 0):.0f}", b["b2b"]])
    return _md(out, ["run", "what", "status", "2026 trades", "PF", "net", "max DD", "2w pass/fail %", "1m pass/fail %", "b2b",
                     "2021-25 trades", "PF", "net", "max DD", "2w pass/fail %", "1m pass/fail %", "3m pass/fail %", "b2b"])


# ------------------------------------------------------------------------------------------------ B1 risk level
def cmd_levels():
    q = "How much should one trade risk? The same strategy at a smaller or bigger $ risk."
    for usd, eng in ((400, True), (600, True), (700, False), (900, False), (1000, True), (1200, True)):
        x = usd / BASE_RISK
        experiment("levels", f"risk_usd{usd}", f"Risk ${usd} instead of $800 (x{x:g})", q,
                   pol={} if eng else {"risk_usd": float(usd)}, engine={"risk_usd": float(usd)} if eng else None,
                   notes=f"Every $ amount in the sizing rule scaled by {x:g} (wide stops and half sizes in proportion); "
                         "a setup that would get less than 1 micro is skipped, as the engine does.", tags=["level"])
    print(table([r for r in ROWS if r[0] == "levels"]))


# ------------------------------------------------------------------------------------------------ B2 wide-stop scaling
def cmd_refstop():
    q = "How much less should a wide stop risk? Full $800 up to a reference stop, less beyond it."
    for ref in (15, 25, 30, 40, 0):
        name = "off (flat $800 on every stop)" if ref == 0 else f"{ref} pts"
        experiment("refstop", f"risk_ref{ref if ref else 'off'}", f"Full risk up to a {name}" if ref else "No wide-stop scaling: $800 on every stop",
                   q, engine={"risk_ref_stop": float(ref)}, tags=["wide-stop"],
                   notes=f"risk_ref_stop {ref} (live 20): risk = $800 x {ref}/stop beyond {ref} pts." if ref else
                   "risk_ref_stop 0: $800 whatever the stop (wide stops get few micros only by the stop itself).")
    for a, lab in ((0.5, "gentler: $800 x square root of 20/stop"), (1.5, "steeper: $800 x (20/stop)^1.5")):
        experiment("refstop", f"risk_shape{str(a).replace('.', '')}", f"Wide-stop scaling {lab}", q, pol={"alpha": a},
                   tags=["wide-stop"], notes=f"risk = $800 x (20/stop)^{a} beyond 20 pts (live: power 1).")
    experiment("refstop", "risk_floor400", "Never less than $400 at risk on a wide stop (before the trending and cold halves)", q,
               pol={"floor": 400.0}, tags=["wide-stop"],
               notes="Stops of 40-60 pts keep $400 at risk instead of $267-400 (a $200 floor would never bind: a 60-pt stop "
                     "already gets $267); the trending-regime and cold-streak halves still apply.")
    print(table([r for r in ROWS if r[0] == "refstop"]))


# ------------------------------------------------------------------------------------------------ B3 cold streak / hot streak
def cmd_cold():
    q = "Which cold-streak rule works best? (last N finished signals sum <= X R -> smaller size; never skips a setup)"
    grid = []
    for lb in (10, 12, 15, 20, 25):
        for thr in (-2.0, 0.0, 2.0):
            for size in (0.25, 0.5, 0.75):
                pol = {"cold": {"lookback": lb, "thr": thr, "size": size}}
                S = score(run_account(baseline()[1], pol), baseline()[0])
                grid.append((lb, thr, size, S))
    print("### Cold-streak grid (post-hoc, not saved as runs; one-at-a-time variations below are saved)")
    rows = [[lb, f"{thr:+.0f}R", size, _money(S["spans"]["2026"]["net"]), S["spans"]["2026"]["pf"],
             f"{S['spans']['2026']['p20']:.0f}/{S['spans']['2026']['f20']:.0f}", _money(S["spans"]["2021-25"]["net"]),
             S["spans"]["2021-25"]["pf"], f"{S['spans']['2021-25']['dd']:,}",
             f"{S['spans']['2021-25']['p20']:.0f}/{S['spans']['2021-25']['f20']:.0f}"] for lb, thr, size, S in grid]
    print(_md(rows, ["lookback", "threshold", "cold size", "2026 net", "PF", "1m p/f", "2021-25 net", "PF", "max DD", "1m p/f"]))
    one = [("risk_cold_lb10", "Cold streak judged on the last 10 signals", {"lookback": 10, "thr": 0.0, "size": 0.5}),
           ("risk_cold_lb12", "Cold streak judged on the last 12 signals", {"lookback": 12, "thr": 0.0, "size": 0.5}),
           ("risk_cold_lb20", "Cold streak judged on the last 20 signals", {"lookback": 20, "thr": 0.0, "size": 0.5}),
           ("risk_cold_lb25", "Cold streak judged on the last 25 signals", {"lookback": 25, "thr": 0.0, "size": 0.5}),
           ("risk_cold_thrm2", "Cold only when the last 15 signals are below -2R", {"lookback": 15, "thr": -2.0, "size": 0.5}),
           ("risk_cold_thrp2", "Cold unless the last 15 signals are above +2R", {"lookback": 15, "thr": 2.0, "size": 0.5}),
           ("risk_cold_q25", "Quarter size (not half) in a cold streak", {"lookback": 15, "thr": 0.0, "size": 0.25}),
           ("risk_cold_q75", "Three-quarter size (not half) in a cold streak", {"lookback": 15, "thr": 0.0, "size": 0.75})]
    for id, title, cold in one:
        experiment("cold", id, title, q, pol={"cold": cold}, tags=["cold-streak"],
                   notes=f"Cold-streak filter {cold} (live: lookback 15, threshold 0R, half size). The size cut is applied to the "
                         "engine's micros as the live loop does: max(1, int(micros x size)), so 1-micro trades stay at 1 micro.")
    qh = "Should the bot press when the strategy is hot? (last 15 finished signals sum >= X R -> bigger size)"
    for thr, m in ((5.0, 1.25), (5.0, 1.5), (8.0, 1.5)):
        experiment("cold", f"risk_hot{int(thr)}_{int(m * 100)}", f"Hot-streak boost: x{m:g} when the last 15 signals are +{thr:g}R or better",
                   qh, pol={"hot": {"lookback": 15, "thr": thr, "mult": m}}, tags=["hot-streak"],
                   notes="On top of the live cold-streak half size; max 40 micros.")
    print(table([r for r in ROWS if r[0] == "cold"]))


# ------------------------------------------------------------------------------------------------ B4 account drawdown-aware
def cmd_ddaware():
    q = "Should the bot trade smaller while the account is in a drawdown (back to full size at a new equity high)?"
    rules = (("risk_dd_half1500", "Half size while $1,500+ below the equity high", lambda t, c: 0.5 if c["dd"] <= -1500 else 1.0),
             ("risk_dd_half3000", "Half size while $3,000+ below the equity high", lambda t, c: 0.5 if c["dd"] <= -3000 else 1.0),
             ("risk_dd_linear", "Size shrinks with the drawdown (x0.75 at -$1k, x0.5 at -$2k, floor x0.25)",
              lambda t, c: max(0.25, 1.0 + c["dd"] / 4000.0)))
    for id, title, fn in rules:
        experiment("ddaware", id, title, q, pol={"mult_usd": fn}, tags=["drawdown"], sizing={"rule": title},
                   notes="Drawdown = sized account equity vs its high, from trades finished before entry. The $ risk is scaled "
                         "before rounding to micros (1 micro minimum when the engine takes the setup).")
    print(table([r for r in ROWS if r[0] == "ddaware"]))


# ------------------------------------------------------------------------------------------------ B5 MFFU eval-aware
EVAL_RULES = (
    ("risk_eval_cap50", "Never risk more than half the cushion", "min($ risk, 0.5 x cushion above the trailing max loss)",
     {"cap_usd": lambda t, c: 0.5 * c["cushion"]}),
    ("risk_eval_cap100", "Never risk more than the whole cushion", "min($ risk, 1.0 x cushion): one loss can never fail the eval",
     {"cap_usd": lambda t, c: 1.0 * c["cushion"]}),
    ("risk_eval_prop1000", "Size down once the cushion is under $1,000", "$ risk x min(1, cushion / $1,000)",
     {"mult_usd": lambda t, c: min(1.0, c["cushion"] / 1000.0)}),
    ("risk_eval_prop1500", "Size down once the cushion is under $1,500", "$ risk x min(1, cushion / $1,500)",
     {"mult_usd": lambda t, c: min(1.0, c["cushion"] / 1500.0)}),
    ("risk_eval_prop1000_qty", "Size down under a $1,000 cushion, applied to the routed micros",
     "routed micros x min(1, cushion / $1,000), rounded down, 1 micro minimum (how the live loop applies the cold-streak half)",
     {"post": lambda t, c: min(1.0, c["cushion"] / 1000.0)}),
    ("risk_eval_bank", "Bank the pass: near the target risk only what is needed",
     "once profit >= $2,000: $ risk <= half of what is still needed (a 2R win finishes the eval)",
     {"cap_usd": lambda t, c: 0.5 * c["need"] if c["profit"] >= 2000 else 1e9}),
    ("risk_eval_presslock", "Press after the floor locks (x1.5)", "x1.5 once the trailing max loss has locked at $50,100",
     {"mult_usd": lambda t, c: 1.5 if c["locked"] else 1.0}),
    ("risk_eval_pressup", "Press while the eval is in profit (x1.25)", "x1.25 while the balance is above $50,000",
     {"mult_usd": lambda t, c: 1.25 if c["profit"] >= 0 else 1.0}),
    ("risk_eval_defend", "Defend while the eval is under water (x0.67)", "x0.67 while the balance is below $50,000",
     {"mult_usd": lambda t, c: 1.0 if c["profit"] >= 0 else 0.67}),
)


def eval_judgement(T, pol, raw, B_av=None):
    """Status + verdict for an eval-aware rule, from eval outcomes only (the net of an eval account is not real money):
    2026 and 2021-25 1-month pass/fail and back-to-back (20 start days) passes per year and evals bought per pass."""
    out = {}
    for name, a, z in PERIODS:
        sess = span_sessions(raw, a, z)
        out[name] = {**eval_stats(T, pol, sess), **b2b_avg(T, pol, sess)}
    return out


def eval_status(J, JB):
    def ok(x, y):
        return (x["evals_per_pass"] or 99) <= (y["evals_per_pass"] or 99) - 0.3 and x["pass_yr"] >= y["pass_yr"] - 0.01
    a, b = J["2026"], J["2021-25"]
    A, Bb = JB["2026"], JB["2021-25"]
    if ok(b, Bb) and ok(a, A) and a["f20"] <= A["f20"] and b["f20"] <= Bb["f20"]:
        return "adopt-candidate"
    if ok(b, Bb) and a["pass_yr"] >= A["pass_yr"] - 0.01:
        return "promising"
    return "rejected"


def eval_verdict(J, JB, status):
    b, Bb, a, A = J["2021-25"], JB["2021-25"], J["2026"], JB["2026"]
    head = {"adopt-candidate": "Passes more evals per eval bought in both periods",
            "promising": "Cheaper passes in 2021-25 without fewer passes", "rejected": "No robust eval gain"}[status]
    return (f"{head}. 2021-25: 1-month fails {b['f20']:.1f}% (live {Bb['f20']:.1f}%), passes {b['pass_yr']}/yr ({Bb['pass_yr']}), "
            f"{b['evals_per_pass']} evals per pass ({Bb['evals_per_pass']}). 2026: 1-month pass {a['p20']:.0f}% ({A['p20']:.0f}%), "
            f"{a['evals_per_pass']} evals per pass ({A['evals_per_pass']}). Net shown is eval-account money (not paid out).")


def cmd_eval():
    q = "Can sizing from the eval's state (cushion above the trailing max loss, profit, distance to target) pass more MFFU evals and fail fewer?"
    raw, T, _, B = baseline()
    JB = eval_judgement(T, {}, raw)
    rules = list(EVAL_RULES) + [
        (f"risk_eval_prop1000_usd{int(usd)}", f"Risk ${int(usd)}, sized down once the cushion is under $1,000",
         f"risk_usd {int(usd)}; $ risk x min(1, cushion / $1,000)", {"risk_usd": usd, "mult_usd": _prop1000}) for usd in (1000.0, 1200.0)]
    for id, title, rule, pol in rules:
        J = eval_judgement(T, pol, raw)
        st = eval_status(J, JB)
        experiment("eval", id, title, q, pol=pol, eval_aware=True, sizing={"rule": rule}, tags=["eval"], status=st,
                   verdict=eval_verdict(J, JB, st),
                   notes=f"Rule: {rule}. Applied to the $ risk before rounding to micros (1 micro minimum when the engine "
                         "takes the setup), then the live cold-streak half size. Judged on eval outcomes only: the trades and net "
                         "of this run are back-to-back evals (eval-account money, not paid out).")
    print(table([r for r in ROWS if r[0] == "eval"]))


# ------------------------------------------------------------------------------------------------ B6 situational
SITUATIONAL = (
    # (id, title, factor key, value, multiplier, mechanism)
    ("risk_sit_against1h_half", "Half size against the 1H trend", "1H trend", "against the trade", 0.5,
     "Fading the higher-timeframe trend: the raid is more often continuation than reversal."),
    ("risk_sit_with1h_x15", "1.5x size with the 1H trend", "1H trend", "with the trade", 1.5, "Same mechanism, lean in instead."),
    ("risk_sit_late_half", "Half size when the 15m trend has already turned (late entry)", "15m already turned (late)", "yes", 0.5,
     "Late entry: part of the move is gone, less room to the draw."),
    ("risk_sit_am_half", "Half size in the morning killzone", "Session", "AM (before 12:00)", 0.5,
     "The open is the most volatile (more stop hunts)."),
    ("risk_sit_pm_x15", "1.5x size in the afternoon killzone", "Session", "PM", 1.5, "Same, lean into the calmer afternoon."),
    ("risk_sit_cisd_half", "Half size on CISD triggers (no fair value gap)", "Trigger", "CISD", 0.5,
     "CISD is the fallback trigger when the leg left no gap (weaker displacement)."),
    ("risk_sit_minor_half", "Half size when only a 15m swing was swept", "Pool swept", "minor (15m swing)", 0.5,
     "Minor pools hold less resting liquidity than session / day levels."),
    ("risk_sit_poorloc_half", "Half size on poor location (long in premium / short in discount)", "Location", "poor", 0.5,
     "Buying high in the range leaves less room to the draw."),
    ("risk_sit_vix20_half", "Half size when VIX closed at 20 or higher", "VIX (prior close)", None, 0.5,
     "High-volatility regimes: wider ranges, sweeps run further."),
    ("risk_sit_firsthour_half", "Half size in the first hour (09:30-10:30)", "First hour (09:30-10:30)", "yes", 0.5,
     "Opening-hour noise."),
    ("risk_sit_near_half", "Half size when the draw is under 2R away", "Target distance", "under 2R", 0.5,
     "A near draw pays less per unit of risk."),
    ("risk_sit_trend_quarter", "Quarter size in a trending regime (live: half)", "Regime (10-day)", "trending", 0.5,
     "A reversal model in a trending market (the live rule already halves it)."),
    ("risk_sit_induce_half", "Half size when inducement was taken before the raid", "Inducement taken first", "yes", 0.5,
     "CLAUDE.md open idea 4: the raid already took the obvious liquidity."),
    ("risk_sit_news_x15", "1.5x size on high-impact news days", "News day", "yes", 1.5, "News days move further (bigger draws)."),
    ("risk_sit_thu_half", "Half size on Thursdays (control: no mechanism)", "Weekday", "Thu", 0.5,
     "Control rule with no market mechanism: shows how often noise looks like an edge."),
)


def _sit_pre(key, val, mult):
    def pre(t):
        f = feats(t)
        if key == "VIX (prior close)":
            hit = f[key] in ("20-25", "25+")
        else:
            hit = f[key] == val
        return mult if hit else 1.0
    pre.__doc__ = f"x{mult} when {key} = {val if val else '20+'}"
    return pre


def cmd_situational():
    """Pick on 2021-25 only, then check 2026 untouched. One factor per rule, each with a stated market mechanism."""
    q = "Lean in or size down by one setup condition known at entry? (picked on 2021-25, checked on 2026)"
    raw, T, _, B = baseline()
    picked = []
    rows = []
    for id, title, key, val, mult, mech in SITUATIONAL:
        pol = {"pre": _sit_pre(key, val, mult), "pre_key": id}
        S = score(run_account(T, pol), raw)
        b, Bb = S["spans"]["2021-25"], B["spans"]["2021-25"]
        a, A = S["spans"]["2026"], B["spans"]["2026"]
        sel = b["net"] > Bb["net"] and (b["pf"] or 0) > (Bb["pf"] or 0) and b["p20"] - b["f20"] >= Bb["p20"] - Bb["f20"] - 1.0
        oos = a["net"] > A["net"] and (a["pf"] or 0) >= (A["pf"] or 0)
        status = status_of(S, B) if sel else "rejected"          # same bar as every other run, but only if picked on 2021-25
        verdict = (("Picked on 2021-25 and " + ("held up in 2026" if oos else "did NOT hold up in 2026")) if sel else
                   "Did not improve 2021-25, so not picked") + \
            (f": 2021-25 {_money(b['net'])} vs {_money(Bb['net'])} (PF {b['pf']} vs {Bb['pf']}), 2026 {_money(a['net'])} vs "
             f"{_money(A['net'])} (PF {a['pf']} vs {A['pf']}).")
        experiment("situational", id, title, q, pol=pol, status=status, verdict=verdict, quiet=True, tags=["situational"],
                   sizing={"rule": pol["pre"].__doc__, "mechanism": mech},
                   notes=f"Mechanism: {mech} Selection on 2021-25 only (net and PF up, 1-month eval pass-fail not worse); "
                         f"2026 is the out-of-sample check. {len(SITUATIONAL)} one-factor rules were tried in total.")
        rows.append([id, title, "picked" if sel else "-", _money(b["net"] - Bb["net"]), f"{b['pf']}", _money(a["net"] - A["net"]),
                     f"{a['pf']}", status])
        if sel:
            picked.append(id)
    print(f"### Situational rules: {len(SITUATIONAL)} tried, {len(picked)} picked on 2021-25: {picked}")
    print(_md(rows, ["run", "rule", "2021-25 pick", "2021-25 net vs live", "PF", "2026 net vs live", "PF", "status"]))
    print(table([r for r in ROWS if r[0] == "situational"]))
    # noise check: a random flag on the same share of setups, sized the same way (x mult, live-loop form), vs the baseline
    for id in picked:
        key, val, mult = next((k, v, m) for i, _, k, v, m, _ in SITUATIONAL if i == id)
        hit = {t["entry_t"] for t in T if _sit_pre(key, val, mult)(t) != 1.0}
        S0 = rl.score(run_account(T, {"late_mult": mult, "late_set": hit}), raw)
        g = [S0["spans"][n]["net"] - B["spans"][n]["net"] for n in ("2021-25", "2026")]
        print(f"noise check {id}: {noise_beats(T, raw, B, len(hit) / len(T), mult, g)}")


def noise_beats(T, raw, ref, share, mult, gains, n=200, seed=7):
    """How often a random flag on the same share of setups (x mult, one live-loop multiplier) beats the rule's net gains
    (2021-25, 2026) over the reference score."""
    rng = np.random.default_rng(seed)
    w21 = w26 = both = 0
    base_pol = {"cold": Q25} if ref is not None and ref.get("_q25") else {}
    for k in range(n):
        m = {t["entry_t"] for t in T if rng.random() < share}
        S = rl.score(run_account(T, {**base_pol, "late_mult": mult, "late_set": m}), raw)
        d21 = S["spans"]["2021-25"]["net"] - ref["spans"]["2021-25"]["net"]
        d26 = S["spans"]["2026"]["net"] - ref["spans"]["2026"]["net"]
        w21 += d21 >= gains[0]; w26 += d26 >= gains[1]; both += d21 >= gains[0] and d26 >= gains[1]
    return f"random flags ({share:.0%} of setups, {n} tries) beat it in 2021-25 {100 * w21 / n:.1f}%, 2026 {100 * w26 / n:.1f}%, both {100 * both / n:.1f}%"


# ------------------------------------------------------------------------------------------------ B7 weekly brake, streaks
def cmd_weekly():
    q = "Should the bot slow down after a bad week or a run of losses? (smaller size, never skipping a setup)"
    rules = (("risk_week_brake2r", "Half size after -2R in the week", lambda t, c: 0.5 if c["week_r"] <= -2.0 else 1.0),
             ("risk_week_brake1r", "Half size after -1R in the week", lambda t, c: 0.5 if c["week_r"] <= -1.0 else 1.0),
             ("risk_streak3_half", "Half size after 3 losers in a row (until a winner)", lambda t, c: 0.5 if c["streak"] <= -3 else 1.0),
             ("risk_streak5_half", "Half size after 5 losers in a row (until a winner)", lambda t, c: 0.5 if c["streak"] <= -5 else 1.0),
             ("risk_win_x15", "1.5x size right after a winner", lambda t, c: 1.5 if c["streak"] >= 1 else 1.0))
    for id, title, fn in rules:
        experiment("weekly", id, title, q, pol={"mult_usd": fn}, tags=["brake"], sizing={"rule": title},
                   notes="Week = ISO week; R and streak from this run's trades that finished before entry (a scratch, |R| <= 0.05, "
                         "counts as a non-winner). Applied to the $ risk before rounding (1 micro minimum).")
    print(table([r for r in ROWS if r[0] == "weekly"]))


# ------------------------------------------------------------------------------------------------ packages + recommendation
Q25 = {"lookback": 15, "thr": 0.0, "size": 0.25}
HOT8 = {"lookback": 15, "thr": 8.0, "mult": 1.5}


def _prop1000(t, c):
    """$ risk x min(1, cushion / $1,000)"""
    return min(1.0, c["cushion"] / 1000.0)


PACKAGES = (
    ("risk_pkg_q25_hot8", "Size by the shadow record: quarter size when cold, 1.5x when the last 15 signals are +8R or better",
     {"cold": Q25, "hot": HOT8}, False),
    ("risk_pkg_q25_late", "Quarter size when cold + half size on late entries (15m already turned)",
     {"cold": Q25, "pre": _sit_pre("15m already turned (late)", "yes", 0.5), "pre_key": "late"}, False),
    ("risk_pkg_q25_prop1000", "Quarter size when cold + size down once the eval cushion is under $1,000",
     {"cold": Q25, "mult_usd": _prop1000}, True),
    ("risk_pkg_half_late", "Live half size when cold + half size on late entries (smallest change)", {"late_mult": 0.5}, False),
    ("risk_pkg_q25_late_live", "RECOMMENDED: quarter size when cold, half size on late entries (one multiplier on the micros)",
     {"cold": Q25, "late_mult": 0.5}, False),
)
RECOMMENDED = {"cold": Q25, "late_mult": 0.5}


def cmd_packages():
    q = "Do the best single changes add up? (each tested together, both periods)"
    raw, T, _, B = baseline()
    JB = eval_judgement(T, {}, raw) if any(ea for *_, ea in PACKAGES) else None
    for id, title, pol, ea in PACKAGES:
        st = v = None
        if ea:
            J = eval_judgement(T, pol, raw)
            st = eval_status(J, JB); v = eval_verdict(J, JB, st)
        experiment("packages", id, title, q, pol=pol, eval_aware=ea, tags=["package"], status=st, verdict=v,
                   notes="Combination of single changes that each looked good alone; judged on both periods like any run.")
    print(table([r for r in ROWS if r[0] == "packages"]))


def cold_stretches(T, cold=LIVE_COLD):
    """Longest stretch (calendar weeks, trades) the cold-streak state lasted."""
    runs, cur = [], []
    for t in T:
        c, _ = cold_mult(T, t["_i"], cold)
        if c < 1:
            cur.append(t)
        elif cur:
            runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    out = []
    for r in runs:
        a, z = dt.date.fromisoformat(r[0]["day"]), dt.date.fromisoformat(r[-1]["day"])
        out.append(((z - a).days / 7.0, len(r), r[0]["day"], r[-1]["day"]))
    return sorted(out, reverse=True)


def cmd_recommend():
    """The recommended change (risk-summary.md): one size multiplier on the engine's micros, applied where the live loop
    applies the cold-streak half size today: x0.25 in a cold streak (today x0.5), x0.5 on a late entry (15m trend already
    pointing the trade's way), both = x0.125; rounded down, at least 1 micro. Full table vs the live baseline, plus a
    cross-check against runlib.size (the dashboard's own sizing code)."""
    raw, T, base_tr, B = baseline()
    rec_tr = run_account(T, RECOMMENDED)
    S = score(rec_tr, raw)
    Sq = score(run_account(T, {"cold": Q25}), raw)
    raw_sorted = sorted(raw["trades"], key=lambda t: t["entry_t"])

    def mult(t, ctx):
        cold = rl.cold_status(raw_sorted, t["entry_t"], rl.LIVE_EQF)[0] < 1
        late = (t.get("m15_trend") or 0) * t["dir"] > 0
        return (0.25 if cold else 1.0) * (0.5 if late else 1.0)
    chk = rl.size(raw, eqf=None, rule=mult)
    same = len(chk) == len(rec_tr) and all(a["qty"] == b["qty"] and abs(a["pnl"] - b["pnl"]) < 0.01 for a, b in zip(chk, rec_tr))
    print(f"cross-check vs runlib.size with the same multiplier as a rule: {'identical' if same else 'DIFFERENT'}")
    s26 = span_sessions(raw, "2026-01-01", "2026-12-31"); s21 = span_sessions(raw, "2021-01-01", "2025-12-31")
    rows = []
    spec = (("Trades", "n", str), ("Setups per week", "tpw", lambda v: f"{v:.2f}"), ("Weeks with 2+ setups", "wk2", lambda v: f"{v}%"),
            ("Win rate", "win", lambda v: f"{v}%"), ("Profit factor", "pf", str), ("Net", "net", _money),
            ("Max drawdown", "dd", lambda v: f"-${-v:,}"), ("Worst day", "worst_day", lambda v: f"-${-v:,}"),
            ("Median $ at risk", "risk", lambda v: f"${v:,.0f}"),
            ("Eval pass / fail within 2 weeks", ("p10", "f10"), None), ("Eval pass / fail within 1 month", ("p20", "f20"), None),
            ("Eval pass / fail within 3 months", ("p60", "f60"), None), ("Back-to-back evals passed / failed", "b2b", str))
    for lab, key, fn in spec:
        row = [lab]
        for name in ("2026", "2021-25"):
            for X in (B, S, Sq):
                sp = X["spans"][name]
                row.append(f"{sp[key[0]]:.1f}% / {sp[key[1]]:.1f}%" if isinstance(key, tuple) else fn(sp[key]))
        rows.append(row)
    av = {(n, k): b2b_avg(T, pol, ss) for n, ss in (("2026", s26), ("2021-25", s21))
          for k, pol in (("live", {}), ("rec", RECOMMENDED), ("q25", {"cold": Q25}))}
    rows.append(["Back-to-back from 20 start days: passes / fails per year"] +
                [f"{av[(n, k)]['pass_yr']} / {av[(n, k)]['fail_yr']}" for n in ("2026", "2021-25") for k in ("live", "rec", "q25")])
    rows.append(["Evals bought per pass (same)"] + [f"{av[(n, k)]['evals_per_pass']}" for n in ("2026", "2021-25") for k in ("live", "rec", "q25")])
    print(_md(rows, ["", "2026 live", "2026 recommended", "2026 cold x0.25 only", "2021-25 live", "2021-25 recommended",
                     "2021-25 cold x0.25 only"]))
    yrs = [[y, B["years"][y]["n"], _money(B["years"][y]["net"]), B["years"][y]["pf"], _money(S["years"][y]["net"]), S["years"][y]["pf"],
            _money(Sq["years"][y]["net"]), Sq["years"][y]["pf"]] for y in sorted(S["years"])]
    print(_md(yrs, ["year", "trades", "live net", "PF", "recommended net", "PF", "cold x0.25 only", "PF"]))
    st = cold_stretches(T)
    print("longest cold stretches (weeks, trades, from, to):", [(round(w, 1), n, a, z) for w, n, a, z in st[:5]])
    late = {t["entry_t"] for t in T if (t.get("m15_trend") or 0) * t["dir"] > 0}
    Sq["_q25"] = True
    g = [S["spans"][n]["net"] - Sq["spans"][n]["net"] for n in ("2021-25", "2026")]
    print(f"late-entry half on top of the quarter size: +${g[0]:,} 2021-25, +${g[1]:,} 2026; noise check: "
          f"{noise_beats(T, raw, Sq, len(late) / len(T), 0.5, g, n=400, seed=23)}")
    for name, a, z in PERIODS:
        X = [t for t in rec_tr if a <= t["day"] <= z]
        late = [t for t in X if (t.get("m15_trend") or 0) * t["dir"] > 0]
        print(f"{name}: cold-streak trades {sum(1 for t in X if t['half'])}, late entries {len(late)}, "
              f"trades at 1 micro {sum(1 for t in X if t['qty'] == 1)} of {len(X)} (live {sum(1 for t in base_tr if a <= t['day'] <= z and t['qty'] == 1)})")


def cmd_summary():
    rows = [r for r in rl.index() if r.get("family") == "risk"]
    for r in rows:
        a, b = r["spans"]["2026"], r["spans"]["2021-25"]
        print(f"{r['id']:28s} {r['status']:15s} 2026 {a.get('net', 0):+7,} PF {a.get('pf')} 1m {a.get('p20')}/{a.get('f20')} | "
              f"2021-25 {b.get('net', 0):+7,} PF {b.get('pf')} 1m {b.get('p20')}/{b.get('f20')} | {r['title']}")


def cmd_all():
    cmd_check()
    cmd_anatomy()
    for c in (cmd_levels, cmd_refstop, cmd_cold, cmd_ddaware, cmd_eval, cmd_situational, cmd_weekly, cmd_packages):
        c()
    cmd_recommend()


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
