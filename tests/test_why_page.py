"""WHY WE WIN / WHY WE LOSE (2026-11-18, night-anatomy; tools/win_loss_anatomy.py, tools/web_public/why/,
research/writeups/win-loss-anatomy-2026-11-18.md).
  a. the tool's pure part: loss cause (news / shaken out / turned / never), the careful-human checklist, spans, sessions, VIX band,
     $ words, the ZEUS Lab kind "anatomy" validation; the trade-path facts on a tiny made-up bar set (MFE / MAE and the minutes to
     each, after the exit: the target later, +1R, the next 30 / 60 minutes, "a stop 50% wider")
  b. page_doc on a small made-up study: plain words with $, every bot card complete, hidden bots left out
  c. the committed files agree: research/anatomy/*.json (631 Zlarior / 1,288 ATLAS trades), why.json = the study + the tested rules,
     the 4 rules registered in the ZEUS Lab (valid, runnable), no account ids / emails, BLITZ absent while it is hidden
  d. the page: AGORA look (theme #14110e, agora.css, a11y), text only through textContent, it reads only why.json, no outside
     address, the static AGORA audit has no hard FAIL for the app
  e. node: why.js model() on the committed why.json (what the page shows), a broken file, a hidden bot, the Kalshi K8 card
  f. Chromium 390 x 844 (skip with WHY_NO_BROWSER=1; run under flock -w 2400 /tmp/olympus_browser.lock): every section drawn,
     no sideways scroll, no page error
    python -X utf8 -m tests.test_why_page
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
APP = os.path.join(WEB, "why")
OUT = os.path.join(ROOT, "research", "anatomy")
RES: list = []

from tools import win_loss_anatomy as W  # noqa: E402


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[-600:]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------ a. the pure part
class FakeBars:
    """A tiny bar container shaped like tools/lit_final.bars (t, o, h, l, c, mod, day, n, secs, dirs)."""

    def __init__(self, rows, secs=60, t0=1767348000, mod0=600):
        import numpy as np
        self.secs = secs
        self.n = len(rows)
        self.t = np.array([t0 + i * secs for i in range(self.n)], dtype=np.int64)
        self.o, self.h, self.l, self.c = (np.array([float(r[k]) for r in rows]) for k in range(4))
        self.mod = np.array([mod0 + i * secs // 60 for i in range(self.n)])
        self.day = np.zeros(self.n, dtype=int)

    def dirs(self, d):
        if d == 1:
            return self.h, self.l, self.c, self.o
        return -self.l, -self.h, -self.c, -self.o


def part_a():
    r = {"usd": -400, "exit": "STOP", "news_in": True, "mfe_r": 0.1}
    check("a. cause: a release inside the trade is 'news' first", W.cause_of(r) == "news")
    check("a. cause: stopped, then the target before 0.5R deeper = 'wick' (shaken out)",
          W.cause_of({"usd": -1, "exit": "STOP", "post_tgt_clean": True, "mfe_r": 0.2}) == "wick")
    check("a. cause: no target (BLITZ) -> +1R before 0.5R deeper decides the shake-out",
          W.cause_of({"usd": -1, "exit": "STOP", "post_tgt_clean": None, "post_1r_clean": True, "mfe_r": 0.2}) == "wick"
          and W.cause_of({"usd": -1, "exit": "STOP", "post_1r_clean": False, "mfe_r": 0.2}) == "never")
    check("a. cause: +0.5R first = 'turned', less = 'never', a winner has none",
          W.cause_of({"usd": -1, "exit": "STOP", "mfe_r": 0.6}) == "turned" and W.cause_of({"usd": -1, "exit": "BE", "mfe_r": 0.3}) == "never"
          and W.cause_of({"usd": 5, "exit": "TARGET", "mfe_r": 3}) is None)
    f = W.checks_of({"d1": "against", "h1": "against", "rng_atr": 1.2, "news_next": 12, "pd_tgt_r": 0.4})
    check("a. checklist: against both trends, late (1 ATR), news within 30 min, prior-day level under 1R ahead",
          f == ["against_htf", "late", "news_soon", "no_room"], f)
    check("a. checklist: one trend with the trade, no news (600), a level 3R ahead / already passed -> no flag",
          W.checks_of({"d1": "with", "h1": "against", "rng_atr": 0.5, "news_next": 600, "pd_tgt_r": 3}) == []
          and W.checks_of({"pd_tgt_r": -0.5}) == [])
    check("a. spans: Jan-Jun / Jul-Oct 2026 and the 2021-25 reference", (W.span_of("2026-03-02"), W.span_of("2026-07-01"), W.span_of("2023-05-05"),
                                                                           W.span_of("2020-01-02")) == ("H1", "H2", "2021-25", None))
    check("a. sessions by the ET minute (18:00 = Asia)", [W.session_of(m) for m in (1100, 150, 360, 540, 600, 720, 900)] ==
          ["Asia 18-02", "London 02-05", "London late 05-08", "NY pre 08-09:30", "NY AM 09:30-11:30", "NY lunch 11:30-13:30", "NY PM 13:30-16"])
    check("a. VIX band and $ words", (W.vix_band(14.9), W.vix_band(20), W.vix_band(None), W.money(-1234.4), W.money(5)) ==
          ("VIX <15", "VIX 20-25", None, "-$1,234", "+$5"))
    good = {"id": "x", "bot": "lit", "kind": "anatomy", "anatomy": {"fact": "pullback", "mult": 1.25}}
    check("a. ZEUS Lab kind anatomy: a known fact and 0..1.5 pass, anything else is refused",
          W.rule_errors(good) == [] and W.rule_errors({**good, "anatomy": {"fact": "moon", "mult": 1}}) and
          W.rule_errors({**good, "anatomy": {"fact": "checklist", "mult": 2}}) and W.rule_errors({**good, "bot": "kalshi"}))
    check("a. rule facts: pullback = daily with + 1h against; checklist = any flag",
          W.fact_on("pullback", {"d1": "with", "h1": "against"}) and not W.fact_on("pullback", {"d1": "with", "h1": "with"})
          and W.fact_on("checklist", {"news_next": 5}) and not W.fact_on("checklist", {}))
    # a long from 100, stop 90, target 130: the bars dip to 95 at minute 3, reach +12 at minute 5, stop out at minute 7;
    # after the exit price runs to 131 (the target) before going 0.5R deeper than the stop
    rows = [(100, 101, 99, 100), (100, 102, 98, 101), (101, 101, 95, 96), (96, 105, 96, 104), (104, 112, 103, 110),
            (110, 110, 100, 101), (101, 101, 89, 90), (90, 100, 90, 99), (99, 120, 99, 118), (118, 131, 117, 130), (130, 130, 120, 121)]
    B = FakeBars(rows)
    P = W.path_facts(B, 0, 6, 1, 100.0, 90.0, 130.0, 10.0, 90.0 - 0.25)
    check("a. path: MFE +12 pts at minute 5, MAE to the stop (10 pts + 1 tick) at minute 7",
          P["mfe_pts"] == 12.0 and P["t_mfe"] == 5 and P["mae_pts"] == 10.25 and P["t_mae"] == 7, P)
    check("a. after the exit: the target reached cleanly (shaken out), +1R too, best +3.1R from the entry",
          P.get("post_tgt") is True and P.get("post_tgt_clean") is True and P.get("post_1r_clean") is True and P.get("post_best_r") == 3.1, P)
    check("a. a stop 50% wider (85): the target came first -> wider_win", P.get("wider_win") is True, P)
    P2 = W.path_facts(B, 0, 6, 1, 100.0, 90.0, None, 10.0, 89.75)
    check("a. no target (BLITZ): wider_1r instead of wider_win", "wider_win" not in P2 and P2.get("wider_1r") is True, P2)
    K = [{"day": "2026-08-03", "leg": "A_gold", "window": "A", "metal": "gold", "period": "train", "price": 0.45, "won": True, "usd": 18.0},
         {"day": "2026-08-03", "leg": "A_silver", "window": "A", "metal": "silver", "period": "train", "price": 0.62, "won": True, "usd": 8.0},
         {"day": "2026-08-04", "leg": "A_gold", "window": "A", "metal": "gold", "period": "test", "price": 0.52, "won": False, "usd": -15.3},
         {"day": "2026-08-04", "leg": "A_silver", "window": "A", "metal": "silver", "period": "test", "price": 0.51, "won": False, "usd": -15.3}]
    k = W.k8_anatomy(K)
    check("a. Kalshi K8: wins vs losses, price bands, both metals of a window together (1 both won, 1 both lost), weeks",
          k["all"]["n"] == 4 and k["all"]["won"] == 50.0 and k["pairs"] == {"n": 2, "both_won": 1, "both_lost": 1}
          and k["price"][0]["usd"] == 18 and k["price"][3]["avg_win"] == 8.0 and len(k["say"]) == 4 and W.k8_anatomy([]) == {}, k)
    rows2 = [(100, 101, 99, 100), (100, 100, 89, 90), (90, 91, 80, 81), (81, 140, 81, 139)]
    P3 = W.path_facts(FakeBars(rows2), 0, 1, 1, 100.0, 90.0, 130.0, 10.0, 89.75)
    check("a. a real stop: price went 0.5R deeper before the target -> not a shake-out", P3.get("post_tgt") is True and P3.get("post_tgt_clean") is False, P3)


# ------------------------------------------------------------------------------------------------ b. page_doc
def tiny_study():
    def span(n, net, lost):
        return {"n": n, "tpw": 3.0, "win": 50.0, "pf": 2.0, "net": net, "per_month": net // 4, "dd": -500, "won": net + lost, "lost": lost,
                "n_win": n // 2, "n_loss": n - n // 2,
                "causes": {c: {"n": 1, "usd": -lost // 4, "share": 25.0} for c in W.CAUSES},
                "stops": {"n": 5, "usd": -900, "mfe_med": 0.2, "mins_med": 30, "never_half": 70.0, "target_later": 10.0, "back_clean": 0.0,
                          "wider_win": 2.0, "after60_med": -0.1},
                "be": {"n": 3, "usd": 4, "mfe_med": 1.5, "target_later": 33.3},
                "winners": {"n": n // 2, "usd": net + lost, "mae_med": 0.2, "mae_small": 50.0, "t_mfe_med": 60, "mins_med": 100, "top20_usd": net,
                            "top20_share_of_net": 100.0, "day_with": 60.0, "beyond_target_r": 2.0},
                "losers": {"n": n - n // 2, "usd": -lost, "mfe_med": 0.3, "t_mae_med": 20, "mins_med": 30, "day_with": 30.0},
                "day_with": {"with": {"n": 5, "avg_r": 1.2, "usd": 900}, "against": {"n": 5, "avg_r": -0.1, "usd": -100}},
                "checklist": {"losers_flagged": {"n": 2, "usd": -300, "share": 30.0}, "good_losers": {"n": 3, "usd": -700, "share": 70.0},
                              "winners_flagged": {"n": 2, "usd": 800, "share": 40.0}, "net_if_skipped": -500, "per_month_if_skipped": -100, "checks": {}},
                "biggest_losers": [{"day": "2026-02-03", "hm": "03:10", "side": "long", "who": "LIT", "exit": "STOP", "usd": -480, "r": -1.0, "mfe_r": 0.1,
                                    "mins": 22, "cause": "never", "flags": []}]}
    chance = {"real": 3, "worse": 2, "better": 1, "shuffled_mean": 4.0, "shuffled_p95": 7, "p": 0.6, "n_buckets": 20, "draws": 10, "list": []}
    bots = {}
    for b in ("lit", "atlas", "blitz"):
        bots[b] = {"bot": b, "name": W.NAME[b], "spans": {sp: span(10, 2000, 1000) for sp in ("H1", "H2", "2021-25", "2026")}, "chance": chance}
    E = {"v": 1, "built": "2026-11-18 23:59", "bots": bots}
    R = {"rules": [{"id": "lit_x", "bot": "lit", "title": "Zlarior: a test rule", "status": "rejected", "why": "Jul-Oct (check): -$23 at the LIT size",
                    "usd_month_by": {"H1": 10, "H2": -5, "2021-25": 1}, "with": {"H1": {"per_month": 110}}, "today": {"H1": {"per_month": 100}}},
                   {"id": "blitz_x", "bot": "blitz", "title": "BLITZ: hidden rule", "status": "passes", "why": "x", "usd_month_by": {}}]}
    return E, R


def part_b():
    E, R = tiny_study()
    D = W.page_doc(E, R, hide=("blitz",), data_to="2026-10-16")
    names = [b["name"] for b in D["bots"]]
    check("b. page_doc: kind olympus-why, the note says nothing changes live, the hidden bot left out", D["kind"] == "olympus-why"
          and "Nothing here changes a live setting" in D["note"] and names == ["Zlarior", "ATLAS"] and D["hidden_note"], (names, D.get("hidden_note")))
    b = D["bots"][0]
    check("b. a bot card: headline with $, 4 causes largest loss first, the checklist split per period, why we win, after the exit, rules",
          "$" in b["headline"] and [c["key"] for c in b["lose"]] and len(b["lose"]) == 4 and len(b["careful"]["net"]) == 3
          and len(b["win"]) == 3 and len(b["after"]) >= 2 and b["rules"] and b["rules"][0]["status"] == "rejected" and b["chance"], b)
    check("b. the tested count leaves the hidden bot's rule out (1 rule, 0 passed)", D["tested"].startswith("1 rules") and ": 0 passed" in D["tested"], D["tested"])
    m = b["rules"][0]["months"]
    check("b. a rule's $ a month: today / with it / change per period", m[0] == {"span": "Jan-Jun", "now": 100, "with": 110, "diff": 10}, m)
    D2 = W.page_doc(E, R, hide=(), data_to=None)
    check("b. nothing hidden -> all three bots, no hidden note", [x["bot"] for x in D2["bots"]] == ["lit", "atlas", "blitz"] and not D2["hidden_note"])


# ------------------------------------------------------------------------------------------------ c. the committed files
def part_c():
    T = {b: W.load_rows(b) for b in W.BOTS}
    check("c. per-trade tables: Zlarior 631 (= run lit_live), ATLAS 1,288 account trades, BLITZ 2026 + 2021-25",
          len(T["lit"]) == 631 and len(T["atlas"]) == 1288 and sum(1 for r in T["blitz"] if r["span"] in ("H1", "H2")) >= 320,
          {b: len(v) for b, v in T.items()})
    need = ("mfe_r", "mae_r", "mfe_usd", "mae_usd", "t_mfe", "t_mae", "mins", "exit", "session", "dow", "vix_band", "rng_atr", "gap18",
            "pd_tgt_r", "d1", "h1", "er5", "news_next", "news_in", "post_best_r", "after60_r")
    miss = [k for k in need if not any(k in r for r in T["lit"])]
    check("c. each Zlarior row has the context: MAE / MFE ($ and R, minutes), exit, session, weekday, VIX band, ranges, gap, prior-day "
          "level, daily / 1h trend, chop, news, after the exit", not miss, miss)
    run = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
    st = {int(r[1]): r[5] for r in run["trades"]}
    bad = [r["entry_t"] for r in T["lit"] if abs(st.get(r["entry_t"], 1e9) - r["usd"]) > 0.6]
    check("c. Zlarior $ per trade = the stored run lit_live", not bad, bad[:5])
    E = json.load(open(os.path.join(OUT, "explain.json"), encoding="utf-8"))
    R = json.load(open(os.path.join(OUT, "rules.json"), encoding="utf-8"))
    D = json.load(open(os.path.join(APP, "why.json"), encoding="utf-8"))
    check("c. why.json: kind, built, data date, source write-up exists, 'nothing changes a live setting'",
          D.get("kind") == "olympus-why" and D.get("built") and D.get("data_to") and os.path.isfile(os.path.join(ROOT, D["source"]))
          and "Nothing here changes a live setting" in D.get("note", ""), {k: D.get(k) for k in ("kind", "built", "data_to", "source")})
    from engine import hidden_bots as HB
    hid = set(HB.hidden())
    bots = [b["bot"] for b in D["bots"]]
    check("c. why.json shows Zlarior and ATLAS, never a hidden bot (dashboard_view.json)", {"lit", "atlas"} <= set(bots) and not (hid & set(bots))
          and D.get("hidden_bots") == sorted(hid) if hid else {"lit", "atlas"} <= set(bots), (bots, sorted(hid)))
    ok = True
    for b in D["bots"]:
        x = E["bots"][b["bot"]]["spans"]["2026"]
        ok = ok and b["lose_total"] == -x["lost"] and abs(sum(c["usd"] for c in b["lose"]) + x["lost"]) <= 4
    check("c. every card's 2026 loss total and cause $ = research/anatomy/explain.json", ok)
    kk = D.get("kalshi") or {}
    check("c. the Kalshi K8 card: 4 lines with $, 6 legs, 4 price bands, from K8's own bet list",
          len(kk.get("lines") or []) == 4 and all("$" in x for x in kk["lines"]) and len(kk.get("legs") or []) == 6
          and len(kk.get("price") or []) == 4 and "legs_bets.csv" in kk.get("source", ""), kk)
    rid = {r["id"]: r["status"] for r in R["rules"]}
    pid = {r["id"]: r["status"] for b in D["bots"] for r in b["rules"]}
    check("c. the page's tested rules = rules.json (statuses too)", pid and all(rid.get(k) == v for k, v in pid.items()), (pid, rid))
    check("c. rules.json: run with the live files untouched, the Lab's many-tests bar recorded", R.get("protected_ok") is True and R.get("p_needed"))
    from tools import zeus_lab as Z
    exps, forever, rules, errs = Z.load_registry()
    mine = {e["id"]: e for e in exps if e["id"] in {r["id"] for r in W.RULES}}
    check("c. the 4 rules are in the ZEUS Lab registry, valid and runnable (kind anatomy / atlas_tilt), none blocked",
          len(mine) == 4 and all(e["kind"] in Z.RUNNABLE and not Z.blocked_by(e, forever) for e in mine.values())
          and not [x for x in errs if any(i in x for i in mine)], (sorted(mine), errs))
    s = json.dumps(D) + rd(APP, "index.html") + rd(APP, "why.js")
    check("c. no account ids, no emails on the page", not re.search(r"[A-Z]{3,}\d{5,}", s) and "@" not in s)


# ------------------------------------------------------------------------------------------------ d. the page files
def part_d():
    html, js, css = rd(APP, "index.html"), rd(APP, "why.js"), rd(APP, "why.css")
    check("d. AGORA look: theme-color #14110e, data-theme agora, agora.css + agora-apps.css, a11y.css + a11y.js, why.js",
          'name="theme-color" content="#14110e"' in html and 'data-theme="agora"' in html and "agora.css" in html and "agora-apps.css" in html
          and "a11y.css" in html and "a11y.js" in html and 'src="why.js' in html)
    check("d. manifest + icon + jarvis.json tile", all(os.path.isfile(os.path.join(APP, f)) for f in ("manifest.webmanifest", "icon.svg", "jarvis.json"))
          and json.load(open(os.path.join(APP, "manifest.webmanifest"), encoding="utf-8"))["theme_color"] == "#14110e")
    tile = json.load(open(os.path.join(APP, "jarvis.json"), encoding="utf-8"))
    check("d. jarvis.json tile: name, status, 3 kpis, lines, theme", tile.get("name") and tile.get("status") and len(tile.get("kpis") or []) == 3
          and tile.get("lines") and tile.get("theme") == "#14110e", tile)
    check("d. text only through textContent (no innerHTML / insertAdjacentHTML / document.write), no inline handlers",
          not re.search(r"innerHTML|insertAdjacentHTML|document\.write|outerHTML", js) and not re.search(r"\son[a-z]+=", html))
    urls = re.findall(r"https?://[^\s\"'<>)]+", html + js + css)
    check("d. no outside address; the only file it reads is why.json; it sends nothing",
          not urls and re.findall(r"fetch\('([^']+)'", js) == ["why.json"] and not re.search(r"method:\s*'POST'|XMLHttpRequest|sendBeacon|WebSocket", js), urls)
    check("d. phone first: 44 px taps, overflow-wrap, a side-scroll box only around the tables",
          "min-height: 44px" in css and "overflow-wrap" in css and ".wrap { overflow-x: auto" in css)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import agora_audit as A
    res = A.static_scan()
    r = res.get("why")
    check("d. the AGORA static audit sees the app and finds no hard FAIL", r is not None and not A.static_fail(r), r and A.static_fail(r))


# ------------------------------------------------------------------------------------------------ e. node: what the page shows
def node(body):
    script = ("const WHY = require(" + json.dumps(os.path.join(APP, "why.js")) + "); const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


def part_e():
    if not shutil.which("node"):
        print("[SKIP] e. node missing")
        return
    doc = rd(APP, "why.json")
    r = node(f"""const d = {doc}; const m = WHY.model(d);
      const h = JSON.parse(JSON.stringify(d)); h.hidden_bots = ['atlas'];
      out({{ ok: m.ok, n: m.bots.length, names: m.bots.map((b) => b.name), w: m.bots.map((b) => b.lose.map((x) => x.width)),
             v: m.bots[0].lose[0].value, rules: m.bots.map((b) => b.rules.length), rows: m.bots[0].money.length,
             care: m.bots[0].carefulRows.map((x) => x.month), bad: WHY.model(null), bad2: WHY.model({{ kind: 'x' }}).ok,
             hid: WHY.model(h).bots.map((b) => b.name), money: [WHY.money(-1234.5), WHY.money(0), WHY.money(null), WHY.money(1234567)],
             k: m.kalshi && {{ n: m.kalshi.lines.length, rows: m.kalshi.rows.length, price: m.kalshi.price.length }} }});""")
    check("e. model(): Zlarior and ATLAS, the biggest cause first at 100% width, every width 0..100",
          r.get("ok") is True and r.get("names", [])[:2] == ["Zlarior", "ATLAS"] and all(x[0] == 100 and all(0 <= y <= 100 for y in x) for x in r.get("w", [])), r)
    check("e. a cause row reads '$ · share · trades'; 3 money rows; the checklist $ a month per period; the rules listed",
          re.match(r"^[-+]\$[\d,]+ · \d+% · \d+ trades$", r.get("v", "")) and r.get("rows") == 3 and len(r.get("care", [])) == 3
          and all(n >= 1 for n in r.get("rules", [])), r)
    check("e. a broken / missing file says so (never blank); a bot the file hides is not drawn",
          r.get("bad", {}).get("ok") is False and "why.json" in r.get("bad", {}).get("status", "") and r.get("bad2") is False
          and "ATLAS" not in r.get("hid", []), r)
    check("e. $ words: -$1,235 / +$0 / - / +$1,234,567", r.get("money") == ["-$1,235", "+$0", "-", "+$1,234,567"], r.get("money"))
    check("e. the Kalshi K8 card: 4 lines, 6 legs, 4 price bands", r.get("k") == {"n": 4, "rows": 6, "price": 4}, r.get("k"))


# ------------------------------------------------------------------------------------------------ f. Chromium 390 x 844
def part_f():
    try:
        from playwright.sync_api import sync_playwright
        from tests import browser_kit
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] f. browser (playwright missing: {e})")
        return

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            br = browser_kit.launch(pw)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
            errs = []
            p = ctx.new_page()
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(base + "/why/")
            p.wait_for_function("document.querySelectorAll('#bots section.bot').length >= 2")
            r = p.evaluate("""(() => { const bots = [...document.querySelectorAll('#bots section.bot')];
              const taps = [...document.querySelectorAll('.jump a, details.more summary')].map((a) => a.getBoundingClientRect().height);
              return { n: bots.length, names: bots.map((b) => b.querySelector('h2.sect').textContent),
                       cards: bots.map((b) => b.querySelectorAll('.ag-card').length), bars: document.querySelectorAll('.bars li').length,
                       rules: document.querySelectorAll('.rule').length, verdict: !document.getElementById('verdict').hidden,
                       wide: document.documentElement.scrollWidth <= window.innerWidth + 1, tap: Math.min(...taps),
                       foot: document.getElementById('foot').textContent, status: document.getElementById('status').textContent }; })()""")
            check("f. 390 px: the short answer, Zlarior + ATLAS each with 7 cards, 4 cause bars each, the tested rules, no sideways scroll",
                  r["n"] == 2 and r["names"] == ["Zlarior", "ATLAS"] and all(c >= 6 for c in r["cards"]) and r["bars"] == 8 and r["rules"] >= 4
                  and r["verdict"] and r["wide"], r)
            check("f. taps >= 44 px, the footer names the write-up, the status line the data date", r["tap"] >= 44 and "win-loss-anatomy" in r["foot"]
                  and "Data to" in r["status"], r)
            k = p.evaluate("(() => ({ shown: !document.getElementById('kalshi').hidden, lines: document.querySelectorAll('#kalshiLines li').length }))()")
            check("f. the Kalshi K8 card is drawn (4 lines)", k == {"shown": True, "lines": 4}, k)
            check("f. no page errors", not errs, errs)
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    if not os.environ.get("WHY_NO_BROWSER"):
        part_f()
    n = sum(RES)
    print(f"\nwhy_page: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
