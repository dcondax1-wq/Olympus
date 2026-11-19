"""Live learning (engine/live_learning.py + engine/sizing.cost_reserve), owner order 2026-10-25.

  a. learn_costs OFF (absent / false / nothing learned) = today's exact sizing: lit_qty and second_qty, every mode, a grid
     of stops / targets / eval states
  b. learn_costs ON only makes sizing more conservative: never more micros, and the trade's $ risk at the learned cost never
     above the old size's $ risk at the assumed cost (except the 1-micro floor), every ceiling holds at the learned price
  c. the cost reserve math: p75 of the adverse slippage, ceil, clipped to 1..4 ticks, nothing learned under 5 fills, paper
     fills ignored, commission from the real balance clipped to $1.90..$4.00
  d. the journal records match the replay twin on a 2026 replay (engine/lit_live.run on data/NQ_5m.csv + NQ_1m.csv):
     identical paper fills -> every record matched, 0 ticks, $0 gap; a slipped fill, a missed and an extra trade are seen
     with the right $; the cause codes are lit_learn's; MFE / MAE from the 1m bars; the PC's fill-audit twin = the same trades
  e. the weekly summary math (gap $ / R, missed / extra, slippage), the Sunday-evening due rule and the push payload
  f. suggestions: the learning loop's shadow knobs with "would have changed $X", the approve command, nothing applied
  g. cloud_hook on a replayed state: reviews, weekly, suggestions in new_state["learning_live"], the phone block

  python -X utf8 -m tests.test_learning_live
"""
from __future__ import annotations

import copy
import itertools
import json
import os
import shutil
import tempfile

from engine import live_learning as LL
from engine import sizing as SZ

RES = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:400]})" if detail and not cond else ""))


def _cfg():
    with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
        return json.load(fh)["lit_sizing"]


def grid():
    """(cfg, trade, state, room) combinations over the modes the bot can run."""
    base = _cfg()
    modes = []
    for m in ("two_week", "eval", "safe_eval", "normal", "fast_eval", "funded"):
        c = copy.deepcopy(base)
        c["mode"] = m
        modes.append(c)
    c = copy.deepcopy(base)
    c["wk_loss_usd"] = 1200
    modes.append(c)
    states = [None, {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "days_traded": 0, "wk_pnl": 0.0},
              {"profit": 1200.0, "cum": -300.0, "room": 900.0, "session": 4, "n_today": 0, "days_traded": 3, "wk_pnl": -700.0},
              {"profit": -1500.0, "cum": 0.0, "room": 260.0, "session": 9, "n_today": 0, "days_traded": 8, "wk_pnl": -400.0},
              {"profit": 2500.0, "cum": 0.0, "room": 3000.0, "session": 12, "n_today": 0, "days_traded": 9, "wk_pnl": 100.0}]
    for c, st, risk, tgt in itertools.product(modes, states, (6.0, 12.5, 20.0, 33.25, 47.0, 80.0), (40.0, 120.0)):
        tr = {"risk_pts": risk, "tgt_pts": tgt, "size_mult": 1.0, "size_why": []}
        yield c, tr, st, (None if st is None else st["room"])


def _q0(risk):
    from engine import lit
    return max(1, int(lit.qty_for(risk)))


def test_off_identical():
    n = bad = 0
    for c, tr, st, room in grid():
        q0 = _q0(tr["risk_pts"])
        ref = SZ._lit_qty_base(q0, tr, c, room=room, state=st, learning=None)
        absent = {k: v for k, v in c.items() if k not in ("learn_costs", "learn_costs_note")}
        for variant in (absent, {**c, "learn_costs": False}, {**c, "learn_costs": True, "two_week": c.get("two_week")}):
            stv = None if st is None else {**st, "costs": {"reserve_ticks": 1, "comm": 1.90}} if variant.get("learn_costs") else st
            got = SZ.lit_qty(q0, tr, variant, room=room, state=stv, learning=None)
            n += 1
            if got["qty"] != ref["qty"] or got.get("reasons") != ref.get("reasons"):
                bad += 1
        s0 = SZ._second_qty_base(tr["risk_pts"], 500.0, c, state=st, room=room)
        s1 = SZ.second_qty(tr["risk_pts"], 500.0, {**c, "learn_costs": False}, state=st, room=room)
        s2 = SZ.second_qty(tr["risk_pts"], 500.0, c, state=st, room=room)
        n += 2
        bad += (s0 != s1) + (s0 != s2)
    check(f"a. learn_costs off / absent / nothing learned = today's exact sizing ({n} cases)", bad == 0, bad)
    # with no costs file at all, learn_costs true still means 1 tick and $1.90 = identical
    old = os.environ.get("LE_LEARN_COSTS")
    os.environ["LE_LEARN_COSTS"] = os.path.join(tempfile.gettempdir(), "no_such_costs_file.json")
    try:
        c = _cfg()
        tr = {"risk_pts": 25.0, "tgt_pts": 100.0, "size_mult": 1.0}
        st = {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "days_traded": 0}
        a = SZ.lit_qty(16, tr, c, room=2000.0, state=st, learning=None)
        b = SZ.lit_qty(16, tr, {**c, "learn_costs": True}, room=2000.0, state=st, learning=None)
        check("a. learn_costs on without a costs file = identical (1 tick, $1.90)", a == b, (a, b))
    finally:
        if old is None:
            os.environ.pop("LE_LEARN_COSTS", None)
        else:
            os.environ["LE_LEARN_COSTS"] = old


def test_on_safer():
    n = more = risk_up = ceil_bad = no_reason = 0
    for (c, tr, st, room), (rt, cm), sw in itertools.product(grid(), ((2, 1.90), (3, 2.40), (4, 4.00), (9, 9.0)), (True, "scale")):
        if st is None and sw == "scale":
            continue
        q0 = _q0(tr["risk_pts"])
        off = SZ.lit_qty(q0, tr, c, room=room, state=st, learning=None)
        stv = {**(st or {}), "costs": {"reserve_ticks": rt, "comm": cm}} if st is not None else None
        cfg_on = {**c, "learn_costs": sw} if st is not None else {**c, "learn_costs": {"reserve_ticks": rt, "comm": cm}}
        on = SZ.lit_qty(q0, tr, cfg_on, room=room, state=stv, learning=None)
        n += 1
        if on["qty"] > off["qty"]:
            more += 1
        if on["qty"] < off["qty"] and not any("learned costs" in x for x in on.get("reasons") or []):
            no_reason += 1
        rtc, cmc = min(4, rt), min(4.0, cm)
        lrn = SZ.loss_1micro(tr["risk_pts"], 0.25 * rtc, cmc)
        if sw == "scale" and on["qty"] > 1 and on["qty"] * lrn > off["qty"] * SZ.loss_1micro(tr["risk_pts"]) + 1e-6:
            risk_up += 1
        if on["qty"] and st is not None and (c.get("mode") or "normal") in SZ.EVAL_MODES:
            if not (on["qty"] * lrn < st["room"] and on["qty"] * lrn <= 1000.0 + st["cum"] + 1e-6):
                ceil_bad += 1
        s_off = SZ.second_qty(tr["risk_pts"], 500.0, c, state=st, room=room)
        s_on = SZ.second_qty(tr["risk_pts"], 500.0, cfg_on, state=stv, room=room)
        more += s_on["qty"] > s_off["qty"]
    check(f"b. learn_costs on (true / \"scale\"): never more micros than off ({n} LIT + {n} ATLAS cases)", more == 0, more)
    check("b. learn_costs on: every cut says why (\"learned costs\" in the reasons)", no_reason == 0, no_reason)
    check("b. learn_costs \"scale\": the $ risk at the learned cost never above the old size's $ risk (beyond the 1-micro floor)", risk_up == 0, risk_up)
    check("b. learn_costs on: the routed micros fit the room and the soft daily loss at the learned price", ceil_bad == 0, ceil_bad)
    c = _cfg()
    st = {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "days_traded": 0, "costs": {"reserve_ticks": 4, "comm": 3.0}}
    tr = {"risk_pts": 20.0, "tgt_pts": 60.0, "size_mult": 1.0}
    off = SZ.lit_qty(20, tr, c, room=2000.0, state={k: v for k, v in st.items() if k != "costs"}, learning=None)
    on = SZ.lit_qty(20, tr, {**c, "learn_costs": True}, room=2000.0, state=st, learning=None)
    check("b. a worse fill history cuts the size (20-pt stop, 4 ticks, $3.00: fewer micros, reason logged)",
          on["qty"] < off["qty"] and any("learned costs" in r for r in on["reasons"]) and on["costs"]["qty_before"] == off["qty"], (off["qty"], on))


def test_cost_math():
    mk = lambda e, x=None, k="STOP", src="broker": {"bot": "lit", "entry_t": 1, "fill_src": src, "exit_src": src, "qty": 2,
                                                    "entry_slip_ticks": e, "exit_slip_ticks": x, "exit_kind": k}
    S = LL.cost_stats([mk(0.0), mk(1.0), mk(0.0, 2.0)], "lit")
    check("c. under 5 observations: nothing learned (1 tick, $1.90)", not S["learned"] and S["reserve_ticks"] == 1.0 and S["comm"] == 1.90, S)
    obs = [mk(e, x) for e, x in ((0, 0), (1, 2), (2, 3), (-1, 1), (0, 4), (3, 0))]
    adv = sorted(max(0, v) for o in obs for v in (o["entry_slip_ticks"], o["exit_slip_ticks"]))
    S = LL.cost_stats(obs, "lit")
    check("c. p75 adverse slippage -> ceil -> reserve ticks", S["learned"] and S["adverse_p75"] == round(LL.pctl(adv, 75), 2)
          and S["reserve_ticks"] == min(4, max(1, -(-LL.pctl(adv, 75) // 1))), (S["adverse_p75"], S["reserve_ticks"]))
    big = [mk(9.0, 12.0) for _ in range(8)]
    check("c. reserve capped at 4 ticks", LL.cost_stats(big, "lit")["reserve_ticks"] == 4.0)
    good = [mk(-2.0, -1.0) for _ in range(8)]
    check("c. better-than-model fills never go below 1 tick", LL.cost_stats(good, "lit")["reserve_ticks"] == 1.0)
    check("c. paper fills are not learned from", LL.cost_stats([mk(5, 5, src="paper") for _ in range(9)], "lit")["fills"] == 0)
    o = [{"day": "2026-10-20", "live_pnl": 100.0, "qty": 10, "fill_src": "broker", "exit_src": "broker"}]
    C = LL.comm_from_cash({"2026-10-19": 50000.0, "2026-10-20": 50090.0}, o)
    check("c. commission from the real balance: $1.90 + ($100 - $90) / 10 = $2.90", C and C[0]["comm"] == 2.9, C)
    S = LL.cost_stats(obs, "lit", comm_obs=[{"comm": 2.9}, {"comm": 9.0}, {"comm": 3.1}])
    check("c. commission learned = median, clipped to $1.90..$4.00", S["comm"] == 3.1, S["comm"])
    S = LL.cost_stats(obs, "lit", comm_obs=[{"comm": 1.2}])
    check("c. a lower booked commission never lowers the assumption", S["comm"] == 1.90)
    rec = {"dir": -1, "entry_t": 100, "t_route": 103, "t_fill": 104, "model_entry": 100.0, "fill_entry": 99.5, "fill_src": "broker",
           "exit_kind": "STOP", "stop": 110.0, "exit_px": 110.5, "exit_src": "broker", "qty": 3, "day": "2026-10-20"}
    ob = LL.obs_of(rec)
    check("c. obs_of: a short filled 2 ticks lower = 2 ticks worse, stop filled 2 ticks above = 2 ticks worse, latency 3 / 4 s",
          ob["entry_slip_ticks"] == 2.0 and ob["exit_slip_ticks"] == 2.0 and ob["latency_route_s"] == 3 and ob["latency_fill_s"] == 4, ob)


def _replay():
    from engine import fill_audit as fa, lit_live
    d5, d1 = fa.load_bars()
    P = fa._params()
    a, end = fa._ts("2026-08-01", 2, 0), fa._ts("2026-10-16", 16, 5)
    x5, x1 = d5[(d5["time"] >= a - 30 * 86400) & (d5["time"] < end)], d1[(d1["time"] >= a - 30 * 86400) & (d1["time"] < end)]
    r = lit_live.run(x5, P, one_min=x1, now=end + 300)
    return r, x1, d5, d1, P


def test_journal(r, d1, d5f, d1f, P):
    from engine import fill_audit as fa
    from engine.lit_learn import cause_codes
    T = [t for t in r["trades"] if t.get("exit_reason") not in (None, "OPEN")]
    check("d. the 2026 replay has finished trades to review", len(T) >= 10, len(T))
    tw = [LL.twin_lit(t) for t in T]
    ledger = {}
    for t in T:                       # the cloud paper ledger at the model's prices (= the replay)
        ledger[str(int(t["entry_t"]))] = {"day": t["day"], "side": "LONG" if t["dir"] == 1 else "SHORT", "entry_px": t["entry"],
                                          "exit_px": t["exit_price"], "exit": t["exit_reason"], "stop_px": t["stop"], "target_px": t["target"],
                                          "qty": t["qty"], "usd": t["pnl"], "R": t["pnl_r"], "risk_pts": t["risk_pts"], "exit_ts": t["exit_t"]}
    live = [LL.live_lit_paper(k, v) for k, v in ledger.items()]
    R = LL.reviews("lit", live, tw, d1)
    ok = all(x["status"] == "matched" and x["diff"]["entry_ticks"] == 0 and x["diff"]["exit_ticks"] == 0 and x["diff"]["entry_s"] == 0
             and x["gap_usd"] == 0 and x["exec_usd"] == 0 and x["diff"]["same_exit"] for x in R)
    check(f"d. identical paper fills: {len(R)} records all matched, 0 ticks, $0 gap", ok and len(R) == len(T),
          [x for x in R if x["status"] != "matched" or x["gap_usd"]][:2])
    cc = all((x["cause"], x["tags"]) == cause_codes({"exit": {"TIME": "EOD", "CUT": "EOD"}.get(x["twin"]["exit_kind"], x["twin"]["exit_kind"]),
                                                     "r": x["twin"]["r"], "risk_pts": abs(x["twin"]["entry"] - x["twin"]["stop"]), "f": {}, "post": {}})
             for x in R)
    check("d. cause codes = engine/lit_learn.cause_codes (the LIT journal's codes)", cc)
    winners_no_cause = all(x["cause"] is None for x in R if x["twin"]["exit_kind"] == "TARGET")
    check("d. a target trade has no loss cause", winners_no_cause)
    mm = [x for x in R if x["mfe_r"] is not None and x["mae_r"] is not None]
    tgt_ok = all(x["mfe_r"] >= 0.99 * abs(x["twin"]["exit"] - x["twin"]["entry"]) / abs(x["twin"]["entry"] - x["twin"]["stop"]) - 0.05
                 for x in mm if x["twin"]["exit_kind"] == "TARGET")
    check("d. MFE / MAE (R) from the 1m bars on every record; a target trade's MFE reaches its exit", len(mm) == len(R) and tgt_ok,
          (len(mm), len(R)))
    # a slipped fill, a missed trade and an extra trade
    L2 = [dict(x) for x in live]
    s = L2[0]
    s["entry"] = s["entry"] + 3 * 0.25 * s["dir"]
    s["usd"] = round(s["usd"] - 3 * 0.5 * s["qty"], 2)
    miss = L2.pop(1)
    extra = {**L2[2], "entry_t": L2[2]["entry_t"] + 5 * 86400 + 3600}
    extra["day"] = LL.trading_day(extra["entry_t"])
    extra["exit_t"] = extra["entry_t"] + 1800
    R2 = LL.reviews("lit", L2 + [extra], tw, d1)
    by = {x["status"]: [y for y in R2 if y["status"] == x["status"]] for x in R2}
    sl = next(x for x in R2 if x["entry_t"] == s["entry_t"])
    ms = by.get("missed") or [{}]
    tw_miss = next(t for t in tw if t["entry_t"] == miss["entry_t"])
    check("d. a fill 3 ticks worse: entry_ticks +3, exec $ = -3 ticks x $0.50 x micros", sl["diff"]["entry_ticks"] == 3.0
          and abs(sl["exec_usd"] + 1.5 * s["qty"]) < 0.02, (sl["diff"], sl["exec_usd"]))
    check("d. a missed trade: gap = -the backtest's $", len(by.get("missed", [])) == 1 and ms[0]["entry_t"] == miss["entry_t"]
          and abs(ms[0]["gap_usd"] + tw_miss["usd"]) < 0.01, ms[0].get("gap_usd"))
    check("d. an extra trade: gap = its own $", len(by.get("extra", [])) == 1 and abs(by["extra"][0]["gap_usd"] - extra["usd"]) < 0.01)
    # the PC's twin (fill_audit.replay_day on the full bars) has the same trades on the same days
    days = sorted({t["day"] for t in T})[-4:]
    same = 0
    for dday in days:
        bt = fa.replay_day(dday, d5f, d1f, P)["trades"]
        a = sorted((int(t["entry_t"]), int(t["dir"]), round(float(t["entry"]), 2), t["exit_reason"]) for t in bt)
        b = sorted((x["entry_t"], x["dir"], round(float(x["entry"]), 2), x["exit_kind"]) for x in tw if x["day"] == dday)
        same += a == [(e, d_, p, {"EOD": "TIME"}.get(k, k)) for e, d_, p, k in b] or a == b
    check("d. the PC's fill-audit twin (replay_day) = the live loop's replay on the last 4 trade days", same == len(days), (same, days))
    return R, R2, live, tw, ledger


def test_weekly(R2):
    wk = LL.week_of(R2[0]["day"])
    W = LL.weekly_summary(R2, wk, {"lit": {"level": "good", "text": "inside (p40)"}})
    rows = [x for x in R2 if wk <= x["day"] <= W["to"]]
    b = W["bots"]["lit"]
    lu = round(sum(x["live"]["usd"] for x in rows if x.get("live")), 2)
    tu = round(sum(x["twin"]["usd"] for x in rows if x.get("twin")), 2)
    check("e. weekly: live $ / backtest $ / gap = the records' sums", b["live_usd"] == lu and b["twin_usd"] == tu and b["gap_usd"] == round(lu - tu, 2),
          (b, lu, tu))
    check("e. weekly: inside the band from the band verdict", b["inside_band"] is True and "inside" in b["text"])
    syn = [{"bot": "atlas", "day": "2026-10-19", "entry_t": 1, "status": "matched", "live": {"usd": -60.0, "r": -1.1}, "twin": {"usd": -50.0, "r": -1.0},
            "diff": {"entry_ticks": 2.0, "exit_ticks": 1.0, "same_exit": True, "entry_s": 4}, "gap_usd": -10.0, "exec_usd": -10.0, "cause": "not_turning_point"},
           {"bot": "atlas", "day": "2026-10-21", "entry_t": 2, "status": "missed", "live": None, "twin": {"usd": 300.0, "r": 2.0}, "gap_usd": -300.0, "gap_r": -2.0},
           {"bot": "atlas", "day": "2026-10-23", "entry_t": 3, "status": "extra", "live": {"usd": 120.0, "r": 0.8}, "twin": None, "gap_usd": 120.0},
           {"bot": "atlas", "day": "2026-10-26", "entry_t": 4, "status": "extra", "live": {"usd": 999.0, "r": 5.0}, "twin": None, "gap_usd": 999.0}]
    A = LL.weekly_summary(syn, "2026-10-19", {"atlas": {"level": "below", "text": "below range"}})["bots"]["atlas"]
    check("e. weekly math: 2 live / 2 backtest, live +$60 vs +$250, gap -$190 / -1.3R, 1 missed ($300), 1 extra ($120), next week left out",
          (A["trades_live"], A["trades_twin"], A["live_usd"], A["twin_usd"], A["gap_usd"], A["gap_r"], A["missed"], A["missed_usd"], A["extra"], A["extra_usd"])
          == (2, 2, 60.0, 250.0, -190.0, -1.3, 1, 300.0, 1, 120.0) and A["inside_band"] is False and A["entry_slip_ticks_med"] == 2.0, A)
    import datetime as dt
    ts = lambda s: int(dt.datetime.fromisoformat(s).replace(tzinfo=LL.ET).timestamp())
    check("e. weekly push due Sunday 17:00 ET and later, for that week's Monday", LL.weekly_due(None, ts("2026-10-25T18:00")) == "2026-10-19"
          and LL.weekly_due(None, ts("2026-10-25T12:00")) is None and LL.weekly_due("2026-10-19", ts("2026-10-25T18:00")) is None
          and LL.weekly_due(None, ts("2026-10-26T09:00")) == "2026-10-19" and LL.weekly_due(None, ts("2026-10-22T18:00")) is None)
    p = LL.weekly_payload(LL.weekly_summary(syn, "2026-10-19"), ts("2026-10-25T18:00"))
    check("e. weekly push payload: kind weekly, one key a week, opens #/learning", p.get("kind") == "weekly" and p.get("key") == "learnweek:2026-10-19"
          and p.get("url") == "#/learning", p)


def test_suggest():
    from engine import lit_learn
    L = lit_learn.load_learning()
    J = lit_learn.load_journal()
    before = open(lit_learn.LEARNING_PATH, "rb").read()
    S = LL.suggestions(L, J, {"bots": {"lit": {"learned": True, "reserve_ticks": 2.0, "comm": 1.90, "text": "x"}}}, False)
    knobs = [s for s in S if s["kind"] == "size_knob"]
    check("f. the learning loop's shadow knobs become suggestions with $ and the approve command", knobs and all(
        s["would_usd"] is not None and s["approve"] == "python -m engine.lit_learn mode apply" and s["applied"] is False for s in knobs), knobs[:1])
    one = knobs[0] if knobs else None
    if one:
        fam, b = next((f, bb) for f, bs in (L.get("knobs") or {}).items() for bb, k in bs.items() if k.get("decision") == one["id"])
        delta = lit_learn.simulate(lit_learn.merged(J), {fam: {b: L["knobs"][fam][b]}}, evals=False)["net"] - lit_learn.simulate(lit_learn.merged(J), {}, evals=False)["net"]
        check("f. 'would have changed $X' = lit_learn.simulate with the knob minus without", abs(one["would_usd"] - round(delta, 2)) < 0.01, (one["would_usd"], delta))
    check("f. a learned cost reserve with learn_costs off becomes a suggestion", any(s["kind"] == "cost_reserve" and not s["applied"] for s in S))
    check("f. suggestions apply nothing (the learning file is unchanged)", open(lit_learn.LEARNING_PATH, "rb").read() == before)


def test_cloud(r, d1, ledger):
    import datetime as dt
    from engine import lit_learn
    now = int(dt.datetime(2026, 10, 25, 18, 10, tzinfo=LL.ET).timestamp())
    first = min(int(k) for k in ledger) - 60
    st = {"first_run": first, "ledger": ledger, "second": {"first_run": first, "strategies": {"ema_lon_vix": {"ledger": {
        "1790000000": {"day": "2026-09-21", "entry_t": 1790000000, "exit_t": 1790003600, "dir": 1, "entry": 100.0, "stop": 90.0, "target": 130.0,
                       "exit": 130.0, "exit_kind": "TARGET", "r": 3.0, "qty": 2, "usd": 116.2, "risk_pts": 10.0}}}}},
          "atlas_v2": {"ledger": {"x1": {"key": "ema_lon_vix", "entry_t": 1790000000, "exit_t": 1790003600, "dir": 1, "entry": 100.0,
                                         "stop": 90.0, "target": 130.0, "exit": 130.0, "exit_kind": "TARGET", "r": 3.0, "qty": 1, "usd": 58.1,
                                         "day": "2026-09-21"}}},
          "pc": {"learn": {"costs": {"bots": {"lit": {"learned": True, "reserve_ticks": 2.0, "comm": 2.1, "text": "x"}}}}}}
    srun = {"strategies": {"ema_lon_vix": {"trades": [{"day": "2026-09-21", "entry_t": 1790000000, "exit_t": 1790003600, "dir": 1, "entry": 100.0,
                                                       "stop": 90.0, "target": 130.0, "exit": 130.0, "exit_kind": "TARGET", "r": 3.0, "qty": 2,
                                                       "usd": 116.2, "risk_pts": 10.0}]}}}
    out = LL.cloud_hook(st, {}, r, srun, d1, now, lit_journal=lit_learn.load_journal(), learning=lit_learn.load_learning(),
                        lit_sizing={"learn_costs": False})
    ll = st.get("learning_live") or {}
    bots = {x["bot"] for x in ll.get("reviews") or []}
    check("g. cloud_hook: reviews for Zlarior, ATLAS and ATLAS v2", bots >= {"lit", "atlas", "atlas_v2"} and not ll.get("errors"), (bots, ll.get("errors")))
    at = [x for x in ll["reviews"] if x["bot"] == "atlas"]
    check("g. ATLAS paper vs its second.run twin: matched, $0 gap", at and at[0]["status"] == "matched" and at[0]["gap_usd"] == 0, at[:1])
    v2 = [x for x in ll["reviews"] if x["bot"] == "atlas_v2"]
    check("g. ATLAS v2 vs the member trade it copied: same trade, its own size (qty diff noted)", v2 and v2[0]["status"] == "matched"
          and v2[0]["diff"]["qty"] == -1, v2[:1])
    check("g. Sunday 18:10 ET: the weekly summary is due -> one push notice", len(out.get("notices") or []) == 1 and ll.get("pushed_week") == "2026-10-19")
    check("g. suggestions on the state (knobs + the PC's cost reserve)", any(s["kind"] == "cost_reserve" for s in ll.get("suggest") or []))
    st2 = {**st, "learning_live": ll}
    out2 = LL.cloud_hook(st2, {"learning_live": ll}, r, srun, d1, now + 900, lit_journal=[], learning=None)
    check("g. the next run: no second weekly push, the journal is not duplicated", not out2.get("notices")
          and len(st2["learning_live"]["reviews"]) == len(ll["reviews"]))
    sb = LL.site_block(st2)
    check("g. phone block: reviews per bot, weekly, suggestions, small", sb and set(sb["reviews"]) == set(LL.BOTS) and sb["weekly"]
          and len(json.dumps(sb)) < 200_000, len(json.dumps(sb)) if sb else None)
    return sb


def test_ui(sb):
    import subprocess
    a = os.path.join(ROOT, "tools", "web_public", "learncore.js")
    b = os.path.join(ROOT, "web_next", "js", "next", "learncore.js")
    check("h. learncore.js: phone and PC copies byte-identical", open(a, "rb").read() == open(b, "rb").read())
    tmp = tempfile.mkdtemp(prefix="llui_")
    try:
        p = os.path.join(tmp, "b.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(sb, fh, default=str)
        js = ("const U=require(process.argv[1]);const B=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));"
              "const z=U.page(B,['lit']),t=U.page(B,['atlas','atlas_v2']),e=U.page(null,['lit']);"
              "console.log(JSON.stringify({z:z.length,t:t.length,sug:z.includes('The bot suggests'),wk:z.includes('Weekly reviews'),"
              "rev:t.includes('ATLAS v2'),empty:e.includes('No learning data'),ap:z.includes('Approve:')}))")
        out = subprocess.run(["node", "-e", js, a, p], capture_output=True, text=True, timeout=30)
        res = json.loads(out.stdout.strip() or "{}")
        check("h. LearnUI renders the Zlarior and ATLAS learning pages in node (suggestions with the approve command, weekly, reviews)",
              res.get("sug") and res.get("wk") and res.get("rev") and res.get("empty") and res.get("ap"), (res, out.stderr[:300]))
    except FileNotFoundError:
        check("h. node available for the render check", False, "node not found")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    clean = open(os.path.join(ROOT, "tools", "web_public", "clean.js"), encoding="utf-8").read()
    idx = open(os.path.join(ROOT, "tools", "web_public", "index.html"), encoding="utf-8").read()
    sw = open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8").read()
    routes = open(os.path.join(ROOT, "web_next", "js", "next", "routes.js"), encoding="utf-8").read()
    check("h. phone: Zlarior > Results and ATLAS > Results have a Learning chip, learning.js loads before clean.js, SW v35+",
          "'execq', 'learning']" in clean and "'atlas/results', 'atstats', 'atlearn']" in clean and idx.index("learning.js?v=1") < idx.index("clean.js?v=4")
          and int(__import__("re").search(r"le-public-v(\d+)", sw).group(1)) >= 35)
    check("h. PC: Zlarior > Results and ATLAS > Results have a Learning page", "'edge', 'learnlit']" in routes and "'atlas:results', 'atlassetups', 'learnatlas']" in routes)


def test_pc_store():
    tmp = tempfile.mkdtemp(prefix="ll_")
    try:
        fa_store = os.path.join(tmp, "fa")
        os.makedirs(fa_store)
        rows = []
        for i in range(8):
            et_ = 1790926440 + i * 86400
            rows.append({"t": et_ + 3, "side": "buy", "qty": 2, "stop": 100.0, "target": 140.0, "entry": 110.0, "entry_t": et_,
                         "adapter": "ninjatrader", "result": {"ok": True, "adapter": "ninjatrader", "legs": [{"filled": 2, "fill_px": 110.0 + 0.25 * (i % 4), "ok": True}]}})
        rows.append({"t": 1790926440 + 9 * 86400 + 3, "side": "sell", "qty": 1, "stop": 120.0, "target": 90.0, "entry": 110.0,
                     "entry_t": 1790926440 + 9 * 86400, "src": "ema_lon_vix", "adapter": "ninjatrader",
                     "result": {"ok": True, "adapter": "ninjatrader", "legs": [{"filled": 1, "fill_px": 109.0, "ok": True}]}})
        with open(os.path.join(fa_store, "ledger.jsonl"), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        C = LL.pc_update(store=os.path.join(tmp, "learn"), fa_store=fa_store, now=1791926440)
        lit, at = C["bots"]["lit"], C["bots"]["atlas"]
        check("c. PC store: Zlarior learns from its 8 fills (p75 of 0/1/2/3 ticks -> 3 ticks), ATLAS from its own fill",
              lit["fills"] == 8 and lit["learned"] and lit["reserve_ticks"] == 3.0 and at["fills"] == 1 and not at["learned"]
              and at["entry_slip_ticks_med"] == 4.0, (lit, at))
        got = LL.load_costs("lit", os.path.join(tmp, "learn", "costs.json"))
        check("c. costs.json written and read back by sizing's loader", got and got["reserve_ticks"] == 3.0)
        hb = LL.heartbeat_block(os.path.join(tmp, "learn"))
        check("c. heartbeat 'learn' block carries the costs (small)", hb and hb["costs"]["bots"]["lit"]["reserve_ticks"] == 3.0 and len(json.dumps(hb)) < 20000)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> bool:
    test_off_identical()
    test_on_safer()
    test_cost_math()
    test_pc_store()
    r, d1, d5f, d1f, P = _replay()
    R, R2, live, tw, ledger = test_journal(r, d1, d5f, d1f, P)
    test_weekly(R2)
    test_suggest()
    sb = test_cloud(r, d1, ledger)
    test_ui(sb)
    n = sum(RES)
    print(f"learning live: {n}/{len(RES)} passed")
    return n == len(RES)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
