"""ARGUS (tools/web_public/argus/, 2026-11-03): the watchtower, one screen with every health light + a ranked "fix this first" list.

  a. the files: the OLYMPUS kit links (?v=o2, data-app="argus"), only local scripts, the module imports exist, read-only (no orders,
     no network but the site's own JSON), the Jarvis card, the orb corner kept free in the CSS
  b. the lights as functions, in the page, against independent Python mirrors: the CME market clock, the weekday-hours clock of CRONOS,
     every light (bots, feed, NinjaTrader, PC, cloud monitor, publish age, CRONOS, 13 app cards, 7-day inactivity, drawdown),
     the verdict words and the ranking of the fix list
  c. the page in Playwright Chromium at 390 x 844: a hundred eyes, their colours = their light's level, the render core's tiers
     (OLYMPUS.fx(): high 3 passes, low 2, off 1), the fix list and the lights tab, a tap on an eye and on a row, #routes, offline
     (the last good copy, "as of"), no data at all, no sideways scroll, the orb corner free, reduced motion, no errors

    python -X utf8 -m tests.test_argus_page            (everything; c needs Playwright's Chromium)
    python -X utf8 -m tests.test_argus_page fast       (a's file checks only: no browser)
"""
from __future__ import annotations

import datetime as dt
import functools
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.olympus_money_kit import JARVIS_FILES, RES, WEB, _Quiet, browser, check, link_assets, open_page, orb_hits, tidy_errors  # noqa: E402

PAGE = os.path.join(WEB, "argus")
NOW_ISO = "2026-11-04T10:30:00-05:00"           # a Wednesday, 10:30 ET (EST: daylight saving ended 2026-11-01)
NOW = int(dt.datetime.fromisoformat(NOW_ISO).timestamp())
Q = "?now=" + NOW_ISO
ET = ZoneInfo("America/New_York")
APPS = ["datacity", "mind", "tree", "oracle", "odeon", "fates", "hermes", "prometheus", "tyche", "pantheon", "arena", "ares", "plutus"]


def rd(name):
    with open(os.path.join(PAGE, name), encoding="utf-8") as fh:
        return fh.read()


def ts_of(iso):
    return int(dt.datetime.fromisoformat(iso).timestamp())


# ------------------------------------------------------------------------------------------------------------ fixtures
def home(now=NOW):
    return {
        "built": dt.datetime.fromtimestamp(now - 600, dt.timezone.utc).isoformat(timespec="seconds"),
        "live": {"last_run": now - 300, "pc": {"running": True, "health": {"running": True, "account": {"armed": True}}}},
        "board": {
            "data_t": now - 60, "running": True,
            "lit": {"status": "open", "blocks": [], "quiet_days": 1, "room": 1800.0, "mll": 2000.0, "floor": 48000.0},
            "atlas": {"status": "open", "blocks": [], "quiet_days": 2, "room": 900.0, "mll": 1000.0, "floor": 24100.0},
            "health": {"items": [
                {"key": "age_1m_s", "label": "Feed 1m", "value": "50 s", "ok": True, "warn": False, "detail": "ninjatrader bars, 50 s old"},
                {"key": "nt", "label": "NinjaTrader", "value": "connected", "ok": True, "warn": False, "detail": "Sim101 connected"}]},
        },
    }


def cronos(now=NOW):
    return {"tasks": {n: {"ok": True, "last_ok_t": now - 8 * 3600, "last_run_t": now - 8 * 3600}
                      for n in ("datacity", "fates", "odeon", "pantheon", "hermes", "tree", "prometheus")}}


def cards(now=NOW):
    return {a: {"v": 1, "name": a, "status": {"level": "ok", "label": "ok"}, "t": now - 3600, "stale_after": 259200} for a in APPS}


def mksite(tmp, name, h, c, k):
    """a throw-away copy of the site: argus + olympus + the Jarvis assets + home.json / cronos / the 13 cards (None = the file is missing)"""
    base = os.path.join(tmp, name)
    shutil.copytree(PAGE, os.path.join(base, "argus"))
    shutil.copytree(os.path.join(WEB, "olympus"), os.path.join(base, "olympus"))
    link_assets(base)                                  # the built site's assets/ (the kit's sounds): no 404 on the first tap
    os.makedirs(os.path.join(base, "jarvis"))
    for f in JARVIS_FILES:
        src = os.path.join(WEB, "jarvis", f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(base, "jarvis", f))

    def put(rel, obj):
        if obj is not None:
            os.makedirs(os.path.dirname(os.path.join(base, rel)), exist_ok=True)
            with open(os.path.join(base, rel), "w", encoding="utf-8") as fh:
                json.dump(obj, fh)
    put("home.json", h)
    put("cronos/status.json", c)
    for a in APPS:
        put(f"{a}/jarvis.json", (k or {}).get(a))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=base))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/argus/"


# ------------------------------------------------------------------------------------------------------------ a
def part_a():
    html = rd("index.html")
    check("a. the OLYMPUS kit: olympus.css, themes.js, olympus.js (data-app=argus) all at ?v=o2",
          all(s in html for s in ('../olympus/olympus.css?v=o7', '../olympus/themes.js?v=o9', '../olympus/olympus.js?v=o17" data-app="argus"')))
    check("a. title Argus, a description, theme-color = the page colour, the Jarvis icon like the siblings",
          "<title>Argus</title>" in html and 'name="description"' in html and 'content="#14110e"' in html and "../jarvis/icon-192.png" in html and "#14110e" in rd("argus.css") + html)
    srcs = re.findall(r'(?:src|href)="([^"]+)"', html)
    check("a. only local files (no external script, font or stylesheet)", all(not s.startswith(("http:", "https:", "//")) for s in srcs), srcs)
    check("a. every local file the page links exists", all(os.path.exists(os.path.normpath(os.path.join(PAGE, s.split("?")[0]))) for s in srcs if not s.startswith("#")), srcs)
    js = rd("argus.js") + rd("arguscore.js")
    imps = re.findall(r"from '(\.[^']+)'", js)
    check("a. every module import resolves (three.js from ../jarvis/, the render core + materials from ../olympus/, the core next door)",
          imps and all(os.path.exists(os.path.normpath(os.path.join(PAGE, i))) for i in imps) and "../olympus/render.js" in imps and "../olympus/materials.js" in imps, imps)
    check("a. 3D goes through the render core (createRenderer), never a renderer of its own; the tier is OLYMPUS.fx() (the page keeps no quality key)",
          "createRenderer(" in js and "new THREE.WebGLRenderer" not in js and "O.fx()" in js and "jfx" not in js)
    gets = sorted(set(re.findall(r"getJson\(\s*[`']([^`',)]+)", js)))
    check("a. read only, no Yahoo: the network is the site's own home.json / data.json / cronos/status.json / each app's jarvis.json",
          "yahoo" not in js.lower() and set(gets) >= {"../home.json", "../data.json", "../cronos/status.json"} and all(g.startswith("../") for g in gets)
          and len(re.findall(r"\bfetch\(", js)) == 1, gets)
    check("a. nothing in the page places, routes or changes an order, or sends anything but the Jarvis card to its parent",
          not re.search(r"place_?order|/api/|websocket|method:\s*['\"]?POST|XMLHttpRequest|sendBeacon", js, re.I))
    card = json.loads(rd("jarvis.json"))
    check("a. the Jarvis card: v 1, name Argus, status, kpis, open #fix, the page theme, a stale_after",
          card["v"] == 1 and card["name"] == "Argus" and card["open"] == "#fix" and card["theme"] == "#050912" and len(card["kpis"]) >= 2
          and card["status"]["level"] in ("ok", "off", "warn", "bad") and 60 <= card["stale_after"] <= 14 * 86400 and len(card["status"]["label"]) <= 48
          and all(len(x) <= 120 for x in card["lines"]), card)
    css = rd("argus.css")
    check("a. the dock and the sheet keep the bottom-right 80 x 160 px free (right padding 88, sheet ends 166 px up)", "padding: 8px calc(88px" in css and ("bottom: calc(166px" in css or "bottom: calc(var(--dock-h) + 16px" in css))   # 2026-11-04: the Money tab made the tabs a 2 x 2 grid: the dock is taller and the sheet ends 16 px above it
    check("a. the app list names all 13 OLYMPUS apps that have a card", all(f"['{a}'," in rd("arguscore.js") for a in APPS))


# ------------------------------------------------------------------------------------------------------------ b
def py_market_open(t):
    d = dt.datetime.fromtimestamp(t, ET)
    m = d.hour * 60 + d.minute
    wd = d.weekday()        # Mon 0 ... Sun 6
    if wd == 5:
        return False
    if wd == 6:
        return m >= 1080
    if wd == 4:
        return m < 1020
    return m < 1020 or m >= 1080


def py_biz_hours(a, b):
    tot, t = 0.0, a
    while t < b:
        if dt.datetime.fromtimestamp(t, ET).weekday() < 5:
            tot += min(900, b - t)
        t += 900
    return tot / 3600.0


def part_b(p):
    def an(h=..., c=..., k=..., now=NOW):
        return p.evaluate("""([h, c, k, now]) => { const R = window.__argus.CORE.analyze({ now, home: h, cronos: c, cards: k }); return { v: R.verdict, counts: R.counts, fix: R.fix.map(e => e.id),
          eyes: Object.fromEntries(R.eyes.map(e => [e.id, { level: e.level, value: e.value, detail: e.detail, fix: e.fix }])), n: R.eyes.length, hasData: R.hasData }; }""",
                          [home(now) if h is ... else h, cronos(now) if c is ... else c, cards(now) if k is ... else k, now])

    def mod(fn, now=NOW, **kw):
        h = home(now)
        fn(h)
        return an(h=h, now=now, **kw)

    ok = an()
    q = ok["eyes"]
    check("b. a healthy system: ALL CLEAR, 25 lights, no red or amber, nothing to fix", ok["v"]["word"] == "All clear" and ok["n"] == 25 and ok["counts"]["bad"] == 0 and ok["counts"]["warn"] == 0 and not ok["fix"], ok["counts"])
    check("b. ... the bots say 'running, armed' (Zlarior) and 'running' (ATLAS); the feed is fresh; NinjaTrader connected",
          q["bot_lit"]["value"] == "running, armed" and q["bot_atlas"]["value"] == "running" and q["feed"]["level"] == "ok" and q["nt"]["value"] == "connected")
    check("b. ... inactivity 'day 1 of 7' / 'day 2 of 7', drawdown '$1,800 left' / '$900 left' (ATLAS 900 of 1,000 is green)",
          q["quiet_lit"]["value"] == "day 1 of 7" and q["quiet_atlas"]["value"] == "day 2 of 7" and q["room_lit"]["value"] == "$1,800 left" and q["room_atlas"]["value"] == "$900 left"
          and q["room_lit"]["level"] == "ok" and q["room_atlas"]["level"] == "ok")

    # bots and the PC
    r = mod(lambda h: h["board"].update(running=False))
    check("b. the bot stopped: RED on the PC and on both bots, 'press Start trading'", r["eyes"]["pc"]["level"] == "bad" and r["eyes"]["bot_lit"]["level"] == "bad" and "Start" in r["eyes"]["bot_lit"]["fix"] and r["v"]["word"] == "Look at this")
    r = mod(lambda h: h["live"]["pc"]["health"]["account"].update(armed=False))
    check("b. running but not armed: AMBER, 'will not send orders' (a plain sentence), never red", r["eyes"]["bot_lit"]["level"] == "warn" and "not send orders" in r["eyes"]["bot_lit"]["detail"] and r["eyes"]["bot_atlas"]["level"] == "ok")
    r = mod(lambda h: h["board"]["lit"].update(blocks=[{"text": "FEED STALE: NinjaTrader bars are old", "fix": "Reload NinjaScript"}]))
    check("b. a guard blocking entries: Zlarior RED with the guard's own sentence and fix", r["eyes"]["bot_lit"]["level"] == "bad" and "FEED STALE" in r["eyes"]["bot_lit"]["detail"] and r["eyes"]["bot_lit"]["fix"] == "Reload NinjaScript")
    a20 = mod(lambda h: h["board"].update(data_t=NOW - 20 * 60))
    a40 = mod(lambda h: h["board"].update(data_t=NOW - 40 * 60))
    check("b. no check-in for 20 min in market hours: the PC is AMBER (and the bots 'unsure'); 40 min: RED and both bots RED",
          a20["eyes"]["pc"]["level"] == "warn" and a20["eyes"]["bot_lit"]["level"] == "warn" and a40["eyes"]["pc"]["level"] == "bad" and a40["eyes"]["bot_lit"]["level"] == "bad")
    r = mod(lambda h: h["board"]["atlas"].update(status="not set up"))
    check("b. ATLAS not set up: grey, not counted", r["eyes"]["bot_atlas"]["level"] == "idle" and r["v"]["word"] == "All clear")
    r = mod(lambda h: h["board"]["lit"].update(status="passed"))
    check("b. eval passed: Zlarior green 'eval passed'; inactivity and drawdown grey (the account is over)", r["eyes"]["bot_lit"]["value"] == "eval passed" and r["eyes"]["quiet_lit"]["level"] == "idle" and r["eyes"]["room_lit"]["level"] == "idle")
    r = mod(lambda h: h["board"]["lit"].update(status="failed"))
    check("b. eval failed: Zlarior RED 'eval ended'", r["eyes"]["bot_lit"]["level"] == "bad" and r["eyes"]["bot_lit"]["value"] == "eval ended")

    # feed and NinjaTrader
    def stale(h):
        h["board"]["health"]["items"][0].update(ok=False, value="9 min", detail="ninjatrader bars, 9 min old")
        h["board"]["health"]["items"][1].update(ok=False, value="not connected")
    r = mod(stale)
    check("b. stale feed + NinjaTrader down: both RED with the plain fix (Reload NinjaScript / Connections), verdict LOOK AT THIS",
          r["eyes"]["feed"]["level"] == "bad" and "Reload NinjaScript" in r["eyes"]["feed"]["fix"] and r["eyes"]["nt"]["level"] == "bad" and "Connections" in r["eyes"]["nt"]["fix"]
          and r["v"]["word"] == "Look at this" and r["v"]["level"] == "bad")
    sat = ts_of("2026-11-07T11:00:00-05:00")
    r = mod(lambda h: (stale(h), h["board"].update(data_t=sat - 36 * 3600)), now=sat, c=cronos(sat), k=cards(sat))
    check("b. Saturday, market closed: a stale feed and a quiet PC are grey (fine), still ALL CLEAR",
          r["eyes"]["feed"]["value"] == "market closed" and r["eyes"]["pc"]["level"] == "idle" and r["eyes"]["feed"]["level"] == "idle" and r["v"]["word"] == "All clear", r["eyes"]["pc"])

    # the cloud pipes
    def cloud(secs):
        return mod(lambda h: h["live"].update(last_run=NOW - secs))["eyes"]["cloud"]["level"]
    check("b. cloud monitor: ran 20 min ago green, 50 min amber, 3 h red", (cloud(1200), cloud(3000), cloud(3 * 3600)) == ("ok", "warn", "bad"))

    def pub(secs):
        return mod(lambda h: h.update(built=dt.datetime.fromtimestamp(NOW - secs, dt.timezone.utc).isoformat(timespec="seconds")))["eyes"]["publish"]["level"]
    check("b. dashboard publish: 30 min green, 90 min amber, 4 h red", (pub(1800), pub(5400), pub(4 * 3600)) == ("ok", "warn", "bad"))

    def cr(upd, now=NOW):
        c = cronos(now)
        upd(c["tasks"])
        return an(c=c, now=now, k=cards(now), h=home(now))["eyes"]["cronos"]
    f50 = cr(lambda t: t["fates"].update(last_ok_t=NOW - 50 * 3600))     # Tuesday 08:30 minus... (all weekdays: 50 weekday hours)
    check("b. CRONOS nightly: 8 h green; fates 50 weekday hours behind amber (named), 92 red",
          cr(lambda t: None)["level"] == "ok" and f50["level"] == "warn" and f50["value"] == "fates late" and cr(lambda t: t["fates"].update(last_ok_t=NOW - 140 * 3600))["level"] == "bad", f50)
    check("b. CRONOS: a failed last run after the last good one is amber; a weekly job (tree) 4 days behind is still green",
          cr(lambda t: t["odeon"].update(ok=False, error="boom", last_run_t=NOW - 600))["level"] == "warn" and cr(lambda t: t["tree"].update(last_ok_t=NOW - 4 * 86400))["level"] == "ok")
    mon, fri = ts_of("2026-11-09T09:00:00-05:00"), ts_of("2026-11-06T20:00:00-05:00")
    check("b. CRONOS: Friday-night data is still fresh on Monday morning (a weekend does not age a nightly job)", cr(lambda t: t["fates"].update(last_ok_t=fri), now=mon)["level"] == "ok")

    # the apps
    def app(upd, name="plutus"):
        k = cards()
        upd(k[name])
        return an(k=k)["eyes"]["app_" + name]
    check("b. app cards: fresh green; past its stale_after amber; 4x past (and a day) red; no stale_after = a week of slack; a missing card is grey",
          app(lambda c: None)["level"] == "ok" and app(lambda c: c.update(t=NOW - 300000))["level"] == "warn" and app(lambda c: c.update(t=NOW - 2000000))["level"] == "bad"
          and app(lambda c: (c.pop("stale_after"), c.update(t=NOW - 700000)))["level"] == "warn" and app(lambda c: (c.pop("stale_after"), c.update(t=NOW - 20000)))["level"] == "ok"
          and an(k={**cards(), "mind": None})["eyes"]["app_mind"]["level"] == "idle")
    st = app(lambda c: c.update(cronos={"state": "stale"}), "odeon")
    check("b. CRONOS-stamped cards: state fresh green; stale / failed amber (never red); the app is named in the fix",
          app(lambda c: c.update(cronos={"state": "fresh"}), "odeon")["level"] == "ok" and st["level"] == "warn" and "Odeon" in st["fix"]
          and app(lambda c: c.update(cronos={"state": "failed"}), "odeon")["value"] == "refresh failed")

    # the 7-day clock and the drawdown
    def qd(n):
        return mod(lambda h: h["board"]["lit"].update(quiet_days=n))["eyes"]["quiet_lit"]
    q3, q4, q6 = qd(3), qd(4), qd(6)
    check("b. the 7-day inactivity clock: day 3 green, day 4 amber, day 6 red with '1 day left' and 'place 1 MNQ by hand'",
          q3["level"] == "ok" and q4["level"] == "warn" and q6["level"] == "bad" and "1 day left" in q6["detail"] and "1 MNQ by hand" in q6["fix"] and qd(0)["level"] == "ok", q6)
    check("b. ... unknown last trade: grey, not guessed", mod(lambda h: h["board"]["lit"].pop("quiet_days"))["eyes"]["quiet_lit"]["level"] == "idle")

    def dd(room):
        return mod(lambda h: h["board"]["lit"].update(room=room))["eyes"]["room_lit"]
    check("b. drawdown left of the $2,000: $1,000 green (50%), $900 amber, $400 red; the floor is named; red says stop and protect",
          dd(1000)["level"] == "ok" and dd(900)["level"] == "warn" and dd(400)["level"] == "bad" and "$48,000" in dd(400)["detail"] and "protect" in dd(400)["fix"] and dd(0)["value"] == "$0 left")
    check("b. ... a room bigger than the max loss (a profit cushion) is green", dd(3240)["level"] == "ok")

    # ranking and verdict
    def many(h):
        h["board"]["lit"].update(room=300, quiet_days=4)
        h["live"].update(last_run=NOW - 3000)
        h["board"]["health"]["items"][1].update(ok=False, value="not connected")
    r = mod(many, k={**cards(), "tyche": {**cards()["tyche"], "t": NOW - 2000000}})
    red = [i for i in r["fix"] if r["eyes"][i]["level"] == "bad"]
    amb = [i for i in r["fix"] if r["eyes"][i]["level"] == "warn"]
    check("b. the fix list is ranked: every red first (the money light, then NinjaTrader, then the app), then every amber; one plain instruction on each",
          r["fix"] == red + amb and red == ["room_lit", "nt", "app_tyche"] and amb == ["quiet_lit", "cloud"] and all(r["eyes"][i]["fix"] for i in r["fix"]), (red, amb))
    check("b. ... the words: 'Look at this' for red or amber, with the first thing to fix in the sentence", r["v"]["word"] == "Look at this" and "Zlarior 50K drawdown" in r["v"]["line"], r["v"])
    n = an(h=None, c=None, k={a: None for a in APPS})
    check("b. no dashboard data at all: 'No data yet' (never 'All clear'), nothing red", n["v"]["word"] == "No data yet" and n["v"]["level"] == "idle" and n["counts"]["bad"] == 0 and not n["hasData"])

    # the clocks against independent Python mirrors
    ts = [NOW - 7 * 86400 + i * 1800 for i in range(0, 7 * 48)]
    got = p.evaluate("(ts) => ts.map(t => window.__argus.CORE.marketOpen(t))", ts)
    bad = [t for t, g in zip(ts, got) if g != py_market_open(t)]
    check("b. the CME clock (Sunday 18:00 to Friday 17:00 ET, the 17:00 break) equals the Python mirror on a week of half-hours", not bad, bad[:3])
    pairs = [[fri, mon], [NOW - 40 * 3600, NOW], [NOW - 200 * 3600, NOW], [NOW - 5 * 3600, NOW]]
    got = p.evaluate("(pr) => pr.map(([a, b]) => window.__argus.CORE.bizHours(a, b))", pairs)
    bad = [(a, b, g, py_biz_hours(a, b)) for (a, b), g in zip(pairs, got) if abs(g - py_biz_hours(a, b)) > 1e-6]
    check("b. the weekday-hours clock (CRONOS) equals the Python mirror; Friday 20:00 to Monday 09:00 = 13 weekday hours", not bad and abs(got[0] - 13.0) < 1e-6, (bad, got))
    c = p.evaluate("([h, c, k, now]) => { const R = window.__argus.CORE.analyze({ now, home: h, cronos: c, cards: k }); return window.__argus.CORE.cardOf(R, now); }", [home(), cronos(), cards(), NOW])
    check("b. the live Jarvis card: Argus, All clear, red / amber / green counts, one line, open #fix, inside the Jarvis limits",
          c["name"] == "Argus" and c["status"] == {"level": "ok", "label": "All clear"} and [k["value"] for k in c["kpis"]] == ["0", "0", "25"] and len(c["lines"]) == 1 and len(c["lines"][0]) <= 120 and c["open"] == "#fix", c)


# ------------------------------------------------------------------------------------------------------------ real
FIXD = os.path.join(ROOT, "tests", "fixtures", "argus")


def jl(name):
    with open(os.path.join(FIXD, name), encoding="utf-8") as fh:
        return json.load(fh)


def part_real(p):
    """the REAL published home.json (a copy of the public site's file, 2026-11-03 21:31 UTC = Tuesday 16:31 ET, market open)"""
    h = jl("home_real.json")
    kards = {"mind": jl("card_mind.json"), "fates": jl("card_fates.json")}
    b = h["board"]
    paths = [h.get("built"), h["live"].get("last_run"), h["live"]["pc"]["health"]["account"].get("armed") is not None, b.get("data_t"), b.get("running") is not None,
             [i["key"] for i in b["health"]["items"] if i["key"] in ("age_1m_s", "nt")], b["lit"].get("room"), b["lit"].get("mll"), b["lit"].get("floor"), b["lit"].get("status"),
             "blocks" in b["lit"], "quiet_days" in b["lit"], b["atlas"].get("room"), b["atlas"].get("floor"), b["real"]["trades"]]
    check("real. every field path the lights read exists in the published home.json", all(x not in (None, [], False) for x in paths), paths)
    now = b["t"]

    def run(**kw):
        return p.evaluate("([h, k, now]) => { const R = window.__argus.CORE.analyze({ now, home: h, cronos: null, cards: k }); return { v: R.verdict, counts: R.counts, fix: R.fix.map(e => e.id), eyes: Object.fromEntries(R.eyes.map(e => [e.id, e])) }; }",
                          [kw.get("h", h), kw.get("k", kards), kw.get("now", now)])
    r = run()
    e = r["eyes"]
    check("real. the real lights: Zlarior 'running, armed', ATLAS 'running', feed fresh, NinjaTrader connected, cloud + publish green",
          e["bot_lit"]["value"] == "running, armed" and e["bot_atlas"]["value"] == "running" and e["feed"]["level"] == "ok" and e["nt"]["value"] == "connected"
          and e["cloud"]["level"] == "ok" and e["publish"]["level"] == "ok" and e["pc"]["level"] == "ok", {k: (v["level"], v["value"]) for k, v in e.items() if v["level"] != "ok"})
    check("real. drawdown left = balance minus floor for both real accounts (Zlarior and ATLAS)",
          abs(b["lit"]["room"] - (b["lit"]["balance"] - b["lit"]["floor"])) < 1 and abs(b["atlas"]["room"] - (b["atlas"]["balance"] - b["atlas"]["floor"])) < 1
          and e["room_lit"]["value"] == "$1,133 left" and e["room_atlas"]["value"] == "$1,351 left" and e["room_lit"]["level"] == "ok" and e["room_atlas"]["level"] == "ok", e["room_lit"])
    check("real. the 7-day clock: ATLAS day 0 (the board's own count); Zlarior has none, so it comes from the last real trade (2026-11-03: day 0), not from nothing",
          e["quiet_atlas"]["value"] == "day 0 of 7" and e["quiet_lit"]["value"] == "day 0 of 7" and e["quiet_lit"]["level"] == "ok", e["quiet_lit"])
    check("real. 13 apps: the two real cards (Mind, Fates) green, the others grey 'no card'; CRONOS comes from the stamped Fates card (fresh); verdict ALL CLEAR, nothing to fix",
          e["app_mind"]["level"] == "ok" and e["app_fates"]["level"] == "ok" and e["app_ares"]["level"] == "idle" and e["cronos"]["level"] == "ok" and r["v"]["word"] == "All clear" and not r["fix"], (r["v"], r["fix"]))
    sat = ts_of("2026-11-07T11:00:00-05:00")
    r = run(now=sat)
    e = r["eyes"]
    check("real. a Saturday later, with the same file: the feed and NinjaTrader are grey 'market closed' (not red), the quiet PC grey; the cloud monitor / publish ages are amber or red (the file is days old: honest)",
          e["feed"]["level"] == "idle" and e["pc"]["level"] == "idle" and e["cloud"]["level"] == "bad" and e["publish"]["level"] == "bad", {k: (v["level"], v["value"]) for k, v in e.items() if v["level"] != "ok"})
    h2 = json.loads(json.dumps(h))
    h2["board"]["lit"]["room"] = 250.0
    h2["board"]["health"]["items"][[i["key"] for i in h2["board"]["health"]["items"]].index("nt")].update(ok=False, value="not connected")
    r = run(h=h2)
    check("real. the real file with the drawdown cut to $250 and NinjaTrader off: LOOK AT THIS, fix list = drawdown first then NinjaTrader",
          r["v"]["word"] == "Look at this" and r["fix"][:2] == ["room_lit", "nt"], r["fix"])


# ------------------------------------------------------------------------------------------------------------ actions
def part_actions(p):
    def an(h):
        return p.evaluate("""([h, c, k, now]) => { const R = window.__argus.CORE.analyze({ now, home: h, cronos: c, cards: k }); return { v: R.verdict, fix: R.fix.map(e => e.id),
          eyes: Object.fromEntries(R.eyes.map(e => [e.id, { level: e.level, cmd: e.cmd, step: e.step }])), card: window.__argus.CORE.cardOf(R, now) }; }""", [h, cronos(), cards(), NOW])
    h = home()
    h["board"]["running"] = False
    h["board"]["health"]["items"][0].update(ok=False, value="9 min")
    h["board"]["health"]["items"][1].update(ok=False, value="not connected")
    h["live"].update(last_run=NOW - 3 * 3600)
    h["board"]["lit"].update(quiet_days=4, room=300)
    h["live"]["pc"]["health"]["account"]["armed"] = False
    r = an(h)
    e = r["eyes"]
    check("fix. the PC and bots stopped: the exact file to double-click is START_BOT.bat (a PC command, copyable)", e["pc"]["cmd"] == {"kind": "pc", "text": "START_BOT.bat"} and e["bot_atlas"]["cmd"] == {"kind": "pc", "text": "START_BOT.bat"}, e["pc"])
    check("fix. a stale feed and NinjaTrader down: HEALTH_CHECK.bat (it shows each red line with its fix); every file named exists in the bot folder",
          e["feed"]["cmd"]["text"] == "HEALTH_CHECK.bat" and e["nt"]["cmd"]["text"] == "HEALTH_CHECK.bat"
          and all(os.path.exists(os.path.join(ROOT, c["cmd"]["text"])) for c in e.values() if c["cmd"] and c["cmd"]["kind"] == "pc"))
    check("fix. cloud / drawdown lights: a message to paste into the Claude chat (kind 'chat'), not a PC command", e["cloud"]["cmd"]["kind"] == "chat" and e["room_lit"]["cmd"]["kind"] == "chat" and "Zlarior" in e["room_lit"]["cmd"]["text"])
    check("fix. the 7-day clock (a manual trade) and 'not armed' (the owner's own decision) have a step but nothing to copy: Argus never offers to arm or trade",
          e["quiet_lit"]["cmd"] is None and e["quiet_lit"]["step"] and not any(re.search(r"arm|trade|order", c["cmd"]["text"], re.I) for c in e.values() if c["cmd"]))
    check("fix. a green light has no fix button data", all(c["cmd"] is None for c in an(home())["eyes"].values()))
    card = r["card"]
    check("fix. the live Jarvis card with reds leads with the problem: status bad, '<n> red: <first light>' (48 chars max), up to 3 lines of fixes, fresh t, a 30-minute stale_after, open #fix",
          card["status"]["level"] == "bad" and re.match(r"^\d+ red: ", card["status"]["label"]) and len(card["status"]["label"]) <= 48 and 1 <= len(card["lines"]) <= 3
          and all(len(x) <= 120 for x in card["lines"]) and card["t"] == NOW and card["stale_after"] == 1800 and card["open"] == "#fix", card)

    # the 14-day history, as functions
    def hu(seq):
        return p.evaluate("""(seq) => { let h = null; const C = window.__argus.CORE;
          for (const [t, lv, ids] of seq) h = C.histUpdate(h, { hasData: true, verdict: { level: lv }, eyes: ids.map(([id, l]) => ({ id, label: id, level: l })) }, t);
          return { h, s: C.histSummary(h, seq[seq.length - 1][0]) }; }""", seq)
    day = 86400
    seq = [[NOW - i * day, "ok", [["a", "ok"]]] for i in range(13, 0, -1)] + [[NOW, "ok", [["a", "ok"]]]]
    r = hu(seq)
    check("hist. 14 clear days in a row: the strip has 14 green squares and says '14 clear days in a row'", r["s"]["streak"] == 14 and [x["level"] for x in r["s"]["strip"]] == ["ok"] * 14 and "14 clear days in a row" in r["s"]["line"], r["s"]["line"])
    seq2 = [[NOW - 3 * day, "ok", []], [NOW - 2 * day, "warn", [["a", "warn"]]], [NOW - day, "ok", []], [NOW, "ok", []]]
    r = hu(seq2)
    check("hist. an amber day breaks the streak: 2 clear days since it; a day I did not open the page stays grey and never counts", r["s"]["streak"] == 2 and r["s"]["strip"][-3]["level"] == "warn" and r["s"]["strip"][0]["level"] == "idle", r["s"]["strip"][-4:])
    seq3 = [[NOW - 7200, "ok", [["feed", "ok"]]], [NOW - 3600, "bad", [["feed", "bad"]]], [NOW - 1800, "bad", [["feed", "bad"]]], [NOW, "ok", [["feed", "ok"]]]]
    r = hu(seq3)
    check("hist. what went red and for how long: the feed went red at -60 min and was fine again at 0: one incident of exactly 3600 s, none still open",
          len(r["s"]["reds"]) == 1 and r["s"]["reds"][0]["secs"] == 3600 and not r["s"]["reds"][0]["open"] and r["s"]["reds"][0]["label"] == "feed", r["s"]["reds"])
    r = hu(seq3[:3])
    check("hist. a light still red is listed 'open' with its running time; today counts as not clear", r["s"]["reds"][0]["open"] and r["s"]["reds"][0]["secs"] == 1800 and r["s"]["streak"] == 0 and "Not clear today" in r["s"]["line"], r["s"])
    r = hu([[NOW - 20 * day, "bad", [["x", "bad"]]], [NOW - 19 * day, "ok", []], [NOW, "ok", []]])
    check("hist. only 14 days are kept (a day 20 days back and its incident are dropped); 'no data' readings never write",
          list(r["h"]["days"].keys()).__len__() == 1 and not r["h"]["reds"]
          and p.evaluate("() => Object.keys(window.__argus.CORE.histUpdate(null, { hasData: false, verdict: { level: 'idle' }, eyes: [] }, %d).days).length" % NOW) == 0, r["h"])


# ------------------------------------------------------------------------------------------------------------ c
def tab(p, t):
    p.click(f"#tabs button[data-tab='{t}']")
    p.wait_for_timeout(120)


def wait_ready(p):
    p.wait_for_function("window.__argus && window.__argus.siteLoaded === true", timeout=30000)
    p.wait_for_timeout(500)


def part_c(tmp):
    from playwright.sync_api import sync_playwright
    srv1, ok_url = mksite(tmp, "s_ok", home(), cronos(), cards())
    h2 = home()
    h2["board"]["lit"].update(room=300, quiet_days=6)
    h2["board"]["health"]["items"][0].update(ok=False, value="9 min", detail="ninjatrader bars, 9 min old")
    srv2, bad_url = mksite(tmp, "s_bad", h2, cronos(), cards())
    srv3, none_url = mksite(tmp, "s_none", None, None, None)
    try:
        with sync_playwright() as pw:
            br = browser(pw)
            errs = []
            ctx, p = open_page(br, ok_url + Q, errs, "__argus")
            part_b(p)
            part_real(p)
            part_actions(p)
            ctx.close()

            errs = []
            ctx, p = open_page(br, ok_url + Q, errs, "__argus")
            check("c. loads at 390 x 844: the 3D sphere is up (WebGL), no OFFLINE tag, the verdict reads ALL CLEAR (green)",
                  p.evaluate("window.__argus.ready3d") and p.is_hidden("#nogl") and p.is_hidden("#offtag") and p.inner_text("#vk") == "All clear" and p.get_attribute("#verdict", "data-level") == "ok", p.inner_text("#vk"))
            check("c. a hundred eyes; every one of them green (all the lights are fine)", p.evaluate("window.__argus.eyes") == 100 and p.evaluate("window.__argus.levels.filter(l => l === 'ok').length") == 100, p.evaluate("window.__argus.levels.slice(0, 8)"))
            check("c. 'Fix this first' says there is nothing to fix; the count is 0", "Nothing to fix" in p.inner_text("#p-fix") and p.inner_text("#fixN") == "0")
            check("c. no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            for t in ("fix", "all"):
                tab(p, t)
                check(f"c. tab '{t}': the bottom-right 80 x 160 px stays free for Jarvis's orb", not orb_hits(p), orb_hits(p))
            tab(p, "all")
            body = p.inner_text("#p-all")
            check("c. all lights: grouped (bots, PC, prices, cloud, MFFU rules, apps), 25 rows with plain values",
                  p.evaluate("document.querySelectorAll('#p-all .lrow').length") == 25 and all(x in body for x in ("The bots", "Olympus apps", "Zlarior 50K", "running, armed", "day 1 of 7", "$1,800 left", "Plutus")), body[:160])
            p.click("#p-all [data-light='room_lit']")
            check("c. a tap on a light opens its one-line explanation and picks it (the caption over the sphere names it)",
                  "before the max-loss floor" in p.inner_text("#p-all") and p.is_visible("#pick") and "drawdown" in p.inner_text("#pick") and p.evaluate("window.__argus.sel") == "room_lit")
            ctx.close()
            check("c. no page errors, console errors or failed requests", not errs, errs[:5])

            # the render core's tiers: OLYMPUS.fx() picks the passes
            for fx, passes in (("high", 3), ("ultra", 3), ("low", 2), ("off", 1)):
                e2 = []
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
                ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{fx}'); }} catch (e) {{}}")
                p = ctx.new_page()
                p.on("pageerror", lambda e, e2=e2: e2.append(str(e)))
                p.on("console", lambda m, e2=e2: e2.append(m.text) if m.type == "error" else None)
                p.goto(ok_url + Q + "&gpu=1")          # ?gpu=1: lift the software-GL cap (high / ultra held to LITE on SwiftShader), as tests.test_olympus_kit
                wait_ready(p)
                got = p.evaluate("[window.__argus.fx, window.__argus.passes.length]")
                check(f"c. OLYMPUS.fx() = {fx}: the render core runs {passes} pass(es) per frame, all 100 eyes still there, no errors", got == [fx, passes] and p.evaluate("window.__argus.levels.length") == 100 and not e2, (got, e2[:2]))
                ctx.close()

            # something wrong: red eyes, the ranked list
            errs = []
            ctx, p = open_page(br, bad_url + Q, errs, "__argus")
            check("c. a red drawdown, a 6-day inactivity clock and a stale feed: LOOK AT THIS (red), the dock says '3 red'",
                  p.inner_text("#vk") == "Look at this" and p.get_attribute("#verdict", "data-level") == "bad" and "3 red" in p.inner_text("#vs"), p.inner_text("#vs"))
            check("c. the eyes follow: eight or more red, the rest mostly green, still exactly 100",
                  p.evaluate("window.__argus.levels.filter(l => l === 'bad').length") >= 8 and p.evaluate("window.__argus.levels.filter(l => l === 'ok').length") >= 60 and p.evaluate("window.__argus.levels.length") == 100)
            rows = p.evaluate("[...document.querySelectorAll('#p-fix .fixrow')].map(r => r.innerText)")
            check("c. 'Fix this first' is ranked, each row one plain instruction: 1 = drawdown (stop and protect), 2 = the 7-day clock, 3 = the feed",
                  len(rows) == 3 and "Zlarior 50K drawdown" in rows[0] and "protect" in rows[0] and "1 MNQ by hand" in rows[1] and "Reload NinjaScript" in rows[2] and p.inner_text("#fixN") == "3", rows)
            check("c. the fix rows are big enough to tap (44 px+)", p.evaluate("[...document.querySelectorAll('#p-fix .fixrow')].every(r => r.getBoundingClientRect().height >= 44)"))
            check("c. no sideways scroll, no orb hits with the list", p.evaluate("document.documentElement.scrollWidth <= innerWidth") and not orb_hits(p), orb_hits(p))
            p.click("#p-fix .fixrow >> nth=1")
            check("c. a tap on a fix row picks that light: the caption names it", p.evaluate("window.__argus.sel") == "quiet_lit" and "inactivity" in p.inner_text("#pick"))
            p.evaluate("location.hash = '#all'")
            p.wait_for_timeout(150)
            ok1 = p.evaluate("window.__argus.tab") == "all"
            p.evaluate("location.hash = '#fix'")
            p.wait_for_timeout(150)
            check("c. #all opens the lights tab and #fix the fix list (the Jarvis card's link)", ok1 and p.evaluate("window.__argus.tab") == "fix")
            ctx.close()
            check("c. no errors on the problem page", not errs, errs[:5])

            # fix buttons, copy, history, the live card (a framed page)
            errs = []
            ctx, p = open_page(br, bad_url + Q, errs, "__argus")
            p.evaluate("() => { window.__clip = null; Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (t) => { window.__clip = t; } }, configurable: true }); }")
            check("ui. every red light has a 'Fix it' button (44 px+), its panel is closed until tapped", p.evaluate("document.querySelectorAll('#p-fix .fixbtn').length") == 3
                  and p.evaluate("[...document.querySelectorAll('#p-fix .fixbtn')].every(b => b.getBoundingClientRect().height >= 44)") and p.is_hidden("#p-fix .fixpanel >> nth=0"))
            p.click("#p-fix .fixbtn >> nth=0")
            check("ui. 'Fix it' on the drawdown opens the exact step in plain words and a message to paste into Claude (no PC file)",
                  p.is_visible("#p-fix .fixpanel >> nth=0") and "protect what is left" in p.inner_text("#p-fix .fixpanel >> nth=0") and "Paste this into your Claude chat" in p.inner_text("#p-fix .fixpanel >> nth=0"))
            p.click("#p-fix .fixbtn >> nth=2")
            panel = p.inner_text("#p-fix .fixpanel >> nth=2")
            check("ui. 'Fix it' on the stale feed: the step (Reload NinjaScript), HEALTH_CHECK.bat in a box, 'double-click' and 'Argus never runs it'", "Reload NinjaScript" in panel and "HEALTH_CHECK.bat" in panel and "never runs it" in panel, panel)
            p.click("#p-fix .copy >> nth=1")
            p.wait_for_timeout(150)
            check("ui. the copy button copies exactly the file name and says 'Copied'; nothing else happens (no request, no order)", p.evaluate("window.__clip") == "HEALTH_CHECK.bat" and "Copied" in p.inner_text("#p-fix .copy >> nth=1"))
            p.click("#p-fix .fixbtn >> nth=1")
            check("ui. the 7-day clock's fix has the step but no copy box", "1 MNQ by hand" in p.inner_text("#p-fix .fixpanel >> nth=1") and p.evaluate("document.querySelectorAll('#p-fix .fixpanel')[1].querySelectorAll('code, .copy').length") == 0)
            tab(p, "all")
            check("ui. the same buttons are on the red / amber rows of 'All lights' (green rows have none)", p.evaluate("document.querySelectorAll('#p-all .fixbtn').length") == 3)
            check("ui. the bottom-right 80 x 160 px stays free with the panels open", not orb_hits(p), orb_hits(p))
            ctx.close()
            check("ui. no errors with the fix buttons", not errs, errs[:5])

            errs = []
            ctx, p = open_page(br, bad_url + Q, errs, "__argus")
            seed = {"days": {}, "open": {}, "reds": []}
            for i in range(1, 4):
                seed["days"][(dt.date.fromisoformat("2026-11-04") - dt.timedelta(days=i)).isoformat()] = "ok"
            p.evaluate("(s) => localStorage.setItem('argus.hist.v1', JSON.stringify(s))", seed)
            p.goto(bad_url + Q + "&r=1#history")
            p.wait_for_function("window.__argus && window.__argus.siteLoaded === true")
            p.wait_for_timeout(400)
            check("hist. #history opens the 'Since yesterday' tab; 14 squares; the last three clear days are green, today red; 'Not clear today.'",
                  p.evaluate("window.__argus.tab") == "hist" and p.evaluate("document.querySelectorAll('#strip .sq').length") == 14 and p.evaluate("document.querySelectorAll('#strip .sq.ok').length") == 3
                  and p.evaluate("document.querySelectorAll('#strip .sq.bad').length") == 1 and "Not clear today" in p.inner_text("#streak"), p.inner_text("#streak"))
            body = p.inner_text("#p-hist")
            check("hist. 'what went red and for how long' lists the lights red right now with 'still red'", "Zlarior 50K drawdown" in body and "still red" in body and "Price feed" in body, body[:300])
            check("hist. the tab keeps the bottom-right free and nothing scrolls sideways", not orb_hits(p) and p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            saved = p.evaluate("JSON.parse(localStorage.getItem('argus.hist.v1'))")
            check("hist. it is remembered on this phone (localStorage): today = red, 3 clear days before, 3 open incidents", saved["days"]["2026-11-04"] == "bad" and len(saved["days"]) == 4 and len(saved["open"]) == 3, saved)
            ctx.close()
            check("hist. no errors", not errs, errs[:5])
            errs = []
            ctx, p = open_page(br, ok_url + Q, errs, "__argus")
            seed = {"days": {}, "open": {}, "reds": []}
            for i in range(1, 14):
                seed["days"][(dt.date.fromisoformat("2026-11-04") - dt.timedelta(days=i)).isoformat()] = "ok"
            p.evaluate("(s) => localStorage.setItem('argus.hist.v1', JSON.stringify(s))", seed)
            p.goto(ok_url + Q + "&r=1#history")
            p.wait_for_function("window.__argus && window.__argus.siteLoaded === true")
            p.wait_for_timeout(400)
            check("hist. 13 clear days remembered + a clear today: '14 clear days in a row', every square green, nothing went red",
                  "14 clear days in a row" in p.inner_text("#streak") and p.evaluate("document.querySelectorAll('#strip .sq.ok').length") == 14 and "Nothing went red" in p.inner_text("#p-hist"))
            ctx.close()

            # the live card to Jarvis: the page inside a frame
            ctx = br.new_context(viewport={"width": 390, "height": 844})
            p = ctx.new_page()
            p.route("**/host.html", lambda r: r.fulfill(content_type="text/html", body=f'<iframe id="f" src="{bad_url + Q}" style="width:390px;height:800px"></iframe>'))
            p.goto(bad_url.replace("/argus/", "/host.html"))
            fr = None
            for _ in range(60):
                fr = next((f for f in p.frames if "/argus/" in f.url), None)
                if fr and fr.evaluate("!!(window.__argus && window.__argus.siteLoaded)"):
                    break
                p.wait_for_timeout(300)
            card = fr.evaluate("window.__argus.card")
            check("jarvis. framed in Jarvis with reds, the page builds the live card: status bad, leads with the problem, fresh, 3 fixes",
                  card["status"]["level"] == "bad" and card["status"]["label"].startswith("3 red: ") and card["t"] >= NOW and len(card["lines"]) == 3 and card["stale_after"] == 1800, card)
            ctx.close()

            # a tap on an eye (reduced motion: the sphere holds still)
            errs = []
            ctx, p = open_page(br, bad_url + Q, errs, "__argus", reduced=True)
            y0 = p.evaluate("window.__argus.yaw")
            p.wait_for_timeout(1200)
            check("c. reduced motion: the sphere stays still (no idle turn), the eyes are all open, the verdict still works",
                  abs(p.evaluate("window.__argus.yaw") - y0) < 1e-6 and p.get_attribute("#verdict", "data-level") == "bad" and p.evaluate("Math.min(...window.__argus.openness) > 0.001"))
            hit = None
            for i in range(100):
                xy = p.evaluate("(i) => window.__argus.eyeXY(i)", i)
                if xy and p.evaluate("(i) => window.__argus.levels[i]", i) == "bad":
                    hit = xy
                    break
            if hit:
                p.mouse.click(hit["x"], hit["y"])
                p.wait_for_timeout(250)
            want = p.evaluate("(k) => window.__argus.R.eyes[k].id", hit["owner"]) if hit else None
            check("c. a tap on a red eye picks its light, opens the explanation and the lights tab",
                  hit is not None and p.evaluate("window.__argus.sel") == want and p.evaluate("window.__argus.tab") == "all" and p.is_visible("#pick"), (hit, want))
            ctx.close()
            check("c. no errors with reduced motion and the tap", not errs, errs[:5])

            # offline: the last good copy, "as of"
            errs = []
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            p = ctx.new_page()
            p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
            p.goto(ok_url + Q)
            wait_ready(p)
            p.route(re.compile(r".*/(home|data)\.json.*"), lambda r: r.abort())
            p.goto(ok_url + "?now=2026-11-04T18:30:00-05:00")
            wait_ready(p)
            check("c. offline with a saved copy: the OFFLINE tag, 'as of' the time it was saved, and no false alarm from the old clock (still ALL CLEAR)",
                  p.is_visible("#offtag") and "Offline" in p.inner_text("#sub") and "Offline, as of" in p.inner_text("#vline") and p.inner_text("#vk") == "All clear" and p.evaluate("window.__argus.offline"), p.inner_text("#vline"))
            ctx.close()
            bad = tidy_errors(errs)
            check("c. offline: no page errors", not bad, bad[:3])

            # no data at all
            errs = []
            ctx, p = open_page(br, none_url + Q, errs, "__argus")
            check("c. nothing published at all: 'NO DATA YET' (never ALL CLEAR), grey eyes, a plain sentence",
                  p.inner_text("#vk") == "No data yet" and p.get_attribute("#verdict", "data-level") == "idle" and "Wi-Fi" in p.inner_text("#vline")
                  and p.evaluate("window.__argus.levels.every(l => l === 'idle')") and p.is_visible("#offtag"))
            tab(p, "all")
            check("c. ... and the lights tab lists the apps as 'no card'", "no card" in p.inner_text("#p-all"))
            ctx.close()
            bad = tidy_errors(errs, allow=("home.json", "data.json", "jarvis.json", "status.json"))
            check("c. no data: only the missing files' 404s, nothing else", not bad, bad[:5])
            br.close()
    finally:
        for s in (srv1, srv2, srv3):
            s.shutdown()


def main(argv):
    fast = "fast" in argv
    tmp = tempfile.mkdtemp(prefix="argus_test_")
    try:
        part_a()
        if not fast:
            part_c(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
