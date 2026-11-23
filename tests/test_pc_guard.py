"""Eval guard pushes of the GitHub-free PC report (tools/pc_guard.py through tools/pc_report.py -> ntfy). Read-only alerts:
drawdown 50% / 75% per eval account, daily loss limit near, no trade for an unusual time, the 16:05 ET day summary with $ per
account. Fake snapshots and the real board builder (engine/live_publish.build on the test heartbeat), fake HTTP, temp
folders; never the network, never an order.

  python -X utf8 -m tests.test_pc_guard
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ["LE_PR_NO_NET"] = "1"

from engine.ninjatrader import ET  # noqa: E402
from tools import pc_guard as G  # noqa: E402

RES: list = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:700]})" if info and not cond else ""))
    return bool(cond)


def at(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def lit(**kw):
    c = {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "status": "open", "balance": 50000.0,
         "floor": 48000.0, "room": 2000.0, "mll": 2000.0, "today_pnl": 0.0, "dll": 1000.0, "dll_used": 0.0, "trades_today": 0,
         "quiet_days": 1, "eval_start": "2026-11-02", "to_target": 3000.0, "position": None}
    c.update(kw)
    return c


def atlas(**kw):
    c = {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "badge": "SIM", "configured": True, "status": "open", "balance": 25000.0,
         "floor": 24000.0, "room": 1000.0, "mll": 1000.0, "today_pnl": 0.0, "dll": 600.0, "trades_today": 0, "quiet_days": 0,
         "eval_start": "2026-11-05", "to_target": 1500.0, "position": None}
    c.update(kw)
    return c


def snap(now, cards, hb_age=60, mode="LIVE"):
    return {"t": now, "hb_age": hb_age, "mode": mode, "live": {"board": cards}}


def run(state, s):
    return G.guard(state, s, roll_state={})


def keys(msgs):
    return [m["key"] for m in msgs]


# ============================================================================================== drawdown, daily loss, quiet
def accounts():
    t = at(2026, 11, 16, 10)
    _s, m = run({}, snap(t, {"lit": lit(room=1100.0)}))
    check("45% used (room $1,100 of $2,000): nothing yet", m == [], m)
    st, m = run({}, snap(t, {"lit": lit(room=900.0), "atlas": atlas()}))
    check("50% of the drawdown used (room $900 of $2,000 = 55%): one push for Zlarior, ATLAS untouched",
          keys(m) == ["guard:dd:lit:2026-11-02:50"] and "55% of the drawdown used" in m[0]["body"] and "$900 of $2,000" in m[0]["body"]
          and m[0]["title"] == "Zlarior 50K: 50% of the room used, $900 left" and "real account" in m[0]["body"], m)
    st, m = run(st, snap(t + 900, {"lit": lit(room=1000.0), "atlas": atlas()}))
    check("not again 15 minutes later", m == [], m)
    st, m = run(st, snap(t + 1800, {"lit": lit(room=480.0), "atlas": atlas()}))
    check("75%: its own push, high priority, 'room getting low, $480 left of $2,000'", keys(m) == ["guard:dd:lit:2026-11-02:75"] and m[0]["priority"] == "high"
          and m[0]["title"] == "Zlarior 50K: room getting low, $480 left of $2,000", m)
    st, m = run(st, snap(t + 2700, {"lit": lit(room=1900.0), "atlas": atlas()}))
    check("back to 5% used: nothing pushed, both levels re-armed", m == [] and not [k for k in st["sent"] if ":dd:lit:" in k], st)
    st, m = run(st, snap(t + 3600, {"lit": lit(room=900.0), "atlas": atlas()}))
    check("crossing 50% again after a recovery pushes again", keys(m) == ["guard:dd:lit:2026-11-02:50"], m)
    _s, m = run({}, snap(t, {"lit": lit(room=300.0)}))
    check("0 -> 85% at once: one push (the 75%), the 50% counted as said", keys(m) == ["guard:dd:lit:2026-11-02:75"]
          and "guard:dd:lit:2026-11-02:50" in _s["sent"], (m, _s))
    _s, m = run(st, snap(t + 4500, {"lit": lit(room=900.0, eval_start="2026-11-20")}))
    check("a new eval (new start) has its own levels", keys(m) == ["guard:dd:lit:2026-11-20:50"], m)
    _s, m = run({}, snap(t, {"lit": lit(room=300.0, status="failed")}))
    check("an eval already failed / passed: no drawdown push", m == [], m)
    _s, m = run({}, snap(t, {"lit": lit(room=300.0)}, hb_age=3600))
    check("an old heartbeat (1 h): no account push (numbers too old; pc_report already says bot down)", m == [], m)
    _s, m = run({}, snap(t, {"atlas": atlas(room=400.0)}, mode="paper"))
    check("ATLAS on Sim: its push says Sim / paper and 25K", keys(m) == ["guard:dd:atlas:2026-11-05:50"] and "Sim / paper" in m[0]["body"]
          and m[0]["title"].startswith("ATLAS 25K"), m)
    _s, m = run({}, snap(t, {"atlas": atlas(room=400.0, configured=False, status="not set up")}))
    check("an account not set up: nothing", m == [], m)
    # ---- daily loss
    _s, m = run({}, snap(t, {"lit": lit(today_pnl=-720.0, room=1280.0)}))
    k = [x for x in m if ":dll:" in x["key"]]
    check("daily loss $720 of $1,000 (72%): 'daily loss limit near', high, once a trading day",
          [x["key"] for x in k] == ["guard:dll:lit:2026-11-16"] and k[0]["priority"] == "high" and "72%" in k[0]["title"], m)
    _s, m = run({}, snap(t, {"lit": lit(today_pnl=-300.0, position={"side": "LONG", "unrealized_usd": -450.0})}))
    k = [x for x in m if ":dll:" in x["key"]]
    check("realized -$300 + an open trade at -$450 = $750: near, the open trade named", k and "$450 of it in the open trade" in k[0]["body"], m)
    _s, m = run({}, snap(t, {"lit": lit(today_pnl=-650.0)}))
    check("65%: not yet", not [x for x in m if ":dll:" in x["key"]], m)
    _s, m = run({}, snap(t, {"atlas": atlas(today_pnl=-430.0)}))
    check("ATLAS: $430 of its $600 limit (72%) -> near", [x["key"] for x in m if ":dll:" in x["key"]] == ["guard:dll:atlas:2026-11-16"], m)
    # ---- quiet bot
    _s, m = run({}, snap(t, {"lit": lit(quiet_days=5)}))
    k = [x for x in m if ":quiet:" in x["key"]]
    check("no trade for 5 days on the real eval: pushed, names MFFU's 7-day rule", k and "MFFU can close an eval after 7 days" in k[0]["body"]
          and k[0]["priority"] == "default", m)
    _s, m = run({}, snap(t, {"lit": lit(quiet_days=6)}))
    check("6 days on the real eval: high priority (tomorrow is day 7)", [x["priority"] for x in m if ":quiet:" in x["key"]] == ["high"], m)
    check("6+ days on the real eval: says check MFFU and place 1 MNQ by hand (5 days: not yet)",
          all("place 1 MNQ by hand" in x["body"] for x in m if ":quiet:" in x["key"])
          and not any("by hand" in x["body"] for x in run({}, snap(t, {"lit": lit(quiet_days=5)}))[1] if ":quiet:" in x["key"]), m)
    _s, m = run({}, snap(t, {"lit": lit(quiet_days=4)}))
    check("4 days: nothing (a long weekend is normal)", not [x for x in m if ":quiet:" in x["key"]], m)
    _s, m = run({}, snap(t, {"atlas": atlas(quiet_days=8)}, mode="paper"))
    k = [x for x in m if ":quiet:" in x["key"]]
    check("ATLAS on Sim, 8 days: pushed without the MFFU sentence", k and "MFFU" not in k[0]["body"], m)
    _s, m = run({}, snap(t, {"lit": lit(quiet_days=9, position={"side": "LONG"})}))
    check("in a trade: no quiet push", not [x for x in m if ":quiet:" in x["key"]], m)
    # ---- quiet hours
    night = at(2026, 11, 17, 3, 10)
    _s, m = run({}, snap(night, {"lit": lit(room=900.0, quiet_days=6)}))
    check("03:10 ET: the 50% push and the quiet push wait for 07:00 (not marked sent)", m == [] and not _s["sent"], (m, _s))
    _s, m = run({}, snap(night, {"lit": lit(room=300.0, today_pnl=-800.0)}))
    check("03:10 ET: 75% and daily loss near go out at once (high)", sorted(keys(m)) == ["guard:dd:lit:2026-11-02:75", "guard:dll:lit:2026-11-17"], m)


# ============================================================================================== extra accounts (7-day rule)
def sub_block(now, ident="b25k_2", name="Zlarior Builder 25K #2", plan="MFFU Builder 25K", start="2026-11-10", closes=(),
              label="LIVE", kind="eval", position=None, nt="MFFUEVBLDR000002222"):
    """an engine/multi_account.AccountRouter.summary row (heartbeat acct.accounts): the 25K #2 / the Rapid's LIT lane"""
    trades = [{"day": d, "exit_t": int(now) - 86400 * 3, "pnl": p} for d, p in closes]
    days = {}
    for d, p in closes:
        days[d] = days.get(d, 0.0) + p
    return {"v": 1, "id": ident, "name": name, "firm": "MFFU", "plan": plan, "kind": kind, "mode": kind,
            "account": {"name": nt, "adapter": "ninjatrader", "kind": label.lower(), "label": "LIVE ACCOUNT" if label == "LIVE" else label,
                        "disabled": ""},
            "enabled": True, "locked": None, "running": True, "kill": False, "position": position, "orders": [], "trades": trades,
            "eval": {"start": start, "days": days},
            "plan_rules": {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "lock": 25100.0, "dll": 500.0, "sessions": 10},
            "day_pnl": 0.0, "size": None,
            **({"funded": {"start": start, "preset": "x", "payouts": {}}} if kind == "funded" else {})}


def extras():
    """round-2 skeptics 2026-11-20 (HIGH): the 7-day alert covered only the board's cards (the 50K, ATLAS, BLITZ). The 25K #2 eval
    ('no trade yet') and the Rapid EOD had none, while the docs promised 'no trade for 5+ days on an account'. Now each extra account
    of the heartbeat (acct.accounts, through the REAL live view: engine/live_publish.build) gets its own once-a-day alert."""
    from engine import live_publish
    from tests.test_live_publish import hb_payload
    t = at(2026, 11, 16, 10, 0)                 # Monday: the 25K #2's eval started Tue Nov 10, no trade since = 6 days
    hb = hb_payload(t - 60, position=False)
    hb["acct"]["trades"][-1]["day"] = "2026-11-16"
    hb["acct"]["accounts"] = [sub_block(t), sub_block(t, ident="rapid", name="Rapid EOD 25K", plan="MFFU Rapid EOD 25K",
                                                      start="2026-11-09", closes=[("2026-11-13", 42.0)], nt="MFFUEVRPD000005555")]
    L = live_publish.build(hb, now=t)
    secs = [a for a in L.get("accounts") or [] if a.get("extra")]
    s0 = {"t": t, "hb_age": 60, "mode": "LIVE", "live": {**L, "board": {"lit": lit(quiet_days=0)}}}
    _s, m = run({}, s0)
    q = [x for x in m if ":quiet:" in x["key"]]
    check("extra accounts reach the guard through the real live view (2 sections, extra=True)", len(secs) == 2, [a.get("id") for a in secs])
    check("the 25K #2, no trade since its eval start 6 days ago: 'Zlarior 25K #2: no trade for 6 days', high, MFFU's 7-day rule, "
          "place 1 MNQ by hand (before: no alert at all)",
          [x["key"] for x in q] == ["guard:quiet:b25k_2:2026-11-16"] and q[0]["title"] == "Zlarior 25K #2: no trade for 6 days"
          and q[0]["priority"] == "high" and "MFFU can close an eval after 7 days" in q[0]["body"] and "place 1 MNQ by hand" in q[0]["body"]
          and "only the bot's own trades" in q[0]["body"], q)
    check("no account id in the alert (title, body, key)", not re.search(r"MFFU[A-Z]*\d|2222|5555", json.dumps(q)), q)
    check("the Rapid traded 3 days ago (Fri, its P&L days count both lanes): no alert", not [x for x in q if ":rapid:" in x["key"]], q)
    _s2, m2 = run(_s, s0)
    check("once a day: the next run repeats nothing", not [x for x in m2 if ":quiet:" in x["key"]], m2)
    # the Rapid quiet too (Fri Nov 6 last), funded: the funded words
    hb["acct"]["accounts"] = [sub_block(t, ident="rapid", name="Rapid EOD 25K", plan="MFFU Rapid EOD 25K", start="2026-11-02",
                                        closes=[("2026-11-10", 42.0)], nt="MFFUSFRPD000005555", kind="funded")]
    L = live_publish.build(hb, now=t)
    _s, m = run({}, {"t": t, "hb_age": 60, "mode": "LIVE", "live": {**L, "board": {"lit": lit(quiet_days=0)}}})
    q = [x for x in m if ":quiet:" in x["key"]]
    check("a funded extra account 6 days quiet: 'MFFU can close a funded account after 7 days ... loses ALL its profits'",
          len(q) == 1 and q[0]["title"].startswith("Rapid EOD 25K") and "funded account after 7 days" in q[0]["body"]
          and "ALL its profits" in q[0]["body"], q)
    for why, sb in (("on Sim", sub_block(t, label="SIM", nt="Sim101")), ("in a trade", sub_block(t, position={"side": "LONG", "entry_t": t - 60})),
                    ("4 days only", sub_block(t, start="2026-11-12"))):
        hb["acct"]["accounts"] = [sb]
        L = live_publish.build(hb, now=t)
        _s, m = run({}, {"t": t, "hb_age": 60, "mode": "LIVE", "live": {**L, "board": {"lit": lit(quiet_days=0)}}})
        check(f"extra account {why}: no quiet alert", not [x for x in m if ":quiet:" in x["key"]], m)
    hb["acct"]["accounts"] = [sub_block(t)]
    L = live_publish.build(hb, now=t)
    for st_ in ("passed", "failed"):
        L2 = copy.deepcopy(L)
        for a in L2["accounts"]:
            if a.get("extra"):
                a["eval"]["status"] = st_
        _s, m = run({}, {"t": t, "hb_age": 60, "mode": "LIVE", "live": {**L2, "board": {"lit": lit(quiet_days=0)}}})
        check(f"extra eval {st_} (its eval clock): no quiet alert", not [x for x in m if ":quiet:" in x["key"]], m)
    night = at(2026, 11, 17, 3, 10)
    _s, m = run({}, {"t": night, "hb_age": 60, "mode": "LIVE", "live": {**L, "board": {"lit": lit(quiet_days=0)}}})
    check("03:10 ET: the extra account's alert waits for the day (never in quiet hours)", not [x for x in m if ":quiet:" in x["key"]], m)
    from engine import notify as N
    check("the alert's kind is account_status (on by default, both apps)", N.kind_of("guard:quiet:b25k_2:2026-11-16") == "account_status"
          and N.on("account_status", N.merge({})))
    # ATLAS's funded card: the funded words too (round-2 skeptic: 'MFFU can close an eval' was wrong for a funded account)
    _s, m = run({}, snap(t, {"atlas": atlas(quiet_days=6, badge="LIVE", real=True, stage="funded")}))
    q = [x for x in m if ":quiet:" in x["key"]]
    check("ATLAS funded, 6 days: 'MFFU can close a funded account after 7 days ... ALL its profits' (not 'an eval')",
          q and "funded account after 7 days" in q[0]["body"] and "ALL its profits" in q[0]["body"] and "close an eval" not in q[0]["body"], q)


# ============================================================================================== day summary
def summary():
    day = at(2026, 11, 16, 16, 20)          # Monday, after the 16:15 summary time
    cards = {"lit": lit(today_pnl=420.0, trades_today=1, room=1800.0), "atlas": atlas(today_pnl=-110.0, trades_today=2, room=890.0)}
    st, m = run({}, snap(day, cards))
    d = [x for x in m if ":day:" in x["key"]]
    check("16:20 ET Monday: one day summary, total +$310, $ today / $ to pass / room per account, tomorrow's news",
          [x["key"] for x in d] == ["guard:day:2026-11-16"] and d[0]["title"] == "Day Mon Nov 16: +$310"
          and "Zlarior 50K: +$420 today, $3,000 to pass, room $1,800 of $2,000" in d[0]["body"]
          and "ATLAS 25K: -$110 today, $1,500 to pass, room $890 of $1,000" in d[0]["body"] and "(Sim / paper)" in d[0]["body"]
          and "Tomorrow (Tue):" in d[0]["body"], d)
    _s, m = run(st, snap(day + 900, cards))
    check("once a day", not [x for x in m if ":day:" in x["key"]], m)
    for label, t in (("15:55 ET", at(2026, 11, 16, 15, 55)), ("16:10 ET (before 16:15)", at(2026, 11, 16, 16, 10)), ("17:02 ET (CME break: too late)", at(2026, 11, 16, 17, 2)), ("Saturday", at(2026, 11, 21, 16, 10)),
                     ("Christmas Day (CME closed)", at(2026, 12, 25, 16, 10))):
        _s, m = run({}, snap(t, cards))
        check(f"no summary at {label}", not [x for x in m if ":day:" in x["key"]], (label, m))
    _s, m = run({}, snap(day, cards, hb_age=7200))
    d = [x for x in m if ":day:" in x["key"]]
    check("an old heartbeat: the summary still comes, marked 'last report old' with its age", d and "(last report old)" in d[0]["title"]
          and "120 min ago" in d[0]["body"], d)
    _s, m = run({}, {"t": day, "hb_age": None, "live": None})
    d = [x for x in m if ":day:" in x["key"]]
    check("no report at all: 'no numbers', tools/bat/STATUS.bat named", d and "no numbers" in d[0]["title"] and "tools/bat/STATUS.bat" in d[0]["body"], d)
    check("guard never raises on junk", run({"sent": None}, {"t": day, "live": {"board": {"lit": "x", "atlas": 5}}, "hb_age": 1})[1] is not None)


# ============================================================================================== through pc_report + the real board
def reporter():
    from tests.test_bots_back import Box, FakeHTTP
    from tests.test_live_publish import account_c_block, hb_payload
    from engine import roll_watch
    from engine import hidden_bots
    real_fact = roll_watch.fact
    roll_watch.fact = lambda *a, **k: {}
    hidden_bots.FORCE = ()                 # BLITZ shown (dashboard_view.json hides it since owner 2026-11-15): this part tests the BLITZ guard logic
    from engine import notify as _N
    real_settings = _N.settings            # every type on: this part tests the guard's pushes (the owner's defaults: "important only")
    _N.settings = lambda path=None: _N.merge({"alerts": {k: True for k in _N.TYPES}})
    b = Box()
    try:
        cfg = b.topic()
        now = at(2026, 11, 16, 15, 0)
        hb = hb_payload(now - 60, position=False)
        hb["acct"]["trades"][-1]["day"] = "2026-11-16"
        hb["account_c"] = account_c_block(now)
        b.hb(hb)
        h = FakeHTTP()
        b.run(h, now)
        check("reporter: first run records only (no guard push)", not h.posts(cfg["topic"]), [c["h"] for c in h.posts()])
        hb2 = copy.deepcopy(hb)
        hb2["t"] = now + 4800 - 60
        hb2["account_c"]["eval"].update(room=420.0, balance=24730.0, floor=24310.0, today=-580.0)
        hb2["account_c"]["day_pnl"] = -430.0
        b.hb(hb2)
        h = FakeHTTP()
        b.run(h, now + 4800)                   # 16:20 ET
        titles = [c["h"].get("Title", "") for c in h.posts(cfg["topic"])]
        bodies = {c["h"].get("Title", ""): c["body"] for c in h.posts(cfg["topic"])}
        check("reporter at 16:20 ET: BLITZ 58% drawdown, its daily loss near ($430 of $600) and the day summary, from the real board",
              any(t.startswith("BLITZ 25K: 50% of the room used") for t in titles) and any(t.startswith("BLITZ 25K: daily loss limit near") for t in titles)
              and any(t.startswith("Day Mon Nov 16:") for t in titles), titles)
        day = next(v for k, v in bodies.items() if k.startswith("Day "))
        check("day summary names Zlarior and BLITZ with $ today and the room left", "Zlarior 50K:" in day and "BLITZ 25K: -$430 today" in day
              and "room $420 of $1,000" in day, day)
        check("every push title is ASCII (HTTP header)", all(all(ord(ch) < 128 for ch in t) for t in titles), titles)
        h = FakeHTTP()
        b.run(h, now + 5700)
        check("reporter: nothing repeated on the next run", not [c for c in h.posts(cfg["topic"]) if "guard" in c["body"] or "drawdown" in c["body"]],
              [c["h"] for c in h.posts(cfg["topic"])])
        state = json.load(open(os.path.join(b.work, "state.json"), encoding="utf-8"))
        check("guard keys kept in data/pc_report/state.json", "guard:day:2026-11-16" in state["guard"]["sent"], state.get("guard"))
    finally:
        roll_watch.fact = real_fact
        hidden_bots.FORCE = None
        _N.settings = real_settings
        b.cleanup()
    kept = [m["key"] for m in _N.apply([{"key": "guard:dd:c:x:50"}, {"key": "guard:dll:c:d"}, {"key": "guard:day:2026-11-16"}],
                                       at(2026, 11, 16, 16, 20), _N.merge({}))]
    check("defaults: drawdown 50%, daily loss near and the day summary are all pushed (room low ON since night-notify 2026-11-22)",
          kept == ["guard:dd:c:x:50", "guard:dll:c:d", "guard:day:2026-11-16"], kept)


def static():
    src = open(os.path.join(ROOT, "tools", "pc_guard.py"), encoding="utf-8").read()
    body = src.split('"""', 2)[-1]
    check("pc_guard.py: read-only (no open(..., 'w'), no order line, no HTTP of its own, no live_model, no arming)",
          not re.search(r"open\([^)]*['\"]w|PLACE;|place_line|CLOSEPOSITION|urllib|requests|live_model|LIVE_PHRASE|/api/live", body))


def main() -> int:
    accounts()
    extras()
    summary()
    reporter()
    static()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


def test_pc_guard():                       # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
