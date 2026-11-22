"""DNC SCRUB (agency/dnc_scrub.py, day-caller2 2026-11-21): the human caller list against the National Do Not Call Registry copy.
  a. a listed number is removed and its lead goes on the never-again list; an unlisted one stays; a row without a phone stays
  b. an area code that was not downloaded (667, toll-free) is held off the list, not silently kept
  c. no download or a download older than 31 days = the list is marked STALE and nothing is called "scrubbed"
  d. the published list never contains a registry number or the registry itself; the stamp records the date + area codes
    python -X utf8 -m tests.test_dnc_scrub
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency import dnc_scrub as D  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def home(codes=("301", "240", "227", "410", "443"), listed=("3015550199",), when=dt.date(2026, 11, 20)):
    h = tempfile.mkdtemp(prefix="dnc-")
    d = os.path.join(h, "caller", "registry")
    os.makedirs(d)
    for ac in codes:
        with open(os.path.join(d, f"{ac}.txt"), "w") as f:
            f.write("".join(x + "\n" for x in listed if x.startswith(ac)) + f"{ac}0000000\n")
    D.stamp(h, when)
    return h


DOC = {"v": 1, "kind": "caller-portal-list", "count": 5, "leads": [
    {"id": "a", "name": "On The List Plumbing", "phone": "(301) 555-0199"},
    {"id": "b", "name": "Clean Bakery", "phone": "3015550142"},
    {"id": "c", "name": "No Phone Salon", "phone": ""},
    {"id": "d", "name": "Baltimore New Number", "phone": "6675550100"},
    {"id": "e", "name": "Toll Free Co", "phone": "8885550100"}]}


def main() -> int:
    h = home()
    new, rep = D.scrub(DOC, h, dt.date(2026, 11, 23))
    ids = [r["id"] for r in new["leads"]]
    check("a. the listed number is removed, the unlisted and the no-phone rows stay", ids == ["b", "c"], ids)
    nev = json.load(open(os.path.join(h, "agency_never.json")))
    check("a. the listed business goes on the never-again list (every channel)", nev["lead_ids"] == ["a"], nev)
    check("b. 667 and toll-free (not downloaded) are held off the list, counted", rep["held"] == 2 and new["dnc_held"] == 2, rep)
    check("d. the header says scrubbed with the download date and counts", new["dnc"] == "scrubbed" and new["dnc_date"] == "2026-11-20"
          and new["dnc_removed"] == 1 and new["count"] == 2)
    txt = json.dumps(new)
    check("d. the published list holds no registry number", "5550199" not in txt and "0000000" not in txt)
    old, rep2 = D.scrub(DOC, home(when=dt.date(2026, 10, 1)), dt.date(2026, 11, 23))
    check("c. a download older than 31 days marks the list STALE and scrubs nothing", old["dnc"] == "STALE" and not rep2["ok"]
          and "53 days" in old["dnc_why"])
    empty = tempfile.mkdtemp()
    none, rep3 = D.scrub(DOC, empty, dt.date(2026, 11, 23))
    check("c. no download at all = STALE", none["dnc"] == "STALE" and not rep3["ok"])
    m = json.load(open(os.path.join(h, "caller", "registry", "meta.json")))
    check("d. the stamp records the date and the 5 area codes found (MD: 301, 240, 227, 410, 443 free; 667 = the 6th)",
          m == {"downloaded": "2026-11-20", "area_codes": ["227", "240", "301", "410", "443"]}, m)
    p = os.path.join(tempfile.mkdtemp(), "calllist.json")
    json.dump(DOC, open(p, "w"))
    os.environ["OLYMPUS_HOME"] = h
    try:
        rc = D.main(["--list", p])
    finally:
        os.environ.pop("OLYMPUS_HOME", None)
    check("d. the command scrubs the file in place and exits 0", rc == 0 and json.load(open(p))["dnc"] == "scrubbed")
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
