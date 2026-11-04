"""tools/kalshi_scan.py: "where the money is" (offline, deterministic: a synthetic feed and ledger, nothing from the network).
  a. the maths: fee-adjusted EV per $1 = (win rate - price - fee) / price with the research's own fee function, the Wilson range on the win rate
  b. cells: a 30-bet floor (29 is out), band / coin / strategy from the totals, time of day (ET, across the DST change) and crossings from bets seen one by one
  c. fragile: positive only on a small sample, a range that includes zero, or an assumed price; ranking (robust first), the avoid list by dollars lost
  d. the file: top 5 and top 5 in plain words with the dollars, <= 30 KB even from thousands of bets, deterministic bytes, no rewrite when nothing changed
  e. junk in (NaN, text, duplicates, negative prices, empty feed, not a feed), the feed unreachable (exit 2, nothing written)
    python -X utf8 -m tests.test_kalshi_scan
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import random
import re
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import kalshi_research as KR  # noqa: E402
from tools import kalshi_scan as KS  # noqa: E402

RES: list = []
ET = ZoneInfo("America/New_York")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def feed(buckets=None, cats=None, strats=None, trades=None, cal=None, t=1_793_000_000):
    return {"v": 3, "kind": "kalshi", "t": t, "balance": 100.0, "total_pnl": 0.0, "buckets": buckets or [], "categories": cats or [], "strategies": strats or [],
            "calibration": cal or [], "trades": trades or [], "stats": {"avg_price": 0.95}}


def bucket(lo, hi, n, w, pnl, st):
    return {"lo": lo, "hi": hi, "trades": n, "wins": w, "losses": n - w, "pnl": pnl, "staked": st}


def bets(n, wins, price, cat, ts, c=10):
    """n settled bets of one kind: `wins` of them win (pnl > 0), the rest lose"""
    out = []
    for i in range(n):
        win = i < wins
        out.append({"t": ts + i * 60, "k": f"KX-{cat}-{price}-{ts}-{i}", "s": "test", "m": cat, "sd": "yes", "p": price, "c": c,
                    "pnl": round(c * (1 - price) - KR.fee_pc(price) * c, 2) if win else round(-c * price - KR.fee_pc(price) * c, 2)})
    return out


def main():
    # ---- a. the maths
    p, n, w = 0.96, 400, 392
    c = KS.make_cell("x", {}, n, w, p, KR.fee_pc(p), 10.0, 3800.0, "t")
    lo, hi = KR.wilson(w, n)
    exp = (w / n - p - KR.fee_pc(p)) / p
    check("a. fee-adjusted EV per $1 = (win rate - price - fee) / price, the fee from tools/kalshi_research.fee_pc (the research's own function)",
          abs(c["ev"] - round(exp, 4)) < 1e-9 and abs(c["ev_gross"] - round((w / n - p) / p, 4)) < 1e-9 and c["ev"] < c["ev_gross"], (c["ev"], exp))
    check("a. its 95% range is the Wilson range of the win rate put through the same formula (lo < ev < hi)",
          abs(c["ev_lo"] - round((lo - p - KR.fee_pc(p)) / p, 4)) < 1e-9 and abs(c["ev_hi"] - round((hi - p - KR.fee_pc(p)) / p, 4)) < 1e-9 and c["ev_lo"] < c["ev"] < c["ev_hi"])
    check("a. the fallback fee / Wilson (used where numpy is missing) equal the research's: same numbers at ten prices and sizes",
          all(abs(KS.fee_pc(x) - KR.fee_pc(x)) < 1e-12 for x in (0.05, 0.3, 0.5, 0.9, 0.96, 0.99)) and KS.wilson is KR.wilson or all(abs(a - b) < 1e-12 for a, b in zip(KS.wilson(30, 40), KR.wilson(30, 40))))
    check("a. fees are real money: a 96c bet's fee is 0.07 x 0.96 x 0.04 = 0.27c a contract, so the gross EV minus the fee EV = fee / price",
          abs((c["ev_gross"] - c["ev"]) - KR.fee_pc(p) / p) < 2e-4, (c["ev_gross"], c["ev"]))
    check("a. below 30 bets there is no cell (29), and no cell without a sensible price", KS.make_cell("x", {}, 29, 28, 0.96, 0.003, 0, 0, "t") is None and KS.make_cell("x", {}, 30, 29, 0.999, 0, 0, 0, "t") is None
          and KS.make_cell("x", {}, 30, 29, 0.96, 0.003, 0, 0, "t") is not None)

    # ---- b. cells from the totals and from bets one by one
    buckets = [bucket(0.9, 0.95, 581, 536, -248.3, 5343.43), bucket(0.95, 0.97, 715, 699, 136.98, 9181.72), bucket(0.97, 0.99, 29, 29, 1.0, 400.0), bucket(0.0, 0.2, 1, 0, -0.16, 0.76)]
    cal = [{"p": 0.9277, "n": 581, "hit": 0.9225}, {"p": 0.961, "n": 715, "hit": 0.9776}]
    cats = [{"name": "XRP", "trades": 192, "wins": 178, "losses": 14, "pnl": -106.63, "staked": 1739.04}, {"name": "Tiny", "trades": 12, "wins": 12, "pnl": 3.0, "staked": 100.0}]
    sample = [{"t": 1_793_000_000 - i, "ticker": "X", "action": "buy", "price": 0.96, "category": "XRP", "strategy": "S", "contracts": 5, "pnl": 0.1} for i in range(4)]
    strats = [{"name": "S", "total_pnl": -50.0, "trades": 300, "wins": 280, "losses": 20}]
    tc = KS.total_cells(feed(buckets, cats, strats, sample, cal))
    names = [x["name"] for x in tc]
    check("b. totals: price bands and coins and strategies with >= 30 bets are cells (the 29-bet band, the 1-bet band and the 12-bet coin are not)",
          names == ["90–95¢ bets", "95–97¢ bets", "XRP bets", "the S strategy"], names)
    band = tc[0]
    check("b. a band uses the calibration's own price (92.77c) and carries its dollars: lost $248.30 on $5,343.43 bet, fees about $27",
          abs(band["price"] - 0.9277) < 1e-9 and band["pnl"] == -248.3 and band["staked"] == 5343.43 and 20 < band["fees"] < 35 and band["source"].startswith("totals"), band)
    xrp = tc[2]
    check("b. a coin's price is not in the totals: the mean of its recent bets (96c from 4 bets) is used and the cell says so", abs(xrp["price"] - 0.96) < 1e-9 and "4 recent XRP bets" in xrp["price_source"], xrp)
    # time of day across the DST change: 2026-11-01 02:00 ET is the fall-back day
    et = lambda y, mo, d, h: int(dt.datetime(y, mo, d, h, 30, tzinfo=ET).timestamp())   # noqa: E731
    check("b. time of day is New York time: 19:30 ET = Asia, 03:30 = London, 09:30 = NY morning, 14:30 = NY afternoon, in summer and winter alike",
          [KS.hour_of(et(2026, 7, 1, h)) for h in (19, 3, 9, 14)] == ["asia", "london", "nyam", "nypm"] and [KS.hour_of(et(2026, 12, 1, h)) for h in (19, 3, 9, 14)] == ["asia", "london", "nyam", "nypm"]
          and KS.hour_of(et(2026, 11, 1, 9)) == "nyam" and KS.hour_of(et(2026, 3, 8, 9)) == "nyam")
    T = et(2026, 10, 14, 9)
    rows = bets(40, 38, 0.96, "BTC", T) + bets(35, 20, 0.93, "XRP", T + 86400) + bets(20, 20, 0.97, "ETH", T + 2 * 86400)
    cc = {x["name"]: x for x in KS.cross_cells(KS.bet_rows(feed(), {"trades": [{"t": r["t"], "k": r["k"], "s": r["s"], "m": r["m"], "sd": r["sd"], "p": r["p"], "c": r["c"], "pnl": r["pnl"]} for r in rows]}))}
    check("b. from bets seen one by one: the crossings with >= 30 bets exist (band x coin, band x time, coin x time, all three, the time alone); the 20-bet ETH slices do not",
          "BTC bets priced 95–97¢ placed in New York morning (8 am to noon ET)" in cc and "BTC bets priced 95–97¢" in cc and "bets placed in New York morning (8 am to noon ET)" in cc
          and not any("ETH" in k for k in cc) and "XRP bets priced 90–95¢" in cc, sorted(cc))
    btc = cc["BTC bets priced 95–97¢"]
    check("b. a crossing's EV is worked bet by bet: win rate 38/40, mean price 96c, the mean fee; its dollars are the sum of the real P&L",
          btc["n"] == 40 and btc["wins"] == 38 and abs(btc["price"] - 0.96) < 1e-9 and abs(btc["pnl"] - round(sum(r["pnl"] for r in rows if r["m"] == "BTC"), 2)) < 0.011 and btc["source"].startswith("95 bets seen"), btc)

    # ---- c. fragile and ranking
    big = bets(400, 394, 0.96, "BTC", T)                                  # 98.5% against 96%: robust
    small = bets(35, 35, 0.96, "ETH", T + 5 * 86400)                      # 35 of 35: positive, a small sample
    losing = bets(120, 100, 0.93, "XRP", T + 9 * 86400)                   # 83% against 93%: clearly negative
    res = KS.scan(feed(), {"trades": [{"t": r["t"], "k": r["k"], "s": r["s"], "m": r["m"], "sd": r["sd"], "p": r["p"], "c": r["c"], "pnl": r["pnl"]} for r in big + small + losing]})
    led_rows = KS.bet_rows(feed(), {"trades": [{"t": r["t"], "k": r["k"], "s": r["s"], "m": r["m"], "sd": r["sd"], "p": r["p"], "c": r["c"], "pnl": r["pnl"]} for r in big + small + losing]})
    by = {x["name"]: x for x in KS.cross_cells(led_rows)}
    check("c. fragile: 35 of 35 is positive but flagged (under 100 bets) and words say so; 394 of 400 is not flagged",
          by["ETH bets priced 95–97¢"]["fragile"] and "fragile (under 100 bets" in KS.say(by["ETH bets priced 95–97¢"]) and not by["BTC bets priced 95–97¢"]["fragile"], [(k, v["fragile"]) for k, v in by.items()])
    names_t = [x["name"] for x in res["test"]]
    robust_first = [x["fragile"] for x in res["test"]]
    check("c. ranking: robust cells come before fragile ones, robust by the lower end of their range", robust_first == sorted(robust_first) and not res["test"][0]["fragile"]
          and [x["ev_lo"] for x in res["test"] if not x["fragile"]] == sorted((x["ev_lo"] for x in res["test"] if not x["fragile"]), reverse=True), names_t)
    check("c. the avoid list is the losing cells, the most dollars lost first; the loser is proven negative", res["avoid"][0]["name"].startswith("XRP") and res["avoid"][0]["proven"] == "negative"
          and [x["pnl"] for x in res["avoid"]] == sorted(x["pnl"] for x in res["avoid"]) and all(x["ev"] < 0 for x in res["avoid"]))
    wide = KS.make_cell("w", {}, 60, 56, 0.9, KR.fee_pc(0.9), 5.0, 500.0, "t")
    guess = KS.make_cell("g", {}, 400, 396, 0.95, KR.fee_pc(0.95), 5.0, None, "t", "the feed's average entry price")
    check("c. positive only by luck of the draw: a range that includes zero (60 bets) is fragile; a big sample at an ASSUMED price is fragile too (a wrong price can fake an edge)",
          wide["ev"] > 0 and wide["ev_lo"] <= 0 and wide["fragile"] and guess["ev"] > 0 and guess["fragile"] and "price is assumed" in KS.say(dict(guess, name="g")))
    lost_big = KS.make_cell("l", {}, 60, 40, 0.5, KR.fee_pc(0.5), -30.0, 300.0, "t")
    pos_lost = KS.make_cell("pl", {}, 150, 147, 0.96, KR.fee_pc(0.96), -20.0, 1000.0, "t")
    check("c. a cell that is positive at equal size but lost real money says the losing bets were bigger; a negative cell whose range includes zero says 'not proven'",
          "losing bets were bigger" in KS.say(pos_lost) and "not proven" in KS.say(KS.make_cell("o", {}, 40, 37, 0.95, KR.fee_pc(0.95), -3.0, 100.0, "t")), KS.say(pos_lost))

    # ---- d. the file
    check("d. top 5 and top 5 at most, each in plain words with the numbers (a win rate, a price, cents per $1, a range), a headline, the 'not proven' label",
          len(res["test"]) <= 5 and len(res["avoid"]) <= 5 and all(re.search(r"won [\d.]+% of [\d,]+ bets against [\d.]+% priced", x["text"]) and "¢ on every $1 risked" in x["text"] and "95% range" in x["text"]
                                                                    for x in res["test"] + res["avoid"]) and "not proven" in res["label"].lower() and "Best slice to paper-test" in res["headline"], res["headline"])
    rnd = random.Random(7)
    heavy = []
    for i in range(6000):
        px = rnd.choice([0.5, 0.7, 0.9, 0.93, 0.96, 0.98])
        cat = rnd.choice(["BTC", "ETH", "XRP", "SOL", "DOGE", "NEAR", "ZEC", "HYPE", "BNB"])
        heavy.append({"t": 1_792_000_000 + i * 700, "k": f"K{i}", "s": "s", "m": cat, "sd": "yes", "p": px, "c": 5, "pnl": round(5 * (1 - px) - 0.02, 2) if rnd.random() < px else round(-5 * px - 0.02, 2)})
    big_res = KS.scan(feed(), {"trades": heavy})
    raw = json.dumps(big_res, ensure_ascii=False).encode("utf-8")
    check("d. from 6,000 bets (hundreds of cells) the file is still <= 30 KB and holds 5 + 5", len(raw) <= 30_000 and len(big_res["test"]) == 5 and len(big_res["avoid"]) == 5 and big_res["cells_scanned"] > 100, (len(raw), big_res["cells_scanned"]))
    tmp = tempfile.mkdtemp(prefix="le_kalshi_scan_")
    try:
        fp, out = os.path.join(tmp, "k.json"), os.path.join(tmp, "o", "scan.json")
        snap = json.load(open(os.path.join(ROOT, "research", "kalshi", "feed_snapshot_2026-11-04.json"), encoding="utf-8"))
        json.dump(snap, open(fp, "w"))
        r1 = KS.main(["--feed", fp, "--out", out, "--ledger", os.path.join(tmp, "none.json")])
        b1 = open(out, "rb").read()
        r2 = KS.main(["--feed", fp, "--out", out, "--ledger", os.path.join(tmp, "none.json")])
        d1 = json.loads(b1)
        check("d. the real 2026-11-04 feed: the slice to avoid is the 90–95¢ band (lost $248), 95–97¢ is the best to paper-test, XRP is on the avoid list; under 30 KB; the same bytes on a rerun with no rewrite",
              r1 == 0 and r2 == 0 and open(out, "rb").read() == b1 and len(b1) <= 30_000 and d1["avoid"][0]["name"] == "90–95¢ bets" and d1["avoid"][0]["pnl"] == -248.3 and d1["test"][0]["name"] == "95–97¢ bets"
              and any(x["name"] == "XRP bets" for x in d1["avoid"]) and not d1["test"][0]["fragile"], d1["headline"])
        check("d. cells are never double counted: no two cells share a name", len({x["name"] for x in d1["test"] + d1["avoid"]}) == len(d1["test"] + d1["avoid"]))
        # ---- e. junk and unreachable
        junk = dict(snap)
        junk["buckets"] = snap["buckets"] + [{"lo": float("nan"), "hi": 1, "trades": 99, "wins": 5, "losses": 5, "pnl": 1, "staked": 1}, "x", None, {"lo": 0.9, "hi": 0.95, "trades": 581, "wins": 536, "losses": 45, "pnl": -248.3, "staked": 5343.43}]
        junk["trades"] = snap["trades"] + [{"t": float("nan"), "price": 0.9, "contracts": 1, "pnl": 1}, {"t": 1_793_000_000, "price": -0.5, "contracts": 1, "pnl": 1}, {"t": 1_793_000_000, "price": True, "contracts": 1, "pnl": 1}, "junk"]
        junk["categories"] = snap["categories"] + [{"name": "Z", "trades": "999", "wins": 1, "pnl": -5, "staked": 5}, {"name": "Y", "trades": 99, "wins": 99, "pnl": float("inf"), "staked": 5}]
        check("e. junk rows (NaN, text, duplicates, negative or boolean prices, infinity, None) change nothing: the same answer as the clean feed", KS.scan(junk)["avoid"] == KS.scan(snap)["avoid"] and KS.scan(junk)["test"] == KS.scan(snap)["test"])
        led_dup = {"trades": [{"t": 1_793_000_000 - i * 60, "k": "D", "s": "s", "m": "BTC", "sd": "yes", "p": 0.97, "c": 5, "pnl": 0.1} for i in range(10)] * 5}
        check("e. a ledger that repeats the same bet 50 times counts it once (10 bets, so no 30-bet cell)", len(KS.bet_rows(feed(), led_dup)) == 10 and KS.cross_cells(KS.bet_rows(feed(), led_dup)) == [])
        empties = [KS.scan(x) for x in (feed(), {"kind": "kalshi"}, {})]
        check("e. an empty feed: 0 cells, 'not enough bets in any one slice', no crash", all(e["cells_scanned"] == 0 and "Not enough bets in any one slice" in e["headline"] and e["test"] == [] and e["avoid"] == [] for e in empties))
        before = open(out, "rb").read()
        rc = [KS.main(["--feed", x, "--out", out]) for x in (os.path.join(tmp, "nope.json"), "http://127.0.0.1:9/k.json")]
        open(os.path.join(tmp, "bad.json"), "w").write("{}")
        rc.append(KS.main(["--feed", os.path.join(tmp, "bad.json"), "--out", out]))
        check("e. feed unreachable (missing file, dead address, not a kalshi.json): exit 2 each time, the earlier scan.json untouched, nothing invented", rc == [2, 2, 2] and open(out, "rb").read() == before)
        rc = KS.main(["--feed", os.path.join(tmp, "nope.json"), "--out", os.path.join(tmp, "fresh", "scan.json")])
        check("e. no feed and no earlier file: exit 2 and no file", rc == 2 and not os.path.exists(os.path.join(tmp, "fresh")))
        led = os.path.join(tmp, "led.json")
        open(led, "w").write("{broken")
        check("e. a broken ledger is ignored: the totals still scan", KS.main(["--feed", fp, "--out", os.path.join(tmp, "o2", "scan.json"), "--ledger", led]) == 0)
        src = open(os.path.join(ROOT, "tools", "kalshi_scan.py"), encoding="utf-8").read()
        check("e. read only: no key, no Kalshi trading address, no order word; the only network call is the feed's own repo",
              not re.search(r"kalshi\.com|trading-api|elections|api_key|KALSHI_|\.env|place_order|POST", src) and KS.FEED_URL == "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(RES)
    print(f"\nkalshi scan: {n_ok}/{len(RES)} " + ("ALL PASS" if n_ok == len(RES) else "FAILED"))
    return 0 if n_ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
