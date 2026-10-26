"""START BOT (engine/go.py, 2026-10-26): names asked once, done steps skipped, market-closed stop, nothing armed without
the typed phrase, NINJATRADER_LIVE written once, a running bot left alone. Every outside call is faked.

  python -X utf8 -m tests.test_go          # ~1 s, nothing written outside temp dirs, no server, no NinjaTrader
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import go as G  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:300]}"), flush=True)


class World:
    """Fakes for every outside effect of engine.go.run."""

    def __init__(self, tmp, running=False, server=False, sims=(False, False), market=True, prep_rc=0, sim_rc=0, start_rc=0):
        self.calls = []
        self.running, self.server, self.sims, self.market = running, server, dict(zip(("roundtrip", "add"), sims)), market
        self.prep_rc, self.sim_rc, self.start_rc = prep_rc, sim_rc, start_rc
        self.direct_ok = False
        G.CFG = os.path.join(tmp, "start_bot.json")
        G.AUTOSTART = os.path.join(tmp, "autostart.json")
        G.ENV_FILE = os.path.join(tmp, ".env.local.ps1")
        G.SUP_PID = os.path.join(tmp, "supervisor.pid")
        G.bot_running = lambda: self.running
        G.server_up = lambda: self.server
        G.server_stale = lambda: self.stale                    # the running server's code vs this folder (go.server_stale)
        self.stale = False
        G.migrate = lambda: {"status": "clean"}                # never the real second_model.json (engine/account_b.migrate_local)
        G.market_open = lambda now=None: self.market
        G.sims_passed = lambda: dict(self.sims)
        G.stop_server = lambda: (self.calls.append("stop_server"), setattr(self, "server", False))
        G.start_server = lambda wait_s=120: (self.calls.append("start_server"), setattr(self, "server", True))[1] or True
        G.checklist_lines = lambda: (["  [OK] all"], 0)
        G._open = lambda: self.calls.append("open")
        G.shortcut = lambda: None
        G.mixup = lambda lit, atlas, balances=None: None
        G.verify_routes = lambda lit, atlas, state=None, b=None: (self.calls.append("verify"), list(self.route_probs))[1]
        self.route_probs = []
        G.startup_shortcuts = lambda: self.calls.append("startup")
        G.ensure_feed = lambda: (self.calls.append("feed"), self.feed)[1]
        self.feed = True
        G.ensure_ninjatrader = lambda: (self.calls.append("nt"), self.nt)[1]
        self.nt = True
        G.arm_b = lambda atlas, path=None, selftest=None: (self.calls.append(("arm_b", atlas)), {"ok": True})[1]
        G.time.sleep = lambda s: None
        world = self

        class _Proc:
            def __init__(self, rc):
                self.returncode = rc

        def fake_run(cmd, cwd=None, **k):
            flag = next((c for c in cmd if c in ("--sim-roundtrip", "--sim-roundtrip-add")), None)
            world.calls.append(" ".join(cmd[-1:]) if not flag else flag + (" direct" if "direct" in cmd else ""))
            if flag:
                rc = world.sim_rc if not ("direct" in cmd and world.direct_ok) else 0
                if not rc:
                    world.sims["add" if flag.endswith("add") else "roundtrip"] = True
                return _Proc(rc)
            return _Proc(0)
        G.subprocess.run = fake_run
        import engine.launch_prep as LP
        import engine.ninjatrader as NT
        LP.main = lambda argv: (self.calls.append(("prep", tuple(argv))), self.prep_rc)[1]
        NT.main = lambda argv: (self.calls.append(("start", tuple(argv))), self.start_rc)[1]


def answers(*xs):
    it = iter(xs)
    return lambda prompt="": next(it, "")


def main():
    real_run = G.subprocess.run
    try:
        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp)
            rc = G.run(inp=answers("MFFU50K-1", "MFFU25K-2", "I ACCEPT LIVE RISK"), pull=False)
            check("first run: rc 0", rc == 0, rc)
            check("first run: launch_prep with both names",
                  any(isinstance(c, tuple) and c[0] == "prep" and c[1][:4] == ("--atlas", "MFFU25K-2", "--lit", "MFFU50K-1") and c[1][4] == "--atlas-start" for c in w.calls), w.calls)
            check("first run: both Sim roundtrips ran, in order",
                  [c for c in w.calls if isinstance(c, str) and c.startswith("--sim")] == ["--sim-roundtrip", "--sim-roundtrip-add"], w.calls)
            check("first run: bot started on the 50K with the typed phrase",
                  ("start", ("--start", "--account", "MFFU50K-1", "--confirm", "I ACCEPT LIVE RISK")) in w.calls, w.calls)
            check("first run: the 25K armed before the start",
                  ("arm_b", "MFFU25K-2") in w.calls and w.calls.index(("arm_b", "MFFU25K-2")) < [i for i, c in enumerate(w.calls) if isinstance(c, tuple) and c[0] == "start"][0], w.calls)
            check("first run: auto-resume on with the typed phrase after the start",
                  ("start", ("--enable-auto-resume", "--account", "MFFU50K-1", "--confirm", "I ACCEPT LIVE RISK")) in w.calls
                  and "startup" in w.calls, w.calls)
            check("first run: NinjaTrader checked before the Sim test",
                  w.calls.index("nt") < w.calls.index("--sim-roundtrip"), w.calls)
            check("first run: NINJATRADER_LIVE written", G.env_has_live(), open(G.ENV_FILE).read())
            check("first run: server started after the live line", "start_server" in w.calls, w.calls)
            cfg = G._read(G.CFG)
            check("names + prepped kept", cfg.get("lit") == "MFFU50K-1" and cfg.get("atlas") == "MFFU25K-2" and cfg.get("prepped"), cfg)

            # second run: nothing asked but the phrase; no prep, no sims, the live line not doubled
            w2 = World(tmp, sims=(True, True))
            rc = G.run(inp=answers("I ACCEPT LIVE RISK"), pull=False)
            check("second run: rc 0", rc == 0, rc)
            check("second run: no prep, no Sim test",
                  not any(isinstance(c, tuple) and c[0] == "prep" for c in w2.calls)
                  and not any(isinstance(c, str) and c.startswith("--sim") for c in w2.calls), w2.calls)
            check("second run: live line once", open(G.ENV_FILE).read().count("NINJATRADER_LIVE") == 1)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp)
            rc = G.run(inp=answers("A", "B", "i accept  live risk "), pull=False)
            check("phrase in small letters counts (the exact phrase is passed on)",
                  rc == 0 and ("start", ("--start", "--account", "A", "--confirm", "I ACCEPT LIVE RISK")) in w.calls, w.calls)
        check("typed_phrase: other words refused", G.typed_phrase("I accept risk") != G.LIVE_PHRASE and G.typed_phrase("") == "")

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp)
            rc = G.run(inp=answers("A", "B", "yes"), pull=False)
            check("wrong phrase: rc 1, never started", rc == 1 and not any(isinstance(c, tuple) and c[0] == "start" for c in w.calls), w.calls)
            check("wrong phrase: NINJATRADER_LIVE not written, 25K not armed",
                  not G.env_has_live() and not any(isinstance(c, tuple) and c[0] == "arm_b" for c in w.calls), w.calls)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp, market=False)
            rc = G.run(inp=answers("A", "B", "I ACCEPT LIVE RISK"), pull=False)
            check("market closed: stops before the Sim test, never started",
                  rc == 1 and not any(isinstance(c, tuple) and c[0] == "start" for c in w.calls), w.calls)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp)
            w.nt = False
            rc = G.run(inp=answers("A", "B", "I ACCEPT LIVE RISK"), pull=False)
            check("NinjaTrader not connected: stops, no Sim test, never started",
                  rc == 1 and not any(isinstance(c, str) and c.startswith("--sim") for c in w.calls)
                  and not any(isinstance(c, tuple) and c[0] == "start" for c in w.calls), w.calls)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp, sim_rc=1)
            rc = G.run(inp=answers("A", "B", "I ACCEPT LIVE RISK"), pull=False)
            check("Sim test fails: stops, never started", rc == 1 and not any(isinstance(c, tuple) and c[0] == "start" for c in w.calls), w.calls)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp, sim_rc=1)
            w.direct_ok = True
            rc = G.run(inp=answers("A", "B", "I ACCEPT LIVE RISK"), pull=False)
            st = [c for c in w.calls if isinstance(c, tuple) and c[0] == "start" and c[1][0] == "--start"]
            check("move mode fails, direct works: remembered and the bot starts with --write-mode direct",
                  rc == 0 and G._read(G.CFG).get("write_mode") == "direct" and st and st[0][1][-2:] == ("--write-mode", "direct")
                  and "--sim-roundtrip-add" not in w.calls and "--sim-roundtrip-add direct" in w.calls, w.calls)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp, server=True)
            rc = G.run(inp=answers("A", "B", "I ACCEPT LIVE RISK"), pull=False)
            check("server running without the live line: stopped for the Sim test and started again with it",
                  rc == 0 and "stop_server" in w.calls and w.calls.index("start_server") > w.calls.index("stop_server"), w.calls)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp, running=True)
            rc = G.run(inp=answers("A", "B"), pull=False)
            check("bot already running: left alone, dashboard opened",
                  rc == 0 and w.calls == ["open"], w.calls)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp)
            rc = G.run(inp=answers("SAME", "SAME"), pull=False)
            check("same name twice: refused", rc == 1 and not w.calls, w.calls)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp)
            with open(G.AUTOSTART, "w") as fh:
                fh.write('{"nt_account": "FROM-AUTOSTART"}')
            G.run(inp=answers("", "B", "no"), pull=False)
            check("50K name defaults to autostart.json", G._read(G.CFG).get("lit") == "FROM-AUTOSTART", G._read(G.CFG))

        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "e.ps1")
            with open(p, "w") as fh:
                fh.write("$env:LE_HEARTBEAT = '1'")                  # no trailing newline
            G.add_env_live(p)
            txt = open(p).read()
            check("live line on its own line", G.env_has_live(p) and txt.splitlines() == ["$env:LE_HEARTBEAT = '1'", G.LIVE_LINE], repr(txt))

        # arm_b on a copy of the real second_model.json: only "armed" changes, other fields kept; wrong name refused
        import importlib
        import json
        import shutil
        g3 = importlib.reload(G)
        from engine import account_b as AB, second as SE
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "second_model.json")
            shutil.copy(SE.CFG_PATH, p)
            ok = lambda: (True, "selftest faked")  # noqa: E731
            shipped = open(p, encoding="utf-8").read()
            r0 = AB.set_account_b("MFFU25K-2", plan="builder25k", start="2026-10-26", path=p, selftest=ok,
                                  extra={"prior_pnl": -50.0})
            before, bb = json.load(open(p)), AB.raw_cfg(p)
            r = g3.arm_b("MFFU25K-2", path=p, selftest=ok)
            after = json.load(open(p))
            ab = AB.raw_cfg(p) or {}
            check("arm_b: armed true", r0.get("ok") and r.get("ok") and ab.get("armed") is True, (r0, r, ab))
            check("arm_b: other fields kept", {k: v for k, v in ab.items() if k != "armed"} == bb, (ab, bb))
            check("arm_b: strategies untouched", after["strategies"] == before["strategies"])
            check("arm_b: written to the local data/account_b.json only (second_model.json byte for byte as shipped)",
                  open(p, encoding="utf-8").read() == shipped and AB.read_local(p)[1] == ab, AB.local_path(p))
            check("arm_b: twice = no change", g3.arm_b("MFFU25K-2", path=p, selftest=ok).get("already") is True)
            check("arm_b: another name refused", g3.arm_b("OTHER", path=p, selftest=ok).get("ok") is False)
            check("arm_b: spec reads armed", AB.normalize(ab, SE.load_cfg(p)).get("armed") is True)

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp)
            w.route_probs = ["ATLAS is on 'X'"]
            rc = G.run(inp=answers("A", "B", "I ACCEPT LIVE RISK"), pull=False)
            check("routes wrong after the start: bot stopped, no auto-resume",
                  rc == 1 and ("start", ("--stop",)) in w.calls
                  and not any(isinstance(c, tuple) and c[1][:1] == ("--enable-auto-resume",) for c in w.calls), w.calls)

        g3 = importlib.reload(G)
        M = g3.mixup
        check("mixup: fine names", M("MFFUEV50K123", "MFFUEV25K456", balances={}) is None)
        check("mixup: plain ids fine", M("MFFUEVA1", "MFFUEVB2", balances={}) is None)
        check("mixup: swapped by name", M("MFFU25K-1", "MFFU50K-2", balances={}) is not None)
        check("mixup: Sim refused", M("Sim101", "MFFU25K", balances={}) is not None)
        check("mixup: 50K slot with $25k balance", M("A", "B", balances={"A": 25000.0, "B": 49710.8}) is not None)
        check("mixup: 25K slot with $49k balance", M("A", "B", balances={"B": 49710.8}) is not None)
        check("mixup: right balances", M("A", "B", balances={"A": 49710.8, "B": 25000.0}) is None)
        V = g3.verify_routes
        okst = {"running": True, "cfg": {"nt_account": "A", "adapter": "ninjatrader"}}
        okb = {"account": "B", "plan": "builder25k", "armed": True}
        check("verify: right", V("A", "B", state=okst, b=okb) == [])
        check("verify: Zlarior on the 25K", V("B", "A", state={"running": True, "cfg": {"nt_account": "B", "adapter": "ninjatrader"}}, b=okb) != [])
        check("verify: ATLAS not armed", V("A", "B", state=okst, b={**okb, "armed": False}) != [])
        check("verify: ATLAS on a 50K plan", V("A", "B", state=okst, b={**okb, "plan": "builder50k"}) != [])
        check("verify: 25K also an extra Zlarior account", V("A", "B", state={"running": True, "cfg": {"nt_account": "A", "adapter": "ninjatrader", "accounts": [{"id": "x", "nt_account": "B"}]}}, b=okb) != [])
        check("verify: not running", V("A", "B", state={**okst, "running": False}, b=okb) != [])

        with tempfile.TemporaryDirectory() as tmp:
            w = World(tmp)
            w.feed = False
            rc = G.run(inp=answers("A", "B", "I ACCEPT LIVE RISK"), pull=False)
            check("no live bars: stops before the Sim test, never started",
                  rc == 1 and "feed" in w.calls and not any(isinstance(c, str) and c.startswith("--sim") for c in w.calls)
                  and not any(isinstance(c, tuple) and c[0] == "start" for c in w.calls), w.calls)
        g3 = importlib.reload(G)
        fs = iter(["stale", "stale", None])
        check("ensure_feed: waits for fresh bars", g3.ensure_feed(wait_s=60, problem=lambda: next(fs), sleep=lambda s: None))
        check("ensure_feed: gives up", not g3.ensure_feed(wait_s=0.01, problem=lambda: "stale", sleep=lambda s: None))

        seq = iter([None, False, True])
        check("ensure_ninjatrader: waits for CONNECTED", g3.ensure_ninjatrader(wait_s=60, connected=lambda: next(seq), sleep=lambda s: None))
        check("ensure_ninjatrader: gives up", not g3.ensure_ninjatrader(wait_s=0.01, connected=lambda: False, sleep=lambda s: None))

        mk = lambda *a: dt.datetime(*a, tzinfo=ET)  # noqa: E731
        import importlib
        g2 = importlib.reload(G)
        check("market: Sun 18:30 open", g2.market_open(mk(2026, 10, 25, 18, 30)))
        check("market: Sun 17:30 closed", not g2.market_open(mk(2026, 10, 25, 17, 30)))
        check("market: Mon 17:15 halt", not g2.market_open(mk(2026, 10, 26, 17, 15)))
        check("market: Tue 02:00 open", g2.market_open(mk(2026, 10, 27, 2, 0)))
        check("market: Fri 17:05 closed", not g2.market_open(mk(2026, 10, 30, 17, 5)))
        check("session: Sun 21:00 -> Mon", g2.session_day(mk(2026, 10, 25, 21, 0)) == "2026-10-26")
        check("session: Mon 10:00 -> Mon", g2.session_day(mk(2026, 10, 26, 10, 0)) == "2026-10-26")
        check("session: Mon 19:00 -> Tue", g2.session_day(mk(2026, 10, 26, 19, 0)) == "2026-10-27")
        check("session: Fri 18:30 -> Mon", g2.session_day(mk(2026, 10, 30, 18, 30)) == "2026-11-02")
        check("market: Sat closed", not g2.market_open(mk(2026, 10, 31, 12, 0)))
    finally:
        G.subprocess.run = real_run
    n = sum(RES)
    print(f"start bot: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
