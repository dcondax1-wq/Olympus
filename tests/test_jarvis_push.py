"""Olympus phone notifications, the phone side (2026-11-19, owner: "I want notifications on my phone"): tools/web_public/jarvis/push-ui.js
(the card and its button) and push-sw.js (the worker's push / notificationclick handlers), in Chromium with a mocked PushManager.
  a. the files: Safari 16 safe, no key / no order words, push-sw.js is a classic worker script with the real handlers, index.html
     mounts #pushCard after the ZEUS card and loads push-ui.js
  b. the card + button (a harness page in /jarvis/ with the real files, the PC's status post and the relay answered by the test):
     Allow -> one subscription with the PC's key, sealed to the PC's box key (Python opens it: endpoint, keys, key, no plain
     endpoint on the relay) -> "on" when the PC lists the phone; Send a test / Turn off (sealed, with the phone's own secret);
     the PC's key changes -> subscribed again and sent again; the PC's own intake (engine/push.intake) accepts what the page sent
  c. the worker (a real service worker importing push-sw.js): an entry shows one notification, the exit replaces it (same tag), a
     second account's trade is its own; a tap opens the right page in a running Olympus; a critical alert's "Got it" posts the ack
     to the relay; a real push event (Chrome DevTools deliverPushMessage) goes through the real handler
  d. the real Olympus page: an iPhone Safari tab says "Add Olympus to your Home Screen first"; a phone that can gets the Allow button
     at once (44 px, no sideways scroll at 375 px); a tapped notification's cold start (./?open=board) opens the Board; no page error
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_jarvis_push      (~1-2 min)
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from tests import browser_kit as BK  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WP = os.path.join(ROOT, "tools", "web_public")
JV = os.path.join(WP, "jarvis")
RES: list = []
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from engine import push as P  # noqa: E402


def check(name, ok, info=""):
    RES.append((name, bool(ok)))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:900]}"), flush=True)


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def code(src):
    return re.sub(r"(^|[^:'\"\\])//[^\n]*", r"\1", src)


# ------------------------------------------------------------------------------------------------ a. the files
def part_a():
    ui, sw, page = read(JV, "push-ui.js"), read(JV, "push-sw.js"), read(JV, "index.html")
    for name, src in (("push-ui.js", ui), ("push-sw.js", sw)):
        r = subprocess.run(["node", "--check", "-"], input=src, capture_output=True, text=True)
        check(f"a. {name} parses", r.returncode == 0, r.stderr[-300:])
        check(f"a. {name} is Safari 16 safe (no optional chaining, no regex lookbehind)", "?." not in code(src) and not re.search(r"\(\?<[=!]", src))
        check(f"a. {name}: no key, no order / arming words", not re.search(r"gsk_|AIza|github_pat_|sk-ant-|vapid_private|place_?order|armLive|\.arm\(", src))
    check("a. push-sw.js: a classic worker script (importScripts-able, no import/export), push + notificationclick + pushsubscriptionchange handlers",
          not re.search(r"^\s*(import|export)\s", sw, re.M) and all(f"addEventListener('{e}'" in sw for e in ("push", "notificationclick", "pushsubscriptionchange")))
    check("a. push-sw.js: every push shows a notification (an iPhone drops a silent app), even when its data is broken",
          "showNotification('Olympus'" in sw and ".catch(() => G.registration.showNotification" in sw)
    check("a. index.html: #pushCard right after the ZEUS card, push-ui.js loaded (versioned, defer)",
          0 < page.find('id="zeusCard"') < page.find('id="pushCard"') < page.find('id="hfirst"')
          and re.search(r'<script src="\./push-ui\.js\?v=pu\d+" defer></script>', page))
    check("a. push-ui.js seals with the PC's label le-push-sub-v1 and posts {le, v: 2, box} only (no plain subscription on the relay)",
          "le-push-sub-v1" in ui and P.SUB_INFO == b"le-push-sub-v1" and "relayPost({ le: kind, v: 2, box })" in ui and "sub: { endpoint" not in ui.split("sendSealed('sub'")[0].split("async function postSub")[-1])


# ------------------------------------------------------------------------------------------------ the test server
HARNESS = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>push test</title></head><body style="background:#14110e;margin:0"><div class="push-host" id="pushCard" hidden></div>
<script>window.__opened = []; window.__jarvis = { show: function (id) { window.__opened.push(id); } };
navigator.serviceWorker.register(/old=1/.test(location.search) ? './__push_test_old_sw.js' : './__push_test_sw.js', { scope: './' });</script>
<script src="../pc_feed.js"></script><script src="./push-ui.js" defer></script></body></html>"""
TEST_SW = """// headless Chromium refuses notifications whatever the test grants: an in-memory notification centre on this registration (the real
// handlers of push-sw.js call it exactly like the phone's)
const mem = [];
const center = {
  showNotification: async (title, o) => {
    const n = { title, body: (o && o.body) || '', tag: (o && o.tag) || '', data: (o && o.data) || null, silent: !!(o && o.silent),
      close() { const i = mem.indexOf(n); if (i >= 0) mem.splice(i, 1); } };
    mem.push(n);
  },
  getNotifications: async (f) => mem.filter((n) => !f || !f.tag || n.tag === f.tag),
};
for (const k of ['showNotification', 'getNotifications']) Object.defineProperty(self.registration, k, { value: center[k], configurable: true });
importScripts('./push-sw.js');
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
const log = [];
const fakeFetch = async (url, opt) => {
  log.push([String(url), (opt && opt.method) || 'GET', (opt && opt.body) || null]);
  if (String(url).indexOf('push_relay.json') >= 0) return { ok: true, json: async () => ({ ntfy: 'https://ntfy.sh', topic: 'le-relaytest' }) };
  return { ok: true };
};
self.addEventListener('message', (e) => {
  const m = e.data || {}, port = e.ports && e.ports[0];
  const reply = (v) => { if (port) port.postMessage(v); };
  if (!m.cmd) return;                         // push-sw.js answers its own ping
  (async () => {
    if (m.cmd === 'push') await self.OLY_PUSH_SW.onPush(m.d, self.registration, self.clients);
    if (m.cmd === 'click') {
      const ns = await self.registration.getNotifications({ tag: m.tag });
      const r = await self.OLY_PUSH_SW.onClick(ns[0], m.action || '', self.clients, self.registration.scope, fakeFetch);
      reply({ r, log, n: ns.length });
      return;
    }
    const all = await self.registration.getNotifications();
    reply(all.map((n) => ({ title: n.title, body: n.body, tag: n.tag, data: n.data, silent: n.silent })));
  })().catch((err) => reply({ error: String(err) }));
});
"""


STUB_SW = "self.addEventListener('install', () => self.skipWaiting()); self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));"


class Handler(http.server.SimpleHTTPRequestHandler):
    stub_sw = False                 # the real page's own worker answered by a stub (its precache of ~100 files is not under test here)

    def log_message(self, *a, **k):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, FileNotFoundError):
            pass                    # the page gave up on a file / a file the site has but this checkout does not (home.json)

    def do_GET(self):  # noqa: N802
        virt = {"/jarvis/__push_test.html": ("text/html", HARNESS), "/jarvis/__push_test_sw.js": ("text/javascript", TEST_SW),
                "/jarvis/__push_test_old_sw.js": ("text/javascript", STUB_SW)}
        if Handler.stub_sw:
            virt["/jarvis/sw.js"] = ("text/javascript", STUB_SW)
        path = self.path.split("?")[0]
        if path in virt:
            ctype, body = virt[path]
            b = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)
            return
        return super().do_GET()


MOCK = """(() => {
  const PHONES = %s;
  let n = 0, cur = null;
  window.__push = { calls: [] };
  window.__perm = 'default';
  try { Object.defineProperty(Notification, 'permission', { get: () => window.__perm, configurable: true }); } catch (e) {}
  Notification.requestPermission = async () => { window.__perm = 'granted'; return 'granted'; };
  const b64 = (u) => { let s = ''; for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); return btoa(s).replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, ''); };
  function make(key) {
    const p = PHONES[n++ %% PHONES.length];
    const sub = { endpoint: p.endpoint, options: { applicationServerKey: key.buffer },
      toJSON() { return { endpoint: p.endpoint, expirationTime: null, keys: { p256dh: p.p256dh, auth: p.auth } }; },
      unsubscribe: async () => { window.__push.calls.push(['unsub', p.endpoint]); if (cur === sub) cur = null; return true; } };
    return sub;
  }
  PushManager.prototype.subscribe = async function (o) {
    const k = new Uint8Array(o.applicationServerKey);
    if (cur) throw new DOMException('a subscription with another key exists', 'InvalidStateError');
    window.__push.calls.push(['sub', b64(k)]);
    window.__perm = 'granted';
    cur = make(k);
    return cur;
  };
  PushManager.prototype.getSubscription = async function () { return cur; };
  try { localStorage.setItem('olympus.push.force', '1'); } catch (e) {}
})();"""


def core_post(status_topic, k, b, d, t):
    msg = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": t, "pc": {"present": True, "t": t}, "reporter": {"t": t}, "wp": {"k": k, "b": b, "d": d}}
    return json.dumps({"id": "x1", "time": t, "event": "message", "topic": status_topic, "message": json.dumps(msg)})


def later(p):
    """pc_feed.js shares one feed answer per page for 20 s (night-feedsA): the next PC status post is read after that"""
    p.clock.fast_forward(21000)


def sw_call(p, msg):
    return p.evaluate("""async (msg) => {
      const reg = await navigator.serviceWorker.ready;
      const ch = new MessageChannel();
      return await new Promise((ok) => { ch.port1.onmessage = (e) => ok(e.data); reg.active.postMessage(msg, [ch.port2]); setTimeout(() => ok({ timeout: true }), 15000); });
    }""", msg)


# ------------------------------------------------------------------------------------------------ b + c. the harness page
def part_bc(br, url):
    feed = json.loads(read(WP, "status_feed.json"))
    relay_cfg = json.loads(read(WP, "push_relay.json"))
    vapid_priv, vapid_pub = P.generate_keys()
    box_priv, box_pub = P.generate_keys()
    phones = []
    for i in range(3):
        from tests.test_webpush import phone
        _k, _a, s = phone(20 + i)
        phones.append({"endpoint": s["endpoint"], "p256dh": s["keys"]["p256dh"], "auth": s["keys"]["auth"]})
    world = {"k": vapid_pub, "b": box_pub, "d": [], "posts": [], "gets": 0}
    now = int(time.time())

    def ntfy(route):
        req = route.request
        if req.method == "POST" and req.url.rstrip("/").endswith("/" + relay_cfg["topic"]):
            world["posts"].append(json.loads(req.post_data or "{}"))
            return route.fulfill(status=200, content_type="application/json", body="{}")
        if req.method == "GET" and ("/" + feed["topic"] + "/json") in req.url:
            world["gets"] += 1
            return route.fulfill(status=200, content_type="application/x-ndjson", body=core_post(feed["topic"], world["k"], world["b"], world["d"], now) + "\n")
        return route.fulfill(status=200, content_type="application/json", body="{}")

    def harness(q=""):
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, service_workers="allow")
        ctx.add_init_script(MOCK % json.dumps(phones))
        ctx.route(re.compile(r"^https://ntfy\.sh/"), ntfy)
        ctx.clock.install()
        p = ctx.new_page()
        errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto(url + "jarvis/__push_test.html" + q)
        return ctx, p, errs

    # the previous Olympus worker is still in charge (an update not taken over yet): never subscribe it (an iPhone would drop a
    # subscription whose pushes show nothing)
    ctx, p, errs = harness("?old=1")
    p.wait_for_function("document.getElementById('pushCard').dataset.state === 'ready'", timeout=30000, polling=200)
    p.click("#pushCard [data-push=allow]")
    p.wait_for_function("document.getElementById('pushCard').dataset.state === 'update'", timeout=60000, polling=250)
    check("b. a worker without the push handlers in charge: the tap asks permission but never subscribes; the card says close and open again",
          not [c for c in p.evaluate("window.__push.calls") if c[0] == "sub"] and not world["posts"] and "open it again" in p.inner_text("#pushCard")
          and p.locator("#pushCard [data-push=allow]").inner_text() == "Try again", (p.evaluate("window.__push.calls"), p.inner_text("#pushCard")))
    ctx.close()
    ctx, p, errs = harness()
    p.wait_for_function("document.getElementById('pushCard').dataset.state === 'ready'", timeout=30000, polling=200)
    btn = p.locator("#pushCard [data-push=allow]")
    check("b. a phone that can: the card says what it gives and shows ONE button, 'Allow notifications', 44 px tall",
          btn.count() == 1 and btn.inner_text() == "Allow notifications" and btn.bounding_box()["height"] >= 44
          and "Every entry and exit" in p.inner_text("#pushCard"), p.inner_text("#pushCard"))
    btn.click()
    p.wait_for_function("document.getElementById('pushCard').dataset.state === 'waiting'", timeout=30000, polling=200)
    calls = p.evaluate("window.__push.calls")
    subs = [x for x in world["posts"] if x.get("le") == "sub"]
    box = {}
    try:
        box = json.loads(P.unseal(subs[0]["box"], box_priv, P.SUB_INFO))
    except Exception as e:  # noqa: BLE001
        box = {"error": repr(e)}
    raw = json.dumps(world["posts"])
    check("b. one tap = one subscription with the PC's own key (applicationServerKey = wp.k)", [c[0] for c in calls] == ["sub"]
          and P.b64u(P.b64u_dec(calls[0][1])) == vapid_pub, calls)
    check("b. the relay gets ONE sealed message {le: sub, v: 2, box}: no endpoint, no key in the clear",
          len(subs) == 1 and set(subs[0]) == {"le", "v", "box"} and subs[0]["v"] == 2 and phones[0]["endpoint"] not in raw and phones[0]["auth"] not in raw, world["posts"])
    check("b. only the PC opens it (WebCrypto seal = engine/push.unseal): the subscription, made for the PC's key, from an iPhone or computer, just now",
          box.get("le") == "sub" and box.get("sub", {}).get("endpoint") == phones[0]["endpoint"] and box["sub"]["keys"] == {"p256dh": phones[0]["p256dh"], "auth": phones[0]["auth"]}
          and box.get("key") == vapid_pub and box.get("ua") == "computer" and abs(int(box.get("t") or 0) - time.time()) < 120, box)
    check("b. then: 'on for this phone, your PC confirms within 5 minutes'", "confirms within 5 minutes" in p.inner_text("#pushCard"), p.inner_text("#pushCard"))
    # the PC's own intake accepts exactly what the page sent (sandboxed files)
    tmp = tempfile.mkdtemp(prefix="jpush_")
    saved = (P.CONFIG_PATH, P.PC_KEY_PATH)
    try:
        P.CONFIG_PATH, P.PC_KEY_PATH = os.path.join(tmp, "push.json"), os.path.join(tmp, "pck.json")
        P._write_private(P.CONFIG_PATH, {"vapid_private": vapid_priv})
        P._write_private(P.PC_KEY_PATH, {"private": box_priv})
        got = []
        ir = P.intake([dict(m, _t=i + 1) for i, m in enumerate(world["posts"])], int(time.time()), sender=lambda s, d, pr, pu: got.append(json.loads(d)) or 201)
        pid = P.endpoint_id(phones[0]["endpoint"])
        check("b. the PC's 5-minute intake takes the page's message: the phone joins and gets the welcome notification",
              ir.get("added") == [pid] and got and got[0]["title"] == "Olympus notifications are on", (ir, got))
        world["d"] = [pid[:8]]
        later(p)
        st = p.evaluate("window.OLY_PUSH.check().then(() => window.OLY_PUSH.state())")
        card = p.inner_text("#pushCard")
        check("b. the PC's next status post lists the phone: the card says 'Notifications on' with Send a test / Turn off",
              st["state"] == "on" and st["id"] == pid and "Notifications on" in card and p.locator("#pushCard [data-push=test]").count() == 1
              and p.locator("#pushCard [data-push=off]").count() == 1, (st, card))
        n0 = len(world["posts"])
        p.click("#pushCard [data-push=test]")
        p.wait_for_function("document.querySelector('#pushCard .pushc-n') && /within 5 minutes/.test(document.querySelector('#pushCard .pushc-n').innerText)", timeout=20000)
        tests = [x for x in world["posts"][n0:] if x.get("le") == "test"]
        tb = json.loads(P.unseal(tests[0]["box"], box_priv, P.SUB_INFO)) if tests else {}
        got.clear()
        ir2 = P.intake([dict(m, _t=100 + i) for i, m in enumerate(world["posts"])], int(time.time()), sender=lambda s, d, pr, pu: got.append(json.loads(d)) or 201)
        check("b. Send a test: a sealed request with this phone's id and its own secret; the PC answers with one test notification",
              len(tests) == 1 and tb.get("id") == pid and tb.get("auth") == phones[0]["auth"] and ir2.get("tests") == [pid] and got and got[0]["title"] == "Test from your PC",
              (tests, tb, ir2, got))
        # the PC's key changes (its key file was lost): the phone subscribes again with the new one, by itself
        v2_priv, v2_pub = P.generate_keys()
        world["k"], world["d"] = v2_pub, []
        n0 = len(world["posts"])
        later(p)
        st = p.evaluate("window.OLY_PUSH.check().then(() => window.OLY_PUSH.state())")
        calls = p.evaluate("window.__push.calls")
        nb = [json.loads(P.unseal(x["box"], box_priv, P.SUB_INFO)) for x in world["posts"][n0:] if x.get("le") == "sub"]
        check("b. the PC's key changed: the old subscription goes, a new one is made with the new key and sent (no tap)",
              [c[0] for c in calls[-2:]] == ["unsub", "sub"] and P.b64u(P.b64u_dec(calls[-1][1])) == v2_pub and len(nb) == 1 and nb[0]["key"] == v2_pub
              and nb[0]["sub"]["endpoint"] == phones[1]["endpoint"] and st["state"] == "waiting", (calls, nb, st))
        world["d"] = [P.endpoint_id(phones[1]["endpoint"])[:8]]
        later(p)
        p.evaluate("window.OLY_PUSH.check()")
        p.wait_for_function("document.getElementById('pushCard').dataset.state === 'on'", timeout=20000)
        n0 = len(world["posts"])
        p.click("#pushCard [data-push=off]")
        p.wait_for_function("document.getElementById('pushCard').dataset.state === 'off'", timeout=20000)
        un = [json.loads(P.unseal(x["box"], box_priv, P.SUB_INFO)) for x in world["posts"][n0:] if x.get("le") == "unsub"]
        st2 = p.evaluate("window.OLY_PUSH.check().then(() => window.OLY_PUSH.state())")
        check("b. Turn off: a sealed unsub with the phone's own secret, the subscription ended, and it stays off (no silent re-subscribe)",
              len(un) == 1 and un[0]["id"] == P.endpoint_id(phones[1]["endpoint"]) and un[0]["auth"] == phones[1]["auth"]
              and p.evaluate("window.__push.calls")[-1][0] == "unsub" and st2["state"] == "off"
              and p.locator("#pushCard [data-push=allow]").count() == 1, (un, st2))
        # never nagging (phone QA 2026-11-19): "Not now" puts the question away for 7 days; once on, the card leaves the home after a day
        n0 = len(world["posts"])
        p.click("#pushCard [data-push=later]")
        gone = p.evaluate("document.getElementById('pushCard').hidden")
        st3 = p.evaluate("window.OLY_PUSH.check().then(() => [window.OLY_PUSH.state().state, document.getElementById('pushCard').hidden, JSON.parse(localStorage.getItem('olympus.push')).later - Date.now()])")
        ui = read(JV, "push-ui.js")
        check("b. 'Not now': the card leaves the home and stays away for 7 days (still off underneath, nothing sent); 'on' leaves the home after one day",
              gone and st3[0] == "off" and st3[1] is True and 6.9 * 86400e3 < st3[2] <= 7 * 86400e3 and len(world["posts"]) == n0
              and "ON_SHOW_MS = 86400 * 1000" in ui and "state === 'on' && +s0.onAt > 0 && now - +s0.onAt > ON_SHOW_MS" in ui, (gone, st3))
    finally:
        P.CONFIG_PATH, P.PC_KEY_PATH = saved
        shutil.rmtree(tmp, ignore_errors=True)
    # ---------------- c. the worker
    entry = {"title": "Zlarior 50K: LONG opened", "body": "risk $303 · target +$4,557. 6 MNQ at 24,980.25.", "tag": "t1a2b3c-1795050000", "url": "#nq",
             "kind": "fill", "key": "fill:1795050000", "t": 1795050000}
    ex = dict(entry, title="Zlarior 50K: LONG closed +$605", body="Target hit · +2.0R · 10:58 AM ET.", kind="outcome", key="out:1795050000", t=1795053000)
    other = dict(entry, title="Zlarior 25K #2: LONG opened", tag="t9f8e7d-1795050000", key="fill:1795050000:x")
    a1 = sw_call(p, {"cmd": "push", "d": entry})
    a2 = sw_call(p, {"cmd": "push", "d": ex})
    a3 = sw_call(p, {"cmd": "push", "d": other})
    mine = [n for n in a3 if isinstance(n, dict) and n.get("tag", "").startswith("t")] if isinstance(a3, list) else a3
    check("c. an entry shows one notification with the account name", isinstance(a1, list) and [n["title"] for n in a1] == ["Zlarior 50K: LONG opened"], a1)
    check("c. the exit replaces it: still one notification, now 'Zlarior 50K: LONG closed +$605'",
          isinstance(a2, list) and [n["title"] for n in a2] == ["Zlarior 50K: LONG closed +$605"] and a2[0]["tag"] == entry["tag"], a2)
    check("c. another account's trade on the same bar is its own notification", isinstance(mine, list) and sorted(n["title"] for n in mine)
          == ["Zlarior 25K #2: LONG opened", "Zlarior 50K: LONG closed +$605"], a3)
    p.evaluate("window.__opened = []")
    c1 = sw_call(p, {"cmd": "click", "tag": entry["tag"]})
    p.wait_for_function("window.__opened.length > 0", timeout=10000)
    check("c. a tap on a trade notification tells the running Olympus to open the NQ page (one message, no new window)",
          isinstance(c1, dict) and c1.get("r", {}).get("app") == "nq" and c1["r"].get("focused") and p.evaluate("window.__opened") == ["nq"], (c1, p.evaluate("window.__opened")))
    crit = {"title": "Position mismatch", "body": "Flatten by hand.", "tag": "le-crit-pos", "url": "#board", "kind": "risk", "key": "crit:pos:1", "t": 1795050000, "ack": "pos"}
    sw_call(p, {"cmd": "push", "d": crit})
    c2 = sw_call(p, {"cmd": "click", "tag": "le-crit-pos", "action": "ack"})
    posts = [x for x in (c2.get("log") or []) if x[1] == "POST"] if isinstance(c2, dict) else []
    check("c. a critical alert's Got it posts {le: ack, id} to the relay (the PC stops repeating it) and opens nothing",
          len(posts) == 1 and posts[0][0] == "https://ntfy.sh/le-relaytest" and json.loads(posts[0][2])["le"] == "ack" and json.loads(posts[0][2])["id"] == "pos"
          and c2["r"].get("app") is None, c2)
    # a real push event through the real handler (Chrome DevTools: ServiceWorker.deliverPushMessage)
    ok_real, info = False, ""
    try:
        cdp = ctx.new_cdp_session(p)
        regs = []
        cdp.on("ServiceWorker.workerRegistrationUpdated", lambda e: regs.extend(e.get("registrations") or []))
        cdp.send("ServiceWorker.enable")
        t0 = time.time()
        while not regs and time.time() - t0 < 10:
            p.wait_for_timeout(200)
        rid = next((r["registrationId"] for r in regs if r.get("scopeURL", "").endswith("/jarvis/")), None)
        payload = dict(entry, title="Zlarior 50K: SHORT opened", tag="t5e5e5e-1795060000", key="fill:1795060000")
        cdp.send("ServiceWorker.deliverPushMessage", {"origin": url.rstrip("/"), "registrationId": rid, "data": json.dumps(payload)})
        t0 = time.time()
        while time.time() - t0 < 15:
            got = sw_call(p, {"cmd": "list"})
            if isinstance(got, list) and any(n.get("title") == "Zlarior 50K: SHORT opened" for n in got):
                ok_real = True
                break
            p.wait_for_timeout(300)
        info = (rid, got)
    except Exception as e:  # noqa: BLE001
        info = repr(e)
    check("c. a real push event (DevTools deliverPushMessage) goes through push-sw.js's own handler and shows the notification", ok_real, info)
    check("c. no page error on the harness", not errs, errs[:3])
    ctx.close()


# ------------------------------------------------------------------------------------------------ d. the real Olympus page
IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"


def part_d(br, url):
    def page(ua=None, q="", width=390):
        kw = {"user_agent": ua} if ua else {}
        Handler.stub_sw = ua is None and not q          # a phone that can: its worker is there (a stub), so the card gets past it
        ctx = br.new_context(viewport={"width": width, "height": 844}, device_scale_factor=1, service_workers="allow" if Handler.stub_sw else "block", **kw)
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1[:/])"), lambda r: r.abort())          # nothing leaves the machine
        ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); "
                            "localStorage.setItem('jarvis.speak', 'off'); localStorage.setItem('olympus.push.force', '1'); } catch (e) {}")
        if ua is None:      # a phone that can, not asked yet (headless Chromium answers "denied" by itself)
            ctx.add_init_script("try { Object.defineProperty(Notification, 'permission', { get: () => 'default', configurable: true }); } catch (e) {}")
        p = ctx.new_page()
        errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto(url + "jarvis/" + q)
        p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=90000, polling=250)
        return ctx, p, errs

    ctx, p, errs = page(IPHONE_UA)
    p.wait_for_function("document.getElementById('pushCard') && document.getElementById('pushCard').dataset.state === 'homescreen'", timeout=20000)
    t = p.inner_text("#pushCard")
    check("d. an iPhone Safari tab: 'Add Olympus to your Home Screen first' (Share, Add to Home Screen), no button that cannot work",
          "Add Olympus to your Home Screen first" in t and "Add to Home Screen" in t and p.locator("#pushCard button").count() == 0, t)
    box = p.evaluate("(() => { const z = document.getElementById('zeusCard').getBoundingClientRect(), c = document.getElementById('pushCard').getBoundingClientRect(); return { z: z.bottom, c: c.top, h: c.height }; })()")
    check("d. the card sits right under the ZEUS card on the home", box["c"] >= box["z"] - 1 and box["h"] > 40, box)
    check("d. no page error (iPhone tab)", not errs, errs[:3])
    ctx.close()
    ctx, p, errs = page(None, width=375)
    p.wait_for_function("document.getElementById('pushCard') && !document.getElementById('pushCard').hidden", timeout=20000)
    st = p.evaluate("document.getElementById('pushCard').dataset.state")
    b = p.locator("#pushCard [data-push=allow]")
    sx = p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("d. a phone that can: the Allow button is there from the first paint (no jump when the PC answers), 44 px, no sideways scroll at 375 px",
          st in ("ready", "nopc") and b.count() == 1 and b.bounding_box()["height"] >= 44 and sx <= 0, (st, sx))
    check("d. no page error (375 px)", not errs, errs[:3])
    ctx.close()
    Handler.stub_sw = False
    ctx, p, errs = page(None, q="?open=board")
    p.wait_for_function("window.__jarvis && window.__jarvis.active() === 'board'", timeout=20000, polling=250)
    check("d. a tapped notification's cold start (./?open=board) opens the Board, and the address is clean again",
          p.evaluate("window.__jarvis.active()") == "board" and "open=" not in p.evaluate("location.search"), p.evaluate("location.href"))
    check("d. no page error (deep link)", not errs, errs[:3])
    ctx.close()


def run_browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        check("playwright available", False, e)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=WP))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            for part in (part_bc, part_d):
                try:
                    part(br, url)
                except Exception as e:  # noqa: BLE001
                    import traceback
                    traceback.print_exc()
                    check(f"{part.__name__} ran without an exception", False, repr(e))
    finally:
        srv.shutdown()


def main() -> int:
    if not shutil.which("node"):
        check("node is installed", False)
        return 1
    part_a()
    run_browser()
    bad = [n for n, ok in RES if not ok]
    print(f"\njarvis push: {len(RES) - len(bad)}/{len(RES)} {'ALL PASS' if not bad else 'FAILED: ' + '; '.join(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
