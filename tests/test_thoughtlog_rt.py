"""red team #43 (day-thoughtlog 2026-11-27): the packed thoughts are ALWAYS scrubbed (emails / paths / generic account ids even when no
names are given); day files older than 45 days are pruned at a new day's first write.
    python -X utf8 -m tests.test_thoughtlog_rt
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def main():
    from engine import thoughtlog as T
    import datetime as dt
    now = int(dt.datetime(2026, 11, 27, 10, 0, tzinfo=T.ET).timestamp())
    with tempfile.TemporaryDirectory() as td:
        f, b = os.path.join(td, "th"), os.path.join(td, "brain")
        os.makedirs(f)
        os.makedirs(b)
        for d in ("2026-09-01", "2026-10-20", "2026-11-26"):
            open(os.path.join(f, f"{d}.jsonl"), "w").write('{"t":1,"bot":"of","text":"x"}\n')
        hb = {"second": {"strategies": {"sr": {"short": "S/R", "brain": {"log": [
            {"t": now - 60, "text": "mail me at someone@example.com, file C:\\Users\\someone\\Documents\\x.txt"}]}}}}}
        n = T.collect(hb, now=now, folder=f)
        check("collect wrote today's row", n == 1, n)
        left = sorted(os.listdir(f))
        check("files older than 45 days pruned at the day's first write, newer kept",
              "2026-09-01.jsonl" not in left and "2026-10-20.jsonl" in left and "2026-11-26.jsonl" in left, left)
        g = T.pack("2026-11-27", folder=f, brain_dir=b, names=())
        txt = gzip.decompress(g).decode() if g else ""
        check("no names given: the email and the path are still scrubbed", txt and "example.com" not in txt and "Users\\\\someone" not in txt
              and "someone@" not in txt, txt)
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
