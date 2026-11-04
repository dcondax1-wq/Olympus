#!/usr/bin/env python3
"""Kalshi Edge v2: where is the edge, where is it negative? (RESEARCH ONLY, read-only.)

Regenerates every number of research/writeups/2026-11-04_kalshi_edges.md from the PUBLIC feed
(https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json). It makes no Kalshi API call, reads no
secret and never touches the bot. The feed is the only data: aggregates over all settled trades (buckets, categories,
strategies, daily P&L) plus the last 40 individual trades.

    python tools/kalshi_research.py                          # fetch the feed, write research/kalshi/edge_tables.json + .md
    python tools/kalshi_research.py --feed kalshi.json       # a saved copy
    python tools/kalshi_research.py --no-sim                 # tables only (fast)
    from tools.kalshi_research import build_tables           # build_tables(feed_dict) -> dict (same as the JSON)

OUTPUT SCHEMA, research/kalshi/edge_tables.json  (schema "kalshi_edge_tables/1"; all money in dollars, all rates 0-1)
  schema, generated_utc, method_notes[]            text
  source        {feed_t, feed_pub_t, balance, total_pnl, stats{...as in the feed}, window_days, caveats[]}
  fees          {formula, maker_formula, rows[{price, fee_per_contract, fee_pct_of_win, breakeven_win_rate,
                  loss_to_win_ratio, breakeven_loss_rate}], drag{fees_est_total, pnl_net, pnl_gross_est, staked,
                  fee_pct_of_stake, by_bucket[{label, fees_est}]}, check_vs_trades{n, mean_abs_err, rule}}
  buckets[]     one row per entry-price bucket of the feed, then merged bands ("90-95c", "95-99c", "<90c", "<95c", "all"):
                  {label, lo, hi, n, wins, losses, win_rate, wilson_lo, wilson_hi, avg_price, breakeven_win_rate, edge_pp,
                   p_one_sided, price_cap (average entry price at which EV is 0 at the observed win rate),
                   price_cap_lo (same at the Wilson lower bound), staked, avg_stake, pnl, roi (pnl / staked),
                   roi_ci_lo, roi_ci_hi, p_roi_gt0, ev_equal_size_pnl (pnl if every bet were the bucket's average size),
                   size_effect_pnl (actual minus that: negative = losing bets were bigger than winning ones),
                   implied_win_stake, implied_loss_stake, fees_est, verdict, low_n (n < 30)}
  categories[]  same fields per asset class of the feed (avg_price = proxy, see price_source)
  strategies[]  {name, mode, n, wins, losses, win_rate, wilson_lo, wilson_hi, pnl, pnl_per_trade, sample_n, sample_price,
                 breakeven_win_rate, price_cap, price_cap_lo, loss_rate, loss_rate_lo, loss_rate_hi, breakeven_loss_rate,
                 verdict, low_n}
  sample        the last 40 trades only: {n, by_strategy[], by_side[], by_asset[], by_hour_et[], minutes_to_expiry{...},
                 windows15m{...}}  (n is tiny: every row carries n and low_n)
  risk          {daily{...}, balance_path[{date, start, pnl, ret}], kelly{...}, sims{late_favourite[], history_bootstrap[]}}
  ideas[]       {id, title, why, how_to_test, n_needed}
  verdict       {positive_pockets[], negative_pockets[], unclear[], headline}
Another tool (tools/kalshi_edges.py / the Kalshi City app) may import this JSON or call build_tables().
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.request
from zoneinfo import ZoneInfo

import numpy as np

FEED_URL = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
TAKER = 0.07          # Kalshi taker fee: ceil-to-cent(0.07 * C * P * (1-P)); the bot's own P&L matches it to the cent (see check_vs_trades)
MAKER = 0.0175
LOW_N = 30
MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


# ---------------------------------------------------------------- small maths
def fee_pc(p: float) -> float:
    """Taker fee per contract (dollars, before cent rounding) at price p."""
    return TAKER * p * (1 - p)


def breakeven_win_rate(p: float) -> float:
    return p + fee_pc(p)


def price_cap(hit: float) -> float:
    """Highest average entry price at which a bettor winning `hit` of the time breaks even after fees."""
    lo, hi = 0.01, 0.999
    for _ in range(60):
        mid = (lo + hi) / 2
        if breakeven_win_rate(mid) > hit:
            hi = mid
        else:
            lo = mid
    return lo


def wilson(k: int, n: int, z: float = 1.96):
    if n <= 0:
        return (float("nan"), float("nan"))
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def binom_sf(k: int, n: int, q: float) -> float:
    """P(X >= k) for X ~ Binomial(n, q), exact."""
    if q <= 0:
        return 1.0 if k <= 0 else 0.0
    if q >= 1:
        return 1.0
    lq, l1 = math.log(q), math.log(1 - q)
    tot = 0.0
    for i in range(k, n + 1):
        tot += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lq + (n - i) * l1)
    return min(1.0, tot)


def size_model(n, w, l, staked, pnl, p):
    """Average stake of a winning and of a losing bet, from totals only.
    win per $ staked r = (1/p - 1) - f, loss per $ = -(1+f), f = 0.07(1-p) (fee per $ staked, charged win or lose).
    staked = s_w*w + s_l*l  and  pnl = s_w*w*r - s_l*l*(1+f)  ->  two equations, two unknowns.
    Falls back to equal sizes when the solution is not sensible (needs both a win and a loss)."""
    f = TAKER * (1 - p)
    r = (1 / p - 1) - f
    if w > 0 and l > 0 and staked > 0:
        s_l = (staked * r - pnl) / (l * (r + 1 + f))
        s_w = (staked - s_l * l) / w
        if s_l > 0 and s_w > 0:
            return s_w, s_l, r, f, True
    s = staked / n if n else 0.0
    return s, s, r, f, False


def analyse(label, n, w, l, staked, pnl, p, rng, sims=20000, lo=None, hi=None):
    """One row of the table. p = average entry price (proxy where the feed does not give it)."""
    hit = w / n if n else float("nan")
    wl, wh = wilson(w, n)
    be = breakeven_win_rate(p)
    s_w, s_l, r, f, solved = size_model(n, w, l, staked, pnl, p)
    ev_eq = staked * (hit / p - 1 - f) if n else 0.0
    row = {"label": label, "lo": lo, "hi": hi, "n": n, "wins": w, "losses": l, "win_rate": round(hit, 4),
           "wilson_lo": round(wl, 4), "wilson_hi": round(wh, 4), "avg_price": round(p, 4), "breakeven_win_rate": round(be, 4),
           "edge_pp": round((hit - be) * 100, 2), "p_one_sided": round(binom_sf(w, n, min(be, 0.9999)), 4),
           "price_cap": round(price_cap(hit), 4), "price_cap_lo": round(price_cap(wl), 4),
           "staked": round(staked, 2), "avg_stake": round(staked / n, 2) if n else 0.0, "pnl": round(pnl, 2),
           "roi": round(pnl / staked, 4) if staked else None,
           "ev_equal_size_pnl": round(ev_eq, 2), "size_effect_pnl": round(pnl - ev_eq, 2),
           "implied_win_stake": round(s_w, 2), "implied_loss_stake": round(s_l, 2), "size_model_solved": solved,
           "fees_est": round(TAKER * staked * (1 - p), 2), "low_n": n < LOW_N}
    if n >= LOW_N and staked:
        wins_sim = rng.binomial(n, hit, size=sims)
        stk = wins_sim * s_w + (n - wins_sim) * s_l
        pn = wins_sim * s_w * r - (n - wins_sim) * s_l * (1 + f)
        roi = pn / stk
        row["roi_ci_lo"], row["roi_ci_hi"] = (round(float(np.percentile(roi, 2.5)), 4), round(float(np.percentile(roi, 97.5)), 4))
        row["p_roi_gt0"] = round(float((roi > 0).mean()), 3)
    else:
        row["roi_ci_lo"] = row["roi_ci_hi"] = row["p_roi_gt0"] = None
    row["verdict"] = verdict_of(row)
    return row


def verdict_of(r):
    if r["low_n"]:
        return "too few trades (n<30)"
    lo, hi = r.get("roi_ci_lo"), r.get("roi_ci_hi")
    if lo is None:
        return "unclear"
    if lo > 0:
        return "positive (95% CI above 0)"
    if hi < 0:
        return "negative (95% CI below 0)"
    return "positive, not proven" if (r["roi"] or 0) > 0 else "negative, not proven"


# ---------------------------------------------------------------- feed
def load_feed(src: str | None):
    if src and os.path.isfile(src):
        with open(src, encoding="utf-8") as fh:
            return json.load(fh)
    url = src or FEED_URL
    req = urllib.request.Request(url, headers={"User-Agent": "kalshi-research/1"})
    with urllib.request.urlopen(req, timeout=30) as resp:        # the public feed only
        return json.loads(resp.read().decode("utf-8"))


def parse_expiry(ticker: str):
    """KXBTCD-26NOV0211-T77399.99 -> expiry datetime (ET). KXDOGE15M-26NOV020245-45 -> 02:45 ET. None if not parseable."""
    try:
        seg = ticker.split("-")[1]
        yy, mon, dd, rest = int(seg[:2]), MONTHS[seg[2:5]], int(seg[5:7]), seg[7:]
        hh = int(rest[:2])
        mm = int(rest[2:4]) if len(rest) >= 4 else 0
        return dt.datetime(2000 + yy, mon, dd, hh, mm, tzinfo=ET)
    except Exception:
        return None


# ---------------------------------------------------------------- sections
def fee_section(feed, buckets_rows):
    rows = []
    for p in (0.50, 0.70, 0.80, 0.90, 0.93, 0.95, 0.96, 0.97, 0.98, 0.99):
        f = fee_pc(p)
        be = p + f
        rows.append({"price": p, "fee_per_contract": round(f, 5), "fee_pct_of_win": round(f / (1 - p), 4),
                     "breakeven_win_rate": round(be, 4), "loss_to_win_ratio": round((p + f) / (1 - p - f), 1),
                     "breakeven_loss_rate": round(1 - be, 4), "maker_fee_per_contract": round(MAKER * p * (1 - p), 5)})
    tot_fee = sum(b["fees_est"] for b in buckets_rows)
    st = feed.get("stats", {})
    drag = {"fees_est_total": round(tot_fee, 2), "pnl_net": st.get("pnl"), "pnl_gross_est": round((st.get("pnl") or 0) + tot_fee, 2),
            "staked": st.get("staked"), "fee_pct_of_stake": round(tot_fee / st["staked"], 4) if st.get("staked") else None,
            "maker_fees_est_total": round(tot_fee * MAKER / TAKER, 2),
            "by_bucket": [{"label": b["label"], "fees_est": b["fees_est"]} for b in buckets_rows]}
    errs = []
    for t in feed.get("trades", []):
        C, P, pnl = t["contracts"], t["price"], t["pnl"]
        if pnl is None or P is None:
            continue
        implied = (C * (1 - P) - pnl) if pnl > 0 else (-pnl - C * P)
        errs.append(abs(implied - round(fee_pc(P) * C, 2)))
    check = {"n": len(errs), "mean_abs_err": round(sum(errs) / len(errs), 4) if errs else None,
             "rule": "the bot's pnl is NET of fees: fee = 0.07*C*P*(1-P) rounded to the cent (matches the last 40 trades to <= 1 cent; "
                     "average price is rounded in the feed)"}
    return {"formula": "taker fee = ceil-to-cent(0.07 x contracts x price x (1 - price)) [third-party descriptions of Kalshi's schedule; "
                       "the bot's own pnl confirms ~0.07]", "maker_formula": "maker fee = 0.0175 x C x P x (1 - P) where maker fees apply",
            "rows": rows, "drag": drag, "check_vs_trades": check}


def buckets_section(feed, rng, sims):
    rows, raw = [], []
    for b in feed.get("buckets", []):
        c = next((c for c in feed["calibration"] if c["n"] == b["trades"]), None)
        p = c["p"] if c else (b["lo"] + b["hi"]) / 2
        lab = f"{int(round(b['lo'] * 100))}-{int(round(b['hi'] * 100))}c"
        raw.append((lab, b, p))
        rows.append(analyse(lab, b["trades"], b["wins"], b["losses"], b["staked"], b["pnl"], p, rng, sims, b["lo"], b["hi"]))

    def merge(label, pick):
        sel = [(b, p) for lab, b, p in raw if pick(b)]
        if not sel:
            return None
        n = sum(b["trades"] for b, _ in sel)
        w = sum(b["wins"] for b, _ in sel)
        l = sum(b["losses"] for b, _ in sel)
        stk = sum(b["staked"] for b, _ in sel)
        pnl = sum(b["pnl"] for b, _ in sel)
        p = sum(b["trades"] * pp for b, pp in sel) / n
        row = analyse(label, n, w, l, stk, pnl, p, rng, sims, min(b["lo"] for b, _ in sel), max(b["hi"] for b, _ in sel))
        row["fees_est"] = round(sum(TAKER * b["staked"] * (1 - pp) for b, pp in sel), 2)     # per bucket: fees are concave in price
        return row

    merged = [merge("90-95c (band)", lambda b: abs(b["lo"] - 0.9) < 1e-9),
              merge("95-99c (band; feed cannot split 98c+)", lambda b: b["lo"] >= 0.95),
              merge("<90c (all)", lambda b: b["hi"] <= 0.9 + 1e-9),
              merge("<95c (all)", lambda b: b["hi"] <= 0.95 + 1e-9),
              merge("60-90c", lambda b: 0.6 - 1e-9 <= b["lo"] and b["hi"] <= 0.9 + 1e-9),
              merge("all settled buys", lambda b: True)]
    return rows, [m for m in merged if m]


def categories_section(feed, rng, sims):
    prices = {}
    for t in feed.get("trades", []):
        if t.get("action") == "buy" and t.get("price"):
            prices.setdefault(t["category"], []).append(t["price"])
    glob = feed.get("stats", {}).get("avg_price", 0.94)
    out = []
    for c in feed.get("categories", []):
        ps = prices.get(c["name"], [])
        p, src = (sum(ps) / len(ps), f"mean of {len(ps)} recent trades") if len(ps) >= 3 else (glob, "feed avg_price (proxy)")
        row = analyse(c["name"], c["trades"], c["wins"], c["losses"], c["staked"], c["pnl"], p, rng, sims)
        row["group"] = c.get("group")
        row["price_source"] = src
        out.append(row)
    return out


def strategies_section(feed):
    by = {}
    for t in feed.get("trades", []):
        if t.get("action") == "buy" and t.get("price"):
            by.setdefault(t["strategy"], []).append(t["price"])
    out = []
    for s in feed.get("strategies", []):
        n, w, l, pnl = s["trades"], s["wins"], s["losses"], s["total_pnl"]
        hit = w / n if n else float("nan")
        wl, wh = wilson(w, n)
        ps = by.get(s["name"], [])
        sp = sum(ps) / len(ps) if ps else None
        row = {"name": s["name"], "mode": s.get("mode"), "n": n, "wins": w, "losses": l, "win_rate": round(hit, 4),
               "wilson_lo": round(wl, 4), "wilson_hi": round(wh, 4), "pnl": pnl, "pnl_per_trade": round(pnl / n, 3) if n else None,
               "sample_n": len(ps), "sample_price": round(sp, 4) if sp else None,
               "price_cap": round(price_cap(hit), 4), "price_cap_lo": round(price_cap(wl), 4),
               "loss_rate": round(l / n, 4) if n else None, "loss_rate_lo": round(1 - wh, 4), "loss_rate_hi": round(1 - wl, 4),
               "low_n": n < LOW_N}
        if sp and len(ps) >= 3:
            be = breakeven_win_rate(sp)
            row["breakeven_win_rate"] = round(be, 4)
            row["breakeven_loss_rate"] = round(1 - be, 4)
            row["p_one_sided"] = round(binom_sf(w, n, min(be, 0.9999)), 4)
            row["edge_pp"] = round((hit - be) * 100, 2)
        if row["low_n"]:
            row["verdict"] = "too few trades (n<30)"
        elif "breakeven_win_rate" in row:
            row["verdict"] = ("negative (CI below break-even)" if wh < row["breakeven_win_rate"] else
                              "positive (CI above break-even)" if wl > row["breakeven_win_rate"] else "not distinguishable from 0")
        else:
            row["verdict"] = "price unknown: pnl %s; needs avg entry below %.1fc" % ("positive" if pnl > 0 else "negative",
                                                                                      row["price_cap"] * 100)
        out.append(row)
    return out


def sample_section(feed):
    tr = [t for t in feed.get("trades", []) if t.get("action") == "buy" and t.get("pnl") is not None]

    def grp(key):
        d = {}
        for t in tr:
            k = key(t)
            g = d.setdefault(k, {"n": 0, "wins": 0, "pnl": 0.0, "stake": 0.0})
            g["n"] += 1
            g["wins"] += 1 if t["pnl"] > 0 else 0
            g["pnl"] += t["pnl"]
            g["stake"] += t["contracts"] * t["price"]
        return [{"key": k, **{kk: (round(v, 2) if isinstance(v, float) else v) for kk, v in g.items()}, "low_n": g["n"] < LOW_N}
                for k, g in sorted(d.items(), key=lambda kv: str(kv[0]))]
    mins, win15 = [], {}
    for t in tr:
        ex = parse_expiry(t["ticker"])
        if ex is None:
            continue
        m = (ex.timestamp() - t["t"]) / 60
        mins.append((t["strategy"], m))
        if "15M" in t["ticker"]:
            w = win15.setdefault(ex.isoformat(), {"bets": 0, "stake": 0.0, "losses": 0})
            w["bets"] += 1
            w["stake"] += t["contracts"] * t["price"]
            w["losses"] += 1 if t["pnl"] < 0 else 0
    tte = {}
    for s, m in mins:
        tte.setdefault(s, []).append(m)
    tte_out = {s: {"n": len(v), "mean_min": round(sum(v) / len(v), 1), "min": round(min(v), 1), "max": round(max(v), 1)} for s, v in tte.items()}
    multi = [w for w in win15.values() if w["bets"] >= 2]
    wins_all = list(win15.values())
    bal = feed.get("balance") or 1
    return {"n": len(tr), "low_n": True, "by_strategy": grp(lambda t: t["strategy"]), "by_side": grp(lambda t: t["side"]),
            "by_asset": grp(lambda t: t["asset"]),
            "by_hour_et": grp(lambda t: (parse_expiry(t["ticker"]) or dt.datetime(2000, 1, 1, tzinfo=ET)).hour),
            "minutes_to_expiry": tte_out,
            "windows15m": {"windows": len(wins_all), "windows_with_2plus_bets": len(multi),
                           "bets_in_multi_windows": sum(w["bets"] for w in multi),
                           "max_bets_in_one_window": max((w["bets"] for w in wins_all), default=0),
                           "max_stake_in_one_window": round(max((w["stake"] for w in wins_all), default=0), 2),
                           "max_stake_pct_of_balance": round(max((w["stake"] for w in wins_all), default=0) / bal, 3),
                           "losses_in_multi_windows": sum(w["losses"] for w in multi),
                           "note": "one loss in 40 trades: same-window loss correlation cannot be measured from the feed"}}


def risk_section(feed, rng, sims, run_sims):
    days = feed.get("days", [])
    pn = np.array([v for _, v in days], dtype=float)
    bal_now, total = feed.get("balance"), feed.get("total_pnl")
    start = bal_now - total
    path, b = [], start
    for d, v in days:
        path.append({"date": d, "start": round(b, 2), "pnl": v, "ret": round(v / b, 4) if b > 0 else None})
        b += v
    rets = np.array([p["ret"] for p in path if p["ret"] is not None])
    losses_sum = float(pn[pn < 0].sum())
    worst5 = float(np.sort(pn)[:5].sum())
    streak = best = 0
    for v in pn:
        streak = streak + 1 if v < 0 else 0
        best = max(best, streak)
    ac1 = float(np.corrcoef(pn[:-1], pn[1:])[0, 1]) if len(pn) > 3 else None
    ret_ac1 = float(np.corrcoef(rets[:-1], rets[1:])[0, 1]) if len(rets) > 3 else None
    peak = max([start] + [p["start"] + p["pnl"] for p in path])
    daily = {"days": len(days), "start_balance_reconstructed": round(start, 2), "peak_balance": round(peak, 2),
             "drawdown_from_peak": round(1 - bal_now / peak, 3), "mean_day": round(float(pn.mean()), 2), "sd_day": round(float(pn.std(ddof=1)), 2),
             "negative_days": int((pn < 0).sum()), "worst_day": round(float(pn.min()), 2), "best_day": round(float(pn.max()), 2),
             "worst5_days_sum": round(worst5, 2), "worst5_pct_of_all_losing_days": round(worst5 / losses_sum, 3),
             "longest_negative_streak_days": best, "lag1_autocorr_pnl": round(ac1, 3) if ac1 is not None else None,
             "lag1_autocorr_return": round(ret_ac1, 3) if ret_ac1 is not None else None,
             "note": "start balance is reconstructed as balance - total_pnl (assumes no deposits / withdrawals)"}
    # Kelly on the late-favourite book and the buckets
    kelly = {"bankroll": bal_now, "feed_kelly": feed.get("kelly")}
    kl = []
    strat = {s["name"]: s for s in feed.get("strategies", [])}
    lf = strat.get("Late favourite (BTC hourly)")
    lf_prices = [t["price"] for t in feed["trades"] if t["strategy"] == "Late favourite (BTC hourly)"]
    p_lf = sum(lf_prices) / len(lf_prices) if lf_prices else 0.978
    cases = []
    if lf:
        cases.append(("Late favourite (BTC hourly)", p_lf, lf["wins"], lf["losses"]))
    for b in feed.get("buckets", []):
        if b["lo"] >= 0.95:
            c = next(c for c in feed["calibration"] if c["n"] == b["trades"])
            cases.append((f"bucket {int(b['lo'] * 100)}-{int(b['hi'] * 100)}c", c["p"], b["wins"], b["losses"]))
    grid = np.linspace(0, 0.5, 501)
    for label, p, w, l in cases:
        f = fee_pc(p)
        gain, loss = (1 - p - f) / p, (p + f) / p            # per $ staked: win +gain, lose -loss(incl. fee)
        n = w + l

        def best_frac(a, bb):
            q = rng.beta(a, bb, size=4000)[:, None]
            g = q * np.log1p(grid[None, :] * gain) + (1 - q) * np.log(1 - grid[None, :] * loss)
            m = g.mean(axis=0)
            i = int(m.argmax())
            return float(grid[i]), float(m[i])
        k = 200                                                 # prior: the market price is right, worth 200 trades
        flat = best_frac(1 + w, 1 + l)
        prior = best_frac(k * p + w, k * (1 - p) + l)
        q_hat = w / n
        point = max(0.0, (q_hat * gain - (1 - q_hat) * loss) / (gain * loss))
        kl.append({"case": label, "price": round(p, 4), "n": n, "win_rate": round(q_hat, 4), "win_per_dollar": round(gain, 4),
                   "loss_per_dollar": round(loss, 4), "kelly_point_estimate": round(point, 3),
                   "kelly_flat_prior_posterior": flat[0], "kelly_market_prior_posterior": prior[0],
                   "dollars_at_bankroll_point": round(point * bal_now, 2), "dollars_at_bankroll_posterior": round(prior[0] * bal_now, 2),
                   "note": "Kelly with parameter uncertainty: expected log growth over the posterior of the win rate"})
    kelly["cases"] = kl
    # independent-trade yardstick for the daily swing: if the 1,845 trades were independent and the size model held
    allr = analyse("all", feed["stats"]["trades"], feed["stats"]["wins"], feed["stats"]["losses"], feed["stats"]["staked"],
                   feed["stats"]["pnl"], feed["stats"]["avg_price"], np.random.default_rng(0), 10)
    W, L = allr["implied_win_stake"] * ((1 / feed["stats"]["avg_price"] - 1) - TAKER * (1 - feed["stats"]["avg_price"])), \
        allr["implied_loss_stake"] * (1 + TAKER * (1 - feed["stats"]["avg_price"]))
    pl = feed["stats"]["losses"] / feed["stats"]["trades"]
    var_t = (1 - pl) * W * W + pl * L * L - ((1 - pl) * W - pl * L) ** 2
    n_day = feed["stats"]["trades"] / max(1, len(days))
    daily["trades_per_day"] = round(n_day, 1)
    daily["avg_win_dollars"], daily["avg_loss_dollars"] = round(W, 2), round(L, 2)
    daily["sd_day_if_independent"] = round(math.sqrt(var_t * n_day), 2)
    daily["overdispersion_ratio"] = round(daily["sd_day"] / daily["sd_day_if_independent"], 2)
    # what-if: k bets in one window, each loses with prob p, losses correlated with rho (beta-binomial, exact)
    corr = []
    for k in (3,):
        for rho in (0.0, 0.2, 0.5, 0.8):
            pp = 0.05
            if rho == 0:
                pmf = [math.comb(k, j) * pp ** j * (1 - pp) ** (k - j) for j in range(k + 1)]
            else:
                a = pp * (1 - rho) / rho
                bb = (1 - pp) * (1 - rho) / rho
                pmf = [math.comb(k, j) * math.exp(math.lgamma(j + a) + math.lgamma(k - j + bb) - math.lgamma(k + a + bb)
                                                  - math.lgamma(a) - math.lgamma(bb) + math.lgamma(a + bb)) for j in range(k + 1)]
            corr.append({"bets_in_window": k, "p_loss_each": pp, "loss_correlation": rho, "p_zero_losses": round(pmf[0], 4),
                         "p_2plus_losses": round(sum(pmf[2:]), 4), "p_all_lose": round(pmf[k], 5),
                         "relative_risk_all_lose_vs_independent": round(pmf[k] / pp ** k, 1)})
    out = {"daily": daily, "balance_path": path, "kelly": kelly, "correlation_what_if": corr, "sims": {}}
    if not run_sims:
        return out
    # ---- sim A: forward, late favourite (the only 15-min-free live strategy), real sample price, real fee rounding
    pw = {"late_favourite": []}
    horizon, per_day, min_bet_bal = 90, 12, 6.0
    wl, _ = wilson(lf["wins"], lf["wins"] + lf["losses"]) if lf else (0.95, 1)
    scen = [("observed (Beta posterior of 179 W / 3 L)", "beta"), ("fair price, zero gross edge (q = price)", "fair"),
            ("pessimistic (q = lower 95% bound)", "lower")]
    pols = [("fixed 6 contracts (today)", ("fix", 6)), ("fixed 3 contracts", ("fix", 3)), ("fixed 1 contract", ("fix", 1)),
            ("10% of bankroll", ("frac", 0.10)), ("5% of bankroll", ("frac", 0.05)), ("2% of bankroll", ("frac", 0.02))]
    npath = min(sims, 10000)
    price = round(p_lf, 3)
    for sname, skind in scen:
        if skind == "beta":
            q = rng.beta(1 + lf["wins"], 1 + lf["losses"], size=npath)
        elif skind == "fair":
            q = np.full(npath, price)
        else:
            q = np.full(npath, wl)
        for pname, (pk, pv) in pols:
            bal = np.full(npath, float(bal_now))
            alive = np.ones(npath, bool)
            for _ in range(horizon * per_day):
                c = np.full(npath, float(pv)) if pk == "fix" else np.maximum(1.0, np.floor(pv * bal / price))
                cost = c * price
                can = alive & (bal >= np.maximum(cost, min_bet_bal))
                alive &= bal >= min_bet_bal
                win = rng.random(npath) < q
                fee = np.round(TAKER * c * price * (1 - price), 2)
                delta = np.where(win, c * (1 - price) - fee, -cost - fee)
                bal = np.where(can, bal + delta, bal)
            ruined = bal < min_bet_bal
            pw["late_favourite"].append({"scenario": sname, "policy": pname, "horizon_days": horizon, "bets_per_day": per_day, "price": price,
                                         "p_ruin": round(float(ruined.mean()), 4), "p_below_half": round(float((bal < bal_now / 2).mean()), 4),
                                         "median_end": round(float(np.median(bal)), 2), "p5_end": round(float(np.percentile(bal, 5)), 2),
                                         "p95_end": round(float(np.percentile(bal, 95)), 2), "mean_end": round(float(bal.mean()), 2)})
    # ---- sim B: bootstrap of the real daily returns (whole bot as it was traded Sep 23 - Nov 2, mostly 15-min era)
    hb = []
    for days_h in (30, 90):
        for kind, block in (("iid days", 1), ("5-day blocks", 5)):
            bal = np.full(npath, float(bal_now))
            ruined = np.zeros(npath, bool)
            t = 0
            while t < days_h:
                if block == 1:
                    r = rng.choice(rets, size=npath)
                    steps = 1
                else:
                    st = rng.integers(0, len(rets) - block + 1, size=npath)
                    steps = min(block, days_h - t)
                    for j in range(steps):
                        bal = np.where(ruined, bal, bal * (1 + rets[st + j]))
                        ruined |= bal < 10.0
                    t += steps
                    continue
                bal = np.where(ruined, bal, bal * (1 + r))
                ruined |= bal < 10.0
                t += 1
            hb.append({"method": kind, "horizon_days": days_h, "start": bal_now, "ruin_below": 10.0,
                       "p_ruin": round(float(ruined.mean()), 4), "p_below_half": round(float((bal < bal_now / 2).mean()), 4),
                       "median_end": round(float(np.median(bal)), 2), "p5_end": round(float(np.percentile(bal, 5)), 2),
                       "p95_end": round(float(np.percentile(bal, 95)), 2),
                       "note": "returns = daily pnl / reconstructed start-of-day balance; includes the 15-min book that is now OFF"})
    out["sims"] = {"late_favourite": pw["late_favourite"], "history_bootstrap": hb,
                   "assumptions": "late favourite: 12 bets/day (recent sample), price = mean recent entry, fee = 0.07*C*P*(1-P) rounded to the cent, "
                                  "ruin = balance < $6 (cannot fund the smallest bet)"}
    return out


IDEAS = [
    {"id": 1, "title": "Price floor: only buy 95c and above (the pocket that pays)",
     "why": "In the feed the 95-97c and 97-99c buckets are +$137 and +$69 (hit rate 1-1.7 points above price), while 90-95c is -$248. "
            "The floor is chosen after seeing the result, so it must be proven forward.",
     "how_to_test": "Paper-log every candidate the bot sees (price, side, asset, strategy, result) with a pre-registered rule 'price >= 0.95'. "
                    "Judge on win rate minus (price + fee) with a Wilson interval; the feed's 40-trade window is too short, so ask the VM chat "
                    "for a one-off CSV of `orders` (ts, ticker, side, book, filled, avg_price, pnl).", "n_needed": 600},
    {"id": 2, "title": "Maker-side entries (post a resting limit one cent better)",
     "why": "Fees are about $73 of the $62.8 loss: gross edge is about zero, the toll is the loss. The maker fee is about a quarter of the taker fee "
            "(0.0175 vs 0.07 x C x P x (1-P)), which would cut the toll to about $18. Risk: you only get filled when price moves against you.",
     "how_to_test": "Paper: for each real signal record the bid/ask at signal time, post a virtual limit at the bid+1c and count a fill only "
                    "when trades print through it; compare fill rate and the win rate of FILLED versus all signals (adverse selection).", "n_needed": 300},
    {"id": 3, "title": "Distance-to-strike / volatility filter for the hourly BTC late favourite",
     "why": "The 3 late-favourite losses are 'BTC crossed the strike in the last minutes'. The ticker holds the strike and the trade time, "
            "so the distance in volatility units (|spot - strike| / (sigma x sqrt(minutes left))) is computable from free public spot candles.",
     "how_to_test": "Join the trade list with public 1-minute BTC spot candles (any free exchange feed, not Kalshi). Bucket trades by z-distance, "
                    "check whether the three losses sit in the lowest bucket, then paper a minimum-z rule.", "n_needed": 400},
    {"id": 4, "title": "One bet per 15-minute window (correlation cap)",
     "why": "In the last 40 trades up to 3 coins were bought in the same 15-minute window; coins move together, so those bets are one bet. "
            "The XRP / SOL / alt categories lose while BTC wins: alts are noisier and more correlated to one BTC shock.",
     "how_to_test": "From the order list group by expiry, measure the phi correlation of same-window outcomes, then replay 'only the best-priced coin per window' "
                    "and 'BTC and ETH only' and compare ROI and worst day.", "n_needed": 500},
    {"id": 5, "title": "Hour-of-day and settlement-average filter",
     "why": "Hourly BTC contracts settle on a short average of the index just before the hour; thin overnight books (00:00-06:00 ET) may price the "
            "last minutes worse. The feed cannot split results by hour (only 40 trades), so this is a pure paper test.",
     "how_to_test": "Tag each paper candidate with expiry hour (ET) and minutes-to-expiry at entry; compare win rate minus price by hour block "
                    "(00-06, 06-12, 12-18, 18-24) and by 3 / 6 / 10 minutes before expiry.", "n_needed": 800},
    {"id": 6, "title": "Negative control: fading the extremes (buy the 2c side)",
     "why": "If favourites were over-priced, the 1-3c side would pay. The feed says the opposite: 97-99c favourites win 98.6% vs 97.7% priced. "
            "Keep it as a control: log the longshot side on paper at 1 contract and confirm it loses about the fee plus the favourites' premium.",
     "how_to_test": "Paper 1-contract buys of the opposite side of each favourite signal; expect negative EV. Do not trade it.", "n_needed": 400},
]


def build_tables(feed, seed=7, sims=20000, run_sims=True):
    rng = np.random.default_rng(seed)
    brows, merged = buckets_section(feed, rng, sims)
    cats = categories_section(feed, rng, sims)
    strat = strategies_section(feed)
    out = {"schema": "kalshi_edge_tables/1", "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "method_notes": [
               "Data = the public feed only: aggregates over all settled trades plus the last 40 trades. No Kalshi API call, no secrets.",
               "The bot's pnl is net of Kalshi's taker fee, so every ROI below is after fees.",
               "win_rate / Wilson are per TRADE. roi is per DOLLAR staked. They differ when losing bets are bigger than winning ones (size_effect_pnl).",
               "roi_ci is a bootstrap (binomial draw of the win count) with the winning / losing average stakes solved from the totals; "
               "it does not include sizing luck, so it is if anything too narrow.",
               "Bucket prices are the feed's average entry price per bucket. Category prices are a proxy (recent trades or the global average).",
               "Entries are not independent (coins move together; hours cluster), so effective n is smaller than n.",
               "Buckets and bands were looked at together: expect some of the 'positive' pockets to be luck (multiple comparisons)."],
           "source": {"feed_t": feed.get("t"), "feed_pub_t": feed.get("pub_t"), "balance": feed.get("balance"), "total_pnl": feed.get("total_pnl"),
                      "stats": feed.get("stats"), "window_days": len(feed.get("days", [])),
                      "caveats": ["stats.pnl (settled buys) differs from total_pnl by the sell-back / exit rows",
                                  "strategies list is capped at 10 rows by the feed; the sum of its pnl is below total_pnl",
                                  "no cross-tab (strategy x price, asset x hour) exists in the feed"]}}
    out["buckets"] = brows + merged
    out["fees"] = fee_section(feed, brows)
    out["categories"] = cats
    out["strategies"] = strat
    out["sample"] = sample_section(feed)
    out["risk"] = risk_section(feed, np.random.default_rng(seed + 1), sims, run_sims)
    out["ideas"] = IDEAS
    allrows = [(b["label"], b) for b in brows + merged] + [("category " + c["label"], c) for c in cats]
    pos = [k for k, r in allrows if r["verdict"].startswith("positive (")]
    neg = [k for k, r in allrows if r["verdict"].startswith("negative (")]
    unc = [k for k, r in allrows if not r["low_n"] and r["verdict"].endswith("not proven")]
    out["verdict"] = {"positive_pockets": pos, "negative_pockets": neg, "unclear": unc,
                      "headline": "Gross edge is about zero; Kalshi's fee is the whole loss. Only the 95c+ entries earn after fees; 90-95c and XRP lose."}
    return out


def to_markdown(t):
    L = ["# Kalshi edge tables (generated by tools/kalshi_research.py)", "",
         f"Feed time {t['source']['feed_t']}, balance ${t['source']['balance']}, window {t['source']['window_days']} days.", "",
         "## Entry-price buckets (after fees)", "",
         "| bucket | n | win % | 95% range | price | needs | edge pts | $ staked | P&L $ | ROI | ROI 95% range | size effect $ | verdict |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    pc = lambda x: "" if x is None else f"{x * 100:.1f}"       # noqa: E731
    for b in t["buckets"]:
        L.append(f"| {b['label']}{' (grey)' if b['low_n'] else ''} | {b['n']} | {pc(b['win_rate'])} | {pc(b['wilson_lo'])}-{pc(b['wilson_hi'])} | "
                 f"{pc(b['avg_price'])} | {pc(b['breakeven_win_rate'])} | {b['edge_pp']:+.1f} | {b['staked']:,.0f} | {b['pnl']:+.2f} | "
                 f"{pc(b['roi'])}% | {pc(b['roi_ci_lo']) if b['roi_ci_lo'] is not None else 'n/a'} to {pc(b['roi_ci_hi']) if b['roi_ci_hi'] is not None else 'n/a'}% | {b['size_effect_pnl']:+.0f} | {b['verdict']} |")
    L += ["", "## Assets / categories", "", "| asset | n | win % | 95% range | $ staked | P&L $ | ROI | ROI 95% range | avg entry must be below | verdict |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for c in t["categories"]:
        L.append(f"| {c['label']}{' (grey)' if c['low_n'] else ''} | {c['n']} | {pc(c['win_rate'])} | {pc(c['wilson_lo'])}-{pc(c['wilson_hi'])} | "
                 f"{c['staked']:,.0f} | {c['pnl']:+.2f} | {pc(c['roi'])}% | {pc(c['roi_ci_lo']) if c['roi_ci_lo'] is not None else 'n/a'} to {pc(c['roi_ci_hi']) if c['roi_ci_hi'] is not None else 'n/a'}% | {pc(c['price_cap'])}c | {c['verdict']} |")
    L += ["", "## Strategies", "", "| strategy | mode | n | W/L | win % | 95% range | P&L $ | $/trade | recent entry | needs | verdict |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in t["strategies"]:
        L.append(f"| {s['name']}{' (grey)' if s['low_n'] else ''} | {s.get('mode') or ''} | {s['n']} | {s['wins']}/{s['losses']} | {pc(s['win_rate'])} | "
                 f"{pc(s['wilson_lo'])}-{pc(s['wilson_hi'])} | {s['pnl']:+.2f} | {s['pnl_per_trade']:+.3f} | {pc(s['sample_price'])} | "
                 f"{pc(s.get('breakeven_win_rate'))} | {s['verdict']} |")
    L += ["", "## Fees", "", "| price | fee per contract | fee as % of the win | break-even win rate | one loss erases N wins |", "|---|---|---|---|---|"]
    for r in t["fees"]["rows"]:
        L.append(f"| {r['price']:.2f} | {r['fee_per_contract'] * 100:.2f}c | {r['fee_pct_of_win'] * 100:.1f}% | {pc(r['breakeven_win_rate'])}% | {r['loss_to_win_ratio']:.0f} |")
    d = t["fees"]["drag"]
    L += ["", f"Estimated fees paid on settled buys: ${d['fees_est_total']:.2f} ({d['fee_pct_of_stake'] * 100:.2f}% of stake). "
          f"Net P&L ${d['pnl_net']}, so before fees about ${d['pnl_gross_est']:+.2f}.", ""]
    if t["risk"].get("sims"):
        L += ["## Ruin simulation, late favourite forward 90 days (from $%s)" % t["source"]["balance"], "",
              "| scenario | sizing | P(ruin) | P(below half) | median end $ | 5th-95th pct $ |", "|---|---|---|---|---|---|"]
        for r in t["risk"]["sims"]["late_favourite"]:
            L.append(f"| {r['scenario']} | {r['policy']} | {r['p_ruin'] * 100:.1f}% | {r['p_below_half'] * 100:.1f}% | {r['median_end']:.2f} | "
                     f"{r['p5_end']:.0f}-{r['p95_end']:.0f} |")
        L += ["", "## Ruin from the real daily returns (bootstrap)", "", "| method | days | P(ruin below $10) | P(below half) | median end $ | 5th-95th pct $ |",
              "|---|---|---|---|---|---|"]
        for r in t["risk"]["sims"]["history_bootstrap"]:
            L.append(f"| {r['method']} | {r['horizon_days']} | {r['p_ruin'] * 100:.1f}% | {r['p_below_half'] * 100:.1f}% | {r['median_end']:.2f} | "
                     f"{r['p5_end']:.0f}-{r['p95_end']:.0f} |")
    L += ["", "## Kelly (log-growth optimal share of bankroll per bet)", "", "| case | n | win % | point-estimate Kelly | with uncertainty (market prior) |", "|---|---|---|---|---|"]
    for k in t["risk"]["kelly"]["cases"]:
        L.append(f"| {k['case']} | {k['n']} | {pc(k['win_rate'])} | {k['kelly_point_estimate'] * 100:.1f}% | {k['kelly_market_prior_posterior'] * 100:.1f}% |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--feed", help="path or URL of kalshi.json (default: the public feed)")
    ap.add_argument("--out", default=os.path.join(ROOT, "research", "kalshi", "edge_tables.json"))
    ap.add_argument("--md", default=None, help="markdown tables path (default: next to --out)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--sims", type=int, default=20000)
    ap.add_argument("--no-sim", action="store_true")
    a = ap.parse_args(argv)
    feed = load_feed(a.feed)
    t = build_tables(feed, seed=a.seed, sims=a.sims, run_sims=not a.no_sim)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(t, fh, indent=1, ensure_ascii=False, default=float)
    md = a.md or os.path.splitext(a.out)[0] + ".md"
    with open(md, "w", encoding="utf-8") as fh:
        fh.write(to_markdown(t))
    print("wrote", a.out, "and", md)
    print(json.dumps(t["verdict"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
