"""A1 audit (2026-10-25): NQ1! vs MNQ1! 5m signal sensitivity for LIT and ATLAS. Read-only.

The live bot trades on NinjaTrader MNQ bars merged over the TradingView NQ1! history (engine/pcbars.merge_basis); the
backtest runs on NQ1!. The only MNQ bars in data/ are data/tv_mnq_5m_2026-10-16.csv (TradingView CME MNQ1! 5m ETH,
2026-08-23 18:00 -> 2026-10-16 07:10 ET; no MNQ 1m anywhere, data/nt_bars absent). So:
  * bar-level: MNQ vs NQ OHLC differences on the 10,875 shared 5m bars (MNQ before the 2026-09-14 roll sits on NQU26 prices:
    a constant -294.75 = the repo's roll gap, removed here like merge_basis would);
  * LIT: the live way: NQ1! history before 2026-08-23 18:00 + MNQ 5m after it (the PC bot's merge), vs NQ1! only; signals
    (setups sent to the executor) and trades on the 37 sessions 2026-08-24 .. 2026-10-15, with (a) 5m execution and (b) the
    research NQ 1m bars for execution (tol 1 pt, the live feed rule; MNQ 1m: UNTESTED, none exist);
  * ATLAS: engine/second.run at each session's close on both frames (1m: the research NQ 1m bars).
    python -X utf8 research/handoff/2026-10-25/a1_nq_vs_mnq.py   -> a1_nq_vs_mnq.json, a1_nq_vs_mnq_signals.csv
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine import lit, lit_live  # noqa: E402
from engine.data import from_frame, load, load_ltf  # noqa: E402

ET = ZoneInfo("America/New_York")
SIGF = ("limit_px", "stop_px", "target_px", "risk_pts", "rr", "target_label", "swept", "sweep_ext", "ind", "disp")


def frames():
    nq = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    mq = pd.read_csv(os.path.join(ROOT, "data", "tv_mnq_5m_2026-10-16.csv"))
    mq.columns = [c.strip().lower() for c in mq.columns]
    mq = mq[["time", "open", "high", "low", "close", "volume"]].copy()
    roll = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json")))["rolls"][-1]
    pre = mq["time"] < roll["switch_t"]
    for c in ("open", "high", "low", "close"):
        mq.loc[pre, c] = mq.loc[pre, c] + roll["gap"]          # onto the repo's back-adjusted NQZ26 basis
    t_end = int(mq["time"].max())
    t_a = int(mq["time"].min())
    lo = int(dt.datetime(2026, 6, 1, 18, 0, tzinfo=ET).timestamp())
    nqw = nq[(nq["time"] >= lo) & (nq["time"] <= t_end)].reset_index(drop=True)
    hyb = pd.concat([nq[(nq["time"] >= lo) & (nq["time"] < t_a)], mq]).sort_values("time").reset_index(drop=True)
    return nq, mq, nqw, hyb, roll


def bar_diffs(nq, mq):
    m = nq.merge(mq, on="time", suffixes=("_nq", "_mnq"))
    out = {"bars": len(m)}
    for c in ("open", "high", "low", "close"):
        d = (m[c + "_mnq"] - m[c + "_nq"]).to_numpy()
        out[c] = {"exact_pct": round(float((np.abs(d) < 1e-9).mean() * 100), 1),
                  "within_1tick_pct": round(float((np.abs(d) <= 0.25 + 1e-9).mean() * 100), 1),
                  "within_1pt_pct": round(float((np.abs(d) <= 1.0 + 1e-9).mean() * 100), 1),
                  "p1": float(np.percentile(d, 1)), "p99": float(np.percentile(d, 99)), "max_abs": float(np.abs(d).max()),
                  "mean": round(float(d.mean()), 3)}
    rng = (m["high_mnq"] - m["low_mnq"]) - (m["high_nq"] - m["low_nq"])
    out["range_mnq_minus_nq_mean"] = round(float(rng.mean()), 3)
    return out


def lit_runs(nqw, hyb, days):
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    out = {}
    for lab, tf in (("exec_5m", "5m"), ("exec_1m_nq", "1m")):
        PP = {**lit.DEFAULTS, **P, "tf": tf}
        res = {}
        for nm, fr in (("nq", nqw), ("mnq", hyb)):
            M = lit.Market(bars=from_frame("NQ", "5m", fr))
            C = lit.candidates(M, ref=PP["ref"])
            B1 = None
            if tf == "1m":
                src = b1.slice(int(np.searchsorted(b1.t, int(fr["time"].min()))), int(np.searchsorted(b1.t, int(fr["time"].max()) + 300)))
                B1 = lit.bars_1m(M, src=src, tol=lit_live.LIVE_TOL_1M)
            R = lit.run_live(M, C, PP, B1=B1, B5=lit.bars_5m(M))
            sig = {(s["day"], s["t"], s["dir"]): s for s in R["signals"] if s["day"] in days}
            tr = {t["day"]: t for t in R["trades"] if t["day"] in days and t.get("exit") != "OPEN"}
            res[nm] = (sig, tr)
        (sn, tn), (sm, tm) = res["nq"], res["mnq"]
        rows = []
        for k in sorted(set(sn) | set(sm)):
            a, b = sn.get(k), sm.get(k)
            if a and b:
                dd = [f for f in SIGF if json.dumps(a.get(f), default=str) != json.dumps(b.get(f), default=str)]
                kind = "same" if not dd else "fields differ"
            else:
                dd, kind = [], "NQ only" if a else "MNQ only"
            rows.append({"run": lab, "day": k[0], "t": k[1], "dir": k[2], "kind": kind, "fields": ",".join(dd),
                         "nq": a and {f: a.get(f) for f in SIGF[:5]}, "mnq": b and {f: b.get(f) for f in SIGF[:5]}})
        trows = []
        for d in sorted(set(tn) | set(tm)):
            a, b = tn.get(d), tm.get(d)
            ka = a and (int(a["entry_t"]), int(a["dir"]), a["exit"], round(a["pnl"], 2))
            kb = b and (int(b["entry_t"]), int(b["dir"]), b["exit"], round(b["pnl"], 2))
            trows.append({"day": d, "same": ka == kb, "nq": ka, "mnq": kb})
        k_ = {}
        for r in rows:
            k_[r["kind"]] = k_.get(r["kind"], 0) + 1
        out[lab] = {"signals": k_, "signal_rows": rows, "trades_nq": len(tn), "trades_mnq": len(tm),
                    "trades_same": sum(r["same"] for r in trows), "trade_rows": trows,
                    "net_nq": round(sum(t["pnl"] for t in tn.values()), 2), "net_mnq": round(sum(t["pnl"] for t in tm.values()), 2)}
    return out


def atlas_runs(nqw, hyb, days):
    from engine import second
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    cfg = second.load_cfg()
    keep = {k: v for k, v in cfg["strategies"].items() if k in ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")}
    cfg = {**cfg, "strategies": keep}
    got = {"nq": {}, "mnq": {}}
    for d in days:
        now = int(dt.datetime.combine(dt.date.fromisoformat(d), dt.time(17, 0), ET).timestamp())
        for nm, fr in (("nq", nqw), ("mnq", hyb)):
            cut = fr[fr["time"] + 300 <= now]
            one = b1.slice(int(np.searchsorted(b1.t, int(cut["time"].min()))), int(np.searchsorted(b1.t + 60, now, side="right")))
            r = second.run(cut, one_min=one, now=now, cfg=cfg, lit=[])
            for k, s in r["strategies"].items():
                for t in s["trades"]:
                    if t["day"] == d:
                        got[nm].setdefault(k, {})[(t["day"], int(t["entry_t"]), int(t["dir"]))] = (t["exit_kind"], t["r"], t["usd"])
    out = {}
    for k in keep:
        a, b = got["nq"].get(k, {}), got["mnq"].get(k, {})
        out[k] = {"nq": len(a), "mnq": len(b), "same_entry": len(set(a) & set(b)),
                  "same_entry_and_exit": sum(1 for x in set(a) & set(b) if a[x][:2] == b[x][:2]),
                  "nq_only": sorted(map(str, set(a) - set(b))), "mnq_only": sorted(map(str, set(b) - set(a))),
                  "net_nq": round(sum(v[2] for v in a.values()), 2), "net_mnq": round(sum(v[2] for v in b.values()), 2)}
    return out


def main():
    nq, mq, nqw, hyb, roll = frames()
    e = (pd.to_datetime(mq["time"], unit="s", utc=True).dt.tz_convert(ET) + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
    days = sorted(set(e) - {e.iloc[-1]})                 # the last MNQ day (10-16) ends at 07:10: left out
    rep = {"label": "A1 NQ1! vs MNQ1! (TradingView 5m) signal sensitivity", "sessions": [days[0], days[-1], len(days)],
           "roll_gap_removed_before": roll["switch_et"], "gap": roll["gap"], "bars": bar_diffs(nq, mq)}
    print(json.dumps(rep, indent=1))
    rep["lit"] = lit_runs(nqw, hyb, set(days))
    for lab, r in rep["lit"].items():
        print(lab, r["signals"], "trades nq/mnq/same", r["trades_nq"], r["trades_mnq"], r["trades_same"], "net", r["net_nq"], r["net_mnq"])
        for t in r["trade_rows"]:
            if not t["same"]:
                print("   ", t)
    rep["atlas"] = atlas_runs(nqw, hyb, days)
    print(json.dumps(rep["atlas"], indent=1))
    pd.DataFrame([x for r in rep["lit"].values() for x in r["signal_rows"]]).to_csv(os.path.join(HERE, "a1_nq_vs_mnq_signals.csv"), index=False)
    json.dump(rep, open(os.path.join(HERE, "a1_nq_vs_mnq.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
