"""Every ATLAS lane is visible and explained (day-moneyaudit, 2026-11-27): today's S/R LONG traded on Zlarior 50K (combo) and the
Rapid EOD 25K, not on ATLAS funded (fixed: day-atlasmiss) and not on the 25K #2's combo, and nothing in the feed or the PC's day
folders said whether the 25K #2's ATLAS lane was even on, or why any non-B lane skipped a signal.

    python -X utf8 -m tests.test_moneyaudit_bot          # ~5 s, temp folders only, nothing routed

  1. account_b.lane_files / lanes_tiny: every ATLAS lane state file (B, the Rapid's _acctr, a combo lane _acct<id>x), each lane's
     open record + today's skip count + last reason (B left to "ab"), the combo switch's accounts as last 4 only
  2. the status post: "cb" rides the core "ab" (every 15 minutes), "abl" (the lanes) an ext block; no full account Name anywhere
  3. the PC's day folder (datapipe.day_decisions): every lane's held{} rows of that day, src "held_atlas" + the lane
  5. live_guard (the instant MISSED push): a stuck record of an EARLIER day no longer silences it (it silenced today's ATLAS
     funded miss: _in_trade_at counted the Nov 20 record as "in a trade"); a late check pushes; a same-day real position and a real
     rule hold stay quiet; the combo's ATLAS lanes (acct_x) are checked and listed at 01:55 / 09:00
  6. feed_trades ("at", the Trading page + Week in Review): the Rapid's ATLAS lane trades (its own state file) reach the Rapid's row
     (today's S/R +$304 was missing: "1 live trade +$304" for a +$608 day); a combo lane's open trade; refused entries never
  7. NinjaTrader's torn-state hold clears itself on a FLAT account with no position file (the real Nov 27 cause: both lanes
     "STARTUP DISARMED" all day): the account's own accounts.csv row at unrealized $0.00 on 3 reads over >= 5 min while the chart
     moved; NEVER on a non-zero / stale row, a position file not FLAT, an open leg, a still chart, or under 5 min; live_guard
     pushes a STARTUP DISARMED skip as a miss
  4. trade_watch: a twin entry the Rapid's lane checked with no reason -> "ATLAS on the Rapid EOD vs backtest: missed", its own key;
     the combo lane's stuck record -> missed; account B's keys and texts unchanged
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import account_b as AB  # noqa: E402
from engine import datapipe as DP  # noqa: E402
from tools import pc_report as PR  # noqa: E402
from tools import trade_watch as TW  # noqa: E402

RES = []
TB = 1795792200                     # Fri 2026-11-27 10:10 ET
OLD = 1795164300                    # Fri 2026-11-20 03:45 ET
NAME50, NAME25 = "MFFUEVBLDR123456016", "MFFUEVBLDR123456019"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def state(root, fn, **kw):
    d = os.path.join(root, "data")
    os.makedirs(d, exist_ok=True)
    b = {"v": 1, "ledger": [], "seen": [], "held": {}, "open_t": None, "prov": {}, **kw}
    json.dump(b, open(os.path.join(d, fn), "w"))


def setup(root):
    state(root, "live_state_acctb.json", held={str(TB): {"key": None, "why": "one position: EMA Fri 11-20 03:45 ET still open on account B",
                                                         "code": "open", "since": OLD}}, open_t=OLD)
    state(root, "live_state_acctr.json", held={str(TB - 600): {"key": "sr_nyreclaim", "why": "size 0 (best-day rule 30%)"}},
          seen=[["probe", TB]], saved_at=TB + 900)
    state(root, "live_state_acctb25k_2x.json", open_t=OLD, held={str(TB): {"key": None, "why": "one position: MACD Fri 11-20 still open",
                                                                          "code": "open", "since": OLD}}, saved_at=TB + 900)
    json.dump({"on": True, "accounts": [NAME50, NAME25]}, open(os.path.join(root, "data", "combo_50k.json"), "w"))
    json.dump({"account_b": {"account": "SIM-B", "plan": "builder25k", "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]}},
              open(os.path.join(root, "data", "account_b.json"), "w"))


def part1(root):
    lf = dict(AB.lane_files(os.path.join(root, "data")))
    check("1. lane_files: account B, the Rapid's lane, the 25K #2's combo lane", set(lf) == {"b", "r", "x:b25k_2"}, lf)
    lt = AB.lanes_tiny(os.path.join(root, "data"), now=TB + 60, root=root)
    ln = {r[0]: r for r in lt["ln"]}
    check("1. lanes_tiny: B left to 'ab'; the Rapid: no open record, 1 skip today + its reason; the combo lane: its stuck Nov 20 record",
          "b" not in ln and ln["r"][1:3] == [0, 1] and "best-day" in ln["r"][3] and ln["x:b25k_2"][1] == OLD and ln["x:b25k_2"][2] == 1, lt)
    check("1. the combo switch's accounts, last 4 only", lt["cb"] == ["6016", "6019"], lt)
    check("1. no lane files and no switch: only 'cb' [] (= the combo is off everywhere)",
          AB.lanes_tiny(os.path.join(root, "nope"), now=TB, root=os.path.join(root, "nope")) == {"cb": []})


def part2(root):
    lt = AB.lanes_tiny(os.path.join(root, "data"), now=TB + 60, root=root)
    st = AB.status_tiny(os.path.join(root, "data", "live_state_acctb.json"), now=TB + 60)
    full = {"t": TB + 60, "v": 1, "kind": "le-live", "ab": {**st, "cb": lt["cb"]}, "abl": lt["ln"]}
    core, exts = PR.split(full)
    x = {k: v for e in exts for k, v in (e.get("x") or {}).items()}
    check("2. core 'ab' carries 'cb' (every 15 minutes); the lanes ride an ext block 'abl'", core.get("ab", {}).get("cb") == ["6016", "6019"]
          and "abl" in x and "abl" not in core, (core.get("ab"), list(x)))
    blob = json.dumps([core, exts])
    check("2. no full account Name in any post", NAME50 not in blob and NAME25 not in blob)
    import inspect
    src = inspect.getsource(PR.full)
    check("2. pc_report.full wires lanes_tiny into 'ab' / 'abl'", "lanes_tiny" in src and 'out["abl"]' in src)


def part3(root):
    rows = DP.day_decisions("2026-11-27", root=root, exec_store=os.path.join(root, "logs"))
    h = [r for r in rows if r.get("src") == "held_atlas"]
    lanes = sorted(r["lane"] for r in h)
    check("3. the day folder's decisions: every lane's held{} of that day (B, Rapid, combo)", lanes == ["b", "r", "x:b25k_2"], h)
    check("3. ... each with its entry time and reason", all(r.get("entry_t") and r.get("why") for r in h), h)
    check("3. another day: none", not [r for r in DP.day_decisions("2026-11-26", root=root, exec_store=os.path.join(root, "logs"))
                                       if r.get("src") == "held_atlas"])


def part4(root):
    tw = {"2026-11-27": [{"key": "sr_nyreclaim", "short": "S/R", "entry_t": TB, "dir": 1, "entry": 26289.5, "stop": 26210.75, "usd": 304.1}]}
    fl = TW.atlas_flags(root, now=TB + 3600, twin=lambda days, keys: tw)
    by = {f["key"]: f for f in fl}
    check("4. account B's stuck record: its usual key and text", "watch:atlas:%d:missed" % TB in by
          and by["watch:atlas:%d:missed" % TB]["title"].startswith("ATLAS vs backtest") and "account B still marks" in by["watch:atlas:%d:missed" % TB]["body"], fl)
    r = by.get("watch:atlas-r:%d:missed" % TB)
    check("4. the Rapid's lane probed the open, routed nothing, no reason: its own push", r and r["title"].startswith("ATLAS on the Rapid EOD vs backtest")
          and "ATLAS on the Rapid EOD's lane" in r["body"], fl)
    x = by.get("watch:atlas-x:b25k_2:%d:missed" % TB)
    check("4. the combo lane's stuck Nov 20 record: its own push", x and "ATLAS (combo, b25k_2)" in x["title"] and "still marks" in x["body"], fl)
    check("4. three lanes, three pushes, no duplicate", len(fl) == 3 and len(by) == 3, [f["key"] for f in fl])


class Lane:
    def __init__(self, label, open_t=None, held=None, probed=(), keys=("ema_lon_vix", "macd_sweep", "sr_nyreclaim")):
        self.label, self.open_t, self.held = label, open_t, dict(held or {})
        self.spec = {"keys": list(keys), "armed": True, "adapter": "ninjatrader"}
        self.ledger, self.closes, self.problem, self.prov = [], [], None, {}
        self.seen = {("probe", t) for t in probed}
        self.name = label

    def disabled_reason(self):
        return None


class Bot:
    def __init__(self, b=None, x=None):
        self.running, self.kill, self.cfg = True, False, {"adapter": "ninjatrader"}
        self.second = {"strategies": {"sr_nyreclaim": {"trades": [{"entry_t": TB, "dir": 1, "r": 1.9, "risk_usd": 157.5}]}}}
        self.acct_b, self.acct_r, self.acct_r2, self.acct_x = b, None, None, dict(x or {})
        self.accts, self.seen, self.state = None, set(), {}


def part5(root):
    from engine import live_guard as LG
    now = TB + 300
    stuck = Lane("ATLAS funded", open_t=OLD, held={str(TB): {"key": None, "why": "one position ... still open", "code": "open", "since": OLD}})
    m = [x for x in LG.missed(Bot(b=stuck), now) if x["model"] == "atlas"]
    check("5. a stuck Nov 20 record: the MISSED push fires, naming the stuck record", len(m) == 1 and "stuck position record" in m[0]["why"], m)
    real = Lane("ATLAS funded", open_t=TB - 3600, held={str(TB): {"key": None, "why": "one position", "code": "open", "since": TB - 3600}})
    check("5. a real position of the same day: quiet (one position is its rule)", not LG.missed(Bot(b=real), now))
    rule = Lane("ATLAS funded", held={str(TB): {"key": "sr_nyreclaim", "why": "size 0 (soft daily loss)"}}, probed=[TB])
    check("5. a real rule hold (size 0): quiet", not LG.missed(Bot(b=rule), now))
    late = Lane("ATLAS funded", held={str(TB): {"key": None, "why": "late: this 5m open was first checked 60 s after it", "code": "late"}})
    m = LG.missed(Bot(b=late), now)
    check("5. a late check: the MISSED push fires with that reason", len(m) == 1 and m[0]["why"].startswith("late"), m)
    combo = Lane("Zlarior 25K #2 (ATLAS)", probed=[])
    b = Bot(b=Lane("ATLAS funded", probed=[TB]), x={"b25k_2": combo})
    b.acct_b.ledger = [{"side": "buy", "entry_t": TB, "result": {"ok": True}}]
    m = LG.missed(b, now)
    check("5. the combo's ATLAS lane on the 25K #2 is checked too (B routed it, the lane did not)",
          [x["account"] for x in m] == ["Zlarior 25K #2 (ATLAS)"] and "did not run" in m[0]["why"], m)
    check("5. ... and it is one of the armed-check accounts (01:55 / 09:00 lines)", combo in LG.atlas_accounts(b))


def part6(root):
    from engine import feed_trades as FT
    d = os.path.join(root, "f6", "data")
    os.makedirs(d, exist_ok=True)
    led = [{"t": TB + 5, "sym": "NQ", "side": "buy", "qty": 1, "stop": 26210.75, "target": 26440.25, "entry": 26289.5, "entry_t": TB,
            "src": "sr_nyreclaim", "result": {"ok": True}},
           {"t": TB - 895, "sym": "NQ", "side": "sell", "qty": 1, "stop": 1, "target": 1, "entry": 1, "entry_t": TB - 900, "result": {"ok": False}}]
    json.dump({"ledger": led, "closes": [["2026-11-27", TB + 900, 304.0, TB]], "prov": {str(TB): {"fill": 26287.25}}, "open_t": None},
              open(os.path.join(d, "live_state_acctr.json"), "w"))
    json.dump({"ledger": [{**led[0], "entry_t": TB + 3600}], "closes": [], "prov": {}, "open_t": TB + 3600},
              open(os.path.join(d, "live_state_acctb25k_2x.json"), "w"))
    L = {"accounts": [{"id": "rapid", "kind": "eval", "trades": [], "broker_account": "MFFUEVRREOD60206020"}]}
    at = FT.compact(L, data_dir=d)
    by = {r["id"]: r for r in at["a"]}
    r = by["rapid"]["tr"]
    check("6. the Rapid's ATLAS lane trade reaches its row: 10:10 LONG 1 @ the fill, closed +$304; the refused one left out",
          len(r) == 1 and r[0][0] == TB and r[0][2] == 1 and r[0][3] == 1 and r[0][4] == 26287.25 and r[0][8] == 304.0 and r[0][1] == TB + 900, at)
    x = by.get("b25k_2", {}).get("tr") or []
    check("6. the combo lane's open trade on the 25K #2 (no row of its own): a new row, open", len(x) == 1 and x[0][1] is None and x[0][7] is None, at)
    check("6. no lane files: the old block", FT.compact({"accounts": []}, data_dir=os.path.join(root, "none")) is None)


def part7(root):
    from engine import ninjatrader as N
    from engine import live_guard as LG

    def adapter(tag):
        fold = os.path.join(root, f"nt7{tag}", "NinjaTrader 8")
        N._FakeNT(fold)
        os.makedirs(os.path.join(fold, "le_feed"), exist_ok=True)
        stp = os.path.join(root, f"nt7{tag}", "st.json")
        open(stp, "w").write('{"legs": [ {"status": "prot')          # torn mid-write
        now = [float(TB - 1200)]
        cfg = {"adapter": "ninjatrader", "sym": "NQ", "nt_account": "Sim102", "nt_folder": fold, "params": {"max_micros": 20, "flat_mod": 955},
               "nt_state_path": stp, "nt_audit_log": os.path.join(root, f"nt7{tag}", "oif.log"), "nt_session_from": 120}
        ad = N.NinjaTraderAdapter(cfg, clock=lambda: now[0])
        return ad, fold, now

    def feed(fold, t, px, unreal=0.0, acct="Sim102"):
        open(os.path.join(fold, "le_feed", "accounts.csv"), "w").write(f"name,time,cash,realized,unrealized,netliq\n{acct},{int(t)},25401.38,0,{unreal},25401.38\n")
        with open(os.path.join(fold, "le_feed", "MNQ_1m.csv"), "w") as fh:
            fh.write("time,open,high,low,close,volume\n" + "".join(f"{int(t) - 60 * k - 60},{px},{px},{px},{px},10\n" for k in range(5, -1, -1)))

    def run(tag, steps):
        ad, fold, now = adapter(tag)
        ok0 = ad.state_problem is not None and not ad._state_problem_resolved()
        res = []
        for dt_, px, un in steps:
            now[0] = float(TB - 1200 + dt_)
            feed(fold, now[0] - 30, px, un)
            res.append(ad._state_problem_resolved())
        return ok0, res, ad
    ok0, res, ad = run("a", [(0, 26280.0, 0.0), (180, 26282.0, 0.0), (360, 26285.0, 0.0)])
    check("7. a torn state file, no position file: blocked at first (as before)", ok0)
    check("7. ... cleared on the 3rd $0.00 account read, 6 min, the chart moved 5 pts; entries allowed again",
          res == [False, False, True] and ad.state_problem is None, res)
    _, res, _ = run("b", [(0, 26280.0, 0.0), (180, 26282.0, -6.5), (360, 26285.0, 0.0), (420, 26286.0, 0.0)])
    check("7. never: a non-zero unrealized read starts the count over (a position is open)", res == [False, False, False, False], res)
    _, res, _ = run("c", [(0, 26280.0, 0.0), (180, 26280.0, 0.0), (360, 26280.0, 0.0)])
    check("7. never: a still chart (a break-even position would read $0 too)", res == [False, False, False], res)
    _, res, _ = run("d", [(0, 26280.0, 0.0), (120, 26282.0, 0.0), (240, 26285.0, 0.0)])
    check("7. never: under 5 minutes of reads", res == [False, False, False], res)
    ad, fold, now = adapter("e")
    open(os.path.join(fold, "outgoing", "MNQ 12-26 Globex_Sim102_Position.txt"), "w").write("LONG;1;26280")
    r = []
    for dt_, px in ((0, 26280.0), (180, 26282.0), (360, 26285.0)):
        now[0] = float(TB - 1200 + dt_)
        feed(fold, now[0] - 30, px, 0.0)
        r.append(ad._state_problem_resolved())
    check("7. never: a position file that says LONG", r == [False, False, False] and ad.state_problem is not None, r)
    ad, fold, now = adapter("f")
    r = []
    for dt_, px in ((0, 26280.0), (180, 26282.0), (360, 26285.0)):
        now[0] = float(TB - 1200 + dt_)
        feed(fold, now[0] - 400, px, 0.0)                                     # the account row is 6+ minutes old
        r.append(ad._state_problem_resolved())
    check("7. never: a stale account row", r == [False, False, False], r)
    dis = Lane("ATLAS funded", held={str(TB): {"key": "sr_nyreclaim", "why": "STARTUP DISARMED until reconciled: the bot's NinjaTrader state file was unreadable"}}, probed=[TB])
    m = LG.missed(Bot(b=dis), TB + 300)
    check("7. live_guard: a STARTUP DISARMED skip is a MISSED push (with that reason)", len(m) == 1 and m[0]["why"].startswith("STARTUP DISARMED"), m)


def main():
    root = tempfile.mkdtemp(prefix="moneyaudit_")
    try:
        setup(root)
        for fn in (part1, part2, part3, part4, part5, part6, part7):
            try:
                fn(root)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{fn.__name__} raised {e.__class__.__name__}: {e}", False)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if RES and all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
