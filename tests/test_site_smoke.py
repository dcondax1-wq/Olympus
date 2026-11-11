"""tools/site_smoke.py: the release smoke over a built site. This suite checks its ANALYSIS with canned data (no browser, no network):
which pages it would open, what counts as a hard failure or a warning, the blank-page test on real pixels, the table, the contact sheets, and the local server.

    python -X utf8 -m tests.test_site_smoke
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import site_smoke as S  # noqa: E402

RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def png(color, box=None, box_color=(200, 162, 74), size=(390, 844)):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, color)
    if box:
        ImageDraw.Draw(im).rectangle(box, fill=box_color)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def good(**kw):
    r = {"app": "moirai", "status": 200, "console": [], "exceptions": [], "failed": [], "off_origin": [], "text_len": 900, "canvases": 1, "painted": 0.4, "title": "Moirai", "kit": True, "overflow_px": 0, "err_banner": "", "first_content_ms": 820, "timeout": False}
    r.update(kw)
    return r


def main():
    with tempfile.TemporaryDirectory() as d:
        for name in ("zeta", "alpha", "olympus"):
            os.makedirs(os.path.join(d, name))
        for p in ("index.html", "alpha/index.html", "zeta/index.html", "olympus/olympus.js", "data.json"):
            open(os.path.join(d, p), "w").write("<title>x</title>")
        apps = S.discover(d)
        check("discover: the root first, then every folder with an index.html by name; a folder without one (olympus/) is not a page", apps == ["", "alpha", "zeta"], apps)
        check("--apps: keeps the named ones in the site's order, 'root' is the root page, an unknown name is reported", S.pick(apps, "zeta, root,nope") == (["", "zeta"], ["nope"]) and S.pick(apps, None) == (apps, []) and S.pick(apps, "alpha/") == (["alpha"], []), S.pick(apps, "zeta, root,nope"))
        srv, origin = S.serve(d)
        try:
            body = urllib.request.urlopen(origin + "/alpha/", timeout=10).read().decode()
            try:
                urllib.request.urlopen(origin + "/nope/", timeout=10)
                missing = 200
            except urllib.error.HTTPError as e:
                missing = e.code
        finally:
            srv.shutdown()
        check("the local server serves the built folder read only on a free port (200 for a page, 404 for a missing one)", "<title>x</title>" in body and missing == 404 and origin.startswith("http://127.0.0.1:"), (body[:40], missing))
        empty = tempfile.mkdtemp(dir=d)
        check("a folder that is not a built site is refused with exit code 2 (no browser is started)", S.main([empty]) == 2 and S.discover(empty) == [])

    ok, pr, wa = S.classify(good())
    check("a healthy page: ok, no problem, no warning", ok and pr == [] and wa == [], (pr, wa))
    cases = [
        ("an HTTP 404 page is a hard failure", good(status=404), "status"),
        ("a page that never loaded is a hard failure", good(status=None), "status"),
        ("an uncaught exception is a hard failure", good(exceptions=["TypeError: x is not a function"]), "exception"),
        ("a console error is a hard failure", good(console=["Uncaught (in promise) boom"]), "console"),
        ("a failed script is a hard failure", good(failed=[{"url": "http://127.0.0.1:1/moirai/moiraicore.js?v=1", "status": 404}]), "request"),
        ("a failed stylesheet is a hard failure", good(failed=[{"url": "http://127.0.0.1:1/olympus/agora.css", "status": 500}]), "request"),
        ("a request that got no answer at all is a hard failure when it is code", good(failed=[{"url": "http://127.0.0.1:1/x/y.js", "status": None}]), "request"),
        ("a page with almost no text and no canvas is blank", good(text_len=3, canvases=0, painted=0.2), "blank"),
        ("a page where nothing is painted is blank, whatever its text", good(text_len=5000, painted=0.001), "blank"),
        ("a timeout is a hard failure", good(timeout=True, status=None), "timeout"),
        ("the kit's own 'could not load' banner is a hard failure", good(err_banner="colosseum could not load: people.js is missing"), "console"),
    ]
    for name, rec, kind in cases:
        ok, pr, wa = S.classify(rec)
        check(f"classify: {name}", ok is False and len(pr) >= 1 and pr[0].startswith(kind + ":") and kind in S.HARD, pr)
    ok, pr, wa = S.classify(good(timeout=True, status=None))
    check("a timeout is reported once (not also as 'did not load' or 'blank')", pr == ["timeout: no answer within 40 s"], pr)
    soft = [
        ("a missing optional data file (JSON 404) is a warning, not a failure", good(failed=[{"url": "http://127.0.0.1:1/home.json", "status": 404}]), "missing data: home.json (404)"),
        ("sideways overflow is a warning with the pixels", good(overflow_px=37), "sideways overflow: 37 px wider than the phone"),
        ("no title is a warning", good(title=""), "no page title"),
        ("no app marker is a warning", good(kit=False), "no app marker (the OLYMPUS kit tag with data-app)"),
        ("a request that tried to leave the site is a warning", good(off_origin=["https://fonts.example/x.woff2"]), "tried to leave the site: https://fonts.example/x.woff2"),
    ]
    for name, rec, text in soft:
        ok, pr, wa = S.classify(rec)
        check(f"classify: {name}", ok is True and pr == [] and wa == [text], (pr, wa))
    ok, pr, wa = S.classify(good(text_len=0, canvases=3, painted=0.3))
    check("a 3D page with no text but a painted canvas is not blank", ok and not pr, pr)
    ok, pr, wa = S.classify(good(painted=None, text_len=500))
    check("without Pillow (painted unknown) the text test still decides", ok and S.classify(good(painted=None, text_len=2, canvases=0))[0] is False)
    noise = ["Failed to load resource: the server responded with a status of 404 (File not found)", "GPU stall due to ReadPixels", "WebGL: software fallback", "", None, "real error here"]
    check("console noise (resource-load echoes, software GL chatter, empty lines) is not an error; a real line is", S.console_errors(noise) == ["real error here"], S.console_errors(noise))
    check("code files: .js .css .html and folders are code; .json .png .csv are data", [S.is_code(u) for u in ("/a/b.js?v=1", "/a.css", "/x/", "/a.JSON", "/i.png#x", "/d.csv", "/m.mjs")] == [True, True, True, False, False, False, True])

    try:
        import PIL  # noqa: F401
        flat, drawn, tiny = S.painted_share(png((20, 17, 14))), S.painted_share(png((20, 17, 14), (40, 100, 350, 500))), S.painted_share(png((20, 17, 14), (0, 0, 6, 6)))
        check("painted pixels: a flat screenshot is 0%, a card on it is about 40%, a speck is under 1% (= blank), junk bytes give None", flat == 0 and 0.3 < drawn < 0.5 and tiny < S.MIN_PAINTED and S.painted_share(b"not a png") is None, (flat, drawn, tiny))
        with tempfile.TemporaryDirectory() as d:
            shots = []
            for i in range(14):
                p = os.path.join(d, f"a{i}.png")
                open(p, "wb").write(png((20 + i * 5, 17, 14), (40, 100, 350, 500)))
                shots.append((f"app{i}", p, i != 3))
            shots.append(("ghost", os.path.join(d, "missing.png"), False))
            sheets = S.contact_sheets(shots, d)
            from PIL import Image
            sizes = [Image.open(s).size for s in sheets]
            check("contact sheets: 15 screenshots give two JPG grids (12 + 3, four columns), a missing screenshot does not stop it", [os.path.basename(s) for s in sheets] == ["sheet-01.jpg", "sheet-02.jpg"] and sizes[0][0] == 4 * 203 + 8 and sizes[0][1] > sizes[1][1], (sheets, sizes))
    except ImportError:
        check("painted pixels / contact sheets skipped: no Pillow", True)
    check("the sheet plan: 0 -> none, 5 -> one row of 4 + 1, 12 -> one full sheet, 25 -> three sheets", S.sheets_plan(0) == [] and S.sheets_plan(5) == [(0, 5, 4, 2)] and S.sheets_plan(12) == [(0, 12, 4, 3)] and [x[1] for x in S.sheets_plan(25)] == [12, 12, 1], S.sheets_plan(25))

    res = S.judge([good(app=""), good(app="alpha", overflow_px=12), good(app="beta", exceptions=["ReferenceError: q is not defined"], console=["x", "y"], first_content_ms=None), {"app": "nope", "status": 404, "url": "/nope/"}])
    lines = S.table_lines(res)
    check("the SIMPLE table: a header, a rule, one row per page (app / ok / first content / problem); the root is '(root)'; a failing row says FAIL and counts the other problems",
          len(lines) == 6 and lines[0].split()[:2] == ["app", "ok"] and lines[2].startswith("(root)") and " ok " in lines[2] + " " and "0.8 s" in lines[2] and "warning: sideways overflow: 12 px" in lines[3]
          and "FAIL" in lines[4] and "exception: ReferenceError: q is not defined (+2 more)" in lines[4] and "FAIL" in lines[5] and "HTTP 404" in lines[5], lines)
    sm = S.summary(res)
    check("the summary: 4 pages, 2 ok, 2 failed (named), 1 ok with warnings; it serialises to JSON", sm == {"pages": 4, "ok": 2, "failed": 2, "with_warnings": 1, "failed_apps": ["beta", "nope"]} and json.loads(json.dumps(res))[2]["ok"] is False, sm)
    check("the defaults: 390 x 844, ?demo=1&q=low&welcome=0&intro=0, 40 s a page", (S.W, S.H) == (390, 844) and S.QUERY == "?demo=1&q=low&welcome=0&intro=0" and S.main.__doc__ is None and "default=40" in open(S.__file__, encoding="utf-8").read())
    src = open(S.__file__, encoding="utf-8").read()
    check("read only and polite: it never writes into the site, never pushes, blocks service workers and every off-site request", "service_workers=\"block\"" in src and "r.abort()" in src and "git " not in src and "subprocess" not in src)

    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed", flush=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
