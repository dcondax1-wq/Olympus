"""A hung bot server never lasts more than ~5 minutes silently (big-zeroerr2 2026-11-26).

What happened: on 2026-11-25 the PC's server stopped answering at 17:22 ET and stayed hung until ~00:35 ET. The 15-minute report
kept posting "BOT DOWN" to the public feed, self-heal only REPORTED it ("the bot server does not answer while it should run"),
the server's own alarms were inside the hung process, and the cloud's PC-silent watch only runs 03-15 ET. If it had lasted past
02:00 ET, London's entries would have been missed. The supervisor (scripts/run_bot.ps1) only restarts a server that EXITS.

This guard is a separate small process (so whatever froze the server cannot freeze it), started by server.py on the supervised
PC server (LE_SUPERVISED=1). Every CHECK_S it asks GET /api/health/ping (PING_TIMEOUT_S). No answer for HANG_S in a row:
  * flat (engine/autoupdate.files_flat_reason: LIT's live_state + every NinjaTrader leg file) -> the server's process tree is
    killed; run_bot.ps1 starts it again in ~5 s and the auto-resume brings an opted-in eval back armed. ONE Telegram line
    (engine/alert_bus, else the PC's ntfy notice): "PC server hung N min: restarted (flat)" + where it was stuck.
  * a trade may be open -> NOT killed (the stop and target sit at the broker); ONE line at once, then the restart as soon as
    the files say flat.
Where it was stuck: server.py arms faulthandler.dump_traceback_later(DUMP_S) from its event loop every 30 s; a loop frozen for
DUMP_S writes every thread's stack to logs/hang_stacks.txt (a C thread does it, no GIL needed). The guard quotes the top frame
and keeps a copy in logs/hang/ for Claude, so the next hang names its own cause.
Never: an order, arming, or a kill while a trade may be open. Off: LE_HANG_GUARD=0. State: data/hang_guard.json (gitignored).
Tests: tests.test_zeroerr2.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "hang_guard.json")
STACKS = os.path.join(ROOT, "logs", "hang_stacks.txt")
KEEP_DIR = os.path.join(ROOT, "logs", "hang")
CHECK_S = 20
PING_TIMEOUT_S = 10
HANG_S = 150                 # 2.5 min of no answer -> act (detected <= 2.5 min + one check, restarted within ~5 min)
DUMP_S = 120                 # server.py: the event loop frozen this long -> stacks to logs/hang_stacks.txt
START_GRACE_S = 120          # a server that is still starting (imports, the auto-resume) is not "hung"


def enabled(env=None) -> bool:
    e = os.environ if env is None else env
    return str(e.get("LE_HANG_GUARD", "1")).strip().lower() not in ("0", "off", "false")


def ping(port: int, timeout: float = PING_TIMEOUT_S) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/health/ping", headers={"User-Agent": "olympus-hang-guard/1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def alive(pid: int) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        try:
            r = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], capture_output=True, text=True, timeout=20)
            return str(int(pid)) in (r.stdout or "")
        except Exception:
            return True                            # cannot tell: never treated as gone
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def kill_tree(pid: int) -> bool:
    try:
        if os.name == "nt":
            r = subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True, text=True, timeout=30)
            return r.returncode == 0
        os.kill(int(pid), signal.SIGKILL)
        return True
    except Exception:
        return False


def where_stuck(since: float, path: str = STACKS) -> str:
    """The top frames of the server's frozen event loop thread from logs/hang_stacks.txt (written within this hang), or ''."""
    try:
        if os.path.getmtime(path) < since - DUMP_S - 60:
            return ""
        txt = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""
    frames = [ln.strip() for ln in txt.splitlines() if ln.strip().startswith("File ")]
    if not frames:
        return ""
    # faulthandler prints the most recent call FIRST: the first non-library frame is the culprit
    pick = next((f for f in frames if "site-packages" not in f and "lib" + os.sep + "python" not in f.lower()
                 and "\\lib\\" not in f.lower()), frames[0])
    return pick.replace('File "', "").replace('", line ', ":")[:160]


def default_notify(title: str, body: str, key: str) -> None:
    try:
        from . import alert_bus
        if alert_bus.active():
            alert_bus.send({"kind": "bot_stopped", "key": key, "title": title, "body": body}, wait=True)
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        from .autoupdate import notify_sync
        notify_sync(title, body, key)
    except Exception:  # noqa: BLE001
        pass


def _save(path, d):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        from .fsutil import replace as _replace
        _replace(path + ".tmp", path)
    except OSError:
        pass


def _hm(t) -> str:
    return dt.datetime.fromtimestamp(float(t), ET).strftime("%H:%M")


class Guard:
    """One guard for one server pid. step() is one check (tests drive it with fakes)."""

    def __init__(self, pid: int, port: int, root: str = ROOT, clock=time.time, ping_fn=None, alive_fn=None, kill_fn=None,
                 flat_fn=None, notify=None, state_path: str = STATE_PATH, stacks: str = STACKS, log=None):
        self.pid, self.port, self.root, self.clock = int(pid), int(port), root, clock
        self.ping_fn = ping_fn or (lambda: ping(self.port))
        self.alive_fn = alive_fn or (lambda: alive(self.pid))
        self.kill_fn = kill_fn or (lambda: kill_tree(self.pid))
        if flat_fn is None:
            def flat_fn():
                from .autoupdate import files_flat_reason
                return files_flat_reason(self.root)
        self.flat_fn = flat_fn
        self.notify = notify or default_notify
        self.state_path, self.stacks = state_path, stacks
        self.log = log or (lambda *_: None)
        self.started = clock()
        self.down_since = None
        self.told_open = False
        self.done = False

    def step(self) -> str:
        """'ok' | 'gone' (the server exited: the guard ends) | 'waiting' | 'open' (hung, a trade may be open) | 'restarted' |
        'failed'."""
        now = self.clock()
        if not self.alive_fn():
            self.done = True
            return "gone"
        if self.ping_fn():
            if self.down_since and self.told_open:
                self.notify("PC server answers again", f"The bot server came back by itself at {_hm(now)} ET (it did not answer for "
                            f"{int((now - self.down_since) // 60)} min). Nothing to do.", f"hang:back:{int(self.down_since)}")
            self.down_since, self.told_open = None, False
            return "ok"
        if now - self.started < START_GRACE_S:
            return "waiting"
        if self.down_since is None:
            self.down_since = now
        mins = (now - self.down_since) / 60.0
        if now - self.down_since < HANG_S:
            return "waiting"
        where = where_stuck(self.down_since, self.stacks)
        try:
            why = self.flat_fn()
        except Exception as e:  # noqa: BLE001
            why = f"cannot tell if flat ({e.__class__.__name__})"
        if why:
            if not self.told_open:
                self.told_open = True
                self.notify("PC server hung: NOT restarted", f"The bot server has not answered since {_hm(self.down_since)} ET. "
                            f"{why}: it is not restarted while a trade may be open (the stop and target sit at the broker). It "
                            "restarts by itself as soon as it is flat." + (f" Stuck at {where}." if where else ""),
                            f"hang:open:{int(self.down_since)}")
            return "open"
        self._keep(where)
        ok = self.kill_fn()
        rec = {"t": int(now), "pid": self.pid, "since": int(self.down_since), "min": round(mins, 1), "where": where, "killed": ok}
        hist = []
        try:
            hist = list((json.load(open(self.state_path, encoding="utf-8")) or {}).get("hist") or [])
        except Exception:  # noqa: BLE001
            pass
        _save(self.state_path, {"last": rec, "hist": (hist + [rec])[-30:]})
        try:
            from . import board_events
            board_events.emit("self_heal", "pc", f"PC server hung {int(mins)} min (no answer since {_hm(self.down_since)} ET): "
                              + ("restarted" if ok else "restart FAILED") + (f"; stuck at {where}" if where else "")[:200],
                              {"fault": "server_hang", "key": "server_hang"})
        except Exception:  # noqa: BLE001
            pass
        self.notify("PC server hung: restarted" if ok else "PC server hung: restart FAILED",
                    f"The bot server did not answer for {int(mins)} min (since {_hm(self.down_since)} ET). "
                    + ("It was flat, so it was restarted; your eval comes back armed by itself (auto-resume)." if ok else
                       "It could not be stopped: on the PC double-click STOP_BOT.bat, then START_BOT.bat.")
                    + (f" Stuck at {where}." if where else ""), f"hang:restart:{int(self.down_since)}")
        self.done = True
        return "restarted" if ok else "failed"

    def _keep(self, where):
        try:
            if os.path.isfile(self.stacks) and where:
                os.makedirs(KEEP_DIR, exist_ok=True)
                shutil.copy2(self.stacks, os.path.join(KEEP_DIR, "stacks-" + dt.datetime.now(ET).strftime("%Y%m%d-%H%M%S") + ".txt"))
        except OSError:
            pass


def spawn(pid: int, port: int, env=None) -> bool:
    """server.py: start the guard as its own process (never blocks; a second guard for the same pid exits by itself)."""
    e = dict(os.environ if env is None else env)
    if not enabled(e) or e.get("LE_SUPERVISED") != "1":
        return False
    kw = {"cwd": ROOT, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED_PROCESS | NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen([sys.executable, "-X", "utf8", "-m", "engine.hang_guard", "--pid", str(int(pid)), "--port", str(int(port))], **kw)
        return True
    except Exception:  # noqa: BLE001
        return False


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    try:
        pid = int(a[a.index("--pid") + 1])
        port = int(a[a.index("--port") + 1])
    except (ValueError, IndexError):
        print("python -m engine.hang_guard --pid <server pid> --port <port>")
        return 2
    lock = os.path.join(ROOT, "data", f"hang_guard_{pid}.lock")
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:                                   # a guard left by a reboot (its pid gone): take over
                other = int(open(lock).read().strip() or 0)
            except (OSError, ValueError):
                other = 0
            if other and alive(other):
                return 0                           # another guard watches this server already
            try:
                os.remove(lock)
            except OSError:
                return 0
    else:
        return 0
    try:
        g = Guard(pid, port)
        while not g.done:
            g.step()
            time.sleep(CHECK_S)
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
