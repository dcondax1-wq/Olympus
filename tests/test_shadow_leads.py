"""engine/shadow_leads.py (observe-only paper-lead log). Temp files only; nothing armed, nothing routed.

    python -X utf8 -m tests.test_shadow_leads            # a-e (seconds) + f (three LiveBot paper replays, ~11 min)
    python -X utf8 -m tests.test_shadow_leads --quick    # a-e only

 a. A3 on a synthetic day: a signal that runs 12+ ticks -> would fill at trigger + 2 ticks, R measured in the bot's own risk;
    one whose stop trades first -> no fill (avoided), shadow 0R vs the model's -1R; rows de-duplicated on a second run.
 b. ES lead on a synthetic day: ES's sweep window from the NQ sweep-extreme bar, ES stop / VIX band, switch by R:R x 1.25,
    ES result walked on ES 5m; a day without ES bars -> "no ES bar", no crash.
 c. the off switch (data/shadow_leads.json {"on": false}) writes nothing; corrupt / missing files never raise.
 d. the weekly line.
 e. isolation: no trading-loop module imports it (engine/live.py, account_b, rapid, lit_live, server.py, multi_account).
 f. a real LiveBot paper replay (tests/test_lit_live.bot_replay, 2 sessions): ledger + trades byte-identical with the
    shadow ON and run on the replay's own ledger in between vs OFF.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import shadow_leads as SL  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:300]})" if info and not ok else ""), flush=True)


def ts(day, h, m):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m), ET).timestamp())


def gzcsv(bars):
    s = "time,open,high,low,close,volume\n" + "".join(f"{t},{o},{h},{l},{c},1\n" for t, o, h, l, c in bars)
    return gzip.compress(s.encode())


def write_day(dd, day, files, rows):
    d = os.path.join(dd, day)
    os.makedirs(os.path.join(d, "bars"), exist_ok=True)
    for k, v in files.items():
        with open(os.path.join(d, "bars", k), "wb") as fh:
            fh.write(gzcsv(v))
    with open(os.path.join(d, "trades.jsonl.gz"), "wb") as fh:
        fh.write(gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode()))


def flat1m(day, start, end, px):
    return [(t, px, px + 0.25, px - 0.25, px) for t in range(ts(day, *start), ts(day, *end), 60)]


def part_a(tmp):
    day = "2026-11-18"
    b = flat1m(day, (9, 0), (10, 0), 20000.0)
    e1 = ts(day, 10, 0)
    # signal 1 (long, stop 19980, target 20040): 1m path runs up 4 ticks/min -> trigger 20003 at minute 3, target later
    run = [(e1 + 60 * i, 20000.0 + i, 20000.0 + i + 0.75, 20000.0 + i - 0.25, 20000.0 + i + 0.5) for i in range(45)]
    e2 = ts(day, 11, 0)
    gap = [(t, 20044.0, 20044.25, 20043.75, 20044.0) for t in range(e1 + 60 * 45, e2, 60)]
    # signal 2 (long, open 20044, stop 20030): falls through the stop in minute 2 without 12 ticks up first
    fall = [(e2, 20044.0, 20045.0, 20040.0, 20041.0), (e2 + 60, 20041.0, 20042.0, 20029.0, 20030.0)] + \
           [(e2 + 60 * i, 20030.0, 20030.25, 20029.75, 20030.0) for i in range(2, 40)]
    tail = flat1m(day, (11, 40), (16, 0), 20030.0)
    rows = [{"src": "acctb", "side": "buy", "entry_t": e1, "stop": 19980.0, "target": 20040.0, "qty": 2, "strategy": "EMA",
             "result": {"ok": True}, "t": e1 + 4},
            {"src": "acctb", "side": "exit", "entry_t": e1, "pnl": 152.2, "reason": "TARGET", "t": e1 + 3000},
            {"src": "acctb", "side": "sell" if False else "buy", "entry_t": e2, "stop": 20030.0, "target": 20080.0, "qty": 3,
             "strategy": "MD", "result": {"ok": True}, "t": e2 + 4}]
    write_day(tmp, day, {"NQ_1m.csv.gz": b + run + gap + fall + tail}, rows)
    out = os.path.join(tmp, "shadow.jsonl")
    r = SL.run_day(day, tmp, out, cfg=os.path.join(tmp, "none.json"))
    a = {x["entry_t"]: x for x in r["rows"] if x["lead"] == "A3"}
    s1, s2 = a.get(e1) or {}, a.get(e2) or {}
    check("a. A3 signal 1 fills (12 ticks within 5 min) at trigger + 2 ticks", s1.get("would_fill") is True and s1.get("fill_px") == 20003.5, s1)
    check("a. A3 signal 1: model and shadow both reach the target; shadow R a little smaller (worse fill)",
          s1.get("model_exit") == "TARGET" and s1.get("shadow_exit") == "TARGET" and 0 < s1["shadow_R"] < s1["model_R"], s1)
    check("a. A3 signal 2: stop traded first -> no fill (avoided), shadow 0R vs model -1R-ish -> delta > 0",
          s2.get("would_fill") is False and s2.get("shadow_R") == 0.0 and s2.get("model_R") < -0.9 and s2.get("delta_R") > 0.9, s2)
    check("a. rows written once; a second run adds nothing (de-duplicated)", r["added"] == len(r["rows"]) and
          SL.run_day(day, tmp, out, cfg=os.path.join(tmp, "none.json"))["added"] == 0, r["added"])
    return out


def part_b(tmp):
    day = "2026-11-19"
    lo18 = int(dt.datetime.combine(dt.date.fromisoformat(day) - dt.timedelta(days=1), dt.time(18, 0), ET).timestamp())
    # NQ 5m: a sweep bar at 09:50 with low 19979.75 (stop 19979.5 = 1 tick beyond), entry 10:00, NQ target 20060 (R:R ~ 3.9)
    n5 = [(t, 20000.0, 20001.0, 19999.0, 20000.0) for t in range(lo18, ts(day, 9, 50), 300)]
    n5 += [(ts(day, 9, 50), 20000.0, 20000.5, 19979.75, 19990.0), (ts(day, 9, 55), 19990.0, 20001.0, 19989.0, 20000.0)]
    n5 += [(t, 20000.0, 20001.0, 19999.0, 20000.0) for t in range(ts(day, 10, 0), ts(day, 16, 5), 300)]
    # ES 5m: 18:00 open 5600; sweep low 5590 at 09:50, entry open 5598 at 10:00 -> ES stop 5589.75, risk 8.5; VIX 20 band:
    # 5600 + 20/100/sqrt(252)*5600 = 5670.6 -> R:R 8.6 capped at 8R (5666.0) >= 1.25 x NQ's -> switch; ES then runs to target
    e5 = [(lo18, 5600.0, 5601.0, 5599.0, 5600.0)] + [(t, 5600.0, 5601.0, 5599.0, 5600.0) for t in range(lo18 + 300, ts(day, 9, 50), 300)]
    e5 += [(ts(day, 9, 50), 5600.0, 5600.5, 5590.0, 5595.0), (ts(day, 9, 55), 5595.0, 5598.5, 5594.0, 5597.75)]
    e5 += [(ts(day, 10, 0) + 300 * i, 5598.0 + 2 * i, 5599.0 + 2 * i, 5597.5 + 2 * i, 5598.5 + 2 * i) for i in range(72)]
    rows = [{"src": "main", "side": "buy", "entry_t": ts(day, 10, 0), "entry": 20000.25, "stop": 19979.5, "target": 20060.0, "qty": 4,
             "result": {"ok": True}, "t": ts(day, 10, 0) + 3},
            {"src": "main", "side": "exit", "entry_t": ts(day, 10, 0), "pnl": -170.0, "reason": "STOP", "t": ts(day, 11, 0)}]
    write_day(tmp, day, {"NQ_5m.csv.gz": n5, "ES_5m.csv.gz": e5}, rows)
    out = os.path.join(tmp, "shadow.jsonl")
    r = SL.run_day(day, tmp, out, cfg=os.path.join(tmp, "none.json"), vix=20.0, vix_k=1.0)
    es = next((x for x in r["rows"] if x["lead"] == "ES"), {})
    check("b. ES lead: sweep window found, ES stop 1 tick beyond ES's sweep low, 8R cap, switch on", es.get("status") == "ok"
          and es.get("es_stop") == 5589.75 and es.get("switch") is True and abs(es.get("es_rr", 0) - 8.0) < 1e-6, es)
    check("b. ES result walked on ES 5m (target) and compared with the booked NQ R", es.get("es_exit") == "TARGET" and
          es.get("es_R") == 8.0 and es.get("nq_R") is not None and es.get("delta_R") > 8, es)
    write_day(tmp, "2026-11-20", {"NQ_5m.csv.gz": [(ts("2026-11-20", 10, 0) - 300 * i, 1, 2, 0.5, 1) for i in range(5, 0, -1)]},
              [{"src": "main", "side": "buy", "entry_t": ts("2026-11-20", 10, 0), "entry": 1.5, "stop": 0.25, "target": 3.0, "qty": 1}])
    r2 = SL.run_day("2026-11-20", tmp, out, cfg=os.path.join(tmp, "none.json"), vix=20.0)
    check("b. a day without ES bars: a status row, no crash", "error" not in r2 and all(x.get("status") != "ok" for x in r2["rows"]), r2)
    return out


def part_c(tmp):
    cfg = os.path.join(tmp, "sl.json")
    json.dump({"on": False}, open(cfg, "w"))
    out = os.path.join(tmp, "off.jsonl")
    r = SL.run_day("2026-11-18", tmp, out, cfg=cfg)
    check("c. off switch: nothing written", r.get("off") and not os.path.exists(out), r)
    bad = os.path.join(tmp, "2026-11-21")
    os.makedirs(os.path.join(bad, "bars"), exist_ok=True)
    open(os.path.join(bad, "trades.jsonl.gz"), "wb").write(b"\x1f\x8bnot gzip")
    open(os.path.join(bad, "bars", "NQ_1m.csv.gz"), "wb").write(b"garbage")
    ok = True
    try:
        r = SL.run_day("2026-11-21", tmp, os.path.join(tmp, "x.jsonl"), cfg=os.path.join(tmp, "none.json"))
        r2 = SL.run_day("1999-01-01", tmp, os.path.join(tmp, "x.jsonl"), cfg=os.path.join(tmp, "none.json"))
        s = SL.summary(out=os.path.join(tmp, "missing.jsonl"))
        n = SL.maybe_run(days_dir=os.path.join(tmp, "nope"), out=os.path.join(tmp, "x.jsonl"))
    except Exception as e:  # noqa: BLE001
        ok, r = False, repr(e)
    check("c. corrupt pack / missing day / missing log never raise", ok and r.get("added") == 0 and r2.get("added") == 0 and n == 0, r)


def part_d(out):
    s = SL.summary(days=30, now=ts("2026-11-20", 20, 0), out=out)
    check("d. weekly line: 'A3 shadow: n signals, m would fill, +xR vs live | ES shadow: ...'", s["line"].startswith("A3 shadow: 2 signals, 1 would fill")
          and "ES shadow: 1 of 1" in s["line"] and s["A3"]["delta_R"] > 0, s)


def part_e():
    bad = []
    for f in ("engine/live.py", "engine/account_b.py", "engine/rapid.py", "engine/lit_live.py", "engine/multi_account.py",
              "engine/ninjatrader.py", "server.py", "engine/sizing.py"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p) and "shadow_leads" in open(p, encoding="utf-8").read():
            bad.append(f)
    check("e. no trading-loop module references shadow_leads (it cannot route, size, block or delay)", not bad, bad)


def part_f(tmp):
    import collections
    import shutil
    from tests import test_lit_live as TL
    from tools import lit_final as F
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    REF = [t for t in F.run(P) if t["day"] >= "2026-10-01"]
    by = collections.defaultdict(list)
    for t in REF:
        by[t["day"]].append(t)
    sess = ("2026-10-13", "2026-10-14")
    got = {}
    for mode in ("off", "on"):
        cfgp = os.path.join(tmp, f"cfg_{mode}.json")
        json.dump({"on": mode == "on"}, open(cfgp, "w"))
        box = {}
        res = TL.bot_replay(P, by, sessions=sess, on_bot=lambda b: box.setdefault("bot", b))
        led = json.dumps([{k: v for k, v in r.items() if k != "t"} for r in box["bot"].ledger], sort_keys=True, default=str)
        if mode == "on":                       # shadow the replay's own ledger as the PC would after the close
            rows = [{**r, "src": "main"} for r in box["bot"].ledger]
            write_day(os.path.join(tmp, "f"), sess[-1], {}, rows)
            SL.run_day(sess[-1], os.path.join(tmp, "f"), os.path.join(tmp, "f.jsonl"), cfg=cfgp)
            res2 = TL.bot_replay(P, by, sessions=sess, on_bot=lambda b: box.setdefault("bot2", b))
            led2 = json.dumps([{k: v for k, v in r.items() if k != "t"} for r in box["bot2"].ledger], sort_keys=True, default=str)
            got["on_after"] = (led2, json.dumps(res2["rows"], sort_keys=True, default=str))
        got[mode] = (led, json.dumps(res["rows"], sort_keys=True, default=str))
        shutil.rmtree(os.path.join(tmp, "f"), ignore_errors=True)
    check("f. LiveBot paper replay: ledger + trades byte-identical, shadow OFF vs ON (and after the shadow ran on its ledger)",
          got["off"] == got["on"] == got["on_after"], [len(got[k][0]) for k in got])


def main():
    tmp = tempfile.mkdtemp(prefix="shadow_leads_")
    out = part_a(tmp)
    part_b(tmp)
    part_c(tmp)
    part_d(out)
    part_e()
    if "--quick" not in sys.argv:
        part_f(tmp)
    n, ok = len(RES), sum(RES)
    print(f"shadow leads: {ok}/{n} {'ALL PASS' if ok == n else 'FAILED'}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
