"""The agency's PUBLIC web address (lead 2026-11-21, privacy H1): every link a business sees (email, postcard, QR, the caller portal's
"email them the link") is built from ONE setting, tools/site_factory_agency.json {"public_base": "https://..."} (day-cities3 exports the
concept sites to that neutral host), or the sender's own "site_base" setting. There is NO default: with no public base nothing is sent.
Never the owner's handle or his personal dashboards: any text or URL containing a BANNED piece is refused (tests: test_agency_autopilot,
test_postcards)."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "tools", "site_factory_agency.json")
BANNED = ("dcondax", "github.io/jarvis", "ts.net")
# the inbound-only wording (lead 2026-11-20 17:34 + day-caller): voice only, no "or text", no "any time"
CALL_LINE = "Questions? Call {agency_number}: our AI assistant answers."


def banned(text) -> str:
    """the first banned piece found in text ('' = clean)"""
    t = str(text or "").lower()
    return next((b for b in BANNED if b in t), "")


def settings(cfg_path: str | None = None) -> dict:
    """tools/site_factory_agency.json: {"public_base": "https://...", "agency_number": "(301) ..."} (public facts only, never a secret)"""
    try:
        with open(cfg_path or CFG, encoding="utf-8") as f:
            j = json.load(f)
        return j if isinstance(j, dict) else {}
    except (OSError, ValueError):
        return {}


def public_base(override: str = "", cfg_path: str | None = None) -> str:
    """the https base every public link starts with, or '' (= not set, or not allowed)"""
    v = str(override or "").strip() or str(settings(cfg_path).get("public_base") or "").strip()
    v = v.rstrip("/")
    return v if v.startswith("https://") and len(v) > 12 and not banned(v) else ""


def agency_number(override: str = "", cfg_path: str | None = None) -> str:
    return str(override or settings(cfg_path).get("agency_number") or "").strip()


def call_line(number: str) -> str:
    n = str(number or "").strip()
    return CALL_LINE.format(agency_number=n) if n else ""
