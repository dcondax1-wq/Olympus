"""Before / after screenshots of the NQ chart card (night-nq-chart 2026-11-27): the fixture feed of tests/test_nq_chart.py (the real packer),
390 x 844 phone (scale 2) and 1440 x 900 desk.  python -X utf8 research/handoff/2026-11-27/night-nq-chart/shots.py <prefix> [--3d]"""
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tests import test_nq_chart as T  # noqa: E402
from tests import test_nq_page as NP  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")


def main():
    pre = sys.argv[1] if len(sys.argv) > 1 else "after"
    now = int(dt.datetime(2026, 11, 18, 13, 12, tzinfo=ZoneInfo("America/New_York")).timestamp())
    post, _ = T.fixture(now, age_s=(12 * 3600 if "--stopped" in sys.argv else 0))
    real = NP.time.time
    NP.time.time = lambda: float(now)
    try:
        home = NP.home_json(180)
    finally:
        NP.time.time = real
    srv, origin = AK.serve({"/status_feed.json": T.FEED, "/home.json": home})
    core = "{}"
    if "--stopped" in sys.argv:   # QA #2: bars 12 h old, the PC's status post has a newer price
        import json
        core = json.dumps({"event": "message", "time": now - 60, "message": json.dumps({"kind": "le-live", "lite": True, "t": now - 60, "price": 21995.25})}) + "\n"
    mock = {f"/{T.TOPIC}-bars/json": T.ndjson(post), f"/{T.TOPIC}/json": core}
    os.makedirs(OUT, exist_ok=True)
    try:
        with AK.browser() as br:
            for w, h, tag in ((390, 844, "390"), (1440, 900, "1440"))[:1 if "--stopped" in sys.argv else 2]:
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock=mock)
                p.clock.set_fixed_time(dt.datetime.fromtimestamp(now, dt.timezone.utc))
                T.open_chart(p, origin)
                p.evaluate("document.getElementById('chartCard').scrollIntoView({block:'start'})")
                p.wait_for_timeout(2500)
                p.locator("#chartCard").screenshot(path=os.path.join(OUT, f"{pre}-{tag}.png"))
                if "--3d" in sys.argv:
                    p.evaluate("window.NQCHART.show3d(true, false)")
                    p.wait_for_timeout(3500)
                    p.locator("#chartCard").screenshot(path=os.path.join(OUT, f"{pre}-{tag}-3d.png"))
                print(tag, "errors:", errs[:3])
                ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
