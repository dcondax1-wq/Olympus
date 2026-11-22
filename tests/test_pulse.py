"""OLYMPUS PULSE (day-arenas 2026-11-20): the shared prop-trader cards (tools/web_public/olympus/pulse.js + pulse.css) in the main apps.

  a. static   the kit files; read-only (no POST, no innerHTML, no outside address); every mount names known parts and carries the same
              placeholder parts the script draws (so the height is reserved: CLS 0); each mounted app loads pulse.css + pulse.js once;
              the 'pu-' class prefix is the kit's own (the polis-life kit owns 'pl-')
  b. node     model(): today across the real accounts, the tightest drawdown, the nearest eval, the funded payout (needs $X / ready $Y),
              fees from the price list vs the phone's Ledger, the bots' waiting words, streak / last trade / setup + weekday win rates
              (the replay is labelled when real trades are too few); junk in -> no throw
  c. Chromium 390 x 844, every mounted app on a fixed home.json (no PC feed): the cards fill, no page error, layout shift 0 while they fill,
              no sideways scroll, the "Open" links are >= 44 px tall... (light theme too: the text is not the dark theme's ink)
    python -X utf8 -m tests.test_pulse            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

def check(name, ok, *info):
    AK.check(name, ok, info[0] if len(info) == 1 else (info or ""))


WEB = AK.WEB
KIT = os.path.join(WEB, "olympus", "pulse.js")
PARTS = {"strip", "hero", "accounts", "bots", "stats", "money"}
APPS = ["aegis", "demeter", "hera", "ledger", "business", "journal", "helios", "compass", "kronos", "pnyx", "chrysos", "mercury", "oikos", "planner"]


def mounts(app):
    html = AK.read(os.path.join(WEB, app, "index.html"))
    return html, re.findall(r'<section class="pulse" data-pulse="([^"]+)" data-pulse-app="([^"]+)"[^>]*>(.*?)</section>', html)


def test_static():
    js, css = AK.read(KIT), AK.read(os.path.join(WEB, "olympus", "pulse.css"))
    check("a. pulse.js reads only this site (../home.json, ../trading/trades.json, ../ledger/rules.json) and sends nothing",
          not re.search(r"innerHTML|insertAdjacentHTML|XMLHttpRequest|method:\s*'POST'|https?://", js) and all(n in js for n in ("home.json", "trading/trades.json", "ledger/rules.json")))
    check("a. account numbers go through olympus/truth.js (the one place for drawdown / balance / age)", "from './truth.js'" in js and "T.accountsOf(" in js and "T.withPcFeed(" in js)
    check("a. pulse.css uses the AGORA tokens (every look, dark and light) and has no animation", "var(--ag-text" in css and "@keyframes" not in css and "animation" not in css)
    check("a. the kit's own class prefix: 'pu-' (polis-life owns 'pl-')", ".pl-" not in css and "'pl-" not in js and ".pu-part" in css)
    for app in APPS:
        html, ms = mounts(app)
        ok = bool(ms) and html.count('href="../olympus/pulse.css') == 1 and html.count('src="../olympus/pulse.js') == 1
        for parts, who, inner in ms:
            names = [p.split(":")[0] for p in parts.split(",")]
            holders = re.findall(r'<div class="pu-part pu-([a-z]+)"></div>', inner)
            age = bool(re.search(r"(^|,)(accounts|bots)", parts))
            ok = ok and who == app and set(names) <= PARTS and holders == names and (('pu-age' in inner) == age)
        check(f"a. {app}: {len(ms)} mount(s), each part reserved by a placeholder of the same kind; pulse.css + pulse.js once", ok, [m[0] for m in ms])


HARNESS = r"""
import(process.argv[2]).then((P) => {
  const o = {}, now = 1795170000;
  const home = { built: now - 300, board: { data_t: now - 120,
      lit: { balance: 49193, floor: 48168, room: 1025, mll: 2000, to_target: 3807, target_balance: 53000, today_pnl: -120, status: 'open', window: { open: true, text: 'entry window open until 15:30 ET' }, waiting: '' },
      atlas: { balance: 24887, floor: 24000, room: 887, mll: 1000, target_balance: 26500, today_pnl: 45, status: 'funded', position: { side: 'SHORT', qty: 1 }, members: [] } },
    accounts: [{ id: 'b25k_2', name: 'Zlarior 25K #2', plan: 'MFFU Builder 25K', kind: 'eval', eval: { balance: 25000, floor: 24000, room: 1000, mll: 1000, target_balance: 26500, start_balance: 25000 } }] };
  const trades = { trades: [
    { src: 'backtest', bot: 'LIT', m: '', day: '2026-01-05', usd: 500, t: 1 }, { src: 'backtest', bot: 'LIT', m: '', day: '2026-01-06', usd: -200, t: 2 },
    { src: 'backtest', bot: 'LIT', m: '', day: '2026-01-07', usd: 300, t: 3 }, { src: 'backtest', bot: 'LIT', m: '', day: '2026-01-08', usd: 300, t: 4 }, { src: 'backtest', bot: 'LIT', m: '', day: '2026-01-09', usd: -100, t: 5 },
    { src: 'backtest', bot: 'ATLAS', m: 'EMA', day: '2026-01-05', usd: -50, t: 6 }, { src: 'backtest', bot: 'ATLAS', m: 'EMA', day: '2026-01-12', usd: -50, t: 7 }, { src: 'backtest', bot: 'ATLAS', m: 'EMA', day: '2026-01-13', usd: 80, t: 8 },
    { src: 'backtest', bot: 'ATLAS', m: 'EMA', day: '2026-01-14', usd: -50, t: 9 }, { src: 'backtest', bot: 'ATLAS', m: 'EMA', day: '2026-01-15', usd: -50, t: 10 },
    { src: 'paper', bot: 'LIT', day: '2026-10-19', usd: -11.4, t: 100 }, { src: 'live', bot: 'LIT', day: '2026-10-28', hm: '03:43', side: 'SHORT', k: 'STOP', usd: -437, t: 200 }] };
  const rules = { plans: { builder_50k: { price_owner: 91.8, payout: { buffer: 2100, min: 500, max: 2000, split: 0.8 } }, builder_25k: { price_owner: 63, payout: { buffer: 1100, min: 250, max: 1000, split: 0.8 } } },
    accounts: { lit50k: { plan: 'builder_50k', price: 91.8 }, atlas25k: { plan: 'builder_25k', price: 43 } } };
  const m = P.model({ home, trades, rules, ledger: null }, now);
  o.n = m.accts.length; o.today = m.today; o.tight = m.tight && m.tight.name; o.pass = m.pass && [m.pass.name, m.pass.toTarget];
  o.pay = m.pay && [m.pay.a.name, m.pay.p.ready, m.pay.p.need, m.pay.p.line, m.pay.p.goal.need, m.pay.p.goal.at, m.pay.p.goal.toYou];
  o.fees = m.fees; o.bots = m.bots.map((b) => [b.key, b.busy, b.open, b.text]);
  o.stats = { streak: m.stats.streak, last: m.stats.last && m.stats.last.usd, basis: m.stats.basis, best: m.stats.bySetup[0] && [m.stats.bySetup[0].key, m.stats.bySetup[0].win], dow: m.stats.byDow.map((d) => d.key + ':' + d.n) };
  o.heroes = ['room', 'today', 'pass', 'payout', 'net', 'last'].map((k) => P.hero(m, k));
  // the phone's Ledger wins over the price list
  o.ledger = P.feesOf(JSON.stringify({ entries: [{ kind: 'fee', amount: 91.8 }, { kind: 'reset', amount: 50 }, { kind: 'payout_in', amount: 800 }, { kind: 'expense', amount: 30 }] }), rules, m.accts);
  // a funded account above its buffer: ready, capped at the plan's max, 80% to you
  o.ready = P.payoutOf({ size: '25K', start: 25000, balance: 27500 }, rules);
  let junk = 0;
  for (const x of [null, 5, 'x', [], { home: 'x' }, { home: { board: 7, accounts: 'no' } }, { trades: { trades: [null, 1, { usd: 'a' }] } }]) { try { const mm = P.model(x, now); ['room','today','pass','payout','net','last'].forEach((k) => P.hero(mm, k)); } catch (e) { junk++; } }
  o.junk = junk;
  console.log(JSON.stringify(o));
});
"""


def test_core():
    out = subprocess.run(["node", "--input-type=module", "-e", HARNESS, "x", "file://" + KIT], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(out.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        check("b. node ran pulse.js", False, (out.stdout + out.stderr)[-600:]); return
    check("b. three real accounts (Zlarior, ATLAS, Zlarior 25K #2); today = their sum (-120 + 45 + 0 = -75)", o["n"] == 3 and abs(o["today"] + 75) < 0.01, o["n"], o["today"])
    check("b. drawdown left: the tightest account by share left: Zlarior (51% of $2,000) before ATLAS (89% of $1,000)", o["tight"] == "Zlarior", o["tight"])
    check("b. to pass: the nearest eval in $ (Zlarior 25K #2: $1,500 < Zlarior's $3,807)", o["pass"] == ["Zlarior 25K #2", 1500], o["pass"])
    check("b. the funded payout in MFFU's terms (a sim-funded account starts at $0: balance -$113): earliest = $1,463 more to $1,350 ($1,100 buffer + $250 min); GOAL = the full $1,000 at $2,100 ($800 to you), $2,213 to go",
          o["pay"] == ["ATLAS", False, 1463, 1350, 2213, 2100, 800], o["pay"])
    check("b. fees from the price list when the Ledger is empty: $91.80 + $43 + the 25K #2 at $63 = $197.80; net -$197.80",
          abs(o["fees"]["fees"] - 197.8) < 0.01 and o["fees"]["payouts"] == 0 and abs(o["fees"]["net"] + 197.8) < 0.01 and "price list" in o["fees"]["src"], o["fees"])
    check("b. the phone's Ledger wins: fees + resets $141.80 (expenses are not fees), payouts $800, net $658.20",
          abs(o["ledger"]["fees"] - 141.8) < 0.01 and o["ledger"]["payouts"] == 800 and abs(o["ledger"]["net"] - 658.2) < 0.01 and o["ledger"]["src"] == "your Ledger", o["ledger"])
    check("b. a funded 25K at $27,500 ($1,400 over the $26,100 line): payout ready, ask $1,000 (the plan's max), $800 to you", o["ready"]["ready"] and o["ready"]["ask"] == 1000 and o["ready"]["toYou"] == 800, o["ready"])
    check("b. the bots: LIT watching (window open), ATLAS in a trade (short 1 micros)",
          o["bots"][0][:3] == ["lit", False, True] and o["bots"][1][1] is True and "short 1 micros" in o["bots"][1][3], o["bots"])
    st = o["stats"]
    check("b. streak over real + paper trades (2 losses), last trade = the real one (-$437)", st["streak"] == {"n": 2, "kind": "loss"} and st["last"] == -437, st)
    check("b. too few real trades: setups and weekdays come from the 2026 replay, and the page says so", "replay" in st["basis"] and "not money made" in st["basis"]
          and st["best"] == ["LIT sweep", 0.6] and st["dow"] == ["Mon:3", "Tue:2", "Wed:2", "Thu:2", "Fri:1"], st)
    H = {h["label"].split(" ")[0]: h for h in o["heroes"]}
    check("b. hero words: drawdown $1,025, today -$75, to pass $1,500, payout goal $2,213 to go, net -$198, last trade -$437",
          [h["value"] for h in o["heroes"]] == ["$1,025", "-$75", "$1,500", "$2,213 to go", "-$198", "-$437"], [h["value"] for h in o["heroes"]])
    check("b. junk in (null, numbers, broken home / trades): no throw", o["junk"] == 0, o["junk"])
    _ = H


def home_fixture(now):
    return {"built": now - 300, "board": {"data_t": now - 120, "today": "2026-11-20",
            "lit": {"balance": 49193, "floor": 48168, "room": 1025, "mll": 2000, "to_target": 3807, "target_balance": 53000, "today_pnl": 0, "status": "open",
                    "window": {"open": True, "text": "entry window open until 15:30 ET"}, "waiting": ""},
            "atlas": {"balance": 24887, "floor": 24000, "room": 887, "mll": 1000, "target_balance": 26500, "today_pnl": 0, "status": "funded", "members": []}},
            "live": {"pc": {"t": now - 120}}}


# the browser part serves its OWN copy of every feed the pulse reads (home.json, trading/trades.json, ledger/rules.json), so the expected
# numbers below never move when a fresh export lands (round 5, 2026-11-20: a fresh trades.json broke the old "any known value" check)
TRADES_FIXTURE = {"v": 1, "trades": (
    [{"src": "backtest", "bot": "LIT", "m": "", "day": d, "usd": u, "t": i} for i, (d, u) in enumerate(
        [("2026-01-05", 400), ("2026-01-06", 300), ("2026-01-07", 200), ("2026-01-08", -150), ("2026-01-09", -150)])]
    + [{"src": "backtest", "bot": "ATLAS", "m": "EMA", "day": d, "usd": u, "t": 10 + i} for i, (d, u) in enumerate(
        [("2026-01-12", 90), ("2026-01-13", -60), ("2026-01-14", -60), ("2026-01-15", -60), ("2026-01-16", -60)])]
    + [{"src": "live", "bot": "LIT", "m": "", "day": "2026-10-28", "hm": "03:43", "side": "SHORT", "k": "STOP", "usd": -437, "t": 1793173380}])}
RULES_FIXTURE = {"plans": {"builder_50k": {"price_owner": 91.8, "payout": {"buffer": 2100, "min": 500, "max": 2000, "split": 0.8}},
                           "builder_25k": {"price_owner": 63, "payout": {"buffer": 1100, "min": 250, "max": 1000, "split": 0.8}}},
                 "accounts": {"lit50k": {"plan": "builder_50k", "price": 91.8}, "atlas25k": {"plan": "builder_25k", "price": 43}}}
# what each mounted part must show from those feeds (exact, in page order). Zlarior: $1,025 of $2,000 left, $3,807 to pass; ATLAS funded at
# $24,887: the payout needs $1,463 more; fees $91.80 + $43 = $135 (no Ledger on a fresh phone); trades: 1 real loss of $437, LIT 60%, ATLAS EMA 20%.
# A bare '-' is allowed only where the card has no number yet by design ("To you" before a payout is ready).
EXPECT = {"strip": ["$0", "$1,025", "$3,807"], "hero:room": ["$1,025"], "hero:pass": ["$3,807"], "hero:payout": ["$2,213 to go"], "hero:net": ["-$135"],
          "hero:last": ["-$437"], "hero:today": ["$0"], "accounts": ["$0", "$0"], "bots": [],
          "money": ["$2,213 to go", "-", "$135", "-$135"], "stats": ["1 loss", "-$437", "60%", "20%"]}


def test_browser():
    import time
    now = int(time.time())
    srv, origin = AK.serve(overrides={"/home.json": json.dumps(home_fixture(now)), "/status_feed.json": None,
                                      "/trading/trades.json": json.dumps(TRADES_FIXTURE), "/ledger/rules.json": json.dumps(RULES_FIXTURE)})
    LS = """window.__cls = 0; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
      try { localStorage.setItem('olympus.intro.seen', '1'); %s } catch (e) {}"""
    try:
        with AK.browser() as br:
            for app in APPS:
                for theme in ("", "ivory"):
                    ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
                    ctx.add_init_script(LS % (f"localStorage.setItem('olympus.theme', '{theme}');" if theme else ""))
                    p = ctx.new_page(); errs = []
                    p.on("pageerror", lambda e, errs=errs: errs.append(str(e)[:160]))
                    p.goto(f"{origin}/{app}/index.html", wait_until="load")
                    try:
                        p.wait_for_function("[...document.querySelectorAll('section.pulse')].every((s) => s.classList.contains('ready'))", timeout=15000)
                    except Exception:  # noqa: BLE001
                        pass
                    p.wait_for_timeout(1200)
                    r = p.evaluate("""() => { const secs = [...document.querySelectorAll('section.pulse')];
                      const nums = secs.map((s) => [...s.querySelectorAll('.pu-tv, .pu-hv, .pu-re')].map((e) => e.textContent));
                      const parts = secs.flatMap((s) => { const spec = String(s.dataset.pulse).split(',').map((x) => x.trim()); const boxes = [...s.querySelectorAll(':scope > .pu-part')];
                        return boxes.map((b, i) => [spec[i] || b.dataset.part, [...b.querySelectorAll('.pu-tv, .pu-hv, .pu-re')].map((e) => e.textContent)]); });
                      const links = [...document.querySelectorAll('section.pulse a, nav.folded a')].map((a) => Math.round(a.getBoundingClientRect().height));
                      const ink = secs[0] ? getComputedStyle(secs[0].querySelector('.pu-tv, .pu-hv') || secs[0]).color : '';
                      const bg = getComputedStyle(document.body).backgroundColor;
                      return { ready: secs.length > 0 && secs.every((s) => s.classList.contains('ready')), nums, parts, links, cls: window.__cls,
                        side: document.documentElement.scrollWidth - innerWidth, ink, bg }; }""")
                    tag = f"{app}{' (Ivory)' if theme else ''}"
                    bad = [(spec, vals, EXPECT.get(spec)) for spec, vals in r["parts"] if vals != EXPECT.get(spec)]
                    check(f"c. {tag}: every card shows its feed's exact numbers ({', '.join(spec for spec, _ in r['parts'])}), no page error",
                          r["ready"] and r["parts"] and not bad and not errs, bad or r["parts"], errs)
                    check(f"c. {tag}: no '-' placeholder left in a headline, the strip, an account row or the trades card (a real negative like -$437 is fine)",
                          not [v for spec, vals in r["parts"] if spec != "money" for v in vals if v.strip() == "-"], r["parts"])
                    check(f"c. {tag}: layout shift {r['cls']:.3f} (< 0.01) while the cards fill; no sideways scroll", r["cls"] < 0.01 and r["side"] <= 0, r["cls"], r["side"])
                    check(f"c. {tag}: every pulse / folded-in link is >= 44 px tall", all(h >= 44 for h in r["links"]), r["links"])
                    if theme:
                        lum = lambda c: sum(int(x) for x in re.findall(r"\d+", c)[:3]) / 3  # noqa: E731
                        check(f"c. {tag}: light page, dark ink on the cards", lum(r["bg"]) > 180 and lum(r["ink"]) < 110, r["bg"], r["ink"])
                    ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_core()
    if "--static" not in sys.argv:
        test_browser()
    AK.finish()
