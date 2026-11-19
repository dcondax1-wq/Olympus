"""The NQ page's live chart, PC side (owner 2026-11-18, "Live chart + our trades"): tools/pc_report.py's "le-bars" post.

Never the real network (a fake http answers ntfy.sh), never this PC's real NinjaTrader folder (a synthetic le_feed folder in a temp dir),
temp folders only.
  a. packer   read_bar_tail (header, junk, torn last line, CRLF, one row a time), the forming 5m bar from the 1m bars, a 1m-only chart,
              pack_bars: always under 3,900 bytes (the oldest bars go first, never below BARS_MIN, then the oldest closed trades),
              the round trip is exact (gaps at the 17:00 halt too), open / closed trades per account by label, never an account id,
              a broker id or its last 4 digits, BLITZ / the cloud paper twin / ATLAS's paper members never; junk never raises
  b. pacing   market closed, stale bars, unchanged, every 15-minute run in the bots' hours, hourly outside, at once when a trade
              changed (>= 5 min), the daily share (BARS_DAY_MAX), the busy-day stop (BARS_DAY_ALL_MAX), a 429 stops it until the next
              UTC day, a dry run sends and writes nothing
  c. run      run_once with a realistic heartbeat: the ext + core status posts are byte-identical with and without the chart, the core is
              still the status topic's newest post, the chart goes LAST (after the core and the pushes) to <status topic>-bars; a broken
              chart step never touches the status, the pushes or rec["errors"]; a test root never reads this PC's NinjaTrader folder
  d. node     (skipped without node) tools/web_public/nq/nqbars.js unpack = unpack_bars, parse picks the newest le-bars post

  python -X utf8 -m tests.test_pc_bars
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["LE_PR_NO_NET"] = "1"                   # the real HTTP helper refuses: only the fakes below answer

from tools import pc_report as R  # noqa: E402

RES: list = []
ET = ZoneInfo("America/New_York")
BROKER_A, BROKER_B = "MFFUEVAL000041234", "MFFUEVAL000045678"     # fakes (tests/test_repo_secrets: obvious fakes only)
TOPIC = "olympus-nq-status-00000000feedbeef"


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:700]})" if info and not cond else ""))
    return bool(cond)


def et(y, mo, d, h, mi=0) -> int:
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def walk(t_end, n, seed=7, step=8.0, wick=40, p=21000.0, tf=300):
    """n closed 5m bars on the 0.25 grid, the last one opening at t_end - tf (a random walk)."""
    rnd = random.Random(seed)
    out = []
    for i in range(n, 0, -1):
        o = p
        c = round((o + rnd.gauss(0, step)) * 4) / 4
        h = max(o, c) + rnd.randint(0, wick) * 0.25
        lo = min(o, c) - rnd.randint(0, wick) * 0.25
        out.append((t_end - i * tf, o, h, lo, c))
        p = c
    return out


def write_csv(path, rows, header=False, torn=None, crlf=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    nl = "\r\n" if crlf else "\n"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        if header:
            fh.write("time,open,high,low,close,volume" + nl)
        for r in rows:
            fh.write(",".join(str(x) for x in r) + ",100" + nl)
        if torn:
            fh.write(torn)


def nt_folder(tmp, m5, m1=(), inst="MNQ 12-26", root="MNQ"):
    d = os.path.join(tmp, "nt")
    write_csv(os.path.join(d, "le_feed", f"{root}_5m.csv"), m5)
    if m1:
        write_csv(os.path.join(d, "le_feed", f"{root}_1m.csv"), m1)
    if inst:
        with open(os.path.join(d, "le_feed", f"{root}_instrument.txt"), "w", encoding="utf-8") as fh:
            fh.write(inst + "\n")
    return d


def live_L(now, e1=None):
    """A PC live.json (engine/live_publish.build shape): the 50K + 25K #2 evals with a closed and an open trade, BLITZ, the cloud
    paper twin, ATLAS's account B on the board (one live trade, one paper member trade)."""
    e1 = e1 or now - 3 * 3600
    day = R._cme_day(e1)
    return {"t": now - 100, "accounts": [
        {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "source": "pc", "badge": "LIVE",
         "broker_account": BROKER_A, "trades": [
             {"day": day, "entry_t": e1, "exit_t": e1 + 900, "side": "LONG", "qty": 3, "entry": 21003.0, "stop": 20990.0, "target": 21030.0,
              "exit_px": 21030.0, "exit": "TARGET", "pnl": 156.3, "r": 1.99}],
         "position": {"entry_t": now - 1200, "side": "SHORT", "dir": -1, "qty": 6, "entry": 21060.25, "stop": 21070.0, "target": 21020.0,
                      "be": False}},
        {"id": "b25k_2", "name": "Zlarior 25K", "plan": "Builder 25K", "kind": "eval", "source": "pc", "broker_account": BROKER_B, "trades": [
            {"day": day, "entry_t": e1, "exit_t": e1 + 900, "side": "LONG", "qty": 1, "entry": 21003.0, "stop": 20990.0, "target": 21030.0,
             "exit_px": 21030.0, "exit": "TARGET", "pnl": 52.1, "r": 2.0}],
         "position": {"entry_t": now - 1200, "side": "SHORT", "qty": 2, "entry": 21060.25, "stop": 21070.0, "target": 21020.0}},
        {"id": "acct_c", "name": "BLITZ", "kind": "eval", "source": "pc_blitz", "trades": [{"entry_t": e1, "exit_t": e1 + 60, "side": "LONG", "pnl": 5}],
         "position": {"entry_t": now - 300, "side": "LONG", "qty": 1, "entry": 21000.0}},
        {"id": "cloud_paper", "kind": "paper", "source": "cloud", "trades": [{"entry_t": e1, "exit_t": e1 + 60, "side": "LONG", "pnl": 7}]}],
        "board": {"data_t": now - 100, "atlas": {"badge": "SIM", "broker": BROKER_B}, "trades": [
            {"acct": "atlas", "src": "live", "key": "ema_lon_vix", "member": "EMA", "entry_t": e1 + 3600, "exit_t": e1 + 4000, "side": "SHORT",
             "qty": 2, "entry": 21050.0, "stop": 21060.0, "target": 21010.0, "exit_px": 21060.25, "exit": "STOP", "usd": -41.0, "r": -1.02},
            {"acct": "atlas", "src": "paper", "key": "macd_sweep", "member": "MACD", "entry_t": e1 + 7000, "exit_t": e1 + 7300, "side": "LONG",
             "usd": 310.0, "exit": "TARGET"}]}}


def as_float(rows):
    return [(int(t), float(o), float(h), float(lo), float(c)) for t, o, h, lo, c in rows]


# ============================================================================================== a. packer
def packer():
    tmp = tempfile.mkdtemp(prefix="pcbars_a_")
    try:
        now = et(2026, 11, 18, 10, 7) + 30                    # Wed 10:07:30 ET: the 10:05 bar is forming
        # read_bar_tail
        p = os.path.join(tmp, "x.csv")
        rows = walk(et(2026, 11, 18, 10, 0), 30)
        write_csv(p, rows[:-1] + [rows[-2][:1] + (1.0, 2.0, 0.5, 1.5)] + [rows[-1]], header=True, torn="1795000000,21000.5")
        with open(p, "a", encoding="utf-8") as fh:
            pass
        got = R.read_bar_tail(p)
        check("a. read_bar_tail: the header and a torn last line are skipped, a repeated time keeps the last row, oldest first",
              len(got) == 30 and got[-2][1:] == (1.0, 2.0, 0.5, 1.5) and got[0][0] < got[-1][0] and got[-1] == rows[-1], (len(got), got[-2:]))
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write("garbage line\r\n1795000000,abc,1,1,1,1\r\n" + "".join(f"{t},{o},{h},{lo},{c},5\r\n" for t, o, h, lo, c in rows[:5]) + "0,1,1,1,1\r\n")
        got = R.read_bar_tail(p)
        check("a. read_bar_tail: CRLF lines, junk lines and a zero time are skipped", got == as_float(rows[:5]), got)
        check("a. read_bar_tail: a missing file, a folder, None -> [] (never raises)", R.read_bar_tail(os.path.join(tmp, "none.csv")) == [] == R.read_bar_tail(tmp)
              == R.read_bar_tail(None))
        big = os.path.join(tmp, "big.csv")
        write_csv(big, walk(et(2026, 11, 18, 10, 0), 3000))
        got = R.read_bar_tail(big, max_rows=200)
        check("a. read_bar_tail: a big file -> only its end (the newest rows, the first cut line dropped)", len(got) == 200 and got[-1][0] == et(2026, 11, 18, 9, 55), got[-1])
        hl = os.path.join(tmp, "hl.csv")
        with open(hl, "w", encoding="utf-8") as fh:
            fh.write("1795000000,100.0,99.0,101.0,100.5,1\n")
        check("a. read_bar_tail: high / low widened to hold open and close (a valid candle always)", R.read_bar_tail(hl) == [(1795000000, 100.0, 101.0, 99.0, 100.5)],
              R.read_bar_tail(hl))

        # the forming bar from 1m bars
        m5 = walk(et(2026, 11, 18, 10, 5), 60)                # the last closed 5m bar opened 10:00
        m1 = [(et(2026, 11, 18, 10, 5), 21100.0, 21102.0, 21099.0, 21101.0), (et(2026, 11, 18, 10, 6), 21101.0, 21108.5, 21100.25, 21107.0),
              (et(2026, 11, 18, 9, 58), 1.0, 1.0, 1.0, 1.0)]
        bars, forming, data_t = R.chart_bars(m5, sorted(m1), now)
        check("a. the 10:05 bar still forming is built from the 1m bars after the last 5m bar (open first, high max, low min, close last); "
              "data time = the last 1m bar's close (10:07), older 1m bars are not mixed in",
              len(bars) == 61 and bars[-1] == (et(2026, 11, 18, 10, 5), 21100.0, 21108.5, 21099.0, 21107.0) and forming and data_t == et(2026, 11, 18, 10, 7)
              and bars[:-1] == m5, (bars[-1], forming, data_t))
        b2, f2, d2 = R.chart_bars(m5, [], now)
        check("a. no 1m bars: the closed 5m bars only, not forming, data time = the last 5m bar's close", b2 == m5 and not f2 and d2 == et(2026, 11, 18, 10, 5), (f2, d2))
        only1 = [(et(2026, 11, 18, 9, 0) + 60 * i, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i) for i in range(67)]     # 09:00 ... 10:06
        b3, f3, d3 = R.chart_bars([], only1, now)
        check("a. a 1-minute-only chart builds every 5m bar from its 1m bars (the last one, 10:05, forming while now is inside it)",
              len(b3) == 14 and b3[0] == (et(2026, 11, 18, 9, 0), 100.0, 105.0, 99.0, 104.5) and b3[-1] == (et(2026, 11, 18, 10, 5), 165.0, 167.0, 164.0, 166.5)
              and f3 and d3 == et(2026, 11, 18, 10, 7), (len(b3), b3[0], b3[-1], f3, d3))
        check("a. the data time is never later than now (a clock ahead on the PC)", R.chart_bars([], only1, et(2026, 11, 18, 10, 6) + 10)[2] == et(2026, 11, 18, 10, 6) + 10)

        # pack: a normal day, the round trip, the trades
        L = live_L(now)
        bars = walk(et(2026, 11, 18, 10, 5), 180)
        accts, opens, closed = R.chart_trades(L, now, since=bars[0][0])
        post = R.pack_bars(bars, opens, closed, accts, now=now, data_t=now - 30, sym="MNQ 12-26", forming=True, day=R._cme_day(now), trades_t=L["t"])
        body = json.dumps(post, separators=(",", ":"), ensure_ascii=False)
        check("a. le-bars post: its own kind, 180 bars (15 h), 5-minute bars on the 0.25 tick, the contract, today's CME day, the forming flag, under 3,900 bytes",
              post["kind"] == "le-bars" and post["v"] == 1 and post["n"] == 180 and post["tf"] == 300 and post["tick"] == 0.25 and post["sym"] == "MNQ 12-26"
              and post["day"] == "2026-11-18" and post["f"] == 1 and len(body.encode()) < 3900 and post["rt"] == now and post["t"] == now - 30 and post["tt"] == L["t"],
              (len(body.encode()), {k: post.get(k) for k in ("n", "day", "f", "t", "rt", "tt")}))
        check("a. round trip: unpack_bars(post) gives back every bar exactly (times and prices)", R.unpack_bars(post) == as_float(bars), R.unpack_bars(post)[:2])
        check("a. 4 small ints a bar (open - previous close, high - open, open - low, close - open in ticks), p0 = the first open in ticks",
              len(post["b"]) == 4 * 180 and all(isinstance(x, int) for x in post["b"]) and post["p0"] == round(bars[0][1] / 0.25) and post["b"][0] == 0
              and post["b"][1] >= 0 and post["b"][2] >= 0, post["b"][:8])
        check("a. accounts by label (Zlarior 50K, Zlarior 25K #2, ATLAS funded 25K), the bot and the badge; BLITZ and the cloud paper twin never",
              post["ac"] == {"z50k": ["Zlarior 50K", "LIT", "LIVE"], "z25k2": ["Zlarior 25K #2", "LIT"], "atlas25f": ["ATLAS funded 25K", "ATLAS", "SIM"]}
              and "BLITZ" not in body.upper() and "cloud" not in body.lower(), post.get("ac"))
        op = {r["k"]: r for r in post["open"]}
        check("a. every open trade: account, side, micros, entry, stop, target, time (50K SHORT 6 at 21,060.25, stop 21,070, target 21,020; 25K #2 SHORT 2)",
              sorted(op) == ["z25k2", "z50k"] and op["z50k"] == {"k": "z50k", "s": -1, "q": 6, "t": now - 1200, "e": 21060.25, "sl": 21070.0, "tp": 21020.0}
              and op["z25k2"]["q"] == 2 and op["z25k2"]["s"] == -1, post["open"])
        cl = post["closed"]
        check("a. today's closed trades: entry / exit time and price, $ and R, how it ended, oldest first; ATLAS's paper member (MACD +$310) never",
              [(r["k"], r["usd"], r["why"]) for r in cl] == [("z50k", 156.3, "TARGET"), ("z25k2", 52.1, "TARGET"), ("atlas25f", -41.0, "STOP")]
              and cl[0] == {"k": "z50k", "s": 1, "q": 3, "t": now - 3 * 3600, "e": 21003.0, "xt": now - 3 * 3600 + 900, "x": 21030.0, "usd": 156.3, "r": 1.99, "why": "TARGET"}
              and cl[2]["x"] == 21060.25 and cl[2]["s"] == -1 and 310.0 not in [r.get("usd") for r in cl], cl)
        allp = body + json.dumps(R.unpack_bars(post))
        check("a. no account id anywhere: no mffu50k_eval / b25k_2 / acct_c, no broker id, not even its last 4 digits",
              not any(x in allp for x in ("mffu50k", "b25k_2", "acct_c", "cloud_paper", BROKER_A, BROKER_B, "41234", "45678", "MFFU", "1234", "5678")), allp[:200])
        # planted private words in an account's own fields never reach the post (labels come from the fixed list only)
        L4 = json.loads(json.dumps(L))
        L4["accounts"][0].update(name=f"MFFU 50K {BROKER_A} owner@example.com", plan=f"Builder 50K {BROKER_A}", badge=BROKER_A)
        a4, o4, c4 = R.chart_trades(L4, now, since=bars[0][0])
        p4 = json.dumps(R.pack_bars(bars, o4, c4, a4, now=now))
        check("a. planted private words in an account's name / plan / badge never reach the post (labels from the fixed list; badge LIVE / SIM / PAPER only)",
              BROKER_A not in p4 and "MFFUEV" not in p4 and "example.com" not in p4 and a4["z50k"] == ["Zlarior 50K", "LIT"], a4)
        # an account the label list does not know: never its id
        L2 = {"accounts": [{"id": "mffu25k_evalfake", "plan": "Builder 25K", "kind": "eval", "source": "pc", "trades": [],
                            "position": {"entry_t": now - 60, "side": "LONG", "qty": 1, "entry": 21000.0, "stop": 20990.0, "target": 21040.0}}]}
        a2, o2, c2 = R.chart_trades(L2, now)
        check("a. an account the label list does not know is 'Account 1 25K' (key x1), never its id", a2 == {"x1": ["Account 1 25K", "LIT"]} and o2[0]["k"] == "x1"
              and "mffu25k" not in json.dumps([a2, o2]), (a2, o2))
        # an earlier CME day's trades (before Tue 18:00 ET): drawn while they are on the bars, else left out; Tue 21:07 ET is today's
        y, z, w = now - 26 * 3600, now - 20 * 3600, now - 13 * 3600
        L3 = {"accounts": [{"id": "mffu50k_eval", "kind": "eval", "source": "pc", "trades": [
            {"day": R._cme_day(y), "entry_t": y, "exit_t": y + 600, "side": "LONG", "qty": 1, "entry": 1.0, "exit_px": 2.0, "exit": "TARGET", "pnl": 10.0},
            {"day": R._cme_day(z), "entry_t": z, "exit_t": z + 600, "side": "SHORT", "qty": 1, "entry": 1.0, "exit_px": 0.5, "exit": "STOP", "pnl": -5.0},
            {"day": R._cme_day(w), "entry_t": w, "exit_t": w + 600, "side": "LONG", "qty": 1, "entry": 1.0, "exit_px": 1.5, "exit": "TIME", "pnl": 3.0}]}]}
        a3, o3, c3 = R.chart_trades(L3, now, since=now - 22 * 3600)
        check("a. trades of an earlier CME day are kept only while they are on the bars (20 h ago: yes; 26 h ago: no); Tue 21:07 ET is today's (18:00 opens it)",
              [r["usd"] for r in c3] == [-5.0, 3.0] and R._cme_day(w) == "2026-11-18" and R._cme_day(z) == "2026-11-17", c3)
        a3b, _o, c3b = R.chart_trades(L3, now, since=now - 6 * 3600)
        check("a. ... with bars from 04:07 ET only today's trade stays", [r["usd"] for r in c3b] == [3.0] and list(a3b) == ["z50k"], c3b)
        # the size cap: wild bars + many trades
        wild = walk(et(2026, 11, 18, 10, 5), 180, seed=11, step=60.0, wick=900)
        many = [{"k": "z50k", "s": 1, "q": 10, "t": now - 3600 * 5 + i * 60, "e": 21003.25, "xt": now - 3600 * 5 + i * 60 + 30, "x": 21130.75,
                 "usd": -1234.56, "r": -1.23, "why": "TARGET"} for i in range(12)]
        manyo = [{"k": k, "s": -1, "q": 20, "t": now - 900, "e": 21060.25, "sl": 21170.0, "tp": 20820.5, "be": 1} for k in ("z50k", "z25k2", "atlas25f")]
        acc = {"z50k": ["Zlarior 50K", "LIT", "LIVE"], "z25k2": ["Zlarior 25K #2", "LIT"], "atlas25f": ["ATLAS funded 25K", "ATLAS", "SIM"]}
        p2 = R.pack_bars(wild, manyo, many, acc, now=now, data_t=now, sym="MNQ 12-26", forming=True)
        s2 = len(json.dumps(p2, separators=(",", ":"), ensure_ascii=False).encode())
        check("a. wild bars (300-point candles) + 12 closed + 3 open trades: still under 3,900 bytes, the OLDEST bars went first (the newest kept), every trade kept",
              s2 <= 3900 and 12 <= p2["n"] < 180 and R.unpack_bars(p2) == as_float(wild[-p2["n"]:]) and len(p2["closed"]) + p2.get("cut", 0) == 12 and len(p2["open"]) == 3,
              (s2, p2["n"], p2.get("cut")))
        tiny = R.pack_bars(wild, manyo, many, acc, now=now, max_bytes=1500)
        st = len(json.dumps(tiny, separators=(",", ":"), ensure_ascii=False).encode()) if tiny else 0
        check("a. a tight cap: never fewer than BARS_MIN bars; then the oldest closed trades go ('cut' says how many), the open ones stay",
              tiny and tiny["n"] == R.BARS_MIN and st <= 1500 and tiny.get("cut", 0) > 0 and len(tiny["open"]) == 3, (st, tiny and tiny.get("n"), tiny and tiny.get("cut")))
        check("a. impossible to fit -> None (never an oversized post)", R.pack_bars(wild, manyo, many, acc, now=now, max_bytes=300) is None)
        # gaps: the 17:00-18:00 halt
        eve = walk(et(2026, 11, 17, 17, 0), 30, seed=3) + [(et(2026, 11, 17, 18, 0) + 300 * i, 21200.0 + i, 21201.0 + i, 21199.0 + i, 21200.5 + i) for i in range(20)]
        p3 = R.pack_bars(eve, now=et(2026, 11, 17, 19, 45), data_t=et(2026, 11, 17, 19, 40))
        check("a. the 17:00-18:00 halt: 'g' marks the first bar after it ([30, 18:00 ET]) and the round trip keeps every time", p3["g"] == [[30, et(2026, 11, 17, 18, 0)]]
              and R.unpack_bars(p3) == as_float(eve) and p3["day"] == "2026-11-18", p3.get("g"))
        # junk
        junk = [R.pack_bars(None), R.pack_bars([]), R.pack_bars(bars[:5]), R.unpack_bars(None), R.unpack_bars({"kind": "le-live"}),
                R.unpack_bars({"kind": "le-bars", "n": 3, "b": [1, 2]}), R.unpack_bars({"kind": "le-bars", "n": "x"})]
        check("a. junk never raises: no bars / too few bars -> None, a wrong or broken post -> []", junk == [None, None, None, [], [], [], []], junk)
        check("a. chart_trades on junk -> nothing (never raises)", R.chart_trades(None, now) == ({}, [], []) == R.chart_trades({"accounts": "x", "board": 5}, now)
              == R.chart_trades({"accounts": [None, 3, {"id": 5}]}, now))
        # the NinjaTrader folder (LE_BarFeed's files) and the archive fallback
        d = nt_folder(tmp, walk(et(2026, 11, 18, 10, 5), 200), m1[:2])
        f = R.bar_files(os.path.join(tmp, "root"), d)
        bp = R.bars_post(L, now, os.path.join(tmp, "root"), d)
        check("a. bar_files: LE_BarFeed's MNQ_5m / MNQ_1m in the NinjaTrader folder, the chart's contract from MNQ_instrument.txt; bars_post = 180 bars, the forming one last",
              f["src"] == "nt" and f["sym"] == "MNQ 12-26" and bp and bp["n"] == 180 and bp["f"] == 1 and R.unpack_bars(bp)[-1][0] == et(2026, 11, 18, 10, 5)
              and bp["t"] == et(2026, 11, 18, 10, 7) and len(bp["open"]) == 2, (f, bp and bp.get("n")))
        root2 = os.path.join(tmp, "root2")
        write_csv(os.path.join(root2, "data", "nt_bars", "NQ_5m.csv"), walk(et(2026, 11, 18, 10, 5), 40), header=True)
        f2 = R.bar_files(root2, "")
        bp2 = R.bars_post({}, now, root2, "")
        check("a. no NinjaTrader folder ('' = never this PC's): the bot's archive data/nt_bars/NQ_5m.csv (with its header); no trades -> no ac / open / closed",
              f2["src"] == "archive" and bp2 and bp2["n"] == 40 and not any(k in bp2 for k in ("ac", "open", "closed")), (f2, bp2 and bp2.get("n")))
        check("a. nothing anywhere -> no post", R.bars_post(L, now, os.path.join(tmp, "empty"), "") is None and R.bar_files(os.path.join(tmp, "empty"), "")["src"] is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================================================== b. pacing
class FakeHTTP:
    def __init__(self, status=None):
        self.calls, self.status = [], dict(status or {})

    def __call__(self, method, url, body=None, headers=None, timeout=15):
        self.calls.append({"m": method, "url": url, "body": body.decode("utf-8") if isinstance(body, bytes) else body, "h": dict(headers or {})})
        if url.startswith("http://127.0.0.1"):
            return 200, '{"ok": true}'
        if url.startswith("https://ntfy.sh/"):
            return self.status.get(url.rsplit("/", 1)[-1], 200), "{}"
        return 0, "unexpected host"

    def posts(self, topic=None):
        return [c for c in self.calls if c["m"] == "POST" and (topic is None or c["url"].endswith("/" + topic))]


def pacing():
    tmp = tempfile.mkdtemp(prefix="pcbars_b_")
    try:
        cfg = {"ntfy": "https://ntfy.sh", "status_topic": TOPIC}
        feed = os.path.join(tmp, "status_feed.json")
        with open(feed, "w", encoding="utf-8") as fh:
            json.dump({"ntfy": "https://ntfy.sh", "topic": TOPIC}, fh)
        check("b. the chart topic = the status topic + '-bars' (status_feed.json 'bars_topic' overrides; a bad name -> the default; no topic -> '')",
              R.bars_topic(cfg, feed) == TOPIC + "-bars" and R.bars_topic({}, feed) == TOPIC + "-bars" and R.bars_topic({}, os.path.join(tmp, "none.json")) == ""
              and R.bars_topic({"status_topic": "x" * 60}, os.path.join(tmp, "none.json")) == "", R.bars_topic(cfg, feed))
        ov = os.path.join(tmp, "feed2.json")
        with open(ov, "w", encoding="utf-8") as fh:
            json.dump({"topic": TOPIC, "bars_topic": "my-own-chart-topic"}, fh)
        bad = os.path.join(tmp, "feed3.json")
        with open(bad, "w", encoding="utf-8") as fh:
            json.dump({"topic": TOPIC, "bars_topic": "no/slash allowed"}, fh)
        check("b. ... 'bars_topic' in status_feed.json wins; an odd one is ignored", R.bars_topic({}, ov) == "my-own-chart-topic" and R.bars_topic({}, bad) == TOPIC + "-bars")

        t10 = et(2026, 11, 18, 10, 7) + 30                    # Wed 10:07:30 ET: the bots' hours
        t20 = et(2026, 11, 18, 20, 7) + 30                    # Wed 20:07:30 ET: open market, not the bots' hours
        check("b. the bots' hours = weekday 01:50-16:10 ET", R.bars_hours(t10) and not R.bars_hours(t20) and R.bars_hours(et(2026, 11, 18, 1, 50))
              and not R.bars_hours(et(2026, 11, 18, 1, 49)) and R.bars_hours(et(2026, 11, 18, 16, 10)) and not R.bars_hours(et(2026, 11, 21, 10, 0)))

        def make(now, L=None, fresh=True):
            d = os.path.join(tmp, f"nt{now}")
            shutil.rmtree(d, ignore_errors=True)
            end = (now // 300) * 300 if fresh else now - 3600
            m1 = [(end + 60 * i, 21100.0 + i, 21101.0 + i, 21099.0 + i, 21100.5 + i) for i in range((now - end) // 60)] if fresh else []
            return nt_folder(os.path.join(tmp, f"nt{now}"), walk(end, 180, seed=now % 97), m1), L
        work = os.path.join(tmp, "work")
        http = FakeHTTP()

        def step(now, L=None, mo=True, fresh=True, dry=False, other=0, limited=False, say=None, nt=None, busy=False):
            d, _ = make(now, L, fresh) if nt is None else (nt, L)
            return R.bars_step(work, cfg, L or {}, now, mo, dry=dry, http=http, say=say or (lambda *_: None), root=os.path.join(tmp, "root"),
                               nt_folder=d, other_posts=other, limited=limited, feed_path=feed, busy_run=busy), d

        r, d1 = step(t10, live_L(t10), mo=False)
        check("b. market closed -> no post", not r["posted"] and r["why"] == "market closed" and not http.posts(), r)
        r, _ = step(t10, live_L(t10), fresh=False)
        check("b. the newest bar is an hour old while the market is open (the feed is stale) -> no post", not r["posted"] and "old" in r["why"] and not http.posts(), r)
        r, d1 = step(t10, live_L(t10), other=40)
        p1 = http.posts(TOPIC + "-bars")
        body = json.loads(p1[0]["body"]) if p1 else {}
        check("b. fresh bars + the day's trades -> one post to <status topic>-bars (a trade-level post: the trades are new), priority min, kind le-bars, "
              "under 3,900 bytes, nothing to the status topic",
              r["posted"] and r.get("kind") == "trades" and len(p1) == 1 and p1[0]["h"].get("Priority") == "min" and body.get("kind") == "le-bars"
              and len(p1[0]["body"].encode()) < 3900 and not http.posts(TOPIC), (r, len(p1)))
        st = R.read_json(os.path.join(work, R.BARS_STATE), {})
        day = R._utc_day(t10)
        check("b. the state counts today's posts per UTC day (this run's 40 others + 1 chart; not a candle post)", st["days"][day] == {"all": 41, "bars": 1} and st["t"] == t10, st.get("days"))
        r, _ = step(t10 + 60, live_L(t10), nt=d1)
        check("b. the same bars and trades a minute later -> 'unchanged', no post", not r["posted"] and r["why"] == "unchanged" and len(http.posts()) == 1, r)
        r, _ = step(t10 + 600, live_L(t10))
        check("b. new candles 10 minutes later, the trades the same -> not yet (candles about hourly)", not r["posted"] and r["why"].startswith("candles next in") and len(http.posts()) == 1, r)
        L_new = live_L(t10)
        L_new["accounts"][0]["position"] = None
        L_new["accounts"][0]["trades"].append({"entry_t": t10 - 1200, "exit_t": t10 + 500, "side": "SHORT", "qty": 6, "entry": 21060.25, "exit_px": 21020.0,
                                               "exit": "TARGET", "pnl": 471.6, "r": 3.8})
        r, _ = step(t10 + 360, L_new, busy=True)
        cl = json.loads(http.posts()[-1]["body"]).get("closed", []) if r["posted"] else []
        check("b. a trade closed (6 min after the last post) -> posted at once, the close in it, even on a run that sent the ext post (trade levels first)",
              r["posted"] and r["why"] == "a trade changed" and len(http.posts()) == 2 and any(c.get("usd") == 471.6 for c in cl), r)
        L_new2 = json.loads(json.dumps(L_new))
        L_new2["accounts"][1]["position"]["stop"] = 21060.25
        r, _ = step(t10 + 360 + 120, L_new2)
        check("b. ... but never twice in 5 minutes (the 25K #2 stop moved 2 min later: waits)", not r["posted"] and r["why"].startswith("a trade changed: next in") and len(http.posts()) == 2, r)
        r, _ = step(t10 + 360 + 900, L_new2)
        check("b. the next run -> posted (the moved stop in it)", r["posted"] and r["why"] == "a trade changed" and len(http.posts()) == 3
              and any(o.get("sl") == 21060.25 for o in json.loads(http.posts()[-1]["body"]).get("open", [])), r)
        t_c = t10 + 360 + 900 + 3600
        r, _ = step(t_c, L_new2, busy=True)
        r2, _ = step(t_c + 900, L_new2)
        check("b. an hour later, only new candles: not on a run that sent the ext post; on the next run -> one hourly candle post",
              not r["posted"] and "ext post" in r["why"] and r2["posted"] and r2["why"] == "hourly candles" and r2.get("kind") == "candles" and len(http.posts()) == 4, (r, r2))
        st = R.read_json(os.path.join(work, R.BARS_STATE), {})
        check("b. ... counted as a candle post", st["days"][day].get("candles") == 1 and st["days"][day]["bars"] == 4, st["days"].get(day))
        # outside the bots' hours: no candles, trade levels still go
        n0 = len(http.posts())
        r, _ = step(t20, L_new2)
        r2, _ = step(t20 + 3600, L_new2)
        L_ev = {"accounts": [{"id": "mffu50k_eval", "kind": "eval", "source": "pc", "trades": [],
                              "position": {"entry_t": t20 + 3600 + 600, "side": "LONG", "qty": 2, "entry": 21000.0, "stop": 20990.0, "target": 21040.0}}]}
        r3, _ = step(t20 + 3600 + 900, L_ev)
        check("b. outside the bots' hours (20:07 ET, market open): no candle post (twice an hour apart), but an entry still posts at once",
              not r["posted"] and "bots' hours" in r["why"] and not r2["posted"] and r3["posted"] and r3["why"] == "a trade changed" and len(http.posts()) == n0 + 1, (r, r2, r3))
        # the daily share, each on its own state file
        def own(name, counts, ht="old-trades", t_last=0):
            w = os.path.join(tmp, name)
            os.makedirs(w, exist_ok=True)
            R.write_json(os.path.join(w, R.BARS_STATE), {"days": counts, "ht": ht, "hb": "old-bars", "t": t_last})
            return w

        def run_at(w, now, L, busy=False, other=0, limited=False):
            d, _ = make(now)
            return R.bars_step(w, cfg, L, now, True, http=http, root=os.path.join(tmp, "root"), nt_folder=d, feed_path=feed, busy_run=busy, other_posts=other, limited=limited)
        dz = R._utc_day(t10)
        w = own("cap23", {dz: {"all": 60, "bars": R.BARS_DAY_MAX - 1, "candles": 10}})
        r = run_at(w, t10, L_ev)
        r2 = run_at(w, t10 + 900, live_L(t10))
        check("b. BARS_DAY_MAX = 24 chart posts this UTC day, every kind counted: the 24th goes, a 25th never (not even a trade level)",
              r["posted"] and not r2["posted"] and "24 chart posts today" in r2["why"] and R.BARS_DAY_MAX == 24
              and R.read_json(os.path.join(w, R.BARS_STATE), {})["days"][dz]["bars"] == 24, (r, r2))
        w = own("cand18", {dz: {"all": 60, "bars": 18, "candles": R.BARS_DAY_MAX - R.BARS_TRADE_RESERVE}})
        r = run_at(w, t10, L_ev)
        r2 = run_at(w, t10 + 2 * 3600, L_ev)
        check("b. 18 candle posts today: no more candles (6 kept for trade levels), yet a trade change still posts", r["posted"] and r["why"] == "a trade changed"
              and not r2["posted"] and "18 candle posts today" in r2["why"] and R.BARS_DAY_MAX - R.BARS_TRADE_RESERVE == 18, (r, r2))
        w = own("busy", {dz: {"all": R.BARS_DAY_ALL_MAX - 1, "bars": 3}})
        r = run_at(w, t10, L_ev, other=1)
        check("b. a busy ntfy day (this PC counted 226 = 250 - 24 posts today with this run's) -> no chart: the status and the pushes first",
              not r["posted"] and "226 posts today" in r["why"] and R.BARS_DAY_ALL_MAX == 226 and R.NTFY_DAY_CAP == 250, r)
        w = own("lim", {dz: {"all": 10, "bars": 3}})
        r = run_at(w, t10, L_ev, limited=True)
        r2 = run_at(w, t10 + 3600, L_ev)
        check("b. the core or a push met ntfy's daily cap this run (429) -> no chart for the rest of the UTC day", not r["posted"] and "429" in r["why"]
              and not r2["posted"] and "429" in r2["why"], (r, r2))
        work = w
        nxt = et(2026, 11, 19, 19, 5) + 86400 * 0                # 00:05 UTC on 11-20 (19:05 ET 11-19): a new UTC day, the market open
        L_nx = {"accounts": [{"id": "b25k_2", "kind": "eval", "source": "pc", "trades": [],
                              "position": {"entry_t": nxt - 300, "side": "SHORT", "qty": 1, "entry": 21000.0, "stop": 21010.0, "target": 20960.0}}]}
        r, _ = step(nxt, L_nx)
        check("b. ... and the next UTC day it posts again (ntfy.sh resets at 00:00 UTC); days older than 3 are dropped", r["posted"]
              and set(R.read_json(os.path.join(work, R.BARS_STATE), {})["days"]) <= {R._utc_day(nxt - 86400 * k) for k in range(4)}, r)
        http429 = FakeHTTP({TOPIC + "-bars": 429})
        w2 = os.path.join(tmp, "work429")
        d429, _ = make(t10)
        d429b, _ = make(t10 + 3600)
        r = R.bars_step(w2, cfg, {}, t10, True, http=http429, root=tmp, nt_folder=d429, feed_path=feed)
        r2 = R.bars_step(w2, cfg, {}, t10 + 3600, True, http=http429, root=tmp, nt_folder=d429b, feed_path=feed)
        check("b. ntfy answers 429 to the chart -> no more chart posts that UTC day (one try, not one a run)", not r["posted"] and "rate limit" in r["why"]
              and not r2["posted"] and "429" in r2["why"] and len(http429.posts()) == 1, (r, r2))
        # a dry run
        w3 = os.path.join(tmp, "workdry")
        said = []
        http3 = FakeHTTP()
        d3, _ = make(t10)
        r = R.bars_step(w3, cfg, live_L(t10), t10, True, dry=True, http=http3, say=said.append, root=tmp, nt_folder=d3, feed_path=feed)
        check("b. a dry run prints what it would send (bars, trades, bytes, the topic) and sends / writes nothing",
              not r["posted"] and not http3.calls and not os.path.exists(os.path.join(w3, R.BARS_STATE)) and len(said) == 1 and "180 bars" in said[0]
              and "2 open" in said[0] and TOPIC + "-bars" in said[0], said)
        r = R.bars_step(os.path.join(tmp, "w4"), {"ntfy": "https://ntfy.sh"}, {}, t10, True, http=http3, root=tmp, nt_folder=d3, feed_path=os.path.join(tmp, "none.json"))
        check("b. no status topic -> no chart post", not r["posted"] and r["why"] == "no status topic" and not http3.calls, r)
        r = R.bars_step(os.path.join(tmp, "w5"), None, None, "junk", None, http=http3)
        check("b. junk arguments never raise", r["posted"] is False and "softly" in r["why"], r)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================================================== b. a whole day (the budget)
def day_L(t, trail=False):
    """The PC's live.json at time t of Wed 2026-11-18: ATLAS SHORT 03:12-03:44 ET (stopped), Zlarior LONG on the 50K + 25K #2 09:47-11:02 ET
    (stop to break-even at 10:20, target). trail=True: the open trade's stop moves on every 15-minute run from 02:00 to 16:00 ET (the worst case)."""
    T = lambda h, m: et(2026, 11, 18, h, m)                   # noqa: E731
    a_in, a_out, l_in, l_be, l_out = T(3, 12), T(3, 44), T(9, 47), T(10, 20), T(11, 2)
    accts, board = [], []
    for acct, q in (("mffu50k_eval", 3), ("b25k_2", 1)):
        row = {"id": acct, "kind": "eval", "source": "pc", "trades": []}
        if trail and T(2, 0) <= t < T(16, 0):
            row["position"] = {"entry_t": T(2, 0), "side": "LONG", "qty": q, "entry": 21000.0, "stop": 20990.0 + 0.25 * ((t - T(2, 0)) // 900), "target": 21100.0}
        elif l_in <= t < l_out:
            row["position"] = {"entry_t": l_in, "side": "LONG", "qty": q, "entry": 21003.0, "stop": 21003.0 if t >= l_be else 20990.0, "target": 21030.0}
        if t >= l_out:
            row["trades"].append({"day": "2026-11-18", "entry_t": l_in, "exit_t": l_out, "side": "LONG", "qty": q, "entry": 21003.0, "exit_px": 21030.0,
                                  "exit": "TARGET", "pnl": round(27 * 2 * q - 1.9 * q, 2)})
        accts.append(row)
    if a_in <= t < a_out:
        board.append({"acct": "atlas", "src": "live", "entry_t": a_in, "side": "SHORT", "qty": 2, "entry": 21050.0, "stop": 21060.0, "target": 21010.0, "open": True})
    elif t >= a_out:
        board.append({"acct": "atlas", "src": "live", "entry_t": a_in, "exit_t": a_out, "side": "SHORT", "qty": 2, "entry": 21050.0, "exit_px": 21060.25,
                      "exit": "STOP", "usd": -44.8})
    return {"t": t - 60, "accounts": accts, "board": {"trades": board}}


def day_sim():
    tmp = tempfile.mkdtemp(prefix="pcbars_day_")
    try:
        cfg = {"ntfy": "https://ntfy.sh", "status_topic": TOPIC}
        feed = os.path.join(tmp, "status_feed.json")
        with open(feed, "w", encoding="utf-8") as fh:
            json.dump({"ntfy": "https://ntfy.sh", "topic": TOPIC}, fh)
        u0 = int(dt.datetime(2026, 11, 18, 0, 0, tzinfo=dt.timezone.utc).timestamp())     # the UTC day = Tue 19:00 ET -> Wed 19:00 ET
        events = [et(2026, 11, 18, 3, 12), et(2026, 11, 18, 3, 44), et(2026, 11, 18, 9, 47), et(2026, 11, 18, 10, 20), et(2026, 11, 18, 11, 2)]
        nt_dir = os.path.join(tmp, "nt")

        def bars_at(t):
            end = t // 300 * 300
            shutil.rmtree(nt_dir, ignore_errors=True)
            return nt_folder(nt_dir, walk(end, 180, seed=t % 89), [(end + 60 * i, 21100.0, 21101.0, 21099.0, 21100.5) for i in range((t - end) // 60)])

        def one_day(name, trail=False, fast=False):
            work, http, rows, status = os.path.join(tmp, name), FakeHTTP(), [], 0
            prev_ht = None
            for k in range(96):
                t = u0 + 180 + k * 900                           # the 15-minute report task (:03, :18, :33, :48)
                calls = [(t, False)] + ([(t + 300, True), (t + 600, True)] if fast else [])     # fast: a 5-minute --bars caller on top
                for tc, alone in calls:
                    L = day_L(tc, trail)
                    mo = R.market_open(tc, env={})
                    changed = R._bars_hashes({"ac": None, **{kk: v for kk, v in zip(("ac", "open", "closed"), R.chart_trades(L, tc)) if v}})[1] != prev_ht
                    ext = (not alone) and (k % 2 == 0 or changed)      # the ext post: every 2nd run, or at once when its news (a trade) changed
                    other = 0 if alone else 1 + (2 if ext else 0) + (1 if changed and k else 0)   # core + 2 ext parts + a trade push
                    status += other
                    d = bars_at(tc)
                    r = R.bars_step(work, cfg, L, tc, mo, http=http, root=os.path.join(tmp, "root"), nt_folder=d, feed_path=feed, other_posts=other, busy_run=ext)
                    rows.append({"t": tc, "posted": r["posted"], "kind": r.get("kind"), "why": r["why"], "mo": mo, "ext": ext, "hours": R.bars_hours(tc)})
                    prev_ht = R._bars_hashes({kk: v for kk, v in zip(("ac", "open", "closed"), R.chart_trades(L, tc)) if v})[1]
            st = R.read_json(os.path.join(work, R.BARS_STATE), {})
            return rows, http, status, st

        rows, http, status, st = one_day("normal")
        posted = [r for r in rows if r["posted"]]
        cand, trd = [r for r in posted if r["kind"] == "candles"], [r for r in posted if r["kind"] == "trades"]
        first_after = [next((r for r in rows if r["t"] >= e), None) for e in events]
        check(f"b. a whole trading day (96 report runs, the ext every 2nd run): {len(posted)} chart posts = {len(cand)} hourly candle posts + {len(trd)} trade-level posts, "
              f"at most 24 (BARS_DAY_MAX); with ~210 status posts a day that is <= 234 of ntfy's 250",
              len(posted) <= R.BARS_DAY_MAX and len(cand) <= R.BARS_DAY_MAX - R.BARS_TRADE_RESERVE and 210 + len(posted) <= 234 and len(posted) >= 15, [(et_str(r["t"]), r["kind"]) for r in posted])
        check(f"b. ... this PC's whole day in the simulation: {status} status + push posts + {len(posted)} chart = {status + len(posted)} <= 250, and the state file counted it",
              status + len(posted) <= R.NTFY_DAY_CAP and st["days"]["2026-11-18"]["all"] == status + len(posted) and st["days"]["2026-11-18"]["bars"] == len(posted)
              and st["days"]["2026-11-18"].get("candles") == len(cand), (status, st.get("days")))
        check("b. ... every entry / exit / stop move went out on the first run after it (ATLAS 03:12 + 03:44, Zlarior 09:47, the BE stop 10:20, the exit 11:02)",
              all(r and r["posted"] and r["kind"] == "trades" for r in first_after), [(et_str(r["t"]), r["posted"], r["why"]) for r in first_after if r])
        check("b. ... candles only in the bots' hours (01:50-16:10 ET), never on a run that sent the ext post, never twice within 59 minutes; nothing while the market is closed",
              all(r["hours"] and not r["ext"] for r in cand) and all(b["t"] - a["t"] >= R.BARS_GAP_CANDLES_S for a, b in zip(cand, cand[1:]))
              and not any(r["posted"] and not r["mo"] for r in rows) and any(not r["mo"] for r in rows), [(et_str(r["t"]), r["ext"]) for r in cand])
        rows2, http2, status2, st2 = one_day("trail", trail=True)
        p2 = [r for r in rows2 if r["posted"]]
        check(f"b. the worst day (the stop moves on every run 02:00-16:00 ET = 56 changes): still exactly 24 chart posts, then nothing (cap), no 429",
              len(p2) == R.BARS_DAY_MAX and len([r for r in p2 if r["kind"] == "candles"]) <= 18 and any("24 chart posts today" in r["why"] for r in rows2)
              and len(http2.posts(TOPIC + "-bars")) == 24, (len(p2), [(et_str(r["t"]), r["kind"]) for r in p2][-4:]))
        rows3, http3, status3, st3 = one_day("fast", fast=True)
        p3 = [r for r in rows3 if r["posted"]]
        check(f"b. a 5-minute --bars caller on top of the 15-minute runs (288 more calls): {len(p3)} chart posts, still <= 24, the same hourly candles",
              len(p3) <= R.BARS_DAY_MAX and len([r for r in p3 if r["kind"] == "candles"]) <= 18, len(p3))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def et_str(t):
    return dt.datetime.fromtimestamp(t, ET).strftime("%H:%M")


# ============================================================================================== c. run_once
def run():
    from tests.test_live_publish import hb_payload
    tmp = tempfile.mkdtemp(prefix="pcbars_c_")
    old = {k: os.environ.get(k) for k in ("OLYMPUS_HOME", "LE_PR_T_NT", "LE_PR_T_MARKET", "LE_PR_T_NTDIR")}
    try:
        now = et(2026, 11, 18, 10, 7) + 30
        feed = os.path.join(tmp, "status_feed.json")
        with open(feed, "w", encoding="utf-8") as fh:
            json.dump({"ntfy": "https://ntfy.sh", "topic": TOPIC}, fh)
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        with open(os.path.join(home, "ntfy.json"), "w", encoding="utf-8") as fh:
            json.dump({"ntfy": "https://ntfy.sh", "topic": "nq-test-alerts-0000"}, fh)
        end = now // 300 * 300
        d = nt_folder(tmp, walk(end, 200), [(end + 60 * i, 21100.0, 21101.0, 21099.0, 21100.5) for i in range(2)])
        os.environ.update(OLYMPUS_HOME=home, LE_PR_T_NT="1", LE_PR_T_MARKET="1")

        def go(name, ntdir, t, hb=None):
            root = os.path.join(tmp, name)
            os.makedirs(os.path.join(root, "logs", "pc_hb"), exist_ok=True)
            with open(os.path.join(root, "logs", "pc_hb", "heartbeat.json"), "w", encoding="utf-8") as fh:
                json.dump(hb or hb_payload(t), fh)
            os.environ["LE_PR_T_NTDIR"] = ntdir
            http = FakeHTTP()
            rec = R.run_once(work=os.path.join(root, "work"), http=http, root=root, now=t, feed_problem=lambda: None, say=lambda *_: None, feed_path=feed)
            return rec, http, root

        import time as _time
        real_time, fixed = _time.time, _time.time()
        _time.time = lambda: fixed          # engine/board_events.status_block stamps the real clock into the ext post's "brd": the same second for both runs
        try:
            rec0, h0, _ = go("plain", "", now)
            rec1, h1, root1 = go("chart", d, now)
        finally:
            _time.time = real_time
        s0 = [(c["url"], c["body"]) for c in h0.posts(TOPIC)]
        s1 = [(c["url"], c["body"]) for c in h1.posts(TOPIC)]
        check("c. the status posts (ext + core) are byte-identical with and without the chart (their 3,900-byte caps untouched)",
              s0 == s1 and len(s1) >= 2 and all(len(b.encode()) < 3900 for _u, b in s1), (len(s0), len(s1)))
        kinds = [json.loads(c["body"]).get("kind") for c in h1.posts(TOPIC)]
        allposts = [c["url"].rsplit("/", 1)[-1] for c in h1.posts()]
        check("c. the core is still the status topic's newest post (since=latest), the chart goes LAST, to <status topic>-bars",
              kinds[-1] == "le-live" and set(kinds[:-1]) == {"le-live-ext"} and allposts[-1] == TOPIC + "-bars" and allposts.count(TOPIC + "-bars") == 1, (kinds, allposts))
        bars = json.loads(h1.posts(TOPIC + "-bars")[0]["body"])
        check("c. the run's chart post: 180 bars, the forming one, the 50K's open SHORT from the heartbeat (by label), the run's record says posted, not in errors",
              bars["kind"] == "le-bars" and bars["n"] == 180 and bars.get("f") == 1 and [o.get("k") for o in bars.get("open", [])] == ["z50k"]
              and bars["ac"]["z50k"][0] == "Zlarior 50K" and rec1["bars"]["posted"] and rec1["errors"] == rec0["errors"] and rec1["ok"] == rec0["ok"], (bars.get("open"), rec1.get("bars")))
        raw = json.dumps(bars)
        check("c. the chart post through the privacy pass: no PC name, no broker account, no 'FAKEEVAL1', no folder",
              not any(x in raw for x in ("SURFACE", "FAKEEVAL1", "EVAL1", "Users", "owner", "mffu50k")), raw[:300])
        check("c. rec['bars'] is kept beside the record (posted, why, bytes, bars), the state file in the work folder",
              set(rec1["bars"]) >= {"posted", "why", "bytes", "n"} and os.path.isfile(os.path.join(root1, "work", R.BARS_STATE)))
        # a second run 15 minutes later: the open trade closed (a "trade_closed" push, on by default): the push goes before the chart
        hb2 = hb_payload(now + 900)
        pos = hb2["acct"].pop("position")
        hb2["acct"]["position"], hb2["position"] = None, False
        hb2["acct"]["trades"].append({"day": "2026-11-18", "entry_t": now - 600, "exit_t": now + 800, "side": "SHORT", "qty": pos["qty"], "entry": pos["entry"],
                                      "stop": pos["stop"], "target": pos["target"], "exit_px": pos["target"], "pnl": 1431.6, "r": 3.9, "exit": "TARGET"})
        st_path = os.path.join(root1, "work", "state.json")
        os.environ["LE_PR_T_NTDIR"] = d
        http2 = FakeHTTP()
        with open(os.path.join(root1, "logs", "pc_hb", "heartbeat.json"), "w", encoding="utf-8") as fh:
            json.dump(hb2, fh)
        end2 = (now + 900) // 300 * 300
        d2 = nt_folder(os.path.join(tmp, "n2"), walk(end2, 200, seed=5), [(end2 + 60 * i, 21100.0, 21101.0, 21099.0, 21100.5) for i in range(2)])
        os.environ["LE_PR_T_NTDIR"] = d2
        rec2 = R.run_once(work=os.path.join(root1, "work"), http=http2, root=root1, now=now + 900, feed_problem=lambda: None, say=lambda *_: None, feed_path=feed)
        order = [c["url"].rsplit("/", 1)[-1] for c in http2.posts()]
        check("c. a run with a trade push: status posts, then the push, then the chart (it never takes their room)", os.path.isfile(st_path)
              and "nq-test-alerts-0000" in order and order[-1] == TOPIC + "-bars" and order.index("nq-test-alerts-0000") > max(i for i, u in enumerate(order) if u == TOPIC)
              and rec2["bars"]["posted"], (order, rec2.get("bars")))
        st = R.read_json(os.path.join(root1, "work", R.BARS_STATE), {})
        check("c. today's count holds every post of both runs (status + pushes + chart)", st["days"][R._utc_day(now)]["all"] == len(h1.posts()) + len(http2.posts())
              and st["days"][R._utc_day(now)]["bars"] == 2, (st.get("days"), len(h1.posts()), len(http2.posts())))
        # a broken chart step never touches the rest
        real_step, real_trades = R.bars_step, R.chart_trades

        def boom(*a, **k):
            raise RuntimeError("chart exploded")
        R.bars_step, _time.time = boom, (lambda: fixed)
        try:
            rec3, h3, _ = go("broken", d, now)
        finally:
            R.bars_step, _time.time = real_step, real_time
        check("c. the chart step raises -> the status posts are the same, no chart post, rec ok as without it, rec['bars'] says it failed softly",
              [(c["url"], c["body"]) for c in h3.posts(TOPIC)] == s0 and not h3.posts(TOPIC + "-bars") and rec3["errors"] == rec0["errors"]
              and "failed softly" in rec3["bars"]["why"], rec3.get("bars"))
        R.chart_trades, _time.time = boom, (lambda: fixed)
        try:
            rec4, h4, _ = go("broken2", d, now)
        finally:
            R.chart_trades, _time.time = real_trades, real_time
        check("c. the trades part raises inside -> no chart post that run, the status posts untouched", not h4.posts(TOPIC + "-bars")
              and [(c["url"], c["body"]) for c in h4.posts(TOPIC)] == s0 and rec4["errors"] == rec0["errors"], rec4.get("bars"))
        # a dry run: nothing sent
        os.environ["LE_PR_T_NTDIR"] = d
        http5 = FakeHTTP()
        said = []
        root5 = os.path.join(tmp, "dry")
        os.makedirs(os.path.join(root5, "logs", "pc_hb"), exist_ok=True)
        with open(os.path.join(root5, "logs", "pc_hb", "heartbeat.json"), "w", encoding="utf-8") as fh:
            json.dump(hb_payload(now), fh)
        R.run_once(work=os.path.join(root5, "work"), dry=True, http=http5, root=root5, now=now, feed_problem=lambda: None, say=said.append, feed_path=feed)
        check("c. a dry run (--dry-run) says the chart post too and sends nothing", not http5.posts() and any("chart bars" in s for s in said), said[-2:])
        # a test root never reads this PC's NinjaTrader folder
        os.environ.pop("LE_PR_T_NTDIR", None)
        check("c. without LE_PR_T_NTDIR a root other than the repo never reads this PC's NinjaTrader folder ('' = none); the repo's own root does",
              R._nt_folder(tmp, {}) == "" and R._nt_folder(R.ROOT, {}) is None and R._nt_folder(tmp, {"LE_PR_T_NTDIR": "/x"}) == "/x")
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================================================== d. node twin
NODE = r"""
const fs = require('fs');
import(process.argv[2]).then((B) => {
  const posts = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), nd = fs.readFileSync(process.argv[4], 'utf8');
  const o = { unpack: posts.map((p) => B.unpack(p)), junk: [B.unpack(null), B.unpack({ kind: 'le-live' }), B.unpack({ kind: 'le-bars', n: 2, b: [1] })] };
  const best = B.parse(nd);
  o.best = best ? [best.rt, best.n] : null;
  o.none = [B.parse(''), B.parse('{}\n<html>'), B.parse(JSON.stringify({ event: 'message', message: '{"kind":"le-live","t":5}' }))];
  o.urls = B.feedUrls({ ntfy: 'https://ntfy.sh/', topic: 'abc_DEF-1' });
  o.urls2 = [B.feedUrls({ topic: 'a b' }), B.feedUrls({ ntfy: 'http://x', topic: 'abc' }), B.feedUrls(null), B.feedUrls({ topic: 'abc', bars_topic: 'own-topic' })];
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e); process.exit(1); });
"""


def node_twin():
    exe = shutil.which("node")
    js = os.path.join(ROOT, "tools", "web_public", "nq", "nqbars.js")
    if not exe or not os.path.isfile(js):
        print("[SKIP] node or nq/nqbars.js missing: the JS twin was not checked")
        return
    tmp = tempfile.mkdtemp(prefix="pcbars_d_")
    try:
        now = et(2026, 11, 18, 10, 7) + 30
        bars = walk(et(2026, 11, 18, 10, 5), 180)
        eve = walk(et(2026, 11, 17, 17, 0), 30, seed=3) + [(et(2026, 11, 17, 18, 0) + 300 * i, 21200.0 + i, 21201.0 + i, 21199.0 + i, 21200.5 + i) for i in range(20)]
        posts = [R.pack_bars(bars, now=now), R.pack_bars(eve, now=now), R.pack_bars(walk(et(2026, 11, 18, 10, 5), 180, seed=11, step=60.0, wick=900), now=now)]
        mjs = os.path.join(tmp, "nqbars.mjs")
        shutil.copy(js, mjs)
        pj, ndj, hj = os.path.join(tmp, "posts.json"), os.path.join(tmp, "feed.ndjson"), os.path.join(tmp, "h.cjs")
        with open(pj, "w", encoding="utf-8") as fh:
            json.dump(posts, fh)
        older, newer = dict(posts[1], rt=now - 900), dict(posts[0], rt=now - 30)
        lines = [json.dumps({"event": "open"}), json.dumps({"event": "message", "time": now - 900, "message": json.dumps(older)}),
                 json.dumps({"event": "message", "time": now - 30, "message": json.dumps(newer)}),
                 json.dumps({"event": "message", "time": now - 10, "message": "not json"}),
                 json.dumps({"event": "message", "time": now - 5, "message": json.dumps({"kind": "le-live", "t": now})})]
        with open(ndj, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        with open(hj, "w", encoding="utf-8") as fh:
            fh.write(NODE)
        r = subprocess.run([exe, hj, mjs, pj, ndj], capture_output=True, text=True, timeout=120)
        o = json.loads(r.stdout or "{}") if r.returncode == 0 else {}
        py = [[list(b) for b in R.unpack_bars(p)] for p in posts]
        check("d. nqbars.js unpack = unpack_bars exactly (a normal day, the 17:00 halt gap, wild candles)", o.get("unpack") == py, (r.stderr[-400:], str(o.get("unpack"))[:200]))
        check("d. nqbars.js unpack of junk -> []", o.get("junk") == [[], [], []], o.get("junk"))
        check("d. nqbars.js parse: the newest le-bars post of an ntfy poll answer (other kinds, junk lines and the open event skipped); nothing -> null",
              o.get("best") == [now - 30, 180] and o.get("none") == [None, None, None], (o.get("best"), o.get("none")))
        check("d. nqbars.js feedUrls: <ntfy>/<topic>-bars, since=latest first then a 12-hour window; a bad topic / http / nothing -> []; 'bars_topic' wins",
              o.get("urls") == ["https://ntfy.sh/abc_DEF-1-bars/json?poll=1&since=latest", "https://ntfy.sh/abc_DEF-1-bars/json?poll=1&since=12h"]
              and o.get("urls2") == [[], [], [], ["https://ntfy.sh/own-topic/json?poll=1&since=latest", "https://ntfy.sh/own-topic/json?poll=1&since=12h"]], (o.get("urls"), o.get("urls2")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    packer()
    pacing()
    day_sim()
    run()
    node_twin()
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


def test_pc_bars():                      # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
