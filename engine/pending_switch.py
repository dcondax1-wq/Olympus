"""One-tap switch requests from the phone (day-zerotouch2 2026-11-24, owner: "a new strategy goes from my YES on the phone to live
at my next START with zero extra steps").

The phone (remote command {"cmd": "switch", "key": "<key>"}) only QUEUES a switch in data/pending_switches.json (gitignored). Nothing
changes then. The next START BOT shows the queue as its FIRST line, and after the ONE phrase the owner types anyway
(I ACCEPT LIVE RISK) applies each one through the switch's own setter (which checks the phrase again); then the queue is empty.
A START without the phrase applies nothing and keeps the queue. Nothing arms without that phrase.

  combo_on     ATLAS on Zlarior's 50K (engine/combo50k.set_on: also needs the Decide card answered yes)
  blitz_on     arm BLITZ on its own 25K (engine/go.arm_c: needs BLITZ's 25K set first)
  lane:<id>    a lane made by tools/new_strategy.py (engine/lanes/<id>.py set_on)
  python -X utf8 -m engine.pending_switch            the queue
Tests: tests/test_zerotouch2.py f.
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "pending_switches.json")
MAX_AGE_S = 14 * 86400                      # a request older than two weeks is dropped (the owner asks again)
FIXED = {"combo_on": "ATLAS on Zlarior's 50K (the combo)", "blitz_on": "BLITZ armed on its own 25K"}


def keys() -> dict:
    """{key: label} of every switch the phone may queue."""
    out = dict(FIXED)
    try:
        from . import lanes
        for lid in lanes.ids():
            m = lanes.load(lid)
            if m:
                out[f"lane:{lid}"] = str(getattr(m, "LABEL", lid))[:80]
    except Exception:  # noqa: BLE001
        pass
    return out


def load(path: str | None = None, now=None) -> list:
    now = time.time() if now is None else now
    try:
        with open(path or PATH, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:  # noqa: BLE001
        return []
    return [x for x in (d.get("items") if isinstance(d, dict) else None) or []
            if isinstance(x, dict) and x.get("key") and now - float(x.get("t") or 0) <= MAX_AGE_S]


def _save(items, path: str | None = None):
    p = path or PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as fh:
        json.dump({"v": 1, "items": items}, fh, indent=1)
    from .fsutil import replace
    replace(p + ".tmp", p)


def request(key: str, via: str = "phone", cid: str | None = None, path: str | None = None, now=None) -> dict:
    """Queue one switch (idempotent: the same key twice = one entry). Never applies anything."""
    now = time.time() if now is None else now
    key = str(key or "").strip().lower()
    known = keys()
    if key not in known:
        return {"ok": False, "error": f"unknown switch {key[:30]!r} (allowed: {', '.join(known)})"}
    items = load(path, now)
    if any(x["key"] == key for x in items):
        return {"ok": True, "say": f"already queued: {known[key]}; it turns on at your next START after the phrase", "dup": True}
    items.append({"key": key, "t": int(now), "via": str(via)[:20], "id": str(cid or "")[:64]})
    _save(items, path)
    return {"ok": True, "say": f"queued: {known[key]}. It turns on at your next START after the phrase (nothing changed now)"}


def first_line(path: str | None = None, now=None) -> str:
    """START's FIRST line ('' when the queue is empty)."""
    items, known = load(path, now), keys()
    if not items:
        return ""
    return ("[..] Your phone asked to switch on: " + "; ".join(known.get(x["key"], x["key"]) for x in items)
            + ". The phrase you type below turns them on too.")


def _apply_one(key: str, phrase: str) -> dict:
    if key == "combo_on":
        from . import combo50k, go
        acct = str((go._read(go.CFG) or {}).get("lit") or "").strip()
        return combo50k.set_on(acct, phrase) if acct else {"ok": False, "error": "no Zlarior 50K saved yet"}
    if key == "blitz_on":
        from . import go
        return go.arm_c(phrase)
    if key.startswith("lane:"):
        from . import lanes
        m = lanes.load(key[5:])
        return m.set_on(phrase) if m else {"ok": False, "error": "the lane is not there any more"}
    return {"ok": False, "error": "unknown switch"}


def apply_all(phrase: str, path: str | None = None, now=None, apply_one=None) -> list:
    """After START's typed phrase: apply every queued switch, then empty the queue. -> lines to print. Wrong phrase = nothing."""
    from .go import LIVE_PHRASE, typed_phrase
    items = load(path, now)
    if not items or typed_phrase(str(phrase or "")) != LIVE_PHRASE:
        return []
    known, out = keys(), []
    for x in items:
        try:
            r = (apply_one or _apply_one)(x["key"], phrase)
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        lbl = known.get(x["key"], x["key"])
        out.append(f"[OK] Switched on from your phone's request: {lbl}" + (f" ({r.get('say')})" if r.get("say") else "")
                   if r.get("ok") else f"[FIX] Not switched on: {lbl}: {str(r.get('error'))[:160]}")
    _save([], path)
    return out


def main() -> int:
    print(first_line() or "No switch is waiting for START.")
    print("Switches the phone may ask for: " + ", ".join(keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
