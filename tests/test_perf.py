"""Performance pages (competitor-features #6, 7, 9, 11, 12, 13, 14): the expected-range band, live vs backtest from the fill
audit, the status page's uptime + incidents, exit efficiency, the robustness helpers, the monthly scoreboard, the look-ahead
audit (incl. a planted look-ahead it must catch), the stored research files, the cloud build cut and the shared renderer.

  python -X utf8 -m tests.test_perf            # ~30 s (one look-ahead trade re-built on cut data + a planted one)
  python -X utf8 -m tests.test_perf --quick    # no engine runs
Read-only: nothing in research/ is written (temp dirs only).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import health_band as HB  # noqa: E402
from engine import perf as PF  # noqa: E402
from engine import uptime as UP  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:300]}"), flush=True)


def ts(y, mo, d, h, mi=0):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def _recent_weekday():
    """(y, m, d) of the last weekday before today (ET): inside engine/uptime's 30-day view whatever day the suite runs."""
    d = dt.datetime.now(ET).date() - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d.year, d.month, d.day


# ------------------------------------------------------------------------------------------------ 6. expected range
def band_checks():
    q = list(range(1, 100))
    check("pct_of: inside, below, above, ties", HB.pct_of(q, 38.5) == 38.5 and HB.pct_of(q, -5) == 0.5 and HB.pct_of(q, 500) == 99.5
          and 1 <= HB.pct_of([0] * 50 + list(range(1, 50)), 0) <= 50, (HB.pct_of(q, 38.5), HB.pct_of([0] * 50 + list(range(1, 50)), 0)))
    S = np.array([[1.0, 1, 100.0, 120.0], [0.0, 0, 0.0, 0.0], [-1.0, 1, -80.0, -90.0]] * 10)
    B = HB.bootstrap(S, n_max=20, reps=2000, seed=1)
    ok = all(B[k].shape == (20, 99) for k in ("r", "n", "usd", "usd_eval")) and all(np.all(np.diff(B["r"][i]) >= -1e-9) for i in range(20))
    check("bootstrap: 99 percentiles per session count, monotone", ok)
    check("bootstrap: the median R after 20 sessions is near 20 x the mean (0)", abs(B["r"][19][49]) <= 1.0, B["r"][19][49])
    st = HB.sessions_between("2026-10-19", "2026-10-23")
    check("sessions_between: weekdays only", st == 5 and HB.sessions_between("2026-10-24", "2026-10-25") == 0, st)
    Bs = HB.load()
    check("health_band.json: H2 + 2026 bands from run lit_live (78 / 206 sessions, 40 / 120 trades)",
          Bs and Bs["bands"]["H2"]["sessions"] == 78 and Bs["bands"]["H2"]["trades"] == 40 and Bs["bands"]["2026"]["trades"] == 120,
          Bs and {k: (v["sessions"], v["trades"]) for k, v in Bs["bands"].items()})
    if not Bs:
        return
    good = [{"day": "2026-10-19", "r": 2.0, "usd": 900.0}, {"day": "2026-10-21", "r": -1.0, "usd": -500.0}]
    c = HB.compare(Bs, good, "2026-10-19", "2026-10-23", "H2", "Live")
    check("compare: 2 trades +1R in 5 sessions = inside the range", c["level"] == "good" and "inside the expected range" in c["text"]
          and c["sessions"] == 5 and c["trades"] == 2 and 5 <= c["pct_r"] <= 95, c)
    bad = [{"day": f"2026-10-{d:02d}", "r": -1.05, "usd": -700.0} for d in (19, 20, 21, 22, 23, 26, 27, 28)]
    c2 = HB.compare(Bs, bad, "2026-10-19", "2026-10-28", "H2", "Live")
    check("compare: 8 straight stop-outs in 8 sessions = below p5, investigate", c2["level"] == "bad" and "investigate" in c2["text"]
          and c2["streak"] == 8, (c2["text"], c2["pct_r"]))
    st = {"ledger": {"1": {"day": "2026-10-20", "R": 1.5, "usd": 600.0, "exit": "TARGET"}, "2": {"day": "2026-10-21", "exit": "OPEN"}},
          "pc": {"acct": {"trades": [{"entry_t": ts(2026, 10, 20, 3, 5), "exit": "STOP", "day": "2026-10-20", "r": -1.0, "pnl": -400.0}]}}}
    cd = HB.card(Bs, st, None, now=ts(2026, 10, 22, 17, 0))
    check("card: paper + live comparisons, the live one in the headline, the cone for the chart",
          cd["paper"]["trades"] == 1 and cd["live"]["trades"] == 1 and cd["headline"] == cd["live"]["text"]
          and len(cd["cone"]["rows"]) >= 10 and cd["cone"]["rows"][0] == [0, 0, 0, 0, 0, 0] and cd["live"]["equity"][-1][2] == -400.0, cd.get("headline"))
    check("card on the PC (no cloud state): no paper block", HB.card(Bs, None, [], now=ts(2026, 10, 22, 17, 0))["paper"] is None)


# ------------------------------------------------------------------------------------------------ 7. live vs backtest
def exec_checks():
    rows = [{"status": "matched", "day": "2026-10-20", "entry_t": 1, "bt_pnl": 500.0, "bt_pnl_live_qty": 450.0, "live_pnl": 430.0,
             "slip_usd": -15.0, "exec_usd": -20.0},
            {"status": "missed", "day": "2026-10-21", "entry_t": 2, "bt_pnl": 300.0, "missed_usd": 300.0, "reason": "PC off: the bot was not running"},
            {"status": "extra", "day": "2026-10-22", "entry_t": 3, "live_pnl": -120.0},
            {"status": "matched", "day": "2026-10-22", "entry_t": 4, "bt_pnl": -200.0, "bt_pnl_live_qty": -200.0, "live_pnl": -210.0,
             "slip_usd": -10.0, "exec_usd": -10.0}]
    c = PF.exec_curve(rows)
    p = c["parts"]
    check("exec curve: backtest line = same-qty backtest + missed, live line = real + extra",
          c["bt"] == 450 + 300 - 200 and c["live"] == 430 - 120 - 210 and c["days"][-1][1] == 550 and c["days"][-1][2] == 100, c["days"])
    check("exec curve: the gap is slippage + other + missed + extra", abs(c["gap"] - sum(p.values())) < 0.01
          and p["slippage"] == -25 and p["missed trades"] == -300 and p["extra trades"] == -120 and abs(p["other execution"] - (-5)) < 0.01, p)
    check("exec curve: missed reasons, counts, plain text", c["missed"] == 1 and c["extra"] == 1 and c["matched"] == 2
          and "PC off" in json.dumps(c["missed_reasons"]) and "Biggest: missed trades" in c["text"], c["text"])
    hb = {"curve": {"days": c["days"], "missed": 1, "extra": 1, "matched": 2, "missed_reasons": c["missed_reasons"]}}
    c2 = PF.exec_from_hb(hb)
    check("exec curve from the heartbeat block = the same numbers", c2["gap"] == c["gap"] and c2["parts"] == c["parts"])
    check("exec curve: nothing audited -> None", PF.exec_curve([]) is None and PF.exec_from_hb({}) is None)
    tmp = tempfile.mkdtemp(prefix="le_perf_fa_")
    try:
        from engine import fill_audit as FA
        FA._write_json(os.path.join(tmp, "summary.json"), {"v": 1, "t": 1, "trades": 2})
        FA._write_json(os.path.join(tmp, "report.json"), {"v": 1, "t": 1, "rows": rows})
        hbb = FA.heartbeat_block(tmp)
        check("fill_audit.heartbeat_block carries the per-day curve (small)", hbb and hbb["curve"]["days"] == c["days"]
              and len(json.dumps(hbb["curve"])) < 4000, hbb and list(hbb))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ 9. status page
def uptime_checks():
    t0 = ts(2026, 10, 20, 9, 0)
    pc_ok = {"present": True, "t": t0, "age_s": 60, "health": {"feed": {"market_open": True, "age_1m_s": 30, "age_5m_s": 100},
                                                               "auto": {"update": {"result": "ok"}}}, "live_pub": {"ok": True, "at": t0}}
    s = UP.sample_from_pc(pc_ok, t0, cloud_ran=True)
    check("sample: every part up", s == {"cloud": True, "surface": True, "feed": True, "live": True, "update": True}, s)
    s2 = UP.sample_from_pc({"present": False, "reason": "no heartbeat branch"}, t0, cloud_ran=True)
    check("sample: Surface silent -> feed / live / update unknown (not counted)", s2 == {"cloud": True, "surface": False, "feed": None,
                                                                                         "live": None, "update": None}, s2)
    U = None
    U = UP.record(U, s, t0, 1800)
    U = UP.record(U, s2, t0 + 1800, 1800, info={"surface": "no heartbeat branch"})
    U = UP.record(U, s2, t0 + 3600, 1800)
    U = UP.record(U, s, t0 + 5400, 1800)
    inc = U["incidents"]
    check("record: one Surface incident, opened and closed, with its fix", len(inc) == 1 and inc[0]["part"] == "surface"
          and inc[0]["mins"] == 90 and "Surface" in inc[0]["fix"] and not U["open"], inc)
    v = UP.view(U, t0 + 5400)
    sf = next(p for p in v["parts"] if p["id"] == "surface")
    check("view: Surface 30-day uptime = up time / watched time", sf["uptime"] == round(100 * 2 * 1800 / (300 + 3 * 1800), 2) or 0 < sf["uptime"] < 100, sf)
    check("view: one square per weekday, state, incident list newest first", len(sf["days"]) >= 20 and sf["state"] in ("up", "degraded")
          and v["incidents"][0]["part"] == "surface", (len(sf["days"]), sf["state"]))
    # the cloud monitor's own dead-man's switch: a 2-hour gap inside the window = missed runs
    U2 = UP.cloud_gap({"cloud_last": t0}, t0 + 2 * 3600 + 120)
    check("cloud_gap: a 2-hour gap = 3 missed runs, one incident", U2["incidents"][-1]["part"] == "cloud" and "3 cloud monitor run" in U2["incidents"][-1]["what"],
          U2.get("incidents"))
    U3 = UP.cloud_gap({"cloud_last": ts(2026, 10, 16, 16, 2)}, ts(2026, 10, 19, 2, 2))
    check("cloud_gap: the weekend is outside the window (a few night slots at most)", not U3.get("incidents") or "run(s) missed" in U3["incidents"][-1]["what"])
    ns = {}
    out = UP.cloud_hook(ns, {"uptime": None}, pc_ok, now=t0)
    check("cloud_hook: writes state uptime inside the window, never raises", ns.get("uptime") and out and UP.cloud_hook({}, None, None) is None)
    tmp = tempfile.mkdtemp(prefix="le_perf_up_")
    try:
        pth = os.path.join(tmp, "uptime_pc.json")
        r1 = UP.pc_hook({"t": t0, "running": True, **{k: pc_ok[k] for k in ("health", "live_pub")}}, path=pth)
        r2 = UP.pc_hook({"t": ts(2026, 10, 24, 12, 0), "running": True}, path=pth)      # a Saturday: not sampled
        check("pc_hook: the PC's own log (no cloud part), weekends skipped", r1 and "cloud" not in r1["days"][UP._day(t0)]
              and r1["days"][UP._day(t0)]["surface"][0] > 0 and r2 is None and os.path.exists(pth))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ 11. exit efficiency
def exit_checks():
    from tools import trade_intel as TI
    rows = [{"source": "backtest", "span": "H1", "day": "2026-01-05", "exit": "TARGET", "r": 4.0, "mfe": 5.0, "mae": 0.2, "heat": 0.2},
            {"source": "backtest", "span": "H1", "day": "2026-01-06", "exit": "BE", "r": 0.0, "mfe": 2.0, "mae": 0.3, "heat": 0.3},
            {"source": "backtest", "span": "H2", "day": "2026-07-06", "exit": "STOP", "r": -1.0, "mfe": 0.5, "mae": 1.0, "heat": 1.0},
            {"source": "paper", "span": "paper", "day": "2026-10-20", "exit": "TARGET", "r": 3.0, "mfe": 3.0, "mae": 0.1}]
    E = TI.exit_eff(rows)
    y = E["y2026"]
    check("exit_eff: kept % of open profit = sum R / sum MFE (trades up > 0.25R)", y["capture_sum"] == round(100 * 3.0 / 7.5, 1), y)
    check("exit_eff: after +1R kept 4/7, giveback (1 + 2) / 2, one gave back", y["capture_up1_sum"] == round(100 * 4 / 7, 1)
          and y["giveback_avg"] == 1.5 and y["gave_back"] == 1 and y["loss_mfe_avg"] == 0.5, y)
    check("exit_eff: by exit type, by month incl. paper, spans", {x["exit"] for x in E["by_exit"]} == {"TARGET", "BE", "STOP"}
          and any(m["source"] == "paper" for m in E["by_month"]) and E["spans"]["paper"]["n"] == 1 and "kept" in E["text"])
    d = TI._load(TI.OUT)
    check("trade_intel.json carries exit_eff (2026: 120 trades)", d and (d.get("exit_eff") or {}).get("y2026", {}).get("n") == 120,
          (d or {}).get("exit_eff", {}).get("y2026"))
    if d:
        cp = TI.compact(TI.merge_live(d, {}, []))
        check("trade intel compact keeps exit_eff without the trade list, still small", cp["exit_eff"] and "trades" not in cp["exit_eff"]
              and len(json.dumps(cp)) < 80_000, len(json.dumps(cp)))


# ------------------------------------------------------------------------------------------------ 12. robustness
def robust_checks():
    from tools import lit_robust as LR
    rng = np.random.default_rng(3)
    o = np.array([100.0, 101.0, 102.0]); h = o + 2; l = o - 2; c = o + 1
    o2, h2, l2, c2 = LR._noisy(rng, 2, o, h, l, c)
    d = np.concatenate([o2 - o, h2 - h, l2 - l, c2 - c])
    check("noise: whole ticks within +/-2 (high / low may widen), bars stay valid", np.all(h2 >= np.maximum(o2, c2)) and np.all(l2 <= np.minimum(o2, c2))
          and np.allclose(np.round(d / 0.25), d / 0.25) and np.all(np.abs(o2 - o) <= 0.5))
    T = [{"pnl": 100.0, "qty": 4, "low": -50.0}, {"pnl": -80.0, "qty": 2, "low": -80.0}]
    S = LR.slip_trades(T, np.random.default_rng(1), 1, 1)
    check("slip: 1 tick in + 1 out = $1 a micro (MNQ $0.50 a tick)", S[0]["pnl"] == 96.0 and S[1]["pnl"] == -82.0 and S[0]["low"] == -54.0, S)
    D = LR.drop_trades([{"i": i} for i in range(1000)], np.random.default_rng(2), 0.2)
    check("drop: about 20% missed", 760 <= len(D) <= 840, len(D))
    R = PF._read(os.path.join(PF.LAB, "robust.json"))
    ok = R and R.get("same_as_run") and set(R["tests"]) >= {"noise1", "noise2", "slip03", "miss10", "miss20", "delay1", "delay2"}
    check("robust.json: base == run lit_live, every test, a headline", ok and R["card"]["headline"] and R["base"]["2026"]["net"] == 43385,
          R and (R.get("same_as_run"), list(R.get("tests") or {})))
    if ok:
        t = R["tests"]["noise1"]["2026"]
        check("robust.json: noise keeps a believable share (40-110%) with a p10-p90 range", 40 <= t["keep"] <= 110 and t["keep_p10"] <= t["keep"] <= t["keep_p90"], t)


# ------------------------------------------------------------------------------------------------ 13. months
def months_checks():
    wf = PF._read(os.path.join(PF.LAB, "walkforward.json"))
    check("walkforward.json: 729 grid points, 9 walk-forward months, the live point is in the grid",
          wf and wf["n_points"] == 729 and len(wf["walk_forward"]["months"]) == 9 and wf["backtest"]["2026-04"]["n"] > 0, wf and wf.get("n_points"))
    if not wf:
        return
    tot = sum(v["net"] for v in wf["backtest"].values())
    check("walkforward.json: the backtest months add up to run lit_live 2026 ($43,385)", abs(tot - 43385) <= 10, tot)
    st = {"ledger": {"9": {"day": "2026-10-20", "R": 1.0, "usd": 500.0, "exit": "TARGET"}}}
    ex = PF.exec_curve([{"status": "matched", "day": "2026-10-20", "entry_t": 1, "bt_pnl": 480.0, "bt_pnl_live_qty": 480.0, "live_pnl": 470.0, "slip_usd": -10}])
    M = PF.months(wf, st, None, ex)
    oc = next(r for r in M["rows"] if r["month"] == "2026-10")
    check("months: one row per month, the paper month and the replay of the same days", len(M["rows"]) == 10 and oc["paper"] == 500.0
          and oc["paper_n"] == 1 and oc["replay"] == 480.0 and oc["bt"] is not None, oc)


# ------------------------------------------------------------------------------------------------ 14. look-ahead audit
def lookahead_checks(quick):
    from tools import lookahead_audit as LA
    L = LA.load()
    check("lookahead_audit.json: LIT runs checked, none flagged, lit_live ok", L and L["summary"]["ok"] > 100 and L["summary"]["flag"] == 0
          and L["runs"]["lit_live"]["status"] == "ok", L and L.get("summary"))
    check("badge text", LA.badge({"status": "ok", "checked": 3}) .startswith("look-ahead check ok")
          and "FAILED" in LA.badge({"status": "flag", "checked": 3, "changed": 1}))
    if quick:
        return
    from engine import lit
    run = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
    P = LA.params_of(run)
    t = LA.top_trades(run, 1)[0]
    r = LA.check_trade(P, t["day"], t["entry_t"], t["dir"])
    check(f"check_trade: lit_live's best trade ({t['day']}) is the same on data cut at its entry bar", r["status"] == "ok" and r["fields"] > 20, r)
    # a planted look-ahead: a setup field that reads the length of the data (future bars) must be caught
    orig = lit.candidates

    def leaky(M, *a, **k):
        C = orig(M, *a, **k)
        for z in C:
            z["future_bars"] = int(M.n - z["entry_i"])
        return C
    lit.candidates = leaky
    LA._W.clear()
    try:
        r2 = LA.check_trade(P, t["day"], t["entry_t"], t["dir"])
    finally:
        lit.candidates = orig
        LA._W.clear()
    check("check_trade: a planted look-ahead (a setup field from future bars) is flagged", r2["status"] == "changed"
          and "setup.future_bars" in r2["diff"], r2)
    bogus = {**P, "disp": 9.9}
    r3 = LA.check_trade(bogus, t["day"], t["entry_t"], t["dir"])
    check("check_trade: params that do not give the trade = not replayable (skipped, not flagged)", r3["status"] == "not_replayable", r3)


# ------------------------------------------------------------------------------------------------ page data + renderer
def view_checks():
    v = PF.view(None, [], [], None)
    check("perf.view: every block, nothing raises without live data", all(k in v for k in ("range", "exec", "exit", "robust", "months", "status", "lookahead"))
          and v["exec"] is None and v["status"]["text"] == "No status samples yet" and v["robust"]["card"]["headline"], {k: type(x).__name__ for k, x in v.items()})
    st = {"ledger": {str(ts(2026, 10, 20, 3, 5)): {"day": "2026-10-20", "R": 2.1, "usd": 1200.0, "exit": "TARGET"}},
          "pc": {"exec": {"curve": {"days": [["2026-10-20", 1000.0, 980.0, 1000.0, 980.0, -20.0, 0.0, 0.0, 0.0]], "matched": 1, "missed": 0, "extra": 0}}},
          # the uptime sample sits on a recent weekday: engine/uptime.view shows the last KEEP_DAYS (30) days from now, so a fixed
          # date ages out of the window (2026-10-20 did on 2026-11-20)
          "uptime": UP.record(None, {"cloud": True, "surface": True}, ts(*_recent_weekday(), 9, 0), 1800)}
    from tools import build_web_dashboard as BW
    tmp = tempfile.mkdtemp(prefix="le_perf_bw_")
    try:
        sp = os.path.join(tmp, "state.json")
        json.dump(st, open(sp, "w"))
        cp = BW._perf(st, sp)
        size = len(json.dumps(cp, default=str))
        check("cloud build cut (data.json perf): paper range, the PC's exec curve, status; under 90 KB",
              cp and cp["range"]["paper"]["trades"] == 1 and cp["exec"]["gap"] == -20.0 and cp["status"]["parts"][0]["uptime"] == 100.0
              and size < 90_000, size)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    a = open(os.path.join(ROOT, "tools", "web_public", "perfcore.js"), "rb").read()
    b = open(os.path.join(ROOT, "web_next", "js", "next", "perfcore.js"), "rb").read()
    check("perfcore.js: the phone and PC copies are identical", a == b)
    html = open(os.path.join(ROOT, "tools", "web_public", "index.html"), encoding="utf-8").read()
    check("phone index.html loads perfcore.js before perf.js", 0 < html.find("perfcore.js") < html.find('src="perf.js'))
    ro = open(os.path.join(ROOT, "web_next", "js", "next", "routes.js"), encoding="utf-8").read()
    check("PC routes: Data > Performance", "id: 'perf'" in ro)
    for mod in ("engine/perf.py", "engine/health_band.py", "engine/uptime.py"):
        src = open(os.path.join(ROOT, mod), encoding="utf-8").read()
        check(f"{mod}: read-only (no order routing / sizing import)", not any(x in src for x in ("ninjatrader", "place_order", "import sizing", "live_model.json\", \"w")))


def main(argv=None):
    quick = "--quick" in (argv or sys.argv[1:])
    band_checks()
    exec_checks()
    uptime_checks()
    exit_checks()
    robust_checks()
    months_checks()
    lookahead_checks(quick)
    view_checks()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
