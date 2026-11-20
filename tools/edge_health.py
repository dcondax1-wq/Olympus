"""Edge health (2026-11-17): is the market still the 2026 kind where LIT makes money, or turning 2021-25-like (no edge)?

A WARNING, not a trading switch (a drift switch was tested and rejected, 0/51: research/writeups/drift-switch-2026-11-17.md).
It changes nothing in the bots and never touches live_model*.json. It answers one question before the owner buys more evals.

  python tools/edge_health.py                 # -> research/lab/edge_health.json (+ the Business card via tools/biz_publish.py)
  python tools/edge_health.py --fetch         # first refresh VIX (CBOE's own daily file, free) and the heartbeat branch bars
  python tools/edge_health.py --print         # the plain table only
  python tools/edge_health.py --pc            # the PC's daily run (tools/pc_report.py starts it after 17:00 ET): data/edge/tiny.json
                                              # -> the PC status key "eh" (<= 120 bytes); the cloud run writes tools/web_public/edge.json

What it does
 1. Data freshness: newest bar of data/NQ_1m / NQ_5m / ES_5m (TradingView NQ1!/ES1! exports), of the PC's NinjaTrader bars
    (the `heartbeat` branch bars_1m/5m.csv.gz, or data/nt_bars/ on the PC) and of VIX. Futures only, never Yahoo.
 2. LIT on the freshest bars: the exact live settings (live_model.json "lit", engine/lit.run_x = run lit_live) on the
    TradingView 5m + 1m history with the PC's NinjaTrader bars appended (same price basis, checked). Up to the last export
    it must equal run lit_live trade for trade (checked, else it stops). Days without 1m bars execute on 5m (the engine's rule).
    Rolling 20 / 40 / 60-session trades/week, win %, PF, $/month (the LIT size rule of run lit_live), vs the same windows over
    2026 H1, 2026 H2 and 2021-25. ATLAS: the stored run atlas_fresh_fixed (tools/atlas_edge_fresh.py save: fixed $250, to the newest bars).
 3. Regime light: five simple day features (VIX, RTH range %, overnight share of the day's range, RTH trend efficiency,
    prior-day sweep reclaim rate), each a 40-session mean. Each feature's cut is picked on 2021-25 (no edge) vs 2026 H1
    (edge) only; the features that separate them well are kept; the light is checked on 2026 H2 (never used to pick) and the
    false-alarm rate there is reported. GREEN = all kept features look like 2026, RED = none or only a minority, AMBER between.
 4. ATLAS (2026-11-18): the same light on ATLAS's own last 40 sessions at a FIXED size (R-PF, R a week; the eval's need size
    distorts its $ PF: research/writeups/atlas-revive-2026-11-17.md), cuts from ATLAS's own 2021-25.
 5. Where the owner sees it: tools/web_public/edge_chip.js (Board, Trading, MFFU view) reads the PC status "eh" (fresh bars,
    the PC's daily --pc run) or else tools/web_public/edge.json (this cloud run), whichever is newer.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import subprocess
import sys
import urllib.request

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.edge_pc import PC_DIR, PC_TINY, TINY_MAX, _bytes, _write_json  # noqa: E402  (the PC side, no pandas: tools/edge_pc.py)

DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "research", "lab", "edge_health.json")
SITE = os.path.join(ROOT, "tools", "web_public", "edge.json")                # the chip's cloud copy (edge_chip.js)
CACHE = os.path.join(ROOT, "research", "runs", "_cache", "edge")          # gitignored
CBOE_VIX = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
ATLAS_RUN = "atlas_fresh_fixed"   # 2026-11-20 day-atlasedge: fixed $250, data to the newest bars (was atlas_deep_zombie, eval path to Oct 16)
WINDOWS = (20, 40, 60)
FEAT_N = 40                                    # sessions per feature mean
SPANS = {"2021-25": ("2021-01-01", "2025-12-31"), "2026 H1": ("2026-01-01", "2026-06-30"), "2026 H2": ("2026-07-01", "2026-12-31")}
FEATURES = {
    "vix": "VIX (prior close)",
    "rth_rng": "RTH range, % of price",
    "on_share": "overnight share of the day's range",
    "er": "RTH trend efficiency (1 = straight line, 0 = chop)",
    "reclaim": "prior-day high/low swept then closed back inside",
}
KEEP_BA = 0.75                                 # a feature is kept when its pick-set balanced accuracy is at least this


# ------------------------------------------------------------------------------------------------ 1. data freshness
def _last_t(path):
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, os.path.getsize(path) - 400))
            last = fh.read().decode("utf-8", "ignore").strip().splitlines()[-1]
        return last.split(",")[0]
    except Exception:
        return None


def _iso(t):
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=-5))).strftime("%Y-%m-%d %H:%M ET")


def heartbeat_bars(fetch=False):
    """The PC's NinjaTrader bars: data/nt_bars/ (on the PC) merged with the heartbeat branch (in the cloud)."""
    from engine import pcbars
    if fetch:
        subprocess.run(["git", "-C", ROOT, "fetch", "-q", "origin", "heartbeat:refs/remotes/origin/heartbeat"], capture_output=True, timeout=120)
    out = {}
    for tf in ("1m", "5m"):
        frames = []
        a = pcbars.archive_read("NQ", tf)
        if len(a):
            frames.append(a)
        for ref in ("origin/heartbeat", "heartbeat", "FETCH_HEAD"):
            try:
                raw = subprocess.run(["git", "-C", ROOT, "show", f"{ref}:bars_{tf}.csv.gz"], capture_output=True, timeout=60).stdout
                if raw[:2] == b"\x1f\x8b":
                    frames.append(pcbars.tidy(pd.read_csv(io.BytesIO(raw), compression="gzip")))
                    break
            except Exception:
                pass
        out[tf] = pcbars.tidy(pd.concat(frames)) if frames else pcbars._empty()
    return out


def vix_frame(fetch=False):
    """data/VIX_1d.csv + CBOE's own daily VIX file (cached, gitignored) for the days after it."""
    v = pd.read_csv(os.path.join(DATA, "VIX_1d.csv"))
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, "VIX_History.csv")
    if fetch:
        try:
            req = urllib.request.Request(CBOE_VIX, headers={"User-Agent": "edge-health/1"})
            with urllib.request.urlopen(req, timeout=30) as r, open(p, "wb") as fh:
                fh.write(r.read())
        except Exception as e:
            print("CBOE VIX fetch failed:", e)
    if os.path.exists(p):
        try:
            c = pd.read_csv(p)
            c.columns = [x.lower() for x in c.columns]
            c["date"] = pd.to_datetime(c["date"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d")
            c = c[c["date"] > v["date"].max()][["date", "open", "high", "low", "close"]]
            v = pd.concat([v, c], ignore_index=True)
        except Exception as e:
            print("CBOE VIX file unreadable:", e)
    return v


def freshness(hb, vix, today):
    rows = {}
    for nm in ("NQ_1m", "NQ_5m", "ES_5m"):
        t = _last_t(os.path.join(DATA, f"{nm}.csv"))
        rows[f"data/{nm}.csv (TradingView)"] = _iso(t) if t and t.isdigit() else None
    for tf in ("1m", "5m"):
        rows[f"PC NinjaTrader bars {tf} (heartbeat)"] = _iso(hb[tf]["time"].max()) if len(hb[tf]) else None
    rows["VIX (data/VIX_1d.csv)"] = str(pd.read_csv(os.path.join(DATA, "VIX_1d.csv"))["date"].max())
    rows["VIX (with CBOE)"] = str(vix["date"].max())
    tv_end = rows["data/NQ_5m.csv (TradingView)"][:10]
    nt_end = rows["PC NinjaTrader bars 5m (heartbeat)"][:10] if rows["PC NinjaTrader bars 5m (heartbeat)"] else tv_end
    newest = max(tv_end, nt_end)
    bd = np.busday_count(np.datetime64(newest, 'D') + np.timedelta64(1, 'D'), np.datetime64(today, 'D'))
    return {"rows": rows, "export_end": tv_end, "bars_end": newest, "today": today, "sessions_missing": int(max(0, bd))}


# ------------------------------------------------------------------------------------------------ 2. LIT on the freshest bars
def extended_dir(hb, vix):
    """A scratch copy of data/ (links) with NQ_5m / NQ_1m = TradingView + the PC's later bars, VIX = + CBOE's later days."""
    from engine import pcbars
    d = os.path.join(CACHE, "data")
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(DATA):
        if f in ("NQ_5m.csv", "NQ_1m.csv", "VIX_1d.csv"):
            continue
        p = os.path.join(d, f)
        if not os.path.lexists(p):
            os.symlink(os.path.join(DATA, f), p)
    shifts = {}
    for tf in ("5m", "1m"):
        old = pd.read_csv(os.path.join(DATA, f"NQ_{tf}.csv"))
        new = hb[tf]
        sh = pcbars.basis_shift(old.tail(5000), new) if len(new) else 0.0
        shifts[tf] = sh
        if len(new):
            new = new[new["time"] > old["time"].max()].copy()
            for c in ("open", "high", "low", "close"):
                new[c] = new[c] - sh                 # onto the back-adjusted TradingView basis (0.0 when the same contract)
            old = pd.concat([old, new[old.columns]], ignore_index=True)
        old.to_csv(os.path.join(d, f"NQ_{tf}.csv"), index=False)
    vix.to_csv(os.path.join(d, "VIX_1d.csv"), index=False)
    return d, shifts


def lit_trades(xdir):
    import engine.data as ED
    from engine import lit
    from tools import runlib as rl
    ED.DATA_DIR, ED.LTF_DIR = xdir, os.path.join(xdir, "ltf")
    lit.DATA_DIR = xdir
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = {**lit.DEFAULTS, **lm["lit"]}
    M = lit.Market(extra_boxes=P["extra_boxes"])
    C = lit.candidates(M, ref=P["ref"])
    B1 = lit.bars_1m(M) if P["tf"] == "1m" else None
    base = [d[0] for d in rl.load("baseline")["days"]]
    # a later session counts once its bars reach the LIT flat time (15:55 ET)
    extra = [str(d) for d, s, e in M.days if str(d) > base[-1] and int(M.mod[e - 1]) >= P["flat_mod"] - 5]
    sess = base + extra
    T = lit.run_x(M, C, P, sess, B1=B1, B5=lit.bars_5m(M))
    T = [{k: (v.item() if hasattr(v, "item") else v) for k, v in t.items() if not k.startswith("_")} for t in T]
    ref = rl.load("lit_live")
    c = ref["trade_cols"]
    kr = [(r[c.index("day")], r[c.index("entry_t")], round(r[c.index("pnl")], 2)) for r in ref["trades"]]
    kt = [(t["day"], t["entry_t"], round(t["pnl"], 2)) for t in T if t["day"] <= base[-1]]
    if kr != kt:
        raise SystemExit(f"edge_health: the run does not reproduce lit_live up to {base[-1]} ({len(kt)} vs {len(kr)} trades)")
    one_min = set(np.unique(np.asarray(M.dates)[np.searchsorted(M.t, B1.t[B1.t >= M.t[0]] // 300 * 300).clip(0, M.n - 1)])) if B1 is not None else set()
    return T, sess, base[-1], {d: (d in one_min) for d in extra}


def atlas_trades():
    from tools import runlib as rl
    r = rl.load(ATLAS_RUN)
    c = r["trade_cols"]
    T = [dict(zip(c, row)) for row in r["trades"]]
    return sorted(T, key=lambda t: t["entry_t"]), [d[0] for d in r["days"]]


def window_stats(T, sess, n):
    """Stats of the trades in each run of n sessions, for every end session. Returns {end_day: stats}."""
    idx = {d: i for i, d in enumerate(sess)}
    by = [[] for _ in sess]
    for t in T:
        i = idx.get(str(t["day"]))
        if i is not None:
            by[i].append(t)
    out = {}
    for e in range(n - 1, len(sess)):
        L = [t for b in by[e - n + 1:e + 1] for t in b]
        pnl = np.array([t["pnl"] for t in L], float)
        r = np.array([t["r"] for t in L], float)
        gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
        rw, rl_ = r[r > 0].sum(), -r[r < 0].sum()
        out[sess[e]] = {"n": len(L), "tpw": round(len(L) / (n / 5), 2), "win": round(100 * float((pnl > 0).mean()), 1) if len(L) else None,
                        "pf": round(float(gw / gl), 2) if gl > 0 else (99.0 if gw > 0 else None),
                        "pf_r": round(float(rw / rl_), 2) if rl_ > 0 else (99.0 if rw > 0 else None),
                        "usd_month": round(float(pnl.sum()) / (n / 21)), "r_sum": round(float(r.sum()), 2),
                        "r_avg": round(float(r.mean()), 3) if len(L) else None}
    return out


def _span_of(day):
    for k, (a, z) in SPANS.items():
        if a <= day <= z:
            return k
    return None


def dist(W, key):
    out = {}
    for sp in SPANS:
        v = np.array([w[key] for d, w in W.items() if _span_of(d) == sp and w[key] is not None], float)
        if len(v):
            v = np.minimum(v, 20.0) if key in ("pf", "pf_r") else v
            out[sp] = {"p10": round(float(np.percentile(v, 10)), 2), "median": round(float(np.median(v)), 2),
                       "p90": round(float(np.percentile(v, 90)), 2), "n": int(len(v))}
    return out


def pct_rank(W, key, val, span):
    v = np.array([w[key] for d, w in W.items() if _span_of(d) == span and w[key] is not None], float)
    if val is None or not len(v):
        return None
    return round(100 * float((v < val).mean() + 0.5 * (v == val).mean()))


def edge_block(T, sess, last_day):
    out = {}
    for n in WINDOWS:
        W = window_stats(T, sess, n)
        cur = W.get(last_day) or {}
        out[str(n)] = {"now": cur, "dist": {k: dist(W, k) for k in ("tpw", "win", "pf", "pf_r", "usd_month", "r_avg")},
                       "now_rank_in_2026": {k: pct_rank({d: w for d, w in W.items()}, k, cur.get(k), "2026 H1") for k in ("pf", "usd_month")},
                       "now_rank_in_2021_25": {k: pct_rank(W, k, cur.get(k), "2021-25") for k in ("pf", "usd_month")}}
    return out


# ------------------------------------------------------------------------------------------------ 3. regime features
def day_features(b5: pd.DataFrame, vix: pd.DataFrame) -> pd.DataFrame:
    from engine.data import from_frame
    B = from_frame("NQ", "5m", b5)
    df = pd.DataFrame({"t": B.t, "o": B.o, "h": B.h, "l": B.l, "c": B.c, "mod": B.mod, "day": B.date_str})
    df = df[df["day"].isin(pd.Series(df["day"]).value_counts()[lambda s: s >= 150].index)]   # full sessions only
    rows = []
    prev = None
    for day, g in df.groupby("day", sort=True):
        rth = g[(g["mod"] >= 570) & (g["mod"] < 960)]
        on = g[(g["mod"] >= 1080) | (g["mod"] < 570)]
        if len(rth) < 60 or len(on) < 30:
            prev = None
            continue
        hi, lo = float(g["h"].max()), float(g["l"].min())
        o_r, c_r = float(rth["o"].iloc[0]), float(rth["c"].iloc[-1])
        steps = np.abs(np.diff(np.r_[o_r, rth["c"].values])).sum()
        rec = None
        if prev is not None:
            up, dn = hi > prev[0], lo < prev[1]
            if up or dn:
                close = float(g["c"].iloc[-1])
                rec = float(prev[1] <= close <= prev[0])
        rows.append({"day": day, "rth_rng": 100 * (rth["h"].max() - rth["l"].min()) / o_r,
                     "on_share": (on["h"].max() - on["l"].min()) / max(hi - lo, 1e-9),
                     "er": abs(c_r - o_r) / max(steps, 1e-9), "reclaim": rec})
        prev = (hi, lo)
    F = pd.DataFrame(rows)
    vd = vix[["date", "close"]].rename(columns={"date": "vday", "close": "vix"}).sort_values("vday")
    F = F.sort_values("day")
    # VIX known at 18:00 ET = the last close before the trading day
    F["vix"] = [float(vd["vix"].values[max(0, np.searchsorted(vd["vday"].values, d) - 1)]) for d in F["day"]]
    return F.reset_index(drop=True)


def rolling(F: pd.DataFrame, n=FEAT_N) -> pd.DataFrame:
    R = pd.DataFrame({"day": F["day"]})
    for k in FEATURES:
        R[k] = F[k].astype(float).rolling(n, min_periods=int(n * 0.6)).mean()
    return R.iloc[n - 1:].reset_index(drop=True)


def pick_cuts(R: pd.DataFrame):
    """Per feature: the cut and side that best separate 2026 H1 (edge, 1) from 2021-25 (no edge, 0), balanced accuracy."""
    sp = R["day"].map(_span_of)
    pick = R[sp.isin(["2021-25", "2026 H1"])]
    y = (pick["day"].map(_span_of) == "2026 H1").values
    cuts = {}
    for k in FEATURES:
        x = pick[k].values
        ok = ~np.isnan(x)
        best = (0.0, None, None)
        for q in np.unique(np.round(np.nanpercentile(x, np.arange(2, 99, 1)), 4)):
            for side in (1, -1):
                pr = (side * (x[ok] - q)) > 0
                ba = 0.5 * (pr[y[ok]].mean() + (~pr[~y[ok]]).mean())
                if ba > best[0]:
                    best = (ba, float(q), side)
        cuts[k] = {"cut": round(best[1], 4), "side": "above" if best[2] == 1 else "below", "ba_pick": round(best[0], 3),
                   "kept": best[0] >= KEEP_BA}
    return cuts


def light_series(R, cuts):
    kept = [k for k, c in cuts.items() if c["kept"]]
    out = []
    for _, r in R.iterrows():
        like = [((r[k] - cuts[k]["cut"]) * (1 if cuts[k]["side"] == "above" else -1)) > 0 for k in kept if not np.isnan(r[k])]
        n, m = len(like), sum(like)
        if not n:
            col = None
        elif m == n:
            col = "GREEN"
        elif m * 2 > n:
            col = "AMBER"
        else:
            col = "RED"
        out.append({"day": r["day"], "light": col, "like_2026": m, "of": n})
    return out, kept


def light_rates(L):
    out = {}
    for sp in SPANS:
        v = [x["light"] for x in L if _span_of(x["day"]) == sp and x["light"]]
        if v:
            out[sp] = {c: round(100 * v.count(c) / len(v), 1) for c in ("GREEN", "AMBER", "RED")} | {"n": len(v)}
    return out


def light_vs_forward(L, T, sess, n=40):
    """Does the light track the edge? LIT's NEXT n sessions (avg R a trade, $/month) by the light shown, per span."""
    idx = {d: i for i, d in enumerate(sess)}
    per = {}
    for t in T:
        per.setdefault(str(t["day"]), []).append(t)
    out = {}
    for sp in SPANS:
        acc = {}
        for x in L:
            if _span_of(x["day"]) != sp or not x["light"] or x["day"] not in idx:
                continue
            i = idx[x["day"]]
            if i + n >= len(sess):
                continue
            nxt = [t for d in sess[i + 1:i + 1 + n] for t in per.get(d, [])]
            a = acc.setdefault(x["light"], {"r": [], "usd": []})
            a["r"].extend(t["r"] for t in nxt)
            a["usd"].append(sum(t["pnl"] for t in nxt) / (n / 21))
        out[sp] = {c: {"avg_r_next": round(float(np.mean(v["r"])), 3) if v["r"] else None,
                       "usd_month_next": round(float(np.mean(v["usd"]))) if v["usd"] else None, "days": len(v["usd"])}
                   for c, v in acc.items()}
    return out


# ------------------------------------------------------------------------------------------------ 4. the light (LIT's own edge)
def edge_light(T, sess, n=FEAT_N):
    """The light from LIT's own last n sessions, R a week (size-free). Cuts from the 2021-25 (no edge) windows only:
    GREEN = more than 90% of them made (= 2026 H1's worst 10% of windows), RED = no more than their median (about 0 R:
    LIT made nothing for 8 weeks, the normal 2021-25 state), AMBER between. Checked on 2026 H2, never used to pick."""
    W = window_stats(T, sess, n)
    wk = {d: w["r_sum"] / (n / 5) for d, w in W.items()}
    ref = np.array([v for d, v in wk.items() if _span_of(d) == "2021-25"])
    g_cut, r_cut = round(float(np.percentile(ref, 90)), 2), round(float(np.percentile(ref, 50)), 2)
    L = [{"day": d, "light": "GREEN" if v > g_cut else ("RED" if v <= r_cut else "AMBER"), "r_week": round(v, 2)} for d, v in wk.items()]
    return L, {"green_above_r_week": g_cut, "red_at_or_below_r_week": r_cut, "sessions": n}


def red_runs(L, span):
    """RED stretches inside a span: how many, the longest (sessions)."""
    runs, cur = [], 0
    for x in L:
        if _span_of(x["day"]) != span:
            continue
        if x["light"] == "RED":
            cur += 1
        elif cur:
            runs.append(cur); cur = 0
    if cur:
        runs.append(cur)
    return {"stretches": len(runs), "longest": max(runs) if runs else 0}


def pc_backtest(hb_json):
    """The PC's own LIT backtest days (heartbeat learn.reviews) for the fresh weeks: a cross-check of the 5m-only replay."""
    out = []
    for r in ((hb_json or {}).get("learn") or {}).get("reviews") or []:
        if r.get("bot") == "lit":
            out.append({"day": r.get("day"), "status": r.get("status"), "note": (r.get("notes") or [""])[0]})
    return sorted(out, key=lambda x: x["day"] or "")


def heartbeat_json():
    for ref in ("origin/heartbeat", "heartbeat", "FETCH_HEAD"):
        try:
            raw = subprocess.run(["git", "-C", ROOT, "show", f"{ref}:heartbeat.json"], capture_output=True, timeout=60).stdout
            if raw.strip().startswith(b"{"):
                return json.loads(raw)
        except Exception:
            pass
    return None


# ------------------------------------------------------------------------------------------------ build
def _md(day):
    return dt.date.fromisoformat(day).strftime("%b %-d")


def build(fetch_vix=False, today=None, fetch_git=None):
    today = today or dt.date.today().isoformat()
    hb = heartbeat_bars(fetch_vix if fetch_git is None else fetch_git)
    vix = vix_frame(fetch_vix)
    fr = freshness(hb, vix, today)
    xdir, shifts = extended_dir(hb, vix)
    T, sess, export_end, one_min = lit_trades(xdir)
    last = sess[-1]
    lit_edge = edge_block(T, sess, last)
    lit_edge_export = {str(n): window_stats(T, sess, n).get(export_end) for n in WINDOWS}
    fresh_trades = [{k: t[k] for k in ("day", "exit", "r", "pnl", "qty", "risk_pts")} for t in T if str(t["day"]) > export_end]
    AT, asess = atlas_trades()
    atlas_edge = edge_block(AT, asess, asess[-1])

    b5 = pd.read_csv(os.path.join(xdir, "NQ_5m.csv"))
    F = day_features(b5, vix)
    R = rolling(F)
    cuts = pick_cuts(R)
    ML, kept = light_series(R, cuts)
    m_rates = light_rates(ML)
    m_fwd = light_vs_forward(ML, T, sess)
    f25 = m_fwd.get("2021-25", {})
    g_r, r_r = (f25.get("GREEN") or {}).get("avg_r_next"), (f25.get("RED") or {}).get("avg_r_next")
    tracks = bool(kept) and g_r is not None and r_r is not None and g_r > r_r + 0.1
    by_half = F.assign(h=F["day"].str[:4] + np.where(F["day"].str[5:7] <= "06", " H1", " H2")).groupby("h")[list(FEATURES)].mean().round(3)
    market = {"features": FEATURES, "mean_of_sessions": FEAT_N, "cuts": cuts, "kept": kept, "rates": m_rates,
              "forward_by_light": m_fwd, "tracks_edge": tracks, "used_for_light": tracks,
              "by_half_year": {h: row.to_dict() for h, row in by_half.iterrows()},
              "now_values": {k: round(float(R[k].iloc[-1]), 4) for k in FEATURES}, "now": ML[-1],
              "verdict": ("market features separate 2026 from 2021-25 AND track LIT's next 40 sessions inside 2021-25: used"
                          if tracks else
                          "NOT used: " + (", ".join(FEATURES[k] for k in kept) + " separates 2021-25 from 2026 H1, but " if kept else
                                          "no feature separates 2021-25 from 2026 H1 well; ") +
                          "inside 2021-25 its 2026-like (GREEN) days were followed by a WORSE LIT than its RED days "
                          f"({g_r} vs {r_r} R a trade over the next 40 sessions): it marks the calendar (a slow rise every year), "
                          "not the edge.")}

    EL, ecuts = edge_light(T, sess)
    e_rates = light_rates(EL)
    e_fwd = light_vs_forward(EL, T, sess)
    now = EL[-1]
    h2 = e_rates.get("2026 H2", {})
    full = {"v": 1, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "today": today,
            "what": "Edge health: a WARNING light for LIT, not a trading switch. Paper research; changes no bot.",
            "freshness": fr, "basis_shift": shifts, "sessions_after_export": len(sess) - sess.index(export_end) - 1,
            "fresh_days_1m": one_min, "fresh_trades": fresh_trades, "pc_backtest_fresh": pc_backtest(heartbeat_json()),
            "lit": {"run": "lit_live settings (live_model.json lit), engine/lit.run_x", "last_day": last, "windows": lit_edge,
                    "at_export_end": {"day": export_end, **lit_edge_export}},
            "atlas": {"run": ATLAS_RUN, "last_day": asess[-1], "windows": atlas_edge},
            "light": {"how": "LIT's own last 40 sessions, R a week; cuts from 2021-25 only (GREEN above its best-10% line, "
                             "RED at or below its median); checked on 2026 H2", "cuts": ecuts, "now": now, "rates": e_rates,
                      "false_alarm_h2_red_pct": h2.get("RED"), "h2_not_green_pct": round(h2.get("RED", 0) + h2.get("AMBER", 0), 1) if h2 else None,
                      "red_runs": {sp: red_runs(EL, sp) for sp in SPANS}, "forward_by_light": e_fwd,
                      "series": [x for x in EL if x["day"] >= "2026-01-01"]},
            "market": market}
    # ATLAS the same way (2026-11-18): its own last 40 sessions, FIXED-SIZE R (each trade's pnl / its risk: the eval's need size
    # put 4-6 micros on some losers and 1-2 on winners, so its $ PF says little; research/writeups/atlas-revive-2026-11-17.md)
    AL, acuts = edge_light(AT, asess)
    a_rates = light_rates(AL)
    a40 = atlas_edge["40"]
    full["atlas"]["light"] = {"how": "ATLAS's own last 40 sessions, R a week at a fixed size; cuts from ATLAS's 2021-25 only (GREEN above "
                                     "its best-10% line, RED at or below its median)", "cuts": acuts, "now": AL[-1], "rates": a_rates,
                              "red_runs": {sp: red_runs(AL, sp) for sp in SPANS}}
    full["atlas"]["card"] = {"light": AL[-1]["light"], "data_to": asess[-1], "pf_r40": a40["now"].get("pf_r"),
                             "pf_r40_2026_h1": (a40["dist"]["pf_r"].get("2026 H1") or {}).get("median"),
                             "pf_r40_2021_25": (a40["dist"]["pf_r"].get("2021-25") or {}).get("median"),
                             "r_week40": AL[-1]["r_week"], "tpw40": a40["now"].get("tpw"), "usd_pf40_eval_sized": a40["now"].get("pf")}
    w40 = lit_edge["40"]
    pf_now, pf_26 = w40["now"].get("pf"), (w40["dist"]["pf"].get("2026 H1") or {}).get("median")
    usd_now = w40["now"].get("usd_month")
    line = f"Edge health: {now['light']} · last 40 sessions PF {pf_now} vs 2026 H1 {pf_26} · data to {_md(fr['bars_end'])}"
    full["card"] = {"light": now["light"], "line": line, "data_to": fr["bars_end"], "sessions_missing": fr["sessions_missing"],
                    "pf40": pf_now, "usd_month40": usd_now, "tpw40": w40["now"].get("tpw"), "r_week40": now["r_week"],
                    "pf40_2026_h1": pf_26, "pf40_2021_25": (w40["dist"]["pf"].get("2021-25") or {}).get("median"),
                    "false_alarm_h2_pct": h2.get("RED"), "market_features_used": tracks,
                    "export": (f"TradingView CME_MINI:NQ1! 1-minute chart (all hours, B-ADJ off), Export chart data from {_md(fr['export_end'])} to today, "
                               "save in data/tv_exports/, then: python data/import_futures.py csv NQ data/tv_exports/<file>.csv "
                               "(5m and ES1! 5m the same way). Or start the PC bot: its heartbeat pushes the NinjaTrader bars."),
                    "note": "A warning, not a switch: the bots trade the same either way. GREEN = LIT's last 40 sessions look like 2026, "
                            "RED = like 2021-25 (about $0). Past weeks do not forecast the next ones; it says what the market has been.",
                    "atlas": full["atlas"]["card"]}
    full["tiny"] = tiny(full)
    return full


# ------------------------------------------------------------------------------------------------ the tiny result (PC status, site)
LETTER = {"GREEN": "G", "AMBER": "A", "RED": "R"}


def tiny(full: dict, t: int | None = None) -> dict:
    """The <= 120-byte result the PC status ("eh") and tools/web_public/edge.json carry:
    {"d": LIT data to, "z": [light, PF last 40, 2026 H1 median PF], "a": [light, R-PF last 40, 2026 H1 median R-PF, ATLAS data to],
     "t": built (epoch s)}. Light = G / A / R. tools/web_public/edge_chip.js reads it."""
    c = full.get("card") or {}
    a = c.get("atlas") or {}
    r1 = lambda v: round(float(v), 1) if isinstance(v, (int, float)) else None
    out = {"d": c.get("data_to"), "z": [LETTER.get(c.get("light"), "?"), r1(c.get("pf40")), r1(c.get("pf40_2026_h1"))]}
    if a:
        out["a"] = [LETTER.get(a.get("light"), "?"), r1(a.get("pf_r40")), r1(a.get("pf_r40_2026_h1")), a.get("data_to")]
    out["t"] = int(t if t is not None else dt.datetime.fromisoformat(full["built"]).timestamp()) if full.get("built") else int(t or 0)
    assert _bytes(out) <= TINY_MAX, out
    return out


def site_bots(full: dict) -> dict:
    """Per bot, the last-40-session numbers ZEUS answers "trades per week / how is it doing" with (jarvis/zeus.js, 2026-11-18):
    {"lit"|"atlas": {name, sessions, to, n, tpw, win, pf, pf_r, usd_month, light, basis}}. Read from the run; nothing re-computed."""
    card = full.get("card") or {}
    lights = {"lit": card.get("light"), "atlas": (card.get("atlas") or {}).get("light")}
    basis = {"lit": "backtest of the live settings on the newest bars (LIT size rule)",
             "atlas": "the stored ATLAS run at eval size (not re-run on the newest bars)"}
    out = {}
    for key, name in (("lit", "Zlarior"), ("atlas", "ATLAS")):
        b = full.get(key) if isinstance(full.get(key), dict) else {}
        w = (((b.get("windows") or {}).get("40") or {}).get("now")) or {}
        if not w:
            continue
        out[key] = {"name": name, "sessions": 40, "to": b.get("last_day"), "n": w.get("n"), "tpw": w.get("tpw"), "win": w.get("win"),
                    "pf": w.get("pf"), "pf_r": w.get("pf_r"), "usd_month": w.get("usd_month"), "light": lights.get(key), "basis": basis[key]}
    return out


def write_site(full: dict, path: str | None = None) -> None:
    """tools/web_public/edge.json: the cloud's copy (the tiny result + the lines the chip shows), the fallback when the PC is quiet."""
    o = {"v": 1, "kind": "le-edge", "src": "tools/edge_health.py", "built": full.get("built"), "eh": full.get("tiny")}
    bots = site_bots(full)
    if bots:
        o["bots"] = bots
    with open(path or SITE, "w", encoding="utf-8") as fh:
        json.dump(o, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def table(d):
    c = d["card"]
    fr = d["freshness"]
    lines = [c["line"], "", "Data:"] + [f"  {k}: {v}" for k, v in fr["rows"].items()] + [f"  sessions missing to {fr['today']}: {fr['sessions_missing']}"]
    for nm in ("lit", "atlas"):
        lines.append(f"{nm.upper()} (to {d[nm]['last_day']}):")
        for n, w in d[nm]["windows"].items():
            x = w["now"]
            pf = w["dist"]["pf"]
            lines.append(f"  last {n}: {x.get('n')} trades {x.get('tpw')}/wk win {x.get('win')}% PF {x.get('pf')} ${x.get('usd_month')}/mo | "
                         f"median PF H1 {pf.get('2026 H1', {}).get('median')} H2 {pf.get('2026 H2', {}).get('median')} 2021-25 {pf.get('2021-25', {}).get('median')}")
    rg = d["market"]
    lines.append("Market features (cuts picked on 2021-25 vs 2026 H1):")
    for k, cc in rg["cuts"].items():
        lines.append(f"  {k}: {cc['side']} {cc['cut']} BA {cc['ba_pick']} {'KEPT' if cc['kept'] else ''} now {rg['now_values'][k]}")
    lines.append(f"  rates {rg['rates']}")
    lines.append(f"  next-40 LIT by market light {rg['forward_by_light']}")
    lines.append(f"  {rg['verdict']}")
    lg = d["light"]
    lines.append(f"Edge light cuts {lg['cuts']} now {lg['now']}")
    lines.append(f"  rates {lg['rates']}  red runs {lg['red_runs']}")
    lines.append(f"  next-40 LIT by edge light {lg['forward_by_light']}")
    al = d["atlas"].get("light") or {}
    lines.append(f"ATLAS edge light (fixed-size R) cuts {al.get('cuts')} now {al.get('now')} card {d['atlas'].get('card')}")
    lines.append(f"  rates {al.get('rates')}  red runs {al.get('red_runs')}")
    lines.append(f"Tiny ({_bytes(d['tiny'])} bytes): {json.dumps(d['tiny'], separators=(',', ':'))}")
    lines.append(f"PC backtest (fresh weeks): {d['pc_backtest_fresh']}")
    lines.append(f"Fresh trades after the export: {d['fresh_trades']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Edge health: a warning light for LIT (paper research, changes no bot).")
    ap.add_argument("--fetch", action="store_true", help="refresh VIX from CBOE and the heartbeat branch from GitHub first")
    ap.add_argument("--today", default=None)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--print", action="store_true", dest="show")
    ap.add_argument("--pc", action="store_true", help="the PC's daily run (pc_report hook): VIX from CBOE, the PC's own bars, "
                                                     "-> data/edge/ (tiny.json = the status 'eh'); no git")
    ap.add_argument("--no-site", action="store_true", help="do not write tools/web_public/edge.json")
    a = ap.parse_args(argv)
    if a.pc:
        try:                                                 # research only, low priority: never in the bot's way
            os.nice(10) if os.name != "nt" else None
        except Exception:  # noqa: BLE001
            pass
        print(dt.datetime.now().isoformat(timespec="seconds"), "edge health (PC daily run)", flush=True)
        d = build(fetch_vix=True, today=a.today, fetch_git=False)
        os.makedirs(PC_DIR, exist_ok=True)
        _write_json(os.path.join(PC_DIR, "edge_health.json"), d, indent=1)
        _write_json(PC_TINY, d["tiny"], separators=(",", ":"))
        print(d["card"]["line"], "| tiny", json.dumps(d["tiny"], separators=(",", ":")), flush=True)
        return 0
    d = build(a.fetch, a.today)
    if not a.show:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1, default=str)
        if not a.no_site and a.out == OUT:
            write_site(d)
    print(table(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
