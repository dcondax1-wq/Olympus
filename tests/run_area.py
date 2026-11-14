"""Run the right test suites for one area, one at a time (job 23, 2026-11-04).

    python tests/run_area.py jarvis|olympus|zenith|kalshi|cities|nq|pc|all [options]
    python tests/run_area.py --list                    the areas and their suites
    python tests/run_area.py jarvis --only hub,home    only suites whose name contains one of these
    options: --budget SEC      per-suite time budget (default 900; the slow browser suites get 3x); over it the suite's OWN process group
                               is stopped and the row says TIMEOUT
             --gate N          wait until the 1-minute load average is below N before each suite (default 2 x cpus; 0 = no gate)
             --gate-wait SEC   the longest wait at the gate (default 300): then it runs anyway and the row says "ran loaded",
                               or with --strict it is skipped ("machine too loaded")
             --fast            BK_FAST=1: browser suites open contexts at scale 1 with reduced motion (tests/browser_kit.py)
             --skip-load R     a browser suite exits with a SKIP when load per cpu is above R (BK_MAX_LOAD)
Writes scratch/results/<area>-<time>.json and .md (a table: suite, passed, failed, seconds, state) and prints it.
Safe next to other agents: it runs ONE suite at a time, never lists or signals any process but its own child, and the child
inherits no secrets beyond the environment it already had.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPUS = os.cpu_count() or 1

# the area map (CLAUDE_REFERENCE "One chat": the tests to run per thing); fast and node-only suites first, the slow browser ones last
AREAS = {
    "jarvis": ["jarvis_system", "jarvis_assistant", "jarvis_obsidian", "jarvis_modes", "jarvis_brain", "jarvis_tools", "jarvis_apps", "jarvis_core",
               "jarvis_voice", "jarvis_talk", "jarvis_bots", "jarvis_engines", "jarvis_transitions", "jarvis_home", "jarvis_hub", "phone_e2e"],
    "olympus": ["olympus_sfx", "sfx_engine", "sfx_lab", "olympus_fx", "olympus_kit", "olympus_render", "olympus_themes", "app_intro", "oracle_page", "odeon_page", "fates", "arena",
                "argus_page", "ares_page", "athena_page", "chronos_page", "forum_page", "hephaestus_page", "hermes", "labyrinth_page", "nemesis_page",
                "plutus_page", "prometheus", "tyche_page", "pantheon", "mind_page", "datacity"],
    "zenith": ["zenith_shell", "zenith_pages", "zenith_pro", "zenith_mode", "atlas_ui", "blitz_tab", "planner_addons", "ui_polish", "phone_e2e"],
    "kalshi": ["kalshi_edges", "kalshi_research", "kalshi_publish", "kalshi_guard", "kalshi_vm_update", "kalshi_page", "kalshicity_page"],
    "cities": ["cities_page", "kalshicity_page", "datacity"],
    "nq": ["lit_live", "no_yahoo", "risk_invariants", "mffu_rules", "guards", "sizing_caps", "second", "eval_lifecycle", "live_board", "live_publish", "heartbeat",
           "lit_scale_in", "lit_learn"],
    "pc": ["autoupdate_source", "autorun", "bots_back", "setup_everything", "calendar_sync", "live_link", "roll_now", "pc_guard", "launch_kit", "second_backup", "clean_pc", "clean_storage", "lite", "win_scripts", "fresh_start", "pc_health", "pc_selftest", "pc_silent", "pc_command_center", "one_time_setup"],
    "agency": ["agency_billing"],
    "money": ["money_machines"],
}
SLOW = {"jarvis_hub", "phone_e2e", "olympus_kit", "olympus_themes", "olympus_render", "zenith_mode", "ui_polish", "datacity", "jarvis_home"}


def suites_for(area: str) -> list:
    names = []
    for a in (AREAS if area == "all" else [area]):
        for n in AREAS[a]:
            if n not in names:
                names.append(n)
    out = [n for n in names if os.path.isfile(os.path.join(ROOT, "tests", f"test_{n}.py"))]
    if area == "all":
        out.sort(key=lambda n: (n in SLOW,))                     # stable: the fast ones first, the slow browser ones last
    return out


def load1() -> float:
    try:
        return os.getloadavg()[0]
    except OSError:
        return 0.0


def gate(limit: float, wait: float) -> str:
    """'' = went through calm, 'loaded' = waited the whole time and goes on, 'wait Ns' = waited then calm"""
    if limit <= 0 or load1() < limit:
        return ""
    t0 = time.time()
    while time.time() - t0 < wait:
        time.sleep(5)
        if load1() < limit:
            return f"waited {time.time() - t0:.0f}s"
    return "loaded"


def count(text: str):
    ok = len(re.findall(r"^\[PASS\]", text, re.M))
    bad = len(re.findall(r"^\[FAIL\]", text, re.M))
    if not ok and not bad:                                         # another style of report: "NN passed", "NN/MM", "ALL PASS"
        m = re.findall(r"(\d+)\s*/\s*(\d+)(?:\s+(?:passed|checks|PASS|ALL PASS))?", text)
        if m:
            a, b = m[-1]
            ok, bad = int(a), max(0, int(b) - int(a))
        else:
            m = re.findall(r"(\d+) passed(?:, (\d+) failed)?", text)
            if m:
                ok, bad = int(m[-1][0]), int(m[-1][1] or 0)
    return ok, bad


def run_one(name: str, budget: float, env: dict) -> dict:
    t0 = time.time()
    p = subprocess.Popen([sys.executable, "-X", "utf8", "-m", f"tests.test_{name}"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors="replace", start_new_session=True)
    state = ""
    try:
        out, _ = p.communicate(timeout=budget)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGTERM)                       # only the group this runner started
        except OSError:
            pass
        try:
            out, _ = p.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
            out, _ = p.communicate()
        state = "TIMEOUT"
    secs = time.time() - t0
    ok, bad = count(out or "")
    if not state:
        if p.returncode == 77 or "SKIP: machine too loaded" in (out or ""):
            state = "SKIP (machine too loaded)"
        elif p.returncode == 0:
            state = "PASS"
        else:
            state = "FAIL"
    return {"suite": name, "passed": ok, "failed": bad, "seconds": round(secs, 1), "state": state, "exit": p.returncode,
            "tail": "\n".join((out or "").strip().splitlines()[-12:]), "fails": [ln[:240] for ln in (out or "").splitlines() if ln.startswith("[FAIL]")][:8]}


def table(rows: list) -> str:
    w = max([len(r["suite"]) for r in rows] + [5])
    lines = [f"| {'suite':<{w}} | passed | failed | seconds | state |", f"|{'-' * (w + 2)}|-------:|-------:|--------:|-------|"]
    for r in rows:
        lines.append(f"| {r['suite']:<{w}} | {r['passed']:>6} | {r['failed']:>6} | {r['seconds']:>7} | {r['state']}{(' (' + r['note'] + ')') if r.get('note') else ''} |")
    tot = sum(r["seconds"] for r in rows)
    lines.append(f"| {'TOTAL':<{w}} | {sum(r['passed'] for r in rows):>6} | {sum(r['failed'] for r in rows):>6} | {tot:>7.0f} | "
                 f"{sum(1 for r in rows if r['state'] == 'PASS')}/{len(rows)} suites pass |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("area", nargs="?", choices=sorted(list(AREAS) + ["all"]))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--budget", type=float, default=900)
    ap.add_argument("--gate", type=float, default=2.0 * CPUS)
    ap.add_argument("--gate-wait", type=float, default=300)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--skip-load", type=float, default=0)
    a = ap.parse_args(argv)
    if a.list or not a.area:
        for k in list(AREAS) + ["all"]:
            print(f"{k:8} {', '.join(suites_for(k))}")
        return 0
    names = suites_for(a.area)
    if a.only:
        keys = [k.strip() for k in a.only.split(",") if k.strip()]
        names = [n for n in names if any(k in n for k in keys)]
    env = dict(os.environ)
    if a.fast:
        env["BK_FAST"] = "1"
    if a.skip_load:
        env["BK_MAX_LOAD"] = str(a.skip_load)
    rows = []
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"area {a.area}: {len(names)} suites, load {load1():.1f} on {CPUS} cpus, budget {a.budget:.0f}s each (slow browser suites x3)", flush=True)
    for n in names:
        g = gate(a.gate, a.gate_wait)
        if g == "loaded" and a.strict:
            rows.append({"suite": n, "passed": 0, "failed": 0, "seconds": 0, "state": "SKIP (machine too loaded)", "exit": None, "tail": "", "fails": []})
            print(f"  {n}: SKIP, machine too loaded (load {load1():.0f})", flush=True)
            continue
        r = run_one(n, a.budget * (3 if n in SLOW else 1), env)
        if g:
            r["note"] = "ran loaded" if g == "loaded" else g
        rows.append(r)
        print(f"  {n}: {r['state']} {r['passed']} ok / {r['failed']} bad in {r['seconds']}s", flush=True)
        for f in r["fails"][:3]:
            print("     " + f, flush=True)
    out = os.path.join(ROOT, "scratch", "results")
    os.makedirs(out, exist_ok=True)
    md = table(rows)
    with open(os.path.join(out, f"{a.area}-{stamp}.json"), "w", encoding="utf-8") as fh:
        json.dump({"area": a.area, "at": stamp, "cpus": CPUS, "rows": rows}, fh, indent=1)
    with open(os.path.join(out, f"{a.area}-{stamp}.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# {a.area} {stamp}\n\n{md}\n")
    print("\n" + md + f"\n\nwritten: scratch/results/{a.area}-{stamp}.json / .md")
    return 0 if all(r["state"] == "PASS" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
