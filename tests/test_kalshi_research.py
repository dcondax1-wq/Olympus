"""tools/kalshi_research.py (research only, offline): maths on a small made-up feed, schema keys, no network."""
import json
import sys

from tools import kalshi_research as kr

RES = []


def check(name, ok):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


def feed():
    return {"t": 1, "pub_t": 2, "balance": 55.81, "total_pnl": -10.0,
            "trades": [{"t": 1793634827, "ticker": "KXBTCD-26NOV0211-T77399.99", "side": "yes", "action": "buy", "contracts": 6.0,
                        "price": 0.98, "pnl": 0.11, "asset": "BTC", "strategy": "Late favourite (BTC hourly)", "category": "Bitcoin"}] * 3,
            "days": [["2026-10-%02d" % d, v] for d, v in zip(range(1, 11), (1, -2, 3, -1, 2, -6, 1, 1, 0.5, -1.5))],
            "strategies": [{"name": "Late favourite (BTC hourly)", "mode": "live", "total_pnl": 5.0, "trades": 100, "wins": 98, "losses": 2}],
            "categories": [{"name": "Bitcoin", "group": "Crypto", "trades": 100, "wins": 98, "losses": 2, "pnl": 5.0, "staked": 900.0}],
            "buckets": [{"lo": 0.95, "hi": 0.97, "trades": 100, "wins": 98, "losses": 2, "pnl": 5.0, "staked": 900.0}],
            "calibration": [{"p": 0.96, "n": 100, "hit": 0.98}],
            "stats": {"trades": 100, "wins": 98, "losses": 2, "staked": 900.0, "pnl": 5.0, "avg_price": 0.96}}


def main():
    check("fee at 98c is 0.07*.98*.02", abs(kr.fee_pc(0.98) - 0.001372) < 1e-6)
    check("break-even above price", kr.breakeven_win_rate(0.98) > 0.98)
    check("price cap inverts break-even", abs(kr.breakeven_win_rate(kr.price_cap(0.95)) - 0.95) < 1e-6)
    lo, hi = kr.wilson(98, 100)
    check("wilson brackets the rate", lo < 0.98 < hi and 0.92 < lo < 0.94)
    check("binomial tail sane", abs(kr.binom_sf(0, 10, 0.5) - 1) < 1e-9 and abs(kr.binom_sf(10, 10, 0.5) - 0.5 ** 10) < 1e-12)
    t = kr.build_tables(feed(), sims=500, run_sims=False)
    for k in ("schema", "buckets", "fees", "categories", "strategies", "sample", "risk", "ideas", "verdict"):
        check("key " + k, k in t)
    b = t["buckets"][0]
    check("bucket row fields", all(k in b for k in ("win_rate", "wilson_lo", "roi", "roi_ci_lo", "size_effect_pnl", "price_cap", "low_n")))
    check("pnl equals equal-size EV plus size effect", abs(b["pnl"] - b["ev_equal_size_pnl"] - b["size_effect_pnl"]) < 0.02)
    check("fee check ran on the sample", t["fees"]["check_vs_trades"]["n"] == 3)
    check("json-able", bool(json.dumps(t, default=float)))
    n = sum(RES)
    print(f"\nkalshi research: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
