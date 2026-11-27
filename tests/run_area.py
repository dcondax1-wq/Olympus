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
    "pc": ["autoupdate_source", "pc_doctor", "obsidian_sync", "autorun", "update_from_zip", "pc_publish", "pc_publish_cloudflare", "gh_publish", "cloudflare_setup", "public_build_privacy", "bots_back", "report_keeper", "state_pulse", "hermetic", "trade_watch_atlas", "setup_everything", "calendar_sync", "me_hub", "live_link", "roll_now", "pc_guard", "launch_kit", "second_backup", "clean_pc", "clean_storage", "lite", "win_scripts", "fresh_start", "pc_health", "pc_selftest", "pc_silent", "notify", "pc_command_center", "one_time_setup", "board", "phone_safety", "kalshi_live", "kalshi_clock", "datapipe", "datafeed", "risk_monitors", "pc_bars", "lucid_rt"],
    "agency": ["agency", "agency_billing", "cold_calls", "agency_storefront", "agency_upsells", "biz_models"],
    "privacy": ["public_build_privacy", "private_link", "repo_secrets", "phone_safety"],       # team Q2 2026-11-14, docs/PRIVACY.md
    "money": ["money_machines", "digital_products", "money_door", "payout_plan", "payout_coach", "biz_models", "business_pages", "mffu_center", "business_goals", "weekly_review", "money_plan", "combo_account"],
    "trading": ["trading_page", "edge_chip", "pc_bars", "nq_chart"],                                                      # the Trading page (tools/web_public/trading/, 2026-11-17)
    "fleet": ["fleet_mffu", "copy_accounts", "firms", "fleet", "rapid", "rapid25", "news_official", "accounts_cli", "onboard", "cross_hedge"],                 # team E 2026-11-16: copy accounts + firm rules
    "board": ["board", "payout_coach", "bots_back", "live_link", "edge_chip", "zeus_hub", "help_page", "decide"],                                       # night-board 2026-11-17: the Board (docs/BOARD.md)
    "journal": ["journal_edge", "journal_build", "journal_page", "kronos_page", "apollo_page", "kratos_page", "kairos_page", "odeon_page"],   # night-botgap 2026-11-18: the trade-journal apps + Mnemosyne's "The bot's edge"
}
# audit D6 (2026-11-22): the PC self-test's suites that sat in no area (cloud landings never ran them)
AREAS["pc"] += ["start_api", "launch_checklist", "nt_outgoing", "nt_exec_audit", "selfheal", "ops", "run_switch", "new_accounts", "go",
                "nt_roll_guard", "broker_balance", "eval_fix", "fsutil", "account_rename"]
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
AREAS["pc"] += [m for m in ("start_api", "launch_checklist", "nt_outgoing", "nt_exec_audit", "selfheal", "ops", "run_switch",
                             "new_accounts", "go", "nt_roll_guard", "broker_balance", "eval_fix", "fsutil", "account_rename")
                 if m not in AREAS["pc"]]   # night-startfix 2026-11-22 (audit Package D): the PC self-test's suites, run at landing too
AREAS["pc"] += ["task_audit"]   # night-tasks 2026-11-23: one report runner (tools/task_audit.py, pc_report's 5-min gap)
AREAS["pc"].append("brain_feed")    # day-brain-feed 2026-11-24: the Brain app feed on the PC report (engine/brain_feed.py, ext block bf)
AREAS["pc"] += ["arm_report", "arm_rt"]   # day-armfix 2026-11-22 + red team 2026-11-23: START summary, ATLAS funded rename (keeps every number)
AREAS["pc"] += ["nt_socket", "le_bridge_cs"]   # big-execution 2026-11-26: socket order bridge prototype (paper only; engine/nt_socket.py + ninjatrader/LE_Bridge.cs)
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
AREAS["agency"].append("postcards")       # day-a11y 2026-11-20: personalised postcards (tools/postcards.py, tools/bat/POSTCARD_SETUP.bat), a fake Lob   # day-a11y 2026-11-20: the PC email autopilot (agency/autopilot/, tools/bat/EMAIL_SETUP.bat), fake Gmail, never the network   # day-a11y 2026-11-20: the Website Factory outreach + close kit (agency/outreach/)
AREAS["agency"].append("web_portal")      # day-a11y 2026-11-21: the CALLER PORTAL (agency/portal/ + agency/portal.py): the human cold caller's list, rules, log
AREAS["agency"].append("site_quality")    # day-a11y 2026-11-22: the 150 concept sites on the call sheet (names, trade, call link, 44 px, photos), the premium top 20
AREAS["trading"].append("panelfx")      # day-a11y 2026-11-20: the effects layer on Trading / Business / Planner (trading/panelfx.js)   # day-web-offers 2026-11-20: Agency Offers (agency/offers/): packages, proposal, terms, invoices + retainers, goal
AREAS["pc"].append("obsidian_brain")    # night-obsidian 2026-11-20: ZEUS Brain, the generated Obsidian vault (tools/obsidian_brain.py, vault/); its own line
AREAS["pc"].append("tickrec_cs")       # day-ofprogram 2026-11-23: LE_TickRec.cs backfill (mcs + fake history server) + autopilot
AREAS["pc"].append("tickrec")          # day-orderflow 2026-11-23: read-only tick recorder (engine/tickrec.py, ninjatrader/LE_TickRec.cs, OFF)
AREAS["pc"].append("tickrec_auto_rt")   # red team 2026-11-23: no autopilot start 01:40-16:05 ET, study stopped before 02:00, an unfinished study never counts
AREAS["nq"].append("nq_live")           # day-livedash 2026-11-26: the NQ live screen (nq/live.html + livecore.js); its own line
AREAS["nq"].append("nq_home")           # night-nq-home 2026-11-27: Trading Home launcher tiles + PC Health page (nq/pchealth*); its own line
AREAS["nq"].append("lit_setups_learn")  # day-litlearn 2026-11-26: LIT learns from live (tools/lit_setups_learn.py, --nightly --litlearn); its own line
AREAS["nq"].append("why_page")          # night-anatomy 2026-11-18: why we win / lose (tools/win_loss_anatomy.py, tools/web_public/why/); its own line
AREAS["nq"].append("learn_night")       # night-learnloop 2026-11-19: ZEUS learned (engine/zeus_learn.py) + tools/learn_night.py + metals feed + speed; its own line
AREAS["nq"].append("forward_paper")     # big-forward 2026-11-26: tools/forward_paper.py (watched leads scored on new sessions); its own line
AREAS["nq"].append("nq_nav")            # night-nq-nav 2026-11-27: shared NQ dock + PC pill (nq/nqnav.js)
AREAS["nq"].append("nq_of")             # night-nq-of 2026-11-27: the order-flow room (nq/orderflow.*)
AREAS["nq"].append("nq_chart_pro")      # night-nq-chart 2026-11-27: chart levels / sweeps / honest age
AREAS["nq"].append("nq_live_trades")    # night-nq-live 2026-11-27: live trades page (nq/live.*)
AREAS["pc"].append("of_conflog")        # night-of-conflog 2026-11-27: per-trade order-flow confluence log (engine/of_conflog.py)
AREAS["pc"].append("missed_alarm")      # night-missedalarm 2026-11-27: one "not armed" line a day + ~$ size hint (engine/live_guard)
AREAS["pc"].append("atlas_armed")       # night-atlasarmed 2026-11-27: AccountB.info carries "armed" (readiness)
AREAS["nq"].append("december_plan")    # night-of-december 2026-11-27: tools/december_plan.py -> nq/december.json + docs/DECEMBER_PLAN.md
AREAS["nq"].append("of_ladder")         # night-of-ladder 2026-11-27: tools/of_ladder.py (order flow lane A gate ladder, research/evalplan/ladder.json)
AREAS["nq"].append("combo_50k")         # night-combolive 2026-11-19: ATLAS + Zlarior on ONE 50K (engine/combo50k.py, OFF) + its LiveBot parity replay
AREAS["pc"].append("learn_night")       # the same suite: the PC side (data pipe hook, status ext "zl", datafeed metals, the 15-minute report's imports)
AREAS["kalshi"].append("kalshi_adapt")  # night-kadapt 2026-11-19: the K8 weekly re-test (engine/kalshi_adapt.py, tools/kalshi_adapt.py); its own line
AREAS["money"].append("tax_ledger")   # day-batch7 2026-11-26: payouts + fees per account per month for the accountant (tools/tax_ledger.py)
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
AREAS["nq"] += ["faults"]; AREAS["pc"] += ["faults"]   # night-faults 2026-11-23: fault injection (feed file, order file, state files, lanes, disk, internet)
AREAS["pc"] += ["nq_live_reliability", "account_b_min_room"]   # the same suite (fast alarm, autoupdate flat, datafeed gaps) + ATLAS min_room CLI
AREAS["nq"].append("fill_cost")          # night-atlasfills 2026-11-20: "real slippage so far" per bot (tools/fill_cost.py + learn_night card)
AREAS["nq"].append("market_learn")       # day-marketlearn 2026-11-24: shared Market Learn (engine/market_learn.py, tools/market_learn_weekly.py); its own line
AREAS["nq"].append("batch5")             # day-batch5 2026-11-26: health bands + forecast shape
AREAS["nq"].append("ideamill")            # day-ideamill 2026-11-25: the idea mill (tools/ideamill.py, research/ideamill/grammar.py)
AREAS["nq"].append("nq_speed")            # night-nq-speed 2026-11-27: nq/nqfeed.js, the shared PC feed loader (one fetch, cache, cross-tab)
AREAS["nq"].append("goals_model"); AREAS["trading"].append("goals_model")   # night-nq-main 2026-11-27: ONE goals model (nq/goals_model.js)
AREAS["nq"].append("nq_plan")   # night-nq-main 2026-11-27: the battle plan + alert history (nq/plancore.js, plan.js)
AREAS["nq"].append("nq_brief")   # night-nq-main 2026-11-27: BRIEF ME (nq/briefcore.js, briefme.js) + SUNLIGHT MODE (nq/sun.css)
AREAS["nq"].append("nq_december")   # night-nq-main 2026-11-27: the December card (nq/decore.js, december.js; nq/december.json from tools/december_plan.py)
AREAS["nq"].append("nq_tour")   # night-nq-main 2026-11-27: the first-visit tour (nq/tour.js)
AREAS["nq"].append("nq_qa2")   # night-nq-main 2026-11-27: QA second sweep (dock row, London now, half-day sentence, replay fold, pillar Ready)
AREAS["nq"].append("atlas2")              # day-atlas2 2026-11-26: ATLAS v2 at real fills (research/atlas2/atlas2.py: switch, fixed scoring, gate)
AREAS["nq"].append("atlas_exec"); AREAS["pc"].append("atlas_exec")   # big-atlasfill 2026-11-26: ATLAS fast lane (engine/atlas_exec.py, OFF, Sim only)
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
AREAS["nq"] += ["combo_25k", "combo25_rt"]   # day-combo25 2026-11-23 + red team: ATLAS + Zlarior on the 25K #2 (OFF), parity replay, switch writer, keep-alive lane
AREAS["nq"].append("time_size")   # day-sbhalf 2026-11-25: ATLAS x0.5 outside SB hours on the Builder eval combo lanes (OFF)
AREAS["nq"] += ["alloc_cards", "lit25_replay"]   # day-alloc 2026-11-26: card 2 (lit25 --on phrase) + card 3 (atlas_from_et) + the lit25 Sim replay
PARTS["combo_25k"] = [("sep", ["--seg", "2026-09-02"]), ("oct", ["--seg", "2026-10-02"])]   # day-combo25: one eval segment each
AREAS["fleet"].append("rapid_launch")       # day-rapid 2026-11-20: Rapid EOD 25K launch check (tools/money/rapid25_launch.py)
AREAS["fleet"] += ["rapid_blitz", "rapid_blitz_rt"]     # day-rapidsize 2026-11-23 + red team: BLITZ on the Rapid EOD 25K eval (OFF until --blitz on + phrase)
AREAS["nq"].append("blitz_learn")      # day-blitz150 2026-11-24: BLITZ learns from its mistakes (research/blitz/learn.py; research + reporting only)
AREAS["nq"].append("blitz_learn_rt")   # red team 2026-11-23: a BLITZ fix needs >= 10 removed fresh trades (no pass on 3)
for _a in ("fleet", "pc"):                  # fix-trade 2026-11-21: an added Rapid / account armed by Start trading's phrase (engine/go.py)
    if "rapid_arm" not in AREAS[_a]:
        AREAS[_a].append("rapid_arm")
SLOW = {"olympus_shell", "fit_edge", "jarvis_hub", "phone_e2e", "olympus_kit", "olympus_themes", "olympus_render", "zenith_mode", "ui_polish", "datacity", "jarvis_home"}
SLOW.add("lit_live")   # night-reds 2026-11-22: the whole replay (9,923 intraday polls) takes ~15-25 min, so 900 s cut it off as "93 failed"; alone it is OK


AREAS["agency"].append("web_audit")         # day-web-audit 2026-11-20: tools/site_audit.py (prospect phone audit -> agency/audit/)


# Retired suites (lead 2026-11-23): never run by an area, always NAMED with the reason (never a silent skip)
RETIRED = {"live_dryrun": "the retired 'engine' model (live_model.json runs LIT): LIT's live loop = backtest is tests.test_lit_live"}


def suites_for(area: str) -> list:
    names = []
    for a in (AREAS if area == "all" else [area]):
        for n in AREAS[a]:
            if n not in names:
                names.append(n)
    out = [n for n in names if os.path.isfile(os.path.join(ROOT, "tests", f"test_{n}.py")) and n not in RETIRED]
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
AREAS["pc"].append("noleak")           # day-noleak 2026-11-26: only the owner's PC posts to the real phone channels (engine/pc_identity.py)
AREAS["privacy"].append("noleak")
AREAS["board"].append("noleak")
AREAS["pc"].append("noleak_rt"); AREAS["privacy"].append("noleak_rt")   # red team 2026-11-26: the real PC never goes dark (fail-open on Windows)
AREAS["pc"].append("guard2")           # day-guard2 2026-11-26: risk-distance alarms, signed status feed + key rotation, /today
AREAS["board"].append("guard2")
AREAS["privacy"].append("guard2")
AREAS["pc"].append("alert_drill")       # day-alerts 2026-11-21: end-to-end alert drill (telegram / ntfy / off set-ups)
AREAS["pc"].append("alerts_box")        # alerts-phone 2026-11-21: /alerts/ = ALERTS_SETUP Telegram from the phone (engine/alerts_box.py); its own line
AREAS["pc"].append("alerts_start_code")   # day-security3 2026-11-21: the /alerts/ page's one-time START code; its own line
AREAS["pc"].append("alert_map")         # night-notify 2026-11-22: every critical event has a zero-setup phone route (engine/alert_map.py), digest, de-dup
AREAS["pc"].append("alert_proof")       # night-alertproof 2026-11-23: every critical alert reaches the phone with zero setup, once per channel
AREAS["pc"].append("alertproof_rt")     # red team 2026-11-23: the readiness 'told' de-dupe never swallows a new clock episode
AREAS["pc"].append("payout_autopilot")   # night-payout 2026-11-22: payout ready after the close, the Builder #5 guard, the Rapid $10k day, TRADE_HOME P
AREAS["pc"].append("payfirst")           # night-payfirst 2026-11-23: ATLAS's first payout at MFFU's minimum (owner), then the normal plan
AREAS["pc"].append("payout_rt")         # red team 2026-11-23: the #5 guard per funded account, the count per account, #4 checks MFFU
AREAS["pc"].append("rapid50k_onboard")   # night-r50k 2026-11-23: buy the Rapid EOD 50K -> one tap, slot rapid2, keep-alive key rapid2, $165
AREAS["pc"].append("rules_watch")         # night-rulewatch 2026-11-23: MFFU help pages vs mffu_rules.json, daily, alert on a real change
AREAS["pc"].append("fleet_mgr")           # night-fleetmgr 2026-11-23: one alert per account change with the next money move (advice only), the Fleet line
AREAS["pc"].append("daily_brief")         # night-brief 2026-11-23: ONE 07:30 brief (<= 8 lines) + ONE evening message (digest merged)
AREAS["pc"].append("package_b")         # audit 2026-11-22 package B: every critical alarm reaches the phone
AREAS["pc"].append("notify_rt")         # red team 2026-11-23: no hourly update-alert storm, subscribe reminder, never blocks, ALERTS_OFF
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
AREAS["cities"].append("mind_brain")      # day-mind 2026-11-23: the 3D Strategy Brain (cities/mind/: a lobe per strategy, step chains, trade timelines)
AREAS["cities"].append("pillars")         # day-pillars 2026-11-24: the FOUR PILLARS page (pillars/), the Brain regroup, the Hub filter
AREAS["nq"].append("pillars")             # day-pillars 2026-11-24: the NQ page strip + header link
AREAS["nq"].append("brain_app")           # day-brain-app 2026-11-24: THE BRAIN (brain/: 6 regions, next trade, 3D chart, thinking, learning, today $)
AREAS["nq"].append("brain_learned")       # big-learnview 2026-11-26: brain/learned.html (What the bots learned: lessons, tests next, ideas on trial)
AREAS["nq"].append("nq_brain_mind")       # night-nq-brain 2026-11-27: the NQ Brain mind layer (nq/brainmind.js: thinking now, setup pipeline, ideas on trial, ...)
AREAS["nq"].append("replay")                # night 2026-11-27: the NQ Replay Theater (nq/replay.html + tools/build_replay.py)
AREAS["nq"].append("setup_score")         # big-setupscore 2026-11-26: engine/setup_score.py (LIT "similar setups" line, display only)
AREAS["pc"].append("tickrec_tiny")        # day-pillars 2026-11-24: engine.tickrec.tiny / write_tiny (the order-flow pillar line)
AREAS["pc"].append("ofready")             # day-ofready 2026-11-24: engine/ofsum.py day summaries + research/orderflow/of_battery.py (synthetic only)
AREAS["pc"].append("oflearn")             # day-oflearn 2026-11-26: DESIGN3 v3 features + nightly learner, proven on of_sim planted ticks (synthetic only, ~5 min)
AREAS["pc"].append("of_send")             # day-ofmax 2026-11-26: the owner's one order-flow line, rehearsed end to end (fake ntfy)
AREAS["pc"].append("of_asks")             # night-of-asks 2026-11-27: one order-flow ask a night across cloud sessions; the PC skips duplicates
AREAS["pc"].append("of_backfill")         # night-of-backfill 2026-11-27: the order-flow year by ntfy's own count (fake ntfy + fake git)
AREAS["pc"].append("of_paper")            # day-oflearn 2026-11-26: the Order Flow pillar PAPER bot (engine/of_paper.py; synthetic live CSVs, ~4 min)
AREAS["pc"].append("of_paper_rt")   # red team 2026-11-26: the paper child BELOW_NORMAL
AREAS["pc"].append("of_paper_e5")   # night-of-paperv2 2026-11-27: the E5 second fill (DESIGN_paper_v2.md)
AREAS["pc"].append("of_lane")             # night-of-lane 2026-11-27: the order-flow LANE on Sim101, OFF (engine/of_lane.py; fake NinjaTrader, ~6 min)
AREAS["pc"].append("of_lane_ready")       # night-of-lane-ready 2026-11-27: /oflane Telegram, the 09:20 runner, Sim102 -> Sim101 fallback, the card (fake TG / NT, ~5 s)
AREAS["pc"].append("blitz_paper")          # day-blitzready 2026-11-27: the BLITZ paper lane (never an order), paper = backtest, the kick, p4 BLITZ = paper (~30 s)
AREAS["pc"].append("of_lane_ready_rt")    # red team #34 2026-11-27: one runner (OS lock), no start from 16:00, never a real account, /oflane owner-only, Sim101 only when free (~10 s)
AREAS["pc"].append("of_monfix")           # night-of-monfix 2026-11-27: lane A prior day = last RTH file; Sunday evening joins the overnight
AREAS["pc"].append("of_daycap")            # night-of-daycap 2026-11-27: the lane's max_per_day entry cap (default 1 = the tested first-of-day book; ~4 min)
AREAS["pc"].append("payout_engine")       # big-payout 2026-11-26: read-only payout planner, /today, the Money tile
AREAS["pc"].append("today_merge_rt")   # red team 2026-11-26: one /today (guard2 + big-payout), key line last
AREAS["pc"].append("ofreal")              # big-ofreal 2026-11-26: tools/of_realday_verdict.py + tools/build_of_room.py (sim pulled days, ~1 min)
AREAS["pc"].append("ofpipe")              # big-ofpipe 2026-11-26: OF paper state PC -> cloud (ext "ofp" + the of answer) + oflive.setup_of
AREAS["cities"].append("research_hub2")   # night-hub2 2026-11-22: the Research Hub (cities/hub.html, data tools/build_research_hub.py); its own line
AREAS["cities"].append("strategy_lab")    # day-mind 2026-11-23: Strategy Lab data (tools/build_strategy_lab.py) + the Research Hub tab
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
        for n, why in RETIRED.items():
            print(f"RETIRED  {n}: {why}")
        return 0
    names = suites_for(a.area)
    for n, why in RETIRED.items():
        if a.only and n in a.only or a.area == "all":
            print(f"RETIRED {n}: {why} (python -X utf8 -m tests.test_{n} still runs it by hand)", flush=True)
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


# (night-cleanup 2026-11-22: these lines used to sit below the __main__ block, so run_area.py never ran them)
AREAS["agency"].append("pricebook")      # day-caller2 2026-11-21: one price book, checked everywhere (agency/pricebook.py --check)
AREAS["agency"].append("trade_scripts")   # day-caller2 2026-11-22: per-trade call scripts
AREAS["money"].append("money_pipeline")     # day-a11y 2026-11-22: the MONEY PIPELINE (business/pipeline.html + agency/pipeline.py) + the Corvette fund
AREAS["pc"] += ["clockfix"]        # 2026-11-22: FIX_CLOCK.bat + OlympusClock task + the schtasks fallback (engine/go.sync_clock, self_heal.fix_clock)
AREAS["nq"] += ["live_vs_bt"]   # night-livevsbt 2026-11-23: daily live vs backtest drift check (read-only), one phone line + one brief line
AREAS["nq"] += ["news_week"]   # night-newsweek 2026-11-23: Thanksgiving week calendar + exact blackout windows
AREAS["pc"] += ["bat_menu", "context_refresh"]   # night-cleanup 2026-11-22: TRADE_HOME = the one front door (tools/bat/), CBOE / GEX / 1d refresh
AREAS["pc"].append("bat_shortcuts")     # red team 2026-11-23: a shortcut to a moved .bat follows it to tools/bat (once a day, the 15-minute report)
AREAS["pc"] += ["zerotouch"]      # night-zerotouch 2026-11-22: START phrase = keep-alive consent, MONDAY_SETUP.bat, recovery matrix, NinjaTrader reopen
AREAS["pc"].append("zerotouch_rt")      # red team 2026-11-23: an old explicit keep-alive OFF sticks, NinjaTrader reopen back-off, no-console start
AREAS["pc"] += ["zerotouch2", "zerotouch2_rt"]   # day-zerotouch2 2026-11-24 + red team: auto-park, phone inbox (newest by time), PC checklist
AREAS["pc"].append("handsfree")
AREAS["pc"].append("ops2")   # day-ops2 2026-11-26: hands-free roll (LE_Feed shadow), OneDrive / clock in START, backup + restore sandbox   # day-handsfree 2026-11-25: Telegram commands, writers sandbox (git status stays clean), NinjaScript sync, reboot chain
AREAS["pc"].append("ops2_rt"); AREAS["pc"].append("le_feed_hub_rt")   # red team 2026-11-26: gappy shadow never verifies, backups disarmed, LE_FeedHub heartbeat
AREAS["pc"].append("zeroerr2")   # big-zeroerr2 2026-11-26: hang guard (a hung server restarted when flat in < 5 min), the sweep's clusters
AREAS["pc"].append("hang_guard_rt")   # red team 2026-11-26: every account flat, python-only kill, no restart loop
AREAS["pc"].append("flat_stuck_rt")   # red team #23: 30 h of 'not flat' = one 'update stuck' line naming the leftover file
AREAS["pc"].append("handsfree_rt")   # red team 2026-11-25: forwarded Telegram = no command, force-park receipt names strategy files
AREAS["nq"] += ["roll_dec_audit", "nt_roll_guard", "dec_roll", "roll"]   # night-roll 2026-11-23: the December roll (ROLL.md): audit with fakes + the three roll suites (were in no area)
AREAS["nq"].append("roll_rt")           # red team 2026-11-23: TRADE_HOME R reports what tools/bat/ROLL.bat found (exit 2 = not now)
AREAS["pc"] += ["post_update_check"]   # night-verify 2026-11-23: the read-only check after an update restart, one phone message
AREAS["nq"] += ["k7proof"]   # night-k7proof 2026-11-23: the 7-day keep-alive on all 4 MFFU accounts (calendars, Thanksgiving, PC off, consent, clock)
AREAS["nq"] += ["k7proof_rt"]   # red team night-k7proof: per-slot Rapid keys keep the START summary, phone clock and BLITZ-free lists right
AREAS["pc"] += ["monday", "mondaysim_rt"]   # night-mondaysim 2026-11-23 + red team: UPDATE.bat exit 0/1/2 read right (MONDAY, TRADE_HOME 7), START always runs
AREAS["pc"] += ["rollback_world"]   # night-rollback 2026-11-23: a bad landing rolls itself back (health / import / crash loop), temp git world
AREAS["pc"] += ["rollback_rt"]      # red team night-rollback: owner / 16:00 restarts never roll a good update back, no good/bad loop, never mid-trade

AREAS["pc"].append("faststart")   # night-faststart 2026-11-23: START BOT looks sooner and more often (same limits), on a fake clock
AREAS["pc"].append("faststart_rt")   # red team 2026-11-23: stop_server keeps its old limit on a slow-answering server; checklist only after the bot start
AREAS["pc"] += ["ship_vault"]   # night-reds2 2026-11-23: ship.py rebuilds + commits a stale generated vault/ before the push

AREAS["pc"].append("add_account")   # night-addacct 2026-11-23: TRADE_HOME 4 = Name -> guessed plan -> HELD -> paper check; ADD_ACCOUNT.bat 6 = Lucid

AREAS["pc_care"] = ["pc_care", "bat_menu", "fresh_start"]   # night-secps 2026-11-23: STATUS / PC_CARE / CLEAN_STORAGE run a site download only on a pinned sha256
AREAS["pc"] += ["startmsg"]   # night-startmsg 2026-11-23: START BOT's exit codes + its [FIX] reason in TRADE_HOME 2 / 8 and MONDAY SETUP
AREAS["nq"] += ["tgweek"]   # night-tgweek 2026-11-23: Thanksgiving week (calendar, update windows, 'half day, closes 13:15' wording)
AREAS["pc"] += ["k7cloud"]   # night-k7cloud 2026-11-23: the cloud warns 'PC looks off: <account> must trade by <date>' (tools/pc_silent_check.k7_step)
AREAS["pc"] += ["alert_test"]   # day-notify 2026-11-23: the cloud "Send me a test alert" (tools/alert_test.py) + its read-back receipt; fakes only

AREAS.setdefault("faults", [])
AREAS["faults"] += [x for x in ("state_safe", "multi_account") if x not in AREAS["faults"]]   # night-statesafe 2026-11-23: a damaged state file never means a clean day
AREAS["nq"].append("state_safe")
AREAS["faults"].append("state_safe_rt"); AREAS["nq"].append("state_safe_rt")   # red team: .bak is a copy (no false pause), a real loss lock replaces a damaged-state pause

AREAS["nq"].append("accounts_screen"); AREAS["pc"].append("accounts_screen")   # day-accounts 2026-11-23: nq/accounts.html (one card per account + 7-day clock) + the new Rapid's keep-alive end to end + cloud K7 fixes

AREAS["pc"].append("remote_notice")     # day-notifyfix 2026-11-23: a remote command's phone notice goes through every channel; its receipt rides the feed ("rc")
AREAS["nq"].append("chaos_live"); AREAS["pc"].append("chaos_live")   # day-zeroerr 2026-11-24: failure map chaos harness (engine/live_guard + fast_alarm stop_missing)
AREAS["pc"].append("live_guard_rt")   # red team 2026-11-24: an account the owner disabled never gets MISSED TRADE / NOT READY

AREAS["nq"].append("ledgerfix"); AREAS["pc"].append("ledgerfix")   # day-ledgerfix 2026-11-24: no order for an un-routed model entry of an ended session / a flat broker; no row before an account's eval start (+ repair); armed record
AREAS["nq"].append("ledgerfix_rt"); AREAS["pc"].append("ledgerfix_rt")   # red team 2026-11-24: a future eval_start never drops a held position's exit or today's real closes

AREAS["nq"].append("setup_progress"); AREAS["pc"].append("setup_progress")   # day-closer 2026-11-25: setup progress pushes (engine/setup_progress.py, read-only)
AREAS["nq"].append("setup_progress_rt"); AREAS["pc"].append("setup_progress_rt")   # red team 2026-11-25: no re-send on a moving EMA, ATLAS cap 8
AREAS["nq"].append("nt_transport_rt")   # red team 2026-11-26: a live account never gets the socket transport

AREAS["nq"].append("trade_cards"); AREAS["pc"].append("trade_cards")   # day-cards 2026-11-26: Telegram trade cards (chart PNG), 16:20 day summary, Friday week report
AREAS["nq"].append("trade_cards_rt"); AREAS["pc"].append("trade_cards_rt")   # red team 2026-11-26: long captions never cut, NT files only when needed
AREAS["pc"].append("buy_gate"); AREAS["money"].append("buy_gate")   # big-shadow 2026-11-26: shadow eval + buy gate (display only)
AREAS["pc"].append("buy_gate_rt")   # red team 2026-11-26: bg < 400 B, a damaged verdict shows nothing

AREAS["nq"].append("fill_log"); AREAS["pc"].append("fill_log")   # day-zeroerr 2026-11-26: every real fill (entry + exit, every lane) in fills.jsonl.gz, BLITZ paper rows, extra accounts in the day summary
AREAS["pc"].append("of_asks_rt")   # red team #29: one 'of' answer per answering night, bf never swallowed

if __name__ == "__main__":
    sys.exit(main())
AREAS["nq"].append("nq_accounts_night")   # night-nq-accounts 2026-11-27: premium account cards + business view (web only)
AREAS["nq"].append("vault_never_blank"); AREAS["olympus"].append("vault_never_blank")   # QA #3 night-nq-accounts: the payout vault is never a blank box
