"""EMAIL AUTOPILOT on the owner's PC (day-a11y 2026-11-20, the Website Factory). Stdlib only; a scheduled task, never the bot.

  python -m agency.autopilot setup     once (tools/bat/EMAIL_SETUP.bat): the free business Gmail + its app password (typed hidden), your name,
                                       business, phone, postal address, a test address, the booking / payment links; then the phrase gate:
                                       type SEND EMAILS to go live, anything else = DRY RUN (every message goes to your test address only)
  python -m agency.autopilot run       one pass (the task runs it every 30 minutes): read replies -> send Claude's allowed drafts ->
                                       the day's follow-ups and new emails within every limit -> the private branch -> the page's counts
  python -m agency.autopilot stop      everything off (tools/bat/EMAIL_STOP.bat), nothing is sent again until setup + the phrase
  python -m agency.autopilot status    the day's numbers (no secret is ever printed)
  python -m agency.autopilot test      one test email to your test address (checks the Gmail login)
Files (all in %USERPROFILE%\\.olympus, never the repo): agency_mail.json (the settings + app password), agency_mail_state.json (who got
what, the suppression list), agency_mail.log (one line per run: counts, never a password), agency_inbox\\ (the private branch's clone).
The trading bot is not touched: no engine file, no live_model, no order; a separate Windows task (scripts\\agency_mail_task.ps1).
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.request

from .. import public as PUB
from . import bridge, core, mailer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB = os.path.join(ROOT, "tools", "web_public")


def home(env=None) -> str:
    e = os.environ if env is None else env
    return e.get("OLYMPUS_HOME") or os.path.join(e.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def path(name: str) -> str:
    return os.path.join(home(), name)


def read_json(p: str, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(p: str, data, private: bool = False) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, p)
    if private:
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass


def load_cfg() -> dict:
    return core.norm_cfg(read_json(path("agency_mail.json"), {}))


def redact(s: str, cfg: dict) -> str:
    """every log / print goes through here: the app password (and its spaced form) can never appear"""
    s = str(s)
    pw = str(cfg.get("app_password") or "")
    for v in {pw, pw.replace(" ", "")} - {""}:
        s = s.replace(v, "[secret]")
    return s


def log(cfg: dict, rec: dict) -> None:
    try:
        os.makedirs(home(), exist_ok=True)
        with open(path("agency_mail.log"), "a", encoding="utf-8") as fh:
            fh.write(redact(json.dumps(rec, ensure_ascii=False), cfg) + "\n")
    except OSError:
        pass


def mask_addr(a: str) -> str:
    a = str(a or "")
    return re.sub(r"^(.).*(@.*)$", r"\1***\2", a) if "@" in a else ""


CODE_RE = re.compile(r"\b([A-Z]{2}-\d{1,4})\b")   # the postcard / concept-site code (FR-27, day-cities3's tools/site_factory_codes.json)


def site_data() -> tuple:
    from agency import leadsfile
    leads = leadsfile.load(os.path.join(WEB, "agency"))   # leads.json, or its per-town files
    extra = read_json(path("agency_leads_private.json"), {}) or {}     # the owner's own additions (emails he found), never in the repo
    if isinstance(extra.get("leads"), list):
        known = {L.get("id") for L in leads}
        leads = leads + [L for L in extra["leads"] if isinstance(L, dict) and L.get("id") not in known]
        for L in leads:
            e = (extra.get("emails") or {}).get(L.get("id"))
            if e and not core.lead_email(L):
                L["email"] = e
    elif isinstance(extra.get("emails"), dict):
        for L in leads:
            e = extra["emails"].get(L.get("id"))
            if e and not core.lead_email(L):
                L["email"] = e
    words = read_json(os.path.join(WEB, "agency", "outreach", "scripts.json"), {}) or {}
    offers = read_json(os.path.join(WEB, "agency", "offers", "offers.json"), {}) or {}
    sites = read_json(os.path.join(WEB, "agency", "sites", "index.json"), {}) or {}
    codes = dict(read_json(os.path.join(ROOT, "tools", "site_factory_codes.json"), {}) or {})
    codes.update(sites.get("codes") if isinstance(sites, dict) and isinstance(sites.get("codes"), dict) else {})
    for L in leads:
        if isinstance(L, dict) and codes.get(L.get("id")):
            L["_code"] = str(codes[L["id"]])
    s = sites.get("sites") if isinstance(sites, dict) else None
    if isinstance(s, list):
        s = {x.get("id"): x.get("url") for x in s if isinstance(x, dict)}
    return leads, words, offers, s if isinstance(s, dict) else {}


def post_public(counts: dict) -> bool:
    """the counts as the PC report's tiny card (data/agency_mail/summary.json -> pc_report's ext block "am"): no post of its own on ntfy"""
    from . import card
    return card.write_card(counts, ROOT)


def notify_owner(text: str) -> bool:
    """one push on the owner's PRIVATE alert topic (the same %USERPROFILE%\\.olympus\\ntfy.json the PC report uses)"""
    c = read_json(path("ntfy.json"), {}) or {}
    topic = str(c.get("topic") or "")
    if not topic or c.get("on", True) is False:
        return False
    try:
        req = urllib.request.Request(f"{str(c.get('ntfy') or 'https://ntfy.sh').rstrip('/')}/{topic}", data=text.encode("utf-8"), method="POST",
                                     headers={"Title": "Agency inbox", "Tags": "email"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def never_add(lead_id: str, email_addr: str = "") -> None:
    """%USERPROFILE%\\.olympus\\agency_never.json: lead ids + emails that never get an email or a postcard again (tools/postcards.py reads it)"""
    p = path("agency_never.json")
    n = read_json(p, {}) or {}
    ids, ems = set(n.get("lead_ids") or []), set(n.get("emails") or [])
    if lead_id:
        ids.add(str(lead_id))
    if email_addr and core.valid_email(email_addr):
        ems.add(core.norm_email(email_addr))
    write_json(p, {"v": 1, "lead_ids": sorted(ids), "emails": sorted(ems)})


# ------------------------------------------------------------------------------------------------ one pass
def caller_share(h: str | None = None) -> dict:
    """day-caller's <home>/caller/share/ (tools/caller): consent/<id>.json (a business asked for the assistant's call), outbox/<id>.json
    (an email the caller promised: demo / booking / payment, "to" = the address said on the call), status/<lead_id>.json ({lead_id, s, t, outcome}).
    files = the copies the PC pushes to agency-inbox as caller/... ("to" masked: no business address in the repo)"""
    base = os.path.join(h or home(), "caller", "share")
    out = {"files": {}, "consent": set(), "outbox": [], "status": {}}
    for sub in ("consent", "outbox", "status"):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            j = read_json(os.path.join(d, n), None) if n.endswith(".json") else None
            if not isinstance(j, dict):
                continue
            out["files"][f"caller/{sub}/{n}"] = dict(j, to=mask_addr(j["to"])) if j.get("to") else j
            if sub == "consent" and j.get("lead_id"):
                out["consent"].add(str(j["lead_id"]))
            elif sub == "outbox":
                out["outbox"].append(dict(j, id=str(j.get("id") or "call-" + n[:-5]), from_app="caller"))
            elif sub == "status" and j.get("lead_id"):
                out["status"][str(j["lead_id"])] = j
    return out


def caller_stop(L: dict | None) -> None:
    """an email opt-out also goes on the caller's do-not-call list and revokes any call consent (tools/caller, when it is installed)"""
    ph = str((L or {}).get("phone") or "")
    if not ph:
        return
    try:
        from tools.caller import compliance as G, consent as K   # day-caller's package; absent = nothing to do
    except Exception:  # noqa: BLE001
        return
    for fn in (G.add_dnc, K.revoke):
        try:
            fn(ph, "email stop")
        except Exception:  # noqa: BLE001
            pass


def run_once(cfg: dict, state: dict, leads: list, words: dict, offers: dict, sites: dict, now: dt.datetime | None = None,
             smtp_factory=None, imap_factory=None, push=None, outbox=None, notify=notify_owner, public=post_public, sleep=time.sleep,
             caller=None) -> dict:
    """returns {sent: [...], inbox: [...], outbox: [...], errors: [...]}; state is changed in place"""
    res = {"sent": [], "inbox": [], "outbox": [], "errors": [], "mode": cfg.get("mode")}
    if cfg.get("mode") not in ("dry", "live"):
        return res
    probs = core.cfg_problems(cfg)
    if probs:
        res["errors"].append("setup incomplete: " + ", ".join(probs))
        return res
    dry = cfg["mode"] == "dry"
    day = core.day_of(now)
    files = {}
    # 1. replies (any time): classify, trim, stop the sequence, suppress opt-outs and bounces
    # 0. the AI caller's share: a business that asked for the call (or was called) leaves the email sequence; its files ride the push
    cs = (caller or caller_share)()
    for lid in cs["consent"]:
        state["replied"].setdefault(lid, "call_me")
    for lid, x in cs["status"].items():
        state["replied"].setdefault(lid, "call_" + str(x.get("s") or "called"))
    for k, v in cs["files"].items():
        h = hashlib.sha1(json.dumps(v, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        if state["caller_pushed"].get(k) != h:
            files[k] = v
            state["caller_pushed"][k] = h
    to_lead = {}
    for lid, log_ in state["sent"].items():
        for x in log_:
            to_lead[core.norm_email(x.get("to"))] = lid
    byid = {L.get("id"): L for L in leads if isinstance(L, dict)}
    code_to = {str(L["_code"]): L.get("id") for L in leads if isinstance(L, dict) and L.get("_code")}
    try:
        msgs = mailer.fetch_new(cfg, int(state.get("last_uid") or 0), factory=imap_factory)
    except Exception as e:  # noqa: BLE001
        msgs = []
        res["errors"].append("inbox: " + redact(str(e)[:160], cfg))
    for m in msgs:
        state["last_uid"] = max(int(state.get("last_uid") or 0), int(m["uid"]))
        cls = core.classify(m["subject"], m["from"] + " " + m.get("from_name", ""), m["text"])
        addr = core.bounced_address(m["text"], set(to_lead)) if cls == "bounce" else m["from"]
        lid = to_lead.get(core.norm_email(addr))
        mc = CODE_RE.search(m.get("subject", "") + " " + m["text"]) if not lid and cls != "bounce" else None
        if mc and mc.group(1) in code_to and core.valid_email(m["from"]):   # a postcard reply naming its code (FR-27): that business
            lid = code_to[mc.group(1)]
            state["pc_from"][lid] = core.norm_email(m["from"])
        if not lid and cls == "optout":                   # a "STOP + business name" email about a postcard: that business never again
            body = (m.get("subject", "") + " " + core.trim(m["text"], mask=False)).lower()
            for L in leads:
                nm = str(L.get("name") or "").lower()
                if len(nm) >= 5 and nm in body:
                    never_add(L.get("id"), m["from"])
                    caller_stop(L)
                    res["inbox"].append({"id": f"r{m['uid']}", "lead_id": L.get("id"), "business": L.get("name"), "class": "optout", "words": "", "subject": "", "t": int(time.time())})
                    break
            continue
        if not lid:
            continue                                      # not a reply to the autopilot: never read further, never stored
        if cls in ("optout", "bounce"):
            core.suppress(state, addr)
            never_add(lid, addr)                          # the ONE never-again list the postcards read too
            caller_stop(byid.get(lid))                    # and the caller's do-not-call list
        state["replied"][lid] = cls
        core.day_counts(state, day)["replies_in"] += 1
        item = {"id": f"r{m['uid']}", "lead_id": lid, "business": (byid.get(lid) or {}).get("name", ""), "class": cls,
                "words": core.trim(m["text"]) if cls != "bounce" else "", "subject": core.trim(m["subject"], limit=120), "t": int(time.time())}
        state["inbox"] = (state.get("inbox") or [])[-299:] + [dict(item, msg_id=m.get("message_id", ""))]
        files[f"inbox/{item['id']}.json"] = item
        res["inbox"].append(item)
    # 2. Claude's drafts: the allowed kinds go out, the rest wait for the owner (one push)
    allowed = {u for u in (cfg.get("booking_link"), cfg.get("payment_link"), PUB.public_base(cfg.get("site_base"))) if u}
    held = []
    for d in list((outbox or (lambda: []))()) + cs["outbox"]:
        did = str(d.get("id") or "")
        if not did or did in state["outbox_done"]:
            continue
        lid = d.get("lead_id")
        log_ = state["sent"].get(lid) or []
        to = core.norm_email(log_[0]["to"]) if log_ else ""
        if not to and d.get("from_app") == "caller" and not d.get("inbox_id") and core.valid_email(d.get("to") or ""):
            to = core.norm_email(d["to"])                 # the caller's promised email: the address the business said on the call
        if not to and state["pc_from"].get(lid):
            to = state["pc_from"][lid]                     # a business that wrote in about its postcard
        ok, why = core.draft_ok(d, cfg, allowed)
        body = core.ensure_footer(str(d.get("body") or ""), cfg)
        subj = str(d.get("subject") or "Re: your website")[:150]
        if not to or core.suppressed(state, to):
            rec = {"id": did, "status": "refused", "why": "no address or they said no", "t": int(time.time())}
        elif not ok:
            if did not in state["flagged"]:
                held.append(f"{(byid.get(lid) or {}).get('name', lid)}: {why}")
                state["flagged"] = (state["flagged"] + [did])[-500:]
            continue                                       # stays in the outbox until approved
        elif core.compliant(body, cfg, "x"):
            rec = {"id": did, "status": "refused", "why": "; ".join(core.compliant(body, cfg, "x")), "t": int(time.time())}
        else:
            try:
                inb = next((x for x in state.get("inbox") or [] if x.get("id") == d.get("inbox_id")), {})
                with mailer.Smtp(cfg, smtp_factory) as s:
                    mid = s.send(cfg["test_address"] if dry else to, (f"[DRY RUN to {to}] " if dry else "") + subj, body, inb.get("msg_id", ""))
                core.record_sent(state, lid, to, "reply", now, mid) if not dry else None
                rec = {"id": did, "status": "sent" + (" (dry run: to your test address)" if dry else ""), "why": why, "t": int(time.time())}
            except Exception as e:  # noqa: BLE001
                res["errors"].append("reply: " + redact(str(e)[:160], cfg))
                continue
        state["outbox_done"][did] = rec["status"]
        files[f"sent/{did}.json"] = rec
        res["outbox"].append(rec)
    # 3. the day's follow-ups and new emails (Mon-Fri 9-16 ET, the caps)
    if dry:
        dstate = json.loads(json.dumps(state))
        n_dry = int((state.get("dry") or {}).get(day, 0)) if isinstance(state.get("dry"), dict) else 0
        todo = core.plan(leads, dstate, now)[:max(0, 3 - n_dry)]   # a dry run: 3 samples a day to your own address, nobody marked
    else:
        todo = core.plan(leads, state, now)
    if todo:
        try:
            with mailer.Smtp(cfg, smtp_factory) as s:
                for i, job in enumerate(todo):
                    msg = core.message(words, job["lead"], job["step"], cfg, offers, sites)
                    bad = core.compliant(msg["body"], cfg, msg["subject"])
                    if bad:
                        res["errors"].append(f"{job['lead'].get('name')}: not sent ({'; '.join(bad)})")
                        continue
                    if i:
                        sleep(random.uniform(20, 60))       # paced like a person, not a burst
                    if dry:
                        s.send(cfg["test_address"], f"[DRY RUN to {job['lead'].get('name')}] {msg['subject']}", msg["body"])
                        state["dry"] = {day: int((state.get("dry") or {}).get(day, 0)) + 1} if isinstance(state.get("dry"), dict) else {day: 1}
                    else:
                        mid = s.send(job["to"], msg["subject"], msg["body"])
                        core.record_sent(state, job["lead"]["id"], job["to"], job["step"], now, mid)
                    res["sent"].append({"lead": job["lead"].get("name"), "step": job["step"], "dry": dry})
        except Exception as e:  # noqa: BLE001
            res["errors"].append("send: " + redact(str(e)[:160], cfg))
    # 4. the private branch + the page's counts + one push for the owner when something needs him
    queue = sum(1 for L in leads if isinstance(L, dict) and core.lead_email(L) and L.get("id") not in state["sent"] and not core.suppressed(state, core.lead_email(L)))
    counts = core.public_counts(state, cfg, queue, now)
    files["status.json"] = dict(counts, kind="agency-mail-status", needs_owner=held[:20])
    if push:
        err = push(files, f"agency mail {day}: {len(res['inbox'])} in, {len(res['sent'])} out")
        if err == bridge.PUBLIC_MSG:
            res["held_local"] = True                      # not an error: H1, the repo is public (the owner makes it private)
            for k in [k for k in files if k.startswith("caller/")]:
                state["caller_pushed"].pop(k, None)
        elif err:
            res["errors"].append("branch: " + redact(err, cfg))
            for k in [k for k in files if k.startswith("caller/")]:
                state["caller_pushed"].pop(k, None)       # not on the branch yet: try those again next run
    if public:
        public(counts)                                    # the PC report's tiny card (agency/autopilot/card.py), never an ntfy post of its own
    want = [x for x in res["inbox"] if x["class"] in ("interested", "question")]
    sent_notes = (state.setdefault("notes", {}) if isinstance(state.get("notes"), dict) else state.update(notes={}) or state["notes"])
    if notify and (want or held) and int(sent_notes.get(day, 0)) < 4:     # 4 pushes a day at most: the PC shares ntfy's per-IP budget with the bot's alerts
        state["notes"] = {day: int(sent_notes.get(day, 0)) + 1}
        parts = [f"{len(want)} repl{'y' if len(want) == 1 else 'ies'} to answer ({', '.join(x['business'] for x in want[:3])})"] if want else []
        if held:
            parts.append(f"{len(held)} draft{'s' if len(held) > 1 else ''} wait for your OK")
        notify("Agency: " + "; ".join(parts) + ". Claude drafts the answers; open the agency-inbox branch or ask Claude.")
    return res


# ------------------------------------------------------------------------------------------------ commands
def setup(ask=input, secret=getpass.getpass, out=print) -> int:
    old = load_cfg()
    out("EMAIL AUTOPILOT setup. Everything stays on this PC (%USERPROFILE%\\.olympus\\agency_mail.json). Nothing is sent now.")
    out("You need a FREE business Gmail and an app password (Google account > Security > 2-Step Verification > App passwords).")

    def q(label, key, hidden=False):
        cur = old.get(key) or ""
        shown = "(saved)" if hidden and cur else cur
        v = (secret if hidden else ask)(f"  {label}{' [' + shown + ']' if shown else ''}: ").strip()
        return v or cur

    c = dict(old)
    c["from_address"] = q("Gmail address that sends", "from_address")
    c["app_password"] = q("Its app password (hidden as you type)", "app_password", hidden=True).replace(" ", "")
    c["from_name"] = q("Your name (the sender)", "from_name")
    c["business_name"] = q("Your business name", "business_name")
    c["phone"] = q("Your business phone", "phone")
    c["postal_address"] = q("Postal address for every email (a PO box is fine)", "postal_address")
    c["test_address"] = q("Your own address for test emails", "test_address")
    c["booking_link"] = q("Booking link (optional, e.g. a free calendar page)", "booking_link")
    c["payment_link"] = q("Payment link from your own free payment account (optional, owner step)", "payment_link")
    c = core.norm_cfg(c)
    probs = core.cfg_problems(c)
    if probs:
        c["mode"] = "off"
        write_json(path("agency_mail.json"), c, private=True)
        out("  Saved, but still OFF: missing " + ", ".join(probs) + ". Run tools/bat/EMAIL_SETUP.bat again.")
        return 1
    out("")
    out("  Type SEND EMAILS to let it email businesses for real (max 20 new a day, Mon-Fri 9-16 ET, opt-outs honoured).")
    out("  Anything else = DRY RUN: every email goes to your test address only.")
    phrase = ask("  > ").strip()
    c["mode"] = "live" if phrase == core.PHRASE else "dry"
    c["t_set"] = int(time.time())
    write_json(path("agency_mail.json"), c, private=True)
    log(c, {"t": int(time.time()), "ev": "setup", "mode": c["mode"]})
    out(f"  [OK] Saved. Mode: {c['mode'].upper()}{' (real emails)' if c['mode'] == 'live' else ' (test address only)'}. tools/bat/EMAIL_STOP.bat turns it off.")
    return 0


def stop(out=print) -> int:
    c = load_cfg()
    c["mode"] = "off"
    write_json(path("agency_mail.json"), c, private=True)
    log(c, {"t": int(time.time()), "ev": "stop"})
    out("  [OK] Email autopilot OFF. Nothing is sent until tools/bat/EMAIL_SETUP.bat and the phrase again.")
    return 0


def status(out=print) -> int:
    c, s = load_cfg(), core.norm_state(read_json(path("agency_mail_state.json"), {}))
    leads, *_ = site_data()
    counts = core.public_counts(s, c, sum(1 for L in leads if core.lead_email(L) and L.get("id") not in s["sent"]))
    out(f"  Mode {c['mode'].upper()} · sender {mask_addr(c.get('from_address'))} · today {counts['new']}/{counts['cap']} new, {counts['followup']} follow-ups, "
        f"{counts['replies_today']} replies · {counts['interested']} interested · {counts['suppressed']} never-again · {counts['queue']} waiting")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The Website Factory's email autopilot (OFF until tools/bat/EMAIL_SETUP.bat + SEND EMAILS).")
    ap.add_argument("cmd", choices=["setup", "run", "stop", "status", "test"])
    a = ap.parse_args(argv)
    if a.cmd == "setup":
        return setup()
    if a.cmd == "stop":
        return stop()
    if a.cmd == "status":
        return status()
    cfg = load_cfg()
    if a.cmd == "test":
        probs = core.cfg_problems(cfg)
        if probs:
            print("  [FIX] missing: " + ", ".join(probs))
            return 1
        try:
            with mailer.Smtp(cfg) as s:
                s.send(cfg["test_address"], "Olympus email autopilot: test", core.ensure_footer(f"It works. Sent by {cfg['from_name']}.", cfg))
            print(f"  [OK] test email sent to {mask_addr(cfg['test_address'])}")
            return 0
        except Exception as e:  # noqa: BLE001
            print("  [FIX] could not send: " + redact(str(e)[:200], cfg))
            return 1
    state = core.norm_state(read_json(path("agency_mail_state.json"), {}))
    leads, words, offers, sites = site_data()
    url, wd = bridge.remote_url(ROOT), path("agency_inbox")
    res = run_once(cfg, state, leads, words, offers, sites,
                   push=(lambda files, msg: bridge.write_and_push(url, wd, files, msg)) if cfg.get("mode") != "off" else None,
                   outbox=(lambda: (bridge.sync(url, wd) or True) and bridge.read_outbox(wd)) if cfg.get("mode") != "off" else None)
    write_json(path("agency_mail_state.json"), state, private=True)
    try:                                                  # the postcards ride the same task (tools/postcards.py; OFF unless tools/bat/POSTCARD_SETUP.bat)
        sys.path.insert(0, ROOT)
        from tools import postcards as PC
        pc = PC.norm_cfg(read_json(path("postcards.json"), {}))
        if pc["mode"] != "off":
            pst = read_json(path("postcards_state.json"), {}) or {}
            pl, ps = PC.leads_and_sites()
            pr = PC.run_once(pc, pst, pl, ps)
            write_json(path("postcards_state.json"), pst)
            rr = PC.results(pst, pl)                       # the results table by code (responded / call me / claimed): `postcards.py results`
            write_json(path("postcards_results.json"), rr)
            if url and rr["rows"]:
                e2 = bridge.write_and_push(url, wd, {"postcards/results.json": rr}, "postcard results")
                res["errors"] += ["postcards branch: " + e2] if e2 and e2 != bridge.PUBLIC_MSG else []
            res["errors"] += ["postcards: " + e for e in pr["errors"][:3]]
            res["postcards"] = len(pr["sent"])
    except Exception as e:  # noqa: BLE001
        res["errors"].append("postcards: " + str(e)[:120])
    log(cfg, {"t": int(time.time()), "ev": "run", "mode": res["mode"], "sent": len(res["sent"]), "in": len(res["inbox"]), "outbox": len(res["outbox"]), "errors": res["errors"][:5]})
    print(redact(f"  mode {res['mode']}: sent {len(res['sent'])}, replies {len(res['inbox'])}, drafts {len(res['outbox'])}" + (f", problems: {res['errors'][:2]}" if res["errors"] else ""), cfg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
