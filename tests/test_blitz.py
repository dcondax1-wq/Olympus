"""BLITZ, the scalper PAPER SHADOW (engine/blitz.py; research/writeups/scalp-momentum.md "na_scalp"). Paper only: never routed.

    python -X utf8 -m tests.test_blitz            # everything (~1 min)
    python -X utf8 -m tests.test_blitz --cloud    # + a cloud monitor dry run writing state "blitz" (~3 min more)

 a. parity, whole frame: engine/blitz.backtest on data/NQ_1m.csv (2026) = research/scalp/mo_best_trades.json trade for trade
    (entry_t, dir, entry, stop, exit, exit_kind, exit_t, pts, r): 481 trades.
 b. parity, live Engine: the same bars fed one closed 1m bar at a time (Engine.on_bar, no look-ahead) = the same 481 trades.
 c. live loop: the shadow polled like the PC bot (bars revealed as they close, random 1-7 minute gaps, a poll right after
    every check close, the state JSON-round-tripped every poll, a cold start warmed on the last 35 days) over 2026 H2 = the
    research trades of H2; data cut at random times (13:00, 11:31, 15:56 ...) never changes a trade that closed before the cut;
    a half day (no bar after 13:00) is flattened by the clock at 16:00 at the research's flat bar; pc_step (own file next to
    the bot state, kept in memory) = step.
 d. the paper eval: the shadow's simulated Builder 25K (30% of the room, max $600) = tools/scalp_mo_lib.run_eval's
    back-to-back path in H1 (from 2026-01-01) and H2 (from 2026-07-01): every sized trade, micros, $, pass / fail / stuck.
 e. never routed: engine/blitz.py imports / names no adapter, broker, NinjaTrader, guard, order or routing code; importing it
    and running a step loads no such module; the PC hook (engine/live.py + engine/bg_worker.py) hands it only the 1m bars.
 f. views: compact (heartbeat "blitz"), the heartbeat payload, Live View's purple layer (band lines, signals, PAPER position),
    the narrator (kind "blitz", strat scalp, PAPER, never pushed by default), card / notices / README lines.
 g. cheap per poll: a poll with a new bar and one without, after the warm-up.
 h. wiring: .gitignore has data/blitz_state.json, docs/CLAUDE_REFERENCE.md has the entry, live_model*.json / second_model.json
    untouched by BLITZ (git HEAD), the cloud monitor runs it next to the ATLAS v2 shadow (state "blitz").
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
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import blitz as BZ  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
REF_PATH = os.path.join(ROOT, "research", "scalp", "mo_best_trades.json")
H1 = ("2026-01-01", "2026-06-30")
H2 = ("2026-07-01", "2026-12-31")


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
    return _D["df"], _D["ref"]


def same(mine, ref, tol=1e-6) -> list:
    """Differences between our trades (entry_t / exit_t unix, dir +-1) and the research file's rows (ET strings)."""
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


def in_span(rows, span, key="entry_t"):
    a, z = span
    return [r for r in rows if a <= f_et(r[key])[:10] <= z]


def ref_in(ref, span):
    a, z = span
    return [r for r in ref if a <= r["entry_t"][:10] <= z]


# ================================================================================================ a + b
def part_ab():
    df, R = data()
    ref = R["trades"]
    check("a. research file: the NA scalp pick, 481 trades, the rule engine/blitz.py runs",
          R["name"] == BZ.PICK and len(ref) == 481 and R["rule"] == {k: BZ.RULE[k] for k in R["rule"]} and R["maxday"] == BZ.MAXDAY
          and R["day_stop_r"] == BZ.DAY_STOP_R, (R["rule"], R["maxday"], R["day_stop_r"]))
    t0 = time.time()
    T = BZ.backtest(df)
    bad = same(T, ref)
    check(f"a. backtest (whole frame) = research trade for trade: {len(T)} trades ({time.time() - t0:.1f} s)", not bad, bad[:3])
    t0 = time.time()
    S = BZ.replay_2026(first_run="2025-12-28")
    L = S["ledger"]
    bad = same(L, ref)
    check(f"b. live Engine, one closed bar at a time = research trade for trade: {len(L)} trades ({time.time() - t0:.1f} s)", not bad, bad[:3])
    ek = collections.Counter(r["exit_kind"] for r in L)
    check("b. exits as the research: 344 time, 105 stop (first or trailed), 32 flat", ek == {"time": 344, "stop": 105, "flat": 32}, ek)
    per_day = collections.Counter(r["day"] for r in L)
    check("b. never more than 6 a day, one position at a time", max(per_day.values()) <= 6 and
          all(L[i]["exit_t"] <= L[i + 1]["entry_t"] for i in range(len(L) - 1)))
    return S


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
        if wk and 650 <= mod <= 970:
            out.append(t)
            t += int(rng.integers(1, 8)) * 60 + int(rng.integers(0, 50))
        else:
            out.append(t)
            t += 1800
    for d in sorted({BZ.et_date(int(x)) for x in df["time"].to_numpy()}):
        if a_day <= d <= z_day:
            out += [BZ.at_et(d, m + 1) + 2 for m in BZ.CHECKS]
    return sorted(set(out))


def live_loop(df, first_day, last_day, seed=7, roundtrip=True):
    times = poll_times(df, first_day, last_day, seed)
    tt = df["time"].to_numpy(np.int64)
    prev = None
    fr = times[0]
    n = 0
    for now in times:
        k = int(np.searchsorted(tt, now - 60, side="right"))           # the bars that have closed by now
        view = df.iloc[:k]
        S = BZ.step(prev, view, now, first_run=fr)
        prev = json.loads(json.dumps(S)) if roundtrip else S
        n += 1
    return prev, n


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
    diff = []
    for cut in cuts:
        E = BZ.Engine()
        k = int(np.searchsorted(tt, cut - 60, side="right"))
        got = {}
        for i in range(k):
            for x in E.on_bar(int(tt[i]), df["open"].iat[i], df["high"].iat[i], df["low"].iat[i], df["close"].iat[i]):
                if x["ev"] == "exit":
                    got[x["entry_t"]] = x
        for et_, r in full.items():
            if r["exit_t"] <= cut and r["exit_kind"] != "flat":
                x = got.get(et_)
                if x is None or abs(x["exit"] - r["exit"]) > 1e-9 or x["kind"] != r["exit_kind"]:
                    diff.append((f_et(cut), f_et(et_)))
        extra = [e for e in got if e not in full]
        diff += [("extra", f_et(cut), f_et(e)) for e in extra]
    check(f"c. data cut at {len(cuts)} random times: every trade closed before the cut is the same, none extra", not diff, diff[:4])
    # a half day: bars stop at 13:00 (no bar until 18:00): the clock flattens at 16:00 ET at the research's flat bar
    day = "2026-08-13"                                                  # a 12:30 paper entry is open at the 13:00 halt
    cut_t = BZ.at_et(day, 780)
    rest = df[(df["time"] < cut_t) | (df["time"] >= BZ.at_et(day, 18 * 60))].reset_index(drop=True)
    T = BZ.backtest(rest[rest["time"] < BZ.at_et("2026-08-14", 0)])
    ref_day = [r for r in T if r["day"] == day]
    E = BZ.Engine()
    sub = rest[rest["time"] < BZ.at_et(day, 18 * 60)]
    out = []
    for r in sub.itertuples():
        out += E.on_bar(int(r.time), r.open, r.high, r.low, r.close)
    n_open_before = 1 if E.s["pos"] else 0
    out += E.on_clock(BZ.at_et(day, 959))
    mid = 1 if E.s["pos"] else 0
    out += E.on_clock(BZ.at_et(day, 961))
    ex = [x for x in out if x["ev"] == "exit" and x["date"] == day]
    rel = {x["entry_t"]: x["kind"] for x in out if x["ev"] == "relabel"}
    mine = [(x["entry_t"], rel.get(x["entry_t"], x["kind"]), round(x["exit"], 6)) for x in ex]
    refd = [(r["entry_t"], r["exit_kind"], round(r["exit"], 6)) for r in ref_day]
    check(f"c. half day {day} (bars stop 13:00): {len(mine)} trades = the whole-frame run's; the clock closes the day at 16:00 ET "
          f"(open at the halt {n_open_before}, still open at 15:59 {mid})", mine == refd and E.s["closed"] and not E.s["pos"]
          and n_open_before == 1 and mid == 1 and refd and refd[-1][1] == "flat", (mine, refd))
    # pc_step = step (own file, in memory between polls)
    tmp = tempfile.mkdtemp(prefix="blitz_pc_")
    try:
        path = BZ.pc_path(os.path.join(tmp, "live_state.json"))
        tt_ = df["time"].to_numpy(np.int64)
        prev = None
        a_ = BZ.at_et("2026-09-14", 10 * 60 + 50)
        polls = [a_ + 60 * i + 3 for i in range(0, 330, 3)]
        ok = True
        S2 = None
        for now in polls:
            k = int(np.searchsorted(tt_, now - 60, side="right"))
            S1 = BZ.pc_step(path, df.iloc[:k], now)
            S2 = BZ.step(prev, df.iloc[:k], now, first_run=polls[0])
            prev = S2
            a1 = {k_: v for k_, v in S1.items() if k_ not in ("saved_t",)}
            a2 = {k_: v for k_, v in S2.items() if k_ not in ("saved_t",)}
            if json.dumps(a1, sort_keys=True, default=str) != json.dumps(a2, sort_keys=True, default=str):
                ok = False
                break
        on_disk = json.load(open(path, encoding="utf-8"))
        check(f"c. pc_step (file {os.path.basename(path)} next to the bot state) = step over {len(polls)} polls of 2026-09-14 "
              f"({len(S2['ledger'])} paper trades), saved on disk", ok and on_disk["eng"]["last_t"] == S2["eng"]["last_t"]
              and path.endswith(os.path.join(os.path.basename(tmp), "blitz_state.json")))
        os.remove(path)
        S3 = BZ.pc_step(path, df.iloc[:10], polls[0])
        check("c. pc_step never raises (a broken frame -> an error state, not an exception)",
              isinstance(BZ.pc_step(path, "not a frame", polls[0] + 60), dict) and isinstance(S3, dict))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return S


# ================================================================================================ d. paper eval
def part_d():
    from tools import scalp_mo_pick as P
    from tools import scalp_mo_lib as Lb
    B, T = P.trades("na_scalp", 1)
    out = {}
    for nm, span in (("H1", H1), ("H2", H2)):
        S_ = Lb.sessions(B, nm)
        Ts = [t for t in T if S_[0] <= t["day"] <= S_[-1]]
        stuck = 2.0 * float(np.median([t["risk_pm"] for t in Ts]))
        e = Lb.eval_score(Ts, S_, "25k", BZ.PLAN["f"], BZ.PLAN["cap"])
        by = collections.defaultdict(list)
        for t in Ts:
            by[t["day"]].append(t)
        K, k, n = [], 0, collections.Counter()
        while k < len(S_):
            r, used = Lb.run_eval(S_[k:], by, Lb.PLANS["25k"], BZ.PLAN["f"], BZ.PLAN["cap"], len(S_) - k, keep=K, stuck=stuck)
            n[r] += 1
            if r == "OPEN":
                break
            k += used
        S = BZ.replay_2026(first_run=span[0], stuck=stuck)
        rows = [r for r in S["ledger"] if r["day"] <= span[1]]
        sized = [r for r in rows if int(r["qty"]) > 0]
        mine = [(r["entry_t"], int(r["qty"]), round(float(r["usd"]), 2)) for r in sized]
        refk = [(int(t["entry_t"]), int(t["qty"]), round(float(t["pnl"]), 2)) for t in K]
        ev = [x for x in S["evals"] if x["end"] <= span[1]]
        cnt = (sum(1 for x in ev if x["result"] == "PASS"), sum(1 for x in ev if x["result"] in ("FAIL", "STUCK")))
        b2b = tuple(int(x) for x in e["b2b"].split("/"))
        bad = [(a, b) for a, b in zip(mine, refk) if a != b]
        net = round(sum(float(r["usd"]) for r in sized))
        check(f"d. {nm}: paper 25K eval = research back-to-back path: {len(mine)} sized trades, every micro / $; "
              f"pass / fail+stuck {cnt[0]}/{cnt[1]} = {e['b2b']}; path ${net:+,} = ${e['path_net']:+,}",
              len(mine) == len(refk) and not bad and cnt == b2b and net == e["path_net"], (bad[:2], len(mine), len(refk), cnt, e["b2b"]))
        st = Lb.stats(T, S_, 150.0, 20)
        out[nm] = {"S": S, "rows": rows, "eval": e, "stats": st, "sessions": len(S_), "evals": ev, "net": net}
    S = BZ.replay_2026(first_run=H1[0])
    check("d. the default stuck room ($243.20 = 2 x the 2026 median stop-out) is the research's over all 2026",
          abs(BZ.STUCK_ROOM - 2.0 * float(np.median([t["risk_pm"] for t in T]))) < 0.01 and S["stuck"] == BZ.STUCK_ROOM)
    return out


# ================================================================================================ e. never routed
FORBID_MODS = ("ninjatrader", "tradovate", "account_b", "accounts", "guards", "live", "multi_account", "sizing", "broker_balance",
               "alerts", "alerts_plus", "remote_ctl", "golive", "go", "botctl", "lit_live", "second", "fill_audit")
FORBID_NAMES = {"route", "_route", "place_order", "submit_order", "send_order", "flatten", "oif", "OIF", "adapter", "Adapter",
                "LiveBot", "BOT", "ninjatrader", "tradovate", "write_oif", "arm", "set_route"}


def part_e():
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
    allowed = {"__future__:annotations", "datetime", "json", "os", "warnings", "zoneinfo:ZoneInfo", "numpy", "pandas", "sys",
               ".:push"}
    check("e. engine/blitz.py imports only the standard library, numpy / pandas and engine/push (cloud notices text only)",
          mods <= allowed, sorted(mods - allowed))
    hit = sorted(names & FORBID_NAMES)
    check("e. engine/blitz.py names no adapter / order / routing call", not hit, hit)
    import io
    import tokenize
    code_only = " ".join(tok.string for tok in tokenize.generate_tokens(io.StringIO(src).readline)
                         if tok.type not in (tokenize.STRING, tokenize.COMMENT)).lower()
    check("e. no broker words in engine/blitz.py code (strings / comments aside): ninjatrader, tradovate, oif, place order, outgoing",
          not any(w in code_only for w in ("ninjatrader", "tradovate", "oif", "place_order", "outgoing", "adapter")))
    code = ("import sys, json; sys.path.insert(0, %r); import pandas as pd; from engine import blitz as BZ; "
            "df = pd.read_csv(%r).tail(60000).reset_index(drop=True); now = int(df['time'].iloc[-1]) + 62; "
            "S = BZ.step(None, df, now); BZ.compact(S); BZ.card(S); BZ.state_text(S); BZ.readme_lines(S); "
            "import tempfile, os; d = tempfile.mkdtemp(); BZ.pc_step(os.path.join(d, 'blitz_state.json'), df, now); "
            "print(json.dumps(sorted(m for m in sys.modules if m.startswith('engine'))))") % (ROOT, os.path.join(ROOT, "data", "NQ_1m.csv"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True, timeout=300)
    try:
        loaded = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        loaded = None
    bad = [m for m in (loaded or []) if m.split(".")[-1] in FORBID_MODS or m in ("engine.push",)]
    check("e. a step / pc_step / views load no order, broker, guard or push module (fresh process)",
          loaded is not None and loaded == ["engine", "engine.blitz"] and not bad, (loaded, bad, r.stderr[-400:]))
    live = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    bgw = open(os.path.join(ROOT, "engine", "bg_worker.py"), encoding="utf-8").read()
    i = live.index("def _second_tick")
    body = live[i:live.index("def _second_cfg")]
    check("e. PC hook: the paper thread / worker job call pc_step(<state dir>/blitz_state.json, the 1m bars, now) only, after LIT's routing",
          "_blz.pc_step(_blz.pc_path(self.state_path), df1, now)" in body and '_blz.pc_step(a["blitz_path"], df1, a["now"])' in bgw
          and '"blitz_path": _blz.pc_path(self.state_path)' in live
          and live.index("self._second_tick(df_full, df1, res, now)") > live.index("self._route_signals(res, sym, now, secs)"))


# ================================================================================================ f. views
def fake_state():
    """A shadow state polled through 2026-09-14 13:20 ET (a paper trade open then), plus its full day."""
    df, _ = data()
    tt = df["time"].to_numpy(np.int64)
    a_ = BZ.at_et("2026-09-14", 10 * 60 + 50)
    prev = None
    S_open = None
    for now in [a_ - 86400 * 2] + [a_ + 60 * i + 3 for i in range(0, 330)]:
        k = int(np.searchsorted(tt, now - 60, side="right"))
        prev = BZ.step(prev, df.iloc[:k], now, first_run=a_ - 86400 * 2)
        if prev.get("open") and S_open is None and BZ.et_parts(now)[1] > 700:
            S_open = copy.deepcopy(prev)
    return prev, S_open


def part_f():
    from engine import heartbeat as HB
    from engine import liveview_api as LV
    from engine import narrator as N
    S, S_open = fake_state()
    c = BZ.compact(S)
    js = json.dumps(c, default=str)
    check(f"f. compact (heartbeat \"blitz\"): paper, never routed, state text, today's trades, eval, band; {len(js):,} bytes",
          c["paper"] and c["never_routed"] and c["state"]["text"] and c["today"] and c["eval"]["plan"] == "MFFU Builder 25K"
          and c["band"] and c["band"].get("checks") and len(js) < 12000, (len(js), c.get("state")))
    bot = SimpleNamespace(state={}, cfg={"adapter": "paper"}, running=True, blitz=S)
    pl = HB._blitz(bot)
    check("f. heartbeat payload block \"blitz\" = compact(LiveBot.blitz); None before the first run",
          pl == c and HB._blitz(SimpleNamespace()) is None)
    src = open(os.path.join(ROOT, "engine", "heartbeat.py"), encoding="utf-8").read()
    check("f. the heartbeat payload carries \"blitz\"", '"blitz": _blitz(self.bot)' in src)
    # Live View: purple layer
    now = BZ.at_et("2026-09-14", 13 * 60 + 20)
    for S_, label in ((S_open, "open trade"), (S, "day end")):
        if S_ is None:
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
            check("f. Live View purple layer (open trade): BLITZ, not a placeholder, band lines, PAPER entry / stop lines, position "
                  "with paper micros, signals", sc["name"] == "BLITZ" and not sc["placeholder"] and {"blz_up", "blz_lo", "blz_entry", "blz_stop"} <= ids
                  and sc["position"] and sc["position"]["paper"] and "PAPER" in next(x["label"] for x in sc["lines"] if x["id"] == "blz_entry")
                  and sc["signals"] and sc["color"] == "#7c3aed" and sc["members"][0]["short"] == "BLITZ", (ids, sc.get("position"), sc.get("error")))
        else:
            check("f. Live View purple layer (day end): today's PAPER entries / exits as marks, band of every check, no position",
                  any(m["kind"] == "exit" and m.get("paper") for m in sc["marks"]) and sc["band"] and len(sc["band"]) == len(BZ.CHECKS)
                  and sc["position"] is None and "never routed" in sc["text"], (sc.get("marks"), sc.get("error")))
        check(f"f. Live View ({label}): no real size claimed (every BLITZ line / mark says PAPER)",
              all(("PAPER" in (x.get("label") or "")) or x["id"] in ("blz_up", "blz_lo", "blz_o0", "blz_trail") for x in sc["lines"])
              and "I ACCEPT" not in txt)
    # narrator
    b = SimpleNamespace(running=True, cfg={"adapter": "paper"}, state={}, brain=None, second=None, acct_b=None, ledger=[], health={},
                        kill=False, clock=lambda: int(S["t"]), blitz=S)
    nar = N.Narrator()
    new = nar.observe(b, int(S["t"]))
    bz = [m for m in new if m["kind"] == "blitz"]
    rows = BZ.today_rows(S)
    check(f"f. narrator: {len(bz)} BLITZ messages (signals, PAPER entries / exits), strat scalp, kind blitz",
          bz and all(m["strat"] == "scalp" for m in bz) and sum(1 for m in bz if "PAPER entry" in m["title"]) == len(rows)
          and sum(1 for m in bz if "PAPER exit" in m["title"]) == sum(1 for r in rows if r["exit_kind"] != "OPEN")
          and all("PAPER" in m["title"] or "paper" in m["text"] for m in bz), [m["title"] for m in bz][:6])
    check("f. narrator: kind blitz is never pushed by default", N.push_prefs(os.path.join(tempfile.gettempdir(), "none_blitz.json"))["blitz"] is False
          and N.KINDS["blitz"][1] is False)
    sent = []
    nar2 = N.Narrator()
    nar2.observe(b, int(S["t"]), push=True, send=lambda m, bot: sent.append(m["kind"]) or True,
                 prefs=N.push_prefs(os.path.join(tempfile.gettempdir(), "none_blitz.json")))
    check("f. narrator with pushes on (the real bot's tick): no BLITZ push", "blitz" not in sent, sent)
    check("f. narrator: second look gives nothing new (stable keys)", nar.observe(b, int(S["t"])) == [])
    # card / notices / readme
    cd = BZ.card(S)
    check("f. card: paper, never routed, the research numbers, today's trades", cd["paper"] and cd["never_routed"] and cd["research"]["H2"]["pf"] == 1.22
          and cd["today"] and cd["source"] == "cloud")
    nt = BZ.notices(S, 0)
    check("f. cloud notices: kind second, titled BLITZ PAPER ..., one per entry / exit",
          nt and all(n["kind"] == "second" and n["title"].startswith("BLITZ PAPER") for n in nt) and
          sum(1 for n in nt if n["key"].startswith("blitz:fill:")) == len(S["ledger"]), [n["title"] for n in nt][:4])
    rl = BZ.readme_lines(S)
    check("f. README lines: label, eval, paper trades", rl and any("never routed" in x for x in rl) and any("Eval" in x for x in rl))


# ================================================================================================ g. speed
def part_g():
    df, _ = data()
    tt = df["time"].to_numpy(np.int64)
    tmp = tempfile.mkdtemp(prefix="blitz_speed_")
    try:
        path = os.path.join(tmp, "blitz_state.json")
        a_ = BZ.at_et("2026-10-14", 11 * 60)
        k = int(np.searchsorted(tt, a_ - 60, side="right"))
        t0 = time.perf_counter()
        BZ.pc_step(path, df.iloc[:k], a_)
        warm = time.perf_counter() - t0
        new_bar, same_bar = [], []
        for i in range(1, 41):
            now = a_ + 60 * i + 2
            k = int(np.searchsorted(tt, now - 60, side="right"))
            t0 = time.perf_counter()
            BZ.pc_step(path, df.iloc[:k], now)
            new_bar.append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            BZ.pc_step(path, df.iloc[:k], now + 5)
            same_bar.append((time.perf_counter() - t0) * 1000)
        m1, m2 = float(np.median(new_bar)), float(np.median(same_bar))
        check(f"g. cheap per poll: cold start {warm * 1000:.0f} ms (35 days of 1m bars), then a poll with a new bar {m1:.1f} ms, "
              f"without {m2:.1f} ms (median)", warm < 5.0 and m1 < 40 and m2 < 25, (warm, m1, m2))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================ h. wiring
def part_h(cloud=False):
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check(".gitignore has data/blitz_state.json", "data/blitz_state.json" in gi.splitlines())
    ref = open(os.path.join(ROOT, "docs", "CLAUDE_REFERENCE.md"), encoding="utf-8").read()
    i = ref.find("## Second strategies")
    j = ref.find("\n## ", i + 5)
    check("docs/CLAUDE_REFERENCE.md: BLITZ entry in the Second strategies section", i >= 0 and "BLITZ" in ref[i:j] and "engine/blitz.py" in ref[i:j])
    changed = subprocess.run(["git", "status", "--porcelain", "--", "live_model.json", "live_model_lit.json", "live_model_engine.json",
                              "second_model.json", "engine/ninjatrader.py", "engine/account_b.py"], cwd=ROOT, capture_output=True, text=True).stdout
    check("live_model*.json, second_model.json, engine/ninjatrader.py, engine/account_b.py unchanged (git)", changed.strip() == "", changed)
    cm = open(os.path.join(ROOT, "tools", "cloud_monitor.py"), encoding="utf-8").read()
    check("cloud monitor: BLITZ step next to the ATLAS v2 shadow, state \"blitz\", notices recorded unless blitz.push, README lines",
          "_blz.step(prev_b, _LIT_IN.get(\"df1\"), now" in cm and 'new_state["blitz"]' in cm and "_blz.push_on()" in cm
          and "_blz.readme_lines(blitz)" in cm and cm.index("_blz.step(") > cm.index("_av2.step("))
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
        check(f"cloud dry run ({time.time() - t0:.0f} s): exit 0, state \"blitz\" written (paper, never routed, "
              f"{(b.get('warm') or {}).get('bars')} warm-up bars, last bar {f_et(b['eng']['last_t']) if (b.get('eng') or {}).get('last_t') else None})",
              r.returncode == 0 and b.get("v") == BZ.VERSION and b.get("paper") and b.get("never_routed") and not b.get("error")
              and "BLITZ shadow failed" not in r.stdout, (r.returncode, r.stdout[-600:], r.stderr[-600:], b.get("error")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for p, bts in keep.items():
            with open(p, "wb") as fh:
                fh.write(bts)


# ================================================================================================ numbers
def numbers(D):
    print("\nBLITZ 2026 paper numbers (the replay above; costs in; $150 a trade = the research table, paper eval = the simulated "
          "Builder 25K at 30% of the room, max $600):")
    print("| Span | Trades | /week | Win % | Avg R | PF | Net $150/trade | $/month | Paper eval trades sized | Eval path $ | "
          "Pass / fail+stuck | Evals bought | Path less $63 fees | $/month | 2-wk pass / fail |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for nm in ("H1", "H2"):
        d = D[nm]
        st, e = d["stats"], d["eval"]
        print(f"| 2026 {nm} | {st['n']} | {st['tpw']} | {st['win']} | {st['avg_r']:+.3f} | {st['pf']} | ${st['net']:+,} | ${st['per_month']:+,} | "
              f"{sum(1 for r in d['rows'] if int(r['qty']) > 0)} | ${d['net']:+,} | {e['b2b']} | {e['evals_bought']} | "
              f"${e['path_net_less_fees']:+,} | ${round(e['path_net_less_fees'] / (d['sessions'] / 21)):+,} | {e['p10']} / {e['f10']} |")


def main():
    t0 = time.time()
    part_ab()
    part_c()
    D = part_d()
    part_e()
    part_f()
    part_g()
    part_h(cloud="--cloud" in sys.argv)
    numbers(D)
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed in {time.time() - t0:.0f} s -> {'ALL PASS' if ok else 'FAILURES'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
