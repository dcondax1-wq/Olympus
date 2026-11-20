"""The concept-page form for the site factory (day-cities3): prints {"caller_html": ...} for tools/site_factory_agency.json.

  python -m tools.caller.siteform                 posts to /api/consent on the concept site itself (cloudflare/consent.js), the default
The site factory fills the hidden inputs lead_id and business per site. No secret and no PC address is in the markup.
It refuses placeholder agency details (YOUR AGENCY, (555) ...): run it where agency/config.json is filled, or pass real settings.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "tools.caller"

from . import config as C  # noqa: E402
from . import consent as K  # noqa: E402


PLACEHOLDER = re.compile(r"YOUR |\(555\)|555-01|the owner|example\.com", re.I)


def build(endpoint: str = "/api/consent", s: dict | None = None) -> dict:
    """endpoint: the concept site's own Pages Function (default, same origin: no PC address on a public page), or a full https URL.
    A Tailscale (.ts.net) address is refused: the publish privacy pass masks it, and it maps the owner's devices."""
    ep = endpoint.rstrip("/")
    if ".ts.net" in ep.lower() or not (ep == "/api/consent" or re.fullmatch(r"https://[a-z0-9.-]+(:\d+)?(/[a-z0-9/_-]*)?", ep)):
        raise SystemExit("the endpoint must be /api/consent (the site's own Cloudflare function) or an https URL that is not a .ts.net address")
    s = s or C.settings()
    shown = " ".join(str(s.get(k, "")) for k in ("agency_name", "callback_number", "owner_first_name"))
    if PLACEHOLDER.search(shown) or not s.get("agency_name"):
        raise SystemExit("fill agency/config.json first (agency name, phone, your name): the consent text must name the real agency and number")
    return {"caller_html": K.consent_form_html(s, None, ep), "caller_button": K.BUTTON,
            "caller_fields": {"lead_id": "the Leads list id (osm-n...)", "business": "the business name"}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="/api/consent")
    a = ap.parse_args(argv)
    print(json.dumps(build(a.endpoint), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
