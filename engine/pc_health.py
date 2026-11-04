"""PC health watchdog + the weekly schedules (2026-10-30, owner: "automatic in a few weeks"; read-only, advisory: the bot's
trading never depends on anything here).

  python -X utf8 -m engine.pc_health            one screen of the health lines now (green / amber / red)
  python -X utf8 -m engine.pc_health --json     the heartbeat block
  python -X utf8 -m engine.pc_health --readiness [--send]   build the Sunday readiness push now (engine/readiness.py)

Lines (each green / amber / red with a plain text; a line this PC cannot measure is skipped, never an error):
  cpu       CPU % (median of the last 5 samples: one busy minute is not an alarm)            psutil
  ram       RAM in use %                                                                     psutil
  disk      free disk where the bot lives (as engine/ops_checks: red < 2 GB, amber < 10 GB)  stdlib
  nt        NinjaTrader.exe running + its memory (red when it is not running while the market is open and the bot routes
            to NinjaTrader)                                                                  psutil, Windows only
  bot_mem   the bot server's own memory and its growth since it started (a leak shows here days before it hurts)
  onedrive  OneDrive conflict copies in the bot folder ("live_state (1).json", "lit_journal-SURFACE.jsonl"): red in data/
            (a state file may have been replaced by an older copy), amber elsewhere; amber when the folder is in OneDrive
  clock     clock drift vs internet time: the bot's own probe (engine/guards._CLOCK, every 15 min; never probed here)
  poll      the bot's poll time: 15-minute median and its trend vs the hour before (bot.health["poll_ms"])
  storage   (2026-11-04, display only) free GB on the bot's drive + the bot folder's and NinjaTrader 8 folder's size, a
            capped folder walk at most every 6 h and never in the first 5 min; amber < 15 GB, red < 2 GB, the fix is
            "Run CLEAN_STORAGE.bat" (scripts/clean_storage.ps1). The block also carries it as `storage`
            {free_gb, bot_gb, nt_gb}. On the phone (live_publish.pc_health_summary) it replaces the plain Disk line.
A red line (two samples in a row) pushes once per issue per ET day (kind pc_health: on / silent / off in the app).

Watcher (a daemon thread in server.py, LE_PC_WATCH=0 = off): every SAMPLE_S seconds it samples (a few ms; the OneDrive scan
every 10 min, capped), writes logs/pc_health.json (gitignored) for the heartbeat ("pc_health") and runs the schedules, all
in New York wall-clock time (DST-safe): the PC self-test every Sunday 15:30 ET (engine/pc_selftest, a below-normal-priority
child process; one push when something fails, else "all green"), the readiness push every Sunday 17:30 ET
(engine/readiness.py), and one baseline self-test after a server start on a version without a result (outside 01:50-16:00
ET on a weekday). Nothing here runs inside the trading poll.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import shutil
import threading
import time
from collections import deque
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")
BLOCK_PATH = os.path.join(LOG_DIR, "pc_health.json")      # gitignored (logs/): the last block, for the heartbeat / CLI
STATE_PATH = os.path.join(LOG_DIR, "pc_watch.json")       # gitignored: pushes sent (key -> t), the schedules' last dates
SAMPLE_S = 60.0
ONEDRIVE_EVERY_S = 600.0
NT_SCAN_S = 300.0                                         # the full process list (the NinjaTrader line) at most this often
GREEN, AMBER, RED, SKIP = "green", "amber", "red", "skip"
ORDER = {GREEN: 0, AMBER: 1, RED: 2}
T = {"cpu_amber": 85.0, "cpu_red": 95.0, "ram_amber": 88.0, "ram_red": 95.0, "disk_amber_gb": 10.0, "disk_red_gb": 2.0,
     "nt_amber_mb": 2500.0, "nt_red_mb": 4000.0, "bot_amber_mb": 2000.0, "bot_red_mb": 3500.0, "grow_amber_mb": 600.0,
     "grow_red_mb": 1500.0, "grow_rate_amber_mbh": 200.0, "clock_amber_s": 2.0, "poll_amber_ms": 5000.0, "poll_red_ms": 20000.0,
     "poll_rise_x": 2.0, "poll_rise_min_ms": 2000.0, "storage_amber_gb": 15.0}
STORAGE_EVERY_S = 6 * 3600.0                              # the folder-size walk: at most this often
STORAGE_WARM_S = 300.0                                    # ... and not in the first minutes after a server start
STORAGE_BUDGET_S = 3.0                                    # time budget of one folder walk (a capped walk reports a lower bound)
SUNDAY_TEST = (15 * 60 + 30, 17 * 60 + 45)                # Sunday 15:30 ET (until 17:45 if the PC was asleep at 15:30)
SUNDAY_READY = (17 * 60 + 30, 18 * 60 + 30)               # Sunday 17:30 ET readiness push (until 18:30)
BASELINE_AFTER_S = 300.0                                  # a baseline self-test no sooner than 5 min after the server start
SCAN_DIRS = (("", 0), ("data", 2), ("engine", 1), ("tools", 1), ("scripts", 1), ("tests", 1), ("web_next", 2), ("ninjatrader", 1))
SCAN_SKIP = {"nt_bars", "clean", "tv_exports", "ltf", "__pycache__", "node_modules", "_cache", ".git", "brain"}
SCAN_MAX = 6000
LABELS = {"cpu": "CPU", "ram": "Memory (RAM)", "disk": "Disk space", "nt": "NinjaTrader", "bot_mem": "Bot memory",
          "onedrive": "OneDrive sync", "clock": "PC clock", "poll": "Bot poll time", "storage": "Storage"}


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(t), ET)


def _psutil():
    try:
        import psutil
        return psutil
    except Exception:
        return None


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def _line(key, level, text, value=None) -> dict:
    return {"key": key, "label": LABELS.get(key, key), "level": level, "text": text, **({"value": value} if value is not None else {})}


def _read_json(path) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write_json(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"), default=str)
        from .fsutil import replace as _fs_replace       # retried: Windows / OneDrive lock the target a moment
        _fs_replace(tmp, path)
    except Exception:
        pass


# ---------------------------------------------------------------------------------------------- OneDrive conflict copies
def conflict_rx(host: str | None = None):
    """Windows' "name (1).ext" copies and OneDrive's "name-<COMPUTER>.ext" / "name-<COMPUTER>-2.ext" conflict copies."""
    h = re.escape((host or platform.node() or "").split(".")[0]) if (host or platform.node()) else None
    pats = [r" \(\d+\)\.[A-Za-z0-9]+$", r"-(?:DESKTOP|LAPTOP|SURFACE)-?[A-Za-z0-9]*(?:-\d+)?\.[A-Za-z0-9]+$"]
    if h:
        pats.append(rf"-{h}(?:-\d+)?\.[A-Za-z0-9]+$")
    return re.compile("|".join(pats), re.I)


def onedrive_conflicts(root: str = ROOT, host: str | None = None, dirs=SCAN_DIRS, max_entries: int = SCAN_MAX) -> list:
    """Relative paths of conflict copies in the bot folder (capped scan, never raises)."""
    rx = conflict_rx(host)
    out, seen = [], [0]

    def walk(path, rel, depth):
        try:
            with os.scandir(path) as it:
                for e in it:
                    seen[0] += 1
                    if seen[0] > max_entries:
                        return
                    if e.is_dir(follow_symlinks=False):
                        if depth > 0 and e.name not in SCAN_SKIP and not e.name.startswith("."):
                            walk(e.path, f"{rel}{e.name}/", depth - 1)
                    elif rx.search(e.name):
                        out.append(f"{rel}{e.name}")
        except Exception:
            return
    for d, depth in dirs:
        p = os.path.join(root, d) if d else root
        if os.path.isdir(p):
            walk(p, f"{d}/" if d else "", depth)
    return sorted(set(out))


def in_onedrive(root: str = ROOT) -> bool:
    return "onedrive" in os.path.abspath(root).lower()


# ---------------------------------------------------------------------------------------------- storage (display only)
def dir_gb(path: str, budget_s: float = STORAGE_BUDGET_S, max_entries: int = 400000):
    """(GB, capped) of a folder tree: an iterative scandir walk that does not follow links and stops at the time or entry
    budget (capped = the size is a lower bound). (None, False) when the folder is missing. Never raises."""
    try:
        if not path or not os.path.isdir(path):
            return None, False
        t_end, total, seen, stack = time.time() + budget_s, 0, 0, [path]
        while stack:
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for e in it:
                        seen += 1
                        if seen > max_entries or (seen % 500 == 0 and time.time() > t_end):
                            return total / 1e9, True
                        try:
                            if e.is_symlink():
                                continue
                            if e.is_dir(follow_symlinks=False):
                                stack.append(e.path)
                            else:
                                total += e.stat(follow_symlinks=False).st_size
                        except OSError:
                            continue
            except OSError:
                continue
        return total / 1e9, False
    except Exception:
        return None, False


def nt_folder() -> str | None:
    """NinjaTrader 8's user folder (NINJATRADER_FOLDER, Documents, OneDrive\\Documents); None when there is none."""
    home = os.path.expanduser("~")
    od = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    for c in (os.environ.get("NINJATRADER_FOLDER"), os.path.join(home, "Documents", "NinjaTrader 8"),
              os.path.join(od, "Documents", "NinjaTrader 8") if od else None):
        if c and os.path.isdir(c):
            return c
    return None


# ---------------------------------------------------------------------------------------------- the lines (pure)
def lines(f: dict) -> list:
    """facts -> the health lines. f keys (any may be missing = that line is skipped): cpu_pct, ram_pct, ram_used_gb,
    ram_total_gb, disk_free_gb, nt {"running", "mb", "market_open", "routes"}, bot_mb, bot_base_mb, bot_rate_mbh, onedrive
    {"files", "in_onedrive"}, clock {"drift", "max", "age_s"}, poll {"med15", "med_prev", "n15"}."""
    out = []
    c = f.get("cpu_pct")
    if c is not None:
        lv = RED if c >= T["cpu_red"] else AMBER if c >= T["cpu_amber"] else GREEN
        out.append(_line("cpu", lv, f"CPU {c:.0f}%" + (" (the bot's decisions may run late)" if lv != GREEN else ""), round(c, 1)))
    r = f.get("ram_pct")
    if r is not None:
        lv = RED if r >= T["ram_red"] else AMBER if r >= T["ram_amber"] else GREEN
        gb = (f" ({f['ram_used_gb']:.1f} of {f['ram_total_gb']:.1f} GB)" if f.get("ram_used_gb") is not None and f.get("ram_total_gb") else "")
        out.append(_line("ram", lv, f"RAM {r:.0f}% in use{gb}" + (": close other apps (browser tabs)" if lv != GREEN else ""), round(r, 1)))
    d = f.get("disk_free_gb")
    if d is not None:
        lv = RED if d < T["disk_red_gb"] else AMBER if d < T["disk_amber_gb"] else GREEN
        out.append(_line("disk", lv, f"{d:.1f} GB free" + (": Settings > System > Storage > Cleanup" if lv != GREEN else ""), round(d, 1)))
    st = f.get("storage")
    if isinstance(st, dict) and (st.get("free_gb") is not None or d is not None):
        fr = float(st["free_gb"]) if st.get("free_gb") is not None else float(d)
        lv = RED if fr < T["disk_red_gb"] else AMBER if fr < T["storage_amber_gb"] else GREEN
        parts = []
        for k, label in (("bot_gb", "bot"), ("nt_gb", "NinjaTrader")):
            if st.get(k) is not None:
                parts.append(f"{label} {float(st[k]):.1f}{'+' if st.get(k + '_capped') else ''} GB")
        out.append(_line("storage", lv, f"{fr:.1f} GB free" + (f" (folders: {', '.join(parts)})" if parts else "")
                         + (": Run CLEAN_STORAGE.bat" if lv != GREEN else ""), round(fr, 1)))
    nt = f.get("nt")
    if isinstance(nt, dict):
        if not nt.get("running"):
            lv = RED if nt.get("market_open") and nt.get("routes") else AMBER
            out.append(_line("nt", lv, "NinjaTrader is not running" + (": no orders can go out, open it now" if lv == RED else "")))
        else:
            mb = nt.get("mb")
            lv = GREEN if mb is None else RED if mb >= T["nt_red_mb"] else AMBER if mb >= T["nt_amber_mb"] else GREEN
            out.append(_line("nt", lv, "NinjaTrader running" + (f", {mb:,.0f} MB" if mb is not None else "")
                             + (": restart it after 16:00 ET (it grows over days)" if lv != GREEN else ""), mb))
    b = f.get("bot_mb")
    if b is not None:
        base = f.get("bot_base_mb")
        grow = None if base is None else b - base
        rate = f.get("bot_rate_mbh")
        lv = GREEN
        if b >= T["bot_red_mb"] or (grow is not None and grow >= T["grow_red_mb"]):
            lv = RED
        elif b >= T["bot_amber_mb"] or (grow is not None and grow >= T["grow_amber_mb"]) or (rate is not None and rate >= T["grow_rate_amber_mbh"]):
            lv = AMBER
        txt = f"Bot server {b:,.0f} MB" + (f" ({'+' if grow >= 0 else '-'}{abs(grow):,.0f} MB since it started)" if grow is not None else "")
        if rate is not None and rate >= T["grow_rate_amber_mbh"]:
            txt += f", growing ~{rate:,.0f} MB an hour"
        if lv != GREEN:
            txt += ": restart the bot server after 16:00 ET (flat)"
        out.append(_line("bot_mem", lv, txt, round(b)))
    od = f.get("onedrive")
    if isinstance(od, dict):
        files = list(od.get("files") or [])
        data = [p for p in files if p.startswith("data/")]
        if data:
            out.append(_line("onedrive", RED, f"{len(files)} OneDrive conflict cop{'y' if len(files) == 1 else 'ies'}: "
                             + ", ".join(files[:3]) + ": a bot state file may have been replaced by an older copy; tell Claude"))
        elif files:
            out.append(_line("onedrive", AMBER, f"{len(files)} OneDrive conflict cop{'y' if len(files) == 1 else 'ies'}: " + ", ".join(files[:3])))
        elif od.get("in_onedrive"):
            out.append(_line("onedrive", AMBER, "the bot folder is inside OneDrive (sync can lock state files); no conflict copies"))
        else:
            out.append(_line("onedrive", GREEN, "no conflict copies"))
    ck = f.get("clock")
    if isinstance(ck, dict) and ck.get("drift") is not None:
        dr, mx = float(ck["drift"]), float(ck.get("max") or 5.0)
        lv = RED if abs(dr) > mx else AMBER if abs(dr) > T["clock_amber_s"] else GREEN
        out.append(_line("clock", lv, f"{abs(dr):.1f} s {'behind' if dr > 0 else 'ahead of'} internet time"
                         + (": entries are blocked, Start page > Sync the clock" if lv == RED else ""), round(dr, 2)))
    p = f.get("poll")
    if isinstance(p, dict) and p.get("med15") is not None:
        m, prev = float(p["med15"]), p.get("med_prev")
        rising = prev is not None and m >= T["poll_rise_x"] * float(prev) and m >= T["poll_rise_min_ms"]
        lv = RED if m >= T["poll_red_ms"] else AMBER if m >= T["poll_amber_ms"] or rising else GREEN
        txt = f"poll {m / 1000:.1f} s (15-min median" + (f"; {float(prev) / 1000:.1f} s the hour before" if prev is not None else "") + ")"
        if lv != GREEN:
            txt += ": decisions run late (Start page > Bot loop names the slow stage)"
        out.append(_line("poll", lv, txt, round(m)))
    return out


def level_of(ls: list) -> str:
    return max((ln["level"] for ln in ls if ln["level"] in ORDER), key=ORDER.get, default=GREEN)


# ---------------------------------------------------------------------------------------------- sampling
class Sampler:
    """Keeps the few rolling numbers the lines need (CPU samples, poll times, the bot's memory). ps: psutil or a fake."""

    def __init__(self, bot=None, ps=..., root: str = ROOT, is_windows: bool | None = None, host: str | None = None, t0=None):
        self.bot, self.root = bot, root
        self.ps = _psutil() if ps is ... else ps
        self.is_windows = (os.name == "nt") if is_windows is None else is_windows
        self.host = host
        self.t0 = time.time() if t0 is None else t0
        self.cpu = deque(maxlen=5)
        self.polls = deque(maxlen=400)           # (t, poll_ms) of new polls only
        self.rss = deque(maxlen=400)             # (t, MB)
        self.base_mb = None
        self._last_poll = None
        self._od = {"t": 0.0, "files": []}
        self._nt_procs: list = []
        self._nt_scan_t = -1e18
        self._st = {"t": -1e18, "bot_gb": None, "nt_gb": None, "bot_gb_capped": False, "nt_gb_capped": False}
        self._proc = None
        try:
            if self.ps is not None:
                self._proc = self.ps.Process()
                self.ps.cpu_percent(interval=None)   # prime: the first call always answers 0.0
        except Exception:
            self._proc = None

    def _clock(self) -> dict | None:
        try:
            from . import guards
            c = dict(getattr(guards, "_CLOCK", {}) or {})
            if c.get("drift") is None:
                return None
            return {"drift": c.get("drift"), "max": float(c.get("max") or 5.0), "age_s": time.time() - float(c.get("ok_t") or 0)}
        except Exception:
            return None

    def _nt(self, now) -> dict | None:
        """NinjaTrader.exe running + its memory. The full process list is read at most every NT_SCAN_S (60 s while it is
        not found); in between only the known NinjaTrader processes are asked (a dead one = scan again). Windows only."""
        if not self.is_windows or self.ps is None:
            return None
        procs, mb = self._nt_procs, None
        scan = now - self._nt_scan_t >= (NT_SCAN_S if procs else 60.0)
        if procs and not scan:
            try:
                mb = sum(float(p.memory_info().rss) for p in procs) / 2 ** 20
            except Exception:                    # NinjaTrader closed (or restarted): look again now
                scan = True
        if scan:
            self._nt_scan_t = now
            procs, mb = [], None
            try:
                for p in self.ps.process_iter(["name", "memory_info"]):
                    info = getattr(p, "info", None) or {}
                    if str(info.get("name") or "").lower() == "ninjatrader.exe":
                        procs.append(p)
                        mi = info.get("memory_info")
                        if mi is not None:
                            mb = (mb or 0.0) + float(getattr(mi, "rss", 0)) / 2 ** 20
            except Exception:
                self._nt_procs = []
                return None
            self._nt_procs = procs
        running = bool(procs)
        try:
            from .ops_checks import market_open
            mo = market_open(now)
        except Exception:
            mo = False
        cfg = getattr(self.bot, "cfg", None) or {}
        routes = bool(getattr(self.bot, "running", False)) and cfg.get("adapter") == "ninjatrader"
        return {"running": running, "mb": None if mb is None else round(mb), "market_open": mo, "routes": routes}

    def _storage(self, now, free_gb) -> dict | None:
        """{free_gb, bot_gb, nt_gb}: the free space every sample (cheap); the two folder sizes from a capped walk at most every
        STORAGE_EVERY_S, the first one STORAGE_WARM_S after the server start. Never raises."""
        try:
            if free_gb is None:
                return None
            if now - self.t0 >= STORAGE_WARM_S and now - self._st["t"] >= STORAGE_EVERY_S:
                bot, bc = dir_gb(self.root)
                nt_dir = nt_folder()
                nt, nc = dir_gb(nt_dir) if nt_dir else (None, False)
                self._st = {"t": now, "bot_gb": bot, "nt_gb": nt, "bot_gb_capped": bc, "nt_gb_capped": nc}
            return {"free_gb": round(free_gb, 1), **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in self._st.items() if k != "t"}}
        except Exception:
            return None

    def facts(self, now=None) -> dict:
        now = time.time() if now is None else now
        f: dict = {}
        ps = self.ps
        if ps is not None:
            try:
                self.cpu.append(float(ps.cpu_percent(interval=None)))
                f["cpu_pct"] = _median(self.cpu)
            except Exception:
                pass
            try:
                vm = ps.virtual_memory()
                f.update(ram_pct=float(vm.percent), ram_used_gb=float(getattr(vm, "used", 0)) / 2 ** 30 or None,
                         ram_total_gb=float(getattr(vm, "total", 0)) / 2 ** 30 or None)
            except Exception:
                pass
            try:
                if self._proc is not None:
                    mb = float(self._proc.memory_info().rss) / 2 ** 20
                    self.rss.append((now, mb))
                    f["bot_mb"] = mb
                    if self.base_mb is None and now - self.t0 >= 600:      # after a 10-min warm-up (the 5-year frames load)
                        self.base_mb = min(m for t, m in self.rss)
                    f["bot_base_mb"] = self.base_mb
                    old = [(t, m) for t, m in self.rss if now - t >= 3600]
                    if old and now - self.t0 >= 2 * 3600:
                        t1, m1 = old[-1]
                        f["bot_rate_mbh"] = max(0.0, (mb - m1) / ((now - t1) / 3600.0))
            except Exception:
                pass
        try:
            f["disk_free_gb"] = shutil.disk_usage(self.root).free / 1e9
        except Exception:
            pass
        st = self._storage(now, f.get("disk_free_gb"))
        if st is not None:
            f["storage"] = st
        nt = self._nt(now)
        if nt is not None:
            f["nt"] = nt
        if now - self._od["t"] >= ONEDRIVE_EVERY_S:
            self._od = {"t": now, "files": onedrive_conflicts(self.root, self.host)}
        f["onedrive"] = {"files": self._od["files"], "in_onedrive": in_onedrive(self.root)}
        ck = self._clock()
        if ck is not None:
            f["clock"] = ck
        try:
            h = getattr(self.bot, "health", None) or {}
            lp = getattr(self.bot, "last_poll", None)
            if getattr(self.bot, "running", False) and lp is not None and lp != self._last_poll and h.get("poll_ms") is not None:
                self._last_poll = lp
                self.polls.append((now, float(h["poll_ms"])))
            r15 = [ms for t, ms in self.polls if now - t <= 900]
            prev = [ms for t, ms in self.polls if 900 < now - t <= 4500]
            if r15:
                f["poll"] = {"med15": _median(r15), "med_prev": _median(prev) if len(prev) >= 5 else None, "n15": len(r15)}
        except Exception:
            pass
        return f

    def block(self, now=None) -> dict:
        now = time.time() if now is None else now
        sto = None
        try:
            fa = self.facts(now)
            sto = fa.get("storage")
            ls = lines(fa)
        except Exception as e:
            ls = [_line("error", AMBER, f"health check failed: {e.__class__.__name__}")]
        have = {ln["key"] for ln in ls}
        out = {"t": int(now), "level": level_of(ls), "lines": ls, "skipped": [k for k in LABELS if k not in have],
               "psutil": self.ps is not None}
        if isinstance(sto, dict):
            out["storage"] = sto
        return out


# ---------------------------------------------------------------------------------------------- pushes
def _send(payload: dict, sender=None):
    """The phone push (engine/alerts_plus.pc_send: the app's on / silent / off level for the kind, de-dup by key, in a
    thread). sender(payload) for tests. Never raises."""
    try:
        if sender is not None:
            return sender(payload)
        from . import alerts_plus
        alerts_plus.pc_send(payload)
        return {"queued": True}
    except Exception as e:
        return {"error": e.__class__.__name__}


def red_notices(block: dict, prev: dict | None, state: dict, now) -> list:
    """A red line in this block AND the previous one -> one push per issue per ET day (state["sent"] keys)."""
    if os.environ.get("LE_PC_HEALTH_PUSH") == "0":
        return []
    was = {ln["key"]: ln["level"] for ln in (prev or {}).get("lines") or []}
    day = _et(now).date().isoformat()
    out = []
    from . import push
    disk_red = any(ln.get("key") == "disk" and ln.get("level") == RED for ln in block.get("lines") or [])
    for ln in block.get("lines") or []:
        if ln["level"] != RED or was.get(ln["key"]) != RED:
            continue
        if ln["key"] == "storage" and disk_red:               # the same low disk: one push, not two
            continue
        key = f"pchealth:{ln['key']}:{day}"
        if key in state.setdefault("sent", {}):
            continue
        state["sent"][key] = int(now)
        out.append(push.text_payload("PC", "pc_health", f"PC health: {ln['label']} red", str(ln["text"])[:500], key=key,
                                     t=int(now), url="#/accounts"))
    if len(state.get("sent") or {}) > 200:
        state["sent"] = dict(sorted(state["sent"].items(), key=lambda kv: kv[1])[-200:])
    return out


# ---------------------------------------------------------------------------------------------- the watcher thread
def in_window(now, wd: int, win: tuple) -> bool:
    e = _et(now)
    return e.weekday() == wd and win[0] <= e.hour * 60 + e.minute < win[1]


class Watcher:
    """server.py: Watcher(BOT).start(). tick() samples, pushes red lines, runs the Sunday self-test / readiness and the
    baseline self-test. Everything is injectable for tests (clock, sampler, runner, sender, readiness, version)."""

    def __init__(self, bot, clock=time.time, every_s: float = SAMPLE_S, state_path: str = STATE_PATH, block_path: str = BLOCK_PATH,
                 sampler=None, runner=None, sender=None, readiness_fn=None, version_fn=None, selftest_last=None, started_at=None):
        self.bot, self.clock, self.every_s = bot, clock, every_s
        self.state_path, self.block_path = state_path, block_path
        self.sampler = sampler if sampler is not None else Sampler(bot)
        self._runner, self.sender, self.readiness_fn = runner, sender, readiness_fn
        self.version_fn, self.selftest_last = version_fn, selftest_last
        self.started_at = clock() if started_at is None else started_at
        self.block: dict | None = None
        self._prev = None
        self._stop = threading.Event()
        self._thread = None
        self.events: list = []                # what the schedules did (tests, the CLI)

    @property
    def runner(self):
        if self._runner is None:
            from . import pc_selftest
            self._runner = pc_selftest.RUNNER
        return self._runner

    def _state(self) -> dict:
        return _read_json(self.state_path)

    def _ver(self):
        try:
            if self.version_fn is not None:
                return self.version_fn()
            from . import autoupdate
            return (autoupdate.version() or {}).get("sha")
        except Exception:
            return None

    def _st_last(self) -> dict:
        try:
            if self.selftest_last is not None:
                return self.selftest_last() or {}
            from . import pc_selftest
            return pc_selftest.last()
        except Exception:
            return {}

    def _selftest_done(self, mode):
        def done(res):
            try:
                from . import pc_selftest
                p = pc_selftest.notice(res, mode, now=self.clock())
                if p:
                    self.events.append({"t": int(self.clock()), "push": p["key"]})
                    _send(p, self.sender)
            except Exception:
                pass
        return done

    def schedules(self, now, state: dict) -> list:
        """Sunday 15:30 ET self-test, Sunday 17:30 ET readiness, the baseline after a start. Returns what started."""
        did = []
        e = _et(now)
        day = e.date().isoformat()
        busy = False
        try:
            busy = bool(self.runner.busy())
        except Exception:
            busy = True
        if in_window(now, 6, SUNDAY_TEST) and state.get("sunday_selftest") != day and not busy:
            state["sunday_selftest"] = day
            r = self.runner.start("sunday", on_done=self._selftest_done("sunday"))
            did.append({"selftest": "sunday", "started": bool((r or {}).get("started"))})
            busy = True
        if in_window(now, 6, SUNDAY_READY) and state.get("readiness") != day:
            state["readiness"] = day
            try:
                if self.readiness_fn is not None:
                    p = self.readiness_fn(self.bot, now)
                else:
                    from . import readiness
                    p = readiness.notice(self.bot, now)
            except Exception as ex:
                p = None
                did.append({"readiness": "failed", "error": ex.__class__.__name__})
            if p:
                _send(p, self.sender)
                did.append({"readiness": p.get("key")})
        if not busy and now - self.started_at >= BASELINE_AFTER_S and os.environ.get("LE_SELFTEST_BASELINE") != "0":
            try:
                from .autoupdate import in_blackout
                blackout = in_blackout(now)
            except Exception:
                blackout = True
            ver = self._ver()
            if ver and not blackout and state.get("baseline_v") != ver and (self._st_last() or {}).get("version") != ver:
                state["baseline_v"] = ver
                r = self.runner.start("baseline", on_done=self._selftest_done("baseline"))
                did.append({"selftest": "baseline", "version": ver, "started": bool((r or {}).get("started"))})
        return did

    def tick(self, now=None) -> dict:
        now = self.clock() if now is None else now
        state = self._state()
        blk = self.sampler.block(now)
        self.block = blk
        _write_json(self.block_path, blk)
        for p in red_notices(blk, self._prev, state, now):
            self.events.append({"t": int(now), "push": p["key"]})
            _send(p, self.sender)
        self._prev = blk
        did = []
        try:
            did = self.schedules(now, state)
            self.events += [{"t": int(now), **d} for d in did]
        except Exception as ex:
            did = [{"error": ex.__class__.__name__}]
        state["tick_t"] = int(now)
        _write_json(self.state_path, state)
        del self.events[:-50]
        return {"block": blk, "did": did}

    def _run(self):
        self._stop.wait(min(30.0, self.every_s))
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                pass
            self._stop.wait(self.every_s)

    def start(self):
        """The thread, on the real server only: LE_PC_WATCH=0, a dev / test server (LE_NO_AUTOSTART=1) and the self-test's
        sealed children (LE_SELFTEST_CHILD=1) never start it."""
        if os.environ.get("LE_PC_WATCH") == "0" or os.environ.get("LE_NO_AUTOSTART") == "1" or os.environ.get("LE_SELFTEST_CHILD") == "1":
            return False
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="pc-watch", daemon=True)
            self._thread.start()
        return True

    def stop(self):
        self._stop.set()


WATCHER: Watcher | None = None              # server.py sets it


def hb_block(path: str | None = None) -> dict | None:
    """The heartbeat's "pc_health" block: the Watcher's last block (else logs/pc_health.json when fresh), ~1.5 KB. None
    when there is none yet (the key is then left out). Never raises."""
    try:
        b = WATCHER.block if WATCHER is not None and WATCHER.block else _read_json(path)
        if not b or time.time() - float(b.get("t") or 0) > 3600:
            return None
        return {"t": b.get("t"), "level": b.get("level"),
                "lines": [{k: ln.get(k) for k in ("key", "level", "text")} for ln in b.get("lines") or []],
                "skipped": b.get("skipped"), **({"storage": b["storage"]} if isinstance(b.get("storage"), dict) else {})}
    except Exception:
        return None


def main(argv=None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="python -m engine.pc_health", description="PC health lines (read-only)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--readiness", action="store_true", help="build the Sunday readiness push now")
    ap.add_argument("--send", action="store_true", help="with --readiness: push it too")
    a = ap.parse_args(argv)
    if a.readiness:
        from . import readiness
        p = readiness.notice(None, time.time(), manual=True)
        print(f"{p['title']}\n{p['body']}")
        if a.send:
            from . import push
            print(json.dumps(push.pc_send_now(p)))
        return 0
    s = Sampler(None)
    time.sleep(0.5)
    b = s.block()
    if a.json:
        print(json.dumps(b, indent=1))
    else:
        tag = {GREEN: " OK ", AMBER: "WARN", RED: "FIX "}
        for ln in b["lines"]:
            print(f"  [{tag.get(ln['level'], ln['level'])}] {ln['label']:<16} {ln['text']}")
        if b["skipped"]:
            print(f"  (not measured here: {', '.join(b['skipped'])})")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
