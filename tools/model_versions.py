#!/usr/bin/env python3
"""The repo's own versions of the root live_model*.json files, for the zip updater: tools/model_versions.json (2026-11-14).

Why: nothing on the PC writes live_model*.json (only the repo does), so a PC copy whose values differ from a new code zip is
almost always an OLDER repo version, not the owner's edit. Without this list tools/update_from_zip.py kept every such copy
("YOURS kept"), so an owner-approved sizing change (lit_sizing two_week room_f 0.8 -> 0.4, commit f62e5dc) would never have
reached the PC through a zip. With it the updater REPLACES a copy whose SHA-256 is listed here (UTF-8 BOM removed, CRLF -> LF:
update_from_zip.model_sha) and keeps any other copy (the owner's own values).

    python tools/model_versions.py           rebuild tools/model_versions.json from git: every version of each root
                                             live_model*.json (the updater's is_model rule) in every commit reachable from HEAD
    python tools/model_versions.py --check   exit 1 when it is STALE (a version older than the current one is missing), else 0

Run it after every change to a live_model*.json and commit the list with the change. The CURRENT version need not be listed
(a zip of that commit carries it, so a PC that has it is "the same"); stale means an OLDER version is missing, one a PC may
still have. A rebuild keeps the entries the list already has (a shallow clone cannot see old commits): delete the file first to
start from git alone. second_model.json is not here: the updater replaces it like any code file (is_model is live_model*.json).
Checked by tests/test_update_from_zip.py; tools/make_backup.py refuses to zip a ref whose committed list is stale.
Stdlib only; needs git.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools import update_from_zip as U  # noqa: E402  (stdlib only: is_model, model_sha, parse_versions, VERSIONS_REL)

LIST_REL = U.VERSIONS_REL
HOW = ("sha256 of every committed version of each root live_model*.json (UTF-8 BOM removed, CRLF -> LF); "
       "built by tools/model_versions.py, read by tools/update_from_zip.py")


class GitError(RuntimeError):
    pass


def git(root: str, args: list, data: bytes | None = None) -> bytes:
    r = subprocess.run(["git", *args], cwd=root, input=data, capture_output=True)
    if r.returncode:
        msg = (r.stderr or r.stdout or b"").decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args[:2])} failed: {msg[-300:]}")
    return r.stdout


def model_names(root: str, ref: str = "HEAD") -> list:
    """The root live_model*.json files at `ref` (the zip updater's own rule: update_from_zip.is_model)."""
    names = git(root, ["ls-tree", "-z", "--name-only", ref]).decode("utf-8", "replace").split("\0")
    return sorted(n for n in names if n and U.is_model(n))


def blobs(root: str, specs) -> dict:
    """{spec: bytes} for each '<commit>:<path>' that names a file there (others are left out). Two git processes in all."""
    specs = list(dict.fromkeys(specs))
    if not specs:
        return {}
    lines = git(root, ["cat-file", "--batch-check"], ("\n".join(specs) + "\n").encode()).decode("utf-8", "replace").splitlines()
    oid_of = {}
    for spec, line in zip(specs, lines):
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            oid_of[spec] = parts[0]
    oids = list(dict.fromkeys(oid_of.values()))
    data = {}
    if oids:
        raw, i = git(root, ["cat-file", "--batch"], ("\n".join(oids) + "\n").encode()), 0
        for oid in oids:
            j = raw.index(b"\n", i)
            size = int(raw[i:j].split()[2])
            data[oid] = raw[j + 1:j + 1 + size]
            i = j + 1 + size + 1
    return {spec: data[oid] for spec, oid in oid_of.items()}


def history_versions(root: str, ref: str = "HEAD", names=None) -> dict:
    """{file: {sha256, ...}} of every version of each root live_model*.json in every commit reachable from `ref`."""
    names = model_names(root, ref) if names is None else names
    commits = git(root, ["rev-list", ref]).decode().split()
    out = {n: set() for n in names}
    for spec, data in blobs(root, [f"{c}:{n}" for c in commits for n in names]).items():
        out[spec.split(":", 1)[1]].add(U.model_sha(data))
    return out


def own_versions(root: str, ref: str | None, names) -> dict:
    """The versions a zip of `ref` carries itself: ref None = the files in the folder now (what the next commit holds)."""
    out = {}
    if ref is None:
        for n in names:
            try:
                with open(os.path.join(root, n), "rb") as fh:
                    out[n] = {U.model_sha(fh.read())}
            except OSError:
                out[n] = set()
        return out
    got = blobs(root, [f"{ref}:{n}" for n in names])
    return {n: ({U.model_sha(got[f"{ref}:{n}"])} if f"{ref}:{n}" in got else set()) for n in names}


def listed(root: str, ref: str | None = None) -> dict | None:
    """The list as the updater reads it (update_from_zip.parse_versions): ref None = the file in the folder, else the one in `ref`."""
    if ref is None:
        try:
            with open(os.path.join(root, *LIST_REL.split("/")), "rb") as fh:
                return U.parse_versions(fh.read())
        except OSError:
            return None
    return U.parse_versions(blobs(root, [f"{ref}:{LIST_REL}"]).get(f"{ref}:{LIST_REL}"))


def missing(root: str = ROOT, ref: str | None = None) -> list:
    """[(file, sha256)] a zip of `ref` must list but its list does not: every committed version (reachable from `ref`) except the
    zip's own. ref None = the folder as it is now (the list and the files on disk, the history of HEAD). [] = current."""
    head = ref or "HEAD"
    names = model_names(root, head)
    hist = history_versions(root, head, names)
    own = own_versions(root, ref, names)
    have = listed(root, ref) or {}
    return [(n, s) for n in names for s in sorted(hist[n] - own[n] - have.get(n.lower(), set()))]


def build(root: str = ROOT) -> dict:
    """The new list: every version in every commit reachable from HEAD, plus the entries the list already has for those files."""
    names = model_names(root, "HEAD")
    hist = history_versions(root, "HEAD", names)
    old = listed(root) or {}
    return {"v": 1, "how": HOW, "files": {n: sorted(hist[n] | old.get(n.lower(), set())) for n in names}}


def text_of(data: dict) -> str:
    return json.dumps(data, indent=1) + "\n"


def write(root: str, data: dict) -> bool:
    """Write the list (LF, UTF-8); False when the file already says exactly this."""
    path = os.path.join(root, *LIST_REL.split("/"))
    new = text_of(data)
    try:
        with open(path, encoding="utf-8") as fh:
            if fh.read() == new:
                return False
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new)
    os.replace(tmp, path)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rebuild / check tools/model_versions.json (see the top of this file).")
    ap.add_argument("--check", action="store_true", help="exit 1 when the list misses a version older than the current one")
    ap.add_argument("--root", default=ROOT, help=argparse.SUPPRESS)              # tests: a temp repo
    a = ap.parse_args(argv)
    try:
        if a.check:
            miss = missing(a.root)
            if miss:
                files = ", ".join(sorted({n for n, _s in miss}))
                print(f" [STALE] {LIST_REL} misses {len(miss)} older version{'s' if len(miss) != 1 else ''} of {files}: a zip would keep "
                      f"that copy on a PC as if the owner had made it. Run: python tools/model_versions.py (then commit it)")
                for n, s in miss[:10]:
                    print(f"         {n}  {s}")
                return 1
            have = listed(a.root) or {}
            print(f" [OK] {LIST_REL} is current (" + ", ".join(f"{n} {len(v)}" for n, v in sorted(have.items())) + " versions listed)")
            return 0
        data = build(a.root)
        changed = write(a.root, data)
        print(f" [OK] {LIST_REL} " + ("written" if changed else "already current") + ": "
              + ", ".join(f"{n} {len(v)} version{'s' if len(v) != 1 else ''}" for n, v in data["files"].items()))
        return 0
    except GitError as e:
        print(f" [FIX] {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
