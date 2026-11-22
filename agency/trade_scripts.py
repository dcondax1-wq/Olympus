"""Per-trade call scripts for the HUMAN caller (agency/trade_scripts.json). One source for the caller's sheet and the portal copy.

  python -m agency.trade_scripts                 print the 8 trade scripts filled with sample names
  python -m agency.trade_scripts --md FILE       write the caller's sheet (research/handoff/2026-11-22/caller/TRADE_SCRIPTS.md)
  python -m agency.trade_scripts --json FILE     write the portal copy (tools/web_public/agency/portal/scripts.json)
  python -m agency.trade_scripts --coverage      how many leads on today's call list each trade script covers

Rules checked in code (tests/test_trade_scripts.py): the opener says who is calling FIRST and fits in 15 seconds (<= 45 words), every
price is the price book's (agency/pricebook.json), no promise of rankings or results, no fake urgency, texts only with consent.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency import pricebook as PB  # noqa: E402

SRC = os.path.join(ROOT, "agency", "trade_scripts.json")
PORTAL_COPY = os.path.join(ROOT, "tools", "web_public", "agency", "portal", "scripts.json")
CALLLIST = os.path.join(ROOT, "tools", "web_public", "agency", "portal", "calllist.json")
MAX_OPENER_WORDS = 45                      # ~15 seconds at a calm 3 words a second
BANNED = re.compile(r"\bguarantee|#1|number one|first page of google|rank(ing)? you|only today|today only|limited time|expires|"
                    r"last chance|google (requires|says you must)|penalt|act now|free forever|no catch at all", re.I)


def load(path: str = SRC) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def trade_for(kind: str, d: dict | None = None) -> dict:
    """The trade whose keywords appear in the lead's kind (first match, list order), else the generic script. Stores are not trades."""
    d = d or load()
    k = " " + str(kind or "").lower() + " "
    if " store" in k and "restaurant" not in k:
        return d["generic"]
    for t in d["trades"]:
        if any(m in k for m in t["match"]):
            return t
    return d["generic"]


def money_slots() -> dict:
    b = PB.load()
    s, cp, nu = PB.pkg(b, "starter"), b["care_plan"], b["no_upfront"]
    return {"starter_setup": PB.usd(s["setup"]), "care": PB.usd(cp["monthly"]), "no_upfront": PB.usd(nu["monthly"]), "months": str(nu["months"]),
            "deposit": PB.words(b)["deposit"], "days": str(s["days"])}


def fill(text: str, slots: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(slots.get(m.group(1), "{" + m.group(1) + "}")), text)


def script_for(lead: dict, who: dict | None = None, d: dict | None = None) -> dict:
    """The words for one lead. who = {me, agency, owner, my_number, day}. lead = a call-list row (name, town, kind, lane, code, problem)."""
    d = d or load()
    who = who or {}
    t = trade_for(lead.get("kind", ""), d)
    lane = lead.get("lane") if lead.get("lane") in d["lanes"] else "no_site"
    slots = {"me": who.get("me") or "<your name>", "agency": who.get("agency") or "<agency>", "owner": who.get("owner") or "<owner>",
             "my_number": who.get("my_number") or "<your number>", "day": who.get("day") or "<day>",
             "name": lead.get("name") or "your business", "town": lead.get("town") or "", "code": lead.get("code") or "",
             "link": lead.get("link") or "<their concept-site link>", "problem": lead.get("problem") or "it wouldn't load",
             "hook_vm": t["hook_vm"], **money_slots()}
    opener = " ".join([fill(d["identify"], slots), fill(d["lanes"][lane], slots), fill(t["hook"], slots), fill(t["ask"], slots)])
    return {"trade": t["id"], "label": t["label"], "lane": lane, "opener": opener, "questions": [fill(q, slots) for q in t["questions"]],
            "close_yes": fill(d["close_yes"], slots), "close_not_now": fill(d["close_not_now"], slots), "voicemail": fill(d["voicemail"], slots)}


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9$'][A-Za-z0-9$',.-]*", text))


SAMPLE = {"roofing": ("Summit Roofing", "Frederick"), "hvac": ("Comfort Air Services", "Rockville"), "plumbing": ("Main Street Plumbing", "Hagerstown"),
          "electrical": ("Bright Line Electric", "Germantown"), "landscaping": ("Green Acres Lawn Care", "Columbia"),
          "remodeling": ("Oak & Stone Remodeling", "Ellicott City"), "auto_repair": ("Route 40 Auto Repair", "Catonsville"),
          "restaurant": ("Casa Lupita", "Frederick"), "other": ("Any Business", "Maryland")}


def all_scripts(d: dict | None = None, who: dict | None = None) -> list:
    d = d or load()
    out = []
    for t in d["trades"] + [d["generic"]]:
        name, town = SAMPLE.get(t["id"], ("Your Business", "Maryland"))
        kind = t["match"][0] if t["match"] else "business"
        out.append({lane: script_for({"name": name, "town": town, "kind": kind, "lane": lane, "problem": "the page shows an error"}, who, d)
                    for lane in d["lanes"]})
    return out


def problems(d: dict | None = None) -> list:
    """[(where, why)] for anything that breaks the rules; [] = fine."""
    d = d or load()
    bad = []
    ms = money_slots()
    for per in all_scripts(d):
        for lane, s in per.items():
            where = f"{s['trade']}/{lane}"
            if not s["opener"].startswith("Hi, it's <your name> with <agency>"):
                bad.append((where, "the opener must say who is calling first"))
            if words(s["opener"]) > MAX_OPENER_WORDS:
                bad.append((where, f"opener is {words(s['opener'])} words (max {MAX_OPENER_WORDS}, about 15 seconds)"))
            if len(s["questions"]) != 3:
                bad.append((where, "needs exactly 3 questions"))
            text = " ".join([s["opener"], s["close_yes"], s["close_not_now"], s["voicemail"]] + s["questions"])
            if BANNED.search(text):
                bad.append((where, f"banned claim: {BANNED.search(text).group(0)!r}"))
            if re.search(r"\{\w+\}", text):
                bad.append((where, "an unfilled {slot}"))
            for k in ("starter_setup", "care", "no_upfront", "deposit"):
                if ms[k] not in s["close_yes"]:
                    bad.append((where, f"close_yes must quote the price book's {k} ({ms[k]})"))
            off = sorted(set(re.findall(r"\$[\d,]*\d", text)) - set(ms.values()))
            if off:
                bad.append((where, f"a price that is not in the price book: {off}"))
    cad = d["cadence"]
    if sum(1 for c in cad if c["what"] == "call") > 2:
        bad.append(("cadence", "more than 1 call + 1 follow-up"))
    if any(c["what"] == "text" and "ONLY if they said" not in c["how"] for c in cad):
        bad.append(("cadence", "a text without their consent"))
    return bad


def coverage(path: str = CALLLIST, d: dict | None = None) -> dict:
    d = d or load()
    try:
        rows = (json.load(open(path, encoding="utf-8")) or {}).get("leads") or []
    except (OSError, ValueError):
        rows = []
    out = {}
    for r in rows:
        tid = trade_for(r.get("kind", ""), d)["id"]
        out[tid] = out.get(tid, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def portal_copy(d: dict | None = None) -> dict:
    """What the caller portal can show next to a lead (no names filled: the page fills {name} {me} ...)."""
    d = d or load()
    ms = money_slots()
    return {"v": 1, "kind": "agency-trade-scripts", "identify": d["identify"], "lanes": d["lanes"],
            "close_yes": fill(d["close_yes"], ms), "close_not_now": d["close_not_now"], "voicemail": d["voicemail"],
            "trades": [{k: t[k] for k in ("id", "label", "match", "hook", "hook_vm", "ask", "questions")} for t in d["trades"]],
            "generic": {k: d["generic"][k] for k in ("id", "label", "hook", "hook_vm", "ask", "questions")},
            "cadence": d["cadence"], "stop_words": d["stop_words"], "targets": d["targets"]}


def markdown(d: dict | None = None) -> str:
    d = d or load()
    cov = coverage(d=d)
    L = ["# Call scripts by trade (the caller's sheet)", "",
         "Generated from `agency/trade_scripts.json` by `python -m agency.trade_scripts --md` (do not edit by hand). Prices: "
         "`agency/pricebook.json`. Every opener says who is calling first and fits in about 15 seconds. Dial by hand, never record, "
         "businesses only, 1 call + 1 follow-up, \"no\" = never again.", "",
         "**How to use it:** the portal shows each business's trade. Read the opener, ask the 3 questions (listen more than you talk), "
         "then the close. If their website is down, or they have an old one, use that version of the opener. **Open their own concept "
         "site (the link in the portal) before you dial**, so you can describe what's on it while you talk, and email that exact link.", ""]
    for per in all_scripts(d):
        s = per["no_site"]
        n = cov.get(s["trade"], 0)
        L += [f"## {s['label']}" + (f" ({n} on today's list)" if n else ""), "",
              f"**Opener (no website):** {s['opener']}", "",
              f"**Opener (website down):** {per['site_down']['opener']}", "",
              f"**Opener (old website):** {per['redesign']['opener']}", "",
              "**3 questions:**", ""] + [f"{i}. {q}" for i, q in enumerate(s["questions"], 1)] + [
              "", f"**Yes:** {s['close_yes']}", "", f"**Not now:** {s['close_not_now']}", "", f"**Voicemail:** {s['voicemail']}", ""]
    L += ["## The 2-week follow-up", "", "| Day | What | How |", "|---|---|---|"]
    L += [f"| {c['day']} | {c['what']} | {c['how']} |" for c in d["cadence"]]
    L += ["", f"**Stop:** {d['stop_words']}", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--coverage", action="store_true")
    a = ap.parse_args(argv)
    bad = problems()
    for w, why in bad:
        print(f"  [FIX] {w}: {why}")
    if a.coverage:
        for k, v in coverage().items():
            print(f"  {k:12} {v}")
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(markdown())
        print(f"  [OK] wrote {a.md}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(portal_copy(), f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"  [OK] wrote {a.json}")
    if not (a.md or a.json or a.coverage):
        for per in all_scripts():
            print(f"\n== {per['no_site']['label']}\n  {per['no_site']['opener']}  ({words(per['no_site']['opener'])} words)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
