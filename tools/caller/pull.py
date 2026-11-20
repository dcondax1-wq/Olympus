"""Collect the signed forms from the concept sites' Cloudflare KV (cloudflare/consent.js) into the PC's consent store, then delete them.

  python -m tools.caller.pull          once (the caller server runs it every minute while it is up)
Needs, saved by CALLER_SETUP.bat in caller.json: cf_account, cf_kv_namespace, cf_kv_token (a Cloudflare token with Workers KV
Storage: Edit on that namespace only). Each entry is checked again by consent.record (the same rules as POST /consent on the PC).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "tools.caller"

from . import config as C  # noqa: E402
from . import consent as K  # noqa: E402

API = "https://api.cloudflare.com/client/v4/accounts/{acct}/storage/kv/namespaces/{ns}"


def cf_keys(h=None) -> dict:
    j = C.read_json(C.keys_path(h), {}) or {}
    return {k: str(j.get(k) or "") for k in ("cf_account", "cf_kv_namespace", "cf_kv_token")}


def pull(h=None, opener=None, s=None, leads: dict | None = None) -> dict:
    k = cf_keys(h)
    if not all(k.values()):
        return {"ok": False, "why": "no Cloudflare KV keys yet (CALLER_SETUP.bat)", "added": 0}
    opener = opener or urllib.request.urlopen
    base = API.format(acct=k["cf_account"], ns=k["cf_kv_namespace"])
    hdr = {"Authorization": "Bearer " + k["cf_kv_token"]}

    def req(url, method="GET"):
        with opener(urllib.request.Request(url, method=method, headers=hdr), timeout=20) as r:
            return r.read().decode()
    s = s or C.settings(h)
    if leads is None:
        from . import run as R
        leads = R.leads_by_phone()       # security review C1: only our own leads' numbers, with their own lead id
    names = [x["name"] for x in json.loads(req(base + "/keys?prefix=c%3A")).get("result", [])]
    added, refused = 0, 0
    for name in names:
        q = urllib.parse.quote(name, safe="")
        try:
            item = json.loads(req(base + "/values/" + q))
            when = dt.datetime.fromisoformat(str(item["received"]).replace("Z", "+00:00"))
            ok, _, _ = K.record(item.get("form") or {}, s, h, now=when, ip=str(item.get("ip", "")), ua=str(item.get("ua", "")), leads=leads)
        except (ValueError, KeyError, TypeError):
            ok = False
        added += int(ok)
        refused += int(not ok)
        req(base + "/values/" + q, "DELETE")
    return {"ok": True, "added": added, "refused": refused}


if __name__ == "__main__":
    r = pull()
    print(C.redact(json.dumps(r)))
    sys.exit(0 if r["ok"] else 1)
