"""ONE account, several NQ bots (tools/money/combo_account.py -> research/lab/combo_account.json, write-up
research/writeups/one-account-combo-2026-11-19.md; night-combo 2026-11-19). Offline, ~10 s:
  a. the plans = the owner's CLUB prices and research/lit/mffu_rules.json / engine/rapid.PLANS numbers
  b. one net position: first-in skips any later signal while a trade is open; "adds" takes a same-side signal up to the
     plan's max micros together and still skips the opposite side; the shared room shrinks by the open trade's stop-out
  c. the eval pass rule: Rapid EOD 30% best day + 4 days; Builder one big day passes; an intraday floor touch fails
  d. funded payouts: Builder buffer / ask line / 2 days / 50% best day; Rapid daily above buffer + keep, >= since-rule
  e. the Monte Carlo draws whole days inside the period (each day keeps its trades), the same paths for every row
  f. parity: the Book == tools/account4_sim.Ev, tools/uprisk.Funded, tools/money/rapid_levers.Rapid on the same paths
  g. the trade table (every bot, futures bars, flat before 16:10) and, when present, the study file + its verdict shape
  h. FINAL rules (night-comboplus, research/lab/combo_final_design_2026-11-19.md): Zlarior priority closes ATLAS at its own
     last bar close at / before Zlarior's minute (-1 tick, worst so far), first-in skips Zlarior; ATLAS's share of its
     size; the eval room guard and day stop; MFFU's live move (no new eval while live, 15 sessions after a live breach,
     "stop" ends the slot); week blocks; the ATLAS path file; when present combo_final.json + combo_50k.json shape
    python -X utf8 -m tests.test_combo_account
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    if p not in sys.path:
        sys.path.insert(0, p)
import combo_account as C  # noqa: E402

RES = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


def part_a():
    M = json.load(open(os.path.join(ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8"))
    check("a. owner's CLUB prices: Builder 50K $91.80, 25K $63, Rapid EOD 25K $97.20, Rapid EOD 50K $165",
          [C.PLANS[a]["price"] for a in C.ACCTS] == [91.80, 63.00, 97.20, 165.00])
    for a, key in (("b50", "builder_50k"), ("b25", "builder_25k")):
        L, P = M["limits"][key], C.plan(a)
        E, F = P["E"], P["F"]
        same = (E["tgt"], E["mll"], E["dll"], E["maxq"], F["buffer"], F["pay_min"], F["pay_max"], F["split"], F["cons"],
                F["cycle_days"], F["max_payouts"]) == (L["target"], L["mll"], L["dll"], L["max_micros"], L["buffer"], L["pay_min"],
                                                      L["pay_max"], L["split"], L["cons"], L["cycle_days"], L["max_payouts"])
        check(f"a. {a}: eval + funded rules = mffu_rules.json limits", same, (E, F, L))
    from engine import rapid as RP
    r = RP.PLANS["mffu_rapid_eod_25k"]
    P = C.plan("r25")
    check("a. Rapid EOD 25K = engine/rapid.PLANS (target, buffer, keep, since) + 30% best day, 4 days, 20 micros, the bot's $500 day",
          (P["E"]["tgt"], P["F"]["buffer"], P["F"]["keep"], P["F"]["since"], P["E"]["cons"], P["E"]["min_days"], P["E"]["maxq"],
           P["E"]["dll"]) == (r["target"], r["buffer"], r["cushion"], r["since"], 0.3, 4, 20, 500.0), P["E"])
    check("a. Rapid EOD 50K reference: $3,000 / $2,000 / 30 micros / keep $1,000 / since $500",
          (C.plan("r50")["E"]["tgt"], C.plan("r50")["E"]["mll"], C.plan("r50")["E"]["maxq"], C.plan("r50")["F"]["keep"],
           C.plan("r50")["F"]["since"]) == (3000.0, 2000.0, 30, 1000.0, 500.0))


def _t(s, et, xt, d, pts=10.0, risk=20.0, w1=-5.0, tgt=40.0):
    return {"s": s, "et": et, "xt": xt, "d": d, "pts": pts, "risk": risk, "w1": w1, "tgt": tgt, "lb": 1.0,
            "sz": {"risk_pts": risk, "tgt_pts": tgt, "size_mult": 1.0}, "sze": {"risk_pts": risk, "tgt_pts": tgt, "size_mult": 1.0}}


def _fixed(book, q):
    seen = []

    def size(t, room, cum, st):
        seen.append(room)
        return q
    book.size = size
    return seen


def part_b():
    day = [_t("Z", 100, 200, 1), _t("A", 150, 250, -1), _t("A", 160, 260, 1), _t("B", 300, 400, -1)]
    b = C.Eval(C.R("b25", "Z+A+B"), "Z+A+B")
    _fixed(b, 3)
    keep = []
    b.step(day, keep)
    check("b. first-in: the trade open keeps the account, later signals (either side) skipped, flat again -> next taken",
          [t["s"] + str(t["d"]) for t, _, _ in keep] == ["Z1", "B-1"], keep)
    b = C.Eval(C.R("b25", "Z+A+B", rule="adds"), "Z+A+B")
    rooms = _fixed(b, 15)
    keep = []
    b.step(day, keep)
    got = [(t["s"] + str(t["d"]), q) for t, q, _ in keep]
    check("b. adds: the opposite signal still skipped, the same-side one added and capped at 20 micros together",
          got == [("Z1", 15), ("A1", 5), ("B-1", 15)], got)
    loss = (20.0 + C.SLIP) * C.PV * 15 + C.COMM * 15
    check("b. adds: the second trade is sized from the room left after the open trade's full stop-out",
          abs((rooms[0] - rooms[1]) - loss) < 0.02, rooms)
    b = C.Eval(C.R("b25", "Z+A"), "Z+A")
    _fixed(b, 20)
    r, cum = b.step([_t("Z", 100, 200, 1, pts=-30.0, w1=-30.0)])
    check("b. a -$1,238 trade on a fresh 25K is cut at the $600 soft day (not a fail)", r is None and abs(cum + 610.0) < 0.01, (r, cum))
    b = C.Eval(C.R("b25", "Z+A"), "Z+A")
    _fixed(b, 20)
    b.bal = -500.0
    r, _ = b.step([_t("Z", 100, 200, 1, pts=-30.0, w1=-30.0)])
    check("b. with $500 of room left the same trade's open loss touches the trailing floor: the eval fails", r == "fail", r)


def part_c():
    e = C.Eval(C.R("r25", "Z"), "Z")
    e.cons = None                       # the size guard off: test the pass rule itself
    _fixed(e, 10)
    res = [e.step([_t("Z", 100, 200, 1, pts=x / 20.0, w1=0.0)])[0] for x in (500 + 19, 400 + 19, 300 + 19, 300 + 19)]
    check("c. Rapid EOD: $1,500 reached on day 4 with the best day $500 > 30% x $1,500 -> NOT passed", res[-1] is None, res)
    r2, _ = e.step([_t("Z", 100, 200, 1, pts=(200 + 19) / 20.0, w1=0.0)])
    check("c. ... it passes the day the profit grows so the best day is <= 30% of it ($500 <= 30% x $1,700)",
          r2 == "pass" and abs(e.bal - 1700.0) < 0.01, (r2, e.bal))
    e = C.Eval(C.R("b25", "Z"), "Z")
    _fixed(e, 10)
    r, _ = e.step([_t("Z", 100, 200, 1, pts=(1500 + 19) / 20.0, w1=0.0)])
    check("c. Builder 25K: no best-day rule and 1 day: one $1,500 day passes", r == "pass", r)


def part_d():
    f = C.Funded(C.R("b25", "Z"), "Z")
    _fixed(f, 1)
    evs = [f.step([_t("Z", 100, 200, 1, pts=(x + 1.9) / 2.0, w1=0.0)]) for x in (600, 600, 600, 600)]
    check("d. Builder 25K funded: nothing while under buffer $1,100 + the $750 ask line; then the $1,000 max, 80% to you",
          [e for e, _ in evs] == [None, None, None, "paid"] and abs(evs[3][1] - 0.8 * 1000.0) < 0.01, evs)
    check("d. ... after the first payout the floor locks at +$100", max(f.floor, f.lock) == 100.0 and f.pays)
    f = C.Funded(C.R("r25", "Z"), "Z")
    _fixed(f, 1)
    evs = [f.step([_t("Z", 100, 200, 1, pts=(x + 1.9) / 2.0, w1=0.0)]) for x in (1000, 1200)]
    check("d. Rapid EOD 25K funded: pays all above buffer $1,100 + keep $500 once that is >= $500, 90% to you",
          evs[0][0] is None and evs[1][0] == "paid" and abs(evs[1][1] - 0.9 * (2200 - 1600)) < 0.01, evs)


def part_e():
    a, z = C.span_ix("H2")
    P1, P2 = C.day_paths("H2", 50, seed=7), C.day_paths("H2", 50, seed=7)
    check("e. paths: whole days inside the period, the same paths for every row (seeded)",
          P1.shape == (50, C.LEN) and P1.min() >= a and P1.max() < z and (P1 == P2).all())
    T = C.trades()
    D = C.combo_days("Z+A+B")
    i = next(k for k in range(a, z) if len(D[k]) >= 3)
    check("e. a drawn day keeps all its bots' trades together, in entry order",
          D[i] == sorted([t for t in T[i] if t["s"] in "ZAB"], key=lambda t: (t["et"], C.PRIO[t["s"]])))


def part_f():
    r = C.check(n=40, log=lambda *_: None)
    check("f. parity with account4_sim.Ev / uprisk.Funded / rapid_levers.Rapid / account_b on the same paths: 0 differences",
          not any(r.values()), r)


def part_g():
    d = json.load(open(C.TRADES, encoding="utf-8"))
    cnt = d["count"]
    check("g. trade table: Zlarior 631, ATLAS, BLITZ, post-close all present", cnt.get("Z") == 631 and all(cnt.get(s, 0) > 200 for s in "ABP"),
          cnt)
    import datetime as dt
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    cols = d["cols"]
    late = 0
    for row in d["rows"]:
        r = dict(zip(cols, row))
        x = dt.datetime.fromtimestamp(r["xt"], ET)
        m = x.hour * 60 + x.minute
        late += 970 < m < 1080
    check("g. every trade is flat before 16:10 ET (MFFU)", late == 0, late)
    if not os.path.exists(C.OUT):
        print("SKIP g. no study file yet")
        return
    o = json.load(open(C.OUT, encoding="utf-8"))
    rows = o["rows"]
    check("g. study: every row has the 3 periods with slot, eval and funded numbers",
          all(all(sp in r and "eval" in r[sp]["slot"] and "pay30" in r[sp]["funded"] for sp in C.SPANS) for r in rows.values()))
    check("g. study: the row count is stated (rows x periods) and matches", o["compared"]["cells"] == len(rows) * 3
          and o["compared"]["rows"] == len(rows))
    check("g. study: today's setup rows exist for every account", all(k in rows for v in o["current"].values() for k in v))
    check("g. study: 2,000 paths", o["n"] >= 2000, o["n"])
    W = os.path.join(ROOT, "research", "writeups", "one-account-combo-2026-11-19.md")
    check("g. the write-up exists and says how many rows were compared", os.path.exists(W)
          and str(o["compared"]["rows"]) in open(W, encoding="utf-8").read())


def _with_path(t, pt, po, pw):
    """register a synthetic ATLAS path for t in combo_account's path table (the real table loaded first)."""
    P = C.atlas_paths()
    t = {**t, "day": "2099-01-01", "src": "EMA"}
    P[(t["day"], int(t["et"]), int(t["d"]), t["src"])] = (pt, po, pw)
    return t


def part_h():
    a_ = _with_path(_t("A", 100, 1000, 1, pts=20.0, w1=-5.0), [400, 700], [3.0, -2.0], [-1.0, -4.0])
    z_opp, z_same = _t("Z", 750, 900, -1, pts=8.0, w1=-2.0), _t("Z", 750, 900, 1, pts=8.0, w1=-2.0)
    a_["day"] = z_opp["day"] = z_same["day"] = "2099-01-01"

    def run(conflict, z):
        b = C.Eval({**C.R("b50", "Z+A"), "conflict": conflict}, "Z+A")
        _fixed(b, 3)
        keep = []
        b.step([a_, z], keep)
        return [(t["s"], t["pts"], t["w1"], t["xt"]) for t, _, _ in keep]
    got = run("zprio", z_opp)
    check("h. zprio: Zlarior the other way closes ATLAS at its last bar close <= that minute - 1 tick (worst so far), then trades",
          got == [("A", -2.25, -4.0, 750), ("Z", 8.0, -2.0, 900)], got)
    got = run("zprio", z_same)
    check("h. zprio: a same-side Zlarior signal is skipped (ATLAS keeps the account)", [g[0] for g in got] == ["A"] and got[0][1] == 20.0, got)
    got = run("zfull", z_same)
    check("h. zfull: any Zlarior entry closes ATLAS", [g[0] for g in got] == ["A", "Z"] and got[0][1] == -2.25, got)
    got = run("first", z_opp)
    check("h. first-in: Zlarior skipped, ATLAS's full trade", got == [("A", 20.0, -5.0, 1000)], got)
    a0 = _with_path(_t("A", 100, 1000, 1, pts=20.0, w1=-5.0), [400, 700], [3.0, -2.0], [-1.0, -4.0])
    c = C.cut_trade(a0, 300)
    check("h. a close inside ATLAS's first bar = the entry price - 1 tick (no look-ahead)", c["pts"] == -0.25 and c["xt"] == 300, c)
    b = C.Eval({**C.R("b50", "Z+A"), "a_f": {"eval": 0.6, "funded": 0.4}}, "Z+A")
    _fixed(b, 10)
    keep = []
    b.step([_t("A", 100, 200, 1)], keep)
    f = C.Funded({**C.R("b50", "Z+A"), "a_f": {"eval": 0.6, "funded": 0.4}}, "Z+A")
    _fixed(f, 1)
    keep2 = []
    f.trade_day([_t("A", 100, 200, 1)], keep2)
    check("h. ATLAS share: 60% of 10 micros = 6 in the eval; 40% of 1 = still 1 once funded (never 0, never above its own)",
          [q for _, q, _ in keep] == [6] and [q for _, q, _ in keep2] == [1], (keep, keep2))
    b = C.Eval({**C.R("b50", "Z+A"), "a_room_min": 1500.0}, "Z+A")
    _fixed(b, 3)
    b.bal = -600.0
    keep = []
    b.step([_t("A", 100, 200, 1), _t("Z", 300, 400, 1)], keep)
    check("h. eval room guard: with $1,400 of room ATLAS is skipped, Zlarior still trades", [t["s"] for t, _, _ in keep] == ["Z"], keep)
    b = C.Eval({**C.R("b50", "Z+A"), "day_cap": 500.0}, "Z+A")
    _fixed(b, 10)
    keep = []
    b.step([_t("Z", 100, 200, 1, pts=-30.0, w1=-30.0), _t("A", 300, 400, 1), _t("Z", 500, 600, 1)], keep)
    check("h. eval day stop: after a -$619 closed day no new entry by either bot", len(keep) == 1, keep)
    f = C.Funded({**C.R("b50", "Z+A"), "day_cap": 500.0, "a_room_min": 1500.0}, "Z+A")
    check("h. the eval guards are off once funded", f.day_cap == 0.0 and f.a_room_min == 0.0)
    lv = C.Live(C.cell_of(C.frow("Z")), "Z")
    _fixed(lv, 1)
    ev = [lv.step([_t("Z", 100, 200, 1, pts=(x + 1.9) / 2.0, w1=0.0)]) for x in (1500, 900, 100, 400)]
    check("h. live account: nothing until the floor locks at the start; then daily, everything above the $2,000 cushion "
          "once >= $250, 80% to you, no payout limit", [e for e, _ in ev] == [None, "paid", None, "paid"]
          and abs(ev[1][1] - 320.0) < 0.01 and abs(ev[3][1] - 400.0) < 0.01 and lv.max_pays is None, ev)

    class Stub:
        def __init__(self, evs):
            self.evs, self.max_risk = list(evs), 0.0

        def step(self, ts):
            return self.evs.pop(0) if self.evs else (None, 0.0)
    for mode in ("live", "stop", "rebuy"):
        s = C.Slot(C.frow("Z", live=mode))
        s.e, s.f = None, Stub([("grad", 1600.0)])
        s.step(0, [], [])
        evals0 = s.evals
        if mode == "live":
            s.step(1, [], [])
            s.step(2, [], [])
            ok = isinstance(s.lv, C.Live) and s.evals == 1
            s.lv = Stub([("lost", 0.0)])
            s.step(3, [], [])
            for k in range(14):
                s.step(4 + k, [], [])
            ok = ok and s.evals == 1
            s.step(18, [], [])
            check("h. live move: after the 5th payout a live account (no new eval while it trades); a live breach = 15 sessions, "
                  "then a new eval", ok and s.evals == 2 and s.lives == 1, (s.evals, s.lives))
        elif mode == "stop":
            for k in range(5):
                s.step(1 + k, [], [])
            check("h. stop: the slot ends at the 5th payout (live worth $0)", s.done and s.evals == 1 and abs(s.owner - 1600.0) < 0.01)
        else:
            check("h. rebuy (the study's model): a new eval at once", evals0 == 2)
    P = C.week_paths("H2", 30, seed=5)
    W = C.week_blocks("H2")
    a, z = C.span_ix("H2")
    starts = {w[0] for w in W}
    check("h. week blocks: calendar weeks inside the period, a path starts on a week's first day and keeps weeks whole",
          P.min() >= a and P.max() < z and all(p[0] in starts for p in P) and sum(len(w) for w in W) == z - a)
    d = json.load(open(C.APATHS, encoding="utf-8"))
    nA = sum(1 for r in json.load(open(C.TRADES, encoding="utf-8"))["rows"] if r[0] == "A")
    check("h. ATLAS path file: every ATLAS row of the trade table, 0 missing, points = the stored trade's",
          len(d["paths"]) == nA and d["missing"] == 0 and d["pts_mismatch"] == 0, (len(d["paths"]), nA))
    if not os.path.exists(C.FINAL_OUT):
        print("SKIP h. no final study file yet")
        return
    o = json.load(open(C.FINAL_OUT, encoding="utf-8"))
    check("h. final: 12 pre-registered variants + Zlarior alone, every test, 2,000 paths, 200 H2 histories",
          len(o["variants"]) == 12 and set(o["results"]) == {"Z", *C.VIDS} and o["n"] >= 2000 and o["n_hist"] >= 200
          and all(set(o["results"][v]) >= {"day", "week", "day_t1", "week_t1", "day_drop5", "day_stop"} for v in C.VIDS))
    pk = o["pick"]
    check("h. final: the pick follows the design rule (tier A: C1-C5, else B: C1-C4, else the base)",
          (pk["tier"] == "A" and pk["winner"] == max(pk["tier_A"], key=lambda v: pk["rows"][v]["h2_week_m"]))
          or (pk["tier"] == "B" and not pk["tier_A"] and pk["winner"] == max(pk["tier_B"], key=lambda v: pk["rows"][v]["h2_week_m"]))
          or (pk["tier"] == "C" and not pk["tier_B"] and pk["winner"] == "base"), pk["tier"])
    cfg = json.load(open(C.FINAL_CFG, encoding="utf-8"))
    check("h. combo_50k.json (the live build reads it): version 1, builder50k, lit + atlas, the winner's conflict / ATLAS size / guards, evidence",
          cfg.get("version") == 1 and cfg.get("account") == "builder50k" and cfg.get("bots") == ["lit", "atlas"]
          and cfg.get("variant") == pk["winner"] and cfg.get("conflict") in ("first", "zprio", "zfull")
          and isinstance(cfg.get("guards"), dict) and "atlas_size_factor" in cfg and isinstance(cfg.get("evidence"), dict)
          and cfg["evidence"].get("paper_only") is True, cfg)


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    part_f()
    part_g()
    part_h()
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
