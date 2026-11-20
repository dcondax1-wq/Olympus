"""The email autopilot's tiny card for the PC report (lead 2026-11-20: no posts of its own on ntfy, the PC hit the 250/day per-IP cap).
run.py writes data/agency_mail/summary.json after each pass; tools/pc_report.py lays it into its existing "le-live-ext" block as "am"
(LEAD_WIRES patch), the site's pc_feed.js merges it into the lite live.json and agency/outreach/ shows it. Numbers only, < 120 bytes:
  {t, m: mode off|dry|live, n: new today, c: cap, f: follow-ups today, r: replies today, i: interested, s: never-again, q: waiting}"""
from __future__ import annotations

import json
import os
import time

KEYS = (("t", "t"), ("m", "mode"), ("n", "new"), ("c", "cap"), ("f", "followup"), ("r", "replies_today"), ("i", "interested"), ("s", "suppressed"), ("q", "queue"))


def path(root: str) -> str:
    return os.path.join(root, "data", "agency_mail", "summary.json")


def tiny(counts: dict) -> dict:
    out = {short: counts.get(long) for short, long in KEYS if counts.get(long) is not None}
    if out.get("m") not in ("off", "dry", "live"):
        out["m"] = "off"
    return {k: (v if k == "m" else int(v or 0)) for k, v in out.items()}


def write_card(counts: dict, root: str) -> bool:
    try:
        p = path(root)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(dict(tiny(counts), kind="agency_mail_pub"), fh, separators=(",", ":"))
        os.replace(p + ".tmp", p)
        return True
    except OSError:
        return False


def read_card(p: str | None = None, now: float | None = None, root: str | None = None):
    """the card for pc_report (its ext block "am"): only when written in the last 2 days; None otherwise. Never raises."""
    try:
        p = p or path(root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("kind") != "agency_mail_pub" or (now or time.time()) - os.path.getmtime(p) > 2 * 86400:
            return None
        return {k: d[k] for k, _ in KEYS if k in d}
    except Exception:  # noqa: BLE001
        return None
