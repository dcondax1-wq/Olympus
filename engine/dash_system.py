"""System-side dashboard data: health, data coverage, launch checklist, bot event feed, paper-vs-backtest drift, memory
insights and the confluence leaderboard (contract: research/DASHBOARD_API.md). Read-only: nothing here starts, stops or
arms the bot, and no credential (TradingView key, bridge URL, Tradovate env) is ever returned.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from zoneinfo import ZoneInfo

from . import dash_data as D
from . import dash_metrics as M

ROOT = D.ROOT
DATA = D.DATA
ET = ZoneInfo("America/New_York")
LAUNCH = dt.datetime(2026, 10, 18, 18, 0, tzinfo=ET)
BOUND = {"watchdog": None, "live_arm": None}        # filled by server.py (DASH EXTRAS block)
_lock = threading.Lock()
_cache: dict = {}

try:
    import psutil
    psutil.cpu_percent(interval=None)                # prime: the first call always returns 0.0
    _PROC = psutil.Process()
    _PROC.cpu_percent(interval=None)
except Exception:                                    # pragma: no cover
    psutil = None
    _PROC = None


def bind(**kw):
    BOUND.update(kw)


def _bot():
    from .live import BOT
    return BOT


def _r(v, nd=1):
    return None if v is None else round(float(v), nd)


# ------------------------------------------------------------------ Windows scheduled task (slow: cached, background)
_task = {"t": 0, "val": None, "running": False}


def task_installed():
    if os.name != "nt":
        return None
    if time.time() - _task["t"] > 600 and not _task["running"]:
        def work():
            _task["running"] = True
            try:
                rc = subprocess.run(["schtasks", "/Query", "/TN", "LiquidityEngine"], capture_output=True, timeout=8).returncode
                _task["val"] = rc == 0
            except Exception:
                _task["val"] = None
            _task.update(t=time.time(), running=False)
        threading.Thread(target=work, daemon=True).start()
    return _task["val"]


# ------------------------------------------------------------------ health
def health():
    bot = _bot()
    h = dict(bot.health or {})
    out = {"status": "ok", "python": platform.python_version(), "platform": platform.platform(terse=True)}
    if psutil:
        vm = psutil.virtual_memory()
        du = psutil.disk_usage(os.path.splitdrive(ROOT)[0] + os.sep if os.name == "nt" else "/")
        out["system"] = {"cpu_pct": psutil.cpu_percent(interval=None), "cpu_count": psutil.cpu_count(), "mem_pct": vm.percent,
                         "mem_used_gb": _r(vm.used / 2 ** 30, 2), "mem_total_gb": _r(vm.total / 2 ** 30, 2), "disk_pct": du.percent,
                         "disk_free_gb": _r(du.free / 2 ** 30, 1), "boot_t": int(psutil.boot_time())}
        with _PROC.oneshot():
            out["process"] = {"pid": _PROC.pid, "uptime_s": int(time.time() - _PROC.create_time()),
                              "rss_mb": _r(_PROC.memory_info().rss / 2 ** 20, 1), "threads": _PROC.num_threads(),
                              "cpu_pct": _PROC.cpu_percent(interval=None)}
    sup = None
    try:
        with open(os.path.join(ROOT, "logs", "supervisor.pid")) as fh:
            pid = int(fh.read().strip() or 0)
        sup = {"pid": pid, "alive": bool(psutil and psutil.pid_exists(pid))}
    except Exception:
        pass
    out["supervisor"] = sup
    out["bot"] = {"running": bool(bot.running), "adapter": (bot.cfg or {}).get("adapter"), "data_source": h.get("data_source"),
                  "kill": bool(bot.kill), "last_poll": bot.last_poll, "last_ok_poll": h.get("last_ok_poll"), "poll_ms": h.get("poll_ms"),
                  "poll_sec": (bot.cfg or {}).get("poll_sec"), "errors": bot.errors, "consecutive_errors": h.get("consecutive_errors"),
                  "data_age_s": h.get("data_age_s"), "stale": h.get("stale"), "market_open": h.get("market_open"),
                  "entries_blocked": h.get("entries_blocked"), "desync": h.get("desync"), "revisions": h.get("revisions"),
                  "fallback": h.get("fallback"), "dropped": h.get("dropped"), "last_error": h.get("last_error"),
                  "last_error_t": h.get("last_error_t"), "ok": h.get("ok")}
    wd = BOUND.get("watchdog")
    st = {}
    if wd is not None:
        try:
            st = wd.status()
        except Exception as e:
            st = {"error": str(e)}
    out["watchdog"] = {"ok": st.get("ok"), "issues": st.get("issues"), "thread_alive": st.get("thread_alive"),
                       "last_check": st.get("last_check"), "server_started_at": st.get("server_started_at")}
    ka = st.get("keepawake") or {}
    out["keepawake"] = {"held": ka.get("held"), "want": ka.get("want"), "since": ka.get("since"), "supported": ka.get("supported"),
                        "last_error": ka.get("last_error")}
    au = st.get("autostart") or {}
    rec = os.path.exists(os.path.join(DATA, "autostart.json"))
    out["autostart"] = {"record": rec, "resumed": au.get("resumed"), "mode": au.get("mode"), "reason": au.get("reason"),
                        "checked_at": au.get("checked_at"), "task_installed": task_installed()}
    log = os.path.join(ROOT, "logs", f"server-{time.strftime('%Y%m%d')}.log")
    out["log"] = {"path": os.path.relpath(log, ROOT), "size_kb": _r(os.path.getsize(log) / 1024, 1) if os.path.exists(log) else None}
    issues = list(st.get("issues") or [])
    if not bot.running:
        issues.append("bot not running")
    if h.get("stale") and h.get("market_open"):
        issues.append("data feed stale")
    out["ok"] = not issues
    out["issues"] = issues
    return out


# ------------------------------------------------------------------ data coverage (built in the job subprocess)
COVER_SYMS = ("NQ", "ES")
COVER_TFS = ("1m", "5m", "15m", "1h", "1d")


def _cover_files():
    out = []
    for s in COVER_SYMS:
        for tf in COVER_TFS:
            p = os.path.join(DATA, f"{s}_{tf}.csv")
            if os.path.exists(p):
                out.append((s, tf, p))
    ltf = os.path.join(DATA, "ltf")
    if os.path.isdir(ltf):
        for f in sorted(os.listdir(ltf)):
            if f.endswith("_1m.csv"):
                out.append((f[:-7], "1m", os.path.join(ltf, f)))
    return out


def coverage_spec():
    mt = "|".join(f"{os.path.basename(p)}:{int(os.path.getmtime(p))}" for _, _, p in _cover_files())
    return {"kind": "coverage", "v": 2, "m": hashlib.md5(mt.encode()).hexdigest()[:10]}


def job_coverage(spec):
    import numpy as np
    import pandas as pd
    secs = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}
    rows = []
    files = _cover_files()
    for k, (sym, tf, path) in enumerate(files):
        D._progress(k, len(files), os.path.basename(path))
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        if "time" not in df.columns:
            continue
        t = df["time"].values.astype("int64")
        ts = pd.to_datetime(t, unit="s", utc=True).tz_convert(ET)
        # daily files are stamped at UTC midnight of the session date; intraday bars roll to the next day at 18:00 ET
        date = (ts + pd.Timedelta(hours=6)).strftime("%Y-%m-%d") if tf != "1d" else pd.to_datetime(t, unit="s", utc=True).strftime("%Y-%m-%d")
        days = sorted(set(date))
        a, z = dt.date.fromisoformat(days[0]), dt.date.fromisoformat(days[-1])
        have, miss, d = set(days), [], a
        while d <= z:
            if d.weekday() < 5 and d.isoformat() not in have:
                miss.append(d.isoformat())
            d += dt.timedelta(days=1)
        gaps = []
        if tf in ("1m", "5m", "15m"):
            mod = (ts.hour * 60 + ts.minute).values
            rth = (mod >= 570) & (mod < 960)
            tt, dd = t[rth], np.asarray(date)[rth]
            if len(tt) > 1:
                step = np.diff(tt)
                same = dd[1:] == dd[:-1]
                bad = np.where(same & (step > 3 * secs[tf]))[0]
                gaps = [{"date": str(dd[i]), "from_t": int(tt[i]), "to_t": int(tt[i + 1]), "missing_bars": int(step[i] // secs[tf]) - 1}
                        for i in bad]
        rows.append({"sym": sym, "tf": tf, "file": os.path.relpath(path, DATA).replace("\\", "/"), "rows": int(len(df)),
                     "from": days[0], "to": days[-1], "sessions": len(days), "first_t": int(t.min()), "last_t": int(t.max()),
                     "missing_weekdays": len(miss), "missing_sample": miss[-20:], "intraday_gaps": len(gaps), "gap_sample": gaps[-10:],
                     "size_kb": round(os.path.getsize(path) / 1024, 1), "mtime": int(os.path.getmtime(path))})
    D._progress(len(files), len(files), "done")
    return {"files": rows}


def coverage():
    obj, st = D.computed(coverage_spec())
    man = {}
    try:
        with open(os.path.join(DATA, "clean", "manifest.json"), encoding="utf-8") as fh:
            man = json.load(fh)
    except Exception:
        pass
    src = {r["source"]: {k: r[k] for k in ("from", "to", "sessions")} for r in man.get("nq_session_source_ranges", [])}
    base = {"sources": src, "manifest_generated": man.get("generated_at"), "price_space": man.get("price_space"),
            "volume_units": man.get("volume_units"), "note": "missing_weekdays includes CME exchange holidays; CFD data is never listed"}
    if obj is None:
        return {"status": st["status"], "job": st["job"], "retry_after_s": 5, **base}
    return {"status": "ok", "stale": st["status"] == "stale", "computed_at": obj.get("computed_at"), "files": obj["result"]["files"], **base}


# ------------------------------------------------------------------ bot event feed
LEVEL = {"error": "error", "warn": "warn", "risk": "warn", "news": "warn"}


def feed(since=0, types=None, limit=100):
    bot = _bot()
    want = {t.strip() for t in (types or "").split(",") if t.strip()}
    rows, counts = [], {}
    for e in list(bot.log):
        counts[e.get("type")] = counts.get(e.get("type"), 0) + 1
        if e.get("t", 0) <= since or (want and e.get("type") not in want):
            continue
        r = {k: v for k, v in e.items() if k != "result"}
        r["level"] = LEVEL.get(e.get("type"), "info")
        rows.append(r)
        if len(rows) >= limit:
            break
    return {"status": "ok" if rows else "no_data", "count": len(rows), "events": rows, "types": counts, "running": bool(bot.running),
            **({} if rows else {"message": "no bot events in this range"})}


# ------------------------------------------------------------------ paper vs backtest drift
def drift():
    paper = D.paper_dataset()
    if not paper["trades"]:
        return {"status": "no_data", "message": "No completed paper trades yet: drift appears after the first paper trade."}
    days = sorted({t["day"] for t in paper["trades"]})
    data, meta = D.dataset("backtest", days[0], days[-1])
    if data is None:
        return {"status": meta["status"], "job": meta.get("job"), "retry_after_s": meta.get("retry_after_s"), "message": meta.get("message")}
    bt = [t for t in data["trades"] if t["day"] in set(days)]
    used, pairs = set(), []
    for p in paper["trades"]:
        best = None
        for k, b in enumerate(bt):
            if k in used or b["dir"] != p["dir"] or abs(b["entry_t"] - p["entry_t"]) > 600:
                continue
            if best is None or abs(b["entry_t"] - p["entry_t"]) < abs(bt[best]["entry_t"] - p["entry_t"]):
                best = k
        slim = lambda t: {k: t.get(k) for k in ("entry_t", "exit_t", "dir", "entry", "exit_price", "r", "pnl", "grade", "exit_reason")}
        if best is None:
            pairs.append({"day": p["day"], "paper": slim(p), "backtest": None, "match": "paper_only"})
        else:
            used.add(best)
            b = bt[best]
            pairs.append({"day": p["day"], "paper": slim(p), "backtest": slim(b), "match": "matched",
                          "r_diff": round((p.get("r") or 0) - (b.get("r") or 0), 3), "pnl_diff": round((p.get("pnl") or 0) - (b.get("pnl") or 0), 2),
                          "entry_slip_min": round((p["entry_t"] - b["entry_t"]) / 60, 1),
                          "entry_px_diff": round((p.get("entry") or 0) - (b.get("entry") or 0), 2) if p.get("entry") and b.get("entry") else None})
    for k, b in enumerate(bt):
        if k not in used:
            pairs.append({"day": b["day"], "paper": None, "backtest": {kk: b.get(kk) for kk in ("entry_t", "dir", "r", "pnl", "grade")},
                          "match": "backtest_only"})
    pairs.sort(key=lambda x: (x["paper"] or x["backtest"])["entry_t"])
    m = [x for x in pairs if x["match"] == "matched"]
    n_p, n_b = len(paper["trades"]), len(bt)
    return {"status": "ok", "days": days, "pairs": pairs, "backtest_meta": meta,
            "summary": {"paper_trades": n_p, "backtest_trades": n_b, "matched": len(m),
                        "paper_only": sum(1 for x in pairs if x["match"] == "paper_only"),
                        "backtest_only": sum(1 for x in pairs if x["match"] == "backtest_only"),
                        "match_rate": round(len(m) / max(n_p, n_b) * 100, 1) if max(n_p, n_b) else None,
                        "paper_pnl": round(sum(t["pnl"] or 0 for t in paper["trades"]), 2), "backtest_pnl": round(sum(t["pnl"] or 0 for t in bt), 2),
                        "avg_entry_slip_min": round(sum(x["entry_slip_min"] for x in m) / len(m), 2) if m else None}}


# ------------------------------------------------------------------ memory insights
def memory_insights():
    from .memory import MEMORY
    from .model import DEFAULTS
    lm, th = int(DEFAULTS.get("exit_learn_min", 20)), float(DEFAULTS.get("exit_learn_threshold", 0.2))
    try:
        counts = {s: MEMORY.count((s,)) for s in ("paper", "live", "backtest")}
        realised = MEMORY.stats(None, lm, th)
        sigs = MEMORY.signal_summary(("paper", "live"), lm, th)
        calib = MEMORY.calibration()
        states = {k: {"updated_at": v["updated_at"]} for k, v in MEMORY.states().items()}
    except Exception as e:
        return {"status": "no_data", "message": f"memory unavailable: {e}"}
    real_n = counts["paper"] + counts["live"]
    src = "paper" if counts["paper"] >= 20 else "backtest"
    data, meta = D.dataset(src)
    cond = M.conditions(data["trades"]) if data else None
    sig_bt = []
    if src == "backtest" and data:
        for x in data.get("exit_signals") or []:
            sig_bt.append({k: x.get(k) for k in x if k in ("key", "name", "n", "avg_gain", "fired", "acted", "helped", "hurt", "total_gain")})
    msg = None if real_n else "No paper or live trades in memory yet; conditions and exit-signal evidence come from the backtest."
    return {"status": "ok", "counts": counts,
            "realised": {k: realised.get(k) for k in ("trades", "wins", "win_rate", "net", "avg_r", "total_r", "profit_factor",
                                                      "expectancy", "first_day", "last_day")},
            "by_grade": realised.get("by_grade"), "by_regime": realised.get("by_regime"), "by_exit": realised.get("by_exit"),
            "signals": sigs, "learner": {"learn_min": lm, "threshold": th, "learned": [s["key"] for s in sigs if s.get("learned")]},
            "backtest_signals": sig_bt, "conditions": {"source": src, "meta": meta, **(cond or {})}, "calibration": calib,
            "learner_states": states, **({"message": msg} if msg else {})}


# ------------------------------------------------------------------ confluence registry leaderboard
def confluence(status=None, sort="lift"):
    path = os.path.join(DATA, "confluence_registry.json")
    if not os.path.exists(path):
        return {"status": "no_data", "message": "data/confluence_registry.json not built yet"}
    mt = os.path.getmtime(path)
    with _lock:
        hit = _cache.get(("conf", mt))
    if hit is None:
        with open(path, encoding="utf-8") as fh:
            hit = json.load(fh)
        with _lock:
            _cache[("conf", mt)] = hit
    reg = hit
    want = {s.strip().upper() for s in (status or "").split(",") if s.strip()}
    items, counts = [], {}
    for it in (reg.get("items") or {}).values():
        st = it.get("status")
        counts[st] = counts.get(st, 0) + 1
        if want and st not in want:
            continue
        ev = (it.get("evidence") or {}).get("candidates") or {}
        tk = (it.get("evidence") or {}).get("taken") or {}
        sc = it.get("scan") or {}
        items.append({"id": it.get("id"), "name": it.get("name"), "status": st, "decision": it.get("decision"), "verdict": sc.get("verdict"),
                      "lift_pooled": ev.get("pooled"), "lift_decide": ev.get("decide"), "lift_confirm": ev.get("confirm"),
                      "n_on": ev.get("n_on"), "n_off": ev.get("n_off"), "ci90": ev.get("ci90"), "taken_lift": tk.get("pooled"),
                      "agree": sc.get("agree"), "valid": sc.get("valid"), "freq": sc.get("freq"), "es_agree": sc.get("es_agree"),
                      "wf_confirm": sc.get("wf_confirm"), "weight": it.get("weight"), "live": it.get("live"), "mechanism": it.get("mechanism"),
                      "reason": it.get("reason"), "first_seen": it.get("first_seen"), "retired": it.get("retired"),
                      "history": [h.get("status") for h in it.get("history") or []]})
    key = {"n": lambda x: -(x["n_on"] or 0), "name": lambda x: str(x["name"]),
           "lift": lambda x: -(x["lift_pooled"] if x["lift_pooled"] is not None else -99)}.get(sort, None)
    order = {"ACTIVE": 0, "PROBATION": 1, "CANDIDATE": 2, "RETIRED": 3}
    items.sort(key=lambda x: (order.get(x["status"], 9), key(x) if key else 0))
    lr = reg.get("last_run") or {}
    return {"status": "ok", "generated": reg.get("generated"), "futures_only": reg.get("futures_only"), "counts": counts,
            "rule": reg.get("rule"), "baseline": {k: v for k, v in (reg.get("baseline") or {}).items() if not isinstance(v, (list, dict))},
            "folds": reg.get("folds"), "data": reg.get("data"), "items": items,
            "last_run": {k: lr.get(k) for k in ("run", "started", "secs", "n_backtests", "n_tests", "counts", "added", "retired_live",
                                                "recommended_params")},
            "runs": [{k: r.get(k) for k in ("run", "started", "secs", "counts")} for r in (reg.get("runs") or [])[-20:]]}


# ------------------------------------------------------------------ launch checklist
def launch(now=None):
    now = int(now or time.time())
    bot = _bot()
    h = bot.health or {}
    checks = []

    def add(key, label, state, detail=None):
        checks.append({"key": key, "label": label, "state": state, "detail": detail})
    ad = (bot.cfg or {}).get("adapter")
    add("bot_running", "Paper bot running on this PC", "pass" if bot.running else "fail",
        f"adapter={ad}" if bot.running else "start it: POST /api/live/start with adapter=paper")
    add("adapter_paper", "Adapter is paper (this PC only mirrors the TradingView strategy)", "pass" if ad == "paper" else "fail", f"adapter={ad}")
    arm = BOUND.get("live_arm") or {}
    add("not_armed", "Live trading NOT armed on this PC", "pass" if not arm.get("armed") else "fail",
        "armed" if arm.get("armed") else "disarmed")
    add("kill_off", "Kill switch off", "pass" if not bot.kill else "warn", "KILL flag set" if bot.kill else None)
    wd = BOUND.get("watchdog")
    st = {}
    try:
        st = wd.status() if wd else {}
    except Exception:
        pass
    add("watchdog", "Watchdog healthy", "pass" if st.get("ok") else "warn", ", ".join(st.get("issues") or []) or None)
    ka = (st.get("keepawake") or {})
    add("keepawake", "PC kept awake while the bot runs", "pass" if ka.get("held") else "warn", None)
    add("autostart_record", "Auto-resume record saved (crash / reboot resumes paper)",
        "pass" if os.path.exists(os.path.join(DATA, "autostart.json")) else "warn", None)
    ti = task_installed()
    add("task", "Windows logon task installed (scripts/install_autostart.ps1)", "pass" if ti else ("info" if ti is None else "warn"),
        "checking" if ti is None else None)
    mo, age = h.get("market_open"), h.get("data_age_s")
    if mo:
        add("feed", "Live data feed fresh", "pass" if age is not None and age < 900 else "warn", f"last bar {age}s old" if age is not None else None)
    else:
        add("feed", "Live data feed", "info", "market closed: feed resumes Sun 18:00 ET")
    try:
        last = None
        with open(os.path.join(DATA, "NQ_5m.csv"), "rb") as fh:
            fh.seek(max(0, os.path.getsize(fh.name) - 200))
            last = int(fh.read().decode().strip().splitlines()[-1].split(",")[0])
        days_old = (now - last) / 86400
        add("history", "NQ 5m history up to date (CME NQ1!)", "pass" if days_old < 4 else "warn",
            f"last stored bar {dt.datetime.fromtimestamp(last, ET):%Y-%m-%d %H:%M} ET")
    except Exception as e:
        add("history", "NQ 5m history up to date", "warn", str(e)[:120])
    tvd = os.path.join(ROOT, "tradingview")
    add("pine", "Pine strategy file present", "pass" if os.path.exists(os.path.join(tvd, "liquidity_engine.pine")) else "fail",
        "tradingview/liquidity_engine.pine")
    add("bridge_doc", "Bridge setup guide present", "pass" if os.path.exists(os.path.join(tvd, "BRIDGE_SETUP.md")) else "warn",
        "tradingview/BRIDGE_SETUP.md")
    wk0 = LAUNCH.date() + dt.timedelta(days=1)
    wk1 = wk0 + dt.timedelta(days=4)
    try:
        from . import calendar_week as cw
        need = cw.pine_entries(wk0, wk1, use_feed=False)
        txt = open(os.path.join(tvd, "blackouts.txt"), encoding="utf-8").read() if os.path.exists(os.path.join(tvd, "blackouts.txt")) else None
        if txt is None:
            add("blackouts", f"Pine blackouts for {wk0}..{wk1}", "fail", "tradingview/blackouts.txt missing")
        else:
            miss = [e for e in need if e not in txt]
            add("blackouts", f"Pine blackouts for {wk0}..{wk1}", "pass" if not miss else "warn",
                f"{len(need)} high-impact release(s) that week" + (f"; missing: {', '.join(miss)}" if miss else ""))
    except Exception as e:
        add("blackouts", "Pine blackouts", "warn", str(e)[:120])
    try:
        cfg = json.load(open(os.path.join(DATA, "tv.json")))
        add("webhook_key", "TradingView webhook key configured", "pass" if cfg.get("key") else "warn", "key set (not shown)" if cfg.get("key") else None)
    except Exception:
        add("webhook_key", "TradingView webhook key configured", "warn", "data/tv.json missing")
    try:
        from .memory import MEMORY
        add("memory", "Trade memory database ready", "pass" if MEMORY.exists() else "warn", os.path.relpath(MEMORY.path, ROOT))
    except Exception as e:
        add("memory", "Trade memory database ready", "warn", str(e)[:120])
    data, meta = D.dataset("backtest")
    if data:
        fq = M.frequency(data["trades"], data["days"])["summary"]
        tpw = fq.get("tpw_overall")
        add("frequency", "Backtest trades/week inside the 2-4 rule", "pass" if tpw and 2 <= tpw <= 4 else "warn",
            f"{tpw} trades/week over {meta.get('sessions')} sessions; {fq.get('pct_in_band')}% of weeks in band")
        from .analytics import PLANS
        mc = M.mc_eval(data["days"], PLANS["builder_50k"], 2000, 60)
        if mc:
            add("mc", "Eval pass probability (60 sessions, backtest bootstrap)", "info",
                f"pass {mc['pass_prob']}% / fail {mc['fail_prob']}% / still open {mc['open_prob']}%")
    else:
        add("frequency", "Backtest trades/week inside the 2-4 rule", "info", f"dataset {meta.get('status')}")
    try:
        from .dash_market import news
        nw = news(days=(wk1 - dt.date.fromtimestamp(now)).days + 1, impact="medium", now=now)
        n_wk = sum(1 for e in nw["events"] if wk0.isoformat() <= e["date"] <= wk1.isoformat())
        add("calendar", "News calendar loaded for launch week", "pass" if n_wk else "warn", f"{n_wk} medium/high events")
    except Exception as e:
        add("calendar", "News calendar loaded for launch week", "warn", str(e)[:120])
    score = {s: sum(1 for c in checks if c["state"] == s) for s in ("pass", "warn", "fail", "info")}
    lt = int(LAUNCH.timestamp())
    return {"status": "ok", "launch_t": lt, "launch_label": "Sun 2026-10-18 18:00 ET", "in_s": lt - now, "launched": now >= lt,
            "ready": score["fail"] == 0, "score": score, "checks": checks}
