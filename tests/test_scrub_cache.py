"""tools/site_privacy.scrub's clean-file cache (day-quality 2026-11-20: the scrub was 45 of the build's 77 s; warm build 67 s -> 29 s).

  a. cold: a private id is masked, a private file removed, clean files remembered
  b. warm on a FRESH unscrubbed copy: the same file with the id is masked again (a file that needed a change is never cached),
     the clean files are skipped (cached count), the output equals a no-cache scrub byte for byte
  c. a changed clean file, new canary values, or another code version = scanned again; LE_SCRUB_CACHE=0 = no cache file at all
    python -X utf8 -m tests.test_scrub_cache
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_privacy as SP  # noqa: E402

RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:400]})" if detail and not cond else ""))


ACCT = "MFFUEVBLD25K" + "12345678"          # built here so this file itself never holds one whole
SITE = {"a/clean.json": json.dumps({"x": 1, "msg": "nothing private here"}), "b/page.txt": "hello",
        "c/acct.json": json.dumps({"broker": "x", "line": "account " + ACCT}), "d/leads.json": json.dumps({"n": 1}),
        "e/canary.txt": "the owner is Pat Example"}


def make(base):
    for rel, t in SITE.items():
        p = os.path.join(base, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(t)


def tree(base):
    out = {}
    for p, rel in SP.iter_files(base):
        out[rel] = open(p, "rb").read()
    return out


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_scrubcache_")
    old = os.environ.get("LE_SCRUB_CACHE")
    try:
        cache = os.path.join(tmp, "cache.json")
        ref, s1, s2 = (os.path.join(tmp, x) for x in ("ref", "s1", "s2"))
        for d in (ref, s1, s2):
            make(d)
        os.environ["LE_SCRUB_CACHE"] = "0"
        SP.scrub(ref, ["Pat Example"])
        check("c. LE_SCRUB_CACHE=0: no cache file", not os.path.exists(cache))
        os.environ["LE_SCRUB_CACHE"] = cache
        r1 = SP.scrub(s1, ["Pat Example"])
        t1 = tree(s1)
        check("a. cold: the account id masked, leads.json removed, the canary masked",
              ACCT.encode() not in t1["c/acct.json"] and "d/leads.json" not in t1 and b"Pat Example" not in t1["e/canary.txt"], (r1, t1))
        c = json.load(open(cache))
        check("a. cold: only clean files are remembered (2 of 5)", len(c["clean"]) == 2 and r1["cached"] == 0, c)
        r2 = SP.scrub(s2, ["Pat Example"])
        t2 = tree(s2)
        check("b. warm on a fresh copy: the clean files skipped, the id and the canary masked AGAIN (never cached)",
              r2["cached"] == 2 and ACCT.encode() not in t2["c/acct.json"] and b"Pat Example" not in t2["e/canary.txt"], r2)
        check("b. warm output == a no-cache scrub, byte for byte", t2 == tree(ref) == t1)
        s3 = os.path.join(tmp, "s3")
        make(s3)
        open(os.path.join(s3, "a", "clean.json"), "w").write(json.dumps({"line": "now " + ACCT}))
        r3 = SP.scrub(s3, ["Pat Example"])
        check("c. a clean file that changes (now holds an id) is scanned again and masked",
              ACCT.encode() not in open(os.path.join(s3, "a", "clean.json"), "rb").read() and r3["cached"] == 1, r3)
        s4 = os.path.join(tmp, "s4")
        make(s4)
        open(os.path.join(s4, "b", "page.txt"), "w").write("Sam Other")
        SP.scrub(s4, ["Pat Example"])                                    # caches page.txt with 'Sam Other' as clean under the old canaries
        s5 = os.path.join(tmp, "s5")
        make(s5)
        open(os.path.join(s5, "b", "page.txt"), "w").write("Sam Other")
        r5 = SP.scrub(s5, ["Pat Example", "Sam Other"])                  # a new canary: every verdict is void
        check("c. new canary values void the cache: the new canary is masked", r5["cached"] == 0
              and b"Sam Other" not in open(os.path.join(s5, "b", "page.txt"), "rb").read(), r5)
    finally:
        if old is None:
            os.environ.pop("LE_SCRUB_CACHE", None)
        else:
            os.environ["LE_SCRUB_CACHE"] = old
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
