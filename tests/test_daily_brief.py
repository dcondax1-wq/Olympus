"""ONE daily phone brief (night-brief 2026-11-23): the 07:30 ET morning brief (tools/morning_brief.py, upgraded) and ONE evening
message (tools/pc_guard.day_summary + the payouts ready, the next money move and the day's low-priority lines). Fakes only.

  a. content: READY / NOT READY first, one line per account, Today (hours, news, the T1 ban, early close), the next money move,
     needs you + decide cards waiting; at most 8 lines even with many accounts; no long id; $ first
  b. the 7-day deadline shows at 3 days or fewer (not at 4), hidden when the running bot's keep-alive covers it
  c. yesterday's $ = the previous CME session (a Monday reads Friday)
  d. holidays: no brief on Christmas / a weekend; Thanksgiving (13:00 halt) still briefs with the early close
  e. size: the push fits ntfy (< 4,096 bytes) and a phone (<= 8 lines)
  f. evening: ONE message: the day summary carries the payouts ready, "Do not take payout #5", "Tomorrow: <next move>" and the
     digest's lines; the 16:20 digest then sends nothing on a trading day (on a Saturday it still does)
  g. de-dup: the brief once a day (guard:brief:<day>), the digest lines carried once
  v. night-briefv2: the PUSHED brief is 5 lines, money first (yesterday $ per account, room to max loss, keep-alive act days,
     news blackout, bot armed / READY); a-e test the detailed build_full
    python -X utf8 -m tests.test_daily_brief
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import morning_brief as MB  # noqa: E402

ET = ZoneInfo("America/New_York")
RES: list = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:500]}]" if detail and not ok else ""))


def ts(y, m, d, h, mi=0):
    return int(dt.datetime(y, m, d, h, mi, tzinfo=ET).timestamp())


def row(key, name, plan, bal, stage="eval", to_pass=None, room=1000.0, badge="LIVE", quiet=None, cover=False, funded=None):
    src = {"badge": badge, "room": room, "quiet_days": quiet, "keepalive": {"cover": cover}}
    if funded is not None:
        src["funded"] = funded
    return {"key": key, "name": name, "plan": plan, "balance": bal, "stage": stage, "to_pass": to_pass, "_src": src}


ROWS = [row("zlarior", "Zlarior", "MFFU Builder 50K", 49213.9, to_pass=3786.1, room=1045.7),
        row("fresh25", "Zlarior 25K #2", "MFFU Builder 25K", 25023.62, to_pass=1476.38, quiet=5),
        row("atlas", "ATLAS", "MFFU Builder 25K", 25401.38, stage="funded", funded={"to_ask": 1698.62, "ready": False}),
        row("rapid1", "Rapid EOD 25K", "MFFU Rapid EOD 25K", 25000.0, to_pass=1500.0, quiet=4)]


def build(now, rows=None, snap=None, **kw):
    keep = MB.rows, MB._trades
    MB.rows = lambda s, n, p=None, e=None: list(ROWS if rows is None else rows)
    if "trades" in kw:
        tr = kw.pop("trades")
        MB._trades = lambda s, n, rs, p, t0: (tr(t0, n), [], lambda k: k)
    try:
        s = {"t": now, "hb_age": 120, "cond": {}, "rd": {"s": "ok", "w": "02:00"}, "eh": {"z": ["G"], "a": ["G"]}}
        s.update(snap or {})
        return MB.build_full(s, now, plan_doc={"accounts": []}, events=[], root=os.path.join(ROOT, "no-news"),
                        fleet=kw.get("fleet", "decide the Rapid EOD 50K card first"), waiting=kw.get("waiting", 4))
    finally:
        MB.rows, MB._trades = keep


def part_a():
    tue = ts(2026, 11, 24, 7, 31)
    b = build(tue)
    L = b["lines"]
    check("a. line 1 = READY for 02:00", L[0].startswith("READY for 02:00"), L)
    check("a. one line per account, $ first after the name", L[1].startswith("Zlarior 50K armed · $49,214 · room $1,046 · $3,786 to pass")
          and L[3].startswith("ATLAS 25K armed · $25,401") and "$1,699 to payout" in L[3] and L[4].startswith("Rapid EOD 25K"), L)
    check("a. Today: the hours", any(x.startswith("Today: Zlarior till 15:30") for x in L), L)
    check("a. the next money move", "Next money move: decide the Rapid EOD 50K card first" in L, L)
    check("a. last: needs you + decide cards waiting", L[-1].endswith("Decide cards waiting: 4"), L[-1])
    check("a. <= 8 lines", len(L) <= 8, len(L))
    many = ROWS + [row(f"x{i}", f"Extra {i}", "MFFU Builder 25K", 25000.0, to_pass=1500.0) for i in range(5)]
    bm = build(tue, rows=many)
    check("a. 9 accounts: still <= 8 lines, the rest named in one line", len(bm["lines"]) <= 8
          and any("more accounts: TRADE_HOME -> 1" in x for x in bm["lines"]), bm["lines"])
    b2 = build(tue, rows=[row("odd", "EVBLDR987654321", "MFFU Builder 25K", 25000.0, to_pass=1500.0)])
    check("a. no long account id in the brief", "987654321" not in b2["body"], b2["body"])
    nr = build(tue, snap={"rd": {"s": "no", "w": "02:00", "b": "Zlarior 50K is not armed", "f": "START BOT and type the phrase"}})
    check("a. NOT READY: the blocker + its fix on line 1, NOT READY in the title", nr["lines"][0] ==
          "NOT READY for 02:00: Zlarior 50K is not armed. Fix: START BOT and type the phrase" and nr["title"].endswith("NOT READY"), nr["lines"][0])
    na = build(tue, rows=[row("z", "Zlarior", "MFFU Builder 50K", 49000.0, to_pass=4000.0, badge="PAPER")])
    check("a. an account not armed says so", "Zlarior 50K NOT armed (paper)" in na["lines"][1], na["lines"][1])
    pr = build(tue, rows=[row("atlas", "ATLAS", "MFFU Builder 25K", 27100.0, stage="funded", funded={"ready": True, "max_request": 1000.0})])
    check("a. a payout ready: on its line and under needs you", "payout READY $1,000" in pr["lines"][1]
          and "request the ATLAS 25K payout $1,000" in pr["lines"][-1], pr["lines"])


def part_b():
    L = build(ts(2026, 11, 24, 7, 31))["lines"]
    check("b. 5 quiet days (2 left): 'MFFU 7-day: trade within 2 day(s)'", "MFFU 7-day: trade within 2 day(s)" in L[2], L[2])
    check("b. 4 quiet days (3 left): shown", "MFFU 7-day: trade within 3 day(s)" in L[4], L[4])
    L2 = build(ts(2026, 11, 24, 7, 31), rows=[row("z", "Zlarior", "MFFU Builder 50K", 49000.0, quiet=3)])["lines"]
    check("b. 3 quiet days (4 left): not shown", "7-day" not in L2[1], L2[1])
    L3 = build(ts(2026, 11, 24, 7, 31), rows=[row("z", "Zlarior", "MFFU Builder 50K", 49000.0, quiet=6, cover=True)])["lines"]
    check("b. the running bot's keep-alive covers it: hidden", "7-day" not in L3[1], L3[1])
    L4 = build(ts(2026, 11, 24, 7, 31), rows=[row("z", "Zlarior", "MFFU Builder 50K", 49000.0, quiet=6)])["lines"]
    check("b. 6 quiet days: shown + 'by hand' under needs you", "trade within 1 day(s)" in L4[1] and "1 MNQ by hand" in L4[-1], L4)


def part_c():
    mon = ts(2026, 11, 30, 7, 31)
    t0, t1 = MB.prev_session(mon)
    e0, e1 = dt.datetime.fromtimestamp(t0, ET), dt.datetime.fromtimestamp(t1, ET)
    check("c. Monday's 'yesterday' = Friday's session (Thu 18:00 -> Fri 17:00)", (e0.strftime("%a %H:%M"), e1.strftime("%a %H:%M")) ==
          ("Thu 18:00", "Fri 17:00"), (e0, e1))
    b = build(mon, trades=lambda t0_, t1_: {"zlarior": (2, 412.5)} if t0_ == t0 else {})
    check("c. yesterday's $ on the account line", "yesterday +$412 (2 trades)" in b["lines"][1] or "yesterday +$413 (2 trades)" in b["lines"][1], b["lines"][1])


def part_d():
    check("d. Christmas: no brief", not MB.due(ts(2026, 12, 25, 7, 35)))
    check("d. Saturday: no brief", not MB.due(ts(2026, 11, 28, 7, 35)))
    check("d. Thanksgiving (13:00 halt): still a brief", MB.due(ts(2026, 11, 26, 7, 35)))
    tg = build(ts(2026, 11, 26, 7, 35))
    check("d. ... with the early close said", any("early close 13:00" in x for x in tg["lines"]), tg["lines"])


def part_e():
    b = build(ts(2026, 11, 24, 7, 31), rows=ROWS * 2)
    size = len((b["title"] + "\n" + b["body"]).encode("utf-8"))
    check("e. fits ntfy (< 4,096 bytes) and <= 8 lines", size < 4096 and len(b["body"].split("\n")) <= 8, size)
    old = build(ts(2026, 11, 24, 7, 31), snap={"hb_age": 3 * 3600 + 600})
    check("rt2. a 3 h old report: every account line says how old its numbers are (and the brief says NOT READY)",
          old["lines"][0].startswith("NOT READY") and all("as of 3 h 10 min ago" in x for x in old["lines"][1:5]), old["lines"])
    check("rt2. a fresh report: no age tail", not any("as of" in x for x in build(ts(2026, 11, 24, 7, 31))["lines"]))
    big = build(ts(2026, 11, 24, 7, 31), snap={"rd": {"s": "no", "b": "x" * 5000, "f": "y" * 5000}})
    check("rt2. a huge blocker text still fits (<= 8 lines, < 4,096 B)", len(big["body"].encode()) < 4096
          and len(big["body"].split("\n")) <= 8, len(big["body"]))


def part_f():
    from engine import alert_bus as AB
    from tools import pc_guard as G
    tmp = tempfile.mkdtemp()
    try:
        pa = os.path.join(tmp, "pa.json")
        json.dump({"last": {"t": int(time.time()), "views": [{"name": "ATLAS 25K", "ready": True, "amount": 1000.0},
                                      {"name": "Zlarior 25K #2", "ready": False, "guard": "stop"}]}}, open(pa, "w"))
        old = os.path.join(tmp, "pa_old.json")
        json.dump({"last": {"t": int(time.time()) - 3 * 86400, "views": [{"name": "ATLAS 25K", "ready": True, "amount": 1000.0}]}},
                  open(old, "w"))
        check("rt2. an autopilot run 3 days old: no 'Payout ready' in the evening (no stale payout shown as today's)",
              "Payout ready" not in G.evening_extra("2026-11-24", pa_path=old, digest_path=os.path.join(tmp, "d0.json"), fleet=""))
        dg = os.path.join(tmp, "digest.json")
        AB.digest_add("Update applied", "a1 -> b2", key="u:1", path=dg)
        ex = G.evening_extra("2026-11-24", pa_path=pa, digest_path=dg, fleet="buy a Rapid EOD 50K ($165 with CLUB)")
        check("f. the evening message adds: payout ready $, the #5 stop, Tomorrow: <next move>, Also: <digest line>",
              "Payout ready: ATLAS 25K $1,000" in ex and "Do not take payout #5 on Zlarior 25K #2" in ex
              and "Tomorrow: buy a Rapid EOD 50K ($165 with CLUB)" in ex and "Also: Update applied: a1 -> b2" in ex, ex)
        tue_eve = ts(2026, 11, 24, 16, 25)
        r = AB.digest_flush(now=tue_eve, path=dg, cfg={"telegram": None, "discord": None, "ntfy": False, "webpush": False})
        check("f. a trading day: the 16:20 digest sends nothing (the day summary carried it): ONE evening message",
              r == "in the day summary" and not AB._state(dg).get("items"), (r, AB._state(dg)))
        ex2 = G.evening_extra("2026-11-25", pa_path=os.path.join(tmp, "none.json"), digest_path=dg, fleet="")
        check("g. the digest line is carried once (not again the next evening)", "Also:" not in ex2, ex2)
        AB.digest_add("Update skipped", "local changes", key="u:2", path=dg)
        sat = ts(2026, 11, 28, 16, 25)
        sent = []
        keep = AB.send_critical
        AB.send_critical = lambda ev, **k: (sent.append(ev), "sent")[1]
        try:
            r2 = AB.digest_flush(now=sat, path=dg)
        finally:
            AB.send_critical = keep
        check("f. Saturday (no day summary): the digest still sends its one silent post", r2 == "sent" and sent and sent[0].get("silent"), (r2, sent))
        AB.digest_add("Late line", "after the summary", key="u:3", path=dg)
        key = "guard:day:2026-11-24"
        check("g. after the day summary went out: no rebuild, a later line is not marked shown (it waits for tomorrow)",
              G.day_summary({"t": ts(2026, 11, 24, 16, 45)}, ts(2026, 11, 24, 16, 45), {key: 1}) == []
              and any(i.get("key") == "u:3" and not i.get("shown") for i in AB._state(dg).get("items") or []))
        src = open(os.path.join(ROOT, "tools", "pc_guard.py"), encoding="utf-8").read()
        check("f. the day summary's body carries evening_extra", "news + evening_extra(" in src)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def five(now, rows=None, snap=None, trades=None, lvb=None):
    keep = MB.rows, MB._trades, MB.build_full
    MB.rows = lambda s, n, p=None, e=None: list(ROWS if rows is None else rows)
    if trades is not None:
        MB._trades = lambda s, n, rs, p, t0: (trades(t0, n), [], lambda k: k)
    try:
        s = {"t": now, "hb_age": 120, "cond": {}, "rd": {"s": "ok", "w": "02:00"}, "eh": {"z": ["G"], "a": ["G"]}}
        s.update(snap or {})
        return MB.build(s, now, plan_doc={"accounts": []}, events=[], root=os.path.join(ROOT, "no-news"), lvb={} if lvb is None else lvb)
    finally:
        MB.rows, MB._trades, MB.build_full = keep


def part_v2():
    """night-briefv2: the pushed brief = the day in 5 lines, money first."""
    tue = ts(2026, 11, 24, 7, 31)
    t0, _ = MB.prev_session(tue)
    b = five(tue, trades=lambda a, n: {"zlarior": (1, 300.0), "atlas": (2, -120.4)} if a == t0 else {})
    L = b["lines"]
    check("v1. exactly 5 lines: Yesterday / Room / Keep-alive / News / Bot, money first", len(L) == 5
          and [x.split(":")[0] for x in L] == ["Yesterday", "Room to max loss", "Keep-alive today", "News", "Bot"], L)
    check("v2. yesterday's $ per account + the total (the previous CME session); the title carries the total",
          L[0] == "Yesterday: Zlarior 50K +$300 · Zlarior 25K #2 +$0 · ATLAS 25K -$120 · Rapid EOD 25K +$0 · total +$180"
          and b["title"].endswith("READY - +$180 yesterday"), (L[0], b["title"]))
    low = [row("z", "Zlarior", "MFFU Builder 50K", 49000.0, room=1045.7), row("a", "ATLAS", "MFFU Builder 25K", 25300.0, stage="funded", room=310.0)]
    L = five(tue, rows=low)["lines"]
    check("v3. room in $ per account, lowest first, under $500 marked LOW", L[1] == "Room to max loss: ATLAS 25K $310 LOW · Zlarior 50K $1,046", L[1])
    ka = [row("z", "Zlarior", "MFFU Builder 50K", 49000.0, quiet=6), row("r", "Rapid EOD", "MFFU Rapid EOD 25K", 25000.0, quiet=6),
          row("q", "Zlarior 25K #2", "MFFU Builder 25K", 25000.0, quiet=3)]
    ka[0]["_src"]["keepalive"]["on"] = True
    L = five(tue, rows=ka)["lines"]
    check("v4. keep-alive act day today: ON = its window, OFF = 1 MNQ by hand; an account 3 days quiet is not due",
          L[2] == "Keep-alive today: Zlarior 50K (keep-alive trades 15:33-15:48 ET) · Rapid EOD 25K (keep-alive OFF: 1 MNQ by hand before 16:05 ET)",
          L[2])
    check("v5. nobody due: 'no account is due'", five(tue, rows=low)["lines"][2] == "Keep-alive today: no account is due")
    check("v6. no news: 'News: no big release today'; Thanksgiving: the early close", five(tue)["lines"][3].startswith("News:")
          and "early close 13:00" in five(ts(2026, 11, 26, 7, 35))["lines"][3], five(ts(2026, 11, 26, 7, 35))["lines"][3])
    na = five(tue, rows=[row("z", "Zlarior", "MFFU Builder 50K", 49000.0), row("p", "Rapid EOD", "MFFU Rapid EOD 25K", 25000.0, badge="PAPER")],
              snap={"rd": {"s": "no", "w": "02:00", "b": "Rapid EOD 25K is not armed", "f": "START BOT and type the phrase"}})
    check("v7. bot line: NOT READY + its fix, armed / NOT armed per account; the title says NOT READY",
          na["lines"][4] == "Bot: NOT READY for 02:00: Rapid EOD 25K is not armed. Fix: START BOT and type the phrase · armed: Zlarior 50K"
          " · NOT armed: Rapid EOD 25K (paper)" and "NOT READY" in na["title"], na["lines"][4])
    big = five(tue, rows=ROWS * 3)
    check("v8. many accounts: still 5 lines, < 4,096 B, no long id", len(big["lines"]) == 5 and len((big["title"] + big["body"]).encode()) < 4096
          and "987654321" not in five(tue, rows=[row("o", "EVBLDR987654321", "MFFU Builder 25K", 25000.0)])["body"])
    old = five(tue, snap={"hb_age": 3 * 3600 + 600})
    check("v9. a 3 h old report: the $ lines say how old, the bot line says NOT READY", "numbers 3 h 10 min old" in old["lines"][0]
          and old["lines"][4].startswith("Bot: NOT READY"), old["lines"])
    from engine import live_vs_bt as LVB
    ok = {"bots": LVB.evaluate([{"bot": "Zlarior", "entry_t": 1, "diff_usd": -8.0, "entry_ticks": 1.0}], [])}
    b = five(tue, lvb=ok)
    check("v11. live vs backtest ok: appended to line 1 (' · live vs bt: LIT -$8 ok'), still 5 lines", len(b["lines"]) == 5
          and b["lines"][0].endswith(" · live vs bt: LIT -$8 ok"), b["lines"][0])
    bad = {"bots": LVB.evaluate([{"bot": "ATLAS", "entry_t": i, "diff_usd": -7.0, "entry_ticks": 3.5, "entry_usd": -7.0} for i in range(10)], [])}
    b = five(tue, lvb=bad)
    check("v12. a flag: line 1 says FLAG and a 6th line gives the plain reason", len(b["lines"]) == 6
          and "live vs bt: ATLAS -$70 FLAG" in b["lines"][0] and b["lines"][5].startswith("ATLAS live is $70 behind the backtest"), b["lines"])
    check("v13. no live trade yet: line 1 unchanged, 5 lines", "live vs bt" not in five(tue, lvb={"bots": LVB.evaluate([], [])})["lines"][0])
    check("v10. the brief that is pushed (pushes) is the 5-line one", "b = build(snap, now, plan_doc, events)" in
          open(os.path.join(ROOT, "tools", "morning_brief.py"), encoding="utf-8").read().split("def pushes", 1)[1])


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_f, part_v2):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
    n, ok = len(RES), sum(RES)
    print(f"\ndaily brief: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
