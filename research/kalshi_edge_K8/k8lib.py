"""K8 shared helpers: load the harvested market lists / minute quotes, ET calendar, fees."""
import collections, datetime, json, math, os

CACHE = "/home/user/kalshi_cache/kmetal"
MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


def day_of(code):
    """'26NOV12' -> datetime.date(2026, 11, 12) (Kalshi event tickers carry the ET date)."""
    return datetime.date(2000 + int(code[:2]), MON.index(code[2:5]) + 1, int(code[5:7]))


def load_markets(series):
    """Settled 15-min markets: list of dicts (date = ET date of the close, hhmm = ET close time)."""
    out = []
    for l in open(os.path.join(CACHE, "mk_%s.jsonl" % series)):
        r = json.loads(l)
        if r.get("result") not in ("yes", "no"):
            continue
        fs, ev = fnum(r.get("floor_strike")), fnum(r.get("expiration_value"))
        code = r["event_ticker"].split("-")[1]
        out.append({"t": r["ticker"], "date": day_of(code[:7]), "hhmm": code[7:11], "up": r["result"] == "yes",
                    "fs": fs, "ev": ev, "mv": (ev - fs) if (fs is not None and ev is not None) else None,
                    "vol": fnum(r.get("volume_fp")) or 0.0, "close": r["close_time"], "open": r["open_time"],
                    "settle_ts": r.get("settlement_ts")})
    return out


def load_candles(series):
    """Minute quotes per market ticker (from harvest_candles.py)."""
    fn = os.path.join(CACHE, "cd_%s.jsonl" % series)
    out = {}
    if not os.path.exists(fn):
        return out
    for l in open(fn):
        try:
            r = json.loads(l)
        except Exception:
            continue
        out[r["t"]] = r
    return out


# candle row layout from harvest_candles.compact_candles
E, BC, AC, BH, BL, AH, AL, PO, PH, PL, PC, V, OI = range(13)


def quote_at(row, ts):
    """Yes bid / ask at the END of the minute that ends at ts (the last candle with end <= ts that has a 2-sided book).
    Returns (bid, ask, candle) or None."""
    best = None
    for k in row["k"]:
        if k[E] <= ts and k[BC] is not None and k[AC] is not None and 0 < k[AC] and k[BC] < 1 and k[AC] > k[BC] - 1e-9:
            if k[BC] > 0 or k[AC] < 1:
                best = k
    if not best:
        return None
    return best[BC], best[AC], best


def fee(p, n=1, rate=0.07):
    """Kalshi taker fee ($) for n contracts at price p ($), rounded up to the cent."""
    return math.ceil(round(rate * n * p * (1 - p) * 100, 6)) / 100.0


def pnl_taker(price, win, stake=15.0):
    """Net $ of buying `stake` dollars of one side at `price` as a taker (whole contracts), and $ risked."""
    n = max(1, int(stake // price))
    cost = n * price + fee(price, n)
    pay = n * 1.0 if win else 0.0
    return pay - cost, cost


def business_days(year, month, holidays=()):
    d = datetime.date(year, month, 1)
    out = []
    while d.month == month:
        if d.weekday() < 5 and d not in holidays:
            out.append(d)
        d += datetime.timedelta(days=1)
    return out


# NYMEX / CME US holidays that matter for 2026 business-day counts (Labor Day, Thanksgiving, Christmas, New Year)
US_HOLIDAYS = {datetime.date(2026, 9, 7), datetime.date(2026, 11, 26), datetime.date(2026, 12, 25),
               datetime.date(2027, 1, 1), datetime.date(2026, 7, 3), datetime.date(2026, 5, 25), datetime.date(2026, 1, 19),
               datetime.date(2026, 2, 16), datetime.date(2026, 4, 3), datetime.date(2026, 6, 19)}


def gsci_roll_days(year, month):
    """5th..9th business day of the month (S&P GSCI-style roll window)."""
    b = business_days(year, month, US_HOLIDAYS)
    return b[4:9]
