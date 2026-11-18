"""One-tap new / upgraded MFFU accounts (2026-11-18, engine/onboard.py): the plan read from the NinjaTrader Name + balance,
the right button first, the tap = the same code as `engine.accounts add` / `engine.lit25 --funded`, added DISARMED, never
armed; "Re-arm now" = STOP + the START arm step, only with the typed phrase and only when flat.

    python -X utf8 -m tests.test_onboard        (temp files only, made-up names; nothing armed, ~5 s)
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

from engine import account_b as AB  # noqa: E402
from engine import go as G  # noqa: E402
from engine import lifecycle as LC  # noqa: E402
from engine import lit25  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import new_accounts as NA  # noqa: E402
from engine import onboard as OB  # noqa: E402
from engine import rapid  # noqa: E402
from engine import second as SE  # noqa: E402
from engine import start_api as S  # noqa: E402

RES = []
L50, L25 = "MFFUEVBLDR900000001", "MFFUEVBLDR900000002"          # Zlarior's 50K, ATLAS's 25K (made up)
N25, N50 = "MFFUEVBLDR900000025", "MFFUEVBLDR900000050"          # fresh Builder evals
OLD25 = "MFFUEVBLDR900000077"                                    # an old passed 25K eval (balance above the target)
SF25 = "MFFUSFBLDR900000099"                                     # ATLAS's new funded 25K
RPD = "MFFUEVRPD900000003"                                       # Rapid-looking (prefix not confirmed by MFFU)


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def acts(opts):
    return [o["act"] for o in opts]


def prim(opts):
    return next((o for o in opts if o.get("primary")), {})


def pure():
    i = OB.parse_name
    check("names: EVBLDR = Builder eval, SFBLDR = Builder funded, RPD = Rapid (a guess), other codes unknown, not MFFU",
          i(N25)["stage"] == "eval" and i(N25)["plan"] == "builder" and not i(N25)["guess"]
          and i(SF25)["stage"] == "funded" and i(SF25)["plan"] == "builder"
          and i(RPD)["plan"] == "rapid" and i(RPD)["guess"] and i("MFFUEVXYZ123")["plan"] is None
          and i("Sim101")["firm"] is None and i("MFFUEVBLD900000001")["plan"] == "builder", [i(n) for n in (N25, SF25, RPD)])
    check("size from the balance: $25,000 / $26,946 = 25K, $49,192 / $50,000 = 50K, none / $0 = unknown",
          OB.size_of(25000) == "25K" and OB.size_of(26946.10) == "25K" and OB.size_of(49192.78) == "50K"
          and OB.size_of(50000) == "50K" and OB.size_of(None) is None and OB.size_of(0) is None and OB.size_of("x") is None)
    f25, f50 = OB.infer(N25, 25000), OB.infer(N50, 50000)
    check("fresh Builder evals: 25K -> builder25k, 50K -> builder50k, button 'Zlarior trades it' first",
          (f25["kind"], f25["plan"]) == ("fresh_eval", "builder25k") and (f50["kind"], f50["plan"]) == ("fresh_eval", "builder50k")
          and prim(OB.offers(f25))["label"] == "Zlarior trades it" and prim(OB.offers(f25))["act"] == "add:builder25k"
          and prim(OB.offers(f50))["act"] == "add:builder50k" and "dismiss" in acts(OB.offers(f50)), (f25, f50))
    p_bal = OB.infer(OLD25, 26946.10)
    p_lock = OB.infer(N25, 25200, life_stage="locked")
    p_pass = OB.infer(N50, 50400, life_stage="passed")
    p_mem = OB.infer(N25, 25100, outcome="passed")
    p_edge = OB.infer(N25, 26499.99)
    check("passed vs fresh: $26,946 on a 25K (target $26,500), a lifecycle LOCKED / PASSED row, the bot's remembered pass -> "
          "an old passed eval with 'Not for the bot' as the only (default) button; $26,499.99 is still fresh",
          all(x["kind"] == "passed_eval" and acts(OB.offers(x)) == ["dismiss"] and prim(OB.offers(x))["label"] == "Not for the bot"
              for x in (p_bal, p_lock, p_pass, p_mem)) and p_edge["kind"] == "fresh_eval"
          and OB.infer(N50, 53000)["kind"] == "passed_eval" and OB.infer(N50, 52999)["kind"] == "fresh_eval", (p_bal, p_lock, p_edge))
    r = OB.infer(RPD, 50000)
    ro = OB.offers(r)
    check("Rapid-looking Name (prefix not confirmed): a choice, Rapid 'Zlarior + ATLAS' first, Builder 50K too, + Not for the bot",
          r["kind"] == "unknown" and r["plan"] == "rapideod" and prim(ro)["act"] == "add:rapideod"
          and "Zlarior + ATLAS" in prim(ro)["label"] and "add:builder50k" in acts(ro) and acts(ro)[-1] == "dismiss"
          and "not confirmed" in OB.say(r, ro), ro)
    r25 = OB.infer(RPD, 25000)
    r25o = OB.offers(r25)
    check("a Rapid-looking 25K (the Rapid EOD 25K, owner 2026-11-18): 'Rapid EOD 25K: Zlarior + ATLAS' first (add:rapideod25), "
          "Builder 25K offered too; passed at $26,500 like the Builder 25K",
          r25["plan"] == "rapideod25" and prim(r25o)["act"] == "add:rapideod25" and "Zlarior + ATLAS" in prim(r25o)["label"]
          and "add:builder25k" in acts(r25o) and "add:rapideod" not in acts(r25o)
          and OB.infer(RPD, 26600)["kind"] == "passed_eval", r25o)
    rsf = OB.offers(OB.infer("MFFUSFRPD900000006", 25000))
    check("a Rapid-looking funded 25K: 'Rapid EOD 25K: Zlarior + ATLAS (funded)' first (engine.accounts add --funded)",
          prim(rsf)["act"] == "funded:rapideod25" and "(funded)" in prim(rsf)["label"], rsf)
    u = OB.infer("MFFUEVXYZ900000004", 25000)
    nb = OB.infer("MFFUEVBLDR900000005", None)
    check("unknown plan code / no balance: a choice, nothing guessed alone (25K -> Builder 25K / Rapid 25K; no balance -> both sizes)",
          u["kind"] == "unknown" and acts(OB.offers(u)) == ["add:builder25k", "add:rapideod25", "dismiss"] and not any(o["primary"] for o in OB.offers(u))
          and nb["kind"] == "unknown" and acts(OB.offers(nb))[:2] == ["add:builder25k", "add:builder50k"], (OB.offers(u), OB.offers(nb)))
    sf = OB.infer(SF25, 25000)
    ev = [{"name": L25, "plan": "builder25k", "role": "b", "passed": True},
          {"name": "MFFUEVBLDR900000031", "plan": "builder25k", "role": "extra", "passed": False},
          {"name": L50, "plan": "builder50k", "role": "main", "passed": False}]
    so = OB.offers(sf, ev)
    check("a new funded 25K: 'Move ATLAS here (funded)' first (ATLAS's eval passed), the other 25K eval offered too, never the 50K",
          sf["kind"] == "funded" and prim(so)["act"] == f"move:{L25}" and prim(so)["label"].startswith("Move ATLAS here (funded)")
          and "move:MFFUEVBLDR900000031" in acts(so) and f"move:{L50}" not in acts(so) and acts(so)[-1] == "dismiss"
          and "passed" in OB.say(sf, so), so)
    s50 = OB.offers(OB.infer("MFFUSFBLDR900000098", 50000), ev)
    check("a new funded 50K: 'Move Zlarior here (funded)'; with no same-size eval: added as a funded Zlarior account",
          prim(s50)["act"] == f"move:{L50}" and prim(s50)["label"] == "Move Zlarior here (funded)"
          and prim(OB.offers(sf, []))["act"] == "funded:builder25k", (s50, OB.offers(sf, [])))


def world(tmp):
    G.CFG = os.path.join(tmp, "start_bot.json")
    G.SECOND_PATH = os.path.join(tmp, "second_model.json")
    shutil.copy(SE.CFG_PATH, G.SECOND_PATH)
    AB.set_account_b(None, path=G.SECOND_PATH)
    AB.set_account_b(L25, plan="builder25k", start="2026-10-27", path=G.SECOND_PATH)
    G.ALLOW_PATH = os.path.join(tmp, "allow.json")
    G.ACCOUNTS_PATH = os.path.join(tmp, "accounts.json")
    G.ANCHOR_PATH = os.path.join(tmp, "eval_anchor.json")
    G._save({"lit": L50, "atlas": L25, "prepped": "2026-11-17"})
    rapid.PATH = os.path.join(tmp, "rapid.json")
    nt = os.path.join(tmp, "NinjaTrader 8")
    os.makedirs(os.path.join(nt, "le_feed"), exist_ok=True)
    os.makedirs(os.path.join(nt, "outgoing"), exist_ok=True)
    now = int(time.time())
    with open(os.path.join(nt, "le_feed", "accounts.csv"), "w") as fh:
        fh.write("name,time,cash,realized,unrealized,netliq\n"
                 f"{L50},{now},49192.78,0,0,49192.78\n{L25},{now},26946.10,0,0,26946.10\n{N25},{now},25000,0,0,25000\n"
                 f"{OLD25},{now},26700,0,0,26700\n{SF25},{now},25000,0,0,25000\nSim101,{now},100000,0,0,100000\n")
    os.environ["NINJATRADER_FOLDER"] = nt
    # the lifecycle saw ATLAS's eval PASSED (the bot stores a hash of the Name, never the Name)
    with open(os.path.join(tmp, LC.FILE), "w") as fh:
        json.dump({"v": 1, "rows": {"atlas": {"stage": "passed", "acct": LC.acct_hash(L25), "label": "ATLAS 25K"}}}, fh)
    return nt


def flow(tmp):
    nt = world(tmp)
    state = os.path.join(tmp, "new_accounts.json")
    NA.STATE_PATH = state
    G.bot_running = lambda: False
    st = OB.status(folder=nt)
    by = {r["name"]: r for r in st["new"]}
    check("status: the 3 new Names (fresh 25K, old passed 25K, funded 25K); the bot's own two and Sim101 not offered",
          set(by) == {N25, OLD25, SF25}, list(by))
    check("status: fresh 25K -> 'Zlarior trades it'; old passed -> 'Not for the bot' only; funded -> 'Move ATLAS here (funded)' "
          "(lifecycle saw ATLAS's eval pass); each line says 'Armed at the next START (you type the phrase)'",
          prim(by[N25]["options"])["act"] == "add:builder25k" and acts(by[OLD25]["options"]) == ["dismiss"]
          and prim(by[SF25]["options"])["act"] == f"move:{L25}" and all(r["armed_note"] == OB.ARMED_LATER for r in st["new"]),
          {k: v["options"] for k, v in by.items()})
    # tap 1: the fresh 25K -> engine.accounts add --plan builder25k (an extra LIT account, DISARMED)
    r = OB.do(N25, "add:builder25k", folder=nt)
    rows = {x.get("nt_account"): x for x in MA.load_file(G.ACCOUNTS_PATH)}
    check("tap 'Zlarior trades it': the same row engine.accounts add writes, armed False, allowlisted; says 'Armed at the next START'",
          r["ok"] and r["armed"] is False and rows.get(N25, {}).get("armed") is False and rows[N25]["preset"] == "mffu_builder_25k"
          and rows[N25]["cli"]["plan"] == "builder25k" and OB.ARMED_LATER in r["say"]
          and N25 in json.load(open(G.ALLOW_PATH)).get("accounts", []), (r, rows))
    check("after the tap the Name is not offered again", N25 not in {x["name"] for x in OB.status(folder=nt)["new"]})
    # tap 2: the funded 25K while the bot runs and is NOT flat -> refused, nothing stopped
    stopped = []
    G.bot_running = lambda: True
    r_nf = OB.do(SF25, f"move:{L25}", folder=nt, stop_fn=lambda: stopped.append(1), flat_reason=lambda: "a position is open")
    check("move to funded while a trade is open: refused, the bot is not stopped, ATLAS unchanged",
          not r_nf["ok"] and "position is open" in r_nf["error"] and not stopped and AB.raw_cfg(G.SECOND_PATH)["account"] == L25, r_nf)
    # ... flat: stopped, then the same switch as python -m engine.lit25 --funded (ATLAS's block funded, DISARMED)
    run = {"on": True}
    G.bot_running = lambda: run["on"]
    keep_st, keep_raw = SE._selftest_ok, lit25.AB.raw_cfg
    SE._selftest_ok = lambda: (True, "PASS")
    lit25.AB.raw_cfg = lambda p=None: keep_raw(p or G.SECOND_PATH)
    try:
        r_f = OB.do(SF25, f"move:{L25}", folder=nt, start="2026-11-18", stop_fn=lambda: run.update(on=False),
                    flat_reason=lambda: None)
    finally:
        SE._selftest_ok, lit25.AB.raw_cfg = keep_st, keep_raw
    b = AB.raw_cfg(G.SECOND_PATH)
    check("move to funded when flat: the bot is stopped first, ATLAS -> funded 25K (engine.lit25 --funded), DISARMED, "
          "start_bot.json atlas follows; says to tap Re-arm now",
          r_f["ok"] and r_f.get("stopped") and b["account"] == SF25 and b["stage"] == "funded" and b.get("armed") is not True
          and json.load(open(G.CFG))["atlas"] == SF25 and "Re-arm now" in r_f["say"] and OB.ARMED_LATER in r_f["say"], (r_f, b))
    G.bot_running = lambda: False
    with open(os.path.join(nt, "le_feed", "accounts.csv"), "a") as fh:
        fh.write(f"{RPD},{int(time.time())},25000,0,0,25000\n")
    rr = next(x for x in OB.status(folder=nt)["new"] if x["name"] == RPD)
    r_r = OB.do(RPD, prim(rr["options"])["act"], folder=nt)
    blk = rapid.read() or {}
    check("one tap on a new Rapid EOD 25K: engine.accounts add --plan rapideod25 (data/rapid.json the 25K plan, LIT + ATLAS), "
          "NOT armed; 'Armed at the next START'",
          prim(rr["options"])["act"] == "add:rapideod25" and r_r["ok"] and blk.get("account") == RPD
          and blk.get("plan") == "mffu_rapid_eod_25k" and blk.get("armed") is not True and OB.ARMED_LATER in r_r["say"], (r_r, blk))
    r_x = OB.do("MFFUEVBLDR123", "add:builder25k", folder=nt)
    r_b = OB.do(OLD25, "nonsense", folder=nt)
    r_d = OB.do(OLD25, "dismiss", folder=nt)
    check("refused: a Name NinjaTrader does not show, an unknown button; 'Not for the bot' hides the old passed eval",
          not r_x["ok"] and "does not show" in r_x["error"] and not r_b["ok"] and r_d["ok"]
          and OLD25 not in {x["name"] for x in OB.status(folder=nt)["new"]}, (r_x, r_b, r_d))
    lines = OB.detect_lines(folder=nt)
    check("ADD_ACCOUNT.bat's detection lines (python -m engine.onboard): nothing new now (the moved-from eval is retired, "
          "not offered back) -> one plain line",
          len(lines) == 1 and "No new MFFU account" in lines[0], lines)
    bat = open(os.path.join(ROOT, "ADD_ACCOUNT.bat"), encoding="utf-8").read()
    check("ADD_ACCOUNT.bat prints what it detected first (engine.onboard), menu unchanged",
          "-m engine.onboard" in bat and bat.index("engine.onboard") < bat.index("Add an account") and "--plan builder25k" in bat
          and "--plan rapideod25" in bat and "5  New Rapid EOD 25K" in bat)
    return nt


def api(tmp, nt):
    G.bot_running = lambda: False
    S._bot = lambda: SimpleNamespace(running=False, cfg={})
    app = FastAPI()
    app.include_router(S.router)
    local = TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50001))
    phone = TestClient(app, base_url="http://192.168.1.20:8766", client=("192.168.1.50", 50003))
    with open(os.path.join(nt, "le_feed", "accounts.csv"), "a") as fh:
        fh.write(f"{N50},{int(time.time())},50000,0,0,50000\n")
    st = local.get("/api/next/start/status").json().get("new_accounts") or {}
    n50 = next((r for r in st.get("new") or [] if r["name"] == N50), None)
    check("API status: the Start page block comes from engine/onboard (the new 50K: 'Zlarior trades it' first)",
          n50 is not None and prim(n50["options"])["act"] == "add:builder50k", st)
    rp = phone.post("/api/next/start/onboard", json={"name": N50, "act": "add:builder50k"})
    rl = local.post("/api/next/start/onboard", json={"name": N50, "act": "add:builder50k"})
    rows = {x.get("nt_account"): x for x in MA.load_file(G.ACCOUNTS_PATH)}
    check("API tap: from the phone 403 (PC only); from the PC 200, added DISARMED", rp.status_code == 403 and rl.status_code == 200
          and rows.get(N50, {}).get("armed") is False and rl.json().get("armed") is False, (rp.text, rl.text))
    # Re-arm now
    jobs, stops = [], []
    keep = (G.job_start, G.sims_passed, G.job_status, S._stop_fn, S._flat_reason)
    G.job_start = lambda step, phrase=None, **k: (jobs.append((step, phrase)), {"ok": True, "step": step})[1]
    G.sims_passed = lambda: {"sim1": True, "sim2": True}
    G.job_status = lambda: {"running": False}
    run = {"on": True}
    G.bot_running = lambda: run["on"]
    S._stop_fn = lambda: (lambda: (stops.append(1), run.update(on=False)))
    try:
        S._flat_reason = lambda: "a position is open"
        r_bad = local.post("/api/next/start/rearm", json={"confirm": "yes"})
        r_ph = phone.post("/api/next/start/rearm", json={"confirm": G.LIVE_PHRASE})
        r_nf = local.post("/api/next/start/rearm", json={"confirm": G.LIVE_PHRASE})
        check("Re-arm: a wrong phrase 400, the phone 403, not flat 400; nothing stopped, no START",
              r_bad.status_code == 400 and r_ph.status_code == 403 and r_nf.status_code == 400 and "Not flat" in r_nf.json()["error"]
              and not stops and not jobs, (r_bad.text, r_ph.text, r_nf.text))
        S._flat_reason = lambda: None
        r_ok = local.post("/api/next/start/rearm", json={"confirm": "i accept live risk"})
        check("Re-arm when flat: STOP once, then the START BOT arm step with the phrase (capitals do not matter)",
              r_ok.status_code == 200 and stops == [1] and jobs == [("arm", G.LIVE_PHRASE)], (r_ok.text, stops, jobs))
        G.sims_passed = lambda: {"sim1": False}
        run["on"], stops[:], jobs[:] = True, [], []
        r_sim = local.post("/api/next/start/rearm", json={"confirm": G.LIVE_PHRASE})
        check("Re-arm when the arm step could not run (Sim test not passed): refused BEFORE stopping",
              r_sim.status_code == 400 and not stops and not jobs, r_sim.text)
    finally:
        G.job_start, G.sims_passed, G.job_status, S._stop_fn, S._flat_reason = keep
    from engine import cloud_guard
    check("both new POSTs are PC-only (cloud_guard's blocked list)",
          "/api/next/start/onboard" in cloud_guard.CLOUD_BLOCKED and "/api/next/start/rearm" in cloud_guard.CLOUD_BLOCKED)
    js = open(os.path.join(ROOT, "web_next", "js", "next", "start.js"), encoding="utf-8").read()
    part = js.split("function newAcctLine")[1].split("function draw")[0]
    check("Start page: taps post 'onboard', Re-arm posts 'rearm' with the typed phrase, never 'arm' / 'go'; the plain note",
          "post('onboard'" in part and "post('rearm'" in part and "post('arm'" not in part and "post('go'" not in part
          and "Armed at the next START (you type the phrase)" in part and "Re-arm now" in part)


def main():
    tmp = tempfile.mkdtemp(prefix="le_onboard_")
    keep = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "bot_running")}
    keep_rp, keep_bot, env_keep = rapid.PATH, S._bot, os.environ.get("NINJATRADER_FOLDER")
    try:
        pure()
        nt = flow(tmp)
        api(tmp, nt)
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        rapid.PATH, S._bot, NA.STATE_PATH = keep_rp, keep_bot, None
        if env_keep is None:
            os.environ.pop("NINJATRADER_FOLDER", None)
        else:
            os.environ["NINJATRADER_FOLDER"] = env_keep
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
