"""Web business research (day-web-research 2026-11-20): the brief, the writeup and offers.json stay complete and in step. No browser, <1 s.
    python -m tests.test_web_research"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEF = os.path.join(ROOT, "research", "handoff", "2026-11-20", "web", "research", "RESEARCH.md")
FULL = os.path.join(ROOT, "research", "writeups", "web-business-2026-11-20.md")
OFFERS = os.path.join(ROOT, "research", "handoff", "2026-11-20", "web", "research", "offers.json")
ok = bad = 0


def check(name, cond, info=""):
    global ok, bad
    if cond:
        ok += 1; print(f"[PASS] {name}")
    else:
        bad += 1; print(f"[FAIL] {name}  -> {info}")


def main():
    brief, full = open(BRIEF, encoding="utf-8").read(), open(FULL, encoding="utf-8").read()
    doc = json.load(open(OFFERS, encoding="utf-8"))
    offers = doc["offers"]
    check("the brief has its 6 sections (prices, facts, offers, price card, first 5 clients, what kills agencies)",
          all(f"## {i}." in brief for i in range(1, 7)))
    check("the writeup ranks exactly 15 offers, 1..15", [o["rank"] for o in offers] == list(range(1, 16)), [o["rank"] for o in offers])
    check("every offer has a $ price, a year-1 $, months to the first $1,000 and the owner's effort",
          all("$" in o["price"] and o["months_to_first_1000"] and o["owner_effort"] for o in offers[:12]), [o["offer"] for o in offers if "$" not in o["price"]])
    urls = re.findall(r"https?://\S+", full[full.index("## Sources"):])
    check("the writeup cites at least 30 public URLs", len(urls) >= 30, len(urls))
    check("numbers are labelled as estimates (ESTIMATE in both files, estimate flag in offers.json)",
          "ESTIMATE" in full and ("estimate" in brief.lower()) and doc["estimate"] is True)
    check("offers.json is what the writeup's table says (same offers, same order)",
          all(o["detail"].replace("**", "")[:30] in full.replace("**", "") for o in offers))
    check("no private data: no email address or phone number in the research files",
          not re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}|\(\d{3}\)\s?\d{3}-\d{4}", brief + full + json.dumps(doc)))
    check("outreach rules are written down (no auto-dial / cold texts, CAN-SPAM, business listings only)",
          "TCPA" in full and "CAN-SPAM" in full and "Business listings only" in full)
    print(f"{ok}/{ok + bad} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
