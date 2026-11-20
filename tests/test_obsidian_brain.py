"""ZEUS Brain (tools/obsidian_brain.py): the Obsidian vault generated from the repo. A fixture repo in a temp folder, no network.

  a. one build from the fixture writes Home, accounts, strategies (+ ATLAS members, K8 legs), research, families, days, months,
     Lessons, Decisions, Apps, Kalshi, State, the CSS snippet and the .obsidian look
  b. idempotent and deterministic: a second build writes nothing; two fresh builds give the same bytes
  c. no private ids: planted emails, keys, account ids, tailnet names, personal folders never reach the vault
  d. every [[link]] resolves to a note of the vault (also on the REAL repo build)
  e. Inbox/ is the owner's: never overwritten, its notes are linked from Home; the owner's own files elsewhere are never deleted;
     a note the brain no longer makes is removed (manifest only)
  f. the PC mode (<vault>/OLYMPUS/ZEUS Brain, no .obsidian rewrite except our snippet), the hooks (learn_night, obsidian_sync)
  g. the committed vault/ matches a fresh build of the repo (python tools/obsidian_brain.py rebuilds it)

    python -X utf8 -m tests.test_obsidian_brain
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import obsidian_brain as OB  # noqa: E402

RES = []
LINK_RX = re.compile(r"\[\[([^\]|#\\]+)")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"   -> {str(info)[:300]}"))


def w(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text if isinstance(text, str) else json.dumps(text))


def fixture(root):
    w(root, "research/writeups/lit-test-2026-11-18.md", "---\ntitle: LIT test idea - an example (night)\nfamily: risk\ndate: 2026-11-18\n"
      "status: rejected - nothing passes\nsummary: Mail me at owner.private@example.com about MFFU-123456789 on myhost.tail1234.ts.net\n"
      "runs: rd_x\n---\n\n## Money first\n\nNo switch. See kalshi-k8-2026-11-19.md and C:\\Users\\RealName\\Desktop\\x.\n")
    w(root, "research/writeups/kalshi-k8-2026-11-19.md", "---\ntitle: Kalshi K8 metals\nfamily: kalshi\ndate: 2026-11-19\n"
      "status: adopt-candidate\nsummary: K8 legs. token: ghp_abcdefghijklmnopqrstuvwxyz0123456789\nruns: k8\n---\n\nbody [[not a note]]\n")
    w(root, "research/writeups/atlas-plain.md", "# ATLAS plain write-up\n\nNo frontmatter here.\n")
    w(root, "docs/TESTED_AND_REJECTED.md", "## Tested and rejected\n- **LIT wider stops (2026-11-18, `lit-test-2026-11-18.md`):** worse.\n"
      "  second line.\n- **BLITZ exits (2026-11-17):** 0 pass.\n")
    w(root, "docs/OLYMPUS_MAP.md", "# OLYMPUS map\n\nEvery app.\n\n| App (id) | District | Group | What it is | Data it reads | Test |\n|---|---|---|---|---|---|\n"
      "| Board (`board`) | ZEUS Trading | trading | The board | `board.json` | `tests.test_board` |\n"
      "| Kalshi City (`kalshicity`) | Kalshi | kalshi | The city | `x.json` | `tests.test_x` |\n\n## Where the organizing code lives\n\nolympus.js\n")
    w(root, "docs/KALSHICITY.md", "# KALSHI CITY\n\nA city of bets.\n")
    w(root, "tools/web_public/board/board.json", {"accounts": [
        {"key": "zlarior", "name": "Zlarior", "plan": "MFFU Builder 50K", "stage": "eval", "balance": 49192.78, "room": 1025, "to_pass": 3807, "pc": ["lit"]},
        {"key": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "stage": "passed", "balance": 26946.1, "pc": ["atlas"]}],
        "events": [{"id": "e1", "t": 1794951527, "kind": "owner_note", "acct": "atlas", "text": "passed, acct MFFU-500000001 by owner@example.com", "src": "owner"}]})
    w(root, "tools/web_public/business/accounts.json", {"accounts": [{"key": "zlarior", "next": "about $3,807 to pass", "bots": "Zlarior"}]})
    w(root, "tools/web_public/business/decisions.json", {"items": [
        {"id": "d1", "question": "Do the thing?", "why": "money", "impact": "+$9 a month", "status": "open", "added": "2026-11-18",
         "source": "research/writeups/lit-test-2026-11-18.md"},
        {"id": "d2", "question": "Old one?", "status": "no", "added": "2026-11-10"}]})
    w(root, "tools/web_public/trading/trades.json", {"trades": [
        {"acct": "zlarior", "bot": "LIT", "day": "2026-11-18", "hm": "09:42", "id": "a", "k": "TARGET", "q": 4, "r": 2.1, "side": "LONG", "src": "paper", "usd": 812.5},
        {"acct": "atlas", "bot": "ATLAS", "day": "2026-11-17", "hm": "04:10", "id": "b", "k": "STOP", "q": 3, "r": -1, "side": "SHORT", "src": "live", "usd": -250}]})
    w(root, "research/anatomy/explain.json", {"built": "2026-11-19", "bots": {"lit": {"spans": {"H1": {"n": 80, "tpw": 3.1, "win": 58.8, "pf": 4.98, "net": 33901, "per_month": 5562, "dd": -2196}},
                                                                                     "say": ["Stops are mostly real."]}},
                                               "kalshi_k8": {"all": {"n": 10, "won": 70, "usd": 22}, "first": "2026-08-03", "last": "2026-11-18",
                                                             "legs": [{"leg": "05:15 down gold", "n": 5, "won": 80, "usd": 12}], "say": ["Gold leads."]}})
    w(root, "second_model.json", {"note": "ATLAS members", "strategies": {"ema_lon_vix": {"on": True, "short": "EMA", "label": "London EMA", "summary": "pullback", "writeup": "atlas-plain"}}})
    w(root, "STRATEGY.md", "# LIT\n\nThe strategy.\n\n## 1. The sweep\n\nA new low.\n\n## How LIT performed\n\nintro\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
    w(root, "BLITZ_STRATEGY.md", "# BLITZ\n\n## Money first\n\nPaper.\n\n## The rule (exact)\n\n- one\n")
    w(root, "docs/RAPID_EOD_SETUP.md", "# Rapid\n\nBoth bots.\n\n## 1. Add it\n")
    w(root, "engine/combo50k.py", '"""ATLAS + Zlarior on ONE account."""\n')
    w(root, "STATE.md", "# STATE\n\nLive: Zlarior.\n")
    w(root, "logs/zeus/review_2026-11-18.json", {"day": "2026-11-18", "text": "Matched the twin."})


def notes_of(vault):
    return {os.path.relpath(p, vault): open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(vault, "**", "*.md"), recursive=True)}


def dangling(vault):
    names = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(vault, "**", "*.md"), recursive=True)}
    bad = []
    for rel, t in notes_of(vault).items():
        bad += [f"{rel}: {m}" for m in LINK_RX.findall(t) if m not in names]
    return bad


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="brain_test_")
    try:
        root, vault = os.path.join(tmp, "repo"), os.path.join(tmp, "vault")
        fixture(root)
        r1 = OB.build(vault, root=root)
        base = os.path.join(vault, OB.SUB)
        want = ["ZEUS Home.md", "ZEUS Lessons.md", "ZEUS Decisions.md", "ZEUS Apps.md", "ZEUS Kalshi.md", "ZEUS State.md",
                "Accounts/Account Zlarior.md", "Accounts/Account ATLAS.md", "Strategies/Zlarior (LIT).md", "Strategies/ATLAS.md",
                "Strategies/BLITZ (paper).md", "Strategies/Rapid lanes.md", "Strategies/50K combo.md", "Strategies/Kalshi K8.md",
                "Strategies/K8 leg 05.15 down gold.md", "Strategies/ATLAS member EMA (ema_lon_vix).md",
                "Research/lit-test-2026-11-18.md", "Research/kalshi-k8-2026-11-19.md", "Research/atlas-plain.md",
                "Families/Family risk.md", "Families/Family kalshi.md", "Days/Day 2026-11-18.md", "Days/Day 2026-11-17.md",
                "Months/Month 2026-11.md", "Apps/Apps ZEUS Trading.md", "Apps/Apps Kalshi.md"]
        miss = [x for x in want if not os.path.isfile(os.path.join(base, x))]
        check("a. one build writes every kind of note", r1["ok"] and not miss, miss)
        N = notes_of(base)
        home = N.get("ZEUS Home.md", "")
        check("a. Home maps accounts, strategies, the big notes, days, research", all(s in home for s in (
            "[[Account Zlarior\\|Zlarior]]", "[[Zlarior (LIT)]]", "[[Kalshi K8]]", "[[ZEUS Decisions]]", "[[ZEUS Lessons]]", "[[Day 2026-11-18|2026-11-18]]")), home[:600])
        lit = N.get("Strategies/Zlarior (LIT).md", "")
        check("a. the LIT note: rules, performance by period, rejected, write-ups", all(s in lit for s in (
            "**The sweep**", "Jan-Jun 2026 (picked on)", "+$5,562", "LIT wider stops", "[[lit-test-2026-11-18|LIT test idea]]")), lit[:900])
        les = N.get("ZEUS Lessons.md", "")
        check("a. Lessons: the loss clusters and every rejected idea family", "Stops are mostly real." in les and "LIT wider stops" in les
              and "BLITZ exits" in les and "Gold leads." in les, les[:600])
        dec = N.get("ZEUS Decisions.md", "")
        check("a. Decisions grouped open / no with the write-up link", "## Open" in dec and "## No" in dec and "Do the thing?" in dec
              and "[[lit-test-2026-11-18|" in dec, dec[:500])
        day = N.get("Days/Day 2026-11-18.md", "")
        check("a. a day note: trades, $ by bot and source, the daily review, research written", "LIT paper: +$812" in day and "Matched the twin." in day
              and "[[lit-test-2026-11-18|" in day and "[[Day 2026-11-17|" in day, day[:600])
        rs = N.get("Research/lit-test-2026-11-18.md", "")
        check("a. a research note: frontmatter tags, verdict callout, family + strategy + day links", rs.startswith("---\ntags:") and "verdict/rejected" in rs
              and "> [!failure] Verdict: rejected" in rs and "[[Family risk]]" in rs and "[[Zlarior (LIT)]]" in rs and "[[Day 2026-11-18]]" in rs, rs[:700])
        check("a. the look: CSS snippet, graph colors, snippet enabled, a starter workspace opening Home",
              os.path.isfile(os.path.join(vault, ".obsidian", "snippets", "zeus.css"))
              and "colorGroups" in open(os.path.join(vault, ".obsidian", "graph.json")).read()
              and "zeus" in open(os.path.join(vault, ".obsidian", "appearance.json")).read()
              and "ZEUS Brain/ZEUS Home.md" in open(os.path.join(vault, ".obsidian", "workspace.json")).read())
        check("a. no plugin syntax (no dataview blocks)", not any("```dataview" in t for t in N.values()))
        # b.
        r2 = OB.build(vault, root=root)
        check("b. a second build writes nothing and removes nothing", r2["wrote"] == [] and r2["removed"] == [], r2["wrote"][:5])
        v2 = os.path.join(tmp, "vault2")
        OB.build(v2, root=root)
        check("b. two fresh builds: the same bytes", notes_of(os.path.join(v2, OB.SUB)) == N)
        # c.
        alltext = "\n".join(N.values())
        leaks = [s for s in ("owner.private@example.com", "owner@example.com", "123456789", "500000001", "tail1234.ts.net", "RealName",
                             "ghp_abcdefghijklmnopqrstuvwxyz") if s in alltext]
        check("c. no email, key, account id, tailnet name or personal folder in the vault", not leaks, leaks)
        from tools import site_privacy as SP
        found = [f for f in SP.scan(vault) if f.get("kind") not in ("inbox",)]
        check("c. the site privacy scanner finds nothing in the vault", not found, found[:3])
        # d.
        bad = dangling(vault)
        check("d. every [[link]] resolves (fixture)", not bad, bad[:5])
        check("d. a [[link]] inside a write-up body never dangles (brackets defused)", "[[not a note]]" not in alltext)
        # e.
        mine = os.path.join(vault, OB.INBOX, "My idea.md")
        w(vault, os.path.join(OB.INBOX, "My idea.md"), "my own words [[ZEUS Home]]")
        start = os.path.join(vault, OB.INBOX, "ZEUS Inbox - start here.md")
        with open(start, "w", encoding="utf-8") as fh:
            fh.write("I edited the start note")
        own = os.path.join(base, "Research", "my own research.md")
        w(base, os.path.join("Research", "my own research.md"), "mine")
        os.remove(os.path.join(root, "research", "writeups", "atlas-plain.md"))
        r3 = OB.build(vault, root=root)
        check("e. the owner's Inbox notes are untouched (also the start note he edited)",
              open(mine, encoding="utf-8").read() == "my own words [[ZEUS Home]]" and open(start, encoding="utf-8").read() == "I edited the start note"
              and not any(x.startswith(OB.INBOX) for x in r3["wrote"]), r3["wrote"][:5])
        check("e. Inbox notes are linked from Home", "[[My idea]]" in open(os.path.join(base, "ZEUS Home.md"), encoding="utf-8").read())
        check("e. a note the brain no longer makes is removed; the owner's own file in the brain folder stays",
              "Research/atlas-plain.md" in r3["removed"] and os.path.isfile(own) and not os.path.isfile(os.path.join(base, "Research", "atlas-plain.md")), r3["removed"])
        check("d. links still resolve after the change", not dangling(vault), dangling(vault)[:5])
        # f.
        pv = os.path.join(tmp, "realvault")
        os.makedirs(os.path.join(pv, ".obsidian", "snippets"))
        w(pv, ".obsidian/workspace.json", '{"mine": true}')
        w(pv, ".obsidian/snippets/zeus.css", "/* the owner's own zeus.css */")
        rp = OB.build(pv, root=root, standalone=False)
        check("f. PC mode: notes in OLYMPUS/ZEUS Brain, the owner's .obsidian and his own zeus.css untouched, no Inbox made",
              os.path.isfile(os.path.join(pv, "OLYMPUS", "ZEUS Brain", "ZEUS Home.md")) and open(os.path.join(pv, ".obsidian", "workspace.json")).read() == '{"mine": true}'
              and open(os.path.join(pv, ".obsidian", "snippets", "zeus.css")).read() == "/* the owner's own zeus.css */"
              and not os.path.isdir(os.path.join(pv, OB.INBOX)) and not os.path.isfile(os.path.join(pv, ".obsidian", "graph.json")), rp["wrote"][:6])
        ln = open(os.path.join(ROOT, "tools", "learn_night.py"), encoding="utf-8").read()
        os_ = open(os.path.join(ROOT, "tools", "obsidian_sync.py"), encoding="utf-8").read()
        check("f. hooks: the cloud learn night rebuilds vault/ (soft, --skip brain); the PC sync builds hourly (soft)",
              "obsidian_brain.build(os.path.join(root, \"vault\")" in ln and '"brain" not in skip' in ln
              and "_brain.build(cfg[\"vault\"], standalone=False)" in os_ and "BRAIN_EVERY_S" in os_)
        src = open(os.path.join(ROOT, "tools", "obsidian_brain.py"), encoding="utf-8").read()
        check("f. no network, no broker / order import, no clock", not re.search(r"urllib|requests|socket|ninjatrader|engine\.live\b|place_order|time\.time|datetime\.now", src))
        # g.
        real = os.path.join(tmp, "realbuild")
        rr = OB.build(real, root=ROOT)
        check("d. the REAL repo build: every [[link]] resolves", rr["notes"] > 100 and not dangling(real), dangling(real)[:5])
        rf = [f for f in SP.scan(real)]
        check("c. the REAL repo build passes the site privacy scanner", not rf, rf[:3])
        if os.path.isdir(os.path.join(ROOT, "vault", OB.SUB)):
            diff = OB.check()
            check("g. the committed vault/ matches a fresh build (else: python tools/obsidian_brain.py)", not diff, diff[:5])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"obsidian brain: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
