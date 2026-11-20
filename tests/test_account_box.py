"""The Add account box (engine/account_box.py, owner 2026-11-19 "a typing thing on the dashboard").

    python -X utf8 -m tests.test_account_box          # ~5 s

Temp files and made-up names only (the test world of tests/test_accounts_cli): nothing armed, nothing routed.
  a. the page + status open on the PC and over the signed-in Tailscale link; refused from the home WiFi, Funnel, cloud mode
  b. a POST needs this page's header, JSON, same Origin (another web site / a bare form cannot press it), small body, rate limit
  c. Add = ADD_ACCOUNT.bat option 5: [OK] Rapid EOD 25K, DISARMED, allowlisted; NOT ADDED for a taken Name, a 2nd Rapid, no plan
  d. CHECK THE NAME when NinjaTrader does not show the Name; the status lists NinjaTrader Names not added yet; Names masked
  e. never arms: no arm route, the phrase in the body changes nothing; the other PC POSTs stay refused over the link
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RESULTS = []


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   -> {info!r}"[:400]))


def main() -> int:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from engine import account_box as AB, account_cli as AC, go as G, live_site as LS, rapid
    from tests import test_accounts_cli as TC
    from tests import test_phone_safety as TPS
    tmp = tempfile.mkdtemp(prefix="acctbox_")
    keep = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "bot_running")}
    keep_rp, env_nt, env_cloud = rapid.PATH, os.environ.get("NINJATRADER_FOLDER"), os.environ.pop("LE_CLOUD", None)
    try:
        TC.world(tmp)
        G.bot_running = lambda: False
        AB._S["log"] = os.path.join(tmp, "account_box.jsonl")
        AB._HITS.clear()
        app = FastAPI()
        LS.install(app)
        AB.install(app)
        link = dict(TPS.LINK_H)
        page_h = {"x-add-account": "1", "content-type": "application/json", "origin": "https://" + TPS.TS_HOST,
                  "sec-fetch-site": "same-origin"}
        c = TestClient(app, follow_redirects=False, client=(TPS.LINK_C, 0), base_url="https://" + TPS.TS_HOST)
        pc = TestClient(app, follow_redirects=False, client=("127.0.0.1", 50000), base_url="http://localhost:8766")
        wifi = TestClient(app, follow_redirects=False, client=("192.168.1.50", 50000), base_url="http://192.168.1.20:8766")
        pc_h = {"x-add-account": "1", "content-type": "application/json", "origin": "http://localhost:8766",
                "sec-fetch-site": "same-origin"}

        # a. who may open it
        p = c.get("/add-account/", headers=link)
        check("a. page opens over the signed-in Tailscale link", p.status_code == 200 and "Add account" in p.text
              and "no-store" in p.headers.get("cache-control", ""), p.status_code)
        check("a. page opens on the PC itself", pc.get("/add-account/").status_code == 200)
        check("a. refused from another device on the home WiFi", wifi.get("/add-account/").status_code == 403)
        check("a. refused through Funnel (internet)",
              c.get("/add-account/", headers={**link, "tailscale-funnel-request": "1"}).status_code == 403)
        nolog = {k: v for k, v in link.items() if k != "tailscale-user-login"}
        check("a. refused without a signed-in Tailscale user", c.get("/add-account/status", headers=nolog).status_code == 403)
        os.environ["LE_CLOUD"] = "1"
        check("a. refused in cloud mode", pc.get("/add-account/status").status_code == 403)
        os.environ.pop("LE_CLOUD", None)
        st = c.get("/add-account/status", headers=link).json()
        check("a. status: 4 plans, Rapid EOD 25K first", st.get("ok") and [x["id"] for x in st["plans"]][0] == "rapideod25"
              and len(st["plans"]) == 4, st)
        check("d. status masks Names to the last 4", all(a["name"].startswith("…") for a in st["accounts"])
              and not any(TC.L50 in str(a) for a in st["accounts"]), st["accounts"])
        check("d. status lists the NinjaTrader Name not added yet (and not the added ones)",
              [x["name"] for x in st["nt_new"]] == [TC.N25], st["nt_new"])

        # b. who may press it
        NR = "MFFUEVRPD250000001"
        good = {"plan": "rapideod25", "name": NR}
        for what, h, cl in (("no page header", {**link, "content-type": "application/json", "origin": "https://" + TPS.TS_HOST}, c),
                            ("another web site (Origin)", {**link, **page_h, "origin": "https://evil.example"}, c),
                            ("cross-site fetch", {**link, **page_h, "sec-fetch-site": "cross-site"}, c),
                            ("no Origin", {**link, **{k: v for k, v in page_h.items() if k != "origin"}}, c),
                            ("form post (not JSON)", {**link, **page_h, "content-type": "application/x-www-form-urlencoded"}, c),
                            ("home WiFi", pc_h, wifi)):
            r = cl.post("/add-account/add", headers=h, content=b'{"plan":"rapideod25","name":"' + NR.encode() + b'"}')
            check(f"b. refused: {what}", r.status_code == 403 and rapid.read() is None, (r.status_code, r.text[:200]))
        r = c.post("/add-account/add", headers={**link, **page_h}, content=b"x" * 5000)
        check("b. refused: body too long", r.status_code == 413 and rapid.read() is None, r.status_code)
        r = c.post("/add-account/arm", headers={**link, **page_h}, json={"confirm": "I ACCEPT LIVE RISK"})
        check("e. no arm button: /add-account/arm does not exist", r.status_code in (403, 404, 405), r.status_code)

        # c. the add itself
        r = c.post("/add-account/add", headers={**link, **page_h}, json={"name": NR}).json()
        check("c. NOT ADDED without a plan", r["ok"] is False and "Pick the plan" in r["lines"][0], r)
        r = c.post("/add-account/add", headers={**link, **page_h}, json={"plan": "rapideod25", "name": "  "}).json()
        check("c. NOT ADDED without a Name", r["ok"] is False and "Type the account Name" in r["lines"][0], r)
        r = c.post("/add-account/add", headers={**link, **page_h}, json={"plan": "rapideod25", "name": TC.L25}).json()
        check("c. NOT ADDED: the Name is ATLAS's 25K", r["ok"] is False and "already" in r["lines"][0]
              and "Nothing changed" in r["lines"][1] and rapid.read() is None, r)
        r = c.post("/add-account/add", headers={**link, **page_h},
                   json={**good, "confirm": "I ACCEPT LIVE RISK", "armed": True}).json()
        b = rapid.read()
        check("c. [OK] Rapid EOD 25K, DISARMED (the phrase in the body arms nothing), allowlisted",
              r["ok"] and r["lines"][0].startswith("[OK] Rapid EOD 25K") and b and b["account"] == NR
              and b["plan"] == "mffu_rapid_eod_25k" and b["armed"] is False and NR in TC.allowed(), (r, b))
        check("c. the reply prints the rules + slots + the next step (START BOT + the phrase yourself)",
              any("target +$1,500" in x for x in r["lines"]) and any("MFFU slots" in x for x in r["lines"])
              and "I ACCEPT LIVE RISK yourself" in r["lines"][-1], r["lines"])
        check("d. CHECK THE NAME: NinjaTrader does not show it", r.get("check_name") is True
              and any(x.startswith("- CHECK THE NAME") for x in r["lines"]), r["lines"])
        r2 = pc.post("/add-account/add", headers=pc_h, json={"plan": "rapideod25", "name": "MFFUEVRPD250000002"}).json()
        check("c. NOT ADDED: a 2nd Rapid (one Rapid only), from the PC itself", r2["ok"] is False and "one Rapid" in r2["lines"][0]
              and rapid.read()["account"] == NR, r2)
        r3 = c.post("/add-account/add", headers={**link, **page_h}, json={"plan": "builder25k", "name": TC.N25}).json()
        check("c. Builder 25K for the Name NinjaTrader shows: [OK], no CHECK THE NAME", r3["ok"] and not r3.get("check_name")
              and any(x["nt_account"] == TC.N25 and x["armed"] is False for x in TC.file_rows()), r3)
        st2 = c.get("/add-account/status", headers=link).json()
        check("d. status after: the Rapid row shows, not armed; nothing left to add", any(a["role"] == "rapid" and not a["armed"]
              for a in st2["accounts"]) and st2["nt_new"] == [], st2)
        check("e. still nothing armed anywhere", rapid.read()["armed"] is False and all(not x.get("armed") for x in TC.file_rows()))
        other = c.post("/api/next/start/arm", headers={**link, **page_h}, json={"confirm": "I ACCEPT LIVE RISK"})
        check("e. the PC's arm / start POSTs stay refused over the link", other.status_code == 403, other.status_code)
        log = open(AB._S["log"], encoding="utf-8").read()
        check("d. press log masks the Name", NR not in log and "…0001" in log, log[-300:])
        AB._HITS.clear()
        codes = [c.post("/add-account/add", headers={**link, **page_h}, json={"plan": "x", "name": "y"}).status_code for _ in range(9)]
        check("b. rate limit: the 9th press in 10 minutes is refused", codes[:8] == [200] * 8 and codes[8] == 429, codes)
        AC.remove(NR)
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        rapid.PATH = keep_rp
        AB._S["log"] = None
        AB._HITS.clear()
        if env_nt is None:
            os.environ.pop("NINJATRADER_FOLDER", None)
        else:
            os.environ["NINJATRADER_FOLDER"] = env_nt
        if env_cloud is not None:
            os.environ["LE_CLOUD"] = env_cloud
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RESULTS)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
