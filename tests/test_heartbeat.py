"""The PC heartbeat push (engine/heartbeat.py) made robust after the Surface went silent 22:38 -> 05:20 ET on 2026-10-25/26.
Offline: temporary bare git repos only, fake bots, no network, never the real data/ or .git.

  python -X utf8 -m tests.test_heartbeat

Checks:
  1. push from the private scratch git dir: round trip, one orphan commit, the project's .git gets no object / ref / index
     change, works from a SHALLOW clone with left-over lock files (index.lock, shallow.lock, the tracking ref's .lock),
     a stale lock in the scratch dir is cleared, the remote's main never moves, a non-heartbeat branch is refused.
  2. another writer moved the branch (old server / second PC): the lease is refused, the tip re-read, the push retried.
  3. a hanging git (remote helper that never answers, like git-remote-https / the credential manager): the Windows
     subprocess.run timeout path blocks for the helper's whole life (reproduced), run_cmd returns at its timeout and kills
     the helper; push returns an error in seconds; the push never prompts (GIT_TERMINAL_PROMPT=0, GCM_INTERACTIVE=never).
  4. the thread: an exception never ends the loop; a dead thread / a hung beat is restarted by the watchdog (new lock,
     the hung one exits without pushing again); a frozen process (PC asleep) is noticed and pushes at once; after a
     failure the next try comes within a minute; health.hb / status() carry the last error (redacted), restarts, sleep.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import heartbeat as hb  # noqa: E402

RES: list = []
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:400]})" if info and not cond else ""), flush=True)


def git(*a, cwd=None, inp=None):
    r = subprocess.run(["git", "-c", "commit.gpgsign=false", *a], cwd=cwd, input=inp, capture_output=True, env=ENV)
    return r.stdout.decode(errors="replace").strip()


def tip(bare, ref="heartbeat"):
    return git("--git-dir", bare, "rev-parse", "-q", "--verify", f"refs/heads/{ref}")


def snapshot(work):
    """What the push must never change in the project repo: its objects, refs, index, HEAD, shallow file."""
    gd = os.path.join(work, ".git")
    objs = sorted(os.path.relpath(os.path.join(b, n), gd) for b, _d, ns in os.walk(os.path.join(gd, "objects")) for n in ns)
    refs = git("for-each-ref", "--format=%(refname) %(objectname)", cwd=work)
    idx = open(os.path.join(gd, "index"), "rb").read() if os.path.exists(os.path.join(gd, "index")) else None
    sh = open(os.path.join(gd, "shallow")).read() if os.path.exists(os.path.join(gd, "shallow")) else None
    return objs, refs, idx, git("rev-parse", "HEAD", cwd=work), sh


def fake_bot(**kw):
    return SimpleNamespace(cfg={"adapter": "paper"}, adapter=None, health={}, state={}, ledger=[], running=True, started_at=None, **kw)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_hbtest_")
    try:
        # ---------------------------------------------------------------- an origin with a real main history
        origin = os.path.join(tmp, "origin.git")
        seed = os.path.join(tmp, "seed")
        git("init", "-q", "--bare", "-b", "main", origin)
        git("init", "-q", "-b", "main", seed)
        for i in range(3):
            with open(os.path.join(seed, "f.txt"), "w") as fh:
                fh.write(f"v{i}\n")
            git("add", "f.txt", cwd=seed)
            git("commit", "-q", "-m", f"main {i}", cwd=seed)
        git("remote", "add", "origin", origin, cwd=seed)
        git("push", "-q", "origin", "main", cwd=seed)
        main0 = tip(origin, "main")
        # the PC's checkout: a SHALLOW clone (like the Surface), with lock files a killed git / a refused pull left behind
        work = os.path.join(tmp, "pc")
        subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + origin, work], capture_output=True, env=ENV)
        git("remote", "set-url", "origin", origin, cwd=work)
        check("setup: the PC checkout is shallow", os.path.exists(os.path.join(work, ".git", "shallow")))
        locks = [os.path.join(work, ".git", p) for p in ("index.lock", "shallow.lock", "packed-refs.lock", "HEAD.lock")]
        os.makedirs(os.path.join(work, ".git", "refs", "remotes", "origin"), exist_ok=True)
        locks.append(os.path.join(work, ".git", "refs", "remotes", "origin", "heartbeat.lock"))
        for p in locks:
            open(p, "w").close()
        before = snapshot(work)

        # ---------------------------------------------------------------- 1. push from the scratch dir
        print("1. push from the private scratch git dir", flush=True)
        now = time.time()
        raw = bytes(range(256)) + b"\r\n\n"
        r1 = hb.push({"t": int(now), "running": True, "every_s": 300}, cwd=work, files={"bars_1m.csv.gz": raw})
        check("push OK from a shallow checkout with index.lock / shallow.lock / packed-refs.lock / HEAD.lock / the tracking "
              "ref's .lock left over", r1.get("ok") and r1.get("attempts") == 1, r1)
        got = hb.read(cwd=seed, now=now + 60, files=("bars_1m.csv.gz",))
        check("read back: present, fresh, the bar file byte for byte", got.get("present") and not got.get("silent")
              and (got.get("files") or {}).get("bars_1m.csv.gz") == raw, {k: got.get(k) for k in ("present", "reason")})
        r2 = hb.push({"t": int(now) + 300, "running": True, "every_s": 300}, cwd=work)
        check("second push: lease on the commit pushed last, one try", r2.get("ok") and r2.get("attempts") == 1 and not r2.get("retried"), r2)
        check("the branch stays ONE orphan commit", git("--git-dir", origin, "rev-list", "--count", "heartbeat") == "1")
        after = snapshot(work)
        check("the project's .git is untouched: no object, ref, index, HEAD or shallow change", after == before,
              [a == b for a, b in zip(after, before)])
        check("its lock files are left alone (never deleted by the heartbeat)", all(os.path.exists(p) for p in locks))
        check("the remote's main never moved", tip(origin, "main") == main0)
        scr = hb.scratch_dir(work)
        check("the scratch dir is data/heartbeat_pub.git under the project, gitignored in the real repo",
              os.path.isdir(os.path.join(scr, "objects")) and "data/heartbeat_pub.git/" in open(os.path.join(ROOT, ".gitignore")).read())
        check("scratch ref refs/hb/last = the pushed commit", git("--git-dir", scr, "rev-parse", hb.LAST_REF) == tip(origin))
        stale = os.path.join(scr, "refs", "hb", "last.lock")
        open(stale, "w").close()
        os.utime(stale, (now - 3600, now - 3600))
        r3 = hb.push({"t": int(now) + 600, "running": True, "every_s": 300}, cwd=work)
        check("a stale lock left in the scratch dir by a killed git is cleared, the push goes on",
              r3.get("ok") and not os.path.exists(stale), r3)
        for b in ("main", "master", "dashboard", "control", "live", "refs/heads/main", "heartbeat/../main", ""):
            rr = hb.push({"t": 1}, cwd=work, branch=b)
            if rr.get("ok") or "refused" not in str(rr.get("error")):
                check(f"branch {b!r} refused", False, rr)
                break
        else:
            check("any branch but heartbeat is refused (main, master, dashboard, control, live, ...)", True)
        check("main still never moved", tip(origin, "main") == main0)

        # ---------------------------------------------------------------- 2. another writer moved the branch
        print("2. another writer moved the branch", flush=True)
        other = os.path.join(tmp, "other.git")          # another process / PC: plain git, its own repo
        git("init", "-q", "--bare", other)
        blob = git("--git-dir", other, "hash-object", "-w", "--stdin", inp=b'{"host":"OTHER-PC"}')
        tree = git("--git-dir", other, "mktree", inp=f"100644 blob {blob}\theartbeat.json\n".encode())
        oc = git("--git-dir", other, "commit-tree", tree, "-m", "other")
        git("--git-dir", other, "push", "-q", "--force", origin, f"{oc}:refs/heads/heartbeat")
        foreign = tip(origin)
        check("setup: a second writer pushed its own heartbeat", foreign == oc, (foreign, oc))
        r4 = hb.push({"t": int(now) + 900, "running": True, "every_s": 300}, cwd=work)
        check("our lease is refused (stale), the tip re-read, the push retried once and lands",
              r4.get("ok") and r4.get("attempts") == 2 and "moved" in str(r4.get("retried")) and tip(origin) != foreign, r4)
        check("still one orphan commit, main untouched", git("--git-dir", origin, "rev-list", "--count", "heartbeat") == "1"
              and tip(origin, "main") == main0)

        # ---------------------------------------------------------------- 3. a hanging git
        print("3. a git that hangs (remote helper / credential manager)", flush=True)
        bindir = os.path.join(tmp, "bin")
        os.makedirs(bindir)
        pids = os.path.join(tmp, "hang.pids")
        helper = os.path.join(bindir, "git-remote-hang")
        with open(helper, "w") as fh:
            fh.write(f'#!/bin/sh\necho $$ >> "{pids}"\nsleep 8\n')
        os.chmod(helper, 0o755)
        env_h = {**ENV, "PATH": bindir + os.pathsep + os.environ.get("PATH", "")}

        def windows_run(cmd, timeout):
            """What CPython's subprocess.run does on Windows after a timeout: kill git, then communicate() WITHOUT a
            limit (Lib/subprocess.py run(): 'if _mswindows: exc.stdout, exc.stderr = process.communicate()')."""
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=env_h)
            try:
                p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()                 # waits until the helper (holding stderr) exits
            return p
        t0 = time.monotonic()
        windows_run(["git", "ls-remote", "hang::x"], 1.0)
        old_s = time.monotonic() - t0
        check(f"reproduced: the Windows subprocess.run timeout path (1 s) blocks until the hung helper ends ({old_s:.1f} s)",
              old_s >= 6.0, old_s)
        if os.path.exists(pids):
            os.remove(pids)
        t0 = time.monotonic()
        rr = hb.run_cmd(["git", "ls-remote", "hang::x"], timeout=1.0, env=env_h)
        new_s = time.monotonic() - t0
        check(f"run_cmd returns at its timeout ({new_s:.1f} s), timed_out, the error says so",
              new_s < 4.0 and rr.timed_out and rr.returncode != 0 and "timed out after 1 s" in rr.err, (new_s, rr.err))
        def running(pid: int) -> bool:
            try:
                os.kill(pid, 0)
            except (ProcessLookupError, PermissionError):
                return False
            try:                                  # killed but not reaped yet (a zombie) counts as gone
                return open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[0] != "Z"
            except OSError:
                return False
        want = [int(x) for x in (open(pids).read().split() if os.path.exists(pids) else [])]
        deadline = time.monotonic() + 3.0
        alive = want
        while alive and time.monotonic() < deadline:
            time.sleep(0.1)
            alive = [p for p in want if running(p)]
        check("the hung helper (grandchild) is killed with git", os.path.exists(pids) and not alive, alive)
        orig_t, orig_path = hb.GIT_TIMEOUT_S, os.environ.get("PATH", "")
        try:
            hb.GIT_TIMEOUT_S = 1.0
            os.environ["PATH"] = env_h["PATH"]
            hb._LAST_PUSHED[("hang::x", "heartbeat")] = "0" * 40     # skip the first ls-remote: straight to the push
            t0 = time.monotonic()
            rp = hb.push({"t": 1}, cwd=work, remote="hang::x", timeout=1.0)
            push_s = time.monotonic() - t0
            check(f"push to a hanging remote returns an error in {push_s:.1f} s (push timed out, the probe too), never raises",
                  not rp.get("ok") and push_s < 8.0 and "timed out" in str(rp.get("error")), rp)
        finally:
            hb.GIT_TIMEOUT_S = orig_t
            os.environ["PATH"] = orig_path
        e = hb._git_env()
        check("git never prompts: GIT_TERMINAL_PROMPT=0, GCM_INTERACTIVE=never, credential.interactive=never",
              e.get("GIT_TERMINAL_PROMPT") == "0" and e.get("GCM_INTERACTIVE") == "never" and "credential.interactive=never" in hb._NET_CFG)
        check("a stalled transfer is dropped (http.lowSpeedLimit / lowSpeedTime)", "http.lowSpeedTime=30" in hb._NET_CFG)
        check("error texts lose credentials", hb._redact("fatal: https://u:ghp_x@github.com/o/r") == "fatal: https://github.com/o/r")

        # ---------------------------------------------------------------- 4. the thread + watchdog
        print("4. the push thread and its watchdog", flush=True)
        lp = os.path.join(tmp, "hb_last.json")
        broken = SimpleNamespace(cfg={"adapter": "paper"}, adapter=None, health={}, state={"strategy": "lit"}, ledger=[], running=True,
                                 started_at=None)
        pl = hb.Heartbeat(broken, last_path=lp).payload()
        check("payload with a non-dict state['strategy'] (raised AttributeError before) builds", isinstance(pl, dict) and "health" in pl)

        calls = {"n": 0}

        def flaky(payload, files=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            if calls["n"] == 2:
                return {"ok": False, "error": "fatal: unable to access 'https://u:tok@github.com/x/y.git/': Could not resolve host"}
            return {"ok": True, "commit": "abc"}
        h = hb.Heartbeat(fake_bot(), every_s=300, last_path=lp, push_fn=flaky, log=lambda *a: None)
        r = h.beat()
        check("an exception inside the push is caught: the beat returns an error, never raises",
              not r.get("ok") and "boom" in str(r.get("error")) and h.fails == 1, r)
        r = h.beat()
        hbk = h.payload()["health"]["hb"]
        check("health.hb in the payload: fails 2, the last error (credentials redacted), its time",
              hbk["fails"] == 2 and "Could not resolve host" in hbk["last_error"] and "tok@" not in hbk["last_error"]
              and hbk["last_error_t"], hbk)
        check("after a failure the next try comes within a minute (retry_s 60), not after 5 min", h.next_wait() == 60.0, h.next_wait())
        r = h.beat()
        check("push works again: fails 0, last_ok_t set, the wait back to every_s", r.get("ok") and h.fails == 0 and h.last_ok_t
              and h.next_wait() == 300.0 and h.status()["health"]["ok"] is True, h.status())

        # the live threads: a BaseException ends the push thread -> the watchdog restarts it
        os.environ["LE_HEARTBEAT"] = "1"
        try:
            seen = {"n": 0}

            def dies_once(payload, files=None):
                seen["n"] += 1
                if seen["n"] == 1:
                    raise SystemExit("thread killed")    # not an Exception: ends the thread (like any fatal error)
                return {"ok": True, "commit": "x"}
            h2 = hb.Heartbeat(fake_bot(), every_s=0.05, last_path=lp, push_fn=dies_once, log=lambda *a: None, watch_s=0.05,
                              stuck_s=5.0)
            h2.start()
            deadline = time.time() + 5
            while time.time() < deadline and not (h2.restarts and seen["n"] >= 3):
                time.sleep(0.05)
            h2.stop()
            check("a dead push thread is restarted by the watchdog, beats again", h2.restarts >= 1 and seen["n"] >= 3
                  and "stopped" in str((h2.restart or {}).get("why")), (h2.restarts, seen, h2.restart))

            # a hung beat (a git that ignores every timeout) -> a new thread with its own lock; the hung one exits quietly
            gate = threading.Event()
            hung = {"n": 0}

            def hangs_first(payload, files=None):
                hung["n"] += 1
                if hung["n"] == 1:
                    gate.wait(10)
                    return {"ok": True, "commit": "late"}
                return {"ok": True, "commit": "fresh"}
            h3 = hb.Heartbeat(fake_bot(), every_s=30, last_path=lp, push_fn=hangs_first, log=lambda *a: None, watch_s=0.05,
                              stuck_s=0.3)
            h3.start()
            deadline = time.time() + 5
            while time.time() < deadline and not (h3.restarts and (h3.last or {}).get("commit") == "fresh"):
                time.sleep(0.05)
            ok_restart = h3.restarts == 1 and (h3.last or {}).get("commit") == "fresh" and "hung" in str((h3.restart or {}).get("why"))
            gate.set()
            time.sleep(0.3)
            h3.stop()
            check("a hung beat: the watchdog starts a new push thread (own lock) that pushes; the hung one, released, exits "
                  "without pushing again", ok_restart and hung["n"] == 2, (h3.restarts, h3.restart, h3.last, hung))
        finally:
            os.environ.pop("LE_HEARTBEAT", None)

        # the PC asleep: the watchdog's tick took hours -> recorded, the push thread woken at once
        clock = [1_793_000_000.0]
        h4 = hb.Heartbeat(fake_bot(), every_s=300, last_path=lp, push_fn=lambda p, files=None: {"ok": True}, log=lambda *a: None,
                          clock=lambda: clock[0])
        h4._started = True
        h4._thread = SimpleNamespace(is_alive=lambda: True)            # a push thread waiting out its 5 minutes
        h4._wake.clear()
        a = clock[0]
        clock[0] += 6 * 3600 + 34 * 60                                   # 22:43 -> 05:17, like the Surface
        h4.watch_tick(a, clock[0])
        fz = h4.health_block()["frozen"]
        check("a 6 h 34 min freeze (PC asleep) is noticed: frozen {from, to, s}, the push thread woken to push now",
              fz and fz["s"] == 6 * 3600 + 34 * 60 and h4._wake.is_set() and h4.frozen_n == 1, fz)
        h4._wake.clear()
        h4.watch_tick(clock[0], clock[0] + 60)
        check("a normal tick afterwards: no new freeze, no wake", h4.frozen_n == 1 and not h4._wake.is_set())
        # a beat interrupted by the sleep is not reported as hung (its clock is shifted by the freeze)
        h4._beat = {"t0": clock[0] - 30, "phase": "push", "gen": 0}
        h4.loop_t = clock[0] - 30
        b0 = clock[0]
        clock[0] += 3 * 3600
        h4.watch_tick(b0, clock[0])
        check("a push in flight when the PC slept is not restarted as 'hung' after the wake",
              h4.restarts == 0 and h4.check(clock[0] + 10) is None, (h4.restarts, h4._beat))
        st = hb.Heartbeat(fake_bot(), last_path=lp).status()
        check("status() (GET /api/health/ping) keeps 'last' and adds 'health' (fails, restarts, frozen, watchdog)",
              {"enabled", "every_s", "last", "thread_alive", "health"} <= set(st) and {"fails", "restarts", "frozen", "watchdog"}
              <= set(st["health"]), st)
        import json as _json
        check("health.hb stays small (< 600 bytes)", len(_json.dumps(h4.health_block())) < 600, len(_json.dumps(h4.health_block())))
        src = open(os.path.join(ROOT, "engine", "heartbeat.py"), encoding="utf-8").read()
        check("no plain subprocess.run left in the push path (every git call through run_cmd)",
              "subprocess.run([\"git\", \"push\"" not in src and "_git([\"push\"" not in src)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"heartbeat: {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
