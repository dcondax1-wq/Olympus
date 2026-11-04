"""tests/run_gate.py (the release gate): how it decides PASS / FAIL / TIMEOUT / SKIP, counts checks, builds the suite list from what exists on disk,
retries a timeout-only failure once, never lets a TIMEOUT make a NO-GO, and --resume / --only / --fast. Fake suites are tiny `python -c` programs; no browser.
    python -X utf8 -m tests.test_run_gate
"""
from __future__ import annotations

import glob
import json
import os
import sys
import tempfile
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import run_gate as G  # noqa: E402

RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def fake(code, budget=60):
    return {"name": "fake", "argv": ["-c", code], "fast": None, "budget": budget, "kind": "browser"}


def main():
    S = G.plan()
    names = [s["name"] for s in S]
    pages = [os.path.basename(f)[5:-3] for f in glob.glob(os.path.join(ROOT, "tests", "test_*_page.py"))]
    check("the suite list is built from the files on disk: every tests/test_*_page.py is in it, no name twice, nothing for a file that does not exist",
          all(p in names for p in pages) and len(names) == len(set(names)) and all(os.path.isfile(os.path.join(ROOT, "tests", a[1][6:] + ".py")) for s in S for a in [s["argv"]] if a[0] == "-m" and a[1].startswith("tests.") and a[1] != "tests.hub_parts"), [p for p in pages if p not in names])
    need = ["jarvis_shell", "apps_list", "safari_lint", "olympus_a11y", "olympus_sfx", "olympus_kit", "olympus_themes", "olympus_render", "jarvis_assistant", "jarvis_tools", "jarvis_modes",
            "jarvis_brain", "jarvis_obsidian", "jarvis_talk", "jarvis_voice", "jarvis_engines", "phone_e2e", "zenith_mode", "zenith_shell", "zenith_pro", "zenith_pages", "kalshi_page"]
    check("the named suites are all there (those whose files exist)", all(n in names for n in need if os.path.isfile(os.path.join(ROOT, "tests", "test_" + {"safari_lint": "safari_smoke"}.get(n, n) + ".py"))), [n for n in need if n not in names])
    hub = [n for n in names if n.startswith("jarvis_hub:")]
    check("the Jarvis hub runs BY PARTS (static, a, b, missing, c, look, switcher, olympus, system, intro), each its own suite with its own budget",
          [h.split(":")[1] for h in hub] == [p for p, _ in G.HUB] and all(s["budget"] > 0 for s in S), hub)
    check("--fast has a static command for the suites that have one and none (SKIP) for the rest; the kit runs static + power + tiers in a full run",
          all(s["fast"] is None or s["fast"][0] == "-m" for s in S) and next(s for s in S if s["name"] == "olympus_kit")["argv"][-2:] == ["power", "tiers"])
    check("count(): [PASS] / [FAIL] lines, a unittest 'Ran n tests' + FAILED, and an 'n/m' summary", G.count("[PASS] a\n[PASS] b\n[FAIL] c\n") == (2, 1)
          and G.count("Ran 12 tests in 0.5s\n\nOK\n") == (12, 0) and G.count("Ran 12 tests in 0.5s\n\nFAILED (failures=2, errors=1)\n") == (9, 3) and G.count("jarvis x: 7/9 FAILED") == (7, 2))

    r = G.run_suite(fake("print('[PASS] one'); print('[PASS] two'); print('all 2/2 PASS')"), False, 1.0, True)
    check("a passing suite: PASS, 2/2 checks", r["state"] == "PASS" and (r["passed"], r["total"]) == (2, 2), r)
    r = G.run_suite(fake("print('[PASS] one'); print('[FAIL] two  -> why'); import sys; sys.exit(1)"), False, 1.0, True)
    check("a failed check is a real FAIL (1/2), not retried, with its line kept", r["state"] == "FAIL" and (r["passed"], r["total"]) == (1, 2) and r["fails"] and "retried" not in r["note"], r)
    r = G.run_suite(fake("raise ImportError('no module named x')"), False, 1.0, True)
    check("an error that is not a timeout (a traceback, an import error) is a FAIL too", r["state"] == "FAIL", r)
    r = G.run_suite(fake("print('[PASS] one'); raise SystemExit('playwright._impl._errors.TimeoutError: Page.click: Timeout 30000ms exceeded.')"), False, 1.0, True)
    check("only a Playwright timeout (no failed check): retried ONCE, still timing out = TIMEOUT (unverified), 'retried once' in the note", r["state"] == "TIMEOUT" and "retried once" in r["note"], r)
    with tempfile.TemporaryDirectory() as d:
        flag = os.path.join(d, "flag")
        code = (f"import os,sys\nif not os.path.exists({flag!r}):\n    open({flag!r},'w').write('1'); print('[PASS] a'); sys.exit('Target crashed')\nprint('[PASS] a'); print('[PASS] b')")
        r = G.run_suite(fake(code), False, 1.0, True)
        check("a timeout-only failure that passes on the retry is PASS (2/2)", r["state"] == "PASS" and r["passed"] == 2, r)
    r = G.run_suite(dict(fake("import time; print('[PASS] a', flush=True); time.sleep(30)"), budget=1), False, 0.5, True)
    check("a suite over its time budget is stopped (its own process group) and is TIMEOUT, not retried", r["state"] == "TIMEOUT" and "budget" in r["note"] and r["seconds"] < 25, r)
    r = G.run_suite(fake("print('SKIP: machine too loaded'); import sys; sys.exit(77)"), False, 1.0, True)
    check("exit 77 'machine too loaded' is SKIP (unverified)", r["state"] == "SKIP", r)
    r = G.run_suite({"name": "x", "argv": ["-c", "pass"], "fast": None, "budget": 5, "kind": "browser"}, True, 1.0, True)
    check("--fast on a suite without a static part is SKIP, not a pass", r["state"] == "SKIP" and "static" in r["note"], r)

    rows = [{"name": "a", "state": "PASS", "passed": 3, "total": 3, "seconds": 1}, {"name": "b", "state": "TIMEOUT", "passed": 1, "total": 1, "seconds": 9, "note": "x"}]
    v, fail, unver = G.verdict(rows)
    check("TIMEOUT makes UNVERIFIED, never NO-GO; one real FAIL makes NO-GO", v == "GO" and not fail and len(unver) == 1 and G.verdict(rows + [{"name": "c", "state": "FAIL", "passed": 0, "total": 1, "seconds": 1}])[0] == "NO-GO")
    check("the rerun command is exact", G.rerun_cmd("jarvis_hub:c", False) == "python -X utf8 tests/run_gate.py --only jarvis_hub:c")

    out = tempfile.mkdtemp(prefix="gate_t_")
    try:
        rc = G.main(["--fast", "--gate", "0", "--only", "jarvis_shell,apps_list", "--out", out])
        j = json.load(open(os.path.join(out, "gate.json"), encoding="utf-8"))
        md = open(os.path.join(out, "gate.md"), encoding="utf-8").read()
        check("--fast --only: two suites run, the table + a final GO line are written (gate.md / gate.json)", rc == 0 and [r["name"] for r in j["rows"]] == ["jarvis_shell", "apps_list"] and "| suite" in md and md.rstrip().endswith("not a full release check)"), md[-300:])
        rc = G.main(["--fast", "--gate", "0", "--only", "jarvis_shell,apps_list", "--resume", "--out", out])
        j2 = json.load(open(os.path.join(out, "gate.json"), encoding="utf-8"))
        check("--resume: suites that PASSed in the last gate.json are not run again (marked resumed)", rc == 0 and all(r.get("resumed") for r in j2["rows"]), j2["rows"])
        check("--only with a name nothing matches: exit 2, nothing run", G.main(["--only", "nope_nothing", "--out", out]) == 2)
    finally:
        shutil.rmtree(out, ignore_errors=True)
    n = sum(RES)
    print(f"\nrun_gate: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
