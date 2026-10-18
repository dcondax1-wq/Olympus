"""Cloud fast-entry watcher (PC off, free): after a cloud-monitor run, keep the GitHub Actions job alive while a LIT setup
is armed (limit working / tapped, waiting for the 1m CISD) or forming (engine/lit_watch.brewing), poll Yahoo NQ=F every
30 s, and the moment the model's state changes (setup placed / tapped / gone, the entry filled) run the full monitor
(tools/cloud_monitor.py: paper ledger, phone notification, README / state.json) and publish (scripts/cloud_publish.sh).
Stops when nothing is armed or forming, the day's trade is in, at --cap minutes, or at 15:57 ET.

Entries stay the backtest's: every decision is engine/lit_live.run on the same bars the monitor uses; the watcher only
decides WHEN the monitor looks (tests/test_lit_watch.py replays 2026). Yahoo NQ=F is a delayed feed (~10 min measured,
research/NIGHT_LOG.md; every poll's lag is logged in <out>/watch.json "lag"): the watcher removes the 0-30 min wait for the
next half-hourly run, not Yahoo's own delay.

Free-minute guard (private repo: 2,000 Actions minutes a month): --forming-budget minutes a day may be spent on forming
setups (armed setups are always watched), --month-budget minutes a month in all (then armed only; 1.5x: no watching).

    python tools/lit_watch.py --out dash [--cap 55] [--every 30] [--forming-budget 15] [--month-budget 550] [--no-publish]
Paper only: nothing here routes an order.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import lit, lit_live, lit_watch                 # noqa: E402
from engine.lab_adapter import live_model                    # noqa: E402

ET = ZoneInfo("America/New_York")
LAG_KEEP = 400


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)
    os.replace(tmp, path)


def watch_summary(W: dict) -> dict:
    """The part of watch.json the monitor copies into state.json (phone app / README): last watch, minutes, Yahoo lag."""
    lags = [x[1] for x in W.get("lag") or [] if x and x[1] is not None]
    srt = sorted(lags)
    med = srt[len(srt) // 2] if srt else None
    return {"last": W.get("last"), "month": W.get("month"), "used_min": round(float(W.get("used_s", 0)) / 60, 1),
            "day": W.get("day"), "forming_min_today": round(float(W.get("forming_s", 0)) / 60, 1),
            "yahoo_lag_1m_s": {"median": med, "n": len(srt), "p90": srt[int(len(srt) * 0.9)] if srt else None}}


def _ledger_rows(out):
    st = _load(os.path.join(out, "state.json"), {})
    return [{"day": v.get("day"), "exit": v.get("exit"), "exit_t": v.get("exit_ts")} for v in (st.get("ledger") or {}).values()]


def full_run(out, publish, why):
    """The regular monitor (ledger + notification + dashboards) and the publish script, as the workflow runs them."""
    print(f"watch: {why} -> full monitor run", flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "cloud_monitor.py"), "--out", out], cwd=ROOT)
    if r.returncode != 0:
        print("watch: monitor run failed", r.returncode, flush=True)
    if publish:
        subprocess.run(["bash", os.path.join(ROOT, "scripts", "cloud_publish.sh"), out, "all"], cwd=ROOT)
    return round(time.time() - t0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dash")
    ap.add_argument("--cap", type=float, default=55.0, help="minutes this job may watch")
    ap.add_argument("--every", type=float, default=30.0, help="seconds between polls")
    ap.add_argument("--forming-budget", type=float, default=15.0, help="minutes a day on setups still forming")
    ap.add_argument("--month-budget", type=float, default=550.0, help="watch minutes a month (then armed setups only)")
    ap.add_argument("--no-publish", action="store_true")
    a = ap.parse_args()
    out = a.out
    lm = live_model()
    if lm.get("model") != "lit":
        print("watch: live model is not LIT; nothing to watch")
        return
    P = {**lit.DEFAULTS, **(lm.get("lit") or {})}
    sym = lm.get("sym") or "NQ"
    wpath = os.path.join(out, "watch.json")
    W = _load(wpath, {})
    t_start = time.time()
    e0 = _et(t_start)
    if W.get("month") != e0.strftime("%Y-%m"):
        W.update(month=e0.strftime("%Y-%m"), used_s=0.0)
    if W.get("day") != e0.strftime("%Y-%m-%d"):
        W.update(day=e0.strftime("%Y-%m-%d"), forming_s=0.0)
    used_min = float(W.get("used_s", 0)) / 60
    arm = (_load(os.path.join(out, "state.json"), {}) or {}).get("armed")
    if not arm:                                   # the monitor run just found nothing armed or forming: done (no cost)
        print("watch: nothing armed or forming at the last monitor run")
        return
    if arm.get("kind") == "forming" and (float(W.get("forming_s", 0)) >= a.forming_budget * 60 or used_min >= a.month_budget):
        print(f"watch: setup forming, but today's forming budget ({a.forming_budget:.0f} min) or the month's is used")
        return
    if used_min >= 1.5 * a.month_budget:
        print(f"watch: {used_min:.0f} min used this month (budget {a.month_budget:.0f}): off until next month")
        return
    from engine.live import LiveBot, _yahoo_recent, clean_bars, market_open
    if not market_open(t_start) or e0.weekday() >= 5 or e0.hour * 60 + e0.minute >= 15 * 60 + 57:
        print("watch: outside the session; nothing to watch")
        return
    bot = LiveBot()
    bot.cfg = {"sym": sym, "tf": "5m", "adapter": "paper", "data_source": "yahoo", "params": {}, "window_days": 20}
    now = int(time.time())
    base5, _ = bot._merged(sym, "5m", now, 300)
    p1 = os.path.join(out, "bars_1m.csv")
    try:
        base1 = pd.read_csv(p1) if os.path.exists(p1) else pd.DataFrame()
    except Exception:
        base1 = pd.DataFrame()
    week = _ledger_rows(out)
    lags = list(W.get("lag") or [])
    last_sig, brew, brew_t, M = None, [], None, None
    polls, runs, why_end, kinds = 0, [], "cap", set()
    forming_s0 = float(W.get("forming_s", 0))
    while True:
        tp = time.time()
        now = int(tp)
        e = _et(now)
        if e.hour * 60 + e.minute >= 15 * 60 + 57:
            why_end = "15:57 ET"
            break
        try:
            y5 = _yahoo_recent(sym, "5m", "1d")
            y1 = _yahoo_recent(sym, "1m", "1d")
        except Exception as ex:
            print("watch: Yahoo fetch failed:", ex.__class__.__name__, flush=True)
            y5 = y1 = pd.DataFrame()
        if len(y1):
            lags.append([now, int(now - (int(y1["time"].max()) + 60))])     # seconds since the newest 1m bar closed
        df5, _ = clean_bars(pd.concat([x for x in (base5, y5) if len(x)]), 300, now)
        df1, _ = clean_bars(pd.concat([x for x in (base1, y1) if len(x)]) if (len(base1) or len(y1)) else pd.DataFrame(), 60, now)
        try:
            res = lit_live.run(df5, P, one_min=df1 if len(df1) else None, now=now, sym=sym, week_hist=week)
        except Exception as ex:
            print("watch: model failed:", ex.__class__.__name__, ex, flush=True)
            why_end = "model error"
            break
        polls += 1
        t5 = int(df5["time"].max())
        if t5 != brew_t:                                   # a new 5m bar: forming setups
            brew_t = t5
            try:
                M = lit_watch.market(df5, P, sym)
                brew = lit_watch.brewing(M, P)
            except Exception as ex:
                print("watch: forming check failed:", ex.__class__.__name__, ex, flush=True)
                brew = []
        ok, why = lit_watch.alive(res, brew)
        if why == "setup forming":
            if float(W.get("forming_s", 0)) >= a.forming_budget * 60 or used_min >= a.month_budget:
                ok, why = False, "forming budget used"
            else:
                W["forming_s"] = float(W.get("forming_s", 0)) + (a.every if polls > 1 else 0)
        kinds.add(why)
        sig = lit_watch.signature(res)
        if last_sig is not None and sig != last_sig:
            line = lit_watch.armed_line(res["state"], brew, P.get("cisd1m") or 20)
            W.update(lag=lags[-LAG_KEEP:], last={"start": int(t_start), "polls": polls, "now": now, "state": why,
                                                 "line": line and line["text"]})
            _save(wpath, W)
            secs = full_run(out, not a.no_publish, f"{why} ({res['state'].get('model_state')})")
            runs.append({"t": now, "why": why, "position": bool(res["state"].get("position")), "secs": secs})
            week = _ledger_rows(out)
        last_sig = sig
        if polls == 1 or polls % 10 == 0 or not ok:
            print(f"watch {e:%H:%M:%S} ET: {why}; {res['state'].get('model_state')}"
                  + (f"; Yahoo 1m lag {lags[-1][1]} s" if lags else ""), flush=True)
        if not ok:
            why_end = why
            break
        if time.time() - t_start >= a.cap * 60:
            why_end = "cap"
            break
        time.sleep(max(1.0, a.every - (time.time() - tp)))
    spent = time.time() - t_start
    W["used_s"] = float(W.get("used_s", 0)) + spent
    W.update(lag=lags[-LAG_KEEP:], last={"start": int(t_start), "end": int(time.time()), "polls": polls, "minutes": round(spent / 60, 1),
                                         "ended": why_end, "states": sorted(kinds), "full_runs": runs,
                                         "forming_min": round((float(W.get("forming_s", 0)) - forming_s0) / 60, 1)})
    _save(wpath, W)
    print(f"watch: {polls} polls in {spent / 60:.1f} min, ended: {why_end}; {len(runs)} full runs; "
          f"month {float(W['used_s']) / 60:.0f} min", flush=True)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as fh:
            fh.write(f"polls={polls}\nruns={len(runs)}\n")
    if polls > 1 and not a.no_publish:          # keep the minutes / lag record (the dashboard branch holds watch.json)
        subprocess.run(["bash", os.path.join(ROOT, "scripts", "cloud_publish.sh"), out, "dash"], cwd=ROOT)


if __name__ == "__main__":
    main()
