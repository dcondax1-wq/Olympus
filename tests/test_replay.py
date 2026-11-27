"""NQ REPLAY THEATER (night 2026-11-27): tools/build_replay.py -> tools/web_public/nq/replay/, the page nq/replay.html + replay.js + replay.css.
  a. data     index.json + one file a day (the last 35 days): 5m bars of the session, events sorted by time, each LIT trade's steps in order (sweep 2 ->
              inducement 3 -> CISD 5 -> entry 8 -> exit), every exit with R and $, ATLAS members only EMA / MACD / S/R, BLITZ never, no account
              ids; the totals = the sum of the exits
  s. static   the page loads its files, OLYMPUS NIGHT palette, no cyan / brown / olive, text only (no innerHTML / eval / storage), GET only,
              the NQ Brain links to it
  b. 390x844  a trading day opens and plays (frames drawn, the clock moves); 60x to the end: the story = every event, LIT's steps lit
              through Exit, the totals = the day file's; 'next event' jumps; a deep link ?day= opens that day; no sideways scroll,
              taps >= 44 px, no console error, nothing off the origin
  c. a day with no bot event says so; reduced motion: no autoplay; 1440: the theater beside the story
    python -X utf8 -m tests.test_replay [--static]
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
NQ = os.path.join(AK.WEB, "nq")
RP = os.path.join(NQ, "replay")


def test_data():
    idx = json.load(open(os.path.join(RP, "index.json"), encoding="utf-8"))
    files = sorted(glob.glob(os.path.join(RP, "2026-*.json")))
    import datetime as _dt
    span = (_dt.date.fromisoformat(idx["to"]) - _dt.date.fromisoformat(idx["from"])).days
    check("a. index.json lists every day file (newest first), a recent window (<= 40 days)", len(idx["days"]) == len(files) >= 10 and span <= 40
          and [d["day"] for d in idx["days"]] == sorted([d["day"] for d in idx["days"]], reverse=True), (len(idx["days"]), len(files)))
    bad, order_bad, tot_bad, n_trades = [], [], [], 0
    blob = ""
    for f in files:
        txt = open(f, encoding="utf-8").read()
        blob += txt
        D = json.loads(txt)
        B, E = D["bars"], D["events"]
        if not (len(B) >= 60 and all(len(b) == 5 and b[2] >= max(b[1], b[4]) - 1e-6 and b[3] <= min(b[1], b[4]) + 1e-6 for b in B)):
            bad.append(D["day"])
        if [e["t"] for e in E] != sorted(e["t"] for e in E):
            order_bad.append(D["day"])
        by = {}
        for e in E:
            if e.get("bot") == "LIT" and e.get("id"):
                by.setdefault(e["id"], []).append(e)
        for sid, L in by.items():
            seq = [e.get("step") if e["kind"] != "exit" else "x" for e in L]
            n_trades += 1
            if seq != [2, 3, 5, 8, "x"] and seq != [2, 3, 5, 8]:
                order_bad.append(f"{D['day']} {sid} {seq}")
        lit = round(sum(e.get("usd") or 0 for e in E if e["kind"] == "exit" and e["bot"] == "LIT"), 2)
        if abs(lit - D["totals"]["lit_usd"]) > 0.01:
            tot_bad.append(D["day"])
    check("a. every day: >= 60 five-minute bars of the session, valid candles", not bad, bad[:3])
    check("a. events sorted by time; each LIT trade in step order (sweep 2 -> inducement 3 -> CISD 5 -> entry 8 -> exit)", not order_bad and n_trades >= 3, (order_bad[:3], n_trades))
    check("a. the totals = the sum of the exits", not tot_bad, tot_bad[:3])
    members = set(re.findall(r'"member":"([^"]+)"', blob))
    check("a. ATLAS members only EMA / MACD / S/R; BLITZ never; no account ids", members <= {"EMA", "MACD", "S/R"} and "blitz" not in blob.lower()
          and not re.search(r"\b(MFFU|FFN|APEX)[A-Z]*-?\d{3,}", blob), members)


def test_static():
    html = open(os.path.join(NQ, "replay.html"), encoding="utf-8").read()
    js = open(os.path.join(NQ, "replay.js"), encoding="utf-8").read()
    css = open(os.path.join(NQ, "replay.css"), encoding="utf-8").read()
    code = re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*", "", js + css, flags=re.S)
    check("s. the page loads replay.js / replay.css; the theater, the steps, the controls, the story", 'src="replay.js?v=' in html and 'href="replay.css?v=' in html
          and all(f'id="{i}"' in html for i in ("rDays", "rChart", "rSteps", "rPlay", "rNext", "rScrub", "rStory", "rNotes", "rTot")))
    check("s. OLYMPUS NIGHT palette, no cyan / brown / olive", all(c in css for c in ("#9d59ee", "#f1c14b", "#77db89", "#3e255e", "#4d2e76"))
          and not re.search(r"cyan|brown|olive|#00ffff|#0ff\b|#8b4513|#808000", code, re.I))
    check("s. text only, no storage, GET only (replay/index.json + replay/<day>.json), reduced motion handled",
          "innerHTML" not in code and "eval(" not in code and "localStorage" not in code and "POST" not in code and code.count("fetch(") == 1
          and "replay/index.json" in js and "prefers-reduced-motion" in js)
    check("s. the NQ Brain links to the Replay", 'href="replay.html"' in open(os.path.join(NQ, "brain.html"), encoding="utf-8").read())


SNAP = """() => { const R = window.NQREPLAY.S; return { day: R.day, p: R.p, frames: R.frames, playing: R.playing, clock: document.getElementById('rClock').textContent,
  story: document.querySelectorAll('#rStory li:not(.rnone)').length, events: (R.events || []).length, steps: [...document.querySelectorAll('#rSteps li')].map((l) => l.className),
  now: document.getElementById('rNow').textContent, tot: document.getElementById('rTot').innerText } }"""


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("b. page tests skipped: no Playwright", True)
        return
    idx = json.load(open(os.path.join(RP, "index.json"), encoding="utf-8"))
    tday = next(d for d in idx["days"] if any(True for _ in [0]) and d["trades"] and d["lit_usd"])
    D = json.load(open(os.path.join(RP, f"{tday['day']}.json"), encoding="utf-8"))
    empty = json.dumps({**D, "events": [], "notes": [], "totals": {"lit_usd": 0, "lit_r": 0, "atlas_usd": 0, "atlas_r": 0}})
    srv, origin = AK.serve({"/nq/replay/2099-01-02.json": empty})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/nq/replay.html?day={tday['day']}")
            p.wait_for_function("window.NQREPLAY && window.NQREPLAY.ready()", timeout=60000)
            p.wait_for_timeout(800)
            a = p.evaluate(SNAP)
            check("b. the deep-linked day opens and plays (frames drawn, the playhead moving)", a["day"] == tday["day"] and a["playing"] and a["frames"] > 3 and a["p"] > 0, a)
            p.locator('.rspeed .btn[data-x="60"]').click()
            p.wait_for_function("!window.NQREPLAY.S.playing", timeout=30000)
            z = p.evaluate(SNAP)
            check("b. at 60x to the day's end: the story = every event, LIT's steps lit through Exit",
                  z["story"] == z["events"] == len(D["events"]) and (z["steps"][-1] in ("win", "loss") or not any(e["bot"] == "LIT" and e["kind"] == "exit" for e in D["events"])), z)
            want = f"{'+' if D['totals']['lit_usd'] >= 0 else '-'}${abs(round(D['totals']['lit_usd'])):,}"
            check("b. the LIT total at the end = the day file's (closed trades)", want in z["tot"], (want, z["tot"]))
            p.evaluate("window.NQREPLAY.seek(0)")
            p.locator("#rNext").click()
            p.wait_for_timeout(200)
            n = p.evaluate(SNAP)
            n["story_txt"] = p.evaluate("document.getElementById('rStory').textContent")
            first = next(e for e in D["events"] if e["kind"] != "setup")
            same = [e["text"] for e in D["events"] if e["t"] == first["t"] or e["hm"] == first["hm"]]
            check("b. 'next event' jumps to the day's first bot event: it is in the story, the narration shows that bar's event",
                  n["story"] >= 1 and first["text"][:30] in n["story_txt"] and any(t[:30] in n["now"] for t in same), (n["now"], first["text"]))
            check("b. 390: no sideways scroll, taps >= 44 px, no console error, nothing off the origin",
                  AK.no_sideways(p) and not AK.taps(p) and not errs and not off, (AK.taps(p)[:4], errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.route("**/nq/replay/index.json", lambda r: r.fulfill(status=200, content_type="application/json",
                                                                  body=json.dumps({**idx, "days": [{"day": "2099-01-02", "bars": len(D["bars"]), "trades": 0, "setups": 0, "lit_usd": 0, "atlas_usd": 0, "events": 0}]})))
            p.goto(f"{origin}/nq/replay.html")
            p.wait_for_function("window.NQREPLAY && window.NQREPLAY.ready()", timeout=60000)
            p.wait_for_timeout(500)
            e = p.evaluate(SNAP)
            check("c. a day with no bot event says so plainly (the candles only)", "No bot event on this day" in e["now"] and not errs, (e["now"], errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True)
            p.goto(f"{origin}/nq/replay.html?day={tday['day']}")
            p.wait_for_function("window.NQREPLAY && window.NQREPLAY.ready()", timeout=60000)
            p.wait_for_timeout(800)
            r = p.evaluate(SNAP)
            check("c. reduced motion: no autoplay (the controls still work)", not r["playing"] and r["p"] == 0, r)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=1440, h=900)
            p.goto(f"{origin}/nq/replay.html?day={tday['day']}")
            p.wait_for_function("window.NQREPLAY && window.NQREPLAY.ready()", timeout=60000)
            pos = p.evaluate("() => ['theater', 'storyCard'].map((i) => { const r = document.getElementById(i).getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]; })")
            check("c. 1440: the theater beside the story", pos[0][0] < pos[1][0] and abs(pos[0][1] - pos[1][1]) <= 12 and AK.no_sideways(p) and not errs, (pos, errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_data()
    test_static()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
