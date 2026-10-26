"""The December 2026 roll (MNQ / NQ 12-26 -> 03-27, orders on Thu 2026-12-10 00:00 ET), simulated end to end.

    python -X utf8 -m tests.test_dec_roll           (~1 min; temp folders only, fake NinjaTrader, no network)

A. The merge on a simulated roll: real NQ 5m / 1m bars are the NEW contract ("truth"); the OLD contract prints truth minus
   a constant 301.25 pts. The TradingView export on disk and the PC's NinjaTrader archive hold old-contract bars; the
   owner switches the LE_BarFeed chart on a Wednesday at 17:00 ET and LE_BarFeed rewrites its files on the new contract.
   On every session after the switch (Thu .. the next Fri) the PC bot's merged LIT window (engine/live.py LiveBot._merged /
   _lit_1m, engine/pcbars.merge_basis) must equal the truth bar for bar (5m and 1m), and LIT's decisions on it (every
   signal and every trade: entry, stop, target, micros, exit) must equal LIT's on the consistently adjusted series. Same on
   the NQ chart (signal_root "NQ"). Without the back-adjustment the levels sit ~300 pts off (the shift matters). The
   real dates of the bars do not matter to the merge; the contract names below run on the December dates.
B. December dates: the order contract by date (MNQ 12-26 through Wed 12-09, MNQ 03-27 from Thu 12-10, NQ alike); the
   chart against it (engine/roll_watch.py): ok -> soon (7 days before) -> early (chart switched Wed evening) -> bad (chart
   still on 12-26 on Thu) with the launch checklist's red line, the Start page's "Live bars from NinjaTrader" line
   (engine/go.py), the dated reminder pushes (7 days / 1 day before, the PC's ops keys) and the "chart still on 12-26"
   push (PC ops tick and the cloud monitor, never both).
C. The adapter (engine/ninjatrader.py) on Thu 12-10 with the chart left on 12-26: entry refused, no order file, the
   startup reconcile names it; chart on 03-27: the entry goes to MNQ 03-27.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import pcbars, roll_watch  # noqa: E402
from engine.ninjatrader import ET, FEED_DIR, nt_instrument  # noqa: E402

RES = []
COLS = ["time", "open", "high", "low", "close", "volume"]
D = 301.25                                  # the simulated roll gap (03-27 minus 12-26), constant


def check(name, ok, info=None):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:700]) if not ok and info is not None else ''}", flush=True)
    RES.append(bool(ok))


def at(y, m, d, hh=0, mm=0, ss=0):
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


class Env:
    def __init__(self, **kw):
        self.kw, self.old = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.old[k] = os.environ.get(k)
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        return self

    def __exit__(self, *a):
        for k, v in self.old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def write_feed(folder, root, b1, b5, t5, t1, upto, inst):
    """LE_BarFeed's files for a chart of `root`: 5m from t5, 1m from t1, bars closed before upto, the chart's contract."""
    d = os.path.join(folder, FEED_DIR)
    os.makedirs(d, exist_ok=True)
    for name, df, secs, t0 in ((f"{root}_1m.csv", b1, 60, t1), (f"{root}_5m.csv", b5, 300, t5)):
        x = df[(df["time"] >= t0) & (df["time"] + secs <= upto)]
        x[COLS].to_csv(os.path.join(d, name), index=False)
    open(os.path.join(d, f"{root}_instrument.txt"), "w").write(inst)


def lit_decisions(df5, df1, now):
    """LIT (live_model.json) at `now`: (signals, trades) as comparable tuples."""
    from engine import lit, lit_live
    from engine.lab_adapter import live_model
    P = {**lit.DEFAULTS, **(live_model().get("lit") or {})}
    keep = {}
    res = lit_live.run(df5[df5["time"] + 300 <= now], P, one_min=df1[df1["time"] + 60 <= now], now=now, sym="NQ", keep=keep)
    sig = [(int(s["t"]), int(s["dir"]), round(float(s["limit_px"]), 2), round(float(s["stop_px"]), 2),
            round(float(s["target_px"]), 2)) for s in keep["R"]["signals"]]
    tr = [(t["entry_t"], t["dir"], round(t["entry"], 2), round(t["stop"], 2), round(t["target"], 2), t["qty"], t["exit_t"],
           t["exit_reason"], round(t["pnl"], 2)) for t in res["trades"]]
    return sig, tr


# ------------------------------------------------------------------------------------------------ A. the merge
def merge_part(tmp, root, signal):
    from tests import test_roll as R
    from engine.lit_live import window_start
    T5, T1 = R.load("5m"), R.load("1m")                 # the new contract (truth)
    O5, O1 = R.plus(T5, -D), R.plus(T1, -D)             # the old contract
    tv_end = at(2026, 9, 25)
    old_inst, new_inst = f"{root} 12-26", f"{root} 03-27"
    with Env(LE_SIGNAL_ROOT=signal, LE_LIVE_MODEL=None):
        pc = R.PC(tmp, f"A_{root}", O5[O5.time < tv_end], O1[O1.time < tv_end])
        for d in (5, 6, 7):                              # Mon-Wed: the chart on the old contract, the archive fills
            n = at(2026, 10, d, 12, 0, 30)
            write_feed(pc.folder, root, O1, O5, n - 29 * 86400, n - 14 * 86400, n - n % 60, old_inst)
            d5, _ = pc.poll(n)
        ok_before = R.diff(d5, O5, window_start(n), n - 300)[0] < 1e-9
        arc_old = R.diff(pcbars.archive_read("NQ", "5m", pc.arc), O5, 0, n)[0] < 1e-9
        check(f"A[{root}]. Mon-Wed, chart on {old_inst}: one contract (old) everywhere, archive written", ok_before and arc_old)
        sessions = ["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]
        bad, n_sig, n_tr, first = [], 0, 0, True
        for day in sessions:
            y, m, dd = map(int, day.split("-"))
            now = at(y, m, dd, 17, 0, 5)
            # Wed 17:00 ET: the chart switched to the new contract; LE_BarFeed writes its whole history on it
            write_feed(pc.folder, root, T1, T5, now - 29 * 86400, now - 14 * 86400, now - now % 60, new_inst)
            d5, d1 = pc.poll(now)
            ws = window_start(now)
            e5, s5, k5 = R.diff(d5, T5, ws, now - 300)
            e1, s1, k1 = R.diff(d1, T1, int(d1["time"].min()), now - 60)
            t1m = T1[T1.time.isin(set(d1.time))]
            got, want = lit_decisions(d5, d1, now), lit_decisions(T5[T5.time < now], t1m, now)
            n_sig, n_tr = max(n_sig, len(want[0])), max(n_tr, len(want[1]))
            if not (e5 < 1e-9 and s5 and e1 < 1e-9 and s1 and got == want):
                bad.append((day, e5, s5, e1, s1, len(got[0]), len(want[0]), len(got[1]), len(want[1])))
            if first:
                first = False
                arc = pcbars.archive_read("NQ", "5m", pc.arc)
                check(f"A[{root}]. first poll after the switch: archive back-adjusted by +{D} (= the truth) and the log says "
                      "'back-adjusted'", R.diff(arc, T5, 0, now)[0] < 1e-9 and any("back-adjusted" in x for x in pc.log()),
                      pc.log()[:6])
        check(f"A[{root}]. every session Thu 10-08 .. Fri 10-16 after the switch: the LIT window (5m + 1m) = the truth bar "
              f"for bar, and LIT's {n_sig} signals / {n_tr} trades in the window = LIT on the adjusted series", not bad, bad)
        # the control: no back-adjustment (old bars left 301.25 pts low) -> the levels and the decisions are wrong
        now = at(2026, 10, 16, 17, 0, 5)
        naive5 = pd.concat([O5[O5.time < now - 29 * 86400], T5[(T5.time >= now - 29 * 86400) & (T5.time < now)]])
        naive1 = pd.concat([O1[O1.time < now - 14 * 86400], T1[(T1.time >= now - 14 * 86400) & (T1.time < now)]])
        days = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]
        ws = window_start(now)
        off = R.lvl_diff(R.levels(naive5[naive5.time >= ws], days), R.levels(T5[(T5.time >= ws) & (T5.time < now)], days))
        check(f"A[{root}]. control: without the back-adjustment PMH/PML sit {off:.2f} pts off: the shift is what keeps LIT right",
              off > 250, off)


# ------------------------------------------------------------------------------------------------ B. December dates
def dates_part(tmp):
    from engine import go, launch_check as LC, ops_checks as oc
    from tests.test_launch_checklist import good_facts, good_health
    check("B. order contract: MNQ 12-26 through Wed 12-09, MNQ 03-27 from Thu 12-10 (NQ alike)",
          nt_instrument("MNQ", dt.date(2026, 12, 9)) == "MNQ 12-26" and nt_instrument("MNQ", dt.date(2026, 12, 10)) == "MNQ 03-27"
          and nt_instrument("NQ", dt.date(2026, 12, 10)) == "NQ 03-27")
    seq = [(at(2026, 11, 20, 10), "MNQ 12-26", "ok"), (at(2026, 12, 3, 16, 6), "MNQ 12-26", "soon"),
           (at(2026, 12, 9, 18, 30), "MNQ 03-27", "early"), (at(2026, 12, 9, 18, 30), "MNQ 12-26", "soon"),
           (at(2026, 12, 9, 10, 0), "MNQ 03-27", "bad"),           # switched during Wed's session: no entry until 00:00
           (at(2026, 12, 10, 1, 40), "MNQ 12-26", "bad"), (at(2026, 12, 10, 1, 40), "MNQ 03-27", "ok"),
           (at(2026, 12, 10, 1, 40), "NQ 12-26", "bad"), (at(2026, 12, 10, 1, 40), "NQ 03-27", "ok"),
           (at(2026, 12, 10, 1, 40), None, "unknown"), (at(2026, 12, 10, 1, 40), "MNQ ##-##", "continuous")]
    got = [(roll_watch.state(t, ch)["level"]) for t, ch, _ in seq]
    check("B. chart vs orders: ok (Nov 20) -> soon (Dec 3) -> early (switched Wed 18:30) / bad (switched Wed 10:00, in the "
          "session) -> bad (still 12-26 on Thu) -> ok (03-27); NQ chart alike; unknown / continuous",
          got == [w for _, _, w in seq], list(zip(got, [w for _, _, w in seq])))
    wed = roll_watch.state(at(2026, 12, 9, 10, 0), "MNQ 03-27", "MNQ")
    check("B. switched too early (Wed 10:00): the line says orders are still on 12-26 and to put the chart back",
          "orders on MNQ 12-26" in wed["say"] and "Instrument > MNQ 12-26" in wed["fix"], wed)
    def good_facts_at(t):
        """test_launch_checklist's all-green facts, moved to time t (Sim results and the bot start stay fresh)."""
        f = good_facts()
        f.update(t=t, bot_started_t=t - 86400, startup={"ok": True, "since": t - 300, "problems": []},
                 sim={k: {**v, "t": t - 1200} for k, v in f["sim"].items()})
        return f
    st_bad = roll_watch.state(at(2026, 12, 10, 1, 40), "MNQ 12-26", "MNQ")
    li = roll_watch.launch_item(roll_watch.compact(st_bad))
    check("B. launch checklist line 'Chart contract (roll)': red on Thu with the chart on 12-26, says MNQ 03-27 and the "
          "NinjaTrader click, fix = python tools/roll_check.py", li["state"] == "bad" and "MNQ 03-27" in li["detail"]
          and "Instrument" in li["detail"] and li["fix"] == roll_watch.CHECK_CMD, li)
    t_bad = at(2026, 12, 10, 1, 40)
    cl = LC.checklist({**good_facts_at(t_bad), "roll": roll_watch.compact(st_bad)}, good_health(), True, t_bad)
    it = next(i for i in cl["items"] if i["key"] == "roll")
    check("B. ... in the real checklist: the one red line, not all green, the detail fits (no cut)",
          it["state"] == "bad" and cl["n_red"] == 1 and not cl["all_green"] and it["detail"].endswith("save workspace"),
          [(i["key"], i["state"]) for i in cl["items"] if i["state"] != "good"] + [it["detail"]])
    t_eve = at(2026, 12, 9, 18, 30)
    f_ok = {**good_facts_at(t_eve), "roll": roll_watch.compact(roll_watch.state(t_eve, "MNQ 03-27", "MNQ"))}
    cl_ok = LC.checklist(f_ok, good_health(), True, t_eve)
    check("B. chart switched Wed evening (orders still 12-26 until 00:00) -> green, all green",
          next(i for i in cl_ok["items"] if i["key"] == "roll")["state"] == "good" and cl_ok["all_green"],
          [(i["key"], i["state"], i["detail"]) for i in cl_ok["items"] if i["state"] != "good"])
    t_wk = at(2026, 12, 3, 16, 6)
    soon = LC.checklist({**good_facts_at(t_wk), "roll": roll_watch.compact(roll_watch.state(t_wk, "MNQ 12-26", "MNQ"))},
                        good_health(), True, t_wk)
    si = next(i for i in soon["items"] if i["key"] == "roll")
    check("B. a week before: info line (not counted) with the date and what to do, uncut", si["state"] == "info"
          and soon["all_green"] and "Wed Dec 09" in si["detail"] and "MNQ 03-27" in si["detail"]
          and si["detail"].endswith("save workspace"), si)
    # the Start page: "Live bars from NinjaTrader" carries the roll line with its own fix
    folder = os.path.join(tmp, "B_nt")
    d = os.path.join(folder, FEED_DIR)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "MNQ_instrument.txt"), "w").write("MNQ 12-26")
    pd.DataFrame([[at(2026, 12, 10, 1, 30), 1, 1, 1, 1, 1]], columns=COLS).to_csv(os.path.join(d, "MNQ_5m.csv"), index=False)
    with Env(LE_SIGNAL_ROOT=None, LE_LIVE_MODEL=None):
        why = roll_watch.problem(folder, now=at(2026, 12, 10, 1, 40))
        why_ok = roll_watch.problem(folder, now=at(2026, 12, 9, 10, 0))
    check("B. go.feed_problem's roll line on Thu: 'Contract roll: chart still on MNQ 12-26, orders on MNQ 03-27 since Thu "
          "Dec 10: no new entry. Fix: ...'; Wed: none", why and why.startswith(roll_watch.PREFIX) and "since Thu Dec 10" in why
          and "Instrument > MNQ 03-27" in why and why_ok is None, (why, why_ok))
    saved = {k: getattr(go, k) for k in ("CFG", "AUTOSTART", "ENV_FILE", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH",
                                         "ANCHOR_PATH", "JOB_FILE", "JOB_LOG", "sims_passed")}
    try:
        go.CFG, go.AUTOSTART, go.ENV_FILE = (os.path.join(tmp, n) for n in ("start_bot.json", "autostart.json", "env.ps1"))
        go.SECOND_PATH = os.path.join(tmp, "second_model.json")
        shutil.copy(os.path.join(ROOT, "second_model.json"), go.SECOND_PATH)
        go.ALLOW_PATH, go.JOB_FILE = os.path.join(tmp, "allow.json"), os.path.join(tmp, "job.json")
        go.ACCOUNTS_PATH, go.ANCHOR_PATH = os.path.join(tmp, "accounts.json"), os.path.join(tmp, "anchor.json")
        go.JOB_LOG = os.path.join(tmp, "job.log")
        go.sims_passed = lambda: {"roundtrip": True, "add": True}
        s_roll = {x["key"]: x for x in go.status(state={"running": False}, connected=lambda: True, feed=lambda: why)["steps"]}
        s_stale = {x["key"]: x for x in go.status(state={"running": False}, connected=lambda: True,
                                                  feed=lambda: "MNQ_5m.csv is stale")["steps"]}
    finally:
        for k, v in saved.items():
            setattr(go, k, v)
    check("B. Start page: 'Live bars from NinjaTrader' red with the roll line as its detail (its own fix, not the reload one); "
          "a stale feed keeps the reload fix", not s_roll["feed"]["done"] and s_roll["feed"]["detail"] == why
          and go.FEED_FIX not in s_roll["feed"]["detail"] and s_stale["feed"]["detail"].endswith(go.FEED_FIX),
          (s_roll["feed"], s_stale["feed"]["detail"]))
    # pushes: the dated reminders (PC ops and cloud: the same keys), the late alarm
    r7, r1, r0 = (roll_watch.reminders(t) for t in (at(2026, 12, 3, 16, 6), at(2026, 12, 9, 1, 45), at(2026, 12, 10, 2, 0)))
    ops7, ops1 = oc.roll_notice(at(2026, 12, 3, 16, 6)), oc.roll_notice(at(2026, 12, 9, 1, 45))
    check("B. reminders: Thu Dec 3 (7 days before) and Wed Dec 9 (the day before), none on the day; the same keys as the PC's "
          "ops helper", [x["key"] for x in r7] == ["ops:roll:MNQ 03-27:week"] and [x["key"] for x in r1] == ["ops:roll:MNQ 03-27:tomorrow"]
          and r0 == [] and r7[0]["key"] == ops7["key"] and r1[0]["key"] == ops1["key"] and roll_watch.reminders(at(2026, 11, 25)) == []
          and "Wed Dec 09" in r7[0]["body"] and "MNQ 03-27" in r7[0]["body"], (r7, r1, r0))
    late = roll_watch.late_notice(st_bad, at(2026, 12, 10, 1, 40))
    check("B. late alarm: 'Chart still on MNQ 12-26: no new entries', once per trading day", late and late["key"]
          == "roll:late:MNQ 03-27:2026-12-10" and "MNQ 12-26" in late["title"] and "Instrument > MNQ 03-27" in late["body"]
          and roll_watch.late_notice(st_bad, at(2026, 12, 10, 19, 0))["key"].endswith("2026-12-11"), late)
    t = at(2026, 12, 10, 1, 40)
    hb = {"present": True, "age_s": 120, "ops": {"tick_t": t - 7200}, "launch": {"facts": {"roll": roll_watch.compact(st_bad)}}}
    c_late = roll_watch.cloud_notices(hb, t)
    c_ops = roll_watch.cloud_notices({**hb, "ops": {"tick_t": t - 120}}, t)
    c_off = roll_watch.cloud_notices({"present": False}, at(2026, 12, 3, 16, 6))
    check("B. cloud monitor: PC ops helper silent -> the late alarm from the heartbeat; ops helper running -> nothing (it "
          "pushes itself); PC off on Dec 3 -> the dated reminder", [n["key"] for n in c_late] == ["roll:late:MNQ 03-27:2026-12-10"]
          and c_ops == [] and [n["key"] for n in c_off] == ["ops:roll:MNQ 03-27:week"], (c_late, c_ops, c_off))
    # the PC's ops tick (01:42 ET pre-session run) pushes the late alarm, once
    sent = []
    spath = os.path.join(tmp, "ops_state.json")
    pre = at(2026, 12, 10, 1, 42)
    ctx = {"now": pre, "folder": folder, "ping": None, "hb": {}, "net": {"up": True, "n": 3, "drift_s": 0.1}, "state": {},
           "light": True}
    with Env(LE_SIGNAL_ROOT=None, LE_LIVE_MODEL=None, LE_OPS_PUSH=None):
        oc.tick(now=pre, ctx=ctx, state=oc.load_state(spath), sender=lambda p: (sent.append(p), {"sent": 1})[1],
                state_path=spath, do_backup=False)
        oc.tick(now=pre + 300, ctx={**ctx, "now": pre + 300}, state=oc.load_state(spath),
                sender=lambda p: (sent.append(p), {"sent": 1})[1], state_path=spath, do_backup=False)
    keys = [p["key"] for p in sent]
    check("B. PC ops tick 01:42 ET Thu: the 'chart still on MNQ 12-26' push goes out once", keys.count("roll:late:MNQ 03-27:2026-12-10") == 1,
          keys)


# ------------------------------------------------------------------------------------------------ C. the adapter
def adapter_part():
    from tests.test_lit_add_safety import World
    with Env(LE_SIGNAL_ROOT=None, LE_LIVE_MODEL=None):
        w = World()
        fake = w.fake
        d = os.path.join(w.folder, FEED_DIR)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "MNQ_instrument.txt"), "w").write("MNQ 12-26")
        w.now[0] = dt.datetime(2026, 12, 10, 2, 5, 3, tzinfo=ET).timestamp()
        ad = w.make("c.json")
        fake.move(25330.0)
        t = int(w.now[0]) - 3
        k = len(fake.files)
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 25300.0, "target": 25400.0, "entry": 25330.0, "entry_t": t})
        sp = ad.startup_problems()
        check("C. Thu 12-10 02:05, chart left on MNQ 12-26: entry refused, no order file, the startup reconcile names it",
              not r["ok"] and len(fake.files) == k and any("Chart is on the old contract (MNQ 12-26)" in p for p in sp), (r, sp))
        open(os.path.join(d, "MNQ_instrument.txt"), "w").write("MNQ 03-27")
        r = ad.send({"sym": "NQ", "side": "buy", "qty": 2, "stop": 25300.0, "target": 25400.0, "entry": 25330.0, "entry_t": t})
        lines = [ln for _, ls in fake.files[k:] for ln in ls]
        check("C. chart switched to MNQ 03-27: the entry and its bracket go to MNQ 03-27, nothing left in the startup check",
              r["ok"] and any(";MNQ 03-27;BUY;2;" in ln for ln in lines)
              and not any("Chart is on" in p for p in ad.startup_problems()), (r, lines))
        ad.send({"side": "exit", "reason": "x", "entry_t": t})


def main():
    from engine import alerts, news
    alerts.send = lambda *a, **kw: None
    news.volatility = lambda *a, **kw: None
    news.ff_calendar = lambda: []
    tmp = tempfile.mkdtemp(prefix="le_decroll_")
    undo = pcbars.install_yahoo_guard()
    try:
        dates_part(tmp)
        adapter_part()
        merge_part(tmp, "MNQ", None)
        merge_part(tmp, "NQ", "NQ")
        check("no Yahoo call anywhere", not undo.calls, undo.calls)
    finally:
        undo()
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nDecember roll: {n}/{len(RES)} {'PASS' if n == len(RES) else 'FAIL'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
