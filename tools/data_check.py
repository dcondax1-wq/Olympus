"""Data integrity check of the futures + volatility files the backtests and the live loop read (read-only).

Per bar file (data/NQ_5m.csv, NQ_1m.csv, ES_5m.csv):
  header       time,open,high,low,close,volume
  order        timestamps strictly increasing, no duplicates, on the bar grid (t % bar == 0)
  ohlc         no NaN, prices > 0, high >= max(open, close), low <= min(open, close)
  gaps         missing bars inside the CME session (Sun-Fri 18:00-17:00 ET, the 17:00 halt and weekends skipped; days
               missing entirely are reported as whole missing sessions, holidays named as such when CME is shut)
  spikes       a bar whose range or close-to-close move exceeds 4% (NQ) / 3% (ES): a bad print or an unadjusted roll
  rolls        the close-to-close step at each back-adjusted roll in data/<SYM>_rolls.json (should look like any bar)
  freshness    the last bar's date
Cross checks: 1m vs 5m (the 1m bars resampled to 5m against the 5m file on their common days: close diff > 1 tick),
VIX / VXN daily files cover every NQ session (the LIT target needs the prior VIX close).

    python -X utf8 tools/data_check.py            # the report; exit 1 when a FIX item exists
    python -X utf8 tools/data_check.py --json out.json
engine/ops_checks.py (HEALTH_CHECK) calls summary() for its "Data files" line.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
ET = ZoneInfo("America/New_York")
OK, WARN, BAD = "ok", "warn", "fix"
FILES = [("NQ", 300), ("NQ", 60), ("ES", 300)]          # no official ES 1m file (TradingView ES1! 1m not exported yet)
SPIKE = {"NQ": 0.04, "ES": 0.03}
TICK = 0.25
GAP_WARN = {300: 6, 60: 60}   # missing bars in one session above which a session counts as gappy (1m: quiet minutes print no bar)
# real market-wide moves (not bad prints): a spike on these ET days, or at the same time on NQ and ES, is reported as real
KNOWN_MOVES = {"2025-04-06", "2025-04-07", "2025-04-09"}
KNOWN_GAPS = {"2025-11-27": "CME Globex outage (data-centre cooling), Nov 28 2025"}   # ET day the gap starts


def _name(sym, bar):
    return f"{sym}_{'5m' if bar == 300 else '1m'}.csv"


def load(sym, bar, data=DATA):
    p = os.path.join(data, _name(sym, bar))
    if not os.path.exists(p):
        return None, p
    return pd.read_csv(p), p


def _session_day(t):
    """CME trading day (18:00 ET start) of epoch seconds array -> array of date strings."""
    e = pd.to_datetime(t, unit="s", utc=True).tz_convert(ET)
    d = (e + pd.Timedelta(hours=6)).date
    return np.array([str(x) for x in d]), e


def check_bars(df, sym, bar, rolls=None, other=None):
    out = {"file": _name(sym, bar), "rows": int(len(df)), "items": []}
    add = lambda lvl, what, text: out["items"].append({"level": lvl, "what": what, "text": text})  # noqa: E731
    cols = ["time", "open", "high", "low", "close", "volume"]
    if list(df.columns[:6]) != cols:
        add(BAD, "header", f"columns {list(df.columns)} (expected {','.join(cols)})")
        return out
    t = df["time"].to_numpy(np.int64)
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    dif = np.diff(t)
    nd, nb = int((dif == 0).sum()), int((dif < 0).sum())
    add(BAD if nd or nb else OK, "order", f"{nd} duplicate, {nb} out-of-order timestamps" if nd or nb else "strictly increasing")
    off = int((t % bar != 0).sum())
    add(WARN if off else OK, "grid", f"{off} bars off the {bar // 60}m grid" if off else f"every bar on the {bar // 60}m grid")
    nan = int(df[cols[:5]].isna().any(axis=1).sum())
    bad_px = int(((o <= 0) | (h <= 0) | (l <= 0) | (c <= 0)).sum())
    bad_hl = int(((h + 1e-9 < np.maximum(o, c)) | (l - 1e-9 > np.minimum(o, c)) | (h + 1e-9 < l)).sum())
    lvl = BAD if nan or bad_px else WARN if bad_hl else OK
    add(lvl, "ohlc", f"{nan} NaN rows, {bad_px} prices <= 0, {bad_hl} bars with high/low outside open/close"
        if lvl != OK else "no NaN, prices > 0, high/low contain open/close")
    # gaps inside sessions
    day, e = _session_day(t)
    mod = (e.hour * 60 + e.minute).to_numpy()
    per = pd.Series(1, index=day).groupby(level=0).size()
    full = (23 * 60) // (bar // 60)                    # 18:00-17:00 = 23 h of bars
    per_c = per.iloc[:-1] if len(per) > 1 else per          # the last session is usually cut by the export
    short = per_c[per_c < full - GAP_WARN[bar]]
    # half days (CME early close 13:00/13:15 ET) look short too: report the count and the worst few
    worst = short.sort_values().head(5)
    days = sorted(per.index)
    span_days = pd.bdate_range(days[0], days[-1]).strftime("%Y-%m-%d") if days else []
    missing = [d for d in span_days if d not in per.index]
    holidays = {"01-01", "12-25", "07-04", "01-19", "02-16", "05-25", "09-07", "11-26", "06-19"}   # approximate CME shut / no-bar days
    miss_odd = [d for d in missing if d[5:] not in holidays]
    add(WARN if len(short) > max(12, 0.05 * len(per)) else OK, "gaps",
        f"{len(per)} sessions; {len(short)} with more than {GAP_WARN[bar]} missing bars (holiday half days count here); worst "
        + ", ".join(f"{d} {int(n)}/{full}" for d, n in worst.items()))
    add(WARN if len(miss_odd) > 12 else OK, "missing days",
        f"{len(missing)} weekdays without bars ({len(missing) - len(miss_odd)} on usual holidays)"
        + (f"; e.g. {', '.join(miss_odd[:6])}" if miss_odd else ""))
    big = np.where(dif > 3 * 3600)[0]
    # a gap that ends at the 18:00 ET open is the daily halt, an early close (holiday) or a weekend: normal
    wk = [i for i in big if not (18 * 60 <= mod[i + 1] <= 18 * 60 + 15)]
    known = [i for i in wk if f"{e[i]:%Y-%m-%d}" in KNOWN_GAPS]
    if known:
        add(OK, "known gaps", "; ".join(f"{e[i]:%Y-%m-%d %H:%M} ET {dif[i] / 3600:.1f} h: {KNOWN_GAPS[f'{e[i]:%Y-%m-%d}']}" for i in known))
    wk = [i for i in wk if i not in known]
    if wk:
        g = max(wk, key=lambda i: dif[i])
        add(WARN, "long gaps", f"{len(wk)} gaps over 3 h outside weekends / the daily halt; longest {dif[g] / 3600:.1f} h after "
            f"{e[g]:%Y-%m-%d %H:%M} ET")
    # spikes
    lim = SPIKE.get(sym, 0.04)
    rng = (h - l) / np.maximum(c, 1e-9)
    cc = np.abs(np.diff(c)) / np.maximum(c[:-1], 1e-9)
    roll_t = {int(r["switch_t"]) for r in (rolls or {}).get("rolls", []) if r.get("switch_t")}
    sp = sorted(set(np.where(rng > lim)[0].tolist()) | {i + 1 for i in np.where(cc > lim)[0].tolist()})
    real = [i for i in sp if f"{e[i]:%Y-%m-%d}" in KNOWN_MOVES or (other is not None and _moved(other, int(t[i]), lim / 2))]
    odd = [i for i in sp if i not in real]
    txt = lambda ix: ", ".join(f"{e[i]:%Y-%m-%d %H:%M}" for i in ix[:5])  # noqa: E731
    add(WARN if odd else OK, "spikes", (f"{len(odd)} bars with a range or step over {lim:.0%} on this symbol only (bad print?): {txt(odd)}"
        if odd else f"no lone bar range or step over {lim:.0%}") + (f"; {len(real)} real market-wide moves ({txt(real)})" if real else ""))
    if roll_t:
        steps = []
        for rt in sorted(roll_t):
            j = int(np.searchsorted(t, rt))
            if 0 < j < len(t):
                steps.append(abs(c[j] - c[j - 1]) / c[j - 1])
        # the roll bar is a session open (often after a weekend): compare with the other session-open gaps of the file
        opens = np.where((mod[1:] == 18 * 60) & (dif > 3600))[0]
        og = cc[opens] if len(opens) else cc
        p99 = float(np.percentile(og, 99)) if len(og) else 0.0
        mx = max(steps) if steps else 0.0
        add(WARN if steps and mx > max(0.01, 1.5 * p99) else OK, "rolls",
            f"{len(steps)} rolls inside the file; largest step at a roll {mx:.2%} (99% of session-open gaps are under {p99:.2%})")
    last = e[-1]
    age = (dt.datetime.now(ET).date() - last.date()).days
    add(WARN if age > 10 else OK, "freshness", f"last bar {last:%Y-%m-%d %H:%M} ET ({age} days ago)"
        + (" - refresh needs the owner's TradingView export (tools/grab_tv_export.py on the PC)" if age > 10 else ""))
    out["first"], out["last"] = f"{e[0]:%Y-%m-%d}", f"{last:%Y-%m-%d}"
    out["sessions"] = int(len(per))
    return out


def _moved(other, t0, lim):
    """other = (times, closes) of the other symbol: did it move more than lim within 10 minutes of t0?"""
    ot, oc = other
    j = int(np.searchsorted(ot, t0))
    a, z = max(0, j - 3), min(len(ot), j + 3)
    if z - a < 2 or abs(int(ot[min(j, len(ot) - 1)]) - t0) > 900:
        return False
    w = oc[a:z]
    return bool((w.max() - w.min()) / w.min() > lim)


def check_1m_vs_5m(d1, d5, sym):
    if d1 is None or d5 is None or not len(d1):
        return None
    g = (d1["time"] // 300) * 300
    r = d1.groupby(g).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    m = r.join(d5.set_index("time")[["close", "high", "low"]], rsuffix="_5", how="inner")
    if not len(m):
        return {"level": WARN, "what": f"{sym} 1m vs 5m", "text": "no common bars"}
    diff = (m["close"] - m["close_5"]).abs()
    bad = int((diff > TICK + 1e-9).sum())
    # a constant offset over a stretch = a roll / back-adjustment difference, not bad data
    off = diff[diff > TICK + 1e-9]
    const = bool(len(off) and (off.round(2).value_counts().iloc[0] > 0.8 * len(off)))
    lvl = OK if bad <= 0.015 * len(m) else WARN
    return {"level": lvl, "what": f"{sym} 1m vs 5m", "text": f"{len(m):,} common 5m bars; {bad:,} closes differ by more than 1 tick"
            + (" (one constant offset: a back-adjustment difference)" if const else "")}


def check_vol(sessions, data=DATA):
    rows = []
    for nm in ("VIX_1d.csv", "VXN_1d.csv"):
        p = os.path.join(data, nm)
        if not os.path.exists(p):
            rows.append({"level": BAD if nm.startswith("VIX") else WARN, "what": nm, "text": "missing"})
            continue
        v = pd.read_csv(p)
        ds = set(v["date"].astype(str))
        nan = int(v["close"].isna().sum())
        order = bool((pd.to_datetime(v["date"]).diff().dt.days.dropna() > 0).all())
        sess = [s for s in sessions if s >= min(ds)]
        # the LIT target needs the close of the day before each session
        prev_ok = 0
        sd = sorted(ds)
        for s in sess:
            i = np.searchsorted(sd, s)
            prev_ok += i > 0 and (dt.date.fromisoformat(s) - dt.date.fromisoformat(sd[i - 1])).days <= 4
        miss = len(sess) - prev_ok
        lvl = BAD if not order else WARN if (miss > 3 or nan) else OK
        rows.append({"level": lvl, "what": nm, "text": f"{len(v)} days to {max(ds)}; {'in order' if order else 'NOT in date order'}; "
                     f"{nan} NaN closes; {miss} NQ sessions without a prior close within 4 days"})
    return rows


def run(data=DATA):
    rep = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "files": [], "cross": []}
    frames, nq_sess = {}, []
    for sym, bar in FILES:
        df, p = load(sym, bar, data)
        if df is None:
            rep["files"].append({"file": _name(sym, bar), "rows": 0, "items": [{"level": BAD if sym == "NQ" else WARN, "what": "file", "text": "missing"}]})
            continue
        frames[(sym, bar)] = df
        try:
            rolls = json.load(open(os.path.join(data, f"{sym}_rolls.json"), encoding="utf-8"))
        except Exception:
            rolls = None
        oth = frames.get(("ES" if sym == "NQ" else "NQ", bar))
        if oth is None:
            o5, _ = load("ES" if sym == "NQ" else "NQ", bar, data)
            oth = o5
        r = check_bars(df, sym, bar, rolls, None if oth is None else (oth["time"].to_numpy(np.int64), oth["close"].to_numpy(float)))
        rep["files"].append(r)
        if sym == "NQ" and bar == 300 and len(df):
            nq_sess = sorted(set(_session_day(df["time"].to_numpy(np.int64))[0]))
    for sym in ("NQ", "ES"):
        x = check_1m_vs_5m(frames.get((sym, 60)), frames.get((sym, 300)), sym)
        if x:
            rep["cross"].append(x)
    rep["cross"] += check_vol(nq_sess, data)
    items = [i for f in rep["files"] for i in f["items"]] + rep["cross"]
    rep["n_fix"] = sum(1 for i in items if i["level"] == BAD)
    rep["n_warn"] = sum(1 for i in items if i["level"] == WARN)
    return rep


def summary(rep=None, data=DATA):
    """One line for HEALTH_CHECK: (level, text)."""
    rep = rep or run(data)
    nq = next((f for f in rep["files"] if f["file"] == "NQ_5m.csv"), {})
    one = next((f for f in rep["files"] if f["file"] == "NQ_1m.csv"), {})
    lvl = BAD if rep["n_fix"] else WARN if rep["n_warn"] else OK
    bad = [f"{f['file']} {i['what']}" for f in rep["files"] for i in f["items"] if i["level"] != OK] + \
          [i["what"] for i in rep["cross"] if i["level"] != OK]
    txt = (f"NQ 5m {nq.get('first', '?')} -> {nq.get('last', '?')}, 1m to {one.get('last', '?')}; "
           + (f"{rep['n_fix']} to fix, {rep['n_warn']} to look at: {', '.join(bad[:4])}" if bad else "every check clean"))
    return lvl, txt


def render(rep):
    tag = {OK: " OK ", WARN: "WARN", BAD: "FIX "}
    L = [f"Data check {rep['built']}"]
    for f in rep["files"]:
        L.append(f"\n{f['file']}  {f['rows']:,} rows" + (f", {f.get('sessions')} sessions {f.get('first')} -> {f.get('last')}" if f.get("first") else ""))
        L += [f"  [{tag[i['level']]}] {i['what']}: {i['text']}" for i in f["items"]]
    L.append("\nCross checks")
    L += [f"  [{tag[i['level']]}] {i['what']}: {i['text']}" for i in rep["cross"]]
    L.append(f"\n{rep['n_fix']} to fix, {rep['n_warn']} to look at")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--data", default=DATA)
    a = ap.parse_args(argv)
    rep = run(a.data)
    print(render(rep))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    return 1 if rep["n_fix"] else 0


if __name__ == "__main__":
    sys.exit(main())
