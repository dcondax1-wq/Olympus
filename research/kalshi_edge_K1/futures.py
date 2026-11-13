"""Futures bars (TradingView CME NQ1!/ES1! exports in data/, futures only) + VXN/VIX daily closes (CBOE files in data/),
and the index level implied by the futures at any minute: index ~= futures - basis, where basis is measured at the most
recent Kalshi settlement (Kalshi publishes the index value it settled on) that is at or before the decision time.
Bars are additively back-adjusted per contract, so a basis is only reused while no roll lies between the two times."""
import bisect, csv, json, math, os

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
D = os.path.join(REPO, "data")


def _bars(fn, lo=1766000000):
    t, o, c = [], [], []
    with open(fn) as fh:
        r = csv.reader(fh)
        next(r)
        for row in r:
            ts = int(float(row[0]))
            if ts < lo:
                continue
            t.append(ts); o.append(float(row[1])); c.append(float(row[4]))
    return t, o, c


class Fut:
    def __init__(self, sym):
        self.sym = sym
        if sym == "NQ" and os.path.exists(os.path.join(D, "NQ_1m.csv")):
            self.t, self.o, self.c = _bars(os.path.join(D, "NQ_1m.csv"))
            self.step = 60
        else:
            self.t, self.o, self.c = _bars(os.path.join(D, f"{sym}_5m.csv"))
            self.step = 300
        self.idx = {x: i for i, x in enumerate(self.t)}
        rolls = json.load(open(os.path.join(D, f"{sym}_rolls.json"))).get("rolls", [])
        self.switch = sorted(r["switch_t"] for r in rolls)
        self.last = self.t[-1]

    def price_at(self, ts):
        """futures price at the instant ts: open of the bar starting at ts (else the close of the bar just before)."""
        i = self.idx.get(ts)
        if i is not None:
            return self.o[i]
        j = bisect.bisect_right(self.t, ts) - 1
        if j >= 0 and ts - self.t[j] <= self.step + 60 * 5:
            return self.c[j]
        return None

    def rolled_between(self, a, b):
        return any(a < s <= b for s in self.switch)

    def rv(self, ts, minutes):
        """realised variance per minute from log returns of bar closes over the `minutes` before ts."""
        j = bisect.bisect_left(self.t, ts) - 1
        if j < 2:
            return None
        lo = ts - minutes * 60
        rs = []
        k = j
        while k > 0 and self.t[k - 1] >= lo:
            if self.t[k] - self.t[k - 1] <= self.step * 3 and not self.rolled_between(self.t[k - 1], self.t[k]):
                rs.append(math.log(self.c[k] / self.c[k - 1]))
            k -= 1
        if len(rs) < max(5, 0.5 * minutes * 60 / self.step):
            return None
        return sum(x * x for x in rs) / (len(rs) * self.step / 60.0)


def daily(fn, col):
    out = {}
    with open(fn) as fh:
        for r in csv.DictReader(fh):
            try:
                out[r["date"]] = float(r[col])
            except (TypeError, ValueError):
                pass
    return out


def prev_close(series, day):
    """last value strictly before the ET date `day` (YYYY-MM-DD): known at the open of `day`."""
    ks = sorted(series)
    i = bisect.bisect_left(ks, day) - 1
    return series[ks[i]] if i >= 0 else None


VXN = daily(os.path.join(D, "VXN_1d.csv"), "close")
VIX = daily(os.path.join(D, "VIX_1d.csv"), "close")
