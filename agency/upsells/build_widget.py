"""Rebuild agency/upsells/chat/widget.min.js from chat/widget.js (only needed after editing the widget source).

    python agency/upsells/build_widget.py           needs Node (npx fetches terser 5.39.0 the first time)
    python agency/upsells/build_widget.py --check   exit 1 when widget.min.js was not built from the current widget.js

The owner never runs this: make_chat.py uses the committed widget.min.js. The first line of the .min file holds the source's
sha256, which the test compares, so a source edit without a rebuild fails loudly.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "chat", "widget.js")
OUT = os.path.join(HERE, "chat", "widget.min.js")
TERSER = "terser@5.39.0"
OPTIONS = ["--ecma", "2017", "--compress", "passes=2", "--mangle", "--comments", "false"]


def src_hash() -> str:
    with open(SRC, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def stamp() -> str:
    return f"/*! Front-desk chat by agency/upsells: no tracking, no cookies, no storage; one request, the lead form post. src {src_hash()} */"


def built_hash() -> str:
    try:
        with open(OUT, encoding="utf-8") as fh:
            first = fh.readline()
    except FileNotFoundError:
        return ""
    return first.split(" src ")[-1].split(" ")[0] if " src " in first else ""


def build() -> str:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise SystemExit("Node.js (npx) is needed to rebuild the widget: https://nodejs.org")
    res = subprocess.run([npx, "--yes", TERSER, SRC] + OPTIONS, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0 or "__FDC_CONFIG__" not in res.stdout:
        raise SystemExit("terser failed:\n" + res.stderr[-2000:])
    code = stamp() + "\n" + res.stdout.strip() + "\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(code)
    return code


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        ok = built_hash() == src_hash()
        print("widget.min.js is " + ("up to date" if ok else "STALE: run python agency/upsells/build_widget.py"))
        return 0 if ok else 1
    code = build()
    print(f"chat/widget.min.js: {len(code.encode('utf-8')):,} bytes (runtime only, before a client's facts are added)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
