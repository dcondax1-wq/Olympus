"""Kalshi in Jarvis (engine/kalshi_publish.py, owner 2026-11-01): the PC's Kalshi status file -> kalshi.json on the branch
`kalshi` of the Pages repo, which the Kalshi page (tools/web_public/kalshi/) and the Jarvis card read. Checks:
  a. clean(): only the contract's keys leave the PC, secrets dropped, local paths redacted, numbers as numbers, lists capped,
     junk never raises
  b. read(): missing / broken / non-object files give an error, a file without "t" takes the file's time, oversize is trimmed
  c. push_once(): one orphan commit on refs/heads/kalshi of a local bare repo holding exactly kalshi.json (replaced on the next
     push, no history); the real live.json push keeps its file name
  d. loop(): pushes when the file changed, keeps quiet when it did not (until the keep-alive), waits while the file is missing
    python -X utf8 -m tests.test_kalshi_publish      (temp folders only; nothing else touched)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import kalshi_publish as kp  # noqa: E402
from engine import live_publish as lp  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def part_a():
    raw = {**kp.SAMPLE, "api_key": "sk-123", "private_key_path": "C:\\Users\\me\\kalshi.pem", "secret": "x", "extra": {"a": 1},
           "status": "log at C:\\Users\\me\\bot\\log.txt", "balance": "512.34",
           "positions": [{**kp.SAMPLE["positions"][0], "token": "t", "contracts": "10"}] * 100,
           "trades": [kp.SAMPLE["trades"][0]] * 100, "days": [["2026-10-01", 1.0]] * 300}
    c = kp.clean(raw, now=1793548900)
    s = json.dumps(c)
    check("a. only the contract's keys (no api_key / private key / secret / unknown keys)",
          set(c) == set(kp.TOP) | {"v", "kind", "positions", "trades", "days", "pub_t"} and "sk-123" not in s and "token" not in s, sorted(c))
    check("a. local paths redacted", "Users" not in s and "<path>" in c["status"], c["status"])
    check("a. numbers as numbers", c["balance"] == 512.34 and c["positions"][0]["contracts"] == 10.0 and c["kind"] == "kalshi" and c["v"] == 1, c["balance"])
    check("a. lists capped (positions 60, trades 40, days 120)", (len(c["positions"]), len(c["trades"]), len(c["days"])) == (60, 40, 120))
    check("a. the sample keeps its numbers", c["today_pnl"] == 18.5 and c["running"] is True and c["mode"] == "paper" and c["t"] == kp.SAMPLE["t"])
    j = kp.clean("junk", now=5)
    check("a. junk input never raises (an empty card)", j["kind"] == "kalshi" and j["positions"] == [] and j["t"] == 5, j)
    d = kp.clean({"days": [{"day": "2026-10-30", "pnl": "2.5"}, ["2026-10-31", "x"], "bad"]}, now=5)
    check("a. days as [day, pnl] pairs or {day, pnl}; bad rows dropped", d["days"] == [["2026-10-30", 2.5]], d["days"])


def part_b(tmp):
    p, err = kp.read(os.path.join(tmp, "missing.json"))
    check("b. missing file -> error, no payload", p is None and "not found" in err, err)
    bad = os.path.join(tmp, "bad.json")
    open(bad, "w").write("{nope")
    check("b. broken JSON -> error", kp.read(bad)[1].startswith("status file is not JSON"))
    lst = os.path.join(tmp, "list.json")
    open(lst, "w").write("[1, 2]")
    check("b. not an object -> error", kp.read(lst)[1] == "status file is not a JSON object")
    f = os.path.join(tmp, "s.json")
    json.dump({k: v for k, v in kp.SAMPLE.items() if k != "t"}, open(f, "w"))
    os.utime(f, (1793500000, 1793500000))
    p, err = kp.read(f)
    check("b. no 't' in the file -> the file's time", err is None and p["t"] == 1793500000, p and p["t"])
    big = os.path.join(tmp, "big.json")
    json.dump({**kp.SAMPLE, "trades": [{**kp.SAMPLE["trades"][0], "title": "x" * 150}] * 40,
               "positions": [{**kp.SAMPLE["positions"][0], "title": "y" * 150}] * 60}, open(big, "w"))
    old = kp.MAX_BYTES
    kp.MAX_BYTES = 8 * 1024
    try:
        p, err = kp.read(big)
    finally:
        kp.MAX_BYTES = old
    check("b. over the size limit -> trimmed (trades first) until it fits",
          err is None and len(json.dumps(p, separators=(",", ":"))) <= 8 * 1024 and len(p["trades"]) < 40, p and len(p["trades"]))


def git(*a, cwd=None):
    return subprocess.run(["git", *a], capture_output=True, text=True, cwd=cwd)


def part_c(tmp):
    remote = os.path.join(tmp, "remote.git")
    git("init", "-q", "--bare", remote)
    f = os.path.join(tmp, "status.json")
    json.dump(kp.SAMPLE, open(f, "w"))
    scratch = os.path.join(tmp, "scratch.git")
    r = kp.push_once(f, url=remote, git_dir=scratch)
    show = git("--git-dir", remote, "ls-tree", "--name-only", "kalshi")
    body = git("--git-dir", remote, "show", "kalshi:kalshi.json").stdout
    check("c. one push: the branch `kalshi` holds exactly kalshi.json", r.get("ok") and show.stdout.split() == ["kalshi.json"], (r, show.stdout, show.stderr))
    check("c. its content is the cleaned status (balance, positions)", json.loads(body or "{}").get("balance") == 512.34
          and len(json.loads(body or "{}").get("positions", [])) == 1, body[:200])
    json.dump({**kp.SAMPLE, "balance": 600}, open(f, "w"))
    r2 = kp.push_once(f, url=remote, git_dir=scratch)
    n = git("--git-dir", remote, "rev-list", "--count", "kalshi").stdout.strip()
    check("c. the next push replaces it (orphan commit, no history)", r2.get("ok") and n == "1"
          and json.loads(git("--git-dir", remote, "show", "kalshi:kalshi.json").stdout)["balance"] == 600, (r2, n))
    r3 = kp.push_once(os.path.join(tmp, "nope.json"), url=remote, git_dir=scratch)
    check("c. a missing status file pushes nothing", not r3["ok"] and "not found" in r3["error"], r3)
    r4 = lp.push({"t": 1}, remote, branch="live", git_dir=os.path.join(tmp, "live.git"))
    check("c. live.json's own push keeps its file name (file= defaults to live.json)",
          r4.get("ok") and git("--git-dir", remote, "ls-tree", "--name-only", "live").stdout.split() == ["live.json"], r4)


def part_d(tmp):
    f = os.path.join(tmp, "loop.json")
    calls, logs, t, rounds = [], [], [1000.0], [0]

    def fake_push(p, url, **kw):
        calls.append((p["balance"], kw.get("branch"), kw.get("file")))
        return {"ok": True, "commit": "abc"}

    def sleep(s):
        t[0] += s
        rounds[0] += 1
        if rounds[0] == 2:                                   # after round 2: the file shows up (pushed in round 3)
            json.dump(kp.SAMPLE, open(f, "w"))
        if rounds[0] == 4:                                   # after round 4: the Kalshi bot writes a new balance (round 5)
            json.dump({**kp.SAMPLE, "balance": 700}, open(f, "w"))
            os.utime(f, (t[0] + 5, t[0] + 5))
    kp.loop(f, every=60, keepalive=600, log=logs.append, clock=lambda: t[0], sleep=sleep, push_fn=fake_push, url="x",
            git_dir=os.path.join(tmp, "s.git"), max_rounds=16)
    check("d. waits while the status file is missing", logs[:2] == ["kalshi publish: waiting for the status file"] * 2, logs[:3])
    check("d. pushes on the file's first appearance and on a change, to branch kalshi as kalshi.json",
          calls[:2] == [(512.34, "kalshi", "kalshi.json"), (700.0, "kalshi", "kalshi.json")], calls)
    check("d. no push while unchanged, then a keep-alive push after 10 min", len(calls) == 3, calls)


def main():
    tmp = tempfile.mkdtemp(prefix="le_kalshi_")
    try:
        part_a()
        part_b(tmp)
        part_c(tmp)
        part_d(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nkalshi publish: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
