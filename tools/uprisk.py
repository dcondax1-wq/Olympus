"""Uprisk study (owner 2026-10-25: "We might need to uprisk, that little bit per month doesn't seem normal. Do more
research, figure out what you're missing."). research/writeups/uprisk.md. Paper research only: reads live_model.json,
writes research/lit/uprisk_<study>.json and runs uprisk_* (tools/runlib), nothing live.

Trades: the 120 live LIT trades of 2026 (run lit_live, research/handoff/2026-10-25/COMPLETE_TRADE_LEDGER.csv T-2026-*, true
1m fills, 1 tick on market entries / stop exits in the prices), $1.90 a micro round trip; reference 2021-25 = the 511 REF
rows (5m only). Sessions: CME NQ1! daily bars. H1 = Jan-Jun 2026 (pick), H2 = Jul-Oct 2026 (check).

Four studies, all on the same Monte Carlo of start days (1,000 paths of 126 sessions = 6 months, 5-session blocks drawn
from the half, seed 23, exactly as tools/funded_path.py):
  1. decomp    where the funded money goes: trading profit vs paid to the owner vs left in the account vs lost, and which
               MFFU rule holds the money back on each session (request max, 50% consistency, 2-day cycle, the owner's
               $1,500 line, the 5-payout end)
  2. frontier  funded sizing grid on the 50K and the 25K: per-trade risk cap x room fraction x winner cap (consistency),
               plus need-based (risk only what reaches the next full payout) and the payout ask line
  3. eval      eval sizing variants (two_week room_f / need_buf / max micros / after-mode / reset rule): pass / fail within
               10 sessions, eventual pass, $ per pass at $91.80
  4. life      a whole account SLOT for 6 months: eval -> (2 sessions of MFFU paperwork) -> funded -> payouts -> lost or
               5 payouts (moves to live, the bot does not trade live) -> buy the next eval; $ to the owner net of every
               eval bought, funded accounts reached, P(slot loses money)

  python -X utf8 tools/uprisk.py [decomp|frontier50|frontier25|asks|eval|life|all] [--n 1000] [--no-save]
"""
from __future__ import annotations

import copy
import csv
import datetime as dt
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import funded_life as FL  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

PV, COMM, SLIP = 2.0, 1.90, 0.25
HO = os.path.join(ROOT, "research", "handoff", "2026-10-25")
OUT = os.path.join(ROOT, "research", "lit", "uprisk.json")
N_MC, BLOCK, LEN = 1000, 5, 126
SPAN = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "REF": ("2021-11-01", "2025-12-31")}
PRICE = {"builder50k": 91.80, "builder25k": 63.00}
GAP = 2                                    # sessions between the eval pass and the first funded session (MFFU paperwork)

_LS = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
LIT_CFG = {k: copy.deepcopy(v) for k, v in _LS.items() if k not in ("eval_start", "eval_prior_pnl", "eval_prior_note", "note",
                                                                    "modes", "eval_mode_note", "funded")}
LIT_CFG["mode"] = "two_week"
FUND_LIVE = dict(_LS["funded"])            # the research funded rule in live_model.json (40% room, <= $800, winner <= $1,500)
EPLAN = {"builder50k": {"tgt": 3000.0, "mll": 2000.0, "dll": 1000.0, "lock": 100.0, "stuck": 200.0, "maxq": 40, "scale": 1.0},
         "builder25k": {"tgt": 1500.0, "mll": 1000.0, "dll": 600.0, "lock": 100.0, "stuck": 100.0, "maxq": 20, "scale": 0.5}}


# ================================================================================================ data
def sessions(a="2021-11-01", z="2026-10-16"):
    out = []
    with open(os.path.join(ROOT, "data", "NQ_1d.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            d = dt.datetime.fromtimestamp(int(float(r["time"])), dt.timezone.utc).date()
            if a <= d.isoformat() <= z and d.weekday() < 5:
                out.append(d.isoformat())
    return sorted(set(out))


def trades(prefix=("T-2026", "REF-")):
    """day -> [unit]; unit = stop pts, target pts, closed pts (slippage in), worst open pts (mae), weekly-stop multiplier."""
    by = {}
    with open(os.path.join(HO, "COMPLETE_TRADE_LEDGER.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r["trade_id"].startswith(prefix):
                continue
            d = 1 if r["direction"] == "long" else -1
            e, s, tg, x = (float(r[k]) for k in ("entry_price", "initial_stop", "target_price", "exit_price"))
            risk = abs(e - s)
            base = qty_for(risk)
            wk = 0.5 if base and int(r["quantity"]) < base else 1.0
            day = r["entry_fill_at"][:10]
            by.setdefault(day, []).append({"day": day, "risk": risk, "risk_pts": risk, "tgt": abs(tg - e), "tgt_pts": abs(tg - e),
                                           "pts": (x - e) * d, "w1": -float(r["mae_r"] or 0) * risk, "size_mult": wk,
                                           "ref": r["trade_id"].startswith("REF")})
    return by


_CAL = []


def cal(k: int) -> str:
    while len(_CAL) <= k:
        d = dt.date(2027, 1, 4) if not _CAL else dt.date.fromisoformat(_CAL[-1]) + dt.timedelta(days=1)
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        _CAL.append(d.isoformat())
    return _CAL[k]


def span_ix(S, span):
    a, z = SPAN[span]
    ix = [i for i, d in enumerate(S) if a <= d <= z]
    return ix[0], ix[-1] + 1


def mc_paths(S, span, n=N_MC, length=LEN, seed=23):
    a, z = span_ix(S, span)
    rng = np.random.default_rng(seed)
    P = []
    for _ in range(n):
        s = []
        while len(s) < length:
            b = int(rng.integers(a, z - BLOCK + 1))
            s.extend(range(b, b + BLOCK))
        P.append(s[:length])
    return P


# ================================================================================================ the funded account
def fplan(plan, ask=None):
    P = FL.plan_of(plan)
    if ask is not None:
        P["ask_above"] = float(ask)
    A = {"mll": P["mll"], "lock": P["lock"], "dll": P["dll"], "buffer": P["buffer"], "pay_min": P["pay_min"],
         "pay_max": P["pay_max"], "split": P["split"], "cons": P["cons"], "cycle_days": P["cycle_days"],
         "max_payouts": P["max_payouts"], "max_micros": P["max_micros"], "scale": 1.0}
    return P, A


class Funded:
    """One MFFU Builder Sim Funded account, a session at a time (the rules of tools/funded_path.run, bit for bit when
    cfg has no "need"), plus the bookkeeping of where the money goes."""

    def __init__(self, plan, cfg, ask=None):
        self.P, self.A = fplan(plan, ask)
        self.cfg = cfg
        self.days, self.pays = {}, {}
        self.k = 0
        self.state = "on"                    # on | lost | grad
        self.trade_pnl = 0.0
        self.paid = 0.0
        self.max_risk = 0.0
        self.first = None
        self.hold = {"cons": 0, "line": 0, "max_left": 0.0, "cycle_days": 0, "min": 0}
        self.n_tr = 0
        # incremental state (= engine/sizing.funded_state / funded_cycle and engine/funded_life.track, checked bit for bit
        # against them by selfcheck())
        self.bal, self.peak, self.floor = 0.0, 0.0, -float(self.A["mll"])
        self.cyc = []                        # this cycle's traded days' P&L
        self.cyc_start_bal = 0.0
        self.first_trade = None
        self.elig_from = None

    def _fast_state(self):
        A = self.A
        floor = max(self.floor, A["lock"]) if self.pays else self.floor
        st0 = {"balance": round(self.bal, 2), "floor": round(floor, 2)}
        cyc = {"cycle_start_bal": round(self.cyc_start_bal, 2), "cycle_prev": round(sum(self.cyc), 2),
               "best_prev": round(max(self.cyc), 2) if self.cyc else 0.0, "cycle_days_prev": len(self.cyc),
               "payouts_n": len(self.pays),
               "cycle_target": round(max(0.0, float(A["buffer"]) + float(A["pay_max"]) - self.cyc_start_bal), 2)}
        return st0, cyc

    def _fast_track(self, day):
        P = self.P
        cprof = round(sum(self.cyc), 2)
        best = round(max(self.cyc), 2) if self.cyc else 0.0
        cons_ok = cprof > 0 and best <= float(P["cons"]) * cprof + 1e-9
        above = round(self.bal - P["buffer"], 2)
        why = self.elig_from is None or day < self.elig_from or above < P["pay_min"] or len(self.cyc) < int(P["cycle_days"]) \
            or (cprof > 0 and not cons_ok) or (cprof <= 0 and bool(self.cyc))
        max_req = round(min(P["pay_max"], max(0.0, above)), 2) if above >= P["pay_min"] else 0.0
        eligible = not why
        ready = eligible and above >= P["ask_above"]
        status = "ready" if ready else "eligible" if eligible else "consistency" if (cprof > 0 and not cons_ok) else "building"
        return {"status": status, "above_buffer": above, "max_request": max_req if eligible else 0.0, "cycle_days": len(self.cyc)}

    def qty(self, t, st):
        c = self.cfg
        q = SZ.funded_qty(t, st, {k: v for k, v in c.items() if k not in ("need", "need_line", "harvest", "harvest_q",
                                                                            "harvest_after")}, acct=self.A)
        if q > 0 and c.get("need"):
            # need-based: only what makes the target reach the next full request line (buffer + pay_max above start, or
            # the cycle's own line after a payout), never more than the rule above; min 1 micro
            line = float(self.A["buffer"]) + float(c.get("need_line") or self.A["pay_max"])
            need = line - (st["bal"] + st["cum"])
            win1 = t["tgt"] * PV - COMM
            if win1 > 0:
                qn = max(1, math.ceil(max(0.0, need) * float(c["need"]) / win1 - 1e-9))
                q = min(q, qn)
        if q > 0 and c.get("harvest") is not None and self.pays_n_ok():
            # harvest: once the next request is already banked (balance - buffer >= harvest $), trade harvest_q micros
            # (1) so the cycle's days stay small and even (the 50% rule) until the payout is taken
            if st["bal"] + st["cum"] - float(self.A["buffer"]) >= float(c["harvest"]):
                q = min(q, int(c.get("harvest_q", 1)))
        return q

    def pays_n_ok(self):
        return len(self.pays) >= int(self.cfg.get("harvest_after", 0))

    def step(self, ts, keep=None):
        """One session with its trades ts. Returns ("paid", amount_to_owner) | ("lost", None) | ("grad", amt) | (None, None)."""
        if self.state != "on":
            return None, None
        A, P = self.A, self.P
        day = cal(self.k)
        self.k += 1
        if SLOW:
            st0 = SZ.funded_state(self.days, 0.0, self.pays, plan=A)
            cyc = SZ.funded_cycle(self.days, 0.0, self.pays, plan=A)
            if self.pays:
                st0["floor"] = max(st0["floor"], A["lock"])
        else:
            st0, cyc = self._fast_state()
        cum = 0.0
        for t in ts:
            if cum <= -A["dll"]:
                break
            room = round(st0["balance"] + cum - st0["floor"], 2)
            st = {"room": room, "cum": cum, "locked": st0["floor"] >= A["lock"] - 1e-9, "bal": st0["balance"], **cyc}
            q = self.qty(t, st)
            if q <= 0:
                continue
            self.n_tr += 1
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -A["dll"]:
                pnl = -A["dll"] - cum - SLIP * PV * q
                low = pnl
            if st0["balance"] + cum + low <= st0["floor"]:
                lossd = st0["floor"] - st0["balance"]
                self.days[day] = round(lossd, 2)
                self.trade_pnl += lossd
                if keep is not None:
                    keep.append((t, q, lossd))
                self.state = "lost"
                return "lost", None
            cum += pnl
            if keep is not None:
                keep.append((t, q, pnl))
        if abs(cum) > 1e-9:
            self.days[day] = round(cum, 2)
            self.trade_pnl += cum
            self.bal += round(cum, 2)
            self.cyc.append(round(cum, 2))
            if self.first_trade is None:
                self.first_trade = day
                self.elig_from = FL._next_weekday(FL._add_days(day, int(math.ceil(P["first_wait_h"] / 24.0))))
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - A["mll"]), A["lock"])
        tr = FL.track(self.days, self.pays, P, today=day) if SLOW else self._fast_track(day)
        if tr["status"] == "consistency" and tr["above_buffer"] >= P["ask_above"]:
            self.hold["cons"] += 1
        elif tr["status"] == "eligible":
            self.hold["line"] += 1                 # MFFU would pay now; the owner's line waits
        elif (tr["status"] == "building" and tr["above_buffer"] >= P["ask_above"] and tr["cycle_days"] < P["cycle_days"]):
            self.hold["cycle_days"] += 1
        if tr["status"] == "ready":
            amt = tr["max_request"]
            self.hold["max_left"] += max(0.0, tr["above_buffer"] - amt)   # above the buffer but over the request max
            self.pays[day] = amt
            self.paid += amt
            self.bal -= amt
            self.cyc_start_bal = self.bal
            self.cyc = []
            self.first = self.first or self.k
            if len(self.pays) >= P["max_payouts"]:
                self.state = "grad"
                return "grad", amt * P["split"]
            return "paid", amt * P["split"]
        return None, None

    def above_start(self):
        return sum(self.days.values()) - sum(self.pays.values())


SLOW = False


def selfcheck(n=150):
    """The incremental funded account == the slow one built on engine/sizing + engine/funded_life (every config family)."""
    global SLOW
    S, BY = load()
    for cfg in (F50, {**F50, "pct": 0.7, "pct_max_usd": 1500, "max_win": None}, {**F50, "need": 1.0, "pct_max_usd": 1500, "max_win": None},
                {**F50, "cons_aware": True}):
        for sp in ("H1", "H2"):
            P = mc_paths(S, sp, n)
            SLOW = True
            a = funded_mc(BY, P, "builder50k", cfg)
            SLOW = False
            b = funded_mc(BY, P, "builder50k", cfg)
            assert a == b, (cfg, sp, a, b)
    print("selfcheck ok: incremental funded account == engine/sizing + engine/funded_life")


def funded_mc(BY, paths, plan, cfg, ask=None, horizon=LEN):
    """Funded only, from its first funded session: 6 months on each path."""
    R = []
    for seq in paths:
        f = Funded(plan, cfg, ask)
        pay_at = []
        lost = grad = None
        for k, si in enumerate(seq[:horizon]):
            ev, x = f.step(BY[si])
            if ev in ("paid", "grad"):
                pay_at.append((k + 1, x))
            if ev == "lost":
                lost = k + 1
                break
            if ev == "grad":
                grad = k + 1
                break
        R.append({"f": f, "pay_at": pay_at, "lost": lost, "grad": grad})
    n = len(R)
    sp = FL.plan_of(plan)["split"]
    paid6 = np.array([sum(x for _, x in r["pay_at"]) for r in R])
    paid3 = np.array([sum(x for k, x in r["pay_at"] if k <= 63) for r in R])
    fr = [r["f"].first for r in R if r["f"].first]
    tp = np.array([r["f"].trade_pnl for r in R])
    left = np.array([r["f"].above_start() if r["f"].state != "lost" else 0.0 for r in R])
    lostamt = np.array([r["f"].above_start() if r["f"].state == "lost" else 0.0 for r in R])   # what the lost account had (<= 0 .. +100)
    idle = np.array([(horizon - r["grad"]) if r["grad"] else 0 for r in R])
    o = {"paths": n, "per_month": round(float(paid6.mean()) / 6.0), "paid_6m": round(float(paid6.mean())),
         "paid_p10": round(float(np.percentile(paid6, 10))), "paid_p50": round(float(np.percentile(paid6, 50))),
         "paid_3m": round(float(paid3.mean())),
         "loss_6m": round(100.0 * sum(1 for r in R if r["lost"]) / n, 1),
         "loss_3m": round(100.0 * sum(1 for r in R if r["lost"] and r["lost"] <= 63) / n, 1),
         "first_med": float(np.median(fr)) if fr else None, "any_pay": round(100.0 * len(fr) / n, 1),
         "payouts": round(float(np.mean([len(r["pay_at"]) for r in R])), 2),
         "grad_6m": round(100.0 * sum(1 for r in R if r["grad"]) / n, 1),
         "grad_med": float(np.median([r["grad"] for r in R if r["grad"]])) if any(r["grad"] for r in R) else None,
         "max_risk": round(max(r["f"].max_risk for r in R)),
         # where the money goes (6 months, per account, $ gross of the 80% split unless marked)
         "trade_pnl_m": round(float(tp.mean()) / 6.0), "paid_gross_m": round(float(paid6.mean()) / sp / 6.0),
         "left_end": round(float(left.mean())), "lost_end": round(float(lostamt.mean())),
         "idle_after_grad": round(float(idle.mean()), 1),
         "hold_cons": round(float(np.mean([r["f"].hold["cons"] for r in R])), 1),
         "hold_line": round(float(np.mean([r["f"].hold["line"] for r in R])), 1),
         "hold_cycle_days": round(float(np.mean([r["f"].hold["cycle_days"] for r in R])), 1),
         "over_max_at_pay": round(float(np.mean([r["f"].hold["max_left"] / max(1, len(r["pay_at"])) for r in R]))),
         "trades_6m": round(float(np.mean([r["f"].n_tr for r in R])), 1)}
    return o


# ================================================================================================ the eval
def ecfg_of(var=None, plan="builder50k"):
    c = copy.deepcopy(LIT_CFG)
    v = dict(var or {})
    tw = c["two_week"]
    for k in ("room_f", "need_buf", "max_usd", "wk", "press_at", "press_mult", "press_room"):
        if k in v:
            tw[k] = v.pop(k)
    if plan == "builder25k":
        tw["acct"] = dict(SZ.TW_25K)
    for k in ("wk_loss_usd", "two_week_until", "after_mode", "safe_cap"):
        if k in v:
            c[k] = v.pop(k)
    c["_maxq"] = v.pop("maxq", EPLAN[plan]["maxq"])
    c["_reset"] = v.pop("reset_at", None)     # buy a new eval when not passed after this many sessions (None = never)
    c["_stuck"] = v.pop("stuck", EPLAN[plan]["stuck"])
    assert not v, v
    return c


class Eval:
    """One MFFU Builder eval, a session at a time (tools/a4_eval_windows.run_window + second_mix.play_day for LIT)."""

    def __init__(self, cfg, plan="builder50k"):
        self.cfg, self.E = cfg, EPLAN[plan]
        self.sc = self.E["scale"]
        self.bal, self.peak, self.floor = 0.0, 0.0, -self.E["mll"]
        self.s = 0
        self.wk = {}
        self.dtr = 0
        self.max_risk = 0.0

    def step(self, ts):
        """-> "pass" | "fail" | "stuck" | "reset" | None"""
        c, E = self.cfg, self.E
        self.s += 1
        wkey = (self.s - 1) // 5
        cum = 0.0
        sub = {k: v for k, v in c.items() if not k.startswith("_")}
        traded = False
        for t in ts:
            if cum <= -E["dll"]:
                break
            m0 = qty_for(t["risk"])
            if self.sc != 1.0:
                m0 = max(1, int(m0 * self.sc)) if m0 else 0
            if not m0:
                continue
            st = {"profit": self.bal, "cum": cum, "room": self.bal + cum - self.floor, "session": self.s, "n_today": 0,
                  "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, sub, room=st["room"],
                           state=st, learning=None, max_micros=c["_maxq"])["qty"]
            q = min(q, c["_maxq"])
            if q <= 0:
                continue
            traded = True
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -E["dll"]:
                pnl = -E["dll"] - cum - SLIP * PV * q
                low = pnl
            if self.bal + cum + low <= self.floor:
                return "fail"
            cum += pnl
        self.bal += cum
        self.wk[wkey] = self.wk.get(wkey, 0.0) + cum
        self.dtr += 1 if traded else 0
        if self.bal <= self.floor:
            return "fail"
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - E["mll"]), E["lock"])
        if self.bal >= E["tgt"]:
            return "pass"
        if self.bal - self.floor < c["_stuck"]:
            return "stuck"
        if c["_reset"] and self.s >= c["_reset"]:
            return "reset"
        return None


def eval_rolling(BY, S, span, cfg, plan="builder50k", h=10, horizon=40):
    """A4-style rolling windows over the real half (one start per session; overlapping) + eventual within horizon."""
    a, z = span_ix(S, span)
    res = []
    for st in range(a, z):
        if st + h > z:
            break
        e = Eval(cfg, plan)
        out, used = "open", 0
        for k, si in enumerate(range(st, min(z, st + horizon))):
            r = e.step(BY[si])
            if r:
                out, used = r, k + 1
                break
        res.append((out, used, e.max_risk))
    n = len(res)
    p10 = sum(1 for o, u, _ in res if o == "pass" and u <= h)
    f10 = sum(1 for o, u, _ in res if o in ("fail", "stuck") and u <= h)
    return {"windows": n, "p10": round(100.0 * p10 / n, 1), "f10": round(100.0 * f10 / n, 1)}


def eval_mc(BY, paths, cfg, plan="builder50k", horizon=60):
    R = []
    for seq in paths:
        e = Eval(cfg, plan)
        out, used = "open", len(seq[:horizon])
        for k, si in enumerate(seq[:horizon]):
            r = e.step(BY[si])
            if r:
                out, used = r, k + 1
                break
        R.append((out, used, e.max_risk))
    n = len(R)
    pas = [u for o, u, _ in R if o == "pass"]
    p10 = 100.0 * sum(1 for u in pas if u <= 10) / n
    f10 = 100.0 * sum(1 for o, u, _ in R if o in ("fail", "stuck", "reset") and u <= 10) / n
    pev = 100.0 * len(pas) / n
    # $ per pass when every failed / stuck / reset eval is bought again (geometric): price / P(an eval passes)
    price = PRICE[plan]
    return {"p10": round(p10, 1), "f10": round(f10, 1), "dec10": round(p10 + f10, 1), "p_ever": round(pev, 1),
            "pass_med": float(np.median(pas)) if pas else None, "slow_pass": round(100.0 * sum(1 for u in pas if u > 15) / max(1, len(pas)), 1),
            "usd_per_pass": round(price / max(1e-9, pev / 100.0), 1), "max_risk": round(max(r[2] for r in R)),
            "sess_per_try": round(float(np.mean([u for _, u, _ in R])), 1)}


# ================================================================================================ the account slot
def life(BY, paths, ecfg, fcfg, plan="builder50k", ask=None, horizon=LEN, gap=GAP, raw=False):
    """One account slot for `horizon` sessions: eval -> gap -> funded -> (lost | 5 payouts) -> new eval ... ."""
    price = PRICE[plan]
    R = []
    for seq in paths:
        cost, owner, evals, funded_n, grads, losts = price, 0.0, 1, 0, 0, 0
        e, f, wait = Eval(ecfg, plan), None, 0
        first_pay = None
        pay_k = []
        for k, si in enumerate(seq[:horizon]):
            if f is None and wait == 0:
                r = e.step(BY[si])
                if r == "pass":
                    wait = gap
                    funded_n += 1
                elif r in ("fail", "stuck", "reset"):
                    cost += price
                    evals += 1
                    e = Eval(ecfg, plan)
            elif f is None:
                wait -= 1
                if wait == 0:
                    f = Funded(plan, fcfg, ask)
            else:
                ev, x = f.step(BY[si])
                if ev in ("paid", "grad"):
                    owner += x
                    pay_k.append(k + 1)
                    first_pay = first_pay or k + 1
                if ev in ("lost", "grad"):
                    if ev == "lost":
                        losts += 1
                    else:
                        grads += 1
                    f = None
                    cost += price
                    evals += 1
                    e = Eval(ecfg, plan)
        R.append({"owner": owner, "cost": cost, "net": owner - cost, "evals": evals, "funded": funded_n, "grads": grads,
                  "lost": losts, "first_pay": first_pay, "pays": len(pay_k)})
    if raw:
        return R
    n = len(R)
    net = np.array([r["net"] for r in R])
    mo = horizon / 21.0
    fp = [r["first_pay"] for r in R if r["first_pay"]]
    return {"net_m": round(float(net.mean()) / mo), "owner_m": round(float(np.mean([r["owner"] for r in R])) / mo),
            "cost_m": round(float(np.mean([r["cost"] for r in R])) / mo, 1), "net_6m": round(float(net.mean())),
            "net_p10": round(float(np.percentile(net, 10))), "net_p50": round(float(np.percentile(net, 50))),
            "p_neg": round(100.0 * float((net < 0).mean()), 1), "p_zero_pay": round(100.0 * sum(1 for r in R if r["pays"] == 0) / n, 1),
            "evals": round(float(np.mean([r["evals"] for r in R])), 2), "funded": round(float(np.mean([r["funded"] for r in R])), 2),
            "funded_m": round(float(np.mean([r["funded"] for r in R])) / mo, 2),
            "lost": round(float(np.mean([r["lost"] for r in R])), 2), "grads": round(float(np.mean([r["grads"] for r in R])), 2),
            "first_pay_med": float(np.median(fp)) if fp else None, "pays": round(float(np.mean([r["pays"] for r in R])), 2)}


# ================================================================================================ grids
F50 = {"pct": 0.4, "pct_min_usd": 100, "pct_max_usd": 800, "ref": 20, "wk": True, "room_f": None, "max_win": 1500,
       "slip_ticks": 2, "skip_breach": True}
F25 = {"pct": 0.4, "pct_min_usd": 50, "pct_max_usd": 400, "ref": 20, "wk": True, "room_f": None, "max_win": 750,
       "slip_ticks": 2, "skip_breach": True}


def frontier_grid(plan):
    base = F50 if plan == "builder50k" else F25
    k = 1.0 if plan == "builder50k" else 0.5
    rows = []
    for cap in (400, 600, 800, 1000, 1200, 1500):
        for pct in (0.3, 0.4, 0.5, 0.6, 0.7):
            for mw in (1500, None):
                rows.append((f"cap{cap}_p{int(pct * 100)}_{'mw' if mw else 'nomw'}",
                             {**base, "pct": pct, "pct_max_usd": cap * k, "pct_min_usd": 100 * k, "max_win": mw * k if mw else None}, None))
    for cap in (1000, 1500):                      # need-based: up to the cap, only what reaches the next full request
        for pct in (0.4, 0.5, 0.6):
            rows.append((f"need_cap{cap}_p{int(pct * 100)}", {**base, "pct": pct, "pct_max_usd": cap * k, "pct_min_usd": 100 * k,
                                                              "max_win": None, "need": 1.0}, None))
    return rows


def wincap_grid(plan):
    """The winner cap (the consistency lever) x the per-trade risk, plus the rejected 'harvest' idea."""
    base = F50 if plan == "builder50k" else F25
    k = 1.0 if plan == "builder50k" else 0.5
    rows = []
    for mw in (800, 1000, 1200, 2000, 2500):
        for cap, pct in ((800, 0.4), (1000, 0.5), (1200, 0.5), (1500, 0.6), (1500, 0.7)):
            rows.append((f"cap{cap}_p{int(pct * 100)}_mw{mw}", {**base, "pct": pct, "pct_max_usd": cap * k, "pct_min_usd": 100 * k,
                                                              "max_win": mw * k}, None))
    for h in (1500, 2000):
        rows.append((f"rec_harvest{h}", {**base, "harvest": h * k}, None))
    rows.append(("rec_cons_aware", {**base, "cons_aware": True}, None))
    rows.append(("cap1500_p60_mw2000_cons_aware", {**base, "pct": 0.6, "pct_max_usd": 1500 * k, "max_win": 2000 * k, "cons_aware": True}, None))
    return rows


def run_wincap(S, BY, n, out):
    for plan in ("builder50k", "builder25k"):
        P = {sp: mc_paths(S, sp, n) for sp in ("H1", "H2", "REF")}
        res = {}
        for cid, cfg, ask in wincap_grid(plan):
            res[cid] = {"cfg": cfg, **{sp: funded_mc(BY, P[sp], plan, cfg, ask) for sp in P}}
            h1, h2 = res[cid]["H1"], res[cid]["H2"]
            print(f"{plan} {cid:30s} H1 ${h1['per_month']:>5} | H2 ${h2['per_month']:>5} lost {h2['loss_6m']}% first {h2['first_med']} "
                  f"grad {h2['grad_6m']}% risk ${h2['max_risk']} | REF ${res[cid]['REF']['per_month']} lost {res[cid]['REF']['loss_6m']}%",
                  flush=True)
        out.setdefault("wincap", {})[plan] = res


EVAL_VARS = [
    ("today", {}),
    ("rf60", {"room_f": 0.6}),
    ("rf70", {"room_f": 0.7}),
    ("rf80", {"room_f": 0.8}),
    ("rf100", {"room_f": 1.0}),
    ("rf70_nb125", {"room_f": 0.7, "need_buf": 1.25}),
    ("rf80_nb150", {"room_f": 0.8, "need_buf": 1.5}),
    ("rf70_nowk", {"room_f": 0.7, "wk_loss_usd": None}),
    ("rf80_nowk", {"room_f": 0.8, "wk_loss_usd": None}),
    ("rf70_tw20", {"room_f": 0.7, "two_week_until": 20}),
    ("rf80_tw99", {"room_f": 0.8, "wk_loss_usd": None, "two_week_until": 999}),
    ("today_reset10", {"reset_at": 10}),
    ("rf80_reset10", {"room_f": 0.8, "wk_loss_usd": None, "reset_at": 10}),
    ("rf100_reset10", {"room_f": 1.0, "wk_loss_usd": None, "reset_at": 10}),
    ("today_reset15", {"reset_at": 15}),
    ("rf80_q20", {"room_f": 0.8, "maxq": 20}),
    ("rf40_nowk_tw80", {"room_f": 0.4, "wk_loss_usd": None, "two_week_until": 80}),   # the live switches since 2026-11-14 (owner "yes 40%")
]


# ================================================================================================ main
def load():
    S = sessions()
    T = trades()
    BY = [T.get(d, []) for d in S]
    return S, BY


def run_frontier(S, BY, n, out, plans=("builder50k", "builder25k")):
    for plan in plans:
        P = {sp: mc_paths(S, sp, n) for sp in ("H1", "H2")}
        res = {}
        for cid, cfg, ask in frontier_grid(plan):
            res[cid] = {"cfg": cfg, **{sp: funded_mc(BY, P[sp], plan, cfg, ask) for sp in ("H1", "H2")}}
            h1, h2 = res[cid]["H1"], res[cid]["H2"]
            print(f"{plan} {cid:22s} H1 ${h1['per_month']:>5} lost {h1['loss_6m']:>5}% first {h1['first_med']} "
                  f"| H2 ${h2['per_month']:>5} lost {h2['loss_6m']:>5}% first {h2['first_med']} grad {h2['grad_6m']}% risk ${h2['max_risk']}",
                  flush=True)
        out.setdefault("frontier", {})[plan] = res


def run_asks(S, BY, n, out):
    P = {sp: mc_paths(S, sp, n) for sp in ("H1", "H2")}
    res = {}
    for ask in (500, 1000, 1500, 2000):
        for cid, cfg in (("rec", F50), ("cap1200_p50_mw", {**F50, "pct": 0.5, "pct_max_usd": 1200})):
            k = f"{cid}_ask{ask}"
            res[k] = {sp: funded_mc(BY, P[sp], "builder50k", cfg, ask) for sp in ("H1", "H2")}
            print("ask", k, res[k]["H1"]["per_month"], res[k]["H2"]["per_month"], flush=True)
    out["asks"] = res


def run_decomp(S, BY, n, out):
    P = {sp: mc_paths(S, sp, n) for sp in ("H1", "H2", "REF")}
    res = {}
    for plan, cfg in (("builder50k", F50), ("builder25k", F25)):
        res[plan] = {sp: funded_mc(BY, P[sp], plan, cfg) for sp in P}
        print("decomp", plan, json.dumps(res[plan]["H2"]), flush=True)
    out["decomp"] = res


def run_eval(S, BY, n, out):
    P = {sp: mc_paths(S, sp, n, length=60) for sp in ("H1", "H2", "REF")}
    res = {}
    for cid, var in EVAL_VARS:
        cfg = ecfg_of(var)
        row = {"var": var}
        for sp in ("H1", "H2", "REF"):
            row[sp] = eval_mc(BY, P[sp], cfg)
        row["H1_roll"] = eval_rolling(BY, S, "H1", cfg)
        row["H2_roll"] = eval_rolling(BY, S, "H2", cfg)
        res[cid] = row
        print(f"eval {cid:15s} H1 p10 {row['H1']['p10']:>5} f10 {row['H1']['f10']:>5} ever {row['H1']['p_ever']:>5} ${row['H1']['usd_per_pass']:>6} "
              f"| H2 p10 {row['H2']['p10']:>5} f10 {row['H2']['f10']:>5} ever {row['H2']['p_ever']:>5} ${row['H2']['usd_per_pass']:>6} "
              f"| roll H1 {row['H1_roll']['p10']} H2 {row['H2_roll']['p10']} | REF p10 {row['REF']['p10']} f10 {row['REF']['f10']} risk ${row['H2']['max_risk']}",
              flush=True)
    out["eval"] = res


LIFE_EVAL = ["today", "rf70", "rf80_nowk", "rf100_reset10", "rf80_reset10", "today_reset10"]
FUND_ALL = {"rec25": F25, "c25_cap500_p50": {**F25, "pct": 0.5, "pct_max_usd": 500},
            "c25_cap600_p50": {**F25, "pct": 0.5, "pct_max_usd": 600}, "c25_cap750_p60": {**F25, "pct": 0.6, "pct_max_usd": 750}}
LIFE_FUND = {"rec": F50, "cap1000_p50_mw": {**F50, "pct": 0.5, "pct_max_usd": 1000},
             "cap1200_p50_mw": {**F50, "pct": 0.5, "pct_max_usd": 1200}, "cap1500_p60_mw": {**F50, "pct": 0.6, "pct_max_usd": 1500},
             "cap1500_p70_nomw": {**F50, "pct": 0.7, "pct_max_usd": 1500, "max_win": None}}


FUND_ALL.update(LIFE_FUND)
UP50 = {**F50, "pct": 0.6, "pct_max_usd": 1500, "max_win": 2000}          # the uprisk candidate (50K)
UP25 = {**F25, "pct": 0.6, "pct_max_usd": 750, "pct_min_usd": 50, "max_win": 1000}   # the same rule at the 25K's half scale
FUND_ALL.update({"up50": UP50, "up25": UP25})


def run_lifeup(S, BY, n, out):
    P = {sp: mc_paths(S, sp, n) for sp in ("H1", "H2", "REF")}
    EV = dict(EVAL_VARS)
    res = {}
    for ek in ("today", "rf80_nowk", "rf100_reset10", "today_reset10"):
        for fk in ("rec", "up50"):
            k = f"{ek}__{fk}"
            res[k] = {sp: life(BY, P[sp], ecfg_of(EV[ek]), FUND_ALL[fk]) for sp in P}
            a, b, c = res[k]["H1"], res[k]["H2"], res[k]["REF"]
            print(f"lifeup {k:28s} H1 ${a['net_m']:>5}/mo p_neg {a['p_neg']}% | H2 ${b['net_m']:>5}/mo p_neg {b['p_neg']}% evals {b['evals']} "
                  f"funded {b['funded']} grads {b['grads']} first {b['first_pay_med']} | REF ${c['net_m']}/mo p_neg {c['p_neg']}%", flush=True)
    out["lifeup"] = res


def run_life(S, BY, n, out, extra_fund=None):
    P = {sp: mc_paths(S, sp, n) for sp in ("H1", "H2", "REF")}
    EV = dict(EVAL_VARS)
    FU = {**LIFE_FUND, **(extra_fund or {})}
    res = {}
    for ek in LIFE_EVAL:
        for fk, fc in FU.items():
            k = f"{ek}__{fk}"
            res[k] = {sp: life(BY, P[sp], ecfg_of(EV[ek]), fc) for sp in P}
            a, b, c = res[k]["H1"], res[k]["H2"], res[k]["REF"]
            print(f"life {k:32s} H1 ${a['net_m']:>5}/mo p_neg {a['p_neg']:>5}% | H2 ${b['net_m']:>5}/mo p_neg {b['p_neg']:>5}% "
                  f"evals {b['evals']} funded {b['funded']} lost {b['lost']} grads {b['grads']} | REF ${c['net_m']}/mo", flush=True)
    out["life"] = res


def book(BY, S, span, slots, n=N_MC, offset=5):
    """Several account slots on the SAME market path (same trades, correlated), slot j bought offset*j sessions later.
    slots = [(plan, ecfg, fcfg)]. -> $ a month net of evals (mean, p10), P(book loses money), P(every slot pays $0)."""
    L = LEN + offset * (len(slots) - 1)
    P = mc_paths(S, span, n, length=L)
    per = []
    for j, (plan, ec, fc) in enumerate(slots):
        sub = [seq[offset * j: offset * j + LEN] for seq in P]
        per.append(life(BY, sub, ec, fc, plan=plan, raw=True))
    net = np.array([sum(per[j][i]["net"] for j in range(len(slots))) for i in range(n)])
    zero = np.mean([all(per[j][i]["pays"] == 0 for j in range(len(slots))) for i in range(n)])
    nets = np.array([[per[j][i]["net"] for j in range(len(slots))] for i in range(n)])
    cor = float(np.corrcoef(nets[:, 0], nets[:, 1])[0, 1]) if len(slots) > 1 else None
    mo = LEN / 21.0
    return {"slots": len(slots), "net_m": round(float(net.mean()) / mo), "net_p10_m": round(float(np.percentile(net, 10)) / mo),
            "net_p50_m": round(float(np.percentile(net, 50)) / mo), "p_neg": round(100.0 * float((net < 0).mean()), 1),
            "p_all_zero": round(100.0 * float(zero), 1), "corr_12": round(cor, 2) if cor is not None else None,
            "evals": round(float(np.mean([sum(per[j][i]["evals"] for j in range(len(slots))) for i in range(n)])), 2),
            "lost": round(float(np.mean([sum(per[j][i]["lost"] for j in range(len(slots))) for i in range(n)])), 2)}


BOOK_FUND = {"rec": ("rec", "rec25"), "up": ("up50", "up25")}


def run_book(S, BY, n, out, fsel=None):
    """MFFU: 1 x 50K + 2 x 25K (the per-person limit), and 3 / 5 slots of 50K rules (a proxy for other firms' 50Ks)."""
    EV = dict(EVAL_VARS)
    e50, e25 = ecfg_of(EV["today"]), ecfg_of(EV["today"], plan="builder25k")
    res = {}
    for fk, (k50, k25) in (fsel or BOOK_FUND).items():
        f50, f25 = FUND_ALL[k50], FUND_ALL[k25]
        books = {"mffu_50": [("builder50k", e50, f50)],
                 "mffu_50_25_25": [("builder50k", e50, f50), ("builder25k", e25, f25), ("builder25k", e25, f25)],
                 "x3_50": [("builder50k", e50, f50)] * 3, "x5_50": [("builder50k", e50, f50)] * 5}
        for bk, sl in books.items():
            k = f"{fk}__{bk}"
            res[k] = {sp: book(BY, S, sp, sl, n) for sp in ("H1", "H2", "REF")}
            a, b, c = res[k]["H1"], res[k]["H2"], res[k]["REF"]
            print(f"book {k:28s} H1 ${a['net_m']:>6}/mo p10 ${a['net_p10_m']:>6} | H2 ${b['net_m']:>6}/mo p10 ${b['net_p10_m']:>6} "
                  f"p_neg {b['p_neg']}% all0 {b['p_all_zero']}% corr {b['corr_12']} | REF ${c['net_m']}/mo p_neg {c['p_neg']}%", flush=True)
    out["book"] = res


def run_life25(S, BY, n, out):
    P = {sp: mc_paths(S, sp, n) for sp in ("H1", "H2", "REF")}
    EV = dict(EVAL_VARS)
    res = {}
    for ek in ("today", "rf80_nowk"):
        for fk in ("rec25", "c25_cap500_p50", "c25_cap750_p60", "up25"):
            k = f"{ek}__{fk}"
            res[k] = {sp: life(BY, P[sp], ecfg_of(EV[ek], plan="builder25k"), FUND_ALL[fk], plan="builder25k") for sp in P}
            a, b, c = res[k]["H1"], res[k]["H2"], res[k]["REF"]
            print(f"life25 {k:30s} H1 ${a['net_m']:>5}/mo | H2 ${b['net_m']:>5}/mo p_neg {b['p_neg']}% lost {b['lost']} | REF ${c['net_m']}/mo",
                  flush=True)
    out["life25"] = res


def real_path(BY, S, span, plan, cfg, ask=None):
    """One funded account from the half's first session (the real 2026 order): its sized trades + payouts."""
    a, z = span_ix(S, span)
    f = Funded(plan, cfg, ask)
    keep, pays = [], []
    for k, si in enumerate(range(a, z)):
        n0 = len(keep)
        ev, x = f.step(BY[si], keep=keep)
        for t, q, pnl in keep[n0:]:
            t["_day"] = S[si]
        if ev in ("paid", "grad"):
            pays.append([k + 1, round(x)])
        if ev in ("lost", "grad"):
            break
    T = []
    for i, (t, q, pnl) in enumerate(keep):
        d = dt.date.fromisoformat(t["_day"])
        et = int(dt.datetime(d.year, d.month, d.day, 14, 0, tzinfo=dt.timezone.utc).timestamp()) + i
        ru = t["risk"] * PV * q
        T.append({"day": t["_day"], "entry_t": et, "exit_t": et + 60, "dir": 1, "r": round(pnl / ru, 3) if ru else 0.0,
                  "pnl": round(pnl, 2), "risk_pts": t["risk"], "qty": q, "risk_usd": round(ru, 2), "half": t.get("size_mult", 1) < 1,
                  "exit": "", "trigger": "funded", "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": None})
    return T, {"payouts": len(pays), "paid": sum(x for _, x in pays), "pay_at": pays, "lost": f.state == "lost"}


def save_runs(picks):
    """picks = [(run id, title, plan, funded cfg, status, verdict)] -> research/runs/<id>.json (tools/runlib)."""
    from tools import runlib as rl
    S, BY = load()
    S26 = [d for d in S if d >= "2026-01-01"]
    for rid, title, plan, cfg, status, verdict in picks:
        T, info = [], {}
        for sp in ("H1", "H2"):
            t, info[sp] = real_path(BY, S, sp, plan, cfg)
            T += t
        T.sort(key=lambda t: (t["day"], t["entry_t"]))
        v = verdict + (f" Real 2026 path (one account from the half's first session): H1 {info['H1']['payouts']} payouts "
                       f"${info['H1']['paid']:,} to you, H2 {info['H2']['payouts']} payouts ${info['H2']['paid']:,}.")
        rl.save(rid, title, "risk", "Owner 2026-10-25: should we uprisk? Where is the funded money capped and what pays more a "
                "month?", params={"plan": plan, "strategy": "lit"}, sizing={"mode": "funded", **cfg}, trades=T,
                scored=rl.score(T, S26), status=status, verdict=v,
                notes="tools/uprisk.py (research/lit/uprisk_*.json); MC 1,000 x 126 sessions in 5-session blocks, seed 23; "
                      "$1.90 a micro; the run-library eval columns are not the funded numbers (see the verdict).",
                writeup="uprisk", tags=["funded", "uprisk", plan])
        print("saved", rid, info, flush=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    what = args[0] if args else "all"
    if what == "selfcheck":
        return selfcheck()
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else N_MC
    S, BY = load()
    for w, fn in (("decomp", run_decomp), ("frontier50", lambda *a: run_frontier(*a, plans=("builder50k",))),
                  ("frontier25", lambda *a: run_frontier(*a, plans=("builder25k",))), ("asks", run_asks), ("eval", run_eval), ("wincap", run_wincap), ("lifeup", run_lifeup),
                  ("life", run_life), ("book", run_book), ("life25", run_life25)):
        if what in (w, "all"):
            out = {"built": dt.date.today().isoformat(), "n": n}
            fn(S, BY, n, out)
            path = OUT.replace(".json", f"_{w}.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump(out, open(path, "w", encoding="utf-8"), indent=1, default=float)
            print("->", path)


if __name__ == "__main__":
    main()
