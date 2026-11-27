"""The NQ chart, pro pass (night-nq-chart 2026-11-27): nqbars.js sessions / levels / sweeps / open-trade zones (pure, node) and nqchart.js's
overlay (session bands, risk / reward boxes, dashed session highs / lows, sweep diamonds), the OHLC readout (newest bar, then the bar under the
crosshair), the honest age badge (LIVE / old), the "Now" button, its own chart.css, the OLYMPUS NIGHT palette (no cyan, no olive / brown).

  a. static   chart.css loaded by nqchart.js itself, the palette, no innerHTML, nqbars.js still pure, controls >= 44 px
  b. node     levels on the fixture post (the real packer, tests.test_nq_chart.fixture): Asia (part) + London highs / lows, the sweeps, the
              PC's own levels (post.lv) only when sent and sane, zones for the open SHORT, sessions in order; no bars = no levels
  c. Chromium 390 x 844 + 1440: the overlay paints, the readout reads the newest bar's O H L C, a crosshair move changes it, LIVE badge,
              an old feed says "Bars ... old", Now shows after a pan and brings the view back; no sideways scroll, taps >= 44, no console error
    python -X utf8 -m tests.test_nq_chart_pro
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from tests import test_nq_chart as T  # noqa: E402

check = AK.check
D = os.path.join(AK.WEB, "nq")
NOW = int(dt.datetime(2026, 11, 18, 13, 12, tzinfo=ZoneInfo("America/New_York")).timestamp())


def test_static():
    js, core, css = (AK.read(os.path.join(D, n)) for n in ("nqchart.js", "nqbars.js", "chart.css"))
    check("a. chart.css exists and nqchart.js loads it itself (a link tag at boot: no page edit needed)", "chart.css?v=" in js and "#chartCard" in css)
    tok = re.sub(r"//[^\n]*", "", js[js.index("function tokensRead()"):js.index("const col = (T, k)")])
    cyan = re.findall(r"#(?:67e8f9|22d3ee|06b6d4|0ff|00ffff)\b", tok + css, re.I)
    check("a. the chart's palette is OLYMPUS NIGHT: mint up #77db89, gold #f1c14b, violet #9d59ee; no cyan, no olive / brown key, no AGORA fallback",
          "'#77db89'" in tok and "'#f1c14b'" in tok and "'#9d59ee'" in tok and not cyan and "olive" not in tok and "--ag-" not in tok, cyan)
    check("a. nqbars.js has no olive account colour any more", "'olive'" not in core.split("const OTHER_COLORS")[1][:80])
    check("a. still text only (no innerHTML / eval), nqbars.js still pure", not re.search(r"\.innerHTML|insertAdjacentHTML|\beval\s*\(", js + core)
          and not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(", re.sub(r"//[^\n]*", "", core)))
    check("a. the Now button is >= 44 px, the readout never takes a tap (pointer-events none), reduced motion stops the LIVE pulse",
          re.search(r"\.cnow \{[^}]*min-height: 44px", css) and re.search(r"\.cleg \{[^}]*pointer-events: none", css) and "prefers-reduced-motion" in css)


NODE = r"""
import(process.argv[2]).then((B) => {
  const fs = require('fs'), post = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), now = +process.argv[4];
  const m = B.model(post, 'all', now), o = {};
  o.sessions = m.sessions.map((s) => s.k); o.levels = m.levels.map((l) => [l.label, l.side, l.src]); o.sweeps = m.sweeps.map((w) => [w.label, w.side]);
  o.zones = m.zones.map((z) => [z.k, z.s, z.e, z.sl, z.tp]);
  const bars = B.unpack(post);
  o.check = m.levels.filter((l) => l.src === 'bars').every((l) => { const ss = B.sessions(bars), s = ss.find((x) => l.k.startsWith(x.k));
    const seg = bars.slice(s.i0, s.i1 + 1); return l.side > 0 ? l.price === Math.max(...seg.map((b) => b[2])) : l.price === Math.min(...seg.map((b) => b[3])); });
  o.sweepOk = m.sweeps.every((w) => { const b = bars[w.i], L = m.levels.find((l) => l.k === w.k); return w.side > 0 ? b[2] > L.price && b[4] < L.price : b[3] < L.price && b[4] > L.price; });
  const lv = JSON.parse(JSON.stringify(post)); lv.lv = { pdh: bars[0][2] + 40, pdl: bars[0][3] - 40, onh: 'junk', onl: 1e9 };
  o.pc = B.model(lv, 'all', now).levels.filter((l) => l.src === 'pc').map((l) => l.label);
  o.none = B.model(null, 'all', now).levels.length;
  o.sess = [B.sessionOf(Date.UTC(2026, 10, 18, 4, 0) / 1000), B.sessionOf(Date.UTC(2026, 10, 18, 9, 0) / 1000), B.sessionOf(Date.UTC(2026, 10, 18, 16, 0) / 1000), B.sessionOf(Date.UTC(2026, 10, 18, 22, 30) / 1000)];
  console.log(JSON.stringify(o));
});
"""


def test_node():
    post, info = T.fixture(NOW)
    with tempfile.TemporaryDirectory() as td:
        pp, hp = os.path.join(td, "post.json"), os.path.join(td, "h.cjs")
        json.dump(post, open(pp, "w"))
        open(hp, "w").write(NODE)
        r = subprocess.run(["node", hp, "file://" + os.path.join(D, "nqbars.js"), pp, str(NOW)], capture_output=True, text=True, timeout=60)
    o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
    check("b. sessions in order from the bars (Asia, London, New York)", o.get("sessions") == ["asia", "london", "ny"], (o.get("sessions"), r.stderr[-300:]))
    check("b. the finished sessions' highs / lows: Asia (part: the feed starts mid-session) and London; none for the session still running",
          o.get("levels") == [["Asia high (part)", 1, "bars"], ["Asia low (part)", -1, "bars"], ["London high", 1, "bars"], ["London low", -1, "bars"]] and o.get("check"), o.get("levels"))
    check("b. sweeps = a later bar through the level that closes back inside it (checked on the bars)", o.get("sweeps") and o.get("sweepOk"), o.get("sweeps"))
    op = info["opens"][0]
    check("b. the open SHORT's risk / reward zone (entry, stop, target) for each account holding it",
          o.get("zones") == [["z50k", -1, op["e"], op["sl"], op["tp"]], ["z25k2", -1, op["e"], op["sl"], op["tp"]]], o.get("zones"))
    check("b. the PC's own levels (post.lv) only when sent and sane: PD high / low shown, junk and absurd values dropped; no bars = no levels",
          o.get("pc") == ["PD high", "PD low"] and o.get("none") == 0, (o.get("pc"), o.get("none")))
    check("b. sessionOf in ET: 23:00 Asia, 04:00 London, 11:00 New York, 17:30 closed", o.get("sess") == ["asia", "london", "ny", None], o.get("sess"))


SNAP = """() => { const S = window.NQCHART.S, fx = document.getElementById('chartFx'), leg = document.getElementById('chartLeg'), ag = document.getElementById('chartAge'),
  now = document.getElementById('chartNow'); let ink = 0;
  if (fx && fx.width) { const d = fx.getContext('2d').getImageData(0, 0, fx.width, fx.height).data; for (let i = 3; i < d.length; i += 64) if (d[i] > 0) ink++; }
  const L = S.model.candles[S.model.candles.length - 1];
  return { fx: !!fx && !fx.hidden, ink, leg: leg ? leg.textContent : '', age: ag && !ag.hidden ? ag.textContent : '', ageCls: ag ? ag.className : '', now: now ? !now.hidden : null,
    css: !!document.getElementById('chartCss') && [...document.styleSheets].some((s) => (s.href || '').includes('chart.css')), last: [L.open, L.high, L.low, L.close] }; }"""


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    from tests import test_nq_page as NP
    post, _ = T.fixture(NOW)
    old, _ = T.fixture(NOW, age_s=3 * 3600)
    real = NP.time.time
    NP.time.time = lambda: float(NOW)
    try:
        home = NP.home_json(180)
    finally:
        NP.time.time = real
    srv, origin = AK.serve({"/status_feed.json": T.FEED, "/home.json": home})
    bars_url, core_url = f"/{T.TOPIC}-bars/json", f"/{T.TOPIC}/json"
    px = lambda v: f"{v:,.2f}"  # noqa: E731
    try:
        with AK.browser() as br:
            for w, h in ((390, 844), (1440, 900)):
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock={bars_url: T.ndjson(post), core_url: "{}"})
                p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW, dt.timezone.utc))
                T.open_chart(p, origin)
                p.evaluate("document.getElementById('chartCard').scrollIntoView({block:'start'})")
                p.wait_for_timeout(600)
                s = p.evaluate(SNAP)
                check(f"c. {w}px: chart.css loaded, the overlay canvas paints (sessions, zones, levels, sweeps: {s['ink']} inked samples)", s["css"] and s["fx"] and s["ink"] > 200, s)
                check(f"c. {w}px: the readout shows the newest bar (its close, high, low) and its session; the badge says LIVE", all(px(v) in s["leg"] for v in s["last"][1:])
                      and "NEW YORK" in s["leg"].upper() and s["age"].startswith("LIVE") and "live" in s["ageCls"], (s["leg"], s["age"]))
                box = p.locator("#chart").bounding_box()
                p.mouse.move(box["x"] + box["width"] * 0.25, box["y"] + box["height"] * 0.5)
                p.wait_for_timeout(300)
                s2 = p.evaluate(SNAP)
                check(f"c. {w}px: a crosshair over an older bar changes the readout to that bar", s2["leg"] and s2["leg"] != s["leg"], (s["leg"], s2["leg"]))
                check(f"c. {w}px: 'Now' hidden while the newest bar is in view", s["now"] is False, s["now"])
                p.evaluate("window.NQCHART.S.chart.timeScale().scrollToPosition(-60, false)")
                p.wait_for_timeout(300)
                s3 = p.evaluate(SNAP)
                b = p.locator("#chartNow").bounding_box() if s3["now"] else None
                check(f"c. {w}px: after a pan back in time 'Now' shows (>= 44 px tall)", s3["now"] and b and b["height"] >= 44, (s3["now"], b))
                if s3["now"]:
                    p.locator("#chartNow").click()
                    p.wait_for_timeout(300)
                    s4 = p.evaluate(SNAP)
                    check(f"c. {w}px: tapping 'Now' brings the newest bar back and hides it", s4["now"] is False, s4["now"])
                check(f"c. {w}px: no sideways scroll, taps >= 44 px, no console error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:3]))
                ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, mock={bars_url: T.ndjson(old), core_url: "{}"})
            p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW, dt.timezone.utc))
            T.open_chart(p, origin)
            s = p.evaluate(SNAP)
            check("c. bars 3 hours old: the badge says so in plain words (never 'LIVE')", s["age"].startswith("Bars 3 hours") and "old" in s["ageCls"], s["age"])
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_node()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
