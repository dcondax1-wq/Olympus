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
  * events  : ONE DATED EVENT STREAM for the day replay: research runs (research/runs/*.json "built", batched per hour and worker), write-up dates, the Mind's last research,
              dated done items of the queue. Git commits (the git block) and the money machines' asof times (money_runs, read from <site>/money/*.json next to --out) are
              volatile, so they live in their own keys and --check ignores them; the page merges all of it.
  * lessons : the LEARNING ENGINE. Every sentence comes from a file (write-up summaries and verdict lines, the "Tested and rejected" list, the Mind's notes). Near-duplicates
              are merged, `strength` counts the independent source files that agree, each lesson has its sources, date and category (NQ strategy, Kalshi, money, process, app).
  * changed : "what changed our mind": sentences where a write-up says an earlier belief did not hold (e.g. the 95c+ Kalshi pocket), with the file.
  * pipeline: Idea -> Testing -> Verdict counts per strategy family and the newest 20 moves, from tools/web_public/archive/index.json (or research/runs when it is missing)
  * gaps    : data sets that end well before the newest research date (for the "what next" planner)
It also writes lessons.json next to queue.json (for Jarvis: "what did we learn this week").
`asof` is the newest date found in the sources (not the clock), so the files are reproducible.
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
MONEY_IDS = ("chrysos", "mercury", "sibyl", "oikos", "arbiter")
CATS = ("NQ strategy", "Kalshi", "money", "process", "app")
STOP = set("""about above after again against also among because been before being below between both cannot could does doing down during each every from have having here into just like
 made make many more most much must never only other over same should since some such than that their them then there these they this those through under until very were what when where
 which while with within without would your even still adds added gives given using used uses shows show showed found find kept keep keeps takes take took gets comes came goes went none
 2026 2021 2025 2024 2023 2022 trades trade week weeks month months data test tests tested result results""".split())
FLIP = re.compile(r"earlier (finding|result|belief|claim)|previous(ly)? (finding|belief|result|thought)|we (had )?thought|looked real|used to (think|believe)|vanished|did not hold|does not hold"
                  r"|no longer holds|turned out (to be )?(noise|wrong|false|luck)|was (only )?luck", re.I)
NEG = re.compile(r"reject|no edge|not an edge|worse|loses|lose money|no gain|nothing (survives|to switch|adopt)|does not|did not|fails\b|failed|vanish|noise|none (beats|of|gives|is|beat)|no real|not predictive", re.I)
NOEDGE = re.compile(r"no edge|not an edge|edge that survives|none (beat|beats|gives)|nothing survives|loses (money )?after (fees|costs)", re.I)
POS = re.compile(r"adopt|better|holds|improv|beats|survives|raises|gain", re.I)
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


def lesson_sentence(text, n=220):
    """The sentence of a summary that carries the verdict (the first one that says rejected / no edge / adopt / better ...), else its first real sentence. Lifted, never rewritten."""
    t = re.sub(r"^(?:[-*]\s+)?(?:Job \d+\.\s*)?(?:Part [A-Z0-9]+\s*[-:]\s*)?(?:\(\d\)\s*)?", "", clean(text, 900))
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", t) if len(x.strip()) >= 25]
    sents = [x for x in sents if not re.match(r"Owner \d{4}", x)] or sents          # the owner's request is the question, not the lesson
    for x in sents[:5]:
        if NEG.search(x) or POS.search(x):
            return clean(x, n)
    return clean(sents[0] if sents else t, n)


def who_of(name, title=""):
    for low, skip in ((name.lower(), ()), (title.lower(), ("money", "mind", "lit"))):     # the file name decides; a title only counts when it names a worker ("lose money" is not Chrysos)
        for key, wid in WHO:
            if key not in skip and re.search(r"(^|[^a-z])" + key + r"($|[^a-z])", low):
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
    if low.startswith(("rejected", "no ", "nothing", "none")):
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
        text = read(os.path.join(folder, n))
        meta = front(text)
        d = DATE.search(meta.get("date", "")) or DATE.match(n) or DATE.search("\n".join(text.splitlines()[:6]))
        status, summary = norm_status(meta.get("status")), lesson_sentence(meta.get("summary", ""))
        if not status and re.search(r"no edge found|rejected", meta.get("title", ""), re.I):
            status = "rejected"                       # a write-up with no front matter whose title is its verdict
        if not summary:
            summary = body_verdict(text)
            if summary and not status:
                status = "finding"
        rows.append({"date": d.group(1) if d else "", "title": clean(meta.get("title") or n[:-3], 110), "status": status,
                     "summary": summary, "file": "research/writeups/" + n, "who": who_of(n, meta.get("title", "")), "flips": flip_lines(text)})
    rows.sort(key=lambda r: (r["date"], r["file"]), reverse=True)
    return rows


def body_verdict(text):
    """A write-up without front matter: the first real sentence under its answer / verdict heading (never invented, only lifted)."""
    m = re.search(r"^##\s+(?:the answer|verdict|answer|summary|result)[^\n]*\n+((?:(?!^#).*\n?)+)", text, re.I | re.M)
    if not m:
        return ""
    for para in re.split(r"\n\s*\n", m.group(1)):
        p = para.strip()
        if p and not p.startswith("|") and len(p) > 30:
            t = clean(p, 700)
            head = first_sentence(t, 200)
            if len(head) >= 40 and (NEG.search(head) or POS.search(head)):
                return head
            rest = lesson_sentence(t[len(head):]) if len(t) > len(head) + 25 else ""   # "No edge found." alone says too little: add the sentence that carries the verdict
            return clean((head + " " + rest).strip(), 240) if len(head) < 40 else (rest or head)
    return ""


def flip_lines(text, cap=2):
    """Sentences where the write-up itself says an earlier belief did not hold. Lifted as written (wrapped lines joined); `was` is the quoted old belief when the sentence quotes it."""
    out = []
    body = text.split("\n---", 1)[1] if text.startswith("---") and "\n---" in text[3:] else text
    blocks, cur = [], []
    for line in body.splitlines() + [""]:
        st = line.strip()
        if not st or st.startswith(("|", "#", "```")) or re.match(r"(?:[-*]|\d+\.)\s", st):
            if cur:
                blocks.append(" ".join(cur))
            cur = [re.sub(r"^(?:[-*]|\d+\.)\s+", "", st)] if st and not st.startswith(("|", "#", "```")) else []
        else:
            cur.append(st)
    for b in blocks:
        sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z(\"])", clean(b, 1500)) if x.strip()]
        for i, sn in enumerate(sents):
            if len(sn) < 40 or not FLIP.search(sn):
                continue
            q = re.search(r'"([^"]{12,160})"', sn)
            full = sn + (" " + sents[i + 1] if i + 1 < len(sents) and re.search(r"earlier|previous|thought|looked real|used to", sn, re.I) and not re.search(r"vanished|did not hold|not an edge", sn, re.I) else "")
            out.append({"text": clean(full, 300), "was": clean(q.group(1), 160) if q else ""})
            break
        if len(out) >= cap:
            break
    return out


def category(who, text):
    low = (who + " " + text).lower()
    if who in ("kalshi", "sibyl") or "kalshi" in low or "prediction market" in low:
        return "Kalshi"
    if who in ("chrysos", "mercury", "oikos", "arbiter") or re.search(r"prop[- ]firm price|discount code|savings rate|payout plan", low):
        return "money"
    if re.search(r"\b(olympus|dashboard|app|page|screen|iphone|3d)\b", low) and who == "dev":
        return "app"
    if who in ("lit", "atlas", "blitz", "prometheus", "hephaestus", "mind") or re.search(r"\b(nq|lit|atlas|blitz|stop|target|eval|sweep|cisd|session|sizing|micros?)\b", low):
        return "NQ strategy"
    return "process"


def tokens(text):
    return frozenset(w for w in re.findall(r"[a-z][a-z0-9+-]{3,}", re.sub(r"[`*]", "", text.lower())) if w not in STOP)


def polarity(text):
    return -1 if NEG.search(text) else 1 if POS.search(text) else 0


def distil(cands, limit=60):
    """The learning engine: merge near-duplicates, count the independent source files that agree, newest first.
    cands = [{text, src, d, who, kind}]. Deterministic: the input is sorted first, ties break on the source name."""
    cands = sorted((c for c in cands if c.get("text") and c.get("src")), key=lambda c: (c.get("d") or "", c["src"], c["text"]), reverse=True)
    toks = [tokens(c["text"]) for c in cands]
    df = {}
    for t in toks:
        for w in t:
            df[w] = df.get(w, 0) + 1
    common = {w for w, n in df.items() if n > max(3, len(cands) * 0.08)}
    rare = [t - common for t in toks]
    groups = []                                           # each: the index of the representative first, then the indexes merged into it
    for i in range(len(cands)):
        hit = None
        for g in groups:
            a, b = toks[g[0]], toks[i]
            inter = len(a & b)
            if inter >= 4 and inter / max(1, min(len(a), len(b))) >= 0.6:
                hit = g
                break
        if hit:
            hit.append(i)
        else:
            groups.append([i])
    out = []
    for g in groups:
        rep = cands[g[0]]
        cat, pol = category(rep.get("who", ""), rep["text"]), polarity(rep["text"])
        src = {}
        for i in g:
            src.setdefault(cands[i]["src"], cands[i].get("d") or "")
        for j, c in enumerate(cands):                    # supporters: another file, same category, same direction, at least 3 uncommon words shared, or both say "no edge" about the same worker
            if j in g or c["src"] in src:
                continue
            same = category(c.get("who", ""), c["text"]) == cat and polarity(c["text"]) == pol
            if same and (len(rare[g[0]] & rare[j]) >= 3 or (NOEDGE.search(rep["text"]) and NOEDGE.search(c["text"]) and c.get("who") == rep.get("who"))):
                src[c["src"]] = c.get("d") or ""
        srcs = sorted(({"src": k, "d": v} for k, v in src.items()), key=lambda x: (x["d"], x["src"]), reverse=True)
        out.append({"text": rep["text"], "cat": cat, "who": rep.get("who") or "dev", "d": rep.get("d") or "", "kind": rep.get("kind") or "", "strength": len(srcs), "merged": len(g),
                    "sources": srcs[:5]})
    out.sort(key=lambda x: (x["d"], x["strength"], x["sources"][0]["src"], x["text"]), reverse=True)
    return out[:limit]


def iso_t(text):
    """'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' (taken as UTC, as written in the file) -> epoch seconds"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?", str(text))
    if not m:
        return 0
    y, mo, d, hh, mi = (int(x) if x else None for x in m.groups())
    try:
        return int(dt.datetime(y, mo, d, 12 if hh is None else hh, mi or 0, tzinfo=dt.timezone.utc).timestamp())
    except ValueError:
        return 0


def run_events(folder):
    """research/runs/*.json -> one event per (hour, worker): how many runs were stored and their verdicts. Only the head of each file is read."""
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith(".json"))
    except OSError:
        return [], {}
    batch, fam = {}, {}
    for n in names:
        try:
            with open(os.path.join(folder, n), encoding="utf-8") as fh:
                head = fh.read(6000)
        except OSError:
            continue

        def g(k):
            m = re.search(r'"%s":\s*"([^"]*)"' % k, head)
            return m.group(1) if m else ""
        family, status, built = g("family") or "other", g("status"), g("built")
        verdict = "adopted" if status.startswith("adopt") or status == "live" else "rejected" if status.startswith("reject") else "open"
        f = fam.setdefault(family, {"name": clean(family, 40), "runs": 0, "adopted": 0, "rejected": 0, "open": 0})
        f["runs"] += 1
        f[verdict] += 1
        m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})", built)
        if not m:
            continue
        who = who_of(n, family + " " + g("tags"))
        who = who if who in ("atlas", "blitz", "kalshi") else "lit" if family.lower().startswith("lit") else "dev"
        b = batch.setdefault((m.group(1), m.group(2), who), {"n": 0, "adopted": 0, "rejected": 0, "open": 0, "last": "", "fam": {}})
        b["n"] += 1
        b[verdict] += 1
        b["last"] = max(b["last"], built[:16].replace("T", " "))
        b["fam"][family] = b["fam"].get(family, 0) + 1
    ev = []
    for (_day, _hh, who), b in batch.items():
        top = sorted(b["fam"].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        parts = [f"{b[k]} {k}" for k in ("adopted", "rejected", "open") if b[k]]
        ev.append({"t": iso_t(b["last"]), "who": who, "kind": "run", "ok": True,
                   "text": clean(f"{b['n']} research run{'s' if b['n'] != 1 else ''} stored ({top}): {', '.join(parts)}.", 150), "src": "research/runs"})
    return ev, fam


def event_stream(root, wu, q, mind, days=45, cap=260):
    ev, fam = run_events(os.path.join(root, "research", "runs"))
    for r in wu:
        if r["date"]:
            st = r["status"]
            ev.append({"t": iso_t(r["date"]), "who": r["who"], "kind": "writeup", "ok": True, "text": clean("Write-up" + (" (" + st + ")" if st else "") + ": " + r["title"], 150), "src": r["file"]})
    for t in q:
        d = DATE.search(t["text"]) if t["done"] else None
        if d:
            ev.append({"t": iso_t(d.group(1)), "who": "queue", "kind": "task", "ok": True, "text": clean("Done: " + t["id"], 150), "src": "handoff/QUEUE.md"})
    if mind.get("t"):
        ev.append({"t": int(mind["t"]), "who": "mind", "kind": "mind", "ok": True, "src": mind["source"],
                   "text": clean(f"Nightly research: {mind['tested']} ideas tested, {len(mind['observations'])} notes about recent trades.", 150)})
    ev = [e for e in ev if e["t"] > 0]
    ev.sort(key=lambda e: (e["t"], e["who"], e["kind"], e["text"]), reverse=True)
    if ev:
        floor = ev[0]["t"] - days * 86400
        ev = [e for e in ev if e["t"] >= floor]
    return ev[:cap], fam


def pipeline_block(root, fam_scan):
    """Idea -> Testing -> Verdict per strategy family + the newest 20 moves, from the Archive's own index (tools/web_public/archive/index.json and its shards)."""
    adir = os.path.join(root, "tools", "web_public", "archive")
    try:
        idx = json.loads(read(os.path.join(adir, "index.json")) or "null")
    except ValueError:
        idx = None
    if isinstance(idx, dict) and isinstance(idx.get("families"), list):
        fams = [{"name": clean(f.get("name"), 40), **{k: int(f.get(k) or 0) for k in ("runs", "adopted", "rejected", "open")}} for f in idx["families"] if isinstance(f, dict)]
        rows = list(idx.get("runs") or [])
        for sh in idx.get("shards") or []:
            try:
                rows += json.loads(read(os.path.join(adir, str(sh))) or "{}").get("runs") or []
            except (ValueError, AttributeError):
                pass
        verd = idx.get("verdicts") or ["adopted", "rejected", "open"]
        seen, moves = set(), []
        for r in rows:
            if isinstance(r, list) and len(r) > 6 and r[0] not in seen and re.match(r"\d\d-\d\d-\d\d$", str(r[6])):
                seen.add(r[0])
                moves.append({"id": clean(r[0], 50), "title": clean(r[1], 110), "family": clean(r[2], 40), "verdict": verd[r[4]] if isinstance(r[4], int) and 0 <= r[4] < len(verd) else "open", "d": "20" + r[6]})
        moves.sort(key=lambda m: (m["d"], m["id"]), reverse=True)
        src, built = "archive/index.json", str(idx.get("built") or "")[:10]
    else:
        idx, fams, moves, src, built = None, [dict(f) for f in fam_scan.values()], [], "research/runs", ""
    fams.sort(key=lambda f: (-f["runs"], f["name"]))
    tot = {k: sum(f[k] for f in fams) for k in ("runs", "adopted", "rejected", "open")}
    return {"src": src, "built": built, "counts": {"ideas": tot["runs"], "testing": tot["open"], "adopted": tot["adopted"], "rejected": tot["rejected"]}, "families": fams[:16], "moves": moves[:20]}, idx


def gaps_block(idx, asof):
    out = []
    if not (isinstance(idx, dict) and asof):
        return out
    a = dt.date.fromisoformat(asof)
    for ds in idx.get("datasets") or []:
        last = DATE.match(str(ds.get("last") or "")) if isinstance(ds, dict) else None
        if last:
            n = (a - dt.date.fromisoformat(last.group(1))).days
            if n >= 14:
                out.append({"name": clean(ds.get("name"), 50), "last": last.group(1), "days": n, "file": clean(ds.get("file"), 80)})
    out.sort(key=lambda g: (-g["days"], g["name"]))
    return out[:8]


def money_runs(out_path):
    """The money machines' own asof times, read from <site>/money/<id>.json next to the output (volatile: never part of --check)."""
    folder, rows = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(out_path))), "money"), []
    for mid in MONEY_IDS:
        try:
            d = json.loads(read(os.path.join(folder, mid + ".json")) or "null")
        except ValueError:
            d = None
        if isinstance(d, dict) and DATE.match(str(d.get("asof") or "")):
            hl = d.get("headline")
            rows.append({"t": iso_t(str(d["asof"])[:16]), "who": mid, "kind": "money", "ok": d.get("status") not in ("error", "failed"), "sample": d.get("status") == "sample",
                         "text": clean((hl.get("text") if isinstance(hl, dict) else hl) or "ran", 150), "src": "money/" + mid + ".json"})
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


def build(root=ROOT, with_git=True, out_path=None):
    q = queue_tasks(read(os.path.join(root, "handoff", "QUEUE.md")))
    wu = writeup_rows(os.path.join(root, "research", "writeups"))
    mind = mind_block() if root == ROOT else {"tested": 0, "t": 0, "date": "", "observations": [], "source": ""}
    dates = [r["date"] for r in wu if r["date"]] + ([mind["date"]] if mind["date"] else [])
    asof = max(dates) if dates else ""
    open_t = [t for t in q if not t["done"]]
    rejected = [{"date": r["date"], "title": r["title"], "file": r["file"], "summary": r["summary"]} for r in wu if r["status"] == "rejected"][:12]
    ref = rejected_bullets(read(os.path.join(root, "docs", "CLAUDE_REFERENCE.md")))
    learnings = []
    for r in wu:
        if r["date"] and r["summary"] and r["status"] not in ("info", ""):
            learnings.append({"d": r["date"], "who": r["who"], "text": r["summary"], "src": r["file"], "kind": r["status"]})
    concl = [x for x in learnings if polarity(x["text"])]             # a lesson is a conclusion: the sentence must carry a verdict word, a plain description stays a "learning" of its worker
    for o in mind["observations"]:
        learnings.append({"d": mind["date"], "who": "mind", "text": o["text"], "src": mind["source"], "kind": "observation"})
    learnings.sort(key=lambda x: (x["d"], x["src"]), reverse=True)
    concl += [x for x in learnings if x["kind"] == "observation"]
    cands = concl + [{"d": (DATE.search(b) or [""])[0], "who": who_of("", b), "text": "Tested and rejected: " + b, "src": "docs/CLAUDE_REFERENCE.md", "kind": "rejected"} for b in ref]
    lessons = distil(cands)
    changed = []
    for r in wu:
        for f in r["flips"]:
            changed.append({"text": f["text"], "was": f["was"], "d": r["date"], "who": r["who"], "cat": category(r["who"], f["text"] + " " + r["title"]), "src": r["file"]})
    changed.sort(key=lambda x: (x["d"], x["src"], x["text"]), reverse=True)
    events, fam = event_stream(root, wu, q, mind)
    pipe, idx = pipeline_block(root, fam)
    return {"v": 2, "asof": asof, "note": "Built from handoff/QUEUE.md, research/writeups, research/runs, the Archive index, the Mind's proposals and git (when present) by tools/ergasterion_build.py. Plain text only; nothing here is a trade.",
            "queue": {"total": len(q), "open": len(open_t), "done": len(q) - len(open_t), "tasks": open_t[:30]},
            "writeups": {"count": len(wu), "latest": [{k: r[k] for k in ("date", "title", "status", "summary", "file")} for r in wu[:12]]},
            "rejected": rejected, "rejected_ref": ref,
            "learnings": learnings[:70], "lessons": lessons, "changed": changed[:12], "events": events, "pipeline": pipe, "gaps": gaps_block(idx, asof), "mind": mind,
            "money_runs": money_runs(out_path) if out_path else [],
            "git": git_block(root) if with_git else {"available": False, "commits": [], "branches": []}}


def week_of(rows, asof, days=7):
    if not asof:
        return []
    lo = (dt.date.fromisoformat(asof) - dt.timedelta(days=days)).isoformat()
    return [r for r in rows if r.get("d") and lo < r["d"] <= asof]


def lessons_file(b):
    """lessons.json for Jarvis ("what did we learn this week"): the week's lessons (by the newest research date), the strongest ones, and what changed our mind."""
    L, asof = b["lessons"], b["asof"]

    def slim(x):
        return {"text": x["text"], "cat": x["cat"], "d": x["d"], "strength": x["strength"], "sources": [s["src"] for s in x["sources"][:3]]}
    week = sorted(week_of(L, asof), key=lambda x: (x["strength"], x["d"], x["text"]), reverse=True)
    top = sorted(L, key=lambda x: (x["strength"], x["d"], x["text"]), reverse=True)
    ch = [{"text": c["text"], "was": c["was"], "cat": c["cat"], "d": c["d"], "source": c["src"]} for c in b["changed"][:6]]
    cats = {c: sum(1 for x in L if x["cat"] == c) for c in CATS}
    if week:
        say = f"This week we wrote down {len(week)} lesson{'s' if len(week) != 1 else ''}. The strongest ({week[0]['strength']} file{'s' if week[0]['strength'] != 1 else ''} agree): {clean(week[0]['text'], 200)}"
    elif L:
        say = f"No new lesson in the 7 days to {asof}. The newest, from {L[0]['d'] or 'an undated note'}: {clean(L[0]['text'], 200)}"
    else:
        say = "No lessons are written down yet."
    if ch:
        say += " What changed our mind: " + clean(ch[0]["text"], 220)
    return {"v": 1, "name": "Ergasterion lessons", "asof": asof, "say": clean(say, 520), "week": [slim(x) for x in week[:8]], "top": [slim(x) for x in top[:8]], "changed": ch, "counts": cats,
            "note": "Every lesson is a sentence lifted from a file in the repo; strength = how many independent files agree. Research notes, never a trade signal."}


def dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def stable(text):
    try:
        d = json.loads(text)
    except ValueError:
        return None
    d.pop("git", None)
    d.pop("money_runs", None)
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    cur = build(out_path=a.out)
    lpath = os.path.join(os.path.dirname(os.path.abspath(a.out)), "lessons.json")
    if a.check:
        old = stable(read(a.out))
        new = stable(dump(cur))
        if old != new or read(lpath) != dump(lessons_file(cur)):
            print("ergasterion queue.json / lessons.json is out of date: run python tools/ergasterion_build.py")
            return 1
        print("ergasterion queue.json and lessons.json are current")
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(dump(cur))
    with open(lpath, "w", encoding="utf-8") as fh:
        fh.write(dump(lessons_file(cur)))
    print(f"wrote {a.out} (+ lessons.json): {cur['queue']['open']} open tasks, {cur['writeups']['count']} write-ups, {len(cur['lessons'])} lessons ({len(cur['changed'])} changed our mind), "
          f"{len(cur['events'])} events, {cur['pipeline']['counts']['ideas']} ideas in the pipeline, git {'yes' if cur['git']['available'] else 'no'}")
    return 0


def selftest():
    ok = []

    def ck(name, cond, why=None):
        ok.append(bool(cond))
        print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond or why is None else "  -> " + str(why)[:700]))
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
    # the learning engine
    c = [{"text": "Buying favourites priced above ninety cents on Kalshi loses money after fees and spread.", "src": "a.md", "d": "2026-11-10", "who": "kalshi", "kind": "rejected"},
         {"text": "Buying favourites priced above ninety cents on Kalshi loses money after the fees and the spread!", "src": "b.md", "d": "2026-11-09", "who": "kalshi", "kind": "rejected"},
         {"text": "Spread plus fees wipe out every Kalshi favourite pocket near ninety cents upward: rejected, no edge.", "src": "c.md", "d": "2026-11-08", "who": "kalshi", "kind": "rejected"},
         {"text": "A wider stop means fewer micros so the risk in dollars stays the same.", "src": "d.md", "d": "2026-10-01", "who": "lit", "kind": "finding"},
         {"text": "", "src": "e.md"}, {"text": "no source"}]
    L = distil(c)
    ck("lessons: near-duplicates merge into one (newest wording kept), strength counts the independent files that agree, each lesson keeps its sources, date and category",
       len(L) == 3 and L[0]["text"].endswith("spread.") and L[0]["merged"] == 2 and L[0]["strength"] == 3 and [x["src"] for x in L[0]["sources"]] == ["a.md", "b.md", "c.md"]
       and L[0]["cat"] == "Kalshi" and L[1]["merged"] == 1 and L[1]["strength"] == 3 and L[2]["cat"] == "NQ strategy" and L[2]["strength"] == 1 and L[0]["d"] == "2026-11-10", L)
    ck("lessons: the same input in any order gives the same output (deterministic)", dump(distil(list(reversed(c)))) == dump(L))
    ck("a lesson is the sentence that carries the verdict, not the job description", lesson_sentence("Job 27. Part 1 - ATLAS and BLITZ were re-tested with 72 versions. None beats today's rules after costs. More.") == "None beats today's rules after costs.")
    ck("categories: Kalshi, money, NQ strategy, app, process", [category("sibyl", "x"), category("mercury", "x"), category("dev", "the stop sits beyond the sweep"), category("dev", "the dashboard page is slow"), category("dev", "commit often")] == ["Kalshi", "money", "NQ strategy", "app", "process"])
    fl = flip_lines('# T\n- The earlier finding "95c and above is +1.4% per $" came from the bot\'s own bets. On the market-wide data it is not an edge.\n| a table row that looked real | x |\nshort vanished\n')
    ck("what changed our mind: the sentence is lifted as written, with the old belief it quotes; tables and short lines are skipped", len(fl) == 1 and fl[0]["was"] == "95c and above is +1.4% per $" and "market-wide" in fl[0]["text"], fl)
    bv = body_verdict("# X: NO EDGE FOUND\n\n2026-11-10. Research.\n\n## The answer\n\n**No edge found.** Out of the 38 cells none beat the noise on training data. More.\n")
    ck("a write-up without front matter: its first answer sentences are lifted from the body", bv == "No edge found. Out of the 38 cells none beat the noise on training data.", bv)
    # the event stream
    os.makedirs(os.path.join(d, "research", "runs"))
    for i, (st, built, famn) in enumerate([("rejected", "2026-11-04 21:10", "filters"), ("adopt-candidate", "2026-11-04 21:40", "filters"), ("open", "2026-11-03 09:00", "ATLAS"), ("rejected", "", "ATLAS"), ("rejected", "2026-01-01 09:00", "old")]):
        with open(os.path.join(d, "research", "runs", f"r{i}.json"), "w", encoding="utf-8") as fh:
            json.dump({"id": f"r{i}", "title": "t", "family": famn, "status": st, "built": built, "trades": []}, fh)
    with open(os.path.join(d, "handoff", "QUEUE.md"), "a", encoding="utf-8") as fh:
        fh.write("- [x] **t3**: shipped 2026-11-02\n")
    b2 = build(d, with_git=False)
    ev = b2["events"]
    ck("event stream: research runs batched per hour and worker (2 filter runs = 1 event, verdicts counted), the write-up and the dated done task are there, an undated run and one older than 45 days are left out",
       [(e["who"], e["kind"]) for e in ev] == [("kalshi", "writeup"), ("dev", "run"), ("atlas", "run"), ("queue", "task")] and ev[1]["text"] == "2 research runs stored (filters): 1 adopted, 1 rejected." and ev[1]["t"] == iso_t("2026-11-04 21:40"), ev)
    ck("event stream: newest first, every event has a time, a worker, plain text and its source; building twice gives the same bytes", all(ev[i]["t"] >= ev[i + 1]["t"] for i in range(len(ev) - 1)) and all(e["t"] and e["who"] and e["text"] and e["src"] for e in ev) and dump(b2) == dump(build(d, with_git=False)))
    ck("pipeline without the Archive index: families counted from research/runs (ideas = runs, testing = open)", b2["pipeline"]["src"] == "research/runs" and b2["pipeline"]["counts"] == {"ideas": 5, "testing": 1, "adopted": 1, "rejected": 3}, b2["pipeline"])
    lf = lessons_file(b2)
    ck("lessons.json for Jarvis: a plain 'say' sentence, the week, the strongest, what changed, counts per category; money_runs never part of --check",
       lf["say"].startswith("This week we wrote down 1 lesson") and len(lf["week"]) == 1 and lf["top"] and set(lf["counts"]) == set(CATS) and stable(dump(dict(b2, money_runs=[{"t": 1}]))) == stable(dump(b2)), lf)
    md = os.path.join(d, "site", "money")
    os.makedirs(md)
    with open(os.path.join(md, "sibyl.json"), "w", encoding="utf-8") as fh:
        json.dump({"asof": "2026-11-10T06:30:00Z", "status": "sample", "headline": {"text": "3 picks"}}, fh)
    mr = money_runs(os.path.join(d, "site", "ergasterion", "queue.json"))
    ck("money machines: asof times are read from <site>/money next to the output, sample is flagged", len(mr) == 1 and mr[0]["who"] == "sibyl" and mr[0]["sample"] and mr[0]["t"] == iso_t("2026-11-10 06:30") and mr[0]["text"] == "3 picks", mr)
    print("ALL PASS" if all(ok) else "SOME FAILED")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
