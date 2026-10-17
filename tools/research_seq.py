"""Sequences and expectations: what the owner's nerves should expect from the locked strategy (study "seq").

On the locked trades (research/runs/baseline.json, the exact live-loop replay with the live sizing, costs included):
streak lengths, whether a loss makes the next trade worse, drawdown depth / duration, time to a new equity high, flat
stretches, the share of profit from the best 5% of trades, R percentiles, Kelly, loss-streak odds inside a 2-week eval,
"what to expect" tables (typical / bad / good month in $), and ONE sizing rule: sit out (or half size) the trade right
after a max-size loss.

  python tools/research_seq.py all          # every table (markdown) + saves the seq_* runs + research/lab/expectations.json
  python tools/research_seq.py stats        # the tables only, nothing saved
  python tools/research_seq.py rules        # the after-a-loss runs only (saved)
  python tools/research_seq.py sweep        # the $-threshold sweep + noise check behind the statuses

Everything is post-hoc on the stored trades (no engine replay). A rule only sees trades that FINISHED before the entry.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

PERIODS = (("2026", "2026-01-01", "2026-12-31"), ("2021-25", "2021-01-01", "2025-12-31"), ("all", "2000-01-01", "2100-01-01"))
RNG = np.random.default_rng(7)
WRITEUP = "what-to-expect.md"
OUT = {}


def md(rows, head):
    """A markdown table from rows of strings."""
    s = "| " + " | ".join(head) + " |\n|" + "|".join("---" if i == 0 else "---:" for i in range(len(head))) + "|\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


def usd(x):
    return f"{'-' if x < 0 else '+'}${abs(x):,.0f}"


def load_baseline():
    r = rl.load("baseline")
    T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    D = [dict(zip(r["day_cols"], a)) for a in r["days"]]
    return T, D


def span(T, D, a, z):
    return [t for t in T if a <= t["day"] <= z], [d for d in D if a <= d["date"] <= z]


def cls(t, mode):
    """W / L / S for one trade. mode "sign": by P&L sign. mode "real": +0.5R / -0.5R, scratch in between."""
    if mode == "sign":
        return "W" if t["pnl"] > 0 else "L"
    return "W" if t["r"] >= 0.5 else ("L" if t["r"] <= -0.5 else "S")


def runs_of(seq, sym):
    """Lengths of runs of `sym` in seq (a scratch 'S' does not break a run, it is skipped)."""
    out, n = [], 0
    for s in seq:
        if s == "S":
            continue
        if s == sym:
            n += 1
        else:
            if n:
                out.append(n)
            n = 0
    if n:
        out.append(n)
    return out


# ------------------------------------------------------------------------------------------------ 1. streaks
def streaks(T, label):
    res = {}
    for mode in ("sign", "real"):
        seq = [cls(t, mode) for t in T]
        L, W = runs_of(seq, "L"), runs_of(seq, "W")
        cL, cW = collections.Counter(L), collections.Counter(W)
        # expected longest loss streak if the order were random: shuffle 3000 times
        mx = []
        arr = np.array(seq)
        for _ in range(3000):
            RNG.shuffle(arr)
            r_ = runs_of(arr.tolist(), "L")
            mx.append(max(r_) if r_ else 0)
        mx = np.array(mx)
        best, n_run, start = (0, 0, 0), 0, None
        for j, sym in enumerate(seq):
            if sym == "S":
                continue
            if sym == "L":
                start = j if n_run == 0 else start
                n_run += 1
                if n_run > best[0]:
                    best = (n_run, start, j)
            else:
                n_run = 0
        seg = T[best[1]:best[2] + 1] if best[0] else []
        years = max(0.5, len(T) and (dt.date.fromisoformat(T[-1]["day"]) - dt.date.fromisoformat(T[0]["day"])).days / 365.25)
        res[mode] = {"longest": {"n": best[0], "from": seg[0]["day"] if seg else None, "to": seg[-1]["day"] if seg else None,
                                 "trades_incl_scratches": len(seg), "net": round(sum(t["pnl"] for t in seg)), "r": round(sum(t["r"] for t in seg), 1)},
                     "years": round(years, 2), "n": len(T), "losses": sum(1 for s in seq if s == "L"), "wins": sum(1 for s in seq if s == "W"),
                     "scratch": sum(1 for s in seq if s == "S"),
                     "loss_runs": dict(sorted(cL.items())), "win_runs": dict(sorted(cW.items())),
                     "max_loss_run": max(L) if L else 0, "max_win_run": max(W) if W else 0,
                     "shuffled_max_loss_run_median": float(np.median(mx)), "shuffled_max_loss_run_p90": float(np.percentile(mx, 90)),
                     "p_shuffled_ge_observed": float((mx >= (max(L) if L else 0)).mean()),
                     "loss_runs_ge4": sum(v for k, v in cL.items() if k >= 4), "loss_runs_ge6": sum(v for k, v in cL.items() if k >= 6),
                     "loss_runs_ge8": sum(v for k, v in cL.items() if k >= 8)}
        res[mode]["loss_runs_ge4_per_year"] = round(res[mode]["loss_runs_ge4"] / years, 1)
        res[mode]["loss_runs_ge6_per_year"] = round(res[mode]["loss_runs_ge6"] / years, 1)
    wins = [t["day"] for t in T if t["pnl"] > 0]
    gaps = [((dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days, a, b) for a, b in zip(wins[:-1], wins[1:])]
    g = max(gaps) if gaps else (0, None, None)
    res["longest_gap_between_winners_days"] = {"days": g[0], "from": g[1], "to": g[2]}
    OUT.setdefault("streaks", {})[label] = res
    return res


# ------------------------------------------------------------------------------------------------ 2. dependence
def dependence(T, label):
    """Is the trade after a loss worse than the trade after a win? Mean R and win% conditional on the previous outcome,
    with a permutation test (3000 shuffles of the order) on the difference of mean R (after loss - after win)."""
    r = np.array([t["r"] for t in T]); p = np.array([t["pnl"] for t in T])
    prev_loss = np.array([False] + [T[i - 1]["pnl"] < 0 for i in range(1, len(T))])
    prev_win = np.array([False] + [T[i - 1]["pnl"] > 0 for i in range(1, len(T))])
    prev_stop = np.array([False] + [T[i - 1]["r"] <= -0.9 for i in range(1, len(T))])
    prev_big = np.array([False] + [T[i - 1]["pnl"] <= -500 for i in range(1, len(T))])
    prev_fullstop = np.array([False] + [T[i - 1]["r"] <= -0.9 and T[i - 1]["mult"] >= 1.0 for i in range(1, len(T))])

    def stat(mask):
        if mask.sum() == 0:
            return {"n": 0}
        return {"n": int(mask.sum()), "avg_r": round(float(r[mask].mean()), 3), "win_pct": round(100 * float((p[mask] > 0).mean()), 1),
                "avg_usd": round(float(p[mask].mean())), "stop_pct": round(100 * float((r[mask] <= -0.9).mean()), 1)}
    obs = float(r[prev_loss].mean() - r[prev_win].mean())
    diffs = []
    idx = np.arange(len(T))
    for _ in range(3000):
        RNG.shuffle(idx)
        rr, pp = r[idx], p[idx]
        pl = np.array([False] + [pp[i - 1] < 0 for i in range(1, len(T))])
        pw = np.array([False] + [pp[i - 1] > 0 for i in range(1, len(T))])
        diffs.append(float(rr[pl].mean() - rr[pw].mean()))
    diffs = np.array(diffs)
    # Wald-Wolfowitz runs test on the W/L sequence (sign)
    seq = [cls(t, "sign") for t in T]
    n1, n2 = seq.count("W"), seq.count("L")
    runs = 1 + sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1])
    mu = 2 * n1 * n2 / (n1 + n2) + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n1 - n2) / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    z = (runs - mu) / np.sqrt(var) if var > 0 else 0.0
    # transition matrix
    nWW = sum(1 for i in range(1, len(seq)) if seq[i - 1] == "W" and seq[i] == "W")
    nW = sum(1 for i in range(1, len(seq)) if seq[i - 1] == "W")
    nLW = sum(1 for i in range(1, len(seq)) if seq[i - 1] == "L" and seq[i] == "W")
    nL = sum(1 for i in range(1, len(seq)) if seq[i - 1] == "L")
    res = {"after_loss": stat(prev_loss), "after_win": stat(prev_win), "after_stop": stat(prev_stop), "after_big_loss_500": stat(prev_big),
           "after_full_size_stop": stat(prev_fullstop), "all": stat(np.ones(len(T), bool)),
           "diff_avg_r_loss_minus_win": round(obs, 3), "perm_p_two_sided": round(float((np.abs(diffs) >= abs(obs)).mean()), 3),
           "runs_test_z": round(float(z), 2), "runs_observed": runs, "runs_expected": round(mu, 1),
           "p_win_after_win": round(100 * nWW / nW, 1) if nW else None, "p_win_after_loss": round(100 * nLW / nL, 1) if nL else None,
           "autocorr_r_lag1": round(float(np.corrcoef(r[:-1], r[1:])[0, 1]), 3) if len(r) > 2 else None}
    OUT.setdefault("dependence", {})[label] = res
    return res


# ------------------------------------------------------------------------------------------------ 3. drawdowns
def drawdowns(D, label):
    """Drawdown episodes on the daily equity (sized $): depth, sessions peak->trough, sessions trough->recovery."""
    eq = np.cumsum([d["pnl"] for d in D]); lows = np.cumsum([d["pnl"] for d in D]) - np.array([d["pnl"] for d in D]) + np.array([d["low"] for d in D])
    peak, peak_i, episodes, cur = 0.0, -1, [], None
    for i, (e, lo) in enumerate(zip(eq, lows)):
        if e >= peak:
            if cur is not None:
                cur["recovered"] = D[i]["date"]; cur["sessions_total"] = i - cur["peak_i"]
                cur["sessions_recover"] = i - cur["trough_i"]; episodes.append(cur); cur = None
            peak, peak_i = e, i
        else:
            depth = min(e, lo) - peak
            if cur is None:
                cur = {"peak": D[peak_i]["date"] if peak_i >= 0 else D[0]["date"], "peak_i": peak_i, "depth": depth, "trough": D[i]["date"], "trough_i": i}
            elif depth < cur["depth"]:
                cur["depth"], cur["trough"], cur["trough_i"] = depth, D[i]["date"], i
    if cur is not None:
        cur["recovered"] = None; cur["sessions_total"] = len(D) - 1 - cur["peak_i"]; cur["sessions_recover"] = None; episodes.append(cur)
    eps = [e for e in episodes if e["depth"] <= -300]        # ignore noise dips under $300
    depths = np.array([-e["depth"] for e in eps]) if eps else np.array([0.0])
    tot = np.array([e["sessions_total"] for e in eps]) if eps else np.array([0])
    rec_l = [e["sessions_recover"] for e in eps if e["sessions_recover"] is not None]
    rec = np.array(rec_l) if rec_l else np.array([0])
    # flat stretches: sessions between consecutive new equity highs
    gaps, last_hi, peak = [], 0, -1e9
    for i, e in enumerate(eq):
        if e >= peak:
            gaps.append(i - last_hi); last_hi, peak = i, e
    open_gap = len(eq) - 1 - last_hi
    top = sorted(eps, key=lambda e: e["depth"])[:6]
    res = {"episodes_300plus": len(eps), "depth_pct": {k: round(float(np.percentile(depths, k))) for k in (50, 75, 90, 100)},
           "sessions_total_pct": {k: round(float(np.percentile(tot, k)), 1) for k in (50, 75, 90, 100)},
           "sessions_recover_pct": {k: round(float(np.percentile(rec, k)), 1) for k in (50, 75, 90, 100)},
           "longest_flat_sessions": int(max(gaps + [open_gap])), "longest_flat_weeks": round(max(gaps + [open_gap]) / 5, 1),
           "open_flat_sessions_at_end": int(open_gap), "at_high_now": bool(open_gap == 0),
           "ge_1000": int((depths >= 1000).sum()), "ge_2000": int((depths >= 2000).sum()), "ge_4000": int((depths >= 4000).sum()),
           "sessions": len(D),
           "top": [{"peak": e["peak"], "trough": e["trough"], "recovered": e["recovered"], "depth": round(e["depth"]),
                    "weeks_to_trough": round((e["trough_i"] - e["peak_i"]) / 5, 1),
                    "weeks_total": round(e["sessions_total"] / 5, 1) if e["sessions_total"] is not None else None} for e in top]}
    OUT.setdefault("drawdowns", {})[label] = res
    return res


# ------------------------------------------------------------------------------------------------ 4. concentration + R
def concentration(T, label):
    p = np.sort(np.array([t["pnl"] for t in T]))[::-1]
    gross = p[p > 0].sum(); net = p.sum()
    k5 = max(1, int(round(0.05 * len(p)))); k10 = max(1, int(round(0.10 * len(p)))); k1 = max(1, int(round(0.01 * len(p))))
    r = np.array([t["r"] for t in T])
    res = {"n": len(p), "net": round(float(net)), "gross_profit": round(float(gross)), "gross_loss": round(float(-p[p < 0].sum())),
           "top1_n": k1, "top1_sum": round(float(p[:k1].sum())), "top5_n": k5, "top5_sum": round(float(p[:k5].sum())),
           "top10_n": k10, "top10_sum": round(float(p[:k10].sum())),
           "top5_share_of_gross": round(100 * float(p[:k5].sum() / gross), 1) if gross else None,
           "top5_share_of_net": round(100 * float(p[:k5].sum() / net), 1) if net > 0 else None,
           "net_without_top5": round(float(net - p[:k5].sum())), "net_without_best1": round(float(net - p[0])),
           "net_without_best3": round(float(net - p[:3].sum())),
           "winners_needed_for_net": int(np.searchsorted(np.cumsum(p), net)) + 1 if net > 0 else None,
           "r_pct": {k: round(float(np.percentile(r, k)), 2) for k in (5, 10, 25, 50, 75, 90, 95, 99)},
           "usd_pct": {k: round(float(np.percentile(np.array([t["pnl"] for t in T]), k))) for k in (5, 10, 25, 50, 75, 90, 95, 99)},
           "avg_r": round(float(r.mean()), 3), "std_r": round(float(r.std()), 3), "avg_win_r": round(float(r[r > 0].mean()), 2),
           "avg_loss_r": round(float(r[r < 0].mean()), 2), "win_pct": round(100 * float((r > 0).mean()), 1),
           "pct_ge_2r": round(100 * float((r >= 2).mean()), 1), "pct_ge_3r": round(100 * float((r >= 3).mean()), 1),
           "pct_full_stop": round(100 * float((r <= -0.9).mean()), 1), "pct_scratch": round(100 * float((np.abs(r) < 0.25).mean()), 1),
           "avg_win_usd": round(float(p[p > 0].mean())), "avg_loss_usd": round(float(p[p < 0].mean())), "biggest_win": round(float(p[0])),
           "biggest_loss": round(float(p[-1]))}
    OUT.setdefault("concentration", {})[label] = res
    return res


# ------------------------------------------------------------------------------------------------ 5. Kelly / optimal f
def kelly(T, label, account=50000.0, unit=800.0):
    """Growth-optimal multiplier k on today's sizing: every trade's P&L scales with k (risk k x $800 up to a 20-pt stop,
    the same wide-stop scaling, cold quarter and late half). Maximise mean log(1 + k * pnl / account). Also on a $2,000
    bankroll (the MFFU trailing max loss is the real account for an eval) and the textbook Kelly from win% and payoff."""
    p = np.array([t["pnl"] for t in T]); r = np.array([t["r"] for t in T])

    def best_k(bank):
        ks = np.linspace(0.05, 60, 1200)
        g = []
        for k in ks:
            x = 1 + k * p / bank
            g.append(np.mean(np.log(x)) if (x > 0).all() else -np.inf)
        g = np.array(g); i = int(np.argmax(g))
        return float(ks[i]), float(g[i])
    k50, g50 = best_k(account); k2, g2 = best_k(2000.0)
    # growth at k=1 (today) and the drawdown at k*
    g_now = float(np.mean(np.log(1 + p / account)))
    # textbook Kelly on R: f* = W - (1-W)/B, W = win rate (pnl>0), B = avg win R / avg |loss R|
    W = float((r > 0).mean()); B = float(r[r > 0].mean() / -r[r < 0].mean()) if (r < 0).any() and (r > 0).any() else None
    f_text = W - (1 - W) / B if B else None
    # optimal f on R (unit risk = 1R): maximise mean log(1 + f R)
    fs = np.linspace(0.001, 0.95, 950)
    gr = [np.mean(np.log(1 + f * r)) if (1 + f * r > 0).all() else -np.inf for f in fs]
    f_opt = float(fs[int(np.argmax(gr))]) if np.isfinite(max(gr)) else None
    avg_risk = float(np.mean([t["risk_usd"] for t in T])); med_risk = float(np.median([t["risk_usd"] for t in T]))
    res = {"n": len(T), "k_opt_50k": round(k50, 2), "kelly_risk_50k": round(k50 * unit), "live_fraction_of_kelly_50k": round(1 / k50, 3) if k50 else None,
           "k_opt_2k": round(k2, 3), "kelly_risk_2k_bank": round(k2 * unit), "live_fraction_of_kelly_2k": round(1 / k2, 2) if k2 else None,
           "growth_per_trade_now_pct": round(100 * g_now, 3), "growth_per_trade_kelly_pct": round(100 * g50, 3),
           "textbook_W": round(100 * W, 1), "textbook_B": round(B, 2) if B else None, "textbook_f_pct_of_bank_per_R": round(100 * f_text, 1) if f_text is not None else None,
           "optimal_f_per_R_pct": round(100 * f_opt, 1) if f_opt is not None else None,
           "live_full_size_pct_of_50k": round(100 * unit / account, 2), "live_full_size_pct_of_2k": round(100 * unit / 2000, 1),
           "avg_risk_usd": round(avg_risk), "median_risk_usd": round(med_risk), "avg_risk_pct_of_50k": round(100 * avg_risk / account, 2)}
    OUT.setdefault("kelly", {})[label] = res
    return res


# ------------------------------------------------------------------------------------------------ 6. eval-window streak risk
def eval_window_risk(T, D, label, H=10):
    """Every rolling window of H sessions (a 2-week eval): the longest loss streak inside it, 4+ / 6+ losses in total, the
    worst dip from the window start (the $ the eval would be down at its lowest)."""
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    out = {"windows": 0, "streak_ge4": 0, "streak_ge6": 0, "losses_ge4": 0, "losses_ge6": 0, "real_streak_ge4": 0, "real_streak_ge6": 0,
           "dip_ge1000": 0, "dip_ge2000": 0, "trades": [], "net": [], "max_loss_streak": 0}
    for i in range(len(D) - H + 1):
        win = D[i:i + H]
        tr = [t for d in win for t in by.get(d["date"], [])]
        seq = [cls(t, "sign") for t in tr]; seqr = [cls(t, "real") for t in tr]
        L = runs_of(seq, "L"); Lr = runs_of(seqr, "L")
        m = max(L) if L else 0
        out["windows"] += 1; out["trades"].append(len(tr)); out["net"].append(sum(t["pnl"] for t in tr))
        out["max_loss_streak"] = max(out["max_loss_streak"], m)
        out["streak_ge4"] += m >= 4; out["streak_ge6"] += m >= 6
        mr = max(Lr) if Lr else 0
        out["real_streak_ge4"] += mr >= 4; out["real_streak_ge6"] += mr >= 6
        nl = seq.count("L"); out["losses_ge4"] += nl >= 4; out["losses_ge6"] += nl >= 6
        cum, dip = 0.0, 0.0
        for d in win:
            dip = min(dip, cum + d["low"]); cum += d["pnl"]; dip = min(dip, cum)
        out["dip_ge1000"] += dip <= -1000; out["dip_ge2000"] += dip <= -2000
    n = max(1, out["windows"])
    tr = np.array(out["trades"]); net = np.array(out["net"])
    # independence approximation: P(at least one run of >=k losses in m trials) with p = loss rate
    pL = float(np.mean([t["pnl"] < 0 for t in T])); m = float(tr.mean())

    def p_run(k, m, p):
        # exact via Markov chain on run length
        m = int(round(m)); st = np.zeros(k + 1); st[0] = 1.0
        for _ in range(m):
            new = np.zeros(k + 1)
            new[k] = st[k]
            for j in range(k):
                new[0] += st[j] * (1 - p)
                new[min(k, j + 1)] += st[j] * p
            st = new
        return float(st[k])
    res = {"windows": out["windows"], "trades_per_window_median": float(np.median(tr)), "trades_per_window_p10_p90": [float(np.percentile(tr, 10)), float(np.percentile(tr, 90))],
           "pct_streak_ge4": round(100 * out["streak_ge4"] / n, 1), "pct_streak_ge6": round(100 * out["streak_ge6"] / n, 1),
           "pct_real_streak_ge4": round(100 * out["real_streak_ge4"] / n, 1), "pct_real_streak_ge6": round(100 * out["real_streak_ge6"] / n, 1),
           "pct_losses_ge4": round(100 * out["losses_ge4"] / n, 1), "pct_losses_ge6": round(100 * out["losses_ge6"] / n, 1),
           "pct_dip_ge1000": round(100 * out["dip_ge1000"] / n, 1), "pct_dip_ge2000": round(100 * out["dip_ge2000"] / n, 1),
           "max_loss_streak_in_window": out["max_loss_streak"], "loss_rate_pct": round(100 * pL, 1),
           "indep_p_streak4": round(100 * p_run(4, m, pL), 1), "indep_p_streak6": round(100 * p_run(6, m, pL), 1),
           "net_pct": {k: round(float(np.percentile(net, k))) for k in (10, 25, 50, 75, 90)}}
    OUT.setdefault("eval_window", {})[label] = res
    return res


# ------------------------------------------------------------------------------------------------ 7. what to expect
def expect(T, D, label):
    months = collections.defaultdict(lambda: {"net": 0.0, "n": 0, "wins": 0, "losses": 0, "best": 0.0, "worst": 0.0})
    for t in T:
        m = months[t["day"][:7]]; m["net"] += t["pnl"]; m["n"] += 1; m["wins"] += t["pnl"] > 0; m["losses"] += t["pnl"] < 0
        m["best"] = max(m["best"], t["pnl"]); m["worst"] = min(m["worst"], t["pnl"])
    # months with sessions but no trades still count as $0 months
    for d in D:
        months[d["date"][:7]]
    keys = sorted(months)
    # drop partial first/last month if it has < 10 sessions
    sess = collections.Counter(d["date"][:7] for d in D)
    keys = [k for k in keys if sess[k] >= 10]
    net = np.array([months[k]["net"] for k in keys]); n = np.array([months[k]["n"] for k in keys])
    wins = np.array([months[k]["wins"] for k in keys])
    weeks = collections.defaultdict(float); wn = collections.Counter()
    for t in T:
        y, w, _ = dt.date.fromisoformat(t["day"]).isocalendar(); weeks[(y, w)] += t["pnl"]; wn[(y, w)] += 1
    for d in D:
        y, w, _ = dt.date.fromisoformat(d["date"]).isocalendar(); weeks[(y, w)]
    wk = np.array(list(weeks.values()))
    pct = lambda a, k: round(float(np.percentile(a, k)))
    res = {"months": len(keys), "month_net_pct": {k: pct(net, k) for k in (10, 25, 50, 75, 90)}, "month_mean": round(float(net.mean())),
           "pct_months_positive": round(100 * float((net > 0).mean()), 1), "pct_months_below_minus1000": round(100 * float((net <= -1000).mean()), 1),
           "pct_months_above_2000": round(100 * float((net >= 2000).mean()), 1),
           "month_trades_pct": {k: round(float(np.percentile(n, k)), 1) for k in (10, 50, 90)}, "month_wins_pct": {k: round(float(np.percentile(wins, k)), 1) for k in (10, 50, 90)},
           "best_month": [keys[int(np.argmax(net))], round(float(net.max()))], "worst_month": [keys[int(np.argmin(net))], round(float(net.min()))],
           "weeks": len(wk), "week_net_pct": {k: pct(wk, k) for k in (10, 25, 50, 75, 90)}, "pct_weeks_positive": round(100 * float((wk > 0).mean()), 1),
           "pct_weeks_zero_trades": round(100 * sum(1 for k in weeks if wn[k] == 0) / max(1, len(weeks)), 1),
           "longest_losing_month_run": max(runs_of(["L" if x < 0 else "W" for x in net], "L") or [0]),
           "longest_winning_month_run": max(runs_of(["L" if x < 0 else "W" for x in net], "W") or [0]),
           "month_table": [{"month": k, "net": round(months[k]["net"]), "n": months[k]["n"], "wins": months[k]["wins"]} for k in keys]}
    OUT.setdefault("expect", {})[label] = res
    return res


# ------------------------------------------------------------------------------------------------ 8. the rule: after a max-size loss
def prev_trade(t, ctx, raw_by_exit):
    """The most recent SIGNAL that finished before this entry (the live shadow record sees every signal, traded or not).
    Returns its sized version if it was traded in this run, else None (a skipped signal was no loss in the account)."""
    pv = None
    for x in raw_by_exit:
        if x["exit_t"] < t["entry_t"]:
            pv = x
        else:
            break
    if pv is None:
        return None
    for x in reversed(ctx["finished"]):
        if x["entry_t"] == pv["entry_t"]:
            return x
    return None


def rule_after(kind, mult, raw):
    """kind: fullstop = previous trade a full stop-out (r <= -0.9) at full engine size (no cold / late cut);
    big500 = previous trade lost $500 or more; stop = previous trade a full stop-out at any size; loss = previous P&L < 0."""
    raw_by_exit = sorted((x for x in raw["trades"] if x.get("exit_t")), key=lambda x: x["exit_t"])

    def rule(t, ctx):
        pv = prev_trade(t, ctx, raw_by_exit)
        if pv is None:
            return 1.0
        if kind == "fullstop":
            hit = pv["r"] <= -0.9 and pv["mult"] >= 1.0
        elif kind == "big500":
            hit = pv["pnl"] <= -500
        elif kind == "big300":
            hit = pv["pnl"] <= -300
        elif kind == "stop":
            hit = pv["r"] <= -0.9
        elif kind == "loss":
            hit = pv["pnl"] < 0
        elif kind == "win":
            hit = pv["pnl"] > 0
        else:
            raise ValueError(kind)
        return mult if hit else 1.0
    return rule


RULES = [
    # id, kind, mult, title, status, reason (statuses were set by hand after the threshold sweep and noise check below)
    ("seq_after_fullstop_skip", "fullstop", 0.0, "Sit out the trade after a full-size stop-out", "rejected",
     "Loses money in 2021-25 and drops 2026 under 2 setups a week. The trade after a full-size stop-out is a normal-to-good trade (+0.14R avg vs +0.06R overall)."),
    ("seq_after_fullstop_half", "fullstop", 0.5, "Half size after a full-size stop-out", "rejected",
     "Less money in both periods: the trade after a full-size stop-out is not worse than average."),
    ("seq_after_big500_skip", "big500", 0.0, "Sit out the trade after a $500+ loss", "info",
     "Too thin to judge: 26 cases in 2021-25 (+$611 from an average of -$22 a trade), 1 case in 2026 (a -$3 scratch). Not adopted."),
    ("seq_after_big500_half", "big500", 0.5, "Half size after a $500+ loss", "info",
     "Too thin to judge: 26 cases in 2021-25, 1 in 2026; +$350 over 5 years is noise. Not adopted."),
    ("seq_after_big300_half", "big300", 0.5, "Half size after a $300+ loss", "rejected",
     "Better in both periods on paper (+$187 / +$1,339) but a lucky threshold: half size after a $250+ or a $400+ loss LOSES money in 2021-25 (-$668 / -$1,461), and 2026 has 4 cases."),
    ("seq_after_stop_half", "stop", 0.5, "Half size after any full stop-out", "rejected",
     "2026 -$4,151: the trades after a stop-out include many of the big winners."),
    ("seq_after_loss_half", "loss", 0.5, "Half size after any losing trade", "rejected",
     "Half size on 78% of trades: about half the money in both periods. The next trade after a loss is not worse (dependence test)."),
    ("seq_after_loss_150", "loss", 1.5, "1.5x size after any losing trade (the opposite bet)", "rejected",
     "More money in both periods, but it is just more size (25% more $ at risk; a uniform 1.25x gets most of it): 2021-25 1-month eval fails 16.5% vs 5.2%, max DD -$11.5k vs -$9.3k."),
]


def sweep(noise_tries=400):
    """Half size / sit out after a loss of $X or more, for every X: is the $300 result a smooth effect or a lucky threshold?
    Plus a noise check: halving the same number of random trades, how often does chance beat the $300 rule in both periods?"""
    raw = rl.replay(); base = rl.size(raw); S0 = rl.score(base, raw)
    A0, B0 = S0["spans"]["2026"], S0["spans"]["2021-25"]
    T, _ = load_baseline()
    rbe = sorted((x for x in raw["trades"] if x.get("exit_t")), key=lambda x: x["exit_t"])

    def thr_rule(thr, m):
        def r_(t, ctx):
            pv = prev_trade(t, ctx, rbe)
            return m if (pv is not None and pv["pnl"] <= -thr) else 1.0
        return r_
    rows, out = [], []
    prev = [None] + T[:-1]
    for thr in (150, 200, 250, 300, 350, 400, 500, 600):
        h26 = [t for t, p in zip(T, prev) if p and p["pnl"] <= -thr and t["day"] >= "2026"]
        h21 = [t for t, p in zip(T, prev) if p and p["pnl"] <= -thr and t["day"] < "2026"]
        Sh = rl.score(rl.size(raw, rule=thr_rule(thr, 0.5)), raw); Ss = rl.score(rl.size(raw, rule=thr_rule(thr, 0.0)), raw)
        a, b, c, d = Sh["spans"]["2026"], Sh["spans"]["2021-25"], Ss["spans"]["2026"], Ss["spans"]["2021-25"]
        rec = {"thr": thr, "cases_2026": len(h26), "cases_2021_25": len(h21),
               "next_avg_r_2026": round(float(np.mean([t["r"] for t in h26])), 2) if h26 else None, "next_avg_usd_2026": round(float(np.mean([t["pnl"] for t in h26]))) if h26 else None,
               "next_avg_r_2021_25": round(float(np.mean([t["r"] for t in h21])), 2) if h21 else None, "next_avg_usd_2021_25": round(float(np.mean([t["pnl"] for t in h21]))) if h21 else None,
               "half_gain_2026": a["net"] - A0["net"], "half_gain_2021_25": b["net"] - B0["net"], "half_pf": [a["pf"], b["pf"]],
               "skip_gain_2026": c["net"] - A0["net"], "skip_gain_2021_25": d["net"] - B0["net"], "skip_tpw": [c["tpw"], d["tpw"]]}
        out.append(rec)
        rows.append((f"${thr}+", f"{len(h26)} / {len(h21)}", f"{rec['next_avg_r_2026']} / {rec['next_avg_r_2021_25']}", f"{rec['next_avg_usd_2026']} / {rec['next_avg_usd_2021_25']}",
                     usd(rec["half_gain_2026"]), usd(rec["half_gain_2021_25"]), usd(rec["skip_gain_2026"]), usd(rec["skip_gain_2021_25"]), f"{c['tpw']} / {d['tpw']}"))
    print(md(rows, ["previous trade lost", "cases 2026 / 2021-25", "next trade avg R 2026 / 2021-25", "next trade avg $ 2026 / 2021-25",
                    "half size: 2026 vs live", "2021-25 vs live", "sit out: 2026 vs live", "2021-25 vs live", "sit out: trades/wk 2026 / 2021-25"]))
    # noise check on the $300 half rule
    T3 = rl.size(raw, rule=thr_rule(300, 0.5)); S3 = rl.score(T3, raw)
    g26, g21 = S3["spans"]["2026"]["net"] - A0["net"], S3["spans"]["2021-25"]["net"] - B0["net"]
    bm = {b["entry_t"]: b["mult"] for b in base}
    hit = [t for t in T3 if t["mult"] != bm[t["entry_t"]]]
    n26 = sum(1 for t in hit if t["day"] >= "2026"); n21 = len(hit) - n26
    rng = np.random.default_rng(3)
    e26 = [t["entry_t"] for t in base if t["day"] >= "2026"]; e21 = [t["entry_t"] for t in base if t["day"] < "2026"]
    beat26 = beat21 = both = 0
    for _ in range(noise_tries):
        pick = set(rng.choice(e26, n26, replace=False).tolist()) | set(rng.choice(e21, n21, replace=False).tolist())
        Sr = rl.score(rl.size(raw, rule=lambda t, c: 0.5 if t["entry_t"] in pick else 1.0), raw)
        a = Sr["spans"]["2026"]["net"] - A0["net"] >= g26; b = Sr["spans"]["2021-25"]["net"] - B0["net"] >= g21
        beat26 += a; beat21 += b; both += a and b
    noise = {"rule": "half after a $300+ loss", "changed_2026": n26, "changed_2021_25": n21, "gain_2026": g26, "gain_2021_25": g21, "tries": noise_tries,
             "random_beats_2026": round(beat26 / noise_tries, 3), "random_beats_2021_25": round(beat21 / noise_tries, 3), "random_beats_both": round(both / noise_tries, 3)}
    print("noise check:", json.dumps(noise))
    OUT["sweep"] = out; OUT["noise"] = noise
    return out, noise


def run_rules(save=True):
    raw = rl.replay()
    base = rl.score(rl.size(raw), raw)
    rows, res = [], {}
    bm = {t["entry_t"]: t["mult"] for t in rl.size(raw)}
    for rid, kind, mult, title, status, reason in RULES:
        T = rl.size(raw, rule=rule_after(kind, mult, raw))
        S = rl.score(T, raw)
        a, b = S["spans"]["2026"], S["spans"]["2021-25"]; A, B = base["spans"]["2026"], base["spans"]["2021-25"]
        better = a["net"] > A["net"] and a["pf"] >= A["pf"] and b["net"] > B["net"] and b["pf"] >= B["pf"]
        changed = [t for t in T if t["mult"] != bm[t["entry_t"]]]
        n26 = sum(1 for t in changed if t["day"] >= "2026") + (sum(1 for t in rl.size(raw) if t["day"] >= "2026") - a["n"])
        n21 = len(changed) - sum(1 for t in changed if t["day"] >= "2026") + (sum(1 for t in rl.size(raw) if t["day"] < "2026") - b["n"])
        verdict = (f"2026 {usd(a['net'])} PF {a['pf']} ({a['tpw']}/wk) vs live {usd(A['net'])} PF {A['pf']}; "
                   f"2021-25 {usd(b['net'])} PF {b['pf']} ({b['tpw']}/wk) vs live {usd(B['net'])} PF {B['pf']}. "
                   + ("Better in both periods on paper. " if better else "Not better in both periods. ") + reason)
        res[rid] = {"title": title, "status": status, "spans": S["spans"], "verdict": verdict, "changed_2026": n26, "changed_2021_25": n21}
        rows.append((rid, title, status, a["n"], a["tpw"], usd(a["net"]), a["pf"], f"{a['dd']:,}", f"{a['p10']}/{a['f10']}", f"{a['p20']}/{a['f20']}",
                     b["n"], b["tpw"], usd(b["net"]), b["pf"], f"{b['dd']:,}", f"{b['p10']}/{b['f10']}", f"{b['p20']}/{b['f20']}", f"{n26} / {n21}"))
        if save:
            rl.save(rid, title, "risk", "Does the trade right after a (max-size) loss deserve less size, or should it be skipped?",
                    params={}, sizing={"rule": kind, "mult": mult, "on_top_of": "live sizing (cold x0.25, late x0.5)"}, trades=T, scored=S,
                    status=status, verdict=verdict, writeup=WRITEUP, tags=["seq", "sequence", "after-loss"],
                    notes="Post-hoc multiplier on the exact live-loop replay. 'Previous trade' = the last trade that had finished before this entry. "
                          "full-size stop-out = r <= -0.9 at mult 1.0 (no cold-streak or late-entry cut).")
    A, B = base["spans"]["2026"], base["spans"]["2021-25"]
    rows.insert(0, ("baseline", "Live strategy (locked)", "baseline", A["n"], A["tpw"], usd(A["net"]), A["pf"], f"{A['dd']:,}", f"{A['p10']}/{A['f10']}", f"{A['p20']}/{A['f20']}",
                    B["n"], B["tpw"], usd(B["net"]), B["pf"], f"{B['dd']:,}", f"{B['p10']}/{B['f10']}", f"{B['p20']}/{B['f20']}", ""))
    head = ["run", "rule", "status", "2026 n", "/wk", "net", "PF", "max DD", "2w pass/fail", "1m pass/fail", "2021-25 n", "/wk", "net", "PF", "max DD", "2w pass/fail", "1m pass/fail", "trades changed 2026 / 2021-25"]
    print(md(rows, head))
    OUT["rules"] = res
    return res


# ------------------------------------------------------------------------------------------------ printing
def stats(T0, D0):
    for label, a, z in PERIODS:
        T, D = span(T0, D0, a, z)
        print(f"\n===== {label}: {len(T)} trades, {len(D)} sessions")
        s = streaks(T, label)
        for mode in ("sign", "real"):
            x = s[mode]
            print(f"[{mode}] W {x['wins']} L {x['losses']} S {x['scratch']} | loss runs {x['loss_runs']} | max L run {x['max_loss_run']} "
                  f"(shuffled median {x['shuffled_max_loss_run_median']}, p90 {x['shuffled_max_loss_run_p90']}, P(>=obs) {x['p_shuffled_ge_observed']:.2f}) | "
                  f"win runs {x['win_runs']} max W {x['max_win_run']}")
        d = dependence(T, label)
        print("dependence:", json.dumps(d))
        dd = drawdowns(D, label)
        print("drawdowns:", json.dumps({k: v for k, v in dd.items() if k != "top"}))
        for e in dd["top"]:
            print("   ", e)
        c = concentration(T, label)
        print("concentration:", json.dumps(c))
        k = kelly(T, label)
        print("kelly:", json.dumps(k))
        ev = eval_window_risk(T, D, label)
        print("eval window:", json.dumps(ev))
        ex = expect(T, D, label)
        print("expect:", json.dumps({k: v for k, v in ex.items() if k != "month_table"}))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    T, D = load_baseline()
    if cmd in ("all", "stats"):
        stats(T, D)
    if cmd in ("all", "rules"):
        run_rules(save=(cmd in ("all", "rules")))
    if cmd in ("all", "sweep"):
        sweep()
    if cmd == "all":
        OUT["built"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M"); OUT["source"] = "research/runs/baseline.json (locked 2026-10-17 evening)"
        OUT["writeup"] = WRITEUP
        path = os.path.join(ROOT, "research", "lab", "expectations.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(OUT, fh, indent=1, default=float)
        print("wrote", path)


if __name__ == "__main__":
    main()
