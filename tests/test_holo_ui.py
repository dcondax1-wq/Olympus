"""Holodeck UI (owner 2026-10-29: "a main feature that allows me to see exactly chart fills, very high quality and 3D, where I can
see what every bot is thinking"): the 3D scene (tools/web_public/fx/src/holo.js in fx.js), the shared page UI (holocore.js,
holo.css, byte-identical on both dashboards), the phone page (tools/web_public/holo.js, #/holo) and the PC page
(web_next/js/next/holo.js, Main after Live View), driven by Playwright with tests/fixtures/holo_fe_sample.json (real 2026
NQ bars + the LIT / ATLAS / BLITZ research trades, mocked real fills 1 tick off the model; tests/make_holo_fe_fixture.py).

  python -X utf8 -m tests.test_holo_ui                     # ~60-90 s (Playwright part skipped without node + playwright)
  LE_SHOTS=<dir> python -X utf8 -m tests.test_holo_ui      # also saves the screenshots there

Phone 390x844 + sideways 844x390 and PC 1440x900: the scene mounts, every fill drawn (= the fixture's fills), a fill's label
and card show the exact price + second (+ REAL, the slip vs the model), trade volumes + the LIT setup anatomy, thought panels,
the Minds panel, replay advances the bars and pops the fills in time order, the day picker, full screen covers the screen,
no page errors, WebGL off = the 2D fallback with the fills, frame time sane.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def main() -> int:
    fix = os.path.join(ROOT, "tests", "fixtures", "holo_fe_sample.json")
    if not os.path.exists(fix):
        subprocess.run([sys.executable, os.path.join(ROOT, "tests", "make_holo_fe_fixture.py")], check=True)
    F = json.load(open(fix, encoding="utf-8"))
    H = F["holo"]
    check("fixture: holo.json contract (v 1, le-holo, bars 1m / 5m, bots, fills with exact seconds, trades, thoughts)",
          H["v"] == 1 and H["kind"] == "le-holo" and H["bars"]["1m"] and H["bars"]["5m"] and set(H["bots"]) == {"lit", "atlas", "blitz"}
          and all(isinstance(f["t"], int) and f["side"] in ("BUY", "SELL") for f in H["fills"]) and H["trades"] and H["thoughts"])
    check("fixture: real Zlarior fills 1 tick off the model, paper ATLAS / BLITZ fills", any(f["real"] and f["slip_ticks"] == 1 for f in H["fills"])
          and any(not f["real"] for f in H["fills"]))
    check("fixture: holo_hist.json days", F["hist"]["kind"] == "le-holo-hist" and len(F["hist"]["days"]) >= 3)

    # static: byte-identical copies, the bundle exports the view, routes, pages, caches
    for a, b in (("tools/web_public/holocore.js", "web_next/js/next/holocore.js"), ("tools/web_public/holo.css", "web_next/css/holo.css"),
                 ("tools/web_public/fx.js", "web_next/js/fx.js")):
        check(f"static: {a} == {b}", rd(*a.split("/")) == rd(*b.split("/")))
    src, idx = rd("tools", "web_public", "fx", "src", "holo.js"), rd("tools", "web_public", "fx", "src", "index.js")
    check("static: fx.js exports FX.holo (holo.js: instanced candles, bloom on Max, the mirrored floor, own loop)",
          "export function holo(" in idx and "InstancedMesh" in src and "UnrealBloomPass" in src and "running() { return false; }" in src)
    bundle = rd("tools", "web_public", "fx.js")
    check("static: the bundle carries the Holodeck scene", "hd-labs" in bundle and "Inducement" in bundle and "le-holo" not in idx)
    pidx = rd("tools", "web_public", "index.html")
    check("static: phone index loads holo.js after liveview.js (one <script defer>)", re.search(r'<script src="holo\.js\?v=\w+" defer></script>', pidx)
          and pidx.index("liveview.js?v=") < pidx.index('"holo.js?v='))
    psw, sw = rd("tools", "web_public", "sw.js"), rd("web_next", "sw.js")
    check("static: caches bumped (phone le-public-v44+, PC le-shell-next-v26+)", int(re.search(r"le-public-v(\d+)", psw).group(1)) >= 44
          and int(re.search(r"le-shell-next-v(\d+)", sw).group(1)) >= 26)
    routes, app = rd("web_next", "js", "next", "routes.js"), rd("web_next", "js", "app.js")
    check("static: PC route Holodeck in Main after Live View + page module", "HOLO = { id: 'holo'" in routes and "indexOf('liveview')" in routes
          and "PAGES.holo = holoPage" in app)
    ph, pc = rd("tools", "web_public", "holo.js"), rd("web_next", "js", "next", "holo.js")
    check("static: phone reads holo.json / holo_hist.json from the live branch, GET only", "contents/${f}?ref=live" in ph and "/live/${f}" in ph
          and "holo_hist.json" in ph and "method:" not in ph and "POST" not in ph)
    check("static: PC reads GET /api/next/holo (+ /days), never POSTs", "/api/next/holo" in pc and "/api/next/holo/days" in pc and "POST" not in pc)
    check("static: Live View (PC) has the 3D button", 'data-goto="holo"' in rd("web_next", "js", "next", "liveview.js"))
    check("static: clean.js not bumped (clean.js?v=3)", 'clean.js?v=3"' in pidx)

    node = shutil.which("node")
    groot = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    if not node or not os.path.isdir(os.path.join(groot, "playwright")):
        print("[SKIP] Holodeck Playwright check: node + playwright not installed")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            site = os.path.join(tmp, "site")
            shutil.copytree(os.path.join(ROOT, "tools", "web_public"), site, ignore=shutil.ignore_patterns("fx", "node_modules"))
            T = int(time.time())
            data = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T - 600)),
                    "live": {"last_run": T - 600, "runs": 1, "pc": {"present": True, "t": T - 60, "age_s": 60, "running": True, "every_s": 60, "host": "SURFACE"}},
                    "accounts": [], "results": {"periods": {}}, "trades": [], "strategy": {}}
            for n in ("data.json", "home.json"):
                with open(os.path.join(site, n), "w", encoding="utf-8") as f:
                    json.dump(data, f)
            shots = os.environ.get("LE_SHOTS", "")
            if shots:
                os.makedirs(shots, exist_ok=True)
            env = {**os.environ, "NODE_PATH": groot}
            if os.path.isdir("/opt/pw-browsers"):
                env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
            r = subprocess.run([node, os.path.join(ROOT, "tests", "holo_ui_check.js"), site, os.path.join(ROOT, "web_next"), os.path.join(ROOT, "web"), fix, shots],
                               capture_output=True, text=True, timeout=420, env=env)
            try:
                out = json.loads((r.stdout or "").strip().splitlines()[-1])
            except Exception:
                out = None
                check("Playwright: the check ran", False, (r.stdout or "")[-400:] + (r.stderr or "")[-400:])
            if out:
                for name, ok, info in out.get("steps") or []:
                    check(f"Playwright {name}", ok, info)
                for k, v in (out.get("perf") or {}).items():
                    print(f"  perf {k}: {v}")
    print(f"\nholodeck ui: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
