"""Create the `control` branch for the phone remote control (engine/remote_ctl.py, docs/REMOTE_CONTROL.md).

    python tools/init_control_branch.py              make it on origin if it does not exist yet (never overwrites)
    python tools/init_control_branch.py --dry-run    show what would be pushed, push nothing
    python tools/init_control_branch.py --remote R   another remote (default origin)

The branch holds two files, in one orphan commit (no history of main, nothing else):
  control/command.json   a blank command ({"id": "", "cmd": "none"}): the PC ignores it. The owner replaces it from the
                         GitHub app with the JSON the phone app's Remote page builds.
  control/README.md      the three steps, the commands, the rules.
Git plumbing only (hash-object, mktree, commit-tree, push): the work tree, the index and the current branch are never
touched. Run by the cloud monitor workflow on each run (a no-op once the branch exists) or on the PC.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = "control"
TEMPLATE = {"id": "", "ts": 0, "cmd": "none",
            "help": "Replace this file with the JSON from the phone app (System > Remote): kill | stop | flatten | update | "
                    "restart | status | start (Sim only). Each command runs once, within 15 min of its ts."}
README = """# Remote control (phone -> PC bot)

The PC bot reads `control/command.json` on this branch every ~60 s (engine/remote_ctl.py, on with LE_REMOTE=1).

1. Phone app -> System -> **Remote**: tap the command; it builds the JSON with a fresh id and time. Tap **Copy**.
2. Tap **Open the GitHub editor** (or open this file in the GitHub app: branch `control`, `control/command.json`, edit).
3. Select all, paste, **Commit changes**. Within about a minute the phone gets a notice with the result.

Commands: `kill` (flatten everything + stop + auto-resume off), `stop` (after flat; `"now": true` flattens first),
`flatten` (close the position, keep running, no new entry today), `update` / `restart` (only when flat, outside trading
hours), `status` (a fresh heartbeat + a notice), `start` (Sim accounts only, never a real account).

Rules: every command needs a new `id` and a `ts` within the last 15 minutes; an id runs once. No command changes the
config or the strategy, and nothing here can start a real account. See docs/REMOTE_CONTROL.md.
"""


def _git(args, cwd, inp: bytes | None = None, env=None):
    r = subprocess.run(["git", *args], cwd=cwd, input=inp, capture_output=True, timeout=120, env=env)
    return r.returncode, r.stdout.decode(errors="replace").strip(), r.stderr.decode(errors="replace").strip()


def exists(cwd: str, remote: str, branch: str = BRANCH) -> bool | None:
    c, out, _ = _git(["ls-remote", "--heads", remote, branch], cwd)
    if c:
        return None
    return bool(out)


def build_commit(cwd: str) -> str:
    """The orphan commit (control/command.json + control/README.md). Returns its sha."""
    def blob(data: bytes) -> str:
        c, out, err = _git(["hash-object", "-w", "--stdin"], cwd, inp=data)
        if c:
            raise RuntimeError(f"hash-object failed: {err}")
        return out
    b_cmd = blob((json.dumps(TEMPLATE, indent=1) + "\n").encode())
    b_md = blob(README.encode())
    c, sub, err = _git(["mktree"], cwd, inp=f"100644 blob {b_cmd}\tcommand.json\n100644 blob {b_md}\tREADME.md\n".encode())
    if c:
        raise RuntimeError(f"mktree failed: {err}")
    c, top, err = _git(["mktree"], cwd, inp=f"040000 tree {sub}\tcontrol\n".encode())
    if c:
        raise RuntimeError(f"mktree failed: {err}")
    env = {**os.environ, "GIT_AUTHOR_NAME": "liquidity-engine", "GIT_AUTHOR_EMAIL": "bot@liquidity-engine.local",
           "GIT_COMMITTER_NAME": "liquidity-engine", "GIT_COMMITTER_EMAIL": "bot@liquidity-engine.local"}
    c, commit, err = _git(["commit-tree", top, "-m", "control branch: blank remote command (tools/init_control_branch.py)"], cwd, env=env)
    if c:
        raise RuntimeError(f"commit-tree failed: {err}")
    return commit


def init(cwd: str = ROOT, remote: str = "origin", dry_run: bool = False, branch: str = BRANCH) -> dict:
    ex = exists(cwd, remote, branch)
    if ex is None:
        return {"ok": False, "status": "error", "reason": f"cannot reach {remote}"}
    if ex:
        return {"ok": True, "status": "exists", "reason": f"{remote}/{branch} already exists: not touched"}
    commit = build_commit(cwd)
    if dry_run:
        return {"ok": True, "status": "dry_run", "commit": commit[:10], "reason": f"would push {commit[:10]} to {remote}/{branch}"}
    # no --force: if someone created the branch meanwhile the push is refused and nothing is overwritten
    c, _, err = _git(["push", "-q", remote, f"{commit}:refs/heads/{branch}"], cwd)
    if c:
        return {"ok": False, "status": "error", "reason": f"push failed: {err[-200:]}"}
    return {"ok": True, "status": "created", "commit": commit[:10], "reason": f"created {remote}/{branch}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="create the control branch for the phone remote control")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cwd", default=ROOT)
    a = ap.parse_args(argv)
    r = init(a.cwd, a.remote, a.dry_run)
    print(f"control branch: {r['status']}: {r['reason']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
