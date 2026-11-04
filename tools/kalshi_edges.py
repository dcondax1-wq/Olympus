#!/usr/bin/env python3
"""KALSHI CITY learning engine (OLYMPUS, 2026-11-04). Reads the public Kalshi feed and writes the city's brain.

  python tools/kalshi_edges.py                      # fetch the live feed, update tools/web_public/kalshicity/
  python tools/kalshi_edges.py --feed kalshi.json   # a local copy (tests, offline)
  python tools/kalshi_edges.py --history DIR|FILE   # older snapshots of kalshi.json: their trade windows join the ledger
  python tools/kalshi_edges.py --history-git REPO   # every commit of kalshi.json in a clone of kalshi-feed joins the ledger

READ ONLY. It reads kalshi.json (contract: docs/KALSHI_PUBLISH.md) and nothing else: no Kalshi call, no key, no order.

Files (all in --out, default tools/web_public/kalshicity/):
  ledger.json         the engine's memory: every settled bet it has ever seen one by one (the feed only carries the last 40),
                      deduplicated, plus one snapshot per day of the feed's own totals (for 7 / 30 day windows of the totals)
  edges.json          what the page reads: one row per edge, the book, the weather, the do-more / stop lists
  learning_log.json   append-only: dated lessons ("Learned: ... EV -$0.04 per $1 over 112 bets: STOP"); never rewritten
  jarvis.json         the Jarvis card

An EDGE is a slice of the bot's bets: any 1 to 3 of five dimensions fixed, the rest "*":
  strategy, market (the asset), hour (ET, four-hour block), band (entry price band, the feed's own edges), side (yes / no).
Per edge: n, win rate w vs the implied probability p (the mean entry price), EV per $1 staked (realised, fees in), the Wilson 95%
interval of w, a z-test of wins against sum(price) (the market's own odds), windows (last 7 days / 30 days / all), the decay
(recent EV minus all-time EV), the Kelly fraction (full, safe = on the Wilson lower bound, quarter of safe), the stake in $, the
chance of losing half the bankroll at that stake (Lundberg bound), and a status:
  NEW        fewer than 30 bets: no verdict yet (greyed in the city, never sized up)
  GROWING    n >= 30, EV > 0, the recent window earns more than 1.5x the all-time EV
  HOLDING    n >= 30, EV > 0, the recent window within [0.5x, 1.5x] of all-time (or no recent window yet)
  DECAYING   n >= 30 and the recent EV fell below half of all-time, or EV <= 0 but not yet proven
  DEAD       n >= 30, EV <= 0 and either z <= -1.645 (proven negative) or every window is losing
Sources: the three single-dimension families the feed totals over its whole life (strategies, markets, price bands) use the feed's
totals when they hold more bets than the ledger ("src": "feed"; p_basis says where the implied price came from); everything else
comes from the ledger ("src": "ledger"). Small samples are honest: n < 30 is flagged "small" and never gets a Kelly stake.
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
import math
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                                   # pragma: no cover - no tz database: UTC (only the hour blocks shift)
    ET = timezone.utc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DEFAULT = os.path.join(ROOT, "tools", "web_public", "kalshicity")
RAW = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"

VERSION = 1
MIN_N = 30                  # fewer bets than this: no verdict (status NEW, greyed, no stake)
Z_SIG = 1.6448536269514722  # one-sided 95%
Z95 = 1.959963984540054     # the Wilson interval
KELLY_FRACTION = 0.25
BAND_EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 0.97, 0.99, 1.0001)    # the bot's own (kalshi_status_vm.py)
BAND_LABELS = ("<20c", "20-40c", "40-60c", "60-80c", "80-90c", "90-95c", "95-97c", "97-99c", "99c+")
DIMS = ("strategy", "market", "hour", "band", "side")
MIN_N_BY_SIZE = {1: 1, 2: 5, 3: 8}      # a combination needs this many bets to be worth a building
MAX_EDGES = 1200
MAX_LOG_PER_RUN = 40
DAY = 86400
ASSET_NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "XRP": "XRP", "DOGE": "Dogecoin", "HYPE": "HYPE", "BNB": "BNB",
               "GOLD": "Gold", "SILVER": "Silver"}
ADVICE_WORD = {"do_more": "DO MORE", "stop": "STOP", "keep": "KEEP", "watch": "WATCH", "collect": "COLLECT"}


# ------------------------------------------------------------------------------------------------ small parsers
def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str) and v.strip():
        try:
            x = float(v)
            return x if math.isfinite(x) else None
        except ValueError:
            return None
    return None


def parse_t(v):
    x = num(v)
    if x is not None:
        return x / 1000.0 if x > 1e12 else x
    if isinstance(v, str) and v.strip():
        try:
            d = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
            return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
        except ValueError:
            return None
    return None


def clean(v, n=60):
    return " ".join(str(v or "").split())[:n]


def dollars(v):
    x = num(v)
    return None if x is None else (x / 100.0 if x > 1 else x)


def et_dt(t):
    return datetime.fromtimestamp(t, ET)


def et_date(t):
    return et_dt(t).strftime("%Y-%m-%d")


def hour_block(t):
    h = et_dt(t).hour // 4 * 4
    return f"{h:02d}-{h + 4:02d} ET"


def band_index(price):
    for i in range(len(BAND_EDGES) - 1):
        if BAND_EDGES[i] <= price < BAND_EDGES[i + 1]:
            return i
    return None


def band_label(price):
    i = band_index(price)
    return BAND_LABELS[i] if i is not None else None


def r4(x):
    return None if x is None else round(float(x), 4)


# ------------------------------------------------------------------------------------------------ the maths
def wilson(wins, n, z=Z95):
    """Wilson score interval for a win rate: (low, high); (0, 1) when n = 0."""
    if n <= 0:
        return 0.0, 1.0
    w = wins / n
    d = 1.0 + z * z / n
    c = (w + z * z / (2 * n)) / d
    h = z * math.sqrt(w * (1 - w) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def z_test(wins, sum_p, sum_var):
    """z of the wins against the market's own odds: (wins - sum of prices) / sqrt(sum of p(1-p)). Two-sided p-value alongside."""
    if sum_var <= 0:
        return None, None
    z = (wins - sum_p) / math.sqrt(sum_var)
    return z, math.erfc(abs(z) / math.sqrt(2.0))


def kelly_full(w, p):
    """Kelly stake as a fraction of the bankroll for a $1 contract bought at price p that wins with chance w: (w - p) / (1 - p)."""
    if w is None or p is None or not 0 < p < 1:
        return None
    return (w - p) / (1.0 - p)


def ruin_half(w, p, f):
    """Upper bound (Lundberg) on the chance the bankroll ever falls to half, staking a fraction f of it per bet on a contract bought
    at price p that wins with chance w. 1.0 when the bet has no positive drift, 0.0 when nothing is staked."""
    if f is None or f <= 0 or w is None or p is None or not 0 < p < 1:
        return 0.0
    f = min(f, 0.99)
    b = (1.0 - p) / p
    up, dn = math.log1p(f * b), math.log1p(-f)             # log-wealth steps: +up with chance w, dn (< 0) otherwise
    if w * up + (1 - w) * dn <= 0:
        return 1.0

    def h(th):
        return w * math.exp(min(700.0, -th * up)) + (1 - w) * math.exp(min(700.0, -th * dn)) - 1.0
    lo, hi = 1e-9, 1e-3
    while h(hi) <= 0 and hi < 1e5:
        lo, hi = hi, hi * 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if h(mid) <= 0:
            lo = mid
        else:
            hi = mid
    return min(1.0, math.exp(-((lo + hi) / 2) * math.log(2.0)))


# ------------------------------------------------------------------------------------------------ trades
def norm_trade(r):
    """A feed trade row -> the ledger's record, or None (sell-backs, rows without a grade, junk)."""
    if not isinstance(r, dict) or str(r.get("action", "")).lower() == "sell":
        return None
    t, pnl, price, c = parse_t(r.get("t")), num(r.get("pnl")), dollars(r.get("price")), num(r.get("contracts"))
    if t is None or pnl is None or price is None or c is None or c <= 0 or not 0 < price < 1:
        return None
    side = clean(r.get("side"), 8).lower()
    side = {"up": "yes", "down": "no"}.get(side, side)
    if side not in ("yes", "no"):
        side = ""
    asset = clean(r.get("asset"), 8).upper()
    market = clean(r.get("category"), 40) or ASSET_NAMES.get(asset) or asset or "Other"
    return {"t": int(t), "k": clean(r.get("ticker"), 64), "s": clean(r.get("strategy"), 60) or "Unlabelled", "m": market, "sd": side,
            "p": round(price, 4), "c": c, "pnl": round(pnl, 4)}


def trade_key(tr):
    return f"{tr['k']}|{tr['t']}|{tr['sd']}|{tr['c']}|{tr['p']}"


def outcome(pnl):
    return 1 if pnl > 0.005 else (-1 if pnl < -0.005 else 0)


def dims_of(tr):
    return (tr["s"], tr["m"], hour_block(tr["t"]), band_label(tr["p"]) or "?", tr["sd"] or "?")


class Acc:
    """Running sums for one group of bets (pushes, a pnl of about 0, are not bets)."""
    __slots__ = ("n", "wins", "push", "sp", "sv", "staked", "pnl", "first", "last")

    def __init__(self):
        self.n = self.wins = self.push = 0
        self.sp = self.sv = self.staked = self.pnl = 0.0
        self.first, self.last = None, None

    def add(self, tr):
        o = outcome(tr["pnl"])
        if o == 0:
            self.push += 1
            return
        self.n += 1
        self.wins += 1 if o > 0 else 0
        self.sp += tr["p"]
        self.sv += tr["p"] * (1 - tr["p"])
        self.staked += tr["c"] * tr["p"]
        self.pnl += tr["pnl"]
        self.first = tr["t"] if self.first is None else min(self.first, tr["t"])
        self.last = tr["t"] if self.last is None else max(self.last, tr["t"])


def acc_stats(a):
    """An Acc -> the public numbers of one window."""
    n = a.n
    if n == 0:
        return {"n": 0, "wins": 0, "w": None, "p": None, "pts": None, "ev": None, "pnl": 0.0, "staked": 0.0, "z": None, "pv": None, "lo": None, "hi": None}
    w, p = a.wins / n, a.sp / n
    z, pv = z_test(a.wins, a.sp, a.sv)
    lo, hi = wilson(a.wins, n)
    return {"n": n, "wins": a.wins, "w": w, "p": p, "pts": w - p, "ev": (a.pnl / a.staked) if a.staked > 0 else None, "pnl": a.pnl,
            "staked": a.staked, "z": z, "pv": pv, "lo": lo, "hi": hi}


def status_of(n, ev, z, ev_recent):
    """The five-state verdict (see the module doc). ev_recent is None when no recent window holds enough bets."""
    if n < MIN_N or ev is None:
        return "NEW"
    if ev <= 0:
        if (z is not None and z <= -Z_SIG) or (ev_recent is not None and ev_recent <= 0):
            return "DEAD"
        return "DECAYING"
    if ev_recent is not None:
        r = ev_recent / ev
        if r < 0.5:
            return "DECAYING"
        if r > 1.5:
            return "GROWING"
    return "HOLDING"


def advice_of(status, small, ev, z, kelly_safe):
    if small:
        return "collect"
    if status == "DEAD":
        return "stop"
    if status == "DECAYING":
        return "watch"
    if ev is not None and ev > 0 and z is not None and z >= Z_SIG and kelly_safe and kelly_safe > 0:
        return "do_more"
    return "keep"


# ------------------------------------------------------------------------------------------------ labels
def edge_id(dims):
    return "~".join(dims)


def dim_word(i, v):
    """One dimension of an edge in plain words: 'at 95-97c', 'buying YES', '10-14 ET'."""
    if i == 3:
        return {"<20c": "under 20c", "99c+": "at 99c+"}.get(v, f"at {v}")
    if i == 4:
        return f"buying {v.upper()}"
    return v


def edge_label(dims):
    parts = [dim_word(i, d) for i, d in enumerate(dims) if d != "*"]
    return " · ".join(parts) if parts else "Everything"


def edge_kind(dims):
    fixed = [DIMS[i] for i, d in enumerate(dims) if d != "*"]
    return fixed[0] if len(fixed) == 1 else "combo"


# ------------------------------------------------------------------------------------------------ the feed
def load_feed(src):
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "kalshi-city-edges/1"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    with open(src, encoding="utf-8") as fh:
        return json.load(fh)


def feed_trades(feed):
    return [x for x in (norm_trade(r) for r in (feed.get("trades") or [])) if x]


def feed_totals(feed):
    """The feed's whole-life totals: {family: {name: {n, wins, pnl, staked | None, p | None}}} for strategy, market and band."""
    out = {"strategy": {}, "market": {}, "band": {}}
    for s in feed.get("strategies") or []:
        if not isinstance(s, dict) or not clean(s.get("name")):
            continue
        w, l = num(s.get("wins")), num(s.get("losses"))
        if w is None or l is None:
            continue
        out["strategy"][clean(s["name"], 60)] = {"n": int(w + l), "wins": int(w), "pnl": num(s.get("total_pnl")) or 0.0, "staked": None, "p": None}
    for c in feed.get("categories") or []:
        if not isinstance(c, dict) or not clean(c.get("name")):
            continue
        w, l = num(c.get("wins")), num(c.get("losses"))
        if w is None or l is None:
            continue
        out["market"][clean(c["name"], 40)] = {"n": int(w + l), "wins": int(w), "pnl": num(c.get("pnl")) or 0.0, "staked": num(c.get("staked")), "p": None}
    cal = [c for c in (feed.get("calibration") or []) if isinstance(c, dict) and num(c.get("p")) is not None]
    for b in feed.get("buckets") or []:
        if not isinstance(b, dict) or num(b.get("lo")) is None:
            continue
        i = band_index(num(b["lo"]) + 1e-9)
        w, l = num(b.get("wins")), num(b.get("losses"))
        if i is None or w is None or l is None:
            continue
        pm = next((num(c["p"]) for c in cal if int(num(c.get("n")) or -1) == int(w + l) and BAND_EDGES[i] <= num(c["p"]) < BAND_EDGES[i + 1]), None)
        out["band"][BAND_LABELS[i]] = {"n": int(w + l), "wins": int(w), "pnl": num(b.get("pnl")) or 0.0, "staked": num(b.get("staked")), "p": pm}
    return out


# ------------------------------------------------------------------------------------------------ the ledger
def empty_ledger():
    return {"v": VERSION, "trades": [], "snaps": []}


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    os.replace(tmp, path)


def merge_trades(ledger, new):
    """Add the trades the ledger has not seen (by key); returns how many were new. Keeps the ledger sorted by time."""
    seen = {trade_key(t) for t in ledger["trades"]}
    k = 0
    for t in new:
        key = trade_key(t)
        if key not in seen:
            seen.add(key)
            ledger["trades"].append(t)
            k += 1
    if k:
        ledger["trades"].sort(key=lambda t: (t["t"], t["k"], t["sd"], t["c"], t["p"]))
    return k


def add_snapshot(ledger, feed, t):
    """One snapshot of the feed's totals per ET day (the latest of the day wins)."""
    tot = feed_totals(feed)
    snap = {"t": int(t), "d": et_date(t)}
    for fam, rows in tot.items():
        snap[fam] = {k: [v["n"], v["wins"], r4(v["pnl"]), r4(v["staked"])] for k, v in rows.items()}
    ledger["snaps"] = [s for s in ledger["snaps"] if s.get("d") != snap["d"]] + [snap]
    ledger["snaps"].sort(key=lambda s: s["t"])
    ledger["snaps"] = ledger["snaps"][-400:]


def snap_window(ledger, family, name, now, days):
    """The change in a feed total over the last `days` days: {n, wins, pnl, staked} or None (no snapshot that old yet)."""
    old = [s for s in ledger["snaps"] if s["t"] <= now - days * DAY]
    cur = ledger["snaps"][-1] if ledger["snaps"] else None
    if not old or cur is None or name not in cur.get(family, {}) or name not in old[-1].get(family, {}):
        return None
    a, b = old[-1][family][name], cur[family][name]
    d = {"n": b[0] - a[0], "wins": b[1] - a[1], "pnl": (b[2] or 0) - (a[2] or 0), "staked": None if b[3] is None or a[3] is None else b[3] - a[3]}
    return d if d["n"] >= 0 else None


def history_files(paths):
    files = []
    for p in paths or []:
        files += sorted(glob.glob(os.path.join(p, "*.json"))) if os.path.isdir(p) else [p]
    return files


def git_history(repo, limit=2000):
    """Every historical version of kalshi.json in a clone: yields the parsed feeds, oldest first."""
    revs = subprocess.run(["git", "-C", repo, "log", f"-n{int(limit)}", "--format=%H", "--", "kalshi.json"], capture_output=True, text=True, timeout=120).stdout.split()
    for rev in reversed(revs):
        p = subprocess.run(["git", "-C", repo, "show", f"{rev}:kalshi.json"], capture_output=True, text=True, timeout=60)
        if p.returncode == 0:
            try:
                yield json.loads(p.stdout)
            except ValueError:
                continue


# ------------------------------------------------------------------------------------------------ the edges
def build_edges(ledger, feed, now, prev_edges, bankroll):
    trades = ledger["trades"]
    totals = feed_totals(feed)
    st = feed.get("stats") or {}
    g_price = num(st.get("avg_price")) or 0.94
    g_stake = (num(st.get("staked")) / num(st.get("trades"))) if num(st.get("staked")) and num(st.get("trades")) else 12.0
    days = [str(d[0]) for d in (feed.get("days") or []) if isinstance(d, (list, tuple)) and d]
    baseline = prev_edges is None
    feed_first = days[0] if days else (et_date(trades[0]["t"]) if trades else et_date(now))

    groups = {}                                                       # dims tuple -> list of trades
    for tr in trades:
        d = dims_of(tr)
        for size in (1, 2, 3):
            for combo in itertools.combinations(range(5), size):
                groups.setdefault(tuple(d[i] if i in combo else "*" for i in range(5)), []).append(tr)

    rows = {}
    for key, trs in groups.items():
        size = sum(1 for d in key if d != "*")
        if sum(1 for x in trs if outcome(x["pnl"]) != 0) >= MIN_N_BY_SIZE[size]:
            rows[key] = trs

    # the feed's whole-life totals for the single-dimension families add the edges the ledger has not seen yet
    feed_key = {}
    for fam, idx in (("strategy", 0), ("market", 1), ("band", 3)):
        for name in totals[fam]:
            key = tuple(name if i == idx else "*" for i in range(5))
            feed_key[key] = (fam, name)
            rows.setdefault(key, [])
    # a combination that holds exactly the same bets as a simpler edge says nothing new: drop it (a Bitcoin-only strategy's "strategy + Bitcoin")
    seen_sig = {}
    for key in sorted(rows, key=lambda k: (sum(1 for d in k if d != "*"), k)):
        trs = rows[key]
        if not trs:
            continue
        sg = (len(trs), round(sum(t["pnl"] for t in trs), 4), round(sum(t["p"] for t in trs), 4))
        if sg in seen_sig and sum(1 for d in key if d != "*") > 1 and key not in feed_key:
            del rows[key]
        else:
            seen_sig.setdefault(sg, key)
    small_keys = [k for k in rows if sum(1 for d in k if d != "*") == 1]
    big_keys = sorted((k for k in rows if sum(1 for d in k if d != "*") > 1), key=lambda k: (-len(rows[k]), k))[: max(0, MAX_EDGES - len(small_keys))]

    prev = {e["id"]: e for e in (prev_edges or [])}
    today = et_date(now)
    out = []
    for key in small_keys + big_keys:
        trs = rows[key]
        eid = edge_id(key)
        a_all, a7, a30 = Acc(), Acc(), Acc()
        for tr in trs:
            a_all.add(tr)
            if tr["t"] >= now - 30 * DAY:
                a30.add(tr)
            if tr["t"] >= now - 7 * DAY:
                a7.add(tr)
        led, win7, win30 = acc_stats(a_all), acc_stats(a7), acc_stats(a30)
        main, src, p_basis = led, "ledger", "bets"
        if key in feed_key and totals[feed_key[key][0]][feed_key[key][1]]["n"] > led["n"]:
            fam, name = feed_key[key]
            f = totals[fam][name]
            src = "feed"
            w = f["wins"] / f["n"] if f["n"] else None
            if f["p"]:                                               # a price band: the feed's calibration row holds the mean entry price
                p, p_basis, staked = f["p"], "price", f["staked"]
            else:                                                    # a strategy or a market: the break-even win rate w / (1 + EV), fees in
                staked = f["staked"] if f["staked"] else f["n"] * g_stake
                p, p_basis = (w / (1 + f["pnl"] / staked)) if (w and staked) else g_price, "break-even win rate"
                if not f["staked"]:
                    p_basis += " + estimated stake"
            p = min(max(p, 0.01), 0.99)
            z, pv = z_test(f["wins"], f["n"] * p, f["n"] * p * (1 - p))
            lo, hi = wilson(f["wins"], f["n"])
            main = {"n": f["n"], "wins": f["wins"], "w": w, "p": p, "pts": (w - p) if w is not None else None, "ev": f["pnl"] / staked if staked else None,
                    "pnl": f["pnl"], "staked": staked, "z": z, "pv": pv, "lo": lo, "hi": hi}
            # windows of a feed total: the change in the feed's own totals once a snapshot is old enough, else the ledger's window
            for days_w in (7, 30):
                d = snap_window(ledger, fam, name, now, days_w)
                if d and d["n"] > 0:
                    stk = d["staked"] if d["staked"] else d["n"] * (staked / f["n"])
                    ww = d["wins"] / d["n"]
                    wd = {"n": d["n"], "wins": d["wins"], "w": ww, "p": p, "pts": ww - p, "ev": d["pnl"] / stk if stk else None, "pnl": d["pnl"], "staked": stk,
                          "z": None, "pv": None, "lo": None, "hi": None}
                    if days_w == 7:
                        win7 = wd
                    else:
                        win30 = wd
        n, ev, z = main["n"], main["ev"], main["z"]
        small = n < MIN_N
        recent, recent_basis = None, None
        if win7["n"] >= MIN_N and win7["ev"] is not None:        # a recent window is only believed with a verdict's worth of bets
            recent, recent_basis = win7, "7d"
        elif win30["n"] >= MIN_N and win30["ev"] is not None:
            recent, recent_basis = win30, "30d"
        ev_recent = recent["ev"] if recent else None
        status = status_of(n, ev, z, ev_recent)
        # Kelly: only with a verdict and a positive realised EV; the safe fraction uses the Wilson lower bound of the win rate
        kf = ks = kq = stake = ruin_k = None
        if main["w"] is not None and main["p"] is not None and 0 < main["p"] < 1:
            kf = kelly_full(main["w"], main["p"])
            ks = max(0.0, kelly_full(main["lo"], main["p"])) if (not small and ev is not None and ev > 0) else 0.0
            kq = KELLY_FRACTION * ks
            stake = kq * bankroll if bankroll else None
            ruin_k = ruin_half(main["lo"], main["p"], kq) if kq > 0 else 0.0        # the chance of losing half, on the conservative win rate
        advice = advice_of(status, small, ev, z, ks)
        pe = prev.get(eid)
        if pe:
            first, since = pe["first"], (pe["since"] if pe["status"] == status else today)
        elif baseline:                                               # the very first run: everything was already there before the engine began to watch
            first, since = feed_first, feed_first
        else:
            first, since = today, today
        out.append({
            "id": eid, "dims": list(key), "label": edge_label(key), "kind": edge_kind(key), "size": sum(1 for d in key if d != "*"),
            "n": n, "wins": main["wins"], "w": r4(main["w"]), "p": r4(main["p"]), "pts": r4(main["pts"]), "ev": r4(ev), "pnl": r4(main["pnl"]), "staked": r4(main["staked"]),
            "lo": r4(main["lo"]), "hi": r4(main["hi"]), "z": r4(z), "pv": r4(main["pv"]), "sig": "+" if (z is not None and z >= Z_SIG) else ("-" if (z is not None and z <= -Z_SIG) else ""),
            "win": {"d7": _win(win7), "d30": _win(win30), "led": _win(led)}, "recent": recent_basis,
            "decay": r4(ev_recent - ev) if (ev_recent is not None and ev is not None) else None,
            "kelly": r4(kf), "kelly_safe": r4(ks), "kelly_q": r4(kq), "stake": r4(stake), "ruin": r4(ruin_k),
            "status": status, "advice": advice, "small": small, "src": src, "p_basis": p_basis,
            "first": first, "since": since, "last": et_date(a_all.last) if a_all.last else None,
        })
    order = {"strategy": 0, "market": 1, "band": 2, "side": 3, "hour": 4, "combo": 5}
    out.sort(key=lambda e: (order[e["kind"]], -e["n"], e["id"]))
    return out


def _win(s):
    return {"n": s["n"], "w": r4(s["w"]), "ev": r4(s["ev"]), "pnl": r4(s["pnl"])}


# ------------------------------------------------------------------------------------------------ the book, the weather, the lists
def downsample(rows, k):
    if len(rows) <= k:
        return rows
    step = (len(rows) - 1) / (k - 1)
    return [rows[round(i * step)] for i in range(k)]


def book_of(feed, ledger, now):
    bal = num(feed.get("balance"))
    days = [(str(d[0]), num(d[1]) or 0.0) for d in (feed.get("days") or []) if isinstance(d, (list, tuple)) and len(d) >= 2]
    last7, last30 = days[-7:], days[-30:]
    st = feed.get("stats") or {}
    nw, nl = num(st.get("wins")) or 0.0, num(st.get("losses")) or 0.0
    w = nw / max(1.0, nw + nl)
    p = num(st.get("avg_price"))
    ev_book = (num(st.get("pnl")) / num(st.get("staked"))) if num(st.get("staked")) and num(st.get("pnl")) is not None else None
    p_eff = min(max(w / (1 + ev_book), 0.01), 0.99) if (ev_book is not None and w) else p          # the break-even win rate, fees in
    recent = [t for t in ledger["trades"] if t["t"] >= now - 7 * DAY]
    avg_stake = (sum(t["c"] * t["p"] for t in recent) / len(recent)) if len(recent) >= 5 else ((num(st.get("staked")) / num(st.get("trades"))) if num(st.get("staked")) and num(st.get("trades")) else None)
    frac = (avg_stake / bal) if (avg_stake and bal) else None
    kb = kelly_full(w, p_eff) if p_eff else None
    positions = []
    for q in (feed.get("positions") or [])[:20]:
        if isinstance(q, dict):
            positions.append({"ticker": clean(q.get("ticker"), 64), "title": clean(q.get("title"), 90),
                              "market": clean(q.get("category"), 40) or ASSET_NAMES.get(clean(q.get("asset"), 8).upper(), "Other"),
                              "strategy": clean(q.get("strategy"), 60), "side": clean(q.get("side"), 8).lower(), "contracts": num(q.get("contracts")),
                              "price": dollars(q.get("price")) or dollars(q.get("avg_price")), "closes": parse_t(q.get("closes"))})
    eq = [e for e in (feed.get("equity") or []) if isinstance(e, (list, tuple)) and len(e) >= 2 and num(e[1]) is not None]
    return {
        "name": clean(feed.get("name"), 40) or "Kalshi bot", "mode": clean(feed.get("mode"), 12).lower(), "running": feed.get("running") if isinstance(feed.get("running"), bool) else None,
        "status": clean(feed.get("status"), 80), "note": clean(feed.get("note"), 80), "feed_t": int(parse_t(feed.get("t")) or now), "balance": r4(bal),
        "today": r4(num(feed.get("today_pnl"))), "week": r4(num(feed.get("week_pnl"))), "total": r4(num(feed.get("total_pnl"))),
        "pnl7": r4(sum(d[1] for d in last7)), "pnl30": r4(sum(d[1] for d in last30)), "win_days7": sum(1 for d in last7 if d[1] > 0), "days7": len(last7),
        "worst_day": r4(min((d[1] for d in days), default=None)), "best_day": r4(max((d[1] for d in days), default=None)),
        "bets_total": int(num(st.get("trades")) or 0), "w": r4(w) if p_eff else None, "p": r4(p_eff), "ev": r4(ev_book), "stake_avg": r4(avg_stake), "stake_frac": r4(frac),
        "kelly_book": r4(kb), "ruin_now": r4(ruin_half(w, p_eff, frac)) if (p_eff and frac) else None,
        "ruin_kelly": r4(ruin_half(w, p_eff, KELLY_FRACTION * max(0.0, kb))) if (p_eff and kb and kb > 0) else 0.0,
        "days": [[d, r4(v)] for d, v in days[-45:]],
        "equity": [[int(parse_t(e[0]) or 0), r4(num(e[1]))] for e in downsample(eq, 60)],
        "positions": positions,
        "recent": [{"t": t["t"], "market": t["m"], "strategy": t["s"], "side": t["sd"], "price": t["p"], "pnl": t["pnl"]} for t in ledger["trades"][-14:]][::-1],
        "calibration": [{"p": r4(num(c.get("p"))), "n": int(num(c.get("n")) or 0), "hit": r4(num(c.get("hit")))} for c in (feed.get("calibration") or [])
                        if isinstance(c, dict) and num(c.get("p")) is not None],
    }


def regime_of(book, now):
    """The market weather: storm / rain / overcast / clear, plus 'paused' (fog) when the bot is not running."""
    bal = book["balance"] or 0.0
    worst3 = min((v for _, v in book["days"][-3:]), default=0.0)
    p7 = book["pnl7"] or 0.0
    wd, nd = book["win_days7"], max(1, book["days7"])
    paused = book["running"] is False or "paus" in (book["status"] or "").lower()
    if bal and worst3 <= -0.12 * bal:
        state, why = "storm", f"a bad day in the last three: {worst3:+.2f} on a ${bal:,.0f} bankroll"
    elif p7 < 0:
        state, why = "rain", f"the last 7 days lost ${abs(p7):.2f}"
    elif p7 > 0 and wd / nd >= 0.5:
        state, why = "clear", f"the last 7 days earned ${p7:.2f}, {wd} of {nd} days up"
    else:
        state, why = "overcast", f"the last 7 days are flat ({p7:+.2f}), {wd} of {nd} days up"
    return {"state": state, "paused": bool(paused), "why": why, "pnl7": book["pnl7"], "t": int(now)}


def lists_of(edges):
    real = [e for e in edges if not e["small"]]
    do_more = sorted((e for e in real if e["advice"] == "do_more"), key=lambda e: -((e["lo"] or 0) - (e["p"] or 0)))
    stop = sorted((e for e in real if e["advice"] == "stop"), key=lambda e: (e["pnl"] or 0))
    watch = sorted((e for e in real if e["advice"] == "watch"), key=lambda e: (e["ev"] or 0))
    board = sorted((e for e in real if e["ev"] is not None), key=lambda e: -((e["lo"] or 0) - (e["p"] or 0)))
    return {"do_more": [e["id"] for e in do_more[:12]], "stop": [e["id"] for e in stop[:12]], "watch": [e["id"] for e in watch[:12]], "board": [e["id"] for e in board[:25]]}


# ------------------------------------------------------------------------------------------------ the learning log
def money(x):
    return f"{'-' if x < 0 else '+'}${abs(x):.{4 if abs(x) < 0.001 else 3 if abs(x) < 0.0095 else 2}f}"


def lesson_text(e, prefix="Learned"):
    return f"{prefix}: {e['label']}: EV {money(e['ev'])} per $1 over {e['n']} bets: {ADVICE_WORD[e['advice']]}"


def log_entries(edges, prev_edges, prev_log, now, new_bets, ledger_n, total_bets):
    """The new lessons of this run (the log is append-only: these are only ever added at the end)."""
    prev = {e["id"]: e for e in (prev_edges or [])}
    first_run = prev_edges is None
    seen = {x.get("ek") for x in prev_log}
    day, entries = et_date(now), []

    def add(ek, kind, e, text):
        if ek in seen:
            return
        seen.add(ek)
        entries.append({"d": day, "t": int(now), "kind": kind, "id": e["id"], "status": e["status"], "advice": e["advice"], "n": e["n"], "ev": e["ev"], "pnl": e["pnl"], "text": text, "ek": ek})
    spotted = 0
    for e in sorted(edges, key=lambda x: -abs(x["pnl"] or 0)):
        p = prev.get(e["id"])
        # the log stays readable: whole families, anything the engine says to do more or stop, and dead pairs (not every small combination)
        if not (e["size"] == 1 or e["advice"] in ("do_more", "stop") or (p and p["advice"] in ("do_more", "stop")) or (e["size"] == 2 and e["status"] == "DEAD")):
            continue
        if len(entries) >= MAX_LOG_PER_RUN:
            break
        if e["small"]:
            if p is None and e["size"] <= 2 and spotted < 6 and not first_run and e["n"] >= 5:
                spotted += 1
                add(f"{e['id']}|spot", "spotted", e, f"Spotted: {e['label']}: {e['n']} bets so far, too few to judge")
            continue
        if p is None or p["small"]:
            add(f"{e['id']}|verdict|{e['advice']}", "learned", e, lesson_text(e))
        elif p["status"] != e["status"]:
            word = {"DEAD": "Crumbled", "GROWING": "Growing", "DECAYING": "Fading", "HOLDING": "Steady"}.get(e["status"], "Changed")
            add(f"{e['id']}|status|{p['status']}>{e['status']}|{day}", "changed", e,
                f"{word}: {e['label']}: {p['status']} -> {e['status']}, EV {money(e['ev'])} per $1 over {e['n']} bets: {ADVICE_WORD[e['advice']]}")
        elif p["advice"] != e["advice"]:
            add(f"{e['id']}|advice|{p['advice']}>{e['advice']}|{day}", "changed", e, lesson_text(e, "Update"))
    if new_bets > 0:
        cov = f"{ledger_n} of the bot's {total_bets}" if total_bets >= ledger_n else str(ledger_n)
        entries.append({"d": day, "t": int(now), "kind": "run", "id": None, "status": None, "advice": None, "n": new_bets, "ev": None, "pnl": None,
                        "text": f"Read {new_bets} new bets one by one ({cov} now in the ledger)", "ek": f"run|{int(now)}|{ledger_n}"})
    return entries


def headline_of(log):
    """The line the city opens with: the biggest lesson (by $) of the latest day, a do-more or a stop first."""
    learned = [x for x in log if x["kind"] in ("learned", "changed")]
    pool = [x for x in learned if x.get("advice") in ("do_more", "stop")] or learned
    if not pool:
        return None
    day = max(x["d"] for x in pool)
    return max((x for x in pool if x["d"] == day), key=lambda x: abs(x.get("pnl") or 0))["text"]


# ------------------------------------------------------------------------------------------------ the Jarvis card
def jarvis_card(doc):
    c, bk = doc["counts"], doc["book"]
    ru = bk.get("ruin_now")
    lines = []
    if doc.get("headline"):
        lines.append(doc["headline"][:120])
    lines.append((f"Bot {bk['status'] or bk['mode']}: bankroll ${bk['balance']:,.2f}. Weather: {doc['regime']['state']}." if bk.get("balance") is not None else "Bot status unknown.")[:120])
    return {"v": 1, "name": "Kalshi City", "status": {"level": "warn" if doc["regime"]["state"] in ("rain", "storm") else "ok", "label": f"{c['do_more']} do more · {c['stop']} stop"},
            "kpis": [{"label": "Do more", "value": str(c["do_more"])}, {"label": "Stop", "value": str(c["stop"])}, {"label": "Ruin risk", "value": f"{round(ru * 100)}%" if ru is not None else "-"}],
            "lines": lines[:3], "t": int(doc["t"]), "open": "#learn", "theme": "#06100f", "stale_after": 259200}


# ------------------------------------------------------------------------------------------------ the run
def run(feed, out, now=None, history=(), history_git=None):
    """One refresh. Returns (edges_doc, new_log_entries, new_bets). Writes ledger.json, edges.json, learning_log.json, jarvis.json into `out`."""
    ledger = read_json(os.path.join(out, "ledger.json"), None)
    if not isinstance(ledger, dict) or not isinstance(ledger.get("trades"), list):
        ledger = empty_ledger()
    ledger.setdefault("snaps", [])
    prev_doc = read_json(os.path.join(out, "edges.json"), None)
    prev_edges = prev_doc.get("edges") if isinstance(prev_doc, dict) and isinstance(prev_doc.get("edges"), list) else None
    log_doc = read_json(os.path.join(out, "learning_log.json"), None)
    prev_log = log_doc.get("entries") if isinstance(log_doc, dict) and isinstance(log_doc.get("entries"), list) else []

    hist_new = 0
    feeds = []
    for f in history_files(history):
        try:
            feeds.append(load_feed(f))
        except (OSError, ValueError):
            continue
    if history_git:
        feeds += list(git_history(history_git))
    for h in feeds:
        if isinstance(h, dict):
            hist_new += merge_trades(ledger, feed_trades(h))
            if parse_t(h.get("t")):
                add_snapshot(ledger, h, parse_t(h["t"]))
    new_bets = merge_trades(ledger, feed_trades(feed)) + hist_new
    ft = parse_t(feed.get("t"))
    last_trade = max((t["t"] for t in ledger["trades"]), default=0)
    now = float(now if now is not None else (max(ft or 0, last_trade) or datetime.now(timezone.utc).timestamp()))
    add_snapshot(ledger, feed, now)

    bankroll = num(feed.get("balance")) or 0.0
    edges = build_edges(ledger, feed, now, prev_edges, bankroll)
    book = book_of(feed, ledger, now)
    regime = regime_of(book, now)
    counts = {s: sum(1 for e in edges if e["status"] == s) for s in ("NEW", "GROWING", "HOLDING", "DECAYING", "DEAD")}
    counts.update({k: sum(1 for e in edges if e["advice"] == k) for k in ("do_more", "stop", "watch")})
    counts.update({"edges": len(edges), "proven": sum(1 for e in edges if not e["small"])})
    entries = log_entries(edges, prev_edges, prev_log, now, new_bets, len(ledger["trades"]), book["bets_total"])
    log = prev_log + entries
    ts = [t["t"] for t in ledger["trades"]]
    doc = {
        "v": VERSION, "kind": "kalshi-edges", "t": int(now), "day": et_date(now), "source": "kalshi-feed",
        "ledger": {"n": len(ledger["trades"]), "first": min(ts) if ts else None, "last": max(ts) if ts else None, "bets_total": book["bets_total"],
                   "seen_share": r4(len(ledger["trades"]) / book["bets_total"]) if book["bets_total"] else None, "new": new_bets, "snaps": len(ledger["snaps"])},
        "params": {"min_n": MIN_N, "z_sig": Z_SIG, "kelly_fraction": KELLY_FRACTION, "bands": list(BAND_LABELS), "dims": list(DIMS)},
        "counts": counts, "regime": regime, "book": book, "lists": lists_of(edges),
        "headline": headline_of(log),
        "edges": edges,
    }
    write_json(os.path.join(out, "ledger.json"), ledger)
    write_json(os.path.join(out, "edges.json"), doc)
    write_json(os.path.join(out, "learning_log.json"), {"v": VERSION, "about": "Append-only. Every lesson the engine learned, dated; old lines are never rewritten.", "entries": log})
    write_json(os.path.join(out, "jarvis.json"), jarvis_card(doc))
    return doc, entries, new_bets


def main(argv=None):
    ap = argparse.ArgumentParser(description="Kalshi City learning engine (read only).")
    ap.add_argument("--feed", default=RAW, help="kalshi.json: a path or an https address (default: the public kalshi-feed)")
    ap.add_argument("--out", default=OUT_DEFAULT, help="folder for edges.json, learning_log.json, ledger.json, jarvis.json")
    ap.add_argument("--now", type=float, default=None, help="unix seconds to use as 'now' (default: the feed's own time)")
    ap.add_argument("--history", nargs="*", default=[], help="older kalshi.json snapshots (files or folders)")
    ap.add_argument("--history-git", default=None, help="a clone of kalshi-feed: every commit of kalshi.json joins the ledger")
    a = ap.parse_args(argv)
    try:
        feed = load_feed(a.feed)
    except Exception as ex:                                   # an unreachable feed leaves every file as it was (stale beats invented)
        print(f"kalshi_edges: cannot read the feed ({ex}); nothing changed", file=sys.stderr)
        return 2
    if not isinstance(feed, dict) or feed.get("kind") != "kalshi":
        print("kalshi_edges: that is not a kalshi.json feed; nothing changed", file=sys.stderr)
        return 2
    doc, entries, new_bets = run(feed, a.out, now=a.now, history=a.history, history_git=a.history_git)
    c = doc["counts"]
    print(f"kalshi_edges: {doc['ledger']['n']} bets in the ledger (+{new_bets}), {c['edges']} edges ({c['proven']} with 30+ bets), "
          f"do more {c['do_more']}, stop {c['stop']}, watch {c['watch']}; weather {doc['regime']['state']}; +{len(entries)} log lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
