"""Before / after shots of the NQ Brain (night-nq-brain 2026-11-27) on the PC's real post (tests/fixtures/truth/pc_post.json), the
same mocks as tests/test_nq_brain.py. 390 x 844 (top + full page) and 1440 x 900.
    python -X utf8 research/handoff/2026-11-27/night-nq-brain/shots.py before|after
"""
import datetime as dt, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK, test_nq_brain as T, test_nq_chart as NC, test_nq_page as NP  # noqa: E402

tag = sys.argv[1] if len(sys.argv) > 1 else "after"
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
real = NP.time.time
NP.time.time = lambda: float(T.NOW)
try:
    home = NP.home_json(3 * 3600)
finally:
    NP.time.time = real
core = json.dumps({"event": "message", "time": T.PC["reporter"]["t"], "message": json.dumps(T.PC)}) + "\n"
srv, origin = AK.serve({"/status_feed.json": NC.FEED, "/home.json": home})
with AK.browser() as br:
    for w, h, q in ((390, 844, ""), (1440, 900, ""), (390, 844, "?bot=atlas")):
        ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock={f"/{NC.TOPIC}/json": core})
        p.clock.set_fixed_time(dt.datetime.fromtimestamp(T.NOW, dt.timezone.utc))
        p.goto(f"{origin}/nq/brain.html{q}")
        p.wait_for_function("window.NQBRAIN && window.NQBRAIN.ready()", timeout=60000)
        p.wait_for_function("document.querySelector('#bStatus').textContent.startsWith('From your PC')", timeout=30000)
        p.wait_for_timeout(2500)
        nm = f"{tag}_{w}{'_atlas' if q else ''}"
        p.screenshot(path=os.path.join(out, nm + "_top.png"))
        if w == 390 and not q:
            p.screenshot(path=os.path.join(out, nm + "_full.png"), full_page=True)
            if tag == "after":
                p.wait_for_function("window.NQMIND && window.NQMIND.ready()", timeout=30000)
                p.add_style_tag(content=".top, header.ag-appbar, .ag-appbar { position: static !important; }")
                for sid in ("mindNow", "mindPipe", "mindAtlas", "mindTrial", "mindLessons", "mindGap", "mindHealth"):
                    p.locator("#" + sid).scroll_into_view_if_needed()
                    p.wait_for_timeout(600)
                    p.locator("#" + sid).screenshot(path=os.path.join(out, f"{nm}_{sid}.png"))
        if w == 1440 and tag == "after":
            p.wait_for_function("window.NQMIND && window.NQMIND.ready()", timeout=30000)
            p.screenshot(path=os.path.join(out, nm + "_full.png"), full_page=True)
        print(nm, "errors:", errs[:3], "off:", off[:2])
        ctx.close()
srv.shutdown()
