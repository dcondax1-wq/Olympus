"""research/kalshi_best_shot (the rewards-maker plan, 2026-11-18): Kalshi's published Liquidity Incentive Program maths
(lip.py), the backtest engine on a made-up market (bt.py) and the live plan file's exact shape (research/lab/kalshi_live_plan.json).
Offline: no network, never an order.
    python -X utf8 -m tests.test_kalshi_best_shot"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research", "kalshi_best_shot"))
import lip  # noqa: E402
import bt  # noqa: E402

RES = []


def check(name, ok):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name)


def made_up_market(t0, trade=None, move=None, result="no"):
    cand = []
    for k in range(0, 1441):
        t = t0 + 60 * k
        b, a = ("0.10", "0.12")
        if move and move[0] <= t < move[1]:
            b, a = ("0.16", "0.18")
        cand.append([t, b, a, "0"])
    return {"info": {"result": result, "close_time": dt.datetime.fromtimestamp(t0 + 2 * 86400, dt.timezone.utc).isoformat(),
                     "yes_bid_dollars": "0.10", "yes_ask_dollars": "0.12"},
            "programs": [{"m": "X", "start": t0, "end": t0 + 86400, "usd": 100.0, "target": 1000.0, "df": 0.5}],
            "candles": cand, "trades": [trade] if trade else []}


def run_one(v, **kw):
    import collections
    prof = {"c2": [{"S": 1000.0, "ahead0": 500.0, "ahead1": 900.0, "ahead2": 950.0, "ahead3": 990.0, "ticks": 0, "valid": True, "ref": 0.1}],
            "hi": [{"S": 1000.0, "ahead0": 500.0, "ahead1": 900.0, "ahead2": 950.0, "ahead3": 990.0, "ticks": 0, "valid": True, "ref": 0.88}]}
    rep = lambda b: [prof.get(b, prof["c2"])[0]] * 4   # noqa: E731
    days = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0])
    st = collections.Counter()
    rule = dict(bt.BASE, **kw)
    t0 = v["programs"][0]["start"]
    for r in range(4):
        bt.sim(v, rep, 1.0, "quadratic", rule, r, t0, t0 + 3 * 86400, days, st)
    for row in days.values():
        for i in range(5):
            row[i] /= 4
    return days, st


def main():
    # 1) the published scoring
    check("reference = first level where cumulative size reaches Target/5", lip.ref_price([(0.39, 150), (0.38, 100), (0.37, 900)], 1000) == 0.38)
    check("score: full at/above the reference, DF^ticks below", abs(lip.side_score([(0.39, 200), (0.37, 100)], 0.39, 0.5) - 225) < 1e-9)
    sh, r = lip.my_share([(0.30, 800)], 0.30, 200, 1000, 0.5)
    check("share is per side: 200 of 1,000 at the reference = 20%", abs(sh - 0.2) < 1e-9 and r == 0.30)
    rr = lip.reward_rate([(0.30, 500), (0.29, 400), (0.28, 5000)], [(0.65, 5000)], "yes", 0.30, 200, 1000, 0.5, 100.0)
    check("a side's share earns half the pool: 200/(500+200+0.5*400) of $50 (the 28c level is past the Target walk)",
          abs(rr - 50 * 200 / 900) < 1e-9)
    check("a bid deeper than where cumulative size reaches Target scores nothing",
          lip.my_share([(0.30, 500), (0.29, 600), (0.28, 5000)], 0.28, 100, 1000, 0.5)[0] == 0.0)
    check("a whole level counts: my bid joining the Target level is in", abs(lip.my_share([(0.30, 500), (0.29, 600)], 0.29, 100, 1000, 0.5)[0] - 50 / 850) < 1e-9)
    check("no reward when the other side is under Target", lip.reward_rate([(0.3, 2000)], [(0.6, 500)], "yes", 0.3, 10, 1000, 0.5, 100) == 0)
    check("help-page example: 20% x $100 x 8,000/10,000 = $16.00", lip.payout(0.2 * 100 * 8000 / 10000) == 16.0)
    check("payout rounds down to the cent and pays nothing under $1", lip.payout(16.239) == 16.23 and lip.payout(0.999) == 0.0 and lip.payout(1.0) == 1.0)
    check("fees: taker 0.07 p(1-p) up to the cent; no maker fee on 'quadratic'",
          lip.taker_fee(0.5, 10) == 0.18 and lip.maker_fee(0.5, 100, "quadratic") == 0.0 and lip.maker_fee(0.5, 100, "quadratic_with_maker_fees") == 0.44)
    # 2) the backtest engine on a made-up day: $10 a side at 10c (100 YES) and 88c (11 NO), others' score 1,000 a side
    t0 = dt.datetime(2026, 11, 10, 5, tzinfo=dt.timezone.utc).timestamp()          # midnight ET
    days, st = run_one(made_up_market(t0), usd=10.0)
    d = days[bt.day_of(t0)]
    exp = 100 * (100 / 1100) / 2 + 100 * (11 / 1011) / 2
    check("quiet day: reward = both sides' per-side shares, paid to the cent (%.2f)" % d[0], abs(d[0] - lip.payout(exp)) < 1e-6 and d[1] == 0)
    check("parked $ = the two resting bids all day", abs(d[2] / 86400 - (100 * 0.10 + 11 * 0.88)) < 0.02)
    days, st = run_one(made_up_market(t0, trade=[t0 + 43200, "no", 0.09, 5.0]), usd=10.0)
    d = days[bt.day_of(t0)]
    check("a trade THROUGH my 10c bid fills the whole order (100 at 10c, settles NO: -$10)", abs(d[1] + 10.0) < 1e-9 and st["through"] == 4)
    exp2 = 100 * (100 / 1100) / 2 * 0.5 + 100 * (11 / 1011) / 2
    check("after the fill the side stops earning (half a day of the YES share)", abs(d[0] - lip.payout(exp2)) < 1e-6)
    days, _ = run_one(made_up_market(t0, trade=[t0 + 43200, "no", 0.10, 300.0]), usd=10.0)
    check("a trade AT my price first eats the 500 ahead: no fill", days[bt.day_of(t0)][1] == 0)
    days, _ = run_one(made_up_market(t0), usd=10.0, sides=("yes",), inv_cap=1e9)
    check("one side only: only the YES share", abs(days[bt.day_of(t0)][0] - lip.payout(100 * (100 / 1100) / 2)) < 1e-6)
    days, st = run_one(made_up_market(t0), usd=0.5, sides=("no",))
    check("an order too small to reach $1 for the program is paid nothing", days[bt.day_of(t0)][0] == 0 and st["paid_programs"] == 0)
    days, _ = run_one(made_up_market(t0), usd=10.0, min_expect=5.0)
    check("min_expect skips orders whose period payout would be under it", days[bt.day_of(t0)][0] == 0 and days[bt.day_of(t0)][2] == 0)
    mv = (t0 + 6 * 3600, t0 + 6 * 3600 + 600)
    a, _ = run_one(made_up_market(t0, move=mv), usd=10.0)
    b, _ = run_one(made_up_market(t0, move=mv), usd=10.0, pause_c=5, pause_h=1.0)
    pa = a[bt.day_of(t0)][2] / 86400
    pb = b[bt.day_of(t0)][2] / 86400
    check("a 6c move pauses both sides for about an hour (parked $ falls by ~1/24, not more than 2/24)",
          pb < pa and 0.9 / 24 < (pa - pb) / pa < 2.2 / 24)
    c, _ = run_one(made_up_market(t0), usd=10.0, blackout=((1, 8, 11),))       # 2026-11-10 is a Tuesday
    check("a Tuesday 8-11 ET blackout removes 3 hours of quotes", abs((a[bt.day_of(t0)][2] - c[bt.day_of(t0)][2]) / a[bt.day_of(t0)][2] - 3 / 24) < 0.01)
    s = bt.summarize({"2026-11-10": [3.0, -1.0, 86400 * 50, 1, 5], "2026-11-11": [1.0, -4.0, 86400 * 50, 2, 9]}, "2026-11-10", "2026-11-11")
    check("summary: net, per $100 a day, days up / down, worst day", s["net"] == -1.0 and abs(s["net_per100_day"] + 1.0) < 1e-9
          and s["days_up"] == 1 and s["days_down"] == 1 and s["worst_day"] == -3.0)
    # 3) the plan file the live-executor helper reads: exactly this shape
    fn = os.path.join(ROOT, "research", "lab", "kalshi_live_plan.json")
    try:
        P = json.load(open(fn, encoding="utf-8"))
    except (OSError, ValueError):
        P = {}
    keys = {"version", "strategy", "status", "capital_cap_usd", "per_market_cap_usd", "daily_loss_stop_usd", "max_open_orders", "markets",
            "evidence", "unproven"}
    check("plan: exactly the agreed top-level keys", set(P) == keys)
    check("plan: version 1, rewards_maker, a proposal or rejected (never 'live' from Claude)",
          P.get("version") == 1 and P.get("strategy") == "rewards_maker" and P.get("status") in ("proposal", "rejected"))
    check("plan: a rejected plan says so in every market's rules",
          P.get("status") != "rejected" or all(any("rejected" in x.lower() for x in m.get("pause", [])) for m in P.get("markets") or []))
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)    # noqa: E731
    check("plan: caps are numbers, small (tens of dollars), per market <= total, loss stop > 0",
          num(P.get("capital_cap_usd")) and num(P.get("per_market_cap_usd")) and num(P.get("daily_loss_stop_usd"))
          and 0 < P["per_market_cap_usd"] <= P["capital_cap_usd"] <= 100 and 0 < P["daily_loss_stop_usd"] <= P["capital_cap_usd"])
    check("plan: max_open_orders is a small int", isinstance(P.get("max_open_orders"), int) and not isinstance(P.get("max_open_orders"), bool)
          and 1 <= P["max_open_orders"] <= 10)
    ms = P.get("markets") or []
    check("plan: each market has series, why, quote {offset_cents int, size int}, pause [str]",
          bool(ms) and all(set(m) == {"series", "why", "quote", "pause"} and isinstance(m["series"], str) and isinstance(m["why"], str)
                           and set(m["quote"]) == {"offset_cents", "size"} and all(isinstance(m["quote"][k], int) and not isinstance(m["quote"][k], bool)
                                                                                 for k in ("offset_cents", "size"))
                           and isinstance(m["pause"], list) and all(isinstance(x, str) for x in m["pause"]) for m in ms))
    ev = P.get("evidence") or {}
    check("plan: evidence {paper_days, net_per_100_per_day, backtest_both_halves bool, worst_day_usd}",
          set(ev) == {"paper_days", "net_per_100_per_day", "backtest_both_halves", "worst_day_usd"} and num(ev.get("paper_days"))
          and num(ev.get("net_per_100_per_day")) and isinstance(ev.get("backtest_both_halves"), bool) and num(ev.get("worst_day_usd")))
    check("plan: unproven is a non-empty list of sentences", isinstance(P.get("unproven"), list) and P["unproven"]
          and all(isinstance(x, str) and len(x) > 10 for x in P["unproven"]))
    src = "".join(open(os.path.join(ROOT, "research", "kalshi_best_shot", f), encoding="utf-8").read()
                  for f in ("kget.py", "books.py", "scan.py", "harvest.py", "lip.py", "bt.py", "profiles.py"))
    check("research code is GET-only: no order, portfolio or key paths", not any(x in src for x in ("/portfolio", "KALSHI-ACCESS", "method=\"POST\"", "DELETE")))
    print("%d/%d passed" % (sum(RES), len(RES)))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
