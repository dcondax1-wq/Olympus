#!/usr/bin/env python3
"""KALSHI REWARDS PAPER (owner 2026-11-17: "try kalshi rewards in paper"). PAPER ONLY: GET-only reads of Kalshi's PUBLIC data
(no key, no account), it never places, changes or cancels an order. Stdlib only, Python 3.9+.

What it pretends: on the best few rewarded markets of KXRT / KXPANAMAWEEKLY / KXBABELMANDEBWEEKLY (K5's lead) it keeps one
virtual resting bid of Q contracts on BOTH sides (YES bid and NO bid) at the reward reference price, and every cycle (~60 s):
  reward  pool $/sec x seconds since the last snapshot (capped at 120 s) x my score / (everyone's score + mine), only when both
          sides have Target depth including mine (help.kalshi.com Liquidity Incentive Program: score = size x DF^ticks behind
          the reference, reference = price where depth reaches Target/5).
  fills   CONSERVATIVE queue model: I join the BACK of the queue at my price; taker volume at or through my price first eats
          all depth that was ahead of me (better prices + same price), only the rest fills me, at my price.
  requote if the reference moved, cancel and re-place at the new one (back of the queue again); a filled order is refilled.
  P&L     filled contracts marked at the mid every cycle, settled at $1/$0 when the market has a result; maker fee only on
          series whose fee_type has maker fees (0.0175 x p(1-p) per contract, rounded up per fill).
The honest verdict is rewards - fill losses. The fill model is the weak spot: real fills behind the queue are likely worse.

  python tools/kalshi_rewards_paper.py --loop 360 --gap 60     6 hours, one cycle a minute (network: api.elections.kalshi.com)
  python tools/kalshi_rewards_paper.py --summary               the ledger's table, no network
  python tools/kalshi_rewards_paper.py --selftest              offline checks with a stub API
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "research", "kalshi_edge_K5", "paper", "rewards_paper.json")
K = "https://api.elections.kalshi.com/trade-api/v2"
UA = "kalshi-rewards-paper (read-only)"
SERIES = ["KXRT", "KXPANAMAWEEKLY", "KXBABELMANDEBWEEKLY"]
PER_SERIES = 3          # markets watched per series
DT_CAP = 120.0          # seconds of reward credited per snapshot at most
RESELECT = 3600         # re-pick markets every hour


def T(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def F(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


class Net:
    def __init__(self):
        self.last = 0.0

    def get(self, path, params=None):
        u = K + path + ("?" + urllib.parse.urlencode(params) if params else "")
        for k in range(4):
            w = self.last + 0.15 - time.time()
            if w > 0:
                time.sleep(w)
            self.last = time.time()
            try:
                r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30)
                return json.load(r)
            except Exception as e:  # noqa: BLE001
                code = getattr(e, "code", None)
                if code in (400, 404):
                    return None
                time.sleep(2 * (k + 1))
        return None


# ---------------------------------------------------------------- book maths
def book(ob):
    o = (ob or {}).get("orderbook_fp") or {}
    yes = sorted([(F(a), F(b)) for a, b in (o.get("yes_dollars") or [])], reverse=True)
    no = sorted([(F(a), F(b)) for a, b in (o.get("no_dollars") or [])], reverse=True)
    return yes, no


def ref_price(levels, target):
    cum = 0.0
    for pr, s in levels:
        cum += s
        if cum >= target / 5 - 1e-9:
            return pr
    return None


def score(levels, ref, df):
    if ref is None:
        return 0.0
    return sum(s * (1.0 if pr >= ref - 1e-9 else df ** round((ref - pr) * 100)) for pr, s in levels)


def ahead(levels, p):
    """depth at prices >= p (ahead of a new order at p)."""
    return sum(s for pr, s in levels if pr >= p - 1e-9)


def maker_fee(p, n, fee_type):
    if "maker" not in str(fee_type or ""):
        return 0.0
    return math.ceil(0.0175 * n * p * (1 - p) * 100 - 1e-9) / 100.0


# ---------------------------------------------------------------- ledger
def blank():
    return {"v": 1, "kind": "kalshi_rewards_paper", "paper_only": True, "started": None, "updated": None,
            "series": SERIES, "picked_at": 0, "markets": {}, "totals": {}}


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("kind") == "kalshi_rewards_paper":
            return d
    except (OSError, ValueError):
        pass
    return blank()


def save(path, d):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, path)


def side_new():
    return {"p": None, "q": 0.0, "queue": 0.0, "pos": 0.0, "cost": 0.0, "fees": 0.0, "fills": 0}


def pick(net, led, now):
    """keep markets with positions; add the biggest-pool rewarded markets per series up to PER_SERIES."""
    for s in SERIES:
        d = net.get("/incentive_programs", {"status": "active", "type": "liquidity", "limit": 1000, "series_ticker": s}) or {}
        ps = [x for x in d.get("incentive_programs", []) if x.get("series_ticker") == s and x.get("incentive_type") == "liquidity"
              and T(x["start_date"]) <= now < T(x["end_date"])]
        ps.sort(key=lambda x: -x["period_reward"] / max(T(x["end_date"]) - T(x["start_date"]), 1))
        have = [t for t, m in led["markets"].items() if m["s"] == s and m.get("active")]
        for x in ps:
            if len(have) >= PER_SERIES:
                break
            t = x["market_ticker"]
            m = led["markets"].get(t)
            if m and m.get("active"):
                continue
            led["markets"][t] = m = m or {"s": s, "t": t, "reward": 0.0, "snaps": 0, "valid": 0, "secs": 0.0,
                                          "yes": side_new(), "no": side_new(), "result": "", "settled": None, "mark": 0.0}
            m["active"] = True
            have.append(t)
        for t in list(led["markets"]):
            m = led["markets"][t]
            if m["s"] == s and m.get("active"):
                prog = next((x for x in ps if x["market_ticker"] == t), None)
                if prog:
                    m["prog"] = {"usd_sec": prog["period_reward"] / 1e4 / max(T(prog["end_date"]) - T(prog["start_date"]), 1),
                                 "target": F(prog["target_size_fp"]), "df": prog["discount_factor_bps"] / 1e4, "end": prog["end_date"]}
                elif not m["yes"]["pos"] and not m["no"]["pos"]:
                    m["active"] = False      # program gone and flat: stop watching
                else:
                    m.pop("prog", None)      # program gone: keep only to settle the position
    led["picked_at"] = now


def fills_from(trades, side, p, since_id_seen):
    """taker volume that hits resting `side` bids at or through price p. side 'yes': taker sold YES (taker_side 'no'),
    trade yes_price <= p. side 'no': taker bought YES (taker_side 'yes'), trade no_price <= p."""
    v = 0.0
    for tr in trades:
        if tr["trade_id"] in since_id_seen:
            continue
        if side == "yes" and tr.get("taker_side") == "no" and F(tr.get("yes_price_dollars"), 9) <= p + 1e-9:
            v += F(tr.get("count_fp"))
        if side == "no" and tr.get("taker_side") == "yes" and F(tr.get("no_price_dollars"), 9) <= p + 1e-9:
            v += F(tr.get("count_fp"))
    return v


def cycle(net, led, now):
    if not led.get("started"):
        led["started"] = dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(timespec="seconds")
    if now - led.get("picked_at", 0) > RESELECT or not any(m.get("active") for m in led["markets"].values()):
        pick(net, led, now)
    for t, m in led["markets"].items():
        if not m.get("active") or m.get("settled") is not None:
            continue
        mk = (net.get("/markets/" + t) or {}).get("market") or {}
        fee_type = m.get("fee_type")
        if fee_type is None:
            sr = (net.get("/series/" + m["s"]) or {}).get("series") or {}
            fee_type = m["fee_type"] = sr.get("fee_type", "")
        # 1) fills since the last cycle (trades newer than last_ts)
        last_ts = m.get("last_ts") or now
        tr = (net.get("/markets/trades", {"ticker": t, "limit": 1000, "min_ts": int(last_ts) - 1}) or {}).get("trades", [])
        seen = set(m.get("seen", []))
        for sd in ("yes", "no"):
            o = m[sd]
            if o["p"] is None or o["q"] <= 0:
                continue
            v = fills_from(tr, sd, o["p"], seen)
            eat = min(v, o["queue"])
            o["queue"] -= eat
            got = min(v - eat, o["q"])
            if got > 1e-9:
                o["q"] -= got
                o["pos"] += got
                o["cost"] += got * o["p"]
                f = maker_fee(o["p"], got, fee_type)
                o["fees"] += f
                o["fills"] += 1
        m["seen"] = [x["trade_id"] for x in tr][:300]
        m["last_ts"] = now
        # 2) settle
        res = mk.get("result") or ""
        if res in ("yes", "no"):
            pay = m["yes"]["pos"] * (res == "yes") + m["no"]["pos"] * (res == "no")
            m["settled"] = pay - m["yes"]["cost"] - m["no"]["cost"] - m["yes"]["fees"] - m["no"]["fees"]
            m["result"] = res
            m["active"] = False
            continue
        if mk.get("status") not in (None, "active", "open"):
            for sd in ("yes", "no"):
                m[sd]["q"] = 0.0
        ob = net.get("/markets/%s/orderbook" % t)
        yes, no = book(ob)
        if yes and no:
            mid = (yes[0][0] + (1 - no[0][0])) / 2
            m["mid"] = mid
            m["mark"] = (m["yes"]["pos"] * mid + m["no"]["pos"] * (1 - mid) - m["yes"]["cost"] - m["no"]["cost"]
                         - m["yes"]["fees"] - m["no"]["fees"])
        prog = m.get("prog")
        if not prog or not yes or not no or mk.get("status") not in (None, "active", "open"):
            m["prev_t"] = now
            continue
        tgt, df, Q = prog["target"], prog["df"], prog["target"] / 5
        # 3) requote: keep my order if the reference did not move, else back of the queue at the new reference
        for sd, lv in (("yes", yes), ("no", no)):
            o = m[sd]
            r = ref_price(lv, tgt)
            if r is None:
                o["p"], o["q"], o["queue"] = None, 0.0, 0.0
                continue
            if o["p"] is None or abs(o["p"] - r) > 1e-9 or o["q"] <= 1e-9:
                o["p"], o["q"], o["queue"] = r, Q, ahead(lv, r)
        # 4) reward for the time since the last snapshot
        prev = m.get("prev_t")
        m["prev_t"] = now
        if prev is None:
            continue
        secs = min(max(now - prev, 0.0), DT_CAP)
        my = {}
        tot = 0.0
        valid = True
        for sd, lv in (("yes", yes), ("no", no)):
            o = m[sd]
            mine = [(o["p"], o["q"])] if o["p"] is not None and o["q"] > 0 else []
            allv = sorted(lv + mine, reverse=True)
            if sum(s for _, s in allv) < tgt:
                valid = False
            r = ref_price(allv, tgt)
            tot += score(allv, r, df)
            my[sd] = score(mine, r, df) if mine else 0.0
        m["snaps"] += 1
        m["secs"] += secs
        if valid and tot > 0:
            m["valid"] += 1
            m["reward"] += prog["usd_sec"] * secs * (my["yes"] + my["no"]) / tot
    tally(led, now)


def tally(led, now):
    ms = list(led["markets"].values())
    rew = sum(m["reward"] for m in ms)
    pnl = sum(m["settled"] if m.get("settled") is not None else m.get("mark", 0.0) for m in ms)
    hrs = sum(m["secs"] for m in ms) / 3600.0
    cap = sum((m["yes"]["p"] or 0) * m["yes"]["q"] + (m["no"]["p"] or 0) * m["no"]["q"] + m["yes"]["cost"] + m["no"]["cost"]
              for m in ms if m.get("active"))
    by = {}
    for s in SERIES:
        sm = [m for m in ms if m["s"] == s]
        by[s] = {"markets": len(sm), "reward": round(sum(m["reward"] for m in sm), 2),
                 "fills_pnl": round(sum(m["settled"] if m.get("settled") is not None else m.get("mark", 0.0) for m in sm), 2),
                 "valid_pct": round(100 * sum(m["valid"] for m in sm) / max(sum(m["snaps"] for m in sm), 1))}
    led["totals"] = {"reward": round(rew, 2), "fills_pnl": round(pnl, 2), "net": round(rew + pnl, 2),
                     "market_hours": round(hrs, 1), "capital_now": round(cap, 0),
                     "net_per_market_day": round((rew + pnl) / max(hrs / 24, 1e-9), 2) if hrs else None, "by_series": by}
    led["updated"] = dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(timespec="seconds")


def summary(led):
    t = led.get("totals") or {}
    print("Kalshi rewards PAPER  started %s  updated %s" % (led.get("started"), led.get("updated")))
    print("%-22s %4s %9s %10s %7s" % ("series", "mkts", "reward$", "fills P&L$", "valid%"))
    for s, b in (t.get("by_series") or {}).items():
        print("%-22s %4d %9.2f %10.2f %6d%%" % (s, b["markets"], b["reward"], b["fills_pnl"], b["valid_pct"]))
    print("NET $%.2f over %.1f market-hours (%s $ per market-day), capital now ~$%s" % (
        t.get("net", 0), t.get("market_hours", 0), t.get("net_per_market_day"), t.get("capital_now")))


# ---------------------------------------------------------------- selftest
class Stub:
    def __init__(self):
        self.trades = []
        self.res = ""

    def get(self, path, params=None):
        if path == "/incentive_programs":
            s = params["series_ticker"]
            return {"incentive_programs": [{"series_ticker": s, "incentive_type": "liquidity", "market_ticker": s + "-A",
                    "period_reward": 1000000, "start_date": "2033-05-17T15:33:20Z", "end_date": "2033-05-18T15:33:20Z",
                    "target_size_fp": "1000", "discount_factor_bps": 5000}]}
        if path.startswith("/series/"):
            return {"series": {"fee_type": "quadratic"}}
        if path == "/markets/trades":
            return {"trades": self.trades}
        if path.endswith("/orderbook"):
            return {"orderbook_fp": {"yes_dollars": [["0.39", "1000"], ["0.38", "500"]], "no_dollars": [["0.60", "1000"], ["0.59", "500"]]}}
        if path.startswith("/markets/"):
            return {"market": {"status": "active", "result": self.res}}
        return None


def selftest():
    ok = 0
    assert ref_price([(0.39, 150), (0.38, 100)], 1000) == 0.38; ok += 1
    assert abs(score([(0.39, 200), (0.37, 100)], 0.39, 0.5) - 225) < 1e-9; ok += 1
    assert maker_fee(0.5, 100, "quadratic") == 0.0 and maker_fee(0.5, 100, "quadratic_with_maker_fees") == 0.44; ok += 1
    st, led = Stub(), blank()
    cycle(st, led, 2e9)
    m = led["markets"]["KXRT-A"]
    assert m["yes"]["p"] == 0.39 and m["yes"]["queue"] == 1000 and m["reward"] == 0; ok += 1
    cycle(st, led, 2e9 + 60)
    # my score 200 per side, everyone 1000+0.5*500 + 200 = 1450 per side -> share 200/1450; pool 100$/day
    exp = 100 / 86400 * 60 * 400 / 2900
    assert abs(m["reward"] - exp) < 1e-9, m["reward"]; ok += 1
    # a taker sells 1100 YES at 0.39: 1000 queue ahead, 100 fill me
    st.trades = [{"trade_id": "a", "taker_side": "no", "yes_price_dollars": "0.39", "no_price_dollars": "0.61", "count_fp": "1100"}]
    cycle(st, led, 2e9 + 120)
    assert abs(m["yes"]["pos"] - 100) < 1e-9 and m["yes"]["queue"] == 0; ok += 1
    cycle(st, led, 2e9 + 180)               # same trade id again: no double fill
    assert abs(m["yes"]["pos"] - 100) < 1e-9; ok += 1
    st.trades, st.res = [], "no"
    cycle(st, led, 2e9 + 240)
    assert abs(m["settled"] - (-39.0)) < 1e-9 and not m["active"]; ok += 1
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    for bad in ("/portfolio/", "KALSHI-ACCESS", "data="):
        assert src.count(bad) == 1, bad      # only this list mentions it
    ok += 1
    print("kalshi_rewards_paper selftest: %d/9 ALL PASS" % ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--loop", type=int, default=1)
    ap.add_argument("--gap", type=float, default=60.0)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    led = load(a.out)
    if a.summary:
        return summary(led)
    net = Net()
    for k in range(a.loop):
        t0 = time.time()
        try:
            cycle(net, led, t0)
            save(a.out, led)
        except Exception as e:  # noqa: BLE001  (one bad cycle never kills the run)
            print("cycle error:", repr(e), file=sys.stderr, flush=True)
        if k < a.loop - 1:
            time.sleep(max(1.0, a.gap - (time.time() - t0)))
    summary(led)


if __name__ == "__main__":
    main()
