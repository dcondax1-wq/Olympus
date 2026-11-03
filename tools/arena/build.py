"""Write ARENA's site files: events.json (the verifiable trading events) and jarvis.json (the Jarvis card).

  python -m tools.arena.build --site site      from a built site (its data.json + home.json) -> site/arena/
  python -m tools.arena.build --demo           the demo (tools/arena/fixture.py) -> tools/web_public/arena/

The cloud publish runs publish(out) through tools/build_web_dashboard.py, guarded: a failure only prints a line and the
page's demo files stay (they say DEMO). The phone adds its own events (Planner, Obsidian, Kalshi, quests) on top.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.arena import events as EV, fixture, score as S  # noqa: E402

NY = ZoneInfo("America/New_York")
PAGE = os.path.join(ROOT, "tools", "web_public", "arena")
THEME = "#0a0710"
KIND = "olympus-arena"
MAX_EVENTS = 1500
MAX_CARD = 8 * 1024
STALE_AFTER = 3 * 86400            # the site publishes every 15-30 min on market days; ranks move slowly


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def dumps(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def et(now: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(now), NY)


def build(data: dict | None, home: dict | None, now: float, demo: bool = False, extra: list | None = None) -> dict:
    today = et(now).date().isoformat()
    ev = EV.from_site(data, home, today) + list(extra or [])
    ev.sort(key=lambda e: (e["day"], e.get("t", 0), e["id"]))
    return {"v": 1, "kind": KIND, "t": int(now), "today": today, "demo": bool(demo), "theme": THEME, "events": ev[-MAX_EVENTS:],
            "sources": {"site": "data.json: perf.status (Surface heartbeat), accounts (trades, evals, payouts)"}}


def server_quests(doc: dict, sc: dict, R: dict, hour: float) -> list:
    """Today's quests as the site can see them (nothing linked): the trading ones verified from the site's events."""
    day = doc["today"]
    today = [e for e in doc["events"] if e["day"] == day]
    ran = any(e["kind"] == "bot_day" for e in today)
    broke = any(e["kind"] == "rule_broken" for e in today)
    out = []
    for q in S.pick_quests(day, {}, R):
        if q["id"] == "bots_watch":
            done = ran
        elif q["id"] == "hands_off":
            done = hour >= 16 and ran and not broke
        else:
            done = None                                          # the phone checks it
        out.append({**q, "done": done})
    return out


def jarvis_card(doc: dict, R: dict | None = None) -> dict:
    R = R or S.load_rules()
    sc = S.score(doc["events"], R, doc["today"])
    e = et(doc["t"])
    qs = server_quests(doc, sc, R, e.hour + e.minute / 60)
    up = sc["streaks"]["uptime"]
    if doc.get("demo"):
        level, label = "off", "Demo data"
    else:
        level, label = "ok", f"{sc['rank']['name']} - level {sc['level']}"
    qline = "Today: " + ", ".join(f"{q['title']} ({'done' if q['done'] else 'open' if q['done'] is False else 'on the phone'})" for q in qs)
    lines = [qline[:120], f"Bot uptime streak: {up['cur']} market day{'s' if up['cur'] != 1 else ''} (best {up['best']})",
             "XP from the site's trading events; the phone adds Planner, notes, Kalshi"]
    nxt = sc["next"]
    return {"v": 1, "name": "ARENA", "status": {"level": level, "label": label[:48]},
            "kpis": [{"label": "Rank", "value": sc["rank"]["name"]},
                     {"label": "XP", "value": f"{sc['xp']:,}", **({"delta": f"{nxt['need']:,} to go"[:16]} if nxt else {})},
                     {"label": "Labours", "value": f"{sc['earned']} of 12"}],
            "lines": [x[:120] for x in lines], "t": int(doc["t"]), "open": "#quests", "theme": THEME, "stale_after": STALE_AFTER}


def write(out_dir: str, doc: dict) -> dict:
    body, card = dumps(doc), dumps(jarvis_card(doc))
    if len(card.encode()) > MAX_CARD:
        raise ValueError(f"jarvis.json is {len(card.encode())} bytes (cap {MAX_CARD})")
    _write(os.path.join(out_dir, "events.json"), body)
    _write(os.path.join(out_dir, "jarvis.json"), card)
    return {"events": len(doc["events"]), "bytes": len(body.encode()), "jarvis": len(card.encode())}


def demo() -> dict:
    return build(fixture.data(), fixture.home(), fixture.NOW, demo=True, extra=fixture.phone_events())


def publish(site: str, now: float | None = None) -> dict | None:
    """<site>/arena/events.json + jarvis.json from <site>/data.json (+ home.json). None when the site has no data.json."""
    data = _load(os.path.join(site, "data.json"))
    if not isinstance(data, dict):
        return None
    home = _load(os.path.join(site, "home.json"))
    doc = build(data, home if isinstance(home, dict) else None, now if now is not None else time.time())
    return write(os.path.join(site, "arena"), doc)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", help="a built site folder (data.json, home.json)")
    ap.add_argument("--now", type=float, help="unix seconds (default: now)")
    ap.add_argument("--demo", action="store_true", help="write the demo files to tools/web_public/arena/")
    a = ap.parse_args(argv)
    if a.demo:
        print("demo ->", PAGE, write(PAGE, demo()))
        return 0
    if not a.site:
        ap.error("--site or --demo")
    res = publish(a.site, a.now)
    print("arena ->", os.path.join(a.site, "arena"), res if res else "(no data.json: the demo stays)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
