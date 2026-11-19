#!/usr/bin/env python3
"""Write research/lab/kalshi_candidates/K8.json from results.json, ONLY if the pre-declared candidate passes on the
held-out half: >= 50 test bets, test net per $1 > 0 with the day-bootstrap 95% low end > 0, and the 2c-slippage test > 0.
Paper only: nothing here places or arms anything."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "research", "lab", "kalshi_candidates", "K8.json")

LEG_RULE = {
    "A_gold": ("KXGOLD15M", "05:30 DOWN gold: the 05:15-05:30 ET market; at 05:15:20 ET buy NO (= 'down') at the ask"),
    "A_silver": ("KXSILVER15M", "05:30 DOWN silver: the 05:15-05:30 ET market; at 05:15:20 ET buy NO at the ask"),
    "B_gold": ("KXGOLD15M", "17:00 UP gold: the 16:45-17:00 ET market; at 16:45:20 ET buy YES (= 'up') at the ask"),
    "B_silver": ("KXSILVER15M", "17:00 UP silver: the 16:45-17:00 ET market; at 16:45:20 ET buy YES at the ask"),
    "C_silver": ("KXSILVER15M", "16:15 DOWN silver: the 16:00-16:15 ET market; at 16:00:20 ET buy NO at the ask"),
    "C_gold": ("KXGOLD15M", "16:15 DOWN gold: the 16:00-16:15 ET market; at 16:00:20 ET buy NO at the ask"),
    "R_natgas": ("KXNATGAS15M", "roll natgas UP: on the 5th-9th US business day of the month, the 17:00-17:15 ET market; buy YES at the open"),
    "R_wti": ("KXWTI15M", "roll WTI DOWN: on the 5th-9th US business day, the 17:00-17:15 ET market; buy NO at the open"),
}


def main():
    R = json.load(open(os.path.join(HERE, "results.json")))
    c = R.get("candidate") or {}
    te, tr = c.get("test") or {}, c.get("train") or {}
    slip2 = (c.get("test_slip_2c") or {}).get("net_per_$1")
    ci = te.get("ci95_net_per_$1") or [None, None]
    ok = (te.get("n", 0) >= 50 and (te.get("net_per_$1") or 0) > 0 and ci[0] is not None and ci[0] > 0
          and (tr.get("net_per_$1") or 0) > 0 and slip2 is not None and slip2 > 0)
    print("candidate legs", c.get("legs"), "test", te.get("n"), te.get("net_per_$1"), ci, "slip2", slip2, "PASS" if ok else "FAIL")
    if not ok:
        if os.path.exists(OUT):
            os.remove(OUT)
        return 1
    legs = c["legs"]
    doc = {
        "strategy": "K8 metals time-of-day (the friend's 'printer' legs, flat size): buy the side the clock favours in Kalshi's "
                    "15-minute gold/silver up/down markets, 20 seconds after the window opens",
        "status": "PAPER ONLY. Never armed. Kalshi is paused for real money; only the owner can ever place real orders.",
        "date": "2026-11-19",
        "source": "research/writeups/kalshi-metals-2026-11-19.md, research/kalshi_edge_K8/study.py -> results.json",
        "series": sorted({LEG_RULE[k][0] for k in legs}),
        "rule": {
            "plain": "Every US weekday, one taker order per leg, flat $10 each, never more than one order per market, "
                     "no averaging, no exits (hold to the settle 15 minutes later).",
            "legs": [LEG_RULE[k][1] for k in legs],
            "entry_time": "20 seconds after the 15-minute window opens (ET, NTP-synced clock); if no fill by 40 s, skip",
            "price_limit": "tested as: take the ask 15-30 s after the open, whatever it is (no cap); in paper, send a limit at that ask and skip if not filled by 40 s",
            "size": "$10 per leg (whole contracts = floor(10 / price)); no compounding",
            "fee": "Kalshi taker fee 0.07 x C x p x (1-p), rounded up to the cent per order",
            "days": "US weekdays only; Kalshi lists these markets Monday-Friday",
        },
        "held_out": {
            "period": "2026-10-01 .. 2026-11-18 (rules and legs fixed on 2026-08-03 .. 09-30)",
            "trades": te.get("n"), "win_rate": te.get("win_rate"), "net_per_dollar": te.get("net_per_$1"),
            "net_per_dollar_95pct_range": ci, "net_per_dollar_if_2c_worse_fills": slip2,
            "worst_streak": te.get("worst_streak"), "max_drawdown_usd_at_15": te.get("max_dd_$"),
            "trades_per_month": te.get("trades_per_month"), "usd_per_month_at_15": te.get("usd_per_month"),
            "usd_per_month_at_10": (c.get("test_at_$10") or {}).get("usd_per_month"),
            "usd_per_month_at_20": (c.get("test_at_$20") or {}).get("usd_per_month"),
        },
        "train": {"trades": tr.get("n"), "win_rate": tr.get("win_rate"), "net_per_dollar": tr.get("net_per_$1")},
        "needs": [
            "Kalshi PUBLIC market data on the PC: the market ticker of each window (e.g. KXGOLD15M-26NOV190530-30) and its "
            "order book / best ask at 20 s after the open (REST GET /markets/{ticker} or the public websocket)",
            "an NTP-synced clock on the PC (the order must go out 15-30 s after 05:15:00, 16:45:00, 16:00:00 ET)",
            "for real money only (owner's decision, never Claude): the owner's own Kalshi API key on the PC",
            "nothing else is required for the clock legs; optional logging: NinjaTrader 1-minute bars of COMEX gold (GC front "
            "month) and silver (SI front month) 04:45-05:45 and 16:15-17:15 ET, to watch whether the drift is still there",
        ],
        "unproven": [
            "the windows come from the friend's own posts; he probably found them in these same months, so the clean test is "
            "forward paper trading from 2026-11-19 (kill rule: stop if the first 60 paper bets win under 55%)",
            "why it happens is not proven: we cannot read Pyth's tick history (it now needs an API key); 05:30 follows the "
            "London clock (gold auction at 10:30 London), 16:00 / 17:00 are CME session times",
            "Kalshi already removed the metals windows inside the CME break on 2026-10-01; it or Pyth can change the market "
            "list or the index any day and the edge would vanish at once",
            "the friend's bot and copycats buy the same seconds: if market makers start pricing the clock, entry prices rise "
            "from ~0.52 toward the win rate (~0.70) and the edge is gone; watch the paid price",
            "losing streaks: test worst streak %s bets; gold and silver usually lose on the same day" % te.get("worst_streak"),
            "the newest days were the worst: 11/16 evening + all 6 legs on 11/17 lost (8 in a row, -$92 that day at $15); "
            "one bad day cannot tell bad luck from the start of the end, which is why paper comes first",
            "the 16:15 legs cost more in November (0.59) and lost money that month: drop them first if paper disappoints",
        ],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
