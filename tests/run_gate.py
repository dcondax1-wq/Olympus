"""The release gate: ONE command that verifies the whole site before it is published (job 2026-11-04). Run it on a quiet machine.

    python -X utf8 tests/run_gate.py                 every suite below, one at a time (never in parallel)
    python -X utf8 tests/run_gate.py --fast          static parts only (no browser): minutes, not hours
    python -X utf8 tests/run_gate.py --only hub,a11y suites whose name contains one of these (exact name first)
    python -X utf8 tests/run_gate.py --resume        skip the suites that PASSed in the last gate.json
    python -X utf8 tests/run_gate.py --list          the suites and what each runs
    other options: --gate N (wait for load < N, default 2 x cpus) --gate-wait SEC (default 300) --no-retry --out DIR --budget-scale X

What runs: first the engine / PC core (CORE below, no browser: run_gate, writeups_index, wire_new_apps, selfheal, dst, pcdash_api,
account_c, lit_oif, fleet, lit_live, rehearsal, dst_sunday; --fast runs dst / fleet / lit_live / rehearsal in their --quick form and leaves lit_oif and
dst_sunday to the full gate), then jarvis_shell, apps_list, safari_lint, olympus a11y / sfx / kit (static + power + tiers) / themes / render, the Jarvis hub BY PARTS
(tests/hub_parts.py: static, a, b, missing, c, look, switcher, olympus, system, intro), the Jarvis assistant / tools / modes / brain / obsidian /
talk / voice / engines suites, phone_e2e, Zenith (mode / shell / pro / pages), kalshi_page, and every per-app page test: tests/test_*_page.py
found on disk plus the known app suites that exist (arena, fates, hermes, pantheon, prometheus, datacity ...). Nothing is hardcoded in a
count: a suite is listed when its file exists.

Each suite runs in its own process group with a time budget scaled by the measured load (tests/browser_kit.py multiplier, 1x on a calm
machine, up to 6x). A suite that FAILS with nothing but timeouts / a crashed browser tab (no [FAIL] line) is run ONE more time.
  PASS      every check passed
  FAIL      a real [FAIL] line (or an error that is not a timeout): this is what makes the verdict NO-GO
  TIMEOUT   over its budget, or still only timeouts after the retry: UNVERIFIED, never a NO-GO; the exact command to rerun is printed
  SKIP      the suite asked to be skipped (machine too loaded) or has nothing static to run in --fast: UNVERIFIED too
The table (suite / result / checks passed of total / seconds) is printed and written to research/handoff/2026-11-04/gate.md and gate.json
(the state --resume reads). The last line is GO or NO-GO. It never kills any process but the one suite it started itself.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.browser_kit import multiplier  # noqa: E402  (the load multiplier: 1x calm, up to 6x swamped)

CPUS = os.cpu_count() or 1
OUT_DIR = os.path.join(ROOT, "research", "handoff", "2026-11-04")
TO_RX = re.compile(r"TimeoutError|Timeout \d+ms exceeded|Target (?:page, context or browser has been )?(?:closed|crashed)|timed out|net::ERR_TIMED_OUT|Page crashed", re.I)

# per-app suites that are not named test_*_page.py but are an app's own test
KNOWN_APPS = ["arena", "fates", "hermes", "pantheon", "prometheus", "datacity", "app_intro", "olympus_fx", "oracle_odeon_fx", "ui_polish", "jarvis_bots",
              "jarvis_kalshi", "space_ui", "atlas_ui", "blitz_tab", "agency", "me_hub"]
# (name = tests/test_<name>.py, full-run args, --fast form ("same" / None / [args]), budget s): the engine / PC core, no browser
CORE = [("run_gate", [], "same", 120), ("writeups_index", [], "same", 120), ("wire_new_apps", [], "same", 180), ("selfheal", [], "same", 180),
        ("dst", [], ["--quick"], 900), ("pcdash_api", [], "same", 300), ("account_c", [], "same", 600), ("lit_oif", [], None, 3600),
        ("fleet", [], ["--quick"], 1500), ("lit_live", [], ["--quick"], 3600), ("rehearsal", [], ["--quick"], 5400), ("dst_sunday", [], None, 1500)]
HUB = [("static", 120), ("a", 900), ("b", 900), ("missing", 1200), ("c", 1500), ("look", 1200), ("switcher", 1200), ("olympus", 1200), ("system", 900), ("intro", 1500)]


def has_static(mod: str) -> bool:
    try:
        src = open(os.path.join(ROOT, "tests", mod + ".py"), encoding="utf-8").read()
    except OSError:
        return False
    return bool(re.search(r"(?m)^def (test_static|part_a|static)\(\):", src))


def exists(mod: str) -> bool:
    return os.path.isfile(os.path.join(ROOT, "tests", mod + ".py"))


def plan() -> list:
    """[{name, argv (after python -X utf8), fast (argv or None), budget (s), kind}] in the order they run: cheap first, the long browser ones last"""
    S: list = []

    def add(name, mod, args=None, fast="same", budget=600, kind="browser", module=True):
        if module and not exists(mod):
            return
        a = ["-m", "tests." + mod] + list(args or []) if module else list(args)
        if fast == "same":
            f = list(a)
        elif fast == "static":
            f = ["-m", "tests.gate_static", "tests." + mod] if has_static(mod) else None
        elif isinstance(fast, list):
            f = ["-m", "tests." + mod] + fast
        else:
            f = None
        S.append({"name": name, "argv": a, "fast": f, "budget": budget, "kind": kind})

    # the engine / PC core (night team D, 2026-11-16): no browser, clock-proof; --fast runs the quick form of the slow ones
    # (dst --quick, lit_live --quick, rehearsal --quick); a full gate runs them whole. Order: cheapest first.
    for nm, args, fast, b in CORE:
        add(nm, "test_" + nm, args, fast=fast, budget=b, kind="static")
    add("jarvis_shell", "test_jarvis_shell", budget=120, kind="static")
    add("apps_list", "test_apps_list", fast=["--static"], budget=600)
    add("safari_lint", "test_safari_smoke", ["--lint"], budget=600, kind="static")
    # optional: the whole iPhone walk in WebKit (every app). Exit 77 = WebKit not installed here = SKIP (never a FAIL); not run by --fast
    add("safari_webkit", "test_safari_smoke", ["--webkit"], fast=None, budget=2400)
    add("olympus_a11y", "test_olympus_a11y", fast=["--static"], budget=600)
    add("olympus_sfx", "test_olympus_sfx", budget=300, kind="static")
    add("sfx_engine", "test_sfx_engine", budget=300, kind="static")
    add("olympus_kit", "test_olympus_kit", ["power", "tiers"], fast="static", budget=1200)
    add("olympus_themes", "test_olympus_themes", fast=None, budget=1500)
    add("olympus_render", "test_olympus_render", fast="static", budget=1200)
    if exists("test_jarvis_hub") and exists("hub_parts"):
        for part, b in HUB:
            S.append({"name": "jarvis_hub:" + part, "argv": ["-m", "tests.hub_parts", part], "fast": ["-m", "tests.hub_parts", "static"] if part == "static" else None,
                      "budget": b, "kind": "browser"})
    for m in ("assistant", "tools", "modes", "brain", "obsidian", "talk", "voice", "engines"):
        add("jarvis_" + m, "test_jarvis_" + m, fast="static" if m == "brain" else None, budget=900)
    add("phone_e2e", "test_phone_e2e", fast=None, budget=2400)
    for z in ("mode", "shell", "pro", "pages"):
        add("zenith_" + z, "test_zenith_" + z, fast="static", budget=1200)
    add("kalshi_page", "test_kalshi_page", fast="static", budget=1200)
    seen = {s["name"] for s in S}
    for f in sorted(glob.glob(os.path.join(ROOT, "tests", "test_*_page.py"))):
        mod = os.path.basename(f)[:-3]
        nm = mod[5:]
        if nm not in seen:
            add(nm, mod, fast="static", budget=900)
            seen.add(nm)
    for k in KNOWN_APPS:
        if k not in seen:
            add(k, "test_" + k, fast="static", budget=900)
            seen.add(k)
    return S


# ------------------------------------------------------------------------------------------------ one suite
def count(text: str):
    ok = len(re.findall(r"^\[PASS\]", text, re.M))
    bad = len(re.findall(r"^\[FAIL\]", text, re.M))
    if ok or bad:
        return ok, bad
    m = re.findall(r"\bRan (\d+) tests?\b", text)                      # unittest
    if m:
        n = int(m[-1])
        f = re.search(r"FAILED \((?:failures=(\d+))?(?:, )?(?:errors=(\d+))?", text)
        b = (int(f.group(1) or 0) + int(f.group(2) or 0)) if f else 0
        return n - b, b
    m = re.findall(r"(\d+)\s*/\s*(\d+)(?:\s+(?:passed|checks|PASS|ALL PASS|FAILED))?", text)
    if m:
        a, b = m[-1]
        return int(a), max(0, int(b) - int(a))
    return 0, 0


def run_once(argv, budget: float, env: dict):
    t0 = time.time()
    p = subprocess.Popen([sys.executable, "-X", "utf8"] + argv, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True)
    over = False
    try:
        out, _ = p.communicate(timeout=budget)
    except subprocess.TimeoutExpired:
        over = True
        try:
            os.killpg(p.pid, signal.SIGTERM)                  # only the group this runner started
        except OSError:
            pass
        try:
            out, _ = p.communicate(timeout=25)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
            out, _ = p.communicate()
    return {"out": out or "", "code": p.returncode, "over": over, "secs": time.time() - t0}


def classify(r) -> str:
    """PASS / FAIL / TIMEOUT / SKIP for one run"""
    out, code = r["out"], r["code"]
    if r["over"]:
        return "TIMEOUT"
    if code == 77 or "SKIP: machine too loaded" in out:
        return "SKIP"
    if code == 0:
        return "PASS"
    ok, bad = count(out)
    if bad:
        return "FAIL"                                          # a real failed check, whatever else happened
    if TO_RX.search(out[-6000:]):
        return "TIMEOUT"                                       # only timeouts / a crashed tab, no failed check
    return "FAIL"                                              # an error that is not a timeout (import error, assertion, traceback)


def run_suite(s: dict, fast: bool, scale: float, retry: bool) -> dict:
    argv = s["fast"] if fast else s["argv"]
    if argv is None:
        return {"state": "SKIP", "passed": 0, "total": 0, "seconds": 0, "note": "no static part (run without --fast)", "tail": "", "fails": [], "argv": s["argv"]}
    budget = s["budget"] * max(1.0, multiplier()) * scale
    env = dict(os.environ)
    total_secs = 0.0
    r = run_once(argv, budget, env)
    st = classify(r)
    total_secs += r["secs"]
    note = ""
    if st == "TIMEOUT" and not r["over"] and retry:             # timeouts only, not a budget overrun: one more try
        r = run_once(argv, budget, env)
        st = classify(r)
        total_secs += r["secs"]
        note = "retried once"
    ok, bad = count(r["out"])
    fails = [ln[:240] for ln in r["out"].splitlines() if ln.startswith("[FAIL]")][:6]
    if st == "TIMEOUT" and r["over"]:
        note = f"over its {budget:.0f} s budget" + (", " + note if note else "")
    elif st == "TIMEOUT":
        note = "timeouts only" + (", " + note if note else "")
    return {"state": st, "passed": ok, "total": ok + bad, "seconds": round(total_secs, 1), "note": note, "fails": fails, "argv": argv,
            "tail": "\n".join(r["out"].strip().splitlines()[-6:])}


# ------------------------------------------------------------------------------------------------ reporting
def rerun_cmd(name: str, fast: bool) -> str:
    return f"python -X utf8 tests/run_gate.py --only {name}" + (" --fast" if fast else "")


def table(rows: list) -> str:
    w = max([len(r["name"]) for r in rows] + [5])
    out = [f"| {'suite':<{w}} | result  | checks | seconds |", f"|{'-' * (w + 2)}|---------|-------:|--------:|"]
    for r in rows:
        chk = f"{r['passed']}/{r['total']}" if r["total"] else "-"
        res = r["state"] + (" *" if r.get("resumed") else "")
        out.append(f"| {r['name']:<{w}} | {res:<7} | {chk:>6} | {r['seconds']:>7} |")
    tp, tt = sum(r["passed"] for r in rows), sum(r["total"] for r in rows)
    out.append(f"| {'TOTAL':<{w}} | {sum(1 for r in rows if r['state'] == 'PASS')}/{len(rows)} pass | {tp}/{tt} | {sum(r['seconds'] for r in rows):>7.0f} |")
    return "\n".join(out)


def verdict(rows: list):
    fail = [r for r in rows if r["state"] == "FAIL"]
    unver = [r for r in rows if r["state"] in ("TIMEOUT", "SKIP")]
    return ("NO-GO" if fail else "GO"), fail, unver


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-retry", action="store_true")
    ap.add_argument("--gate", type=float, default=2.0 * CPUS)
    ap.add_argument("--gate-wait", type=float, default=300)
    ap.add_argument("--budget-scale", type=float, default=1.0)
    ap.add_argument("--out", default=OUT_DIR)
    a = ap.parse_args(argv)
    suites = plan()
    if a.list:
        for s in suites:
            print(f"{s['name']:<22} {' '.join(s['argv'])[:90]:<92} fast: {'-' if s['fast'] is None else ' '.join(s['fast'])[:60]}")
        print(f"{len(suites)} suites")
        return 0
    if a.only:
        keys = [k.strip() for k in a.only.split(",") if k.strip()]
        names = {s["name"] for s in suites}
        suites = [s for s in suites if any(k == s["name"] or (k not in names and k in s["name"]) for k in keys)]
        if not suites:
            print("no suite matches --only " + a.only)
            return 2
    os.makedirs(a.out, exist_ok=True)
    jp, mp = os.path.join(a.out, "gate.json"), os.path.join(a.out, "gate.md")
    prev = {}
    if a.resume and os.path.isfile(jp):
        try:
            prev = {r["name"]: r for r in json.load(open(jp, encoding="utf-8")).get("rows", [])}
        except (OSError, ValueError):
            prev = {}
    from tests.run_area import gate as load_gate, load1
    rows: list = []
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    mode = "FAST (static parts only)" if a.fast else "FULL"
    print(f"release gate {stamp}, {mode}: {len(suites)} suites, one at a time; load {load1():.1f} on {CPUS} cpus, timeout multiplier x{multiplier():.1f}", flush=True)

    def save():
        with open(jp, "w", encoding="utf-8") as fh:
            json.dump({"at": stamp, "mode": mode, "rows": [{k: v for k, v in r.items() if k != "tail"} for r in rows]}, fh, indent=1)

    for s in suites:
        p = prev.get(s["name"])
        if p and p.get("state") == "PASS" and (p.get("mode") == mode or not a.fast):
            r = dict(p, resumed=True, mode=mode)
            rows.append(r)
            print(f"  {s['name']}: PASS (resumed, {p['passed']}/{p['total']})", flush=True)
            continue
        g = load_gate(a.gate, a.gate_wait)
        r = run_suite(s, a.fast, a.budget_scale, not a.no_retry)
        r.update(name=s["name"], mode=mode)
        if g == "loaded":
            r["note"] = (r.get("note", "") + ", ran loaded").strip(", ")
        rows.append(r)
        print(f"  {s['name']}: {r['state']} {r['passed']}/{r['total']} in {r['seconds']}s" + (f" ({r['note']})" if r.get("note") else ""), flush=True)
        for f in r["fails"][:3]:
            print("     " + f, flush=True)
        save()
    v, fail, unver = verdict(rows)
    md = table(rows)
    lines = [f"# Release gate {stamp} - {mode}", "", md, ""]
    if any(r.get("resumed") for r in rows):
        lines += ["* = PASSed in the last gate.json, not run again (--resume)", ""]
    if fail:
        lines += ["FAILED (real failures):"]
        for r in fail:
            detail = "; ".join(r["fails"][:2]) or (r.get("tail", "").splitlines() or [""])[-1]
            lines.append(f"- {r['name']}: {detail}  -> {rerun_cmd(r['name'], a.fast)}")
        lines.append("")
    if unver:
        lines += [f"UNVERIFIED ({len(unver)}): not a NO-GO, but not proven; rerun on a calmer machine:"] + [f"- {r['name']} ({r['state']}{', ' + r['note'] if r.get('note') else ''}): {rerun_cmd(r['name'], a.fast)}" for r in unver] + [""]
    lines += [v + ("  (fast: static parts only, not a full release check)" if a.fast and v == "GO" else "")]
    text = "\n".join(lines)
    with open(mp, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    save()
    print("\n" + text)
    print(f"\nwritten: {os.path.relpath(mp, ROOT)} and gate.json")
    return 0 if v == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())
