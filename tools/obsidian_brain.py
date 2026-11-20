"""ZEUS Brain: an Obsidian vault GENERATED from the repo (night-obsidian 2026-11-20; owner: "I want a huge Obsidian that basically
learns everything from Jarvis to Kalshi to NQ, keeps pushing and building and adapting").

    python tools/obsidian_brain.py                     build the repo's vault: vault/ZEUS Brain/ (+ vault/.obsidian look, vault/Inbox/)
    python tools/obsidian_brain.py --check             exit 1 when the committed vault differs from a fresh build
    python tools/obsidian_brain.py --vault "C:\\...\\MyVault"   build into a real vault as <vault>/OLYMPUS/ZEUS Brain/ (+ the CSS snippet)
    from tools import obsidian_brain; obsidian_brain.build(vault_dir, root=ROOT, standalone=True)

What it writes (only inside <vault>/<SUB>/; plus, standalone, <vault>/.obsidian/ and one start note in <vault>/Inbox/ when Inbox is new):
    ZEUS Home                      the map of content (accounts, strategies, decisions, lessons, apps, Kalshi, last days, newest research)
    Accounts/Account <name>        one per account: stage, balance, room, to pass, plan, events, trades by month
    Strategies/<bot>               Zlarior (LIT), ATLAS + one note per member, BLITZ (paper), Rapid lanes, 50K combo, Kalshi K8 + legs:
                                   rules in plain words, performance by period, what was tested and rejected, the write-ups
    Research/<stem>                one per research/writeups/*.md: frontmatter, summary, verdict, links (strategies, family, day, refs)
    Families/Family <f>            the research families (graph clusters)
    Days/Day <YYYY-MM-DD>          one per day with trades, board events, research or a ZEUS daily review; Months/Month <YYYY-MM>
    ZEUS Lessons                   loss-cluster findings (research/anatomy/explain.json) + every rejected idea family (TESTED_AND_REJECTED)
    ZEUS Decisions                 business decisions.json by status (open / yes / no / later)
    ZEUS Apps + Apps/Apps <door>   docs/OLYMPUS_MAP.md
    ZEUS Kalshi                    the Kalshi docs, K8 legs, the edge tables, the Kalshi research
    ZEUS State                     STATE.md
Rules: deterministic (no clock: the same inputs give the same bytes), idempotent (a file is rewritten only when its text changed;
a note this tool made earlier and no longer makes is removed, using its own manifest .zeus_brain.json; nothing else is ever
deleted); Inbox/ is the owner's: never written once it exists; every [[link]] resolves to a note of the vault; no plugins needed
(callouts + CSS only); privacy: every note goes through scrub() (emails, keys, account ids, tailnet names, personal folders).
Hooks: tools/learn_night.py (the cloud night: rebuilds vault/), tools/obsidian_sync.py (the PC's 15-minute run, once an hour).
Tests: python -X utf8 -m tests.test_obsidian_brain
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SUB = "ZEUS Brain"                      # standalone: <vault>/ZEUS Brain; inside the owner's vault: <vault>/OLYMPUS/ZEUS Brain
PC_SUB = os.path.join("OLYMPUS", "ZEUS Brain")
REPO_VAULT = os.path.join(ROOT, "vault")
MANIFEST = ".zeus_brain.json"
INBOX = "Inbox"
CSS_MARK = "/* ZEUS Brain snippet (tools/obsidian_brain.py) */"
DAYS_ON_HOME = 14
RESEARCH_ON_HOME = 15

# ------------------------------------------------------------------------------------------------ small helpers
_SCRUB = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,}|xox[abp]-[A-Za-z0-9-]{10,}|nfp_[A-Za-z0-9]{20,})\b"), "[key]"),
    (re.compile(r"(?i)\b(token|api[_ -]?key|password|secret)\s*[:=]\s*(?![\[(])\S{6,}"), r"\1: [hidden]"),
    (re.compile(r"\b(?:MFFU|APEX|TPT|FTMO|TOPSTEP|LL|PA|FF|MFF)[A-Z]*-?\d{5,}\b"), "[account]"),
    (re.compile(r"\b[a-z0-9-]{1,63}\.[a-z0-9-]{3,40}\.ts\.net\b"), "[tailnet]"),
    (re.compile(r"(?<![\d.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}(?![\d.])"), "[tailscale-ip]"),
    (re.compile(r"(?i)\b([A-Z]:[\\/]+(?:Users|Documents and Settings)[\\/]+)(?!YOU\b|you\b|<you>|USER\b|user\b|Public\b)[^\\/\s\"'<>|]{1,64}"), r"\1<you>"),
    (re.compile(r"/home/(?!user\b)[a-z][a-z0-9_-]{1,31}(?=/)"), "/home/<you>"),
    (re.compile(r"\b\d{10,}\b"), "[number]"),
]


def scrub(text: str) -> str:
    s = str(text or "")
    for rx, rep in _SCRUB:
        s = rx.sub(rep, s)
    return s


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:  # noqa: BLE001
        return ""


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def read_jsonl(path: str) -> list:
    out = []
    for line in read_text(path).splitlines():
        try:
            r = json.loads(line)
            if isinstance(r, dict):
                out.append(r)
        except Exception:  # noqa: BLE001
            pass
    return out


def fname(s: str, n: int = 90) -> str:
    """A note name Obsidian accepts as a file AND a [[link]] (no \\ / : * ? " < > | # ^ [ ])."""
    s = re.sub(r'[\\/:*?"<>|#^\[\]]', "-", str(s or "")).replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip(" .-")[:n].strip() or "note"


def link(name: str, label: str | None = None) -> str:
    label = (label or "").replace("|", "-").replace("[", "(").replace("]", ")").strip()
    return f"[[{name}|{label}]]" if label and label != name else f"[[{name}]]"


def usd(v, sign: bool = False) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "-"
    s = f"${abs(f):,.0f}"
    return ("-" + s) if f < 0 else (("+" + s) if sign and f > 0 else s)


def yq(v) -> str:
    return json.dumps(str(v), ensure_ascii=False)


def front(tags, **kv) -> str:
    lines = ["---", "tags:"] + [f"  - {t}" for t in tags]
    for k, v in kv.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, list):
            lines.append(f"{k}:")
            lines += [f"  - {yq(x)}" for x in v]
        else:
            lines.append(f"{k}: {yq(v)}")
    return "\n".join(lines + ["---", ""])


def tagify(s: str) -> str:
    return re.sub(r"[^a-z0-9_/-]+", "-", str(s or "other").lower()).strip("-") or "other"


def oneline(s: str, n: int = 300) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + " ..."


def callout(kind: str, title: str, body_lines, fold: str = "") -> str:
    out = [f"> [!{kind}]{fold} {title}".rstrip()]
    for b in body_lines:
        for ln in str(b).splitlines() or [""]:
            out.append("> " + ln if ln else ">")
    return "\n".join(out)


def md_table(head, rows) -> str:
    if not rows:
        return ""
    clean = lambda c: str(c if c is not None else "-").replace("\\|", "|").replace("|", "\\|").replace("\n", " ")  # noqa: E731
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(clean(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def section(md: str, heading_rx: str) -> str:
    """The text under the first markdown heading matching heading_rx, up to the next heading of the same or higher level."""
    lines = md.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m and re.search(heading_rx, m.group(2), re.I):
            lvl, out = len(m.group(1)), []
            for ln2 in lines[i + 1:]:
                m2 = re.match(r"^(#{1,6})\s", ln2)
                if m2 and len(m2.group(1)) <= lvl:
                    break
                out.append(ln2)
            return "\n".join(out).strip()
    return ""


def first_para(md: str, n: int = 500) -> str:
    for p in re.split(r"\n\s*\n", md or ""):
        p = p.strip()
        if p and not p.startswith(("#", "|", "```", "---")):
            return oneline(p, n)
    return ""


def unlink_md(text: str) -> str:
    """Repo text dropped into a note: [[...]] would create dangling links, so brackets become parentheses."""
    return str(text or "").replace("[[", "(").replace("]]", ")")


# ------------------------------------------------------------------------------------------------ sources
def parse_fm(text: str):
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for ln in m.group(1).splitlines():
        mm = re.match(r"^([a-z_]+):\s*(.*)$", ln)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip()
    return fm, text[m.end():]


def verdict_of(status: str) -> str:
    s = (status or "").lower().strip()
    head = re.split(r"[;:(.]| - ", s, maxsplit=1)[0]
    for part in (head, s):
        for key, word in (("reject", "rejected"), ("adopted", "adopted"), ("adopt", "adopt-candidate"), ("promising", "promising"),
                          ("finding", "finding"), ("info", "info")):
            if key in part:
                return word
    return "research"


VERDICT_CALLOUT = {"rejected": "failure", "adopt-candidate": "success", "adopted": "success", "promising": "tip", "finding": "info",
                   "info": "note", "research": "abstract"}


def writeups(root: str) -> list:
    out = []
    for p in sorted(glob.glob(os.path.join(root, "research", "writeups", "*.md"))):
        stem = os.path.basename(p)[:-3]
        if stem.upper() == "INDEX":
            continue
        txt = read_text(p)
        fm, body = parse_fm(txt)
        title = fm.get("title") or (re.search(r"^#\s+(.+)$", body, re.M).group(1) if re.search(r"^#\s+(.+)$", body, re.M) else stem)
        date = fm.get("date") or (re.search(r"(20\d\d-\d\d-\d\d)", stem).group(1) if re.search(r"(20\d\d-\d\d-\d\d)", stem) else "")
        refs = sorted(set(re.findall(r"([a-z0-9][a-z0-9._-]{2,80})\.md\b", body)) - {stem})
        out.append({"stem": stem, "name": fname(stem), "title": oneline(title, 400), "short": oneline(re.split(r" - | \(|: ", title)[0], 90),
                    "family": tagify(fm.get("family") or "other"), "date": date, "status": oneline(fm.get("status") or "", 500),
                    "verdict": verdict_of(fm.get("status") or ""), "summary": fm.get("summary") or first_para(body, 900),
                    "runs": fm.get("runs") or "", "refs": refs, "body": body, "money": section(body, r"money first|verdict|bottom line")})
    return out


def rejected_bullets(root: str) -> list:
    """docs/TESTED_AND_REJECTED.md: one item per top-level bullet: {title, text, refs}."""
    md = read_text(os.path.join(root, "docs", "TESTED_AND_REJECTED.md"))
    items, cur = [], None
    for ln in md.splitlines():
        if ln.startswith("- "):
            cur = {"lines": [ln[2:]]}
            items.append(cur)
        elif cur is not None and ln.startswith((" ", "\t")) and ln.strip():
            cur["lines"].append(ln.strip())
        elif not ln.strip() or ln.startswith("#"):
            cur = None
    out = []
    for it in items:
        text = " ".join(it["lines"])
        m = re.match(r"\*\*(.+?)\*\*:?\s*(.*)$", text)
        title, rest = (m.group(1), m.group(2)) if m else (oneline(text, 80), text)
        title = re.sub(r"\s*\(.*$", "", title).strip(" :") or oneline(title, 80)
        out.append({"title": oneline(title, 120), "text": text, "rest": rest,
                    "refs": sorted(set(re.findall(r"([a-z0-9][a-z0-9._-]{2,80})\.md\b", text)))})
    return out


def board_events(root: str) -> list:
    b = read_json(os.path.join(root, "tools", "web_public", "board", "board.json"), {}) or {}
    ev = [e for e in (b.get("events") or []) if isinstance(e, dict)]
    ev += read_jsonl(os.path.join(root, "data", "board", "shared.jsonl"))
    seen, out = set(), []
    for e in ev:
        k = e.get("id") or (e.get("t"), e.get("kind"), e.get("text"))
        if k in seen or not e.get("t"):
            continue
        seen.add(k)
        out.append(e)
    return sorted(out, key=lambda e: (e.get("t") or 0, str(e.get("id"))))


def et_day_hm(t):
    import datetime as dt
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/New_York")
    except Exception:  # noqa: BLE001
        tz = dt.timezone(dt.timedelta(hours=-5))
    d = dt.datetime.fromtimestamp(float(t), tz)
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M")


def reviews(root: str) -> dict:
    """ZEUS daily reviews (engine/zeus_review on the PC: logs/zeus/review_<day>.json; pulled copies data/pc_days/<day>/review.json)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(root, "logs", "zeus", "review_*.json")) + glob.glob(os.path.join(root, "data", "pc_days", "*", "review.json"))):
        r = read_json(p, {}) or {}
        day = r.get("day") or (re.search(r"(20\d\d-\d\d-\d\d)", p).group(1) if re.search(r"(20\d\d-\d\d-\d\d)", p) else None)
        if day and isinstance(r, dict):
            out[day] = r
    return out


# ------------------------------------------------------------------------------------------------ strategies
BOT_ACCT = {"zlarior": "zlarior", "atlas": "atlas"}
STRAT = {   # key: (note name, keyword regex over write-up stems / titles and rejected bullets, tags)
    "lit": ("Zlarior (LIT)", r"\blit\b|zlarior|lit-|-lit", ["bot/zlarior", "market/nq"]),
    "atlas": ("ATLAS", r"atlas|second-|\bsecond\b|stophunt", ["bot/atlas", "market/nq"]),
    "blitz": ("BLITZ (paper)", r"blitz|scalp", ["bot/blitz", "market/nq", "paper"]),
    "rapid": ("Rapid lanes", r"rapid", ["lane/rapid", "market/nq"]),
    "combo": ("50K combo", r"combo", ["lane/combo50k", "market/nq"]),
    "k8": ("Kalshi K8", r"\bk8\b|kalshi", ["bot/kalshi", "market/kalshi"]),
}


def strat_of(text: str) -> list:
    t = (text or "").lower()
    return [k for k, (_, rx, _) in STRAT.items() if re.search(rx, t)]


def perf_table(spans: dict) -> str:
    order = [("H1", "Jan-Jun 2026 (picked on)"), ("H2", "Jul-Oct 2026 (check)"), ("2026", "2026 all"), ("2021-25", "2021-25 (reference)")]
    rows = []
    for k, lab in order:
        s = (spans or {}).get(k)
        if isinstance(s, dict):
            rows.append([lab, s.get("n"), s.get("tpw"), f"{s.get('win')}%", s.get("pf"), usd(s.get("net"), True), usd(s.get("per_month"), True), usd(s.get("dd"))])
    return md_table(["Period", "Trades", "Per week", "Win", "PF", "Net", "Per month", "Max DD"], rows)


# ------------------------------------------------------------------------------------------------ the build
class Brain:
    def __init__(self, root: str):
        self.root = root
        self.notes: dict = {}               # rel path (inside SUB) -> text
        self.names: dict = {}               # basename -> rel path
        self.W = writeups(root)
        self.Wby = {w["stem"]: w for w in self.W}
        self.R = rejected_bullets(root)
        self.events = board_events(root)
        self.reviews = reviews(root)
        tr = read_json(os.path.join(root, "tools", "web_public", "trading", "trades.json"), {}) or {}
        self.trades = sorted([t for t in (tr.get("trades") or []) if isinstance(t, dict) and t.get("day")],
                             key=lambda t: (t.get("day"), t.get("hm") or "", str(t.get("id"))))
        self.board = read_json(os.path.join(root, "tools", "web_public", "board", "board.json"), {}) or {}
        self.plan = read_json(os.path.join(root, "tools", "web_public", "business", "accounts.json"), {}) or {}
        self.decisions = read_json(os.path.join(root, "tools", "web_public", "business", "decisions.json"), {}) or {}
        self.explain = read_json(os.path.join(root, "research", "anatomy", "explain.json"), {}) or {}
        self.second = read_json(os.path.join(root, "second_model.json"), {}) or {}
        self.inbox = []

    # -- registry
    def add(self, folder: str, name: str, text: str):
        name = fname(name)
        rel = os.path.join(folder, name + ".md") if folder else name + ".md"
        self.notes[rel] = scrub(text.rstrip() + "\n")
        self.names[name] = rel
        return name

    def wl(self, stem: str) -> str:
        w = self.Wby.get(stem)
        return link(w["name"], w["short"]) if w else ""

    # -- names known before the text is written (so every note can link to the rest)
    def plan_names(self):
        self.days = sorted({t["day"] for t in self.trades} | {et_day_hm(e["t"])[0] for e in self.events}
                           | {w["date"] for w in self.W if re.match(r"^20\d\d-\d\d-\d\d$", w["date"])} | set(self.reviews))
        self.months = sorted({d[:7] for d in self.days})
        self.families = sorted({w["family"] for w in self.W})
        self.accounts = [a for a in (self.board.get("accounts") or self.plan.get("accounts") or []) if isinstance(a, dict) and a.get("name")]

    def acct_note(self, a) -> str:
        return fname("Account " + str(a.get("name")).replace("#", "no "))

    # ================================================================ research
    def research(self):
        for w in self.W:
            ss = strat_of(w["stem"] + " " + w["title"] + (" kalshi" if w["family"] == "kalshi" else ""))
            rel = [link(STRAT[k][0]) for k in ss]
            day = f"Day {w['date']}" if w["date"] in self.days else ""
            refs = [self.wl(r) for r in w["refs"] if r in self.Wby]
            body = [front(["zeus/research", f"family/{w['family']}", f"verdict/{w['verdict']}"] + [STRAT[k][2][0] for k in ss],
                          type="research", date=w["date"], status=oneline(w["status"], 200), source=f"research/writeups/{w['stem']}.md",
                          aliases=[w["short"]]),
                    f"# {w['short']}", "",
                    callout(VERDICT_CALLOUT.get(w["verdict"], "abstract"), f"Verdict: {w['verdict']}", [unlink_md(w["status"]) or "(no status line)"]), "",
                    f"**Full title:** {unlink_md(w['title'])}", "",
                    "## Summary", "", unlink_md(w["summary"]) or "(no summary)", ""]
            if w["money"]:
                body += ["## Money first", "", unlink_md(w["money"])[:6000], ""]
            body += ["## Links", "", f"- Family: {link('Family ' + w['family'])}"]
            if day:
                body.append(f"- Day: {link(day)}")
            if rel:
                body.append("- Strategies: " + ", ".join(rel))
            if refs:
                body.append("- Refers to: " + ", ".join(refs))
            if w["runs"]:
                body.append(f"- Runs: `{w['runs'][:300]}`")
            body += [f"- Source: `research/writeups/{w['stem']}.md`", f"- Back to {link('ZEUS Home')}"]
            self.add("Research", w["name"], "\n".join(body))

    def families_notes(self):
        for f in self.families:
            ws = sorted([w for w in self.W if w["family"] == f], key=lambda w: (w["date"], w["stem"]), reverse=True)
            cnt = {}
            for w in ws:
                cnt[w["verdict"]] = cnt.get(w["verdict"], 0) + 1
            lines = [front(["zeus/family", f"family/{f}"], type="family"), f"# Research family: {f}", "",
                     callout("abstract", f"{len(ws)} write-ups", [", ".join(f"{k} {v}" for k, v in sorted(cnt.items()))]), "",
                     md_table(["Date", "Write-up", "Verdict"], [[w["date"], link(w["name"], w["short"]), w["verdict"]] for w in ws]), "",
                     f"Back to {link('ZEUS Home')} · {link('ZEUS Lessons')}"]
            self.add("Families", "Family " + f, "\n".join(lines))

    # ================================================================ strategies
    def related(self, key: str):
        rx = STRAT[key][1]
        ws = [w for w in self.W if re.search(rx, (w["stem"] + " " + w["title"] + (" kalshi" if w["family"] == "kalshi" else "")).lower())]
        rj = [r for r in self.R if re.search(rx, (r["title"] + " " + r["rest"][:240]).lower())]
        return sorted(ws, key=lambda w: (w["date"], w["stem"]), reverse=True), rj

    def rejected_block(self, rj) -> list:
        if not rj:
            return ["_Nothing on the rejected list names this one yet._"]
        out = []
        for r in rj:
            refs = [self.wl(x) for x in r["refs"] if x in self.Wby]
            out.append(callout("failure", r["title"], [oneline(unlink_md(r["rest"]), 700)] + (["Write-ups: " + ", ".join(refs)] if refs else []), "-"))
            out.append("")
        return out

    def research_block(self, ws, n: int = 40) -> list:
        if not ws:
            return ["_No write-ups yet._"]
        rows = [[w["date"], link(w["name"], w["short"]), w["verdict"]] for w in ws[:n]]
        more = [f"", f"... and {len(ws) - n} older (see the families)."] if len(ws) > n else []
        return [md_table(["Date", "Write-up", "Verdict"], rows)] + more

    def live_block(self, acct: str | None, bot: str | None) -> list:
        tr = [t for t in self.trades if (acct is None or t.get("acct") == acct) and (bot is None or t.get("bot") == bot)]
        if not tr:
            return ["_No trades in the published trade list._"]
        by = {}
        for t in tr:
            k = (t["day"][:7], t.get("src") or "?")
            n, s = by.get(k, (0, 0.0))
            by[k] = (n + 1, s + float(t.get("usd") or 0))
        rows = [[link(f"Month {m}", m), src, n, usd(s, True)] for (m, src), (n, s) in sorted(by.items())]
        return [md_table(["Month", "Source", "Trades", "Net $"], rows), "",
                "_backtest = the bot's rules replayed on futures data (costs in); paper / live = what the bot really did._"]

    def strategies(self):
        sp = (self.explain.get("bots") or {})
        md = read_text(os.path.join(self.root, "STRATEGY.md"))
        # ---- Zlarior (LIT)
        ws, rj = self.related("lit")
        rules = []
        for m in re.finditer(r"^## (\d+)\. (.+)$", md, re.M):
            txt = first_para(section(md, re.escape(m.group(2))), 420)
            rules.append(f"{m.group(1)}. **{m.group(2)}**: {unlink_md(txt)}")
        perf_md = section(md, r"^How LIT performed")
        tab = "\n".join(ln for ln in perf_md.split("\n\n", 2)[1].splitlines() if ln.startswith("|")) if perf_md.count("\n\n") >= 1 else ""
        self.strategy_note("lit", "Zlarior (LIT)", "Liquidity Inducement on NQ (MNQ micros): sweep, inducement, 5m shift, 1m entry; one target.",
                           first_para(md, 700), rules, sp.get("lit"), tab, ws, rj, acct="zlarior", bot="LIT",
                           extra=[f"- Account: {link('Account Zlarior')}" if any(a.get("name") == "Zlarior" for a in self.accounts) else ""])
        # ---- ATLAS + members
        ws, rj = self.related("atlas")
        mem = []
        for key in sorted((self.second.get("strategies") or {})):
            s = self.second["strategies"][key]
            if not isinstance(s, dict):
                continue
            nm = fname(f"ATLAS member {s.get('short') or key} ({key})")
            mem.append((nm, s, key))
            wr = s.get("writeup")
            lines = [front(["zeus/strategy", "bot/atlas", "atlas/member", "market/nq"], type="strategy-member", key=key,
                           on=str(bool(s.get("on"))), route=str(bool(s.get("route")))),
                     f"# {s.get('label') or key}", "",
                     callout("success" if s.get("on") else "warning", "On" if s.get("on") else "Off",
                             [f"Key `{key}` · routed to an account: {'yes' if s.get('route') else 'no (paper)'}" + (" · candidate (paper only)" if s.get("candidate") else "")]), "",
                     "## Rules in plain words", "", unlink_md(s.get("summary") or "(no summary)"), "",
                     "## Links", "", f"- Part of {link('ATLAS')}"]
            if wr and wr in self.Wby:
                lines.append(f"- Write-up: {self.wl(wr)}")
            self.add("Strategies", nm, "\n".join(lines))
        rules = [f"- {link(nm, s.get('label') or k)}: {'ON' if s.get('on') else 'off'}{' (routed)' if s.get('route') else ''}" for nm, s, k in mem]
        self.strategy_note("atlas", "ATLAS", "The second-strategy team next to LIT (engine/second.py): each member is its own rule; ATLAS trades them on its own account.",
                           unlink_md(oneline(self.second.get("note") or "", 700)), rules, sp.get("atlas"), "", ws, rj, acct="atlas", bot="ATLAS",
                           extra=[f"- Account: {link('Account ATLAS')}" if any(a.get("name") == "ATLAS" for a in self.accounts) else ""], rules_title="Members")
        # ---- BLITZ
        bmd = read_text(os.path.join(self.root, "BLITZ_STRATEGY.md"))
        ws, rj = self.related("blitz")
        rule = section(bmd, r"^The rule")
        self.strategy_note("blitz", "BLITZ (paper)", "The scalper on a Builder 25K. Hidden on the site, paper only.",
                           first_para(section(bmd, r"^Money first"), 900), [unlink_md(x) for x in rule.splitlines() if x.strip()][:30],
                           sp.get("blitz"), "", ws, rj, acct=None, bot="BLITZ")
        # ---- Rapid
        rmd = read_text(os.path.join(self.root, "docs", "RAPID_EOD_SETUP.md"))
        ws, rj = self.related("rapid")
        steps = [f"- **{m.group(1)}**" for m in re.finditer(r"^## (.+)$", rmd, re.M)]
        self.strategy_note("rapid", "Rapid lanes", "MFFU Rapid EOD accounts: Zlarior (LIT) and ATLAS together, one trade at a time.",
                           first_para(rmd, 700), steps, None, "", ws, rj, acct=None, bot=None,
                           extra=[f"- Uses {link('Zlarior (LIT)')} and {link('ATLAS')}"])
        # ---- combo
        cdoc = read_text(os.path.join(self.root, "engine", "combo50k.py"))
        m = re.match(r'\s*"""(.*?)"""', cdoc, re.S)
        ws, rj = self.related("combo")
        self.strategy_note("combo", "50K combo", "ATLAS + Zlarior on ONE Builder 50K (engine/combo50k.py). Built, OFF by default.",
                           first_para(m.group(1) if m else "", 900), [], None, "", ws, rj, acct=None, bot=None,
                           extra=[f"- Combines {link('Zlarior (LIT)')} and {link('ATLAS')}"])
        # ---- Kalshi K8
        k8 = self.explain.get("kalshi_k8") or {}
        ws, rj = self.related("k8")
        legs = []
        for lg in k8.get("legs") or []:
            nm = fname("K8 leg " + str(lg.get("leg")).replace(":", "."))
            legs.append(f"- {link(nm, lg.get('leg'))}: {lg.get('n')} bets, won {lg.get('won')}%, {usd(lg.get('usd'), True)}")
            self.add("Strategies", nm, "\n".join([
                front(["zeus/strategy", "bot/kalshi", "kalshi/k8-leg", "market/kalshi"], type="strategy-member", leg=lg.get("leg")),
                f"# K8 leg: {lg.get('leg')}", "",
                callout("money", "How it did", [f"{lg.get('n')} bets · won {lg.get('won')}% · {usd(lg.get('usd'), True)} · "
                                                f"average win {usd(lg.get('avg_win'))} / average loss {usd(lg.get('avg_loss'))}"]), "",
                f"Part of {link('Kalshi K8')} · {link('ZEUS Kalshi')}"]))
        a = k8.get("all") or {}
        perf = md_table(["Span", "Bets", "Won", "Net"], [[f"{k8.get('first')} to {k8.get('last')}", a.get("n"), f"{a.get('won')}%", usd(a.get("usd"), True)]]) if a else ""
        self.strategy_note("k8", "Kalshi K8", "Kalshi gold / silver range legs at fixed times (research/kalshi_edge_K8).", "", legs, None, perf, ws, rj,
                           acct=None, bot=None, say=k8.get("say"), rules_title="Legs", extra=[f"- Hub: {link('ZEUS Kalshi')}"])

    def strategy_note(self, key, name, tagline, intro, rules, spans, extra_table, ws, rj, acct=None, bot=None, extra=None, say=None, rules_title="Rules in plain words"):
        sp = spans or {}
        lines = [front(["zeus/strategy"] + STRAT[key][2], type="strategy", key=key), f"# {name}", "",
                 callout("abstract", tagline, [unlink_md(intro)] if intro else []), ""]
        if rules:
            lines += [f"## {rules_title}", ""] + rules + [""]
        lines += ["## Performance by period", ""]
        if sp.get("spans"):
            lines += [perf_table(sp["spans"]), "", "_From research/anatomy/explain.json (costs in)._", ""]
        if extra_table:
            lines += [extra_table, ""]
        if not sp.get("spans") and not extra_table:
            lines += ["_No period table published for this one yet; see the write-ups._", ""]
        if bot or acct:
            lines += ["### Trades by month", ""] + self.live_block(acct, bot) + [""]
        said = say if say is not None else sp.get("say")
        if said:
            lines += ["## Why it wins and loses", ""] + [f"- {unlink_md(s)}" for s in said[:12]] + [""]
        lines += ["## Tested and rejected", ""] + self.rejected_block(rj) + ["", "## Write-ups", ""] + self.research_block(ws) + [""]
        lines += ["## Links", ""] + [e for e in (extra or []) if e] + [f"- {link('ZEUS Lessons')} · {link('ZEUS Decisions')} · {link('ZEUS Home')}"]
        self.add("Strategies", name, "\n".join(lines))

    # ================================================================ accounts
    def account_notes(self):
        plan_by = {p.get("key"): p for p in (self.plan.get("accounts") or []) if isinstance(p, dict)}
        for a in self.accounts:
            p = plan_by.get(a.get("key"), {})
            pcs = [x for x in (a.get("pc") or p.get("pc") or []) if isinstance(x, str)]
            bots = sorted({STRAT[k][0] for k in ("lit", "atlas") if any(k in x for x in pcs)})
            if "rapid" in str(a.get("plan", "")).lower():
                bots.append("Rapid lanes")
            ev = [e for e in self.events if e.get("acct") == a.get("key")]
            rows = [["Plan", a.get("plan")], ["Stage", a.get("stage")], ["Status", a.get("status")], ["Balance", usd(a.get("balance"))],
                    ["Room left", usd(a.get("room"))], ["To pass", usd(a.get("to_pass"))], ["Target balance", usd(a.get("target_balance"))],
                    ["Locked", "yes" if a.get("locked") else "no"], ["Numbers from", a.get("src")]]
            lines = [front(["zeus/account", f"account/{tagify(a.get('key'))}"], type="account", plan=a.get("plan"), stage=a.get("stage")),
                     f"# {a.get('name')}", "",
                     callout("money", f"{a.get('plan')} · {a.get('stage')}", [unlink_md(p.get("next") or "")] if p.get("next") else []), "",
                     md_table(["", ""], rows), ""]
            if p:
                lines += ["## Plan", ""] + [f"- **{k}**: {unlink_md(p.get(k))}" for k in ("bots", "payout", "usd_month", "cost") if p.get(k)] + [""]
            lines += ["## Bots", ""] + ([f"- {link(b)}" for b in bots] or ["_none yet_"]) + [""]
            lines += ["## History (board events)", ""]
            lines += [f"- {link('Day ' + et_day_hm(e['t'])[0], et_day_hm(e['t'])[0])} {et_day_hm(e['t'])[1]} ET · {e.get('kind')}: {unlink_md(oneline(e.get('text'), 300))}" for e in ev] or ["_no events yet_"]
            lines += ["", "## Trades by month", ""] + self.live_block(a.get("key"), None) + ["", f"Back to {link('ZEUS Home')}"]
            self.add("Accounts", self.acct_note(a), "\n".join(lines))

    # ================================================================ days / months
    def day_notes(self):
        wd = {}
        for w in self.W:
            wd.setdefault(w["date"], []).append(w)
        for i, d in enumerate(self.days):
            tr = [t for t in self.trades if t["day"] == d]
            ev = [e for e in self.events if et_day_hm(e["t"])[0] == d]
            rv = self.reviews.get(d)
            nav = [link(f"Day {self.days[i - 1]}", "<- " + self.days[i - 1]) if i else "", link(f"Month {d[:7]}", d[:7]),
                   link(f"Day {self.days[i + 1]}", self.days[i + 1] + " ->") if i + 1 < len(self.days) else ""]
            tot = {}
            for t in tr:
                k = f"{t.get('bot')} {t.get('src') or ''}".strip()
                tot[k] = tot.get(k, 0.0) + float(t.get("usd") or 0)
            tags = ["zeus/day"] + sorted({f"bot/{tagify(t.get('bot'))}" for t in tr}) + (["zeus/review"] if rv else [])
            lines = [front(tags, type="day", date=d), f"# {d}", "", " · ".join(x for x in nav if x), ""]
            if tot:
                lines += [callout("money", "The day in $", [" · ".join(f"{b}: {usd(v, True)}" for b, v in sorted(tot.items()))]), ""]
            if tr:
                bl = {"LIT": "Zlarior (LIT)", "ATLAS": "ATLAS", "BLITZ": "BLITZ (paper)"}
                lines += ["## Trades", "", md_table(["Time", "Bot", "Source", "Side", "Micros", "Exit", "R", "$"],
                                                    [[t.get("hm"), link(bl[t.get("bot")]) if t.get("bot") in bl else t.get("bot"), t.get("src"),
                                                      t.get("side"), t.get("q"), t.get("k"), t.get("r"), usd(t.get("usd"), True)] for t in tr]), ""]
            if ev:
                lines += ["## Board", ""] + [f"- {et_day_hm(e['t'])[1]} ET · {e.get('kind')} ({e.get('src')}): {unlink_md(oneline(e.get('text'), 300))}" for e in ev] + [""]
            if rv:
                txt = rv.get("text") if isinstance(rv.get("text"), str) else "\n".join(map(str, rv.get("text") or []))
                lines += ["## ZEUS daily review", "", callout("info", "What the bot learned today", [unlink_md(txt or oneline(json.dumps(rv.get("items"))[:600]))]), ""]
            if wd.get(d):
                lines += ["## Research written", ""] + [f"- {link(w['name'], w['short'])} ({w['verdict']})" for w in sorted(wd[d], key=lambda w: w["stem"])] + [""]
            self.add("Days", f"Day {d}", "\n".join(lines))
        for m in self.months:
            ds = [d for d in self.days if d.startswith(m)]
            rows = []
            for d in ds:
                tr = [t for t in self.trades if t["day"] == d]
                rows.append([link(f"Day {d}", d), len(tr), usd(sum(float(t.get("usd") or 0) for t in tr), True) if tr else "-",
                             len([w for w in self.W if w["date"] == d])])
            self.add("Months", f"Month {m}", "\n".join([front(["zeus/month"], type="month", month=m), f"# {m}", "",
                                                         md_table(["Day", "Trades", "Net $", "Write-ups"], rows), "", f"Back to {link('ZEUS Home')}"]))

    # ================================================================ hubs
    def lessons(self):
        lines = [front(["zeus/lessons"], type="lessons"), "# ZEUS Lessons", "",
                 callout("tip", "This note grows by itself", ["Every night it is rebuilt from the loss anatomy, the rejected list and the newest write-ups. "
                                                              "Don't redo a rejected idea without a new angle."]), ""]
        lines += ["## Why we lose (loss clusters)", "", f"_Built {self.explain.get('built', '-')}, research/anatomy/explain.json._", ""]
        for b, v in sorted((self.explain.get("bots") or {}).items()):
            nm = {"lit": "Zlarior (LIT)", "atlas": "ATLAS", "blitz": "BLITZ (paper)"}.get(b)
            if v.get("say"):
                lines += [f"### {link(nm) if nm else b}", ""] + [f"- {unlink_md(s)}" for s in v["say"]] + [""]
        k8 = self.explain.get("kalshi_k8") or {}
        if k8.get("say"):
            lines += [f"### {link('Kalshi K8')}", ""] + [f"- {unlink_md(s)}" for s in k8["say"]] + [""]
        lines += ["## Rejected idea families", "", f"{len(self.R)} entries from docs/TESTED_AND_REJECTED.md, newest first.", ""]
        for r in self.R:
            ss = strat_of(r["title"] + " " + r["rest"][:240])
            refs = [self.wl(x) for x in r["refs"] if x in self.Wby]
            tail = (" · " + ", ".join(link(STRAT[k][0]) for k in ss) if ss else "") + (" · " + ", ".join(refs[:4]) if refs else "")
            lines.append(f"- **{unlink_md(r['title'])}**{tail}")
        rej = sorted([w for w in self.W if w["verdict"] == "rejected"], key=lambda w: (w["date"], w["stem"]), reverse=True)
        lines += ["", "## Rejected in the write-ups", ""] + [f"- {w['date']} {link(w['name'], w['short'])} ({link('Family ' + w['family'], w['family'])})" for w in rej]
        good = sorted([w for w in self.W if w["verdict"] in ("adopt-candidate", "adopted", "promising")], key=lambda w: (w["date"], w["stem"]), reverse=True)
        lines += ["", "## What worked or looks promising", ""] + [f"- {w['date']} {link(w['name'], w['short'])} ({w['verdict']})" for w in good]
        lines += ["", f"Back to {link('ZEUS Home')}"]
        self.add("", "ZEUS Lessons", "\n".join(lines))

    def decisions_note(self):
        items = [i for i in (self.decisions.get("items") or []) if isinstance(i, dict)]
        groups = {}
        for i in items:
            groups.setdefault(str(i.get("status") or "open"), []).append(i)
        lines = [front(["zeus/decisions"], type="decisions"), "# ZEUS Decisions", "",
                 callout("question", f"{len(groups.get('open', []))} open", ["Answer on the Decide card (Business app). A yes means Claude tests it; nothing live changes without proof."]), ""]
        for st in ["open", "yes", "no", "later"] + sorted(set(groups) - {"open", "yes", "no", "later"}):
            if not groups.get(st):
                continue
            lines += [f"## {st.capitalize()}", ""]
            for i in groups[st]:
                src = os.path.basename(str(i.get("source") or ""))[:-3] if str(i.get("source") or "").endswith(".md") else ""
                body = [f"**Why:** {unlink_md(i.get('why'))}" if i.get("why") else "", f"**Impact:** {unlink_md(i.get('impact'))}" if i.get("impact") else "",
                        f"Added {i.get('added')}" + (f" · write-up {self.wl(src)}" if src in self.Wby else "") + (f" · id `{i.get('id')}`" if i.get("id") else "")]
                lines += [callout({"open": "question", "yes": "success", "no": "failure"}.get(st, "note"), unlink_md(oneline(i.get("question"), 200)), [b for b in body if b], "-" if st != "open" else ""), ""]
        lines += [f"Back to {link('ZEUS Home')}"]
        self.add("", "ZEUS Decisions", "\n".join(lines))

    def apps(self):
        md = read_text(os.path.join(self.root, "docs", "OLYMPUS_MAP.md"))
        rows = []
        for ln in md.splitlines():
            if ln.startswith("| ") and not ln.startswith("| App (id)") and not re.match(r"^\|\s*-", ln):
                c = [x.strip() for x in ln.strip().strip("|").split("|")]
                if len(c) >= 6:
                    rows.append(c)
        doors = {}
        for c in rows:
            doors.setdefault(c[1], []).append(c)
        for d, rs in doors.items():
            self.add("Apps", f"Apps {d}", "\n".join([front(["zeus/apps", f"door/{tagify(d)}"], type="apps", door=d), f"# {d}", "",
                                                     md_table(["App", "Group", "What it is", "Data", "Test"], [[r[0], r[2], r[3], r[4], r[5]] for r in rs]), "",
                                                     f"Back to {link('ZEUS Apps')}"]))
        intro = [unlink_md(oneline(p, 600)) for p in re.split(r"\n\s*\n", md) if p.strip() and not p.lstrip().startswith(("#", "|"))][:4]
        code = section(md, r"organizing code")
        lines = [front(["zeus/apps", "jarvis"], type="apps"), "# ZEUS Apps (Olympus + Jarvis)", "",
                 callout("info", f"{len(rows)} apps behind {len(doors)} doors", intro[:1]), ""] + intro[1:] + [""]
        lines += ["## Doors", ""] + [f"- {link('Apps ' + fname(d), d)}: {len(rs)} apps" for d, rs in doors.items()]
        if code:
            lines += ["", "## Where the organizing code lives", "", unlink_md(code)]
        lines += ["", f"Back to {link('ZEUS Home')}"]
        self.add("", "ZEUS Apps", "\n".join(lines))

    def kalshi(self):
        docs = sorted(glob.glob(os.path.join(self.root, "docs", "KALSHI*.md")))
        lines = [front(["zeus/kalshi", "market/kalshi"], type="kalshi"), "# ZEUS Kalshi", "",
                 callout("abstract", "Kalshi in one place", [f"Strategy: {link('Kalshi K8')} · research family: {link('Family kalshi')}" if "kalshi" in self.families else f"Strategy: {link('Kalshi K8')}"]), "",
                 "## The docs", ""]
        for p in docs:
            t = read_text(p)
            h = re.search(r"^#\s+(.+)$", t, re.M)
            lines.append(f"- **{unlink_md(h.group(1) if h else os.path.basename(p))}** (`docs/{os.path.basename(p)}`): {unlink_md(first_para(t, 300))}")
        et = read_text(os.path.join(self.root, "research", "kalshi", "edge_tables.md"))
        if et.strip():
            lines += ["", "## Edge tables", "", callout("note", "research/kalshi/edge_tables.md", [unlink_md(et.strip())[:9000]], "-")]
        ws = sorted([w for w in self.W if w["family"] == "kalshi" or "kalshi" in w["stem"]], key=lambda w: (w["date"], w["stem"]), reverse=True)
        lines += ["", "## Kalshi research", ""] + self.research_block(ws, 60) + ["", f"Back to {link('ZEUS Home')}"]
        self.add("", "ZEUS Kalshi", "\n".join(lines))

    def state(self):
        st = read_text(os.path.join(self.root, "STATE.md"))
        self.add("", "ZEUS State", front(["zeus/state"], type="state", source="STATE.md") + "# STATE (what's live, waiting, next)\n\n"
                 + unlink_md(st.strip() or "_STATE.md not found_") + f"\n\nBack to {link('ZEUS Home')}")

    def home(self):
        accts = [[link(self.acct_note(a), a.get("name")), a.get("plan"), a.get("stage"), usd(a.get("balance")), usd(a.get("room")), usd(a.get("to_pass"))]
                 for a in self.accounts]
        strat = [f"- {link(v[0])}" for v in STRAT.values()]
        opn = [i for i in (self.decisions.get("items") or []) if isinstance(i, dict) and (i.get("status") or "open") == "open"]
        last = self.days[-DAYS_ON_HOME:][::-1]
        newest = sorted(self.W, key=lambda w: (w["date"], w["stem"]), reverse=True)[:RESEARCH_ON_HOME]
        lines = [front(["zeus/home"], type="home"), "# ZEUS Brain", "",
                 callout("zeus", "Everything ZEUS knows, rebuilt every night", [
                     f"{len(self.accounts)} accounts · {len(STRAT)} strategies · {len(self.W)} write-ups · {len(self.days)} days · "
                     f"{len(self.R)} rejected idea families · {len(opn)} open decisions",
                     f"Data up to {self.days[-1] if self.days else '-'}. Generated by tools/obsidian_brain.py: don't edit here, write in {INBOX}/."]), "",
                 "## Accounts", "", md_table(["Account", "Plan", "Stage", "Balance", "Room", "To pass"], accts) or "_no accounts published_", "",
                 "## Strategies and bots", ""] + strat + ["",
                 "## The big notes", "",
                 f"- {link('ZEUS Decisions')}: {len(opn)} open",
                 f"- {link('ZEUS Lessons')}: what lost money and what was rejected",
                 f"- {link('ZEUS Apps')}: Olympus + Jarvis apps map",
                 f"- {link('ZEUS Kalshi')}",
                 f"- {link('ZEUS State')}: what's live, what's waiting", "",
                 "## Last days", ""] + [f"- {link('Day ' + d, d)}" for d in last] + ["",
                 "## Newest research", ""] + [f"- {w['date']} {link(w['name'], w['short'])} ({w['verdict']})" for w in newest] + ["",
                 "## Research families", "", " · ".join(link("Family " + f, f) for f in self.families), "",
                 "## Months", "", " · ".join(link("Month " + m, m) for m in self.months), ""]
        lines += ["## Your notes (Inbox)", ""] + ([f"- {link(n)}" for n in self.inbox] or [f"_Write anything in {INBOX}/: it is never overwritten._"])
        self.add("", "ZEUS Home", "\n".join(lines))

    def build(self, inbox_names=()):
        self.inbox = sorted(inbox_names)
        self.plan_names()
        self.research()
        self.families_notes()
        self.strategies()
        self.account_notes()
        self.day_notes()
        self.lessons()
        self.decisions_note()
        self.apps()
        self.kalshi()
        self.state()
        self.home()
        return self.notes


# ------------------------------------------------------------------------------------------------ look (no plugins)
CSS = CSS_MARK + """
/* Turn on: Settings -> Appearance -> CSS snippets -> zeus. Works with the default theme, light and dark. */
.theme-dark, .theme-light { --zeus-gold: #d4a72c; --zeus-blue: #3b82f6; }
.callout[data-callout="zeus"] { --callout-color: 212, 167, 44; --callout-icon: lucide-zap; border-left: 4px solid var(--zeus-gold); }
.callout[data-callout="money"] { --callout-color: 34, 160, 90; --callout-icon: lucide-circle-dollar-sign; }
.markdown-rendered h1 { color: var(--zeus-gold); letter-spacing: .02em; border-bottom: 1px solid var(--background-modifier-border); padding-bottom: .2em; }
.markdown-rendered h2 { color: var(--zeus-blue); }
.markdown-rendered table { font-size: .92em; }
.markdown-rendered td:last-child { font-variant-numeric: tabular-nums; }
.tag[href^="#verdict/rejected"] { background: rgba(220, 60, 60, .15); color: rgb(220, 60, 60); }
.tag[href^="#verdict/adopt"] { background: rgba(34, 160, 90, .15); color: rgb(34, 160, 90); }
.tag[href^="#zeus/"] { background: rgba(212, 167, 44, .15); color: var(--zeus-gold); }
"""

GRAPH = {"collapse-filter": False, "search": "", "showTags": False, "showAttachments": False, "hideUnresolved": True, "showOrphans": False,
         "collapse-color-groups": False, "colorGroups": [
             {"query": "tag:#zeus/home", "color": {"a": 1, "rgb": 13936428}},
             {"query": "tag:#zeus/strategy", "color": {"a": 1, "rgb": 15105570}},
             {"query": "tag:#zeus/account", "color": {"a": 1, "rgb": 2269274}},
             {"query": "tag:#verdict/rejected", "color": {"a": 1, "rgb": 14433340}},
             {"query": "tag:#zeus/research", "color": {"a": 1, "rgb": 3900150}},
             {"query": "tag:#zeus/day", "color": {"a": 1, "rgb": 9807270}},
             {"query": "tag:#market/kalshi", "color": {"a": 1, "rgb": 10181046}}],
         "collapse-display": False, "showArrow": False, "textFadeMultiplier": 0, "nodeSizeMultiplier": 1.1, "lineSizeMultiplier": 1,
         "collapse-forces": True, "centerStrength": 0.5, "repelStrength": 12, "linkStrength": 1, "linkDistance": 160, "scale": 0.6, "close": False}


def workspace(home_rel: str) -> dict:
    leaf = lambda i, t, st: {"id": i, "type": "leaf", "state": {"type": t, "state": st}}  # noqa: E731
    return {"main": {"id": "zmain", "type": "split", "direction": "vertical", "children": [
                {"id": "ztabs", "type": "tabs", "children": [leaf("zhome", "markdown", {"file": home_rel, "mode": "preview", "source": False})]}]},
            "left": {"id": "zleft", "type": "split", "direction": "horizontal", "width": 280, "children": [
                {"id": "zltabs", "type": "tabs", "children": [leaf("zfiles", "file-explorer", {"sortOrder": "alphabetical"}),
                                                              leaf("zsearch", "search", {"query": "", "matchingCase": False})]}]},
            "right": {"id": "zright", "type": "split", "direction": "horizontal", "width": 300, "collapsed": True, "children": [
                {"id": "zrtabs", "type": "tabs", "children": [leaf("zback", "backlink", {"file": home_rel, "collapseAll": False}),
                                                              leaf("zlocal", "localgraph", {"file": home_rel})]}]},
            "active": "zhome", "lastOpenFiles": [home_rel]}


def inbox_start() -> str:
    return ("# ZEUS Inbox: start here\n\nThis folder is yours. ZEUS Brain never writes here again once it exists.\n\n"
            "- Write ideas, questions or trade feelings as notes here.\n- They are linked from [[ZEUS Home]] at the next rebuild.\n"
            "- Link them yourself to any note, like [[Zlarior (LIT)]] or [[ZEUS Lessons]].\n")


# ------------------------------------------------------------------------------------------------ writing
def _put(path: str, text: str, wrote: list, base: str):
    if os.path.isfile(path) and read_text(path) == text:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)
    wrote.append(os.path.relpath(path, base).replace(os.sep, "/"))


def build(vault: str, root: str = ROOT, standalone: bool = True, sub: str | None = None) -> dict:
    """Build the brain into <vault>/<sub>. Returns {ok, notes, wrote, removed, folder}. Never touches <vault>/Inbox once it exists."""
    sub = sub or (SUB if standalone else PC_SUB)
    base = os.path.join(vault, sub)
    os.makedirs(base, exist_ok=True)
    inbox = os.path.join(vault, INBOX)
    wrote, removed = [], []
    new_inbox = not os.path.isdir(inbox)
    if new_inbox and standalone:
        _put(os.path.join(inbox, "ZEUS Inbox - start here.md"), inbox_start(), wrote, vault)
    names = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(inbox, "**", "*.md"), recursive=True)) if os.path.isdir(inbox) else []
    names = [n for n in names if n == fname(n)]
    notes = Brain(root).build(names)
    for rel, text in sorted(notes.items()):
        _put(os.path.join(base, rel), text, wrote, vault)
    man_path = os.path.join(base, MANIFEST)
    old = (read_json(man_path, {}) or {}).get("files") or []
    keep = set(notes)
    for rel in old:
        rel_n = os.path.normpath(rel)
        if rel_n in keep or rel_n.startswith("..") or os.path.isabs(rel_n):
            continue
        p = os.path.join(base, rel_n)
        if os.path.isfile(p) and p.endswith(".md"):
            os.remove(p)
            removed.append(rel.replace(os.sep, "/"))
    _put(man_path, json.dumps({"v": 1, "files": sorted(k.replace(os.sep, "/") for k in keep)}, indent=0) + "\n", wrote, vault)
    snip = os.path.join(vault, ".obsidian", "snippets", "zeus.css")
    if not os.path.isfile(snip) or read_text(snip).startswith(CSS_MARK):
        _put(snip, CSS, wrote, vault)
    if standalone:
        ob = os.path.join(vault, ".obsidian")
        home_rel = f"{sub}/ZEUS Home.md".replace(os.sep, "/")
        _put(os.path.join(ob, "graph.json"), json.dumps(GRAPH, indent=1) + "\n", wrote, vault)
        _put(os.path.join(ob, "appearance.json"), json.dumps({"enabledCssSnippets": ["zeus"]}, indent=1) + "\n", wrote, vault)
        _put(os.path.join(ob, "app.json"), json.dumps({"defaultViewMode": "preview", "alwaysUpdateLinks": True, "newFileLocation": "folder",
                                                       "newFileFolderPath": INBOX}, indent=1) + "\n", wrote, vault)
        if not os.path.isfile(os.path.join(ob, "workspace.json")):
            _put(os.path.join(ob, "workspace.json"), json.dumps(workspace(home_rel), indent=1) + "\n", wrote, vault)
    return {"ok": True, "notes": len(notes), "wrote": wrote, "removed": removed, "folder": base}


def check(vault: str = REPO_VAULT, root: str = ROOT) -> list:
    """The notes (relative to <vault>/ZEUS Brain) whose committed text differs from a fresh build; [] = up to date."""
    tmp = tempfile.mkdtemp(prefix="zeus_brain_")
    try:
        if os.path.isdir(os.path.join(vault, INBOX)):
            shutil.copytree(os.path.join(vault, INBOX), os.path.join(tmp, INBOX))
        build(tmp, root)
        a, b = os.path.join(tmp, SUB), os.path.join(vault, SUB)
        diff = []
        for p in sorted(glob.glob(os.path.join(a, "**", "*.md"), recursive=True)):
            rel = os.path.relpath(p, a)
            if read_text(p) != read_text(os.path.join(b, rel)):
                diff.append(rel)
        return diff
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ZEUS Brain: build the Obsidian vault from the repo")
    ap.add_argument("--out", default=REPO_VAULT, help="standalone vault folder (default vault/)")
    ap.add_argument("--vault", default="", help="a real Obsidian vault: notes go to <vault>/OLYMPUS/ZEUS Brain (+ the CSS snippet)")
    ap.add_argument("--check", action="store_true", help="exit 1 when vault/ differs from a fresh build")
    a = ap.parse_args(argv)
    if a.check:
        d = check(a.out)
        print("ZEUS Brain up to date" if not d else f"ZEUS Brain differs in {len(d)} note(s): " + ", ".join(d[:8]))
        return 1 if d else 0
    res = build(a.vault, standalone=False) if a.vault else build(a.out)
    print(f"ZEUS Brain: {res['notes']} notes in {res['folder']} · {len(res['wrote'])} written · {len(res['removed'])} removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
