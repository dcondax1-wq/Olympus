#!/usr/bin/env python3
"""K3 angle 1 (live): scan EVERY open Kalshi event (public listing, read only) for internal arbitrage at the top of book.

Checks, all after the taker fee (0.07 p (1-p), rounded up per order, priced for an order of N_REF contracts per leg):
  me_no   mutually-exclusive event: buy NO on every market. At most one YES -> payoff >= (N-1) x $1. Safe without exhaustiveness.
  me_yes  mutually-exclusive event: buy YES on every market. Pays $1 only if exactly one resolves YES (needs exhaustiveness:
          flagged 'exh' when the strikes tile the line: two open tails plus contiguous ranges).
  ladder  threshold ladder ("above X" or "below X") in one event: buy YES on the easier strike and NO on the harder one when
          the pair costs under $1 (payoff >= $1 in every state).
Size = the smallest top-of-book size across the legs (contracts). Writes one line per pass to data/live_scan.jsonl.gz
(pass stats + every opportunity with gross >= 0, so near-misses are visible too).

    python research/kalshi_edge_K3/scan_live.py [--passes 1] [--every 600]
"""
import argparse, gzip, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk

N_REF = 100
OUT = os.path.join(kk.DATA, "live_scan.jsonl.gz")


def all_open_events():
    evs, cur, pages = [], "", 0
    while True:
        p = {"status": "open", "with_nested_markets": "true", "limit": 200}
        if cur:
            p["cursor"] = cur
        d = kk.get("/events", p, cache=False)
        if not d:
            break
        evs += d.get("events", [])
        pages += 1
        cur = d.get("cursor") or ""
        if not cur or not d.get("events"):
            break
    return evs, pages


def mk_row(m):
    ya, yb, na, nb = (kk.c(m.get(k)) for k in ("yes_ask_dollars", "yes_bid_dollars", "no_ask_dollars", "no_bid_dollars"))
    return {"t": m["ticker"], "ya": ya, "yb": yb, "na": na, "nb": nb,
            "yas": kk.fl(m.get("yes_ask_size_fp")) or 0.0, "ybs": kk.fl(m.get("yes_bid_size_fp")) or 0.0,
            "st": m.get("strike_type"), "fs": m.get("floor_strike"), "cs": m.get("cap_strike"),
            "status": m.get("status"), "ct": m.get("close_time"), "v24": kk.fl(m.get("volume_24h_fp")) or 0.0}


def fee_pc(p):
    """fee per contract in cents (fractional) for an N_REF-contract order"""
    return kk.fee_c(p, N_REF) / N_REF


def exhaustive(ms):
    """strikes tile the line: one 'less' tail, contiguous 'between' ranges, one 'greater' tail"""
    lo = [m for m in ms if m["st"] in ("less", "less_or_equal")]
    hi = [m for m in ms if m["st"] in ("greater", "greater_or_equal")]
    mid = sorted([m for m in ms if m["st"] == "between"], key=lambda m: m["fs"] if m["fs"] is not None else -1e18)
    if len(lo) != 1 or len(hi) != 1 or len(lo) + len(hi) + len(mid) != len(ms):
        return False
    edges = [lo[0]["cs"]] + [x for m in mid for x in (m["fs"], m["cs"])] + [hi[0]["fs"]]
    if any(e is None for e in edges):
        return False
    # integer-valued ladders (weather: 'B57.5' = 57-58, less 57 = <57) are contiguous when next floor = previous cap + 1 or == cap
    ok = True
    prev = lo[0]["cs"]
    for m in mid:
        if not (abs(m["fs"] - prev) < 1e-9 or abs(m["fs"] - prev - 1) < 1e-9 or abs(m["fs"] - prev - 0.01) < 1e-6):
            ok = False
        prev = m["cs"]
    if not (abs(hi[0]["fs"] - prev) < 1e-9 or abs(hi[0]["fs"] - prev - 1) < 1e-9 or abs(hi[0]["fs"] - prev - 0.01) < 1e-6):
        ok = False
    return ok


def check_event(e):
    ms = [mk_row(m) for m in e.get("markets", []) if m.get("status") in ("active", "open")]
    out = []
    if len(ms) < 2:
        return out, ms
    if e.get("mutually_exclusive"):
        n = len(ms)
        if all(m["na"] for m in ms) and all(m["yb"] for m in ms):
            cost = sum(m["na"] for m in ms)
            fees = sum(fee_pc(m["na"]) for m in ms)
            gross = (n - 1) * 100 - cost
            size = min(m["ybs"] for m in ms)
            if gross >= 0:
                days = max(0.5, (max(kk.ts(m["ct"]) for m in ms) - time.time()) / 86400) if all(m["ct"] for m in ms) else None
                out.append({"k": "me_no", "days": round(days, 1) if days else None, "e": e["event_ticker"], "s": e.get("series_ticker"), "n": n, "gross_c": gross,
                            "net_c": round(gross - fees, 3), "cost_c": cost, "size": size, "cat": e.get("category")})
        if all(m["ya"] and m["ya"] < 100 for m in ms):
            cost = sum(m["ya"] for m in ms)
            fees = sum(fee_pc(m["ya"]) for m in ms)
            gross = 100 - cost
            size = min(m["yas"] for m in ms)
            if gross >= 0:
                days = max(0.5, (max(kk.ts(m["ct"]) for m in ms) - time.time()) / 86400) if all(m["ct"] for m in ms) else None
                out.append({"k": "me_yes", "days": round(days, 1) if days else None, "e": e["event_ticker"], "s": e.get("series_ticker"), "n": n, "gross_c": gross,
                            "net_c": round(gross - fees, 3), "cost_c": cost, "size": size, "exh": exhaustive(ms), "cat": e.get("category")})
    # threshold ladders inside one event
    for kind, sign in ((("greater", "greater_or_equal"), 1), (("less", "less_or_equal"), -1)):
        lad = sorted([m for m in ms if m["st"] in kind and m[("fs" if sign == 1 else "cs")] is not None
                      and re.search(r"-T-?[0-9.]+$", m["t"])],
                     key=lambda m: m["fs" if sign == 1 else "cs"] * sign)
        # 'above': higher strike = harder. 'below': lower strike = harder. sorted from easy to hard.
        for i in range(len(lad)):
            for j in range(i + 1, len(lad)):
                ez, hd = lad[i], lad[j]
                if not ez["ya"] or ez["ya"] >= 100 or not hd["na"] or hd["na"] >= 100:
                    continue
                cost = ez["ya"] + hd["na"]
                gross = 100 - cost
                if gross >= 0:
                    fees = fee_pc(ez["ya"]) + fee_pc(hd["na"])
                    out.append({"k": "ladder", "e": e["event_ticker"], "s": e.get("series_ticker"), "pair": [ez["t"], hd["t"]],
                                "gross_c": gross, "net_c": round(gross - fees, 3), "cost_c": cost,
                                "size": min(ez["yas"], hd["ybs"]), "cat": e.get("category")})
    return out, ms


def one_pass():
    t0 = time.time()
    evs, pages = all_open_events()
    opps, n_me, n_mk, n_lad, sums = [], 0, 0, 0, []
    for e in evs:
        o, ms = check_event(e)
        n_mk += len(ms)
        if e.get("mutually_exclusive") and len(ms) >= 2:
            n_me += 1
            if all(m["ya"] and m["ya"] < 100 for m in ms) and all(m["yb"] for m in ms) and sum(m["v24"] for m in ms) >= 1:
                sums.append([e["event_ticker"], len(ms), sum(m["ya"] for m in ms), sum(m["yb"] for m in ms),
                             round(sum(m["v24"] for m in ms))])
        if any(m["st"] in ("greater", "greater_or_equal", "less", "less_or_equal") for m in ms):
            n_lad += 1
        opps += o
    opps = [o for o in opps if o["net_c"] > -0.5]   # keep the near misses, not every zero-gross 2-way book
    rec = {"ts": int(t0), "secs": round(time.time() - t0, 1), "pages": pages, "events": len(evs), "markets": n_mk,
           "me_events": n_me, "ladder_events": n_lad, "opps": opps, "me_sums": sums}
    with gzip.open(OUT, "at") as fh:
        fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    pos = [o for o in opps if o["net_c"] > 0]
    print(time.strftime("%H:%M:%S"), f"events {len(evs)} markets {n_mk} me {n_me} ladders {n_lad} gross>=0 {len(opps)} net>0 {len(pos)} "
          f"({rec['secs']}s) {kk.STATS}", flush=True)
    for o in sorted(pos, key=lambda o: -o["net_c"])[:8]:
        print("   ", o, flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", type=int, default=1)
    ap.add_argument("--every", type=int, default=600)
    a = ap.parse_args()
    for i in range(a.passes):
        t0 = time.time()
        one_pass()
        if i < a.passes - 1:
            time.sleep(max(5, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
