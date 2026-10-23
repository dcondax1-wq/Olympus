"""Scaling plan (tools/scale_plan.py research + engine/scale_plan.py status + the phone / PC pages): ladder math, step
detection from sample account states, the conditions / progress, the cloud and PC views, the stored research JSON, the
shared renderer (node --check, byte-identical copies, registered pages) and the API route.

  python -X utf8 -m tests.test_scale_plan            # ~10 s (+ the executors reproduce the stored studies)
  python -X utf8 -m tests.test_scale_plan --quick    # no executor check
Read-only: nothing in research/ is written.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from engine import scale_plan as SP  # noqa: E402

RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:300]}"), flush=True)


def row(strategy, plan, stage, **kw):
    r = {"id": kw.pop("id", f"{strategy}_{plan}_{stage}"), "strategy": strategy, "plan": plan, "stage": stage, "label": plan, "src": "test", **kw}
    r["type"] = SP.type_key(strategy, plan)
    return r


def math_checks():
    import scale_plan as TP
    check("ladder: 2 / 4 / 6 / 8 / 10 accounts", [len(TP.step_types(s["n"])) for s in TP.STEPS] == [2, 4, 6, 8, 10])
    check("step costs at the owner's / code prices", TP.step_cost(0) == 154.8 and TP.step_cost(1) == 285.39 and TP.step_cost(2) == 230.8,
          [TP.step_cost(s["n"]) for s in TP.STEPS])
    check("step 0 = LIT on the MFFU 50K + ATLAS on the MFFU 25K", TP.STEPS[0]["add"] == ["lit_b50", "atlas_b25"])
    # per-firm caps of the ladder at 10 accounts: MFFU 1x50K + 1x25K, Lucid <= 4 (cap 5), ATLAS never on 2 MFFU accounts
    ty = TP.step_types(4)
    firm = lambda f: sum(1 for t in ty if TP.TYPES[t]["firm"] == f)
    check("firm caps respected at 10 accounts", firm("MFFU") == 2 and firm("Lucid") <= 4 and ty.count("lit_b50") == 1, ty)
    # trigger_k: a synthetic account life
    L = [{"fees": [(0, 91.8)], "pays": [(30, 1200.0), (50, 1500.0)], "fund": [(10, 200, "alive")]},
         {"fees": [(5, 63.0)], "pays": [], "fund": [(20, 200, "alive")]}]
    k, fees, paid = TP.trigger_k(L, {"payouts_n": 1}, 1, 100, 285.39, 300.0)
    check("trigger: first payout + cash (300 + 1200 - 154.8 >= 285)", k == 30 and abs(fees - 154.8) < 1e-6 and paid == 1200.0, (k, fees, paid))
    k2, _, _ = TP.trigger_k(L, {"funded": 3}, 1, 100, 10.0, 300.0)
    check("trigger: 3 funded never with 2 accounts", k2 is None)
    k3, _, _ = TP.trigger_k(L, {"payouts_usd": 2000}, 1, 100, 10.0, 300.0)
    check("trigger: $2,000 paid out after the 2nd payout", k3 == 50, k3)
    L2 = L + [{"fees": [(0, 100.0)], "pays": [], "fund": [(10, 25, "lost")]}]
    k4, _, _ = TP.trigger_k(L2, {"payouts_n": 1}, 1, 100, 10.0, 300.0)
    check("trigger: waits 10 sessions after a lost funded account", k4 == 36, k4)
    risk = {t: {"eval": {"med": 300, "p95": 800, "max": 1000}, "funded": {"med": 200, "p95": 300, "max": 400}} for t in TP.TYPES}
    rs = TP.risk_step(1, risk)
    check("risk at once: typical / worst / ladder", rs["typical"] == 800 and rs["worst"] == 4000 and rs["ladder"] == 2 * 300 + 2 * 1000, rs)


def stored_checks():
    d = json.load(open(SP.PLAN_PATH, encoding="utf-8"))
    T = d["table"]
    check("scale.json: 5 rungs with every column", len(T) == 5 and all(k in T[0] for k in (
        "usd_month_h2", "usd_month_2025", "fees_month_h2", "risk", "fees_to_reach_h2", "months_h2", "reach_24m_2025")))
    check("scale.json: more accounts = more $ (2026-like)", all(T[i]["usd_month_h2"] < T[i + 1]["usd_month_h2"] for i in range(4)))
    check("scale.json: the bad year reaches the top less often", T[4]["reach_24m_2025"] < T[4]["reach_24m_h2"])
    check("scale.json: executors reproduced the stored studies", all(abs(a - b) <= max(1, 0.02 * abs(b)) for a, b in d["check"].values()), d["check"])
    check("scale.json: honest notes", len(d.get("honest") or []) >= 4)


def step_checks():
    P = SP.load_plan()
    money0 = {"fees": 91.8, "payouts": 0.0, "payouts_n": 0, "budget": 300.0}
    s = SP.status([row("LIT", "mffu_builder_50k", "eval"), row("ATLAS", "mffu_builder_25k", "planned", start="2026-10-26")], money0, P)
    check("step 0 in progress: 25K planned", s["step"] == 0 and s["step_done"] is False and s["next"]["progress"] == 50
          and "25K" in s["next"]["action"] and "2026-10-26" in s["next"]["when"], s.get("sentence"))
    rows = [row("LIT", "mffu_builder_50k", "eval"), row("ATLAS", "mffu_builder_25k", "eval")]
    s = SP.status(rows, {"fees": 154.8, "payouts": 0.0, "payouts_n": 0, "budget": 300.0}, P)
    c = {x["label"]: x for x in s["next"]["conditions"]}
    check("step 0 done -> next = step 1 (Lucid + FundedNext) on the first payout", s["step"] == 0 and s["step_done"] and s["next"]["n"] == 1
          and not s["next"]["ready"] and c["payouts received"]["have"] == 0, s.get("sentence"))
    check("cash = budget + payouts - fees", abs(s["money"]["cash"] - 145.2) < 0.01, s["money"])
    s = SP.status(rows, {"fees": 154.8, "payouts": 1200.0, "payouts_n": 1, "budget": 300.0}, P)
    check("step 1 ready after the first payout (cash covers $285)", s["next"]["ready"] and s["next"]["progress"] == 100, s["next"])
    rows4 = rows + [row("LIT", "lucid_pro_50k", "funded"), row("LIT", "fn_rapid_daily_50k", "eval")]
    rows4[0]["stage"] = "funded"
    s = SP.status(rows4, {"fees": 440.0, "payouts": 1400.0, "payouts_n": 2, "budget": 300.0}, P)
    check("step 1 detected (4 accounts), next = step 2, progress between 0 and 100", s["step"] == 1 and s["next"]["n"] == 2
          and 0 < s["next"]["progress"] < 100, s.get("sentence"))
    rows_failed = [dict(r) for r in rows4]
    rows_failed[3]["stage"] = "failed"
    check("a failed eval still holds its rung", SP.status(rows_failed, {"fees": 0, "payouts": 0, "payouts_n": 0, "budget": 300}, P)["step"] == 1)
    import datetime as dt
    lost = rows4 + [row("LIT", "lucid_pro_50k", "lost", lost_on=dt.date.today().isoformat())]
    s = SP.status(lost, {"fees": 440.0, "payouts": 9000.0, "payouts_n": 6, "budget": 300.0}, P)
    c = {x["label"]: x for x in s["next"]["conditions"]}
    check("a funded account lost this week blocks the next step", not c["no funded account lost in the last 2 weeks"]["ok"] and not s["next"]["ready"])
    import scale_plan as TP
    allr = [row(TP.TYPES[t]["strategy"], TP.TYPES[t]["plan"], "funded") for t in TP.step_types(4)]
    s = SP.status(allr, {"fees": 0, "payouts": 0, "payouts_n": 0, "budget": 300}, P)
    check("top of the ladder", s["step"] == 4 and s["next"]["n"] is None and s["next"]["progress"] == 100)


def overlay_checks():
    base = [row("LIT", "mffu_builder_50k", "eval"), row("ATLAS", "mffu_builder_25k", "planned")]
    r = SP.overlay(base, {"status": "passed"}, [{"id": "lucid1", "name": "LucidPro 50K", "plan": "LucidPro 50K (daily loss option on)", "kind": "funded"},
                                              {"id": "x", "error": "boom"}],
                   {"label": "Account B", "plan": "builder25k", "eval": {"status": "open"}})
    st = {(x["strategy"], x["plan"]): x["stage"] for x in r}
    check("overlay: PC eval passed, extra funded Lucid, account B open", st.get(("LIT", "mffu_builder_50k")) == "passed"
          and st.get(("LIT", "lucid_pro_50k")) == "funded" and st.get(("ATLAS", "mffu_builder_25k")) == "eval" and len(r) == 3, r)
    r2 = SP.overlay(base, None, [{"id": "mffu50k_funded", "plan": "Builder 50K", "kind": "funded"}], {"plan": "builder25k", "eval": {"status": "stuck"}})
    st = {(x["strategy"], x["plan"]): x["stage"] for x in r2}
    check("overlay: funded MFFU 50K (eval_life --to-funded) upgrades the 50K; stuck B = failed", st[("LIT", "mffu_builder_50k")] == "funded"
          and st[("ATLAS", "mffu_builder_25k")] == "failed", r2)
    check("plan ids from free text", SP.plan_id("Rapid Daily 50K") == "fn_rapid_daily_50k" and SP.plan_id("MFFU Builder 25K") == "mffu_builder_25k"
          and SP.plan_id("lucid") == "lucid_pro_50k" and SP.plan_id("?") is None)
    state = {"pc": {"acct": {"eval": {"start": "2026-10-19", "days": {"2026-10-19": 3200.0}}},
                    "second": {"route": {"account_b": {"plan": "builder25k", "eval": {"status": "open"}}}}}}
    v = SP.cloud_view(state)
    check("cloud view from a heartbeat: LIT 50K passed, size < 16 KB", not v.get("error") and v["accounts"][0]["stage"] == "passed"
          and len(json.dumps(v)) < 16000, v.get("error") or v.get("accounts"))
    check("PC view without a bot", not SP.pc_view(None).get("error") and SP.pc_view(None)["source"] == "business.json")


def page_checks():
    node = shutil.which("node")
    for f in ("tools/web_public/scalecore.js", "tools/web_public/scale.js", "web_next/js/next/scalecore.js"):
        if node:
            p = subprocess.run([node, "--check", os.path.join(ROOT, f)], capture_output=True, text=True)
            check(f"node --check {f}", p.returncode == 0, p.stderr)
    if node:
        p = subprocess.run([node, "--input-type=module", "--check"], input=open(os.path.join(ROOT, "web_next/js/next/scale.js")).read(),
                           capture_output=True, text=True)
        check("node --check web_next/js/next/scale.js (module)", p.returncode == 0, p.stderr)
        # render in node with a stub DOM: the hero sentence and every rung come out
        S = SP.status([row("LIT", "mffu_builder_50k", "eval"), row("ATLAS", "mffu_builder_25k", "eval")],
                      {"fees": 154.8, "payouts": 0, "payouts_n": 0, "budget": 300}, SP.load_plan())
        js = ("global.window={};global.document={getElementById:()=>null,createElement:()=>({}),head:{appendChild(){}}};"
              + open(os.path.join(ROOT, "tools/web_public/scalecore.js"), encoding="utf-8").read()
              + f";const el={{innerHTML:''}};window.ScaleUI.render(el,{json.dumps(S)});console.log(el.innerHTML);")
        p = subprocess.run([node, "-e", js], capture_output=True, text=True)
        h = p.stdout
        check("renderer: sentence, 5 rungs, the table", p.returncode == 0 and "You are at step 0 of 4" in h and h.count('class="sc-rung') == 5
              and "Accounts 2 / 4 / 6 / 8 / 10" in h, p.stderr or h[:200])
    a = open(os.path.join(ROOT, "tools/web_public/scalecore.js"), "rb").read()
    b = open(os.path.join(ROOT, "web_next/js/next/scalecore.js"), "rb").read()
    check("scalecore.js: phone and PC copies byte-identical", a == b)
    idx = open(os.path.join(ROOT, "tools/web_public/index.html"), encoding="utf-8").read()
    check("phone index loads scalecore.js then scale.js", 0 < idx.index("scalecore.js?v=") < idx.index('src="scale.js?v='))
    sc = open(os.path.join(ROOT, "tools/web_public/scale.js"), encoding="utf-8").read()
    check("phone page registered under Money", "g.id === 'money'" in sc and "VIEWS.scale" in sc)
    check("phone service worker cache bumped", int(__import__("re").search(r"le-public-v(\d+)", open(os.path.join(ROOT, "tools/web_public/sw.js"), encoding="utf-8").read()).group(1)) >= 26)
    routes = open(os.path.join(ROOT, "web_next/js/next/routes.js"), encoding="utf-8").read()
    app = open(os.path.join(ROOT, "web_next/js/app.js"), encoding="utf-8").read()
    ni = open(os.path.join(ROOT, "web_next/index.html"), encoding="utf-8").read()
    check("PC page: Data tab, app.js page, section", "id: 'scale'" in routes and "scale: scalePage" in app and 'id="page-scale"' in ni)


def api_checks():
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from engine import next_api
    except Exception as e:
        check("api: fastapi test client available", False, e)
        return
    app = FastAPI()
    app.include_router(next_api.router)
    r = TestClient(app).get("/api/next/scale")
    d = r.json()
    check("/api/next/scale 200 with step, next, table", r.status_code == 200 and "step" in d and "next" in d and len(d.get("table") or []) == 5, r.text[:200])
    check("/api/next/scale GET only", all(getattr(rt, "methods", {"GET"}) <= {"GET", "HEAD"} for rt in next_api.router.routes
                                          if getattr(rt, "path", "") == "/api/next/scale"))


def main(argv=None):
    quick = "--quick" in (argv or sys.argv[1:])
    math_checks()
    stored_checks()
    step_checks()
    overlay_checks()
    page_checks()
    api_checks()
    if not quick:
        try:
            import scale_plan as TP
            ok = TP.check()
            check("executors reproduce the stored LIT / ATLAS numbers", all(abs(a - b) <= max(1, 0.02 * abs(b)) for a, b in ok.values()), ok)
        except FileNotFoundError as e:
            print("[SKIP] executor check (unit caches missing):", e)
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
