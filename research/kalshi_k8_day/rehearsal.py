"""K8 MONDAY REHEARSAL (day-kalshi 2026-11-20): Monday Nov 23's three sessions through the REAL bot code (engine/kalshi_clock.ClockLoop),
on a fake clock and the test suite's fake Kalshi, with the REAL $55 settings (research/lab/kalshi_clock.json).

The order books are rebuilt from RECORDED PUBLIC Kalshi trades: "if Monday trades like day X", each leg's first 45 s of public trades
on day X (research/kalshi_k8_day/data/tape.jsonl, else research/kalshi_k8_monday/data/tape_fresh.jsonl) is replayed on Monday's
tickers (KXGOLD15M-26NOV230530-30, ...), at the moment the bot reads the book (+20 / +30 / +40 s), and Kalshi's real result of day X
settles it. Every scenario runs twice:
  paper  not armed (what the PC does until the owner types the phrase): the paper ledger, no order;
  live   armed by this script typing the phrase into a TEMP folder with a FAKE key (no network, no real order): the orders it would send.
and in both the bot is RESTARTED at 12:00 ET (a new ClockLoop reading the state from disk, like a PC reboot): the evening must keep the
morning's counters (bets today, $ at risk, the morning bet not sent twice).

    python research/kalshi_k8_day/rehearsal.py            -> research/kalshi_k8_day/rehearsal.json + a plain table
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from engine import kalshi_adapt as KA, kalshi_clock as KC, kalshi_live as KL  # noqa: E402

MONDAY = dt.date(2026, 11, 23)
OUT = os.path.join(HERE, "rehearsal.json")
TAPES = (os.path.join(HERE, "data", "tape.jsonl"), os.path.join(ROOT, "research", "kalshi_k8_monday", "data", "tape_fresh.jsonl"))
REAL = os.path.join(ROOT, "research", "lab", "kalshi_clock.json")


def tape() -> dict:
    out = {}
    for p in reversed(TAPES):                        # the newer file wins on overlap
        out.update(KA.read_tape(p))
    return out


def our_trades(tr, side):
    """[(seconds after the open, price of OUR side, contracts)] of public takers buying our side, in time order."""
    out = []
    for x in tr or []:
        try:
            s, ts, yp, c = float(x[0]), str(x[1]), float(x[2]), float(x[3])
        except (TypeError, ValueError, IndexError):
            continue
        if ts == side and c > 0 and 0 < yp < 1:
            out.append((s, round(yp if side == "yes" else 1 - yp, 4), c))
    return sorted(out)


def book_from_tape(tr, side, t_from, span=5.0):
    """The fake Kalshi's (yes bids, no bids) at t_from s: OUR side's asks = what public takers of our side really paid in the next
    `span` s, each level at least as dear as the one before (the bot cannot buy a cheaper print that only comes later)."""
    lv, top = [], 0.0
    for s, p, c in our_trades(tr, side):
        if t_from <= s <= min(45.0, t_from + span):
            top = max(top, p)
            if lv and abs(lv[-1][0] - top) < 1e-9:
                lv[-1][1] += c
            else:
                lv.append([top, c])
    if not lv:
        return [], []
    other = [(round(max(0.01, lv[0][0] - 0.02), 4), 50.0)]
    if side == "no":                                 # NO is bought from the YES bids: YES bid = 1 - NO ask
        return [(round(1 - p, 4), q) for p, q in lv], [(round(1 - x, 4), q) for x, q in other]
    return [(round(1 - x, 4), q) for x, q in other], [(round(1 - p, 4), q) for p, q in lv]


def source_days(T, cfg, n=5) -> list:
    """The newest weekdays whose 3 live legs are all in the recorded tape (the scenarios)."""
    out, d = [], MONDAY - dt.timedelta(days=1)
    while len(out) < n and d > dt.date(2026, 8, 1):
        if d.weekday() < 5:
            tks = [KC.ticker(KC.LEG[l]["series"], KC.leg_open(KC.LEG[l], d)) for l in cfg["live_legs"] if not KC.skipped(KC.LEG[l], d)]
            if tks and all(t in T for t in tks):
                out.append(d)
        d -= dt.timedelta(days=1)
    return out


def world_cls():
    from tests import test_kalshi_clock as TC, test_kalshi_live as TL   # the fake Kalshi + World (tests import with the $15 fixture)
    return TC, TL


def run_day(src, mode, tmp, T, restart_at_et=(12, 0), cash=55.0, days=None):
    """One Monday (or the days in `days`) replaying the tape of `src` (a date, or a list of dates for `days`) in `mode`.
    -> (world, armed (ok, words), cfg, info)."""
    TC, TL = world_cls()
    KC.CFG_PATH = KL.CLOCK_PATH = REAL
    cfg = KC.load_config(REAL)[0]
    w = TC.World(tmp, f"{mode}-{src if not isinstance(src, list) else 'wk'}", cash=cash)
    f = w.fake
    days = days or [MONDAY]
    srcs = src if isinstance(src, list) else [src] * len(days)
    w.clock.t = KC.london_epoch(days[0], 10, 14)
    armed = w.arm() if mode == "live" else (False, "paper")
    loop = w.loop()
    info = {"restarts": 0, "views": []}
    for d, sd in zip(days, srcs):
        restart_t = KC.et_epoch(d, *restart_at_et)
        for open_t, ids in KC.windows(d, cfg):
            if restart_t and w.clock.t < restart_t <= open_t:
                w.run_until(loop, restart_t)
                before = loop.live_view(loop.now())
                loop = w.loop()                       # THE RESTART: a new loop object, state read back from disk
                after = loop.live_view(loop.now())
                info["restarts"] += 1
                info["views"].append({k: (before[k], after[k]) for k in ("bets_today", "day_worst", "week_worst", "open_all", "dd_now")}
                                     | {"tickers_same": before["tickers_today"] == after["tickers_today"], "done_same": True})
            recs = {}
            for lid in ids:
                leg = KC.LEG[lid]
                tk = KC.ticker(leg["series"], open_t)
                src_tk = KC.ticker(leg["series"], KC.leg_open(leg, sd))
                rec = T.get(src_tk)
                f.markets[tk] = {"ticker": tk, "event_ticker": tk.rsplit("-", 1)[0], "status": "active", "result": "",
                                 "close_time": TL.iso(open_t + 900), "yes_sub_title": "Target", "price_ranges": []}
                recs[lid] = (tk, rec, src_tk)
                f.books[tk] = book_from_tape(rec["tr"], leg["side"], 20.0) if rec else ([], [])
            w.clock.t = max(w.clock.t, open_t - 30)
            for k in (20, 30, 40, 50):
                w.run_until(loop, open_t + k - 0.5)
                for lid, (tk, rec, _) in recs.items():
                    if rec:
                        f.books[tk] = book_from_tape(rec["tr"], KC.LEG[lid]["side"], float(k))
            w.run_until(loop, open_t + 60)
            for lid, (tk, rec, _) in recs.items():
                if rec and f.markets[tk]["status"] == "active":
                    f.settle(tk, rec["res"])
            w.run_until(loop, open_t + 17 * 60)
        w.run_until(loop, KC.et_epoch(d, 17, 10))     # the day's summary push (17:05 ET)
    info["loop"] = loop
    return w, armed, cfg, info


def summarize(w, mode, cfg, armed, info, src):
    rs = w.paper() if mode == "paper" else w.live()
    posts = [c[3] for c in w.posts()] if mode == "live" else []
    bets = [{"leg": r["leg"], "ticker": r["ticker"], "side": r["side"], "status": r.get("status"), "why": r.get("why"), "n": r.get("n"),
             "price": r.get("price"), "cost": r.get("cost"), "fee": r.get("fee"), "result": r.get("result"), "pnl": r.get("pnl")} for r in rs]
    done = [b for b in bets if b["result"] in ("won", "lost")]
    return {"source_day": str(src), "mode": mode, "armed": bool(armed[0]), "bets": bets,
            "orders": [{k: b.get(k) for k in ("ticker", "side", "count", "price", "expiration_time", "client_order_id")} for b in posts if b],
            "won": sum(1 for b in done if b["result"] == "won"), "settled": len(done), "net": round(sum(b["pnl"] or 0 for b in done), 2),
            "restart": [{k: v for k, v in x.items()} for x in info["views"]],
            "pushes": [{"title": p.get("title"), "body": p.get("body")} for p in w.pushes]}


def main(n=5) -> int:
    T = tape()
    KC.CFG_PATH = KL.CLOCK_PATH = REAL
    cfg = KC.load_config(REAL)[0]
    days = source_days(T, cfg, n)
    tmp = tempfile.mkdtemp(prefix="k8reh-")
    out = {"monday": str(MONDAY), "settings": "research/lab/kalshi_clock.json ($55 rule)", "tickers": {}, "scenarios": []}
    for open_t, ids in KC.windows(MONDAY, cfg):
        for lid in ids:
            out["tickers"][lid] = KC.ticker(KC.LEG[lid]["series"], open_t)
    for d in days:
        for mode in ("paper", "live"):
            w, armed, cfg, info = run_day(d, mode, tmp, T)
            out["scenarios"].append(summarize(w, mode, cfg, armed, info, d))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    print("Monday", MONDAY, "tickers:", ", ".join(sorted(set(out["tickers"].values()))))
    for s in out["scenarios"]:
        legs = "; ".join(f"{b['leg']}: {b['n']} at {round(100 * b['price']) if b['price'] else '-'}c {b['result'] or b['status']} "
                         f"{'' if b['pnl'] is None else ('+' if b['pnl'] >= 0 else '') + format(b['pnl'], '.2f')}" for b in s["bets"])
        print(f"like {s['source_day']} {s['mode']:5}: {s['won']}/{s['settled']} won, ${s['net']:+.2f}, {len(s['orders'])} orders | {legs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
