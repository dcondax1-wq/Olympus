"""The concept-page form for the site factory (day-cities3): prints {"caller_html": ...} for tools/site_factory_agency.json.

  python -m tools.caller.siteform --endpoint https://<pc>.<tailnet>.ts.net:10000      (the address CALLER_ON.bat shows)
The site factory fills the hidden inputs lead_id and business per site. No secret is in the markup: only the public endpoint.
Privacy: the endpoint shows this PC's Tailscale name on every concept page, so name the PC something neutral in Tailscale first
(e.g. olympus-caller), never a person's name.
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


def build(endpoint: str, s: dict | None = None) -> dict:
    if not re.fullmatch(r"https://[a-z0-9.-]+(:\d+)?", endpoint.rstrip("/")):
        raise SystemExit("the endpoint must be https://host[:port] (the Funnel address), nothing else")
    s = s or C.settings()
    return {"caller_html": K.consent_form_html(s, None, endpoint.rstrip("/") + "/consent"), "caller_button": K.BUTTON,
            "caller_fields": {"lead_id": "the Leads list id (osm-n...)", "business": "the business name"}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    a = ap.parse_args(argv)
    print(json.dumps(build(a.endpoint), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
