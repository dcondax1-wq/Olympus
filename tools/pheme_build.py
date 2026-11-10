#!/usr/bin/env python3
"""PHEME builder: history of what NQ did on scheduled-release days, from the repo's own saved data. READ ONLY, OFFLINE, stdlib only. It writes tools/web_public/pheme/stats.json for the Pheme page.

    python tools/pheme_build.py                          # data/news/events.csv + data/NQ_5m.csv (+ data/news/hub.json when present) -> tools/web_public/pheme/stats.json
    python tools/pheme_build.py --asof 2026-11-10 --out DIR/stats.json
    python tools/pheme_build.py --check                  # exit 1 when stats.json is not what this script writes now (a test runs it)
    python tools/pheme_build.py --selftest

What it measures (history only, never a forecast; every figure carries its n):
  * for each kind of release (CPI, jobs report, PPI, FOMC decision) and each past release day that the 5m NQ file covers:
      day range   = highest high minus lowest low from 08:00 to 16:00 ET (it holds both release windows; full days only: at least 90 of the 96 five-minute bars), in index points
      window      = the same high-low over the 30 minutes that start at the release time (08:30 or 14:00 ET), in points
  * the same two numbers on ordinary weekdays (no tracked release that day), as the yardstick
  * dollars: points x $2 = one MNQ micro contract (1 NQ point = $20 per NQ, $2 per MNQ micro). A RANGE is not a profit or a loss: it is how far the price travelled.
  * per kind: all days (n), the last 8 days (n=8), the median, and the 8 rows themselves
  * the schedule: the scheduled releases in data/news/events.csv (built from bls.gov and federalreserve.gov by data/build_news.py), plus any newer ones in data/news/hub.json
Times: the 5m file holds epoch seconds (UTC); they are turned into New York time with the zoneinfo rules.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import statistics
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BARS = os.path.join(ROOT, "data", "NQ_5m.csv")
CAL = os.path.join(ROOT, "data", "news", "events.csv")
HUB = os.path.join(ROOT, "data", "news", "hub.json")
OUT = os.path.join(ROOT, "tools", "web_public", "pheme", "stats.json")
USD_PER_POINT = 2.0                         # one MNQ micro
MIN_BARS = 90                               # a full 08:00-16:00 day has 96 five-minute bars
TRACKED = ("cpi", "nfp", "ppi", "fomc")
LABELS = {"cpi": "CPI (consumer prices)", "nfp": "Jobs report (NFP)", "ppi": "PPI (producer prices)", "fomc": "FOMC decision"}
LAST_N = 8
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                           # pragma: no cover
    ET = None


def kind_of(name):
    low = str(name).lower()
    if low.startswith("fomc rate decision"):
        return "fomc"
    if low.startswith("fomc press") or low.startswith("fomc"):
        return None
    for k, keys in (("cpi", ("cpi",)), ("ppi", ("ppi",)), ("nfp", ("non-farm payrolls", "nonfarm")), ("claims", ("unemployment claims",)), ("minutes", ("fed meeting minutes",)),
                    ("pce", ("pce", "personal income")), ("gdp", ("gdp",)), ("ism", ("ism ",)), ("jolts", ("jolts",)), ("adp", ("adp ",))):
        if any(low.startswith(x) for x in keys):
            return k
    return "other"


def read_events(path=CAL, hub=HUB):
    """[{date, time, title, kind, impact, source}] sorted, press conferences dropped, hub.json rows added when they are not already there."""
    rows = []
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                k = kind_of(r.get("event", ""))
                if k is None or not (r.get("date", "")[:4].isdigit() and len(r.get("time_et", "")) == 5):
                    continue
                imp = {"high": "high", "medium": "med"}.get(str(r.get("impact", "")).strip().lower(), "low")
                rows.append({"date": r["date"], "time": r["time_et"], "title": r["event"].strip(), "kind": k, "impact": imp, "source": str(r.get("source", "")).strip()})
    except OSError:
        pass
    have = {(r["date"], r["kind"], r["title"][:12].lower()) for r in rows}
    try:
        with open(hub, encoding="utf-8") as fh:
            h = json.load(fh)
        for e in h.get("events", []) if isinstance(h, dict) else []:
            if not isinstance(e, dict) or e.get("country") not in (None, "USD") or not e.get("date") or not e.get("time_et"):
                continue
            k = kind_of(e.get("title", ""))
            if k is None or (e["date"], k, str(e["title"])[:12].lower()) in have or any(r["date"] == e["date"] and r["kind"] == k and k != "other" for r in rows):
                continue
            rows.append({"date": e["date"], "time": e["time_et"], "title": str(e["title"]).strip()[:80], "kind": k, "impact": {"high": "high", "medium": "med"}.get(str(e.get("impact", "")).lower(), "low"), "source": "data/news/hub.json"})
    except (OSError, ValueError):
        pass
    return sorted(rows, key=lambda r: (r["date"], r["time"], r["title"]))


def load_bars(path=BARS):
    """{date: [(minute_of_day_ET, high, low)]} for bars between 07:00 and 16:00 ET, plus the last date seen. One pass, one zone conversion per row."""
    out, last = {}, ""
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            rd = csv.reader(fh)
            next(rd, None)
            for row in rd:
                try:
                    t, hi, lo = int(row[0]), float(row[2]), float(row[3])
                except (ValueError, IndexError):
                    continue
                d = dt.datetime.fromtimestamp(t, ET)
                mod = d.hour * 60 + d.minute
                ds = d.strftime("%Y-%m-%d")
                if ds > last:
                    last = ds
                if 420 <= mod < 960 and d.weekday() < 5:
                    out.setdefault(ds, []).append((mod, hi, lo))
    except OSError:
        pass
    return out, last


def day_range(bars):
    rth = [b for b in bars if 480 <= b[0] < 960]
    return round(max(b[1] for b in rth) - min(b[2] for b in rth), 2) if len(rth) >= MIN_BARS else None


def window_range(bars, hm):
    start = int(hm[:2]) * 60 + int(hm[3:])
    w = [b for b in bars if start <= b[0] < start + 30]
    return round(max(b[1] for b in w) - min(b[2] for b in w), 2) if len(w) >= 5 else None


def summ(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return {"n": 0, "avg": None, "median": None}
    return {"n": len(v), "avg": round(sum(v) / len(v), 1), "median": round(statistics.median(v), 1)}


def build(events, bars, last_bar_day, asof):
    tracked_days = {r["date"] for r in events if r["kind"] in TRACKED}
    times = sorted({r["time"] for r in events if r["kind"] in TRACKED})
    base_days = [d for d in sorted(bars) if d not in tracked_days and day_range(bars[d]) is not None]
    base = {"days": len(base_days), "day": summ([day_range(bars[d]) for d in base_days]), "window": {tm: summ([window_range(bars[d], tm) for d in base_days]) for tm in times}}
    kinds = {}
    for k in TRACKED:
        evs = [r for r in events if r["kind"] == k and r["date"] in bars]
        used = []
        for r in evs:
            dr, wr = day_range(bars[r["date"]]), window_range(bars[r["date"]], r["time"])
            if dr is not None and wr is not None:
                used.append({"date": r["date"], "time": r["time"], "day_range": dr, "window_range": wr})
        last = used[-LAST_N:]
        kinds[k] = {"label": LABELS[k], "time": (used[-1]["time"] if used else (evs[-1]["time"] if evs else "")), "n_listed": len([r for r in events if r["kind"] == k]), "n_with_data": len(used),
                    "all": {"day": summ([u["day_range"] for u in used]), "window": summ([u["window_range"] for u in used])},
                    "last": {"day": summ([u["day_range"] for u in last]), "window": summ([u["window_range"] for u in last])},
                    "rows": [{**u, "day_usd": round(u["day_range"] * USD_PER_POINT), "window_usd": round(u["window_range"] * USD_PER_POINT)} for u in reversed(last)]}
    lo = (dt.date.fromisoformat(asof) - dt.timedelta(days=60)).isoformat()
    sched = [r for r in events if r["date"] >= lo]
    return {"v": 1, "built": asof, "last_bar_day": last_bar_day, "usd_per_point": USD_PER_POINT, "last_n": LAST_N, "min_bars": MIN_BARS,
            "source": {"calendar": "data/news/events.csv (bls.gov, federalreserve.gov via data/build_news.py), data/news/hub.json when newer", "bars": "data/NQ_5m.csv (TradingView CME NQ1! 5m)"},
            "label": "History, not a forecast: how far NQ travelled on past release days. A range is not a profit or a loss.",
            "baseline": base, "kinds": kinds, "events": sched, "calendar_last_date": events[-1]["date"] if events else ""}


def render(o):
    return json.dumps(o, indent=1, ensure_ascii=False) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pheme builder: NQ history on release days (offline, stdlib).")
    ap.add_argument("--asof", help="the date the file says it was built (default: the last date in the saved calendar's file name... or today)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--bars", default=BARS)
    ap.add_argument("--calendar", default=CAL)
    ap.add_argument("--hub", default=HUB)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    asof = a.asof
    if not asof:
        try:
            asof = json.load(open(a.out, encoding="utf-8")).get("built")
        except (OSError, ValueError, AttributeError):
            asof = None
    asof = asof or dt.date.today().isoformat()
    bars, last = load_bars(a.bars)
    text = render(build(read_events(a.calendar, a.hub), bars, last, asof))
    if a.check:
        try:
            ok = open(a.out, encoding="utf-8").read() == text
        except OSError:
            ok = False
        print("stats.json is in step" if ok else "stats.json is NOT what pheme_build.py writes: run  python tools/pheme_build.py")
        return 0 if ok else 1
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, a.out)
    print(f"wrote {a.out} (as of {asof}, bars to {last})")
    return 0


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    bad = []

    def ck(name, ok, info=""):
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"))
        if not ok:
            bad.append(name)
    d = tempfile.mkdtemp(prefix="pheme-")
    bars, cal = os.path.join(d, "NQ_5m.csv"), os.path.join(d, "events.csv")

    def epoch(ds, hm):
        y, m, dd = map(int, ds.split("-"))
        return int(dt.datetime(y, m, dd, int(hm[:2]), int(hm[3:]), tzinfo=ET).timestamp())
    rows = ["time,open,high,low,close,volume"]
    days = [("2026-10-27", 20), ("2026-10-28", 40), ("2026-10-29", 20), ("2026-10-30", 20), ("2026-11-02", 20), ("2026-11-03", 60), ("2026-11-04", 20)]
    for ds, rng in days:                                   # Oct 27-30 EDT, Nov 2-4 EST (the clocks went back on Nov 1)
        t = epoch(ds, "07:00")
        end = epoch(ds, "16:00")
        i = 0
        while t < end:
            base = 1000.0
            hi = base + (rng if (t == epoch(ds, "10:00")) else 1)
            lo = base - 1
            if ds == "2026-11-03" and t == epoch(ds, "08:30"):
                hi = base + 15                              # a big 08:30 bar on the CPI day
            rows.append(f"{t},{base},{hi},{lo},{base},1")
            t += 300
            i += 1
    open(bars, "w").write("\n".join(rows) + "\n")
    open(cal, "w").write("date,time_et,event,impact,source\n2026-10-28,14:00,FOMC rate decision,high,federalreserve.gov\n2026-10-28,14:30,FOMC press conference,high,federalreserve.gov\n"
                         "2026-11-03,08:30,CPI (consumer inflation),high,bls.gov\n2026-11-12,08:30,CPI (consumer inflation),high,bls.gov\n2026-11-04,08:30,Unemployment Claims,medium,dol.gov\n")
    ev = read_events(cal, os.path.join(d, "none.json"))
    ck("events: the press conference is dropped, kinds are read (fomc, cpi, claims), impact words are mapped", [e["kind"] for e in ev] == ["fomc", "cpi", "claims", "cpi"] and ev[0]["impact"] == "high" and ev[2]["impact"] == "med", ev)
    b, last = load_bars(bars)
    ck("bars: grouped by New York day across the Nov 1 clock change (Oct 30 and Nov 2 both start at 07:00 ET), last day found", min(x[0] for x in b["2026-10-30"]) == 420 and min(x[0] for x in b["2026-11-02"]) == 420 and last == "2026-11-04", (sorted(b)[:2], last))
    ck("day range: 41 on the 28th (high 1040 minus low 999), 21 on an ordinary day", day_range(b["2026-10-28"]) == 41.0 and day_range(b["2026-10-29"]) == 21.0, (day_range(b["2026-10-28"]), day_range(b["2026-10-29"])))
    ck("a half day (fewer than 90 bars) gives no day range", day_range([(570, 1, 0)] * 10) is None and window_range([(510, 1, 0)] * 3, "08:30") is None)
    ck("window range: the 08:30-09:00 window on the CPI day holds the 15-point bar (range 16), an ordinary day 2", window_range(b["2026-11-03"], "08:30") == 16.0 and window_range(b["2026-11-02"], "08:30") == 2.0)
    out = build(ev, b, last, "2026-11-10")
    k = out["kinds"]
    ck("CPI: listed 2 (Nov 12 has no bars), 1 with data, the row has the day range 61, the window 16 and dollars at $2 a point (122 and 32); FOMC 1 with data",
       k["cpi"]["n_listed"] == 2 and k["cpi"]["n_with_data"] == 1 and k["cpi"]["rows"][0]["day_range"] == 61.0 and k["cpi"]["rows"][0]["day_usd"] == 122 and k["cpi"]["rows"][0]["window_usd"] == 32 and k["fomc"]["n_with_data"] == 1, k["cpi"])
    ck("n is always there and an empty kind says n 0 with no averages (nothing invented)", k["cpi"]["all"]["day"]["n"] == 1 and k["nfp"]["all"]["day"] == {"n": 0, "avg": None, "median": None} and k["nfp"]["rows"] == [])
    ck("baseline: ordinary days exclude the tracked release days (Oct 28 FOMC, Nov 3 CPI; claims are not tracked): 5 days, average range 21", out["baseline"]["days"] == 5 and out["baseline"]["day"]["avg"] == 21.0 and out["baseline"]["window"]["08:30"]["n"] == 5, out["baseline"])
    ck("the label says history, not a forecast", "not a forecast" in out["label"] and out["usd_per_point"] == 2.0)
    ck("deterministic", render(out) == render(build(read_events(cal, os.path.join(d, 'none.json')), *load_bars(bars), "2026-11-10")))
    ck("summ: median and average with n; None values are ignored", summ([1, 2, 3, None]) == {"n": 3, "avg": 2.0, "median": 2.0} and summ([]) == {"n": 0, "avg": None, "median": None})
    o = os.path.join(d, "stats.json")
    ck("write then --check agree, and drift fails", main(["--out", o, "--bars", bars, "--calendar", cal, "--hub", os.path.join(d, "n.json"), "--asof", "2026-11-10"]) == 0 and main(["--out", o, "--bars", bars, "--calendar", cal, "--hub", os.path.join(d, "n.json"), "--check"]) == 0)
    open(o, "a").write(" ")
    ck("a drifted file fails --check", main(["--out", o, "--bars", bars, "--calendar", cal, "--hub", os.path.join(d, "n.json"), "--check"]) == 1)
    import re
    code = open(os.path.abspath(__file__), encoding="utf-8").read().split("# ----", 1)[0]
    ck("offline and read only: no network import", not re.search(r"^\s*(import|from)\s+(urllib|requests|socket|http|ssl)\b", code, re.M))
    print(f"\n{'ALL PASS' if not bad else str(len(bad)) + ' FAILED'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
