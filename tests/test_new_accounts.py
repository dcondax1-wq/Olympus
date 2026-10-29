"""New MFFU account Names (2026-10-29, engine/new_accounts.py): after a pass / fail MFFU issues a new account Name; the bot
notices it in NinjaTrader, pushes once and offers it on the Start page. It never assigns, arms or trades it by itself.

    python -X utf8 -m tests.test_new_accounts      (temp files only: go.CFG, the NinjaTrader folder, the state file)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from engine import go as G  # noqa: E402
from engine import new_accounts as NA  # noqa: E402
from engine import ops_checks as OC  # noqa: E402
from engine import second as SE  # noqa: E402
from engine import account_b as AB  # noqa: E402
from engine import start_api as S  # noqa: E402

RES = []
L50, L25 = "MFFUEVBLDR602936016", "MFFUEVBLDR602936017"
NEW50, NEW25, FUNDED = "MFFUFBLDR700000001", "MFFUEVBLDR602936099", "MFFUFDBLDR700000002"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def world(tmp):
    G.CFG = os.path.join(tmp, "start_bot.json")
    G.SECOND_PATH = os.path.join(tmp, "second_model.json")
    shutil.copy(SE.CFG_PATH, G.SECOND_PATH)
    AB.set_account_b(None, path=G.SECOND_PATH)
    G.ALLOW_PATH = os.path.join(tmp, "allow.json")
    G.ACCOUNTS_PATH = os.path.join(tmp, "accounts.json")
    G.ANCHOR_PATH = os.path.join(tmp, "eval_anchor.json")
    G._save({"lit": L50, "atlas": L25, "prepped": "2026-10-28"})
    nt = os.path.join(tmp, "NinjaTrader 8")
    os.makedirs(os.path.join(nt, "le_feed"), exist_ok=True)
    os.makedirs(os.path.join(nt, "outgoing"), exist_ok=True)
    now = int(time.time())
    with open(os.path.join(nt, "le_feed", "accounts.csv"), "w") as fh:
        fh.write("name,time,cash,realized,unrealized,netliq\n"
                 f"{L50},{now},52710.80,0,0,52710.80\n{L25},{now},24100,0,0,24100\nSim101,{now},100000,0,0,100000\n"
                 f"{NEW50},{now},50000,0,0,50000\n{NEW25},{now},25000,0,0,25000\n")
    open(os.path.join(nt, "outgoing", f"MNQ DEC26 Globex_{FUNDED}_Position.txt"), "w").write("FLAT;0;0")
    os.environ["NINJATRADER_FOLDER"] = nt
    return nt


def main():
    tmp = tempfile.mkdtemp(prefix="le_newacct_")
    keep = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "bot_running")}
    env_keep = os.environ.get("NINJATRADER_FOLDER")
    state = os.path.join(tmp, "new_accounts.json")
    try:
        nt = world(tmp)
        G.bot_running = lambda: False
        c = {r["name"]: r for r in NA.candidates(nt, state)}
        check("candidates: the new 50K (Zlarior), the new 25K (ATLAS / BLITZ) and a Name seen only in a position file (any "
              "role); the two Names the bots use and Sim101 are not offered",
              set(c) == {NEW50, NEW25, FUNDED} and c[NEW50]["roles"] == ["zlarior"] and c[NEW25]["roles"] == ["atlas", "blitz"]
              and c[FUNDED]["roles"] == ["zlarior", "atlas", "blitz"], c)
        st = NA.status(nt, state)
        check("status: one line per Name, e.g. 'New account MFFUFBLDR700000001 ($50,000) in NinjaTrader: use it for Zlarior?'; "
              "BLITZ not tappable until its slot registers",
              any(x["say"] == f"New account {NEW50} ($50,000) in NinjaTrader: use it for Zlarior?" for x in st["new"])
              and st["blitz_ready"] is False, st)
        # pushes: one per Name, through the ops helper's key store (never twice)
        sent = []
        ostate = {"sent": {}}
        OC.ops_log = lambda *a, **k: None          # the ops log lives in logs/: not written by a test
        for _ in range(2):
            for p in NA.notices(folder=nt, path=state):
                OC.send(p, ostate, sender=lambda pl: (sent.append(pl["key"]), {"sent": 1})[1])
        check("phone push: one per new Name (key newacct:<Name>), the second ops tick sends nothing again",
              sorted(sent) == sorted(f"newacct:{n}" for n in (NEW50, NEW25, FUNDED)), sent)
        # the owner's taps
        before = json.load(open(G.CFG))
        r_bad = NA.use(NEW25, "zlarior", path=state, folder=nt)
        r_run = None
        G.bot_running = lambda: True
        r_run = NA.use(NEW50, "zlarior", path=state, folder=nt)
        G.bot_running = lambda: False
        check("refused: a 25K Name for Zlarior (size), and any change while the bot runs (stop it first); start_bot.json unchanged",
              not r_bad["ok"] and "25K" in r_bad["error"] and not r_run["ok"] and "Stop the bot" in r_run["error"]
              and json.load(open(G.CFG)) == before, (r_bad, r_run))
        r = NA.use(NEW50, "zlarior", path=state, folder=nt)
        cfg = json.load(open(G.CFG))
        check("Use for Zlarior: the 50K Name is the new one, ATLAS kept, the setup runs again (prepped cleared), nothing armed "
              "(no armed / phrase / opt-in written), the old Name retired (never offered back)",
              r["ok"] and cfg.get("lit") == NEW50 and cfg.get("atlas") == L25 and "prepped" not in cfg
              and not any(k in cfg for k in ("armed", "confirm")) and not os.path.exists(os.path.join(tmp, "auto_resume.json"))
              and L50 not in {x["name"] for x in NA.candidates(nt, state)} and NEW50 not in {x["name"] for x in NA.candidates(nt, state)}
              and "live phrase" in r["say"], (r, cfg))
        r_bl = NA.use(NEW25, "blitz", path=state, folder=nt)
        got = []
        NA.ROLE_SETTERS["blitz"] = lambda name: (got.append(name), {"ok": True})[1]
        try:
            r_bl2 = NA.use(NEW25, "blitz", path=state, folder=nt)
        finally:
            NA.ROLE_SETTERS.pop("blitz", None)
        check("Use for BLITZ: refused until BLITZ's slot registers its setter, then handed to it (the Name only)",
              not r_bl["ok"] and r_bl2["ok"] and got == [NEW25], (r_bl, r_bl2))
        d = NA.dismiss(FUNDED, path=state)
        check("Not for the bot: the Name is never offered again", d["ok"] and FUNDED not in {x["name"] for x in NA.candidates(nt, state)})
        # the Start page API: the block in status, the tap PC-only
        NA.STATE_PATH = state
        open(state, "w").write("{}")
        G._save({"lit": L50, "atlas": L25})
        S._bot = lambda: SimpleNamespace(running=False, cfg={})
        app = FastAPI()
        app.include_router(S.router)
        local = TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50001))
        phone = TestClient(app, base_url="http://192.168.1.20:8766", client=("192.168.1.50", 50003))
        rp = phone.post("/api/next/start/newacct", json={"name": NEW25, "role": "atlas"})
        rl = local.post("/api/next/start/newacct", json={"name": NEW25, "role": "atlas"})
        check("API: the tap from the phone is refused (403, PC only); from the PC it sets ATLAS's 25K Name",
              rp.status_code == 403 and rl.status_code == 200 and json.load(open(G.CFG)).get("atlas") == NEW25, (rp.text, rl.text))
        from engine import cloud_guard
        check("the tap is in cloud_guard's blocked list (never from the cloud dashboard)", "/api/next/start/newacct" in cloud_guard.CLOUD_BLOCKED)
        js = open(os.path.join(ROOT, "web_next", "js", "next", "start.js"), encoding="utf-8").read()
        check("Start page: one line per new Name in its own function (newAcctLine / wireNewAcct), confirm before the tap, "
              "'Not for the bot', no arming", "function newAcctLine(d)" in js and "function wireNewAcct(el)" in js
              and "data-na-use" in js and "Not for the bot" in js and "post('newacct'" in js and "post('arm'" not in js.split("function newAcctLine")[1].split("function draw")[0])
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        NA.STATE_PATH = os.path.join(ROOT, "data", "new_accounts.json")
        if env_keep is None:
            os.environ.pop("NINJATRADER_FOLDER", None)
        else:
            os.environ["NINJATRADER_FOLDER"] = env_keep
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"new accounts: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
