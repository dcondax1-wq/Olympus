"""Jarvis strategy facts (2026-11-11, JARVIS BRAIN v3): STRATEGY.md + the plain-words glossary -> jarvis/strategy-facts.json.

Jarvis answers "what is a sweep / CISD / drawdown / Kelly / PF" and "where does the stop go" from THIS file only, so it can
never invent a rule: every rule line is a line of STRATEGY.md (the live LIT part, rules 1 to 11), and every meaning is a line
of olympus/glossary-core.js or of the small EXTRA list below (textbook meanings, no rules).

    python tools/jarvis_facts_build.py              write tools/web_public/jarvis/strategy-facts.json
    python tools/jarvis_facts_build.py --check      exit 1 when the file on disk differs from a fresh build
    python tools/jarvis_facts_build.py --selftest   parse checks on the real STRATEGY.md (no file written)
    python tools/jarvis_facts_build.py --out DIR    write DIR/strategy-facts.json (the site build)

Stdlib only, no network, deterministic (no clock in the output).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WP = os.path.join(ROOT, "tools", "web_public")
STRATEGY = os.path.join(ROOT, "STRATEGY.md")
GLOSSARY = os.path.join(WP, "olympus", "glossary-core.js")
OUT = os.path.join(WP, "jarvis", "strategy-facts.json")
MAX_LINES = 8          # rule lines kept per section
MAX_CHARS = 300        # per rule line

# Which rule sections answer which word. The builder FAILS when the word is not in that section's text, so this table
# cannot drift away from STRATEGY.md.  word -> ([section numbers], the text that must be found there)
TOPICS = {
    "liquidity": ([1], "liquidity"),
    "sweep": ([2], "sweep"),
    "inducement": ([3], "inducement"),
    "displacement": ([4], "ATR"),
    "CISD": ([4, 5], "CISD"),
    "entry": ([5], "limit order"),
    "stop": ([6], "beyond the sweep extreme"),
    "target": ([7], "VIX"),
    "VIX band": ([7], "VIX move"),
    "breakeven": ([8], "breakeven"),
    "15-minute check": ([8], "15-minute check"),
    "flat": ([8], "Flat by"),
    "scale-in": ([8], "Scale-in"),
    "one trade a day": ([8], "One trade a day"),
    "size": ([9], "risk"),
    "weekly stop": ([10], "Weekly stop"),
    "Monday rule": ([10], "Monday rule"),
}
# Textbook meanings for words the site glossary does not hold. Meanings only: no rule of the owner's is stated here.
EXTRA = {
    "R": "One R is the money a trade risks: the distance from the entry to the stop, times the size. A +2R trade made twice what it risked.",
    "Kelly": "The Kelly fraction: the share of a bankroll that a bet's edge and odds say to stake for the fastest long-run growth. Staking more than Kelly loses money over time, so careful bettors use a fraction of it.",
    "breakeven": "Moving the stop to the entry price (plus costs) once the trade is in profit, so the trade can no longer lose money.",
    "stop": "The price where a trade is closed at a loss, so one wrong idea costs a known amount.",
    "target": "The price where a trade takes its profit.",
    "eval": "A prop-firm evaluation account: reach the profit target before touching the max loss limit and the firm funds you.",
    "micro": "One MNQ micro contract: $2 for each point the NQ moves.",
    "win rate": "The share of trades that made money. On its own it says little: a low win rate with big winners can still make money.",
    "DLL": "Daily loss limit: the most the account may lose in one day.",
    "profit target": "The profit an eval account has to reach to pass.",
    "VIX": "The market's fear gauge: how big a daily move the options market expects.",
    "ATR": "Average true range: the average size of a candle, a measure of how much the price is moving.",
    "FVG": "Fair-value gap: a three-candle gap that the price jumped over, leaving an area with little trading.",
    "paper trading": "Trading with pretend money to test a strategy: the fills are simulated and nothing real is at risk.",
    "walk-forward": "Testing an idea on data that comes after the data it was built on, step by step, the way it would have been traded.",
    "sample size": "How many trades or bets a number is based on (n). A small n means the number can be luck.",
    "payout": "Money a prop firm pays you from a funded account's profit.",
    "killzone": "A time window in the day when a strategy is allowed to take entries.",
}
# What people say -> the term (lower case). The JS side adds typo tolerance on top.
ALIASES = {
    "profit factor": "PF", "inverse fair value gap": "IFVG", "inverse fvg": "IFVG", "inversion fair value gap": "IFVG", "change in state of delivery": "CISD",
    "max loss limit": "MLL", "max loss": "MLL", "maximum loss limit": "MLL", "dd": "drawdown", "draw down": "drawdown", "max drawdown": "drawdown",
    "expected value": "EV", "out of sample": "OOS", "false discovery rate": "FDR", "kelly criterion": "Kelly", "kelly fraction": "Kelly", "kelly bet": "Kelly", "kelly sizing": "Kelly",
    "one r": "R", "1r": "R", "an r": "R", "r multiple": "R", "risk unit": "R", "be": "breakeven", "break even": "breakeven", "break-even": "breakeven",
    "stop loss": "stop", "stoploss": "stop", "the stop": "stop", "stop rule": "stop", "take profit": "target", "the target": "target", "tp": "target", "target rule": "target",
    "vix band": "VIX band", "vix move": "VIX band", "vix target": "VIX band", "evaluation": "eval", "micros": "micro", "mnq": "micro", "winrate": "win rate", "hit rate": "win rate",
    "daily loss limit": "DLL", "daily loss": "DLL", "fair value gap": "FVG", "liquidity sweep": "sweep", "stop hunt": "sweep", "stop run": "sweep", "sweeps": "sweep",
    "sizing": "size", "position size": "size", "position sizing": "size", "size rule": "size", "risk per trade": "size", "the entry": "entry", "entry rule": "entry", "entries": "entry",
    "weekly loss stop": "weekly stop", "monday": "Monday rule", "15 minute check": "15-minute check", "15 minute cut": "15-minute check", "fifteen minute check": "15-minute check",
    "15-minute cut": "15-minute check", "scale in": "scale-in", "scaling in": "scale-in", "flat time": "flat", "flat by": "flat", "flat rule": "flat", "paper": "paper trading", "paper trade": "paper trading",
    "walk forward": "walk-forward", "n": "sample size", "payouts": "payout", "liquidity level": "liquidity", "liquidity levels": "liquidity", "displacement candle": "displacement",
    "average true range": "ATR", "mfe": "MFE", "mae": "MAE", "p10": "p10", "f10": "f10", "one trade a day": "one trade a day", "trades a day": "one trade a day", "kill zone": "killzone",
}


def read(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


def clean(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\(\s*`[^`]*`[^)]*\)", "", s)            # (`research/writeups/x.md`) file pointers
    s = s.replace("`", "")
    s = s.replace("→", "to").replace("÷", "/").replace("×", "x").replace("√", "sqrt ").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def clip(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    cut = s[:n]
    dot = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[: dot + 1] if dot > n * 0.5 else cut[: cut.rfind(" ")].rstrip(",;:") + "…").strip()


def live_part(text: str) -> tuple[str, str]:
    """(the live LIT part, the previous-strategy part)"""
    m = re.search(r"^## How LIT performed", text, re.M)
    p = re.search(r"^## Previous strategy", text, re.M)
    if not m or not p:
        raise ValueError("STRATEGY.md: the 'How LIT performed' / 'Previous strategy' headings are missing")
    return text[: m.start()], text[p.start():]


def sections(live: str) -> list[dict]:
    out = []
    parts = re.split(r"^## (\d+)\. (.+)$", live, flags=re.M)
    for i in range(1, len(parts) - 2, 3):
        n, title, body = int(parts[i]), parts[i + 1].strip(), parts[i + 2]
        lines, cur = [], None
        for raw in body.split("\n"):
            if re.match(r"^- ", raw):
                if cur:
                    lines.append(cur)
                cur = raw[2:]
            elif raw.startswith("  ") and cur is not None and raw.strip() and not raw.strip().startswith("|"):
                cur += " " + re.sub(r"^- ", "", raw.strip())
            else:
                if cur:
                    lines.append(cur)
                cur = None
        if cur:
            lines.append(cur)
        full = clean(" ".join(lines))
        out.append({"n": n, "title": clean(re.sub(r"\(.*$", "", title)).rstrip(": ") or clean(title), "lines": [clip(clean(x), MAX_CHARS) for x in lines[:MAX_LINES]], "_full": full, "_raw": body})
    return out


def glossary_terms() -> dict:
    src = read(GLOSSARY)
    m = re.search(r"export const TERMS = \{(.*?)\n\};", src, re.S)
    if not m:
        raise ValueError("glossary-core.js: TERMS not found")
    out = {}
    for a, b, c in re.findall(r"^\s*(?:'([^']+)'|([A-Za-z0-9_]+)):\s*'((?:[^'\\]|\\.)*)',?\s*$", m.group(1), re.M):
        out[a or b] = c.replace("\\'", "'").replace('\\"', '"')
    if len(out) < 10:
        raise ValueError("glossary-core.js: only %d terms parsed" % len(out))
    return out


def build() -> dict:
    text = read(STRATEGY)
    live, prev = live_part(text)
    secs = sections(live)
    if [s["n"] for s in secs] != list(range(1, len(secs) + 1)) or len(secs) < 9:
        raise ValueError("STRATEGY.md: expected rule sections 1..N in order, got %s" % [s["n"] for s in secs])
    by_n = {s["n"]: s for s in secs}
    head = clean(live.split("\n## ")[0].split("\n\n")[1]).split(" Settings:")[0]
    terms: dict = {}
    for name, d in glossary_terms().items():
        terms[name] = {"def": d, "src": "the site glossary"}
    for name, d in EXTRA.items():
        terms.setdefault(name, {"def": d, "src": "Jarvis' word list"})
    for name, (ns, needle) in TOPICS.items():
        for n in ns[:1]:
            if n not in by_n or needle.lower() not in (by_n[n]["_full"] + " " + by_n[n]["title"]).lower():
                raise ValueError("TOPICS drifted: %r is not in STRATEGY.md rule %d" % (needle, n))
        terms.setdefault(name, {"def": "", "src": ""})["rules"] = ns
    for name, t in terms.items():          # where else the word is used, so Jarvis can say "your live strategy does not use it"
        rx = re.compile(r"(?<![A-Za-z])" + re.escape(name) + r"s?(?![A-Za-z])", re.I if len(name) > 3 else 0)
        t["live"] = bool(t.get("rules")) or bool(rx.search(live))
        t["prev"] = bool(rx.search(prev))
    for a, target in ALIASES.items():
        if target not in terms:
            raise ValueError("alias %r points at an unknown term %r" % (a, target))
    body = {
        "v": 1, "src": "STRATEGY.md", "strategy": "LIT", "head": clip(head, 400),
        "sections": [{"n": s["n"], "title": s["title"], "lines": s["lines"]} for s in secs],
        "terms": {k: terms[k] for k in sorted(terms, key=str.lower)},
        "aliases": {k: ALIASES[k] for k in sorted(ALIASES)},
    }
    body["sha"] = hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    return body


def dumps(body: dict) -> str:
    return json.dumps(body, ensure_ascii=False, indent=1) + "\n"


def selftest() -> int:
    b = build()
    bad = []
    t = b["terms"]
    by = {s["n"]: s for s in b["sections"]}
    if "1 tick" not in " ".join(by[6]["lines"]):
        bad.append("rule 6 (stop) lost '1 tick'")
    if "8R" not in " ".join(by[7]["lines"]):
        bad.append("rule 7 (target) lost '8R'")
    if "15:55" not in " ".join(by[8]["lines"]):
        bad.append("rule 8 lost 'Flat by 15:55'")
    for k in ("IFVG", "CISD", "sweep", "drawdown", "PF", "Kelly", "R", "stop", "target", "size"):
        if k not in t or not (t[k].get("def") or t[k].get("rules")):
            bad.append("term %s has no meaning and no rule" % k)
    if t["IFVG"]["live"] or not t["IFVG"]["prev"]:
        bad.append("IFVG should be a previous-strategy word only, got live=%s prev=%s" % (t["IFVG"]["live"], t["IFVG"]["prev"]))
    if t["stop"].get("rules") != [6] or t["CISD"].get("rules") != [4, 5]:
        bad.append("rule pointers wrong")
    if any(len(x) > MAX_CHARS + 2 for s in b["sections"] for x in s["lines"]) or any("`" in x or "**" in x for s in b["sections"] for x in s["lines"]):
        bad.append("a rule line is too long or still has markdown")
    if dumps(build()) != dumps(b):
        bad.append("not deterministic")
    size = len(dumps(b).encode("utf-8"))
    if size > 40000:
        bad.append("too big: %d bytes" % size)
    for x in bad:
        print("[FAIL] " + x)
    print("jarvis_facts_build selftest: %d sections, %d terms, %d aliases, %d bytes: %s" % (len(b["sections"]), len(t), len(b["aliases"]), size, "FAIL" if bad else "ok"))
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", help="directory to write strategy-facts.json into (default: tools/web_public/jarvis)")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    text = dumps(build())
    path = os.path.join(a.out, "strategy-facts.json") if a.out else OUT
    if a.check:
        ok = os.path.exists(path) and read(path) == text
        print("strategy-facts.json: " + ("up to date" if ok else "STALE: run python tools/jarvis_facts_build.py"))
        return 0 if ok else 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote %s (%d bytes)" % (os.path.relpath(path, ROOT) if path.startswith(ROOT) else path, len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
