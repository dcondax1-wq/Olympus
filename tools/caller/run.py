"""THE DIALER: who may be called right now, and (only when ON) one dial per tick through the gate.

  python -m tools.caller.run --dry          every consented number: the gate's answer right now, in plain words (no call, no lookup cost:
                                            line types come from the cache, unknown = blocked)
The server (server.py) runs tick() once a minute while the caller is ON. Nothing else dials.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import secrets
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "tools.caller"

from . import compliance as G  # noqa: E402
from . import config as C  # noqa: E402
from . import consent as K  # noqa: E402
from . import telephony as T  # noqa: E402

LEADS = os.path.join(C.ROOT, "tools", "web_public", "agency", "leads", "leads.json")
AREA_STATE = {**{a: "MD" for a in ("301", "240", "410", "443", "667")}, "202": "DC", "771": "DC",
              **{a: "VA" for a in ("703", "571", "540", "804", "757", "434", "276", "826", "948")}, "302": "DE",
              **{a: "PA" for a in ("215", "267", "445", "717", "223", "610", "484", "835", "412", "878", "724", "814", "582", "570", "272")},
              "304": "WV", "681": "WV"}
LINE_CACHE_DAYS = 30


def leads_by_phone(path: str = LEADS) -> dict:
    j = C.read_json(path, {}) or {}
    rows = j.get("leads", []) if isinstance(j, dict) else (j if isinstance(j, list) else [])
    return {G.e164(r.get("phone", "")): r for r in rows if isinstance(r, dict) and G.e164(r.get("phone", ""))}


def lead_for(consent_rec: dict, idx: dict) -> dict:
    lead = dict(idx.get(consent_rec["phone"]) or {})
    lead.setdefault("phone", consent_rec["phone"])
    lead.setdefault("name", consent_rec.get("business", ""))
    lead.setdefault("id", consent_rec.get("lead_id", ""))
    if not lead.get("state"):
        lead["state"] = AREA_STATE.get(G.area_code(consent_rec["phone"]), "")
    return lead


def line_type(number: str, adapter, h=None, now=None, allow_lookup=True) -> str:
    """Cached 30 days in <home>/caller/linetype.json (each lookup costs $0.008); no cache and no lookup allowed = 'unknown'."""
    p = os.path.join(C.state_dir(h), "linetype.json")
    cache = C.read_json(p, {}) or {}
    now = now or dt.datetime.now(dt.timezone.utc)
    hit = cache.get(number)
    if hit and (now - dt.datetime.fromisoformat(hit["ts"])).days <= LINE_CACHE_DAYS:
        return hit["type"]
    if not allow_lookup or adapter is None:
        return "unknown"
    t = adapter.lookup(number)
    cache[number] = {"type": t, "ts": now.isoformat()}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    return t


def plan(now: dt.datetime, adapter=None, h=None, s=None, allow_lookup=False, leads_path=LEADS) -> list:
    """[(lead, Decision)] for every consented number, oldest consent first."""
    s = s or C.settings(h)
    idx = leads_by_phone(leads_path)
    out = []
    for rec in sorted(K.consented_numbers(h), key=lambda r: r["ts"]):
        lead = lead_for(rec, idx)
        if G.e164(lead["phone"]) in G.dnc_numbers(h):
            lt = "skipped"
        else:
            lt = line_type(rec["phone"], adapter, h, now, allow_lookup)
        dec = G.check_outbound(lead, now, lt, K.valid_for(rec["phone"], now, s, h), h, s)
        out.append((lead, dec, rec))
    return out


def tick(now: dt.datetime, adapter, public_base: str, h=None, s=None, register=None, leads_path=LEADS) -> dict | None:
    """At most ONE dial: the first consented number the gate allows. Returns the attempt record, or None."""
    s = s or C.settings(h)
    for lead, dec, rec in plan(now, adapter, h, s, allow_lookup=True, leads_path=leads_path):
        if not dec.ok:
            continue
        token = secrets.token_urlsafe(18)
        opener = G.opening_line(s, lead.get("name", ""))
        ok, why = G.check_disclosure(opener, s)
        if not ok:
            raise RuntimeError("disclosure check failed: " + why)
        ws = public_base.replace("https://", "wss://").rstrip("/") + f"/relay?t={token}"
        twiml = T.relay_twiml(ws, opener, s.get("voice", {}))
        call_id = adapter.dial(dec.number, twiml, public_base.rstrip("/") + "/voice/status")
        att = {"kind": "attempt", "dir": "out", "ts": now.isoformat(), "call_id": call_id, "number": dec.number, "lead_id": lead.get("id", ""),
               "business": lead.get("name", ""), "outcome": "dialed", "gate": dec.reasons}
        G.log_call(att, h)
        if register:
            register(token, {"lead": lead, "call_id": call_id, "email": rec.get("email", ""), "inbound": False})
        return att
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="show the gate's answers, never dial (the only mode this command has)")
    ap.parse_args(argv)
    now = dt.datetime.now(dt.timezone.utc)
    rows = plan(now)
    if not rows:
        print("No signed consent yet: nobody may be called. (Cold calls are not allowed in Maryland: Com. Law 14-4502(a)(3).)")
        return 0
    for lead, dec, _ in rows:
        print(("CALL  " if dec.ok else "WAIT  ") + f"{lead.get('name') or '?'} {dec.number}" + ("" if dec.ok else f"  ({dec.blocked_by})"))
        for r in dec.reasons:
            print("        " + r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
