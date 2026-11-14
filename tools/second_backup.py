"""Second backup (owner 2026-11-13, GitHub suspended): a git mirror on a free second host (Codeberg or GitLab) and the weekly
code zip (tools/make_backup.py) in a synced folder (OneDrive / iCloud / Google Drive / Dropbox). docs/DISASTER_RECOVERY.md.

  python tools/second_backup.py --setup      once (BACKUP_SETUP.bat): paste the mirror repo URL, type the token (hidden),
                                             pick the synced folder. Saved in %USERPROFILE%\\.olympus\\backup.json (outside the
                                             repo, file mode 600 where it applies). The token is never printed or logged.
  python tools/second_backup.py --weekly     the weekly run (Task Scheduler "OlympusWeeklyBackup", scripts/backup_task.ps1):
                                             1 snapshot, 2 zip into the synced folder (keeps the newest 4), 3 mirror push,
                                             4 one phone push (ntfy, the alert topic of tools/pc_report.py) with the result
  python tools/second_backup.py --mirror     only the mirror push
  python tools/second_backup.py --dry-run    says what it would do, writes and sends nothing
  python tools/second_backup.py --status     the saved settings (token hidden) and the last run

The snapshot: the PC is updated by zip (UPDATE_FROM_ZIP.bat), so its git HEAD can be older than its files. The weekly run
first records the folder as it is in a side branch "pc-snapshot" (a temporary index: the working files, the real index and
the checked-out branch are never touched; .gitignore'd files are never included, nor any new file over 25 MB or with a
secret-looking name). The zip and the mirror then hold what the PC really runs.
The mirror push: every local branch and tag, forced (the mirror is a copy). The token goes to git only through this run's
environment (an Authorization header), never on the command line, in a URL, in .git/config or in a credential store. A
public mirror repo is refused (Codeberg / GitLab API check): the repo holds the strategy.
Never touches the bot, NinjaTrader, an order, live_model*.json or a setting. Every failure is said plainly (exit 1).
Tests: tests/test_second_backup.py (temp repos, a local bare "mirror", fake HTTP).
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import getpass
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SNAP_REF = "refs/heads/pc-snapshot"
KEEP_ZIPS = 4
MAX_NEW_FILE = 25 * 1024 * 1024
SECRET_NAME = re.compile(r"(^|[\\/])(\.env[^\\/]*|id_rsa[^\\/]*|id_ed25519[^\\/]*|[^\\/]*\.(pem|key|pfx|p12|kdbx)|"
                         r"[^\\/]*(token|secret|password|passwd|credential)[^\\/]*)$", re.I)
KNOWN_HOSTS = ("codeberg.org", "gitlab.com")
SYNCED = (("OneDrive", ("OneDrive", "OneDriveConsumer")), ("iCloud Drive", ()), ("Google Drive", ()), ("Dropbox", ()))
UA = "olympus-backup/1"
HTTP_TIMEOUT_S = 20
PUSH_TIMEOUT_S = 1800


# ------------------------------------------------------------------------------------------------ settings (outside the repo)
def olympus_dir(env=None) -> str:
    try:
        from engine import nogithub
        return nogithub.olympus_dir(env)
    except Exception:
        env = os.environ if env is None else env
        return env.get("OLYMPUS_HOME") or os.path.join(env.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def cfg_path(env=None) -> str:
    return os.path.join(olympus_dir(env), "backup.json")


def inside(path: str, root: str) -> bool:
    try:
        a, b = os.path.realpath(path), os.path.realpath(root)
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


def load(env=None) -> dict:
    try:
        with open(cfg_path(env), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(d: dict, env=None, root: str = ROOT) -> str:
    p = cfg_path(env)
    if inside(p, root):
        raise RuntimeError("the backup settings must be saved outside the bot folder")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


def parse_url(url: str, allow_local: bool = False) -> dict:
    """{"url", "host", "owner", "repo"} of an https git URL (a .git ending is added), or {"error"}."""
    u = str(url or "").strip().strip('"').strip("'")
    if allow_local and (u.startswith("file://") or os.path.isdir(u)):
        return {"url": u, "host": "local", "owner": "", "repo": os.path.basename(u.rstrip("/\\"))}
    p = urllib.parse.urlparse(u)
    if p.scheme != "https" or not p.hostname:
        return {"error": "the address must start with https:// (copy it from the repository page: Code / Clone > HTTPS)"}
    if p.username or p.password:
        return {"error": "paste the address without a name or token in it (the token is asked for next, hidden)"}
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2:
        return {"error": "the address needs the owner and the repository, like https://codeberg.org/<you>/<repo>.git"}
    path = "/".join(parts)
    if not path.endswith(".git"):
        path += ".git"
    return {"url": f"https://{p.hostname}/{path}", "host": p.hostname.lower(), "owner": parts[0], "repo": parts[-1].removesuffix(".git"),
            "path": path.removesuffix(".git")}


def synced_candidates(env=None) -> list:
    """[(name, folder)] of the synced folders that exist on this PC, best first."""
    env = os.environ if env is None else env
    home = env.get("USERPROFILE") or os.path.expanduser("~")
    out = []
    for k in ("OneDrive", "OneDriveConsumer"):
        if env.get(k) and os.path.isdir(env[k]):
            out.append(("OneDrive", env[k]))
    for name, p in (("iCloud Drive", os.path.join(home, "iCloudDrive")), ("Google Drive", os.path.join(home, "Google Drive")),
                    ("Google Drive", "G:\\My Drive" if os.name == "nt" else ""), ("Dropbox", os.path.join(home, "Dropbox")),
                    ("OneDrive", os.path.join(home, "OneDrive"))):
        if p and os.path.isdir(p) and all(os.path.realpath(p) != os.path.realpath(q) for _n, q in out):
            out.append((name, p))
    return out


# ------------------------------------------------------------------------------------------------ git
def git(args, cwd=ROOT, env=None, timeout=600, check=True) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode:
        raise RuntimeError(f"git {args[0]} failed: {(r.stderr or r.stdout).strip()[-300:]}")
    return r


def is_repo(root: str) -> bool:
    try:
        return git(["rev-parse", "--is-inside-work-tree"], cwd=root, check=False).stdout.strip() == "true"
    except Exception:
        return False


def snapshot(root: str = ROOT, now=None, say=print) -> dict:
    """Record the working files in refs/heads/pc-snapshot (a temporary index; nothing else changes).
    -> {"ref": sha to back up, "new": bool, "skipped": [paths left out]}."""
    head = git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    fd, idx = tempfile.mkstemp(prefix="olympus_snap_", suffix=".idx")
    os.close(fd)
    os.unlink(idx)
    env = {**os.environ, "GIT_INDEX_FILE": idx}
    skipped = []
    try:
        real = git(["rev-parse", "--git-path", "index"], cwd=root).stdout.strip()
        real = real if os.path.isabs(real) else os.path.join(root, real)
        if os.path.isfile(real):
            import shutil
            shutil.copyfile(real, idx)            # a COPY of the real index (its file stats make `add` fast); the real one is never written
        else:
            git(["read-tree", "HEAD"], cwd=root, env=env)
        git(["add", "-A", "--", "."], cwd=root, env=env)
        added = [x for x in git(["diff", "--cached", "--name-only", "--diff-filter=A", "-z", "HEAD"], cwd=root, env=env).stdout.split("\0") if x]
        for rel in added:
            p = os.path.join(root, rel)
            try:
                big = os.path.getsize(p) > MAX_NEW_FILE
            except OSError:
                big = False
            if big or SECRET_NAME.search(rel):
                skipped.append(rel)
        for i in range(0, len(skipped), 100):
            git(["rm", "--cached", "-q", "--", *skipped[i:i + 100]], cwd=root, env=env)
        tree = git(["write-tree"], cwd=root, env=env).stdout.strip()
    finally:
        try:
            os.unlink(idx)
        except OSError:
            pass
    if tree == git(["rev-parse", "HEAD^{tree}"], cwd=root).stdout.strip():
        return {"ref": head, "new": False, "skipped": skipped}
    stamp = dt.datetime.fromtimestamp(now or time.time()).strftime("%Y-%m-%d %H:%M")
    cenv = {**os.environ, "GIT_AUTHOR_NAME": "OLYMPUS PC", "GIT_AUTHOR_EMAIL": "pc@localhost", "GIT_COMMITTER_NAME": "OLYMPUS PC",
            "GIT_COMMITTER_EMAIL": "pc@localhost"}
    prev = git(["rev-parse", "-q", "--verify", SNAP_REF], cwd=root, check=False).stdout.strip()
    if prev and git(["rev-parse", prev + "^{tree}"], cwd=root, check=False).stdout.strip() == tree:
        return {"ref": prev, "new": False, "skipped": skipped}
    commit = git(["commit-tree", tree, "-p", head, "-m", f"PC snapshot {stamp} (the files this PC runs; HEAD {head[:7]})"],
                 cwd=root, env=cenv).stdout.strip()
    git(["update-ref", SNAP_REF, commit], cwd=root)
    return {"ref": commit, "new": True, "skipped": skipped}


def auth_env(user: str, token: str) -> dict:
    """The token for one git run only: an Authorization header through GIT_CONFIG_* (git 2.31+), no credential helper, no prompt."""
    b = base64.b64encode(f"{user}:{token}".encode("utf-8")).decode("ascii")
    return {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_ASKPASS": "", "SSH_ASKPASS": "",
            "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "credential.helper", "GIT_CONFIG_VALUE_0": "",
            "GIT_CONFIG_KEY_1": "http.extraHeader", "GIT_CONFIG_VALUE_1": f"Authorization: Basic {b}"}


def redact(text: str, token: str | None, user: str | None = None) -> str:
    s = str(text or "")
    if token:
        s = s.replace(token, "***")
        if user is not None:
            s = s.replace(base64.b64encode(f"{user}:{token}".encode("utf-8")).decode("ascii"), "***")
    return s


def push(root: str, cfg: dict, refs=None, timeout=PUSH_TIMEOUT_S) -> tuple:
    """git push --force of every branch and tag to the mirror. -> (ok, plain why)."""
    u = cfg.get("url")
    env = dict(os.environ)
    if cfg.get("host") != "local":
        env.update(auth_env(cfg.get("user") or "oauth2", cfg.get("token") or ""))
    specs = refs or ["+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*"]
    try:
        r = git(["push", "--porcelain", u, *specs], cwd=root, env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return False, f"the push took longer than {timeout // 60} minutes (slow internet?): it tries again next week, or run BACKUP_SETUP.bat"
    out = redact((r.stderr or "") + (r.stdout or ""), cfg.get("token"), cfg.get("user") or "oauth2")
    if r.returncode == 0:
        n = len([ln for ln in out.splitlines() if re.match(r"^[ +*=!-]\t", ln) and not ln.startswith("=")])
        return True, f"mirror up to date ({n} branch / tag update{'s' if n != 1 else ''})"
    low = out.lower()
    if "403" in low or "401" in low or "authentication" in low or "could not read username" in low or "denied" in low:
        return False, "the mirror refused the token (wrong, expired, or without write access): make a new one and run BACKUP_SETUP.bat"
    if "not found" in low or "404" in low or "does not appear to be a git repository" in low:
        return False, "the mirror repository was not found: create it (empty, private) first, then run BACKUP_SETUP.bat"
    if "could not resolve host" in low or "unable to access" in low:
        return False, "no internet to the mirror host right now: it tries again next week"
    return False, "git push failed: " + " ".join(out.split())[-200:]


# ------------------------------------------------------------------------------------------------ the host's API (privacy check)
def default_http(method, url, body=None, headers=None, timeout=HTTP_TIMEOUT_S):
    """-> (status, text), never raises. Same signature as tools/pc_report.default_http (one fake serves both in the tests)."""
    if os.environ.get("LE_PR_NO_NET") == "1":
        return 0, "network off (LE_PR_NO_NET=1)"
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("User-Agent", UA)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, e.__class__.__name__


def visibility(cfg: dict, http=None) -> tuple:
    """("private" | "public" | "missing" | "denied" | "unknown", why) from Codeberg's / GitLab's API with the token."""
    http = http or default_http
    host, tok = cfg.get("host"), cfg.get("token") or ""
    if host == "codeberg.org":
        st, txt = http("GET", f"https://codeberg.org/api/v1/repos/{cfg['owner']}/{cfg['repo']}", None, {"Authorization": f"token {tok}"})
        key = "private"
    elif host == "gitlab.com":
        st, txt = http("GET", "https://gitlab.com/api/v4/projects/" + urllib.parse.quote(cfg.get("path") or "", safe=""), None,
                       {"PRIVATE-TOKEN": tok})
        key = "visibility"
    else:
        return "unknown", f"{host} is not Codeberg or GitLab: the script cannot check that the repository is private (make sure it is)"
    if st == 404:
        return "missing", "the repository does not exist yet (or the token cannot see it): create it, empty and private"
    if st in (401, 403):
        return "denied", "the token was refused: make a new one with repository write access"
    if st != 200:
        return "unknown", f"could not ask {host} ({st or txt}); the push still tries"
    try:
        d = json.loads(txt)
    except Exception:
        return "unknown", f"{host} answered something unexpected; the push still tries"
    if key == "private":
        return ("private", "private") if d.get("private") is True else ("public", "the repository is PUBLIC")
    v = str(d.get("visibility") or "")
    return ("private", "private") if v == "private" else ("public", f"the repository is {v.upper() or 'not private'}")


# ------------------------------------------------------------------------------------------------ the zip
def make_zip(root: str, out_dir: str, ref: str, say=print) -> dict:
    """tools/make_backup.py on `ref` into out_dir, then keep only the newest KEEP_ZIPS zips (and their .sha256.txt)."""
    import contextlib
    import io
    from tools import make_backup
    buf = io.StringIO()
    old = make_backup.ROOT
    make_backup.ROOT = root
    try:
        with contextlib.redirect_stdout(buf):                  # the PC's own files: its version list is the one its last code zip brought
            make_backup.main(["--out", out_dir, "--ref", ref, "--no-model-check"])
    finally:
        make_backup.ROOT = old
    zips = sorted((n for n in os.listdir(out_dir) if re.fullmatch(r"OLYMPUS_BACKUP_\d{4}-\d{2}-\d{2}_[0-9a-f]+\.zip", n)),
                  key=lambda n: os.path.getmtime(os.path.join(out_dir, n)), reverse=True)
    removed = []
    for n in zips[KEEP_ZIPS:]:
        for f in (n, n[:-4] + ".sha256.txt"):
            try:
                os.remove(os.path.join(out_dir, f))
                removed.append(f)
            except OSError:
                pass
    newest = zips[0] if zips else None
    size = os.path.getsize(os.path.join(out_dir, newest)) / 1048576 if newest else 0
    return {"zip": newest, "mb": round(size, 1), "removed": removed}


# ------------------------------------------------------------------------------------------------ phone push (ntfy)
def notify(title: str, body: str, priority="default", http=None) -> bool:
    try:
        from tools import pc_report
        c = pc_report.load_cfg()
        if not c.get("topic") or not c.get("on"):
            return False
        ok, _why = pc_report.ntfy_post(c["ntfy"], c["topic"], body, title=title, priority=priority, tags="floppy_disk", http=http)
        return ok
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ the runs
def last_path(env=None) -> str:
    return os.path.join(olympus_dir(env), "backup_last.json")


def weekly(root: str = ROOT, env=None, http=None, dry=False, mirror_only=False, say=print, now=None) -> int:
    cfg = load(env)
    rows, bad = [], []
    if not is_repo(root):
        say("  [FIX] this folder has no git history (.git): copy the bot folder from a backup zip with its .git, or ask Claude.")
        return 1
    if dry:
        say(f"  DRY RUN - snapshot of the working files -> {SNAP_REF}; zip -> {cfg.get('backup_dir') or '(no synced folder set)'}; "
            f"mirror -> {cfg.get('url') or '(no mirror set)'}. Nothing written or sent.")
        return 0
    try:
        snap = snapshot(root, now)
        ref = snap["ref"]
        rows.append(("OK", "SNAPSHOT", f"{ref[:7]}" + (" (new: the files this PC runs)" if snap["new"] else " (no change)")
                     + (f"; left out {len(snap['skipped'])} file(s) (secret-looking name or over 25 MB)" if snap["skipped"] else "")))
    except Exception as e:
        ref = "HEAD"
        rows.append(("FIX", "SNAPSHOT", f"could not record the working files ({str(e)[:120]}); backing up HEAD"))
    if not mirror_only:
        d = cfg.get("backup_dir")
        if not d:
            rows.append(("SKIP", "ZIP", "no synced folder set: double-click BACKUP_SETUP.bat"))
        elif not os.path.isdir(os.path.dirname(os.path.abspath(d)) or d):
            rows.append(("FIX", "ZIP", f"the synced folder is gone ({d}): double-click BACKUP_SETUP.bat"))
            bad.append("zip")
        else:
            try:
                os.makedirs(d, exist_ok=True)
                z = make_zip(root, d, ref, say)
                rows.append(("OK", "ZIP", f"{z['zip']} ({z['mb']} MB) in {d}" + (f"; removed {len(z['removed']) // 2} old" if z["removed"] else "")))
            except BaseException as e:
                rows.append(("FIX", "ZIP", f"zip failed: {str(e)[:160]}"))
                bad.append("zip")
    if not cfg.get("url"):
        rows.append(("SKIP", "MIRROR", "no mirror set: double-click BACKUP_SETUP.bat"))
    else:
        vis, why = ("private", "") if cfg.get("host") == "local" else visibility(cfg, http)
        if vis == "public":
            rows.append(("FIX", "MIRROR", f"{why}: make it private on {cfg.get('host')} (Settings > Visibility); nothing pushed"))
            bad.append("mirror")
        elif vis in ("missing", "denied"):
            rows.append(("FIX", "MIRROR", why + "; then double-click BACKUP_SETUP.bat"))
            bad.append("mirror")
        else:
            ok, msg = push(root, cfg)
            rows.append(("OK" if ok else "FIX", "MIRROR", f"{cfg.get('host')}/{cfg.get('owner')}/{cfg.get('repo')}: {msg}"
                         + (f" ({why})" if vis == "unknown" and ok else "")))
            if not ok:
                bad.append("mirror")
    for kind, label, text in rows:
        say(f"  [{kind}] {label:<8} {text}")
    rec = {"t": int(now or time.time()), "ok": not bad, "rows": [list(r) for r in rows]}
    try:
        os.makedirs(olympus_dir(env), exist_ok=True)
        with open(last_path(env), "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1)
    except Exception:
        pass
    summary = "; ".join(f"{label.lower()}: {text}" for kind, label, text in rows if kind != "SKIP")[:500]
    if bad:
        notify("Weekly backup: something to fix", summary + " Double-click BACKUP_SETUP.bat on the PC.", "high", http)
    else:
        notify("Weekly backup OK", summary, "low", http)
    return 1 if bad else 0


def setup(env=None, ask=input, ask_secret=getpass.getpass, http=None, say=print, root: str = ROOT, allow_local=False) -> int:
    cfg = load(env)
    say("  BACKUP SETUP: a second copy of the code on a free git host, and a weekly zip in your synced folder.")
    say("  (Enter keeps what is there.)")
    while True:
        raw = ask(f"  1/3 Mirror repository address (https://codeberg.org/<you>/<repo>.git){' [' + cfg['url'] + ']' if cfg.get('url') else ''}: ").strip()
        if not raw and cfg.get("url"):
            u = {k: cfg.get(k) for k in ("url", "host", "owner", "repo", "path")}
            break
        u = parse_url(raw, allow_local=allow_local)
        if "error" not in u:
            break
        say(f"      {u['error']}")
    new_repo = u["url"] != cfg.get("url")
    tok = cfg.get("token") if not new_repo else None
    if u["host"] != "local":
        t = ask_secret("  2/3 Access token (typed hidden; Enter keeps the saved one): ").strip()
        if t:
            tok = t
        if not tok:
            say("  [FIX] no token: make one on the host (Codeberg: Settings > Applications, scope repository read and write; "
                "GitLab: the project > Settings > Access tokens, role Maintainer, scope write_repository), then run this again.")
            return 1
        user = u["owner"] if u["host"] != "gitlab.com" else "oauth2"
        probe = {**u, "token": tok, "user": user}
        vis, why = visibility(probe, http)
        if vis == "public":
            say(f"  [FIX] {why}: make it private first (the repo holds your strategy). Nothing saved.")
            return 1
        if vis in ("missing", "denied"):
            say(f"  [FIX] {why}. Nothing saved.")
            return 1
        say(f"      repository: {why}")
    else:
        user = ""
    cands = synced_candidates(env)
    default = cfg.get("backup_dir") or (os.path.join(cands[0][1], "OLYMPUS_BACKUPS") if cands else "")
    if cands:
        say("      synced folders on this PC: " + ", ".join(f"{n} ({p})" for n, p in cands))
    raw = ask(f"  3/3 Folder for the weekly zip{' [' + default + ']' if default else ' (a OneDrive / iCloud / Google Drive folder)'}: ").strip().strip('"')
    bdir = raw or default
    if bdir and inside(bdir, root):
        say("  [FIX] the zip folder must be outside the bot folder (a synced folder). Nothing saved.")
        return 1
    cfg.update({k: u.get(k) for k in ("url", "host", "owner", "repo", "path")})
    cfg.update(token=tok, user=user, backup_dir=bdir or None, saved=int(time.time()))
    p = save(cfg, env, root)
    say(f"  [OK]  saved in {p} (outside the bot folder; the token is not shown)")
    return 0


def status(env=None, say=print) -> int:
    c = load(env)
    say(f"  mirror : {c.get('url') or 'not set'}" + (" (token saved)" if c.get("token") else ""))
    say(f"  zip    : {c.get('backup_dir') or 'not set'}")
    try:
        last = json.load(open(last_path(env), encoding="utf-8"))
        say(f"  last   : {dt.datetime.fromtimestamp(last['t']):%a %Y-%m-%d %H:%M} {'OK' if last.get('ok') else 'something to fix'}")
        for kind, label, text in last.get("rows") or []:
            say(f"    [{kind}] {label:<8} {text}")
    except Exception:
        say("  last   : never ran")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/second_backup.py", description="Second backup: git mirror + weekly zip.")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--mirror", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="the scheduled task: no output")
    a = ap.parse_args(argv)
    say = (lambda *_: None) if a.quiet else print
    if a.setup:
        return setup()
    if a.status:
        return status()
    return weekly(dry=a.dry_run, mirror_only=a.mirror, say=say)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("  stopped. Nothing else changed.")
        sys.exit(1)
