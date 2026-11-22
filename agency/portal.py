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
  python -m agency.portal scorecard [--days N]   per caller: dials, talks, links, booked vs the daily targets, sold, $ owed
  python -m agency.portal paid ID KIND [DATE]   the owner records client money that CLEARED (deposit / launch / monthly / refund):
                                           a commission is owed only after that (agency/pricebook.json "commission")
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
# the first line after "Hi, it's <caller> with <agency>." per lane (the Overture check, tools/web_leads_overture.py): honest, no pressure, no claim we
# can't back. no_site = we built them a free concept site; site_down = their site did not load on the check date; redesign = they have a working site
OPENERS = {
    "no_site": "I noticed {name} doesn't have a website, so we built you one. It's free to look at. Can I email you the link?",
    "site_down": "I tried your website and it didn't load for me, so we built you a fresh one. It's free to look at. Can I email you the link?",
    "redesign": "I looked at your website. We help local businesses get a faster, mobile-friendly site that brings more calls. Can I email you a free 2-minute check of yours?",
}
SCORES = os.path.join(ROOT, "tools", "agency_site_scores.json")


def build(web: str = WEB, out: str = LIST) -> dict:
    from agency import leadsfile
    leads = leadsfile.load(web)                     # leads.json, or its per-town files ("files": ["towns/<town>.json"])
    leads += [L for L in (rj(ADDED, {}) or {}).get("leads") or [] if isinstance(L, dict)]
    fac = {x.get("id"): x for x in ((rj(os.path.join(web, "factory", "sites.json"), {}) or {}).get("sites") or []) if isinstance(x, dict)}
    codes = rj(os.path.join(ROOT, "tools", "site_factory_codes.json"), {}) or {}
    nev, rows, seen = never_ids(), [], set()
    found = (rj(os.path.join(home(), "portal_log.json"), {}) or {}).get("phones") or {}   # numbers callers found on Google Maps by hand
    skip = {"chain": 0, "has a website": 0, "never again": 0}
    scores = (rj(SCORES, {}) or {}).get("scores") or {}
    # the National Do Not Call list (owner step: the FTC's free download for up to 5 area codes, saved as
    # %USERPROFILE%\.olympus\dnc_scrub.json {"listed": ["3015550100", ...], "checked": ["301", "240", ...]}): a number in a checked area code is
    # 'clear' or 'listed'; anything else stays 'unknown' (the caller can check by hand). Only that word goes into the public list
    scrub = rj(os.path.join(home(), "dnc_scrub.json"), {}) or {}
    listed, checked = {digits(x) for x in scrub.get("listed") or []}, {str(x)[:3] for x in scrub.get("checked") or []}      # agency/redesign_score.py: how dated / slow each working site is (public page facts only)
    for L in leads:
        lid = str(L.get("id") or "")
        if not lid or lid in seen or not str(L.get("name") or "").strip():
            continue
        seen.add(lid)
        f = fac.get(lid) or {}
        if f.get("chain") or chain(L.get("name")):
            skip["chain"] += 1
            continue
        verdict = (L.get("web") or {}).get("verdict")
        url = str(L.get("website") or (L.get("web") or {}).get("url") or "")
        lane = "redesign" if (L.get("website") or verdict == "has_site") else "site_down" if verdict == "site_down" else "no_site"
        if lane == "redesign" and not re.match(r"^https?://", url):
            skip["has a website"] += 1                      # a website tag with no usable address: nothing honest to say about it
            continue
        if lid in nev:
            skip["never again"] += 1
            continue
        rows.append({"id": lid, "name": str(L["name"]).strip()[:80], "phone": digits(L.get("phone")) or digits(found.get(lid)), "town": str(L.get("town") or L.get("city") or "")[:40],
                     "state": str(L.get("state") or "MD")[:2].upper(), "niche": str(f.get("niche") or L.get("niche") or "other")[:20],
                     "kind": str(f.get("kind") or L.get("kind") or L.get("niche_name") or "")[:40], "code": str(f.get("code") or codes.get(lid) or ""),
                     "site": str(f.get("path") or ""), "heat": str(L.get("heat") or ""),
                     "lane": lane, "opener": OPENERS[lane].format(name=str(L["name"]).strip()[:80])})   # Overture check (tools/web_leads_overture.py)
        ph = rows[-1]["phone"]
        if ph and ph in listed:
            rows[-1]["dnc"] = "listed"
        elif ph and ph[:3] in checked:
            rows[-1]["dnc"] = "clear"
        if lane == "redesign":
            sc = scores.get(lid) or {}
            rows[-1].update(url=url[:200], score=int(sc.get("score") or 0), why=[str(w)[:40] for w in (sc.get("why") or [])][:4], site="", code="")
        try:                                             # the $ score (tools/lead_value.py: roofing / HVAC first, site_down, a phone)
            from tools import lead_value as LV
            rows[-1]["usd"] = LV.score(L)
        except ImportError:
            pass
    # the big county leads (tools/web_leads_counties.py; the county files stay private in research/web_leads/counties/): ONLY the ranked
    # first 100 + next 500 calls (tools/first_calls.py) go on the public list, with their lane / opener / trade / county / $ / concept link
    have = {r["id"] for r in rows}
    for fn in ("first100.json", "next500.json"):
        for r in (rj(os.path.join(web, "portal", fn), {}) or {}).get("leads") or []:
            if not isinstance(r, dict) or not r.get("county") or r.get("id") in have or r.get("id") in nev:
                continue
            have.add(r["id"])
            lane = r.get("lane") if r.get("lane") in ("no_site", "site_down") else "no_site"
            rows.append({"id": r["id"], "name": str(r.get("name") or "")[:80], "phone": digits(r.get("phone")), "town": str(r.get("town") or "")[:40],
                         "state": "MD", "niche": str(r.get("niche") or "other")[:20], "kind": str(r.get("kind") or "")[:40], "code": str(r.get("code") or ""),
                         "site": str(r.get("site") or ""), "heat": str(r.get("heat") or ""), "lane": lane, "opener": OPENERS[lane].format(name=str(r.get("name") or "")[:80]),
                         "trade": str(r.get("trade") or "")[:30], "county": str(r.get("county") or "")[:30], "usd": int(r.get("score") or 0)})
            ph = rows[-1]["phone"]
            if ph and ph in listed:
                rows[-1]["dnc"] = "listed"
            elif ph and ph[:3] in checked:
                rows[-1]["dnc"] = "clear"
    rank = {"trades": 0, "home": 0, "health": 1, "beauty": 2, "auto": 3, "food": 4}
    # biggest $ first (Today mode keeps this order after follow-ups and best-hour leads); redesign and no-phone rows last
    rows.sort(key=lambda r: (r["lane"] == "redesign", not r["phone"], -r.get("usd", 0), -r.get("score", 0), rank.get(r["niche"], 9), r["name"].lower()))
    lanes = {k: sum(1 for r in rows if r["lane"] == k) for k in OPENERS}
    pb = rj(os.path.join(ROOT, "agency", "pricebook.json"), {}) or {}
    st = next((x for x in pb.get("packages") or [] if isinstance(x, dict) and x.get("id") == "starter"), {})
    price = {"name": str(st.get("name") or "Starter site"), "setup": int(st.get("setup") or 1500), "monthly": int(st.get("monthly") or 79)}   # the pipeline's $ (agency/pricebook.json)
    doc = {"v": 1, "kind": "caller-portal-list", "built": time.strftime("%Y-%m-%d"), "count": len(rows), "lanes": lanes, "price": price,
           "note": "public map data only (OpenStreetMap + businesses a caller added); no private data", "skipped": skip, "leads": rows}
    for r in rows:                                       # a phone downloads this: drop empty fields
        for k in [k for k, v in r.items() if v in ("", None, []) and k not in ("id", "name", "phone", "lane")]:
            del r[k]
        if r.get("state") == "MD":
            del r["state"]
        if r.get("opener") == OPENERS[r["lane"]].format(name=r["name"]):
            del r["opener"]                                  # the page says the same line for its lane (portalcore.js opener())
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(out + ".tmp", out)
    return doc


# ------------------------------------------------------------------------------------------------ the page's public facts + passphrase
DEFAULT_CONF = {"v": 1, "agency": "", "agency_email": "", "postal": "", "public_base": "", "agency_number": "", "pass": {"salt": "", "sha256": ""},
                "prices": {"starter": "$1,500 + $79/month", "monthly": "$149/month for 12 months, nothing upfront"},
                "commission": {"sale": 300, "booked_show": 40, "clawback_days": 30}, "hours": [540, 1020], "tz": "America/New_York"}


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


PAID_KINDS = ("deposit", "launch", "monthly", "refund")


def paid_ledger(h: str | None = None) -> list:
    """The owner's record of client money that has CLEARED (%USERPROFILE%\\.olympus\\agency_paid.json), written only by
    `python -m agency.portal paid <lead id or code> deposit|launch|monthly|refund [YYYY-MM-DD]`. A caller's own 'Won' is only a claim."""
    d = rj(os.path.join(h or home(), "agency_paid.json"), {}) or {}
    return [e for e in d.get("payments") or [] if isinstance(e, dict) and e.get("kind") in PAID_KINDS and e.get("id")]


def mark_paid(lead_id: str, kind: str, day: str, h: str | None = None) -> dict:
    if kind not in PAID_KINDS or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(day)):
        raise ValueError("kind must be deposit / launch / monthly / refund, the date YYYY-MM-DD")
    codes = {str(v).upper(): k for k, v in (rj(os.path.join(ROOT, "tools", "site_factory_codes.json"), {}) or {}).items()}
    lid = codes.get(str(lead_id).upper(), str(lead_id))[:40]
    p = os.path.join(h or home(), "agency_paid.json")
    d = rj(p, {}) or {}
    e = {"id": lid, "kind": kind, "t": day}
    d = {"v": 1, "payments": (d.get("payments") or []) + [e]}
    wj(p, d)
    return e


def sale_cleared(pays: list, lid: str) -> str:
    """The date the sale counts as paid for commission ('' if not yet): deposit AND launch cleared, or the 3rd monthly payment."""
    mine = [e for e in pays if e["id"] == lid]
    dep = sorted(e["t"] for e in mine if e["kind"] == "deposit")
    lau = sorted(e["t"] for e in mine if e["kind"] == "launch")
    mon = sorted(e["t"] for e in mine if e["kind"] == "monthly")
    if dep and lau:
        return max(dep[0], lau[0])
    return mon[2] if len(mon) >= 3 else ""


def _days(a: str, b: str) -> int:
    import datetime as _dt
    return (_dt.date.fromisoformat(b) - _dt.date.fromisoformat(a)).days


def commissions(store: dict, c: dict | None = None, paid: list | None = None) -> list:
    """per caller: dials, talks, interested, booked, won, and the money (agency/pricebook.json "commission"):
    - ONE commission per business, to the first caller who logged it interested / booked / won;
    - $300 a sale only once the client's money has CLEARED (deposit + launch, or the 3rd $149 payment: the owner's `paid` ledger),
      never at 'yes' or at a caller's own 'Won' (that is 'pending');
    - a refund within clawback_days (30) of clearing = $0 for that sale ('clawback' shows what to take back if it was already paid);
    - $40 when the owner marks a booked call 'showed' and the business did not (yet) buy; a later cleared sale replaces it: $300, never $340."""
    c = c or conf()
    rate = c.get("commission") or {}
    sale, show = int(rate.get("sale", 300)), int(rate.get("booked_show", 40))
    claw = int(rate.get("clawback_days", 30))
    pays = paid_ledger() if paid is None else paid
    rows: dict = {}
    first: dict = {}
    showed, claimed = set(), set()
    for e in sorted(store.get("log") or [], key=lambda e: (e.get("t") or 0)):
        caller = e.get("caller") or "?"
        r = rows.setdefault(caller, {"caller": caller, "calls": 0, "interested": 0, "booked": 0, "showed": 0, "won": 0, "no": 0,
                                     "owed": 0, "pending": 0, "clawback": 0, "sold": 0})
        k, lid = e.get("k"), e.get("id")
        if k in ("called", "voicemail", "interested", "booked", "no", "dnc", "won"):
            r["calls"] += 1
        if k in ("interested", "booked", "showed", "won"):
            r[k] += 1
        if k in ("no", "dnc"):
            r["no"] += 1
        if lid and k in ("interested", "booked", "won"):
            first.setdefault(lid, caller)
        if lid and k == "showed":
            showed.add(lid)
            first.setdefault(lid, caller)         # no earlier interested / booked line: the caller on the 'showed' line
        if lid and k == "won":
            claimed.add(lid)
    for lid, caller in first.items():
        r = rows[caller]
        clear = sale_cleared(pays, lid)
        refunds = sorted(e["t"] for e in pays if e["id"] == lid and e["kind"] == "refund")
        if clear:
            if any(_days(clear, t) <= claw and t >= clear for t in refunds) or any(t < clear for t in refunds):
                r["clawback"] += sale
            else:
                r["owed"] += sale
                r["sold"] += 1
        elif lid in claimed:
            r["pending"] += sale
        elif lid in showed:
            r["owed"] += show
    return sorted(rows.values(), key=lambda r: (-r["owed"], -r["pending"]))


TALKS = ("called", "interested", "booked", "no", "dnc", "won")
DIAL_KINDS = ("called", "voicemail", "interested", "booked", "no", "dnc", "won")


def targets() -> dict:
    """Daily targets per caller (agency/trade_scripts.json "targets"): dials, talks, links (interested), booked."""
    d = rj(os.path.join(ROOT, "agency", "trade_scripts.json"), {}) or {}
    return d.get("targets") or {"dials": 50, "talks": 10, "links": 2, "booked": 1}


def scorecard(store: dict, days: int = 1, now_ms: float | None = None, c: dict | None = None, paid: list | None = None) -> list:
    """Per caller over the last `days` calling days: dials, talks, links emailed (interested), booked, showed, against the daily targets
    x days; plus sold / owed / pending / clawback from commissions() (all time: money is counted when it clears, not when it was dialed)."""
    now_ms = now_ms if now_ms is not None else time.time() * 1000
    since = now_ms - days * 86400000 * (7 / 5 if days >= 5 else 1)        # 5 calling days ~ a week
    tg = targets()
    money = {r["caller"]: r for r in commissions(store, c, paid)}
    rows: dict = {}
    for e in store.get("log") or []:
        if (e.get("t") or 0) < since:
            continue
        caller = e.get("caller") or "?"
        r = rows.setdefault(caller, {"caller": caller, "dials": 0, "talks": 0, "links": 0, "booked": 0, "showed": 0})
        k = e.get("k")
        r["dials"] += k in DIAL_KINDS
        r["talks"] += k in TALKS
        r["links"] += k == "interested"
        r["booked"] += k == "booked"
        r["showed"] += k == "showed"
    for caller, m in money.items():
        rows.setdefault(caller, {"caller": caller, "dials": 0, "talks": 0, "links": 0, "booked": 0, "showed": 0})
    out = []
    for caller, r in rows.items():
        m = money.get(caller) or {}
        r.update({k: m.get(k, 0) for k in ("sold", "owed", "pending", "clawback")})
        r["target"] = {k: int(tg.get(k, 0)) * days for k in ("dials", "talks", "links", "booked")}
        r["hit"] = {k: r[k] >= r["target"][k] for k in r["target"]}
        r["talk_rate"] = round(100 * r["talks"] / r["dials"]) if r["dials"] else 0
        out.append(r)
    return sorted(out, key=lambda r: (-r["owed"], -r["booked"], -r["dials"]))


def scorecard_table(rows: list, days: int) -> str:
    head = f"  SCORECARD, last {days} calling day{'s' if days != 1 else ''} (done/target; + = target hit)"
    out = [head, "  caller               dials        talks       links      booked   sold   owed  pending  clawback"]
    for r in rows:
        t, h = r["target"], r["hit"]
        cell = lambda k, w: (f"{r[k]}/{t[k]}" + ("+" if h[k] else " ")).rjust(w)
        out.append(f"  {r['caller'][:20]:<20} {cell('dials', 9)}  {cell('talks', 9)}  {cell('links', 9)}  {cell('booked', 9)}  {r['sold']:>5}  "
                   f"${r['owed']:,}  ${r['pending']:,}  ${r['clawback']:,}   ({r['talk_rate']}% of dials became a talk)")
    if not rows:
        out.append("  (no calls logged in this window)")
    return "\n".join(out)


def table(rows: list) -> str:
    out = ["  caller               calls  interested  booked  showed  won  no   owed  pending  clawback"]
    for r in rows:
        out.append(f"  {r['caller'][:20]:<20} {r['calls']:>5}  {r['interested']:>10}  {r['booked']:>6}  {r['showed']:>6}  {r['won']:>3}  {r['no']:>2}  "
                   f"${r['owed']:,}  ${r.get('pending', 0):,}  ${r.get('clawback', 0):,}")
    out.append("  owed = the client's money has cleared; pending = a 'Won' waiting for the deposit + launch payment; clawback = refunded within 30 days")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The caller portal's PC side (build the list, the passphrase, import a caller's log)")
    ap.add_argument("cmd", choices=["build", "pass", "setup", "import", "commissions", "paid", "scorecard"])
    ap.add_argument("--days", type=int, default=1, help="scorecard window in calling days (1 = today, 5 = a week, 10 = two weeks)")
    ap.add_argument("files", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "paid":
        import datetime as _dt
        if len(a.files) not in (2, 3):
            print("  [FIX] python -m agency.portal paid <lead id or code> deposit|launch|monthly|refund [YYYY-MM-DD]  (only once the money CLEARED)")
            return 1
        try:
            e = mark_paid(a.files[0], a.files[1], a.files[2] if len(a.files) == 3 else _dt.date.today().isoformat())
        except ValueError as x:
            print("  [FIX] " + str(x))
            return 1
        print(f"  [OK] {e['kind']} for {e['id']} on {e['t']}")
        print(table(commissions(rj(os.path.join(home(), "portal_log.json"), {}) or {})))
        return 0
    if a.cmd == "scorecard":
        print(scorecard_table(scorecard(rj(os.path.join(home(), "portal_log.json"), {}) or {}, max(1, a.days)), max(1, a.days)))
        return 0
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
