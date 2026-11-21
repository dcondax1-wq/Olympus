"""THE CALLER PORTAL's PC side (day-a11y 2026-11-21; plan: research/writeups/cold-calling-plan-2026-11-20.md).

A real person dials by hand (legal in Maryland); the page tools/web_public/agency/portal/ is their list, rules and log. It is a static page
that must also work on the neutral public host (day-cities3's public_base export), so it holds NO secret and NO private data:

  python -m agency.portal build            calllist.json from the leads + the factory's concept sites (codes FR-n, paths f/<id>/); chains,
                                           businesses with a website and the never-again list (%USERPROFILE%\\.olympus\\agency_never.json)
                                           are left out, so a 'no' on any channel is never on the list again (only ids are dropped: the
                                           never list itself is never published)
  python -m agency.portal pass             set the callers' shared passphrase: only a salted SHA-256 goes into portal.json (typed hidden)
  python -m agency.portal setup            the public facts on the page: agency name, agency Gmail (the 'Email them the link' sender),
                                           postal address (CAN-SPAM), prices, commissions
  python -m agency.portal import FILE...   a caller's exported log (portal-log-*.json): 'no' / 'do not call' join the never-again list for
                                           every channel, new businesses go to tools/agency_added_leads.json (the factory builds their
                                           sites), and the commission table per caller is printed ($300 a sale, $40 a booked call that shows)
  python -m agency.portal commissions      the table again from %USERPROFILE%\\.olympus\\portal_log.json
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import secrets
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public", "agency")
PORTAL = os.path.join(WEB, "portal")
CONF = os.path.join(PORTAL, "portal.json")
LIST = os.path.join(PORTAL, "calllist.json")
ADDED = os.path.join(ROOT, "tools", "agency_added_leads.json")
NICHES = ["trades", "health", "beauty", "auto", "food", "fitness", "retail", "pets", "home", "other"]
OUTCOMES = ("called", "voicemail", "interested", "booked", "no", "dnc", "won", "emailed", "showed")
CHAINS = ["bonefish", "glory days", "crunch fitness", "bruster", "exxon", "ymca", "america's best wings", "medstar", "med star",
          "anchor bar", "planet fitness", "anytime fitness", "orangetheory", "subway", "mcdonald",
          "burger king", "wendy", "taco bell", "domino", "papa john", "pizza hut", "starbucks", "dunkin", "chick-fil-a", "chipotle",
          "panera", "applebee", "olive garden", "red robin", "buffalo wild", "jiffy lube", "valvoline", "midas", "meineke", "firestone",
          "great clips", "supercuts", "sport clips", "aspen dental"]


def home() -> str:
    return os.environ.get("OLYMPUS_HOME") or os.path.join(os.path.expanduser("~"), ".olympus")


def rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def wj(p, data) -> None:
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, p)


def digits(phone) -> str:
    d = re.sub(r"\D", "", str(phone or ""))
    d = d[1:] if len(d) == 11 and d.startswith("1") else d
    return d if len(d) == 10 and d[0] not in "01" else ""


def never_ids() -> set:
    n = rj(os.path.join(home(), "agency_never.json"), {}) or {}
    st = rj(os.path.join(home(), "agency_mail_state.json"), {}) or {}
    return set(n.get("lead_ids") or []) | {k for k, c in (st.get("replied") or {}).items() if c in ("optout", "bounce")}


def chain(name) -> bool:
    n = str(name or "").lower()
    return any(c in n for c in CHAINS)


# ------------------------------------------------------------------------------------------------ the list
def build(web: str = WEB, out: str = LIST) -> dict:
    leads = list((rj(os.path.join(web, "leads", "leads.json"), {}) or {}).get("leads") or [])
    leads += [L for L in (rj(ADDED, {}) or {}).get("leads") or [] if isinstance(L, dict)]
    fac = {x.get("id"): x for x in ((rj(os.path.join(web, "factory", "sites.json"), {}) or {}).get("sites") or []) if isinstance(x, dict)}
    codes = rj(os.path.join(ROOT, "tools", "site_factory_codes.json"), {}) or {}
    nev, rows, seen = never_ids(), [], set()
    found = (rj(os.path.join(home(), "portal_log.json"), {}) or {}).get("phones") or {}   # numbers callers found on Google Maps by hand
    skip = {"chain": 0, "has a website": 0, "never again": 0}
    for L in leads:
        lid = str(L.get("id") or "")
        if not lid or lid in seen or not str(L.get("name") or "").strip():
            continue
        seen.add(lid)
        f = fac.get(lid) or {}
        if f.get("chain") or chain(L.get("name")):
            skip["chain"] += 1
            continue
        if L.get("website"):
            skip["has a website"] += 1
            continue
        if lid in nev:
            skip["never again"] += 1
            continue
        rows.append({"id": lid, "name": str(L["name"]).strip()[:80], "phone": digits(L.get("phone")) or digits(found.get(lid)), "town": str(L.get("town") or L.get("city") or "")[:40],
                     "state": str(L.get("state") or "MD")[:2].upper(), "niche": str(f.get("niche") or L.get("niche") or "other")[:20],
                     "kind": str(f.get("kind") or L.get("kind") or L.get("niche_name") or "")[:40], "code": str(f.get("code") or codes.get(lid) or ""),
                     "site": str(f.get("path") or ""), "heat": str(L.get("heat") or "")})
    rank = {"trades": 0, "home": 0, "health": 1, "beauty": 2, "auto": 3, "food": 4}
    rows.sort(key=lambda r: (not r["phone"], rank.get(r["niche"], 9), r["name"].lower()))
    doc = {"v": 1, "kind": "caller-portal-list", "built": time.strftime("%Y-%m-%d"), "count": len(rows),
           "note": "public map data only (OpenStreetMap + businesses a caller added); no private data", "skipped": skip, "leads": rows}
    wj(out, doc)
    return doc


# ------------------------------------------------------------------------------------------------ the page's public facts + passphrase
DEFAULT_CONF = {"v": 1, "agency": "", "agency_email": "", "postal": "", "public_base": "", "agency_number": "", "pass": {"salt": "", "sha256": ""},
                "prices": {"starter": "$1,500 + $79/month", "monthly": "$149/month for 12 months, nothing upfront"},
                "commission": {"sale": 300, "booked_show": 40}, "hours": [540, 1020], "tz": "America/New_York"}


def conf() -> dict:
    c = json.loads(json.dumps(DEFAULT_CONF))
    raw = rj(CONF, {}) or {}
    for k, v in raw.items():
        if k in c:
            c[k] = v
    return c


def pass_hash(phrase: str, salt: str) -> str:
    return hashlib.sha256((salt + ":" + phrase).encode("utf-8")).hexdigest()


def set_pass(phrase: str, path: str = CONF) -> dict:
    if len(phrase) < 10:
        raise ValueError("the passphrase needs at least 10 characters (e.g. three words)")
    c = conf() if path == CONF else dict(DEFAULT_CONF, **(rj(path, {}) or {}))
    salt = secrets.token_hex(8)
    c["pass"] = {"salt": salt, "sha256": pass_hash(phrase, salt)}
    wj(path, c)
    return c


def cmd_setup(ask=input, out=print) -> int:
    sys.path.insert(0, ROOT)
    from agency import public as PUB
    c = conf()
    out("CALLER PORTAL: the facts the page shows (all public; never a password here).")

    def q(label, key):
        v = ask(f"  {label}{' [' + str(c.get(key)) + ']' if c.get(key) else ''}: ").strip()
        return v or c.get(key, "")
    c["agency"] = q("Agency name (what the caller says)", "agency")
    c["agency_email"] = q("Agency Gmail ('Email them the link' sends from it)", "agency_email")
    c["postal"] = q("Postal address for the emails (a PO box is fine)", "postal")
    c["public_base"] = PUB.public_base() or c.get("public_base", "")
    c["agency_number"] = PUB.agency_number() or c.get("agency_number", "")
    for k in ("agency", "agency_email", "postal"):
        if PUB.banned(c[k]):
            out(f"  [FIX] {k}: that shows the owner's private address. Not saved.")
            return 1
    wj(CONF, c)
    out("  [OK] saved tools/web_public/agency/portal/portal.json" + ("" if c["public_base"] else
        "  (public_base not set yet: the concept-site links stay hidden until tools/site_factory_agency.json has it)"))
    return 0


# ------------------------------------------------------------------------------------------------ a caller's log back on the PC
def merge_logs(files: list) -> dict:
    """portal-log-*.json (the page's export) -> %USERPROFILE%\\.olympus\\portal_log.json (deduped); returns the merged store"""
    p = os.path.join(home(), "portal_log.json")
    store = rj(p, {}) or {}
    log = {(e.get("t"), e.get("id"), e.get("k"), e.get("caller")): e for e in store.get("log") or [] if isinstance(e, dict)}
    added = {a.get("id"): a for a in store.get("added") or [] if isinstance(a, dict)}
    phones = dict(store.get("phones") or {})
    for fp in files:
        d = rj(fp, {}) or {}
        if d.get("app") != "agency-portal":
            raise ValueError(f"{os.path.basename(fp)}: not a caller-portal export")
        for e in d.get("log") or []:
            if isinstance(e, dict) and e.get("k") in OUTCOMES and e.get("id"):
                e = {k: e.get(k) for k in ("t", "id", "k", "caller", "name", "code")}
                e["caller"] = str(e.get("caller") or d.get("caller") or "?")[:40]
                log[(e["t"], e["id"], e["k"], e["caller"])] = e
        for k, v in (d.get("phones") or {}).items() if isinstance(d.get("phones"), dict) else []:
            if digits(v):
                phones[str(k)[:40]] = digits(v)
        for a in d.get("added") or []:
            if isinstance(a, dict) and a.get("id") and a.get("name"):
                added[a["id"]] = {"id": str(a["id"])[:40], "name": str(a["name"])[:80], "phone": digits(a.get("phone")), "town": str(a.get("town") or "")[:40],
                                  "state": str(a.get("state") or "MD")[:2].upper(), "niche": a.get("niche") if a.get("niche") in NICHES else "other",
                                  "by": str(a.get("by") or d.get("caller") or "")[:40], "source": "caller (Google Maps, by hand)"}
    store = {"v": 1, "log": sorted(log.values(), key=lambda e: (e.get("t") or 0)), "added": list(added.values()), "phones": phones}
    wj(p, store)
    return store


def apply_never(store: dict) -> list:
    """'no' or 'do not call' on a call = never again on every channel (email, the caller list); returns the lead ids added"""
    p = os.path.join(home(), "agency_never.json")
    n = rj(p, {}) or {}
    ids = set(n.get("lead_ids") or [])
    new = sorted({e["id"] for e in store["log"] if e.get("k") in ("no", "dnc")} - ids)
    if new:
        wj(p, {"v": 1, "lead_ids": sorted(ids | set(new)), "emails": sorted(set(n.get("emails") or []))})
    return new


def add_leads(store: dict, path: str | None = None) -> int:
    """businesses a caller found on Google Maps -> tools/agency_added_leads.json (public facts only: name, phone, town, niche).
    The factory (tools/site_factory.py) builds their concept sites from it (LEAD_WIRES: its load_leads reads this file too)."""
    path = path or ADDED
    cur = rj(path, {}) or {}
    have = {L.get("id") for L in cur.get("leads") or []}
    add = [dict(a, niche_name=a["niche"], heat="warm") for a in store.get("added") or [] if a.get("id") not in have]
    if add:
        wj(path, {"v": 1, "kind": "caller-added-leads", "leads": (cur.get("leads") or []) + add})
    return len(add)


def commissions(store: dict, c: dict | None = None) -> list:
    """per caller: dials, talks, interested, booked, won, and what is owed ($300 a sale; $40 a booked call only once the owner marks it 'showed')"""
    c = c or conf()
    rate = c.get("commission") or {}
    rows: dict = {}
    for e in store.get("log") or []:
        r = rows.setdefault(e.get("caller") or "?", {"caller": e.get("caller") or "?", "calls": 0, "interested": 0, "booked": 0, "showed": 0, "won": 0, "no": 0})
        k = e.get("k")
        if k in ("called", "voicemail", "interested", "booked", "no", "dnc", "won"):
            r["calls"] += 1
        if k in ("interested", "booked", "showed", "won"):
            r[k] += 1
        if k in ("no", "dnc"):
            r["no"] += 1
    for r in rows.values():
        r["owed"] = r["won"] * int(rate.get("sale", 300)) + r["showed"] * int(rate.get("booked_show", 40))
    return sorted(rows.values(), key=lambda r: -r["owed"])


def table(rows: list) -> str:
    out = ["  caller               calls  interested  booked  showed  won  no   owed"]
    for r in rows:
        out.append(f"  {r['caller'][:20]:<20} {r['calls']:>5}  {r['interested']:>10}  {r['booked']:>6}  {r['showed']:>6}  {r['won']:>3}  {r['no']:>2}  ${r['owed']:,}")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The caller portal's PC side (build the list, the passphrase, import a caller's log)")
    ap.add_argument("cmd", choices=["build", "pass", "setup", "import", "commissions"])
    ap.add_argument("files", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        d = build()
        print(f"  [OK] {d['count']} businesses on the list ({sum(1 for r in d['leads'] if r['phone'])} with a phone); left out: {d['skipped']}")
        return 0
    if a.cmd == "pass":
        p1 = getpass.getpass("  New passphrase for the callers (hidden; 10+ characters): ")
        if p1 != getpass.getpass("  Again: "):
            print("  [FIX] they did not match")
            return 1
        try:
            set_pass(p1)
        except ValueError as e:
            print("  [FIX] " + str(e))
            return 1
        print("  [OK] only a salted hash is saved in portal.json. Give the passphrase to the caller yourself (not by email).")
        return 0
    if a.cmd == "setup":
        return cmd_setup()
    if a.cmd == "import":
        if not a.files:
            print("  [FIX] name the file(s): python -m agency.portal import portal-log-....json")
            return 1
        store = merge_logs(a.files)
        new = apply_never(store)
        n = add_leads(store)
        print(f"  [OK] {len(store['log'])} log lines; {len(new)} new 'never again'; {n} new businesses for the factory")
        print(table(commissions(store)))
        return 0
    print(table(commissions(rj(os.path.join(home(), "portal_log.json"), {}) or {})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
