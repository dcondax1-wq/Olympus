"""ARENA's rules engine in Python: the twin of tools/web_public/arena/rules.js (same rules.json, same output).

score(events, R, today) -> {xp, level, into, level_xp, rank, next, streaks, labours, earned, counts, bySrc, log, n}
pick_quests(day, ctx, R) -> the day's quests
Pure: no I/O, no clock. tests/test_arena.py runs both on the same fixture and compares the JSON.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES_PATH = os.path.join(ROOT, "tools", "web_public", "arena", "rules.json")
DAY_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_rules(path: str = RULES_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def add_days(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


def weekday(day: str) -> int:
    """0 Sunday .. 6 Saturday (JavaScript's getUTCDay)."""
    return (dt.date.fromisoformat(day).weekday() + 1) % 7


def day_number(day: str) -> int:
    return (dt.date.fromisoformat(day) - dt.date(1970, 1, 1)).days


def is_market_day(day: str) -> bool:
    return 1 <= weekday(day) <= 5


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def clean_events(events, R) -> list:
    seen, out = set(), []
    for e in events if isinstance(events, list) else []:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not e["id"] or e["id"] in seen:
            continue
        if not DAY_RX.match(str(e.get("day"))) or e.get("kind") not in R["xp"]:
            continue
        seen.add(e["id"])
        t = _num(e.get("t"))
        out.append({"id": e["id"], "day": e["day"], "kind": e["kind"], "src": str(e.get("src") or R["xp"][e["kind"]]["src"]),
                    "t": t if t is not None else 0, "note": e["note"][:160] if isinstance(e.get("note"), str) else ""})
    out.sort(key=lambda e: (e["day"], e["t"], e["id"]))
    return out


def _step(s: dict, d: dict, e: dict) -> None:
    if d["type"] == "seq":
        if e["kind"] in d["kinds"]:
            s["cur"] += 1
            s["best"] = max(s["best"], s["cur"])
            s["last"] = e["day"]
        elif e["kind"] in d["breaks"]:
            s["cur"] = 0
            s["last"] = e["day"]
        return
    if e["kind"] not in d["kinds"] or s["last"] == e["day"]:
        return
    s["cur"] = s["cur"] + 1 if s["last"] and add_days(s["last"], 1) == e["day"] else 1
    s["last"] = e["day"]
    s["best"] = max(s["best"], s["cur"])


def _rank_of(xp, R) -> int:
    i = 0
    for j, r in enumerate(R["ranks"]):
        if xp >= r["xp"]:
            i = j
    return i


def _labour_value(l, counts, st, xp, R):
    m = l.get("metric") or {}
    if m.get("count"):
        return counts.get(m["count"], 0)
    if m.get("best"):
        return (st.get(m["best"]) or {}).get("best", 0)
    if m.get("rank"):
        r = next((x for x in R["ranks"] if x["id"] == m["rank"]), None)
        return 1 if r and xp >= r["xp"] else 0
    return 0


def score(events, R, today: str) -> dict:
    evs = clean_events(events, R)
    used, counts, by_src, log = {}, {}, {}, []
    st = {s["id"]: {"cur": 0, "best": 0, "last": None} for s in R["streaks"]}
    defs = {l["id"]: l for l in R["labours"]}
    labours = [{"id": l["id"], "n": l["n"], "name": l["name"], "task": l["task"], "goal": l["goal"], "value": 0, "earned": False,
                "day": None} for l in R["labours"]]
    xp = xp_today = 0
    for e in evs:
        rule, key = R["xp"][e["kind"]], (e["kind"], e["day"])
        n = used.get(key, 0)
        used[key] = n + 1
        got = rule["xp"] if n < rule["cap_day"] else 0
        xp += got
        if e["day"] == today:
            xp_today += got
        by_src[e["src"]] = by_src.get(e["src"], 0) + got
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
        for d in R["streaks"]:
            _step(st[d["id"]], d, e)
        for l in labours:
            if not l["earned"] and _labour_value(defs[l["id"]], counts, st, xp, R) >= l["goal"]:
                l["earned"], l["day"] = True, e["day"]
        log.append({"id": e["id"], "day": e["day"], "kind": e["kind"], "src": e["src"], "xp": got,
                    "capped": got == 0 and rule["xp"] > 0, "label": rule["label"], "note": e["note"]})
    for l in labours:
        l["value"] = min(l["goal"], _labour_value(defs[l["id"]], counts, st, xp, R))
    streaks = {}
    for d in R["streaks"]:
        s = st[d["id"]]
        alive = d["type"] == "seq" or bool(s["last"] and (s["last"] == today or add_days(s["last"], 1) == today))
        streaks[d["id"]] = {"id": d["id"], "name": d["name"], "unit": d["unit"], "cur": s["cur"] if alive else 0, "best": s["best"],
                            "last": s["last"]}
    ri, lx = _rank_of(xp, R), R["level_xp"]
    nxt = R["ranks"][ri + 1] if ri + 1 < len(R["ranks"]) else None
    return {"xp": xp, "xpToday": xp_today, "level": 1 + xp // lx, "into": xp % lx, "level_xp": lx, "rank": {**R["ranks"][ri], "i": ri},
            "next": {**nxt, "need": nxt["xp"] - xp} if nxt else None, "streaks": streaks, "labours": labours,
            "earned": sum(1 for l in labours if l["earned"]), "counts": counts, "bySrc": by_src, "log": log[-60:][::-1],
            "n": len(evs)}


def pick_quests(day: str, ctx: dict | None, R) -> list:
    c = ctx or {}
    has = {"market": is_market_day(day), "planner": bool(c.get("planner")), "habits": bool(c.get("habits")),
           "vault": bool(c.get("vault")), "kalshi": bool(c.get("kalshi"))}
    ok = lambda q: (not has[q["needs"][1:]]) if q["needs"].startswith("!") else has[q["needs"]]  # noqa: E731
    pool = [q for q in R["quests"] if ok(q)]
    lane = lambda x: [q for q in pool if q["lane"] == x]  # noqa: E731
    life = lane("life")
    k = day_number(day) % len(life) if life else 0
    n = max(1, min(3, int(_num(c.get("tasksToday")) or 0) or 1))
    picked = (lane("trade") + life[k:] + life[:k] + lane("setup"))[:3]
    return [{"id": q["id"], "title": q["title"].replace("{n}", str(n)), "text": q["text"].replace("{n}", str(n)), "src": q["src"],
             "lane": q["lane"], "n": n} for q in picked]
