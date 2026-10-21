"""Bot Brain checks (engine/brain.py, engine/brain_api.py): the Brain must say exactly what the engine decided, use no
future bar, fit its size budgets and stay read-only.

    python -X utf8 -m tests.test_brain            # every 2026 session at 16:00 + intraday polls on 4 days (~2.5 min)
    python -X utf8 -m tests.test_brain --quick    # 30 sessions + 2 intraday days (~40 s)

1. Day-end replay (16:00 ET, the PC bot's poll: 5m + 1m bars closed by then, early mode): the setups marked "filled" are
   exactly the LIT backtest's trades of that day (tools/lit_final run with live_model.json "lit": entry time, side, entry
   price); every setup without a signal names the rule the engine's own check fails first (lit_brief.reject_reason, or
   the 1-trade-a-day rule when an earlier setup filled); every engine signal of the day appears with its plan.
2. Intraday (a target day, a no-fill day, a rejected-only day, a Monday-rule day): the stage follows the engine's state
   at each poll (open position -> In trade, entry routed now -> Entry, tapped limit -> 1m CISD wait, armed -> Limit armed).
3. No look-ahead: the Brain at time t built from the full files equals the one built from files cut at t.
4. Sizes: full < 120 KB, phone cut < 16 KB on every replayed session; heartbeat / live.json carry it under 64 KB.
5. The thought log persists to data/brain-like JSONL and reads back; the API routes answer and are GET only.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from engine import brain  # noqa: E402

ET = brain.ET
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:400]})" if info and not cond else ""), flush=True)


def at(day, hh, mm):
    d = dt.date.fromisoformat(day) - dt.timedelta(days=1 if hh >= 18 else 0)
    return int(dt.datetime.combine(d, dt.time(hh, mm), ET).timestamp())


def strip(b):
    b = dict(b)
    b.pop("build_ms", None)
    return json.dumps(b, sort_keys=True, default=str)


def day_end(days, REF):
    from engine import lit_brief
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    P = {**__import__("engine.lit", fromlist=["DEFAULTS"]).DEFAULTS, **P}
    by_day = collections.defaultdict(list)
    for t in REF:
        by_day[t["day"]].append(t)
    filled_ok = filled_bad = rule_ok = 0
    rule_bad, sig_missing, sizes, cnt = [], [], [], collections.Counter()
    for d in days:
        keep = {}
        b = brain.replay(d, _keep=keep)
        if b.get("error"):
            rule_bad.append((d, b["error"]))
            continue
        M, C, R = keep["M"], keep["C"], keep["R"]
        sizes.append((len(json.dumps(b, default=str)), len(json.dumps(brain.compact(b), separators=(",", ":"), default=str))))
        got = sorted((s["trade"]["entry_t"], s["dir"], round(float(s["trade"]["entry"]), 2)) for s in b["setups"] if s["status"] == "filled" and s.get("trade"))
        want = sorted((int(t["entry_t"]), int(t["dir"]), round(float(t["entry_px"]), 2)) for t in by_day.get(d, []))
        if got == want:
            filled_ok += 1
        else:
            filled_bad += 1
            rule_bad.append((d, "filled", got, want))
        zi = {f"{z['i']}:{z['dir']}": z for z in C if z["day"] == d}
        for s in b["setups"]:
            cnt[s["status"]] += 1
            if s["status"] in ("rejected", "blocked"):
                z = zi[s["id"]]
                why = lit_brief.reject_reason(M, z, P)
                exp = "day" if s["rule"] == "day" else (why[0] if why else None)
                if s["status"] == "rejected" and why is not None and why[0] == s["rule"]:
                    rule_ok += 1
                elif s["status"] == "blocked" and exp == "day":
                    rule_ok += 1
                else:
                    rule_bad.append((d, s["hm"], s["status"], s.get("rule"), why))
        sig_t = {(int(x["t"]), int(x["dir"])) for x in R["signals"] if x["day"] == d}
        planned = {(int(s["plan"]["armed_t"]), int(s["dir"])) for s in b["setups"] if s.get("plan")}
        if sig_t - planned:
            sig_missing.append((d, sorted(sig_t - planned)))
    n_sess = len(days)
    check(f"day-end: filled setups = the backtest's trades on {filled_ok}/{n_sess} sessions", filled_bad == 0, rule_bad[:5])
    check(f"day-end: every rejected / blocked setup names the engine's failing rule ({rule_ok} setups)",
          not [r for r in rule_bad if r[1] != "filled"], [r for r in rule_bad if r[1] != "filled"][:5])
    check("day-end: every engine signal appears with its plan", not sig_missing, sig_missing[:5])
    check(f"sizes: full < 120 KB (max {max(s[0] for s in sizes)}), phone cut < 16 KB (max {max(s[1] for s in sizes)})",
          max(s[0] for s in sizes) < 120_000 and max(s[1] for s in sizes) <= 16_000)
    print("   setup statuses:", dict(cnt))
    return cnt


def intraday(days, REF):
    by_day = collections.defaultdict(list)
    for t in REF:
        by_day[t["day"]].append(t)
    for d in days:
        a, z = brain.day_bounds(d)
        times = set(range(at(d, 1, 55), at(d, 16, 0) + 1, 300))
        for t in by_day.get(d, []):
            times |= set(range(int(t["entry_t"]) - 600, int(t["entry_t"]) + 600, 60))
        bad, seen, n = [], collections.Counter(), 0
        for now in sorted(times):
            keep = {}
            b = brain.replay(d, now + 3, _keep=keep)
            n += 1
            st = keep["res"]["state"]
            k = b["stage"]["key"]
            seen[k] += 1
            pend = [p for p in keep["R"].get("pending") or []]
            if st.get("position"):
                exp = "trade"
            elif st.get("enter_now"):
                exp = "entry"
            elif pend:
                exp = "cisd1m" if any(p.get("tapped_t") for p in pend) else "limit"
            else:
                exp = None
            if exp and k != exp:
                bad.append((b["at"], k, exp))
            if not exp and k in ("trade", "entry", "limit", "cisd1m"):
                bad.append((b["at"], k, "no engine state for it"))
            if b.get("trade") and st.get("position") and abs(b["trade"]["entry"] - st["position"]["entry"]) > 1e-6:
                bad.append((b["at"], "trade entry differs"))
        check(f"intraday {d}: the stage follows the engine on {n} polls ({dict(seen)})", not bad, bad[:5])


def no_lookahead(cases):
    import pandas as pd  # noqa: F401
    D = brain._replay_data()
    full = dict(D)
    bad = []
    for d, hh, mm in cases:
        t = at(d, hh, mm)
        b1 = brain.replay(d, t)
        try:
            cut = full["df5"][full["df5"]["time"] + 300 <= t].reset_index(drop=True)
            brain._RP.update(df5=cut, T5=cut["time"].values, b1=full["b1"].slice(0, int(np.searchsorted(full["b1"].t, t))))
            b2 = brain.replay(d, t)
        finally:
            brain._RP.update(full)
        if strip(b1) != strip(b2):
            bad.append((d, hh, mm))
    check(f"no look-ahead: the Brain at t from the full files = from files cut at t ({len(cases)} times)", not bad, bad)


def log_and_transport():
    tmp = tempfile.mkdtemp(prefix="le_brain_")
    try:
        lg = brain.BrainLog(tmp)
        d = "2026-10-13"
        b1 = brain.build(*_live(d, at(d, 5, 50)), log=lg)
        b2 = brain.build(*_live(d, at(d, 6, 10)), log=lg)
        p = os.path.join(tmp, f"{d}.jsonl")
        rows = [json.loads(x) for x in open(p, encoding="utf-8")]
        keys = [r["key"] for r in rows]
        check("log: persisted as JSONL, one row per fact, no duplicates", len(keys) == len(set(keys)) and len(rows) >= 10, len(rows))
        check("log: the 05:50 lines keep their first-seen time; the 06:10 poll added the entry",
              any(r["kind"] == "entry" for r in b2["log"]) and not any(r["kind"] == "entry" for r in b1["log"]))
        back = brain.read_day_log(d, tmp)
        check("log: read back newest first", back and back[0]["t"] >= back[-1]["t"] and len(back) == len(rows))
        # heartbeat / live.json carry the phone cut
        from engine import heartbeat, live_publish

        class Bot:
            brain = b2
        hb = heartbeat._brain(Bot())
        hbn = len(json.dumps(hb, separators=(",", ":"), default=str))
        check("heartbeat: brain block = compact, < 16 KB", hb and hb.get("compact") and hbn <= 16_000, hbn)
        lj = live_publish.build({"running": True, "brain": hb, "model_state": "x"}, now=int(time.time()), lm={})
        n = len(json.dumps(lj, separators=(",", ":"), default=str))
        check(f"live.json: carries pc.brain with stage + waiting + checks, {n} bytes < 64 KB",
              (lj.get("pc") or {}).get("brain", {}).get("stage", {}).get("waiting") and n < 64 * 1024, n)
        big = json.loads(json.dumps(hb))
        big["log"] = big["log"] * 200
        lj2 = live_publish.fit({"pc": {"brain": big}, "accounts": []}, max_bytes=20_000)
        check("live.json: fit() trims the Brain log first", len(json.dumps(lj2)) <= 20_000 and (lj2["pc"].get("brain") or {}).get("stage"))
        # API
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from engine import brain_api
        old = brain_api._bot
        brain_api._bot = lambda: Bot()
        try:
            app = FastAPI()
            app.include_router(brain_api.router)
            cl = TestClient(app)
            r = cl.get("/api/next/brain")
            check("api /api/next/brain: the bot's Brain", r.status_code == 200 and r.json().get("stage", {}).get("key") == "trade", r.text[:200])
            r = cl.get("/api/next/brain?compact=1")
            check("api ?compact=1: the phone cut", r.status_code == 200 and r.json().get("compact"))
            r = cl.get("/api/next/brain/day/2026-10-13?hm=06:10&frames=1")
            j = r.json()
            check("api /brain/day: replay at 06:10 = in trade, with the scrubber's frames", r.status_code == 200 and j["stage"]["key"] == "trade"
                  and len(j.get("frames") or []) > 200, (r.status_code, j.get("error")))
            check("api /brain/day: same answer as the live Brain of that minute", strip({**j, "frames": None, "replay": None, "mode": None})
                  == strip({**b2, "frames": None, "replay": None, "mode": None, "log": j["log"]}))
            r = cl.get("/api/next/brain/days")
            check("api /brain/days: 2026 sessions with their trade", r.status_code == 200 and len(r.json()["days"]) > 150)
            check("api /brain/day: bad date -> 400", cl.get("/api/next/brain/day/2026-13-99").status_code == 400)
            Bot.brain = None
            r = cl.get("/api/next/brain")
            check("api: no Brain yet -> empty with the latest day to replay", r.json().get("empty") and r.json().get("latest_day"))
            check("api: GET only", all(getattr(rt, "methods", {"GET"}) <= {"GET", "HEAD"} for rt in brain_api.router.routes))
        finally:
            brain_api._bot = old
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _live(day, t):
    """(res, P, now, keep, ctx) as the PC bot hands them to build() at t (the replay's inputs)."""
    from engine import lit_live
    D = brain._replay_data()
    P, ls = brain._live_params()
    cut5 = D["df5"].iloc[:int(np.searchsorted(D["T5"] + 300, t, side="right"))]
    cut5 = cut5[cut5["time"] >= t - 75 * 86400]
    cut1 = D["b1"].slice(0, int(np.searchsorted(D["b1"].t + 60, t, side="right")))
    jf = int(np.searchsorted(D["b1"].t, t - t % 60))
    forming = (int(D["b1"].t[jf]), float(D["b1"].o[jf])) if jf < len(D["b1"].t) and int(D["b1"].t[jf]) == t - t % 60 else None
    keep = {}
    res = lit_live.run(cut5, P, one_min=cut1, now=t, forming=forming, early=True, keep=keep)
    ctx = {"lit_sizing": ls, "learning": None, "news": brain._news(day),
           "eval_state": {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "days_traded": 0},
           "eval_clock": {"session": 1, "limit": 10, "status": "open", "to_target": 3000.0, "room": 2000.0,
                          "text": "replay: sized as a fresh eval (session 1 of 10, $3,000 to go)"}}
    return res, P, t, keep, ctx


def keep_is_readonly(days):
    """lit_live.run(keep=) returns the same result as without it."""
    from engine import lit_live
    bad = []
    for d, hh, mm in days:
        res, P, t, keep, ctx = _live(d, at(d, hh, mm))
        D = brain._replay_data()
        cut5 = D["df5"].iloc[:int(np.searchsorted(D["T5"] + 300, t, side="right"))]
        cut5 = cut5[cut5["time"] >= t - 75 * 86400]
        cut1 = D["b1"].slice(0, int(np.searchsorted(D["b1"].t + 60, t, side="right")))
        jf = int(np.searchsorted(D["b1"].t, t - t % 60))
        forming = (int(D["b1"].t[jf]), float(D["b1"].o[jf])) if jf < len(D["b1"].t) and int(D["b1"].t[jf]) == t - t % 60 else None
        r2 = lit_live.run(cut5, P, one_min=cut1, now=t, forming=forming, early=True)
        if json.dumps(res["trades"], default=str) != json.dumps(r2["trades"], default=str) or \
                json.dumps(res["state"], default=str, sort_keys=True) != json.dumps(r2["state"], default=str, sort_keys=True):
            bad.append(d)
    check(f"lit_live.run(keep=) changes nothing ({len(days)} sessions)", not bad, bad)


def main() -> int:
    quick = "--quick" in sys.argv
    t0 = time.time()
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    from tools import lit_final as F
    REF = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    sess = [s["day"] for s in brain.sessions_2026()]
    days = sess if not quick else sorted(set(sess[:20] + [sess[i] for i in np.linspace(20, len(sess) - 1, 10).astype(int)]))
    day_end(days, [t for t in REF if t["day"] in set(days)])
    intraday(["2026-10-13", "2026-10-09"] if quick else ["2026-10-13", "2026-10-09", "2026-10-16", "2026-10-12"], REF)
    no_lookahead([("2026-10-13", 4, 0), ("2026-10-13", 5, 47), ("2026-10-13", 6, 4), ("2026-10-09", 10, 30), ("2026-10-16", 15, 20)])
    keep_is_readonly([("2026-10-13", 16, 0), ("2026-10-13", 6, 10), ("2026-10-12", 16, 0)])
    log_and_transport()
    ok = all(RES)
    print(f"bot brain: {sum(RES)}/{len(RES)}", "ALL PASS" if ok else "FAILED", f"({time.time() - t0:.0f} s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
