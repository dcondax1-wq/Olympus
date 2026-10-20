"""research/writeups/INDEX.md is current (tools/writeups_index.py --check) and the dashboards do not list it as a write-up.

  python -X utf8 -m tests.test_writeups_index
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import writeups_index as W  # noqa: E402

R = []


def check(name, ok, info=""):
    R.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' - ' + str(info) if info else ''}")


def main():
    rows = W.rows()
    check("every write-up has a title and a date", all(r["title"] and r["date"] != "-" for r in rows),
          [r["file"] for r in rows if not r["title"] or r["date"] == "-"])
    check("INDEX.md up to date (rerun tools/writeups_index.py)", W.main(["--check"]) == 0)
    txt = W.render()
    check("every write-up linked once", all(txt.count(f"]({r['file']})") == 1 for r in rows))
    check("verdicts", W.verdict("rejected - nothing adopted") == "rejected" and W.verdict("one small adopt-candidate (x)") == "adopt-candidate"
          and W.verdict("no adopt-candidate; one promising target idea") == "promising" and W.verdict("finding") == "finding")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from engine import next_api
    app = FastAPI()
    app.include_router(next_api.router)
    items = TestClient(app).get("/api/next/writeups").json()["items"]
    check("PC Write-ups page skips INDEX.md", not any(i["file"].endswith("INDEX.md") for i in items), len(items))
    print(f"writeups_index: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
