"""MONEY ENGINE (tools/money_engine.py, 2026-11-10): runs the five money scanners, builds money/index.json. Paper only, stdlib, offline.

  a. the five contract fixtures in tools/money/fixtures/ follow the data contract; the sample is labelled "not real"
  b. the engine's own --selftest (fake scanners: ok, slow, crashing, bad json, missing; lock file; stale fallback) passes
  c. a run with no scanners present works from the fixtures; the index has a low <= base <= high ESTIMATE and never an error
  d. the schedule helpers: RUN_MONEY.bat (CRLF, every goto target exists) and .github/workflows/money-engine.yml (schedule + dispatch only, read-only token, no secrets)
  e. paper only: the engine and the workflow never import engine/, never read keys, never place orders
    python -X utf8 -m tests.test_money_engine
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from tests import agora_kit as AK  # noqa: E402
import money_engine as M  # noqa: E402

check = AK.check
ROOT = AK.ROOT
FX = os.path.join(ROOT, "tools", "money", "fixtures")


def test_fixtures():
    for sid in M.IDS:
        raw = json.load(open(os.path.join(FX, sid + ".json"), encoding="utf-8"))
        ok = (raw["v"] == 1 and raw["id"] == sid and raw["mode"] == "paper" and raw["status"] == "sample" and M.parse_iso(raw["asof"]) is not None
              and isinstance(raw["headline"]["text"], str) and raw["headline"]["text"] and M.num(raw["headline"]["usd_month"]) is not None
              and 1 <= len(raw["items"]) <= 8 and all(set(i) == {"title", "detail", "usd", "score", "risk"} and 0 <= i["score"] <= 100 and i["risk"] in M.RISKS for i in raw["items"])
              and any("not real" in n.lower() for n in raw["notes"]))
        check(f"a. fixture {sid}: v1, paper, sample, headline + $/month, 1-8 items with title/detail/usd/score/risk, a 'not real' note", ok, raw)
        n = M.normalize(sid, raw)
        check(f"a. fixture {sid} survives normalize() unchanged in meaning (same headline, same item count)", n and n["headline"]["text"] == raw["headline"]["text"] and len(n["items"]) == len(raw["items"]))


def test_selftest():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money_engine.py"), "--selftest"], capture_output=True, text=True, timeout=120)
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    check("b. money_engine.py --selftest passes (timeout, crash, bad json, missing scanner, lock, stale fallback)", r.returncode == 0 and "FAIL" not in r.stdout, (r.stdout[-500:], r.stderr[-300:]))
    check("b. the self-test counts its checks", re.match(r"\d+/\d+ passed", last) is not None, last)


def test_run():
    out = tempfile.mkdtemp(prefix="money-test-")
    empty = tempfile.mkdtemp(prefix="money-none-")
    idx = M.run(out, True, 5, scanners=empty, quiet=True)
    check("c. a run with no scanners at all still gives five streams in the fixed order", idx and [s["id"] for s in idx["streams"]] == list(M.IDS))
    t = idx["total"]
    check("c. the total is labelled ESTIMATE, low <= base <= high, paper mode, and states it is not income", idx["label"] == "ESTIMATE" and idx["mode"] == "paper" and t["low"] <= t["base"] <= t["high"] and "not income" in idx["note"].lower(), idx["note"])
    check("c. every stream: status sample, source fixture, a headline, a low / base / high, up to 3 items, an 'age' key", all(s["status"] == "sample" and s["source"] == "fixture" and s["headline"] and set(s["usd_month"]) == {"low", "base", "high"} and len(s["items"]) <= 3 and "age_min" in s for s in idx["streams"]))
    check("c. sample money is never counted as real: real_base is 0 when every stream is a sample", t["real_base"] == 0 and idx["counts"]["sample"] == 5)
    files = sorted(f for f in os.listdir(out) if f.endswith(".json"))
    check("c. the output folder holds <id>.json for each id plus index.json, and no lock file is left", files == sorted([i + ".json" for i in M.IDS] + ["index.json"]) and not os.path.exists(os.path.join(out, ".money_engine.lock")), files)
    one = M.run(out, True, 5, only=["sibyl"], scanners=empty, quiet=True)
    check("c. --only runs just the named streams", [s["id"] for s in one["streams"]] == ["sibyl"])
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money_engine.py"), "--fixture", "--quiet", "--out", out], capture_output=True, text=True, timeout=120)
    check("c. the command line works (--fixture --quiet) and exits 0", r.returncode == 0, r.stderr[-300:])
    ex = M.estimate("ok", 100), M.estimate("stale", 100), M.estimate("sample", 100), M.estimate("ok", None)
    check("c. the honest range: ok 30%-150%, stale 0-120%, sample 0-200%, no number -> none", ex == ((30.0, 100.0, 150.0), (0.0, 100.0, 120.0), (0.0, 100.0, 200.0), (None, None, None)), ex)
    bad = M.normalize("mercury", {"id": "mercury", "status": "ok", "asof": "garbage", "headline": {"text": "x", "usd_month": float("nan")}, "items": [None, {"title": ""}, {"title": "t", "score": "x", "risk": 5}]})
    check("c. junk input is cleaned, never raises: bad date -> stale, nan -> no number, bad items dropped / defaulted", bad and bad["status"] == "stale" and bad["headline"]["usd_month"] is None and len(bad["items"]) == 1 and bad["items"][0]["risk"] == "med" and bad["items"][0]["score"] == 0, bad)


def test_schedule():
    bat = open(os.path.join(ROOT, "RUN_MONEY.bat"), "rb").read()
    txt = bat.decode("ascii")
    check("d. RUN_MONEY.bat is ASCII with CRLF line endings only", b"\r\n" in bat and bat.count(b"\n") == bat.count(b"\r\n"))
    labels = {m.lower() for m in re.findall(r"^:(\w+)", txt, re.M)}
    gotos = {m.lower() for m in re.findall(r"goto :(\w+)", txt, re.I)}
    check("d. every goto target in RUN_MONEY.bat exists", gotos <= labels, gotos - labels)
    check("d. RUN_MONEY.bat runs the engine, shows the Task Scheduler line (every 30 minutes) and has an 'auto' mode without pause", "tools\\money_engine.py" in txt and "/MO 30" in txt and 'auto' in txt and "schtasks /Create" in txt)
    wf = open(os.path.join(ROOT, ".github", "workflows", "money-engine.yml"), encoding="utf-8").read()
    on = wf.split("jobs:")[0]
    check("d. the workflow runs only on schedule and by hand (no push / pull_request trigger)", "schedule:" in on and "workflow_dispatch:" in on and not re.search(r"^\s*(push|pull_request)\s*:", on, re.M), on)
    check("d. the workflow has a read-only token (contents: read), no secrets, no write permission, uploads the JSON as an artifact",
          "contents: read" in wf and "secrets." not in wf and "write" not in re.sub(r"#[^\n]*", "", wf) and "upload-artifact" in wf)
    check("d. the workflow self-tests, then runs the engine from the repo, with a job timeout", "money_engine.py --selftest" in wf and "money_engine.py --out" in wf and "timeout-minutes" in wf)
    ig = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("d. the generated money_out/ folder and the runner log are gitignored", "money_out/" in ig and "money_out_log.txt" in ig)


def test_paper_only():
    src = open(os.path.join(ROOT, "tools", "money_engine.py"), encoding="utf-8").read()
    code = re.sub(r'""".*?"""', "", src, flags=re.S)
    check("e. the engine never imports engine/ or the bot, never reads live_model*.json, keys or .env, never opens a network connection of its own",
          not re.search(r"^\s*(from|import)\s+engine\b|live_model|\.env|alerts\.json|urllib|requests|socket|http\.client|ninjatrader", code, re.M | re.I), re.findall(r"live_model|\.env|urllib|requests|socket", code))
    check("e. the engine says paper in its output (mode paper) and its docstring", '"mode": "paper"' in src and "PAPER ONLY" in src)


if __name__ == "__main__":
    test_fixtures()
    test_selftest()
    test_run()
    test_schedule()
    test_paper_only()
    AK.finish()
