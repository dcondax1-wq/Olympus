"""engine/shadow_eval.py + engine/buy_gate.py (big-shadow 2026-11-26): DISPLAY ONLY. Fakes only (report rows, ledgers in a temp dir).

  a. twin trades: fill_audit report rows -> trades (extra rows out, LONG / SHORT points, no stop = out, de-duplicated)
  b. shadow eval: one winner passes (MFFU Builder 50K: +$3,000, min 1 day), a pass restarts the next session
  c. shadow eval: the floor touched = fail, a fresh eval the next session; the trailing floor locks at +$100
  d. no consistency rule on the Builder: a pass whose best day is bigger than the total still passes (the rank.py edge)
  e. the soft daily loss: no entry once the day is down $1,000; a plan with cons=0.3 waits for the best day <= 30%
  f. the shadow matches the live sizer (engine/sizing.lit_qty two_week, room_f 0.4): micros of the first trade
  g. buy gate W3: STOP when the last 40 LIT trades sum < 0R; OK again only after a shadow PASS on / after the STOP day
  h. buy gate W5: STOP at $300 under the business's best (payouts to you - eval fees), OK after a shadow pass (new best)
  i. display only: tiny() None and the brief line '' with the switch off; on: OK / STOP words, < 400 bytes, never "buy" verbs
  j. record_buy writes data/eval_buys.json-style rows; pc_report carries "bg" in its ext order; heartbeat _bg() None when off
    python -X utf8 -m tests.test_buy_gate
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import buy_gate as BG  # noqa: E402
from engine import shadow_eval as SE  # noqa: E402

RES = []


def check(name, ok):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


def T(day, risk, pts, tgt=None, k=0, d=1):
    return {"day": day, "entry_t": int(SE.dt.datetime.fromisoformat(day + "T10:00").timestamp()) + k, "dir": d, "risk": risk,
            "tgt": tgt if tgt is not None else 6 * risk, "pts": pts}


def part_a():
    rows = [{"status": "matched", "day": "2026-11-02", "entry_t": 10, "side": "LONG", "bt_entry": 100.0, "bt_stop": 90.0, "bt_target": 160.0, "bt_exit": 160.0},
            {"status": "missed", "day": "2026-11-03", "entry_t": 20, "side": "SHORT", "bt_entry": 100.0, "bt_stop": 110.0, "bt_target": 40.0, "bt_exit": 110.0},
            {"status": "extra", "day": "2026-11-03", "entry_t": 30, "side": "LONG", "bt_entry": 1, "bt_stop": 0, "bt_exit": 2},
            {"status": "unknown", "day": "2026-11-04", "entry_t": 40, "side": "LONG", "bt_entry": 100.0, "bt_stop": 100.0, "bt_exit": 101.0},
            {"status": "matched", "day": "2026-11-02", "entry_t": 10, "side": "LONG", "bt_entry": 100.0, "bt_stop": 90.0, "bt_target": 160.0, "bt_exit": 160.0}]
    t = SE.twin_trades(rows=rows)
    check("a1 extra / zero-stop / duplicate rows out", len(t) == 2)
    check("a2 long +60 pts, short -10 pts, risk 10, target 60", t[0]["pts"] == 60 and t[1]["pts"] == -10 and t[0]["risk"] == 10 and t[0]["tgt"] == 60)


def part_b():
    r = SE.run([T("2026-11-02", 20.0, 120.0)], "2026-11-02", "2026-11-04")
    a = r["attempts"]
    check("b1 one 6R winner passes the shadow 50K", len(a) == 1 and a[0]["result"] == "pass" and a[0]["profit"] >= 3000)
    check("b2 a pass restarts the next session", r["cur"] and r["cur"]["start"] == "2026-11-03" and r["cur"]["sessions"] == 2)


def part_c():
    tr = [T(d, 30.0, -30.0) for d in SE.sessions("2026-11-02", "2026-11-12")]
    r = SE.run(tr, "2026-11-02", "2026-11-12")
    fails = [x for x in r["attempts"] if x["result"] == "fail"]
    check("c1 repeated stop-outs fail the shadow (floor / stuck)", len(fails) >= 1 and fails[0]["profit"] < -1500)
    check("c2 a fresh shadow starts the session after the fail", r["cur"] is not None and r["cur"]["start"] > fails[0]["end"])
    r2 = SE.run([T("2026-11-02", 20.0, 400.0, tgt=400.0)], "2026-11-02", "2026-11-02", plan={"target": 1e9, "max_micros": 4})
    c = r2["cur"]
    p = c["profit"]
    check("c3 the trailing floor follows the close and locks at +$100", p > 2100 and abs(c["room"] - (p - 100.0)) < 0.01)


def part_d():
    tr = [T("2026-11-02", 50.0, -50.0), T("2026-11-03", 25.0, 200.0)]
    r = SE.run(tr, "2026-11-02", "2026-11-04")
    a = r["attempts"]
    check("d1 a pass from a loss, best day > total: still a pass (MFFU Builder has no consistency rule)",
          a and a[0]["result"] == "pass" and a[0]["end"] == "2026-11-03")


def part_e():
    tr = [T("2026-11-02", 40.0, -40.0, k=1), T("2026-11-02", 40.0, -40.0, k=2), T("2026-11-02", 40.0, -40.0, k=3),
          T("2026-11-02", 40.0, -40.0, k=4), T("2026-11-02", 40.0, -40.0, k=5)]
    r = SE.run(tr, "2026-11-02", "2026-11-02")
    c = r["cur"] or (r["attempts"][0] if r["attempts"] else {})
    check("e1 the soft daily loss stops new entries near -$1,000", c.get("profit", 0) >= -1100 and c.get("trades", 99) < 5)
    r2 = SE.run([T("2026-11-02", 20.0, 120.0)], "2026-11-02", "2026-11-03", plan={"cons": 0.3})
    check("e2 a cons 0.3 plan does not pass on one 100% day", not any(x["result"] == "pass" for x in r2["attempts"]))


def part_f():
    from engine import sizing as SZ
    from engine.lit import qty_for
    cfg = SE.sizing_cfg(SE.PLAN_50K)
    check("f1 the shadow sizes with the live two_week rule (room_f 0.4)", cfg["mode"] == "two_week" and cfg["two_week"]["room_f"] == 0.4)
    q = SZ.lit_qty(qty_for(40.0), {"risk_pts": 40.0, "tgt_pts": 240.0, "size_mult": 1.0}, cfg, room=2000.0,
                   state={"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "days_traded": 0}, learning=None, max_micros=40)["qty"]
    r = SE.run([T("2026-11-02", 40.0, -40.0, tgt=240.0)], "2026-11-02", "2026-11-02")
    lost = -(r["cur"] or r["attempts"][0])["profit"]
    check("f2 the first trade's micros = engine/sizing.lit_qty's", q > 0 and abs(lost - q * (40.0 * 2 + 1.90)) < 0.01)


def _paths(tmp):
    return {k: os.path.join(tmp, v) for k, v in {"report_path": "report.json", "shadow_state": "shadow_state.json", "shadow_out": "shadow.json",
                                                "seed_path": "seed.json", "ledger_path": "ledger.json", "buys_path": "buys.json",
                                                "switch": "switch.json", "out_path": "gate.json"}.items()}


def _w(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def part_g():
    start, mid = "2026-11-02", "2026-11-09"
    R = [("2026-10-01", i, 0.5) for i in range(40)]
    g = BG.evaluate(R, {}, [], start, "2026-11-06")
    check("g1 last 40 trades +20R: OK", g["verdict"] == "OK" and g["w3"]["sum40"] == 20.0)
    R2 = R + [("2026-11-03", 100 + i, -1.0) for i in range(25)]
    g = BG.evaluate(R2, {}, [], start, "2026-11-06")
    check("g2 sum under 0R -> STOP (since the day it crossed)", g["verdict"] == "STOP" and g["w3"]["stop"] and g["w3"]["since"] == "2026-11-03")
    g = BG.evaluate(R2, {}, ["2026-11-02"], start, "2026-11-06")
    check("g3 a shadow pass BEFORE the STOP does not lift it", g["verdict"] == "STOP")
    g = BG.evaluate(R2, {}, [mid], start, "2026-11-10")
    check("g4 a shadow pass while LIT's sum is still under 0R: STOP stays (as the planner)", g["verdict"] == "STOP")
    R3 = R2 + [("2026-11-10", 200 + i, 1.5) for i in range(20)]
    g = BG.evaluate(R3, {}, ["2026-11-11"], start, "2026-11-12")
    check("g4b sum back above 0R, then a shadow pass -> OK again", g["verdict"] == "OK" and not g["w3"]["stop"])
    g = BG.evaluate(R3, {}, [], start, "2026-11-12")
    check("g4c sum back above 0R but no shadow pass yet -> still STOP", g["verdict"] == "STOP")
    g = BG.evaluate(R2, {}, [], start, "2026-11-06", rules=("W5",))
    check("g5 rules W5 only: W3's STOP does not count", g["verdict"] == "OK" and g["rules"] == ["W5"])


def part_h():
    start = "2026-11-02"
    R = [("2026-10-01", i, 0.5) for i in range(40)]
    biz = {"2026-11-03": 800.0, "2026-11-04": -97.20, "2026-11-05": -63.0, "2026-11-06": -91.80}
    g = BG.evaluate(R, biz, [], start, "2026-11-05")
    check("h1 $160 under the best: OK", g["verdict"] == "OK" and abs(g["w5"]["under"] - 160.2) < 0.01)
    g = BG.evaluate(R, biz, [], start, "2026-11-09")
    check("h2 $252 under the best: still OK", g["verdict"] == "OK")
    biz2 = {**biz, "2026-11-09": -97.20}
    g = BG.evaluate(R, biz2, [], start, "2026-11-10")
    check("h3 STOP at more than $300 under the best", g["verdict"] == "STOP" and g["w5"]["since"] == "2026-11-09")
    g = BG.evaluate(R, biz2, ["2026-11-10"], start, "2026-11-11")
    check("h4 a shadow pass lifts it and the best restarts from there", g["verdict"] == "OK" and g["w5"]["under"] == 0)


def part_i():
    tmp = tempfile.mkdtemp()
    try:
        P = _paths(tmp)
        _w(P["seed_path"], [{"day": "2026-10-01", "entry_t": i, "r": 0.5} for i in range(40)])
        _w(P["report_path"], {"rows": []})
        g = BG.refresh(**P)
        check("i1 switch off: computed but not shown; tiny() None", g["verdict"] == "OK" and not g["shown"] and BG.tiny(g) is None)
        _w(P["switch"], {"show": True})
        os.remove(P["report_path"])
        g = BG.refresh(**P)
        t = BG.tiny(g)
        js = json.dumps(t)
        check("i2 switch on: tiny() OK, < 400 bytes, display-only words", t and t["s"] == "OK" and len(js) < 400 and "display only" in t["l"])
        check("i2b a missing / old nightly backtest says so on the shadow line", "nightly fill audit" in t["sh"])
        _w(P["report_path"], {"rows": []})
        g2 = BG.refresh(**P)
        check("i2c a fresh nightly backtest file: no stale words", "nightly fill audit" not in g2["shadow"])
        from tools import morning_brief as MB
        check("i3 the morning brief line reads it (fresh, shown)", MB.buy_gate_line(P["out_path"]).startswith("Buy gate: OK to buy"))
        _w(P["out_path"], {**g, "shown": False})
        check("i4 the brief line is '' when the gate is not shown", MB.buy_gate_line(P["out_path"]) == "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_j():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "buys.json")
        r = BG.record_buy("Rapid EOD 25K", 97.20, "2026-11-27", path=p)
        rows = SE._read(p)["rows"]
        check("j1 record_buy writes the fee row", r["ok"] and rows[-1]["price"] == 97.2 and rows[-1]["day"] == "2026-11-27")
        b = BG.biz_by_day(os.path.join(tmp, "none.json"), p, "2026-11-01")
        check("j2 the fee counts in the business $", b == {"2026-11-27": -97.2})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    import tools.pc_report as PR
    check("j3 the PC report carries 'bg' in an ext post", "bg" in PR.EXT_ORDER)
    from engine import heartbeat as HB
    old = BG.OUT
    try:
        BG.OUT = os.path.join(tempfile.gettempdir(), "no_such_buy_gate.json")
        check("j4 heartbeat _bg() is None when nothing is shown (the payload unchanged)", HB._bg() is None)
    finally:
        BG.OUT = old
    src = open(os.path.join(ROOT, "engine", "buy_gate.py"), encoding="utf-8").read() + open(os.path.join(ROOT, "engine", "shadow_eval.py"), encoding="utf-8").read()
    bad = [w for w in ("place_order", "ninjatrader", "submit", "adapter", "requests.post") if w in src.lower()]
    check("j5 no order / broker path in the two modules", not bad)


def part_k():
    """red team #19 notes: (1) no owner $ on the PUBLIC feed; (2) payouts recorded by the old CLIs count (no false W5 STOP)."""
    tmp = tempfile.mkdtemp()
    try:
        P = _paths(tmp)
        _w(P["seed_path"], [{"day": "2026-10-01", "entry_t": i, "r": 0.5} for i in range(40)])
        _w(P["report_path"], {"rows": []})
        _w(P["switch"], {"show": True})
        st = SE.today_et()
        _w(P["shadow_state"], {"start": "2026-11-02"})
        _w(P["buys_path"], {"rows": [{"day": "2026-11-03", "plan": "Rapid EOD 25K", "price": 97.2}]})
        _w(P["ledger_path"], {"rows": [{"key": "atlas", "day": "2026-11-04", "gross": 1000.0, "to_you": 800.0, "kind": "builder"}]})
        g = BG.refresh(trackers=[], **P)
        t = BG.tiny(g)
        check("k1 public tiny(): OK/STOP + LIT R, no $ at all", t and "$" not in t["l"] and "LIT last 40 trades" in t["l"] and "payouts-minus-fees rule OK" in t["l"])
        from tools import morning_brief as MB
        check("k2 the morning brief (its lines also go to a public Board event) carries no $", "$" not in MB.buy_gate_line(P["out_path"]))
        check("k3 the private 16:15 line keeps the business $", "$" in MB.buy_gate_line(P["out_path"], key="line"))
        # (2) fees $250, then a $1,000 payout recorded ONLY through account_b's own CLI, then one more $97.20 fee:
        #     real business: -250 -> +550 (best) -> +452.80 = $97 under: OK; a ledger-only view: -$347 = $347 under its best: STOP
        _w(P["buys_path"], {"rows": [{"day": "2026-11-02", "plan": "Builder 25K", "price": 63.0}, {"day": "2026-11-02", "plan": "Rapid EOD 25K", "price": 187.0},
                                     {"day": "2026-11-05", "plan": "Rapid EOD 25K", "price": 97.2}]})
        _w(P["ledger_path"], {"rows": []})
        trk = [{"key": "atlas", "day": "2026-11-04", "to_you": 800.0}]
        old = BG.biz_by_day(P["ledger_path"], P["buys_path"], "2026-11-02", trackers=[])
        new = BG.biz_by_day(P["ledger_path"], P["buys_path"], "2026-11-02", trackers=trk)
        check("k4 a payout only in the account's own tracker is counted", abs(sum(new.values()) - sum(old.values()) - 800.0) < 0.01)
        R = [("2026-10-01", i, 0.5) for i in range(40)]
        g_old = BG.evaluate(R, old, [], "2026-11-02", "2026-11-06", rules=("W5",))
        g_new = BG.evaluate(R, new, [], "2026-11-02", "2026-11-06", rules=("W5",))
        check("k5 no false W5 STOP: ledger-only view would say STOP, with the tracker it is OK ($97 under its best)",
              g_old["verdict"] == "STOP" and g_new["verdict"] == "OK" and abs(g_new["w5"]["under"] - 97.2) < 0.01)
        _w(P["ledger_path"], {"rows": [{"key": "atlas", "day": "2026-11-04", "gross": 1000.0, "to_you": 800.0, "kind": "builder"}]})
        both = BG.biz_by_day(P["ledger_path"], P["buys_path"], "2026-11-02", trackers=trk)
        check("k6 a payout in BOTH the ledger and the tracker counts once", abs(sum(both.values()) - sum(new.values())) < 0.01)
        check("k7 tracker_payouts() never raises on this machine", isinstance(BG.tracker_payouts(), list))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_f, part_g, part_h, part_i, part_j, part_k):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
    n, ok = len(RES), sum(RES)
    print(f"\nbuy gate + shadow eval: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
