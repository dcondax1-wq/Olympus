"""day-ofroom2 2026-11-27: the footprint heat strip (tools/web_public/nq/ofstrip.js + ofstrip.css, data nq/of_strip.json from
tools/build_of_room.strip_from_summary). Simulated ticks only (research/orderflow/of_sim.py, a planted absorption day).
  a. static: read only (no innerHTML / storage / network in the module), OLYMPUS NIGHT, >= 12 px text, reduced motion
  b. data: strip_from_summary = the summary's RTH bars; volume and delta add up to the bars file; OF1 absorption marks
  c. node: describe() words ('buyers absorbed at 26,685.00 · 1,240 contracts'), scale()
  d. browser 390x844 + 1440x900 on orderflow.html: one column per bar, cells, gold absorption marks, big-print dots, delta row;
     tap a bar -> its words; the slider steps; empty file -> honest line; taps >= 44, no sideways scroll, no console error
Run: python -X utf8 -m tests.test_ofstrip [--shots]
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

check = AK.check
NQ = os.path.join(ROOT, "tools", "web_public", "nq")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-27", "day-ofroom2", "shots")
ET = ZoneInfo("America/New_York")


def load(path, name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


def main():
    js = AK.read(os.path.join(NQ, "ofstrip.js")); css = AK.read(os.path.join(NQ, "ofstrip.css"))
    check("a. module: mount(el, data, opts) exported + window.OFSTRIP; read only (no innerHTML / storage / fetch)",
          "export function mount(" in js and "window.OFSTRIP" in js and not re.search(r"innerHTML|localStorage|sessionStorage|fetch\(|XMLHttpRequest", js))
    sizes = [float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", css)]
    check("a. css: scoped .ofs, OLYMPUS NIGHT colours, every text >= 12 px, reduced motion", css.count(".ofs") > 10 and "#9d59ee" in css and "#f1c14b" in css
          and "#77db89" in css and sizes and min(sizes) >= 12 and "prefers-reduced-motion" in css and not re.search(r"cyan|#0ff\b|olive|brown", css, re.I), sizes)
    RB = load("tools/build_of_room.py", "ofs_rb")
    Sim = load("research/orderflow/of_sim.py", "ofs_sim")
    W = Sim.world(3, "planted", seed=5, lvl=True)
    d = W["days"][-1]
    R = W["R"][d]
    st = RB.strip_from_summary(R, d)
    b = R["bars"]
    import pandas as pd
    et = pd.to_datetime(b.t, unit="s", utc=True).dt.tz_convert(ET)
    mod = et.dt.hour * 60 + et.dt.minute
    rth = b[(mod >= 570) & (mod < 960)]
    check("b. one strip bar per RTH 5m bar (78), volume + delta = the bars file", len(st["bars"]) == len(rth) == 78
          and sum(x["v"] for x in st["bars"]) == int(rth.vol.sum()) and sum(x["d"] for x in st["bars"]) == int((rth.buy - rth.sell).sum()))
    cv = sum(c[1] + c[2] for x in st["bars"] for c in x["cells"])
    check("b. the 2-point cells hold every buy + sell lot of the RTH footprint", cv == int((rth.buy + rth.sell).sum()), (cv, int((rth.buy + rth.sell).sum())))
    ab = [a for x in st["bars"] for a in x["abs"]]
    check("b. OF1 absorption marks: low = buyers absorbed (delta into it < 0), high = sellers absorbed (> 0), share >= 20%",
          ab and all((a["side"] == "low" and a["who"] == "buyers" and a["dz"] < 0) or (a["side"] == "high" and a["who"] == "sellers" and a["dz"] > 0) for a in ab)
          and all(abs(a["dz"]) >= 0.2 * a["vz"] for a in ab), ab[:2])
    size = len(json.dumps(st, separators=(",", ":")))
    check("b. a whole RTH day < 40 KB", size < 40_000, size)
    # c. node
    with tempfile.TemporaryDirectory() as td:
        drv = os.path.join(td, "d.mjs")
        open(drv, "w").write("import * as S from '%s';\nconst b = %s;\nconsole.log(JSON.stringify({ a: S.describe(b[0]), n: S.describe(b[1]), s: S.scale({ bars: b, bucket: 2 }) }));\n" % (
            "file://" + os.path.join(NQ, "ofstrip.js"),
            json.dumps([{"t": "10:05", "v": 4000, "d": -900, "big": -60, "abs": [{"side": "low", "who": "buyers", "px": 26685.0, "vz": 1240, "dz": -400}], "cells": [[26684, 10, 20]], "l": 26684, "h": 26690},
                        {"t": "10:10", "v": 3000, "d": 1500, "big": 0, "abs": [], "cells": [[26690, 50, 10]], "l": 26686, "h": 26696}])))
        r = subprocess.run(["node", drv], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        o = {}
        check("c. node ran", False, r.stderr[-300:])
    if o:
        check("c. describe(): '10:05 · buyers absorbed at 26,685.00 · 1,240 contracts · delta −900 of 4,000 · big prints −60'",
              o["a"] == "10:05 · buyers absorbed at 26,685.00 · 1,240 contracts · delta −900 of 4,000 · big prints −60", o["a"])
        check("c. describe() without absorption: 'buyers in control' + delta", o["n"] == "10:10 · buyers in control · delta +1,500 of 3,000", o["n"])
        check("c. scale(): price range, busiest cell, biggest delta / print", o["s"]["lo"] == 26684 and o["s"]["hi"] == 26696 and o["s"]["dmax"] == 1500 and o["s"]["bmax"] == 60, o["s"])
    # d. browser
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return AK.finish()
    shots = "--shots" in sys.argv
    read = """() => ({ cols: document.querySelectorAll('#strip .ofs-col').length, cells: document.querySelectorAll('#strip .ofs-c').length,
        abs: document.querySelectorAll('#strip .ofs-abs').length, big: document.querySelectorAll('#strip .ofs-big').length, d: document.querySelectorAll('#strip .ofs-d').length,
        info: document.querySelector('#strip .ofs-info') && document.querySelector('#strip .ofs-info').textContent, chip: document.getElementById('stripChip').textContent,
        sel: document.getElementById('strip').dataset.sel, scrolled: (document.querySelector('#strip .ofs-scroll') || {}).scrollLeft || 0 })"""
    for name, w, h, data in (("strip-390", 390, 844, st), ("strip-1440", 1440, 900, st), ("strip-empty-390", 390, 844, None)):
        srv, origin = AK.serve({"/nq/of_strip.json": json.dumps(data) if data else None, "/nq/of_room.json": None, "/home.json": None})
        try:
            with AK.browser() as br:
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock={"json?poll=1": ""})
                p.goto(f"{origin}/nq/orderflow.html")
                p.wait_for_function("window.NQ_OF && window.NQ_OF.ready()", timeout=60000)
                p.wait_for_timeout(1500)
                p.evaluate("document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")
                o = p.evaluate(read)
                if data:
                    check(f"d. {name}: 78 columns with cells, gold absorption marks, big-print dots, 78 delta bars; the newest bar picked, scrolled to the end",
                          o["cols"] == 78 and o["cells"] > 300 and o["abs"] == len(ab) and o["big"] > 0 and o["d"] == 78 and o["sel"] == "77"
                          and (w > 1000 or o["scrolled"] > 0) and o["chip"].endswith("78 bars"), o)
                    box = p.evaluate("() => { const s = document.querySelector('#strip .ofs-svg').getBoundingClientRect(); return [s.left, s.top, s.width, s.height]; }")
                    k = next(i for i, x in enumerate(st["bars"]) if x["abs"])
                    p.evaluate(f"() => {{ const sc = document.querySelector('#strip .ofs-scroll'); sc.scrollLeft = Math.max(0, {4 + k * 12} - 40); }}")
                    p.wait_for_timeout(200)
                    box = p.evaluate("() => { const s = document.querySelector('#strip .ofs-svg').getBoundingClientRect(); return [s.left, s.top, s.width, s.height]; }")
                    p.mouse.click(box[0] + 4 + k * 12 + 6, box[1] + 60)
                    p.wait_for_timeout(250)
                    o2 = p.evaluate(read)
                    want = f"{st['bars'][k]['t']} · " + st["bars"][k]["abs"][0]["who"]
                    check(f"d. {name}: tap the bar at {st['bars'][k]['t']} -> '{want} absorbed at ... contracts'", o2["sel"] == str(k) and o2["info"].startswith(want)
                          and "absorbed at" in o2["info"] and "contracts" in o2["info"], o2["info"])
                    p.evaluate("() => { const s = document.querySelector('#strip .ofs-slider'); s.value = '3'; s.dispatchEvent(new Event('input')); }")
                    o3 = p.evaluate(read)
                    check(f"d. {name}: the slider picks bar 4 (keyboard / big-thumb access)", o3["sel"] == "3" and o3["info"].startswith(st["bars"][3]["t"]), o3["info"])
                else:
                    check("d. strip-empty-390: no file -> an honest line, no columns", o["cols"] == 0 and o["chip"] == "no day yet", o)
                check(f"d. {name}: taps >= 44 px, no sideways scroll, nothing off the site, no console error",
                      not AK.taps(p) and AK.no_sideways(p) and not off and not errs, (AK.taps(p)[:4], off[:3], errs[:3]))
                if shots:
                    os.makedirs(SHOTS, exist_ok=True)
                    p.locator("#stripCard").screenshot(path=os.path.join(SHOTS, f"{name}.png"))
                ctx.close()
        finally:
            srv.shutdown()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
