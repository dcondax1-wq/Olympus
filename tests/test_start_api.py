"""Start & Accounts page (engine/start_api.py + engine/go.py steps, web_next/js/next/start.js): the checklist, the account
panel, the step jobs, and that the phone / cloud / a proxy / another site can never arm, start or change an account.
Every file it writes is in a temp dir (go.CFG, ENV_FILE, SECOND_PATH, ALLOW_PATH, ACCOUNTS_PATH, ANCHOR_PATH, JOB_*), the
NinjaTrader folder is a temp one, launch prep / the server / NinjaTrader / the Sim test are faked; at the end it checks
that the real .env.local.ps1, data/ files and second_model.json did not change.

  python -X utf8 -m tests.test_start_api        # ~5 s
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from engine import account_b as AB, cloud_guard as CG, go as G, second as SE, start_api as S  # noqa: E402

RES = []
PHRASE = "I ACCEPT LIVE RISK"
L50, L25, FUND = "MFFUEV50K1", "MFFUEV25K2", "MFFUFUNDED9"
REAL = [os.path.join(ROOT, p) for p in (".env.local.ps1", "second_model.json", "data/start_bot.json", "data/accounts.json",
                                         "data/nt_accounts_allow.json", "data/eval_anchor.json", "data/autostart.json",
                                         "data/sim_roundtrip_last.json", "logs/start_job.json", "logs/start_job.log")]


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


class World:
    def __init__(self, tmp):
        self.tmp, self.calls, self.popen = tmp, [], []
        self.sims = {"roundtrip": False, "add": False}
        self.market, self.running, self.server = True, False, False
        self.bot = SimpleNamespace(running=False, cfg={})
        G.CFG = os.path.join(tmp, "start_bot.json")
        G.AUTOSTART = os.path.join(tmp, "autostart.json")
        G.ENV_FILE = os.path.join(tmp, ".env.local.ps1")
        G.SUP_PID = os.path.join(tmp, "supervisor.pid")
        G.SECOND_PATH = os.path.join(tmp, "second_model.json")
        shutil.copy(SE.CFG_PATH, G.SECOND_PATH)
        AB.set_account_b(None, path=G.SECOND_PATH)              # the copy starts with account B off
        G.ALLOW_PATH = os.path.join(tmp, "allow.json")
        G.ACCOUNTS_PATH = os.path.join(tmp, "accounts.json")
        G.ANCHOR_PATH = os.path.join(tmp, "eval_anchor.json")
        G.JOB_FILE = os.path.join(tmp, "logs", "start_job.json")
        G.JOB_LOG = os.path.join(tmp, "logs", "start_job.log")
        G.sims_passed = lambda: dict(self.sims)
        G.market_open = lambda now=None: self.market
        G.server_up = lambda: self.server
        G.stop_server = lambda: (self.calls.append("stop_server"), setattr(self, "server", False))
        G.start_server = lambda wait_s=120: (self.calls.append("start_server"), setattr(self, "server", True))[1] or True
        G.startup_shortcuts = lambda: self.calls.append("startup")
        G.shortcut = lambda: None
        G._open = lambda: self.calls.append("open")
        G.checklist_lines = lambda: (["  [OK] all"], 0)
        G.time.sleep = lambda s: None
        G.POPEN = lambda cmd, **k: self.popen.append((cmd, k))
        SE._selftest_ok = lambda timeout=600: (True, "selftest faked")
        S._bot = lambda: self.bot
        S._connected = lambda: True
        self.feed = None
        G.feed_problem = lambda: self.feed
        S._feed = lambda: self.feed
        import engine.launch_prep as LP
        import engine.ninjatrader as NT

        def prep(argv):                                      # what launch_prep does, on the temp files
            a = dict(zip(argv[::2], argv[1::2]))
            self.calls.append(("prep", tuple(argv)))
            G._allow(a["--lit"])
            G._allow(a["--atlas"])
            r = AB.set_account_b(a["--atlas"], plan="builder25k", start=a.get("--atlas-start"), path=G.SECOND_PATH)
            return 0 if r.get("ok") else 1
        LP.main = prep
        NT.main = lambda argv: (self.calls.append(("nt", tuple(argv))), 0)[1]
        # a NinjaTrader folder: LE_BarFeed's accounts.csv (50K, 25K, Sim101) and a position file of a funded account
        nt = os.path.join(tmp, "NinjaTrader 8")
        os.makedirs(os.path.join(nt, "le_feed"))
        os.makedirs(os.path.join(nt, "outgoing"))
        now = int(time.time())
        with open(os.path.join(nt, "le_feed", "accounts.csv"), "w") as fh:
            fh.write("name,time,cash,realized,unrealized,netliq\n"
                     f"{L50},{now},49710.80,0,0,49710.80\n{L25},{now},25000,0,0,25000\nSim101,{now},100000,0,0,100000\n")
        open(os.path.join(nt, "outgoing", f"MNQ DEC26 Globex_{FUND}_Position.txt"), "w").write("LONG;1;25000")
        open(os.path.join(nt, "outgoing", "MNQ DEC26 Globex_Sim101_Position.txt"), "w").write("FLAT;0;0")
        os.environ["NINJATRADER_FOLDER"] = nt


def clients():
    app = FastAPI()
    app.include_router(S.router)
    return {
        "local": TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50001)),
        "localhost": TestClient(app, base_url="http://localhost:8766", client=("::1", 50002)),
        "phone": TestClient(app, base_url="http://192.168.1.20:8766", client=("192.168.1.50", 50003)),
        "tailscale": TestClient(app, base_url="http://100.101.102.103:8766", client=("100.64.0.7", 50004)),
        "default": TestClient(app),                                                  # host "testclient"
        "tunnel": TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50005),
                             headers={"X-Forwarded-For": "203.0.113.9"}),
        "rebind": TestClient(app, base_url="http://evil.example:8766", client=("127.0.0.1", 50006)),
        "origin": TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50007),
                             headers={"Origin": "http://evil.example"}),
    }, app


BODIES = {"names": {"lit": L50, "atlas": L25}, "nt": {}, "setup": {}, "sims": {}, "arm": {"confirm": PHRASE},
          "accounts/add": {"name": "MFFUEV25K3", "plan": "builder25k", "strategy": "zlarior"},
          "accounts/remove": {"name": L50}, "accounts/anchor": {"name": L50, "balance": 49800, "floor": 48200, "as_of": "2026-10-23"},
          "accounts/funded": {"name": L50, "funded_name": FUND, "start": "2026-11-02"}}


def tmp_files(w):
    return [G.CFG, G.ENV_FILE, G.SECOND_PATH, G.ALLOW_PATH, G.ACCOUNTS_PATH, G.ANCHOR_PATH, G.JOB_FILE, G.JOB_LOG]


def main():
    real_before = digest(REAL)
    env0 = {k: os.environ.get(k) for k in ("NINJATRADER_FOLDER", "LE_CLOUD", "LE_DASH_PASSWORD", "LE_PAPER_AUTOSTART")}
    with tempfile.TemporaryDirectory() as tmp:
        w = World(tmp)
        C, app = clients()

        # ---------------------------------------------------------------- the guard: every write refused off this PC
        routes = sorted(r.path for r in S.router.routes if "POST" in getattr(r, "methods", set()))
        check("every POST route is a START write", set(routes) == set(CG.START_WRITES), routes)
        check("every START write is CLOUD_BLOCKED", all(p in CG.CLOUD_BLOCKED for p in CG.START_WRITES))
        check("the old blocked routes stay blocked", all(p in CG.CLOUD_BLOCKED for p in ("/api/live/arm", "/api/live/golive", "/api/launch/test_webhook")))
        before = digest(tmp_files(w))
        for who in ("phone", "tailscale", "default", "tunnel", "rebind", "origin"):
            codes = {p: C[who].post("/api/next/start/" + p, json=BODIES[p]).status_code for p in BODIES}
            check(f"{who}: every write refused (403)", all(c == 403 for c in codes.values()), codes)
        check("refused writes changed nothing (no file, no job, no NinjaTrader, no prep)",
              digest(tmp_files(w)) == before and not w.popen and not w.calls, (w.calls, w.popen))
        r = C["phone"].get("/api/next/start/status")
        d = r.json()
        check("phone: status readable, local false", r.status_code == 200 and d.get("local") is False, r.text[:200])
        check("status: 7 lines in order", [s["key"] for s in d["steps"]] == ["nt", "feed", "accounts", "setup", "sims", "armed", "running"], d.get("steps"))
        check("status: no phrase typed by the bot (job empty, nothing armed)", "not armed" in d["say"] and d["job"]["step"] is None, d["say"])
        r = C["local"].get("/api/next/start/status")
        check("local: status local true", r.json().get("local") is True)
        check("localhost (::1): local true", C["localhost"].get("/api/next/start/status").json().get("local") is True)

        # cloud mode: local_only refuses even 127.0.0.1, and the cloud middleware 403s the paths
        os.environ["LE_CLOUD"] = "1"
        r = C["local"].post("/api/next/start/names", json=BODIES["names"])
        check("LE_CLOUD=1: local request refused too", r.status_code == 403 and "cloud" in r.json().get("error", ""), r.text)
        os.environ.update(LE_DASH_PASSWORD="x" * 16, LE_PAPER_AUTOSTART="0")
        from engine.live import BOT
        start0 = BOT.start
        try:
            capp = FastAPI()
            CG.install(capp)
            capp.include_router(S.router)
            cc = TestClient(capp, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50008), headers={"Authorization": "Basic " + __import__("base64").b64encode(b"u:" + b"x" * 16).decode()})
            codes = {p: cc.post("/api/next/start/" + p, json=BODIES[p]).status_code for p in BODIES}
            check("cloud middleware: every START write 403", all(c == 403 for c in codes.values()), codes)
        finally:
            BOT.start = start0
            for k in ("LE_CLOUD", "LE_DASH_PASSWORD", "LE_PAPER_AUTOSTART"):
                os.environ.pop(k, None)
        check("cloud: still nothing changed", digest(tmp_files(w)) == before and not w.popen and not w.calls, w.calls)

        L = C["local"]
        post = lambda p, body=None: L.post("/api/next/start/" + p, json=body if body is not None else BODIES.get(p, {}))  # noqa: E731
        # ---------------------------------------------------------------- names (START BOT's mix-up checks)
        check("names: swapped by balance refused", post("names", {"lit": L25, "atlas": L50}).status_code == 400)
        check("names: the same account twice refused", "both" in post("names", {"lit": L50, "atlas": L50}).json().get("error", ""))
        check("names: Sim101 refused", post("names", {"lit": "Sim101", "atlas": L25}).status_code == 400)
        check("names: a name saying 25K in the 50K slot refused", post("names", {"lit": "MFFU25K-9", "atlas": "MFFU-B"}).status_code == 400)
        w.bot.running = True
        check("names: refused while the bot runs", post("names").status_code == 400)
        w.bot.running = False
        r = post("names")
        check("names: saved", r.status_code == 200 and G._read(G.CFG).get("lit") == L50 and G._read(G.CFG).get("atlas") == L25, r.text)
        d = L.get("/api/next/start/status").json()
        st = {s["key"]: s for s in d["steps"]}
        check("status: accounts line green, setup red with its button", st["accounts"]["done"] and not st["setup"]["done"]
              and st["setup"]["ready"] and st["setup"]["action"] == "setup", st)
        check("status: say = Zlarior -> 50K / ATLAS -> 25K", d["say"].startswith(f"Zlarior → 50K {L50} · ATLAS → 25K {L25}"), d["say"])
        picks = [p["name"] for p in d["accounts"]["picks"]]
        check("pick list from NinjaTrader (accounts.csv + outgoing), no Sim", set(picks) == {L50, L25, FUND}, picks)

        # ---------------------------------------------------------------- setup, NinjaTrader
        r = post("setup")
        check("setup: launch prep ran with both names", r.status_code == 200 and any(c[0] == "prep" and c[1][:4] == ("--atlas", L25, "--lit", L50)
                                                                                      for c in w.calls if isinstance(c, tuple)), (r.text, w.calls))
        st = {s["key"]: s for s in L.get("/api/next/start/status").json()["steps"]}
        check("status: setup green (prepped, both allowlisted, ATLAS on the 25K)", st["setup"]["done"], st["setup"])
        check("status: sims red, ready (NinjaTrader connected)", not st["sims"]["done"] and st["sims"]["ready"], st["sims"])
        check("status: armed not ready before the Sim test", not st["armed"]["ready"] and st["armed"]["first"] == "Sim tests passed", st["armed"])
        r = post("nt")
        check("nt: answers (no wait)", r.status_code == 200 and "connected" in r.json(), r.text)

        # ---------------------------------------------------------------- live bars (LE_BarFeed), then the Sim test job
        w.feed = "the newest bar is 42 min old"
        st = {s["key"]: s for s in L.get("/api/next/start/status").json()["steps"]}
        check("feed: stale bars -> red line with the chart fix, Sim test not ready", not st["feed"]["done"] and "Reload NinjaScript" in st["feed"]["detail"]
              and st["feed"]["button"] == "Check again" and not st["sims"]["ready"] and st["sims"]["first"] == "Live bars from NinjaTrader", st["feed"])
        check("feed: Sim test job refused while the bars are stale", post("sims").status_code == 400 and not w.popen)
        check("feed: fresh=1 answers", L.get("/api/next/start/status?fresh=1").status_code == 200)
        w.feed = None
        check("feed: fresh -> green", {s["key"]: s for s in L.get("/api/next/start/status").json()["steps"]}["feed"]["done"])
        w.market = False
        check("sims: refused with the market closed", post("sims").status_code == 400 and not w.popen)
        w.market = True
        r = post("sims")
        cmd, kw = w.popen[-1] if w.popen else ([], {})
        check("sims: a job started (python -m engine.go --step sims)", r.status_code == 200 and cmd[-2:] == ["--step", "sims"], (r.text, cmd))
        check("sims: no phrase in its environment", "LE_START_CONFIRM" not in (kw.get("env") or {}))
        check("sims: a second one refused while it runs", post("sims").status_code == 400 and len(w.popen) == 1)
        w.server = True
        real_run = G.subprocess.run

        def fake_run(cmd, cwd=None, **k):                   # the Sim roundtrips need NinjaTrader: faked
            flag = next(c for c in cmd if c.startswith("--sim"))
            direct = "--write-mode" in cmd and cmd[cmd.index("--write-mode") + 1] == "direct"
            w.calls.append(flag + (" direct" if direct else ""))
            if not direct:                                   # this "PC" ignores files moved into incoming (the Surface)
                return SimpleNamespace(returncode=1)
            w.sims["add" if flag.endswith("add") else "roundtrip"] = True
            return SimpleNamespace(returncode=0)
        G.subprocess.run = fake_run
        try:
            rc = G.job_main("sims")
        finally:
            G.subprocess.run = real_run
        check("sims job: server stopped, move mode failed -> retried direct, then direct for the 2nd test, server started again",
              rc == 0 and [c for c in w.calls if isinstance(c, str)] == ["stop_server", "--sim-roundtrip", "--sim-roundtrip direct",
                                                                         "--sim-roundtrip-add direct", "start_server"]
              and all(w.sims.values()), (rc, w.calls))
        check("sims job: write_mode direct kept in the temp start_bot.json (names kept)", G._read(G.CFG).get("write_mode") == "direct"
              and G._read(G.CFG).get("lit") == L50, G._read(G.CFG))
        js = G.job_status()
        check("job status: done, rc 0, lines", js["state"] == "done" and js["rc"] == 0 and js["lines"], js)

        # ---------------------------------------------------------------- arm (typed phrase only)
        n0 = len(w.popen)
        for bad in ("", "i accept live risk", "I ACCEPT LIVE RISK ", "yes"):
            r = post("arm", {"confirm": bad})
            check(f"arm: {bad!r} refused, nothing started", r.status_code == 400 and len(w.popen) == n0 and not G.env_has_live(), r.text)
        w.sims.update(add=False)
        check("arm: refused before both Sim tests passed", post("arm").status_code == 400 and len(w.popen) == n0)
        w.sims.update(add=True)
        w.bot.running = True
        check("arm: refused while a bot runs", post("arm").status_code == 400 and len(w.popen) == n0)
        w.bot.running = False
        r = post("arm")
        cmd, kw = w.popen[-1]
        check("arm: job started with the phrase in its environment, not on its command line",
              r.status_code == 200 and cmd[-2:] == ["--step", "arm"] and kw["env"].get("LE_START_CONFIRM") == PHRASE
              and not any(PHRASE in str(c) for c in cmd), (r.text, cmd))
        check("arm: the endpoint itself wrote nothing live", not G.env_has_live() and AB.raw_cfg(G.SECOND_PATH).get("armed") is not True)
        os.environ["LE_START_CONFIRM"] = PHRASE
        vr = G.verify_routes
        G.verify_routes = lambda lit, atlas, state=None, b=None: []
        w.calls.clear()
        rc = G.job_main("arm")
        G.verify_routes = vr
        check("arm job: rc 0, live line in the temp env file, 25K armed in the temp second_model.json",
              rc == 0 and G.env_has_live() and AB.raw_cfg(G.SECOND_PATH).get("armed") is True, (rc, w.calls))
        check("arm job: started on the 50K with the phrase and the saved write mode, auto-resume the same, no browser opened",
              ("nt", ("--start", "--account", L50, "--confirm", PHRASE, "--write-mode", "direct")) in w.calls
              and ("nt", ("--enable-auto-resume", "--account", L50, "--confirm", PHRASE, "--write-mode", "direct")) in w.calls
              and "open" not in w.calls, w.calls)
        check("arm job: the phrase left the environment", "LE_START_CONFIRM" not in os.environ)
        check("arm job: the log never shows the phrase", all(PHRASE not in ln for ln in G.job_status()["lines"]))
        w.bot.running, w.bot.cfg = True, {"nt_account": L50, "adapter": "ninjatrader", "armed": True}
        d = L.get("/api/next/start/status").json()
        check("status: all seven green", d["all_green"], [(s["key"], s["done"], s["detail"]) for s in d["steps"]])
        check("status: say", d["say"] == f"Zlarior → 50K {L50} · ATLAS → 25K {L25} · both armed · running", d["say"])
        w.bot.cfg = {"nt_account": L25, "adapter": "ninjatrader"}
        st = {s["key"]: s for s in L.get("/api/next/start/status").json()["steps"]}
        check("status: Zlarior on the 25K -> running line red, button Stop the bot", not st["running"]["done"]
              and st["running"]["action"] == "stop" and "not the 50K" in st["running"]["detail"], st["running"])

        # ---------------------------------------------------------------- the accounts panel
        w.bot.running, w.bot.cfg = False, {}
        rows = L.get("/api/next/start/status").json()["accounts"]["rows"]
        r50 = next((r for r in rows if r["name"] == L50), {})
        r25 = next((r for r in rows if r["name"] == L25), {})
        check("accounts: 50K Zlarior eval, balance from NinjaTrader", r50.get("bot") == "Zlarior" and r50.get("state") == "eval"
              and r50.get("balance") == 49710.8 and r50.get("source") == "NinjaTrader", r50)
        check("accounts: 25K ATLAS armed", r25.get("bot") == "ATLAS" and r25.get("armed") is True and r25.get("plan") == "builder25k", r25)
        add = lambda body: post("accounts/add", body)  # noqa: E731
        check("add: ATLAS on a second 25K refused (one account B)", add({"name": "MFFUEV25K3", "plan": "builder25k", "strategy": "atlas"}).status_code == 400)
        check("add: the 25K again for Zlarior refused (one bot per account)",
              "ATLAS" in add({"name": L25, "plan": "builder25k", "strategy": "zlarior"}).json().get("error", ""))
        check("add: the 50K for ATLAS refused", add({"name": L50, "plan": "builder25k", "strategy": "atlas"}).status_code == 400)
        check("add: Sim101 refused", add({"name": "Sim101", "plan": "builder50k", "strategy": "zlarior"}).status_code == 400)
        check("add: a 25K name as a 50K refused", add({"name": "MFFU25K-7", "plan": "builder50k", "strategy": "zlarior"}).status_code == 400)
        w.bot.running = True
        check("add: refused while the bot runs", add({"name": "MFFUEV25K3", "plan": "builder25k", "strategy": "zlarior"}).status_code == 400)
        w.bot.running = False
        r = add({"name": "MFFUEV25K3", "plan": "builder25k", "strategy": "zlarior", "start": "2026-10-27"})
        ex = json.load(open(G.ACCOUNTS_PATH))["accounts"] if os.path.exists(G.ACCOUNTS_PATH) else []
        check("add: extra Zlarior 25K in the temp accounts.json, disarmed, allowlisted",
              r.status_code == 200 and len(ex) == 1 and ex[0]["nt_account"] == "MFFUEV25K3" and ex[0]["preset"] == "mffu_builder_25k"
              and ex[0]["armed"] is False and ex[0]["eval_start"] == "2026-10-27" and "MFFUEV25K3" in G._allowed(), (r.text, ex))
        check("names: an extra account cannot become ATLAS's", post("names", {"lit": L50, "atlas": "MFFUEV25K3"}).status_code == 400)
        r = post("accounts/anchor", {"name": L50, "balance": 49800.5, "floor": 48200, "as_of": "2026-10-26"})
        anc = json.load(open(G.ANCHOR_PATH)).get("main") or {}
        check("anchor: the 50K's balance / floor / as of saved (main)", r.status_code == 200 and anc.get("balance") == 49800.5
              and anc.get("floor") == 48200 and anc.get("as_of") == "2026-10-26", (r.text, anc))
        check("anchor: a floor above the balance refused", post("accounts/anchor", {"name": L50, "balance": 100, "floor": 200, "as_of": "2026-10-26"}).status_code == 400)
        check("anchor: a bad day refused", post("accounts/anchor", {"name": L50, "balance": 1, "floor": 1, "as_of": "x"}).status_code == 400)
        check("funded: the 25K's Name as the funded account refused", post("accounts/funded", {"name": L50, "funded_name": L25, "start": "2026-11-02"}).status_code == 400)
        check("funded: an unknown source account refused", post("accounts/funded", {"name": "NOPE", "funded_name": FUND, "start": "2026-11-02"}).status_code == 400)
        r = post("accounts/funded")
        ex = {e["id"]: e for e in json.load(open(G.ACCOUNTS_PATH))["accounts"]}
        f = ex.get("mffu50k_funded") or {}
        check("funded: the funded 50K joins (mode funded, disarmed, from its first day)", r.status_code == 200 and f.get("mode") == "funded"
              and f.get("nt_account") == FUND and f.get("armed") is False and (f.get("funded") or {}).get("start") == "2026-11-02", (r.text, ex))
        rows = L.get("/api/next/start/status").json()["accounts"]["rows"]
        check("accounts: 4 rows, the funded one says funded", len(rows) == 4 and next(r for r in rows if r["name"] == FUND)["state"] == "funded", rows)
        check("remove: unknown refused", post("accounts/remove", {"name": "NOPE"}).status_code == 400)
        w.bot.running = True
        check("remove: refused while the bot runs", post("accounts/remove", {"name": "MFFUEV25K3"}).status_code == 400)
        w.bot.running = False
        r = post("accounts/remove", {"name": "MFFUEV25K3"})
        check("remove: extra account gone, off the allowlist", r.status_code == 200 and "MFFUEV25K3" not in G._allowed()
              and all(e.get("nt_account") != "MFFUEV25K3" for e in json.load(open(G.ACCOUNTS_PATH))["accounts"]), r.text)
        r = post("accounts/remove", {"name": L25})
        check("remove: ATLAS's 25K -> account B off, name cleared, off the allowlist",
              r.status_code == 200 and AB.raw_cfg(G.SECOND_PATH) is None and not G._read(G.CFG).get("atlas") and L25 not in G._allowed(), r.text)
        st = {s["key"]: s for s in L.get("/api/next/start/status").json()["steps"]}
        check("status: accounts line red again after the remove", not st["accounts"]["done"] and not st["setup"]["done"], st["accounts"])
        r = post("accounts/add", {"name": L25, "plan": "builder25k", "strategy": "atlas", "start": "2026-10-27"})
        b = AB.raw_cfg(G.SECOND_PATH) or {}
        check("add: ATLAS on the 25K again (account B, first session, not armed)", r.status_code == 200 and b.get("account") == L25
              and b.get("eval_start") == "2026-10-27" and b.get("armed") is not True and G._read(G.CFG).get("atlas") == L25, (r.text, b))

        # ---------------------------------------------------------------- the page wiring (static)
        rt = open(os.path.join(ROOT, "web_next/js/next/routes.js"), encoding="utf-8").read()
        app_js = open(os.path.join(ROOT, "web_next/js/app.js"), encoding="utf-8").read()
        idx = open(os.path.join(ROOT, "web_next/index.html"), encoding="utf-8").read()
        sw = open(os.path.join(ROOT, "web_next/sw.js"), encoding="utf-8").read()
        js = open(os.path.join(ROOT, "web_next/js/next/start.js"), encoding="utf-8").read()
        check("routes: Start in the sidebar's Main group", "ids: ['cc', 'start'," in rt and "id: 'start'" in rt)
        check("app.js: start page registered", "from './next/start.js'" in app_js and "start: startPage" in app_js)
        check("index.html: page section + stylesheet", 'id="page-start"' in idx and "/css/start.css" in idx)
        check("sw.js: shell cache bumped, start.css cached", "le-shell-next-v20" in sw and "/css/start.css" in sw)
        check("start.js: arm button enabled only by the exact phrase", "$('#stPhrase')?.value !== P.d?.phrase" in js)
        check("start.js: only /api/next/start/* and the existing stop are POSTed",
              js.count("fetch('/api/next/start/' + path") == 1 and "/api/live/arm" not in js and "/api/live/start" not in js)
    for k, v in env0.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    check("the real .env.local.ps1, data/ files, second_model.json and logs/start_job.* did not change", digest(REAL) == real_before,
          {p: (real_before[p], v) for p, v in digest(REAL).items() if real_before[p] != v})
    n = sum(RES)
    print(f"start api: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
