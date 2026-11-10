"""MERCURY, money machine #2 "DEALS": watches public prop-firm / data / platform pages for sales, codes, free resets and rule changes.

It NEVER buys anything and never logs in. It does one polite GET per page per run (timeout 10 s, generic user agent, public URLs only, at most
one fetch per page every --min-minutes), turns the page into plain text, picks out the lines that talk about a discount, a code, an end date,
a reset or a rule change, compares them with what it saw last time (state file), and scores each deal by the dollars it would save against the
owner's real price list. Everything is an estimate and says so.

    python tools/money/mercury.py --out DIR              # live: fetch the config pages (needs network, every page optional)
    python tools/money/mercury.py --out DIR --fixture    # offline: the bundled sample pages (tools/money/fixtures/mercury/*.html), fixed clock
    python tools/money/mercury.py --selftest             # canned HTML checks (no network, writes only to a temp folder)
Writes DIR/mercury.json (contract: tools/money, docs/NIGHT_BRIEF.md) and DIR/mercury_state.json (the last-seen lines). Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html.parser
import json
import os
import re
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures", "mercury")
UA = "price-watch/1.0 (personal deal checker; one request per page)"
TIMEOUT = 10
MAX_BYTES = 1_500_000
FIXTURE_NOW = "2026-11-10T12:00:00+00:00"

# the owner's real prices (CLAUDE.md): Builder 25K $63, ATLAS 25K $43, Builder 50K $91.80
PRICES = {"mffu": {25: 63.0, 50: 91.80}, "atlas": {25: 43.0}}
DEFAULT_PRICES = {25: 63.0, 50: 91.80}      # reference for a firm the owner has no price at: the MFFU price of the same size
RESET_FACTOR = 0.25                         # assumption: a reset only pays off if an eval fails, so it is valued at a quarter of an eval (an estimate)

# public pages only. owner = a firm / tool the owner uses today. ref_usd = what one purchase is worth for non-eval pages (estimate, edit it).
DEFAULT_PAGES = [
    {"id": "mffu", "firm": "MyFundedFutures", "kind": "prop", "owner": True, "url": "https://myfundedfutures.com/"},
    {"id": "apex", "firm": "Apex Trader Funding", "kind": "prop", "owner": False, "url": "https://apextraderfunding.com/"},
    {"id": "topstep", "firm": "Topstep", "kind": "prop", "owner": False, "url": "https://www.topstep.com/"},
    {"id": "tpt", "firm": "TakeProfitTrader", "kind": "prop", "owner": False, "url": "https://takeprofittrader.com/"},
    {"id": "ninjatrader", "firm": "NinjaTrader", "kind": "platform", "owner": True, "ref_usd": 100.0, "url": "https://ninjatrader.com/pricing/"},
    {"id": "tradingview", "firm": "TradingView", "kind": "data", "owner": True, "ref_usd": 30.0, "url": "https://www.tradingview.com/pricing/"},
    {"id": "atlas", "firm": "ATLAS", "kind": "prop", "owner": True, "url": None},      # no public page configured yet: add its URL here
]

RE_PCT = re.compile(r"(\b(?:up to|upto|extra)\s+)?(\d{1,2})\s?%\s*(?:off|discount)|(?:save|savings of)\s+(?:up to\s+)?(\d{1,2})\s?%", re.I)
RE_CODE = re.compile(r"(?i:\bcodes?|\bcoupon|\bpromo)\s*[:\-]?\s*[\"'\u201c]?([A-Z][A-Z0-9]{3,15})\b")
RE_SIZE = re.compile(r"\b(25|50|100|150)\s?k\b", re.I)
RE_RESET = re.compile(r"\bfree\s+resets?\b", re.I)
RE_SALE = re.compile(r"\b(sale|offer|deal|promo|promotion|discount|coupon|save|savings)\b", re.I)
RE_RULE_HEAD = re.compile(r"\b(rule change|rules? change|new rules?|updated rules?|rules? update|now freezes|is now|are now|now requires?|updated for|effective|no longer|changed to)\b", re.I)
RE_TOPIC = re.compile(r"(drawdown|consistency|payout|daily loss|loss limit|profit target|contract limit|scaling|news|automat|\bbots?\b|\balgo|copy trad|hedg|activation|inactiv|minimum (?:trading )?days|reset)", re.I)
RE_NO_CODE = re.compile(r"no (?:promo )?code (?:needed|required)|automatically applied", re.I)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
RE_END_KEY = r"(?:ends?|ending|expires?|expiring|until|through|valid (?:until|through)|offer ends|by)"
RE_DATE_NAME = re.compile(RE_END_KEY + r"\s+(?:on\s+)?(?:(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?,?\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", re.I)
RE_DATE_NUM = re.compile(RE_END_KEY + r"\s+(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", re.I)
RE_IN_DAYS = re.compile(r"\b(?:ends?|expires?|ending)\s+in\s+(\d{1,2})\s+days?\b", re.I)
RE_TODAY = re.compile(r"\b(?:ends?|expires?|ending)\s+(?:today|tonight)\b", re.I)
RE_TOMORROW = re.compile(r"\b(?:ends?|expires?|ending)\s+tomorrow\b", re.I)

IMPACT = [  # topic -> what it means for the bot, in plain words
    (re.compile(r"automat|\bbots?\b|\balgo|copy trad", re.I), "It touches automated trading, which the bot relies on. Read it before the next eval."),
    (re.compile(r"consistency|payout", re.I), "It can change when and how much you can withdraw."),
    (re.compile(r"drawdown|daily loss|loss limit", re.I), "It can change how much room the account has for a bad day."),
    (re.compile(r"profit target|minimum", re.I), "It can change how fast an eval can be passed."),
    (re.compile(r"contract limit|scaling", re.I), "It can change how many micros the bot may use."),
    (re.compile(r"news|hedg", re.I), "It can change which trades are allowed."),
    (re.compile(r"reset|activation|inactiv", re.I), "It can change what a failed eval or an idle account costs."),
]


# ------------------------------------------------------------------------------------------------ text
class _Text(html.parser.HTMLParser):
    BLOCK = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "tr", "section", "article", "header", "footer", "ul", "ol", "table", "td", "th", "span", "a", "button"}
    SKIP = {"script", "style", "noscript", "template", "svg", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK and tag not in ("span", "a", "button"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK and tag not in ("span", "a", "button"):
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def page_lines(raw: str) -> list:
    """Visible text of an HTML page as clean lines (script / style / head dropped, long lines split into sentences)."""
    p = _Text()
    try:
        p.feed(raw)
        p.close()
    except Exception:
        pass
    lines = []
    for chunk in "".join(p.out).split("\n"):
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if not chunk:
            continue
        # a block is one line (so "30% off ... Sale ends in 3 days." stays together); only a very long block is cut into sentences
        for s in ([chunk] if len(chunk) <= 400 else re.split(r"(?<=[.!?])\s+(?=[A-Z])", chunk)):
            s = s.strip()
            if 6 <= len(s) <= 400:
                lines.append(s)
    return lines


# ------------------------------------------------------------------------------------------------ extraction
def _date(y, m, d, now):
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def find_expiry(line: str, now: dt.datetime):
    """The date an offer ends, as YYYY-MM-DD, or None. Handles 'ends in 3 days', 'ends tonight', 'ends Nov 13', 'until November 30, 2026', 'ends 11/13'."""
    today = now.date()
    if RE_TODAY.search(line):
        return today.isoformat()
    if RE_TOMORROW.search(line):
        return (today + dt.timedelta(days=1)).isoformat()
    m = RE_IN_DAYS.search(line)
    if m:
        return (today + dt.timedelta(days=int(m.group(1)))).isoformat()
    d = None
    m = RE_DATE_NAME.search(line)
    if m:
        mon, day, yr = MONTHS[m.group(1)[:3].lower()], int(m.group(2)), m.group(3)
        d = _date(int(yr) if yr else today.year, mon, day, now)
        if d and not yr and (today - d).days > 30:
            d = _date(today.year + 1, mon, day, now)
    else:
        m = RE_DATE_NUM.search(line)
        if m:
            mon, day, yr = int(m.group(1)), int(m.group(2)), m.group(3)
            y = (int(yr) + (2000 if len(yr) == 2 else 0)) if yr else today.year
            d = _date(y, mon, day, now)
            if d and not yr and (today - d).days > 30:
                d = _date(today.year + 1, mon, day, now)
    return d.isoformat() if d else None


def sizes_in(line: str) -> list:
    return sorted({int(x) for x in RE_SIZE.findall(line)})


def ref_price(page: dict, sizes: list):
    """(usd, label) the owner would pay for the plan(s) on this line. Eval pages use the owner's price list, others the page's ref_usd (estimate)."""
    if page.get("kind") != "prop":
        r = float(page.get("ref_usd") or 0)
        return (r, f"about ${r:.0f} for one purchase (estimate, edit ref_usd in the config)") if r else (0.0, "no reference price")
    table = {**DEFAULT_PRICES, **PRICES.get(page["id"], {})}
    cand = [s for s in sizes if s in table] or ([50] if 50 in table else [min(table)])
    best = max(cand, key=lambda s: table[s])
    own = page["id"] in PRICES and best in PRICES[page["id"]]
    return table[best], f"{best}K at ${table[best]:.2f}" + ("" if own else " (reference price, not yours)")


def impact_for(line: str) -> str:
    for rx, text in IMPACT:
        if rx.search(line):
            return text
    return "Worth a quick read."


def key_of(page_id: str, line: str) -> str:
    norm = re.sub(r"[^a-z0-9%$]+", " ", line.lower()).strip()
    return hashlib.sha1(f"{page_id}|{norm}".encode()).hexdigest()[:12]


def days_left(expires, now: dt.datetime):
    if not expires:
        return None
    return (dt.date.fromisoformat(expires) - now.date()).days


def score_deal(usd, days, has_code, owner_page, risk):
    s = min(100, round((usd or 0) * 1.6))
    if has_code:
        s += 10
    if days is not None and 0 <= days <= 3:
        s += 10
    if not owner_page:
        s -= 15
    if risk == "high":
        s -= 15
    return max(0, min(100, s))


def extract(page: dict, lines: list, now: dt.datetime, seen: set) -> list:
    items = []
    for line in lines:
        pm, code = RE_PCT.search(line), RE_CODE.search(line)
        key = key_of(page["id"], line)
        base = {"id": f"{page['id']}-{key[:6]}", "key": key, "firm": page["firm"], "page": page["id"], "url": page.get("url"), "new": key not in seen,
                "expires": find_expiry(line, now), "code": code.group(1) if code else None, "text": line[:240]}
        days = days_left(base["expires"], now)
        if days is not None and days < 0:
            continue                                                  # already over: not a deal
        if pm and RE_SALE.search(line) or pm and "off" in line.lower():
            pct = int(pm.group(2) or pm.group(3))
            if not 3 <= pct <= 95:
                continue
            sizes = sizes_in(line)
            ref, ref_txt = ref_price(page, sizes)
            usd = round(ref * pct / 100, 2)
            up_to = bool(pm.group(1)) or "up to" in line.lower()
            no_code = bool(RE_NO_CODE.search(line))
            pts = (0 if base["expires"] else 1) + (0 if (base["code"] or no_code) else 1) + (0 if page["owner"] else 1) + (1 if pct >= 70 else 0)
            risk = "high" if up_to else ("low" if pts == 0 else "med" if pts <= 2 else "high")
            how = f"with code {base['code']}" if base["code"] else ("no code needed" if no_code else "no code on the page, check the checkout")
            when = "" if not base["expires"] else (" It ends today." if days == 0 else f" It ends in {days} day{'s' if days != 1 else ''} ({base['expires']}).")
            detail = (f"{pct}% off{' (up to, the real cut may be smaller)' if up_to else ''}, {how}. About ${usd:.2f} saved on {ref_txt}, an estimate.{when}"
                      + ("" if page["owner"] else " Not a firm you use now: switching has its own cost and rules."))
            items.append({**base, "kind": "deal", "pct": pct, "title": f"{pct}% off at {page['firm']}", "detail": detail, "usd": usd,
                          "score": score_deal(usd, days, bool(base["code"]), page["owner"], risk), "risk": risk, "affects_me": False})
        elif RE_RESET.search(line):
            sizes = sizes_in(line)
            ref, ref_txt = ref_price(page, sizes)
            usd = round(ref * RESET_FACTOR, 2)
            risk = "low" if base["expires"] and page["owner"] else "med"
            when = "" if not base["expires"] else f" Until {base['expires']}."
            items.append({**base, "kind": "reset", "pct": None, "title": f"Free reset at {page['firm']}", "detail": f"A free reset is worth about ${usd:.2f}, an estimate: a reset only helps if an eval fails, so it is valued at a quarter of {ref_txt}.{when}",
                          "usd": usd, "score": score_deal(usd, days, False, page["owner"], risk), "risk": risk, "affects_me": False})
        elif RE_RULE_HEAD.search(line) and RE_TOPIC.search(line) and not RE_SALE.search(line):
            bots = bool(re.search(r"automat|\bbots?\b|\balgo|copy trad", line, re.I))
            affects = bool(page["owner"] or bots)
            items.append({**base, "kind": "rule", "pct": None, "title": f"Rule change at {page['firm']}", "detail": (impact_for(line) if affects else "A firm you do not use now. Only matters if you switch.") + f" The page says: {line[:160]}",
                          "usd": None, "score": 70 if affects else 25, "risk": "med" if affects else "low", "affects_me": affects})
    # one item per line key, best first
    items.sort(key=lambda i: (-i["score"], i["title"]))
    return items


# ------------------------------------------------------------------------------------------------ fetch + state
def fetch_page(url: str) -> str:
    """One polite GET: generic agent, 10 s timeout, size cap, public http(s) only. Raises on any problem (the caller records it)."""
    if not url or not url.lower().startswith(("http://", "https://")):
        raise ValueError("not a public web address")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.5", "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(MAX_BYTES).decode(r.headers.get_content_charset() or "utf-8", "replace")


def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            s = json.load(fh)
        return s if isinstance(s, dict) and isinstance(s.get("pages"), dict) else {"v": 1, "pages": {}}
    except Exception:
        return {"v": 1, "pages": {}}


def money(v) -> str:
    return f"${v:,.2f}".replace(".00", "") if v is not None else "n/a"


def build_pick(items: list, now: dt.datetime, owner_pages: set) -> dict:
    cand = [i for i in items if i["kind"] in ("deal", "reset") and i["page"] in owner_pages and i["score"] >= 40]
    if not cand:
        return {"buy": False, "title": "Nothing worth buying now", "why": "No deal on a firm or tool you use scores high enough. Waiting costs nothing.", "usd": None, "buy_by": None}
    b = cand[0]
    d = days_left(b["expires"], now)
    why = f"Saves about {money(b['usd'])} (estimate). Risk: {b['risk']}."
    if b["code"]:
        why += f" Code {b['code']}."
    if d is not None:
        why += " Ends today." if d == 0 else f" Ends in {d} day{'s' if d != 1 else ''}."
    why += " Only worth it if you were going to buy this anyway; Mercury never buys for you."
    return {"buy": True, "title": f"{b['title']}" + (f" (code {b['code']})" if b["code"] else ""), "why": why, "usd": b["usd"], "buy_by": b["expires"], "item": b["id"]}


def run(pages: list, out: str, fixture: bool = False, now: dt.datetime | None = None, fetcher=None, min_minutes: int = 30, write: bool = True) -> dict:
    now = now or (dt.datetime.fromisoformat(FIXTURE_NOW) if fixture else dt.datetime.now(dt.timezone.utc))
    sp = os.path.join(out, "mercury_state.json")
    state = load_state(sp) if write or os.path.isfile(sp) else {"v": 1, "pages": {}}
    new_state = {"v": 1, "pages": {}}
    notes, items, failed, fresh_skip, skipped_cfg = [], [], [], 0, []
    for pg in pages:
        pid, old = pg["id"], state["pages"].get(pg["id"], {})
        seen = set(old.get("keys", {}))
        if not pg.get("url") and not fixture:
            skipped_cfg.append(pg["firm"])
            continue
        raw, err = None, None
        if fixture:
            fp = os.path.join(FIXTURES, f"{pid}.html")
            if not os.path.isfile(fp):
                continue
            with open(fp, encoding="utf-8") as fh:
                raw = fh.read()
        else:
            last = old.get("fetched")
            try:
                recent = last and (now - dt.datetime.fromisoformat(last)).total_seconds() < min_minutes * 60
            except ValueError:
                recent = False
            if recent and old.get("items") is not None:
                fresh_skip += 1
                items.extend(old["items"])
                new_state["pages"][pid] = old
                continue
            try:
                raw = (fetcher or fetch_page)(pg["url"])
            except Exception as e:                                   # a page may be down, blocked or changed: never fatal
                err = f"{type(e).__name__}"
        if raw is None:
            failed.append(pg["firm"])
            if old:
                items.extend([{**i, "new": False} for i in old.get("items", [])])
                new_state["pages"][pid] = old
            notes.append(f"Could not read {pg['firm']} ({err}); showing what was seen last time." if old else f"Could not read {pg['firm']} ({err}); nothing seen yet.")
            continue
        found = extract(pg, page_lines(raw), now, seen)
        # the state keeps what was seen so the next run can say what is new; "new" is only for deals the first run did not know
        keys = {i["key"]: i["title"] for i in found}
        for k, t in (old.get("keys") or {}).items():
            if k not in keys:
                notes.append(f"No longer on the {pg['firm']} page: {t}.")
        new_state["pages"][pid] = {"fetched": now.isoformat(), "keys": keys, "items": [{**i, "new": False} for i in found], "hash": hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]}
        items.extend(found)
    if skipped_cfg:
        notes.append("No public page set yet for: " + ", ".join(skipped_cfg) + ". Add its web address in DEFAULT_PAGES to watch it.")
    if fresh_skip:
        notes.append(f"{fresh_skip} page(s) were read less than {min_minutes} minutes ago, so they were not asked again (polite).")
    items.sort(key=lambda i: (-i["score"], i["title"]))
    items = items[:14]
    owner_pages = {p["id"] for p in pages if p.get("owner")}
    pick = build_pick(items, now, owner_pages)
    deals = [i for i in items if i["kind"] in ("deal", "reset")]
    mine = [i for i in deals if i["page"] in owner_pages]
    best = max(mine or deals, key=lambda i: i["score"]) if deals else None
    if best and best["usd"]:
        text = f"Best deal now: {best['title']}, about {money(best['usd'])} saved (estimate)."
    elif best:
        text = f"Best deal now: {best['title']}."
    else:
        text = "No deals found right now. Nothing to buy."
    status = "sample" if fixture else ("stale" if failed else "ok")
    notes += ["Estimates only: each saving is the percent off times your own price for that plan. Reference prices are used for firms you do not use.",
              "Mercury only reads public pages and never buys, logs in or pays. A banner may be a lead-in or wrong: check the checkout before you pay.",
              "A discount is only a saving if you would have bought the eval anyway. Do not buy extra evals for a sale. This is not a monthly income."]
    doc = {"v": 1, "id": "mercury", "asof": now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": "paper", "status": status,
           "headline": {"text": text, "usd_month": None},
           "items": [{k: v for k, v in i.items()} for i in items], "pick": pick, "prices": {"builder_25k": 63.0, "atlas_25k": 43.0, "builder_50k": 91.80},
           "pages": [{"id": p["id"], "firm": p["firm"], "ok": p["firm"] not in failed and bool(p.get("url") or (fixture and os.path.isfile(os.path.join(FIXTURES, p["id"] + ".html")))), "owner": bool(p.get("owner"))} for p in pages],
           "notes": notes}
    if write:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "mercury.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
        with open(sp, "w", encoding="utf-8") as fh:
            json.dump(new_state, fh, ensure_ascii=False)
    return doc


def contract_problems(doc: dict) -> list:
    p = []
    if doc.get("v") != 1 or doc.get("id") != "mercury" or doc.get("mode") != "paper" or doc.get("status") not in ("ok", "stale", "sample"):
        p.append("header")
    try:
        dt.datetime.strptime(doc["asof"], "%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        p.append("asof")
    h = doc.get("headline") or {}
    if not isinstance(h.get("text"), str) or not (h.get("usd_month") is None or isinstance(h["usd_month"], (int, float))):
        p.append("headline")
    for i in doc.get("items", []):
        if not (isinstance(i.get("title"), str) and isinstance(i.get("detail"), str) and (i.get("usd") is None or isinstance(i["usd"], (int, float)))
                and isinstance(i.get("score"), int) and 0 <= i["score"] <= 100 and i.get("risk") in ("low", "med", "high")):
            p.append(f"item {i.get('id')}")
    if not isinstance(doc.get("notes"), list):
        p.append("notes")
    return p


# ------------------------------------------------------------------------------------------------ selftest
def selftest() -> int:
    bad = []

    def ok(name, cond, info=""):
        print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {info}"))
        if not cond:
            bad.append(name)

    now = dt.datetime.fromisoformat(FIXTURE_NOW)
    pages = [p for p in DEFAULT_PAGES]
    with tempfile.TemporaryDirectory(prefix="mercury-") as tmp:
        doc = run(pages, tmp, fixture=True, now=now)
        ok("contract: header, headline, items, notes", not contract_problems(doc), contract_problems(doc))
        ok("fixture status is sample, mode paper, no monthly promise", doc["status"] == "sample" and doc["mode"] == "paper" and doc["headline"]["usd_month"] is None)
        by = {}
        for i in doc["items"]:
            by.setdefault(i["page"], []).append(i)
        m = next(i for i in by["mffu"] if i["kind"] == "deal")
        ok("MFFU: 30% off, code BLACK30, ends in 3 days -> 2026-11-13", m["pct"] == 30 and m["code"] == "BLACK30" and m["expires"] == "2026-11-13", m)
        ok("MFFU: saving = 30% of the Builder 50K price $91.80 = $27.54 (the dearer of the 25K / 50K the line names)", abs(m["usd"] - 27.54) < 0.01, m["usd"])
        ok("MFFU: the page's <script> text '99% off' is ignored", not any(i.get("pct") == 99 for i in doc["items"]))
        r = next(i for i in by["mffu"] if i["kind"] == "reset")
        ok("MFFU: free reset until 2026-11-30, valued at a quarter of the 50K price (estimate)", r["expires"] == "2026-11-30" and abs(r["usd"] - 22.95) < 0.01, r)
        ru = [i for i in by["mffu"] if i["kind"] == "rule"]
        ok("MFFU: a rule change that affects me (payout consistency) with a plain impact", ru and ru[0]["affects_me"] and "withdraw" in ru[0]["detail"], ru)
        a = next(i for i in by["apex"] if i["kind"] == "deal")
        ok("Apex: 80% off, code APEX80, ends Nov 13, not my firm -> lower score, med/high risk", a["pct"] == 80 and a["code"] == "APEX80" and a["expires"] == "2026-11-13" and a["risk"] in ("med", "high"), a)
        ok("Apex: priced against the reference 50K price, not mine (says so)", "reference price" in a["detail"] and abs(a["usd"] - 73.44) < 0.01, a["detail"])
        ar = [i for i in by["apex"] if i["kind"] == "rule"]
        ok("Apex rule change is not 'mine' (a firm I do not use)", ar and not ar[0]["affects_me"], ar)
        t = next(i for i in by["topstep"] if i["kind"] == "deal")
        ok("Topstep: 15% off with 'no code needed'", t["pct"] == 15 and t["code"] is None and "no code needed" in t["detail"], t["detail"])
        ts = [i for i in by["topstep"] if i["kind"] == "rule"]
        ok("Topstep: a dated rule change, not mine", ts and not ts[0]["affects_me"])
        ok("TakeProfitTrader: nothing found on a quiet page", "tpt" not in by)
        n = next(i for i in by["ninjatrader"] if i["kind"] == "deal")
        ok("NinjaTrader: 20% off code NTHOLIDAY ends 2026-12-05, priced on the configured reference", n["code"] == "NTHOLIDAY" and n["expires"] == "2026-12-05" and abs(n["usd"] - 20.0) < 0.01, n)
        tv = by["tradingview"]
        up = next(i for i in tv if i.get("pct") == 16)
        ok("TradingView: 'Save up to 16%' is high risk (the real cut may be smaller)", up["risk"] == "high", up)
        tonight = next(i for i in tv if i.get("pct") == 10)
        ok("TradingView: 'ends tonight' expires today", tonight["expires"] == "2026-11-10" and "ends today" in tonight["detail"].lower(), tonight)
        ok("the pick is an owner-firm deal with a plain 'why', and says Mercury never buys", doc["pick"]["buy"] and doc["pick"]["item"] in {i["id"] for i in doc["items"]} and "never buys" in doc["pick"]["why"], doc["pick"])
        ok("ATLAS has no public page: listed in the notes only in live mode, never fetched", all(p["id"] != "atlas" or not p["ok"] for p in doc["pages"]))
        ok("items are sorted best score first", [i["score"] for i in doc["items"]] == sorted((i["score"] for i in doc["items"]), reverse=True))
        ok("every deal row has a $ figure; every rule row has none", all((i["usd"] is not None) == (i["kind"] != "rule") for i in doc["items"]))
        # state + diff
        d2 = run(pages, tmp, fixture=True, now=now)
        ok("second run: nothing is new any more", not any(i["new"] for i in d2["items"]) and any(i["new"] for i in doc["items"]))
        fp = os.path.join(FIXTURES, "tpt.html")
        extra = open(fp, encoding="utf-8").read().replace("</body>", "<p>Flash sale: 25% off the 50K Test account, use code TPT25. Ends in 2 days.</p></body>")
        calls = []

        def fake(url):
            calls.append(url)
            return extra if "takeprofit" in url else "<html><body><p>nothing</p></body></html>"
        live_pages = [p for p in DEFAULT_PAGES if p["id"] in ("tpt", "mffu")]
        d3 = run(live_pages, tmp, fetcher=fake, now=now + dt.timedelta(hours=2))
        tp = [i for i in d3["items"] if i["page"] == "tpt"]
        ok("live (mocked): a sale that appears on a page is flagged new, exactly one request per page", tp and tp[0]["new"] and tp[0]["code"] == "TPT25" and len(calls) == 2, (tp, calls))
        ok("live (mocked): the deal that vanished from the MFFU page is reported", any("No longer on the MyFundedFutures page" in n for n in d3["notes"]), d3["notes"])
        calls.clear()
        d4 = run(live_pages, tmp, fetcher=fake, now=now + dt.timedelta(hours=2, minutes=5))
        ok("live (mocked): asked again 5 minutes later -> no new request (polite)", not calls and any("not asked again" in n for n in d4["notes"]), calls)

        def boom(url):
            raise OSError("down")
        d5 = run(live_pages, tmp, fetcher=boom, now=now + dt.timedelta(days=1))
        ok("live (mocked): a page that is down gives status stale, a note, and the last-seen items, never a crash", d5["status"] == "stale" and any("Could not read" in n for n in d5["notes"]) and any(i["page"] == "tpt" for i in d5["items"]), d5["notes"])
        with tempfile.TemporaryDirectory(prefix="mercury2-") as t2:
            d6 = run(live_pages, t2, fetcher=boom, now=now)
            ok("live (mocked): down on the very first run -> stale, empty list, a plain headline", d6["status"] == "stale" and not d6["items"] and "No deals" in d6["headline"]["text"] and not contract_problems(d6))
        ok("fetcher refuses non-web addresses", all(_raises(lambda u=u: fetch_page(u)) for u in ("file:///etc/passwd", "ftp://x", "", None)))
    ok("expiry parser: tomorrow, 11/13, ended last year's date rolls forward", find_expiry("Ends tomorrow", now) == "2026-11-11" and find_expiry("offer ends 11/13", now) == "2026-11-13"
       and find_expiry("ends Jan 5", now) == "2027-01-05" and find_expiry("until 12/31/26", now) == "2026-12-31" and find_expiry("Sale!", now) is None)
    ok("an expired offer is dropped", extract({"id": "x", "firm": "X", "owner": True, "kind": "prop"}, ["Sale: 40% off 50K, ends Nov 1, 2026."], now, set()) == [])
    print(f"\n{'ALL PASS' if not bad else 'FAILED: ' + '; '.join(bad)}")
    return 1 if bad else 0


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Mercury: watch public pages for prop-firm sales, codes, free resets and rule changes. Never buys.")
    ap.add_argument("--out", help="folder to write mercury.json and mercury_state.json into")
    ap.add_argument("--fixture", action="store_true", help="use the bundled sample pages (offline, fixed clock)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--config", help="a JSON list of pages replacing the built-in list ({id, firm, kind, owner, url, ref_usd})")
    ap.add_argument("--min-minutes", type=int, default=30, help="do not ask the same page again within this many minutes")
    ap.add_argument("--now", help="ISO time to use as 'now' (tests)")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.out:
        ap.error("--out is required")
    pages = DEFAULT_PAGES
    if a.config:
        with open(a.config, encoding="utf-8") as fh:
            pages = json.load(fh)
    now = dt.datetime.fromisoformat(a.now) if a.now else None
    if now and now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    doc = run(pages, a.out, fixture=a.fixture, now=now, min_minutes=a.min_minutes)
    print(f"mercury: {doc['status']}, {len(doc['items'])} items. {doc['headline']['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
