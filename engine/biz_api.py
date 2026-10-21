"""Read-only API for the business tools on the PC dashboard (web_next/js/next/bizpages.js). Mounted by engine/next_api.py.
Every route reads the owner's files through tools/business.py; nothing here starts, arms, routes, sizes or stops anything.

  GET /api/next/hub/biz                       statement, tax year, payout reminders, eval planner, scaling calendar, Z06
                                              goal, ROI per account, rule / code watcher (the PC bot's eval balance when it runs)
  GET /api/next/hub/biz/statement/<YYYY-MM>   the monthly P&L statement as a PDF (HTML when reportlab is missing; ?html=1)
  GET /api/next/hub/biz/tax/<YYYY>.csv        the tax-year summary CSV (not tax advice)
"""
from __future__ import annotations

import json
import os
import re

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from tools import business as B

router = APIRouter()


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _pc_eval():
    try:
        from . import hub_api
        ac = hub_api._account(hub_api._bot())
        return (ac or {}).get("eval")
    except Exception:
        return None


@router.get("/api/next/hub/biz")
def hub_biz():
    try:
        return _J(B.view(pc_eval=_pc_eval()))
    except Exception as e:                                   # never 500 the page without a reason
        return _J({"error": f"{e.__class__.__name__}: {str(e)[:160]}"}, 500)


@router.get("/api/next/hub/biz/statement/{month}")
def hub_biz_statement(month: str, html: int = 0):
    if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", month or ""):
        return _J({"error": "month must be YYYY-MM"}, 400)
    try:
        path = B.write_statement(month, html=bool(html))
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {str(e)[:160]}"}, 500)
    kind = "application/pdf" if path.endswith(".pdf") else "text/html"
    return FileResponse(path, media_type=kind, filename=os.path.basename(path) if kind == "application/pdf" else None)


@router.get("/api/next/hub/biz/tax/{year}.csv")
def hub_biz_tax(year: int):
    if not 2020 <= int(year) <= 2100:
        return _J({"error": "bad year"}, 400)
    try:
        text = B.tax_csv(B.tax_year(year))
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {str(e)[:160]}"}, 500)
    return Response(text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="tax_{int(year)}.csv"'})
