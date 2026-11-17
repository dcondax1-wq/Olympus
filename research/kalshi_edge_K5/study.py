#!/usr/bin/env python3
"""K5 'answer partly public before close' study on slow niche Kalshi series (hourly public candles, settled history).
Taker buys at the ask (NO = 1 - yes bid), fee 0.07 x C x p x (1-p) rounded up on a $10 order (lib.fee_per_contract).
Strict time split per series (SPLIT below, fixed before any outcome was looked at): train = earlier closes, test = later,
read once. Cells: series x hours-before-close x role (favourite / underdog, or model signal) x price band. A cell is
carried to the test only if its training t-stat beats a one-sided Bonferroni bar over EVERY cell scored in training.
Pre-registered 'known answer' cells (PREREG) are reported on the test half whatever their training result.
    python research/kalshi_edge_K5/study.py            -> results.json + printed tables
"""
import gzip, json, math, os, sys, collections, datetime as dt
from statistics import NormalDist
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import pnl_per_dollar, summary, tstat  # noqa: E402
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
def D(s): return dt.datetime.fromisoformat(s + "T00:00:00+00:00").timestamp()

# hours before close to decide at, and the train/test split date (closes on/after SPLIT = test)
CFG = {
    "KXYTVIEWSW":     {"hours": [6, 12, 24, 36], "split": "2026-10-12"},  # window ends ~38 h before close
    "KXTRUTHSOCIAL":  {"hours": [2, 5, 9], "split": "2026-10-01"},        # window ends ~10 h before close
    "KXTRUTHSOCIALD": {"hours": [1, 3, 6], "split": "2026-10-25"},        # late in the counted day
    "KXTSAW":         {"hours": [3, 8, 16], "split": "2025-12-01"},       # Sunday: Mon-Sat numbers already public
    "KXAAAGASD":      {"hours": [2, 8, 16], "split": "2026-09-01"},       # value of the day before is public
    "KXAAAGASW":      {"hours": [2, 8, 16, 40], "split": "2026-09-01"},
    "KXAAAGASM":      {"hours": [2, 8, 16, 40], "split": "2026-09-01"},
    "KXAPPRANKFREE":  {"hours": [1, 3, 8], "split": "2025-08-01"},        # live Apple chart public all day
    "KXSPOTIFYD":     {"hours": [1, 4, 8], "split": "2025-12-01"},        # yesterday's chart public before close
    "KXNETFLIXRANKSHOW": {"hours": [2, 8, 24], "split": "2026-03-01"},    # FlixPatrol dailies public during the week
}
BANDS = [(0.03, 0.20), (0.20, 0.50), (0.50, 0.80), (0.80, 0.90), (0.90, 0.95), (0.95, 0.985)]
MAXSPREAD = 0.06
# pre-registered 'known answer' cells: (series, hours, role, band)
PREREG = [("KXYTVIEWSW", 12, "fav", (0.80, 0.985)), ("KXTRUTHSOCIAL", 5, "fav", (0.80, 0.985)),
          ("KXTRUTHSOCIALD", 1, "fav", (0.80, 0.985)), ("KXTSAW", 8, "fav", (0.80, 0.985)),
          ("KXAPPRANKFREE", 1, "fav", (0.80, 0.985)), ("KXSPOTIFYD", 4, "persist", (0.03, 0.985)),
          ("KXAAAGASD", 8, "model", (0.03, 0.985)), ("KXAAAGASW", 8, "model", (0.03, 0.985))]


def load(s):
    fn = os.path.join(RAW, s + "_c.json.gz")
    return json.load(gzip.open(fn, "rt")) if os.path.exists(fn) else []


def quote(r, t):
    """last hourly candle ending at or before t with a usable two-sided quote."""
    best = None
    for c in r.get("c") or []:
        if c[0] <= t and c[1] is not None and c[2] is not None:
            best = c
    if not best or not (0 < best[1] < best[2] < 1) or best[2] - best[1] > MAXSPREAD:
        return None
    if t - best[0] > 3 * 3600:
        return None
    return best[1], best[2]


def gas_values():
    """AAA national daily value by date, from the settled KXAAAGASD / KXAAAGASW / KXAAAGASM markets (public)."""
    v = {}
    for s in ("KXAAAGASD", "KXAAAGASW", "KXAAAGASM"):
        fn = os.path.join(RAW, s + "_list.json.gz")
        if not os.path.exists(fn):
            continue
        for r in json.load(gzip.open(fn, "rt")):
            try:
                x = float(str(r["ev"]).replace(",", ""))
            except Exception:
                continue
            day = r["e"].split("-")[-1]  # 26NOV17
            try:
                d = dt.datetime.strptime(day, "%y%b%d").date()
            except Exception:
                continue
            v[d] = x
    return v


def gas_target(r):
    return dt.datetime.strptime(r["e"].split("-")[-1], "%y%b%d").date()


def units(s, rows, gas=None, gas_fit=None):
    """one unit per (market, hours, side). role: fav / dog by the side's price, persist (Spotify), model (gas)."""
    out = []
    cfg = CFG[s]
    prev_winner = {}
    if s in ("KXSPOTIFYD", "KXAPPRANKFREE"):
        ev = {}
        for r in rows:
            ev[r["e"]] = r["ev"]
        for e, w in ev.items():
            try:
                d = dt.datetime.strptime(e.split("-")[-1], "%y%b%d").date()
            except Exception:
                continue
            prev_winner[d + dt.timedelta(days=1)] = (w or "").strip().lower()
    for r in rows:
        for h in cfg["hours"]:
            t = r["close"] - h * 3600
            q = quote(r, t)
            if not q:
                continue
            bid, ask = q
            for side in ("yes", "no"):
                p = ask if side == "yes" else 1 - bid
                if not 0.03 <= p <= 0.985:
                    continue
                won = (r["res"] == side)
                u = {"s": s, "t": r["t"], "h": h, "side": side, "p": p, "won": won, "ts": r["close"],
                     "cl": r["e"], "r": pnl_per_dollar(p, won), "test": r["close"] >= D(cfg["split"]),
                     "role": "fav" if p >= 0.5 else "dog"}
                out.append(u)
                if s in ("KXSPOTIFYD", "KXAPPRANKFREE"):
                    try:
                        d = dt.datetime.strptime(r["e"].split("-")[-1], "%y%b%d").date()
                    except Exception:
                        continue
                    pw = prev_winner.get(d)
                    if pw:
                        same = (r["sub"] or "").strip().lower() == pw
                        # 'persist' = back yesterday's #1 (YES on it), 'change' = bet against it (NO on it)
                        if same and side == "yes":
                            out.append(dict(u, role="persist"))
                        if same and side == "no":
                            out.append(dict(u, role="change"))
                if gas is not None and gas_fit is not None:
                    try:
                        D0 = gas_target(r)
                    except Exception:
                        continue
                    # what is public at decision time t: AAA posts the day's value early morning ET (~ 08 UTC)
                    known = dt.datetime.fromtimestamp(t - 8 * 3600, dt.timezone.utc).date()
                    v1 = gas.get(known); v2 = gas.get(known - dt.timedelta(days=1))
                    if v1 is None or v2 is None or r["fl"] is None:
                        continue
                    k = (D0 - known).days
                    if k < 1 or k > 8:
                        continue
                    b, sd1 = gas_fit
                    # AR(1) on daily changes: mean path of the next k changes, sd grows with the horizon
                    d1 = v1 - v2
                    mu = v1 + sum(d1 * b ** j for j in range(1, k + 1))
                    sd = sd1 * math.sqrt(sum(sum(b ** (2 * i) for i in range(j)) for j in range(1, k + 1)) / 1.0)
                    pyes = 1 - NormalDist(mu, max(sd, 1e-4)).cdf(r["fl"])
                    pm = pyes if side == "yes" else 1 - pyes
                    gap = pm - p
                    if gap >= 0.05:
                        out.append(dict(u, role="model"))
    return out


def fit_gas(gas, last_day):
    """AR(1) coefficient and residual sd of AAA daily changes, on days before the split only."""
    ds = sorted(d for d in gas if d < last_day)
    ch = [(d, gas[d] - gas[d - dt.timedelta(days=1)]) for d in ds if d - dt.timedelta(days=1) in gas]
    chd = dict(ch)
    pairs = [(chd[d - dt.timedelta(days=1)], c) for d, c in ch if d - dt.timedelta(days=1) in chd]
    sxx = sum(a * a for a, _ in pairs); sxy = sum(a * c for a, c in pairs)
    b = sxy / sxx if sxx else 0.0
    res = [c - b * a for a, c in pairs]
    sd = math.sqrt(sum(x * x for x in res) / max(len(res) - 1, 1))
    # fat tails: inflate sd by 1.25 (set before looking at any market outcome)
    return b, sd * 1.25, len(pairs)


def cells(us):
    g = collections.defaultdict(list)
    for u in us:
        for lo, hi in BANDS:
            if lo <= u["p"] < hi:
                g[(u["s"], u["h"], u["role"], (lo, hi))].append(u)
    return g


def days_of(us):
    if not us:
        return 1
    return max(1.0, (max(u["ts"] for u in us) - min(u["ts"] for u in us)) / 86400 + 7)


def main():
    allu = []
    gas = gas_values()
    info = {}
    for s in CFG:
        rows = load(s)
        if not rows:
            print("no data", s); continue
        gf = None
        if s.startswith("KXAAAGAS"):
            gf = fit_gas(gas, dt.datetime.fromtimestamp(D(CFG[s]["split"]), dt.timezone.utc).date())
            info[s + "_gasfit"] = gf
        us = units(s, rows, gas if gf else None, gf[:2] if gf else None)
        info[s] = {"markets": len(rows), "with_candles": sum(1 for r in rows if r.get("c")), "units": len(us),
                   "train_units": sum(not u["test"] for u in us), "test_units": sum(u["test"] for u in us),
                   "train_events": len({u["cl"] for u in us if not u["test"]}), "test_events": len({u["cl"] for u in us if u["test"]})}
        allu += us
    tr = cells([u for u in allu if not u["test"]])
    elig = {k: v for k, v in tr.items() if len(v) >= 30 and len({u["cl"] for u in v}) >= 10}
    N = len(elig)
    bar = NormalDist().inv_cdf(1 - 0.05 / max(N, 1))
    scored = []
    for k, v in elig.items():
        sm = summary(v, days_of(v)); sm["cell"] = [k[0], k[1], k[2], list(k[3])]
        scored.append(sm)
    scored.sort(key=lambda x: -x["t"])
    carried = [x for x in scored if x["t"] > bar]
    te = cells([u for u in allu if u["test"]])
    def test_of(cell):
        k = (cell[0], cell[1], cell[2], tuple(cell[3]))
        v = te.get(k, [])
        return summary(v, days_of(v)) if v else None
    # pre-registered cells: merge bands inside the stated range
    pre = []
    for s, h, role, (lo, hi) in PREREG:
        for half in (False, True):
            v = [u for u in allu if u["s"] == s and u["h"] == h and u["role"] == role and lo <= u["p"] < hi and u["test"] == half]
            if not half:
                trs = summary(v, days_of(v)) if v else None
            else:
                tes = summary(v, days_of(v)) if v else None
        pre.append({"cell": [s, h, role, [lo, hi]], "train": trs, "test": tes})
    # controls: buy everything, per series, test half
    ctrl = {}
    for s in CFG:
        v = [u for u in allu if u["s"] == s and u["test"] and u["role"] in ("fav", "dog")]
        if v:
            ctrl[s] = summary(v, days_of(v))
    out = {"info": info, "n_cells_scored": N, "bar_t": bar, "top_train": scored[:15],
           "carried": [{"cell": c["cell"], "train": c, "test": test_of(c["cell"])} for c in carried],
           "prereg": pre, "control_test": ctrl}
    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=str)
    pr = lambda x: ("n %4d edge %+6.1f%% [%+6.1f, %+6.1f] t %+5.2f win %.3f /mo %6.1f streak %d" % (
        x["n"], 100 * x["edge"], 100 * x["lo"], 100 * x["hi"], x["t"], x["win"], x["trades_month"], x["max_lose_streak"])) if x else "none"
    print(json.dumps(info, default=str))
    print("cells scored", N, "bar t", round(bar, 2))
    print("TOP TRAIN"); [print("  ", c["cell"], pr(c)) for c in scored[:12]]
    print("CARRIED"); [print("  ", c["cell"], "TRAIN", pr(c["train"]), "\n      TEST ", pr(c["test"])) for c in out["carried"]]
    print("PREREG"); [print("  ", c["cell"], "\n      TRAIN", pr(c["train"]), "\n      TEST ", pr(c["test"])) for c in pre]
    print("CONTROL test"); [print("  ", s, pr(x)) for s, x in ctrl.items()]


if __name__ == "__main__":
    main()
