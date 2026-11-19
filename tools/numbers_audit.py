"""Numbers audit (2026-11-04): wrong money numbers are the costliest bug we can ship, so this finds them.

READ-ONLY. It builds the key facts from the sources of truth, then scans every PUBLISHED file for the same facts written differently (a list
price where the owner's real price belongs, an old funded figure, an old headline, an old count) and prints one table:
    severity | file | line | found | expected | rule

  python tools/numbers_audit.py            the table (wrong + warn), the facts it checked against
  python tools/numbers_audit.py --check    exit 1 when any 'wrong' finding is left (a gate for the site build / the tests)
  python tools/numbers_audit.py --all      also the 'ok' lines that were skipped on purpose (a number in a sentence about the past)
  python tools/numbers_audit.py --json     machine-readable
  python tools/numbers_audit.py --root DIR audit another tree (the test uses a small synthetic one)

Sources of truth (a missing one is itself reported):
  CLAUDE.md                              the owner's real prices, the headline (2026 PF / net, the H2 check rate)
  research/lit/mffu_rules.json           the MFFU Builder 50K / 25K numbers (target, max loss, floor, daily loss, payouts, split, list prices)
  research/props/roadmap.json            the prices used in the plans, the published 2-week pass / fail
  research/lit/funded_firms.json         the funded $ a month of every combination (the trio: Builder 50K + LucidPro 50K + FundedNext Rapid Daily 50K)
  tools/web_public/plutus/plans.json     the per-account funded $ a month (the Plutus app's own copy of the study)
  tools/web_public/bridge/jobs.json + index.html (job counts), tools/web_public/jarvis/apps.js (app count)

'wrong'  = certain: a superseded figure, a list price as the owner's price, a figure that contradicts a source. Fix it.
'warn'   = differs from the source but may be about something else (another firm, another account): a person looks.
Lines about the past ("was", "up from", "before", "old") are 'ok': history is not an error.
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_EXT = {".html", ".htm", ".js", ".mjs", ".json", ".md", ".txt", ".css", ".webmanifest", ".xml"}
SKIP_PARTS = {"node_modules", "__pycache__", ".git"}
MAX_BYTES = 8 * 1024 * 1024
HISTORY = re.compile(r"\b(was|were|old|older|before|previous|previously|used to|up from|down from|instead of|until|replaced|no longer|stale|superseded|earlier|formerly|last run)\b", re.I)
FULL_BRIEF = "## The full brief (CLAUDE.md as it was"          # CLAUDE_REFERENCE.md's last section: the long brief, moved there 2026-11-15
OWNER_DOCS_SKIP = {"CLAUDE_REFERENCE.md"}
# the Archive app is the library of every run ever made (each row dated, "live" there is a run's label): an old headline / trio figure in
# it is a dated result to look at ('warn'), never the current headline ('wrong'); certain errors (list prices, limits, counts) stay 'wrong'
HISTORY_PATHS = ("tools/web_public/archive/",)
HISTORY_RULES = {"old-headline", "old-trio", "trio-month"}                 # Claude's own map and history: full of old numbers on purpose, never shown to the owner


# ------------------------------------------------------------------------------------------------ the facts
def _json(root, rel):
    try:
        with open(os.path.join(root, *rel.split("/")), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _text(root, rel):
    try:
        with open(os.path.join(root, *rel.split("/")), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def money(s):
    return float(str(s).replace(",", "").replace("$", ""))


def load_facts(root: str = ROOT) -> dict:
    """The facts every published number is checked against, each with where it came from. Never raises; a missing source goes in facts['missing']."""
    F = {"missing": [], "sources": {}, "conflicts": []}
    claude = _text(root, "CLAUDE.md")
    brief = claude
    if claude is not None:                              # the brief was cut to one page on 2026-11-15: its long form (word for word) is the last
        ref = _text(root, "docs/CLAUDE_REFERENCE.md") or ""   # section of CLAUDE_REFERENCE.md; a fact not in the short brief is read from there
        i = ref.find(FULL_BRIEF)
        brief = claude + ("\n" + ref[i:] if i >= 0 else "")
    rules = _json(root, "research/lit/mffu_rules.json")
    road = _json(root, "research/props/roadmap.json")
    firms = _json(root, "research/lit/funded_firms.json")
    plans = _json(root, "tools/web_public/plutus/plans.json")
    jobs = _json(root, "tools/web_public/bridge/jobs.json")
    for name, v in (("CLAUDE.md", claude), ("research/lit/mffu_rules.json", rules), ("research/props/roadmap.json", road), ("research/lit/funded_firms.json", firms),
                    ("tools/web_public/plutus/plans.json", plans)):
        if v is None:
            F["missing"].append(name)
    # prices: the owner's real ones (CLAUDE.md hard rules), cross-checked against the three data files
    price = {}
    if claude:
        # the one-page brief says "Builder 50K $91.80, 25K $63 / $43" (the Builder 25K, then the ATLAS 25K); the long form names each one
        short = re.search(r"Builder 50K \$(\d+(?:\.\d+)?), 25K \$(\d+(?:\.\d+)?) / \$(\d+(?:\.\d+)?)", claude)
        m = re.search(r"Builder 25K \$(\d+(?:\.\d+)?)", brief)
        price["b25"] = float(short.group(2)) if short else (float(m.group(1)) if m else None)
        m = re.search(r"ATLAS 25K[^$]{0,40}\$(\d+(?:\.\d+)?)", brief)
        price["atlas25"] = float(short.group(3)) if short else (float(m.group(1)) if m else None)
        m = re.search(r"Builder 50K \$(\d+(?:\.\d+)?)", brief)
        price["b50"] = float(m.group(1)) if m else None
        price["activation"] = 0.0 if re.search(r"\$0 activation", brief) else None
    F["price"] = price
    if road and "prices" in road:
        for k, key in (("L50", "b50"), ("L25", "b25"), ("A25", "atlas25")):
            if price.get(key) is not None and road["prices"].get(k) is not None and abs(float(road["prices"][k]) - price[key]) > 0.005:
                F["conflicts"].append(("research/props/roadmap.json", f"price {k}", road["prices"][k], price[key]))
    if firms:
        pid = {p["id"]: p for p in firms.get("plans", [])}
        for pk, key in (("mffu_builder_50k", "b50"), ("mffu_builder_25k", "b25")):
            if pk in pid and price.get(key) is not None and abs(float(pid[pk]["price"]) - price[key]) > 0.005:
                F["conflicts"].append(("research/lit/funded_firms.json", f"price {pk}", pid[pk]["price"], price[key]))
    # MFFU Builder numbers
    lim = (rules or {}).get("limits", {})
    F["b50"], F["b25"] = lim.get("builder_50k", {}), lim.get("builder_25k", {})
    if F["b50"]:
        F["b50"] = dict(F["b50"], floor=50000 - F["b50"]["mll"], lock_level=50000 + F["b50"]["lock"])
    if F["b25"]:
        F["b25"] = dict(F["b25"], floor=25000 - F["b25"]["mll"], lock_level=25000 + F["b25"]["lock"])
    try:
        lp = rules["builder_50k"]["eval"]["price"]["value"]
        F["list"] = {"b50": float(lp["list"]), "b50_addon": float(lp.get("list_addon_1500_mll", 0) or 0), "b50_owner": float(lp["owner_paid"])}
    except (KeyError, TypeError):
        F["list"] = {}
    if plans:
        for p in plans.get("plans", []):
            if p.get("id") == "mffu_builder_25k":
                F["list"]["b25"] = float(p.get("list_price", 0) or 0)
            if p.get("id") == "mffu_builder_50k":
                F["list"].setdefault("b50", float(p.get("list_price", 0) or 0))
    # the 2-week pass / fail (published) and the funded $ a month
    F["pass_2w"] = (road or {}).get("published_pass_2w", {})
    trio = {}
    if firms:
        want = {"mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k"}
        for c in firms.get("combos", []):
            if set(c.get("plans", [])) == want and len(c["plans"]) == 3:
                trio[c["span"]] = {"per_month": int(round(c["net_per_month"])), "months4_6": int(round(c["months4_6_per_month"])), "neg_6m": c.get("neg_6m")}
    F["trio"] = trio
    per = {}
    if plans:
        for p in plans.get("plans", []):
            per[p["id"]] = {sp: p["spans"][sp].get("funded_per_month") for sp in p.get("spans", {})}
        pt = plans.get("trio", {})
        for sp, v in pt.items():
            if sp in trio and v.get("net_per_month") is not None and int(round(v["net_per_month"])) != trio[sp]["per_month"]:
                F["conflicts"].append(("tools/web_public/plutus/plans.json", f"trio {sp} per month", v["net_per_month"], trio[sp]["per_month"]))
    F["per_account"] = per
    # the headline: CLAUDE.md
    head = {}
    if claude:
        m = re.search(r"\*\*Headline[^\n]*?2026 PF (\d\.\d\d), \+\$([\d,]+)", brief)
        if m:
            head["pf_2026"], head["net_2026"] = float(m.group(1)), int(money(m.group(2)))
        m = re.search(r"H2 check rate: PF (\d\.\d\d), \+\$([\d,]+) \(~\$([\d,]+)/mo\)", brief)
        if m:
            head["pf_h2"], head["net_h2"], head["pm_h2"] = float(m.group(1)), int(money(m.group(2))), int(money(m.group(3)))
        m = re.search(r"funded 60% of room, <= \$([\d,]+), winner <= \$([\d,]+)", brief)
        if m:
            head["funded_cap"], head["winner_cap"] = int(money(m.group(1))), int(money(m.group(2)))
    F["headline"] = head
    for k in ("pf_2026", "net_2026", "pf_h2", "net_h2", "pm_h2"):
        if k not in head and claude is not None:
            F["missing"].append(f"CLAUDE.md headline {k}")
    # counts
    lib = (jobs or {}).get("jobs", [])
    page = _text(root, "tools/web_public/bridge/index.html") or ""
    cards = len(re.findall(r"\{ id: '[a-z0-9-]+', t:", page))
    F["jobs"] = {"library": len(lib), "cards": cards, "total": len(lib) + cards} if lib else {}
    apps = _text(root, "tools/web_public/jarvis/apps.js")
    F["apps"] = len(re.findall(r"\bapp\('", apps)) if apps else None
    return F


# ------------------------------------------------------------------------------------------------ the rules
def past(pre, post):
    """is this number about the past? a history word just before it ("up from $1,754", "was ...") or just after it ("$1,754 on the old trades")"""
    return bool(HISTORY.search(pre[-80:]) or re.match(r"[^.\n]{0,30}\b(?:old|older|before|previous|previously|earlier)\b", post, re.I))


def _near(ctx, *words):
    return any(re.search(w, ctx, re.I) for w in words)


def _fmt(n):
    return f"${n:,.2f}".rstrip("0").rstrip(".") if n % 1 else f"${int(n):,}"


def rules_for(F):
    """-> list of (rule id, compiled regex, function(match, ctx) -> (severity, found, expected) | None)"""
    R = []
    own50, own25 = F["price"].get("b50"), F["price"].get("b25")
    lst = F.get("list", {})
    t = F.get("trio", {})
    h2, h1 = t.get("H2"), t.get("H1")
    head = F.get("headline", {})
    trio_exp = (f"the trio makes {_fmt(h2['per_month'])} a month on Jul-Oct trades (H2, the number to quote; {_fmt(h2['months4_6'])} in months 4-6), "
                f"{_fmt(h1['per_month'])} on Jan-Jun") if h2 and h1 else "the trio's current $ a month (research/lit/funded_firms.json)"
    head_exp = (f"2026 PF {head.get('pf_2026')}, +${head.get('net_2026', 0):,}; H2 check rate PF {head.get('pf_h2')}, +${head.get('net_h2', 0):,} (~${head.get('pm_h2', 0):,}/mo)") if head else "the headline in CLAUDE.md"

    # 1. a list price where the owner's real price belongs
    def list_price(m, ctx, pre, post):
        v = m.group(1)
        own = own50 if v in ("153", "125") else own25 if v == "105" else None
        if own is not None and (_fmt(own) in ctx or f"{own:.2f}" in ctx):
            return None                                           # "$91.80 ($153)": the owner's price is right there
        if v in ("153", "125") and own50 and re.search(r"50\s?K", ctx) and _near(ctx, "Builder", "MFFU", "eval"):
            ok = _near(ctx, r"\blist\b", r"default", r"regular", r"full price", r"promo", r"add-?on", r"\bcode", r"discount", r"saving", r"\bvs\b", r"instead", r"retail", r"sticker", r"without", r"cheaper")
            return ("ok" if ok else "wrong", "$" + v, f"{_fmt(own50)} (the owner's real Builder 50K price), not the list price")
        if v == "105" and own25 and re.search(r"25\s?K", ctx) and _near(ctx, "Builder", "MFFU", "eval"):
            ok = _near(ctx, r"\blist\b", r"default", r"regular", r"full price", r"promo", r"add-?on", r"\bcode", r"discount", r"saving", r"\bvs\b", r"instead", r"retail", r"sticker", r"without", r"cheaper")
            return ("ok" if ok else "wrong", "$105", f"{_fmt(own25)} (the owner's real Builder 25K price), not the list price")
        return None
    R.append(("list-price", re.compile(r"\$\s?(153|125|105)(?:\.00)?(?![\d,.]*\d)"), list_price))

    # 2. old funded figures of the trio
    def old_trio(m, ctx, pre, post):
        v = m.group(1)
        if v == "2,315" and _near(ctx, r"\bDD\b", "drawdown", "max loss", r"[-−]\s?\$2,315"):
            return None                                           # the old 2026 max drawdown, a different number
        if not _near(ctx, "month", r"/mo\b", "funded", "payout", "trio", "FundedNext", "Lucid", r"\bnet\b"):
            return None
        return ("ok" if past(pre, post) else "wrong", "$" + v, trio_exp)
    R.append(("old-trio", re.compile(r"\$\s?(1,754|2,315|2,373|2,944)(?![\d,])"), old_trio))

    # 3. the trio's $ a month, any other number
    if h1 and h2:
        allowed = {h1["per_month"], h1["months4_6"], h2["per_month"], h2["months4_6"]}

        def trio_other(m, ctx, pre, post):
            sent = re.split(r"(?:\.\s|</p>|<p>|<br>|\n)", pre)[-1]                  # the sentence the number sits in
            if not _near(sent, "FundedNext") or not _near(sent, "Lucid"):
                return None
            v = int(money(m.group(1)))
            if v in allowed or v < 1000 or past(pre, post):
                return None
            sure = _near(sent, r"Builder 50K") and _near(sent, "LucidPro", "Lucid Pro") and _near(sent, r"FundedNext Rapid Daily")
            return ("wrong" if sure else "warn", "$" + m.group(1), trio_exp)
        R.append(("trio-month", re.compile(r"\$\s?(\d,\d{3})\s*(?:a|per|/)\s*(?:month|mo)\b"), trio_other))

    # 4. the old headline
    def old_head(m, ctx, pre, post):
        if not _near(ctx, "LIT", "2026", "H2", "headline", "PF", "the bot"):
            return None
        sure = _near(ctx, "headline", "quote", "current", r"\bnow\b", r"\blive\b", "today")     # a dated research result ("Together (litlosspack): 2026 +$41.7k, PF 3.66") is history, not the headline
        return ("ok" if past(pre, post) else "wrong" if sure else "warn", m.group(0).strip(), head_exp)
    R.append(("old-headline", re.compile(r"\+\$\s?41,734|\$4,254(?:\s*(?:/|a|per)\s*(?:mo|month))?|\bPF\s?3\.66\b|\+\$\s?8,962\b"), old_head))

    # 5. the old 2-week pass / fail of the 50K eval
    p2 = F.get("pass_2w", {}).get("L50", {})
    if p2:
        exp2 = f"{p2['H2']['pass']} / {p2['H2']['fail']} (H2) and {p2['H1']['pass']} / {p2['H1']['fail']} (H1) pass / fail in 2 weeks"

        def old_2w(m, ctx, pre, post):
            return ("ok" if past(pre, post) else "wrong", m.group(0), exp2)
        R.append(("old-2week", re.compile(r"\b53\.7\s*(?:%\s*)?/\s*2\.2\b"), old_2w))

    # 6. old eval wording: a day count the MFFU Builder eval does not have
    def old_days(m, ctx, pre, post):
        return ("ok" if past(pre, post) else "wrong", m.group(0), "no day-count rule: the Builder eval passes at the profit target (" + (_fmt(F["b50"].get("target", 3000)) if F.get("b50") else "$3,000") + "), trading days are not the test")
    R.append(("old-days", re.compile(r"\b7\s+(?:of|out of)\s+(?:the\s+)?(?:last\s+)?10\s+(?:trading\s+)?(?:days|sessions)\b", re.I), old_days))

    # 7. counts
    j = F.get("jobs", {})
    if j:
        okj = {j["library"], j["total"], j["cards"]}

        def jobs_count(m, ctx, pre, post):
            v = int(m.group(1))
            if v in okj or v < 20 or v > 400 or not _near(ctx, "ChatGPT", "Bridge", "library", "ready"):
                return None
            return ("ok" if past(pre, post) else "wrong", m.group(0), f"{j['library']} ready jobs in the library ({j['total']} with the {j['cards']} job cards)")
        R.append(("jobs-count", re.compile(r"\b(\d{2,3})\s+(?:ready(?:-made)?\s+)?(?:ChatGPT\s+)?jobs\b", re.I), jobs_count))
    if F.get("apps"):
        def app_count(m, ctx, pre, post):
            v = int(m.group(1))
            after = ctx[ctx.find(m.group(0)) + len(m.group(0)):][:3]
            if "//" in pre or "/*" in pre or pre.rstrip().endswith("~"):
                return None                                       # a code comment or an approximate count
            if v == F["apps"] or not 9 <= v <= 40 or not _near(ctx, "OLYMPUS", "Olympus", "Jarvis", "wired", "built-in", "hub") or after.startswith((" (", ":")):
                return None
            return ("ok" if past(pre, post) else "warn", m.group(0), f"{F['apps']} apps in jarvis/apps.js")
        R.append(("app-count", re.compile(r"\b(\d{1,2})\s+(?:built-in\s+|wired\s+|OLYMPUS\s+|Olympus\s+)*apps\b"), app_count))

    # 8. MFFU Builder numbers next to the words that name them
    b50, b25 = F.get("b50") or {}, F.get("b25") or {}

    def which(ctx):
        a, b = bool(re.search(r"50\s?K", ctx)), bool(re.search(r"25\s?K", ctx))
        return (b50, "50K") if a and not b else (b25, "25K") if b and not a else (None, None)

    def lim_rule(key, label):
        def f(m, ctx, pre, post):
            if not _near(ctx, "Builder", "MFFU"):
                return None
            lim, size = which(ctx)
            if not lim or key not in lim:
                return None
            v = money(m.group(1))
            known = {float(x) for k_, x in lim.items() if isinstance(x, (int, float)) and k_ in ("target", "mll", "lock", "dll", "floor", "lock_level", "buffer", "pay_min", "pay_max")}
            if abs(v - float(lim[key])) < 0.5 or v in known or past(pre, post):
                return None                                       # the right number, or another true MFFU figure that sits next to the phrase
            return ("wrong", "$" + m.group(1), f"{_fmt(float(lim[key]))} ({label} on the Builder {size})")
        return f
    R.append(("mffu-dll", re.compile(r"(?:daily loss(?: limit)?|\bDLL\b)[^$\n]{0,40}\$\s?(\d[\d,]*)(?![\d,]*\.\d)", re.I), lim_rule("dll", "daily loss limit")))
    R.append(("mffu-mll", re.compile(r"(?:max(?:imum)? loss|\bMLL\b|trailing (?:max )?(?:drawdown|loss))[^$\n]{0,40}\$\s?(\d[\d,]*)(?![\d,]*\.\d)", re.I), lim_rule("mll", "max loss")))
    R.append(("mffu-target", re.compile(r"profit target[^$\n]{0,30}\$\s?(\d[\d,]*)(?![\d,]*\.\d)", re.I), lim_rule("target", "profit target")))

    def payouts(m, ctx, pre, post):
        if not _near(ctx, "Builder", "MFFU") or past(pre, post):
            return None
        mp = (F.get("b50") or {}).get("max_payouts")
        return None if mp is None or int(m.group(1)) == mp else ("warn", m.group(0), f"{mp} payouts on the Builder")
    R.append(("mffu-payouts", re.compile(r"\b(\d{1,2})\s+payouts?\b", re.I), payouts))

    def split(m, ctx, pre, post):
        if not _near(ctx, "Builder", "MFFU") or past(pre, post) or not _near(ctx, "split", "you keep", "payout"):
            return None
        sp = (F.get("b50") or {}).get("split")
        return None if sp is None or int(m.group(1)) == round(sp * 100) else ("warn", m.group(0), f"{round(sp * 100)}% profit split on the Builder")
    R.append(("mffu-split", re.compile(r"\b(\d{2})\s?%\s*(?:profit\s+)?split\b|\bsplit\b[^%\n]{0,20}\b(\d{2})\s?%", re.I), lambda m, ctx, pre, post: split(_Alt(m), ctx, pre, post)))

    def activation(m, ctx, pre, post):
        v = m.group(1) or m.group(2)
        if not v or not _near(ctx, "MFFU", "Builder") or past(pre, post):
            return None
        if m.group(2) and re.search(r"\b\d{2,3}K\b|Builder|eval", m.group(0), re.I):
            return None                                           # "activation fees (Builder 50K $91.80, ...)": the $ after it is an eval's price
        return ("wrong", "$" + v + " activation", "$0 activation (one-time price, nothing else to pay)")
    R.append(("mffu-activation", re.compile(r"\$\s?([1-9]\d*)\s+activation|activation fee[^$\n]{0,20}\$\s?([1-9]\d*)", re.I), activation))
    return R


class _Alt:
    """a regex match whose number is in group 1 or 2 (the split rule has two spellings)"""
    def __init__(self, m):
        self.m = m

    def group(self, i=0):
        if i == 1:
            return self.m.group(1) or self.m.group(2)
        return self.m.group(i)


# ------------------------------------------------------------------------------------------------ which files are published
def published_files(root: str = ROOT):
    """every file a visitor or the owner can read: the site (tools/web_public), the next site (web_next), the hub snapshot, the docs the owner reads, handoff/, STRATEGY.md"""
    out = []

    def add_tree(rel):
        base = os.path.join(root, *rel.split("/"))
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in SKIP_PARTS]
            for fn in sorted(fns):
                out.append(os.path.join(dp, fn))
    add_tree("tools/web_public")
    add_tree("web_next")
    add_tree("handoff")
    docs = os.path.join(root, "docs")
    if os.path.isdir(docs):
        out += [os.path.join(docs, f) for f in sorted(os.listdir(docs)) if f.endswith(".md") and f not in OWNER_DOCS_SKIP]
    for rel in ("tools/web_hub_snapshot.json", "STRATEGY.md", "README.md"):
        p = os.path.join(root, *rel.split("/"))
        if os.path.isfile(p):
            out.append(p)
    seen, res = set(), []
    for p in out:
        if p in seen or os.path.splitext(p)[1].lower() not in TEXT_EXT:
            continue
        seen.add(p)
        try:
            if os.path.getsize(p) <= MAX_BYTES and not os.path.islink(p):
                res.append(p)
        except OSError:
            pass
    return res


# ------------------------------------------------------------------------------------------------ the scan
def scan_text(text: str, rules, rel: str) -> list:
    starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
    out = []
    for rid, rx, fn in rules:
        for m in rx.finditer(text):
            a, b = max(0, m.start() - 110), min(len(text), m.end() + 110)
            ctx = text[a:b]
            r = fn(m, ctx, text[max(0, m.start() - 150):m.start()], text[m.end():m.end() + 40])
            if not r:
                continue
            sev, found, exp = r
            if sev == "wrong" and rid in HISTORY_RULES and rel.startswith(HISTORY_PATHS):
                sev = "warn"
            out.append({"severity": sev, "file": rel, "line": bisect.bisect_right(starts, m.start()), "found": re.sub(r"\s+", " ", found)[:60], "expected": exp, "rule": rid,
                        "context": re.sub(r"\s+", " ", ctx)[:200]})
    return out


def audit(root: str = ROOT) -> dict:
    F = load_facts(root)
    rules = rules_for(F)
    findings = []
    for name in F["missing"]:
        findings.append({"severity": "warn", "file": name, "line": 0, "found": "source missing", "expected": "the source of truth", "rule": "source", "context": ""})
    for f, what, a, b in F["conflicts"]:
        findings.append({"severity": "wrong", "file": f, "line": 0, "found": f"{what} = {a}", "expected": f"{b} (CLAUDE.md / the other sources)", "rule": "sources-disagree", "context": ""})
    files = published_files(root)
    for p in files:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        findings += scan_text(text, rules, os.path.relpath(p, root).replace(os.sep, "/"))
    uniq, seen = [], set()
    for f in findings:                                    # one line per number (two rules can see the same figure)
        k = (f["file"], f["line"], f["found"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    findings = uniq
    order = {"wrong": 0, "warn": 1, "ok": 2}
    findings.sort(key=lambda f: (order.get(f["severity"], 3), f["file"], f["line"]))
    return {"facts": F, "files": len(files), "findings": findings}


def facts_lines(F):
    h, t, b50 = F.get("headline", {}), F.get("trio", {}), F.get("b50", {})
    L = [f"owner prices: Builder 50K {F['price'].get('b50')}, Builder 25K {F['price'].get('b25')}, ATLAS 25K {F['price'].get('atlas25')}, activation {F['price'].get('activation')}"]
    L.append(f"list prices (never the owner's): {F.get('list')}")
    if b50:
        L.append(f"MFFU Builder 50K: target {b50.get('target')}, max loss {b50.get('mll')} (floor {b50.get('floor')}, locks at {b50.get('lock_level')}), daily loss {b50.get('dll')}, "
                 f"{b50.get('max_payouts')} payouts, {round(b50.get('split', 0) * 100)}% split, buffer {b50.get('buffer')}")
    L.append(f"headline: {h}")
    L.append(f"2-week pass/fail (published): {F.get('pass_2w', {}).get('L50')}")
    L.append(f"funded trio per month: {t}")
    L.append(f"per account funded $/month (Builder 50K): {F.get('per_account', {}).get('mffu_builder_50k')}")
    L.append(f"counts: jobs {F.get('jobs')}, apps {F.get('apps')}")
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description="find wrong money numbers in published files")
    ap.add_argument("--check", action="store_true", help="exit 1 when any 'wrong' finding is left")
    ap.add_argument("--all", action="store_true", help="also show the 'ok' lines (history)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=ROOT)
    a = ap.parse_args(argv)
    res = audit(a.root)
    shown = [f for f in res["findings"] if a.all or f["severity"] != "ok"]
    bad = [f for f in res["findings"] if f["severity"] == "wrong"]
    if a.json:
        print(json.dumps({"files": res["files"], "wrong": len(bad), "findings": shown}, indent=1))
    else:
        print("FACTS")
        for l in facts_lines(res["facts"]):
            print("  " + l)
        print(f"\nscanned {res['files']} published files: {len(bad)} wrong, {sum(1 for f in res['findings'] if f['severity'] == 'warn')} to look at, "
              f"{sum(1 for f in res['findings'] if f['severity'] == 'ok')} history lines skipped\n")
        if shown:
            print(f"{'sev':5} | {'file':58} | {'line':>6} | {'found':28} | expected")
            for f in shown:
                print(f"{f['severity']:5} | {f['file'][:58]:58} | {f['line']:>6} | {f['found'][:28]:28} | {f['expected'][:150]}")
    return 1 if (a.check and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
