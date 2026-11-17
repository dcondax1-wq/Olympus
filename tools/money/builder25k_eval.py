"""Eval sizing for a FRESH MFFU Builder 25K (owner buys one 2026-11-17): which LIT eval sizing passes fastest without raising
fails? Write-up: research/writeups/builder25k-eval-sizing-2026-11-17.md. PAPER RESEARCH ONLY: reads stored trades, writes
research/lab/builder25k_eval.json, changes nothing live (no live_model*.json, no engine file).

The 25K: $1,500 target, $1,000 EOD trailing (locks at +$100), $600 soft daily loss, max 20 micros, no eval consistency, 1 day.
Every option is the EXACT bot config: engine/multi_account.sizing_cfg(live_model.json lit_sizing, a mffu_builder_25k spec +
the option's lit_sizing override) -> engine/sizing.lit_qty, n_today counted (the preset's day guard = 1 LIT entry a day).
Options: room_f 0.3-0.6 / a $ risk cap a trade ($150-$400 = two_week.max_usd x the 25K's 0.5 scale) / LIT + ATLAS in the
eval (stack_q: <= $250 and 20-30% of the room) / "first-hit" (a bigger room share for the eval's first trade(s), then smaller).
Funded after the pass (the research plan, builder-levers 2026-11-16): LIT (UP25) + ATLAS $250 (30% of the room).

Metrics per span (H1 = 2026 Jan-Jun pick, H2 = Jul-Oct check, REF = 2021-11..2025): one eval from fresh, 60 sessions:
median sessions to pass, pass / fail within 10 sessions (2 weeks), fail within 60; the seat (eval -> 2 sessions paperwork ->
funded, a failed eval re-bought at $63): first funded payout median sessions + date (from 2026-11-18), $ a month after fees.
Same Monte Carlo paths as builder_levers (5-session blocks, seeds 7 / 23). + how often the 20-micro cap binds / a trade is
skipped because 1 micro does not fit.

    python -X utf8 tools/money/builder25k_eval.py            # -> research/lab/builder25k_eval.json
    python -X utf8 tools/money/builder25k_eval.py --n 300    # quicker
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import builder_levers as BL  # noqa: E402

SA, U, A4 = BL.SA, BL.U, BL.A4
ROOT = BL.ROOT
from engine import multi_account as MA  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

PV, COMM, SLIP = BL.PV, BL.COMM, BL.SLIP
OUT = os.path.join(ROOT, "research", "lab", "builder25k_eval.json")
SPANS = BL.SPANS
E25 = BL.E25
PRICE = 63.00
START_DAY = "2026-11-18"
LIVE = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
RULES = MA.PRESETS["mffu_builder_25k"]["rules"]
F25 = {"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)}       # funded: LIT + ATLAS $250 (builder-levers pick)


def cfg_of(over=None):
    """The bot's own lit_sizing for a mffu_builder_25k account with the override `over` (multi_account.sizing_cfg)."""
    spec = {"preset": "mffu_builder_25k", "rules": dict(RULES), "mode": "two_week", "eval_start": "",
            "lit_sizing": copy.deepcopy(over or {})}
    c = MA.sizing_cfg(copy.deepcopy(LIVE), spec)
    return c


def tw(room_f, max_usd=None, until=80, safe_cap=0.6):
    """Override: two_week room_f (+ a $ cap a trade: two_week.max_usd is scaled x 0.5 on the 25K, so $X real = max_usd 2X)."""
    return {"two_week": {"room_f": room_f, "max_usd": (2.0 * max_usd) if max_usd else None}, "two_week_until": until,
            "after_mode": "safe_eval", "safe_cap": safe_cap}


# name -> (lit cfg override, first-hit (n trades, cfg override for those) or None, ATLAS in the eval (usd, f) or None)
OPTS = {
    "preset today (50% room to s10, then safe 30%)": ({}, None, None),
    "live 50K rule (40% room to s80)": (tw(0.4), None, None),
    "room 30%": (tw(0.3), None, None),
    "room 35%": (tw(0.35), None, None),
    "room 45%": (tw(0.45), None, None),
    "room 50%": (tw(0.5), None, None),
    "room 55%": (tw(0.55), None, None),
    "room 60%": (tw(0.6), None, None),
    "room 50% + cap $150": (tw(0.5, 150), None, None),
    "room 50% + cap $200": (tw(0.5, 200), None, None),
    "room 50% + cap $250": (tw(0.5, 250), None, None),
    "room 50% + cap $300": (tw(0.5, 300), None, None),
    "room 50% + cap $400": (tw(0.5, 400), None, None),
    "room 60% + cap $300": (tw(0.6, 300), None, None),
    "room 60% + cap $400": (tw(0.6, 400), None, None),
    "first-hit 60% then 40%": (tw(0.4), (1, tw(0.6)), None),
    "first-hit 60% then 30%": (tw(0.3), (1, tw(0.6)), None),
    "first-hit 50% then 35%": (tw(0.35), (1, tw(0.5)), None),
    "first-hit 50% then 40%": (tw(0.4), (1, tw(0.5)), None),
    "first-hit 2 trades 50% then 40%": (tw(0.4), (2, tw(0.5)), None),
    "LIT 40% + ATLAS $250 at 20%": (tw(0.4), None, (250.0, 0.2)),
    "LIT 40% + ATLAS $250 at 30%": (tw(0.4), None, (250.0, 0.3)),
    "LIT 50% + ATLAS $250 at 20%": (tw(0.5), None, (250.0, 0.2)),
}
BASE = "live 50K rule (40% room to s80)"


class Ev25(BL.GEv):
    """BL.GEv on a fresh 25K with the bot's own cfg (n_today and the eval's trade count tracked) + cap-binding counters."""

    def __init__(self, opt, count=False):
        over, fh, atl = OPTS[opt]
        z = {"LIT": ("lit", cfg_of(over))}
        if atl:
            z["ATLAS"] = ("stack", atl[0], atl[1])
        super().__init__(E25, z, stuck=RULES["min_room"])
        self.fh = (fh[0], cfg_of(fh[1])) if fh else None
        self.n_tr = 0
        self.count = count
        self.cnt = {"lit_signals": 0, "lit_traded": 0, "skip_1micro": 0, "skip_room700": 0, "cap20": 0, "cap20_lost": 0,
                    "bind_need": 0, "bind_room": 0, "bind_dll": 0, "bind_usd": 0, "bind_other": 0}

    def _lit(self, t, st, room):
        cfg = self.fh[1] if (self.fh and self.n_tr < self.fh[0]) else self.z["LIT"][1]
        m0 = qty_for(t["risk"])
        if not m0:
            return 0
        tr = {"risk_pts": t["risk"], "tgt_pts": t["tgt"] or 2.0 * t["risk"], "size_mult": 1.0}
        sub = {k: v for k, v in cfg.items() if not k.startswith("_")}
        r = SZ.lit_qty(m0, tr, sub, room=room, state=st, learning=None, max_micros=20)
        q = int(r["qty"])
        if self.count:
            if q > 0:
                tail = (r["reasons"] or [""])[-1]
                k = ("bind_room" if "room ->" in tail else "bind_dll" if "daily loss" in tail
                     else "bind_usd" if "a trade ->" in tail else "bind_need" if "one winner" in tail else "bind_other")
                self.cnt[k] += 1
            self.cnt["lit_signals"] += 1
            big = copy.deepcopy(sub)
            big["two_week"]["acct"]["max_micros"] = 200
            if big.get("guard"):
                big["guard"]["max_micros"] = 200
            q2 = int(SZ.lit_qty(m0, tr, big, room=room, state=st, learning=None, max_micros=200)["qty"])
            if q > 0:
                self.cnt["lit_traded"] += 1
            elif st.get("n_today", 0) == 0 and st["profit"] + st["cum"] < E25["tgt"]:
                self.cnt["skip_1micro"] += 1
                self.cnt["skip_room700"] += room >= 700
            if q2 > q and q == 20:
                self.cnt["cap20"] += 1
                self.cnt["cap20_lost"] += q2 - q
        return min(q, 20)

    def step(self, ts):
        E = self.E
        dll = E["dll"]
        self.s += 1
        wkey = (self.s - 1) // 5
        cum, traded, nlit = 0.0, False, 0
        for t in ts:
            if cum <= -dll:
                break
            room = self.bal + cum - self.floor
            st = {"profit": self.bal, "cum": cum, "room": room, "session": self.s, "n_today": nlit,
                  "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
            if t["strat"] == "LIT":
                q = self._lit(t, st, room)
            elif t["strat"] in self.z:
                q = SA.stack_q(t, {t["strat"]: {"usd": self.z[t["strat"]][1], "f": self.z[t["strat"]][2]}}, room, cum, E["maxq"],
                               min(dll, SA.SOFT_DLL))
                if self.bal + cum >= E["tgt"]:
                    q = 0
            else:
                q = 0
            if q <= 0:
                continue
            traded = True
            self.n_tr += 1
            nlit += t["strat"] == "LIT"
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if self.bal + cum + low <= self.floor:
                return "fail", round(self.floor - self.bal, 2)
            cum += pnl
        self.bal += cum
        self.wk[wkey] = self.wk.get(wkey, 0.0) + cum
        if traded:
            self.dtr += 1
        if self.bal <= self.floor:
            return "fail", round(cum, 2)
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - E["mll"]), E["lock"])
        if self.bal >= E["tgt"] and self.dtr >= 1:
            return "pass", round(cum, 2)
        if self.bal - self.floor < self.stuck:
            return "stuck", round(cum, 2)
        return None, round(cum, 2)


def eval_one(BY, paths, opt, h=60):
    res = []
    for seq in paths:
        e = Ev25(opt)
        out, used = "open", h
        for k, si in enumerate(seq[:h]):
            r, _ = e.step(BY[si])
            if r:
                out, used = ("pass" if r == "pass" else "fail"), k + 1
                break
        res.append((out, used))
    n = len(res)
    pas = sorted(u for o, u in res if o == "pass")
    allu = sorted(u if o == "pass" else 999 for o, u in res)
    return {"p10": round(100.0 * sum(1 for u in pas if u <= 10) / n, 1),
            "f10": round(100.0 * sum(1 for o, u in res if o == "fail" and u <= 10) / n, 1),
            "p60": round(100.0 * len(pas) / n, 1), "f60": round(100.0 * sum(1 for o, _ in res if o == "fail") / n, 1),
            "pass_med": float(np.median(pas)) if pas else None,
            "med_all": float(allu[n // 2]) if allu[n // 2] < 999 else None}


def counters(BY, paths, opt, h=60):
    tot = {}
    for seq in paths:
        e = Ev25(opt, count=True)
        for si in seq[:h]:
            r, _ = e.step(BY[si])
            if r:
                break
        for k, v in e.cnt.items():
            tot[k] = tot.get(k, 0) + v
    s = max(1, tot["lit_signals"])
    return {**tot, "cap20_pct_of_signals": round(100.0 * tot["cap20"] / s, 1),
            "skip_pct_of_signals": round(100.0 * tot["skip_1micro"] / s, 1),
            "skip_room700_pct": round(100.0 * tot["skip_room700"] / s, 1),
            "bind_pct": {k[5:]: round(100.0 * tot[k] / max(1, tot["lit_traded"]), 1) for k in tot if k.startswith("bind_")},
            "cap20_avg_micros_lost": round(tot["cap20_lost"] / max(1, tot["cap20"]), 1)}


def seats(BYe, BYf, paths, cal):
    M = {nm: (lambda nm=nm: BL.Seat(lambda _=None, nm=nm: Ev25(nm), lambda: BL.GF("builder25k", U.UP25, F25), PRICE,
                                    [Ev25(nm)], cost0=PRICE)) for nm in OPTS}
    R = BL.run_seats({k: (BYe["LA"] if OPTS[k][2] else BYe["L"]) for k in M}, {k: BYf for k in M}, paths, M)
    return {nm: BL.seat_stats(v, cal) for nm, v in R.items()}


def stop_stats(BYl, span):
    S = SA.data()["S"]
    a, z = U.span_ix(S, span)
    rs = [t["risk"] for i in range(a, z) for t in BYl[i]]
    rs = np.array(rs)
    multi = sum(1 for i in range(a, z) if len(BYl[i]) > 1)
    days = sum(1 for i in range(a, z) if BYl[i])
    return {"n": int(len(rs)), "stop_p10": round(float(np.percentile(rs, 10)), 1), "stop_med": round(float(np.median(rs)), 1),
            "stop_p90": round(float(np.percentile(rs, 90)), 1), "stop_max": round(float(rs.max()), 1),
            "days_2plus_lit": multi, "lit_days": days,
            "micros20_risk_usd_at_med": round(20 * ((float(np.median(rs)) + SLIP) * PV + COMM))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import payout_plan as PP
    cal = PP.calendar(U.LEN + 5, START_DAY)
    S = SA.data()["S"]
    t0 = time.time()
    PE = {sp: U.mc_paths(S, sp, a.n, length=60, seed=A4.SEED_EVAL) for sp in SPANS}
    PF = {sp: U.mc_paths(S, sp, a.n, length=U.LEN, seed=A4.SEED_LIFE) for sp in SPANS}
    BYe = {"L": BL.by_mix(("LIT",)), "LA": BL.by_mix(("LIT", "ATLAS"))}
    BYf = BYe["LA"]
    out = {"date": "2026-11-17", "n": a.n, "start_day": START_DAY, "base": BASE, "spans": U.SPAN, "eval": {}, "seat": {},
           "cap": {}, "stops": {}, "configs": {k: v[0] for k, v in OPTS.items()}}
    for sp in SPANS:
        out["stops"][sp] = stop_stats(BYe["L"], sp)
        out["eval"][sp] = {}
        for nm in OPTS:
            out["eval"][sp][nm] = eval_one(BYe["LA"] if OPTS[nm][2] else BYe["L"], PE[sp], nm)
        out["seat"][sp] = seats(BYe, BYf, PF[sp], cal)
        for nm in OPTS:
            e, s = out["eval"][sp][nm], out["seat"][sp][nm]
            print(f"{sp:3s} {nm:46s} med {e['pass_med']} (all {e['med_all']}) 2wk {e['p10']:5.1f}/{e['f10']:4.1f} "
                  f"60: {e['p60']:5.1f}/{e['f60']:4.1f} | 1st pay {s['first_pay_med']} ({s['first_pay_date']}) "
                  f"nopay {s['no_pay_6m']}% ${s['net_m']}/mo evals {s['evals']}", flush=True)
        print(f"  {sp} stops {out['stops'][sp]}  ({time.time() - t0:.0f}s)", flush=True)
    for sp in SPANS:
        out["cap"][sp] = {nm: counters(BYe["LA"] if OPTS[nm][2] else BYe["L"], PE[sp][:300], nm)
                          for nm in (BASE, "preset today (50% room to s10, then safe 30%)", "room 50%", "room 60%",
                                     "room 50% + cap $300", "first-hit 60% then 40%", "first-hit 50% then 40%",
                                     "LIT 40% + ATLAS $250 at 20%")}
        for nm, c in out["cap"][sp].items():
            print(f"  cap {sp} {nm:46s} {c}")
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        print("wrote", os.path.relpath(OUT, ROOT))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
