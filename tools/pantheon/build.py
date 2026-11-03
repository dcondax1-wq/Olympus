"""PANTHEON builder: every god's reading + the council verdict + the honest NQ relation table -> the JSON files.

Outputs (small JSON):
  research/pantheon/pantheon.json   the page data (gods, council, relation table, sources, what was skipped)
  research/pantheon/states.json     daily regime states per god for Data City (format: docs/PANTHEON.md)
  tools/web_public/pantheon/        the same two files + jarvis.json (the Jarvis card) next to the page
  --out <dir>                       pantheon.json, states.json, jarvis.json there too (the CRONOS task)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import time

import numpy as np
import pandas as pd

from tools.pantheon import council as C
from tools.pantheon import gods as G
from tools.pantheon import sources as SRC
from tools.pantheon import stats as S

ROOT = SRC.ROOT
RESEARCH = os.path.join(ROOT, "research", "pantheon")
WEB = os.path.join(ROOT, "tools", "web_public", "pantheon")
THEME = "#07060d"
STALE_AFTER = 259200              # 3 days: refreshed nightly by CRONOS
ET = "America/New_York"


def _clean(x):
    """JSON-safe: NaN / inf -> None, numpy -> python."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def _honesty(st: dict | None) -> str:
    if not st:
        return "No overlap with the NQ futures history yet."
    p = {r["period"]: r for r in st["periods"]}
    a, b = p.get("2021-25", {}), p.get("2026", {})
    if "corr" in a:
        def c(r):
            return "n/a" if r.get("corr") is None else f"{r['corr']:+.2f}"
        head = "Weak signal" if st["holds"] else "Inverse, context only" if st.get("inverse") else "Context, not a signal"
        return f"{head}: next-day NQ correlation {c(a)} (2021-25), {c(b)} (2026)."
    def m(r):
        return "n/a" if r.get("ratio") is None else f"{r['ratio']:.2f}x"
    head = "Bigger NQ moves on event days" if st["holds"] else "Context, not a signal"
    return f"{head}: event-day NQ move vs other days {m(a)} (2021-25), {m(b)} (2026)."


def build(store: SRC.Store, now: dt.datetime | None = None, nq_path: str = S.NQ_1D) -> tuple[dict, dict]:
    """(pantheon.json, states.json) documents from the store's sources."""
    now = now or dt.datetime.now(dt.timezone.utc)
    now_et = pd.Timestamp(now).tz_convert(ET).tz_localize(None)
    days = S.sessions(end=now_et.normalize())
    ret = S.nq_returns(nq_path)
    gods, votes, rows, state_rows = [], {}, [], []
    for g in G.GODS:
        try:
            r = G.athena(store, days, now=now_et) if g.key == "athena" else G.BUILDERS[g.key](store, days)
        except Exception as e:  # noqa: BLE001 - one broken source never stops the hall
            r = G.Reading(meaning=f"Could not read its data ({e.__class__.__name__}).")
        st = None
        if r.ok and r.flag is not None:
            st = S.abs_move(r.flag, ret)
        elif r.ok and r.vote is not None:
            st = S.relation(r.vote, ret)
            if g.council:
                votes[g.key] = r.vote
        for sid, (lab, ser, first) in r.states.items():
            ser = ser.reindex(days).fillna(False).astype(bool)
            state_rows.append({"id": sid, "god": g.key, "label": lab, "from": None if first is None else str(first.date()),
                               "now": bool(ser.iloc[-1]), "days_on": int(ser.sum()), "on": S.intervals(ser)})
        src = [store.log.get(s, {"id": s, "from": "missing"}) for s in g.sources]
        gods.append({
            "key": g.key, "name": g.name, "glyph": g.glyph, "title": g.title, "why": g.why, "color": g.color,
            "council": g.council, "futures": g.futures, "lag_days": g.lag,
            "sources": [{"id": x["id"], "name": SRC.BY_ID[x["id"]].name, "from": x.get("from"), "newest": x.get("newest")}
                        for x in src],
            "ok": r.ok, "reading": {"value": r.value, "text": r.text}, "asof": r.asof,
            "change": {"value": r.change, "text": r.change_text, "window": r.window},
            "pct": r.pct, "pct_years": r.pct_years, "meaning": r.meaning, "lean": r.lean if r.ok else "offline",
            "vote": r.vote_today if g.council else None, "vote_display": r.vote_today, "subs": r.subs, "spark": r.spark,
            "extra": r.extra, "states_now": [x["label"] for x in state_rows if x["god"] == g.key and x["now"]],
            "stats": st, "honesty": _honesty(st) if r.ok else "",
        })
        if st:
            rows.append(_row(g.name, st))
    hist = C.history(votes)
    cst = S.relation(hist, ret) if not hist.dropna().empty else None
    ath = next(x for x in gods if x["key"] == "athena")
    caution = ""
    if ath["ok"] and ath["lean"] == "caution":
        caution = f"ATHENA warns: {ath['extra'].get('next', {}).get('event', 'an event')} " \
                  f"{['today', 'next session'][min(1, ath['extra'].get('next', {}).get('days', 1))]}: expect bigger moves."
    today = {x["key"]: (x["name"], x["vote"]) for x in gods if x["council"] and x["ok"]}
    verdict = C.verdict(today, caution)
    verdict.update(spark=S.spark(hist, days=365), stats=cst, honesty=_honesty(cst),
                   members=[g.name for g in G.GODS if g.council])
    if cst:
        rows.insert(0, _row("COUNCIL", cst))
    nq = ret.dropna()
    doc = {
        "v": 1, "app": "pantheon", "demo": False, "t": int(now.timestamp()),
        "built": now_et.strftime("%Y-%m-%d %H:%M ET"), "next_session": str(days[-1].date()),
        "council": verdict, "gods": gods, "relation": rows,
        "nq": {"source": "TradingView CME NQ1! daily export (data/NQ_1d.csv)", "first": str(nq.index[0].date()),
               "last": str(nq.index[-1].date()), "sessions": int(len(nq))},
        "method": [
            "Each god's vote is its driver's z-score against the last 5 years (rolling, past only), halved and clipped to -1..+1.",
            "No look-ahead: a value counts for session D only once published before D (FRED: next day; CFTC: Friday for "
            "Tuesday's positions); it is compared with NQ's return of session D.",
            "Hit rate: risk-on votes on up days and risk-off votes on down days, on days with |vote| >= 0.25; chance = the "
            "hit rate if votes were unrelated to NQ.",
            "A god is a 'weak signal' only if corr >= 0.05 and the hit rate beats chance by 2+ points in BOTH 2021-25 and 2026.",
        ],
        "sources": [dict(store.log[s.id]) for s in SRC.SOURCES if s.id in store.log],
        "skipped": list(SRC.SKIPPED),
    }
    states = {
        "v": 1, "app": "pantheon", "t": doc["t"], "built": doc["built"],
        "sessions": {"first": str(days[0].date()), "last": str(days[-1].date()), "calendar": "Mon-Fri"},
        "rule": "A state listed for session D used only data published by the close of session D-1 (no look-ahead). "
                "Before a state's `from` session its source had no data yet: false there means unknown.",
        "gods": [g.key for g in G.GODS], "states": state_rows,
    }
    return _clean(doc), _clean(states)


def _row(name: str, st: dict) -> dict:
    p = {r["period"]: r for r in st["periods"]}
    out = {"god": name, "verdict": st["verdict"], "holds": st["holds"], "inverse": bool(st.get("inverse"))}
    for k, r in p.items():
        tag = "a" if k == "2021-25" else "b"
        if "corr" in r:
            out.update({f"corr_{tag}": r["corr"], f"hit_{tag}": r["hit"], f"chance_{tag}": r["chance"], f"n_{tag}": r["n"]})
        else:
            out.update({f"ratio_{tag}": r["ratio"], f"n_{tag}": r["n_on"]})
    return out


def _cut(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def jarvis_card(doc: dict) -> dict:
    """The Jarvis card (docs/JARVIS_APPS.md): the council verdict, VIX, the 10-year, the next event."""
    cv = doc["council"]
    by = {g["key"]: g for g in doc["gods"]}
    up = sum(1 for g in doc["gods"] if g["ok"])
    level = "ok" if up >= 6 else "warn" if up >= 3 else "bad"
    gauge = f"{cv['gauge']}/100" if cv.get("gauge") is not None else "-"
    kpis = [{"label": "Council", "value": _cut(f"{cv['label'].title()} {gauge}", 24)}]
    for key, lab in (("ares", "VIX"), ("zeus", "10y yield")):
        g = by.get(key)
        if g and g["ok"]:
            k = {"label": lab, "value": _cut(g["reading"]["text"], 24)}
            if g["change"]["text"]:
                k["delta"] = _cut(g["change"]["text"].replace(" ", ""), 16)
            kpis.append(k)
    lines = [_cut(cv["text"], 120)]
    ath = by.get("athena")
    if ath and ath["ok"] and ath["extra"].get("next"):
        n = ath["extra"]["next"]
        lines.append(_cut(f"ATHENA: {n['event']} {n['when']}", 120))
    lines.append(_cut(cv.get("honesty") or "Context, not a signal.", 120))
    label = f"Council: {cv['label'].title()} {gauge}" + ("" if up == len(doc["gods"]) else f" · {up}/{len(doc['gods'])} gods")
    return {"v": 1, "name": "Pantheon", "status": {"level": level, "label": _cut(label, 48)}, "kpis": kpis[:3],
            "lines": lines[:3], "t": doc["t"], "open": "#council", "theme": THEME, "stale_after": STALE_AFTER}


def _write(path: str, obj, compact: bool = True) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":") if compact else (",", ": "),
                  indent=None if compact else 1)
    os.replace(tmp, path)
    return os.path.getsize(path)


def write(doc: dict, states: dict, research: str | None = RESEARCH, web: str | None = WEB, out: str | None = None) -> dict:
    """Write the files; returns {path: bytes}."""
    card = jarvis_card(doc)
    sizes = {}
    if research:
        sizes[os.path.join(research, "pantheon.json")] = _write(os.path.join(research, "pantheon.json"), doc, compact=False)
        sizes[os.path.join(research, "states.json")] = _write(os.path.join(research, "states.json"), states)
    for d in (web, out):
        if d:
            for name, obj in (("pantheon.json", doc), ("states.json", states), ("jarvis.json", card)):
                sizes[os.path.join(d, name)] = _write(os.path.join(d, name), obj)
    return sizes


def demo_fixture(doc: dict) -> dict:
    """The page's demo copy (fixture.json): a frozen real build, marked demo."""
    d = json.loads(json.dumps(doc))
    d["demo"] = True
    return d


def run(offline: bool = False, fixtures: str | None = None, out: str | None = None, research: str | None = RESEARCH,
        web: str | None = WEB, now=None, fixture_json: bool = False, echo=print) -> dict:
    t0 = time.time()
    store = SRC.Store(offline=offline, fixtures=fixtures)
    store.prefetch()
    doc, states = build(store, now=now)
    sizes = write(doc, states, research, web, out)
    if fixture_json and web:
        sizes[os.path.join(web, "fixture.json")] = _write(os.path.join(web, "fixture.json"), demo_fixture(doc))
    for s in doc["sources"]:
        echo(f"  {s['id']:<22} {s['from']:<8} newest {s.get('newest') or '-':<10} {s.get('error') or ''}")
    cv = doc["council"]
    echo(f"PANTHEON: {sum(g['ok'] for g in doc['gods'])}/8 gods, council {cv['label']} {cv.get('gauge')}/100 "
         f"({time.time() - t0:.1f}s)")
    for p, n in sizes.items():
        echo(f"  wrote {os.path.relpath(p, ROOT)} ({n:,} bytes)")
    return doc
