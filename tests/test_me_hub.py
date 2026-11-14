"""The Me hub (team ME1, 2026-11-14, docs/ME_HUB.md): hub/?h=me, the owner's one organized place for personal life (money, cards, health, home & WiFi,
freedom, dates, car, streaks). PC tools tools/me_*.py -> data/me/ (PRIVATE, served only by engine/live_site.py /site/me/) -> hub/me.js on the phone.

  a. static: the files, the hub in the catalog / home / hub page / gate-nav, ES5 + text-only DOM + read only in me.js, colours only through the AGORA
     tokens, the PC report hook, the doc (at most 3 owner steps per connection), the private folder in .gitignore
  b. the inbox: POST /inbox/health is strict (good posts kept, bad ones refused with a plain reason), and appends one line only
  c. private: /site/me/ serves data/me only (never a site folder), the public build and the publishers never carry it, no card number anywhere
  d. cards: use % per card and in total, the 30% / 10% words, due and statement dates (short months), interest, the 5-day / 1-day reminders
  e. health: the fixture export.xml (streamed, zip, entities refused, no double count, sleep union, rings, workouts), speed, the inbox merge,
     trends, "recovered?", the Jarvis lines
  f. home: the arp / gateway / vendor parsers, the speed-test parser and a fake speed test, outages, a new device, the disk, no full MAC on the phone
  g. life: freedom, dates, car, streaks
  h. the hub file: tiles + sections, empty = how to connect, the money-left math, the reminders (quiet hours, once each), the PC-report hook run
  i. node: the catalog's Me hub, the home line, me.js view() with / without / with a broken file, the connect lines equal to the PC's
  j. Chromium 390 x 844 (under the shared browser lock): the hub with and without data, one tap opens a card, Home > Me, the home's Me tile line,
     the search finds it, Mix gives it its own look, 375 x 667 reduced motion; taps >= 44 px, no sideways scroll, Jarvis's corner free
    python -X utf8 -m tests.test_me_hub            (--static: a-i only; screenshots with AGORA_SHOTS=<dir>)
"""
from __future__ import annotations

import atexit
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
ROOT = AK.ROOT
WEB = AK.WEB
FIX = os.path.join(ROOT, "tests", "fixtures", "me_health", "export.xml")
NOW = int(dt.datetime(2026, 11, 14, 15, 0, tzinfo=dt.timezone.utc).timestamp())      # Saturday 10:00 New York
NOW_ISO = "2026-11-14T15:00:00Z"
TODAY = "2026-11-14"
TMP = tempfile.mkdtemp(prefix="me-hub-test-")
atexit.register(shutil.rmtree, TMP, True)        # also when tests.gate_static imports this module


def env_for(name: str) -> dict:
    """a private home + data folder of its own for one part (never the real %USERPROFILE%\\.olympus or data/)"""
    base = os.path.join(TMP, name)
    os.makedirs(base, exist_ok=True)
    return {"OLYMPUS_HOME": os.path.join(base, "home"), "LE_ME_DIR": os.path.join(base, "me"), "LE_INBOX_DIR": os.path.join(base, "inbox"),
            "LE_DAY_DIR": os.path.join(base, "day"), "LE_MONEY_OUT": os.path.join(base, "money_out"), "LE_PR_NO_NET": "1", "USERPROFILE": base}


def strip_comments(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)^\s*//[^\n]*|\s//\s[^\n]*", "", js)


def no_colour_literals(css):
    body = re.sub(r":where\(:root\)\s*\{.*?\n\}", "", css, flags=re.S)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d", body)


# ------------------------------------------------------------------------------------------------ the shared test data
def household():
    """a real household.json made by tools/money_import.py from two small made-up exports (Jul..Nov 2026)"""
    from tools import money_import as MI
    rows = []
    for m in ("2026-07", "2026-08", "2026-09", "2026-10", "2026-11"):
        rows += [(m + "-01", 2150.0, "ACME CORP PAYROLL", "bank"), (m + "-01", -1450.0, "SUNSET APARTMENTS RENT", "bank"), (m + "-05", -11.99, "SPOTIFY USA", "card"),
                 (m + "-09", -30.0, "DOORDASH ORDER", "card")]
        if m != "2026-11":
            rows += [(m + "-15", 2150.0, "ACME CORP PAYROLL", "bank"), (m + "-12", -80.0, "KROGER", "card"), (m + "-20", -40.0, "SHELL OIL", "card"),
                     (m + "-18", -91.80, "MYFUNDEDFUTURES.COM", "card")]
    rows += [("2026-09-10", 600.0, "MYFUNDEDFUTURES PAYOUT", "bank"), ("2026-10-10", 900.0, "MYFUNDEDFUTURES PAYOUT", "bank"), ("2026-11-10", 1200.0, "MYFUNDEDFUTURES PAYOUT", "bank")]
    card = ["Transaction Date,Post Date,Description,Category,Type,Amount,Memo"]
    bank = ["Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #"]
    for date, amt, desc, f in sorted(rows, reverse=True):
        mdy = f"{date[5:7]}/{date[8:10]}/{date[:4]}"
        if f == "card":
            card.append(f'{mdy},{mdy},"{desc}",,{"Payment" if amt > 0 else "Sale"},{amt:.2f},')
        else:
            bank.append(f'{"CREDIT" if amt > 0 else "DEBIT"},{mdy},"{desc}",{amt:.2f},ACH,1000.00,,')
    d = os.path.join(TMP, "bank")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "card.csv"), "w", encoding="utf-8", newline="") as fh:
        fh.write("\r\n".join(card) + "\r\n")
    with open(os.path.join(d, "bank.csv"), "w", encoding="utf-8", newline="") as fh:
        fh.write("\r\n".join(bank) + "\r\n")
    led = MI.empty_ledger()
    MI.import_paths(led, [os.path.join(d, "card.csv"), os.path.join(d, "bank.csv")], TODAY)
    return MI.build(led, MI.DEFAULT_RULES_DOC, TODAY, balances={"accounts": [{"name": "Checking", "kind": "cash", "usd": 2500}, {"name": "Savings", "kind": "savings", "usd": 6000},
                                                                             {"name": "Chase Freedom", "kind": "debt", "usd": 1100}]}, kalshi=None, history=[])


def inbox_days(n=20):
    from tools import me_core as M
    out = {}
    for i in range(n):
        day = M.add_days(TODAY, -i)
        out[day] = {"date": day, "steps": 7000 + 300 * (i % 5), "active_kcal": 480 + 10 * i, "exercise_min": 25 + i % 10, "stand_h": 10 + i % 3, "rhr": 58 + (i % 3),
                    "hrv_ms": 45 + (i % 4), "sleep_h": 6.8 + 0.1 * (i % 6), "t": NOW - i * 86400}
    return out


def cards_doc():
    from tools import me_cards as C
    return {"cards": [C.validate({"nick": "Chase Freedom", "limit": 5000, "balance": 1200, "statement_day": 3, "due_day": 19, "apr": 24.99, "autopay": "yes"}, TODAY)[0],
                      C.validate({"nick": "Gas card", "limit": 1500, "balance": 900, "statement_day": 20, "due_day": 15, "apr": 29.9, "autopay": "no"}, TODAY)[0]]}


def home_doc():
    from tools import me_home as HM
    st, _ = HM.update({}, NOW - 7200, online=True, found={"ip": "192.168.1.23", "gateway": "192.168.1.1", "devices": [{"ip": "192.168.1.1", "mac": "a0:b1:c2:d3:e4:f5"},
                                                                                                                            {"ip": "192.168.1.40", "mac": "f0:18:98:12:34:56"}]})
    st["seeded_t"] = NOW - 7200
    st, ev = HM.update(st, NOW - 3600, online=True, found={"ip": "192.168.1.23", "gateway": "192.168.1.1", "devices": [{"ip": "192.168.1.1", "mac": "a0:b1:c2:d3:e4:f5"},
                       {"ip": "192.168.1.40", "mac": "f0:18:98:12:34:56"}, {"ip": "192.168.1.57", "mac": "24:0a:c4:11:22:33"}]},
                       speed={"ok": True, "down_mbps": 412.0, "up_mbps": 38.0, "ping_ms": 14.0, "jitter_ms": 1.2, "colo": "EWR", "mb_used": 30.0},
                       pc={"name": "PC", "disk_total_gb": 480.0, "disk_free_gb": 120.5, "disk_free_pct": 25.1, "uptime_h": 50.0, "boot_t": NOW - 180000, "cpu_temp_c": None, "mem_used_pct": 40})
    return HM.build(st, NOW, {"names": {"a0:b1:c2:d3:e4:f5": "Router upstairs"}, "ignore": []}), ev


def full_inputs():
    from tools import me_health, me_life
    H = household()
    hd, _ = home_doc()
    return {"household": H, "cards": cards_doc(), "cards_t": NOW - 86400, "health": me_health.build(inbox_days(), {}, dict(me_health.GOALS_DEFAULT), NOW),
            "home": hd, "day": {"kind": "olympus-day", "t": NOW - 900, "events": [{"day": "2026-11-17", "start": "15:00", "title": "Dentist appointment", "work": False},
                                                                               {"day": "2026-11-16", "start": "09:00", "title": "Work shift", "work": True}],
                                "days": {"2026-11-22": {"all_day": ["Sam's birthday"]}}, "week": {"pay": {"month_usd": 3200}}},
            "dates": {"dates": [me_life.parse_date_arg("Mom's birthday=11-20")[0]]}, "dates_t": NOW - 1000,
            "car": {"name": "Civic", "readings": [{"day": "2026-10-01", "miles": 47000}, {"day": "2026-11-01", "miles": 48000}], "oil": {"last_miles": 43200, "last_day": "2026-08-01"},
                    "dates": {"registration": "2026-11-25"}}, "car_t": NOW, "freedom": {}, "agency": 800.0}


# ------------------------------------------------------------------------------------------------ a. static
def test_static():
    files = ["tools/me_core.py", "tools/me_cards.py", "tools/me_health.py", "tools/me_home.py", "tools/me_life.py", "tools/me_hub.py", "tools/me_oui.json",
             "tools/web_public/hub/me.js", "tools/web_public/hub/me.css", "docs/ME_HUB.md", "tests/fixtures/me_health/export.xml"]
    check("a. the files: tools/me_core / me_cards / me_health / me_home / me_life / me_hub, the vendor table, hub/me.js + me.css, docs/ME_HUB.md, the fixture export",
          all(os.path.isfile(os.path.join(ROOT, f)) for f in files), [f for f in files if not os.path.isfile(os.path.join(ROOT, f))])
    js, css = AK.read(os.path.join(WEB, "hub", "me.js")), AK.read(os.path.join(WEB, "hub", "me.css"))
    hub_html, hub_js = AK.read(os.path.join(WEB, "hub", "index.html")), AK.read(os.path.join(WEB, "hub", "hub.js"))
    gate_html, gate_js = AK.read(os.path.join(WEB, "gate", "index.html")), AK.read(os.path.join(WEB, "gate", "gate.js"))
    cat, hs, nav = (AK.read(os.path.join(WEB, "olympus", n)) for n in ("gate-catalog.js", "hub-status.js", "gate-nav.js"))
    code = strip_comments(js)
    es6 = [p for p in (r"=>", r"\blet\s", r"\bconst\s", r"`", r"\bclass\s+\w+\s*[{e]", r"\.\.\.\w", r"\.at\(", r"\(\?<[=!]") if re.search(p, code)]
    check("a. hub/me.js is an ES5 classic script (Safari 12+ safe, no build step)", not es6, es6)
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function") if re.search(p, js)]
    check("a. me.js: no markup from data (textContent only; a bar is a width in %)", not bad and "textContent" in js and "style.width = p + '%'" in js, bad)
    check("a. me.js is read only: no XHR / WebSocket / beacon / POST / cookie / storage / web address; it fetches me/me.json and nothing else",
          not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|method:\s*['\"]POST|document\.cookie|localStorage|sessionStorage|indexedDB|https?://", strip_comments(js))
          and set(re.findall(r"getJSON\(([^)]*)\)", js)) == {"url", "base + 'me/me.json'"} and "g.fetch(url + '?t='" in js, re.findall(r"getJSON\(([^)]*)\)", js))
    lit = no_colour_literals(css)
    check("a. me.css: colours only through the AGORA tokens (no #hex, no rgb() literal), serif titles, tabular numbers, no neon / glow / techno font",
          not lit and "var(--ag-serif)" in css and "tabular-nums" in css and not AK.BANNED_LOOK.search(css + js) and ".me-" in css, lit)
    check("a. me.css: taps >= 44 px (chips), 60 px card rows, reduced motion, LITE, the style-look layer; every rule is .me- (nothing else changes)",
          "min-height: 44px" in css and "min-height: 60px" in css and "prefers-reduced-motion: reduce" in css and 'data-oly-lite="1"' in css and "html[data-oly-style]" in css
          and all(sel.strip().startswith(("@", "html", ".me-", "}")) or not sel.strip() for sel in re.findall(r"(?m)^([^{}\n]+)\{", re.sub(r"/\*.*?\*/", "", css, flags=re.S))))
    check("a. the hub page loads me.css after hub.css and me.js (deferred) before hub.js; a Me chip in the plain hub list",
          hub_html.index('href="hub.css?v=h1"') < hub_html.index('href="me.css?v=m1"') < hub_html.index("</head>")
          and hub_html.index('<script src="me.js?v=m1" defer></script>') < hub_html.index('<script src="hub.js?v=h2" defer></script>') and 'data-hub="me" href="index.html?h=me"' in hub_html)
    check("a. hub.js hands a PAGE hub (page: 'me') to OLYMPUS_ME_PAGE.mount (no tabs), with the Me icon",
          "if (H.page)" in hub_js and "MP.mount(panel, { base: base, now: nowS, hub: H, done:" in hub_js and "me: ['M20 6.5" in hub_js)
    check("a. the catalog: the hub 'me' (Me, its question, page 'me', 8 areas, no apps, legacy life for old themes), findHubs; the hub-status line meOf",
          "id: 'me', name: 'Me', q: 'How am I doing — money, health, home?'" in cat and "page: 'me'" in cat and "findHubs: findHubs" in cat
          and "function meOf(doc, t)" in hs and "case 'me':" in hs)
    check("a. the home: the Me tile (wide, second, a plain link to hub/?h=me), its line from the private me/me.json, its size ('8 areas') and the search finds page hubs",
          gate_html.index('data-hub="today"') < gate_html.index('class="g-hub g-wide" data-hub="me" data-to="hub/index.html?h=me"') < gate_html.index('data-hub="bots"')
          and "getJSON(base + 'me/me.json')" in gate_js and "H.size || plural(H.count, 'app')" in gate_js and "C.findHubs ? C.findHubs(q) : []" in gate_js and "ME: X.ME" in gate_js)
    check("a. gate-nav: Go to shows a hub's size (the Me hub: its areas, not '0 apps') and loads the catalog ?v=g3", "h.size || (h.count + ' apps')" in nav and "gate-catalog.js?v=g3" in nav)
    pr = AK.read(os.path.join(ROOT, "tools", "pc_report.py"))
    hook = pr[pr.index("def main("):]
    check("a. the PC report's 15-minute task calls me_hub.maybe_run softly (after calendar_sync, never on --dry-run, inside try)",
          re.search(r"try:\s+from tools import me_hub as _me\s+_me\.maybe_run\(", hook) is not None and hook.index("_cal.maybe_run(") < hook.index("_me.maybe_run(")
          and hook.index("if not a.dry_run:") < hook.index("_me.maybe_run("))
    gi = AK.read(os.path.join(ROOT, ".gitignore"))
    check("a. data/me/ (the phone files) is gitignored; the typed inputs live outside the repo (%USERPROFILE%\\.olympus\\me)", re.search(r"(?m)^data/me/$", gi) is not None)
    doc = AK.read(os.path.join(ROOT, "docs", "ME_HUB.md"))
    steps = re.findall(r"(?ms)^## (.+?)\n(.*?)(?=^## |\Z)", doc)
    owner = [(h, len(re.findall(r"(?m)^\d+\. ", b.split("\n### ")[0]))) for h, b in steps if h.lower().startswith(("connect", "your steps", "steps"))]
    check("a. docs/ME_HUB.md: a table, each connection's owner steps (at most 3), the Shortcut recipe, privacy, honest limits, wiring for the lead",
          "| What | Result |" in doc and len(owner) >= 5 and all(n <= 3 for _h, n in owner) and sum(n for _h, n in owner) >= 10 and "Health to PC" in doc and "/inbox/health" in doc and "Honest limits" in doc
          and "Wiring" in doc and "OTHER_APPS" in doc, owner)
    for name in ("me_core", "me_cards", "me_health", "me_home", "me_life", "me_hub"):
        src = AK.read(os.path.join(ROOT, "tools", name + ".py"))
        if re.search(r"web_public|pc_publish|live_site/site|money_publish", strip_py_comments(src)) or re.search(r"\b(ninjatrader|lit_live|live_model|place_order|arm_live)\b", src):
            check(f"a. {name}.py never writes into a site folder and never touches the bots", False, name)
            break
    else:
        check("a. the Me tools never name a site folder or a publisher, and never touch the bots (no ninjatrader / lit_live / live_model / order)", True)


def strip_py_comments(src):
    src = re.sub(r'(?s)"""(.*?)"""', "", src)
    return re.sub(r"(?m)#.*$", "", src)


# ------------------------------------------------------------------------------------------------ b. the inbox
def test_inbox():
    from engine import day_inbox as DI
    v = DI.validate_health
    good, why = v({"Date": TODAY, "Steps": "8,432", "active_energy": 512.4, "exercise": 34, "stand_hours": "11", "resting_hr": 58, "hrv": 46.25, "sleep": "7:12",
                   "weight_kg": 82, "workouts": [{"type": "Running", "min": 32, "mi": 3.1, "kcal": 310}]}, NOW)
    check("b. a good post: any letter case, plain aliases, '8,432', '7:12' sleep, kg -> lb, a workout in miles -> km; the date kept",
          good == {"date": TODAY, "steps": 8432, "active_kcal": 512, "exercise_min": 34, "stand_h": 11, "rhr": 58.0, "hrv_ms": 46.2, "sleep_h": 7.2, "weight_lb": 180.8,
                   "workouts": [{"type": "Running", "min": 32.0, "kcal": 310.0, "km": 5.0}]} and not why, (good, why))
    t2, _ = v({"steps": 9000, "sleep_h": ""}, NOW)
    check("b. no date = today in New York; an empty value = not sent", t2 == {"steps": 9000, "date": TODAY}, t2)
    t3, _ = v({"sleep_s": 25920}, NOW)
    t4 = v({"sleep_s": 7.2}, NOW)
    t5 = v({"sleep_min": "432", "sleep_s": 0}, NOW)
    check("b. sleep in seconds (the Shortcut's Duration) or minutes: 25,920 s = 7.2 h; 7.2 'seconds' (hours sent by mistake) refused, never stored as 0.002 h; sent twice refused",
          t3 == {"sleep_h": 7.2, "date": TODAY} and t4[0] is None and "too short" in t4[1] and t5[0] is None and "sent twice" in t5[1], (t3, t4, t5))
    cases = {"plain text": ("8432", "JSON object"), "a list": ([1, 2], "JSON object"), "unknown field": ({"steps": 1, "password": "x"}, "unknown field"),
             "out of range": ({"steps": -5}, "outside"), "too many steps": ({"steps": 999999}, "outside"), "a boolean": ({"steps": True}, "true / false"),
             "words": ({"rhr": "58 bpm"}, "not a number"), "an old date": ({"date": "2026-01-01", "steps": 3}, "last 10 days"), "a bad date": ({"date": "14/11/2026", "steps": 3}, "yyyy-MM-dd"),
             "a future date": ({"date": "2026-11-20", "steps": 3}, "last 10 days"), "nothing": ({"steps": ""}, "nothing to save"), "NaN": ({"steps": float("nan")}, "not a number"),
             "a script": ({"steps": "<script>"}, "not a number"), "a bad workout": ({"workouts": [{"type": "Run", "hack": 1}]}, "unknown field"),
             "13 workouts": ({"workouts": [{"type": "Run"}] * 13}, "12 at most"), "a nested object": ({"steps": {"a": 1}}, "send a number")}
    res = {k: v(b, NOW) for k, (b, _w) in cases.items()}
    bad = {k: r for k, r in res.items() if r[0] is not None or cases[k][1] not in r[1]}
    check(f"b. strict: {len(cases)} bad posts refused with a plain reason (plain text, unknown field, out of range, a boolean, words, dates, empty, NaN, markup, workouts)", not bad, bad)
    e = env_for("inbox")
    H = {"X-Olympus-Inbox": "1", "Content-Type": "application/json"}
    DI._HITS.clear()
    st0, _ = DI.accept("health", json.dumps({"steps": 8432}).encode(), "application/json", {"Content-Type": "application/json"}, now_s=NOW, env=e)
    st1, r1 = DI.accept("health", json.dumps({"date": TODAY, "steps": 8432, "sleep_h": 7.2, "exercise_min": 34}).encode(), "application/json", H, now_s=NOW, env=e)
    st2, r2 = DI.accept("health", json.dumps({"steps": "lots"}).encode(), "application/json", H, now_s=NOW + 1, env=e)
    st3, _ = DI.accept("health", b"x" * 3000, "application/json", H, now_s=NOW + 2, env=e)
    lines = open(os.path.join(e["LE_INBOX_DIR"], "health.jsonl"), encoding="utf-8").read().splitlines()
    files = sorted(os.path.relpath(os.path.join(dp, f), os.path.join(TMP, "inbox")) for dp, _dn, fn in os.walk(os.path.join(TMP, "inbox")) for f in fn)
    check("b. POST /inbox/health: no header 403; a good post 200 + its reply in plain words; a bad one 400 with the reason; over 2 KB 413",
          st0 == 403 and st1 == 200 and r1["said"] == "Saved your health for 2026-11-14: 8,432 steps, slept 7.2 h, 34 min exercise. The Me hub updates within 15 minutes."
          and st2 == 400 and "not a number" in r2["error"] and st3 == 413, (st0, st1, r1, st2, r2, st3))
    check("b. it appends ONE line to inbox/health.jsonl and writes nothing else", files == ["inbox/health.jsonl"] and len(lines) == 1 and json.loads(lines[0])["steps"] == 8432, (files, lines))
    check("b. the guard lets POST /inbox/health through only once install() ran (the same rule as /inbox/day)",
          "health" in DI.KINDS and DI.PATH_RX.match("/inbox/health") is not None and not DI.allowed("POST", "/inbox/health") or DI._S["installed"])
    DI._HITS.clear()


# ------------------------------------------------------------------------------------------------ c. private
def test_private():
    from engine import live_site as LS
    e = env_for("private")
    os.makedirs(e["LE_ME_DIR"], exist_ok=True)
    for n in ("me.json", "health.json", "home.json", "state.json"):
        with open(os.path.join(e["LE_ME_DIR"], n), "w", encoding="utf-8") as fh:
            json.dump({"kind": "x"}, fh)
    ok = [LS.me_file(n, e) for n in ("me.json", "health.json", "home.json")]
    no = [LS.me_file(n, e) for n in ("state.json", "../me.json", "me.json/../../x", "cards.json", "")]
    check("c. live_site.me_file: me.json, health.json, home.json from data/me only; state.json, a path trick or another name: never", all(ok) and not any(no), (ok, no))
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except ImportError as ex:
        check("c. fastapi is available", False, ex)
        return
    site = os.path.join(TMP, "private", "site")
    os.makedirs(os.path.join(site, "me"), exist_ok=True)
    with open(os.path.join(site, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html>")
    with open(os.path.join(site, "me", "cards.json"), "w", encoding="utf-8") as fh:
        json.dump({"leak": True}, fh)
    old = {k: os.environ.get(k) for k in ("LE_ME_DIR", "LE_SITE_DIR")}
    os.environ.update(LE_ME_DIR=e["LE_ME_DIR"], LE_SITE_DIR=site)
    try:
        app = FastAPI()
        LS.install(app)
        cl = TestClient(app)
        link = {"X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": "owner@example.com"}
        r1 = cl.get("/site/me/me.json", headers=link)
        r2 = cl.get("/site/me/cards.json", headers=link)
        r3 = cl.get("/site/me/state.json", headers=link)
        os.remove(os.path.join(e["LE_ME_DIR"], "health.json"))
        r4 = cl.get("/site/me/health.json", headers=link)
        r5 = cl.post("/site/me/me.json", headers=link)
        check("c. the PC's link: /site/me/me.json 200 (no-store) from data/me; a site folder's me/cards.json is NEVER served; state.json 404; a missing file 404 with how; POST 403",
              r1.status_code == 200 and r1.headers.get("cache-control") == "no-store" and r2.status_code == 404 and "leak" not in r2.text and r3.status_code == 404
              and r4.status_code == 404 and "docs/ME_HUB.md" in r4.json()["error"] and r5.status_code in (403, 405), (r1.status_code, r2.status_code, r2.text[:80], r3.status_code, r4.text[:120], r5.status_code))
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    bw = AK.read(os.path.join(ROOT, "tools", "build_web_dashboard.py"))
    pubs = "".join(AK.read(os.path.join(ROOT, "tools", n)) for n in ("pc_publish.py", "money_publish.py") if os.path.isfile(os.path.join(ROOT, "tools", n)))
    check("c. the public build and the publishers never carry the Me files: no data/me in build_web_dashboard / pc_publish / money_publish, no me/ folder in tools/web_public",
          "data/me" not in bw and '"data", "me"' not in bw and "data/me" not in pubs and '"data", "me"' not in pubs and not os.path.exists(os.path.join(WEB, "me")))
    from tools import money_publish as MP
    check("c. money_publish's KEEP (what the public site gets) has no household and no cards", "household" not in MP.KEEP and "cards" not in MP.KEEP)
    # no card number anywhere: the nickname rule, the phone file, the pushes, the repo's own new files
    from tools import me_cards as C
    refused = [C.validate({"nick": n, "limit": 1000, "due_day": 5}, TODAY)[1] for n in ("Visa 4111 1111 1111 1111", "Chase 1234", "Amex ending 0005", "x-9876", "4 2 4 2", "1234")]
    check("c. a nickname with a card number or a last 4 is refused (spaces, dashes and dots do not hide it)", all("no card number" in w for w in refused), refused)
    from tools import me_hub
    I = full_inputs()
    doc = me_hub.build(NOW, None, I)
    pushes = me_hub.reminders(I, TODAY)
    blob = json.dumps(doc) + json.dumps(pushes)
    pan = [m for m in re.findall(r"\d[\d -]{11,22}\d", blob) if luhn(re.sub(r"\D", "", m))]
    check("c. no card number in the phone file or the pushes: no Luhn-valid 13-19 digit run, no 4-digit run in a card name, no balance in a push",
          not pan and not any(re.search(r"\d{4}", c["nick"]) for c in I["cards"]["cards"]) and not any("$" in p["body"] for p in pushes if p["key"].startswith("card:")), pan[:3])
    new = ["tools/me_core.py", "tools/me_cards.py", "tools/me_health.py", "tools/me_home.py", "tools/me_life.py", "tools/me_hub.py", "tools/web_public/hub/me.js", "docs/ME_HUB.md"]
    leaks = [f for f in new if any(luhn(re.sub(r"\D", "", m)) for m in re.findall(r"(?<![\d.])\d[\d -]{11,22}\d(?![\d.])", AK.read(os.path.join(ROOT, f))))]
    check("c. the new files hold no card-number-like number", not leaks, leaks)
    from tools import me_core as M
    check("c. scrub: a long run of digits in a phone string is masked (an account number), amounts stay numbers",
          M.scrub_doc({"a": "ACH 123456789012", "b": 1234567890123, "c": ["$1,234", "2026-11-14"]}) == {"a": "ACH •••", "b": 1234567890123, "c": ["$1,234", "2026-11-14"]})


def luhn(s: str) -> bool:
    if not 13 <= len(s) <= 19:
        return False
    tot = 0
    for i, ch in enumerate(reversed(s)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        tot += d
    return tot % 10 == 0


# ------------------------------------------------------------------------------------------------ d. cards
def test_cards():
    from tools import me_cards as C
    from tools import me_core as M
    check("d. due dates: the next day of the month (today counts), a due day 31 is Nov 30 / Feb 28 / Feb 29 (leap), Dec rolls to Jan",
          [M.next_on_day("2026-11-14", 14), M.next_on_day("2026-11-14", 31), M.next_on_day("2027-02-01", 31), M.next_on_day("2028-02-10", 30), M.next_on_day("2026-12-20", 5),
           M.next_on_day("2026-11-14", 13)] == ["2026-11-14", "2026-11-30", "2027-02-28", "2028-02-29", "2027-01-05", "2026-12-13"])
    lv = [C.util_level(u)[0] for u in (0, 9.9, 10, 29.9, 30, 49.9, 50, 120)]
    check("d. the use words: under 10% best, under 30% fine (both ok), over 30% high (warn), over 50% very high (bad)", lv == ["ok", "ok", "ok", "ok", "warn", "warn", "bad", "bad"], lv)
    S = C.summary(cards_doc(), TODAY, [{"name": "Chase Freedom", "kind": "debt", "usd": 1100, "updated": "2026-11-12"}, {"name": "Checking", "kind": "cash", "usd": 2500}])
    cf, gc = S["cards"][0], S["cards"][1]
    check("d. per card: Chase Freedom $1,100 from the bank import (not the typed $1,200) of $5,000 = 22%; the Gas card typed $900 of $1,500 = 60% (very high)",
          cf["balance"] == 1100 and cf["balance_src"] == "your bank import" and cf["util"] == 22.0 and cf["lvl"] == "ok" and gc["balance"] == 900 and gc["util"] == 60.0 and gc["lvl"] == "bad", (cf, gc))
    check("d. in total: $2,000 of $6,500 = 30.8% (high); the next due is the Gas card on Sun Nov 15 (tomorrow)", S["balance"] == 2000 and S["limit"] == 6500 and S["util"] == 30.8
          and S["lvl"] == "warn" and S["next_due"]["nick"] == "Gas card" and S["next_due"]["due"] == "2026-11-15" and S["next_due"]["due_in"] == 1, S)
    check("d. interest if carried: $1,100 x 24.99% / 365 x 30 = $22.59 a month; $900 x 29.9% = $22.12; to report under 30% the Gas card needs $450 paid before its statement (Nov 20)",
          cf["interest_month"] == 22.59 and gc["interest_month"] == 22.12 and gc["pay_to_30"] == 450.0 and gc["statement"] == "2026-11-20" and C.interest_month(0, 24) == 0 and C.interest_month(500, None) == 0,
          (cf["interest_month"], gc["interest_month"], gc["pay_to_30"]))
    R = C.reminders(cards_doc(), TODAY)
    R2 = C.reminders(cards_doc(), "2026-11-18")
    check("d. reminders: the Gas card (due tomorrow) = the 1-day one, which retires its 5-day one; Chase (due in 5 days) = the 5-day one; on Nov 18 Chase's 1-day one",
          [(r["key"], r["also"]) for r in R] == [("card:" + cards_doc()["cards"][0]["id"] + ":2026-11-19:5", []), ("card:" + cards_doc()["cards"][1]["id"] + ":2026-11-15:1", ["card:" + cards_doc()["cards"][1]["id"] + ":2026-11-15:5"])]
          and [r["key"].split(":")[-1] for r in R2] == ["1"] and "Autopay is off" in R[1]["body"] and R[1]["priority"] == "high", [(r["key"], r["body"]) for r in R])
    sec = C.section(cards_doc(), TODAY, [], NOW)
    check("d. the Cards area: 3 cards (All cards used, Next due, Interest if carried) with their rows, the 30% / 10% words in the note",
          [c["id"] for c in sec["cards"]] == ["use", "due", "interest"] and "Under 30% is fine, under 10% is best" in sec["cards"][0]["note"] and len(sec["cards"][0]["rows"]) == 2, sec["cards"][0])
    e = env_for("cards")
    out = []
    rc = C.main(["--add", "--nick", "Discover", "--limit", "3000", "--due-day", "31", "--autopay", "y"], env=e, say=out.append, now_s=NOW)
    rc2 = C.main(["--add", "--nick", "Visa 4242", "--limit", "3000", "--due-day", "3"], env=e, say=out.append, now_s=NOW)
    answers = iter(["Gas card", "1500", "900", "20", "15", "29.9", "maybe", "n", ""])
    rc3 = C.main(["--add"], env=e, say=out.append, ask=lambda q: next(answers), now_s=NOW)
    rc4 = C.main(["--set", "gas card", "balance=300"], env=e, say=out.append, now_s=NOW)
    saved = M.read_json(os.path.join(e["OLYMPUS_HOME"], "me", "cards.json"))
    check("d. the CLI: --add with flags, a card number refused (exit 2), --add question by question (a bad 'maybe' asked again), --set; saved owner-only outside the repo",
          rc == 0 and rc2 == 2 and rc3 == 0 and rc4 == 0 and [c["nick"] for c in saved["cards"]] == ["Discover", "Gas card"] and saved["cards"][1]["balance"] == 300
          and "4242" not in json.dumps(saved) and (os.name == "nt" or (os.stat(os.path.join(e["OLYMPUS_HOME"], "me", "cards.json")).st_mode & 0o077) == 0), (rc, rc2, rc3, rc4, saved, out[-6:]))


# ------------------------------------------------------------------------------------------------ e. health
def test_health():
    from tools import me_health as MH
    from tools import me_core as M
    with open(FIX, "rb") as fh:
        R = MH.parse_export(fh, 400, TODAY)
    D = R["days"]
    check("e. the export: iPhone + Watch steps are not added up (5,000, the bigger source, not 9,200); Apple's ActivitySummary wins for the rings (512 kcal, 34 min, 11 h)",
          D["2026-11-10"]["steps"] == 5000 and D["2026-11-10"]["active_kcal"] == 512 and D["2026-11-10"]["exercise_min"] == 34 and D["2026-11-10"]["stand_h"] == 11, D["2026-11-10"])
    check("e. the export: kJ -> kcal (1,000 kJ = 239), stand hours counted from 'Stood' only (3 of 4), resting HR and HRV averaged (58, 45 ms)",
          D["2026-11-11"]["active_kcal"] == 239 and D["2026-11-11"]["stand_h"] == 3 and D["2026-11-10"]["rhr"] == 58 and D["2026-11-10"]["hrv_ms"] == 45.0, (D["2026-11-11"], D["2026-11-10"]))
    check("e. the export: sleep = the union of the asleep stages of every source (7.5 h, not 14; in bed and awake left out), deep 1.0 h, REM 1.0 h, on the wake-up day",
          D["2026-11-11"]["sleep_h"] == 7.5 and D["2026-11-11"]["sleep_deep_h"] == 1.0 and D["2026-11-11"]["sleep_rem_h"] == 1.0 and "sleep_h" not in D["2026-11-10"], D["2026-11-11"])
    check("e. the export: weight 82 kg = 180.8 lb; the run: 32.5 min, 310 kcal, 3.1 mi = 4.99 km (from WorkoutStatistics); Apple's ring goals (move 600, exercise 30, stand 12)",
          D["2026-11-12"]["weight_lb"] == 180.8 and D["2026-11-12"]["workouts"] == [{"type": "Run", "min": 32.5, "kcal": 310, "km": 4.99}] and R["goals"] == {"move": 600, "exercise": 30, "stand": 12}, (D["2026-11-12"], R["goals"]))
    check("e. the export: a 2024 record (older than 400 days) is skipped, not counted", "2024-01-01" not in D and R["first"] == "2026-11-10" and R["records"] == 24, (R["first"], R["records"]))
    bad = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]><HealthData>&b;</HealthData>'
    try:
        MH.parse_export(io.BytesIO(bad))
        refused = False
    except MH.Refused:
        refused = True
    check("e. a file that declares entities (a 'billion laughs' bomb) is refused, never expanded", refused)
    rows = "".join('<Record type="HKQuantityTypeIdentifierStepCount" sourceName="W" unit="count" startDate="2026-%02d-%02d 08:00:00 -0500" endDate="2026-%02d-%02d 08:10:00 -0500" value="%d"/>\n'
                   % (1 + i % 10, 1 + i % 28, 1 + i % 10, 1 + i % 28, i % 500) for i in range(100000))
    blob = ('<?xml version="1.0"?><HealthData locale="en_US">' + rows + "</HealthData>").encode()
    t0 = time.time()
    R2 = MH.parse_export(io.BytesIO(blob), 400, TODAY)
    took = time.time() - t0
    check(f"e. streamed and fast: 100,000 records ({len(blob) / 1e6:.0f} MB) in {took:.2f} s (under 4 s here)", took < 4.0 and R2["records"] == 100000, took)
    e = env_for("health")
    z = os.path.join(TMP, "health", "export.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(FIX, "apple_health_export/export.xml")
        zf.writestr("apple_health_export/export_cda.xml", "<ClinicalDocument/>" * 50000)
    out = []
    rc = MH.main(["--import", z], env=e, say=out.append, now_s=NOW)
    hist = M.read_json(os.path.join(e["OLYMPUS_HOME"], "me", "health_history.json"))
    files = sorted(os.listdir(os.path.join(e["OLYMPUS_HOME"], "me")))
    check("e. --import export.zip: the export.xml inside (not the bigger CDA file), its days kept as daily totals in the private health_history.json only",
          rc == 0 and hist and sorted(hist["days"]) == ["2026-11-10", "2026-11-11", "2026-11-12"] and files == ["health_history.json"] and "imported 3 days" in out[0], (rc, out[:2], files))
    os.makedirs(e["LE_INBOX_DIR"], exist_ok=True)
    with open(os.path.join(e["LE_INBOX_DIR"], "health.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "a", "kind": "health", "t": NOW - 3600, "date": "2026-11-12", "steps": 4000, "sleep_h": 6.0}) + "\n")
        fh.write(json.dumps({"id": "b", "kind": "health", "t": NOW - 60, "date": "2026-11-12", "steps": 9100}) + "\n")
        fh.write("not json\n")
    ib = MH.read_inbox(os.path.join(e["LE_INBOX_DIR"], "health.jsonl"))
    rows_m = MH.merged_rows(ib, hist["days"])
    check("e. the Shortcut's posts: the newest value of a field wins (9,100 steps), the others stay (6.0 h sleep); over the export's day (weight and the run kept)",
          ib["2026-11-12"]["steps"] == 9100 and ib["2026-11-12"]["sleep_h"] == 6.0 and rows_m["2026-11-12"]["weight_lb"] == 180.8 and rows_m["2026-11-12"]["steps"] == 9100
          and rows_m["2026-11-12"]["workouts"][0]["type"] == "Run", rows_m["2026-11-12"])
    doc = MH.build(inbox_days(), {}, dict(MH.GOALS_DEFAULT), NOW)
    tr = doc["trends"]
    check("e. health.json: today + rings-style goals (move, exercise, stand, steps, sleep), the week from Monday, 7 / 30-day trends, private",
          doc["kind"] == "olympus-health" and doc["private"] and [r["id"] for r in doc["today_rings"]] == ["move", "exercise", "stand", "steps", "sleep"]
          and doc["week"][0]["date"] == "2026-11-09" and doc["week"][0]["dow"] == "Mon" and doc["week"][6]["future"] and tr["steps"]["d7"] is not None and tr["rhr"]["d30"] is not None, doc["week"][:2])
    rec = doc["recovery"]
    check("e. recovered?: against your own 30-day normal (HRV 45 vs 46.6, resting HR 58 vs 59, slept 6.8 h < 7.5 - 1 -> 'Partly recovered'), not medical advice",
          rec["level"] == "warn" and rec["word"] == "Partly recovered" and "not medical advice" in rec["text"], rec)
    good = {d: {**r, "hrv_ms": 60.0, "rhr": 55.0, "sleep_h": 8.0} if d == TODAY else r for d, r in inbox_days().items()}
    low = {d: {**r, "hrv_ms": 30.0} if d == TODAY else r for d, r in inbox_days().items()}
    few = {d: r for d, r in inbox_days().items() if d >= M.add_days(TODAY, -3)}
    rr = [MH.recovery(MH.merged_rows(x, {}), TODAY, MH.GOALS_DEFAULT)["level"] for x in (good, low, few)]
    check("e. recovered?: high HRV + low resting HR + 8 h = Recovered (ok); HRV far under normal = Take it easy (bad); 4 days of data = not enough history ('')", rr == ["ok", "bad", ""], rr)
    J = doc["jarvis"]
    check("e. the Jarvis lines: 'Last night: 6.8 h asleep ...', 'This week (Monday to today): ... steps', and the recovered line",
          J["sleep"].startswith("Last night: 6.8 h asleep") and J["steps_week"].startswith("This week (Monday to today): 45,000 steps, about 7,500 a day") and J["recovered"] == rec["text"], J)
    empty = MH.build({}, {}, dict(MH.GOALS_DEFAULT), NOW)
    check("e. no data: status empty, the Jarvis lines say so (nothing invented)", empty["status"] == "empty" and "no sleep data yet" in empty["jarvis"]["sleep"] and "no steps" in empty["jarvis"]["steps_week"], empty["jarvis"])


# ------------------------------------------------------------------------------------------------ f. home
WIN_ARP = """
Interface: 192.168.1.23 --- 0x6
  Internet Address      Physical Address      Type
  192.168.1.1           a0-b1-c2-d3-e4-f5     dynamic
  192.168.1.40          f0-18-98-12-34-56     dynamic
  192.168.1.57          24-0a-c4-11-22-33     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static
  239.255.255.250       01-00-5e-7f-ff-fa     static
"""
LINUX_NEIGH = "192.168.1.1 dev eth0 lladdr a0:b1:c2:d3:e4:f5 REACHABLE\n192.168.1.9 dev eth0  FAILED\n10.0.0.5 dev wlan0 lladdr 5a:11:22:33:44:55 STALE\n8.8.8.8 dev x lladdr 00:11:22:33:44:56 STALE"
IPCONFIG = "Wireless LAN adapter Wi-Fi:\n   IPv4 Address. . . . . . . . . . . : 192.168.1.23\n   Default Gateway . . . . . . . . . : fe80::1%12\n                                       192.168.1.1\n"


class FakeResp:
    def __init__(self, body: bytes, timing: float, ray="8e2f3a1b2c3d4e5f-EWR"):
        self.body, self.h = io.BytesIO(body), {"Server-Timing": f"cfRequestDuration;dur={timing}", "CF-RAY": ray}

    def read(self, n=-1):
        return self.body.read() if n is None or n < 0 else self.body.read(n)

    def getheader(self, k):
        return self.h.get(k)


class FakeConn:
    """speed.cloudflare.com on a fake clock: 20 ms a round trip, 100 Mbps down, 20 Mbps up"""
    def __init__(self, clock):
        self.clock, self.last = clock, None

    def request(self, method, path, body=None, headers=None):
        n = int(re.search(r"bytes=(\d+)", path).group(1)) if "bytes=" in path else len(body or b"")
        self.last = (method, path, n)

    def getresponse(self):
        method, path, n = self.last
        rtt = 0.020
        self.clock[0] += rtt + (n * 8 / 100e6 if method == "GET" else n * 8 / 20e6)
        return FakeResp(b"0" * (n if method == "GET" else 0), 0.5)

    def close(self):
        pass


def test_home():
    from tools import me_home as HM
    devs = HM.parse_arp(WIN_ARP)
    check("f. arp -a (Windows): the 3 real neighbours; broadcast, multicast and static rows left out", devs == [{"ip": "192.168.1.1", "mac": "a0:b1:c2:d3:e4:f5"}, {"ip": "192.168.1.40", "mac": "f0:18:98:12:34:56"},
                                                                                                             {"ip": "192.168.1.57", "mac": "24:0a:c4:11:22:33"}], devs)
    check("f. ip neigh (Linux): REACHABLE / STALE kept, FAILED and a public address left out", HM.parse_arp(LINUX_NEIGH) == [{"ip": "192.168.1.1", "mac": "a0:b1:c2:d3:e4:f5"}, {"ip": "10.0.0.5", "mac": "5a:11:22:33:44:55"}],
          HM.parse_arp(LINUX_NEIGH))
    check("f. the router's address: ipconfig (the IPv4 one under an IPv6 one) and ip route", HM.parse_gateway(IPCONFIG) == "192.168.1.1" and HM.parse_gateway("default via 10.0.0.1 dev eth0") == "10.0.0.1"
          and HM.parse_gateway("nothing here") is None)
    v = [HM.vendor_of(m)[0] for m in ("f0:18:98:12:34:56", "24:0a:c4:11:22:33", "b8:27:eb:00:00:01", "5a:11:22:33:44:55", "00:11:22:33:44:55")]
    check("f. the offline vendor table: Apple, Espressif (a smart plug or bulb), Raspberry Pi, a private Wi-Fi address, an unknown maker", v == ["Apple", "Espressif", "Raspberry Pi", "Private address", "Unknown maker"], v)
    oui = json.load(open(os.path.join(ROOT, "tools", "me_oui.json"), encoding="utf-8"))
    check("f. tools/me_oui.json: from the IEEE list, the home vendors only (60+), under 120 KB", oui["source"].startswith("IEEE MA-L") and len(oui["vendors"]) >= 60
          and os.path.getsize(os.path.join(ROOT, "tools", "me_oui.json")) < 120_000)
    check("f. the speed-test parser: Server-Timing 'cfRequestDuration;dur=12.5' -> 12.5 ms, CF-RAY '...-EWR' -> EWR, 10 MB in 1.1 s less a 20 ms round trip -> 74.2 Mbps",
          HM.server_ms("cfRequestDuration;dur=12.5") == 12.5 and HM.server_ms(None) == 0 and HM.colo_of("8e2f3a1b2c3d4e5f-EWR") == "EWR"
          and HM.parse_result([80, 20, 22, 18, 21, 19], [(2_000_000, 0.3, 1), (10_000_000, 1.1, 2)], [(1_000_000, 0.5, 1)], "EWR")
          == {"ok": True, "ping_ms": 20, "jitter_ms": 2.8, "down_mbps": 74.2, "up_mbps": 16.7, "colo": "EWR", "mb_used": 13.0})
    clock = [0.0]
    res = HM.speed_test(lambda: FakeConn(clock), clock=lambda: clock[0])
    check("f. a fake speed test (100 Mbps down, 20 up, 20 ms): about 100 / 20 Mbps, ping 20 ms, sizes grown until one took a second (2 + 10 + 25 MB down, 1 + 4 MB up)",
          res["ok"] and 95 <= res["down_mbps"] <= 101 and 19 <= res["up_mbps"] <= 21 and res["ping_ms"] == 19.5 and res["colo"] == "EWR" and res["mb_used"] == 42.0, res)

    class Boom:
        def request(self, *a, **k):
            raise OSError("no network")
    check("f. a speed test that cannot connect says so and never raises", HM.speed_test(lambda: Boom()) == {"ok": False, "error": "OSError"})
    st, ev = HM.update({}, NOW - 7200, online=True, found={"ip": "192.168.1.23", "gateway": "192.168.1.1", "devices": devs[:2]})
    st, ev1 = HM.update(st, NOW - 6300, online=False)
    st, ev2 = HM.update(st, NOW - 5400, online=False)
    st, ev3 = HM.update(st, NOW - 4500, online=True)
    st, ev4 = HM.update(st, NOW - 3600, online=False)
    st, ev5 = HM.update(st, NOW - 2700, online=True)
    blips = [o["blip"] for o in HM.build(st, NOW)["outages"]["list"]]
    check("f. outages: down at two checks in a row (08:15, 08:30) and back at 08:45: one 'Internet back' push (about 30 min); down at one check only = 'a short drop', logged, not pushed",
          not ev and not ev1 and not ev2 and len(ev3) == 1 and ev3[0]["title"] == "Internet back" and "about 30 min (08:15 to 08:45 New York)" in ev3[0]["body"] and not ev4 and not ev5
          and len(st["outages"]) == 2 and blips == [True, False], (ev3, st["outages"], blips))
    st, evd = HM.update(st, NOW - 600, found={"ip": "192.168.1.23", "gateway": "192.168.1.1", "devices": devs})
    st, evd2 = HM.update(st, NOW - 300, found={"ip": "192.168.1.23", "gateway": "192.168.1.1", "devices": devs})
    check("f. a new device: the first scan only records what is there; a new one later = one push (vendor, never its MAC or IP), and only once",
          len(evd) == 1 and evd[0]["title"] == "New device on your Wi-Fi" and "Espressif" in evd[0]["body"] and "24:0a" not in evd[0]["body"] and "192.168" not in evd[0]["body"] and not evd2, evd)
    st, evp = HM.update(st, NOW, pc={"disk_free_pct": 4.0, "disk_free_gb": 19.0})
    check("f. the disk almost full (< 10% free): one push a day, the fix in plain words", len(evp) == 1 and "CLEAN_STORAGE.bat" in evp[0]["body"] and evp[0]["key"] == f"home:disk:{TODAY}", evp)
    st["seeded_t"] = NOW - 7200
    doc = HM.build(st, NOW, {"names": {"a0:b1:c2:d3:e4:f5": "Router upstairs"}, "ignore": []})
    blob = json.dumps(doc)
    D = {d["vendor"]: d for d in doc["devices"]["list"]}
    check("f. home.json: the devices with their vendor, your names, the new one flagged; only the last 2 bytes of a MAC (no full MAC), the router named",
          doc["kind"] == "olympus-home" and "f0:18:98:12:34:56" not in blob and "a0:b1:c2:d3:e4:f5" not in blob and D["Espressif"]["new"] and D["Espressif"]["mac_tail"] == "22:33"
          and any(d["name"] == "Router upstairs" for d in doc["devices"]["list"]) and doc["outages"]["week"] == 2, doc["devices"])
    check("f. the home status, worst first: down now = 'Internet down'; 2+ drops today; then a new device (warn)",
          doc["status"]["lvl"] == "warn" and doc["status"]["short"] == "2 drops today" and HM.build({**st, "outages": []}, NOW)["status"]["short"] == "New device"
          and HM.build({**st, "online": {"ok": False, "t": NOW, "since": NOW - 600}}, NOW)["status"]["short"] == "Internet down", doc["status"])
    e = env_for("home")
    calls = []
    fake_run = lambda args, timeout=10: (WIN_ARP if args[0] == "arp" else IPCONFIG if args[0] == "ipconfig" else "")  # noqa: E731
    pc = lambda env, temp: {"name": "PC", "disk_free_gb": 200.0, "disk_free_pct": 40.0, "disk_total_gb": 500.0, "uptime_h": 3.0, "cpu_temp_c": temp}  # noqa: E731
    d1, ev_a = HM.maybe_run(NOW, e, http=lambda u, timeout=6.0: calls.append(u) or 200, runner=fake_run, speed_fn=lambda: {"ok": True, "down_mbps": 300.0, "up_mbps": 30.0, "ping_ms": 12.0}, sweep=False, pc_fn=pc)
    d2, ev_b = HM.maybe_run(NOW + 900, e, http=lambda u, timeout=6.0: 200, runner=fake_run, speed_fn=lambda: (_ for _ in ()).throw(AssertionError("no test due")), sweep=False, pc_fn=pc)
    files = sorted(os.listdir(os.path.join(e["OLYMPUS_HOME"], "me"))) + sorted(os.listdir(e["LE_ME_DIR"]))
    check("f. maybe_run with fakes: the online check, the devices, a speed test only when 4 h passed, the PC; writes home_state.json (private) + home.json only",
          d1["internet"]["last"]["down_mbps"] == 300.0 and d2["devices"]["n"] >= 3 and calls[:1] == [HM.CHECK_URLS[0]] and files == ["home_state.json", "home.json"] and not ev_a, (files, calls[:2]))
    check("f. LE_ME_HOME=0 turns the home checks off", HM.maybe_run(NOW, {**e, "LE_ME_HOME": "0"}) == (None, []))


# ------------------------------------------------------------------------------------------------ g. life
def test_life():
    from tools import me_life as L
    H = household()
    F = L.freedom(H, {"week": {"pay": {"month_usd": 3200}}}, {}, 800.0)
    check("g. freedom: trading cash = payouts minus fees (the last 3 full months: -$92, +$508, +$808 = $408 a month) + the agency's $800 = $1,208 of a $3,200 paycheck (37.8%)",
          F["trading_3m"] == 408.2 and F["side"] == 1208.2 and F["paycheck"] == 3200 and F["paycheck_src"].startswith("your shifts") and F["cover_pct"] == 37.8, F)
    check("g. freedom: months to quit at the last months' pace (+$330 a month each month) = 7; savings $8,500 cover the gap for months",
          F["slope"] == 330.0 and F["months_to"] == 7 and F["liquid"] == 8500.0 and F["runway_months"] is not None, (F["slope"], F["months_to"], F["runway_months"]))
    F2 = L.freedom(H, None, {"paycheck_month": 1000}, 800.0)
    F3 = L.freedom(None, None, {}, None)
    check("g. freedom: side income above the paycheck = 'Now'; nothing to go on = not enough (the area says how to connect)",
          F2["months_to"] == 0 and F2["when"].startswith("Now") and not F3["has"] and L.freedom_section(F3)["state"] == "empty", (F2["when"], F3))
    check("g. agency MRR from data/agency/*.json (mrr, or the sum of clients[].mrr); no folder = None", agency_check(L))
    nxt = [L.next_of({"date": "11-20", "yearly": True}, TODAY), L.next_of({"date": "11-10", "yearly": True}, TODAY), L.next_of({"date": "02-29", "yearly": True}, "2026-03-01"),
           L.next_of({"date": "2026-12-01"}, TODAY)]
    check("g. a yearly date: this year's, or next year's once it passed; Feb 29 is Feb 28 in a normal year; a one-off stays", nxt == ["2026-11-20", "2027-11-10", "2027-02-28", "2026-12-01"], nxt)
    I = full_inputs()
    car = L.car_state(I["car"], TODAY)
    items = L.dates(I["dates"], I["day"], car["dates"], TODAY)
    check("g. dates: typed (Mom's birthday), the calendar's important ones (Dentist appointment, Sam's birthday; a work shift never), the car's registration, soonest first",
          [(x["name"], x["day"], x["src"]) for x in items] == [("Dentist appointment", "2026-11-17", "calendar"), ("Mom's birthday", "2026-11-20", "typed"), ("Sam's birthday", "2026-11-22", "calendar"),
                                                              ("Car registration", "2026-11-25", "car")], items)
    R = L.date_reminders(items)
    check("g. date reminders: a birthday 7 days and 1 day before (Mom's in 6 days: the 7-day one, 'A card or a gift?'), the rest 3 and 1 (the dentist in 3 days); the car's come from the car",
          [(r["key"].split(":")[-1], r["title"]) for r in R] == [("3", "Dentist appointment in 3 days"), ("7", "Mom's birthday in 6 days")] and "A card or a gift?" in R[1]["body"], R)
    check("g. car: miles now estimated from the readings (48,000 on Nov 1 + 13 days at 32.3 a day = 48,419), oil every 5,000 mi: last at 43,200 -> due now (by miles before Feb 1 by months)",
          car["miles_now"] == 48419 and car["oil"]["miles_left"] == -219 and car["oil"]["soon"] and car["oil"]["by_time_day"] == "2027-02-01" and car["per_month"] == 981, car)
    CR = L.car_reminders(car)
    check("g. car reminders: the oil change (due now) and the registration in 11 days (the 14-day one)", [r["key"].split(":")[1] for r in CR] == ["oil", CR[1]["key"].split(":")[1]] and CR[1]["key"].endswith(":14")
          and "due now" in CR[0]["body"], CR)
    one = L.car_state({"readings": [{"day": "2026-11-01", "miles": 10000}]}, TODAY)
    check("g. one reading: the pace is about the US average (1,000 mi a month), said so", one["per_month"] == 1000 and "US average" in one["pace_src"], one)
    hj = {"goals": {"steps": 8000, "move": 500, "exercise": 30, "stand": 12, "sleep": 7.5},
          "days": [{"date": d, "steps": s} for d, s in (("2026-11-08", 9000), ("2026-11-09", 3000), ("2026-11-10", 9000), ("2026-11-11", 9100), ("2026-11-12", 8800), ("2026-11-13", 8100), ("2026-11-14", 2000))]}
    S = L.streaks(hj, TODAY)
    check("g. streaks: steps over 8,000 four days in a row (Nov 10-13); today is not over, so its 2,000 does not break it; best 4", S == [{"id": "steps", "label": "Steps", "goal": 8000, "goal_words": "8,000+ steps",
                                                                                                                                   "current": 4, "best": 4, "today": False}], S)


def agency_check(L) -> bool:
    d = os.path.join(TMP, "agency")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "a.json"), "w", encoding="utf-8") as fh:
        json.dump({"mrr": 500}, fh)
    with open(os.path.join(d, "b.json"), "w", encoding="utf-8") as fh:
        json.dump({"clients": [{"mrr": 200}, {"mrr": 150.5}, {"name": "x"}]}, fh)
    return L.agency_mrr(d) == 850.5 and L.agency_mrr(os.path.join(TMP, "nope")) is None


# ------------------------------------------------------------------------------------------------ h. the hub file
def test_hub():
    from tools import me_hub
    I = full_inputs()
    doc = me_hub.build(NOW, None, I)
    T = {t["id"]: t for t in doc["tiles"]}
    check("h. me.json: 4 tiles in order (Money left this month, Health today, Home, Next important date), each with its source and the time of its data",
          [t["label"] for t in doc["tiles"]] == ["Money left this month", "Health today", "Home", "Next important date"] and all(t["src"] and t["t"] for t in doc["tiles"]), doc["tiles"])
    check("h. 8 areas in order, each a short card stack (at most 6), private", [s["id"] for s in doc["sections"]] == ["money", "cards", "health", "home", "freedom", "dates", "car", "streaks"]
          and all(s["state"] == "ok" and 1 <= len(s["cards"]) <= 6 for s in doc["sections"]) and doc["private"] and doc["kind"] == "olympus-me", [(s["id"], s["state"], len(s["cards"])) for s in doc["sections"]])
    H = I["household"]
    usual = max(H["avg3"]["in"], H["this_month"]["in"])
    still = sum(s["usd"] for s in H["subscriptions"]["items"] if s["active"] and TODAY < s["next"] <= "2026-11-30")
    left = usual - H["this_month"]["out"] - still
    check("h. Money left this month = your usual money in (the last 3 months) - spent so far - the charges still due this month",
          T["money"]["value"] == "$" + f"{round(left):,}" and T["money"]["lvl"] == "ok" and "of your usual" in T["money"]["sub"], (T["money"], usual, still))
    check("h. the other tiles: today's steps (Partly recovered), Home 'New device' (warn), the next important date (the dentist in 3 days)",
          T["health"]["value"] == "7,000 steps" and "Partly recovered" in T["health"]["sub"] and T["home"]["value"] == "New device" and T["home"]["lvl"] == "warn"
          and T["date"]["value"] == "Dentist appointment" and T["date"]["sub"] == "Tue Nov 17 · in 3 days", T)
    money = doc["sections"][0]
    check("h. Money: spending this month vs last by category (rent first), subscriptions with next dates, due in 14 days, net worth $7,400 (assets - the card debt)",
          [c["id"] for c in money["cards"]] == ["spend", "subs", "due", "networth"] and money["cards"][0]["rows"][0]["k"] == "Rent" and money["cards"][3]["value"] == "$7,400"
          and all(r["s"].startswith("next ") for r in money["cards"][1]["rows"]), [(c["title"], c["value"]) for c in money["cards"]])
    empty = me_hub.build(NOW, None, {"household": None, "cards": {"cards": []}, "health": None, "home": None, "day": None, "dates": {}, "car": {}, "freedom": {}, "agency": None})
    check("h. nothing connected: every tile 'Not connected' with the one line that connects it; every area empty with its line",
          all(t["empty"] and t["value"] in ("Not connected", "Not checked yet") and t["connect"] for t in empty["tiles"]) and all(s["state"] == "empty" and s["connect"] for s in empty["sections"])
          and not any(empty["connected"].values()), [(t["id"], t["value"]) for t in empty["tiles"]])
    old = dict(I["household"])
    old["data"] = {**old["data"], "last": "2026-10-20"}
    st = me_hub.build(NOW, None, {**I, "household": old})["sections"][0]
    check("h. a bank export 25 days old: the Money area says 'stale' and how to refresh it", st["state"] == "stale" and "25 days old" in st["stale_note"], st.get("stale_note"))
    e = env_for("hub")
    os.makedirs(os.path.join(e["OLYMPUS_HOME"]), exist_ok=True)
    with open(os.path.join(e["OLYMPUS_HOME"], "ntfy.json"), "w", encoding="utf-8") as fh:
        json.dump({"topic": "nq-test-topic-0000", "ntfy": "https://ntfy.example"}, fh)
    sent = []
    http = lambda method, url, body=None, headers=None, timeout=15: (sent.append((url, headers.get("Title"), body.decode())) or (200, "ok"))  # noqa: E731
    msgs = me_hub.reminders(I, TODAY)
    st1, n1 = me_hub.send(msgs, {}, NOW, e, http)
    st2, n2 = me_hub.send(msgs, st1, NOW + 900, e, http)
    check("h. the reminders go to the PC report's private topic, each once (a second run sends nothing); a 1-day card reminder retires its 5-day one",
          n1 == len(msgs) == 6 and n2 == 0 and all(u == "https://ntfy.example/nq-test-topic-0000" for u, _t, _b in sent)
          and any(k.endswith("2026-11-15:5") for k in st1["sent"]) and any("Card due tomorrow" == t for _u, t, _b in sent), (n1, n2, [t for _u, t, _b in sent]))
    check("h. reminders only 08:00-21:00 New York (not at 06:00 or 22:30)", me_hub.quiet_ok(NOW) and not me_hub.quiet_ok(NOW - 4 * 3600) and not me_hub.quiet_ok(NOW + 12.5 * 3600))
    # the hook as the PC report runs it: files from disk, no network (LE_PR_NO_NET=1), a dry run sends nothing
    os.makedirs(e["LE_MONEY_OUT"], exist_ok=True)
    with open(os.path.join(e["LE_MONEY_OUT"], "household.json"), "w", encoding="utf-8") as fh:
        json.dump(I["household"], fh)
    os.makedirs(os.path.join(e["OLYMPUS_HOME"], "me"), exist_ok=True)
    with open(os.path.join(e["OLYMPUS_HOME"], "me", "cards.json"), "w", encoding="utf-8") as fh:
        json.dump(cards_doc(), fh)
    said = []
    d = me_hub.maybe_run(NOW, e, say=said.append, http=http, dry=True)
    files = sorted(os.listdir(e["LE_ME_DIR"]))
    check("h. maybe_run (the PC report's hook): me.json + health.json written in data/me, the home checks skipped without the network, the pushes only printed on a dry run",
          d and d["tiles"][0]["value"] != "Not connected" and files == ["health.json", "me.json"] and any(s.startswith("  [dry] push: Card due") for s in said)
          and said[-1].startswith("  [OK]  Me hub: Money left this month:"), (files, said[-2:]))
    check("h. LE_ME=0 turns the hook off; a broken input never raises", me_hub.maybe_run(NOW, {**e, "LE_ME": "0"}) is None and me_hub.maybe_run(NOW, {**e, "LE_ME_DIR": "/proc/forbidden/x"}, say=lambda *_: None) is None)


# ------------------------------------------------------------------------------------------------ i. node
HARNESS = r"""
const C = require(process.argv[1]), HS = require(process.argv[2]), P = require(process.argv[3]), doc = JSON.parse(require('fs').readFileSync(process.argv[4], 'utf8')), t = Number(process.argv[5]);
const me = C.hub('me');
const out = {
  me: { id: me.id, name: me.name, q: me.q, page: me.page, count: me.count, size: me.size, areas: me.areas, see: me.see, legacy: me.legacy, layout: C.layout('me'), mix: me.id },
  order: C.hubs.map((h) => h.id), find: ['health', 'wifi', 'credit card', 'birthday', 'kalshi', 'sleep steps'].map((q) => C.findHubs(q).map((h) => h.id)),
  line: HS.hubLine('me', { ME: HS.meOf(doc, t) }), lineOld: HS.hubLine('me', { ME: HS.meOf(Object.assign({}, doc, { t: t - 3 * 86400 }), t) }), lineNone: HS.hubLine('me', { ME: HS.meOf(null, t) }),
  view: P.view(doc, t, me.areas), none: P.view(null, t, me.areas), broken: P.view({ kind: 'olympus-me', tiles: 'x', sections: 5 }, t, me.areas),
  junk: P.view({ kind: 'olympus-me', t: t, tiles: [{ id: 'money', value: '<b>x</b>', sub: 'a'.repeat(500), lvl: 'evil' }], sections: [{ id: 'money', state: 'ok', cards: [{ title: 'T', rows: [{ k: 'a', v: 'b', pct: 250 }] }] }] }, t, me.areas),
  connect: P.CONNECT
};
process.stdout.write(JSON.stringify(out));
"""


def test_node():
    exe = shutil.which("node")
    if not exe:
        check("i. node is available", True)
        return
    from tools import me_hub
    doc = me_hub.build(NOW, None, full_inputs())
    p = os.path.join(TMP, "me.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    r = subprocess.run([exe, "-e", HARNESS, os.path.join(WEB, "olympus", "gate-catalog.js"), os.path.join(WEB, "olympus", "hub-status.js"), os.path.join(WEB, "hub", "me.js"), p, str(NOW)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("i. the catalog, hub-status and me.js run in node", False, r.stderr[-800:])
        return
    O = json.loads(r.stdout)
    m = O["me"]
    check("i. the catalog: hub 'me' (Me, 'How am I doing — money, health, home?'), second after Today, a page hub with 8 areas and no apps ('8 areas'), no tabs, legacy life, see Oikos / Planner / Argo",
          m["name"] == "Me" and m["q"] == "How am I doing — money, health, home?" and m["page"] == "me" and m["count"] == 0 and m["size"] == "8 areas" and len(m["areas"]) == 8
          and m["layout"] == [] and m["legacy"] == "life" and m["see"] == ["oikos", "planner", "argo"] and O["order"][:2] == ["today", "me"], m)
    check("i. the search finds the Me hub by its words (health, wifi, credit card, birthday, 'sleep steps'), never for Kalshi", O["find"] == [["me"], ["me"], ["me"], ["me"], [], ["me"]], O["find"])
    check("i. the home's Me line: the 3 first tiles in short words with the worst level; 3 days old = the age and warn; no file = a plain line, no number",
          O["line"]["text"] == " · ".join(t["short"] for t in doc["tiles"][:3]) and O["line"]["text"].endswith(" left · 7,000 steps · New device") and O["line"]["lvl"] == "warn" and O["lineOld"]["text"].endswith("(3 d ago)") and O["lineOld"]["lvl"] == "warn"
          and O["lineNone"] == {"text": "Money, cards, health, home: on your PC link", "lvl": ""}, (O["line"], O["lineOld"]))
    V, N, B, J = O["view"], O["none"], O["broken"], O["junk"]
    check("i. me.js view(): 4 tiles with value, source and age ('Bank exports · 2 d ago'), 8 areas with their card stacks, '8 of 8 areas connected'",
          [t["id"] for t in V["tiles"]] == ["money", "health", "home", "date"] and V["tiles"][0]["src"] == "Bank exports" and V["tiles"][0]["age"] == "4 d ago"
          and V["tiles"][2]["age"] == "just now" and len(V["areas"]) == 8 and V["connected"] == 8 and V["has"] and not V["banner"] and len(V["areas"][0]["cards"]) == 4, V["tiles"])
    check("i. me.js view() without the file (the public site): the banner says to open it through the PC's link; every tile 'Not connected' + how; every area its connect line",
          not N["has"] and "LIVE_LINK.bat" in N["banner"] and all(t["empty"] and t["connect"] for t in N["tiles"]) and all(a["state"] == "empty" and a["connect"] for a in N["areas"]), N["tiles"][0])
    check("i. a broken file = the same as none; junk is cut and cleaned (markup removed, 120 characters, an unknown level dropped, a bar kept within 0-100%)",
          not B["has"] and J["tiles"][0]["value"] == "b x /b" and len(J["tiles"][0]["sub"]) == 120 and J["tiles"][0]["lvl"] == "" and J["areas"][0]["cards"][0]["rows"][0]["pct"] == 100, J["tiles"][0])
    check("i. the connect lines on the phone are the PC's own words (me.js CONNECT == tools/me_hub.py CONNECT)", O["connect"] == me_hub.CONNECT,
          {k: (O["connect"].get(k), me_hub.CONNECT.get(k)) for k in me_hub.CONNECT if O["connect"].get(k) != me_hub.CONNECT.get(k)})


# ------------------------------------------------------------------------------------------------ j. the browser
STATE = """() => ({ title: document.querySelector('#hubName').textContent, q: document.querySelector('#hubQ').textContent, district: document.documentElement.dataset.olyDistrict,
  page: document.documentElement.dataset.olyPage, tabsHidden: document.querySelector('#tabs').hidden, status: (document.querySelector('#meStatus') || {}).textContent,
  tiles: [...document.querySelectorAll('.me-tile')].map((a) => ({ id: a.dataset.tile, href: a.getAttribute('href'), text: [...a.children].map((c) => c.textContent), cls: a.className })),
  chips: [...document.querySelectorAll('.me-chip')].map((a) => a.textContent), areas: [...document.querySelectorAll('.me-sec')].map((s) => [s.dataset.area, s.className.replace('me-sec ', ''), s.querySelectorAll('details.me-card').length]),
  empties: [...document.querySelectorAll('.me-empty .me-ec')].map((p) => p.textContent), see: [...document.querySelectorAll('#seeList a')].map((a) => a.dataset.app),
  crumbs: [...document.querySelectorAll('nav.gn-crumbs a, nav.gn-crumbs .gn-cur')].filter((e) => getComputedStyle(e).display !== 'none' && e.textContent).map((e) => e.textContent.trim()) })"""


def open_me(p, origin, q=""):
    p.goto(f"{origin}/hub/?h=me&now={NOW_ISO}{q}")
    p.wait_for_function("window.HUB && window.HUB.ready()", timeout=60000, polling=200)
    p.wait_for_function("window.OLYMPUS_GATE_NAV && window.OLYMPUS_GATE_NAV.placed()", timeout=30000, polling=200)
    p.wait_for_timeout(300)


def test_page():
    from tools import me_hub
    doc = me_hub.build(NOW, None, full_inputs())
    srv, origin = AK.serve({"/me/me.json": json.dumps(doc)})
    srv2, origin2 = AK.serve({})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            open_me(p, origin)
            r = p.evaluate(STATE)
            check("j. hub/?h=me: the title Me, its question, <html data-oly-district=me data-oly-page=hub-me> (Mix can give it its own look), no tabs",
                  r["title"] == "Me" and r["q"] == "How am I doing — money, health, home?" and r["district"] == "me" and r["page"] == "hub-me" and r["tabsHidden"], r)
            check("j. the 4 tiles on top, each with its value, line and 'source · age', each a link to its area", [t["id"] for t in r["tiles"]] == ["money", "health", "home", "date"]
                  and [t["href"] for t in r["tiles"]] == ["#me-money", "#me-health", "#me-home", "#me-dates"] and r["tiles"][0]["text"][0] == "Money left this month"
                  and r["tiles"][0]["text"][3].startswith("Bank exports · ") and r["tiles"][2]["text"][1] == "New device" and "warn" in r["tiles"][2]["cls"], r["tiles"])
            check("j. the 8 areas as chips and as sections with their card stacks (4 money, 3 cards, 5 health, 4 home ...); Also useful: Oikos, Planner, Argo; Home > Me",
                  r["chips"] == ["Money", "Cards", "Health", "Home & WiFi", "Freedom", "Dates", "Car", "Streaks"] and [a[0] for a in r["areas"]] == ["money", "cards", "health", "home", "freedom", "dates", "car", "streaks"]
                  and [a[2] for a in r["areas"]][:4] == [4, 3, 5, 4] and r["see"] == ["oikos", "planner", "argo"] and r["crumbs"][:2] == ["Home", "Me"] and "8 of 8 areas connected" in r["status"], r)
            p.click("#me-cards details[data-card='use'] summary")
            p.wait_for_timeout(150)
            det = p.evaluate("() => { const d = document.querySelector('#me-cards details[data-card=use]'); return [d.open, [...d.querySelectorAll('.me-row')].map((x) => x.textContent), d.querySelector('.me-cnote').textContent]; }")
            check("j. one tap on a card opens its detail: each card's use with its bar, the 30% / 10% guidance", det[0] and len(det[1]) == 2 and det[1][0].startswith("Chase Freedom22%") and "Under 30% is fine" in det[2], det)
            p.click(".me-tile[data-tile='health']")
            p.wait_for_timeout(250)
            y = p.evaluate("() => Math.round(document.querySelector('#me-health').getBoundingClientRect().top)")
            check("j. a tile tap goes to its area (Health)", 0 <= y < 200 and p.url.endswith("#me-health"), (y, p.url))
            AK.shot(p, "me-hub")
            t = AK.taps(p)
            check("j. with data: every tap >= 44 px, no sideways scroll, Jarvis's corner free, no console error, nothing off the origin",
                  not t and AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (t[:4], AK.corner(p), errs[:3], off[:2]))
            ctx.close()
            # the public site: no me.json at all
            ctx, p, errs, seen, off = AK.page(br, origin2)
            open_me(p, origin2)
            r = p.evaluate(STATE)
            check("j. without the file (the public site): the banner says to open it through the PC's link, every tile 'Not connected' + its one-line how, every area its connect line",
                  "LIVE_LINK.bat" in r["status"] and all(t["text"][1] == "Not connected" and t["text"][3] == "How to connect" and len(t["text"]) == 4 for t in r["tiles"])
                  and len(r["empties"]) == 8 and r["empties"][1].startswith("On the PC: python tools\\me_cards.py --add") and not errs, (r["status"], r["tiles"][0], errs[:2]))
            AK.shot(p, "me-hub-empty")
            check("j. without data: taps >= 44 px, no sideways scroll", not AK.taps(p) and AK.no_sideways(p), AK.taps(p)[:3])
            ctx.close()
            # the home: the Me tile's line, the search, Mix
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/gate/?now={NOW_ISO}")
            p.wait_for_function("window.GATE && window.GATE.ready()", timeout=60000)
            p.wait_for_timeout(400)
            g = p.evaluate("() => { const t = document.querySelector('.g-hub[data-hub=me]'); return [t.className, t.querySelector('.g-hline').textContent, t.querySelector('.g-hcount').textContent, t.getAttribute('href')]; }")
            check("j. the home: the Me tile (wide, second) reads '$... left · 7,000 steps · New device' from the PC's file, '8 areas', and opens hub/?h=me",
                  "g-wide" in g[0] and g[1] == " · ".join(t["short"] for t in doc["tiles"][:3]) and g[2] == "8 areas" and g[3].endswith("hub/index.html?h=me"), g)
            p.fill("#q", "health")
            p.wait_for_timeout(200)
            first = p.evaluate("() => { const a = document.querySelector('#results a.g-row'); return a ? [a.dataset.hub, a.textContent] : null; }")
            check("j. the home's search: 'health' finds the Me hub first", first and first[0] == "me" and first[1].startswith("Me"), first)
            have = p.evaluate("() => !!document.querySelector('#lookTab2') && !document.querySelector('#lookSec').hidden")
            if have:
                p.click("#lookTab2")
                p.wait_for_timeout(250)
                rows = p.evaluate("() => [...document.querySelectorAll('.g-mixrow .g-mixh b')].map((b) => b.textContent)")
                tid = p.evaluate("() => { const row = [...document.querySelectorAll('.g-mixrow')].find((r) => r.querySelector('.g-mixh b').textContent === 'Me'); const b = row && row.querySelector('.g-mini[data-theme-id]:not([data-theme-id=agora])'); if (!b) return null; b.click(); return b.dataset.themeId; }")
                p.wait_for_timeout(300)
                open_me(p, origin)
                applied = p.evaluate("() => document.documentElement.getAttribute('data-oly-theme')")
                check("j. Mix gives the Me hub its own look: a 'Me' row in the Gate's Mix, a look picked there paints hub/?h=me", "Me" in rows and tid and applied == tid, (rows, tid, applied))
            else:
                check("j. the Gate's Look row is there (the theme engine loaded)", False, "no Look section")
            check("j. the home and the Mix: no console error, nothing off the origin", not errs and not off, (errs[:3], off[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            open_me(p, origin)
            p.click("#me-home details[data-card='devices'] summary")
            p.wait_for_timeout(150)
            anim = p.evaluate("() => document.getAnimations().length")
            check("j. 375 x 667, reduced motion, LITE: a card opens, nothing animates, no sideways scroll, every tap >= 44 px, no console error",
                  p.evaluate("() => document.querySelector('#me-home details[data-card=devices]').open") and anim == 0 and AK.no_sideways(p) and not AK.taps(p) and not errs, (anim, AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "me-hub-375")
            ctx.close()
    finally:
        srv.shutdown()
        srv2.shutdown()


if __name__ == "__main__":
    try:
        test_static()
        test_inbox()
        test_private()
        test_cards()
        test_health()
        test_home()
        test_life()
        test_hub()
        test_node()
        if "--static" not in sys.argv:
            test_page()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    AK.finish()
