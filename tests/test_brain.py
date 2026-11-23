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
6. Glance (engine/brain_glance.py, the phone Brain page's "All bots" tab): Zlarior + ATLAS (+ Rapid EOD only when its lane
   is set up), never BLITZ; an armed setup shows its trigger; $ risk / $ target of the open trade; under its byte budget and
   inside the PC's 15-minute status (tools/pc_report.lite, < 3,900 bytes); read-only; never raises.
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


def glance_checks(REF):
    """engine/brain_glance.py: what the phone's All-bots tab shows (a replayed Brain on the heartbeat fixture of test_live_publish)."""
    import copy
    from engine import brain_glance as G, live_publish as lp
    from tests.test_live_publish import hb_payload, account_c_block
    from tools import pc_report as R
    # 2026-11-22: the heartbeat's route.account_b (engine/account_b.info) has no "armed" key; a LIVE + enabled account B passed
    # the adapter's live gate (armed + phrase + NINJATRADER_LIVE + allowlist) = armed. The phone showed "NOT armed" before.
    check("6. ATLAS armed on the phone = a LIVE account B whose live gate passed (enabled); SIM / PAPER / gate refused / explicit false = not",
          G._ab_armed({"kind": "LIVE", "enabled": True}) is True and G._ab_armed({"kind": "LIVE", "enabled": False}) is False
          and G._ab_armed({"kind": "SIM", "enabled": True}) is False and G._ab_armed({"kind": "PAPER", "enabled": True}) is False
          and G._ab_armed({"armed": False, "kind": "LIVE", "enabled": True}) is False and G._ab_armed({}) is False)
    t_arm, b_arm = None, None
    for tr in [t for t in REF if t["day"] == "2026-10-13"][:1]:
        for t in range(int(tr["entry_t"]) - 3 * 3600, int(tr["entry_t"]) + 1, 300):
            b = brain.replay("2026-10-13", t + 3)
            if (b.get("stage") or {}).get("key") in ("limit", "cisd1m"):
                t_arm, b_arm = t + 3, b
                break
    check("glance: a replayed 2026-10-13 poll with a LIT limit armed was found", b_arm is not None)
    if b_arm is None:
        return
    hb = hb_payload(t_arm)
    hb["brain"] = brain.compact(b_arm)
    hb["account_c"] = account_c_block(t_arm)
    hb["blitz"] = {"label": "BLITZ (paper shadow)", "eval": {"room": 900}}
    before = copy.deepcopy(hb)
    p = lp.build(hb, t_arm)
    g = (p.get("pc") or {}).get("glance") or {}
    ids = [b.get("id") for b in g.get("bots") or []]
    check("glance: in live.json pc.glance, bots Zlarior + ATLAS only (no BLITZ, no Rapid EOD while it is off)", ids == ["lit", "atlas"]
          and "blitz" not in json.dumps(g).lower(), ids)
    L = (g.get("bots") or [{}])[0]
    check("glance: Zlarior on + armed + LIVE, the stage, what it waits for", L.get("on") is True and L.get("armed") is True and L.get("mode") == "LIVE"
          and L.get("stage") and L.get("wait"), L)
    arm = L.get("arm") or []
    check("glance: the armed setup says what triggers it (limit price, then the 1m close)", arm and any("comes back to" in a.get("trig", "")
          or "1-minute close" in a.get("trig", "") for a in arm), arm)
    lv = L.get("lv") or []
    check("glance: the nearest levels (label, price, points away; at most 3 above + 3 below)", 0 < len(lv) <= 6
          and all(isinstance(r[0], str) and isinstance(r[1], float) for r in lv), lv)
    check("glance: the last thought-log lines (newest first, at most 4)", 0 < len(L.get("log") or []) <= 4, L.get("log"))
    pos = L.get("pos") or {}
    check("glance: the open trade with $ risk and $ target (29.75 pts x $2 x 6 = $357; 120.25 pts = $1,443)",
          pos.get("risk_usd") == 357 and pos.get("tgt_usd") == 1443 and pos.get("side") == "SHORT", pos)
    check("glance: today's $ and the room left (with the max loss) from the board card", L.get("room") is not None and L.get("mll") == 2000, L)
    check("glance: under its byte budget", G.size(g) <= G.MAX_BYTES, G.size(g))
    check("glance: read-only (the heartbeat payload is not changed)", hb == before)
    # Rapid EOD shows only when its lane is set up
    hb2 = copy.deepcopy(before)
    hb2["acct"]["accounts"] = [{"id": "rapid", "name": "Rapid", "plan_rules": {"start": 50000.0, "mll": 2000.0},
                                "eval": {"days": {"2026-10-12": 300.0}, "anchor": {"floor": 48100.0}}, "day_pnl": -40.0, "running": True,
                                "account": {"label": "SIM"}}]
    hb2["health"]["accounts"] = [{"id": "rapid", "enabled": True, "armed": False, "label": "SIM", "day_pnl": -40.0}]
    g2 = G.build(hb2, (lp.build(hb2, t_arm).get("board")))
    rp = next((b for b in g2.get("bots") or [] if b.get("id") == "rapid"), None)
    check("glance: Rapid EOD appears when its lane is set up (today -$40, room $50,300 - $48,100 = $2,200 of $2,000)",
          rp is not None and rp.get("day") == -40 and rp.get("room") == 2200 and rp.get("mll") == 2000 and rp.get("on") is True, rp)
    # long texts are cut to fit
    hb3 = copy.deepcopy(before)
    for r in hb3["brain"].get("log") or []:
        r["text"] = "x " * 300
    g3 = G.build(hb3, None)
    check("glance: long thought lines are cut to fit the budget", G.size(g3) <= G.MAX_BYTES, G.size(g3))
    # the PC's 15-minute status carries it and still fits
    snap = {"t": t_arm, "hb": hb, "hb_t": t_arm - 60, "server": True, "nt": True, "market_open": True, "entry_hours": True, "mode": "LIVE",
            "live": p}
    core, exts = R.posts(snap)
    lt = R.merged(snap)
    check("glance: on the PC's 15-minute status (the ext post, merged back to pc.glance) and every post still fits 3,900 bytes",
          (lt.get("pc") or {}).get("glance", {}).get("bots") and all(R._size(x) <= R.MAX_STATUS_BYTES for x in [core, *exts]), R._size(lt))
    check("glance: never raises on junk", G.build(None) is None and isinstance(G.build({"brain": "x", "second": 3, "acct": []}), dict))
    # v2 (day-nqdash3 2026-11-21, the NQ Brain page's PC fields): LIT checks / blocks / price, ATLAS lobes / dll / level distances, the longer log
    px = (hb.get("brain") or {}).get("price")
    chk = L.get("chk")
    check("glance v2: Zlarior's latest setup checks [passed, total] and the last price", G.VERSION == 2 and isinstance(chk, list) and len(chk) == 2
          and 0 <= chk[0] <= chk[1] and chk[1] > 0 and L.get("px") == px, (chk, L.get("px"), px))
    hb4 = copy.deepcopy(before)
    now4 = int(t_arm)
    hb4["second"] = {"t": now4, "strategies": {
        "ema_lon_vix": {"short": "EMA", "route": True, "state": {"stage": "done", "text": "Done for today (1 trade a day): long 04:10 ET -> TARGET"},
                        "brain": {"levels": [{"name": "EMA50", "px": px + 12.5, "stage": "watch"}], "log": [{"t": now4 - 900, "text": "EMA long filled"}]}},
        "macd_sweep": {"short": "MACD", "route": True, "state": {"stage": "armed", "text": "Signal (short): 5m CISD after a pullback"},
                       "brain": {"levels": [{"name": "PDH", "px": px - 20.0, "stage": "watch"}, {"name": "old", "px": 1.0, "stage": "taken"}],
                                 "log": [{"t": now4 - 60 * i, "text": f"MACD line {i}"} for i in range(1, 9)]}},
        "sr_nyreclaim": {"short": "S/R", "route": True, "state": {"stage": "off", "text": "Outside its hours: entries 09:30-11:00"}},
        "lit_asia": {"short": "Asia", "state": {"stage": "waiting", "text": "candidate, paper"}, "brain": {"log": [{"t": now4, "text": "not routed"}]}}}}
    card = dict((lp.build(hb4, t_arm).get("board") or {}).get("atlas") or {}, today_pnl=-150.0, dll=600.0)
    card.pop("dll_used", None)
    g4 = G.build(hb4, {"lit": (lp.build(hb4, t_arm).get("board") or {}).get("lit"), "atlas": card})
    A = next((b for b in g4.get("bots") or [] if b.get("id") == "atlas"), {})
    lob = {x["id"]: x["st"] for x in A.get("lobes") or []}
    check("glance v2: ATLAS's 3 lobes from its strategies' state (EMA done, MACD armed, S/R off; the paper candidate is not a lobe)",
          lob == {"ema": "done", "macd": "armed", "sr": "off"}, A.get("lobes"))
    check("glance v2: ATLAS's daily loss: $600 limit, $150 used (today -$150, no dll_used on the card)", A.get("dll") == 600 and A.get("dll_used") == 150, A)
    lv4 = {r[0]: r[2] for r in A.get("lv") or []}
    check("glance v2: ATLAS's levels carry points from the last price (EMA50 +12.5, PDH -20.0), a taken level left out",
          lv4.get("EMA EMA50") == 12.5 and lv4.get("MACD PDH") == -20.0 and not any("old" in k for k in lv4), A.get("lv"))
    check("glance v2: still under its byte budget with the new fields", G.size(g4) <= G.MAX_BYTES, G.size(g4))
    gl = G.logs(hb4)
    check("glance v2: the longer log (8 lines a bot, newest first; routed strategies only)", gl and len(gl.get("atlas") or []) == 8
          and gl["atlas"][0][1].startswith("EMA") is False and "not routed" not in str(gl) and len(gl.get("lit") or []) <= 8, gl)
    check("glance v2: logs() never raises on junk", G.logs(None) is None and G.logs({"brain": 3, "second": "x"}) is None)
    snap4 = dict(snap, hb=hb4, live=lp.build(hb4, t_arm))
    core4, exts4 = R.posts(snap4)
    xs = [k for e in exts4 for k in (e.get("x") or {})]
    check("glance v2: the PC's status carries 'glog' in an ext post, every post <= 3,900 bytes, at most 2 ext posts",
          "glog" in xs and all(R._size(x) <= R.MAX_STATUS_BYTES for x in [core4, *exts4]) and len(exts4) <= R.EXT_PARTS, (xs, [R._size(x) for x in [core4, *exts4]]))
    e1 = [{"x": {"glog": {"lit": [["09:00", "a"]]}, "glance": {"v": 2}}}]
    e2 = [{"x": {"glog": {"lit": [["09:05", "b"]]}, "glance": {"v": 2, "x": 1}}}]
    check("glance v2: a new log line alone does not spend an ntfy post (ext_hash leaves glog out, as it does glance)", R.ext_hash(e1) == R.ext_hash(e2))


def main() -> int:
    quick = "--quick" in sys.argv
    t0 = time.time()
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    from tools import lit_final as F
    REF = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    sess = [s["day"] for s in brain.sessions_2026()]
    # the reference backtest covers its baseline's sessions only (lit_final.SESS, to 2026-10-16); the replay runs on every session the data
    # has, so a day past the reference's last one would count its real trades as "extra" fills. Compare only the days both cover.
    sess = [d for d in sess if d <= F.SESS[-1]]
    days = sess if not quick else sorted(set(sess[:20] + [sess[i] for i in np.linspace(20, len(sess) - 1, 10).astype(int)]))
    day_end(days, [t for t in REF if t["day"] in set(days)])
    intraday(["2026-10-13", "2026-10-09"] if quick else ["2026-10-13", "2026-10-09", "2026-10-16", "2026-10-12"], REF)
    no_lookahead([("2026-10-13", 4, 0), ("2026-10-13", 5, 47), ("2026-10-13", 6, 4), ("2026-10-09", 10, 30), ("2026-10-16", 15, 20)])
    keep_is_readonly([("2026-10-13", 16, 0), ("2026-10-13", 6, 10), ("2026-10-12", 16, 0)])
    log_and_transport()
    glance_checks(REF)
    ok = all(RES)
    print(f"bot brain: {sum(RES)}/{len(RES)}", "ALL PASS" if ok else "FAILED", f"({time.time() - t0:.0f} s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
