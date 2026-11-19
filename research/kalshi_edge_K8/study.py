#!/usr/bin/env python3
"""K8 main study: the friend's 'printer' legs on Kalshi's 15-minute commodity markets, tested honestly.

Legs (taken from the friend's posted trades, not mined by us):
  A  05:30 DOWN  gold + silver: window 05:15 -> 05:30 ET, buy NO at the open
  B  17:00 UP    gold + silver: window 16:45 -> 17:00 ET, buy YES at the open
  C  16:15 DOWN  silver (and gold): window 16:00 -> 16:15 ET, buy NO
  R  roll        on the 5th-9th business day of the month (Pyth's commodity indices roll then):
                 natgas UP 17:00->17:15, WTI DOWN 17:00->17:15, Brent DOWN 17:30->17:45 (+ the friend's 16:15 roll tickets)
Entry: (a) the trade tape at 15-30 s after the window opens (the friend's fills are at 20-25 s; taker price paid
for our side), (b) the 1-minute candle quote at 60 s (ask; NO ask = 1 - yes bid).  Flat stake, whole contracts,
Kalshi taker fee 0.07*C*p*(1-p) rounded up to the cent per order.
Split fixed before reading test results: TRAIN 2026-08-03..09-30, TEST 2026-10-01..11-18.
Filters are picked on TRAIN only (min 20 train trades) and then read once on TEST.

    python research/kalshi_edge_K8/study.py         # tables + research/kalshi_edge_K8/results.json
"""
import collections, datetime, json, math, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import k8lib  # noqa: E402
import analyze as A  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = {}


# ---------------------------------------------------------------- entry prices
_OT = {}


def open_tape(name):
    s = A.SER[name]
    if s not in _OT:
        fn = os.path.join(k8lib.CACHE, "ot_%s.jsonl" % s)
        d = {}
        if os.path.exists(fn):
            for l in open(fn):
                r = json.loads(l)
                d[r["t"]] = r["tr"]
        _OT[s] = d
    return _OT[s]


def price_tape(name, m, side, lo=15.0, hi=30.0):
    """VWAP paid by takers of `side` between lo and hi seconds after the open (None if no such trade)."""
    tr = open_tape(name).get(m["t"])
    if tr is None:
        return None, None
    px = [((x[2] if x[1] == "yes" else 1 - x[2]), x[3]) for x in tr if x[1] == side and lo <= x[0] <= hi]
    if not px:
        px = [((x[2] if x[1] == "yes" else 1 - x[2]), x[3]) for x in tr if x[1] == side and 5 <= x[0] <= 45]
        if not px:
            return None, 0.0
    q = sum(c for p, c in px)
    vol45 = sum(x[3] for x in tr if x[1] == side and x[0] <= 45)
    return sum(p * c for p, c in px) / q, vol45


SLIP = 0.0      # extra cents paid on every entry (robustness: 0.01 / 0.02)


def bet(name, m, side, how="tape", stake=15.0, max_price=1.0, min_price=0.0):
    if how == "tape":
        p, vol = price_tape(name, m, side)
        if p is None:
            return None
        mid = p if side == "yes" else 1 - p          # market's YES-probability, as in analyze.stats
    else:
        mk, cd, idx = A.data(name)
        row = cd.get(m["t"])
        if not row:
            return None
        q = A.entry_quote(row, int(how[1:]) if how.startswith("m") else 1)
        if not q:
            return None
        b, a = q
        if a - b > 0.10:
            return None
        p = a if side == "yes" else 1 - b
        mid = (a + b) / 2                            # YES terms
        vol = None
    if not (min_price < p <= max_price) or p >= 0.995:     # filters judge the price seen; slippage is paid on top
        return None
    p = round(min(0.999, p + SLIP), 4)
    win = m["up"] if side == "yes" else (not m["up"])
    n = max(1, int(stake // p))
    fee = k8lib.fee(p, n)
    cost = n * p + fee
    return {"date": m["date"], "t": m["t"], "ts": A.k8lib_ts(m["close"]), "side": side, "price": p, "mid": mid, "win": win, "n": n, "fee": fee,
            "cost": cost, "net": (n - cost) if win else -cost, "vol45": vol, "hhmm": m["hhmm"]}


def legs_def():
    R = A.ROLL
    return [
        # key, label, series, window, side, day-set, london
        ("A_gold", "05:30 DOWN gold", "gold", "0530", "no", None, False),
        ("A_silver", "05:30 DOWN silver", "silver", "0530", "no", None, False),
        ("A_gold_lon", "10:30 London DOWN gold", "gold", "0530", "no", None, True),
        ("A_silver_lon", "10:30 London DOWN silver", "silver", "0530", "no", None, True),
        ("B_gold", "17:00 UP gold", "gold", "1700", "yes", None, False),
        ("B_silver", "17:00 UP silver", "silver", "1700", "yes", None, False),
        ("C_silver", "16:15 DOWN silver", "silver", "1615", "no", None, False),
        ("C_gold", "16:15 DOWN gold", "gold", "1615", "no", None, False),
        ("D_gold", "17:15 UP gold (Aug-Sep only)", "gold", "1715", "yes", None, False),
        ("D_silver", "17:15 UP silver (Aug-Sep only)", "silver", "1715", "yes", None, False),
        ("R_natgas", "roll: natgas UP 17:00-17:15", "natgas", "1715", "yes", R, False),
        ("R_wti", "roll: WTI DOWN 17:00-17:15", "wti", "1715", "no", R, False),
        ("R_brent", "roll: Brent DOWN 17:30-17:45", "brent", "1745", "no", R, False),
        ("R_natgas_1615", "roll ticket: natgas UP 16:00-16:15", "natgas", "1615", "yes", R, False),
        ("R_brent_1615", "roll ticket: Brent DOWN 16:00-16:15", "brent", "1615", "no", R, False),
    ]


def collect(key, how="tape", stake=15.0, max_price=1.0, flt=None, min_price=0.0):
    for k, lab, name, hh, side, days, lon in legs_def():
        if k != key:
            continue
        res = {"train": [], "test": []}
        for m in A.leg_markets(name, hh, days, lon):
            p = A.period(m["date"])
            if not p or (flt and not flt(name, m)):
                continue
            b = bet(name, m, side, how, stake, max_price, min_price)
            if b:
                res[p].append(b)
        return res
    raise KeyError(key)


def boot_ci(tr, reps=2000, seed=7):
    """95% bootstrap range of net per $1 (resampling days)."""
    if len(tr) < 5:
        return None
    byd = collections.defaultdict(list)
    for x in tr:
        byd[x["date"]].append(x)
    days = list(byd)
    rnd = random.Random(seed)
    vals = []
    for _ in range(reps):
        s = [x for d in (rnd.choice(days) for _ in days) for x in byd[d]]
        c = sum(x["cost"] for x in s)
        vals.append(sum(x["net"] for x in s) / c if c else 0)
    vals.sort()
    return [round(vals[int(0.025 * reps)], 3), round(vals[int(0.975 * reps)], 3)]


def st(tr):
    s = A.stats(tr)
    if s.get("n"):
        s["ci95_net_per_$1"] = boot_ci(tr)
        vv = [x["vol45"] for x in tr if x.get("vol45") is not None]
        if vv:
            vv.sort()
            s["median_contracts_our_side_first45s"] = vv[len(vv) // 2]
    return s


# ---------------------------------------------------------------- filters (picked on TRAIN)
def prev_window_up(name, m):
    mk, cd, idx = A.data(name)
    hh, mm = int(m["hhmm"][:2]), int(m["hhmm"][2:])
    prev = (datetime.datetime(2000, 1, 1, hh, mm) - datetime.timedelta(minutes=15)).strftime("%H%M")
    pm = idx.get((m["date"], prev))
    return None if (not pm or pm["mv"] is None) else pm["mv"] >= 0


def filters():
    F = {"none": None}
    for cap in (0.50, 0.55, 0.60, 0.65, 0.70):
        F["price<=%.2f" % cap] = ("cap", cap)
    for flo in (0.45, 0.50, 0.55):
        F["price>=%.2f" % flo] = ("floor", flo)
    F["prev15 up"] = lambda n, m: prev_window_up(n, m) is True
    F["prev15 down"] = lambda n, m: prev_window_up(n, m) is False
    F["prior4h up"] = lambda n, m: (A.prior_move(n, m, 4) or 0) > 0
    F["prior4h down"] = lambda n, m: (A.prior_move(n, m, 4) or 0) < 0
    # the session before the window: 18:15 the evening before -> 05:15 (Asia) for the 05:30 legs, 05:45 -> 16:45 (London+NY) for 17:00
    F["prior11h up"] = lambda n, m: (A.prior_move(n, m, 11) or 0) > 0
    F["prior11h down"] = lambda n, m: (A.prior_move(n, m, 11) or 0) < 0
    F["Mon-Wed"] = lambda n, m: m["date"].weekday() <= 2
    F["Thu-Fri"] = lambda n, m: m["date"].weekday() >= 3
    return F


def pick_filter(key, how):
    best = ("none", None, -9)
    rows = []
    for fname, f in filters().items():
        kw = {}
        if isinstance(f, tuple):
            kw["max_price" if f[0] == "cap" else "min_price"] = f[1] if f[0] == "cap" else f[1] - 1e-9
            flt = None
        else:
            flt = f
        r = collect(key, how, flt=flt, **kw)
        s = A.stats(r["train"])
        t = A.stats(r["test"])
        rows.append((fname, s, t))
        if s.get("n", 0) >= 20 and s["net_per_$1"] > best[2]:
            best = (fname, s, s["net_per_$1"])
    return best[0], rows


# ---------------------------------------------------------------- data-mined seasonality control
def mined(names=("gold", "silver", "natgas", "wti"), zbar=3.0):
    """Pick windows on TRAIN outcomes only (|z| >= zbar of the up-rate), trade the bias on TEST at real prices."""
    picks = []
    for name in names:
        mk, cd, idx = A.data(name)
        by = collections.defaultdict(list)
        for m in mk:
            if A.period(m["date"]) == "train" and m["vol"] > 0 and m["date"].weekday() < 5:
                by[m["hhmm"]].append(m["up"])
        test_windows = {m["hhmm"] for m in mk if A.period(m["date"]) == "test"}
        for hh, v in by.items():
            if hh not in test_windows or len(v) < 25:
                continue
            p = sum(v) / len(v)
            z = (p - 0.5) / math.sqrt(0.25 / len(v))
            if abs(z) >= zbar:
                picks.append((name, hh, "yes" if z > 0 else "no", round(z, 2), len(v)))
    tr_all = []
    per = []
    for name, hh, side, z, n in picks:
        trs = []
        for m in A.leg_markets(name, hh):
            if A.period(m["date"]) != "test":
                continue
            b = bet(name, m, side, "m1")
            if b:
                trs.append(b)
        tr_all += trs
        per.append({"series": name, "window_close_ET": hh, "side": side, "train_z": z, "train_n": n, "test": A.stats(trs)})
    return {"zbar": zbar, "picks": per, "pooled_test": A.stats(tr_all)}


# ---------------------------------------------------------------- roll legs: late entries like the friend's 80-95c
def late_roll(key, lo=0.80, hi=0.96, start_min=1, end_min=12):
    """First minute (end of minute start_min..end_min) where our side's ask is in [lo, hi]: buy there."""
    for k, lab, name, hh, side, days, lon in legs_def():
        if k != key:
            continue
        mk, cd, idx = A.data(name)
        res = {"train": [], "test": []}
        for m in A.leg_markets(name, hh, days, lon):
            p = A.period(m["date"])
            row = cd.get(m["t"])
            if not p or not row:
                continue
            for mi in range(start_min, end_min + 1):
                q = A.entry_quote(row, mi, max_back=0)
                if not q:
                    continue
                b, a = q
                px = a if side == "yes" else 1 - b
                if lo <= px <= hi and a - b <= 0.06:
                    win = m["up"] if side == "yes" else (not m["up"])
                    n = max(1, int(15 // px))
                    fee = k8lib.fee(px, n)
                    cost = n * px + fee
                    res[p].append({"date": m["date"], "t": m["t"], "ts": A.k8lib_ts(m["close"]), "side": side, "price": px,
                                   "mid": px if side == "yes" else 1 - px, "win": win,
                                   "n": n, "fee": fee, "cost": cost, "net": (n - cost) if win else -cost, "minute": mi})
                    break
        return res


def roll_open_seconds(key):
    """Roll markets: what our side cost in the first seconds (public tape), and what the jump left by 15-30 s."""
    for k, lab, name, hh, side, days, lon in legs_def():
        if k != key:
            continue
        out = []
        for m in A.leg_markets(name, hh, days, lon):
            tr = open_tape(name).get(m["t"])
            if tr is None:
                continue
            row = {"date": str(m["date"]), "won": (m["up"] if side == "yes" else not m["up"])}
            for lo, hi in ((0, 5), (5, 15), (15, 30)):
                px = [((x[2] if x[1] == "yes" else 1 - x[2]), x[3]) for x in tr if x[1] == side and lo <= x[0] < hi]
                q = sum(c for p, c in px)
                row["%d-%ds" % (lo, hi)] = (round(sum(p * c for p, c in px) / q, 3), round(q)) if q else None
            out.append(row)
        return out


def calib(key, how="m1"):
    """Month by month: what the market charged for our side vs how often it won."""
    r = collect(key, how)
    by = collections.defaultdict(list)
    for p in ("train", "test"):
        for x in r[p]:
            by[x["date"].strftime("%Y-%m")].append(x)
    return {mo: {"n": len(v), "paid": round(sum(x["price"] for x in v) / len(v), 3),
                 "won": round(sum(x["win"] for x in v) / len(v), 3),
                 "net_per_$1": round(sum(x["net"] for x in v) / sum(x["cost"] for x in v), 3)} for mo, v in sorted(by.items())}


def friend_check():
    """Our quotes at 15-30 s vs the friend's posted fills (same markets)."""
    F = [("2026-11-06", "gold", "0530", "no", .66, 8, True), ("2026-11-09", "silver", "0530", "no", .42, 15, False),
         ("2026-11-10", "gold", "0530", "no", .59, 9, True), ("2026-11-10", "silver", "1615", "no", .47, 12, True),
         ("2026-11-12", "gold", "0530", "no", .58, 12, True), ("2026-11-12", "silver", "0530", "no", .63, 11, True),
         ("2026-11-12", "silver", "1700", "yes", .63, 13, True), ("2026-11-13", "gold", "0530", "no", .60, 21, True),
         ("2026-11-13", "silver", "0530", "no", .53, 24, True), ("2026-11-13", "gold", "1700", "yes", .41, 36, True),
         ("2026-11-13", "silver", "1700", "yes", .49, 29, True), ("2026-11-16", "gold", "1700", "yes", .48, 42, False),
         ("2026-11-16", "silver", "1700", "yes", .44, 45, False), ("2026-11-17", "gold", "0530", "no", .56, 27, False),
         ("2026-11-17", "silver", "0530", "no", .53, 28, False), ("2026-11-17", "gold", "1700", "yes", .41, 19, False),
         ("2026-11-17", "silver", "1700", "yes", .42, 19, False), ("2026-11-18", "gold", "0530", "no", .58, 11, True),
         ("2026-11-18", "silver", "0530", "no", .49, 13, True), ("2026-11-18", "gold", "1700", "yes", .46, 16, True),
         ("2026-11-18", "silver", "1700", "yes", .42, 18, False),
         ("2026-11-06", "natgas", "1715", "yes", .80, 2, True), ("2026-11-12", "natgas", "1715", "yes", .95, 3, True),
         ("2026-11-10", "natgas", "1615", "yes", .57, 2, True), ("2026-11-06", "brent", "1615", "no", .48, 3, True)]
    out = []
    for d, name, hh, side, px, n, won in F:
        mk, cd, idx = A.data(name)
        m = idx.get((datetime.date.fromisoformat(d), hh))
        if not m:
            out.append({"day": d, "leg": name + " " + hh, "found": False})
            continue
        tp, _ = price_tape(name, m, side)
        won_k = m["up"] if side == "yes" else (not m["up"])
        out.append({"day": d, "leg": "%s %s %s" % (name, hh, side), "friend_price": px, "tape_15_30s": round(tp, 3) if tp else None,
                    "friend_won": won, "kalshi_result_agrees": won_k == won})
    # legs the friend did NOT trade on days we can see: what did they cost?
    skipped = []
    for d, name, hh, side in [("2026-11-06", "silver", "0530", "no"), ("2026-11-09", "gold", "0530", "no"),
                              ("2026-11-10", "silver", "0530", "no"), ("2026-11-12", "gold", "1700", "yes")]:
        mk, cd, idx = A.data(name)
        m = idx.get((datetime.date.fromisoformat(d), hh))
        if m:
            tp, _ = price_tape(name, m, side)
            skipped.append({"day": d, "leg": "%s %s %s" % (name, hh, side), "tape_15_30s": round(tp, 3) if tp else None,
                            "would_have_won": m["up"] if side == "yes" else (not m["up"])})
    return out, skipped


# Declared BEFORE the full test read: a leg joins the candidate if its TRAIN result (tape entry, fee in) is at least
# +5% per $1 on >= 20 train trades.  The candidate's TEST result is then read once, pooled.
CANDIDATE_POOL = ("A_gold", "A_silver", "B_gold", "B_silver", "C_silver", "C_gold", "R_natgas", "R_wti")
TRAIN_BAR, TRAIN_MIN_N = 0.05, 20


def candidate(how="tape"):
    chosen, test_tr, train_tr = [], [], []
    for k in CANDIDATE_POOL:
        r = collect(k, how)
        s = A.stats(r["train"])
        if s.get("n", 0) >= TRAIN_MIN_N and s["net_per_$1"] >= TRAIN_BAR:
            chosen.append(k)
            test_tr += r["test"]
            train_tr += r["train"]
    return chosen, st(train_tr), st(test_tr), test_tr


def main():
    res = {"stake_$": 15.0, "split": {"train": [str(x) for x in A.TRAIN], "test": [str(x) for x in A.TEST]}, "legs": {}}
    print("=== Legs: flat $15 taker bets, fee in.  tape = price paid 15-30 s after the open; m1 = quote at 60 s ===")
    for k, lab, name, hh, side, days, lon in legs_def():
        res["legs"][k] = {"label": lab}
        for how in ("tape", "m1"):
            r = collect(k, how)
            s = {p: st(v) for p, v in r.items()}
            res["legs"][k][how] = s
            print("%-36s %-4s TRAIN %s" % (lab, how, A.fmt(s["train"])))
            print("%-36s %-4s TEST  %s" % ("", how, A.fmt(s["test"])))
    print("\n=== Month by month (m1): paid vs won ===")
    for k in ("A_gold", "A_silver", "B_gold", "B_silver", "C_silver", "C_gold", "R_natgas", "R_wti"):
        c = calib(k)
        res["legs"][k]["by_month"] = c
        print("%-10s %s" % (k, "  ".join("%s n%d paid %.2f won %.2f (%+.2f)" % (mo[5:], v["n"], v["paid"], v["won"], v["net_per_$1"]) for mo, v in c.items())))
    print("\n=== Filters picked on TRAIN (tape entry), read once on TEST ===")
    for k in ("A_gold", "A_silver", "B_gold", "B_silver", "C_silver", "C_gold"):
        best, rows = pick_filter(k, "tape")
        res["legs"][k]["filters"] = {f: {"train": s, "test": t} for f, s, t in rows}
        res["legs"][k]["filter_picked_on_train"] = best
        print("%-9s picked on train: %-12s -> TEST %s" % (k, best, A.fmt(res["legs"][k]["filters"][best]["test"])))
        for f, s, t in rows:
            print("      %-12s train n%3s %+.3f | test n%3s %+.3f" % (f, s.get("n", 0), s.get("net_per_$1", 0) or 0, t.get("n", 0), t.get("net_per_$1", 0) or 0))
    print("\n=== Roll legs, late entry at 80-96c after the step shows (like the friend's 80c / 95c tickets) ===")
    for k in ("R_natgas", "R_wti", "R_brent"):
        r = late_roll(k)
        res["legs"][k]["late_80_96"] = {p: A.stats(v) for p, v in r.items()}
        print("%-9s TRAIN %s\n%-9s TEST  %s" % (k, A.fmt(A.stats(r["train"])), "", A.fmt(A.stats(r["test"]))))
    print("\n=== Roll markets: our side's price in the first seconds (VWAP, contracts) ===")
    for k in ("R_natgas", "R_wti", "R_brent"):
        ro = roll_open_seconds(k)
        res["legs"][k]["first_seconds"] = ro
        for x in ro:
            print("   %-8s %s" % (k, x))
    print("\n=== Control: windows mined on TRAIN outcomes (|z|>=3), traded on TEST at m1 prices ===")
    for zb in (3.0, 2.5):
        mn = mined(zbar=zb)
        res["mined_control" if zb == 3.0 else "mined_control_z25"] = mn
        print("  bar |z| >= %.1f" % zb)
        for p in mn["picks"]:
            print("   %-7s %s %-3s train z %+.1f -> TEST %s" % (p["series"], p["window_close_ET"], p["side"], p["train_z"], A.fmt(p["test"])))
        print("   pooled TEST", A.fmt(mn["pooled_test"]))
    chosen, s_tr, s_te, te = candidate("tape")
    res["candidate"] = {"rule": "legs with train >= +5%/$1 (n>=20), tape entry", "legs": chosen, "train": s_tr, "test": s_te}
    print("\n=== Candidate (legs picked on TRAIN): %s ===" % ", ".join(chosen))
    print("   TRAIN", A.fmt(s_tr))
    print("   TEST ", A.fmt(s_te), " 95%% range %s" % s_te.get("ci95_net_per_$1"))
    for stake in (10.0, 20.0):
        tr2 = []
        for k in chosen:
            tr2 += collect(k, "tape", stake=stake)["test"]
        s2 = A.stats(tr2)
        res["candidate"]["test_at_$%d" % stake] = s2
        print("   TEST at $%d a bet: %s" % (stake, A.fmt(s2)))
    global SLIP
    for slip in (0.01, 0.02):
        SLIP = slip
        tr2 = []
        for k in chosen:                      # the same legs, every entry paid 1c / 2c worse
            tr2 += collect(k, "tape")["test"]
        b = st(tr2)
        res["candidate"]["test_slip_%dc" % int(round(slip * 100))] = b
        print("   TEST paying %dc more on every entry: %s" % (round(slip * 100), A.fmt(b)))
    SLIP = 0.0
    print("\n=== Last two weeks (2026-11-05 .. 11-18), tape entry ===")
    res["last_two_weeks"] = {}
    for k in ("A_gold", "A_silver", "B_gold", "B_silver", "C_silver", "C_gold"):
        r = collect(k, "tape")
        tr = [x for x in r["test"] if x["date"] >= datetime.date(2026, 11, 5)]
        res["last_two_weeks"][k] = A.stats(tr)
        print("%-9s %s" % (k, A.fmt(A.stats(tr))))
    fc, sk = friend_check()
    res["friend_check"] = fc
    res["friend_skipped"] = sk
    print("\n=== The friend's posted fills vs the public tape at 15-30 s ===")
    for x in fc:
        print("   ", x)
    print("   skipped legs:", sk)
    # every bet of the friend's legs, one row each (small; lets anyone re-check a day by hand)
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    with open(os.path.join(HERE, "data", "legs_bets.csv"), "w") as fh:
        fh.write("date,leg,ticker,side,period,entry_15_30s,entry_60s,won,net_usd_at_15\n")
        for k in ("A_gold", "A_silver", "B_gold", "B_silver", "C_silver", "C_gold", "R_natgas", "R_wti", "R_brent"):
            t1 = collect(k, "tape")
            m1 = {x["t"]: x for p in ("train", "test") for x in collect(k, "m1")[p]}
            for p in ("train", "test"):
                for x in t1[p]:
                    y = m1.get(x["t"])
                    fh.write("%s,%s,%s,%s,%s,%.3f,%s,%d,%.2f\n" % (x["date"], k, x["t"], x["side"], p, x["price"],
                                                                 ("%.3f" % y["price"]) if y else "", x["win"], x["net"]))
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    print("\nwrote", os.path.join(HERE, "results.json"))


if __name__ == "__main__":
    main()
