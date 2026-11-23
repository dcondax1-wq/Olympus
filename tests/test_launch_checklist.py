"""Launch checklist (engine/launch_check.py, tools/web_public/launch.js, web_next/js/next/cc.js): every line turns red / green
from fixture data, each red line carries its one fix command, the facts come from the real file readers (temp files), the
only file written is the Sim roundtrip result, the heartbeat / live.json / Command center carry the block, and the phone
turns the PC lines red when the heartbeat is old.

    python -X utf8 -m tests.test_launch_checklist
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import launch_check as LC  # noqa: E402

ET = ZoneInfo("America/New_York")
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {str(detail)[:400]}"), flush=True)


def ts(y, mo, d, h, mi):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


NOW = ts(2026, 10, 25, 19, 30)            # Sunday 19:30 ET, after the launch
LIT, B = "MFFU50K-EVAL-1", "MFFU25K-EVAL-2"


def good_facts():
    return {"v": 1, "t": NOW, "lit_account": LIT,
            "anchor": {"set": True, "balance": 49710.8, "floor": 48168.2, "as_of": "2026-10-23", "set_t": NOW - 600},
            "b": {"configured": True, "account": B, "plan": "builder25k", "eval_start": "2026-10-26", "armed": False, "running": True},
            "allow": {"n": 2, "lit": True, "lit_sim": False, "b": True, "b_sim": False},
            "startup": {"ok": True, "since": NOW - 300, "problems": []},
            "sim": {"roundtrip": {"t": NOW - 1200, "ok": True, "account": "Sim101"}, "add": {"t": NOW - 900, "ok": True, "account": "Sim101"}},
            "roll": {"level": "ok", "chart": "MNQ 12-26", "root": "MNQ", "orders": "MNQ 12-26", "signal_root": "MNQ",
                     "say": "chart MNQ 12-26, orders MNQ 12-26; next roll Thu Dec 10"},
            "lit_armed": True, "bot_started_t": NOW - 400}


def good_health():
    return {"account": {"name": LIT, "adapter": "ninjatrader", "armed": True},
            "nt": {"connected": True, "connections": {"MFFU": "CONNECTED"}},
            "feed": {"used": "ninjatrader", "age_1m_s": 20, "age_5m_s": 100, "stale": False, "entries_blocked": False, "market_open": True}}


def item(cl, key):
    return next((i for i in cl["items"] if i["key"] == key), {})


def pure_checks():
    cl = LC.checklist(good_facts(), good_health(), True, NOW)
    keys = [i["key"] for i in cl["items"]]
    check("12 lines in order (roll = the chart's contract, 2026-10-26)",
          keys == ["anchor", "allow", "b", "startup", "nt", "feed", "roll", "broker", "sim", "sim_add", "armed", "up"], keys)
    f_old = {k: v for k, v in good_facts().items() if k != "roll"}
    c_old = LC.checklist(f_old, good_health(), True, NOW)
    check("an older PC without the roll fact: the roll line is info (not counted), still all green",
          item(c_old, "roll")["state"] == "info" and c_old["all_green"], item(c_old, "roll"))
    check("all green from the good fixture (armed is display only)", cl["all_green"] and cl["n_red"] == 0
          and all(i["state"] == "good" for i in cl["items"] if i["key"] not in ("armed", "broker")), [(i["key"], i["state"]) for i in cl["items"]])
    check("anchor line shows the launch numbers", "$49,710.80" in item(cl, "anchor")["detail"] and "$48,168.20" in item(cl, "anchor")["detail"],
          item(cl, "anchor"))
    check("armed: info, says 50K ARMED / 25K not armed, no fix", item(cl, "armed")["state"] == "info" and "50K ARMED" in item(cl, "armed")["detail"]
          and "25K not armed" in item(cl, "armed")["detail"] and not item(cl, "armed")["fix"], item(cl, "armed"))
    check("no red line without a fix, no green line with one", all(bool(i["fix"]) == (i["state"] == "bad") for i in cl["items"]))

    def red(name, key, f=None, h=None, running=True, now=NOW, want_fix=None):
        c = LC.checklist(f or good_facts(), h or good_health(), running, now)
        i = item(c, key)
        ok = i.get("state") == "bad" and not c["all_green"] and (want_fix is None or i.get("fix") == want_fix)
        check(f"red: {name} -> {i.get('fix')}", ok, i)
        return i

    f = good_facts(); f["anchor"] = {"set": False}
    red("no eval anchor", "anchor", f, want_fix=f'python -m engine.launch_prep --atlas "{B}"')
    f = good_facts(); f["allow"]["b"] = False
    red("25K not allowlisted", "allow", f, want_fix=f'python -m engine.ninjatrader --allow-account "{B}"')
    f = good_facts(); f["allow"].update(lit=False, b=False)
    red("neither allowlisted", "allow", f, want_fix=f'python -m engine.launch_prep --atlas "{B}"')
    f = good_facts(); f["b"] = {"configured": False, "account": None}; f["allow"]["b"] = None
    i = red("account B not set", "b", f, want_fix='python -m engine.launch_prep --atlas "<25K Name>"')
    f = good_facts(); f["startup"] = {"ok": False, "since": None, "problems": ["NinjaTrader restarted: confirm the account"]}
    red("startup disarmed after a NinjaTrader restart", "startup", f, want_fix=LC.RESET_CMD)
    f = good_facts(); f["startup"] = {"ok": False, "since": None, "problems": ["no eval anchor set (startup_require_anchor)"]}
    red("startup disarmed (no anchor)", "startup", f, want_fix=f'python -m engine.launch_prep --atlas "{B}"')
    f = good_facts(); f["startup"] = {"ok": False, "since": None, "problems": ["bar feed not fresh (stale)"]}
    i = red("startup disarmed (feed)", "startup", f, want_fix=LC.STATUS_CMD)
    check("startup red line names the reason", "bar feed not fresh" in i["detail"], i)
    f = good_facts(); f["startup"] = {"ok": False, "since": None, "problems": ["PC clock check against internet time still running"]}
    c = LC.checklist(f, good_health(), True, NOW)
    check("startup waiting only for the clock probe -> wait", item(c, "startup")["state"] == "wait", item(c, "startup"))
    f = good_facts(); f["startup"] = {"ok": False, "since": None, "problems": []}
    c = LC.checklist(f, good_health(), True, NOW)
    check("startup not checked yet -> wait (not green, not red)", item(c, "startup")["state"] == "wait" and not c["all_green"], item(c, "startup"))
    h = good_health(); h["nt"] = {"connected": False, "connections": {}}
    red("NinjaTrader not connected", "nt", h=h, want_fix=LC.STATUS_CMD)
    h = good_health(); h["account"]["adapter"] = "paper"
    red("bot on paper, not NinjaTrader", "nt", h=h)
    h = good_health(); h["feed"].update(stale=True, block="FEED STALE: 1m bar 9 min old")
    red("feed stale", "feed", h=h, want_fix=LC.STATUS_CMD)
    h = good_health(); h["feed"].update(age_1m_s=900, age_5m_s=1500)
    red("feed old", "feed", h=h)
    h = good_health(); h["feed"].update(market_open=False, age_1m_s=None, age_5m_s=None)
    c = LC.checklist(good_facts(), h, True, NOW)
    check("feed while the market is closed -> wait", item(c, "feed")["state"] == "wait", item(c, "feed"))
    f = good_facts(); f["sim"] = {}
    red("Sim roundtrip not run", "sim", f, want_fix=LC.RT_CMD)
    red("Sim roundtrip + add not run", "sim_add", f, want_fix=LC.RT_ADD_CMD)
    f = good_facts(); f["sim"]["roundtrip"]["ok"] = False
    i = red("Sim roundtrip failed", "sim", f, want_fix=LC.RT_CMD)
    check("failed Sim line says FAILED", "FAILED" in i["detail"], i)
    f = good_facts(); f["sim"]["add"]["t"] = NOW - 8 * 86400
    red("Sim roundtrip + add older than 7 days", "sim_add", f, want_fix=LC.RT_ADD_CMD)
    for k in ("startup", "nt", "feed", "up"):
        red(f"bot stopped: {k}", k, running=False, want_fix=LC.START_CMD)
    # bot running from 01:55 ET
    mon_0300 = ts(2026, 10, 26, 3, 0)
    f = good_facts(); f["bot_started_t"] = ts(2026, 10, 25, 18, 20)
    c = LC.checklist(f, good_health(), True, mon_0300)
    check("up: started Sun 18:20, Mon 03:00 -> green", item(c, "up")["state"] == "good", item(c, "up"))
    f["bot_started_t"] = ts(2026, 10, 26, 2, 10)
    red("bot restarted after 01:55", "up", f, now=mon_0300, want_fix=LC.START_CMD)
    check("up_from_t: Sun 19:30 -> Mon 01:55 ET", LC.up_from_t(NOW) == ts(2026, 10, 26, 1, 55))
    check("up_from_t: Fri 19:00 -> Mon 01:55 ET", LC.up_from_t(ts(2026, 10, 30, 19, 0)) == ts(2026, 11, 2, 1, 55))
    check("up_from_t: Mon 10:00 -> Mon 01:55 ET", LC.up_from_t(ts(2026, 10, 26, 10, 0)) == ts(2026, 10, 26, 1, 55))
    check("checklist(None, None, False) never raises, everything red but armed",
          LC.checklist(None, None, False, NOW)["n_red"] == 9)


def file_checks():
    tmp = tempfile.mkdtemp(prefix="le_launch_")
    try:
        anchor = os.path.join(tmp, "eval_anchor.json")
        allow = os.path.join(tmp, "allow.json")
        sec = os.path.join(tmp, "second_model.json")
        sim = os.path.join(tmp, "sim_roundtrip_last.json")
        bot = SimpleNamespace(cfg={"adapter": "ninjatrader", "nt_account": LIT, "armed": False}, running=True, started_at=NOW - 100,
                              health={"startup": {"ok": False, "problems": ["chart contract MNQ 09-26 is not the order contract"]}},
                              _startup_ok=None, acct_b=None, state={})
        h = good_health()
        kw = dict(sim_path=sim, second_path=sec, allow_path=allow, anchor_path=anchor)
        data_dir = os.path.join(ROOT, "data")
        snap = lambda: sorted((n, os.path.getmtime(os.path.join(data_dir, n))) for n in os.listdir(data_dir)) if os.path.isdir(data_dir) else []
        before = snap()
        f0 = LC.facts(bot, h, NOW, **kw)
        c0 = LC.checklist(f0, h, True, NOW)
        check("facts from empty files: anchor / allow / B / Sim red, startup red with its reason",
              all(item(c0, k)["state"] == "bad" for k in ("anchor", "allow", "b", "sim", "sim_add", "startup"))
              and "contract" in item(c0, "startup")["detail"], [(i["key"], i["state"]) for i in c0["items"]])
        # the owner's launch: launch_prep's writers, into temp files
        from engine import eval_life, ninjatrader
        eval_life.save_anchor({"balance": 49710.80, "floor": 48168.20, "as_of": "2026-10-23"}, path=anchor)
        ninjatrader.allow_account(LIT, path=allow)
        ninjatrader.allow_account(B, path=allow)
        json.dump({"account_b": {"account": B, "plan": "builder25k", "eval_start": "2026-10-26", "strategies": []}, "strategies": {}},
                  open(sec, "w"))
        r1 = LC.save_sim_result("roundtrip", True, "Sim101", ["exit code 0"], path=sim, now=NOW - 60)
        r2 = LC.save_sim_result("add", True, "Sim101", ["exit code 0"], path=sim, now=NOW - 30)
        check("save_sim_result writes both kinds into one file", r1 and r2 and set(json.load(open(sim))) == {"v", "roundtrip", "add"})
        check("save_sim_result refuses an unknown kind", LC.save_sim_result("other", True, "Sim101", path=sim) is None)
        bot._startup_ok = NOW - 50
        f1 = LC.facts(bot, h, NOW, **kw)
        c1 = LC.checklist(f1, h, True, NOW)
        check("facts after the launch steps: every line green", c1["all_green"], [(i["key"], i["state"], i["detail"]) for i in c1["items"]])
        check("facts: anchor numbers read back", f1["anchor"]["balance"] == 49710.8 and f1["anchor"]["floor"] == 48168.2, f1["anchor"])
        check("facts: allowlist hits both, B configured", f1["allow"]["lit"] and f1["allow"]["b"] and f1["b"]["configured"], f1)
        blob = json.dumps(f1)
        check("facts: secret-free (no phrase / confirm / path / password)", not any(w in blob.lower() for w in ("confirm", "phrase", "password", tmp.lower())), blob)
        check("facts / checklist wrote nothing in data/", snap() == before)
        check("only the Sim result file was written in the temp folder", sorted(os.listdir(tmp)) == sorted(
            ["eval_anchor.json", "allow.json", "second_model.json", "sim_roundtrip_last.json"]), os.listdir(tmp))
        # the CLI hook: --sim-roundtrip / --sim-roundtrip-add write the result (the route itself is stubbed)
        old_cli, old_path = ninjatrader._cli_sim_check, LC.SIM_RESULT
        cli_sim = os.path.join(tmp, "cli_sim.json")
        try:
            LC.SIM_RESULT = cli_sim
            ninjatrader._cli_sim_check = lambda cfg, roundtrip=False, add=False: 0 if not add else 1
            rc1 = ninjatrader.main(["--sim-roundtrip"])
            rc2 = ninjatrader.main(["--sim-roundtrip-add"])
            d = json.load(open(cli_sim))
            check("CLI: --sim-roundtrip writes ok, --sim-roundtrip-add writes FAILED (exit 1)", rc1 == 0 and rc2 == 1
                  and d["roundtrip"]["ok"] is True and d["add"]["ok"] is False and d["roundtrip"]["account"] == "Sim101", d)
            rc3 = ninjatrader.main(["--sim-check"])
            check("CLI: --sim-check writes no result", rc3 == 0 and set(json.load(open(cli_sim))) == {"v", "roundtrip", "add"})
        finally:
            ninjatrader._cli_sim_check, LC.SIM_RESULT = old_cli, old_path
        check("data/ untouched by the CLI test", snap() == before)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def wiring_checks():
    from engine import heartbeat, live_publish, pc_cc_api
    bot = SimpleNamespace(cfg={"adapter": "paper"}, running=False, state={}, health={}, ledger=[], log=[])
    hb = heartbeat.Heartbeat(bot, every_s=300, log=lambda *a: None)
    # sealed from the PC's real data/rapid.json, rapid2.json, account_c.json (2026-11-22: the owner's PC runs a Rapid EOD
    # 25K, 13 lines there and the self-test failed "exactly 12"): the 12 base lines always, + one per configured extra
    from engine import launch_check as LCK, rapid as RPD
    base = ["anchor", "allow", "b", "startup", "nt", "feed", "roll", "broker", "sim", "sim_add", "armed", "up"]
    keep = (RPD.PATH, getattr(RPD, "PATH2", None), LCK.facts)
    sealed = tempfile.mkdtemp(prefix="le_lc_seal_")
    real_facts = LCK.facts

    def keys_of(p):
        return [i.get("key") for i in ((p.get("launch") or {}).get("items") or [])]
    try:
        RPD.PATH, RPD.PATH2 = os.path.join(sealed, "rapid.json"), os.path.join(sealed, "rapid2.json")
        LCK.facts = lambda *a, **k: real_facts(*a, **{"c_root": sealed, **k})
        pl = hb.payload()
        keys = keys_of(pl)
        check("heartbeat payload has 'launch' with items (sealed: exactly the 12 base lines)",
              isinstance(pl.get("launch"), dict) and keys == base, keys or pl.get("launch"))
        RPD.save({"account": "MFFUEVRPD900000001", "plan": "mffu_rapid_eod_25k", "start": "2026-11-20"}, RPD.PATH)
        RPD.save({"account": "MFFUEVRPD900000002", "plan": "mffu_rapid_eod_50k", "start": "2026-11-20"}, RPD.PATH2)
        os.makedirs(os.path.join(sealed, "data"), exist_ok=True)
        with open(os.path.join(sealed, "data", "account_c.json"), "w") as fh:
            json.dump({"account_c": {"account": "Sim101", "plan": "builder25k"}}, fh)
        k2 = keys_of(hb.payload())
        check("with a fake rapid.json, rapid2.json and account_c.json: the 12 base keys a subset, + rapid, rapid2, blitz "
              "(n = 12 + 3)", set(base) <= set(k2) and {"rapid", "rapid2", "blitz"} <= set(k2) and len(k2) == 15
              and len(set(k2)) == 15, k2)
    finally:
        RPD.PATH, RPD.PATH2, LCK.facts = keep
        shutil.rmtree(sealed, ignore_errors=True)
    check("heartbeat 'launch' under 4 KB", len(json.dumps(pl["launch"])) < 4096, len(json.dumps(pl["launch"])))
    check("heartbeat 'launch' facts carry the chart contract (roll)", isinstance((pl["launch"].get("facts") or {}).get("roll"), dict),
          (pl["launch"].get("facts") or {}).get("roll"))
    lj = live_publish.build(pl, now=pl["t"])
    check("live.json carries pc.launch", (lj.get("pc") or {}).get("launch", {}).get("items") == pl["launch"]["items"])
    src = open(os.path.join(ROOT, "tools", "cloud_monitor.py"), encoding="utf-8").read()
    check("cloud monitor keeps pc.launch in data.json", '"ai", "launch"' in src)
    check("cloud monitor pushes the roll notices (engine/roll_watch.cloud_notices)", "roll_watch.cloud_notices(pc, now)" in src)
    check("pc_cc_api home_view has the launch block", "launch" in pc_cc_api.home_view.__code__.co_names or '"launch"' in
          open(pc_cc_api.__file__, encoding="utf-8").read())
    web = os.path.join(ROOT, "tools", "web_public")
    idx = open(os.path.join(web, "index.html"), encoding="utf-8").read()
    check("index.html loads launch.js after goals.js", 0 < idx.find("goals.js?v=") < idx.find("launch.js?v="))
    check("More hub lists the Launch checklist", "['launch', 'lights'" in open(os.path.join(web, "features.js"), encoding="utf-8").read())
    cc = open(os.path.join(ROOT, "web_next", "js", "next", "cc.js"), encoding="utf-8").read()
    check("PC Command center draws the launch card on top", "launchHtml(d.launch) + banners(d)" in cc)


def phone_model_checks():
    node = shutil.which("node")
    if not node:
        # the PC has no Node.js (owner screenshot 2026-11-16): the phone-page JS check is skipped with a note, never a FAIL
        print("[SKIP] optional: install Node.js (nodejs.org, free) for the phone-page JS check; the Python checks above ran")
        return
    f, h = good_facts(), good_health()
    lc = {**LC.checklist(f, h, True, NOW), "facts": f}
    stub = ("const GROUPS=[{id:'system',pages:[['system','More','modules','']]},{id:'today',pages:[]}];const VIEWS={today(el){el.innerHTML='';}};"
            "const PAGES={};const SCENE={};const ALIAS={launch:'x'};const esc=(s)=>String(s??'');const icon=()=>'';const usd=(v)=>'$'+v;"
            "const head=(a,b)=>'<h>'+b+'</h>';const toast=()=>0;global.document={addEventListener(){},createElement(){return {}},head:{appendChild(){}}};"
            "global.window={};global.navigator={};")
    js = (stub + "let D=null;" + f"eval(require('fs').readFileSync({json.dumps(os.path.join(ROOT, 'tools', 'web_public', 'launch.js'))},'utf8'));"
          "const U=window.LaunchUI;const out={};const now=Date.now()/1000;"
          f"const lc={json.dumps(lc)};"
          "D={live:{pc:{present:true,t:now-60,launch:lc}}};let m=U.model();out.fresh={all:m.all,good:m.good,n:m.n,card:U.card()};"
          "D={live:{pc:{present:true,t:now-3600,launch:lc}}};m=U.model();out.stale={all:m.all,red:m.items.filter(i=>i.state==='bad').map(i=>i.key),"
          "fix:m.items.find(i=>i.key==='up').fix,card:U.card().includes('Launch checklist')};"
          "D={live:{pc:{present:true,t:now-30}}};m=U.model();out.none={red:m.items.filter(i=>i.state==='bad').length};"
          "const el={innerHTML:'',insertAdjacentHTML(p,h){this.innerHTML+=h}};D={live:{pc:{present:true,t:now-60,launch:lc}}};VIEWS.launch(el);"
          "out.page=el.innerHTML.includes('Launch checklist')&&el.innerHTML.includes('$49,710.80')&&el.innerHTML.includes('MFFU25K-EVAL-2');out.pageReg=!!PAGES.launch&&GROUPS[0].pages.some(p=>p[0]==='launch');"
          "console.log(JSON.stringify(out));")
    r = subprocess.run([node, "-e", js], capture_output=True, text=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("phone launch.js runs in node", False, r.stderr[-600:])
        return
    check("phone: fresh heartbeat + all-green block -> all green, Home card hidden", o["fresh"]["all"] and o["fresh"]["card"] == ""
          and o["fresh"]["good"] == o["fresh"]["n"] == 10, o["fresh"])
    check("phone: heartbeat 60 min old -> startup / NinjaTrader / feed / up red with the start command, card shown",
          sorted(o["stale"]["red"]) == ["feed", "nt", "startup", "up"] and not o["stale"]["all"] and "run_bot.ps1" in o["stale"]["fix"]
          and o["stale"]["card"], o["stale"])
    check("phone: no launch block from the PC -> 9 red lines", o["none"]["red"] == 9, o["none"])
    check("phone: #/launch page draws with the anchor, registered under More", o["page"] and o["pageReg"], o)


def blitz_checks():
    """2026-10-29: a "BLITZ (account C) ready" line when account C is configured (engine/blitz_preflight.py's go-live check in
    one line: green when every line is, else the first red one with its fix); no line when it is off."""
    f = good_facts()
    cl = LC.checklist(f, good_health(), True, NOW)
    check("BLITZ off: no BLITZ line (the 12 lines as before)", item(cl, "blitz") == {})
    first = {"key": "armed", "label": "Armed (you do this)", "state": "bad", "detail": "MFFUEVBLDR777 is NOT armed",
             "fix": "Start page > BLITZ · 25K > Arm BLITZ (type I ACCEPT LIVE RISK)"}
    f["c"] = {"configured": True, "all_green": False, "n_red": 1, "n_wait": 0, "n": 14, "account": "MFFUEVBLDR777", "sim": False, "first": first}
    cl = LC.checklist(f, good_health(), True, NOW)
    it = item(cl, "blitz")
    keys = [i["key"] for i in cl["items"]]
    check("BLITZ configured, one red: its line red with that line's fix, right after account B",
          it.get("state") == "bad" and "Arm BLITZ" in it.get("fix", "") and "NOT armed" in it.get("detail", "") and keys[keys.index("b") + 1] == "blitz"
          and not cl["all_green"], it)
    f["c"] = {**f["c"], "all_green": True, "n_red": 0, "first": None}
    cl = LC.checklist(f, good_health(), True, NOW)
    check("BLITZ all green: its line green, the checklist all green", item(cl, "blitz").get("state") == "good" and cl["all_green"], item(cl, "blitz"))
    f["c"] = {**f["c"], "all_green": False, "n_wait": 1, "first": {"key": "bot", "label": "Bot running with BLITZ", "state": "wait", "detail": "next poll", "fix": ""}}
    cl = LC.checklist(f, good_health(), True, NOW)
    check("BLITZ only waiting: a wait line without a fix", item(cl, "blitz").get("state") == "wait" and not item(cl, "blitz").get("fix"), item(cl, "blitz"))
    tmp = tempfile.mkdtemp(prefix="le_launch_c_")
    try:
        from engine import account_c as AC
        bot = SimpleNamespace(cfg={"adapter": "ninjatrader", "nt_account": LIT}, running=False, health={}, _startup_ok=None, acct_b=None, state={})
        check("facts: no data/account_c.json -> no 'c' fact", "c" not in LC.facts(bot, good_health(), NOW, c_root=tmp))
        os.makedirs(os.path.join(tmp, "data"))
        AC.write_local({"account": "MFFUEVBLDR777", "plan": "builder25k", "eval_start": "2026-11-02", "armed": False}, tmp)
        fc = LC.facts(bot, good_health(), NOW, c_root=tmp).get("c") or {}
        check("facts: account C configured -> its go-live check cut (count, first red line, account)",
              fc.get("configured") and fc.get("account") == "MFFUEVBLDR777" and fc.get("n_red", 0) >= 1 and (fc.get("first") or {}).get("fix"), fc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    pure_checks()
    blitz_checks()
    file_checks()
    wiring_checks()
    phone_model_checks()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
