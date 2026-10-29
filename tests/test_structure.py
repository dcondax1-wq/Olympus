"""Market structure engine (engine/structure.py): synthetic bars with known swings / BOS / CHoCH / protected swings, the
vectorised pivots == engine/lit.fractals, closed-bar resampling, no look-ahead (a cut history gives the same events), the
pools (session boxes, prior day, equal highs, swept), the dashboard block's exact shape, speed, and a real-data sanity run on
data/NQ_1m.csv 2026 (skipped when the file is missing).

  python -X utf8 -m tests.test_structure          # ~20 s with the real-data run
"""
from __future__ import annotations

import datetime as dt
import os
import statistics
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from engine import structure as S  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def path_bars(points, t0=1_790_000_000 // 300 * 300, secs=300, step=1.0, wick=0.25):
    """Bars walking through waypoints `step` points a bar: o = previous close, h / l = body +/- wick."""
    closes = [float(points[0])]
    for a, b in zip(points, points[1:]):
        n = max(1, int(round(abs(b - a) / step)))
        for i in range(1, n + 1):
            closes.append(a + (b - a) * i / n)
    rows, prev = [], closes[0]
    for i, c in enumerate(closes):
        o = prev
        rows.append([t0 + i * secs, o, max(o, c) + wick, min(o, c) - wick, c])
        prev = c
    return rows


def feed(rows, secs=300):
    tr = S.Tracker(secs)
    evs = []
    for r in rows:
        evs += tr.push(*r)
    return tr, evs


def T(y, m, d, hh, mm):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


# ================================================================================================ synthetic structure
def t_synthetic():
    # range -> rally breaks the 95 swing high (BOS up, from range) -> HH 110, HL 98 -> 115 breaks 110 (BOS up) ->
    # drop below the 98 swing low (CHoCH down) -> LH 96 -> drop below the 90 low (BOS down) -> rally above the protected high
    pts = [100, 80, 95, 85, 100, 110, 98, 115, 90, 96, 84, 93, 86, 99]
    rows = path_bars(pts)
    tr, evs = feed(rows)
    kinds = [(e["kind"], e["dir"]) for e in evs]
    check("synthetic: break sequence BOS up, BOS up, CHoCH down, BOS down, CHoCH up",
          kinds == [("BOS", 1), ("BOS", 1), ("CHoCH", -1), ("BOS", -1), ("CHoCH", 1)], kinds)
    lv = [round(e["price"], 2) for e in evs]
    check("synthetic: broken levels = the swing extremes (95.25, 110.25, 97.75, 89.75, then the 93.25 LH)",
          lv == [95.25, 110.25, 97.75, 89.75, 93.25], lv)
    pr = [round(e["prot"], 2) for e in evs]
    # BOS up over 95: the leg's low is the 85 pullback; BOS over 110: the 98 pullback; CHoCH down: the 115 top;
    # BOS down below 90: the 96 LH; CHoCH up over the 93 LH: the 86 higher low
    check("synthetic: protected swing after each break = origin of the breaking leg (84.75, 97.75, 115.25, 96.25, 85.75)",
          pr == [84.75, 97.75, 115.25, 96.25, 85.75], pr)
    sw = [(s["kind"], round(s["price"], 2)) for s in tr.swings]
    want = [("L", 79.75), ("H", 95.25), ("HL", 84.75), ("HH", 110.25), ("HL", 97.75), ("HH", 115.25), ("LL", 89.75),
            ("LH", 96.25), ("LL", 83.75), ("LH", 93.25), ("HL", 85.75)]
    check("synthetic: swing labels H/L, HH/HL, LL/LH in order", sw == want, sw)
    check("synthetic: trend up after the last CHoCH, protected low 85.75", tr.trend_word() == "up" and tr.protected() == {"high": None, "low": 85.75},
          (tr.trend_word(), tr.protected()))
    # every event is known one bar after its bar opened (at its close), never earlier
    check("synthetic: event known_t = bar t + secs", all(e["known_t"] == e["t"] + 300 for e in evs))
    # a swing exists only from bar j + 2's close
    ok = all(s["known"] == s["j"] + 2 for s in tr.swings)
    check("synthetic: a swing is confirmed 2 bars after its bar", ok)
    # protected-low violation without a newer swing low -> CHoCH via "protected"
    pts2 = [100, 90, 105, 95, 112, 120, 93]       # up, BOS over 105 (prot 95 low leg), runs to 120 with no pullback, dumps
    tr2, ev2 = feed(path_bars(pts2))
    last = ev2[-1] if ev2 else {}
    check("synthetic: close below the protected low with no newer swing low = CHoCH down",
          last.get("kind") == "CHoCH" and last.get("dir") == -1, [(e["kind"], e["dir"], e["via"], e["price"]) for e in ev2])
    # dealing range + premium / discount
    rg = tr.dealing_range()
    check("synthetic: dealing range up = protected low -> highest high since", rg is not None and rg["lo"] == 85.75 and rg["hi"] == 99.25, rg)
    # displacement legs: one big candle inside a run
    rows3 = path_bars([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116])
    rows3 += [[rows3[-1][0] + 300, 116, 116.25, 99.75, 100.0], [rows3[-1][0] + 600, 100.0, 100.25, 98.75, 99.0],
              [rows3[-1][0] + 900, 99.0, 100.25, 98.75, 100.0]]
    tr3, _ = feed(rows3)
    legs = list(tr3.legs)
    check("synthetic: a 16-pt candle (>= 1 ATR) makes a displacement leg down", any(lg["dir"] == -1 and lg["body_atr"] >= 1.0 for lg in legs), legs)


def t_pivots():
    from engine import lit
    rng = np.random.default_rng(7)
    c = np.cumsum(rng.normal(0, 3, 3000)) + 1000
    h = c + rng.uniform(0, 2, 3000)
    lo = c - rng.uniform(0, 2, 3000)
    h = np.round(h * 4) / 4
    lo = np.round(lo * 4) / 4
    a = lit.fractals(h, lo)
    b = S.pivots(h, lo)
    check("pivots() == engine/lit.fractals on 3,000 random bars (ties included)", np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]))
    rows = [[i * 300, float(c[i]), float(h[i]), float(lo[i]), float(c[i])] for i in range(3000)]
    tr = S.Tracker(300, max_swings=None)
    for r in rows:
        tr.push(*r)
    hs = sorted(s["j"] for s in tr.swings if s["side"] == 1)
    ls = sorted(s["j"] for s in tr.swings if s["side"] == -1)
    check("Tracker swings == the fractal pivots (same bars)", hs == list(b[0]) and ls == list(b[1]), (len(hs), len(b[0]), len(ls), len(b[1])))


def t_lookahead():
    rng = np.random.default_rng(11)
    c = np.cumsum(rng.normal(0, 4, 2500)) + 20000
    rows = []
    prev = c[0]
    for i, x in enumerate(c):
        rows.append([1_790_000_000 + i * 300, prev, max(prev, x) + 1, min(prev, x) - 1, float(x)])
        prev = float(x)
    full, evf = feed(rows)
    bad = 0
    for cut in (300, 900, 1500, 2200):
        part, evp = feed(rows[:cut])
        known = [e for e in evf if e["known_t"] <= rows[cut - 1][0] + 300]
        if [(e["kind"], e["dir"], e["t"], e["price"]) for e in known] != [(e["kind"], e["dir"], e["t"], e["price"]) for e in evp]:
            bad += 1
        # the snapshot of the cut history = what the full run knew at that bar (trend, protected)
    check("no look-ahead: events of a cut history == the full run's events known by the cut (4 cuts)", bad == 0, bad)
    # analyze() on a window ending at a cut == the tracker over that window
    A = S.analyze(None, rows[:1000], now=rows[999][0] + 300, tfs=("5m",))
    tr, _ = feed(rows[1000 - S.WINDOW["5m"]:1000])
    check("analyze() 5m frame == a Tracker fed the same window", A["frames"]["5m"]["last_event"] == tr.last_event()
          and A["frames"]["5m"]["protected"] == tr.protected(), (A["frames"]["5m"]["last_event"], tr.last_event()))


def t_resample():
    t0 = T(2026, 10, 14, 9, 30)
    rows = []
    for i in range(37):                        # 09:30 .. 10:06 (the 10:05 bucket still forming)
        o = 100 + i
        rows.append([t0 + 60 * i, o, o + 2, o - 1, o + 0.5])
    r5 = S.resample(rows, 300, 60)
    check("resample 1m -> 5m: 7 closed buckets (the forming 10:05 bucket is left out)", len(r5) == 7, len(r5))
    b = r5[0]
    check("resample: 5m O/H/L/C = first open, max high, min low, last close", b == [t0, 100, 106, 99, 104.5], b)
    r5b = S.resample(rows, 300, 60, now=t0 + 37 * 60 + 300)
    check("resample: a bucket counts as closed once `now` passed its end", len(r5b) == 8, len(r5b))
    r1h = S.resample(rows, 3600, 60)
    check("resample 1m -> 1h: the 09:00 hour closes only at 10:00 (09:30-09:59 -> one bar once 10:00 has a bar)", len(r1h) == 1 and r1h[0][0] == T(2026, 10, 14, 9, 0), r1h)
    fr = S.frames_from(rows, None, now=t0 + 36 * 60 + 30)
    check("frames_from: forming 1m bar dropped (t + 60 > now)", fr["1m"][-1][0] == t0 + 35 * 60, fr["1m"][-1][0] - t0)


def t_pools():
    # Two trading days of 5m bars: prior day 30,000 +/- 50; today Asia 20:00-24:00 high 30,080 / low 29,990, London 02:00-05:00
    # high 30,120 / low 30,010, then price at 05:30 = 30,060 after taking the Asia high (swept) but not the London high.
    rows = []
    t = T(2026, 10, 12, 18, 0)
    end = T(2026, 10, 14, 5, 30)
    while t < end:
        e = dt.datetime.fromtimestamp(t, ET)
        m = e.hour * 60 + e.minute
        day2 = t >= T(2026, 10, 13, 18, 0)
        if not day2:
            if e.hour == 17:
                t += 300
                continue
            px = 30000 + 50 * np.sin(t / 3000.0)
            hi, lo = px + 1, px - 1
        elif 1200 <= m < 1440:
            px = 30035 + 45 * np.sin(t / 900.0)
            hi, lo = min(px + 1, 30080), max(px - 1, 29990)
        elif 120 <= m < 300:
            px = 30065 + 55 * np.sin(t / 700.0)
            hi, lo = min(px + 1, 30120), max(px - 1, 30010)
        else:
            px = 30060
            hi, lo = 30085 if m == 315 else 30061, 30059
        rows.append([t, float(px), float(hi), float(lo), float(px)])
        t += 300
    P = S.pools(rows, now=end, price=30060)
    lab = {p["label"]: p for p in P}
    check("pools: Asia high / low, London high / low, prior day high / low found",
          all(k in lab for k in ("Asia high", "Asia low", "London high", "London low", "Prior day high", "Prior day low")), sorted(lab))
    ah = lab.get("Asia high") or {}
    lh = lab.get("London high") or {}
    check("pools: Asia high swept (05:15 traded 30,085 > 30,080), London high not", ah.get("swept") is True and lh.get("swept") is False,
          (ah, lh))
    check("pools: sides (highs = buy-side, lows = sell-side), known after the box closed",
          ah.get("side") == "buy" and (lab.get("Asia low") or {}).get("side") == "sell" and ah.get("t0") == T(2026, 10, 14, 0, 0), ah)
    check("pools: unswept first, nearest first", [p["swept"] for p in P] == sorted(p["swept"] for p in P))


def t_block_shape():
    rng = np.random.default_rng(3)
    t0 = T(2026, 10, 9, 18, 0)
    rows, p = [], 30000.0
    for i in range(6000):
        c = p + rng.normal(0, 2.5)
        rows.append([t0 + 60 * i, p, max(p, c) + rng.uniform(0, 1), min(p, c) - rng.uniform(0, 1), c])
        p = c
    now = rows[-1][0] + 60
    B = S.block(rows, None, now=now, price=rows[-1][4], key="test")
    check("block: top-level keys exactly t/summary/frames/pools/zone/per_strategy",
          set(B) == {"t", "summary", "frames", "pools", "zone", "per_strategy"}, sorted(B))
    check("block: frames exactly 5m / 15m / 1h", set(B["frames"]) == {"5m", "15m", "1h"}, sorted(B["frames"]))
    fok = all(set(f) == {"trend", "last_event", "swings", "protected"} and f["trend"] in ("up", "down", "range")
              and set(f["protected"]) == {"high", "low"} and len(f["swings"]) <= 20
              and all(set(s) == {"t", "price", "kind"} and s["kind"] in ("HH", "HL", "LH", "LL", "H", "L") for s in f["swings"])
              and (f["last_event"] is None or (set(f["last_event"]) == {"kind", "dir", "t", "price"} and f["last_event"]["kind"] in ("BOS", "CHoCH")
                                               and f["last_event"]["dir"] in (1, -1)))
              for f in B["frames"].values())
    check("block: each frame = trend / last_event / swings (<= 20, HH..L) / protected", fok, B["frames"])
    pok = all(set(p) == {"price", "side", "label", "t0", "swept"} and p["side"] in ("buy", "sell") and isinstance(p["t0"], int)
              and isinstance(p["swept"], bool) for p in B["pools"])
    check("block: pools = price / side buy|sell / label / t0 / swept", pok and len(B["pools"]) > 0, B["pools"][:3])
    z = B["zone"]
    check("block: zone = lo / hi / eq / premium (or null)", z is None or (set(z) == {"lo", "hi", "eq", "premium"} and z["lo"] < z["eq"] < z["hi"]), z)
    ps = B["per_strategy"]
    check("block: per_strategy lit / atlas / scalp with bias long|short|none + note",
          set(ps) == {"lit", "atlas", "scalp"} and all(v["bias"] in ("long", "short", "none") and isinstance(v["note"], str) and v["note"]
                                                       for v in ps.values()), ps)
    check("block: one plain summary sentence", isinstance(B["summary"], str) and B["summary"].startswith("Structure:") and B["summary"].endswith("."), B["summary"])
    import json
    check("block: JSON-serialisable and small (< 12 KB)", len(json.dumps(B)) < 12000, len(json.dumps(B)))
    # cache: same closed bars -> no recompute (fast), price changes the premium flag only
    t1 = time.perf_counter()
    B2 = S.block(rows, None, now=now + 20, price=rows[-1][4] + 500, key="test")
    ms = (time.perf_counter() - t1) * 1000
    check("block: cached on the last closed bar (second call < 15 ms)", ms < 15, f"{ms:.1f} ms")
    check("block: the price refreshes the premium flag", B2["zone"] is None or B2["zone"]["premium"] is True, B2["zone"])
    # speed: a full recompute on 6,000 1m bars
    ts = []
    for k in range(5):
        t1 = time.perf_counter()
        S.analyze(rows[: 5000 + k * 200], None, now=rows[4999 + k * 200][0] + 60)
        ts.append((time.perf_counter() - t1) * 1000)
    med = statistics.median(ts)
    print(f"   analyze() full recompute on 1m: median {med:.1f} ms (max {max(ts):.1f})")
    check("speed: a full recompute (1m, 5m, 15m, 1h windows) < 150 ms median", med < 150, f"{med:.1f} ms")
    # incremental: one push per new 1m bar
    tr = S.Tracker(60)
    t1 = time.perf_counter()
    for r in rows:
        tr.push(*r)
    us = (time.perf_counter() - t1) / len(rows) * 1e6
    print(f"   Tracker.push: {us:.1f} us a bar")
    check("speed: Tracker.push < 200 us a bar", us < 200, f"{us:.1f} us")
    # empty / tiny input never raises
    E = S.block([], [], now=now, key="empty")
    check("block: no bars -> a valid empty block", set(E) == {"t", "summary", "frames", "pools", "zone", "per_strategy"} and E["pools"] == [], E)


def t_real():
    p = os.path.join(ROOT, "data", "NQ_1m.csv")
    if not os.path.exists(p):
        print("[SKIP] real data: data/NQ_1m.csv missing")
        return
    import pandas as pd
    df = pd.read_csv(p, usecols=["time", "open", "high", "low", "close"])
    df = df[df["time"] >= int(dt.datetime(2026, 1, 2, tzinfo=ET).timestamp())].drop_duplicates("time").sort_values("time")
    rows = S.as_rows(df)
    t1 = time.perf_counter()
    r5 = S.resample(rows, 300, 60)
    tr = S.Tracker(300, max_events=None, max_swings=None)
    for r in r5:
        tr.push(*r)
    ms = (time.perf_counter() - t1) * 1000
    E = list(tr.events)
    days = sorted({S.trading_day(e["t"]) for e in E})
    per_day = len(E) / max(1, len(days))
    n_ch = sum(1 for e in E if e["kind"] == "CHoCH")
    print(f"   2026 1m -> 5m: {len(rows):,} 1m bars, {len(r5):,} 5m bars, {len(E):,} breaks ({per_day:.1f} a day, CHoCH {100 * n_ch / max(1, len(E)):.0f}%), "
          f"{len(tr.swings):,} swings, {ms:.0f} ms")
    check("real 2026: 5m breaks a day between 2 and 40 (a sane structure rate)", 2 <= per_day <= 40, per_day)
    check("real 2026: both BOS and CHoCH occur (CHoCH 15-70% of breaks)", 0.15 <= n_ch / max(1, len(E)) <= 0.70, n_ch / max(1, len(E)))
    # 1m -> 5m == the 5m file on a normal day (TradingView exports; same contract basis)
    p5 = os.path.join(ROOT, "data", "NQ_5m.csv")
    if os.path.exists(p5):
        d5 = pd.read_csv(p5, usecols=["time", "open", "high", "low", "close"])
        a, z = T(2026, 3, 9, 18, 0), T(2026, 3, 10, 16, 0)
        m5 = {int(r[0]): r for r in S.as_rows(d5[(d5["time"] >= a) & (d5["time"] < z)])}
        mine = [r for r in r5 if a <= r[0] < z]
        same = sum(1 for r in mine if r[0] in m5 and all(abs(r[i] - m5[r[0]][i]) < 0.01 for i in (1, 2, 3, 4)))
        check("real: 1m -> 5m rebuilds the 5m export on 2026-03-10 (>= 95% of bars identical)", mine and same / len(mine) >= 0.95,
              f"{same}/{len(mine)}")
    # analyze() on the live window at 20 cuts of 2026: speed on real bars
    ts = []
    for k in range(20):
        i = 20000 + k * 9000
        if i >= len(rows):
            break
        t1 = time.perf_counter()
        A = S.analyze(rows[max(0, i - 17000):i], None, now=rows[i - 1][0] + 60)
        ts.append((time.perf_counter() - t1) * 1000)
    med = statistics.median(ts)
    print(f"   analyze() on real 2026 windows: median {med:.1f} ms, max {max(ts):.1f} ms ({len(ts)} cuts); last: {S.to_block(A)['summary'][:200]}")
    check("real: analyze() on a 12-day 1m window < 150 ms median", med < 150, med)


def shape_ok(B) -> bool:
    if set(B) != {"t", "summary", "frames", "pools", "zone", "per_strategy"} or set(B["frames"]) != {"5m", "15m", "1h"}:
        return False
    for f in B["frames"].values():
        if set(f) != {"trend", "last_event", "swings", "protected"} or f["trend"] not in ("up", "down", "range"):
            return False
        if set(f["protected"]) != {"high", "low"} or len(f["swings"]) > 20:
            return False
        if any(set(s) != {"t", "price", "kind"} for s in f["swings"]):
            return False
        if f["last_event"] is not None and set(f["last_event"]) != {"kind", "dir", "t", "price"}:
            return False
    if any(set(p) != {"price", "side", "label", "t0", "swept"} for p in B["pools"]):
        return False
    if B["zone"] is not None and set(B["zone"]) != {"lo", "hi", "eq", "premium"}:
        return False
    return set(B["per_strategy"]) == {"lit", "atlas", "scalp"} and isinstance(B["t"], int) and isinstance(B["summary"], str)


def t_liveview():
    """engine/liveview_api.view() / phone_view() carry the structure block (exact shape), the thinking panel's structure line
    and playbook rule; the narrator's structure kind; the advisor's PC hook on a fake bot; speed of the cached path."""
    import json
    import tempfile
    from tests import test_liveview_api as TL       # its fake bot (synthetic bars, Brain), CSV fallback off
    from engine import liveview_api as L, narrator as N, advisor as AD
    now = TL.T(4, 50)
    b = TL.bot(now)
    L._SB.clear()
    t1 = time.perf_counter()
    v = L.view(b, "1m", now, narr=N.Narrator())
    ms_first = (time.perf_counter() - t1) * 1000
    S = v.get("structure") or {}
    check("view(): a 'structure' block with exactly the Live View shape", shape_ok(S), S if not isinstance(S, dict) else sorted(S))
    th = v["strategies"]["lit"]["thinking"]
    check("view(): Zlarior's thinking panel has a structure line and the playbook rule it is on",
          isinstance(th.get("structure"), str) and th["structure"] and (th.get("rule") or {}).get("id", "").startswith("Z"), (th.get("structure"), th.get("rule")))
    check("view(): ATLAS and BLITZ layers carry their structure note", all(isinstance(v["strategies"][k].get("structure_note"), str)
                                                                         for k in ("atlas", "scalp")))
    t1 = time.perf_counter()
    for k in range(10):
        L.structure_block(b, now + 2 + k)
    ms_cached = (time.perf_counter() - t1) * 100
    print(f"   structure in view(): first {ms_first:.0f} ms (whole view), cached structure_block {ms_cached:.2f} ms")
    check("structure_block cached on the same bars and minute: < 10 ms a call", ms_cached < 10, f"{ms_cached:.2f} ms")
    ph = L.phone_view(b, now, narr=N.Narrator())
    sz = len(json.dumps(ph, separators=(",", ":"), default=str))
    check("phone_view(): structure block included, still under the 240 KB cap", shape_ok(ph.get("structure") or {}) and sz <= L.PHONE_MAX, sz)
    t1 = time.perf_counter()
    msgs, _ = N.derive(b, now + 3)
    ms_der = (time.perf_counter() - t1) * 1000
    check("narrator.derive with the structure part stays fast on a cached bar (< 60 ms)", ms_der < 60, f"{ms_der:.1f} ms")
    sm = [m for m in msgs if m["kind"] == "structure"]
    S2 = L.structure_block(b, now + 3, compute=False) or {}
    want = [tf for tf in ("15m", "1h") if (S2.get("frames", {}).get(tf) or {}).get("last_event")
            and N.trading_day(S2["frames"][tf]["last_event"]["t"]) == N.trading_day(now)]
    check("narrator: a 'structure' message for each 15m / 1h break of today (from the cached block, strat sys)",
          len(sm) == len(want) and all(m["strat"] == "sys" and "trend is now" in m["text"] for m in sm), (want, [m["title"] for m in sm]))
    L._SB.clear()
    check("narrator on the poll thread never recomputes structure (no cache -> no structure message, no work)",
          L.structure_block(b, now + 3, compute=False) is None and not [m for m in N.derive(b, now + 4)[0] if m["kind"] == "structure"])
    check("narrator: 'structure' kind exists, never pushed by default", "structure" in N.KINDS and N.KINDS["structure"][1] is False)
    # the advisor's PC hook on the fake bot: one finished routed LIT trade in the ledger
    et = TL.T(3, 30)
    b.ledger = [{"t": et + 2, "side": "buy", "qty": 2, "entry_t": et, "entry": 30800.0, "stop": 30780.0, "target": 30900.0, "result": {"ok": True}},
                {"t": TL.T(4, 10), "side": "exit", "qty": 2, "entry_t": et, "exit_t": TL.T(4, 10), "pnl": -80.0, "reason": "STOP"}]
    with tempfile.TemporaryDirectory() as tmp:
        AD._PC.update(last=None, seen=None, store=None)
        r1 = AD.pc_tick(b, now, store=tmp)
        r2 = AD.pc_tick(b, now, store=tmp)
        check("advisor.pc_tick: scores the finished routed trade into the temp store, nothing twice in the same bar",
              r1 and (r1.get("lit") or {}).get("new") == 1 and r2 is None and os.path.exists(os.path.join(tmp, "lit.jsonl")), (r1, r2))
        b._lit_1m_store = b._lit_1m_store.iloc[:-1]
        AD._PC["last"] = None
        t1 = time.perf_counter()
        r3 = AD.pc_tick(b, now, store=tmp)
        ms_pc = (time.perf_counter() - t1) * 1000
        check("advisor.pc_tick on a new bar with nothing new to score: no bars converted, < 20 ms", r3 == {} and ms_pc < 20, (r3, ms_pc))


def main():
    t_synthetic()
    t_pivots()
    t_lookahead()
    t_resample()
    t_pools()
    t_block_shape()
    t_liveview()
    if "--quick" not in sys.argv:
        t_real()
    n = len(RES)
    ok = sum(RES)
    print(f"\nstructure: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
