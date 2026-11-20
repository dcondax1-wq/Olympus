"""EMAIL AUTOPILOT reply bridge: the PC <-> Claude, through the PRIVATE repo's branch 'agency-inbox' (the pattern of the PC's other data
branches; a separate working clone in %USERPROFILE%\\.olympus\\agency_inbox, never the bot's own folder, never the pc branch).

  inbox/<id>.json    the PC writes: one trimmed reply (lead id, business, class, their words: no address, no signature, phones masked)
  status.json        the PC writes: the day's counts (core.public_counts) + what needs the owner
  outbox/<id>.json   Claude writes (the scheduled cloud session): a draft answer {id, inbox_id, lead_id, kind, subject, body, approved?}
  sent/<id>.json     the PC writes: what it did with each draft {id, status: sent | held | refused, why, t}
Plain git (clone / fetch / reset / commit / push); a refused push is re-fetched and retried once. Never force-pushes, never another branch."""
from __future__ import annotations

import json
import os
import subprocess

BRANCH = "agency-inbox"
README = ("# agency-inbox (private)\n\nThe Website Factory's email autopilot: the PC writes inbox/ (trimmed replies) and status.json,\n"
          "Claude writes outbox/ (draft answers), the PC writes sent/. No passwords, no full email addresses of the businesses' people.\n")


def git(args, cwd, timeout=90) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="olympus-pc", GIT_AUTHOR_EMAIL="pc@olympus.local",
               GIT_COMMITTER_NAME="olympus-pc", GIT_COMMITTER_EMAIL="pc@olympus.local")
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def remote_url(repo_root: str) -> str:
    r = git(["remote", "get-url", "--push", "origin"], repo_root)
    return r.stdout.strip() if r.returncode == 0 else ""


def sync(url: str, wd: str) -> str:
    """make wd a clone of the branch at its remote tip (created as an orphan branch the first time). '' = ok, else the problem"""
    if not url:
        return "no repo address (git remote origin)"
    if not os.path.isdir(os.path.join(wd, ".git")):
        os.makedirs(wd, exist_ok=True)
        if git(["init", "-q"], wd).returncode:
            return "git init failed"
        git(["remote", "add", "origin", url], wd)
    else:
        git(["remote", "set-url", "origin", url], wd)
    f = git(["fetch", "-q", "origin", BRANCH], wd)
    if f.returncode == 0:
        r = git(["checkout", "-q", "-B", BRANCH, "FETCH_HEAD"], wd)
        if r.returncode:
            return "checkout failed: " + r.stderr.strip()[:120]
        git(["reset", "-q", "--hard", "FETCH_HEAD"], wd)
        return ""
    if "couldn't find remote ref" in (f.stderr or "").lower() or "not found" in (f.stderr or "").lower():
        git(["checkout", "-q", "--orphan", BRANCH], wd)
        with open(os.path.join(wd, "README.md"), "w", encoding="utf-8") as fh:
            fh.write(README)
        git(["add", "README.md"], wd)
        c = git(["commit", "-q", "-m", "agency-inbox: start"], wd)
        if c.returncode:
            return "first commit failed"
        p = git(["push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}"], wd)
        return "" if p.returncode == 0 else "first push failed: " + p.stderr.strip()[:120]
    return "fetch failed: " + (f.stderr or "").strip()[:160]


def read_outbox(wd: str) -> list:
    out, d = [], os.path.join(wd, "outbox")
    if not os.path.isdir(d):
        return out
    for n in sorted(os.listdir(d)):
        if n.endswith(".json"):
            try:
                with open(os.path.join(d, n), encoding="utf-8") as fh:
                    j = json.load(fh)
                if isinstance(j, dict):
                    j.setdefault("id", n[:-5])
                    out.append(j)
            except (OSError, ValueError):
                continue
    return out


def write_and_push(url: str, wd: str, files: dict, message: str) -> str:
    """files = {relative path: dict}; commit on top of the remote tip and push (once more after a re-fetch). '' = ok"""
    for attempt in range(2):
        err = sync(url, wd)
        if err:
            return err
        for rel, data in files.items():
            if ".." in rel or rel.startswith(("/", "\\")):
                continue
            p = os.path.join(wd, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1, ensure_ascii=False)
        paths = [x for x in ("inbox", "sent", "status.json") if os.path.exists(os.path.join(wd, x))]   # a missing pathspec aborts the whole add
        if paths:
            git(["add", "-A", *paths], wd)
        if git(["diff", "--cached", "--quiet"], wd).returncode == 0:
            return ""
        if git(["commit", "-q", "-m", message], wd).returncode:
            return "commit failed"
        p = git(["push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}"], wd)
        if p.returncode == 0:
            return ""
        if attempt == 1:
            return "push refused twice: " + p.stderr.strip()[:120]
    return "push failed"
