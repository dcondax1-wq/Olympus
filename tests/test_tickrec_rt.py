"""Red team on day-orderflow (2026-11-23): the tick recorder. Temp folders only; never this PC's NinjaTrader folder.

    python -X utf8 -m tests.test_tickrec_rt        (~5 s; the C# part needs mono's mcs, else it is skipped)

1. real repeated prints are kept: two identical trades in one millisecond stay two rows (FOUND: drop_duplicates kept one, so
   every busy second's volume and delta came out too small); re-ingesting the same file adds nothing; a grown file adds its
   new rows only.
2. ingest reads only CSVs that changed (FOUND: every run re-read and re-wrote every day since recording began, each minute,
   on the trading PC); a raw CSV more than RAW_KEEP_DAYS old, once ingested, is deleted (disk bounded).
3. the instrument list follows the front contract while recording (FOUND: written once at enable: after the Dec roll the
   recorder kept the expiring 12-26); nothing is written while OFF.
5. the NT8 export import (day-ofprogram): UTC stamps, repeated prints kept, 3-field lines, re-import adds nothing.
4. ninjatrader/LE_TickRec.cs compiles as C# 5 against tests/nt8_stub (the NT8 AddOn / MarketData API it uses), has the
   low-disk stop (10 GB) and the locked subscribe / unsubscribe, and still no Account / Order / ATI code.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import tickrec as T  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if (info is not None and not isinstance(info, str) or info) and not ok else ''}")
    RES.append(bool(ok))


def main():
    keep = (T.TICK_DIR, T.CFG_PATH, os.environ.get("OLYMPUS_NT_DIR"), os.environ.get(T.ENV))
    with tempfile.TemporaryDirectory() as tmp:
        T.TICK_DIR = os.path.join(tmp, "ticks")
        T.CFG_PATH = os.path.join(tmp, "tickrec.json")
        nd = os.path.join(tmp, "NinjaTrader 8")
        rd = os.path.join(nd, "le_ticks")
        os.makedirs(rd)
        os.environ["OLYMPUS_NT_DIR"] = nd
        os.environ.pop(T.ENV, None)
        f = os.path.join(rd, "NQ_2026-11-20.csv")
        with open(f, "w") as fh:
            fh.write("t_ms,price,size,bid,ask\n1795167000500,21000.25,3,21000,21000.25\n1795167000500,21000.25,3,21000,21000.25\n"
                     "1795167000500,21000,1,20999.75,21000.25\n")
        r1 = T.ingest(nd, today="2026-11-20")
        d = T.read_day("2026-11-20")
        check("1. two identical prints in one ms stay two rows (3 trades, 7 contracts)", len(d) == 3 and int(d["size"].sum()) == 7, d.to_dict("records") if d is not None else None)
        r2 = T.ingest(nd, today="2026-11-20")
        check("2. unchanged CSV: not read again, nothing added", r2["read"] == 0 and len(T.read_day("2026-11-20")) == 3, r2)
        with open(f, "a") as fh:
            fh.write("1795167001000,21000.5,2,21000.25,21000.5\n")
        os.utime(f, (os.path.getatime(f), os.path.getmtime(f) + 5))
        r3 = T.ingest(nd, today="2026-11-20")
        d = T.read_day("2026-11-20")
        check("1. the grown CSV adds only its new row (4 trades, the repeated print still twice)",
              r3["read"] == 1 and len(d) == 4 and int(d["size"].sum()) == 9, (r3, d))
        g = os.path.join(rd, "ES_2026-11-05.csv")
        with open(g, "w") as fh:
            fh.write("t_ms,price,size,bid,ask\n1793871000000,6800.25,5,6800,6800.25\n")
        r4 = T.ingest(nd, today="2026-11-20")
        check("2. a raw CSV 15 days old: ingested, then deleted (its daily file holds it)",
              "ES_2026-11-05.csv" in r4["removed_raw"] and not os.path.exists(g) and T.read_day("2026-11-05") is not None, r4)
        check("2. today's raw CSV is kept", os.path.exists(f))

        ex = os.path.join(tmp, "NQ 12-26.Last.txt")
        with open(ex, "w") as fh:     # NT8 export = UTC: 14:30 UTC on Nov 20 = 09:30 ET; a repeated print; a 3-field line
            fh.write("20261120 143000 1000000;21000.25;21000;21000.25;2\n20261120 143000 1000000;21000.25;21000;21000.25;2\n"
                     "20261120 143000 2000000;21000;21000;21000.25;9\nbad;line\n20261120 143001 5000000;21000.5;1\n")
        i1 = T.import_file(ex)
        d = T.read_day("2026-11-20")
        nq = d[d.root == "NQ"]
        t0 = __import__("pandas").Timestamp(int(nq.t_ns.min()), tz="UTC").tz_convert(T.ET)
        check("5. NT8 export (UTC): 14:30 UTC = 09:30 ET, the repeated print kept, the 3-field line read, junk skipped",
              i1["root"] == "NQ" and i1["first_et"] == "2026-11-20 09:30:00" and i1["rows"] == 4 and "OK" in i1["tz_check"], (i1, str(t0)))
        before = len(nq)
        i2 = T.import_file(ex)
        d2 = T.read_day("2026-11-20")
        check("5. re-importing the export adds nothing (and keeps the live rows of that day)",
              len(d2[d2.root == "NQ"]) == before, (before, len(d2)))
        check("3. OFF: the instrument list is never written", not T.refresh_instruments(nd, dt.date(2026, 12, 15))
              and not os.path.exists(os.path.join(rd, "instruments.txt")))
        T.set_enabled(True, ["NQ", "ES"])
        with open(os.path.join(rd, "instruments.txt"), "w") as fh:
            fh.write("NQ 12-26\nES 12-26\n")
        rolled = T.refresh_instruments(nd, dt.date(2026, 12, 15))
        lst = open(os.path.join(rd, "instruments.txt")).read().split("\n")
        check("3. recording after the Dec roll: the list moves to 03-27", rolled and lst[:2] == ["NQ 03-27", "ES 03-27"], lst)
        check("3. already the front: not rewritten", not T.refresh_instruments(nd, dt.date(2026, 12, 15)))
        T.set_enabled(False)

    T.TICK_DIR, T.CFG_PATH = keep[0], keep[1]
    for k, v in (("OLYMPUS_NT_DIR", keep[2]), (T.ENV, keep[3])):
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    cs = open(os.path.join(ROOT, "ninjatrader", "LE_TickRec.cs"), encoding="utf-8").read()
    code = "\n".join(ln.split("//")[0] for ln in cs.splitlines())
    check("4. LE_TickRec.cs: the low-disk stop and the locked subscribe / unsubscribe are there",
          "AvailableFreeSpace < MinFreeBytes" in code and "lock (InstLock)" in code)
    check("4. LE_TickRec.cs: no Account / Order / ATI / incoming code",
          not re.search(r"\b(Account|Order|Submit|CreateOrder|incoming|PLACE|CLOSEPOSITION|FLATTEN)\w*\b", code.replace("NinjaTrader.Cbi", "")))
    mcs = shutil.which("mcs")
    if mcs:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([mcs, "-langversion:5", "-target:library", "-out:" + os.path.join(tmp, "t.dll"),
                                os.path.join(ROOT, "tests", "nt8_stub", "NtStub.cs"), os.path.join(ROOT, "ninjatrader", "LE_TickRec.cs")],
                               capture_output=True, text=True)
        check("4. LE_TickRec.cs compiles as C# 5 against the NT8 API stub", r.returncode == 0, (r.stdout + r.stderr)[-400:])
    else:
        print("skip 4. C# compile (no mcs here: apt-get install mono-mcs)")
    ok = sum(RES)
    print(f"\ntickrec red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
