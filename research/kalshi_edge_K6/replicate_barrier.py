#!/usr/bin/env python3
"""K6: the 'how high / how low' (barrier) lead, FROZEN, on four barrier series that were not looked at before the lead
was noticed (5Y how low, 30Y how low, 7Y how high, 7Y how low; monthly, Sep-Nov 2026). Model parameters and the trading
rule are read from results_yields.json (fixed on the 2023-24 weekly 10Y markets); nothing is refitted.
Caveat written before the run: these are the SAME months as the lead (Sep / Oct 2026), so they share the yield moves;
this checks the tenor, not the time period.

    python research/kalshi_edge_K6/replicate_barrier.py   # -> results_barrier_replication.json, trades_barrier_rep.json
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("K6_OFFLINE", "1")
import kk6
import yields as Yl

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    fr = json.load(open(os.path.join(HERE, "results_yields.json")))
    P, R = fr["params"], fr["rule"]
    Y = Yl.Yields()
    fomc = Yl.fomc_days()
    rows = [r for r in Yl.load_rows(Yl.REPLICATION) if r["c"]]
    ob = Yl.build_obs(rows, Y, fomc, P["half_life_days"], P["k"], P["df"], P["fomc_var_mult"], np.random.default_rng(5))
    tr = Yl.trades(ob, R["margin"], R["max_spread_c"])
    res = {"frozen_params": P, "frozen_rule": R, "markets": len(rows), "obs": len(ob),
           "brier": {"market_mid": Yl.brier([(o["bid"] + o["ask"]) / 200 for o in ob if o["ask"] - o["bid"] <= 10],
                                            [o["y"] for o in ob if o["ask"] - o["bid"] <= 10]),
                     "model": Yl.brier([o["p"] for o in ob if o["ask"] - o["bid"] <= 10],
                                       [o["y"] for o in ob if o["ask"] - o["bid"] <= 10])},
           "all": Yl.summarize(tr), "by_series": {s: Yl.summarize([x for x in tr if x["s"] == s]) for s in Yl.REPLICATION},
           "by_event": {e: Yl.summarize([x for x in tr if x["e"] == e]) for e in sorted({x["e"] for x in tr})}}
    json.dump(res, open(os.path.join(HERE, "results_barrier_replication.json"), "w"), indent=1)
    vt = [{"ts": x["ts"], "info_ts": x["info"], "price": x["price"], "contracts": kk6.fee_order(x["price"])[0],
           "outcome": x["won"], "event": x["e"], "ticker": x["t"], "settle_ts": x["ct"]} for x in tr]
    json.dump({"rule": R, "trades": vt}, open(os.path.join(HERE, "trades_barrier_rep.json"), "w"))
    print(json.dumps({k: v for k, v in res.items() if k != "by_event"}, indent=1))
    for e, v in res["by_event"].items():
        print(e, v["n"], round(v["net_per_dollar"], 3), round(v["win"], 2))


if __name__ == "__main__":
    main()
