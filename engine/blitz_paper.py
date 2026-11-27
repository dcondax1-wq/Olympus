"""The BLITZ PAPER lane (day-blitzready 2026-11-27): BLITZ's rule run LIVE as a paper bot of its own, by itself on the PC.

PAPER ONLY. It never sends an order: it imports no broker / adapter / NinjaTrader / live-loop module (tests/test_blitz_paper.py
checks the imports), has no account and no routing switch, and nothing in this file can be turned into one. The owner's rule
"BLITZ can be paper till we study more" stands: this lane never asks for, reads or flips BLITZ's live switch.

What it does: every run reads the closed 1m bars (data/NQ_1m.csv tail + the PC's archive + NinjaTrader's le_feed file, read only),
feeds them through engine.blitz.step (the SAME state machine the research backtest is held to: 330/330 parity), keeps its own
state in data/blitz_paper/state.json, and logs every paper trade ONCE to data/blitz_paper/trades.jsonl (an entry row when it
opens, an exit row when it closes, keyed by entry_t). Report: data/blitz_paper.json (the PC feed's p4 BLITZ = "paper").

Safety pattern = engine/of_paper + engine/of_lane:
  started by engine/ops_checks.blitz_paper_kick (BELOW_NORMAL, detached, weekdays 09:25-16:10 ET, never twice: heartbeat
  data/blitz_paper_run.json < 2 min old or a start < 3 min ago), stops itself at 16:10 ET or on data/blitz_paper_stop;
  kill switch (data/live_state.json "kill", or data/blitz_paper_kill): no new paper entry, an open paper trade is closed at the
  next bar; off: LE_BLITZPAPER=0 or data/blitz_paper_off.

    python -X utf8 -m engine.blitz_paper tick      # one run
    python -X utf8 -m engine.blitz_paper loop      # every 30 s until 16:10 ET
    python -X utf8 -m engine.blitz_paper replay --last 3   # the last 3 sessions through the live path vs blitz.backtest
    python -X utf8 -m engine.blitz_paper show
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
DIR_NAME = "blitz_paper"
STATE, TRADES, REPORT, RUN = "state.json", "trades.jsonl", "blitz_paper.json", "blitz_paper_run.json"
OFF_NAME, STOP_NAME, KILL_NAME = "blitz_paper_off", "blitz_paper_stop", "blitz_paper_kill"
LABEL = "BLITZ paper lane (shadow)"
VERSION = 1
FROM_MOD, TO_MOD = 9 * 60 + 25, 16 * 60 + 10          # the run's day (ET minutes)
BEAT_S, LOOP_S = 120, 30
HIST_DAYS = 45                                        # bars read: > blitz.WARM_DAYS (35) so a cold start warms fully


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def et_day(t) -> str:
    return _et(t).strftime("%Y-%m-%d")


def _rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"), default=float)
    from . import fsutil                              # retries on a Windows / OneDrive lock (test_selfheal)
    fsutil.replace(tmp, p)


def _d(root: str) -> str:
    return os.path.join(root, "data", DIR_NAME)


# ------------------------------------------------------------------------------------------------ switches
def off_reason(root: str = ROOT) -> str | None:
    if os.environ.get("LE_BLITZPAPER") == "0" or os.path.exists(os.path.join(root, "data", OFF_NAME)):
        return "off"
    return None


def killed(root: str = ROOT) -> bool:
    """The owner's kill (data/live_state.json "kill") or this lane's own kill file."""
    return bool((_rj(os.path.join(root, "data", "live_state.json")) or {}).get("kill")) or os.path.exists(os.path.join(root, "data", KILL_NAME))


# ------------------------------------------------------------------------------------------------ bars (read only)
def read_bars(root: str = ROOT, now: int | None = None, nt: str | None = None):
    """Closed + forming 1m bars, newest wins: data/NQ_1m.csv tail, the PC archive (engine.pcbars), NinjaTrader's le_feed file.
    Plain file reads. None when nothing readable."""
    import pandas as pd
    now = int(now if now is not None else time.time())
    t0 = now - HIST_DAYS * 86400
    cols = ["time", "open", "high", "low", "close"]
    frames = []
    p = os.path.join(root, "data", "NQ_1m.csv")
    try:
        d = pd.read_csv(p)
        frames.append(d[d["time"] >= t0][cols])
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import pcbars
        a = pcbars.archive_read("NQ", "1m")
        if a is not None and len(a):
            frames.append(a[a["time"] >= t0][cols])
    except Exception:  # noqa: BLE001
        pass
    try:
        if nt is None:
            from . import oflive
            nt = oflive.nt_dir()
        if nt:
            for r in ("NQ", "MNQ"):
                f = os.path.join(nt, "le_feed", f"{r}_1m.csv")
                if os.path.exists(f):
                    d = pd.read_csv(f, on_bad_lines="skip")
                    d.columns = [str(c).strip().lower() for c in d.columns]
                    if all(c in d.columns for c in cols):
                        d = d[pd.to_numeric(d["time"], errors="coerce").notna()]
                        for c in cols:
                            d[c] = pd.to_numeric(d[c], errors="coerce")
                        frames.append(d[d["time"] >= t0][cols].dropna())
                    break
    except Exception:  # noqa: BLE001
        pass
    frames = [f for f in frames if len(f)]
    if not frames:
        return None
    out = pd.concat(frames).drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    out["time"] = out["time"].astype("int64")
    return out


# ------------------------------------------------------------------------------------------------ the paper trade log
def _row(r: dict, ev: str) -> dict:
    keep = ("id", "day", "sig_t", "entry_t", "dir", "side", "entry", "stop", "risk_pts", "qty", "risk_usd", "skip", "exit_t", "exit",
            "exit_kind", "pts", "r", "usd", "r_usd150", "late", "eval", "killed_window")
    return {"ev": ev, "v": VERSION, **{k: r.get(k) for k in keep if k in r}}


def log_trades(S: dict, root: str = ROOT) -> int:
    """Append each paper trade ONCE (an 'entry' row at its open, an 'exit' row at its close) to data/blitz_paper/trades.jsonl, keyed by
    (entry_t, ev) from the file itself, so a restart never repeats a row. Returns the rows written."""
    p = os.path.join(_d(root), TRADES)
    seen = set()
    try:
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    x = json.loads(ln)
                    seen.add((int(x["entry_t"]), x["ev"]))
                except Exception:  # noqa: BLE001
                    continue
    except OSError:
        pass
    new = []
    for r in S.get("ledger") or []:
        k = int(r["entry_t"])
        if (k, "entry") not in seen:
            new.append(_row(r, "entry"))
        if r.get("exit_kind") not in (None, "OPEN") and (k, "exit") not in seen:
            new.append(_row(r, "exit"))
    if new:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            for x in new:
                fh.write(json.dumps(x, separators=(",", ":"), default=float) + "\n")
    return len(new)


def read_trades(root: str = ROOT) -> list:
    out = []
    try:
        with open(os.path.join(_d(root), TRADES), encoding="utf-8") as fh:
            for ln in fh:
                try:
                    out.append(json.loads(ln))
                except Exception:  # noqa: BLE001
                    pass
    except OSError:
        pass
    return out


# ------------------------------------------------------------------------------------------------ one step
def line(S: dict | None, day: str | None = None) -> str:
    if not S:
        return "BLITZ paper: no state yet"
    from . import blitz as BZ
    day = day or et_day(S.get("t") or time.time())
    rows = [r for r in S.get("ledger") or [] if r.get("day") == day]
    done = [r for r in rows if r.get("exit_kind") not in (None, "OPEN")]
    usd = sum(float(r.get("r_usd150") or 0) for r in done)
    op = " (1 open)" if any(r.get("exit_kind") == "OPEN" for r in rows) else ""
    return f"BLITZ paper {day}: {len(done)} trades, ${usd:+,.0f} at $150 a trade{op}"


def step(prev: dict | None, df1, now: int, root: str = ROOT) -> dict:
    """One poll through engine.blitz.step (the 25K-eval ledger = the pillar's own paper trades; the 50K ledger needs LIT / ATLAS state
    this lane does not read, so it stays empty). Pure paper: nothing is routed, no account exists."""
    from . import blitz as BZ
    hist = None
    if not (isinstance(prev, dict) and (prev.get("eng") or {}).get("last_t")):
        hist = BZ.history_frame(os.path.join(root, "data", "NQ_1m.csv"), since=int(now) - HIST_DAYS * 86400)
    return BZ.step(prev, df1, now, hist=hist, res=None, second=None, atlas_open=None)


def mark_killed_window(S: dict, kill_t: int, now: int):
    """The kill switch froze the lane at kill_t; on resume the state catches up on the bars of the frozen window. A paper trade ENTERED in
    that window is tagged killed_window (kept in the log, never scored): no new paper entry while the kill is on."""
    for r in S.get("ledger") or []:
        if int(r.get("entry_t") or 0) >= int(kill_t) - 60:
            r["killed_window"] = True


def tick(now: int | None = None, root: str = ROOT, df1=None, force: bool = False) -> dict:
    """One run: read bars, step, save state + trade log + report. Never raises."""
    now = int(now if now is not None else time.time())
    try:
        if off_reason(root) and not force:
            return {"ok": False, "why": "off"}
        e = _et(now)
        mod = e.hour * 60 + e.minute
        if not force and (e.weekday() >= 5 or not (FROM_MOD <= mod <= TO_MOD)):
            return {"ok": False, "why": "outside the session"}
        sp = os.path.join(_d(root), STATE)
        prev = _rj(sp)
        kill = killed(root)
        if kill:                                       # kill switch: frozen, no new paper entry (state catches up, tagged, on resume)
            if prev is not None and not prev.get("kill_t"):
                prev["kill_t"] = now
                _wj(sp, prev)
            rep = report(prev or {}, now, True, 0)
            _wj(os.path.join(root, "data", REPORT), rep)
            return {"ok": False, "why": "kill"}
        df = df1 if df1 is not None else read_bars(root, now)
        if df is None or not len(df):
            rep = {"v": VERSION, "paper": True, "never_routed": True, "label": LABEL, "t": now, "day": et_day(now), "error": "no 1m bars readable"}
            _wj(os.path.join(root, "data", REPORT), rep)
            return {"ok": False, "why": "no bars"}
        S = step(prev, df, now, root)
        if isinstance(prev, dict) and prev.get("kill_t"):
            mark_killed_window(S, int(prev["kill_t"]), now)
        S.pop("kill_t", None)
        S["saved_t"] = now
        _wj(sp, S)
        n = log_trades(S, root)
        rep = report(S, now, kill, n)
        _wj(os.path.join(root, "data", REPORT), rep)
        return {"ok": True, "new_rows": n, "line": rep["line"]}
    except Exception as ex:  # noqa: BLE001
        try:
            _wj(os.path.join(root, "data", REPORT), {"v": VERSION, "paper": True, "never_routed": True, "label": LABEL, "t": now,
                                                      "day": et_day(now), "error": f"{ex.__class__.__name__}: {str(ex)[:160]}"})
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "why": f"{ex.__class__.__name__}: {str(ex)[:120]}"}


def report(S: dict, now: int, kill: bool = False, new_rows: int = 0) -> dict:
    """data/blitz_paper.json: what the PC feed reads (plain JSON, small). paper + never_routed always."""
    day = et_day(now)
    rows = [r for r in S.get("ledger") or [] if r.get("day") == day]
    done = [r for r in rows if r.get("exit_kind") not in (None, "OPEN")]
    allr = [r for r in S.get("ledger") or [] if r.get("exit_kind") not in (None, "OPEN")]
    return {"v": VERSION, "paper": True, "never_routed": True, "label": LABEL, "t": int(now), "day": day, "line": line(S, day),
            "state": "kill" if kill else "paper", "today_n": len(done), "today_usd150": round(sum(float(r.get("r_usd150") or 0) for r in done), 2),
            "open": sum(1 for r in rows if r.get("exit_kind") == "OPEN"), "total_n": len(allr), "first_run": S.get("first_run"),
            "total_usd150": round(sum(float(r.get("r_usd150") or 0) for r in allr), 2), "bars_t": S.get("bars_t")}


def fresh(rep: dict | None, now: float | None = None, max_age: int = 15 * 60) -> bool:
    """The feed's rule for "paper": today's report, written < max_age ago, no error."""
    if not isinstance(rep, dict) or rep.get("error"):
        return False
    now = now if now is not None else time.time()
    return rep.get("day") == et_day(now) and now - float(rep.get("t") or 0) <= max_age


def compact(root: str = ROOT) -> dict | None:
    """For the PC feed (tools/pc_report): the report + whether the lane is alive. Plain JSON reads."""
    rep = _rj(os.path.join(root, "data", REPORT))
    return rep if isinstance(rep, dict) else None


# ------------------------------------------------------------------------------------------------ the runner
def loop(root: str = ROOT, clock=time.time, sleep=time.sleep, max_runs: int | None = None) -> int:
    """Every 30 s until 16:10 ET (or the stop flag, off, kill with nothing open). Heartbeat in data/blitz_paper_run.json."""
    lk = run_lock(root)
    if lk is None:                                     # red team #40: a 2nd runner (a slow run let the 2-min heartbeat age) exits at once,
        return 0                                       # writing nothing (not the 1st one's heartbeat, state or trade log)
    try:
        return _loop(root, clock, sleep, max_runs)
    finally:
        lk.close()                                     # the OS lock goes with the handle (and with the process if it dies)


RUN_LOCK = "run.lock"


def run_lock(root: str = ROOT):
    """ONE BLITZ paper runner per repo: an OS lock on data/blitz_paper/run.lock held for the runner's life (freed by the OS on a crash,
    never stale; the same pattern as engine/of_lane.run_lock). The open handle, or None when another runner holds it."""
    d = _d(root)
    os.makedirs(d, exist_ok=True)
    fh = open(os.path.join(d, RUN_LOCK), "a+")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def _loop(root, clock, sleep, max_runs) -> int:
    runs = 0
    while True:
        now = int(clock())
        e = _et(now)
        mod = e.hour * 60 + e.minute
        if e.weekday() >= 5 or mod > TO_MOD or os.path.exists(os.path.join(root, "data", STOP_NAME)) or off_reason(root):
            _wj(os.path.join(root, "data", RUN), {"t": now, "pid": os.getpid(), "stopped": True})
            return 0
        if mod >= FROM_MOD:
            tick(now, root)
        _wj(os.path.join(root, "data", RUN), {"t": now, "pid": os.getpid()})
        runs += 1
        if max_runs is not None and runs >= max_runs:
            return 0
        sleep(LOOP_S)


# ------------------------------------------------------------------------------------------------ paper = backtest check
def replay(last: int = 3, root: str = ROOT, df=None, active: bool = False) -> dict:
    """The last `last` sessions of data/NQ_1m.csv through the LIVE lane path (cold start 'last-3-days ago', one poll a minute, the
    same step(), the same trade log writer into a scratch dir) and blitz.backtest on the whole frame: trade-for-trade."""
    import pandas as pd
    import tempfile
    from . import blitz as BZ
    if df is None:
        df = pd.read_csv(os.path.join(root, "data", "NQ_1m.csv"))
    df = df[["time", "open", "high", "low", "close"]].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    days = sorted({et_day(t) for t in df["time"].to_numpy() if 570 <= (lambda e: e.hour * 60 + e.minute)(_et(t)) < 960})
    days = [d for d in days if _et(int(df[df["time"] >= BZ.at_et(d, 570)]["time"].iloc[0])).weekday() < 5]
    allbt = BZ.backtest(df)
    if active:                                         # the last `last` sessions that HAD a BLITZ trade (the filter skips many days)
        have = {r["day"] for r in allbt}
        use = [d for d in days if d in have][-last:]
    else:
        use = days[-last:]
    bt = [r for r in allbt if r["day"] in use]         # the backtest on everything up to the last bar
    # the live path: first poll 09:20 ET of the first session (a cold start there: the shadow starts, warms 35 days, books from then)
    scratch = tempfile.mkdtemp(prefix="blitz_replay_")
    t_first = BZ.at_et(use[0], 9 * 60 + 20)
    tt = df["time"].to_numpy()
    S = None
    n_poll = 0
    for d in (x for x in days if use[0] <= x <= use[-1]):
        for mm in range(9 * 60 + 21, 16 * 60 + 11):
            now = BZ.at_et(d, mm)
            sub = df.iloc[:int(tt.searchsorted(now - 60, side="right"))]          # bars closed by `now` (open + 60 <= now)
            if not len(sub) or int(sub["time"].iloc[-1]) < now - 5 * 60:
                continue
            S = step(S, sub, now, root=scratch) if S is not None else step_cold(sub, now, t_first, scratch)
            S["saved_t"] = now
            log_trades(S, scratch)
            n_poll += 1
    live = [r for r in S["ledger"] if r["day"] in use and r.get("exit_kind") not in (None, "OPEN")]
    logged = [x for x in read_trades(scratch) if x["ev"] == "exit"]
    return {"sessions": use, "polls": n_poll, "backtest": bt, "live": live, "logged": logged, **compare(bt, live)}


def step_cold(sub, now: int, first_run: int, root: str) -> dict:
    from . import blitz as BZ
    return BZ.step(None, sub, now, first_run=first_run, hist=sub)


def compare(bt: list, live: list) -> dict:
    """Trade-for-trade: entry_t, dir, entry, stop, exit_t, exit, exit_kind, r."""
    def key(r):
        return (int(r["entry_t"]), int(r["dir"]), round(float(r["entry"]), 2), round(float(r["stop"]), 2), int(r["exit_t"]),
                round(float(r["exit"]), 2), str(r["exit_kind"]))
    a, b = sorted(map(key, bt)), sorted(map(key, live))
    return {"n_backtest": len(a), "n_live": len(b), "match": a == b, "only_backtest": [x for x in a if x not in b],
            "only_live": [x for x in b if x not in a]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="engine.blitz_paper")
    ap.add_argument("cmd", choices=("tick", "loop", "replay", "show"))
    ap.add_argument("--last", type=int, default=3)
    ap.add_argument("--active", action="store_true", help="the last N sessions that had a BLITZ trade")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd in ("tick", "loop") and hasattr(os, "nice"):
        try:
            os.nice(5)                                  # below the bot (Windows: BELOW_NORMAL from engine/ops_checks.blitz_paper_kick)
        except OSError:
            pass
    if a.cmd == "tick":
        print(json.dumps(tick(force=a.force), default=str)[:600])
        return 0
    if a.cmd == "loop":
        return loop()
    if a.cmd == "replay":
        r = replay(a.last, active=a.active)
        print(json.dumps({k: v for k, v in r.items() if k not in ("backtest", "live", "logged")}, default=str, indent=1))
        return 0 if r["match"] else 1
    print(json.dumps(compact(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
