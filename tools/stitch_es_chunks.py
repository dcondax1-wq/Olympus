"""Stitch TradingView ES1! 5m exports into data/clean/ES_{5m,15m,1h}.csv (back-adjusted, anchored to ESZ26).

    python tools/stitch_es_chunks.py           # build data/clean/ES_*, print the price-space check
    python tools/stitch_es_chunks.py --check   # report only, write nothing
    python tools/stitch_es_chunks.py --swap    # build, then back up data/ES_{5m,15m,1h}.csv + ES_rolls.json to
                                               # data/_pre_clean_backup/*.pre_tv.* and copy the clean files to data/

Inputs (read-only)
  data/tv_exports/ES1_5m_chunk_*.csv     CME_MINI:ES1! 5m ETH (Bar Replay chunks), front-month UNADJUSTED
  data/clean/ES_5m.csv + ES_rolls.json   Yahoo ES=F 5m from 2026-08-06, already back-adjusted to ESZ26 (data_audit.build_es)
  data/_pre_clean_backup/ES_5m.csv, ES_1h.csv   the original raw Yahoo ES=F files (roll-gap cross-check, price-space check)

Method (same as tools/stitch_tv_chunks.py for NQ)
  1. Chunks de-duplicated (overlaps must agree), sanitized (break / weekend / flat placeholder rows dropped).
  2. TradingView front-month switches located with stitch_tv_chunks.detect_rolls (first bar of the session 3 full trading
     days before the last trading day; the rule-check flags any bigger weekday jump in the roll week).
  3. Gap per roll, best first: the weekday session-open jump; the raw Yahoo ES=F 1h quotes at the same hours, where
     Yahoo and TradingView sat on different contracts (sign-corrected median); carry model (median gap/price of the
     measured rolls). Tick-rounded.
  4. Back-adjust additively to the newest TradingView contract, then add the Sep-2026 (ESU26->ESZ26) gap from
     ES_rolls.json so the whole series is in ESZ26 price space, the same space as the clean Yahoo bars after Aug 2026.
  5. Per trading day one source: TradingView if it has >= 98% of the bars Yahoo has that day, else the clean Yahoo bars.
  6. 15m and 1h are resampled from the stitched 5m (ES 1h therefore now starts 2025-04, not 2024-05).
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_audit as da  # noqa: E402
import stitch_tv_chunks as st  # noqa: E402

BK = os.path.join(da.DATA, "_pre_clean_backup")


def yahoo_cross_gap(tv, y1h, roll, min_abs=10.0):
    """Hours in the roll window where Yahoo ES=F and TradingView quote different contracts: d = yahoo - tv equals +gap
    before the TV switch (Yahoo already on the new contract) or -gap after it (Yahoo still on the old one)."""
    if y1h is None or y1h.empty:
        return None
    sw = roll["switch_t"]
    h = da.resample(tv[(tv.time >= sw - 6 * 86400) & (tv.time < sw + 6 * 86400)], 3600)
    m = h.merge(y1h[["time", "close"]], on="time", suffixes=("", "_y"))
    if m.empty:
        return None
    d = np.where(m.time < sw, m.close_y - m.close, -(m.close_y - m.close))
    sel = d[np.abs(m.close_y - m.close) > min_abs]
    if len(sel) < 4:
        return None
    med = float(np.median(sel))
    return med, float(np.median(np.abs(sel - med)) * 1.4826 / np.sqrt(len(sel)) + 0.25), int(len(sel))


def main(argv):
    check = "--check" in argv
    paths = sorted(glob.glob(os.path.join(da.DATA, "tv_exports", "ES1_5m_*.csv")))
    tv, skipped = st._load_group(paths, "tv-ES1!")
    tv, dis = st.dedupe(tv)
    print(f"ES1! files: {len(paths)} -> {len(tv)} unique bars; overlap disagreements {len(dis)}; skipped {skipped}")
    tv = da.sanitize(tv, 300, "ES1! 5m").reset_index(drop=True)
    y5_raw = da.read_bars(os.path.join(BK, "ES_5m.csv")) if os.path.exists(os.path.join(BK, "ES_5m.csv")) else None
    y1h_raw = da.sanitize(da.read_bars(os.path.join(BK, "ES_1h.csv")), 3600) if os.path.exists(os.path.join(BK, "ES_1h.csv")) else None
    yc = da.read_bars(os.path.join(da.CLEAN, "ES_5m.csv"))           # clean Yahoo, ESZ26 space
    es_rolls = json.load(open(os.path.join(da.CLEAN, "ES_rolls.json")))
    sep26 = [r for r in es_rolls["rolls"] if r["from"] == "ESU26"]
    if not sep26:
        sys.exit("ES_rolls.json has no ESU26->ESZ26 roll")
    g_sep26 = float(sep26[0]["gap"])

    rolls, p50, p90 = st.detect_rolls(tv, sym="ES")
    measured = []
    for r in rolls:
        r["candidates"] = {}
        if not r["weekend_switch"]:
            r["candidates"]["open_jump"] = {"gap": r["open_jump"], "unc": round(p50, 2)}
        yg = yahoo_cross_gap(tv, y1h_raw, r)
        if yg:
            r["candidates"]["yahoo_1h_cross"] = {"gap": round(yg[0], 2), "unc": round(yg[1], 2), "n": yg[2]}
        px = float(tv.loc[tv.time < r["switch_t"], "close"].iloc[-1])
        r["price_before"] = px
        c = r["candidates"].get("open_jump") or r["candidates"].get("yahoo_1h_cross")
        if c:
            measured.append(c["gap"] / px)
    carry = float(np.median(measured)) if measured else None
    for r in rolls:
        if carry is not None:
            r["candidates"]["carry_model"] = {"gap": round(carry * r["price_before"], 2), "pct": round(carry * 100, 3)}
        for k in ("open_jump", "yahoo_1h_cross", "carry_model"):
            if k in r["candidates"]:
                r["method"], r["gap"], r["uncertainty"] = k, round(r["candidates"][k]["gap"] * 4) / 4, r["candidates"][k].get("unc")
                break
        else:
            r["method"], r["gap"], r["uncertainty"] = "none", 0.0, None
        print(f"roll {r['from']}->{r['to']} switch {r['switch_et']} jump {r['open_jump']:+.2f} -> gap {r['gap']:+.2f} "
              f"({r['method']}, check {r['check']})  candidates {json.dumps(r['candidates'])}")
    tv["contract"] = st.label_contracts(tv, rolls, "ES")
    adj = st.back_adjust(tv, rolls)
    newest = str(tv["contract"].iloc[-1]) if len(tv) else ""
    if newest != "ESZ26":                                             # TV data ends before the Sep-2026 roll:
        for c in ("open", "high", "low", "close"):                   # shift into ESZ26 price space
            adj[c] += g_sep26
    print(f"newest TradingView contract {newest}: {'already ESZ26, no extra shift' if newest == 'ESZ26' else f'shifted by Sep-26 gap {g_sep26:+.2f}'}")
    adj["source"] = "tv-ES1!"

    # ---- price-space check on the days both sources have (Aug 2026)
    ov = adj.merge(yc, on="time", suffixes=("", "_y"))
    dclose = (ov.close - ov.close_y)
    print(f"price-space check vs clean Yahoo (ESZ26 space): {len(ov)} shared bars, close diff median {dclose.median():+.2f}, "
          f"|diff| p90 {dclose.abs().quantile(0.9):.2f}, max {dclose.abs().max():.2f}")
    if y5_raw is not None:
        ovr = tv.merge(y5_raw, on="time", suffixes=("", "_y"))
        dr = ovr.close - ovr.close_y
        print(f"raw check vs raw Yahoo ES=F: {len(ovr)} shared bars, close diff median {dr.median():+.2f}, |diff| p90 {dr.abs().quantile(0.9):.2f}")
    if len(ov) and abs(dclose.median()) > 1.0:
        sys.exit("price spaces disagree by more than 1 pt - not writing")

    # ---- one source per trading day
    a = adj.assign(td=da.tday_of(adj.time))
    y = yc.assign(td=da.tday_of(yc.time), source="yahoo-ES=F")
    ct, cy = a.groupby("td").size(), y.groupby("td").size()
    days = sorted(set(ct.index) | set(cy.index))
    pick = {d: ("tv" if ct.get(d, 0) > 0 and ct.get(d, 0) >= 0.98 * cy.get(d, 0) else "y") for d in days}
    out = pd.concat([a[a.td.map(pick) == "tv"], y[y.td.map(pick) == "y"]]).sort_values("time").drop_duplicates("time")
    out = out.reset_index(drop=True)
    yc_contract = np.where(out.time < sep26[0]["switch_t"], "ESU26", "ESZ26")
    out["contract"] = np.where(out.source == "tv-ES1!", out.get("contract", ""), yc_contract)
    n_tv = sum(1 for v in pick.values() if v == "tv"); n_y = len(pick) - n_tv
    print(f"stitched ES 5m: {len(out)} bars, {len(pick)} sessions ({n_tv} TradingView, {n_y} Yahoo), "
          f"{da.et_of([out.time.min()])[0]} -> {da.et_of([out.time.max()])[0]}")
    if check:
        return
    da.write_csv(out, os.path.join(da.CLEAN, "ES_5m.csv"))
    da.write_csv(da.resample(out, 900), os.path.join(da.CLEAN, "ES_15m.csv"))
    da.write_csv(da.resample(out, 3600), os.path.join(da.CLEAN, "ES_1h.csv"))
    os.makedirs(os.path.join(da.CLEAN, "raw"), exist_ok=True)
    da.write_csv(tv, os.path.join(da.CLEAN, "raw", "ES_5m_unadjusted_tv.csv"), da.COLS + ["source", "contract"])
    allr = [{k: v for k, v in r.items()} for r in rolls] + sep26
    json.dump({"sym": "ES", "anchor": "ESZ26",
               "method": "additive back-adjustment anchored to ESZ26: bars with time < switch_t get +gap (cumulative). "
                         "TradingView ES1! chunks 2025-04 -> 2026-08-23, clean Yahoo ES=F after that.",
               "rolls": allr, "carry_pct": None if carry is None else round(carry * 100, 3),
               "sessions": {"tv-ES1!": n_tv, "yahoo-ES=F": n_y}, "tv_files": [os.path.basename(p) for p in paths]},
              open(os.path.join(da.CLEAN, "ES_rolls.json"), "w"), indent=1, default=str)
    mpath = os.path.join(da.CLEAN, "manifest.json")
    if os.path.exists(mpath):
        man = json.load(open(mpath))
        for f in ("ES_5m.csv", "ES_15m.csv", "ES_1h.csv"):
            x = pd.read_csv(os.path.join(da.CLEAN, f), usecols=["time"])
            man.setdefault("files", {})[f] = {"rows": int(len(x)), "from_et": str(da.et_of([x.time.min()])[0]),
                                              "to_et": str(da.et_of([x.time.max()])[0])}
        man["es_sources"] = {"tv-ES1!": [os.path.basename(p) for p in paths], "yahoo-ES=F": "clean ES_5m (2026-08-06 ->)",
                             "builder": "tools/stitch_es_chunks.py"}
        json.dump(man, open(mpath, "w"), indent=1, default=str)
    print("wrote data/clean/ES_5m.csv, ES_15m.csv, ES_1h.csv, ES_rolls.json, raw/ES_5m_unadjusted_tv.csv")
    if "--swap" in argv:
        os.makedirs(BK, exist_ok=True)
        for f in ("ES_5m.csv", "ES_15m.csv", "ES_1h.csv", "ES_rolls.json"):
            src = os.path.join(da.DATA, f)
            if os.path.exists(src):
                base, ext = os.path.splitext(f)
                shutil.copy2(src, os.path.join(BK, f"{base}.pre_tv{ext}"))
            shutil.copy2(os.path.join(da.CLEAN, f), src)
        print("backed up data/ES_{5m,15m,1h}.csv + ES_rolls.json to data/_pre_clean_backup/*.pre_tv.*, copied clean ES to data/")


if __name__ == "__main__":
    main(sys.argv)
