#!/usr/bin/env python3
"""Kalshi SCAN: "where the money is" (research only: reads the public feed and the city's own ledger, never an order, no key, no Kalshi call).

For every cell of the bot's bets with at least 30 bets it works out the fee-adjusted expected value per $1 risked, gives it a 95% range (Wilson on the
win rate), flags cells that look positive only because the sample is small, and writes the top 5 "worth a paper test" and the top 5 "to avoid" in plain words
with the dollars. LOOKING BACK, NOT PROVEN: a cell is a slice of past bets, picked from many slices, so the best of them are partly luck.

    python tools/kalshi_scan.py                        # fetch the public feed, write tools/web_public/kalshicity/scan.json
    python tools/kalshi_scan.py --feed kalshi.json     # a local copy (tests, offline)
    python tools/kalshi_scan.py --ledger ledger.json   # the city's memory of every settled bet seen one by one (default: kalshicity/ledger.json if there)

Cells (dimensions the feed really carries):
  from the feed's own totals over every settled bet:   price band · category (the coin) · strategy
  from bets seen one by one (the ledger + the feed's last 40):  time of day (ET: Asia 18-02, London 02-08, NY morning 08-12, NY afternoon 12-18) and the crossings
                                                       band x category, band x time, category x time, band x category x time
EV per $1 at equal size = (win rate - price - fee per contract) / price, the fee being Kalshi's taker fee (tools/kalshi_research.fee_pc, 0.07 p (1-p) a contract).
A coin's or a strategy's price is not in the feed's totals: the mean price of its recent bets (else the feed's average) is used and the cell says so.
Fragile = EV above zero but under 100 bets or a range that includes zero: a hint, never a result.
Exit codes: 0 ok (also "nothing changed": the file is not rewritten), 2 feed unreachable (nothing written: stale beats invented). scan.json stays under 30 KB.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:                                                    # the research's own functions (it needs numpy: the workflow has none, so the same formulas stand in there)
    from tools.kalshi_research import fee_pc, wilson
except Exception:                                       # noqa: BLE001
    def fee_pc(p):
        return 0.07 * p * (1 - p)

    def wilson(k, n, z=1.96):
        if n <= 0:
            return (float("nan"), float("nan"))
        ph = k / n
        d = 1 + z * z / n
        c = (ph + z * z / (2 * n)) / d
        h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
        return (max(0.0, c - h), min(1.0, c + h))

FEED_URL = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"
OUT = os.path.join(ROOT, "tools", "web_public", "kalshicity", "scan.json")
LEDGER = os.path.join(ROOT, "tools", "web_public", "kalshicity", "ledger.json")
MIN_N, FRAGILE_N, TOP, MAX_BYTES = 30, 100, 5, 30_000
ET = ZoneInfo("America/New_York")
EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 0.97, 0.99, 1.0001)
HOURS = (("asia", "overnight Asia hours (6 pm to 2 am ET)"), ("london", "London hours (2 to 8 am ET)"),
         ("nyam", "New York morning (8 am to noon ET)"), ("nypm", "New York afternoon (noon to 6 pm ET)"))
HNAME = dict(HOURS)


def fin(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def usd(x, sign=False):
    v = round(abs(x) + 1e-9, 2)
    s = "−" if x < 0 and v else "+" if sign and v else ""
    return s + (f"${v:,.2f}" if v < 100 else f"${v:,.0f}")


def band_label(lo, hi):
    return f"{round(lo * 100)}–{round(min(hi, 1.0) * 100)}¢"


def band_of(p):
    for i in range(len(EDGES) - 1):
        if EDGES[i] <= p < EDGES[i + 1]:
            return (EDGES[i], min(1.0, EDGES[i + 1]))
    return None


def hour_of(t):
    h = dt.datetime.fromtimestamp(t, dt.timezone.utc).astimezone(ET).hour
    return "asia" if h >= 18 or h < 2 else "london" if h < 8 else "nyam" if h < 12 else "nypm"


# ------------------------------------------------------------------ one cell
def make_cell(name, dims, n, wins, p, fee, pnl, staked, source, price_source=None):
    """EV per $1 at equal size, fee-adjusted; None when the cell cannot be worked out (no usable price)."""
    if n < MIN_N or not (0.01 < p < 0.995) or wins < 0 or wins > n:
        return None
    w = wins / n
    lo, hi = wilson(wins, n)
    ev = lambda x: (x - p - fee) / p                                    # noqa: E731
    c = {"name": name, "dims": dims, "n": n, "wins": wins, "win_rate": round(w, 4), "price": round(p, 4), "w_lo": round(lo, 4), "w_hi": round(hi, 4),
         "ev": round(ev(w), 4), "ev_lo": round(ev(lo), 4), "ev_hi": round(ev(hi), 4), "ev_gross": round((w - p) / p, 4), "source": source}
    if price_source:
        c["price_source"] = price_source
    if staked and staked > 0 and fin(pnl):
        c["pnl"], c["staked"], c["fees"] = round(pnl, 2), round(staked, 2), round(fee / p * staked, 2)
    c["fragile"] = bool(c["ev"] > 0 and (n < FRAGILE_N or c["ev_lo"] <= 0 or price_source))          # an assumed price can fake an edge: never trusted
    c["proven"] = "positive" if c["ev_lo"] > 0 else "negative" if c["ev_hi"] < 0 else "open"
    return c


def say(c):
    cents = lambda x: f"{x * 100:+.1f}¢".replace("-", "−")              # noqa: E731
    s = (f"{c['name']}: won {c['win_rate'] * 100:.1f}% of {c['n']:,} bets against {c['price'] * 100:.1f}% priced. After Kalshi's fee that is "
         f"{cents(c['ev'])} on every $1 risked (95% range {cents(c['ev_lo'])} to {cents(c['ev_hi'])}).")
    if "pnl" in c:
        s += f" It {'made' if c['pnl'] >= 0 else 'lost'} {usd(abs(c['pnl']))} on {usd(c['staked'])} bet; fees were about {usd(c['fees'])}."
    if c["ev"] > 0 and "pnl" in c and c["pnl"] < 0:
        s += " In real dollars it still lost: the losing bets were bigger than the winning ones."
    if c["ev"] > 0 and c["fragile"]:
        why = ["under 100 bets" if c["n"] < FRAGILE_N else "", "the range includes zero" if c["ev_lo"] <= 0 else "", "the price is assumed" if c.get("price_source") else ""]
        s += f" Positive but fragile ({', '.join(w for w in why if w)}): a hint, not a result."
    elif c["ev"] < 0 and c["proven"] != "negative":
        s += " Negative, but the range includes zero: not proven."
    if c.get("price_source"):
        s += f" Price assumed: {c['price_source']}."
    return s


# ------------------------------------------------------------------ the cells
def total_cells(feed):
    out = []
    cal = {int(c["n"]): c["p"] for c in feed.get("calibration") or [] if isinstance(c, dict) and fin(c.get("n")) and fin(c.get("p"))}
    seen = set()
    for b in feed.get("buckets") or []:
        if not isinstance(b, dict) or not all(fin(b.get(k)) for k in ("trades", "wins", "losses", "lo", "hi", "pnl", "staked")):
            continue
        n, w, l, lo, hi = int(b["trades"]), int(b["wins"]), int(b["losses"]), float(b["lo"]), float(b["hi"])
        if n <= 0 or w < 0 or l < 0 or w + l > n or b["staked"] <= 0 or not 0 <= lo < hi <= 1.0001 or (lo, hi) in seen:
            continue
        seen.add((lo, hi))
        p = cal.get(n, (lo + min(hi, 1.0)) / 2)
        c = make_cell(f"{band_label(lo, hi)} bets", {"band": band_label(lo, hi)}, n, w, p, fee_pc(p), b["pnl"], b["staked"], "totals over every settled bet")
        if c:
            out.append(c)
    glob = (feed.get("stats") or {}).get("avg_price") if isinstance(feed.get("stats"), dict) else None
    glob = glob if fin(glob) and 0.05 < glob < 0.995 else 0.95
    sample = [t for t in feed.get("trades") or [] if isinstance(t, dict) and t.get("action") != "sell" and fin(t.get("price")) and 0 < t["price"] < 1.0001]

    def price_for(key, val):
        ps = [t["price"] for t in sample if t.get(key) == val]
        return (sum(ps) / len(ps), f"the mean of {len(ps)} recent {val} bets") if len(ps) >= 3 else (glob, "the feed's average entry price")
    for c0 in feed.get("categories") or []:
        if isinstance(c0, dict) and all(fin(c0.get(k)) for k in ("trades", "wins", "pnl", "staked")) and c0.get("name") and c0["staked"] > 0:
            p, src = price_for("category", c0["name"])
            c = make_cell(f"{c0['name']} bets", {"category": str(c0["name"])}, int(c0["trades"]), int(c0["wins"]), p, fee_pc(p), c0["pnl"], c0["staked"], "totals over every settled bet", src)
            if c:
                out.append(c)
    for s0 in feed.get("strategies") or []:
        if isinstance(s0, dict) and all(fin(s0.get(k)) for k in ("trades", "wins", "total_pnl")) and s0.get("name"):
            p, src = price_for("strategy", s0["name"])
            c = make_cell(f"the {s0['name']} strategy", {"strategy": str(s0["name"])}, int(s0["trades"]), int(s0["wins"]), p, fee_pc(p), s0["total_pnl"], None, "totals over every settled bet", src)
            if c:
                out.append(c)
    return out


def bet_rows(feed, ledger):
    """settled buys seen one by one: the ledger's rows {t,k,s,m,sd,p,c,pnl} and the feed's last trades, each once"""
    rows, seen = [], set()

    def add(t, k, s, m, sd, p, c, pnl):
        if not all(fin(x) for x in (t, p, c, pnl)) or not 1e9 < t < 4e9 or not 0 < p < 1.0001 or c <= 0:
            return
        key = (t, k, sd, c, p)
        if key in seen:
            return
        seen.add(key)
        rows.append({"t": t, "s": s, "m": m, "p": p, "c": c, "pnl": pnl})
    for r in (ledger or {}).get("trades") or [] if isinstance(ledger, dict) else []:
        if isinstance(r, dict):
            add(r.get("t"), r.get("k"), r.get("s"), r.get("m"), r.get("sd"), r.get("p"), r.get("c"), r.get("pnl"))
    for r in feed.get("trades") or []:
        if isinstance(r, dict) and r.get("action") != "sell":
            add(r.get("t"), r.get("ticker"), r.get("strategy"), r.get("category"), r.get("side"), r.get("price"), r.get("contracts"), r.get("pnl"))
    return rows


def cross_cells(rows):
    groups = {}
    for r in rows:
        b = band_of(r["p"])
        if b is None:
            continue
        d = {"band": band_label(*b), "category": str(r["m"]) if r["m"] else None, "hour": hour_of(r["t"])}
        for dims in (("hour",), ("band", "category"), ("band", "hour"), ("category", "hour"), ("band", "category", "hour")):
            if any(d[k] is None for k in dims):
                continue
            groups.setdefault(tuple((k, d[k]) for k in dims), []).append(r)
    out = []
    for key, rs in sorted(groups.items(), key=lambda kv: kv[0]):
        n = len(rs)
        if n < MIN_N:
            continue
        wins, p = sum(1 for r in rs if r["pnl"] > 0.005), sum(r["p"] for r in rs) / n
        fee = sum(fee_pc(r["p"]) for r in rs) / n
        d = dict(key)
        name = (f"{d['category']} bets" if "category" in d else "bets") + (f" priced {d['band']}" if "band" in d else "") + (f" placed in {HNAME[d['hour']]}" if "hour" in d else "")
        c = make_cell(name, {k: v for k, v in key}, n, wins, p, fee, sum(r["pnl"] for r in rs), sum(r["c"] * r["p"] for r in rs), f"{len(rows):,} bets seen one by one")
        if c:
            out.append(c)
    return out


def scan(feed, ledger=None):
    cells = total_cells(feed) + cross_cells(bet_rows(feed, ledger))
    pos = [c for c in cells if c["ev"] > 0]
    neg = [c for c in cells if c["ev"] < 0]
    pos.sort(key=lambda c: (c["fragile"], -c["ev_lo"] if not c["fragile"] else -c["ev"], c["name"]))
    money = lambda c: c["pnl"] if "pnl" in c else c["ev"] * c["n"]         # noqa: E731
    neg.sort(key=lambda c: (money(c), c["name"]))
    top = lambda lst: [dict(c, text=say(c)) for c in lst[:TOP]]            # noqa: E731
    out = {"v": 1, "kind": "kalshi-scan", "t": feed.get("t"), "min_n": MIN_N, "fragile_n": FRAGILE_N,
           "label": "Looking back at past bets, not proven: each cell is one slice of many, so the best-looking ones are partly luck. Suggestions only: nothing here places or changes a bet.",
           "cells_scanned": len(cells), "positive": len(pos), "negative": len(neg), "fragile": sum(1 for c in cells if c["fragile"]),
           "test": top(pos), "avoid": top(neg)}
    out["headline"] = headline(out)
    raw = json.dumps(out, ensure_ascii=False)
    while len(raw.encode("utf-8")) > MAX_BYTES and (out["test"] or out["avoid"]):          # never over 30 KB (the sentences are the bulk)
        (out["test"] if len(out["test"]) >= len(out["avoid"]) else out["avoid"]).pop()
        raw = json.dumps(out, ensure_ascii=False)
    return out


def headline(o):
    if not o["cells_scanned"]:
        return "Not enough bets in any one slice yet (30 needed) to say where the money is."
    t = o["test"][0] if o["test"] else None
    a = o["avoid"][0] if o["avoid"] else None
    bits = []
    if t:
        bits.append(f"Best slice to paper-test: {t['name']} ({t['ev'] * 100:+.1f}¢ per $1{', a small sample' if t['fragile'] else ''})")
    if a:
        bits.append(f"slice to avoid: {a['name']} ({a['ev'] * 100:+.1f}¢ per $1".replace("-", "−") + (f", {usd(a['pnl'], True)}" if "pnl" in a else "") + ")")
    return "; ".join(bits).replace("+-", "−") + f". {o['cells_scanned']} slices scanned." if bits else f"{o['cells_scanned']} slices scanned, none clearly positive or negative."


def load(src):
    if src and os.path.isfile(src):
        return json.load(open(src, encoding="utf-8"))
    req = urllib.request.Request(src or FEED_URL, headers={"User-Agent": "kalshi-scan/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--feed", help="path or URL of kalshi.json (default: the public feed)")
    ap.add_argument("--ledger", help="the city's ledger.json (default: kalshicity/ledger.json next to --out, else the repo's)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    try:
        feed = load(a.feed)
        if not isinstance(feed, dict) or feed.get("kind") != "kalshi":
            raise ValueError("not a kalshi.json")
    except Exception as e:                                             # noqa: BLE001 - stale beats invented
        print(f"feed unreachable ({e.__class__.__name__}): nothing changed")
        return 2
    led = None
    for cand in (a.ledger, os.path.join(os.path.dirname(os.path.abspath(a.out)), "ledger.json"), LEDGER):
        if cand and os.path.isfile(cand):
            try:
                led = json.load(open(cand, encoding="utf-8"))
                break
            except Exception:                                          # noqa: BLE001 - a broken ledger is ignored, the totals still scan
                led = None
    res = scan(feed, led)
    text = json.dumps(res, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    if len(text.encode("utf-8")) > MAX_BYTES:
        text = json.dumps(res, ensure_ascii=False, sort_keys=True) + "\n"
    if os.path.isfile(a.out) and open(a.out, encoding="utf-8").read() == text:
        print("nothing changed")
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, a.out)
    print(res["headline"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
