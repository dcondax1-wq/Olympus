"""Poll speed diagnostics (engine/poll_timing.py) and the NinjaTrader outgoing-folder read cache
(engine/ninjatrader.NinjaTraderAdapter.connections). The owner's Surface polled in ~32 s every time (heartbeat
2026-10-25) against <1 s here on the same bars.

    python -X utf8 -m tests.test_poll_timing

  1. the timer changes nothing: a LIT paper bot on NinjaTrader feed files (20,000 1m bars, a temp NinjaTrader folder)
     polled with and without it -> the same state and ledger; with it, health.poll_stages has every stage (incl. nested
     ones), wall and CPU, other busy threads; the heartbeat block (accounts.poll_stages_block) and the Home line
     (pc_cc_api.poll_line) read it.
  2. connections(): the same answer, but an unchanged file is not opened again (604 -> 2 outgoing file reads a poll with
     300 order files); a changed / removed file is read again / dropped; shared by every adapter (autoresume makes a new
     one each check).
No network (the news / VIX refresh is stubbed), temp folders only; the real data/ files are checked unchanged at the end.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from engine import accounts, live, news, ninjatrader, pc_cc_api, poll_timing  # noqa: E402

ET = ZoneInfo("America/New_York")
T = int(dt.datetime(2026, 10, 15, 10, 1, 2, tzinfo=ET).timestamp())
RES = []
WATCH = [os.path.join(ROOT, "data", f) for f in ("VIX_1d.csv", "VXN_1d.csv", "live_state.json", "account_b.json")] + \
    [os.path.join(ROOT, "data", "news", f) for f in ("ff_thisweek.json", "ff_archive.csv")]


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:300]})" if info and not ok else ""), flush=True)


def digest():
    out = {}
    for p in WATCH:
        try:
            out[p] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        except OSError:
            out[p] = None
    return out


def nt_folder(tmp, n_orders=300):
    nt = os.path.join(tmp, "NinjaTrader 8")
    for d in ("le_feed", "outgoing", "incoming"):
        os.makedirs(os.path.join(nt, d), exist_ok=True)
    d1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    d5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    d1[d1["time"] + 60 <= T].tail(20000).to_csv(os.path.join(nt, "le_feed", "MNQ_1m.csv"), index=False)
    d5[d5["time"] + 300 <= T].tail(8300).to_csv(os.path.join(nt, "le_feed", "MNQ_5m.csv"), index=False)
    out = os.path.join(nt, "outgoing")
    open(os.path.join(out, "Simulation.txt"), "w").write("CONNECTED")
    open(os.path.join(out, "MNQ 12-26 Globex_Sim101_Position.txt"), "w").write("FLAT;0;0")
    for i in range(n_orders):
        open(os.path.join(out, f"{i:032x}.txt"), "w").write("FILLED;1;25000.25")
    return nt


def bot(tmp, nt, adapter="paper"):
    b = live.LiveBot()
    b.clock = lambda: T
    b.state_path = os.path.join(tmp, "live_state.json")
    cfg = {"sym": "NQ", "tf": "5m", "adapter": adapter, "data_source": "ninjatrader", "nt_folder": nt,
           "nt_archive": os.path.join(tmp, "arch"), "poll_sec": 60}
    if adapter == "ninjatrader":
        cfg.update(nt_account="Sim101", armed=True, nt_state_path=os.path.join(tmp, "nts.json"), nt_audit_log=os.path.join(tmp, "oif.log"))
    r = b.start(cfg, spawn=False)
    assert r.get("ok"), r
    return b


def snap(b):
    st = json.loads(json.dumps(b.state, default=str))
    return {"state": st, "ledger": json.loads(json.dumps(b.ledger, default=str))}


def timer_part(base):
    print("1. the timer changes nothing and sees every stage", flush=True)
    runs = []
    for k in ("plain", "timed"):
        tmp = os.path.join(base, k)
        os.makedirs(tmp)
        nt = nt_folder(tmp, 10)
        if k == "timed":
            poll_timing.install()
        b = bot(tmp, nt)
        if k == "timed":
            poll_timing.install(b)
        out = []
        for i in range(3):
            os.utime(os.path.join(nt, "le_feed", "MNQ_1m.csv"))          # a new minute: the feed file changed
            b.poll_once()
            out.append(snap(b))
        runs.append((out, b))
    (a, _), (t, bt) = runs
    check("the same state and ledger after 3 polls with and without the timer", a == t,
          [k for k in a[-1]["state"] if a[-1]["state"].get(k) != t[-1]["state"].get(k)][:5])
    ps = bt.health.get("poll_stages") or {}
    names = [s["name"] for s in ps.get("stages") or []]
    want = ["adapter tick (NinjaTrader files)", "news + VIX refresh", "bars: merge", "1m bars", "LIT model (lit_live.run)",
            "route", "guards", "alerts + AI watch", "save state"]
    check("health.poll_stages: every main stage, in poll order", all(w in names for w in want)
          and [n for n in names if n in want] == [w for w in want], names)
    check("nested stages: the 1m bars' file parse and feed checks under their parent",
          any(n.startswith("1m bars > bars: merge > NinjaTrader feed > feed checks") for n in names), names)
    check("total = the whole poll (>= the sum of the top stages), CPU and waiting split, recent totals kept",
          ps.get("total_ms", 0) >= sum(s["ms"] for s in ps["stages"] if " > " not in s["name"]) - 2
          and ps.get("cpu_ms") is not None and ps.get("wait_ms") is not None and len(ps.get("recent_ms") or []) == 3, ps)
    hb = accounts.poll_stages_block(ps)
    check("heartbeat health.poll.stages: top stages + nested ones of 50 ms or more, small", hb and hb["total_ms"] == ps["total_ms"]
          and all(" > " not in s["name"] or s["ms"] >= 50 for s in hb["stages"]) and len(json.dumps(hb)) < 6000, len(json.dumps(hb or {})))
    line = pc_cc_api.poll_line(hb)
    check("the Home 'Bot loop' line names the poll time and the slowest stages", "s a poll" in line and "slowest:" in line, line)
    # a busy background thread shows up (a CPU-heavy thread slows every stage through Python's GIL)
    stop = threading.Event()

    def busy():
        x = 0
        while not stop.is_set():
            x = sum(i * i for i in range(20000)) + x % 7
    th = threading.Thread(target=busy, name="busy-test-thread", daemon=True)
    th.start()
    time.sleep(0.3)
    bt.poll_once()
    stop.set()
    th.join(2)
    thr = (bt.health.get("poll_stages") or {}).get("threads") or []
    check("the other threads busy during the poll are named with their CPU", any(t["name"] == "busy-test-thread" and t["cpu_ms"] > 0
                                                                                  for t in thr), thr)
    check("outside a poll the wrapped functions are plain calls (no record, same result)",
          live.clean_bars is not None and getattr(live.LiveBot.poll_once, "_le_timed", False)
          and poll_timing._TL.__dict__.get("stack") is None)


def conn_part(base):
    print("2. connections(): same answer, unchanged files not opened again", flush=True)
    tmp = os.path.join(base, "conn")
    os.makedirs(tmp)
    nt = nt_folder(tmp, 300)
    out = os.path.join(nt, "outgoing")
    reads = []
    orig = ninjatrader._read_text
    ninjatrader._read_text = lambda p: (reads.append(os.path.basename(p)), orig(p))[1]
    try:
        cfg = {"adapter": "ninjatrader", "nt_folder": nt, "nt_account": "Sim101", "nt_state_path": os.path.join(tmp, "s.json")}
        ad = ninjatrader.NinjaTraderAdapter(cfg, readonly=True)
        c1 = ad.connections()
        n1 = len(reads)
        reads.clear()
        c2 = ad.connections()
        n2 = len(reads)
        ad2 = ninjatrader.NinjaTraderAdapter(cfg, readonly=True)     # autoresume.nt_connected makes a new adapter each time
        reads.clear()
        c3 = ad2.connections()
        n3 = len(reads)
        check("first call reads every candidate file, the answer is the connection", c1 == {"Simulation": "CONNECTED"} and n1 == 301, (c1, n1))
        check("second call: same answer, no file opened (unchanged size and time)", c2 == c1 and n2 == 0, n2)
        check("a new adapter shares it (autoresume's checks): no file opened", c3 == c1 and n3 == 0, n3)
        time.sleep(0.01)
        open(os.path.join(out, "Simulation.txt"), "w").write("DISCONNECTED")
        reads.clear()
        c4 = ad.connections()
        check("a changed file is read again: DISCONNECTED seen at once", c4 == {"Simulation": "DISCONNECTED"} and reads == ["Simulation.txt"], (c4, reads))
        open(os.path.join(out, "MFFU.txt"), "w").write("CONNECTED")
        os.remove(os.path.join(out, "Simulation.txt"))
        c5 = ad.connections()
        check("a new connection file appears, a removed one is gone (NinjaTrader restart wipes outgoing)",
              c5 == {"MFFU": "CONNECTED"} and not any(p.endswith("Simulation.txt") for p in ninjatrader._CONN_SEEN), c5)
        # the LIT bot's whole poll with its NinjaTrader adapter (Sim101): the outgoing reads per poll
        b = bot(tmp, nt, adapter="ninjatrader")
        counts = []
        for i in range(3):
            reads.clear()
            b.poll_once()
            counts.append(sum(1 for r in reads if r.endswith(".txt")))
        check("a poll with 300 order files in outgoing: a few file reads once warm (was 604)", max(counts[1:]) <= 5, counts)
    finally:
        ninjatrader._read_text = orig


def full_part():
    """--full: tests.test_lit_live's LiveBot replay (3 sessions, bars revealed as they close) with and without the timer:
    the same routed entries / exits (side, micros, stop, target, exit, P&L)."""
    print("3. the LIT LiveBot replay of tests.test_lit_live with and without the timer", flush=True)
    import collections
    from tests import test_lit_live as TL
    from tools import lit_final as F
    P = json.load(open(TL.LIVE, encoding="utf-8"))["lit"]
    by_day = collections.defaultdict(list)
    for t in F.run(P):
        if t["day"] >= "2026-01-01":
            by_day[t["day"]].append(t)
    a = TL.bot_replay(P, by_day)
    poll_timing.install()
    b = TL.bot_replay(P, by_day)
    keys = ("want", "entries_ok", "exits_ok", "extra", "not_routed", "errors", "modify_routes")
    strip = lambda r: [{"entry": x["entry"], "want": x["want"], "e": {k: v for k, v in (x["routed_entry"] or {}).items() if k != "t"},  # noqa: E731
                        "x": {k: v for k, v in (x["routed_exit"] or {}).items() if k != "t"}} for x in r["rows"]]
    check("the LiveBot replay: ok both ways, the same routed entries and exits, the same counts",
          a["ok"] and b["ok"] and strip(a) == strip(b) and all(a[k] == b[k] for k in keys),
          {k: (a.get(k), b.get(k)) for k in keys})


def main():
    before = digest()
    keep = (news.ff_calendar, news.volatility)
    news.ff_calendar = lambda: []                                   # no network in the test
    news.volatility = lambda: {"regime": "normal"}
    base = tempfile.mkdtemp(prefix="le_polltiming_")
    try:
        if "--full" in sys.argv:
            full_part()
        timer_part(base)
        conn_part(base)
    finally:
        news.ff_calendar, news.volatility = keep
        shutil.rmtree(base, ignore_errors=True)
    check("the real data/ files did not change", digest() == before)
    print(f"poll timing: {sum(RES)}/{len(RES)} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
