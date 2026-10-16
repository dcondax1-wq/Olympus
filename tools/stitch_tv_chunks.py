"""Stitch TradingView NQ1! 5m exports into the authoritative NQ set in data/clean/ (re-runnable as chunks arrive).

    python tools/stitch_tv_chunks.py            # rebuild data/clean/NQ_{5m,15m,1h}.csv, NQ_rolls.json, manifest, audits
    python tools/stitch_tv_chunks.py --check    # only report coverage / overlap disagreements, write nothing

Inputs (all read-only)
  data/tv_exports/NQ1_5m_*.csv       CME_MINI:NQ1! 5m (Bar Replay chunks; files without a Volume column are skipped)
  data/tv_exports/MNQ1_5m_*.csv,
  data/tv_mnq_5m_*.csv               CME_MINI:MNQ1! 5m: used only for sessions no NQ1! file covers (Aug 24 -> Oct 16)
  data/NQ_5m.yahoo_backup.csv        Yahoo NQ=F 5m: last resort per session, and a cross-check for roll gaps
  data/clean/_src/yahoo_NQZ26_1h.csv single-contract reference quotes (tools/data_audit.py fetch-refs)
  data/clean/NQ_roll_overrides.json  optional {"NQM26->NQU26": 288.0, ...} exact gaps read off TradingView contract charts

Method
  1. NQ1! chunks are de-duplicated; every overlapping bar must agree on OHLCV (disagreements are listed in the manifest;
     the copy farther from its file's last bar wins, because a Bar Replay file can end on a still-forming bar).
  2. Per trading day (18:00 ET -> 17:00 ET) one source is chosen, never a mix inside a session:
     NQ1! > MNQ1! > Yahoo, unless the higher-priority source has < 98% of the bars the best source has for that day.
  3. The exports are front-month UNADJUSTED (verified: they equal Yahoo NQ=F to the tick before and after rolls, and the
     roll jump is in the data), so rolls are located and the series is back-adjusted here: additive, anchored to the
     newest contract, every bar before a switch gets +gap. Bars after the last roll are exact exchange prices.
     Switch = first bar of the session that starts 3 trading days before the last trading day (TradingView's NQ1! rule,
     observed on the Dec-25, Mar-26, Jun-26 and Sep-26 rolls). Gap, best first: override file; simultaneous quotes of
     both contracts (Yahoo NQ=F switched mid-session in Sep 2026); single-contract reference hours (NQZ26) for weekend
     switches; the session-open jump for weekday switches (error ~ the weekday 17:00->18:00 drift, median 9 pts);
     carry model (median gap/price of the measured rolls) as the last resort.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_audit as da  # noqa: E402

PRIORITY = ["tv-NQ1!", "tv-MNQ1!", "yahoo-NQ=F"]


def _load_group(paths, label):
    frames, skipped = [], []
    for p in paths:
        head = pd.read_csv(p, nrows=0).columns
        if not any(c.strip().lower() == "volume" for c in head):
            skipped.append(os.path.basename(p))
            continue
        df = da.read_bars(p)
        df["file"] = os.path.basename(p)
        df["pos_from_end"] = np.arange(len(df))[::-1]
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=da.COLS + ["file", "pos_from_end", "source"]), skipped
    df = pd.concat(frames, ignore_index=True)
    df["source"] = label
    return df, skipped


def dedupe(df: pd.DataFrame):
    """One row per timestamp; list timestamps where the files disagree."""
    if df.empty:
        return df, []
    key = ["open", "high", "low", "close", "volume"]
    g = df.groupby("time")
    nuniq = g[key].nunique(dropna=False).max(axis=1)
    bad_t = nuniq[nuniq > 1].index
    dis = []
    for t in bad_t[:500]:
        rows = df[df.time == t]
        dis.append({"time": int(t), "et": str(da.et_of([t])[0]),
                    "rows": rows[["file", "open", "high", "low", "close", "volume", "pos_from_end"]].to_dict("records")})
    df = df.sort_values(["time", "pos_from_end"], ascending=[True, False]).drop_duplicates("time", keep="first")
    return df.reset_index(drop=True), dis


def choose_sessions(groups: dict) -> pd.DataFrame:
    parts = []
    for lab, df in groups.items():
        if len(df):
            parts.append(df.assign(td=da.tday_of(df.time), source=lab)[da.COLS + ["td", "source"]])
    allb = pd.concat(parts, ignore_index=True)
    counts = allb.groupby(["td", "source"]).size().unstack(fill_value=0)
    pick = {}
    for td, row in counts.iterrows():
        best = row.max()
        for lab in PRIORITY:
            if lab in row and row[lab] > 0 and row[lab] >= 0.98 * best:
                pick[td] = lab
                break
    allb["keep"] = allb.td.map(pick) == allb.source
    out = allb[allb.keep].drop(columns="keep").sort_values("time").reset_index(drop=True)
    return out, counts.assign(chosen=pd.Series(pick))


def _sessions(df):
    td = da.tday_of(df.time)
    first = df.groupby(td).time.min()
    return first.sort_index()


def detect_rolls(df: pd.DataFrame, sym="NQ"):
    """Locate TradingView's front-month switches in the unadjusted stitched series."""
    sess = _sessions(df)                       # trading day -> first bar time
    days = list(sess.index)
    start, end = dt.date.fromisoformat(days[0]), dt.date.fromisoformat(days[-1])
    rolls = []
    close_by_t = df.set_index("time").close
    open_by_t = df.set_index("time").open
    t_sorted = df.time.values
    for y, m, ltd in da.quarterly_expiries(start, end):
        ltd_s = ltd.isoformat()
        if ltd_s not in sess.index:
            continue
        i = days.index(ltd_s)
        # count back 3 full trading days before the LTD; holiday short sessions do not count (Juneteenth 2025:
        # LTD Fri Jun 20, Thu Jun 19 holiday -> switch at the Sunday Jun 15 open, as observed)
        full = [d for d in days[:i] if not da.holiday_name(d)]
        if len(full) < 4:
            continue
        sw_day = full[-3]
        sw_t = int(sess[sw_day])
        j = np.searchsorted(t_sorted, sw_t)
        prev_t = int(t_sorted[j - 1])
        jump = float(open_by_t[sw_t] - close_by_t[prev_t])
        nm = m + 3 if m < 12 else 3
        ny = y if m < 12 else y + 1
        rolls.append({"from": da.contract_code(sym, y, m), "to": da.contract_code(sym, ny, nm), "ltd": ltd_s,
                      "switch_day": sw_day, "switch_t": sw_t, "switch_et": str(da.et_of([sw_t])[0]),
                      "weekend_switch": bool(da.et_of([sw_t])[0].weekday() == 6), "open_jump": jump,
                      "source_at_switch": df.loc[df.time == sw_t, "source"].iloc[0] if "source" in df else None})
    # weekday 17:00->18:00 open drift on non-roll days = error bar of the jump method
    first = sess.values
    j = np.searchsorted(t_sorted, first)
    ok = j > 0
    drift = pd.Series(open_by_t.reindex(first[ok]).values - close_by_t.reindex(t_sorted[j[ok] - 1]).values,
                      index=first[ok])
    wk = drift[[da.et_of([t])[0].weekday() != 6 for t in drift.index]]
    wk = wk[~wk.index.isin([r["switch_t"] for r in rolls])]
    p90 = float(wk.abs().quantile(0.9)) if len(wk) else 40.0
    for r in rolls:   # sanity: the rule-based switch should carry the biggest positive weekday jump of the roll week
        ltd = pd.Timestamp(r["ltd"]).tz_localize(da.TZ)
        win = drift[(drift.index >= int((ltd - pd.Timedelta(days=8)).timestamp())) & (drift.index < int(ltd.timestamp()))]
        win = win[[da.et_of([t])[0].weekday() != 6 for t in win.index]]
        r["check"] = "ok"
        if len(win) and win.idxmax() != r["switch_t"] and win.max() > r["open_jump"] + 3 * p90:
            r["check"] = f"CHECK: bigger weekday jump {win.max():+.2f} at {da.et_of([win.idxmax()])[0]}"
    return rolls, float(wk.abs().median()) if len(wk) else 10.0, float(wk.abs().quantile(0.9)) if len(wk) else 40.0


def simultaneous_gap(tv: pd.DataFrame, yahoo: pd.DataFrame, roll: dict):
    """If Yahoo NQ=F already quoted the new contract while TradingView still showed the old one, the spread is measured
    on identical timestamps (no maintenance-break drift)."""
    if yahoo is None or yahoo.empty:
        return None
    w = tv[(tv.time < roll["switch_t"]) & (tv.time >= roll["switch_t"] - 3 * 86400)]
    m = w.merge(yahoo, on="time", suffixes=("", "_y"))
    d = m.close_y - m.close
    j = roll["open_jump"]
    if abs(j) < 50:
        return None
    sel = d[(np.sign(d) == np.sign(j)) & (d.abs() > 0.5 * abs(j)) & (d.abs() < 1.5 * abs(j))]
    if len(sel) < 6:
        return None
    last = sel.iloc[-12:]
    return float(last.median()), float((last - last.median()).abs().median() * 1.4826 / np.sqrt(len(last)) + 0.25), int(len(sel))


def estimate_gaps(df, rolls, drift_p50, drift_p90, yahoo=None, overrides=None):
    overrides = overrides or {}
    for r in rolls:
        r["candidates"] = {}
        sim = simultaneous_gap(df, yahoo, r)
        if sim:
            r["candidates"]["simultaneous_yahoo"] = {"gap": sim[0], "unc": round(sim[1], 2), "n": sim[2]}
        rp = da.ref_path("NQ", "NQZ26")
        if rp and r["from"] != "NQZ26":
            rg = da.ref_gap(df, da.read_bars(rp), r["switch_t"])
            if rg:
                r["candidates"]["ref_NQZ26_1h"] = {"gap": round(rg[0], 2), "unc": round(rg[1], 2), "n": [rg[2], rg[3]]}
        if not r["weekend_switch"]:
            r["candidates"]["open_jump"] = {"gap": r["open_jump"], "unc": round(drift_p50, 2)}
    measured = [r for r in rolls if not r["weekend_switch"] or "simultaneous_yahoo" in r["candidates"]]
    pct = []   # (switch_t, gap/price) of rolls measured directly
    for r in measured:
        c = r["candidates"].get("simultaneous_yahoo") or r["candidates"].get("open_jump")
        px = float(df.loc[df.time < r["switch_t"], "close"].iloc[-1])
        pct.append((r["switch_t"], c["gap"] / px))
    carry = float(np.median([p for _, p in pct])) if pct else None
    for r in rolls:
        px = float(df.loc[df.time < r["switch_t"], "close"].iloc[-1])
        near = sorted((p for p in pct if p[0] != r["switch_t"]), key=lambda p: abs(p[0] - r["switch_t"]))[:4]
        if near:   # carry depends on the rate level: use the 4 nearest directly measured rolls
            vals = [p for _, p in near]
            c_pct = float(np.median(vals))
            r["candidates"]["carry_model"] = {"gap": round(c_pct * px, 2),
                                              "unc": round(float(np.std(vals) * px) if len(vals) > 1 else 50, 2),
                                              "pct": round(c_pct * 100, 3)}
        key = f"{r['from']}->{r['to']}"
        if key in overrides:
            r["method"], g, u = "override (TradingView contract charts)", float(overrides[key]), 0.25
        else:
            order = ["simultaneous_yahoo", "open_jump", "ref_NQZ26_1h", "carry_model"] if not r["weekend_switch"] else \
                    ["simultaneous_yahoo", "ref_NQZ26_1h", "carry_model"]
            for k in order:
                c = r["candidates"].get(k)
                if c and (k != "ref_NQZ26_1h" or c["unc"] <= 30):
                    r["method"], g, u = k, c["gap"], c["unc"]
                    break
            else:
                r["method"], g, u = "none", 0.0, None
        r["gap"] = round(g * 4) / 4      # tick-rounded so adjusted prices stay on the 0.25 grid
        r["uncertainty"] = u
        r["price_before"] = px
    return rolls, carry


def back_adjust(df, rolls):
    out = df.copy()
    out["adj"] = 0.0
    for r in rolls:
        out.loc[out.time < r["switch_t"], "adj"] += r["gap"]
    for c in ("open", "high", "low", "close"):
        out[c] = out[c] + out["adj"]
    return out


def label_contracts(df, rolls, sym="NQ"):
    lab = np.empty(len(df), dtype=object)
    t = df.time.values
    if not rolls:
        lab[:] = "?"
        return lab
    lab[:] = rolls[-1]["to"]
    for r in reversed(rolls):
        lab[t < r["switch_t"]] = r["from"]
    return lab


def coverage_table(df):
    x = df.assign(td=da.tday_of(df.time))
    x["month"] = x.td.str[:7]
    q = da.audit_frame(df, 300, "NQ_5m")
    q["month"] = q.day.str[:7]
    g = q.groupby("month")
    cov = pd.DataFrame({"sessions": g.size(), "bars": g.bars.sum(), "missing_inside": g.missing_inside.sum(),
                        "days_with_gaps": g.status.apply(lambda s: int(s.str.contains("gaps").sum())),
                        "holiday_sessions": g.holiday.apply(lambda s: int((s != "").sum())),
                        "not_ok_days": g.status.apply(lambda s: int((s != "OK").sum()))})
    src = x.groupby("month").source.agg(lambda s: "/".join(sorted(set(s))))
    con = x.groupby("month").contract.agg(lambda s: "/".join(sorted(set(s))))
    return cov.join(src).join(con), q


def main(argv):
    check_only = "--check" in argv
    D = da.DATA
    nq1, skipped = _load_group(sorted(glob.glob(os.path.join(D, "tv_exports", "NQ1_5m_*.csv"))), "tv-NQ1!")
    mnq_paths = sorted(glob.glob(os.path.join(D, "tv_exports", "MNQ1_5m_*.csv")) + glob.glob(os.path.join(D, "tv_mnq_5m_*.csv")))
    mnq, _ = _load_group(mnq_paths, "tv-MNQ1!")
    ypath = os.path.join(D, "NQ_5m.yahoo_backup.csv")
    yahoo = da.read_bars(ypath) if os.path.exists(ypath) else pd.DataFrame(columns=da.COLS)
    nq1, dis_nq1 = dedupe(nq1)
    mnq, dis_mnq = dedupe(mnq)
    print(f"NQ1! files: {nq1.file.nunique() if len(nq1) else 0} -> {len(nq1)} unique bars; overlap disagreements: {len(dis_nq1)}; skipped (no volume): {skipped}")
    print(f"MNQ1! files: {len(mnq_paths)} -> {len(mnq)} bars; disagreements {len(dis_mnq)}; Yahoo {len(yahoo)} bars")
    stitched, counts = choose_sessions({"tv-NQ1!": nq1, "tv-MNQ1!": mnq, "yahoo-NQ=F": yahoo})
    stitched = da.sanitize(stitched, 300, "stitched NQ 5m").reset_index(drop=True)
    rolls, p50, p90 = detect_rolls(stitched)
    ov_path = os.path.join(da.CLEAN, "NQ_roll_overrides.json")
    overrides = json.load(open(ov_path)) if os.path.exists(ov_path) else {}
    rolls, carry = estimate_gaps(stitched, rolls, p50, p90, yahoo, overrides)
    stitched["contract"] = label_contracts(stitched, rolls)
    adj = back_adjust(stitched, rolls)
    cov, q5 = coverage_table(adj)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(cov.to_string())
    for r in rolls:
        print(f"roll {r['from']}->{r['to']} switch {r['switch_et']} jump {r['open_jump']:+.2f} -> gap {r['gap']:+.2f} "
              f"({r['method']}, +-{r['uncertainty']})  candidates {json.dumps(r['candidates'])}")
    if check_only:
        return
    os.makedirs(da.CLEAN, exist_ok=True)
    da.write_csv(adj, os.path.join(da.CLEAN, "NQ_5m.csv"))
    da.write_csv(da.resample(adj, 900), os.path.join(da.CLEAN, "NQ_15m.csv"))
    da.write_csv(da.resample(adj, 3600), os.path.join(da.CLEAN, "NQ_1h.csv"))
    os.makedirs(os.path.join(da.CLEAN, "raw"), exist_ok=True)
    da.write_csv(stitched, os.path.join(da.CLEAN, "raw", "NQ_5m_unadjusted.csv"), da.COLS + ["source", "contract"])
    json.dump({"sym": "NQ", "anchor": rolls[-1]["to"] if rolls else None,
               "method": "additive back-adjustment anchored to the newest contract: bars with time < switch_t get +gap "
                         "(cumulative). Unadjusted price = adjusted - sum(gaps of rolls after the bar).",
               "rolls": [{k: v for k, v in r.items()} for r in rolls], "carry_pct": carry,
               "weekday_open_drift_p50_p90": [p50, p90]},
              open(os.path.join(da.CLEAN, "NQ_rolls.json"), "w"), indent=1, default=str)
    # per-day quality for every clean file (ES / 1m are built by tools/data_audit.py)
    aud_dir = os.path.join(da.CLEAN, "audit")
    q = da.audit_dir(da.CLEAN)
    seg = adj.assign(td=da.tday_of(adj.time)).groupby("td").agg(source=("source", "first"), contract=("contract", "last"))
    q = q.merge(seg, left_on="day", right_index=True, how="left") if len(q) else q
    os.makedirs(aud_dir, exist_ok=True)
    q.to_csv(os.path.join(aud_dir, "quality_by_day.csv"), index=False)
    cov.to_csv(os.path.join(aud_dir, "coverage_by_month.csv"))
    counts.to_csv(os.path.join(aud_dir, "source_bars_by_day.csv"))
    files = {}
    for f in sorted(os.listdir(da.CLEAN)):
        if f.endswith(".csv"):
            x = pd.read_csv(os.path.join(da.CLEAN, f), usecols=["time"])
            files[f] = {"rows": int(len(x)), "from_et": str(da.et_of([x.time.min()])[0]), "to_et": str(da.et_of([x.time.max()])[0])}
    es_rolls = os.path.join(da.CLEAN, "ES_rolls.json")
    manifest = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "price_space": "back-adjusted (additive) to the current front month; bars since the last roll are exact exchange prices",
        "files": files,
        "nq_sources": {"tv-NQ1!": sorted(nq1.file.unique().tolist()) if len(nq1) else [], "skipped_no_volume": skipped,
                       "tv-MNQ1!": [os.path.basename(p) for p in mnq_paths], "yahoo-NQ=F": os.path.basename(ypath)},
        "nq_sessions_by_source": adj.assign(td=da.tday_of(adj.time)).groupby("source").td.nunique().to_dict(),
        "nq_session_source_ranges": _ranges(seg),
        "volume_units": {"tv-NQ1!": "NQ contracts", "tv-MNQ1!": "MNQ contracts (about 5x NQ counts)", "yahoo-NQ=F": "NQ contracts"},
        "overlap_disagreements": {"NQ1!": dis_nq1[:50], "NQ1!_count": len(dis_nq1), "MNQ1!_count": len(dis_mnq)},
        "nq_rolls": "NQ_rolls.json", "es_rolls": "ES_rolls.json" if os.path.exists(es_rolls) else None,
        "swap_command_powershell": "New-Item -ItemType Directory -Force data\\_pre_clean_backup | Out-Null; "
                                   "Copy-Item data\\NQ_*.csv,data\\ES_*.csv data\\_pre_clean_backup\\ -Force; "
                                   "Copy-Item data\\clean\\NQ_*.csv,data\\clean\\ES_*.csv,data\\clean\\NQ_rolls.json,"
                                   "data\\clean\\ES_rolls.json data\\ -Force",
    }
    json.dump(manifest, open(os.path.join(da.CLEAN, "manifest.json"), "w"), indent=1, default=str)
    print("wrote data/clean (NQ_5m/15m/1h, raw/NQ_5m_unadjusted.csv, NQ_rolls.json, manifest.json, audit/*)")


def _ranges(seg):
    out, cur = [], None
    for td, row in seg.iterrows():
        if cur and cur["source"] == row.source:
            cur["to"] = td
            cur["sessions"] += 1
        else:
            cur = {"source": row.source, "from": td, "to": td, "sessions": 1}
            out.append(cur)
    return out


if __name__ == "__main__":
    main(sys.argv)
