"""KALSHI CITY learning engine (tools/kalshi_edges.py, OLYMPUS 2026-11-04): the maths against an independent mirror.
  a. the formulas: Wilson 95%, the z-test, the normal tail, Kelly, the risk of ruin (a root solver of its own AND a seeded Monte Carlo), each checked
     against a second implementation written differently (closed forms, numeric integration, Newton, simulation) and against hand numbers
  b. every edge of a rich synthetic ledger (tools/kalshi_demo.py, the planted edges) recomputed by brute force from the raw bets: n, wins, pnl, win rate,
     implied probability, EV per $1, Wilson range, z, the 7 / 30 day windows, Kelly, the five statuses, the advice
  c. the feed-total edges (strategy / market / price band) against the feed's own numbers, and the 7 / 30 day windows of the totals from snapshots
  d. the learning log: append-only (old lines byte-identical), idempotent (a rerun adds nothing), a new verdict, a status change (HOLDING -> DEAD), honest small samples
  e. robustness: junk rows, duplicates, an unreachable feed leaves every file as it was, history from a folder and from a git clone
  e2. the one-off order export (CSV: time, ticker, side, book, contracts, price, pnl) joins the ledger and unlocks hour-of-day edges
  f. the shipped files: edges.json / ledger.json / learning_log.json / jarvis.json agree with each other and the fixture is exactly what tools/kalshi_demo.py makes
    python -X utf8 -m tests.test_kalshi_edges
"""
from __future__ import annotations

import copy
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import kalshi_demo as kd  # noqa: E402
from tools import kalshicity_learned as kl  # noqa: E402
from tools import kalshi_edges as ke  # noqa: E402

RES = []
NY = ZoneInfo("America/New_York")
PAGE = os.path.join(ROOT, "tools", "web_public", "kalshicity")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def close(a, b, tol=1e-9):
    return a is None and b is None or (a is not None and b is not None and abs(a - b) <= tol * max(1.0, abs(a), abs(b)))


# ------------------------------------------------------------------------------------------------ the mirror (written differently on purpose)
def m_wilson(wins, n, z=1.959963984540054):
    """The closed form (2nw + z^2 +- z sqrt(z^2 + 4nw(1-w))) / (2 (n + z^2)), not the centre-and-half-width form the engine uses."""
    w = wins / n
    root = z * math.sqrt(z * z + 4 * n * w * (1 - w))
    return (2 * n * w + z * z - root) / (2 * (n + z * z)), (2 * n * w + z * z + root) / (2 * (n + z * z))


def m_tail(z, steps=4000):
    """P(Z > z) by Simpson integration of the normal density, not math.erfc."""
    hi = 12.0
    if z >= hi:
        return 0.0
    h = (hi - z) / steps
    f = lambda x: math.exp(-x * x / 2) / math.sqrt(2 * math.pi)  # noqa: E731
    s = f(z) + f(hi) + sum((4 if i % 2 else 2) * f(z + i * h) for i in range(1, steps))
    return s * h / 3


def m_kelly(w, p):
    b = (1 - p) / p                       # net odds per $1 staked
    return w - (1 - w) / b


def m_ruin_newton(w, p, f):
    """Newton on g(t) = w e^{-t a} + (1-w) e^{t c} - 1 from a start well above the root (a different solver from the engine's bisection)."""
    b = (1 - p) / p
    a, c = math.log(1 + f * b), -math.log(1 - f)
    if w * a - (1 - w) * c <= 0:
        return 1.0
    g = lambda t: w * math.exp(-t * a) + (1 - w) * math.exp(t * c) - 1   # noqa: E731
    dg = lambda t: -w * a * math.exp(-t * a) + (1 - w) * c * math.exp(t * c)  # noqa: E731
    t = 2 * (w * a - (1 - w) * c) / (w * a * a + (1 - w) * c * c)        # the second-order guess (cumulant), then polish
    for _ in range(80):
        step = g(t) / dg(t)
        t -= step
        if abs(step) < 1e-14:
            break
    return min(1.0, math.exp(-t * math.log(2)))


def m_ruin_mc(w, p, f, paths=4000, horizon=600, seed=5):
    """Seeded Monte Carlo: how often the bankroll touches half within `horizon` bets (a lower bound of the all-time chance)."""
    rnd = random.Random(seed)
    b = (1 - p) / p
    hit = 0
    for _ in range(paths):
        x = 1.0
        for _ in range(horizon):
            x *= (1 + f * b) if rnd.random() < w else (1 - f)
            if x <= 0.5:
                hit += 1
                break
    return hit / paths


def m_band(price):
    table = [(0.0, 0.2, "<20c"), (0.2, 0.4, "20-40c"), (0.4, 0.6, "40-60c"), (0.6, 0.8, "60-80c"), (0.8, 0.9, "80-90c"), (0.9, 0.95, "90-95c"),
             (0.95, 0.97, "95-97c"), (0.97, 0.99, "97-99c"), (0.99, 1.0001, "99c+")]
    return next(lab for lo, hi, lab in table if lo <= price < hi)


def m_dims(t):
    h = datetime.fromtimestamp(t["t"], NY).hour
    return [t["s"], t["m"], f"{h - h % 4:02d}-{h - h % 4 + 4:02d} ET", m_band(t["p"]), t["sd"]]


def m_group(trades, dims, since=None):
    sel = [t for t in trades if all(d == "*" or m_dims(t)[i] == d for i, d in enumerate(dims)) and (since is None or t["t"] >= since)]
    bets = [t for t in sel if abs(t["pnl"]) > 0.005]
    n = len(bets)
    if not n:
        return {"n": 0}
    wins = sum(1 for t in bets if t["pnl"] > 0)
    sp = sum(t["p"] for t in bets)
    var = sum(t["p"] * (1 - t["p"]) for t in bets)
    staked = sum(t["c"] * t["p"] for t in bets)
    pnl = sum(t["pnl"] for t in bets)
    lo, hi = m_wilson(wins, n)
    z = (wins - sp) / math.sqrt(var) if var else None
    return {"n": n, "wins": wins, "w": wins / n, "p": sp / n, "pts": wins / n - sp / n, "ev": pnl / staked if staked else None, "pnl": pnl, "staked": staked, "lo": lo, "hi": hi, "z": z}


def m_status(n, ev, z, ev_recent):
    if n < 30 or ev is None:
        return "NEW"
    if ev <= 0:
        return "DEAD" if ((z is not None and z <= -1.6448536269514722) or (ev_recent is not None and ev_recent <= 0)) else "DECAYING"
    if ev_recent is not None and ev_recent / ev < 0.5:
        return "DECAYING"
    if ev_recent is not None and ev_recent / ev > 1.5:
        return "GROWING"
    return "HOLDING"


# ------------------------------------------------------------------------------------------------ a. formulas
def part_a():
    cases = [(38, 40), (3, 30), (990, 1000), (0, 12), (12, 12), (250, 500), (1, 1)]
    ok = True
    for wins, n in cases:
        a, b = ke.wilson(wins, n), m_wilson(wins, n)
        ok &= close(a[0], max(0.0, b[0]), 1e-12) and close(a[1], min(1.0, b[1]), 1e-12)
    check("a. Wilson 95% interval equals the closed form on 7 cases (including 0 of 12, 12 of 12 and 1 of 1)", ok)
    lo, hi = ke.wilson(50, 100)
    check("a. by hand: 50 of 100 gives 0.4038 to 0.5962", abs(lo - 0.4038) < 5e-4 and abs(hi - 0.5962) < 5e-4, (lo, hi))
    check("a. n = 0 gives the honest (0, 1)", ke.wilson(0, 0) == (0.0, 1.0))
    ok = True
    for z in (-3.1, -1.645, 0.0, 0.7, 1.96, 2.576, 4.0):
        sf = 0.5 * math.erfc(z / math.sqrt(2))
        ok &= abs(sf - m_tail(z)) < 1e-8
    z, pv = ke.z_test(60, 50.0, 25.0)
    check("a. the normal tail (erfc) equals numeric integration at 7 points", ok)
    check("a. z-test by hand: 60 wins against 50 expected with variance 25 is z = 2 (two-sided p 0.0455); no variance gives None",
          abs(z - 2.0) < 1e-12 and abs(pv - 2 * m_tail(2.0)) < 1e-7 and ke.z_test(5, 3.0, 0.0) == (None, None), (z, pv))
    ok = True
    for w, p in ((0.62, 0.55), (0.97, 0.95), (0.5, 0.5), (0.4, 0.5), (0.99, 0.9)):
        ok &= close(ke.kelly_full(w, p), m_kelly(w, p), 1e-12)
    check("a. Kelly (w - p) / (1 - p) equals w - (1 - w) / b on 5 cases; by hand: 0.6 against 0.5 is 0.2; no edge is 0; a loser is negative",
          ok and abs(ke.kelly_full(0.6, 0.5) - 0.2) < 1e-12 and ke.kelly_full(0.5, 0.5) == 0 and ke.kelly_full(0.4, 0.5) < 0 and ke.kelly_full(0.5, 1.0) is None)
    worst, ok = 0.0, True
    for w, p, f in ((0.62, 0.55, 0.05), (0.97, 0.95, 0.04), (0.6, 0.5, 0.1), (0.9, 0.8, 0.2), (0.99, 0.97, 0.02), (0.55, 0.5, 0.03)):
        a, b = ke.ruin_half(w, p, f), m_ruin_newton(w, p, f)
        worst = max(worst, abs(a - b))
        ok &= abs(a - b) < 1e-9
    check("a. the risk of ruin (bisection) equals Newton's root on 6 cases", ok, worst)
    ok, rows = True, []
    for w, p, f in ((0.6, 0.5, 0.1), (0.97, 0.95, 0.05), (0.62, 0.55, 0.06)):
        bound, mc = ke.ruin_half(w, p, f), m_ruin_mc(w, p, f)
        rows.append((round(bound, 3), round(mc, 3)))
        ok &= mc <= bound + 0.03 and bound - mc < 0.35     # a bound, close enough to be useful: the simulation sits just under it
    check("a. the ruin bound sits just above a seeded simulation of 4,000 paths (never below it)", ok, rows)
    check("a. ruin edge cases: nothing staked is 0; no edge or a loser is 1; a bigger stake is riskier; more edge is safer",
          ke.ruin_half(0.6, 0.5, 0) == 0 and ke.ruin_half(0.5, 0.5, 0.1) == 1.0 and ke.ruin_half(0.4, 0.5, 0.05) == 1.0
          and ke.ruin_half(0.62, 0.55, 0.12) > ke.ruin_half(0.62, 0.55, 0.04) and ke.ruin_half(0.70, 0.55, 0.08) < ke.ruin_half(0.60, 0.55, 0.08))
    cases = [(0.0, "<20c"), (0.199, "<20c"), (0.2, "20-40c"), (0.5, "40-60c"), (0.79, "60-80c"), (0.8, "80-90c"), (0.9, "90-95c"), (0.95, "95-97c"), (0.969, "95-97c"),
             (0.97, "97-99c"), (0.989, "97-99c"), (0.99, "99c+")]
    check("a. price bands follow the bot's own edges (lower edge inclusive)", all(ke.band_label(p) == lab and m_band(p) == lab for p, lab in cases))
    check("a. the ET hour block: 2026-11-02 21:30 ET is 20-24, 03:59 ET is 00-04 (and a summer date uses daylight time)",
          ke.hour_block(datetime(2026, 11, 2, 21, 30, tzinfo=NY).timestamp()) == "20-24 ET" and ke.hour_block(datetime(2026, 11, 2, 3, 59, tzinfo=NY).timestamp()) == "00-04 ET"
          and ke.hour_block(datetime(2026, 7, 1, 12, 0, tzinfo=NY).timestamp()) == "12-16 ET")
    st = [("NEW", 29, 0.1, 3.0, None), ("HOLDING", 100, 0.01, 1.0, None), ("HOLDING", 100, 0.01, 1.0, 0.012), ("GROWING", 100, 0.01, 1.0, 0.02), ("DECAYING", 100, 0.01, 1.0, 0.004),
          ("DECAYING", 100, 0.01, 1.0, -0.01), ("DEAD", 100, -0.02, -2.0, None), ("DECAYING", 100, -0.001, -0.5, None), ("DEAD", 100, -0.001, -0.5, -0.003), ("NEW", 100, None, None, None)]
    check("a. the five statuses on 10 hand cases (and the engine equals the mirror's rules)",
          all(ke.status_of(n, ev, z, r) == want == m_status(n, ev, z, r) for want, n, ev, z, r in st), [(w, ke.status_of(n, ev, z, r)) for w, n, ev, z, r in st])


# ------------------------------------------------------------------------------------------------ b / c. the rich ledger and the totals
def part_bc():
    tmp = tempfile.mkdtemp(prefix="kc_edges_")
    try:
        now_dt, trades = kd.make(36)
        full = kd.feed_of(now_dt, trades)
        feed = dict(full, trades=list(reversed(trades)))
        now = now_dt.timestamp()
        doc, entries, new = ke.run(feed, tmp, now=now)
        led = ke.read_json(os.path.join(tmp, "ledger.json"), {})
        raw = led["trades"]
        check("b. the ledger holds every invented bet once (1,513) and a snapshot of the totals", len(raw) == len(trades) == new and len(led["snaps"]) == 1, (len(raw), len(trades), new))
        edges = {e["id"]: e for e in doc["edges"]}
        led_edges = [e for e in doc["edges"] if e["src"] == "ledger"]
        bad, kelly_bad, stat_bad, win_bad = [], [], [], []
        for e in led_edges:
            m = m_group(raw, e["dims"])
            keys = ("n", "wins", "w", "p", "pts", "ev", "pnl", "staked", "lo", "hi", "z")
            if not all(close(e[k], m[k], 2e-4) or (e[k] is not None and m[k] is not None and abs(e[k] - m[k]) < 6e-5) for k in keys):
                bad.append((e["id"], {k: (e[k], m[k]) for k in keys if not close(e[k], m[k], 2e-4)}))
            r7, r30 = m_group(raw, e["dims"], now - 7 * 86400), m_group(raw, e["dims"], now - 30 * 86400)
            if e["win"]["d7"]["n"] != r7["n"] or e["win"]["d30"]["n"] != r30["n"] or (r30["n"] and abs((e["win"]["d30"]["ev"] or 0) - r30["ev"]) > 6e-5):
                win_bad.append((e["id"], e["win"]["d7"]["n"], r7["n"], e["win"]["d30"]["n"], r30["n"]))
            rec = r7 if r7["n"] >= 30 else (r30 if r30["n"] >= 30 else None)
            want = m_status(m["n"], m["ev"], m["z"], rec["ev"] if rec else None)
            if e["status"] != want:
                stat_bad.append((e["id"], e["status"], want))
            # Kelly: safe fraction on the Wilson lower bound, zero without a verdict or a positive EV; quarter of it; the stake in $
            ks = max(0.0, m_kelly(m["lo"], m["p"])) if (m["n"] >= 30 and m["ev"] > 0) else 0.0
            if not (close(e["kelly_safe"], ks, 1e-3) and close(e["kelly_q"], 0.25 * ks, 1e-3) and close(e["kelly"], m_kelly(m["w"], m["p"]), 1e-3)):
                kelly_bad.append((e["id"], e["kelly_safe"], ks))
            if e["small"] and (e["stake"] not in (0, 0.0) or e["advice"] != "collect" or e["status"] != "NEW"):
                kelly_bad.append((e["id"], "small but sized", e["stake"]))
        check(f"b. every one of the {len(led_edges)} ledger edges equals a brute-force recount (n, wins, win rate, implied p, EV, pnl, staked, Wilson, z)", not bad, bad[:2])
        check("b. the 7 and 30 day windows count the same bets as the brute force, and the 30 day EV agrees", not win_bad, win_bad[:3])
        check("b. every status equals the mirror's rules (recent window = last 7 days, else 30, only when it holds 30+ bets)", not stat_bad, stat_bad[:3])
        check("b. every Kelly number equals the mirror (safe on the Wilson lower bound, quarter of it, zero below 30 bets or with EV <= 0)", not kelly_bad, kelly_bad[:3])
        ruin_bad = [e["id"] for e in led_edges if e["kelly_q"] and abs(e["ruin"] - m_ruin_newton(e["lo"], e["p"], e["kelly_q"])) > 0.01 * e["ruin"] + 1e-3]    # on the Wilson lower win rate; kelly_q is stored to 4 places
        check("b. the risk of ruin of every sized edge equals Newton's root", not ruin_bad and any(e["kelly_q"] for e in led_edges), ruin_bad[:3])
        planted = {
            "dead": edges.get("*~XRP~*~*~*"), "decay": edges.get("15-min favourites~Ethereum~*~*~*"), "value": edges.get("Value~*~*~*~*"),
            "grow": edges.get("combo~*~*~*~*"), "new": edges.get("Gold 5 PM~*~*~*~*"), "hourly": edges.get("Hourly BTC~*~*~*~*"),
        }
        check("b. the planted edges come out right: XRP is DEAD and STOP, Value is DEAD, the new Gold rule is NEW and greyed (too few), Ethereum is not HOLDING",
              planted["dead"]["status"] == "DEAD" and planted["dead"]["advice"] == "stop" and planted["value"]["status"] == "DEAD" and planted["new"]["status"] == "NEW" and planted["new"]["small"]
              and planted["new"]["advice"] == "collect" and planted["decay"]["status"] in ("DECAYING", "DEAD"), {k: (v or {}).get("status") for k, v in planted.items()})
        check("b. at least one proven DO MORE edge, each with ev > 0, z >= 1.645 and a stake; every STOP is DEAD with 30+ bets",
              doc["counts"]["do_more"] >= 1 and all(e["ev"] > 0 and e["z"] >= 1.6448 and e["stake"] > 0 for e in doc["edges"] if e["advice"] == "do_more")
              and all(e["status"] == "DEAD" and e["n"] >= 30 for e in doc["edges"] if e["advice"] == "stop"))
        check("b. combinations that hold the same bets as a simpler edge are dropped (no 'strategy + Bitcoin' twin of a Bitcoin-only strategy)",
              "Late favourite (BTC hourly)~Bitcoin~*~*~*" not in edges and "Late favourite (BTC hourly)~*~*~*~*" in edges)
        # c. the feed totals
        tot = ke.feed_totals(full)
        c_bad = []
        for fam, idx in (("strategy", 0), ("market", 1), ("band", 3)):
            for name, f in tot[fam].items():
                e = edges.get(ke.edge_id(["*"] * idx + [name] + ["*"] * (4 - idx)))
                if e is None or e["n"] != f["n"] or e["wins"] != f["wins"] or not close(e["pnl"], f["pnl"], 1e-3):
                    c_bad.append((fam, name, e and e["n"], f["n"]))
        check("c. every strategy, market and price band of the feed's totals is an edge with the feed's n, wins and pnl (the whole-life totals)", not c_bad and len(tot["strategy"]) == 6, c_bad[:3])
        c_bad = []
        for fam, idx in (("market", 1), ("band", 3), ("strategy", 0)):
            for name, f in tot[fam].items():
                e = edges[ke.edge_id(["*"] * idx + [name] + ["*"] * (4 - idx))]
                if e["src"] != "feed":
                    continue
                w = f["wins"] / f["n"]
                if f["p"]:
                    p = f["p"]
                else:
                    staked = f["staked"] or f["n"] * (full["stats"]["staked"] / full["stats"]["trades"])
                    p = w / (1 + f["pnl"] / staked)
                z = (f["wins"] - f["n"] * p) / math.sqrt(f["n"] * p * (1 - p))
                if not (abs(e["p"] - p) < 6e-5 and abs(e["z"] - z) < 2e-3 and abs(e["w"] - w) < 6e-5):
                    c_bad.append((name, e["p"], p, e["z"], z))
        check("c. feed-source edges: the implied probability is the band's mean price or the break-even rate w / (1 + EV), and z follows", not c_bad, c_bad[:3])
        # snapshots: the 7 day window of a total is the change since the snapshot a week ago
        led2 = {"v": 1, "trades": copy.deepcopy(raw[-40:]), "snaps": copy.deepcopy(led["snaps"])}        # a young ledger: 40 bets, the totals are far bigger
        snap_old = copy.deepcopy(led2["snaps"][-1])
        snap_old["t"] = int(now - 8 * 86400)
        snap_old["d"] = ke.et_date(snap_old["t"])
        name = "Late favourite (BTC hourly)"
        n0, w0, p0, s0 = snap_old["strategy"][name]
        snap_old["strategy"][name] = [n0 - 40, w0 - 38, round(p0 - 3.0, 4), s0]
        led2["snaps"] = [snap_old] + led2["snaps"]
        d7 = ke.snap_window(led2, "strategy", name, now, 7)
        check("c. a 7 day window of a total: today minus the snapshot 8 days ago (hand numbers: 40 bets, 38 wins, +$3.00)", d7 == {"n": 40, "wins": 38, "pnl": 3.0, "staked": None} or (d7["n"] == 40 and d7["wins"] == 38 and abs(d7["pnl"] - 3.0) < 1e-9), d7)
        check("c. no snapshot that old yet: no window (None), never a guess", ke.snap_window(led, "strategy", name, now, 7) is None)
        os.makedirs(os.path.join(tmp, "two"), exist_ok=True)
        ke.write_json(os.path.join(tmp, "two", "ledger.json"), led2)
        doc2, _, _ = ke.run(full, os.path.join(tmp, "two"), now=now)
        e2 = next(e for e in doc2["edges"] if e["id"] == f"{name}~*~*~*~*")
        check("c. with that snapshot the feed edge gets a real 7 day window (40 bets) that the status sees", e2["win"]["d7"]["n"] == 40 and e2["recent"] == "7d" and e2["decay"] is not None, e2["win"])
        # the book
        bk = doc["book"]
        w, p = bk["w"], bk["p"]
        check("c. the book: break-even rate w / (1 + EV), its Kelly, the chance of losing half at the average bet and at quarter Kelly equal the mirror",
              abs(p - w / (1 + bk["ev"])) < 6e-5 and close(bk["kelly_book"], m_kelly(w, p), 2e-3) and abs(bk["ruin_now"] - (1.0 if m_kelly(w, p) <= 0 else m_ruin_newton(w, p, bk["stake_frac"]))) < 2e-3
              and (bk["ruin_kelly"] == 0.0 or abs(bk["ruin_kelly"] - m_ruin_newton(w, p, 0.25 * bk["kelly_book"])) < 2e-3), bk)
        check("c. the weather: a feed with a bad day is a storm, a losing week rain, a good week clear, a flat one overcast; a paused bot adds fog",
              weather_cases())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def weather_cases():
    def reg(days, bal=100.0, running=True, status="Running"):
        bk = {"balance": bal, "days": [[f"2026-10-{i + 1:02d}", v] for i, v in enumerate(days)], "pnl7": sum(days[-7:]), "win_days7": sum(1 for v in days[-7:] if v > 0), "days7": len(days[-7:]), "running": running, "status": status}
        return ke.regime_of(bk, 0)
    a = reg([1, 1, 1, 1, 1, 1, -15])["state"] == "storm"
    b = reg([1, -1, -1, -1, 1, -1, -1])["state"] == "rain"
    c = reg([1, 1, 1, -1, 1, 1, 1])["state"] == "clear"
    d = reg([1, -1, 1, -1, 1, -1, 0.5])["state"] == "overcast" or reg([1, -1, 1, -1, 1, -1, 0.5])["state"] == "clear"
    e = reg([1, 1, 1, 1, 1, 1, 1], running=False, status="Paused")["paused"] is True
    return a and b and c and d and e


# ------------------------------------------------------------------------------------------------ d. the learning log
def mini_feed(t0, extra=(), strat="S1", ft=None):
    """A small hand-made feed: strategy S1, Bitcoin, 40 bets at 0.9 with 38 wins (a proven small edge), plus anything in `extra`."""
    trades = []
    for i in range(40):
        win = i not in (5, 20)
        trades.append({"t": t0 - i * 3600, "ticker": f"KXB-{i}", "title": "x", "side": "yes", "action": "buy", "contracts": 10.0, "price": 0.9, "pnl": 0.9 if win else -9.0,
                       "asset": "BTC", "strategy": strat, "category": "Bitcoin"})
    trades += list(extra)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    return {"v": 3, "kind": "kalshi", "name": "Mini", "mode": "live", "status": "Running", "running": True, "t": ft or t0, "balance": 100.0, "today_pnl": 0.0, "week_pnl": 0.0, "total_pnl": 0.0,
            "positions": [], "trades": trades, "days": [["2026-11-01", 1.0], ["2026-11-02", 2.0]], "strategies": [{"name": strat, "trades": len(trades), "wins": wins, "losses": len(trades) - wins, "total_pnl": sum(t["pnl"] for t in trades)}],
            "equity": [], "categories": [], "buckets": [], "calibration": [], "alerts": [], "stats": {"trades": len(trades), "wins": wins, "losses": len(trades) - wins, "staked": 360.0, "pnl": 0.0, "avg_price": 0.9}}


def part_d():
    tmp = tempfile.mkdtemp(prefix="kc_log_")
    try:
        t0 = int(datetime(2026, 11, 2, 21, 0, tzinfo=NY).timestamp())
        feed = mini_feed(t0)
        doc1, e1, n1 = ke.run(feed, tmp, now=t0)
        log1 = open(os.path.join(tmp, "learning_log.json"), "rb").read()
        s1 = next(e for e in doc1["edges"] if e["id"] == "S1~*~*~*~*")
        # by hand: 38 wins of 40 at price 0.9: pnl = 38 x 0.9 - 2 x 9 = +16.2 on 40 x 9 = $360 staked: EV +0.045 per $1
        check("d. by hand: 38 wins of 40 at 0.90, +$0.90 a win and -$9.00 a loss: EV +0.045 per $1, win rate 0.95 against 0.90, 40 bets",
              s1["n"] == 40 and s1["wins"] == 38 and abs(s1["ev"] - 0.045) < 1e-9 and abs(s1["w"] - 0.95) < 1e-9 and abs(s1["p"] - 0.9) < 1e-9 and abs(s1["pnl"] - 16.2) < 1e-9, s1)
        z = (38 - 36.0) / math.sqrt(40 * 0.9 * 0.1)
        lo, hi = m_wilson(38, 40)
        check("d. ...z = (38 - 36) / sqrt(3.6) = 1.054 (not proven), Wilson 0.8318 to 0.9861, so no DO MORE: a KEEP; the first verdict is logged once",
              abs(s1["z"] - z) < 1e-3 and abs(s1["lo"] - lo) < 1e-4 and abs(s1["hi"] - hi) < 1e-4 and s1["advice"] == "keep" and s1["status"] == "HOLDING"
              and sum(1 for x in e1 if x["kind"] == "learned" and x["id"] == "S1~*~*~*~*") == 1, (s1["z"], s1["advice"], s1["status"]))
        doc1b, e1b, n1b = ke.run(feed, tmp, now=t0)
        check("d. a rerun on the same feed learns nothing new: no new bets, no new log lines, the log file is byte for byte the same", n1b == 0 and e1b == [] and open(os.path.join(tmp, "learning_log.json"), "rb").read() == log1)
        # 30 more bets that all lose: the edge dies; the old lines must not change
        extra = [{"t": t0 + 600 + i * 60, "ticker": f"KXL-{i}", "title": "x", "side": "yes", "action": "buy", "contracts": 10.0, "price": 0.9, "pnl": -9.0, "asset": "BTC", "strategy": "S1", "category": "Bitcoin"} for i in range(30)]
        doc2, e2, n2 = ke.run(mini_feed(t0, extra, ft=t0 + 3600), tmp, now=t0 + 3600)
        s2 = next(e for e in doc2["edges"] if e["id"] == "S1~*~*~*~*")
        log2 = ke.read_json(os.path.join(tmp, "learning_log.json"), {})["entries"]
        old = ke.read_json(os.path.join(tmp, "learning_log.json"), {})
        check("d. 30 more losing bets: the edge is DEAD and STOP; the log gains 'Crumbled: S1: HOLDING -> DEAD ... STOP' and exactly one 'Read 30 new bets' line (the same bets also kill the market, price-band and side edges they belong to)",
              n2 == 30 and s2["status"] == "DEAD" and s2["advice"] == "stop" and sum(1 for x in e2 if x["kind"] == "run") == 1 and any(x["text"].startswith("Crumbled: S1: HOLDING -> DEAD") and x["text"].endswith("STOP") for x in e2)
              and any(x["text"].startswith("Read 30 new bets") for x in e2), (s2["status"], [x["text"] for x in e2]))
        first = json.loads(log1.decode("utf-8"))["entries"]
        check("d. append-only: every earlier line is still there, identical, in the same place, with the new lines after them", log2[: len(first)] == first and len(log2) == len(first) + len(e2) and len(e2) >= 2)
        check("d. 'since' moves when the status changes (the building crumbles from this day) and 'first' stays", s2["first"] == s1["first"] and s2["since"] == ke.et_date(t0 + 3600), (s2["first"], s2["since"]))
        m = m_group([t for t in ke.read_json(os.path.join(tmp, "ledger.json"), {})["trades"]], s2["dims"])
        check("d. ...and the dead edge's EV is the brute-force EV (negative, proven by z <= -1.645)", close(s2["ev"], m["ev"], 1e-4) and m["ev"] < 0 and s2["z"] <= -1.6449, (s2["ev"], m["ev"], s2["z"]))
        # honest small samples
        tmp2 = tempfile.mkdtemp(prefix="kc_small_")
        small = mini_feed(t0)
        small["trades"] = small["trades"][:12]
        small["strategies"] = [{"name": "S1", "trades": 12, "wins": 11, "losses": 1, "total_pnl": 1.0}]
        d3, _, _ = ke.run(small, tmp2, now=t0)
        sm = next(e for e in d3["edges"] if e["id"] == "S1~*~*~*~*")
        check("d. honest about small samples: 12 bets is NEW, small, advice COLLECT, no Kelly stake, no ruin number sized, never in the do-more list",
              sm["n"] == 12 and sm["status"] == "NEW" and sm["small"] and sm["advice"] == "collect" and sm["kelly_safe"] == 0 and sm["stake"] == 0 and sm["ruin"] == 0 and sm["id"] not in d3["lists"]["do_more"])
        shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ e. robustness
def part_e():
    tmp = tempfile.mkdtemp(prefix="kc_rob_")
    try:
        t0 = int(datetime(2026, 11, 2, 21, 0, tzinfo=NY).timestamp())
        feed = mini_feed(t0)
        junk = [None, 5, "x", {}, {"t": "abc", "pnl": 1}, {"t": t0, "pnl": 1, "price": 250, "contracts": 1}, {"t": t0, "pnl": 1, "price": 0.5, "contracts": 0}, {"t": t0, "pnl": 1, "price": 0, "contracts": 3},
                {"t": t0, "pnl": 1, "price": 0.5, "contracts": 1, "action": "sell"}, {"t": t0, "pnl": None, "price": 0.5, "contracts": 1}]
        feed["trades"] = feed["trades"] + junk + [copy.deepcopy(feed["trades"][0])]
        feed["strategies"].append({"name": "", "wins": "x"})
        doc, _, new = ke.run(feed, tmp, now=t0)
        check("e. junk rows, sell-backs, a bad price, zero contracts, a duplicate bet: ignored without a throw; 40 bets kept once", new == 40 and doc["ledger"]["n"] == 40, new)
        before = {f: open(os.path.join(tmp, f), "rb").read() for f in ("edges.json", "ledger.json", "learning_log.json", "jarvis.json")}
        rc = ke.main(["--feed", os.path.join(tmp, "nope.json"), "--out", tmp])
        rc2 = ke.main(["--feed", os.path.join(tmp, "ledger.json"), "--out", tmp])
        after = {f: open(os.path.join(tmp, f), "rb").read() for f in before}
        check("e. an unreachable feed (or a file that is not a feed) exits 2 and leaves every file exactly as it was (stale beats invented)", rc == 2 and rc2 == 2 and before == after, (rc, rc2))
        # history: older snapshots in a folder and a git clone add bets the live feed no longer shows
        hist = os.path.join(tmp, "hist")
        os.makedirs(hist)
        older = mini_feed(t0 - 30 * 86400, strat="S1")
        for t in older["trades"]:
            t["ticker"] = "OLD-" + t["ticker"]
        ke.write_json(os.path.join(hist, "old.json"), older)
        doc2, _, new2 = ke.run(feed, tmp, now=t0, history=[hist])
        check("e. history from a folder of older kalshi.json snapshots adds their bets (40 more, deduplicated by ticker, time, side, size, price)", new2 == 40 and doc2["ledger"]["n"] == 80, (new2, doc2["ledger"]["n"]))
        repo = os.path.join(tmp, "repo")
        os.makedirs(repo)
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        subprocess.run(["git", "init", "-q", repo], check=True, env=env)
        for k in (1, 2):
            f = mini_feed(t0 - k * 40 * 86400)
            for t in f["trades"]:
                t["ticker"] = f"G{k}-" + t["ticker"]
            ke.write_json(os.path.join(repo, "kalshi.json"), f)
            subprocess.run(["git", "-C", repo, "add", "kalshi.json"], check=True, env=env)
            subprocess.run(["git", "-C", repo, "commit", "-qm", f"v{k}"], check=True, env=env)
        tmp3 = os.path.join(tmp, "three")
        doc3, _, new3 = ke.run(feed, tmp3, now=t0, history_git=repo)
        check("e. history from every commit of a kalshi-feed clone (2 commits x 40 bets) joins the ledger with the live feed's 40", new3 == 120 and doc3["ledger"]["n"] == 120 and doc3["ledger"]["snaps"] >= 2, (new3, doc3["ledger"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_e2():
    tmp = tempfile.mkdtemp(prefix="kc_csv_")
    try:
        t0 = int(datetime(2026, 11, 2, 21, 0, tzinfo=NY).timestamp())
        rows = ["Time,Ticker,Side,Book,Contracts,Price,PnL"]
        for i in range(60):                                               # 60 bets in two ET hour blocks: the 08-12 block wins, the 20-24 block loses
            day_t = datetime(2026, 10, 20 + i % 10, 9 if i < 30 else 21, 15, tzinfo=NY).astimezone(ZoneInfo("UTC"))
            win = (i % 10 != 0) if i < 30 else (i % 3 == 0)
            rows.append(f"{day_t:%Y-%m-%dT%H:%M:%SZ},KXETHD-26OCT2009-T{i},{'yes' if i % 2 else 'no'},Late favourite (BTC hourly),5,{97 if i % 2 else 0.97},{0.15 if win else -4.85}")
        rows.append(f"2026-10-30T12:00:00Z,KXBTCD-OPEN,yes,Late favourite (BTC hourly),5,0.97,")       # still open: skipped
        rows.append("junk,,,,,,")
        path = os.path.join(tmp, "orders.csv")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
        got = ke.orders_trades(path)
        check("e. the order CSV: 60 filled rows parsed (column names matched loosely, prices in cents or dollars, the open order and the junk row skipped), the coin read from the ticker (KXETHD is Ethereum)",
              len(got) == 60 and all(t["m"] == "Ethereum" and abs(t["p"] - 0.97) < 1e-9 and t["c"] == 5.0 for t in got) and ke.asset_of_ticker("KXBTCD-26NOV0211") == "Bitcoin"
              and ke.asset_of_ticker("KXDOGE15M-X") == "Dogecoin" and ke.asset_of_ticker("KXWEIRD-1") == "Other", (len(got), got[:1]))
        feed = mini_feed(t0)
        doc, _, new = ke.run(feed, tmp, now=t0, orders=[path])
        hours = {e["dims"][2]: e for e in doc["edges"] if e["kind"] == "hour"}
        m_day = m_group(ke.read_json(os.path.join(tmp, "ledger.json"), {})["trades"], ["*", "*", "08-12 ET", "*", "*"])
        check("e. with the export in the ledger the hour-of-day edges exist (08-12 ET and 20-24 ET) and equal a brute-force recount; a rerun adds nothing",
              new == 100 and "08-12 ET" in hours and hours["08-12 ET"]["n"] == m_day["n"] and close(hours["08-12 ET"]["ev"], m_day["ev"], 1e-4)
              and ke.run(feed, tmp, now=t0, orders=[path])[2] == 0, (new, sorted(hours)))
        bad = os.path.join(tmp, "bad.csv")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("a,b\n1,2\n")
        try:
            ke.orders_trades(bad)
            check("e. a CSV without the needed columns is refused", False)
        except ValueError:
            check("e. a CSV without the needed columns is refused", True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ f. the shipped files
def part_f():
    edges = ke.read_json(os.path.join(PAGE, "edges.json"), None)
    led = ke.read_json(os.path.join(PAGE, "ledger.json"), None)
    log = ke.read_json(os.path.join(PAGE, "learning_log.json"), None)
    card = ke.read_json(os.path.join(PAGE, "jarvis.json"), None)
    check("f. the shipped files exist and parse (edges, ledger, learning log, Jarvis card)", all(x is not None for x in (edges, led, log, card)))
    if any(x is None for x in (edges, led, log, card)):
        return
    ids = [e["id"] for e in edges["edges"]]
    check("f. edges.json: unique ids, five dims each, every status one of the five, grey (small) exactly when n < 30, no stake for a grey edge, every list id exists",
          len(ids) == len(set(ids)) and all(len(e["dims"]) == 5 and e["status"] in ("NEW", "GROWING", "HOLDING", "DECAYING", "DEAD") and e["small"] == (e["n"] < 30) for e in edges["edges"])
          and all((not e["small"]) or not e["stake"] for e in edges["edges"]) and all(i in set(ids) for L in edges["lists"].values() for i in L))
    check("f. the ledger holds the bets the edges were made from (n of the all-dims edge equals the bets, pushes aside), and the log is dated and append-only shaped",
          edges["ledger"]["n"] == len(led["trades"]) and all(x.get("d") and x.get("text") and x.get("ek") for x in log["entries"]) and len({x["ek"] for x in log["entries"]}) == len(log["entries"]))
    check("f. the Jarvis card keeps the contract (name, status, 3 kpis, <= 3 lines of <= 120, t, open, theme, < 8 KB, plain text)",
          card["v"] == 1 and card["name"] == "Kalshi City" and card["status"]["level"] in ("ok", "warn", "bad", "off") and len(card["kpis"]) == 3 and len(card["lines"]) <= 3
          and all(len(x) <= 120 for x in card["lines"]) and isinstance(card["t"], int) and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192 and not any(c in json.dumps(card) for c in "<>"))
    with open(os.path.join(ROOT, "research", "kalshi", "edge_tables.json"), encoding="utf-8") as fh:
        tables = json.load(fh)
    learned = ke.read_json(os.path.join(PAGE, "learned.json"), None)
    check("f. learned.json is exactly what tools/kalshicity_learned.py makes from research/kalshi/edge_tables.json (headline, fees, bands, ruin sims, ideas)", learned == kl.build(tables) and learned["headline"] == tables["verdict"]["headline"]
          and learned["fees"]["total"] == tables["fees"]["drag"]["fees_est_total"] and learned["ruin"]["rows"][0]["p_ruin"] == tables["risk"]["sims"]["late_favourite"][0]["p_ruin"] and len(learned["ideas"]) == len(tables["ideas"]))
    fx = ke.read_json(os.path.join(PAGE, "fixture.json"), None)
    mine = kd.build(36)
    check("f. fixture.json is exactly what tools/kalshi_demo.py makes (deterministic, seed 36), marked demo", fx == mine and fx["demo"] is True and fx["edges"]["counts"]["edges"] > 400)
    # rerunning the engine on the shipped feed state in a scratch copy changes nothing but the run line (idempotent on the shipped data)
    tmp = tempfile.mkdtemp(prefix="kc_ship_")
    try:
        for f in ("ledger.json", "edges.json", "learning_log.json"):
            shutil.copy(os.path.join(PAGE, f), os.path.join(tmp, f))
        feed = dict(mini_feed(1), t=edges["t"])
        # a full rerun from the same ledger: rebuild the feed the ledger came from
        rebuilt = {"v": 3, "kind": "kalshi", "t": edges["t"], "trades": [], "balance": edges["book"]["balance"], "running": edges["book"]["running"], "status": edges["book"]["status"],
                   "days": edges["book"]["days"], "stats": {"trades": edges["book"]["bets_total"], "wins": 0, "losses": 0, "staked": 0, "pnl": 0, "avg_price": 0.9}}
        del feed
        check("f. the shipped ledger rebuilds the shipped edges: every ledger-source edge of edges.json equals a brute-force recount from ledger.json",
              all(close(e["n"], m_group(led["trades"], e["dims"])["n"], 0) and close(e["pnl"], m_group(led["trades"], e["dims"])["pnl"], 1e-3)
                  for e in edges["edges"] if e["src"] == "ledger"), None)
        del rebuilt
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ g. the research ideas (tools/kalshi_hypotheses.py): a paper score for each
LOW = ["<20c", "20-40c", "40-60c", "60-80c", "80-90c", "90-95c"]


def m_z(rows):
    """z of a set of (n, wins, p) rows: (wins - sum n p) / sqrt(sum n p (1 - p)), written out, not the engine's z_test."""
    w = sum(r[1] for r in rows)
    mu = sum(r[0] * r[2] for r in rows)
    var = sum(r[0] * r[2] * (1 - r[2]) for r in rows)
    return (w - mu) / math.sqrt(var)


def part_g():
    kh = __import__("tools.kalshi_hypotheses", fromlist=["x"])
    hy = ke.read_json(os.path.join(PAGE, "hypotheses.json"), None)
    edges = ke.read_json(os.path.join(PAGE, "edges.json"), None)
    led = ke.read_json(os.path.join(PAGE, "ledger.json"), None)
    check("g. the shipped hypotheses.json exists, parses, holds the 8 research ideas with their verdicts, a pair in dollars and an append-only dated log", bool(hy) and len(hy["hyps"]) == 8 and hy["pair"]["best"] and hy["pair"]["worst"]
          and all(x.get("d") and x.get("text") and x.get("ek") for x in hy["log"]) and len({x["ek"] for x in hy["log"]}) == len(hy["log"]))
    if not hy:
        return
    by = {h["id"]: h for h in hy["hyps"]}
    snap = led["snaps"][-1]
    pband = {e["dims"][3]: e["p"] for e in edges["edges"] if e["size"] == 1 and e["dims"][3] != "*"}
    pmark = {e["dims"][1]: e["p"] for e in edges["edges"] if e["size"] == 1 and e["dims"][1] != "*"}
    # the 95c floor and the 90-95c leak: recounted from the feed's band totals (n, wins, pnl, staked) by hand
    for hid, names in (("floor95", LOW), ("leak9095", ["90-95c"])):
        rows = [snap["band"][b] for b in names if b in snap["band"]]
        n, wins, pnl = sum(r[0] for r in rows), sum(r[1] for r in rows), sum(r[2] for r in rows)
        z = m_z([(snap["band"][b][0], snap["band"][b][1], pband[b]) for b in names if b in snap["band"]])
        b = by[hid]["back"]
        check(f"g. {hid}: the bets it would skip are {n}, they made ${pnl:.2f}, so the rule adds ${-pnl:.2f} looking back; z {z:.3f} (a hand recount of the feed's price-band totals)",
              b["n_skip"] == n and close(b["pnl_skip"], pnl, 1e-4) and close(b["gain"], -pnl, 1e-4) and abs(b["z"] - z) < 2e-3 and b["n_all"] == edges["book"]["bets_total"], (b, n, pnl, z))
    r = snap["market"]["XRP"]
    zx = m_z([(r[0], r[1], pmark["XRP"])])
    bx = by["xrp"]["back"]
    check("g. xrp: 192 bets it would skip, -$106.63, so +$106.63 looking back; the loss is beyond luck (z <= -1.645) but the rule was picked after seeing it, so the verdict is PROMISING, never WORKS",
          bx["n_skip"] == r[0] and close(bx["gain"], -r[2], 1e-4) and abs(bx["z"] - zx) < 2e-3 and bx["sig"] == "-" and by["xrp"]["word"] == "PROMISING" and not by["xrp"]["judged_live"], (bx, zx))
    # the maker idea: fees = 0.07 x staked x (1 - p) per band (= 0.07 x C x P x (1 - P)); the maker fee is a quarter of it, so 3/4 would be saved
    fees = sum(0.07 * snap["band"][b][3] * (1 - pband[b]) for b in snap["band"])
    with open(os.path.join(ROOT, "research", "kalshi", "edge_tables.json"), encoding="utf-8") as fh:
        tables = json.load(fh)
    bm = by["maker"]["back"]
    check("g. maker orders: the fee bill recounted by hand ($%.2f, the research says $%.2f), a quarter of it would remain, so up to $%.2f could be saved if every resting order filled; the verdict is NEEDS DATA (no bid / ask logged)"
          % (fees, tables["fees"]["drag"]["fees_est_total"], 0.75 * fees),
          abs(bm["fees"] - fees) < 0.01 and abs(bm["saved"] - 0.75 * fees) < 0.01 and abs(fees - tables["fees"]["drag"]["fees_est_total"]) < 0.05 and by["maker"]["word"] == "NEEDS DATA", (bm, fees))
    # the ledger-based ideas, brute force
    trs = led["trades"]
    keep = {}
    for t in trs:
        keep.setdefault(t["k"].split("-")[1], []).append(t)
    skip_w = []
    for g in keep.values():
        if len(g) > 1:
            best = sorted(g, key=lambda t: (-t["p"], t["t"], t["k"]))[0]
            skip_w += [t for t in g if t is not best]
    skip_h = [t for t in trs if datetime.fromtimestamp(t["t"], NY).hour < 8]
    for hid, sk in (("window1", skip_w), ("hours", skip_h)):
        b = by[hid]["back"]
        check(f"g. {hid}: {len(sk)} of the {len(trs)} bets the engine read one by one would be skipped, they made ${sum(t['pnl'] for t in sk):.2f}; fewer than 30, so the verdict is COLLECTING (honest about small samples)",
              b["n_skip"] == len(sk) and close(b["pnl_skip"], sum(t["pnl"] for t in sk), 1e-4) and b["n_all"] == len(trs) and by[hid]["word"] == "COLLECTING", (b, len(sk)))
    # the size idea: same bets, never more than 5% of the bankroll
    bk = edges["book"]
    scale = min(1.0, 0.05 / bk["stake_frac"])
    bs = by["small"]["back"]
    check("g. small bets: scale = 5%% / %.1f%% = %.3f, so %s becomes %s (+$%.2f), the worst day %s becomes %s; the chance of losing half (%.3f) matches an independent root solver"
          % (bk["stake_frac"] * 100, scale, bk["total"], round(bk["total"] * scale, 2), bk["total"] * (scale - 1), bk["worst_day"], round(bk["worst_day"] * scale, 2), bs["ruin_after"]),
          close(bs["scale"], scale, 1e-3) and abs(bs["gain"] - bk["total"] * (scale - 1)) < 0.01 and abs(bs["worst_day_after"] - bk["worst_day"] * scale) < 0.01 and abs(bs["ruin_after"] - m_ruin_newton(bk["w"], bk["p"], 0.05)) < 2e-3, (bs, scale))
    real = [e for e in edges["edges"] if e["size"] == 1 and not e["small"]]
    b0, w0 = max(real, key=lambda e: e["pnl"]), min(real, key=lambda e: e["pnl"])
    check("g. Best edge so far and Worst leak are the biggest winner and loser among the 30+ bet single slices (%s %+.2f, %s %+.2f), the leak points at the idea that plugs it"
          % (hy["pair"]["best"]["label"], b0["pnl"], hy["pair"]["worst"]["label"], w0["pnl"]), hy["pair"]["best"]["id"] == b0["id"] and hy["pair"]["worst"]["id"] == w0["id"] and close(hy["pair"]["best"]["pnl"], b0["pnl"], 1e-4)
          and close(hy["pair"]["worst"]["pnl"], w0["pnl"], 1e-4) and hy["pair"]["worst"]["fix"] == "leak9095")
    # live tracking in a scratch folder: register on one run, then 30 losing 90-95c bets and 3 night bets arrive
    tmp = tempfile.mkdtemp(prefix="kc_hyp_")
    try:
        t0 = int(datetime(2026, 11, 2, 21, 0, tzinfo=NY).timestamp())

        def feed_at(t, extra):
            """mini_feed plus the whole-life totals the bot publishes: every bet is 10 contracts at 0.90 (a $9 stake), 38 wins and the rest losses."""
            f = mini_feed(t0, extra, ft=t)
            n, w = 40 + len(extra), 38
            pnl = round(0.9 * w - 9.0 * (n - w), 2)
            f["buckets"] = [{"lo": 0.9, "hi": 0.95, "trades": n, "wins": w, "losses": n - w, "pnl": pnl, "staked": 9.0 * n}]
            f["calibration"] = [{"p": 0.9, "n": n, "hit": round(w / n, 4)}]
            f["categories"] = [{"name": "Bitcoin", "group": "Crypto", "trades": n, "wins": w, "losses": n - w, "pnl": pnl, "staked": 9.0 * n}]
            f["stats"].update({"trades": n, "wins": w, "losses": n - w, "staked": 9.0 * n, "pnl": pnl})
            return f
        ke.run(feed_at(t0, []), tmp, now=t0)
        h1 = ke.read_json(os.path.join(tmp, "hypotheses.json"), None)
        log1 = open(os.path.join(tmp, "hypotheses.json"), "rb").read()
        b1 = {h["id"]: h for h in h1["hyps"]}
        check("g. the first run registers every idea (today's date, nothing live yet): live skipped bets 0, looking back counts the 40 bets, no WORKS, one 'Started testing' line per idea",
              len(h1["hyps"]) == 8 and all(h["live"]["n_skip"] == 0 for h in h1["hyps"]) and b1["leak9095"]["back"]["n_skip"] == 40 and b1["leak9095"]["reg"]["day"] == ke.et_date(t0) and all(h["word"] != "WORKS" for h in h1["hyps"])
              and sum(1 for x in h1["log"] if x["kind"] == "started") == 8, [(h["id"], h["word"]) for h in h1["hyps"]])
        ke.run(feed_at(t0, []), tmp, now=t0)
        check("g. a rerun on the same feed learns nothing new: the ideas file is byte for byte the same", open(os.path.join(tmp, "hypotheses.json"), "rb").read() == log1)
        extra = [{"t": t0 + 600 + i * 60, "ticker": f"KXL-{i}", "title": "x", "side": "yes", "action": "buy", "contracts": 10.0, "price": 0.9, "pnl": -9.0, "asset": "BTC", "strategy": "S1", "category": "Bitcoin"} for i in range(30)]
        night = int(datetime(2026, 11, 3, 2, 0, tzinfo=NY).timestamp())
        extra += [{"t": night + i * 60, "ticker": f"KXN-{i}", "title": "x", "side": "yes", "action": "buy", "contracts": 10.0, "price": 0.9, "pnl": -9.0, "asset": "BTC", "strategy": "S1", "category": "Bitcoin"} for i in range(3)]
        ke.run(feed_at(t0 + 7200, extra), tmp, now=t0 + 7200)
        h2 = ke.read_json(os.path.join(tmp, "hypotheses.json"), None)
        b2 = {h["id"]: h for h in h2["hyps"]}
        lk = b2["leak9095"]
        check("g. 33 losing 90-95c bets arrive: the leak idea's LIVE window is exactly those 33 (the feed's totals minus the registration snapshot), -$297 for the bets, +$297 for the rule; 30+ live bets that lose beyond luck read WORKS, judged live",
              lk["live"]["n_skip"] == 33 and close(lk["live"]["pnl_skip"], -297.0, 1e-6) and close(lk["live"]["gain"], 297.0, 1e-6) and lk["live"]["sig"] == "-" and lk["word"] == "WORKS" and lk["judged_live"] is True and lk["back"]["n_skip"] == 73, lk["live"])
        check("g. the ledger-based ideas count only bets after the registration: 3 night bets (02:00 ET) are the 'night filter' idea's live window (-$27 for the bets, +$27 for the rule); fewer than 30 is COLLECTING",
              b2["hours"]["live"]["n_skip"] == 3 and close(b2["hours"]["live"]["gain"], 27.0, 1e-6) and b2["hours"]["word"] == "COLLECTING", b2["hours"]["live"])
        check("g. the registration never moves, the history grows one point per day, the log is append-only (the first file's lines are all still there, in order) and gains the verdict change as a plain-words line",
              all(b2[i]["reg"] == b1[i]["reg"] for i in b2) and all(len(b2[i]["hist"]) == 1 for i in b2) and h2["log"][: len(h1["log"])] == h1["log"] and any(x["ek"].startswith("leak9095|word|WORKS") and "paper bets" in x["text"] for x in h2["log"][len(h1["log"]):]), None)
        check("g. junk in, safe out: no ledger, no edges, no bets still gives 8 ideas (COLLECTING / NEEDS DATA), never a crash, and a pair of nothing",
              (lambda d: len(d["hyps"]) == 8 and d["pair"] == {"best": None, "worst": None} and all(h["word"] in ("COLLECTING", "NEEDS DATA", "PROMISING", "SAFER") for h in d["hyps"]))(kh.track({"trades": [], "snaps": []}, [], {}, t0)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    part_a()
    part_bc()
    part_d()
    part_e()
    part_e2()
    part_f()
    part_g()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
