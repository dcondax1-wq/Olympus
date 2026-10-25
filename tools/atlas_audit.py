"""ATLAS pre-launch audit (2026-10-25, agent A3): evidence for research/handoff/2026-10-25/A3_atlas.md.

ATLAS = three INDEPENDENT setups pooled on account B (MFFU Builder 25K): ATLAS_LONDON_EMA (ema_lon_vix), ATLAS_MACD_SWEEP
(macd_sweep), ATLAS_NY_RECLAIM (sr_nyreclaim). Nothing here changes a rule, a default or second_model.json.

    python -X utf8 tools/atlas_audit.py probe     # live entry timing: every 2026 research trade re-derived the way
                                                  # engine/account_b.AccountB.entry does it (bars cut at the decision bar,
                                                  # a flat probe bar at the entry open, now = open + 2 s) and the fill check
                                                  # once the fill bar closed -> PROBE_CHECK.csv
    python -X utf8 tools/atlas_audit.py perf      # PERFORMANCE_BY_SETUP.csv, ATLAS_TRADE_LEDGER.csv, ATLAS_SIGNAL_LEDGER.csv,
                                                  # ROBUSTNESS_BY_SETUP.csv (alone at $500 + the account-B 25K routed path)
Paper research only.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "handoff", "2026-10-25")
ET = ZoneInfo("America/New_York")
TICK, PV, COMM = 0.25, 2.0, 1.90
KEYS = {"ema_lon_vix": "ATLAS_LONDON_EMA", "macd_sweep": "ATLAS_MACD_SWEEP", "sr_nyreclaim": "ATLAS_NY_RECLAIM"}
SRC2KEY = {"EMA": "ema_lon_vix", "MD": "macd_sweep", "SR": "sr_nyreclaim"}
REF = {"ema_lon_vix": "research/second/ema_best.json", "macd_sweep": "research/second/md_best.json",
       "sr_nyreclaim": "research/second/sr_best.json"}
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "2025": ("2025-01-01", "2025-12-31"),
         "2021-24": ("2021-11-01", "2024-12-31")}
LIT_COLS = ['day', 'entry_t', 'exit_t', 'dir', 'r', 'pnl', 'risk_pts', 'qty', 'risk_usd', 'half', 'exit', 'trigger', 'mfe', 'mae',
            'bars_held', 'regime', 'mult']
MARKET_EXITS = {"STOP", "BE", "FLAT", "T15", "CUT", "HEDGE", "PRE", "TIME"}


def et(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%Y-%m-%d %H:%M")


def ref_trades(k):
    return json.load(open(os.path.join(ROOT, REF[k]), encoding="utf-8"))["trades"]


def wcsv(name, rows, cols):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("wrote", os.path.join(OUT, name), len(rows), "rows", flush=True)


# ============================================================================================ 1. live entry timing / prefix
def probe(only=None):
    from engine import second
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] >= 1759000000].drop_duplicates("time").sort_values("time").reset_index(drop=True)   # 2025-09-27 on
    df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    df1 = df1[df1["time"] >= int(df5["time"].min())].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    cols = ["time", "open", "high", "low", "close", "volume"]
    df5, df1 = df5[cols], df1[cols]
    T5, T1 = df5["time"].values, df1["time"].values
    cfg = second.load_cfg()
    rows = []
    t0 = time.time()
    for k in KEYS:
        if only and k != only:
            continue
        sub = {**cfg, "strategies": {k: {**cfg["strategies"][k], "route": True}}}
        for w in ref_trades(k):
            if not ("2026-01-01" <= w["day"] <= "2026-10-16"):
                continue
            tb = int(w["entry_t"])
            # decision time: the signal bar (tb - 300) has closed; the probe runs 2 s after the entry bar's open
            c5 = df5.iloc[:int(np.searchsorted(T5, tb))]
            c1 = df1.iloc[:int(np.searchsorted(T1, tb))]
            i5 = int(np.searchsorted(T5, tb))
            real_open = float(df5["open"].iloc[i5]) if i5 < len(df5) and int(T5[i5]) == tb else float("nan")
            px = real_open
            bar = pd.DataFrame([{"time": tb, "open": px, "high": px, "low": px, "close": px, "volume": 1.0}])
            d5x = pd.concat([c5, bar], ignore_index=True)
            d1x = pd.concat([c1, bar], ignore_index=True) if len(c1) and int(c1["time"].max()) < tb else c1
            now = tb + 2
            r = second.run(d5x, one_min=d1x, now=now, cfg=sub, lit=[])
            s = r["strategies"][k]
            err = s.get("error")
            got = next((t for t in s.get("trades") or [] if int(t["entry_t"]) == tb and t.get("exit_kind") == "OPEN"
                        and t.get("target") is not None), None)
            # any trade of that day entered at another time (an early / late shift)?
            other = [t for t in s.get("trades") or [] if t["day"] == w["day"] and int(t["entry_t"]) != tb]
            # the fill check once the fill bar closed (AccountB.manage): real bars up to tb + 300, now = tb + 302
            f5 = df5.iloc[:int(np.searchsorted(T5, tb + 300))]
            f1 = df1.iloc[:int(np.searchsorted(T1, tb + 300))]
            r2 = second.run(f5, one_min=f1, now=tb + 302, cfg=sub, lit=[])
            s2 = r2["strategies"][k]
            fill = next((t for t in s2.get("trades") or [] if int(t["entry_t"]) == tb), None)
            row = {"setup_id": KEYS[k], "day": w["day"], "research_entry_t": tb, "research_entry_et": et(tb),
                   "decision_bar_et": et(tb - 300), "probe_now_et": et(tb) + ":02", "dir": int(w["dir"]),
                   "research_entry": w["entry"], "research_stop": w["stop"], "research_target": w.get("target"),
                   "probe_trade": bool(got), "probe_entry": got and got["entry"], "probe_stop": got and got["stop"],
                   "probe_target": got and got["target"], "probe_qty": got and got["qty"], "research_qty": w["qty"],
                   "fill_check_trade": bool(fill), "fill_entry": fill and fill["entry"],
                   "other_entries_that_day": ";".join(et(t["entry_t"]) for t in other), "error": err or s2.get("error") or ""}
            same = bool(got) and int(got["dir"]) == int(w["dir"]) and abs(float(got["stop"]) - float(w["stop"])) < 1e-6 \
                and abs(float(got["entry"]) - float(w["entry"])) < 1e-6 \
                and (w.get("target") is None or abs(float(got["target"]) - float(w["target"])) < 1e-6)
            row["offset_bars"] = 0 if got else ""
            row["verdict"] = "SAME_BAR_SAME_LEVELS" if same and fill else ("SAME_BAR_LEVELS_DIFFER" if got else "NOT_SEEN_AT_PROBE")
            rows.append(row)
        print(f"  {k}: {sum(1 for r in rows if r['setup_id'] == KEYS[k])} trades probed ({time.time() - t0:.0f}s)", flush=True)
    wcsv("PROBE_CHECK.csv" if not only else f"PROBE_CHECK_{only}.csv", rows, list(rows[0].keys()))
    c = collections.Counter((r["setup_id"], r["verdict"]) for r in rows)
    for kk, v in sorted(c.items()):
        print(" ", kk, v)
    return rows


WIN_OPEN = {"ema_lon_vix": ((180, 570),), "macd_sweep": ((120, 300), (570, 660)), "sr_nyreclaim": ((570, 720),)}


def scan(k, lo="2026-01-02", hi="2026-10-16"):
    """Every 5m open inside the setup's entry window of every session lo..hi, probed as AccountB.entry does (decision bar
    closed, flat probe bar at the real open, now = open + 2 s): which opens would the live bot route? Compared with the
    research trades: a live entry the research does not have (false positive), a research trade the live probe misses, or
    the same trade a bar early / late."""
    from engine import second
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] >= 1759000000].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    df1 = df1[df1["time"] >= int(df5["time"].min())].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    cols = ["time", "open", "high", "low", "close", "volume"]
    df5, df1 = df5[cols], df1[cols]
    T5, T1, O5 = df5["time"].values, df1["time"].values, df5["open"].values
    cfg = second.load_cfg()
    sub = {**cfg, "strategies": {k: {**cfg["strategies"][k], "route": True}}}
    ref = {int(t["entry_t"]): t for t in ref_trades(k) if lo <= t["day"] <= hi}
    et_ = pd.to_datetime(T5, unit="s", utc=True).tz_convert("America/New_York")
    mod = (et_.hour * 60 + et_.minute).values
    sday = (et_.tz_localize(None).normalize() + pd.to_timedelta((mod >= 1080).astype(int), unit="D")).strftime("%Y-%m-%d").values
    hits, rows = {}, []
    t0 = time.time()
    idx = [i for i in range(1, len(T5)) if lo <= sday[i] <= hi and any(a <= mod[i] < b for a, b in WIN_OPEN[k])]
    for n_, i in enumerate(idx):
        tb = int(T5[i])
        c5 = df5.iloc[:i]
        c1 = df1.iloc[:int(np.searchsorted(T1, tb))]
        px = float(O5[i])
        bar = pd.DataFrame([{"time": tb, "open": px, "high": px, "low": px, "close": px, "volume": 1.0}])
        d5x = pd.concat([c5, bar], ignore_index=True)
        d1x = pd.concat([c1, bar], ignore_index=True) if len(c1) and int(c1["time"].max()) < tb else c1
        s = second.run(d5x, one_min=d1x, now=tb + 2, cfg=sub, lit=[])["strategies"][k]
        got = next((t for t in s.get("trades") or [] if int(t["entry_t"]) == tb and t.get("exit_kind") == "OPEN"
                    and t.get("target") is not None), None)
        if got:
            hits[tb] = got
        if n_ % 500 == 0:
            print(f"  {k}: {n_}/{len(idx)} opens ({time.time() - t0:.0f}s), {len(hits)} live entries", flush=True)
    for tb in sorted(set(hits) | set(ref)):
        g, w = hits.get(tb), ref.get(tb)
        if g and w:
            v = "MATCH" if int(g["dir"]) == int(w["dir"]) and abs(g["stop"] - w["stop"]) < 1e-6 else "MATCH_TIME_LEVELS_DIFFER"
        elif g:
            near = [x for x in ref if abs(x - tb) <= 600]
            v = "LIVE_ONLY_SHIFTED" if near else "LIVE_ONLY_FALSE_POSITIVE"
        else:
            near = [x for x in hits if abs(x - tb) <= 600]
            v = "RESEARCH_ONLY_SHIFTED" if near else "RESEARCH_ONLY_MISSED"
        rows.append({"setup_id": KEYS[k], "entry_t": tb, "entry_et": et(tb), "verdict": v, "live_dir": g and g["dir"],
                     "research_dir": w and w["dir"], "live_stop": g and g["stop"], "research_stop": w and w["stop"]})
    wcsv(f"SCAN_{k}.csv" if (lo, hi) == ("2026-01-02", "2026-10-16") else f"SCAN_{k}_{lo}_{hi}.csv", rows, ["setup_id", "entry_t", "entry_et", "verdict", "live_dir", "research_dir", "live_stop", "research_stop"])
    print(k, len(idx), "opens probed", collections.Counter(r["verdict"] for r in rows), flush=True)


# ============================================================================================ 2. performance + ledgers
def sessions():
    r = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
    return [d[0] for d in r["days"]]


def stats(P, days_in_span, by_week_days=None):
    """P: list of (day, pnl). Returns the metrics row."""
    p = np.array([x[1] for x in P], float)
    n = len(p)
    weeks = collections.OrderedDict()
    for d in days_in_span:
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        weeks.setdefault((y, w), 0)
    for d, _ in P:
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        if (y, w) in weeks:
            weeks[(y, w)] += 1
    nw = max(1, len(days_in_span) / 5.0)
    o = {"trades": n, "net_pnl": round(float(p.sum()), 2) if n else 0.0}
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    o["PF"] = round(float(gw / gl), 2) if gl > 0 else (None if not n else "inf")
    o["positive_trade_rate"] = round(100.0 * (p > 0).sum() / n, 1) if n else None
    o["average_win"] = round(float(p[p > 0].mean()), 2) if (p > 0).any() else None
    o["average_loss"] = round(float(p[p < 0].mean()), 2) if (p < 0).any() else None
    eq = np.cumsum(p) if n else np.zeros(1)
    o["max_drawdown"] = round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()), 2) if n else 0.0
    o["weekly_frequency"] = round(n / nw, 2)
    o["weeks"] = len(weeks)
    o["zero_trade_weeks"] = sum(1 for v in weeks.values() if v == 0)
    o["weeks_2plus_pct"] = round(100.0 * sum(1 for v in weeks.values() if v >= 2) / max(1, len(weeks)), 1)
    o["per_month"] = round(float(p.sum()) / (len(days_in_span) / 21.0), 2) if days_in_span else None
    # tail concentration: share of the net made by the best 10% of trades (>100% = the rest loses money)
    if n and p.sum() > 0:
        top = np.sort(p)[::-1][:max(1, int(np.ceil(0.1 * n)))]
        o["tail_concentration"] = round(100.0 * float(top.sum()) / float(p.sum()), 1)
        o["net_ex_top3"] = round(float(p.sum() - np.sort(p)[::-1][:3].sum()), 2)
    else:
        o["tail_concentration"] = None
        o["net_ex_top3"] = round(float(p.sum() - np.sort(p)[::-1][:3].sum()), 2) if n else 0.0
    return o


def bars5():
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")).drop_duplicates("time").sort_values("time")
    return df["time"].values.astype(np.int64), df["high"].values, df["low"].values


def mfe_mae(t, B):
    """MFE / MAE in R from the 5m bars between the entry bar and the exit bar (5m resolution; stored trades only)."""
    T, H, L = B
    a = int(np.searchsorted(T, int(t["entry_t"])))
    z = int(np.searchsorted(T, int(t["exit_t"]))) if t.get("exit_t") else a + 1
    z = max(z, a + 1)
    risk = abs(float(t["entry"]) - float(t["stop"]))
    if risk <= 0:
        return None, None, 0
    d = int(t["dir"])
    hi, lo = H[a:z].max(), L[a:z].min()
    fav = (hi - float(t["entry"])) if d > 0 else (float(t["entry"]) - lo)
    adv = (float(t["entry"]) - lo) if d > 0 else (hi - float(t["entry"]))
    return round(fav / risk, 3), round(max(0.0, adv) / risk, 3), z - a


def alone_ledger(B):
    out = []
    for k, sid in KEYS.items():
        for t in ref_trades(k):
            if t["day"] > "2026-10-16":
                continue
            risk = abs(float(t["entry"]) - float(t["stop"]))
            mf, ma, nb = mfe_mae(t, B)
            out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
                        "r": t["r"], "pnl": t["pnl_usd"], "risk_pts": round(risk, 2), "qty": int(t["qty"]),
                        "risk_usd": round(risk * PV * int(t["qty"]), 2), "half": False, "exit": str(t["exit_kind"]).upper(),
                        "trigger": t.get("setup"), "mfe": mf, "mae": ma, "bars_held": nb, "regime": "", "mult": 1.0,
                        "setup_id": sid, "book": "ALONE_USD500", "label": "BASELINE", "entry_et": et(t["entry_t"]),
                        "exit_et": et(t["exit_t"]), "entry_px": t["entry"], "stop_px": t["stop"], "target_px": t.get("target"),
                        "exit_px": t["exit"]})
    return sorted(out, key=lambda r: (r["entry_t"], r["setup_id"]))


# ---- account B routed path (tools/second_account_b.py executor, logged)
def acctb_path(span):
    """Back-to-back eval path on the Builder 25K with the live sizing (engine/account_b.qty "need"), no hedge vs LIT's
    account, max 2 a day, one position, the soft daily loss, the stuck rule; a new eval right after a pass / fail / stuck.
    Returns (taken records, signal log)."""
    from tools import second_account_b as SB
    M = SB.M
    from engine import account_b as AB
    with SB.Plan("builder25k"):
        q0 = M.second_q
        zero = {}
        spec = AB.normalize({"account": "research", "plan": "builder25k", "eval_start": "2026-01-02"}, lit_account=None)

        def second_q(t, st, rule):          # the executor's own size call, logged when it says 0 (why)
            q = q0(t, st, rule)
            if q <= 0:
                r = AB.qty({**spec, "sizing": "need"}, {"risk_pts": t["risk"], "tgt_pts": t["tgt"]}, dict(st))
                zero[(t["src"], t["entry_t"])] = "; ".join(str(x) for x in r["reasons"][-2:])[:200] + \
                    f" (room ${st['room']:,.0f}, day ${st['cum']:,.0f}, session {st['session']})"
            return q
        M.second_q = second_q
        allU = [t for nm in ("EMA", "MD", "SR") for t in M.units()[nm]]
        hedged = {(t["src"], t["entry_t"]): t for t in M.no_hedge(allU)}
        sig = []
        U = []
        for t in allU:
            h = hedged.get((t["src"], t["entry_t"]))
            if h is None:
                sig.append({**t, "reason": "VETO_HEDGE_LIT_OPPOSITE_OPEN"})
                continue
            if h.get("exit") == "HEDGE":
                sig.append({**t, "reason": "TAKEN_BUT_CLOSED_AT_LIT_OPPOSITE_ENTRY", "_cut": True})
            U.append(h)
        by = M.by_day(U)
        a, z = SPANS[span]
        S = [d for d in M.units()["sessions"] if a <= d <= z]
        T = []
        k = 0
        res = collections.Counter()
        evn = 0
        while k < len(S):
            evn += 1
            keep = []
            r, used, _ = SB.run_eval(S[k:], by, "acctb_need", len(S) - k, keep=keep)
            for x in keep:
                x["eval_no"] = evn
                x["eval_result"] = r
            T.extend(keep)
            res[r] += 1
            if r == "OPEN":
                break
            k += used
        taken = {(x["src"], x["entry_t"]) for x in T}
        # why each other candidate of the span was not taken (re-derived with the executor's own rules, in its order)
        Tby = collections.defaultdict(list)
        for x in T:
            Tby[x["day"]].append(x)
        for t in U:
            if not (a <= t["day"] <= z):
                continue
            if (t["src"], t["entry_t"]) in taken:
                continue
            day = Tby.get(t["day"], [])
            prior = [x for x in day if x["entry_t"] <= t["entry_t"]]
            if any(x["entry_t"] <= t["entry_t"] < x["exit_t"] for x in day):
                why = "VETO_ONE_POSITION_BUSY"
            elif len(prior) >= 2:
                why = "VETO_MAX_2_PER_DAY"
            elif sum(x["pnl"] for x in prior) <= -M.DLL:
                why = "VETO_SOFT_DAILY_LOSS_HIT"
            elif (t["src"], t["entry_t"]) in zero:
                z_ = zero[(t["src"], t["entry_t"])]
                why = "VETO_SIZE_0: " + z_
            else:
                why = "VETO_NO_EVAL_RUNNING_THAT_DAY"   # the day fell after a pass / fail / stuck inside the same session
            sig.append({**t, "reason": why})
        sig = [s for s in sig if a <= s["day"] <= z]
        return T, sig, res


def perf():
    B = bars5()
    S = sessions()
    alone = alone_ledger(B)
    rows = []
    span_days = {sp: [d for d in S if a <= d <= z] for sp, (a, z) in SPANS.items()}
    for sp, (a, z) in SPANS.items():
        for sid in list(KEYS.values()) + ["ATLAS_POOLED_ALONE"]:
            P = [(t["day"], float(t["pnl"])) for t in alone if a <= t["day"] <= z and (sid == "ATLAS_POOLED_ALONE" or t["setup_id"] == sid)]
            rows.append({"setup_id": sid, "book": "ALONE_USD500 (each setup at $500 price risk, no interaction)", "span": sp,
                         "label": "BASELINE", **stats(P, span_days[sp])})
    led = list(alone)
    siglog = []
    for sp in SPANS:
        T, sig, res = acctb_path(sp)
        P = [(x["day"], float(x["pnl"])) for x in T]
        rows.append({"setup_id": "ATLAS_ACCOUNT_B_25K", "book": "ROUTED account B Builder 25K need size, back-to-back evals", "span": sp,
                     "label": "BASELINE", **stats(P, span_days[sp]),
                     "evals_pass_fail_stuck_open": f"{res['PASS']}/{res['FAIL']}/{res['STUCK']}/{res['OPEN']}"})
        for src in ("EMA", "MD", "SR"):
            P2 = [(x["day"], float(x["pnl"])) for x in T if x["src"] == src]
            rows.append({"setup_id": KEYS[SRC2KEY[src]], "book": "ROUTED account B Builder 25K (this setup's share)", "span": sp,
                         "label": "BASELINE", **stats(P2, span_days[sp])})
        for x in T:
            sid = KEYS[SRC2KEY[x["src"]]]
            led.append({"day": x["day"], "entry_t": int(x["entry_t"]), "exit_t": int(x["exit_t"]), "dir": int(x["dir"]),
                        "r": round((x["pnl"]) / (x["risk"] * PV * x["qty"]), 4) if x["qty"] else None, "pnl": x["pnl"],
                        "risk_pts": x["risk"], "qty": x["qty"], "risk_usd": x["risk_usd"], "half": False, "exit": str(x["exit"]).upper(),
                        "trigger": x["src"], "mfe": None, "mae": round(-x["low"] / (x["risk"] * PV * x["qty"]), 3) if x["qty"] else None,
                        "bars_held": None, "regime": "", "mult": 1.0, "setup_id": sid, "book": "ACCTB_25K_NEED",
                        "label": "BASELINE", "entry_et": et(x["entry_t"]), "exit_et": et(x["exit_t"]),
                        "eval_no": f"{sp}#{x['eval_no']}", "eval_result": x["eval_result"]})
        for s in sig:
            siglog.append({"span": sp, "day": s["day"], "setup_id": KEYS[SRC2KEY[s["src"]]], "entry_t": int(s["entry_t"]),
                           "entry_et": et(s["entry_t"]), "dir": int(s["dir"]), "risk_pts": s["risk"], "research_exit": s["exit"],
                           "research_R_per_micro_pts": s["pts"], "reason": s["reason"], "book": "ACCTB_25K_NEED"})
        print(f"  account B {sp}: {len(T)} trades, {res}", flush=True)
    cols = ["setup_id", "book", "span", "label", "trades", "net_pnl", "PF", "positive_trade_rate", "average_win", "average_loss",
            "max_drawdown", "weekly_frequency", "zero_trade_weeks", "weeks", "weeks_2plus_pct", "tail_concentration", "net_ex_top3",
            "per_month", "evals_pass_fail_stuck_open"]
    wcsv("PERFORMANCE_BY_SETUP.csv", rows, cols)
    wcsv("ATLAS_TRADE_LEDGER.csv", led, LIT_COLS + ["setup_id", "book", "label", "entry_et", "exit_et", "entry_px", "stop_px",
                                                   "target_px", "exit_px", "eval_no", "eval_result"])
    # research-level rejections the stored ledgers already exclude (candidates that never became a trade)
    siglog += research_rejections()
    wcsv("ATLAS_SIGNAL_LEDGER.csv", siglog, ["span", "day", "setup_id", "entry_t", "entry_et", "dir", "risk_pts", "research_exit",
                                            "research_R_per_micro_pts", "reason", "book"])
    robust(alone, span_days)


def research_rejections():
    """EMA: every CISD candidate of 2026 that passed the setup mask but was not the trade (reason codes). MACD / S/R: the
    candidates the generators produced in 2026 that the selection dropped."""
    out = []
    from tools import second_ema as SE
    from engine import second
    cfg = second.load_cfg()["strategies"]
    E, X = cfg["ema_lon_vix"]["entry"], cfg["ema_lon_vix"]["exit"]
    d = SE.load()
    df = SE.candidates()
    m = SE.entry_mask(df, E) & (df["day"].values >= "2026-01-01") & (df["day"].values <= "2026-10-16")
    taken = {int(t["entry_t"]) for t in ref_trades("ema_lon_vix")}
    seen = set()
    for j in np.flatnonzero(m):
        row = df.iloc[j]
        t_ = int(d["t"][int(row["ei"])])
        if t_ in taken:
            seen.add(row["day"])
            continue
        if row["day"] in seen:
            why = "REJECT_ONE_PER_DAY"
        else:
            why = "REJECT_NO_VALID_EXIT_OR_TARGET_UNDER_1.5R" if SE.simulate(row, X, d) is None else "REJECT_OTHER"
        out.append({"span": "2026", "day": row["day"], "setup_id": "ATLAS_LONDON_EMA", "entry_t": t_, "entry_et": et(t_),
                    "dir": int(row["dir"]), "risk_pts": round(float(row["risk"]), 2), "reason": why, "book": "RESEARCH_SELECTION"})
    return out


def robust(alone, span_days):
    """Per setup alone at $500: +1/+2/+4 ticks on every market fill (entry + market exits; target limits none), fee +$0.50 a
    micro round trip, top winners removed; 1 bar late from research/second/robust.json (the research code re-run)."""
    rb = json.load(open(os.path.join(ROOT, "research", "second", "robust.json"), encoding="utf-8"))
    late = rb["tests"]["late1"]["alone"]
    nm = {"ATLAS_LONDON_EMA": "EMA", "ATLAS_MACD_SWEEP": "MD", "ATLAS_NY_RECLAIM": "SR"}
    rows = []
    for sp, (a, z) in SPANS.items():
        for sid in list(KEYS.values()) + ["ATLAS_POOLED_ALONE"]:
            T = [t for t in alone if a <= t["day"] <= z and (sid == "ATLAS_POOLED_ALONE" or t["setup_id"] == sid)]
            base = stats([(t["day"], float(t["pnl"])) for t in T], span_days[sp])

            def add(test, P, note=""):
                s = stats(P, span_days[sp])
                rows.append({"setup_id": sid, "span": sp, "test": test, "label": "RESEARCH_VARIANT" if test != "base" else "BASELINE",
                             "trades": s["trades"], "net_pnl": s["net_pnl"], "PF": s["PF"], "positive_trade_rate": s["positive_trade_rate"],
                             "max_drawdown": s["max_drawdown"],
                             "kept_pct": round(100.0 * s["net_pnl"] / base["net_pnl"], 1) if base["net_pnl"] else None, "note": note})
            add("base", [(t["day"], float(t["pnl"])) for t in T])
            for k in (1, 2, 4):
                P = []
                for t in T:
                    fills = 1 + (1 if t["exit"] in MARKET_EXITS else 0)
                    P.append((t["day"], float(t["pnl"]) - t["qty"] * k * TICK * PV * fills))
                add(f"slip_plus{k}tick", P, "k extra ticks against on the market entry and on every market exit (stop/BE/cut/flat); target limits none; qty unchanged")
            add("fee_plus_0.50", [(t["day"], float(t["pnl"]) - 0.5 * t["qty"]) for t in T], "+$0.50 a micro round trip")
            srt = sorted(T, key=lambda t: -float(t["pnl"]))
            for nrm in (1, 3):
                drop = {id(x) for x in srt[:nrm]}
                add(f"top{nrm}_winners_removed", [(t["day"], float(t["pnl"])) for t in T if id(t) not in drop])
            drop = {id(x) for x in srt[:max(1, int(np.ceil(0.1 * len(T))))]}
            add("top10pct_winners_removed", [(t["day"], float(t["pnl"])) for t in T if id(t) not in drop])
            if sid in nm:
                L = late[nm[sid]][sp]
                rows.append({"setup_id": sid, "span": sp, "test": "late_1bar (stress, research code re-run)", "label": "RESEARCH_VARIANT",
                             "trades": int(L["n"]), "net_pnl": L["net"], "PF": L["pf"], "positive_trade_rate": None, "max_drawdown": None,
                             "kept_pct": L["kept"], "note": "research/second/robust.json tests.late1 (tools/second_robust.py): every entry 1 5m bar later"})
    wcsv("ROBUSTNESS_BY_SETUP.csv", rows, ["setup_id", "span", "test", "label", "trades", "net_pnl", "PF", "positive_trade_rate",
                                           "max_drawdown", "kept_pct", "note"])


def evals(min_room=None):
    """tools/second_account_b.score on the Builder 25K need size as of today's code (sizing caps of 2026-10-24 in):
    2-week / 1-month pass / fail / stuck with a fresh eval every session + the back-to-back path -> EVAL_25K_NOW.csv,
    next to research/second/atlas.json (what the dashboard shows). min_room (RESEARCH_VARIANT): the stuck threshold
    (live engine/account_b.MIN_ROOM = $100) raised, i.e. buy a new eval earlier."""
    from tools import second_account_b as SB
    M = SB.M
    if min_room is not None:
        SB.MIN_ROOM = float(min_room)
    at = json.load(open(os.path.join(ROOT, "research", "second", "atlas.json"), encoding="utf-8"))
    nmap = {"H1": "H1", "H2": "H2", "2025": "y2025", "2021-24": "y2124"}
    rows = []
    with SB.Plan("builder25k") as pl:
        U = M.acct_units(("EMA", "MD", "SR"), nohedge=True)
        for sp in SPANS:
            o, T = SB.score(U, "acctb_need", sp, pl.safe_rule)
            a = at["eval25k"].get(nmap[sp], {})
            b = at["numbers"].get(nmap[sp], {})
            rows.append({"span": sp, "label": "BASELINE" if min_room is None else f"RESEARCH_VARIANT stuck<${min_room}",
                         "evals_bought": o.get("evals_bought"), **{k: o.get(k) for k in ("p10", "f10", "s10", "dec10", "p15", "f15", "p20", "f20",
                                                                                    "s20", "pass_med", "slow_pass", "p60", "f60", "n", "tpw",
                                                                                    "net", "per_month", "dd", "pf", "b2b", "path_net_less_fees",
                                                                                    "med_qty", "med_risk", "max_risk")},
                         "atlas_json_p10": a.get("p10"), "atlas_json_f10": a.get("f10"), "atlas_json_s10": a.get("s10"),
                         "atlas_json_net": b.get("net"), "atlas_json_pf": b.get("pf")})
            print(sp, rows[-1], flush=True)
    wcsv("EVAL_25K_NOW.csv" if min_room is None else f"EVAL_25K_STUCK{int(min_room)}.csv", rows, list(rows[0].keys()))


if __name__ == "__main__":
    a = sys.argv[1:] or ["perf"]
    if a[0] == "probe":
        probe(a[1] if len(a) > 1 else None)
    elif a[0] == "evals":
        evals(float(a[1]) if len(a) > 1 else None)
    elif a[0] == "scan":
        scan(a[1], *a[2:4])
    elif a[0] == "perf":
        perf()
