#!/usr/bin/env python3
"""K6 study 1: Kalshi Treasury-yield markets priced from the OFFICIAL daily par yields (FRED = Treasury's own curve,
the exact numbers the markets settle on; checked: 0 mismatches) plus a volatility model fitted on older data only.

Decision time: the evening of each business day d (the hourly quote that ends between 01:00 and 03:00 UTC of the next
day = 20:00-23:00 ET), when day d's official yield is already public (assumed public at 18:30 ET; Treasury posts by
about 6 pm). So the model knows the same closing level as the crowd; only the distribution of the next moves is
modelled. info_ts = 18:30 ET of day d, order ts = the quote's candle end.

Model: next daily changes are Student-t (df NU) with standard deviation K x EWMA(half-life H) of past official daily
changes; an FOMC day inside the horizon multiplies that day's variance by F. Terminal markets (above / below / bucket)
use the sum over the remaining business days; "how high / how low" (barrier) markets use 6,000 simulated daily paths.
Parameters and the trading margin are fixed on the OLDER half; the newer half is read once.

    python research/kalshi_edge_K6/yields.py            # -> results_yields.json, trades_yields_test.json
"""
import bisect, calendar, datetime as dt, glob, gzip, json, math, os, re, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("K6_OFFLINE", "1")
import kk6

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = os.environ.get("K6_SPLIT", "2025-01-01")  # older half: settle before this date; newer half (held out): on / after
NEWEST = "2026-07-01"         # the newest series (KXUST*A, how-high / how-low) all settle after this
SERIES = {"KXTNOTED": "DGS10", "KXTNOTEW": "DGS10", "KXUST10A": "DGS10", "KXUST2A": "DGS2", "KXUST5A": "DGS5",
          "KXUST30A": "DGS30", "KX10YRDIRHW": "DGS10", "KX10YRDIRLW": "DGS10", "KX10YRDIRHM": "DGS10",
          "KX10YRDIRLM": "DGS10", "KX2YRDIRHM": "DGS2", "KX2YRDIRLM": "DGS2", "KX5YRDIRHM": "DGS5", "KX30YRDIRHM": "DGS30"}
# barrier series NOT looked at before the barrier lead was noticed: used only by replicate_barrier.py
REPLICATION = {"KX5YRDIRLM": "DGS5", "KX30YRDIRLM": "DGS30", "KX7YRDIRHM": "DGS7", "KX7YRDIRLM": "DGS7"}
COMPLETE_BEFORE = "2026-11-18"   # harvest day: barrier events whose window ends on/after this are incomplete
MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def et_offset(day):
    """hours UTC is ahead of US Eastern on that date (DST: 2nd Sunday March .. 1st Sunday November)."""
    y = day.year
    m2 = dt.date(y, 3, 8 + (6 - dt.date(y, 3, 8).weekday()) % 7)
    n1 = dt.date(y, 11, 1 + (6 - dt.date(y, 11, 1).weekday()) % 7)
    return 4 if m2 <= day < n1 else 5


def utc_ts(day, hh, mm=0):
    return calendar.timegm((day.year, day.month, day.day, hh, mm, 0)) + 0


def info_ts(day):
    """18:30 ET of `day` as unix seconds (the assumed publication time of that day's official yield)."""
    return calendar.timegm((day.year, day.month, day.day, 18, 30, 0)) + et_offset(day) * 3600


def tcdf_table(nu):
    x = np.linspace(-40, 40, 160001)
    if nu >= 200:
        pdf = np.exp(-0.5 * x * x)
    else:
        pdf = (1 + x * x / nu) ** (-(nu + 1) / 2)
    c = np.cumsum(pdf)
    c = (c - c[0]) / (c[-1] - c[0])
    return x, c


_TT = {}


def tcdf(z, nu):
    if nu not in _TT:
        _TT[nu] = tcdf_table(nu)
    x, c = _TT[nu]
    return np.interp(z, x, c)


def t_std_scale(nu):
    return 1.0 if nu >= 200 else math.sqrt((nu - 2) / nu)


class Yields:
    def __init__(self):
        self.f = json.load(open(os.path.join(kk6.DATA, "fred.json")))
        self.days = {s: sorted(self.f[s]) for s in self.f}
        self.bdays = self.days["DGS10"]           # official business days (holidays are known in advance)

    def known(self, s, day):
        """official values of series s for days <= day (ISO)."""
        ds = self.days[s]
        i = bisect.bisect_right(ds, day)
        return ds[:i]

    def ewma_sd(self, s, day, hl):
        ds = self.known(s, day)[-400:]
        v = np.array([self.f[s][d] for d in ds])
        ch = np.diff(v)
        if len(ch) < 30:
            return None
        lam = 0.5 ** (1.0 / hl)
        w = lam ** np.arange(len(ch))[::-1]
        return float(math.sqrt(np.sum(w * ch * ch) / np.sum(w)))

    def future_bdays(self, after, upto):
        """business days in (after, upto], ISO strings; past days from the official calendar, beyond it weekdays."""
        out = [d for d in self.bdays if after < d <= upto]
        last = self.bdays[-1]
        d = max(dt.date.fromisoformat(after), dt.date.fromisoformat(last))
        end = dt.date.fromisoformat(upto)
        while d < end:
            d += dt.timedelta(days=1)
            if d.weekday() < 5 and d.isoformat() > last:
                out.append(d.isoformat())
        return out


def fomc_days():
    out = set()
    for s in ("KXFEDDECISION", "KXFED"):
        for m in kk6.markets(s, historical=True) + kk6.markets(s):
            r = m.get("rules_primary") or ""
            mm = re.search(r"Federal Reserve's ([A-Z][a-z]+) (\d{4}) meeting", r)
            # the decision day = the market's close date (markets close around the statement)
            out.add(m["close_time"][:10])
    return out


def window_of(m):
    """barrier markets: (first, last) business day of the 'between X and Y' window from the rule text."""
    r = m.get("rules_primary") or ""
    mm = re.search(r"between ([A-Z][a-z]{2})[a-z]* (\d{1,2}), (\d{4}) and ([A-Z][a-z]{2})[a-z]* (\d{1,2}), (\d{4})", r)
    if not mm:
        return None
    a = dt.date(int(mm.group(3)), MON[mm.group(1)], int(mm.group(2))).isoformat()
    b = dt.date(int(mm.group(6)), MON[mm.group(4)], int(mm.group(5))).isoformat()
    return a, b


def load_rows(series=None):
    rows = []
    for s in (series or SERIES):
        fn = os.path.join(kk6.DATA, f"q_{s}.jsonl.gz")
        if not os.path.exists(fn):
            continue
        lst = {m["ticker"]: m for m in kk6.markets(s, historical=True) + kk6.markets(s)}
        for line in gzip.open(fn, "rt"):
            r = json.loads(line)
            r["series"] = s
            m = lst.get(r["t"], {})
            r["barrier"] = "DIR" in s
            if r["barrier"]:
                w = window_of(m)
                if not w:
                    continue
                r["w0"], r["w1"] = w
                if r["w1"] >= COMPLETE_BEFORE:      # window still open: only the strikes already HIT are settled,
                    continue                        # so keeping them would bias the sample toward YES
                r["dirn"] = "up" if re.search(r"DIRH[MW]$", s) else "down"
            rows.append(r)
    return rows


def settle_day(r):
    return r["w1"] if r.get("barrier") else time_day(r["ct"])


def time_day(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()


def strike_win_prob(r, y_paths_end=None, y_paths_ext=None, mu=None, sd=None, nu=None):
    """P(YES) for one market given either a terminal t distribution (mu, sd, nu) or simulated paths."""
    fs, cs, st = r["fs"], r["cs"], r["st"]
    if r.get("barrier"):
        k = fs if fs is not None else cs
        if r["dirn"] == "up":
            return float(np.mean(y_paths_ext > k + 1e-9))       # 'above k' on any day: max > k (2-dec values: >= k+0.01)
        return float(np.mean(y_paths_ext < k - 1e-9))
    sc = sd * t_std_scale(nu)

    def cdf(x):
        return float(tcdf((x - mu) / sc, nu)) if sc > 0 else float(x >= mu)
    if st == "greater":
        return 1 - cdf(fs + 0.005)
    if st == "less":
        return cdf(cs - 0.005)
    if st == "between":
        return cdf(cs + 0.005) - cdf(fs - 0.005)
    return None


def decision_points(r, Y):
    """(day d, quote) for each business day d whose evening falls inside the market's life."""
    out = []
    c = r["c"]
    if not c:
        return out
    ts_list = [x[0] for x in c]
    sday = settle_day(r)
    i0 = bisect.bisect_left(Y.bdays, time_day(r["ot"] - 86400 * 2))
    i1 = bisect.bisect_left(Y.bdays, sday)
    for d in Y.bdays[i0:i1]:
        dd = dt.date.fromisoformat(d)
        nxt = dd + dt.timedelta(days=1)
        lo, hi = utc_ts(nxt, 1), utc_ts(nxt, 3)
        if hi <= r["ot"] or lo >= r["ct"]:
            continue
        i = bisect.bisect_right(ts_list, hi) - 1
        if i < 0 or ts_list[i] < lo or ts_list[i] <= info_ts(dd):
            continue
        out.append((d, c[i]))
    return out


CENTER = bool(os.environ.get("K6_CENTER"))   # variant: centre the model on the market's own median (tests width only)


def market_median(rs, dps, d):
    """the yield level where the market's own CDF (from all quoted strikes of the event that evening) crosses 50%."""
    pts = []
    q = {r["t"]: dict(dps[r["t"]]).get(d) for r in rs}
    mids = {t: (v[1] + v[2]) / 200.0 for t, v in q.items() if v and v[2] - v[1] <= 10}
    less = [r for r in rs if r["st"] == "less" and r["t"] in mids]
    for r in rs:
        if r["t"] in mids and r["st"] == "greater":
            pts.append((r["fs"] + 0.005, 1 - mids[r["t"]]))
        if r["t"] in mids and r["st"] == "less":
            pts.append((r["cs"] - 0.005, mids[r["t"]]))
    if less:
        acc, top = mids[less[0]["t"]], less[0]["cs"]
        for r in sorted([r for r in rs if r["st"] == "between"], key=lambda r: r["fs"]):
            if r["fs"] < top - 1e-9:
                continue
            if abs(r["fs"] - top) > 1e-6 or r["t"] not in mids:
                break
            acc += mids[r["t"]]
            top = r["cs"] + 0.01
            pts.append((r["cs"] + 0.005, acc))
    if len(pts) < 2:
        return None
    pts.sort()
    xs = [x for x, _ in pts]
    fs_ = np.maximum.accumulate([f for _, f in pts])
    if fs_[0] > 0.5 or fs_[-1] < 0.5:
        return None
    return float(np.interp(0.5, fs_ + np.arange(len(fs_)) * 1e-9, xs))


def build_obs(rows, Y, fomc, H, K, NU, F, rng):
    """one observation per (market, evening): model P(YES), quote, outcome."""
    obs = []
    by_ev = {}
    for r in rows:
        by_ev.setdefault((r["series"], r["e"]), []).append(r)
    for (s, e), rs in by_ev.items():
        ys = SERIES.get(s) or REPLICATION[s]
        cache = {}
        dps = {r["t"]: decision_points(r, Y) for r in rs}
        for r in rs:
            sday = settle_day(r)
            for d, q in dps[r["t"]]:
                if d not in Y.f[ys]:
                    continue
                key = d
                if key not in cache:
                    sd1 = Y.ewma_sd(ys, d, H)
                    if sd1 is None:
                        cache[key] = None
                        continue
                    y0 = Y.f[ys][d]
                    fut = Y.future_bdays(d, sday)
                    var_mult = np.array([F if x in fomc else 1.0 for x in fut])
                    if r.get("barrier"):
                        w_days = [x for x in fut if x >= r["w0"]]
                        past = [Y.f[ys][x] for x in Y.known(ys, d) if x >= r["w0"]]
                        steps = rng.standard_t(NU, size=(6000, len(fut))) * t_std_scale(NU) if NU < 200 else \
                            rng.standard_normal((6000, len(fut)))
                        steps = steps * (K * sd1) * np.sqrt(var_mult)[None, :]
                        paths = y0 + np.cumsum(steps, axis=1)
                        paths = np.round(paths, 2)
                        inwin = np.array([x >= r["w0"] for x in fut])
                        if inwin.any():
                            mx = paths[:, inwin].max(axis=1)
                            mn = paths[:, inwin].min(axis=1)
                        else:
                            mx = np.full(6000, -1e9)
                            mn = np.full(6000, 1e9)
                        if past:
                            mx = np.maximum(mx, max(past))
                            mn = np.minimum(mn, min(past))
                        cache[key] = ("b", mx, mn)
                    else:
                        mu = y0
                        if CENTER:
                            mu = market_median(rs, dps, d)
                        cache[key] = None if mu is None else ("t", mu, K * sd1 * math.sqrt(float(var_mult.sum())))
                cc = cache[key]
                if cc is None:
                    continue
                if cc[0] == "b":
                    p = strike_win_prob(r, y_paths_ext=cc[1] if r["dirn"] == "up" else cc[2])
                else:
                    p = strike_win_prob(r, mu=cc[1], sd=cc[2], nu=NU)
                if p is None:
                    continue
                obs.append({"t": r["t"], "e": e, "s": s, "d": d, "ts": q[0], "info": info_ts(dt.date.fromisoformat(d)),
                            "bid": q[1], "ask": q[2], "qv": q[3], "p": min(max(p, 0.0005), 0.9995),
                            "y": 1 if r["res"] == "yes" else 0, "settle": sday, "ct": r["ct"]})
    return obs


def logloss(obs):
    return float(np.mean([-(o["y"] * math.log(o["p"]) + (1 - o["y"]) * math.log(1 - o["p"])) for o in obs]))


def brier(ps, ys):
    return float(np.mean([(p - y) ** 2 for p, y in zip(ps, ys)]))


def trades(obs, margin, max_spread, pmin=0.03, pmax=0.97):
    """first evening per market where the model beats the ask (or 1 - bid for NO) by more than fee + margin."""
    out, seen = [], set()
    for o in sorted(obs, key=lambda o: o["ts"]):
        if o["t"] in seen:
            continue
        b, a = o["bid"] / 100.0, o["ask"] / 100.0
        if a - b > max_spread / 100.0 or a <= 0 or b >= 1:
            continue
        cand = []
        if pmin <= a <= pmax:
            c, fe = kk6.fee_order(a)
            cand.append(("yes", a, o["p"] - a - fe / c))
        na = 1 - b
        if pmin <= na <= pmax:
            c, fe = kk6.fee_order(na)
            cand.append(("no", na, (1 - o["p"]) - na - fe / c))
        cand = [x for x in cand if x[2] > margin]
        if not cand:
            continue
        side, px, edge = max(cand, key=lambda x: x[2])
        won = (o["y"] == 1) if side == "yes" else (o["y"] == 0)
        seen.add(o["t"])
        out.append(dict(o, side=side, price=px, edge=edge, won=int(won), r=kk6.pnl_per_dollar(px, won)))
    return out


def summarize(tr, days=None):
    if not tr:
        return {"n": 0}
    v = np.array([x["r"] for x in tr])
    ev = {}
    for x in tr:
        ev.setdefault(x["e"], []).append(x["r"])
    sums = np.array([sum(g) for g in ev.values()])
    ns = np.array([len(g) for g in ev.values()])
    rng = np.random.default_rng(11)
    k = len(sums)
    bs = []
    for _ in range(2000):
        i = rng.integers(0, k, k)
        bs.append(sums[i].sum() / ns[i].sum())
    bs = np.sort(bs)
    first = min(x["ts"] for x in tr)
    last = max(x["ts"] for x in tr)
    span = max((last - first) / 86400.0, 1.0) if days is None else days
    cost = sum(kk6.fee_order(x["price"])[0] * x["price"] + kk6.fee_order(x["price"])[1] for x in tr)
    pnl = sum(x["r"] * (kk6.fee_order(x["price"])[0] * x["price"] + kk6.fee_order(x["price"])[1]) for x in tr)
    return {"n": len(tr), "events": k, "win": float(np.mean([x["won"] for x in tr])),
            "avg_price": float(np.mean([x["price"] for x in tr])), "net_per_dollar": float(pnl / cost),
            "mean_r": float(v.mean()), "lo": float(bs[50]), "hi": float(bs[1949]),
            "trades_month": len(tr) / span * 30.4, "usd_month_10": float(pnl / cost) * 10 * len(tr) / span * 30.4}


def main():
    Y = Yields()
    fomc = fomc_days()
    rows = [r for r in load_rows() if r["c"]]
    print("markets with quotes", len(rows), {s: sum(1 for r in rows if r["series"] == s) for s in SERIES}, flush=True)
    rng = np.random.default_rng(5)
    train_rows = [r for r in rows if settle_day(r) < SPLIT]
    test_rows = [r for r in rows if settle_day(r) >= SPLIT]
    # 1. fit the vol model on the older half (log loss of outcomes), small grid
    fits = []
    for H in (10, 30, 90):
        for NU in (4, 8, 400):
            for K in (0.8, 0.9, 1.0, 1.1, 1.25, 1.4):
                for F in (1.0, 2.5):
                    ob = build_obs(train_rows, Y, fomc, H, K, NU, F, rng)
                    if len(ob) < 50:
                        continue
                    fits.append((logloss(ob), H, NU, K, F, len(ob)))
    fits.sort()
    print("best fits (logloss, H, NU, K, F, n):", fits[:5], flush=True)
    _, H, NU, K, F, _ = fits[0]
    ob_tr = build_obs(train_rows, Y, fomc, H, K, NU, F, rng)
    ob_te = build_obs(test_rows, Y, fomc, H, K, NU, F, rng)
    res = {"params": {"half_life_days": H, "df": NU, "k": K, "fomc_var_mult": F}, "split": SPLIT,
           "fits_top": fits[:10], "n_obs": {"train": len(ob_tr), "test": len(ob_te)}}

    def mid_brier(ob):
        ok = [o for o in ob if o["ask"] - o["bid"] <= 10]
        return {"n": len(ok), "market_mid": brier([(o["bid"] + o["ask"]) / 200 for o in ok], [o["y"] for o in ok]),
                "model": brier([o["p"] for o in ok], [o["y"] for o in ok])}
    res["brier"] = {"train": mid_brier(ob_tr), "test": mid_brier(ob_te),
                    "test_newest": mid_brier([o for o in ob_te if o["settle"] >= NEWEST])}
    # 2. trading margin and spread cap chosen on the older half only
    grid = []
    for mg in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20):
        for sp in (4, 6, 10, 20):
            tr = trades(ob_tr, mg, sp)
            s = summarize(tr)
            if s["n"] >= 30:
                grid.append((s["net_per_dollar"], mg, sp, s["n"]))
    grid.sort(reverse=True)
    res["train_grid_top"] = grid[:10]
    best = grid[0] if grid else (None, 0.1, 10, 0)
    mg, sp = best[1], best[2]
    tr_tr, tr_te = trades(ob_tr, mg, sp), trades(ob_te, mg, sp)
    res["rule"] = {"margin": mg, "max_spread_c": sp}
    res["train"] = summarize(tr_tr)
    res["test"] = summarize(tr_te)
    res["test_newest"] = summarize([x for x in tr_te if x["settle"] >= NEWEST])
    res["test_by_series"] = {s: summarize([x for x in tr_te if x["s"] == s]) for s in SERIES}
    res["test_weekly_10y_2025_26"] = summarize([x for x in tr_te if x["s"] == "KXTNOTEW"])
    res["test_terminal"] = summarize([x for x in tr_te if "DIR" not in x["s"]])
    res["test_barrier"] = summarize([x for x in tr_te if "DIR" in x["s"]])
    res["test_quote_hour_traded_share"] = float(np.mean([x["qv"] > 0 for x in tr_te])) if tr_te else None
    res["test_by_side"] = {k: summarize([x for x in tr_te if x["side"] == k]) for k in ("yes", "no")}
    res["test_all_cells"] = {f"m{mg2}_s{sp2}": summarize(trades(ob_te, mg2, sp2)) for mg2 in (0.02, 0.05, 0.10, 0.15)
                             for sp2 in (6, 10)}
    # control: buy every quoted YES / NO at the ask (first evening), spread cap as chosen
    res["control_test"] = summarize(trades(ob_te, -9, sp))
    tag = "_center" if CENTER else ""
    json.dump(res, open(os.path.join(HERE, f"results_yields{tag}.json"), "w"), indent=1)
    vt = [{"ts": x["ts"], "info_ts": x["info"], "price": x["price"], "contracts": kk6.fee_order(x["price"])[0],
           "outcome": x["won"], "event": x["e"], "ticker": x["t"], "settle_ts": x["ct"]} for x in tr_te]
    json.dump({"rule": res["rule"], "trades": vt}, open(os.path.join(HERE, f"trades_yields{tag}_test.json"), "w"))
    print(json.dumps({k: res[k] for k in ("params", "n_obs", "brier", "rule", "train", "test", "test_newest", "test_by_side",
                                           "control_test")}, indent=1))


if __name__ == "__main__":
    main()
