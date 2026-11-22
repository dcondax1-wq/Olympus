"""K8-style clock scan on OTHER Kalshi short up/down series: exactly research/kalshi_k8_day/PREREG_scan.md.

Rerunnable: every Kalshi answer is cached (kget.py, $SCAN_CACHE), so a rerun costs no requests for what it already has.
Kalshi PUBLIC GET only (no key, no auth header, never POST), >= 1.05 s between requests, one process.

    python research/kalshi_k8_day/scan/scan.py            # discovery + stage 1 + stage 2 -> scan.json
Mechanical choices fixed before the results were looked at (written into scan.json "rules"):
  * universe = /series with frequency fifteen_min or hourly, minus KXGOLD15M / KXSILVER15M / *TEST;
    kept only if each event is ONE market whose YES is "at least / above the Target" (the window's start value):
    yes_sub_title starts with "Target"; ladders of strikes and range buckets are excluded (listed with the reason);
    and it has settled markets on >= 50% of the weekdays Aug 3 - Oct 21 ("most weekdays").
  * a window = [close - 15 min (60 for hourly), close]; its open time is read on the ET clock; weekdays (ET) only, like K8.
  * cells with >= 40 windows count as "tried" (both sides), Bonferroni alpha = 0.05 / cells tried.
  * stage 2 = K8's walk (research/kalshi_k8_monday/k8m_data.walk_from, min half the wanted contracts filled), $2.50,
    cap 70c, from +20 s to +45 s, exact fee (engine.kalshi_adapt.fee).
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import kget  # noqa: E402
from engine.kalshi_adapt import fee as kfee, compact_trades  # noqa: E402

_spec = importlib.util.spec_from_file_location("k8m_data", os.path.join(ROOT, "research", "kalshi_k8_monday", "k8m_data.py"))
K8M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(K8M)

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
FIND = (dt.date(2026, 8, 3), dt.date(2026, 10, 21))
HOLD = (dt.date(2026, 10, 22), dt.date(2026, 11, 20))
STAKE, CAP, DELAY, UNTIL = 2.5, 0.70, 20.0, 45.0
MIN_WIN, MIN_N, ALPHA, MAX_CAND = 0.62, 40, 0.05, 10
PASS_FIND, PASS_HOLD, PASS_HOLD_N = 0.10, 0.05, 12
K8_OWN = {"KXGOLD15M", "KXSILVER15M"}
OUT = os.path.join(HERE, "scan.json")
TAPES = os.path.join(HERE, "tapes")


def ts(day, end=False):
    return int(dt.datetime(day.year, day.month, day.day, 23 if end else 0, 59 if end else 0, tzinfo=ET).timestamp())


def iso_ts(x):
    return dt.datetime.fromisoformat(str(x).replace("Z", "+00:00")).timestamp()


def weekdays(a, b):
    d, out = a, []
    while d <= b:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


# ------------------------------------------------------------------ discovery
def discover():
    series = (kget.get("/series") or {}).get("series") or []
    rows = []
    for x in series:
        if x.get("frequency") not in ("fifteen_min", "hourly"):
            continue
        t = x["ticker"]
        r = {"series": t, "freq": x["frequency"], "category": x.get("category"), "title": x.get("title")}
        if t in K8_OWN:
            r.update(keep=False, why="K8's own series (already tested)")
            rows.append(r)
            continue
        if "TEST" in t:
            r.update(keep=False, why="Kalshi test series")
            rows.append(r)
            continue
        ms = ((kget.get("/markets", {"series_ticker": t, "status": "settled", "limit": 200}) or {}).get("markets") or [])
        if not ms:
            ms = ((kget.get("/historical/markets", {"series_ticker": t, "limit": 200}) or {}).get("markets") or [])
        if not ms:
            r.update(keep=False, why="no settled markets at all (live or historical)")
            rows.append(r)
            continue
        ev = {m.get("event_ticker") for m in ms}
        per = len(ms) / max(1, len(ev))
        m0 = ms[0]
        r.update(per_event=round(per, 1), strike_type=m0.get("strike_type"), example=m0.get("ticker"),
                 yes_sub=m0.get("yes_sub_title"), newest_close=m0.get("close_time"))
        if per > 1.05:
            r.update(keep=False, why=f"ladder/range: {per:.0f} strikes per window, YES is not 'above the start'")
        elif not str(m0.get("yes_sub_title") or "").lower().startswith("target") or m0.get("strike_type") not in ("greater", "greater_or_equal"):
            r.update(keep=False, why=f"YES is not 'above the start' ({m0.get('strike_type')}, {m0.get('yes_sub_title')!r})")
        else:
            r.update(keep=True, why="one market per window, YES = at least / above the start (Target)")
        rows.append(r)
    return rows


# ------------------------------------------------------------------ settled markets of a series in [a, b]
def settled(series, a, b):
    """{ticker: (close_epoch, result)} for markets closing in [a, b] (ET dates). Historical (before the cutoff) is paged newest
    first (its date filters are ignored) until it passes a; live /markets takes min/max_close_ts."""
    lo, hi = ts(a), ts(b, end=True)
    cut = iso_ts((kget.get("/historical/cutoff") or {}).get("market_settled_ts") or "2026-09-21T00:00:00Z")
    out = {}

    def take(ms):
        older = False
        for m in ms:
            try:
                c = iso_ts(m["close_time"])
            except (KeyError, ValueError, TypeError):
                continue
            if c < lo:
                older = True
            if lo <= c <= hi and m.get("result") in ("yes", "no"):
                out[m["ticker"]] = (c, m["result"])
        return older

    if hi > cut - 86400:          # live part (overlap a day around the cutoff, dedup by ticker)
        cur = None
        for _ in range(60):
            p = {"series_ticker": series, "status": "settled", "min_close_ts": max(lo, int(cut) - 86400), "max_close_ts": hi,
                 "limit": 1000, "cursor": cur}
            j = kget.get("/markets", p)
            if not j:
                break
            take(j.get("markets") or [])
            cur = j.get("cursor")
            if not cur or not j.get("markets"):
                break
    if lo < cut:
        cur = None
        for _ in range(80):
            j = kget.get("/historical/markets", {"series_ticker": series, "limit": 1000, "cursor": cur})
            if not j:
                break
            ms = j.get("markets") or []
            older = take(ms)
            cur = j.get("cursor")
            if older or not cur or not ms:
                break
    return out


def window_len(freq):
    return 900 if freq == "fifteen_min" else 3600


def windows(mk, freq, a, b):
    """[(ticker, open_epoch, ET date, 'HH:MM', result)] on ET weekdays in [a, b]."""
    out = []
    for tk, (c, res) in mk.items():
        o = c - window_len(freq)
        e = dt.datetime.fromtimestamp(o, ET)
        if e.weekday() >= 5 or not (a <= e.date() <= b):
            continue
        out.append((tk, o, e.date(), f"{e:%H:%M}", res))
    return sorted(out, key=lambda x: x[1])


def binom_p(k, n):
    """one-sided P(X >= k), X ~ Bin(n, 1/2)."""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2.0 ** n


# ------------------------------------------------------------------ stage 2
def first45(tk, o):
    cut = iso_ts((kget.get("/historical/cutoff") or {}).get("trades_created_ts") or "2026-09-21T00:00:00Z")
    q = {"ticker": tk, "min_ts": int(o) - 1, "max_ts": int(o) + int(UNTIL), "limit": 1000}
    paths = ("/historical/trades", "/markets/trades") if o < cut else ("/markets/trades", "/historical/trades")
    for p in paths:
        rows, cur, ok = [], None, False
        for _ in range(5):
            j = kget.get(p, dict(q, cursor=cur))
            if j is None:
                break
            ok = True
            rows += j.get("trades") or []
            cur = j.get("cursor")
            if not cur or not j.get("trades"):
                break
        if ok and rows:
            return compact_trades(rows, o)
        if ok and p == paths[0]:
            return []
    return None


def price_rows(cand, freq):
    s, hhmm, side = cand["series"], cand["open_et"], cand["side"]
    mk = settled(s, FIND[0], HOLD[1])
    ws = [w for w in windows(mk, freq, FIND[0], HOLD[1]) if w[3] == hhmm]
    os.makedirs(TAPES, exist_ok=True)
    tape_path = os.path.join(TAPES, f"{s}_{hhmm.replace(':', '')}.jsonl")
    tape = {}
    if os.path.exists(tape_path):
        for ln in open(tape_path, encoding="utf-8"):
            r = json.loads(ln)
            tape[r["t"]] = r
    rows = []
    for tk, o, day, _, res in ws:
        if tk not in tape:
            tr = first45(tk, o)
            if tr is None:
                rows.append({"day": str(day), "ticker": tk, "n": 0, "why": "trades not served"})
                continue
            tape[tk] = {"t": tk, "o": o, "res": res, "tr": tr}
            with open(tape_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(tape[tk], separators=(",", ":")) + "\n")
        tr = tape[tk]["tr"]
        n, px, p1 = K8M.walk_from(tr, side, DELAY, STAKE, CAP, UNTIL)
        won = res == side
        row = {"day": str(day), "ticker": tk, "res": res, "won": won, "n": 0, "first": p1, "hold": day >= HOLD[0]}
        want = max(1, int(math.floor(STAKE / p1 + 1e-9))) if p1 else None
        if n and (want is None or n >= max(1, math.ceil(want * 0.5 - 1e-9))):
            f = kfee(px, n)
            cost = n * px + f
            row.update(n=n, price=px, fee=f, cost=round(cost, 4), pnl=round((n if won else 0) - cost, 4))
        rows.append(row)
    return rows


def summ(rows, a, b):
    r = [x for x in rows if x.get("n")]
    weeks = ((b - a).days + 1) / 7.0
    if not r:
        return {"bets": 0, "windows": len(rows)}
    cost, net = sum(x["cost"] for x in r), sum(x["pnl"] for x in r)
    return {"windows": len(rows), "bets": len(r), "bets_week": round(len(r) / weeks, 2), "win_rate": round(sum(x["won"] for x in r) / len(r), 4),
            "avg_price": round(sum(x["price"] for x in r) / len(r), 4), "fees_usd": round(sum(x["fee"] for x in r), 2),
            "cost_usd": round(cost, 2), "net_usd": round(net, 2), "net_per_1": round(net / cost, 4),
            "usd_month": round(net / weeks * 4.33, 2)}


def k8_power(thr):
    """Sanity (NOT in the universe): the same stage-1 count on K8's own gold/silver legs, to show whether this Bonferroni
    bar could have found K8 itself from results alone."""
    legs = [("KXGOLD15M", "05:15", "no"), ("KXGOLD15M", "16:45", "yes"), ("KXSILVER15M", "05:15", "no"), ("KXSILVER15M", "16:45", "yes")]  # ET opens of the K8 legs (London 10:15 = 05:15 ET)
    out = []
    for s, hhmm, side in legs:
        ws = [w for w in windows(settled(s, *FIND), "fifteen_min", *FIND) if w[3] == hhmm]
        n, k = len(ws), sum(1 for w in ws if w[4] == side)
        if n:
            out.append({"series": s, "open_et": hhmm, "side": side, "n": n, "won": k, "win": round(k / n, 4),
                        "p": binom_p(k, n), "passes_bar": binom_p(k, n) < thr and k / n >= MIN_WIN})
    return out


# ------------------------------------------------------------------ main
def main():
    rules = {"universe": "series frequency fifteen_min/hourly, one market per window, YES = at least/above the Target (start), "
                         ">= 50% of find weekdays with settled markets; not KXGOLD15M/KXSILVER15M",
             "find": [str(FIND[0]), str(FIND[1])], "hold": [str(HOLD[0]), str(HOLD[1])], "weekdays_only_ET": True,
             "min_windows": MIN_N, "min_win": MIN_WIN, "alpha": ALPHA, "stake": STAKE, "cap": CAP, "delay_s": DELAY,
             "until_s": UNTIL, "pass_find_net_per_1": PASS_FIND, "pass_hold_net_per_1": PASS_HOLD, "pass_hold_bets": PASS_HOLD_N}
    found = discover()
    wd = weekdays(*FIND)
    cells, series_info = [], {}
    for r in found:
        if not r.get("keep"):
            continue
        s = r["series"]
        mk = settled(s, *FIND)
        ws = windows(mk, r["freq"], *FIND)
        days = {w[2] for w in ws}
        r["find_windows"], r["find_weekdays_with_markets"] = len(ws), len(days)
        if len(days) < 0.5 * len(wd):
            r.update(keep=False, why=f"thin: settled markets on only {len(days)} of {len(wd)} find weekdays")
            print(s, "thin", len(days), flush=True)
            continue
        by = {}
        for w in ws:
            by.setdefault(w[3], []).append(w[4])
        for hhmm, res in sorted(by.items()):
            n = len(res)
            if n < MIN_N:
                continue
            y = sum(1 for x in res if x == "yes")
            for side, k in (("yes", y), ("no", n - y)):
                cells.append({"series": s, "freq": r["freq"], "open_et": hhmm, "side": side, "n": n, "won": k,
                              "win": round(k / n, 4), "z": round((k - n / 2) / math.sqrt(n / 4), 3)})
        print(s, len(ws), "windows", len(days), "days", flush=True)
    n_cells = len(cells)
    thr = ALPHA / max(1, n_cells)
    for c in cells:
        c["p"] = binom_p(c["won"], c["n"])
    cand = sorted([c for c in cells if c["win"] >= MIN_WIN and c["p"] < thr], key=lambda c: -c["z"])
    top_raw = sorted(cells, key=lambda c: -c["z"])[:25]
    stage2 = []
    freq = {r["series"]: r["freq"] for r in found}
    for c in cand[:MAX_CAND]:
        rows = price_rows(c, freq[c["series"]])
        f = summ([x for x in rows if not x.get("hold") and "why" not in x], *FIND)
        h = summ([x for x in rows if x.get("hold") and "why" not in x], *HOLD)
        ok = (f.get("net_per_1", -9) >= PASS_FIND and h.get("net_per_1", -9) >= PASS_HOLD and h.get("bets", 0) >= PASS_HOLD_N)
        stage2.append({**c, "find": f, "hold": h, "passed": ok, "not_served": sum(1 for x in rows if "why" in x)})
        print("stage2", c["series"], c["open_et"], c["side"], f, h, ok, flush=True)
    passed = sorted([x for x in stage2 if x["passed"]], key=lambda x: -x["hold"]["net_per_1"])[:3]
    doc = {"generated_utc": dt.datetime.now(UTC).strftime("%Y-%m-%d %H:%M"), "prereg": "research/kalshi_k8_day/PREREG_scan.md",
           "rules": rules, "series_found": found, "series_kept": [r["series"] for r in found if r.get("keep")],
           "cells_tried": n_cells, "bonferroni_p": thr, "candidates": cand, "top25_by_z_any": top_raw,
           "stage2": stage2, "passed_top3": passed, "verdict": "none" if not passed else "see passed_top3",
           "requests_this_run": kget.STATS["requests"], "cache_hits_this_run": kget.STATS["cache_hits"],
           "refused": kget.STATS["refused"][:50], "errors": kget.STATS["errors"]}
    try:
        doc["requests_total_logged"] = sum(1 for _ in open(kget.LOG))
    except OSError:
        pass
    # context (not part of the test): how many cells clear 62% vs how many pure chance would give, and the K8 power check
    doc["cells_win_ge_62"] = sum(1 for c in cells if c["win"] >= MIN_WIN)
    doc["cells_win_ge_62_expected_by_chance"] = round(sum(binom_p(math.ceil(MIN_WIN * c["n"] - 1e-9), c["n"]) for c in cells), 1)
    doc["k8_power_check"] = k8_power(thr)
    doc["cells"] = [[c["series"], c["open_et"], c["side"], c["n"], c["won"]] for c in cells]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=str)
    print("cells", n_cells, "thr", thr, "cands", len(cand), "passed", len(passed), kget.STATS["requests"], "requests", flush=True)


if __name__ == "__main__":
    main()
