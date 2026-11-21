"""PC dashboard live pages: /api/next/pc/status, /api/next/pc/account, /api/next/pc/trade/<entry_t>, /api/next/extras
(engine/pcdash_api.py). A fake PC bot (no loop, no broker), a temp journal and a temp state file; every route is a GET and
must leave the bot untouched.

  python -X utf8 -m tests.test_pcdash_api
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from engine import lit_learn, pcdash_api
from engine.live import LiveBot, market_open

ET = ZoneInfo("America/New_York")


def ts(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def fake_bot(tmp, account="MFFUEVAL123", env="live", kill=False, stale=False, running=True):
    now = ts(2026, 10, 20, 9, 40)
    b = LiveBot()
    b.state_path = os.path.join(tmp, "live_state.json")
    b.clock = lambda: now
    b.cfg = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "eval_start": "2026-10-19", "eval_prior_pnl": -100,
             "webhook_url": "https://hooks.example/SECRET-TOKEN", "model": "lit", "data_source": "ninjatrader"}
    b._lit_sizing = {"eval_start": "2026-10-19", "eval_prior_pnl": -100}
    b._eval_prev = {"2026-10-19": 1450.0}
    b.running, b.kill, b.started_at, b.last_poll = running, kill, now - 7200, now - 20
    e1, e2 = ts(2026, 10, 20, 3, 5), ts(2026, 10, 20, 8, 35)
    oif = r"C:\Users\Owner\Documents\NinjaTrader 8\incoming\oif_LE_1.txt"
    b.ledger = [
        {"t": e1 + 3, "sym": "NQ", "side": "buy", "qty": 12, "stop": 24990.0, "target": 25150.0, "entry": 25020.0, "entry_t": e1,
         "result": {"ok": True, "adapter": "ninjatrader", "legs": [{"filled": 12, "fill_px": 25020.5, "ok": True}]}},
        {"t": e1 + 1800, "sym": "NQ", "side": "modify", "qty": 12, "stop": 25020.5, "reason": "BE", "entry_t": e1,
         "result": {"ok": False, "error": f"stop change REJECTED: see {oif}"}},
        {"t": e1 + 3600, "sym": "NQ", "side": "exit", "qty": 12, "reason": "BE", "pnl": -22.8, "entry_t": e1, "exit_t": e1 + 3600,
         "result": {"ok": True}},
        {"t": e2 + 3, "sym": "NQ", "side": "sell", "qty": 8, "stop": 25110.0, "target": 24900.0, "entry": 25070.0, "entry_t": e2,
         "result": {"ok": True, "legs": [{"filled": 8, "fill_px": 25069.75, "ok": True}]}},
    ]
    b.log.appendleft({"t": e1 - 600, "type": "risk", "text": "Entry at 02:55 ET NOT routed: feed stale"})
    b._open_routed, b._open_qty = e2, 8
    b.state = {"model": "lit", "price": 25050.0, "t": now - 360, "day_trades": 1, "setups": {},
               "model_state": "LIT: IN TRADE SHORT @ 25,070.00 | stop 25,110.00 | target 24,900.00",
               "position": {"entry_t": e2, "dir": -1, "qty": 9, "stop": 25110.0, "stop0": 25110.0, "target": 24900.0,
                            "entry": 25070.0, "risk_pts": 40.0, "be": False, "target_label": "VIX band low"},
               "lit": {"signals_today": [{"t": e2 - 600, "dir": -1, "swept": ["pdh", "asia20_h"], "limit_px": 25070.0, "stop_px": 25110.0,
                                          "target_px": 24900.0, "risk_pts": 40.0, "rr": 4.25}]},
               "eval_2wk": {"session": 2, "limit": 10, "status": "open", "text": "session 2 of 10, 9 left"}}
    b.health.update({"data_source": "ninjatrader", "stale": stale, "market_open": True, "last_bar_t": now - (2400 if stale else 600),
                     "last_1m_bar_t": now - (2400 if stale else 120), "last_ok_poll": now - 20, "poll_ms": 500})
    b.adapter = SimpleNamespace(name="ninjatrader", account=account, env=env, disabled=None, last_error=None, killed=False,
                                legs=[{"entry_t": e2, "dir": -1, "fill_px": 25069.75, "stop": 25110.0, "target": 24900.0,
                                       "status": "protected", "filled": 8, "instrument": "MNQ 12-26", "stop0": 25110.0}],
                                connections=lambda: {"Tradovate": "CONNECTED"}, folder_status=lambda: {"incoming": True, "outgoing": True})
    bars = pd.DataFrame({"time": [now - 3 * 3600 + 60 * i for i in range(180)]})
    bars["open"] = 25060.0
    bars["high"], bars["low"], bars["close"] = 25064.0, 25052.25, 25058.5
    b.bars_tail = [{"time": int(t), "open": 25060.0, "high": 25065.0, "low": 25050.0, "close": 25055.0, "volume": 1}
                   for t in range(now - 6 * 3600, now - 300, 300)]
    b._lit_1m_store = bars
    return b, now


def fake_nt_folder(tmp, account="MFFUEVAL123"):
    """A Documents\\NinjaTrader 8 look-alike: incoming / outgoing, a CONNECTED connection, a position file for the real
    account and fresh LE_BarFeed MNQ 5m + 1m files ending now."""
    import time as _t
    f = os.path.join(tmp, "NinjaTrader 8")
    for d in ("incoming", "outgoing", "le_feed"):
        os.makedirs(os.path.join(f, d), exist_ok=True)
    open(os.path.join(f, "outgoing", "Tradovate.txt"), "w").write("CONNECTED")
    open(os.path.join(f, "outgoing", f"MNQ 12-26 Globex_{account}_Position.txt"), "w").write("FLAT;0;0")
    now = int(_t.time())
    for m in (5, 1):
        s = m * 60
        last = now - now % s - s
        with open(os.path.join(f, "le_feed", f"MNQ_{m}m.csv"), "w") as fh:
            fh.write("time,open,high,low,close,volume\n")
            for i in range(400, -1, -1):
                if market_open(last - i * s) or i == 0:          # no bars in the 17:00 ET halt / weekend; the newest bar always (fresh at any wall time)
                    fh.write(f"{last - i * s},25000,25002,24998,25001,10\n")
    return f


def botctl_checks(tmp, check, live_bot):
    """Bot Control center (engine/botctl.py): preflight, accounts, Start (Sim one click; a real account only with the typed
    phrase + present + the live env flag), the phrase never echoed / stored, auto-update / auto-resume, restart, read-only
    switches, insights."""
    from engine import autoresume, autoupdate, botctl
    from engine.tradovate import LIVE_PHRASE
    folder = fake_nt_folder(tmp)
    old = {"bot": botctl._bot, "hooks": dict(botctl.HOOKS), "env": os.environ.get("NINJATRADER_FOLDER"),
           "ar_en": autoresume.enable, "ar_dis": autoresume.disable, "au_load": autoupdate.load_state, "au_save": autoupdate.save_state,
           "au_log": autoupdate.file_log, "sup": os.environ.get(botctl.SUPERVISED_ENV), "live": os.environ.get(botctl.LIVE_ENV)}
    calls = []

    def _start(body):
        calls.append(copy.deepcopy(body))
        fb.running = True
        fb.cfg = dict(body)
        return {"ok": True, "restored": False}

    fb = SimpleNamespace(running=False, kill=False, cfg={}, adapter=None, state={}, log=[], ledger=[], health={}, started_at=None,
                         last_poll=None, errors=0, start=_start, stop=lambda: {"ok": True}, clock=lambda: int(__import__("time").time()),
                         day_pnl_routed=lambda: 0.0, bars_tail=[])
    optin = os.path.join(tmp, "auto_resume.json")
    au_path = os.path.join(tmp, "autoupdate.json")
    texts = []
    try:
        os.environ["NINJATRADER_FOLDER"] = folder
        os.environ.pop(botctl.LIVE_ENV, None)
        os.environ.pop(botctl.SUPERVISED_ENV, None)
        autoresume.enable = lambda a, c, cfg=None: old["ar_en"](a, c, cfg, path=optin)
        autoresume.disable = lambda reason, now=None: old["ar_dis"](reason, now, path=optin)
        autoupdate.load_state = lambda path=au_path: old["au_load"](au_path)
        autoupdate.save_state = lambda s, path=au_path: old["au_save"](s, au_path)
        autoupdate.file_log = lambda text: None
        botctl.HOOKS.update(start=None, stop=None, heartbeat=lambda: {"enabled": True, "last": {"at": int(fb.clock()) - 30, "ok": True}})
        botctl._bot = lambda: fb
        app = FastAPI()
        app.include_router(botctl.router)
        cl = TestClient(app)

        def call(method, path, body=None):
            r = cl.post(path, json=body) if method == "POST" else cl.get(path)
            texts.append(r.text)
            return r, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})

        st = botctl.selftest(start=True, wait=True)
        check("botctl: self-test runs in a subprocess and passes", st.get("ok") is True and not st.get("running"), st)
        check("botctl: the self-test left the server's live env flag alone", os.environ.get(botctl.LIVE_ENV) is None)

        # ---- status + preflight
        r, s = call("GET", "/api/next/botctl/status")
        check("botctl status 200", r.status_code == 200, r.text[:300])
        rows = {x["id"]: x for x in s["preflight"]["rows"]}
        need = ("strategy", "folder", "ati", "connection", "feed5m", "feed1m", "noyahoo", "selftest", "livelock", "kill", "sizing", "auto", "version")
        check("preflight: every row of the checklist", all(k in rows for k in need), sorted(rows))
        check("preflight: folder, ATI, CONNECTED, 5m + 1m feed, self-test green on a good NinjaTrader",
              all(rows[k]["ok"] is True for k in ("folder", "ati", "connection", "selftest", "strategy"))
              and all(rows[k]["ok"] is True or (rows[k]["ok"] is None and not market_open(fb.clock())) for k in ("feed5m", "feed1m")),
              {k: (rows[k]["ok"], rows[k]["detail"]) for k in ("folder", "ati", "connection", "feed5m", "feed1m", "selftest")})
        check("preflight: Sim101 is startable (no red row)", s["preflight"]["ok"] and s["preflight"]["account"] == "Sim101", s["preflight"]["red"])
        check("preflight: every red row carries its fix", all(x["fix"] for x in s["preflight"]["rows"] if x["ok"] is False))
        names = {a["name"]: a for a in s["accounts"]}
        check("accounts: Sim101 + the real account NinjaTrader reports", "Sim101" in names and names.get("MFFUEVAL123", {}).get("label") == "LIVE", names)
        r, s2 = call("GET", "/api/next/botctl/status?account=MFFUEVAL123")
        rows2 = {x["id"]: x for x in s2["preflight"]["rows"]}
        check("preflight (real account): the live env flag missing is RED with its fix", rows2["livelock"]["ok"] is False and rows2["livelock"]["fix"]
              and s2["preflight"]["needs_phrase"] and not s2["preflight"]["ok"], rows2["livelock"])
        check("strip: window, heartbeat pushed, eval meter", s["strip"]["window"].get("text") and abs(s["strip"]["heartbeat"]["age_s"] - 30) <= 2
              and "to_target" in (s.get("eval") or {}), (s["strip"]["window"], s["strip"]["heartbeat"], s.get("eval")))
        os.environ["NINJATRADER_FOLDER"] = os.path.join(tmp, "nowhere")
        r, s3 = call("GET", "/api/next/botctl/status")
        rows3 = {x["id"]: x for x in s3["preflight"]["rows"]}
        check("preflight: no NinjaTrader -> red folder / ATI / connection / feed rows, Start blocked",
              all(rows3[k]["ok"] is False for k in ("folder", "ati", "connection", "feed5m", "feed1m")) and not s3["preflight"]["ok"])
        os.environ["NINJATRADER_FOLDER"] = folder

        # ---- start
        r, j = call("POST", "/api/next/botctl/start", {"account": "Sim101"})
        cli = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "present": True, "poll_sec": 60, "data_source": "ninjatrader",
               "nt_account": "Sim101"}
        check("start: Sim101 with one click", r.status_code == 200 and j.get("ok") and len(calls) == 1, j)
        check("start: the same body as `python -m engine.ninjatrader --start --account Sim101`",
              {k: v for k, v in calls[0].items() if k != "accounts"} == cli, calls[0])
        r, j = call("POST", "/api/next/botctl/start", {"account": "Sim101"})
        check("start: refused while already running", r.status_code == 400 and len(calls) == 1, j)
        fb.running = False
        n0 = len(calls)
        r, j = call("POST", "/api/next/botctl/start", {"account": "MFFUEVAL123", "present": True})
        check("start: a real account WITHOUT the phrase is refused (nothing started)", r.status_code == 400 and j.get("refused") and len(calls) == n0, j)
        typed = "i accept something else 7731"
        r, j = call("POST", "/api/next/botctl/start", {"account": "MFFUEVAL123", "confirm": typed, "present": True})
        check("start: a wrong phrase is refused and not echoed", r.status_code == 400 and len(calls) == n0 and typed not in r.text, j)
        r, j = call("POST", "/api/next/botctl/start", {"account": "MFFUEVAL123", "confirm": LIVE_PHRASE, "present": True})
        check("start: the exact phrase without the server's live env flag is refused", r.status_code == 400 and len(calls) == n0, j)
        r, j = call("POST", "/api/next/botctl/start", {"account": "MFFUEVAL123", "confirm": LIVE_PHRASE, "present": False})
        check("start: the exact phrase without 'I am at the PC' is refused", r.status_code == 400 and len(calls) == n0, j)
        res = botctl.do_start(fb, "MFFUEVAL123", LIVE_PHRASE, present=True, env={botctl.LIVE_ENV: "1"})
        check("start: real account with phrase + present + live env flag -> the start route gets the CLI body with the phrase "
              "(in memory, for the adapter's own gate)", res.get("ok") and len(calls) == n0 + 1 and calls[-1].get("confirm") == LIVE_PHRASE
              and calls[-1].get("nt_account") == "MFFUEVAL123" and calls[-1].get("armed") is True, {k: v for k, v in calls[-1].items() if k != "confirm"})
        check("start: the answer never carries the phrase", LIVE_PHRASE not in json.dumps(botctl.scrub(res)), "")
        lb = LiveBot()
        lb.cfg = {"adapter": "ninjatrader", "confirm": LIVE_PHRASE, "webhook_url": "https://x/SECRET"}
        check("snapshot (/api/live/state) never returns the typed phrase", LIVE_PHRASE not in json.dumps(lb.snapshot(), default=str))
        check("scrub(): phrase keys dropped, phrase text redacted",
              botctl.scrub({"confirm": LIVE_PHRASE, "a": [f"x {LIVE_PHRASE} y"], "phrase": 1}) == {"a": [f"x {botctl.REDACT} y"]})
        fb.running = True
        r, j = call("POST", "/api/next/botctl/stop")
        check("stop: the bot's stop", r.status_code == 200 and j.get("ok"), j)
        fb.running = False

        # ---- auto-update / auto-resume
        r, j = call("POST", "/api/next/botctl/autoupdate", {"on": True})
        check("auto-update on (same state file switch as --enable)", j.get("ok") and j.get("on") and json.load(open(au_path))["enabled"] is True, j)
        r, j = call("POST", "/api/next/botctl/autoupdate", {"on": False})
        check("auto-update off", j.get("ok") and j.get("on") is False and json.load(open(au_path))["enabled"] is False, j)
        n0 = len(calls)
        r, j = call("POST", "/api/next/botctl/autoresume", {"on": True, "account": "MFFUEVAL123"})
        check("auto-resume on without the phrase is refused (nothing written)", r.status_code == 400 and not os.path.exists(optin), j)
        r, j = call("POST", "/api/next/botctl/autoresume", {"on": True, "account": "MFFUEVAL123", "confirm": LIVE_PHRASE})
        rec = json.load(open(optin)) if os.path.exists(optin) else {}
        check("auto-resume on with the phrase: engine.autoresume.enable (proof only)", r.status_code == 200 and j.get("on") and rec.get("enabled")
              and rec.get("account") == "MFFUEVAL123" and autoresume.valid(rec), j)
        check("auto-resume on: then the CLI's start (refused here: the live env flag is not set)", len(calls) == n0 and (j.get("start") or {}).get("refused"), j.get("start"))
        r, j = call("POST", "/api/next/botctl/autoresume", {"on": False})
        check("auto-resume off", j.get("ok") and j.get("on") is False and not json.load(open(optin)).get("enabled"), j)

        # ---- restart
        r, j = call("POST", "/api/next/botctl/restart")
        check("restart: refused when no supervisor (run_bot.ps1) would bring the server back", r.status_code == 400 and "run_bot" in (j.get("error") or ""), j)
        os.environ[botctl.SUPERVISED_ENV] = "1"
        fb.state = {"position": {"entry_t": 1, "dir": 1, "qty": 1, "entry": 1.0, "stop": 0.0}}
        fb._open_routed = None
        r, j = call("POST", "/api/next/botctl/restart")
        check("restart: refused while not flat", r.status_code == 400 and "flat" in (j.get("error") or ""), j)
        exited = []
        botctl.HOOKS["exit"] = exited.append
        fb.state = {}
        r, j = call("POST", "/api/next/botctl/restart")
        __import__("time").sleep(1.3)
        check("restart: flat + supervised -> exit code 75 (run_bot.ps1 restarts at once)", r.status_code == 200 and exited == [75], (j, exited))

        # ---- read-only panels
        r, j = call("GET", "/api/next/botctl/switches")
        sw = {x["key"]: x for x in j.get("switches") or []}
        check("switches: t_check, scale_in, be_off with H1 / H2 numbers and on/off", set(sw) == {"t_check", "scale_in", "be_off"}
              and all("H1" in x["rule"] and "H2" in x["rule"] and x["on"] in (True, False) for x in sw.values()) and j.get("read_only"), list(sw))
        check("switches: no route can change them", not any("switch" in getattr(rt, "path", "") and "POST" in getattr(rt, "methods", set())
                                                        for rt in botctl.router.routes))
        if os.path.exists(os.path.join(pcdash_api.DATA, "NQ_5m.csv")):
            r, j = call("GET", "/api/next/botctl/plan")
            check("plan: today's LIT levels (watched / swept) from lit_brief", r.status_code == 200 and isinstance(j.get("watched"), list)
                  and "_brief" not in j, r.text[:200])
        r, j = call("GET", "/api/next/botctl/insights")
        check("insights: rule checklist, why-no-trade, radar, killzones, news, alerts, timeline, changelog",
              r.status_code == 200 and len(j.get("checklist") or []) == 6 and j.get("why", {}).get("headline") and "levels" in j.get("radar", {})
              and len(j.get("killzones") or []) == 3 and "events" in j.get("news", {}) and "rows" in j.get("alerts", {})
              and isinstance(j.get("timeline"), list) and "commits" in j.get("changelog", {}), r.text[:300])

        # ---- the phrase: never echoed, never stored
        check("phrase: in no response of any botctl route", not any(LIVE_PHRASE in t for t in texts))
        blob = ""
        for dp, _dn, fns in os.walk(tmp):
            for fn in fns:
                try:
                    blob += open(os.path.join(dp, fn), encoding="utf-8", errors="ignore").read()
                except OSError:
                    pass
        check("phrase: in no file written (auto-resume opt-in, auto-update state)", LIVE_PHRASE not in blob)
    finally:
        botctl._bot = old["bot"]
        botctl.HOOKS.clear()
        botctl.HOOKS.update(old["hooks"])
        autoresume.enable, autoresume.disable = old["ar_en"], old["ar_dis"]
        autoupdate.load_state, autoupdate.save_state, autoupdate.file_log = old["au_load"], old["au_save"], old["au_log"]
        for k, v in (("NINJATRADER_FOLDER", old["env"]), (botctl.SUPERVISED_ENV, old["sup"]), (botctl.LIVE_ENV, old["live"])):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def intel_checks(tmp, check):
    """Data > Trade intel (/api/next/intel, engine/next_api.py -> tools/trade_intel.py): the stored backtest rows + the PC
    journal's paper / live trades, the signs and the compact cut. Read-only (a GET over research/lab/trade_intel.json)."""
    from engine import next_api
    from tools import trade_intel as TI
    if not os.path.exists(TI.OUT):
        check("intel: research/lab/trade_intel.json exists (python -X utf8 tools/trade_intel.py)", False)
        return
    app = FastAPI()
    app.include_router(next_api.router)
    cl = TestClient(app)
    jp = os.path.join(tmp, "intel_journal.jsonl")
    with open(jp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"source": "pc", "key": "x", "day": "2026-10-20", "entry_t": ts(2026, 10, 20, 3, 5), "exit_t": ts(2026, 10, 20, 4, 0),
                             "side": "LONG", "entry_px": 25000.0, "stop_px": 24970.0, "target_px": 25150.0, "risk_pts": 30.0, "qty": 5,
                             "exit": "STOP", "r": -1.02, "pnl": -306.0, "mfe": 0.2, "mae": 1.0, "f": {"disp": 1.1, "idm_n": 2, "vix": 18.2}}) + "\n")
    old = TI._journal
    TI._journal = lambda path, _o=old: _o(jp)          # the PC's journal -> the temp one
    try:
        r = cl.get("/api/next/intel")
        d = r.json()
        keys = [c["key"] for c in d.get("cols") or []]
        rows = [dict(zip(keys, x)) for x in d.get("rows") or []]
        check("intel 200: cols, rows, signs, summary", r.status_code == 200 and len(keys) >= 60 and d.get("signs") and d.get("summary"), r.text[:200])
        check("intel: backtest rows + the journal's live trade", sum(1 for x in rows if x["source"] == "backtest") >= 600
              and [x["source"] for x in rows if x["source"] != "backtest"] == ["live"], (d.get("meta") or {}).get("sources"))
        lv = next((x for x in rows if x["source"] == "live"), {})
        check("intel: the live row carries the journal features + outcome", lv.get("disp") == 1.1 and lv.get("idm_n") == 2
              and lv.get("r") == -1.02 and lv.get("outcome") == "loss" and lv.get("rr") == 5.0, lv)
        rc = cl.get("/api/next/intel?compact=1").json()
        check("intel compact: summary, top signs, the live row, small", rc.get("summary") and isinstance(rc.get("top"), list)
              and len(rc.get("live_rows") or []) == 1 and len(json.dumps(rc)) < 80_000, len(json.dumps(rc)))
        check("intel: GET only", all(getattr(rt, "methods", {"GET"}) <= {"GET", "HEAD"} for rt in next_api.router.routes
                                     if getattr(rt, "path", "") == "/api/next/intel"))
    finally:
        TI._journal = old


def brain_checks(check, live_bot):
    """Bot Brain (/api/next/brain*, engine/brain_api.py mounted by engine/next_api.py): the bot's Brain, the phone cut, a
    replayed 2026 minute, the sessions list. Read-only GETs (tests/test_brain.py checks the content against the engine)."""
    from engine import brain, brain_api, next_api
    app = FastAPI()
    app.include_router(next_api.router)
    cl = TestClient(app)
    old = brain_api._bot
    try:
        live_bot.brain = None
        brain_api._bot = lambda: live_bot
        r = cl.get("/api/next/brain")
        check("brain: no Brain yet -> empty + a day to replay", r.status_code == 200 and r.json().get("empty"), r.text[:200])
        if not os.path.exists(os.path.join(pcdash_api.DATA, "NQ_5m.csv")):
            return
        rb = cl.get("/api/next/brain/day/2026-10-13?hm=06:10")
        j = rb.json()
        check("brain: replay 2026-10-13 06:10 = in the SHORT trade, BE trigger and 15-minute check shown",
              rb.status_code == 200 and j["stage"]["key"] == "trade" and j["trade"]["side"] == "SHORT" and j["trade"]["t_check"]["at_hm"] == "06:18",
              (rb.status_code, (j.get("stage") or {}).get("key"), j.get("error")))
        live_bot.brain = j
        r = cl.get("/api/next/brain?compact=1")
        c = r.json()
        check("brain: the live Brain's phone cut (stage, waiting, setups with checks) < 16 KB",
              r.status_code == 200 and c.get("compact") and c["stage"]["waiting"] and c["setups"] and len(r.text) < 16_500, len(r.text))
        check("brain: GET only, the bot untouched", all(getattr(rt, "methods", {"GET"}) <= {"GET", "HEAD"} for rt in brain_api.router.routes)
              and not live_bot.kill)
        check("brain: days list", len(cl.get("/api/next/brain/days").json().get("days") or []) > 150)
    finally:
        brain_api._bot = old
        live_bot.brain = None
        _ = brain


def perf_checks(tmp, check):
    """Data > Performance (/api/next/perf, engine/next_api.py -> engine/perf.pc_view): expected range, live vs backtest from
    the fill audit's report, exit efficiency, robustness, months, status (the PC's uptime log), look-ahead audit. GET only."""
    from engine import fill_audit as FA
    from engine import next_api
    from engine import uptime as UP
    app = FastAPI()
    app.include_router(next_api.router)
    cl = TestClient(app)
    store, old_store, old_up = os.path.join(tmp, "perf_exec"), FA.STORE, UP.PC_PATH
    FA.STORE, UP.PC_PATH = store, os.path.join(tmp, "uptime_pc.json")
    try:
        FA._write_json(os.path.join(store, "report.json"), {"v": 1, "t": 1, "rows": [
            {"status": "matched", "day": "2026-10-20", "entry_t": ts(2026, 10, 20, 3, 5), "bt_pnl": 600.0, "bt_pnl_live_qty": 600.0,
             "live_pnl": 585.0, "slip_usd": -15.0, "exec_usd": -15.0},
            {"status": "missed", "day": "2026-10-21", "entry_t": ts(2026, 10, 21, 9, 50), "bt_pnl": -300.0, "missed_usd": -300.0, "reason": "feed stale"}]})
        UP.pc_hook({"t": ts(2026, 10, 20, 9, 40), "running": True, "health": {"feed": {"market_open": True, "age_1m_s": 20}}})
        # the Status view shows the last 30 days before NOW: freeze its clock on Wed 2026-10-21 so the 10-20 sample stays in view
        # whatever the real date (it fell out of the window from 2026-11-19 on)
        import types as _types
        from engine import perf as _PERF
        real_time = _PERF.time
        _PERF.time = _types.SimpleNamespace(**{k: getattr(real_time, k) for k in dir(real_time) if not k.startswith("__")})
        _PERF.time.time = lambda: float(ts(2026, 10, 21, 12, 0))
        try:
            r = cl.get("/api/next/perf")
        finally:
            _PERF.time = real_time
        d = r.json()
        check("perf 200: every block", r.status_code == 200 and all(k in d for k in ("range", "exec", "exit", "robust", "months", "status", "lookahead")), r.text[:200])
        ex = d.get("exec") or {}
        check("perf: live vs backtest from the fill audit's report (gap = slippage + missed)", ex.get("live") == 585.0 and ex.get("bt") == 300.0
              and ex.get("gap") == 285.0 and (ex.get("parts") or {}).get("missed trades") == 300.0, ex.get("parts"))
        sf = next((p for p in (d.get("status") or {}).get("parts") or [] if p["id"] == "surface"), {})
        check("perf: status from the PC's uptime log", sf.get("uptime") == 100.0, sf)
        check("perf: range band, exit efficiency, robustness card, months, look-ahead summary",
              (d.get("range") or {}).get("bands") and (d.get("exit") or {}).get("y2026") and (d.get("robust") or {}).get("card")
              and (d.get("months") or {}).get("rows") and (d.get("lookahead") or {}).get("summary"), {k: bool(v) for k, v in d.items()})
        check("perf: GET only", all(getattr(rt, "methods", {"GET"}) <= {"GET", "HEAD"} for rt in next_api.router.routes
                                    if getattr(rt, "path", "") == "/api/next/perf"))
    finally:
        FA.STORE, UP.PC_PATH = old_store, old_up


def hub_checks(tmp, check, live_bot):
    """The hub pages' API (engine/hub_api.py: Prop Firms, Business, Market, Learn, System): read-only GETs, data shapes,
    every fact of research/props/firms.json marked and sourced, eval odds that rise with the balance, the gallery route
    refusing paths outside research/lab/gallery, and the phone export (tools/hub_data.export)."""
    from engine import hub_api
    from tools import hub_data
    app = FastAPI()
    app.include_router(hub_api.router)
    cl = TestClient(app)
    before = copy.deepcopy(live_bot.ledger)

    r = cl.get("/api/next/hub/firms")
    f = r.json()
    check("hub firms 200 with firms, table, sources, next steps", r.status_code == 200 and len(f.get("firms") or []) >= 5
          and len(f.get("table") or []) >= 8 and f.get("sources") and (f.get("next") or {}).get("steps"), r.text[:200])
    ids = {x["firm_id"] for x in f.get("table") or []}
    check("hub firms: MFFU, Lucid, FundedNext + 3 others", {"mffu", "lucid", "fundednext"} <= ids and len(ids) >= 6, ids)
    mffu = {x["plan_id"]: x for x in f.get("table") or [] if x["firm_id"] == "mffu"}
    check("hub firms: MFFU Builder 25K / 50K, Rapid, Rapid EOD with the owner's prices",
          {"mffu_builder_25k", "mffu_builder_50k", "mffu_rapid_50k", "mffu_rapid_eod_50k"} <= set(mffu)
          and mffu["mffu_builder_50k"]["price_real"] == 91.8 and mffu["mffu_builder_25k"]["price_real"] == 63.0, list(mffu))
    facts = list(hub_data._iter_facts(hub_data.firms_raw().get("firms")))
    bad_st = [x for x in facts if x.get("st") not in ("confirmed", "unconfirmed", "conflict")]
    srcs = hub_data.firms_raw().get("sources") or {}
    bad_src = sorted({s for x in facts for s in x.get("src") or [] if s not in srcs})
    check("hub firms: every fact confirmed / unconfirmed / conflict, every source key resolves", facts and not bad_st and not bad_src,
          (len(bad_st), bad_src[:5]))
    lv = [fm for fm in f["firms"] if all(k in (fm.get("live") or {}) for k in ("when", "how", "changes", "closes_others", "risk_rules", "reports"))]
    check("hub firms: a live-account section for every firm", len(lv) == len(f["firms"]), [fm["id"] for fm in f["firms"]])
    b50 = next(p for fm in f["firms"] for p in fm["plans"] if p["id"] == "mffu_builder_50k")
    check("hub firms: LIT fit from funded_firms.json (H2 p10, funded $/month)",
          not os.path.exists(os.path.join(hub_data.LIT_DOCS, "funded_firms.json")) or (ok_num((b50.get("lit") or {}).get("H2", {}).get("p10"))
                                                                                   and ok_num(b50["lit"]["H2"].get("funded_month"))), b50.get("lit"))
    codes = [c for fm in f["firms"] for c in fm.get("codes") or []]
    check("hub firms: discount codes with date + status", codes and all(c.get("seen") and c.get("st") for c in codes), len(codes))

    r = cl.get("/api/next/hub/business")
    b = r.json()
    ev = b.get("eval") or {}
    check("hub business 200: eval from the PC bot's account", r.status_code == 200 and "PC bot" in str(b.get("eval_source"))
          and ev.get("balance") == 50000 - 100 + 1450 - 22.8, (b.get("eval_source"), ev.get("balance")))
    check("hub business: odds, floor gauge, compliance, payouts, P&L, tax, goal, planners",
          all(k in b for k in ("odds", "floor", "compliance", "payouts", "live", "pnl", "tax", "goal", "scaling", "withdraw"))
          and not (b["odds"] or {}).get("error") and b["compliance"].get("rows"), [k for k in b if isinstance(b[k], dict) and b[k].get("error")])
    rows = {x["rule"]: x for x in b["compliance"]["rows"]}
    check("hub business: compliance sees the open 8 micros and today's $22.80 daily loss",
          rows["Max contracts"]["ok"] is True and "8 micros" in rows["Max contracts"]["now"] and rows["Daily loss (soft)"]["ok"] is True
          and "$23" in rows["Daily loss (soft)"]["now"], rows.get("Max contracts"))
    check("hub business: tax labelled not advice", "not tax advice" in str(b["tax"].get("label", "")).lower(), b["tax"])
    lo = cl.get("/api/next/hub/odds?profit=-1500&session=3").json()
    hi = cl.get("/api/next/hub/odds?profit=2500&session=3").json()
    check("hub odds: pass chance rises with the balance, fail chance falls", hi.get("pass_left", 0) > lo.get("pass_left", 100)
          and hi.get("fail_ever", 100) < lo.get("fail_ever", 0), (lo.get("pass_left"), hi.get("pass_left")))

    r = cl.get("/api/next/hub/market")
    m = r.json()
    check("hub market 200: calendar, earnings, holidays, roll, VIX, overnight, levels", r.status_code == 200
          and all(k in m for k in ("calendar", "earnings", "holidays", "roll", "vix", "overnight", "levels")), r.text[:200])
    check("hub market: 8 mega-caps, roll to the next quarterly contract", {x["sym"] for x in m["earnings"].get("rows") or []}
          >= {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO"} and m["roll"].get("days_to_roll") is not None, m["roll"])
    check("hub market: CME holidays list early closes and closures", any(x["kind"] == "early" for x in m["holidays"].get("rows") or [])
          and any(x["kind"] == "closed" for x in m["holidays"].get("rows") or []), len(m["holidays"].get("rows") or []))

    r = cl.get("/api/next/hub/learn")
    le = r.json()
    check("hub learn 200: versions, library with verdicts, glossary, gallery, upgrades", r.status_code == 200
          and (le.get("library") or {}).get("rows") and (le.get("learn") or {}).get("glossary") and "upgrades" in le, r.text[:200])
    check("hub learn: verdicts are known buckets", all(x["verdict"] in ("adopted", "candidate", "rejected", "promising", "finding", "info")
                                                     for x in le["library"]["rows"]))
    check("hub learn: upgrades tracker shows a placeholder until lit_base exists", (le["upgrades"].get("live") or {}).get("placeholder")
          or (le["upgrades"].get("live") or {}).get("with") is not None, le["upgrades"].get("live"))

    r = cl.get("/api/next/hub/system")
    s = r.json()
    check("hub system 200: discipline, uptime, data quality", r.status_code == 200 and all(k in s for k in ("discipline", "uptime", "dataq")), r.text[:200])
    check("hub system: the bot log's kill / start lines reach the discipline log", any(x["src"] == "bot log" for x in s["discipline"].get("rows") or [])
          or not any("kill" in str(x.get("text", "")).lower() or "start" in str(x.get("text", "")).lower() for x in live_bot.log), s["discipline"].get("counts"))

    check("hub gallery: a path outside research/lab/gallery -> 404", cl.get("/api/next/hub/gallery/../../live_model.json").status_code == 404
          and cl.get("/api/next/hub/gallery/x.txt").status_code == 404)
    texts = [cl.get(p).text for p in ("/api/next/hub/firms", "/api/next/hub/business", "/api/next/hub/system")]
    check("hub: no secrets or webhook tokens in any response", all("SECRET" not in t and "hooks.example" not in t for t in texts))
    check("hub read-only: every route is a GET", all(getattr(rt, "methods", {"GET"}) <= {"GET", "HEAD"} for rt in hub_api.router.routes))
    check("hub read-only: the bot's ledger, kill flag and state file untouched", live_bot.ledger == before and not live_bot.kill
          and not os.path.exists(live_bot.state_path))

    out = os.path.join(tmp, "hub.json")
    rc = hub_data.main(["--out", out, "--no-fetch"])
    d = json.load(open(out, encoding="utf-8"))
    check("hub export: research/props/hub.json shape for the phone (firms, business, market, learn, odds grid)",
          rc == 0 and all(k in d for k in ("firms", "business", "market", "learn", "odds_grid")) and d["odds_grid"].get("rows"), list(d))


def ok_num(v):
    return v is not None and not (isinstance(v, float) and v != v)


def ops_checks(tmp, check, live_bot, now):
    """Operator tools (engine/pcops_api.py): pulse (sound / desktop alerts, tab badge), live chart with the LIT levels + trade
    lines, log viewer over logs/ (filters, search, fixed file names only), NinjaTrader panel, session timeline, settings viewer,
    morning report. Read-only GETs; no phrase, webhook URL or file path in any answer."""
    from engine import pcops_api
    from engine.tradovate import LIVE_PHRASE
    folder = fake_nt_folder(os.path.join(tmp, "ops"))
    logs = os.path.join(tmp, "ops_logs")
    os.makedirs(logs, exist_ok=True)
    stamp = dt.datetime.fromtimestamp(now, ET).strftime("%Y%m%d")
    with open(os.path.join(logs, f"server-{stamp}.log"), "w", encoding="utf-8") as fh:
        fh.write("2026-10-20 07:00:01 [supervisor] server started\n")
        fh.write('INFO:     127.0.0.1:5000 - "GET /api/live/state HTTP/1.1" 200 OK\n')
        fh.write("2026-10-20 07:10:00 ERROR webhook=https://hooks.example/SECRET-TOKEN failed for C:\\Users\\Owner\\x.txt\n")
        fh.write(f"2026-10-20 07:11:00 phrase typed {LIVE_PHRASE}\n")
    with open(os.path.join(logs, "ninjatrader_oif.log"), "w", encoding="utf-8") as fh:
        fh.write("2026-10-20 08:35:03 ET  MFFUEVAL123  oif_LE_7.txt  PLACE;MFFUEVAL123;MNQ 12-26;SELL;8;LIMIT;25070;0;DAY;;LE7;;\n")
    old = {"logs": pcops_api.LOGS, "env": os.environ.get("NINJATRADER_FOLDER")}
    before = copy.deepcopy(live_bot.ledger)
    try:
        pcops_api.LOGS = logs
        os.environ["NINJATRADER_FOLDER"] = folder
        app = FastAPI()
        app.include_router(pcops_api.router)
        cl = TestClient(app)
        texts = []

        def get(path):
            r = cl.get(path)
            texts.append(r.text)
            return r, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})

        r, p = get("/api/next/pc/pulse")
        check("ops pulse 200: running, position, realized / unrealized, day P&L", r.status_code == 200 and p["running"] and p["position"]["side"] == "SHORT"
              and p["realized"] == -22.8 and p["unrealized"] is not None and abs(p["day_pnl"] - (p["realized"] + p["unrealized"])) < 0.01, r.text[:300])
        ids = [e["id"] for e in p["events"]]
        check("ops pulse: entry / exit / stale events with unique ids", len(ids) == len(set(ids)) and {"entry", "exit", "stale"} <= {e["kind"] for e in p["events"]}, p["events"])
        r, c = get("/api/next/pc/chart?tf=5m")
        check("ops chart 200: bars, LIT levels, entry / stop / target lines, killzones", r.status_code == 200 and c["bars"] and c["levels"]
              and {"entry", "stop", "target"} <= {x["id"] for x in c["lines"]} and c["killzones"], {k: c.get(k) for k in ("source", "plan_error", "lines")})
        r, c1 = get("/api/next/pc/chart?tf=1m")
        r2, cx = get("/api/next/pc/chart?tf=../../etc")
        check("ops chart: 1m bars; an unknown tf falls back to 5m", c1["tf"] == "1m" and len(c1["bars"]) > len(c["bars"]) and cx["tf"] == "5m")
        r, lg = get("/api/next/pc/logs")
        srcs = {x["src"] for x in lg["rows"]}
        check("ops logs 200: bot log + ledger + server log + OIF audit, access lines counted not listed", r.status_code == 200
              and {"bot", "ledger", "server", "oif"} <= srcs and lg["access_lines"] == 1 and not any("GET /api" in x["text"] for x in lg["rows"]), (srcs, lg.get("files")))
        check("ops logs: counts per category, OIF rows are orders", set(lg["counts"]) == set(pcops_api.CATS)
              and all(x["cat"] == "orders" for x in lg["rows"] if x["src"] == "oif"), lg["counts"])
        r, le = get("/api/next/pc/logs?cat=errors&q=stale")
        check("ops logs: filter + search", le["matched"] >= 1 and all(x["cat"] == "errors" and "stale" in x["text"].lower() for x in le["rows"]), le["rows"])
        r, lt = get("/api/next/pc/logs?day=../../secrets")
        check("ops logs: a bad day falls back to today (fixed file names only)", r.status_code == 200 and lt["day"] == "2026-10-20")
        blob = json.dumps(lg)
        check("ops logs: URLs, credentials, Windows paths and the phrase redacted", "SECRET-TOKEN" not in blob and "hooks.example" not in blob
              and LIVE_PHRASE not in blob and "Users\\\\Owner" not in blob, [x["text"] for x in lg["rows"] if x["src"] == "server"])
        r, nt = get("/api/next/pc/nt")
        rid = {x["id"]: x for x in nt.get("rows") or []}
        check("ops NinjaTrader 200: folder, ATI, connection, LE_BarFeed 5m + 1m, bot bars, positions rows", r.status_code == 200
              and {"folder", "ati", "connection", "feed5m", "feed1m", "bot5m", "bot1m", "positions"} <= set(rid), sorted(rid))
        check("ops NinjaTrader: green folder / ATI / connection / fresh feed files", all(rid[k]["ok"] for k in ("folder", "ati", "connection", "feed5m", "feed1m")),
              {k: rid[k] for k in ("folder", "ati", "connection", "feed5m", "feed1m")})
        check("ops NinjaTrader: every red row has its plain fix; last OIF files sent + reports received", all(x["fix"] for x in nt["rows"] if x["ok"] is False)
              and nt["sent"] and nt["sent"][0]["action"] == "PLACE" and nt["received"], (nt["sent"], nt["received"]))
        check("ops NinjaTrader: the position mismatch (NinjaTrader flat, bot short) is red", rid["positions"]["ok"] is False, rid["positions"])
        r, tl = get("/api/next/pc/timeline")
        check("ops timeline 200: 18:00 -> 17:00, killzones, entry window, events", r.status_code == 200 and tl["t1"] - tl["t0"] == 23 * 3600
              and any(b["kind"] == "killzone" for b in tl["bands"]) and any(b["id"] == "window" for b in tl["bands"])
              and {"entry", "exit", "signal"} <= {e["kind"] for e in tl["events"]}, [e["kind"] for e in tl.get("events") or []])
        r, se = get("/api/next/pc/settings")
        names = {x["path"]: x for x in se.get("rows") or []}
        check("ops settings 200: read-only, switches with on/off and tested numbers", r.status_code == 200 and se["read_only"]
              and {"lit.t_check", "lit.be_off", "lit.scale_in"} <= set(names) and names["lit.scale_in"]["on"] is False
              and names["lit.t_check"]["on"] is True and all(names[k]["tested"] for k in ("lit.t_check", "lit.be_off")), sorted(names)[:8])
        check("ops settings: every row explained, live_model.json = live_model_lit.json", all(x["what"] for x in se["rows"]) and se["drift"] == [], se.get("drift"))
        r, mo = get("/api/next/pc/morning")
        check("ops morning 200: headline, trades, feed stale, restarts, verdict, position", r.status_code == 200 and mo["headline"].startswith("Overnight")
              and mo["feed_stale"] and mo["position"] and mo["verdict"], mo.get("headline"))
        gaps = pcops_api.bar_gaps([[now - 3600 + 60 * i] for i in range(30)] + [[now - 3600 + 60 * 40]], 60, now - 4000, now)
        check("ops morning: a 10-minute hole in the 1m bars is a feed gap", len(gaps) == 1 and gaps[0]["missing"] == 10, gaps)
        check("ops: every route is a GET", all(getattr(rt, "methods", {"GET"}) <= {"GET", "HEAD"} for rt in pcops_api.router.routes))
        check("ops: no phrase, webhook token or bot file path in any answer", not any(LIVE_PHRASE in t or "SECRET-TOKEN" in t or "oif_LE_1.txt" in t for t in texts))
        check("ops read-only: ledger, kill flag and state file untouched", live_bot.ledger == before and not live_bot.kill and not os.path.exists(live_bot.state_path))
    finally:
        pcops_api.LOGS = old["logs"]
        if old["env"] is None:
            os.environ.pop("NINJATRADER_FOLDER", None)
        else:
            os.environ["NINJATRADER_FOLDER"] = old["env"]


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_pcdash_")
    results = []

    def check(name, cond, info=""):
        results.append(bool(cond))
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""))

    old_bot, old_jp = pcdash_api._bot, lit_learn.JOURNAL_PATH
    try:
        jp = os.path.join(tmp, "journal.jsonl")
        rp = os.path.join(pcdash_api.LAB, "replays.json")
        chart_rec = None
        if os.path.exists(rp):                                      # a real replay chart: the routed trade links to it
            ch = json.load(open(rp, encoding="utf-8")).get("charts") or {}
            k = sorted(ch)[-1]
            chart_rec = (k, ch[k]["day"], int(ch[k]["entry"]["t"]))
        with open(jp, "w", encoding="utf-8") as fh:
            rows = [{"source": "pc", "key": "a", "day": "2026-10-19", "entry_t": ts(2026, 10, 19, 4, 10), "exit_t": ts(2026, 10, 19, 6, 0),
                     "side": "LONG", "qty": 10, "entry_px": 24800, "stop_px": 24770, "target_px": 25040, "exit_px": 25040, "exit": "TARGET",
                     "r": 8.0, "pnl": 1450.0, "risk_pts": 30}]
            rows.append({"source": "pc", "key": "f", "day": "2026-10-12", "entry_t": ts(2026, 10, 12, 5, 0), "exit_t": ts(2026, 10, 12, 6, 0),
                         "side": "LONG", "qty": 2, "entry_px": 25000, "stop_px": 24960, "target_px": 25200, "exit": "STOP", "r": -1, "pnl": -165, "risk_pts": 40})
            if chart_rec:
                rows.append({"source": "pc", "key": "c", "day": chart_rec[1], "entry_t": chart_rec[2], "exit_t": chart_rec[2] + 3600,
                             "side": "SHORT", "qty": 3, "entry_px": 1, "stop_px": 2, "target_px": 0, "exit": "STOP", "r": -1, "pnl": -100, "risk_pts": 1})
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        lit_learn.JOURNAL_PATH = jp
        bot, now = fake_bot(tmp)
        pcdash_api._bot = lambda: bot
        app = FastAPI()
        app.include_router(pcdash_api.router)
        cl = TestClient(app)
        before = copy.deepcopy(bot.ledger)

        # ---- /api/next/pc/status
        r = cl.get("/api/next/pc/status")
        s = r.json()
        check("status 200", r.status_code == 200, r.text[:200])
        check("status: TRADING YOUR EVAL on a live NinjaTrader account", s["verdict"]["code"] == "TRADING" and s["verdict"]["label"] == "TRADING YOUR EVAL", s["verdict"])
        check("status: account, feed age, last poll, LIT stage", s["health"]["account"]["name"] == "MFFUEVAL123" and s["health"]["feed"]["age_1m_s"] == 60
              and s["health"]["poll"]["age_s"] == 20 and s["health"]["lit"]["stage"] == "trade", s["health"])
        check("status: setups seen today", len(s["setups_today"]) == 1 and s["setups_today"][0]["side"] == "SHORT" and "PDH" in s["setups_today"][0]["level"], s["setups_today"])
        check("status: no secrets", "SECRET" not in r.text, "")
        for label, kw, code in (("Sim101 -> ON SIM", {"account": "Sim101", "env": "demo"}, "SIM"), ("kill switch -> DISABLED", {"kill": True}, "DISABLED"),
                                ("stale feed in session -> FEED STALE", {"stale": True}, "FEED"), ("bot stopped -> DISABLED", {"running": False}, "DISABLED")):
            b2, _ = fake_bot(tmp, **kw)
            check("status: " + label, pcdash_api.status_view(b2)["verdict"]["code"] == code, pcdash_api.status_view(b2)["verdict"])
        idle = LiveBot()
        idle.state_path = os.path.join(tmp, "none.json")
        check("status: a never-started bot answers (DISABLED: bot stopped)", pcdash_api.status_view(idle)["verdict"]["code"] == "DISABLED")

        # ---- /api/next/pc/account
        r = cl.get("/api/next/pc/account")
        a = r.json()
        ev = a.get("eval") or {}
        check("account 200", r.status_code == 200, r.text[:200])
        check("eval: balance counts the prior -$100 and routed P&L", ev.get("balance") == 50000 - 100 + 1450 - 22.8 and ev.get("prior") == -100, ev)
        check("eval: trailing floor, room, session N of 10, daily loss used",
              ev.get("floor") is not None and ev.get("room") == round(ev["balance"] - ev["floor"], 2) and ev.get("session") == 2
              and ev.get("sessions") == 10 and ev.get("dll_used") == 22.8, ev)
        check("account: LIVE badge from the bot's health block", a["account"]["badge"] == "LIVE", a["account"])
        p = a.get("position") or {}
        check("position: routed micros, broker fill, stop, target", p.get("side") == "SHORT" and p.get("qty") == 8 and p.get("entry") == 25069.75
              and p.get("stop") == 25110.0 and p.get("target") == 24900.0, p)
        check("position: unrealized $, time in trade, BE trigger", p.get("unrealized_usd") == round((25069.75 - 25050.0) * 2 * 8, 2)
              and p.get("time_in_s") == now - ts(2026, 10, 20, 8, 35) and p.get("be_trigger") == round(25069.75 - 40.25, 2), p)
        kinds = [(o["kind"], o["refused"]) for o in a["orders"]]
        check("timeline: risk refusal, entry, refused BE move, exit, entry", kinds == [("risk", True), ("entry", False), ("stop", True), ("exit", False), ("entry", False)], kinds)
        check("trades: journal + ledger, newest first", len(a["trades"]) >= 2 and a["trades"][0]["entry_t"] >= a["trades"][-1]["entry_t"], a["trades"])
        check("equity curve starts at the prior P&L", a["equity"][0] == ["start", -100.0] and a["equity"][-1][1] == round(-100 + 1450 - 22.8, 2), a["equity"])
        check("bars: the bot's 5m tail and packed 1m", len(a["bars5"]) > 10 and a["bars1"] and len(a["bars1"]["dt"]) == 180, (len(a["bars5"]), (a["bars1"] or {}).get("s")))
        check("account: no secrets or file paths", "SECRET" not in r.text and "Users" not in r.text and "oif_" not in r.text, "")
        b1 = a["bars1"]
        check("pack(): prices round-trip through quarter points", (b1["p0"] + b1["h"][0]) / 4 == 25064.0 and (b1["p0"] + b1["l"][0]) / 4 == 25052.25, b1["p0"])

        # ---- /api/next/pc/trade/<entry_t>
        e1 = ts(2026, 10, 20, 3, 5)
        # the bot's feed is the source when no bar file covers that day (a stub: the repo's data/NQ_5m.csv grows past the fixture's
        # 2026-10-20 over time, and then the fuller file is rightly preferred, checked just below)
        real_file_bars, pcdash_api.file_bars = pcdash_api.file_bars, (lambda *a, **k: ([], []))
        try:
            r = cl.get(f"/api/next/pc/trade/{e1}")
        finally:
            pcdash_api.file_bars = real_file_bars
        t = r.json()
        check("trade: today's routed trade with bars from the bot's feed", r.status_code == 200 and t["trade"]["entry_t"] == e1 and t["chart"] is None
              and len(t["bars5"]) > 0 and t["bars_source"] == "bot feed", {k: v for k, v in t.items() if k not in ("bars5", "bars1")})
        f5_day = pcdash_api.file_bars("NQ", e1 - 6 * 3600, e1 + 3600)[0]
        r = cl.get(f"/api/next/pc/trade/{e1}")
        t = r.json()
        check("trade: the bar file fills in when the bot's feed starts after the trade (only when the file covers that day)",
              r.status_code == 200 and t["bars_source"] == ("data/NQ_5m.csv" if f5_day else "bot feed") and len(t["bars5"]) > 0, t.get("bars_source"))
        if chart_rec:
            r = cl.get(f"/api/next/pc/trade/{chart_rec[2]}")
            check("trade: a routed trade the LIT replay has links its chart id", r.status_code == 200 and r.json().get("chart") == chart_rec[0], r.text[:200])
        if os.path.exists(os.path.join(pcdash_api.DATA, "NQ_5m.csv")):
            r = cl.get(f"/api/next/pc/trade/{ts(2026, 10, 12, 5, 0)}")
            t = r.json()
            check("trade: an older routed trade falls back to data/NQ_5m.csv + NQ_1m.csv", r.status_code == 200 and t.get("bars_source") == "data/NQ_5m.csv"
                  and len(t.get("bars5") or []) > 20 and (t.get("bars1") or {}).get("s") == 60, {k: v for k, v in t.items() if k not in ("bars5", "bars1")})
        r = cl.get("/api/next/pc/trade/123")
        check("trade: unknown entry -> 404", r.status_code == 404 and "error" in r.json())

        # ---- /api/next/extras
        r = cl.get("/api/next/extras")
        x = r.json()
        check("extras 200 with the phone's shapes", r.status_code == 200 and x.get("tcols") and isinstance(x.get("trades"), list), r.text[:200])
        if x.get("trades"):
            check("extras: trade rows match tcols", all(len(row) == len(x["tcols"]) for row in x["trades"]))
        check("extras: two_week odds + MFFU rules when their files exist",
              (not os.path.exists(os.path.join(pcdash_api.RUNS, "lit_2wk_rec.json")) or "H2" in (x.get("two_week") or {}).get("eval", {}))
              and (not os.path.exists(os.path.join(pcdash_api.LIT_DOCS, "mffu_rules.json")) or (x.get("mffu") or {}).get("stages")), list(x))

        # ---- read-only
        check("read-only: every route is a GET", all(getattr(rt, "methods", {"GET"}) <= {"GET", "HEAD"} for rt in pcdash_api.router.routes))
        check("read-only: the bot's ledger, kill flag and state file untouched", bot.ledger == before and not bot.kill
              and not os.path.exists(bot.state_path), "")

        botctl_checks(tmp, check, bot)
        hub_checks(tmp, check, bot)
        ops_checks(tmp, check, bot, now)
        intel_checks(tmp, check)
        brain_checks(check, bot)
        perf_checks(tmp, check)
    finally:
        pcdash_api._bot, lit_learn.JOURNAL_PATH = old_bot, old_jp
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print(f"pcdash api: {sum(results)}/{len(results)}", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
