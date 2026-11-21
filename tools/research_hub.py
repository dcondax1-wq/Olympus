"""Research Hub generator (owner 2026-11-21: "research hubs, more organized"). Writes tools/web_public/clio/hub.json, the one
file Clio (tools/web_public/clio/, the research library) reads for its owner view:

  works     What works now: the live strategies (Zlarior = LIT, ATLAS) with their real trades and their 2026 backtest $ a month
            (tools/web_public/trading/trades.json: src live / backtest; BLITZ stays hidden, paper)
  rejected  Tried and rejected: every entry of docs/TESTED_AND_REJECTED.md (one line, its $ figure, the write-up it points to)
            + every write-up whose status is rejected and that no entry already points to
  leads     Open leads: write-ups with status promising / candidate, and the open rows of research/findings/LEDGER.md
            (WATCH / BRANCH / OPEN / CARD)
  decide    Money decisions waiting: the Decide cards (tools/web_public/business/decisions.json) still open or "later"
  writeups  the library (research/writeups/*.md front matter: slug, title, date, family, status, summary), so Clio needs no
            8 MB data.json when the site's writeups/index.json is missing
  lab       headline counts (research/lab/*.json files, the edge light from research/lab/edge_health.json)

Every string goes through tools/site_privacy (account numbers masked, keys / private topics / home paths removed) and the
finished file is scanned again; a finding stops the build (exit 2). Read only on every source.

    python tools/research_hub.py            # write the hub
    python tools/research_hub.py --check    # build in memory, print the counts, write nothing
Run by tools/learn_night.py (nightly) and on ship (LEAD_WIRES).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools import site_privacy as SP  # noqa: E402

WRITEUPS = os.path.join(ROOT, "research", "writeups")
TAR = os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md")
LEDGER = os.path.join(ROOT, "research", "findings", "LEDGER.md")
DECIDE = os.path.join(ROOT, "tools", "web_public", "business", "decisions.json")
TRADES = os.path.join(ROOT, "tools", "web_public", "trading", "trades.json")
LAB = os.path.join(ROOT, "research", "lab")
OUT = os.path.join(ROOT, "tools", "web_public", "clio", "hub.json")
OUT_FLAT = os.path.join(ROOT, "tools", "web_public", "research", "hub.json")      # the Cities "Lab & Research" district (flat records)
STATUS_OF = {"works": "live", "leads": "lead", "rejected": "rejected", "decide": "decide"}
FAMILIES = ("baseline", "risk", "stops", "targets", "management", "bias", "filters", "timing", "sessions", "data", "other")
# 'other' is too broad for a street a family (Cities, 2026-11-21): guess one from the words, first match wins
GUESS = (("kalshi", r"\bkalshi|\bk8\b|prediction.market"), ("atlas", r"\batlas\b"), ("lit", r"zlarior|\blit\b|liquidity"),
         ("money", r"payout|funded|eval|mffu|rapid|builder|prop|account|fee|seat|business|income"), ("risk", r"siz(e|ing)|risk|drawdown|room"),
         ("management", r"breakeven|exit|trail|partial|target|stop"), ("filters", r"filter|bias|news|vix|regime|skip"),
         ("sessions", r"session|london|asia|new york|hours|timing|minute"))
FAM_ALL = FAMILIES + tuple(k for k, _ in GUESS) + ("ops",)


def fam_guess(fam: str, *texts) -> str:
    fam = (fam or "other").lower()
    if fam in FAMILIES and fam != "other":
        return fam
    t = " ".join(str(x or "") for x in texts).lower()
    for k, rx in GUESS:
        if re.search(rx, t):
            return k
    return "other"
LIVE = {"LIT": ("Zlarior (LIT)", "zlarior", "lit-strategy"), "ATLAS": ("ATLAS", "atlas", "atlas")}
MONEY_RX = re.compile(r"(-|−|\+)?\$\s?(\d[\d,]*(?:\.\d+)?)(k)?")
PM_RX = re.compile(r"(-|−|\+)?\s?\$\s?(\d[\d,]*(?:\.\d+)?)\s*(?:/\s*mo(?:nth)?\b|a month\b|per month\b)", re.I)


# ------------------------------------------------------------------------------------------------ text helpers
def clean(s, n=200) -> str:
    """Plain, private-safe, capped text: markdown marks and tags out, account numbers masked, keys / paths / mails removed."""
    s = str(s or "")
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\*+|`+|(?<![A-Za-z0-9])_+|_+(?![A-Za-z0-9])", "", s)
    s = re.sub(r"<[^>]*>", " ", s)
    s = re.sub(r"[\u0000-\u001f<>]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for f in (SP.mask_account, SP.mask_secrets, SP.mask_net, SP.mask_paths, SP.mask_emails):
        s = f(s)
    if len(s) > n:
        cut = s[:n]
        sp = cut.rfind(" ")
        s = (cut[:sp] if sp > n * 0.6 else cut).rstrip(" ,;:-") + "…"
    return s


def first_sentence(s, n=170) -> str:
    s = clean(s, 2000)
    m = re.search(r"(.+?[.!?])(\s|$)", s)
    return clean(m.group(1) if m and len(m.group(1)) >= 25 else s, n)


def per_month(text):
    m = PM_RX.search(str(text or ""))
    if not m:
        return None
    v = float(m.group(2).replace(",", ""))
    return -v if m.group(1) in ("-", "−") else v


def first_money(text):
    m = MONEY_RX.search(str(text or ""))
    if not m:
        return None
    v = float(m.group(2).replace(",", "")) * (1000 if m.group(3) else 1)
    return -v if m.group(1) in ("-", "−") else v


def slugify(stem) -> str:
    """= tools/build_web_dashboard._docs slugify (the site's writeups/<slug>.md)."""
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")[:70] or "doc"


def front(raw):
    meta = {}
    if raw.startswith("---"):
        e = raw.find("\n---", 3)
        if e > 0:
            for ln in raw[3:e].split("\n"):
                if ":" in ln and not ln.startswith(" "):
                    k, v = ln.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
            raw = raw[e + 4:]
    return meta, raw


# ------------------------------------------------------------------------------------------------ sources
def writeups():
    out = []
    for p in sorted(glob.glob(os.path.join(WRITEUPS, "*.md"))):
        stem = os.path.splitext(os.path.basename(p))[0]
        if stem.upper() == "INDEX":
            continue
        try:
            meta, body = front(open(p, encoding="utf-8").read())
        except (OSError, UnicodeDecodeError):
            continue
        h1 = re.search(r"^#\s+(.+)$", body, re.M)
        date = meta.get("date") or (re.search(r"(20\d\d-\d\d-\d\d)", stem) or re.search(r"(20\d\d-\d\d-\d\d)", body) or [None, ""])[1]
        fam = (meta.get("family") or "other").lower()
        status = (meta.get("status") or "info").lower()
        summary = meta.get("summary") or ""
        out.append({"slug": slugify(stem), "stem": stem.lower(), "title": clean(meta.get("title") or (h1.group(1) if h1 else stem), 140),
                    "date": date if re.match(r"^\d{4}-\d{2}-\d{2}$", date or "") else "",
                    "family": fam_guess(fam if fam in FAMILIES else "other", meta.get("title") or stem, summary), "status": clean(status, 160).lower(),
                    "summary": clean(summary, 420), "usd_month": per_month(summary)})
    out.sort(key=lambda w: (w["date"], w["title"]), reverse=True)
    return out


def group_of(status: str) -> str:
    s = status.lower()
    if re.match(r"^(adopt|live|adopted)", s):
        return "adopt"
    if re.match(r"^(promising|lead|candidate)", s):
        return "promising"
    if re.match(r"^finding", s):
        return "finding"
    if re.match(r"^(reject|dead|no\b)", s):
        return "rejected"
    return "info"


def tested_and_rejected(stems):
    """docs/TESTED_AND_REJECTED.md top-level bullets -> one record each (title, date, line, $, slug of the write-up)."""
    try:
        text = open(TAR, encoding="utf-8").read()
    except OSError:
        return []
    entries, cur = [], None
    for ln in text.split("\n"):
        if ln.startswith("- "):
            if cur:
                entries.append(cur)
            cur = ln[2:]
        elif cur is not None and (ln.startswith(" ") or ln.startswith("\t")) and ln.strip():
            cur += " " + ln.strip()
        elif cur is not None and not ln.strip():
            entries.append(cur)
            cur = None
    if cur:
        entries.append(cur)
    out = []
    for e in entries:
        m = re.match(r"\*\*(.+?)\*\*:?\s*(.*)$", e)
        head, rest = (m.group(1), m.group(2)) if m else ("", e)
        if not head:
            continue
        title = re.split(r"\s\(", head, maxsplit=1)[0].rstrip(":").strip()
        date = (re.search(r"(20\d\d-\d\d-\d\d)", head) or [None, ""])[1]
        slug = ""
        for md in re.findall(r"`?([A-Za-z0-9_.\-]+)\.md`?", head + " " + rest):
            if md.lower() in stems:
                slug = slugify(md)
                break
        body = rest.lstrip(":").strip() or head
        out.append({"title": clean(title, 120), "date": date, "line": first_sentence(body, 180), "usd_month": per_month(body), "slug": slug, "text": clean(body, 1600), "src": "tested"})
    return out


def ledger():
    """research/findings/LEDGER.md rows still open (WATCH / BRANCH / OPEN / CARD / FIX in flight)."""
    out = []
    try:
        lines = open(LEDGER, encoding="utf-8").read().split("\n")
    except OSError:
        return out
    for ln in lines:
        if not ln.startswith("| 20"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        date, finding, risk, status = cells[0], cells[1], cells[2], " | ".join(cells[3:])
        word = (re.match(r"([A-Z][A-Z ]+?)\b", status) or [None, ""])[1].strip()
        if word.startswith(("FIXED", "REFUTED", "DONE")):
            continue
        out.append({"title": clean(finding, 120), "date": date if re.match(r"^\d{4}-\d{2}-\d{2}$", date) else "",
                    "line": clean(f"{risk}. Status: {status}", 180), "usd": first_money(risk), "slug": "", "src": "ledger",
                    "kind": clean(word or "OPEN", 20), "text": clean(f"{finding}. Risk or $: {risk}. Status: {status}", 1200)})
    out.sort(key=lambda r: r["date"], reverse=True)
    return out


def decide():
    try:
        d = json.load(open(DECIDE, encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for it in d.get("items") or []:
        st = str(it.get("status") or "open").lower()
        if st not in ("open", "later", ""):
            continue
        out.append({"id": clean(it.get("id"), 60), "title": clean(it.get("question") or it.get("id"), 140), "line": first_sentence(it.get("why"), 180),
                    "usd_month": it.get("usd_month") if isinstance(it.get("usd_month"), (int, float)) else per_month(it.get("impact")),
                    "recommend": clean(it.get("recommend"), 40), "status": st, "added": clean(it.get("added"), 10), "slug": "",
                    "text": clean(f"{it.get('question') or ''} {it.get('why') or ''} {it.get('impact') or ''} "
                                  f"Recommended: {it.get('recommend') or '-'}. {it.get('recommend_why') or ''}", 1400), "src": "decide"})
    return out


def works():
    """The live strategies: real trades (src live) and the 2026 backtest $ a month (src backtest) from trades.json."""
    try:
        d = json.load(open(TRADES, encoding="utf-8"))
    except (OSError, ValueError):
        return []
    T = d.get("trades") or []
    out = []
    for bot, (name, acct, slug_hint) in LIVE.items():
        live = [t for t in T if t.get("bot") == bot and t.get("src") == "live"]
        bt = [t for t in T if t.get("bot") == bot and t.get("src") == "backtest" and str(t.get("day", "")) >= "2026-01-01"]
        months = sorted({str(t["day"])[:7] for t in bt})
        bt_usd = sum(float(t.get("usd") or 0) for t in bt)
        pm = round(bt_usd / len(months)) if months else None
        real = round(sum(float(t.get("usd") or 0) for t in live))
        since = min((t["day"] for t in live), default="")
        wins = sum(1 for t in live if float(t.get("usd") or 0) > 0)
        line = (f"Backtest 2026: {money(pm)} a month ({len(bt)} trades). Real so far: {len(live)} trades, {money(real, True)}"
                + (f" since {since}." if since else "."))
        out.append({"title": name, "bot": bot, "usd_month": pm, "real_usd": real, "real_n": len(live), "real_wins": wins, "since": since,
                    "line": clean(line, 180), "slug": slug_hint if os.path.exists(os.path.join(WRITEUPS, slug_hint + ".md")) else "",
                    "text": clean(line + " Real trades are the account's own fills; the backtest is the same rules on stored 2026 bars, costs in. "
                                  "Past trades, not a promise.", 600), "src": "live"})
    return out


def money(v, sign=False):
    if v is None:
        return "$0"
    a = abs(round(v))
    s = ("-" if v < 0 and a else ("+" if sign and v > 0 and a else "")) + "$" + f"{a:,}"
    return s


def lab():
    n = len(glob.glob(os.path.join(LAB, "*.json")))
    light = None
    try:
        e = json.load(open(os.path.join(LAB, "edge_health.json"), encoding="utf-8"))
        now = (e.get("light") or {}).get("now") or {}
        light = {"lit": clean(now.get("light"), 10), "day": clean(now.get("day"), 10), "r_week": now.get("r_week")}
        an = ((e.get("atlas") or {}).get("light") or {}).get("now") or {}
        light["atlas"] = clean(an.get("light"), 10)
    except (OSError, ValueError, AttributeError):
        pass
    return {"files": n, "edge_light": light}


# ------------------------------------------------------------------------------------------------ build
def build():
    W = writeups()
    stems = {w["stem"] for w in W}
    tested = tested_and_rejected(stems)
    linked = {r["slug"] for r in tested if r["slug"]}
    rej_w = [{"title": w["title"], "date": w["date"], "line": first_sentence(w["summary"] or w["status"], 180), "usd_month": w["usd_month"], "slug": w["slug"], "text": w["summary"], "src": "writeup", "family": w["family"]}
             for w in W if group_of(w["status"]) == "rejected" and w["slug"] not in linked]
    fam_of = {w["slug"]: w["family"] for w in W}
    for r in tested:
        r["family"] = fam_guess(fam_of.get(r["slug"], "other"), r["title"], r["text"])
    rejected = sorted(tested + rej_w, key=lambda r: r["date"], reverse=True)
    leads_w = [{"title": w["title"], "date": w["date"], "line": first_sentence(w["summary"] or w["status"], 180), "usd_month": w["usd_month"],
                "slug": w["slug"], "text": w["summary"], "src": "writeup", "kind": "PAPER LEAD", "family": w["family"]}
               for w in W if group_of(w["status"]) == "promising"]
    leads = leads_w + ledger()
    leads.sort(key=lambda r: r["date"], reverse=True)
    hub = {"v": 1, "built": dt.date.today().isoformat(),
           "about": "Research Hub: what works now, what was tried and rejected, open leads, money decisions waiting. Built by "
                    "tools/research_hub.py from the repo's research files. Past trades, not a promise.",
           "works": works(), "rejected": rejected, "leads": leads, "decide": decide(),
           "writeups": [{k: w[k] for k in ("slug", "title", "date", "family", "status", "summary", "usd_month")} for w in W],
           "lab": lab()}
    hub["counts"] = {k: len(hub[k]) for k in ("works", "rejected", "leads", "decide", "writeups")}
    return hub


def item_id(tab: str, r: dict) -> str:
    """Stable id: <status>-<write-up slug or slugified title> (+ the date when there is no write-up), <= 90 chars."""
    if tab == "works":
        return "live-" + {"LIT": "zlarior"}.get(r.get("bot"), slugify(r.get("bot") or r["title"]))
    base = r.get("slug") or slugify((r.get("id") or r.get("bot") or r.get("title") or "item") + ("-" + r["date"] if r.get("date") and not r.get("slug") else ""))
    return f"{STATUS_OF[tab]}-{base}"[:90]


def flat(hub: dict) -> dict:
    """tools/web_public/research/hub.json: one record per hub item for the Cities district.
    {id, title, family, status live|lead|rejected|decide, usd_month, date, summary, url}; url = the rendered write-up in Clio
    (../clio/?read=<slug>) or the item itself (../clio/?item=<id>)."""
    items, seen = [], set()
    for tab in ("works", "decide", "leads", "rejected"):
        for r in hub[tab]:
            i = item_id(tab, r)
            k, n = i, 2
            while k in seen:
                k, n = f"{i}-{n}", n + 1
            seen.add(k)
            r["id"] = k                                    # the Clio hub row carries the same id (the city's ?fly=<id>)
            if tab == "works":
                r["family"] = {"LIT": "lit", "ATLAS": "atlas"}.get(r.get("bot"), "other")
            elif r.get("src") == "ledger":                    # findings on the bots / pages: their own street unless Kalshi
                r["family"] = "kalshi" if re.search(GUESS[0][1], (r["title"] + " " + r.get("text", "")).lower()) else "ops"
            else:
                r["family"] = fam_guess(r.get("family"), r["title"], r.get("line"), r.get("text"))
            items.append({"id": k, "title": r["title"], "family": r["family"], "status": STATUS_OF[tab],
                          "usd_month": r.get("usd_month"), "date": r.get("date") or r.get("since") or "", "summary": r.get("line") or "",
                          "url": f"../clio/?read={r['slug']}" if r.get("slug") else f"../clio/?item={k}"})
    FOLD = {"targets": "management", "stops": "management", "bias": "filters", "timing": "sessions", "data": "ops", "baseline": "lit"}
    for x in items:                                        # a street needs 4+ items: fold the tiny families into their neighbours
        x["family"] = FOLD.get(x["family"], x["family"])
    return {"v": 1, "built": hub["built"], "schema": "id, title, family, status (live | lead | rejected | decide), usd_month (null = none quoted), "
                                                    "date (YYYY-MM-DD or ''), summary (one plain line), url (the rendered write-up in Clio)",
            "counts": dict(collections.Counter(x["status"] for x in items)), "items": items}


def privacy_findings(blob: str):
    return [f for f in SP.scan_text(blob, "clio/hub.json") if f.get("kind") not in ("note",)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--flat-out", default=None, help="the flat Cities file (default tools/web_public/research/hub.json with the default --out)")
    a = ap.parse_args(argv)
    hub = build()
    fl = flat(hub)                                         # also stamps r["id"] on the hub rows
    blob = json.dumps(hub, separators=(",", ":"), ensure_ascii=False)
    blob2 = json.dumps(fl, separators=(",", ":"), ensure_ascii=False)
    bad = privacy_findings(blob) + privacy_findings(blob2)
    print("research hub:", hub["counts"], f"{len(blob) / 1024:.0f} KB", "privacy findings:", len(bad))
    if bad:
        for f in bad[:10]:
            print("  PRIVATE?", f)
        return 2
    if not a.check:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(blob)
        print("wrote", os.path.relpath(a.out, ROOT))
        if a.out == OUT or a.flat_out:
            fo = a.flat_out or OUT_FLAT
            os.makedirs(os.path.dirname(fo), exist_ok=True)
            with open(fo, "w", encoding="utf-8") as fh:
                fh.write(blob2)
            print("wrote", os.path.relpath(fo, ROOT), fl["counts"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
