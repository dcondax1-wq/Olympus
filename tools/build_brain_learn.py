"""THE BRAIN's learning file (day-brain-app 2026-11-24): tools/web_public/brain/learn.json, what each brain region learned.

Sources, best first:
  research/learn/journal.json     [{date, pillar, text, n, usd, status}]                       (the learning bot's journal, research/learn/BRAIN_FEED.md)
  research/learn/brain_state.json {pillar: {confidence, lessons, last_learned, testing_next, market_read}}
  research/learn/insights.json    the weekly market-learn lessons (tools/market_learn_weekly.py): used while the two above have not landed
Nothing is made up: a field no source has stays null and the page says "not scored yet". Read only, no network.
    python tools/build_brain_learn.py           write it
    python tools/build_brain_learn.py --check   exit 1 when the file is stale against its sources
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "brain", "learn.json")
JOURNAL = "research/learn/journal.json"
STATE = "research/learn/brain_state.json"
INSIGHTS = "research/learn/insights.json"
PILLARS = ("lit", "atlas", "blitz", "of", "learn", "risk")
ALIAS = {"orderflow": "of", "order_flow": "of", "zlarior": "lit", "market": "learn", "shared": "learn", "accounts": "risk"}


def _load(rel):
    p = os.path.join(ROOT, rel)
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _pid(x):
    k = str(x or "").strip().lower()
    k = ALIAS.get(k, k)
    return k if k in PILLARS else None


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def _s(v, n=280):
    return " ".join(str(v if v is not None else "").replace("->", "→").replace("<", "").replace(">", "").split())[:n]


def journal_rows(j):
    rows = j if isinstance(j, list) else (j.get("journal") or j.get("rows") or []) if isinstance(j, dict) else []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        pid = _pid(r.get("pillar"))
        ev = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
        txt = r.get("text") or r.get("noticed")      # day-brain-research journal uses "noticed" + evidence{n, usd}
        if not pid or not txt:
            continue
        out.append({"date": _s(r.get("date"), 10), "pillar": pid, "text": _s(txt), "n": _num(r.get("n", ev.get("n"))), "usd": _num(r.get("usd", ev.get("usd"))),
                    "status": _s(r.get("status") or "noted", 20).lower()})
    out.sort(key=lambda r: r["date"], reverse=True)
    return out[:120]


def state_rows(s):
    out = {}
    src = s.get("pillars", s) if isinstance(s, dict) else {}
    for k, v in (src.items() if isinstance(src, dict) else []):
        pid = _pid(k)
        if not pid or not isinstance(v, dict):
            continue
        c = _num(v.get("confidence"))
        if c is not None and c > 1:
            c = c / 100.0
        tn = v.get("testing_next")
        out[pid] = {"confidence": None if c is None else round(max(0.0, min(1.0, c)), 3),
                    "lessons": int(v["lessons"]) if isinstance(v.get("lessons"), (int, float)) else len(v["lessons"]) if isinstance(v.get("lessons"), list) else None,
                    "last_learned": _s((v["last_learned"].get("what") if isinstance(v.get("last_learned"), dict) else v.get("last_learned")), 120) or None,
                    "testing_next": [_s(x, 200) for x in (tn if isinstance(tn, list) else [tn] if tn else [])][:4],
                    "market_read": _s(v.get("market_read"), 240) or None}
    return out


def from_insights(ins):
    """the weekly lessons as journal rows + a state without a confidence (the insights file does not score one)"""
    day = _s(ins.get("built"), 10)
    rows, state = [], {}
    for k, p in (ins.get("pillars") or {}).items():
        pid = _pid(k)
        if not pid or not isinstance(p, dict):
            continue
        for t in p.get("lessons") or []:
            rows.append({"date": day, "pillar": pid, "text": _s(t), "n": None, "usd": None, "status": "found"})
        fix = p.get("last_fix")
        nxt = []
        if isinstance(fix, dict) and fix.get("key"):
            st = _s(fix.get("status") or "registered", 20).lower()
            what = _s(f"{fix.get('kind', 'fix')} {fix.get('bucket', '')}".strip(), 80)
            why = "; ".join(_s(w, 60) for w in (fix.get("why") or [])[:3])
            if st in ("registered", "testing", "queued"):
                nxt.append(f"{what} (registered {_s(fix.get('registered'), 10)})")
            else:
                rows.append({"date": _s(fix.get("tested") or day, 10), "pillar": pid, "text": f"Tested a fix: {what} -> {st}" + (f" ({why})" if why else ""),
                             "n": None, "usd": None, "status": st})
        state[pid] = {"confidence": None, "lessons": len(p.get("lessons") or []), "last_learned": day or None,
                      "testing_next": nxt,
                      "market_read": _s(p.get("read"), 240) or None}
    for t in ins.get("shared") or []:
        rows.append({"date": day, "pillar": "learn", "text": _s(t), "n": None, "usd": None, "status": "found"})
    cur = ins.get("current") or {}
    read = ", ".join(x for x in [f"{cur['regime']} week" if cur.get("regime") else "", f"{cur['vix_band']}" if cur.get("vix_band") else "",
                                 f"prior day {cur['prior_day']}" if cur.get("prior_day") else ""] if x)
    state["learn"] = {"confidence": None, "lessons": len(ins.get("shared") or []), "last_learned": day or None,
                      "testing_next": [], "market_read": (f"Market read for {cur.get('for')}: {read}" if read else None)}
    return rows, state


def build():
    j, s, ins = _load(JOURNAL), _load(STATE), _load(INSIGHTS)
    src, rows, state = [], [], {}
    if j is not None:
        rows = journal_rows(j)
        src.append(JOURNAL)
    if s is not None:
        state = state_rows(s)
        src.append(STATE)
    cur, line, built = None, None, None
    if isinstance(ins, dict):
        r2, s2 = from_insights(ins)
        if j is None:
            rows = sorted(r2, key=lambda r: r["date"], reverse=True)
        for k, v in s2.items():
            state.setdefault(k, v)
        cur, line, built = ins.get("current"), _s(ins.get("phone_line"), 200) or None, _s(ins.get("built"), 40)
        src.append(INSIGHTS)
    return {"v": 1, "kind": "brain-learn", "built_from": built, "sources": src, "journal_landed": j is not None, "state_landed": s is not None,
            "paper_only": True, "note": "What each brain learned. Research only: nothing here changes a live rule.",
            "current": cur, "line": line, "journal": rows, "state": state}


def main(argv):
    d = build()
    txt = json.dumps(d, indent=1, ensure_ascii=False) + "\n"
    if "--check" in argv:
        try:
            with open(OUT, encoding="utf-8") as fh:
                old = fh.read()
        except OSError:
            old = ""
        ok = old == txt
        print("brain/learn.json " + ("fresh" if ok else "STALE: run python tools/build_brain_learn.py"))
        return 0 if ok else 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(d['journal'])} journal rows, {len(d['state'])} regions, from {', '.join(d['sources']) or 'nothing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
