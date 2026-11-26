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
FORWARD = "research/forward/forward.json"           # big-forward 2026-11-26: the watched leads on new sessions (tools/forward_paper.py)
IDEAMILL = "research/ideamill/summary.json"
LIVEGAP = "research/livegap/daily.json"
HEALTH = "research/health/bands.json"
OF_LEARN = "research/orderflow/learner.json"        # the order-flow learner's lines when it lands ({lines: [{date, text}]})
SETUPS = "research/learn/lit_setups.json"
SCORE_EVAL = "research/setupscore/eval.json"         # big-setupscore 2026-11-26: the pre-registered holdout verdict
PROMOTE_N = 20
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
    t = str(v if v is not None else "").replace("->", "→").replace(">=", "≥").replace("<=", "≤")
    t = t.replace("<", " under ").replace(">", " over ")    # the page writes text only; keep the meaning of a < / > (big-learnview)
    return " ".join(t.split()).replace("( ", "(")[:n]


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


# ================================================================================================ the learning view (big-learnview 2026-11-26)
def _weekdays(a, z):
    import datetime as dt
    try:
        d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(z)
    except (TypeError, ValueError):
        return None
    n, d = 0, d0
    while d <= d1:
        n += d.weekday() < 5
        d += dt.timedelta(days=1)
    return n


def forward_rows(f):
    """Each watched rule: how many new trades, forward R vs its own backtest, how close to the promotion bar."""
    out = []
    for rid, r in ((f or {}).get("rules") or {}).items():
        if not isinstance(r, dict):
            continue
        b = r.get("band") or {}
        n = int(r.get("n") or 0)
        days = b.get("days") or [None, None]
        bd = _weekdays(days[0], days[1]) if days and days[0] else None
        rate = (b.get("n_bt") or 0) / bd if bd else None            # events a session in its backtest
        need = max(0, PROMOTE_N - n)
        eta = None if not rate else int(round(need / rate))
        st = _s(r.get("status") or "watching", 12)
        if st == "promote":
            word = "ready: the lead writes your yes/no card"
        elif st == "demoted":
            word = "dropped: worse on new days than in its backtest"
        elif st == "error":
            word = "could not be scored tonight"
        else:
            word = f"needs {need} more new trades" + (f" (~{eta} trading days at its usual pace)" if eta is not None else "")
        out.append({"id": _s(rid, 60), "what": _s(r.get("desc"), 160), "bot": _s(r.get("bot"), 10), "kind": _s(r.get("kind"), 16),
                    "n": n, "need": PROMOTE_N, "fwd_r": _num(r.get("mean")), "fwd_sum": _num(r.get("sum")), "band_r": _num(b.get("mu")),
                    "band_n": b.get("n_bt"), "z": _num(r.get("z")), "status": st, "eta_days": eta, "word": word,
                    "progress": round(min(1.0, n / PROMOTE_N), 3)})
    out.sort(key=lambda x: (-x["progress"], x["eta_days"] if x["eta_days"] is not None else 10 ** 6, x["id"]))
    return {"from": _s((f or {}).get("fwd_from"), 10) or None, "data_end": _s((f or {}).get("data_end"), 10) or None,
            "sessions": (f or {}).get("forward_sessions"), "rules": out} if f else None


def ideamill_block(m, st):
    if not isinstance(m, dict):
        return None
    c = m.get("counts") or {}
    bi = (st or {}).get("ideamill") or {}
    return {"tested": c.get("trials_total"), "scored": c.get("scored"), "families": c.get("v3_families"),
            "passed_discovery": c.get("G1_bh"), "passed_haircut": c.get("G2_dsr"), "passed_holdouts": c.get("G3_holdouts"),
            "survivors": len(m.get("v3_survivors") or []), "lucky_expected": c.get("expected_raw_p05_by_luck"),
            "data_end": _s(m.get("data_end"), 10) or None, "best": _s(bi.get("best"), 80) or None}


def livegap_block(d):
    if not isinstance(d, dict):
        return None
    diffs = []
    for r in d.get("rows") or []:
        for x in r.get("diffs") or []:
            diffs.append({"day": _s(x.get("day"), 10), "when": _s(x.get("when"), 24), "kind": _s(x.get("kind"), 10), "bot": _s(x.get("bot"), 8),
                          "usd": _num(x.get("usd")), "detail": _s(x.get("detail"), 140)})
    diffs.sort(key=lambda x: (x["day"], x["when"]), reverse=True)
    return {"to": _s(d.get("bars_to") or d.get("last_day"), 10) or None,
            "totals": {k: _num(v) for k, v in (d.get("totals_usd_by_kind") or {}).items()}, "recent": diffs[:6], "count": len(diffs)}


def health_block(h):
    if not isinstance(h, dict):
        return None
    out = {}
    for bot, b in (h.get("bots") or {}).items():
        if not isinstance(b, dict):
            continue
        lv, bd = b.get("live") or {}, b.get("bands") or {}
        tw = b.get("twin_live_window") or {}
        out[_s(bot, 10)] = {"live_n": lv.get("n"), "live_r": _num(lv.get("mean_r")), "zone": _s(lv.get("zone"), 80) or None,
                            "band_2026": [_num((bd.get("2026") or {}).get(k)) for k in ("p5", "p50", "p95")],
                            "twin_n": tw.get("n"), "twin_r": _num(tw.get("mean_r")),
                            "twin_pct_2026": _num((tw.get("pct_of_same_length_windows") or {}).get("2026"))}
    return {"window": h.get("window"), "bots": out}


def lit_setups(st):
    x = (((st or {}).get("pillars") or {}).get("lit") or {}).get("setups")
    if not isinstance(x, dict):
        return None
    return {"data_end": _s(x.get("data_end"), 10) or None, "setups": x.get("setups"), "taken": x.get("taken"),
            "funnel": [{"step": int(f[0]), "why": _s(f[1], 40), "n": int(f[2])} for f in (x.get("funnel") or []) if isinstance(f, list) and len(f) == 3],
            "costs_most": [_s(v, 120) for v in (x.get("costs_most") or [])][:3], "earns_most": [_s(v, 120) for v in (x.get("earns_most") or [])][:3],
            "recent": [_s(v, 220) for v in (x.get("recent") or [])][:6]}


def of_lines(o, st):
    rows = []
    for r in ((o or {}).get("lines") or []) if isinstance(o, dict) else []:
        if isinstance(r, dict) and r.get("text"):
            rows.append({"date": _s(r.get("date"), 10), "text": _s(r.get("text"), 240)})
    p = (((st or {}).get("pillars") or {}).get("orderflow") or {})
    return {"lines": sorted(rows, key=lambda r: r["date"], reverse=True)[:8], "next": _s(p.get("testing_next"), 200) or None}


def next_tests(st):
    out = []
    for k, v in (((st or {}).get("pillars") or {}).items()):
        pid = _pid(k)
        if pid and isinstance(v, dict) and v.get("testing_next"):
            tn = v["testing_next"]
            for t in (tn if isinstance(tn, list) else [tn])[:2]:
                out.append({"pillar": pid, "text": _s(t, 220)})
    return out


def setup_scores():
    """The newest sessions' LIT setups (research/learn/lit_setups.json review) with their 'similar setups' score (engine/setup_score,
    pool dated before each setup's day) + the holdout verdict. Display only."""
    doc, ev = _load(SETUPS), _load(SCORE_EVAL)
    if not isinstance(doc, dict):
        return None
    try:
        sys.path.insert(0, ROOT)
        from engine import setup_score as SS
    except Exception:  # noqa: BLE001
        return None
    rows = []
    for r in doc.get("review") or []:
        if not isinstance(r, dict):
            continue
        f = r.get("f") or {}
        try:
            hh, mm = str(r.get("at") or "").split(":")
            mod = int(hh) * 60 + int(mm)
        except ValueError:
            mod = None
        d = -1 if str(r.get("side") or "").upper().startswith("S") else 1
        sc = SS.score(SS.feats(mod=mod, depth=f.get("depth"), disp=f.get("disp"), idm=f.get("idm"), vix=SS._prior_vix(str(r.get("day")))), d,
                      before=str(r.get("day")))
        rows.append({"day": _s(r.get("day"), 10), "at": _s(r.get("at"), 5), "side": _s(r.get("side"), 6), "step": r.get("step"),
                     "why": _s(r.get("why"), 40), "outcome": _s(r.get("outcome"), 12), "r": _num(r.get("r")),
                     "n": (sc or {}).get("n"), "win": (sc or {}).get("win"), "avg_r": (sc or {}).get("avg_r")})
    rows.sort(key=lambda x: (x["day"], x["at"]), reverse=True)
    A = ((ev or {}).get("holdouts") or {}).get("A Jul-Oct 2026 (pool to 2026-06-30)") or {}
    a = A.get("all with an outcome") or {}
    return {"verdict": _s((ev or {}).get("verdict") or "not checked", 20), "rows": rows[:12],
            "holdout": {k: a.get(k) for k in ("n", "spearman", "p", "auc", "top_third_r", "bottom_third_r")} if a else None}


def learning(st):
    f, m, d, h, o = _load(FORWARD), _load(IDEAMILL), _load(LIVEGAP), _load(HEALTH), _load(OF_LEARN)
    src = [p for p, x in ((FORWARD, f), (IDEAMILL, m), (LIVEGAP, d), (HEALTH, h), (OF_LEARN, o)) if x is not None]
    return {"sources": src, "forward": forward_rows(f), "ideamill": ideamill_block(m, st), "livegap": livegap_block(d),
            "health": health_block(h), "lit_setups": lit_setups(st), "setup_scores": setup_scores(), "of": of_lines(o, st), "next": next_tests(st),
            "promote_bar": f"{PROMOTE_N} new trades, holding near its own backtest, money made overall"}


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
            "current": cur, "line": line, "journal": rows, "state": state, "learning": learning(s)}


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
