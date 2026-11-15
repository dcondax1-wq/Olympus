"""BLITZ, the scalper PAPER SHADOW (engine/blitz.py; research/writeups/scalp-na-mffu.md). Paper only: never routed.

    python -X utf8 -m tests.test_blitz            # everything (~1.5 min)
    python -X utf8 -m tests.test_blitz --cloud    # + a cloud monitor dry run writing state "blitz" (~1-3 min more)

 a. parity, whole frame: engine/blitz.backtest on data/NQ_1m.csv (2026) = research/scalp/na_best_trades.json trade for trade
    (the NA scalp + the prior-day range filter: entry_t, dir, entry, stop, exit, exit_kind, exit_t, pts, r): 330 trades;
    unfiltered (the option, off) = research/scalp/mo_best_trades.json: 481 trades.
 b. parity, live Engine: the same bars fed one closed 1m bar at a time (Engine.on_bar, no look-ahead) = the same 330 / 481.
 c. live loop: the shadow polled like the PC bot (bars revealed as they close, random 1-7 minute gaps, a poll right after
    every check close, the state JSON-round-tripped every poll, a cold start warmed on the last 35 days) over 2026 H2 = the
    research trades of H2; data cut at random times never changes a trade that closed before the cut; a half day (no bar
    after 13:00) is flattened by the clock at 16:00 at the research's flat bar; pc_step (own file next to the bot state,
    kept in memory) = step.
 d. the paper 25K eval (40% of the room, max $600) = tools/scalp_na_lib.run_eval's back-to-back path in H1 (from 2026-01-01)
    and H2 (from 2026-07-01): every sized trade, micros, $, pass / fail / stuck; unfiltered at 30% = tools/scalp_mo_lib's.
 e. the paper funded 50K next to LIT: fed the research's LIT trades, LIT armed setups and ATLAS account-B trades, its trades
    = tools/scalp_na_combo's BLITZ units on LIT's account (lit_flat mask -> cut_on -> yield_to): 312 trades, entry, exit,
    kind (LIT FIRST / HEDGE), points, worst open points; micros = tools/div_stack.na_q (20% of the room, <= $450, the soft
    daily loss left); the live inputs: a LIT trade / armed setup from a lit_live run blocks a signal, LIT entering closes an
    open BLITZ trade at that bar's open, an opposite ATLAS paper trade or account B's open trade skips the entry.
 f. never routed: engine/blitz.py imports / names no adapter, broker, NinjaTrader, guard, order or routing code; importing it
    and running a step loads no such module; the PC hook (engine/live.py + engine/bg_worker.py) hands it only the 1m bars,
    LIT's run, the ATLAS paper run and account B's open trade.
 g. views: compact (heartbeat "blitz" with both ledgers), the heartbeat payload, Live View's purple layer (band lines,
    signals, PAPER positions of both ledgers), the narrator (kind "blitz", strat scalp, PAPER, never pushed by default),
    card / notices / README lines.
 h. cheap per poll: a poll with a new bar and one without, after the warm-up.
 i. wiring: .gitignore has data/blitz_state.json, docs/CLAUDE_REFERENCE.md has the entry, live_model*.json /
    second_model.json untouched (git), the cloud monitor runs it next to the ATLAS v2 shadow with LIT's run and the ATLAS
    ledgers (state "blitz").
Prints the 2026 H1 / H2 paper numbers of the replay.
"""
from __future__ import annotations

import ast
import collections
import copy
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import blitz as BZ  # noqa: E402

warnings.filterwarnings("ignore")
ET = ZoneInfo("America/New_York")
RES = []
REF_PATH = os.path.join(ROOT, "research", "scalp", "na_best_trades.json")
RAW_PATH = os.path.join(ROOT, "research", "scalp", "mo_best_trades.json")
H1 = ("2026-01-01", "2026-06-30")
H2 = ("2026-07-01", "2026-12-31")
HALF_DAY = "2026-07-29"             # a 12:30 BLITZ entry is open at the simulated 13:00 halt
VIEW_DAY = "2026-09-15"             # 5+ BLITZ trades


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"\n       {str(info)[:700]}" if info != "" and not ok else ""), flush=True)


def f_et(t) -> str:
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%Y-%m-%d %H:%M")


_D = {}


def data():
    if not _D:
        _D["df"] = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        _D["ref"] = json.load(open(REF_PATH, encoding="utf-8"))
        _D["raw"] = json.load(open(RAW_PATH, encoding="utf-8"))
    return _D["df"], _D["ref"]


def same(mine, ref, tol=1e-6) -> list:
    """Differences between our trades (entry_t / exit_t unix, dir +-1) and a research file's rows (ET strings)."""
    bad = []
    for k, (a, b) in enumerate(zip(mine, ref)):
        side = "long" if int(a["dir"]) > 0 else "short"
        ok = (f_et(a["entry_t"]) == b["entry_t"] and side == b["dir"] and abs(float(a["entry"]) - b["entry"]) < tol
              and abs(round(float(a["stop"]), 2) - b["stop"]) < 0.0051 and abs(float(a["exit"]) - b["exit"]) < tol
              and str(a["exit_kind"]) == b["exit_kind"] and f_et(a["exit_t"]) == b["exit_t"]
              and abs(round(float(a["pts"]), 2) - b["pts"]) < 0.0051 and abs(round(float(a["r"]), 3) - b["r"]) < 0.0011)
        if not ok:
            bad.append((k, {x: a.get(x) for x in ("entry_t", "dir", "entry", "stop", "exit", "exit_kind", "exit_t", "pts", "r")}, b))
    if len(mine) != len(ref):
        bad.append(("count", len(mine), len(ref)))
    return bad


def ref_in(ref, span):
    a, z = span
    return [r for r in ref if a <= r["entry_t"][:10] <= z]


# ================================================================================================ a + b
def part_ab():
    df, R = data()
    ref, raw = R["trades"], _D["raw"]["trades"]
    check("a. research file: BLITZ = the NA scalp + the prior-day range filter (prng>=0.8), 330 trades, the rule engine/blitz.py runs",
          R["name"] == BZ.PICK and len(ref) == 330 and R["params"]["filter"] == BZ.RULE["filter"] and R["params"]["maxday"] == BZ.MAXDAY
          and R["params"]["day_stop"] == BZ.DAY_STOP_R and R["params"]["stopk"] == BZ.STOP_ATR and R["params"]["hold"] == BZ.HOLD
          and tuple(R["params"]["win"]) == BZ.WIN and R["params"]["trail"] == BZ.TRAIL_R and R["params"]["tstart"] == BZ.TRAIL_START,
          R["params"])
    check("a. the checks are the 1m closes 11:00, 11:30 ... 15:30 (10 checks; the first research entry of a day is at 11:00)",
          [f"{(m + 1) // 60:02d}:{(m + 1) % 60:02d}" for m in BZ.CHECKS] == [f"{h:02d}:{mm:02d}" for h in range(11, 16) for mm in (0, 30)]
          and min(r["entry_t"][11:] for r in ref) == "11:00" and max(r["entry_t"][11:] for r in ref) == "15:30")
    for filt, rf, nm in ((True, ref, "filtered (BLITZ)"), (False, raw, "unfiltered option (plain NA)")):
        t0 = time.time()
        T = BZ.backtest(df, filtered=filt)
        bad = same(T, rf)
        check(f"a. backtest (whole frame), {nm} = research trade for trade: {len(T)} trades ({time.time() - t0:.1f} s)", not bad, bad[:3])
        t0 = time.time()
        S = BZ.replay_2026(first_run="2025-12-28", filtered=filt)
        L = S["ledger"]
        bad = same(L, rf)
        check(f"b. live Engine, one closed bar at a time, {nm} = research trade for trade: {len(L)} trades ({time.time() - t0:.1f} s)",
              not bad, bad[:3])
        if filt:
            ek = collections.Counter(r["exit_kind"] for r in L)
            check(f"b. exits as the research: {dict(ek)}", ek == collections.Counter(r["exit_kind"] for r in rf), ek)
            per_day = collections.Counter(r["day"] for r in L)
            check("b. never more than 6 a day, one position at a time, never on a filtered day",
                  max(per_day.values()) <= 6 and all(L[i]["exit_t"] <= L[i + 1]["entry_t"] for i in range(len(L) - 1)))


# ================================================================================================ c. live loop
def poll_times(df, a_day, z_day, seed=7):
    """Poll times like the PC bot: random 1-7 minute gaps 10:50-16:10 ET on weekdays (+ a poll 2 s after every check close),
    every 30 minutes otherwise."""
    rng = np.random.default_rng(seed)
    t_a = BZ.at_et(a_day, 0)
    t_z = BZ.at_et(z_day, 23 * 60 + 59)
    out, t = [], t_a
    while t <= t_z:
        d, mod = BZ.et_parts(t)
        wk = dt.date.fromisoformat(d).weekday() < 5
        out.append(t)
        t += (int(rng.integers(1, 8)) * 60 + int(rng.integers(0, 50))) if (wk and 650 <= mod <= 970) else 1800
    for d in sorted({BZ.et_date(int(x)) for x in df["time"].to_numpy()}):
        if a_day <= d <= z_day:
            out += [BZ.at_et(d, m + 1) + 2 for m in BZ.CHECKS]
    return sorted(set(out))


def live_loop(df, first_day, last_day, seed=7):
    times = poll_times(df, first_day, last_day, seed)
    tt = df["time"].to_numpy(np.int64)
    prev, fr = None, times[0]
    for now in times:
        k = int(np.searchsorted(tt, now - 60, side="right"))           # the bars that have closed by now
        S = BZ.step(prev, df.iloc[:k], now, first_run=fr)
        prev = json.loads(json.dumps(S))
    return prev, len(times)


def part_c():
    df, R = data()
    ref = R["trades"]
    t0 = time.time()
    S, n = live_loop(df, H2[0], "2026-10-17")
    L = S["ledger"]
    bad = same(L, ref_in(ref, H2))
    check(f"c. live loop over 2026 H2 ({n} polls, bars revealed as they close, state JSON each poll, cold start warmed on "
          f"{(S.get('warm') or {}).get('bars')} bars): {len(L)} trades = research H2 ({time.time() - t0:.0f} s)", not bad, bad[:3])
    check("c. every H2 trade decided on a poll after its signal bar closed (no look-ahead: decided_t >= the entry bar's open)",
          all(int(r["decided_t"]) >= int(r["entry_t"]) for r in L))
    # data cut at random times: closed trades before the cut never change
    full = {r["entry_t"]: r for r in BZ.replay_2026(first_run="2025-12-28")["ledger"]}
    rng = np.random.default_rng(3)
    days = sorted({r["day"] for r in full.values()})
    cuts = [BZ.at_et(d, m) for d, m in zip(rng.choice(days, 8, replace=False), (780, 691, 956, 721, 600, 870, 931, 662))]
    tt = df["time"].to_numpy(np.int64)
    o_, h_, l_, c_ = (df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    diff = []
    for cut in cuts:
        E = BZ.Engine()
        k = int(np.searchsorted(tt, cut - 60, side="right"))
        got = {}
        for i in range(k):
            for x in E.on_bar(int(tt[i]), o_[i], h_[i], l_[i], c_[i]):
                if x["ev"] == "exit":
                    got[x["entry_t"]] = x
        for et_, r in full.items():
            if r["exit_t"] <= cut and r["exit_kind"] != "flat":
                x = got.get(et_)
                if x is None or abs(x["exit"] - r["exit"]) > 1e-9 or x["kind"] != r["exit_kind"]:
                    diff.append((f_et(cut), f_et(et_)))
        diff += [("extra", f_et(cut), f_et(e)) for e in got if e not in full]
    check(f"c. data cut at {len(cuts)} random times: every trade closed before the cut is the same, none extra", not diff, diff[:4])
    # a half day: bars stop at 13:00 (no bar until 18:00): the clock flattens at 16:00 ET at the research's flat bar
    day = HALF_DAY
    nxt = (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()
    rest = df[(df["time"] < BZ.at_et(day, 780)) | (df["time"] >= BZ.at_et(day, 18 * 60))].reset_index(drop=True)
    T = BZ.backtest(rest[rest["time"] < BZ.at_et(nxt, 0)])
    refd = [(r["entry_t"], r["exit_kind"], round(r["exit"], 6)) for r in T if r["day"] == day]
    E = BZ.Engine()
    out = []
    for r in rest[rest["time"] < BZ.at_et(day, 18 * 60)].itertuples():
        out += E.on_bar(int(r.time), r.open, r.high, r.low, r.close)
    open_halt = 1 if E.s["pos"] else 0
    out += E.on_clock(BZ.at_et(day, 959))
    mid = 1 if E.s["pos"] else 0
    out += E.on_clock(BZ.at_et(day, 961))
    rel = {x["entry_t"]: x["kind"] for x in out if x["ev"] == "relabel"}
    mine = [(x["entry_t"], rel.get(x["entry_t"], x["kind"]), round(x["exit"], 6)) for x in out if x["ev"] == "exit" and x["date"] == day]
    check(f"c. half day {day} (bars stop 13:00): {len(mine)} trades = the whole-frame run's; the clock closes the day at 16:00 ET "
          f"(open at the halt {open_halt}, still open at 15:59 {mid})", mine == refd and E.s["closed"] and not E.s["pos"]
          and open_halt == 1 and mid == 1 and refd and refd[-1][1] == "flat", (mine, refd))
    # pc_step = step (own file, in memory between polls)
    tmp = tempfile.mkdtemp(prefix="blitz_pc_")
    try:
        path = BZ.pc_path(os.path.join(tmp, "live_state.json"))
        a_ = BZ.at_et(VIEW_DAY, 10 * 60 + 50)
        polls = [a_ + 60 * i + 3 for i in range(0, 330, 3)]
        ok, prev, S2 = True, None, None
        for now in polls:
            k = int(np.searchsorted(tt, now - 60, side="right"))
            S1 = BZ.pc_step(path, df.iloc[:k], now)
            S2 = BZ.step(prev, df.iloc[:k], now, first_run=polls[0])
            prev = S2
            a1 = {k_: v for k_, v in S1.items() if k_ != "saved_t"}
            a2 = {k_: v for k_, v in S2.items() if k_ != "saved_t"}
            if json.dumps(a1, sort_keys=True, default=str) != json.dumps(a2, sort_keys=True, default=str):
                ok = False
                break
        on_disk = json.load(open(path, encoding="utf-8"))
        check(f"c. pc_step (file {os.path.basename(path)} next to the bot state) = step over {len(polls)} polls of {VIEW_DAY} "
              f"({len(S2['ledger'])} paper trades), saved on disk", ok and on_disk["eng"]["last_t"] == S2["eng"]["last_t"]
              and path.endswith(os.path.join(os.path.basename(tmp), "blitz_state.json")) and len(S2["ledger"]) >= 5)
        os.remove(path)
        S3 = BZ.pc_step(path, df.iloc[:10], polls[0])
        check("c. pc_step never raises (a broken frame -> an error state, not an exception)",
              isinstance(BZ.pc_step(path, "not a frame", polls[0] + 60), dict) and isinstance(S3, dict))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ d. paper 25K eval
def b2b_path(Lb, Ts, S_, f, cap, stuck, run_eval):
    by = collections.defaultdict(list)
    for t in Ts:
        by[t["day"]].append(t)
    K, k = [], 0
    while k < len(S_):
        r, used = run_eval(S_[k:], by, Lb.PLANS["25k"], f, cap, len(S_) - k, keep=K, stuck=stuck)
        if r == "OPEN":
            break
        k += used
    return K


def part_d():
    from tools import scalp_na as X
    from tools import scalp_na_lib as N
    from tools import scalp_mo_lib as Lm
    from tools import scalp_mo_pick as Pm
    T1 = [t for t in X.blitz_trades(None, names=("prng>=0.8",))[1] if t["day"] >= "2026-01-01"]
    B = N.bars(1)
    out = {}
    for filt in (True, False):
        Tall = T1 if filt else Pm.trades("na_scalp", 1)[1]
        f = BZ.PLAN["f"] if filt else BZ.F_RAW
        for nm, span in (("H1", H1), ("H2", H2)):
            S_ = N.sessions(B, nm)
            Ts = [t for t in Tall if S_[0] <= t["day"] <= S_[-1]]
            stuck = 2.0 * float(np.median([t["risk_pm"] for t in Ts]))
            if filt:
                sz = {"mode": "frac", "f": f, "cap": BZ.PLAN["cap"]}
                e = N.eval_score(Ts, S_, "25k", sz)
                K = b2b_path(N, Ts, S_, f, BZ.PLAN["cap"], stuck,
                             lambda days, by, P, f_, cap_, hz, keep, stuck: N.run_eval(days, by, P, sz, hz, keep=keep, stuck=stuck))
            else:
                e = Lm.eval_score(Ts, S_, "25k", f, BZ.PLAN["cap"])
                K = b2b_path(Lm, Ts, S_, f, BZ.PLAN["cap"], stuck, Lm.run_eval)
            S = BZ.replay_2026(first_run=span[0], stuck=stuck, filtered=filt)
            rows = [r for r in S["ledger"] if r["day"] <= span[1]]
            sized = [r for r in rows if int(r["qty"]) > 0]
            mine = [(r["entry_t"], int(r["qty"]), round(float(r["usd"]), 2)) for r in sized]
            refk = [(int(t["entry_t"]), int(t["qty"]), round(float(t["pnl"]), 2)) for t in K]
            ev = [x for x in S["evals"] if x["end"] <= span[1]]
            cnt = (sum(1 for x in ev if x["result"] == "PASS"), sum(1 for x in ev if x["result"] in ("FAIL", "STUCK")))
            b2b = tuple(int(x) for x in e["b2b"].split("/"))
            bad = [(a, b) for a, b in zip(mine, refk) if a != b]
            net = round(sum(float(r["usd"]) for r in sized))
            tag = "BLITZ 40%" if filt else "unfiltered 30%"
            check(f"d. {nm} {tag}: paper 25K eval = research back-to-back path: {len(mine)} sized trades, every micro / $; "
                  f"pass / fail+stuck {cnt[0]}/{cnt[1]} = {e['b2b']}; path ${net:+,} = ${e['path_net']:+,}",
                  len(mine) == len(refk) and not bad and cnt == b2b and net == e["path_net"], (bad[:2], len(mine), len(refk), cnt, e["b2b"]))
            if filt:
                st = N.stats(T1, S_, 150.0, 20)
                out[nm] = {"S": S, "rows": rows, "eval": e, "stats": st, "sessions": len(S_), "evals": ev, "net": net}
    check("d. the default stuck room ($249.56 = 2 x the 2026 median stop-out of the 330) is the research's over all 2026",
          abs(BZ.STUCK_ROOM - 2.0 * float(np.median([t["risk_pm"] for t in T1]))) < 0.01)
    return out


# ================================================================================================ e. the 50K next to LIT
def research_ctx():
    from tools import scalp_na_combo as C
    from tools import scalp_na_lib as N
    lit = [x for d, v in N.lit_trades().items() if d >= "2025-12-01" for x in v]
    arm = [(a, z) for d, v in N.lit_armed().items() if d >= "2025-12-01" for _, a, z in v]
    atl = [x for d, v in C.atlas_by_day().items() if d >= "2025-12-01" for x in v]
    U = [u for u in C.blitz_units(lit_flat=True) if u["day"] >= "2026-01-01"]
    U = C.yield_to(C.cut_on(U, C.lit_by_day()), C.atlas_by_day())
    return {"lit": lit, "armed": arm, "atlas": atl}, U


def part_e():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from tools import div_stack as DS
    ctx, U = research_ctx()
    t0 = time.time()
    S = BZ.replay_2026(first_run="2025-12-28", ctx=ctx)
    L = [r for r in S["ledger50"] if r["exit_kind"] != "SKIP"]
    km = {"PRE": "LIT FIRST"}
    bad = [(a["entry_t"], a["exit_t"], a["exit_kind"], a["pts"], a.get("w1"), b["entry_t"], b["exit_t"], b["exit"], b["pts"], b["w1"])
           for a, b in zip(L, U) if not (a["entry_t"] == b["entry_t"] and a["dir"] == b["dir"] and a["exit_t"] == b["exit_t"]
                                         and a["exit_kind"] == km.get(b["exit"], b["exit"]) and abs(round(a["pts"], 2) - b["pts"]) < 0.0051
                                         and abs(a["w1"] - b["w1"]) < 0.0051)]
    m5 = BZ.money50(S)
    check(f"e. 50K next to LIT = the research's BLITZ units on LIT's account (LIT flat at the signal, LIT first, never opposite ATLAS): "
          f"{len(L)} trades = {len(U)}, {m5['masked']} signals while LIT was busy, {m5['skipped']} skipped (ATLAS), {m5['hedge']} HEDGE / "
          f"{m5['lit_first']} LIT FIRST cuts ({time.time() - t0:.1f} s)", len(L) == len(U) and not bad, bad[:3])
    nc = {"f": BZ.FUNDED50["f"], "cap": BZ.FUNDED50["cap"]}
    qbad = [(r["entry_t"], r["qty"], r.get("room"), r.get("cum")) for r in L
            if r.get("room") is not None and int(r["qty"]) != DS.na_q({"risk": round(float(r["risk_pts"]), 2)}, float(r["room"]), nc, 40,
                                                                       BZ.FUNDED50["dll"] + float(r["cum"]))]
    check("e. 50K micros = tools/div_stack.na_q (20% of the room, <= $450, the soft daily loss left, 40 micros) on every trade",
          not qbad and all(r.get("room") is not None for r in L if int(r["qty"]) > 0), qbad[:3])
    # the account: an independent re-run of the booking on the ledger's trades (EOD trailing floor, soft daily loss, lost)
    bal = peak = 0.0
    floor, cum, day, okb = -2000.0, 0.0, None, True
    for r in sorted(L, key=lambda r: r["entry_t"]):
        if r["day"] != day:
            if day is not None:
                bal += cum
                peak = max(peak, bal)
                floor = min(max(floor, peak - 2000.0), 100.0)
            day, cum = r["day"], 0.0
        q = int(r["qty"])
        pnl = r["pts"] * 2 * q - 1.9 * q
        low = min(0.0, r["w1"] * 2 * q - 1.9 * q, pnl)
        if cum + low <= -1000.0:
            pnl = -1000.0 - cum - 0.25 * 2 * q
        okb &= abs(pnl - float(r["usd"])) < 0.011
        cum += pnl
    check(f"e. 50K account booking = an independent re-run (soft daily loss cap, EOD trailing floor): paper ${m5['usd']:+,.0f} on "
          f"{m5['sized']} trades, {m5['lost']} accounts lost", okb and m5["lost"] == 0)
    # the live inputs: a lit_live run, the ATLAS paper run, account B's open trade
    df, R = data()
    day = VIEW_DAY
    rows = [r for r in R["trades"] if r["entry_t"].startswith(day)]
    e0 = int(dt.datetime.fromisoformat(rows[0]["entry_t"]).replace(tzinfo=ET).timestamp())     # the day's first BLITZ entry
    tt = df["time"].to_numpy(np.int64)
    z = BZ.at_et(day, 16 * 60 + 10)
    k = int(np.searchsorted(tt, z - 60, side="right"))
    base = BZ.step(None, df.iloc[:k], z, first_run=BZ.at_et(day, 0))
    d0 = int(rows[0]["dir"] == "long") * 2 - 1
    x0 = int(dt.datetime.fromisoformat(rows[0]["exit_t"]).replace(tzinfo=ET).timestamp())       # end of its exit bar
    # 1) LIT holds a trade over the first signal
    res = {"trades": [{"entry_t": e0 - 600, "exit_t": e0 + 60, "dir": 1}], "state": {}, "signals": []}
    S1 = BZ.step(None, df.iloc[:k], z, first_run=BZ.at_et(day, 0), res=res)
    r0 = {r["entry_t"]: r for r in S1["ledger50"]}
    sk = [x for x in S1["skipped50"] if x["t"] == e0 - 60]
    check("e. live: a LIT trade open at the signal close = no 50K entry (\"LIT in a trade\"); the 25K eval still takes it",
          sk and sk[0]["why"] == "LIT in a trade" and e0 not in r0 and any(r["entry_t"] == e0 for r in S1["ledger"]), (sk, list(r0)[:3]))
    # 2) LIT enters inside the first BLITZ trade (still open in the poll's LIT run)
    a_lit = e0 + 60 * max(1, ((x0 - e0) // 60 - 1) // 2)
    res = {"trades": [], "state": {"position": {"entry_t": a_lit, "dir": -d0}}, "signals": []}
    S1 = BZ.step(None, df.iloc[:k], z, first_run=BZ.at_et(day, 0), res=res)
    c1 = {r["entry_t"]: r for r in S1["ledger50"]}.get(e0)
    o_cut = float(df["open"].iat[int(np.searchsorted(tt, a_lit))])
    check(f"e. live: LIT entering inside an open 50K trade ({f_et(a_lit)}, from the run's open position) closes it at that bar's "
          f"open - 1 tick (LIT FIRST at {c1 and c1.get('exit')}); later signals wait while LIT holds",
          c1 and c1["exit_kind"] == "LIT FIRST" and abs(float(c1["exit"]) - (o_cut - d0 * 0.25)) < 1e-9 and c1["exit_t"] == a_lit
          and all(r["entry_t"] <= a_lit for r in S1["ledger50"] if r["exit_kind"] != "SKIP"), c1)
    res2 = {"trades": [], "state": {"setups": {"long": {"arm_t": e0 - 300, "expires_t": e0 + 1500}}},
            "signals": [{"t": e0 - 300, "dir": 1, "status": "pending"}]}
    S2 = BZ.step(None, df.iloc[:k], e0 + 30, first_run=BZ.at_et(day, 0), res=res2)
    check("e. live: a LIT setup armed (lit_live state setups / pending signal) at the signal close = no 50K entry, kept in lit_armed",
          any(x["why"] == "LIT setup armed" for x in S2["skipped50"]) and S2["lit_armed"], (S2["skipped50"], S2["lit_armed"]))
    sec = {"strategies": {"ema_lon_vix": {"trades": [{"entry_t": e0 - 900, "exit_t": None, "dir": -d0, "exit_kind": "OPEN"}]}}}
    S3 = BZ.step(None, df.iloc[:k], z, first_run=BZ.at_et(day, 0), second=sec)
    S4 = BZ.step(None, df.iloc[:k], z, first_run=BZ.at_et(day, 0), atlas_open={"entry_t": e0 - 900, "dir": -d0})
    s3 = {r["entry_t"]: r for r in S3["ledger50"]}.get(e0)
    s4 = {r["entry_t"]: r for r in S4["ledger50"]}.get(e0)
    check("e. live: an open opposite ATLAS paper trade / account B's open trade skips the 50K entry (\"ATLAS holds the other side\")",
          s3 and s3["exit_kind"] == "SKIP" and s3["skip"] == "ATLAS holds the other side" and s4 and s4["exit_kind"] == "SKIP",
          (s3, s4))
    b0 = {r["entry_t"]: r for r in base["ledger50"]}
    check("e. live: with LIT and ATLAS quiet the 50K takes the same trades as the 25K eval (sized on its own account)",
          sorted(b0) == sorted(r["entry_t"] for r in base["ledger"]) and all(r["qty"] > 0 for r in b0.values()))
    return S


# ================================================================================================ f. never routed
FORBID_MODS = ("ninjatrader", "tradovate", "account_b", "accounts", "guards", "live", "multi_account", "sizing", "broker_balance",
               "alerts", "alerts_plus", "remote_ctl", "golive", "go", "botctl", "lit_live", "second", "fill_audit")
FORBID_NAMES = {"route", "_route", "place_order", "submit_order", "send_order", "flatten", "oif", "OIF", "adapter", "Adapter",
                "LiveBot", "BOT", "ninjatrader", "tradovate", "write_oif", "arm", "set_route"}


def part_f():
    import io
    import tokenize
    src = open(os.path.join(ROOT, "engine", "blitz.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    mods, names = set(), set()
    for nd in ast.walk(tree):
        if isinstance(nd, ast.Import):
            mods |= {a.name for a in nd.names}
        elif isinstance(nd, ast.ImportFrom):
            mods |= {("." * nd.level) + (nd.module or "") + (":" + ",".join(a.name for a in nd.names))}
        elif isinstance(nd, ast.Name):
            names.add(nd.id)
        elif isinstance(nd, ast.Attribute):
            names.add(nd.attr)
    allowed = {"__future__:annotations", "datetime", "json", "os", "warnings", "zoneinfo:ZoneInfo", "numpy", "pandas", "sys", ".:push", ".:hidden_bots"}   # hidden_bots: push_on only (read-only switch)
    check("f. engine/blitz.py imports only the standard library, numpy / pandas and engine/push (cloud notices text only)",
          mods <= allowed, sorted(mods - allowed))
    hit = sorted(names & FORBID_NAMES)
    check("f. engine/blitz.py names no adapter / order / routing call", not hit, hit)
    code_only = " ".join(tok.string for tok in tokenize.generate_tokens(io.StringIO(src).readline)
                         if tok.type not in (tokenize.STRING, tokenize.COMMENT)).lower()
    check("f. no broker words in engine/blitz.py code (strings / comments aside): ninjatrader, tradovate, oif, place order, outgoing",
          not any(w in code_only for w in ("ninjatrader", "tradovate", "oif", "place_order", "outgoing", "adapter")))
    code = ("import sys, json; sys.path.insert(0, %r); import pandas as pd; from engine import blitz as BZ; "
            "df = pd.read_csv(%r).tail(60000).reset_index(drop=True); now = int(df['time'].iloc[-1]) + 62; "
            "res = {'trades': [{'entry_t': now - 7200, 'exit_t': now - 3600, 'dir': 1}], 'state': {}, 'signals': []}; "
            "S = BZ.step(None, df, now, res=res, second={'strategies': {}}); BZ.compact(S); BZ.card(S); BZ.state_text(S); BZ.readme_lines(S); "
            "import tempfile, os; d = tempfile.mkdtemp(); BZ.pc_step(os.path.join(d, 'blitz_state.json'), df, now, res=res); "
            "print(json.dumps(sorted(m for m in sys.modules if m.startswith('engine'))))") % (ROOT, os.path.join(ROOT, "data", "NQ_1m.csv"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True, timeout=300)
    try:
        loaded = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        loaded = None
    bad = [m for m in (loaded or []) if m.split(".")[-1] in FORBID_MODS or m in ("engine.push",)]
    check("f. a step / pc_step / views load no order, broker, guard or push module (fresh process)",
          loaded is not None and loaded == ["engine", "engine.blitz"] and not bad, (loaded, bad, r.stderr[-400:]))
    live = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    bgw = open(os.path.join(ROOT, "engine", "bg_worker.py"), encoding="utf-8").read()
    i = live.index("def _second_tick")
    body = live[i:live.index("def _second_cfg")]
    check("f. PC hook: the paper thread / worker job call pc_step(<state dir>/blitz_state.json, 1m bars, now, LIT's run, the ATLAS "
          "paper run, account B's open trade) only, after LIT's routing",
          "_blz.pc_step(_blz.pc_path(self.state_path), df1, now, res=res," in body and '_blz.pc_step(a["blitz_path"], df1, a["now"], res=a.get("res"), second=out["second"],' in bgw
          and '"blitz_path": _blz.pc_path(self.state_path)' in live and "def _blitz_atlas_open(self)" in live
          and live.index("self._second_tick(df_full, df1, res, now)") > live.index("self._route_signals(res, sym, now, secs)"))


# ================================================================================================ g. views
def fake_state():
    """A shadow state polled through VIEW_DAY (a paper trade open at some poll), plus its full day."""
    df, _ = data()
    tt = df["time"].to_numpy(np.int64)
    a_ = BZ.at_et(VIEW_DAY, 10 * 60 + 50)
    prev, S_open = None, None
    for now in [a_ - 86400 * 2] + [a_ + 60 * i + 3 for i in range(0, 330)]:
        k = int(np.searchsorted(tt, now - 60, side="right"))
        prev = BZ.step(prev, df.iloc[:k], now, first_run=a_ - 86400 * 2)
        if prev.get("open") and prev.get("open50") and S_open is None and BZ.et_parts(now)[1] > 670:
            S_open = copy.deepcopy(prev)
    return prev, S_open


def part_g():
    from engine import heartbeat as HB
    from engine import liveview_api as LV
    from engine import narrator as N
    S, S_open = fake_state()
    c = BZ.compact(S)
    js = json.dumps(c, default=str)
    f50 = c.get("funded50") or {}
    check(f"g. compact (heartbeat \"blitz\"): paper, never routed, state text, both ledgers today, 25K eval, funded 50K, band; {len(js):,} bytes",
          c["paper"] and c["never_routed"] and c["state"]["text"] and c["today"] and c["eval"]["plan"] == "MFFU Builder 25K"
          and f50.get("today") and f50["account"]["plan"].startswith("MFFU Builder 50K") and "PAPER" in f50["label"]
          and c["band"] and c["band"].get("checks") and len(js) < 16000, (len(js), c.get("state")))
    bot = SimpleNamespace(state={}, cfg={"adapter": "paper"}, running=True, blitz=S)
    check("g. heartbeat payload block \"blitz\" = compact(LiveBot.blitz); None before the first run",
          HB._blitz(bot) == c and HB._blitz(SimpleNamespace()) is None)
    src = open(os.path.join(ROOT, "engine", "heartbeat.py"), encoding="utf-8").read()
    check("g. the heartbeat payload carries \"blitz\"", '"blitz": _blitz(self.bot)' in src)
    for S_, label in ((S_open, "open trade"), (S, "day end")):
        if S_ is None:
            check(f"g. Live View ({label}): a state with an open paper trade exists", False)
            continue
        b = SimpleNamespace(running=True, kill=False, cfg={"adapter": "paper"}, state={"price": None}, brain=None, second=None, acct_b=None,
                            ledger=[], log=[], health={}, bars_tail=[], _lit_1m_store=None, _open_routed=None, _open_qty=None, _open_src=None,
                            adapter=None, clock=lambda: int(S_["t"]), blitz=S_)
        b._push_account = lambda: "Paper"
        LV.CSV_FALLBACK = False
        v = LV.view(b, "1m", int(S_["t"]), narr=N.Narrator())
        sc = v["strategies"]["scalp"]
        ids = {x["id"] for x in sc.get("lines") or []}
        txt = json.dumps(sc, default=str)
        if label == "open trade":
            ent = next((x["label"] for x in sc["lines"] if x["id"] == "blz_entry"), "")
            check("g. Live View purple layer (open trade): BLITZ, band lines, one PAPER entry line with both paper sizes, stop, the "
                  "position of each ledger, signals, the two members", sc["name"] == "BLITZ" and not sc["placeholder"]
                  and {"blz_up", "blz_lo", "blz_entry", "blz_stop"} <= ids and "PAPER" in ent and "25K eval" in ent and "50K" in ent
                  and sc["position"]["paper"] and sc["position50"]["paper"] and sc["signals"] and sc["color"] == "#7c3aed"
                  and [m["short"] for m in sc["members"]][:2] == ["BLITZ", "BLITZ 50K + LIT"], (ids, ent, sc.get("error")))
        else:
            check("g. Live View purple layer (day end): today's PAPER entries / exits of both ledgers as marks, band of every check",
                  any(m["kind"] == "exit" and m.get("paper") and m.get("ledger") == "25K eval" for m in sc["marks"])
                  and any(m["kind"] == "exit" and m.get("ledger") == "50K + LIT" for m in sc["marks"]) and sc["band"]
                  and len(sc["band"]) == len(BZ.CHECKS) and sc["position"] is None and "never routed" in sc["text"]
                  and "funded 50K next to LIT" in sc["text"], (sc.get("marks"), sc.get("error")))
        check(f"g. Live View ({label}): no real size claimed (every BLITZ line / mark says PAPER)",
              all(("PAPER" in (x.get("label") or "")) or x["id"] in ("blz_up", "blz_lo", "blz_o0", "blz_trail", "b50_trail") for x in sc["lines"])
              and all(m.get("paper") or m["kind"] == "signal" for m in sc["marks"]) and "I ACCEPT" not in txt)
    b = SimpleNamespace(running=True, cfg={"adapter": "paper"}, state={}, brain=None, second=None, acct_b=None, ledger=[], health={},
                        kill=False, clock=lambda: int(S["t"]), blitz=S)
    nar = N.Narrator()
    new = nar.observe(b, int(S["t"]))
    bz = [m for m in new if m["kind"] == "blitz"]
    rows = BZ.today_rows(S)
    rows50 = [r for r in BZ.today_rows(S, ledger="ledger50") if r["exit_kind"] != "SKIP"]
    check(f"g. narrator: {len(bz)} BLITZ messages (signals, PAPER entries / exits of both ledgers), strat scalp, kind blitz",
          bz and all(m["strat"] == "scalp" for m in bz) and sum(1 for m in bz if "PAPER entry" in m["title"]) == len(rows)
          and sum(1 for m in bz if "PAPER 50K entry" in m["title"]) == len(rows50)
          and sum(1 for m in bz if "PAPER exit" in m["title"]) == sum(1 for r in rows if r["exit_kind"] != "OPEN")
          and all("PAPER" in m["title"] or "paper" in m["text"] for m in bz), [m["title"] for m in bz][:6])
    none = os.path.join(tempfile.gettempdir(), "none_blitz.json")
    check("g. narrator: kind blitz is never pushed by default", N.push_prefs(none)["blitz"] is False and N.KINDS["blitz"][1] is False)
    sent = []
    N.Narrator().observe(b, int(S["t"]), push=True, send=lambda m, bot: sent.append(m["kind"]) or True, prefs=N.push_prefs(none))
    check("g. narrator with pushes on (the real bot's tick): no BLITZ push", "blitz" not in sent, sent)
    check("g. narrator: second look gives nothing new (stable keys)", nar.observe(b, int(S["t"])) == [])
    cd = BZ.card(S)
    check("g. card: paper, never routed, the research numbers, both ledgers", cd["paper"] and cd["never_routed"] and cd["research"]["H2"]["pf"] == 1.49
          and cd["today"] and cd["funded50"] and cd["trades50"] and cd["source"] == "cloud")
    nt = BZ.notices(S, 0)
    check("g. cloud notices: kind second, titled BLITZ PAPER ..., one per entry / exit, the 50K size in the text",
          nt and all(n["kind"] == "second" and n["title"].startswith("BLITZ PAPER") for n in nt) and
          sum(1 for n in nt if n["key"].startswith("blitz:fill:")) == len(S["ledger"]) and any("50K next to LIT" in n["body"] for n in nt),
          [n["title"] for n in nt][:4])
    rl = BZ.readme_lines(S)
    check("g. README lines: label, the 25K eval, the funded 50K", rl and any("never routed" in x for x in rl) and any("25K eval" in x for x in rl)
          and any("Funded 50K next to LIT" in x for x in rl))


# ================================================================================================ h. speed
def part_h():
    df, _ = data()
    tt = df["time"].to_numpy(np.int64)
    tmp = tempfile.mkdtemp(prefix="blitz_speed_")
    try:
        path = os.path.join(tmp, "blitz_state.json")
        a_ = BZ.at_et("2026-10-14", 11 * 60)
        res = {"trades": [{"entry_t": a_ - 7200, "exit_t": a_ - 3600, "dir": 1}], "state": {}, "signals": []}
        k = int(np.searchsorted(tt, a_ - 60, side="right"))
        t0 = time.perf_counter()
        BZ.pc_step(path, df.iloc[:k], a_, res=res)
        warm = time.perf_counter() - t0
        new_bar, same_bar = [], []
        for i in range(1, 41):
            now = a_ + 60 * i + 2
            k = int(np.searchsorted(tt, now - 60, side="right"))
            t0 = time.perf_counter()
            BZ.pc_step(path, df.iloc[:k], now, res=res)
            new_bar.append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            BZ.pc_step(path, df.iloc[:k], now + 5, res=res)
            same_bar.append((time.perf_counter() - t0) * 1000)
        m1, m2 = float(np.median(new_bar)), float(np.median(same_bar))
        check(f"h. cheap per poll: cold start {warm * 1000:.0f} ms (35 days of 1m bars, two ledgers), then a poll with a new bar "
              f"{m1:.1f} ms, without {m2:.1f} ms (median)", warm < 5.0 and m1 < 40 and m2 < 25, (warm, m1, m2))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ j. why no trade today
def part_j():
    """The day filter in the state text with its numbers (2026-10-29: the PC shadow said only "No more checks today" on two
    0-trade days; Oct 29 was filtered: Oct 28's range 239 pts = 0.59 x its 14-day mean 404). Real 2026 bars: Oct 14 is a
    filtered day (Oct 13's range 0.77 x its mean), Oct 15 a trading day (1.89 x)."""
    df, _ = data()
    B = BZ.frame(df)
    pr = BZ.prior_range(B)
    dates = list(B["dates"])

    def engine_at(now):
        E = BZ.Engine(None, True)
        t, o, h, l, c = BZ._bars_of(df, now - BZ.WARM_DAYS * 86400, now - 60)
        for i in range(len(t)):
            E.on_bar(int(t[i]), o[i], h[i], l[i], c[i])
        return {"eng": E.s, "t": now, "ledger": [], "ledger50": []}
    r14, r15 = float(pr[dates.index("2026-10-14")]), float(pr[dates.index("2026-10-15")])
    for when, hh in (("during the checks", 12 * 60 + 10), ("after the last check", 15 * 60 + 40), ("in the evening", 20 * 60)):
        now = BZ.at_et("2026-10-14", hh)
        S = engine_at(now)
        st = BZ.state_text(S, now)
        f = BZ.day_filter(S["eng"], "2026-10-14", now=now)
        want = f"{r14:.2f} x" in st["text"] and f"{f['yday']:,.0f} pts < 0.8 x its 14-day mean {f['mean']:,.0f} pts" in st["text"]
        nx = ("The next trading day trades" in st["text"]) if hh >= 16 * 60 else True
        check(f"j. 2026-10-14 {when}: stage {st['stage']}, \"{st['text'][:150]}...\"", st["stage"] == "filtered" and want and nx
              and abs(f["ratio"] - r14) < 1e-3 and f["ok"] is False, st)
    nxt = BZ.day_filter(engine_at(BZ.at_et("2026-10-14", 20 * 60))["eng"], "2026-10-14", now=BZ.at_et("2026-10-14", 20 * 60))["next"]
    check(f"j. 2026-10-14 evening: the next day's ratio from today's final range = the research's ({nxt['ratio']} vs {r15:.3f})",
          nxt["final"] and abs(nxt["ratio"] - r15) < 1e-3 and nxt["ok"], nxt)
    now = BZ.at_et("2026-10-15", 12 * 60 + 10)
    S = engine_at(now)
    st = BZ.state_text(S, now)
    f = BZ.day_filter(S["eng"], "2026-10-15", now=now)
    check(f"j. 2026-10-15 (a trading day, {r15:.2f} x): not filtered, stage {st['stage']}; the day filter block says it trades",
          st["stage"] not in ("filtered",) and f["ok"] and "BLITZ trades today" in f["text"], st)
    now = BZ.at_et("2026-10-11", 20 * 60)                 # Sunday evening: the verdict is Monday's, never "skipped today"
    S = engine_at(now)
    st = BZ.state_text(S, now)
    r12 = float(pr[dates.index("2026-10-12")])
    check(f"j. Sunday 2026-10-11 evening: stage {st['stage']}, names the next session's verdict ({r12:.2f} x): \"{st['text'][:140]}\"",
          st["stage"] == "closed" and "next session" in st["text"] and "skipped today" not in st["text"] and f"{r12:.2f} x" in st["text"], st)
    S2 = BZ.step(None, df[df["time"] < BZ.at_et("2026-10-14", 20 * 60) - 60], BZ.at_et("2026-10-14", 20 * 60),
                 res={"trades": [], "state": {}, "signals": []}, second={"strategies": {}})
    cp = BZ.compact(S2)
    check("j. heartbeat compact carries day_filter (ratio, yesterday's range, the mean) and the filtered state text",
          (cp.get("day_filter") or {}).get("ok") is False and abs(cp["day_filter"]["ratio"] - r14) < 1e-3 and cp["state"]["stage"] == "filtered",
          {k: cp.get(k) for k in ("day_filter", "state")})


# ================================================================================================ i. wiring
def part_i(cloud=False):
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("i. .gitignore has data/blitz_state.json", "data/blitz_state.json" in gi.splitlines())
    ref = open(os.path.join(ROOT, "docs", "CLAUDE_REFERENCE.md"), encoding="utf-8").read()
    i = ref.find("## Second strategies")
    j = ref.find("\n## ", i + 5)
    check("i. docs/CLAUDE_REFERENCE.md: BLITZ entry in the Second strategies section (filter, 50K next to LIT)",
          i >= 0 and "BLITZ" in ref[i:j] and "engine/blitz.py" in ref[i:j] and "50K next to LIT" in ref[i:j] and "prng" in ref[i:j])
    changed = subprocess.run(["git", "status", "--porcelain", "--", "live_model.json", "live_model_lit.json", "live_model_engine.json",
                              "second_model.json", "engine/ninjatrader.py", "engine/account_b.py"], cwd=ROOT, capture_output=True, text=True).stdout
    check("i. live_model*.json, second_model.json, engine/ninjatrader.py, engine/account_b.py unchanged (git)", changed.strip() == "", changed)
    cm = open(os.path.join(ROOT, "tools", "cloud_monitor.py"), encoding="utf-8").read()
    check("i. cloud monitor: BLITZ step next to the ATLAS v2 shadow with LIT's run and the ATLAS ledgers, state \"blitz\", notices "
          "recorded unless blitz.push, README lines",
          "_blz.step(prev_b, _LIT_IN.get(\"df1\"), now" in cm and "res=res, second=second_block" in cm and 'new_state["blitz"]' in cm
          and "_blz.push_on()" in cm and "_blz.readme_lines(blitz)" in cm and cm.index("_blz.step(") > cm.index("_av2.step("))
    if not cloud:
        return
    tmp = tempfile.mkdtemp(prefix="blitz_cloud_")
    keep = {p: open(p, "rb").read() for p in (os.path.join(ROOT, "data", f) for f in ("VIX_1d.csv", "VXN_1d.csv", "CBOE_vol_1d.csv"))
            if os.path.exists(p)}
    try:
        t0 = time.time()
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join("tools", "cloud_monitor.py"), "--out", tmp], cwd=ROOT,
                           capture_output=True, text=True, timeout=1500)
        st = json.load(open(os.path.join(tmp, "state.json"), encoding="utf-8")) if os.path.exists(os.path.join(tmp, "state.json")) else {}
        b = st.get("blitz") or {}
        check(f"i. cloud dry run ({time.time() - t0:.0f} s): exit 0, state \"blitz\" written (paper, never routed, both ledgers, "
              f"{(b.get('warm') or {}).get('bars')} warm-up bars, last bar {f_et(b['eng']['last_t']) if (b.get('eng') or {}).get('last_t') else None})",
              r.returncode == 0 and b.get("v") == BZ.VERSION and b.get("paper") and b.get("never_routed") and not b.get("error")
              and "ledger50" in b and "acct50" in b and "BLITZ shadow failed" not in r.stdout, (r.returncode, r.stdout[-600:], r.stderr[-600:], b.get("error")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for p, bts in keep.items():
            with open(p, "wb") as fh:
                fh.write(bts)


# ================================================================================================ numbers
def numbers(D, S50):
    print("\nBLITZ 2026 paper numbers (the replay above; costs in; $150 a trade = the research table, 25K eval = the simulated "
          "Builder 25K at 40% of the room, max $600; 50K = the simulated funded 50K next to LIT, BLITZ's own P&L, no payouts):")
    print("| Span | Trades | /week | Win % | Avg R | PF | Net $150/trade | $/month | 25K eval sized | Eval path $ | Pass / fail+stuck "
          "| Path less $63 fees | $/month | 2-wk pass / fail | 50K + LIT trades | 50K $ | 50K $/month |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for nm, span in (("H1", H1), ("H2", H2)):
        d = D[nm]
        st, e = d["stats"], d["eval"]
        fees = e["evals_bought"] * BZ.PLAN["price"]
        r50 = [r for r in S50["ledger50"] if span[0] <= r["day"] <= span[1] and r["exit_kind"] != "SKIP" and int(r["qty"]) > 0]
        u50 = round(sum(float(r["usd"]) for r in r50))
        print(f"| 2026 {nm} | {st['n']} | {st['tpw']} | {st['win']} | {st['avg_r']:+.3f} | {st['pf']} | ${st['net']:+,} | ${st['per_month']:+,} | "
              f"{sum(1 for r in d['rows'] if int(r['qty']) > 0)} | ${d['net']:+,} | {e['b2b']} | ${round(d['net'] - fees):+,} | "
              f"${round((d['net'] - fees) / (d['sessions'] / 21)):+,} | {e['p10']} / {e['f10']} | {len(r50)} | ${u50:+,} | "
              f"${round(u50 / (d['sessions'] / 21)):+,} |")


def main():
    t0 = time.time()
    part_ab()
    part_c()
    D = part_d()
    S50 = part_e()
    part_f()
    part_g()
    part_h()
    part_j()
    part_i(cloud="--cloud" in sys.argv)
    numbers(D, S50)
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed in {time.time() - t0:.0f} s -> {'ALL PASS' if ok else 'FAILURES'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
