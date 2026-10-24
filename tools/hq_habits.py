"""HQ habits: four "what a successful trader does" rules on LIT (research only, 2026-10-24).

Judged the LIT way: pick on 2026 H1 (Jan-Jun), check untouched on 2026 H2 (Jul-Oct 16), 2021-25 a reference line. Every rule
is scored on three bases: today's live LIT, the hq-lit candidate set without scale-in (cisd1m 22 + room_f 0.55 + wk_loss_usd
1200) and the same set with scale-in. Two money views: the LIT size rule ($1.90 a micro, as tools/hq_lit.py) and the eval path
(the live two_week sizing, back-to-back evals) on the MFFU Builder 50K and on the Builder 25K preset (engine/account_b /
tools/second_account_b sizing_cfg: 50% room, 20 micros, $600 soft daily loss, soft-daily-loss guard on every trade, stuck at
room < $100 counts as dead = fail).

Rules (pre-declared; default = off = today's behaviour):
  1. news    no new entry (or half size) when the fill is within X min (15 / 30 / 60) of a high-impact US release (CPI, NFP,
             FOMC statement + press conference, PCE, GDP). Skip = engine re-run with the blocked setups removed (a later
             setup of the day may then trade), repeated until no fill sits in a window.
  2. cushion house-money sizing on the eval: extra risk = a share s of the eval profit (s 0.25 / 0.5) on top of two_week;
             "down" = two_week x room / max-loss when the eval is below start; "classic" = the LIT $ rule (no two_week) + 0.5 of
             the profit + the down scaling. LIT-rule view: the same on a running funded-style balance (trailing $2,000 floor).
  3. cooloff after 2 / 3 losing trades in a row the next trade is half size (never a skip); reset on any non-loss, or only on
             a real win (>= +0.5R).
  4. wf      walk-forward self-check: each Sunday, using only trades closed before that week, a weekday (or entry-hour ET)
             bucket with 15+ past trades and a negative R sum trades at half size that week. History = everything since 2021
             or the calendar year to date.

    python -X utf8 tools/hq_habits.py check    # the generic eval runner == tools/hq_lit (live + the combo), 25K plan sanity
    python -X utf8 tools/hq_habits.py run      # every variant x base -> research/hq/habits.json
    python -X utf8 tools/hq_habits.py placebo  # placebo for the candidates -> research/hq/habits_placebo.json
    python -X utf8 tools/hq_habits.py save     # rl.save runs hq_habit_*
Paper only. Edits no engine file and no live_model*.json.
"""
from __future__ import annotations

import collections
import copy
import csv
import datetime as dt
import json
import os
import random
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine import account_b as AB  # noqa: E402
from tools import hq_lit as H  # noqa: E402  (patches lit_adv_manage.run_eval; overridden below)
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402
from tools import second_account_b as SAB  # noqa: E402

OUTD = H.OUTD
ET = ZoneInfo("America/New_York")
PV, SLIP = lit.PV, lit.SLIP
COMM = H.COMM
SCALE = H.SCALE

# ================================================================================================ plans + bases
PLANS = {"50k": {"rules": dict(SZ.TW_50K), "cfg": copy.deepcopy(H.CFG0), "dll_guard": False, "stuck": False, "usd": 800.0,
                 "price": 91.80},
         "25k": {"rules": dict(SZ.TW_25K), "cfg": SAB.sizing_cfg("builder25k"), "dll_guard": True, "stuck": True, "usd": 400.0,
                 "price": 63.00}}
BASES = collections.OrderedDict([
    ("live", {"lab": "live LIT", "x": {}, "c50": {}, "c25": {}}),
    ("combo", {"lab": "hq-lit set without scale-in (cisd1m 22 + room_f 0.55 + wk_loss_usd 1200)", "x": {"cisd1m": 22},
               "c50": {"two_week": {"room_f": 0.55}, "wk_loss_usd": 1200},
               # the 25K preset scaled the same way: room 50% -> 45%, weekly loss stop half of the 50K's
               "c25": {"two_week": {"room_f": 0.45}, "wk_loss_usd": 600}}),
    ("combo_scale", {"lab": "hq-lit set with scale-in", "x": {"cisd1m": 22, "scale_in": SCALE},
                     "c50": {"two_week": {"room_f": 0.55}, "wk_loss_usd": 1200},
                     "c25": {"two_week": {"room_f": 0.45}, "wk_loss_usd": 600}}),
])


def merge(base, over):
    c = copy.deepcopy(base)
    for a, b in (over or {}).items():
        c[a] = {**(c.get(a) or {}), **b} if isinstance(b, dict) else b
    return c


# ================================================================================================ generic eval runner
CUR: dict = {}


def caps_q(t, st, G):
    """Largest micros the plan allows for this trade: room_f of the room, the soft daily loss left today, max micros."""
    R, c = G["rules"], G["cfg"]
    r = float(t["risk"])
    rf = float((c.get("two_week") or {}).get("room_f") or 0.6)
    loss_d = (r + SZ.TW_DLL_SLIP) * SZ.TW_PV + SZ.TW_COMM
    return min(int(R["max_micros"]), int(rf * max(0.0, st["room"]) / (r * PV)), int(max(0.0, R["dll"] + st["cum"]) / loss_d))


def size_q(t, st, G):
    R, c = G["rules"], G["cfg"]
    maxq = int(R["max_micros"])
    risk = float(t["risk"])
    sz = G.get("size")
    m0 = lit.qty_for(risk)
    if t.get("hm") and m0:
        m0 = max(1, int(m0 * float(t["hm"]) + 1e-9))
    if not m0:
        return 0
    eq = st["profit"] + st["cum"]
    if sz and sz[0] == "classic":
        # the LIT $ rule on the plan ($800 / $400 up to a 20-pt stop, then x 20/stop) + s x profit; below start x room / mll
        if eq >= R["target"]:
            return 0
        wl = c.get("wk_loss_usd")
        if wl and st.get("wk_pnl", 0.0) <= -float(wl):
            return 0
        usd = G["usd"] * (1.0 if risk <= 20 else 20.0 / risk) + float(sz[1]) * max(0.0, eq)
        q = int(usd / (risk * PV))
        if eq < 0:
            q = int(q * max(0.0, st["room"]) / R["mll"])
        cap = caps_q(t, st, G)
        if cap < 1:
            return 0
        return max(1, min(q, cap))
    q = SZ.lit_qty(m0, {"risk_pts": risk, "tgt_pts": t.get("tgt_size", t["tgt"]), "size_mult": 1.0}, c, room=st["room"], state=st,
                   max_micros=maxq, learning=None)["qty"]
    if q > 0 and G["dll_guard"]:
        q = AB.dll_guard({"qty": q, "reasons": []}, risk, R, st)["qty"]
    if q <= 0 or not sz:
        return q
    if sz[0] == "hm" and eq > float(sz[2]):
        q2 = q + int(float(sz[1]) * (eq - float(sz[2])) / (risk * PV))
        q = max(q, min(q2, caps_q(t, st, G)))
    elif sz[0] == "down" and eq < 0:
        q = max(1, int(q * max(0.0, st["room"]) / R["mll"] + 1e-9))
    return q


def trade_pnl_g(t, q, qfull, st, G):
    adds = t.get("adds")
    if not adds:
        pnl = A.leg_pnl(t, q)
        return pnl, min(0.0, t["w1"] * PV * q - COMM * q, pnl), q
    R, c = G["rules"], G["cfg"]
    rf = float((c.get("two_week") or {}).get("room_f") or 0.6)
    qa = SZ.scale_in_qty(q, qfull, t["risk"], adds, f=t.get("add_f", 1.0), state=st, room_f=rf, dll=R["dll"],
                         max_micros=int(R["max_micros"]))
    tot = q + sum(qa)
    g = q * t["pts"] * PV
    lows = [q * t["w_pre"] * PV]
    for i, a in enumerate(adds):
        g += qa[i] * a["pts"] * PV
        lows.append((q * a["w_ph"] + sum(qq * (a["w_ph"] - b["dist"]) for qq, b in zip(qa[:i + 1], adds))) * PV)
    pnl = g - COMM * tot
    return pnl, min(0.0, min(lows) - COMM * tot, pnl), tot


def run_eval_g(seq, by, horizon=20, keep=None, cfg=None):
    """One eval on the current plan (CUR): sized by engine/sizing.lit_qty as live (two_week 10 sessions, then safe_eval), the
    eval weekly loss stop state (wk_pnl), a per-trade multiplier t["m"] on the whole position (base + adds), the 25K's soft
    daily loss guard, a rule-2 sizing override (CUR["size"]), and the 25K stuck rule (room < $100 = dead)."""
    G = CUR
    R = G["rules"]
    tgt, mll, dll, lockv = R["target"], R["mll"], R["dll"], R["lock"]
    bal = peak = 0.0
    floor = -mll
    wk_pnl = collections.defaultdict(float)
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        wk = lit.iso_week(A.S26[si])
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0, "wk_pnl": wk_pnl[wk] + cum}
            q = size_q(t, st, G)
            if q <= 0:
                continue
            qfull = q
            m = float(t.get("m", 1.0))
            if m < 1.0 - 1e-9:
                q = max(1, int(q * m + 1e-9))
                qfull = q
            pnl, low, tot = trade_pnl_g(t, q, qfull, st, G)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2)}
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            if keep is not None:
                keep.append(rec)
        bal += cum
        wk_pnl[wk] += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
        if G["stuck"] and bal - floor < 100.0:
            return "FAIL", kk + 1
    return "OPEN", min(len(seq), horizon)


A.run_eval = run_eval_g


def set_plan(plan, over=None, size=None):
    P = PLANS[plan]
    CUR.clear()
    CUR.update(rules=P["rules"], cfg=merge(P["cfg"], over), dll_guard=P["dll_guard"], stuck=P["stuck"], usd=P["usd"], size=size)


def eval_view(U, plan, over=None, size=None):
    set_plan(plan, over, size)
    o = BI.short(A.score(U))
    for s in o:
        o[s]["cost"] = round(PLANS[plan]["price"] / (o[s]["p10"] / 100.0)) if o[s]["p10"] else None
    return o


def eval_path(U, plan, over=None, size=None):
    set_plan(plan, over, size)
    Tp = []
    for sp in ("H1", "H2"):
        Tp += A.b2b(U, sp)[0]
    for t in Tp:
        t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
        t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
    return Tp, copy.deepcopy(CUR["cfg"])


# ================================================================================================ base trades
_BT = {}


def base(bk, extra_x=None):
    """(LIT-rule trades at $1.90, eval units 2026) of base bk + extra engine params (skip_keys)."""
    x = {**BASES[bk]["x"], **(extra_x or {})}
    key = json.dumps(x, sort_keys=True, default=str)
    if key not in _BT:
        T0 = H.run(x)
        _BT[key] = (sorted(H.recost(T0), key=lambda t: t["entry_t"]), H.engine_units(T0))
    T, U = _BT[key]
    return copy.deepcopy(T), copy.deepcopy(U)


def resize(T, mult):
    """Apply a size multiplier m (dict (day, entry_t) -> m) to LIT-rule trades: q' = max(1, int(q x m)) once, P&L scaled
    q'/q (exact for single-entry trades: P&L is linear in micros incl. commission; scale-in trades scale pro rata)."""
    out = []
    for t in T:
        m = mult.get((t["day"], int(t["entry_t"])), 1.0)
        if m == 0.0:
            continue
        if abs(m - 1.0) > 1e-9:
            q = int(t["qty"])
            q2 = max(1, int(q * m + 1e-9)) if m < 1 else min(lit.MAX_MICROS, int(q * m + 1e-9))
            f = q2 / q
            t = dict(t)
            t.update(qty=q2, pnl=round(t["pnl"] * f, 2), low=round(t["low"] * f, 2), risk_usd=round(t["risk_usd"] * f, 2),
                     mult=round(float(t.get("mult") or 1.0) * f, 3), hab=True)
            if t.get("qty_total"):
                t["qty_total"] = int(round(t["qty_total"] * f))
        out.append(t)
    return out


def tag_units(U, mult):
    out = []
    for u in U:
        m = mult.get((u["day"], int(u["entry_t"])), 1.0)
        if m == 0.0:
            continue
        if abs(m - 1.0) > 1e-9:
            u = {**u, "m": float(u.get("m", 1.0)) * m}
        out.append(u)
    return out


# ================================================================================================ rule 1: news calendar
CAL = os.path.join(OUTD, "news_calendar.csv")
# BEA (bea.gov release schedule + release pages, 2026; dates after the Oct-Nov 2025 shutdown re-schedule): GDP and Personal
# Income & Outlays (PCE price index), 08:30 ET unless noted
BEA_2026 = [("2026-01-22", "08:30", "GDP Q3 2025 (updated estimate)"), ("2026-01-22", "10:00", "Personal Income & Outlays / PCE (Oct+Nov 2025)"),
            ("2026-02-20", "08:30", "GDP Q4 2025 advance + PCE (Dec 2025)"), ("2026-03-13", "08:30", "GDP Q4 2025 second + PCE (Jan)"),
            ("2026-04-09", "08:30", "PCE (Feb) + GDP Q4 2025 third"), ("2026-04-30", "08:30", "GDP Q1 advance + PCE (Mar)"),
            ("2026-05-28", "08:30", "PCE (Apr) + GDP Q1 second"), ("2026-06-25", "08:30", "PCE (May) + GDP Q1 third"),
            ("2026-07-30", "08:30", "GDP Q2 advance + PCE (Jun)"), ("2026-08-26", "08:30", "GDP Q2 second + PCE (Jul)"),
            ("2026-09-30", "08:30", "GDP Q2 third + PCE (Aug)"), ("2026-10-29", "08:30", "GDP Q3 advance + PCE (Sep)")]
KEEP = ("CPI (consumer inflation)", "Non-Farm Payrolls (jobs report)", "FOMC rate decision", "FOMC rate decision + projections",
        "FOMC press conference", "GDP Q3 advance estimate", "Personal Income & Outlays / Core PCE (Sep)")


def nfp_rule(y, m):
    """BLS Employment Situation rule: the third Friday after the reference week (the Sun-Sat week holding the 12th) of the
    previous month. Used only before Oct 2023 (data/news/events.csv has the real BLS dates from then on)."""
    pm, py = (m - 1, y) if m > 1 else (12, y - 1)
    d12 = dt.date(py, pm, 12)
    sat = d12 + dt.timedelta(days=(5 - d12.weekday()) % 7)
    return sat + dt.timedelta(days=20)


def build_calendar():
    rows = []
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8")):
        if r["event"] in KEEP:
            rows.append((r["date"], r["time_et"], r["event"], r["source"]))
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "news", "ff_archive.csv"), encoding="utf-8")):
        if r["event"] == "CPI m/m" and r["date"] >= "2026-10-01":
            rows.append((r["date"], r["time_et"], "CPI (consumer inflation)", "forexfactory (repo archive)"))
    for d, tm, ev in BEA_2026:
        rows.append((d, tm, ev, "bea.gov"))
    for y in range(2021, 2024):
        for m in range(1, 13):
            d = nfp_rule(y, m)
            if d < dt.date(2023, 10, 1):
                rows.append((d.isoformat(), "08:30", "Non-Farm Payrolls (jobs report)", "BLS schedule rule (3rd Friday after the reference week)"))
    rows = sorted(set(rows))
    os.makedirs(OUTD, exist_ok=True)
    with open(CAL, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "time_et", "event", "source"])
        w.writerows(rows)
    return rows


_EV = None


def events():
    """Release times as epoch seconds."""
    global _EV
    if _EV is None:
        rows = build_calendar()
        _EV = np.array(sorted({int(dt.datetime.fromisoformat(f"{d}T{tm}:00").replace(tzinfo=ET).timestamp()) for d, tm, _, _ in rows}))
    return _EV


def in_window(t_sec, X):
    E = events()
    i = int(np.searchsorted(E, t_sec))
    near = [E[j] for j in (i - 1, i) if 0 <= j < len(E)]
    return any(abs(int(t_sec) - int(e)) <= X * 60 for e in near)


def news_skip(bk, X):
    """Engine re-run with every setup whose fill lands in a news window removed (later setups of the day may trade)."""
    keys = []
    for _ in range(8):
        T0 = H.run({**BASES[bk]["x"], **({"skip_keys": keys} if keys else {})})
        bad = [(t["day"], int(t["i"]), int(t["dir"])) for t in T0 if in_window(int(t["entry_t"]), X)]
        if not bad:
            break
        keys = sorted(set(keys) | set(bad))
    return {"skip_keys": keys} if keys else {}, len(keys)


# ================================================================================================ rules 3 + 4: multipliers
def cooloff_mult(T, k, reset):
    m, streak = {}, 0
    for t in T:
        if streak >= k:
            m[(t["day"], int(t["entry_t"]))] = 0.5
        if t["pnl"] < 0:
            streak += 1
        elif reset == "any" or float(t["r"]) >= 0.5:
            streak = 0
    return m


def bucket_of(t, kind):
    if kind == "weekday":
        return dt.date.fromisoformat(t["day"]).weekday()
    return dt.datetime.fromtimestamp(int(t["entry_t"]), ET).hour


def wf_mult(T, kind, hist, n_min=15):
    """Each Sunday: from trades of earlier weeks only (all since 2021, or the calendar year to date), a bucket with n_min+
    trades and a negative R sum is halved for the coming week."""
    m, log = {}, []
    past = []
    by_wk = collections.OrderedDict()
    for t in T:
        by_wk.setdefault(lit.iso_week(t["day"]), []).append(t)
    for wk, TT in by_wk.items():
        yr = TT[0]["day"][:4]
        P = past if hist == "all" else [p for p in past if p["day"][:4] == yr]
        agg = collections.defaultdict(lambda: [0, 0.0])
        for p in P:
            a = agg[bucket_of(p, kind)]
            a[0] += 1; a[1] += float(p["r"])
        bad = {b for b, (n, s) in agg.items() if n >= n_min and s < 0}
        if bad:
            log.append({"week": "%d-W%02d" % wk, "halved": sorted(bad)})
        for t in TT:
            if bucket_of(t, kind) in bad:
                m[(t["day"], int(t["entry_t"]))] = 0.5
        past += TT
    return m, log


# ================================================================================================ rule 2 on the LIT rule
def cushion_lit(T, s, down):
    """LIT rule on a running funded-style 50K balance per track (2026 from Jan 2; 2021-25 from its start): extra risk = s x
    the balance above start (at most the base size again); below start x room / $2,000 (trailing floor, locked at +$100)."""
    out = []
    st = {}
    for t in T:
        tr = "2026" if t["day"] >= "2026" else "pre"
        b = st.setdefault(tr, {"bal": 0.0, "peak": 0.0, "floor": -2000.0})
        q = int(t["qty"])
        # the house money on top is capped at the base size (at most 2x): an uncapped share of a growing balance is plain
        # compounding to the 40-micro cap, not a habit
        add = min(q, int(s * max(0.0, b["bal"]) / (float(t["risk_pts"]) * PV))) if s else 0
        q2 = min(lit.MAX_MICROS, q + add)
        if down and b["bal"] < 0:
            q2 = max(1, int(q2 * max(0.0, b["bal"] - b["floor"]) / 2000.0 + 1e-9))
        f = q2 / q
        x = dict(t)
        x.update(qty=q2, pnl=round(t["pnl"] * f, 2), low=round(t["low"] * f, 2), risk_usd=round(t["risk_usd"] * f, 2))
        out.append(x)
        b["bal"] += x["pnl"]
        b["peak"] = max(b["peak"], b["bal"])
        b["floor"] = min(max(b["floor"], b["peak"] - 2000.0), 100.0)
    return out


# ================================================================================================ variants
def variants():
    V = collections.OrderedDict()
    for X in (15, 30, 60):
        V[f"news_skip{X}"] = ("1 news", f"no new entry within {X} min of a high-impact release", {"news": ("skip", X)})
    for X in (15, 30, 60):
        V[f"news_half{X}"] = ("1 news", f"half size within {X} min of a high-impact release", {"news": ("half", X)})
    V["cush_hm25"] = ("2 cushion", "two_week + 25% of the eval profit as extra risk", {"size": ("hm", 0.25, 0.0)})
    V["cush_hm50"] = ("2 cushion", "two_week + 50% of the eval profit as extra risk", {"size": ("hm", 0.5, 0.0)})
    V["cush_down"] = ("2 cushion", "two_week x room / max loss while the eval is below start", {"size": ("down",)})
    V["cush_classic"] = ("2 cushion", "classic house money: LIT $ rule + 50% of profit, x room / max loss when down (no two_week)",
                         {"size": ("classic", 0.5)})
    for k in (2, 3):
        V[f"cool{k}_any"] = ("3 cool-off", f"after {k} losses in a row half size, reset on any non-loss", {"cool": (k, "any")})
        V[f"cool{k}_win"] = ("3 cool-off", f"after {k} losses in a row half size, reset only on a win >= +0.5R", {"cool": (k, "win")})
    for kind in ("weekday", "hour"):
        for hist in ("all", "ytd"):
            V[f"wf_{kind}_{hist}"] = ("4 walk-forward", f"Sunday check: halve a losing {kind} bucket (15+ past trades, history "
                                      f"{'since 2021' if hist == 'all' else 'year to date'})", {"wf": (kind, hist)})
    return V


def build(bk, spec):
    """-> (LIT-rule trades, eval units, size override, info) for one variant on base bk."""
    T, U = base(bk)
    info = {}
    size = spec.get("size")
    if "news" in spec:
        how, X = spec["news"]
        if how == "skip":
            xx, nk = news_skip(bk, X)
            T, U = base(bk, xx)
            info["skipped_setups"] = nk
        else:
            m = {(t["day"], int(t["entry_t"])): 0.5 for t in T if in_window(int(t["entry_t"]), X)}
            T, U = resize(T, m), tag_units(U, m)
            info["halved"] = len(m)
    elif "cool" in spec:
        m = cooloff_mult(T, *spec["cool"])
        T, U = resize(T, m), tag_units(U, m)
        info["halved"] = len(m)
    elif "wf" in spec:
        m, log = wf_mult(T, *spec["wf"])
        T, U = resize(T, m), tag_units(U, m)
        info["halved"] = len(m)
        info["log"] = log
    elif size:
        if size[0] == "hm":
            T = cushion_lit(T, size[1], False)
        elif size[0] == "down":
            T = cushion_lit(T, 0.0, True)
        else:
            T = cushion_lit(T, size[1], True)
    return T, U, size, info


def score(bk, T, U, size=None):
    B = BASES[bk]
    return {"lit": H.lit_view(T), "e50": eval_view(U, "50k", B["c50"], size), "e25": eval_view(U, "25k", B["c25"], size),
            "months": H.months(T)}


def counts(info, T):
    out = {}
    for sp in ("H1", "H2", "2021-25"):
        a, z = H.SPAN[sp]
        out[sp] = sum(1 for t in T if a <= t["day"] <= z and t.get("hab"))
    return out


def gate(o, b):
    """Pre-declared candidate gate (the base = the same base without the rule):
       LIT rule: H1 net > base, H2 net >= base (rule 2 = sizing only: judged on the eval path alone);
       50K eval path: H1 net > base, H2 net >= base; 2-week fail not higher in either half, 2-week pass not lower in H2;
       >= 2 trades a week in both halves."""
    L, Lb, E, Eb = o["lit"], b["lit"], o["e50"], b["e50"]
    lit_ok = L["H1"]["net"] > Lb["H1"]["net"] and L["H2"]["net"] >= Lb["H2"]["net"]
    ev_ok = (E["H1"]["net"] > Eb["H1"]["net"] and E["H2"]["net"] >= Eb["H2"]["net"] and E["H1"]["f10"] <= Eb["H1"]["f10"]
             and E["H2"]["f10"] <= Eb["H2"]["f10"] and E["H2"]["p10"] >= Eb["H2"]["p10"])
    freq = L["H1"]["tpw"] >= 2 and L["H2"]["tpw"] >= 2
    return {"lit": lit_ok, "eval50": ev_ok, "freq": freq}


def line(nm, o):
    L, E, F = o["lit"], o["e50"], o["e25"]
    f = lambda s: f"{L[s]['tpw']}/wk PF {L[s]['pf']} {L[s]['net']:+,}"  # noqa
    g = lambda X, s: f"{X[s]['net']:+,} {X[s]['p10']}/{X[s]['f10']}"  # noqa
    return (f"{nm[:30]:30s} LIT H1[{f('H1')}] H2[{f('H2')}] 21-25[{L['2021-25'].get('net', 0):+,}] | 50K H1[{g(E, 'H1')}] "
            f"H2[{g(E, 'H2')}] | 25K H1[{g(F, 'H1')}] H2[{g(F, 'H2')}]")


# ================================================================================================ commands
def check():
    T0 = H.run()
    U = H.engine_units(T0)
    e = eval_view(U, "50k")
    print("generic runner 50K live:", {s: (e[s]["net"], e[s]["p10"], e[s]["f10"]) for s in e},
          "(hq_lit live: +34,253 57.1/5.9 | +9,059 52.2/0.0)", flush=True)
    T1 = H.run({"cisd1m": 22})
    e = eval_view(H.engine_units(T1), "50k", BASES["combo"]["c50"])
    print("generic runner 50K combo:", {s: (e[s]["net"], e[s]["p10"], e[s]["f10"]) for s in e}, flush=True)
    H.A.run_eval = H.run_eval_hq
    try:
        e2 = H.eval_view(H.engine_units(T1), {"two_week": {"room_f": 0.55}, "wk_loss_usd": 1200})
    finally:
        A.run_eval = run_eval_g
    print("hq_lit runner 50K combo:", {s: (e2[s]["net"], e2[s]["p10"], e2[s]["f10"]) for s in e2}, flush=True)
    e = eval_view(U, "25k")
    print("generic runner 25K live:", {s: (e[s]["net"], e[s]["p10"], e[s]["f10"], e[s]["n"]) for s in e}, flush=True)
    rows = build_calendar()
    yrs = collections.Counter(r[0][:4] for r in rows)
    print("news calendar rows by year:", dict(sorted(yrs.items())), "->", CAL, flush=True)


def run_all():
    V = variants()
    res = {"bases": {}, "variants": {}}
    for bk in BASES:
        T, U = base(bk)
        b = score(bk, T, U)
        res["bases"][bk] = b
        print(line(f"[{bk}]", b), flush=True)
        for nm, (rule, lab, spec) in V.items():
            T2, U2, size, info = build(bk, spec)
            o = score(bk, T2, U2, size)
            o.update(rule=rule, label=lab, spec=spec, info={k: v for k, v in info.items() if k != "log"},
                     changed=counts(info, T2), gate=gate(o, b))
            if "log" in info:
                o["wf_log"] = info["log"]
            if rule == "2 cushion":
                o["gate"]["lit"] = True           # sizing only: judged on the eval path
            o["candidate"] = all(o["gate"].values())
            res["variants"][f"{nm}@{bk}"] = o
            print(line(f"{nm}@{bk}", o) + ("  <-- CANDIDATE" if o["candidate"] else ""), flush=True)
    res["n_tests"] = len(res["variants"])
    res["n_candidates"] = sum(1 for o in res["variants"].values() if o["candidate"])
    H.jdump(res, "habits.json")
    print("tests", res["n_tests"], "candidates", res["n_candidates"], flush=True)
    return res


def placebo(n=200, only=None):
    """For each candidate (or `only`): the same number of trades per half, chosen at random, get the same treatment (half
    size, or dropped for a skip); percentile of the real result among the placebo draws (LIT $ and 50K eval $ / pass)."""
    R = json.load(open(os.path.join(OUTD, "habits.json")))
    V = variants()
    names = only or [k for k, o in R["variants"].items() if o["candidate"]]
    pp = os.path.join(OUTD, "habits_placebo.json")
    out = json.load(open(pp)) if os.path.exists(pp) else {}      # merged: one file for every placebo run
    rng = random.Random(5)
    for key in names:
        nm, bk = key.split("@")
        o = R["variants"][key]
        spec = V[nm][2]
        T, U = base(bk)
        Tv, Uv, size, info = build(bk, spec)
        skip = spec.get("news", ("",))[0] == "skip"
        if skip:
            got = {(t["day"], int(t["entry_t"])) for t in Tv}
            chg = [t for t in T if (t["day"], int(t["entry_t"])) not in got]
        else:
            chg = [t for t in Tv if t.get("hab")]
        k = {sp: sum(1 for t in chg if H.SPAN[sp][0] <= t["day"] <= H.SPAN[sp][1]) for sp in ("H1", "H2", "2021-25")}
        draws = []
        for _ in range(n):
            m = {}
            for sp, kk in k.items():
                pool = [t for t in T if H.SPAN[sp][0] <= t["day"] <= H.SPAN[sp][1]]
                for t in rng.sample(pool, min(kk, len(pool))):
                    m[(t["day"], int(t["entry_t"]))] = 0.0 if skip else 0.5
            Tp, Up = resize(T, m), tag_units(U, m)
            Lp = H.lit_view(Tp)
            Ep = eval_view(Up, "50k", BASES[bk]["c50"])
            draws.append({sp: (Lp[sp]["net"], Ep[sp]["net"] if sp in Ep else None, Ep[sp]["p10"] - Ep[sp]["f10"] if sp in Ep else None)
                          for sp in ("H1", "H2", "2021-25")})
        res = {"k": k}
        for sp in ("H1", "H2", "2021-25"):
            real_l = o["lit"][sp]["net"]
            pl = [d[sp][0] for d in draws]
            res[sp] = {"lit_real": real_l, "lit_pctile": round(100.0 * np.mean([p < real_l for p in pl]), 1),
                       "lit_p50": round(float(np.median(pl)))}
            if sp in o["e50"]:
                er, eo = o["e50"][sp]["net"], o["e50"][sp]["p10"] - o["e50"][sp]["f10"]
                pe = [d[sp][1] for d in draws]; po = [d[sp][2] for d in draws]
                res[sp].update(ev_real=er, ev_pctile=round(100.0 * np.mean([p < er for p in pe]), 1), ev_p50=round(float(np.median(pe))),
                               odds_real=round(eo, 1), odds_pctile=round(100.0 * np.mean([p < eo for p in po]), 1))
        out[key] = res
        print(key, json.dumps(res), flush=True)
    H.jdump(out, "habits_placebo.json")
    return out


Q = ("Owner 2026-10-24: backtest four 'what a successful trader does' habits on LIT (news blackout, house-money / cushion "
     "sizing, cool-off after a loss streak, a walk-forward weekday / hour self-check) and say which ones make money.")


def _h(s):
    return (f"n={s['n']} {s['tpw']}/wk win>0 {s['win0']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}"
            if s.get("n") else "no trades")


def _he(s):
    return (f"PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}; 2-week pass/fail {s['p10']}/{s['f10']}, "
            f"1 month {s['p20']}/{s['f20']}, median {s['pass_med']} sessions")


def save_one(rid, title, bk, T, U, size, o, status, params, plans=("50k",)):
    from tools import runlib as rl
    l = o["lit"]
    keep = ("day", "entry_t", "exit_t", "dir", "r", "pnl", "risk_pts", "qty", "risk_usd", "half", "exit", "trigger", "mfe", "mae",
            "bars_held", "regime", "mult", "low", "entry_px", "stop_px", "target_px")
    Ts = [{k: t.get(k) for k in keep} for t in T]
    P = {**lit.DEFAULTS, **H.LIVE, **BASES[bk]["x"], **(params or {})}
    ev = " ".join(f"Eval path {p.upper()}: H1 {_he(o['e' + p[:2]]['H1'])}; H2 {_he(o['e' + p[:2]]['H2'])}." for p in ("50k", "25k"))
    rl.save(rid, title, "risk", Q, params=P, trades=Ts, scored=rl.score(Ts, H.SESS), status=status,
            verdict=f"LIT size rule ($1.90 a micro): 2026 H1 (pick) {_h(l['H1'])}; H2 (check) {_h(l['H2'])}; 2021-25 reference "
                    f"{_h(l['2021-25'])}. {ev}",
            notes=f"tools/hq_habits.py, base {bk} ({BASES[bk]['lab']}).", writeup="hq-habits", tags=["lit", "hq_habits"])
    for p in plans:
        Tp, c = eval_path(U, p, BASES[bk]["c" + p[:2]], size)
        rl.save(f"{rid}_eval{'' if p == '50k' else '25'}", f"{title} (eval path, MFFU Builder {p.upper()}, two_week sizing)", "risk",
                Q, params=P, sizing={"mode": "two_week", "plan": p, **c}, trades=Tp, scored=rl.score(Tp, A.S26), status=status,
                verdict=f"Eval path {p.upper()}: H1 (pick) {_he(o['e' + p[:2]]['H1'])}. H2 (check) {_he(o['e' + p[:2]]['H2'])}.",
                notes="tools/hq_habits.py: the trades as units, sized by the live two_week rules of the plan (stored trades = "
                      "the back-to-back eval path per half).", writeup="hq-habits", tags=["lit", "hq_habits"])
    print("saved", rid, flush=True)


def save():
    from tools import runlib as rl
    R = json.load(open(os.path.join(OUTD, "habits.json")))
    V = variants()
    idx = rl.index
    rl.index = lambda: None
    try:
        for bk in BASES:
            T, U = base(bk)
            save_one(f"hq_habit_base_{bk}", f"LIT habits study reference: {BASES[bk]['lab']}", bk, T, U, None, R["bases"][bk],
                     "info", {}, plans=("50k", "25k"))
        for key, o in R["variants"].items():
            nm, bk = key.split("@")
            if bk != "live" and not o["candidate"]:
                continue
            rule, lab, spec = V[nm]
            T, U, size, _ = build(bk, spec)
            st = "info" if o["candidate"] else "rejected"   # gate passed on 1-2 trades only: no adopt-candidate
            save_one(f"hq_habit_{nm}" + ("" if bk == "live" else "_" + bk), f"LIT + habit: {lab}" +
                     ("" if bk == "live" else f" (on the {BASES[bk]['lab']})"), bk, T, U, size, o, st, {"hq_habit": spec},
                     plans=("50k", "25k"))
    finally:
        rl.index = idx
    rl.index()


def _k(v):
    return f"{v / 1000:+.1f}k" if v is not None else "-"


def row(lab, o):
    L, E, F = o["lit"], o["e50"], o["e25"]
    return (f"| {lab} | {L['2026']['tpw']} | {L['2026']['win0']} | {L['2026']['pf']} | {_k(L['2026']['net'])} | "
            f"${L['2026']['per_month']:,} | {_k(L['2026']['dd'])} | {_k(L['H1']['net'])} / {L['H1']['pf']} | "
            f"{_k(L['H2']['net'])} / {L['H2']['pf']} | {_k(E['H1']['net'])} / {_k(E['H2']['net'])} | "
            f"{E['H1']['p10']}/{E['H1']['f10']} · {E['H2']['p10']}/{E['H2']['f10']} | {_k(F['H1']['net'])} / {_k(F['H2']['net'])} | "
            f"{F['H1']['p10']}/{F['H1']['f10']} · {F['H2']['p10']}/{F['H2']['f10']} | {_k(L['2021-25'].get('net'))} |")


HDR = ("| variant | 2026 trades/wk | win % (> $0) | PF | 2026 net | $/month | max DD | H1 net / PF | H2 net / PF | 50K eval $ H1 / H2 | "
       "50K 2-wk pass/fail H1 · H2 | 25K eval $ H1 / H2 | 25K 2-wk pass/fail H1 · H2 | 2021-25 net |\n"
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def tables(path_md):
    R = json.load(open(os.path.join(OUTD, "habits.json")))
    L = []
    for bk in BASES:
        L.append(f"\n### Base: {BASES[bk]['lab']}\n\n" + HDR)
        L.append(row(f"**base: {bk}**", R["bases"][bk]))
        for key, o in R["variants"].items():
            nm, b = key.split("@")
            if b == bk:
                L.append(row(f"`{nm}`" + (" (gate passed)" if o["candidate"] else ""), o))
    open(path_md, "w").write("\n".join(L) + "\n")
    print("wrote", path_md)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "run":
        run_all()
    elif cmd == "placebo":
        placebo(only=sys.argv[2].split(",") if len(sys.argv) > 2 else None)
    elif cmd == "save":
        save()
    elif cmd == "tables":
        tables(sys.argv[2])
