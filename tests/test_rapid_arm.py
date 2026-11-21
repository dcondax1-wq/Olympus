"""The Rapid arm bug (2026-11-21): an account added with ADD_ACCOUNT / the account box (data/rapid.json, data/rapid2.json, an
engine.accounts row) is added DISARMED; only START BOT / the Start page with the typed phrase may arm it, in the SAME run.

    python -X utf8 -m tests.test_rapid_arm        (temp files, a fake NINJATRADER_FOLDER, no server, nothing real; ~5 s)

The bug: STOP BOT clears only data/autostart.json, the auto-resume opt-in stays valid, so the Start page's "Start trading" took
the no-phrase resume path (engine/go.resume_now), which never arms; a typed phrase was ignored there too. The Rapid lane was
then refused by the NinjaTrader gate ("start config is not armed"), also after every auto-resume. And START BOT's arm step
restarted a stale server BEFORE arming: the fresh server resumed the bot from its record with the Rapid disarmed and the later
--start failed with "already running".
  a. a new Rapid (or an engine.accounts row) still disarmed -> "Start trading" asks for the phrase (status need_phrase, the
     Armed row red with the masked Name, resume_now refused with need=phrase, step_auto rc 3, nothing started)
  b. the phrase typed on the Start page -> step_arm arms the Rapid in this run and the started bot's Rapid lane passes the gate
  c. both Rapids (data/rapid2.json) disarmed -> asked, then both armed by the one phrase
  d. START BOT with a server restart that resumes the bot by itself -> armed BEFORE the restart, the bot restarted with the
     phrase; its own resume winning the race after --start -> stopped and started once more; rc 0
  e. the phrase typed but the Rapid could not be armed -> the page says NOT armed / NOT trading (never silent)
  f. everything armed -> no phrase needed again (the opt-in flow is kept); a Sim Rapid never asks
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_cli as AC, autoresume as AR, go as G, multi_account as MA, rapid  # noqa: E402
import engine.ninjatrader as NT  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402
from tests import test_accounts_cli as TC  # noqa: E402

RES = []
NR, NR2 = "MFFUEVRPD2500009021", "MFFUEVRPD500009022"         # made-up Rapid EOD 25K / 50K Names


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def gate(tmp, cfg_start, slot="rapid"):
    """What the bot's Rapid LIT lane adapter says at BOT.start(cfg_start): lane_spec of the Rapid file read NOW."""
    blk = rapid.read(rapid.slot_path(slot))
    spec = MA.normalize(rapid.lane_spec(blk, cfg_start or {}, slot=slot))
    cfg = {"adapter": "ninjatrader", "nt_account": spec["nt_account"], "armed": bool(spec.get("armed")),
           "confirm": spec.get("confirm") or "", "nt_state_path": os.path.join(tmp, f"nt_state_{slot}.json"),
           "nt_audit_log": os.path.join(tmp, "oif.log"), "nt_lock": False, "nt_allow_path": G.ALLOW_PATH}
    return NT.NinjaTraderAdapter(cfg, readonly=True).disabled


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="rapid_arm_")
    names = ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "JOB_FILE", "JOB_LOG", "_b", "env_has_live",
             "bot_running", "update", "migrate", "setup_missing", "feed_problem", "sims_passed", "server_up", "server_stale",
             "env_newer_than_server", "verify_routes", "_http", "arm_b", "start_server", "stop_server", "checklist_lines",
             "time", "startup_shortcuts", "shortcut", "arm_problem")
    keep = {k: getattr(G, k) for k in names}
    keep_mod = (rapid.PATH, rapid.PATH2, rapid.arm, AR.OPTIN_PATH, AR.nt_connected, NT.main, AC.resume_optin)
    env_keep = {k: os.environ.get(k) for k in ("NINJATRADER_FOLDER", "NINJATRADER_LIVE")}
    try:
        TC.world(tmp)
        rapid.PATH2 = None                                     # data/rapid2.json next to the temp rapid.json
        os.environ["NINJATRADER_LIVE"] = "1"                   # in-process only: the adapter's gate text; no server, no order
        AR.OPTIN_PATH = os.path.join(tmp, "auto_resume.json")
        G.JOB_FILE, G.JOB_LOG = os.path.join(tmp, "job.json"), os.path.join(tmp, "job.log")
        # the owner typed the phrase at an earlier START BOT: opt-in on for the 50K, ATLAS armed, the live switch on
        AR.enable(TC.L50, LIVE_PHRASE, {"adapter": "ninjatrader", "nt_account": TC.L50}, path=AR.OPTIN_PATH)
        G._b = lambda: {"account": TC.L25, "armed": True}
        G.env_has_live = lambda path=None: True
        check("f. before any new account: everything armed -> Start trading needs no phrase", G.resume_problem() is None,
              G.resume_problem())
        with contextlib.redirect_stdout(io.StringIO()):
            r = AC.add("rapideod25", NR)                       # ADD_ACCOUNT option 5
        check("a. ADD_ACCOUNT 5: the Rapid EOD 25K is added DISARMED", r.get("ok") and (rapid.read() or {}).get("armed") is False, r)
        why = G.resume_problem()
        check("a. resume_problem names it, masked to its last 4 (never the full Name)",
              why and "Rapid EOD 25K ..9021" in why and "not armed" in why and NR not in why, why)

        st = {"running": False, "cfg": None}
        calls = []
        G.bot_running = lambda: st["running"]
        G.update = lambda py=None: False
        G.migrate = lambda: None
        G.setup_missing = lambda cfg=None, b=None, allow=None: []
        AR.nt_connected = lambda cfg: True
        G.feed_problem = lambda: None
        G.sims_passed = lambda: {"roundtrip": True, "add": True}
        G.server_up = lambda: True
        G.server_stale = lambda: False
        G.env_newer_than_server = lambda env=None, pid=None: False
        G.verify_routes = lambda *a, **k: []
        G.arm_b = lambda atlas, path=None, selftest=None: {"ok": True, "already": True}
        G.checklist_lines = lambda: ([], 0)
        G.time = type("T", (), {"sleep": staticmethod(lambda s: None), "time": staticmethod(time.time)})
        G.startup_shortcuts = lambda: None
        G.shortcut = lambda: None
        AC.resume_optin = lambda phrase: []
        starts = []

        def start_fn(cfg):                                   # Bot Control's start in the server (resume_now)
            starts.append(("resume", cfg))
            st.update(running=True, cfg=cfg)
            return {"ok": True}

        def fake_http(path, body=None, timeout=5):
            if path == "/api/next/start/resume":
                return G.resume_now(start_fn, connected=True, live_state={}, env={"NINJATRADER_LIVE": "1"}, state_fn=lambda: {})
            raise RuntimeError(path)
        G._http = fake_http

        def nt_main(argv):                                   # engine.ninjatrader's CLI: /api/live/start | stop
            calls.append(argv[0])
            if argv[0] == "--start":
                if st["running"]:
                    return 1                                 # "already running"
                cfg = {"adapter": "ninjatrader", "nt_account": TC.L50, "armed": True, "confirm": argv[argv.index("--confirm") + 1]}
                starts.append(("start", cfg))
                st.update(running=True, cfg=cfg)
            elif argv[0] == "--stop":
                st.update(running=False)
            return 0
        NT.main = nt_main

        def job(phrase=""):
            G._save({"step": "auto", "state": "running", "t0": time.time()}, G.JOB_FILE)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = G.step_auto(G._read(G.CFG), phrase, sleep=lambda s: None, wait_s=1)
            return rc, G._read(G.JOB_FILE), out.getvalue()

        d = G.status(state={"running": False}, connected=lambda: True, feed=lambda: None)
        arm = next(s for s in d["steps"] if s["key"] == "armed")
        check("a. Start page: the phrase box shows (need_phrase) and the Armed row is red naming the Rapid",
              d["need_phrase"] is True and "..9021" in (d["resume_why"] or "") and not arm["done"]
              and "Rapid EOD 25K ..9021 not armed" in arm["detail"] and "NOT armed" in d["say"], (d["resume_why"], arm, d["say"]))
        r = G.resume_now(start_fn, connected=True, live_state={}, env={"NINJATRADER_LIVE": "1"}, state_fn=lambda: {})
        check("a. resume_now (Start trading without the phrase, in the server) is refused with need=phrase, nothing started",
              not r["ok"] and r.get("need") == "phrase" and "..9021" in r["error"] and not starts, r)
        rc, j, _ = job("")
        check("a. Start trading, no phrase typed -> rc 3, need=phrase, the Rapid named, nothing started, still disarmed",
              rc == 3 and j.get("need") == "phrase" and "..9021" in j.get("say", "") and not starts and not calls
              and (rapid.read() or {}).get("armed") is False, (rc, j, starts, calls))
        rc, j, out = job("i accept live risk")
        cfg = (starts[-1][1] if starts else {})
        check("b. Start trading with the phrase typed -> step_arm: rapid.json armed in this run, the bot started WITH the phrase",
              rc == 0 and (rapid.read() or {}).get("armed") is True and starts and starts[-1][0] == "start"
              and cfg.get("confirm") == LIVE_PHRASE and "--start" in calls, (rc, j, starts, calls, out[-400:]))
        check("b. the started bot's Rapid lane passes the NinjaTrader gate (before: 'start config is not armed')",
              gate(tmp, cfg) is None, gate(tmp, cfg))
        check("b. the page says Running, no NOT armed line", j.get("stage") == "running" and "NOT armed" not in j.get("say", ""), j)
        check("f. all armed now -> the next Start trading needs no phrase again", G.resume_problem() is None, G.resume_problem())

        # c. both Rapids disarmed (a re-added 25K + the 2nd Rapid in data/rapid2.json)
        b1 = rapid.load()
        b1["armed"] = False
        rapid.save(b1)
        with contextlib.redirect_stdout(io.StringIO()):
            r2 = AC.add("rapideod", NR2)
        why = G.resume_problem() or ""
        check("c. the 2nd Rapid (slot rapid2) is added DISARMED and both Rapids are named", r2.get("ok") and r2.get("slot") == "rapid2"
              and "Rapid EOD 25K ..9021" in why and "Rapid EOD 50K ..9022" in why, (r2, why))
        st.update(running=False, cfg=None)
        starts.clear()
        calls.clear()
        rc, j, out = job(LIVE_PHRASE)
        cfg = (starts[-1][1] if starts else {})
        check("c. one typed phrase arms both Rapids in the same run; both lanes pass the gate",
              rc == 0 and (rapid.read() or {}).get("armed") is True and (rapid.read(rapid.slot_path("rapid2")) or {}).get("armed") is True
              and gate(tmp, cfg) is None and gate(tmp, cfg, "rapid2") is None, (rc, j, out[-400:]))

        # d. START BOT's arm step when the server is restarted and resumes the bot by itself (autostart record kept)
        for sl in ("rapid", "rapid2"):
            b = rapid.load(rapid.slot_path(sl))
            b["armed"] = False
            rapid.save(b, rapid.slot_path(sl))
        st.update(running=False, cfg=None)
        starts.clear()
        calls.clear()
        srv = {"up": True, "boot": None}

        def start_server(wait_s=120):                        # the fresh server's _autostart_resume: BOT.start from the record
            srv["up"] = True
            dd = AR.decide(AR.load(AR.OPTIN_PATH), {"adapter": "ninjatrader", "nt_account": TC.L50}, {},
                           env={"NINJATRADER_LIVE": "1"}, connected=True)
            srv["boot"] = (rapid.read() or {}).get("armed")
            starts.append(("boot", dd["cfg"]))
            st.update(running=True, cfg=dd["cfg"])
            return True
        G.server_up = lambda: srv["up"]
        G.server_stale = lambda: True
        G.stop_server = lambda: srv.update(up=False) or True
        G.start_server = start_server
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = G.step_arm(G._read(G.CFG), LIVE_PHRASE, open_page=False)
        cfg = (starts[-1][1] if starts else {})
        check("d. START BOT with a server restart: both Rapids armed BEFORE the restart (the boot resume reads them armed)",
              srv["boot"] is True, srv)
        check("d. the bot the server resumed by itself is restarted with the phrase: --stop then --start, rc 0, lanes pass the gate",
              rc == 0 and calls[:2] == ["--stop", "--start"] and starts[-1][0] == "start" and cfg.get("confirm") == LIVE_PHRASE
              and gate(tmp, cfg) is None and gate(tmp, cfg, "rapid2") is None, (rc, calls, out.getvalue()[-500:]))
        # its own resume wins the race only after the arm step looked (it waits for NinjaTrader): --start says already running
        st.update(running=False, cfg=None)
        starts.clear()
        calls.clear()
        G.server_stale = lambda: False
        race = {"armed": True}

        def nt_racing(argv):                                 # the server's resume (waiting for NinjaTrader) starts the bot
            if argv[0] == "--start" and race["armed"]:       # just before this --start arrives: "already running"
                race["armed"] = False
                st.update(running=True, cfg={"adapter": "ninjatrader", "nt_account": TC.L50, "armed": True})
                starts.append(("boot", st["cfg"]))
            return nt_main(argv)
        NT.main = nt_racing
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = G.step_arm(G._read(G.CFG), LIVE_PHRASE, open_page=False)
        check("d. the server's own resume won the race after --start ('already running') -> stopped and started once more, rc 0",
              rc == 0 and calls[:3] == ["--start", "--stop", "--start"] and starts[-1][0] == "start", (rc, calls, out.getvalue()[-500:]))
        NT.main = nt_main
        G.server_up = lambda: True
        G.start_server, G.stop_server = keep["start_server"], keep["stop_server"]

        # e. the phrase typed but the Rapid cannot be armed: said on the page, never a silent "Running"
        for sl in ("rapid", "rapid2"):
            b = rapid.load(rapid.slot_path(sl))
            b["armed"] = False
            rapid.save(b, rapid.slot_path(sl))
        AC.arm(LIVE_PHRASE)                                  # the 2nd Rapid armed: only the 1st is left
        rapid.arm = lambda phrase, p=None: {"ok": False, "error": "test: could not write data/rapid.json"}
        st.update(running=False, cfg=None)
        rc, j, out = job(LIVE_PHRASE)
        check("e. the 1st Rapid could not be armed -> 'NOT armed, so NOT trading: Rapid EOD 25K ..9021' on the page, the reason "
              "in the lines", rc == 0 and "NOT armed, so NOT trading" in j.get("say", "") and "..9021" in j.get("say", "")
              and "NOT armed: test: could not write" in out, (j, out[-400:]))
        rapid.arm = keep_mod[2]

        # f. a Sim Rapid (the owner's test) never asks for the phrase; an armed one neither
        rapid.off(rapid.slot_path("rapid2"))
        b = rapid.load()
        b.update(account="Sim205", armed=False)
        rapid.save(b)
        check("f. a Sim Rapid never makes Start trading ask for the phrase", G.unarmed_added() == [] and G.resume_problem() is None,
              (G.unarmed_added(), G.resume_problem()))
        with contextlib.redirect_stdout(io.StringIO()):
            AC.add("builder25k", TC.N25)                     # an engine.accounts row (LIT on a Builder 25K #2), DISARMED
        check("a. an engine.accounts row added DISARMED asks for the phrase too ('Builder 25K ..0025')",
              "Builder 25K ..0025" in (G.resume_problem() or ""), G.resume_problem())
        AC.arm(LIVE_PHRASE)
        check("f. ... and once armed by the phrase, Start trading needs none again", G.resume_problem() is None, G.resume_problem())
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        rapid.PATH, rapid.PATH2, rapid.arm, AR.OPTIN_PATH, AR.nt_connected, NT.main, AC.resume_optin = keep_mod
        for k, v in env_keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
