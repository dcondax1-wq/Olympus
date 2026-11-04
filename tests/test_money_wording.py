"""Money wording guard (2026-11-04, owner: "room to floor should be directly what the drawdown is"; "R next to $").

Scans the text of every OLYMPUS app (tools/web_public/<app>/*.js and *.html, comments and vendor code left out) for the wording the owner banned:

  1. eval days as "X of 10": "day 6 of 10", "session 4 of 10", "6/10 days" ... (the eval clock is words and dates, never a count out of ten)
  2. "room to the floor" / "room to floor" on a line with no dollars (it must be "Drawdown left $X of $max loss", or carry the $ next to it)
  3. a progress bar or meter for the eval days (a bar is for dollars: the drawdown left, the $ to the target)
  4. an R figure as a headline (a big number, a <b>, a card value) with no $ on the same line ("+1.2R" alone): R always sits next to dollars

    python -X utf8 -m tests.test_money_wording            list every violation, exit 1 if there is one
    python -X utf8 -m tests.test_money_wording --report   list them and exit 0

A line that is allowed on purpose carries the marker  money-wording-ok  in a comment (say why).
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
SKIP_DIRS = {"fx", "mind", "olympus", "cache", "node_modules", "starter", "vendor"}
SKIP_FILES = ("three.module", ".min.js", "starter_pack")
OK = "money-wording-ok"

DAYS_OF_10 = re.compile(r"(?:\b(?:day|session)s?\s+(?:\S+\s+)?of\s+10\b|\b\d+\s+of\s+10\s+(?:days|sessions|eval)|\bof\s+10\s+(?:days|sessions)\b|\b(?:day|session)s?\s+[\w${}.()]+/10\b|\b\d+/10\s+(?:days|sessions))", re.I)
ROOM = re.compile(r"room\s+to\s+(?:the\s+)?floor", re.I)
MONEY = re.compile(r"\$(?!\{)|usd\(|sgn\(|money\(|fmtUsd|fmtMoney|Drawdown left|dollar", re.I)
PROGRESS = re.compile(r"(?:<progress|progress[- ]?bar|\bmeter\b)", re.I)
EVALDAYS = re.compile(r"(?:eval day|session|sessions|day \d+|days left|eval clock)", re.I)
R_FIG = re.compile(r"(?:\$\{[^}]*(?:toFixed|fmtR|round)[^}]*\}\s?R\b|>\s*[+−-]?\d+(?:\.\d+)?R\s*<|\bfmtR\()")
HEADLINE = re.compile(r"""(?:class=["'][^"']*\b(?:big|hero|headline|kpi|figure)\b|h\(['"](?:b|strong|big)['"]|<b>|<strong>|\bbig\b['"]|\.big\b)""")


def strip_comments(text: str, js: bool):
    """(line number, line) pairs with comments removed: whole-line comments, trailing // comments and block comments (good enough for a text guard)."""
    out, in_block = [], False
    for i, line in enumerate(text.split("\n"), 1):
        raw = line
        if in_block:
            if "*/" in line:
                line = line.split("*/", 1)[1]; in_block = False
            else:
                continue
        while "/*" in line and ("*/" in line.split("/*", 1)[1] or not js):
            a, b = line.split("/*", 1)
            line = a + (b.split("*/", 1)[1] if "*/" in b else "")
        if "/*" in line and js:
            line = line.split("/*", 1)[0]; in_block = True
        s = line.strip()
        if js and (s.startswith("//") or s.startswith("*")):
            continue
        if js:
            m = re.search(r"(?<![:\w'\"`])\s//\s", line)                         # a trailing comment, not a URL
            if m:
                line = line[:m.start()]
        if text and OK in raw:
            continue
        if line.strip():
            out.append((i, line))
    return out


def app_files():
    for app in sorted(os.listdir(WEB)):
        d = os.path.join(WEB, app)
        if not os.path.isdir(d) or app in SKIP_DIRS or app.startswith("."):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith((".js", ".html")) and not any(w in f for w in SKIP_FILES) and os.path.getsize(os.path.join(d, f)) < 600_000:
                yield app, f, os.path.join(d, f)


def scan(path: str):
    text = open(path, encoding="utf-8", errors="replace").read()
    out = []
    for n, line in strip_comments(text, path.endswith(".js")):
        if DAYS_OF_10.search(line):
            out.append((n, "eval days as 'X of 10'", line))
        if ROOM.search(line) and not MONEY.search(line):
            out.append((n, "'room to the floor' with no dollars on the line", line))
        if PROGRESS.search(line) and EVALDAYS.search(line) and not MONEY.search(line):
            out.append((n, "a progress bar / meter for the eval days", line))
        if R_FIG.search(line) and HEADLINE.search(line) and not MONEY.search(line):
            out.append((n, "an R headline figure with no $ on the line", line))
    return out


def self_test():
    """the guard must catch what it is for (and let the right wording through)"""
    bad = ["<p>day 6 of 10</p>", "`Session ${n} of 10`", "'4/10 days'", "<span>room to floor</span>", "h('b', '', `${r.toFixed(1)}R`)", "<b>+1.2R</b>",
           "<div class='meter'>session 4</div>"]
    good = ["<b>Drawdown left $1,805 of $2,000 max loss</b>", "<b>${usd(room)}</b><span>room to floor</span>", "h('b', '', `${sgn(u)} (${r.toFixed(1)}R)`)", "'top 10 rules'", "'payouts 2 of 5'"]
    ok = True
    for s in bad:
        hit = bool(DAYS_OF_10.search(s) or (ROOM.search(s) and not MONEY.search(s)) or (PROGRESS.search(s) and EVALDAYS.search(s) and not MONEY.search(s))
                   or (R_FIG.search(s) and HEADLINE.search(s) and not MONEY.search(s)))
        if not hit:
            print("[FAIL] the guard misses:", s); ok = False
    for s in good:
        hit = bool(DAYS_OF_10.search(s) or (ROOM.search(s) and not MONEY.search(s)) or (PROGRESS.search(s) and EVALDAYS.search(s) and not MONEY.search(s))
                   or (R_FIG.search(s) and HEADLINE.search(s) and not MONEY.search(s)))
        if hit:
            print("[FAIL] the guard flags good wording:", s); ok = False
    print(("[PASS] " if ok else "[FAIL] ") + "the guard catches the banned wording and lets the right wording through")
    return ok


def main():
    ok = self_test()
    total, files, per_app = 0, 0, {}
    for app, f, path in app_files():
        files += 1
        for n, why, line in scan(path):
            total += 1
            per_app.setdefault(app, []).append(f"{f}:{n}: {why}: {line.strip()[:150]}")
    print(f"[INFO] scanned {files} files in {len({a for a, _, _ in app_files()})} apps")
    for app, rows in per_app.items():
        print(f"[FAIL] {app}: {len(rows)} violation(s)")
        for r in rows:
            print("        " + r)
    if not total:
        print("[PASS] no banned money wording in any app")
    print(f"\n{'ALL CLEAN' if ok and not total else str(total) + ' violation(s)'}")
    return 0 if (ok and not total) or "--report" in sys.argv else 1


if __name__ == "__main__":
    sys.exit(main())
