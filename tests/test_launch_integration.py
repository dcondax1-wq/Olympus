"""Integration checks from the 2026-10-25 pre-launch bug hunt (research/handoff/2026-10-25/BUGHUNT.md).

  a. the cloud workflow's sparse checkout carries every repo file the cloud's published blocks read: Goals (news calendar,
     health band), Performance (range / exit / robustness / months / look-ahead), Trade intel, rejected setups. Before the
     fix these files were missing in GitHub Actions, so the phone's Goals news / month band, Performance and Trade intel
     pages were empty in the cloud build (found by auditing every file the cloud steps open vs the sparse patterns).
  b. the PC dashboard's news line reads the blackout epoch fields (blackout_start_t / blackout_end_t): the API's
     blackout_start / blackout_end are 'HH:MM' text, which threw "RangeError: Invalid time value" on every PC page as soon
     as a high-impact event was in the next 14 days.

    python -X utf8 -m tests.test_launch_integration
"""
from __future__ import annotations

import fnmatch
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" - {detail}" if detail and not cond else ""))


def sparse_patterns():
    wf = open(os.path.join(ROOT, ".github", "workflows", "cloud-monitor.yml"), encoding="utf-8").read()
    m = re.search(r"sparse-checkout: \|\n((?:\s{12}\S.*\n)+)", wf)
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()] if m else []


def covered(path, pats):
    p = "/" + path.replace(os.sep, "/")
    return any((x.endswith("/") and p.startswith(x)) or fnmatch.fnmatchcase(p, x) for x in pats)


def part_a():
    pats = sparse_patterns()
    from engine import goals, health_band, perf  # noqa: F401  (the readers below must still read these files)
    need = {
        "research/hq/news_calendar.csv": "engine/goals.py",
        "research/lab/health_band.json": "engine/health_band.py",
        "research/lab/lookahead_audit.json": "engine/perf.py",
        "research/lab/robust.json": "engine/perf.py",
        "research/lab/walkforward.json": "engine/perf.py",
        "research/lab/trade_intel.json": "engine/perf.py",
        "research/lab/rejections.json": "tools/build_web_dashboard.py",
        "research/lab/backtest_live.json": "tools/build_web_dashboard.py",
        "research/runs/lit_live.json": "tools/cloud_monitor.py",
        "live_model.json": "tools/cloud_monitor.py", "second_model.json": "engine/second.py",
    }
    for f, reader in need.items():
        name = os.path.basename(f)
        src = open(os.path.join(ROOT, reader), encoding="utf-8").read()
        stem = name.rsplit(".", 1)[0]
        check(f"a. {f}: read by {reader}, present in the repo, in the cloud sparse checkout",
              (name in src or stem in src) and os.path.exists(os.path.join(ROOT, f)) and covered(f, pats),
              f"in reader {name in src or stem in src}, exists {os.path.exists(os.path.join(ROOT, f))}, covered {covered(f, pats)}")


def part_b():
    js = open(os.path.join(ROOT, "web", "js", "dash", "ops.js"), encoding="utf-8").read()
    m = re.search(r"newsApi\.events\.map\(e => \(\{[^)]*\}\)\)", js)
    line = m.group(0) if m else ""
    check("b. PC news line maps blackout_start_t / blackout_end_t (epoch s), not the 'HH:MM' text fields",
          "blackout_start_t" in line and "blackout_end_t" in line and "bs: e.blackout_start," not in line, line[:160])
    from engine import calendar_week as cw
    src = open(cw.__file__, encoding="utf-8").read()
    check("b. engine/calendar_week still sends blackout_start as 'HH:MM' text (the reason the JS must use the *_t fields)",
          '"blackout_start": _hhmm(b0)' in src)


def part_c():
    """engine.launch_prep end to end on temp files (allowlist + 50K anchor + account B), twice: the second run keeps the
    25K's first session (was: moved to the next weekday, dropping the eval's earlier days from account B's book)."""
    import json
    import shutil
    import tempfile
    from engine import account_b, eval_life, launch_prep, ninjatrader, second
    tmp = tempfile.mkdtemp(prefix="le_lprep_")
    keep = (ninjatrader.ALLOW_PATH, second.CFG_PATH, eval_life.anchor_path, second._selftest_ok, launch_prep._next_session)
    try:
        ninjatrader.ALLOW_PATH = os.path.join(tmp, "nt_accounts_allow.json")
        second.CFG_PATH = os.path.join(tmp, "second_model.json")
        shutil.copy(os.path.join(ROOT, "second_model.json"), second.CFG_PATH)
        raw = json.load(open(second.CFG_PATH, encoding="utf-8"))
        raw["account_b"] = None
        json.dump(raw, open(second.CFG_PATH, "w", encoding="utf-8"), indent=1)
        eval_life.anchor_path = lambda state_path=None: os.path.join(tmp, "eval_anchor.json")
        second._selftest_ok = lambda timeout=600: (True, "PASS")
        launch_prep._next_session = lambda today=None: "2026-10-26"
        rc1 = launch_prep.main(["--atlas", "MFFU25K-TEST", "--lit", "MFFU50K-TEST"])
        ab1 = account_b.raw_cfg(second.CFG_PATH) or {}
        an = eval_life.load_anchor(None, path=os.path.join(tmp, "eval_anchor.json"))
        allow = json.load(open(ninjatrader.ALLOW_PATH, encoding="utf-8"))["accounts"]
        check("c. launch_prep: both accounts allowlisted, 50K anchor 49,710.80 / 48,168.20 as of 2026-10-23, ATLAS on the 25K from 10-26",
              rc1 == 0 and allow == ["MFFU50K-TEST", "MFFU25K-TEST"] and an and an["balance"] == 49710.8 and an["floor"] == 48168.2
              and ab1.get("account") == "MFFU25K-TEST" and ab1.get("eval_start") == "2026-10-26", (rc1, allow, an, ab1))
        launch_prep._next_session = lambda today=None: "2026-10-28"          # the owner re-runs it on Tuesday evening
        ap_ = os.path.join(tmp, "eval_anchor.json")
        eval_life.save_anchor({"balance": 50310.0, "floor": 48310.0, "as_of": "2026-10-27"}, path=ap_)   # a newer real anchor
        rc2 = launch_prep.main(["--atlas", "MFFU25K-TEST", "--lit", "MFFU50K-TEST"])
        ab2 = account_b.raw_cfg(second.CFG_PATH) or {}
        an2 = eval_life.load_anchor(None, path=ap_)
        check("c. launch_prep run again later: the 25K keeps its first session (2026-10-26), the newer 50K anchor (10-27) is "
              "kept, the allowlist is not duplicated",
              rc2 == 0 and ab2.get("eval_start") == "2026-10-26" and an2 and an2["as_of"] == "2026-10-27" and an2["balance"] == 50310.0
              and sorted(json.load(open(ninjatrader.ALLOW_PATH, encoding="utf-8"))["accounts"]) == ["MFFU25K-TEST", "MFFU50K-TEST"], (ab2, an2))
        rc2b = launch_prep.main(["--atlas", "MFFU25K-TEST", "--lit", "MFFU50K-TEST", "--balance", "50100", "--floor", "48300",
                                 "--as-of", "2026-10-28"])
        an3 = eval_life.load_anchor(None, path=ap_)
        check("c. explicit --balance --floor --as-of replace the anchor", rc2b == 0 and an3 and an3["as_of"] == "2026-10-28"
              and an3["balance"] == 50100.0, an3)
        rc3 = launch_prep.main(["--atlas", "MFFU25K-TEST", "--lit", "MFFU50K-TEST", "--atlas-start", "2026-11-02"])
        check("c. --atlas-start still sets a new first session (a new 25K eval)",
              rc3 == 0 and (account_b.raw_cfg(second.CFG_PATH) or {}).get("eval_start") == "2026-11-02")
        check("c. the same account for both is refused", launch_prep.main(["--atlas", "MFFU50K-TEST", "--lit", "MFFU50K-TEST"]) == 1)
    finally:
        ninjatrader.ALLOW_PATH, second.CFG_PATH, eval_life.anchor_path, second._selftest_ok, launch_prep._next_session = keep
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    part_a()
    part_b()
    part_c()
    print(f"launch integration: {sum(RES)}/{len(RES)} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
