"""Strategy Lab data for the Strategy Brain (cities/mind/) and the Research Hub's Strategy Lab tab (cities/hub.html).

    python tools/build_strategy_lab.py           writes tools/web_public/cities/lab-data.json
    python tools/build_strategy_lab.py --check   exit 1 when lab-data.json is stale

One row per tested strategy, with up to three spans of numbers (trades/week, win %, PF, $/month, max DD $) and a verdict
(live | paper | promising | rejected). Sources, in order (a later source never overwrites an earlier id):
  1. live: tools/web_public/edge.json bots (LIT/Zlarior, ATLAS): the edge-health backtest of the live settings (last 40 sessions)
  2. research/lab/popular_ict.json + research/lab/popular_classic.json (the popular-strategy sessions; rows
     {id, name, family, spans: {<span>: {tpw, win, pf, usd_mo, maxdd}} | [..] | {tpw, ...}, verdict, rules?})
  3. research/lab/LEADERBOARD.md (the Strategy Lab table: dev / confirm / ytd spans; gate PASS in a span = promising)
When neither popular file exists yet, tools/strategy_lab_fixture.json fills (2) and the output says "fixture": true, so the
pages show a SAMPLE banner (never presented as real results). Read only research; changes no bot or model.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "cities", "lab-data.json")
POPULAR = [os.path.join(ROOT, "research", "lab", "popular_ict.json"), os.path.join(ROOT, "research", "lab", "popular_classic.json")]
FIXTURE = os.path.join(ROOT, "tools", "strategy_lab_fixture.json")
LEADER = os.path.join(ROOT, "research", "lab", "LEADERBOARD.md")
EDGE = os.path.join(ROOT, "tools", "web_public", "edge.json")
VERDICTS = ("live", "paper", "promising", "rejected")
# months in each Strategy Lab span (protocol: dev 2026-01-02..06-30, confirm 07-01..10-16, ytd = both)
LAB_MONTHS = {"dev": 6.0, "confirm": 3.5, "ytd": 9.5}
LIVE_RULES = {
    "lit": ["Sweep of a liquidity level (>= 0.5 ATR) after an inducement, then displacement and a 5m CISD back through it.",
            "Limit at the CISD level (30 min), a 1m CISD confirms; entry at the next 1m open, 1 trade a day 02:00-15:30 ET.",
            "Stop 1 tick beyond the sweep extreme, size follows the stop; one target: the VIX band, banked at 8R."],
    "atlas": ["Three lobes, each its own hours and 1 trade a day: EMA trend pullback, MACD divergence at a sweep, S/R sweep + reclaim.",
              "Entry at the next 5m open after the trigger close; LIT goes first (no ATLAS entry while LIT is in a trade).",
              "Stop beyond the setup's sweep wick; VIX-band target (S/R: 2R); breakeven + costs at 1R."],
}


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _txt(v, n=200):
    return re.sub(r"[<>]", "", str(v if v is not None else ""))[:n].strip()


def verdict(v) -> str:
    s = str(v or "").lower()
    if "live" in s or "adopt" in s:
        return "live"
    if "reject" in s or "fail" in s or "dead" in s or "no edge" in s:
        return "rejected"
    if "paper" in s:
        return "paper"
    if "promis" in s or "pass" in s or "open" in s or "candidate" in s or "watch" in s:
        return "promising"
    return "rejected" if not s else "promising"


def span(k, d) -> dict | None:
    if not isinstance(d, dict):
        return None
    g = lambda *ks: next((_num(d.get(x)) for x in ks if _num(d.get(x)) is not None), None)  # noqa: E731
    out = {"k": _txt(k or d.get("k") or d.get("span") or d.get("period") or "span", 24), "tpw": g("tpw", "trades_wk", "per_week"),
           "win": g("win", "win_pct", "wr"), "pf": g("pf"), "usd_mo": g("usd_mo", "usd_month", "per_month"), "maxdd": g("maxdd", "max_dd", "mdd")}
    if out["maxdd"] is not None:
        out["maxdd"] = -abs(out["maxdd"])
    return out if any(out[x] is not None for x in ("tpw", "pf", "usd_mo")) else None


def spans(v) -> list:
    if isinstance(v, list):
        out = [span(None, x) for x in v]
    elif isinstance(v, dict) and any(isinstance(x, dict) for x in v.values()):
        out = [span(k, x) for k, x in v.items()]
    elif isinstance(v, dict):
        out = [span("all", v)]
    else:
        out = []
    return [x for x in out if x][:3]


def rules(r) -> list:
    v = r.get("rules") or r.get("how") or r.get("summary") or r.get("desc") or r.get("description") or ""
    lines = [str(x) for x in v] if isinstance(v, list) else re.split(r"(?<=[.;])\s+|\n", str(v))
    return [_txt(x, 160) for x in lines if _txt(x)][:3]


def row(r, src) -> dict | None:
    if not isinstance(r, dict):
        return None
    name = _txt(r.get("name") or r.get("id"), 80)
    rid = re.sub(r"[^a-z0-9_]+", "_", str(r.get("id") or name).lower()).strip("_")[:60]
    if not rid:
        return None
    return {"id": rid, "name": name, "family": _txt(r.get("family") or "other", 30), "verdict": verdict(r.get("verdict")),
            "rules": rules(r), "spans": spans(r.get("spans")), "src": src}


def _load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def popular() -> tuple[list, bool]:
    rows, found = [], False
    for p in POPULAR:
        d = _load(p)
        if d is None:
            continue
        found = True
        items = d if isinstance(d, list) else (d.get("strategies") or d.get("rows") or d.get("items") or []) if isinstance(d, dict) else []
        fam = "ICT" if "ict" in os.path.basename(p) else "classic"
        for r in items:
            x = row({**r, "family": r.get("family") or fam} if isinstance(r, dict) else r, os.path.basename(p))
            if x:
                rows.append(x)
    if found:
        return rows, False
    d = _load(FIXTURE) or {}
    return [x for x in (row(r, "fixture") for r in d.get("strategies", [])) if x], True


def leaderboard() -> list:
    try:
        text = open(LEADER, encoding="utf-8").read()
    except OSError:
        return []
    by: dict = {}
    for line in text.splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) < 12 or c[0] in ("name", "") or set(c[0]) <= set("-:"):
            continue
        name, period = c[0], c[1]
        if period not in LAB_MONTHS:
            continue
        net, dd = _num(c[7].replace(",", "").replace("+", "")), _num(c[8].replace(",", ""))
        sp = {"k": period, "tpw": _num(c[3]), "win": _num(c[4]), "pf": _num(c[6]),
              "usd_mo": round(net / LAB_MONTHS[period]) if net is not None else None, "maxdd": -abs(dd) if dd is not None else None}
        e = by.setdefault(name, {"id": "lab_" + re.sub(r"[^a-z0-9_]+", "_", name.lower()), "name": name, "family": "Strategy Lab (LIT variants)",
                                 "verdict": "rejected", "rules": [], "spans": [], "src": "LEADERBOARD.md", "_pass": False})
        e["spans"].append(sp)
        e["_pass"] = e["_pass"] or c[11].upper() == "PASS"
    out = []
    for e in by.values():
        e["verdict"] = "promising" if e.pop("_pass") else "rejected"
        order = {"dev": 0, "confirm": 1, "ytd": 2}
        e["spans"] = sorted(e["spans"], key=lambda s: order.get(s["k"], 9))[:3]
        e["rules"] = [f"Strategy Lab variant of LIT: {e['name'].replace('_', ' ')}.",
                      "Gate: PF >= 1.3, 2-5 trades a week, max DD under $2k, net > 0, eval pass at least zero-edge + 10 pts.",
                      "Spans: dev 2026 H1, confirm Jul-Oct 2026, ytd both (real NQ1!, costs in)."]
        out.append(e)
    return out


def live() -> list:
    d = _load(EDGE) or {}
    out = []
    for k, b in (d.get("bots") or {}).items():
        if k not in LIVE_RULES or not isinstance(b, dict):
            continue
        sp = {"k": f"last {int(_num(b.get('sessions')) or 40)} sessions", "tpw": _num(b.get("tpw")), "win": _num(b.get("win")), "pf": _num(b.get("pf")),
              "usd_mo": _num(b.get("usd_month")), "maxdd": None}
        out.append({"id": k, "name": "LIT (Zlarior)" if k == "lit" else "ATLAS (EMA + MACD + S/R)", "family": "live", "verdict": "live",
                    "rules": LIVE_RULES[k], "spans": [sp], "src": "edge.json"})
    return out


def best_addon(rows) -> dict:
    """the strongest non-live, non-rejected strategy whose EVERY span is positive with PF >= 1.3 and 1-5 trades a week:
    the worst span's $/month decides. Overlap with LIT's own trades is NOT measured here (the combo protocol does that)."""
    real = any(r["src"].startswith("popular_") for r in rows)
    best, why = None, ("No separate strategy passes every span yet (PF >= 1.3, $/month > 0, 1-5 trades a week)." if real else
                       "No pick yet: the popular-strategy files (ICT + classic) have not landed. Sample rows and LIT variants are never picked.")
    for r in rows:
        # only a SEPARATE strategy can be an add-on: the popular files (a LEADERBOARD row is a LIT variant = a replacement; a SAMPLE row is never "best")
        if r["verdict"] in ("live", "rejected") or len(r["spans"]) < 2 or not r["src"].startswith("popular_"):
            continue
        s = r["spans"]
        if all((x["pf"] or 0) >= 1.3 and (x["usd_mo"] or 0) > 0 and 1 <= (x["tpw"] or 0) <= 5 for x in s):
            worst = min(x["usd_mo"] for x in s)
            if best is None or worst > best["worst_usd_mo"]:
                best = {"id": r["id"], "name": r["name"], "worst_usd_mo": worst, "src": r["src"]}
    if best:
        best["why"] = (f"Every span positive with PF >= 1.3; the worst span still makes ${best['worst_usd_mo']:,.0f}/month. "
                       "Next: the combo test with LIT (overlap, 2-4 trades a week together) before any paper run.")
    return best or {"id": None, "why": why}


def build() -> dict:
    pop, fixture = popular()
    seen, rows = set(), []
    for r in live() + pop + leaderboard():
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        rows.append(r)
    return {"v": 1, "fixture": fixture, "sources": ["edge.json", "fixture" if fixture else "popular_*.json", "LEADERBOARD.md"],
            "n": len(rows), "rows": rows, "best_addon": best_addon(rows)}


def main(argv) -> int:
    d = build()
    text = json.dumps(d, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    if "--check" in argv:
        try:
            cur = open(OUT, encoding="utf-8").read()
        except OSError:
            cur = ""
        ok = cur.strip() == text
        print("lab-data.json " + ("is fresh" if ok else "is STALE: run python tools/build_strategy_lab.py"))
        return 0 if ok else 1
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {d['n']} strategies ({'fixture' if d['fixture'] else 'popular files'}), best add-on: {d['best_addon'].get('name')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
