"""AGENCY: the local-business website machine (owner 2026-11-14: "I want a website building machine").

Find local businesses that need a website (OpenStreetMap, free), build each one a fast demo site, write the pitch,
keep the pipeline in the OLYMPUS Agency page. Python stdlib only. Nothing here places a call or texts anyone. The one sender is
agency/autopilot (email only, OFF until EMAIL_SETUP.bat + the typed phrase SEND EMAILS, docs/EMAIL_AUTOPILOT.md); the rest prepares the words.

    python -m agency.run --city "Fort Collins, CO"        the whole day's batch (leads -> 3 demo sites -> pitch kits -> CRM data)
    python -m agency.leads --city "Fort Collins, CO"      only the lead list (CSV + JSON)
    python -m agency.build_site --leads FILE --id ID      one demo site (folder + zip + self-check)
    python -m agency.pitch --leads FILE --id ID           one pitch kit (one-pager, email, 30-second phone opener)
    python -m agency.publish --leads FILE                 the CRM data (tools/web_public/agency/leads.json)

Docs: docs/AGENCY.md. Tests: python -X utf8 -m tests.test_agency
"""
from __future__ import annotations

import os

__version__ = "1.0"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE_DIR = os.environ.get("AGENCY_CACHE") or os.path.join(HERE, "cache")       # gitignored
OUT_DIR = os.environ.get("AGENCY_OUT") or os.path.join(HERE, "out")             # gitignored: the owner's real batches
TEMPLATES = os.path.join(HERE, "templates")
CRM_DIR = os.path.join(ROOT, "tools", "web_public", "agency")

# One clear User-Agent for every request (OSM / Overpass / Nominatim ask for it). No personal data in it, ever.
UA = f"OLYMPUS-agency/{__version__} (local-business website lead finder; stdlib Python; one request at a time)"
ATTRIBUTION = "Business data (c) OpenStreetMap contributors, ODbL 1.0 (openstreetmap.org/copyright)"


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path
