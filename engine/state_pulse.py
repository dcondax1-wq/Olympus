"""STATE PULSE (night-truth 2026-11-22): a CHANGE in the bot's state reaches the phone at once, not 5-15 minutes later.

Why: on 2026-11-22 the bot stopped 20:55 and was running again 21:03 ET, but the phone said "bot stopped" until the next
15-minute report (tools/pc_report.py, Task Scheduler) picked up the next 5-minute heartbeat: 10+ minutes of a wrong screen.

What it does (a daemon thread of the bot server, read-only towards the bot):
  * every TICK_S it takes a tiny signature of the bot (signature(): running, each account armed / enabled / open / locked /
    entries today, the entry block); no network, no file, no order code: attributes the heartbeat already reads.
  * on a change (running <-> stopped, an account armed / disarmed, an entry block appearing / clearing, a trade opened /
    closed) it fires ONE small update, debounced: never within MIN_GAP_S (30 s) of the last one; changes inside the gap
    are folded into the next fire, which carries the newest state. A fire = a fresh heartbeat (Heartbeat.beat: the
    local logs/pc_hb/heartbeat.json in GitHub-free mode), the phone's live.json (Publisher.publish, its own 45 s gap) and
    `tools/pc_report.py --pulse --quiet`: ONLY the core status post on the public ntfy topic (no ext, no chart, no alerts:
    the trade alerts already go at once from engine/notify.instant_*).
  * the regular cadence is unchanged (heartbeat 5 min, the report every 15 min).
ntfy budget (ntfy.sh free: NTFY_DAY_CAP 250 messages a UTC day per IP), per UTC day at most:
      96 core (15-min report; a repeat within pc_report.CORE_MIN_GAP_S with nothing changed is skipped)
    + 66 ext  (2 parts every 44 min: pc_report.EXT_EVERY_S, EXT_PARTS)
    + 24 chart (pc_report.BARS_DAY_MAX)
    + 24 pulse (DAY_MAX here; pc_report --pulse enforces the same count from data/pc_report/pulse.json)
    = 210, + 12 kept for trade alerts (pc_report.TRADE_ALERT_RESERVE) = 222 <= 250 (budget(); tests/test_state_pulse.py).
  The pulse is also held when this PC's own count or ntfy's own count (GET /v1/account) leaves less than the reserve.
Off: LE_STATE_PULSE=0, a dev / test server (LE_NO_AUTOSTART=1), the self-test's children (LE_SELFTEST_CHILD=1). Never raises.
"""
from __future__ import annotations

import json
import os
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "data", "pc_report")
STATE_FILE = "pulse.json"
TICK_S = 10.0
MIN_GAP_S = 30.0                 # debounce: never two pulses within 30 s
DAY_MAX = 24                     # pulse posts a UTC day (ntfy budget above)
RUN_TIMEOUT_S = 120
START_GRACE_S = 90.0             # the first 90 s of a server start: "stopped" is not posted (the autostart is bringing the bot up)
BUSY_RC = 3                      # tools/pc_report.py --pulse: another report run holds the lock
# the other posts of a day (tools/pc_report.py), for the budget proof
CORE_DAY = 96
EXT_DAY = 66
BARS_DAY = 24
NTFY_DAY_CAP = 250
TRADE_ALERT_RESERVE = 12


def budget() -> dict:
    """The worst-case ntfy posts of a UTC day with the pulse on, and whether it holds under ntfy's cap with the reserve."""
    total = CORE_DAY + EXT_DAY + BARS_DAY + DAY_MAX
    return {"core": CORE_DAY, "ext": EXT_DAY, "bars": BARS_DAY, "pulse": DAY_MAX, "total": total,
            "reserve": TRADE_ALERT_RESERVE, "cap": NTFY_DAY_CAP, "holds": total + TRADE_ALERT_RESERVE <= NTFY_DAY_CAP}


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _call(obj, name, *a):
    f = getattr(obj, name, None)
    if not callable(f):
        return None
    try:
        return f(*a)
    except Exception:  # noqa: BLE001
        return None


def signature(bot, now=None) -> dict:
    """What the phone must see change at once. Small, JSON-safe, stable while nothing changes. Never raises.
      run   the bot runs
      blk   entries blocked (the feed / entry guard) + its reason, "" when none
      a     per account [armed, enabled, open, locked, entries today]: "lit" (the main account), "atlas" (account B),
            the extra accounts by id (engine/multi_account health rows)"""
    out = {"run": False, "blk": "", "a": {}}
    try:
        now = int(now or time.time())
        cfg = _d(getattr(bot, "cfg", None))
        st = _d(getattr(bot, "state", None))
        h = _d(getattr(bot, "health", None))
        out["run"] = bool(getattr(bot, "running", False))
        if h.get("entries_blocked") or h.get("feed_block"):
            out["blk"] = str(h.get("feed_block") or "entries blocked")[:60]
        ad = getattr(bot, "adapter", None)
        led = [r for r in list(getattr(bot, "ledger", None) or []) if isinstance(r, dict) and r.get("side") in ("buy", "sell")]
        try:
            from .accounts import trading_day
            today = trading_day(now)
            n_today = sum(1 for r in led if r.get("t") and trading_day(r["t"]) == today)
        except Exception:  # noqa: BLE001
            n_today = len(led)
        out["a"]["lit"] = [bool(cfg.get("armed")), not bool(getattr(ad, "disabled", None)) if ad is not None else False,
                           bool(st.get("position")), None, n_today]
        ab = getattr(bot, "acct_b", None)
        if ab is not None:
            dis = _call(ab, "disabled_reason")
            today = None
            try:
                from .accounts import trading_day
                today = trading_day(now)
            except Exception:  # noqa: BLE001
                pass
            lk = _d(getattr(ab, "lock", None))
            out["a"]["atlas"] = [str(_call(ab, "kind") or "").upper() == "LIVE" and not dis, not dis, bool(_call(ab, "position")),
                                 lk.get("reason") if lk.get("day") == today else None, _call(ab, "entries_today", today)]
        ra = getattr(bot, "accts", None)
        rows = _call(ra, "health", now) if ra is not None else None
        for r in rows or []:
            r = _d(r)
            if r.get("id"):
                out["a"][str(r["id"])] = [bool(r.get("armed")), bool(r.get("enabled")), bool(r.get("open")),
                                          r.get("locked") or None, r.get("entries_today")]
    except Exception:  # noqa: BLE001
        pass
    return out


def changes(old: dict | None, new: dict) -> list:
    """Plain words of what changed between two signatures ([] = nothing): for the log and the post's "pulse" note."""
    if not isinstance(old, dict):
        return ["first look"]
    out = []
    if bool(old.get("run")) != bool(new.get("run")):
        out.append("bot " + ("running" if new.get("run") else "stopped"))
    if (old.get("blk") or "") != (new.get("blk") or ""):
        out.append("entry block " + ("on" if new.get("blk") else "cleared"))
    oa, na = _d(old.get("a")), _d(new.get("a"))
    for k in sorted(set(oa) | set(na)):
        o, n = oa.get(k), na.get(k)
        if o == n:
            continue
        if not isinstance(o, list) or not isinstance(n, list) or len(o) < 5 or len(n) < 5:
            out.append(f"{k} " + ("added" if n else "removed"))
            continue
        if o[0] != n[0]:
            out.append(f"{k} " + ("armed" if n[0] else "disarmed"))
        if o[1] != n[1]:
            out.append(f"{k} " + ("enabled" if n[1] else "disabled"))
        if o[2] != n[2]:
            out.append(f"{k} trade " + ("opened" if n[2] else "closed"))
        if o[3] != n[3]:
            out.append(f"{k} " + ("locked" if n[3] else "unlocked"))
        if o[4] != n[4] and o[2] == n[2]:
            out.append(f"{k} entries today {n[4]}")
    return out


def _utc_day(t) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(int(t)))


def read_state(work: str = WORK) -> dict:
    try:
        with open(os.path.join(work, STATE_FILE), encoding="utf-8") as fh:
            j = json.load(fh)
        return j if isinstance(j, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def write_state(st: dict, work: str = WORK) -> None:
    try:
        os.makedirs(work, exist_ok=True)
        p = os.path.join(work, STATE_FILE)
        with open(p + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
        _fs_replace(p + ".tmp", p)
    except Exception:  # noqa: BLE001
        pass


def day_count(st: dict, now) -> int:
    try:
        return int(_d(st.get("days")).get(_utc_day(now)) or 0)
    except Exception:  # noqa: BLE001
        return 0


def count_one(st: dict, now) -> dict:
    """st with today's pulse count + 1 (the last 3 days kept)."""
    day = _utc_day(now)
    keep = _utc_day(int(now) - 3 * 86400)
    days = {k: v for k, v in _d(st.get("days")).items() if str(k) >= keep}
    days[day] = int(days.get(day) or 0) + 1
    return {**st, "days": days}


def _python() -> str:
    try:
        from .report_keeper import _python as p
        return p()
    except Exception:  # noqa: BLE001
        import sys
        return sys.executable or "python"


def default_run(argv, timeout):
    try:
        from .report_keeper import default_run as r
        return r(argv, timeout)
    except Exception as e:  # noqa: BLE001
        return -1, e.__class__.__name__


class Pulse:
    """The watcher thread. tick() is the whole logic (tests drive it with a fake clock and fake hooks)."""

    def __init__(self, bot, heartbeat=None, livepub=None, run=None, clock=time.time, work: str = WORK, log=None,
                 min_gap_s: float = MIN_GAP_S, day_max: int = DAY_MAX):
        self.bot, self.hb, self.lp = bot, heartbeat, livepub
        self.run = run or default_run
        self.clock, self.work = clock, work
        self.log = log or (lambda t: print(t, flush=True))
        self.min_gap_s, self.day_max = float(min_gap_s), int(day_max)
        self.posted_sig = None            # the signature the phone last got from us (or the file, after a restart)
        self.pending = None               # [what changed] waiting for the debounce
        self.last_fire = 0.0
        self.fires = 0
        self.held = None                  # why the last fire did not go
        self._loaded = False
        self.t0 = None                    # the first tick (the server start)
        self.grace_s = START_GRACE_S
        self._stop = threading.Event()
        self._thread = None

    def _load(self):
        self._loaded = True
        st = read_state(self.work)
        if isinstance(st.get("sig"), dict):
            self.posted_sig = st["sig"]
        self.last_fire = float(st.get("t") or 0.0)

    def tick(self, now=None) -> dict:
        """One look. -> {"changed": [...], "fired": bool, "held": why | None}. Never raises."""
        now = float(now if now is not None else self.clock())
        res = {"changed": [], "fired": False, "held": None}
        try:
            if not self._loaded:
                self._load()
            if self.t0 is None:
                self.t0 = now
            sig = signature(self.bot, now)
            ch = changes(self.posted_sig, sig)
            if not ch:
                self.pending = None
                return res
            res["changed"] = ch
            self.pending = ch
            if not sig.get("run") and now - self.t0 < self.grace_s:
                res["held"] = self.held = "server starting: the bot may come up in a moment"
                return res
            if now - self.last_fire < self.min_gap_s:
                res["held"] = self.held = f"debounce: next in {int(self.min_gap_s - (now - self.last_fire))} s"
                return res
            st = read_state(self.work)
            if day_count(st, now) >= self.day_max:
                res["held"] = self.held = f"ntfy budget: {self.day_max} pulses today already (the 15-minute report goes on)"
                self.posted_sig = sig         # nothing more to try today for this change; the regular report carries it
                return res
            res["fired"] = self.fire(sig, ch, now)
        except Exception as e:  # noqa: BLE001
            res["held"] = self.held = f"pulse failed softly: {e.__class__.__name__}"
        return res

    def fire(self, sig: dict, ch: list, now: float) -> bool:
        prev = self.posted_sig
        self.last_fire = now
        self.posted_sig = sig
        self.pending = None
        self.fires += 1
        if self.hb is not None:
            _call(self.hb, "beat")            # the fresh heartbeat first: the report reads it
        if self.lp is not None:
            try:
                from . import live_publish
                if live_publish.enabled():
                    self.lp.publish()
            except Exception:  # noqa: BLE001
                pass
        why = "; ".join(ch)[:120]
        rc, _ = self.run([_python(), "-X", "utf8", os.path.join(ROOT, "tools", "pc_report.py"), "--pulse", "--quiet",
                          "--why", why], RUN_TIMEOUT_S)
        if rc == BUSY_RC:                   # the 15-minute report holds the lock: try again after the debounce (it may have read
            self.posted_sig, self.pending = prev, ch     # the heartbeat before this change)
            self.held = "another report run is busy: again in 30 s"
            return False
        st = read_state(self.work)          # pc_report --pulse counted its post; keep our view of what went
        write_state({**st, "sig": sig, "t": int(now), "why": why}, self.work)
        self.held = None if rc == 0 else f"report child exit {rc}"
        try:
            self.log(f"[pulse] {why}: phone updated now" + ("" if rc == 0 else f" (report child exit {rc})"))
        except Exception:  # noqa: BLE001
            pass
        return rc == 0

    def _loop(self):
        while not self._stop.wait(TICK_S):
            self.tick()

    def start(self):
        if os.environ.get("LE_STATE_PULSE") == "0" or os.environ.get("LE_NO_AUTOSTART") == "1" \
                or os.environ.get("LE_SELFTEST_CHILD") == "1":
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._thread = threading.Thread(target=self._loop, name="state-pulse", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def status(self) -> dict:
        return {"fires": self.fires, "last_fire": int(self.last_fire) or None, "pending": self.pending, "held": self.held,
                "thread": bool(self._thread and self._thread.is_alive()), "budget": budget()}
