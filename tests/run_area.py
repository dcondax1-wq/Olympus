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
Faster landing (day-quality round 2, 2026-11-20):
             --changed BASE    only the suites that read a file changed since BASE (tests/suite_map.py: imports + path strings; a
                               file no suite maps, or a shared kit file, runs the whole area), the skipped ones are printed with why
             --jobs N          plain suites N at once (default cpus-1); browser suites stay one at a time in their own lane
             --no-lock         do not take /tmp/olympus_browser.lock (--lock PATH, --lock-wait SEC 2400); by default the runner takes it
                               ONLY around each browser suite, so no outer `flock` is needed (an outer one is recognised, no deadlock)
Safe next to other agents: it runs ONE browser suite at a time, never lists or signals any process but its own child, and the child
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
                "plutus_page", "prometheus", "tyche_page", "pantheon", "mind_page", "datacity", "clio_page", "research_hub"],
    "zenith": ["hidden_bots", "zenith_shell", "zenith_pages", "zenith_pro", "zenith_mode", "atlas_ui", "blitz_tab", "planner_addons", "ui_polish", "phone_e2e", "feed_accounts"],
    "kalshi": ["kalshi_edges", "kalshi_red_team", "kalshi_research", "kalshi_publish", "kalshi_guard", "kalshi_live", "kalshi_clock", "kalshi_vm_update", "kalshi_rewards_paper", "kalshi_best_shot", "kalshi_page", "kalshicity_page"],
    "cities": ["world_build", "cities_page", "kalshicity_page", "datacity", "world_page"],
    "nq": ["lit_live", "risk_monitors", "no_yahoo", "risk_invariants", "mffu_rules", "holidays", "holiday_replay", "guards", "sizing_caps", "second", "eval_lifecycle", "lifecycle", "live_board", "live_publish", "mffu_view", "heartbeat",
           "lit_scale_in", "lit_learn", "learn_loop", "zeus_lab", "setup_grade", "other_markets", "keepalive", "rehearse_caps"],
    "pc": ["autoupdate_source", "pc_doctor", "obsidian_sync", "autorun", "update_from_zip", "pc_publish", "pc_publish_cloudflare", "gh_publish", "cloudflare_setup", "public_build_privacy", "bots_back", "report_keeper", "trade_watch_atlas", "setup_everything", "calendar_sync", "me_hub", "live_link", "roll_now", "pc_guard", "launch_kit", "second_backup", "clean_pc", "clean_storage", "lite", "win_scripts", "fresh_start", "pc_health", "pc_selftest", "pc_silent", "notify", "pc_command_center", "one_time_setup", "board", "phone_safety", "kalshi_live", "kalshi_clock", "datapipe", "datafeed", "risk_monitors", "pc_bars", "lucid_rt"],
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
AREAS["agency"].append("web_expert")       # team web-expert 2026-11-20: agency/expert/ (the playbook, the 5-tap diagnosis) + Jarvis 'web' answers
AREAS["jarvis"].append("jarvis_shortcuts")  # team JARVIS 2026-11-20: the Siri / Shortcuts page + the "Add to Home Screen" hint
AREAS["jarvis"].append("jarvis_fx")  # owner 2026-11-20 "3D, effects, no gold": jfx.css / jfx.js, the switcher without gold
AREAS["jarvis"].append("jarvis_money_answers")  # lead QA 2026-11-21: the 60 money questions, live + PC-silent
AREAS["olympus"].append("pulse")         # day-arenas 2026-11-20: the shared prop-trader cards in the main apps (olympus/pulse.js), CLS 0, light + dark
AREAS["olympus"].append("archive_banners")  # day-archive 2026-11-20: the "Archived · data <date>, N days old -> live app" strip on every archived page (tools/archive_banners.py)
AREAS["olympus"].append("olympus_nav")     # day-a11y 2026-11-21 ORGANIZE: link crawler (no 404), every app <= 2 taps from Home, Home > arena > app on every page, retired -> replacement
AREAS["olympus"].append("home_six")        # day-a11y 2026-11-22: the app opens on the 6 main dashboards (gate/), More hides the rest, the installed app's launch lands on Home
AREAS["olympus"].insert(0, "site_sweep")  # night-siteqa 2026-11-20: every href / src of the main pages + doors.js points at a real file (no browser, 1 s); its own line
AREAS["pc"].append("disk_clean")        # night-clean 2026-11-19: the weekly container clean (tools/disk_clean.py); its own line, no clash with the pc list
AREAS["pc"].append("account_box")     # 2026-11-20: the Add account box (engine/account_box.py, /add-account/); its own line
AREAS["pc"].append("phone_link")      # 2026-11-20: the bot server's own private Tailscale port :8444 (engine/phone_link.py)
AREAS["pc"] += ["arm_report", "arm_rt"]   # day-armfix 2026-11-22 + red team 2026-11-23: START summary, ATLAS funded rename (keeps every number)
AREAS["pc"].append("self_heal_pc")    # night-selfheal 2026-11-20: the PC self-heal (engine/self_heal.py, docs/SELF_HEAL.md); its own line
AREAS["pc"].append("remote_ctl")      # night-phonectl 2026-11-20: phone remote through the backup repo (olympus/control, engine/remote_ctl.py)
AREAS["pc"] += ["trading_home"]   # 2026-11-22: TRADE_HOME.bat menu (engine/trade_home.py), add-account prices, nq/trading_home.html at 390x844
AREAS["pc"] += ["nqops", "pc_always_on"]   # day-nqops 2026-11-21: Sunday/daily preflight, cloud pre-open push, the MFFU 7-day clock (engine/preflight.py, engine/clock7.py, nq/clock7.js); the PC always-on tool (tools/pc_always_on.py)
AREAS["pc"].append("ready")         # day-ready 2026-11-22: READY / NOT READY self-check (engine/readiness.py, tools/ready_check.py, the "rd" status block)
AREAS["pc"].append("ready_rt")      # red team 2026-11-23: start hook never blocks, read-only, no spam, no false NOT READY
AREAS["pc"].append("lucid")         # day-nqdash3 2026-11-22: the second firm, LucidPro 50K OFF by default (engine/account_cli lucidpro50k, docs/LUCID_SETUP.md)
AREAS["agency"].append("web_offers")
AREAS["agency"].append("web_outreach")
AREAS["agency"].append("agency_autopilot")
AREAS["agency"].append("postcards")       # day-a11y 2026-11-20: personalised postcards (tools/postcards.py, POSTCARD_SETUP.bat), a fake Lob   # day-a11y 2026-11-20: the PC email autopilot (agency/autopilot/, EMAIL_SETUP.bat), fake Gmail, never the network   # day-a11y 2026-11-20: the Website Factory outreach + close kit (agency/outreach/)
AREAS["agency"].append("web_portal")      # day-a11y 2026-11-21: the CALLER PORTAL (agency/portal/ + agency/portal.py): the human cold caller's list, rules, log
AREAS["agency"].append("site_quality")    # day-a11y 2026-11-22: the 150 concept sites on the call sheet (names, trade, call link, 44 px, photos), the premium top 20
AREAS["trading"].append("panelfx")      # day-a11y 2026-11-20: the effects layer on Trading / Business / Planner (trading/panelfx.js)   # day-web-offers 2026-11-20: Agency Offers (agency/offers/): packages, proposal, terms, invoices + retainers, goal
AREAS["pc"].append("obsidian_brain")    # night-obsidian 2026-11-20: ZEUS Brain, the generated Obsidian vault (tools/obsidian_brain.py, vault/); its own line
AREAS["nq"].append("why_page")          # night-anatomy 2026-11-18: why we win / lose (tools/win_loss_anatomy.py, tools/web_public/why/); its own line
AREAS["nq"].append("learn_night")       # night-learnloop 2026-11-19: ZEUS learned (engine/zeus_learn.py) + tools/learn_night.py + metals feed + speed; its own line
AREAS["nq"].append("combo_50k")         # night-combolive 2026-11-19: ATLAS + Zlarior on ONE 50K (engine/combo50k.py, OFF) + its LiveBot parity replay
AREAS["pc"].append("learn_night")       # the same suite: the PC side (data pipe hook, status ext "zl", datafeed metals, the 15-minute report's imports)
AREAS["kalshi"].append("kalshi_adapt")  # night-kadapt 2026-11-19: the K8 weekly re-test (engine/kalshi_adapt.py, tools/kalshi_adapt.py); its own line
AREAS["money"].append("money_ideas")   # night-moneyideas 2026-11-20: money book + Kalshi bankroll ladder (tools/money/money_book.py, kalshi_bankroll.py); its own line
AREAS["money"].append("fleet_months")  # day-fleet 2026-11-20: the whole fleet month by month to Jun 2027 (tools/money/fleet_months.py, business/fleet_plan.json); its own line
AREAS["money"].append("fleet_90day")   # day-fleet 2026-11-21: the 90-day scale plan + its 3 purchase cards (tools/money/fleet_90day.py); its own line
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
AREAS["money"].append("business_taxes")
AREAS["money"].append("account_rules")   # day-taxes 2026-11-20: bot constants = research/lit/mffu_rules.json (docs/ACCOUNT_RULES.md)   # day-taxes 2026-11-20: Taxes page + keep-the-most waterfall (tools/money/keep_most.py)
AREAS["board"].append("owner_manual")  # day-manual 2026-11-20: hub/manual.html + docs/OWNER_MANUAL.md (browser part under the lock); its own line
AREAS["olympus"].append("nav_search")     # day-manual NAV 2026-11-20: 67 plain phrasings -> the right place first (olympus/gate-catalog.js findAll); node only
AREAS["board"].append("nav_pages")       # day-manual NAV 2026-11-20: hub help/steps/manual/zeus/doors: Home first, the OLYMPUS look, 390 px (browser part under the lock)
AREAS["agency"].append("web_hub")         # day-web-hub 2026-11-20: the Website Business HQ on agency/index.html (browser part under the lock)
AREAS["pc"].append("land_branch")       # 2026-11-20: the lead's landing tool (tools/land_branch.py: preview, merge, known conflicts, fix-ups, plan); its own line
AREAS["olympus"].append("node_suites")    # day-quality 2026-11-20: the 29 tests/*.mjs no Python suite ran (tests/test_node_suites.py), by part
AREAS["cities"].append("node_suites")
AREAS["pc"].append("site_checks")         # day-quality 2026-11-20: tools/site_checks.py (Kalshi cache = css/js ?v, worker tags, launcher drift, generated gap) + self_heal 'site'
AREAS["olympus"].append("site_checks")
AREAS["pc"].append("run_area_fast")       # day-quality round 2: --changed mapper (tests/suite_map.py), parallel lanes, the per-suite browser lock
AREAS["privacy"].append("status_sign")   # day-security 2026-11-20: signed status posts + no future-dated post (tests/test_status_sign.py); its own line
AREAS["board"].append("status_sign")
AREAS["pc"] += ["status_sign", "pc_report_sign", "push_pairing", "datafeed_sign", "nqbars_sign"]   # day-security2 2026-11-20: W3 W4 W6 W7; its own line
AREAS["privacy"] += ["pc_report_sign", "push_pairing", "datafeed_sign", "nqbars_sign"]
AREAS["nq"].append("nqbars_sign")
AREAS["pc"].append("autoupdate_paths")   # updategate 2026-11-20: site-only updates never restart the bot, import check, crash-loop rollback; its own line
AREAS["pc"].append("pc_watch")            # day-quality round 3: the cloud PC watch (.github/workflows/pc-watch.yml, docs/PC_WATCH.md)
AREAS["nq"].append("data_health")      # day-brief 2026-11-20: data health + the ES feed (MES with MNQ) in the live engine
AREAS["olympus"].append("perf_sweep")      # day-quality Olympus v2: tools/perf_sweep.py (phone sweep + offline pass, budgets tools/perf_budgets.json)
AREAS["privacy"].append("scrub_cache")      # day-quality 2026-11-20: site_privacy.scrub's clean-file cache (warm build 67 s -> 29 s)
AREAS["olympus"].append("offline_apps")    # day-quality Olympus v2: every visible app opens offline after one visit (browser)
for _a in ("pc", "nq"):                   # wf-atlas-start 2026-11-20: ATLAS without a start day = a plain problem + push, never a TypeError
    if "account_b_start" not in AREAS[_a]:
        AREAS[_a].append("account_b_start")
# suites too long for one budget run BY PARTS, each its own row and budget (night team D 2026-11-16: the whole kit walk, every app +
# power + tiers + more in one browser, is the longest browser suite); a part is "<suite>:<label>" = python -m tests.test_<suite> <args>
PARTS = {"olympus_kit": [("a", ["datacity", "mind", "tree"]), ("b", ["oracle", "odeon", "fates"]), ("c", ["hermes", "prometheus", "tyche"]),
                         ("power", ["power", "tiers"]), ("more", ["more"])]}
PARTS["combo_50k"] = [("sep", ["--seg", "2026-09-02"]), ("oct", ["--seg", "2026-10-02", "--scenario"])]   # night-combolive: one eval segment each
AREAS["fleet"].append("rapid_launch")       # day-rapid 2026-11-20: Rapid EOD 25K launch check (tools/money/rapid25_launch.py)
for _a in ("fleet", "pc"):                  # fix-trade 2026-11-21: an added Rapid / account armed by Start trading's phrase (engine/go.py)
    if "rapid_arm" not in AREAS[_a]:
        AREAS[_a].append("rapid_arm")
SLOW = {"olympus_shell", "fit_edge", "jarvis_hub", "phone_e2e", "olympus_kit", "olympus_themes", "olympus_render", "zenith_mode", "ui_polish", "datacity", "jarvis_home"}


AREAS["agency"].append("web_audit")         # day-web-audit 2026-11-20: tools/site_audit.py (prospect phone audit -> agency/audit/)


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


def run_all(names: list, a, env: dict, jobs: int) -> list:
    """Plain suites on `jobs` workers; browser suites (tests/suite_map.is_browser) one at a time in their own lane, each under the
    browser lock (taken per suite, so other helpers' browser runs interleave; an outer flock of this process tree is recognised).
    The load gate applies to the browser lane only. Rows come back in the area's order."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import browser_lock
    import suite_map
    tasks = []                                            # (index, suite, part name, args, browser)
    for n in names:
        br = suite_map.is_browser(n)
        for label, args in PARTS.get(n, [("", [])]):
            tasks.append((len(tasks), n, f"{n}:{label}" if label else n, args, br))
    out = [None] * len(tasks)
    say = threading.Lock()

    def report(i, r):
        out[i] = r
        with say:
            print(f"  {r['suite']}: {r['state']} {r['passed']} ok / {r['failed']} bad in {r['seconds']}s"
                  + (f" ({r['note']})" if r.get("note") else ""), flush=True)
            for f in r["fails"][:3]:
                print("     " + f, flush=True)

    def plain(t):
        i, n, nm, args, _br = t
        report(i, run_one(nm, a.budget * (3 if n in SLOW else 1), env, args))

    def browser_lane(ts):
        for i, n, nm, args, _br in ts:
            g = gate(a.gate, a.gate_wait)
            if g == "loaded" and a.strict:
                report(i, {"suite": nm, "passed": 0, "failed": 0, "seconds": 0, "state": "SKIP (machine too loaded)", "exit": None, "tail": "", "fails": []})
                continue
            try:
                if a.no_lock:
                    r = run_one(nm, a.budget * (3 if n in SLOW else 1), env, args)
                    how = "off"
                else:
                    t0 = time.time()
                    with browser_lock.hold(a.lock, a.lock_wait) as how:
                        waited = time.time() - t0
                        r = run_one(nm, a.budget * (3 if n in SLOW else 1), env, args)
                    if waited >= 5:
                        g = (g + "; " if g else "") + f"lock wait {waited:.0f}s"
            except TimeoutError as e:
                r = {"suite": nm, "passed": 0, "failed": 0, "seconds": 0, "state": "SKIP (browser lock busy)", "exit": None, "tail": str(e), "fails": []}
            if g:
                r["note"] = "ran loaded" if g == "loaded" else g
            report(i, r)

    br_tasks = [t for t in tasks if t[4]]
    pl_tasks = [t for t in tasks if not t[4]]
    lane = threading.Thread(target=browser_lane, args=(br_tasks,), daemon=True)
    lane.start()
    if jobs <= 1:
        for t in pl_tasks:
            plain(t)
    else:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            list(ex.map(plain, pl_tasks))
    lane.join()
    return [r for r in out if r is not None]


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
AREAS["trading"] += ["nq_goals", "nq_brain"]   # day-nqdash3 v4 2026-11-20: the NQ money goals strip, the numbers card, the 3D price landscape (tools/web_public/nq/nqgoals.js, nqland.js)
AREAS["pc"].append("alert_audit"); AREAS["pc"].append("ntfy_budget")   # 2026-11-20 ntfy cap: tools/pc_report.py ext_hash + ntfy_quota
AREAS["trading"].append("truth_check"); AREAS["board"].append("truth_check")   # Olympus 2 data truth (tools/truth_check.py, age.js), offline
AREAS["nq"].append("premarket_brief")       # day-brief 2026-11-20: nq/brief.json contract + pre-registered bias (tools/premarket_brief.py)
AREAS["money"].append("week_more")          # day-brief 2026-11-20: weekly review round 2 (twins, best/worst, K8, calendar, weekend)
AREAS["privacy"].append("cross_site")   # day-security 2026-11-20: the bot server refuses POSTs from other web sites (engine/cross_site.py)
AREAS["pc"].append("cross_site")
AREAS["pc"].append("redteam2_live")       # day-redteam2 2026-11-20: half-day halt alarm + TRADE HAS NO STOP alarm (engine/fast_alarm.py)
AREAS["pc"].append("alert_bus")         # day-alerts 2026-11-21: engine/alert_bus.py (Telegram / Discord first, ntfy + Web Push fallbacks)
AREAS["pc"].append("alert_drill")       # day-alerts 2026-11-21: end-to-end alert drill (telegram / ntfy / off set-ups)
AREAS["pc"].append("alerts_box")        # alerts-phone 2026-11-21: /alerts/ = ALERTS_SETUP Telegram from the phone (engine/alerts_box.py); its own line
AREAS["pc"].append("alerts_start_code")   # day-security3 2026-11-21: the /alerts/ page's one-time START code; its own line
AREAS["privacy"] += ["alerts_start_code", "cross_site"]
AREAS["nq"].append("redteam2_live")
AREAS["pc"].append("redteam2_wires")      # day-redteam2 2026-11-20: L2 rapid._other_names covers the extra accounts
AREAS["agency"].append("web_research")   # day-web-research 2026-11-20: the website-business research (RESEARCH.md, writeup, offers.json); its own line
AREAS["agency"].append("web_demos")      # day-web-demos 2026-11-20: the 4 sellable 3D website demos + gallery (tools/web_public/agency/demos/); its own line
AREAS["olympus"].append("site_refresh")   # day-archive 2026-11-20: tools/site_refresh.py, the CRONOS-era builders at site-build time (never fatal); its own line
AREAS["olympus"].append("nqfx")           # day-arenas 2026-11-20: the NQ dashboard effects kit (olympus/nqfx.js, nqvault3d.js, nqfx-lab.html); its own line


AREAS["agency"].append("web_leads")  # day-web-leads 2026-11-20: OpenStreetMap lead finder + agency/leads/ phone list (tools/web_leads.py); its own line


AREAS["agency"].append("web_showcase")   # day-web 2026-11-20: the owner's agency website (tools/web_public/agency/showcase/)
AREAS["zenith"].append("zenith_settle")  # day-arenas 2026-11-20: Home start-up without jumps (zenith_settle.js, home.json first, the NQ strip slot)
AREAS["olympus"].append("dashfx")        # day-arenas 2026-11-20: the dashboard FX layer (olympus/dashfx.js + dashfx.css, dashfx-lab.html); its own line
AREAS["cities"].append("brain_hub")       # day-brain4 2026-11-22: the giant research brain (cities/brain.html); its own line
AREAS["olympus"].append("brain3d")       # day-arenas 2026-11-21: the bot brain in 3D (olympus/brain3d.js + brain3d-scene.js, brain3d-lab.html); its own line

AREAS["agency"].append("site_factory")   # day-cities3 2026-11-21: Website Factory (tools/site_factory.py -> agency/f/<id>/ + agency/factory/)
AREAS["agency"].append("factory2")       # day-cities3 2026-11-21: agency launch site, client delivery, first 100 calls
AREAS["agency"].append("dnc_scrub")      # day-caller2 2026-11-21: the free National DNC scrub before any dial (agency/dnc_scrub.py)
AREAS["agency"].append("intake_page")      # day-caller2 2026-11-21: the client intake page (mailto only)
AREAS["nq"].append("shadow_leads")      # day-edge2 2026-11-21: paper-lead shadow log, observe only
AREAS["nq"].append("reconcile_live")      # day-atlasedge 2026-11-21: live vs model reconciliation
AREAS["agency"].append("leads_overture")  # day-cities3 2026-11-21: Overture website check of the leads (fixture parquet)

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
    ap.add_argument("--changed", default="", metavar="BASE", help="only the suites that read a file changed since BASE (tests/suite_map.py)")
    ap.add_argument("--jobs", type=int, default=max(1, CPUS - 1), help="plain (non-browser) suites at once (default cpus-1; 1 = the old serial run)")
    ap.add_argument("--no-lock", action="store_true", help="do not take the browser lock around browser suites")
    ap.add_argument("--lock", default="/tmp/olympus_browser.lock")
    ap.add_argument("--lock-wait", type=float, default=2400)
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
    if a.changed:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import suite_map
        plan = suite_map.select(names, suite_map.changed_since(a.changed))
        if plan["fallback"]:
            print(f"--changed {a.changed}: {plan['fallback']}", flush=True)
        else:
            print(f"--changed {a.changed}: {len(plan['run'])} of {len(names)} suites read a changed file", flush=True)
            for n, why in plan["skipped"].items():
                print(f"  skip {n}: {why}", flush=True)
            for n in plan["run"]:
                print(f"  run  {n}: reads {plan['why'][n]}", flush=True)
        names = plan["run"]
    rows = []
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    jobs = max(1, a.jobs)
    print(f"area {a.area}: {len(names)} suites, load {load1():.1f} on {CPUS} cpus, budget {a.budget:.0f}s each (slow browser suites x3), "
          f"{jobs} plain suite(s) at once, browser suites one at a time{'' if a.no_lock else ' under ' + a.lock}", flush=True)
    rows = run_all(names, a, env, jobs)
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
AREAS["agency"].append("pricebook")      # day-caller2 2026-11-21: one price book, checked everywhere (agency/pricebook.py --check)
AREAS["agency"].append("trade_scripts")   # day-caller2 2026-11-22: per-trade call scripts
AREAS["money"].append("money_pipeline")     # day-a11y 2026-11-22: the MONEY PIPELINE (business/pipeline.html + agency/pipeline.py) + the Corvette fund
AREAS["pc"] += ["clockfix"]        # 2026-11-22: FIX_CLOCK.bat + OlympusClock task + the schtasks fallback (engine/go.sync_clock, self_heal.fix_clock)
