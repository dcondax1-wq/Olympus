"""DNC SCRUB for the human caller list (day-caller2 2026-11-21). Runs on the PC after `python -m agency.portal build`, before the list
is published. Scrubbing means checking the list against the National Do Not Call Registry, so no listed number is ever dialed.

  python -m agency.dnc_scrub              scrub tools/web_public/agency/portal/calllist.json in place
  python -m agency.dnc_scrub --stamp      after a new download: record today's date + the area codes found (the files below)

The registry copy: download your area codes as text files from telemarketing.donotcall.gov (free for up to 5 area codes a year) into
<OLYMPUS_HOME>/caller/registry/<area>.txt (one 10-digit number per line). The AI caller reads the same folder.
The registry data never leaves the PC: the published list only loses rows, never shows why, and never contains registry numbers.

What it does to every row with a phone:
  - on the registry                         -> row removed + lead id added to the never-again list (agency_never.json, every channel)
  - area code not downloaded (e.g. 667, 8xx) -> row removed for now ("not scrubbed"), back on the list once that area code is downloaded
  - the download is older than 31 days      -> NOTHING is published as scrubbed: the list gets "dnc": "STALE" and exits 1
Rows without a phone stay (the caller finds the number on Google Maps; it is scrubbed at the next build, before anyone dials it).
The list header gets {"dnc": "scrubbed", "dnc_date": "<download date>", "dnc_removed": n, "dnc_held": n}.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = os.path.join(ROOT, "tools", "web_public", "agency", "portal", "calllist.json")
MAX_AGE_DAYS = 31


def home() -> str:
    return os.environ.get("OLYMPUS_HOME") or os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def reg_dir(h=None) -> str:
    return os.path.join(h or home(), "caller", "registry")


def rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, p)


def ten(phone) -> str:
    d = re.sub(r"\D", "", str(phone or ""))
    d = d[1:] if len(d) == 11 and d.startswith("1") else d
    return d if len(d) == 10 else ""


def stamp(h=None, today: dt.date | None = None) -> dict:
    d = reg_dir(h)
    os.makedirs(d, exist_ok=True)
    codes = sorted(m.group(1) for n in os.listdir(d) if (m := re.fullmatch(r"(\d{3})\.txt", n)))
    meta = {"downloaded": (today or dt.date.today()).isoformat(), "area_codes": codes}
    wj(os.path.join(d, "meta.json"), meta)
    return meta


def load_registry(h=None) -> tuple:
    """(meta, {area: set(10-digit)})"""
    d = reg_dir(h)
    meta = rj(os.path.join(d, "meta.json"), {}) or {}
    numbers = {}
    for ac in meta.get("area_codes") or []:
        try:
            with open(os.path.join(d, f"{ac}.txt"), encoding="utf-8") as f:
                numbers[str(ac)] = {x for x in (ten(line) for line in f) if x}
        except OSError:
            pass
    return meta, numbers


def scrub(doc: dict, h=None, today: dt.date | None = None) -> tuple:
    """(new_doc, report). Never raises on a bad registry: a missing or stale copy marks the list STALE instead."""
    today = today or dt.date.today()
    meta, numbers = load_registry(h)
    try:
        got = dt.date.fromisoformat(str(meta.get("downloaded")))
        age = (today - got).days
    except ValueError:
        got, age = None, None
    out = dict(doc)
    if got is None or age > MAX_AGE_DAYS or not numbers:
        why = "no registry download yet" if got is None or not numbers else f"registry download is {age} days old (max {MAX_AGE_DAYS})"
        out.update({"dnc": "STALE", "dnc_why": why})
        return out, {"ok": False, "why": why}
    keep, listed, held = [], [], 0
    for r in doc.get("leads") or []:
        p = ten(r.get("phone"))
        if not p:
            keep.append(r)
            continue
        ac = p[:3]
        if ac not in numbers:
            held += 1
            continue
        if p in numbers[ac]:
            listed.append(str(r.get("id") or ""))
            continue
        keep.append(r)
    if listed:
        np_ = os.path.join(h or home(), "agency_never.json")
        n = rj(np_, {}) or {}
        ids = set(n.get("lead_ids") or []) | {x for x in listed if x}
        wj(np_, {**n, "v": 1, "lead_ids": sorted(ids), "emails": sorted(set(n.get("emails") or []))})
    out.update({"leads": keep, "count": len(keep), "dnc": "scrubbed", "dnc_date": got.isoformat(), "dnc_removed": len(listed), "dnc_held": held})
    out.pop("dnc_why", None)
    return out, {"ok": True, "removed": len(listed), "held": held, "kept": len(keep), "date": got.isoformat(), "area_codes": sorted(numbers)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--list", default=LIST)
    a = ap.parse_args(argv)
    if a.stamp:
        m = stamp()
        print(f"[OK] registry copy dated {m['downloaded']}, area codes: {', '.join(m['area_codes']) or '(none found)'}")
        return 0 if m["area_codes"] else 1
    doc = rj(a.list, {}) or {}
    new, rep = scrub(doc)
    wj(a.list, new)
    if not rep["ok"]:
        print(f"[FIX] NOT scrubbed: {rep['why']}. The list now says STALE: callers must not dial until you re-download "
              "(telemarketing.donotcall.gov) and run: python -m agency.dnc_scrub --stamp, then python -m agency.dnc_scrub")
        return 1
    print(f"[OK] scrubbed against the {rep['date']} registry copy ({', '.join(rep['area_codes'])}): {rep['removed']} on the registry "
          f"(never again), {rep['held']} held (area code not downloaded), {rep['kept']} on the list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
