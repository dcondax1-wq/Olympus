#!/usr/bin/env python3
"""K3 paper forward logger: 'known-outcome' Kalshi temperature buckets (READ ONLY: no orders, no keys, no account).

Why: history says the market reprices a bucket within ~2-3 minutes of the METAR that kills it, so the only open question is
whether a bot that reacts to the METAR's real publication time (aviationweather.gov receiptTime) still finds the known side
at <= 98c, and whether a resting order at 98c on a known side gets filled by late buyers of the dead side. Neither can be
measured from the archive (it has no publication times). This logger measures it forward.

Each run (cron every minute on the VM, or --loop 60):
  1. latest METARs for the 20 settlement stations (aviationweather.gov public API, one request), receiptTime kept;
  2. running max (min) of the LOCAL STANDARD day, rounded F (the CLI convention);
  3. open daily high/low markets (Kalshi public listing); a bucket is KNOWN when the running value is past it by >= MARGIN F
     (default 1: in 2,046 historical crossings at margin 1 the known side never lost; at margin 0, 4 of 2,744 lost);
  4. for each newly known bucket: log the METAR receipt time, our seen time, the known side's best ask + size (paper TAKER
     buy if ask <= 98c, up to 100 contracts), and a paper MAKER order at 98c (filled later only if the public tape shows a
     wrong-side buyer at >= 2c after our post time);
  5. settle every logged entry once Kalshi shows the result. P&L after fees: taker 0.07 p(1-p), maker 0.0175 p(1-p), rounded up.

Ledger: research/kalshi_edge_K3/forward/ledger.json (or --ledger PATH). Summary: forward/summary.json.
    python research/kalshi_edge_K3/forward_logger.py [--once | --loop 60] [--margin 1] [--selftest]
Decision rule written now: the idea counts only if, after >= 30 settled days and >= 100 taker or maker fills, net $ after fees
is > 0 with a day-bootstrap 95% range above 0. Otherwise: no edge.
"""
import argparse, calendar, json, math, os, random, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KAL = "https://api.elections.kalshi.com/trade-api/v2"
AWC = "https://aviationweather.gov/api/data/metar"
# series -> (ICAO, standard UTC offset, kind)
SER = {"KXHIGHNY": ("KNYC", -5, "high"), "KXHIGHCHI": ("KMDW", -6, "high"), "KXHIGHMIA": ("KMIA", -5, "high"), "KXHIGHAUS": ("KAUS", -6, "high"),
       "KXHIGHLAX": ("KLAX", -8, "high"), "KXHIGHDEN": ("KDEN", -7, "high"), "KXHIGHPHIL": ("KPHL", -5, "high"), "KXHIGHTSFO": ("KSFO", -8, "high"),
       "KXHIGHTPHX": ("KPHX", -7, "high"), "KXHIGHTATL": ("KATL", -5, "high"), "KXHIGHTSEA": ("KSEA", -8, "high"), "KXHIGHTBOS": ("KBOS", -5, "high"),
       "KXHIGHTDAL": ("KDFW", -6, "high"), "KXHIGHTDC": ("KDCA", -5, "high"), "KXHIGHTLV": ("KLAS", -8, "high"), "KXHIGHTHOU": ("KHOU", -6, "high"),
       "KXHIGHTMIN": ("KMSP", -6, "high"), "KXHIGHTOKC": ("KOKC", -6, "high"), "KXHIGHTNOLA": ("KMSY", -6, "high"), "KXHIGHTSATX": ("KSAT", -6, "high"),
       "KXLOWTNYC": ("KNYC", -5, "low"), "KXLOWTAUS": ("KAUS", -6, "low"), "KXLOWTDEN": ("KDEN", -7, "low"), "KXLOWTMIA": ("KMIA", -5, "low"),
       "KXLOWTCHI": ("KMDW", -6, "low"), "KXLOWTLAX": ("KLAX", -8, "low"), "KXLOWTPHIL": ("KPHL", -5, "low")}
MON = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


_LAST = [0.0]


def http_json(url, params=None, tries=4):
    u = url + ("?" + urllib.parse.urlencode(params) if params else "")
    for k in range(tries):
        w = 0.3 - (time.time() - _LAST[0])   # polite: at most ~3 requests per second
        if w > 0:
            time.sleep(w)
        _LAST[0] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research-logger"}), timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(1.5 * (k + 1))
    return None


def fee_c(p, n, rate):
    return math.ceil(round(rate * n * (p / 100) * (1 - p / 100) * 100, 9))


def cents(x):
    try:
        return int(round(float(x) * 100))
    except Exception:
        return None


def ts(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def known_side(m, run, kind, margin):
    st, fs, cs = m.get("strike_type"), m.get("floor_strike"), m.get("cap_strike")
    if run is None:
        return None
    if kind == "high":
        if (st == "between" and cs is not None and cs < run - margin) or (st in ("less", "less_or_equal") and cs is not None and cs <= run - margin):
            return "no"
        if st in ("greater", "greater_or_equal") and fs is not None and fs < run - margin:
            return "yes"
    else:
        if (st == "between" and fs is not None and fs > run + margin) or (st in ("greater", "greater_or_equal") and fs is not None and fs >= run + margin):
            return "no"
        if st in ("less", "less_or_equal") and cs is not None and cs > run + margin:
            return "yes"
    return None


def event_day(et):
    s = et.split("-")[1]
    return 2000 + int(s[:2]), MON.index(s[2:5]) + 1, int(s[5:7])


def running(metars, icao, off_h, day, kind, now):
    """running max/min (rounded F) over the local-standard day, from METARs received by `now`; returns (value, receipt_ts_of_the_extreme)"""
    w0 = calendar.timegm(day + (0, 0, 0)) - off_h * 3600
    best, rec = None, None
    for m in metars:
        if m.get("icaoId") != icao or m.get("temp") is None:
            continue
        ot = m.get("obsTime")
        rt = ts(m["receiptTime"]) if m.get("receiptTime") else ot
        if not (w0 <= ot < w0 + 86400) or rt > now:
            continue
        f = round(m["temp"] * 9 / 5 + 32)   # temp is the T-group tenths of C when present
        if best is None or (f > best if kind == "high" else f < best):
            best, rec = f, rt
    return best, rec


def run_once(ledger, margin, now=None, fetch=None):
    fetch = fetch or http_json
    now = now or int(time.time())
    icaos = sorted({v[0] for v in SER.values()})
    metars = fetch(AWC, {"ids": ",".join(icaos), "format": "json", "hours": 30}) or []
    seen_new = 0
    for ser, (icao, off_h, kind) in SER.items():
        d = fetch(KAL + "/markets", {"series_ticker": ser, "status": "open", "limit": 200}) or {}
        for m in d.get("markets", []):
            tk = m["ticker"]
            if tk in ledger["entries"]:
                continue
            try:
                day = event_day(m["event_ticker"])
            except Exception:
                continue
            run, rec = running(metars, icao, off_h, day, kind, now)
            side = known_side(m, run, kind, margin)
            if not side:
                continue
            if side == "no":
                ask, size = cents(m.get("no_ask_dollars")), float(m.get("yes_bid_size_fp") or 0)
            else:
                ask, size = cents(m.get("yes_ask_dollars")), float(m.get("yes_ask_size_fp") or 0)
            e = {"t": tk, "s": ser, "kind": kind, "side": side, "run": run, "margin": margin, "metar_receipt": rec, "seen": now,
                 "lag_s": (now - rec) if rec else None, "ask": ask, "ask_size": size, "close": m.get("close_time"),
                 "taker": None, "maker_post": now, "maker_px": 98, "result": None}
            if ask is not None and ask <= 98 and size > 0:
                n = int(min(100, size))
                e["taker"] = {"px": ask, "n": n, "fee_c": fee_c(ask, n, 0.07)}
            ledger["entries"][tk] = e
            seen_new += 1
    ledger["last_run"] = now
    return seen_new


def settle(ledger, fetch=None, now=None):
    fetch = fetch or http_json
    now = now or int(time.time())
    done = 0
    for tk, e in ledger["entries"].items():
        if e.get("result") is not None or (e.get("close") and ts(e["close"]) > now):
            continue
        d = fetch(KAL + f"/markets/{tk}") or {}
        m = d.get("market") or {}
        if m.get("result") not in ("yes", "no"):
            continue
        e["result"] = m["result"]
        won = m["result"] == e["side"]
        if e.get("taker"):
            t = e["taker"]
            e["taker"]["pnl_usd"] = round((t["n"] * ((100 if won else 0) - t["px"]) - t["fee_c"]) / 100, 2)
        # maker fill: wrong-side taker at >= 2c (known side <= 98c) after our post time
        tr = fetch(KAL + "/markets/trades", {"ticker": tk, "min_ts": e["maker_post"], "max_ts": ts(e["close"]), "limit": 1000}) or {}
        filled = 0.0
        for x in tr.get("trades", []):
            yp = cents(x.get("yes_price_dollars"))
            kp = (100 - yp) if e["side"] == "no" else yp
            wrong_taker = x.get("taker_side") != e["side"]
            if kp is not None and kp <= e["maker_px"] and wrong_taker:
                filled += float(x.get("count_fp") or 0)
        n = int(min(100, filled))
        e["maker"] = {"px": e["maker_px"], "n_upper_bound": n,
                      "pnl_usd": round((n * ((100 if won else 0) - e["maker_px"]) - (fee_c(e["maker_px"], n, 0.0175) if n else 0)) / 100, 2)}
        done += 1
    return done


FRESH_S = 600   # only buckets that became known while the logger was watching (METAR received <= 10 min before we saw it)


def summary(ledger):
    # entries found already-known at start-up (or after a gap) are logged but not scored: they answer a different question
    es = [e for e in ledger["entries"].values() if e.get("result") and e.get("lag_s") is not None and e["lag_s"] <= FRESH_S]
    days = {}
    for e in es:
        dk = e["t"].split("-")[1]
        days.setdefault(dk, 0.0)
        days[dk] += (e.get("taker") or {}).get("pnl_usd", 0) + (e.get("maker") or {}).get("pnl_usd", 0)
    vals = list(days.values())
    rnd = random.Random(1)
    bs = sorted(sum(rnd.choice(vals) for _ in vals) for _ in range(1000)) if vals else [0.0] * 1000
    tk = [e for e in es if e.get("taker")]
    mk = [e for e in es if (e.get("maker") or {}).get("n_upper_bound")]
    lags = sorted(e["lag_s"] for e in ledger["entries"].values() if e.get("lag_s") is not None and e["lag_s"] <= FRESH_S)
    backlog = sum(1 for e in ledger["entries"].values() if e.get("lag_s") is None or e["lag_s"] > FRESH_S)
    s = {"settled": len(es), "days": len(days), "known_side_lost": sum(1 for e in es if e["result"] != e["side"]),
         "taker_fills": len(tk), "taker_usd": round(sum(e["taker"]["pnl_usd"] for e in tk), 2),
         "maker_fills": len(mk), "maker_usd_upper_bound": round(sum(e["maker"]["pnl_usd"] for e in mk), 2),
         "net_usd": round(sum(vals), 2), "net_usd_95": [round(bs[25], 2), round(bs[974], 2)],
         "median_lag_s_metar_to_seen": lags[len(lags) // 2] if lags else None, "fresh_logged": len(lags), "backlog_not_scored": backlog,
         "verdict": "collecting" if len(days) < 30 or (len(tk) + len(mk)) < 100 else ("edge" if bs[25] > 0 else "no edge")}
    return s


def selftest():
    now = calendar.timegm((2026, 11, 13, 21, 0, 0))
    met = [{"icaoId": "KNYC", "temp": 15.0, "obsTime": now - 300, "receiptTime": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now - 120))}]
    mk = {"markets": [
        {"ticker": "KXHIGHNY-26NOV13-B55.5", "event_ticker": "KXHIGHNY-26NOV13", "strike_type": "between", "floor_strike": 55, "cap_strike": 56,
         "no_ask_dollars": "0.9700", "yes_bid_size_fp": "40", "close_time": "2026-11-14T06:00:00Z"},
        {"ticker": "KXHIGHNY-26NOV13-B58.5", "event_ticker": "KXHIGHNY-26NOV13", "strike_type": "between", "floor_strike": 58, "cap_strike": 59,
         "no_ask_dollars": "0.6000", "yes_bid_size_fp": "40", "close_time": "2026-11-14T06:00:00Z"},
        {"ticker": "KXHIGHNY-26NOV13-T53", "event_ticker": "KXHIGHNY-26NOV13", "strike_type": "greater", "floor_strike": 53,
         "yes_ask_dollars": "0.9900", "yes_ask_size_fp": "500", "close_time": "2026-11-14T06:00:00Z"}]}

    def fake(url, params=None):
        if url == AWC:
            return met
        if url.endswith("/markets") and params.get("series_ticker") == "KXHIGHNY":
            return mk
        if "/markets/KXHIGHNY" in url:
            return {"market": {"result": "no" if "B55" in url else "yes"}}
        if url.endswith("/trades"):
            return {"trades": [{"yes_price_dollars": "0.0200", "taker_side": "yes", "count_fp": "30"}]}
        return {"markets": []}
    L = {"entries": {}}
    n = run_once(L, 1, now=now, fetch=fake)
    # 15.0 C = 59 F: bucket 55-56 dead (NO), 58-59 alive, 'above 53' known YES
    assert n == 2, L
    e = L["entries"]["KXHIGHNY-26NOV13-B55.5"]
    assert e["side"] == "no" and e["taker"]["px"] == 97 and e["taker"]["n"] == 40, e
    assert L["entries"]["KXHIGHNY-26NOV13-T53"]["side"] == "yes" and L["entries"]["KXHIGHNY-26NOV13-T53"]["taker"] is None
    assert settle(L, fetch=fake, now=now + 86400) == 2
    assert e["taker"]["pnl_usd"] == round((40 * 3 - fee_c(97, 40, 0.07)) / 100, 2), e
    assert e["maker"]["n_upper_bound"] == 30
    s = summary(L)
    assert s["settled"] == 2 and s["known_side_lost"] == 0 and s["verdict"] == "collecting", s
    print("selftest OK", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", type=int, default=0)
    ap.add_argument("--margin", type=int, default=1)
    ap.add_argument("--ledger", default=os.path.join(HERE, "forward", "ledger.json"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    os.makedirs(os.path.dirname(a.ledger), exist_ok=True)
    while True:
        L = json.load(open(a.ledger)) if os.path.exists(a.ledger) else {"entries": {}, "started": int(time.time()), "margin": a.margin}
        n = run_once(L, a.margin)
        k = settle(L)
        tmp = a.ledger + ".tmp"
        json.dump(L, open(tmp, "w"), separators=(",", ":"))
        os.replace(tmp, a.ledger)
        s = summary(L)
        json.dump(s, open(os.path.join(os.path.dirname(a.ledger), "summary.json"), "w"), indent=1)
        print(time.strftime("%H:%M:%S"), "new known", n, "settled", k, s, flush=True)
        if not a.loop:
            break
        time.sleep(a.loop)


if __name__ == "__main__":
    main()
