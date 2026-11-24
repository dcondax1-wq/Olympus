"""The FOUR PILLARS of the Olympus trading side (owner 2026-11-23 23:00 ET: "Orderflow and BLITZ alongside LIT and ATLAS are gonna make
us. Those are our 4 pillars"): LIT (Zlarior), ATLAS, BLITZ, ORDER FLOW. The static half of tools/web_public/pillars/ (the live half,
accounts / armed / today / 7-day clock / the day's thinking / tick days, comes from the PC's post in the browser: pillars/pillarscore.js).

    python tools/build_pillars.py           writes tools/web_public/pillars/pillars-data.json
    python tools/build_pillars.py --check   exit 1 when it is stale

Every number is read from a file in the repo and carries its source; nothing is typed in by hand except the words. Sources:
  LIT      research/lab/backtest_live.json periods (2026 H1 picked on / H2 check / 2021-25 reference) + tools/web_public/edge.json (last 40 sessions)
  ATLAS    research/second/atlas.json numbers (H1, H2, 2025, 2021-24) + edge.json
  BLITZ    research/writeups/blitz-review-2026-11-18.md span table (2026 Jan-Jun / Jul-Oct / 2021-25, $150 a trade, costs in)
  ORDER FLOW research/lab/orderflow.json (status, the 3 tick designs OF1-OF3, round-1 bar tests + round-2 LVN tests, each with spans)
Read only research; changes no bot, no model, no switch.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "pillars", "pillars-data.json")
SRC = {
    "lit": "research/lab/backtest_live.json",
    "atlas": "research/second/atlas.json",
    "edge": "tools/web_public/edge.json",
    "blitz": "research/writeups/blitz-review-2026-11-18.md",
    "of": "research/lab/orderflow.json",
}
STUDY_DAYS = 60                     # engine/tickrec.STUDY_DAYS: the order-flow study runs at 60 NQ tick days


def _load(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _n(v):
    try:
        f = float(str(v).replace(",", "").replace("$", "").replace("+", "").replace("%", "").replace("*", ""))
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def sp(k, tpw, win, pf, usd_mo, maxdd=None, n=None):
    return {"k": k, "tpw": _n(tpw), "win": _n(win), "pf": _n(pf), "usd_mo": _n(usd_mo), "maxdd": -abs(_n(maxdd)) if _n(maxdd) is not None else None,
            "n": int(_n(n)) if _n(n) is not None else None}


def recent(bot):
    b = ((_load(SRC["edge"]) or {}).get("bots") or {}).get(bot)
    if not isinstance(b, dict):
        return None
    return sp(f"last {int(_n(b.get('sessions')) or 40)} sessions", b.get("tpw"), b.get("win"), b.get("pf"), b.get("usd_month"), None, b.get("n"))


def lit_spans():
    per = (_load(SRC["lit"]) or {}).get("periods") or {}
    out = []
    for key, label in (("2026 H1 (picked on)", "2026 H1"), ("2026 H2 (check)", "2026 H2"), ("2021-25 (reference)", "2021-25")):
        p = per.get(key)
        if isinstance(p, dict):
            out.append(sp(label, p.get("per_week"), p.get("win_pct"), p.get("pf"), p.get("per_month"), p.get("max_dd"), p.get("trades")))
    return out


def atlas_spans():
    num = (_load(SRC["atlas"]) or {}).get("numbers") or {}
    out = []
    for key, label in (("H1", "2026 H1"), ("H2", "2026 H2"), ("y2025", "2025"), ("y2124", "2021-24")):
        p = num.get(key)
        if isinstance(p, dict):
            out.append(sp(label, p.get("tpw"), p.get("win"), p.get("pf"), p.get("per_month"), p.get("max_dd"), p.get("trades")))
    return out


def blitz_spans():
    try:
        text = open(os.path.join(ROOT, SRC["blitz"]), encoding="utf-8").read()
    except OSError:
        return []
    out = []
    for label, rx in (("2026 H1", r"^\| 2026 Jan-Jun \|"), ("2026 H2", r"^\| 2026 Jul-Oct \|"), ("2021-25", r"^\| 2021-25 \(5m\) \|")):
        line = next((l for l in text.splitlines() if re.match(rx, l)), None)
        if not line:
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        # | Span | Trades | / week | Weeks with 2+ | Win % | Avg R | PF | Net | $ a month | Max DD |
        if len(c) >= 10:
            out.append(sp(label, c[2], c[4], c[6], c[8], c[9], c[1]))
    return out


def of_tests():
    d = _load(SRC["of"]) or {}
    rows = []
    def add(name, t, stage):
        if not isinstance(t, dict):
            return
        spans = []
        for k in ("2026 H1", "2026 H2", "2021-25"):
            v = t.get(k)
            if isinstance(v, dict):
                spans.append(sp(k, v.get("per_wk"), v.get("win%"), v.get("pf"), v.get("$/mo"), v.get("maxDD$"), v.get("n")))
            elif _n(v) is not None:                                   # a LIT-rule test: only the $ gained vs all-LIT in the span
                spans.append({"k": k, "tpw": None, "win": None, "pf": None, "usd_mo": None, "maxdd": None, "n": None, "net_vs_lit": _n(v)})
        rows.append({"id": "of_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:50], "name": name, "stage": stage,
                     "verdict": "rejected" if "REJECT" in str(t.get("verdict", "")).upper() else "promising", "spans": spans,
                     "placebo_p": _n(t.get("placebo_p")), "holm_p": _n(t.get("holm_p"))})
    for name, t in (d.get("bar_tests") or {}).items():
        add(name, t, "round 1: bar proxies")
    for name, t in ((d.get("round2") or {}).get("standalone") or {}).items():
        add(name, t, "round 2: LVN stand-alone")
    return rows


def build() -> dict:
    lit, atlas, blitz = lit_spans(), atlas_spans(), blitz_spans()
    ofd = _load(SRC["of"]) or {}
    tests = of_tests()
    g = lambda s, k: next((x for x in s if x["k"] == k), {})  # noqa: E731
    pf = lambda s, k: g(s, k).get("pf")  # noqa: E731
    designs = [{"id": k, "text": v} for k, v in (ofd.get("tick_designs") or {}).items()]
    gates = {"OF1": "Pass = more net $ than all LIT in both 2026 halves while keeping at least half the trades",
             "OF2": "Pass = more net $ than all LIT in both 2026 halves while keeping at least half the trades",
             "OF3": "Pass = PF >= 1.15 and net > 0 in each half, >= 0.5 trades a week, placebo p < 0.10"}
    for x in designs:
        x["gate"] = gates.get(x["id"], "")
    pillars = [
        {"id": "lit", "name": "LIT", "alias": "Zlarior", "color": "#f1c14b", "bot": "lit", "state": "live",
         "status": "On the PC bot: MFFU Builder 50K eval + Builder 25K #2 eval",
         "edge": (f"Sweep, inducement, CISD; stop 1 tick beyond the sweep, one VIX-band target. PF {pf(lit, '2026 H1')} / {pf(lit, '2026 H2')} "
                  f"in the 2026 halves, {pf(lit, '2021-25')} over 2021-25 (barely positive before 2026)."),
         "spans": lit, "recent": recent("lit"), "src": f"{SRC['lit']} + {SRC['edge']}",
         "next": "Pass the Builder 50K eval, then the 25K #2; no rule change without the proof protocol (STATE.md, CLAUDE.md)."},
        {"id": "atlas", "name": "ATLAS", "alias": "EMA · MACD · S/R", "color": "#77db89", "bot": "atlas", "state": "live",
         "status": "On the PC bot: MFFU Builder 25K funded (3 small lobes, 1 trade a day each)",
         "edge": (f"Three small lobes that rarely trade together: London EMA pullback, MACD divergence at a sweep, NY level reclaim. "
                  f"PF {pf(atlas, '2026 H1')} / {pf(atlas, '2026 H2')} in 2026, {pf(atlas, '2025')} in 2025, {pf(atlas, '2021-24')} over 2021-24."),
         "spans": atlas, "recent": recent("atlas"), "src": f"{SRC['atlas']} + {SRC['edge']}",
         "next": "First payout on the funded 25K: ask the max $1,000 at $2,100 profit (CLAUDE.md); keep the rules (358 tweaks found nothing better)."},
        {"id": "blitz", "name": "BLITZ", "alias": "the scalper", "color": "#9d59ee", "bot": "blitz", "state": "off",
         "status": "Built and switched off: paper only, meant for a Rapid eval (hidden on the dashboard since 2026-11-15)",
         "edge": (f"Rides a 1m band break for 30 minutes (checks every 30 min 11:00-15:30, 1.5 ATR stop, trail after +1R). "
                  f"PF {pf(blitz, '2026 H1')} / {pf(blitz, '2026 H2')} in 2026, {pf(blitz, '2021-25')} over 2021-25 ($150 a trade, costs in)."),
         "spans": blitz, "recent": None, "src": SRC["blitz"],
         "chain": [
             {"key": "filter", "label": "Day filter", "help": "Trade a day only if yesterday's 09:30-16:00 range is at least 0.8 x the mean of the last 14."},
             {"key": "band", "label": "Noise band", "help": "Today's 09:30 open x (1 +/- sigma): sigma = the usual move for that minute over the last 14 sessions."},
             {"key": "check", "label": "30-min check", "help": "Only at the 1m closes 11:00, 11:30 ... 15:30: a close above the band = long, below = short."},
             {"key": "entry", "label": "Entry", "help": "Market at the next bar's open + 1 tick; max 6 a day, none after -3R; never against Zlarior or ATLAS."},
             {"key": "stop", "label": "Stop", "help": "The signal close -/+ 1.5 x ATR(14) of 5m bars; after +1R the stop trails 1.5R behind the best price."},
             {"key": "exit", "label": "30-min exit", "help": "Out at the close of the 30th bar after entry (the clock exit is where it earns), or flat by 15:55."}],
         "chain_src": "engine/blitz.py",
         "next": ("Stays OFF (owner switch). Its one paying use: next to Zlarior on a FUNDED 50K while LIT is flat (+$290-300 a month in 2026, "
                  "+$16 in 2021-25): needs the 50K funded first and new code (blitz-review-2026-11-18).")},
        {"id": "of", "name": "ORDER FLOW", "alias": "ticks, delta, absorption", "color": "#5fd0c9", "bot": None, "state": "collecting",
         "status": f"Recording NQ ticks on the PC; the study runs at {STUDY_DAYS} tick days",
         "edge": ("Not proven yet: " + str(ofd.get("status") or "no result") + ". The real test needs tick data (who hit the bid / the ask)."),
         "spans": [], "recent": None, "src": SRC["of"],
         "designs": designs, "tests": tests, "study_days": STUDY_DAYS, "trigger": ofd.get("tick_trigger") or "",
         "chain": [
             {"key": "record", "label": "Record ticks", "help": "NinjaTrader's tick recorder saves every NQ trade (price, size, side) on the PC."},
             {"key": "backfill", "label": "Backfill", "help": "Outside trading hours it asks NinjaTrader for older tick days, one at a time."},
             {"key": "days", "label": f"{STUDY_DAYS} tick days", "help": f"The study waits for {STUDY_DAYS} NQ tick days, so one lucky week cannot decide."},
             {"key": "study", "label": "Run OF1-OF3", "help": "research/orderflow/of_study.py runs the 3 pre-registered designs once (a 2nd, final look after the backfill)."},
             {"key": "verdict", "label": "Verdict", "help": "Each design has its pass rule written before the data: a pass goes to paper first, never straight to money."}],
         "chain_src": "research/writeups/orderflow-program-2026-11-23.md, engine/tickrec.py",
         "next": f"Keep the recorder on; at {STUDY_DAYS} tick days the PC runs OF1-OF3 by itself and posts one line (engine/tickrec autopilot)."},
    ]
    return {"v": 1, "title": "The Four Pillars", "said": "Orderflow and BLITZ alongside LIT and ATLAS are gonna make us. Those are our 4 pillars.",
            "said_when": "2026-11-23 23:00 ET", "pillars": pillars, "sources": SRC}


def main(argv) -> int:
    d = build()
    text = json.dumps(d, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    if "--check" in argv:
        try:
            cur = open(OUT, encoding="utf-8").read()
        except OSError:
            cur = ""
        ok = cur.strip() == text
        print("pillars-data.json " + ("is fresh" if ok else "is STALE: run python tools/build_pillars.py"))
        return 0 if ok else 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: " + ", ".join(f"{p['name']} {len(p['spans'])} spans" for p in d["pillars"])
          + f", {len(d['pillars'][3]['tests'])} order-flow tests")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
