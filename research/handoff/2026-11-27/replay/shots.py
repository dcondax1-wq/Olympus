"""Shots of the NQ Replay Theater (night 2026-11-27): 390 x 844 (top, mid-play, full) and 1440 x 900.
    python -X utf8 research/handoff/2026-11-27/replay/shots.py
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
out = os.path.join(ROOT, "research", "handoff", "2026-11-27", "replay", "shots")
os.makedirs(out, exist_ok=True)
srv, origin = AK.serve()
with AK.browser() as br:
    for w, h in ((390, 844), (1440, 900)):
        ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h)
        p.goto(f"{origin}/nq/replay.html?day=2026-11-10")
        p.wait_for_function("window.NQREPLAY && window.NQREPLAY.ready()", timeout=60000)
        p.evaluate("window.NQREPLAY.pause(); window.NQREPLAY.seek(0)")
        p.wait_for_timeout(300)
        p.screenshot(path=os.path.join(out, f"replay_{w}_start.png"))
        p.evaluate("window.NQREPLAY.seek(window.NQREPLAY.S.events.find((e) => e.kind === 'entry').i + 3)")
        p.wait_for_timeout(500)
        p.screenshot(path=os.path.join(out, f"replay_{w}_in_trade.png"))
        if w == 390:
            p.locator("#theater").screenshot(path=os.path.join(out, "replay_390_theater.png"))
            p.screenshot(path=os.path.join(out, "replay_390_full.png"), full_page=True)
        print(w, "errors:", errs[:3], "off:", off[:2])
        ctx.close()
srv.shutdown()
