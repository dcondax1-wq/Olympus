"""The browser lock (/tmp/olympus_browser.lock), held by tests/run_area.py only around a browser suite (day-quality round 2,
2026-11-20): helpers sharing a box take turns on Chromium, while plain suites run in parallel without waiting.

    with browser_lock.hold(path, wait=2400) as how:   how = "took" | "ancestor" (an outer `flock` of this process tree already
                                                     holds it: going on, never a self-deadlock) | "off" (no fcntl: Windows)
Raises TimeoutError when another process keeps it past `wait` seconds. Same lock as `flock -w 2400 /tmp/olympus_browser.lock ...`
(flock(2) on the file), so both styles exclude each other.
"""
from __future__ import annotations

import contextlib
import os
import time

try:
    import fcntl
except ImportError:                                    # Windows: no shared box, nothing to lock
    fcntl = None

DEFAULT = "/tmp/olympus_browser.lock"


def ancestors(pid=None) -> list:
    out, p = [], pid or os.getpid()
    for _ in range(64):
        try:
            with open(f"/proc/{p}/stat", encoding="utf-8") as fh:
                ppid = int(fh.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
        if ppid <= 1:
            break
        out.append(ppid)
        p = ppid
    return out


def holders(path) -> list:
    """pids holding a FLOCK on this file (Linux /proc/locks), [] when unknown"""
    try:
        st = os.stat(path)
        with open("/proc/locks", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    want = f":{st.st_ino}"
    out = []
    for ln in lines:
        f = ln.split()
        if len(f) >= 6 and f[1] == "FLOCK" and f[5].endswith(want):
            try:
                out.append(int(f[4]))
            except ValueError:
                pass
    return out


def held_by_ancestor(path) -> bool:
    anc = set(ancestors())
    return any(h in anc for h in holders(path))


@contextlib.contextmanager
def hold(path=DEFAULT, wait=2400.0, poll=1.0):
    if fcntl is None:
        yield "off"
        return
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        t0 = time.time()
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                how = "took"
                break
            except BlockingIOError:
                if held_by_ancestor(path):
                    how = "ancestor"
                    break
                if time.time() - t0 >= wait:
                    raise TimeoutError(f"{path} held by pid {holders(path) or '?'} for {wait:.0f}s")
                time.sleep(poll)
        try:
            yield how
        finally:
            if how == "took":
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
