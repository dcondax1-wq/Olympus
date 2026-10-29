"""Datasets behind the /api/dash/* analytics (contract: research/DASHBOARD_API.md).

Three trade sources, one normalized shape (slim trades + per-session days):
  backtest  light backtest of the current model over a window (default: last DEFAULT_SESSIONS sessions)
  paper     completed paper trades the bot routed (data/memory.db, source 'paper')
  5y        five-year NQ history as independent 8-week windows (40 sessions + 25-session warm-up), merged

Backtests never run inside the server process: a background subprocess (`python -m engine.dash_data --job ...`, below-normal
priority) writes cache/dash/<key>.json and the server only reads JSON. A result is keyed by its window and fingerprinted
by the data files + model code it came from; when the fingerprint changes the last good result is served as `stale`
while a recompute runs (at most once per RECOMPUTE_MIN_S per key). Real CME futures only: data/_cfd_archive is never read.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "cache", "dash")
ET = ZoneInfo("America/New_York")

DEFAULT_SESSIONS = 120          # default backtest window
WARM_SESS = 25                  # warm-up sessions before every window (pools, ADR, 10-day regime, 1h structure)
WIN_SESS = 40                   # 5y: 8-week test windows
RECOMPUTE_MIN_S = 600           # never rebuild the same key more often than this (other sessions edit model.py often)
MAX_CACHE_FILES = 40
FP_CODE = ("model.py", "backtest.py", "data.py", "mtf.py", "learn.py", "ict_features.py", "instruments.py", "analytics.py",
           "dash_data.py")
FP_DATA = ("NQ_5m.csv", "NQ_1h.csv", "ES_5m.csv", "NQ_1m.csv", os.path.join("news", "events.csv"))

SLIM_KEYS = ("day", "entry_t", "exit_t", "dir", "entry", "exit_price", "stop0", "target", "risk_pts", "qty", "qty_label",
             "pnl", "mae", "mfe", "grade", "grade_points", "trigger", "trigger_tf", "pools", "target_label", "regime",
             "exit_reason", "exit_signal", "score", "bars_held", "model", "sweep_ext", "signal_t", "pd_pos", "open_loc", "rr")


# ------------------------------------------------------------------ helpers
def _f(v, nd=None):
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return round(x, nd) if nd is not None else x


def _py(v):
    if hasattr(v, "item") and not isinstance(v, (list, dict, str)):
        try:
            return v.item()
        except Exception:
            pass
    if isinstance(v, (list, tuple)):
        return [_py(x) for x in v]
    return v


def slim_trade(t: dict) -> dict:
    out = {k: _py(t.get(k)) for k in SLIM_KEYS if k in t}
    out["r"] = _f(t.get("pnl_r", t.get("r")), 3)
    for k in ("pnl", "entry", "exit_price", "stop0", "target", "risk_pts", "sweep_ext"):
        if k in out:
            out[k] = _f(out[k], 2)
    for k in ("mae", "mfe", "pd_pos", "rr"):
        if k in out:
            out[k] = _f(out[k], 3)
    if not out.get("day") and out.get("entry_t"):
        out["day"] = trading_day(out["entry_t"])
    return out


def slim_day(d: dict) -> dict:
    return {"date": d["date"], "dow": d.get("dow", dt.date.fromisoformat(d["date"]).weekday()), "pnl": _f(d.get("pnl"), 2) or 0.0,
            "trades": int(d.get("trades") or 0), "er5": _f(d.get("er5"), 3), "er10": _f(d.get("er10"), 3),
            "regime": d.get("regime"), "balance": _f(d.get("balance"), 2), "mll": _f(d.get("mll"), 2),
            "low": _f(d.get("low_intraday", min(0.0, float(d.get("pnl") or 0))), 2) or 0.0,
            "vol_expansion": _f(d.get("vol_expansion"), 3)}


def trading_day(ts) -> str:
    return (dt.datetime.fromtimestamp(int(ts), ET) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def today_session() -> str:
    """Current trading-day label (Sat/Sun roll to Monday)."""
    d = dt.date.fromisoformat(trading_day(time.time()))
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d.isoformat()


def _mt(path):
    try:
        st = os.stat(path)
        return f"{int(st.st_mtime)}:{st.st_size}"
    except OSError:
        return "-"


def fingerprint(spec: dict) -> str:
    parts = [json.dumps(spec, sort_keys=True)]
    parts += [_mt(os.path.join(ROOT, "engine", f)) for f in FP_CODE]
    parts += [_mt(os.path.join(DATA, f)) for f in FP_DATA]
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]


def code_version() -> str:
    return hashlib.md5("|".join(_mt(os.path.join(ROOT, "engine", f)) for f in FP_CODE).encode()).hexdigest()[:8]


def _atomic_write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"), default=_py)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, path)


def _iso_minus_sessions(day: str, n: int) -> str:
    """Approximate n sessions before `day` in calendar days (weekends skipped; holidays ignored)."""
    d = dt.date.fromisoformat(day)
    k = 0
    while k < n:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            k += 1
    return d.isoformat()


# ------------------------------------------------------------------ job specs
def backtest_spec(sym="NQ", days_from=None, days_to=None) -> dict:
    """Window spec. Default window = last DEFAULT_SESSIONS sessions up to today."""
    to = days_to or None
    frm = days_from or _iso_minus_sessions(today_session(), DEFAULT_SESSIONS - 1)
    for v in (frm, to):
        if v:
            dt.date.fromisoformat(v)          # raises ValueError on a bad date
    return {"kind": "bt", "sym": sym, "from": frm, "to": to, "default": not days_from and not days_to}


def spec_key(spec: dict) -> str:
    if spec["kind"] == "5y":
        return f"5y_{spec.get('sym', 'NQ')}"
    if spec["kind"] in ("es_fresh", "coverage"):
        return spec["kind"]
    if spec.get("default"):
        return f"bt_{spec['sym']}_default"
    return f"bt_{spec['sym']}_{spec['from']}_{spec['to'] or 'latest'}"


# ------------------------------------------------------------------ job bodies (run in the subprocess)
def _progress(a, b, msg):
    print(f"PROGRESS {a}/{b} {msg}", flush=True)


def _run_window(job):
    """(run_from, keep_from, keep_to, sym) -> slim trades/days kept in [keep_from, keep_to]."""
    run_from, k0, k1, sym = job
    from engine.backtest import run
    r = run(sym, "5m", {"days_from": run_from, "days_to": k1}, light=True)
    keep = lambda d: (k0 is None or d >= k0) and (k1 is None or d <= k1)
    return {"trades": [slim_trade(t) for t in r["trades"] if keep(t["day"])],
            "days": [slim_day(d) for d in r["days"] if keep(d["date"])],
            "exit_signals": r.get("exit_signals", []), "resets": len(r.get("account_resets", []))}


def job_bt(spec):
    _progress(0, 1, f"backtest {spec['from']}..{spec['to'] or 'latest'}")
    out = _run_window((_iso_minus_sessions(spec["from"], WARM_SESS), spec["from"], spec["to"], spec["sym"]))
    _progress(1, 1, "done")
    days = out["days"]
    return {"trades": out["trades"], "days": days, "exit_signals": out["exit_signals"], "account_resets": out["resets"],
            "from": days[0]["date"] if days else spec["from"], "to": days[-1]["date"] if days else spec["to"], "windows": 1}


def job_5y(spec):
    from multiprocessing import Pool
    from engine.data import load
    sym = spec.get("sym", "NQ")
    ss = sorted(set(load(sym, "5m").date_str))
    jobs = []
    for a in range(WARM_SESS, len(ss), WIN_SESS):
        z = min(a + WIN_SESS, len(ss)) - 1
        jobs.append((ss[a - WARM_SESS], ss[a], ss[z], sym))
    procs = max(1, min(3, (os.cpu_count() or 2) // 3, len(jobs)))
    try:                                  # each worker holds the full 5-year history (~0.5 GB): never squeeze the bot's RAM
        import psutil
        procs = max(1, min(procs, int(psutil.virtual_memory().available / 2 ** 30 / 0.7)))
    except Exception:
        pass
    outs = []
    _progress(0, len(jobs), f"{len(jobs)} windows on {procs} processes")
    with Pool(procs) as p:
        for k, o in enumerate(p.imap(_run_window, jobs), 1):
            outs.append(o)
            _progress(k, len(jobs), f"window {jobs[k - 1][1]}")
    trades = sorted([t for o in outs for t in o["trades"]], key=lambda t: t["entry_t"])
    days = sorted([d for o in outs for d in o["days"]], key=lambda d: d["date"])
    return {"trades": trades, "days": days, "exit_signals": [], "account_resets": sum(o["resets"] for o in outs),
            "from": days[0]["date"] if days else None, "to": days[-1]["date"] if days else None, "windows": len(jobs),
            "window_sessions": WIN_SESS, "warmup_sessions": WARM_SESS}


def job_es_fresh(spec):
    """Fresh ES 5m bars from Yahoo ES=F (CME futures), in this subprocess so yfinance never runs beside the bot."""
    from engine.live import _yahoo_recent
    from engine import pcbars
    if pcbars.no_yahoo():           # no Yahoo (owner 2026-10-19): the stored CME ES history only
        _progress(1, 1, "no_yahoo: stored ES history only")
        return {"rows": []}
    _progress(0, 1, "yahoo ES=F 5m")
    df = _yahoo_recent("ES", "5m", "5d")
    rows = [] if df is None or df.empty else df[["time", "open", "high", "low", "close", "volume"]].values.tolist()
    _progress(1, 1, f"{len(rows)} bars")
    return {"rows": rows}


def job_coverage(spec):
    from engine.dash_system import job_coverage as jc
    return jc(spec)


JOBS = {"bt": job_bt, "5y": job_5y, "es_fresh": job_es_fresh, "coverage": job_coverage}


def run_job(spec: dict) -> str:
    t0 = time.time()
    res = JOBS[spec["kind"]](spec)
    path = os.path.join(CACHE, spec_key(spec) + ".json")
    _atomic_write(path, {"spec": spec, "fp": spec.get("_fp") or fingerprint({k: v for k, v in spec.items() if k != "_fp"}),
                         "version": code_version(), "computed_at": int(time.time()), "secs": round(time.time() - t0, 1),
                         "result": res})
    return path


# ------------------------------------------------------------------ server side: job manager + cache reads
class Jobs:
    """One background subprocess at a time; specs queue up, duplicates are ignored."""

    def __init__(self):
        self.q = queue.Queue()
        self.lock = threading.Lock()
        self.state = {}              # key -> {state, started, finished, step, steps, msg, error, secs}
        self.last_start = {}         # key -> time the last build started (rate limit)
        self.worker = None

    def _ensure_worker(self):
        if self.worker is None or not self.worker.is_alive():
            self.worker = threading.Thread(target=self._loop, name="dash-jobs", daemon=True)
            self.worker.start()

    def submit(self, spec: dict, force=False) -> bool:
        key = spec_key(spec)
        with self.lock:
            st = self.state.get(key, {})
            if st.get("state") in ("queued", "running"):
                return False
            if not force and time.time() - self.last_start.get(key, 0) < RECOMPUTE_MIN_S:
                return False
            self.state[key] = {"key": key, "state": "queued", "queued": int(time.time()), "step": 0, "steps": 1, "msg": "queued",
                               "error": None}
            self.last_start[key] = time.time()
        self.q.put(spec)
        self._ensure_worker()
        return True

    def status(self, key):
        with self.lock:
            return dict(self.state.get(key) or {})

    def all(self):
        with self.lock:
            return [dict(v) for v in self.state.values()]

    def _loop(self):
        while True:
            spec = self.q.get()
            key = spec_key(spec)
            with self.lock:
                self.state[key].update(state="running", started=int(time.time()), msg="starting")
            flags = 0x00004000 if os.name == "nt" else 0          # BELOW_NORMAL_PRIORITY_CLASS: the bot always wins the CPU
            tail = []
            try:
                proc = subprocess.Popen([sys.executable, "-u", "-m", "engine.dash_data", "--job", json.dumps(spec)], cwd=ROOT,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                        errors="replace", creationflags=flags)
                for raw in iter(proc.stdout.readline, ""):
                    line = raw.rstrip()
                    if line.startswith("PROGRESS "):
                        try:
                            frac, msg = line[9:].split(" ", 1)
                            a, b = frac.split("/")
                            with self.lock:
                                self.state[key].update(step=int(a), steps=int(b), msg=msg)
                        except ValueError:
                            pass
                    elif line:
                        tail = (tail + [line])[-8:]
                rc = proc.wait()
                with self.lock:
                    s = self.state[key]
                    s.update(state="done" if rc == 0 else "failed", finished=int(time.time()),
                             secs=round(time.time() - s.get("started", time.time()), 1),
                             error=None if rc == 0 else ("; ".join(tail) or f"exit {rc}")[-600:])
            except Exception as e:
                with self.lock:
                    self.state[key].update(state="failed", finished=int(time.time()), error=f"{e.__class__.__name__}: {e}")
            _prune_cache()


JOBS_MGR = Jobs()
_mem = {}                            # path -> (mtime, parsed json)
_mem_lock = threading.Lock()


def _prune_cache():
    try:
        files = sorted((os.path.join(CACHE, f) for f in os.listdir(CACHE) if f.endswith(".json")), key=os.path.getmtime)
        keep = {"5y_NQ.json", "bt_NQ_default.json", "es_fresh.json", "coverage.json"}
        extra = [f for f in files if os.path.basename(f) not in keep]
        for f in extra[:-MAX_CACHE_FILES]:
            os.remove(f)
    except OSError:
        pass


def read_cache(key: str):
    path = os.path.join(CACHE, key + ".json")
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    with _mem_lock:
        hit = _mem.get(path)
        if hit and hit[0] == mt:
            return hit[1]
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except Exception:
        return None
    with _mem_lock:
        _mem[path] = (mt, obj)
        if len(_mem) > 24:
            _mem.pop(next(iter(_mem)))
    return obj


def computed(spec: dict, autostart=True):
    """(cache object | None, status). status: ok | stale | computing (+ job progress) | failed."""
    spec = dict(spec)
    fp = fingerprint(spec)
    spec["_fp"] = fp
    key = spec_key(spec)
    obj = read_cache(key)
    job = JOBS_MGR.status(key)
    fresh = obj is not None and obj.get("fp") == fp
    if not fresh and autostart:
        JOBS_MGR.submit(spec, force=obj is None and job.get("state") != "failed")
        job = JOBS_MGR.status(key)
    if obj is not None:
        return obj, {"status": "ok" if fresh else "stale", "job": job or None}
    return None, {"status": "failed" if job.get("state") == "failed" else "computing", "job": job or None}


# ------------------------------------------------------------------ paper source (memory.db)
_paper = {"t": 0, "val": None}


def paper_dataset(since: str | None = None):
    """Completed paper trades from memory.db, as the same {trades, days} shape. Days = every weekday from the first
    paper trade (or `since`) to today, so zero-trade weeks count."""
    now = time.time()
    if since is None and _paper["val"] is not None and now - _paper["t"] < 15:
        return _paper["val"]
    from engine.memory import MEMORY
    rows = MEMORY.recent(5000, "paper") if MEMORY.exists() else []
    trades = sorted((slim_trade(r) for r in rows if r.get("exit_t")), key=lambda t: t["entry_t"])
    if since:
        trades = [t for t in trades if t["day"] >= since]
    start = since or (trades[0]["day"] if trades else None)
    days = []
    if start:
        by = {}
        for t in trades:
            by.setdefault(t["day"], []).append(t)
        d, end = dt.date.fromisoformat(start), dt.date.fromisoformat(today_session())
        while d <= end:
            if d.weekday() < 5:
                ts = by.get(d.isoformat(), [])
                pnl = round(sum(t["pnl"] or 0 for t in ts), 2)
                days.append({"date": d.isoformat(), "dow": d.weekday(), "pnl": pnl, "trades": len(ts), "er5": None, "er10": None,
                             "regime": ts[0].get("regime") if ts else None, "balance": None, "mll": None,
                             "low": min(0.0, pnl), "vol_expansion": None})
            d += dt.timedelta(days=1)
    val = {"trades": trades, "days": days, "exit_signals": [], "from": start, "to": days[-1]["date"] if days else None}
    if since is None:
        _paper.update(t=now, val=val)
    return val


# ------------------------------------------------------------------ one entry point for the endpoints
def dataset(source="backtest", days_from=None, days_to=None, sym="NQ"):
    """-> (data | None, meta). meta carries status (ok | stale | computing | failed | no_data) and dataset facts."""
    source = (source or "backtest").lower()
    if source in ("bt", "backtest"):
        spec = backtest_spec(sym, days_from, days_to)
        obj, st = computed(spec)
        meta = {"source": "backtest", "sym": sym, "window": {"from": spec["from"], "to": spec["to"]}}
    elif source in ("5y", "fiveyear", "history"):
        spec = {"kind": "5y", "sym": sym}
        obj, st = computed(spec)
        meta = {"source": "5y", "sym": sym}
    elif source == "paper":
        data = paper_dataset()
        meta = {"source": "paper", "sym": sym, "from": data["from"], "to": data["to"], "sessions": len(data["days"]),
                "trades": len(data["trades"]), "computed_at": int(time.time()), "stale": False}
        if not data["trades"]:
            return None, {**meta, "status": "no_data",
                          "message": "No completed paper trades yet. The paper bot records every routed trade in data/memory.db."}
        return data, {**meta, "status": "ok"}
    else:
        raise ValueError("source must be backtest, paper or 5y")
    if obj is None:
        return None, {**meta, "status": st["status"], "job": st["job"], "retry_after_s": 5 if source != "5y" else 15,
                      "message": "building the dataset in the background" if st["status"] == "computing"
                      else f"dataset build failed: {(st['job'] or {}).get('error')}"}
    res = obj["result"]
    meta.update({"from": res.get("from"), "to": res.get("to"), "sessions": len(res["days"]), "trades": len(res["trades"]),
                 "computed_at": obj.get("computed_at"), "build_secs": obj.get("secs"), "stale": st["status"] == "stale",
                 "model_version": obj.get("version"), "status": "ok"})
    if res.get("windows", 1) > 1:
        meta["windows"] = res["windows"]
    if st["status"] == "stale":
        meta["job"] = st["job"]
    return res, meta


def warm():
    """Queue the default datasets (server start-up)."""
    for spec in (backtest_spec(), {"kind": "5y", "sym": "NQ"}):
        try:
            computed(spec)
        except Exception as e:
            print(f"[dash] warm-up failed for {spec}: {e}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--job":
        sys.path.insert(0, ROOT)
        print("wrote", run_job(json.loads(sys.argv[2])), flush=True)
    else:
        print(__doc__)
