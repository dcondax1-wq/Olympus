"""LIT risk & money study (2026-10-20): what is NOT done yet in the sizing / eval-game / funded / portfolio work.

  1. equity-curve sizing on LIT (last-N R sum cold / hot, drawdown from the R peak, after a target, loss streaks): the old
     engine's cold filter re-tested on LIT
  2. eval-game refinements on config C: room share by session (early / late), clock press on C, protect near the target,
     size after the first loss of the eval, $-to-go caps, what to do after session 10 (after_mode, eventual pass), the
     minimum-days trade, and the day to START an eval (day of week, after a LIT loss / win / quiet days)
  3. weekly profit / loss stops (R-based on LIT's own week, and $-based on the eval's week), keeping 2+ trades a week
  4. funded-phase risk: % of the room, Kelly from LIT's R distribution, a risk ramp after each payout, with the $1,500+
     payout policy (lit-money-batch2)
  5. a portfolio of MFFU Builder 50K evals: how many at once / staggered waves at a cash budget, with the 1-sim-funded-
     account rule, Monte Carlo on 2026 paths (H1 / H2)

Every idea is scored on live LIT (run lit_live) AND on top of the adopt-candidate combo (t_check + scale_in + be_off,
research/lit/adopt_combo.json "all3"). Judged the LIT way: 2026 only, pick on H1 (Jan-Jun), check on H2 (Jul-Oct).

Executor: engine/lit.py run_x trades (tools/lit_final.run on live_model.json lit + options) -> units (tools/lit_adopt_combo.units)
-> sized trade by trade by engine/sizing.lit_qty with the exact MFFU 50K eval rules (tools/lit_adv_manage.py evals / mc / b2b,
adds by tools/lit_big_ideas.trade_pnl). run_eval_h below = lit_big_ideas.run_eval_x + hooks; with the hooks off it gives the
published numbers exactly (`check`). Funded: tools/lit_money2.py's MFFU Builder 50K funded model with a size hook.

    python -X utf8 tools/lit_risk_money.py check       # executor == adopt_combo.json (base and all3)
    python -X utf8 tools/lit_risk_money.py grid        # parts 1-3 -> research/lit/risk_money.json
    python -X utf8 tools/lit_risk_money.py funded      # part 4    -> research/lit/risk_money_funded.json
    python -X utf8 tools/lit_risk_money.py portfolio   # part 5    -> research/lit/risk_money_portfolio.json
    python -X utf8 tools/lit_risk_money.py save        # rl.save runs lit_risk_m_*
Paper only. Changes nothing in live_model.json or the engine.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (patches A.run_eval; replaced below)
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "risk_money.json")
OUT_F = os.path.join(ROOT, "research", "lit", "risk_money_funded.json")
OUT_P = os.path.join(ROOT, "research", "lit", "risk_money_portfolio.json")
CACHE = os.path.join(ROOT, "research", "runs", "_cache", "lit_risk_money_units.pkl")
PV, SLIP, ECOMM, DLL = A.PV, A.SLIP, A.ECOMM, A.A50["dll"]
PRICE = 91.80                                   # owner's Builder 50K price (one-time, $0 activation)
VARS = {"base": {}, "all3": {"t_check": AC.T15, "scale_in": AC.SCALE, "be_off": AC.BE_OFF}}
S26 = A.S26
SIDX = {d: i for i, d in enumerate(F.SESS)}


# ================================================================================================ units + causal features
def _feat(T, U):
    """Per 2026 unit: LIT's own history known at its entry (trades exited before it, all years): r list, this ISO week's
    r list, sessions since the previous trade. r = the engine's R (LIT size rule, costs in)."""
    TT = sorted(T, key=lambda t: int(t["entry_t"]))
    ex = sorted(((int(t["exit_t"]), float(t["r"]), t["day"], t["exit"]) for t in TT))
    for u in U:
        e = u["entry_t"]
        h = [x for x in ex if x[0] <= e]
        u["_hist"] = [x[1] for x in h]
        u["_hexit"] = [x[3] for x in h]
        wk = lit.iso_week(u["day"])
        u["_wk"] = [x[1] for x in h if lit.iso_week(x[2]) == wk]
        u["_wk_exit"] = [x[3] for x in h if lit.iso_week(x[2]) == wk]
        u["_gap"] = SIDX[u["day"]] - SIDX[h[-1][2]] if h else 99
    return U


def _cache_path():
    """The units cache keyed by the NQ data (2026-11-03: a rehearsal sandbox, which symlinks research/ and runs on a cut
    NQ_5m.csv, wrote its 31-trade units into the shared un-keyed file and test_eval_lifecycle then found no payout)."""
    from tools import runlib as rl
    return rl.keyed(CACHE)


def load(fresh=False):
    cache = _cache_path()
    if not fresh and os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    out = {}
    for nm, x in VARS.items():
        T = F.run({**AC.LIVE, **x})
        U = AC.units(T)
        if nm == "base" and not AC.check_units(U):
            raise SystemExit("engine units differ from the research executor")
        T6 = [t for t in T if t["day"] >= "2026-01-01"]
        for u, t in zip(U, T6):
            assert u["entry_t"] == int(t["entry_t"])
            u["wk_m"] = 0.5 if t.get("half") else 1.0          # the weekly stop (funded mode keeps it)
        out[nm] = {"T": T, "U": _feat(T, U)}
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    pickle.dump(out, open(cache, "wb"))
    return out


# ================================================================================================ the eval with hooks
G = {"m_fn": None, "cfg_fn": None, "wk_usd": None}


def run_eval_h(seq, by, horizon=20, keep=None, cfg=None):
    """lit_big_ideas.run_eval_x + hooks: G["m_fn"](t, ctx) -> size multiplier (0 = skip the trade; < 1 cut int(q x m) min 1;
    > 1 up to the live caps), G["cfg_fn"](ctx, cfg) -> the lit_sizing cfg for this trade, G["wk_usd"] = (loss, profit): skip
    the rest of the calendar week once the eval's week P&L <= -loss or >= profit. ctx: session, eval state, this eval's
    closed trades [(day, pnl, exit)], the eval's balance."""
    cfg0 = cfg or A.CFG
    tgt, mll, lockv = A.A50["target"], A.A50["mll"], A.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    ev = []
    wk_pnl = collections.defaultdict(float)
    mf, cf, wu = G["m_fn"], G["cfg_fn"], G["wk_usd"]
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        for t in by[si]:
            if cum <= -DLL:
                break
            wk = lit.iso_week(t["day"])
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0, "wk_pnl": wk_pnl[wk]}
            if wu and (wk_pnl[wk] <= -wu[0] or (wu[1] is not None and wk_pnl[wk] >= wu[1])):
                continue
            ctx = {"session": kk + 1, "st": st, "ev": ev, "bal": bal, "wk": wk_pnl[wk]}
            cfg = cf(ctx, cfg0) if cf else cfg0
            m0 = lit.qty_for(t["risk"])
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, cfg, room=st["room"], state=st,
                           learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            qfull = q
            m = float(mf(t, ctx)) if mf else float(t.get("m", 1.0))
            if m <= 0:
                continue
            if m < 1.0 - 1e-9:
                q = max(1, int(q * m + 1e-9))
            elif m > 1.0 + 1e-9:
                q = max(q, min(int(q * m + 1e-9), BI._cap(t, st)))
            pnl, low, tot = BI.trade_pnl(t, q, qfull, st)
            if cum + low <= -DLL:
                pnl = -DLL - cum - SLIP * PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2),
                   "risk_full": round(((t["risk"] + SLIP) * PV + ECOMM) * q, 2), "session": kk + 1}
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            wk_pnl[wk] += pnl
            ev.append((t["day"], pnl, t["exit"]))
            if keep is not None:
                keep.append(rec)
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


A.run_eval = run_eval_h


def hooks(m_fn=None, cfg_fn=None, wk_usd=None):
    G.update(m_fn=m_fn, cfg_fn=cfg_fn, wk_usd=wk_usd)


# ---- eventual pass (no reset: after session 10 the after_mode), exact starts + Monte Carlo of 120 sessions
_EVQ = {}


def eventual(U, n=1000):
    by = A.by_day(U)
    o = {}
    for sp in ("H1", "H2"):
        a, z = A.span_ix(sp)
        ex = [run_eval_h(list(range(k, z)), by, 10 ** 6) for k in range(a, z - 10)]
        if sp not in _EVQ:
            rng = np.random.default_rng(5)
            S = []
            for _ in range(n):
                s = []
                while len(s) < 120:
                    b = int(rng.integers(a, z - 5 + 1))
                    s.extend(range(b, b + 5))
                S.append(s[:120])
            _EVQ[sp] = S
        mcr = [run_eval_h(s, by, 120) for s in _EVQ[sp]]

        def sm(R):
            N = len(R) or 1
            p = [d for r, d in R if r == "PASS"]
            return {"pass": round(100.0 * len(p) / N, 1), "fail": round(100.0 * sum(1 for r, _ in R if r == "FAIL") / N, 1),
                    "pass_med": float(np.median(p)) if p else None, "p15": round(100.0 * sum(1 for d in p if d <= 15) / N, 1),
                    "slow": round(100.0 * sum(1 for d in p if d > 15) / max(1, len(p)), 1)}
        o[sp] = {**sm(ex), "mc": sm(mcr)}
    return o


def risk_stats(U):
    o = {}
    for sp in ("H1", "H2"):
        T, n = A.b2b(U, sp)
        r = [t["risk_full"] for t in T]
        o[sp] = {"risk_max": round(max(r)) if r else None, "risk_med": round(float(np.median(r))) if r else None,
                 "b2b": f"{n['PASS']}/{n['FAIL']}/{n['OPEN']}"}
    return o


def score(U, ev=False):
    A._MC.clear() if False else None
    e = BI.short(BI.score(U))
    rk = risk_stats(U)
    for s in ("H1", "H2"):
        e[s].update(rk[s])
        e[s]["cost2w"] = round(PRICE / (e[s]["p10"] / 100.0)) if e[s]["p10"] else None
    if ev:
        E = eventual(U)
        for s in ("H1", "H2"):
            e[s]["ev"] = E[s]
    return e


def verdict(o, b, money=True):
    """adopt-candidate: in BOTH halves net $ up (money first), 2-week pass not down, 2-week fail not up, and the Monte Carlo
    2-week pass not down / fail not up by more than 1 point; promising: the eval part holds but money is flat or down < 3%."""
    ok_e = all(o[s]["p10"] >= b[s]["p10"] and o[s]["f10"] <= b[s]["f10"] and o[s]["mc_p10"] >= b[s]["mc_p10"] - 1.0
               and o[s]["mc_f10"] <= b[s]["mc_f10"] + 1.0 for s in ("H1", "H2"))
    better = any(o[s]["p10"] > b[s]["p10"] or o[s]["f10"] < b[s]["f10"] or o[s]["net"] > b[s]["net"] for s in ("H1", "H2"))
    ok_m = all(o[s]["net"] > b[s]["net"] for s in ("H1", "H2"))
    ok_tpw = all(o[s]["tpw"] >= 2.0 for s in ("H1", "H2"))
    if ok_e and ok_m and ok_tpw and better:
        return "adopt-candidate"
    if ok_e and ok_tpw and better and all(o[s]["net"] >= 0.97 * b[s]["net"] for s in ("H1", "H2")):
        return "promising"
    return "rejected"


def verdict_eval(o, b):
    """The eval rule (owner): better in H1 AND H2 = in each half 2-week pass not down and 2-week fail not up (exact starts),
    the Monte Carlo not worse by more than 1 point, and at least one of the two strictly better in each half; 2+ trades a
    week on the eval path. Eval-account $ is not cash (it is shown, never a gate)."""
    nw = all(o[s]["p10"] >= b[s]["p10"] and o[s]["f10"] <= b[s]["f10"] and o[s]["mc_p10"] >= b[s]["mc_p10"] - 1.0
             and o[s]["mc_f10"] <= b[s]["mc_f10"] + 1.0 and o[s]["tpw"] >= 2.0 for s in ("H1", "H2"))
    st = all(o[s]["p10"] > b[s]["p10"] or o[s]["f10"] < b[s]["f10"] for s in ("H1", "H2"))
    if nw and st:
        return "adopt-candidate"
    if nw and any(o[s]["p10"] > b[s]["p10"] or o[s]["f10"] < b[s]["f10"] for s in ("H1", "H2")):
        return "promising"
    return "rejected"


def line(nm, o):
    def f(s):
        x = o[s]
        ev = f" ev {x['ev']['pass']}/{x['ev']['fail']} mc {x['ev']['mc']['pass']}" if "ev" in x else ""
        return (f"{x['tpw']}/wk PF {x['pf']} {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,} 2w {x['p10']}/{x['f10']} "
                f"mc {x['mc_p10']}/{x['mc_f10']} risk {x['risk_max']}{ev}")
    return f"{nm[:46]:46s} H1[{f('H1')}] H2[{f('H2')}]"


# ================================================================================================ LIT size rule view (money)
def lit_rule(T, m_of):
    """The engine's own trades ($800 up to a 20-pt stop, weekly stop) re-sized by m_of(trade) (exact: P&L is linear in the
    micros: per-micro points, commission and slippage); 0 = skipped. 2021-25 is the reference line."""
    out = []
    for t in T:
        m = m_of(t)
        if m <= 0:
            continue
        q0 = int(t["qty"])
        q = max(1, int(q0 * m + 1e-9)) if m < 1 else min(40, int(q0 * m + 1e-9)) if m > 1 else q0
        f = q / q0
        out.append({**t, "qty": q, "pnl": round(t["pnl"] * f, 2), "low": round(t.get("low", t["pnl"]) * f, 2),
                    "risk_usd": round(t["risk_usd"] * f, 2)})
    return out


def lit_rule_score(T):
    o = F.score(T, spans=("H1", "H2", "2021-25"), fast=True)
    return o


# ================================================================================================ part 1-3 rules
def _hist_feats(T):
    """For the LIT size rule view: the same causal features on every engine trade (all years)."""
    TT = sorted(T, key=lambda t: int(t["entry_t"]))
    ex = sorted(((int(t["exit_t"]), float(t["r"]), t["day"], t["exit"]) for t in TT))
    F_ = {}
    for t in TT:
        e = int(t["entry_t"])
        h = [x for x in ex if x[0] <= e]
        wk = lit.iso_week(t["day"])
        F_[e] = {"_hist": [x[1] for x in h], "_hexit": [x[3] for x in h], "_wk": [x[1] for x in h if lit.iso_week(x[2]) == wk],
                 "_wk_exit": [x[3] for x in h if lit.iso_week(x[2]) == wk],
                 "_gap": SIDX[t["day"]] - SIDX[h[-1][2]] if h else 99}
    return F_


def m_cold(n, thr=0.0, m=0.5):
    return lambda u: m if len(u["_hist"]) >= n and sum(u["_hist"][-n:]) <= thr else 1.0


def m_hot(n, thr, m=1.5):
    return lambda u: m if len(u["_hist"]) >= n and sum(u["_hist"][-n:]) >= thr else 1.0


def m_dd(k, m=0.5, look=None):
    def f(u):
        h = u["_hist"][-look:] if look else u["_hist"]
        if not h:
            return 1.0
        eq = np.cumsum(h)
        return m if float(eq.max(initial=0.0) - eq[-1]) >= k else 1.0
    return f


def m_after_target(m):
    return lambda u: m if u["_hexit"] and u["_hexit"][-1] == "TARGET" else 1.0


def m_lstreak(k, m):
    def f(u):
        n = 0
        for x in reversed(u["_hexit"]):
            if x == "STOP":
                n += 1
            else:
                break
        return m if n >= k else 1.0
    return f


def m_wk_profit(x, m=0.0):
    return lambda u: m if sum(u["_wk"]) >= x else 1.0


def m_wk_loss(y, m=0.0):
    return lambda u: m if sum(u["_wk"]) <= -y else 1.0


def m_wk_stops(k, m=0.0):
    return lambda u: m if sum(1 for e in u["_wk_exit"] if e == "STOP") >= k else 1.0


def m_wk_target(m=0.0):
    return lambda u: m if any(e == "TARGET" for e in u["_wk_exit"]) else 1.0


def rules_strategy():
    R = {}
    for n in (5, 8, 10, 15, 20):
        for m in (0.5, 0.25):
            R[f"cold: last {n} R <= 0 -> x{m}"] = ("cold", m_cold(n, 0.0, m))
    for n, thr in ((10, -3.0), (15, -3.0), (20, -5.0)):
        R[f"cold: last {n} R <= {thr:g} -> x0.5"] = ("cold", m_cold(n, thr, 0.5))
    for n, thr in ((5, 3.0), (10, 5.0), (15, 8.0), (20, 10.0)):
        for m in (1.25, 1.5):
            R[f"hot: last {n} R >= {thr:g} -> x{m}"] = ("hot", m_hot(n, thr, m))
    for k in (3.0, 5.0, 8.0, 12.0):
        for m in (0.5, 0.25):
            R[f"R drawdown from peak >= {k:g}R -> x{m}"] = ("dd", m_dd(k, m))
    for m in (0.5, 1.5):
        R[f"after a LIT target -> x{m}"] = ("streak", m_after_target(m))
    for k in (2, 3, 4):
        for m in (0.5, 1.5):
            R[f"after {k} stop-outs in a row -> x{m}"] = ("streak", m_lstreak(k, m))
    # part 3: weekly stops on LIT's own week (R closed earlier in the same ISO week)
    for x in (2.0, 3.0, 5.0, 8.0):
        R[f"week: stop after +{x:g}R closed"] = ("week", m_wk_profit(x, 0.0))
        R[f"week: half after +{x:g}R closed"] = ("week", m_wk_profit(x, 0.5))
    R["week: stop after a target"] = ("week", m_wk_target(0.0))
    R["week: half after a target"] = ("week", m_wk_target(0.5))
    for y in (1.0, 1.5, 2.0, 3.0):
        R[f"week: stop after -{y:g}R closed"] = ("week", m_wk_loss(y, 0.0))
    for k in (1, 2, 3):
        R[f"week: stop after {k} stop-out(s)"] = ("week", m_wk_stops(k, 0.0))
        R[f"week: half after {k} stop-out(s)"] = ("week", m_wk_stops(k, 0.5))
    return R


# ---- part 2: eval-state rules (cfg_fn / m_fn on the eval context)
def _tw(cfg, **kw):
    return {**cfg, "two_week": {**cfg["two_week"], **kw}}


def cf_room(early, late, at=6):
    return lambda ctx, cfg: _tw(cfg, room_f=early if ctx["session"] < at else late)


def cf_press(at, mult, room=None):
    return lambda ctx, cfg: _tw(cfg, press_at=at, press_mult=mult, press_room=room)


def cf_protect(over, keep):
    return lambda ctx, cfg: _tw(cfg, protect_over=over, protect_keep=keep)


def cf_after_loss(k, room=None, mult=None):
    """After k losing trades in this eval: room share `room` and / or a size multiplier (through m_fn)."""
    def f(ctx, cfg):
        nl = sum(1 for _, p, _e in ctx["ev"] if p < 0)
        return _tw(cfg, room_f=room) if nl >= k and room is not None else cfg
    return f


def mf_after_loss(k, m):
    return lambda t, ctx: m if sum(1 for _, p, _e in ctx["ev"] if p < 0) >= k else 1.0


def mf_last_loss(m):
    return lambda t, ctx: m if ctx["ev"] and ctx["ev"][-1][1] < 0 else 1.0


def cf_maxusd_near(to_go, usd):
    """Once the eval needs <= to_go $, cap a trade's full stop-out at usd."""
    def f(ctx, cfg):
        need = A.A50["target"] - ctx["st"]["profit"] - ctx["st"]["cum"]
        return _tw(cfg, max_usd=usd) if need <= to_go else cfg
    return f


def cf_need_buf(early_buf, until=3):
    return lambda ctx, cfg: _tw(cfg, need_buf=early_buf) if ctx["session"] <= until else cfg


def cf_after(mode, **kw):
    """after session 10: after_mode (+ a different safe_cap or a two_week room)."""
    def f(ctx, cfg):
        c = {**cfg, "after_mode": mode, **{k: v for k, v in kw.items() if k != "room_f"}}
        if mode == "two_week":
            c["two_week_until"] = None
            if ctx["session"] > 10 and "room_f" in kw:
                c = _tw(c, room_f=kw["room_f"])
        return c
    return f


def rules_eval():
    R = {}
    for e, l in ((0.5, 0.6), (0.5, 0.7), (0.6, 0.7), (0.6, 0.8), (0.6, 1.0), (0.5, 0.8), (0.7, 0.6), (0.7, 0.7), (0.7, 0.5),
                 (0.6, 0.5)):
        for at in (4, 6, 8):
            if (e, l, at) in ((0.7, 0.7, 4), (0.7, 0.7, 8)):
                continue
            R[f"room {e:g} sessions 1-{at - 1}, {l:g} from {at}"] = ("room", cf_room(e, l, at), None)
    for at in (5, 6, 8):
        for mult in (1.5, 2.0):
            R[f"press x{mult:g} from session {at}"] = ("press", cf_press(at, mult), None)
    for over in (1500.0, 2000.0, 2500.0):
        for keep in (0.3, 0.5, 0.7):
            R[f"protect: over +${over:,.0f} keep {keep:g}"] = ("protect", cf_protect(over, keep), None)
    for to_go, usd in ((1000, 400), (1500, 600), (1000, 600), (2000, 800)):
        R[f"near target: need <= ${to_go:,} -> max ${usd} a stop-out"] = ("near", cf_maxusd_near(to_go, usd), None)
    for k in (1, 2):
        for room in (0.4, 0.5, 0.8):
            R[f"after {k} eval loss(es): room {room:g}"] = ("loss", cf_after_loss(k, room), None)
        for m in (0.5, 0.75, 1.5):
            R[f"after {k} eval loss(es): x{m:g}"] = ("loss", None, mf_after_loss(k, m))
    for m in (0.5, 1.5):
        R[f"right after an eval loss: x{m:g}"] = ("loss", None, mf_last_loss(m))
    for b, u in ((1.25, 3), (1.5, 3), (0.75, 2)):
        R[f"need_buf {b:g} in sessions 1-{u}"] = ("need", cf_need_buf(b, u), None)
    for usd in (300.0, 500.0):
        pass
    for loss, prof in ((500.0, None), (800.0, None), (1000.0, None), (1500.0, None)):
        R[f"eval week: stop after -${loss:,.0f}"] = ("week$", ("wk", (loss, prof)), None)
    return R


def rules_after():
    return {"after 10: safe_eval 60% (live)": cf_after("safe_eval", safe_cap=0.6),
            "after 10: safe_eval 40%": cf_after("safe_eval", safe_cap=0.4),
            "after 10: safe_eval 80%": cf_after("safe_eval", safe_cap=0.8),
            "after 10: eval ($800 to 25 pts + 60% room)": cf_after("eval"),
            "after 10: normal LIT size (no room cap)": cf_after("normal"),
            "after 10: fast_eval ($800 to 40 pts)": cf_after("fast_eval"),
            "after 10: two_week continues (60% room)": cf_after("two_week", room_f=0.6),
            "after 10: two_week at 40% room": cf_after("two_week", room_f=0.4),
            "after 10: two_week at 50% room": cf_after("two_week", room_f=0.5)}


# ---- start-day study (fresh evals by the start session's condition, causal)
def starts(U, spans=("H1", "H2")):
    by = A.by_day(U)
    T = sorted(U, key=lambda t: t["entry_t"])
    # LIT's history known at the START of each session: trades of earlier sessions
    prev = {}
    for i, d in enumerate(S26):
        h = [t for t in T if t["day"] < d]
        prev[i] = h
    full = {}
    for sp in spans:
        a, z = A.span_ix(sp)
        rows = []
        for i in range(a, z - 10 + 1):
            r, k = run_eval_h(list(range(i, min(z, i + 20))), by)
            h = prev[i]
            last = h[-1] if h else None
            quiet = i - S26.index(last["day"]) - 1 if last else 99
            lr = [x["pts"] / x["risk"] for x in h]
            rows.append({"i": i, "dow": dt.date.fromisoformat(S26[i]).weekday(), "res": r, "k": k,
                         "last": (last["exit"] if last else None), "quiet": quiet,
                         "nw2": len(h) >= 2 and all(x["exit"] != "TARGET" for x in h[-2:]),
                         "nw3": len(h) >= 3 and all(x["exit"] != "TARGET" for x in h[-3:]),
                         "l5": sum(lr[-5:]) if len(lr) >= 5 else None})
        full[sp] = rows
    conds = {"any session": lambda r: True}
    for d, nm in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")):
        conds[nm] = (lambda dd: (lambda r: r["dow"] == dd))(d)
    conds.update({"after a LIT stop-out": lambda r: r["last"] == "STOP", "after a LIT target": lambda r: r["last"] == "TARGET",
                  "after a LIT breakeven": lambda r: r["last"] == "BE",
                  "after 1+ quiet sessions (no LIT trade)": lambda r: r["quiet"] >= 1,
                  "after 2+ quiet sessions": lambda r: r["quiet"] >= 2,
                  "the session after a LIT trade": lambda r: r["quiet"] == 0,
                  "after 2 non-winners": lambda r: r["nw2"], "after 3 non-winners": lambda r: r["nw3"],
                  "last 5 LIT trades <= 0R": lambda r: r["l5"] is not None and r["l5"] <= 0,
                  "last 5 LIT trades > 0R": lambda r: r["l5"] is not None and r["l5"] > 0})
    out = {}
    for nm, c in conds.items():
        o = {}
        for sp in spans:
            R = [r for r in full[sp] if c(r)]
            N = len(R) or 1
            o[sp] = {"n": len(R), "p10": round(100.0 * sum(1 for r in R if r["res"] == "PASS" and r["k"] <= 10) / N, 1),
                     "f10": round(100.0 * sum(1 for r in R if r["res"] == "FAIL" and r["k"] <= 10) / N, 1),
                     "blocks": len({r["i"] // 10 for r in R})}
        out[nm] = o
    return out


# ================================================================================================ part 1-3 driver
def eval_grid():
    D = load()
    res = {"_meta": {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                     "note": "eval path: live two_week (config C) 10 sessions then safe_eval, no reset, $1.90, true 1m"}}
    for vn in ("base", "all3"):
        U0, T = D[vn]["U"], D[vn]["T"]
        HF = _hist_feats(T)
        hooks()
        for u in U0:
            u.pop("m", None)
        b = score(U0, ev=True)
        lr_b = lit_rule_score(T)
        R = {"_base": {"eval": b, "lit_rule": lr_b}}
        print(line(f"{vn} base", b), flush=True)
        # ---- part 1 + 3 (strategy-level multipliers: same on the eval path and the LIT size rule)
        for nm, (grp, fn) in rules_strategy().items():
            for u in U0:
                u["m"] = fn(u)
            o = score(U0)
            lr = lit_rule_score(lit_rule(T, lambda t: fn(HF[int(t["entry_t"])])))
            ch = sum(1 for u in U0 if abs(u["m"] - 1.0) > 1e-9)
            R[nm] = {"group": grp, "eval": o, "lit_rule": lr, "changed": ch, "verdict": verdict(o, b)}
            print(line(f"{vn} {nm}", o) + f" chg {ch} {R[nm]['verdict']}", flush=True)
        for u in U0:
            u.pop("m", None)
        # ---- part 2 (eval-state rules)
        for nm, (grp, cfn, mfn) in rules_eval().items():
            if isinstance(cfn, tuple):
                hooks(wk_usd=cfn[1])
            else:
                hooks(m_fn=mfn, cfg_fn=cfn)
            o = score(U0)
            R[nm] = {"group": grp, "eval": o, "verdict": verdict(o, b)}
            print(line(f"{vn} {nm}", o) + f" {R[nm]['verdict']}", flush=True)
        hooks()
        # ---- after session 10 (eventual pass, no reset)
        for nm, cfn in rules_after().items():
            hooks(cfg_fn=cfn)
            o = score(U0, ev=True)
            R[nm] = {"group": "after10", "eval": o}
            print(line(f"{vn} {nm}", o), flush=True)
        hooks()
        # ---- minimum days: passes on session 1 (a 2nd traded day needed: the 1-micro trade)
        by = A.by_day(U0)
        p1 = {}
        for sp in ("H1", "H2"):
            a, z = A.span_ix(sp)
            rs = [run_eval_h(list(range(i, min(z, i + 20))), by) for i in range(a, z - 10 + 1)]
            ps = [k for r, k in rs if r == "PASS"]
            p1[sp] = {"passes": len(ps), "on_session_1": sum(1 for k in ps if k == 1)}
        R["_min_days"] = p1
        R["_starts"] = starts(U0)
        res[vn] = R
        json.dump(res, open(OUT, "w"), indent=1, default=float)
    return res


def m_wk_stopout(m=0.0):
    """eval week: no more trades this calendar week once this eval had a stop-out in it (m_fn on the eval context)."""
    def f(t, ctx):
        wk = lit.iso_week(t["day"])
        return m if any(e == "STOP" and lit.iso_week(d) == wk for d, p, e in ctx["ev"]) else 1.0
    return f


def round2():
    """Neighbours of the round-1 leads, all with the eventual pass: the eval-week $ stop, safe_cap after session 10, and
    the start rules 'last N LIT trades <= 0R' (fresh starts) + the b2b policy that waits for it."""
    D = load()
    res = json.load(open(OUT, encoding="utf-8"))
    for vn in ("base", "all3"):
        U0 = D[vn]["U"]
        for u in U0:
            u.pop("m", None)
        hooks()
        b = score(U0, ev=True)
        R = {"_base": b}
        V = {}
        for loss in (600.0, 700.0, 800.0, 900.0, 1000.0, 1200.0, 1500.0, 2000.0):
            V[f"eval week: stop after -${loss:,.0f}"] = dict(wk_usd=(loss, None))
        V["eval week: stop after a stop-out"] = dict(m_fn=m_wk_stopout(0.0))
        V["eval week: half after a stop-out"] = dict(m_fn=m_wk_stopout(0.5))
        for cap in (0.3, 0.4, 0.5):
            V[f"after 10: safe_eval {int(cap * 100)}%"] = dict(cfg_fn=cf_after("safe_eval", safe_cap=cap))
        V["eval week -$800 + after 10: safe_eval 40%"] = dict(wk_usd=(800.0, None), cfg_fn=cf_after("safe_eval", safe_cap=0.4))
        for nm, kw in V.items():
            hooks(**kw)
            o = score(U0, ev=True)
            R[nm] = {"eval": o, "verdict": verdict_eval(o, b)}
            print(line(f"{vn} {nm}", o) + " " + R[nm]["verdict"], flush=True)
        hooks()
        R["_start_rules"] = start_rules(U0)
        res.setdefault("round2", {})[vn] = R
        json.dump(res, open(OUT, "w"), indent=1, default=float)
    return res


def start_rules(U):
    """'Start only after the last N LIT trades sum <= thr R' (known at the start session): fresh starts in each half, and
    the back-to-back policy that waits for the condition after each pass / fail (sessions waited count as calendar time)."""
    by = A.by_day(U)
    T = sorted(U, key=lambda t: t["entry_t"])
    pre = []
    for i, d in enumerate(S26):
        pre.append([x["pts"] / x["risk"] for x in T if x["day"] < d])
    out = {}
    for n in (0, 3, 4, 5, 6, 8, 10):
        for thr in ((0.0,) if n else (None,)):
            ok = (lambda i: True) if not n else (lambda i, n=n, thr=thr: len(pre[i]) >= n and sum(pre[i][-n:]) <= thr)
            nm = "any session" if not n else f"last {n} LIT trades <= {thr:g}R"
            o = {}
            for sp in ("H1", "H2"):
                a, z = A.span_ix(sp)
                rs = [(run_eval_h(list(range(i, min(z, i + 20))), by), i) for i in range(a, z - 10 + 1) if ok(i)]
                N = len(rs) or 1
                # back to back with waiting: after a pass / fail start again at the first session that meets the rule
                k, P, Fl, used = a, 0, 0, 0
                while k < z:
                    while k < z and not ok(k):
                        k += 1
                    if k >= z:
                        break
                    r, u = run_eval_h(list(range(k, z)), by, z - k)
                    if r == "OPEN":
                        break
                    P += r == "PASS"; Fl += r == "FAIL"
                    k += u
                o[sp] = {"n": len(rs), "p10": round(100.0 * sum(1 for (r, kk), _ in rs if r == "PASS" and kk <= 10) / N, 1),
                         "f10": round(100.0 * sum(1 for (r, kk), _ in rs if r == "FAIL" and kk <= 10) / N, 1),
                         "share": round(100.0 * len(rs) / max(1, z - 10 + 1 - a), 1), "b2b_pass": P, "b2b_fail": Fl,
                         "blocks": len({i // 10 for _, i in rs})}
            out[nm] = o
            print(f"  start {nm:28s} " + " | ".join(f"{s} n={o[s]['n']} ({o[s]['share']}%) 2w {o[s]['p10']}/{o[s]['f10']} b2b {o[s]['b2b_pass']}/{o[s]['b2b_fail']}"
                                                  for s in ("H1", "H2")), flush=True)
    return out


def ref2125(span="2021-25"):
    """2021-25 reference (never a gate): the live LIT unit trades of tools/lit_2wk.py build (5m entries there, no 1m),
    fresh evals on every session with the same eval runner: base, the eval-week $ stop, safe_cap after 10, start rules."""
    from tools import lit_2wk as W
    Dw = W.data()
    by = []
    for day in Dw["by"]:
        by.append([{**t, "legs": t.get("legs") or [(1.0, t["pts"])], "entry_t": int(t["entry_t"]),
                    "exit_t": int(t["exit_t"])} for t in day])
    a, z = W.span_idx(span)
    pre = []
    acc = []
    for i in range(len(Dw["sess"])):
        pre.append(list(acc))
        acc += [t["pts"] / t["risk"] for t in by[i]]
    V = {"base (config C)": {}, "eval week: stop after -$800": dict(wk_usd=(800.0, None)),
         "eval week: stop after -$1,200": dict(wk_usd=(1200.0, None)),
         "eval week: stop after -$1,500": dict(wk_usd=(1500.0, None)),
         "after 10: safe_eval 40%": dict(cfg_fn=cf_after("safe_eval", safe_cap=0.4))}
    out = {}
    for nm, kw in V.items():
        hooks(**kw)
        rs = [run_eval_h(list(range(i, min(z, i + 20))), by) for i in range(a, z - 10 + 1)]
        ev = [run_eval_h(list(range(i, z)), by, 120) for i in range(a, z - 10 + 1)]
        N = len(rs)
        out[nm] = {"n": N, "p10": round(100.0 * sum(1 for r, k in rs if r == "PASS" and k <= 10) / N, 1),
                   "f10": round(100.0 * sum(1 for r, k in rs if r == "FAIL" and k <= 10) / N, 1),
                   "ev_pass": round(100.0 * sum(1 for r, k in ev if r == "PASS") / N, 1),
                   "ev_fail": round(100.0 * sum(1 for r, k in ev if r == "FAIL") / N, 1)}
        print(f"2021-25 {nm:36s} {out[nm]}", flush=True)
    hooks()
    rs = {i: run_eval_h(list(range(i, min(z, i + 20))), by) for i in range(a, z - 10 + 1)}
    for n in (3, 5, 8, 10):
        ii = [i for i in rs if len(pre[i]) >= n and sum(pre[i][-n:]) <= 0]
        N = len(ii) or 1
        out[f"start: last {n} LIT trades <= 0R"] = {"n": len(ii), "p10": round(100.0 * sum(1 for i in ii if rs[i][0] == "PASS" and rs[i][1] <= 10) / N, 1),
                                                   "f10": round(100.0 * sum(1 for i in ii if rs[i][0] == "FAIL" and rs[i][1] <= 10) / N, 1)}
        ii = [i for i in rs if len(pre[i]) >= n and sum(pre[i][-n:]) > 0]
        N = len(ii) or 1
        out[f"start: last {n} LIT trades > 0R"] = {"n": len(ii), "p10": round(100.0 * sum(1 for i in ii if rs[i][0] == "PASS" and rs[i][1] <= 10) / N, 1),
                                                  "f10": round(100.0 * sum(1 for i in ii if rs[i][0] == "FAIL" and rs[i][1] <= 10) / N, 1)}
        print(f"2021-25 start last {n} <= 0R {out[f'start: last {n} LIT trades <= 0R']} | > 0R {out[f'start: last {n} LIT trades > 0R']}", flush=True)
    res = json.load(open(OUT, encoding="utf-8"))
    res["ref_2021_25"] = out
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    return out


def episodes():
    """How many separate episodes the start rule 'last N <= 0R' covers (runs of consecutive qualifying sessions)."""
    D = load()
    for vn in ("base", "all3"):
        T = sorted(D[vn]["U"], key=lambda t: t["entry_t"])
        pre = [[x["pts"] / x["risk"] for x in T if x["day"] < d] for d in S26]
        for n in (5, 8, 10):
            ok = [len(p) >= n and sum(p[-n:]) <= 0 for p in pre]
            for sp in ("H1", "H2"):
                a, z = A.span_ix(sp)
                runs, prev = 0, False
                for i in range(a, z - 10 + 1):
                    if ok[i] and not prev:
                        runs += 1
                    prev = ok[i]
                print(vn, n, sp, "episodes", runs)


# ================================================================================================ part 4: funded
AF = dict(SZ.FD_50K)
REC = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]["funded"]


def by_full(U):
    """Units on tools/lit_2wk.py's session index (all sessions since 2021-11; 2026 days filled) so that
    tools/lit_funded.mc_seqs gives the same Monte Carlo paths as lit-funded-sizing / lit-money-batch2."""
    from tools import lit_2wk as W
    sess = W.data()["sess"]
    ix = {d: i for i, d in enumerate(sess)}
    by = [[] for _ in sess]
    for u in U:
        by[ix[u["day"]]].append(u)
    return by


def funded_run(sizer, policy, seq, by, keep=None):
    """tools/lit_money2.py funded run (MFFU Builder 50K funded, $1.90) with sizer(t, st, ctx) -> micros (ctx: payouts so far,
    the account's peak balance) and adds through lit_big_ideas.trade_pnl. policy as lit_money2: ("asap", 0) / ("atl", h)."""
    mll, dll, lockv = AF["mll"], AF["dll"], AF["lock"]
    bal = peak = 0.0
    floor = -mll
    paid = 0.0
    n_pay, first, last_bal, cyc = 0, None, 0.0, []
    pay_at = []
    max_risk = 0.0
    for k, si in enumerate(seq):
        cum = 0.0
        traded = False
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"room": bal + cum - floor, "cum": cum, "locked": floor >= lockv - 1e-9, "bal": bal, "session": 99}
            q = sizer(t, st, {"n_pay": n_pay, "peak": peak, "k": k})
            if q <= 0:
                continue
            traded = True
            pnl, low, tot = BI.trade_pnl(t, q, q, st)
            max_risk = max(max_risk, (t["risk"] + SLIP) * PV * q + ECOMM * q)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * tot
                low = pnl
            if keep is not None:
                keep.append(_trade_rec(t, tot, q, pnl if bal + cum + low > floor else floor - bal - cum, low))
            if bal + cum + low <= floor:
                return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": k + 1, "grad": None,
                        "max_risk": max_risk, "end_bal": bal + cum + low}
            cum += pnl
        bal += cum
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if traded:
            cyc.append(cum)
        if k + 1 < AF["first_wait"] or len(cyc) < AF["cycle_days"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or (cyc and max(cyc) > AF["cons"] * prof):
            continue
        avail = bal - AF["buffer"]
        pol, h = policy
        amt = min(avail, AF["pay_max"]) if (pol == "asap" or avail >= h) else 0.0
        if amt < AF["pay_min"]:
            continue
        paid += amt * AF["split"]
        n_pay += 1
        pay_at.append((k + 1, amt * AF["split"]))
        first = first or k + 1
        bal -= amt
        last_bal, cyc = bal, []
        if n_pay >= AF["max_payouts"]:
            return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": k + 1,
                    "max_risk": max_risk, "end_bal": bal}
    return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": None, "max_risk": max_risk,
            "end_bal": bal}


def _trade_rec(t, tot, q, pnl, low):
    ru = t["risk"] * PV * q
    return {"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": round(pnl / ru, 3) if ru else 0.0,
            "pnl": round(pnl, 2), "low": round(low, 2), "risk_pts": t["risk"], "qty": tot, "risk_usd": round(ru, 2), "half": False,
            "exit": t["exit"], "trigger": "LIT-1m" if t.get("on1") else "LIT-5m", "mfe": None, "mae": None, "bars_held": None,
            "regime": "", "mult": None, "tgt_pts": t["tgt"]}


def funded_b2b(sizer, policy, U, span):
    """Real 2026 history of the half: a funded account from the half's first session, a new one after a loss / graduation."""
    by = A.by_day(U)
    a, z = A.span_ix(span)
    k, T, n, paid = a, [], collections.Counter(), 0.0
    while k < z:
        r = funded_run(sizer, policy, list(range(k, z)), by, keep=T)
        paid += r["paid"]
        if r["blown"]:
            n["lost"] += 1; k += r["blown"]
        elif r["grad"]:
            n["graduated"] += 1; k += r["grad"]
        else:
            n["open"] += 1; break
    return T, {"accounts": sum(n.values()), **n, "paid": round(paid)}


def funded_mc(sizer, policy, by, span):
    from tools import lit_funded as LF
    R = [funded_run(sizer, policy, s, by) for s in LF.mc_seqs(span)]
    o = {}
    for lab, h in (("3m", LF.H3), ("6m", LF.H6)):
        lost = [r for r in R if r["blown"] and r["blown"] <= h]
        paid = [sum(x for kk, x in r["pay_at"] if kk <= h) for r in R]
        o[f"loss_{lab}"] = round(100.0 * len(lost) / len(R), 1)
        o[f"paid_{lab}"] = round(float(np.mean(paid)))
        o[f"paid_p10_{lab}"] = round(float(np.percentile(paid, 10)))
    o["per_month"] = round(o["paid_6m"] / 6.0)
    fr = [r["first"] for r in R if r["first"]]
    o["first_med"] = float(np.median(fr)) if fr else None
    o["max_risk"] = round(max(r["max_risk"] for r in R))
    o["npay"] = round(float(np.mean([r["n"] for r in R])), 2)
    o["grad_6m"] = round(100.0 * sum(1 for r in R if r["grad"] and r["grad"] <= LF.H6) / len(R), 1)
    return o


def kelly_units(U, span):
    """Full Kelly fraction of the bankroll on LIT's 1-micro trades of the half: R = 1-micro $ result / 1-micro full stop-out
    (2 ticks of slippage, $1.90); bankroll = the room to the funded floor (losing it = losing the account)."""
    a, z = A.SPANS[span]
    R = []
    for t in U:
        if a <= t["day"] <= z:
            loss1 = (t["risk"] + 2 * SLIP) * PV + ECOMM
            R.append((t["pts"] * PV - ECOMM) / loss1)
    R = np.array(R)
    fs = np.linspace(0.005, 0.95, 400)
    g = [float(np.mean(np.log1p(f * R))) if (1 + f * R).min() > 0 else -1e9 for f in fs]
    i = int(np.argmax(g))
    return {"f_star": round(float(fs[i]), 3), "n": len(R), "mean_r": round(float(R.mean()), 3),
            "win": round(float((R > 0).mean()), 3), "half_kelly": round(float(fs[i]) / 2, 3)}


def fz(**kw):
    """the live funded sizing with some keys changed"""
    c = {**REC, **kw}
    return lambda t, st, ctx: SZ.funded_qty(t, st, c, acct=AF)


def fz_ramp(step_usd=200.0, cap_usd=1400.0, win_step=0.0, win_cap=1500.0):
    """risk ramp after each payout: pct_max_usd + step x payouts (cap), best-day cap + win_step x payouts (cap)."""
    def f(t, st, ctx):
        n = ctx["n_pay"]
        c = {**REC, "pct_max_usd": min(cap_usd, REC["pct_max_usd"] + step_usd * n),
             "max_win": min(win_cap, REC["max_win"] + win_step * n)}
        return SZ.funded_qty(t, st, c, acct=AF)
    return f


def fz_mult(mfn):
    """the live funded sizing x a strategy-level multiplier (part 1 rules on the unit's causal history): cut int(q x m) min
    1; up capped by 60% of the room / the soft daily loss (2 ticks)."""
    def f(t, st, ctx):
        q = SZ.funded_qty(t, st, REC, acct=AF)
        if q <= 0:
            return 0
        m = mfn(t)
        if m <= 0:
            return 0
        if m < 1:
            return max(1, int(q * m + 1e-9))
        if m > 1:
            loss1 = (t["risk"] + 2 * SLIP) * PV + ECOMM
            cap = min(40, int(0.6 * max(0.0, st["room"]) / loss1), int(max(0.0, DLL + st["cum"]) / loss1))
            return max(q, min(int(q * m + 1e-9), cap))
        return q
    return f


def fz_room_derisk(below, pct):
    def f(t, st, ctx):
        c = {**REC, "pct": pct} if st["room"] < below else REC
        return SZ.funded_qty(t, st, c, acct=AF)
    return f


def funded_grid():
    D = load()
    out = {"_meta": {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                     "note": "MFFU Builder 50K funded (tools/lit_money2.py model), 1,000 MC paths x 126 sessions, same paths as "
                             "lit-funded-sizing / lit-money-batch2; $1.90"}}
    P15, ASAP = ("atl", 1500.0), ("asap", 0.0)
    for vn in ("base", "all3"):
        U = D[vn]["U"]
        by = by_full(U)
        R = {"_kelly": {s: kelly_units(U, s) for s in ("H1", "H2")}}
        V = {"live funded | asap (today)": (fz(), ASAP), "live funded | wait for $1,500+ (adopt-candidate)": (fz(), P15)}
        for pct in (0.2, 0.3, 0.5, 0.6):
            V[f"pct {pct:g} of the room | $1,500+"] = (fz(pct=pct), P15)
        for mx in (600.0, 1000.0, 1200.0):
            V[f"max ${mx:,.0f} a trade | $1,500+"] = (fz(pct_max_usd=mx), P15)
        for mw in (1000.0, 2000.0):
            V[f"best-day cap ${mw:,.0f} | $1,500+"] = (fz(max_win=mw), P15)
        V["no weekly stop | $1,500+"] = (fz(wk=False), P15)
        for st_, cap in ((100.0, 1200.0), (200.0, 1400.0), (400.0, 2000.0)):
            V[f"ramp +${st_:,.0f} max a payout (cap ${cap:,.0f}) | $1,500+"] = (fz_ramp(st_, cap), P15)
        V["ramp +$200 max and +$250 best day a payout | $1,500+"] = (fz_ramp(200.0, 1400.0, 250.0, 2500.0), P15)
        for below, pct in ((1500.0, 0.25), (1200.0, 0.2)):
            V[f"room < ${below:,.0f}: pct {pct:g} | $1,500+"] = (fz_room_derisk(below, pct), P15)
        V["cold: last 5 R <= 0 -> x0.5 | $1,500+"] = (fz_mult(m_cold(5, 0.0, 0.5)), P15)
        V["cold: last 10 R <= 0 -> x0.5 | $1,500+"] = (fz_mult(m_cold(10, 0.0, 0.5)), P15)
        V["hot: last 10 R >= 5 -> x1.5 | $1,500+"] = (fz_mult(m_hot(10, 5.0, 1.5)), P15)
        V["hot: last 20 R >= 10 -> x1.5 | $1,500+"] = (fz_mult(m_hot(20, 10.0, 1.5)), P15)
        V["R drawdown >= 5R -> x0.5 | $1,500+"] = (fz_mult(m_dd(5.0, 0.5)), P15)
        for nm, (sz, pol) in V.items():
            R[nm] = {s: funded_mc(sz, pol, by, s) for s in ("H1", "H2")}
            h1, h2 = R[nm]["H1"], R[nm]["H2"]
            print(f"{vn} {nm[:54]:54s} H1 lost {h1['loss_6m']:4.1f}% paid ${h1['paid_6m']:5,} (${h1['per_month']}/mo) p10 ${h1['paid_p10_6m']:,} "
                  f"1st {h1['first_med']} risk {h1['max_risk']} | H2 lost {h2['loss_6m']:4.1f}% paid ${h2['paid_6m']:5,} (${h2['per_month']}/mo) "
                  f"p10 ${h2['paid_p10_6m']:,} 1st {h2['first_med']} risk {h2['max_risk']}", flush=True)
        print(vn, "Kelly", R["_kelly"], flush=True)
        out[vn] = R
        json.dump(out, open(OUT_F, "w"), indent=1, default=float)
    return out


# ================================================================================================ part 5: portfolio of evals
class EvalSM:
    """One MFFU Builder 50K eval, session by session (the same rules and sizing as run_eval_h, hooks included)."""

    def __init__(self):
        self.bal = self.peak = 0.0
        self.floor = -A.A50["mll"]
        self.k = 0
        self.ev = []
        self.wk = collections.defaultdict(float)

    def step(self, day_trades):
        tgt, mll, lockv = A.A50["target"], A.A50["mll"], A.A50["lock"]
        mf, cf, wu = G["m_fn"], G["cfg_fn"], G["wk_usd"]
        cum = 0.0
        self.k += 1
        for t in day_trades:
            if cum <= -DLL:
                break
            st = {"profit": self.bal, "cum": cum, "room": self.bal + cum - self.floor, "session": self.k, "n_today": 0}
            wk = lit.iso_week(t["day"])
            if wu and (self.wk[wk] <= -wu[0] or (wu[1] is not None and self.wk[wk] >= wu[1])):
                continue
            ctx = {"session": self.k, "st": st, "ev": self.ev, "bal": self.bal, "wk": self.wk[wk]}
            cfg = cf(ctx, A.CFG) if cf else A.CFG
            m0 = lit.qty_for(t["risk"])
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, cfg, room=st["room"], state=st,
                           learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            qfull = q
            m = float(mf(t, ctx)) if mf else 1.0
            if m <= 0:
                continue
            if m < 1.0 - 1e-9:
                q = max(1, int(q * m + 1e-9))
            pnl, low, tot = BI.trade_pnl(t, q, qfull, st)
            if cum + low <= -DLL:
                pnl = -DLL - cum - SLIP * PV * tot
                low = pnl
            if self.bal + cum + low <= self.floor:
                return "FAIL"
            cum += pnl
            self.wk[wk] += pnl
            self.ev.append((t["day"], pnl, t["exit"]))
        self.bal += cum
        if self.bal <= self.floor:
            return "FAIL"
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - mll), lockv)
        if self.bal >= tgt:
            return "PASS"
        return "OPEN"


class FundedSM:
    """One MFFU Builder 50K funded account, session by session (funded_run with the live funded sizing + a payout policy)."""

    def __init__(self, policy=("atl", 1500.0), sizer=None):
        self.bal = self.peak = 0.0
        self.floor = -AF["mll"]
        self.n_pay, self.last_bal, self.cyc, self.k = 0, 0.0, [], 0
        self.policy, self.sizer = policy, sizer or fz()

    def room(self):
        return self.bal - self.floor

    def step(self, day_trades):
        """-> (status OPEN / BLOWN / GRAD, $ paid to the trader this session)"""
        mll, dll, lockv = AF["mll"], AF["dll"], AF["lock"]
        cum = 0.0
        traded = False
        self.k += 1
        for t in day_trades:
            if cum <= -dll:
                break
            st = {"room": self.bal + cum - self.floor, "cum": cum, "locked": self.floor >= lockv - 1e-9, "bal": self.bal,
                  "session": 99}
            q = self.sizer(t, st, {"n_pay": self.n_pay, "peak": self.peak, "k": self.k})
            if q <= 0:
                continue
            traded = True
            pnl, low, tot = BI.trade_pnl(t, q, q, st)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * tot
                low = pnl
            if self.bal + cum + low <= self.floor:
                return "BLOWN", 0.0
            cum += pnl
        self.bal += cum
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - mll), lockv)
        if traded:
            self.cyc.append(cum)
        if self.k < AF["first_wait"] or len(self.cyc) < AF["cycle_days"]:
            return "OPEN", 0.0
        prof = self.bal - self.last_bal
        if prof <= 0 or (self.cyc and max(self.cyc) > AF["cons"] * prof):
            return "OPEN", 0.0
        avail = self.bal - AF["buffer"]
        pol, h = self.policy
        amt = min(avail, AF["pay_max"]) if (pol == "asap" or avail >= h) else 0.0
        if amt < AF["pay_min"]:
            return "OPEN", 0.0
        self.n_pay += 1
        self.bal -= amt
        self.last_bal, self.cyc = self.bal, []
        return ("GRAD" if self.n_pay >= AF["max_payouts"] else "OPEN"), amt * AF["split"]


def portfolio_path(seq, by, pol):
    """One 6-month path. pol: K funded slots, E max open evals, gap (sessions between purchases), when ('free' = buy only
    while open funded + queued passes < K; 'always'), queue (a pass waits for a free slot), budget (max purchases per 21
    sessions), standby (also buy 1 eval while every slot is full once a funded account's room < standby $)."""
    K, E, gap = pol.get("K", 1), pol.get("E", 1), pol.get("gap", 0)
    when, queue, budget, standby = pol.get("when", "free"), pol.get("queue", False), pol.get("budget"), pol.get("standby")
    evals, funded, waiting = [], [], 0
    buys, paid, last_buy, wasted, funded_days = [], 0.0, -10 ** 6, 0, 0
    first_funded = None
    pay_sessions = []
    for s, si in enumerate(seq):
        # ---- purchases at the session's start
        while len(evals) < E and s - last_buy >= gap:
            if budget is not None and sum(1 for b in buys if b > s - 21) >= budget:
                break
            busy = len(funded) + waiting
            ok = when == "always" or busy < K
            if not ok and standby is not None and not evals and funded and min(f.room() for f in funded) < standby:
                ok = True
            if not ok:
                break
            evals.append(EvalSM())
            buys.append(s)
            last_buy = s
            if gap == 0 and len(evals) >= E:
                break
        # ---- the session's trades
        keep = []
        for e in evals:
            r = e.step(by[si])
            if r == "PASS":
                if len(funded) + waiting < K:
                    waiting += 1                    # funded from the next session
                elif queue:
                    waiting += 1
                else:
                    wasted += 1
            elif r == "OPEN":
                keep.append(e)
        evals = keep
        alive = []
        for f in funded:
            stt, p = f.step(by[si])
            paid += p
            if p:
                pay_sessions.append(s)
            if stt == "OPEN":
                alive.append(f)
        funded = alive
        funded_days += len(funded)
        # ---- passes become funded accounts for the next session (up to K)
        while waiting and len(funded) < K:
            funded.append(FundedSM())
            waiting -= 1
            first_funded = first_funded if first_funded is not None else s + 1
    fees = PRICE * len(buys)
    return {"net": paid - fees, "paid": paid, "fees": fees, "buys": len(buys), "wasted": wasted,
            "funded_share": funded_days / (len(seq) * K), "first_funded": first_funded,
            "first_pay": pay_sessions[0] if pay_sessions else None}


_PSEQ = {}


def port_seqs(span, n=500, length=126, seed=31):
    if (span, n) not in _PSEQ:
        a, z = A.span_ix(span)
        rng = np.random.default_rng(seed)
        S = []
        for _ in range(n):
            s = []
            while len(s) < length:
                b = int(rng.integers(a, z - 5 + 1))
                s.extend(range(b, b + 5))
            S.append(s[:length])
        _PSEQ[(span, n)] = S
    return _PSEQ[(span, n)]


def portfolio(n=500):
    D = load()
    pols = {
        "A serial: 1 eval, the next only after a fail or when the funded account ends (today)": {"K": 1, "E": 1},
        "B one eval always running (passes wasted while the slot is full)": {"K": 1, "E": 1, "when": "always"},
        "C 2 evals bought the same day": {"K": 1, "E": 2, "gap": 0},
        "D 2 evals staggered 3 sessions": {"K": 1, "E": 2, "gap": 3},
        "E 2 evals staggered 5 sessions": {"K": 1, "E": 2, "gap": 5},
        "F 2 evals staggered 10 sessions": {"K": 1, "E": 2, "gap": 10},
        "G 3 evals staggered 5 sessions": {"K": 1, "E": 3, "gap": 5},
        "H serial + standby eval when the funded room < $1,000": {"K": 1, "E": 1, "standby": 1000.0},
        "I serial + standby eval when the funded room < $1,500": {"K": 1, "E": 1, "standby": 1500.0},
        "J 1 eval always running, passes queue (if MFFU let a pass wait)": {"K": 1, "E": 1, "when": "always", "queue": True},
        # if more funded slots were allowed (sensitivity: MFFU's general rule says up to 5 sim funded; Builder 50K page says 1)
        "K2 2 slots, 1 eval at a time": {"K": 2, "E": 1},
        "K2 2 slots, 2 evals staggered 5": {"K": 2, "E": 2, "gap": 5},
        "K3 3 slots, 1 eval at a time": {"K": 3, "E": 1},
        "K3 3 slots, 2 evals staggered 5": {"K": 3, "E": 2, "gap": 5},
        "K3 3 slots, 3 evals staggered 5": {"K": 3, "E": 3, "gap": 5},
        "K3 3 slots, 3 evals same day": {"K": 3, "E": 3, "gap": 0},
        "K3 3 slots, 3 evals staggered 5, max 2 buys a month ($184)": {"K": 3, "E": 3, "gap": 5, "budget": 2},
        "K3 3 slots, 3 evals staggered 5, max 1 buy a month ($92)": {"K": 3, "E": 3, "gap": 5, "budget": 1},
    }
    out = {"_meta": {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "paths": n, "length": 126,
                     "note": "Monte Carlo of 126-session (6-month) paths in 5-session blocks of the half; every eval and funded "
                             "account trades the same LIT trades (correlation built in); eval = live two_week config C then "
                             "safe_eval, funded = live funded sizing + payouts once $1,500+ is available; $91.80 an eval; "
                             "graduation (5 payouts -> live) frees the slot and the live account is not counted"}}
    for vn in ("base", "all3"):
        hooks()
        by = A.by_day(D[vn]["U"])
        R = {}
        for nm, pol in pols.items():
            o = {}
            for sp in ("H1", "H2"):
                rs = [portfolio_path(s, by, pol) for s in port_seqs(sp, n)]
                net = np.array([r["net"] for r in rs])
                ff = [r["first_funded"] for r in rs if r["first_funded"] is not None]
                o[sp] = {"net_mo": round(float(net.mean()) / 6.0), "net_p10_mo": round(float(np.percentile(net, 10)) / 6.0),
                         "p_loss": round(100.0 * float((net < 0).mean()), 1), "paid_6m": round(float(np.mean([r["paid"] for r in rs]))),
                         "fees_6m": round(float(np.mean([r["fees"] for r in rs]))), "buys": round(float(np.mean([r["buys"] for r in rs])), 2),
                         "wasted": round(float(np.mean([r["wasted"] for r in rs])), 2),
                         "funded_share": round(100.0 * float(np.mean([r["funded_share"] for r in rs])), 1),
                         "first_funded_med": float(np.median(ff)) if ff else None,
                         "no_funded": round(100.0 * sum(1 for r in rs if r["first_funded"] is None) / len(rs), 1)}
            R[nm] = o
            print(f"{vn} {nm[:66]:66s} " + " | ".join(
                f"{sp} ${o[sp]['net_mo']:,}/mo (p10 ${o[sp]['net_p10_mo']:,}) loss {o[sp]['p_loss']}% buys {o[sp]['buys']} "
                f"waste {o[sp]['wasted']} funded {o[sp]['funded_share']}% 1st {o[sp]['first_funded_med']}" for sp in ("H1", "H2")), flush=True)
        out[vn] = R
        json.dump(out, open(OUT_P, "w"), indent=1, default=float)
    return out


def portfolio_extra(n=500):
    """A (serial) and E (2 evals staggered 5) with the eval weekly loss stop (-$1,200 / -$800) on every eval."""
    D = load()
    out = json.load(open(OUT_P, encoding="utf-8"))
    pols = {"A serial": {"K": 1, "E": 1}, "E 2 evals staggered 5 sessions": {"K": 1, "E": 2, "gap": 5}}
    for vn in ("base", "all3"):
        by = A.by_day(D[vn]["U"])
        for loss in (1200.0, 800.0):
            hooks(wk_usd=(loss, None))
            for pn, pol in pols.items():
                o = {}
                for sp in ("H1", "H2"):
                    rs = [portfolio_path(s, by, pol) for s in port_seqs(sp, n)]
                    net = np.array([r["net"] for r in rs])
                    o[sp] = {"net_mo": round(float(net.mean()) / 6.0), "net_p10_mo": round(float(np.percentile(net, 10)) / 6.0),
                             "p_loss": round(100.0 * float((net < 0).mean()), 1), "buys": round(float(np.mean([r["buys"] for r in rs])), 2),
                             "funded_share": round(100.0 * float(np.mean([r["funded_share"] for r in rs])), 1)}
                nm = f"{pn} + eval weekly loss stop -${loss:,.0f}"
                out[vn][nm] = o
                print(vn, nm, o, flush=True)
        hooks()
    json.dump(out, open(OUT_P, "w"), indent=1, default=float)


# ================================================================================================ run library
Q = ("LIT risk & money (2026-10-20): equity-curve sizing, eval-game refinements, weekly loss / profit stops, funded-phase risk "
     "and a portfolio of evals - what was not tested yet. LIT rule: 2026 only, pick on Jan-Jun, check on Jul-Oct; eval: 2-week "
     "pass not down and fail not up in both halves; funded: $ up and accounts lost not up; scored on live LIT and on top of "
     "t_check + scale_in + be_off.")


def _eval_trades(U):
    Tp = []
    for sp in ("H1", "H2"):
        Tp += A.b2b(U, sp)[0]
    for t in Tp:
        t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
        t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
    return Tp


def _he(e, s, b=None):
    x = e[s]
    o = (f"PF {x['pf']} eval-path net {x['net']:+,} (${x['per_month']:,}/mo, eval account P&L, not cash) DD {x['dd']:,}; "
         f"2-week pass/fail {x['p10']}/{x['f10']} (Monte Carlo {x['mc_p10']}/{x['mc_f10']}), 1 month {x['p20']}/{x['f20']}, "
         f"{x['tpw']} trades/wk")
    if "ev" in x:
        o += f"; eventual pass/fail (no reset) {x['ev']['pass']}/{x['ev']['fail']} (MC {x['ev']['mc']['pass']}/{x['ev']['mc']['fail']})"
    if b is not None:
        o += f" [live: 2-week {b[s]['p10']}/{b[s]['f10']}, MC {b[s]['mc_p10']}/{b[s]['mc_f10']}"
        o += (f", eventual {b[s]['ev']['pass']}/{b[s]['ev']['fail']}]" if "ev" in b[s] else "]")
    return o


def save():
    from tools import runlib as rl
    D = load()
    rm = json.load(open(OUT, encoding="utf-8"))
    EV = [  # id, variant, title, hooks, status, why
        ("lit_risk_m_wk1200", "base", "eval weekly loss stop -$1,200 (no new trade until next week)", dict(wk_usd=(1200.0, None)),
         "adopt-candidate", "Holds on live LIT in both halves (2-week pass never down, fails down in H1, pass up in H2), on the "
                            "combo it is non-worse (fails down in H1), its neighbours -$700 to -$1,500 all cut fails, 2021-25 "
                            "reference fails 5.6 -> 5.2%. Money-neutral in the 6-month MFFU portfolio (-$2 / -$3 a month)."),
        ("lit_risk_m_wk1200_all3", "all3", "eval weekly loss stop -$1,200 on t_check + scale_in + be_off",
         dict(wk_usd=(1200.0, None)), "promising", "On the combo: H1 fails 2.5 -> 0.8% at the same pass, H2 unchanged."),
        ("lit_risk_m_wk800", "base", "eval weekly loss stop -$800 (= after one full stop-out)", dict(wk_usd=(800.0, None)),
         "promising", "Bigger fail cut on live LIT, but on the combo the H1 2-week pass drops 58.0 -> 55.5%."),
        ("lit_risk_m_cold5", "base", "equity-curve cold filter: last 5 LIT R <= 0 -> half size", None, "rejected",
         "The old engine's cold filter re-tested on LIT: costs money in both halves, both variants and 2021-25."),
        ("lit_risk_m_hot10", "base", "hot hand: last 10 LIT R >= +5 -> x1.5", None, "rejected",
         "More money at the plain LIT size in 2026, but more 2-week fails on the eval path and less money in 2021-25."),
        ("lit_risk_m_wkprofit3", "base", "weekly profit stop: no trade after +3R closed in the week", None, "rejected",
         "Stops the trades after a target: costs H1 money and 2-week passes, trades/week 2.7 / 2.05."),
        ("lit_risk_m_after10_safe40", "base", "after session 10: safe_eval at 40% of the room (live 60%)",
         dict(cfg_fn=cf_after("safe_eval", safe_cap=0.4)), "promising",
         "Eventual pass (no reset) up 1.5-3 pts in both halves on live LIT, slower passes, on the combo H1 exact eventual pass -0.9, "
         "2021-25 eventual pass 31.0 -> 28.3%."),
    ]
    MF = {"lit_risk_m_cold5": m_cold(5, 0.0, 0.5), "lit_risk_m_hot10": m_hot(10, 5.0, 1.5), "lit_risk_m_wkprofit3": m_wk_profit(3.0, 0.0)}
    for rid, vn, title, hk, stt, why in EV:
        U = D[vn]["U"]
        for u in U:
            u.pop("m", None)
        hooks()
        b = score(U, ev=True)
        if rid in MF:
            for u in U:
                u["m"] = MF[rid](u)
        else:
            hooks(**hk)
        e = score(U, ev=True)
        Tp = _eval_trades(U)
        hooks()
        for u in U:
            u.pop("m", None)
        P = {**lit.DEFAULTS, **AC.LIVE, **VARS[vn]}
        extra = ""
        if rid in MF:
            lr = rm[vn].get({"lit_risk_m_cold5": "cold: last 5 R <= 0 -> x0.5", "lit_risk_m_hot10": "hot: last 10 R >= 5 -> x1.5",
                             "lit_risk_m_wkprofit3": "week: stop after +3R closed"}[rid], {}).get("lit_rule")
            lb = rm[vn]["_base"]["lit_rule"]
            if lr:
                extra = " LIT size rule ($800 to 20 pts): " + ", ".join(f"{s} {lr[s]['net']:+,} (live {lb[s]['net']:+,}, {lr[s]['tpw']}/wk)"
                                                                        for s in ("H1", "H2", "2021-25")) + "."
        rl.save(rid, title, "risk", Q, params=P, sizing={"mode": "two_week", **A.CFG, "rule": title}, trades=Tp,
                scored=rl.score(Tp, A.S26), status=stt,
                verdict=f"{why} Eval path (live two_week 10 sessions then safe_eval, no reset, $1.90, true 1m). 2026 H1 (pick) "
                        f"{_he(e, 'H1', b)}. 2026 H2 (check) {_he(e, 'H2', b)}.{extra}",
                notes="tools/lit_risk_money.py: engine/lit.py run_x trades as units, sized by engine/sizing.lit_qty (run_eval_h = "
                      "lit_big_ideas.run_eval_x + hooks), scored by tools/lit_adv_manage.py evals / mc / b2b; stored trades = the "
                      "back-to-back eval path per half.", writeup="lit-risk-money", tags=["lit", "lit_risk_m"])
        print("saved", rid, flush=True)
    # ---- funded: the ramp after payouts (rejected) and the live funded + $1,500 policy reference
    rf = json.load(open(OUT_F, encoding="utf-8"))
    for rid, nm, sz_, stt, why in (
            ("lit_risk_m_funded_ramp400", "ramp +$400 max a payout (cap $2,000) | $1,500+", fz_ramp(400.0, 2000.0), "rejected",
             "Risk ramp after each payout: +$3 / +$101 per 6 months on live LIT (noise), +$117 / +$276 on the combo, max risk a "
             "trade +60-100%."),
            ("lit_risk_m_funded_ref", "live funded | wait for $1,500+ (adopt-candidate)", fz(), "info",
             "Reference: live funded sizing + ask for a payout once $1,500+ is above the buffer (lit-money-batch2).")):
        T = []
        bb = {}
        for sp in ("H1", "H2"):
            Tx, bb[sp] = funded_b2b(sz_, ("atl", 1500.0), D["base"]["U"], sp)
            T += Tx
        r, ref = rf["base"][nm], rf["base"]["live funded | wait for $1,500+ (adopt-candidate)"]
        h = lambda s: (f"MC 6 months: lost {r[s]['loss_6m']}% (ref {ref[s]['loss_6m']}%), paid ${r[s]['paid_6m']:,} "  # noqa
                       f"(${r[s]['per_month']:,}/mo; ref ${ref[s]['paid_6m']:,}), max risk ${r[s]['max_risk']:,}; real path {bb[s]}")
        rl.save(rid, "funded: " + nm, "risk", Q, params={"funded": REC, "variant": nm}, sizing={"mode": "funded", **REC},
                trades=T, scored=rl.score(T, A.S26), status=stt, verdict=f"{why} H1 (pick): {h('H1')}. H2 (check): {h('H2')}.",
                notes="tools/lit_risk_money.py funded (the lit_money2 MFFU Builder 50K funded model, same 1,000 MC paths); stored "
                      "trades = the back-to-back funded path of 2026; the run library's eval columns are not the funded numbers.",
                writeup="lit-risk-money", tags=["lit", "lit_risk_m", "funded"])
        print("saved", rid, flush=True)
    # ---- portfolio: 2 evals staggered 5 sessions (adopt-candidate, owner habit)
    rp = json.load(open(OUT_P, encoding="utf-8"))
    U = D["base"]["U"]
    hooks()
    Tp = _eval_trades(U)
    A_, E_ = (rp["base"]["A serial: 1 eval, the next only after a fail or when the funded account ends (today)"],
              rp["base"]["E 2 evals staggered 5 sessions"])
    A3, E3 = (rp["all3"]["A serial: 1 eval, the next only after a fail or when the funded account ends (today)"],
              rp["all3"]["E 2 evals staggered 5 sessions"])
    f = lambda o, s: f"${o[s]['net_mo']:,}/mo net (p10 ${o[s]['net_p10_mo']:,}), no money in 6 months {o[s]['p_loss']}%, {o[s]['buys']} evals"  # noqa
    rl.save("lit_risk_m_portfolio_stagger5", "portfolio: a 2nd eval 5 sessions after the 1st (while no funded account)", "risk", Q,
            params={**lit.DEFAULTS, **AC.LIVE}, sizing={"mode": "two_week", **A.CFG}, trades=Tp, scored=rl.score(Tp, A.S26),
            status="adopt-candidate",
            verdict=f"MFFU allows 1 sim-funded Builder 50K. 500 paths x 6 months, payouts minus $91.80 evals. Live LIT: serial "
                    f"H1 {f(A_, 'H1')} / H2 {f(A_, 'H2')}; staggered H1 {f(E_, 'H1')} / H2 {f(E_, 'H2')}. On the combo: serial "
                    f"H1 {f(A3, 'H1')} / H2 {f(A3, 'H2')}; staggered H1 {f(E3, 'H1')} / H2 {f(E3, 'H2')}. Same-day copies "
                    f"are the same eval twice (worse). Neighbours 3 / 10 sessions and 3 evals also beat serial.",
            notes="tools/lit_risk_money.py portfolio (EvalSM / FundedSM == run_eval_h / funded_run). Stored trades = the live eval "
                  "path (reference); the portfolio numbers are in the verdict and research/lit/risk_money_portfolio.json.",
            writeup="lit-risk-money", tags=["lit", "lit_risk_m", "portfolio"])
    print("saved lit_risk_m_portfolio_stagger5", flush=True)


def check_sm():
    """EvalSM / FundedSM == run_eval_h / funded_run on the same session sequences."""
    D = load()
    ok = True
    for vn in ("base", "all3"):
        U = D[vn]["U"]
        by = A.by_day(U)
        a, z = A.span_ix("H1")
        bad = 0
        for i in range(a, z - 20):
            seq = list(range(i, i + 20))
            r1 = run_eval_h(seq, by)
            e = EvalSM()
            r2 = ("OPEN", 20)
            for k, si in enumerate(seq):
                r = e.step(by[si])
                if r != "OPEN":
                    r2 = (r, k + 1)
                    break
            bad += r1 != r2
        S = port_seqs("H2", 50)
        badf = 0
        for s in S:
            r1 = funded_run(fz(), ("atl", 1500.0), s, by)
            f = FundedSM()
            paid = 0.0
            for si in s:
                stt, p = f.step(by[si])
                paid += p
                if stt != "OPEN":
                    break
            badf += abs(paid - r1["paid"]) > 1e-6
        print(vn, "eval SM mismatches", bad, "| funded SM mismatches", badf, flush=True)
        ok &= bad == 0 and badf == 0
    return ok


def check_engine_wk():
    """The research rule (G wk_usd) == engine/sizing.lit_qty with lit_sizing "wk_loss_usd" (state wk_pnl) on the eval path,
    and eval_state(today=) gives the same week P&L as the research counter."""
    D = load()
    ok = True
    for vn in ("base", "all3"):
        U = D[vn]["U"]
        for loss in (800.0, 1200.0):
            hooks(wk_usd=(loss, None))
            a = score(U)
            hooks(cfg_fn=lambda ctx, cfg, loss=loss: {**cfg, "wk_loss_usd": loss})
            b = score(U)
            hooks()
            same = all(a[s][k] == b[s][k] for s in ("H1", "H2") for k in ("net", "p10", "f10", "mc_p10", "mc_f10", "b2b"))
            print(vn, f"wk_loss_usd {loss:g}: research rule == engine lit_qty:", same, flush=True)
            ok &= same
    st = SZ.eval_state({"2026-10-12": -500.0, "2026-10-14": -300.0, "2026-10-09": -900.0}, -250.0, today="2026-10-16")
    ok &= abs(st["wk_pnl"] + 1050.0) < 1e-9 and "wk_pnl" not in SZ.eval_state({"2026-10-12": -500.0}, 0.0)
    print("eval_state(today=) week P&L:", st["wk_pnl"], "(want -1050)", flush=True)
    return ok


def check():
    D = load()
    ref = json.load(open(AC.OUT, encoding="utf-8"))
    ok = True
    for vn in ("base", "all3"):
        hooks()
        o = score(D[vn]["U"])
        r = ref[vn]["eval"]
        same = all(o[s][k] == r[s][k] for s in ("H1", "H2") for k in ("net", "pf", "dd", "p10", "f10", "mc_p10", "mc_f10"))
        print(vn, "== adopt_combo.json eval:", same, flush=True)
        print(line(vn, o))
        ok &= same
    return ok


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        sys.exit(0 if check() else 1)
    elif cmd == "grid":
        eval_grid()
    elif cmd == "funded":
        funded_grid()
    elif cmd == "portfolio":
        sys.exit(0 if check_sm() else 1) if len(sys.argv) > 2 and sys.argv[2] == "check" else portfolio()
    elif cmd == "save":
        save()
    elif cmd == "round2":
        round2()
    elif cmd == "units":
        load(fresh=True)
