#!/usr/bin/env python3
"""BRAIN HUB data (day-brain4 2026-11-22): every finding in research/findings/LEDGER.md and every bullet of docs/TESTED_AND_REJECTED.md
becomes one neuron of the giant 3D research brain (tools/web_public/cities/brain.html).

    python tools/build_brain_hub.py            write tools/web_public/cities/brain-data.json
    python tools/build_brain_hub.py --check    exit 1 when the committed JSON is stale (no write)

Output (small, gzip-friendly, privacy-clean: no phone, name, email, account id; masked by tools/site_privacy):
  { v, built, fam: [name...], n: [ {i, f, s, d, t, r, v, w, x} ... ], e: [[a, b], ...] }
  s = 'a' adopted / live (mint), 'r' rejected (red-violet), 'o' open / waiting on the owner (gold)
  f = family index, d = date (YYYY-MM-DD), t = short title, r = the result in plain words ($ a month when the text has one),
  v = the verdict line, w = write-up file stem (only when research/writeups/<stem>.md exists), x = 1 for a sub-bullet
  e = synapses (index pairs): same write-up, or two or more rare words in common (max 3 per neuron)
Stdlib only. Nothing is fetched; nothing live is touched.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "research", "findings", "LEDGER.md")
REJECTED = os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md")
WRITEUPS = os.path.join(ROOT, "research", "writeups")
OUT = os.path.join(ROOT, "tools", "web_public", "cities", "brain-data.json")

FAMILIES = ["LIT / Zlarior", "ATLAS", "BLITZ", "Rapid + fleet money", "Kalshi", "Websites + calls", "Ops"]
# first match wins (lower-case text of the title + body start)
FAM_RULES = [
    (2, r"\bblitz\b"),
    (1, r"\batlas\b"),
    (4, r"\bkalshi\b|\bweather market|\bprediction market"),
    (0, r"edge hunt|zlarior|\blit\b|regime guard"),
    (5, r"website|agency|cold.?call|rank.and.rent|pay.per|\bleads?\b|caller|factory|\boutreach\b|\bseo\b|\bclient"),
    (3, r"\brapid\b|\bfleet\b|payout|money plan|mffu|eval path|\bfunded\b|prop firm|\bcopy trad"),
    (0, r"zlarior|\blit\b|\blit-|\bnq\b|sweep|cisd|regime|edge hunt|\bsmt\b|orb\b|vwap|session|\bmes\b|\bes\b|backtest"),
]
OPEN_WORDS = ("OWNER", "WATCH", "CARD", "BRANCH", "OPEN", "HELD", "FIX IN", "FIX TON", "FIX TAX", "FIX SAT", "STATUS", "PENDING", "WAIT")


def clean(s: str) -> str:
    """markdown -> plain words, with anything private masked"""
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\*\*|__", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", s)                  # emails
    s = re.sub(r"(?<![\d-])\+?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b", "[number]", s)                 # US phone numbers
    s = re.sub(r"\b(MFFU[A-Z]*|SIM|PA|EV)[A-Z]*\d{5,}\b", "[account]", s)   # broker account ids
    s = re.sub(r"[A-Za-z]:\\Users\\[^\\\s]+", "<you>", s)
    return s


def short(s: str, n: int) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0].rstrip(",;:(-")
    return cut + "..."


def family(text: str) -> int:
    t = text.lower()
    for f, rx in FAM_RULES:
        if re.search(rx, t):
            return f
    return 6


def writeup_of(raw: str) -> str:
    for m in re.finditer(r"`?([A-Za-z0-9_.-]+)\.md`?", raw):
        stem = m.group(1)
        if os.path.exists(os.path.join(WRITEUPS, stem + ".md")):
            return stem
    return ""


MONEY = re.compile(r"[-+]?\$\s?[\d][\d,]*(?:\.\d+)?k?(?:\s?(?:a|per|/)\s?(?:month|mo|year|yr|trade|week))?", re.I)


def result_line(body: str) -> str:
    """the $ numbers first: the sentence(s) with a $ a month; else the first sentence with a $; else the first sentence"""
    sents = re.split(r"(?<=[.;])\s+(?=[A-Z0-9(])", body)
    for rx in (r"\$[^.;]{0,40}(?:a|per|/)\s?month|\bmonth\b[^.;]{0,30}\$|\$\s?[\d,]+\s*/\s*month", r"\$\s?[\d]"):
        hit = [x for x in sents if re.search(rx, x)]
        if hit:
            return short(" ".join(hit[:2]), 230)
    return short(sents[0] if sents else body, 200)


def parse_ledger() -> list:
    out = []
    for ln in open(LEDGER, encoding="utf-8"):
        if not ln.startswith("|"):
            continue
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) < 4 or not re.match(r"\d{4}-\d\d-\d\d", c[0]):
            continue
        date, finding, risk, status = c[0], c[1], c[2], "|".join(c[3:])
        up = status.upper()
        if up.startswith("REFUTED") or up.startswith("SKIPPED"):
            s, verdict = "r", "Rejected: " + short(clean(status), 90)
        elif up.startswith("FIXED") or up.startswith("LANDED") or up.startswith("DONE"):
            s, verdict = "a", "Adopted / live: " + short(clean(status), 90)
        elif any(up.startswith(w) for w in OPEN_WORDS) or up.startswith("FIX"):
            s, verdict = "o", "Open: " + short(clean(status), 90)
        else:
            s, verdict = "o", "Open: " + short(clean(status), 90)
        title = clean(finding)
        out.append(dict(d=date, s=s, t=short(title, 96), r=short(clean(risk), 200) or "no $ figure yet",
                        v=verdict, w=writeup_of(finding + " " + status), x=0, _body=title + " " + risk))
    return out


DATE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")


def parse_rejected() -> list:
    lines = open(REJECTED, encoding="utf-8").read().splitlines()
    items, cur = [], None
    for ln in lines:
        if ln.startswith("- "):
            cur = {"head": ln[2:], "sub": []}
            items.append(cur)
        elif re.match(r"^\s+- ", ln) and cur is not None:
            cur["sub"].append(ln.strip()[2:])
            cur["_in_sub"] = True
        elif ln.startswith("  ") and cur is not None:
            if cur["sub"] and cur.get("_in_sub"):
                cur["sub"][-1] += " " + ln.strip()
            else:
                cur["head"] += " " + ln.strip()
        elif not ln.strip() and cur is not None:
            cur["_in_sub"] = False
    out = []
    for it in items:
        parts = []
        parents = len(out)
        for k, raw in enumerate([it["head"]] + it["sub"]):
            m = re.match(r"\*\*(.+?)\*\*\s*(.*)", raw, re.S)
            head, body = (m.group(1), m.group(2)) if m else ("", raw)
            if head.endswith(":") is False and ":" in head and len(head) > 140:
                pass
            head0 = re.split(r"\s*\((?:20\d\d|\d\d? [A-Z]|[A-Za-z ]*20\d\d)", head)[0] if head else ""
            title = re.sub(r"^20\d\d-\d\d-\d\d\s+", "", clean(head0)) if head0 else short(clean(body), 90)
            body_c = clean(body) if head else clean(body)
            d = (DATE.search(raw) or [None, ""])[1] if DATE.search(raw) else ""
            out.append(dict(d=d, s="r", t=short(title.rstrip(":"), 96), r=result_line(body_c or title),
                            v="Rejected: tested, nothing beat costs in both halves; do not redo without a new idea.",
                            w=writeup_of(raw), x=1 if k else 0, _body=title + " " + body_c, _parent=parents if k else -1))
        # a 'sub' neuron is wired to its parent below
    return out


STOP = set("""the and for with that this from into than then when while only more most over under each same what which were was are not but
 all any one two three four five six per its off out has have had can day days week weeks month months year years trade trades
 variants variant tested test rejected result results idea ideas pass fail jan jun jul oct nov dec half halves cost costs
 live paper owner research write file files code line lane round""".split())


def words(s: str) -> set:
    return {w for w in re.findall(r"[a-z][a-z0-9-]{3,}", s.lower()) if w not in STOP}


def build() -> dict:
    nodes = parse_ledger() + parse_rejected()
    # parents of rejected sub-bullets were indexed inside the rejected list only; shift by the ledger count
    nled = len(parse_ledger())
    for n in nodes:
        n["f"] = family(n["_body"][:600])
    # sub-bullets keep their parent's family
    for n in nodes:
        p = n.get("_parent", -1)
        if p is not None and p >= 0:
            n["f"] = nodes[nled + p]["f"]
    # newest first inside each source keeps ids stable; ids are the position
    df: dict = {}
    ws = [words(n["_body"]) for n in nodes]
    for w in ws:
        for x in w:
            df[x] = df.get(x, 0) + 1
    edges, deg = set(), [0] * len(nodes)
    def add(a, b):
        if a == b or deg[a] >= 3 or deg[b] >= 3:
            return
        k = (min(a, b), max(a, b))
        if k not in edges:
            edges.add(k); deg[a] += 1; deg[b] += 1
    for i, n in enumerate(nodes):                                         # sub-bullet -> parent
        p = n.get("_parent", -1)
        if p is not None and p >= 0:
            edges.add((nled + p, i)); deg[nled + p] += 1; deg[i] += 1
    by_w: dict = {}
    for i, n in enumerate(nodes):
        if n["w"]:
            by_w.setdefault(n["w"], []).append(i)
    for ids in by_w.values():
        for a, b in zip(ids, ids[1:]):
            add(a, b)
    rare = {x for x, c in df.items() if 2 <= c <= 6}
    cands = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            sh = ws[i] & ws[j] & rare
            if len(sh) >= 2:
                cands.append((len(sh), i, j))
    for _, i, j in sorted(cands, reverse=True):
        add(i, j)
    out_nodes = []
    for i, n in enumerate(nodes):
        o = {"i": i, "f": n["f"], "s": n["s"], "d": n["d"], "t": n["t"], "r": n["r"], "v": n["v"]}
        if n["w"]:
            o["w"] = n["w"]
        if n.get("x"):
            o["x"] = 1
        out_nodes.append(o)
    # the data stamp = the newest finding date (stable between runs: no clock in the file)
    built = max([n["d"] for n in nodes if n["d"]] or [""])
    return {"v": 1, "built": built, "fam": FAMILIES, "n": out_nodes, "e": sorted([list(e) for e in edges])}


def dump(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"


def main(argv) -> int:
    doc = build()
    text = dump(doc)
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import site_privacy as SP
        hits = SP.scan_text(text, "brain-data.json")
        if hits:
            print("privacy: " + ", ".join(sorted({h.kind for h in hits})))
            return 1
    except ImportError:
        pass
    if "--check" in argv:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if cur != text:
            print("brain-data.json is stale: python tools/build_brain_hub.py")
            return 1
        print("brain-data.json up to date: %d neurons, %d synapses" % (len(doc["n"]), len(doc["e"])))
        return 0
    open(OUT, "w", encoding="utf-8", newline="\n").write(text)
    c = {s: sum(1 for n in doc["n"] if n["s"] == s) for s in "aro"}
    print("wrote %s: %d neurons (adopted %d, rejected %d, open %d), %d synapses, %d bytes" % (
        os.path.relpath(OUT, ROOT), len(doc["n"]), c["a"], c["r"], c["o"], len(doc["e"]), len(text.encode())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
