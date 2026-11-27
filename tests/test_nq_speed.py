"""NQ SPEED data layer (night-nq-speed 2026-11-27): tools/web_public/nq/nqfeed.js, ONE shared fetch of the PC's signed status post.

  a. static: classic script, no innerHTML / eval, no outside URL (the feed's own ntfy base only), storage access wrapped, never
     writes a post that did not come through PC_FEED.fetchLatest (the signature check), the NQCORE_API.md spec exists
  b. node (fake PC_FEED / fetch / clock / storage): one flight for N callers, fresh-for-60 s, the cache at start (sync + on()),
     network down -> the last VERIFIED post with its own time (never a made-up one, null with no cache), a future-dated post refused,
     an older network post never replaces a newer kept one, the cached feed settings skip the status_feed.json round trip and a
     changed key re-reads, the 60 s "anything new?" probe (empty -> no full read), backoff 2 s -> 4 s, a custom feed goes to the original,
     a peer tab's post (BroadcastChannel message) is taken, the lease makes a 2nd tab wait for the 1st instead of fetching
Run: python -X utf8 -m tests.test_nq_speed
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = os.path.join(ROOT, "tools", "web_public", "nq", "nqfeed.js")
SPEC = os.path.join(ROOT, "research", "handoff", "2026-11-27", "speed", "NQCORE_API.md")
FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
    if not ok:
        FAILS.append(name)


NODE = r"""
const F = require(process.argv[1]);
const out = {};
const NOW0 = 1795750000000;
function env(o) {
  const st = o.mem || {}, timers = [];
  const storage = { getItem: (k) => (k in st ? st[k] : null), setItem: (k, v) => { st[k] = String(v); }, removeItem: (k) => { delete st[k]; } };
  const clock = { t: o.t || NOW0 };
  const calls = { latest: 0, feeds: [], net: [] };
  const pcFeed = { fetchLatest: async (opts) => { calls.latest++; calls.feeds.push(opts && opts.feed ? opts.feed.vk : null); if (o.delay) await new Promise((r) => setTimeout(r, o.delay)); return o.post ? (typeof o.post === 'function' ? o.post(opts) : JSON.parse(JSON.stringify(o.post))) : null; } };
  const fetch = async (u) => { calls.net.push(u); if (/status_feed/.test(u)) { if (o.cfgDelay) await new Promise((r) => setTimeout(r, o.cfgDelay)); return { ok: true, json: async () => o.cfg || { ntfy: 'https://ntfy.sh', topic: 'tp', vk: 'K1' } }; }
    return { ok: true, text: async () => o.probe || '' }; };
  const L = F.create({ storage, now: () => clock.t, pcFeed, fetch, feedUrl: '../status_feed.json', noChannel: true, setTimeout: (f, ms) => { if (ms !== 15000) timers.push(ms); }, visible: () => true });
  return { L, st, clock, calls, timers, storage };
}
const post = (t, x) => ({ v: 1, kind: 'le-live', lite: true, t, pc: { running: true }, board: { lit: { room: 1500 + (x || 0) } } });
(async () => {
  // 1. one flight for three callers, stored
  let e = env({ post: post(1795749900), delay: 5 });
  const r = await Promise.all([e.L.latest(), e.L.latest(), e.L.latest()]);
  out.one_flight = { latest: e.calls.latest, same: r.every((x) => x && x.t === 1795749900), stored: !!e.st['olympus.nqfeed.v1'] };
  // 2. fresh for 60 s, then re-read
  await e.L.latest(); out.fresh60 = e.calls.latest;
  e.clock.t += 61000; await e.L.latest(); out.after60 = e.calls.latest;
  // 3. a new page with that storage: the post at once (sync + on), src cache; settings cached -> fetchLatest called with them
  const mem = e.st;
  let e2 = env({ mem: { ...mem }, post: post(1795749990), cfgDelay: 30 });
  const sync = e2.L.cached(); let seen = []; e2.L.on((j, m) => seen.push([j.t, m.src]));
  const p2 = e2.L.latest({ force: true });
  await new Promise((r) => setTimeout(r, 5));
  out.cache_start = { sync_t: sync && sync.t, first: seen[0], early_call: e2.calls.latest };   // fetchLatest started before status_feed.json answered
  await p2; out.cache_then_net = seen.map((x) => x.join(':'));
  // 4. network down with a cache: the cached post (own t), never a new one; without a cache: null
  let e3 = env({ mem: { ...mem }, post: null });
  const r3 = await e3.L.latest({ force: true });
  out.down_cached = { t: r3 && r3.t, fails: e3.L.info().fails, timers: e3.timers.slice() };
  e3.L._state.retryAt = 0;   // the 2 s retry ran (fake timers never fire)
  await e3.L.latest({ force: true }); out.backoff = e3.timers.slice();
  let e4 = env({ post: null }); out.down_nocache = await e4.L.latest();
  // 5. a post dated 20 min in the future is refused; an older post never replaces a newer kept one
  let e5 = env({ post: post(Math.floor(NOW0 / 1000) + 1200) }); out.future = await e5.L.latest();
  let e6 = env({ mem: { ...mem }, post: post(1795740000) }); const r6 = await e6.L.latest({ force: true }); out.older = r6 && r6.t;
  // 6. a changed key in status_feed.json: read again with the new settings
  let e7 = env({ mem: { ...mem }, post: post(1795749995), cfg: { ntfy: 'https://ntfy.sh', topic: 'tp', vk: 'K2' } });
  await e7.L.latest({ force: true }); out.rotate = e7.calls.feeds;
  // 7. the probe: empty -> no full read; a message -> full read; > 5 min since the last full -> full read
  let e8 = env({ post: post(1795749900) }); await e8.L.latest(); const n8 = e8.calls.latest;
  e8.clock.t += 60000; await e8.L.probe(); out.probe_empty = { full: e8.calls.latest - n8, url: e8.calls.net.filter((u) => /since=\d+/.test(u)).length };
  let e9 = env({ post: post(1795749900), probe: '{"id":"x","time":1795750050,"event":"message","message":"{}"}' }); await e9.L.latest(); const n9 = e9.calls.latest;
  e9.clock.t += 60000; await e9.L.probe(); out.probe_msg = e9.calls.latest - n9;
  e9.clock.t += 6 * 60000; await e9.L.probe(); out.probe_5min = e9.calls.latest - n9;
  // 8. a custom feed goes straight to the original
  let e10 = env({ post: post(1795749900) }); await e10.L.fetchLatestShared({ feed: { topic: 'other', vk: 'KX' } }); await e10.L.fetchLatestShared({ feed: { topic: 'other', vk: 'KX' } });
  out.custom = e10.calls.latest;
  // 9. ages
  out.age = [F.age(NOW0 / 1000 - 30, NOW0 / 1000), F.age(NOW0 / 1000 - 47 * 60, NOW0 / 1000), F.age(NOW0 / 1000 - 40 * 3600, NOW0 / 1000), F.age(null)].map((a) => a.text + '|' + a.level);
  // 10. the lease: another tab is fetching -> without a channel this tab fetches itself (no wait forever); storage broken -> still works
  let e11 = env({ post: post(1795749900) }); e11.st['olympus.nqfeed.lease'] = JSON.stringify({ id: 'other', until: NOW0 + 5000 });
  await e11.L.latest(); out.lease_nochan = e11.calls.latest;
  const bad = F.create({ storage: { getItem: () => { throw new Error('x'); }, setItem: () => { throw new Error('x'); }, removeItem: () => {} }, now: () => NOW0, noChannel: true, setTimeout: () => {},
    pcFeed: { fetchLatest: async () => post(1795749900) }, fetch: async () => ({ ok: true, json: async () => ({ topic: 'tp' }) }) });
  const rb = await bad.latest(); out.storage_broken = rb && rb.t;
  console.log(JSON.stringify(out));
})().catch((e) => { console.log(JSON.stringify({ error: String(e && e.stack || e) })); });
"""


def main() -> int:
    src = open(FEED, encoding="utf-8").read()
    # ---------------------------------------------------------------- a. static
    check("a1 classic script + CommonJS, window.NQ_FEED", "root.NQ_FEED = API" in src and "module.exports = API" in src and not re.search(r"^\s*(import|export)\s", src, re.M))
    check("a2 no innerHTML / eval / document.write", not re.search(r"innerHTML|\beval\(|document\.write|new Function", src))
    urls = set(re.findall(r"https?://[^\s'\"`)]+", src))
    check("a3 no outside URL but the feed's ntfy base", urls <= {"https://ntfy.sh"}, str(urls))
    check("a4 every storage access wrapped (getItem / setItem only inside makeStore's try)",
          src.count("getItem(") == 1 and src.count("setItem(") == 1 and "try { const s = ls && ls.getItem" in src)
    check("a5 posts come only from PC_FEED.fetchLatest (signature-checked) or a peer's copy of one",
          "orig.call(F, { feed, fetch: pollFetch })" in src and "const pollFetch = (E.fetch || !early) ? E.fetch" in src and "parseLatest" not in src and "JSON.parse(t" not in src)
    check("a6 future-dated post refused (10 min skew, as pc_feed SKEW_S)", "+ 600" in src)
    check("a7 the spec NQCORE_API.md exists", os.path.exists(SPEC))
    # ---------------------------------------------------------------- b. node
    r = subprocess.run(["node", "-e", NODE, FEED], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
    except Exception:
        o = {"error": r.stdout + r.stderr}
    if "error" in o:
        check("b0 node runs", False, o["error"][:600])
        return 1
    check("b1 three callers, ONE fetch, kept in localStorage", o["one_flight"] == {"latest": 1, "same": True, "stored": True}, str(o["one_flight"]))
    check("b2 fresh for 60 s (no 2nd fetch), re-read after", o["fresh60"] == 1 and o["after60"] == 2, f"{o['fresh60']} {o['after60']}")
    cs = o["cache_start"]
    check("b3 a new page: the kept post at once (sync + on() src cache), the poll starts before status_feed.json answers",
          cs["sync_t"] == 1795749900 and cs["first"] == [1795749900, "cache"] and cs["early_call"] == 1, str(cs))
    check("b4 then the network's newer post reaches the widget", o["cache_then_net"] == ["1795749900:cache", "1795749990:net"], str(o["cache_then_net"]))
    check("b5 network down: the last verified post with its own time, one retry queued at 2 s", o["down_cached"]["t"] == 1795749900 and o["down_cached"]["fails"] == 1 and o["down_cached"]["timers"] == [2000], str(o["down_cached"]))
    check("b6 backoff 2 s -> 4 s", o["backoff"] == [2000, 4000], str(o["backoff"]))
    check("b7 network down, nothing kept: null (never a made-up post)", o["down_nocache"] is None, str(o["down_nocache"]))
    check("b8 a post dated 20 min ahead refused", o["future"] is None, str(o["future"]))
    check("b9 an older network post never replaces the newer kept one", o["older"] == 1795749900, str(o["older"]))
    check("b10 a changed key: read again with the new settings", o["rotate"] == ["K1", "K2"], str(o["rotate"]))
    check("b11 probe: empty answer -> no full read (1 small poll)", o["probe_empty"] == {"full": 0, "url": 1}, str(o["probe_empty"]))
    check("b12 probe: a new message -> full read; > 5 min since the last -> full read anyway", o["probe_msg"] == 1 and o["probe_5min"] == 2, f"{o['probe_msg']} {o['probe_5min']}")
    check("b13 a custom feed goes to the original fetchLatest each time", o["custom"] == 2, str(o["custom"]))
    check("b14 ages: just now ok / 47 min warn / 40 h bad / none off",
          o["age"] == ["just now|ok", "47 min ago|warn", "1 day 16 h ago|bad", "no report yet|off"], str(o["age"]))
    check("b15 another tab's lease without a channel: this tab fetches (never waits forever)", o["lease_nochan"] == 1, str(o["lease_nochan"]))
    check("b16 storage blocked (private mode): still loads", o["storage_broken"] == 1795749900, str(o["storage_broken"]))
    print(f"\n{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
