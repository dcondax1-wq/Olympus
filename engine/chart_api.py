"""Read-only API of the trade pictures (engine/trade_chart.py) for the PC dashboard (Bot Brain, ATLAS, Trades pages).
Mounted by engine/next_api.py.

  GET /api/next/charts                 per strategy: the PC bot's newest pictures (logs/charts, its own live / paper trades)
                                       and the backtest examples (research/lab/chart_examples), each with its image URL
  GET /api/next/chart/{id}             one PNG; id = <strategy>.<day>_<HHMM>_<side> (PC picture first, else the example);
                                       ?ex=1 = the example only
"""
from __future__ import annotations

import json
import os
import re

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from . import trade_chart as TC

router = APIRouter()
_ID = re.compile(r"^([a-z0-9_]+)[./](\d{4}-\d{2}-\d{2}_\d{4}_(?:long|short))(?:\.png)?$")


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _dirs():
    """(PC pictures dir, examples dir): tests point these elsewhere."""
    return TC.PC_DIR, TC.EXAMPLES


@router.get("/api/next/charts")
def charts_index(n: int = 24):
    try:
        pc, ex = _dirs()
        ix = TC.Store(pc).ix if os.path.isdir(pc) else {"strategies": {}}
        exi = TC.Store(ex).ix if os.path.isdir(ex) else {"strategies": {}}
        v = TC.index_view(ix, base="/api/next/chart/", n=max(1, min(int(n), 60)), examples=exi, ex_base="/api/next/chart/")
        for s in v["strategies"].values():        # /api/next/chart/<key>.<tid>?v=<hash>
            for r in s["items"]:
                r["url"] = f"/api/next/chart/{r['key']}.{r['tid']}" + (f"?v={r['hash']}" if r.get("hash") else "")
            for r in s["examples"]:
                r["url"] = f"/api/next/chart/{r['key']}.{r['tid']}?ex=1" + (f"&v={r['hash']}" if r.get("hash") else "")
        v["source"] = "PC bot (logs/charts) + backtest examples (research/lab/chart_examples)"
        return _J(v)
    except Exception as e:                       # never 500 the dashboard over a page
        return _J({"error": f"{e.__class__.__name__}: {e}", "strategies": {}}, 500)


@router.get("/api/next/chart/{cid:path}")
def chart_png(cid: str, ex: int = 0):
    m = _ID.match(cid or "")
    if not m or m.group(1) not in TC.STRATS:
        return _J({"error": "bad chart id"}, 404)
    key, tid = m.group(1), m.group(2)
    pc, exd = _dirs()
    for root in ((exd,) if ex else (pc, exd)):
        p = os.path.join(root, key, tid + ".png")
        if os.path.isfile(p):
            return FileResponse(p, media_type="image/png", headers={"Cache-Control": "public, max-age=300"})
    return _J({"error": "no picture"}, 404)
