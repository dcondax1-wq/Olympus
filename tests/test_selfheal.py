"""Self-healing (2026-10-29): what broke on 2026-10-28 and what breaks next, recovered without the owner.

    python -X utf8 -m tests.test_selfheal      (temp folders only, fake NinjaTrader, no network)

 1. Weekend: NinjaTrader's connection DISCONNECTED Friday 17:00 -> Sunday; the running bot refuses entries while every
    connection is DISCONNECTED (and the startup reconcile names it), and takes Monday's 02:05 entry once NinjaTrader is
    CONNECTED again: no restart, no tap. Market closed all weekend: no FEED STALE / stale-block (market_open False).
 2. NinjaTrader restarted over the weekend (outgoing\\ wiped, the bot flat): no "NinjaTrader reset" block; Monday's entry
    goes in. (With a position open the reset block stays: tests/test_nt_exec_audit.)
 3. Disk growth: the narrator's daily feeds are gzipped after 3 days and deleted after 120 (ops_checks.rotate_logs);
    data/nt_bars stays capped (pcbars.ARCHIVE_KEEP_DAYS).
 4. State saves: every engine module writes its state through fsutil.replace (Windows / OneDrive lock retries), except the
    order-file publish (no-overwrite rename) and the corrupt-state move.
 5. GitHub Actions minutes: the cloud monitor's month estimate and saver mode (engine/actions_budget.py), the guard step's
    budget read (never blocks when the file cannot be read), month rollover.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import gzip
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.ninjatrader import ET  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def ts(*a):
    return dt.datetime(*a, tzinfo=ET).timestamp()


def t_weekend():
    print("1-2. weekend disconnect / NinjaTrader restart", flush=True)
    from engine import live
    from tests.test_lit_add_safety import World
    w = World()
    fake = w.fake
    conn = os.path.join(w.folder, "outgoing", "Tradovate.txt")
    w.now[0] = ts(2026, 10, 30, 16, 30)
    ad = w.make("wk.json")
    ad.tick()
    ok_fri = not any("DISCONNECTED" in p for p in ad.startup_problems())
    open(conn, "w").write("DISCONNECTED")                       # Friday 17:00: MFFU / Tradovate drops for the weekend
    for x in ((2026, 10, 31, 12, 0), (2026, 11, 1, 1, 30), (2026, 11, 1, 1, 30), (2026, 11, 1, 18, 5)):
        w.now[0] = ts(*x)
        ad.tick()
    sat = [live.market_open(ts(2026, 10, 31, 12, 0)), live.market_open(ts(2026, 11, 1, 17, 59)), live.market_open(ts(2026, 11, 1, 18, 0))]
    w.now[0] = ts(2026, 11, 2, 2, 5, 3)
    fake.move(25330.0)
    t = int(w.now[0]) - 3
    order = {"sym": "NQ", "side": "buy", "qty": 1, "stop": 25300.0, "target": 25400.0, "entry": 25330.0, "entry_t": t}
    k = len(fake.files)
    r1 = ad.send(dict(order))
    sp1 = ad.startup_problems()
    open(conn, "w").write("CONNECTED")                          # Sunday evening / Monday: NinjaTrader reconnects by itself
    w.now[0] = ts(2026, 11, 2, 2, 6, 3)
    ad.tick()
    r2 = ad.send({**order, "entry_t": int(w.now[0]) - 3})
    lines = [ln for _, ls in fake.files[k:] for ln in ls]
    check("weekend: Fri connected; DISCONNECTED Sat-Sun -> Mon 02:05 entry refused (and named by the startup check), no order "
          "file; NinjaTrader CONNECTED again -> the 02:06 entry goes in, nothing to tap or restart",
          ok_fri and not r1["ok"] and "DISCONNECTED" in r1["error"] and any("DISCONNECTED" in p for p in sp1)
          and r2["ok"] and any(";BUY;1;" in ln for ln in lines) and not any("DISCONNECTED" in p for p in ad.startup_problems()),
          (r1, sp1, r2))
    check("weekend: market_open False Saturday and Sunday before 18:00 ET (no FEED STALE, no stale block), True from Sun 18:00",
          sat == [False, False, True], sat)
    ad.send({"side": "exit", "reason": "x", "entry_t": int(w.now[0]) - 3})
    # 2. NinjaTrader restarted over the weekend while the bot is flat: its outgoing folder is wiped
    w2 = World()
    w2.now[0] = ts(2026, 10, 30, 16, 30)
    a2 = w2.make("wk2.json")
    w2.fake.move(25020.0)
    a2.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": int(w2.now[0]) - 3})
    a2.send({"side": "exit", "reason": "x", "entry_t": int(w2.now[0]) - 3})
    a2.tick()
    w2.now[0] = ts(2026, 10, 31, 10, 0)
    for f in glob.glob(os.path.join(w2.folder, "outgoing", "*")):
        os.remove(f)                                            # NinjaTrader's restart wipes outgoing\
    a2.tick()
    w2.fake._write("Tradovate.txt", "CONNECTED")
    w2.now[0] = ts(2026, 11, 2, 2, 5, 3)
    a2.tick()
    r3 = a2.send({"sym": "NQ", "side": "buy", "qty": 1, "stop": 24990.0, "target": 25100.0, "entry": 25020.0, "entry_t": int(w2.now[0]) - 3})
    check("NinjaTrader restarted over the weekend with the bot flat: no 'reset' block, Monday's entry goes in",
          a2.nt_reset is None and r3["ok"], (a2.nt_reset, r3))
    a2.send({"side": "exit", "reason": "x", "entry_t": int(w2.now[0]) - 3})


def t_disk(tmp):
    print("3. disk growth", flush=True)
    from engine import ops_checks as OC, pcbars
    L = os.path.join(tmp, "logs")
    nar = os.path.join(L, "narrator")
    os.makedirs(nar)
    now = time.time()
    for name, age_d in (("2026-10-28.jsonl", 0.2), ("2026-10-24.jsonl", 4), ("2026-06-01.jsonl.gz", 150), ("2026-08-01.jsonl.gz", 80)):
        p = os.path.join(nar, name)
        if name.endswith(".gz"):
            with gzip.open(p, "wb") as fh:
                fh.write(b"{}\n")
        else:
            open(p, "w").write('{"t": 1}\n')
        os.utime(p, (now - age_d * 86400,) * 2)
    r = OC.rotate_logs(L, now=now)
    have = sorted(os.listdir(nar))
    check("narrator feeds: today's kept, the 4-day-old one gzipped (readable), the 150-day-old .gz deleted, the 80-day-old kept",
          r.get("narrator", {}).get("gzipped") == 1 and r["narrator"]["deleted"] == 1
          and have == ["2026-08-01.jsonl.gz", "2026-10-24.jsonl.gz", "2026-10-28.jsonl"]
          and gzip.open(os.path.join(nar, "2026-10-24.jsonl.gz")).read() == b'{"t": 1}\n', (r, have))
    check("NinjaTrader bar archive capped (1m 40 days, 5m 120 days)", pcbars.ARCHIVE_KEEP_DAYS == {"1m": 40, "5m": 120})


def t_saves():
    print("4. state saves through fsutil.replace", flush=True)
    allow = {("ninjatrader.py", "os.replace(src, dst)"), ("ninjatrader.py", "os.replace(self.state_path, bad)"), ("fsutil.py", None)}
    hits = []
    for p in sorted(glob.glob(os.path.join(ROOT, "engine", "*.py"))):
        b = os.path.basename(p)
        if (b, None) in allow:
            continue
        for i, ln in enumerate(open(p, encoding="utf-8"), 1):
            code = ln.split("#", 1)[0]
            if re.search(r"\bos\.replace\(", code) and not any(b == a and s in ln for a, s in allow if s):
                hits.append(f"{b}:{i}")
    check("no engine module replaces a state file with a bare os.replace (Windows / OneDrive lock: fsutil.replace retries)",
          not hits, hits)


def t_actions(tmp):
    print("5. GitHub Actions minutes", flush=True)
    from engine import actions_budget as A
    t0 = int(ts(2026, 11, 3, 10, 0))
    s = {}
    for i in range(10):
        s = A.add_run(s, t0 + i * 1800, run_s=70, watch_min=0)
    e = A.estimate(s, t0 + 10 * 1800)
    check("estimate: 10 runs of 70 s = 10 x 2 billed minutes (each job rounds up, + setup) this month",
          e["month"] == "2026-11" and e["used_min"] == 20 and e["saver"] is False, e)
    big = {"month": "2026-11", "runs": 700, "min": 1500, "watch_min": 260}
    e2 = A.estimate(big, int(ts(2026, 11, 20, 10, 0)))
    check("saver mode at 85% of the 2,000 free minutes (1,760): on; the plain text says what is skipped and when it resets",
          e2["saver"] is True and "saver" in e2["text"].lower() and "Dec 1" in e2["text"], e2)
    e3 = A.estimate(big, int(ts(2026, 12, 1, 2, 0)))
    check("month rollover: Dec 1 starts at 0 minutes, saver off", e3["used_min"] == 0 and e3["saver"] is False, e3)
    keep = A.keep_run(int(ts(2026, 11, 20, 9, 32)), True)
    drop = A.keep_run(int(ts(2026, 11, 20, 12, 2)), True)
    night = A.keep_run(int(ts(2026, 11, 20, 1, 32)), True)
    check("saver: the night check (01:32) and the first run of each hour in the session stay; the extra half-hour runs and the "
          "midday ones go", keep is False and drop is False and night is True and A.keep_run(int(ts(2026, 11, 20, 9, 2)), True)
          and A.keep_run(int(ts(2026, 11, 20, 12, 2)), False), (keep, drop, night))
    # the workflow guard step: reads budget.json from the dashboard branch; anything unreadable -> runs as before
    bash = shutil.which("bash")
    if not bash or os.name == "nt":
        check("guard budget read: bash not available here: skipped", True)
        return
    import yaml
    wf = yaml.safe_load(open(os.path.join(ROOT, ".github", "workflows", "cloud-monitor.yml"), encoding="utf-8"))
    step = next(x for x in wf["jobs"]["monitor"]["steps"] if x.get("id") == "guard")
    script = step["run"]
    check("the guard step asks the dashboard branch's budget.json (curl, 10 s max, only on a GitHub runner: tests and local "
          "runs never call out) and only drops a run when saver is on for THIS month",
          "budget.json" in script and "--max-time" in script and "saver" in script and 'GITHUB_ACTIONS:-}" = "true"' in script)
    real_date = shutil.which("date")
    shim = os.path.join(tmp, "shim")
    os.makedirs(shim, exist_ok=True)
    open(os.path.join(shim, "date"), "w").write(f'#!/bin/sh\nexec "{real_date}" -d "@$FAKE_EPOCH" "$@"\n')
    open(os.path.join(shim, "curl"), "w").write('#!/bin/sh\nif [ -n "$FAKE_BUDGET" ]; then printf "%s" "$FAKE_BUDGET"; exit 0; fi\nexit 22\n')
    for f in ("date", "curl"):
        os.chmod(os.path.join(shim, f), 0o755)

    def go(t, budget, cron="2,32 6-21 * * 1-5"):
        s2 = script.replace("${{ github.event_name }}", "schedule").replace("${{ github.event.schedule }}", cron) \
            .replace("${{ github.repository }}", "owner/repo").replace("${{ github.token }}", "x")
        out = os.path.join(tmp, "gh_out")
        open(out, "w").close()
        env = {**os.environ, "PATH": shim + os.pathsep + os.environ["PATH"], "FAKE_EPOCH": str(int(t)), "GITHUB_OUTPUT": out,
               "FAKE_BUDGET": budget or "", "GITHUB_ACTIONS": "true"}
        subprocess.run([bash, "-e", "-c", s2], env=env, capture_output=True, text=True, timeout=20)
        return "go=1" in open(out).read()
    on = '{"month": "2026-11", "saver": true}'
    old = '{"month": "2026-10", "saver": true}'
    t_half, t_hour = ts(2026, 11, 20, 9, 32), ts(2026, 11, 20, 9, 2)
    res = [go(t_half, None), go(t_half, "not json"), go(t_half, old), go(t_half, on), go(t_hour, on), go(ts(2026, 11, 20, 1, 32), on)]
    check("guard: no file / bad file / last month's saver -> the 09:32 run goes as before; saver on this month -> 09:32 skipped, "
          "09:02 and the 01:32 night check still run", res == [True, True, True, False, True, True], res)


def t_credentials(tmp):
    print("6. GitHub login refused on the PC (heartbeat) / the PC's phone-push config", flush=True)
    from types import SimpleNamespace
    from engine import heartbeat as HB, push
    clock = [ts(2026, 11, 2, 9, 0)]
    sent = []
    hb = HB.Heartbeat(SimpleNamespace(running=True, cfg={}), push_fn=lambda pl, files=None: {"ok": False}, clock=lambda: clock[0],
                      log=lambda t: None, notify_fn=lambda title, body, key: sent.append((title, key)))
    auth = {"ok": False, "error": "remote: Invalid username or password. fatal: Authentication failed for 'https://github.com/x'"}
    for i in range(40):                                        # one failed push a minute for 40 min
        clock[0] = ts(2026, 11, 2, 9, 0) + 60 * i
        hb._note(auth)
    n1 = list(sent)
    clock[0] = ts(2026, 11, 2, 14, 0)
    hb._note(auth)
    hb2 = HB.Heartbeat(SimpleNamespace(running=True, cfg={}), push_fn=lambda pl, files=None: {"ok": False}, clock=lambda: clock[0],
                       log=lambda t: None, notify_fn=lambda title, body, key: sent.append((title, key)))
    for i in range(40):
        clock[0] = ts(2026, 11, 3, 9, 0) + 60 * i
        hb2._note({"ok": False, "error": "fatal: unable to access 'https://github.com/x/': Could not resolve host: github.com"})
    hb3 = HB.Heartbeat(SimpleNamespace(running=True, cfg={}), push_fn=lambda pl, files=None: {"ok": False}, log=lambda t: None)
    check("heartbeat: GitHub refusing the login for 30 min -> one phone push 'Surface can't upload to GitHub' a day (the bot "
          "keeps trading); a network error -> none (the cloud's alarm covers it); a test's fake push never notifies",
          len(n1) == 1 and n1[0][0] == "Surface can't upload to GitHub" and len(sent) == 1 and hb3.notify_fn is None, sent)
    # the PC's push config: a failed fetch keeps the last good answer (memory, then the file) and asks again in 2 min
    keep = dict(push._PC)
    try:
        pc_key = os.path.join(tmp, "pc_key.json")
        cache = os.path.join(tmp, "push_pc_sync.json")
        priv, pub = push.pc_keypair() if hasattr(push, "pc_keypair") else (None, None)
        st = {"push_subs": [{"sub": {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}}}]}
        if priv:
            open(pc_key, "w").write(json.dumps({"private": priv}))
        ok = push.pc_sync(force=True, fetch=lambda: st, key_path=pc_key, cache_path=cache)

        def boom():
            raise RuntimeError("fatal: Authentication failed")
        bad = push.pc_sync(force=True, fetch=boom, key_path=pc_key, cache_path=cache)
        retry_in = push.SYNC_EVERY_S - (time.time() - push._PC["sync_t"])
        push._PC.pop("good", None)                             # a restart: nothing in memory, the file is there
        bad2 = push.pc_sync(force=True, fetch=boom, key_path=pc_key, cache_path=cache)
        check("PC push config: a failed GitHub fetch keeps the phones (last good: this process, then data/push_pc_sync.json "
              "after a restart) and tries again in ~2 min (was: nothing for 20 min)",
              ok["subs"] and bad["subs"] == ok["subs"] and bad.get("stale") and bad2["subs"] == ok["subs"] and 0 < retry_in <= 130,
              (ok, bad, bad2, retry_in))
    finally:
        push._PC.clear()
        push._PC.update(keep)


def main():
    tmp = tempfile.mkdtemp(prefix="le_selfheal_")
    try:
        t_weekend()
        t_disk(tmp)
        t_saves()
        t_actions(tmp)
        t_credentials(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"self-heal: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
