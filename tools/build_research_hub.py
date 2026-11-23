#!/usr/bin/env python3
"""RESEARCH HUB v2 data (night-hub2 2026-11-22): every piece of trading research in one phone page (tools/web_public/cities/hub.html).

    python tools/build_research_hub.py            write tools/web_public/cities/hub-data.json
    python tools/build_research_hub.py --check    exit 1 when the committed JSON is stale (no write)

Sources (read only; nothing is fetched, nothing live is touched):
  research/writeups/*.md                     every study = one card (front matter title / family / date / status / summary;
                                             a write-up without front matter: its # title and first paragraph)
  tools/web_public/business/decisions.json   the Decide cards: open / later = 'Waiting on you'; yes / no answers colour the study
  tools/web_public/business/accounts.json    what is live now (account, plan, stage, bots)
  tools/web_public/business/fleet_plan.json  the accounts' plan (next buy)
  tools/web_public/cities/brain-data.json    adopted ledger findings that name a write-up (mint); the brain's neuron count
  STATE.md                                   the keep-alive line
  docs/TESTED_AND_REJECTED.md, research/findings/LEDGER.md   counts only (the Brain shows every bullet)

Output (one small JSON; privacy-masked with tools/research_hub.clean = tools/site_privacy masks):
  { v, built, fam: [...], live: [ {k, t, s, src} ], wait: [ {id, q, jj, jo, rf, rec, src} ], hunt: {head, lines: [ {k, t, src} ]},
    cards: [ {s, t, d, f, v, m, x} ], counts: {...} }
  card: s = site slug (../clio/?read=<s> opens the write-up), t = title, d = date, f = family index, v = 'a' adopted / 'r' rejected /
        'o' open, m = the headline $ line pulled from the summary ('' = no $ figure), x = the summary (search + the open card)
Every $ / number in the live strip and the edge-hunt lines is checked against its source file here (build fails if one is missing).
Stdlib + tools/research_hub (parsers) only.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import research_hub as R  # noqa: E402

WRITEUPS = os.path.join(ROOT, "research", "writeups")
BIZ = os.path.join(ROOT, "tools", "web_public", "business")
DECIDE = os.path.join(BIZ, "decisions.json")
ACCOUNTS = os.path.join(BIZ, "accounts.json")
FLEET = os.path.join(BIZ, "fleet_plan.json")
BRAIN = os.path.join(ROOT, "tools", "web_public", "cities", "brain-data.json")
STATE = os.path.join(ROOT, "STATE.md")
TAR = os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md")
LEDGER = os.path.join(ROOT, "research", "findings", "LEDGER.md")
OUT = os.path.join(ROOT, "tools", "web_public", "cities", "hub-data.json")

FAMILIES = ["LIT", "ATLAS", "Rapid + fleet money", "Kalshi", "Websites", "Ops"]
# first match wins; title-only rules first (the summary of a trading study often says 'lead' or 'site')
TITLE_RULES = [
    (3, r"\bkalshi\b|prediction market|\bk[1-9]\b"),
    (4, r"website|web business|agency|cold.?call|rank.and.rent|pay.per.job|\bcaller\b|\bseo\b|\bclients?\b|\boutreach\b|\bleads? list"),
    (5, r"security|\btax(es)?\b|disk|auto.?update|privacy|\bvoice\b|jarvis|dashboard|phone (qa|site)|notification|bot gap|\bops\b|\bpc\b setup"),
    (0, r"edge hunt|\bedge2?\b|\bnq\b|regime guard"),
    (2, r"\brapid\b|\bfleet\b|payout|money|mffu|\beval|funded|prop firm|\baccounts?\b|lucid|budget|\bplan[s -]|one account|builder|tradeify|apex|topstep"),
    (1, r"\batlas\b|\bsecond\b|\bblitz\b|third strategy"),
]
FM_FAMILY = {"kalshi": 3, "money": 2, "second": 1, "product": 5}
REJ = re.compile(r"^\W*(rejected|reject\b|no winner|nothing\b|no change|no rule|no adopt|no switch|no new|dead\b|refuted|not adopted)|\b0 of \d+ (pass|variant)", re.I)
ADO = re.compile(r"^\W*(adopted|live\b|shipped)", re.I)
MONEY = re.compile(r"[-+−]?\$\s?\d[\d,]*(?:\.\d+)?k?")
PM = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?k?(?:\s*/\s*[-+]?\$\s?\d[\d,]*(?:\.\d+)?k?)*\s*(?:a month|/\s*mo(?:nth)?\b|per month|a mo\b)", re.I)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def family(title: str, fm_family: str, summary: str) -> int:
    t = title.lower()
    for f, rx in TITLE_RULES:
        if re.search(rx, t):
            return f
    if fm_family in FM_FAMILY:
        return FM_FAMILY[fm_family]
    s = summary.lower()
    if re.search(r"\bkalshi\b", s):
        return 3
    if re.search(r"\batlas\b|\bblitz\b", s) and not re.search(r"\blit\b|zlarior", s):
        return 1
    return 0


def first_para(body: str) -> str:
    """a write-up without front matter: the first paragraph under the # title (the headline paragraph)."""
    for block in re.split(r"\n\s*\n", body):
        b = block.strip()
        if b and not b.startswith("#") and not b.startswith("|"):
            return b
    return ""


def headline(summary: str) -> str:
    """the one-line $ result: the clause of the summary with the first '$ ... a month' (else the first $), never invented."""
    if not MONEY.search(summary):
        return ""
    parts = [p.strip() for p in re.split(r"(?<=[.;])\s+|\s+-\s+|\s+—\s+", summary) if p.strip()]
    pick = next((p for p in parts if PM.search(p)), None) or next((p for p in parts if MONEY.search(p)), "")
    pick = pick.rstrip(" .;")
    if len(pick) > 150:      # keep the $ in view: start a little before it, at a word
        m = PM.search(pick) or MONEY.search(pick)
        a = max(0, m.start() - 60)
        a = pick.rfind(" ", 0, a) + 1 if a else 0
        pick = ("…" if a else "") + pick[a:]
        if len(pick) > 150:
            pick = pick[:150].rsplit(" ", 1)[0].rstrip(" ,;:(-") + "…"
    return pick


def num_tokens(text: str):
    """every $ amount and plain number in a curated line, normalised (for the 'numbers come from files' check)."""
    out = []
    for m in re.finditer(r"\$\s?\d[\d,]*(?:\.\d+)?k?|\b\d[\d,]*(?:\.\d+)?%?", text):
        tok = m.group(0).replace(" ", "")
        if re.fullmatch(r"20\d\d|20\d\d-\d\d-\d\d|\d", tok) or re.fullmatch(r"\d{1,2}", tok) and int(tok) <= 12:
            continue      # years, single digits, small counts (2 accounts, 3 Lucid) are words here, not results
        out.append(tok)
    return out


def missing_numbers(text: str, src_text: str):
    flat = src_text.replace(" ", "")
    return [t for t in num_tokens(text) if t not in flat]


def cur(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


# ------------------------------------------------------------------------------------------------ the sections
def cards():
    dec = json.loads(read(DECIDE))["items"]
    by_src = {}
    for c in dec:
        stem = os.path.splitext(os.path.basename(c.get("source") or ""))[0].lower()
        if stem:
            by_src.setdefault(stem, []).append(c.get("status"))
    adopted_ledger = set()
    try:
        for n in json.loads(read(BRAIN))["n"]:
            if n.get("s") == "a" and n.get("w"):
                adopted_ledger.add(n["w"].lower())
    except (OSError, ValueError, KeyError):
        pass
    out = []
    for w in R.writeups():
        path = os.path.join(WRITEUPS, w["stem"] + ".md")
        if not os.path.exists(path):          # stems are lower-cased by the parser: find the real file
            hits = [f for f in os.listdir(WRITEUPS) if f.lower() == w["stem"] + ".md"]
            if not hits:
                continue
            path = os.path.join(WRITEUPS, hits[0])
        raw = read(path)
        meta, body = R.front(raw)
        summary = w["summary"] or R.clean(first_para(body), 420)
        st = w["status"]
        answers = by_src.get(w["stem"], [])
        if any(a in ("yes", "done") for a in answers) or ADO.search(st) or w["stem"] in adopted_ledger:
            v = "a"
        elif (answers and all(a == "no" for a in answers)) or REJ.search(st) or (not meta and REJ.search(summary)):
            v = "r"
        else:
            v = "o"
        if not meta and re.search(r"\b(no winner|nothing wins|0 pass|nothing passes)\b", summary, re.I):
            v = "r"
        raw_sum = (meta.get("summary") or first_para(body)).replace("->", "→").replace("<=", "≤").replace(">=", "≥").replace("<", "under ").replace(">", "over ")
        out.append({"s": w["slug"], "t": w["title"], "d": w["date"], "f": family(w["title"], (meta.get("family") or "").lower(), summary),
                    "v": v, "m": R.clean(headline(R.clean(raw_sum, 4000)), 170), "x": R.clean(summary, 300), "_src": cur(path)})
    out.sort(key=lambda c: (c["d"], c["t"]), reverse=True)
    return out


def money_line(c):
    by = c.get("usd_month_by") or {}
    def f(v):
        return ("+" if v > 0 else "-" if v < 0 else "") + "${:,.0f}".format(abs(v))
    if by.get("jan_jun") is not None and by.get("jul_oct") is not None:
        return f"{f(by['jan_jun'])} / {f(by['jul_oct'])} a month (Jan-Jun / Jul-Oct-like)"
    if c.get("usd_month") is not None:
        return f"{f(c['usd_month'])} a month"
    return "no $ figure"


def waiting():
    out = []
    for c in json.loads(read(DECIDE))["items"]:
        if c.get("status") not in ("open", "later"):
            continue
        src = os.path.splitext(os.path.basename(c.get("source") or ""))[0]
        out.append({"id": c["id"], "q": R.clean(c.get("question"), 200), "m": money_line(c), "st": c["status"],
                    "rec": (c.get("recommend") or "").lower(), "s": R.slugify(src) if src and os.path.exists(os.path.join(WRITEUPS, src + ".md")) else ""})
    out.sort(key=lambda r: (r["st"] != "open", -abs(next((x["usd_month"] for x in json.loads(read(DECIDE))["items"] if x["id"] == r["id"]), 0) or 0)))
    return out


def live():
    acc = json.loads(read(ACCOUNTS))
    by = {a["key"]: a for a in acc["accounts"]}
    rows = []
    word = {"live": "LIVE", "buying": "BOUGHT, being added", "plan": "PLAN"}
    for key, label in (("zlarior", "Zlarior (LIT)"), ("atlas", "ATLAS"), ("fresh25", "Zlarior 25K #2"), ("rapid1", "Rapid EOD 25K")):
        a = by.get(key)
        if not a:
            continue
        s = word.get(a.get("status"), (a.get("status") or "").upper())
        rows.append({"k": label, "s": s, "t": R.clean(f"{a['plan']} · {a['stage']} · runs {a['bots']}".replace("<=", "≤").replace(">=", "≥"), 170), "src": cur(ACCOUNTS)})
    st = read(STATE)
    ka = "Keep-alive (one tiny trade so MFFU's 7-day no-trade close never hits): built, OFF per account; you switch it on (TRADE_HOME.bat, option 3)"
    if "keep-alive" in st.lower() and "OFF per account" in st and "3 Keep-alive on" in st:
        rows.append({"k": "Keep-alive", "s": "OFF until you", "t": ka, "src": "STATE.md"})
    fl = json.loads(read(FLEET))
    nb = fl.get("next_buy") or {}
    if nb.get("what"):
        rows.append({"k": "The accounts' plan", "s": "PLAN", "t": R.clean(f"Next buy: {nb['what']} (${nb['price']:,.0f}, code {nb.get('code', '')}) about {nb['when']}, paid from {nb['from']}", 170), "src": cur(FLEET)})
    rows.append({"k": "BLITZ / Kalshi", "s": "PAPER", "t": "BLITZ stays hidden on paper; Kalshi K8 is paper until you start it", "src": "STATE.md"})
    return rows


HUNT_SRC = "research/writeups/"
HUNT = [
    ("A · session", "edge-a-session-2026-11-22", "No winner: 14 variants, 0 positive in both 2026 halves (trend ones won Jan-Jun and lost Jul-Oct: a regime flip, not an edge)"),
    ("B · cross-asset", "edge-b-cross-2026-11-22", "No winner: 128 variants (dealer gamma, VIX term structure, ES/NQ strength). One paper lead, opposite sign, t < 1.2, about $230 a month"),
    ("C · calendar", "edge-c-calendar-2026-11-22", "Nothing wins: 174 variants, 0 pass (Monday long is a lottery ticket: its top 3 trades are the whole net)"),
    ("D · meta-label", "edge-d-meta-2026-11-22", "Rejected: 31 versions of size and re-entry rules on LIT's signals; the one that clears money is leverage, not skill"),
    ("E · one account", "one-account-book-2026-11-22", "The lever is the ACCOUNT TYPE: an MFFU Rapid EOD 50K ($165) with LIT + ATLAS, LIT half size in the eval = $4,918 / $2,204 / -$88 a month (Jan-Jun / Jul-Oct / 2021-25-like) vs today's two accounts $981 / $857 / -$62. Worse in 2021-25, so no new card"),
    ("Fleet v2", "fleet-v2-2026-11-22", "LucidPro 50K adds nothing at a $300 budget; $500 + 3 Lucid = $14.1k / $9.7k a month vs the $300 plan $12.3k / $7.5k (Lucid price $126 assumed). Card lucid-3-at-500-budget, later"),
    ("Rapid 25K slot", "rapid25-slot-2026-11-22", "Today's LIT + ATLAS on the 25K stays ($1,883 / $800 a month); a Rapid EOD 50K in the slot makes $5,001 / $2,281 but loses $560 in a 2021-25-like market: no new card"),
]


def hunt():
    lines = []
    for k, stem, text in HUNT:
        p = os.path.join(WRITEUPS, stem + ".md")
        miss = missing_numbers(text, read(p))
        if miss:
            raise SystemExit(f"build_research_hub: '{k}' quotes {miss} that {cur(p)} does not have")
        lines.append({"k": k, "t": text, "s": R.slugify(stem), "src": cur(p)})
    return {"date": "2026-11-22", "head": "0 new edges tonight. Lanes A-D tried 347 variants (14 + 128 + 174 + 31): none beat costs in both 2026 halves and 2021-25. Lane E (53 one-account books) found the money lever is the account type: a Rapid EOD 50K.",
            "lines": lines}


def build():
    cs = cards()
    w = waiting()
    h = hunt()
    tar_n = sum(1 for ln in read(TAR).split("\n") if ln.startswith("- "))
    led_n = sum(1 for ln in read(LEDGER).split("\n") if re.match(r"\|\s*\d{4}-\d\d-\d\d", ln))
    try:
        neurons = len(json.loads(read(BRAIN))["n"])
    except (OSError, ValueError, KeyError):
        neurons = 0
    for c in cs:
        c.pop("_src", None)
    built = max([c["d"] for c in cs if c["d"]] + [json.loads(read(DECIDE)).get("updated", "")])
    return {"v": 1, "built": built, "fam": FAMILIES, "live": live(), "wait": w, "hunt": h, "cards": cs,
            "counts": {"studies": len(cs), "adopted": sum(c["v"] == "a" for c in cs), "rejected": sum(c["v"] == "r" for c in cs),
                       "open": sum(c["v"] == "o" for c in cs), "waiting": len(w), "rejected_list": tar_n, "ledger": led_n, "neurons": neurons}}


def dump(h) -> str:
    return json.dumps(h, ensure_ascii=False, separators=(",", ":")) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = dump(build())
    if "--check" in argv:
        try:
            old = read(OUT)
        except OSError:
            old = ""
        if old != text:
            print("hub-data.json is STALE: run python tools/build_research_hub.py")
            return 1
        print("hub-data.json is fresh")
        return 0
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {cur(OUT)} ({len(text.encode()) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
