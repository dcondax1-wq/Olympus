"""The leads list as the leads team writes it (tools/web_leads.py): agency/leads/leads.json holds "leads" directly, or, once the list is big,
"leads": [] plus "files": ["towns/<town>.json", ...] (one file per town). One loader for every PC reader (email autopilot, caller portal,
postcards), the same rule as the Leads page (leads.js) and the factory (site_factory.load_leads): first row per id wins."""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public", "agency")
TOWN = re.compile(r"^towns/[a-z0-9-]+\.json$")


def _rj(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load(web: str = WEB) -> list:
    d = os.path.join(web, "leads")
    top = _rj(os.path.join(d, "leads.json"))
    top = top if isinstance(top, dict) else {}
    rows = list(top.get("leads") or [])
    for f in top.get("files") or []:
        if isinstance(f, str) and TOWN.match(f):
            part = _rj(os.path.join(d, f))
            rows += (part.get("leads") or []) if isinstance(part, dict) else []
    out, seen = [], set()
    for L in rows:
        if isinstance(L, dict) and isinstance(L.get("id"), str) and L["id"] and L["id"] not in seen:
            seen.add(L["id"])
            out.append(L)
    return out
