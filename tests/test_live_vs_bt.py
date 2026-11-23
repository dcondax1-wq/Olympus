"""Live vs backtest, daily (night-livevsbt 2026-11-23, engine/live_vs_bt.py). Fixture ledgers / day folders in temp dirs; nothing
is sent, no real file is read or written (OUT, the day folders and the brief's cache all point at temp paths).

    python -X utf8 -m tests.test_live_vs_bt

 a. the rules: fills close to the model = ok; a missed trade (-its model $), an extra trade (+its real $) or an average entry
    slippage above 2 ticks = flagged; the window is the last 10 events; the plain phone line and the brief line
 b. the real pipeline on a fixture PC day folder (tools/reconcile_live): the ATLAS 15-tick fill, the refused Zlarior entry, the
    twin's missed and extra trades
 c. the push: once a day per flagged bot after 16:20 ET on a CME day (not before, not on a weekend / a full closure, not twice)
 d. the brief: one line from the last saved check; none when it is older than 30 h
 e. read-only: the module has no order / adapter / arm call
"""
import gzip
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import live_vs_bt as L  # noqa: E402
from tools import reconcile_live as RL  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"))


def tr(bot, t, diff, ticks=1.0, real=None, entry_usd=0.0, exit_usd=0.0):
    return {"bot": bot, "entry_t": t, "diff_usd": diff, "entry_ticks": ticks, "real_usd": real, "entry_usd": entry_usd, "exit_usd": exit_usd}


def part_a():
    T = [tr("Zlarior", 1000 + i, -2.0, ticks=1.0) for i in range(4)]
    o = L.evaluate(T, [])
    z = o["LIT"]
    check("a1. 4 trades, fills close to the model: not flagged, the plain line", not z["flag"] and z["gap"] == -8.0
          and z["line"] == "LIT live is $8 behind the backtest over the last 4 trades: fills close to the model (entry +1.0 ticks avg)", z["line"])
    check("a2. the brief's short form", z["short"] == "LIT -$8 over 4 trades (ok)", z["short"])
    o = L.evaluate(T, [{"bot": "Zlarior", "entry_t": 2000, "cause": "missed (refused by the broker)", "model_usd": 250.0}])
    z = o["LIT"]
    check("a3. a missed trade: flagged, the gap counts its model $ (-$250), the cause named", z["flag"] and z["missed"] == 1
          and z["gap"] == -258.0 and z["line"].startswith("LIT live is $258 behind the backtest over the last 5 trades: 1 missed (missed (refused by the broker))"), z["line"])
    o = L.evaluate(T + [tr("Zlarior", 3000, 0.0, real=120.0)], [], extra={3000})
    z = o["LIT"]
    check("a4. an extra trade: flagged, the gap counts its real $ (+$120)", z["flag"] and z["extra"] == 1 and z["gap"] == 112.0
          and "ahead of the backtest" in z["line"] and "1 extra" in z["line"], z["line"])
    S = [tr("ATLAS", 5000 + i, -7.0, ticks=3.5, entry_usd=-7.0) for i in range(12)]
    a = L.evaluate(S, [])["ATLAS"]
    check("a5. average entry slippage 3.5 ticks (> 2): flagged; only the last 10 counted", a["flag"] and a["n"] == 10 and a["gap"] == -70.0
          and "entry slippage +3.5 ticks avg (-$70)" in a["line"], a["line"])
    two = L.evaluate([tr("ATLAS", 1, -4.0, ticks=2.0)], [])["ATLAS"]
    check("a6. exactly 2 ticks: not flagged (above 2 only)", not two["flag"], two)
    check("a7. no live trade yet: a plain 'no live trade' line, no brief part", L.evaluate([], [])["LIT"]["n"] == 0
          and L.brief_line({"bots": L.evaluate([], [])}) == "")
    res = {"bots": L.evaluate(T, [])}
    res["bots"]["ATLAS"] = a
    check("a8. the brief line: both bots, one line", L.brief_line(res) ==
          "Live vs backtest: LIT -$8 over 4 trades (ok) · ATLAS -$70 over 10 trades (entry slippage +3.5 ticks avg (-$70))", L.brief_line(res))


def gzl(p, rows):
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def part_b(tmp):
    d = os.path.join(tmp, "days", "2026-11-18")
    os.makedirs(d)
    T1, T2, T3 = 1795513800, 1795521600, 1795530000
    rows = [
        {"mode": "live", "bot": "atlas", "src": "acctb", "acct": "...1234", "side": "sell", "entry_t": T1, "entry": 27395.5, "stop": 27422.5,
         "target": 27000.0, "qty": 2, "result": {"ok": True, "legs": [{"filled": 2, "fill_px": 27391.75}]}},
        {"mode": "live", "bot": "atlas", "src": "acctb", "acct": "...1234", "side": "exit", "entry_t": T1, "exit_t": T1 + 900, "qty": 2,
         "reason": "STOP", "exit_px": 27422.75, "pnl": -112.8},
        {"mode": "live", "bot": "zlarior", "acct": "...5678", "side": "buy", "entry_t": T3, "entry": 27850.0, "stop": 27800.0, "qty": 2,
         "result": {"ok": False, "error": "rejected: max order quantity"}},
        {"mode": "live", "bot": "zlarior", "acct": "...5678", "side": "buy", "entry_t": T2, "entry": 27800.0, "stop": 27760.0,
         "target": 27900.0, "qty": 2, "result": {"ok": True, "legs": [{"filled": 2, "fill_px": 27800.25}]}},
        {"mode": "live", "bot": "zlarior", "acct": "...5678", "side": "exit", "entry_t": T2, "exit_t": T2 + 3000, "qty": 2, "reason": "TARGET",
         "exit_px": 27900.0, "pnl": 395.0},
    ]
    gzl(os.path.join(d, "trades.jsonl.gz"), rows)
    gzl(os.path.join(d, "fills.jsonl.gz"), [{"entry_t": T1, "fill_px": 27391.75, "filled": 2, "sent_s_after_open": 4.2}])
    with gzip.open(os.path.join(d, "twin.json.gz"), "wt", encoding="utf-8") as fh:
        json.dump({"day": "2026-11-18", "nightly": {"rows": [
            {"status": "extra", "entry_t": T2, "live_pnl": 395.0},
            {"status": "missed", "day": "2026-11-18", "entry_t": T3 + 7200, "bt_pnl": 250.0, "reason": "PC bot off"}]}}, fh)
    gzl(os.path.join(d, "decisions.jsonl.gz"), [])
    old = RL.DAY_DIRS
    RL.DAY_DIRS = (os.path.join(tmp, "days"),)
    try:
        res = L.run(now=1795600000, RL=RL)
    finally:
        RL.DAY_DIRS = old
    a, z = res["bots"]["ATLAS"], res["bots"]["LIT"]
    check("b1. ATLAS: the 15-tick late fill = -$15, flagged on slippage", a["n"] == 1 and a["gap"] == -15.0 and a["flag"]
          and "entry slippage +15.0 ticks avg" in a["line"], a["line"])
    check("b2. LIT: the refused entry + the twin's missed trade (-$250) + the extra trade the backtest did not take (+its real $)",
          z["missed"] == 2 and z["extra"] == 1 and z["flag"] and "2 missed" in z["line"] and "1 extra" in z["line"], z)
    return res


def part_c(res):
    from zoneinfo import ZoneInfo
    import datetime as dt
    ET = ZoneInfo("America/New_York")

    def t(y, m, d, h, mi):
        return int(dt.datetime(y, m, d, h, mi, tzinfo=ET).timestamp())
    p = L.pushes(t(2026, 11, 24, 16, 25), {}, res=res)
    check("c1. after 16:20 ET on a CME day: one push per flagged bot, the line as title", {x["key"] for x in p} ==
          {"lvb:ATLAS:2026-11-24", "lvb:LIT:2026-11-24"} and all(x["title"].startswith(("LIT live is", "ATLAS live is")) for x in p), p)
    check("c2. before 16:20: nothing", L.pushes(t(2026, 11, 24, 16, 10), {}, res=res) == [])
    check("c3. Saturday / Christmas (a full CME closure): nothing; Thanksgiving (a half day that traded): yes",
          L.pushes(t(2026, 11, 28, 17, 0), {}, res=res) == [] and L.pushes(t(2026, 12, 25, 17, 0), {}, res=res) == []
          and len(L.pushes(t(2026, 11, 26, 17, 0), {}, res=res)) == 2)
    sent = {x["key"]: 1 for x in p}
    check("c4. once a day (keys already sent: nothing)", L.pushes(t(2026, 11, 24, 18, 0), sent, res=res) == [])
    ok = {"bots": L.evaluate([tr("Zlarior", 1, -2.0)], [])}
    check("c5. nothing flagged: no push", L.pushes(t(2026, 11, 24, 16, 25), {}, res=ok) == [])


def part_d(tmp, res):
    p = os.path.join(tmp, "lvb.json")
    L.save({**res, "t": 1795600000}, p)
    check("d1. the brief reads the last saved check: one line", L.last_line(1795600000 + 3600, path=p).startswith("Live vs backtest: "))
    check("d2. older than 30 h: no line (never an old drift shown as today's)", L.last_line(1795600000 + 31 * 3600, path=p) == "")
    check("d2b. a check saved 'later' than the clock (a test's fake time): ignored", L.last(1795600000 - 3600, path=p) is None
          and L.last(1795600000 + 60, path=p) is not None)
    from tools import morning_brief as MB
    src = open(os.path.join(ROOT, "tools", "morning_brief.py"), encoding="utf-8").read()
    check("d3. the brief adds it as one line after the accounts and keeps <= 8 lines", "lines = [rl] + acc + ([lvb] if lvb else [])" in src
          and "MAX_LINES - 4 - (1 if lvb else 0)" in src and MB.MAX_LINES == 8)
    g = open(os.path.join(ROOT, "tools", "pc_guard.py"), encoding="utf-8").read()
    check("d4. pc_guard collects its pushes (inside a try)", "live_vs_bt.pushes(now, st[\"sent\"])" in g)


def part_e():
    src = open(os.path.join(ROOT, "engine", "live_vs_bt.py"), encoding="utf-8").read()
    check("e. read-only: no adapter, order, arm or route call", not any(w in src for w in ("place_bracket", "adapter", ".arm(", "route(", "write_oif")))


def main():
    tmp = tempfile.mkdtemp(prefix="lvb_")
    try:
        part_a()
        res = part_b(tmp)
        part_c(res)
        part_d(tmp, res)
        part_e()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nlive vs backtest: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
