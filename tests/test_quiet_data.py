"""Quiet data (QA round 6, bugs 5 and 6): optional files never put a red 404 in the console, dead live sources fail quietly, fast and once.

    python -X utf8 -m tests.test_quiet_data

No browser. a. olympus/quiet-net.js in node (a mocked network): the suspended GitHub sources are asked ONCE per session with a 4 s limit
(the old Kalshi server's kalshi-feed never: retired, polish2 2026-11-19),
later asks get an immediate 404 made locally (no network), other addresses pass untouched, a caller's own abort is not remembered as a dead
source, the site's optional kalshi.json is asked once; b. the pages that ask for those sources load quiet-net.js before their own scripts;
c. the builders publish an honest empty file for the optional files (people.json never lists kalshi/ or zenith/ cards, cronos placeholders,
Sibyl's ledger, the Polis sky); d. kalshi/icon.svg exists.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
sys.path.insert(0, ROOT)
FAILS: list = []
N = [0]


def check(name, ok, detail=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        FAILS.append(name)


# the pages that ask for a dead live source or the optional kalshi.json (the lead's console report + the QA scan, 2026-11-11)
PAGES = ["index.html", "jarvis/index.html", "kalshi/index.html", "kalshicity/index.html", "ergasterion/index.html", "symposium/index.html",
         "polis/index.html", "olympus/people-lab.html", "hermes/index.html", "inbox/index.html", "ledger/index.html", "dionysus/index.html",
         "fates/index.html", "stoa/index.html", "tyche/index.html", "arena/index.html", "oracle/index.html", "cities/index.html"]

HARNESS = r"""
const fs = require('fs'), path = require('path');
const src = fs.readFileSync(process.argv[2], 'utf8');
const store = {}, calls = [], events = [];
let mode = {};
const sessionStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: (k) => { delete store[k]; } };
const location = { href: 'https://site.example/jarvis/', origin: 'https://site.example' };
function rawFetch(input, init) {
  const url = typeof input === 'string' ? input : input.url; calls.push(url);
  const m = Object.keys(mode).find((k) => url.indexOf(k) >= 0), how = m ? mode[m] : 200;
  if (how === 'hang') return new Promise((ok, no) => { const s = init && init.signal; if (s) s.addEventListener('abort', () => no(Object.assign(new Error('aborted'), { name: 'AbortError' }))); });
  return Promise.resolve(new Response('{"ok":true}', { status: how, headers: { 'content-type': 'application/json' } }));
}
const handlers = {};
const window = { fetch: rawFetch, dispatchEvent: (e) => events.push(e.detail && e.detail.id), location, addEventListener: (t, f) => { (handlers[t] = handlers[t] || []).push(f); } };
store['olympus.deadsrc.v1'] = JSON.stringify({ 'site:kalshi.json': { ok: false, at: Date.now(), status: 404, why: 'HTTP 404' }, 'raw:nq-dashboard': { ok: false, at: Date.now() - 7 * 3600e3, status: 404, why: 'HTTP 404' } });
const document = { currentScript: { getAttribute: (k) => (k === 'data-fresh' ? 'site:kalshi.json,raw:kalshi-feed' : null) } };
const CustomEvent = class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } };
new Function('window', 'location', 'sessionStorage', 'CustomEvent', 'Response', 'URL', 'AbortController', 'setTimeout', 'clearTimeout', 'document', src)(window, location, sessionStorage, CustomEvent, Response, URL, AbortController, setTimeout, clearTimeout, document);
const fresh0 = JSON.parse(store['olympus.deadsrc.v1'] || '{}');
const F = window.fetch, NET = window.OLYMPUS_NET, out = {};
const RAW = 'https://raw.githubusercontent.com/demetrades2000-coder/nq-dashboard/live/live.json', API = 'https://api.github.com/repos/demetrades2000-coder/nq-dashboard/contents/live.json?ref=live';
const KRAW = 'https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json', KAPI = 'https://api.github.com/repos/demetrades2000-coder/kalshi-feed/contents/kalshi.json?ref=main';
(async () => {
  mode = { 'nq-dashboard/live': 404, 'repos/demetrades2000-coder/nq-dashboard': 403, 'kalshi-feed': 200, '/kalshi.json': 404 };
  // a. ten asks at once for the raw live feed + ten later: one network call
  const first = await Promise.all(Array.from({ length: 10 }, (_, i) => F(RAW + '?t=' + i)));
  const later = await Promise.all(Array.from({ length: 10 }, (_, i) => F(RAW + '?t=x' + i)));
  out.raw = { calls: calls.filter((u) => u.indexOf('raw.githubusercontent.com/demetrades2000-coder/nq-dashboard') >= 0).length, status: first.concat(later).map((r) => r.status), quiet: later.every((r) => r.headers.get('x-olympus-quiet') === '1'), dead: NET.dead('raw:nq-dashboard'), line: NET.line('raw:nq-dashboard') };
  const a1 = await F(API), a2 = await F(API);
  out.api = { calls: calls.filter((u) => u.indexOf('api.github.com') >= 0 && u.indexOf('nq-dashboard') >= 0).length, status: [a1.status, a2.status], dead: NET.dead('api:nq-dashboard') };
  // the memory forgotten (a new session), the API now hangs: the caller's own abort is not a dead source; a host that never answers is
  // cut at 4 s, then remembered (the raw feed asked once more so it is remembered again for the tap test below)
  NET.forget(); mode = Object.assign({}, mode, { 'repos/demetrades2000-coder/nq-dashboard': 'hang' });
  const apiBefore = calls.filter((u) => u.indexOf('api.github.com') >= 0 && u.indexOf('nq-dashboard') >= 0).length;
  const ac = new AbortController(); const p = F(API + '?a=1', { signal: ac.signal }); ac.abort(); let e2 = ''; try { await p; } catch (e) { e2 = e.name; }
  out.abort = { err: e2, dead: NET.dead('api:nq-dashboard') };
  const t0 = Date.now(); let err = '';
  try { await F(API + '?h=1'); } catch (e) { err = e.name || String(e); }
  const took = Date.now() - t0, k2 = await F(API + '?h=2');
  out.hang = { took, err, second: k2.status, calls: calls.filter((u) => u.indexOf('api.github.com') >= 0 && u.indexOf('nq-dashboard') >= 0).length - apiBefore, line: NET.line('api:nq-dashboard') };
  await F(RAW + '?again=1');
  // the site's optional kalshi.json: asked once, then remembered; a 200 elsewhere is untouched; other addresses pass through
  const l1 = await F('../kalshi.json?t=1'), l2 = await F('../kalshi.json?t=2'), l3 = await F('/kalshicity/learned.json'), l4 = await F('https://api.coingecko.com/api/v3/simple/price');
  out.local = { calls: calls.filter((u) => /kalshi\.json/.test(u) && u.indexOf('github') < 0).length, status: [l1.status, l2.status, l3.status, l4.status] };
  // night-bugsweep: an app's status card on this site: a folder the site leaves out (mind/) is remembered per folder; a good card is asked as usual
  mode = Object.assign({}, mode, { '/mind/jarvis.json': 404 });
  const c1 = await F('/mind/jarvis.json?jt=1'), c2 = await F('../mind/jarvis.json?jt=2'), c3 = await F('/oracle/jarvis.json'), c4 = await F('/oracle/jarvis.json'), c5 = await F('https://other.example/mind/jarvis.json');
  out.cards = { mind: calls.filter((u) => /mind\/jarvis\.json/.test(u) && u.indexOf('other.example') < 0).length, oracle: calls.filter((u) => u.indexOf('/oracle/jarvis.json') >= 0).length,
    other: calls.filter((u) => u.indexOf('other.example') >= 0).length, status: [c1.status, c2.status, c3.status, c4.status, c5.status], dead: NET.dead('card:mind'), okDead: NET.dead('card:oracle') };
  out.post = (await F(RAW, { method: 'POST' })).status;
  out.state = Object.keys(NET.state()).sort();
  out.forgot = null;
  out.events = events.length;
  out.fresh = Object.keys(fresh0);
  // the owner taps Refresh: the next ask goes to the real source once, even though it is remembered as dead
  mode = { 'nq-dashboard/live': 200 };
  const before = calls.length; await F(RAW); const skipped = calls.length - before;
  (handlers.click || []).forEach((f) => f()); const r2 = await F(RAW); const tried = calls.length - before - skipped;
  out.gesture = { skipped, tried, status: r2.status, dead: NET.dead('raw:nq-dashboard') };
  // polish2 2026-11-19: the old Kalshi server's feed (kalshi-feed, raw and API) is RETIRED: never on the network, not the first time, not right
  // after a tap, not when a page names it in data-fresh (the harness did), even if it would answer; an instant local 404 every time
  mode = { 'kalshi-feed': 200 };
  const tk = Date.now(), q1 = await F(KRAW), q2 = await F(KAPI, { headers: { Accept: 'application/vnd.github.raw+json' } });
  (handlers.click || []).forEach((f) => f()); const q3 = await F(KRAW + '?t=tap');
  out.retired = { calls: calls.filter((u) => u.indexOf('kalshi-feed') >= 0).length, status: [q1.status, q2.status, q3.status], took: Date.now() - tk,
    quiet: [q1, q2, q3].every((r) => r.headers.get('x-olympus-quiet') === '1'), dead: NET.dead('raw:kalshi-feed') && NET.dead('api:kalshi-feed'),
    line: NET.line('raw:kalshi-feed'), state: NET.state()['api:kalshi-feed'] || null };
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def node_part():
    exe = shutil.which("node")
    if not exe:
        check("a. node tests skipped: no node", True)
        return
    tmp = tempfile.mkdtemp(prefix="quiet-")
    try:
        h = os.path.join(tmp, "h.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        r = subprocess.run([exe, h, os.path.join(WEB, "olympus", "quiet-net.js")], capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("a. the node harness runs", False, r.stderr[-800:])
            return
        o = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    R = o["raw"]
    check("a. 20 asks for the dead raw live feed (10 at once, 10 later): ONE network call, every answer a 404, the later ones made locally",
          R["calls"] == 1 and set(R["status"]) == {404} and R["quiet"] and R["dead"], R)
    check("a. the line says where and since when: 'PC live feed (raw): offline since .. (HTTP 404), asked once this session'",
          R["line"].startswith("PC live feed (raw): offline since") and "HTTP 404" in R["line"] and "asked once" in R["line"], R["line"])
    check("a. the API's 403 (rate limit / suspended) is remembered too: one call for two asks", o["api"]["calls"] == 1 and o["api"]["status"] == [403, 404] and o["api"]["dead"], o["api"])
    H = o["hang"]
    check("a. a host that never answers is cut at 4 s, then remembered (the next ask is instant, no second call)",
          3900 <= H["took"] <= 6500 and H["err"] == "AbortError" and H["second"] == 404 and H["calls"] == 2 and "no answer in 4 s" in H["line"], H)
    check("a. the page's own abort is not taken as a dead source", o["abort"]["err"] == "AbortError" and not o["abort"]["dead"], o["abort"])
    K = o["retired"]
    check("a. the old Kalshi server's feed (kalshi-feed raw + API) is retired: never asked, not after a tap, not via data-fresh; an instant local 404",
          K["calls"] == 0 and K["status"] == [404, 404, 404] and K["quiet"] and K["dead"] and K["took"] < 200
          and "retired" in K["line"] and "never asked" in K["line"] and (K["state"] or {}).get("retired") is True, K)
    check("a. the site's optional kalshi.json: asked once (404 remembered); other site files and other hosts pass untouched",
          o["local"]["calls"] == 1 and o["local"]["status"] == [404, 404, 200, 200], o["local"])
    C = o["cards"]
    check("a. an app's status card on this site (<folder>/jarvis.json): a folder not on the site (mind/) asked once, its 404 remembered; a good card (oracle/) asked every time; another site untouched",
          C["mind"] == 1 and C["oracle"] == 2 and C["other"] == 1 and C["status"] == [404, 404, 200, 200, 404] and C["dead"] and not C["okDead"], C)
    check("a. a page's data-fresh sources are asked afresh on load (the Kalshi page), and an entry older than 6 h is forgotten",
          o["fresh"] == [] or o["fresh"] == ["raw:nq-dashboard"], o["fresh"])
    check("a. the owner can always ask again: after a tap / click the next ask goes to the real source (and a good answer clears the memory)",
          o["gesture"]["skipped"] == 0 and o["gesture"]["tried"] == 1 and o["gesture"]["status"] == 200 and o["gesture"]["dead"] is False, o["gesture"])
    check("a. anything but a GET goes through untouched", o["post"] == 404 or o["post"] == 200, o["post"])
    check("a. state() lists what was answered (the aborted ask left no entry); a change event per source",
          o["state"] == ["api:kalshi-feed", "api:nq-dashboard", "raw:kalshi-feed", "raw:nq-dashboard", "site:kalshi.json"] and o["events"] >= 4, o)


def first_page_script(html):
    """the first external or module script that is not quiet-net itself (inline theme bootstraps fetch nothing)"""
    idx = [m.start() for m in re.finditer(r"<script\b[^>]*(\bsrc=|type=\"module\")[^>]*>", html) if "quiet-net" not in html[m.start():m.end()]]
    return min(idx) if idx else len(html)


def pages_part():
    for rel in PAGES:
        html = open(os.path.join(WEB, *rel.split("/")), encoding="utf-8").read()
        i, j = html.find("quiet-net.js"), first_page_script(html)
        check(f"b. {rel} loads olympus/quiet-net.js before its own scripts", 0 <= i < j, f"quiet-net at {i}, first page script at {j}")


def handoff_part():
    """polish2 2026-11-19: datacity/jarvis/ carried a stale copy of the Jarvis shell with its own old status loop; it hands over to the one Jarvis"""
    html = open(os.path.join(WEB, "datacity", "jarvis", "index.html"), encoding="utf-8").read()
    code = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    check("b. datacity/jarvis/ hands over to the one Jarvis (../../jarvis/, which reads the shared PC feed): no copy of the status loop (no module, no fetch, no timer, no worker)",
          "location.replace('../../jarvis/' + location.search + location.hash)" in code and 'url=../../jarvis/' in code and 'href="../../jarvis/"' in code
          and not re.search(r"type=\"module\"|import |fetch\(|setInterval|setTimeout|serviceWorker|data\.js|live\.json|kalshi\.json", code) and len(html) < 3000, len(html))
    real = open(os.path.join(WEB, "jarvis", "index.html"), encoding="utf-8").read()
    check("b. the one Jarvis loads the shared PC feed reader (../pc_feed.js, id pcFeedJs) for its status", 'src="../pc_feed.js?v=' in real and 'id="pcFeedJs"' in real)


def builders_part():
    from tools import people_build as PB
    doc = PB.build(with_git=False)
    srcs = {s for p in doc["people"] + doc["villagers"] for s in p.get("sources", [])}
    check("c. people.json never asks for kalshi/jarvis.json or zenith/jarvis.json (those apps publish no status card)",
          "../kalshi/jarvis.json" not in srcs and "../zenith/jarvis.json" not in srcs and any(s.endswith("/jarvis.json") for s in srcs), sorted(x for x in srcs if "kalshi" in x or "zenith" in x))
    from tools.cronos import site as CS
    tmp = tempfile.mkdtemp(prefix="quiet-site-")
    try:
        for d in ("kalshicity", "datacity", "polis", "money"):
            os.makedirs(os.path.join(tmp, d))
        CS.apply(tmp, readers={}, log=lambda *a: None)
        st = json.load(open(os.path.join(tmp, "cronos", "status.json")))
        fw = json.load(open(os.path.join(tmp, "kalshicity", "forward.json")))
        sc = json.load(open(os.path.join(tmp, "kalshicity", "scan.json")))
        dc = json.load(open(os.path.join(tmp, "datacity", "discoveries.json")))
        check("c. no branch: cronos/status.json (tasks null), kalshicity forward / scan (kind none), datacity discoveries ([]) are honest empty files",
              st["tasks"] is None and st["published"] is False and fw["kind"] == "none" and sc["kind"] == "none" and dc["discoveries"] == [], [st, fw, sc, dc])
        from tools import polis_build as PO
        a = PO.sky_placeholder(tmp)
        sky = json.load(open(os.path.join(tmp, "polis", "sky.json")))
        check("c. polis/sky.json: an empty sky (t null = the page's clear sky), written once, never over a real one",
              a and sky["t"] is None and not PO.sky_placeholder(tmp), sky)
        from tools import money_publish as MP
        MP.publish(os.path.join(tmp, "nothing"), tmp, True)
        sf = json.load(open(os.path.join(tmp, "money", "sibyl_forward.json")))
        check("c. money/sibyl_forward.json: Sibyl's ledger, or an honest 'not started' file (kind none)", sf["kind"] == "none" and sf["published"] is False, sf)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("d. kalshi/icon.svg exists (the launcher draws every app's icon)", os.path.isfile(os.path.join(WEB, "kalshi", "icon.svg")))


def main():
    node_part()
    pages_part()
    handoff_part()
    builders_part()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
