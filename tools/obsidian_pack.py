"""Obsidian starter vault (owner 2026-11-04: "Obsidian connected to everything, Jarvis thinking like me").

    python tools/obsidian_pack.py              write tools/web_public/mind/starter/{starter_pack.json, starter_pack.js, manifest.json}
    python tools/obsidian_pack.py --check      exit 1 when the committed files differ from a fresh build (the repo's facts moved on)
    python tools/obsidian_pack.py --zip F.zip  also write the vault as a real .zip (store-only, fixed dates: the same bytes every run)
    from tools import obsidian_pack; obsidian_pack.publish(out_dir)   -> <out_dir>/mind/starter/obsidian_pack.zip + the three files

What it builds: a ready-to-drop Obsidian vault of markdown notes (about 250), generated from files that already exist in the repo, so
nothing is invented here:
    tools/web_public/athena/library.json   the plain-words library (strategy steps, MFFU rules, glossary, playbooks, what we learned,
                                           rejected ideas, Kalshi, OLYMPUS app guides): one note each, its [[ids]] turned into [[Titles]]
    research/lit/mffu_rules.json           the MFFU rules that matter (a table of the numbers, with their status)
    tools/web_public/plutus/plans.json     the money plan (accounts, prices, per-month results, caps)
    research/writeups/*.md                 short summary notes of the newest research nights
    tools/web_public/jarvis/obsidian.js    the "Me" note Jarvis seeds (ME_TEMPLATE) and the paths Jarvis reads
Layout: 00 Home (the map) / Trading (strategy steps, MFFU, glossary, risk rules, checklists, second strategies) / Playbooks / Research /
Money / Templates (Daily, Trade journal entry, Weekly review, Kalshi bet review, Idea note) / Daily / Journal / OLYMPUS (app guides) /
OLYMPUS/Jarvis (Me, Memory: the exact paths Jarvis reads and appends to) / Goals. Every note has frontmatter (tags, type, source) and
[[wikilinks]]; every [[link]] resolves (tests/test_obsidian_pack.py). Public facts only: no keys, no logins, no account numbers (the
accounts are "the 50K" and "the 25K"). The page (tools/web_public/mind/starter.js, the Teach page) offers the .zip and a one-file copy;
it never writes into the vault. Deterministic: no clock, the same inputs give the same bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "mind", "starter")
SRC = {
    "library": "tools/web_public/athena/library.json", "rules": "research/lit/mffu_rules.json", "plans": "tools/web_public/plutus/plans.json",
    "obsidian": "tools/web_public/jarvis/obsidian.js", "strategy": "STRATEGY.md",
}
WRITEUPS = [  # (file, note title, why it is here)
    ("2026-11-04_kalshi_edges.md", "Kalshi edges - why it loses and what might work", "Kalshi"),
    ("2026-11-04_lit_ideas_night.md", "LIT ideas night - 16 new ideas tested", "LIT"),
    ("2026-11-04_lit_ideas_round2.md", "LIT ideas round 2 - scale-in and six more ideas", "LIT"),
    ("2026-11-04_second_strategies_night.md", "Second strategies night - ATLAS and BLITZ on the 25K", "second strategies"),
    ("atlas.md", "ATLAS research - account B on the Builder 25K", "second strategies"),
    ("blitz-25k.md", "BLITZ research - its own Builder 25K", "second strategies"),
    ("2026-11-03-money-plan.md", "The money plan research", "money"),
]
ZIP_DATE = (2026, 11, 4, 0, 0, 0)
FORBID = re.compile(r'[\\/:*?"<>|#^\[\]]')
LINK = re.compile(r"\[\[([^\]|#]{1,200})(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


ASCII = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", "→": "->", "×": "x", "≥": ">=",
         "≤": "<=", "·": "-", "−": "-", " ": " "}


def ascii_title(s: str) -> str:
    for k, v in ASCII.items():
        s = s.replace(k, v)
    s = s.encode("ascii", "ignore").decode()
    s = s.replace("...", " ").replace(":", " -").replace("/", "-").replace("\\", "-").replace("|", "-")
    s = FORBID.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" .-")
    return s


def short_title(s: str, n: int = 72) -> str:
    s = ascii_title(s)
    if len(s) > n:
        s = s[:n].rsplit(" ", 1)[0].strip(" .,-(")
        while re.search(r"\s(and|or|the|a|an|of|to|for|on|in|with|by|vs|is|at|from)$", s, re.I):
            s = s.rsplit(" ", 1)[0].strip(" .,-(")
    return s


def quote(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


class Pack:
    def __init__(self):
        self.notes: dict[str, dict] = {}          # path -> {title, tags, type, source, body, up}
        self.by_title: dict[str, str] = {}

    def add(self, folder: str, title: str, body: str, tags, typ: str, source=(), up=None, extra=None) -> str:
        title = ascii_title(title) or "Note"
        base, n = title, 2
        while title.lower() in {t.lower() for t in self.by_title}:
            title = f"{base} {n}"
            n += 1
        path = (folder.rstrip("/") + "/" if folder else "") + title + ".md"
        self.notes[path] = {"title": title, "tags": [t for t in dict.fromkeys(tags) if t], "type": typ, "source": list(source), "body": body.strip("\n"), "up": up or [], "extra": extra or {}}
        self.by_title[title] = path
        return title

    def render(self, path: str) -> str:
        n = self.notes[path]
        if n["body"].startswith("---\n"):                    # a template: its own frontmatter ({{date}} is filled by Obsidian), no footer
            return scrub(n["body"]) + "\n"
        fm = ["---", f"type: {n['type']}", "tags: [" + ", ".join(n["tags"]) + "]"]
        for k, v in n["extra"].items():
            fm.append(f"{k}: {v}")
        if n["source"]:
            fm.append("source: [" + ", ".join(quote(s) for s in n["source"]) + "]")
        fm.append("---")
        body = n["body"]
        if not body.lstrip().startswith("# "):
            body = f"# {n['title']}\n\n{body}"
        up = [f"[[{u}]]" for u in n["up"] if u != n["title"]]
        foot = ("\n\n---\nUp: " + " | ".join(up)) if up else ""
        return scrub("\n".join(fm) + "\n\n" + body + foot) + "\n"


ACCOUNT_ID = re.compile(r"\bMFFU[A-Z]*\d{5,}\b")


def scrub(s: str) -> str:
    """Account ids out, whatever the source says ('eval (MFFU...123, $43) passes' -> 'eval ($43) passes')."""
    s = re.sub(r"\((" + ACCOUNT_ID.pattern + r")\)\s*", "", s)                # "eval (ID) passes"  -> "eval passes"
    s = re.sub(r"\((" + ACCOUNT_ID.pattern + r"),\s*", "(", s)                 # "eval (ID, $43)"    -> "eval ($43)"
    return ACCOUNT_ID.sub("", s)


def undate(t: str) -> str:
    """A note named with a date is a daily note to Jarvis: the date leaves the name and goes into the frontmatter."""
    t = re.sub(r"\s*\(20\d\d-\d\d-\d\d\s*([^)]*)\)", lambda m: f" ({m.group(1).strip()})" if m.group(1).strip() else "", t)
    return re.sub(r"\s*20\d\d-\d\d-\d\d", "", t)


def usd(x) -> str:
    x = float(x)
    return f"${x:,.0f}" if abs(x - round(x)) < 0.005 else f"${x:,.2f}"


def lower_word(t: str) -> str:
    """'Stop' -> 'stop' mid-sentence; acronyms and names (CISD, MNQ and NQ) stay."""
    return t[0].lower() + t[1:] if len(t) > 1 and t[0].isupper() and t[1:].islower() else t


def cut(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(" ,;:-") + "..."


def slug_tag(t: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", t.lower()).strip("-")


def build() -> tuple[dict, dict]:
    lib = json.loads(read(SRC["library"]))
    rules = json.loads(read(SRC["rules"]))
    plans = json.loads(read(SRC["plans"]))
    entries = {e["id"]: e for e in lib["entries"]}
    P = Pack()

    # ---------------------------------------------------------------- titles first (links need them before the bodies are written)
    FOLDER = {"strategy": ("Trading/Strategy", "trading"), "mffu": ("Trading/MFFU rules", "trading"), "words": ("Trading/Glossary", "trading"),
              "numbers": ("Money/Numbers", "money"), "playbook": ("Playbooks", "playbook"), "rejected": ("Research/Rejected ideas", "research"),
              "kalshi": ("Research/Kalshi", "kalshi"), "learned": ("Research/What we learned", "research"), "olympus": ("OLYMPUS/Apps", "olympus")}
    HUB = {"strategy": "Zlarior LIT strategy", "mffu": "MFFU rules that matter", "words": "Glossary", "numbers": "Money hub", "playbook": "Playbooks",
           "rejected": "Rejected ideas", "kalshi": "Kalshi bot research", "learned": "What we learned", "olympus": "OLYMPUS apps"}
    title_of: dict[str, str] = {}
    taken: set[str] = {"00 Home", "Trading hub", "Zlarior LIT strategy", "Second strategies", "MFFU rules that matter", "Risk rules", "Glossary", "Playbooks",
                       "Research hub", "What we learned", "Rejected ideas", "Kalshi bot research", "Money hub", "Accounts plan", "Plutus numbers", "Templates",
                       "Daily note", "Trade journal entry", "Weekly review", "Kalshi bet review", "Idea note", "Daily notes", "Trade journal", "Goals", "Me", "Memory",
                       "How Jarvis reads this vault", "OLYMPUS apps", "Before the session checklist", "During the session checklist", "After the session checklist",
                       "Money checklist", "Never checklist", "Trading checklists"}
    for e in lib["entries"]:
        t = short_title(undate(e["title"])) or e["id"]
        if t in taken:
            t = f"{t} ({e['kind']})"
        while t in taken:
            t += " x"
        taken.add(t)
        title_of[e["id"]] = t

    def link(m):
        i = m.group(1).strip()
        if i not in title_of:
            return i
        t = title_of[i]
        return f"[[{t}|{lower_word(t)}]]" if lower_word(t) != t else f"[[{t}]]"

    def text(s: str) -> str:
        return re.sub(r"\[\[([^\]]+)\]\]", link, s)

    def plain(s: str) -> str:
        return re.sub(r"\[\[([^\]]+)\]\]", lambda m: lower_word(title_of.get(m.group(1).strip(), m.group(1))), s)

    # ---------------------------------------------------------------- the library entries, one note each
    kinds_present = set()
    for e in lib["entries"]:
        kind = e["kind"]
        folder, area = FOLDER[kind]
        kinds_present.add(kind)
        tags = [area] + [slug_tag(t) for t in e["tags"] if slug_tag(t) != area]
        body = [f"> {text(e['short'])}", ""]
        for b in e["body"]:
            body.append(text(b))
            body.append("")
        q = e.get("quiz")
        if q:
            body += ["## Check yourself", f"**Q:** {q['q']}", f"**A:** {q['a']}", ""]
        if kind == "strategy" and e["id"].startswith("step-"):
            n = int(e["id"].split("-")[1])
            nav = []
            if n > 1:
                nav.append(f"Before: [[{title_of['step-%d' % (n - 1)]}]]")
            if n < 9:
                nav.append(f"Next: [[{title_of['step-%d' % (n + 1)]}]]")
            body += [" | ".join(nav), ""]
        pth = P.add(folder, title_of[e["id"]], "\n".join(body), tags, {"words": "term", "strategy": "strategy", "mffu": "rule", "playbook": "playbook", "learned": "research",
                                                                          "rejected": "rejected", "kalshi": "kalshi", "numbers": "numbers", "olympus": "app-guide"}[kind],
                    e.get("src") or [], up=[HUB[kind], "00 Home"],
                    extra=({"date": re.search(r"20\d\d-\d\d-\d\d", e["title"]).group(0)} if re.search(r"20\d\d-\d\d-\d\d", e["title"]) else None))
        assert pth == title_of[e["id"]], (pth, title_of[e["id"]])

    def L(i):
        return f"[[{title_of[i]}]]"

    def bullets(ids, short=True):
        out = []
        for i in ids:
            e = entries[i]
            out.append(f"- {L(i)}" + (f" - {cut(plain(e['short']), 150)}" if short else ""))
        return "\n".join(out)

    ids_of = lambda kind: [e["id"] for e in lib["entries"] if e["kind"] == kind]  # noqa: E731

    # ---------------------------------------------------------------- Trading
    steps = [f"step-{i}" for i in range(1, 10)]
    lit_body = "\n".join([
        f"> {text(entries['lit-in-one']['short'])}", "",
        *[text(b) + "\n" for b in entries["lit-in-one"]["body"]],
        "## The nine steps", *[f"{n}. {L(i)} - {cut(plain(entries[i]['short']), 140)}" for n, i in enumerate(steps, 1)], "",
        "## Size, trades a day, paper", bullets(["one-trade", "eval-sizing", "funded-sizing", "paper-only"]), "",
        "## The numbers", bullets(ids_of("numbers")), "",
        "## Where to go next",
        "- The exact rulebook is `STRATEGY.md` in the repo (this note is the plain-words version).",
        "- What you can do with it today: [[Daily routine]] and [[Trading checklists]]. When something goes wrong: [[Playbooks]].",
        "- What was tried and dropped: [[Rejected ideas]]. Words you do not know: [[Glossary]]. The prop firm's limits: [[MFFU rules that matter]].",
        "- The second and third bots: [[Second strategies]]."])
    P.add("Trading", "Zlarior LIT strategy", lit_body, ["trading", "strategy", "moc"], "moc", ["STRATEGY.md"], up=["Trading hub", "00 Home"])

    # second strategies, from plans.json (numbers) and the writeups' own status lines
    acc = {a["id"]: a for a in plans["strategy"]["accounts"]}
    wf = {f: parse_writeup(f) for f, _, _ in WRITEUPS}
    a, b = acc["atlas_25k"], acc["blitz_25k"]
    sec = [
        "> Zlarior (LIT) is the main bot on the 50K. ATLAS and BLITZ are two more strategies for the 25K accounts. All are paper first; the owner arms live himself.", "",
        "## ATLAS (EMA + MACD + support/resistance, account B)",
        f"- Runs on a Builder 25K (eval price paid {usd(a['price'])}). Eval within 2 weeks: {a['eval_2w_pass']['H1']:g}% pass in Jan-Jun 2026, {a['eval_2w_pass']['H2']:g}% in Jul-Oct; 2-week fails {a['eval_2w_fail']['H1']:g}% / {a['eval_2w_fail']['H2']:g}%.",
        f"- Funded: about ${a['funded_per_month']['H1']:,} a month (Jan-Jun) and ${a['funded_per_month']['H2']:,} (Jul-Oct); net per month counting the purchase: ${a['net_per_month_from_purchase']['H1']:,} / ${a['net_per_month_from_purchase']['H2']:,}.",
        f"- Latest research verdict: {wf['atlas.md']['status']}", "",
        "## BLITZ (a noise-area scalp, account C)",
        f"- Its own Builder 25K (price {usd(b['price'])}). Eval within 2 weeks: {b['eval_2w_pass']['H1']:g}% pass / {b['eval_2w_fail']['H1']:g}% fail in Jan-Jun; {b['eval_2w_pass']['H2']:g}% / {b['eval_2w_fail']['H2']:g}% in Jul-Oct.",
        f"- Net per month counting the purchase: ${b['net_per_month_from_purchase']['H1']:,} (Jan-Jun) and ${b['net_per_month_from_purchase']['H2']:,} (Jul-Oct): the thinnest of the three.",
        f"- Latest research verdict: {wf['blitz-25k.md']['status']}", "",
        "## How the three fit together",
        f"- {plans['notes'][0]}",
        f"- {plans['strategy']['mffu_caps']['text']}", "",
        "More: [[Accounts plan]], [[Plutus numbers]], [[Second strategies night - ATLAS and BLITZ on the 25K]], [[ATLAS research - account B on the Builder 25K]], [[BLITZ research - its own Builder 25K]]."]
    P.add("Trading", "Second strategies", "\n".join(sec), ["trading", "strategy", "atlas", "blitz"], "strategy",
          ["tools/web_public/plutus/plans.json", "research/writeups/atlas.md", "research/writeups/blitz-25k.md"], up=["Trading hub", "00 Home"])

    # MFFU rules that matter, straight from research/lit/mffu_rules.json
    lim, e50, sf = rules["limits"]["builder_50k"], rules["builder_50k"]["eval"], rules["builder_50k"]["sim_funded"]
    l25 = rules["limits"]["builder_25k"]
    st = lambda d: d.get("status", "")  # noqa: E731
    mffu = [
        f"> The prop firm's rules that decide whether the account lives. Source: `research/lit/mffu_rules.json` (web research {rules['built']}; re-check before the first live payout).", "",
        "## Builder 50K (the eval account)", "| Rule | Value | Status |", "|---|---|---|",
        f"| Profit target (eval) | ${lim['target']:,.0f} | {st(e50['profit_target'])} |",
        f"| Max loss | ${lim['mll']:,.0f}, end-of-day trailing (the {L('m-floor')}), locks at start + ${lim['lock']:,.0f} | {st(e50['max_loss'])} |",
        f"| Daily loss limit | ${lim['dll']:,.0f}, soft: trading pauses for that session | {st(e50['daily_loss_limit'])} |",
        f"| Largest size | {lim['max_micros']} micros or {lim['max_minis']} minis | {st(e50['max_contracts'])} |",
        f"| Flat by | 16:10 ET; no overnight or weekend positions | {st(e50['overnight_weekend'])} |",
        f"| Inactivity | no trade for {lim['inactivity_days']} calendar days can close the account | {st(e50['inactivity'])} |",
        f"| Hedging | not allowed (no long and short at once, also across accounts) | {st(e50['hedging'])} |",
        f"| Bots | allowed, with your own parameters; no high-frequency tricks, no exploiting simulated fills | {st(e50['automation'])} |",
        f"| Price | list {usd(e50['price']['value']['list'])}; the owner paid {usd(e50['price']['value']['owner_paid'])}; one-time, {usd(e50['activation_fee']['value'])} activation | {st(e50['price'])} |",
        "", "## When funded (sim funded)", "| Rule | Value | Status |", "|---|---|---|",
        f"| Buffer | ${lim['buffer']:,.0f} above the start before the first payout | {st(sf['buffer'])} |",
        f"| First payout | {sf['first_payout']['value']} | {st(sf['first_payout'])} |",
        f"| Payout size | ${lim['pay_min']:,.0f} to ${lim['pay_max']:,.0f}; you keep {lim['split'] * 100:.0f}% | {st(sf['payout_min'])} |",
        f"| Best-day rule | no single day may be more than {lim['cons'] * 100:.0f}% of the profit | {st(sf['consistency'])} |",
        f"| Cycle and count | one payout every {lim['cycle_days']} winning days, up to {lim['max_payouts']} sim payouts | {st(sf['max_sim_payouts'])} |",
        "", "## Builder 25K (ATLAS and BLITZ)", "| Rule | Value |", "|---|---|",
        f"| Profit target | ${l25['target']:,.0f} |", f"| Max loss | ${l25['mll']:,.0f} (end-of-day trailing) |", f"| Daily loss limit | ${l25['dll']:,.0f} |",
        f"| Largest size | {l25['max_micros']} micros |", f"| Buffer and payouts | buffer ${l25['buffer']:,.0f}, payouts ${l25['pay_min']:,.0f} to ${l25['pay_max']:,.0f} |",
        f"| Price | usually $63; $43 on 2026-10-26 |", "",
        f"## Caps\n{plans['strategy']['mffu_caps']['text']}", "",
        "## The notes behind these rules", bullets(ids_of("mffu")), "",
        "See also [[Risk rules]], [[Playbooks]] and [[Glossary]]."]
    P.add("Trading", "MFFU rules that matter", "\n".join(mffu), ["trading", "mffu", "moc"], "moc", ["research/lit/mffu_rules.json"], up=["Trading hub", "00 Home"])

    # risk rules
    risk = [
        "> Size follows the stop. The stop sits where the idea is wrong, never a random distance. A wider stop means fewer micros, not skipping the trade.", "",
        "## The rules", "1. Stop = 1 tick beyond the sweep extreme (the protected high or low). See " + L("step-6") + ".",
        "2. Size follows the stop and the room left to the floor: " + L("eval-sizing") + ", " + L("funded-sizing") + ".",
        "3. One clear target (the VIX band), banked at 8R. No greed. See " + L("step-7") + ".",
        "4. One trade a day at most: " + L("one-trade") + ".",
        "5. Paper only until the owner arms live himself: " + L("paper-only") + ".",
        "6. A new rule must hold in 2026 AND in 2021-25 and keep 2 to 4 trades a week. See " + L("p-new") + ".", "",
        "## The account limits", bullets(["m-floor", "m-dll", "m-size", "m-flat", "m-hedge", "m-idle"]), "",
        "## After a bad day", bullets(["p-loss", "p-two-losses", "p-dll"]), "",
        "More: [[MFFU rules that matter]], [[Trading checklists]], [[Never checklist]]."]
    P.add("Trading", "Risk rules", "\n".join(risk), ["trading", "risk"], "rule", ["STRATEGY.md", "research/lit/mffu_rules.json"], up=["Trading hub", "00 Home"])

    # checklists from the library's rules (numbered, not tasks: Jarvis would list every open "- [ ]" it finds)
    groups = [("before", "Before the session checklist", "Before the session"), ("during", "During the session checklist", "During the session"),
              ("after", "After the session checklist", "After the session"), ("money", "Money checklist", "Money"), ("never", "Never checklist", "Never")]
    for g, title, label in groups:
        items = [r for r in lib["rules"] if r["group"] == g]
        body = [f"> {label}: {len(items)} rules from the daily routine. Copy the ones you want into today's daily note as tasks.", ""]
        for n, r in enumerate(items, 1):
            src = f" ({L(r['from'])})" if r.get("from") in title_of else ""
            body.append(f"{n}. {text(r['text'])}{src}")
        body += ["", "Back to [[Daily routine]] and [[Trading checklists]]."]
        P.add("Trading/Checklists", title, "\n".join(body), ["trading", "checklist"], "checklist", ["tools/web_public/athena/library.json"], up=["Trading checklists", "00 Home"])
    P.add("Trading/Checklists", "Trading checklists", "> The daily routine as five short lists.\n\n" + "\n".join(f"- [[{t}]]" for _, t, _ in groups) + "\n\nThe routine itself: [[Daily routine]]. The templates: [[Templates]].",
          ["trading", "checklist", "moc"], "moc", [], up=["Trading hub", "00 Home"])

    # glossary hub
    words = sorted(ids_of("words"), key=lambda i: title_of[i].lower())
    P.add("Trading", "Glossary", "> Every term in plain words, one note per term. The links between them show how the ideas fit.\n\n" + bullets(words),
          ["trading", "glossary", "moc"], "moc", [], up=["Trading hub", "00 Home"])

    P.add("Trading", "Trading hub", "\n".join([
        "> Everything about how the NQ bots trade and what the prop firm allows.", "",
        "- [[Zlarior LIT strategy]] - the main bot in nine steps", "- [[Second strategies]] - ATLAS and BLITZ", "- [[MFFU rules that matter]] - the firm's limits",
        "- [[Risk rules]] - size follows the stop", "- [[Trading checklists]] - before, during, after, money, never", "- [[Daily routine]] - the simple day",
        "- [[Glossary]] - every term", "- [[Playbooks]] - what to do when something happens", "- [[Rejected ideas]] - the graveyard, check it before a new idea", "- [[Trade journal]] - where each trade is written down"]),
        ["trading", "moc"], "moc", [], up=["00 Home"])

    # ---------------------------------------------------------------- Playbooks, Research, Money hubs
    P.add("Playbooks", "Playbooks", "> What to do when... Short, numbered, no panic.\n\n" + bullets(ids_of("playbook")) + "\n\nSee also [[Risk rules]] and [[Trading checklists]].",
          ["playbook", "moc"], "moc", [], up=["00 Home"])
    P.add("Research", "Research hub", "\n".join([
        "> What the research nights found, in short notes. The long versions are in `research/writeups/` in the repo.", "",
        "- [[What we learned]] - one note per research night", "- [[Rejected ideas]] - tested, did not work, and why", "- [[Kalshi bot research]] - why the Kalshi bot loses, the one pocket that might work",
        "", "## Latest writeups", *[f"- [[{t}]]" for _, t, _ in WRITEUPS], "", "The rule for keeping an idea: better in 2026 and in 2021-25, and still 2 to 4 trades a week."]),
        ["research", "moc"], "moc", [], up=["00 Home"])
    P.add("Research", "What we learned", "> Every research night in two lines.\n\n" + bullets(sorted(ids_of("learned"), key=lambda i: title_of[i].lower())),
          ["research", "moc"], "moc", [], up=["Research hub", "00 Home"])
    P.add("Research", "Rejected ideas", "> The graveyard. Search here before you suggest a new strategy idea; do not redo one without a genuinely new idea.\n\n" + bullets(ids_of("rejected")),
          ["research", "moc"], "moc", [], up=["Research hub", "00 Home"])
    P.add("Research", "Kalshi bot research", "> Why the Kalshi bot loses money, and the one pocket that might work.\n\n" + bullets(ids_of("kalshi")) + "\n\nTemplate: [[Kalshi bet review]]. Long version: [[Kalshi edges - why it loses and what might work]].",
          ["research", "kalshi", "moc"], "moc", [], up=["Research hub", "00 Home"])
    for f, title, topic in WRITEUPS:
        w = wf[f]
        body = [f"> {w['status']}" if w["status"] else f"> {w['title']}", ""]
        if w["status"]:
            body += [f"**Full title:** {w['title']}", ""]
        if w["summary"]:
            body += ["## Summary", w["summary"], ""]
        if w["table"]:
            body += ["## The answer in one table", *w["table"], ""]
        body += [f"Source: `research/writeups/{f}`.", "", "Related: [[Research hub]], [[What we learned]]" + (", [[Kalshi bot research]]" if topic == "Kalshi" else ", [[Second strategies]]" if topic == "second strategies" else ", [[Rejected ideas]]" if topic == "LIT" else ", [[Money hub]]") + "."]
        P.add("Research/Writeups", title, "\n".join(body), ["research", slug_tag(topic)], "research", [f"research/writeups/{f}"], up=["Research hub", "00 Home"])

    # Money: accounts plan + Plutus numbers
    s = plans["strategy"]
    rows = ["| Accounts | Jan-Jun 2026 | Jul-Oct 2026 |", "|---|---|---|"]
    for k, v in s["by_count"].items():
        rows.append(f"| {k} | ${v['H1']['per_month']:,} a month | ${v['H2']['per_month']:,} a month |")
    acct = ["> The accounts plan in short. Numbers are net of every eval fee, after costs, from the bot's real LIT trades and the research files (`tools/web_public/plutus/plans.json`).", "",
            "## What each account is", *[f"- **{a['name']}** (eval price {usd(a['price'])}): funded about ${a['funded_per_month']['H1'] if a['funded_per_month'] else 0:,} a month in Jan-Jun, "
                                         f"${a['funded_per_month']['H2'] if a['funded_per_month'] else 0:,} in Jul-Oct; 2-week eval pass {a['eval_2w_pass']['H1']:g}% / {a['eval_2w_pass']['H2']:g}%." for a in s["accounts"] if a["funded_per_month"]],
            f"- **{b['name']}** (eval price {usd(b['price'])}): eval pass within 2 weeks {b['eval_2w_pass']['H1']:g}% / {b['eval_2w_pass']['H2']:g}%; net per month from the purchase ${b['net_per_month_from_purchase']['H1']:,} / ${b['net_per_month_from_purchase']['H2']:,}.", "",
            "## How many accounts", *rows, "", f"Three accounts is the MFFU cap. {s['three_accounts']['range']['text']}.", "", "## Notes", *[f"- {n}" for n in plans["notes"][:3]], "",
            "Related: [[Plutus numbers]], [[Second strategies]], [[MFFU rules that matter]], [[Money hub]]."]
    P.add("Money", "Accounts plan", "\n".join(acct), ["money", "accounts"], "money", ["tools/web_public/plutus/plans.json"], up=["Money hub", "00 Home"])
    prow = ["| Plan | Eval price (list) | Target | Max loss | Split |", "|---|---|---|---|---|"]
    for pl in plans["plans"]:
        prow.append(f"| {pl['firm']} {pl['name']} | {usd(pl['price'])} ({usd(pl['list_price'])}) | ${pl['target']:,.0f} | ${pl['mll']:,.0f} | {pl['split'] * 100:.0f}% |")
    tr = plans["trio"]
    plut = ["> The Plutus app's numbers as a note. Spans: Jan-Jun 2026, Jul-Oct 2026 (the honest check) and 2021-25 (reference only).", "", "## Plans", *prow, "",
            "## All the bots together (per month, net of fees)", "| Span | Per month | Months 4-6 per month | Months with a loss over 6 |", "|---|---|---|---|",
            *[f"| {k} | ${v['net_per_month']:,} | ${v['months4_6_per_month']:,} | {v['neg_6m']:g}% |" for k, v in tr.items()], "",
            f"Built {plans['built']}. Source: {plans['source'][:220].rstrip()}...", "", "Related: [[Accounts plan]], [[Money hub]], " + L("n-money") + "."]
    P.add("Money", "Plutus numbers", "\n".join(plut), ["money", "plutus"], "money", ["tools/web_public/plutus/plans.json"], up=["Money hub", "00 Home"])
    P.add("Money", "Money hub", "> Money, not only R: every result shows net dollars and dollars a month.\n\n- [[Accounts plan]]\n- [[Plutus numbers]]\n" + bullets(ids_of("numbers")) + "\n- [[MFFU rules that matter]]",
          ["money", "moc"], "moc", [], up=["00 Home"])

    # ---------------------------------------------------------------- OLYMPUS app guides + Jarvis
    P.add("OLYMPUS/Apps", "OLYMPUS apps", "> How to use each app in one line each. Open the app, look at the one thing the guide names.\n\n" + bullets(ids_of("olympus")) + "\n\nJarvis: [[How Jarvis reads this vault]].",
          ["olympus", "moc"], "moc", [], up=["00 Home"])
    obs = read(SRC["obsidian"])
    m = re.search(r"export const ME_TEMPLATE = `(.*?)`;", obs, re.S)
    assert m, "ME_TEMPLATE not found in jarvis/obsidian.js"
    me = m.group(1)
    assert "## Preferences Jarvis learned" in me
    me = me.replace("## Preferences Jarvis learned", "## Where my rules live\n- [[Zlarior LIT strategy]] and [[Risk rules]]\n- [[MFFU rules that matter]] and [[Playbooks]]\n- [[Goals]], [[Daily routine]], [[Templates]]\n- [[00 Home]]\n\n## Preferences Jarvis learned")
    P.add("OLYMPUS/Jarvis", "Me", me, ["me", "jarvis"], "me", ["tools/web_public/jarvis/obsidian.js"], up=[])
    P.add("OLYMPUS/Jarvis", "Memory", "Jarvis adds what it learns about you below, one line each. It only ever appends; edit freely.\n\nSee [[Me]] and [[How Jarvis reads this vault]].\n",
          ["jarvis", "memory"], "memory", [], up=[])
    P.add("OLYMPUS/Jarvis", "How Jarvis reads this vault", "\n".join([
        "> What Jarvis looks at in these notes, so you know where to write things.", "",
        "- **[[Me]]** (`OLYMPUS/Jarvis/Me.md`): who you are and how to answer. Jarvis reads it to think the way you do.",
        "- **[[Memory]]** (`OLYMPUS/Jarvis/Memory.md`): lines Jarvis appends when you say \"remember ...\".",
        "- **Daily notes**: a note named with a date, like `2026-11-04.md`, in the `Daily` folder. Use the [[Daily note]] template.",
        "- **Tasks**: any line that starts with a checkbox (a dash, a space, an empty box, a space, then the text) is an open task Jarvis can list. Done ones are ticked.",
        "- **Goals**: any note with *Goals* in its title, tags or a heading. See [[Goals]].",
        "- **Search**: titles, headings, tags and text. Tags go in the frontmatter `tags: [..]` or as #words.",
        "- **What Jarvis writes**: only appends, and only into `OLYMPUS/Inbox`, `OLYMPUS/Notes`, `OLYMPUS/Logs`, the two notes above and today's daily note, after you say yes.", "",
        "The checklists in this vault are numbered lists on purpose: a list of boxes would show up as open tasks every day.", "", "Back to [[00 Home]]."]),
        ["jarvis"], "guide", ["tools/web_public/jarvis/obsidian.js"], up=["00 Home"])

    # ---------------------------------------------------------------- Goals, Daily, Journal
    P.add("", "Goals", "\n".join([
        "> The targets, in the owner's words, kept short. Change them when they change.", "",
        "## Trading", "- Pass the MFFU Builder 50K eval within 2 weeks, never more than 3 weeks.", "- 2 to 4 trades a week from the bot.",
        "- Show money, not only R: net dollars and dollars a month.", "- Go live only when the owner decides, present at the desk.", "",
        "## The system", "- OLYMPUS and Jarvis: the home of everything.", "- Obsidian connected to everything, so Jarvis thinks like me. See [[Me]].", "",
        "Related: [[Zlarior LIT strategy]], [[Money hub]], [[00 Home]]."]),
        ["goals", "trading"], "goals", ["CLAUDE.md"], up=["00 Home"])
    P.add("Daily", "Daily notes", "> Put one note a day here, named with the date (for example 2026-11-04). Make it from the [[Daily note]] template.\n\nThe routine: [[Daily routine]]. Jarvis finds today's note by its date: [[How Jarvis reads this vault]].",
          ["daily", "moc"], "moc", [], up=["00 Home"])
    P.add("Journal", "Trade journal", "> One note per trade, made from the [[Trade journal entry]] template. Fields: setup, size, plan followed, emotion, lesson.\n\nEvery Sunday read the week back with the [[Weekly review]] template. The rules you check against: [[Zlarior LIT strategy]], [[Risk rules]].",
          ["journal", "moc"], "moc", [], up=["00 Home"])

    # ---------------------------------------------------------------- Templates (no "- [ ]" lines: Jarvis would list them as open tasks)
    P.add("Templates", "Templates", "> Five templates. In Obsidian: Settings > Core plugins > Templates, set the template folder to Templates, then insert one with the command palette.\n\n"
          "- [[Daily note]]\n- [[Trade journal entry]]\n- [[Weekly review]]\n- [[Kalshi bet review]]\n- [[Idea note]]\n\nBack to [[00 Home]].", ["templates", "moc"], "moc", [], up=["00 Home"])
    P.add("Templates", "Daily note", "\n".join([
        "---", "date: \"{{date}}\"", "tags: [daily]", "---", "", "# {{date}}", "", "## Before the session", "Room to the floor: ", "Days since the last trade: ", "Bot on and its feed fresh? yes / no",
        "The plan for today: ", "", "## During", "Trade taken? If yes, make a Trade journal entry and link it here.", "", "## After", "Result in dollars: ", "Rules followed? yes / no",
        "One line to remember: ", "", "## Tasks", "Write tasks as `- [ ] text` (a dash, a space, an empty box, a space, the text). Jarvis reads them.", "",
        "Routine: [[Daily routine]] | Checklists: [[Trading checklists]] | [[Trade journal]]"]), ["templates", "daily"], "template", [], up=["Templates"])
    P.add("Templates", "Trade journal entry", "\n".join([
        "---", "date: \"{{date}}\"", "tags: [journal, trade]", "setup: ", "size: ", "plan_followed: ", "emotion: ", "lesson: ", "---", "", "# Trade {{date}} {{time}}", "",
        "## Setup", "Which level was swept? Was there an inducement, a displacement, the 5m shift, the 1m confirmation? See [[Zlarior LIT strategy]].", "",
        "## Size", "Micros: . Stop in points: . Risk in dollars: . Size follows the stop: [[Risk rules]].", "",
        "## Plan followed?", "yes / no. If no, which rule: ", "", "## Result", "Dollars: . R: . Net after costs: ", "",
        "## Emotion", "Before: . During: . After: ", "", "## Lesson", "One sentence: ", "", "Back to [[Trade journal]]."]), ["templates", "journal"], "template", [], up=["Templates"])
    P.add("Templates", "Weekly review", "\n".join([
        "---", "date: \"{{date}}\"", "tags: [weekly, review]", "---", "", "# Week of {{date}}", "", "## The numbers", "Trades: . Wins: . Dollars: . Days with no trade: ", "",
        "## Rules", "Did I follow the plan on every trade? Where not, and why: ", "", "## What worked", "", "## What to change", "Only change a rule with two-halves proof: [[Rejected ideas]] first.", "",
        "## Next week", "Anything on the calendar (news, a payout, an inactivity clock)? See [[Playbooks]].", "", "Back to [[Trade journal]] | [[Goals]]"]), ["templates", "weekly"], "template", [], up=["Templates"])
    P.add("Templates", "Kalshi bet review", "\n".join([
        "---", "date: \"{{date}}\"", "tags: [kalshi, review]", "market: ", "side: ", "price_cents: ", "size_dollars: ", "result: ", "---", "", "# Kalshi bet {{date}}", "",
        "## The bet", "Market, side, price in cents, size in dollars: ", "", "## Why", "What edge did I think I had? Was it one of the pockets in [[Kalshi bot research]]?", "",
        "## Result", "Won or lost, dollars, the fee: ", "", "## Lesson", "One sentence: ", "", "Back to [[Kalshi bot research]]."]), ["templates", "kalshi"], "template", [], up=["Templates"])
    P.add("Templates", "Idea note", "\n".join([
        "---", "date: \"{{date}}\"", "tags: [idea]", "status: new", "---", "", "# Idea {{title}}", "", "## The idea in one line", "", "## Why it might work", "",
        "## First check the graveyard", "Is it already in [[Rejected ideas]] or [[What we learned]]? Do not redo a dead end without a new angle.", "",
        "## How to test it", "Pick on Jan-Jun 2026, check on Jul-Oct 2026, 2021-25 as a reference. It must stay at 2 to 4 trades a week. Show net dollars, dollars a month, profit factor and max drawdown.", "",
        "Back to [[Research hub]]."]), ["templates", "idea"], "template", [], up=["Templates"])

    # ---------------------------------------------------------------- Home
    first = ["lit-in-one", "step-1", "step-6", "step-7", "m-floor", "p-loss", "p-daily", "n-money", "x-all"]
    home = ["> Your starter vault: the trading system, the prop firm's rules, what to do when, what was tried, the money, and the templates. Every note links to the others.", "",
            "## Start here",
            "1. Open the Files app (or iCloud Drive) and find the folder you unzipped.", "2. In Obsidian choose *Open folder as vault* (or copy the folder into your existing vault).",
            "3. Set Templates to the *Templates* folder, then open [[Zlarior LIT strategy]]. In Jarvis, connect the vault so it can read [[Me]].", "",
            "## The map", "- [[Trading hub]] - strategy, risk, glossary, checklists", "- [[Playbooks]] - what to do when", "- [[Research hub]] - what the research found",
            "- [[Money hub]] - accounts and the numbers", "- [[Templates]] - daily, trade journal, weekly, Kalshi, ideas", "- [[OLYMPUS apps]] - how to use each app",
            "- [[Goals]] | [[Me]] | [[How Jarvis reads this vault]]", "", "## Read these first", bullets(first), "",
            "## Every day", "[[Daily routine]] then [[Trading checklists]]. Write the day in a [[Daily notes]] note and each trade in the [[Trade journal]]."]
    P.add("", "00 Home", "\n".join(home), ["home", "moc"], "moc", [], up=[])

    # ---------------------------------------------------------------- backlinks: terms and rules list where they are used
    inbound: dict[str, set] = {}
    for pth, n in P.notes.items():
        for t in LINK.findall(n["body"]):
            inbound.setdefault(t.strip(), set()).add(n["title"])
    for pth, n in P.notes.items():
        if n["type"] in ("term", "rule", "strategy") and n["title"] in inbound:
            users = sorted(u for u in inbound[n["title"]] if u != n["title"] and u not in ("Glossary", "00 Home") and not P.notes[P.by_title[u]]["type"] == "moc")[:10]
            if users:
                n["body"] += "\n\n## Used in\n" + "\n".join(f"- [[{u}]]" for u in users)

    # ---------------------------------------------------------------- output
    files = [{"path": p, "text": P.render(p)} for p in sorted(P.notes)]
    link_count = 0
    for f in files:
        link_count += len(LINK.findall(f["text"]))
    sha = hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    pack = {"v": 1, "kind": "olympus-starter-pack", "sha": sha, "notes": files}
    man = {"v": 1, "kind": "olympus-starter-manifest", "sha": sha, "sources": sorted(set(list(SRC.values()) + [f"research/writeups/{w[0]}" for w in WRITEUPS])),
           "counts": {"notes": len(files), "links": link_count, "words": sum(len(f["text"].split()) for f in files),
                      "folders": {k: sum(1 for f in files if (f["path"].split("/")[0] if "/" in f["path"] else "(top)") == k) for k in sorted({(f["path"].split("/")[0] if "/" in f["path"] else "(top)") for f in files})}},
           "notes": [{"path": f["path"], "title": P.notes[f["path"]]["title"], "type": P.notes[f["path"]]["type"], "tags": P.notes[f["path"]]["tags"],
                      "words": len(f["text"].split()), "links": len(set(LINK.findall(f["text"])))} for f in files]}
    return pack, man


def parse_writeup(fname: str) -> dict:
    """title / status / summary of a research writeup (its frontmatter when it has one, else the first lines), plus the first table."""
    t = read(f"research/writeups/{fname}")
    fm, body = {}, t
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    if m:
        for ln in m.group(1).splitlines():
            kv = re.match(r"([A-Za-z_]+):\s*(.*)$", ln)
            if kv:
                fm[kv.group(1)] = kv.group(2).strip()
        body = t[m.end():]
    title = fm.get("title") or (re.search(r"^# (.+)$", body, re.M).group(1) if re.search(r"^# (.+)$", body, re.M) else fname)
    status = fm.get("status", "")
    summary = fm.get("summary", "")
    if not summary:
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip() and not p.lstrip().startswith(("#", "|", "-", "```"))]
        summary = paras[0].replace("\n", " ") if paras else ""
    clean = lambda s, n: cut(s.replace("`", ""), n)  # noqa: E731
    table = []
    for ln in body.splitlines():
        if ln.startswith("|"):
            cells = [cut(c.replace("`", ""), 200) for c in ln.strip().strip("|").split("|")]
            table.append("| " + " | ".join(cells) + " |")
            if len(table) >= 6:
                break
        elif table:
            break
    # keep the table small and well formed: only when it has a header separator in the first 2 rows
    if len(table) < 3 or not set(table[1].replace("|", "").replace(" ", "")) <= set("-:"):
        table = []
    return {"title": clean(title, 160), "status": clean(status, 520), "summary": clean(summary, 900), "table": table}


# ---------------------------------------------------------------------------------------------------------------- writing
def dump(pack: dict, man: dict) -> dict[str, str]:
    pj = json.dumps(pack, ensure_ascii=False, indent=0, sort_keys=False) + "\n"
    js = ("// Generated by tools/obsidian_pack.py (do not edit): the OLYMPUS starter vault as one module, for the Mind page's Teach screen and its demo brain.\n"
          "// The same notes as starter_pack.json ({path, text} each). Loaded on demand with import('./starter/starter_pack.js').\n"
          "export default " + json.dumps(pack, ensure_ascii=False, separators=(",", ":")) + ";\n")
    return {"starter_pack.json": pj, "starter_pack.js": js, "manifest.json": json.dumps(man, ensure_ascii=False, indent=1) + "\n"}


def zip_bytes(pack: dict) -> bytes:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for n in sorted(pack["notes"], key=lambda x: x["path"]):
            zi = zipfile.ZipInfo("OLYMPUS Starter Vault/" + n["path"], ZIP_DATE)
            zi.compress_type = zipfile.ZIP_STORED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, n["text"].encode("utf-8"))
    return buf.getvalue()


def write(out: str = OUT) -> dict:
    pack, man = build()
    os.makedirs(out, exist_ok=True)
    for name, data in dump(pack, man).items():
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(data)
    return man


def publish(out_dir: str) -> str:
    """For the site build: the three files plus obsidian_pack.zip under <out_dir>/mind/starter/ (one line to add to the build)."""
    pack, man = build()
    d = os.path.join(out_dir, "mind", "starter")
    os.makedirs(d, exist_ok=True)
    for name, data in dump(pack, man).items():
        with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(data)
    with open(os.path.join(d, "obsidian_pack.zip"), "wb") as fh:
        fh.write(zip_bytes(pack))
    return f"{man['counts']['notes']} notes, {man['counts']['links']} links"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    pack, man = build()
    data = dump(pack, man)
    if "--check" in argv:
        bad = [n for n, d in data.items() if not os.path.exists(os.path.join(OUT, n)) or open(os.path.join(OUT, n), encoding="utf-8", newline="").read() != d]
        print("starter pack is up to date" if not bad else "starter pack differs: " + ", ".join(bad) + " (run python tools/obsidian_pack.py)")
        return 1 if bad else 0
    write()
    if "--zip" in argv:
        with open(argv[argv.index("--zip") + 1], "wb") as fh:
            fh.write(zip_bytes(pack))
    c = man["counts"]
    print(f"{c['notes']} notes, {c['links']} links, {c['words']} words -> {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
