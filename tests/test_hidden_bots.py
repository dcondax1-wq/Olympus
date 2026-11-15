"""Hidden bots (owner 2026-11-15: "we are keeping Zlarior and ATLAS only for now; get rid of BLITZ on the dashboard, just know
it's still there"): engine/hidden_bots.py + dashboard_view.json, the one switch.

  python -X utf8 -m tests.test_hidden_bots

Checks: the switch (default ["blitz"], [] = shown, a broken file = default, real money on account C is never hidden), scrub()
on the real fixtures (Holodeck, Mind, Home) leaves no BLITZ key / item and keeps Zlarior and ATLAS, scrub_inplace() edits
shared parts, site_block() scrubs data.json in place and stamps it, the PC middleware scrubs a JSON answer (and leaves a
non-JSON one and /api/next/blitz alone), pushes are silent (blitz.push_on, narrator prefs), the engine never imports it for
trading, and every page knows window.OLY_HIDDEN.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

from engine import hidden_bots as H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES: list = []


def check(name, cond, info=""):
    RES.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  ({str(info)[:300]})"))


def _blitz_left(o) -> list:
    out = []

    def go(x, p):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "hidden_bots":
                    continue
                if str(k).lower() in ("blitz", "account_c", "scalp") or str(k).lower().startswith("blitz"):
                    out.append(p + "/" + str(k))
                go(v, p + "/" + str(k))
        elif isinstance(x, list):
            for i, v in enumerate(x):
                if isinstance(v, dict) and any(str(v.get(f) or "").lower().startswith(("blitz", "scalp:blitz")) for f in ("id", "key", "bot", "acct")):
                    out.append(f"{p}[{i}]")
                go(v, f"{p}[{i}]")
    go(o, "")
    return out


def main() -> int:
    # ------------------------------------------------------------------ the switch
    check("switch: dashboard_view.json says hidden_bots ['blitz'] (committed default)",
          json.load(open(os.path.join(ROOT, "dashboard_view.json"), encoding="utf-8")).get("hidden_bots") == ["blitz"])
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "v.json")
        json.dump({"hidden_bots": []}, open(p, "w"))
        check("switch: [] = nothing hidden", H.hidden(p) == ())
        open(p, "w").write("{broken")
        check("switch: a broken file = the default (BLITZ hidden)", H.hidden(p) == ("blitz",))
        check("switch: a missing file = the default", H.hidden(os.path.join(d, "nope.json")) == ("blitz",))
        os.makedirs(os.path.join(d, "data"))
        json.dump({"account_c": {"account": "MFFU1", "armed": True}}, open(os.path.join(d, "data", "account_c.json"), "w"))
        check("switch: account C armed for real money -> real_money_c() (BLITZ is then always shown)", H.real_money_c(d) is True)
        json.dump({"account_c": {"account": "Sim101", "armed": False}}, open(os.path.join(d, "data", "account_c.json"), "w"))
        check("switch: account C on Sim / not armed -> stays hidden", H.real_money_c(d) is False)
    check("switch: is_hidden('blitz') by default; Zlarior / ATLAS never", H.is_hidden("blitz") and not H.is_hidden("lit") and not H.is_hidden("atlas"))
    # ------------------------------------------------------------------ scrub on the real fixtures
    for f in ("holo_sample.json", "mind_sample.json", os.path.join("argus", "home_real.json")):
        src = json.load(open(os.path.join(ROOT, "tests", "fixtures", f), encoding="utf-8"))
        before = json.dumps(src, sort_keys=True)
        out = H.publish(src, ("blitz",))
        left = _blitz_left(out)
        check(f"scrub {f}: no BLITZ key or item left, hidden_bots stamped", not left and out.get("hidden_bots") == ["blitz"], left[:6])
        check(f"scrub {f}: the source is not changed (a copy)", json.dumps(src, sort_keys=True) == before)
        check(f"scrub {f}: [] returns it as it is", H.scrub(src, ()) is src)
    holo = H.scrub(json.load(open(os.path.join(ROOT, "tests", "fixtures", "holo_sample.json"), encoding="utf-8")), ("blitz",))
    check("scrub: Zlarior and ATLAS stay (holo bots, trades)", "lit" in (holo.get("bots") or {}) and "atlas" in (holo.get("bots") or {})
          and any(t.get("bot") == "lit" for t in holo.get("trades") or []) and any(t.get("bot") == "atlas" for t in holo.get("trades") or []),
          list((holo.get("bots") or {}).keys()))
    line = "Zlarior: 1 trade · ATLAS paper: 2 trades · BLITZ paper: 3 trades, -$12"
    check("scrub: a summary line loses its BLITZ part only", H.scrub({"t": line}, ("blitz",))["t"] == "Zlarior: 1 trade · ATLAS paper: 2 trades")
    check("scrub: names / lists", H.scrub({"bots": ["lit", "atlas", "blitz"], "accounts": [{"id": "lit"}, {"name": "BLITZ", "plan": "25K"},
                                                                                            {"source": "pc_blitz"}]}, ("blitz",))
          == {"bots": ["lit", "atlas"], "accounts": [{"id": "lit"}]})
    shared = {"accounts": [{"id": "lit"}, {"id": "blitz"}], "blitz": {"x": 1}}
    home = {"accounts": shared["accounts"]}
    H.scrub_inplace(shared, ("blitz",))
    check("scrub_inplace: shared parts change for every holder (home.json is made of data.json's parts)",
          home["accounts"] == [{"id": "lit"}] and "blitz" not in shared)
    # ------------------------------------------------------------------ the site build's last helper
    from engine import live_board
    data = {"live": {"pc": {"blitz": {"eval": 1}, "account_c": {"a": 1}}, "notices": [{"key": "blitz:fill:1", "title": "BLITZ PAPER LONG"},
                                                                                         {"key": "fill:2", "title": "Zlarior LONG"}]},
            "blitz": {"label": "BLITZ"}, "accounts": [], "goals": {}, "second": {}, "extras": {}}
    H.FORCE = ("blitz",)
    try:
        bd = live_board.site_block(data, {}, now=1_790_000_000)
    finally:
        H.FORCE = None
    check("site_block: data.json loses BLITZ in place (cards, live.pc, notices) and says hidden_bots",
          "blitz" not in data and "blitz" not in data["live"]["pc"] and "account_c" not in data["live"]["pc"]
          and [n["key"] for n in data["live"]["notices"]] == ["fill:2"] and data.get("hidden_bots") == ["blitz"], data)
    check("site_block: the board it returns is scrubbed and stamped", isinstance(bd, dict) and bd.get("hidden_bots") == ["blitz"]
          and "blitz" not in bd and not _blitz_left(bd), _blitz_left(bd)[:5])
    # ------------------------------------------------------------------ the PC dashboard middleware
    async def app(scope, receive, send):
        body = json.dumps({"lit": 1, "blitz": {"room": 5}, "accounts": [{"id": "blitz"}, {"id": "atlas"}]}).encode()
        ctype = b"application/json" if scope["path"] != "/api/text" else b"text/plain"
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", ctype), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    def call(path, method="GET"):
        got = []

        async def send(m):
            got.append(m)

        async def receive():
            return {"type": "http.request"}
        asyncio.run(H.ScrubMiddleware(app, hide_fn=lambda: ("blitz",))({"type": "http", "method": method, "path": path}, receive, send))
        body = b"".join(m.get("body", b"") for m in got if m["type"] == "http.response.body")
        hdr = dict(next(m for m in got if m["type"] == "http.response.start")["headers"])
        return body, hdr
    b, h = call("/api/next/board")
    j = json.loads(b)
    check("middleware: a GET /api JSON answer loses BLITZ, says hidden_bots, right content-length",
          j == {"lit": 1, "accounts": [{"id": "atlas"}], "hidden_bots": ["blitz"]} and int(h[b"content-length"]) == len(b), j)
    check("middleware: /api/next/blitz (its own page) answers as before", "blitz" in json.loads(call("/api/next/blitz")[0]))
    check("middleware: a POST is never touched", "blitz" in json.loads(call("/api/next/start", "POST")[0]))
    check("middleware: a non-JSON answer passes untouched", b"blitz" in call("/api/text")[0])
    src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    check("middleware: server.py installs it", "ScrubMiddleware as _HideBots" in src and "app.add_middleware(_HideBots)" in src)
    # ------------------------------------------------------------------ silent pushes, engine untouched
    from engine import blitz, narrator
    H.FORCE = ("blitz",)
    try:
        check("pushes: BLITZ PAPER notices are recorded only (push_on False even with blitz.push true)", blitz.push_on({"push": True}) is False)
        check("pushes: the narrator's BLITZ kind is off", narrator.push_prefs("/nonexistent").get("blitz") is False)
    finally:
        H.FORCE = ()
    try:
        check("pushes: shown again -> blitz.push true pushes as before", blitz.push_on({"push": True}) is True)
    finally:
        H.FORCE = None
    from types import SimpleNamespace
    from engine.account_c import AccountC
    for kind, want in (("PAPER", 0), ("SIM", 0), ("LIVE", 1)):
        sent, logs = [], []
        fake = SimpleNamespace(kind=lambda k=kind: k, log=lambda a, b: logs.append(b), bot=SimpleNamespace(_push_send=sent.append))
        H.FORCE = ("blitz",)
        try:
            AccountC._send(fake, {"title": "BLITZ Sim101 EVAL PASSED"})
        finally:
            H.FORCE = None
        check(f"pushes: account C on {kind} while hidden -> {'pushed (real money is never silenced)' if want else 'logged only'}",
              len(sent) == want and (want or logs), (sent, logs))
    eng = open(os.path.join(ROOT, "engine", "blitz.py"), encoding="utf-8").read()
    check("engine: BLITZ's rule / ledgers do not read the switch (only push_on does)", eng.count("hidden_bots") == 3 and "def push_on" in eng.split("hidden_bots")[0][-600:])
    check("engine: hidden_bots imports no broker, adapter or order module",
          not any(w in open(H.__file__, encoding="utf-8").read() for w in ("ninjatrader", "tradovate", "adapter", "import live")))
    # ------------------------------------------------------------------ the pages
    # the definer (idempotent) sits at the top of the first script each app runs: main.js (Zenith, deferred first), Jarvis's
    # data.js and brain.js (modules), web_next routes.js (module); no <head> line of any page changed
    pages = {"phone main.js": "tools/web_public/main.js", "jarvis data.js": "tools/web_public/jarvis/data.js",
             "jarvis brain.js": "tools/web_public/jarvis/brain.js", "pc routes.js": "web_next/js/next/routes.js"}
    for k, p in pages.items():
        s = open(os.path.join(ROOT, p), encoding="utf-8").read()
        check(f"pages: {k} defines window.OLY_HIDDEN (default ['blitz'], kept in localStorage, idempotent)",
              "window.OLY_HIDDEN = H" in s and "var L = ['blitz']" in s and "window.OLY_HIDDEN) return" in s)
    mj = open(os.path.join(ROOT, "tools", "web_public", "main.js"), encoding="utf-8").read()
    check("pages: main.js defines it before its own code and reads each data.json / home.json",
          mj.index("window.OLY_HIDDEN = H") < mj.index("'use strict';") + 3000 and mj.count("window.OLY_HIDDEN.seen(") == 2)
    W = lambda p: open(os.path.join(ROOT, "tools", "web_public", p), encoding="utf-8").read()
    check("pages: the BLITZ tab is not made while hidden (clean.js)", "if (!bzHidden && !GROUPS.some((g) => g.id === 'blitz'))" in W("clean.js"))
    for f in ("boardcore.js", "missioncore.js", "statuscore.js", "deckcore.js", "mindcore.js", "holocore.js", "realcore.js",
              "moneynowcore.js", "liveview.js", "polish.js", "blitz.js", "jarvis/data.js", "jarvis/brain.js"):
        check(f"pages: {f} asks OLY_HIDDEN", "OLY_HIDDEN" in W(f))
    for f in ("boardcore.js", "missioncore.js", "statuscore.js", "deckcore.js", "mindcore.js", "holocore.js", "realcore.js", "moneynowcore.js", "fx.js"):
        same = W(f) == open(os.path.join(ROOT, "web_next", "js", f if f == "fx.js" else os.path.join("next", f)), encoding="utf-8").read()
        check(f"pages: {f} byte-identical on both dashboards", same)
    rt = open(os.path.join(ROOT, "web_next", "js", "next", "routes.js"), encoding="utf-8").read()
    check("pages: the PC sidebar drops BLITZ while hidden (routes.js)", "export const BLITZ_HIDDEN" in rt)
    n_ok = sum(1 for _, ok in RES if ok)
    print(f"hidden bots: {n_ok}/{len(RES)} {'ALL PASS' if n_ok == len(RES) else 'FAILED'}")
    return 0 if n_ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
