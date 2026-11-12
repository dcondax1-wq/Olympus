"""Phone Live View (owner 2026-10-28: "add it to the phone too"): engine/liveview_api.phone_view (liveview.json), the
extra file in the PC's live commit (engine/live_publish.push / Publisher.extra), the phone page (tools/web_public/liveview.js
+ the byte-identical liveviewchart.js / liveview.css) and a Playwright run of it at phone size (Home button, chart, thinking
cards, feed, 1m / 5m, full screen portrait + sideways, back gesture, "PC not sending" banner). Fake bot from
tests/test_liveview_api (CSV fallback off); every file goes to a temp dir.

  python -X utf8 -m tests.test_phone_liveview            # ~20 s (Playwright part skipped without node + playwright)
  LE_SHOTS=<dir> python -X utf8 -m tests.test_phone_liveview    # also saves the phone screenshots there
"""
from __future__ import annotations

import copy
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

from engine import liveview_api as L, live_publish as LP, narrator as N  # noqa: E402
from tests import test_liveview_api as F  # noqa: E402  (fake bot, brain, ATLAS; sets L.CSV_FALLBACK = False)
from engine import holo_api as HA  # noqa: E402  (the Holodeck files ride in the same commit: no real logs / data/ read)
_HT = tempfile.mkdtemp(prefix="phone_holo_")
HA.STORE, HA.NARR_DIR, HA.BRAIN_DIR, HA.STATE_PATH, HA.CSV_FALLBACK = _HT, _HT, _HT, os.path.join(_HT, "live_state.json"), False

RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def fixture(now):
    """A busy morning: a tapped Zlarior setup, ATLAS long on account B with its members, the feed."""
    sec = {"t": now, "day": "2026-10-14", "strategies": {
        "ema_lon_vix": {"short": "EMA", "label": "London EMA", "on": True, "state": {"stage": "waiting", "text": "Waiting for a pullback", "window": "03:00-09:30 ET"},
                        "brain": {"checks": [{"k": "t15", "name": "15m trend", "ok": True, "val": "down"}], "first_fail": None}},
        "macd_sweep": {"short": "MACD", "on": True, "state": {"stage": "armed", "text": "Armed (long)", "window": "02:00-05:00, 09:30-11:00 ET"},
                       "brain": {"plan": {"side": "long", "entry": 30790.0, "stop": 30770.0, "target": 30850.0}}}}}
    b = F.bot(now, second=sec, acct_b=F.AB())
    b.brain = F.brain(status="tapped")
    return b


def main():
    now = F.T(4, 50)
    b = fixture(now)
    before = copy.deepcopy((b.state, b.brain, b.ledger, b.cfg))
    v = L.phone_view(b, now, narr=N.Narrator())
    txt = json.dumps(v, separators=(",", ":"), default=str)
    check("phone_view: kind le-liveview, t, 1m bars + 5m bars5",
          v.get("kind") == "le-liveview" and v["t"] == now and v["bars"] and v["bars"][1][0] - v["bars"][0][0] == 60
          and v["bars5"] and v["bars5"][1][0] - v["bars5"][0][0] == 300, {k: v.get(k) for k in ("kind", "t", "error")})
    check("phone_view: at most 480 1m bars (8 h), the 5m session from 18:00", len(v["bars"]) <= L.PHONE_N1 and v["bars5"][0][0] >= v["t0"],
          (len(v["bars"]), v["bars5"][0][0], v["t0"]))
    check("phone_view: the three layers + the thinking panel", set(v["strategies"]) == {"lit", "atlas", "scalp"}
          and v["strategies"]["lit"]["thinking"]["headline"] and v["strategies"]["atlas"].get("members"), list(v["strategies"]))
    check("phone_view: feed cut to 60, under 240 KB", len(v.get("narrator") or []) <= L.PHONE_FEED and len(txt) < L.PHONE_MAX, len(txt))
    check("phone_view: no confirm phrase / webhook", "I ACCEPT" not in txt and "https://x" not in txt and "webhook" not in txt.lower())
    check("phone_view: read-only (bot state / brain / ledger / cfg unchanged)", copy.deepcopy((b.state, b.brain, b.ledger, b.cfg)) == before)
    m0 = L.PHONE_MAX
    try:
        L.PHONE_MAX = 12 * 1024
        vs = L.phone_view(fixture(now), now, narr=N.Narrator())
        check("phone_view trims 1m bars first (never below 120) when too big", vs.get("trimmed") and 120 <= len(vs["bars"]) < len(v["bars"]),
              (vs.get("trimmed"), len(vs["bars"])))
    finally:
        L.PHONE_MAX = m0
    bad = L.phone_view(object(), now)
    check("phone_view never raises (a broken bot -> a small answer)", isinstance(bad, dict) and bad.get("kind") == "le-liveview" and bad.get("t") == now, bad)

    # the live commit: live.json + liveview.json
    seen = {}
    pub = LP.Publisher(fixture(now), None, log=lambda t: None, clock=lambda: now, url="file:///x",
                       push_fn=lambda pl, url, **kw: seen.update(kw) or {"ok": True, "bytes": 10})
    ex = pub.extra()
    check("Publisher.extra(): liveview.json from phone_view, scrubbed (+ the Holodeck's holo.json / holo_hist.json)",
          list(ex)[:1] == ["liveview.json"] and set(ex) <= {"liveview.json", "holo.json", "holo_hist.json"} and ex["liveview.json"]["kind"] == "le-liveview"
          and "I ACCEPT" not in json.dumps(ex, default=str), list(ex))
    pub.publish(force=True)
    check("Publisher.publish passes liveview.json to the push", "liveview.json" in (seen.get("extra") or {}), list(seen))
    with tempfile.TemporaryDirectory() as tmp:
        remote = os.path.join(tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
        r = LP.push({"v": 1, "kind": "le-live", "t": now}, remote, git_dir=os.path.join(tmp, "scratch.git"), cwd=tmp,
                    extra={"liveview.json": v, "../evil.json": {"x": 1}, "live.json": {"x": 2}, "bad name.json": {}})
        ls = subprocess.run(["git", "--git-dir", remote, "ls-tree", "--name-only", "live"], capture_output=True, text=True).stdout.split()
        check("push: one commit with live.json + liveview.json (odd names refused, live.json not overwritten)",
              r.get("ok") and ls == ["live.json", "liveview.json"] and r["extra_bytes"].get("liveview.json", 0) > 1000, (r, ls))
        body = subprocess.run(["git", "--git-dir", remote, "show", "live:live.json"], capture_output=True, text=True).stdout
        check("push: live.json is still the live payload", json.loads(body).get("kind") == "le-live", body[:80])
        r2 = LP.push({"v": 1, "kind": "le-live", "t": now + 60}, remote, git_dir=os.path.join(tmp, "scratch.git"), cwd=tmp)
        ls2 = subprocess.run(["git", "--git-dir", remote, "ls-tree", "--name-only", "live"], capture_output=True, text=True).stdout.split()
        check("push without extra: live.json only (as before)", r2.get("ok") and ls2 == ["live.json"] and r2["extra_bytes"] == {}, (r2, ls2))

    # the phone page wiring
    pidx, lv, cl, lj, sw = (rd("tools", "web_public", n) for n in ("index.html", "liveview.js", "clean.js", "live.js", "sw.js"))
    check("liveviewchart.js + liveview.css byte-identical to the PC's", rd("tools", "web_public", "liveviewchart.js") == rd("web_next", "js", "next", "liveviewchart.js")
          and rd("tools", "web_public", "liveview.css") == rd("web_next", "css", "liveview.css"))
    check("index.html loads liveview.js after real.js; live.js v2", 'src="liveview.js?v=' in pidx and pidx.index("real.js?v=") < pidx.index("liveview.js?v=")
          and 'src="live.js?v=3"' in pidx)
    check("More > Today lists liveview; live.js waits on the Live View page", "['Today', ['liveview'," in cl and "PAGE === 'liveview'" in lj)
    check("phone cache bumped to le-public-v42+", int(re.search(r"le-public-v(\d+)", sw).group(1)) >= 42)
    check("liveview.js reads liveview.json from the live branch, GET only", "contents/liveview.json?ref=live" in lv and "/live/liveview.json" in lv
          and "method:" not in lv and "POST" not in lv)

    # Playwright at phone size
    node = shutil.which("node")
    groot = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    if not node or not os.path.isdir(os.path.join(groot, "playwright")):
        print("[SKIP] phone Playwright check: node + playwright not installed")
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
            lvp = os.path.join(tmp, "liveview.json")
            with open(lvp, "w", encoding="utf-8") as f:
                json.dump(LP.scrub(v), f, default=str)
            shots = os.environ.get("LE_SHOTS", "")
            if shots:
                os.makedirs(shots, exist_ok=True)
            env = {**os.environ, "NODE_PATH": groot}
            if os.path.isdir("/opt/pw-browsers"):
                env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
            r = subprocess.run([node, os.path.join(ROOT, "tests", "phone_liveview_check.js"), site, "8798", lvp, shots],
                               capture_output=True, text=True, timeout=240, env=env)
            try:
                out = json.loads((r.stdout or "").strip().splitlines()[-1])
            except Exception:
                out = None
                check("phone (Playwright): the check ran", False, (r.stdout or "")[-300:] + (r.stderr or "")[-300:])
            if out:
                for name, ok, info in out.get("steps") or []:
                    check(f"phone (Playwright): {name}", ok, info)
                if out.get("error"):
                    check("phone (Playwright): no harness error", False, out["error"])
    print(f"\nphone live view: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
