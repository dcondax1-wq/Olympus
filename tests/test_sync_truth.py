"""One source of truth (night A, 2026-11-16, owner: "everything needs to be synced"): every page that shows the bots' drawdown left,
today's $, balance and data age gets the SAME numbers from the same inputs. Node only (no browser), fake fetch, no network.

The inputs disagree on purpose: home.json's old account row says $1,300 left, its board says $1,200, and the PC feed (ntfy, newer) says
$1,145; GitHub's live.json is old ($1,300). The answer everywhere must be the PC feed's $1,145 (truth.js's rule: the newest PC report).

  a. truth.js: withPcFeed + accountsOf -> Zlarior $1,145 / ATLAS $822, today +$212 / -$40, the PC report's time
  b. Jarvis data.js (the live board Jarvis's home, bots and system view read): the PC feed wins over an older GitHub live.json
  c. Jarvis data.js keeps GitHub's live.json when it is the newer one, and works with no PC feed at all
  d. Jarvis jdata.loadSources (brain / copilot / nudges / briefing): canonical rows -> accounts() = truth's numbers
  e. the Gate's and the hubs' light copies (gate.js / hub-status.js, used only when truth.js fails to load) read board first like truth.js
  f. BLITZ stays hidden in Jarvis's board while dashboard_view hides it (the home.json the site publishes is already scrubbed)

    python -X utf8 -m tests.test_sync_truth
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WP = os.path.join(ROOT, "tools", "web_public")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"   -> {str(info)[:400]}"))


NODE = r"""
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import path from 'node:path';
const WP = process.argv[2];
const require = createRequire(import.meta.url);
const NOW = 1794920400;                               // seconds
const store = new Map();
globalThis.localStorage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) };
const old = NOW - 3 * 3600, fresh = NOW - 240;
const ghLive = { kind: 'le-live', t: old, pc: { t: old }, board: { t: old, data_t: old, lit: { room: 1300, mll: 2000, today_pnl: 50, balance: 51300 }, atlas: { room: 900, mll: 1000, today_pnl: 0, balance: 24900 },
  trades: [{ acct: 'lit', entry_t: old - 600, usd: 50 }] } };
const lite = { kind: 'le-live', lite: true, t: fresh, pc: { t: fresh, running: true }, board: { t: fresh, data_t: fresh, lit: { room: 1145, mll: 2000, today_pnl: 212.5, balance: 51145 },
  atlas: { room: 822, mll: 1000, today_pnl: -40, balance: 24822 } }, reporter: { t: NOW - 60, server: true },
  // night-feedsA: the PC's account list (the lit card's own 50K row, the 25K #2 eval, a cloud paper twin) + Kalshi's paper K1 card
  accounts: [{ id: 'mffu50k_eval', name: 'MFFU 50K Eval', plan: 'Builder 50K', kind: 'eval', source: 'pc', badge: 'LIVE', eval: { balance: 51145, room: 1145, mll: 2000 } },
    { id: 'b25k_2', name: 'Zlarior Builder 25K #2', plan: 'Builder 25K', kind: 'eval', source: 'pc', badge: 'LIVE', conn: { t: fresh }, eval: { start_balance: 25000, balance: 25120, floor: 24120, room: 1000, mll: 1000, to_target: 1380, target_balance: 26500 }, pnl: { today: 120 } },
    { id: 'cloud_paper', name: 'Paper (cloud)', kind: 'paper', source: 'cloud', badge: 'PAPER', eval: { balance: 49900, room: 1900, mll: 2000 } }],
  kalshi_k1: { kind: 'kalshi_k1_pub', paper_only: true, updated: new Date((NOW - 300) * 1000).toISOString(), days: 1.5, sig: 3, set: 2, net: 1.25 } };
let ghAsked = 0;
const home = { built: new Date((old) * 1000).toISOString(), live: { pc: { t: old } }, board: { t: old, data_t: old, lit: { room: 1200, mll: 2000, today_pnl: 10, balance: 51200 }, atlas: { room: 900, mll: 1000, today_pnl: 0, balance: 24900 } },
  accounts: [{ id: 'mffu50k', name: 'Zlarior 50K', plan: 'MFFU Builder 50K', eval: { room: 1300, mll: 2000, balance: 51300 }, pnl: { today: 50 } }] };
const feed = { ntfy: 'https://ntfy.example', topic: 'olympus_status_test' };
let useFeed = true, liveBody = ghLive;
const fakeFetch = async (u) => {
  u = String(u);
  if (u.includes('live.json')) { ghAsked++; return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(liveBody)) }; }
  if (u.endsWith('status_feed.json')) return useFeed ? { ok: true, status: 200, json: async () => feed } : { ok: false, status: 404, json: async () => ({}) };
  if (u.startsWith('https://ntfy.example/')) return { ok: true, status: 200, text: async () => JSON.stringify({ event: 'message', time: NOW - 60, message: JSON.stringify(lite) }) + '\n' };
  if (u.endsWith('home.json')) return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(home)) };
  return { ok: false, status: 404, json: async () => ({}), text: async () => '' };
};
globalThis.fetch = fakeFetch;
globalThis.PC_FEED = require(path.join(WP, 'pc_feed.js'));
globalThis.window = { PC_FEED: globalThis.PC_FEED, addEventListener() {}, removeEventListener() {} }; globalThis.document = { createElement: () => ({}), head: { appendChild() {} } };
const T = await import(pathToFileURL(path.join(WP, 'olympus/truth.js')).href);
const out = {};
// a. truth
const h1 = await T.withPcFeed(JSON.parse(JSON.stringify(home)));
const A = T.accountsOf(h1), ag = T.agesOf(h1, NOW);
out.truth = { lit: A.lit.room, atlas: A.atlas.room, litToday: A.lit.today, atlasToday: A.atlas.today, litBal: A.lit.balance, pcT: ag.pc.t, extra: T.extraOf(h1).map((x) => [x.name, x.room, x.today, x.toTarget]) };
// b / c. Jarvis data.js
const D = await import(pathToFileURL(path.join(WP, 'jarvis/data.js')).href + '?a');
await D.refreshLive(); await D.pcFeedReady();
let v = D.liveView();
out.jarvisFeed = { lit: v.lit && v.lit.room, atlas: v.atlas && v.atlas.room, litToday: v.lit && v.lit.today_pnl, t: v.raw && v.raw.pc && v.raw.pc.t, trades: (v.trades || []).length, blitz: v.blitz, gh: ghAsked,
  extra: (v.extra || []).map((x) => [x.name, x.room, x.today_pnl, x.to_target]), kp: v.kpaper && v.kpaper.k1 ? [v.kpaper.k1.sig, v.kpaper.k1.net, v.kpaper.net] : null,
  sys: D.systemStatus({ now: new Date(NOW * 1000), live: v, kalshiState: 'waiting' }).rows.map((r) => [r.id, r.abbr || '', r.value]) };
const D2 = await import(pathToFileURL(path.join(WP, 'jarvis/data.js')).href + '?b');
liveBody = { ...ghLive, t: NOW, pc: { t: NOW }, board: { ...ghLive.board, t: NOW, data_t: NOW, lit: { ...ghLive.board.lit, room: 1100 } } };
ghAsked = 0; await D2.refreshLive(); await D2.pcFeedReady(); v = D2.liveView(); out.jarvisNewerGh = { lit: v.lit && v.lit.room, gh: ghAsked };
const D3 = await import(pathToFileURL(path.join(WP, 'jarvis/data.js')).href + '?c');
useFeed = false; liveBody = ghLive; await D3.refreshLive(); await D3.pcFeedReady(); v = D3.liveView(); out.jarvisNoFeed = { lit: v.lit && v.lit.room, err: v.err };
useFeed = true;
// d. jdata
const J = await import(pathToFileURL(path.join(WP, 'jarvis/jdata.js')).href);
const S = await J.loadSources({ fetch: fakeFetch, now: () => NOW * 1000 });
const acc = J.accounts(S);
out.jdata = acc.map((a) => ({ name: a.name, room: a.room, today: a.today, balance: a.balance }));
console.log(JSON.stringify(out));
"""


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sync_truth_") as tmp:
        p = os.path.join(tmp, "t.mjs")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(NODE)
        r = subprocess.run(["node", p, WP], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        check("node ran", False, (r.stdout[-400:], r.stderr[-800:]))
        return 1
    t = o["truth"]
    check("a. truth.js with the PC feed: Zlarior $1,145, ATLAS $822, today +212.5 / -40, the PC report's time",
          t["lit"] == 1145 and t["atlas"] == 822 and t["litToday"] == 212.5 and t["atlasToday"] == -40 and t["litBal"] == 51145, t)
    j = o["jarvisFeed"]
    check("b. Jarvis data.js: the newer PC feed wins over GitHub's old live.json (the same $1,145 / $822 / +212.5 as truth.js)",
          j["lit"] == t["lit"] and j["atlas"] == t["atlas"] and j["litToday"] == t["litToday"] and j["t"] == t["pcT"], j)
    # night-feedsA 2026-11-18: the PC feed is read FIRST; GitHub's live.json lives on the old, suspended account (every read was a 404 in
    # the console on the phone), so it is asked only when the feed has nothing (c, below). The trades come from the feed's own ext post.
    check("b. the PC feed answered: GitHub's old live.json (the suspended account) was not asked at all", j["gh"] == 0, j)
    check("c. the PC feed stays the word while it answers (GitHub not asked again)", o["jarvisNewerGh"]["lit"] == 1145 and o["jarvisNewerGh"]["gh"] == 0, o["jarvisNewerGh"])
    check("g. every real account: the PC's 25K #2 next to the bot cards in Jarvis (the 50K's own row and the cloud paper twin are not a 2nd account), same as truth.extraOf",
          j["extra"] == [["Zlarior 25K #2", 1000, 120, 1380]] and t["extra"] == [["Zlarior 25K #2", 1000, 120, 1380]], (j["extra"], t["extra"]))
    sysr = {r[0]: r for r in j["sys"]}
    check("g. the System view has its own line for it (Z2) and Kalshi says PAUSED with the paper tests, never 'not linked'",
          sysr.get("b25k_2", [None, ""])[1] == "Z2" and sysr.get("kalshi", [None, None, ""])[2] == "PAUSED", j["sys"])
    check("g. Kalshi's paper K1 card from the feed: 3 signals, +$1.25", j["kp"] == [3, 1.25, 1.25], j["kp"])
    check("c. no PC feed at all: GitHub's live.json as before, no error", o["jarvisNoFeed"]["lit"] == 1300 and not o["jarvisNoFeed"]["err"], o["jarvisNoFeed"])
    jd = {a["name"].split()[0]: a for a in o["jdata"]}
    check("d. Jarvis brain / copilot / nudges (jdata.accounts): the canonical rows = truth.js's numbers",
          jd.get("Zlarior", {}).get("room") == t["lit"] and jd.get("ATLAS", {}).get("room") == t["atlas"] and jd["Zlarior"]["today"] == t["litToday"]
          and jd["Zlarior"]["balance"] == t["litBal"] and not any(n.startswith("BLITZ") for n in jd), o["jdata"])
    gate = open(os.path.join(WP, "gate", "gate.js"), encoding="utf-8").read()
    hs = open(os.path.join(WP, "olympus", "hub-status.js"), encoding="utf-8").read()
    check("e. the Gate and the hubs read truth.js (accountsOf / agesOf) with the PC feed laid over home.json",
          "T.accountsOf(" in gate and "T.agesOf(" in gate and "T.accountsOf(" in hs and "overlayHome" in gate)
    check("f. BLITZ hidden in Jarvis's board", j["blitz"] is None, j)
    jdx = open(os.path.join(WP, "jarvis", "index.html"), encoding="utf-8").read()
    check("f. Jarvis loads the PC feed async (never holds the start on a slow network) and reads afresh when it lands",
          '<script src="../pc_feed.js?v=n5" id="pcFeedJs" async></script>' in jdx and "s.addEventListener('load', () => safe(() => D.refreshLive()))" in jdx)
    n, ok = len(RES), sum(RES)
    print(f"sync truth: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
