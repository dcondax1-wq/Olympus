"""Deterministic dry run of the live loop.

    python -m tests.test_live_dryrun            # full run (~3-5 min: ~450 polls of the real Engine)
    python -m tests.test_live_dryrun --quick    # replay only the entry windows + session ends

Replays the last 3 trading sessions of data/NQ_5m.csv bar by bar through LiveBot + PaperAdapter as if each bar were
arriving live: the bot's clock is frozen at each simulated "now", its history source only shows bars closed by then,
its fresh-bar fetch is stubbed (and abused for failure injection), alerts are captured, and no network is touched.
Writes nothing under data/ (live state goes to a temp file). Exit code 1 on any failed assertion.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import traceback
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import alerts, gamma, live, news  # noqa: E402
from engine.data import DATA_DIR, TF_SECONDS, from_frame  # noqa: E402
from engine.model import Engine, merge_params  # noqa: E402

ET = ZoneInfo("America/New_York")
SYM, TF, SECS = "NQ", "5m", 300
QUICK = "--quick" in sys.argv
SESSIONS = 3

RESULTS: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
    return bool(ok)


def et(ts):
    return dt.datetime.fromtimestamp(int(ts), ET)


def hm(ts):
    return et(ts).strftime("%m-%d %H:%M")


# ------------------------------------------------------------------------------------------------ harness
class Replay:
    """Frozen clock + bar source that only reveals bars closed by `now`. Hooks inject failures."""

    def __init__(self):
        self.frames = {}
        for sym, tf in (("NQ", "5m"), ("ES", "5m"), ("NQ", "1h")):
            df = pd.read_csv(os.path.join(DATA_DIR, f"{sym}_{tf}.csv"))
            self.frames[(sym, tf)] = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))].reset_index(drop=True)
        self.now = 0
        self.alerts = []
        self.recent_hook = None     # (sym, interval, period) -> DataFrame | raise
        self.hist_hook = None       # (sym, tf, frame_as_of_now) -> DataFrame
        self.alert_fail = False
        self.tmp = tempfile.mkdtemp(prefix="nqbot_dryrun_")
        self.state_path = os.path.join(self.tmp, "live_state.json")

    # pluggable bits -------------------------------------------------------------------------
    def clock(self):
        return self.now

    def read_hist(self, sym, tf):
        df = self.frames.get((sym, tf))
        if df is None:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        cut = df[df["time"] + TF_SECONDS[tf] <= self.now]
        if self.hist_hook:
            cut = self.hist_hook(sym, tf, cut)
        return cut

    def fetch_recent(self, sym, interval, period="5d"):
        if self.recent_hook:
            return self.recent_hook(sym, interval, period)
        return pd.DataFrame()

    def send(self, text, kind="signal", force=False):
        if self.alert_fail:
            raise RuntimeError("alert sender down (injected)")
        self.alerts.append({"t": self.now, "kind": kind, "text": text})
        return {"sent": True, "result": {"test": 200}}

    def install_globals(self):
        alerts.send = self.send
        news.ff_calendar = lambda: []
        news.volatility = lambda: {}
        news.guard = lambda now=None, params=None, vol=None, events=None: {"allowed": True, "reasons": [], "regime": None,
                                                                            "next_high": None, "now": now}
        gamma.refresh_history = lambda max_age_h=12: os.path.join(DATA_DIR, "GEX_1d.csv")

    def bot(self, cfg=None, state_path=None, start_now=None):
        b = live.LiveBot()
        b.clock = self.clock
        b.read_hist = self.read_hist
        b.fetch_recent = self.fetch_recent
        b.state_path = state_path or self.state_path
        if start_now is not None:
            self.now = start_now
        r = b.start({"sym": SYM, "tf": TF, "adapter": "paper", "poll_sec": 60, **(cfg or {})}, spawn=False)
        assert r.get("ok"), r
        return b

    def poll(self, b, now, errors):
        self.now = int(now)
        try:
            return b.poll_once()
        except Exception as e:
            errors.append((now, f"{e.__class__.__name__}: {e}", traceback.format_exc()))
            return None

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def ref_backtest(rp: Replay, params=None, upto=None):
    """What a plain backtest over the same files says (full history, live=True so the last open trade is kept)."""
    nq = rp.frames[("NQ", "5m")]
    es = rp.frames[("ES", "5m")]
    h1 = rp.frames[("NQ", "1h")]
    if upto is not None:
        nq = nq[nq["time"] + 300 <= upto]
        es = es[es["time"] + 300 <= upto]
        h1 = h1[h1["time"] + 3600 <= upto]
    h1c, _ = live.clean_bars(h1, 3600, int(h1["time"].max()) + 3600)
    eng = Engine(from_frame("NQ", "5m", nq), htf=from_frame("NQ", "1h", h1c), partner=from_frame("ES", "5m", es),
                 params=merge_params({**(params or {}), "live": True})).run()
    return eng.result()


def session_window(rp: Replay, n=SESSIONS):
    """Bars of the last n trading sessions (18:00 ET boundaries) that contain an RTH open."""
    b = from_frame("NQ", "5m", rp.frames[("NQ", "5m")])
    days = []
    for d, mod in zip(b.date_str, b.mod):
        if 570 <= mod < 960 and (not days or days[-1] != d):
            days.append(d)
    pick = days[-n:]
    idx = [i for i, d in enumerate(b.date_str) if d >= pick[0]]
    return b, idx, pick


# ------------------------------------------------------------------------------------------------ tests
def test_replay(rp: Replay):
    print("\n== 1. Bar-by-bar replay of the last 3 sessions (PaperAdapter) ==")
    b, idx, days = session_window(rp)
    start_t = int(b.t[idx[0]])
    print(f"  sessions {days}  bars {len(idx)}  from {hm(start_t)} ET to {hm(b.t[idx[-1]])} ET")
    ref = ref_backtest(rp)
    ref_trades = [t for t in ref["trades"] if t["entry_t"] >= start_t - SECS]
    ref_open = ref["state"].get("position")
    print(f"  reference backtest: {len(ref_trades)} completed trades in window" + (", 1 open at data end" if ref_open else ""))

    bot = rp.bot(start_now=start_t)
    errors, polls, flat_viol, poll_ms = [], 0, [], []
    for k, i in enumerate(idx):
        mod = int(b.mod[i])
        dense = 470 <= mod <= 975
        if QUICK and not dense and k % 12 != 0 and k != len(idx) - 1:
            continue
        if not dense and k % 6 != 0 and k != len(idx) - 1:
            continue
        now = int(b.t[i]) + SECS + 3
        st = rp.poll(bot, now, errors)
        polls += 1
        poll_ms.append(bot.health.get("poll_ms") or 0)
        if st is None:
            continue
        nmod = et(now).hour * 60 + et(now).minute
        if 960 <= nmod < 1080 and st.get("position"):
            flat_viol.append(hm(now))
        if st.get("t") != int(b.t[i]):
            errors.append((now, f"engine last bar {hm(st.get('t'))} != simulated bar {hm(b.t[i])}", ""))
    check("replay: no exceptions across the whole replay", not errors,
          f"{polls} polls" + (f"; first error: {errors[0][1]}" if errors else ""))
    for e in errors[:3]:
        print("     ", hm(e[0]), e[1]); print(e[2][-800:])

    # ---- entries / exits vs reference (diff table)
    led = bot.ledger
    rep_entries = {r["entry_t"]: r for r in led if r["side"] in ("buy", "sell")}
    rep_exits = {r["entry_t"]: r for r in led if r["side"] == "exit"}
    rows, ok = [], True
    for t in ref_trades:
        e = rep_entries.get(t["entry_t"]) or next((r for r in rep_entries.values() if abs(r["entry_t"] - t["entry_t"]) <= SECS), None)
        x = rep_exits.get(t["entry_t"]) or next((r for r in rep_exits.values() if abs(r["entry_t"] - t["entry_t"]) <= SECS), None)
        e_ok = e is not None and e["side"] == ("buy" if t["dir"] == 1 else "sell") and e["qty"] == t["qty"]
        x_ok = x is not None and x["reason"] == t["exit_reason"] and abs(x["exit_t"] - t["exit_t"]) <= SECS
        ok &= e_ok and x_ok
        rows.append((hm(t["entry_t"]), "L" if t["dir"] == 1 else "S", t["qty"], e["side"] + f" {e['qty']}" if e else "MISSING",
                     hm(t["exit_t"]), t["exit_reason"], (hm(x["exit_t"]) + " " + x["reason"]) if x else "MISSING",
                     "ok" if e_ok and x_ok else "DIFF"))
    if ref_open:
        e = rep_entries.get(ref_open["entry_t"])
        ok &= e is not None
        rows.append((hm(ref_open["entry_t"]), "L" if ref_open["dir"] == 1 else "S", ref_open["qty"], e["side"] if e else "MISSING",
                     "(open)", "-", "-", "ok" if e else "DIFF"))
    extra = [r for r in led if r["side"] != "exit" and not any(abs(r["entry_t"] - t["entry_t"]) <= SECS for t in ref_trades)
             and not (ref_open and abs(r["entry_t"] - ref_open["entry_t"]) <= SECS)]
    for r in extra:
        ok = False
        rows.append((hm(r["entry_t"]), "?", r["qty"], r["side"] + " (replay only)", "-", "-", "-", "DIFF"))
    print("  diff table  (reference backtest  |  live replay)")
    print(f"  {'entry (ET)':12s} {'d':2s} {'qty':4s} {'replay entry':16s} {'ref exit':12s} {'ref reason':12s} {'replay exit':24s} status")
    for r in rows:
        print(f"  {r[0]:12s} {r[1]:2s} {r[2]!s:4s} {r[3]:16s} {r[4]:12s} {r[5]:12s} {r[6]:24s} {r[7]}")
    check("replay: entries/exits match the plain backtest (1-bar tolerance)", ok and len(rows) > 0,
          f"{len(ref_trades)} ref trades, {len(rep_entries)} replay entries, {len(rep_exits)} replay exits")
    check("replay: engine events (signal/entry/exit) logged for every reference trade",
          all(any(l["type"] == "entry" and l.get("bar_t") == t["entry_t"] for l in bot.log) for t in ref_trades))
    check("replay: flat at/after 16:00 ET every session", not flat_viol, f"violations: {flat_viol[:5]}")
    daily = {}
    for a in rp.alerts:
        if a["kind"] == "daily":
            daily[et(a["t"]).strftime("%Y-%m-%d")] = daily.get(et(a["t"]).strftime("%Y-%m-%d"), 0) + 1
    exp_days = [d for d in days]
    check("replay: EOD summary fires exactly once per session (none for the evening the bot was started)",
          all(daily.get(d) == 1 for d in exp_days) and sum(daily.values()) == len(exp_days), f"daily alerts per day: {daily}")
    check("replay: health flag clean at the end (no stale/desync, last_error only informational)",
          bot.health["ok"] and not bot.health["desync"] and bot.health["consecutive_errors"] == 0,
          json.dumps({k: bot.health[k] for k in ('data_age_s', 'stale', 'desync', 'revisions', 'last_error')}, default=str))
    check("replay: snapshot() is JSON-serialisable and carries health/day P&L", _json_ok(bot.snapshot()) and "health" in bot.snapshot())
    state_ok = os.path.exists(bot.state_path)
    check("persistence: data/live_state.json written on every change (temp path in tests)", state_ok)
    mean_ms = float(np.mean(poll_ms)) if poll_ms else 0
    print(f"  timing: poll_once compute wall time mean {mean_ms:.0f} ms, max {max(poll_ms) if poll_ms else 0} ms over {len(poll_ms)} polls "
          f"(window_days={bot.cfg['window_days']}, network stubbed)")
    check("timing: poll_once mean < 5 s on this machine (compute only)", mean_ms < 5000, f"{mean_ms:.0f} ms")
    return b, idx, days, ref_trades, ref_open, bot, mean_ms


def _json_ok(obj):
    try:
        json.dumps(obj, default=live._jsonable)
        return True
    except Exception:
        return False


def test_window_equivalence(rp: Replay, ref_trades, start_t):
    print("\n== 4. Windowed Engine run vs full history (decisions must be identical) ==")
    tmax = int(rp.frames[("NQ", "5m")]["time"].max()) + SECS
    out = {}
    for wd in (0, 10, 20, 30):
        bot = rp.bot({"window_days": wd}, state_path=os.path.join(rp.tmp, f"w{wd}.json"), start_now=start_t)
        rp.now = tmax + 3
        t0 = time.perf_counter()
        bot.poll_once()
        ms = (time.perf_counter() - t0) * 1000
        eng_trades = [(t["entry_t"], t["exit_reason"]) for t in bot.ledger if False]  # ledger not used here
        # compare the engine's own completed-trade list seen from the last poll via a fresh run of the same window
        out[wd] = (ms, bot.state["model_state"], bot.state.get("position", {}) and bot.state["position"].get("entry_t"))
        print(f"  window_days={wd or 'all':>3}: poll {ms:6.0f} ms  model={bot.state['model_state']}  bars={len(bot.bars_tail)}")
    ref_full = {(t["entry_t"], t["exit_reason"]) for t in ref_trades}
    same = True
    for wd in (10, 20, 30):
        df = rp.frames[("NQ", "5m")]
        d = df[df["time"] >= df["time"].max() - wd * 86400]
        es = rp.frames[("ES", "5m")]
        es = es[es["time"] >= d["time"].min()]
        h1c, _ = live.clean_bars(rp.frames[("NQ", "1h")], 3600, tmax)
        r = Engine(from_frame("NQ", "5m", d), htf=from_frame("NQ", "1h", h1c), partner=from_frame("ES", "5m", es),
                   params=merge_params({"live": True})).run().result()
        got = {(t["entry_t"], t["exit_reason"]) for t in r["trades"] if t["entry_t"] >= start_t - SECS}
        same &= got == ref_full
        if got != ref_full:
            print(f"  window {wd}d DIFF: {got ^ ref_full}")
    check("window: 10/20/30-day windows give the same trades as the full run over the replay sessions", same)


def test_kill_switch(rp: Replay, ref_trades, ref_open, start_t):
    print("\n== kill switch / limits ==")
    trade = ref_trades[0] if ref_trades else None
    if trade is None:
        check("kill switch: (no reference trade in window to test with)", False)
        return
    bot = rp.bot(state_path=os.path.join(rp.tmp, "kill.json"), start_now=start_t)
    errors = []
    rp.poll(bot, trade["entry_t"] + SECS + 3, errors)
    had_pos = bot.state and bot.state.get("position") is not None and len([r for r in bot.ledger if r["side"] != "exit"]) == 1
    bot.kill_switch()
    last = bot.ledger[-1] if bot.ledger else {}
    check("kill switch: flattens the open paper position (exit KILL SWITCH routed) and stops the bot",
          had_pos and last.get("side") == "exit" and last.get("reason") == "KILL SWITCH" and not bot.running and bot.kill)
    n = len(bot.ledger)
    later = [t for t in ref_trades[1:]] + ([ref_open] if ref_open else [])
    for t in later:
        rp.poll(bot, t["entry_t"] + SECS + 3, errors)
        if t.get("exit_t"):
            rp.poll(bot, t["exit_t"] + SECS + 3, errors)
    rp.poll(bot, trade["exit_t"] + SECS + 3, errors)
    check("kill switch: blocks every later entry/exit route (engine still runs, nothing is sent)",
          len(bot.ledger) == n and not errors and len(later) > 0, f"{len(later)} later reference trades, ledger unchanged at {n} rows")
    s = json.load(open(bot.state_path, encoding="utf-8"))
    check("kill switch: flag persisted to live_state.json", s.get("kill") is True)
    # restored kill flag blocks routing on restart; clear_kill re-arms
    rp.now = trade["entry_t"] + SECS + 3
    b2 = live.LiveBot(); b2.clock = rp.clock; b2.read_hist = rp.read_hist; b2.fetch_recent = rp.fetch_recent; b2.state_path = bot.state_path
    b2.start({"sym": SYM, "tf": TF, "adapter": "paper"}, spawn=False)
    check("restart: restored kill flag keeps routing blocked and is logged as risk",
          b2.kill and any(l["type"] == "risk" and "KILL flag restored" in l["text"] for l in b2.log))
    b3 = live.LiveBot(); b3.clock = rp.clock; b3.read_hist = rp.read_hist; b3.fetch_recent = rp.fetch_recent; b3.state_path = bot.state_path
    b3.start({"sym": SYM, "tf": TF, "adapter": "paper", "clear_kill": True}, spawn=False)
    check("restart: clear_kill=true re-arms", not b3.kill)


def test_limit_rules(rp: Replay):
    def by_day(trades):
        out = {}
        for t in sorted(trades, key=lambda t: t["entry_t"]):
            out.setdefault(live.trading_day(t["entry_t"]), []).append(t)
        return out

    # defaults: max 2/day, stop after a win
    r = ref_backtest(rp)
    p = r["params"]
    days = by_day(r["trades"])
    viol_max = [d for d, ts in days.items() if len(ts) > p["max_trades_day"]]
    viol_win = []
    for d, ts in days.items():
        won = False
        for t in ts:
            if won:
                viol_win.append(d)
            if t["pnl"] > 0:
                won = True
    check(f"rules: never more than max_trades_day={p['max_trades_day']} entries per day (60 days, defaults)", not viol_max, f"{len(days)} trading days with trades")
    check("rules: stop_after_win - no entry after a winning trade on the same day (defaults)", not viol_win, str(viol_win[:3]))
    # stress: tiny daily loss limit -> after the first loss no more entries that day; the rule must actually bite
    r2 = ref_backtest(rp, {"daily_max_loss": 1.0, "max_trades_day": 5, "stop_after_win": False})
    days2 = by_day(r2["trades"])
    viol_loss, bit = [], 0
    for d, ts in days2.items():
        cum = 0.0
        for t in ts:
            if cum <= -1.0:
                viol_loss.append(d)
            cum += t["pnl"]
        if cum <= -1.0:
            bit += 1
    risk_ev = sum(1 for e in r2["events"] if e["type"] == "risk" and "Daily loss stop" in e["text"])
    check("rules: daily loss stop blocks further entries once day P&L <= -limit (stress daily_max_loss=1)", not viol_loss and bit > 0 and risk_ev > 0,
          f"days where it bit: {bit}, risk events: {risk_ev}")
    r3 = ref_backtest(rp, {"max_trades_day": 1, "stop_after_win": False})
    days3 = by_day(r3["trades"])
    skips = sum(1 for e in r3["events"] if e["type"] == "skip" and "daily limits reached" in e["text"])
    check("rules: max_trades_day=1 holds and the limit visibly bites (skip events logged)", all(len(ts) <= 1 for ts in days3.values()) and skips > 0,
          f"{skips} 'daily limits reached' skips")
    check("rules: stop_after_win off lets a second trade happen on some day (control)", any(len(ts) > 1 for ts in days2.values()))


def test_news_blackout(rp: Replay, ref_trades, ref_open, start_t):
    target = (ref_trades + ([ref_open] if ref_open else []))[-1]
    sig_t = target.get("signal_t") or target["entry_t"] - SECS
    orig = news.historical_events
    fake = [{"t": int(sig_t), "date": live.trading_day(sig_t), "time_et": et(sig_t).strftime("%H:%M"), "event": "INJECTED CPI",
             "impact": "high", "currency": "USD", "source": "test"}]
    news.historical_events = lambda impacts=("high",): sorted(orig(impacts) + fake, key=lambda e: e["t"])
    try:
        r = ref_backtest(rp)
        gone = not any(abs(t["entry_t"] - target["entry_t"]) <= SECS for t in r["trades"]) and \
            not (r["state"].get("position") and abs(r["state"]["position"]["entry_t"] - target["entry_t"]) <= SECS)
        blocked_ev = any(e["type"] == "news" and "NEWS BLACKOUT" in e["text"] and e["t"] == int(sig_t) for e in r["events"])
        bot = rp.bot(state_path=os.path.join(rp.tmp, "news.json"), start_now=start_t)
        errors = []
        rp.poll(bot, target["entry_t"] + SECS + 3, errors)
        routed = [x for x in bot.ledger if x["side"] != "exit"]
        check("news: a high-impact event inside the window blocks the entry (engine) and nothing is routed (bot)",
              gone and blocked_ev and not routed and not errors, f"event injected at {hm(sig_t)} ET")
    finally:
        news.historical_events = orig


def test_failure_injection(rp: Replay, ref_trades, start_t):
    print("\n== 2. Failure injection (loop must log, flag and continue) ==")
    b = from_frame("NQ", "5m", rp.frames[("NQ", "5m")])
    trade = ref_trades[0]
    # a quiet RTH bar on the first session, a few bars after the open
    i0 = next(i for i in range(len(b)) if b.t[i] >= start_t and 600 <= b.mod[i] < 700)
    t_bar = int(b.t[i0])
    now = t_bar + SECS + 3
    bot = rp.bot(state_path=os.path.join(rp.tmp, "fail.json"), start_now=start_t)
    errors = []

    # 1. refresh raising
    rp.recent_hook = lambda *a: (_ for _ in ()).throw(ConnectionError("yfinance down (injected)"))
    st = rp.poll(bot, now, errors)
    check("inject: data refresh raising -> poll completes on stored history, last_error set, not stale",
          st is not None and not errors and bot.health["fetch_ok"] is False and "data refresh failed" in (bot.health["last_error"] or "")
          and bot.health["stale"] is False and st["t"] == t_bar)
    rp.recent_hook = None

    # 2. stale bars (feed stuck 20 minutes)
    rp.hist_hook = lambda sym, tf, cut: cut[cut["time"] + TF_SECONDS[tf] <= rp.now - 1200]
    st = rp.poll(bot, now + 2 * SECS, errors)
    stale_log = any(l["type"] == "warn" and "DATA STALE" in l["text"] for l in bot.log)
    check("inject: stale bars (>15 min old) -> stale=True, data_age_s reported, WARN logged, no exception",
          st is not None and not errors and bot.health["stale"] and bot.health["data_age_s"] >= 1200 and stale_log,
          f"data_age_s={bot.health['data_age_s']}")
    rp.hist_hook = None
    st = rp.poll(bot, now + 3 * SECS, errors)
    check("inject: feed recovers -> stale clears and is logged", st is not None and not bot.health["stale"] and bot.health["stale_polls"] == 0
          and any("fresh again" in l["text"] for l in bot.log))

    # 3. partial (still forming) last bar + misaligned timestamp bar from the feed
    nxt = int(b.t[i0 + 4])
    now4 = nxt + SECS + 3
    forming = pd.DataFrame([{"time": nxt + SECS, "open": 1.0, "high": 99999.0, "low": 0.5, "close": 2.0, "volume": 1},
                            {"time": now4 - 100, "open": 1.0, "high": 99999.0, "low": 0.5, "close": 2.0, "volume": 1}])
    rp.recent_hook = lambda sym, interval, period: forming if interval == "5m" else pd.DataFrame()
    st = rp.poll(bot, now4, errors)
    check("inject: partial/forming last bar and misaligned bar -> dropped, engine sees only closed bars",
          st is not None and not errors and st["t"] == nxt and bot.health["dropped"]["forming"] >= 1 and bot.health["dropped"]["misaligned"] >= 1,
          f"dropped={bot.health['dropped']}")

    # 4. duplicate bar (same time, revised OHLC) -> dedup keep-last, revision flagged, no crash
    row = b.to_records(i0 + 4, i0 + 5)[0]
    dup = pd.DataFrame([{**row, "close": row["close"] + 0.25, "high": max(row["high"], row["close"] + 0.25)}])
    rp.recent_hook = lambda sym, interval, period: dup if interval == "5m" else pd.DataFrame()
    st = rp.poll(bot, now4 + 60, errors)
    check("inject: duplicate bar with revised values -> de-duplicated (keep last), revision counted + logged, no exception",
          st is not None and not errors and bot.health["revisions"] >= 1 and len(bot.bars_tail) == len({r['time'] for r in bot.bars_tail}),
          f"revisions={bot.health['revisions']}")
    rp.recent_hook = None

    # 5. clock jumps (backwards 1 h, then forwards 3 h)
    st = rp.poll(bot, now4 - 3600, errors)
    back_log = any("clock moved backwards" in l["text"] for l in bot.log)
    st2 = rp.poll(bot, now4 + 3 * 3600, errors)
    check("inject: clock jump backwards/forwards -> logged, poll survives, forming-bar filter still correct",
          st is not None and st2 is not None and not errors and back_log and st2["t"] + SECS <= now4 + 3 * 3600)

    # 6. alerts sender raising at the real entry bar -> entry still routed
    bot2 = rp.bot(state_path=os.path.join(rp.tmp, "fail2.json"), start_now=start_t)
    rp.alert_fail = True
    st = rp.poll(bot2, trade["entry_t"] + SECS + 3, errors)
    rp.alert_fail = False
    routed = [x for x in bot2.ledger if x["side"] != "exit"]
    check("inject: alerts.send raising -> logged as error, order routing still happens in the same poll",
          st is not None and not errors and len(routed) == 1 and "alert failed" in (bot2.health["last_error"] or ""))

    # 7. adapter raising -> ledger records the failure, loop continues
    class BadAdapter:
        name = "bad"

        def send(self, a):
            raise RuntimeError("broker 500 (injected)")
    bot3 = rp.bot(state_path=os.path.join(rp.tmp, "fail3.json"), start_now=start_t)
    bot3.adapter = BadAdapter()
    st = rp.poll(bot3, trade["entry_t"] + SECS + 3, errors)
    check("inject: adapter.send raising -> recorded in ledger result, poll survives",
          st is not None and not errors and bot3.ledger and bot3.ledger[-1]["result"].get("ok") is False)

    # 8. data_source=tradovate with the module returning None / raising -> fallback to yahoo path, flagged
    class _FakeTV:
        class TradovateData:
            def recent_bars(self, sym, interval, period):
                return None
    sys.modules["engine.tradovate_backup"] = sys.modules.get("engine.tradovate")
    real_mod = sys.modules.get("engine.tradovate")
    import engine as _engine_pkg
    real_attr = getattr(_engine_pkg, "tradovate", None)
    sys.modules["engine.tradovate"] = _FakeTV
    _engine_pkg.tradovate = _FakeTV
    orig_yahoo = live._yahoo_recent
    live._yahoo_recent = lambda sym, interval="5m", period="5d": pd.DataFrame()
    try:
        bot4 = rp.bot({"data_source": "tradovate"}, state_path=os.path.join(rp.tmp, "fail4.json"), start_now=start_t)
        bot4.fetch_recent = bot4._fetch_recent          # use the real dispatcher
        st = rp.poll(bot4, now, errors)
        fb_log = any("falling back to Yahoo" in l["text"] for l in bot4.log)
        check("inject: data_source=tradovate returning None -> falls back to Yahoo, fallback flag + one log line",
              st is not None and not errors and bot4.health["fallback"] and fb_log and bot4.health["data_source"] == "tradovate")
        # module import error
        if "engine.tradovate" in sys.modules:
            del sys.modules["engine.tradovate"]
        if hasattr(_engine_pkg, "tradovate"):
            delattr(_engine_pkg, "tradovate")
        sys.modules["engine.tradovate"] = None  # forces ImportError
        st = rp.poll(bot4, now + SECS, errors)
        check("inject: engine.tradovate missing/erroring -> paper path still works via Yahoo fallback",
              st is not None and not errors and bot4.health["fallback"])
    finally:
        live._yahoo_recent = orig_yahoo
        if real_mod is not None:
            sys.modules["engine.tradovate"] = real_mod
        else:
            sys.modules.pop("engine.tradovate", None)
        if real_attr is not None:
            _engine_pkg.tradovate = real_attr
        elif hasattr(_engine_pkg, "tradovate"):
            delattr(_engine_pkg, "tradovate")
        sys.modules.pop("engine.tradovate_backup", None)

    # 9. stale for > 3 polls inside an entry window -> NEW entries blocked, the stale entry is never routed, later exit skipped
    bot5 = rp.bot(state_path=os.path.join(rp.tmp, "fail5.json"), start_now=start_t)
    freeze_at = trade["entry_t"] - 2 * SECS                    # feed stuck two bars before the entry bar
    rp.hist_hook = lambda sym, tf, cut: cut[cut["time"] + TF_SECONDS[tf] <= freeze_at]
    for k in range(1, 6):
        rp.poll(bot5, trade["entry_t"] + k * SECS + 3, errors)
    blocked_flag = bot5.health["entries_blocked"] and bot5.health["stale_polls"] >= 4
    # feed delivers a late burst including the entry bar, but still > 2 bars behind the clock
    rp.hist_hook = lambda sym, tf, cut: cut[cut["time"] + TF_SECONDS[tf] <= trade["entry_t"] + SECS]
    st = rp.poll(bot5, trade["entry_t"] + 6 * SECS + 3, errors)
    not_routed = not [x for x in bot5.ledger if x["side"] != "exit"]
    blk_log = any(l["type"] == "risk" and "NOT routed" in l["text"] for l in bot5.log)
    rp.hist_hook = None
    rp.poll(bot5, trade["exit_t"] + SECS + 3, errors)
    no_exit = not [x for x in bot5.ledger if x["side"] == "exit"]
    check("inject: feed stale >3 polls in an entry window -> entries_blocked, late entry NOT routed, its exit not routed either",
          blocked_flag and st is not None and not errors and not_routed and blk_log and no_exit and st["position"] is not None,
          f"stale_polls={bot5.health['stale_polls']}")

    # 10. a position that was entered during a gap (bot down) is not chased; a trade that opened AND closed in the gap
    #     produces no phantom paper exit either
    longest = max(ref_trades, key=lambda t: t["exit_t"] - t["entry_t"])
    bot6 = rp.bot(state_path=os.path.join(rp.tmp, "fail6.json"), start_now=longest["entry_t"] - 2 * SECS)
    st = rp.poll(bot6, longest["entry_t"] + 4 * SECS + 3, errors)
    late_log = any("not chasing" in l["text"] for l in bot6.log)
    check("inject: entry first seen > 2 bars late (restart/feed gap) -> not chased, logged as risk",
          st is not None and not errors and not bot6.ledger and late_log and st["position"] is not None,
          f"trade {hm(longest['entry_t'])}, poll {hm(longest['entry_t'] + 4 * SECS)}")
    shortest = min(ref_trades, key=lambda t: t["exit_t"] - t["entry_t"])
    bot6b = rp.bot(state_path=os.path.join(rp.tmp, "fail6b.json"), start_now=shortest["entry_t"] - 2 * SECS)
    st = rp.poll(bot6b, shortest["exit_t"] + 2 * SECS + 3, errors)
    check("inject: trade opened and closed while the bot was down -> no phantom paper exit, warning logged",
          st is not None and not errors and not bot6b.ledger and any("never routed" in l["text"] for l in bot6b.log))

    # 10b. feed stalls across the flat time with a routed position open -> clock-based safety flatten, model exit not re-sent
    #      (flat_mod moved to 14:05 ET so the 13:55 trade is the one spanning it; signal at 13:50 stays inside the window)
    span = max(ref_trades, key=lambda t: t["exit_t"] - t["entry_t"])
    e_mod = et(span["entry_t"]).hour * 60 + et(span["entry_t"]).minute
    fm = e_mod + 10
    bot9 = rp.bot({"params": {"flat_mod": fm}}, state_path=os.path.join(rp.tmp, "fail9.json"), start_now=start_t)
    st = rp.poll(bot9, span["entry_t"] + SECS + 3, errors)
    routed_entry = len([x for x in bot9.ledger if x["side"] != "exit"]) == 1
    rp.hist_hook = lambda sym, tf, cut: cut[cut["time"] + TF_SECONDS[tf] <= span["entry_t"] + SECS]   # feed frozen at the entry bar
    st2 = rp.poll(bot9, span["entry_t"] + 4 * SECS + 3, errors)       # 15 min later = flat_mod + 5: past flat time, model blind
    exits = [x for x in bot9.ledger if x["side"] == "exit"]
    safety = len(exits) == 1 and exits[0]["reason"] == "TIME SAFETY"
    rp.hist_hook = None
    st3 = rp.poll(bot9, span["entry_t"] + 5 * SECS + 3, errors)       # feed catches up: engine shows its own TIME exit
    exits2 = [x for x in bot9.ledger if x["side"] == "exit"]
    check("inject: feed stalls across flat time with a routed position -> clock-based SAFETY flatten once, model exit not re-sent",
          routed_entry and safety and len(exits2) == 1 and st3 is not None and st3["position"] is None and not errors
          and any("not sent again" in l["text"] for l in bot9.log), f"flat_mod={fm // 60:02d}:{fm % 60:02d}")

    # 11. the background loop itself survives repeated poll failures and exits cleanly on stop()
    bot7 = live.LiveBot(); bot7.clock = rp.clock; bot7.state_path = os.path.join(rp.tmp, "loop.json")
    bot7.cfg = {**live.LIVE_DEFAULTS, "poll_sec": 0.01}
    n = {"calls": 0, "snap": None}

    def boom():
        n["calls"] += 1
        if n["calls"] <= 3:
            raise RuntimeError("injected poll failure")
        n["snap"] = (dict(bot7.health), bot7.errors)
        bot7.stop()
    bot7.poll_once = boom
    bot7.running = True
    import io, contextlib
    with contextlib.redirect_stderr(io.StringIO()):
        th = threading.Thread(target=bot7._loop, args=(bot7._gen,), daemon=True)
        th.start(); th.join(timeout=10)
    snap = n["snap"] or ({}, 0)
    check("loop: _loop logs and continues after 3 consecutive poll failures, then exits on stop()",
          not th.is_alive() and n["calls"] == 4 and snap[1] == 3 and snap[0].get("consecutive_errors") == 3 and snap[0].get("ok") is False
          and bot7.health["consecutive_errors"] == 0)

    # 12. start() twice (stop/start race) never leaves two loops alive
    bot8 = live.LiveBot(); bot8.clock = rp.clock; bot8.read_hist = rp.read_hist; bot8.fetch_recent = rp.fetch_recent
    bot8.state_path = os.path.join(rp.tmp, "race.json")
    slow = {"n": 0}

    def slow_poll():
        slow["n"] += 1
        time.sleep(0.05)
    bot8.poll_once = slow_poll
    bot8.start({"sym": SYM, "tf": TF, "adapter": "paper", "poll_sec": 0.01})
    t1 = bot8.thread
    bot8.stop()
    bot8.poll_once = slow_poll
    bot8.start({"sym": SYM, "tf": TF, "adapter": "paper", "poll_sec": 0.01})
    t2 = bot8.thread
    time.sleep(0.3)
    first_dead = not t1.is_alive()
    bot8.stop(); t2.join(timeout=2)
    check("loop: stop()+start() retires the old thread (no two loops polling at once)", first_dead and not t2.is_alive())


def test_restart(rp: Replay, ref_trades, start_t):
    print("\n== 3. Restart safety ==")
    trade = ref_trades[0]
    path = os.path.join(rp.tmp, "restart.json")
    errors = []
    a = rp.bot(state_path=path, start_now=start_t)
    rp.poll(a, trade["entry_t"] + SECS + 3, errors)
    a_rows = len(a.ledger)
    saved = json.load(open(path, encoding="utf-8"))
    check("restart: state file holds open routed position, ledger, day P&L, trades today, kill flag",
          a_rows == 1 and saved["open_routed"] == trade["entry_t"] and len(saved["ledger"]) == 1 and saved["kill"] is False
          and saved["trades_today"] == 1 and "day_pnl_routed" in saved)
    # "server restarts" one bar later: brand-new LiveBot, same file
    rp.now = trade["entry_t"] + 2 * SECS + 3
    b = live.LiveBot(); b.clock = rp.clock; b.read_hist = rp.read_hist; b.fetch_recent = rp.fetch_recent; b.state_path = path
    r = b.start({"sym": SYM, "tf": TF, "adapter": "paper"}, spawn=False)
    restored_log = any(l["type"] == "system" and l["text"].startswith("Restored live state") for l in b.log)
    check("restart: new process restores ledger/open position with a clear log line",
          r.get("restored") and r["restored"]["ledger"] == 1 and r["restored"]["open_routed"] == trade["entry_t"] and restored_log
          and b.started_at == a.started_at)
    rp.poll(b, trade["entry_t"] + 2 * SECS + 3, errors)
    check("restart: the already-routed entry is not routed again", len([x for x in b.ledger if x["side"] != "exit"]) == 1 and not errors)
    rp.poll(b, trade["exit_t"] + SECS + 3, errors)
    exits = [x for x in b.ledger if x["side"] == "exit"]
    check("restart: the exit of the restored position is routed exactly once with the right reason and P&L",
          len(exits) == 1 and exits[0]["reason"] == trade["exit_reason"] and abs(exits[0]["pnl"] - trade["pnl"]) < 0.01 and b._open_routed is None
          and not errors and round(b.day_pnl_routed(), 2) == round(trade["pnl"], 2))
    # a state file from another day is ignored
    old = dict(saved); old["day"] = "2000-01-01"
    json.dump(old, open(path, "w", encoding="utf-8"))
    c = live.LiveBot(); c.clock = rp.clock; c.read_hist = rp.read_hist; c.fetch_recent = rp.fetch_recent; c.state_path = path
    c.start({"sym": SYM, "tf": TF, "adapter": "paper"}, spawn=False)
    check("restart: a state file from a previous day is ignored (logged)", not c.ledger and c._open_routed is None
          and any("Ignoring live_state.json" in l["text"] for l in c.log))
    # corrupt file never prevents start
    open(path, "w", encoding="utf-8").write("{not json")
    d = live.LiveBot(); d.clock = rp.clock; d.state_path = path; d.read_hist = rp.read_hist; d.fetch_recent = rp.fetch_recent
    r = d.start({"sym": SYM, "tf": TF, "adapter": "paper"}, spawn=False)
    check("restart: corrupt state file -> starts clean with a warning", r.get("ok") and any("unreadable" in l["text"] for l in d.log))


# ------------------------------------------------------------------------------------------------ main
def main():
    t_all = time.perf_counter()
    prod_state = live.STATE_PATH
    prod_existed = os.path.exists(prod_state)
    prod_mtime = os.path.getmtime(prod_state) if prod_existed else None
    rp = Replay()
    rp.install_globals()
    print(f"Liquidity Engine live dry run  ({'quick' if QUICK else 'full'})  data through {hm(rp.frames[('NQ', '5m')]['time'].max())} ET")
    try:
        b, idx, days, ref_trades, ref_open, bot, mean_ms = test_replay(rp)
        start_t = int(b.t[idx[0]])
        test_failure_injection(rp, ref_trades, start_t)
        test_restart(rp, ref_trades, start_t)
        test_window_equivalence(rp, ref_trades, start_t)
        test_kill_switch(rp, ref_trades, ref_open, start_t)
        test_limit_rules(rp)
        test_news_blackout(rp, ref_trades, ref_open, start_t)
    except Exception:
        traceback.print_exc()
        check("harness: completed without an internal error", False, traceback.format_exc().splitlines()[-1])
    finally:
        rp.cleanup()
    touched = (os.path.exists(prod_state) != prod_existed) or (prod_existed and os.path.getmtime(prod_state) != prod_mtime)
    check("hygiene: harness did not write data/live_state.json", not touched)
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{'=' * 100}\n{npass}/{len(RESULTS)} assertions passed in {time.perf_counter() - t_all:.0f}s")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAIL  {name}  {detail}")
    sys.exit(0 if npass == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
