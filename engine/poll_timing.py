"""Per-stage timing of the PC bot's poll (owner's Surface 2026-10-25: poll_ms ~32,300 ms on every poll, against ~950 ms
on the same bars in the cloud). Read-only diagnostics: no decision, order or file changes.

How: install() wraps the stages of LiveBot.poll_once (its methods, plus the few module functions it calls: the LIT run,
the bar file parse, the bar object) with a timer that only counts inside a poll on the poll's own thread, so
engine/live.py stays byte-identical (the PC carries a hand-patched copy of it until its next update; a change there would
block that update). server.py installs it for the real bot (LE_POLL_TIMING=0 turns it off); tests and harnesses run
without it unless they install it.

Each poll leaves bot.health["poll_stages"]:
  {"t", "total_ms" (the whole poll, incl. the state save and the post-save part), "cpu_ms" (CPU this thread used),
   "wait_ms" (total - cpu: waiting on disk, network, a lock or other threads), "stages": [{"name", "ms", "cpu_ms", "n"}]
   in poll order ("a > b" = b inside a), "other_ms" (poll code between the stages), "slowest", "threads": the other
   threads that used the most CPU during the poll [{"name", "cpu_ms"}] (a busy background thread slows every stage of the
   poll through Python's GIL), "recent_ms": the last 10 poll totals}
The heartbeat carries it as health.poll.stages (engine/accounts.poll_stages_block); the dashboard shows it (Home "Bot
loop" light, the Start page's Bot loop card). table(ps) prints it. Tests: tests/test_poll_timing.py.
"""
from __future__ import annotations

import functools
import os
import threading
import time

_TL = threading.local()
_INSTALLED = {"done": False}
METHODS = (            # LiveBot method -> label (poll order)
    ("_adapter_tick", "adapter tick (NinjaTrader files)"), ("_refresh_guard", "news + VIX refresh"),
    ("_merged", "bars: merge"), ("_read_hist", "history file"), ("_fetch_recent", "NinjaTrader feed"),
    ("_archive_add", "bar archive"), ("_detect_revisions", "revision check"), ("_lit_1m", "1m bars"),
    ("lit_week_hist", "week history"), ("_learn_es", "ES bars (learning)"), ("eval_clock", "eval clock"),
    ("_eval_life_tick", "eval life"), ("_broker_tick", "broker balance"), ("_narrate_filter", "filter note"),
    ("_emit_events", "events"), ("_eod_summary", "day summary"), ("_route_signals", "route"), ("_guards_tick", "guards"),
    ("_alerts_tick", "alerts + AI watch"), ("_save_state", "save state"), ("_brain_tick", "Bot Brain"),
    ("_second_route_tick", "second route"), ("_account_b_tick", "ATLAS (account B)"), ("_second_tick", "second strategies"),
    ("_chart_tick", "trade charts"),
)
FUNCS = (              # (module, attribute, label): module functions poll_once looks up at call time
    ("engine.lit_live", "run", "LIT model (lit_live.run)"), ("engine.live", "from_frame", "bar object"),
    ("engine.live", "clean_bars", "clean bars"), ("engine.pcbars", "merge_basis", "history + feed merge"),
    ("engine.lab_adapter", "live_model", "live_model.json"),
)
CLASS_FUNCS = (("engine.ninjatrader", "NinjaTraderBars", "load", "bar file parse"),
               ("engine.ninjatrader", "NinjaTraderBars", "recent_bars", "feed checks"))


def _now():
    return time.perf_counter(), time.thread_time()


def _timed(fn, label):
    """fn timed under `label` while this thread is inside a poll; a plain call otherwise."""
    @functools.wraps(fn)
    def w(*a, **k):
        st = getattr(_TL, "stack", None)
        if st is None:
            return fn(*a, **k)
        t0, c0 = _now()
        st.append([label, 0.0, 0.0])                   # label, child wall, child cpu
        try:
            return fn(*a, **k)
        finally:
            t1, c1 = _now()
            me = st.pop()
            wall, cpu = t1 - t0, c1 - c0
            path = " > ".join([s[0] for s in st if s[0] != "poll"] + [label])
            r = _TL.rec.setdefault(path, [0.0, 0.0, 0])
            r[0] += wall
            r[1] += cpu
            r[2] += 1
            if st:
                st[-1][1] += wall
                st[-1][2] += cpu
            del me
    w._le_timed = True
    return w


def _thread_cpu() -> dict:
    """{native thread id: cpu seconds} of this process (psutil; {} when it is not there)."""
    try:
        import psutil
        return {t.id: t.user_time + t.system_time for t in psutil.Process().threads()}
    except Exception:
        return {}


def _names() -> dict:
    return {t.native_id: t.name for t in threading.enumerate() if getattr(t, "native_id", None)}


def summarize(rec: dict, total_s: float, cpu_s: float, threads: list | None = None, recent=None, now=None) -> dict:
    """The health block from one poll's records (pure)."""
    stages = [{"name": k, "ms": int(round(v[0] * 1000)), "cpu_ms": int(round(v[1] * 1000)), "n": int(v[2])} for k, v in rec.items()]
    top = sum(s["ms"] for s in stages if " > " not in s["name"])
    total = int(round(total_s * 1000))
    slow = max((s for s in stages if " > " not in s["name"]), key=lambda s: s["ms"], default=None)
    return {"t": int(now if now is not None else time.time()), "total_ms": total, "cpu_ms": int(round(cpu_s * 1000)),
            "wait_ms": max(0, total - int(round(cpu_s * 1000))), "stages": stages, "other_ms": max(0, total - top),
            "slowest": f"{slow['name']} {slow['ms'] / 1000:.1f} s" if slow else None, "threads": threads or [],
            "recent_ms": list(recent or [])[-10:]}


def _poll_wrapper(fn):
    @functools.wraps(fn)
    def poll_once(self, *a, **k):
        if getattr(_TL, "stack", None) is not None:      # nested (never in the bot): plain call
            return fn(self, *a, **k)
        _TL.stack, _TL.rec = [["poll", 0.0, 0.0]], {}
        tc0 = _thread_cpu()
        t0, c0 = _now()
        try:
            return fn(self, *a, **k)
        finally:
            t1, c1 = _now()
            rec = _TL.rec
            _TL.stack = None
            _TL.rec = {}
            try:
                tc1, names, me = _thread_cpu(), _names(), threading.get_native_id()
                other = sorted(({"name": names.get(i, f"thread {i}"), "cpu_ms": int(round((c - tc0.get(i, 0.0)) * 1000))}
                                for i, c in tc1.items() if i != me and c - tc0.get(i, 0.0) >= 0.05),
                               key=lambda r: -r["cpu_ms"])[:4]
                h = self.health
                recent = (list((h.get("poll_stages") or {}).get("recent_ms") or []) + [int(round((t1 - t0) * 1000))])[-10:]
                h["poll_stages"] = summarize(rec, t1 - t0, c1 - c0, other, recent)
            except Exception:
                pass
    poll_once._le_timed = True
    return poll_once


def install(bot=None) -> bool:
    """Wrap the stages (once per process); bot = an existing LiveBot whose read_hist / fetch_recent were bound at its
    creation (engine.live.BOT) gets the timed ones too. True when installed."""
    import importlib
    from . import live
    if not _INSTALLED["done"]:
        L = live.LiveBot
        if not getattr(L.poll_once, "_le_timed", False):
            L.poll_once = _poll_wrapper(L.poll_once)
        for name, label in METHODS:
            f = getattr(L, name, None)
            if callable(f) and not getattr(f, "_le_timed", False):
                setattr(L, name, _timed(f, label))
        for mod, attr, label in FUNCS:
            m = importlib.import_module(mod)
            f = getattr(m, attr, None)
            if callable(f) and not getattr(f, "_le_timed", False):
                setattr(m, attr, _timed(f, label))
        for mod, cls, attr, label in CLASS_FUNCS:
            C = getattr(importlib.import_module(mod), cls, None)
            f = getattr(C, attr, None) if C is not None else None
            if callable(f) and not getattr(f, "_le_timed", False):
                setattr(C, attr, _timed(f, label))
        _INSTALLED["done"] = True
    for b in [bot] if bot is not None else []:
        for attr, meth in (("read_hist", "_read_hist"), ("fetch_recent", "_fetch_recent")):
            cur = getattr(b, attr, None)
            if getattr(cur, "__func__", None) is not None and getattr(cur, "__name__", "") == meth \
                    and not getattr(cur.__func__, "_le_timed", False):
                setattr(b, attr, getattr(b, meth))        # rebinding picks up the timed class method
    return True


def enabled(env=None) -> bool:
    return (os.environ if env is None else env).get("LE_POLL_TIMING", "1") != "0"


def table(ps: dict) -> str:
    if not ps:
        return "no timed poll yet"
    out = [f"poll {ps['total_ms']} ms (CPU {ps['cpu_ms']} ms, waiting {ps['wait_ms']} ms), between stages {ps['other_ms']} ms"]
    for s in ps["stages"]:
        out.append(f"  {s['ms']:>7} ms  cpu {s['cpu_ms']:>6} ms  x{s['n']:<3} {s['name']}")
    for t in ps.get("threads") or []:
        out.append(f"  other thread {t['name']}: {t['cpu_ms']} ms CPU during the poll")
    return "\n".join(out)
