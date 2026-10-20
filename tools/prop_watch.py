"""Weekly watchers for the prop-firm business (read-only, free, cheap): rule pages and discount codes.

  9  rules   fetch the firms' own public rule / help pages (MFFU, Lucid, FundedNext: the sources in research/props/firms.json
             on the firm's own domain), keep only the rule-like sentences, hash them, and compare with the stored hashes in
             research/props/rule_hashes.json. A changed page -> push "MFFU rules page changed - review" (once per change). The
             first sight of a page only stores its hash. A page that cannot be fetched (DNS blocked, 403, timeout) is recorded
             as a failure and never pushes.
  10 codes   look at coupon / affiliate pages (and a free web search when it answers) for MFFU / Lucid / FundedNext codes;
             codes not seen before are listed in research/props/code_watch.json as UNVERIFIED ("verify at checkout") and shown
             on the Prop Firms page of both dashboards. One push a week when there are new ones.

Runs from the PC's ops task (engine/ops_checks.py tick, Sunday evening window, once per ISO week; not GitHub Actions). Both
state files are machine-local (gitignored, so a weekly write never blocks the PC's auto-update); the heartbeat carries a
small summary to the phone (engine/ops_checks.hb_fields "watch").

  python tools/prop_watch.py rules|codes|all [--dry] [--timeout 10]
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
PROPS = os.path.join(ROOT, "research", "props")
HASHES_PATH = os.path.join(PROPS, "rule_hashes.json")
CODES_PATH = os.path.join(PROPS, "code_watch.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
WATCH_FIRMS = ("mffu", "lucid", "fundednext")
FIRM_NAME = {"mffu": "MFFU", "lucid": "Lucid", "fundednext": "FundedNext"}
# the firms' own pages (firms.json source keys); the cheap set: the rules that matter for the bot and for payouts
RULE_KEYS = {"mffu": ["mffu_b50", "mffu_builder", "mffu_news", "mffu_fair", "mffu_inact", "mffu_live"],
             "lucid": ["lucid_test", "lucid"],
             "fundednext": ["fn_rd_rules", "fn_rd_funded", "fn_bots", "fn_terms"]}
RULE_WORDS = re.compile(r"payout|buffer|drawdown|trailing|loss limit|daily loss|consisten|best day|split|profit target|"
                        r"contract|micro|mini|automat|bot|algo|copy trad|news|inactiv|activation|reset|minimum|maximum|"
                        r"withdraw|scaling|hedg|prohibit|overnight|close|eod|end of day|\$\d", re.I)
NOISE = re.compile(r"updated (over |about )?(a|an|\d+) \w+ ago|written by [^.]*|\d+ (views?|reads?)\b|cookie[^.]*\.|"
                   r"©[^.]*|all rights reserved[^.]*", re.I)
# coupon / affiliate pages seen in research/writeups/prop-codes-2026-10.md (third-party: every code they show is unverified)
CODE_PAGES = {
    "mffu": ["https://www.marketing91.com/my-funded-futures-discount-code/", "https://opinatron.com/en/my-funded-futures-coupon-code/",
             "https://propscope.net/en/myfundedfutures/", "https://proptradingvibes.com/blog/myfundedfutures-discount-codes"],
    "lucid": ["https://www.eltraderfinanciado.com/en/discounts/lucid-trading", "https://proptradingvibes.com/de/blog/lucid-trading-discount"],
    "fundednext": ["https://helpfutures.fundednext.com/en/articles/16295692-fundednext-futures-rapid-daily-rapid-pro-up-to-50-discount-offer",
                   "https://fundedtrading.com/propfirm/fundednext-futures/"],
}
RETRY_S, MAX_TRIES = 3600, 3                       # nothing reachable: retry an hour later, at most 3 runs a week
SEARCH = "https://html.duckduckgo.com/html/?q={q}"
SEARCH_Q = {"mffu": "MyFundedFutures discount code", "lucid": "Lucid Trading discount code", "fundednext": "FundedNext Futures discount code"}
CODE_RE = re.compile(r"(?:code|coupon|promo)\s*(?:code)?\s*(?:is|:|-|–|—)?\s*[\"“'‘]?\s*([A-Z][A-Z0-9]{2,15})\b")
STOP = {"THE", "FOR", "AND", "OFF", "USE", "CODE", "COUPON", "PROMO", "COPY", "GET", "SAVE", "NEW", "USD", "FAQ", "MFFU", "LUCID",
        "FUNDEDNEXT", "DISCOUNT", "DEAL", "DEALS", "HERE", "NOW", "APPLY", "VALID", "CHECKOUT", "TODAY", "NONE", "EVAL", "RAPID",
        "BUILDER", "PRO", "FLEX", "EOD", "FREE", "OCTOBER", "NOVEMBER", "ALL", "YOUR", "THIS", "WITH", "VERIFIED", "WORKING",
        "EXPIRED", "SHOW", "REVEAL", "CLICK", "LINK", "BEST", "TOP", "OUR", "NOT", "YES", "HTTPS", "HTML", "WWW"}


def _now_et(now=None) -> dt.datetime:
    return dt.datetime.fromtimestamp(time.time() if now is None else now, ET)


def _json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(tmp, path)


def fetch(url, timeout=10.0) -> tuple[str | None, str | None]:
    """(text, None) or (None, short error). Plain GET, no cookies, no auth; never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(2_000_000)
            cs = r.headers.get_content_charset() or "utf-8"
        return raw.decode(cs, "replace"), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:                                   # DNS blocked, proxy refusal, timeout, TLS
        return None, f"{e.__class__.__name__}: {str(e)[:80]}"


def page_text(raw: str) -> str:
    """Visible text of an HTML page (scripts, styles, nav and footers dropped), whitespace collapsed."""
    t = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)[^>]*>.*?</\1>", " ", raw or "")
    t = re.sub(r"(?is)<br\s*/?>|</(p|div|li|h\d|tr|td|section|article)>", ". ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def rule_text(raw: str) -> str:
    """Only the rule-like sentences (payout, drawdown, bots, news ...), without the page's moving parts (dates, view counts)."""
    t = NOISE.sub(" ", page_text(raw))
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if 12 <= len(s.strip()) <= 600]
    keep = [s for s in sents if RULE_WORDS.search(s)]
    return "\n".join(dict.fromkeys(keep))                    # same sentence twice (menus, repeats) counts once


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rule_pages(F=None) -> list:
    F = F or _json(os.path.join(PROPS, "firms.json"), {}) or {}
    src = F.get("sources") or {}
    out = []
    for firm in WATCH_FIRMS:
        for k in RULE_KEYS.get(firm, []):
            if src.get(k):
                out.append({"firm": firm, "key": k, "url": src[k]})
    return out


def check_rules(now=None, fetcher=fetch, pages=None, path=HASHES_PATH, timeout=10.0, deadline_s=120.0) -> dict:
    """Fetch every rule page, compare its hash with the stored one. Returns {"changes", "errors", "checked", "state"}; the
    caller pushes the changes. The state file is written (unless path is None)."""
    now = time.time() if now is None else now
    st = _json(path, {}) if path else {}
    st.setdefault("pages", {})
    st.setdefault("changes", [])
    t0, changes, errors, checked = time.time(), [], [], 0
    stamp = _now_et(now).strftime("%Y-%m-%d %H:%M ET")
    for pg in pages if pages is not None else rule_pages():
        rec = st["pages"].setdefault(pg["url"], {"firm": pg["firm"], "key": pg["key"], "first_seen": None, "hash": None, "fails": 0})
        if time.time() - t0 > deadline_s:
            errors.append({**pg, "error": "skipped: weekly time budget used"})
            continue
        raw, err = fetcher(pg["url"], timeout) if fetcher is fetch else fetcher(pg["url"])
        rec["last_try"] = stamp
        if err or not raw:
            rec["fails"] = int(rec.get("fails") or 0) + 1
            rec["last_error"] = err or "empty page"
            errors.append({**pg, "error": rec["last_error"]})
            continue
        txt = rule_text(raw)
        if len(txt) < 40:
            rec["fails"] = int(rec.get("fails") or 0) + 1
            rec["last_error"] = "no rule text found (page layout changed or blocked)"
            errors.append({**pg, "error": rec["last_error"]})
            continue
        checked += 1
        h = digest(txt)
        rec.update(last_ok=stamp, fails=0, last_error=None, chars=len(txt))
        if rec.get("hash") is None:
            rec.update(hash=h, first_seen=stamp)
        elif rec["hash"] != h:
            ch = {"firm": pg["firm"], "key": pg["key"], "url": pg["url"], "old": rec["hash"][:12], "new": h[:12], "seen": stamp}
            changes.append(ch)
            st["changes"] = ([ch] + st["changes"])[:30]
            rec.update(hash=h, last_change=stamp)
    st.update(updated=stamp, how="sha256 of the rule-like sentences of each firm page (tools/prop_watch.py); a change means "
                                 "'read the page again', not that a rule changed. Text is not stored.",
              last_run={"checked": checked, "errors": len(errors), "changes": len(changes)})
    if path:
        _write(path, st)
    return {"changes": changes, "errors": errors, "checked": checked, "state": st}


def find_codes(text: str) -> list:
    out = []
    for m in CODE_RE.finditer(text or ""):
        c = m.group(1)
        if c in STOP or c.isdigit() or len(set(c)) < 2:
            continue
        ctx = text[max(0, m.start() - 80): m.end() + 80]
        off = re.search(r"(\d{1,2})\s*%", ctx)
        out.append({"code": c, "off": f"{off.group(1)}%" if off else None})
    seen, uniq = set(), []
    for c in out:
        if c["code"] not in seen:
            seen.add(c["code"])
            uniq.append(c)
    return uniq


def known_codes(F=None) -> dict:
    F = F or _json(os.path.join(PROPS, "firms.json"), {}) or {}
    out = {}
    for f in F.get("firms") or []:
        s = out.setdefault(f.get("id"), set())
        for c in f.get("codes") or []:
            for part in re.split(r"[\s/,]+", str(c.get("code") or "")):
                if re.fullmatch(r"[A-Z][A-Z0-9]{2,15}", part):
                    s.add(part)
    return out


def check_codes(now=None, fetcher=fetch, pages=None, path=CODES_PATH, timeout=10.0, search=True, deadline_s=90.0) -> dict:
    now = time.time() if now is None else now
    st = _json(path, {}) if path else {}
    st.setdefault("codes", [])
    stamp = _now_et(now).strftime("%Y-%m-%d")
    known = known_codes()
    have = {(c["firm"], c["code"]) for c in st["codes"]}
    pages = pages if pages is not None else CODE_PAGES
    t0, new, errors, ok = time.time(), [], [], 0
    jobs = [(firm, u, "page") for firm, urls in pages.items() for u in urls]
    if search:
        jobs += [(firm, SEARCH.format(q=urllib.parse.quote_plus(q)), "search") for firm, q in SEARCH_Q.items() if firm in pages]
    for firm, url, kind in jobs:
        if time.time() - t0 > deadline_s:
            errors.append({"firm": firm, "url": url, "error": "skipped: weekly time budget used"})
            continue
        raw, err = fetcher(url, timeout) if fetcher is fetch else fetcher(url)
        if err or not raw:
            errors.append({"firm": firm, "url": url, "error": err or "empty"})
            continue
        ok += 1
        for c in find_codes(page_text(raw)):
            if c["code"] in known.get(firm, set()) or (firm, c["code"]) in have:
                continue
            row = {"firm": firm, "firm_name": FIRM_NAME.get(firm, firm), "code": c["code"], "off": c["off"], "seen": stamp,
                   "source": urllib.parse.urlparse(url).netloc + (" (search)" if kind == "search" else ""), "st": "unverified",
                   "note": "verify at checkout: seen on a third-party page, not confirmed by the firm"}
            have.add((firm, c["code"]))
            new.append(row)
    for c in st["codes"]:
        c["new"] = False
    for c in new:
        c["new"] = True
    st["codes"] = (new + st["codes"])[:60]
    st.update(updated=stamp, how="codes seen on coupon / affiliate pages and a free web search (tools/prop_watch.py), not in "
                                 "firms.json yet. All UNVERIFIED: type the code at checkout and check the total before paying.",
              last_run={"sources_ok": ok, "errors": len(errors), "new": len(new)}, errors=errors[:12])
    if path:
        _write(path, st)
    return {"new": new, "errors": errors, "ok": ok, "state": st}


def summary(hash_path=HASHES_PATH, code_path=CODES_PATH) -> dict:
    """Small block for the dashboards and the heartbeat: last runs, recent rule-page changes, newest codes."""
    h, c = _json(hash_path, {}) or {}, _json(code_path, {}) or {}
    pages = h.get("pages") or {}
    return {"rules": {"updated": h.get("updated"), "pages": len(pages), "ok": sum(1 for p in pages.values() if p.get("last_ok") and not p.get("last_error")),
                      "failing": [{"firm": p.get("firm"), "key": p.get("key"), "error": p.get("last_error")} for p in pages.values() if p.get("last_error")][:8],
                      "changes": (h.get("changes") or [])[:6], "last_run": h.get("last_run")},
            "codes": {"updated": c.get("updated"), "rows": [{k: x.get(k) for k in ("firm", "firm_name", "code", "off", "seen", "source", "st", "new")}
                                                            for x in (c.get("codes") or [])[:12]],
                      "last_run": c.get("last_run"), "note": "unverified: verify at checkout"},
            "schedule": "weekly, Sunday evening, from the PC ops task (engine/ops_checks.py)"}


def rule_notice(ch: dict) -> dict:
    name = FIRM_NAME.get(ch["firm"], ch["firm"])
    return {"sub": "rules", "title": f"{name} rules page changed — review",
            "body": f"{ch['key']}: {ch['url']} changed this week. Read it before the next trade or payout; then tell Claude if a rule moved.",
            "key": f"biz:rules:{ch['key']}:{ch['new']}"}


def codes_notice(new: list, now=None) -> dict | None:
    if not new:
        return None
    iso = _now_et(now).isocalendar()
    txt = ", ".join(f"{c['firm_name']} {c['code']}" + (f" ({c['off']})" if c.get("off") else "") for c in new[:6])
    return {"sub": "codes", "title": "New discount codes seen (unverified)",
            "body": f"{txt}. Verify at checkout. List: Prop Firms page.", "key": f"biz:codes:{iso[0]}-W{iso[1]:02d}"}


def weekly(now=None, state=None, fetcher=fetch, hash_path=HASHES_PATH, code_path=CODES_PATH) -> list:
    """The ops task's weekly run: both watchers once per ISO week (state["prop_watch_wk"]); returns the notices to push."""
    now = time.time() if now is None else now
    iso = _now_et(now).isocalendar()
    wk = f"{iso[0]}-W{iso[1]:02d}"
    if state is not None and state.get("prop_watch_wk") == wk:
        return []
    tries = (state or {}).get("prop_watch_try") or {}
    if tries.get("wk") == wk and now - float(tries.get("t") or 0) < RETRY_S:
        return []                                        # nothing was reachable a moment ago: wait before the next try
    out = []
    r = check_rules(now, fetcher, path=hash_path)
    out += [rule_notice(c) for c in r["changes"]]
    c = check_codes(now, fetcher, path=code_path)
    n = codes_notice(c["new"], now)
    if n:
        out.append(n)
    if state is not None:
        n_try = (int(tries.get("n") or 0) if tries.get("wk") == wk else 0) + 1
        state["prop_watch_try"] = {"wk": wk, "t": int(now), "n": n_try}
        if not r["checked"] and not c["ok"] and n_try < MAX_TRIES:
            return out                                   # offline / every site blocked: try again in an hour (3 tries a week)
        state["prop_watch_wk"] = wk
        state["prop_watch_last"] = {"t": int(now), "rules_checked": r["checked"], "rules_errors": len(r["errors"]),
                                    "changes": len(r["changes"]), "codes_new": len(c["new"]), "code_errors": len(c["errors"])}
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python tools/prop_watch.py", description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=("rules", "codes", "all"))
    ap.add_argument("--dry", action="store_true", help="do not write the state files")
    ap.add_argument("--timeout", type=float, default=10.0)
    a = ap.parse_args(argv)
    if a.what in ("rules", "all"):
        r = check_rules(path=None if a.dry else HASHES_PATH, timeout=a.timeout)
        print(f"rules: {r['checked']} pages read, {len(r['changes'])} changed, {len(r['errors'])} failed")
        for c in r["changes"]:
            print("  CHANGED", rule_notice(c)["title"], c["url"])
        for e in r["errors"]:
            print("  failed", e["key"], e["error"])
    if a.what in ("codes", "all"):
        c = check_codes(path=None if a.dry else CODES_PATH, timeout=a.timeout)
        print(f"codes: {c['ok']} sources read, {len(c['new'])} new (unverified), {len(c['errors'])} failed")
        for x in c["new"]:
            print("  NEW", x["firm_name"], x["code"], x.get("off") or "", "from", x["source"], "- verify at checkout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
