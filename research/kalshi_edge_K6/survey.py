#!/usr/bin/env python3
"""K6 step 1: survey the candidate rates / index series (public listing only, cached): how many settled markets, which
dates, how much volume, and the settlement rule. Writes data/survey.json. GET only, no key, never an order.

    python research/kalshi_edge_K6/survey.py [SERIES,SERIES,...]
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk6

SERIES = ("KXFED FED KXFEDDECISION FEDDECISION KXRATECUTCOUNT KXFEDFUNDSYEAR KXEFFR KXSOFR KXSOFRD KX3MTBILL TBILL "
          "KXINXW KXINXWD INXW KXNASDAQ100W KXNASDAQ100WD NASDAQ100W KXINXM KXINXME KXINXMD INXM KXNASDAQ100M "
          "KXNASDAQ100ME KXNASDAQ100MD NASDAQ100M KXNASDAQ100MAXM KXNASDAQ100MINM KXINXMAXMM KXINXMINMON KXINXMAXMON "
          "KXNASDAQ100MAXMON KXNASDAQ100MINMON KXINXWUD KXNASDAQWUD "
          "KXTNOTED KXTNOTEW TNOTED TNOTEW TNOTE KXTNOTE KXNOTE10W KXNOTE10M KXNOTE10 KX10YRDIRHW KX10YRDIRLW "
          "KX10YRDIRHM KX10YRDIRLM KX2YRDIRHM KX2YRDIRLM KX5YRDIRHM KX5YRDIRLM KX30YRDIRHM KX30YRDIRLM KXNOTE30W "
          "KX30YUSTW KXUST10 KXUST10M KXUST2 KXUST30 KXUST30M KXUST5M KXUST10A KXUST2A KXUST5A KXUST30A KX20YRRATEW "
          "KX20YRRATED KXFRM FRM KX10Y2Y 10Y2Y").split()


def main():
    ser = sys.argv[1].split(",") if len(sys.argv) > 1 else SERIES
    out_fn = os.path.join(kk6.DATA, "survey.json")
    os.makedirs(kk6.DATA, exist_ok=True)
    res = json.load(open(out_fn)) if os.path.exists(out_fn) else {}
    for s in ser:
        live = kk6.markets(s)
        hist = kk6.markets(s, historical=True)
        ms = {m["ticker"]: m for m in hist + live}.values()
        ms = [m for m in ms if m.get("result") in ("yes", "no")]
        if not ms:
            res[s] = {"n": 0}
            print(s, "none", kk6.STATS, flush=True)
            continue
        cts = sorted(m["close_time"][:10] for m in ms)
        vol = sum(kk6.fl(kk6.g(m, "volume_fp", "volume")) or 0 for m in ms)
        ev = {m.get("event_ticker") for m in ms}
        last = max(ms, key=lambda m: m["close_time"])
        res[s] = {"n": len(ms), "events": len(ev), "first": cts[0], "last": cts[-1], "volume": vol,
                  "n_live": len(live), "n_hist": len(hist),
                  "rule": (last.get("rules_primary") or "")[:400], "rule2": (last.get("rules_secondary") or "")[:300],
                  "example": last["ticker"], "strike_type": last.get("strike_type")}
        print(f"{s}: {len(ms)} mkts, {len(ev)} events, {cts[0]}..{cts[-1]}, vol {vol:,.0f} | {res[s]['rule'][:160]}", flush=True)
        json.dump(res, open(out_fn, "w"), indent=1)
    print(kk6.STATS)


if __name__ == "__main__":
    main()
