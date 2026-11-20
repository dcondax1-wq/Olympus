"""tools/a11y_sweep.py + tools/a11y/rules.js (day-a11y 2026-11-20): the sweep finds each rule on a bad page and nothing on a good one.

    python -X utf8 -m tests.test_a11y_sweep            (--static: no browser)
"""
from __future__ import annotations

import functools
import http.server
import os
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import a11y_sweep as S  # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{str(info)[:300]}]"))
    if not ok:
        FAILS.append(name)


HEAD = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>t</title>'
BAD = HEAD + """<style>
 body { margin: 0; background: #111; color: #eee; font-size: 16px; }
 .tiny { width: 30px; height: 30px; }
 .small { font-size: 12px; }
 .wide { width: 700px; height: 20px; background: #333; }
 .bar { position: fixed; left: 0; right: 0; bottom: 0; height: 50px; background: #222; }
 .spin { width: 50px; height: 50px; animation: spin 2s linear infinite; }
 @keyframes spin { to { transform: rotate(360deg); } }
 .loss { color: #e03030; font-size: 1rem; }
 .faint { color: #444; font-size: 1rem; }
 button:focus { outline: none; }
</style></head><body>
<h1>Bad</h1>
<button class="tiny" id="iconbtn"></button>
<p class="small">This sentence is set at twelve pixels and does not grow.</p>
<div class="wide"></div>
<div class="spin"></div>
<p><span class="loss">$120</span></p>
<p class="faint">Low contrast words on a dark page here.</p>
<h4>Skipped two levels</h4>
<div class="bar"><button style="width:120px;height:48px">Go</button></div>
</body></html>"""
GOOD = HEAD + """<style>
 html { font-size: 100%; }
 body { margin: 0; background: #111; color: #eee; font-size: 1rem; padding-bottom: 80px; }
 button { min-width: 2.75rem; min-height: 2.75rem; font-size: 1rem; background: #333; color: #fff; border: 0; }
 button:focus-visible { outline: 3px solid #c8a24a; }
 .bar { position: fixed; left: 0; right: 0; bottom: 0; padding-bottom: env(safe-area-inset-bottom); background: #222; }
 .up { color: #4caf50; }
 @media (prefers-reduced-motion: no-preference) { .spin { animation: spin 2s linear infinite; } }
 @keyframes spin { to { transform: rotate(360deg); } }
</style></head><body>
<h1>Good</h1>
<h2>Section</h2>
<button aria-label="Close">x</button>
<p>Body text at the root size, which grows with Dynamic Type.</p>
<div class="spin" style="width:50px;height:50px"></div>
<p><span class="up">+$120</span> up today</p>
<div class="bar"><button>Go</button></div>
</body></html>"""


def static():
    check("ratio: black on white is 21:1", abs(S.ratio("#000000", "#ffffff") - 21) < 0.01)
    c = S.fix_color("#666666", "#111111", 4.5)
    check("fix_color: the suggested colour reaches 4.5:1 on the dark fill", bool(c) and S.ratio(c, "#111111") >= 4.5, c)
    c2 = S.fix_color("#aaaaaa", "#ffffff", 4.5)
    check("fix_color: on a light fill it goes darker and reaches 4.5:1", bool(c2) and S.ratio(c2, "#ffffff") >= 4.5 and S._lum(S._rgb(c2)) < S._lum(S._rgb("#aaaaaa")), c2)
    check("screens: full = 12 (3 sizes x dark/light x motion), quick = 6", len(S.screens(False)) == 12 and len(S.screens(True)) == 6)
    check("screens: the axe + Dynamic Type pass runs at 390 px, dark and light, reduced motion", sorted(s[0] for s in S.screens(False) if s[5] == "full") == ["390-dark-rm", "390-light-rm"])
    apps = dict(S.visible_apps())
    check("visible apps: the door apps minus the Archive, plus Jarvis, the Gate and the hubs",
          "compass" in apps and "apollo" not in apps and apps.get("zenith") == "index.html" and {"jarvis", "gate", "hub", "hub-zeus"} <= set(apps), sorted(apps))
    check("every visible app has an owning team", all(a in S.OWNER for a in apps), [a for a in apps if a not in S.OWNER])
    per = [{"screen": "390-dark-rm", "issues": [{"rule": "tap-target", "sel": "a", "detail": "30x30"}, {"rule": "tap-target", "sel": "a", "detail": "30x30"},
                                               {"rule": "color-contrast", "sel": "p", "detail": "#444444 on #111111 = 1.9:1, need 4.5 (16px)"}, {"rule": "region", "sel": "x"}]}]
    s = S.summarise("compass", "compass/", per)
    check("summarise: one issue per element + rule, ignored axe rules dropped, contrast + tap down to 0.5 (compass loads a11y.js: Dynamic Type not scored, 13 rules)", len(s["issues"]) == 2 and s["score"] == round(100 * 12 / 13) and s["a11y_js"], (len(s["issues"]), s["score"]))
    check("score_of: 14 rules without a11y.js, 13 with", S.score_of({c: 0 for c in S.CATS} | {"dyntype": 5}, False) == round(100 * 13 / 14) and S.score_of({c: 0 for c in S.CATS} | {"dyntype": 5}, True) == 100)
    fx = [i["fix"] for i in s["issues"] if i["rule"] == "color-contrast"][0]
    check("summarise: the contrast fix names an exact colour", "#" in fx and ":1" in fx, fx)


def serve(files):
    d = tempfile.mkdtemp(prefix="a11y-")
    for name, body in files.items():
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(body)
    h = type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(h, directory=d))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP browser part: no Python playwright")
        return
    srv, origin = serve({"bad.html": BAD, "good.html": GOOD})
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import browser_kit as BK
    with sync_playwright() as pw:
        br = BK.launch(pw)
        for name, page_name in (("bad", "bad.html"), ("good", "good.html")):
            ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce", device_scale_factor=1)
            ctx.add_init_script(S.INIT_JS % "agora")
            page = ctx.new_page()
            res = S.check_page(page, origin, page_name, ("390-dark-rm", 390, 844, "dark", "reduce", "full"))
            ctx.close()
            rules = {i["rule"] for i in res["issues"]}
            if name == "bad":
                for r in ("tap-target", "small-text", "fixed-text", "h-scroll", "bottom-bar", "motion", "color-only", "color-contrast", "button-name", "heading-order", "no-focus"):
                    check(f"bad page: {r} found", r in rules, sorted(rules))
                src = [i.get("src", "") for i in res["issues"] if i["rule"] == "small-text"]
                check("bad page: the small text names its CSS rule (.small { font-size: 12px })", any(".small" in s and "12px" in s for s in src), src)
            else:
                own = rules & {"tap-target", "small-text", "fixed-text", "h-scroll", "bottom-bar", "motion", "color-only", "color-contrast", "button-name", "heading-order", "no-focus"}
                check("good page: none of the rules fire", not own, [(i["rule"], i["sel"], i.get("detail")) for i in res["issues"]])
    srv.shutdown()


if __name__ == "__main__":
    static()
    if "--static" not in sys.argv:
        browser()
    print(f"\n{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    sys.exit(1 if FAILS else 0)
