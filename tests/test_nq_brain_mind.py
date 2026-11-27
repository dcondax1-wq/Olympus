"""NQ BRAIN · the mind layer (night-nq-brain 2026-11-27): tools/web_public/nq/brainmind.js + brainmind.css on the NQ Brain page.
On the PC's real post (tests/fixtures/truth/pc_post.json) + the site's brain/learn.json, the same mocks as tests/test_nq_brain.py.
  a. static   the files, brain.html loads them (brain.js stays ?v=7), OLYMPUS NIGHT palette, no cyan / brown / olive, text only (no innerHTML /
              eval / storage), GET of ../brain/learn.json only, reduced motion handled
  b. 390x844  'Thinking right now' = both bots from the PC's post (Zlarior step 5/10 5m CISD, ATLAS MACD armed); the pipeline canvas animates,
              8 gates in words, the PC's live step marked NOW (5m CISD -> 'Limit armed'), the newest analysed session's setups listed; ATLAS's 3
              members (MACD armed); every idea on trial as an n/20 ring with the S1 flag; lessons <= 7 with no repeats; live vs twin; health
              bands; BLITZ nowhere; no sideways scroll, taps >= 44 px, no console error, nothing off the origin
  c. 1440     a two-column dashboard: the 3D brain beside its steps, ATLAS's members beside the lessons, the ideas full width
  d. reduced motion: the pipeline drawn without a running animation; no learn.json: every card says why, no error
  f. Ask WHY (nq/ask.js): five questions answered only from the page's data, each with its data age
  e. nq/nqfeed.js (the shared fast feed): its kept post paints the page at once when the network has nothing, with the post's age
    python -X utf8 -m tests.test_nq_brain_mind [--static]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from tests import test_nq_brain as T  # noqa: E402

check = AK.check
NQ = os.path.join(AK.WEB, "nq")


def test_static():
    html = open(os.path.join(NQ, "brain.html"), encoding="utf-8").read()
    js = open(os.path.join(NQ, "brainmind.js"), encoding="utf-8").read()
    css = open(os.path.join(NQ, "brainmind.css"), encoding="utf-8").read()
    code = re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*", "", js + css, flags=re.S)
    check("a. brain.html loads the mind layer (brainmind.js / .css) after brain.js, which stays ?v=7; every mind card is in the page",
          'src="brainmind.js?v=' in html and 'href="brainmind.css?v=' in html and 'src="brain.js?v=7"' in html
          and all(f'id="{i}"' in html for i in ("mindNow", "mindPipe", "mindAtlas", "mindTrial", "mindLessons", "mindGap", "mindHealth", "mPipe", "mPipeList")))
    check("a. OLYMPUS NIGHT palette (violet glow, gold accents, mint up), no cyan / brown / olive",
          all(c in css for c in ("#9d59ee", "#f1c14b", "#77db89", "#16131e", "#3e255e", "#4d2e76"))
          and not re.search(r"cyan|brown|olive|#00ffff|#0ff\b|#8b4513|#808000|#6b8e23|#556b2f", code, re.I))
    check("a. text only, no storage, GET of ../brain/learn.json only, reduced motion handled",
          "innerHTML" not in code and "eval(" not in code and "localStorage" not in code and "POST" not in code
          and code.count("fetch(") == 1 and "'../brain/learn.json'" in js and "prefers-reduced-motion" in js and "prefers-reduced-motion" in css)


def test_ask_static():
    html = open(os.path.join(NQ, "brain.html"), encoding="utf-8").read()
    js = open(os.path.join(NQ, "ask.js"), encoding="utf-8").read()
    code = re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*", "", js, flags=re.S)
    check("f. Ask WHY: brain.html loads nq/ask.js + the card; data only (no fetch of its own, no AI call), text only, no storage",
          'src="ask.js?v=' in html and 'id="askCard"' in html and 'id="askQs"' in html and "fetch(" not in code and "innerHTML" not in code
          and "localStorage" not in code and not re.search(r"anthropic|openai|/v1/", code, re.I))


SNAP = """() => { const t = (id) => (document.getElementById(id) || {}).textContent || '';
  const M = window.NQMIND; return {
  now: [...document.querySelectorAll('#mNowBody .mnrow')].map((r) => r.innerText), meta: t('mNowMeta'),
  drawn: M.S.drawn, gates: [...document.querySelectorAll('#mPipeList .mst')].map((li) => li.className), sub: t('mPipeSub'), list: t('mPipeList'),
  atlas: [...document.querySelectorAll('#mAtlas .mmem')].map((x) => x.className.replace('mmem ', '')), rings: document.querySelectorAll('#mTrial .mring').length,
  s1: !!document.querySelector('#mTrial .mnew'), lessons: [...document.querySelectorAll('#mLessons li')].map((x) => x.innerText),
  gap: document.querySelectorAll('#mGap .mgap').length, bands: document.querySelectorAll('#mHealth .mband').length,
  mind: ['mindNow', 'mindPipe', 'mindAtlas', 'mindTrial', 'mindLessons', 'mindGap', 'mindHealth'].map(t).join('\\n'),
  w: document.getElementById('app').getBoundingClientRect().width,
  pos: Object.fromEntries(['brainCard', 'mindAtlas', 'mindLessons', 'mindTrial'].map((i) => { const r = document.getElementById(i).getBoundingClientRect(); return [i, [Math.round(r.left), Math.round(r.top), Math.round(r.width)]]; })),
  stage: getComputedStyle(document.querySelector('#brainCard .bstage')).gridTemplateColumns } }"""


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("b. page tests skipped: no Playwright", True)
        return
    from tests import test_nq_chart as NC, test_nq_page as NP
    real = NP.time.time
    NP.time.time = lambda: float(T.NOW)
    try:
        home = NP.home_json(3 * 3600)
    finally:
        NP.time.time = real
    core = json.dumps({"event": "message", "time": T.PC["reporter"]["t"], "message": json.dumps(T.PC)}) + "\n"
    learn = json.load(open(os.path.join(AK.WEB, "brain", "learn.json"), encoding="utf-8"))
    rules = [r for r in learn["learning"]["forward"]["rules"] if "blitz" not in (str(r.get("bot")) + r["id"]).lower()]

    def open_brain(p, q=""):
        p.goto(f"{origin}/nq/brain.html{q}")
        p.wait_for_function("window.NQBRAIN && window.NQBRAIN.ready() && window.NQMIND && window.NQMIND.ready()", timeout=60000)

    srv, origin = AK.serve({"/status_feed.json": NC.FEED, "/home.json": home})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, mock={f"/{NC.TOPIC}/json": core})
            p.clock.set_fixed_time(dt.datetime.fromtimestamp(T.NOW, dt.timezone.utc))
            open_brain(p)
            p.wait_for_function("document.querySelector('#bStatus').textContent.startsWith('From your PC') && document.querySelectorAll('#mNowBody .mnrow').length === 2", timeout=30000)
            p.wait_for_timeout(1200)
            s = p.evaluate(SNAP)
            p.wait_for_timeout(600)
            s["drawn2"] = p.evaluate("window.NQMIND.S.drawn")
            check("b. thinking right now: Zlarior at step 5/10 (5m CISD) and ATLAS's MACD armed, from the PC's post, with its report time",
                  s["now"][0].startswith("Zlarior") and "Step 5/10, 5m CISD" in s["now"][0] and s["now"][1].startswith("ATLAS") and "MACD" in s["now"][1]
                  and "PC report" in s["meta"], (s["now"], s["meta"]))
            check("b. the pipeline animates (frames drawn) and says its 8 gates in words; the PC's live step = NOW at 'Limit armed'; the newest session's setups listed",
                  s["drawn"] >= 1 and s["drawn2"] > s["drawn"] + 1 and len(s["gates"]) == 8 and [i for i, c in enumerate(s["gates"]) if "live" in c] == [4] and "taken" in s["gates"][7]
                  and "Now (PC): 5m CISD" in s["list"] and "8,784" in s["sub"] and re.search(r"Nov \d+: \d\d:\d\d (long|short)", s["list"]),
                  {k: s[k] for k in ("drawn", "drawn2", "gates", "sub", "list")})
            check("b. ATLAS's 3 members (EMA done, MACD armed, S/R)", len(s["atlas"]) == 3 and s["atlas"][1] == "armed", s["atlas"])
            check("b. every idea on trial (BLITZ hidden) as an n/20 ring; the new S1 forward flag marked", s["rings"] == len(rules) and s["s1"], (s["rings"], len(rules)))
            heads = [x.split("\n", 1)[-1].split(" - ")[0][:90] for x in s["lessons"]]
            check("b. lessons: up to 7, no lesson twice (FADED follow-ups folded)", 1 <= len(s["lessons"]) <= 7 and len(set(heads)) == len(heads), s["lessons"][:3])
            check("b. live vs twin rows and the health bands", s["gap"] >= 1 and s["bands"] >= 1, (s["gap"], s["bands"]))
            check("b. BLITZ nowhere in the mind layer (owner rule)", "BLITZ" not in s["mind"].upper())
            cls = p.evaluate("() => new Promise((ok) => { let v = 0; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) v += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {} setTimeout(() => ok(v), 300); })")
            check("b. 390: no sideways scroll, taps >= 44 px, no console error, nothing off the origin but the PC feed",
                  AK.no_sideways(p) and not AK.taps(p) and not errs and not off, (AK.taps(p)[:4], errs[:3], off[:3], cls))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=1440, h=900, mock={f"/{NC.TOPIC}/json": core})
            p.clock.set_fixed_time(dt.datetime.fromtimestamp(T.NOW, dt.timezone.utc))
            open_brain(p)
            p.wait_for_timeout(800)
            d = p.evaluate(SNAP)
            P = d["pos"]
            check("c. 1440: a two-column dashboard (page > 1,000 px; ATLAS's members beside the lessons; the ideas full width; the 3D brain beside its steps)",
                  d["w"] > 1000 and P["mindAtlas"][1] == P["mindLessons"][1] and P["mindAtlas"][0] < P["mindLessons"][0]
                  and P["mindTrial"][2] > 1000 and len(d["stage"].split()) == 2 and AK.no_sideways(p) and not errs, (d["w"], P, d["stage"], errs[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True, mock={f"/{NC.TOPIC}/json": core})
            open_brain(p)
            p.wait_for_timeout(1500)
            a = p.evaluate("window.NQMIND.S.drawn")
            p.wait_for_timeout(1000)
            b = p.evaluate("window.NQMIND.S.drawn")
            anim = p.evaluate("getComputedStyle(document.querySelector('.mthink i')).animationName")
            check("d. reduced motion: the pipeline is drawn but not animated, the thinking dots still", a >= 1 and b - a <= 1 and anim == "none", (a, b, anim))
            ctx.close()
    finally:
        srv.shutdown()
    # the shared fast feed (nq/nqfeed.js, night-nq-speed): a stand-in NQ_FEED that keeps the PC's post; the network gives nothing
    fake = ("window.NQ_FEED = { _cbs: [], cached: function () { return JSON.parse(JSON.stringify(%s)); }, "
            "on: function (cb) { this._cbs.push(cb); return function () {}; }, age: function () { return { text: '5 min ago', level: 'ok' }; } };") % json.dumps(T.PC)
    srv, origin = AK.serve({"/status_feed.json": NC.FEED, "/home.json": home, "/nq/nqfeed.js": fake})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, mock={f"/{NC.TOPIC}/json": "{}"})
            p.clock.set_fixed_time(dt.datetime.fromtimestamp(T.NOW, dt.timezone.utc))
            open_brain(p)
            p.wait_for_timeout(800)
            f = p.evaluate("() => ({ st: document.querySelector('#bStatus').textContent, now: [...document.querySelectorAll('#mNowBody .mnrow')].map((r) => r.innerText), meta: document.querySelector('#mNowMeta').textContent })")
            check("e. the shared fast feed (nqfeed.js): with no network post, the kept post paints at once (Zlarior step 5/10) with its age",
                  f["st"].startswith("From your PC") and "Step 5/10" in f["now"][0] and "(5 min ago)" in f["meta"] and not errs, (f, errs[:3]))
            ctx.close()
    finally:
        srv.shutdown()
    # Ask WHY: every question answered from the page's data, each with its data age
    srv, origin = AK.serve({"/status_feed.json": NC.FEED, "/home.json": home})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, mock={f"/{NC.TOPIC}/json": core})
            p.clock.set_fixed_time(dt.datetime.fromtimestamp(T.NOW, dt.timezone.utc))
            open_brain(p)
            p.wait_for_function("window.NQASK && window.NQASK.ready() && document.querySelector('#bStatus').textContent.startsWith('From your PC')", timeout=30000)
            A = {}
            for q in ("notrade", "next", "accounts", "learned", "pc"):
                p.locator(f'#askQs button[data-q="{q}"]').click()
                p.wait_for_timeout(150)
                A[q] = p.evaluate("document.getElementById('askA').innerText")
            check("f. why no trade: Zlarior at step 5 of 10 (5m CISD) + only setups up to now; ATLAS DID trade today (its 03:45 short)",
                  "step 5 of 10 (5m CISD)" in A["notrade"] and "15:50" not in A["notrade"] and "It DID trade today: short at 3:45 AM" in A["notrade"], A["notrade"])
            check("f. next trade: the open window, the 5m CISD's next rule, ATLAS's armed MACD", "window open" in A["next"].lower() and "What moves it on" in A["next"]
                  and "MACD is ARMED" in A["next"], A["next"])
            check("f. accounts: Zlarior 50K needs $3,807 more to pass; funded ATLAS by its payout line (no contradicting eval line)",
                  "Zlarior 50K: needs $3,807 more to pass" in A["accounts"] and "ATLAS payout" in A["accounts"] and "ATLAS: needs" not in A["accounts"], A["accounts"])
            check("f. learned: this week's lessons from learn.json; PC: 'Nothing wrong' when every check is green",
                  "lessons in the 7 days" in A["learned"] and "Nothing wrong: every check the PC sends is green" in A["pc"], (A["learned"][:200], A["pc"][:200]))
            check("f. every answer ends with its data age; BLITZ never; no console error; taps >= 44 px",
                  all("Data:" in v for v in A.values()) and "PC report" in A["notrade"] and "BLITZ" not in " ".join(A.values()).upper()
                  and not errs and not AK.taps(p), ([v[-120:] for v in A.values()], errs[:2], AK.taps(p)[:3]))
            ctx.close()
    finally:
        srv.shutdown()
    srv, origin = AK.serve({"/status_feed.json": NC.FEED, "/home.json": home, "/brain/learn.json": None})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, mock={f"/{NC.TOPIC}/json": "{}"})
            open_brain(p)
            p.wait_for_timeout(800)
            t = p.evaluate("() => ['mPipeList', 'mTrial', 'mLessons', 'mGap', 'mHealth'].map((i) => document.getElementById(i).textContent)")
            check("d. no learn.json: every learning card says why (no funnel / no idea / no lessons / no audit / no bands), no error",
                  "has not written its funnel" in t[0] and "No idea is on trial" in t[1] and "No lessons" in t[2] and "has not run" in t[3]
                  and "not been built" in t[4] and not errs, (t, errs[:3]))
            ctx.close()
    finally:
        srv.shutdown()


def main():
    test_static()
    test_ask_static()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()


if __name__ == "__main__":
    main()
