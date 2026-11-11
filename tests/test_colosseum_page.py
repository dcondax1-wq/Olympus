"""COLOSSEUM, the OLYMPUS arena where strategies fight (tools/colosseum_build.py + tools/web_public/colosseum/, AGORA look, 2026-11-11): two stored runs of the Archive duel over seven rounds
on their REAL stored numbers, money first; a seeded tournament of the top adopted runs; the league of the three bots; the hall of champions; the fallen. Read only.

  a. static: the extras builder's selftest and --check, the files, the kit lines, the AGORA look, read-only, the card, the manifest, the DEMO fixture, the 3D budget in the code, the new_apps.json row, the wiring section
  b. the maths in node (colosseumcore.js): the seven rounds against the raw research files, missing numbers = no contest (never guessed), the 2-4 trades rule, tie-breaks, seeding, the bracket, determinism, the league, links, junk input
  c. Chromium 390 x 844 and 375 x 667 (every browser run under `flock -w 2400 /tmp/olympus_browser.lock`): the real Archive with its shards, a full duel, the verdict, the tournament, deep links, the 3D arena inside its budget
     (or the flat arena), LITE + reduced motion, DEMO fallback, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_colosseum_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "colosseum", "Colosseum"
check = AK.check
BUILD = os.path.join(AK.ROOT, "tools", "colosseum_build.py")
D = os.path.join(AK.WEB, APP)
ARCH = os.path.join(AK.WEB, "archive")
RAW = os.path.join(AK.ROOT, "research", "runs")


def raw(rid, span="2026"):
    return json.load(open(os.path.join(RAW, rid + ".json"), encoding="utf-8"))["spans"][span]


def home_json():
    return json.dumps({"accounts": [
        {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "kind": "eval", "stats": {"n": 6, "net": 912.5, "pf": 2.4, "win_pct": 50.0, "max_dd": -410.0}, "pnl": {"today": 0, "week": 180.0, "traded": 912.5}},
        {"id": "acctb", "name": "ATLAS 25K", "kind": "eval", "stats": {"n": 4, "net": -120.0, "pf": 0.7, "win_pct": 25.0, "max_dd": -260.0}, "pnl": {"today": -40, "week": -120.0}}]})


def test_static():
    r = subprocess.run([sys.executable, "-I", BUILD, "--selftest"], capture_output=True, text=True, timeout=300)
    check("a. the extras builder's own selftest passes (tools/colosseum_build.py --selftest)", r.returncode == 0 and "ALL PASS" in r.stdout, r.stdout[-600:] + r.stderr[-300:])
    r2 = subprocess.run([sys.executable, "-I", BUILD, "--check"], capture_output=True, text=True, timeout=300)
    check("a. extra.json is EXACTLY what `python tools/colosseum_build.py` writes now (rebuild after research/runs changes)", r2.returncode == 0, r2.stdout[-300:] + r2.stderr[-200:])
    AK.static_kit(APP, NAME, reads=("../archive/index.json", "../home.json", "./extra.json"))
    ex = json.load(open(os.path.join(D, "extra.json"), encoding="utf-8"))
    live = raw("lit_live")
    size = os.path.getsize(os.path.join(D, "extra.json"))
    check(f"a. extra.json ({size / 1024:.0f} KB, < 200 KB) carries max drawdown, dec10 and pass_med exactly as stored: lit_live 2026 = {live['dd']}, {live['dec10']}, {live['pass_med']}",
          size < 200_000 and ex["cols"] == ["dd", "dec10", "pass_med"] and ex["runs"]["lit_live"][0] == [live["dd"], live["dec10"], live["pass_med"]] and len(ex["runs"]) > 2000, ex["runs"].get("lit_live"))
    html = AK.read(os.path.join(D, "index.html"))
    check("a. the page order: the duel (arena), the verdict, pick the fighters, the tournament, my bots, the hall of champions, the fallen",
          html.index('id="arena"') < html.index('id="verdict"') < html.index('id="results"') < html.index('id="bracket"') < html.index('id="leagueRows"') < html.index('id="hall"') < html.index('id="fallen"'))
    check("a. the 3D arena is its own module tag (a failed load can never stop the page) and the flat SVG arena exists", 'src="arena.js' in html and "COLOSSEUM_ARENA_FAIL" in html and 'id="flat"' in html and html.index('src="arena.js') < html.index('src="colosseum.js'))
    st = AK.read(os.path.join(D, "arena.js"))
    check("a. the arena is light by design: the render core + the shared shapes (helmet, shield), every repeated part instanced, a budget of 45 draws / 150,000 triangles, bloom <= .25, a dpr cap <= 1.5, no shadow maps, no data, no network, idle rules",
          "olympus/render.js" in st and "olympus/shapes3d.js" in st and "'shield'" in st and "'bust'" in st and st.count("InstancedMesh") >= 4 and "draws: 45, tris: 150000" in st and re.search(r"strength:\s*0\.(?:[0-2]\d?)\b", st)
          and "maxDpr: 1.5" in st and "O.hidden()" in st and "frameGap" in st and "RM" in st and "shadowMap" not in st and not re.search(r"fetch\(|XMLHttpRequest|innerHTML|WebSocket", st) and not AK.BANNED_LOOK.search(st))
    check("a. the champions are friendly toy-like people (a big round head with a face, a crested cap, mitten hands), not statues; the crowd is instanced round heads that cheer a round win; three baked meshes a champion",
          "big round head" in st and "a small smile" in st and "crowdFrame" in st and "cheer = {" in st and st.count("bake(") >= 4)
    check("a. every champion is a person: a Talk button that uses the shared kit when it is loaded (no tag for a file that does not exist yet: the wiring section names it), the page's own five-question card as the fallback", ('olympus/people.js?v=' not in html or os.path.isfile(os.path.join(AK.WEB, "olympus", "people.js"))) and "people.js" in AK.read(os.path.join(AK.ROOT, "docs", "NEW_APPS_WIRING.md")).split("Wiring COLOSSEUM")[1] and 'id="talk"' in html and 'id="asks"' in html
          and "OLYMPUS_PEOPLE" in AK.read(os.path.join(D, "colosseum.js")) and "kit.open(id" in AK.read(os.path.join(D, "colosseum.js")))
    check("a. the page tells the kit it is ready (OLYMPUS.ready()), so the loading veil lifts at once and not after its 12 s safety timer", AK.read(os.path.join(D, "colosseum.js")).count("O.ready()") >= 2)
    check("a. LITE is the flat SVG arena: on a low / off tier the 3D module steps aside", re.search(r"q0 === 'low' \|\| q0 === 'off'", st) is not None and "createFlat" in AK.read(os.path.join(D, "colosseum.js")))
    fx = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))
    check("a. the fixture: invented 'Example' runs, rejected ideas and three bot rows, with their own extras; never blank", all(x[1].startswith("Example") for x in fx["runs"]) and len(fx["runs"]) >= 12 and all(x["title"].startswith("Example") for x in fx["rejected"])
          and [b["key"] for b in fx["bots"]] == ["lit", "atlas", "blitz"] and "lit_live" in fx["extra"]["runs"])
    core = AK.read(os.path.join(D, "colosseumcore.js"))
    sc = AK.read(os.path.join(D, "colosseum.js")) + core
    check("a. read only: no order / key / signal words in the page code", not re.search(r"\b(trade signal|placeOrder|submitOrder|api[_-]?key|Authorization|\.post\()", re.sub(r"`[^`]*`|'[^'\n]*'|\"[^\"\n]*\"", "", re.sub(r"//[^\n]*", "", sc)), re.I))
    check("a. the honest words are in the code and on the page: no contest, nothing is guessed, not a promise, costs, sample size",
          all(w in core for w in ("No contest", "Nothing is guessed", "not a promise", "Costs are in", "Sample size", "is not proof")) and "nothing is guessed" in html and "not a promise" in html)
    check("a. money, not R: the page shows dollars everywhere and never an R figure on its own", not re.search(r"['`}]R\b|\dR\b", re.sub(r"//[^\n]*", "", sc)))
    na = json.load(open(os.path.join(AK.ROOT, "tools", "new_apps.json"), encoding="utf-8"))["apps"]
    row = next((a for a in na if a["id"] == APP), None)
    scenes = set(re.findall(r"^  SC\.(\w+) =", AK.read(os.path.join(AK.WEB, "olympus", "intro-app.js")), re.M))
    check("a. tools/new_apps.json has the Colosseum row: group trading, a hex accent, a glyph, a description under 80 characters, an ambient bed, an EXISTING intro scene, a transition",
          bool(row) and row["group"] == "trading" and re.match(r"^#[0-9a-f]{6}$", row["accent"]) and row["glyph"] and len(row["description"]) < 80 and row["ambient"] and row["flavour"][0] in scenes and len(row["flavour"]) == 3 and row["transition"]["kind"] and row["transition"]["ms"], row)
    wiring = AK.read(os.path.join(AK.ROOT, "docs", "NEW_APPS_WIRING.md"))
    check("a. the wiring section for the lead is in docs/NEW_APPS_WIRING.md and names the exact build line (python tools/colosseum_build.py)", re.search(r"^# .*COLOSSEUM", wiring, re.M) is not None and "python tools/colosseum_build.py" in wiring)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const fs = require('fs'), J = (p) => JSON.parse(fs.readFileSync(p, 'utf8')), o = {};
  const fx = J(process.argv[3]), real = J(process.argv[4]), extra = J(process.argv[5]), home = JSON.parse(process.argv[6]);
  o.words = [C.usd(758), C.usd(-12.4), C.usd(null), C.usdS(43820), C.usdS(-5), C.pf(4.1899), C.pf(null), C.dec(2.91, 1), C.pct(31.6), C.pct(null)];
  o.choose = [C.chooseData(real, fx).src, C.chooseData(null, fx).src, C.chooseData({ runs: [] }, fx).src, C.chooseData(null, null), C.chooseData('x', { runs: 3 })];
  const rv = C.chooseData(real, fx).v, n0 = rv.runs.length;
  const before = C.byId(rv, 'lit_live').m26.dd;
  o.extra = [before, C.addExtra(rv, extra) > 80, C.byId(rv, 'lit_live').m26.dd, C.addExtra(rv, null), C.addExtra(rv, { runs: 7 })];
  let added = 0; for (const s of rv.shards) { const sh = J(process.argv[4].replace('index.json', s)); added += C.addShard(rv, sh); added += C.addShard(rv, sh) * 1000; }
  C.addExtra(rv, extra);
  o.shards = [n0, added, rv.runs.length, rv.total, C.addShard(rv, null), C.addShard(rv, { runs: 'x' })];
  const fv = C.chooseData(null, fx).v, F = (id) => C.byId(fv, id), R = (id) => C.byId(rv, id);
  // ---- the real duel
  const a = R('lit_live'), b = R('atlas_base'), snap = JSON.stringify([a, b]), d = C.duel(a, b), d2 = C.duel(a, b);
  o.real = { period: d.period, n: d.rounds.length, keys: d.rounds.map((r) => r.key), w: d.rounds.map((r) => r.winner), score: d.score, winner: d.winner, by: d.decidedBy,
    a: { net: d.rounds[0].a.v, pm: d.rounds[1].a.v, pf: d.rounds[2].a.v, dd: d.rounds[3].a.v, tpw: d.rounds[4].a.raw, ev: d.rounds[5].a.v, both: d.rounds[6].a.v },
    b: { net: d.rounds[0].b.v, pm: d.rounds[1].b.v, pf: d.rounds[2].b.v, dd: d.rounds[3].b.v, tpw: d.rounds[4].b.raw, ev: d.rounds[5].b.v, both: d.rounds[6].b.v },
    vs0: d.rounds[0].vs, line0: d.rounds[0].line, why: d.why, cav: d.caveats, share: d.share, same: JSON.stringify(d) === JSON.stringify(d2), pure: JSON.stringify([a, b]) === snap };
  const m = C.duel(b, a);
  o.mirror = [m.winner, m.score, m.rounds.map((r) => r.winner)];
  // ---- missing numbers are no contest, never guessed
  const small = C.duel(F('lit_live'), F('demo_small'));
  o.small = [small.period, small.rounds.map((r) => r.winner), small.rounds[6].b.text, small.rounds[6].line, small.caveats.join(' | ')];
  const old = C.duel(F('lit_live'), F('demo_old_only'));
  o.old = [old.period, old.rounds.map((r) => r.winner), old.rounds[5].b.v, old.rounds[5].line, old.rounds[3].a.v];
  const only26 = F('demo_two_week'), nope = C.duel(only26, F('demo_old_only'));
  o.nope = [nope.period, nope.rounds.every((r) => r.winner === 'none'), nope.score, nope.winner, nope.why[0], nope.share];
  const bare = C.rowObj(['bare_run', 'Bare', 'risk', 1, 0, 'x', '', 1, [50, null, null, null, null, null, null], 0, '', '']);
  const bd = C.duel(bare, F('lit_live'));
  o.bare = [bd.rounds.map((r) => r.winner), bd.winner, bd.why[1], bd.rounds[0].a.text];
  const noExtra = C.chooseData(null, { ...fx, extra: undefined }).v, ne = C.duel(C.byId(noExtra, 'lit_live'), C.byId(noExtra, 'demo_monday'));
  o.noExtra = [ne.rounds[3].winner, ne.rounds[3].line, ne.rounds[5].winner, ne.rounds[5].a.text];
  // ---- the rules of single rounds
  const mk = (id, m26, mold, ex) => { const r = C.rowObj([id, id, 'risk', 1, 0, 'x', '', 3, m26, mold || 0, '', '']); if (ex && r.m26) Object.assign(r.m26, ex); return r; };
  const base = [100, 3.0, 2.0, 10000, 1000, 20, 5];
  const rd = (x, y, k) => C.duel(x, y).rounds[k];
  o.tpw = [rd(mk('in', base), mk('out', [100, 4.7, 2.0, 10000, 1000, 20, 5]), 4).winner, rd(mk('a', base), mk('b', [100, 2.1, 2.0, 10000, 1000, 20, 5]), 4).winner, rd(mk('lo', [100, 1.5, 2, 1, 1, 1, 1]), mk('hi', [100, 4.2, 2, 1, 1, 1, 1]), 4).winner,
    rd(mk('a', base), mk('b', [100, 2.1, 2.0, 10000, 1000, 20, 5]), 4).line];
  o.dd = [rd(mk('a', base, 0, { dd: -900 }), mk('b', base, 0, { dd: -2500 }), 3).winner, rd(mk('a', base, 0, { dd: -900 }), mk('b', base, 0, { dd: 900 }), 3).winner, rd(mk('a', base, 0, { dd: -900 }), mk('b', base), 3).winner];
  o.ev = [rd(mk('a', [100, 3, 2, 1, 1, 30, 10]), mk('b', [100, 3, 2, 1, 1, 25, 2]), 5).winner, rd(mk('a', base, 0, { dec10: 30 }), mk('b', base, 0, { dec10: 20 }), 5).winner, rd(mk('a', base, 0, { pass_med: 18 }), mk('b', base, 0, { pass_med: 12 }), 5).winner,
    rd(mk('a', [100, 3, 2, 1, 1, null, 10]), mk('b', base), 5).winner];
  const oldGood = [400, 2.5, 1.2, 5000, 100, 5, 9], oldBad = [400, 2.5, 0.9, -5000, -100, 5, 9];
  o.both = [rd(mk('h', base, oldGood), mk('n', [100, 3, 2, 90000, 9000, 20, 5], oldBad), 6).winner, rd(mk('h1', base, oldGood), mk('h2', base, [400, 2.5, 1.2, 9000, 180, 5, 9]), 6).winner, rd(mk('h', base, oldGood), mk('x', base), 6).winner,
    C.holds(mk('h', base, oldGood)), C.holds(mk('n', base, oldBad)), C.holds(mk('x', base))];
  const twinA = mk('twa', base), twinB = mk('twb', base), tw = C.duel(twinA, twinB);
  o.twin = [tw.winner, tw.decidedBy, tw.score, tw.why[0]];
  const m1 = mk('m1', [100, 3.0, 3.0, 9000, 900, 20, 5], 0, { dd: -500 }), m2 = mk('m2', [100, 3.0, 2.0, 12000, 1200, 20, 5], 0, { dd: -400 });
  const mny = C.duel(m1, m2);   // m1 wins PF; m2 wins net, pm, dd -> m2 by rounds. Then a level case:
  const l1 = mk('l1', [100, 3.0, 3.0, 9000, 1000, 20, 5], 0, { dd: -400 }), l2 = mk('l2', [100, 3.0, 2.0, 12000, 1000, 20, 5], 0, { dd: -400 }), lv = C.duel(l1, l2);
  o.money = [mny.winner, mny.decidedBy, lv.score, lv.winner, lv.decidedBy, lv.why[0]];
  const rej = C.rowObj(['rej_win', 'Rejected winner', 'stops', 1, 1, 'rejected', '', 1, [100, 3, 9, 99000, 9900, 50, 0], 0, '', '']);
  o.rej = C.duel(rej, mk('a', base)).caveats.some((x) => x.indexOf('REJECTED') >= 0);
  // ---- seeding and the bracket
  const pool = C.contenders(rv.runs, C.N_FLOOR);
  o.seed = [pool.length, pool.every((r) => r.verdict === 0 && r.m26 && r.m26.n >= C.N_FLOOR && r.m26.pm !== null), pool.every((r, i) => i === 0 || pool[i - 1].m26.pm >= r.m26.pm), new Set(pool.map((r) => [r.m26.n, r.m26.pf, r.m26.net, r.m26.pm].join('|'))).size === pool.length,
    C.contenders(rv.runs, 1).length >= pool.length, C.contenders(rv.runs, 100000).length, C.contenders(null).length, JSON.stringify(C.contenders(rv.runs.slice().reverse(), C.N_FLOOR).map((r) => r.id)) === JSON.stringify(pool.map((r) => r.id))];
  o.pairs = [C.bracketPairs(16), C.bracketPairs(8), C.bracketPairs(2)];
  const T = C.tournament(rv.runs), T2 = C.tournament(rv.runs.slice().reverse());
  o.tour = { ok: T.ok, size: T.size, rounds: T.rounds.map((r) => [r.name, r.matches.length]), seeds: T.field.map((f) => f.seed), first: T.rounds[0].matches.map((mt) => [mt.a.seed, mt.b.seed]), champ: T.champion.f.id, champSeed: T.champion.seed, share: T.share,
    same: T2.champion.f.id === T.champion.f.id && JSON.stringify(T2.rounds.map((r) => r.matches.map((mt) => [mt.a.f.id, mt.b.f.id, mt.score, mt.winner.f.id]))) === JSON.stringify(T.rounds.map((r) => r.matches.map((mt) => [mt.a.f.id, mt.b.f.id, mt.score, mt.winner.f.id]))),
    winnersAdvance: T.rounds.slice(1).every((r, i) => r.matches.every((mt, k) => mt.a === T.rounds[i].matches[2 * k].winner && mt.b === T.rounds[i].matches[2 * k + 1].winner)),
    scoresReal: T.rounds.every((r) => r.matches.every((mt) => { const dd = C.duel(mt.a.f, mt.b.f); return dd.score.a === mt.score[0] && dd.score.b === mt.score[1]; })),
    topPm: T.field[0].f.m26.pm, floor: T.floor };
  const Tf = C.tournament(fv.runs, { demo: true });
  o.tourFx = [Tf.ok, Tf.size, Tf.eligible, Tf.rounds.length, Tf.champion.f.id, Tf.share.indexOf('DEMO') > 0, Tf.field.some((f) => f.f.id === 'demo_small')];
  o.tourFew = [C.tournament(fv.runs.slice(0, 1)).ok, C.tournament([]).share, C.tournament(fv.runs.slice(0, 3)).size, C.tournament(fv.runs, { floor: 115 }).size];
  const levelT = C.tournament([mk('ta', [100, 3, 2, 10000, 1000, 20, 5]), mk('tb', [100, 3, 2, 10000, 990, 20, 5]), mk('tc', [100, 3, 3, 10000, 980, 20, 5]), mk('td', [100, 3, 3, 10000, 970, 20, 5])]);
  o.level = [levelT.size, levelT.rounds[0].matches.map((mt) => [mt.a.seed, mt.b.seed, mt.winner.seed, mt.decidedBy])];
  // ---- the bots
  const L = C.league(home, fx), Ld = C.league(null, fx), Lj = C.league({ accounts: 'x' }, null);
  o.league = [L.demo, L.rows.map((r) => [r.name, r.rank, r.net, r.pfv, r.n, r.dd, r.has, r.demo]), Ld.demo, Ld.rows.map((r) => [r.name, r.net, r.demo]), Lj.demo, Lj.rows.map((r) => [r.name, r.net, r.has])];
  const bdl = C.duel(L.rows[0], L.rows[1]);
  o.bots = [bdl.period, bdl.rounds.map((r) => r.winner), bdl.winner, bdl.caveats[0], C.duel(L.rows[0], L.rows[2]).period, C.duel(L.rows[0], R('lit_live')).period];
  // ---- hall, fallen, search, links, crest, card
  const H = C.hall(rv.runs, 12), Fl = C.fallen(rv.rejected, 10);
  o.hall = [H.length, H[0].id === pool[0].id || H[0].m26.pm >= pool[0].m26.pm, H.every((r) => r.verdict === 0), Fl.length, Fl.every((x) => x.title && x.reason), C.fallen(null).length, C.fallen(fv.rejected, 2).length];
  o.search = [C.search(rv.runs, 'lit_live', 5)[0].id, C.search(rv.runs, 'atlas', 8).length, C.search(rv.runs, 'zzzzqq').length, C.search(rv.runs, '', 3).length, C.search(rv.runs, 'atlas', 8)[0].verdict, C.search(fv.runs, 'stop').map((r) => r.id)];
  o.links = [C.parseHash('#a=lit_live&b=atlas_base'), C.parseHash('#b=x%20y&a=<script>'), C.parseHash(''), C.parseHash('#a=bot:lit&b=bot:atlas&c=1'), C.parseHash('#a=%E0%A4%A&b=ok'), C.makeHash('lit_live', 'atlas_base'), C.makeHash('a b', null), C.makeHash(null, 'x')];
  o.crest = [C.crest('LIT research'), C.crest('ATLAS'), C.crest('never seen'), C.crest('never seen') === C.crest('never seen'), C.crest(null), rv.runs.every((r) => /^#[0-9a-f]{6}$/.test(C.crest(r.family)))];
  o.card = C.card(rv, 1794355200); o.cardFx = C.card(fv, 1).status; o.cardNone = C.card(null, 0).kpis.map((k) => k.value);
  o.plate = [C.plate(a), C.plate(null), C.plate(L.rows[0]), C.plate(C.rowObj(['x', 'x', 'risk', 0, 0, '', '', 0, 0, 0, '', '']))];
  const evil = C.rowObj(['ok_id', '<img src=x onerror=1>`boom`', '<b>fam</b>', 1, 0, 'x', '', 1, [40, 2, 2, 1, 1, 1, 1], 0, 'BAD SLUG', '<i>n</i>']);
  o.junk = [C.rowObj(null), C.rowObj(['<x>']), C.rowObj([5]), evil.name, evil.family, evil.writeup, C.duel(null, a), JSON.stringify(C.duel(evil, a)).indexOf('<') < 0, C.normIndex({ runs: [[1], null, 'x'] }), C.rowObj(['n', 'n', 'f', 0, 0, '', '', 1, ['12', 'x', NaN, Infinity, 1, 1, 1], 0, '', '']).m26];
  o.rounds = [C.ROUNDS.map((r) => r.key), C.ROUNDS.length];
  // ---- every champion is a person
  const rj = R('atlas_gpt_a02p'), pd = C.duel(a, rj), keys = C.QUESTIONS.map((x) => x[0]);
  o.person = { ids: [C.personId(a), C.personId(L.rows[0]), C.personId(null)], q: C.QUESTIONS.map((x) => x[1]), a: keys.map((k) => C.answer(a, k, pd)), r: keys.map((k) => C.answer(rj, k, pd)), pre: C.answer(a, 'win', null),
    all: [a, rj, F('demo_small'), F('demo_old_only'), L.rows[0]].every((f) => keys.every((k) => { const t = C.answer(f, k, null); return t.indexOf('$') >= 0 && t.indexOf('n = ') >= 0 && /not a promise/i.test(t); })),
    small: C.answer(F('demo_small'), 'weak', null), old: C.answer(F('demo_old_only'), 'eval', null), bot: [C.answer(L.rows[0], 'rejected', null), C.answer(L.rows[0], 'trades', null), C.answer(L.rows[2], 'win', null)],
    junk: [C.answer(null, 'win'), C.answer(a, 'nonsense'), C.answer(bare, 'win', null)], say: C.afterLines(pd), sayDraw: C.afterLines(tw).map((x) => x.role), sayNone: C.afterLines(nope).map((x) => [x.role, x.line]), sayNull: C.afterLines(null),
    sayBots: C.afterLines(bdl).map((x) => [x.id, x.role, x.line]) };
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e); process.exit(1); });
"""


def test_maths():
    o = AK.node(APP, HARNESS, os.path.join(D, "fixture.json"), os.path.join(ARCH, "index.json"), os.path.join(D, "extra.json"), home_json())
    if o is None:
        check("b. maths skipped: no node", True)
        return
    if "_error" in o:
        check("b. the node harness runs", False, o["_error"])
        return
    idx = json.load(open(os.path.join(ARCH, "index.json"), encoding="utf-8"))
    check("b. money words: $758, -$12, n/a, +$43,820, -$5, PF 4.19, 2.9, 31.6%", o["words"] == ["$758", "-$12", "n/a", "+$43,820", "-$5", "4.19", "n/a", "2.9", "31.6%", "n/a"], o["words"])
    check("b. the real Archive wins; a missing, empty or broken one falls back to the labelled demo; both unusable = null", o["choose"] == ["file", "demo", "demo", None, None], o["choose"])
    live, atlas, live_old, atlas_old = raw("lit_live"), raw("atlas_base"), raw("lit_live", "2021-25"), raw("atlas_base", "2021-25")
    check("b. the extras: before extra.json a max drawdown is null (not guessed); after it lit_live's is the stored one; junk extras change nothing", o["extra"] == [None, True, live["dd"], 0, 0], o["extra"])
    check(f"b. the shards: {idx['counts']['runs']:,} runs after index.json + {len(idx['shards'])} shards, never added twice; a junk shard adds nothing",
          o["shards"][1] == idx["counts"]["runs"] - o["shards"][0] and o["shards"][2] == idx["counts"]["runs"] == o["shards"][3] and o["shards"][4:] == [0, 0], o["shards"])
    r = o["real"]
    check("b. the duel has seven rounds, money first: net $, $ a month, PF, max drawdown, trades a week, eval speed, holds in both periods", o["rounds"] == [["net", "pm", "pf", "dd", "tpw", "eval", "both"], 7] and r["n"] == 7 and r["keys"] == o["rounds"][0])
    check("b. lit_live v atlas_base uses EXACTLY the stored 2026 numbers of research/runs (net, $ a month, PF, max drawdown, trades a week, pass10 - fail10)",
          r["period"] == "26" and r["a"]["net"] == round(live["net"]) and r["a"]["pm"] == round(live["per_month"]) and r["a"]["pf"] == round(live["pf"], 2) and r["a"]["dd"] == abs(live["dd"]) and r["a"]["tpw"] == live["tpw"] and abs(r["a"]["ev"] - (live["p10"] - live["f10"])) < 0.05
          and r["b"]["net"] == round(atlas["net"]) and r["b"]["pm"] == round(atlas["per_month"]) and r["b"]["pf"] == round(atlas["pf"], 2) and r["b"]["dd"] == abs(atlas["dd"]) and r["b"]["tpw"] == atlas["tpw"], (r["a"], r["b"]))
    check("b. 'holds in both periods' compares each run's weaker period ($ a month of 2026 and 2021-25, as stored)", r["a"]["both"] == min(round(live["per_month"]), round(live_old["per_month"])) and r["b"]["both"] == min(round(atlas["per_month"]), round(atlas_old["per_month"])), (r["a"]["both"], r["b"]["both"]))
    check("b. the result: lit_live wins 6 rounds to 1 (ATLAS takes max drawdown), decided by rounds; the two numbers read '+$43,820 vs +$10,914'",
          r["w"] == ["a", "a", "a", "b", "a", "a", "a"] and r["score"] == {"a": 6, "b": 1, "draw": 0, "none": 0} and r["winner"] == "a" and r["by"] == "rounds" and r["vs0"] == "+$43,820 vs +$10,914" and "takes it by $32,906" in r["line0"], (r["w"], r["vs0"], r["line0"]))
    check("b. why it won: three plain sentences (the score, the money with $ a month, where each was better)", len(r["why"]) == 3 and r["why"][0] == "lit_live beat atlas_base by 6 rounds to 1." and "+$43,820 ($4,467 a month) against +$10,914 ($1,113 a month)" in r["why"][1] and "atlas_base was better on max drawdown" in r["why"][2], r["why"])
    cav = " | ".join(r["cav"])
    check("b. the honest caveats: backtest not a promise, costs in, sample size n of both, the LIT 2021-25 note, 'not proof'", "not a promise" in cav and "Costs are in" in cav and "n = 120 trades" in cav and "n = 79 trades" in cav and "LIT is tuned and judged on 2026" in cav and "not proof" in cav, r["cav"])
    check("b. a shareable line: who beat whom, the score, the period, net against net, 'not a promise'", r["share"] == "COLOSSEUM: lit_live beat atlas_base 6-1 (2026 backtest, after costs). Net +$43,820 vs +$10,914. History, not a promise.", r["share"])
    check("b. deterministic and pure: the same duel twice is byte-identical and the fighters are not changed; swapped sides mirror the result", r["same"] and r["pure"] and o["mirror"] == ["b", {"a": 1, "b": 6, "draw": 0, "none": 0}, ["b", "b", "b", "a", "b", "b", "b"]], o["mirror"])
    s = o["small"]
    check("b. MISSING: a run with no 2021-25 result makes 'holds in both periods' no contest (said in words and in the caveats); under 30 trades is flagged",
          s[0] == "26" and s[1][6] == "none" and s[2] == "not stored" and s[3].startswith("No contest: demo_small has no 2021-25 result stored") and "no contest because a number is not stored (holds in both periods)" in s[4] and "Under 30 trades (demo_small)" in s[4] and "DEMO numbers" in s[4], s)
    check("b. MISSING: a run with only 2021-25 fights on 2021-25; its eval rates are not stored so eval speed is no contest (the number stays null)", o["old"][0] == "old" and o["old"][1][5] == "none" and o["old"][2] is None and "has no eval pass and fail rates stored" in o["old"][3] and o["old"][1][6] == "none" and o["old"][4] == 19000, o["old"])
    check("b. MISSING: no period in common = seven no contests, no winner, said plainly", o["nope"][0] is None and o["nope"][1] and o["nope"][2] == {"a": 0, "b": 0, "draw": 0, "none": 7} and o["nope"][3] == "draw" and o["nope"][4].startswith("No winner") and "no contest" in o["nope"][5], o["nope"])
    check("b. MISSING: a run with only a trade count loses nothing by a guess: every round is no contest and the money sentence says so", set(o["bare"][0]) == {"none"} and o["bare"][1] == "draw" and "could not be compared" in o["bare"][2] and o["bare"][3] == "not stored", o["bare"])
    check("b. MISSING: without extra.json the max drawdown round is no contest, and eval speed still runs on pass10 / fail10 alone", o["noExtra"][0] == "none" and "has no max drawdown" in o["noExtra"][1] and o["noExtra"][2] in ("a", "b") and "decided" not in o["noExtra"][3], o["noExtra"])
    check("b. trades a week: inside 2-4 beats outside; both inside is level; outside, the closer one wins", o["tpw"][:3] == ["a", "draw", "b"] and "inside the 2 to 4 a week rule" in o["tpw"][3], o["tpw"])
    check("b. max drawdown: the smaller drop wins (the sign does not matter); a missing one is no contest", o["dd"] == ["a", "draw", "none"], o["dd"])
    check("b. eval speed: pass10 minus fail10 first, then decided-in-10, then the faster median pass; a missing rate is no contest", o["ev"] == ["b", "a", "b", "none"], o["ev"])
    check("b. holds in both: a run that makes money in both periods beats a richer one that loses in 2021-25; two that hold are split by the weaker period; one period only = no contest", o["both"] == ["a", "b", "none", True, False, False], o["both"])
    check("b. twins draw 0-0 with five level rounds; rounds level but money apart = money decides ($ a month, then net)", o["twin"][0] == "draw" and o["twin"][1] == "none" and o["twin"][2]["draw"] >= 5 and o["twin"][3].startswith("A draw")
          and o["money"][0] == "b" and o["money"][1] == "rounds" and o["money"][2]["a"] == o["money"][2]["b"] == 1 and o["money"][3] == "b" and o["money"][4] == "money" and "wins on money" in o["money"][5], (o["twin"], o["money"]))
    check("b. a rejected run that wins carries a warning", o["rej"] is True)
    sd = o["seed"]
    check(f"b. seeding: {sd[0]} adopted runs with n >= 30 and $ a month, best first, runs with identical numbers once, the same order whatever the input order; an impossible floor = none; junk = none", sd[0] >= 16 and all(sd[1:5]) and sd[5] == 0 and sd[6] == 0 and sd[7], sd)
    check("b. the bracket: 1 v 16, 8 v 9, 4 v 13, 5 v 12, 2 v 15, 7 v 10, 3 v 14, 6 v 11 (seeds 1 and 2 can only meet in the final)",
          o["pairs"][0] == [[1, 16], [8, 9], [4, 13], [5, 12], [2, 15], [7, 10], [3, 14], [6, 11]] and o["pairs"][1] == [[1, 8], [4, 5], [2, 7], [3, 6]] and o["pairs"][2] == [[1, 2]], o["pairs"])
    t = o["tour"]
    check(f"b. the tournament: top 16 adopted runs, 8 + 4 + 2 + 1 matches, winners advance, every score is that pair's real duel, champion {t['champ']} (seed {t['champSeed']}), the same whatever the input order",
          t["ok"] and t["size"] == 16 and t["rounds"] == [["Round of 16", 8], ["Quarter-finals", 4], ["Semi-finals", 2], ["Final", 1]] and t["seeds"] == list(range(1, 17)) and t["first"] == o["pairs"][0] and t["same"] and t["winnersAdvance"] and t["scoresReal"] and t["floor"] == 30, t)
    check("b. the tournament's shareable text: champion, seed, final score, net $, $ a month, PF, n, 'not a promise'", t["champ"] in t["share"] and "a month" in t["share"] and "n = " in t["share"] and "not a promise" in t["share"] and "net" in t["share"], t["share"])
    check("b. the demo tournament: 8 of 8 runs (the tiny sample of 14 trades is left out), 3 rounds, labelled DEMO; fewer than two runs = no tournament; three runs = a final of the top two; a floor of 115 trades cuts the field",
          o["tourFx"] == [True, 8, 8, 3, o["tourFx"][4], True, False] and o["tourFew"][0] is False and "No tournament" in o["tourFew"][1] and o["tourFew"][2] == 2 and o["tourFew"][3] == 4, (o["tourFx"], o["tourFew"]))
    check("b. a match level on rounds is decided by money, said in its note", o["level"][0] == 4 and all(m[2] == min(m[0], m[1]) and m[3] == "money" for m in o["level"][1]), o["level"])
    lg = o["league"]
    check("b. my bots from home.json: LIT +$912.50 first, ATLAS -$120 second, BLITZ has no row (no numbers, never invented), not demo; no home.json = the fixture's rows labelled DEMO; junk = three empty rows",
          lg[0] is False and lg[1][0][:6] == ["LIT", 1, 912.5, 2.4, 6, -410.0] and lg[1][1][:3] == ["ATLAS", 2, -120.0] and lg[1][2][0] == "BLITZ" and lg[1][2][2] is None and lg[1][2][6] is False
          and lg[2] is True and lg[3] == [["LIT", 1260.0, True], ["ATLAS", 280.0, True], ["BLITZ", -140.0, True]] and lg[4] is True and all(x[1] is None and x[2] is False for x in lg[5]), lg)
    b = o["bots"]
    check("b. a bot duel runs on live numbers: net, PF and max drawdown are fought; $ a month, trades a week, eval speed and both periods are no contest; a bot with no trades or a bot against a backtest has no shared period",
          b[0] == "live" and b[1] == ["a", "none", "a", "b", "none", "none", "none"] and b[2] == "a" and "Live account numbers so far" in b[3] and b[4] is None and b[5] is None, b)
    check("b. the hall: 12 adopted statues, best $ a month first; the fallen: 10 rejected ideas, each with its reason; junk = none", o["hall"] == [12, True, True, 10, True, 0, 2], o["hall"])
    check("b. search: an exact id comes first, adopted before rejected, nothing for nonsense, the fixture finds its stop runs", o["search"][0] == "lit_live" and o["search"][1] == 8 and o["search"][2] == 0 and o["search"][3] == 3 and o["search"][4] == 0 and "demo_wide_stop" in o["search"][5], o["search"])
    check("b. deep links: #a=<runId>&b=<runId> both ways; unsafe ids are dropped", o["links"] == [{"a": "lit_live", "b": "atlas_base"}, {"a": "", "b": ""}, {"a": "", "b": ""}, {"a": "bot:lit", "b": "bot:atlas"}, {"a": "", "b": "ok"}, "#a=lit_live&b=atlas_base", "", "#b=x"], o["links"])
    check("b. the crest colour is the family's: gold for LIT research, aegean for ATLAS, a stable warm pick for an unknown family, every real family has one", o["crest"][0] == "#c8a24a" and o["crest"][1] == "#4b7a99" and re.match(r"^#[0-9a-f]{6}$", o["crest"][2]) and o["crest"][3] and re.match(r"^#[0-9a-f]{6}$", o["crest"][4]) and o["crest"][5], o["crest"])
    check("b. the Jarvis card follows the contract and matches the committed jarvis.json; the demo card says so", not AK.jarvis_problems(o["card"]) and o["card"] == json.loads(AK.read(os.path.join(D, "jarvis.json"))) and o["cardFx"] == {"level": "off", "label": "Demo data"} and o["cardNone"] == ["0", "0", "n/a"], o["card"])
    check("b. a fighter's plate is money first: '2026: +$43,820, $4,467 a month, PF 4.19, n = 120'", o["plate"] == ["2026: +$43,820, $4,467 a month, PF 4.19, n = 120", "Empty", "live so far: +$913, PF 2.40, n = 6", "No result stored"], o["plate"])
    ps = o["person"]
    check("b. PEOPLE: a champion's id is champion:<run-id>, a bot's is bot:<key> (docs/PERSONA_API.md); five questions", ps["ids"] == ["champion:lit_live", "bot:lit", ""] and ps["q"] == ["How did you win?", "What is your weakness?", "How many trades?", "Would you pass an eval?", "Why were you rejected?"], (ps["ids"], ps["q"]))
    check("b. PEOPLE: every answer of every kind of fighter (adopted, rejected, tiny sample, old-only, live bot) carries $ and n and 'not a promise'", ps["all"] is True)
    check("b. PEOPLE: the winner answers from the stored numbers: 'I beat atlas_gpt_a02p 7 to 0', its worst drop -$2,196, 120 trades at 2.9 a week (and 511 in 2021-25), 31.6% pass / 1% fail in 10 sessions, 'I am an adopted run'; before a duel it says it has not fought",
          "I beat atlas_gpt_a02p 7 to 0" in ps["a"][0] and "-$2,196" in ps["a"][1] and "120 trades in 2026, 2.9 a week (inside the 2 to 4 rule). And 511 trades in 2021-25" in ps["a"][2] and "31.6% of MFFU evals passed within 10 sessions and 1% failed" in ps["a"][3]
          and "nobody knows" in ps["a"][3] and "I am an adopted run" in ps["a"][4] and all("(2026: +$43,820, n = 120 trades. Backtest, not a promise.)" in x for x in ps["a"]) and ps["pre"].startswith("I have not finished a duel yet"), ps["a"])
    check("b. PEOPLE: the rejected loser is honest: 'lit_live beat me 7 to 0', outside the 2 to 4 rule, more evals failed than passed, PF 0.88, 'I was rejected' with the Archive's note",
          "lit_live beat me 7 to 0" in ps["r"][0] and "outside the 2 to 4 rule" in ps["r"][1] and "more of my evals failed (12.1%) than passed (1.9%)" in ps["r"][1] and "PF 0.88" in ps["r"][1] and ps["r"][4].startswith("I was rejected. The Archive's note:") and "-$5,099, n = 193" in ps["r"][4], ps["r"])
    check("b. PEOPLE: a tiny sample says so (14 trades, too few; no 2021-25 result); missing eval rates are 'not stored, I will not guess'; a bot is 'a live bot, not a run'; a bot with no trades has nothing to show; junk gives no text",
          "only 14 trades" in ps["small"] and "no 2021-25 result" in ps["small"] and "I will not guess" in ps["old"] and "live bot" in ps["bot"][0] and "6 trades in live so far" in ps["bot"][1] and "A short live record, not a promise" in ps["bot"][1]
          and ps["bot"][2].startswith("No result is stored for me") and ps["junk"][:2] == ["", ""] and "no dollars stored, n = 50 trades" in ps["junk"][2], (ps["small"], ps["old"], ps["bot"], ps["junk"]))
    sy = ps["say"]
    check("b. PEOPLE: after a duel the winner and the loser each say one honest line with $ and n ('I won 7 to 0, but one duel proves little' / 'I lost 0 to 7 ... My record: -$5,099 over n = 193 trades: a backtest, not a promise'); a draw, no shared period, bots and no duel are covered",
          [x["role"] for x in sy] == ["winner", "loser"] and sy[0]["id"] == "champion:lit_live" and sy[0]["line"] == "I won 7 to 0, but one duel proves little. +$43,820 over n = 120 trades: a backtest, not a promise."
          and sy[1]["line"] == "I lost 0 to 7 and was better on no round. My record: -$5,099 over n = 193 trades: a backtest, not a promise." and ps["sayDraw"] == ["draw", "draw"] and all(x[0] == "none" and "no period in common" in x[1] for x in ps["sayNone"]) and ps["sayNull"] == []
          and ps["sayBots"][0][0] == "bot:lit" and ps["sayBots"][0][1] == "winner" and "a short live record, not a promise" in ps["sayBots"][0][2] and "ATLAS was better on max drawdown" in ps["sayBots"][0][2], (sy, ps["sayBots"]))
    j = o["junk"]
    check("b. junk never breaks it and no markup survives: bad rows are dropped, angle brackets and backticks are stripped, a bad write-up slug is emptied, NaN / Infinity / text numbers become null",
          j[0] is None and j[1] is None and j[2] is None and "<" not in j[3] and "`" not in j[3] and j[4] == "bfam/b" and j[5] == "" and j[6] is None and j[7] is True and j[8] is None and j[9] is None, j)


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve(overrides={"/home.json": home_json()})
    idx = json.load(open(os.path.join(ARCH, "index.json"), encoding="utf-8"))
    try:
        with AK.browser() as br:
            # ---- 1. the real Archive at 390 x 844, the 3D arena asked for (?q=high)
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?q=high", hook="COLOSSEUM")
            p.wait_for_function("window.COLOSSEUM.shards()", timeout=90000)
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, a: document.querySelector('#nameA').textContent, b: document.querySelector('#nameB').textContent, pill: document.querySelector('#periodPill').textContent,
              runs: window.COLOSSEUM.S.v.runs.length, mode: window.COLOSSEUM.mode, score: document.querySelector('#score').textContent, pips: document.querySelectorAll('#pips li').length, verdictHidden: document.querySelector('#verdict').hidden,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, results: document.querySelectorAll('#results .pickrun').length, crestA: document.querySelector('#crestA').style.background,
              dd: window.COLOSSEUM.S.a.m26.dd, league: [...document.querySelectorAll('#leagueRows tr')].map((r) => r.textContent), botPill: document.querySelector('#botPill').textContent })""")
            check(f"c. the real Archive: no DEMO chip, all {idx['counts']['runs']:,} runs loaded, lit_live (champion) against atlas_base on 2026, 0 - 0, seven round pips, the verdict still hidden, six suggested fighters",
                  not d["demo"] and d["runs"] == idx["counts"]["runs"] and d["a"] == "lit_live" and d["b"] == "atlas_base" and d["pill"] == "2026 backtest" and d["score"] == "0 - 0" and d["pips"] == 7 and d["verdictHidden"] and d["results"] == 6 and d["dd"] == raw("lit_live")["dd"], d)
            check("c. AGORA look: serif title, warm dark body, the crest of fighter A is the LIT gold", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)" and "200, 162, 74" in d["crestA"], (d["font"], d["bg"], d["crestA"]))
            check("c. it read only the site's own files: the Archive index, its shards, extra.json and home.json; nothing off the origin", any("archive/index.json" in u for u in seen) and sum(1 for u in seen if "archive/runs-" in u) == len(idx["shards"]) and any("colosseum/extra.json" in u for u in seen) and any(u.endswith("/home.json") for u in seen) and not off, off[:3])
            check("c. my bots from the live home.json: LIT first with +$913, ATLAS second with -$120, BLITZ 'no trades yet'; labelled live", d["botPill"] == "Live accounts" and "1. LIT+$913" in d["league"][0] and "2. ATLAS-$120" in d["league"][1] and "BLITZ" in d["league"][2] and "no trades yet" in d["league"][2], d["league"])
            check("c. the arena is 3D or the flat drawing, never nothing: the canvas XOR the svg is visible", d["mode"] in ("3d", "flat") and p.evaluate("() => document.querySelector('#arena').hidden !== document.querySelector('#flat').hasAttribute('hidden')"), d["mode"])
            if d["mode"] == "3d":
                st = p.evaluate("() => ({ s: window.COLOSSEUM.stage.stats(), q: window.COLOSSEUM.stage.quality(), size: [document.querySelector('#arena').clientWidth, document.querySelector('#arena').clientHeight], f: window.COLOSSEUM.stage.frames(), cols: window.COLOSSEUM.stage.colours() })")
                check(f"c. 3D on phone-high: {st['s']['draws']} draw calls (<= 45) and {st['s']['tris']:,} triangles (<= 150,000) with {st['s']['crowd']} spectators on {st['s']['tiers']} tiers; the canvas has a real size; the champions wear their family colours (LIT gold, ATLAS aegean)",
                      st["s"]["draws"] <= 45 and 20000 < st["s"]["tris"] <= 150000 and st["s"]["crowd"] > 300 and st["s"]["tiers"] == 7 and st["size"][0] > 300 and st["size"][1] > 200 and st["f"] > 0 and st["cols"] == ["#c8a24a", "#4b7a99"], st)
            else:
                check("c. 3D: no WebGL tier here, so the flat SVG arena is shown (the page still works)", p.evaluate("() => document.querySelectorAll('#flat .champ-a, #flat .champ-b').length === 2"))
            AK.shot(p, "colosseum-start")
            p.locator("#next").click()
            p.wait_for_function("window.COLOSSEUM.S.shown === 1 && !window.COLOSSEUM.S.busy", timeout=20000)
            r1 = p.evaluate("() => [document.querySelector('#roundNo').textContent, document.querySelector('#numA').textContent, document.querySelector('#numB').textContent, document.querySelector('#roundLine').textContent, document.querySelector('#score').textContent, document.querySelector('.num.a').className, document.querySelector('#pips li').className]")
            check("c. one round: 'Round 1 of 7: Net profit', the two numbers big (+$43,820 and +$10,914), the award in plain words, 1 - 0, the winner's number in gold", r1[0] == "Round 1 of 7: Net profit" and r1[1] == "+$43,820" and r1[2] == "+$10,914" and "lit_live takes it by $32,906" in r1[3] and r1[4] == "1 - 0" and "win" in r1[5] and r1[6].startswith("a"), r1)
            AK.shot(p, "colosseum-round1")
            p.locator("#fight").click()
            p.wait_for_function("window.COLOSSEUM.S.done === true", timeout=60000)
            p.wait_for_timeout(700)
            v = p.evaluate("""() => ({ shown: !document.querySelector('#verdict').hidden, head: document.querySelector('#verHead').textContent, pill: document.querySelector('#verPill').textContent, why: [...document.querySelectorAll('#why li')].map((l) => l.textContent),
              cav: [...document.querySelectorAll('#caveats li')].map((l) => l.textContent), rows: [...document.querySelectorAll('#roundRows tr')].map((r) => r.textContent), share: document.querySelector('#shareText').textContent, score: document.querySelector('#score').textContent,
              openA: document.querySelector('#openA').getAttribute('href'), openB: document.querySelector('#openB').textContent, fight: document.querySelector('#fight').textContent, pose: window.COLOSSEUM.stage.pose ? window.COLOSSEUM.stage.pose() : 'flat', hash: location.hash, status: document.querySelector('#status').textContent })""")
            check("c. 'Play the rest' runs the other six rounds by itself and ends in the verdict: lit_live wins 6 - 1, three plain sentences, seven rows, the caveats (backtest, costs, n = 120 and n = 79, not proof)",
                  v["shown"] and v["head"] == "lit_live wins" and v["pill"] == "6 - 1" and v["score"] == "6 - 1" and len(v["why"]) == 3 and "+$43,820 ($4,467 a month)" in v["why"][1] and len(v["rows"]) == 7 and "Max drawdown-$2,196-$938B" in v["rows"][3]
                  and len(v["cav"]) >= 5 and any("not a promise" in c for c in v["cav"]) and any("n = 120 trades" in c and "n = 79 trades" in c for c in v["cav"]) and any("Costs are in" in c for c in v["cav"]), v)
            check("c. the result can be shared and opened: the share line, 'Open ... in the Archive' links for both, the link holds the two fighters (#a=lit_live&b=atlas_base), the champion's pose in 3D",
                  v["share"].startswith("COLOSSEUM: lit_live beat atlas_base 6-1") and v["openA"] == "../archive/?q=lit_live" and "atlas_base" in v["openB"] and v["hash"] == "#a=lit_live&b=atlas_base" and v["fight"] == "Fight again" and v["pose"] in ("verdict", "flat"), v)
            sy = p.evaluate("() => [...document.querySelectorAll('#says .say')].map((q) => [q.className, q.dataset.person, q.textContent])")
            check("c. after the duel both champions say one honest line: the winner 'I won 6 to 1, but atlas_base was better on max drawdown' and the loser 'I lost 1 to 6 ...', each with $ and n and 'not a promise'",
                  len(sy) == 2 and "winner" in sy[0][0] and sy[0][1] == "champion:lit_live" and "I won 6 to 1, but atlas_base was better on max drawdown" in sy[0][2] and "+$43,820 over n = 120 trades" in sy[0][2] and "loser" in sy[1][0] and "I lost 1 to 6" in sy[1][2] and "+$10,914 over n = 79 trades: a backtest, not a promise" in sy[1][2], sy)
            AK.shot(p, "colosseum-verdict")
            p.locator("#plateB").click()
            p.wait_for_timeout(150)
            pc = p.evaluate("() => [!document.querySelector('#person').hidden, document.querySelector('#pName').textContent, document.querySelector('#pPlate').textContent, document.querySelector('#talk').textContent, document.querySelector('#askBox').hidden, document.querySelectorAll('#face *').length > 5, document.querySelector('#plateB').getAttribute('aria-expanded')]")
            check("c. a champion is a person: a tap on the name plate opens its card (a face, the name, the money line, 'Talk to atlas_base')", pc[0] and "ATLAS" in pc[1] and "+$10,914" in pc[2] and "n = 79" in pc[2] and pc[3] == "Talk to atlas_base" and pc[4] is True and pc[5] and pc[6] == "true", pc)
            p.locator("#talk").click()
            p.wait_for_timeout(150)
            qa = p.evaluate("() => [[...document.querySelectorAll('#asks button')].map((b) => b.textContent), document.querySelector('#answer').textContent]")
            p.locator("#asks [data-ask=weak]").click()
            p.wait_for_timeout(100)
            qa.append(p.evaluate("() => document.querySelector('#answer').textContent"))
            p.locator("#asks [data-ask=eval]").click()
            p.wait_for_timeout(100)
            qa.append(p.evaluate("() => document.querySelector('#answer').textContent"))
            check("c. Talk without the shared kit: the page's own card with five tappable questions; the loser answers honestly ('lit_live beat me 6 to 1'), its weakness (1.9 trades a week, outside the rule), its eval rates; every answer ends with $, n and 'not a promise'",
                  len(qa[0]) == 5 and qa[0][0] == "How did you win?" and "lit_live beat me 6 to 1" in qa[1] and "1.9 times a week, outside the 2 to 4 rule" in qa[2] and "5.8% of MFFU evals passed" in qa[3] and all("(2026: +$10,914, n = 79 trades. Backtest, not a promise.)" in x for x in qa[1:]), qa)
            AK.shot(p, "colosseum-talk")
            # search a rejected run that lives in a shard, send it in as B
            p.fill("#q", "atlas_gpt_a02p")
            p.wait_for_timeout(300)
            p.locator("#results .pickrun[data-id=atlas_gpt_a02p]").click()
            p.wait_for_timeout(300)
            s2 = p.evaluate("() => [document.querySelector('#nameB').textContent, document.querySelector('#score').textContent, document.querySelector('#verdict').hidden, location.hash, document.querySelector('#sPlateB').textContent, document.querySelector('#slotA').getAttribute('aria-pressed')]")
            check("c. search finds a rejected run from a shard (atlas_gpt_a02p); a tap sends it in as B: a fresh duel at 0 - 0, the old verdict gone, the link updated, the next pick goes to A", s2[0] == "atlas_gpt_a02p" and s2[1] == "0 - 0" and s2[2] is True and s2[3] == "#a=lit_live&b=atlas_gpt_a02p" and "Rejected" in s2[4] and "-$5,099" in s2[4] and s2[5] == "true", s2)
            p.evaluate("() => window.COLOSSEUM.finish()")
            p.wait_for_timeout(300)
            s3 = p.evaluate("() => [document.querySelector('#verHead').textContent, document.querySelector('#roundRows').textContent]")
            check("c. 'To the verdict' skips the show: the verdict of the new pair is there at once", s3[0] == "lit_live wins" and "Net profit+$43,820-$5,099A" in s3[1], s3)
            # champion vs challenger, then the bots
            p.locator("#modes [data-mode=champ]").click()
            p.wait_for_timeout(200)
            c1 = p.evaluate("() => [document.querySelector('#nameA').textContent, document.querySelector('#slotA').disabled, document.querySelector('#swap').hidden, document.querySelector('#modeNote').textContent]")
            check("c. champion vs challenger: the live LIT run holds slot A (locked), any run can challenge", c1[0] == "lit_live" and c1[1] is True and c1[2] is True and "the live LIT run" in c1[3], c1)
            p.locator("#modes [data-mode=bots]").click()
            p.wait_for_timeout(200)
            p.evaluate("() => window.COLOSSEUM.finish()")
            p.wait_for_timeout(300)
            b1 = p.evaluate("() => [document.querySelector('#nameA').textContent, document.querySelector('#nameB').textContent, document.querySelector('#periodPill').textContent, document.querySelector('#roundRows').textContent, document.querySelector('#verHead').textContent, document.querySelector('#finder').hidden, document.querySelectorAll('#botPick button').length, document.querySelector('#openA').hidden]")
            check("c. my three bots duel on their live numbers: LIT against ATLAS, 'Live so far', $ a month is 'not stored / No contest' (never guessed), LIT wins, no Archive link for a bot", b1[0] == "LIT" and b1[1] == "ATLAS" and b1[2] == "Live so far" and "Dollars a monthnot storednot storedNo contest" in b1[3] and b1[4] == "LIT wins" and b1[5] is True and b1[6] == 3 and b1[7] is True, b1)
            # the tournament
            p.locator("#tGo").click()
            p.wait_for_function("window.COLOSSEUM.S.tDone === true", timeout=30000)
            t = p.evaluate("""() => ({ rounds: [...document.querySelectorAll('#bracket .tround')].map((r) => [r.querySelector('h3').textContent, r.querySelectorAll('.match').length]), champ: document.querySelector('#champName').textContent, nums: document.querySelector('#champNums').textContent,
              laurel: document.querySelectorAll('#laurel ellipse').length, share: document.querySelector('#tShareText').textContent, core: window.COLOSSEUM.S.tour.champion.f.id, note: document.querySelector('#tNote').textContent, pill: document.querySelector('#tPill').textContent })""")
            check("c. the tournament plays itself: Round of 16 (8), Quarter-finals (4), Semi-finals (2), Final (1); the champion is crowned with a laurel, with net $, $ a month, PF and n; a shareable line",
                  t["rounds"] == [["Round of 16", 8], ["Quarter-finals", 4], ["Semi-finals", 2], ["Final", 1]] and t["champ"].startswith(t["core"]) and "a month" in t["nums"] and "n = " in t["nums"] and "not a promise" in t["nums"] and t["laurel"] >= 10
                  and t["share"].startswith("COLOSSEUM tournament: " + t["core"]) and t["pill"] == "Top 16" and "seeded by dollars a month" in t["note"], t)
            p.locator("#tFinal").click()
            p.wait_for_function("window.COLOSSEUM.S.done === true", timeout=60000)
            f = p.evaluate("() => [document.querySelector('#nameA').textContent, window.COLOSSEUM.S.tour.champion.f.id, window.COLOSSEUM.S.tour.runnerUp.f.id, document.querySelector('#nameB').textContent, document.querySelector('#verHead').textContent, window.COLOSSEUM.S.mode]")
            check("c. 'Watch the final' sends the two finalists into the arena and the champion wins there too", f[0] == f[1] and f[3] == f[2] and f[4] == f[1] + " wins" and f[5] == "any", f)
            hl = p.evaluate("() => ({ hall: document.querySelectorAll('#hall .arch').length, busts: document.querySelectorAll('#hall .arch svg').length, first: document.querySelector('#hall .arch').textContent, fallen: document.querySelectorAll('#fallen li').length, tag: document.querySelector('#fallen li small').textContent, pill: document.querySelector('#fallPill').textContent })")
            check(f"c. the hall of champions: 12 statues with $ a month, net $, PF and n; the fallen: 10 of the {len(idx['rejected'])} rejected ideas, each marked \"Don't redo this\" with its reason", hl["hall"] == 12 and hl["busts"] == 12 and "a month" in hl["first"] and "n = " in hl["first"] and hl["fallen"] == 10 and hl["tag"] == "Don't redo this" and str(len(idx["rejected"])) in hl["pill"], hl)
            p.locator("#hall .arch button[data-slot=b]").nth(2).click()
            p.wait_for_timeout(250)
            h2 = p.evaluate("() => [document.querySelector('#nameB').textContent, document.querySelectorAll('#hall .arch b')[2].textContent]")
            check("c. a statue steps into the arena: 'As B' on the third statue makes it fighter B", h2[0] == h2[1], h2)
            tp = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (chips, slots, runs, buttons, links, summaries)", not tp, tp[:6])
            check("c. no sideways scroll; Jarvis's corner is free; no console error", AK.no_sideways(p) and not AK.corner(p) and not errs, (errs[:3], AK.corner(p)))
            AK.shot(p, "colosseum-full")
            ctx.close()

            # ---- 2. a deep link on the real data: a run that only exists in a shard
            ctx, p, errs, seen, off = AK.page(br, origin)
            ctx.add_init_script("window.__opened = []; window.OLYMPUS_PEOPLE = { open: (id, opts) => { window.__opened.push([id, !!(opts && opts.anchor)]); } };")
            AK.open_app(p, origin, APP, "?flat=1#a=atlas_gpt_a02p&b=lit_live", hook="COLOSSEUM")
            p.wait_for_function("window.COLOSSEUM.shards()", timeout=90000)
            p.wait_for_timeout(300)
            dl = p.evaluate("() => [document.querySelector('#nameA').textContent, document.querySelector('#nameB').textContent, window.COLOSSEUM.mode, !document.querySelector('#flat').hasAttribute('hidden'), document.querySelectorAll('#flat .champ-a, #flat .champ-b').length]")
            check("c. a deep link (#a=atlas_gpt_a02p&b=lit_live) opens that duel once the shard with the rejected run has loaded; ?flat=1 draws the flat arena with both champions", dl == ["atlas_gpt_a02p", "lit_live", "flat", True, 2] and not errs, (dl, errs[:2]))
            p.locator("#plateA").click()
            p.locator("#talk").click()
            p.wait_for_timeout(150)
            kt = p.evaluate("() => [window.__opened, document.querySelector('#askBox').hidden]")
            check("c. Talk with the shared kit loaded (a stub): the page calls OLYMPUS_PEOPLE.open('champion:atlas_gpt_a02p', { anchor }) and keeps its own card closed", kt == [[["champion:atlas_gpt_a02p", True]], True], kt)
            ctx.close()

            # ---- 3. 375 x 667, LITE, reduced motion, DEMO
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low#a=demo_two_week&b=demo_small", hook="COLOSSEUM")
            l0 = p.evaluate("() => [!document.querySelector('#demo').hidden, !document.querySelector('#lite').hidden, window.COLOSSEUM.mode, document.querySelector('#nameA').textContent, document.querySelector('#nameB').textContent, document.querySelector('#status').textContent, document.querySelector('#botPill').textContent]")
            check("c. 375 x 667, LITE, DEMO: the DEMO and LITE chips, the flat SVG arena, the deep link's two demo fighters, the bots labelled DEMO", l0[0] and l0[1] and l0[2] == "flat" and l0[3] == "demo_two_week" and l0[4] == "demo_small" and l0[5].startswith("DEMO") and l0[6] == "DEMO", l0)
            p.locator("#fight").click()
            p.wait_for_timeout(400)
            l1 = p.evaluate("() => [window.COLOSSEUM.S.done, document.querySelector('#verHead').textContent, [...document.querySelectorAll('#caveats li')].map((l) => l.textContent).join(' | '), document.querySelector('#roundRows').textContent, document.querySelector('#flat').getAttribute('class')]")
            check("c. reduced motion: the duel goes straight to the verdict (no animation); the caveats say DEMO, under 30 trades, and which round was no contest; the winner wears the laurel in the flat arena",
                  l1[0] is True and l1[1].endswith("wins") and "DEMO numbers" in l1[2] and "Under 30 trades (demo_small)" in l1[2] and "no contest because a number is not stored" in l1[2] and "Holds in both periodsnot storednot storedNo contest" in l1[3] and "crown-" in (l1[4] or ""), l1)
            p.locator("#modes [data-mode=bots]").click()
            p.locator("#plateA").click()
            p.locator("#talk").click()
            p.wait_for_timeout(150)
            lb = p.evaluate("() => [document.querySelector('#pName').textContent, document.querySelector('#answer').textContent, document.querySelectorAll('#flat .skin').length]")
            check("c. a bot is a person too (bot:lit): its fallback answer is from the demo account row with $, n and 'not a promise'; the flat champions have round heads with skin tones", lb[0].startswith("LIT") and "$" in lb[1] and "n = 14 trades" in lb[1] and "not a promise" in lb[1] and lb[2] >= 8, lb)
            p.locator("#tGo").click()
            p.wait_for_timeout(300)
            l2 = p.evaluate("() => [document.querySelectorAll('#bracket .tround').length, document.querySelector('#tShareText').textContent, document.querySelector('#tPill').textContent]")
            check("c. the demo tournament: top 8, three rounds at once on reduced motion, the share line says DEMO", l2[0] == 3 and "(DEMO numbers)" in l2[1] and l2[2] == "Top 8", l2)
            tp = AK.taps(p)
            check("c. 375 x 667: no sideways scroll, every tap >= 44 px, Jarvis's corner free, no console error, nothing but its fixture read", AK.no_sideways(p) and not tp and not AK.corner(p) and not errs and not any("index.json" in u or "home.json" in u or "extra.json" in u for u in seen), (tp[:4], errs[:2]))
            AK.shot(p, "colosseum-lite-375")
            ctx.close()

            # ---- 4. a broken Archive falls back to the demo, never blank
            srv2, origin2 = AK.serve({"/archive/index.json": "{broken", "/home.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?flat=1", hook="COLOSSEUM")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#nameA').textContent, document.querySelectorAll('#hall .arch').length, document.querySelector('#botPill').textContent, document.querySelectorAll('#results .pickrun').length]")
            check("c. a broken index.json and no home.json: the labelled demo fights instead (lit_live example, a hall, demo bots), never blank", r[0] is True and r[1] == "lit_live" and r[2] >= 6 and r[3] == "DEMO" and r[4] >= 4 and not errs, (r, errs[:2]))
            ctx.close()
            srv2.shutdown()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
