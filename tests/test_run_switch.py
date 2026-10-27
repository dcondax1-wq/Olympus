"""The Run / Stop switch at the top of every PC dashboard page (web_next/js/next/runswitch.js, owner 2026-10-27: "a simple
stop and run switch on the dashboard"). Fast, no real files written: the start job is faked, nothing touches data/,
.env.local.ps1 or second_model.json (checked at the end).

  python -X utf8 -m tests.test_run_switch        # ~2 s

Checks: the switch is served and mounted in every page's top bar; Run POSTs /api/next/start/go, Stop POSTs /api/live/stop
(with the confirm text), never /api/live/kill; the phrase is typed by the owner only (never stored, never prefilled, the
field cleared, the dialog removed); the switch's states (node runs swState); /api/next/start/go refuses every non-local
caller (phone, Tailscale, tunnel, DNS rebinding, another site, cloud mode) and never starts a job for them.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from engine import cloud_guard as CG, go as G, start_api as S  # noqa: E402

RES = []
PHRASE = "I ACCEPT LIVE RISK"
REAL = [os.path.join(ROOT, p) for p in (".env.local.ps1", "second_model.json", "data/start_bot.json", "data/accounts.json",
                                         "data/autostart.json", "data/auto_resume.json", "logs/start_job.json")]
JS = os.path.join(ROOT, "web_next", "js", "next", "runswitch.js")


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def digest(paths):
    out = {}
    for p in paths:
        try:
            with open(p, "rb") as fh:
                out[p] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            out[p] = None
    return out


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return fh.read()


def static_checks():
    js = read("web_next/js/next/runswitch.js")
    app_js = read("web_next/js/app.js")
    css = read("web_next/css/start.css")
    sw = read("web_next/sw.js")
    code = "\n".join(ln for ln in js.splitlines() if not ln.lstrip().startswith("//"))     # without the comments
    boot = app_js[app_js.index("async function boot()"):]
    check("app.js imports the switch and mounts it at boot (every page)",
          "from './next/runswitch.js'" in app_js and "initRunSwitch();" in boot[:400])
    check("the switch sits in the shared top bar (.nx-top, just left of .tb-right), id runSw",
          "document.querySelector('.nx-top .tb-right')" in code and "el.id = 'runSw'" in code and "tb.parentElement.insertBefore(el, tb)" in code)
    idx = read("web_next/index.html")
    check("index.html: the top bar it mounts into + start.css", 'class="topbar nx-top"' in idx and 'class="tb-right"' in idx
          and "/css/start.css" in idx)
    check("the four states and their words", all(k in code for k in ("'running'", "'stopped'", "'starting'", "'need'"))
          and "Trading: Zlarior 50K + ATLAS 25K" in code and "'Stopped'" in code and "'Needs you'" in code)
    check("states styled (green / grey / amber / red)", all(f".rsw.{k}" in css for k in ("running", "stopped", "starting", "need")))
    check("Run = POST /api/next/start/go, Stop = POST /api/live/stop (one each)",
          code.count("postJSON('/api/next/start/go'") == 1 and code.count("postJSON('/api/live/stop'") == 1)
    check("Stop asks first, with the owner's sentence",
          "window.confirm('Stop trading? It stays stopped (also after a restart) until you press Run.')" in code)
    check("never the kill switch, never arm / live start / botctl start from the switch",
          "/api/live/kill" not in code and "/api/live/arm" not in code and "/api/live/start" not in code and "botctl/start" not in code)
    check("polls the status: 3 s while starting, 15 s otherwise",
          "fetch('/api/next/start/status')" in code and "FAST_MS = 3000" in code and "SLOW_MS = 15000" in code)
    # the phrase: only typed by the owner, sent once, never kept
    check("phrase dialog only when status.need_phrase", "d.need_phrase && !d.running" in code and "askPhrase()" in code)
    check("phrase field: password, no autocomplete, never prefilled",
          'type="password" name="rswp" autocomplete="off"' in code and 'value="' not in code.split("function askPhrase")[1].split("function postJSON")[0]
          and 'placeholder="type the phrase"' in code)
    check("phrase never stored: no localStorage / store / sessionStorage of it, only the 'auto' / 'tries' flags",
          "localStorage" not in code and "store." not in code and "from '../util.js'" in code and "store" not in code.split("from '../util.js'")[0]
          and set(re.findall(r"SS\.set\('(\w+)'", code)) <= {"auto", "tries"})
    check("phrase: field cleared and dialog removed at once, sent once as {confirm}, then dropped",
          "inp.value = ''; m.remove();" in code and "JSON.stringify({ confirm: a.phrase })" in code and "a.phrase = '';" in code
          and "finally { body = null; }" in code)
    check("phrase never re-sent by the automatic retry", "if (retry) { SS.set('auto', null); return; }" in code)
    check("off the PC: read-only 'PC: running / stopped', no button", "!d.local" in code and "PC: ${on ? 'running'" in code
          and "rsw ro" in code)
    check("old START buttons point to the switch (Bot Control hint, Start page line, Home 'what to do now')",
          "Run / Stop switch at the top" in read("web_next/js/next/botctl.js") and "switch at the top" in read("web_next/js/next/start.js")
          and "Press Run in the switch at the top" in read("web_next/js/next/cc.js"))
    check("Bot Control's HOLD TO KILL is still there", "holdToKill" in read("web_next/js/next/botctl.js")
          and "api('/api/live/kill'" in read("web_next/js/next/botctl.js"))
    v = re.search(r"le-shell-next-v(\d+)", sw)
    check("sw.js cache bumped for the switch (v22+)", v and int(v.group(1)) >= 22 and "runswitch" in sw, v and v.group(0))


def served_checks():
    app = FastAPI()
    st = StaticFiles(directory=os.path.join(ROOT, "web"))
    st.all_directories = [os.path.join(ROOT, "web_next"), os.path.join(ROOT, "web")]    # as server.py serves it
    app.mount("/", st, name="web")
    c = TestClient(app, base_url="http://127.0.0.1:8766")
    r = c.get("/js/next/runswitch.js")
    check("served: /js/next/runswitch.js", r.status_code == 200 and "export function initRunSwitch" in r.text, r.status_code)
    r = c.get("/js/app.js")
    check("served: app.js loads it", r.status_code == 200 and "./next/runswitch.js" in r.text)
    r = c.get("/css/start.css")
    check("served: the switch's styles", r.status_code == 200 and ".rsw.running" in r.text)
    r = c.get("/js/util.js")
    check("served: util.js (web/ fallback) has what the switch imports", r.status_code == 200 and "export const esc" in r.text
          and "export function toast" in r.text)


NODE = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');
const a = src.indexOf('export function swState');
const b = src.indexOf('\n}\n', a) + 2;
const RUNNING_TEXT = 'Trading: Zlarior 50K + ATLAS 25K', FRESH_S = 2 * 3600;
const swState = eval('(' + src.slice(a, b).replace('export ', '') + ')');
const now = 1800000000;
const base = { local: true, running: false, need_phrase: false, steps: [{ key: 'running', done: false }], job: { step: null, running: false } };
const C = (o) => Object.assign(JSON.parse(JSON.stringify(base)), o);
const out = {
  stopped: swState(C({}), now),
  phrase: swState(C({ need_phrase: true }), now),
  running: swState(C({ running: true, steps: [{ key: 'running', done: true }] }), now),
  wrong: swState(C({ running: true, steps: [{ key: 'running', done: false }] }), now),
  starting: swState(C({ job: { step: 'auto', running: true, say: 'Opening NinjaTrader' } }), now),
  need: swState(C({ job: { step: 'auto', running: false, rc: 1, t1: now - 60, need: 'nt', retry_s: 60, say: 'Log in to NinjaTrader.' } }), now),
  old: swState(C({ job: { step: 'auto', running: false, rc: 1, t1: now - 3 * 86400, say: 'Log in to NinjaTrader.' } }), now),
  oldPressed: swState(C({ job: { step: 'auto', running: false, rc: 1, t1: now - 3 * 86400, say: 'Log in to NinjaTrader.' } }), now, true),
  done: swState(C({ job: { step: 'auto', running: false, rc: 0, t1: now - 60 } }), now),
  offline: swState(null, now),
};
console.log(JSON.stringify(out));
"""


def state_checks():
    node = shutil.which("node")
    if not node:
        check("node available for the state checks (skipped)", True)
        return
    p = subprocess.run([node, "-e", NODE, JS], capture_output=True, text=True, timeout=30)
    try:
        o = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception as e:
        check("swState runs in node", False, (e, p.stderr[-400:]))
        return
    check("state: stopped -> grey 'Stopped', tap = Run", o["stopped"]["k"] == "stopped" and o["stopped"]["label"] == "Stopped"
          and o["stopped"]["can"] == "run", o["stopped"])
    check("state: need_phrase stays Stopped (Run opens the phrase dialog)", o["phrase"]["k"] == "stopped" and "phrase" in o["phrase"]["sub"], o["phrase"])
    check("state: running -> green 'Trading: Zlarior 50K + ATLAS 25K', tap = Stop", o["running"]["k"] == "running"
          and o["running"]["label"] == "Trading: Zlarior 50K + ATLAS 25K" and o["running"]["can"] == "stop", o["running"])
    check("state: running with the wrong set-up -> Needs you, Stop", o["wrong"]["k"] == "need" and o["wrong"]["can"] == "stop", o["wrong"])
    check("state: job running -> amber Starting with the job's say, no tap", o["starting"]["k"] == "starting"
          and o["starting"]["sub"] == "Opening NinjaTrader" and o["starting"]["can"] is None, o["starting"])
    check("state: job stopped with a reason -> red Needs you, the one sentence, Run again", o["need"]["k"] == "need"
          and o["need"]["sub"] == "Log in to NinjaTrader." and o["need"]["can"] == "run", o["need"])
    check("state: a days-old failed job is not shown as Needs you (unless Run was pressed in this tab)",
          o["old"]["k"] == "stopped" and o["oldPressed"]["k"] == "need", (o["old"], o["oldPressed"]))
    check("state: a finished job while stopped -> Stopped", o["done"]["k"] == "stopped", o["done"])
    check("state: no answer -> offline, no tap", o["offline"]["k"] == "offline" and o["offline"]["can"] is None, o["offline"])


def endpoint_checks():
    calls = []
    saved = {k: getattr(G, k) for k in ("job_start", "status", "accounts")}
    saved_s = {k: getattr(S, k) for k in ("_connected", "_feed", "_clock", "_poll", "_cards", "_bot")}
    env0 = os.environ.get("LE_CLOUD")
    try:
        G.job_start = lambda step, phrase=None: (calls.append((step, phrase)), {"ok": True, "say": "started"})[1]
        G.status = lambda state=None, connected=None, feed=None: {"steps": [], "running": False, "need_phrase": True,
                                                                  "job": {"step": None, "running": False}}
        G.accounts = lambda cards: {"rows": []}
        S._connected = lambda: True
        S._feed = lambda: None
        S._clock = lambda fresh=False: {"known": False, "ok": True}
        S._poll = lambda: None
        S._cards = lambda: {}
        S._bot = lambda: type("B", (), {"running": False, "cfg": {}})()
        os.environ.pop("LE_CLOUD", None)
        app = FastAPI()
        app.include_router(S.router)
        local = TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50001))
        others = {
            "phone": TestClient(app, base_url="http://192.168.1.20:8766", client=("192.168.1.50", 50003)),
            "tailscale": TestClient(app, base_url="http://100.101.102.103:8766", client=("100.64.0.7", 50004)),
            "tunnel": TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50005), headers={"X-Forwarded-For": "203.0.113.9"}),
            "rebind": TestClient(app, base_url="http://evil.example:8766", client=("127.0.0.1", 50006)),
            "origin": TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50007), headers={"Origin": "http://evil.example"}),
        }
        st = local.get("/api/next/start/status").json()
        check("status: local=true on the PC (the switch is a button)", st.get("local") is True and "need_phrase" in st, st)
        st = others["phone"].get("/api/next/start/status").json()
        check("status: local=false on the phone (the switch is read-only)", st.get("local") is False, st)
        for name, c in others.items():
            for body in ({}, {"confirm": PHRASE}):
                r = c.post("/api/next/start/go", json=body)
                check(f"go refused for {name} {'with' if body else 'without'} the phrase (403, no job)",
                      r.status_code == 403 and r.json().get("local") is False and not calls, (r.status_code, r.text, calls))
        os.environ["LE_CLOUD"] = "1"
        r = local.post("/api/next/start/go", json={})
        check("go refused in cloud mode (paper only)", r.status_code == 403 and not calls, r.text)
        os.environ.pop("LE_CLOUD", None)
        check("/api/next/start/go is in cloud_guard's blocked list", "/api/next/start/go" in CG.CLOUD_BLOCKED)
        r = local.post("/api/next/start/go", json={"confirm": "I accept"})
        check("go: a wrong phrase is refused, nothing starts", r.status_code == 400 and not calls, r.text)
        r = local.post("/api/next/start/go", json={})
        check("go on the PC without the phrase -> the one job (auto, no phrase)", r.status_code == 200 and calls == [("auto", None)], (r.text, calls))
        calls.clear()
        r = local.post("/api/next/start/go", json={"confirm": "i accept live risk"})
        check("go on the PC with the typed phrase (any capitals) -> the job gets the exact phrase once",
              r.status_code == 200 and calls == [("auto", PHRASE)], (r.text, calls))
    finally:
        for k, v in saved.items():
            setattr(G, k, v)
        for k, v in saved_s.items():
            setattr(S, k, v)
        if env0 is None:
            os.environ.pop("LE_CLOUD", None)
        else:
            os.environ["LE_CLOUD"] = env0
    srv = read("server.py")
    stop = srv[srv.index('@app.post("/api/live/stop")'):srv.index('@app.post("/api/live/kill")')]
    check("server: /api/live/stop clears the autostart record (a reboot does not resume) and does not touch auto-resume",
          '_autostart_clear("stop")' in stop and "autoresume" not in stop and "disable(" not in stop)


def main():
    before = digest(REAL)
    static_checks()
    served_checks()
    state_checks()
    endpoint_checks()
    check("the real data/, .env.local.ps1, second_model.json and logs/start_job.json did not change", digest(REAL) == before)
    n = sum(RES)
    print(f"run switch: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
