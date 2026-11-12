#!/usr/bin/env python3
"""Bundle docs/NQ_BOT_BACK.md for the NQ app's "Bring the bots back (3 steps)" sheet (tools/web_public/nq/).

    python tools/nq_howto_build.py            write tools/web_public/nq/howto.json
    python tools/nq_howto_build.py --check    exit 1 when the file is missing or no longer matches the doc (no write)

The sheet shows plain text only, so the markdown marks are dropped; the one copy-paste line of a step (the back-ticked line
that starts with "python ") is kept apart as "code". Stdlib only, deterministic (no clock), at most 5 steps.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "NQ_BOT_BACK.md")
OUT = os.path.join(ROOT, "tools", "web_public", "nq", "howto.json")
MAX_STEPS, MAX_TEXT, MAX_LIMIT, N_LIMITS = 5, 600, 300, 4


def plain(s: str) -> str:
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = s.replace("`", "")
    s = s.replace("<", "").replace(">", " then ") if re.search(r"<[a-zA-Z/]", s) else s
    return re.sub(r"\s+", " ", s).strip()


def first_sentences(s: str, limit: int) -> str:
    """Whole sentences up to `limit` characters (a bullet of the doc can be a paragraph)."""
    out = ""
    for part in re.split(r"(?<=[.!?])\s+", s):
        if out and len(out) + 1 + len(part) > limit:
            break
        out = (out + " " + part).strip()
    return out[:limit]


def section(md: str, title_re: str) -> str:
    m = re.search(rf"^## {title_re}[^\n]*\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    return m.group(1) if m else ""


def build(md: str) -> dict:
    head = re.search(r"^# (.+)$", md, re.M)
    date = re.search(r"\((\d{4}-\d{2}-\d{2})\)", head.group(1) if head else "")
    intro = next((ln.strip() for ln in md.split("\n")[1:] if ln.strip() and not ln.startswith(("#", "|"))), "")
    body = section(md, "Do this")
    steps, cur = [], None
    for ln in body.split("\n"):
        m = re.match(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(.*)$", ln)
        if m:
            cur = {"n": int(m.group(1)), "title": plain(m.group(2)).rstrip("."), "raw": m.group(3)}
            steps.append(cur)
        elif cur is not None and ln.startswith("   ") and ln.strip():
            cur["raw"] += " " + ln.strip()
        elif ln.strip() and not ln.startswith(" "):
            cur = None
    out_steps = []
    for s in steps:
        code = re.search(r"`(python [^`]+)`", s["raw"])
        raw = s["raw"].replace(code.group(0), "") if code else s["raw"]
        step = {"n": s["n"], "title": s["title"], "text": plain(raw)}
        if code:
            step["code"] = code.group(1).strip()
        out_steps.append(step)
    undo = next((plain(ln) for ln in body.split("\n") if ln.startswith("Undo")), "")
    limits = [first_sentences(plain(ln[2:]), MAX_LIMIT) for ln in section(md, "Honest limits").split("\n") if ln.startswith("- ")][:N_LIMITS]
    return {"v": 1, "source": "docs/NQ_BOT_BACK.md", "updated": date.group(1) if date else "", "title": "Bring the bots back",
            "intro": plain(intro), "steps": out_steps, "undo": undo, "limits": limits}


def problems(doc: dict) -> list[str]:
    p = []
    st = doc["steps"]
    if not 1 <= len(st) <= MAX_STEPS:
        p.append(f"{len(st)} steps (the owner's rule: at most {MAX_STEPS})")
    if [s["n"] for s in st] != list(range(1, len(st) + 1)):
        p.append("the steps are not numbered 1..n")
    for s in st:
        if not s["title"] or len(s["text"]) > MAX_TEXT:
            p.append(f"step {s['n']}: no title or more than {MAX_TEXT} characters")
    raw = json.dumps(doc)
    if re.search(r"(?i)(token|secret|password)\s*[:=]\s*[A-Za-z0-9_\-]{16,}", raw) or "<" in raw:
        p.append("looks like a secret or markup")
    return p


def render(doc: dict) -> str:
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    with open(DOC, encoding="utf-8") as fh:
        doc = build(fh.read())
    bad = problems(doc)
    if bad:
        print("nq_howto_build: " + "; ".join(bad))
        return 1
    text = render(doc)
    if "--check" in argv:
        try:
            with open(OUT, encoding="utf-8") as fh:
                same = fh.read() == text
        except OSError:
            same = False
        print(f"nq howto: {'up to date' if same else 'OUT OF DATE: run python tools/nq_howto_build.py'} ({len(doc['steps'])} steps)")
        return 0 if same else 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"nq howto: {len(doc['steps'])} steps, {len(doc['limits'])} limits -> {os.path.relpath(OUT, ROOT)} ({len(text.encode())} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
