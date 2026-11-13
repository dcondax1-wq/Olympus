"""Kalshi risk guard (tools/kalshi_kit/public/kalshi_guard.py, team K2 2026-11-13): the gate every order of the owner's
Kalshi bot passes on its VM. No network, no keys, temp folders only. Checks:
  a. the fee: 0.07 * P * (1 - P) per contract rounded UP to the cent (exact against fractions, every price 1-99, other rates)
  b. every risk check on its own (a good order passes; one change trips exactly the check it should)
  c. sells: only what is held, never stopped by the daily stop; the kill switch stops everything
  d. the mode switch: paper by default, live only with today's phrase, and back to paper on a limits change, an update,
     the kill switch, an expired --hours, a broken file
  e. the Guard on files: init, paper / dry-run logging, live arming, booking, fills, settlements, caps, the ET day roll,
     trades.db merged (read-only), orders around the guard found, fail closed, several processes at once
  f. the command line: 'live' without a terminal or the phrase is refused; with it, armed; kill / unkill; limits --set
  g. phone alerts: fills, losses, kill switch, daily stop, mode changes, orders around the guard; first round silent,
     each alert once, a failed post retried
  h. no network: the checks run with sockets switched off
    python -X utf8 -m tests.test_kalshi_guard
"""
from __future__ import annotations

import importlib.util
import json
import math
import multiprocessing as mp
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD_FILE = os.path.join(ROOT, "tools", "kalshi_kit", "public", "kalshi_guard.py")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def load():
    spec = importlib.util.spec_from_file_location("kalshi_guard_t", GUARD_FILE)
    m = importlib.util.module_from_spec(spec)
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(m)
    finally:
        sys.dont_write_bytecode = old
    return m


G = load()
NOW = 1_794_600_000.0          # 2026-11-14 (Saturday) about 13:20 ET
GOOD = {"ticker": "KXBTCD-26NOV1417-T99500", "side": "yes", "action": "buy", "count": 5, "price_cents": 40, "fair": 0.5,
        "close_ts": NOW + 3600, "strategy": "main"}


def codes(d):
    return sorted(r["code"] for r in d["reasons"])


def part_a():
    bad = []
    for p in range(1, 100):
        want = math.ceil(Fraction(7, 100) * Fraction(p, 100) * Fraction(100 - p, 100) * 100)
        if G.fee_cents(p) != want:
            bad.append((p, G.fee_cents(p), want))
    check("a. fee per contract = ceil(0.07 * P * (1-P)) cents for every price 1-99 (exact)", not bad, bad)
    check("a. known values: 50c -> 2c, 1c / 99c -> 1c, 90c -> 1c, 30c -> 2c", (G.fee_cents(50), G.fee_cents(1), G.fee_cents(99),
          G.fee_cents(90), G.fee_cents(30)) == (2, 1, 1, 1, 2))
    bad = [p for p in range(1, 100) if G.fee_cents(p, 0.035) != math.ceil(Fraction(35, 1000) * Fraction(p * (100 - p), 10000) * 100)]
    check("a. another rate (0.035) is exact too", not bad, bad)
    check("a. order fee = per-contract fee x contracts (never below Kalshi's per-order rounding)",
          G.order_fee_cents(50, 10) == 20 and all(G.order_fee_cents(p, n) >= math.ceil(Fraction(7, 100) * n * Fraction(p * (100 - p), 10000) * 100)
                                                  for p in range(1, 100) for n in (1, 3, 7, 25)))
    check("a. price 0 / 100 -> no fee (not a valid price anyway)", G.fee_cents(0) == 0 and G.fee_cents(100) == 0)
    check("a. EV after fee: fair 0.5 at 40c = 50 - 40 - 2 = +8c", G.ev_cents(0.5, 40) == 8.0)


def part_b():
    lim = dict(G.DEFAULT_LIMITS)
    b = G.empty_book(G.et_day(NOW))
    d = G.check_order(GOOD, lim, b, "live", NOW, balance=100)
    check("b. a good order passes every check and may be sent in live", d["ok"] and d["send"] and d["reasons"] == [], d)
    check("b. its cost = 5 x 40c + 5 x 2c fee = $2.10, EV +8c", d["cost_usd"] == 2.1 and d["fee_usd"] == 0.1 and d["ev_cents"] == 8.0, d)
    check("b. the same order in paper / dry run passes but is never sent",
          all(G.check_order(GOOD, lim, b, m, NOW)["ok"] and not G.check_order(GOOD, lim, b, m, NOW)["send"] for m in ("paper", "dry_run")))

    def trips(name, order=None, want=(), book=None, limits=None, balance=100, now=NOW):
        dd = G.check_order(order or GOOD, {**lim, **(limits or {})}, book or b, "live", now, balance=balance)
        check(f"b. {name} -> {', '.join(want)}", codes(dd) == sorted(want) and not dd["send"], codes(dd))

    trips("max $ per order ($5)", {**GOOD, "count": 12}, ["ORDER_USD"])
    trips("max share of the balance (10% of $20)", {**GOOD, "count": 5}, ["ORDER_PCT"], balance=20)
    trips("more than the balance", {**GOOD, "count": 5}, ["BALANCE"], balance=2)
    bk = G.empty_book(G.et_day(NOW))
    G.book_order(bk, dict(GOOD, _rate=0.07), 9.0, "x1", NOW)
    trips("max $ in one market ($10, $9 already)", GOOD, ["MARKET_USD"], book=bk)
    bk2 = {**G.empty_book(G.et_day(NOW)), "spend_usd": 24.0}
    trips("max $ per day ($25, $24 spent)", GOOD, ["DAY_USD"], book=bk2)
    trips("daily stop-loss hit (-$10)", GOOD, ["DAY_STOP"], book={**G.empty_book(G.et_day(NOW)), "pnl_usd": -10.0})
    trips("an order that could lose more than the day's room ($1 left)", GOOD, ["STOP_ROOM"], book={**G.empty_book(G.et_day(NOW)), "pnl_usd": -9.0})
    big = G.empty_book(G.et_day(NOW))
    for i in range(3):
        G.book_order(big, dict(GOOD, ticker=f"KXOTHER-{i}", _rate=0.07), 8.0, f"y{i}", NOW)
    big["spend_usd"] = 0.0                                   # bought on an earlier day: open, not today's spend
    trips("max $ open in total ($25, $24 open)", GOOD, ["OPEN_USD"], book=big)
    trips("max orders per day", GOOD, ["ORDERS_DAY"], book={**G.empty_book(G.et_day(NOW)), "sent": 40})
    trips("max contracts", {**GOOD, "count": 300, "price_cents": 1, "fair": 0.05}, ["CONTRACTS"], limits={"max_order_usd": 1000, "max_market_usd": 1000,
          "max_day_usd": 1000, "max_open_usd": 1000, "daily_stop_usd": 1000, "max_order_pct_balance": 1.0}, balance=10000)
    trips("last 60 s before the close", {**GOOD, "close_ts": NOW + 30}, ["CLOSE_WINDOW"])
    dd = G.check_order({**GOOD, "close_ts": NOW + 30, "strategy": "latefav"}, {**lim, "late_ok_strategies": ["latefav"]}, b, "live", NOW)
    check("b. ... unless the strategy is listed in late_ok_strategies", dd["send"], codes(dd))
    trips("never in the last 5 s, listed or not", {**GOOD, "close_ts": NOW + 3, "strategy": "latefav"}, ["CLOSE_WINDOW"],
          limits={"late_ok_strategies": ["latefav"]})
    trips("a market that already closed", {**GOOD, "close_ts": NOW - 1}, ["CLOSED"])
    trips("close time unknown", {k: v for k, v in GOOD.items() if k != "close_ts"}, ["CLOSE_UNKNOWN"])
    trips("no fair value", {k: v for k, v in GOOD.items() if k != "fair"}, ["NO_FAIR"])
    trips("price above fair + 0 (fair 39c, price 40c)", {**GOOD, "fair": 0.39}, ["EV", "OVER_FAIR"])
    trips("under fair but no edge after the fee (fair 41c at 40c: +1 - 2 = -1c)", {**GOOD, "fair": 0.41}, ["EV"])
    dd = G.check_order({**GOOD, "fair": 0.43}, lim, b, "live", NOW)
    check("b. fair 43c at 40c: +3 - 2 = +1c, exactly the 1c minimum edge -> passes", dd["send"] and dd["ev_cents"] == 1.0, dd)
    trips("price outside min/max price", {**GOOD, "price_cents": 96, "fair": 0.99}, ["PRICE_RANGE"], limits={"max_price_cents": 95})
    trips("a stale quote (90 s old)", {**GOOD, "quote_ts": NOW - 90}, ["QUOTE_STALE"])
    for bad_o, why in (({**GOOD, "side": "maybe"}, "side"), ({**GOOD, "count": 0}, "count 0"), ({**GOOD, "count": 2.5}, "count 2.5"),
                       ({**GOOD, "price_cents": 0}, "price 0"), ({**GOOD, "price_cents": 100}, "price 100"), ({**GOOD, "ticker": "a b"}, "ticker"),
                       ({**GOOD, "fair": 1.5}, "fair 1.5"), ({**GOOD, "action": "short"}, "action"), ("junk", "not a dict")):
        dd = G.check_order(bad_o, lim, b, "live", NOW)
        if not (codes(dd) == ["BAD_ORDER"] and not dd["send"]):
            check(f"b. a bad order is refused ({why})", False, codes(dd))
            break
    else:
        check("b. bad orders (side, count, price, ticker, fair, action, junk) are refused, never sent", True)
    dd = G.check_order({**GOOD, "price": 0.4, "price_cents": None}, lim, b, "live", NOW)
    check("b. a price in dollars (0.40) reads as 40c", dd["send"] and dd["order"]["price_cents"] == 40, dd)


def part_c():
    lim = dict(G.DEFAULT_LIMITS)
    b = G.empty_book(G.et_day(NOW))
    G.book_order(b, dict(GOOD, _rate=0.07), 2.1, "z", NOW)
    sell = {**GOOD, "action": "sell", "count": 5, "price_cents": 60, "fair": 0.55}
    d = G.check_order(sell, lim, b, "live", NOW)
    check("c. selling what is held passes", d["send"], codes(d))
    d = G.check_order({**sell, "count": 6}, lim, b, "live", NOW)
    check("c. selling more than held -> NOT_HELD", codes(d) == ["NOT_HELD"])
    stopped = {**b, "pnl_usd": -50.0, "spend_usd": 999.0, "sent": 999}
    d = G.check_order(sell, lim, stopped, "live", NOW)
    check("c. an exit is never blocked by the daily stop, the day cap or the order count", d["send"], codes(d))
    d = G.check_order({**sell, "price_cents": 40}, lim, b, "live", NOW)
    check("c. never sell below fair (55c) - x", codes(d) == ["OVER_FAIR"], codes(d))
    d = G.check_order(sell, lim, b, "live", NOW, kill=True)
    check("c. the kill switch blocks every order, exits included", "KILL" in codes(d) and not d["send"])
    G.book_order(b, dict(sell, _rate=0.07), 0, "s1", NOW)
    check("c. a booked sell closes the position and books its P&L (5 x 60c - 10c fee - $2.10 basis = +$0.80)",
          G.held(b, GOOD["ticker"], "yes") == 0 and abs(b["pnl_usd"] - 0.8) < 1e-9, b)


def part_d():
    lim = dict(G.DEFAULT_LIMITS)
    day = G.et_day(NOW)
    rec = {"mode": "live", "t": int(NOW), "day": day, "phrase": G.phrase_for(day, 10), "limits_sha": G.limits_sha(lim),
           "guard_version": G.GUARD_VERSION, "until": None}
    check("d. the phrase: GO LIVE <ET day> STOP <daily stop>", G.phrase_for("2026-11-14", 10) == "GO LIVE 2026-11-14 STOP 10"
          and G.phrase_for("2026-11-14", 12.5) == "GO LIVE 2026-11-14 STOP 12.50")
    check("d. no switch file / junk / unknown mode -> paper", all(G.resolve_mode(r, lim, False, NOW)[0] == "paper"
                                                               for r in (None, "x", [], {"mode": "LIVE!"}, {})))
    check("d. paper and dry_run as set", G.resolve_mode({"mode": "paper"}, lim, False, NOW)[0] == "paper"
          and G.resolve_mode({"mode": "dry_run"}, lim, False, NOW)[0] == "dry_run")
    check("d. live with today's phrase, these limits and this guard -> live", G.resolve_mode(rec, lim, False, NOW)[0] == "live")
    check("d. live but the kill switch is on -> paper", G.resolve_mode(rec, lim, True, NOW) [0] == "paper")
    m = G.resolve_mode(rec, {**lim, "max_order_usd": 50.0}, False, NOW)
    check("d. live but the limits changed since -> paper, says why", m[0] == "paper" and "limits changed" in m[1], m)
    check("d. live armed by an older guard -> paper", G.resolve_mode({**rec, "guard_version": "old"}, lim, False, NOW)[0] == "paper")
    check("d. live without the phrase -> paper", G.resolve_mode({**rec, "phrase": "yes"}, lim, False, NOW)[0] == "paper"
          and G.resolve_mode({k: v for k, v in rec.items() if k != "phrase"}, lim, False, NOW)[0] == "paper")
    check("d. live with --hours that ran out -> paper", G.resolve_mode({**rec, "until": NOW - 1}, lim, False, NOW)[0] == "paper"
          and G.resolve_mode({**rec, "until": NOW + 60}, lim, False, NOW)[0] == "live")
    lim2, probs = G.load_limits({"max_order_usd": "abc", "daily_stop_usd": -5, "max_day_usd": 99999999, "nope": 1,
                                 "require_fair": "maybe", "late_ok_strategies": "LateFav, gold"})
    check("d. limits: bad values keep the default and are reported; unknown keys ignored; lists from text",
          lim2["max_order_usd"] == 5.0 and lim2["daily_stop_usd"] == 10.0 and lim2["max_day_usd"] == 25.0 and "nope" not in lim2
          and lim2["require_fair"] is True and lim2["late_ok_strategies"] == ["gold", "latefav"] and len(probs) == 4, (lim2, probs))
    check("d. limits.json that is not an object -> defaults, reported", G.load_limits([1, 2])[0] == G.DEFAULT_LIMITS and G.load_limits([1])[1])


def make_db(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE orders (ts REAL, ticker TEXT, side TEXT, book TEXT, filled INTEGER, avg_price REAL, pnl REAL, "
                "result TEXT, close_ts REAL, asset TEXT, mode TEXT)")
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()


def _proc(home, n, q):
    g = load().Guard(home, bot_dir="")
    out = 0
    for i in range(n):
        d = g.check({**GOOD, "ticker": f"KXP-{os.getpid()}-{i}", "count": 1, "price_cents": 10, "fair": 0.2}, now=NOW)
        out += 1 if d["send"] else 0
    q.put(out)


def part_e(tmp):
    home = os.path.join(tmp, "guard")
    g = G.Guard(home, bot_dir="", clock=lambda: NOW).init()
    lim, _ = g.limits()
    check("e. init: limits.json with the defaults, paper, folder private",
          lim == G.DEFAULT_LIMITS and g.mode()[0] == "paper" and oct(os.stat(home).st_mode & 0o777) == "0o700")
    d = g.check(GOOD, balance=100)
    log = [json.loads(x) for x in open(os.path.join(home, "orders.jsonl"))]
    check("e. paper: the order passes the checks, is NOT sent, and is logged", d["ok"] and not d["send"] and d["mode"] == "paper"
          and len(log) == 1 and log[0]["ticker"] == GOOD["ticker"] and log[0]["send"] is False, (d, log))
    ok, msg = g.set_mode("dry_run")
    d = g.check({**GOOD, "count": 2})
    log = [json.loads(x) for x in open(os.path.join(home, "orders.jsonl"))]
    check("e. dry run: logs the exact intended order (ticker, side, count, price, cost, fee, EV), not sent",
          ok and not d["send"] and d["mode"] == "dry_run" and log[-1]["order"]["count"] == 2 and log[-1]["cost"] == 0.84
          and log[-1]["mode"] == "dry_run", log[-1])
    st = json.load(open(os.path.join(home, "state.json")))
    check("e. paper / dry-run orders are booked in their own paper book, never the live one",
          st["paper"]["sent"] == 2 and "live" not in st, st.keys())
    ok, msg = g.set_mode("live", phrase="go live")
    check("e. live with a wrong phrase is refused and says the exact phrase", not ok and G.phrase_for(G.et_day(NOW), 10) in msg
          and g.mode()[0] == "dry_run", msg)
    ok, msg = g.set_mode("live", phrase="  go live " + G.et_day(NOW) + "  stop 10 ")
    check("e. live with today's phrase (any case / spaces) -> LIVE", ok and g.mode()[0] == "live", msg)
    d = g.check(GOOD, balance=100)
    check("e. live: a good order may be sent; it is booked at once (spend $2.10, $2.10 open in the market)",
          d["send"] and json.load(open(os.path.join(home, "state.json")))["live"]["spend_usd"] == 2.1, d)
    g.record_fill(d["id"], 3, 40)
    st = json.load(open(os.path.join(home, "state.json")))
    check("e. record_fill: 3 of 5 filled -> spend and exposure $1.26", abs(st["live"]["spend_usd"] - 1.26) < 1e-9
          and st["live"]["open"][GOOD["ticker"]]["yes"]["n"] == 3, st["live"])
    sends = sum(g.check({**GOOD, "ticker": f"KXM-{i}"}, balance=100)["send"] for i in range(20))
    check("e. the day cap ($25) stops buys after enough orders (each $2.10)", sends == 11, sends)
    g.record_settle("KXM-0", -9.5)
    d = g.check({**GOOD, "ticker": "KXNEW", "count": 1}, balance=100)
    check("e. a settled loss counts toward the daily stop: -$9.50 leaves $0.50, a $0.42 buy ... ", "DAY_STOP" not in codes(d))
    g.record_settle("KXM-1", -1.0)
    d = g.check({**GOOD, "ticker": "KXNEW2", "count": 1}, balance=100)
    check("e. ... then -$10.50: DAY_STOP, nothing sent", "DAY_STOP" in codes(d) and not d["send"], codes(d))
    pub = g.public()
    check("e. public(): live, stopped, room 0, today's numbers, last block, intended orders, no phrase while live",
          pub["mode"] == "live" and pub["stopped"] and pub["room"]["stop"] == 0 and pub["today"]["blocked"] >= 1
          and pub["last_block"]["text"] and pub["intended"] and pub["go_live"] is None and pub["connected"], pub)
    g2 = G.Guard(home, bot_dir="", clock=lambda: NOW + 86400)
    d = g2.check({**GOOD, "ticker": "KXDAY2", "close_ts": NOW + 86400 + 3600}, balance=100)
    check("e. the next ET day: spend, P&L and orders reset; open positions that closed went", d["send"]
          and g2.public()["today"]["spend"] == 2.1, (codes(d), g2.public()["today"]))
    ok, msg = g.set_limits({"max_order_usd": "7"})
    check("e. a limits change drops LIVE back to paper and says so", ok and g.mode()[0] == "paper" and "phrase again" in msg, (msg, g.mode()))
    ok, msg = g.set_limits({"max_order_usd": "7000"})
    check("e. an out-of-range limit is refused, nothing saved", not ok and g.limits()[0]["max_order_usd"] == 7.0, msg)
    g.set_mode("live", phrase=G.phrase_for(G.et_day(NOW), 10))
    g.kill("testing")
    check("e. kill: every order blocked, live disarmed (mode.json back to paper)", "KILL" in codes(g.check(GOOD))
          and json.load(open(os.path.join(home, "mode.json")))["mode"] == "paper")
    ok, msg = g.set_mode("live", phrase=G.phrase_for(G.et_day(NOW), 10))
    check("e. live cannot be armed while the kill switch is on", not ok and "kill" in msg, msg)
    g.unkill()
    check("e. unkill: the switch goes, the bot stays paper", not g.kill_on() and g.mode()[0] == "paper")
    # trades.db merged, read-only
    bot = os.path.join(tmp, "bot")
    os.makedirs(bot)
    t0 = G.et_midnight(G.et_day(NOW))
    make_db(os.path.join(bot, "trades.db"), [
        (t0 + 100, "KXDB-A", "yes", "main", 10, 0.9, -9.0, "no", t0 + 200, "BTC", "live"),
        (NOW - 60, "KXDB-B", "yes", "main", 10, 0.8, None, None, NOW + 3600, "BTC", "live"),
        (NOW - 60, "KXDB-P", "yes", "main", 10, 0.8, None, None, NOW + 3600, "BTC", "paper")])
    os.chmod(os.path.join(bot, "trades.db"), 0o444)
    h3 = os.path.join(tmp, "guard3")
    g3 = G.Guard(h3, bot_dir=bot, clock=lambda: NOW).init()
    g3.set_mode("live", phrase=G.phrase_for(G.et_day(NOW), 10))
    d = g3.check({**GOOD, "ticker": "KXDB-B", "count": 5}, balance=100)
    st3 = G.merge_books(G.empty_book(G.et_day(NOW)), g3._db_book(NOW))
    check("e. trades.db (read-only) counts: today's $17 spend, -$9 P&L, $8 open in KXDB-B; paper rows ignored",
          sorted(codes(d)) == ["MARKET_USD", "STOP_ROOM"] and abs(st3["spend_usd"] - 17) < 1e-9 and st3["pnl_usd"] == -9.0
          and list(st3["open"]) == ["KXDB-B"], (codes(d), st3))
    pub = g3.public()
    check("e. real orders from before the guard was installed are not flagged", pub["unguarded"] == 0)
    g4 = G.Guard(os.path.join(tmp, "guard4"), bot_dir=bot, clock=lambda: NOW - 7200).init()
    check("e. ... a guard installed 2 h ago: the 1 real order after that it never approved is flagged", g4.public(now=NOW)["unguarded"] == 1,
          g4.public(now=NOW)["unguarded"])
    check("e. sells use what trades.db says is held", g3.check({**GOOD, "ticker": "KXDB-B", "action": "sell", "count": 10, "price_cents": 85,
                                                                 "fair": 0.85})["send"])
    # fail closed
    h5 = os.path.join(tmp, "guard5")
    g5 = G.Guard(h5, bot_dir="", clock=lambda: NOW).init()
    open(os.path.join(h5, "state.json"), "w").write("{not json")
    open(os.path.join(h5, "mode.json"), "w").write("{not json")
    d = g5.check(GOOD)
    check("e. a broken state / switch file: paper, the order still checked, never sent", d["mode"] == "paper" and not d["send"] and d["ok"], d)
    g5.set_mode("live", phrase=G.phrase_for(G.et_day(NOW), 10))
    real_atomic = G._atomic

    def broken(*a, **k):
        raise OSError("disk full")

    G._atomic = broken
    try:
        d = g5.check(GOOD)
    finally:
        G._atomic = real_atomic
    check("e. a guard that cannot write its state blocks the order even in live (GUARD_ERROR, fail closed)",
          codes(d) == ["GUARD_ERROR"] and not d["send"] and g5.mode()[0] == "live", d)
    # several processes at once: the lock keeps the order cap exact
    h6 = os.path.join(tmp, "guard6")
    g6 = G.Guard(h6, bot_dir="", clock=lambda: NOW).init()
    g6.set_limits({"max_orders_day": "25", "max_day_usd": "1000", "max_open_usd": "1000", "daily_stop_usd": "1000"})
    g6.set_mode("live", phrase=G.phrase_for(G.et_day(NOW), 1000))
    q = mp.get_context("fork").Queue()
    ps = [mp.get_context("fork").Process(target=_proc, args=(h6, 15, q)) for _ in range(4)]
    for p in ps:
        p.start()
    for p in ps:
        p.join(60)
    total = sum(q.get(timeout=5) for _ in ps)
    check("e. 4 processes x 15 orders at once: exactly the cap of 25 sent (the state lock)", total == 25, total)


def part_e2(tmp):
    g = G.Guard(os.path.join(tmp, "gs"), bot_dir="", clock=lambda: NOW).init()
    calls = []

    def send():
        calls.append(1)
        return {"order": {"order_id": "o1", "fill_count": 2, "status": "executed"}}

    d, r = G.guarded_send(GOOD, send, balance=100, guard=g)
    check("e2. guarded_send in paper: send() is never called", not calls and r is None and not d["send"])
    g.set_mode("dry_run")
    d, r = G.guarded_send(GOOD, send, balance=100, guard=g)
    check("e2. guarded_send in dry run: send() is never called, the order is logged", not calls and r is None
          and json.loads(open(os.path.join(g.home, "orders.jsonl")).readlines()[-1])["mode"] == "dry_run")
    g.set_mode("live", phrase=G.phrase_for(G.et_day(NOW), 10))
    d, r = G.guarded_send({**GOOD, "count": 50}, send, balance=100, guard=g)
    check("e2. guarded_send in live, a blocked order: send() is never called", not calls and r is None and "ORDER_USD" in codes(d))
    d, r = G.guarded_send(GOOD, send, balance=100, guard=g)
    st = json.load(open(os.path.join(g.home, "state.json")))
    check("e2. guarded_send in live, a good order: send() once, the answer's fill_count (2 of 5) booked",
          calls == [1] and r["order"]["order_id"] == "o1" and st["live"]["open"][GOOD["ticker"]]["yes"]["n"] == 2, st["live"])


def part_f(tmp):
    home = os.path.join(tmp, "cli")
    env = {**os.environ, "KALSHI_GUARD_HOME": home}

    def run(*a, inp=None):
        return subprocess.run([sys.executable, "-I", GUARD_FILE, "--bot-dir", "", *a], capture_output=True, text=True, env=env,
                              input=inp, timeout=60)

    r = run("init")
    check("f. init prints the card: paper, the limits, the phrase to go live", r.returncode == 0 and "mode: PAPER" in r.stdout
          and "GO LIVE" in r.stdout, r.stdout + r.stderr)
    r = run("live", inp="GO LIVE whatever\n")
    check("f. 'live' without a terminal and without --phrase is refused (no piping the phrase in)", r.returncode == 1
          and "not armed" in r.stdout and json.load(open(os.path.join(home, "mode.json")))["mode"] == "paper", r.stdout)
    import time as _t
    phrase = G.phrase_for(G.et_day(_t.time()), 10)
    r = run("live", "--phrase", "GO LIVE 2020-01-01 STOP 10")
    check("f. an old day's phrase is refused", r.returncode == 1 and json.load(open(os.path.join(home, "mode.json")))["mode"] == "paper")
    r = run("live", "--phrase", phrase, "--hours", "48")
    m = json.load(open(os.path.join(home, "mode.json")))
    check("f. 'live --phrase <today's phrase> --hours 48' arms it (recorded: not a terminal, an end time)",
          r.returncode == 0 and "LIVE" in r.stdout and m["mode"] == "live" and m["tty"] is False and m["until"], r.stdout)
    r = run("check", "--order", json.dumps({**GOOD, "close_ts": _t.time() + 3600}))
    out = json.loads(r.stdout)
    check("f. 'check' shows the decision (manual: nothing booked)", out["ok"] and out["send"] and out["mode"] == "live", out)
    r = run("limits", "--set", "max_order_usd=3")
    check("f. 'limits --set' saves and says live is off until the phrase again", r.returncode == 0 and "phrase again" in r.stdout
          and run("status").stdout.startswith("mode: PAPER"), r.stdout)
    r = run("limits", "--set", "nope=1")
    check("f. 'limits --set' with an unknown key is refused", r.returncode == 1 and "unknown setting" in r.stdout)
    r = run("kill", "going", "out")
    check("f. kill / unkill", r.returncode == 0 and "KILL SWITCH ON" in r.stdout and "kill switch: ON" in run("status").stdout
          and "still paper" in run("unkill").stdout)
    r = run("dry-run")
    check("f. dry-run needs no phrase", r.returncode == 0 and "mode: DRY RUN" in run("status").stdout)
    r = run("selftest")
    check("f. selftest OK", r.returncode == 0 and "OK" in r.stdout, r.stdout)
    pub = json.loads(run("public").stdout)
    check("f. 'public' prints the risk block (no phrase or file paths in it beyond the GO LIVE line)",
          pub["mode"] == "dry_run" and home not in json.dumps(pub) and "limits" in pub, pub)


def feed(t, trades=(), risk=None, alerts=()):
    return {"t": t, "trades": list(trades), "risk": risk or {"mode": "paper"}, "alerts": list(alerts)}


def part_g(tmp):
    tr = {"t": 1, "ticker": "KXA", "title": "Bitcoin up", "side": "yes", "action": "buy", "contracts": 5, "price": 0.4, "pnl": None}
    m = G.events(feed(1), feed(2, [tr]))
    check("g. a new trade -> 'Kalshi fill' with what, how many, price", len(m) == 1 and m[0]["title"] == "Kalshi fill"
          and "BUY 5 YES @ 40c" in m[0]["body"], m)
    m = G.events(feed(2, [tr]), feed(3, [{**tr, "pnl": -2.1}]))
    check("g. that trade settled at a loss -> 'Kalshi loss -$2.10' (high)", [x["title"] for x in m] == ["Kalshi loss -$2.10"]
          and m[0]["priority"] == "high", m)
    check("g. a win: no push", G.events(feed(2, [tr]), feed(3, [{**tr, "pnl": 3.0}])) == [])
    m = G.events(feed(1, risk={"mode": "live"}), feed(2, risk={"mode": "paper", "kill": True, "kill_t": 5}))
    check("g. kill switch on -> urgent push; the mode change too", {"Kalshi KILL SWITCH ON", "Kalshi now paper"} == {x["title"] for x in m}
          and any(x["priority"] == "urgent" for x in m), m)
    m = G.events(feed(1, risk={"mode": "live", "today": {"day": "d"}}), feed(2, risk={"mode": "live", "stopped": True, "today": {"day": "d", "pnl": -10}}))
    check("g. daily stop hit -> push", [x["title"] for x in m] == ["Kalshi daily stop hit"] and "$10.00" in m[0]["body"], m)
    m = G.events(feed(1, risk={"mode": "paper"}), feed(2, risk={"mode": "live", "why": "armed by you"}))
    check("g. armed live -> 'Kalshi LIVE: real money'", [x["title"] for x in m] == ["Kalshi LIVE: real money"], m)
    m = G.events(feed(1, risk={"mode": "paper", "unguarded": 0}), feed(2, risk={"mode": "paper", "unguarded": 1}))
    check("g. a real order around the guard -> urgent push", m and m[0]["priority"] == "urgent", m)
    m = G.events(feed(1), feed(2, alerts=[{"level": "bad", "text": "A bot service is not running"}]))
    check("g. a new 'bad' alert from the bot -> 'needs you'", [x["title"] for x in m] == ["Kalshi bot: needs you"], m)
    home = os.path.join(tmp, "ntfy")
    os.makedirs(home)
    json.dump({"topic": "olympus-test-topic-1"}, open(os.path.join(home, "ntfy.json"), "w"))
    sent = []

    def post(base, topic, body, **k):
        sent.append((topic, k.get("title"), body))
        return True, "ok"

    n1 = G.notify(feed(1, [tr]), home=home, post=post, say=lambda *_: None)
    check("g. notify: the first round only records (no flood of old trades)", n1 == 0 and not sent)
    n2 = G.notify(feed(2, [{**tr, "t": 9}, tr]), home=home, post=post, say=lambda *_: None)
    check("g. notify: the next round pushes the new fill to the topic", n2 == 1 and sent[-1][1] == "Kalshi fill"
          and sent[-1][0] == "olympus-test-topic-1")
    n3 = G.notify(feed(3, [{**tr, "t": 9}, tr]), home=home, post=post, say=lambda *_: None)
    check("g. notify: nothing new -> nothing sent", n3 == 0 and len(sent) == 1)

    def fail(*a, **k):
        return False, "down"

    G.notify(feed(4, [{**tr, "t": 10}, {**tr, "t": 9}, tr]), home=home, post=fail, say=lambda *_: None)
    n5 = G.notify(feed(5, [{**tr, "t": 10}, {**tr, "t": 9}, tr]), home=home, post=post, say=lambda *_: None)
    check("g. notify: a failed post is kept and sent on the next round (once)", n5 == 1 and sent[-1][1] == "Kalshi fill"
          and G.notify(feed(6, [{**tr, "t": 10}, {**tr, "t": 9}, tr]), home=home, post=post, say=lambda *_: None) == 0)
    al = G.feed_alerts({"mode": "paper", "kill": True, "stopped": True, "connected": False, "unguarded": 2, "limits": {"daily_stop_usd": 10},
                        "last_block": {"t": 100, "text": "too close"}}, now=200)
    check("g. feed_alerts: around-the-guard, kill, stop = bad; not connected = warn; a recent block = info",
          [a["level"] for a in al] == ["bad", "bad", "bad", "warn", "info"], al)


def part_h():
    real = socket.socket

    def nope(*a, **k):
        raise RuntimeError("network used")

    socket.socket = nope
    try:
        tmp = tempfile.mkdtemp(prefix="kguard_net_")
        g = G.Guard(os.path.join(tmp, "g"), bot_dir="", clock=lambda: NOW).init()
        g.set_mode("live", phrase=G.phrase_for(G.et_day(NOW), 10))
        d = g.check(GOOD, balance=100)
        g.record_fill(d["id"], 5, 40)
        g.public()
        ok = d["send"]
        shutil.rmtree(tmp, ignore_errors=True)
    except RuntimeError as e:
        ok = False
        d = str(e)
    finally:
        socket.socket = real
    check("h. checks, fills and the public block make no network call", ok, d)
    src = open(GUARD_FILE, encoding="utf-8").read()
    check("h. the guard never builds a Kalshi order request (no 'portfolio/orders', no key loading)",
          "portfolio/orders" not in src and "PRIVATE KEY" not in src and "KALSHI_API_KEY" not in src)


def main():
    tmp = tempfile.mkdtemp(prefix="kguard_")
    try:
        part_a()
        part_b()
        part_c()
        part_d()
        part_e(tmp)
        part_e2(tmp)
        part_f(tmp)
        part_g(tmp)
        part_h()
    finally:
        for d, _, fs in os.walk(tmp):
            try:
                os.chmod(d, 0o700)
            except OSError:
                pass
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nkalshi guard: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
