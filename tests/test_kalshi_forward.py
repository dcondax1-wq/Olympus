"""tools/kalshi_forward.py: the forward paper tally for the Kalshi rule sets A / B / C. Offline and deterministic: a synthetic feed (a made-up bot at
$100, bets at 93c / 96c / 98c / 85c), no network, no browser, nothing outside a temp folder.
  a. the first run freezes the start (the feed's own time) and counts nothing: bets placed before it are never counted (no look-ahead)
  b. new settled bets are folded in once, each rule set keeps / skips / shrinks them by its rule, net $ and max drawdown exact to the cent
  c. the same feed again: 'no new bets', every file byte-identical; an open bet counts only once it settles, once
  d. the feed unreachable (missing file, junk, not a kalshi.json, a dead address): exit 2, nothing written, an earlier tally untouched
  e. 'collecting' under 30 bets (no leader), a leader from 30 on; the gap flag when a whole window of bets is newer than anything seen
  f. the card keeps the Jarvis contract; sell rows and junk values are ignored; the output is deterministic
    python -X utf8 -m tests.test_kalshi_forward
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import kalshi_forward as KF  # noqa: E402

RES: list = []
T0 = 1_793_000_000


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def bet(i, t, price, n, pnl, side="yes", action="buy", ticker=None):
    return {"t": t, "ticker": ticker or f"KXTEST-{i}", "title": f"test {i}", "side": side, "action": action, "contracts": n, "price": price, "pnl": pnl,
            "asset": "BTC", "strategy": "Late favourite (BTC hourly)", "category": "Bitcoin"}


def feed(trades, t, balance=100.0):
    """newest first, like the real feed; at most 40"""
    tr = sorted(trades, key=lambda x: -(x["t"] if isinstance(x["t"], (int, float)) else 0))[:40]
    return {"v": 3, "kind": "kalshi", "name": "Synthetic", "t": t, "balance": balance, "total_pnl": 0.0, "trades": tr}


def put(folder, name, obj):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return path


def run(folder, fd, name="kalshi.json"):
    src = put(folder, name, fd)
    return KF.main(["--feed", src, "--out", os.path.join(folder, "state", "forward.json")])


def files(folder):
    d = os.path.join(folder, "state")
    return {f: open(os.path.join(d, f), "rb").read() for f in sorted(os.listdir(d))} if os.path.isdir(d) else {}


def load(folder, name="forward.json"):
    return json.load(open(os.path.join(folder, "state", name), encoding="utf-8"))


def sha(d):
    return hashlib.sha256(json.dumps({k: v.decode() for k, v in d.items()}, sort_keys=True).encode()).hexdigest()


def main():
    tmp = tempfile.mkdtemp(prefix="le_kalshi_forward_")
    try:
        # ---- a. the first run: the frozen start, nothing counted
        old = [bet(1, T0 - 9000, 0.93, 10, -9.5), bet(2, T0 - 8000, 0.96, 10, 0.3)]            # placed before the start: never counted
        r = run(tmp, feed(old, T0))
        f, st = load(tmp), load(tmp, "forward_state.json")
        check("a. first run: exit 0, the start is the feed's own time and date, no bet counted (the two older bets are ignored)",
              r == 0 and f["start_t"] == T0 and st["start_t"] == T0 and f["bets"] == 0 and all(s["bets"] == 0 for s in f["sets"]) and f["start_day"] == st["start_day"], f)
        check("a. nothing yet: 'Collecting: 0 bets so far', collecting flag, no leader, the after-the-fact flag is there",
              f["collecting"] and f["leader"] is None and f["text"].startswith("Collecting: 0 bets so far") and f["flags"]["band_picked_after_the_fact"] and f["flags"]["no_look_ahead"], f["text"])
        check("a. the three files are written beside each other: forward.json, forward_state.json, forward_card.json", sorted(files(tmp)) == ["forward.json", "forward_card.json", "forward_state.json"])
        # ---- b. new settled bets
        # cap = 2% of $100 = $2.00. A 93c x10 bet costs $9.30 (in the 90-95c leak); 96c x10 = $9.60; 98c x5 = $4.90; 85c x4 = $3.40 (under 90c)
        new = [bet(3, T0 + 100, 0.93, 10, -9.31), bet(4, T0 + 200, 0.96, 10, 0.31), bet(5, T0 + 300, 0.98, 5, 0.09), bet(6, T0 + 400, 0.85, 4, 0.58),
               bet(7, T0 + 500, 0.93, 10, 0.6), bet(8, T0 + 600, 0.96, 10, -9.62)]
        r = run(tmp, feed(old + new, T0 + 700))
        f = load(tmp)
        S = {s["id"]: s for s in f["sets"]}
        cap = 2.0
        exp = {
            "asis": sum(b["pnl"] for b in new),
            "A": sum(b["pnl"] for b in new if not (0.9 <= b["price"] < 0.95)),
            "B": sum(b["pnl"] * min(1, cap / (b["contracts"] * b["price"])) for b in new if b["price"] >= 0.95),
            "C": sum(b["pnl"] * min(1, cap / (b["contracts"] * b["price"])) for b in new if not (0.9 <= b["price"] < 0.95)),
        }
        check("b. six new bets, each folded in once: the bot as it is = the sum of the real P&L, A skips the two 93c bets, B keeps 95c+ at 2% size, C skips 93c and shrinks the rest",
              r == 0 and f["bets"] == 6 and all(abs(S[k]["net"] - round(v, 2)) < 0.006 for k, v in exp.items()) and [S[k]["bets"] for k in ("asis", "A", "B", "C")] == [6, 4, 3, 4],
              ({k: S[k]["net"] for k in S}, {k: round(v, 2) for k, v in exp.items()}))
        check("b. net vs the bot as it is (vs_asis) and wins / losses per set", abs(S["A"]["vs_asis"] - round(S["A"]["net"] - S["asis"]["net"], 2)) < 0.006 and S["asis"]["wins"] == 4 and S["asis"]["losses"] == 2, S["asis"])
        # max drawdown on the bot as it is: equity -9.31, -9.00, -8.91, -8.33, -7.73, -17.35 -> peak 0, trough -17.35
        check("b. max drawdown exact: -9.31 -> ... -> -17.35 on the bot as it is ($17.35); smaller under B", abs(S["asis"]["max_dd"] - 17.35) < 0.006 and S["B"]["max_dd"] < S["asis"]["max_dd"], (S["asis"]["max_dd"], S["B"]["max_dd"]))
        check("b. still collecting (6 of 30): no leader named, the words say so", f["collecting"] and f["leader"] is None and "Collecting: 6 bets so far" in f["text"], f["text"])
        # ---- c. the same feed: nothing changes; an open bet counts once, when it settles
        before = files(tmp)
        r = run(tmp, feed(old + new, T0 + 700))
        check("c. the same feed again: exit 0, 'no new bets', every file byte-identical", r == 0 and files(tmp) == before)
        opened = bet(9, T0 + 800, 0.98, 5, None)
        r = run(tmp, feed(old + new + [opened], T0 + 900))
        check("c. an open bet (no P&L yet) is not counted and rewrites nothing", r == 0 and files(tmp) == before)
        settled = dict(opened, pnl=0.09)
        r = run(tmp, feed(old + new + [settled], T0 + 1000))
        f2 = load(tmp)
        check("c. once it settles it is counted, once (7 bets, the bot +$0.09 more)", f2["bets"] == 7 and abs(f2["sets"][0]["net"] - (S["asis"]["net"] + 0.09)) < 0.006, f2["sets"][0])
        r = run(tmp, feed(old + new + [settled], T0 + 1100))
        check("c. and not again on the next run", load(tmp)["bets"] == 7)
        # ---- d. unreachable: nothing written, an earlier tally untouched
        before = files(tmp)
        bad = [("a missing file", os.path.join(tmp, "nope.json")), ("junk", put(tmp, "junk.json", {"x": 1})), ("not json", None), ("a dead address", "http://127.0.0.1:9/kalshi.json")]
        rc = []
        for nm, src in bad:
            if src is None:
                src = os.path.join(tmp, "junk.txt")
                open(src, "w").write("<html>nope")
            rc.append(KF.main(["--feed", src, "--out", os.path.join(tmp, "state", "forward.json")]))
        check("d. feed unreachable (missing, junk, not json, a dead address): exit 2 each time and the earlier tally is byte-identical", rc == [2, 2, 2, 2] and files(tmp) == before, rc)
        empty = os.path.join(tmp, "fresh", "forward.json")
        rc = KF.main(["--feed", os.path.join(tmp, "nope.json"), "--out", empty])
        check("d. no earlier tally and no feed: exit 2 and no file is invented", rc == 2 and not os.path.exists(empty) and not os.path.exists(os.path.join(tmp, "fresh")))
        with open(os.path.join(tmp, "state", "forward_state.json"), "w") as fh:
            fh.write("{broken")
        check("d. a broken state file is never guessed at: exit 2 and forward.json untouched", KF.main(["--feed", os.path.join(tmp, "kalshi.json"), "--out", os.path.join(tmp, "state", "forward.json")]) == 2
              and files(tmp)["forward.json"] == before["forward.json"])
        os.remove(os.path.join(tmp, "state", "forward_state.json"))
        check("d. forward.json without its state file is never restarted silently (the frozen start would be lost): exit 2, nothing written",
              KF.main(["--feed", os.path.join(tmp, "kalshi.json"), "--out", os.path.join(tmp, "state", "forward.json")]) == 2 and "forward_state.json" not in files(tmp))
        # ---- e. 30+ bets: a leader; the gap flag
        t2 = os.path.join(tmp, "big")
        os.makedirs(t2)
        run(t2, feed([], T0))
        bets, k = [], 100
        for i in range(31):                                           # 31 new bets: the 93c ones lose, the 96c ones win a little
            px = 0.93 if i % 2 == 0 else 0.96
            bets.append(bet(k + i, T0 + 100 + i * 10, px, 10, -9.31 if px == 0.93 else 0.31))
        run(t2, feed(bets[:25], T0 + 500))
        mid = load(t2)
        run(t2, feed(bets, T0 + 900))
        big = load(t2)
        check("e. under 30 bets: collecting, no leader (25 bets)", mid["bets"] == 25 and mid["collecting"] and mid["leader"] is None)
        check("e. 31 bets: judged (not collecting) and the leader is the set with the best net that beats the bot (A: it skips the losing 93c bets)",
              big["bets"] == 31 and not big["collecting"] and big["leader"] == "A" and "A is " in big["text"] and "ahead of the bot" in big["text"], big["text"])
        check("e. no gap when the windows overlap", big["gaps"] == 0 and not big["flags"]["may_be_incomplete"])
        wave = [bet(500 + i, T0 + 2000 + i, 0.96, 5, 0.1) for i in range(40)]            # a whole window newer than anything seen: some bets were missed
        run(t2, feed(wave, T0 + 3000))
        gap = load(t2)
        check("e. a whole window of 40 newer bets with no overlap: counted, and flagged as maybe incomplete (gaps 1)", gap["gaps"] == 1 and gap["flags"]["may_be_incomplete"] and gap["bets"] == 31 + 40, (gap["gaps"], gap["bets"]))
        # ---- f. the card, sells, junk, determinism
        c = load(t2, "forward_card.json")
        raw = open(os.path.join(t2, "state", "forward_card.json"), "rb").read()
        check("f. forward_card.json follows the Jarvis card contract (v 1, status, <= 3 kpis, <= 3 lines of plain text <= 120, t, open, theme, < 8 KB)",
              c["v"] == 1 and c["status"]["level"] in ("ok", "warn", "bad", "off") and len(c["status"]["label"]) <= 48 and len(c["kpis"]) <= 3 and len(c["lines"]) <= 3
              and all(len(x) <= 120 and not re.search(r"[<>&\n]", x) for x in c["lines"]) and isinstance(c["t"], int) and re.fullmatch(r"#[0-9a-f]{6}", c["theme"]) and len(raw) < 8192
              and all(len(k["label"]) <= 20 and len(str(k["value"])) <= 24 for k in c["kpis"]), c)
        t3 = os.path.join(tmp, "junk")
        os.makedirs(t3)
        run(t3, feed([], T0))
        mess = [bet(1, T0 + 10, 0.96, 10, 0.31), bet(2, T0 + 20, 0.96, 10, 0.5, action="sell"), bet(3, T0 + 30, 1.5, 10, 0.3), bet(4, T0 + 40, 0.96, 0, 0.3),
                bet(5, T0 + 50, 0.96, 10, "x"), bet(6, T0 + 60, 0.96, 10, True), {"t": T0 + 70, "ticker": "X"}, "junk", None]
        run(t3, feed([m for m in mess if isinstance(m, dict)], T0 + 100))
        check("f. sell rows and junk values (bad price, 0 contracts, text / bool P&L, missing fields) are ignored: one real bet counted", load(t3)["bets"] == 1, load(t3)["bets"])
        a1, a2 = os.path.join(tmp, "d1"), os.path.join(tmp, "d2")
        for d in (a1, a2):
            os.makedirs(d)
            run(d, feed(old, T0))
            run(d, feed(old + new, T0 + 700))
        check("f. deterministic: two runs of the same feeds give the same bytes", files(a1) == files(a2) and sha(files(a1)) == sha(files(a2)))
        check("f. the script reads and writes only: no key, no Kalshi address, no network call but the feed's own repo (a source check)",
              not re.search(r"kalshi\.com|trading-api|elections|api_key|KALSHI_|\.env", open(os.path.join(ROOT, "tools", "kalshi_forward.py"), encoding="utf-8").read())
              and KF.FEED_URL == "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json")
        # ---- g. the adversary: bad rows, empty feeds, clocks, duplicate bets
        g = os.path.join(tmp, "adv")
        os.makedirs(g)
        run(g, feed([], T0))
        twin = bet(1, T0 + 100, 0.96, 10, 0.31, ticker="KXSAME")
        split = bet(2, T0 + 100, 0.96, 5, 0.15, ticker="KXSAME")               # same market, same second, same side, different size: another bet
        run(g, feed([twin, dict(twin), split], T0 + 200))
        n_first = load(g)["bets"]
        run(g, feed([twin, dict(twin), split], T0 + 300))
        check("g. duplicate ids: two identical rows are two bets, a same-second row of another size is a third (3 counted), none twice on a rerun",
              n_first == 3 and load(g)["bets"] == 3, (n_first, load(g)["bets"]))
        run(g, feed([twin, dict(twin), dict(twin), split], T0 + 400))
        check("g. a third identical row appearing later is one more bet (4), still never recounting the first two", load(g)["bets"] == 4, load(g)["bets"])
        nan = float("nan")
        rows = [bet(10, T0 + 500, 0.96, 10, nan), bet(11, T0 + 510, 0.96, 10, float("inf")), bet(12, T0 + 520, nan, 10, 0.1), bet(13, T0 + 530, 0.96, nan, 0.1),
                bet(14, T0 + 540, True, 10, 0.1), bet(15, T0 + 550, 0.96, True, 0.1), bet(16, (T0 + 560) * 1000, 0.96, 10, 0.1), bet(17, T0 + 570, -0.5, 10, 0.1),
                bet(18, T0 + 580, 0, 10, 0.1), bet(19, T0 + 590, 0.96, -3, 0.1), bet(20, str(T0 + 600), 0.96, 10, 0.1), bet(21, T0 + 610, 0.96, 10, 0.1)]
        src = os.path.join(g, "nan.json")
        with open(src, "w") as fh:
            json.dump(feed(rows, T0 + 700), fh)                              # Python writes NaN / Infinity as bare tokens, and reads them back
        rc = KF.main(["--feed", src, "--out", os.path.join(g, "state", "forward.json")])
        f = load(g)
        check("g. NaN / Infinity P&L or price, boolean price or size, millisecond or text times, negative or zero prices, negative sizes: all ignored, only the one clean bet is counted (5 total)",
              rc == 0 and f["bets"] == 5 and all(s_["net"] == s_["net"] and abs(s_["net"]) < 1e6 for s_ in f["sets"]), [(s_["id"], s_["net"]) for s_ in f["sets"]])
        g2 = os.path.join(tmp, "adv2")
        os.makedirs(g2)
        run(g2, feed([], T0))
        pending = [bet(30, T0 + 100, 0.96, 10, 0.31)]
        for bal in (None, 0, -5.0, float("nan"), True, "100"):
            fd = feed(pending, T0 + 200)
            fd["balance"] = bal
            run(g2, fd)
        check("g. no usable balance (missing, 0, negative, NaN, boolean, text): nothing counted and the bet is NOT marked seen", load(g2)["bets"] == 0 and not load(g2, "forward_state.json")["seen"])
        run(g2, feed(pending, T0 + 300))
        check("g. the next run with a real balance counts that bet (once)", load(g2)["bets"] == 1)
        for nm, tr in (("a dict", {"x": 1}), ("a string", "oops"), ("None", None), ("a number", 7), ("missing", "MISSING")):
            fd = feed([], T0 + 400)
            if tr == "MISSING":
                fd.pop("trades")
            else:
                fd["trades"] = tr
            rc = run(g2, fd)
            check(f"g. trades is {nm}: no crash, nothing changes", rc == 0 and load(g2)["bets"] == 1, rc)
        check("g. an empty feed ({} with its kind only) on a fresh folder starts a tally at the clock with 0 bets",
              KF.main(["--feed", put(tmp, "empty.json", {"kind": "kalshi"}), "--out", os.path.join(tmp, "e1", "forward.json")], now=T0 + 5) == 0
              and json.load(open(os.path.join(tmp, "e1", "forward.json")))["start_t"] == T0 + 5)
        # clocks: a feed time in the future must not hide every real bet; the start day is the UTC date of the start
        g3 = os.path.join(tmp, "adv3")
        os.makedirs(g3)
        KF.main(["--feed", put(g3, "k.json", feed([], T0 + 10 ** 8)), "--out", os.path.join(g3, "forward.json")], now=T0 + 50)
        check("g. a feed time in the far future: the start is the clock (T0+50), never the feed's", json.load(open(os.path.join(g3, "forward.json")))["start_t"] == T0 + 50)
        late = 1_793_068_200                                                  # 2026-10-27 03:30 UTC = 2026-10-26 23:30 New York
        KF.main(["--feed", put(g3, "k2.json", feed([], late)), "--out", os.path.join(g3, "z", "forward.json")], now=late + 5)
        check("g. time zones: the start day is the UTC date (2026-10-27 for 23:30 New York on the 26th), written once and never recomputed",
              json.load(open(os.path.join(g3, "z", "forward.json")))["start_day"] == "2026-10-27")
        # a forward.json that cannot be read is rewritten from the state; the files are replaced whole (no .tmp left behind)
        with open(os.path.join(g2, "state", "forward.json"), "w") as fh:
            fh.write("{broken")
        run(g2, feed(pending, T0 + 500))
        check("g. an unreadable forward.json is rewritten from the state on the next run; no half-written .tmp file is ever left", load(g2)["bets"] == 1
              and not [f_ for f_ in os.listdir(os.path.join(g2, "state")) if f_.endswith(".tmp")])
        # kalshi_whatif: the same adversary
        from tools import kalshi_whatif as KW
        snap = json.load(open(os.path.join(ROOT, "research", "kalshi", "feed_snapshot_2026-11-04.json"), encoding="utf-8"))
        junk = json.loads(json.dumps(snap))
        junk["buckets"] += [{"lo": nan, "hi": 0.5, "trades": 10, "wins": 5, "losses": 5, "pnl": 1, "staked": 10}, {"lo": 0.9, "hi": 0.95, "trades": 581, "wins": 536, "losses": 45, "pnl": -248.3, "staked": 5343.43},
                            {"lo": 0.1, "hi": 0.2, "trades": "9", "wins": 1, "losses": 1, "pnl": 0, "staked": 5}, {"lo": 0.3, "hi": 0.4, "trades": 10, "wins": 9, "losses": 9, "pnl": 0, "staked": 5},
                            {"lo": 0.4, "hi": 0.5, "trades": 10, "wins": 5, "losses": 5, "pnl": 0, "staked": -5}, "junk", None, {"lo": 0.5, "hi": 0.6}]
        junk["calibration"] = [{"p": "x", "n": "y"}, None, {"p": nan, "n": 5}] + junk["calibration"]
        junk["categories"] += [{"name": "Z", "pnl": -50, "trades": "999"}, {"name": "Y", "pnl": nan, "trades": 99}]
        junk["strategies"] += [{"name": "S", "total_pnl": -50, "trades": "999"}]
        base, bj = KW.build(snap), KW.build(junk)
        check("g. whatif: junk bands (NaN, text, wins+losses > bets, negative stake, a duplicated 90-95c band, strings, None), junk calibration / categories / strategies: ignored, the answer is the clean feed's",
              bj["what_if"]["sets"] == base["what_if"]["sets"] and bj["why"]["text"] == base["why"]["text"], (bj["what_if"]["recommend"], bj["why"]["text"]))
        bad_bal = []
        for bal in (True, -5, 0, nan, "55", None):
            q = dict(snap, balance=bal)
            bad_bal.append((KW.build(q)["what_if"]["enough"], KW.build(q)["what_if"]["sets"]))
        check("g. whatif: a balance that is boolean, negative, 0, NaN, text or missing: 'not enough', no sets, no crash", all(e is False and st_ == [] for e, st_ in bad_bal), bad_bal)
        check("g. whatif: empty feed, None, a list, junk buckets / total_pnl: 'not enough bets', no crash",
              all(not KW.build(x)["what_if"]["enough"] and not KW.build(x)["why"]["enough"] for x in ({}, None, [], {"buckets": "x", "trades": 5}, dict(snap, buckets=None, calibration=None)))
              and not KW.build(dict(snap, total_pnl=nan, stats={"pnl": "x"}))["why"]["enough"])
        tr = KW.typical_stake({"trades": [{"contracts": -5, "price": 0.9}, {"contracts": nan, "price": 0.9}, {"contracts": 10, "price": -1}, {"contracts": 10, "price": 0.5}, "x"]})
        check("g. whatif: the usual bet size ignores negative / NaN / bad rows (a $5.00 bet here)", abs(tr - 5.0) < 1e-9, tr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nkalshi forward: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
