"""tools/numbers_audit.py (2026-11-04): wrong money numbers are the costliest bug we can ship, so a tool finds them.

  a. the facts: read from a SYNTHETIC mini-tree (the owner's prices, the MFFU Builder numbers, the headline, the trio's $ a month, the job and app counts);
     a source that disagrees with CLAUDE.md is itself a 'wrong'; a missing source is reported, never a crash
  b. every rule finds its planted error in a published file and stays quiet on the right number: a list price where the owner's price belongs, the old funded
     figures, another number for the trio, the old headline, the old 2-week pass / fail, the old '7 of 10 days' wording, '58 jobs', a wrong daily loss / max loss /
     profit target / payouts / split / activation, an old app count; a sentence about the past ("up from $1,754", "Before: ...") is skipped, not flagged
  c. what is scanned: tools/web_public, web_next, handoff, the docs the owner reads, the hub snapshot, STRATEGY.md; not CLAUDE_REFERENCE.md, not research/
  d. --check exits 1 on a 'wrong' and 0 on a clean tree; --json is valid; the table has file / line / found / expected / severity
  e. the REAL tree: its facts equal the sources of truth, the classes that must be clean (list prices, 7 of 10, job counts, MFFU figures, 2-week, sources) are
     clean, and the open items (the stale trio / headline copy) are printed so nobody forgets them

    python -X utf8 -m tests.test_numbers_audit
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import numbers_audit as A  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else "  -> " + str(info)[:500]))


def put(root, rel, text):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text if isinstance(text, str) else json.dumps(text))


CLAUDE = """# brief
- **Prop-firm prices:** use the owner's real prices (Builder 25K $63, the ATLAS 25K of 2026-10-26 $43, Builder 50K $91.80, one-time, $0 activation), not list prices.
- **Headline (run `lit_live`, costs in):** 2026 PF 4.19, +$43,820; **quote the H2 check rate: PF 2.91, +$9,919 (~$2,670/mo)** (cisd1m 22).
  **Uprisk:** funded 60% of room, <= $1,500, winner <= $2,000 (~$915/mo H2 to the owner, 0% lost).
"""


def mini(tmp, *, price_in_roadmap=91.8, drop=(), apps=24):
    """a small tree with every source of truth and a few published files (all clean); the caller plants errors"""
    root = os.path.join(tmp, "t")
    put(root, "CLAUDE.md", CLAUDE)
    put(root, "research/lit/mffu_rules.json", {"limits": {"builder_50k": {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40, "buffer": 2100.0,
                                                                         "pay_min": 500.0, "pay_max": 2000.0, "split": 0.8, "max_payouts": 5},
                                               "builder_25k": {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20, "buffer": 1100.0, "pay_min": 250.0,
                                                               "pay_max": 1000.0, "split": 0.8, "max_payouts": 5}},
                                     "builder_50k": {"eval": {"price": {"value": {"list": 153.0, "list_addon_1500_mll": 125.0, "owner_paid": 91.8, "type": "one-time"}}}}})
    put(root, "research/props/roadmap.json", {"prices": {"L50": price_in_roadmap, "L25": 63.0, "A25": 43.0}, "published_pass_2w": {"L50": {"H1": {"pass": 52.9, "fail": 17.8}, "H2": {"pass": 58.6, "fail": 20.9}}}})
    trio = ["mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k"]
    put(root, "research/lit/funded_firms.json", {"plans": [{"id": "mffu_builder_50k", "price": 91.8}, {"id": "mffu_builder_25k", "price": 63.0}],
                                                 "combos": [{"plans": trio, "span": "H1", "net_per_month": 2655, "months4_6_per_month": 3292, "neg_6m": 3.1},
                                                            {"plans": trio, "span": "H2", "net_per_month": 2147, "months4_6_per_month": 2792, "neg_6m": 5.2}]})
    put(root, "tools/web_public/plutus/plans.json", {"plans": [{"id": "mffu_builder_50k", "list_price": 153, "spans": {"H2": {"funded_per_month": 914}}}, {"id": "mffu_builder_25k", "list_price": 105, "spans": {}}],
                                                      "trio": {"H1": {"net_per_month": 2655}, "H2": {"net_per_month": 2147}}})
    put(root, "tools/web_public/bridge/jobs.json", {"jobs": [{"id": f"job-{i}"} for i in range(78)]})
    put(root, "tools/web_public/bridge/index.html", "".join("{ id: 'card" + str(i) + "', t: 'x' },\n" for i in range(11)))
    put(root, "tools/web_public/jarvis/apps.js", "".join(f"  app('a{i}', 'A{i}'),\n" for i in range(apps)))
    for d in drop:
        os.remove(os.path.join(root, *d.split("/")))
    return root


def rule_hits(root):
    r = A.audit(root)
    return r, {(f["rule"], f["severity"]) for f in r["findings"]}


def part_facts():
    tmp = tempfile.mkdtemp(prefix="le_audit_")
    try:
        root = mini(tmp)
        F = A.load_facts(root)
        check("a. facts: the owner's real prices come from CLAUDE.md (Builder 50K $91.80, Builder 25K $63, ATLAS 25K $43, $0 activation)",
              F["price"] == {"b25": 63.0, "atlas25": 43.0, "b50": 91.8, "activation": 0.0}, F["price"])
        check("a. facts: the MFFU Builder 50K figures (target $3,000, max loss $2,000, floor $48,000, locks at $50,100, daily loss $1,000, 5 payouts, 80%) and the list prices ($153, $125, $105)",
              F["b50"]["floor"] == 48000 and F["b50"]["lock_level"] == 50100 and F["b50"]["dll"] == 1000 and F["b50"]["max_payouts"] == 5 and F["b50"]["split"] == 0.8
              and F["list"] == {"b50": 153.0, "b50_addon": 125.0, "b50_owner": 91.8, "b25": 105.0}, (F["b50"], F["list"]))
        check("a. facts: the headline (2026 PF 4.19 / +$43,820, H2 PF 2.91 / +$9,919 / ~$2,670 a month), the 2-week pass / fail, the trio's $ a month, the job and app counts",
              F["headline"]["pf_2026"] == 4.19 and F["headline"]["net_2026"] == 43820 and F["headline"]["pf_h2"] == 2.91 and F["headline"]["net_h2"] == 9919 and F["headline"]["pm_h2"] == 2670
              and F["pass_2w"]["L50"]["H2"] == {"pass": 58.6, "fail": 20.9} and F["trio"]["H2"]["per_month"] == 2147 and F["trio"]["H1"]["months4_6"] == 3292
              and F["jobs"] == {"library": 78, "cards": 11, "total": 89} and F["apps"] == 24 and F["per_account"]["mffu_builder_50k"]["H2"] == 914, F)
        check("a. a clean mini-tree has no source missing and no conflict", F["missing"] == [] and F["conflicts"] == [])
        r, hits = rule_hits(mini(tempfile.mkdtemp(prefix="le_audit_"), price_in_roadmap=153.0))
        check("a. a source that disagrees with CLAUDE.md (the roadmap prices Builder 50K at $153) is a 'wrong' finding by itself", ("sources-disagree", "wrong") in hits, hits)
        r2 = A.audit(mini(tempfile.mkdtemp(prefix="le_audit_"), drop=("research/lit/funded_firms.json",)))
        check("a. a missing source of truth is reported as a finding, never a crash", any(f["rule"] == "source" and "funded_firms" in f["file"] for f in r2["findings"]), r2["findings"][:2])
        # night-bugsweep 2026-11-19: the brief was cut to one page (2026-11-15); the long brief moved, word for word, to CLAUDE_REFERENCE.md's last section
        short = mini(tempfile.mkdtemp(prefix="le_audit_"))
        put(short, "CLAUDE.md", "# one-page brief\n- Prop prices: owner's real prices (Builder 50K $91.80, 25K $63 / $43), never list prices.\n")
        put(short, "docs/CLAUDE_REFERENCE.md", "# map\nold numbers: 2026 PF 3.66\n\n## The full brief (CLAUDE.md as it was on 2026-11-15, moved here word for word)\n" + CLAUDE)
        Fs = A.load_facts(short)
        check("a. one-page brief: prices come from its 'Builder 50K $91.80, 25K $63 / $43' line, the headline and $0 activation from the full brief in CLAUDE_REFERENCE.md; nothing missing",
              Fs["price"] == {"b25": 63.0, "atlas25": 43.0, "b50": 91.8, "activation": 0.0} and Fs["headline"].get("pf_h2") == 2.91 and Fs["headline"].get("net_2026") == 43820
              and Fs["missing"] == [] and Fs["conflicts"] == [], (Fs["price"], Fs["headline"], Fs["missing"]))
        put(short, "docs/CLAUDE_REFERENCE.md", "# map, no full brief section\n")
        check("a. one-page brief and no full brief: the headline is reported missing (never read from the reference's history lines)",
              "CLAUDE.md headline pf_h2" in A.load_facts(short)["missing"], A.load_facts(short)["missing"])
        empty = A.audit(tempfile.mkdtemp(prefix="le_audit_"))
        check("a. an empty folder does not crash the audit (every source reported missing)", empty["files"] == 0 and len([f for f in empty["findings"] if f["rule"] == "source"]) >= 5)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


PLANT = {
    "list-price": ("tools/web_public/a/list.html", "<p>The MFFU Builder 50K eval costs $153 one time.</p>\n<p>Builder 25K eval: $105.</p>\n", {"$153", "$105"}),
    "old-trio": ("tools/web_public/a/trio.html", "<p>The trio (Builder 50K + LucidPro 50K + FundedNext) pays $1,754 a month net, $2,315 on Jan-Jun, funded.</p>\n", {"$1,754", "$2,315"}),
    "trio-month": ("tools/web_public/a/trio2.html", "<p>Builder 50K + LucidPro 50K + FundedNext Rapid Daily 50K now makes $2,530 a month net.</p>\n", {"$2,530"}),
    "old-headline": ("docs/PLAYBOOK.md", "The bot's 2026 headline is PF 3.66 and +$41,734 net.\n", {"PF 3.66", "+$41,734"}),
    "old-2week": ("handoff/SYNC.md", "LIT 2-week pass / fail is 53.7 / 2.2 on the 50K eval.\n", {"53.7 / 2.2"}),
    "old-days": ("tools/web_public/a/eval.js", "const card = 'Pass the eval: profit in 7 of 10 days';\n", {"7 of 10 days"}),
    "jobs-count": ("tools/web_public/bridge/readme.md", "The Bridge library has 58 jobs ready for ChatGPT.\n", {"58 jobs"}),
    "mffu-dll": ("web_next/a.html", "<p>MFFU Builder 50K daily loss limit: $1,500.</p>\n", {"$1,500"}),
    "mffu-mll": ("tools/web_public/a/mll.html", "<p>MFFU Builder 50K max loss: $2,500 trailing.</p>\n", {"$2,500"}),
    "mffu-target": ("tools/web_public/a/target.html", "<p>MFFU Builder 25K profit target: $3,000.</p>\n", {"$3,000"}),
    "mffu-payouts": ("tools/web_public/a/pay.html", "<p>MFFU Builder pays out in 3 payouts.</p>\n", {"3 payouts"}),
    "mffu-split": ("tools/web_public/a/split.html", "<p>MFFU Builder payout: you keep a 90% profit split.</p>\n", {"90% profit split"}),
    "mffu-activation": ("tools/web_public/a/act.html", "<p>MFFU Builder 50K: $0 to start but a $25 activation fee.</p>\n", {"$25 activation"}),
    "app-count": ("tools/web_public/a/apps.html", "<p>OLYMPUS has 17 built-in apps.</p>\n", {"17 built-in apps"}),
}
CLEAN = {
    "tools/web_public/a/fine.html": ("<p>MFFU Builder 50K eval: $91.80 ($153 list price). Builder 25K: $63 ($105 list).</p>\n<p>MFFU Builder 50K: $3,000 target, $2,000 max loss, $1,000 daily loss limit, "
                                    "5 payouts, 80% split, $0 activation.</p>\n<p>Builder 25K: $1,500 target, $1,000 max loss, $600 daily loss limit.</p>\n"
                                    "<p>The trio makes $2,147 a month on Jul-Oct and $2,655 on Jan-Jun (Builder 50K + LucidPro 50K + FundedNext Rapid Daily 50K).</p>\n"
                                    "<p>2026 PF 4.19, +$43,820; H2 PF 2.91, +$9,919 (~$2,670/mo). LIT 2-week pass 58.6 / 20.9. The library has 78 ready jobs. OLYMPUS has 24 apps.</p>\n"),
    "docs/OLD.md": ("The trio paid $1,754 a month before the rerun (up from $1,754 on the old trades).\nBefore: room 55% | 53.7 / 2.2 | the old pass rate.\nThe bot was PF 3.66 and +$41,734 until the new cut.\n"),
    "tools/web_public/a/mffu_dd.html": "<p>MFFU Builder 50K: trailing max loss $2,000 that locks at $50,100; fee $91.80.</p>\n",
    "tools/web_public/a/code.js": "// OLYMPUS with ~12 apps: opts.apps()\nconst fee = '$91.80';\n",
    # night-bugsweep: the taxes page lists deductible fees; the $ after "activation fees" is the eval's price, not an activation fee
    "tools/web_public/a/taxes.html": "<li><b>Eval fees, resets, activation fees</b> (Builder 50K $91.80, 25K $63 / $43). Keep each receipt email.</li>\n",
}


def part_rules():
    tmp = tempfile.mkdtemp(prefix="le_audit_")
    try:
        root = mini(tmp)
        for rel, text in CLEAN.items():
            put(root, rel, text)
        clean = A.audit(root)
        bad = [(f["rule"], f["file"], f["found"]) for f in clean["findings"] if f["severity"] in ("wrong", "warn")]
        check("b. the RIGHT numbers (the owner's prices next to list prices, the true Builder figures, the trio's current $, the current headline, 78 jobs, 24 apps) raise nothing", not bad, bad)
        hist = [f for f in clean["findings"] if f["severity"] == "ok"]
        check("b. sentences about the past ('before the rerun', 'up from', 'Before:', 'was ... until') are skipped as history, not flagged", len(hist) >= 3 and all(f["file"] == "docs/OLD.md" for f in hist), hist)
        for rid, (rel, text, found) in PLANT.items():
            r = os.path.join(tmp, "p_" + rid)
            shutil.copytree(root, r)
            put(r, rel, text)
            res = A.audit(r)
            got = {f["found"] for f in res["findings"] if f["rule"] == rid and f["file"] == rel and f["severity"] in ("wrong", "warn")}
            lines = {f["line"] for f in res["findings"] if f["rule"] == rid and f["file"] == rel}
            check(f"b. rule {rid}: finds the planted error(s) {sorted(found)} in {rel} with its line number and the expected value", found <= got and all(n >= 1 for n in lines)
                  and all(f["expected"] for f in res["findings"] if f["rule"] == rid), (got, res["findings"][:2]))
        sev = {rid: {f["severity"] for f in A.audit(os.path.join(tmp, "p_" + rid))["findings"] if f["rule"] == rid and f["file"] == PLANT[rid][0]} for rid in PLANT}
        check("b. severities: certain errors are 'wrong' (list price, old trio, old headline, old 2-week, 7 of 10, job count, daily loss / max loss / target, activation); a count that may mean something else is 'warn' (apps, payouts, split)",
              all("wrong" in sev[r] for r in ("list-price", "old-trio", "trio-month", "old-2week", "old-days", "jobs-count", "mffu-dll", "mffu-mll", "mffu-target", "mffu-activation"))
              and sev["old-headline"] == {"wrong"} and sev["app-count"] == {"warn"} and sev["mffu-payouts"] == {"warn"} and sev["mffu-split"] == {"warn"}, sev)
        # a dated research result is a warn, not a wrong
        r = os.path.join(tmp, "p_dated")
        shutil.copytree(root, r)
        put(r, "tools/web_public/a/learned.html", "<p>Together (litlosspack): 2026 +$41.7k, PF 3.66, max DD -$2.3k.</p>\n")
        sv = {f["severity"] for f in A.audit(r)["findings"] if f["rule"] == "old-headline" and f["file"] == "tools/web_public/a/learned.html"}
        check("b. a dated research result ('litlosspack: 2026 +$41.7k, PF 3.66') is a 'warn' to look at, only a 'headline / quote / current' sentence with an old figure is 'wrong'", sv == {"warn"}, sv)
        # night-bugsweep: the Archive app (every run ever made, "live" = a run's label) holds dated results: old headline = 'warn'; a list price there stays 'wrong'
        put(r, "tools/web_public/archive/index.json", '["lit_adv","reference: LIT live with the live sizing (vs live). 2026 H1 (pick) n=80 PF 3.66 net +36,723"]\n')
        put(r, "tools/web_public/archive/runs-9.json", '["fee","The MFFU Builder 50K eval costs $153."]\n')
        ar = {(f["rule"], f["severity"]) for f in A.audit(r)["findings"] if f["file"].startswith("tools/web_public/archive/")}
        check("b. the Archive's dated runs: an old headline figure is a 'warn' (history), a list price as the owner's price is still 'wrong'",
              ("old-headline", "warn") in ar and ("old-headline", "wrong") not in ar and ("list-price", "wrong") in ar, ar)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_scope_and_cli():
    tmp = tempfile.mkdtemp(prefix="le_audit_")
    try:
        root = mini(tmp)
        bad = "The MFFU Builder 50K eval costs $153.\n"
        for rel in ("tools/web_public/x/page.html", "web_next/js/n.js", "handoff/note.md", "docs/GO_LIVE.md", "tools/web_hub_snapshot.json", "STRATEGY.md"):
            put(root, rel, bad)
        for rel in ("docs/CLAUDE_REFERENCE.md", "research/writeups/old.md", "engine/x.py", "tools/web_public/node_modules/a.js"):
            put(root, rel, bad)
        res = A.audit(root)
        files = {f["file"] for f in res["findings"] if f["rule"] == "list-price"}
        check("c. scanned: the site (tools/web_public), web_next, handoff, the docs, the hub snapshot and STRATEGY.md; not CLAUDE_REFERENCE.md (Claude's own history), research/, engine/ or node_modules",
              files == {"tools/web_public/x/page.html", "web_next/js/n.js", "handoff/note.md", "docs/GO_LIVE.md", "tools/web_hub_snapshot.json", "STRATEGY.md"}, files)
        out = io.StringIO()
        with redirect_stdout(out):
            code = A.main(["--root", root, "--check"])
        txt = out.getvalue()
        check("d. --check exits 1 when a 'wrong' is left; the table has severity, file, line, found and expected; the facts are printed first",
              code == 1 and "FACTS" in txt and "sev " in txt and "tools/web_public/x/page.html" in txt and "$153" in txt and "$91.8" in txt, txt[:300])
        clean_root = mini(os.path.join(tmp, "c"))
        out = io.StringIO()
        with redirect_stdout(out):
            code0 = A.main(["--root", clean_root, "--check"])
        check("d. --check exits 0 on a clean tree and without --check the exit is always 0", code0 == 0 and "0 wrong" in out.getvalue(), out.getvalue()[-200:])
        out = io.StringIO()
        with redirect_stdout(out):
            code2 = A.main(["--root", root, "--json"])
        j = json.loads(out.getvalue())
        check("d. --json is valid JSON with the count of wrong findings and each finding's severity / file / line / found / expected / rule",
              code2 == 0 and j["wrong"] >= 6 and all({"severity", "file", "line", "found", "expected", "rule"} <= set(f) for f in j["findings"]), j["wrong"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_real():
    res = A.audit(ROOT)
    F = res["facts"]
    sources = {"price": F["price"], "trio": F["trio"], "headline": F["headline"]}
    check("e. REAL tree: every source of truth is there and agrees with CLAUDE.md (prices in roadmap.json and funded_firms.json match; the Plutus trio equals funded_firms.json)",
          F["missing"] == [] and F["conflicts"] == [], (F["missing"], F["conflicts"]))
    check("e. REAL tree: the facts are what the owner was told ($91.80 / $63 / $43, $0 activation, floor $48,000, 5 payouts at 80%, H2 PF 2.91 / +$9,919 / ~$2,670 a month, 2026 PF 4.19 / +$43,820)",
          F["price"] == {"b25": 63.0, "atlas25": 43.0, "b50": 91.8, "activation": 0.0} and F["b50"]["floor"] == 48000 and F["b50"]["max_payouts"] == 5 and F["b50"]["split"] == 0.8
          and F["headline"]["pf_h2"] == 2.91 and F["headline"]["net_h2"] == 9919 and F["headline"]["pm_h2"] == 2670 and F["headline"]["pf_2026"] == 4.19 and F["headline"]["net_2026"] == 43820, sources)
    must_be_clean = {"list-price", "old-2week", "old-days", "jobs-count", "mffu-dll", "mffu-mll", "mffu-target", "mffu-activation", "sources-disagree", "source"}
    dirty = [(f["rule"], f["file"], f["line"], f["found"]) for f in res["findings"] if f["severity"] == "wrong" and f["rule"] in must_be_clean]
    check(f"e. REAL tree ({res['files']} published files): no list price as the owner's price, no old 2-week pass / fail, no '7 of 10 days', no wrong job count, no wrong Builder limit, no source conflict", not dirty, dirty)
    open_items = [(f["rule"], f["file"], f["line"], f["found"]) for f in res["findings"] if f["severity"] == "wrong" and f["rule"] not in must_be_clean]
    print(f"  [info] open items (stale trio / headline copy generated from older writeups): {len(open_items)}")
    for o in open_items[:20]:
        print("    ", o)
    check("e. REAL tree: the open items are only the stale funded / headline copy (nothing else is wrong)", all(o[0] in ("old-trio", "trio-month", "old-headline") for o in open_items), open_items[:5])


def main():
    part_facts()
    part_rules()
    part_scope_and_cli()
    part_real()
    n = sum(RES)
    print(f"\nnumbers audit: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
