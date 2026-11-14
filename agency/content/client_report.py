"""Monthly client report (retention): one good-looking page per client per month + the email that goes with it.

    python agency/content/client_report.py client.json --month 2026-11 --leads leads.csv --reviews 47 --reviews-before 41
    python agency/content/client_report.py data/agency/clients.json --id fade-co --month last --leads form.csv --reviews 47 --reviews-before 41 \
        --rating 4.9 --did "Added the holiday hours banner" --plan "New photos for the gallery"
options: --uptime 99.98 (the month's % from a free monitor, e.g. UptimeRobot)  --offline (skip the live site check)
         --posts-json PATH (default: the content machine's posts.json for that month)  --agency-name NAME  --out DIR  --no-pdf

What is on the page:
  - what we did this month (the posts made by make_posts.py for that month + the owner's --did lines)
  - website check: is the site up right now, how fast it answered, is it secure (https) - or the month's % with --uptime
  - website leads: form submissions in the month from the CSV the owner exports (any form tool: the date column is found by name),
    the change vs the month before, a small chart by week
  - Google reviews: the count the owner typed, the change, the rating
  - next month's plan: the content machine's plan for next month (holidays, post count) + the owner's --plan lines
  - one suggestion for what to add next (agency/content/offers.json), chosen from the numbers
Out (default data/agency/reports/<id>/<YYYY-MM>/, gitignored): report.html (print / save as PDF), report.pdf when a browser is
available, email.txt (subject + body ready to paste).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agency.content import designs as D  # noqa: E402
from agency.content import make_posts as M  # noqa: E402
from agency.content import packs as P  # noqa: E402
from agency.content import seasons as S  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATE_NAMES = ["date", "submitted at", "submitted_at", "submission date", "date submitted", "created", "created_at", "created at",
              "timestamp", "time", "_date", "submitted", "received", "sent"]
FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M:%S %p",
           "%m/%d/%Y %I:%M %p", "%m/%d/%Y", "%m/%d/%y %H:%M", "%m/%d/%y", "%b %d, %Y %I:%M %p", "%b %d, %Y", "%B %d, %Y", "%d %b %Y",
           "%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%a, %d %b %Y %H:%M:%S"]


def esc(t) -> str:
    return html.escape(str(t if t is not None else ""), quote=True)


# ------------------------------------------------------------------------------------------------------------------ leads
def parse_when(text: str):
    t = (text or "").strip()
    if not t:
        return None
    t2 = re.sub(r"\s*(UTC|GMT)$", "", t).strip()
    try:
        return dt.datetime.fromisoformat(t2.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for f in FORMATS:
        try:
            return dt.datetime.strptime(t2, f)
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", t2)
    if m:
        return dt.datetime.fromisoformat(m.group(1))
    return None


def _date_column(headers: list[str]) -> str | None:
    norm = {h: re.sub(r"\s+", " ", (h or "").strip().lower().replace("_", " ")) for h in headers}
    for want in DATE_NAMES:
        w = want.replace("_", " ")
        for h, n in norm.items():
            if n == w:
                return h
    for h, n in norm.items():
        if any(k in n for k in ("date", "time", "created", "submit")):
            return h
    return None


def _is_spam(row: dict) -> bool:
    """a 'spam' column that says yes, or a status / label column that says spam (Netlify, Formspree and friends mark them so)"""
    for k, v in row.items():
        if not k:
            continue
        kl, vl = k.strip().lower(), str(v or "").strip().lower()
        if "spam" in kl and vl in ("true", "yes", "y", "1", "spam"):
            return True
        if kl in ("status", "state", "label", "folder", "type") and vl == "spam":
            return True
    return False


def read_leads(path: str | None, year: int, month: int) -> dict:
    """form submissions per month from an exported CSV: {'ok', 'month', 'prev', 'people', 'weeks', 'skipped', 'column'}"""
    res = {"ok": False, "month": 0, "prev": 0, "people": 0, "weeks": [0, 0, 0, 0, 0], "skipped": 0, "spam": 0, "column": "", "rows": 0, "note": ""}
    if not path:
        res["note"] = "no form export given"
        return res
    with open(path, encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    res["rows"] = len(rows)
    if not rows:
        res["ok"], res["note"] = True, "the export is empty"
        return res
    col = _date_column(list(rows[0].keys()))
    if not col:
        res["note"] = "no date column found in the export"
        return res
    res["column"] = col
    py, pm = S.shift_month(year, month, -1)
    people = set()
    seen = set()
    for r in rows:
        if _is_spam(r):
            res["spam"] += 1
            continue
        when = parse_when(r.get(col, ""))
        if when is None:
            res["skipped"] += 1
            continue
        contact = ""
        for k, v in r.items():
            if k and re.search(r"e-?mail", k, re.I) and v and "@" in v:
                contact = v.strip().lower()
                break
        if not contact:
            for k, v in r.items():
                if k and re.search(r"phone|tel|mobile", k, re.I) and v:
                    contact = re.sub(r"\D", "", v)
                    break
        key = (contact, when.date()) if contact else None
        if key and key in seen:                                        # the same person twice on the same day = one lead
            continue
        if key:
            seen.add(key)
        if when.year == year and when.month == month:
            res["month"] += 1
            res["weeks"][min(4, (when.day - 1) // 7)] += 1
            people.add(contact or f"row{res['month']}")
        elif when.year == py and when.month == pm:
            res["prev"] += 1
    res["people"] = len(people)
    res["ok"] = True
    return res


# ---------------------------------------------------------------------------------------------------------------- website
def check_site(url: str, timeout: float = 10.0) -> dict:
    """one live check: up? status, how fast (ms), https? Never sends anything but a plain GET."""
    now = dt.datetime.now().isoformat(timespec="minutes")
    if not url:
        return {"checked": False, "up": None, "reason": "no website on file", "at": now}
    u = url if re.match(r"^https?://", url, re.I) else "https://" + url
    host = urllib.parse.urlparse(u).hostname or ""
    handlers = []
    if host in ("localhost", "127.0.0.1", "::1"):
        handlers.append(urllib.request.ProxyHandler({}))                # a local test server never goes through a proxy
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (compatible; site-check)", "Accept": "text/html"})
    t0 = time.time()
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read(300000)
            status, final = r.status, r.geturl()
        ms = int((time.time() - t0) * 1000)
        m = re.search(rb"<title[^>]*>(.*?)</title>", body, re.I | re.S)
        title = html.unescape(m.group(1).decode("utf-8", "replace").strip())[:80] if m else ""
        return {"checked": True, "up": 200 <= status < 400, "status": status, "ms": ms, "https": final.lower().startswith("https://"),
                "url": final, "title": title, "at": now}
    except urllib.error.HTTPError as e:
        return {"checked": True, "up": False, "status": e.code, "ms": int((time.time() - t0) * 1000), "https": u.startswith("https"),
                "url": u, "reason": f"the site answered with error {e.code}", "at": now}
    except (ssl.SSLError, ssl.CertificateError) as e:
        return {"checked": True, "up": False, "status": None, "ms": None, "https": False, "url": u, "reason": f"HTTPS certificate problem ({str(e)[:60]})", "at": now}
    except Exception as e:  # noqa: BLE001
        reason = getattr(e, "reason", e)
        if isinstance(reason, ssl.SSLError):
            return {"checked": True, "up": False, "status": None, "ms": None, "https": False, "url": u, "reason": "HTTPS certificate problem", "at": now}
        return {"checked": True, "up": False, "status": None, "ms": None, "https": u.startswith("https"), "url": u,
                "reason": f"no answer ({str(reason)[:70]})", "at": now}


# ------------------------------------------------------------------------------------------------------------------ pieces
def load_agency(name: str | None) -> dict:
    ag = {"name": name or "", "email": "", "phone": "", "site": ""}
    path = os.path.join(ROOT, "data", "agency", "agency.json")
    if not name and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            ag.update({k: str(d.get(k) or "") for k in ("name", "email", "phone", "site")})
        except (OSError, ValueError):
            pass
    ag["name"] = ag["name"] or "Your web team"
    return ag


def load_offers() -> list[dict]:
    with open(os.path.join(HERE, "offers.json"), encoding="utf-8") as fh:
        return json.load(fh)["offers"]


def suggest(client: dict, leads: dict, reviews_gain: int | None) -> dict | None:
    """one next step, from the numbers: no social -> social posts; few new reviews -> review booster; many leads -> chat; basic -> pro"""
    pk = str(client.get("package") or "").lower()
    offers = {o["id"]: o for o in load_offers()}
    has = lambda o: any(h in pk for h in o["has"])  # noqa: E731
    n = leads.get("month", 0) if leads.get("ok") else None
    if "social" not in pk and "social_basic" in offers:
        o = dict(offers["social_basic"])
        o["why"] = ("Your website brought in " + (f"{n} leads" if n is not None else "new visitors") +
                    " this month. Posting 3 times a week keeps you in front of local customers between visits.")
        return o
    if "review_booster" in offers and not has(offers["review_booster"]) and (reviews_gain is None or reviews_gain < 4):
        o = dict(offers["review_booster"])
        o["why"] = ("You gained " + (f"{reviews_gain} new Google review{'s' if reviews_gain != 1 else ''}" if reviews_gain is not None else "a few reviews")
                    + " this month. Reviews are the first thing new customers read, and most happy customers will leave one when asked.")
        return o
    if "chat_widget" in offers and not has(offers["chat_widget"]) and (n or 0) >= 8:
        o = dict(offers["chat_widget"])
        o["why"] = f"{n} people reached out through your website this month. Answering in seconds instead of hours wins more of them."
        return o
    if "social_pro" in offers and "basic" in pk:
        o = dict(offers["social_pro"])
        o["why"] = "You are already posting with us. Pro adds more posts, review shout-outs and seasonal offers."
        return o
    return None


def content_summary(plan: dict | None) -> dict:
    if not plan:
        return {"posts": 0, "stories": 0, "holidays": [], "kinds": {}}
    kinds = {}
    for p in plan.get("posts", []):
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    return {"posts": len(plan.get("posts", [])), "stories": len(plan.get("posts", [])), "holidays": plan.get("holidays", []), "kinds": kinds}


def _bars(weeks: list[int], color: str, ink: str) -> str:
    """the leads-by-week chart: inline SVG, labelled, no script"""
    w, h, pad = 300, 104, 22
    mx = max(weeks + [1])
    bw = (w - 20) / len(weeks)
    parts = []
    for i, v in enumerate(weeks):
        bh = 0 if v == 0 else max(4, (h - pad - 16) * v / mx)
        x = 10 + i * bw + bw * 0.18
        y = h - pad - bh
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw * 0.64:.1f}" height="{bh:.1f}" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{x + bw * 0.32:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="12" font-weight="800" fill="{ink}">{v}</text>')
        parts.append(f'<text x="{x + bw * 0.32:.1f}" y="{h - 5}" text-anchor="middle" font-size="11" fill="{ink}" opacity=".65">'
                     f'{["1-7", "8-14", "15-21", "22-28", "29+"][i]}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Leads by week: {", ".join(str(v) for v in weeks)}" '
            f'font-family="Manrope, sans-serif">{"".join(parts)}</svg>')


def _delta(now: int, before: int | None) -> str:
    if before is None:
        return ""
    d = now - before
    if d > 0:
        return f'<span class="up">&#9650; {d} vs last month</span>'
    if d < 0:
        return f'<span class="down">&#9660; {abs(d)} vs last month</span>'
    return '<span class="flat">same as last month</span>'


def _ms(ms) -> str:
    return "-" if ms is None else (f"{ms / 1000:.1f} s" if ms >= 1000 else f"{ms} ms")


# ------------------------------------------------------------------------------------------------------------------ report
CSS = """
:root{--paper:#FFFFFF;--bg:#EEECE7;--ink:#1C2126;--ink2:#4A525A;--ink3:#737B83;--line:#E3E0D9;--brand:%(brand)s;--brandink:%(brandink)s;
--acc:%(acc)s;--accbrand:%(accbrand)s;--soft:%(soft)s;--good:#15803D;--bad:#B42318}
@page{size:Letter;margin:0}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%%}
body{margin:0;background:var(--bg);color:var(--ink);font:500 13px/1.45 "Manrope",system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
.sheet{width:8.5in;min-height:11in;margin:24px auto;background:var(--paper);box-shadow:0 20px 50px -20px rgba(0,0,0,.25);display:flex;flex-direction:column}
.hd{background:var(--brand);color:var(--brandink);padding:.42in .5in .34in;position:relative;overflow:hidden}
.hd .pat{position:absolute;inset:0;background:%(pattern)s;opacity:.45;-webkit-mask:linear-gradient(100deg,transparent 45%%,#000);mask:linear-gradient(100deg,transparent 45%%,#000)}
.hd .in{position:relative;display:flex;justify-content:space-between;align-items:flex-end;gap:20px}
.kick{font:800 10.5px/1 "Manrope";letter-spacing:.22em;text-transform:uppercase;color:var(--accbrand)}
h1{margin:8px 0 0;font:400 34px/1.04 "DM Serif Display",Georgia,serif;letter-spacing:-.01em}
.sub{margin-top:6px;font:600 13px/1.3 "Manrope";opacity:.85}
.mon{text-align:right;flex:none}
.mon b{display:block;font:400 26px/1 "DM Serif Display",Georgia,serif}
.mon span{font:700 11px/1.4 "Manrope";letter-spacing:.06em;opacity:.8}
main{padding:.3in .5in .2in;display:flex;flex-direction:column;gap:16px;flex:1}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.kpi{border:1px solid var(--line);border-radius:12px;padding:12px 13px 11px;background:var(--paper)}
.kpi .l{font:800 9.5px/1.2 "Manrope";letter-spacing:.16em;text-transform:uppercase;color:var(--ink3)}
.kpi .v{font:400 32px/1.05 "DM Serif Display",Georgia,serif;margin-top:6px;color:var(--ink)}
.kpi .v small{font:800 13px "Manrope";margin-left:4px;color:var(--ink2)}
.kpi .d{font:700 11.5px/1.35 "Manrope";color:var(--ink2);margin-top:3px}
.up{color:var(--good)}.down{color:var(--bad)}.flat{color:var(--ink3)}
.ok{color:var(--good)}.no{color:var(--bad)}
.cols{display:grid;grid-template-columns:1.15fr 1fr;gap:16px}
.card{border:1px solid var(--line);border-radius:12px;padding:14px 15px}
h2{margin:0 0 9px;font:800 10.5px/1.2 "Manrope";letter-spacing:.18em;text-transform:uppercase;color:var(--acc)}
ul{margin:0;padding-left:17px}li{margin:3px 0;color:var(--ink)}li::marker{color:var(--acc)}
table{width:100%%;border-collapse:collapse;font-size:12.5px}td{padding:5px 0;border-bottom:1px solid var(--line)}td:last-child{text-align:right;font-weight:800}
tr:last-child td{border-bottom:0}
.muted{color:var(--ink3);font-size:11.5px}
.next{background:var(--soft);border:0;border-radius:12px;padding:15px 16px;display:grid;grid-template-columns:1fr auto;gap:6px 18px;align-items:center}
.next h2{color:var(--accbrand)}
.next .t{font:400 22px/1.15 "DM Serif Display",Georgia,serif;color:var(--ink)}
.next p{margin:0;color:var(--ink2);grid-column:1}
.next .price{grid-row:1 / span 3;grid-column:2;text-align:center;background:var(--paper);border-radius:12px;padding:10px 14px;min-width:1.25in}
.next .price b{display:block;font:400 22px/1.1 "DM Serif Display",Georgia,serif;color:var(--ink)}
.next .price span{font:700 10.5px/1.3 "Manrope";color:var(--ink3);letter-spacing:.04em}
.ft{padding:.16in .5in .3in;display:flex;justify-content:space-between;gap:16px;color:var(--ink3);font-size:11px;border-top:1px solid var(--line);margin:0 .5in;padding-left:0;padding-right:0}
@media screen and (max-width:860px){
 body{background:var(--paper)}
 .sheet{width:auto;min-height:0;margin:0;box-shadow:none}
 .hd{padding:26px 16px 22px}.hd .in{flex-direction:column;align-items:flex-start}.mon{text-align:left}
 h1{font-size:30px}
 main{padding:18px 16px 12px}
 .kpis{grid-template-columns:1fr 1fr}
 .cols{grid-template-columns:1fr}
 .next{grid-template-columns:1fr}.next .price{grid-row:auto;grid-column:1;justify-self:start}
 .ft{margin:0 16px;flex-direction:column}
}
@media print{body{background:#fff}.sheet{margin:0;box-shadow:none;width:8.5in;height:11in;min-height:0;overflow:hidden}}
"""


def build_report(client: dict, year: int, month: int, leads: dict, site: dict, reviews: int | None, reviews_before: int | None,
                 rating: float | None, did: list[str], plan_lines: list[str], this_plan: dict | None, next_plan: dict | None,
                 agency: dict, uptime_pct: float | None = None) -> dict:
    trade = P.trade_of(client.get("trade", "")) if client.get("trade") else "barber"
    brand = M.brand_for(client, trade)
    v = brand["vars"]
    label = f"{S.month_name(month)} {year}"
    ny, nm = S.shift_month(year, month, 1)
    cs, ns = content_summary(this_plan), content_summary(next_plan)
    gain = (reviews - reviews_before) if (reviews is not None and reviews_before is not None) else None
    sug = suggest(client, leads, gain)

    # KPI tiles
    if leads.get("ok"):
        k_leads = (f'<div class="v">{leads["month"]}</div><div class="d">{_delta(leads["month"], leads["prev"])}'
                   f'{"<br>" if leads["month"] else ""}{(str(leads["people"]) + " different people") if leads["month"] else ""}</div>')
    else:
        k_leads = f'<div class="v">-</div><div class="d">{esc(leads.get("note") or "not counted")}</div>'
    if uptime_pct is not None:
        k_site = f'<div class="v ok">{uptime_pct:g}%</div><div class="d">up this month (monitor)</div>'
    elif site.get("checked"):
        k_site = (f'<div class="v {"ok" if site["up"] else "no"}">{"Up" if site["up"] else "Down"}</div>'
                  f'<div class="d">{("answered in " + _ms(site.get("ms"))) if site["up"] else esc(site.get("reason", ""))}</div>')
    else:
        k_site = f'<div class="v">-</div><div class="d">{esc(site.get("reason") or "not checked")}</div>'
    if reviews is not None:
        g = "" if gain is None else (f'<span class="up">+{gain} this month</span>' if gain > 0 else
                                     (f'<span class="down">{gain} this month</span>' if gain < 0 else '<span class="flat">no change</span>'))
        rt = f" &middot; {rating:g}&#9733;" if rating else ""
        k_rev = f'<div class="v">{reviews}</div><div class="d">{g}{rt}</div>'
    else:
        k_rev = '<div class="v">-</div><div class="d">not entered</div>'
    k_posts = (f'<div class="v">{cs["posts"]}<small>+ {cs["stories"]} stories</small></div><div class="d">on Facebook &amp; Instagram</div>'
               if cs["posts"] else '<div class="v">-</div><div class="d">no social plan this month</div>')
    kpis = (f'<section class="kpis" aria-label="This month in numbers"><div class="kpi"><div class="l">Website leads</div>{k_leads}</div>'
            f'<div class="kpi"><div class="l">Website</div>{k_site}</div><div class="kpi"><div class="l">Google reviews</div>{k_rev}</div>'
            f'<div class="kpi"><div class="l">Social posts</div>{k_posts}</div></section>')

    # what we did
    items = []
    if cs["posts"]:
        extra = ""
        if cs["holidays"]:
            extra = " including " + ", ".join(cs["holidays"][:3])
        items.append(f"Made and scheduled {cs['posts']} posts and {cs['stories']} stories{extra}.")
        tips = cs["kinds"].get("tip", 0) + cs["kinds"].get("checklist", 0)
        if tips:
            items.append(f"Shared {tips} helpful tip{'s' if tips != 1 else ''} that show customers you know your trade.")
    if site.get("checked") or uptime_pct is not None:
        items.append("Kept your website online and checked it" + (" (it is up and secure)." if site.get("up") and site.get("https") else "."))
    items += [d.strip().rstrip(".") + "." for d in did if d.strip()]
    if not items:
        items.append("Kept your website running.")
    did_html = "".join(f"<li>{esc(t)}</li>" for t in items)

    # website check table
    if uptime_pct is not None:
        rows = [("Uptime this month", f"{uptime_pct:g}%")]
        if site.get("checked"):
            rows.append(("Answered today in", _ms(site.get("ms"))))
    elif site.get("checked"):
        rows = [("Status", "Online" if site["up"] else "Not answering"), ("Answered in", _ms(site.get("ms"))),
                ("Secure (https)", "Yes" if site.get("https") else "No")]
    else:
        rows = [("Status", "Not checked")]
    site_url = M.display_site(client.get("site_url") or client.get("demo_url") or "")
    site_tbl = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in rows)
    when = site.get("at", "")
    site_note = (f'<p class="muted" style="margin:6px 0 0">{esc(site_url)}{" &middot; checked " + esc(when.replace("T", " ")) if when and site.get("checked") else ""}</p>'
                 if site_url else "")

    # leads chart
    if leads.get("ok") and leads["month"]:
        chart = _bars(leads["weeks"], v["acc_p"], "#1C2126")
        lnote = f'<p class="muted" style="margin:4px 0 0">From your website form. {leads["month"]} this month, {leads["prev"]} last month.</p>'
    else:
        chart = ""
        lnote = f'<p class="muted" style="margin:0">{esc(leads.get("note") or "No form submissions this month.") if not leads.get("ok") else "No form submissions this month."}</p>'

    # next month
    nxt = []
    if ns["posts"]:
        h = f" for {', '.join(ns['holidays'][:4])}" if ns["holidays"] else ""
        nxt.append(f"{ns['posts']} new posts and stories{h}.")
    nxt += [x.strip().rstrip(".") + "." for x in plan_lines if x.strip()]
    nxt.append("Keep your website fast, secure and up to date.")
    next_html = "".join(f"<li>{esc(t)}</li>" for t in nxt)

    sug_html = ""
    if sug:
        price = sug.get("price")
        sug_html = (f'<section class="next" aria-label="Our suggestion"><h2>Our suggestion for {esc(S.month_name(nm))}</h2>'
                    f'<div class="t">{esc(sug["name"])}</div><p>{esc(sug["what"][0].upper() + sug["what"][1:])}</p><p>{esc(sug["why"])}</p>'
                    f'<div class="price"><b>{esc(price) if price else "Ask us"}</b><span>{"per month" if price else "about pricing"}</span></div></section>')

    fonts = D.font_faces({"manrope", "dmserif"})
    css = CSS % {"brand": v["bg"], "brandink": v["ink"], "acc": v["acc_p"], "accbrand": v["acc_d"], "soft": D.mix(v["paper"], "#FFFFFF", 0.35),
                 "pattern": D.trade_pattern(brand["motif"], v["line_d"], 1)}
    name = brand["name"]
    contact = " &middot; ".join(esc(x) for x in (agency.get("email"), agency.get("phone"), agency.get("site")) if x)
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(name)} - {esc(label)} report</title><style>{fonts}{css}</style></head><body><div class="sheet">'
            f'<header class="hd"><div class="pat"></div><div class="in"><div><div class="kick">Monthly report</div><h1>{esc(name)}</h1>'
            f'<div class="sub">{esc(P.PACKS[trade]["label"])}{" &middot; " + esc(brand["city"]) if brand["city"] else ""}</div></div>'
            f'<div class="mon"><b>{esc(label)}</b><span>Prepared by {esc(agency["name"])}</span></div></div></header>'
            f'<main>{kpis}<div class="cols"><section class="card"><h2>What we did in {esc(S.month_name(month))}</h2><ul>{did_html}</ul></section>'
            f'<section class="card"><h2>Website leads by week</h2>{chart}{lnote}</section></div>'
            f'<div class="cols"><section class="card"><h2>Next month: {esc(S.month_name(nm))}</h2><ul>{next_html}</ul></section>'
            f'<section class="card"><h2>Website check</h2><table>{site_tbl}</table>{site_note}</section></div>{sug_html}</main>'
            f'<footer class="ft"><span>Questions? Just reply to this email{(" or call " + esc(agency["phone"])) if agency.get("phone") else ""}.</span>'
            f'<span>{contact or esc(agency["name"])}</span></footer></div>'
            f'<script>document.documentElement.setAttribute("data-ready","1")</script></body></html>')

    # the email
    lines = [f"Subject: Your {label} report - {name}", "", "Hi there,", "", f"Here is your {S.month_name(month)} snapshot for {name}:", ""]
    if leads.get("ok"):
        d = leads["month"] - leads["prev"]
        tail = f" ({'+' if d > 0 else ''}{d} vs {S.month_name(S.shift_month(year, month, -1)[1])})" if leads["prev"] or leads["month"] else ""
        lines.append(f"- Website leads: {leads['month']}{tail}")
    if uptime_pct is not None:
        lines.append(f"- Website: up {uptime_pct:g}% of the month")
    elif site.get("checked"):
        lines.append(f"- Website: {'up and answering in ' + _ms(site.get('ms')) if site['up'] else 'NOT answering when we checked - we are on it'}")
    if reviews is not None:
        lines.append(f"- Google reviews: {reviews}" + (f" ({'+' if gain > 0 else ''}{gain} this month)" if gain is not None else "") + (f", rating {rating:g}" if rating else ""))
    if cs["posts"]:
        lines.append(f"- Social: {cs['posts']} posts + {cs['stories']} stories on Facebook and Instagram")
    lines += ["", f"Coming up in {S.month_name(nm)}: " + (nxt[0] if nxt else "more of the same, done well.")]
    if sug:
        lines += ["", f"One idea for {S.month_name(nm)}: {sug['name']} - {sug['what']}" + (f" ({sug['price']})" if sug.get("price") else "")]
    lines += ["", "The one-page report is attached. Any questions, just reply to this email.", "", "Thank you for trusting us with your business online!",
              agency["name"]]
    email = "\n".join(lines) + "\n"
    return {"html": page, "email": email, "suggestion": sug, "kpis": {"leads": leads.get("month"), "leads_prev": leads.get("prev"),
            "site_up": site.get("up"), "ms": site.get("ms"), "reviews": reviews, "reviews_gain": gain, "posts": cs["posts"]}}


def _plan_for(client: dict, year: int, month: int, path: str | None) -> dict | None:
    p = path or os.path.join(M.default_out(client, f"{year}-{month:02d}"), "posts.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the monthly one-page report + email for a client.")
    ap.add_argument("client", nargs="?", default=os.path.join(ROOT, "data", "agency", "clients.json"))
    ap.add_argument("--id", dest="cid")
    ap.add_argument("--month", default="last", help="YYYY-MM, or last / this (default last)")
    ap.add_argument("--leads", help="the form submissions CSV exported from the site's form tool")
    ap.add_argument("--reviews", type=int, help="Google review count now")
    ap.add_argument("--reviews-before", type=int, help="Google review count at the start of the month")
    ap.add_argument("--rating", type=float)
    ap.add_argument("--did", action="append", default=[], help="a line for 'what we did' (repeat)")
    ap.add_argument("--plan", action="append", default=[], help="a line for next month's plan (repeat)")
    ap.add_argument("--uptime", type=float, help="the month's uptime %% from a monitor")
    ap.add_argument("--offline", action="store_true", help="skip the live website check")
    ap.add_argument("--posts-json")
    ap.add_argument("--agency-name")
    ap.add_argument("--out")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.client):
        print(f"client file not found: {a.client}", file=sys.stderr)
        return 2
    y, m = S.parse_month(a.month)
    client = M.choose_clients(M.load_clients(a.client), a.cid, False)[0]
    leads = read_leads(a.leads, y, m)
    url = client.get("site_url") or client.get("demo_url") or ""
    site = {"checked": False, "up": None, "reason": "check skipped (offline)", "at": ""} if a.offline else check_site(url)
    this_plan = _plan_for(client, y, m, a.posts_json)
    ny, nm = S.shift_month(y, m, 1)
    next_plan = _plan_for(client, ny, nm, None)
    if next_plan is None:
        try:
            next_plan = M.plan_month(client, ny, nm)
        except ValueError:
            next_plan = None
    rep = build_report(client, y, m, leads, site, a.reviews, a.reviews_before, a.rating, a.did, a.plan, this_plan, next_plan,
                       load_agency(a.agency_name), a.uptime)
    out = a.out or os.path.join(ROOT, "data", "agency", "reports", M.client_slug(client), f"{y}-{m:02d}")
    os.makedirs(out, exist_ok=True)
    _guard(out)
    with open(os.path.join(out, "report.html"), "w", encoding="utf-8") as fh:
        fh.write(rep["html"])
    with open(os.path.join(out, "email.txt"), "w", encoding="utf-8") as fh:
        fh.write(rep["email"])
    pdf = ""
    if not a.no_pdf:
        from agency.content import render as R
        with R.Renderer() as r:
            if r.ok:
                pdf = os.path.join(out, "report.pdf")
                r.pdf(rep["html"], pdf)
    k = rep["kpis"]
    print(f"{client.get('name')} - {S.month_name(m)} {y}: leads {k['leads']}, site {'up' if k['site_up'] else ('down' if k['site_up'] is False else 'not checked')}, "
          f"reviews {k['reviews']}, posts {k['posts']}; suggestion: {rep['suggestion']['name'] if rep['suggestion'] else 'none'}")
    print(f"  {os.path.join(out, 'report.html')}" + (f"\n  {pdf}" if pdf else "") + f"\n  {os.path.join(out, 'email.txt')}")
    return 0


def _guard(out: str) -> None:
    ab = os.path.abspath(out)
    top = os.path.join(ROOT, "data", "agency", "reports")
    if ab.startswith(top + os.sep):
        gi = os.path.join(top, ".gitignore")
        if not os.path.exists(gi):
            with open(gi, "w", encoding="utf-8") as fh:
                fh.write("# real client reports: never committed (agency/content/client_report.py)\n*\n")


if __name__ == "__main__":
    sys.exit(main())
