#!/usr/bin/env python3
"""Land helper branches on Olympus pc: the repeatable part, with few tokens (the lead's tool, 2026-11-20).

    python tools/land_branch.py --preview day-x day-y ...   test-merge them IN ORDER in a temp git worktree from HEAD (your checkout,
                                                            index and branch are not touched; the worktree is removed at the end)
    python tools/land_branch.py day-x [--run]               land day-x here: a clean checkout or stop; fetch, record the base,
                                                            git merge --no-edit, the known conflicts resolved (any other: merge --abort
                                                            and the files), bump_versions --apply --base, the known fix-ups, the plan
    python tools/land_branch.py --after BASE [--run]        the same steps after a merge you finished by hand (bump, fix-ups, plan)
    python tools/land_branch.py --plan BASE [--run]         only the test plan for what changed since BASE
    --run          run smoke + the non-browser suites of the plan (+ the bot checks), --budget 900 s each; browser suites stay
                   printed commands under flock; the two files smoke rewrites are put back
    --why          also print which changed file put each suite in the plan
    --remote NAME  default: the remote whose URL is dcondax1-wq/Olympus    --no-fetch  use the refs you have    --root DIR  the checkout
A helper branch that was never pushed is landed from the local branch of that name. Landing also says when olympus/pc is ahead of
HEAD (ship.py's push would be refused) and which generated files (write-ups INDEX.md, vault) are stale.

Per branch it prints: commits, files by top folder, conflicts, BOT FILES (engine/live.py, lit_live, lit, ninjatrader, second,
account_b, autoupdate, generated_files, notify, engine/kalshi_*.py, server.py, live_model*.json, second_model.json, accounts/*.json,
scripts/*.ps1, *.bat: the extra bot checks are added to the plan), LEAD-ONLY files (any sw.js, tools/build_web_dashboard.py,
jarvis/apps.js, olympus.js), other service workers (bump_versions does not bump them), its research/handoff/<day>/<id>/LEAD_WIRES.md.
Conflicts resolved on their own (anything else stops): STATE.md (union of lines, ours first, order kept), tests/run_area.py (union of
the appended AREAS / PARTS / SLOW lines, only when the conflict is made of those), research/writeups/INDEX.md and vault/** (theirs,
then rebuilt by tools/writeups_index.py / tools/obsidian_brain.py), tools/web_public/business/decisions.json (cards merged by id; a
card changed on both sides: stop). A resolved merge is committed with git's own message, as git merge --no-edit does when clean.
Fix-ups after bump_versions (it gets these wrong): kalshi/sw.js cache = the kalshi.css / kalshi.js ?v; the two launcher.js copies
byte-identical with apps-list ?v = the highest lN; gate/index.html root-relative tags whose file changed but whose ?v did not move
(reported); tests/run_area.py lines after the main guard (they never run as a script: moved above it).
The plan: changed files -> the suites that name them (path, module, its own test) -> their tests/run_area.py areas; a suite is a
browser suite when it (or a tests/ helper it imports) imports playwright or the browser kit, or drives node Playwright.
Never commits the bump / fix-ups, never pushes, never runs ship.py: the lead reviews, commits and ships.
Tests: python -X utf8 -m tests.test_land_branch
"""
from __future__ import annotations

import argparse
import ast
import collections
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize
import types
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME_REPO = "dcondax1-wq/olympus"
MARK = 15                                             # conflict-marker size of our own 3-way runs: never mistaken for a text line
LOCK = "flock -w 2400 /tmp/olympus_browser.lock"
SMOKE = "python tests/smoke.py"
BOT_CHECKS = (("lit_live --quick", ["-X", "utf8", "-m", "tests.test_lit_live", "--quick"], "python -X utf8 -m tests.test_lit_live --quick"),
              ("ninjatrader --selftest", ["-m", "engine.ninjatrader", "--selftest"], "python -m engine.ninjatrader --selftest"))
DROPPINGS = ("data/GEX_1d.csv", "tools/web_hub_snapshot.json")          # smoke rewrites them; never committed (land-helper skill)
PIN_FIXTURES = {"tests/test_bump_versions.py", "tests/test_add_kit_tags.py", "tests/test_release_manifest.py", "tests/test_land_branch.py"}
BOT_GLOBS = ("engine/live.py", "engine/lit_live.py", "engine/lit.py", "engine/ninjatrader.py", "engine/second.py", "engine/account_b.py",
             "engine/autoupdate.py", "engine/generated_files.py", "engine/notify.py", "engine/kalshi_*.py", "server.py", "live_model*.json",
             "second_model.json", "accounts/*.json", "scripts/*.ps1", "**/*.bat")
LEAD_GLOBS = ("**/sw.js", "tools/build_web_dashboard.py", "tools/web_public/jarvis/apps.js", "**/olympus.js")
STATE, RUN_AREA, INDEX, DECISIONS = "STATE.md", "tests/run_area.py", "research/writeups/INDEX.md", "tools/web_public/business/decisions.json"
GENERATORS = ((INDEX, "tools/writeups_index.py"), ("vault/", "tools/obsidian_brain.py"))       # a generated file -> its generator
KAL_SW, KAL_IDX = "tools/web_public/kalshi/sw.js", "tools/web_public/kalshi/index.html"
KAL_FILES = {KAL_IDX, "tools/web_public/kalshi/kalshi.css", "tools/web_public/kalshi/kalshi.js"}
LAUNCHERS = ("tools/web_public/launcher.js", "web_next/js/next/launcher.js")
GATE = "tools/web_public/gate/index.html"
TAG = r"[A-Za-z]*\d+"
WHY = False                                           # --why: print the changed file behind each suite of the plan


def _glob_re(pat):
    out, i = "", 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pat[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(pat[i]), i + 1
    return re.compile(out + r"\Z")


BOT_RE = [_glob_re(p) for p in BOT_GLOBS]
LEAD_RE = [_glob_re(p) for p in LEAD_GLOBS]


def is_bot(path: str) -> bool:
    return any(r.match(path) for r in BOT_RE)


def is_lead_only(path: str) -> bool:
    return any(r.match(path) for r in LEAD_RE)


def is_other_worker(path: str) -> bool:
    """A service worker that is not a sw.js (hub/manual-sw.js, push-sw.js): bump_versions has no rule for its cache name."""
    return bool(re.search(r"[-_.]sw\.js\Z", posixpath.basename(path))) and path.startswith(("tools/web_public/", "web_next/"))


def tag_num(tag: str) -> int:
    m = re.fullmatch(r"[A-Za-z_-]*(\d+)", tag or "")
    return int(m.group(1)) if m else -1


def bump_tag(tag: str) -> str:
    m = re.fullmatch(r"([A-Za-z_-]*)(\d+)", tag or "")
    return m.group(1) + str(int(m.group(2)) + 1).zfill(len(m.group(2))) if m else tag


def short(xs, n=6, sep=", "):
    xs = list(xs)
    return sep.join(xs[:n]) + (f" (+{len(xs) - n} more)" if len(xs) > n else "")


def top_folder(path: str) -> str:
    p = path.split("/")
    if len(p) == 1:
        return "(root)"
    if p[0] == "tools" and p[1] == "web_public":
        return "web_public/" + p[2] if len(p) > 3 else "web_public"
    return p[0]


def by_top(files, n=8) -> str:
    c = collections.Counter(top_folder(f) for f in files).most_common()
    return ", ".join(f"{k} {v}" for k, v in c[:n]) + (f" (+{len(c) - n} more)" if len(c) > n else "")


def read(root, rel):
    try:
        with open(os.path.join(root, *rel.split("/")), encoding="utf-8", newline="") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def _read_abs(path) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def write(root, rel, text):
    with open(os.path.join(root, *rel.split("/")), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


# ------------------------------------------------------------------------------------------------------------------------- git
class GitError(RuntimeError):
    pass


class Git:
    def __init__(self, root, temp=False):
        self.root = root
        self.pre = ["git", "-C", root, "-c", "core.quotepath=false"]
        if temp:                       # the preview's throwaway worktree: no hooks, no rerere, a stand-in identity, no signing
            self.pre += ["-c", "core.hooksPath=/dev/null", "-c", "rerere.enabled=false", "-c", "user.name=land-preview",
                         "-c", "user.email=land-preview@localhost", "-c", "commit.gpgsign=false"]

    def run(self, *args, check=True):
        r = subprocess.run(self.pre + [str(a) for a in args], capture_output=True)
        res = types.SimpleNamespace(code=r.returncode, out=r.stdout.decode("utf-8", "replace"), err=r.stderr.decode("utf-8", "replace"))
        if check and r.returncode != 0:
            raise GitError(f"git {' '.join(str(a) for a in args[:3])}: {(res.err or res.out).strip()[-300:]}")
        return res

    def out(self, *args) -> str:
        return self.run(*args).out.strip()

    def ok(self, *args) -> bool:
        return self.run(*args, check=False).code == 0

    def names(self, *args) -> list:            # a -z listing (paths with spaces / unicode stay whole)
        return [p for p in self.run(*args).out.split("\0") if p]

    def blob(self, sha) -> str:
        return self.run("cat-file", "blob", sha).out

    def show(self, rev, rel):
        r = self.run("show", f"{rev}:{rel}", check=False)
        return r.out if r.code == 0 else None

    def head(self) -> str:
        return self.out("rev-parse", "HEAD")

    def merging(self) -> bool:
        return self.ok("rev-parse", "-q", "--verify", "MERGE_HEAD")

    def status(self) -> list:                    # [(XY, path)] of tracked changes (-z: no quoting; a rename gives its new path)
        out, recs = [], self.run("status", "--porcelain", "-z", "--untracked-files=no").out.split("\0")
        i = 0
        while i < len(recs):
            rec = recs[i]
            i += 1
            if len(rec) > 3:
                out.append((rec[:2], rec[3:]))
                if set(rec[:2]) & {"R", "C"}:
                    i += 1                           # the rename's old path follows
        return out

    def changed_since(self, base) -> list:       # the working tree against the base, deletions and both sides of a rename included
        return self.names("diff", "--name-only", "--no-renames", "-z", base)

    def unmerged(self) -> dict:                  # path -> {stage: blob sha}
        st = {}
        for rec in self.run("ls-files", "-u", "-z").out.split("\0"):
            if "\t" in rec:
                meta, path = rec.split("\t", 1)
                st.setdefault(path, {})[int(meta.split()[2])] = meta.split()[1]
        return st


def repo_of(url: str) -> str:
    u = (url or "").strip().lower().rstrip("/")
    u = u[:-4] if u.endswith(".git") else u
    return "/".join(u.split("github.com", 1)[-1].lstrip(":/").split("/")[-2:])


def home_remote(git) -> str | None:
    names = git.out("remote").split()
    for n in names:
        if repo_of(git.run("remote", "get-url", n, check=False).out) == HOME_REPO:
            return n
    return "olympus" if "olympus" in names else ("origin" if "origin" in names else None)


def get_ref(git, remote, name, fetch=True):
    """(ref, note) of a helper branch: fetched from the home remote into refs/remotes/<remote>/<name>, else a local branch of that
    name (a helper that committed here without pushing). A failed fetch never falls back to an old remote-tracking copy."""
    nm = name[len(remote) + 1:] if remote and name.startswith(remote + "/") else name
    why = ""
    if remote and fetch:
        r = git.run("fetch", "-q", remote, f"+refs/heads/{nm}:refs/remotes/{remote}/{nm}", check=False)
        if r.code == 0:
            return f"refs/remotes/{remote}/{nm}", ""
        why = ((r.err or r.out).strip().splitlines() or [""])[-1][:120]
    elif remote and git.ok("rev-parse", "-q", "--verify", f"refs/remotes/{remote}/{nm}^{{commit}}"):
        return f"refs/remotes/{remote}/{nm}", "not fetched"
    if git.ok("rev-parse", "-q", "--verify", f"refs/heads/{nm}^{{commit}}"):
        return f"refs/heads/{nm}", "local branch"
    raise GitError(f"{nm}: not on {remote or 'any remote'}{' (' + why + ')' if why else ''} and no local branch")


def today_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:  # noqa: BLE001 - no tz database: UTC is close enough for a folder name
        return dt.datetime.now(dt.timezone.utc).date().isoformat()


def summarize(git, ref, name) -> dict:
    sha = git.out("rev-parse", ref)
    mb = git.out("merge-base", "HEAD", ref)
    files = git.names("diff", "--name-only", "--no-renames", "-z", mb, ref)
    bid = re.sub(r"^(day|night|local)-", "", name.split("/")[-1])
    wires = [f for f in files if f.startswith("research/handoff/") and f.endswith("/LEAD_WIRES.md")]
    exp = f"research/handoff/{today_et()}/{bid}/LEAD_WIRES.md"
    if exp not in wires and git.ok("cat-file", "-e", f"{sha}:{exp}"):
        wires.append(exp)
    return {"sha": sha, "commits": int(git.out("rev-list", "--count", f"HEAD..{ref}")), "files": files,
            "bot": [f for f in files if is_bot(f)], "lead": [f for f in files if is_lead_only(f)],
            "workers": [f for f in files if is_other_worker(f)], "wires": wires}


def summary_lines(s) -> list:
    out = [f"  {s['commits']} commit(s), {len(s['files'])} file(s): {by_top(s['files'])}"]
    if s["bot"]:
        out.append(f"  BOT FILES: {short(s['bot'])}  (bot checks added to the tests)")
    if s["lead"]:
        out.append(f"  LEAD-ONLY: {short(s['lead'])}")
    if s["workers"]:
        out.append(f"  other service worker(s): {short(s['workers'])} (bump_versions does not bump them: check the cache name)")
    for w in s["wires"]:
        out.append(f"  wires: {w}")
    return out


# -------------------------------------------------------------------------------------------------------------- the resolvers
class Unresolvable(Exception):
    def __init__(self, paths, why):
        super().__init__(why)
        self.paths, self.why = list(paths), why


def parse_conflicts(text: str, size: int = 7) -> list:
    """[('text', lines)] and [('conflict', ours, base, theirs)] segments of a file with conflict markers (merge or diff3 style)."""
    def mark(line, ch):
        s = line.rstrip("\r\n")
        return s.startswith(ch * size) and (len(s) == size or s[size] == " ")
    segs, buf, lines, i = [], [], text.splitlines(keepends=True), 0
    while i < len(lines):
        if not mark(lines[i], "<"):
            buf.append(lines[i])
            i += 1
            continue
        if buf:
            segs.append(("text", buf))
            buf = []
        ours, base, theirs, cur, i = [], [], [], None, i + 1
        cur = ours
        while i < len(lines) and not mark(lines[i], ">"):
            if mark(lines[i], "|"):
                cur = base
            elif lines[i].rstrip("\r\n") == "=" * size:
                cur = theirs
            else:
                cur.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError("a conflict with no end marker")
        segs.append(("conflict", ours, base, theirs))
        i += 1
    if buf:
        segs.append(("text", buf))
    return segs


def union_text(text: str, size: int = 7, file_scope: bool = False, allowed=None, collect=None):
    """Every conflict -> ours, then the lines of theirs that ours does not have (order kept; blank lines are never 'duplicates').
    file_scope: a line of theirs already ANYWHERE in the file is dropped (a line one side moved). allowed(line) -> False on a
    non-blank line of either side raises Unresolvable. Returns (text, number of their lines kept); `collect` (a list) gets them."""
    segs = parse_conflicts(text, size)
    seen = set()
    if file_scope:
        for s in segs:
            seen.update(x.strip() for x in s[1] if x.strip())
    out, kept = [], 0
    for s in segs:
        if s[0] == "text":
            out.extend(s[1])
            continue
        _, ours, _base, theirs = s
        if allowed is not None:
            bad = [x.strip() for x in ours + theirs if x.strip() and not allowed(x)]
            if bad:
                raise Unresolvable([], f"a conflict outside the appended lines: {bad[0][:80]}")
        have = (set(seen) if file_scope else set()) | {x.strip() for x in ours if x.strip()}
        add = [x for x in theirs if not x.strip() or x.strip() not in have]
        if not any(x.strip() for x in add):
            add = []
        while add and not add[0].strip() and (not ours or not ours[-1].strip()):
            add.pop(0)                                       # no double blank line where the two sides meet
        block = list(ours)
        if block and add and not block[-1].endswith("\n"):
            block[-1] += "\n"
        out.extend(block + add)
        kept += sum(1 for x in add if x.strip())
        seen.update(x.strip() for x in add if x.strip())
        if collect is not None:
            collect.extend(x.strip() for x in add if x.strip())
    return "".join(out), kept


def merge_file(ours: str, base: str, theirs: str, size: int = MARK) -> str:
    """git merge-file (diff3 markers of `size`) on three texts; byte-exact (CRLF kept)."""
    with tempfile.TemporaryDirectory(prefix="land-mf-") as d:
        paths = []
        for nm, t in (("ours", ours), ("base", base), ("theirs", theirs)):
            p = os.path.join(d, nm)
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(t)
            paths.append(p)
        r = subprocess.run(["git", "merge-file", "-p", "--diff3", f"--marker-size={size}", "-L", "ours", "-L", "base", "-L", "theirs", *paths],
                           capture_output=True)
        if r.returncode < 0 or r.returncode > 127:
            raise Unresolvable([], f"git merge-file failed: {r.stderr.decode('utf-8', 'replace').strip()[:120]}")
        return r.stdout.decode("utf-8", "replace")


AREA_LINE = re.compile(r"\s*(?:#|(?:AREAS|PARTS|SLOW)\b)")
_MISSING, _CLASH = object(), object()


def _merge3(b, o, t):
    if o == t:
        return o
    if o == b:
        return t
    if t == b:
        return o
    return _CLASH


def merge_decisions(base: str, ours: str, theirs: str):
    """business/decisions.json: the cards merged by id (ours' order, their new cards after); a card changed on BOTH sides (or added
    on both with different text) -> Unresolvable. Top-level keys merged the same way ('updated': the later date)."""
    try:
        B = json.loads(base) if base.strip() else {}
        O, T = json.loads(ours), json.loads(theirs)
    except ValueError as e:
        raise Unresolvable([DECISIONS], f"decisions.json is not JSON ({e})")
    if not all(isinstance(x, dict) for x in (B, O, T)):
        raise Unresolvable([DECISIONS], "decisions.json is not an object")

    def by_id(lst, side):
        d, order = {}, []
        for it in lst or []:
            if not isinstance(it, dict) or "id" not in it:
                raise Unresolvable([DECISIONS], f"a card without an id on {side}")
            if it["id"] in d:
                raise Unresolvable([DECISIONS], f"card '{it['id']}' twice on {side}")
            d[it["id"]] = it
            order.append(it["id"])
        return d, order

    bi, _ = by_id(B.get("items"), "base")
    oi, oo = by_id(O.get("items"), "ours")
    ti, to = by_id(T.get("items"), "theirs")
    items, clash = [], []
    for i in oo + [i for i in to if i not in oi]:
        v = _merge3(bi.get(i, _MISSING), oi.get(i, _MISSING), ti.get(i, _MISSING))
        if v is _CLASH:
            clash.append(i)
        elif v is not _MISSING:
            items.append(v)
    if clash:
        raise Unresolvable([DECISIONS], f"decisions.json card(s) changed on both sides: {', '.join(clash)}")
    out = {}
    for k in list(O) + [k for k in T if k not in O]:
        if k == "items":
            out[k] = items
            continue
        v = _merge3(B.get(k, _MISSING), O.get(k, _MISSING), T.get(k, _MISSING))
        if v is _CLASH:
            if k == "updated" and isinstance(O.get(k), str) and isinstance(T.get(k), str):
                v = max(O[k], T[k])
            else:
                raise Unresolvable([DECISIONS], f"decisions.json '{k}' changed on both sides")
        if v is not _MISSING:
            out[k] = v
    if "items" not in out:
        out["items"] = items
    m = re.match(r"\{\r?\n( +)\"", ours)
    text = json.dumps(out, indent=len(m.group(1)) if m else 1, ensure_ascii=not any(ord(c) > 127 for c in ours + theirs)) + "\n"
    new = [i for i in to if i not in oi and i not in bi]
    return text, f"cards by id (+{len(new)} of theirs{': ' + short(new, 4) if new else ''})"


def _is_main_guard(node) -> bool:
    t = getattr(node, "test", None)
    return (isinstance(node, ast.If) and isinstance(t, ast.Compare) and isinstance(t.left, ast.Name) and t.left.id == "__name__"
            and len(t.comparators) == 1 and isinstance(t.comparators[0], ast.Constant) and t.comparators[0].value == "__main__")


@contextlib.contextmanager
def repo_path(root):
    """sys.path as when tests/run_area.py runs from `root` (its tests/ helpers and the repo importable), put back after."""
    saved = list(sys.path)
    sys.path[:0] = [os.path.join(root, "tests"), root]
    try:
        yield
    finally:
        sys.path[:] = saved


def check_run_area(text: str, root=ROOT):
    """tests/run_area.py must compile and its module code (the AREAS lines) must run."""
    try:
        code = compile(text, RUN_AREA, "exec")
        with repo_path(root):
            exec(code, {"__name__": "_land_check", "__file__": os.path.join(root, RUN_AREA)})   # noqa: S102 - the repo's own file
    except Exception as e:  # noqa: BLE001
        raise Unresolvable([RUN_AREA], f"tests/run_area.py breaks after the union: {type(e).__name__}: {e}")


def move_tail(text: str):
    """tests/run_area.py: AREAS / PARTS / SLOW lines (and their comments) AFTER `if __name__ == "__main__":` never run when the file is
    run as a script; move them to just after the last module-level statement before the first def. (text, lines moved, note)."""
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return text, 0, f"run_area: does not parse ({e.msg} line {e.lineno})"
    body = tree.body
    gi = next((i for i, n in enumerate(body) if _is_main_guard(n)), None)
    if gi is None or gi == len(body) - 1:                  # no statement after the guard (a comment there runs nothing anyway)
        return text, 0, ""
    lines = text.splitlines(keepends=True)
    for n in body[gi + 1:]:
        if not re.match(r"(AREAS|PARTS|SLOW)\b", lines[n.lineno - 1].lstrip()):
            return text, 0, f"run_area: code after the main guard that is not an AREAS line (line {n.lineno}): move it by hand"
    gend = body[gi].end_lineno
    fi = next((i for i, n in enumerate(body[:gi]) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))), gi)
    anchor = body[fi - 1].end_lineno if fi > 0 else 0
    have = {x.strip() for x in lines[:gend] if x.strip()}
    moved = [x if x.endswith("\n") else x + "\n" for x in lines[gend:] if x.strip() and x.strip() not in have]
    new = "".join(lines[:anchor] + moved + lines[anchor:gend])
    if not new.endswith("\n"):
        new += "\n"
    n_tail = sum(1 for x in lines[gend:] if x.strip())
    return new, n_tail, f"run_area: {n_tail} line(s) after the main guard moved above it ({n_tail - len(moved)} already there)"


def auto_kind(path: str):
    if path == STATE:
        return "union"
    if path == RUN_AREA:
        return "areas"
    if path == DECISIONS:
        return "json"
    if path == INDEX or path.startswith("vault/"):
        return "theirs"
    return None


def run_generator(root, tool, timeout=600):
    """(ok, last line) of one of the repo's generators, run from its root."""
    if not os.path.isfile(os.path.join(root, tool)):
        return None, "no generator"
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", tool], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timed out ({timeout} s)"
    return r.returncode == 0, ((r.stdout + r.stderr).strip().splitlines() or [""])[-1][:140]


def resolve_all(git, root, st: dict):
    """Resolve every unmerged path of `st` (path -> stages) or raise Unresolvable (nothing written then for the unknown files:
    the caller aborts the merge). Returns [(path, how)]."""
    kinds = {p: auto_kind(p) for p in st}
    manual = sorted(p for p, k in kinds.items() if k is None)
    if manual:
        raise Unresolvable(manual, "conflicts outside the files this tool resolves")
    done = []
    for p in sorted(p for p, k in kinds.items() if k in ("union", "areas", "json")):
        s = st[p]
        if 2 not in s or 3 not in s:
            raise Unresolvable([p], f"{p}: deleted on one side")
        ours, theirs, base = git.blob(s[2]), git.blob(s[3]), (git.blob(s[1]) if 1 in s else "")
        try:
            if kinds[p] == "json":
                text, how = merge_decisions(base, ours, theirs)
            elif kinds[p] == "union":
                got = []
                text, kept = union_text(merge_file(ours, base, theirs), MARK, collect=got)
                how = f"union (+{kept} line(s) of theirs" + (": " + " | ".join(x[:70] for x in got[:2]) if got else "") + ")"
            else:
                text, kept = union_text(merge_file(ours, base, theirs), MARK, file_scope=True, allowed=AREA_LINE.match)
                text, moved, _ = move_tail(text)
                check_run_area(text, root)
                how = f"union of the AREAS lines (+{kept} of theirs{', moved above the main guard' if moved else ''})"
        except Unresolvable as e:
            raise Unresolvable([p], f"{p}: {e.why}")
        write(root, p, text)
        git.run("add", "--", p)
        done.append((p, how))
    th = sorted(p for p, k in kinds.items() if k == "theirs")
    if th:
        keep, gone = [p for p in th if 3 in st[p]], [p for p in th if 3 not in st[p]]
        for i in range(0, len(keep), 200):
            git.run("checkout", "--theirs", "--", *keep[i:i + 200])
            git.run("add", "--", *keep[i:i + 200])
        for i in range(0, len(gone), 200):
            git.run("rm", "-q", "--", *gone[i:i + 200])
        for target, tool in GENERATORS:
            hit = [p for p in th if p == target or (target.endswith("/") and p.startswith(target))]
            if not hit:
                continue
            ok, last = run_generator(root, tool)
            if ok:
                git.run("add", "-A", "--", target.rstrip("/"))
                done.append((f"{target.rstrip('/')} ({len(hit)} file(s))", f"theirs, rebuilt by {tool}"))
            else:
                done.append((f"{target.rstrip('/')} ({len(hit)} file(s))", f"theirs ({tool}: {last}; rebuild by hand)"))
    return done


@dataclass
class MergeResult:
    status: str                                       # clean | uptodate | resolved | stop | failed
    conflicts: list = field(default_factory=list)
    resolved: list = field(default_factory=list)
    manual: list = field(default_factory=list)
    why: str = ""


def do_merge(git, root, ref) -> MergeResult:
    before = git.head()
    name = re.sub(r"^refs/(?:remotes|heads)/", "", ref)       # git's own message: "Merge remote-tracking branch 'olympus/day-x' into pc"
    same = git.run("rev-parse", "-q", "--verify", f"{name}^{{commit}}", check=False).out.strip() == git.out("rev-parse", f"{ref}^{{commit}}")
    r = git.run("merge", "--no-edit", name if same else ref, check=False)
    if r.code == 0:
        return MergeResult("uptodate" if git.head() == before else "clean")
    if not git.merging():
        return MergeResult("failed", why=(r.err or r.out).strip()[-400:])
    st = git.unmerged()
    res = MergeResult("stop", conflicts=sorted(st))
    try:
        res.resolved = resolve_all(git, root, st)
        left = sorted(git.unmerged())
        if left:
            raise Unresolvable(left, "still unmerged after the resolvers")
        git.run("commit", "-q", "--no-edit", "--cleanup=strip")
    except (Unresolvable, GitError) as e:
        git.run("merge", "--abort", check=False)
        res.manual = getattr(e, "paths", []) or res.conflicts
        res.why = getattr(e, "why", str(e))
        res.resolved = []
        return res
    res.status = "resolved"
    return res


def merge_lines(m: MergeResult) -> list:
    if m.status == "clean":
        return ["  merge: clean"]
    if m.status == "uptodate":
        return ["  merge: already in HEAD (nothing to land)"]
    if m.status == "failed":
        return [f"  STOP: git merge failed before any conflict: {m.why[-200:]}"]
    if m.status == "resolved":
        return ["  merge: conflicts resolved: " + "; ".join(f"{p} {how}" for p, how in m.resolved[:6])]
    out = [f"  STOP: {m.why}", f"  conflicts ({len(m.conflicts)}): {short(m.conflicts, 10)}"]
    if m.manual and m.manual != m.conflicts:
        out.append(f"  needs a hand: {short(m.manual, 10)}")
    return out + ["  (merge aborted: nothing changed; merge by hand, then python tools/land_branch.py --after <base>)"]


# ---------------------------------------------------------------------------------------------------------------- the fix-ups
def repin(root, pairs, cache_lines=False) -> list:
    """Exact replacements of version pins in tests/*.py (the synthetic fixtures of the release tools excluded). cache_lines: only on
    lines that name CACHE / caches.open. Returns 'tests/x.py:N' of every change."""
    hits, tdir = [], os.path.join(root, "tests")
    if not pairs or not os.path.isdir(tdir):
        return hits
    for fn in sorted(os.listdir(tdir)):
        rel = f"tests/{fn}"
        if not fn.endswith(".py") or rel in PIN_FIXTURES:
            continue
        t = read(root, rel) or ""
        if not any(o in t for o, _ in pairs):
            continue
        lines = t.split("\n")
        for i, ln in enumerate(lines):
            if cache_lines and not re.search(r"CACHE|caches\.open", ln):
                continue
            new = ln
            for o, n in pairs:
                new = re.sub(r"(?<![\w-])" + re.escape(o) + r"(?![\w])", n, new)
            if new != ln:
                lines[i] = new
                hits.append(f"{rel}:{i + 1}")
        if any(h.startswith(rel + ":") for h in hits):
            write(root, rel, "\n".join(lines))
    return hits


@dataclass
class Fix:
    notes: list = field(default_factory=list)
    written: list = field(default_factory=list)
    reverted: bool = False                            # kalshi: the cache went back to the css/js value (bump --check flags it)


KAL_CACHE_RE = re.compile(r"(const CACHE = 'kalshi-)(" + TAG + r")(';)")
KAL_TAG_RE = re.compile(r"((?<![\w-])kalshi\.(?:css|js)\?v=)(" + TAG + r")")


def fix_kalshi(root, merged: set) -> Fix:
    """kalshi/sw.js `const CACHE = 'kalshi-<v>'` must equal the ?v of kalshi.css AND kalshi.js in kalshi/index.html and in the
    worker's SHELL. When they differ: index.html or kalshi.css/js changed in the merge -> every css/js ?v (both files) and the cache
    go to the highest of them (never back to a used tag); else the cache goes back to the css/js value."""
    f = Fix()
    sw, idx = read(root, KAL_SW), read(root, KAL_IDX)
    if sw is None or idx is None:
        return f
    m = KAL_CACHE_RE.search(sw)
    if not m:
        f.notes.append("kalshi: no `const CACHE = 'kalshi-...'` line in kalshi/sw.js (check by hand)")
        return f
    cache = m.group(2)
    tags = [t for _, t in KAL_TAG_RE.findall(idx)] + [t for _, t in KAL_TAG_RE.findall(sw)]
    if not tags or all(t == cache for t in tags):
        return f
    if merged & KAL_FILES:
        target = max(tags + [cache], key=tag_num)
        new_idx = KAL_TAG_RE.sub(lambda mm: mm.group(1) + target, idx)
        new_sw = KAL_CACHE_RE.sub(lambda mm: mm.group(1) + target + mm.group(3), KAL_TAG_RE.sub(lambda mm: mm.group(1) + target, sw), count=1)
        pins = [(f"kalshi.{e}?v={t}", f"kalshi.{e}?v={target}") for t in sorted(set(tags) - {target}) for e in ("css", "js")]
        f.notes.append(f"kalshi: css/js ?v {'/'.join(sorted(set(tags), key=tag_num))} -> {target}, cache kalshi-{cache} -> kalshi-{target}"
                       if cache != target else f"kalshi: css/js ?v {'/'.join(sorted(set(tags), key=tag_num))} -> {target} (= the cache)")
    else:
        if len(set(tags)) != 1:
            f.notes.append(f"kalshi: css/js ?v disagree ({'/'.join(sorted(set(tags)))}) and none changed in the merge: fix by hand")
            return f
        target, new_idx, pins = tags[0], idx, []
        new_sw = KAL_CACHE_RE.sub(lambda mm: mm.group(1) + target + mm.group(3), sw, count=1)
        f.reverted = True
        f.notes.append(f"kalshi: cache kalshi-{cache} -> kalshi-{target} (back to the css/js ?v: neither changed in the merge)")
    for rel, old, new in ((KAL_IDX, idx, new_idx), (KAL_SW, sw, new_sw)):
        if new != old:
            write(root, rel, new)
            f.written.append(rel)
    hits = repin(root, pins) + (repin(root, [(f"kalshi-{cache}", f"kalshi-{target}")], cache_lines=True) if cache != target else [])
    if hits:
        f.notes.append(f"kalshi: test pins moved: {short(hits, 4)}")
    return f


APPS_LINE_RE = re.compile(r"(isPC \? '/js/next/apps-list\.js\?v=)(" + TAG + r")(' : 'olympus/apps-list\.js\?v=)(" + TAG + r")(')")


def fix_launcher(root) -> Fix:
    """tools/web_public/launcher.js and web_next/js/next/launcher.js must be byte-identical. When they differ ONLY in the apps-list
    line (or its two sides disagree), both sides of that ternary in both files -> the highest lN found; otherwise report."""
    f = Fix()
    a, b = read(root, LAUNCHERS[0]), read(root, LAUNCHERS[1])
    if a is None or b is None:
        return f
    ma, mb = list(APPS_LINE_RE.finditer(a)), list(APPS_LINE_RE.finditer(b))
    if len(ma) != 1 or len(mb) != 1:
        if a != b:
            f.notes.append("launcher: the two launcher.js copies differ and the apps-list line is not found once in each: copy by hand")
        return f
    tags = [ma[0].group(2), ma[0].group(4), mb[0].group(2), mb[0].group(4)]
    if a == b and tags[0] == tags[1] and re.fullmatch(r"l\d+", tags[0]):
        return f
    norm = APPS_LINE_RE.sub(r"\1#\3#\5", a), APPS_LINE_RE.sub(r"\1#\3#\5", b)
    if norm[0] != norm[1]:
        f.notes.append("launcher: tools/web_public/launcher.js and web_next/js/next/launcher.js differ beyond the apps-list line: "
                       "make them byte-identical by hand")
        return f
    ls = [t for t in tags if re.fullmatch(r"l\d+", t)]
    if not ls:
        f.notes.append(f"launcher: apps-list ?v has no lN ({'/'.join(tags)}): set it by hand")
        return f
    target = max(ls, key=tag_num)
    for rel, old in zip(LAUNCHERS, (a, b)):
        new = APPS_LINE_RE.sub(lambda m: f"{m.group(1)}{target}{m.group(3)}{target}{m.group(5)}", old)
        if new != old:
            write(root, rel, new)
            f.written.append(rel)
    f.notes.append(f"launcher: apps-list ?v -> {target} on both sides, both copies (were {tags[0]}:{tags[1]} and {tags[2]}:{tags[3]})")
    return f


GATE_REF_RE = re.compile(r"'([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:js|css))\?v=(" + TAG + r")'")


def site_tags(root, target) -> list:
    """The ?v= tags other pages / scripts of the phone site use for `target` (a repo path), resolved like bump_versions does."""
    site, base = os.path.join(root, "tools", "web_public"), posixpath.basename(target)
    pat = re.compile(r"""(["'])([^"'\s?#]*?""" + re.escape(base) + r""")\?v=(""" + TAG + r""")\1""")
    tags = []
    for dp, dns, fns in os.walk(site):
        dns[:] = [d for d in dns if d not in ("node_modules", "three-addons", "__pycache__")]
        for fn in fns:
            if not fn.endswith((".html", ".js", ".mjs")) or fn.endswith(".min.js"):
                continue
            rel = os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, "/")
            t = read(root, rel) or ""
            if base not in t or len(t) > 1_500_000:
                continue
            for m in pat.finditer(t):
                lit = m.group(2)
                if "://" in lit:
                    continue
                res = posixpath.normpath(posixpath.join("tools/web_public", lit.lstrip("/")) if lit.startswith("/")
                                         else posixpath.join(posixpath.dirname(rel), lit))
                if res == target:
                    tags.append(m.group(3))
    return tags


def check_gate(root, git, base, changed: set) -> list:
    """gate/index.html loads its scripts / sheets from a site-root base (b + 'olympus/themes.js?v=o9'), so bump_versions does not see
    them: report each one whose file changed since the base while its ?v did not move, with the tag to use (the highest the other
    pages use now when it is newer, else the next one: never a tag an older copy already had)."""
    cur, old = read(root, GATE), git.show(base, GATE)
    if cur is None or old is None:
        return []
    out, seen = [], set()
    for m in GATE_REF_RE.finditer(cur):
        lit, tag = m.group(1), m.group(2)
        tgt = posixpath.normpath(f"tools/web_public/{lit}")
        if lit in seen or tgt not in changed or not os.path.isfile(os.path.join(root, tgt)):
            continue
        seen.add(lit)
        bm = re.search("'" + re.escape(lit) + r"\?v=(" + TAG + ")'", old)
        if bm and bm.group(1) == tag:
            others = [t for t in site_tags(root, tgt) if t != tag]
            top = max(others, key=tag_num) if others else ""
            new = top if top and tag_num(top) > tag_num(tag) else bump_tag(tag)
            out.append(f"gate: '{lit}?v={tag}' did not move but {tgt} changed (set ?v={new} in gate/index.html"
                       + (", as the other pages" if new == top else "") + ")")
    return out


def fix_run_area_tail(root) -> Fix:
    f = Fix()
    t = read(root, RUN_AREA)
    if t is None:
        return f
    new, moved, note = move_tail(t)
    if note:
        f.notes.append(note)
    if moved and new != t:
        try:
            check_run_area(new, root)
        except Unresolvable as e:
            f.notes = [f"run_area: lines after the main guard not moved ({e.why})"]
            return f
        write(root, RUN_AREA, new)
        f.written.append(RUN_AREA)
    return f


# ----------------------------------------------------------------------------------------------------------- bump_versions
def run_bump(root, base, mode="--apply", changed=None, timeout=600):
    """(exit code or None when the tool is missing, its output). Called by its CLI only: the tool changes often."""
    tool = os.path.join(root, "tools", "bump_versions.py")
    if not os.path.isfile(tool):
        return None, "tools/bump_versions.py not found"
    cmd = [sys.executable, "-X", "utf8", tool, mode, "--base", base] + (["--changed", *changed] if changed else [])
    try:
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"timed out ({timeout} s)"
    return r.returncode, (r.stdout + r.stderr)


def bump_rows(text):
    rows, notes, last, table = [], [], "", False
    for ln in (text or "").splitlines():
        if ln.startswith("note: "):
            notes.append(ln[6:])
        elif re.match(r"^-+\s+-+", ln):
            table = True
        elif ln.startswith(("applied:", "dry run:", "check ok", "CHECK FAILED", "nothing needs a bump")):
            last = ln
        elif table and ln.strip() and not ln.startswith(("what ", "Traceback")):
            rows.append(re.sub(r"\s{2,}", "  ", ln.strip()))
    return rows, notes, last


ROW_Q = re.compile(r"^query\s+(\S+)\s+(\S+?)\?v=(\S+) -> \?v=(\S+)")
ROW_W = re.compile(r"^worker\s+(\S+)\s+cache (\S+) -> (\S+)")


def rebump_loop(apply_text, check_rows) -> list:
    """The --check rows that only want to bump AGAIN what --apply just bumped (bump_versions cannot read the base's tag, e.g. 'a1q',
    so it never sees the file as bumped): [] when any row is a real miss."""
    done = set()
    for row in bump_rows(apply_text)[0]:
        m, k = ROW_Q.match(row), ROW_W.match(row)
        if m:
            done.add((m.group(1), m.group(2), m.group(4)))
        elif k:
            done.add((k.group(1), "cache", k.group(3)))
    loop = []
    for row in check_rows:
        m, k = ROW_Q.match(row), ROW_W.match(row)
        key = (m.group(1), m.group(2), m.group(3)) if m else (k.group(1), "cache", k.group(2)) if k else None
        if row.startswith("pin "):
            continue
        if key is None or key not in done:
            return []
        loop.append(f"{key[0].replace('tools/web_public/', '')} {key[1]}")
    return loop


def bump_lines(label, code, text, limit=5) -> list:
    if code is None:
        return [f"  {label}: skipped ({text})"]
    rows, notes, last = bump_rows(text)
    if code not in (0, 1) or (code == 1 and "CHECK FAILED" not in text):
        return [f"  {label}: FAILED (exit {code}): {(text or '').strip()[-240:]}"]
    out = [f"  {label}: {last or ('nothing needs a bump.' if not rows else f'{len(rows)} change(s)')}"]
    out += [f"     {r[:150]}" for r in rows[:limit]] + ([f"     (+{len(rows) - limit} more)"] if len(rows) > limit else [])
    out += [f"     note: {n[:150]}" for n in notes if "by hand" in n][:4]
    return out


# ----------------------------------------------------------------------------------------------------------- the test plan
GENERIC = {"index.html", "sw.js", "app.js", "main.js", "style.css", "styles.css", "jarvis.json", "manifest.webmanifest", "manifest.json",
           "icon.svg", "README.md", "__init__.py", "data.json", "config.json", "state.json", "index.js", "core.js", "page.js", "page.css"}
TOKEN_RE = re.compile(r"[A-Za-z0-9_@][A-Za-z0-9_./@+-]*")
LIT_RE = re.compile(r"""(['"])([^'"\n\\]{1,200})\1""")
PATHISH = re.compile(r"[\w@+.-][\w@+. /-]*\Z")
FROM_IMPORT_RE = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+\(?([\w ,]+)", re.M)
IMPORT_RE = re.compile(r"^\s*import\s+([\w., ]+)", re.M)
BROWSER_KIT_RE = re.compile(r"^\s*(?:from|import)\s+(?:tests\.)?browser_kit\b|^\s*from\s+tests\s+import\s+[^\n#]*\bbrowser_kit\b", re.M)
_PW_CACHE: dict = {}
PW = "play" "wright"                                   # spelled in two parts, so this file is no Playwright user itself
PW_NAMES, PW_MODULES = (PW, "sync_" + PW, "async_" + PW), (PW, "@" + PW + "/test", PW + "-core")


def uses_playwright(text: str) -> bool:
    """Real use, not a mention: a `playwright` name (import playwright, from playwright.sync_api ..., sync_playwright) or a string that
    IS 'playwright' (node Playwright: os.path.join(groot, "playwright"), ["npx", "playwright", ...]). A docstring, a comment or a
    fixture string that only names it does not count; a file the tokenizer cannot read counts (when unsure: a browser suite)."""
    if PW not in text.lower():
        return False
    key = hash(text)
    if key not in _PW_CACHE:
        found = False
        try:
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.NAME and tok.string in PW_NAMES:
                    found = True
                elif tok.type == tokenize.STRING and PW in tok.string.lower():
                    try:
                        v = ast.literal_eval(tok.string)
                    except (ValueError, SyntaxError):
                        continue
                    found = isinstance(v, str) and v.strip("/").lower() in PW_MODULES
                if found:
                    break
        except (tokenize.TokenError, SyntaxError):
            found = True
        _PW_CACHE[key] = found
    return _PW_CACHE[key]


DIRECT = {"vault/": ["obsidian_brain"], "research/writeups/": ["writeups_index"]}     # a generated tree -> the suite that checks it
NO_NEEDLES = {RUN_AREA, "tests/smoke.py", "tests/run_gate.py", "tests/__init__.py"}  # named in every docstring: only their own rules
FIXTURE_SUITES = {f[len("tests/test_"):-3] for f in PIN_FIXTURES}  # a mini repo of real-looking paths inside: picked by their own files only


def load_run_area(root):
    """tests/run_area.py of `root`, imported as a module (not __main__: lines after the main guard count, as in a real import)."""
    path = os.path.join(root, "tests", "run_area.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location(f"_land_run_area_{abs(hash(root))}", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        with repo_path(root):
            spec.loader.exec_module(mod)
    except Exception:  # noqa: BLE001 - a broken run_area.py: the plan runs without areas
        return None
    return mod


def areas_of_text(text, root=ROOT):
    ns = {"__name__": "_land_base", "__file__": os.path.join(root, RUN_AREA)}
    try:
        with repo_path(root):
            exec(compile(text, RUN_AREA, "exec"), ns)   # noqa: S102 - the repo's own file at the base
    except Exception:  # noqa: BLE001
        return {}
    return ns.get("AREAS", {}) or {}


def _expand(tok, into):
    tok = tok.strip().rstrip("./-")
    if not tok:
        return
    into.add(tok)
    if "/" in tok:
        parts = [p for p in tok.split("/") if p not in ("", ".", "..")]
        for i in range(len(parts)):
            into.add("/".join(parts[i:]))


def file_tokens(text) -> set:
    """The path / module names a test file mentions: words with / or ., every quoted string, the strings of one line joined by /
    (os.path.join(WEB, "kalshi", "kalshi.js")), `from X import a, b` -> X.a, X.b; each path also by every suffix."""
    toks = set()
    for t in TOKEN_RE.findall(text):
        if "/" in t or "." in t:
            _expand(t, toks)
    for line in text.splitlines():
        lits = [m.group(2) for m in LIT_RE.finditer(line)]
        run = []
        for s in lits + [None]:
            if s is not None and PATHISH.match(s) and len(s) <= 120:
                _expand(s, toks)
                run.append(s.strip("/"))
                continue
            if len(run) > 1:
                _expand("/".join(run), toks)
            run = []
    for m in FROM_IMPORT_RE.finditer(text):
        toks.add(m.group(1))
        for nm in re.split(r"[\s,]+", m.group(2)):
            if nm and nm != "as":
                toks.add(f"{m.group(1)}.{nm}")
    for m in IMPORT_RE.finditer(text):                 # `import browser_kit as BK`, `import engine.live`
        for part in m.group(1).split(","):
            nm = part.split(" as ")[0].strip()
            if nm:
                toks.add(nm)
    return toks


def needles(path, uniq) -> set:
    n = {path}
    for pre in ("tools/web_public/", "web_next/"):
        if path.startswith(pre) and "/" in path[len(pre):]:
            n.add(path[len(pre):])
    parts = path.split("/")
    if len(parts) >= 3:
        n.add("/".join(parts[-2:]))
    base = parts[-1]
    if uniq.get(base, 0) == 1 and base not in GENERIC and len(base) >= 7:
        n.add(base)
    if path.endswith(".py"):
        mod = path[:-3].replace("/", ".")
        n.add(mod)
        if mod.startswith("tests."):
            n.add(mod[6:])
    return n


@dataclass
class TestPlan:
    suites: dict = field(default_factory=dict)       # suite -> why (the changed file that names it)
    browser: set = field(default_factory=set)
    area: dict = field(default_factory=dict)         # suite -> its area ('' = in no area)
    bot: list = field(default_factory=list)
    commands: list = field(default_factory=list)
    parts: dict = field(default_factory=dict)

    @property
    def nonbrowser(self):
        return [s for s in self.suites if s not in self.browser]


def test_texts(root) -> dict:
    tdir, out = os.path.join(root, "tests"), {}
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if fn.endswith(".py"):
                out[fn[:-3]] = read(root, f"tests/{fn}") or ""
    return out


def _repo_modules(text, root) -> list:
    """Repo files a test imports (engine.x, tools.y, `from agency import content`): one level, for the browser check."""
    names = set()
    for m in FROM_IMPORT_RE.finditer(text):
        names.add(m.group(1))
        names.update(f"{m.group(1)}.{nm}" for nm in re.split(r"[\s,]+", m.group(2)) if nm and nm != "as")
    for m in IMPORT_RE.finditer(text):
        names.update(p.split(" as ")[0].strip() for p in m.group(1).split(","))
    out = []
    for nm in names:
        if not nm or nm.startswith(".") or nm.split(".")[0] in ("tests", "os", "sys", "re", "json"):
            continue
        p = os.path.join(root, *nm.split("."))
        for cand in (p + ".py", os.path.join(p, "__init__.py")):
            if os.path.isfile(cand):
                out.append(cand)
                break
    return out


def browser_suites(texts: dict, root=None) -> set:
    """Suites (test_<x>.py -> x) that use playwright (python or node), import the browser kit, import a tests/ helper that does (to
    a fixed point), or import a repo module that uses playwright itself (one level: a tool that drives Chromium)."""
    browser = {n for n, t in texts.items() if uses_playwright(t) or BROWSER_KIT_RE.search(t)}
    if root:
        for n, t in texts.items():
            if n not in browser and n.startswith("test_") and any(uses_playwright(_read_abs(p)) for p in _repo_modules(t, root)):
                browser.add(n)
    helpers = [n for n in texts if not n.startswith("test_") and n not in ("run_area", "run_gate", "smoke", "__init__")]
    pats = {h: re.compile(r"^\s*(?:import\s+(?:tests\.)?" + h + r"\b|from\s+(?:tests\.|\.)?" + h + r"\s+import|from\s+(?:tests|\.)\s+import\s+[^\n#]*\b"
                          + h + r"\b)", re.M) for h in helpers}
    grew = True
    while grew:
        grew = False
        for n, t in texts.items():
            if n not in browser and any(h in browser and h in t and pats[h].search(t) for h in helpers):
                browser.add(n)
                grew = True
    return {n[5:] for n in browser if n.startswith("test_")}


VERSION_RE = re.compile(r"(\?v=|(?:le-public-v|le-shell-next-v|jarvis-v|kalshi-))[A-Za-z]*\d+")


def version_only(git, base, root, changed) -> set:
    """Site files whose change since the base is only ?v= tags / worker cache names (what bump_versions writes): they name no suite
    (smoke's pins cover them), else every landing would pull in each test that reads the root sw.js."""
    out = set()
    for f in changed:
        if f.startswith(("tools/web_public/", "web_next/")) and f.endswith((".html", ".js", ".mjs")):
            old, new = git.show(base, f), read(root, f)
            if old is not None and new is not None and old != new and VERSION_RE.sub(r"\1#", old) == VERSION_RE.sub(r"\1#", new):
                out.add(f)
    return out


def make_plan(root, changed, base_areas=None, ra=None, uniq=None, skip=()) -> TestPlan:
    """changed files -> suites -> areas, browser or not, and the exact commands (smoke first). `skip`: changed files that name no
    suite (version-only edits)."""
    plan = TestPlan()
    texts = test_texts(root)
    suites = {n[5:] for n in texts if n.startswith("test_")}
    ra = ra if ra is not None else load_run_area(root)
    areas = dict(getattr(ra, "AREAS", {}) or {})
    plan.parts = dict(getattr(ra, "PARTS", {}) or {})
    if uniq is None:
        try:
            uniq = collections.Counter(posixpath.basename(p) for p in Git(root).names("ls-files", "-z"))
        except GitError:
            uniq = {}
    want = {}                                          # needle -> the changed file
    for f in changed:
        if is_bot(f):
            plan.bot.append(f)
        if f in skip:
            continue
        b = posixpath.basename(f)
        if f.startswith("tests/") and b.startswith("test_") and b.endswith(".py"):
            if b[5:-3] in suites:
                plan.suites.setdefault(b[5:-3], f)
            continue
        stem = os.path.splitext(b)[0]
        for s in (stem, f"{stem}_page"):
            if s in suites:
                plan.suites.setdefault(s, f)
        if f.startswith("tools/web_public/") and f.count("/") >= 3:
            app = f.split("/")[2]
            for s in (app, f"{app}_page"):
                if s in suites:
                    plan.suites.setdefault(s, f)
        for pre, ss in DIRECT.items():
            if f.startswith(pre):
                for s in ss:
                    if s in suites:
                        plan.suites.setdefault(s, f)
        if f not in NO_NEEDLES:
            for nd in needles(f, uniq):
                want.setdefault(nd, f)
    if want:
        for n, t in texts.items():
            if n.startswith("test_") and n[5:] not in plan.suites and n[5:] not in FIXTURE_SUITES:
                hit = want.keys() & file_tokens(t)
                if hit:
                    plan.suites[n[5:]] = want[sorted(hit)[0]]
    if base_areas is not None:                         # a suite newly registered in tests/run_area.py
        old = {s for v in base_areas.values() for s in v}
        for v in areas.values():
            for s in v:
                if s not in old and s in suites:
                    plan.suites.setdefault(s, RUN_AREA)
    plan.browser = browser_suites(texts, root) & set(plan.suites)
    count = collections.Counter(a for s in plan.suites for a, v in areas.items() if s in v)
    order = list(areas)
    for s in plan.suites:
        cand = [a for a in order if s in areas[a]]
        plan.area[s] = max(cand, key=lambda a: (count[a], -order.index(a))) if cand else ""
    plan.commands = plan_commands(plan, ra, areas)
    return plan


def _exact_only(area, group, ra) -> bool:
    """run_area's --only is a substring match: True when `--only a,b` on `area` picks exactly `group`."""
    if ra is None or not area:
        return False
    try:
        names = ra.suites_for(area)
    except Exception:  # noqa: BLE001
        return False
    picked = [n for n in names if any(k in n for k in group)]
    return bool(picked) and set(picked) == set(group)


def plan_commands(plan, ra, areas) -> list:
    """smoke; one run_area line per area (non-browser first); the suites with no area (or no exact --only) on ONE loop line per kind
    (a suite run by parts: one line per part); the browser ones under the lock (per suite in the loop, so others wait less)."""
    cmds = [SMOKE]
    for browser in (False, True):
        lock = f"{LOCK} " if browser else ""
        groups = collections.OrderedDict()
        for s in plan.suites:
            if (s in plan.browser) == browser:
                groups.setdefault(plan.area.get(s, ""), []).append(s)
        rest = []
        for area in sorted(groups, key=lambda a: (a == "", list(areas).index(a) if a in areas else 0)):
            if _exact_only(area, groups[area], ra):
                cmds.append(f"{lock}python tests/run_area.py {area} --only {','.join(groups[area])}")
            else:
                rest += groups[area]
        for s in [s for s in rest if s in plan.parts]:
            cmds += [f"{lock}python -X utf8 -m tests.test_{s} {' '.join(args)}".rstrip() for _, args in plan.parts[s]]
        rest = [s for s in rest if s not in plan.parts]
        if len(rest) == 1:
            cmds.append(f"{lock}python -X utf8 -m tests.test_{rest[0]}")
        elif rest:
            cmds.append(f"for s in {' '.join(rest)}; do {lock}python -X utf8 -m tests.test_$s || echo \"FAILED $s\"; done")
    if plan.bot:
        cmds += [c for _, _, c in BOT_CHECKS]
    return cmds


def plan_lines(plan, full=True, why=False) -> list:
    nb, br = len(plan.nonbrowser), len(plan.browser)
    groups = collections.OrderedDict()
    for s in plan.suites:
        groups.setdefault(plan.area.get(s) or "no area", []).append(s + ("*" if s in plan.browser else ""))
    head = f"  tests: smoke + {nb + br} suite(s), {br} browser*" + (" + bot checks" if plan.bot else "")
    if groups:
        head += ": " + "; ".join(f"{a}: {short(v, 6)}" for a, v in list(groups.items())[:6])
    if not full:
        return [head[:400]]
    out = [head[:600]] + [f"     {c}" for c in plan.commands]
    if why:
        out += [f"     why {s}: {f}" for s, f in plan.suites.items()]
    return out


def plan_for(root, git, base, changed=None) -> TestPlan:
    changed = git.changed_since(base) if changed is None else changed
    return make_plan(root, changed, base_areas=areas_of_text(git.show(base, RUN_AREA) or "", root), skip=version_only(git, base, root, changed))


def run_plan(root, plan, git, budget=900) -> list:
    """--run: smoke + the non-browser suites (+ the bot checks), each with its budget; one line each. The two files smoke rewrites are
    put back when they were clean before; any other file a test changed is named."""
    before = {p for _, p in git.status()}
    out = []
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, "tests/smoke.py"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=budget)
        m = re.search(r"smoke: (\d+)/(\d+)", r.stdout)
        out.append(f"  smoke: {m.group(1)}/{m.group(2)} {'PASS' if r.returncode == 0 else 'FAIL'} ({time.time() - t0:.0f}s)" if m
                   else f"  smoke: exit {r.returncode} ({time.time() - t0:.0f}s)")
        out += [f"     {ln[:150]}" for ln in r.stdout.splitlines() if ln.startswith("[BAD]")][:4]
    except subprocess.TimeoutExpired:
        out.append(f"  smoke: TIMEOUT ({budget} s)")
    ra = load_run_area(root)
    env = dict(os.environ)
    for s in plan.nonbrowser:
        for label, args in plan.parts.get(s, [("", [])]):
            nm = f"{s}:{label}" if label else s
            if ra is not None:
                res = ra.run_one(nm, budget, env, args)
                tot = res["passed"] + res["failed"]
                out.append(f"  {nm}: {res['passed']}/{tot} {res['state']} ({res['seconds']:.0f}s)")
                out += [f"     {x[:150]}" for x in res["fails"][:3]]
            else:
                out.append(f"  {nm}: not run (tests/run_area.py missing)")
    if plan.bot:
        for label, args, _ in BOT_CHECKS:
            t0 = time.time()
            try:
                r = subprocess.run([sys.executable, *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=budget)
                tail = ((r.stdout + r.stderr).strip().splitlines() or [""])[-1][:110] if r.returncode else ""
                out.append(f"  {label}: {'PASS' if r.returncode == 0 else 'FAIL'} ({time.time() - t0:.0f}s) {tail}".rstrip())
            except subprocess.TimeoutExpired:
                out.append(f"  {label}: TIMEOUT ({budget} s)")
    new = sorted({p for _, p in git.status()} - before)
    back = [p for p in new if p in DROPPINGS]
    if back:
        git.run("checkout", "--", *back, check=False)
        out.append(f"  put back (smoke rewrites them): {', '.join(back)}")
    rest = [p for p in new if p not in DROPPINGS]
    if rest:
        out.append(f"  NOTE the tests changed: {short(rest, 6)} (not put back: look before committing)")
    return out


# ------------------------------------------------------------------------------------------------------------- the steps
def stale_generated(root) -> list:
    out = []
    for label, tool in (("write-ups INDEX.md", "tools/writeups_index.py"), ("vault", "tools/obsidian_brain.py")):
        if not os.path.isfile(os.path.join(root, tool)):
            continue
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", tool, "--check"], cwd=root, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=300)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode != 0:
            out.append(label)
    return out


def after_merge(root, git, base, merged=None, quiet=False):
    """bump_versions --apply --base, the fix-ups, bump --check; lines to print and the kalshi fix result."""
    lines = []
    merged = set(merged if merged is not None else git.names("diff", "--name-only", "--no-renames", "-z", base, "HEAD"))
    code, text = run_bump(root, base)
    lines += bump_lines("bump", code, text, limit=3 if quiet else 5)
    changed_now = set(git.changed_since(base))
    kal, lau = fix_kalshi(root, merged), fix_launcher(root)
    fixes = kal.notes + lau.notes
    rebump = [p for p in lau.written if p not in changed_now]
    if rebump:                                         # a launcher copy the merge had not changed: its own ?v= must move too
        c2, t2 = run_bump(root, base, changed=rebump)
        lines += bump_lines("bump (launcher copy)", c2, t2, limit=3)
        text = f"{text}\n{t2}"
    fixes += check_gate(root, git, base, set(git.changed_since(base)))
    fixes += fix_run_area_tail(root).notes
    lines.append("  fix-ups: " + ("ok (kalshi cache, launcher copies, gate tags, run_area tail)" if not fixes else fixes[0]))
    lines += [f"     {x}" for x in fixes[1:8]]
    c3, t3 = run_bump(root, base, mode="--check")
    if c3 is not None:
        rows, _, last = bump_rows(t3)
        loop = rebump_loop(text, rows) if c3 else []
        if c3 == 0:
            lines.append("  check: bump --check ok")
        elif kal.reverted and rows and all("kalshi/sw.js" in r for r in rows):
            lines.append("  check: bump --check flags only kalshi/sw.js: expected (its cache kept = the css/js ?v on purpose)")
        elif loop:
            lines.append(f"  check: bump --check only wants to bump again what --apply just bumped ({short(loop, 3)}): bump_versions "
                         "cannot read the base's tag there (e.g. 'a1q'), every run bumps it once more; keep the one bump, ignore it")
        else:
            lines.append(f"  check: {last or 'bump --check FAILED'}: {short(rows, 3, '; ')}"[:400])
    return lines, kal


def commit_hint(git, base, name) -> list:
    paths = [p for _, p in git.status()]
    if not paths:
        return ["  uncommitted: nothing (the merge commit is all)"]
    tops = sorted({p.split("/")[0] for p in paths})
    msg = f"Land {name}: <what>" if name else "<what>"
    return [f"  uncommitted: {len(paths)} file(s): {by_top(paths)}",
            f"  then: git add -A {' '.join(tops)} && git commit -m \"{msg}\" && python tools/ship.py --no-tests"]


def land(root, name, remote=None, fetch=True, run=False, budget=900) -> int:
    git = Git(root)
    if git.merging():
        print("[STOP] a merge is in progress here: finish it (git commit) or git merge --abort, then run again")
        return 2
    st = git.status()
    if st:
        hint = " (smoke rewrites these two: git checkout -- " + " ".join(DROPPINGS) + ")" if all(p in DROPPINGS for _, p in st) else ""
        print("[STOP] the checkout is not clean: commit or put back first" + hint + "\n  " + "\n  ".join(f"{xy} {p}" for xy, p in st[:8]))
        return 2
    remote = remote or home_remote(git)
    try:
        ref, note = get_ref(git, remote, name, fetch)
    except GitError as e:
        print(f"[STOP] {e}")
        return 2
    base = git.head()
    s = summarize(git, ref, name)
    print(f"land {name} ({ref.split('/', 2)[-1]} {s['sha'][:8]}{', ' + note if note else ''}) on {base[:8]}   undo: git reset --hard {base[:8]}")
    if remote and fetch and git.ok("fetch", "-q", remote, f"+refs/heads/pc:refs/remotes/{remote}/pc") \
            and not git.ok("merge-base", "--is-ancestor", f"refs/remotes/{remote}/pc", "HEAD"):
        n = git.out("rev-list", "--count", f"HEAD..refs/remotes/{remote}/pc")
        print(f"  NOTE: {remote}/pc has {n} commit(s) this checkout does not: ship.py's push will be refused until you merge them")
    print("\n".join(summary_lines(s)))
    stale0 = set(stale_generated(root))
    m = do_merge(git, root, ref)
    print("\n".join(merge_lines(m)))
    if m.status in ("stop", "failed"):
        return 2
    if m.status == "uptodate":
        return 0
    return finish(root, git, base, name, run, budget, stale0, merged_note=m.status)


def finish(root, git, base, name, run, budget, stale0=None, merged_note=""):
    lines, _ = after_merge(root, git, base)
    print("\n".join(lines))
    stale = stale_generated(root)
    for lab in stale:
        tool = "tools/writeups_index.py" if lab.startswith("write-ups") else "tools/obsidian_brain.py"
        print(f"  stale: {lab}{' (already stale at the base)' if stale0 is not None and lab in stale0 else ''}: python -X utf8 {tool}")
    print("\n".join(commit_hint(git, base, name)))
    plan = plan_for(root, git, base)
    print("\n".join(plan_lines(plan, why=WHY)))
    if run:
        print("  run (non-browser; browser suites stay the flock lines above):")
        print("\n".join(run_plan(root, plan, git, budget)))
    return 0


def _preview_one(tg, wt, ref, note, name, label):
    s = summarize(tg, ref, name)
    print(f"{label} {name} {s['sha'][:8]}{' (' + note + ')' if note else ''}")
    print("\n".join(summary_lines(s)))
    pre = tg.head()
    m = do_merge(tg, wt, ref)
    print("\n".join(merge_lines(m)))
    if m.status in ("clean", "resolved"):
        lines, _ = after_merge(wt, tg, pre, quiet=True)
        print("\n".join(lines))
        print("\n".join(plan_lines(plan_for(wt, tg, pre), full=WHY, why=WHY)))
        if tg.run("status", "--porcelain").out.strip():   # the next branch merges onto what the lead will have committed
            tg.run("add", "-A")
            tg.run("commit", "-q", "-m", f"preview: bump + fix-ups after {name}")
    return name, m.status, s


def preview(root, names, remote=None, fetch=True) -> int:
    git = Git(root)
    remote = remote or home_remote(git)
    head = git.head()
    tmp = tempfile.mkdtemp(prefix="land-preview-")
    wt = os.path.join(tmp, "wt")
    results = []
    t0 = time.time()
    dirty = git.status()
    print(f"preview of {len(names)} branch(es) on {head[:8]} in a temp worktree (your checkout is not touched)"
          + (f"; your {len(dirty)} uncommitted file(s) are not in it" if dirty else ""))
    try:
        git.run("worktree", "add", "--detach", "--quiet", wt, head)
        tg = Git(wt, temp=True)
        for i, name in enumerate(names, 1):
            try:
                ref, note = get_ref(git, remote, name, fetch)
            except GitError as e:
                print(f"[{i}/{len(names)}] {name}: SKIP: {e}")
                results.append((name, "missing", {}))
                continue
            try:
                results.append(_preview_one(tg, wt, ref, note, name, f"[{i}/{len(names)}]"))
            except GitError as e:                     # one broken branch never ends the preview of the others
                print(f"  ERROR: {e}")
                tg.run("merge", "--abort", check=False)
                tg.run("reset", "-q", "--hard", check=False)
                results.append((name, "failed", {}))
    finally:
        git.run("worktree", "remove", "--force", wt, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
        git.run("worktree", "prune", check=False)
    st = collections.Counter(r[1] for r in results)
    stops = [r[0] for r in results if r[1] in ("stop", "failed")]
    print(f"preview done in {time.time() - t0:.0f}s: {st['clean']} clean, {st['resolved']} auto-resolved, {len(stops)} STOP"
          + (f" ({', '.join(stops)})" if stops else "") + (f", {st['uptodate']} already in" if st["uptodate"] else "")
          + (f", {st['missing']} not found" if st["missing"] else ""))
    bots = [r[0] for r in results if r[2].get("bot")]
    leads = [r[0] for r in results if r[2].get("lead")]
    wires = sum(len(r[2].get("wires", [])) for r in results)
    print(f"  bot checks: {', '.join(bots) or 'none'} | lead-only files: {', '.join(leads) or 'none'} | LEAD_WIRES to read: {wires}")
    print("  land one at a time: python tools/land_branch.py <branch> --run   (then commit + ship; after a STOP merge by hand, then "
          "python tools/land_branch.py --after <base>)")
    return 2 if stops else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="land helper branches on Olympus pc (the lead's tool)")
    ap.add_argument("branches", nargs="*")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--preview", action="store_true", help="test-merge the branches in a temp worktree; the checkout is not touched")
    g.add_argument("--after", metavar="BASE", help="bump + fix-ups + plan after a merge finished by hand")
    g.add_argument("--plan", metavar="BASE", help="only the test plan for what changed since BASE")
    ap.add_argument("--run", action="store_true", help="run smoke + the non-browser suites (900 s each)")
    ap.add_argument("--budget", type=float, default=900)
    ap.add_argument("--remote")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--why", action="store_true", help="also print which changed file put each suite in the plan")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    global WHY
    WHY = a.why
    try:
        if a.preview:
            if not a.branches:
                ap.error("--preview needs at least one branch")
            return preview(root, a.branches, a.remote, not a.no_fetch)
        if a.after or a.plan:
            git = Git(root)
            base = git.out("rev-parse", a.after or a.plan)
            if a.after:
                if git.merging():
                    print("[STOP] a merge is in progress: commit it first")
                    return 2
                print(f"after the merge on {base[:8]}   undo: git reset --hard {base[:8]}")
                return finish(root, git, base, "", a.run, a.budget, stale0=None)
            plan = plan_for(root, git, base)
            print("\n".join(plan_lines(plan, why=WHY)))
            if a.run:
                print("\n".join(run_plan(root, plan, git, a.budget)))
            return 0
        if len(a.branches) != 1:
            ap.error("land one branch at a time (or --preview a list)")
        return land(root, a.branches[0], a.remote, not a.no_fetch, a.run, a.budget)
    except GitError as e:
        print(f"[STOP] {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
