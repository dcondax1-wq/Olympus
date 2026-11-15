"""Rule-change log (2026-10-22, research/writeups/ai-features.md): who changed the trading rules, when and why.

Two sources, read-only (nothing here changes a rule):
  git       every commit that touched a trading file (live_model.json, live_model_lit.json, second_model.json): the author,
            the date, the commit title (the "why") and the key-level changes ("lit.t_check.at: 15 -> 20").
            python -X utf8 -m engine.rulelog build  -> research/lab/rule_log.json (the dashboards read it; rerun after a change)
            python -X utf8 -m engine.rulelog show   -> the last changes as text
  runtime   the PC bot compares the rules it trades on every poll with the last seen (engine/ai_watch.rules_step) and
            appends each change to logs/rule_changes.jsonl (+ a push, kind "rules_change"): this also catches a start-cfg
            override or an edit that was never committed.
Pure helpers: flatten(obj), diff(a, b). Tests: tests/test_ai_features.py.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("live_model.json", "live_model_lit.json", "second_model.json")
OUT = os.path.join(ROOT, "research", "lab", "rule_log.json")
RUNTIME = os.path.join(ROOT, "logs", "rule_changes.jsonl")
SKIP_KEYS = ("note", "summary", "notes", "label", "lock_note", "no_yahoo_note", "with_lit_note", "with_lit_label")
VERSION = 1


def _short(v, n=60) -> str:
    s = json.dumps(v, sort_keys=True, default=str) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n - 3] + "..."


def flatten(obj, pre: str = "", out: dict | None = None, depth: int = 0) -> dict:
    """{"a.b.c": leaf}; lists are leaves (compared whole); text-only keys (notes, labels) are left out."""
    out = {} if out is None else out
    if isinstance(obj, dict) and depth < 6:
        for k, v in obj.items():
            if str(k) in SKIP_KEYS or str(k).endswith("_note"):
                continue
            flatten(v, f"{pre}.{k}" if pre else str(k), out, depth + 1)
    else:
        out[pre or "."] = obj
    return out


def diff(a, b) -> list:
    """["path: old -> new", "path: added new", "path: removed (was old)"], sorted by path."""
    fa, fb = flatten(a or {}), flatten(b or {})
    out = []
    for k in sorted(set(fa) | set(fb)):
        if k not in fa:
            out.append(f"{k}: added {_short(fb[k])}")
        elif k not in fb:
            out.append(f"{k}: removed (was {_short(fa[k])})")
        elif fa[k] != fb[k]:
            out.append(f"{k}: {_short(fa[k])} -> {_short(fb[k])}")
    return out


def _git(args, cwd=ROOT, timeout=20) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def role(name: str) -> str:
    """who changed a rule, as a role: "Claude" for Claude's commits, "owner" for everyone else. The git author name itself is never
    kept (team Q2 privacy, docs/PRIVACY.md: it reached the heartbeat, the phone site and this committed log)."""
    n = str(name or "").strip().lower()
    return "Claude" if n.startswith("claude") or n.endswith("[bot]") or n in ("github", "github actions") else "owner"


def head_commit(cwd=ROOT) -> dict | None:
    """{"sha", "who" (a role, never the git name), "when", "why"} of HEAD (None outside a git checkout)."""
    s = _git(["log", "-1", "--format=%H%x1f%an%x1f%aI%x1f%s"], cwd=cwd)
    if not s or "\x1f" not in s:
        return None
    sha, who, when, why = s.strip().split("\x1f", 3)
    return {"sha": sha, "who": role(who), "when": when, "why": why}


def _load_at(sha: str, path: str, cwd=ROOT):
    s = _git(["show", f"{sha}:{path}"], cwd=cwd)
    if s is None:
        return None
    try:
        return json.loads(s)
    except ValueError:
        return None


def history(n: int = 40, cwd=ROOT, files=FILES) -> list:
    """Newest first: [{"sha", "who", "when", "why", "files": {file: [changes]}, "n"}] for commits with a real rule change."""
    log = _git(["log", f"-n{int(n)}", "--format=%H%x1f%an%x1f%aI%x1f%s", "--", *files], cwd=cwd)
    out = []
    for ln in (log or "").splitlines():
        if ln.count("\x1f") < 3:
            continue
        sha, who, when, why = ln.split("\x1f", 3)
        per = {}
        for f in files:
            new, old = _load_at(sha, f, cwd), _load_at(sha + "^", f, cwd)
            if new is None and old is None:
                continue
            ch = diff(old, new)
            if ch:
                per[f] = ch[:60]
        if per:
            out.append({"sha": sha[:10], "who": role(who), "when": when, "why": why[:200], "files": per, "n": sum(len(v) for v in per.values())})
    return out


def append_runtime(row: dict, path: str | None = None):
    p = path or RUNTIME
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


def runtime_rows(path: str | None = None, n: int = 30) -> list:
    rows = []
    try:
        with open(path or RUNTIME, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    rows.append(json.loads(ln))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows[-n:][::-1]


def build(n: int = 40, out: str = OUT) -> dict:
    H = history(n)
    d = {"v": VERSION, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "files": list(FILES), "commits": H,
         "how": "git log of the trading files, key-level diff of each commit against its parent (text-only keys left out)"}
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=1)
    except OSError:
        pass
    return d


def view(path: str = OUT, runtime_path: str | None = None) -> dict:
    """For the dashboards: the committed git log + this PC's runtime changes."""
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        d = {"commits": [], "error": "research/lab/rule_log.json missing: python -m engine.rulelog build"}
    d["runtime"] = runtime_rows(runtime_path)
    return d


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.rulelog")
    ap.add_argument("what", choices=("build", "show"), nargs="?", default="show")
    ap.add_argument("-n", type=int, default=40)
    a = ap.parse_args(argv)
    d = build(a.n) if a.what == "build" else view()
    for c in (d.get("commits") or [])[:12]:
        print(f"{c['when'][:16]}  {c['who']}  {c['why'][:70]}")
        for f, ch in c["files"].items():
            for x in ch[:6]:
                print(f"    {f}: {x}")
    if a.what == "build":
        print(f"-> {os.path.relpath(OUT, ROOT)} ({len(d['commits'])} commits)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
