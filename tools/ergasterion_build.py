#!/usr/bin/env python3
"""ERGASTERION builder: the compact queue.json for the workshop page (tools/web_public/ergasterion/). READ ONLY, OFFLINE, stdlib only.

    python tools/ergasterion_build.py                       # repo -> tools/web_public/ergasterion/queue.json
    python tools/ergasterion_build.py --out DIR/queue.json  # the site build writes it into the built site folder
    python tools/ergasterion_build.py --check               # exit 1 when queue.json is not what this script writes now (git part ignored)
    python tools/ergasterion_build.py --selftest

What it indexes (everything is plain text out of files the repo already has; nothing is run, nothing is sent):
  * queue   : the tasks of handoff/QUEUE.md (open / done, first 30 open with their section)
  * writeups: the newest research write-ups (research/writeups/*.md front matter: date, title, status, summary)
  * rejected: write-ups whose status is rejected, plus the "Tested and rejected" bullets of docs/CLAUDE_REFERENCE.md
  * learnings: dated one-liners, each with the worker it belongs to and its source file (write-up summaries + the Mind's observations)
  * mind    : research/mind/proposals_seed.json (or logs/mind/proposals.json when present): tested count and the latest observations
  * git     : the newest commits and agent / task branches, only when a git repo is there at build time (never required, never part of --check)
`asof` is the newest date found in the sources (not the clock), so the file is reproducible.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "handoff", "QUEUE.md")
WRITEUPS = os.path.join(ROOT, "research", "writeups")
REFERENCE = os.path.join(ROOT, "docs", "CLAUDE_REFERENCE.md")
MIND_LIVE = os.path.join(ROOT, "logs", "mind", "proposals.json")
MIND_SEED = os.path.join(ROOT, "research", "mind", "proposals_seed.json")
OUT = os.path.join(ROOT, "tools", "web_public", "ergasterion", "queue.json")
WHO = (("kalshi", "kalshi"), ("atlas", "atlas"), ("blitz", "blitz"), ("prometheus", "prometheus"), ("hephaestus", "hephaestus"), ("cronos", "cronos"),
       ("mind", "mind"), ("sibyl", "sibyl"), ("chrysos", "chrysos"), ("mercury", "mercury"), ("oikos", "oikos"), ("arbiter", "arbiter"),
       ("money", "chrysos"), ("lit", "lit"))
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def clean(text, n):
    t = re.sub(r"\s+", " ", re.sub(r"[`*<>]", "", str(text or ""))).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def first_sentence(text, n=170):
    t = clean(text, 600)
    m = re.match(r"(.{12,}?[.!?])(\s|$)", t)
    return clean(m.group(1) if m else t, n)


def who_of(name, title=""):
    low = (name + " " + title).lower()
    for key, wid in WHO:
        if re.search(r"(^|[^a-z])" + key, low):
            return wid
    return "dev"


def front(text):
    meta = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
    if "title" not in meta:
        m = re.search(r"^#\s+(.+)$", text, re.M)
        meta["title"] = m.group(1).strip() if m else ""
    return meta


def queue_tasks(text):
    tasks, section = [], ""
    for line in text.splitlines():
        h = re.match(r"^##\s+(.*)", line)
        if h:
            section = clean(h.group(1), 70)
            continue
        m = re.match(r"^- \[( |x|X)\]\s+(?:\*\*([^*]+)\*\*:?\s*)?(.*)", line)
        if m:
            tid = m.group(2) or clean(m.group(3), 28)
            tasks.append({"id": clean(tid, 40), "text": clean(m.group(3), 150), "section": section.split(":")[0][:40], "done": m.group(1) != " "})
    return tasks


def norm_status(raw):
    low = str(raw or "").lower().strip()
    if low.startswith("rejected") or low.startswith("no rule change"):
        return "rejected"
    if "adopt" in low[:30]:
        return "adopt-candidate"
    m = re.match(r"[a-z-]+", low)
    return m.group(0) if m else ""


def writeup_rows(folder=WRITEUPS):
    rows = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return rows
    for n in names:
        if not n.endswith(".md") or n.upper() == "INDEX.MD":
            continue
        meta = front(read(os.path.join(folder, n)))
        d = DATE.search(meta.get("date", "")) or DATE.match(n)
        rows.append({"date": d.group(1) if d else "", "title": clean(meta.get("title") or n[:-3], 110), "status": norm_status(meta.get("status")),
                     "summary": first_sentence(meta.get("summary", ""), 170), "file": "research/writeups/" + n, "who": who_of(n, meta.get("title", ""))})
    rows.sort(key=lambda r: (r["date"], r["file"]), reverse=True)
    return rows


def rejected_bullets(text):
    out, on = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            on = line.lower().startswith("## tested and rejected")
            continue
        if on and line.startswith("- "):
            out.append(clean(line[2:], 190))
    return out[:14]


def mind_block():
    for p in (MIND_LIVE, MIND_SEED):
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            obs = [{"text": clean(o.get("text"), 170), "bot": str(o.get("bot", ""))[:12], "score": round(float(o.get("score") or 0), 2)} for o in (d.get("observations") or [])[:8] if isinstance(o, dict)]
            t = int(d.get("t") or 0)
            return {"tested": int(d.get("tested") or 0), "t": t, "date": dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d") if t else "", "observations": obs,
                    "source": os.path.relpath(p, ROOT).replace(os.sep, "/")}
        except (OSError, ValueError, TypeError):
            continue
    return {"tested": 0, "t": 0, "date": "", "observations": [], "source": ""}


def git_block(root=ROOT):
    def run(*args):
        return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=15, check=True).stdout
    try:
        log = run("log", "-n", "40", "--pretty=%ct|%an|%s")
        refs = run("for-each-ref", "refs/heads", "--sort=-committerdate", "--count=60", "--format=%(refname:short)|%(committerdate:unix)|%(subject)")
    except Exception:  # noqa: BLE001 - git is never required
        return {"available": False, "commits": [], "branches": []}
    commits = []
    for ln in log.splitlines():
        a = ln.split("|", 2)
        if len(a) == 3 and a[0].isdigit():
            commits.append({"t": int(a[0]), "s": clean(a[2], 110)})
    branches = []
    for ln in refs.splitlines():
        a = ln.split("|", 2)
        if len(a) == 3 and a[1].isdigit() and re.match(r"(worktree-agent|claude/|chatgpt/|sprint/|agent)", a[0]):
            branches.append({"name": a[0][:50], "t": int(a[1]), "s": clean(a[2], 100)})
    return {"available": bool(commits), "commits": commits[:25], "branches": branches[:12]}


def build(root=ROOT, with_git=True):
    q = queue_tasks(read(os.path.join(root, "handoff", "QUEUE.md")))
    wu = writeup_rows(os.path.join(root, "research", "writeups"))
    mind = mind_block()
    dates = [r["date"] for r in wu if r["date"]] + ([mind["date"]] if mind["date"] else [])
    asof = max(dates) if dates else ""
    open_t = [t for t in q if not t["done"]]
    rejected = [{"date": r["date"], "title": r["title"], "file": r["file"], "summary": r["summary"]} for r in wu if r["status"] == "rejected"][:12]
    learnings = []
    for r in wu:
        if r["date"] and r["summary"] and r["status"] not in ("info", ""):
            learnings.append({"d": r["date"], "who": r["who"], "text": r["summary"], "src": r["file"], "kind": r["status"]})
    for o in mind["observations"]:
        learnings.append({"d": mind["date"], "who": "mind", "text": o["text"], "src": mind["source"], "kind": "observation"})
    learnings.sort(key=lambda x: (x["d"], x["src"]), reverse=True)
    return {"v": 1, "asof": asof, "note": "Built from handoff/QUEUE.md, research/writeups, the Mind's proposals and git (when present) by tools/ergasterion_build.py. Plain text only; nothing here is a trade.",
            "queue": {"total": len(q), "open": len(open_t), "done": len(q) - len(open_t), "tasks": open_t[:30]},
            "writeups": {"count": len(wu), "latest": [{k: r[k] for k in ("date", "title", "status", "summary", "file")} for r in wu[:12]]},
            "rejected": rejected, "rejected_ref": rejected_bullets(read(os.path.join(root, "docs", "CLAUDE_REFERENCE.md"))),
            "learnings": learnings[:70], "mind": mind, "git": git_block(root) if with_git else {"available": False, "commits": [], "branches": []}}


def dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def stable(text):
    try:
        d = json.loads(text)
    except ValueError:
        return None
    d.pop("git", None)
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    cur = build()
    if a.check:
        old = stable(read(a.out))
        new = stable(dump(cur))
        if old != new:
            print("ergasterion queue.json is out of date: run python tools/ergasterion_build.py")
            return 1
        print("ergasterion queue.json is current")
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(dump(cur))
    print(f"wrote {a.out}: {cur['queue']['open']} open tasks, {cur['writeups']['count']} write-ups, {len(cur['learnings'])} learnings, git {'yes' if cur['git']['available'] else 'no'}")
    return 0


def selftest():
    ok = []

    def ck(name, cond):
        ok.append(bool(cond))
        print(("[PASS] " if cond else "[FAIL] ") + name)
    ck("queue parse: open / done / section / bold id", [(t["id"], t["done"], t["section"]) for t in queue_tasks("## P1: fix\n- [ ] **a-b**: do it\n- [x] plain task\n")] == [("a-b", False, "P1"), ("plain task", True, "P1")])
    ck("front matter + first sentence", front("---\ntitle: T\nstatus: Rejected\n---\nx")["status"] == "Rejected" and norm_status("rejected - nothing to switch") == "rejected" and first_sentence("Owner asked this. Then more.") == "Owner asked this.")
    ck("who_of picks the worker", who_of("2026-11-04_kalshi_edges.md") == "kalshi" and who_of("lit-all-hours.md") == "lit" and who_of("zzz.md") == "dev")
    ck("rejected bullets read the reference section only", rejected_bullets("## Other\n- no\n## Tested and rejected (x)\n- yes one\n- yes two\n## Next\n- no") == ["yes one", "yes two"])
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "handoff"))
    os.makedirs(os.path.join(d, "research", "writeups"))
    with open(os.path.join(d, "handoff", "QUEUE.md"), "w", encoding="utf-8") as fh:
        fh.write("## P1\n- [ ] **t1**: one\n- [x] **t2**: two\n")
    with open(os.path.join(d, "research", "writeups", "2026-11-05_kalshi_x.md"), "w", encoding="utf-8") as fh:
        fh.write("---\ntitle: Kalshi X\ndate: 2026-11-05\nstatus: rejected\nsummary: Nothing survives after fees. More text.\n---\nbody")
    b = build(d, with_git=False)
    ck("build: counts, asof, rejected, learning with its source", b["queue"]["open"] == 1 and b["queue"]["done"] == 1 and b["asof"] == "2026-11-05" and len(b["rejected"]) == 1
       and any(x["who"] == "kalshi" and x["src"].endswith("kalshi_x.md") and x["text"] == "Nothing survives after fees." for x in b["learnings"]))
    ck("build is reproducible and --check ignores git", dump(b) == dump(build(d, with_git=False)) and stable(dump(b)) == stable(dump(dict(b, git={"available": True}))))
    ck("git block never raises on a folder that is not a repo", git_block(tempfile.mkdtemp())["available"] is False)
    print("ALL PASS" if all(ok) else "SOME FAILED")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
