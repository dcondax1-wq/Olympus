"""The stale research files (night-cleanup 2026-11-22): tools/context_refresh.py (CBOE vol + GEX + VIX / VXN), the daily bars
(data/import_futures.build_daily) and the PC answer the cloud used to refuse (engine/datafeed.DAY_FILE vs pack_day's names).

    python -X utf8 -m tests.test_context_refresh     # ~5 s, fakes only (no network)

a. CBOE history files, both shapes (DATE,OPEN,HIGH,LOW,CLOSE and DATE,VVIX) -> closes; the new host first, the old as fallback
b. CBOE_vol_1d: new days appended, a blank cell of a recent day completed, older rows untouched, CRLF kept, a dead source = no change
c. GEX_1d: append-only from DIX.csv; an error page / wrong header never touches the file
d. build_daily: CME day 18:00 -> 17:00 ET, stamped 00:00 UTC, OHLCV = the 1h bars; an unfinished day is left out; append-only
e. datafeed.DAY_FILE accepts every file name datafeed.pack_day can write (fills.jsonl.gz was refused from Nov 20 on)
f. data_health names the fix for each stale file kind; the CBOE URL is the new host everywhere
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
RESULTS = []
ET = ZoneInfo("America/New_York")


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   -> {info!r}"[:600]))


def ohlc(rows):
    return ("DATE,OPEN,HIGH,LOW,CLOSE\n" + "".join(f"{d},{c},{c},{c},{c}\n" for d, c in rows)).encode()


def one(name, rows):
    return (f"DATE,{name}\n" + "".join(f"{d},{c}\n" for d, c in rows)).encode()


def fake_cboe(files, dead=()):
    calls = []

    def fetch(url):
        calls.append(url)
        name = url.rsplit("/", 1)[-1].replace("_History.csv", "")
        if name in dead or "cdn-api" not in url:
            raise OSError("down")
        return files[name]
    fetch.calls = calls
    return fetch


def part_a(CR):
    c = CR.cboe_closes(ohlc([("11/19/2026", 29.26), ("11/20/2026", 40.72)]))
    check("a. OHLC file -> {date: close}", c == {"2026-11-19": 29.26, "2026-11-20": 40.72}, c)
    c = CR.cboe_closes(one("VVIX", [("11/20/2026", 138.03)]))
    check("a. two-column file (VVIX / SKEW) -> its value", c == {"2026-11-20": 138.03}, c)
    f = fake_cboe({"VIX9D": ohlc([("11/20/2026", 40.72)])})
    got = CR.cboe_fetch("VIX9D", f)
    check("a. the new host (cdn-api.cboe.com) is asked first", got and "cdn-api.cboe.com" in f.calls[0], f.calls)
    try:
        CR.cboe_closes(b"<html>nope</html>")
        check("a. an HTML page is refused", False)
    except ValueError:
        check("a. an HTML page is refused", True)


def part_b(CR, tmp):
    p = os.path.join(tmp, "CBOE_vol_1d.csv")
    old = ["date,vix9d,vix3m,vix1d,vvix,skew", "2026-09-16,17.4,19.73,17.01,95.41,145.95", "2026-09-17,13.39,18.55,13.12,87.72,"]
    with open(p, "wb") as fh:
        fh.write(("\r\n".join(old) + "\r\n").encode())
    files = {"VIX9D": ohlc([("09/17/2026", 13.39), ("09/18/2026", 12.27)]), "VIX3M": ohlc([("09/17/2026", 18.55), ("09/18/2026", 18.24)]),
             "VIX1D": ohlc([("09/17/2026", 13.12), ("09/18/2026", 11.42)]), "VVIX": one("VVIX", [("09/17/2026", 87.72), ("09/18/2026", 87.38)]),
             "SKEW": one("SKEW", [("09/16/2026", 999.0), ("09/17/2026", 145.7), ("09/18/2026", 148.1)])}
    line = CR.refresh_cboe_vol(tmp, fake_cboe(files))
    raw = open(p, "rb").read()
    rows = raw.decode().split("\r\n")
    check("b. +1 day, the 09-17 SKEW blank completed", "+1 day" in line and rows[3] == "2026-09-18,12.27,18.24,11.42,87.38,148.1"
          and rows[2] == "2026-09-17,13.39,18.55,13.12,87.72,145.7", (line, rows))
    check("b. CRLF kept, the header and older lines byte-identical", raw.startswith(("\r\n".join(old[:1]) + "\r\n").encode())
          and b"\n" not in raw.replace(b"\r\n", b""), raw[:80])
    check("b. a recent row is completed from CBOE (inside the last 10 dates)", rows[1] == "2026-09-16,17.4,19.73,17.01,95.41,999", rows[1])
    before = open(p, "rb").read()
    line = CR.refresh_cboe_vol(tmp, fake_cboe(files, dead={"VIX9D", "VIX3M", "VIX1D", "VVIX", "SKEW"}))
    check("b. every source down: nothing changed", open(p, "rb").read() == before and "nothing changed" in line, line)
    line = CR.refresh_cboe_vol(tmp, fake_cboe(files))
    check("b. run twice: up to date, file unchanged", "up to date" in line and open(p, "rb").read() == before, line)


def part_c(CR, tmp):
    p = os.path.join(tmp, "GEX_1d.csv")
    with open(p, "w", newline="") as fh:
        fh.write("date,price,dix,gex\n2026-10-15,7600.0,0.44,1.0\n2026-10-16,7659.44,0.4465,94244460.13\n")
    good = b"date,price,dix,gex\n2026-10-16,7659.44,0.4465,94244460.13\n2026-10-19,7700.0,0.45,2.5\n"
    line = CR.refresh_gex(tmp, lambda u: good)
    txt = open(p).read()
    check("c. +1 GEX day, older rows kept, LF kept", "+1 day" in line and txt.endswith("2026-10-19,7700.0,0.45,2.5\n")
          and txt.startswith("date,price,dix,gex\n2026-10-15,7600.0,0.44,1.0\n"), (line, txt))
    before = open(p, "rb").read()
    line = CR.refresh_gex(tmp, lambda u: b"<html>Rate limited</html>")
    check("c. an error page never touches the file", open(p, "rb").read() == before and "nothing changed" in line, line)
    line = CR.refresh_gex(tmp, lambda u: (_ for _ in ()).throw(OSError("down")))
    check("c. no answer: nothing changed", open(p, "rb").read() == before, line)


def part_d(tmp):
    import pandas as pd
    sys.path.insert(0, os.path.join(ROOT, "data"))
    import import_futures as IF
    d0 = dt.date(2026, 11, 18)
    pd.DataFrame({"time": [int(dt.datetime(2026, 11, 17, tzinfo=dt.timezone.utc).timestamp())], "open": [1.0], "high": [1.0],
                  "low": [1.0], "close": [1.0], "volume": [1]}).to_csv(os.path.join(tmp, "NQ_1d.csv"), index=False)
    rows = []
    for k, day in enumerate((d0, d0 + dt.timedelta(days=1), d0 + dt.timedelta(days=2))):
        start = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(18, 0), ET)
        hours = 23 if k < 2 else 10                     # the third day is unfinished (no 16:00 ET hour, no later day)
        for h in range(hours):
            t = start + dt.timedelta(hours=h)
            if t.hour == 17:
                continue
            base = 100 * (k + 1) + h
            rows.append({"time": int(t.timestamp()), "open": base, "high": base + 5, "low": base - 5, "close": base + 1, "volume": 10})
    pd.DataFrame(rows).to_csv(os.path.join(tmp, "NQ_1h.csv"), index=False)
    n = IF.build_daily("NQ", tmp)
    d = pd.read_csv(os.path.join(tmp, "NQ_1d.csv"))
    stamps = [dt.datetime.fromtimestamp(int(x), dt.timezone.utc) for x in d["time"]]
    check("d. 2 finished days added, the unfinished one left out", n == 2 and len(d) == 3, (n, d.to_dict("records")))
    check("d. stamped the CME day at 00:00 UTC", [s.date() for s in stamps[1:]] == [d0, d0 + dt.timedelta(days=1)]
          and all(s.hour == 0 for s in stamps), stamps)
    r = d.iloc[1]
    check("d. OHLCV = first open / max high / min low / last close / sum volume of the day's hours",
          (r.open, r.high, r.low, r.close, r.volume) == (100, 100 + 22 + 5, 100 - 5, 100 + 22 + 1, 230), r.to_dict())
    check("d. the old row is untouched, run twice adds nothing", d.iloc[0].open == 1.0 and IF.build_daily("NQ", tmp) == 0)


def part_e():
    import io
    import zipfile
    from engine import datafeed as DF
    names = ["manifest.json", "trades.jsonl.gz", "fills.jsonl.gz", "gaps.json"] + list(DF.EXTRAS) + \
            [f"bars/{r}_{tf}.csv.gz" for r in ("MNQ", "NQ", "MES", "ES") for tf in ("1m", "5m")]
    bad = [n for n in names if not DF.DAY_FILE.match(f"days/2026-11-20/{n}")]
    check("e. DAY_FILE accepts every name pack_day writes (fills.jsonl.gz included)", not bad, bad)
    src = open(os.path.join(ROOT, "engine", "datafeed.py"), encoding="utf-8").read()
    body = src[src.index("def pack_day("):src.index("return files", src.index("def pack_day("))]
    import re
    lit = set(re.findall(r'files\["([^"]+)"\]', body))
    check("e. every literal file name in pack_day is allowed", lit and all(DF.DAY_FILE.match(f"days/2026-11-20/{n}") for n in lit), sorted(lit))
    check("e. a stranger name is still refused", not DF.DAY_FILE.match("days/2026-11-20/../../x.py")
          and not DF.DAY_FILE.match("days/2026-11-20/evil.exe"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("days/2026-11-20/fills.jsonl.gz", b"x")
    try:
        DF.extract(buf.getvalue(), tempfile.mkdtemp(prefix="cr_x_"))
        ok, why = True, ""
    except ValueError as e:
        ok, why = "unexpected file" not in str(e), str(e)
    check("e. a bundle with fills.jsonl.gz is no longer 'unexpected' (it fails only for its missing manifest)", ok, why)


def part_f():
    from tools import data_health as DH
    check("f. data_health says the fix for CBOE / GEX / VIX / ES / 1d", all(k in DH.WHY for k in ("CBOE", "GEX", "VIX", "ES", "1d"))
          and "context_refresh" in DH.WHY["CBOE"] and "build_daily" in DH.WHY["1d"])
    from engine import news
    from tools.pantheon import sources
    check("f. the CBOE URL is the new host in engine/news.py and tools/pantheon/sources.py",
          "cdn-api.cboe.com" in news.CBOE_URL and "cdn-api.cboe.com" in sources.CBOE)
    g = open(os.path.join(ROOT, "engine", "gamma.py"), encoding="utf-8").read()
    check("f. engine/gamma.refresh_history writes only a real DIX.csv", 'startswith(b"date,price,dix,gex")' in g and "os.replace(tmp, path)" in g)


def main():
    from tools import context_refresh as CR
    tmp = tempfile.mkdtemp(prefix="ctx_refresh_")
    try:
        for p, a in ((part_a, (CR,)), (part_b, (CR, tmp)), (part_c, (CR, tmp)), (part_d, (tmp,)), (part_e, ()), (part_f, ())):
            try:
                p(*a)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{p.__name__} ran", False, f"{e.__class__.__name__}: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
