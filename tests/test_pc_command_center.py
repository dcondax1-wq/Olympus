"""PC Command center upgrade (engine/pc_cc_api.py, web_next/js/next/cc.js): every /api/next/cc route on a fake PC bot
(tests/test_pcdash_api.fake_bot), the health lights (feed, NinjaTrader, clock, STARTUP RECONCILED / DISARMED, allowlist,
duplicate-process lock, heartbeat, kill, loop), the day (phase, early close, DST), the audit file guard, and that nothing
changes the bot or writes a file. Plus static checks of the SPA wiring (routes, sidebar groups, sections, keys).

  python -X utf8 -m tests.test_pc_command_center
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from engine import guards, pc_cc_api as C
from tests.test_pcdash_api import fake_bot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {str(detail)[:300]}"), flush=True)


def ts(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def light(rows, key):
    return next((r for r in rows if r["key"] == key), {})


def snapshot(b):
    return json.dumps({"ledger": b.ledger, "state": b.state, "running": b.running, "kill": b.kill,
                       "legs": getattr(b.adapter, "legs", None), "cfg": b.cfg}, default=str, sort_keys=True)


def api_checks(tmp):
    b, now = fake_bot(tmp)
    before = snapshot(b)
    files_before = sorted(os.listdir(tmp))
    app = FastAPI()
    app.include_router(C.router)
    old = C._bot
    C._bot = lambda: b
    try:
        cl = TestClient(app)
        r = cl.get("/api/next/cc/home")
        check("home: 200", r.status_code == 200, r.text[:200])
        d = r.json()
        L, A = d.get("lit") or {}, d.get("atlas") or {}
        check("home: LIT card balance / target / room / floor", L.get("balance") == 51327.2 and L.get("target_balance") == 53000.0
              and L.get("room") == 1977.2 and L.get("floor") == 49350.0, L)
        check("home: LIT session 2 of 10, today -$22.80, 1 trade today of 1", L.get("session") == 2 and L.get("sessions") == 10
              and L.get("today_pnl") == -22.8 and L.get("trades_today") == 1 and L.get("max_trades_day") == 1, L)
        check("home: LIT open position SHORT 8 with stop / target / BE trigger", (L.get("position") or {}).get("side") == "SHORT"
              and L["position"].get("qty") == 8 and L["position"].get("stop") == 25110.0 and L["position"].get("be_trigger") == 25029.5)
        check("home: LIT launch anchor 49,710.80 / 48,168.20", (L.get("launch_anchor") or {}).get("balance") == 49710.80
              and L["launch_anchor"]["floor"] == 48168.20 and round(L["launch_anchor"]["target_balance"] - L["launch_anchor"]["balance"], 2) == 3289.20)
        check("home: ATLAS not set up -> 25K defaults (target 26,500, floor 24,000, 2 trades a day)",
              A.get("configured") is False and A.get("target_balance") == 26500.0 and A.get("floor") == 24000.0 and A.get("max_trades_day") == 2, A)
        check("home: waiting sentence for a trade", "In a trade" in (d.get("waiting") or {}).get("say", ""), d.get("waiting"))
        keys = [x["key"] for x in d.get("lights") or []]
        check("home: 9 health lights", keys == ["feed", "nt", "clock", "startup", "allow", "lock", "heartbeat", "kill", "poll"], keys)
        check("home: feed + NinjaTrader + kill + loop green", all(light(d["lights"], k).get("ok") is True for k in ("feed", "nt", "kill", "poll")),
              d["lights"])
        check("home: allowlist red for an unlisted live account, fix = the allow command",
              light(d["lights"], "allow").get("ok") is False and "--allow-account" in light(d["lights"], "allow").get("fix", ""))
        check("home: the day block (phase, news, early close)", (d.get("day") or {}).get("phase", {}).get("code") == "window"
              and "news" in d["day"] and "early_close" in d["day"], d.get("day"))
        check("home: recent log rows", any("NOT routed" in (x.get("text") or "") for x in d.get("log") or []), d.get("log"))
        # the audit routes
        r = cl.get("/api/next/cc/handoff").json()
        check("handoff: lists the audit folder with README + the runbook", any(f["name"] == "README.md" for f in r["files"])
              and any(f["name"] == "STARTUP_AND_RECOVERY_RUNBOOK.md" for f in r["files"]) and "READY" in r.get("verdict", ""), r.get("verdict"))
        r = cl.get("/api/next/cc/doc", params={"name": "A5_execution.md"})
        check("doc: A5 has the EXECUTION_TEST_MATRIX", r.status_code == 200 and "EXECUTION_TEST_MATRIX" in r.json()["text"])
        bad = [n for n in ("../README.md", "/etc/passwd", "..%2FREADME.md", "../../live_model.json", "a1_intrabar.py", "../../../server.py")
               if cl.get("/api/next/cc/doc", params={"name": n}).status_code != 404]
        check("doc: no path outside the folder, no .py", not bad, bad)
        r = cl.get("/api/next/cc/setups").json()
        ids = {x["setup_id"] for x in r["rows"]}
        check("setups: EMA / MACD / NY reclaim + pooled, H1 and H2", {"ATLAS_LONDON_EMA", "ATLAS_MACD_SWEEP", "ATLAS_NY_RECLAIM"} <= ids
              and {"H1", "H2"} <= set(r["spans"]), (ids, r["spans"]))
        row = next(x for x in r["rows"] if x["setup_id"] == "ATLAS_LONDON_EMA" and x["span"] == "H1")
        check("setups: numbers parsed (London EMA H1 60 trades, PF 2.72)", row["trades"] == 60 and row["PF"] == 2.72, row)
        r = cl.get("/api/next/cc/atlas_trades", params={"year": "2026"}).json()
        check("atlas_trades: 2026 rows of one book", r["rows"] and all(str(x["day"]).startswith("2026") for x in r["rows"]) and r["book"] in r["books"])
        r = cl.get("/api/next/cc/runbook").json()
        em = [s for s in r["sections"] if s["emergency"]]
        check("runbook: EMERGENCY section apart, HOLD TO KILL in it", len(em) == 1 and "HOLD TO KILL" in em[0]["body"], [s["title"] for s in r["sections"]])
        check("runbook: commands extracted (--kill, --allow-account)", any("--kill" in c for c in r["commands"]) and any("--allow-account" in c for c in r["commands"]))
        r = cl.get("/api/next/cc/calendar", params={"days": 14}).json()["rows"]
        check("calendar: 14 weekdays", len(r) == 14 and all(dt.date.fromisoformat(x["day"]).weekday() < 5 for x in r))
        check("calendar: Monday 2026-11-02 is the first session after the clock change", any(x["day"] == "2026-11-02" and x["dst"] for x in r)
              and not any(x["dst"] for x in r if x["day"] != "2026-11-02"), [x for x in r if x["dst"]])
        r = cl.get("/api/next/cc/data_files").json()
        check("data_files: rows with names", r["rows"] and all("name" in x for x in r["rows"]))
        check("no route is a write (GET only)", all(m == {"GET"} for rt in C.router.routes for m in [set(rt.methods)]), [rt.path for rt in C.router.routes])
    finally:
        C._bot = old
    check("read-only: bot ledger / state / position / cfg unchanged", snapshot(b) == before)
    check("read-only: no file written in the bot folder", sorted(os.listdir(tmp)) == files_before, os.listdir(tmp))


def light_checks(tmp):
    b, now = fake_bot(tmp, stale=True)
    h = C._safe(lambda: __import__("engine.pcdash_api", fromlist=["x"]).status_view(b, now))["health"]
    L = C.lights(b, now, h)
    check("lights: stale feed -> red", light(L, "feed").get("ok") is False, light(L, "feed"))
    b, now = fake_bot(tmp, account="Sim101")
    h = __import__("engine.pcdash_api", fromlist=["x"]).status_view(b, now)["health"]
    check("lights: Sim101 never needs the allowlist", light(C.lights(b, now, h), "allow").get("ok") is True)
    b.health["startup"] = {"ok": False, "problems": ["bar feed not fresh (stale)"]}
    L = C.lights(b, now, h)
    check("lights: STARTUP DISARMED -> red with the reason", light(L, "startup").get("ok") is False and "bar feed not fresh" in light(L, "startup")["detail"])
    b._startup_ok = now
    check("lights: STARTUP RECONCILED -> green", "STARTUP RECONCILED" in light(C.lights(b, now, h), "startup").get("detail", "")
          and light(C.lights(b, now, h), "startup").get("ok") is True)
    b.adapter.disabled = "another bot process already trades account Sim101 (pid 42)"
    check("lights: duplicate-process lock -> red", light(C.lights(b, now, h), "lock").get("ok") is False)
    b.adapter.disabled = None
    b.adapter._lock_key = "x"
    check("lights: lock held -> green", light(C.lights(b, now, h), "lock").get("ok") is True)
    old = dict(guards._CLOCK)
    try:
        guards._CLOCK.update(drift=7.5, max=5.0)
        check("lights: clock 7.5 s off -> red", light(C.lights(b, now, h), "clock").get("ok") is False)
        guards._CLOCK.update(drift=0.4)
        check("lights: clock 0.4 s -> green", light(C.lights(b, now, h), "clock").get("ok") is True)
    finally:
        guards._CLOCK.clear()
        guards._CLOCK.update(old)
    b.kill = True
    check("lights: kill used -> red", light(C.lights(b, now, h), "kill").get("ok") is False)
    b.running, b.kill = False, False
    check("home: stopped bot -> waiting says stopped", "stopped" in C.home_view(b, now)["waiting"]["say"])
    # account B configured: the card reads AccountB.info()
    b.acct_b = SimpleNamespace(info=lambda now=None: {"label": "Account B", "account": "MFFU25K1", "plan_label": "MFFU Builder 25K", "kind": "SIM",
                                                      "enabled": True, "disabled": None, "keys": ["atlas"], "day_pnl": 120.0, "entries_today": 1,
                                                      "open": None, "locked": None, "routed": [{"t": now, "side": "exit", "pnl": 120.0}],
                                                      "eval": {"start_balance": 25000.0, "balance": 25420.0, "profit": 420.0, "target": 26500.0,
                                                               "to_target": 1080.0, "floor": 24520.0, "room": 900.0, "session": 3, "status": "open", "dll": 600.0}})
    A = C.home_view(b, now)["atlas"]
    check("home: ATLAS configured -> balance 25,420, progress 28%, 1 of 2 trades", A.get("configured") and A["balance"] == 25420.0
          and abs(A["progress"] - 0.28) < 1e-6 and A["trades_today"] == 1 and A["max_trades_day"] == 2, A)


def day_checks():
    p = C.phase(ts(2026, 10, 26, 9, 30))
    check("phase: Mon 09:30 = entry window, 360 min left", p["code"] == "window" and p["entries"] and p["min_left"] == 360, p)
    check("phase: 15:40 = manage only", C.phase(ts(2026, 10, 26, 15, 40))["code"] == "manage")
    check("phase: 17:30 = CME break", C.phase(ts(2026, 10, 26, 17, 30))["code"] == "break")
    check("phase: Saturday = weekend", C.phase(ts(2026, 10, 24, 12, 0))["code"] == "weekend")
    check("phase: Sunday 19:00 = evening session", C.phase(ts(2026, 10, 25, 19, 0))["code"] == "evening")
    d = C.dst_change(dt.date(2026, 10, 25))
    check("dst: 2026-11-01 fall back, 7 days ahead", d and d["date"] == "2026-11-01" and d["days"] == 7 and "fall back" in d["kind"], d)
    check("dst: none in mid-December", C.dst_change(dt.date(2026, 12, 10)) is None)
    check("dst: 2027-03-14 spring forward", (C.dst_change(dt.date(2027, 3, 10)) or {}).get("date") == "2027-03-14")
    check("day: Thanksgiving Friday 2026-11-27 early close 13:15", C.day_info("2026-11-27")["early_close"] == "13:15", C.day_info("2026-11-27"))
    check("day: Christmas 2026-12-25 closed", C.day_info("2026-12-25")["closed"] is True)


def static_checks():
    rd = lambda *p: open(os.path.join(ROOT, *p), encoding="utf-8").read()
    routes, shell, app, html, keys, cc = (rd("web_next", "js", "next", "routes.js"), rd("web_next", "js", "next", "shell.js"), rd("web_next", "js", "app.js"),
                                          rd("web_next", "index.html"), rd("web_next", "js", "next", "keys.js"), rd("web_next", "js", "next", "cc.js"))
    pages = ["cc", "goals", "evaltl", "sesscal", "tradelog", "atlassetups", "runbook", "audit", "features"]
    check("index.html: a section per new page + cc.css", all(f'id="page-{p}"' in html for p in pages) and "/css/cc.css" in html)
    check("app.js: cc pages registered, initCC, home = cc", "...ccPages" in app and "initCC()" in app and "store.get('page', 'cc')" in app)
    check("routes: Command center top-level, ATLAS kept, sidebar groups", "{ id: 'cc', label: 'Command center'" in routes and "{ id: 'atlas', label: 'ATLAS'" in routes
          and "export const GROUPS" in routes)
    # clean-up 2026-10-25 (layout deliberately changed): six main items, then one folded "Advanced" group with four sections
    grp = re.findall(r"label: '(\w+)', (?:ids|advanced)", routes)
    main = re.search(r"label: 'Main', ids: \[([^\]]*)\]", routes)
    check("routes: Main (6 items max) + Advanced (Accounts, Bot, Results, Help)", grp == ["Main", "Advanced", "Accounts", "Bot", "Results", "Help"]
          and main and len(re.findall(r"'[a-z]+'", main.group(1))) <= 6, grp)
    # 2026-10-25 PM: the LIT bot is "Zlarior": Main = Home · Zlarior · ATLAS · Results · All tools; each bot page has its sections
    # 2026-10-26: + Start (the Start & Accounts page, engine/start_api.py) after Home
    # 2026-10-28: Real results (real money only) takes the Main slot; the backtest page ("Backtest & research") is under Advanced > Results
    check("routes: Main = cc, start, zlarior, atlas, real, modules + BOTS sections", main and re.findall(r"'([a-z]+)'", main.group(1)) == ["cc", "start", "zlarior", "atlas", "real", "modules"]
          and "export const BOTS" in routes and "['Plan & levels'" in routes and "['Setups'" in routes and "if (page === 'zlarior'" in app, main and main.group(1))
    side = re.findall(r"'([a-z]+)'", routes[routes.index("export const GROUPS"):routes.index("export const NAV_NAMES")])
    check("routes: no page twice in the sidebar, Archive under Advanced", len(side) == len(set(side)) and "archive" in side and side.index("archive") > 5, side)
    ids = re.findall(r"'([a-z]+)'", routes[routes.index("export const GROUPS"):routes.index("export const TABS")])
    missing = [i for i in ids if i not in ("data", "zlarior") and f'id="page-{i}"' not in html]   # data / zlarior open their last sub-page
    check("routes: every sidebar id has a page section", not missing, missing)
    check("shell: grouped, foldable sidebar", "nx-grp-h" in shell and "navShut" in shell)
    check("keys: G then H = Command center, W = Runbook; no K kill shortcut", "['h', 'cc'" in keys and "['w', 'runbook'" in keys and "['k'," not in keys)
    m = re.search(r"FEATURE_COUNT", cc)
    blk = cc[cc.index("export const FEATURES"):cc.index("export const FEATURE_COUNT")]
    n = len(re.findall(r"\['[^']+', '[^']*'\]", blk))
    check("All features: 40+ new features listed", m and n >= 40, n)
    bad = [w for w in ("/api/live/start", "/api/live/stop", "/api/live/kill", "method: 'POST'", "method:'POST'", "botctl/start", "flatten") if w in cc]
    check("cc.js: no call that starts, stops, kills or flattens", not bad, bad)
    src = rd("engine", "pc_cc_api.py")
    check("pc_cc_api: no order / sizing / write path", not any(x in src for x in ("place_order", "import sizing", "allow_account(", "set_anchor", '"w"', "'w'",
                                                                                "kill_switch(", "flatten", ".start(", ".stop(")))
    node = "node"
    try:
        r = subprocess.run([node, "--input-type=module", "--check"], input=cc, capture_output=True, text=True, timeout=30)
        check("node --check cc.js", r.returncode == 0, r.stderr)
    except FileNotFoundError:
        check("node available (skipped)", True)


def main():
    tmp = tempfile.mkdtemp(prefix="le_cc_")
    api_checks(tmp)
    light_checks(tempfile.mkdtemp(prefix="le_cc2_"))
    day_checks()
    static_checks()
    print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} passed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
