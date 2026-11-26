"""engine/datapipe.day_fills + fills.jsonl.gz in both day packers + tools/fill_speed.py (day-speed 2026-11-20).
    python -X utf8 -m tests.test_datapipe_fills
a. from a synthetic OIF audit log + archived order states + fill-audit legs: one row per MARKET entry order of the day, every
   account (Zlarior main, ATLAS acctb_), send time from the OIF file name (ms), NinjaTrader's fill time + price, seconds split
b. bracket orders (STOPMARKET / LIMIT), CLOSEPOSITION and another day's entry are left out; account names cut to the last 4
c. a FILLED state wins over a later WORKING line for the same order; a leg's own sent_at is kept as leg_sent_t
d. datapipe.pack_day and datafeed.pack_day both carry fills.jsonl.gz; load_day reads it back; the manifest counts it
e. tools/fill_speed.py: ticks past the fill bar's open, $ past the backtest's 1 tick, seconds, per account; old days without
   fills.jsonl.gz fall back to the ledger stamp ("stamp only")
f. no missing file raises (no OIF log, no store)
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine import datapipe as DP  # noqa: E402
import fill_speed as FS  # noqa: E402

FAIL = []
ET_ = 1795164300                      # Fri 2026-11-20 03:45 ET (ATLAS's real short)
EZ = 1795174560                       # 06:36 ET, a Zlarior entry
OLD = 1794995400                      # Wed 2026-11-18 04:50 ET (another day)


def check(name, ok, info=""):
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAIL.append(name)


def oif(stamp, acct, tag, ms, line):
    return f"{stamp} ET  {acct}  oif_le_{tag}{ms}_3.txt  {line}\n"


def main():
    tmp = tempfile.mkdtemp(prefix="dp_fills_")
    try:
        os.makedirs(os.path.join(tmp, "logs", "exec_audit"))
        ida, idz, ido = f"LE{ET_}k3f9ME", f"LE{EZ}a1b2ME", f"LE{OLD}zz11ME"
        with open(os.path.join(tmp, "logs", "ninjatrader_oif.log"), "w", encoding="utf-8") as fh:
            fh.write(oif("2026-11-20 03:45:02", "MFFUFUND25K6017", "acctb_", (ET_ + 2) * 1000 + 412,
                         f"PLACE;MFFUFUND25K6017;MNQ 12-26;SELL;1;MARKET;;;DAY;;{ida};;"))
            fh.write(oif("2026-11-20 03:45:04", "MFFUFUND25K6017", "acctb_", (ET_ + 4) * 1000,
                         f"PLACE;MFFUFUND25K6017;MNQ 12-26;BUY;1;STOPMARKET;;26419.5;GTC;O1;LE{ET_}k3f9MS;;"))
            fh.write(oif("2026-11-20 03:45:04", "MFFUFUND25K6017", "acctb_", (ET_ + 4) * 1000 + 1,
                         f"PLACE;MFFUFUND25K6017;MNQ 12-26;BUY;1;LIMIT;26122.75;;GTC;O1;LE{ET_}k3f9MT;;"))
            fh.write(oif("2026-11-20 06:36:02", "MFFUEVAL50K1234", "", (EZ + 2) * 1000 + 250,
                         f"PLACE;MFFUEVAL50K1234;MNQ 12-26;BUY;3;MARKET;;;DAY;;{idz};;"))
            fh.write(oif("2026-11-20 09:00:00", "MFFUEVAL50K1234", "", (EZ + 9000) * 1000, "CLOSEPOSITION;MFFUEVAL50K1234;MNQ 12-26;;;;;;;;;;"))
            fh.write(oif("2026-11-18 04:50:02", "MFFUFUND25K6017", "acctb_", (OLD + 2) * 1000,
                         f"PLACE;MFFUFUND25K6017;MNQ 12-26;SELL;2;MARKET;;;DAY;;{ido};;"))
        with open(os.path.join(tmp, "logs", "exec_audit", "orders.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": ida, "state": "FILLED", "filled": 1, "avg": 26375.5, "mtime": ET_ + 2.731, "seen": ET_ + 60}) + "\n")
            fh.write(json.dumps({"id": ida, "state": "WORKING", "filled": 0, "avg": None, "mtime": ET_ + 2.5, "seen": ET_ + 61}) + "\n")
            fh.write(json.dumps({"id": idz, "state": "FILLED", "filled": 3, "avg": 27001.25, "mtime": EZ + 2.6, "seen": EZ + 60}) + "\n")
            fh.write(json.dumps({"id": idz[:-1] + "S", "state": "FILLED", "filled": 3, "avg": 26989.5, "mtime": EZ + 900, "seen": EZ + 960}) + "\n")
            fh.write(json.dumps({"id": idz[:-1] + "T", "state": "CANCELLED", "filled": 0, "avg": None, "mtime": EZ + 900, "seen": EZ + 960}) + "\n")
        with open(os.path.join(tmp, "logs", "exec_audit", "legs.json"), "w", encoding="utf-8") as fh:
            json.dump({idz: {"entry_id": idz, "entry_t": EZ, "sent_at": EZ + 2.249, "fill_mtime": EZ + 2.6, "fill_px": 27001.25, "filled": 3,
                             "send_at": EZ + 2.25, "ack_at": EZ + 2.31, "fill_seen_at": EZ + 2.7, "ref": 27000.5,
                             "dir": 1, "stop": 26990.0, "target": 27050.0}}, fh)
        names = {"MFFUFUND25K6017", "MFFUEVAL50K1234"}
        rows = DP.day_fills("2026-11-20", root=tmp, names=names)
        by = {r["order_id"]: r for r in rows}
        a, z = by.get(ida), by.get(idz)
        check("a. 2 MARKET entries of the day, both accounts", len(rows) == 2 and a is not None and z is not None, str(rows))
        check("a. ATLAS: book atlas, sent 2.412 s after the open, filled 0.319 s later at 26,375.50",
              a and a["book"] == "atlas" and a["sent_s_after_open"] == 2.412 and a["fill_s_after_sent"] == 0.319
              and a["fill_px"] == 26375.5 and a["filled"] == 1 and a["action"] == "SELL", str(a))
        check("a. Zlarior: book zlarior, 3 filled, sent 2.25 s, filled 0.35 s later", z and z["book"] == "zlarior"
              and z["filled"] == 3 and z["sent_s_after_open"] == 2.25 and z["fill_s_after_sent"] == 0.35, str(z))
        txt = json.dumps(rows)
        check("b. brackets, CLOSEPOSITION and the Nov 18 entry left out", ido not in by and "STOPMARKET" not in txt and "CLOSEPOSITION" not in txt)
        check("b. account names only as their last 4", "MFFUFUND25K6017" not in txt and "MFFUEVAL50K1234" not in txt
              and a["account"] == "...6017" and z["account"] == "...1234", txt[:200])
        check("c. FILLED wins over a later WORKING line", a["state"] == "FILLED")
        check("c. the leg's own sent_at kept as leg_sent_t", z.get("leg_sent_t") == EZ + 2.249)
        check("c2. big-execution latency chain: signal_t / send_t / ack_t / fill_seen_t / model_px + ack_s_after_send",
              z.get("signal_t") == EZ and z.get("send_t") == EZ + 2.25 and z.get("ack_t") == EZ + 2.31 and z.get("fill_seen_t") == EZ + 2.7
              and z.get("model_px") == 27000.5 and z.get("ack_s_after_send") == 0.06 and a.get("signal_t") == a.get("entry_t")
              and "send_t" not in a, str(z))
        check("c3. big-exitreal: the real exit (stop filled 2 ticks below its 26,990 level) next to the levels; none for ATLAS",
              z.get("exit_order") == "stop" and z.get("exit_fill_px") == 26989.5 and z.get("exit_slip_ticks") == 2.0
              and z.get("stop_px") == 26990.0 and z.get("target_px") == 27050.0 and z.get("exit_fill_t") == EZ + 900
              and "exit_fill_px" not in a, str(z))
        files = DP.pack_day("2026-11-20", {}, [], names, root=tmp, exec_store=os.path.join(tmp, "logs", "exec_audit"),
                            build_twin=False, now=ET_ + 86400)
        back = [json.loads(x) for x in gzip.decompress(files["fills.jsonl.gz"]).decode().splitlines() if x]
        man = json.loads(files["manifest.json"])
        check("d. datapipe.pack_day carries fills.jsonl.gz (2 rows) + the manifest counts it",
              len(back) == 2 and man["counts"].get("fills") == 2 and "fills.jsonl.gz" in man["files"], str(man.get("counts")))
        dd = os.path.join(tmp, "days")
        DP.write_local("2026-11-20", files, days_dir=dd)
        check("d. load_day reads fills back", len(DP.load_day(os.path.join(dd, "2026-11-20"))["fills"]) == 2)
        from engine import datafeed as DF
        old_root, DP.ROOT = DP.ROOT, tmp
        try:
            f2 = DF.pack_day("2026-11-20", {}, [], names, {}, ET_ + 86400, "test", os.path.join(tmp, "nolocal"))
        finally:
            DP.ROOT = old_root
        check("d. datafeed.pack_day (the ntfy path the PC uses) carries fills.jsonl.gz too", "fills.jsonl.gz" in f2, str(sorted(f2)))
        # e. fill_speed over a pc_days folder: one new day (fills) + one old day (trades only)
        pd_dir = os.path.join(tmp, "pc_days")
        new = os.path.join(pd_dir, "2026-11-20")
        os.makedirs(os.path.join(new, "bars"))
        with open(os.path.join(new, "fills.jsonl.gz"), "wb") as fh:
            fh.write(files["fills.jsonl.gz"])
        with gzip.open(os.path.join(new, "bars", "MNQ_1m.csv.gz"), "wt") as fh:
            fh.write(f"time,open,high,low,close,volume\n{ET_},26381.0,26388.25,26361.0,26371.25,1487\n{EZ},27000.0,27003,26999,27002,10\n")
        oldd = os.path.join(pd_dir, "2026-11-18")
        os.makedirs(os.path.join(oldd, "bars"))
        with gzip.open(os.path.join(oldd, "trades.jsonl.gz"), "wt") as fh:
            fh.write(json.dumps({"side": "sell", "mode": "live", "bot": "atlas", "entry_t": OLD, "t": OLD + 3,
                                 "result": {"legs": [{"fill_px": 27391.75, "filled": 2, "instrument": "MNQ 12-26"}]}}) + "\n")
        with gzip.open(os.path.join(oldd, "bars", "MNQ_1m.csv.gz"), "wt") as fh:
            fh.write(f"time,open,high,low,close,volume\n{OLD},27395.75,27398.5,27385.25,27393.25,755\n")
        R = FS.collect(pd_dir)
        S = FS.summary(R)
        ra = next(r for r in R if r["entry_t"] == ET_)
        check("e. ATLAS Nov 20: 22 ticks past the open = $10.50 past the backtest (1 micro), 2.412 s to send",
              ra["ticks"] == 22.0 and ra["usd_vs_backtest"] == 10.5 and ra["sent_s"] == 2.412, str(ra))
        rz = next(r for r in R if r["entry_t"] == EZ)
        check("e. Zlarior: 5 ticks past the open (a buy), $6.00 on 3 micros", rz["ticks"] == 5.0 and rz["usd_vs_backtest"] == 6.0, str(rz))
        ro = next(r for r in R if r["entry_t"] == OLD)
        check("e. an old day without fills.jsonl.gz: ledger stamp only, 16 ticks", ro["src"] == "stamp only" and ro["ticks"] == 16.0
              and ro["sent_s"] is None and ro["stamp_s"] == 3, str(ro))
        check("e. per account: atlas n 2 (1 timed), worst 22 ticks; zlarior n 1", S["atlas"]["n"] == 2 and S["atlas"]["with_seconds"] == 1
              and S["atlas"]["ticks"][1] == 22.0 and S["zlarior"]["n"] == 1, str(S))
        empty = tempfile.mkdtemp(prefix="dp_fills_empty_")
        check("f. no OIF log / no store: [] (never raises)", DP.day_fills("2026-11-20", root=empty) == [])
        shutil.rmtree(empty, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'ALL OK' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
