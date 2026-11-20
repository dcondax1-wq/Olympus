"""Run the right test suites for one area, one at a time (job 23, 2026-11-04).

    python tests/run_area.py jarvis|olympus|zenith|kalshi|cities|nq|pc|all [options]
    python tests/run_area.py --list                    the areas and their suites
    python tests/run_area.py jarvis --only hub,home    only suites whose name contains one of these
    python tests/run_area.py pc --skip a,b             leave these suites out (default: win_scripts; --skip '' runs it)
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
    "jarvis": ["jarvis_system", "jarvis_assistant", "jarvis_obsidian", "jarvis_modes", "jarvis_brain", "jarvis_skills", "jarvis_tools", "jarvis_apps", "jarvis_core",
               "jarvis_speech", "jarvis_voice", "jarvis_talk", "jarvis_bots", "jarvis_engines", "jarvis_transitions", "sync_truth", "jarvis_classic", "jarvis_classic_home", "jarvis_home", "jarvis_hub", "phone_e2e"],
    "olympus": ["olympus_sfx", "sfx_engine", "sfx_lab", "olympus_fx", "olympus_kit", "olympus_render", "olympus_themes", "app_intro", "warp", "oracle_page", "odeon_page", "fates", "arena",
                "argus_page", "ares_page", "athena_page", "chronos_page", "forum_page", "hephaestus_page", "hermes", "labyrinth_page", "nemesis_page",
                "plutus_page", "prometheus", "tyche_page", "pantheon", "mind_page", "datacity"],
    "zenith": ["hidden_bots", "zenith_shell", "zenith_pages", "zenith_pro", "zenith_mode", "atlas_ui", "blitz_tab", "planner_addons", "ui_polish", "phone_e2e", "feed_accounts"],
    "kalshi": ["kalshi_edges", "kalshi_red_team", "kalshi_research", "kalshi_publish", "kalshi_guard", "kalshi_live", "kalshi_clock", "kalshi_vm_update", "kalshi_rewards_paper", "kalshi_best_shot", "kalshi_page", "kalshicity_page"],
    "cities": ["world_build", "cities_page", "kalshicity_page", "datacity", "world_page"],
    "nq": ["lit_live", "risk_monitors", "no_yahoo", "risk_invariants", "mffu_rules", "holidays", "holiday_replay", "guards", "sizing_caps", "second", "eval_lifecycle", "lifecycle", "live_board", "live_publish", "mffu_view", "heartbeat",
           "lit_scale_in", "lit_learn", "learn_loop", "zeus_lab", "setup_grade", "other_markets"],
    "pc": ["autoupdate_source", "pc_doctor", "obsidian_sync", "autorun", "update_from_zip", "pc_publish", "pc_publish_cloudflare", "gh_publish", "cloudflare_setup", "public_build_privacy", "bots_back", "report_keeper", "trade_watch_atlas", "setup_everything", "calendar_sync", "me_hub", "live_link", "roll_now", "pc_guard", "launch_kit", "second_backup", "clean_pc", "clean_storage", "lite", "win_scripts", "fresh_start", "pc_health", "pc_selftest", "pc_silent", "notify", "pc_command_center", "one_time_setup", "board", "phone_safety", "kalshi_live", "kalshi_clock", "datapipe", "datafeed", "risk_monitors", "pc_bars"],
    "agency": ["agency", "agency_billing", "cold_calls", "agency_storefront", "agency_upsells", "biz_models"],
    "privacy": ["public_build_privacy", "private_link", "repo_secrets", "phone_safety"],       # team Q2 2026-11-14, docs/PRIVACY.md
    "money": ["money_machines", "digital_products", "money_door", "payout_plan", "payout_coach", "biz_models", "business_pages", "mffu_center", "business_goals", "weekly_review", "money_plan", "combo_account"],
    "trading": ["trading_page", "edge_chip", "pc_bars", "nq_chart"],                                                      # the Trading page (tools/web_public/trading/, 2026-11-17)
    "fleet": ["fleet_mffu", "copy_accounts", "firms", "fleet", "rapid", "rapid25", "news_official", "accounts_cli", "onboard", "cross_hedge"],                 # team E 2026-11-16: copy accounts + firm rules
    "board": ["board", "payout_coach", "bots_back", "live_link", "edge_chip", "zeus_hub", "help_page", "decide"],                                       # night-board 2026-11-17: the Board (docs/BOARD.md)
    "journal": ["journal_edge", "journal_page", "kronos_page", "apollo_page", "kratos_page", "kairos_page", "odeon_page"],   # night-botgap 2026-11-18: the trade-journal apps + Mnemosyne's "The bot's edge"
}
AREAS["money"] += ["widget", "money_dash"]      # night-revamp-dash 2026-11-20: the Scriptable widget + Glance page (tools/web_public/widget/)
AREAS["olympus"].append("olympus_shell")  # night-revamp-main 2026-11-20: the main pages: no sideways scroll, nothing under the bottom bar, keys above the home bar (tools/olympus_shell_audit.py)
AREAS["olympus"].append("pulse")         # day-arenas 2026-11-20: the shared prop-trader cards in the main apps (olympus/pulse.js), CLS 0, light + dark
AREAS["olympus"].insert(0, "site_sweep")  # night-siteqa 2026-11-20: every href / src of the main pages + doors.js points at a real file (no browser, 1 s); its own line
AREAS["pc"].append("disk_clean")        # night-clean 2026-11-19: the weekly container clean (tools/disk_clean.py); its own line, no clash with the pc list
AREAS["pc"].append("account_box")     # 2026-11-20: the Add account box (engine/account_box.py, /add-account/); its own line
AREAS["pc"].append("phone_link")      # 2026-11-20: the bot server's own private Tailscale port :8444 (engine/phone_link.py)
AREAS["pc"].append("self_heal_pc")    # night-selfheal 2026-11-20: the PC self-heal (engine/self_heal.py, docs/SELF_HEAL.md); its own line
AREAS["pc"].append("remote_ctl")      # night-phonectl 2026-11-20: phone remote through the backup repo (olympus/control, engine/remote_ctl.py)
AREAS["pc"].append("obsidian_brain")    # night-obsidian 2026-11-20: ZEUS Brain, the generated Obsidian vault (tools/obsidian_brain.py, vault/); its own line
AREAS["nq"].append("why_page")          # night-anatomy 2026-11-18: why we win / lose (tools/win_loss_anatomy.py, tools/web_public/why/); its own line
AREAS["nq"].append("learn_night")       # night-learnloop 2026-11-19: ZEUS learned (engine/zeus_learn.py) + tools/learn_night.py + metals feed + speed; its own line
AREAS["nq"].append("combo_50k")         # night-combolive 2026-11-19: ATLAS + Zlarior on ONE 50K (engine/combo50k.py, OFF) + its LiveBot parity replay
AREAS["pc"].append("learn_night")       # the same suite: the PC side (data pipe hook, status ext "zl", datafeed metals, the 15-minute report's imports)
AREAS["kalshi"].append("kalshi_adapt")  # night-kadapt 2026-11-19: the K8 weekly re-test (engine/kalshi_adapt.py, tools/kalshi_adapt.py); its own line
AREAS["money"].append("money_ideas")   # night-moneyideas 2026-11-20: money book + Kalshi bankroll ladder (tools/money/money_book.py, kalshi_bankroll.py); its own line
AREAS["money"].append("fleet_months")  # day-fleet 2026-11-20: the whole fleet month by month to Jun 2027 (tools/money/fleet_months.py, business/fleet_plan.json); its own line
AREAS["pc"].append("kalshi_adapt")      # the same suite: the PC half (pc_weekly, clock_adapt.json, the ZEUS learned line)
AREAS["kalshi"].append("kalshi_k8_monday")  # night-kalshi8 2026-11-20: the $55 rule, the edge tests, the Nov 16-19 dry run (research/kalshi_k8_monday/); its own line
AREAS["kalshi"].append("kalshi_k8_dash")    # day-kalshi 2026-11-20: the K8 day dashboard (Kalshi page K8 card + Dionysus "K8 today"; node Playwright); its own line
AREAS["kalshi"].append("kalshi_k8_day")  # day-kalshi 2026-11-20: Monday rehearsal, every stop on $55, restarts, no order without key + phrase; its own line
AREAS["kalshi"] += ["dionysus_page", "dionysus_merge"]  # day-kalshi 2026-11-20: Dionysus absorbs Kalshi City + Sibyl as plain cards (node Playwright); its own line
AREAS["nq"].append("live_gap_proposal")  # night-litmore 2026-11-19: live vs backtest gap + the fill_audit "no record" proposal (tools/live_gap_proposal.py); its own line
AREAS["nq"] += ["nq_live_reliability", "fast_entry"]   # night-nqlive 2026-11-20: missed-trade alarms + audit fixes, poll-on-tick (OFF); own line
AREAS["pc"] += ["nq_live_reliability", "account_b_min_room"]   # the same suite (fast alarm, autoupdate flat, datafeed gaps) + ATLAS min_room CLI
AREAS["nq"].append("fill_cost")          # night-atlasfills 2026-11-20: "real slippage so far" per bot (tools/fill_cost.py + learn_night card)
# night-webpush 2026-11-19: Olympus phone notifications from the PC (engine/push.py: own key, relay intake, phone first / ntfy backup;
# docs/NOTIFICATIONS.md); the browser half (the card, the button, push-sw.js) runs with the jarvis suites
AREAS["pc"] += ["push", "webpush"]
AREAS["jarvis"].insert(AREAS["jarvis"].index("jarvis_classic"), "jarvis_push")
# night-fitperf 2026-11-19: edge to edge on the iPhone Home Screen app (dock, app frames, host badge, phantom keyboard) + the start memo; its own line
AREAS["jarvis"].append("fit_edge")
AREAS["pc"].append("trade_alerts")    # night-tradealerts 2026-11-20: entry + exit alerts on every account route (tests/test_trade_alerts.py); its own line
AREAS["board"].append("phone_fit")    # night-tradealerts 2026-11-20: ZEUS / MFFU / Trading / Board at 390 + 430 px with the iPhone safe areas (browser); its own line
AREAS["board"].append("steps_page")   # night-ownersteps 2026-11-20: hub/steps.html "Your steps" (browser part under the lock); its own line
AREAS["olympus"].append("home_fx")          # night-effects 2026-11-20: the living hero on the Gate + Doors (tests/test_home_fx.py)
AREAS["nq"].append("nqdeep")                # night-nqdash2 2026-11-20: Trading deep dive / MFFU payout ranges / NQ news week
AREAS["money"].append("business_taxes")   # day-taxes 2026-11-20: Taxes page + keep-the-most waterfall (tools/money/keep_most.py)
AREAS["board"].append("owner_manual")  # day-manual 2026-11-20: hub/manual.html + docs/OWNER_MANUAL.md (browser part under the lock); its own line
AREAS["pc"].append("land_branch")       # 2026-11-20: the lead's landing tool (tools/land_branch.py: preview, merge, known conflicts, fix-ups, plan); its own line
# suites too long for one budget run BY PARTS, each its own row and budget (night team D 2026-11-16: the whole kit walk, every app +
# power + tiers + more in one browser, is the longest browser suite); a part is "<suite>:<label>" = python -m tests.test_<suite> <args>
PARTS = {"olympus_kit": [("a", ["datacity", "mind", "tree"]), ("b", ["oracle", "odeon", "fates"]), ("c", ["hermes", "prometheus", "tyche"]),
                         ("power", ["power", "tiers"]), ("more", ["more"])]}
PARTS["combo_50k"] = [("sep", ["--seg", "2026-09-02"]), ("oct", ["--seg", "2026-10-02", "--scenario"])]   # night-combolive: one eval segment each
AREAS["olympus"].append("node_suites")    # day-quality 2026-11-20: the 29 tests/*.mjs no Python suite ran (tests/test_node_suites.py), by part
AREAS["cities"].append("node_suites")
PARTS["node_suites"] = [("datacity", ["datacity"]), ("apps", ["apps"])]
AREAS["pc"].append("site_checks")         # day-quality 2026-11-20: tools/site_checks.py (Kalshi cache = css/js ?v, worker tags, launcher drift, generated gap) + self_heal 'site'
AREAS["olympus"].append("site_checks")
AREAS["fleet"].append("rapid_launch")       # day-rapid 2026-11-20: Rapid EOD 25K launch check (tools/money/rapid25_launch.py)
SLOW = {"olympus_shell", "fit_edge", "jarvis_hub", "phone_e2e", "olympus_kit", "olympus_themes", "olympus_render", "zenith_mode", "ui_polish", "datacity", "jarvis_home"}


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


def run_one(name: str, budget: float, env: dict, args=()) -> dict:
    t0 = time.time()
    p = subprocess.Popen([sys.executable, "-X", "utf8", "-m", f"tests.test_{name.split(':')[0]}", *args], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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
AREAS["board"].append("payready"); AREAS["trading"] += ["payready", "nq_desk", "trading_merged", "alert_audit"]   # nqdash3 2026-11-20: payout readiness, the NQ desk, the merged Odeon / Why cards, the alert audit; its own line
AREAS["pc"].append("alert_audit")
AREAS["nq"].append("premarket_brief")       # day-brief 2026-11-20: nq/brief.json contract + pre-registered bias (tools/premarket_brief.py)
AREAS["money"].append("week_more")          # day-brief 2026-11-20: weekly review round 2 (twins, best/worst, K8, calendar, weekend)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("area", nargs="?", choices=sorted(list(AREAS) + ["all"]))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="win_scripts", help="suites to leave out, comma list of exact names (default win_scripts: never in a cloud run)")
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
    skip = {k.strip() for k in a.skip.split(",") if k.strip()}
    names = [n for n in names if n not in skip]
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
        for label, args in PARTS.get(n, [("", [])]):
            nm = f"{n}:{label}" if label else n
            r = run_one(nm, a.budget * (3 if n in SLOW else 1), env, args)
            if g:
                r["note"] = "ran loaded" if g == "loaded" else g
            rows.append(r)
            print(f"  {nm}: {r['state']} {r['passed']} ok / {r['failed']} bad in {r['seconds']}s", flush=True)
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
