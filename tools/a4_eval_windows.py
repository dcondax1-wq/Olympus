"""Pre-launch audit A4 (2026-10-25): MFFU evaluation windows for LIT on the Builder 50K and ATLAS on the Builder 25K.

"Two weeks" = 10 trading sessions (TradingView CME sessions, 18:00-17:00 ET; holiday Globex sessions count as sessions).
A window starts at one session and runs at most 10 sessions, never past the end of its half (H1 = 2026-01-02..06-30,
H2 = 07-01..10-16): a window that cannot see 10 sessions is marked full_window=0 and is left out of the rates.
Two window sets per starting state:
  rolling  one window per session start (they OVERLAP: neighbouring starts share up to 9 sessions and the same few big
           winning days, so they are not independent trials; overlap_group = the non-overlapping block the start falls in)
  block    non-overlapping 10-session blocks from the first session of each half (independent in time)

Starting states:
  A_fresh        a new eval on every start (LIT: Builder 50K $0 profit, floor -$2,000; ATLAS: Builder 25K, floor -$1,000)
  B_owner        LIT only: the owner's real 50K on 2026-10-25 (balance $49,710.80, floor $48,168.20, need $3,289.20, i.e.
                 profit -$289.20, EOD high $50,168.20), started at each 2026 session with the eval clock at session 6
                 (eval_start 2026-10-19: two_week sizing for sessions 6-10, then safe_eval)
  C_fresh        LIT 50K + ATLAS 25K side by side from the same start, the live router rules (engine/live.py +
                 engine/account_b.py): LIT priority; an ATLAS entry is blocked while LIT holds, enters or has an ARMED setup
                 (limit working / waiting for its 1m CISD) in the other direction; an open ATLAS trade is closed at market
                 (HEDGE, 1 tick) when LIT enters the other way; same direction allowed; ATLAS one position, max 2 a day,
                 member priority EMA > MACD > S/R on the same bar (tools/atlas.account_units)
  C_owner        as C_fresh with LIT at the owner's snapshot (B_owner) and a fresh ATLAS 25K (tonight's real choice)

Rules (research/lit/mffu_rules.json, help center 2026-10-24): 50K target $3,000, EOD trailing max loss $2,000 locked at
start + $100, soft daily loss $1,000 (pause the day, not a breach), 40 micros; 25K $1,500 / $1,000 / $600 / 20 micros;
MNQ $1.90 round trip + 1 tick on market entries and stop / BE / time exits.
Equity treatment: the trailing floor moves only on END-OF-DAY balances (MFFU EOD trailing); a breach is checked INTRADAY
against each trade's worst open point (1m bars in 2026, capped at the stop + 1 tick) on top of the day's closed P&L, and
against the EOD balance. A trade whose worst point would cross the soft daily loss is cut there (pause, not breach). Pass =
EOD balance >= target (no 2nd-day minimum: MFFU's minimum days is recorded as "conflict"). Stuck = not passed and room
(balance - floor) below $200 (LIT 50K, engine/eval_life STUCK push) / $100 (ATLAS 25K, engine/account_b MIN_ROOM): the bot
stops trading it, the owner must buy a new one.
Sizing = what the live bot routes: LIT engine/sizing.lit_qty on the full live_model.json lit_sizing (two_week, room_f 0.55,
soft daily loss cap, wk_loss_usd 1200 with the eval's ISO-week P&L, after session 10 safe_eval); ATLAS engine/account_b.qty
"need" on the 25K preset (tools/atlas.q_variant BASE). Trades = the live LIT replay (run lit_live settings, 120 trades in
2026) and the stored EMA / MACD / S/R research trades (tools/second_mix units).

    python -X utf8 tools/a4_eval_windows.py     # -> research/handoff/2026-10-25/EVALUATION_WINDOWS.csv + summaries (~1 min)
Paper research only: reads live_model.json / second_model.json, writes nothing else.
"""
from __future__ import annotations

import collections
import copy
import csv
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import second_mix as M  # noqa: E402
from tools import atlas as AT  # noqa: E402

OUTD = os.path.join(ROOT, "research", "handoff", "2026-10-25")
H = 10                                         # two weeks = 10 trading sessions
HALVES = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31")}
_LS = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
LIT_CFG = {k: copy.deepcopy(v) for k, v in _LS.items() if k not in ("eval_start", "eval_prior_pnl", "eval_prior_note", "note",
                                                                    "modes", "eval_mode_note", "funded")}
LIT_CFG["mode"] = "two_week"
OWNER = {"balance": 49710.80, "floor": 48168.20, "start": 50000.0}
OWNER_SESSION0 = SZ.eval_session("2026-10-19", "2026-10-26") - 1      # 5 sessions done: the next one is session 6
PLAN = {"LIT 50K": {"tgt": 3000.0, "mll": 2000.0, "dll": 1000.0, "lock": 100.0, "stuck": 200.0, "maxq": 40},
        "ATLAS 25K": {"tgt": 1500.0, "mll": 1000.0, "dll": 600.0, "lock": 100.0, "stuck": 100.0, "maxq": 20}}
PROFILE = {
    "LIT 50K": "MFFU Builder 50K: target 3000, EOD trailing MLL 2000 locked at +100, soft DLL 1000 (pause), 40 micros; "
               "intraday worst-point breach check, EOD trail; LIT live sizing two_week room_f 0.55 + DLL cap + wk_loss 1200, "
               "safe_eval after session 10; $1.90 RT + 1 tick; stuck if room < 200",
    "ATLAS 25K": "MFFU Builder 25K: target 1500, EOD trailing MLL 1000 locked at +100, soft DLL 600 (pause), 20 micros; "
                 "intraday worst-point breach check, EOD trail; account_b need sizing (25K preset, 50% room, day guard, "
                 "safe_eval 30% after session 10); max 2 a day, one position; $1.90 RT + 1 tick; stuck if room < 100",
}
DRIFT = SZ.TW_COMM - lit.COMM                 # engine/lit.py books routed LIT P&L at $1.40 a micro, MFFU charges $1.90
COLS = ["window_start", "window_end", "starting_state", "overlap_group", "result", "time_to_pass", "min_headroom",
        "largest_daily_loss", "rule_profile", "account", "half", "window_kind", "full_window", "sessions", "trades", "net",
        "worst_intraday_day", "paired_result", "booked_comm_drift"]


def sessions():
    return [d for d in M.units()["sessions"] if "2026-01-01" <= d <= "2026-12-31"]


def half_days(h):
    a, z = HALVES[h]
    return [d for d in sessions() if a <= d <= z]


# ================================================================================================ units
def lit_units():
    return [t for t in M.units()["LIT"] if t["day"] >= "2026-01-01"]


def atlas_units(hedge):
    """ATLAS members EMA + MACD + S/R in member priority; hedge=True: the live no-opposite rules vs LIT (armed included)."""
    V = AT.BASE
    U = []
    for nm in V["members"]:
        U += AT.member_units(nm, V)
    pr = {nm: i for i, nm in enumerate(V["members"])}
    U = sorted(U, key=lambda t: (t["entry_t"], pr.get(t["src"], 9)))
    U = AT.no_hedge_real(U, True) if hedge else U
    return [t for t in U if t["day"] >= "2026-01-01"]


# ================================================================================================ one window
def run_window(days, by, acct, start=None, sess0=0):
    """One eval over days[:H]. start = (bal, floor, peak) in profit space (None = fresh). Returns a dict (result, ...)."""
    P = PLAN[acct]
    bal, floor, peak = start if start is not None else (0.0, -P["mll"], 0.0)
    head = bal - floor
    worst_day = worst_intra = 0.0
    wk = collections.defaultdict(float)
    dtr, ntr, recs_all = 0, 0, []
    res, used = "unfinished", min(len(days), H)
    for kk, day in enumerate(days[:H]):
        extra = {"wk_pnl": wk[lit.iso_week(day)], "days_traded": dtr}
        if acct == "LIT 50K":
            cum, recs, failed = M.play_day(by.get(day, ()), day, bal, floor, sess0 + kk + 1, "usd500", False, 2, None,
                                           litcfg=LIT_CFG, dll=P["dll"], reserve=False, extra=extra)
        else:
            cum, recs, failed = M.play_day(by.get(day, ()), day, bal, floor, sess0 + kk + 1, "atlas", False, 2, None,
                                           reserve=False, extra=extra)
        c = 0.0
        for r in recs:
            head = min(head, bal + c + r["low"] - floor)
            worst_intra = min(worst_intra, c + r["low"])
            c += r["pnl"]
        recs_all += recs
        ntr += len(recs)
        if failed:
            res, used = "breach", kk + 1
            worst_day = min(worst_day, c)
            break
        bal += cum
        wk[lit.iso_week(day)] += cum
        worst_day = min(worst_day, cum)
        dtr += 1 if recs else 0
        head = min(head, bal - floor)
        if bal <= floor:
            res, used = "breach", kk + 1
            break
        peak = max(peak, bal)
        floor = min(max(floor, peak - P["mll"]), P["lock"])
        if bal >= P["tgt"]:
            res, used = "pass", kk + 1
            break
        if bal - floor < P["stuck"]:
            res, used = "stuck", kk + 1
            break
    return {"result": res, "used": used, "min_headroom": round(head, 2), "largest_daily_loss": round(worst_day, 2),
            "worst_intraday_day": round(worst_intra, 2), "trades": ntr, "net": round(sum(r["pnl"] for r in recs_all), 2),
            "drift": round(DRIFT * sum(r["qty"] for r in recs_all), 2) if acct == "LIT 50K" else 0.0,
            "recs": recs_all}


def owner_start():
    b = OWNER["balance"] - OWNER["start"]
    f = OWNER["floor"] - OWNER["start"]
    return (round(b, 2), round(f, 2), round(f + PLAN["LIT 50K"]["mll"], 2))


# ================================================================================================ all windows
def windows():
    byL = M.by_day(lit_units())
    byA0 = M.by_day(atlas_units(False))
    byA1 = M.by_day(atlas_units(True))
    rows, paths = [], collections.defaultdict(list)
    for h in HALVES:
        S = half_days(h)
        starts = {"rolling": list(range(len(S))), "block": list(range(0, len(S), H))}
        for kind, ix in starts.items():
            for i in ix:
                days = S[i:i + H]
                full = len(days) >= H
                grp = f"{h}-blk{i // H:02d}"
                jobs = [("A_fresh", "LIT 50K", byL, None, 0), ("B_owner", "LIT 50K", byL, owner_start(), OWNER_SESSION0)]
                with AT.Plan(AT.BASE):
                    a0 = run_window(days, byA0, "ATLAS 25K")
                    a1 = run_window(days, byA1, "ATLAS 25K")
                out = {}
                for st, acct, by, s0, ss in jobs:
                    out[(st, acct)] = run_window(days, by, acct, s0, ss)
                out[("A_fresh", "ATLAS 25K")] = a0
                out[("C_fresh", "LIT 50K")] = out[("A_fresh", "LIT 50K")]
                out[("C_fresh", "ATLAS 25K")] = a1
                out[("C_owner", "LIT 50K")] = out[("B_owner", "LIT 50K")]
                out[("C_owner", "ATLAS 25K")] = a1
                for (st, acct), o in out.items():
                    pair = ""
                    if st.startswith("C_"):
                        other = out[(st, "ATLAS 25K" if acct == "LIT 50K" else "LIT 50K")]
                        lr, ar = (o, other) if acct == "LIT 50K" else (other, o)
                        pair = f"LIT {lr['result']} / ATLAS {ar['result']}"
                    rows.append({"window_start": days[0], "window_end": days[o["used"] - 1], "starting_state": st,
                                 "overlap_group": grp, "result": o["result"],
                                 "time_to_pass": o["used"] if o["result"] == "pass" else "",
                                 "min_headroom": o["min_headroom"], "largest_daily_loss": o["largest_daily_loss"],
                                 "rule_profile": PROFILE[acct], "account": acct, "half": h, "window_kind": kind,
                                 "full_window": int(full), "sessions": o["used"], "trades": o["trades"], "net": o["net"],
                                 "worst_intraday_day": o["worst_intraday_day"], "paired_result": pair,
                                 "booked_comm_drift": o["drift"]})
                    if kind == "rolling" and st in ("A_fresh", "C_fresh") and full:
                        paths[(st, acct, h)].append((days[0], o["recs"]))
    return rows, paths


def summarize(rows):
    out = []
    keyf = lambda r: (r["starting_state"], r["account"], r["half"], r["window_kind"])
    G = collections.defaultdict(list)
    for r in rows:
        G[keyf(r)].append(r)
    for k in sorted(G):
        R = [r for r in G[k] if r["full_window"]]
        n = len(R) or 1
        c = collections.Counter(r["result"] for r in R)
        tp = [r["time_to_pass"] for r in R if r["result"] == "pass"]
        win_end = {r["window_end"] for r in R if r["result"] == "pass"}
        o = {"starting_state": k[0], "account": k[1], "half": k[2], "window_kind": k[3], "starts_all": len(G[k]),
             "full_windows": len(R), "pass_pct": round(100 * c["pass"] / n, 1), "breach_pct": round(100 * c["breach"] / n, 1),
             "stuck_pct": round(100 * c["stuck"] / n, 1), "unfinished_pct": round(100 * c["unfinished"] / n, 1),
             "pass_le5_pct": round(100 * sum(1 for x in tp if x <= 5) / n, 1),
             "pass_med_sessions": float(np.median(tp)) if tp else "", "distinct_pass_days": len(win_end),
             "min_headroom": min((r["min_headroom"] for r in R), default=""),
             "worst_daily_loss": min((r["largest_daily_loss"] for r in R), default=""),
             "worst_intraday_day": min((r["worst_intraday_day"] for r in R), default=""),
             "max_booked_comm_drift": max((r["booked_comm_drift"] for r in R), default="")}
        if k[0].startswith("C_") and k[1] == "LIT 50K":
            pr = collections.Counter(r["paired_result"] for r in R)
            o["both_pass_pct"] = round(100 * pr["LIT pass / ATLAS pass"] / n, 1)
            o["any_breach_pct"] = round(100 * sum(v for p_, v in pr.items() if "breach" in p_) / n, 1)
        out.append(o)
    return out


def hedge_check(paths):
    """Router invariant on the simulated C paths: no ATLAS 25K position open in the opposite direction of a LIT signal's
    trade (every LIT signal counted, routed or not) or inside an opposite LIT armed window at its entry."""
    from tools import atlas_lit_armed as ARM
    byL = collections.defaultdict(list)
    for t in lit_units():
        byL[t["day"]].append(t)
    AW = ARM.by_day()
    bad, n = [], 0
    for (st, acct, h), P in paths.items():
        if st != "C_fresh" or acct != "ATLAS 25K":
            continue
        for _, recs in P:
            for r in recs:
                n += 1
                for x in byL.get(r["day"], ()):
                    if x["dir"] != r["dir"] and x["entry_t"] < r["exit_t"] and r["entry_t"] < x["exit_t"]:
                        bad.append(("overlap", r["day"], r["entry_t"], r["src"]))
                for d, a, z in AW.get(r["day"], ()):
                    if d != r["dir"] and a <= r["entry_t"] < z:
                        bad.append(("armed", r["day"], r["entry_t"], r["src"]))
    return {"atlas_trades_checked": n, "violations": len(bad), "examples": bad[:5]}


def reproduce_check():
    """LIT alone, A_fresh rolling, 2-week pass/fail over full windows == research/hq/switch.json c22+r55+wk12 (published)."""
    pub = json.load(open(os.path.join(ROOT, "research", "hq", "switch.json"), encoding="utf-8"))["combos"]["c22+r55+wk12"]["eval"]
    return {h: {"published_p10_f10": [pub[h]["p10"], pub[h]["f10"]]} for h in HALVES}


# ================================================================================================ commission drift ($1.40 vs $1.90)
def run_window_booked(days, by, start=None, sess0=0):
    """LIT 50K window where the BOT's book (sizing state: profit, cum, room, week P&L, its soft-loss pause) uses P&L at
    engine/lit.py's $1.40 a micro, while the broker's account (breach / pass / stuck) is charged MFFU's $1.90. = what
    happens live until the eval anchor (broker balance + floor) is refreshed."""
    P = PLAN["LIT 50K"]
    bal, floor, peak = start if start is not None else (0.0, -P["mll"], 0.0)
    tb, tf, tp = bal, floor, peak                          # true (broker) book
    wk = collections.defaultdict(float)
    old = M.ECOMM
    M.ECOMM = lit.COMM
    try:
        for kk, day in enumerate(days[:H]):
            cum, recs, _ = M.play_day(by.get(day, ()), day, bal, floor, sess0 + kk + 1, "usd500", False, 2, None,
                                      litcfg=LIT_CFG, dll=P["dll"], reserve=False, extra={"wk_pnl": wk[lit.iso_week(day)]})
            c = 0.0
            for r in recs:
                d = DRIFT * r["qty"]
                if tb + c + r["low"] - d <= tf:
                    return "breach", kk + 1
                c += r["pnl"] - d
            bal += cum
            wk[lit.iso_week(day)] += cum
            peak = max(peak, bal)
            floor = min(max(floor, peak - P["mll"]), P["lock"])
            tb += c
            if tb <= tf:
                return "breach", kk + 1
            tp = max(tp, tb)
            tf = min(max(tf, tp - P["mll"]), P["lock"])
            if tb >= P["tgt"]:
                return "pass", kk + 1
            if tb - tf < P["stuck"]:
                return "stuck", kk + 1
    finally:
        M.ECOMM = old
    return "unfinished", min(len(days), H)


def commission_drift(rows):
    from tools import runlib as rl
    r = rl.load("lit_live")
    C = r["trade_cols"]
    T = [dict(zip(C, x)) for x in r["trades"] if x[0] >= "2026-01-01"]
    with open(os.path.join(OUTD, "COMMISSION_DRIFT.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["day", "entry_t", "exit", "qty", "pnl_booked_1.40", "pnl_mffu_1.90", "drift"])
        for t in T:
            w.writerow([t["day"], t["entry_t"], t["exit"], t["qty"], t["pnl"], round(t["pnl"] - DRIFT * t["qty"], 2),
                        round(-DRIFT * t["qty"], 2)])
    out = {"lit_live_2026": {"trades": len(T), "micros": sum(t["qty"] for t in T),
                             "booked_net": round(sum(t["pnl"] for t in T)),
                             "mffu_net": round(sum(t["pnl"] - DRIFT * t["qty"] for t in T)),
                             "drift_total": round(DRIFT * sum(t["qty"] for t in T), 2),
                             "drift_max_trade": round(DRIFT * max(t["qty"] for t in T), 2),
                             "drift_per_month": round(DRIFT * sum(t["qty"] for t in T) / (206 / 21), 2)}}
    for h in HALVES:
        TT = [t for t in T if HALVES[h][0] <= t["day"] <= HALVES[h][1]]
        out["lit_live_2026"][h] = {"booked": round(sum(t["pnl"] for t in TT)),
                                   "mffu": round(sum(t["pnl"] - DRIFT * t["qty"] for t in TT)),
                                   "pf_mffu": round(sum(t["pnl"] - DRIFT * t["qty"] for t in TT if t["pnl"] - DRIFT * t["qty"] > 0)
                                                    / -sum(t["pnl"] - DRIFT * t["qty"] for t in TT if t["pnl"] - DRIFT * t["qty"] < 0), 2)}
    # eval path: per-window drift (two_week sizes) and whether a $1.40 book flips any window's result
    R = [x for x in rows if x["account"] == "LIT 50K" and x["window_kind"] == "rolling" and x["full_window"]
         and x["starting_state"] in ("A_fresh", "B_owner")]
    out["eval_window_drift"] = {"max": max(x["booked_comm_drift"] for x in R), "median": float(np.median([x["booked_comm_drift"] for x in R]))}
    byL = M.by_day(lit_units())
    flips = collections.Counter()
    for h in HALVES:
        S = half_days(h)
        for i in range(len(S) - H + 1):
            days = S[i:i + H]
            for st, s0, ss in (("A_fresh", None, 0), ("B_owner", owner_start(), OWNER_SESSION0)):
                a = run_window(days, byL, "LIT 50K", s0, ss)["result"]
                b = run_window_booked(days, byL, s0, ss)[0]
                flips[(st, h, a, b)] += 1
    out["booked_vs_true_results"] = {f"{k[0]}|{k[1]}|true-book {k[2]} -> $1.40-book {k[3]}": v for k, v in sorted(flips.items())}
    return out


def main():
    os.makedirs(OUTD, exist_ok=True)
    rows, paths = windows()
    with open(os.path.join(OUTD, "EVALUATION_WINDOWS.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    S = summarize(rows)
    cols = list(dict.fromkeys(k for o in S for k in o))
    with open(os.path.join(OUTD, "EVALUATION_SUMMARY.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(S)
    rep = reproduce_check()
    for o in S:
        if o["starting_state"] == "A_fresh" and o["account"] == "LIT 50K" and o["window_kind"] == "rolling":
            rep[o["half"]]["this_tool_pass_breach"] = [o["pass_pct"], o["breach_pct"]]
    hc = hedge_check(paths)
    meta = {"reproduce": rep, "hedge_check": hc, "owner_start_profit_space": owner_start(), "owner_session0": OWNER_SESSION0,
            "lit_cfg": LIT_CFG, "rows": len(rows), "lit_units_2026": len(lit_units()),
            "atlas_units_2026": {"standalone": len(atlas_units(False)), "with_router_rules": len(atlas_units(True))},
            "commission": commission_drift(rows)}
    json.dump(meta, open(os.path.join(OUTD, "EVALUATION_META.json"), "w"), indent=1, default=str)
    for o in S:
        print(o, flush=True)
    print(json.dumps({k: meta[k] for k in ("reproduce", "hedge_check", "owner_start_profit_space", "owner_session0", "commission",
                                           "atlas_units_2026")}, default=str))
    return rows, S, meta


if __name__ == "__main__":
    main()
