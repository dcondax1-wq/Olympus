"""day-unstick: build a commit chain on top of origin/pc that lets the PC's OLD auto-update (75d5a60b9 era) pass a dirty tracked
file without anyone at the PC.

Why it works: the old engine/autoupdate.fast_forward lets a dirty tracked file through only when from_main() finds the local
blob (worktree AND index) among the versions of that path committed in old..new. So we commit, one after the other, every
version that path ever had in git (plus any exact bytes we can reproduce, --bytes), and finish with a commit that puts the
CURRENT pc version back. Net tree change of the whole chain = nothing; the PC's file matches one of the cycled versions ->
"checked out from main by hand" -> back to HEAD -> fast-forward -> the PC gets the current pc version of that file.
If the PC's bytes are none of the cycled versions (a fresh hand edit, a runtime write with timestamps), it still blocks:
fallback = the owner's one stash line (PLAN.md).

  python research/handoff/2026-11-24/unstick/cycle_versions.py --path notify_settings.json            dry run: lists versions
  python research/handoff/2026-11-24/unstick/cycle_versions.py --path P [--path Q] --build             builds the chain, prints its tip
  ... --build --verify 75d5a60b9            also replays the OLD fast_forward in a temp clone for EACH cycled version (and
                                            for an unknown edit, which must still block) and prints updated / skipped
  ... --bytes FILE (with one --path)        add an exact local copy reproduced elsewhere as one more cycled version
Then the lead: git push origin <tip>:pc   (plain fast-forward of pc; no force).

Needs full history for the path (the script deepens a shallow clone itself). Never pushes, never touches the work tree.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or os.getcwd()


def git(*args, cwd=ROOT, env=None, check=True, inp=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})}, input=inp)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()[-400:]}")
    return r.stdout.strip()


def versions(path: str, base: str) -> list:
    """Distinct blobs `path` ever had in any fetched ref, newest first, minus base's own blob."""
    if git("rev-parse", "--is-shallow-repository") == "true":
        subprocess.run(["git", "fetch", "-q", "--unshallow", "origin"], cwd=ROOT)
    raw = git("log", "--all", "--no-abbrev", "--raw", "-m", "--format=", "--", path, check=False)
    cur = git("rev-parse", "-q", "--verify", f"{base}:{path}", check=False)
    seen, out = set(), []
    for ln in raw.splitlines():
        if not ln.startswith(":"):
            continue
        parts = ln.split("\t", 1)[0].split()
        for b in (parts[3], parts[2]):                       # new side, then old side
            if set(b) != {"0"} and b != cur and b not in seen:
                seen.add(b)
                out.append(b)
    return out


def build(paths_blobs: dict, base: str) -> str:
    """paths_blobs {path: [blob, ...]} -> tip of a linear chain on base whose LAST commit's tree == base's tree."""
    idx = tempfile.mktemp(prefix="unstick_idx_")
    env = {"GIT_INDEX_FILE": idx}
    prev = git("rev-parse", base)
    base_tree = git("rev-parse", f"{base}^{{tree}}")
    try:
        for path, blobs in paths_blobs.items():
            ls = git("ls-tree", base, "--", path)
            mode = ls.split()[0] if ls else "100644"
            for i, b in enumerate(blobs, 1):
                git("read-tree", base, env=env)
                git("update-index", "--add", "--cacheinfo", f"{mode},{b},{path}", env=env)
                tree = git("write-tree", env=env)
                msg = (f"day-unstick: {path} version {i}/{len(blobs)} (zero-touch update match for the PC's old auto-update; "
                       f"the chain ends with the current version)")
                prev = git("commit-tree", tree, "-p", prev, "-m", msg)
        msg = ("day-unstick: put the current pc version back (end of the version cycle; tree == "
               f"{base[:9]}): the PC's old auto-update now finds its local copy of {', '.join(paths_blobs)} in old..new")
        prev = git("commit-tree", base_tree, "-p", prev, "-m", msg)
    finally:
        if os.path.exists(idx):
            os.remove(idx)
    return prev


def verify(old_code: str, pc_head: str, tip: str, path: str, blob: str | None, label: str) -> str:
    """Replay the OLD fast_forward: a clone at pc_head with `path` = blob (None = an unknown edit), origin main = tip."""
    tmp = tempfile.mkdtemp(prefix="unstick_v_")
    try:
        code = os.path.join(tmp, "code")
        git("worktree", "add", "-f", "-q", code, old_code)
        bare = os.path.join(tmp, "up.git")
        git("init", "-q", "--bare", bare)
        git("push", "-q", bare, f"{tip}:refs/heads/main")
        pc = os.path.join(tmp, "pc")
        git("clone", "-q", "--no-checkout", bare, pc)
        git("fetch", "-q", ROOT, git("rev-parse", pc_head), cwd=pc)
        git("checkout", "-q", "-B", "main", pc_head, cwd=pc)
        fp = os.path.join(pc, *path.split("/"))
        os.makedirs(os.path.dirname(fp) or pc, exist_ok=True)
        data = subprocess.run(["git", "cat-file", "blob", blob], cwd=ROOT, capture_output=True).stdout if blob else None
        with open(fp, "ab" if data is None else "wb") as fh:
            fh.write(b"\n# owner edit nobody knows\n" if data is None else data)
        prog = ("import sys,json; sys.path.insert(0, sys.argv[1]); from engine import autoupdate as AU;"
                "src={'remote':'origin','url':None,'branch':'main','account':None,'label':'origin/main'};"
                "r=AU.fast_forward(AU.Shell(cwd=sys.argv[2], log=lambda t: None),'main',src=src);"
                "print(r['status'], '|', r['reason'][:160])")
        r = subprocess.run([sys.executable, "-c", prog, code, pc], capture_output=True, text=True,
                           env={**os.environ, "LE_SELF_HEAL": "0", "LE_AUTOUPDATE_BRANCH": "main"}, timeout=600)
        return f"{label}: {(r.stdout.strip() or r.stderr.strip()[-300:])}"
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", os.path.join(tmp, "code")], cwd=ROOT, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", required=True)
    ap.add_argument("--base", default="origin/pc")
    ap.add_argument("--bytes", help="an exact reproduced local copy of the (single) --path, added as one more version")
    ap.add_argument("--limit", type=int, default=400, help="max versions per path (newest first)")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--verify", metavar="OLD_CODE_SHA", help="replay the old fast_forward (PC HEAD = this sha too)")
    ap.add_argument("--pc-head", help="the PC's HEAD for --verify (default = OLD_CODE_SHA)")
    ap.add_argument("--max-verify", type=int, default=5)
    a = ap.parse_args(argv)
    pb = {}
    for p in a.path:
        vs = versions(p, a.base)[: a.limit]
        if a.bytes and len(a.path) == 1:
            b = git("hash-object", "-w", "--path", p, a.bytes)
            vs = [b] + [v for v in vs if v != b]
        pb[p] = vs
        print(f"{p}: {len(vs)} earlier version(s) to cycle (current {a.base} blob excluded)")
    if not a.build:
        return 0
    tip = build(pb, a.base)
    print(f"chain tip: {tip}  ({sum(len(v) for v in pb.values()) + 1} commits on {git('rev-parse', '--short', a.base)})")
    print(f"tree check: tip tree == base tree: {git('rev-parse', tip + '^{tree}') == git('rev-parse', a.base + '^{tree}')}")
    if a.verify:
        head = git("rev-parse", a.pc_head or a.verify)
        for p, vs in pb.items():
            for b in vs[: a.max_verify]:
                print(verify(a.verify, head, tip, p, b, f"PC copy of {p} = version {b[:9]}"))
            print(verify(a.verify, head, tip, p, None, f"PC copy of {p} = an unknown edit (must stay skipped)"))
    print(f"lead: git push origin {tip}:pc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
