"""NQ "data ports" for the NQ page (day-nqports 2026-11-27): one file, tools/web_public/nq/ports.json, read by nq/ports.js.

Futures prices only (data/NQ_*.csv, data/ES_*.csv: TradingView CME exports + the PC's NinjaTrader bars), the CBOE / SqueezeMetrics files
tools/context_refresh.py keeps (data/CBOE_vol_1d.csv, VIX_1d, VXN_1d, GEX_1d), the CFTC's free public API (Traders in Financial Futures,
NASDAQ MINI, code 209742; cached in data/cot/nq_tff.json so an offline build still has the last weeks), the CME calendar
(engine/cme_calendar) and the roll (engine/roll_watch), the high-impact news list (data/news/events.csv). No key, no paid source.

Sections (each carries its own date so the page can stamp its age):
  vol      VIX term structure (VIX9D / VIX / VIX3M: contango = calm, backwardation = stress), VVIX, VXN, SKEW, dealer gamma (GEX) + DIX,
           and LIT's own VIX band + target size today (the 18:00-open rule: close x VIX / 100 / sqrt(252) pts; $2 a point per MNQ)
  normal   the last 20 sessions' medians: Asia range (18:00-02:00 ET), overnight range (18:00-09:30), full-day range; where the session
           high / low usually prints (by window, last 120 sessions); ES vs NQ over the last day and week (daily closes)
  sweeps   base rates 2021-26 from the 5-minute bars: how often a session takes the prior day's high / low, and how often London / New York
           take the Asia high / low (the levels LIT trades), all days + the last 60; the prior day's levels for the live check
  cot      CFTC weekly positioning: leveraged funds (hedge funds / CTAs), asset managers, dealers: net contracts, the week's change,
           where the hedge funds' net sits in its 3-year range (context, never a signal)
  cal      the next 45 days: CME half days / closures, the next contract roll, high-impact US releases (with LIT's flat-5-min rule)

Run (cloud side, in the site build, after the data refresh):  python tools/nq_ports.py            (fetches the CFTC weeks, ~1 s)
                                                              python tools/nq_ports.py --offline  (no network: the cached COT weeks)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import statistics as st
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "tools", "web_public", "nq", "ports.json")
COT_CACHE = os.path.join(DATA, "cot", "nq_tff.json")
COT_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
COT_CODE = "209742"                      # NASDAQ MINI (CME): the E-mini; MNQ positions are reported inside it
ET = ZoneInfo("America/New_York")
BANDS = ((15.0, "calm"), (20.0, "normal"), (30.0, "elevated"), (1e9, "high"))   # = tools/premarket_brief.BANDS (LIT's VIX bands)
WINDOWS = (("asia", 1080, 120, "Asia (18:00-02:00)"), ("london", 120, 480, "London (02:00-08:00)"), ("nyopen", 480, 660, "NY open (08:00-11:00)"),
           ("midday", 660, 840, "Midday (11:00-14:00)"), ("late", 840, 1020, "Late (14:00-17:00)"))


def _r(x, n=2):
    return None if x is None else round(float(x), n)


def band(v):
    return None if v is None else next(name for top, name in BANDS if float(v) < top)


def read_csv(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def pct_rank(series, v):
    xs = [x for x in series if x is not None]
    return None if v is None or len(xs) < 20 else round(100.0 * sum(1 for x in xs if x <= v) / len(xs))


# ------------------------------------------------------------------------------------------------ vol
def vol_section():
    cb = [r for r in read_csv("CBOE_vol_1d.csv") if r.get("date")]
    vix = {r["date"]: fnum(r["close"]) for r in read_csv("VIX_1d.csv") if r.get("date")}
    vxn = {r["date"]: fnum(r["close"]) for r in read_csv("VXN_1d.csv") if r.get("date")}
    gx = [r for r in read_csv("GEX_1d.csv") if r.get("date")]
    nq = read_csv("NQ_1d.csv")
    if not cb or not vix:
        return None
    last = cb[-1]
    d = last["date"]
    vk = max(k for k in vix if k <= d) if any(k <= d for k in vix) else max(vix)
    v, v9, v3 = vix.get(vk), fnum(last.get("vix9d")), fnum(last.get("vix3m"))
    vv, sk = fnum(last.get("vvix")), fnum(last.get("skew"))
    if v9 is not None and v is not None and v3 is not None:
        struct = "contango" if v9 < v < v3 else "backwardation" if v9 > v > v3 else "mixed"
    else:
        struct = None
    ratio = _r(v / v3, 3) if v and v3 else None
    gl = gx[-1] if gx else None
    gex = fnum(gl["gex"]) if gl else None
    dix = fnum(gl["dix"]) if gl else None
    gex_hist = [fnum(r["gex"]) for r in gx[-252:]]
    nq_close = fnum(nq[-1]["close"]) if nq else None
    nq_day = dt.datetime.fromtimestamp(int(float(nq[-1]["time"])), dt.timezone.utc).date().isoformat() if nq else None
    move = nq_close * v / 100 / math.sqrt(252) if nq_close and v else None
    vxk = max((k for k in vxn if k <= d), default=None)
    vxn_v = vxn.get(vxk) if vxk else None
    return {
        "date": d, "vix_date": vk, "vix": _r(v), "vix9d": _r(v9), "vix3m": _r(v3), "ratio": ratio, "structure": struct,
        "vvix": _r(vv), "vvix_pct": pct_rank([fnum(r.get("vvix")) for r in cb[-252:]], vv), "skew": _r(sk),
        "vxn": _r(vxn_v), "vxn_date": vxk, "vxn_move": _r(nq_close * vxn_v / 100 / math.sqrt(252), 0) if nq_close and vxn_v else None,
        "gex": _r(gex / 1e9, 2) if gex is not None else None, "gex_pct": pct_rank(gex_hist, gex), "dix": _r(dix * 100, 1) if dix is not None else None,
        "dix_pct": pct_rank([fnum(r["dix"]) for r in gx[-252:]], dix), "gex_date": gl["date"] if gl else None,
        "band": band(v), "nq_close": _r(nq_close), "nq_day": nq_day, "move_pts": _r(move, 0), "move_usd_mnq": _r(move * 2, 0) if move else None,
        "vix_hist": [[r["date"], fnum(r.get("vix9d")), vix.get(r["date"]), fnum(r.get("vix3m"))] for r in cb[-30:]],
    }


# ------------------------------------------------------------------------------------------------ sessions from the 5-minute bars
def sessions(name="NQ_5m.csv", since="2021-01-01"):
    """{cme_day: {hi, lo, hi_m, lo_m, asia_hi, asia_lo, on_hi, on_lo, post2_hi, post2_lo, post2_hi_m, post2_lo_m, o1800, close}} (minutes ET)"""
    out = {}
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return out
    t0 = dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc).timestamp()
    with open(p, encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd, None)
        for row in rd:
            try:
                t = int(float(row[0]))
                if t < t0:
                    continue
                o, h, lo, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
            except (ValueError, IndexError):
                continue
            e = dt.datetime.fromtimestamp(t, ET)
            m = e.hour * 60 + e.minute
            if 1020 <= m < 1080:              # the CME break (17:00-18:00)
                continue
            day = (e + dt.timedelta(hours=6)).date().isoformat()
            s = out.get(day)
            if s is None:
                s = out[day] = {"hi": h, "lo": lo, "hi_m": m, "lo_m": m, "asia_hi": None, "asia_lo": None, "on_hi": None, "on_lo": None,
                                "post2_hi": None, "post2_lo": None, "post2_hi_m": None, "post2_lo_m": None, "o1800": o if m == 1080 else None, "close": c, "n": 0}
            s["n"] += 1
            if h > s["hi"]:
                s["hi"], s["hi_m"] = h, m
            if lo < s["lo"]:
                s["lo"], s["lo_m"] = lo, m
            s["close"] = c
            asia = m >= 1080 or m < 120
            if asia:
                s["asia_hi"] = h if s["asia_hi"] is None else max(s["asia_hi"], h)
                s["asia_lo"] = lo if s["asia_lo"] is None else min(s["asia_lo"], lo)
            else:
                if s["post2_hi"] is None or h > s["post2_hi"]:
                    s["post2_hi"], s["post2_hi_m"] = h, m
                if s["post2_lo"] is None or lo < s["post2_lo"]:
                    s["post2_lo"], s["post2_lo_m"] = lo, m
            if m >= 1080 or m < 570:
                s["on_hi"] = h if s["on_hi"] is None else max(s["on_hi"], h)
                s["on_lo"] = lo if s["on_lo"] is None else min(s["on_lo"], lo)
    return {k: v for k, v in out.items() if v["n"] >= 150}     # whole sessions only (a short / missing day would bias the rates)


def win_of(m):
    for wid, a, b, _ in WINDOWS:
        if (a < b and a <= m < b) or (a > b and (m >= a or m < b)):
            return wid
    return "late"


def normal_section(S):
    days = sorted(S)
    if len(days) < 25:
        return None
    last20 = days[-20:]
    med = lambda f: _r(st.median([f(S[d]) for d in last20 if f(S[d]) is not None]), 0)
    tail = days[-120:]
    def dist(key):
        c = {w[0]: 0 for w in WINDOWS}
        for d in tail:
            c[win_of(S[d][key])] += 1
        return [{"id": w[0], "label": w[3], "pct": round(100 * c[w[0]] / len(tail))} for w in WINDOWS]
    nq = read_csv("NQ_1d.csv")
    es = read_csv("ES_1d.csv")
    def closes(rows):
        return {dt.datetime.fromtimestamp(int(float(r["time"])), dt.timezone.utc).date().isoformat(): fnum(r["close"]) for r in rows}
    cn, ce = closes(nq), closes(es)
    common = sorted(set(cn) & set(ce))
    esnq = None
    if len(common) >= 6:
        a, b, c = common[-1], common[-2], common[-6]
        p = lambda x, y: _r(100 * (x / y - 1), 2) if x and y else None
        esnq = {"day": a, "nq_1d": p(cn[a], cn[b]), "es_1d": p(ce[a], ce[b]), "nq_5d": p(cn[a], cn[c]), "es_5d": p(ce[a], ce[c])}
    return {"date": days[-1], "n": len(last20), "asia": med(lambda s: s["asia_hi"] - s["asia_lo"] if s["asia_hi"] is not None else None),
            "overnight": med(lambda s: s["on_hi"] - s["on_lo"] if s["on_hi"] is not None else None), "day": med(lambda s: s["hi"] - s["lo"]),
            "high_at": dist("hi_m"), "low_at": dist("lo_m"), "n_at": len(tail), "esnq": esnq}


def sweeps_section(S):
    days = sorted(S)
    if len(days) < 70:
        return None
    def rates(ds):
        n = pdh = pdl = both = ah = al = ah_ny = al_ny = 0
        for i, d in enumerate(ds):
            j = days.index(d)
            if j == 0:
                continue
            p, s = S[days[j - 1]], S[d]
            n += 1
            th, tl = s["hi"] > p["hi"], s["lo"] < p["lo"]
            pdh += th
            pdl += tl
            both += th and tl
            if s["asia_hi"] is not None and s["post2_hi"] is not None:
                ah += s["post2_hi"] > s["asia_hi"]
                al += s["post2_lo"] < s["asia_lo"]
        pc = lambda k: round(100 * k / n) if n else None
        return {"n": n, "pdh": pc(pdh), "pdl": pc(pdl), "both": pc(both), "neither": pc(n - pdh - pdl + both), "asia_hi": pc(ah), "asia_lo": pc(al)}
    last = S[days[-1]]
    return {"date": days[-1], "since": days[0], "all": rates(days), "recent": rates(days[-60:]),
            "levels": {"day": days[-1], "pdh": last["hi"], "pdl": last["lo"], "pdc": last["close"]}}


# ------------------------------------------------------------------------------------------------ COT
def fetch_cot(weeks=160):
    q = {"$where": f"cftc_contract_market_code='{COT_CODE}'", "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": str(weeks)}
    req = urllib.request.Request(COT_URL + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "olympus-nq-ports/1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.load(r)
    keep = []
    for x in rows:
        i = lambda k: int(float(x.get(k) or 0))
        keep.append({"date": str(x.get("report_date_as_yyyy_mm_dd", ""))[:10], "oi": i("open_interest_all"),
                     "lev_l": i("lev_money_positions_long"), "lev_s": i("lev_money_positions_short"),
                     "am_l": i("asset_mgr_positions_long"), "am_s": i("asset_mgr_positions_short"),
                     "dl_l": i("dealer_positions_long_all"), "dl_s": i("dealer_positions_short_all")})
    return sorted([k for k in keep if k["date"]], key=lambda k: k["date"])


def cot_section(offline=False):
    rows, src = None, "cache"
    if not offline:
        try:
            rows = fetch_cot()
            src = "cftc"
            os.makedirs(os.path.dirname(COT_CACHE), exist_ok=True)
            with open(COT_CACHE, "w", encoding="utf-8") as fh:
                json.dump({"made": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "rows": rows}, fh, separators=(",", ":"))
        except Exception as e:                                       # noqa: BLE001 - the cache stands in, said so
            print(f"nq_ports: CFTC fetch failed ({e.__class__.__name__}): using the cache", file=sys.stderr)
            rows = None
    if rows is None:
        try:
            with open(COT_CACHE, encoding="utf-8") as fh:
                rows = json.load(fh)["rows"]
        except (OSError, ValueError, KeyError):
            return None
    if len(rows) < 2:
        return None
    net = lambda r, a: r[a + "_l"] - r[a + "_s"]
    cur, prev = rows[-1], rows[-2]
    lev_hist = [net(r, "lev") for r in rows[-156:]]
    out = {"date": cur["date"], "src": src, "oi": cur["oi"], "weeks": len(rows[-156:])}
    for a, name in (("lev", "Hedge funds / CTAs"), ("am", "Asset managers"), ("dl", "Dealers")):
        h = [net(r, a) for r in rows[-156:]]
        out[a] = {"name": name, "net": net(cur, a), "chg": net(cur, a) - net(prev, a), "pct": pct_rank(h, net(cur, a)), "min": min(h), "max": max(h)}
    out["lev_spark"] = lev_hist[-26:]
    return out


# ------------------------------------------------------------------------------------------------ calendar
def cal_section(today: dt.date, days=45):
    from engine import cme_calendar as C
    out = []
    for c in C.calendar(today, days):
        out.append({"day": c["day"], "kind": "closed" if c["kind"] == "closed" else "half", "what": "CME closed: no session" if c["kind"] == "closed"
                    else f"Half day: the CME halts at {c['halt']} ET (LIT flat 5 min before)", "t": c["halt"]})
    try:
        from engine import roll_watch as R
        nr = R.next_roll(today)
        if nr and (nr[0] - today).days <= days:
            out.append({"day": nr[0].isoformat(), "kind": "roll", "what": f"Contract roll: {nr[1]} -> {nr[2]} (the bot switches by itself)", "t": "00:00"})
    except Exception:                                                # noqa: BLE001 - no roll line rather than a wrong one
        pass
    end = (today + dt.timedelta(days=days)).isoformat()
    for r in read_csv(os.path.join("news", "events.csv")):
        if today.isoformat() <= r.get("date", "") <= end and r.get("impact") == "high":
            out.append({"day": r["date"], "kind": "news", "what": f"{r['event']} {r['time_et']} ET: LIT flat by 5 min before; Rapid lanes pause 2 min either side", "t": r["time_et"]})
    return {"from": today.isoformat(), "days": days, "events": sorted(out, key=lambda e: (e["day"], e["t"] or ""))}


def build(offline=False, today=None):
    today = today or dt.datetime.now(ET).date()
    S = sessions()
    return {"v": 1, "kind": "nq-ports", "made": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "note": "Context for decisions, never a trade signal. Futures prices only (CME NQ / ES bars); CBOE, SqueezeMetrics and CFTC files are free and public.",
            "vol": vol_section(), "normal": normal_section(S), "sweeps": sweeps_section(S), "cot": cot_section(offline), "cal": cal_section(today)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true", help="no network: the cached CFTC weeks")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    doc = build(a.offline)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    ok = [k for k in ("vol", "normal", "sweeps", "cot", "cal") if doc.get(k)]
    print(f"nq_ports: wrote {os.path.relpath(a.out, ROOT)} ({os.path.getsize(a.out) // 1024} KB): {', '.join(ok)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
