"""COLOSSEUM extras (stdlib, offline, read only): the numbers the Archive index does not carry, for the duel rounds "max drawdown $" and "MFFU eval speed".

    python tools/colosseum_build.py            # writes tools/web_public/colosseum/extra.json
    python tools/colosseum_build.py --check    # exit 1 when the committed file is stale
    python tools/colosseum_build.py --selftest

Reads research/runs/<id>.json (spans "2026" and "2021-25") and writes
  {"v": 1, "built": "YYYY-MM-DD", "cols": ["dd", "dec10", "pass_med"], "runs": {"<id>": [m26 | 0, mold | 0]}}
where m = [max drawdown $ (negative), % of evals decided within 10 sessions, median sessions to pass]; a missing number is null, a missing period is 0.
Nothing is computed or guessed here: every number is copied as stored. It never trades and touches nothing but its own output file.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "research", "runs")
OUT = os.path.join(ROOT, "tools", "web_public", "colosseum", "extra.json")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,90}$")
COLS = ("dd", "dec10", "pass_med")


def _num(x, k):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or x in (float("inf"), float("-inf")):
        return None
    v = round(float(x), k)
    return int(v) if k == 0 or v == int(v) else v


def period(sp):
    """[dd, dec10, pass_med] of one period, or 0 when the run has no such period (same rule as the Archive: n must be there)."""
    if not isinstance(sp, dict) or not sp.get("n"):
        return 0
    row = [_num(sp.get("dd"), 0), _num(sp.get("dec10"), 1), _num(sp.get("pass_med"), 1)]
    return row if any(v is not None for v in row) else 0


def build(runs_dir=RUNS):
    rows, built = {}, ""
    for p in sorted(glob.glob(os.path.join(runs_dir, "*.json"))):
        name = os.path.basename(p)
        if name == "index.json":
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                r = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(r, dict) or not SAFE_ID.match(str(r.get("id") or "")) or str(r["id"]) + ".json" != name or not isinstance(r.get("spans"), dict):
            continue
        a, b = period(r["spans"].get("2026")), period(r["spans"].get("2021-25"))
        if a or b:
            rows[str(r["id"])] = [a, b]
        built = max(built, str(r.get("built") or "")[:10])
    return {"v": 1, "built": built, "cols": list(COLS), "runs": rows}


def dump(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=True) + "\n"


def selftest():
    import tempfile
    ok = []

    def t(name, cond):
        ok.append(bool(cond))
        print(("[PASS] " if cond else "[FAIL] ") + name)
    with tempfile.TemporaryDirectory() as d:
        def put(rid, spans, **kw):
            with open(os.path.join(d, rid + ".json"), "w", encoding="utf-8") as fh:
                json.dump({"id": rid, "built": "2026-10-01 10:00", "spans": spans, **kw}, fh)
        put("a", {"2026": {"n": 10, "dd": -1234.4, "dec10": 33.33, "pass_med": 15.0}, "2021-25": {"n": 0, "dd": -5}})
        put("b", {"2026": {"n": 5}, "2021-25": {"n": 7, "dd": -9, "dec10": None}})
        put("c", {"2026": {"n": 5, "dd": float("nan")}})
        with open(os.path.join(d, "bad.json"), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        o = build(d)
    t("numbers are copied as stored, rounded (dd whole dollars, the rest one decimal)", o["runs"]["a"][0] == [-1234, 33.3, 15])
    t("a period without trades is 0, never zeros", o["runs"]["a"][1] == 0)
    t("a missing number is null, never guessed", o["runs"]["b"] == [0, [-9, None, None]])
    t("a run with nothing to add, a broken file and index.json are left out", set(o["runs"]) == {"a", "b"})
    t("the output is stable (same input, same bytes)", dump(o) == dump(json.loads(dump(o))) and o["built"] == "2026-10-01")
    print("ALL PASS" if all(ok) else "SOME FAILED")
    return 0 if all(ok) else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    text = dump(build())
    if "--check" in sys.argv:
        try:
            with open(OUT, encoding="utf-8") as fh:
                same = fh.read() == text
        except OSError:
            same = False
        print("colosseum/extra.json is up to date" if same else "colosseum/extra.json is STALE: run python tools/colosseum_build.py")
        return 0 if same else 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {OUT} ({len(text) / 1024:.0f} KB, {len(json.loads(text)['runs'])} runs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
