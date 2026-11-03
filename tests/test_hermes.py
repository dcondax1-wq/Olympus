"""HERMES, OLYMPUS Wrapped (tools/hermes/ builds wrapped.json + jarvis.json, tools/web_public/hermes/ tells it as stories).
  a. the builder on the fixture (tools/hermes/fixture.py): deterministic, the $ sums by hand (week / month / all, per bot,
     won / lost, $ per month), the paper twin never counted twice, best / worst trade + lesson, discipline, eval, odds,
     learned, next goal; edge cases (no data, paper only, broken rules, last week early on a Monday)
  b. the Jarvis card (docs/JARVIS_APPS.md): every limit, plain text, "This week: +$X", theme
  c. publish(site) and the site build's hook (tools/build_web_dashboard.py), the committed demo files are the fixture's
  d. static page rules: safe areas, the orb's corner, reduced motion, no CDN, no sideways overflow rules
  e. the page in Chromium at 390 x 844: no errors, swipe / tap / keys move through the cards, periods, counters, the share
     button makes a PNG blob, nothing past the 16 px gutter or in the orb's 80 x 160 corner, no sideways scroll, peers
     (Fates odds, Data City, Kalshi, Planner) and escaping, reduced motion, screenshots to research/handoff/2026-11-03/hermes/
    python -X utf8 -m tests.test_hermes            (temp folders + a local server; nothing else touched)
HERMES_NO_BROWSER=1 skips part e.
"""
from __future__ import annotations

import copy
import functools
import glob
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.hermes import build, fixture, wrapped  # noqa: E402

PAGE = os.path.join(ROOT, "tools", "web_public", "hermes")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-03", "hermes")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def demo():
    return wrapped.build(fixture.data(), fixture.home(), None, now=fixture.NOW, demo=True)


# ------------------------------------------------------------------------------------------------ a. the builder
def part_a():
    w1, w2 = demo(), demo()
    check("a. deterministic: the same input twice gives the same bytes", build.dumps(w1) == build.dumps(w2))
    rt = wrapped.build(json.loads(json.dumps(fixture.data())), json.loads(json.dumps(fixture.home())), None, now=fixture.NOW, demo=True)
    check("a. deterministic through a JSON round trip (the cloud reads data.json from disk)", build.dumps(rt) == build.dumps(w1))
    wk, mo, al = (w1["periods"][k] for k in ("week", "month", "all"))
    check("a. week: Mon Oct 26 - Sun Nov 1, 'This week'", (wk["from"], wk["to"], wk["label"]) == ("2026-10-26", "2026-11-01", "This week"), wk["label"])
    check("a. week $: net +$2,072.50 on 5 trades, 3 won / 2 lost, won +$2,462.50, lost -$390.00",
          (wk["net"], wk["trades"], wk["wins"], wk["losses"], wk["won_usd"], wk["lost_usd"]) == (fixture.WEEK_NET, fixture.WEEK_TRADES, 3, 2, 2462.5, -390.0), wk)
    check("a. week per bot: Zlarior +$1,982.50 (3), ATLAS +$90.00 (2), sums to the net",
          [(b["name"], b["net"], b["trades"]) for b in wk["bots"]] == [("Zlarior", 1982.5, 3), ("ATLAS", 90.0, 2)]
          and round(sum(b["net"] for b in wk["bots"]), 2) == wk["net"], wk["bots"])
    check("a. the paper twin is listed, never counted (the PC has trades)",
          wk["paper_twin"] == {"net": 1982.5, "trades": 3} and not any(b["paper"] for b in wk["bots"]) and wk["paper_only"] is False, wk["paper_twin"])
    by_hand = round(sum(r[8] for r in fixture.LIT + fixture.ATLAS if r[0] >= "2026-10-01"), 2)
    check("a. month = every October trade by hand; all time = every trade",
          mo["net"] == by_hand and al["net"] == round(sum(r[8] for r in fixture.LIT + fixture.ATLAS), 2) and mo["trades"] == len(fixture.LIT + fixture.ATLAS),
          (mo["net"], by_hand, al["net"]))
    check("a. $ per month: net / weekdays so far x 21 (week 2,072.50 / 5 x 21 = 8,704.50; month / 22 weekdays to Oct 30)",
          wk["per_month"] == 8704.5 and mo["per_month"] == round(mo["net"] / 22 * 21, 2), (wk["per_month"], mo["per_month"]))
    check("a. per-day P&L sums to the net and the equity ends on it",
          round(sum(v for _, v in wk["days"]), 2) == wk["net"] and wk["equity"][-1] == wk["net"] and [d for d, _ in wk["days"]] == sorted(d for d, _ in wk["days"]), wk["days"])
    b, x = wk["best"], wk["worst"]
    check("a. best trade: Zlarior +$1,912.50 Thu Oct 29 09:47 SHORT 8R, its replay from the site's 5m bars",
          (b["bot"], b["pnl"], b["day"], b["time"], b["side"], b["r"], b["spark"]["kind"]) == ("Zlarior", 1912.5, "2026-10-29", "09:47", "SHORT", 8.0, "bars")
          and len(b["spark"]["points"]) >= 4, b)
    check("a. worst trade: -$240.00 Tue Oct 27, schematic path (no bars that day), the Mind's lesson for that trade",
          (x["pnl"], x["day"], x["spark"]["kind"]) == (-240.0, "2026-10-27", "schematic") and x["lesson"].startswith("A wick took the stop"), x)
    d = wk["discipline"]
    check("a. discipline: 5 rules checked on the week, all kept = 100",
          d["score"] == 100 and [r["id"] for r in d["rules"]] == ["one_a_day", "stop", "window", "flat", "hands_off"] and d["kept"] == d["checked"] == 19, d)
    ev = w1["eval"]
    check("a. eval: Zlarior 50K +$2,170.50 of $3,000 ($829.50 to go, room $2,070.50), ATLAS 25K; the paper twin has no eval ring",
          [(e["bot"], e["profit"], e["target"], e["to_target"], e["room"]) for e in ev] == [("Zlarior", 2170.5, 3000.0, 829.5, 2070.5), ("ATLAS", 90.0, 1500.0, 1410.0, 850.0)]
          and abs(ev[0]["progress"] - 2170.5 / 3000) < 1e-3, ev)
    check("a. odds: the backtest's H2 two-week pass / fail at the live sizing", w1["odds"] and (w1["odds"]["p10"], w1["odds"]["f10"], w1["odds"]["span"]) == (58.6, 20.9, "H2"), w1["odds"])
    L = w1["learned"]
    check("a. learned: the Mind's lessons and proposal, the live-vs-twin gap with the bot's name (lit -> Zlarior), at most 4",
          len(L) == 4 and L[0]["tag"] == "Mind · Zlarior" and L[2]["tag"] == "Mind · research" and "Zlarior made +$1,983 live vs +$2,040" in L[3]["text"], L)
    check("a. next goal: bank what is left on the 50K", w1["next"]["goal"] == "Bank $830 to pass the Builder 50K", w1["next"])
    check("a. wrapped.json is small (< 16 KB)", len(build.dumps(w1).encode()) < 16 * 1024, len(build.dumps(w1)))

    # edge cases
    e = wrapped.build({}, None, None, now=fixture.NOW)
    check("a. no data: zeros, no best / worst, discipline None, the same three periods",
          all(e["periods"][k]["trades"] == 0 and e["periods"][k]["net"] == 0 and e["periods"][k]["best"] is None
              and e["periods"][k]["discipline"]["score"] is None for k in ("week", "month", "all")) and e["eval"] == [], e["periods"]["week"])
    po = fixture.data()
    po["accounts"] = [a for a in po["accounts"] if a["id"] == "cloud_paper"]
    p = wrapped.build(po, None, None, now=fixture.NOW)["periods"]["week"]
    check("a. paper only: the twin counts, marked paper, no twin line", p["paper_only"] and p["trades"] == 3 and p["net"] == 1982.5
          and p["bots"][0]["paper"] and p["paper_twin"] is None and p["best"]["paper"], p)
    br = fixture.data()
    lit = br["accounts"][0]["trades"]
    extra = copy.deepcopy(lit[-1])                                   # a 2nd Zlarior trade on Fri, 16:05 -> 16:20, closed by hand
    extra.update(entry_t=fixture.ts("2026-10-30", "16:05"), exit_t=fixture.ts("2026-10-30", "16:20"), exit="MANUAL", pnl=-55.0, r=-0.3)
    lit.append(extra)
    wb = wrapped.build(br, None, None, now=fixture.NOW)
    db = {r["id"]: r for r in wb["periods"]["week"]["discipline"]["rules"]}
    check("a. broken rules are caught: 2 trades on a day, an entry at 16:05, an exit at 16:20, a manual exit",
          not db["one_a_day"]["ok"] and db["window"]["kept"] == 3 and db["window"]["total"] == 4 and not db["flat"]["ok"]
          and db["hands_off"]["kept"] == 5 and db["hands_off"]["total"] == 6 and wb["periods"]["week"]["discipline"]["score"] < 100, db)
    check("a. the manual exit's lesson says hands off; the next goal is the first broken rule",
          wb["periods"]["week"]["worst"]["pnl"] == -240.0 and wb["next"]["goal"] == 'Keep "1 trade a day" every time', wb["next"])
    check("a. a wrong-side stop fails 'Stop beyond the sweep'",
          wrapped.discipline([{**lit[0], "stop": lit[0]["entry"] + 5, "bot": "Zlarior", "account_id": "x", "orders": []}])["rules"][1]["ok"] is False)
    mon = wrapped.build(fixture.data(), None, None, now=fixture.ts("2026-11-02", "09:00"))["periods"]["week"]
    check("a. Monday morning with no trade yet: the recap is last week, labelled so",
          (mon["label"], mon["from"], mon["net"]) == ("Last week", "2026-10-26", fixture.WEEK_NET), (mon["label"], mon["from"]))
    sat = wrapped.build(fixture.data(), None, None, now=fixture.ts("2026-10-31", "12:00"))["periods"]["week"]
    check("a. Saturday is still 'This week' (the calendar day in New York)", sat["label"] == "This week" and sat["net"] == fixture.WEEK_NET, sat["label"])
    check("a. money format: whole dollars half up, ASCII minus", (wrapped.usd(2072.5), wrapped.usd(-0.4), wrapped.usd(-1234.5), wrapped.usd(0)) == ("+$2,073", "$0", "-$1,235", "$0"))
    nb = fixture.data()
    nb["live"]["bars"] = []
    sp = wrapped.build(nb, None, None, now=fixture.NOW)["periods"]["week"]["best"]["spark"]
    check("a. no bars: the best trade's path is schematic: entry, its best point (mfe x risk), exit",
          sp["kind"] == "schematic" and sp["points"] == [25412.0, round(25412.0 - 8.0 * 23.75, 2), 25222.0], sp)


# ------------------------------------------------------------------------------------------------ b. the Jarvis card
def part_b():
    for name, w in (("demo", demo()), ("real", wrapped.build(fixture.data(), None, None, now=fixture.NOW)),
                    ("empty", wrapped.build({}, None, None, now=fixture.NOW))):
        c = wrapped.jarvis_card(w)
        s = json.dumps(c, ensure_ascii=False)
        texts = [c["name"], c["status"]["label"]] + [k["label"] for k in c["kpis"]] + [str(k["value"]) for k in c["kpis"]] + c["lines"]
        ok = (c["v"] == 1 and c["name"] == "HERMES" and c["status"]["level"] in ("ok", "warn", "bad", "off") and len(c["status"]["label"]) <= 48
              and len(c["kpis"]) <= 3 and all(len(k["label"]) <= 20 and len(str(k["value"])) <= 24 for k in c["kpis"])
              and len(c["lines"]) <= 3 and all(len(x) <= 120 for x in c["lines"]) and isinstance(c["t"], int) and c["t"] == fixture.NOW
              and re.fullmatch(r"#[0-9a-f]{6}", c["theme"]) and c["open"] == "#week" and len(s.encode()) <= 8 * 1024
              and not any(re.search(r"<[a-z/!]|&[a-z#0-9]+;|[\r\n]", x) for x in texts))
        check(f"b. Jarvis card ({name}) keeps every rule of the contract", ok, c)
    c = wrapped.jarvis_card(wrapped.build(fixture.data(), None, None, now=fixture.NOW))
    check("b. the card says 'This week: +$2,073', green, with $ per month and the best trade",
          c["status"] == {"level": "ok", "label": "This week: +$2,073"} and c["kpis"][0] == {"label": "This week", "value": "+$2,073"}
          and c["kpis"][1]["label"] == "Per month" and "a month at this pace" in c["lines"][0] and c["lines"][1].startswith("Best: Zlarior +$1,913"), c)
    check("b. demo card is grey 'Demo data'; no trades is grey 'No trades yet'",
          wrapped.jarvis_card(demo())["status"]["level"] == "off" and wrapped.jarvis_card(wrapped.build({}, now=fixture.NOW))["status"]["label"] == "No trades yet")


# ------------------------------------------------------------------------------------------------ c. publish + site build
def part_c():
    tmp = tempfile.mkdtemp(prefix="le_hermes_pub_")
    try:
        check("c. publish: a site without data.json keeps the demo (None)", build.publish(tmp, now=fixture.NOW) is None and not os.path.exists(os.path.join(tmp, "hermes")))
        with open(os.path.join(tmp, "data.json"), "w", encoding="utf-8") as fh:
            json.dump(fixture.data(), fh)
        with open(os.path.join(tmp, "home.json"), "w", encoding="utf-8") as fh:
            json.dump(fixture.home(), fh)
        res = build.publish(tmp, now=fixture.NOW)
        w = json.load(open(os.path.join(tmp, "hermes", "wrapped.json"), encoding="utf-8"))
        j = json.load(open(os.path.join(tmp, "hermes", "jarvis.json"), encoding="utf-8"))
        check("c. publish writes hermes/wrapped.json (not demo) + jarvis.json, no temp file left",
              res and w["demo"] is False and w["periods"]["week"]["net"] == fixture.WEEK_NET and j["kpis"][0]["value"] == "+$2,073"
              and sorted(os.listdir(os.path.join(tmp, "hermes"))) == ["jarvis.json", "wrapped.json"], (res, os.listdir(os.path.join(tmp, "hermes"))))
        live = os.path.join(tmp, "live.json")
        with open(live, "w", encoding="utf-8") as fh:
            json.dump({"kind": "le-live", "pc": {"mind": {"reviews": [{"bot": "Zlarior", "lesson": "Fresh from the PC."}]}}}, fh)
        build.publish(tmp, now=fixture.NOW, live_path=live)
        w = json.load(open(os.path.join(tmp, "hermes", "wrapped.json"), encoding="utf-8"))
        check("c. --live: the PC's live.json Mind lessons come first", w["learned"][0]["text"] == "Fresh from the PC.", w["learned"][:1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    d = build.dumps(build.demo())
    same = all(open(os.path.join(PAGE, f), encoding="utf-8").read() == d for f in ("demo.json", "wrapped.json"))
    check("c. the committed demo.json / wrapped.json are the fixture's (python -m tools.hermes.build --demo)", same)
    check("c. the committed jarvis.json is the demo card", json.load(open(os.path.join(PAGE, "jarvis.json"), encoding="utf-8")) == wrapped.jarvis_card(build.demo()))
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    check("c. the site build publishes hermes/ with the other apps",
          'for app in ("jarvis", "kalshi", "datacity", "mind", "tree", "oracle", "odeon", "fates", "hermes"):' in b)
    m = re.search(r"\n(\s*)try:\n\s*from tools\.hermes import build as _hermes\n\s*print\(\"  hermes:\", _hermes\.publish\(out\)\)\n\s*except Exception", b)
    check("c. the site build runs hermes.publish(out) inside try / except (a failure never stops the publish)", bool(m))
    check("c. the builder never imports trading code and never reads live_model*.json",
          not any(re.search(r"^\s*(from engine|import engine)|live_model", open(os.path.join(ROOT, "tools", "hermes", f), encoding="utf-8").read(), re.M)
                  for f in ("wrapped.py", "build.py", "fixture.py")))


# ------------------------------------------------------------------------------------------------ d. static page rules
def part_d():
    html = open(os.path.join(PAGE, "index.html"), encoding="utf-8").read()
    css = open(os.path.join(PAGE, "hermes.css"), encoding="utf-8").read()
    js = "".join(open(f, encoding="utf-8").read() for f in glob.glob(os.path.join(PAGE, "*.js")))
    code = re.sub(r"^\s*//.*$", "", js, flags=re.M)                  # without the comments
    check("d. viewport-fit=cover, theme-color, dark scheme, a module script", 'viewport-fit=cover' in html and 'name="theme-color" content="#12081f"' in html
          and 'name="color-scheme" content="dark"' in html and '<script type="module" src="app.js">' in html)
    check("d. safe areas on all four sides", all(f"env(safe-area-inset-{s}" in css for s in ("top", "right", "bottom", "left")))
    check("d. the orb's corner: content ends 160 px above the bottom, the footer keeps 96 px from the right",
          "--bot: calc(var(--sb) + 160px)" in css and re.search(r"\.foot \{[^}]*right: calc\(var\(--sr\) \+ 96px\)", css))
    check("d. prefers-reduced-motion in the CSS and the script", "@media (prefers-reduced-motion: reduce)" in css and "prefers-reduced-motion: reduce" in js)
    urls = set(re.findall(r"https?://[^\s'\"`)]+", html + css + js))
    allowed = {"https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json",
               "https://api.github.com/repos/demetrades2000-coder/kalshi-feed/contents/kalshi.json?ref=main", "https://demetrades2000-coder.github.io"}
    check("d. no CDN, no other site: only the Kalshi feed and Jarvis's origin", urls <= allowed, urls - allowed)
    check("d. Safari 16 safe: no lookbehind, no Array copy methods, no Object.groupBy, no AbortSignal.timeout",
          not re.search(r"\(\?<[=!]|\.toSorted\(|\.toReversed\(|\.toSpliced\(|\.with\(|Object\.groupBy|AbortSignal\.timeout", code))
    check("d. only transform / opacity / stroke animate (no layout transitions)",
          not re.search(r"transition:[^;]*\b(width|height|top|left|right|bottom|margin|padding)\b", css))


# ------------------------------------------------------------------------------------------------ e. the browser
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def make_site(tmp, w, peers=False, title="Tuesdays pay the most"):
    site = os.path.join(tmp, "nq-dashboard")
    shutil.copytree(PAGE, os.path.join(site, "hermes"))
    os.makedirs(os.path.join(site, "jarvis"))
    shutil.copy(os.path.join(ROOT, "tools", "web_public", "jarvis", "orbitron.woff2"), os.path.join(site, "jarvis"))
    if w is not None:
        with open(os.path.join(site, "hermes", "wrapped.json"), "w", encoding="utf-8") as fh:
            fh.write(build.dumps(w))
    if peers:
        os.makedirs(os.path.join(site, "fates"))
        json.dump({"v": 1, "name": "Fates", "status": {"level": "ok", "label": "On track"},
                   "kpis": [{"label": "Pass odds", "value": "64%"}], "t": fixture.NOW}, open(os.path.join(site, "fates", "jarvis.json"), "w"))
        os.makedirs(os.path.join(site, "datacity"))
        json.dump({"discoveries": [{"title": "Old one", "text": "older", "t": 1},
                                   {"title": title, "text": "Tuesday sweeps paid 2.1R on average since 2021.",
                                    "usd": 1840, "t": fixture.NOW}]}, open(os.path.join(site, "datacity", "discoveries.json"), "w"))
    return site


KALSHI = {"name": "Kalshi Edge v2", "running": True, "balance": 68.42, "week_pnl": 7.25, "total_pnl": 18.4, "t": fixture.NOW,
          "days": [["2026-10-27", 3.5], ["2026-10-29", -1.25], ["2026-10-30", 5.0]],
          "strategies": [{"name": "15-min favourites", "total_pnl": 12.1, "wins": 27, "losses": 14}, {"name": "Gold 5 PM", "total_pnl": 6.3, "wins": 7, "losses": 5}]}
PLANNER = {"tasks": [{"title": "Review the week", "date": "2026-10-28", "done": True}, {"title": "Gym", "date": "2026-10-29", "done": True},
                     {"title": "Call the bank", "date": "2026-10-30", "done": False}],
           "events": [{"title": "Class", "date": "2026-10-27"}], "habits": [{"name": "Read", "log": ["2026-10-26", "2026-10-28", "2026-10-29"]}]}

INIT = """
(() => {
  window.__shared = null;
  navigator.canShare = () => true;
  navigator.share = async (d) => {
    const f = d.files[0], b = new Uint8Array(await f.slice(0, 8).arrayBuffer());
    window.__shared = { type: f.type, size: f.size, name: f.name, sig: Array.from(b) };
  };
})();
"""

OVERFLOW = """() => {
  const W = innerWidth, H = innerHeight, bad = [];
  const card = document.querySelector('.card.on');
  if (!card) return ['no card'];
  for (const el of card.querySelectorAll('*')) {
    if ((el.closest('svg') && el.tagName.toLowerCase() !== 'svg') || el.classList.contains('tilt')) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.right > W - 16 + 0.5 || r.left < 16 - 0.5) bad.push('gutter ' + el.className + ' ' + Math.round(r.left) + '-' + Math.round(r.right));
    if (r.right > W - 80 && r.bottom > H - 160) bad.push('orb ' + el.className + ' ' + Math.round(r.right) + ',' + Math.round(r.bottom));
  }
  if (document.documentElement.scrollWidth > W || document.body.scrollWidth > W) bad.push('scroll ' + document.documentElement.scrollWidth);
  return bad;
}"""


def run_browser():
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOTS, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="le_hermes_page_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/hermes/"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])

            def page(kalshi=None, reduced=False, planner=None, expect=(), slow_kalshi=False):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True,
                                     reduced_motion="reduce" if reduced else "no-preference")
                ctx.add_init_script(INIT)
                if slow_kalshi:                                      # the feed answers 1.5 s after the deck started (inside data.js's 4 s limit)
                    ctx.add_init_script("""(() => { const f = window.fetch.bind(window);
                      window.fetch = (u, o) => String(u).includes('kalshi-feed') ? new Promise((ok) => { const t = setInterval(() => { if (window.HERMES && HERMES.state().n > 0) { clearInterval(t); setTimeout(ok, 1500); } }, 50); }).then(() => f(u, o)) : f(u, o); })();""")
                if planner:
                    ctx.add_init_script(f"localStorage.setItem('planner.v1', {json.dumps(json.dumps(planner))});")
                cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"}   # as GitHub sends
                # no request leaves the machine: the Kalshi feed from the stub, anything else off-site a 404
                ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(kalshi), headers=cors)
                          if kalshi and "kalshi-feed" in r.request.url else r.fulfill(status=404, body="not found", headers=cors))
                p = ctx.new_page()
                p.errs, p.bad = [], []
                p.on("pageerror", lambda e: p.errs.append(str(e)))
                p.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and p.errs.append(m.text))
                expected = ("/fates/jarvis.json", "/datacity/discoveries.json", "kalshi-feed", "favicon") + tuple(expect)
                p.on("response", lambda r: r.status >= 400 and not any(x in r.url for x in expected) and p.bad.append(f"{r.status} {r.url}"))
                return ctx, p

            def ready(p, url):
                p.goto(url)
                p.wait_for_function("window.HERMES && HERMES.state().n > 0", timeout=15000)
                p.wait_for_timeout(300)

            st = lambda p: p.evaluate("HERMES.state()")  # noqa: E731

            # ---- the demo (no wrapped.json published: the demo.json fallback)
            site = make_site(tmp, None)
            os.remove(os.path.join(site, "hermes", "wrapped.json"))
            ctx, p = page(expect=("/hermes/wrapped.json",))            # its 404 is the point of this part
            ready(p, base)
            s0 = st(p)
            check("e. no wrapped.json: the demo, with the DEMO badge, starts on the money card",
                  s0["demo"] and s0["id"] == "money" and s0["i"] == 0 and p.is_visible("#demo"), s0)
            p.wait_for_timeout(1700)
            check("e. the money counter lands on +$2,072.50", p.inner_text(".card.on .count") == "+$2,072.50", p.inner_text(".card.on .count"))
            check("e. the progress bar fills while the card shows", p.evaluate("parseFloat(getComputedStyle(document.querySelector('#prog i')).transform.split(',')[0].replace('matrix(',''))") > 0.05)
            p.screenshot(path=os.path.join(SHOTS, "01_money.jpg"), type="jpeg", quality=82)
            p.mouse.move(320, 420); p.mouse.down(); p.mouse.move(80, 430, steps=6); p.mouse.up()
            p.wait_for_timeout(250)
            s1 = st(p)
            check("e. swipe left: the next card (best trade)", s1["i"] == 1 and s1["id"] == "best", s1)
            p.mouse.move(80, 420); p.mouse.down(); p.mouse.move(330, 420, steps=6); p.mouse.up()
            p.wait_for_timeout(250)
            check("e. swipe right: back to the money card", st(p)["i"] == 0, st(p))
            p.mouse.click(330, 500); p.wait_for_timeout(200)
            check("e. tap the right side: next", st(p)["i"] == 1, st(p))
            p.mouse.click(40, 500); p.wait_for_timeout(200)
            check("e. tap the left side: back", st(p)["i"] == 0, st(p))
            p.keyboard.press("ArrowRight"); p.wait_for_timeout(200)
            check("e. arrow right: next", st(p)["i"] == 1, st(p))
            p.touchscreen.tap(340, 500); p.wait_for_timeout(250)
            check("e. a finger tap: next (worst trade)", st(p)["id"] == "worst", st(p))
            p.evaluate("HERMES.go(0)")
            p.mouse.move(300, 500); p.mouse.down(); p.wait_for_timeout(600)
            held = st(p)["paused"]
            p.mouse.up(); p.wait_for_timeout(150)
            check("e. hold = pause, release = go on, same card", held and not st(p)["paused"] and st(p)["i"] == 0, st(p))
            ids, overflow, teaser = [], {}, ""
            n = st(p)["n"]
            for i in range(n):
                p.evaluate(f"HERMES.go({i}); HERMES.pause(true)")
                p.wait_for_timeout(2300)
                cid = st(p)["id"]
                ids.append(cid)
                bad = p.evaluate(OVERFLOW)
                if bad:
                    overflow[cid] = bad[:4]
                if cid == "kalshi":
                    teaser = p.inner_text(".card.on")
                p.screenshot(path=os.path.join(SHOTS, f"demo_{i + 1:02d}_{cid}.jpg"), type="jpeg", quality=82)
            check("e. the demo deck: money, best, worst, eval, discipline, learned, Kalshi teaser, next",
                  ids == ["money", "best", "worst", "eval", "discipline", "learned", "kalshi", "next"], ids)
            check("e. every card: inside the 16 px gutters, nothing in the orb's 80 x 160 corner, no sideways scroll", not overflow, overflow)
            check("e. without the Kalshi feed its card is a teaser", "COMING SOON" in teaser.upper() and "joins next" in teaser, teaser[:200])
            p.evaluate("HERMES.go(0)"); p.wait_for_timeout(300)
            p.click("#share")
            p.wait_for_function("window.__shared", timeout=10000)
            sh = p.evaluate("window.__shared")
            check("e. Share makes a PNG blob (image/png, PNG signature, > 20 KB) and hands it to the share sheet",
                  sh["type"] == "image/png" and sh["sig"] == [137, 80, 78, 71, 13, 10, 26, 10] and sh["size"] > 20_000 and sh["name"].endswith(".png"), sh)
            ls = p.evaluate("HERMES.lastShare")
            check("e. HERMES.lastShare names the card and the blob", ls and ls["type"] == "image/png" and ls["card"] == "money", ls)
            p.click(".periods button[data-k='month']"); p.wait_for_timeout(1900)
            mo = round(sum(r[8] for r in fixture.LIT + fixture.ATLAS), 2)
            check("e. Month: the deck restarts on October's money", st(p)["key"] == "month" and st(p)["i"] == 0
                  and p.inner_text(".card.on .count") == f"+${mo:,.2f}" and "month" in p.url, (st(p), p.inner_text(".card.on .count")))
            p.screenshot(path=os.path.join(SHOTS, "02_month.jpg"), type="jpeg", quality=82)
            check("e. no page errors, no failed request of the page's own files (demo)", not p.errs and not p.bad, (p.errs, p.bad))
            ctx.close()

            # ---- real data + every peer (Fates odds, Data City, Kalshi, Planner)
            shutil.rmtree(site)
            make_site(tmp, wrapped.build(fixture.data(), fixture.home(), None, now=fixture.NOW), peers=True)
            ctx, p = page(kalshi=KALSHI, planner=PLANNER)
            ready(p, base + "#week")
            p.wait_for_timeout(600)
            s = st(p)
            ids = []
            for i in range(s["n"]):
                p.evaluate(f"HERMES.go({i}); HERMES.pause(true)")
                p.wait_for_timeout(2200)
                ids.append(st(p)["id"])
                if ids[-1] in ("money", "eval", "discovery", "kalshi", "planner"):
                    p.screenshot(path=os.path.join(SHOTS, f"peers_{ids[-1]}.jpg"), type="jpeg", quality=82)
                bad = p.evaluate(OVERFLOW)
                if bad:
                    overflow[ids[-1]] = bad[:4]
                txt = p.inner_text(".card.on")
                if ids[-1] == "eval":
                    check("e. eval card: the Fates pass odds over the backtest's", "64%" in txt and "Pass odds" in txt and "Fates" in txt, txt[:300])
                if ids[-1] == "discovery":
                    check("e. Data City: the newest discovery with its $", "Tuesdays pay the most" in txt and "+$1,840.00" in txt
                          and "Tuesday sweeps paid 2.1R" in txt and "Old one" not in txt, txt[:300])
                if ids[-1] == "kalshi":
                    check("e. Kalshi: this week's +$7.25, balance, wins / losses, best strategy",
                          "+$7.25" in txt and "$68.42" in txt and "34 wins" in txt and "19 losses" in txt and "15-min favourites" in txt, txt[:300])
                if ids[-1] == "planner":
                    check("e. Planner: 2 tasks done, 1 open, 1 event, Read 3x", "Review the week" in txt and "Read" in txt and "3×" in txt, txt[:300])
                if ids[-1] == "money":
                    check("e. real data: no DEMO badge; the money card lists Kalshi beside the bots",
                          not p.is_visible("#demo") and "Kalshi Edge v2" in txt and "+$7.25" in txt and "Paper twin" in txt, txt[:400])
            check("e. with every peer: Data City, the real Kalshi and the Planner join the deck",
                  ids == ["money", "best", "worst", "eval", "discipline", "learned", "discovery", "kalshi", "planner", "next"], ids)
            check("e. peers' cards stay inside the gutters and out of the orb's corner", not overflow, overflow)
            p.evaluate("HERMES.go(1)"); p.wait_for_timeout(300)
            p.evaluate("window.__shared = null"); p.click("#share"); p.wait_for_function("window.__shared", timeout=10000)
            check("e. Share on the best trade: a PNG too", p.evaluate("window.__shared.type") == "image/png" and p.evaluate("HERMES.lastShare.card") == "best")
            check("e. no page errors, no failed request of the page's own files (real data + peers)", not p.errs and not p.bad, (p.errs, p.bad))
            ctx.close()

            # ---- a late peer: Kalshi answers after the deck started; the money card on screen gains its row in place
            ctx, p = page(kalshi=KALSHI, slow_kalshi=True)
            ready(p, base)
            p.evaluate("HERMES.pause(true)")
            before = p.inner_text(".card.on")
            p.wait_for_function("document.querySelector('.card.on').innerText.includes('Kalshi Edge v2')", timeout=12000)
            p.wait_for_timeout(200)
            after = p.inner_text(".card.on")
            check("e. Kalshi late: the money card on screen gains its Kalshi row in place (same card, numbers final)",
                  "Kalshi Edge v2" not in before and "Kalshi Edge v2" in after and st(p)["i"] == 0 and p.inner_text(".card.on .count") == "+$2,072.50", (before[-200:], after[-200:]))
            p.evaluate("HERMES.go(HERMES.state().ids.indexOf('kalshi'))"); p.wait_for_timeout(1900)
            check("e. Kalshi late: its card is the real one, not the teaser", st(p)["id"] == "kalshi" and "+$7.25" in p.inner_text(".card.on") and not p.errs, p.errs)
            ctx.close()

            # ---- escaping: an <img onerror> in every text of wrapped.json stays text, never runs
            evil = '<img src=x onerror="window.__x=1">'
            w = wrapped.build(fixture.data(), fixture.home(), None, now=fixture.NOW)
            wk = w["periods"]["week"]
            for b in wk["bots"]:
                b["name"] = evil
            wk["best"]["bot"] = wk["worst"]["bot"] = wk["best"]["exit"] = evil
            wk["worst"]["lesson"] = evil
            wk["label"] = evil
            for r in wk["discipline"]["rules"]:
                r["label"] = evil
            for x in w["learned"]:
                x["tag"] = x["text"] = evil
            w["eval"][0]["plan"] = w["eval"][0]["bot"] = evil
            w["next"] = {"goal": evil, "why": evil}
            shutil.rmtree(os.path.join(tmp, "nq-dashboard"))
            make_site(tmp, w, peers=True, title=evil)
            ctx, p = page()
            ready(p, base)
            seen = 0
            for i in range(st(p)["n"]):
                p.evaluate(f"HERMES.go({i}); HERMES.pause(true)")
                p.wait_for_timeout(500)
                seen += p.inner_text(".card.on").count("<img src=x")
            check("e. escaping: every text of wrapped.json and Data City is shown as text (bots, trades, lesson, rules, learned, eval, goal, discovery), nothing runs",
                  p.evaluate("window.__x") is None and seen >= 9 and not p.query_selector(".card img"), (seen, p.evaluate("window.__x")))
            check("e. no page errors with hostile text", not p.errs, p.errs)
            ctx.close()
            shutil.rmtree(os.path.join(tmp, "nq-dashboard"))
            make_site(tmp, None)                                          # the committed demo again

            # ---- auto-advance
            ctx, p = page()
            ready(p, base)
            p.wait_for_timeout(8600)
            check("e. a card moves on by itself after its time (money 8 s)", st(p)["i"] >= 1, st(p))
            ctx.close()

            # ---- reduced motion
            ctx, p = page(reduced=True)
            ready(p, base)
            s = st(p)
            check("e. reduced motion: no animation loop, the numbers shown at once, no auto-advance",
                  s["still"] and p.inner_text(".card.on .count") == "+$2,072.50" and p.evaluate("getComputedStyle(document.querySelector('.card.on .kt .w > span')).opacity") == "1", s)
            p.wait_for_timeout(8600)
            check("e. reduced motion: still on the first card after 8.6 s", st(p)["i"] == 0, st(p))
            p.keyboard.press("ArrowRight"); p.wait_for_timeout(100)
            check("e. reduced motion: taps / keys still move", st(p)["i"] == 1 and not p.errs, (st(p), p.errs))
            p.screenshot(path=os.path.join(SHOTS, "03_reduced_motion.jpg"), type="jpeg", quality=82)
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    if os.environ.get("HERMES_NO_BROWSER") != "1":
        run_browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
