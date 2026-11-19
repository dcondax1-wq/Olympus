#!/usr/bin/env python3
"""K8: test the friend's 'printer' legs on Kalshi's 15-minute commodity markets with real Kalshi quotes and fees.

Markets: KXGOLD15M / KXSILVER15M / KXNATGAS15M / KXWTI15M / KXBRENT15M, "price up in next 15 mins?"
(YES if the Pyth 1-min close at the window end >= the Pyth close at the window start; the market only trades
during its own 15 minutes).  Entry = taker buy at the ask (NO ask = 1 - yes bid) at the end of minute m of the window
(default m=1, i.e. 60 s after the open; the friend's fills are at ~20-25 s), flat $ stake, Kalshi taker fee
0.07*C*p*(1-p) rounded up to the cent per order.

Split fixed before reading results: TRAIN = 2026-08-03 .. 2026-09-30, TEST = 2026-10-01 .. 2026-11-18.
    python research/kalshi_edge_K8/analyze.py            # prints tables, writes research/kalshi_edge_K8/results.json
"""
import collections, datetime, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import k8lib  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN = (datetime.date(2026, 8, 3), datetime.date(2026, 9, 30))
TEST = (datetime.date(2026, 10, 1), datetime.date(2026, 11, 18))
STAKE = 15.0
SER = {"gold": "KXGOLD15M", "silver": "KXSILVER15M", "natgas": "KXNATGAS15M", "wti": "KXWTI15M", "brent": "KXBRENT15M"}
ROLL = set()
for _y, _m in [(2026, 8), (2026, 9), (2026, 10), (2026, 11)]:
    ROLL |= set(k8lib.gsci_roll_days(_y, _m))
# US clocks move 2026-11-01, UK clocks 2026-10-25: 10:30 London = 06:30 ET on these days, 05:30 ET otherwise
DST_GAP = {datetime.date(2026, 10, 26) + datetime.timedelta(days=i) for i in range(5)}


def period(d):
    if TRAIN[0] <= d <= TRAIN[1]:
        return "train"
    if TEST[0] <= d <= TEST[1]:
        return "test"
    return None


_DATA = {}


def data(name):
    """markets (list) + candles (dict ticker -> row) + index (date, hhmm) -> market."""
    if name not in _DATA:
        s = SER[name]
        mk = [m for m in k8lib.load_markets(s) if m["mv"] is not None]
        cd = k8lib.load_candles(s)
        idx = {(m["date"], m["hhmm"]): m for m in mk}
        _DATA[name] = (mk, cd, idx)
    return _DATA[name]


def entry_quote(row, minute=1, max_back=2):
    """(yes_bid, yes_ask) at the end of minute `minute` of the window (falls back up to max_back minutes earlier)."""
    o = row["o"]
    target = o + 60 * minute
    best = None
    for k in row["k"]:
        e, b, a = k[k8lib.E], k[k8lib.BC], k[k8lib.AC]
        if e > target or e < target - 60 * max_back:
            continue
        if b is None or a is None or a <= 0 or b >= 1 or a < b:
            continue
        if b <= 0 and a >= 1:
            continue
        best = (b, a)
    return best


def trade(name, m, side, minute=1, max_price=1.0, min_price=0.0, max_spread=0.10, stake=STAKE):
    """One taker bet on market m: side 'yes' or 'no'. Returns a dict or None (no quote / filtered)."""
    mk, cd, idx = data(name)
    row = cd.get(m["t"])
    if not row:
        return None
    q = entry_quote(row, minute)
    if not q:
        return None
    b, a = q
    if a - b > max_spread:
        return None
    price = a if side == "yes" else round(1 - b, 4)
    if price <= min_price or price > max_price or price >= 0.999:
        return None
    win = m["up"] if side == "yes" else (not m["up"])
    n = max(1, int(stake // price))
    fee = k8lib.fee(price, n)
    cost = n * price + fee
    net = (n - cost) if win else -cost
    return {"date": m["date"], "t": m["t"], "side": side, "price": price, "mid": (a + b) / 2, "spread": a - b,
            "win": win, "n": n, "fee": fee, "cost": cost, "net": net}


def stats(tr):
    if not tr:
        return {"n": 0}
    tr = sorted(tr, key=lambda x: (x["date"], x.get("ts", 0), x["t"]))      # time order (close time) for streaks
    n = len(tr)
    w = [x for x in tr if x["win"]]
    l = [x for x in tr if not x["win"]]
    cost = sum(x["cost"] for x in tr)
    net = sum(x["net"] for x in tr)
    streak = cur = 0
    for x in tr:
        cur = cur + 1 if not x["win"] else 0
        streak = max(streak, cur)
    days = (max(x["date"] for x in tr) - min(x["date"] for x in tr)).days + 1
    months = max(days / 30.44, 0.5)
    # implied (market) win chance at entry for the side bought, vs what happened
    implied = sum((x["mid"] if x["side"] == "yes" else 1 - x["mid"]) for x in tr) / n
    # day-clustered bootstrap-free normal approx of net/$1: per-bet returns
    r = [x["net"] / x["cost"] for x in tr]
    mu = sum(r) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in r) / max(1, n - 1))
    # running max drawdown in $ (flat stake)
    eq = pk = dd = 0.0
    for x in tr:
        eq += x["net"]
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    return {"n": n, "win_rate": round(len(w) / n, 3), "avg_price": round(sum(x["price"] for x in tr) / n, 3),
            "implied_win": round(implied, 3), "avg_win_$": round(sum(x["net"] for x in w) / max(1, len(w)), 2),
            "avg_loss_$": round(sum(x["net"] for x in l) / max(1, len(l)), 2), "net_$": round(net, 2),
            "net_per_$1": round(net / cost, 4), "t_stat": round(mu / (sd / math.sqrt(n)), 2) if sd > 0 else None,
            "worst_streak": streak, "max_dd_$": round(dd, 2), "trades_per_month": round(n / months, 1),
            "usd_per_month": round(net / months, 2), "first": str(tr[0]["date"]), "last": str(tr[-1]["date"])}


def leg_markets(name, hhmm, days=None, london=False):
    """Markets of one window per day. london=True: the window that ends at the same London clock time."""
    mk, cd, idx = data(name)
    out = []
    for m in mk:
        h = m["hhmm"]
        if london:
            want = hhmm if m["date"] not in DST_GAP else "%02d%s" % (int(hhmm[:2]) + 1, hhmm[2:])
            if h != want:
                continue
        elif h != hhmm:
            continue
        if m["date"].weekday() >= 5:
            continue
        if days is not None and m["date"] not in days:
            continue
        out.append(m)
    return out


def run_leg(name, hhmm, side, minute=1, max_price=1.0, min_price=0.0, days=None, london=False, flt=None):
    res = {"train": [], "test": []}
    for m in leg_markets(name, hhmm, days, london):
        p = period(m["date"])
        if not p:
            continue
        if flt and not flt(name, m):
            continue
        t = trade(name, m, side, minute, max_price, min_price)
        if t:
            res[p].append(t)
    return res


# ---------- information a bot has at the window open (no lookahead) ----------
def prior_move(name, m, hours):
    """Pyth % move over the `hours` before the window start, from the chain of 15-min reference prices."""
    mk, cd, idx = data(name)
    o = k8lib_ts(m["open"])
    target = o - int(hours * 3600)
    # the market that CLOSED at target has ev = Pyth price at target; if none (e.g. the 17:00-18:15 break), the first
    # close after target within 90 minutes (still before the window opens, so nothing from the future)
    bc = _by_close(name)
    best = None
    for k in range(0, 7):
        t = target + 900 * k
        if t >= o:
            break
        if bc.get(t):
            best = bc[t][-1]
            break
    if not best or not m["fs"] or not best["ev"]:
        return None
    return (m["fs"] - best["ev"]) / best["ev"]


_BC = {}


def _by_close(name):
    if name not in _BC:
        d = collections.defaultdict(list)
        for mm in data(name)[0]:
            d[k8lib_ts(mm["close"])].append(mm)
        _BC[name] = d
    return _BC[name]


def k8lib_ts(s):
    import calendar, time
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def fmt(s):
    if not s or not s.get("n"):
        return "n=0"
    return ("n=%(n)d win %(win_rate).0f%%  paid %(avg_price).2f (mkt %(implied_win).2f)  net/$1 %(net_per_$1)+.3f  t=%(t_stat)s  "
            "avgW %(avg_win_$)+.2f avgL %(avg_loss_$)+.2f  streak %(worst_streak)d  maxDD %(max_dd_$).0f  "
            "%(trades_per_month).0f/mo  $%(usd_per_month)+.0f/mo" % dict(s, win_rate=100 * s["win_rate"]))


def main():
    out = {"stake_$": STAKE, "train": [str(TRAIN[0]), str(TRAIN[1])], "test": [str(TEST[0]), str(TEST[1])], "legs": {}}
    legs = [
        ("0530 down gold", "gold", "0530", "no", {}),
        ("0530 down silver", "silver", "0530", "no", {}),
        ("0530 down gold (London 10:30)", "gold", "0530", "no", {"london": True}),
        ("0530 down silver (London 10:30)", "silver", "0530", "no", {"london": True}),
        ("1700 up gold", "gold", "1700", "yes", {}),
        ("1700 up silver", "silver", "1700", "yes", {}),
        ("1615 down silver", "silver", "1615", "no", {}),
        ("1615 down gold", "gold", "1615", "no", {}),
        ("1715 up gold (Aug-Sep only)", "gold", "1715", "yes", {}),
        ("1715 up silver (Aug-Sep only)", "silver", "1715", "yes", {}),
        ("roll natgas up 1715", "natgas", "1715", "yes", {"days": ROLL}),
        ("roll wti down 1715", "wti", "1715", "no", {"days": ROLL}),
        ("roll brent down 1745", "brent", "1745", "no", {"days": ROLL}),
        ("roll natgas up 1615", "natgas", "1615", "yes", {"days": ROLL}),
        ("roll brent down 1615", "brent", "1615", "no", {"days": ROLL}),
    ]
    for minute in (1, 2, 5):
        print("\n=== entry at the end of minute %d of the window, flat $%.0f, taker, fee in ===" % (minute, STAKE))
        for lab, name, hh, side, kw in legs:
            r = run_leg(name, hh, side, minute=minute, **kw)
            st = {p: stats(v) for p, v in r.items()}
            out["legs"].setdefault(lab, {})["m%d" % minute] = st
            print("%-34s TRAIN %s" % (lab, fmt(st["train"])))
            print("%-34s TEST  %s" % ("", fmt(st["test"])))
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
