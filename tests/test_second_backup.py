"""Second backup: tools/second_backup.py (git mirror on Codeberg / GitLab + the weekly zip to a synced folder), tools/bat/BACKUP_SETUP.bat,
scripts/backup_task.ps1 (the Sunday task). Temp git repos, a local bare repo as the "mirror", fake HTTP for the hosts' API and
ntfy; never the real network, never the real Task Scheduler (LE_BB_T_LOG), never the owner's settings folder.

  python -X utf8 -m tests.test_second_backup
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ["LE_PR_NO_NET"] = "1"

from tools import second_backup as SB  # noqa: E402

RES: list = []
TOKEN = "tok_ABCdef1234567890secret"


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:700]})" if info and not cond else ""))
    return bool(cond)


def sh(args, cwd):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


class Fake:
    """Fake HTTP: the hosts' repository API and ntfy.sh."""

    def __init__(self, codeberg=(200, {"private": True}), gitlab=(200, {"visibility": "private"})):
        self.codeberg, self.gitlab, self.calls = codeberg, gitlab, []

    def __call__(self, method, url, body=None, headers=None, timeout=15):
        self.calls.append({"m": method, "url": url, "h": dict(headers or {}), "body": body.decode() if isinstance(body, bytes) else body})
        if url.startswith("https://codeberg.org/api/"):
            return self.codeberg[0], json.dumps(self.codeberg[1])
        if url.startswith("https://gitlab.com/api/"):
            return self.gitlab[0], json.dumps(self.gitlab[1])
        if url.startswith("https://ntfy.sh/"):
            return 200, "{}"
        return 0, "unexpected"

    def ntfy(self):
        return [c for c in self.calls if c["url"].startswith("https://ntfy.sh/")]


class Box:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="sb_", dir=os.environ.get("LE_TEST_TMP") or None)
        self.repo = os.path.join(self.dir, "bot")
        self.home = os.path.join(self.dir, "home")
        self.sync = os.path.join(self.dir, "OneDrive")
        self.mirror = os.path.join(self.dir, "mirror.git")
        os.makedirs(self.repo)
        os.makedirs(self.sync)
        sh(["init", "-q", "-b", "main"], self.repo)
        with open(os.path.join(self.repo, ".gitignore"), "w") as fh:
            fh.write("data/alerts.json\nlogs/\n")
        os.makedirs(os.path.join(self.repo, "engine"))
        with open(os.path.join(self.repo, "engine", "lit.py"), "w") as fh:
            fh.write("V = 1\n")
        sh(["add", "-A"], self.repo)
        sh(["commit", "-q", "-m", "first"], self.repo)
        sh(["tag", "v1"], self.repo)
        subprocess.run(["git", "init", "-q", "--bare", self.mirror], check=True, capture_output=True)
        self.env = {"OLYMPUS_HOME": self.home, "USERPROFILE": self.dir}
        self._old = {}

    def __enter__(self):
        for k, v in self.env.items():
            self._old[k] = os.environ.get(k)
            os.environ[k] = v
        return self

    def __exit__(self, *a):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)


# ============================================================================================== url + setup
def setup_checks():
    ok = SB.parse_url("https://codeberg.org/demo/olympus")
    check("url: https Codeberg address -> .git added, owner / repo", ok == {"url": "https://codeberg.org/demo/olympus.git", "host": "codeberg.org",
                                                                          "owner": "demo", "repo": "olympus", "path": "demo/olympus"}, ok)
    gl = SB.parse_url("https://gitlab.com/group/sub/olympus.git")
    check("url: GitLab subgroup kept whole", gl["path"] == "group/sub/olympus" and gl["repo"] == "olympus", gl)
    for bad in ("http://codeberg.org/a/b", "git@codeberg.org:a/b.git", "https://codeberg.org/onlyowner", f"https://me:{TOKEN}@codeberg.org/a/b.git"):
        check(f"url: refused: {bad[:40]}", "error" in SB.parse_url(bad), SB.parse_url(bad))
    with Box() as b:
        out = []
        answers = iter(["https://codeberg.org/demo/olympus", ""])
        http = Fake()
        rc = SB.setup(ask=lambda p: next(answers), ask_secret=lambda p: TOKEN, http=http, say=out.append, root=ROOT)
        p = SB.cfg_path()
        cfg = json.load(open(p))
        check("setup: saved outside the bot folder, file mode 600, url / owner / token / user", rc == 0 and not SB.inside(p, ROOT)
              and (os.name == "nt" or stat.S_IMODE(os.stat(p).st_mode) == 0o600) and cfg["url"] == "https://codeberg.org/demo/olympus.git"
              and cfg["token"] == TOKEN and cfg["user"] == "demo", (rc, out, cfg))
        check("setup: the token is never printed", not any(TOKEN in x for x in out), out)
        check("setup: asks Codeberg whether the repository is private, with the token in a header (never in the URL)",
              http.calls and http.calls[0]["url"] == "https://codeberg.org/api/v1/repos/demo/olympus"
              and http.calls[0]["h"].get("Authorization") == f"token {TOKEN}" and TOKEN not in http.calls[0]["url"], http.calls)
        answers = iter(["", b.sync])
        rc = SB.setup(ask=lambda p: next(answers), ask_secret=lambda p: "", http=Fake(), say=out.append, root=ROOT)
        cfg = json.load(open(p))
        check("setup again: Enter keeps the address and the token; the zip folder set", rc == 0 and cfg["token"] == TOKEN and cfg["backup_dir"] == b.sync, cfg)
        out.clear()
        answers = iter(["https://codeberg.org/demo/public-one", ""])
        rc = SB.setup(ask=lambda p: next(answers), ask_secret=lambda p: TOKEN, http=Fake(codeberg=(200, {"private": False})), say=out.append, root=ROOT)
        check("setup: a PUBLIC repository is refused, nothing saved", rc == 1 and any("PUBLIC" in x for x in out)
              and json.load(open(p))["url"].endswith("/olympus.git"), out)
        out.clear()
        answers = iter(["https://gitlab.com/demo/missing", ""])
        rc = SB.setup(ask=lambda p: next(answers), ask_secret=lambda p: TOKEN, http=Fake(gitlab=(404, {})), say=out.append, root=ROOT)
        check("setup: a missing GitLab project -> 'create it, empty and private', nothing saved", rc == 1 and any("create it" in x for x in out), out)
        out.clear()
        answers = iter(["https://codeberg.org/demo/olympus", os.path.join(ROOT, "backups")])
        rc = SB.setup(ask=lambda p: next(answers), ask_secret=lambda p: TOKEN, http=Fake(), say=out.append, root=ROOT)
        check("setup: a zip folder inside the bot folder is refused", rc == 1 and any("outside the bot folder" in x for x in out), out)
        os.environ["OLYMPUS_HOME"] = os.path.join(ROOT, "data", "sb_test_home")
        try:
            try:
                SB.save({"x": 1}, root=ROOT)
                inside_ok = False
            except RuntimeError:
                inside_ok = True
            check("settings are never saved inside the repo", inside_ok and not os.path.exists(os.path.join(ROOT, "data", "sb_test_home")))
        finally:
            os.environ["OLYMPUS_HOME"] = b.home
            shutil.rmtree(os.path.join(ROOT, "data", "sb_test_home"), ignore_errors=True)
        os.makedirs(os.path.join(b.dir, "OneDrive"), exist_ok=True)
        cands = SB.synced_candidates({"OneDrive": b.sync, "USERPROFILE": b.dir})
        check("synced folders: OneDrive found (env OneDrive)", cands and cands[0] == ("OneDrive", b.sync), cands)


# ============================================================================================== snapshot
def snapshot_checks():
    with Box() as b:
        r = b.repo
        with open(os.path.join(r, "engine", "lit.py"), "w") as fh:
            fh.write("V = 2  # updated by zip\n")
        with open(os.path.join(r, "engine", "new_tool.py"), "w") as fh:
            fh.write("X = 1\n")
        os.makedirs(os.path.join(r, "data"))
        with open(os.path.join(r, "data", "alerts.json"), "w") as fh:
            fh.write('{"telegram_token": "SECRET"}')
        with open(os.path.join(r, "my_token.txt"), "w") as fh:
            fh.write("SECRET")
        with open(os.path.join(r, "big.bin"), "wb") as fh:
            fh.truncate(SB.MAX_NEW_FILE + 1)
        status0 = sh(["status", "--porcelain"], r)
        head0 = sh(["rev-parse", "HEAD"], r).strip()
        idx0 = open(os.path.join(r, ".git", "index"), "rb").read()
        s = SB.snapshot(r)
        files = sh(["ls-tree", "-r", "--name-only", "pc-snapshot"], r).split()
        check("snapshot: a new commit on pc-snapshot (parent HEAD) with the changed and the new file",
              s["new"] and sh(["rev-parse", "pc-snapshot"], r).strip() == s["ref"] and sh(["rev-parse", "pc-snapshot^"], r).strip() == head0
              and "engine/new_tool.py" in files and sh(["show", "pc-snapshot:engine/lit.py"], r).startswith("V = 2"), (s, files))
        check("snapshot: never a .gitignore'd file, a secret-looking name or a new file over 25 MB",
              "data/alerts.json" not in files and "my_token.txt" not in files and "big.bin" not in files
              and set(s["skipped"]) == {"my_token.txt", "big.bin"}, (files, s["skipped"]))
        check("snapshot: working files, the real index, HEAD and the checked-out branch untouched",
              sh(["status", "--porcelain"], r) == status0 and sh(["rev-parse", "HEAD"], r).strip() == head0
              and open(os.path.join(r, ".git", "index"), "rb").read() == idx0 and sh(["branch", "--show-current"], r).strip() == "main")
        s2 = SB.snapshot(r)
        check("snapshot: run again with no change -> the same commit, no new one", not s2["new"] and s2["ref"] == s["ref"], s2)
        sh(["checkout", "-q", "--", "engine/lit.py"], r)
        os.remove(os.path.join(r, "engine", "new_tool.py"))
        s3 = SB.snapshot(r)
        check("snapshot: files equal to HEAD -> HEAD itself", not s3["new"] and s3["ref"] == head0, s3)


# ============================================================================================== weekly run
def weekly_checks():
    with Box() as b:
        r = b.repo
        with open(os.path.join(r, "engine", "lit.py"), "w") as fh:
            fh.write("V = 3\n")
        os.makedirs(b.home)
        with open(os.path.join(b.home, "ntfy.json"), "w") as fh:
            json.dump({"topic": "nq-test-topic-1234", "ntfy": "https://ntfy.sh"}, fh)
        dest = os.path.join(b.sync, "OLYMPUS_BACKUPS")
        os.makedirs(dest)
        for i in range(5):                                   # five older zips: only the newest 4 stay after the run
            n = os.path.join(dest, f"OLYMPUS_BACKUP_2026-10-0{i + 1}_abc{i}def.zip")
            open(n, "w").close()
            open(n[:-4] + ".sha256.txt", "w").close()
            os.utime(n, (time.time() - 86400 * (10 - i), time.time() - 86400 * (10 - i)))
        open(os.path.join(dest, "my_notes.txt"), "w").close()
        SB.save({"url": b.mirror, "host": "local", "owner": "", "repo": "mirror", "token": None, "user": "", "backup_dir": dest}, root=ROOT)
        out, http = [], Fake()
        rc = SB.weekly(root=r, http=http, say=out.append)
        zips = sorted(n for n in os.listdir(dest) if n.endswith(".zip"))
        heads = subprocess.run(["git", "--git-dir", b.mirror, "for-each-ref", "--format=%(refname)"], capture_output=True, text=True).stdout.split()
        check("weekly: exit 0, the rows SNAPSHOT / ZIP / MIRROR all OK", rc == 0 and [x.split("]")[0] for x in out] == ["  [OK", "  [OK", "  [OK"], out)
        check("weekly: the zip of the snapshot (the files the PC runs) in the synced folder, with its sha256 list",
              any(re.fullmatch(r"OLYMPUS_BACKUP_\d{4}-\d{2}-\d{2}_[0-9a-f]+\.zip", z) and not z.startswith("OLYMPUS_BACKUP_2026-10") for z in zips)
              and any(n.endswith(".sha256.txt") and not n.startswith("OLYMPUS_BACKUP_2026-10") for n in os.listdir(dest)), zips)
        import zipfile
        newest = max((os.path.join(dest, z) for z in zips), key=os.path.getmtime)
        check("weekly: the zip holds the PC's current engine/lit.py (V = 3), not HEAD's", zipfile.ZipFile(newest).read("engine/lit.py").startswith(b"V = 3"))
        check("weekly: only the newest 4 zips kept (the oldest 2 and their .sha256.txt removed, other files left alone)",
              len(zips) == 4 and "OLYMPUS_BACKUP_2026-10-01_abc0def.zip" not in zips and "OLYMPUS_BACKUP_2026-10-02_abc1def.zip" not in zips
              and not os.path.exists(os.path.join(dest, "OLYMPUS_BACKUP_2026-10-01_abc0def.sha256.txt")) and os.path.exists(os.path.join(dest, "my_notes.txt")), zips)
        check("weekly: the mirror has main, pc-snapshot and the tag", {"refs/heads/main", "refs/heads/pc-snapshot", "refs/tags/v1"} <= set(heads), heads)
        np = http.ntfy()
        check("weekly: one phone push 'Weekly backup OK' on the alert topic", len(np) == 1 and np[0]["url"].endswith("/nq-test-topic-1234")
              and np[0]["h"].get("Title") == "Weekly backup OK", np)
        last = json.load(open(SB.last_path()))
        check("weekly: the last run recorded outside the repo (backup_last.json)", last["ok"] is True and len(last["rows"]) == 3, last)
        out.clear()
        rc = SB.weekly(root=r, http=Fake(), say=out.append, dry=True)
        check("--dry-run: says, writes nothing", rc == 0 and out and "DRY RUN" in out[0] and len([n for n in os.listdir(dest) if n.endswith(".zip")]) == 4, out)
        # ---- a public GitLab mirror is refused
        SB.save({"url": "https://gitlab.com/demo/olympus.git", "host": "gitlab.com", "owner": "demo", "repo": "olympus", "path": "demo/olympus",
                 "token": TOKEN, "user": "oauth2", "backup_dir": dest}, root=ROOT)
        out, http = [], Fake(gitlab=(200, {"visibility": "public"}))
        rc = SB.weekly(root=r, http=http, say=out.append, mirror_only=True)
        np = http.ntfy()
        check("weekly: a PUBLIC GitLab mirror -> nothing pushed, [FIX] make it private, a high-priority push 'something to fix'",
              rc == 1 and any("PUBLIC" in x and "nothing pushed" in x for x in out) and np and np[0]["h"].get("Priority") == "high"
              and TOKEN not in json.dumps(http.calls[1:]), (out, np))
        # ---- a mirror that is not there
        SB.save({"url": os.path.join(b.dir, "nothere.git"), "host": "local", "token": None, "user": "", "backup_dir": dest}, root=ROOT)
        out = []
        rc = SB.weekly(root=r, http=Fake(), say=out.append, mirror_only=True)
        check("weekly: a mirror repository that does not exist -> plain 'create it' sentence, exit 1",
              rc == 1 and any("not found" in x and "create it" in x for x in out), out)


def auth_checks():
    e = SB.auth_env("demo", TOKEN)
    check("auth: the token only in this run's environment (Authorization header), helpers off, no prompt",
          e["GIT_CONFIG_KEY_0"] == "credential.helper" and e["GIT_CONFIG_VALUE_0"] == "" and e["GIT_CONFIG_KEY_1"] == "http.extraHeader"
          and e["GIT_CONFIG_VALUE_1"].startswith("Authorization: Basic ") and e["GIT_TERMINAL_PROMPT"] == "0" and TOKEN not in json.dumps(e))
    import base64
    b64 = base64.b64encode(f"demo:{TOKEN}".encode()).decode()
    check("redact: token and its base64 form removed from git output", SB.redact(f"x {TOKEN} y {b64} z", TOKEN, "demo") == "x *** y *** z")
    with Box() as b:
        cfg = {"url": "https://127.0.0.1:9/demo/olympus.git", "host": "127.0.0.1", "user": "demo", "token": TOKEN}
        old = {k: os.environ.get(k) for k in ("NO_PROXY", "no_proxy")}
        os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1"
        try:
            ok, why = SB.push(b.repo, cfg, timeout=120)
        finally:
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        conf = open(os.path.join(b.repo, ".git", "config")).read()
        check("push to an unreachable host: fails softly with a plain sentence, the token in no output and not in .git/config",
              not ok and TOKEN not in why and TOKEN not in conf and "extraheader" not in conf.lower(), (why, conf))


# ============================================================================================== static + pwsh
def static_checks():
    raw = open(os.path.join(ROOT, "tools/bat/BACKUP_SETUP.bat"), "rb").read()
    check("tools/bat/BACKUP_SETUP.bat: CRLF, ASCII, setup -> task -> one run, -Remove, pauses",
          b"\n" not in raw.replace(b"\r\n", b"") and all(c < 128 for c in raw) and b"second_backup.py\" --setup" in raw
          and b"backup_task.ps1\"" in raw and b"second_backup.py\" --weekly" in raw and b"-Remove" in raw and b"pause" in raw)
    ps = open(os.path.join(ROOT, "scripts", "backup_task.ps1"), "rb").read()
    check("backup_task.ps1: ASCII (Windows PowerShell 5.1 reads it without a BOM)", all(c < 128 for c in ps))
    src = open(os.path.join(ROOT, "tools", "second_backup.py"), encoding="utf-8").read()
    body = src.split('"""', 2)[-1]
    check("second_backup.py: no order, no live_model, no live phrase, never prints the token",
          not re.search(r"PLACE;|place_line|live_model|I ACCEPT|LIVE_PHRASE|/api/live|print\([^)]*token", body))
    check("second_backup.py: never puts the token into a URL or git config on disk", "remote add" not in body and "config --" not in body
          and not re.search(r"https://[^\"']*\{[^}]*token", body))


def pwsh_checks():
    pw = os.environ.get("LE_PWSH") or shutil.which("pwsh")
    if not pw:
        print("[SKIP] pwsh not found")
        return
    r = subprocess.run([pw, "-NoProfile", "-NoLogo", "-File", os.path.join(ROOT, "tests", "win_harness", "lint51.ps1"),
                        os.path.join(ROOT, "scripts", "backup_task.ps1")], capture_output=True, text=True, timeout=300)
    found = [ln for ln in r.stdout.splitlines() if ln.strip()]
    check("5.1 lint: backup_task.ps1 has no PowerShell-7-only syntax", r.returncode == 0 and not found, found or r.stderr)
    d = tempfile.mkdtemp(prefix="sbps_")
    try:
        root = os.path.join(d, "root")
        os.makedirs(os.path.join(root, "scripts"))
        os.makedirs(os.path.join(root, "tools"))
        shutil.copy(os.path.join(ROOT, "scripts", "backup_task.ps1"), os.path.join(root, "scripts"))
        open(os.path.join(root, "tools", "second_backup.py"), "w").close()
        py = os.path.join(d, "python")
        open(py, "w").close()
        log = os.path.join(d, "win.log")
        env = {**os.environ, "LE_BB_T_LOG": log}

        def run(*args):
            x = subprocess.run([pw, "-NoProfile", "-NoLogo", "-NonInteractive", "-File", os.path.join(root, "scripts", "backup_task.ps1"),
                                "-Python", py, *args], capture_output=True, text=True, timeout=120, env=env)
            return x.returncode, x.stdout + x.stderr
        rc, out = run("-DryRun")
        check("pwsh -DryRun: says the Sunday task, registers nothing", rc == 0 and "DRY RUN" in out and "Sunday" in out and not os.path.exists(log), out)
        rc, out = run()
        lines = open(log).read().splitlines() if os.path.exists(log) else []
        check("pwsh: registers OlympusWeeklyBackup weekly with pythonw-or-python --weekly --quiet",
              rc == 0 and lines and lines[-1].startswith("TASK REGISTER OlympusWeeklyBackup weekly Sunday") and "--weekly --quiet" in lines[-1], (out, lines))
        rc, out = run("-Remove")
        lines = open(log).read().splitlines()
        check("pwsh -Remove: deletes only the task", rc == 0 and lines[-1] == "TASK REMOVE OlympusWeeklyBackup", (out, lines))
        os.remove(os.path.join(root, "tools", "second_backup.py"))
        rc, out = run()
        check("pwsh: an old folder without second_backup.py -> [FIX] update from the zip, exit 1", rc == 1 and "UPDATE" not in out.upper().split("FIX")[0]
              and "missing" in out, out)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main() -> int:
    setup_checks()
    snapshot_checks()
    weekly_checks()
    auth_checks()
    static_checks()
    pwsh_checks()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


def test_second_backup():                       # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
