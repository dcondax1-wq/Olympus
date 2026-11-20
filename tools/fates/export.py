"""FATES: shape the simulation into the page's JSON (tools/web_public/fates/fates.json) and Jarvis's card (jarvis.json).

Schema v1 (validate() checks it; the page reads nothing else):
  {v, app, built, t, seed, paths, threads, today, live{source, t, feed_day, bots{zlarior, atlas}, trades[]},
   calendar[ISO dates of the simulated sessions], periods{key: {label, from, to, days}},
   scenarios{"eval:<bot>:<period>": EVAL, "money:<period>": MONEY}, headline{...}, notes[]}
  EVAL  = {kind:"eval", bot, name, period, rules{target, mll, lock, dll, min_days, inactivity_days, price},
           start{profit, peak, floor, session, quiet_days}, horizon,
           summary{pass, fail, closed, stuck, open, p10, f10, dec10, p15, f15, slow_pass, pass_med, pass_cal_med, decide_med,
                   pass_hist[], no_keepalive{pass, closed, ...}, fresh{...}, money{6m, 12m, pay30, ...}},
           bands{q[], p[[progress per session]]},    progress = (balance - floor) / (target - floor): 0 = floor, 1 = target
           threads{o: "pfsco..." one letter per thread, b[[balance after each session, $]]}}
  MONEY = {kind:"money", period, horizon, goal, slots[{label, bot, plan, price, start}],
           books{"1".."6": summary}, bands{"1".."6": {q[], every, v[[...]]}},
           threads{ev[[k, slot, code, $, ...] flat per thread]}}  codes: 0 buy eval, 1 pass, 2 eval lost, 3 funded lost,
                                                                   4 payout, 5 five payouts (graduated)
"""
from __future__ import annotations

import json
import math

import numpy as np

from tools.fates.rules import CLOSED, FAIL, PASS, STUCK
from tools.fates.sim import book_cash, quantile_bands

OUT_CODES = {PASS: "p", FAIL: "f", STUCK: "s", CLOSED: "c", "open": "o"}
QS = (10, 25, 50, 75, 90)
MAX_BYTES = 1_000_000


def floors(hist: list[float], start, rules) -> list[float]:
    """The trailing floor after each session of one thread (EvalBook's rule, replayed from the balances)."""
    peak, floor, out = start.peak, start.floor if start.floor is not None else -rules.mll, []
    for b in hist:
        if b > floor + 1e-9:
            peak = max(peak, b)
            floor = min(max(floor, peak - rules.mll), rules.lock)
        out.append(floor)
    return out


def progress(hist: list[float], start, rules, horizon: int) -> list[float]:
    """Progress after each session (0 = the floor, 1 = the target), today's first; a decided thread keeps its last value."""
    fl = floors(hist, start, rules)
    f0 = start.floor if start.floor is not None else -rules.mll
    p = [(start.profit - f0) / (rules.target - f0)]
    for b, f in zip(hist, fl):
        p.append(max(0.0, (b - f) / max(1e-9, rules.target - f)))
    while len(p) < horizon + 1:
        p.append(p[-1])
    return p


def eval_block(src, period, rules, start, live_bot, res, res_noka, fresh, money, n_threads, horizon) -> dict:
    from tools.fates.sim import eval_summary
    P = np.array([progress(h, start, rules, horizon) for h in res["hist"]])
    summ = eval_summary(res, start, rules, res["cal"])
    nk = eval_summary(res_noka, start, rules, res["cal"])
    summ["no_keepalive"] = {k: nk[k] for k in ("pass", "fail", "closed", "open", "p10", "f10", "pass_med")}
    summ["fresh"] = fresh
    summ["money"] = money
    return {
        "kind": "eval", "bot": src.bot, "name": src.name, "period": period, "horizon": horizon,
        "rules": {k: getattr(rules, k) for k in ("name", "target", "mll", "lock", "dll", "min_days", "inactivity_days", "price")},
        "start": {"profit": start.profit, "peak": start.peak, "floor": start.floor, "session": start.session,
                  "quiet_days": live_bot.get("quiet_days"), "room": live_bot.get("room"), "to_target": live_bot.get("to_target"),
                  "source": live_bot.get("source")},
        "summary": summ,
        "bands": {"q": list(QS), "p": quantile_bands(P, QS)},
        "threads": {"o": "".join(OUT_CODES[o] for o in res["out"][:n_threads]),
                    "b": [[int(round(x)) for x in h] for h in res["hist"][:n_threads]]},
    }


def money_block(period, slots, R, cal, goal, n_threads, every=5) -> dict:
    from tools.fates.sim import money_summary
    books, bands = {}, {}
    for n in range(1, len(slots) + 1):
        idx = list(range(n))
        books[str(n)] = money_summary(R, idx, cal, goal)
        C = book_cash(R, idx)
        C = np.concatenate([np.zeros((C.shape[0], 1)), C], axis=1)        # today = 0
        bands[str(n)] = {"q": list(QS), "every": every, "v": [[int(round(x)) for x in row] for row in quantile_bands(C, QS, every)]}
    ev = []
    for p in R[:n_threads]:
        flat = []
        for j, sl in enumerate(p):
            for k, code, amt in sl["events"]:
                flat.extend((int(k), j, int(code), int(round(amt))))
        ev.append(flat)
    return {"kind": "money", "period": period, "horizon": len(R[0][0]["cash"]), "goal": goal,
            "slots": [{"label": s.label, "bot": s.src.bot, "plan": s.rules.key, "price": s.rules.price,
                       "start": "today's eval" if s.start is not None else f"buy in {s.offset} sessions" if s.offset else "buy today"}
                      for s in slots],
            "books": books, "bands": bands, "threads": {"ev": ev}}


def single_money(R, j, cal, goal) -> dict:
    from tools.fates.sim import money_summary
    m = money_summary(R, [j], cal, goal)
    return {k: m[k] for k in ("6m", "12m", "pay30", "first_pay_med", "any_pay", "ahead", "behind", "funded", "payouts")}


def headline(doc: dict) -> dict:
    """The numbers Jarvis and the write-up lead with: today's pass odds (2026 sample), and the 2021-25 line."""
    S = doc["scenarios"]
    h = {}
    for bot in ("zlarior", "atlas"):
        for per in ("2026", "2021-25", "H2"):
            k = f"eval:{bot}:{per}"
            if k in S:
                s = S[k]["summary"]
                h[f"{bot}_{per}"] = {"pass": s["pass"], "fail": s["fail"], "pass_med": s["pass_med"], "p10": s["p10"], "f10": s["f10"]}
    return h


def jarvis_card(doc: dict) -> dict:
    """docs/JARVIS_APPS.md contract: v, name, status, up to 3 kpis, up to 3 lines (<= 120 chars), t, open, theme."""
    S = doc["scenarios"]
    z, a = S["eval:zlarior:2026"]["summary"], S["eval:atlas:2026"]["summary"]
    zr, ar = S["eval:zlarior:2021-25"]["summary"], S["eval:atlas:2021-25"]["summary"]
    m = S["money:2026"]["books"]["2"]["12m"]
    lvl = "ok" if z["pass"] >= 50 else "warn" if z["pass"] >= 30 else "bad"
    return {
        "v": 1, "name": "FATES",
        "status": {"level": lvl, "label": f"Zlarior pass odds {pct(z['pass'])}"[:48]},
        "kpis": [{"label": "Zlarior pass", "value": pct(z["pass"]), "delta": f"-{pct(z['fail'])} fail"[:16]},
                 {"label": "ATLAS pass", "value": pct(a["pass"]), "delta": f"-{pct(a['fail'])} fail"[:16]},
                 {"label": "$/mo (2 accts)", "value": f"${m['pm_p50']:,}"}],
        "lines": [f"Pass odds this eval: {pct(z['pass'])} (Zlarior, 2026 sample; 2021-25: {pct(zr['pass'])})"[:120],
                  f"ATLAS: {pct(a['pass'])} (2026), {pct(ar['pass'])} (2021-25)"[:120],
                  f"{doc['paths']:,} futures from today, MFFU rules, paper only"[:120]],
        "t": int(doc["t"]), "open": "#zlarior", "theme": THEME,
    }


THEME = "#14110e"


def pct(x) -> str:
    """'67%': rounded half up, like the page's Math.round."""
    return f"{math.floor(float(x) + 0.5)}%"


def validate(doc: dict) -> list[str]:
    """Schema and size checks. -> list of problems (empty = good)."""
    bad = []
    for k in ("v", "app", "built", "t", "seed", "paths", "threads", "today", "live", "calendar", "periods", "scenarios", "headline"):
        if k not in doc:
            bad.append(f"missing {k}")
    if bad:
        return bad
    for key, s in doc["scenarios"].items():
        if s.get("summary_only"):
            if "summary" not in s and "books" not in s:
                bad.append(f"{key}: no numbers")
            continue
        if s["kind"] == "eval":
            for k in ("rules", "start", "summary", "bands", "threads", "horizon"):
                if k not in s:
                    bad.append(f"{key}: missing {k}")
            t = s.get("threads", {})
            if len(t.get("o", "")) != len(t.get("b", [])):
                bad.append(f"{key}: outcome / thread count differ")
            if any(len(b) > s["horizon"] for b in t.get("b", [])):
                bad.append(f"{key}: a thread is longer than the horizon")
            if set(t.get("o", "")) - set("pfsco"):
                bad.append(f"{key}: unknown outcome letter")
            for k in ("pass", "fail", "pass_med", "p10", "f10", "dec10", "p15", "f15", "slow_pass", "money"):
                if k not in s.get("summary", {}):
                    bad.append(f"{key}: summary missing {k}")
        elif s["kind"] == "money":
            for n in map(str, range(1, len(s["slots"]) + 1)):
                if n not in s["books"] or n not in s["bands"]:
                    bad.append(f"{key}: book {n} missing")
            if any(len(e) % 4 for e in s["threads"]["ev"]):
                bad.append(f"{key}: an event list is not in fours")
        else:
            bad.append(f"{key}: unknown kind")
    size = len(json.dumps(doc, separators=(",", ":")))
    if size > MAX_BYTES:
        bad.append(f"too big: {size} bytes")
    return bad


def dump(doc: dict, path: str) -> int:
    s = json.dumps(doc, separators=(",", ":"), allow_nan=False)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(s)
    return len(s)
