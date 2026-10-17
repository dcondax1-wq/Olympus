"""Read-only API for the new dashboard (web_next/): the live-settings replay, tested variants, study trades, rules.

Mounted by server.py with  app.include_router(router).  Everything is served from files already in the repo:
  research/lab/backtest_live.json   tools/export_backtest.py  (5-year live-loop replay, per-trade reports, lessons)
  research/lab/variant_results.json every variant tested, 2026 and 5-year columns
  research/study/                   trades the owner is reviewing (json + png pairs)
  research/runs/                    the research run library (tools/runlib.py): every backtest with its trades and days
  research/writeups/ + research/*.md  research write-ups (front matter + markdown) and the older reports
  live_model.json / STRATEGY.md     the locked live strategy
Files are re-read only when their mtime changes.
"""
from __future__ import annotations

import json
import os
import re
import threading

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from . import equity_filter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "research", "lab")
STUDY = os.path.join(ROOT, "research", "study")
RUNS = os.path.join(ROOT, "research", "runs")
WRITEUPS = os.path.join(ROOT, "research", "writeups")
router = APIRouter()
_cache: dict = {}
_lock = threading.Lock()


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _read(path: str, parse=json.load):
    """Parsed file contents, cached per mtime. None when the file is missing or unreadable."""
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] == mt:
            return hit[1]
    try:
        with open(path, encoding="utf-8") as fh:
            val = parse(fh)
    except Exception:
        return None
    with _lock:
        _cache[path] = (mt, val)
    return val


def _live_bt():
    return _read(os.path.join(LAB, "backtest_live.json"))


@router.get("/api/next/results")
def results():
    """Everything in the live replay except the per-trade rows (those come from /api/next/trades)."""
    d = _live_bt()
    if not d:
        return _J({"error": "research/lab/backtest_live.json missing: run python tools/export_backtest.py"}, 404)
    out = {k: v for k, v in d.items() if k != "trades"}
    out["trade_count"] = len(d.get("trades") or [])
    return _J(out)


@router.get("/api/next/trades")
def trades(year: str = "2026"):
    """Per-trade rows of the live replay, newest first. year = 2021..2026 or 'all'."""
    d = _live_bt()
    if not d:
        return _J({"error": "backtest_live.json missing", "trades": []}, 404)
    rows = d.get("trades") or []
    if year != "all":
        rows = [t for t in rows if str(t.get("day", "")).startswith(year)]
    years = sorted({str(t.get("day", ""))[:4] for t in d.get("trades") or [] if t.get("day")})
    return _J({"year": year, "years": years, "built": d.get("meta", {}).get("built"), "trades": rows[::-1]})


@router.get("/api/next/variants")
def variants():
    v = _read(os.path.join(LAB, "variant_results.json"))
    return _J(v or {"rows": [], "columns": {}, "note": "research/lab/variant_results.json missing"})


def _study_items():
    try:
        names = sorted(os.listdir(STUDY))
    except OSError:
        return []
    groups: dict = {}
    for n in names:
        stem, ext = os.path.splitext(n)
        if ext.lower() not in (".json", ".png"):
            continue
        groups.setdefault(stem, {})[ext.lower()[1:]] = n
    items = []
    for stem, g in groups.items():
        it = {"id": stem, "date": stem[:10], "title": stem[11:].replace("_", " ") if len(stem) > 11 else stem,
              "image": g.get("png"), "data": None}
        if g.get("json"):
            it["data"] = _read(os.path.join(STUDY, g["json"]))
        items.append(it)
    return sorted(items, key=lambda x: x["id"], reverse=True)


@router.get("/api/next/study")
def study():
    return _J({"items": _study_items()})


@router.get("/api/next/study/file/{name}")
def study_file(name: str):
    # only plain file names that really exist in research/study (no paths)
    if os.path.basename(name) != name or name not in set(os.listdir(STUDY) if os.path.isdir(STUDY) else []):
        return _J({"error": "not found"}, 404)
    return FileResponse(os.path.join(STUDY, name))


@router.get("/api/next/strategy")
def strategy():
    lm = _read(os.path.join(ROOT, "live_model.json")) or {}
    md = _read(os.path.join(ROOT, "STRATEGY.md"), parse=lambda fh: fh.read()) or ""
    return _J({"live_model": lm, "markdown": md})


@router.get("/api/next/cold")
def cold():
    """Cold-streak filter now (shadow ledger) plus its history across the live replay."""
    lm = _read(os.path.join(ROOT, "live_model.json")) or {}
    cfg = lm.get("equity_filter")
    now = equity_filter.status(cfg)
    last = equity_filter.load()[-(int((cfg or {}).get("lookback", 15))):]
    d = _live_bt() or {}
    hist = [{"day": t.get("day"), "r": t.get("r"), "half": bool(t.get("half")), "pnl": t.get("pnl")} for t in d.get("trades") or []]
    return _J({"config": cfg, "now": now, "eval_timing": equity_filter.eval_timing(now, equity_filter.sessions_since_flip(cfg)), "window": last, "history": hist})


# ------------------------------------------------------------------ research lab: run library + write-ups
@router.get("/api/next/runs")
def runs():
    """The run library index (one row per stored backtest, headline numbers for 2026 / 2021-25 / all)."""
    return _J(_read(os.path.join(RUNS, "index.json")) or {"runs": [], "count": 0, "note": "no runs yet: python tools/runlib.py baseline"})


@router.get("/api/next/run/{rid}")
def run(rid: str):
    """One stored run with every trade and day."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", rid) or rid in ("index",) or rid.startswith("_"):
        return _J({"error": "bad id"}, 400)
    d = _read(os.path.join(RUNS, rid + ".json"))
    return _J(d) if d else _J({"error": "not found"}, 404)


def _front(text: str):
    """Split a '---' front-matter block (key: value lines) from the markdown body."""
    meta, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = text[end + 4:].lstrip("\n")
    if "runs" in meta:
        meta["runs"] = [x.strip() for x in meta["runs"].strip("[]").split(",") if x.strip()]
    if "title" not in meta:
        m = re.search(r"^#\s+(.+)$", body, re.M)
        meta["title"] = m.group(1).strip() if m else "Untitled"
    return meta, body


@router.get("/api/next/writeups")
def writeups():
    """Research write-ups (research/writeups/*.md) newest first, then the older reports in research/ as an archive."""
    items = []
    for folder, kind in ((WRITEUPS, "writeup"), (os.path.join(ROOT, "research"), "archive"), (LAB, "archive")):
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for n in names:
            if not n.endswith(".md") or n.upper().startswith("STRATEGY"):
                continue
            path = os.path.join(folder, n)
            if os.path.getsize(path) > 400_000:
                continue
            text = _read(path, parse=lambda fh: fh.read()) or ""
            meta, body = _front(text)
            items.append({"slug": n[:-3], "kind": kind, "file": os.path.relpath(path, ROOT), "mtime": int(os.path.getmtime(path)),
                          **meta, "body": body})
    items.sort(key=lambda x: (x["kind"] != "writeup", -(x.get("mtime") or 0)))
    return _J({"items": items})


@router.get("/api/next/lab/{name}")
def lab_file(name: str):
    """A research data file for a dashboard view: research/lab/<name>.json (montecarlo, intraday_heat, ...)."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", name):
        return _J({"error": "bad name"}, 400)
    d = _read(os.path.join(LAB, name + ".json"))
    return _J(d) if d is not None else _J({"error": "not found"}, 404)


@router.get("/api/next/news")
def news_hub(compact: int = 0):
    """The news hub (tools/news_hub.py -> data/news/hub.json): USD calendar with the bot's blackouts, scored headlines,
    per-day summaries. compact=1 returns the same cut the public site embeds in data.json (next 7 days, 40 headlines)."""
    path = os.path.join(ROOT, "data", "news", "hub.json")
    d = _read(path)
    if not d:
        return _J({"error": "data/news/hub.json missing: run python tools/news_hub.py --out data/news/hub.json",
                   "events": [], "headlines": [], "days": [], "next": None, "sources": []}, 404)
    if compact:
        from tools import news_hub as nh
        return _J(nh.compact(d))
    return _J(d)
