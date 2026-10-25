"""The sizing cap invariant (pre-launch audit 2026-10-24, research/writeups/sizing-caps.md): every $ budget is a ceiling.
Micros are computed after ALL caps (room to the trailing max-loss floor, 60% / 50% / 30% room caps, the soft daily loss
$1,000 50K / $600 25K, the eval weekly loss stop, ATLAS's $ risk a trade); when not even 1 micro fits a cap the entry is
SKIPPED (qty 0), never raised back to 1. Every cap prices 1 micro at (stop + 1 tick) x $2 + $1.90. Kept on purpose: the
1-micro minimum-days trade after an early target, but only when that micro fits too.

Covers LIT (engine/sizing.lit_qty, every eval mode on the live config), ATLAS on LIT's account (sizing.second_qty),
account B (engine/account_b.qty, Builder 25K and 50K, need + safe) and an extra account (engine/multi_account
Account.qty_for, 25K / 50K presets), each with nearly exhausted room, the daily loss nearly used, a wide stop, plus a
randomised sweep that checks qty x loss <= every ceiling on thousands of states.

    python -X utf8 -m tests.test_sizing_caps          # ~5 s
Paper only: no adapter, no file written.
"""
from __future__ import annotations

import json
import logging
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_b as AB  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import sizing as sz  # noqa: E402
from engine import lit  # noqa: E402

logging.getLogger("engine.sizing").setLevel(logging.ERROR)
RESULTS = []
from tests.sizing_pins import LIVE, PINNED, live_checks  # noqa: E402

# the cases below test the sizing math on a pinned config (room_f 0.55, the $1,200 weekly stop: the values they were
# written for); the sweeps also run on the live config (owner 2026-10-25: room_f 0.8, no eval weekly stop)
LSZ = PINNED


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def L1(risk):
    return (float(risk) + 0.25) * 2.0 + 1.90


def st_of(profit=0.0, cum=0.0, room=2000.0, session=1, n_today=0, days_traded=0, wk_pnl=None):
    s = {"profit": profit, "cum": cum, "room": room, "session": session, "n_today": n_today, "days_traded": days_traded}
    if wk_pnl is not None:
        s["wk_pnl"] = wk_pnl
    return s


def lq(risk, tgt, state, cfg=None, room=None, maxq=40):
    c = dict(LSZ if cfg is None else cfg)
    return sz.lit_qty(lit.qty_for(risk) or 1, {"risk_pts": risk, "tgt_pts": tgt, "size_mult": 1.0}, c,
                      room=state.get("room") if room is None and state else room, state=state, max_micros=maxq, learning=None)


def skipped(r):
    return int(r.get("qty") or 0) == 0 and any(str(w).split(": ", 1)[-1].startswith("skip") or "skip:" in str(w) for w in r.get("reasons") or [])


# ------------------------------------------------------------------------------------------------ LIT (50K, live cfg)
def lit_cases():
    # nearly exhausted room: $120 to the floor, 50-pt stop: 55% x 120 = $66 < 1 micro ($102.40) -> skip (was 1 micro)
    r = lq(50.0, 200.0, st_of(profit=-1880.0, room=120.0, session=3))
    check("LIT two_week: room $120, 50-pt stop -> skip (1 micro $102 > 55% room $66)", skipped(r), r)
    # daily loss nearly used: today -$950, $50 left, 40-pt stop ($82.40 a micro) -> skip
    r = lq(40.0, 150.0, st_of(cum=-950.0, room=1050.0, session=2))
    check("LIT two_week: day -$950 of the $1,000 soft loss, 40-pt stop -> skip", skipped(r), r)
    # wide stop: 88 pts = $178.40 a micro (1 tick, $1.90); 55% of $330 room = $181.50 -> 1 fits; 55% of $320 = $176 -> skip
    # (room_f 0.55 since the owner's safe switches 2026-10-24; was 60% of $300 / $290)
    r1 = lq(88.0, 200.0, st_of(profit=-1670.0, room=330.0, session=4))
    r0 = lq(88.0, 200.0, st_of(profit=-1680.0, room=320.0, session=4))
    check("LIT two_week: 88-pt stop, room $330 -> 1 micro ($178.40 <= $181.50)", int(r1["qty"]) == 1, r1)
    check("LIT two_week: 88-pt stop, room $320 -> skip ($178.40 > $176)", skipped(r0), r0)
    # a normal fresh eval is unchanged in kind: one winner passes, inside every cap
    r = lq(40.0, 200.0, st_of())
    check("LIT two_week fresh eval: 40-pt stop, 200-pt target -> 8 micros (one winner passes)", int(r["qty"]) == 8, r)
    # safe_eval after session 10 (after_mode): room $150, 80-pt stop -> skip; and the soft daily loss now applies there too
    r = lq(80.0, 200.0, st_of(profit=-1850.0, room=150.0, session=12))
    check("LIT safe_eval (session 12): room $150, 80-pt stop -> skip (was 1 micro)", skipped(r), r)
    r = lq(30.0, 200.0, st_of(profit=500.0, cum=-950.0, room=1550.0, session=12))
    check("LIT safe_eval (session 12): day -$950, 30-pt stop -> skip (the final ceilings check the soft daily loss)", skipped(r), r)
    # mode eval / fast_eval with a tiny room
    for m in ("eval", "fast_eval", "safe_eval"):
        r = lq(60.0, 200.0, st_of(profit=-1900.0, room=100.0, session=3), cfg={**LSZ, "mode": m})
        check(f"LIT {m}: room $100, 60-pt stop -> skip", int(r["qty"]) == 0, r)
    # the minimum-days trade: kept (1 micro) when it fits, skipped when it does not
    r = lq(40.0, 150.0, st_of(profit=3050.0, room=2950.0, session=6, days_traded=1))
    check("LIT min-days trade after an early target: 1 micro", int(r["qty"]) == 1 and r.get("lock") == "min_days", r)
    r = lq(40.0, 150.0, st_of(profit=3050.0, room=60.0, session=6, days_traded=1))
    check("LIT min-days trade: skipped when 1 micro ($82.40) does not fit the room ($60)", int(r["qty"]) == 0, r)
    for m in ("eval", "safe_eval"):
        r = lq(40.0, 150.0, st_of(profit=3050.0, room=60.0, session=12, days_traded=1), cfg={**LSZ, "mode": m})
        check(f"LIT {m} min-days trade: skipped when 1 micro does not fit the room", int(r["qty"]) == 0, r)
    # the eval weekly loss stop as a ceiling (switch wk_loss_usd 1200): week -$1,150 -> $50 left -> skip; -$1,000 -> 2
    W = {**LSZ, "wk_loss_usd": 1200}
    r = lq(40.0, 200.0, st_of(room=1500.0, session=3, wk_pnl=-1150.0), cfg=W)
    check("LIT weekly loss stop $1,200: week -$1,150, 40-pt stop -> skip", skipped(r), r)
    r = lq(40.0, 200.0, st_of(room=1500.0, session=3, wk_pnl=-1000.0), cfg=W)
    check("LIT weekly loss stop $1,200: week -$1,000 -> 2 micros (2 x $82.40 <= $200)", int(r["qty"]) == 2, r)
    # a failed eval keeps its lock
    r = lq(30.0, 200.0, st_of(profit=-2050.0, room=-50.0, session=3))
    check("LIT failed eval (room -$50): 0, lock failed", int(r["qty"]) == 0 and r.get("lock") == "failed", r)


def live_cases():
    """The owner's live values (2026-10-25): room_f 0.8 and no eval weekly loss stop, still inside every ceiling."""
    live_checks(check)
    L = dict(LIVE)
    # 88-pt stop = $178.40 a micro: 80% of $230 = $184 -> 1; 80% of $220 = $176 -> skip
    r1 = lq(88.0, 200.0, st_of(profit=-1770.0, room=230.0, session=4), cfg=L)
    r0 = lq(88.0, 200.0, st_of(profit=-1780.0, room=220.0, session=4), cfg=L)
    check("LIVE two_week (room_f 0.8): 88-pt stop, room $230 -> 1 micro ($178.40 <= $184)", int(r1["qty"]) == 1, r1)
    check("LIVE two_week (room_f 0.8): 88-pt stop, room $220 -> skip ($178.40 > $176)", skipped(r0), r0)
    # no weekly stop: week -$1,190 still trades (the soft daily loss and the room still bound it)
    r = lq(40.0, 200.0, st_of(room=1500.0, session=3, wk_pnl=-1190.0), cfg=L)
    check("LIVE: no eval weekly loss stop: week -$1,190, 40-pt stop -> trades, inside 80% room and the $1,000 day",
          1 <= int(r["qty"]) and int(r["qty"]) * L1(40.0) <= min(0.8 * 1500.0, 1000.0), r)
    r = lq(40.0, 150.0, st_of(cum=-950.0, room=1050.0, session=2), cfg=L)
    check("LIVE two_week: day -$950 of the $1,000 soft loss, 40-pt stop -> skip", skipped(r), r)


def lit_sweep(n=6000, seed=7, base=None, label=""):
    rnd = random.Random(seed)
    bad = []
    B = LSZ if base is None else base
    plans = {"50K": (B, 1000.0, 40), "25K": (AB.sizing_cfg({**AB.normalize({"account": "x", "plan": "builder25k"},
                                                                            scfg={"strategies": {}}), "sizing": "need"}, B), 600.0, 20)}
    for _ in range(n):
        pk = rnd.choice(list(plans))
        cfg, dll, maxq = plans[pk]
        mode = rnd.choice(["two_week", "two_week", "eval", "safe_eval", "fast_eval"])
        c = {**cfg, "mode": mode}
        wl = rnd.choice([None, None, 1200.0 if pk == "50K" else 600.0])
        if wl:
            c["wk_loss_usd"] = wl
        else:
            c.pop("wk_loss_usd", None)
        risk = rnd.choice([8.0, 12.5, 20.0, 33.0, 47.0, 60.0, 75.0, 88.0, 120.0])
        room = rnd.choice([30.0, 80.0, 120.0, 180.0, 300.0, 600.0, 1200.0, 2000.0])
        cum = rnd.choice([0.0, 0.0, -200.0, -500.0, -dll + 60.0, 150.0])
        prof = rnd.choice([-1500.0, -800.0, 0.0, 900.0, 2000.0, 3050.0 if pk == "50K" else 1550.0])
        s = st_of(profit=prof, cum=cum, room=room, session=rnd.choice([1, 4, 9, 11, 14]), days_traded=rnd.choice([0, 1, 3]),
                  wk_pnl=rnd.choice([None, -900.0, -300.0, 0.0]) if wl else None)
        r = lq(risk, rnd.choice([40.0, 120.0, 250.0]), s, cfg=c, maxq=maxq)
        q = int(r["qty"])
        if q < 1:
            continue
        l = q * L1(risk)
        ok = l < room and l <= dll + cum + 1e-6 and q <= maxq
        if wl and s.get("wk_pnl") is not None:
            ok &= l <= wl + s["wk_pnl"] + 1e-6
        if not ok:
            bad.append((pk, mode, risk, room, cum, prof, q, round(l, 2)))
    check(f"LIT sweep{label} ({n} random states, 50K + 25K, every eval mode): qty x (stop + 1 tick, $1.90) inside the room, "
          "the soft daily loss and the weekly stop", not bad, bad[:4])


# ------------------------------------------------------------------------------------------------ ATLAS on LIT's account
def atlas_cases():
    E = {**LSZ}
    r = sz.second_qty(260.0, 500.0, {"mode": "normal"})
    check("ATLAS $500: 260-pt stop ($522.40 a micro) -> skip (was 1)", r["qty"] == 0 and r.get("cap") == "skip", r)
    r = sz.second_qty(240.0, 500.0, {"mode": "normal"})
    check("ATLAS $500: 240-pt stop ($482.40) -> 1", r["qty"] == 1, r)
    r = sz.second_qty(60.0, 500.0, E, state=st_of(profit=-1850.0, room=150.0, session=3))
    check("ATLAS eval: room $150, 60-pt stop (60% = $90 < $122.40) -> skip", r["qty"] == 0, r)
    r = sz.second_qty(20.0, 500.0, E, state=st_of(cum=-950.0, room=1050.0, session=3))
    check("ATLAS eval: day -$950, 20-pt stop ($42.40 a micro) -> 1", r["qty"] == 1, r)
    r = sz.second_qty(30.0, 500.0, E, state=st_of(cum=-950.0, room=1050.0, session=3))
    check("ATLAS eval: day -$950, 30-pt stop ($62.40) -> skip", r["qty"] == 0, r)
    r = sz.second_qty(20.0, 500.0, {**E, "wk_loss_usd": 1200}, state=st_of(room=1500.0, session=3, wk_pnl=-1180.0))
    check("ATLAS eval weekly loss $1,200: week -$1,180, 20-pt stop -> skip", r["qty"] == 0, r)
    rnd = random.Random(3)
    bad = []
    for _ in range(4000):
        risk = rnd.choice([5.0, 9.0, 15.0, 25.0, 40.0, 60.0, 90.0, 140.0, 255.0])
        room = rnd.choice([40.0, 100.0, 200.0, 500.0, 1500.0, 2000.0])
        cum = rnd.choice([0.0, -300.0, -900.0, -980.0, 200.0])
        usd = rnd.choice([150.0, 300.0, 500.0])
        r = sz.second_qty(risk, usd, E, state=st_of(profit=rnd.choice([-1500.0, 0.0, 1200.0]), cum=cum, room=room, session=3))
        q = r["qty"]
        if q and not (q * L1(risk) <= 0.6 * room + 1e-6 and q * L1(risk) <= 1000.0 + cum + 1e-6 and L1(risk) <= usd):
            bad.append((risk, room, cum, usd, q))
    check("ATLAS sweep (4000 states): qty x loss inside 60% room, the soft daily loss; 1 micro inside the $ risk", not bad, bad[:4])


# ------------------------------------------------------------------------------------------------ account B 25K / 50K
def acctb_cases():
    specs = {}
    for plan in ("builder25k", "builder50k"):
        for sizing in ("need", "safe"):
            sp = AB.normalize({"account": "SimB", "plan": plan, "eval_start": "2026-10-19", "sizing": sizing}, scfg={"strategies": {}})
            specs[(plan, sizing)] = sp
    S = specs[("builder25k", "need")]
    r = AB.qty(S, {"risk_pts": 50.0, "tgt_pts": 200.0}, st_of(profit=-880.0, room=120.0, session=3), base=LSZ)
    check("account B 25K need: room $120, 50-pt stop -> skip", r["qty"] == 0, r)
    r = AB.qty(S, {"risk_pts": 40.0, "tgt_pts": 200.0}, st_of(cum=-550.0, room=900.0, session=2), base=LSZ)
    check("account B 25K need: day -$550 of $600, 40-pt stop -> skip", r["qty"] == 0, r)
    r = AB.qty(S, {"risk_pts": 20.0, "tgt_pts": 200.0}, st_of(), base=LSZ)
    check("account B 25K need fresh: 20-pt stop -> a normal size inside the caps", 1 <= r["qty"] <= 20 and r["qty"] * L1(20.0) <= 500.0, r)
    S = specs[("builder25k", "safe")]
    r = AB.qty(S, {"risk_pts": 80.0, "tgt_pts": 200.0}, st_of(), base=LSZ)
    check("account B 25K safe $150: 80-pt stop ($162.40 a micro) -> skip (was 1)", r["qty"] == 0, r)
    r = AB.qty(S, {"risk_pts": 70.0, "tgt_pts": 200.0}, st_of(), base=LSZ)
    check("account B 25K safe $150: 70-pt stop ($142.40) -> 1", r["qty"] == 1, r)
    S = specs[("builder50k", "safe")]
    r = AB.qty(S, {"risk_pts": 150.0, "tgt_pts": 300.0}, st_of(), base=LSZ)
    check("account B 50K safe $300: 150-pt stop ($302.40) -> skip", r["qty"] == 0, r)
    S = specs[("builder50k", "need")]
    r = AB.qty(S, {"risk_pts": 88.0, "tgt_pts": 200.0}, st_of(profit=-1750.0, room=250.0, session=3), base=LSZ)
    check("account B 50K need: room $250, 88-pt stop (60% = $150 < $178.40) -> skip", r["qty"] == 0, r)
    rnd = random.Random(11)
    bad = []
    for _ in range(4000):
        (plan, sizing), sp = rnd.choice(list(specs.items()))
        dll = float(sp["rules"]["dll"])
        risk = rnd.choice([6.0, 12.0, 20.0, 35.0, 50.0, 70.0, 88.0, 110.0])
        room = rnd.choice([40.0, 90.0, 150.0, 300.0, 700.0, 1000.0, 2000.0])
        cum = rnd.choice([0.0, -200.0, -dll + 40.0, 100.0])
        s = st_of(profit=rnd.choice([-900.0, 0.0, 600.0]), cum=cum, room=room, session=rnd.choice([1, 5, 11, 13]))
        r = AB.qty(sp, {"risk_pts": risk, "tgt_pts": rnd.choice([60.0, 200.0])}, s, base=LSZ)
        q = r["qty"]
        if q and not (q * L1(risk) < room and q * L1(risk) <= dll + cum + 1e-6 and q <= int(sp["rules"]["max_micros"])):
            bad.append((plan, sizing, risk, room, cum, q))
    check("account B sweep (4000 states, 25K + 50K, need + safe): qty x loss inside the room and the plan's soft daily loss",
          not bad, bad[:4])


# ------------------------------------------------------------------------------------------------ extra account (qty_for)
class _Router:
    def base_sizing(self):
        return dict(LSZ)

    def log(self, *a):
        pass


def extra_cases():
    for preset, dll in (("mffu_builder_25k", 600.0), ("mffu_builder_50k", 1000.0)):
        sp = MA.normalize({"id": "t", "name": "SimX", "preset": preset, "mode": "safe_eval", "adapter": "paper",
                           "eval_start": "2026-10-19"})
        a = MA.Account(sp, _Router())
        day = "2026-10-21"
        now = 1792591200          # 2026-10-21 ~10:00 ET
        a.closes = [("2026-10-20", now - 86400, -float(sp["rules"]["mll"]) + 70.0, now - 90000)]   # room ~$70 left
        ent = {"qty": 10, "risk_pts": 40.0, "tgt_pts": 150.0, "entry_t": now, "dir": 1}
        q = a.qty_for(ent, now)
        check(f"extra account {preset} safe_eval: room ~$70, 40-pt stop -> skip (was 1)", q == 0, a.last_size)
        a.closes = [(day, now - 600, -dll + 50.0, now - 900)]       # today almost at the soft daily loss
        q = a.qty_for({**ent, "risk_pts": 30.0}, now)
        check(f"extra account {preset}: day {-dll + 50:,.0f}, 30-pt stop -> skip", q == 0, a.last_size)
        a.closes = []
        q = a.qty_for(ent, now)
        check(f"extra account {preset}: fresh, 40-pt stop -> traded inside the caps", q >= 1 and q * L1(40.0) <= dll, a.last_size)


def stuck_cases():
    from engine import eval_life as EL
    v = EL.view({"0000-00-00": -100.0, "2026-10-19": -1750.0}, "2026-10-19", "2026-10-21", LSZ)
    check("eval_life: room $150 (< $200) -> stuck, push 'EVAL STUCK'", v["stuck"] and v["status"] == "open"
          and any("STUCK" in p["title"] for p in EL.notices(v, "Sim", 1792591200)), v.get("trading"))
    v = EL.view({"0000-00-00": -100.0, "2026-10-19": -500.0}, "2026-10-19", "2026-10-21", LSZ)
    check("eval_life: room $1,400 -> not stuck, no push", not v["stuck"] and not EL.notices(v, "Sim", 1792591200), v.get("trading"))


def main():
    lit_cases()
    stuck_cases()
    lit_sweep()
    live_cases()
    lit_sweep(base=LIVE, label=" on the LIVE config (room_f 0.8, weekly stop off unless drawn)")
    atlas_cases()
    acctb_cases()
    extra_cases()
    print(f"sizing caps: {sum(RESULTS)}/{len(RESULTS)} passed")
    return all(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
