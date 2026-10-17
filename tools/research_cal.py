"""Calendar & seasonality research (study "cal", runs cal_* in research/runs/, write-up research/writeups/calendar-effects.md).

Question: does WHEN a setup happens (weekday, month, half of month, month turn, holiday weeks, OPEX / triple witching,
FOMC / CPI / NFP days and the day after, the first trade of the week, days after a long weekend, DST-change weeks,
contract-roll weeks) say anything about how it does? For every calendar factor: trades, win %, avg R, net $ in 2021-25
and in 2026 on the exact live-loop replay of the LOCKED strategy (tools/runlib.replay, live sizing applied). The
strongest, consistent factors are then tested as SIZE rules (x0.5 / x1.25) with runlib.size; a skip only as a check.

  python tools/research_cal.py tables      # every factor table (markdown) + research/lab/calendar_effects.json
  python tools/research_cal.py rules       # size rules for the strongest factors, saved as runs cal_*
  python tools/research_cal.py all

No look-ahead: every flag is known before the entry (the calendar, data/news/events.csv release dates, data/NQ_rolls.json,
and for "first trade of the week" only trades that finished before this one entered).
Calendar sources: ET dates of the replay sessions; half-day sessions and closed weekdays from the bar count of
data/NQ_5m.csv (09:30-16:00 ET has 78 five-minute bars, a 13:00 close has 42); FOMC/CPI/NFP from data/news/events.csv.
events.csv has CPI/NFP only from Oct 2023; the Nov 2021 - Sep 2023 release dates below were backfilled by the researcher
from the standard BLS schedule and are flagged as such in the tables.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

LAB_JSON = os.path.join(ROOT, "research", "lab", "calendar_effects.json")
WRITEUP = "research/writeups/calendar-effects.md"
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Backfilled BLS release dates (events.csv starts CPI/NFP in Oct 2023). Flagged "backfill" in every table that uses them.
CPI_BACKFILL = """2021-11-10 2021-12-10 2022-01-12 2022-02-10 2022-03-10 2022-04-12 2022-05-11 2022-06-10 2022-07-13 2022-08-10
2022-09-13 2022-10-13 2022-11-10 2022-12-13 2023-01-12 2023-02-14 2023-03-14 2023-04-12 2023-05-10 2023-06-13 2023-07-12
2023-08-10 2023-09-13""".split()
NFP_BACKFILL = """2021-11-05 2021-12-03 2022-01-07 2022-02-04 2022-03-04 2022-04-01 2022-05-06 2022-06-03 2022-07-08 2022-08-05
2022-09-02 2022-10-07 2022-11-04 2022-12-02 2023-01-06 2023-02-03 2023-03-10 2023-04-07 2023-05-05 2023-06-02 2023-07-07
2023-08-04 2023-09-01""".split()


# ------------------------------------------------------------------------------------------------ calendar
def third_friday(y, m):
    d = dt.date(y, m, 15)
    while d.weekday() != 4:
        d += dt.timedelta(days=1)
    return d


def nth_sunday(y, m, n):
    d = dt.date(y, m, 1)
    while d.weekday() != 6:
        d += dt.timedelta(days=1)
    return d + dt.timedelta(days=7 * (n - 1))


def rth_bar_counts():
    """{ET date: number of 5m bars between 09:30 and 16:00} from data/NQ_5m.csv (78 = full day, 42 = 13:00 close)."""
    import pandas as pd
    from zoneinfo import ZoneInfo
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"), usecols=["time"])
    t = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ZoneInfo("America/New_York"))
    mins = t.dt.hour * 60 + t.dt.minute
    rth = (mins >= 570) & (mins < 960)
    cnt = pd.Series(1, index=df.index)[rth].groupby(t.dt.date[rth]).sum()
    return {d.isoformat(): int(n) for d, n in cnt.items()}


def load_events():
    ev = collections.defaultdict(set)
    with open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            e = r["event"]
            if e.startswith("FOMC rate decision"):
                ev["fomc"].add(r["date"])
            elif e.startswith("CPI"):
                ev["cpi"].add(r["date"])
            elif e.startswith("Non-Farm"):
                ev["nfp"].add(r["date"])
            elif e.startswith("PPI"):
                ev["ppi"].add(r["date"])
    return ev


def build_calendar(sessions):
    """One dict of flags per session day (ISO date string). Everything here is known before the day starts."""
    bars = rth_bar_counts()
    ev = load_events()
    rolls = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json"), encoding="utf-8"))["rolls"]
    S = [dt.date.fromisoformat(s) for s in sessions]
    sset = set(S)
    first, last = S[0], S[-1]
    # weekday status: "full", "half" (early close) or "closed" (no RTH bars)
    status = {}
    d = first - dt.timedelta(days=10)
    while d <= last + dt.timedelta(days=10):
        if d.weekday() < 5:
            n = bars.get(d.isoformat(), 0)
            status[d] = "closed" if n == 0 else ("half" if n < 70 else "full")
        d += dt.timedelta(days=1)
    def prev_wd(d):
        d -= dt.timedelta(days=1)
        while d.weekday() >= 5:
            d -= dt.timedelta(days=1)
        return d
    def next_wd(d):
        d += dt.timedelta(days=1)
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        return d
    # sessions by ISO week and by month (positions)
    by_week = collections.defaultdict(list); by_month = collections.defaultdict(list)
    for d in S:
        by_week[d.isocalendar()[:2]].append(d); by_month[(d.year, d.month)].append(d)
    week_full = {w: sum(1 for x in ds if status.get(x) == "full") for w, ds in by_week.items()}
    # ISO week of special days
    opex_weeks, tw_weeks, dst_weeks, qend_weeks = set(), set(), set(), set()
    for y in range(first.year, last.year + 1):
        for m in range(1, 13):
            f = third_friday(y, m)
            opex_weeks.add(f.isocalendar()[:2])
            if m in (3, 6, 9, 12):
                tw_weeks.add(f.isocalendar()[:2])
        for sun in (nth_sunday(y, 3, 2), nth_sunday(y, 11, 1)):   # DST starts / ends; the Mon-Fri after it
            dst_weeks.add((sun + dt.timedelta(days=1)).isocalendar()[:2])
    for (y, m), ds in by_month.items():
        if m in (3, 6, 9, 12):
            qend_weeks.add(ds[-1].isocalendar()[:2])
    roll_spans = [(dt.date.fromisoformat(r["switch_day"]), dt.date.fromisoformat(r["ltd"])) for r in rolls]
    roll_days = {dt.date.fromisoformat(r["switch_day"]) for r in rolls}
    cpi_all = ev["cpi"] | set(CPI_BACKFILL); nfp_all = ev["nfp"] | set(NFP_BACKFILL)
    def next_session_of(days):
        """Session that follows each event date (the first session strictly after it)."""
        out = set()
        for x in days:
            xd = dt.date.fromisoformat(x)
            nx = [s for s in S if s > xd]
            if nx:
                out.add(nx[0].isoformat())
        return out
    nxt = {k: next_session_of(v) for k, v in (("fomc", ev["fomc"]), ("cpi", ev["cpi"]), ("nfp", ev["nfp"]),
                                               ("cpi_all", cpi_all), ("nfp_all", nfp_all))}
    cal = {}
    for d in S:
        s = d.isoformat(); w = d.isocalendar()[:2]
        ms = by_month[(d.year, d.month)]; pos = ms.index(d); from_end = len(ms) - 1 - pos
        tf = third_friday(d.year, d.month)
        cal[s] = {
            "dow": DOW[d.weekday()], "month": MON[d.month - 1], "quarter": f"Q{(d.month - 1) // 3 + 1}",
            "half": "1st-15th" if d.day <= 15 else "16th-end",
            "week_of_month": f"wk{min(5, (d.day - 1) // 7 + 1)}",
            "mpos": "first 2" if pos < 2 else ("last 2" if from_end < 2 else "middle"),
            "turn_of_month": from_end == 0 or pos < 3,
            "short_week": week_full.get(w, 5) < 5,
            "half_day": status.get(d) == "half",
            "pre_holiday": status.get(next_wd(d)) in ("closed", "half"),
            "post_holiday": status.get(prev_wd(d)) in ("closed", "half"),
            "long_weekend": (d - prev_wd(d)).days >= 3 or status.get(prev_wd(d)) == "closed" or (d.weekday() == 1 and status.get(prev_wd(d)) == "half"),
            "opex": d == tf, "opex_week": w in opex_weeks,
            "triple_witching": d == tf and d.month in (3, 6, 9, 12), "tw_week": w in tw_weeks,
            "fomc": s in ev["fomc"], "fomc_next": s in nxt["fomc"],
            "cpi": s in ev["cpi"], "cpi_next": s in nxt["cpi"], "cpi_bf": s in cpi_all, "cpi_bf_next": s in nxt["cpi_all"],
            "nfp": s in ev["nfp"], "nfp_next": s in nxt["nfp"], "nfp_bf": s in nfp_all, "nfp_bf_next": s in nxt["nfp_all"],
            "ppi": s in ev["ppi"],
            "dst_week": w in dst_weeks,
            "roll_week": any(a <= d <= b for a, b in roll_spans), "roll_day": d in roll_days,
            "qend_week": w in qend_weeks,
            "xmas": (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 5),
            "summer": d.month in (7, 8),
            "week": f"{w[0]}-W{w[1]:02d}",
        }
    # "long_weekend" above: Monday after a closed Friday, Tuesday after a closed/half Monday, or any gap of 3+ days
    for s, c in cal.items():
        d = dt.date.fromisoformat(s); p = prev_wd(d)
        c["long_weekend"] = (status.get(p) == "closed") or (d.weekday() == 1 and status.get(p) in ("half", "closed")) or (d.weekday() == 0 and status.get(p) in ("half", "closed"))
    return cal


def tag_trades(T, cal):
    """Add the calendar flags and the first-of-week / trade-number-in-week flags (from earlier trades only)."""
    seen = collections.Counter()
    for t in sorted(T, key=lambda x: x["entry_t"]):
        c = cal[t["day"]]
        t["cal"] = dict(c)
        k = c["week"]
        seen[k] += 1
        t["cal"]["trade_in_week"] = f"#{min(seen[k], 3)}" + ("+" if seen[k] >= 3 else "")
        t["cal"]["first_of_week"] = seen[k] == 1
        mk = t["day"][:7]
        seen[mk] += 1
        t["cal"]["first_of_month"] = seen[mk] == 1
    return T


# ------------------------------------------------------------------------------------------------ tables
def span_of(day):
    return "2026" if day >= "2026-01-01" else "2021-25"


def stats(rows):
    if not rows:
        return {"n": 0}
    r = np.array([t["r"] for t in rows]); p = np.array([t["pnl"] for t in rows])
    gl = -p[p < 0].sum()
    return {"n": len(rows), "win": round(100 * float((r > 0).mean()), 1), "avg_r": round(float(r.mean()), 3),
            "net": round(float(p.sum())), "per_trade": round(float(p.mean())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None}


def perm_p(rows, all_rows, draws=2000, seed=7):
    """Two-sided chance that a random group of the same size has an avg R at least this far from the period's average."""
    if len(rows) < 3 or len(rows) >= len(all_rows) - 2:
        return None
    rng = np.random.default_rng(seed)
    R = np.array([t["r"] for t in all_rows]); mu = R.mean(); n = len(rows)
    obs = abs(np.mean([t["r"] for t in rows]) - mu)
    sims = np.array([abs(rng.choice(R, n, replace=False).mean() - mu) for _ in range(draws)])
    return round(float((sims >= obs).mean()), 3)


def factor_table(T, key, levels=None, label=None):
    """Rows per level of a calendar flag: both periods, n / win / avg R / net / $ per trade / permutation p."""
    vals = sorted({t["cal"][key] for t in T}, key=lambda v: (levels.index(v) if levels and v in levels else 99, str(v)))
    out = {"factor": label or key, "key": key, "levels": []}
    for v in vals:
        row = {"level": str(v) if not isinstance(v, bool) else ("yes" if v else "no")}
        for sp in ("2021-25", "2026"):
            allr = [t for t in T if span_of(t["day"]) == sp]
            rows = [t for t in allr if t["cal"][key] == v]
            st = stats(rows); st["p"] = perm_p(rows, allr)
            row[sp] = st
        out["levels"].append(row)
    return out


def md_table(ft):
    lines = [f"| {ft['factor']} | 2021-25 trades | win % | avg R | net $ | $/trade | 2026 trades | win % | avg R | net $ | $/trade |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in ft["levels"]:
        cells = [row["level"]]
        for sp in ("2021-25", "2026"):
            s = row[sp]
            if not s.get("n"):
                cells += ["0", "", "", "", ""]
            else:
                cells += [str(s["n"]), f"{s['win']}%", f"{s['avg_r']:+.2f}", f"{s['net']:+,}", f"{s['per_trade']:+,}"]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


FACTORS = [
    ("dow", DOW, "Day of week"),
    ("trade_in_week", ["#1", "#2", "#3+"], "Trade number in the week"),
    ("first_of_week", [True, False], "First trade of the week"),
    ("month", MON, "Month"),
    ("quarter", ["Q1", "Q2", "Q3", "Q4"], "Quarter"),
    ("half", ["1st-15th", "16th-end"], "Half of the month"),
    ("week_of_month", ["wk1", "wk2", "wk3", "wk4", "wk5"], "Week of the month"),
    ("mpos", ["first 2", "middle", "last 2"], "Month start / end (sessions)"),
    ("turn_of_month", [True, False], "Turn of month (last session + first 3)"),
    ("first_of_month", [True, False], "First trade of the month"),
    ("short_week", [True, False], "Holiday-shortened week"),
    ("half_day", [True, False], "Half-day session (13:00 close)"),
    ("pre_holiday", [True, False], "Day before a holiday / half day"),
    ("post_holiday", [True, False], "Day after a holiday / half day"),
    ("long_weekend", [True, False], "Day after a 3-day weekend"),
    ("opex", [True, False], "OPEX (3rd Friday)"),
    ("opex_week", [True, False], "OPEX week"),
    ("triple_witching", [True, False], "Triple witching day"),
    ("tw_week", [True, False], "Triple witching week"),
    ("qend_week", [True, False], "Quarter-end week"),
    ("fomc", [True, False], "FOMC decision day"),
    ("fomc_next", [True, False], "Day after FOMC"),
    ("cpi", [True, False], "CPI day (events.csv, from Oct 2023)"),
    ("cpi_bf", [True, False], "CPI day (+ backfilled 2021-23)"),
    ("cpi_next", [True, False], "Day after CPI (events.csv)"),
    ("cpi_bf_next", [True, False], "Day after CPI (+ backfill)"),
    ("nfp", [True, False], "NFP day (events.csv, from Oct 2023)"),
    ("nfp_bf", [True, False], "NFP day (+ backfilled 2021-23)"),
    ("nfp_next", [True, False], "Day after NFP (events.csv)"),
    ("nfp_bf_next", [True, False], "Day after NFP (+ backfill)"),
    ("ppi", [True, False], "PPI day (events.csv, from Oct 2023)"),
    ("dst_week", [True, False], "DST-change week"),
    ("roll_week", [True, False], "Contract roll week"),
    ("roll_day", [True, False], "Roll switch day"),
    ("xmas", [True, False], "Dec 20 - Jan 5"),
    ("summer", [True, False], "July-August"),
]


def all_tables(T):
    return [factor_table(T, k, lv, lb) for k, lv, lb in FACTORS]


def candidates(tables, S0, min_n_old=25, min_n_new=6):
    """One level vs the period average: keeps levels with enough trades in both periods and marks whether the avg R sits
    on the same side of the period's average in BOTH periods ("consistent"). Ranked by the smaller of the two gaps."""
    mu = {"2021-25": S0["spans"]["2021-25"]["avg_r"], "2026": S0["spans"]["2026"]["avg_r"]}
    rows = []
    for ft in tables:
        for row in ft["levels"]:
            a, b = row["2021-25"], row["2026"]
            if not a.get("n") or not b.get("n") or a["n"] < min_n_old or b["n"] < min_n_new:
                continue
            ga, gb = a["avg_r"] - mu["2021-25"], b["avg_r"] - mu["2026"]
            rows.append({"factor": ft["factor"], "key": ft["key"], "level": row["level"], "n_old": a["n"], "n_new": b["n"],
                         "r_old": a["avg_r"], "r_new": b["avg_r"], "gap_old": round(ga, 3), "gap_new": round(gb, 3),
                         "net_old": a["net"], "net_new": b["net"], "p_old": a["p"], "p_new": b["p"],
                         "consistent": (ga > 0) == (gb > 0), "strength": round(min(abs(ga), abs(gb)), 3)})
    rows.sort(key=lambda c: (not c["consistent"], -c["strength"]))
    return rows


# ------------------------------------------------------------------------------------------------ size rules
def make_rule(cal, key, level, mult, week_rule=None):
    """fn(t, ctx) for runlib.size: multiplier when the trade's calendar flag equals `level` (0 = skip)."""
    def is_on(t, ctx):
        if key == "first_of_week":
            wk = cal[t["day"]]["week"]
            earlier = any(cal[x["day"]]["week"] == wk for x in ctx["finished"])
            return (not earlier) == (level is True or level == "yes")
        if key == "trade_in_week":
            wk = cal[t["day"]]["week"]
            k = 1 + sum(1 for x in ctx["finished"] if cal[x["day"]]["week"] == wk)
            lab = f"#{min(k, 3)}" + ("+" if k >= 3 else "")
            return lab == level
        v = cal[t["day"]][key]
        if isinstance(v, bool):
            return v == (level is True or level == "yes")
        return str(v) == str(level)
    def rule(t, ctx):
        return mult if is_on(t, ctx) else 1.0
    return rule


def judge(S, S0):
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]; A, B = S0["spans"]["2026"], S0["spans"]["2021-25"]
    better = lambda x, X: x["net"] > X["net"] and (x["pf"] or 0) >= (X["pf"] or 0)
    tpw_ok = 2.0 <= a["tpw"] <= 4.0 and 2.0 <= b["tpw"] <= 4.0
    if better(a, A) and better(b, B) and tpw_ok:
        return "adopt-candidate"
    if (a["net"] > A["net"] or b["net"] > B["net"]) and tpw_ok:
        return "promising"
    return "rejected"


def delta_line(S, S0):
    out = []
    for sp in ("2026", "2021-25"):
        a, A = S["spans"][sp], S0["spans"][sp]
        out.append(f"{sp}: net {a['net']:+,} ({a['net'] - A['net']:+,} vs live), PF {a['pf']} (live {A['pf']}), DD {a['dd']:,}, "
                   f"eval 1m {a['p20']}/{a['f20']} (live {A['p20']}/{A['f20']}), tpw {a['tpw']}")
    return "; ".join(out)


def run_rules(raw, cal, S0, picks, save=True):
    """picks: [(id, title, key, level, mult, question)]. Returns {id: (S, verdict)}."""
    res = {}
    for rid, title, key, level, mult, q in picks:
        rule = make_rule(cal, key, level, mult)
        T = rl.size(raw, rule=rule)
        S = rl.score(T, raw)
        st = judge(S, S0) if mult > 0 else ("info")
        verdict = delta_line(S, S0)
        years = {y: (v["net"], v["pf"]) for y, v in S["years"].items()}
        print(f"\n== {rid}: {title}\n   {verdict}")
        print("   years:", ", ".join(f"{y} {n:+,} ({pf})" for y, (n, pf) in years.items()))
        if save:
            rl.save(rid, title, "timing", q, params={}, sizing={"rule": f"{key} == {level}: x{mult}"}, trades=T, scored=S,
                    status=st, verdict=verdict, notes="Calendar size rule on top of the live sizing (post-hoc, exact). Study cal.",
                    writeup=WRITEUP, tags=["calendar", "cal"])
        res[rid] = (S, st, years)
    return res


# ------------------------------------------------------------------------------------------------ main
def main(cmd="all"):
    raw = rl.replay()
    cal = build_calendar(raw["sessions"])
    T0 = rl.size(raw)
    S0 = rl.score(T0, raw)
    T = tag_trades([dict(t) for t in T0], cal)
    print("live:", rl.line(S0, "2026")); print("live:", rl.line(S0, "2021-25"))
    tables = all_tables(T)
    if cmd in ("tables", "all"):
        for ft in tables:
            print(f"\n### {ft['factor']}\n" + md_table(ft))
        cands = candidates(tables, S0)
        print("\n### candidates (n>=25 / n>=6; consistent = same side of the period average in both periods)")
        for c in cands:
            print(c)
        # session counts per flag (how often it happens)
        freq = {}
        for k, lv, lb in FACTORS:
            if k in ("trade_in_week", "first_of_week", "first_of_month"):
                continue
            cnt = collections.Counter(str(c[k]) for c in cal.values())
            freq[k] = dict(cnt)
        os.makedirs(os.path.dirname(LAB_JSON), exist_ok=True)
        json.dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "cal", "writeup": WRITEUP,
                   "method": "exact live-loop replay of the locked strategy, live sizing, costs included; flags known before entry",
                   "live": {sp: S0["spans"][sp] for sp in ("2026", "2021-25")}, "tables": tables, "candidates": cands,
                   "session_counts": freq},
                  open(LAB_JSON, "w", encoding="utf-8"), indent=1)
        print("wrote", LAB_JSON)
    if cmd in ("rules", "all"):
        picks = PICKS
        res = run_rules(raw, cal, S0, picks)
        summ = {rid: {"status": st, "2026": S["spans"]["2026"], "2021-25": S["spans"]["2021-25"], "years": years} for rid, (S, st, years) in res.items()}
        out = json.load(open(LAB_JSON, encoding="utf-8")) if os.path.exists(LAB_JSON) else {}
        out["rules"] = summ
        json.dump(out, open(LAB_JSON, "w", encoding="utf-8"), indent=1)
        print("\nrules added to", LAB_JSON)
    return raw, cal, T, S0, tables


# (id, title, flag, level, multiplier, question). Multiplier 0 = skip (a check only; the owner wants 2-4 trades a week).
PICKS = [
    ("cal_nfp_next_half", "Half size the day after NFP", "nfp_bf_next", True, 0.5,
     "The session after the jobs report lost in both periods (-0.42R on 31 trades, -0.55R on 3). Half size there?"),
    ("cal_nfp_next_skip", "Skip the day after NFP (check only)", "nfp_bf_next", True, 0,
     "Check: what if the day after NFP is not traded at all?"),
    ("cal_nfp_next_csv_half", "Half size the day after NFP (events.csv dates only)", "nfp_next", True, 0.5,
     "Same rule using only the release dates in data/news/events.csv (Oct 2023 on), no backfilled dates."),
    ("cal_june_half", "Half size in June", "month", "Jun", 0.5,
     "June lost in both periods (-0.21R on 53 trades, -0.25R on 7). Half size in June?"),
    ("cal_june_skip", "Skip June (check only)", "month", "Jun", 0,
     "Check: what if June is not traded at all?"),
    ("cal_summer_125", "Size x1.25 in July-August", "summer", True, 1.25,
     "July-August beat the average in both periods (+0.13R vs +0.01; +0.74R vs +0.41). More size in summer?"),
    ("cal_opex_week_125", "Size x1.25 in OPEX week", "opex_week", True, 1.25,
     "OPEX week was the best week of the month in 2021-25 (+0.17R on 158 trades). More size in OPEX week?"),
    ("cal_tom_half", "Half size at the turn of the month", "turn_of_month", True, 0.5,
     "The last session and first 3 sessions of a month sat below the average in both periods (-0.12R; +0.27R). Half size?"),
    ("cal_half_day_half", "Half size on half-day sessions", "half_day", True, 0.5,
     "Half-day sessions (13:00 close) averaged -0.37R on 21 trades in 2021-25; 1 trade in 2026. Half size?"),
    ("cal_cpi_125", "Size x1.25 on CPI day", "cpi_bf", True, 1.25,
     "CPI days averaged +0.66R on 30 trades in 2021-25 (p 0.004) but 2026 has only 2 of them. Info."),
    ("cal_dst_week_125", "Size x1.25 in DST-change weeks", "dst_week", True, 1.25,
     "The week after a clock change averaged +0.17R (29 trades) and +2.48R (2 trades). Info."),
    ("cal_first_week_half", "Half size on the first trade of the week", "first_of_week", True, 0.5,
     "The first trade of the week is a little below the average in R in both periods (213 / 40 trades). Half size?"),
    ("cal_wed_half", "Half size on Wednesdays (the trap)", "dow", "Wed", 0.5,
     "Wednesday was the best day in 2021-25 (+0.25R, p 0.015) and the worst in 2026 (-0.52R, p 0.04). What a Wednesday rule does."),
]


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
