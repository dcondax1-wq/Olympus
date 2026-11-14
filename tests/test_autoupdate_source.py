"""The PC updates itself from the backup repo (owner 2026-11-14: "keep it on GitHub in case we get banned ... I'm not
updating the files every time"). engine/autoupdate.py: update_source.json, the one-time --connect (any folder state ->
exactly the backup's newest commit, put back on any failure), GitHub-free mode blocking only origin, and an eval without
auto-resume updating only in Friday's halt. Real git in temp folders; no network.

    python -X utf8 -m tests.test_autoupdate_source
"""
from __future__ import annotations

import datetime as dt
import json
import os
import socket
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import autoupdate as au  # noqa: E402

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:300]})" if info and not cond else ""))


def ts(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp()


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def write(base, rel, text):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p) or base, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read(base, rel):
    try:
        with open(os.path.join(base, rel), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def files(base):
    """{rel: content} of every file outside .git (what the owner's folder looks like)."""
    out = {}
    for r, ds, fs in os.walk(base):
        ds[:] = [d for d in ds if d != ".git"]
        for f in fs:
            p = os.path.join(r, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, base).replace(os.sep, "/")] = fh.read()
    return out


def model(room):
    return json.dumps({"lit_sizing": {"two_week": {"room_f": room}, "two_week_until": 80 if room == 0.4 else 10}}, indent=1) + "\n"


OK_T = [["-c", "import sys; sys.exit(0)"]]
BAD_T = [["-c", "import sys; sys.exit(3)"]]


def plain_fetch(sh, src):
    c, out = sh.git("fetch", "-q", src["remote"], src["branch"])
    return c, ("" if c == 0 else out.strip()[-80:])


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_ausrc_")
    au.LOG_DIR = os.path.join(tmp, "logs")
    os.environ["LE_AUTOUPDATE_LOCAL_OK"] = "1"           # the test's backup repo is a local folder, not https://
    said = []

    def say(kind, text):
        said.append((kind, text))

    # ---------------------------------------------------------------------- update_source.json
    with open(os.path.join(ROOT, "update_source.json"), encoding="utf-8") as f:
        mine = json.load(f)
    s_repo = au.source(ROOT, env={})
    check("repo: update_source.json names the backup remote 'olympus', branch 'pc', an https URL",
          s_repo["remote"] == "olympus" and s_repo["branch"] == "pc" and s_repo["url"].startswith("https://github.com/") is False
          and s_repo["url"].startswith("https://"), s_repo)
    user = mine["url"].split("://", 1)[1].split("@", 1)[0]
    check("repo: the URL carries the account the owner signs in with (Git Credential Manager picks that account)",
          user == mine.get("account") and mine["url"].endswith(f"/{user}/olympus.git"), mine["url"])
    check("repo: no password or token in the URL (only the user name before @)",
          ":" not in mine["url"].split("://", 1)[1].split("@", 1)[0] and not any(t in mine["url"] for t in ("ghp_", "github_pat_", "gho_")))
    check("label: 'account/repo (branch)', no user@ part", s_repo["label"] == f"{user}/olympus (pc)" and "@" not in s_repo["label"], s_repo["label"])
    empty = os.path.join(tmp, "nosrc")
    os.makedirs(empty)
    check("no update_source.json: origin/main as before", au.source(empty, env={})["remote"] == "origin"
          and au.source(empty, env={})["branch"] == "main")
    check("LE_UPDATE_SOURCE=origin: origin/main", au.source(ROOT, env={"LE_UPDATE_SOURCE": "origin"})["remote"] == "origin")
    bad = os.path.join(tmp, "badsrc")
    os.makedirs(bad)
    for name, body in (("http", {"remote": "olympus", "url": "http://x/y.git", "branch": "pc"}),
                       ("space", {"remote": "olympus", "url": "https://x/y z.git", "branch": "pc"}),
                       ("origin", {"remote": "origin", "url": "https://x/y.git", "branch": "pc"}),
                       ("dots", {"remote": "olympus", "url": "https://x/y.git", "branch": "../pc"}),
                       ("junk", "not json")):
        write(bad, "update_source.json", body if isinstance(body, str) else json.dumps(body))
        check(f"a bad update_source.json ({name}) falls back to origin", au.source(bad, env={})["remote"] == "origin")

    # ---------------------------------------------------------------------- GitHub-free mode blocks only origin
    check("GitHub-free mode + no backup source: auto-update off (as before)",
          au.is_enabled({"enabled": True}, {"LE_NO_GITHUB": "1"}, empty) is False)
    check("GitHub-free mode + the backup source: auto-update ON", au.is_enabled({"enabled": True}, {"LE_NO_GITHUB": "1"}, ROOT) is True)
    check("LE_AUTOUPDATE=0 still turns it off", au.is_enabled({"enabled": True}, {"LE_AUTOUPDATE": "0"}, ROOT) is False)
    check("not enabled: off", au.is_enabled({}, {}, ROOT) is False)

    # ---------------------------------------------------------------------- an eval without auto-resume: Friday only
    tue, fri = ts(2026, 11, 17, 17, 10), ts(2026, 11, 20, 17, 10)
    why = "a real-account bot without auto-resume: waits for the 17:02 ET halt check"
    check("live_wait_reason: an eval on a Tuesday waits for Friday", "Friday" in (au.live_wait_reason(tue, why) or ""))
    check("live_wait_reason: Friday goes", au.live_wait_reason(fri, why) is None)
    check("live_wait_reason: paper / Sim / auto-resume (no reason) goes any day", au.live_wait_reason(tue, None) is None)

    class Bot:
        running, state, cfg = True, {}, {}

    calls = []
    real_rs, real_ru, real_flat = au.restart_safe_reason, au.run_update, au.bot_flat_reason
    sp = os.path.join(tmp, "daily_state.json")
    au.save_state({"enabled": True}, sp)
    try:
        au.bot_flat_reason = lambda bot: None
        au.run_update = lambda *a, **k: calls.append(a[1]) or {"status": "up_to_date", "reason": "x", "t": a[2], "mode": a[1]}
        au.restart_safe_reason = lambda bot, optin=None: why
        up = au.DailyUpdater(Bot(), clock=lambda: tue, state_path=sp)
        r = up.check_once(tue, optin={})
        check("daily check, eval without auto-resume, Tuesday: skipped, no update run",
              r and r["status"] == "skipped" and "Friday" in r["reason"] and not calls, r)
        r = au.DailyUpdater(Bot(), clock=lambda: fri, state_path=sp).check_once(fri, optin={})
        check("daily check, same bot, Friday 17:10 ET: the update runs", calls == ["daily"], (r, calls))
        au.restart_safe_reason = lambda bot, optin=None: None
        calls.clear()
        au.save_state({"enabled": True}, sp)
        au.DailyUpdater(Bot(), clock=lambda: tue, state_path=sp).check_once(tue, optin={})
        check("daily check, paper / Sim / auto-resume bot, Tuesday: runs as before", calls == ["daily"], calls)
    finally:
        au.restart_safe_reason, au.run_update, au.bot_flat_reason = real_rs, real_ru, real_flat

    # ---------------------------------------------------------------------- real git: the backup repo and its history
    dev, backup = os.path.join(tmp, "dev"), os.path.join(tmp, "backup.git")
    subprocess.run(["git", "init", "-q", "-b", "main", dev], check=True)
    git(dev, "config", "user.email", "t@t"); git(dev, "config", "user.name", "t")
    src_json = json.dumps({"remote": "olympus", "url": backup, "branch": "pc", "account": "acct"})
    write(dev, ".gitignore", "data/live_state.json\nlogs/\n")
    write(dev, "update_source.json", src_json)
    write(dev, "live_model.json", model(0.8))
    write(dev, "second_model.json", "{}\n")
    write(dev, "a.txt", "1\n")
    write(dev, "old.txt", "old\n")
    write(dev, "requirements.txt", "x\n")
    git(dev, "add", "-A"); git(dev, "commit", "-qm", "c1")
    c1 = git(dev, "rev-parse", "HEAD")
    write(dev, "live_model.json", model(0.4))               # the owner's 40% (repo change, 2026-11-14)
    write(dev, "a.txt", "2\n")
    write(dev, "b.txt", "new\n")
    os.remove(os.path.join(dev, "old.txt"))
    git(dev, "add", "-A"); git(dev, "commit", "-qm", "c2")
    c2 = git(dev, "rev-parse", "HEAD")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", backup], check=True)
    git(dev, "remote", "add", "bk", backup)
    git(dev, "push", "-q", "bk", f"{c2}:refs/heads/pc")
    SRC = {"remote": "olympus", "url": backup, "branch": "pc", "account": "acct", "label": "acct/backup (pc)"}

    def zip_applied(name, hand_edit=None, with_git=True):
        """A PC folder after code zips: an old clone at c1 (origin gone) with c2's files copied over it, except
        live_model.json (the zip updater kept the old one), old.txt still there (zips never delete), local data."""
        pc = os.path.join(tmp, name)
        subprocess.run(["git", "clone", "-q", dev, pc], check=True, capture_output=True)
        git(pc, "checkout", "-q", "-B", "main", c1)
        git(pc, "remote", "set-url", "origin", os.path.join(tmp, "gone.git"))
        write(pc, "a.txt", hand_edit or "2\n")
        write(pc, "b.txt", "new\n")
        write(pc, "data/live_state.json", json.dumps({"saved_at": 0}))
        write(pc, "notes.txt", "the owner's own file\n")
        if not with_git:
            au._rmtree(os.path.join(pc, ".git"))
        return pc

    def connect(pc, **kw):
        said.clear()
        kw.setdefault("tests", OK_T)
        return au.connect(au.Shell(pc), src=SRC, fetch=kw.pop("fetch", plain_fetch), port=kw.pop("port", 0),
                          state_path=kw.pop("state_path", os.path.join(pc, "data", "autoupdate.json")), say=say, pip=False, **kw)

    # A: the usual PC (zip-applied old clone)
    pc = zip_applied("pc_a")
    rc = connect(pc)
    st = au.load_state(os.path.join(pc, "data", "autoupdate.json"))
    check("connect (zip-applied clone): exit 0, the folder is exactly the backup's newest commit",
          rc == 0 and git(pc, "rev-parse", "HEAD") == c2 and git(pc, "status", "--porcelain", "--untracked-files=no") == "", (rc, said))
    check("connect: the owner's 40% reaches the PC (live_model.json the zip had kept is now the repo's)",
          json.loads(read(pc, "live_model.json"))["lit_sizing"]["two_week"]["room_f"] == 0.4)
    check("connect: a file the repo deleted goes (old.txt), a new one is there (b.txt)",
          read(pc, "old.txt") is None and read(pc, "b.txt") == "new\n")
    check("connect: local files stay (gitignored bot state, the owner's own untracked file)",
          read(pc, "data/live_state.json") == json.dumps({"saved_at": 0}) and read(pc, "notes.txt") == "the owner's own file\n")
    check("connect: auto-update ON, connect record names the backup", st.get("enabled") is True
          and (st.get("connected") or {}).get("url") == backup and st["connected"]["sha"] == c2, st)
    check("connect: branch main tracks olympus/pc, the snapshot ref is kept",
          git(pc, "rev-parse", "--abbrev-ref", "main@{upstream}") == "olympus/pc"
          and len(git(pc, "rev-parse", au.SNAPSHOT_REF)) == 40)
    check("connect: no copies when every file was a known repo version", not st["connected"].get("copies")
          and not os.path.exists(os.path.join(pc, "logs")), st["connected"])
    check("connect: says ON in plain words", any(k == "OK" and "Auto-update is ON" in t for k, t in said), said)
    check("source_status after connect: 0", au.source_status(pc, au.Shell(pc), st, env={"LE_AUTOUPDATE_LOCAL_OK": "1"})[0] == 0)
    rc = connect(pc)
    check("connect again: exit 0, 'already runs the newest code', nothing moved",
          rc == 0 and git(pc, "rev-parse", "HEAD") == c2 and any("already runs" in t for _k, t in said), said)

    # normal updates from the backup afterwards, in GitHub-free mode too
    write(dev, "a.txt", "3\n")
    git(dev, "commit", "-qam", "c3")
    c3 = git(dev, "rev-parse", "HEAD")
    git(dev, "push", "-q", "bk", f"{c3}:refs/heads/pc")
    evening = ts(2026, 11, 17, 20, 0)
    r = au.run_update(au.Shell(pc), "start", evening, None, state={"enabled": True}, tests=OK_T, env={"LE_NO_GITHUB": "1", "LE_AUTOUPDATE_LOCAL_OK": "1"})
    check("after connect: a new push to olympus/pc fast-forwards the PC (GitHub-free mode on)",
          r["status"] == "updated" and git(pc, "rev-parse", "HEAD") == c3 and read(pc, "a.txt") == "3\n", r)
    write(pc, "a.txt", "hand edit\n")
    write(dev, "a.txt", "4\n")
    git(dev, "commit", "-qam", "c4")
    git(dev, "push", "-q", "bk", "HEAD:refs/heads/pc")
    r = au.run_update(au.Shell(pc), "start", evening, None, state={"enabled": True}, tests=OK_T, env={"LE_NO_GITHUB": "1", "LE_AUTOUPDATE_LOCAL_OK": "1"})
    check("after connect: a hand edit still blocks the automatic update (only the one-time connect replaces files)",
          r["status"] == "skipped" and "local changes" in r["reason"] and read(pc, "a.txt") == "hand edit\n", r)
    git(pc, "checkout", "--", "a.txt")
    r = au.run_update(au.Shell(pc), "start", ts(2026, 11, 17, 10, 0), None, state={"enabled": True}, tests=OK_T, env={})
    check("after connect: never during trading hours", r["status"] == "skipped" and "trading hours" in r["reason"], r)

    # B: a hand-edited file is copied to logs/connect-*/ before the move
    pc = zip_applied("pc_b", hand_edit="my own edit\n")
    git(dev, "push", "-q", "-f", "bk", f"{c2}:refs/heads/pc")
    rc = connect(pc)
    st = au.load_state(os.path.join(pc, "data", "autoupdate.json"))
    cp = (st.get("connected") or {}).get("copies")
    check("connect: a file that is no repo version (a hand edit) is copied first, then replaced",
          rc == 0 and cp and read(pc, os.path.join(cp, "a.txt")) == "my own edit\n" and read(pc, "a.txt") == "2\n", (rc, cp, said))
    check("connect: the copy is named in plain words", any("a copy of each is in" in t for _k, t in said), said)

    # C: a copied folder without .git
    pc = zip_applied("pc_c", with_git=False)
    rc = connect(pc)
    check("connect (no .git: a copied folder): exit 0, git made, HEAD = the backup's newest, 40% in, local files kept",
          rc == 0 and git(pc, "rev-parse", "HEAD") == c2 and json.loads(read(pc, "live_model.json"))["lit_sizing"]["two_week"]["room_f"] == 0.4
          and read(pc, "notes.txt") == "the owner's own file\n"
          and git(pc, "status", "--porcelain", "--untracked-files=no") == "", (rc, said))
    check("connect (no .git): a file git never tracked here is never deleted (old.txt stays, untracked, like the zip updater)",
          read(pc, "old.txt") == "old\n" and "old.txt" in git(pc, "status", "--porcelain"))

    # D: a failing self-test puts everything back exactly as it was
    for name, with_git in (("pc_d", True), ("pc_d2", False)):
        pc = zip_applied(name, with_git=with_git)
        before = files(pc)
        head = git(pc, "rev-parse", "HEAD") if with_git else None
        stat = git(pc, "status", "--porcelain") if with_git else None
        rc = connect(pc, tests=BAD_T)
        same = files(pc) == before
        if with_git:
            ok = same and git(pc, "rev-parse", "HEAD") == head and git(pc, "status", "--porcelain") == stat
        else:
            ok = same and not os.path.exists(os.path.join(pc, ".git"))
        check(f"connect, self-test fails ({'clone' if with_git else 'no .git'}): exit 1, every file / HEAD / git state as before",
              rc == 1 and ok, (rc, said, sorted(set(files(pc)) ^ set(before))))
        check(f"connect, self-test fails ({'clone' if with_git else 'no .git'}): auto-update not turned on",
              not au.load_state(os.path.join(pc, "data", "autoupdate.json")).get("enabled"))

    # E: the backup cannot be reached (sign-in cancelled, no internet)
    for name, with_git in (("pc_e", True), ("pc_e2", False)):
        pc = zip_applied(name, with_git=with_git)
        before = files(pc)
        rc = connect(pc, fetch=lambda sh, src: (128, "authentication failed"))
        gone = (subprocess.run(["git", "remote", "get-url", "olympus"], cwd=pc, capture_output=True).returncode != 0) if with_git \
            else not os.path.exists(os.path.join(pc, ".git"))
        check(f"connect, backup unreachable ({'clone' if with_git else 'no .git'}): exit 20, nothing changed, remote / .git undone",
              rc == 20 and files(pc) == before and gone, (rc, said))
    check("connect, unreachable: the line says to sign in as the account and that the zip way still works",
          any(k == "SKIP" and "sign in as acct" in t and "zip way still works" in t for k, t in said), said)

    # F / G: never while the bot server runs or a trade is open
    pc = zip_applied("pc_f")
    before = files(pc)
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    rc = connect(pc, port=srv.getsockname()[1])
    srv.close()
    check("connect while the bot server answers: exit 21, nothing changed", rc == 21 and files(pc) == before, said)
    write(pc, "data/live_state.json", json.dumps({"saved_at": __import__("time").time(), "open_routed": {"side": "long"}}))
    before = files(pc)
    rc = connect(pc)
    check("connect with a trade open: exit 21, nothing changed", rc == 21 and files(pc) == before, said)

    # source_status / CLI
    pc = zip_applied("pc_s")
    check("source_status before connect: 10", au.source_status(pc, au.Shell(pc), {}, env={"LE_AUTOUPDATE_LOCAL_OK": "1"})[0] == 10)
    check("source_status without update_source.json: 10", au.source_status(empty, au.Shell(empty), {"enabled": True}, env={})[0] == 10)
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "engine.autoupdate", "--source-status"], cwd=ROOT,
                       capture_output=True, text=True, timeout=120,
                       env={**os.environ, "LE_AUTOUPDATE_LOCAL_OK": "0"})
    check("CLI --source-status runs (this cloud checkout is not connected: 10)", r.returncode in (0, 10) and "Auto-update" in r.stdout,
          (r.returncode, r.stdout[-200:], r.stderr[-300:]))
    v = au.version(ROOT)
    check("version() names the source, no user@ part", "@" not in str(v.get("source")) and "olympus" in str(v.get("source")), v)

    n, ok = len(RESULTS), sum(RESULTS)
    print(f"autoupdate_source: {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
