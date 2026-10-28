"""Background worker PROCESS for the PC bot's read-only, CPU-heavy paper work (owner's Surface 2026-10-26: polls of 5-32 s).

Why: Python runs one thread at a time per process (the GIL). The paper work the PC bot started in threads after LIT's
routing (second strategies + stop-hunt candidates ~0.8 s, the ATLAS v2 shadow ~2.4 s, trade pictures ~0.5 s a chart, all
on this 4-core box; ~5x that on the Surface) ran while the next poll ran, and the poll's LIT decision waited for the GIL:
measured here, the LIT part of a poll went from ~0.57 s to 2.5 s (median) / 5 s (p90) with them on
(tests/test_poll_speed.py). In a separate process they cannot hold the trading process's GIL at all.

What runs here (never anything that decides, sizes or routes an order):
  "second"  engine/second.run (the ATLAS members + the stop-hunt candidates, PAPER) + engine/atlas_v2.pc_step (the
            ATLAS v2 PAPER shadow, its own file) + engine/blitz.pc_step (the BLITZ scalper PAPER shadow, its own file)
                                                          <- LiveBot._second_tick
  "charts"  engine/trade_chart.PcCharts.draw (the trade pictures, logs/charts/)  <- LiveBot._chart_tick
Account B (ATLAS on its own account) and the routed second strategies ROUTE orders: they stay in the trading loop.

How: one child `python -m engine.bg_worker` at a lower CPU priority (Windows BELOW_NORMAL_PRIORITY_CLASS, elsewhere nice
10): the trading process, NinjaTrader and the dashboard always win the CPU. Jobs go to its stdin and results come back on
its stdout as length-prefixed pickles. The bars go as deltas: the child keeps a copy of each bar frame and only the rows
that changed since the last job are sent (the 5-year 5m history is sent once). submit() never blocks the caller (a sender
thread writes, a receiver thread hands each result to the job's callback). One job of a kind at a time per owner: a kind
still running is "busy" (the caller skips the tick, as the threads did). A child that dies or hangs (JOB_TIMEOUT_S) is
restarted; one that keeps failing, or LE_BG_WORKER=0, turns the worker off and the callers use their old in-process thread.
The results are the same as in process: the same functions on the same bars (tests/test_poll_speed.py checks it).
"""
from __future__ import annotations

import atexit
import os
import pickle
import struct
import subprocess
import sys
import threading
import time
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAIL = 2000                    # rows always re-sent at the end of a frame (new bars, a revised bar, the forming one)
JOB_TIMEOUT_S = 600.0          # a job running longer than this = a hung child: killed and restarted
MAX_FAILS = 3                  # child deaths in a row (no job finished in between) before the worker turns itself off
RESTART_GAP_S = 20.0           # at least this long between two child starts
BELOW_NORMAL = 0x00004000      # Windows BELOW_NORMAL_PRIORITY_CLASS
NO_WINDOW = 0x08000000         # Windows CREATE_NO_WINDOW
_HDR = struct.Struct(">Q")


def enabled(env=None) -> bool:
    return (os.environ if env is None else env).get("LE_BG_WORKER", "1") != "0"


# ------------------------------------------------------------------------------------------------ wire format
def _write(fh, obj) -> None:
    b = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    fh.write(_HDR.pack(len(b)))
    fh.write(b)
    fh.flush()


def _read_exact(fh, n: int) -> bytes | None:
    out = bytearray()
    while len(out) < n:
        b = fh.read(n - len(out))
        if not b:
            return None
        out += b
    return bytes(out)


def _read(fh):
    h = _read_exact(fh, _HDR.size)
    if h is None:
        return None
    b = _read_exact(fh, _HDR.unpack(h)[0])
    return None if b is None else pickle.loads(b)


# ------------------------------------------------------------------------------------------------ bar frames as deltas
def _arrays(df) -> dict:
    return {c: df[c].to_numpy() for c in df.columns}


def _plain_index(df) -> bool:
    import pandas as pd
    ix = df.index
    return isinstance(ix, pd.RangeIndex) and ix.start == 0 and ix.step == 1


def frame_packet(df, prev: dict | None) -> tuple:
    """(packet, new prev) for one bar frame. prev = what the child holds (the last packet's frame: {"cols", "arr", "plain"}).
    The packet carries only the rows from `keep` on when the child's first `keep` rows are exactly this frame's."""
    import numpy as np
    if df is None:
        return {"none": True}, None
    cols = list(df.columns)
    arr = _arrays(df)
    plain = _plain_index(df)
    n = len(df)
    keep = 0
    if prev is not None and prev["cols"] == cols and prev["plain"] and plain:
        k = min(prev["n"], n) - TAIL
        if k > 0 and all(prev["arr"][c].dtype == arr[c].dtype and
                         np.array_equal(prev["arr"][c][:k], arr[c][:k], equal_nan=arr[c].dtype.kind == "f")
                         for c in cols):
            keep = k
    pk = {"cols": cols, "keep": keep, "n": n, "arr": {c: np.ascontiguousarray(arr[c][keep:]) for c in cols},
          "dtypes": {c: df[c].dtype for c in cols}, "index": None if plain else df.index.to_numpy()}
    return pk, {"cols": cols, "arr": arr, "n": n, "plain": plain}


def frame_apply(pk: dict, held):
    """The child side of frame_packet: the frame the parent has, from the held one + the packet."""
    import numpy as np
    import pandas as pd
    if pk.get("none"):
        return None
    k = int(pk["keep"])
    if k:
        if held is None or len(held) < k or list(held.columns) != pk["cols"]:
            raise RuntimeError("bar frame delta does not fit the held frame")
        data = {c: np.concatenate([held[c].to_numpy()[:k], pk["arr"][c]]) for c in pk["cols"]}
    else:
        data = {c: pk["arr"][c] for c in pk["cols"]}
    idx = pd.RangeIndex(pk["n"]) if pk["index"] is None else pk["index"]
    df = pd.DataFrame(data, columns=pk["cols"], index=idx)
    for c, dt_ in (pk.get("dtypes") or {}).items():
        if df[c].dtype != dt_:
            df[c] = df[c].astype(dt_)
    if len(df) != pk["n"]:
        raise RuntimeError("bar frame delta: wrong length")
    return df


# ------------------------------------------------------------------------------------------------ the jobs (child side)
def job_second(df5, df1, a: dict) -> dict:
    """engine/second.run + the ATLAS v2 shadow step: what LiveBot._second_tick's paper thread did, on the same bars."""
    from engine import second as _second
    cfg = a["cfg"]
    out = {"second": None, "atlas_v2": None, "av2": False, "blitz": None, "blz": False}
    err = None
    try:
        if any(s.get("on", True) for s in cfg["strategies"].values()):
            out["second"] = _second.run(df5, one_min=df1, now=a["now"], cfg=cfg, lit=a["lit"])
    except Exception as e:
        err = e
    if a.get("blitz_path"):                     # BLITZ PAPER shadow (engine/blitz.py): 1m bars + LIT / ATLAS state, own file, never raises
        from engine import blitz as _blz
        out["blitz"], out["blz"] = _blz.pc_step(a["blitz_path"], df1, a["now"], res=a.get("res"), second=out["second"],
                                                atlas_open=a.get("atlas_open")), True
    if err is not None:
        raise err
    if out["second"] is not None and a.get("av2_path"):
        from engine import atlas_v2 as _av2
        out["atlas_v2"], out["av2"] = _av2.pc_step(a["av2_path"], out["second"], a["res"], df5, df1, a["now"]), True
    return out


def job_charts(df5, df1, a: dict) -> dict:
    """engine/trade_chart.PcCharts.draw: what LiveBot._chart_tick's picture thread did, on the same bars."""
    from engine import trade_chart as _tc
    pc = _tc.PcCharts(root=a["root"])
    pc.draw(a["lit_trades"], a["second"], df5, df1, a["now"], keep=a.get("keep"))
    return {"last": pc.last, "error": pc.error, "drawn": pc.sigs()}


def job_echo(df5, df1, a: dict) -> dict:
    """Tests: the frames as the child holds them, the engine modules it loaded, its priority; a["sleep"] / a["exit"]."""
    if a.get("sleep"):
        time.sleep(float(a["sleep"]))
    if a.get("exit"):
        os._exit(int(a["exit"]))
    if a.get("raise"):
        raise ValueError(str(a["raise"]))
    nice = None
    try:
        import psutil
        nice = psutil.Process().nice()
    except Exception:
        pass
    return {"df5": df5 if a.get("frames", True) else None, "df1": df1 if a.get("frames", True) else None, "a": a,
            "modules": sorted(m for m in sys.modules if m.startswith("engine.")), "pid": os.getpid(), "nice": nice}


JOBS = {"second": job_second, "charts": job_charts, "echo": job_echo}


def _below_normal():
    try:
        if os.name == "nt":
            import ctypes
            k = ctypes.windll.kernel32
            k.SetPriorityClass(k.GetCurrentProcess(), BELOW_NORMAL)
        else:
            os.nice(10)
    except Exception:
        pass


def _watch_parent():
    """Exit when the PC bot's process is gone (killed: its pipe may stay open while a job runs)."""
    try:
        pid = int(os.environ.get("LE_BG_PARENT") or 0)
    except ValueError:
        pid = 0
    if not pid:
        return
    try:
        import psutil
        par = psutil.Process(pid)
        born = par.create_time()
    except Exception:
        return

    def loop():
        while True:
            time.sleep(5.0)
            try:
                ok = par.is_running() and par.create_time() == born
            except Exception:
                ok = False
            if not ok:
                os._exit(0)
    threading.Thread(target=loop, name="bg-worker-parent", daemon=True).start()


def child_main() -> int:
    """python -m engine.bg_worker: read jobs on stdin, answer on stdout; ends when stdin closes (the PC bot stopped)."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    _below_normal()
    _watch_parent()
    inp = sys.stdin.buffer
    sys.stdout.flush()
    out = os.fdopen(os.dup(1), "wb")            # the answers go on a private copy of stdout; fd 1 and sys.stdout now point
    try:                                        # at stderr: a stray print in a job (Python or C) never corrupts them
        os.dup2(2, 1)
    except OSError:                             # no stderr (pythonw): prints go nowhere
        nul = os.open(os.devnull, os.O_WRONLY)
        os.dup2(nul, 1)
    sys.stdout = sys.stderr
    frames: dict = {}
    while True:
        try:
            msg = _read(inp)
        except Exception as e:
            print(f"[bg worker] bad message: {e.__class__.__name__}: {e}", file=sys.stderr, flush=True)
            return 2
        if msg is None or msg.get("op") == "stop":
            return 0
        t0, c0 = time.perf_counter(), time.process_time()
        res = {"id": msg.get("id"), "kind": msg.get("kind"), "ok": False}
        try:
            for name, pk in (msg.get("frames") or {}).items():
                try:
                    frames[name] = frame_apply(pk, frames.get(name))
                except Exception:
                    frames.clear()                  # the parent sends the full frames again
                    res["resync"] = True
                    raise
            fn = JOBS[msg["kind"]]
            args = pickle.loads(msg["args"]) if isinstance(msg.get("args"), bytes) else (msg.get("args") or {})
            res["result"] = fn(frames.get("df5"), frames.get("df1"), args)
            res["ok"] = True
        except Exception as e:
            import traceback
            res["error"] = f"{e.__class__.__name__}: {e}"
            res["trace"] = traceback.format_exc()[-2000:]
        res["ms"] = int((time.perf_counter() - t0) * 1000)
        res["cpu_ms"] = int((time.process_time() - c0) * 1000)
        try:
            _write(out, res)
        except Exception:
            return 3


# ------------------------------------------------------------------------------------------------ parent side
class Worker:
    """The PC bot's handle on the child. submit() -> "queued" | "busy" (that kind still runs) | "wait" (the child is being
    restarted: skip this tick) | "off" (run it the old way, in a thread)."""

    def __init__(self, log=None, cmd=None):
        self.log = log or (lambda text: print(text, flush=True))
        self.cmd = cmd or [sys.executable, "-X", "utf8", "-m", "engine.bg_worker"]
        self.mx = threading.RLock()
        self.cv = threading.Condition(self.mx)
        self.proc = None
        self.out_q: deque = deque()
        self.inflight: dict = {}                # (kind, owner) -> {"id", "t", "done"}
        self.ids = 0
        self.sent: dict = {}                    # frame name -> what the child holds (frame_packet prev)
        self.fails = 0
        self.started_t = 0.0
        self.off_reason = None if enabled() else "LE_BG_WORKER=0"
        self.stats = {"jobs": 0, "errors": 0, "restarts": 0, "last": {}}
        self._sender = None
        self._gen = 0

    # ---- public
    def info(self) -> dict:
        with self.mx:
            p = self.proc
            return {"on": self.off_reason is None, "off": self.off_reason, "pid": p.pid if p is not None and p.poll() is None else None,
                    "busy": sorted(k for k, _ in self.inflight), "jobs": self.stats["jobs"], "errors": self.stats["errors"],
                    "restarts": self.stats["restarts"], "last": dict(self.stats["last"])}

    def busy(self, kind: str, owner=None) -> bool:
        with self.mx:
            j = self.inflight.get((kind, owner))
            return j is not None and time.time() - j["t"] < JOB_TIMEOUT_S

    def submit(self, kind: str, args: dict, frames: dict, done, owner=None) -> str:
        """Queue one job. frames = {"df5": DataFrame, "df1": DataFrame | None} (references; sent as deltas by the sender
        thread). done(result | None, error | None) runs in the receiver thread when the child answers (or dies)."""
        with self.mx:
            if self.off_reason is not None:
                return "off"
            self._reap_hung()
            if (kind, owner) in self.inflight:
                return "busy"
            up = self._ensure()
            if up != "ok":
                return up                       # "wait": a restart is due shortly (skip this tick); "off": run it in a thread
            # the arguments are copied now (pickled): the bot's dicts may change after this poll; the bar frames are new
            # objects every poll and are only read
            blob = pickle.dumps(args, protocol=pickle.HIGHEST_PROTOCOL)
            self.ids += 1
            jid = self.ids
            self.inflight[(kind, owner)] = {"id": jid, "t": time.time(), "done": done}
            self.out_q.append({"op": "job", "id": jid, "kind": kind, "args": blob, "frames": frames, "gen": self._gen})
            self.cv.notify_all()
            return "queued"

    def stop(self):
        with self.mx:
            p, self.proc = self.proc, None
            self._gen += 1
            self.out_q.clear()
            jobs, self.inflight = list(self.inflight.values()), {}
            self.cv.notify_all()
        for j in jobs:
            try:
                j["done"](None, "background worker stopped")
            except Exception:
                pass
        if p is not None:
            try:
                p.stdin.close()
            except Exception:
                pass
            try:
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    # ---- child lifecycle
    def _ensure(self) -> str:
        """"ok" (the child runs), "wait" (it stopped: restarted RESTART_GAP_S after the last start) or "off"."""
        p = self.proc
        if p is not None and p.poll() is None:
            return "ok"
        if p is not None:
            self._dead(f"exited with code {p.poll()}")
        if self.off_reason is not None:
            return "off"
        if self.started_t and time.time() - self.started_t < RESTART_GAP_S:
            return "wait"
        self.started_t = time.time()
        try:
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "LE_BG_CHILD": "1", "LE_BG_PARENT": str(os.getpid())}
            flags = (BELOW_NORMAL | NO_WINDOW) if os.name == "nt" else 0
            self.proc = subprocess.Popen(self.cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
                                         env=env, creationflags=flags)
        except Exception as e:
            self.proc = None
            self._fail(f"could not start: {e.__class__.__name__}: {e}")
            return "off" if self.off_reason is not None else "wait"
        self._gen += 1
        self.sent = {}
        if self.stats["jobs"] or self.stats["restarts"] or self.fails:
            self.stats["restarts"] += 1
        g = self._gen
        threading.Thread(target=self._recv_loop, args=(self.proc, g), name="bg-worker-recv", daemon=True).start()
        if self._sender is None or not self._sender.is_alive():
            self._sender = threading.Thread(target=self._send_loop, name="bg-worker-send", daemon=True)
            self._sender.start()
        return "ok"

    def _fail(self, why: str):
        self.fails += 1
        self.log(f"[bg worker] {why}")
        if self.fails >= MAX_FAILS:
            self.off_reason = f"turned off after {self.fails} failures ({why}); the paper work runs in threads again"
            self.log(f"[bg worker] {self.off_reason}")

    def _dead(self, why: str):
        """The child is gone: every job in flight gets its callback (None, error); the next submit starts a new child."""
        p, self.proc = self.proc, None
        self._gen += 1
        self.sent = {}
        self.out_q.clear()
        jobs, self.inflight = list(self.inflight.values()), {}
        if p is not None:
            try:
                p.kill()
            except Exception:
                pass
        self._fail(f"child stopped: {why}")
        for j in jobs:
            try:
                j["done"](None, f"background worker stopped ({why})")
            except Exception:
                pass

    def _reap_hung(self):
        now = time.time()
        if any(now - j["t"] > JOB_TIMEOUT_S for j in self.inflight.values()):
            self._dead(f"a job ran longer than {int(JOB_TIMEOUT_S)} s")

    # ---- threads
    def _send_loop(self):
        while True:
            with self.mx:
                while not self.out_q:
                    self.cv.wait(5.0)
                msg = self.out_q.popleft()
                p = self.proc
                if p is None or msg.get("gen") != self._gen:
                    continue
                sent = dict(self.sent)
            try:
                frames = {}
                for name, df in (msg.pop("frames") or {}).items():
                    frames[name], sent[name] = frame_packet(df, sent.get(name))
                msg["frames"] = frames
                msg.pop("gen", None)
            except Exception as e:                  # this job's bars could not be packed: only this job fails
                self._job_failed(msg.get("id"), f"bars not sent: {e.__class__.__name__}: {e}")
                continue
            try:
                _write(p.stdin, msg)
                with self.mx:
                    if p is self.proc:
                        self.sent = sent
            except Exception as e:
                with self.mx:
                    if p is self.proc:
                        self._dead(f"send failed: {e.__class__.__name__}: {e}")

    def _job_failed(self, jid, err):
        done = None
        with self.mx:
            key = next((k for k, j in self.inflight.items() if j["id"] == jid), None)
            if key is not None:
                done = self.inflight.pop(key)["done"]
            self.stats["errors"] += 1
        if done is not None:
            try:
                done(None, err)
            except Exception:
                pass

    def _recv_loop(self, p, gen):
        while True:
            try:
                res = _read(p.stdout)
            except Exception as e:
                res, err = None, f"{e.__class__.__name__}: {e}"
            else:
                err = "closed its output"
            if res is None:
                with self.mx:
                    if p is self.proc and gen == self._gen:
                        self._dead(err)
                return
            done = None
            with self.mx:
                key = next((k for k, j in self.inflight.items() if j["id"] == res.get("id")), None)
                if key is not None:
                    done = self.inflight.pop(key)["done"]
                self.stats["last"][str(res.get("kind"))] = {"t": int(time.time()), "ms": res.get("ms"), "cpu_ms": res.get("cpu_ms"),
                                                            "ok": bool(res.get("ok")), "error": res.get("error")}
                if res.get("ok"):
                    self.stats["jobs"] += 1
                    self.fails = 0
                else:
                    self.stats["errors"] += 1
                if res.get("resync"):
                    self.sent = {}
            if done is not None:
                try:
                    done(res.get("result") if res.get("ok") else None, None if res.get("ok") else res.get("error") or "failed")
                except Exception as e:
                    self.log(f"[bg worker] result handler failed: {e.__class__.__name__}: {e}")


_SHARED = {"w": None}
_SHARED_MX = threading.Lock()


def shared(log=None) -> Worker:
    """The process's one worker (every LiveBot of the process uses it; each job names its own files)."""
    with _SHARED_MX:
        if _SHARED["w"] is None:
            _SHARED["w"] = Worker(log=log)
            atexit.register(_SHARED["w"].stop)
        return _SHARED["w"]


if __name__ == "__main__":
    sys.exit(child_main())
