"""Read-only API for the new dashboard (web_next/): the live-settings replay, tested variants, study trades, rules.

Mounted by server.py with  app.include_router(router).  Everything is served from files already in the repo:
  research/lab/backtest_live.json   tools/export_backtest.py  (5-year live-loop replay, per-trade reports, lessons)
  research/lab/variant_results.json every variant tested, 2026 and 5-year columns
  research/lab/replays.json         session bars + LIT trade chart records (tools/export_replays.py): /api/next/tradechart/<id>
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
from . import lab_scope

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "research", "lab")
STUDY = os.path.join(ROOT, "research", "study")
RUNS = os.path.join(ROOT, "research", "runs")
WRITEUPS = os.path.join(ROOT, "research", "writeups")
LIT_DOCS = os.path.join(ROOT, "research", "lit")
ARCHIVE = os.path.join(ROOT, *lab_scope.ARCHIVE_DIR.split("/"))      # the previous strategy (Liquidity Engine, Oct 17)
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
    ix = _chart_index()
    if ix:
        rows = [{**t, "chart": ix[(t.get("day"), int(t.get("entry_t") or 0))]} if (t.get("day"), int(t.get("entry_t") or 0)) in ix else t
                for t in rows]
    years = sorted({str(t.get("day", ""))[:4] for t in d.get("trades") or [] if t.get("day")})
    return _J({"year": year, "years": years, "built": d.get("meta", {}).get("built"), "model": d.get("meta", {}).get("model") or "engine",
               "strategy": d.get("meta", {}).get("strategy"), "trades": rows[::-1]})


def _replays():
    return _read(os.path.join(LAB, "replays.json"))


def _chart_index():
    """(day, entry_t) -> chart id of every LIT trade chart record in research/lab/replays.json."""
    rp = _replays() or {}
    ch = rp.get("charts") or {}
    with _lock:
        hit = _cache.get("_chart_index")
        if hit and hit[0] is ch:
            return hit[1]
    ix = {(r.get("day"), int((r.get("entry") or {}).get("t") or 0)): k for k, r in ch.items()}
    with _lock:
        _cache["_chart_index"] = (ch, ix)
    return ix


@router.get("/api/next/tradechart/{cid}")
def tradechart(cid: str):
    """One LIT trade's chart record (bars + every marker; tools/lit_chart_data.py) for web_next/js/tradechart.js."""
    rp = _replays()
    if not rp:
        return _J({"error": "research/lab/replays.json missing: run python tools/export_replays.py"}, 404)
    rec = (rp.get("charts") or {}).get(cid)
    if not rec:
        return _J({"error": f"no chart for {cid}"}, 404)
    return _J(rec)


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
    lit = lab_scope.is_lit_model(lm)
    # the cold-streak filter is the previous strategy's: while LIT is live it is read from its archived lock and its bundle
    cfg = lm.get("equity_filter") or ((_read(os.path.join(ROOT, "live_model_engine.json")) or {}).get("equity_filter") if lit else None)
    now = equity_filter.status(cfg)
    last = equity_filter.load()[-(int((cfg or {}).get("lookback", 15))):]
    d = (_read(os.path.join(LAB, "backtest_engine.json")) if lit else None) or _live_bt() or {}
    hist = [{"day": t.get("day"), "r": t.get("r"), "half": bool(t.get("half")), "pnl": t.get("pnl")} for t in d.get("trades") or []]
    et = equity_filter.eval_timing(now, equity_filter.sessions_since_flip(cfg))
    model = lm.get("model") or "engine"
    rules = None
    if model == "lit":
        # LIT has no cold-streak filter: the eval odds are LIT's own (stored run lit_live), plus its weekly stop / Monday rule
        from . import lit_live
        et = {**et, **lit_live.eval_odds(ROOT)}
        try:
            from .live import BOT
            rules = (BOT.state or {}).get("lit_rules")
        except Exception:
            rules = None
    return _J({"config": cfg, "now": now, "eval_timing": et, "window": last, "history": hist, "model": model, "lit_rules": rules,
               "archived": lit, "archive_label": lab_scope.ARCHIVE_LABEL if lit else None,
               "lit": {k: (lm.get("lit") or {}).get(k) for k in ("monday", "wk_stop")} if model == "lit" else None,
               "lit_sizing": lm.get("lit_sizing") if model == "lit" else None})


# ------------------------------------------------------------------ research lab: run library + write-ups
@router.get("/api/next/runs")
def runs():
    """The run library index (one row per stored backtest, headline numbers for 2026 / 2021-25 / all)."""
    idx = _read(os.path.join(RUNS, "index.json"))
    if not idx:
        return _J({"runs": [], "count": 0, "note": "no runs yet: python tools/runlib.py baseline"})
    # every row tagged lit | engine; while LIT is live the reference run is lit_live and the engine's lock is the archive's
    lm = _read(os.path.join(ROOT, "live_model.json")) or {}
    rows = [{**r, "strategy": lab_scope.strategy_of_run(r)} for r in idx.get("runs") or []]
    ids = {r["id"] for r in rows}
    base = lab_scope.live_baseline(lm, ids) or idx.get("baseline")
    old = lab_scope.ENGINE_BASELINE if lab_scope.ENGINE_BASELINE in ids and base != lab_scope.ENGINE_BASELINE else None
    for r in rows:
        if r["id"] == base:
            r["family"], r["status"] = "baseline", "baseline"
        elif old and r["id"] == old:
            r["status"] = "baseline"
    return _J({**idx, "runs": rows, "baseline": base, "archive_baseline": old,
               "live_strategy": "lit" if lab_scope.is_lit_model(lm) else "engine", "archive_label": lab_scope.ARCHIVE_LABEL})


@router.get("/api/next/run/{rid}")
def run(rid: str):
    """One stored run with every trade and day."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", rid) or rid in ("index",) or rid.startswith("_"):
        return _J({"error": "bad id"}, 400)
    d = _read(os.path.join(RUNS, rid + ".json"))
    if d and lab_scope.strategy_of_run(d) == "lit" and "cold-streak" in str(d.get("method") or ""):
        d = {**d, "method": lab_scope.LIT_METHOD, "strategy": "lit"}    # runlib's default text names the engine's filter
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
    for folder, kind in ((WRITEUPS, "writeup"), (LIT_DOCS, "writeup"), (ARCHIVE, "writeup"), (os.path.join(ROOT, "research"), "archive"), (LAB, "archive")):
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for n in names:
            if not n.endswith(".md") or n.upper().startswith("STRATEGY") or n.upper() == "INDEX.MD":   # INDEX: tools/writeups_index.py
                continue
            path = os.path.join(folder, n)
            if os.path.getsize(path) > 400_000:
                continue
            text = _read(path, parse=lambda fh: fh.read()) or ""
            meta, body = _front(text)
            slug = ("lit-" + n[:-3]) if folder == LIT_DOCS else ("archive-engine-2026-10-17" if folder == ARCHIVE else n[:-3])
            strat = "archive" if folder == ARCHIVE else lab_scope.strategy_of_doc(slug, os.path.relpath(path, ROOT))
            items.append({"slug": slug, "kind": kind, "file": os.path.relpath(path, ROOT), "mtime": int(os.path.getmtime(path)),
                          **meta, "body": body, "strategy": strat if kind == "writeup" else "engine", "pin": lab_scope.pin_rank(slug)})
    # LIT write-ups first (the pinned ones in order), then the previous strategy's, then the older reports
    items.sort(key=lambda x: (x["kind"] != "writeup", {"lit": 0, "archive": 1}.get(x["strategy"], 2), x["pin"], -(x.get("mtime") or 0)))
    return _J({"items": items})


@router.get("/api/next/lab/{name}")
def lab_file(name: str):
    """A research data file for a dashboard view: research/lab/<name>.json (montecarlo, intraday_heat, ...)."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", name):
        return _J({"error": "bad name"}, 400)
    # <name>_engine: the previous strategy's copy from the archive (montecarlo_engine, intraday_heat_engine)
    d = _read(os.path.join(ARCHIVE, name[:-7] + ".json")) if name.endswith("_engine") else _read(os.path.join(LAB, name + ".json"))
    return _J(d) if d is not None else _J({"error": "not found"}, 404)


@router.get("/api/next/archive")
def archive():
    """The previous strategy (Liquidity Engine, locked 2026-10-17) for the Archive page: its lock, its last bundle's periods
    (research/lab/backtest_engine.json, no per-trade rows), its stored runs' headline numbers, the README in plain words
    (research/archive/engine-2026-10-17/README.md) and the cold-streak filter's state on the PC's shadow ledger."""
    lm = _read(os.path.join(ROOT, "live_model_engine.json")) or {}
    bt = _read(os.path.join(LAB, "backtest_engine.json")) or {}
    idx = _read(os.path.join(RUNS, "index.json")) or {}
    runs = {r["id"]: r for r in idx.get("runs") or [] if r.get("id") in (lab_scope.ENGINE_BASELINE, lab_scope.ENGINE_PREV)}
    readme = _read(os.path.join(ARCHIVE, "README.md"), parse=lambda fh: fh.read()) or ""
    cfg = lm.get("equity_filter")
    now = equity_filter.status(cfg)
    return _J({"label": lab_scope.ARCHIVE_LABEL, "dir": lab_scope.ARCHIVE_DIR, "live_model": lm,
               "periods": bt.get("periods") or {}, "meta": {k: (bt.get("meta") or {}).get(k) for k in ("built", "strategy", "method")},
               "runs": runs, "readme": _front(readme)[1] if readme else "",
               "cold": {"config": cfg, "now": now, "eval_timing": equity_filter.eval_timing(now, equity_filter.sessions_since_flip(cfg))},
               "engine_runs": sum(1 for r in idx.get("runs") or [] if lab_scope.strategy_of_run(r) == "engine")})


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


@router.get("/api/next/lit_extra")
def lit_extra():
    """The LIT panels' static data (tools/lit_dash_extra.py): MFFU plan, LIT size rule + switches, timing rules, session
    boxes, 2026 stats and sessions (forward eval odds). The live parts (levels, setups, session boxes' prices) come from
    the PC bot's own state (/api/live/state), so the state passed here is empty."""
    lm = _read(os.path.join(ROOT, "live_model.json")) or {}
    if not lab_scope.is_lit_model(lm):
        return _J({"error": "live_model.json is not LIT"}, 404)
    try:
        from tools import lit_dash_extra
        return _J(lit_dash_extra.extra({}, lm))
    except Exception as e:                                   # never 500 the dashboard over a panel
        return _J({"error": f"{e.__class__.__name__}: {e}"}, 500)


@router.get("/api/next/lit_backtest")
def lit_backtest(period: str = "2026"):
    """The LIT replay (research/lab/backtest_live.json) in /api/backtest's shape for the PC pages that show the live strategy
    (Today widgets, Chart overlays, Replays, Journal, Reports, Weekly Review): trades, days with the MFFU balance / trailing
    MLL, stats, eval, LIT levels + session boxes per day, events, and the LIT state (the PC bot's when it runs LIT, else
    the state at the last bar of the data files). period = 2026 (default) | all. /api/backtest stays for the Archive."""
    try:
        from . import lit_dash
        return _J(lit_dash.backtest(period))
    except FileNotFoundError:
        return _J({"error": "research/lab/backtest_live.json missing: run python tools/export_backtest.py"}, 404)
    except Exception as e:                                   # never 500 the dashboard
        return _J({"error": f"{e.__class__.__name__}: {e}"}, 500)


# ------------------------------------------------------------------ the PC bot's own account / status + the phone extras
# /api/next/pc/status, /api/next/pc/account, /api/next/pc/trade/<entry_t>, /api/next/extras (engine/pcdash_api.py, read-only)
from .pcdash_api import router as _pc_router  # noqa: E402
router.include_router(_pc_router)

# Bot Control center (engine/botctl.py): START with the preflight checklist, status strip, safety switches. Its POST routes
# call the same functions as the CLI (server.py fills botctl.HOOKS with the /api/live/start and /api/live/stop code paths).
from .botctl import router as _botctl_router  # noqa: E402
router.include_router(_botctl_router)

# Hub pages (Prop Firms, Business, Market, Learn, System): read-only GETs over research/props + repo files (engine/hub_api.py)
from .hub_api import router as _hub_router  # noqa: E402
router.include_router(_hub_router)
# Business tools (statement, tax year, payout + eval-purchase reminders, scaling calendar, goal, ROI, watchers): engine/biz_api.py
from .biz_api import router as _biz_router  # noqa: E402
router.include_router(_biz_router)

# Operator tools (pulse for sound / desktop alerts + tab badge, live chart with the LIT levels, log viewer, NinjaTrader
# panel, session timeline, settings viewer, morning report): read-only GETs (engine/pcops_api.py)
from .pcops_api import router as _ops_router  # noqa: E402
router.include_router(_ops_router)
