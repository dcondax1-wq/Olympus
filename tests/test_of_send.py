"""Rehearsal of the owner's ONE order-flow line (tools/of_send_now.py) end to end, in a sandbox (day-ofmax 2026-11-26):
realistic PC files (LE_TickRec backfill CSVs with NinjaTrader's filled-in quotes, its status line, the add-on in AddOns\\)
-> import -> summaries of every day -> signed pages through a FAKE ntfy (the real protocol, tests/test_datafeed.FakeNtfy) within the
daily cap -> the cloud's `data_pull --of` takes the pushed pages -> the battery runs. Also: old code / trading hours / cap / resume.
    python -X utf8 -m tests.test_of_send
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES: list = []
ET = "America/New_York"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def write_pc_day(rd: str, day: str, n: int, seed: int) -> None:
    """One LE_TickRec backfill file exactly as the add-on writes it: bf_NQ_<ET day>.csv, t_ms,price,size,bid,ask, NinjaTrader
    history quotes filled in (Bid = Last, Ask = Bid + 1 tick), heavier in RTH, NQ prices."""
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp(day + " 00:00", tz=ET).value // 10**6
    w = np.ones(24 * 60); w[570:960] = 6.0                          # RTH 6x busier
    mins = rng.choice(24 * 60, n, p=w / w.sum())
    t = np.sort(t0 + mins * 60_000 + rng.integers(0, 60_000, n))
    pk = 100_800 + np.cumsum(rng.choice([-1, 0, 0, 1], n))           # ~25,200 in ticks
    px = pk * 0.25
    size = np.where(rng.random(n) < 0.96, rng.integers(1, 4, n), rng.integers(4, 60, n))
    df = pd.DataFrame({"t_ms": t, "price": px, "size": size, "bid": px, "ask": px + 0.25})
    df.to_csv(os.path.join(rd, f"bf_NQ_{day}.csv"), index=False, float_format="%.2f")


def main():
    from engine import datafeed as DF, ofsum, tickrec as T
    from tests.test_datafeed import FakeNtfy
    import importlib.util
    sp = importlib.util.spec_from_file_location("of_send_now", os.path.join(ROOT, "tools", "of_send_now.py"))
    OS = importlib.util.module_from_spec(sp); sp.loader.exec_module(OS)
    from tools import data_pull as DPL
    td = tempfile.mkdtemp(prefix="of_send_")
    keep = (T.TICK_DIR, T.CFG_PATH, T.DEPTH_DIR)
    env_keep = {k: os.environ.get(k) for k in ("LE_DATAFEED_BASE", "LE_DATAFEED_TOPIC", "OLYMPUS_NT_DIR")}
    fake = FakeNtfy()
    try:
        nd = os.path.join(td, "NinjaTrader 8"); rd = os.path.join(nd, "le_ticks"); os.makedirs(rd)
        os.makedirs(os.path.join(nd, "bin", "Custom", "AddOns"))
        shutil.copy(os.path.join(ROOT, "ninjatrader", "LE_TickRec.cs"), os.path.join(nd, "bin", "Custom", "AddOns", "LE_TickRec.cs"))
        T.TICK_DIR = os.path.join(td, "data", "ticks"); T.CFG_PATH = os.path.join(td, "data", "tickrec.json")
        T.DEPTH_DIR = os.path.join(td, "data", "depth")
        os.makedirs(os.path.dirname(T.CFG_PATH)); json.dump({"enabled": True}, open(T.CFG_PATH, "w"))
        os.environ.update(LE_DATAFEED_BASE=fake.base, LE_DATAFEED_TOPIC="of-rehearsal", OLYMPUS_NT_DIR=nd)
        days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-09-28", periods=42)]
        for k, d in enumerate(days):
            write_pc_day(rd, d, 60_000, k)
        evening = dt.datetime(2026, 11, 26, 17, 30, tzinfo=dt.timezone(dt.timedelta(hours=-5))).timestamp()
        fake.clock = lambda: evening
        with open(os.path.join(rd, "le_tickrec_status.txt"), "w") as fh:
            fh.write("2026-11-26T22:29:50Z,on=1,instruments=NQ 12-26;ES 12-26,rows=812,backfill=running,backfill_days=42,"
                     "oldest=2026-09-28,bf_errors=0,low_disk=0,bf_unknown=0,depth=on,depth_rows=5120\n")
        os.utime(os.path.join(rd, "le_tickrec_status.txt"), (evening - 10, evening - 10))
        dp_work, feed_work = os.path.join(td, "logs", "datapipe"), os.path.join(td, "logs", "datafeed")
        runf = lambda now=evening, **k: _cap(lambda: OS.run(now=now, nd=nd, dp_work=dp_work, feed_work=feed_work, sleep=lambda *_: None, **k))

        # 0. old code -> one clear line
        real = DF.build_of
        try:
            del DF.build_of
            rc, out = runf()
            check("old code: one clear line 'Run the update line first'", rc == 2 and out.strip().startswith("Run the update line first"), out)
        finally:
            DF.build_of = real
        # 0b. trading hours -> refuses
        rc, out = runf(now=dt.datetime(2026, 11, 26, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=-5))).timestamp())
        check("10:00 ET: refuses (the bot trades), says when", rc == 3 and "after 16:05 ET" in out, out)

        # 1. the real run, small pages so the cap and the resume are exercised (42 days ~ 2.5 MB at 1.85 MB pages = 2 pages;
        #    with 600 KB pages: 4 a night, then the cap)
        rc, out = runf(max_zip=120_000)
        print("   PC said:\n   " + out.strip().replace("\n", "\n   "))
        check("recorder report: the new version running, backfill line in plain words",
              "[OK]  Tick recorder: the new version is running" in out and "Backfill: running, 42 days fetched, oldest 2026-09-28" in out, out)
        check("every day imported (backfill CSV -> data/ticks, the .csv -> .done)", len(T.nq_days()) == 42 and
              len([f for f in os.listdir(rd) if f.endswith(".done")]) == 42, (len(T.nq_days()),))
        ready = sorted(os.listdir(os.path.join(dp_work, "days")))
        check("a summary for every finished day", len(ready) == 42 and all(os.path.exists(os.path.join(dp_work, "days", d, "of", "NQ_meta.json")) for d in ready))
        last = out.strip().splitlines()[-1]
        check("final line: sent N days (oldest, newest); depth recording: yes; next: ...",
              last.startswith("sent ") and "depth recording: yes" in last and "next:" in last, last)
        st = json.load(open(os.path.join(feed_work, "state.json")))
        pages = [x for x in st["sent"] if x.get("page")]
        check("within the cap: 6 pages today (8 a day - 2 kept for the bars), newest first", len(pages) == 6 and pages[0]["to"] == days[-1], pages)
        n_sent = sum(p["days"] for p in pages)
        check("cap reached on the first evening: says 'run this line again tomorrow'", n_sent < 42 and "again tomorrow" in last, (n_sent, last))
        # 2. the cloud: data_pull --of takes the pushed pages (no new ask) and the battery runs on them
        pc = os.path.join(td, "pc_days")
        ns = argparse.Namespace(out=pc, since=None, wait=0.01)
        posted = []
        keep_post = DF.post_request

        def cloud_pull():
            DF.post_request = lambda *a, **k: (posted.append(a) or (True, "ok"))
            try:
                return DPL.latest_of(ns, sleep=lambda *_: None)
            finally:
                DF.post_request = keep_post
        rc2 = cloud_pull()
        got = DPL.of_days(pc)
        check("cloud: pushed pages taken, no new ask sent", rc2 == 0 and not posted and len(got) == n_sent, (rc2, posted, len(got), n_sent))
        # 3. resume: the next evenings send the rest (older days), never a day twice
        nights, dup, t_ = 1, False, evening
        while "Already sent" not in out and nights < 6:
            t_ += 86400
            fake.clock = (lambda v: (lambda: v))(t_)
            prev_got = set(DPL.of_days(pc))
            rc, out = runf(now=t_, max_zip=120_000)
            print("   evening %d the PC said: %s" % (nights + 1, out.strip().splitlines()[-1]))
            st2 = json.load(open(os.path.join(feed_work, "state.json")))
            day_ = dt.datetime.fromtimestamp(t_, dt.timezone(dt.timedelta(hours=-5))).date().isoformat()
            new_pages = [x for x in st2["sent"] if x.get("page") and x.get("day") == day_]
            dup = dup or any(x["from"] <= max(prev_got) and x["to"] >= min(prev_got) and x["to"] <= max(prev_got) and x["from"] >= min(prev_got)
                             for x in new_pages) if prev_got and new_pages else dup
            cloud_pull()
            nights += 1
        got = DPL.of_days(pc)
        check("resume: all 42 days reach the cloud over %d evenings, none sent twice, then 'Already sent'" % nights,
              len(got) == 42 and not dup and "Already sent" in out, (len(got), dup, out[-200:]))
        # 4. the battery on the pulled days (cloud side, into a temp folder: no tracked file touched)
        bsp = importlib.util.spec_from_file_location("of_battery_t", os.path.join(ROOT, "research", "orderflow", "of_battery.py"))
        BB = importlib.util.module_from_spec(bsp); bsp.loader.exec_module(BB)
        with contextlib.redirect_stdout(io.StringIO()) as so:
            r = BB.run(src=pc, out_dir=os.path.join(td, "bat"), force=True)
        check("battery ran on the pulled days (look 1 at 42 days), wrote its results + the idea mill", r.get("state") == "ran" and r.get("look") == 1
              and os.path.exists(os.path.join(td, "bat", "battery_results.json")) and os.path.exists(os.path.join(td, "bat", "mill_results.json")),
              (r.get("state"), so.getvalue()[-300:]))
        print("   battery: " + BB.phone_line(r))
        # 5. --of alone runs the battery after the pull (cloud W4)
        calls = []
        keep_rb, keep_lo = DPL.run_battery, DPL.latest_of
        DPL.run_battery = lambda out_dir=None: calls.append(out_dir)
        DPL.latest_of = lambda a, sleep=None: 0
        try:
            DPL.main(["--of", "--out", pc])
        finally:
            DPL.run_battery, DPL.latest_of = keep_rb, keep_lo
        check("`data_pull --of` alone: pull, then the battery", calls == [pc], calls)
    finally:
        T.TICK_DIR, T.CFG_PATH, T.DEPTH_DIR = keep
        for k, v in env_keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        fake.srv.shutdown()
        shutil.rmtree(td, ignore_errors=True)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def _cap(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn()
    return rc, buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
