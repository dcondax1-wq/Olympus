"""Website Factory (tools/site_factory.py -> agency/f/<id>/ + agency/factory/): honest, hidden, small, phone-first.

    python tests/test_site_factory.py           static checks (fast)
    python tests/test_site_factory.py --browser  + 5 random sites and the gallery in a phone browser (run under the browser lock)
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_factory as F  # noqa: E402

AG = os.path.join(ROOT, "tools", "web_public", "agency")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  [OK]  " if ok else "  [FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def main() -> int:
    leads = F.load_leads()
    # a. the build is reproducible: --check builds into a temp folder and matches what is committed
    with tempfile.TemporaryDirectory() as t:
        ip = os.path.join(t, "ids.json")
        with open(ip, "w") as f:
            f.write(read(F.IDS))
        sites_tmp = F.build(os.path.join(t, "agency"), ip, write_ids=True)
        ids_after = json.load(open(ip))
        same = all(read(os.path.join(t, "agency", s["path"], "index.html")) == read(os.path.join(AG, s["path"], "index.html")) for s in sites_tmp)
    ids = json.load(open(F.IDS))
    check("a. every lead with no website has a site (%d leads)" % len(leads), len(sites_tmp) == len(leads) and all(L["id"] in ids for L in leads))
    check("a. committed sites = a fresh build (run python tools/site_factory.py after the leads change)", same)
    check("a. links never change: a rebuild keeps every lead's folder", ids_after == ids)
    check("a. folder ids are 8 random characters, all different", all(re.fullmatch(r"[a-z2-9]{8}", v) for v in ids.values()) and len(set(ids.values())) == len(ids))

    S = json.load(open(os.path.join(AG, "factory", "sites.json")))["sites"]
    check("b. gallery list = the sites on disk", sorted(s["path"] for s in S) == sorted("f/%s/" % d for d in os.listdir(os.path.join(AG, "f")) if os.path.isdir(os.path.join(AG, "f", d))))
    bad = {"noindex": [], "words": [], "size": [], "viewport": [], "footer": [], "ext": [], "tel": [], "facts": []}
    byid = {L["id"]: L for L in leads}
    for s in S:
        h = read(os.path.join(AG, s["path"], "index.html"))
        L = byid[s["id"]]
        if '<meta name="robots" content="noindex' not in h or 'name="referrer" content="no-referrer"' not in h:
            bad["noindex"].append(s["name"])
        vis = re.sub(r"<style>.*?</style>|<script>.*?</script>", " ", h, flags=re.S).replace(F.esc(L["name"]), " ")
        for w in F.BANNED:
            if re.search(r"(?<![a-z])" + re.escape(w), vis, re.I):
                bad["words"].append((s["name"], w))
        if len(h.encode()) > F.BUDGET:
            bad["size"].append((s["name"], len(h)))
        if 'name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"' not in h:
            bad["viewport"].append(s["name"])
        if f"Concept made for {F.esc(L['name'].strip())} - not live, not affiliated" not in h or "OpenStreetMap contributors" not in h:
            bad["footer"].append(s["name"])
        # nothing loaded from anywhere else: no photos, fonts, scripts or trackers (links out are fine)
        if re.search(r"<(?:img|script|link|iframe)[^>]+(?:src|href)=\"https?://", h) or re.search(r"url\(\s*['\"]?https?://|@import", h):
            bad["ext"].append(s["name"])
        t = F.tel(L.get("phone"))
        if t and f'href="tel:{t}"' not in h:
            bad["tel"].append(s["name"])
        if L.get("phone") and t and L["phone"].strip() not in h:
            bad["facts"].append((s["name"], "phone"))
        if L.get("town") and F.esc(L["town"]) not in h:
            bad["facts"].append((s["name"], "town"))
        if re.search(r"\$\s?\d", re.sub(r'<section class="agency".*?</section>', " ", vis, flags=re.S)):   # the agency offer is ours, not the business's
            bad["facts"].append((s["name"], "a price"))
    check("c. every site: noindex + no referrer", not bad["noindex"], bad["noindex"])
    check("c. no review / testimonial / award / licence / price words", not bad["words"], bad["words"])
    check("c. every site under 100 KB (largest %.1f KB)" % (max(s["bytes"] for s in S) / 1024), not bad["size"], bad["size"])
    check("c. phone viewport on every site", not bad["viewport"], bad["viewport"])
    check("c. footer: 'Concept made for <business> - not live, not affiliated' + OpenStreetMap credit", not bad["footer"], bad["footer"])
    check("c. nothing loaded from other sites (no copied photos, fonts, trackers)", not bad["ext"], bad["ext"])
    check("c. click-to-call on every site with a phone; the real phone + town shown, no $ amounts", not bad["tel"] and not bad["facts"], bad["tel"] + bad["facts"])

    g = read(os.path.join(AG, "factory", "index.html"))
    check("d. gallery: noindex, phone viewport, copy-link + preview", '<meta name="robots" content="noindex' in g and "viewport-fit=cover" in g
          and "Copy link" in g and "iframe" in g and "sandbox" in g)
    check("d. agency/f/ itself lists nothing (no folder index)", "Not found" in read(os.path.join(AG, "f", "index.html")))
    # d2. the agency band (lead 2026-11-20): Maryland bans cold AI calls -> the assistant only calls a business that asks; consent form
    #     slot (day-caller fills it), 'Call us' (agency number placeholder); no third-party form service, no secret in the page
    band = {"band": [], "form3p": [], "secret": []}
    for s in S:
        h = read(os.path.join(AG, s["path"], "index.html"))
        if 'data-agency="1"' not in h or "our AI assistant answers" not in h or "any time" in h or "sms:" in h or "text us" in h.lower() or "callme" in h or "CALLER-FORM" in h:
            band["band"].append(s["name"])
        if re.search(r"formspree|getform|formsubmit|basin|netlify-form|typeform|jotform|google\.com/forms|hsforms|wufoo", h, re.I):
            band["form3p"].append(s["name"])
        if re.search(r"(?:api[_-]?key|secret|token|bearer)\s*[:=]", h, re.I) or re.search(r"\.ts\.net|\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", h):
            band["secret"].append(s["name"])
    check("d2. every site: 'Like this site?' band = 'Call <agency number>: our AI assistant answers' (voice only, no 'any time') (no consent form: lead 2026-11-20)", not band["band"], band["band"])
    check("d2. no third-party form service, no secret, no ts.net / PC address in any page", not band["form3p"] and not band["secret"], band)
    # day-caller's form (tools/caller/siteform.py): its two hidden fields get THIS site's lead id + business name; a form without them is refused
    demo = ('<form class="callme"><input type="hidden" name="lead_id" value=""><input type="hidden" name="business" value="">'
            '<button type="submit">Have our assistant call me</button></form>')
    out = F.caller_form(demo, "osm-n1", 'Joe\'s "Diner"')
    try:
        F.caller_form("<form></form>", "x", "y")
        refused = False
    except ValueError:
        refused = True
    check("d2. caller form: per-site lead_id + business filled (escaped), a form without the fields refused",
          'name="lead_id" value="osm-n1"' in out and 'value="Joe&#x27;s &quot;Diner&quot;"' in out and refused, out)
    codes = json.load(open(F.CODES))
    cb = []
    for s in S:
        h = read(os.path.join(AG, s["path"], "index.html"))
        c = codes.get(s["id"], "")
        if not re.fullmatch(r"[A-Z]{2}-\d+", c) or f"Your code: {c}" not in h or s.get("code") != c:
            cb.append((s["name"], "code"))
        if F.OFFER not in h or not (('data-claim="1"' in h) if F.agency_cfg()["pay_url"] else "Claim this site: call us" in h):
            cb.append((s["name"], "claim"))
    check("d2. every site: the offer + 'Claim this site' (payment link once set, else call us / assistant) + 'Your code: FR-n'", not cb, cb)
    check("d2. codes are unique and stable (a rebuild keeps them)", len(set(codes.values())) == len(codes) and all(L["id"] in codes for L in leads))
    ix = json.load(open(os.path.join(AG, "sites", "index.json")))
    check("d2. agency/sites/index.json: every lead id -> its f/<id>/ path (relative to agency/)",
          ix.get("sites") == {L["id"]: "f/%s/" % ids[L["id"]] for L in leads} and all(os.path.isfile(os.path.join(AG, p, "index.html")) for p in ix["sites"].values()))
    # e. hidden: nothing outside the factory links to it (Home, apps lists, sitemaps, service worker)
    hits = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "tools", "web_public")):
        rel = os.path.relpath(base, AG)
        if rel == "f" or rel.startswith("f" + os.sep) or rel in ("factory", "sites"):
            continue
        for fn in files:
            if fn.endswith((".html", ".js", ".json", ".xml", ".txt", ".webmanifest")):
                try:
                    txt = read(os.path.join(base, fn))
                except (UnicodeDecodeError, OSError):
                    continue
                if re.search(r"agency/f/[a-z2-9]{8}|agency/factory", txt) or any(v in txt for v in list(ids.values())[:20]):
                    hits.append(os.path.relpath(os.path.join(base, fn), ROOT))
    check("e. no page, apps list, sitemap or sw.js links to the factory or a site", not hits, hits)
    # h. the neutral-host export (lead 2026-11-21): refuses without public_base (or with an Olympus / github.io one), else a standalone site
    def exp(cfg):
        with tempfile.TemporaryDirectory() as t:
            ag, out = os.path.join(t, "ag.json"), os.path.join(t, "out")
            if cfg is not None:
                with open(ag, "w") as f:
                    json.dump(cfg, f)
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "site_factory.py"), "--export", out], capture_output=True, text=True,
                               timeout=120, env={**os.environ, "SITE_FACTORY_AGENCY": ag})
            files = {}
            for b, _d, fs in os.walk(out):
                for fn in fs:
                    files[os.path.relpath(os.path.join(b, fn), out).replace(os.sep, "/")] = read(os.path.join(b, fn))
            return r.returncode, files, r.stderr
    rc0, f0, e0 = exp(None)
    rc1, f1, _ = exp({"public_base": "https://dcondax1-wq.github.io/sites/"})
    rc2, f2, _ = exp({"public_base": "http://plain.example.com/"})
    check("h. export refuses (and writes nothing) without public_base, with a github.io base, or with plain http",
          rc0 == 2 and not f0 and "public_base" in e0 and rc1 == 2 and not f1 and rc2 == 2 and not f2, (rc0, rc1, rc2, e0[:200]))
    rc, fx, err = exp({"public_base": "https://neutral-sites.pages.dev/"})
    sites_x = [k for k in fx if re.fullmatch(r"f/[a-z2-9]{8}/index\.html", k)]
    leak = [(k, m.group(0)) for k, v in fx.items() for m in [re.search("|".join(F.FORBIDDEN), v, re.I)] if m]
    check("h. export: every site + landing, 404, robots (Disallow: / until the agency is named), _headers noindex, nothing pointing at Olympus",
          rc == 0 and len(sites_x) == len(S) and {"index.html", "404.html", "robots.txt", "_headers", "f/index.html"} <= set(fx)
          and fx["robots.txt"].strip().endswith("Disallow: /") and "noindex" in fx["index.html"] and "X-Robots-Tag: noindex" in fx["_headers"]
          and not leak, (rc, len(sites_x), leak[:5], err[-200:]))
    rc, fx, _ = exp({"public_base": "https://neutral-sites.pages.dev/", "agency_name": "Main Street Web"})
    check("h. once the agency is named: the landing is indexable, the concept sites stay blocked (robots Disallow: /f/)",
          rc == 0 and '"index, follow"' in fx["index.html"] and "Main Street Web" in fx["index.html"] and "Disallow: /f/" in fx["robots.txt"]
          and all('content="noindex' in v for k, v in fx.items() if k.startswith("f/") and k.endswith(".html") and k != "f/index.html"))
    # f. the hours reader: simple OSM forms in, unclear ones -> 'call to ask' (never a wrong time)
    ph = F.parse_hours
    check("f. hours: 'Mo-Fr 09:00-17:00; Sa 09:00-14:00; Su off' -> 9 am - 5 pm ... Closed",
          [x for _, x in ph("Mo-Fr 09:00-17:00; Sa 09:00-14:00; Su off")] == ["9 am - 5 pm"] * 5 + ["9 am - 2 pm", "Closed"])
    check("f. hours: wrap-around 'Su-Th', 24/7, midnight, a cut-off string -> None",
          ph("Su-Th 11:30-20:00 || Fr-Sa 11:30-21:00")[6][1] == "11:30 am - 8 pm" and ph("24/7")[0][1] == "Open 24 hours"
          and ph("Mo-Sa 11:00-24:00, Su 11:00-23:00")[0][1] == "11 am - midnight" and ph("Su 11:00-1") is None and ph("") is None)

    if "--browser" in sys.argv:
        random.seed(int(os.environ.get("FACTORY_SEED", "11")))
        pick = random.sample(S, min(5, len(S)))
        js = os.path.join(ROOT, "tests", "site_factory_shots.cjs")
        out = os.path.join(ROOT, "scratch", "factory_shots")
        os.makedirs(out, exist_ok=True)
        r = subprocess.run(["node", js, os.path.join(ROOT, "tools", "web_public"), out] + ["agency/" + s["path"] for s in pick] + ["agency/factory/"],
                           capture_output=True, text=True, timeout=240)
        try:
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            res = []
        check("g. 5 random sites + the gallery open in a phone browser: no error, no sideways scroll, the call button reachable",
              len(res) == 6 and all(x["sw"] <= 390 and not x["errs"] for x in res) and all(x["dock"] or not byid[s["id"]].get("phone") for x, s in zip(res, pick)),
              res or r.stderr[-400:])
    print(f"{sum(RES)} passed, {len(RES) - sum(RES)} failed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
