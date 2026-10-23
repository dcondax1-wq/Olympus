"""Stitch TradingView ES1! 5m exports into data/clean/ES_{5m,15m,1h}.csv (back-adjusted, anchored to the newest contract).

    python tools/stitch_es_chunks.py           # build data/clean/ES_*, ES_rolls.json
    python tools/stitch_es_chunks.py --check   # report only, write nothing
    python tools/stitch_es_chunks.py --swap    # build, then back up data/ES_{5m,15m,1h}.csv + ES_rolls.json to
                                               # data/_pre_clean_backup/*.pre_tv.* and copy the clean files to data/

Inputs (read-only; official data only, owner 2026-10-23)
  data/tv_exports/ES1_5m_chunk_*.csv     CME_MINI:ES1! 5m ETH (Bar Replay chunks + the regular-chart export), front-month
                                         UNADJUSTED
  data/tv_exports/ESZ26_1h_*.csv         optional TradingView single-contract exports (any ES<M><YY>_1h_ / _5m_ file)

Method (same code as tools/stitch_tv_chunks.py for NQ)
  1. Chunks de-duplicated (overlaps must agree), sanitized (break / weekend / flat placeholder rows dropped).
  2. TradingView front-month switches located with stitch_tv_chunks.detect_rolls (first bar of the session 3 full trading
     days before the last trading day; the rule-check flags any bigger weekday jump in the roll week).
  3. Gap per roll: stitch_tv_chunks.estimate_gaps (a TradingView single-contract export when there is one; the weekday
     session-open jump; the carry model of the 4 nearest directly measured rolls for weekend switches). Tick-rounded.
  4. Back-adjust additively to the newest TradingView contract.
  5. 15m, 1h and 1d (per CME trading day) are built from the stitched 5m.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_audit as da  # noqa: E402
import stitch_tv_chunks as st  # noqa: E402

BK = os.path.join(da.DATA, "_pre_clean_backup")


def main(argv):
    check = "--check" in argv
    paths = sorted(glob.glob(os.path.join(da.DATA, "tv_exports", "ES1_5m_*.csv")))
    tv, skipped = st._load_group(paths, "tv-ES1!")
    tv, dis = st.dedupe(tv)
    print(f"ES1! files: {len(paths)} -> {len(tv)} unique bars; overlap disagreements {len(dis)}; skipped {skipped}")
    tv = da.sanitize(tv, 300, "ES1! 5m").reset_index(drop=True)
    tv["source"] = "tv-ES1!"

    rolls, p50, p90 = st.detect_rolls(tv, sym="ES")
    ov_path = os.path.join(da.CLEAN, "ES_roll_overrides.json")
    overrides = json.load(open(ov_path)) if os.path.exists(ov_path) else {}
    rolls, carry = st.estimate_gaps(tv, rolls, p50, p90, None, overrides, sym="ES")
    for r in rolls:
        print(f"roll {r['from']}->{r['to']} switch {r['switch_et']} jump {r['open_jump']:+.2f} -> gap {r['gap']:+.2f} "
              f"({r['method']}, +-{r['uncertainty']}, check {r['check']})  candidates {json.dumps(r['candidates'])}")
    tv["contract"] = st.label_contracts(tv, rolls, "ES")
    out = st.back_adjust(tv, rolls).drop(columns="adj")
    newest = str(tv["contract"].iloc[-1]) if len(tv) else ""
    n_tv = len(set(da.tday_of(out.time)))
    print(f"stitched ES 5m: {len(out)} bars, {n_tv} sessions (all TradingView ES1!), anchor {newest}, "
          f"{da.et_of([out.time.min()])[0]} -> {da.et_of([out.time.max()])[0]}")
    if check:
        return
    da.write_csv(out, os.path.join(da.CLEAN, "ES_5m.csv"))
    da.write_csv(da.resample(out, 900), os.path.join(da.CLEAN, "ES_15m.csv"))
    da.write_csv(da.resample(out, 3600), os.path.join(da.CLEAN, "ES_1h.csv"))
    da.write_csv(da.daily(out), os.path.join(da.CLEAN, "ES_1d.csv"))
    os.makedirs(os.path.join(da.CLEAN, "raw"), exist_ok=True)
    da.write_csv(tv, os.path.join(da.CLEAN, "raw", "ES_5m_unadjusted_tv.csv"), da.COLS + ["source", "contract"])
    json.dump({"sym": "ES", "anchor": newest,
               "method": f"additive back-adjustment anchored to {newest}: bars with time < switch_t get +gap (cumulative). "
                         "Unadjusted price = adjusted - sum(gaps of rolls after the bar). TradingView ES1! chunks only.",
               "rolls": [{k: v for k, v in r.items()} for r in rolls], "carry_pct": None if carry is None else round(carry * 100, 3),
               "weekday_open_drift_p50_p90": [p50, p90],
               "sessions": {"tv-ES1!": n_tv}, "tv_files": [os.path.basename(p) for p in paths]},
              open(os.path.join(da.CLEAN, "ES_rolls.json"), "w"), indent=1, default=str)
    mpath = os.path.join(da.CLEAN, "manifest.json")
    if os.path.exists(mpath):
        man = json.load(open(mpath))
        for f in ("ES_5m.csv", "ES_15m.csv", "ES_1h.csv", "ES_1d.csv"):
            x = pd.read_csv(os.path.join(da.CLEAN, f), usecols=["time"])
            man.setdefault("files", {})[f] = {"rows": int(len(x)), "from_et": str(da.et_of([x.time.min()])[0]),
                                              "to_et": str(da.et_of([x.time.max()])[0])}
        man["es_sources"] = {"tv-ES1!": [os.path.basename(p) for p in paths], "builder": "tools/stitch_es_chunks.py"}
        json.dump(man, open(mpath, "w"), indent=1, default=str)
    print("wrote data/clean/ES_5m.csv, ES_15m.csv, ES_1h.csv, ES_rolls.json, raw/ES_5m_unadjusted_tv.csv")
    if "--swap" in argv:
        os.makedirs(BK, exist_ok=True)
        for f in ("ES_5m.csv", "ES_15m.csv", "ES_1h.csv", "ES_1d.csv", "ES_rolls.json"):
            src = os.path.join(da.DATA, f)
            if os.path.exists(src):
                base, ext = os.path.splitext(f)
                shutil.copy2(src, os.path.join(BK, f"{base}.pre_tv{ext}"))
            shutil.copy2(os.path.join(da.CLEAN, f), src)
        print("backed up data/ES_{5m,15m,1h}.csv + ES_rolls.json to data/_pre_clean_backup/*.pre_tv.*, copied clean ES to data/")


if __name__ == "__main__":
    main(sys.argv)
