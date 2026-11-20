"""Create the `control` branch for the phone remote control (engine/remote_ctl.py, docs/REMOTE_CONTROL.md).

    python tools/init_control_branch.py              make it if it does not exist yet (never overwrites), on the remote
                                                     the PC reads (engine/remote_ctl.control_source: "olympus" when
                                                     update_source.json names the backup repo, else origin)
    python tools/init_control_branch.py --dry-run    show what would be pushed, push nothing
    python tools/init_control_branch.py --remote R   another remote
    python tools/init_control_branch.py --write DIR  write the two files to DIR/control/ (no git; the lead can push them)

The branch holds two files, in one orphan commit (no history of main, nothing else):
  control/command.json   an expired no-op ({"id": "noop-0", "ts": 0, "cmd": "none"}): the PC ignores it silently. The
                         owner replaces it from the GitHub app with the JSON the phone app's Remote page builds
                         (https://github.com/dcondax1-wq/olympus/edit/control/control/command.json).
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
EDIT_URL = "https://github.com/dcondax1-wq/olympus/edit/control/control/command.json"
# an expired no-op: "cmd": "none" is skipped silently (engine/remote_ctl.screen 'blank'), and ts 0 is long expired anyway
TEMPLATE = {"id": "noop-0", "ts": 0, "cmd": "none",
            "help": "Replace this file with the JSON from the phone app (System > Remote): status | update | pause | flatten | "
                    "stop | kill | restart | start (Sim only). Each command runs once, within 15 min of its ts."}
README = """# Remote control (phone -> PC bot)

The PC bot reads `control/command.json` on this branch every ~60 s (engine/remote_ctl.py, on with LE_REMOTE=1).

1. Phone app -> System -> **Remote**: tap the command (Status, Update now, Pause, Flatten, ...). Tap **Copy and open GitHub**.
2. GitHub opens this file's editor (""" + EDIT_URL + """; in the GitHub app: branch `control`,
   `control/command.json`, the pencil). Select all, paste.
3. **Commit changes**. Within about a minute the phone gets a notice with the result.

The PC acts within ~60 s; update / restart only when the bot is flat, and never 01:50-16:00 ET on a weekday.

Commands: `kill` (flatten everything + stop + auto-resume off), `stop` (after flat; `"now": true` flattens first),
`flatten` (close the position, keep running, no new entry today), `update` / `restart` (only when flat, outside trading
hours), `status` (a fresh heartbeat + a notice), `pause` (no new entries until a time), `start` (Sim accounts only,
never a real account).

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


def default_remote(cwd: str = ROOT, env=None) -> str:
    """The remote the PC reads commands from (engine/remote_ctl.control_source): the backup repo's remote when
    update_source.json names it, else origin."""
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from engine.remote_ctl import control_source
        return control_source(cwd, env)["remote"]
    except Exception:
        return "origin"


def write_files(out_dir: str) -> list:
    """The branch's two files under out_dir/control/ (for a push with plain git). Returns the paths."""
    d = os.path.join(out_dir, "control")
    os.makedirs(d, exist_ok=True)
    paths = []
    for name, data in (("command.json", json.dumps(TEMPLATE, indent=1) + "\n"), ("README.md", README)):
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
        paths.append(p)
    return paths


def init(cwd: str = ROOT, remote: str | None = None, dry_run: bool = False, branch: str = BRANCH) -> dict:
    remote = remote or default_remote(cwd)
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
    ap.add_argument("--remote", default=None, help="default: the remote the PC reads (olympus with update_source.json)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cwd", default=ROOT)
    ap.add_argument("--write", metavar="DIR", help="only write DIR/control/command.json + README.md (no git)")
    a = ap.parse_args(argv)
    if a.write:
        for p in write_files(a.write):
            print(f"wrote {p}")
        return 0
    r = init(a.cwd, a.remote, a.dry_run)
    print(f"control branch: {r['status']}: {r['reason']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
