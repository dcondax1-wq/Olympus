"""tools/import_1m_dryrun.py: the self-test round trip is READY, a shifted (back-adjusted) export is refused, data/ untouched.

  python -X utf8 -m tests.test_import_1m_dryrun
"""
from __future__ import annotations

import glob
import os
import sys
import tempfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import import_1m_dryrun as D  # noqa: E402

R = []


def check(name, ok, info=""):
    R.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' - ' + str(info) if info else ''}")


def main():
    files = [os.path.join(D.DATA, f) for f in ("NQ_1m.csv", "NQ_5m.csv", "NQ_15m.csv", "NQ_1h.csv")]
    before = {f: (os.path.getmtime(f), os.path.getsize(f)) for f in files}
    rep = D.run()
    lv = {i["what"]: i["level"] for i in rep["items"]}
    check("self-test: no FIX item", all(v != D.BAD for v in lv.values()), lv)
    check("self-test: round trip identical", lv.get("round trip") == D.OK)
    check("self-test: every day on 1m", rep.get("days", {}).get("on_1m") == rep.get("days", {}).get("n"), rep.get("days"))
    ch = sorted(glob.glob(os.path.join(D.DATA, "tv_exports", "NQ1_1m_chunk_2026-02-09.csv")))
    if ch:
        d = pd.read_csv(ch[0])
        for c in ("open", "high", "low", "close"):
            d[c] = d[c] + 300.0                          # a back-adjusted / other-contract export
        p = os.path.join(tempfile.mkdtemp(prefix="le_1m_t_"), "shifted.csv")
        d.to_csv(p, index=False)
        r2 = D.run([p])
        check("shifted export refused at the price-space check", any(i["what"] == "price space" and i["level"] == D.BAD for i in r2["items"]),
              next((i["text"][:90] for i in r2["items"] if i["what"] == "price space"), ""))
    check("data/ untouched", all((os.path.getmtime(f), os.path.getsize(f)) == before[f] for f in files))
    print(f"import_1m_dryrun: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
