"""The node-only test files (tests/*.mjs) that no Python suite runs (day-quality 2026-11-20).

    python -X utf8 -m tests.test_node_suites                 every group
    python -X utf8 -m tests.test_node_suites datacity        one group (datacity | apps)
    python -X utf8 -m tests.test_node_suites --stale         also the known-stale files (report only, never fails the run)

31 .mjs files sat unrun; 20 of them had gone red (old ?v pins, a redesigned page). Version pins in them are now
"has a ?v" (the bump tool and `tools/bump_versions.py --check` own the exact values). Every tests/*.mjs must be run by
some Python suite, be in GROUPS here, or be in STALE with its owner: a new orphan fails this suite.
Prints [PASS]/[FAIL] lines (tests/run_area.py counts them). Areas: olympus + cities (part datacity, part apps).
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")

GROUPS = {
    "datacity": ["test_datacity_context_loss", "test_datacity_fallback_ready", "test_datacity_first_frame_watchdog",
                 "test_datacity_frame_guard", "test_datacity_map_rescue", "test_datacity_phone_profile",
                 "test_datacity_satellite_network", "test_datacity_skyline", "test_datacity_standalone_map"],
    "apps": ["test_arena_citadel", "test_arena_colosseum_upgrade", "test_atlas_strategy_cities", "test_bridge_status_helper_fallback",
             "test_bridge_status_line", "test_cities_context_loss", "test_cities_districts", "test_cities_fallback",
             "test_intro_failed_kit", "test_kalshi_status_freshness", "test_kalshicity_network_switch",
             "test_launcher_celestial_glyphs", "test_observatory_lesson_clock", "test_observatory_scan_race",
             "test_oracle_city_quality", "test_oracle_fallback_city", "test_oracle_fallback_honesty", "test_oracle_future_source",
             "test_pantheon_gpu_recovery", "test_prometheus_fallback", "test_jarvis_biz",
             "test_atlas_intro", "test_atlas_standalone_hub"],   # night-reds 2026-11-22: were orphans (both green)
}
# red because the page was rebuilt (not a pin): the test reads code that moved. Owner today: day-cities3 (cities/).
STALE = {
    "test_cities_hq_network": "cities app switcher markup changed (APPS dialog name)",
    "test_cities_metropolis": "evals a module that now needs a $ helper",
    "test_cities_network_switcher": "networkApps button markup changed",
    "test_cities_routes": "five bridges where the test wants six worlds",
    "test_cities_keyboard": "evals an ES module as a script (export)",
    "test_cities_phone_map": "planCityNetwork moved out of the file it slices",
    "test_cities_record_overlay": "warmHex moved out of the file it slices",
}


def run(name: str, timeout: int = 180) -> tuple[bool, str]:
    path = os.path.join(TESTS, name + ".mjs")
    try:
        p = subprocess.run(["node", path], cwd=ROOT, capture_output=True, text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    out = (p.stdout or "") + (p.stderr or "")
    why = next((ln.strip() for ln in out.splitlines() if ln.startswith("not ok") or "Error" in ln), "")
    return p.returncode == 0, why[:200]


def orphans() -> list:
    """.mjs files no Python suite / tool names and that are in neither GROUPS nor STALE"""
    known = {n for g in GROUPS.values() for n in g} | set(STALE)
    py = ""
    for f in glob.glob(os.path.join(TESTS, "*.py")) + glob.glob(os.path.join(ROOT, "tools", "*.py")):
        if os.path.basename(f) == "test_node_suites.py":
            continue
        try:
            py += open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            pass
    out = []
    for f in sorted(glob.glob(os.path.join(TESTS, "*.mjs"))):
        b = os.path.basename(f)[:-4]
        if b not in known and (b + ".mjs") not in py:
            out.append(b)
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    stale = "--stale" in argv
    picks = [a for a in argv if not a.startswith("--")] or list(GROUPS)
    bad = 0
    for g in picks:
        for n in GROUPS[g]:
            ok, why = run(n)
            print(f"[{'PASS' if ok else 'FAIL'}] {g}: {n}{'' if ok else '  ' + why}", flush=True)
            bad += not ok
    if not [a for a in argv if not a.startswith("--")]:          # the whole run also guards against new orphans
        o = orphans()
        print(f"[{'FAIL' if o else 'PASS'}] every tests/*.mjs is run somewhere{(': orphan ' + ', '.join(o)) if o else ''}")
        bad += bool(o)
    if stale:
        for n, why in STALE.items():
            ok, got = run(n)
            print(f"  stale {n}: {'now green, move it to a group' if ok else 'still red'} ({why})")
    print(f"node suites: {'ALL PASS' if not bad else str(bad) + ' failed'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
