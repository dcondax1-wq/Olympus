"""Cross-market & regime context research (study "xm", runs xm_* in research/runs/, write-up
research/writeups/cross-market-context.md, dashboard data research/lab/cross_market_context.json).

Question: does the market AROUND the setup (ES, VIX, VXN, dealer gamma, the multi-day regime, the shape of the entry day
so far) say anything about how a locked-strategy trade does? Every factor is computed from what was known at the entry
bar, attached to the exact live-loop replay of the LOCKED strategy (tools/runlib.replay, live sizing applied) and
tabulated per bucket: trades, win %, avg R, net $, PF in 2026 and in 2021-25. The strongest, consistent factors are then
tested as SIZE rules with runlib.size (exact, post hoc) and saved as runs.

  python tools/research_xm.py tables     # every factor table + research/lab/cross_market_context.json
  python tools/research_xm.py rules      # size rules for the strongest factors, saved as runs xm_*
  python tools/research_xm.py all

Factors and sources (all prior to or at the entry bar):
  1. NQ vs ES relative strength (data/ES_5m.csv, from 2025-04-13): % move of NQ minus % move of ES, signed by the
     trade direction, over (a) the session since 18:00 ET, (b) the last hour, (c) the sweep -> trigger leg.
  2. SMT divergence at the sweep: the engine's own tag (ES did not take out its prior 3-hour extreme while NQ swept)
     plus a replica with a full-session window.
  3. VIX prior close (level buckets) and its 1-day change (data/VIX_1d.csv, 2021-25 and 2026).
  4. VXN / VIX ratio, prior closes (data/VXN_1d.csv).
  5. Dealer gamma (data/GEX_1d.csv, SPX GEX / DIX, 2011 -> 2026-10-16): prior-day sign, 1-year percentile, DIX.
  6. 10-day efficiency (the live trending-day test, 0.45) vs 20-day: computed from the session closes of NQ_5m.
  7. Entry-day shape known at entry: gap vs ADR20, opening-range size vs ADR20, range so far vs ADR20, price vs the
     opening range, the day's directional efficiency so far (the engine's rg_day_er).
No look-ahead: VIX/VXN/GEX use the last value dated BEFORE the trade day; ES and NQ bars only up to the entry bar.
"""
from __future__ import annotations

import bisect
import collections
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

LAB_JSON = os.path.join(ROOT, "research", "lab", "cross_market_context.json")
WRITEUP = "research/writeups/cross-market-context.md"
ES_START = "2025-04-14"


# ------------------------------------------------------------------------------------------------ data
def _daily(path):
    df = pd.read_csv(os.path.join(ROOT, "data", path))
    df["date"] = df["date"].astype(str)
    return df.sort_values("date").reset_index(drop=True)


def prior_value(dates, values, day):
    """Last value whose date is strictly before `day` (what a trader knows before the open)."""
    k = bisect.bisect_left(dates, day) - 1
    return (values[k], k) if k >= 0 else (None, None)


def session_closes(b):
    """{trading day: close of its last bar} in order (the engine's prev_days close is the last bar before the day change)."""
    out, last = collections.OrderedDict(), None
    for i, d in enumerate(b.date_str):
        out[d] = float(b.c[i])
    return list(out.keys()), np.array(list(out.values()))


def er(closes, n):
    if len(closes) < n + 1:
        return None
    seg = closes[-(n + 1):]
    path = float(np.abs(np.diff(seg)).sum())
    return abs(float(seg[-1] - seg[0])) / path if path else None


def build_features(raw):
    """{entry_t: {feature: value}} for every raw trade."""
    from engine.data import load
    nq, es = load("NQ", "5m"), load("ES", "5m")
    es_idx = {int(t): j for j, t in enumerate(es.t)}
    nq_t = nq.t
    sdays, scloses = session_closes(nq)
    sday_pos = {d: k for k, d in enumerate(sdays)}
    # day ranges for ADR20 (completed sessions, 18:00 -> 17:00 ET)
    hi = collections.OrderedDict(); lo = collections.OrderedDict()
    for i, d in enumerate(nq.date_str):
        hi[d] = max(hi.get(d, -1e9), float(nq.h[i])); lo[d] = min(lo.get(d, 1e9), float(nq.l[i]))
    rng = np.array([hi[d] - lo[d] for d in sdays])
    vix = _daily("VIX_1d.csv"); vxn = _daily("VXN_1d.csv"); gex = _daily("GEX_1d.csv")
    vd, vc = vix["date"].tolist(), vix["close"].astype(float).values
    xd, xc = vxn["date"].tolist(), vxn["close"].astype(float).values
    gd, gv, gdix = gex["date"].tolist(), gex["gex"].astype(float).values, gex["dix"].astype(float).values
    first_day = {}
    for i, d in enumerate(nq.date_str):
        first_day.setdefault(d, i)
    F = {}
    for t in raw["trades"]:
        f = {}
        day, d = t["day"], int(t["dir"])
        i = int(np.searchsorted(nq_t, int(t["signal_t"])))          # trigger bar
        ie = min(i + 1, len(nq_t) - 1)                                 # entry bar (next bar open)
        if nq_t[i] != int(t["signal_t"]):
            continue
        ds = first_day.get(day, i)
        # ---- regime from completed sessions (strictly before the trade day)
        k = sday_pos.get(day)
        prev = scloses[:k] if k is not None else scloses[:0]
        f["er10"], f["er20"], f["er5"] = er(prev, 10), er(prev, 20), er(prev, 5)
        f["er10_live"] = (t.get("f") or {}).get("rg_er10")
        adr20 = float(np.mean(rng[max(0, k - 20):k])) if k and k >= 5 else None
        f["adr20"] = adr20
        # ---- entry-day shape known at the entry bar: only CLOSED bars (up to the trigger bar i); the entry is the open of bar i+1
        rth0 = next((j for j in range(ds, i + 1) if 570 <= int(nq.mod[j]) < 1080), None)
        day_hi, day_lo = float(nq.h[ds:i + 1].max()), float(nq.l[ds:i + 1].min())
        f["range_so_far_adr"] = (day_hi - day_lo) / adr20 if adr20 else None
        if rth0 is not None and adr20:
            or_end = min(rth0 + 6, i + 1)                             # 09:30-10:00 (6 bars), or what exists at entry
            f["or_adr"] = (float(nq.h[rth0:or_end].max()) - float(nq.l[rth0:or_end].min())) / adr20
            f["or_complete"] = int(i + 1 >= rth0 + 6)
            orh, orl = float(nq.h[rth0:or_end].max()), float(nq.l[rth0:or_end].min())
            px = float(nq.o[ie])
            f["vs_or"] = "above" if px > orh else ("below" if px < orl else "inside")
            f["or_pos"] = ("with" if (px > orh and d == 1) or (px < orl and d == -1) else "against") if f["vs_or"] != "inside" else "inside"
            rth_range = float(nq.h[rth0:i + 1].max()) - float(nq.l[rth0:i + 1].min())
            f["rth_range_adr"] = rth_range / adr20
            cl = nq.c[rth0:i + 1]
            path = float(np.abs(np.diff(cl)).sum()) if len(cl) > 1 else 0.0
            f["day_er_rth"] = abs(float(cl[-1] - cl[0])) / path if path else None
            f["rth_dir"] = (1 if cl[-1] > cl[0] else -1) if len(cl) > 1 else 0
            f["with_rth"] = int(f["rth_dir"] == d)
        f["gap_adr"] = (t.get("f") or {}).get("rg_gap_adr")
        f["x_with_day"] = (t.get("f") or {}).get("x_with_day")   # engine flag: close at trigger vs the 18:00 ET open, with the trade
        f["day_er"] = (t.get("f") or {}).get("rg_day_er")
        # ---- VIX / VXN / GEX (prior to the trade day)
        v, kv = prior_value(vd, vc, day)
        f["vix"] = v
        f["vix_chg"] = (v - vc[kv - 1]) if kv and kv >= 1 else None
        f["vix_chg_pct"] = 100 * (v / vc[kv - 1] - 1) if kv and kv >= 1 and vc[kv - 1] else None
        x, kx = prior_value(xd, xc, day)
        f["vxn"] = x
        f["vxn_vix"] = (x / v) if x and v else None
        g, kg = prior_value(gd, gv, day)
        f["gex"] = g
        f["gex_sign"] = None if g is None else ("neg" if g < 0 else "pos")
        if kg is not None and kg >= 60:
            win = gv[max(0, kg - 251):kg + 1]
            f["gex_pct"] = 100 * float((win < g).mean())
        else:
            f["gex_pct"] = None
        f["dix"] = gdix[kg] if kg is not None else None
        # ---- ES relative strength & SMT
        f["es_ok"] = 0
        je, jd = es_idx.get(int(nq_t[i])), es_idx.get(int(nq_t[ds]))
        if je is not None and jd is not None and day >= ES_START:
            f["es_ok"] = 1
            def ret(a, b, arr_nq, arr_es):
                return 100 * (float(arr_nq[b]) / float(arr_nq[a]) - 1), 100 * (float(arr_es[b]) / float(arr_es[a]) - 1)
            # (a) session so far: 18:00 ET open -> trigger close
            n_, e_ = 100 * (float(nq.c[i]) / float(nq.o[ds]) - 1), 100 * (float(es.c[je]) / float(es.o[jd]) - 1)
            f["rs_session"] = (n_ - e_) * d
            # (b) last hour (12 bars)
            a = max(ds, i - 12); ja = es_idx.get(int(nq_t[a]))
            if ja is not None:
                n_, e_ = 100 * (float(nq.c[i]) / float(nq.c[a]) - 1), 100 * (float(es.c[je]) / float(es.c[ja]) - 1)
                f["rs_1h"] = (n_ - e_) * d
            # sweep bar: the bar that printed the sweep extreme, searched back from the trigger within the day (>= 08:00 ET)
            ext = float(t["sweep_ext"]); sw = None
            for j in range(i, ds - 1, -1):
                if (d == 1 and abs(float(nq.l[j]) - ext) < 1e-6) or (d == -1 and abs(float(nq.h[j]) - ext) < 1e-6):
                    sw = j; break
            if sw is not None:
                js = es_idx.get(int(nq_t[sw]))
                if js is not None:
                    # (c) reclaim leg: sweep extreme bar -> trigger close, NQ vs ES, in the trade direction
                    n_, e_ = 100 * (float(nq.c[i]) / float(nq.c[sw]) - 1), 100 * (float(es.c[je]) / float(es.c[js]) - 1)
                    f["rs_reclaim"] = (n_ - e_) * d
                    # how far did each market run past its own 36-bar reference during the sweep (depth, in % of price)
                    for W, nm in ((36, "smt36"), (78, "smt78")):
                        a0 = max(ds - W, 0); a0 = max(0, sw - W); ja0 = es_idx.get(int(nq_t[a0]))
                        if ja0 is None or js <= ja0:
                            continue
                        if d == 1:
                            es_swept = float(es.l[js:je + 1].min()) <= float(es.l[ja0:js].min())
                        else:
                            es_swept = float(es.h[js:je + 1].max()) >= float(es.h[ja0:js].max())
                        f[nm] = int(not es_swept)      # 1 = SMT divergence (ES did not sweep), 0 = both swept
            f["smt_engine"] = int("SMT divergence" in (t.get("conf_tags") or []))
        F[int(t["entry_t"])] = f
    return F


# ------------------------------------------------------------------------------------------------ tables
PERIODS = (("2026", "2026-01-01", "2026-12-31"), ("2021-25", "2021-01-01", "2025-12-31"))
ES_PERIODS = (("2026", "2026-01-01", "2026-12-31"), ("2025 Apr-Dec", ES_START, "2025-12-31"))


def bucket_stats(T, key):
    """Rows per bucket per period: n, win %, avg R, sum R, net $, PF, and a t-stat of avg R vs the rest of the period."""
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for t in T:
        b = key(t)
        if b is None:
            continue
        by[b]["all"].append(t)
    rows = []
    periods = PERIODS
    labels = sorted(by.keys(), key=lambda s: (str(type(s)), s))
    for lab in labels:
        row = {"bucket": str(lab)}
        for pn, a, z in periods:
            grp = [t for t in by[lab]["all"] if a <= t["day"] <= z]
            rest = [t for t in T if a <= t["day"] <= z and key(t) is not None and key(t) != lab]
            row[pn] = _agg(grp, rest)
        rows.append(row)
    return rows


def _agg(grp, rest=None):
    if not grp:
        return {"n": 0}
    r = np.array([t["r"] for t in grp]); p = np.array([t["pnl"] for t in grp])
    gl = -p[p < 0].sum()
    out = {"n": len(grp), "win": round(100 * float((r > 0).mean()), 1), "avg_r": round(float(r.mean()), 3), "sum_r": round(float(r.sum()), 1),
           "net": round(float(p.sum())), "pf": (round(float(p[p > 0].sum() / gl), 2) if gl > 0 else None),
           "avg_pnl": round(float(p.mean()))}
    if rest:
        r2 = np.array([t["r"] for t in rest])
        se = np.sqrt(r.var(ddof=1) / len(r) + r2.var(ddof=1) / len(r2)) if len(r) > 1 and len(r2) > 1 else 0
        out["t"] = round(float((r.mean() - r2.mean()) / se), 2) if se else None
    return out


def md_table(rows, periods=PERIODS, title=""):
    cols = [p[0] for p in periods]
    head = "| bucket | " + " | ".join(f"{c}: n | win% | avg R | net $ | PF | t" for c in cols) + " |"
    sep = "|---|" + "|".join("---:|---:|---:|---:|---:|---:" for _ in cols) + "|"
    lines = [f"**{title}**", "", head, sep]
    for r in rows:
        cells = []
        for c in cols:
            s = r.get(c, {"n": 0})
            if not s.get("n"):
                cells.append("0 | | | | | ")
            else:
                cells.append(f"{s['n']} | {s['win']} | {s['avg_r']:+.2f} | {s['net']:+,} | {s['pf'] if s['pf'] is not None else 'inf'} | {s.get('t') if s.get('t') is not None else ''}")
        lines.append(f"| {r['bucket']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def qcut(v, edges, labels):
    if v is None or v != v:
        return None
    for e, lab in zip(edges, labels):
        if v < e:
            return lab
    return labels[-1]


def make_tables(T, F):
    """All factor tables as {name: {"title", "rows", "periods"}}; T = sized trades with F attached as t["xm"]."""
    tabs = collections.OrderedDict()

    def add(name, title, key, periods=PERIODS, note=""):
        TT = [t for t in T if key(t) is not None]
        rows = []
        by = collections.defaultdict(list)
        for t in TT:
            by[key(t)].append(t)
        for lab in sorted(by, key=lambda s: _order(s)):
            row = {"bucket": str(lab)}
            for pn, a, z in periods:
                grp = [t for t in by[lab] if a <= t["day"] <= z]
                rest = [t for t in TT if a <= t["day"] <= z and key(t) != lab]
                row[pn] = _agg(grp, rest)
            rows.append(row)
        tabs[name] = {"title": title, "rows": rows, "periods": [p[0] for p in periods], "note": note}

    g = lambda t, k: t["xm"].get(k)
    # 1. relative strength
    rs_lab = ["NQ lags (RS < -0.3%)", "flat (-0.3..+0.3%)", "NQ leads (> +0.3%)"]
    add("rs_session", "NQ vs ES since 18:00 ET, signed by trade direction (ES data from 2025-04)",
        lambda t: qcut(g(t, "rs_session"), [-0.3, 0.3], rs_lab), ES_PERIODS)
    rs1 = ["NQ lags (< -0.1%)", "flat", "NQ leads (> +0.1%)"]
    add("rs_1h", "NQ vs ES over the last hour, signed by trade direction", lambda t: qcut(g(t, "rs_1h"), [-0.1, 0.1], rs1), ES_PERIODS)
    add("rs_reclaim", "NQ vs ES on the reclaim leg (sweep extreme -> trigger), signed by trade direction",
        lambda t: qcut(g(t, "rs_reclaim"), [-0.1, 0.1], ["NQ reclaims less", "same", "NQ reclaims more"]), ES_PERIODS)
    add("rs_session_sign", "NQ vs ES since 18:00 ET: just the sign", lambda t: None if g(t, "rs_session") is None else ("NQ leads" if g(t, "rs_session") > 0 else "NQ lags"), ES_PERIODS)
    # 2. SMT
    add("smt_engine", "SMT divergence at the sweep, the engine's tag (ES kept its prior 3-hour extreme while NQ swept)",
        lambda t: None if g(t, "smt_engine") is None else ("SMT (ES did not sweep)" if g(t, "smt_engine") else "both swept"), ES_PERIODS)
    add("smt36", "SMT replica, 3-hour window (research)", lambda t: None if g(t, "smt36") is None else ("SMT" if g(t, "smt36") else "both swept"), ES_PERIODS)
    add("smt78", "SMT replica, full-session window (6.5 hours)", lambda t: None if g(t, "smt78") is None else ("SMT" if g(t, "smt78") else "both swept"), ES_PERIODS)
    # 3. VIX
    add("vix_level", "VIX prior close", lambda t: qcut(g(t, "vix"), [15, 20, 25], ["< 15", "15-20", "20-25", "25+"]))
    add("vix_chg", "VIX 1-day change (prior close vs the close before)", lambda t: qcut(g(t, "vix_chg_pct"), [-5, 5], ["down > 5%", "flat (+-5%)", "up > 5%"]))
    add("vix_chg10", "VIX 1-day change, big moves", lambda t: qcut(g(t, "vix_chg_pct"), [-10, 10], ["down > 10%", "within 10%", "up > 10%"]))
    add("vix_level_chg", "VIX level x direction", lambda t: None if g(t, "vix") is None or g(t, "vix_chg_pct") is None else
        f"{'VIX 20+' if g(t, 'vix') >= 20 else 'VIX < 20'}, {'rising' if g(t, 'vix_chg_pct') > 0 else 'falling'}")
    # 4. VXN / VIX
    add("vxn_vix", "VXN / VIX ratio, prior closes", lambda t: qcut(g(t, "vxn_vix"), [1.15, 1.25, 1.35], ["< 1.15", "1.15-1.25", "1.25-1.35", "1.35+"]))
    add("vxn_level", "VXN prior close", lambda t: qcut(g(t, "vxn"), [18, 22, 28], ["< 18", "18-22", "22-28", "28+"]))
    # 5. GEX
    add("gex_sign", "Dealer gamma (SPX GEX) prior day: sign", lambda t: g(t, "gex_sign"))
    add("gex_pct", "Dealer gamma prior day: 1-year percentile", lambda t: qcut(g(t, "gex_pct"), [25, 50, 75], ["0-25 (low)", "25-50", "50-75", "75-100 (high)"]))
    add("dix", "DIX (dark-pool buying) prior day", lambda t: qcut(g(t, "dix"), [0.40, 0.43, 0.46], ["< 0.40", "0.40-0.43", "0.43-0.46", "0.46+"]))
    add("gex_sign_dir", "Gamma sign x trade direction", lambda t: None if g(t, "gex_sign") is None else f"{g(t, 'gex_sign')} gamma, {'long' if t['dir'] == 1 else 'short'}")
    # 6. efficiency lookbacks
    add("er10", "10-day efficiency (live test: > 0.45 = trending day, half size, BE at 3R)", lambda t: qcut(g(t, "er10"), [0.25, 0.45], ["<= 0.25 rotational", "0.25-0.45", "> 0.45 trending"]))
    add("er20", "20-day efficiency, same cut points", lambda t: qcut(g(t, "er20"), [0.25, 0.45], ["<= 0.25 rotational", "0.25-0.45", "> 0.45 trending"]))
    add("er20_q", "20-day efficiency, 0.35 cut (about the same share of days as 0.45 on 10 days)", lambda t: qcut(g(t, "er20"), [0.2, 0.35], ["<= 0.20", "0.20-0.35", "> 0.35"]))
    add("er5", "5-day efficiency", lambda t: qcut(g(t, "er5"), [0.3, 0.6], ["<= 0.30", "0.30-0.60", "> 0.60"]))
    add("er10x20", "10-day vs 20-day trending disagreement", lambda t: None if g(t, "er10") is None or g(t, "er20") is None else
        f"er10 {'trend' if g(t, 'er10') > 0.45 else 'rot'} / er20 {'trend' if g(t, 'er20') > 0.35 else 'rot'}")
    # 7. entry-day shape
    add("gap_adr", "Opening gap vs ADR20 (engine field)", lambda t: qcut(g(t, "gap_adr"), [0.15, 0.35], ["small gap (< 0.15 ADR)", "0.15-0.35", "big gap (> 0.35 ADR)"]))
    add("or_adr", "Opening range (09:30-10:00) vs ADR20", lambda t: qcut(g(t, "or_adr"), [0.2, 0.35], ["narrow OR (< 0.2 ADR)", "0.2-0.35", "wide OR (> 0.35 ADR)"]))
    add("range_so_far", "Day range so far at entry vs ADR20", lambda t: qcut(g(t, "range_so_far_adr"), [0.6, 0.9, 1.2], ["< 0.6 ADR", "0.6-0.9", "0.9-1.2", "> 1.2 (range already done)"]))
    add("vs_or", "Entry price vs the opening range", lambda t: g(t, "or_pos"))
    add("day_er", "Today's directional efficiency so far at entry (engine rg_day_er)", lambda t: qcut(g(t, "day_er"), [0.2, 0.35, 0.55], ["< 0.20 choppy", "0.20-0.35", "0.35-0.55 trend day", "> 0.55 strong trend"]))
    add("with_day18", "Trade direction vs the move since the 18:00 ET open (engine flag x_with_day)", lambda t: None if g(t, "x_with_day") is None else ("with the day" if g(t, "x_with_day") else "against the day"))
    add("with_rth_pm", "Trade direction vs the RTH direction so far, by killzone", lambda t: None if g(t, "with_rth") is None else f"{'PM' if (t.get('f') or {}).get('pm') else 'AM'} {'with' if g(t, 'with_rth') else 'against'}")
    add("with_rth_er", "With/against the RTH direction x how directional the day is so far", lambda t: None if g(t, "with_rth") is None or g(t, "day_er") is None else f"{'with' if g(t, 'with_rth') else 'against'}, day_er {'>= 0.35' if g(t, 'day_er') >= 0.35 else '< 0.35'}")
    add("with_rth", "Trade direction vs the RTH direction so far", lambda t: None if g(t, "with_rth") is None else ("with the day" if g(t, "with_rth") else "against the day"))
    add("trend_class", "Trend-day vs range-day class at entry (day_er >= 0.35 AND range so far >= 0.8 ADR = trend day)",
        lambda t: None if g(t, "day_er") is None or g(t, "range_so_far_adr") is None else
        ("trend day" if g(t, "day_er") >= 0.35 and g(t, "range_so_far_adr") >= 0.8 else ("range day" if g(t, "range_so_far_adr") < 0.8 else "wide chop")))
    add("session", "Killzone", lambda t: "PM" if (t.get("f") or {}).get("pm") else "AM")
    return tabs


def _order(s):
    s = str(s)
    for k, pre in enumerate(["<", "NQ lags", "NQ reclaims less", "down", "small", "narrow", "0-25", "<=", "SMT", "neg", "AM", "with", "trend day",
                             "er10 rot / er20 rot", "er10 rot / er20 trend", "er10 trend / er20 rot", "er10 trend / er20 trend"]):
        if s.startswith(pre):
            return (k, s)
    return (50, s)


# ------------------------------------------------------------------------------------------------ rules
def _attach(T, F):
    for t in T:
        t["xm"] = F.get(int(t["entry_t"]), {})
    return T


def baseline():
    raw = rl.replay(quiet=True)
    F = build_features(raw)
    T = _attach(rl.size(raw), F)
    S = rl.score(T, raw)
    return raw, F, T, S


def run_rule(raw, F, id, title, question, rule, sizing, status_hint=None, notes="", tags=None, info=False):
    T = rl.size(raw, rule=lambda t, ctx: rule(F.get(int(t["entry_t"]), {}), t, ctx))
    S = rl.score(T, raw)
    B = rl.load("baseline")
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    A, Bb = B["spans"]["2026"], B["spans"]["2021-25"]
    better26 = a["net"] > A["net"] and (a["pf"] or 0) >= (A["pf"] or 0)
    better25 = b["net"] > Bb["net"] and (b["pf"] or 0) >= (Bb["pf"] or 0)
    if info:
        status = "info"
    elif min(a["tpw"], b["tpw"]) < 2.0:
        status = "rejected"
    elif better26 and better25:
        status = "adopt-candidate"
    elif (better26 and b["net"] >= Bb["net"] - 300) or (better25 and a["net"] >= A["net"] - 300):
        status = "promising"
    else:
        status = "rejected"
    status = status_hint or status
    head = {"adopt-candidate": "Better in both periods", "promising": "Helps one period without hurting the other",
            "rejected": "Not better in both periods", "info": "For information (ES data covers 2025-04 onward only)"}[status]
    m = lambda v: f"{v:+,}$"
    verdict = (f"{head}. 2026 {m(a['net'])} (lock {m(A['net'])}), PF {a['pf']} ({A['pf']}), max DD {m(a['dd'])} ({m(A['dd'])}), evals passed/failed "
               f"within 1 month {a['p20']}/{a['f20']}% ({A['p20']}/{A['f20']}). 2021-25 {m(b['net'])} ({m(Bb['net'])}), PF {b['pf']} ({Bb['pf']}), "
               f"max DD {m(b['dd'])} ({m(Bb['dd'])}), evals {b['p20']}/{b['f20']}% ({Bb['p20']}/{Bb['f20']}).")
    rl.save(id, title, "filters", question, params={}, sizing=sizing, trades=T, scored=S, status=status, verdict=verdict, notes=notes,
            writeup=WRITEUP, tags=["xm", "context"] + (tags or []))
    print(f"{id:34s} {status:16s} 2026 {a['net']:+7,} PF {a['pf']}  | 2021-25 {b['net']:+7,} PF {b['pf']} DD {b['dd']:+,} | tpw {a['tpw']}/{b['tpw']}", flush=True)
    return S, status


RULES = {
    # (title, question, rule(f, t, ctx) -> mult, sizing dict, info?)
    "xm_vixup5_half": ("Half size when VIX rose more than 5% the day before",
                       "VIX jumped more than 5% into the trade day: does sizing down help in both periods?",
                       lambda f, t, c: 0.5 if (f.get("vix_chg_pct") or 0) > 5 else 1.0,
                       {"rule": "x0.5 when the prior VIX close is > 5% above the close before", "source": "data/VIX_1d.csv"}, False),
    "xm_vixup5_x125": ("125% size when VIX rose more than 5% the day before",
                       "The opposite lean: lean in after a VIX jump?",
                       lambda f, t, c: 1.25 if (f.get("vix_chg_pct") or 0) > 5 else 1.0,
                       {"rule": "x1.25 when the prior VIX close is > 5% above the close before"}, False),
    "xm_vix20_half": ("Half size when VIX is 20+ (prior close), on the locked rules",
                      "Re-test of the earlier 'promising' VIX 20 rule on top of the 2026-10-17 lock (quarter cold, half late, BE 3R).",
                      lambda f, t, c: 0.5 if (f.get("vix") or 0) >= 20 else 1.0,
                      {"rule": "x0.5 when VIX prior close >= 20"}, False),
    "xm_vxnvix_hi_half": ("Half size when VXN/VIX is 1.35+ (Nasdaq fear premium)",
                          "When Nasdaq vol is unusually high relative to SPX vol, does the setup do worse?",
                          lambda f, t, c: 0.5 if (f.get("vxn_vix") or 0) >= 1.35 else 1.0,
                          {"rule": "x0.5 when VXN/VIX (prior closes) >= 1.35"}, False),
    "xm_vxnvix_lo_half": ("Half size when VXN/VIX is below 1.15",
                          "When Nasdaq vol is cheap relative to SPX vol?",
                          lambda f, t, c: 0.5 if f.get("vxn_vix") is not None and f["vxn_vix"] < 1.15 else 1.0,
                          {"rule": "x0.5 when VXN/VIX (prior closes) < 1.15"}, False),
    "xm_gexneg_half": ("Half size when dealer gamma was negative the day before",
                       "Negative GEX days (dealers chase moves): are sweeps-and-reverse trades worse?",
                       lambda f, t, c: 0.5 if f.get("gex_sign") == "neg" else 1.0,
                       {"rule": "x0.5 when the prior day's SPX GEX < 0", "source": "data/GEX_1d.csv"}, False),
    "xm_gexneg_x125": ("125% size when dealer gamma was negative the day before",
                       "The opposite lean on negative gamma.",
                       lambda f, t, c: 1.25 if f.get("gex_sign") == "neg" else 1.0,
                       {"rule": "x1.25 when the prior day's SPX GEX < 0"}, False),
    "xm_gexlow_half": ("Half size when dealer gamma is in its bottom quartile (1-year)",
                       "Low-gamma regime (percentile < 25): size down?",
                       lambda f, t, c: 0.5 if f.get("gex_pct") is not None and f["gex_pct"] < 25 else 1.0,
                       {"rule": "x0.5 when GEX 1-year percentile < 25"}, False),
    "xm_er20_trend_half": ("Half size when the 20-day efficiency is above 0.35 (on top of the live 10-day rule)",
                           "Does a longer trend lookback split trades better than the live 10-day test?",
                           lambda f, t, c: 0.5 if (f.get("er20") or 0) > 0.35 else 1.0,
                           {"rule": "x0.5 when 20-day efficiency > 0.35 (the live 10-day half stays)"}, False),
    "xm_er20_only": ("Swap the trending-day half size from 10-day to 20-day efficiency (size only)",
                     "What if the half-size trending test used 20 days (> 0.35) instead of 10 days (> 0.45)? Size swap only; the BE-at-3R exit still follows the 10-day test.",
                     lambda f, t, c: (2.0 if (f.get("er10") or 0) > 0.45 else 1.0) * (0.5 if (f.get("er20") or 0) > 0.35 else 1.0),
                     {"rule": "undo the 10-day half (x2) and apply x0.5 when 20-day efficiency > 0.35", "caveat": "approximate: rounding of the engine's half, exits unchanged"}, False),
    "xm_rangedone_half": ("Half size when the day's range at entry is already 1.2x ADR20",
                          "When the day has already travelled more than its average range before the setup, is the reversal worse?",
                          lambda f, t, c: 0.5 if (f.get("range_so_far_adr") or 0) >= 1.2 else 1.0,
                          {"rule": "x0.5 when (day high - day low at entry) >= 1.2 x ADR20"}, False),
    "xm_rangedone_x125": ("125% size when the day's range at entry is already 1.2x ADR20",
                          "The opposite lean: exhausted days reverse harder?",
                          lambda f, t, c: 1.25 if (f.get("range_so_far_adr") or 0) >= 1.2 else 1.0,
                          {"rule": "x1.25 when range so far >= 1.2 x ADR20"}, False),
    "xm_trendday_half": ("Half size on a trend day at entry (day efficiency >= 0.35 and range >= 0.8 ADR)",
                         "Trend-day vs range-day class of the entry day, known at entry: size down the trend days?",
                         lambda f, t, c: 0.5 if (f.get("day_er") or 0) >= 0.35 and (f.get("range_so_far_adr") or 0) >= 0.8 else 1.0,
                         {"rule": "x0.5 when rg_day_er >= 0.35 and range so far >= 0.8 ADR20"}, False),
    "xm_withday_x125": ("125% size when the trade goes with the RTH direction so far",
                        "Lean in when the setup points the way the day has gone since 09:30 (known at the trigger bar)?",
                        lambda f, t, c: 1.25 if f.get("with_rth") == 1 else 1.0,
                        {"rule": "x1.25 when the trade direction = sign(close at trigger - 09:30 open)"}, False),
    "xm_withday_x150": ("150% size when the trade goes with the RTH direction so far",
                        "The same lean, stronger.",
                        lambda f, t, c: 1.5 if f.get("with_rth") == 1 else 1.0,
                        {"rule": "x1.5 when with the RTH direction"}, False),
    "xm_withday_tilt": ("Tilt: 125% with the RTH direction, 75% against it",
                        "Shift risk from fades to with-day setups, same average size.",
                        lambda f, t, c: 1.25 if f.get("with_rth") == 1 else 0.75,
                        {"rule": "x1.25 with the RTH direction, x0.75 against it"}, False),
    "xm_against_day_07": ("70% size when trading against the RTH direction so far",
                          "A gentler size-down on fades.",
                          lambda f, t, c: 0.7 if f.get("with_rth") == 0 else 1.0,
                          {"rule": "x0.7 when against the RTH open -> trigger direction"}, False),
    "xm_withday18_x125": ("125% size when with the move since 18:00 ET (engine flag x_with_day)",
                          "Same idea with the engine's own flag (overnight session included).",
                          lambda f, t, c: 1.25 if f.get("x_with_day") == 1 else 1.0,
                          {"rule": "x1.25 when engine x_with_day = 1"}, False),
    "xm_against_day_half": ("Half size when trading against the RTH direction so far",
                            "Fading the day's direction: worse?",
                            lambda f, t, c: 0.5 if f.get("with_rth") == 0 else 1.0,
                            {"rule": "x0.5 when the trade goes against the RTH open -> entry direction"}, False),
    "xm_wideor_half": ("Half size when the opening range (09:30-10:00) is wider than 0.35 ADR20",
                       "Wide opening range = trend/volatile day: size down?",
                       lambda f, t, c: 0.5 if (f.get("or_adr") or 0) > 0.35 else 1.0,
                       {"rule": "x0.5 when the 09:30-10:00 range > 0.35 x ADR20"}, False),
    "xm_all_x125": ("CONTROL: 125% size on every trade",
                    "The fair benchmark for every lean-in rule: a positive strategy x1.25 makes more money in both periods by construction. A lean-in only counts if it beats this on PF and drawdown.",
                    lambda f, t, c: 1.25,
                    {"rule": "x1.25 on every trade (control)"}, False),
    "xm_er20_45_half": ("Half size when the 20-day efficiency is above 0.45 (the live cut, 20 days instead of 10)",
                        "The 20-day trending bucket (> 0.45) lost money in both periods; size it down on top of the live 10-day rule.",
                        lambda f, t, c: 0.5 if (f.get("er20") or 0) > 0.45 else 1.0,
                        {"rule": "x0.5 when 20-day efficiency > 0.45 (the live 10-day half stays)"}, False),
    "xm_both_trend_half": ("Half size when BOTH the 10-day (> 0.45) and the 20-day (> 0.35) efficiency say trending",
                           "The trend that has run for a month: the only efficiency bucket that lost money in both periods.",
                           lambda f, t, c: 0.5 if (f.get("er10") or 0) > 0.45 and (f.get("er20") or 0) > 0.35 else 1.0,
                           {"rule": "x0.5 when er10 > 0.45 and er20 > 0.35 (on top of the live half on er10)"}, False),
    "xm_both_trend_quarter": ("Quarter size when both the 10-day and the 20-day efficiency say trending",
                              "Same bucket, stronger size-down.",
                              lambda f, t, c: 0.25 if (f.get("er10") or 0) > 0.45 and (f.get("er20") or 0) > 0.35 else 1.0,
                              {"rule": "x0.25 when er10 > 0.45 and er20 > 0.35"}, False),
    "xm_er20_swap_45": ("Swap the trending-day half size from 10-day > 0.45 to 20-day > 0.45 (size only)",
                        "The same swap as xm_er20_only with the live 0.45 cut on 20 days (fewer trending days).",
                        lambda f, t, c: (2.0 if (f.get("er10") or 0) > 0.45 else 1.0) * (0.5 if (f.get("er20") or 0) > 0.45 else 1.0),
                        {"rule": "undo the 10-day half (x2), apply x0.5 when 20-day efficiency > 0.45", "caveat": "approximate: rounding of the engine's half, exits unchanged"}, False),
    "xm_smallgap_half": ("Half size when the opening gap is under 0.15 ADR20",
                         "Small-gap days were the weakest gap bucket in both periods.",
                         lambda f, t, c: 0.5 if f.get("gap_adr") is not None and f["gap_adr"] < 0.15 else 1.0,
                         {"rule": "x0.5 when |09:30 open - prior RTH close| < 0.15 x ADR20"}, False),
    "xm_biggap_x125": ("125% size when the opening gap is over 0.35 ADR20",
                       "Big-gap days were the best gap bucket in both periods (lean-in: compare with the control).",
                       lambda f, t, c: 1.25 if (f.get("gap_adr") or 0) > 0.35 else 1.0,
                       {"rule": "x1.25 when the opening gap > 0.35 x ADR20"}, False),
    "xm_vxn_mid_half": ("Half size when VXN/VIX sits between 1.25 and 1.35",
                        "The one VXN/VIX bucket that was weak in both periods.",
                        lambda f, t, c: 0.5 if f.get("vxn_vix") is not None and 1.25 <= f["vxn_vix"] < 1.35 else 1.0,
                        {"rule": "x0.5 when 1.25 <= VXN/VIX < 1.35"}, False),
    "xm_widechop_half": ("Half size on a 'wide chop' day at entry (range so far >= 0.8 ADR but day efficiency < 0.35)",
                         "The entry-day class that lost money in 2021-25 and was the weakest in 2026.",
                         lambda f, t, c: 0.5 if (f.get("day_er") is not None and f["day_er"] < 0.35 and (f.get("range_so_far_adr") or 0) >= 0.8) else 1.0,
                         {"rule": "x0.5 when range so far >= 0.8 ADR20 and rg_day_er < 0.35"}, False),
    "xm_smt_only_x125": ("125% size on SMT divergence (engine tag), info: ES data from 2025-04",
                         "When ES did not confirm the sweep, lean in?",
                         lambda f, t, c: 1.25 if f.get("smt_engine") == 1 else 1.0,
                         {"rule": "x1.25 when the engine tagged SMT divergence", "coverage": "2025-04-14 onward"}, True),
    "xm_nolead_half": ("Half size when NQ lags ES into the setup (RS since 18:00 ET < -0.3%), info: ES data from 2025-04",
                       "When NQ is the weaker index going into the setup direction, is the trade worse?",
                       lambda f, t, c: 0.5 if f.get("rs_session") is not None and f["rs_session"] < -0.3 else 1.0,
                       {"rule": "x0.5 when (NQ% - ES%) since 18:00 ET, signed by direction, < -0.3%", "coverage": "2025-04-14 onward"}, True),
    "xm_reclaim_more_x125": ("125% size when NQ reclaims harder than ES on the sweep -> trigger leg, info",
                             "A reclaim led by NQ: better?",
                             lambda f, t, c: 1.25 if f.get("rs_reclaim") is not None and f["rs_reclaim"] > 0.1 else 1.0,
                             {"rule": "x1.25 when NQ outruns ES by > 0.1% on the reclaim leg", "coverage": "2025-04-14 onward"}, True),
}


# Lean-in rules (x1.25 / x1.5 on a group) pass the mechanical both-periods test whenever the group is net positive, because a
# positive strategy sized up makes more money by construction. They are judged against the uniform x1.25 control instead:
# the group has to be BETTER than average (PF up, drawdown not worse than the control's). Statuses set here override.
OVERRIDE = {
    "xm_withday_x125": ("rejected", "Lean-in artifact: with-day trades average +0.06R (2026) / +0.08R (2021-25), below the rest (+0.58R / -0.02R); the extra $ is just 'more size on a positive group' and does not beat the uniform x1.25 control."),
    "xm_withday_x150": ("rejected", "Same lean-in artifact as xm_withday_x125, bigger drawdown."),
    "xm_withday18_x125": ("rejected", "Same lean-in artifact with the engine's x_with_day flag."),
    "xm_rangedone_x125": ("rejected", "Lean-in on 47 trades; the bucket lost money in 2021-25 (-$950), the 2026 gain is 7 trades."),
    "xm_gexneg_x125": ("info", "Negative gamma is rare (4 trades in 2026, 83 in 2021-25); a lean-in there changes 2026 by $0 and 2021-25 by +$0.7k: no evidence either way."),
    "xm_biggap_x125": ("info", "Lean-in: judge against the uniform x1.25 control (xm_all_x125)."),
    "xm_all_x125": ("info", "Control run, not a proposal."),
    "xm_both_trend_quarter": ("promising", "Same bucket as xm_both_trend_half; $150 more over 5 years for a more extreme size step. The half version is the single candidate."),
    "xm_er20_swap_45": ("promising", "Passes the money test in both periods, but it is a size-only approximation (the engine's 10-day half is undone by x2, the BE-at-3R exit still follows the 10-day test) and 1-month eval fails in 2021-25 rise 5.2% -> 8.6% because more days trade full size. Most of the 2021-25 gain is from undoing the 10-day half (undo alone: +$21.8k); the 20-day half is what repairs 2026 (PF 3.56 -> 4.09, DD -$3.4k -> -$2.5k). Needs an engine option (regime lookback 20 days) and a live window of 30+ days before an exact replay can decide it."),
    "xm_er20_only": ("promising", "Size-only approximation of a 20-day trending test: better money and drawdown in 2021-25, same money and a hair lower PF in 2026. Needs an engine option (regime lookback 20 days, cut 0.35, BE-at-3R following the same test) and a 21-session live window before it can be adopted."),
}


def rules(raw=None, F=None, only=None):
    if raw is None:
        raw = rl.replay(quiet=True); F = build_features(raw)
    out = {}
    for id, (title, q, fn, sz, info) in RULES.items():
        if only and id not in only:
            continue
        hint, note = OVERRIDE.get(id, (None, ""))
        out[id] = run_rule(raw, F, id, title, q, fn, sz, info=info, status_hint=hint, notes=note)
    return out


# ------------------------------------------------------------------------------------------------ main
def tables():
    raw, F, T, S = baseline()
    ok = [t for t in T if t["xm"].get("er10") is not None and t["xm"].get("er10_live") is not None]
    diff = np.array([abs(t["xm"]["er10"] - t["xm"]["er10_live"]) for t in ok])
    print(f"er10 replica vs engine: n={len(ok)} median |diff|={np.median(diff):.3f}, within 0.05: {100 * (diff < 0.05).mean():.0f}%")
    es_n = sum(1 for t in T if t["xm"].get("es_ok"))
    print(f"trades with ES data: {es_n} of {len(T)}; SMT-tagged: {sum(1 for t in T if t['xm'].get('smt_engine') == 1)}")
    tabs = make_tables(T, F)
    cov = {"vix": sum(1 for t in T if t["xm"].get("vix") is not None), "vxn": sum(1 for t in T if t["xm"].get("vxn") is not None),
           "gex": sum(1 for t in T if t["xm"].get("gex") is not None), "es": es_n, "n": len(T),
           "gex_range": [str(_daily("GEX_1d.csv")["date"].iloc[0]), str(_daily("GEX_1d.csv")["date"].iloc[-1])]}
    for name, tb in tabs.items():
        per = ES_PERIODS if tb["periods"][1].startswith("2025") else PERIODS
        print("\n" + md_table(tb["rows"], per, tb["title"]))
    os.makedirs(os.path.dirname(LAB_JSON), exist_ok=True)
    with open(LAB_JSON, "w", encoding="utf-8") as fh:
        json.dump({"built": rl.dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "xm", "writeup": WRITEUP, "coverage": cov,
                   "baseline": {k: S["spans"][k] for k in ("2026", "2021-25", "all")}, "tables": tabs}, fh, indent=1)
    print("\nwrote", LAB_JSON)
    return raw, F, T, S, tabs


def noise(n26=12, n25=75, draws=3000, seed=7):
    """Chance benchmark: half size on a RANDOM group of n26 trades in 2026 and n25 in 2021-25 (the size of the both-trend
    bucket). How often is that better than the lock in both periods (net and PF), like the owner's test asks?
    Net/PF only (no eval simulation); the half is applied as the live loop would round it (floor, min 1 micro)."""
    rng = np.random.default_rng(seed)
    raw = rl.replay(quiet=True)
    T = rl.size(raw)
    def arr(a, z):
        X = [t for t in T if a <= t["day"] <= z]
        return np.array([t["pnl"] for t in X]), np.array([t["qty"] for t in X])
    out = {}
    for name, a, z, k in (("2026", "2026-01-01", "2026-12-31", n26), ("2021-25", "2021-01-01", "2025-12-31", n25)):
        p, q = arr(a, z)
        base_net, base_pf = p.sum(), p[p > 0].sum() / -p[p < 0].sum()
        wins = 0; nets = []
        for _ in range(draws):
            idx = rng.choice(len(p), k, replace=False)
            m = np.ones(len(p)); m[idx] = np.maximum(1, np.floor(q[idx] * 0.5)) / q[idx]
            pp = p * m
            net, pf = pp.sum(), pp[pp > 0].sum() / -pp[pp < 0].sum()
            wins += (net > base_net and pf >= base_pf); nets.append(net - base_net)
        out[name] = {"better_pct": round(100 * wins / draws, 1), "median_delta": round(float(np.median(nets))), "p90_delta": round(float(np.percentile(nets, 90)))}
    # both periods at once (independent draws)
    out["both_pct"] = round(out["2026"]["better_pct"] * out["2021-25"]["better_pct"] / 100, 1)
    print("noise benchmark (half size on a random group):", json.dumps(out))
    return out


def finish():
    """Append the xm_* run headlines to the lab JSON (after `rules`)."""
    lab = json.load(open(LAB_JSON, encoding="utf-8"))
    idx = json.load(open(os.path.join(rl.RUNS, "index.json"), encoding="utf-8"))["runs"]
    lab["rules"] = [{k: r.get(k) for k in ("id", "title", "status", "verdict", "sizing", "spans")} for r in idx if str(r["id"]).startswith("xm_")]
    lab["baseline"] = rl.load("baseline")["spans"]
    with open(LAB_JSON, "w", encoding="utf-8") as fh:
        json.dump(lab, fh, indent=1)
    print(f"lab json: {len(lab['tables'])} tables, {len(lab['rules'])} rules")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tables"
    if cmd in ("tables", "all"):
        raw, F, T, S, tabs = tables()
        if cmd == "all":
            rules(raw, F)
            finish()
    elif cmd == "rules":
        rules(only=sys.argv[2:] or None)
        finish()
    elif cmd == "finish":
        finish()
    elif cmd == "noise":
        noise()
