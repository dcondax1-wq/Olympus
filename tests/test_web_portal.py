"""THE CALLER PORTAL (tools/web_public/agency/portal/ + agency/portal.py, day-a11y 2026-11-21; plan research/writeups/cold-calling-plan-2026-11-20.md).

    python -X utf8 -m tests.test_web_portal            (--static: no browser)
a. static: noindex, self-contained (no Olympus file, relative paths only: it must run on the neutral host), no secret, never the owner's
   address, no texting, the identify line + the rules on the page, a passphrase hash only
b. core (node): the window (weekdays 9-17 their time, holidays, weekends), 1 call + 1 follow-up, never twice in a day, no / do not call =
   never again, a missing number, the site link only from a clean public_base, the email's CAN-SPAM parts, add a business, the tally
c. the PC side: build (chains / a website / the never list left out, numbers first, codes + site paths), the passphrase (salted hash, never
   the phrase), import (never-again for every channel, new businesses for the factory, numbers found by hand, commissions per caller)
d. browser 390 x 844 + 320: locked without the passphrase, the right one opens it, tap-to-call, logging blocks a second call that day, add
   a business, find a number, the email opens the agency Gmail compose with the link, no sideways scroll, 44 px controls, no page error
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
D = os.path.join(ROOT, "tools", "web_public", "agency", "portal")
FAILS: list = []
N = [0]


def check(name, ok, info=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  [{str(info)[:300]}]"))
    if not ok:
        FAILS.append(name)


def read(name):
    with open(os.path.join(D, name), encoding="utf-8") as fh:
        return fh.read()


def static():
    html, js, core, css = read("index.html"), read("portal.js"), read("portalcore.js"), read("portal.css")
    allsrc = html + js + core + css
    check("a. noindex + no referrer", 'name="robots" content="noindex, nofollow"' in html and 'name="referrer" content="no-referrer"' in html)
    refs = re.findall(r'(?<![\w-])(?:src|href)="([^"#]+)"', html) + re.findall(r"from '([^']+)'", js + core) + re.findall(r"getJSON\('([^']+)'\)", js)
    check("a. self-contained: every file it loads sits in its own folder (no ../, no Olympus kit, no CDN)",
          refs and all(not r.startswith(("../", "/", "http")) or r.startswith("data:") for r in refs) and "olympus" not in html.lower().replace("no olympus file", ""), refs)
    handle = "dcon" + "dax"                      # the owner's GitHub handle: no shipped agency file names it (the check lives in agency/public.py)
    hits = []
    for dp, _, fs in os.walk(os.path.join(ROOT, "tools", "web_public", "agency")):
        for f in fs:
            if f.endswith((".html", ".js", ".css", ".json", ".txt", ".svg", ".webmanifest", ".md", ".xml")):
                t = open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read().lower()
                if handle in t or "github.io/jarvis" in t:
                    hits.append(os.path.relpath(os.path.join(dp, f), ROOT))
    check("a. no file under tools/web_public/agency/ names the owner's handle or his dashboards' address", not hits, hits[:5])
    check("a. no secret in the folder: portal.json holds a salted hash only (never a phrase)",
          set(json.loads(read("portal.json")).get("pass", {})) <= {"salt", "sha256"} and "password" not in read("portal.json").lower())
    check("a. the identify-yourself line and the rules are on the page (9-5 their time, 1 call + 1 follow-up, never twice a day, never a recording / AI / text)",
          "Say this first" in html and "Weekdays 9:00 am to 5:00 pm, their time" in html and "1 call + 1 follow-up" in html and "never twice in a day" in html
          and "never an AI voice, never a text" in html)
    check("a. no texting anywhere (no sms: links), calls are tel: only", "sms:" not in allsrc and "tel:+1" in core)
    check("a. light + dark, 44 px controls in the CSS", "prefers-color-scheme: dark" in css and "min-height: 44px" in css)


NODE = r"""
import * as P from '%s';
const out = {}, conf = {tz: 'America/New_York', hours: [540, 1020], public_base: 'https://sites.example.com', agency: 'Peak Web', agency_email: 'peak@gmail.example',
  postal: 'PO Box 12, Frederick MD 21701', prices: {starter: '$1,500 + $79/month', monthly: '$149/month'}, commission: {sale: 300, booked_show: 40}};
const T = (s) => Date.parse(s);
out.mon10 = P.windowAt(T('2026-11-23T15:00:00Z'), conf).open; out.mon1659 = P.windowAt(T('2026-11-23T21:59:00Z'), conf).open; out.mon17 = P.windowAt(T('2026-11-23T22:00:00Z'), conf).open;
out.mon859 = P.windowAt(T('2026-11-23T13:59:00Z'), conf).open; out.sat = P.windowAt(T('2026-11-21T15:00:00Z'), conf); out.thx = P.windowAt(T('2026-11-26T15:00:00Z'), conf);
out.blackfri = P.windowAt(T('2026-11-27T15:00:00Z'), conf).open; out.summer = P.windowAt(T('2026-07-07T13:30:00Z'), conf).open;  // 9:30 EDT
out.hol = [P.holidays(2026)['2026-11-26'], P.holidays(2027)['2027-07-05'], P.holidays(2026)['2026-05-25']];
const st = P.emptyState(); st.caller = 'Ann';
const L = {id: 'a', name: 'Ace Roofing', phone: '(301) 555-0100', site: 'f/abcdefgh/', code: 'FR-1'};
out.s0 = P.statusOf(L, st, T('2026-11-23T15:00:00Z'), conf);
P.logOutcome(st, L, 'voicemail', T('2026-11-23T15:00:00Z'));
out.s1 = P.statusOf(L, st, T('2026-11-23T20:00:00Z'), conf); out.s1b = P.statusOf(L, st, T('2026-11-24T15:00:00Z'), conf); out.s2 = P.statusOf(L, st, T('2026-11-25T15:00:00Z'), conf);
P.logOutcome(st, L, 'called', T('2026-11-25T15:00:00Z'));
out.s3 = P.statusOf(L, st, T('2026-11-30T15:00:00Z'), conf);
const B = {id: 'b', name: 'Bee Salon', phone: '3015550111', site: 'f/zzzzzzzz/'};
P.logOutcome(st, B, 'dnc', T('2026-11-23T15:00:00Z')); out.sb = P.statusOf(B, st, T('2026-12-10T15:00:00Z'), conf); out.dnc = st.dnc.slice();
P.undoLast(st, 'b'); out.undo = [st.dnc.length, P.statusOf(B, st, T('2026-11-23T16:00:00Z'), conf).tone];
const C = {id: 'c', name: 'Cee Auto', phone: '', site: 'f/cccccccc/'};
out.sc = P.statusOf(C, st, T('2026-11-23T15:00:00Z'), conf); st.phones.c = '240-555-0123'; out.sc2 = P.statusOf(C, st, T('2026-11-23T15:00:00Z'), conf).tone;
out.site = [P.siteUrl(L, conf), P.siteUrl(L, Object.assign({}, conf, {public_base: 'ftp://files.example'})), P.siteUrl(L, Object.assign({}, conf, {public_base: ''})),
  P.siteUrl({site: '../../x/'}, conf), P.siteUrl(L, Object.assign({}, conf, {public_base: 'http://plain.example'}))];
const m = P.emailFor(L, 'Ann', conf); out.mail = m; out.gmail = P.gmailUrl(conf, 'boss@ace.example', m.subject, m.body);
out.notReady = P.emailFor(L, 'Ann', Object.assign({}, conf, {postal: ''})).ready;
out.tel = [P.telHref('(301) 555-0100'), P.telHref('555-0100'), P.prettyPhone('13015550100')];
out.maps = P.mapsUrl({name: 'Joe & Sons', town: 'Frederick', state: 'MD'});
out.add = [P.addBusiness(st, {name: 'Dee Plumbing', phone: '301 555 0199', town: 'Frederick', niche: 'trades'}, 1).lead, P.addBusiness(st, {name: 'Dup', phone: '3015550199', town: 'F'}, 2).error,
  P.addBusiness(st, {name: 'Xy', phone: '12', town: 'F'}, 3).error];
out.all = P.allLeads([L], st).map((x) => x.id);
out.tally = P.tally(st, conf, 0);
out.junk = P.loadState('{"log":[{"t":"x"},{"t":1,"id":"a","k":"hack"},{"t":2,"id":"a","k":"won"}],"dnc":[1,"z"]}');
out.ident = P.identify('Ann', 'Peak Web');
out.exp = Object.keys(P.exportDoc(st, 0)).sort();
console.log(JSON.stringify(out));
"""


def node():
    if not shutil.which("node"):
        print("SKIP node: no node")
        return
    tmp = tempfile.mkdtemp(prefix="portal-node-")
    try:
        f = os.path.join(tmp, "t.mjs")
        open(f, "w").write(NODE % os.path.join(D, "portalcore.js").replace("\\", "/"))
        r = subprocess.run(["node", f], capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("b. node ran", False, r.stderr[-400:])
            return
        o = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("b. the window: 9:00 am to 5:00 pm their time (8:59 and 5:00 pm closed), daylight time handled",
          o["mon10"] and o["mon1659"] and not o["mon17"] and not o["mon859"] and o["summer"], o)
    check("b. weekends, Thanksgiving and the day after are closed, with when it opens", not o["sat"]["open"] and o["sat"]["why"] == "Weekend" and o["sat"]["next"] == "Mon 9:00 am"
          and not o["thx"]["open"] and "Thanksgiving" in o["thx"]["why"] and not o["blackfri"], (o["sat"], o["thx"]))
    check("b. federal holidays (observed dates)", o["hol"] == ["Thanksgiving", "Independence Day", "Memorial Day"], o["hol"])
    check("b. 1 call + 1 follow-up: first call, never twice in a day, the follow-up comes back on its day (a voicemail: 2 workdays), then done",
          o["s0"]["ok"] and o["s0"]["why"] == "First call" and not o["s1"]["ok"] and "Called today" in o["s1"]["why"] and "Wed Nov 25" in o["s1"]["why"]
          and not o["s1b"]["ok"] and "Follow-up tomorrow (after a voicemail)" == o["s1b"]["why"] and o["s2"]["ok"] and o["s2"]["due"] and "Follow-up due" in o["s2"]["why"] and o["s3"]["tone"] == "done" and "1 call + 1 follow-up" in o["s3"]["why"], (o["s1"], o["s3"]))
    check("b. 'do not call' = never again (and undo within reach for a mis-tap)", o["sb"]["tone"] == "done" and "never again" in o["sb"]["why"] and o["dnc"] == ["b"]
          and o["undo"][0] == 0, (o["sb"], o["undo"]))
    check("b. no number = 'find the number first'; a number found by hand makes it callable", o["sc"]["tone"] == "need" and o["sc2"] == "go", o["sc"])
    check("b. the site link = <public_base>/f/<id>/ (the neutral host's layout), only from an https base and an f/<id>/ path",
          o["site"] == ["https://sites.example.com/f/abcdefgh/", "", "", "", ""], o["site"])
    mb = o["mail"]["body"]
    check("b. the email: honest subject, the link, the sender + agency, the postal address, 'no thanks'; not ready without the postal address",
          o["mail"]["ready"] and o["mail"]["subject"] == "The website we built for Ace Roofing" and "https://sites.example.com/f/abcdefgh/" in mb
          and "Ann, Peak Web" in mb and "PO Box 12" in mb and "no thanks" in mb and not o["notReady"], mb[:300])
    check("b. 'Email them the link' opens the AGENCY Gmail's compose (authuser), nothing is sent by the page",
          o["gmail"].startswith("https://mail.google.com/mail/?view=cm&fs=1&authuser=peak%40gmail.example&to=boss%40ace.example&su="), o["gmail"][:120])
    check("b. tap-to-call tel:+1 only for a real 10-digit number", o["tel"] == ["tel:+13015550100", "", "(301) 555-0100"], o["tel"])
    check("b. Google Maps search link (a link, no scraping)", o["maps"] == "https://www.google.com/maps/search/?api=1&query=Joe%20%26%20Sons%20Frederick%20MD", o["maps"])
    check("b. add a business: saved with the caller's name; a duplicate number or a bad number is refused",
          o["add"][0]["by"] == "Ann" and o["add"][0]["phone"] == "3015550199" and "Already" in o["add"][1] and "10-digit" in o["add"][2] and "add-1" in o["all"], o["add"])
    check("b. the tally: calls, booked, won, and what it could pay ($300 a sale, $40 a booked call)", o["tally"]["calls"] == 2 and o["tally"]["maybe"] == 0, o["tally"])
    check("b. a junk saved state loads safely (bad lines dropped)", len(o["junk"]["log"]) == 1 and o["junk"]["dnc"] == ["z"], o["junk"])
    check("b. the identify line", o["ident"] == "Hi, it's Ann with Peak Web. We build websites for local businesses.", o["ident"])
    check("b. the export carries the log, the added businesses, the numbers found, the caller", o["exp"] == ["added", "app", "caller", "exported", "log", "phones", "v", "version"], o["exp"])


def pcside():
    tmp = tempfile.mkdtemp(prefix="portal-pc-")
    os.environ["OLYMPUS_HOME"] = os.path.join(tmp, "home")
    from agency import portal as PT
    try:
        web = os.path.join(tmp, "web")
        os.makedirs(os.path.join(web, "leads"))
        os.makedirs(os.path.join(web, "factory"))
        leads = [{"id": "a", "name": "Ace Roofing", "phone": "+1 301-555-0100", "town": "Frederick", "state": "MD", "niche": "trades"},
                 {"id": "b", "name": "Subway", "phone": "3015550101", "town": "Frederick"},
                 {"id": "c", "name": "Has Site Cafe", "website": "https://x.example", "town": "Frederick"},
                 {"id": "d", "name": "Rosa Pizza", "town": "Frederick", "niche": "food"},
                 {"id": "e", "name": "Said No Dental", "phone": "3015550102", "town": "Frederick"},
                 {"id": "f", "name": "Glow Salon", "town": "Frederick", "niche": "beauty"}]
        json.dump({"leads": leads}, open(os.path.join(web, "leads", "leads.json"), "w"))
        json.dump({"sites": [{"id": "a", "path": "f/aaaaaaaa/", "code": "FR-1", "niche": "trades", "kind": "Roofer"}, {"id": "d", "path": "f/dddddddd/", "code": "FR-4", "niche": "food"}]},
                  open(os.path.join(web, "factory", "sites.json"), "w"))
        os.makedirs(os.environ["OLYMPUS_HOME"])
        json.dump({"lead_ids": ["e"]}, open(os.path.join(os.environ["OLYMPUS_HOME"], "agency_never.json"), "w"))
        out = os.path.join(tmp, "calllist.json")
        PT.ADDED = os.path.join(tmp, "added.json")
        d = PT.build(web, out)
        ids = [r["id"] for r in d["leads"]]
        cl = next((r for r in d["leads"] if r["id"] == "c"), {})
        check("c. build: chains and the never-again list are left out; a business WITH a website stays, last, on the redesign lane with its address; numbers first, then the best niches",
              ids == ["a", "f", "d", "c"] and d["skipped"] == {"chain": 1, "has a website": 0, "never again": 1} and cl.get("lane") == "redesign" and cl.get("url") == "https://x.example"
              and d["leads"][0]["lane"] == "no_site" and d["lanes"] == {"no_site": 3, "site_down": 0, "redesign": 1}, (ids, d["skipped"], cl))
        a = d["leads"][0]
        check("c. build: each row has the code, the site path, a clean 10-digit number; the file says public data only",
              a["code"] == "FR-1" and a["site"] == "f/aaaaaaaa/" and a["phone"] == "3015550100" and "no private data" in d["note"] and "agency_never" not in json.dumps(d), a)
        sweb = os.path.join(tmp, "split")                 # the leads team's split format: "leads": [] + "files": ["towns/<town>.json"]
        os.makedirs(os.path.join(sweb, "leads", "towns"))
        os.makedirs(os.path.join(sweb, "factory"))
        json.dump({"leads": [], "files": ["towns/frederick.json", "towns/hagerstown.json", "../evil.json"]}, open(os.path.join(sweb, "leads", "leads.json"), "w"))
        json.dump({"leads": leads[:3]}, open(os.path.join(sweb, "leads", "towns", "frederick.json"), "w"))
        json.dump({"leads": leads[3:] + [dict(leads[0], name="Dup")]}, open(os.path.join(sweb, "leads", "towns", "hagerstown.json"), "w"))
        json.dump({"sites": []}, open(os.path.join(sweb, "factory", "sites.json"), "w"))
        ds = PT.build(sweb, os.path.join(tmp, "split.json"))
        check("c. build reads the split list (leads.json 'files' -> towns/*.json), first row per id, nothing outside towns/",
              sorted(r["id"] for r in ds["leads"]) == ["a", "c", "d", "f"] and next(r for r in ds["leads"] if r["id"] == "a")["name"] == "Ace Roofing", ds["leads"])
        cp = os.path.join(tmp, "portal.json")
        c = PT.set_pass("blue river candle", cp)
        raw = open(cp).read()
        check("c. the passphrase: a salted SHA-256 only, the phrase never saved; short phrases refused",
              "blue river" not in raw and c["pass"]["sha256"] == PT.pass_hash("blue river candle", c["pass"]["salt"]) and len(c["pass"]["salt"]) == 16)
        try:
            PT.set_pass("short", cp)
            short = False
        except ValueError:
            short = True
        check("c. a passphrase under 10 characters is refused", short)
        lg = os.path.join(tmp, "portal-log-Ann.json")
        json.dump({"v": 1, "app": "agency-portal", "caller": "Ann", "log": [
            {"t": 1, "id": "a", "k": "called", "caller": "Ann"}, {"t": 2, "id": "a", "k": "won", "caller": "Ann"},
            {"t": 3, "id": "d", "k": "no", "caller": "Ann"}, {"t": 4, "id": "f", "k": "booked", "caller": "Ann"}, {"t": 5, "id": "f", "k": "hack"}],
            "added": [{"id": "add-x", "name": "Dee Plumbing", "phone": "301 555 0199", "town": "Frederick", "niche": "trades", "by": "Ann"}],
            "phones": {"f": "(240) 555-0123"}}, open(lg, "w"))
        json.dump({"v": 1, "app": "agency-portal", "caller": "Bo", "log": [{"t": 9, "id": "f", "k": "showed", "caller": "Bo"}]}, open(lg + "2", "w"))
        store = PT.merge_logs([lg, lg + "2", lg])
        new = PT.apply_never(store)
        n = PT.add_leads(store)
        nev = json.load(open(os.path.join(os.environ["OLYMPUS_HOME"], "agency_never.json")))
        check("c. import: deduped, junk outcomes dropped; a 'no' joins the ONE never-again list (email + calls)",
              len(store["log"]) == 5 and new == ["d"] and set(nev["lead_ids"]) == {"d", "e"}, (len(store["log"]), new))
        added = json.load(open(PT.ADDED))
        check("c. import: a business the caller added goes to the factory's added-leads file (public facts only)",
              n == 1 and added["leads"][0]["name"] == "Dee Plumbing" and added["leads"][0]["phone"] == "3015550199" and PT.add_leads(store) == 0)
        d2 = PT.build(web, out)
        ids2 = [r["id"] for r in d2["leads"]]
        check("c. the next build: the 'no' is gone, the number found by hand is used, the added business is on the list",
              "d" not in ids2 and next(r for r in d2["leads"] if r["id"] == "f")["phone"] == "2405550123" and "add-x" in ids2, ids2)
        rate = {"commission": {"sale": 300, "booked_show": 40, "clawback_days": 30}}
        com = {r["caller"]: r for r in PT.commissions(store, rate, paid=[])}
        check("c. commissions (pricebook 2026-11-21): a caller's own 'Won' is only PENDING until the client's money clears; one commission per "
              "business, to the first caller who logged it (Ann booked f, so Bo's 'showed' pays Ann $40)",
              com["Ann"]["owed"] == 40 and com["Ann"]["pending"] == 300 and com["Ann"]["booked"] == 1 and com["Bo"]["owed"] == 0
              and "pending" in PT.table(list(com.values())), com)
        cleared = [{"id": "a", "kind": "deposit", "t": "2026-11-23"}, {"id": "a", "kind": "launch", "t": "2026-11-30"}]
        com2 = {r["caller"]: r for r in PT.commissions(store, rate, paid=cleared)}
        check("c. once the deposit AND the launch payment cleared: $300 owed (the deposit alone is not enough)",
              com2["Ann"]["owed"] == 340 and com2["Ann"]["pending"] == 0
              and {r["caller"]: r for r in PT.commissions(store, rate, paid=cleared[:1])}["Ann"]["pending"] == 300, com2)
        refunded = cleared + [{"id": "a", "kind": "refund", "t": "2026-12-20"}]
        late = cleared + [{"id": "a", "kind": "refund", "t": "2027-01-15"}]
        c3 = {r["caller"]: r for r in PT.commissions(store, rate, paid=refunded)}["Ann"]
        c4 = {r["caller"]: r for r in PT.commissions(store, rate, paid=late)}["Ann"]
        check("c. a refund within 30 days of clearing claws the $300 back; a refund after 30 days does not",
              c3["owed"] == 40 and c3["clawback"] == 300 and c4["owed"] == 340 and c4["clawback"] == 0, (c3, c4))
        both = {"log": [{"t": 1, "id": "z1", "k": "booked", "caller": "Cy"}, {"t": 2, "id": "z1", "k": "showed", "caller": "Cy"},
                        {"t": 3, "id": "z1", "k": "won", "caller": "Cy"}, {"t": 4, "id": "z2", "k": "showed", "caller": "Cy"},
                        {"t": 5, "id": "z1", "k": "won", "caller": "Di"}]}
        mon = [{"id": "z1", "kind": "monthly", "t": d} for d in ("2026-11-23", "2026-12-23", "2027-01-23")]
        cy = {r["caller"]: r for r in PT.commissions(both, rate, paid=mon)}
        check("c. a booked call that showed AND bought is paid $300 once, never $340 (nothing upfront: after the 3rd $149 cleared); "
              "a second caller's 'Won' on the same business earns nothing",
              cy["Cy"]["owed"] == 300 + 40 and cy["Cy"]["won"] == 1 and cy["Cy"]["showed"] == 2 and cy["Di"]["owed"] == 0 and cy["Di"]["pending"] == 0, cy)
        old = os.environ.get("OLYMPUS_HOME")
        e = PT.mark_paid("z9", "deposit", "2026-11-24")
        check("c. `paid` records cleared money in the owner's ledger (and refuses a bad kind or date)",
              e == {"id": "z9", "kind": "deposit", "t": "2026-11-24"} and PT.paid_ledger()[-1] == e and old)
        try:
            PT.mark_paid("z9", "won", "2026-11-24")
            check("c. `paid` refuses a kind that is not money", False)
        except ValueError:
            check("c. `paid` refuses a kind that is not money", True)
        try:
            json.dump({"app": "other"}, open(lg + "3", "w"))
            PT.merge_logs([lg + "3"])
            refused = False
        except ValueError:
            refused = True
        check("c. import refuses a file that is not a portal export", refused)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sitecheck():
    """agency/redesign_score.py: one home-page GET, page facts only (https, viewport, (c) year, speed, size, old code); never the page's text"""
    from agency import redesign_score as SC
    old = SC.score("http://old.example/", 200, b"<html><table><p>Call 301-555-0100, bob@old.example</p><footer>&copy; 2016 Old Co</footer><script src=jquery-1.8.js></script>", 3.4, 2026)
    new = SC.score("https://new.example/", 200, b'<html><meta name="viewport" content="width=device-width"><footer>\xc2\xa9 2026</footer>', 0.6, 2026)
    check("c. the redesign score: http +3, no viewport +3, (c) 3+ years old +2, slow +2, old code +1; a modern page scores 0",
          old["score"] == 11 and new["score"] == 0 and "not mobile-friendly" in old["why"] and "old copyright (\u00a9 2016)" in old["why"], (old, new))
    check("c. the score keeps page facts only: no phone, no email, no page text", "301" not in json.dumps(old) and "bob@" not in json.dumps(old) and "Old Co" not in json.dumps(old))
    def boom(url):
        raise OSError("timeout")
    res = SC.run([{"id": "a", "url": "https://x.example"}, {"id": "b", "url": "ftp://y"}, {"id": "c", "url": "https://z.example"}],
                 get=lambda u: boom(u) if "x." in u else ("https://z.example/", 200, b'<meta name="viewport">', 0.2))
    check("c. a site that does not answer is marked down (not scored); a bad address is never fetched; results carry the check date",
          res["a"]["down"] and res["b"]["down"] and res["c"]["score"] == 0 and res["c"]["checked"], res)


def dialing_static():
    from agency import portal as PT
    html, js, core = (open(os.path.join(D, f), encoding="utf-8").read() for f in ("index.html", "portal.js", "portalcore.js"))
    check("a. dialing session: Today is the first tab and the default; the end-of-day card; the scripts drawer and the Do Not Call field on every row",
          html.index('data-f="today" aria-pressed="true"') < html.index('data-f="go"') and "filter = 'today'" in js and 'id="eodH"' in html and 'class="scripts"' in html and 'class="dncSel"' in html)
    check("a. texts only when they asked, typed by a human: no sms: link anywhere, the drawer says so", "sms:" not in html + js + core and "ONLY if they asked you to text" in html)
    lst = json.load(open(os.path.join(D, "calllist.json"), encoding="utf-8"))
    pb = json.load(open(os.path.join(ROOT, "agency", "pricebook.json"), encoding="utf-8"))
    st = next(x for x in pb["packages"] if x["id"] == "starter")
    check("a. the list carries the price book's Starter price (the pipeline's $)", lst.get("price") == {"name": st["name"], "setup": st["setup"], "monthly": st["monthly"]}, lst.get("price"))


def lanes():
    """the lanes from the Overture check: no_site / site_down / redesign, the opener per lane (the same words in Python and JS), the redesign score"""
    tmp = tempfile.mkdtemp(prefix="portal-lanes-")
    os.environ["OLYMPUS_HOME"] = os.path.join(tmp, "home")
    from agency import portal as PT
    try:
        web = os.path.join(tmp, "web")
        os.makedirs(os.path.join(web, "leads"))
        json.dump({"leads": [
            {"id": "n", "name": "No Site Co", "phone": "3015550001", "town": "Frederick", "web": {"verdict": "none"}},
            {"id": "s", "name": "Down Deli", "phone": "3015550002", "town": "Frederick", "web": {"verdict": "site_down", "url": "http://down.example", "status": "dns"}},
            {"id": "r1", "name": "Old Site Dental", "phone": "3015550003", "town": "Frederick", "website": "http://old.example", "web": {"verdict": "has_site"}},
            {"id": "r2", "name": "New Site Salon", "phone": "3015550004", "town": "Frederick", "website": "https://new.example", "web": {"verdict": "has_site"}},
            {"id": "r3", "name": "Bad Url Shop", "phone": "3015550005", "town": "Frederick", "website": "javascript:alert(1)"}]}, open(os.path.join(web, "leads", "leads.json"), "w"))
        sc = os.path.join(tmp, "scores.json")
        json.dump({"scores": {"r1": {"score": 8, "why": ["not secure (http)", "not mobile-friendly", "old copyright (\u00a9 2019)"]}, "r2": {"score": 1, "why": ["heavy page"]}}}, open(sc, "w"))
        PT.SCORES, PT.ADDED = sc, os.path.join(tmp, "added.json")
        out = os.path.join(tmp, "list.json")
        d = PT.build(web, out)
        by = {r["id"]: r for r in d["leads"]}
        check("c. lanes: no website -> no_site, a site that did not load -> site_down, a working site -> redesign (with its score and the reasons); a site with no usable address is left out",
              by["n"]["lane"] == "no_site" and by["s"]["lane"] == "site_down" and by["r1"]["lane"] == "redesign" and by["r1"]["score"] == 8 and "not mobile-friendly" in by["r1"]["why"]
              and "r3" not in by and d["lanes"] == {"no_site": 1, "site_down": 1, "redesign": 2}, (by, d["lanes"]))
        check("c. redesign rows come after the first-site rows, the most dated site first", [r["id"] for r in d["leads"]][-2:] == ["r1", "r2"], [r["id"] for r in d["leads"]])
        raw = open(out, encoding="utf-8").read()
        check("c. the list file is compact (no indent) and leaves the standard opener out (the page says the same words)", "\n" not in raw.strip() and '"opener"' not in raw, raw[:200])
        js = open(os.path.join(D, "portalcore.js"), encoding="utf-8").read()
        same = all(PT.OPENERS[k].replace("{name}", "{n}").replace("'", "\\'") in js for k in PT.OPENERS)
        check("c. the opener per lane is the same in Python (agency/portal.py OPENERS) and the page (portalcore.js)", same)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


NODE3 = r"""
import * as P from '%s';
const o = {}, T = (x) => Date.parse(x);
const c = {tz: 'America/New_York', hours: [540, 1020], agency: 'Peak Web', agency_number: '(301) 555-0142', public_base: 'https://sites.example.com'};
o.wd = [P.addWorkdays('2026-11-23', 2), P.addWorkdays('2026-11-25', 2), P.addWorkdays('2026-11-20', 1)];
o.best = [P.bestWindows({niche: 'trades'}, c), P.bestWindows({niche: 'food'}, c), P.bestWindows({niche: 'retail'}, c), P.bestWindows({niche: 'trades'}, Object.assign({}, c, {hours: [420, 1080]}))];
o.inBest = [P.inBest({niche: 'food'}, T('2026-11-23T19:30:00Z'), c), P.inBest({niche: 'food'}, T('2026-11-23T15:00:00Z'), c)];
const st = P.emptyState(); st.caller = 'Ann';
const mk = (i, niche) => ({id: 'x' + i, name: 'Biz ' + i, phone: '30155501' + String(10 + i), niche, site: 'f/abcdefgh/'});
const leads = [mk(1, 'retail'), mk(2, 'food'), mk(3, 'food'), mk(4, 'retail')];
P.logOutcome(st, leads[3], 'voicemail', T('2026-11-20T15:00:00Z'));      // Fri: its follow-up is due Tue 11-24
const tl = P.todayList(leads, st, T('2026-11-24T19:30:00Z'), c, 60);     // Tue 2:30 pm ET: food is in its best hour
o.today = tl.map((r) => [r.L.id, !!r.s.due, r.best]);
o.n60 = P.todayList(Array.from({length: 90}, (_, i) => mk(i + 10, 'food')), P.emptyState(), T('2026-11-24T19:30:00Z'), c, 60).length;
const D = mk(7, 'food'); o.dnc = [P.dncOf(D, st), P.dncOf(Object.assign({dnc: 'clear'}, D), st)]; P.setDnc(st, D, 'listed');
o.dncS = P.statusOf(D, st, T('2026-11-24T15:00:00Z'), c); o.dncLoad = P.loadState(JSON.stringify({dncCheck: {a: 'listed', b: 'hack'}})).dncCheck;
o.sc = [P.scripts({name: 'Ace', lane: 'no_site', site: 'f/abcdefgh/'}, 'Ann', c), P.scripts({name: 'Ace', lane: 'site_down'}, 'Ann', c), P.scripts({name: 'Ace', lane: 'redesign'}, 'Ann', c)];
const s2 = P.emptyState(), day = '2026-11-24T';
P.logOutcome(s2, {id: 'a'}, 'voicemail', T(day + '14:00:00Z')); P.logOutcome(s2, {id: 'b'}, 'called', T(day + '14:10:00Z')); P.logOutcome(s2, {id: 'c'}, 'interested', T(day + '14:20:00Z'));
P.logOutcome(s2, {id: 'd'}, 'booked', T(day + '14:30:00Z')); P.logOutcome(s2, {id: 'e'}, 'no', T(day + '14:40:00Z')); P.logOutcome(s2, {id: 'c'}, 'emailed', T(day + '14:21:00Z'));
P.logOutcome(s2, {id: 'f'}, 'interested', T('2026-11-23T15:00:00Z'));   // yesterday: not in today's tally
o.tally = P.dayTally(s2, T(day + '20:00:00Z'), c, {name: 'Starter site', setup: 1500, monthly: 79});
console.log(JSON.stringify(o));
"""


def node3():
    if not shutil.which("node"):
        return
    tmp = tempfile.mkdtemp(prefix="portal-node3-")
    try:
        f = os.path.join(tmp, "t.mjs")
        open(f, "w").write(NODE3 % os.path.join(D, "portalcore.js").replace("\\", "/"))
        r = subprocess.run(["node", f], capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("b. node3 runs", False, r.stderr[-300:])
            return
        o = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("b. follow-ups come back on workdays: Mon + 2 = Wed; the Wed before Thanksgiving + 2 = Tue Dec 1 (Thanksgiving, the day after, the weekend skipped); Fri + 1 = Mon",
          o["wd"] == ["2026-11-25", "2026-12-01", "2026-11-23"], o["wd"])
    check("b. the best hours per kind of business (restaurants 2-4 pm, trades 7-9 am + 4-6 pm, retail 10-12), clipped to the portal's calling hours (9-5 by default)",
          o["best"][0] == [[960, 1020]] and o["best"][1] == [[840, 960]] and o["best"][2] == [[600, 720]] and o["best"][3] == [[420, 540], [960, 1080]]
          and o["inBest"] == [True, False], o["best"])
    check("b. Today: follow-ups due today first, then the ones in their best hour now, then the rest; at most 60",
          [x[0] for x in o["today"]] == ["x4", "x2", "x3", "x1"] and o["today"][0][1] and o["today"][1][2] and o["n60"] == 60, o["today"])
    check("b. the Do Not Call field: 'unknown' by default, the PC's scrub can say 'clear', 'listed' = never call; junk states are dropped",
          o["dnc"] == ["unknown", "clear"] and o["dncS"]["tone"] == "done" and "Do Not Call" in o["dncS"]["why"] and o["dncLoad"] == {"a": "listed"}, (o["dnc"], o["dncS"], o["dncLoad"]))
    vm = [x["voicemail"] for x in o["sc"]]
    tx = [x["text"] for x in o["sc"]]
    check("b. a voicemail per lane (the caller says it: the name, the agency, the business, the agency number) and one text line per lane with 'Reply STOP'",
          all("Ann with Peak Web here, for Ace" in v and "(301) 555-0142" in v for v in vm) and "free website draft" in vm[0] and "didn't load" in vm[1] and "free 2-minute check" in vm[2]
          and all(t.endswith("Reply STOP to opt out.") for t in tx) and "https://sites.example.com/f/abcdefgh/" in tx[0] and "we built" not in tx[2], (vm, tx))
    t = o["tally"]
    check("b. the end-of-day tally: dials 5, connects 4 (talked / interested / booked / no), 1 show booked, pipeline 2 x the Starter setup = $3,000 + $158/mo; yesterday left out",
          t["dials"] == 5 and t["connects"] == 4 and t["booked"] == 1 and t["pipelineN"] == 2 and t["pipeline"] == 3000 and t["monthly"] == 158
          and t["text"] == "Today: 5 dials, 4 connects, 1 booked, 2 in the pipeline ($3,000 + $158/mo at Starter site prices).", t)


NODE4 = r"""
import * as P from '%s';
import { readFileSync } from 'fs';
const price = JSON.parse(readFileSync('%s', 'utf8')), o = {}, T = (x) => Date.parse(x);
const c = {tz: 'America/New_York', hours: [540, 1020], agency: 'Peak Web', agency_email: 'peak@gmail.example', postal: 'PO Box 12, Frederick MD 21701', agency_number: '(301) 555-0142', public_base: 'https://sites.example.com'};
const L = {id: 'a', name: 'Ace Roofing', phone: '3015550100', site: 'f/abcdefgh/', lane: 'no_site'};
const st = P.emptyState(); st.caller = 'Ann';
P.logOutcome(st, L, 'interested', T('2026-11-23T15:00:00Z')); P.logOutcome(st, L, 'proposal', T('2026-11-23T15:05:00Z'));
const at = (d) => P.statusOf(L, st, T(d + 'T15:00:00Z'), c);
o.s = [at('2026-11-24'), at('2026-11-25')];
P.logOutcome(st, L, 'voicemail', T('2026-11-25T15:00:00Z')); o.s.push(at('2026-11-26'), at('2026-12-02'));
o.today = P.todayList([L], st, T('2026-12-02T15:00:00Z'), c, 60).length;
P.logOutcome(st, L, 'fu_email', T('2026-12-02T16:00:00Z')); o.s.push(at('2026-12-03'));
const s2 = P.emptyState(); P.logOutcome(s2, L, 'proposal', T('2026-11-23T15:05:00Z')); P.logOutcome(s2, L, 'booked', T('2026-11-24T15:00:00Z'));
o.answered = P.statusOf(L, s2, T('2026-11-25T15:00:00Z'), c);
o.prop = P.proposalFor(L, 'Ann', c, price, T('2026-11-23T15:00:00Z'));
o.red = P.proposalFor({id: 'r', name: 'Old Site Dental', lane: 'redesign', url: 'http://old.example'}, 'Ann', c, price, T('2026-11-23T15:00:00Z')).email;
o.fu = P.proposalFollowUp(L, 'Ann', c);
o.load = P.loadState(JSON.stringify({log: [{t: 1, id: 'a', k: 'proposal'}, {t: 2, id: 'a', k: 'fu_email'}, {t: 3, id: 'a', k: 'hack'}]})).log.length;
console.log(JSON.stringify(o));
"""


def node4():
    if not shutil.which("node"):
        return
    tmp = tempfile.mkdtemp(prefix="portal-node4-")
    try:
        f = os.path.join(tmp, "t.mjs")
        open(f, "w").write(NODE4 % (os.path.join(D, "portalcore.js").replace("\\", "/"), os.path.join(D, "price.json").replace("\\", "/")))
        r = subprocess.run(["node", f], capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("b. node4 runs", False, r.stderr[-300:])
            return
        o = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    w = [x["why"] for x in o["s"]]
    check("b. proposal follow-ups: a call on workday 2, an email on workday 5 (Thanksgiving + the day after skipped), then stop; a due email is on Today",
          w[0] == "Proposal sent: follow-up call tomorrow" and o["s"][1]["ok"] and w[1] == "Proposal: follow-up call due" and "email on Wed Dec 2" in w[2]
          and o["s"][3]["mail"] and "send the follow-up email" in w[3] and o["today"] == 1 and o["s"][4]["tone"] == "done" and "stop here" in w[4], w)
    check("b. a business that answers (booked / interested after the proposal) leaves the sequence", "they answered" in o["answered"]["why"] and not o["answered"]["ok"], o["answered"])
    e = o["prop"]["email"]
    pb = json.load(open(os.path.join(ROOT, "agency", "pricebook.json"), encoding="utf-8"))
    st = next(x for x in pb["packages"] if x["id"] == "starter")
    check("b. the proposal: their concept link, the price book's package + monthly + no-upfront option + 3% Maryland tax line, the 7-day timeline, "
          "what we need, the $750 deposit step, valid 14 days; sender, postal address, 'no thanks'; no sms",
          "https://sites.example.com/f/abcdefgh/" in e and f"${st['setup']:,} once + ${st['monthly']}/month" in e and "$149/month for 12 months" in e
          and "Maryland sales tax (3%)" in e and "LIVE IN 7 DAYS" in e and "WHAT WE NEED FROM YOU" in e and "A $750 deposit (50%)" in e
          and "Prices hold until 2026-12-07" in e and "Ann, Peak Web" in e and "PO Box 12" in e and "no thanks" in e and "sms" not in e.lower(), e[:300])
    check("b. a redesign proposal rebuilds their current site (never 'the draft we built')", "We rebuild your current site (http://old.example)" in o["red"] and "draft we already built" not in o["red"])
    check("b. the follow-up email: short, the last note, 'no thanks'", o["fu"]["subject"].startswith("Re: Your website proposal") and "this is my last note" in o["fu"]["email"] and "no thanks" in o["fu"]["email"])
    check("b. 'proposal' and 'fu_email' are saved log lines (junk still dropped)", o["load"] == 2, o["load"])


def closekit_static():
    from agency import proposal as PR, pricebook as PB
    check("a. close kit: price.json = the price book (python -m agency.proposal), and the price book's own check passes (agreement included)",
          not PR.problems() and not PB.check(), (PR.problems(), PB.check()[:3]))
    ag = open(os.path.join(ROOT, "docs", "agency", "AGREEMENT.md"), encoding="utf-8").read()
    check("a. docs/agency/AGREEMENT.md: plain English, 'have a lawyer and an accountant glance at it', scope, price, deposit, the care plan term + 30 days' notice, "
          "your domain + content, 3% Maryland sales tax line, no promised results",
          "Have a lawyer and an accountant glance at it" in ag and "$750 deposit" in ag and "3%" in ag and "in your name" in ag and "We do not promise" in ag
          and "cancel any time with 30 days' notice" in ag and "NOT LEGAL ADVICE" in ag)
    h, j = (open(os.path.join(D, f), encoding="utf-8").read() for f in ("proposal.html", "proposal.js"))
    check("a. the printable proposal page: noindex, no referrer, own folder only, no sms: link, text only through textContent",
          'content="noindex, nofollow"' in h and "no-referrer" in h and "sms:" not in h + j and "innerHTML" not in j and "http" not in re.sub(r"<!--.*?-->", "", h, flags=re.S))
    from tools import site_factory as F
    check("a. the neutral-host export carries the proposal files", {"price.json", "proposal.html", "proposal.js", "proposal.css"} <= set(F.PORTAL_FILES))


NODE2 = r"""
import * as P from '%s';
const o = {}, c = {agency: 'Peak Web', agency_email: 'peak@gmail.example', postal: 'PO Box 12, Frederick MD 21701', public_base: 'https://sites.example.com', prices: {starter: '$1,500'}};
const R = {id: 'r', name: 'Old Site Dental', lane: 'redesign', url: 'http://old.example', score: 8, why: ['not secure (http)', 'not mobile-friendly']};
o.tabs = [P.tabOf(R, {tone: 'go'}), P.tabOf(R, {tone: 'done'}), P.tabOf({lane: 'site_down'}, {tone: 'go'}), P.tabOf({}, {tone: 'need'})];
o.open = [P.opener(R), P.opener({name: 'Down Deli', lane: 'site_down'}), P.opener({name: 'No Site Co'})];
o.their = [P.theirSite(R), P.theirSite({lane: 'redesign', url: 'javascript:alert(1)'}), P.theirSite({lane: 'no_site', url: 'https://x.example'})];
o.mail = P.emailFor(R, 'Ann', c); o.lanes = P.LANES;
console.log(JSON.stringify(o));
"""


def node2():
    if not shutil.which("node"):
        return
    tmp = tempfile.mkdtemp(prefix="portal-node2-")
    try:
        f = os.path.join(tmp, "t.mjs")
        open(f, "w").write(NODE2 % os.path.join(D, "portalcore.js").replace("\\", "/"))
        r = subprocess.run(["node", f], capture_output=True, text=True, timeout=60)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("b. the Redesign tab holds the businesses with a site (until done); site_down and no_site rows stay in the status tabs", o.get("tabs") == ["redesign", "done", "go", "need"], o.get("tabs"))
    check("b. the opener per lane: redesign offers a free check (never 'we built you'), site_down says it did not load, no_site the built site",
          o["open"][0].startswith("I looked at your website") and "we built" not in o["open"][0] and "didn't load" in o["open"][1] and o["open"][2].startswith("I noticed No Site Co doesn't have a website"), o.get("open"))
    check("b. 'their current site' only for a redesign row with an http(s) address", o["their"] == ["http://old.example", "", ""], o.get("their"))
    m = o["mail"]
    check("b. the redesign email: honest subject, their address, the check's reasons, sender + postal address + 'no thanks'; no concept-site link",
          m["ready"] and m["subject"] == "A free check of the Old Site Dental website" and "http://old.example" in m["body"] and "- not mobile-friendly" in m["body"]
          and "PO Box 12" in m["body"] and "no thanks" in m["body"] and "sites.example.com" not in m["body"], m)


def twenty():
    """a caller works 20 calls on a 390 x 844 phone: never a sideways scroll, the Redesign tab sorted by the most dated site, 25 rows at a time"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import browser_kit as BK
    from tests import agora_kit as AK
    from agency import portal as PT
    salt = "0123456789abcdef"
    conf = dict(PT.DEFAULT_CONF, agency="Peak Web", agency_email="peak@gmail.example", postal="PO Box 12, Frederick MD 21701", public_base="https://sites.example.com")
    conf["pass"] = {"salt": salt, "sha256": PT.pass_hash("blue river candle", salt)}
    long = "Frederick County Very Long Business Name Plumbing Heating And Cooling Services"
    leads = [{"id": f"g{i}", "name": (long if i % 7 == 0 else f"Business {i}"), "phone": f"301555{1000 + i}", "town": "Frederick", "niche": "trades", "kind": "Plumber",
              "code": f"FR-{i}", "site": "f/abcdefg%d/" % (2 + i % 8), "lane": "site_down" if i % 5 == 0 else "no_site"} for i in range(40)]
    leads += [{"id": f"r{i}", "name": f"Has Site {i}", "phone": f"240555{1000 + i}", "town": "Frederick", "niche": "health", "lane": "redesign",
               "url": f"https://site{i}.example", "score": sc, "why": ["not mobile-friendly"] if sc else []} for i, sc in enumerate((2, 9, 5))]
    srv, origin = AK.serve({"/agency/portal/portal.json": json.dumps(conf), "/agency/portal/calllist.json": json.dumps({"v": 1, "leads": leads})})
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce", service_workers="block", timezone_id="America/New_York")
            ctx.route(re.compile(r"^(?!https?://127\.0\.0\.1)"), lambda r: r.abort())
            p = ctx.new_page()
            p.clock.install(time=1795446000)          # Mon 2026-11-23 10:00 ET
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)[:120]))
            p.add_init_script("window.open = () => null;")
            p.goto(f"{origin}/agency/portal/", wait_until="load")
            p.fill("#who", "Ann")
            p.fill("#phrase", "blue river candle")
            p.click("#lockForm button")
            p.wait_for_selector("#list li.lead")
            first = p.evaluate("() => ({ rows: document.querySelectorAll('#list li.lead').length, more: !document.getElementById('moreRows').hidden,"
                               " lane: document.querySelector('#list li.lead .lane').textContent, opener: document.querySelector('#list li.lead .opener').textContent })")
            check("d. 390 px: 25 rows at a time (Show 25 more), each with its lane and the line to say", first["rows"] == 25 and first["more"] and first["lane"].split(" ·")[0] in ("No website", "Site down", "Has a site")
                  and first["opener"].startswith(("I noticed", "I tried your website", "I looked at your website")), first)
            wide, done = [], 0
            for k in range(20):
                li = p.locator("#list li.lead.go").first
                li.locator(".call").click()
                li.locator(".outcomes button", has_text=("Voicemail" if k % 2 else "Talked")).click()
                p.wait_for_timeout(60)
                wide.append(p.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth"))
                done += 1
            log = p.evaluate("JSON.parse(localStorage.getItem('agency.portal.v1')).log.length")
            check("d. a caller works 20 calls in a row (Call, then what happened) on 390 x 844 with never a sideways scroll; all 20 logged", done == 20 and log == 20 and max(wide) <= 1 and not errs, (wide, log, errs))
            eod = p.evaluate("() => [document.getElementById('eDials').textContent, document.getElementById('eConn').textContent, document.getElementById('eText').textContent,"
                             " document.querySelector(\".tabs button[aria-pressed='true']\").dataset.f]")
            check("d. the end-of-day card after the 20 calls: 20 dials, 10 connects (the Talked ones), the tally line; Today stayed the open tab",
                  eod[0] == "20" and eod[1] == "10" and eod[2].startswith("Today: 20 dials, 10 connects") and eod[3] == "today", eod)
            li = p.locator("#list li.lead").first
            name = li.locator(".name").text_content()
            li.locator("details.scripts summary").click()
            vm = li.locator(".vm").text_content()
            li.locator(".dncSel").select_option("listed")
            p.wait_for_timeout(200)
            gone = p.evaluate("(n) => ![...document.querySelectorAll('#list li.lead .name')].some((e) => e.textContent === n)", name)
            check("d. a row's scripts drawer shows the voicemail with the caller's name; 'On the list' in the Do Not Call field takes the business off Today at once",
                  vm.startswith("Ann with Peak Web here, for ") and gone, (vm, gone))
            # close the sale: Interested -> the proposal panel -> the printable one-page proposal
            li = p.locator("#list li.lead.go").first
            pname = li.locator(".name").text_content()
            li.locator(".call").click()
            li.locator(".outcomes button", has_text="Interested").click()
            p.click(".tabs button[data-f='wait']")
            row = p.locator("#list li.lead", has=p.locator(".name", has_text=pname)).first
            row.locator(".proposal:not([hidden]) .openProp").wait_for(timeout=8000)
            row.locator(".openProp").click()
            pp = ctx.new_page()
            pp.goto(f"{origin}/agency/portal/proposal.html", wait_until="load")
            pp.wait_for_selector("#secs section")
            doc = pp.evaluate("() => ({ h1: document.getElementById('biz').textContent, secs: [...document.querySelectorAll('#secs h2')].map((h) => h.textContent),"
                              " txt: document.getElementById('secs').innerText, wide: document.documentElement.scrollWidth - innerWidth })")
            logged = p.evaluate("(n) => JSON.parse(localStorage.getItem('agency.portal.v1')).log.filter((e) => e.k === 'proposal' && e.name === n).length", pname)
            check("d. Interested -> 'Open the proposal': the one-page proposal for that business (5 parts: what, price, 7 days, what we need, to start), "
                  "the $750 deposit, no sideways scroll; the proposal is logged once",
                  doc["h1"] == pname and doc["secs"][0] == "What you get" and len(doc["secs"]) == 5 and "$750 deposit" in doc["txt"] and doc["wide"] <= 1 and logged == 1, (doc, logged))
            pp.close()
            p.click(".tabs button[data-f='redesign']")
            p.wait_for_selector("#list li.lead")
            rd = p.evaluate("() => [...document.querySelectorAll('#list li.lead')].map((li) => [li.querySelector('.name').textContent, li.querySelector('.lane').textContent,"
                            " (li.querySelector('.site') || {}).textContent || '', li.querySelector('.opener').textContent.slice(0, 22)])")
            check("d. the Redesign tab: the businesses with a site, the most dated first (9, 5, 2), 'Their current site', the free-check opener",
                  [r[0] for r in rd] == ["Has Site 1", "Has Site 2", "Has Site 0"] and rd[0][1] == "Has a site · 9/11" and rd[0][2] == "Their current site" and rd[0][3] == "I looked at your websi", rd)
            check("d. the Redesign tab: no sideways scroll either", p.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 1)
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP browser: no Python playwright")
        return
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import browser_kit as BK
    from tests import agora_kit as AK
    from agency import portal as PT
    salt = "0123456789abcdef"
    conf = dict(PT.DEFAULT_CONF, agency="Peak Web", agency_email="peak@gmail.example", postal="PO Box 12, Frederick MD 21701", public_base="https://sites.example.com",
                pass_={}, tz="America/New_York")
    conf.pop("pass_")
    conf["pass"] = {"salt": salt, "sha256": PT.pass_hash("blue river candle", salt)}
    lst = {"v": 1, "leads": [{"id": "a", "name": "Ace Roofing", "phone": "3015550100", "town": "Frederick", "state": "MD", "niche": "trades", "kind": "Roofer", "code": "FR-1", "site": "f/aaaaaaaa/"},
                             {"id": "d", "name": "Rosa Pizza", "phone": "", "town": "Frederick", "state": "MD", "niche": "food", "kind": "Restaurant", "code": "FR-4", "site": "f/dddddddd/"}]}
    srv, origin = AK.serve({"/agency/portal/portal.json": json.dumps(conf), "/agency/portal/calllist.json": json.dumps(lst)})
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            for w, hgt in ((390, 844), (320, 568)):
                ctx = br.new_context(viewport={"width": w, "height": hgt}, is_mobile=True, has_touch=True, reduced_motion="reduce", service_workers="block",
                                     timezone_id="America/New_York")
                ctx.route(re.compile(r"^(?!https?://127\.0\.0\.1)"), lambda r: r.abort())
                p = ctx.new_page()
                p.clock.install(time=1795446000)           # Mon 2026-11-23 10:00 ET (seconds): the window is open
                errs, opened = [], []
                p.on("pageerror", lambda e: errs.append(str(e)))
                p.add_init_script("window.open = (u) => { window.__opened = u; return null; };")
                p.goto(f"{origin}/agency/portal/", wait_until="load")
                check(f"d. {w}px: locked first (the list hidden)", p.is_visible("#lock") and p.is_hidden("#main"))
                p.fill("#who", "Ann")
                p.fill("#phrase", "wrong phrase here")
                p.click("#lockForm button")
                p.wait_for_function("document.getElementById('lockMsg').textContent.length > 0")
                check(f"d. {w}px: a wrong passphrase stays locked", p.is_hidden("#main") and "not right" in p.text_content("#lockMsg"))
                p.fill("#phrase", "blue river candle")
                p.click("#lockForm button")
                p.wait_for_selector("#list li.lead", timeout=10000)
                check(f"d. {w}px: the right passphrase opens it; the identify line names the caller and the agency",
                      "Hi, it's Ann with Peak Web" in p.text_content("#identify") and not errs, errs)
                call = p.get_attribute("li[data-id='a'] .call", "href")
                check(f"d. {w}px: tap-to-call (tel:) + their own site link", call == "tel:+13015550100" and p.get_attribute("li[data-id='a'] .site", "href") == "https://sites.example.com/f/aaaaaaaa/", call)
                stray = p.evaluate("[...document.querySelectorAll('li.lead .phoneForm, li.lead .mailForm')].filter(e => e.getClientRects().length).length")
                check(f"d. {w}px: before any call no row shows the email box, and a row with a number shows no 'number you found' box", stray == 0, stray)
                wide = p.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth")
                check(f"d. {w}px: no sideways scroll", wide <= 1, wide)
                small = p.evaluate("""() => [...document.querySelectorAll('#main button, #main a.btn, #main input, #main select, #main summary')].filter(e => e.getClientRects().length)
                  .map(e => [e.textContent.trim().slice(0, 20) || e.id, Math.round(e.getBoundingClientRect().height)]).filter(x => x[1] < 43.5)""")
                check(f"d. {w}px: every control is at least 44 px tall", not small, small[:5])
                if w != 390:
                    ctx.close()
                    continue
                p.click("li[data-id='a'] .outcomes button:has-text('Voicemail')")
                p.wait_for_function("!document.querySelector(\"#list li[data-id='a']\")")
                p.click(".tabs button[data-f='wait']")
                p.wait_for_selector("li[data-id='a']")
                check("d. logging a call moves it to Later: never twice in a day (no tel: link now)",
                      "Called today" in p.text_content("li[data-id='a'] .why") and p.get_attribute("li[data-id='a'] .call", "href") is None
                      and p.get_attribute("li[data-id='a'] .call", "aria-disabled") == "true")
                p.click("li[data-id='a'] button:has-text('Undo')")
                p.click(".tabs button[data-f='go']")
                p.wait_for_selector("li[data-id='a']")
                p.click("li[data-id='a'] .outcomes button:has-text('Interested')")
                p.click(".tabs button[data-f='wait']")
                p.wait_for_selector("li[data-id='a'] .mailForm:not([hidden])")
                p.fill("li[data-id='a'] .theirEmail", "boss@ace.example")
                p.click("li[data-id='a'] .mailForm button")
                u = p.evaluate("window.__opened || ''")
                check("d. undo works; after 'Interested', Email them the link opens the agency Gmail with their site link (the page sends nothing)",
                      u.startswith("https://mail.google.com/mail/?view=cm&fs=1&authuser=peak%40gmail.example&to=boss%40ace.example")
                      and "sites.example.com%2Ff%2Faaaaaaaa%2F" in u, u[:160])
                p.click(".tabs button[data-f='need']")
                p.wait_for_selector("li[data-id='d'] .phoneForm:not([hidden])")
                check("d. no number: a Google Maps search link + a box for the number found", "google.com/maps/search" in (p.get_attribute("li[data-id='d'] .maps", "href") or ""))
                p.fill("li[data-id='d'] .foundPhone", "240-555-0123")
                p.click("li[data-id='d'] .phoneForm button")
                p.click(".tabs button[data-f='go']")
                p.wait_for_selector("li[data-id='d'] .call[href='tel:+12405550123']")
                p.fill("#aName", "Dee Plumbing")
                p.fill("#aPhone", "301 555 0199")
                p.fill("#aTown", "Frederick")
                p.click("#addForm button")
                p.wait_for_selector("li .name:has-text('Dee Plumbing')")
                saved = p.evaluate("JSON.parse(localStorage.getItem('agency.portal.v1'))")
                check("d. a found number and an added business are saved on this phone with the caller's name; the log has the caller",
                      saved["phones"].get("d") == "2405550123" and saved["added"][0]["by"] == "Ann" and all(e["caller"] == "Ann" for e in saved["log"]), saved)
                with p.expect_download() as dl:
                    p.click("#saveLog")
                f = dl.value
                doc = json.loads(open(f.path(), encoding="utf-8").read())
                check("d. 'Save my log file' gives the export the PC imports", doc["app"] == "agency-portal" and doc["caller"] == "Ann" and f.suggested_filename.startswith("portal-log-Ann-"))
                p.reload()
                p.wait_for_selector("#list li.lead", timeout=10000)
                check("d. stays signed in on this phone after a reload; Sign out locks it", p.is_hidden("#lock"))
                p.click("#signout")
                p.wait_for_selector("#lock:not([hidden])")
                check("d. no page error", not errs, errs)
                ctx.close()
            br.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    static()
    node()
    pcside()
    sitecheck()
    dialing_static()
    lanes()
    node2()
    node3()
    node4()
    closekit_static()
    if "--static" not in sys.argv:
        browser()
        twenty()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed" + ("" if not FAILS else f"; FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)
