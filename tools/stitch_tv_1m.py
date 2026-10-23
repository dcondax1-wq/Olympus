"""Stitch TradingView NQ1! 1-minute exports into data/clean/NQ_1m_tv.csv, back-adjusted into the data/NQ_5m.csv price space.

    python tools/stitch_tv_1m.py              # build + verify; write data/clean/NQ_1m_tv.csv and research/lab/DATA_1M.md
    python tools/stitch_tv_1m.py --check      # build + verify only, write nothing
    python tools/stitch_tv_1m.py --install    # as the default, then back up data/NQ_1m.csv to
                                              # data/_pre_clean_backup/NQ_1m.<time>.csv and copy the clean file over it

Inputs (read-only)
  data/tv_exports/NQ1_1m_*.csv   CME_MINI:NQ1! 1m, ETH, front month UNADJUSTED, from the "Liquidity Engine Bot" layout:
                                 Bar Replay chunks NQ1_1m_chunk_<replay date>.csv (each ~10 sessions, the history TradingView
                                 loads before the replay point) + the regular-chart export NQ1_1m_chunk_<date>_regular.csv
  data/NQ_rolls.json             roll switch times + gaps that built data/NQ_5m.csv (tools/stitch_tv_chunks.py)
  data/NQ_5m.csv                 verification target (the same TradingView NQ1! feed at 5m)

Method
  1. De-duplicate (stitch_tv_chunks.dedupe): overlapping bars must agree on OHLCV; disagreements are counted and listed,
     the copy farther from its file's last bar wins.
  2. data_audit.sanitize(.., 60): duplicates, off-grid stamps, 17:00-18:00 ET break / weekend bars, impossible OHLC and flat
     zero-volume bars are dropped; a leading partial session is dropped.
  3. Roll check: for every NQ_rolls.json switch inside the 1m span, the 1m open jump at switch_t (first bar open minus the
     previous bar's close) must equal the 5m open_jump recorded there, i.e. TradingView switched contracts at the same bar.
  4. Back-adjust exactly like stitch_tv_chunks.back_adjust: additive, bars with time < switch_t get +gap (cumulative),
     anchored to the newest contract, so bars after the last roll are exchange prices.
  5. Verify: resample to 5m (data_audit.resample) and compare with data/NQ_5m.csv on common bars. Required: |median close
     diff| <= 0.125 and p90 |close diff| <= 0.25. Otherwise diagnostics are printed and nothing is written (exit 1).
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_audit as da  # noqa: E402
import stitch_tv_chunks as stc  # noqa: E402

D = da.DATA
EXPORTS = os.path.join(D, "tv_exports")
OUT = os.path.join(da.CLEAN, "NQ_1m_tv.csv")
LIVE = os.path.join(D, "NQ_1m.csv")
BACKUP = os.path.join(D, "_pre_clean_backup", f"NQ_1m.{dt.datetime.now():%Y%m%d_%H%M%S}.csv")
DOC = os.path.join(da.ROOT, "research", "lab", "DATA_1M.md")
ROLLS = os.path.join(D, "NQ_rolls.json")
REF5 = os.path.join(D, "NQ_5m.csv")
MED_MAX, P90_MAX = 0.125, 0.25
KEY = ["open", "high", "low", "close", "volume"]


def et(t) -> str:
    return da.et_of([int(t)])[0].strftime("%Y-%m-%d %H:%M")


def load_chunks():
    paths = sorted(glob.glob(os.path.join(EXPORTS, "NQ1_1m_*.csv")))
    if not paths:
        sys.exit("no data/tv_exports/NQ1_1m_*.csv")
    raw, skipped = stc._load_group(paths, "tv-NQ1!")
    inv = raw.groupby("file").agg(bars=("time", "size"), t0=("time", "min"), t1=("time", "max")).sort_values("t0")
    inv["from_et"] = [et(t) for t in inv.t0]
    inv["to_et"] = [et(t) for t in inv.t1]
    return raw, inv.reset_index(), skipped


def disagreements(raw: pd.DataFrame):
    """Timestamps present in >1 file whose OHLCV differ (full count + per-column counts)."""
    dup = raw[raw.duplicated("time", keep=False)]
    if dup.empty:
        return 0, 0, {}
    nun = dup.groupby("time")[KEY].nunique(dropna=False)
    bad = nun[nun.max(axis=1) > 1]
    return int(dup.time.nunique()), int(len(bad)), {c: int((bad[c] > 1).sum()) for c in KEY}


def roll_checks(df: pd.DataFrame, rolls: list) -> list:
    t = df.time.values
    out = []
    for r in rolls:
        sw = int(r["switch_t"])
        if sw <= t[0] or sw > t[-1]:
            continue
        j = int(np.searchsorted(t, sw))
        jump = float(df.open.iloc[j] - df.close.iloc[j - 1])
        out.append({"roll": f"{r['from']}->{r['to']}", "switch_et": et(sw), "bar_at_switch": bool(t[j] == sw),
                    "jump_1m": jump, "jump_5m": float(r["open_jump"]), "match": bool(abs(jump - float(r["open_jump"])) < 1e-6),
                    "gap_applied": float(r["gap"]), "gap_method": r.get("method"), "gap_unc": r.get("uncertainty")})
    return out


def verify(adj: pd.DataFrame, ref: pd.DataFrame):
    r5 = da.resample(adj.assign(n=1), 300)
    r5["n1m"] = adj.assign(b=adj.time // 300 * 300).groupby("b").size().values
    lo, hi = int(r5.time.min()), int(r5.time.max())
    ref = ref[(ref.time >= lo) & (ref.time <= hi)]
    m = r5.merge(ref, on="time", suffixes=("", "_5m"))
    d = {c: (m[c] - m[c + "_5m"]) for c in ("open", "high", "low", "close")}
    dc = d["close"]
    res = {"bars_5m_compared": int(len(m)),
           "ref_5m_bars_in_span": int(len(ref)),
           "ref_5m_bars_missing_from_1m": int((~ref.time.isin(r5.time)).sum()),
           "resampled_5m_bars_not_in_ref": int((~r5.time.isin(ref.time)).sum()),
           "close_diff_median": float(dc.median()),
           "close_absdiff_p90": float(dc.abs().quantile(0.9)),
           "close_absdiff_p99": float(dc.abs().quantile(0.99)),
           "close_absdiff_max": float(dc.abs().max()),
           "exact_match_pct": {c: round(float((d[c].abs() < 1e-9).mean() * 100), 3) for c in d},
           "volume_exact_pct": round(float((m.volume == m.volume_5m).mean() * 100), 3),
           "volume_sum_ratio_1m_over_5m": round(float(m.volume.sum() / m.volume_5m.sum()), 5)}
    m["td"] = da.tday_of(m.time)
    m["dc"] = dc
    bad = m[dc.abs() > 0.25]
    res["bars_close_off_by_more_than_0.25"] = int(len(bad))
    res["days_with_close_mismatch"] = {k: int(v) for k, v in bad.groupby("td").size().items()}
    ok = abs(res["close_diff_median"]) <= MED_MAX and res["close_absdiff_p90"] <= P90_MAX
    return ok, res, m


def diagnose(adj, ref, m):
    """Printed only when verification fails: per-day median offsets (roll gap errors show as constant offsets over a
    contract segment) and a clock-shift test (timestamp convention errors)."""
    per_day = m.groupby("td").dc.agg(["size", "median", lambda x: x.abs().max()])
    print("per-day close diff (1m->5m minus NQ_5m), days with any mismatch:")
    print(per_day[per_day.iloc[:, 2] > 0.25].to_string())
    r5 = da.resample(adj, 300)
    for sh in (-3600, -300, -60, 0, 60, 300, 3600):
        k = r5.assign(time=r5.time + sh).merge(ref, on="time", suffixes=("", "_5m"))
        print(f"  clock shift {sh:+5d}s: n={len(k)} median|dclose|={(k.close - k.close_5m).abs().median():.2f}")


def coverage(adj: pd.DataFrame):
    q = da.audit_frame(adj, 60, "NQ_1m_tv", extra_cols=("contract",))
    q["month"] = q.day.str[:7]
    g = q.groupby("month")
    cov = pd.DataFrame({"sessions": g.size(), "bars": g.bars.sum(), "missing_inside": g.missing_inside.sum(),
                        "days_with_gaps": g.status.apply(lambda s: int(s.str.contains("gaps").sum())),
                        "holiday_sessions": g.holiday.apply(lambda s: int((s != "").sum())),
                        "not_ok_days": g.status.apply(lambda s: int((s != "OK").sum())),
                        "contracts": g.contract.agg(lambda s: "/".join(sorted(set("/".join(s).split("/")))))})
    have = set(q.day)
    missing = [{"day": d.strftime("%Y-%m-%d"), "weekday": d.strftime("%a"), "holiday": da.holiday_name(d.strftime("%Y-%m-%d")) or ""}
               for d in pd.bdate_range(q.day.min(), q.day.max()) if d.strftime("%Y-%m-%d") not in have]
    return q, cov, missing


def md_table(df: pd.DataFrame, index=False) -> str:
    x = df.reset_index() if index else df
    cols = list(x.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in x.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def write_doc(adj, inv, n_overlap, n_dis, dis_cols, checks, ver, q, cov, missing, skipped, sanitized_drop):
    tds = sorted(set(q.day))
    nonok = q[q.status != "OK"][["day", "bars", "expected", "first_et", "last_et", "missing_inside", "missing_at_open",
                                 "missing_at_close", "holiday", "status"]]
    real_gaps = [m for m in missing if not m["holiday"]]
    hol_closed = [m for m in missing if m["holiday"]]
    hol_sess = q[q.holiday != ""][["day", "holiday", "bars", "expected", "first_et", "last_et", "missing_at_close"]]
    lines = [
        "# NQ 1-minute data (TradingView NQ1!, 2026)",
        "",
        f"Generated {dt.datetime.now():%Y-%m-%d %H:%M} by `python tools/stitch_tv_1m.py` (re-runnable as chunks are added).",
        "",
        "**Source:** CME_MINI:NQ1! 1-minute, ETH, exported from the user's TradingView (layout \"Liquidity Engine Bot\") via "
        "Bar Replay + Download chart data. Official CME futures data only.",
        "",
        "**Files:** `data/clean/NQ_1m_tv.csv` (authoritative) = `data/NQ_1m.csv` (installed copy). Columns `time,open,high,low,close,volume`; `time` = bar open, "
        "UNIX seconds UTC (same convention as `data/NQ_5m.csv`); volume in NQ contracts.",
        "",
        "## Coverage",
        "",
        f"- First bar {et(adj.time.min())} ET, last bar {et(adj.time.max())} ET",
        f"- Sessions (CME trading days, 18:00 ET -> 17:00 ET): **{len(tds)}**, first **{tds[0]}**, last **{tds[-1]}**",
        f"- Rows: {len(adj):,}",
        f"- Weekdays with no session: {len(missing)} "
        f"({len(hol_closed)} exchange holiday(s): {', '.join(m['day'] + ' ' + m['holiday'] for m in hol_closed) or 'none'}; "
        f"{len(real_gaps)} unexplained: {', '.join(m['day'] for m in real_gaps) or 'none'})",
        f"- Sessions not fully clean: {len(nonok)} (listed below; holiday early closes are expected)",
        "",
        md_table(cov, index=True),
        "",
        "`missing_inside` = 1-minute slots without a bar between a session's first and last bar. NQ prints every minute in "
        "practice, so a few per month are minutes with no trade; `gaps` status needs > 2% of the session missing.",
        "",
        "### Sessions with flags",
        "",
        md_table(nonok) if len(nonok) else "none",
        "",
        "### Holiday sessions (shortened by the exchange; kept, not flagged)",
        "",
        md_table(hol_sess) if len(hol_sess) else "none",
        "",
        "## Price space / rolls",
        "",
        "Back-adjusted (additive) to NQZ26 exactly like `data/NQ_5m.csv`: switch times and gaps come from `data/NQ_rolls.json`; "
        "bars before a switch get +gap (cumulative). Bars since the 2026-09-14 18:00 ET switch are exact exchange prices. "
        "Raw (unadjusted) price = adjusted - sum of the gaps of the rolls after the bar.",
        "",
        "The 1m open jump at each switch equals the 5m open_jump in NQ_rolls.json, i.e. TradingView switched contracts at the "
        "same bar on both timeframes:",
        "",
        md_table(pd.DataFrame(checks)) if checks else "no roll inside the span",
        "",
        "## Verification against data/NQ_5m.csv",
        "",
        "The 1m series resampled to 5m (`data_audit.resample`) vs the existing 5m file on the same bars "
        f"(pass: |median close diff| <= {MED_MAX}, p90 |close diff| <= {P90_MAX}).",
        "",
        "```",
        json.dumps(ver, indent=1),
        "```",
        "",
        "## Harvest",
        "",
        f"- {len(inv)} export files, {int(inv.bars.sum()):,} rows before de-duplication; {n_overlap:,} overlapping timestamps; "
        f"{n_dis} of them disagree between files (per column: {json.dumps(dis_cols)}). Skipped (no Volume column): {skipped or 'none'}.",
        f"- Sanitize dropped {sanitized_drop} rows.",
        "",
        md_table(inv[["file", "bars", "from_et", "to_et"]]),
        "",
        "## How to extend",
        "",
        "1. On the \"Liquidity Engine Bot\" layout set `CME_MINI:NQ1!`, 1 minute (ETH, Vol indicator stay as they are).",
        "2. Bar Replay -> Select date = D; click the chart, Alt+G, go to D - 20 days. TradingView loads ~10 sessions "
        "(13.9k-15.3k bars) before the replay point and then reports \"Last available bar\".",
        "3. Save/Load menu -> Download chart data -> Download, then `python tools/grab_tv_export.py NQ1_1m_chunk_<D> 3`.",
        "4. Next chunk: D = (first day of the previous chunk) + 1 day, so consecutive chunks overlap.",
        "5. The regular chart (no replay) gives the latest 10 sessions: export it as NQ1_1m_chunk_<today>_regular.",
        "6. `python tools/stitch_tv_1m.py --install`. A new roll must first be in data/NQ_rolls.json (re-run "
        "tools/stitch_tv_chunks.py on new 5m chunks), otherwise the roll check / verification fails.",
        "",
    ]
    os.makedirs(os.path.dirname(DOC), exist_ok=True)
    with open(DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def install():
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    if not os.path.exists(BACKUP):
        shutil.copy2(LIVE, BACKUP)
        print(f"backed up {LIVE} -> {BACKUP}")
    else:
        print(f"backup already present, kept: {BACKUP}")
    tmp = LIVE + ".tmp"
    shutil.copy2(OUT, tmp)
    os.replace(tmp, LIVE)
    print(f"installed {OUT} -> {LIVE}")


def main(argv):
    check_only = "--check" in argv
    raw, inv, skipped = load_chunks()
    n_overlap, n_dis, dis_cols = disagreements(raw)
    uniq, dis = stc.dedupe(raw)
    print(f"{len(inv)} files, {len(raw)} rows -> {len(uniq)} unique bars; overlapping timestamps {n_overlap}, "
          f"disagreeing {n_dis} {dis_cols}; skipped (no volume) {skipped}")
    for x in dis[:5]:
        print("  disagreement", x["et"], x["rows"])
    clean = da.sanitize(uniq, 60, "NQ1! 1m").reset_index(drop=True)
    clean = da.from_first_full_session(clean).reset_index(drop=True)
    sanitized_drop = len(uniq) - len(clean)
    rolls = json.load(open(ROLLS))["rolls"]
    checks = roll_checks(clean, rolls)
    for c in checks:
        print("  roll", c)
    adj = stc.back_adjust(clean, rolls)
    adj["contract"] = stc.label_contracts(adj, rolls)
    ok, ver, m = verify(adj, da.read_bars(REF5))
    print(json.dumps(ver, indent=1))
    roll_ok = all(c["match"] and c["bar_at_switch"] for c in checks)
    if not ok or not roll_ok:
        diagnose(adj, da.read_bars(REF5), m)
        sys.exit(f"VERIFY FAILED (verify ok={ok}, roll check ok={roll_ok}): nothing written")
    q, cov, missing = coverage(adj)
    pd.set_option("display.width", 250)
    print(cov.to_string())
    print("weekdays without a session:", missing)
    print(q[q.status != "OK"][["day", "bars", "expected", "missing_inside", "missing_at_open", "missing_at_close", "holiday", "status"]].to_string())
    if check_only:
        return
    da.write_csv(adj, OUT)
    print(f"wrote {OUT}: {len(adj)} rows, {q.day.nunique()} sessions {q.day.min()} -> {q.day.max()}")
    write_doc(adj, inv, n_overlap, n_dis, dis_cols, checks, ver, q, cov, missing, skipped, sanitized_drop)
    print(f"wrote {DOC}")
    if "--install" in argv:
        install()


if __name__ == "__main__":
    main(sys.argv)
