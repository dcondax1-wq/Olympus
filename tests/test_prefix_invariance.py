"""Prefix invariance (A1 pre-launch audit 2026-10-25): every 2026 LIT signal and every 2026 ATLAS trade (EMA, MACD, S/R),
re-run through the LIVE code on data truncated at its decision bar, must emit the same signal as the full-history run.

    python -X utf8 -m tests.test_prefix_invariance              # quick: LIT (research-clean 1m) + ATLAS (~3.5 min)
    python -X utf8 -m tests.test_prefix_invariance --full       # + LIT with the raw data/NQ_1m.csv as the feed (~8 min)
    python -X utf8 -m tests.test_prefix_invariance --lit        # LIT only (--atlas: ATLAS only)

Known differences (reported with the reason, not failed; anything else fails), see KNOWN below:
  2026-04-03  Good Friday: the backtest's whole-day 1m cover rule (as tests/test_lit_live.py KNOWN).
  2026-01-14  the day's 1m cover sits at the 97% line at 02:00: the signal's execution bar size flips 1m/5m from poll to
              poll (lit.bars_1m counts the forming window's 1m bars in the numerator only); the trade is identical.
  2026-03-23, 2026-05-05  clean harness only: engine/data._clean_1m drops the genuine 1m window of the trigger bar (volume
              heuristic), so the early view has no 1m bars for it and sees the setup at the entry bar's close (the raw feed sees
              it at once). On 03-23 the backtest's CISD entry (06:58) falls inside that wait, so it is missed there too.
  2026-03-23, 2026-05-05  raw feed: the live 1m bars keep windows the research cleaning dropped, so the live CISD entry
              differs from the backtest (research/handoff/2026-10-25/a1_clean1m_variant.py: the backtest without that
              heuristic gives exactly the live trades; 2026 net -$730).

LIT (live_model.json "lit"):
  reference = engine/lit.py on the WHOLE history (lit.Market() + candidates + bars_1m research rule): run_live "signals"
  (every setup sent to the executor, its limit / stop / target / R:R / label / sweep) and tools/lit_final.run trades.
  a. signal: cut at the trigger bar's close (5m bars closed by then, 1m bars closed by then, the forming 1m bar's open),
     engine/lit_live.run(early=True) as the PC bot polls: the signal must be there with every field equal. A signal first
     seen at the entry bar's close (no 1m bar for the early view) is "late", compared too.
  b. entry: cut at the 1m CISD candle's close (= the backtest fill bar's open): state "enter_now" must be the backtest
     trade (entry, stop, target, micros), not an estimate; cut at the fill bar's close: the open position / finished trade.
  c. phantom: a signal at the cut time that the full run does not have (reported with the reason when known).
ATLAS (second_model.json members ema_lon_vix, macd_sweep, sr_nyreclaim; reference = the research trades of
research/second/*_best.json, full-history research modules):
  a. cut at the signal bar's close: engine/second.run state "signal" = same side and stop, and no trade yet;
  b. cut at the entry bar's close: the trade is there with the research entry, stop and target.
Results -> research/handoff/2026-10-25/a1_prefix_invariance.json
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "research", "handoff", "2026-10-25", "a1_prefix_invariance.json")
SIGF = ("dir", "limit_px", "stop_px", "target_px", "risk_pts", "rr", "target_label", "swept", "sweep_ext", "ind", "disp", "how")
RESULTS = []
KNOWN = {   # mode -> {"entry": days whose entry may differ, "tf": signal bar-size flips, "late": signals seen at the entry bar close}
    "clean": {"entry": ("2026-04-03", "2026-03-23"), "tf": ("2026-04-03", "2026-01-14"), "late": ("2026-04-03", "2026-03-23", "2026-05-05")},
    "raw_feed": {"entry": ("2026-04-03", "2026-03-23", "2026-05-05"), "tf": ("2026-04-03", "2026-01-14"), "late": ("2026-04-03",)},
}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def _n(x):
    return json.dumps(x, sort_keys=True, default=str)


# ------------------------------------------------------------------------------------------------ LIT
def lit_part(raw1m=False):
    from engine import lit, lit_live
    from engine.data import load, load_ltf
    from tools import lit_final as F
    from tests.test_lit_live import ref_key, day_close
    t0 = time.time()
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    PP = {**lit.DEFAULTS, **P}
    M, C = F.market(PP["ref"], PP["extra_boxes"])
    R = lit.run_live(M, C, PP, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    SIG = [s for s in R["signals"] if "2026-01-01" <= s["day"] <= "2026-10-16"]
    REF = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    print(f"LIT reference (whole history): {len(SIG)} signals, {len(REF)} trades in 2026 ({time.time() - t0:.0f}s)", flush=True)
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] >= day_close("2025-12-01") - 60 * 86400].reset_index(drop=True)
    T5 = df5["time"].values
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
    raw = None
    if raw1m:
        raw = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        raw = raw[raw["time"] >= int(df5["time"].min())].reset_index(drop=True)
    o1 = dict(zip(b1.t.astype(np.int64).tolist(), b1.o.astype(float).tolist()))
    # the forming 1m bar's open as the feed shows it: research-clean bars (as tests/test_lit_live.py) / the raw file (feed mode)
    o1r = dict(zip(raw["time"].astype(np.int64).tolist(), raw["open"].astype(float).tolist())) if raw is not None else {}
    sig_by = {(s["t"], s["dir"]): s for s in SIG}

    def poll(now, use_raw=False):
        cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
        if use_raw:
            cut1 = raw.iloc[:int(np.searchsorted(raw["time"].values + 60, now, side="right"))]
        else:
            cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
        m0 = now - now % 60
        oo = o1r if use_raw else o1
        forming = (m0, oo[m0]) if m0 in oo else None
        keep = {}
        res = lit_live.run(cut5, P, one_min=cut1, now=now, forming=forming, early=True, keep=keep)
        return res, keep["R"]

    out = {}
    for mode in (("clean", False),) + ((("raw_feed", True),) if raw1m else ()):
        name, use_raw = mode
        t1 = time.time()
        same = late = 0
        diff, missing, phantom, tf_diff, late_l = [], [], [], [], []
        for s in SIG:
            res, Rc = poll(s["t"] + 2, use_raw)
            got = {(x["t"], x["dir"]): x for x in Rc["signals"]}
            g = got.get((s["t"], s["dir"]))
            for k, x in got.items():
                if k[0] == s["t"] and k not in sig_by:
                    pend = [p for p in Rc.get("pending") or [] if p.get("day") == x["day"] and p.get("sig_t", 0) < s["t"]]
                    phantom.append({"t": k[0], "dir": k[1], "day": x["day"], "earlier_pending": bool(pend)})
            if g is None:
                res, Rc = poll(s["t"] + 302, use_raw)              # the entry bar has closed (the non-early view)
                g = {(x["t"], x["dir"]): x for x in Rc["signals"]}.get((s["t"], s["dir"]))
                if g is not None:
                    late += 1
                    late_l.append({"day": s["day"], "t": s["t"], "status_full": s["status"]})
            if g is None:
                missing.append({"day": s["day"], "t": s["t"], "dir": s["dir"], "status_full": s["status"]})
                continue
            dd = [f for f in SIGF if _n(g.get(f)) != _n(s.get(f))]
            if dd:
                diff.append({"day": s["day"], "t": s["t"], "fields": dd, "full": {f: s.get(f) for f in dd}, "cut": {f: g.get(f) for f in dd}})
            else:
                same += 1
            if g.get("tf") != s.get("tf"):
                tf_diff.append({"day": s["day"], "t": s["t"], "full_tf": s.get("tf"), "cut_tf": g.get("tf"), "status_full": s["status"]})
        # b. entries
        e_ok, e_bad, p_ok, p_bad = 0, [], 0, []
        for w in REF:
            res, _ = poll(int(w["entry_t"]) + 2, use_raw)
            en = res["state"].get("enter_now")
            ek = en and (en["entry_t"], en["dir"], round(en["entry"], 2), round(en["stop0"], 2), round(en["target"], 2), en["qty"])
            if en and ek == ref_key(w) and not en.get("est"):
                e_ok += 1
            else:
                pos = res["state"].get("position")
                e_bad.append({"day": w["day"], "tf": w.get("tf"), "want": ref_key(w), "enter_now": ek, "est": en and en.get("est"),
                              "position": pos and (pos["entry_t"], pos["dir"], round(pos["entry"], 2), round(pos["stop0"], 2),
                                                   round(pos["target"], 2), pos["qty"])})
            res, _ = poll(int(w["entry_t"]) + 60 * int(w.get("tf") or 5) + 2, use_raw)
            pos = res["state"].get("position")
            fin = [t for t in res["trades"] if t["day"] == w["day"] and int(t["entry_t"]) == int(w["entry_t"])]
            pk = pos and (pos["entry_t"], pos["dir"], round(pos["entry"], 2), round(pos["stop0"], 2), round(pos["target"], 2), pos["qty"])
            fk = fin and (int(fin[0]["entry_t"]), int(fin[0]["dir"]), round(fin[0]["entry"], 2), round(fin[0]["stop"], 2),
                          round(fin[0]["target"], 2), int(fin[0]["qty"]))
            if pk == ref_key(w) or fk == ref_key(w):
                p_ok += 1
            else:
                p_bad.append({"day": w["day"], "want": ref_key(w), "position": pk, "finished": fk})
        known = set(KNOWN[name]["entry"])
        e_bad_u = [x for x in e_bad if x["day"] not in known]
        p_bad_u = [x for x in p_bad if x["day"] not in known]
        r = {"signals": len(SIG), "same": same, "late_seen_at_entry_bar_close": late, "late": late_l, "differ": diff, "missing": missing,
             "phantom": phantom, "tf_differs": tf_diff, "trades": len(REF), "enter_now_ok": e_ok, "enter_now_bad": e_bad,
             "position_ok": p_ok, "position_bad": p_bad, "known_days": sorted(known), "seconds": round(time.time() - t1)}
        out[name] = r
        lab = "LIT" + (" (raw 1m feed)" if use_raw else "")
        check(f"{lab} a: {same}/{len(SIG)} 2026 signals identical on data cut at the trigger bar's close ({late} first seen at the "
              f"entry bar's close: {[x['day'] for x in late_l]}), {len(diff)} differ, {len(missing)} missing",
              same == len(SIG) and not diff and not missing and all(x["day"] in KNOWN[name]["late"] for x in late_l),
              {"differ": diff[:3], "missing": missing[:3], "late": late_l})
        check(f"{lab} a: execution bar size (1m / 5m) of the signal same as the full run on {len(SIG) - len(tf_diff)}/{len(SIG)}",
              not [x for x in tf_diff if x["day"] not in KNOWN[name]["tf"]], tf_diff[:5])
        check(f"{lab} b: {e_ok}/{len(REF)} trades decided at the 1m CISD close as the backtest trade (entry, stop, target, micros; "
              f"known days {sorted(known)} reported, not failed: {len(e_bad) - len(e_bad_u)})", not e_bad_u, e_bad_u[:3])
        check(f"{lab} b: {p_ok}/{len(REF)} open positions / finished trades at the fill bar's close = the backtest trade",
              not p_bad_u, p_bad_u[:3])
        check(f"{lab} c: phantom signals at the cut time {len(phantom)} (an earlier setup's limit still pending: "
              f"{sum(p['earlier_pending'] for p in phantom)})", all(p["earlier_pending"] for p in phantom), phantom[:5])
    return out


# ------------------------------------------------------------------------------------------------ ATLAS
def atlas_part():
    from tests.test_second import Data, key
    t0 = time.time()
    D = Data()
    out = {}
    for k, ref in D.ref.items():
        s_ok, s_bad, t_ok, t_bad = 0, [], 0, []
        for w in ref:
            now = int(w["entry_t"]) + 2
            r = D.poll(now, only=k)["strategies"][k]
            sg = (r.get("state") or {}).get("signal")
            early_trade = any(key(t) == key(w) for t in r["trades"])
            if sg and int(sg["dir"]) == int(w["dir"]) and abs(float(sg["stop"]) - float(w["stop"])) < 1e-6 and not early_trade:
                s_ok += 1
            else:
                s_bad.append({"day": w["day"], "entry_t": w["entry_t"], "signal": sg, "trade_before_entry": early_trade,
                              "text": (r.get("state") or {}).get("text")})
            r = D.poll(int(w["entry_t"]) + 302, only=k)["strategies"][k]
            t = next((t for t in r["trades"] if key(t) == key(w)), None)
            if t is not None and abs(t["entry"] - w["entry"]) < 1e-6 and abs(t["stop"] - w["stop"]) < 1e-6 \
                    and abs(t["target"] - w["target"]) < 0.011:
                t_ok += 1
            else:
                t_bad.append({"day": w["day"], "entry_t": w["entry_t"], "got": t and {x: t.get(x) for x in ("entry", "stop", "target")},
                              "want": {x: w.get(x) for x in ("entry", "stop", "target")}})
        out[k] = {"trades": len(ref), "signal_ok": s_ok, "signal_bad": s_bad, "entry_ok": t_ok, "entry_bad": t_bad}
        check(f"ATLAS {k} a: {s_ok}/{len(ref)} 2026 research trades signalled from the bars up to the signal bar alone "
              f"(same side, same stop, no trade before the entry bar opens)", not s_bad, s_bad[:3])
        check(f"ATLAS {k} b: {t_ok}/{len(ref)} trades at the entry bar's close with the research entry / stop / target",
              not t_bad, t_bad[:3])
    out["seconds"] = round(time.time() - t0)
    return out


def main(argv):
    t0 = time.time()
    rep = {"what": "prefix invariance (A1 audit 2026-10-25)", "argv": argv}
    if "--atlas" not in argv:
        rep["lit"] = lit_part(raw1m="--full" in argv or "--raw1m" in argv)
    if "--lit" not in argv:
        rep["atlas"] = atlas_part()
    rep["checks"] = RESULTS
    rep["seconds"] = round(time.time() - t0)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, default=str)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed in {rep['seconds']}s -> {os.path.relpath(OUT, ROOT)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
