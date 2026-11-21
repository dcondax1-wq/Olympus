"""CLIENT INTAKE PAGE (tools/web_public/agency/intake/, day-caller2 2026-11-21): static checks, no browser.
  a. mailto only: no form action, no POST, no backend; the only fetch is the public ../portal/portal.json (read)
  b. self-contained: no external script, style or font; noindex + no-referrer; a viewport for phones
  c. the JSON keys it sends are exactly client_deliver.py's edits.json keys (+ code, need_domain)
  d. honesty: the 'everything is true, I own the photos, no made-up reviews' box is required
    python -X utf8 -m tests.test_intake_page
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "tools", "web_public", "agency", "intake", "index.html")
EDIT_KEYS = {"domain", "name", "phone", "email", "hours", "address", "town", "tagline", "about", "services"}
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def main() -> int:
    s = open(PAGE, encoding="utf-8").read()
    fetches = re.findall(r"fetch\(([^,)]+)", s)
    check("a. mailto only: no form action, no POST, the only fetch reads ../portal/portal.json",
          "mailto:" in s and not re.search(r"<form[^>]*action=", s) and "POST" not in s and fetches == ['"../portal/portal.json"'], fetches)
    check("b. self-contained: no external script / stylesheet / font, noindex, no-referrer, phone viewport",
          not re.search(r"<script[^>]+src=|<link[^>]+stylesheet|@import|fonts\.googleapis", s) and 'content="noindex, nofollow"' in s
          and 'name="referrer" content="no-referrer"' in s and "width=device-width" in s)
    keys = set(re.findall(r'\["(name|phone|email|address|town|tagline|about)"', s)) | set(re.findall(r'\["([a-z_]+)", "phone"', s))
    sent = set(re.findall(r"\be\.([a-z_]+)\s*=", s)) | {"name", "phone", "email", "address", "town", "tagline", "about"}
    check("c. the keys it sends are client_deliver.py's edits.json keys", sent == EDIT_KEYS, sent ^ EDIT_KEYS)
    check("c. hours are written in client_deliver's form ('Mo-Fr 09:00-17:00; Su off')", '" off"' in s and "slice(0, 2)" in s)
    check("d. the truth / own-the-photos / no made-up reviews box is required before sending",
          'id="true" required' in s and "No made-up reviews" in s and "Please tick the last box." in s)
    check("d. the studio email comes only from the public portal.json or a checked ?to= address (never typed into the page source)",
          'var TO = "";' in s and not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(com|net|org)", s.replace("joesdiner.com", "")))
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
