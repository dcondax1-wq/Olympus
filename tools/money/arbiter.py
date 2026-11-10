#!/usr/bin/env python3
"""ARBITER (money machine #5, 2026-11-10): a spread and funding finder. PAPER ONLY, it never trades, never asks for a key.

It looks at free PUBLIC data and lists market-neutral "carry" ideas with an honest net APR after fees, slippage and the time the money is locked:
  funding  : hold the coin and short its perpetual, collect the funding rate (Binance, Bybit public endpoints)
  peg      : a stablecoin trading below (or above) one dollar (CoinGecko public price)
  venues   : the same yes/no event priced differently on two prediction venues (Polymarket + Kalshi public lists)

    python tools/money/arbiter.py --out <dir> [--fixture] [--capital 1000]     writes <dir>/arbiter.json
    python tools/money/arbiter.py --selftest

Works offline from tools/money/arbiter_fixture.json (--fixture, and also when every live call fails). Live calls are stdlib, polite, 10 s timeout, optional, fail soft.
Output contract (docs/NIGHT_BRIEF.md): {"v":1,"id":"arbiter","asof","mode":"paper","status":"ok|stale|sample","headline":{"text","usd_month"},"items":[{"title","detail","usd","score","risk",...extra}],"notes":[...]}
usd = estimated net $ a month on `capital` (default $1,000) if the idea held as costed; score 0-100 = how good it looks after risk (higher is better); risk low|med|high.
Every number is an ESTIMATE. Read the "why" and "warning" of each item before anything else.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "arbiter_fixture.json")

# ---- assumptions, all printed in the notes so nothing is hidden ----
CAPITAL = 1000.0
MARGIN = 0.20            # perp margin kept next to the coin: $1,000 of position needs $1,200 deployed
HOLD_FUNDING = 30        # days we assume the funding position is held
FUNDING_KEEP = 0.60      # funding rates mean-revert: count only 60% of today's rate
FEE_SPOT, FEE_PERP = 0.0010, 0.0005     # taker fee per side
SLIP_LEG = 0.0004        # slippage per leg per side (4 legs: buy spot, short perp, sell spot, close perp)
PEG_FEE, PEG_SLIP, PEG_HOLD = 0.0010, 0.0005, 2
VENUE_SLIP = 0.01        # one cent per leg on a prediction market
BENCH_APR = 4.0          # a plain savings rate, the bar every idea must beat (assumption)
HURDLE_PREMIUM = {"low": 1.0, "med": 4.0, "high": 10.0}
UA = "arbiter-paper/1 (read-only public data)"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def num(v, d=None):
    try:
        f = float(v)
        return f if f == f and abs(f) != float("inf") else d
    except (TypeError, ValueError):
        return d


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------------------------- scoring
def risk_score(kind, net_apr, hold_days, venue_big=True):
    base = {"funding": 25, "peg": 40, "venues": 55}[kind]
    r = base + (0 if venue_big else 10) + min(25.0, max(0.0, net_apr) / 4.0) + min(15.0, hold_days / 10.0)
    return int(clamp(round(r), 0, 100))


def risk_band(rs):
    return "low" if rs < 35 else "med" if rs < 60 else "high"


def finish_item(kind, title, detail, gain_pct, cost_pct, hold_days, capital, why, warning, venue_big=True, extra=None):
    """gain_pct / cost_pct are % of the capital deployed over the whole hold. net_apr = (gain - cost) over the hold, scaled to a year."""
    hold_days = max(1.0, hold_days)
    net_apr = (gain_pct - cost_pct) * 365.0 / hold_days
    rs = risk_score(kind, net_apr, hold_days, venue_big)
    band = risk_band(rs)
    net_month = (gain_pct - cost_pct) / 100.0 * capital * 30.0 / hold_days
    score = int(clamp(round(clamp(net_apr, 0, 40) * 1.5 + (100 - rs) * 0.4), 0, 100))
    it = {"title": title, "detail": detail, "usd": round(net_month, 2), "score": score, "risk": band,
          "kind": kind, "gross_apr": round(gain_pct * 365.0 / hold_days, 2), "cost_pct": round(cost_pct, 3), "gain_pct": round(gain_pct, 3),
          "net_apr": round(net_apr, 2), "hurdle_apr": round(BENCH_APR + HURDLE_PREMIUM[band], 1), "hold_days": round(hold_days, 1),
          "capital_usd": round(capital, 2), "gain_usd": round(gain_pct / 100.0 * capital, 2), "cost_usd": round(cost_pct / 100.0 * capital, 2),
          "net_usd_per_1000_year": round(net_apr * 10.0, 2), "risk_score": rs, "exposed_usd": round(capital, 2), "why": why, "warning": warning}
    if extra:
        it.update(extra)
    return it


# ---------------------------------------------------------------------------------------------- the three idea makers
def funding_item(p, capital=CAPITAL):
    r = num(p.get("funding"))
    iv = num(p.get("interval_h"), 8.0)
    if r is None or not iv or iv <= 0 or r <= 0:
        return None          # only the positive side (long coin + short perp) needs no borrowing
    ann = r * (24.0 / iv) * 365.0 * 100.0                       # % a year on the position
    kept = ann * FUNDING_KEEP
    gain_pos = kept * HOLD_FUNDING / 365.0                        # % of the position over the hold
    cost_pos = (2 * FEE_SPOT + 2 * FEE_PERP + 4 * SLIP_LEG) * 100.0
    dep = 1.0 + MARGIN                                            # $ deployed per $ of position
    mark, index = num(p.get("mark")), num(p.get("index"))
    basis = ((mark - index) / index * 100.0) if mark and index else None
    sym, ex = str(p.get("symbol", "?")), str(p.get("exchange", "?"))
    coin = re.sub(r"(USDT|USD|PERP)$", "", sym) or sym
    detail = (f"Pays {r * 100:.4f}% every {iv:g} hours, about {ann:.1f}% a year before costs. I count {int(FUNDING_KEEP * 100)}% of it because rates fall back. "
              f"Fees and slippage {cost_pos:.2f}% of the position.") + (f" Price gap to spot now {basis:+.2f}%." if basis is not None else "")
    return finish_item(
        "funding", f"Hold {coin}, short its perpetual ({ex})", detail, gain_pos / dep, cost_pos / dep, HOLD_FUNDING, capital,
        "Everyone sees the same rate: more money piles in, the rate falls, or it turns negative and you pay instead. The profit is also eaten by fees every time you open and close.",
        "Your money sits on an exchange, not in your own wallet. If it freezes, is hacked or fails, you can lose all of it. A fast price spike can liquidate the short before the coin covers it.",
        venue_big=ex.lower() in ("binance", "bybit", "okx"),
        extra={"exchange": ex, "symbol": sym, "funding_8h_pct": round(r * (8.0 / iv) * 100.0, 4), "basis_pct": None if basis is None else round(basis, 3)})


def peg_item(s, capital=CAPITAL):
    px = num(s.get("price_usd"))
    sym = str(s.get("symbol", "?"))
    if px is None or px <= 0:
        return None
    gap = abs(1.0 - px) * 100.0
    below = px < 1.0
    if gap < 0.02:
        return None
    cost = (PEG_FEE + PEG_SLIP) * 100.0
    verb = "buy below one dollar, redeem at one dollar" if below else "mint at one dollar, sell above it"
    return finish_item(
        "peg", f"{sym} peg gap: {verb}", f"{sym} trades at ${px:.4f}, a {gap:.2f}% gap to $1.00. Redeeming takes about {PEG_HOLD} days; fee and slippage {cost:.2f}%.",
        gap, cost, PEG_HOLD, capital,
        "Big traders close peg gaps within minutes, and redemption usually needs an account, a minimum size and KYC that a small holder does not have. If you cannot redeem you just hold the coin.",
        "A stablecoin that is off its peg may be falling for a real reason. In a true depeg the loss can be many times the gap. Money is locked while you wait to redeem.",
        extra={"symbol": sym, "price_usd": round(px, 5), "gap_pct": round(gap, 3), "direction": "redeem" if below else "mint"})


STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "will", "be", "by", "for", "and", "or", "is", "are", "before", "after", "with", "than", "this", "that", "who", "what", "does", "do"}


def toks(t):
    return {w for w in re.findall(r"[a-z0-9]+", str(t).lower()) if w not in STOP}


def similar(a, b):
    x, y = toks(a), toks(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def venue_fee(venue, p):
    """Fee per contract in dollars at price p: Kalshi charges about 0.07 x p x (1-p); Polymarket charges nothing on most markets."""
    return 0.07 * p * (1.0 - p) if str(venue).lower().startswith("kalshi") else 0.0


def venue_items(a_list, b_list, capital=CAPITAL, min_sim=0.6):
    out = []
    for A in a_list or []:
        best = None
        for B in b_list or []:
            sim = similar(A.get("title"), B.get("title"))
            if sim >= min_sim and (best is None or sim > best[0]):
                best = (sim, B)
        if not best:
            continue
        sim, B = best
        pa = {k: num(A.get(k)) for k in ("yes_bid", "yes_ask")}
        pb = {k: num(B.get(k)) for k in ("yes_bid", "yes_ask")}
        if None in pa.values() or None in pb.values():
            continue
        # buy Yes on one venue at its ask, buy No on the other (= 1 - its yes bid): the pair pays exactly $1 if both are the same event
        options = [(pb["yes_bid"] - pa["yes_ask"], A, B, pa["yes_ask"], pb["yes_bid"]), (pa["yes_bid"] - pb["yes_ask"], B, A, pb["yes_ask"], pa["yes_bid"])]
        prof, buy, sell, ybuy, ysell = max(options, key=lambda o: o[0])
        if prof <= 0:
            continue
        pair_cost = ybuy + (1.0 - ysell)
        fees = venue_fee(buy.get("venue"), ybuy) + venue_fee(sell.get("venue"), 1.0 - ysell) + 2 * VENUE_SLIP
        days = max(1.0, min(num(A.get("close_days"), 30.0), num(B.get("close_days"), 30.0)))
        out.append(finish_item(
            "venues", f"Same event, two prices: {str(A.get('title'))[:70]}",
            f"Yes costs {ybuy * 100:.0f} cents on {buy.get('venue')} and sells at {ysell * 100:.0f} cents on {sell.get('venue')}: a {prof * 100:.0f}-cent gap on a {pair_cost * 100:.0f}-cent pair. Resolves in about {days:.0f} days.",
            prof / pair_cost * 100.0, fees / pair_cost * 100.0, days, capital,
            "These gaps are usually not free money: the two venues often word the question differently (dates, sources, tie rules), so one leg can win and the other lose. Thin books also mean the price you see is gone when you click.",
            "Money is locked on two venues until the event resolves. If the rules differ you can lose the whole pair. Deposits and withdrawals have their own costs and limits.",
            venue_big=False, extra={"match": round(sim, 2), "buy_on": buy.get("venue"), "other_on": sell.get("venue")}))
    return out


# ---------------------------------------------------------------------------------------------- the whole scan
def compute(raw, capital=CAPITAL):
    """raw = {"perps":[{exchange,symbol,funding,interval_h,mark,index}], "stables":[{symbol,price_usd}], "venues":{"a":[...],"b":[...]}} -> (items, n_checked)."""
    raw = raw if isinstance(raw, dict) else {}
    cap = clamp(num(capital, CAPITAL), 100, 1e6)
    cand = []
    for p in raw.get("perps") or []:
        if isinstance(p, dict):
            cand.append(funding_item(p, cap))
    for s in raw.get("stables") or []:
        if isinstance(s, dict):
            cand.append(peg_item(s, cap))
    v = raw.get("venues") if isinstance(raw.get("venues"), dict) else {}
    cand.extend(venue_items([x for x in v.get("a") or [] if isinstance(x, dict)], [x for x in v.get("b") or [] if isinstance(x, dict)], cap))
    cand = [c for c in cand if c]
    good = sorted((c for c in cand if c["net_apr"] > 0), key=lambda c: (-c["score"], -c["net_apr"]))
    return good[:10], len(cand)


def headline(items, checked, status):
    tag = " (sample data)" if status == "sample" else ""
    if not items:
        return {"text": f"Nothing beats its costs right now{tag}. Checked {checked} ideas on paper.", "usd_month": None}
    b = max(items, key=lambda c: c["usd"])
    return {"text": f"Best paper idea{tag}: {b['title']}, about {b['net_apr']:.0f}% a year after costs (estimate), about ${b['usd']:.0f} a month on ${b['capital_usd']:,.0f}. Risk {b['risk']}.", "usd_month": b["usd"]}


def build(raw, status, capital=CAPITAL, extra_notes=(), asof=None):
    items, checked = compute(raw, capital)
    notes = list(extra_notes) + [
        f"Paper only. ARBITER never trades and never asks for a key. Every number is an estimate on ${capital:,.0f}.",
        f"Assumptions: funding positions held {HOLD_FUNDING} days, {int(FUNDING_KEEP * 100)}% of today's funding rate counted, {MARGIN * 100:.0f}% margin kept beside the coin (so $1,000 of position ties up ${1000 * (1 + MARGIN):,.0f}), taker fees {FEE_SPOT * 100:.2f}% spot and {FEE_PERP * 100:.2f}% perp per side, slippage {SLIP_LEG * 100:.2f}% per leg.",
        f"The bar to beat: a plain {BENCH_APR:.0f}% savings rate plus a risk allowance (+1 low, +4 medium, +10 high points).",
        f"{checked} ideas checked, {len(items)} beat their costs." if checked else "No ideas could be checked.",
        "Carry that looks easy is usually paid for by a risk you cannot see in the number: exchange failure, a depeg, or two venues that mean different things.",
    ]
    out = {"v": 1, "id": "arbiter", "asof": asof or now_iso(), "mode": "paper", "status": status, "headline": headline(items, checked, status), "items": items, "notes": notes}
    if status == "sample":
        out["demo"] = True
        out["note"] = "EXAMPLE numbers, not real: a bundled sample shown when the live feeds cannot be reached."
    return out


# ---------------------------------------------------------------------------------------------- live fetch (optional, fails soft)
def get_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:     # noqa: S310  (public https endpoints only)
        return json.loads(r.read().decode("utf-8", "replace"))


def live_raw(fail):
    raw = {"perps": [], "stables": [], "venues": {"a": [], "b": []}}
    try:
        for r in get_json("https://fapi.binance.com/fapi/v1/premiumIndex"):
            if str(r.get("symbol", "")).endswith("USDT"):
                raw["perps"].append({"exchange": "Binance", "symbol": r["symbol"], "funding": r.get("lastFundingRate"), "interval_h": 8, "mark": r.get("markPrice"), "index": r.get("indexPrice")})
    except Exception as e:  # noqa: BLE001
        fail.append(f"Binance funding not reachable ({type(e).__name__})")
    try:
        for r in get_json("https://api.bybit.com/v5/market/tickers?category=linear")["result"]["list"]:
            if str(r.get("symbol", "")).endswith("USDT"):
                raw["perps"].append({"exchange": "Bybit", "symbol": r["symbol"], "funding": r.get("fundingRate"), "interval_h": num(r.get("fundingIntervalHour"), 8), "mark": r.get("markPrice"), "index": r.get("indexPrice")})
    except Exception as e:  # noqa: BLE001
        fail.append(f"Bybit funding not reachable ({type(e).__name__})")
    try:
        ids = {"tether": "USDT", "usd-coin": "USDC", "dai": "DAI", "ethena-usde": "USDe", "first-digital-usd": "FDUSD", "paypal-usd": "PYUSD"}
        d = get_json("https://api.coingecko.com/api/v3/simple/price?vs_currencies=usd&ids=" + ",".join(ids))
        raw["stables"] = [{"symbol": s, "price_usd": (d.get(i) or {}).get("usd")} for i, s in ids.items()]
    except Exception as e:  # noqa: BLE001
        fail.append(f"Stablecoin prices not reachable ({type(e).__name__})")
    try:
        for m in get_json("https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=200&order=volume24hr&ascending=false"):
            pr = json.loads(m["outcomePrices"]) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices")
            y = num(pr[0]) if pr else None
            bid, ask = num(m.get("bestBid"), y), num(m.get("bestAsk"), y)
            end = str(m.get("endDate", ""))[:10]
            days = max(1.0, (dt.date.fromisoformat(end) - dt.date.today()).days) if end else 30.0
            if y is not None:
                raw["venues"]["a"].append({"venue": "Polymarket", "title": m.get("question"), "yes_bid": bid, "yes_ask": ask, "close_days": days})
    except Exception as e:  # noqa: BLE001
        fail.append(f"Polymarket list not reachable ({type(e).__name__})")
    try:
        for m in get_json("https://api.elections.kalshi.com/trade-api/v2/markets?status=open&limit=200").get("markets", []):
            bid, ask = num(m.get("yes_bid")), num(m.get("yes_ask"))
            if bid is None or ask is None:
                continue
            bid, ask = (bid / 100.0, ask / 100.0) if max(bid, ask) > 1 else (bid, ask)
            ct = str(m.get("close_time", ""))[:10]
            days = max(1.0, (dt.date.fromisoformat(ct) - dt.date.today()).days) if ct else 30.0
            raw["venues"]["b"].append({"venue": "Kalshi", "title": m.get("title"), "yes_bid": bid, "yes_ask": ask, "close_days": days})
    except Exception as e:  # noqa: BLE001
        fail.append(f"Kalshi list not reachable ({type(e).__name__})")
    return raw


def load_fixture(path=FIXTURE):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def run(use_fixture=False, capital=CAPITAL):
    fx = load_fixture()
    if use_fixture:
        return build(fx, "sample", capital, ["Using the bundled sample (--fixture)."], asof=fx.get("asof"))
    fail: list = []
    raw = live_raw(fail)
    if not raw["perps"] and not any(s.get("price_usd") for s in raw["stables"]) and not raw["venues"]["a"]:
        return build(fx, "sample", capital, ["Live feeds were not reachable, so this is the bundled sample: " + "; ".join(fail)], asof=fx.get("asof"))
    return build(raw, "ok", capital, [("Some feeds were skipped: " + "; ".join(fail)) if fail else "All live feeds answered."])


# ---------------------------------------------------------------------------------------------- contract check + selftest
def validate(o):
    errs = []
    if not isinstance(o, dict) or o.get("v") != 1 or o.get("id") != "arbiter" or o.get("mode") != "paper":
        errs.append("header")
    if o.get("status") not in ("ok", "stale", "sample"):
        errs.append("status")
    h = o.get("headline") or {}
    if not isinstance(h.get("text"), str) or not (h.get("usd_month") is None or isinstance(h.get("usd_month"), (int, float))):
        errs.append("headline")
    for i, it in enumerate(o.get("items") or []):
        if not all(k in it for k in ("title", "detail", "usd", "score", "risk")) or it["risk"] not in ("low", "med", "high") or not 0 <= it["score"] <= 100:
            errs.append(f"item {i}")
    if not isinstance(o.get("notes"), list):
        errs.append("notes")
    return errs


def selftest():
    ok = [0, 0]

    def chk(name, cond, info=""):
        ok[0 if cond else 1] += 1
        print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"))
    it = funding_item({"exchange": "Binance", "symbol": "SOLUSDT", "funding": 0.0005, "interval_h": 8, "mark": 150.3, "index": 150.0})
    chk("funding 0.05%/8h: 54.75% a year, 60% kept, 0.46% costs, 20% margin -> about 22.7% net APR", abs(it["net_apr"] - 22.7) < 0.1 and abs(it["cost_pct"] - 0.383) < 0.001, it)
    chk("funding: $ a month on $1,000 = (gain - cost) on the capital over a 30-day hold", abs(it["usd"] - (it["gain_usd"] - it["cost_usd"])) < 0.02, it["usd"])
    low = funding_item({"exchange": "Binance", "symbol": "BTCUSDT", "funding": 0.0001, "interval_h": 8})
    chk("the normal 0.01% funding does NOT beat the costs on a 30-day hold (an honest, boring answer)", low["net_apr"] < 2, low["net_apr"])
    chk("negative or junk funding makes no idea (no borrowing side)", funding_item({"funding": -0.001}) is None and funding_item({"funding": "x"}) is None and funding_item({}) is None)
    h4 = funding_item({"exchange": "Bybit", "symbol": "ABCUSDT", "funding": 0.0002, "interval_h": 4})
    h8 = funding_item({"exchange": "Bybit", "symbol": "ABCUSDT", "funding": 0.0002, "interval_h": 8})
    chk("a 4-hour funding interval pays twice as often as an 8-hour one", abs(h4["gross_apr"] - 2 * h8["gross_apr"]) < 0.01, (h4["gross_apr"], h8["gross_apr"]))
    pg = peg_item({"symbol": "USDX", "price_usd": 0.995})
    chk("peg 0.5% gap, 2 days, 0.15% costs: 0.35% over 2 days = about 64% a year, never rated low risk", abs(pg["net_apr"] - 63.9) < 0.5 and pg["risk"] in ("med", "high") and pg["direction"] == "redeem", pg)
    chk("a peg gap under 0.02% is ignored; junk price ignored", peg_item({"symbol": "USDC", "price_usd": 1.0001}) is None and peg_item({"symbol": "Q", "price_usd": "x"}) is None)
    A = [{"venue": "Polymarket", "title": "Will the Fed cut rates in December 2026?", "yes_bid": 0.58, "yes_ask": 0.60, "close_days": 40}]
    B = [{"venue": "Kalshi", "title": "Fed cut rates in December 2026", "yes_bid": 0.68, "yes_ask": 0.70, "close_days": 40}, {"venue": "Kalshi", "title": "Snow in Denver", "yes_bid": 0.1, "yes_ask": 0.2, "close_days": 5}]
    vs = venue_items(A, B)
    chk("two venues, same event: matched by words; Yes bought at 60, sold at 68 -> an 8-cent gap, fees and slippage taken off", len(vs) == 1 and "8-cent" in vs[0]["detail"] and vs[0]["net_apr"] > 0 and vs[0]["gain_pct"] > vs[0]["cost_pct"], vs)
    chk("a different event is never matched; no gap -> no idea", venue_items(A, [B[1]]) == [] and venue_items(A, [{"venue": "Kalshi", "title": B[0]["title"], "yes_bid": 0.59, "yes_ask": 0.61, "close_days": 9}]) == [])
    chk("junk input never raises", compute(None)[0] == [] and compute({"perps": [None, 5, {"funding": "x"}], "stables": ["a"], "venues": 3})[0] == [])
    fx = load_fixture()
    out = build(fx, "sample", asof=fx.get("asof"))
    chk("the bundled sample builds a valid contract file (paper, sample, demo flag)", not validate(out) and out["status"] == "sample" and out["demo"] is True and "not real" in out["note"], validate(out))
    kinds = {i["kind"] for i in out["items"]}
    chk("the sample shows all three kinds, best first; every item has a why, a warning and money exposed", kinds == {"funding", "peg", "venues"} and [i["score"] for i in out["items"]] == sorted((i["score"] for i in out["items"]), reverse=True) and all(i["why"] and i["warning"] and i["exposed_usd"] > 0 for i in out["items"]), kinds)
    chk("the headline names the best idea in plain words and says estimate", "estimate" in out["headline"]["text"] and out["headline"]["usd_month"] > 0, out["headline"])
    c2, c1 = compute(fx, 2000)[0][0], compute(fx, 1000)[0][0]
    chk("capital scales the dollars, not the APR", abs(c2["usd"] / c1["usd"] - 2) < 0.01 and c2["net_apr"] == c1["net_apr"])
    chk("an empty scan gives an honest 'nothing beats costs' headline and a null $", build({}, "sample")["headline"]["usd_month"] is None)
    src = open(__file__, encoding="utf-8").read().split("def selftest")[0]
    chk("it never sends anything: no POST, no key, no order words", not re.search(r"method\s*=\s*['\"]POST|api[_-]?key|place_order|new_order", src, re.I))
    print(f"\n{ok[0]}/{ok[0] + ok[1]} passed")
    return 0 if not ok[1] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="ARBITER: paper-only spread and funding finder")
    ap.add_argument("--out", help="folder; writes arbiter.json there")
    ap.add_argument("--fixture", action="store_true", help="use the bundled sample, no network")
    ap.add_argument("--capital", type=float, default=CAPITAL)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    res = run(a.fixture, a.capital)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "arbiter.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
            fh.write("\n")
    print(res["headline"]["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
