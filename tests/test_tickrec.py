"""engine/tickrec.py + ninjatrader/LE_TickRec.cs: the READ-ONLY tick recorder (day-orderflow 2026-11-23).

Temp folders only (never this PC's NinjaTrader folder, never data/ticks):
  a. off by default; enable / disable write and remove le_ticks\\enabled.txt + instruments.txt; the env switch
  b. side: quote rule then tick rule; NT8 export (5-field and 3-field) parse, ET time, de-duplicated re-import, tz check
  c. ingest of LE_TickRec CSVs (torn line, junk) -> daily files; footprint delta / POC / CVD
  d. safety: tickrec.py imports nothing that trades, names no incoming\\ folder or OIF command; LE_TickRec.cs uses no
     Account / Order / ATI call; nothing in the bot imports engine.tickrec
  python -X utf8 -m tests.test_tickrec
"""
from __future__ import annotations

import glob
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import tickrec as T  # noqa: E402

P = F = 0


def ok(cond, what):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print("FAIL:", what)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        T.TICK_DIR = os.path.join(tmp, "ticks")
        T.CFG_PATH = os.path.join(tmp, "tickrec.json")
        nd = os.path.join(tmp, "NinjaTrader 8")
        os.makedirs(nd)
        os.environ["OLYMPUS_NT_DIR"] = nd
        os.environ.pop(T.ENV, None)
        # a
        ok(T.is_enabled() is False, "off by default")
        T.set_enabled(True, ["NQ", "ES", "XX"])
        ok(T.is_enabled(), "enable")
        ok(os.path.exists(os.path.join(nd, "le_ticks", "enabled.txt")), "flag written")
        lst = open(os.path.join(nd, "le_ticks", "instruments.txt")).read().split()
        ok(lst[0] == "NQ" and lst[2] == "ES" and "XX" not in lst, "instrument list %s" % lst)
        T.set_enabled(False)
        ok(not T.is_enabled() and not os.path.exists(os.path.join(nd, "le_ticks", "enabled.txt")), "disable removes the flag")
        os.environ[T.ENV] = "1"; ok(T.is_enabled(), "env switch"); os.environ.pop(T.ENV)
        # b
        ok(list(T.classify([10.0, 10.25, 10.25, 10.0], [10.0, 0, 10.0, 9.75], [10.25, 0, 10.25, 10.25])) == [-1, 1, 1, -1], "classify")
        ex = os.path.join(tmp, "NQ 12-26.Last.txt")
        with open(ex, "w") as f:
            f.write("20261120 093000 0000000;21000.25;21000;21000.25;3\n"
                    "20261120 093000 1000000;21000;21000;21000.25;2\n"
                    "garbage line\n20261120 093001;21000.5;4\n")
        df = T.parse_nt_export(ex, "NQ")
        ok(len(df) == 3 and list(df.side) == [1, -1, 1], "export parse %s" % list(df.side))
        ok(int(df.t_ns.iloc[1] - df.t_ns.iloc[0]) == 100_000_000, "sub-second stamp")
        T.write_days(df); T.write_days(df)
        ok(len(T.read_day("2026-11-20")) == 3, "re-import is de-duplicated")
        ok(T.tz_check(df).startswith("OK"), "tz check " + T.tz_check(df))
        # c
        rd = os.path.join(nd, "le_ticks")
        with open(os.path.join(rd, "ES_2026-11-20.csv"), "w") as f:
            f.write("t_ms,price,size,bid,ask\n1795185000000,6700.25,5,6700,6700.25\n1795185000100,6700,1,6700,6700.25\nxx,1\n1795185000")
        r = T.ingest()
        ok(r["ok"] and r["rows"] == 2, "ingest %s" % r)
        es = T.load("2026-11-20", "2026-11-20", "ES")
        ok(len(es) == 2 and list(es.side) == [1, -1], "ES rows")
        fp = T.footprint(T.load("2026-11-20", "2026-11-20", "NQ"), 5)
        ok(int(fp.delta.iloc[0]) == 5 and float(fp.poc.iloc[0]) == 21000.5 and int(fp.cvd.iloc[-1]) == 5, "footprint %s" % fp.to_dict("records"))
    # d
    src = open(os.path.join(ROOT, "engine", "tickrec.py"), encoding="utf-8").read()
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    ok(not re.search(r"^\s*(from|import)\s+[.\w]*(ninjatrader|live|tradovate|lit_live|account)", code, re.M), "no trading imports")
    ok("incoming" not in code and not re.search(r"PLACE|CLOSEPOSITION|FLATTEN", code), "no OIF in tickrec.py")
    cs = open(os.path.join(ROOT, "ninjatrader", "LE_TickRec.cs"), encoding="utf-8").read()
    cs_code = "\n".join(l for l in cs.splitlines() if not l.strip().startswith("//"))
    ok(not re.search(r"\bAccount\b|Submit|CreateOrder|Cancel|Flatten|incoming|\$\"|\?\.", cs_code), "LE_TickRec.cs read-only + C# 5")
    users = [p for p in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True)
             if "tickrec" not in os.path.basename(p) and "orderflow" not in p and "/scratch" not in p
             and re.search(r"engine\.tickrec|from \. import tickrec|import tickrec", open(p, encoding="utf-8", errors="replace").read())]
    ok(users == [], "nothing imports engine.tickrec: %s" % users)
    print("test_tickrec: %d passed, %d failed" % (P, F))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
