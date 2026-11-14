"""Build the PROP EVAL TRACKER product (digital download): spreadsheet, how-to PDF, licence, listing copy, covers, upload zip.

    python -m money_machines.products.build_eval_tracker            # rebuild everything in money_machines/products/eval_tracker/
    python -m money_machines.products.build_eval_tracker --zip      # + money_machines/out/products/prop_eval_tracker_v1.zip (the upload)
    python -m money_machines.products.build_eval_tracker --verify   # LibreOffice recomputes the spreadsheet: must equal eval_math.py
    python -m money_machines.products.build_eval_tracker --no-images  # skip the Chromium parts (PDF, covers)

The web app (eval_tracker/prop_eval_tracker.html) is hand-written and copied as is. Everything uses the same math
(money_machines/products/eval_math.py). The product tracks the buyer's own rules; it promises nothing, names no firm and talks
to no server. Prices, fees and platform rules: docs/MONEY_MACHINES.md section 3.
"""
from __future__ import annotations

import argparse
import base64
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

from money_machines.products import eval_math as M

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.join(HERE, "eval_tracker")
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(os.environ.get("MONEY_MACHINES_OUT") or os.path.join(ROOT, "money_machines", "out"), "products")
XLSX = os.path.join(PROD, "Prop_Eval_Tracker.xlsx")
APP = os.path.join(PROD, "prop_eval_tracker.html")
PDF = os.path.join(PROD, "How_to_use.pdf")
VERSION = "1.0"
FIRST, LAST = 7, 206          # Log data rows (row 6 = the Start row)
EXAMPLE_RULES = {"start": 50000, "target": 3000, "max_loss": 2000, "type": "EOD trailing", "lock": 100, "daily_limit": "", "consistency": "", "min_days": 1}
EXAMPLE_DAY = {"date": "2026-11-16", "pnl": 420, "low": 49850, "high": 50510, "trades": 2, "note": "Example row: type your first day over it"}

LISTING = {
    "id": "prop-eval-tracker", "version": VERSION, "price_usd": 17,
    "title": "Prop Firm Evaluation Tracker: Drawdown Left, Daily Limit, Consistency and Position Size (Excel, Google Sheets + Offline Web App)",
    "short": "Know your drawdown left before every session. A spreadsheet and an offline web page for futures prop-firm evaluations.",
    "description": [
        "Most evaluations end on a rule, not on the market: the trailing max loss, a daily limit, a consistency rule. This tracker keeps those numbers in front of you.",
        "WHAT YOU GET",
        "- Spreadsheet for Excel and Google Sheets: your rules, a daily log, a dashboard (drawdown left, max-loss level, target left, consistency check, status) and a position-size helper",
        "- Offline web app (one HTML file): the same tracker with a chart, CSV export and backups; your data stays in your browser",
        "- How-to PDF (2 pages) and a licence",
        "WORKS WITH",
        "- End-of-day trailing, intraday trailing or static max loss, with an optional point where the trail stops",
        "- Optional daily loss limit, consistency rule and minimum trading days",
        "- Micro and E-mini index futures, gold and crude (dollars per point built in)",
        "WHAT IT IS NOT",
        "- No signals, no predictions, no advice. It applies the rules you type; your firm's own dashboard always has the final word.",
        "- Not affiliated with, endorsed by or connected to any prop firm, broker or platform.",
        "Instant download. Made with the help of AI coding tools; designed, checked and supported by me.",
        "Futures trading involves substantial risk of loss and is not suitable for everyone. No results are shown or promised.",
    ],
    "tags_etsy": ["prop firm tracker", "trading journal", "futures trading", "drawdown tracker", "trading spreadsheet", "day trading log",
                  "risk management", "excel template", "google sheets", "position size", "eval tracker", "funded trader", "trader planner"],
    "faq": [
        ["Does it work with my firm?", "If you can type your firm's rules into it (how the max loss moves, the daily limit, the consistency rule), yes. Check your firm's rules page; they change."],
        ["Is this financial advice?", "No. It tracks the rules you enter. It does not tell you what or when to trade."],
        ["Does it connect to my broker or firm?", "No. You type one line per day. Nothing is sent anywhere."],
        ["Which apps open it?", "Excel (Windows or Mac), Google Sheets (File > Import), and any modern browser for the web app. Apple Numbers opens it but may drop the drop-down lists."],
        ["Refunds?", "It is a digital file. If it does not work for you, message me within 14 days and I will help or refund you."],
    ],
    "files": ["Prop_Eval_Tracker.xlsx", "prop_eval_tracker.html", "How_to_use.pdf", "LICENSE.txt", "README.txt"],
    "images": ["cover.jpg (1280 x 720: Gumroad / Payhip cover)", "cover_square.jpg (2000 x 2000: Etsy first photo)", "app_screenshot.jpg (gallery)"],
    "platforms": {
        "Payhip (free plan)": {"fee": "5% + card fees (Stripe/PayPal, about 2.9% + $0.30)", "net_usd": None},
        "Gumroad": {"fee": "10% + $0.50 per sale + card fees (30% on Gumroad Discover sales)", "net_usd": None},
        "Etsy": {"fee": "$0.20 listing + 6.5% + 3% + $0.25 processing (US); Offsite Ads 12-15% only on sales they bring", "net_usd": None},
    },
}


def fees(price: float) -> dict:
    """Net per sale on each platform's basic plan (estimates from the 2026-11-14 research; card fees assumed 2.9% + $0.30)."""
    card = price * 0.029 + 0.30
    return {"Payhip (free plan)": round(price - price * 0.05 - card, 2), "Gumroad": round(price - price * 0.10 - 0.50 - card, 2),
            "Etsy": round(price - 0.20 - price * 0.065 - (price * 0.03 + 0.25), 2)}


# ------------------------------------------------------------------------------------------------ the spreadsheet
def build_xlsx(path: str = XLSX, rules: dict | None = None, days: list | None = None) -> str:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    rules = rules or EXAMPLE_RULES
    days = [EXAMPLE_DAY] if days is None else days
    F = "Arial"
    title = Font(name=F, size=16, bold=True)
    bold = Font(name=F, size=11, bold=True)
    norm = Font(name=F, size=11)
    small = Font(name=F, size=10, color="555555")
    blue = Font(name=F, size=11, color="0000FF")
    head_fill = PatternFill("solid", fgColor="EEEAE2")
    calc_fill = PatternFill("solid", fgColor="F4F4F4")
    input_fill = PatternFill("solid", fgColor="FFF2CC")
    line = Border(bottom=Side(style="thin", color="BBBBBB"))
    money = '$#,##0.00;-$#,##0.00;"-"'
    wrap = Alignment(wrap_text=True, vertical="top")
    lock = 'IF(Rules!$B$7="",9E+99,Rules!$B$3+Rules!$B$7)'

    wb = Workbook()
    # Start here ----------------------------------------------------------------------------------------------------
    ws = wb.active
    ws.title = "Start here"
    ws.column_dimensions["A"].width = 110
    lines = [("Prop Eval Tracker v" + VERSION, title),
             ("Know your drawdown left before every session. This file applies the rules YOU type; it gives no advice and promises nothing.", norm),
             ("", norm),
             ("1. Rules: copy your firm's rules into the yellow cells (start balance, target, max loss, how it moves, daily limit, consistency).", norm),
             ("2. Log: one row per trading day, top to bottom with no empty rows. Row 7 is an example: type your first day over it.", norm),
             ("3. Dashboard: drawdown left, the max-loss level, target left, the consistency check and the status (OK / CAREFUL / BREACHED / TARGET MET).", norm),
             ("4. Size: pick the contract and your stop; it shows how many contracts fit your risk (size follows the stop).", norm),
             ("", norm),
             ("Yellow cells with blue numbers are inputs. Grey cells are calculated: do not type in them.", bold),
             ("Google Sheets: File > Import > Upload this file > Replace spreadsheet. Excel: open it as is.", norm),
             ("", norm),
             ("How the max loss moves", bold),
             ("EOD trailing: the level follows your best END-OF-DAY balance (it moves at the close, up only).", norm),
             ("Intraday trailing: the level follows your best balance DURING the day (type the day's highest balance for an exact level).", norm),
             ("Static: the level never moves.", norm),
             ("Trail stops at: many firms stop the trailing level at the start balance or a set amount above it. Leave it blank if yours never stops.", norm),
             ("A breach is equity AT or BELOW the level at any moment: type the day's lowest balance to check it; without it, the end-of-day balance is used.", norm),
             ("", norm),
             ("Not affiliated with any prop firm, broker or platform. Your firm's own dashboard always decides. Futures trading involves substantial risk of loss.", small)]
    for i, (t, f) in enumerate(lines, 1):
        ws.cell(row=i, column=1, value=t).font = f
        ws.cell(row=i, column=1).alignment = Alignment(wrap_text=True)

    # Rules -----------------------------------------------------------------------------------------------------------
    r = wb.create_sheet("Rules")
    r.column_dimensions["A"].width = 44
    r.column_dimensions["B"].width = 20
    r.column_dimensions["C"].width = 80
    r["A1"] = "Your firm's rules"
    r["A1"].font = title
    r["A2"] = "Yellow cells with blue numbers are yours: copy them from your firm's rules page. The example is a 50K account, $2,000 EOD trailing max loss that stops at start + $100."
    r["A2"].font = small
    rows = [("Start balance ($)", rules["start"], money, "Account size at the start"),
            ("Profit target ($)", rules["target"], money, "Profit needed to pass"),
            ("Max loss ($)", rules["max_loss"], money, "Also called max drawdown or maximum loss limit"),
            ("How the max loss moves", rules["type"], "@", "EOD trailing, Intraday trailing or Static (pick from the list)"),
            ("Trail stops at start + ($)", rules["lock"], money, "Blank = it never stops trailing"),
            ("Daily loss limit ($)", rules["daily_limit"], money, "Blank = no daily limit"),
            ("Consistency: best day at most (% of profit)", (rules["consistency"] / 100 if rules["consistency"] not in ("", None) else ""), "0%", "Blank = no rule. Type 40% for a 40% rule"),
            ("Minimum trading days", rules["min_days"], "0", "Days with at least one trade needed before a pass")]
    for i, (lab, val, fmt, note) in enumerate(rows, 3):
        r.cell(row=i, column=1, value=lab).font = norm
        c = r.cell(row=i, column=2, value=(None if val == "" else val))
        c.font, c.fill, c.number_format = blue, input_fill, fmt
        r.cell(row=i, column=3, value=note).font = small
    dv = DataValidation(type="list", formula1='"EOD trailing,Intraday trailing,Static"', allow_blank=False)
    dv.add("B6")
    r.add_data_validation(dv)

    # Log ---------------------------------------------------------------------------------------------------------------
    lg = wb.create_sheet("Log")
    lg["A1"] = "Daily log"
    lg["A1"].font = title
    lg["A2"] = ("One row per trading day, top to bottom, no empty rows. Yellow = you type (date, net P&L after fees, and if you know them the lowest "
                "and highest balance during the day). Grey = calculated.")
    lg["A2"].font = small
    lg["A3"] = "Row 7 is an example: type your first day over it."
    lg["A3"].font = small
    heads = ["Date", "Net P&L ($)", "Lowest balance today ($)", "Highest balance today ($)", "Trades", "Note", "End balance ($)",
             "Best balance ($)", "Max-loss level in effect ($)", "Max-loss level after close ($)", "Drawdown left ($)", "Day loss ($)", "Status"]
    widths = [12, 13, 15, 15, 8, 30, 15, 15, 16, 16, 15, 12, 14]
    for j, (h, w) in enumerate(zip(heads, widths), 1):
        c = lg.cell(row=5, column=j, value=h)
        c.font, c.fill, c.border, c.alignment = bold, head_fill, line, Alignment(wrap_text=True, vertical="bottom")
        lg.column_dimensions[c.column_letter].width = w
    lg.row_dimensions[5].height = 44
    lg["A6"] = "Start"
    lg["A6"].font = bold
    lg["G6"], lg["H6"], lg["J6"], lg["K6"] = "=Rules!$B$3", "=Rules!$B$3", "=Rules!$B$3-Rules!$B$5", "=G6-J6"
    for col in "GHJK":
        lg[f"{col}6"].number_format = money
        lg[f"{col}6"].fill = calc_fill
        lg[f"{col}6"].font = norm
    for rr in range(FIRST, LAST + 1):
        p = rr - 1
        low = f'IF(C{rr}="",G{rr},MIN(G{rr},C{rr}))'
        high = f'IF(D{rr}="",G{rr},MAX(G{rr},D{rr}))'
        f = {
            "G": f'=IF(B{rr}="","",G{p}+B{rr})',
            "H": f'=IF(B{rr}="","",IF(Rules!$B$6="Intraday trailing",MAX(H{p},{high}),IF(Rules!$B$6="EOD trailing",MAX(H{p},G{rr}),H{p})))',
            "I": f'=IF(B{rr}="","",IF(Rules!$B$6="Intraday trailing",MAX(J{p},MIN(MAX(H{p},{high})-Rules!$B$5,{lock})),J{p}))',
            "J": f'=IF(B{rr}="","",IF(Rules!$B$6="Static",I{rr},MAX(I{rr},MIN(H{rr}-Rules!$B$5,{lock}))))',
            "K": f'=IF(B{rr}="","",G{rr}-J{rr})',
            "L": f'=IF(B{rr}="","",MAX(0,G{p}-{low}))',
            "M": f'=IF(B{rr}="","",IF({low}<=I{rr},"BREACHED",IF(AND(Rules!$B$8<>"",L{rr}>=Rules!$B$8),"DAILY LIMIT",IF(K{rr}<=0.25*Rules!$B$5,"CAREFUL","OK"))))',
        }
        for col, formula in f.items():
            c = lg[f"{col}{rr}"]
            c.value = formula
            c.fill, c.font = calc_fill, norm
            c.number_format = "@" if col == "M" else money
        for col in "ABCDEF":
            c = lg[f"{col}{rr}"]
            c.fill, c.font = input_fill, blue
        lg[f"A{rr}"].number_format = "yyyy-mm-dd"
        for col in "BCD":
            lg[f"{col}{rr}"].number_format = money
    import datetime as dt
    for i, d in enumerate(days):
        rr = FIRST + i
        lg[f"A{rr}"] = dt.date.fromisoformat(d["date"]) if d.get("date") else None
        lg[f"B{rr}"] = d["pnl"]
        lg[f"C{rr}"] = None if d.get("low") in ("", None) else d["low"]
        lg[f"D{rr}"] = None if d.get("high") in ("", None) else d["high"]
        lg[f"E{rr}"] = None if d.get("trades") in ("", None) else d["trades"]
        lg[f"F{rr}"] = d.get("note") or None
    status_rng = f"M{FIRST}:M{LAST}"
    for txt, color in (("BREACHED", "F4CCCC"), ("DAILY LIMIT", "FCE5CD"), ("CAREFUL", "FCE5CD"), ("OK", "D9EAD3")):
        lg.conditional_formatting.add(status_rng, CellIsRule(operator="equal", formula=[f'"{txt}"'], fill=PatternFill("solid", fgColor=color)))
    dvn = DataValidation(type="decimal", operator="between", formula1="-10000000", formula2="10000000", allow_blank=True)
    dvn.add(f"B{FIRST}:D{LAST}")
    lg.add_data_validation(dvn)
    lg.freeze_panes = "B6"

    # Dashboard ---------------------------------------------------------------------------------------------------------
    db = wb.create_sheet("Dashboard", 1)
    db.column_dimensions["A"].width = 44
    db.column_dimensions["B"].width = 34
    db["A1"] = "Where you stand"
    db["A1"].font = title
    rng = f"{FIRST}:{'B'}{LAST}"
    items = [
        ("Days logged", f"=COUNT(Log!B{FIRST}:B{LAST})", "0"),
        ("Balance ($)", f"=IF(B3=0,Rules!B3,INDEX(Log!G{FIRST}:G{LAST},B3))", money),
        ("Max-loss level ($)", f"=IF(B3=0,Rules!B3-Rules!B5,INDEX(Log!J{FIRST}:J{LAST},B3))", money),
        ("DRAWDOWN LEFT ($)", "=B4-B5", money),
        ("Profit so far ($)", "=B4-Rules!B3", money),
        ("Profit target left ($)", "=MAX(0,Rules!B4-B7)", money),
        ("Best day ($)", f"=MAX(0,MAX(Log!B{FIRST}:B{LAST}))", money),
        ("Best day share of profit", '=IF(B7>0,B9/B7,"")', "0%"),
        ("Consistency rule met?", '=IF(Rules!B9="","No rule",IF(B7<=0,"Not yet",IF(B9/B7<=Rules!B9,"Yes","No")))', "@"),
        ("More profit needed for the consistency rule ($)", '=IF(B11="No",B9/Rules!B9-B7,"")', money),
        ("Max-loss level reached?", f'=IF(COUNTIF(Log!M{FIRST}:M{LAST},"BREACHED")>0,"Yes","No")', "@"),
        ("Minimum days met?", '=IF(B3>=Rules!B10,"Yes","No")', "@"),
        ("STATUS", '=IF(B13="Yes","BREACHED",IF(AND(Rules!B4>0,B7>=Rules!B4,B14="Yes",OR(B11="No rule",B11="Yes")),"TARGET MET",IF(B6<=0.25*Rules!B5,"CAREFUL","OK")))', "@"),
    ]
    del rng
    for i, (lab, formula, fmt) in enumerate(items, 3):
        a = db.cell(row=i, column=1, value=lab)
        a.font = bold if lab.isupper() or lab.startswith("DRAWDOWN") else norm
        c = db.cell(row=i, column=2, value=formula)
        c.number_format, c.fill = fmt, calc_fill
        c.font = Font(name=F, size=14, bold=True) if lab in ("DRAWDOWN LEFT ($)", "STATUS") else norm
        a.border = c.border = line
    for txt, color in (("BREACHED", "F4CCCC"), ("CAREFUL", "FCE5CD"), ("OK", "D9EAD3"), ("TARGET MET", "CFE2F3")):
        db.conditional_formatting.add("B15", CellIsRule(operator="equal", formula=[f'"{txt}"'], fill=PatternFill("solid", fgColor=color)))
    db["A17"] = "Your firm's dashboard has the final word. This sheet only applies the rules you typed on the Rules tab."
    db["A17"].font = small

    # Size -----------------------------------------------------------------------------------------------------------------
    sz = wb.create_sheet("Size")
    sz.column_dimensions["A"].width = 44
    sz.column_dimensions["B"].width = 28
    sz["A1"] = "Position size: size follows the stop"
    sz["A1"].font = title
    srows = [("Contract", "MNQ (Micro Nasdaq-100)", "@", True), ("$ per point", "=INDEX(Lists!$B$2:$B$13,MATCH(B3,Lists!$A$2:$A$13,0))", money, False),
             ("Stop (points)", 20, "0.00", True), ("Risk per trade (% of drawdown left)", 0.10, "0%", True),
             ("Or a fixed risk ($, blank = use the %)", None, money, True), ("Costs per contract, round trip ($)", 1.0, money, True),
             ("Drawdown left ($)", "=Dashboard!B6", money, False), ("", None, "@", False),
             ("Risk for this trade ($)", '=IF(B7<>"",B7,MAX(0,B9)*B6)', money, False), ("Risk per contract ($)", "=B5*B4+B8", money, False),
             ("CONTRACTS", "=IF(B12>0,INT(B11/B12+0.000000001),0)", "0", False), ("Loss if stopped ($)", "=B13*B12", money, False),
             ("Losses in a row before the max-loss level", '=IF(B14>0,INT(B9/B14+0.000000001),"")', "0", False)]
    for i, (lab, val, fmt, is_input) in enumerate(srows, 3):
        if not lab:
            continue
        sz.cell(row=i, column=1, value=lab).font = bold if lab.isupper() else norm
        c = sz.cell(row=i, column=2, value=val)
        c.number_format = fmt
        c.font, c.fill = (blue, input_fill) if is_input else (Font(name=F, size=14, bold=True) if lab.isupper() else norm, calc_fill)
    dvi = DataValidation(type="list", formula1="=Lists!$A$2:$A$13", allow_blank=False)
    dvi.add("B3")
    sz.add_data_validation(dvi)
    sz["A17"] = "A wider stop means fewer contracts. Never widen a stop to fit a size. 0 contracts = the stop is too wide for this risk."
    sz["A17"].font = small

    # Lists ----------------------------------------------------------------------------------------------------------------
    ls = wb.create_sheet("Lists")
    ls["A1"], ls["B1"] = "Contract", "$ per point"
    ls["A1"].font = ls["B1"].font = bold
    for i, (k, v) in enumerate(M.INSTRUMENTS.items(), 2):
        ls.cell(row=i, column=1, value=k).font = norm
        ls.cell(row=i, column=2, value=v).number_format = money
    ls["A15"] = "Source: the exchanges' contract specifications ($ per 1.00 index point; gold and crude per $1.00 move)."
    ls["A15"].font = small
    ls.column_dimensions["A"].width = 30
    ls.column_dimensions["B"].width = 14
    for w in wb.worksheets:
        w.sheet_view.zoomScale = 110
    wb.active = 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path


def soffice_values(xlsx: str) -> dict:
    """{sheet: rows} as LibreOffice computes them (headless CSV export of every sheet). {} without LibreOffice."""
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return {}
    tmp = tempfile.mkdtemp(prefix="mm_lo_")
    try:
        subprocess.run([exe, f"-env:UserInstallation=file://{tmp}/profile", "--headless", "--convert-to",
                        "csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,false,false,false,-1", "--outdir", tmp, xlsx],
                       capture_output=True, timeout=180)
        out = {}
        base = os.path.splitext(os.path.basename(xlsx))[0]
        for p in glob.glob(os.path.join(tmp, base + "-*.csv")):
            with open(p, encoding="utf-8") as fh:
                out[os.path.basename(p)[len(base) + 1:-4]] = list(csv.reader(fh))
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _num(s):
    s = (s or "").replace("$", "").replace(",", "").strip()
    if s in ("", "-"):
        return 0.0 if s == "-" else None
    try:
        return float(s)
    except ValueError:
        return s


SCENARIOS = [
    ("EOD trailing, trail stops at start + 100, then a breach",
     {"start": 50000, "target": 3000, "max_loss": 2000, "type": "EOD trailing", "lock": 100, "daily_limit": 800, "consistency": 40, "min_days": 3},
     [{"date": "2026-01-05", "pnl": 900, "low": 49700}, {"date": "2026-01-06", "pnl": 1300, "high": 52400}, {"date": "2026-01-07", "pnl": -650, "low": 51300},
      {"date": "2026-01-08", "pnl": 600}, {"date": "2026-01-09", "pnl": -2100, "low": 49900}]),
    ("Intraday trailing, no lock, target met",
     {"start": 100000, "target": 6000, "max_loss": 3000, "type": "Intraday trailing", "lock": "", "daily_limit": "", "consistency": 50, "min_days": 2},
     [{"date": "2026-02-02", "pnl": 2500, "high": 103200}, {"date": "2026-02-03", "pnl": -400, "low": 101200}, {"date": "2026-02-04", "pnl": 2200},
      {"date": "2026-02-05", "pnl": 1900, "high": 106500, "low": 104000}]),
    ("Static with a daily limit day",
     {"start": 25000, "target": 1500, "max_loss": 1000, "type": "Static", "lock": "", "daily_limit": 500, "consistency": "", "min_days": 1},
     [{"date": "2026-03-02", "pnl": -520, "low": 24400}, {"date": "2026-03-03", "pnl": 300}, {"date": "2026-03-04", "pnl": 200, "low": 24100}]),
]


def verify(log=print) -> list:
    """Each scenario: build a copy of the workbook, let LibreOffice compute it, compare with eval_math. Returns problems ([] = equal)."""
    if not (shutil.which("soffice") or shutil.which("libreoffice")):
        log("verify skipped: LibreOffice (soffice) is not installed")
        return []
    probs = []
    tmp = tempfile.mkdtemp(prefix="mm_ver_")
    try:
        for name, rules, days in SCENARIOS:
            p = build_xlsx(os.path.join(tmp, "v.xlsx"), rules, days)
            vals = soffice_values(p)
            py_rules = dict(rules, consistency=(rules["consistency"] / 100 if rules["consistency"] != "" else ""))
            exp = M.compute(py_rules, days)
            lgv = vals.get("Log", [])
            for i, row in enumerate(exp["rows"]):
                got = lgv[FIRST - 1 + i]
                pairs = {"end": _num(got[6]), "floor_in_effect": _num(got[8]), "floor_after": _num(got[9]), "dd_left": _num(got[10]),
                         "day_loss": _num(got[11]), "status": got[12]}
                for k, v in pairs.items():
                    e = row[k]
                    if (isinstance(e, float) and (not isinstance(v, float) or abs(v - e) > 0.005)) or (isinstance(e, str) and v != e):
                        probs.append(f"{name}: day {i + 1} {k}: sheet {v!r} vs math {e!r}")
            dbv = {r[0]: r[1] for r in vals.get("Dashboard", []) if len(r) > 1 and r[0]}
            if dbv.get("STATUS") != exp["status"] or abs((_num(dbv.get("DRAWDOWN LEFT ($)")) or 0) - exp["dd_left"]) > 0.005:
                probs.append(f"{name}: dashboard {dbv.get('STATUS')} / {dbv.get('DRAWDOWN LEFT ($)')} vs math {exp['status']} / {exp['dd_left']}")
            log(f"verify: {name}: {'equal' if not any(x.startswith(name) for x in probs) else 'DIFFERENT'} (status {exp['status']}, drawdown left {exp['dd_left']})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return probs


# ------------------------------------------------------------------------------------------------ text files
LICENSE = f"""Prop Eval Tracker v{VERSION}: licence

You may use these files for your own trading records, on any number of your own devices.
You may not resell, share, upload or give away the files or edited copies of them.

The tracker applies the rules you type. It is not financial advice, does not predict or promise any result, and is not
affiliated with, endorsed by or connected to any prop firm, broker or trading platform. Your firm's official rules and
dashboard always take precedence. Futures trading involves substantial risk of loss and is not suitable for everyone.

The files are provided as is, without warranty of any kind. If something does not work, message the seller and we will
help or refund you within 14 days of purchase.
"""

README = f"""PROP EVAL TRACKER v{VERSION}: quick start

1. Open Prop_Eval_Tracker.xlsx in Excel, or in Google Sheets (File > Import > Upload > Replace spreadsheet).
2. Rules tab: type your firm's rules in the yellow cells.
3. Log tab: one row per trading day (date, net P&L after fees; lowest and highest balance if you know them).
4. Dashboard tab: drawdown left, max-loss level, target left, consistency check, status.
5. Size tab: contracts that fit your risk for a given stop.

Prefer a page? Open prop_eval_tracker.html in Chrome, Edge, Firefox or Safari on your computer. It works offline and keeps
your data in that browser only (use "Download backup" now and then).

How_to_use.pdf explains every field. Not financial advice. Futures trading involves substantial risk of loss.
"""

HOWTO = """<!doctype html><html><head><meta charset="utf-8"><style>
@page{size:Letter;margin:16mm 16mm}
body{font-family:'Inter',Arial,sans-serif;color:#1d1a16;font-size:11pt;line-height:1.45}
h1{font-family:'Iowan Old Style','Palatino Linotype',Caladea,Georgia,serif;font-size:24pt;margin:0 0 4pt}
h2{font-family:'Iowan Old Style','Palatino Linotype',Caladea,Georgia,serif;font-size:14pt;border-bottom:2px solid #c8a24a;padding-bottom:3pt;margin:14pt 0 6pt}
.sub{color:#5a5145;margin:0 0 10pt}table{border-collapse:collapse;width:100%;font-size:10pt}td,th{border-bottom:1px solid #ddd5c6;padding:4pt 6pt;text-align:left}
th{background:#f1ece2}.box{background:#f6f2ea;border-radius:8pt;padding:8pt 10pt;margin:8pt 0}.small{color:#6b6256;font-size:9pt}ol{padding-left:16pt}
</style></head><body>
<h1>Prop Eval Tracker</h1><p class="sub">How to use it in 5 minutes. Version """ + VERSION + """.</p>
<h2>1. Type your firm's rules</h2>
<p>Open the <b>Rules</b> tab (or the Rules card in the web page) and copy these from your firm's rules page: start balance, profit target,
max loss, how the max loss moves, where the trail stops, the daily loss limit, the consistency rule and the minimum trading days.
Leave a cell blank when your firm has no such rule.</p>
<table><tr><th>How the max loss moves</th><th>What it means</th></tr>
<tr><td>EOD trailing</td><td>The max-loss level follows your best end-of-day balance. It moves once a day, at the close, and only up.</td></tr>
<tr><td>Intraday trailing</td><td>The level follows your best balance during the day. Type the day's highest balance for an exact level.</td></tr>
<tr><td>Static</td><td>The level never moves: start balance minus the max loss.</td></tr>
<tr><td>Trail stops at</td><td>Many firms stop the trailing level at the start balance or a set amount above it. Blank = it never stops.</td></tr></table>
<div class="box"><b>Example</b> (made-up numbers): a 50,000 account with a 2,000 EOD trailing max loss starts with the level at 48,000.
After a day that closes at 50,600 the level moves to 48,600. If the trail stops at start + 100, the level never goes above 50,100.</div>
<h2>2. Log each trading day</h2>
<p>One row per day, top to bottom, no empty rows: the date and the day's <b>net P&amp;L after fees</b>. If you know them, add the lowest
and highest balance during the day: a breach is equity <b>at or below</b> the level at any moment, so the low matters.</p>
<h2>3. Read the dashboard</h2>
<ol><li><b>Drawdown left</b>: balance minus the max-loss level. The number to know before every session.</li>
<li><b>Status</b>: OK, CAREFUL (less than a quarter of the max loss left), DAILY LIMIT (that day reached your daily loss limit),
BREACHED (the level was reached) or TARGET MET (target, minimum days and consistency all met).</li>
<li><b>Consistency</b>: your best day as a share of total profit, and how much more profit the rule needs.</li></ol>
<h2>4. Size the next trade</h2>
<p>Pick the contract, type your stop in points and your risk (a share of drawdown left, or a fixed amount) and the costs per contract.
Contracts = risk / (stop x dollars per point + costs), rounded down. A wider stop means fewer contracts.</p>
<h2>5. Keep it safe</h2>
<p>The web page saves to your browser only. Use <b>Download backup</b> now and then, and <b>Restore a backup</b> on another computer.
The spreadsheet saves wherever you keep it.</p>
<p class="small">This tracker applies the rules you type. It is not financial advice, predicts nothing, and is not affiliated with any prop
firm, broker or platform. Your firm's official dashboard always decides. Futures trading involves substantial risk of loss and is not
suitable for everyone.</p></body></html>"""


def listing_md(price: float) -> str:
    L = [f"# Listing: {LISTING['title']}", "", f"**Price:** ${price} (one-time). **Version:** {VERSION}.", "", f"**Short line:** {LISTING['short']}", "",
         "## Description (paste as is)", "", "```"] + LISTING["description"] + ["```", "", "## Etsy tags (13, each <= 20 characters)", "",
                                                                                   ", ".join(LISTING["tags_etsy"]), "", "## FAQ", ""]
    L += [f"- **{q}** {a}" for q, a in LISTING["faq"]]
    L += ["", "## Files in the zip", ""] + [f"- {f}" for f in LISTING["files"]]
    L += ["", "## Images", ""] + [f"- {f}" for f in LISTING["images"]]
    L += ["", f"## What you keep from one ${price} sale (estimates; card fees assumed 2.9% + $0.30)", "", "| Platform | Fees | You keep |", "|---|---|---|"]
    net = fees(price)
    L += [f"| {k} | {v['fee']} | ${net[k]:.2f} |" for k, v in LISTING["platforms"].items()]
    L += ["", "## Rules for this listing", "",
          "- Never name a prop firm in the title, tags or pictures; never show results, profits or payouts; no 'pass your eval' promises.",
          "- Etsy: choose 'I did' (made by a seller) and 'a finished product'; the description says AI coding tools helped.",
          "- Gumroad reviews trading-related products more closely: keep the education-only wording and the risk line.", ""]
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------ images + PDF (Chromium)
def _browser(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))


DEMO_DAYS = [{"date": "2026-11-16", "pnl": 420, "low": 49850}, {"date": "2026-11-17", "pnl": -180}, {"date": "2026-11-18", "pnl": 610, "low": 50120},
             {"date": "2026-11-19", "pnl": 260}, {"date": "2026-11-20", "pnl": -320, "low": 50600}, {"date": "2026-11-23", "pnl": 540}]


def build_media(log=print) -> list:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        log("no PDF or images: playwright is not installed")
        return []
    done = []
    with sync_playwright() as pw:
        br = _browser(pw)
        pg = br.new_page(viewport={"width": 1000, "height": 900})
        pg.set_content(HOWTO)
        pg.pdf(path=PDF, format="Letter", print_background=True)
        done.append(PDF)
        state = {"rules": EXAMPLE_RULES, "days": DEMO_DAYS, "size": {"inst": "MNQ (Micro Nasdaq-100)", "stop": 20, "pct": 10, "fixed": "", "cost": 1}}
        app = open(APP, encoding="utf-8").read()
        seed = "<script>try{localStorage.setItem('propEvalTracker.v1'," + json.dumps(json.dumps(state)) + ")}catch(e){}</script>"
        pg2 = br.new_page(viewport={"width": 1000, "height": 1500}, device_scale_factor=1)
        pg2.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=app.replace("<head>", "<head>" + seed, 1)))
        pg2.goto("http://tracker.local/")
        pg2.wait_for_timeout(300)
        shot = os.path.join(PROD, "app_screenshot.jpg")
        pg2.screenshot(path=shot, type="jpeg", quality=80, full_page=False)
        done.append(shot)
        top = pg2.screenshot(type="jpeg", quality=85, clip={"x": 0, "y": 0, "width": 1000, "height": 600})
        b64 = base64.b64encode(top).decode()
        for name, w, h in (("cover.jpg", 1280, 720), ("cover_square.jpg", 2000, 2000)):
            pg3 = br.new_page(viewport={"width": w, "height": h})
            pg3.set_content(cover_html(w, h, b64))
            pg3.wait_for_timeout(200)
            p = os.path.join(PROD, name)
            pg3.screenshot(path=p, type="jpeg", quality=80)
            done.append(p)
        br.close()
    return done


def cover_html(w: int, h: int, shot_b64: str) -> str:
    square = w == h
    k = w / 1280
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:{w}px;height:{h}px;background:#14110e;overflow:hidden}}
body{{font-family:-apple-system,'Segoe UI',Inter,sans-serif;color:#f3ece0;display:flex;{'flex-direction:column;' if square else ''}
padding:{int(56 * k)}px;gap:{int(40 * k)}px;align-items:{'stretch' if square else 'center'}}}
.txt{{flex:{'0 0 auto' if square else '0 0 46%'}}}
h1{{font-family:'Iowan Old Style','Palatino Linotype',Caladea,Georgia,serif;font-size:{int(64 * k * (1.05 if square else 1))}px;line-height:1.05;color:#f3ece0}}
.rule{{width:{int(110 * k)}px;height:{max(4, int(7 * k))}px;background:#c8a24a;border-radius:4px;margin:{int(22 * k)}px 0}}
p{{font-size:{int(26 * k)}px;color:#cfc4b2;line-height:1.35}}
ul{{list-style:none;margin-top:{int(20 * k)}px}}li{{font-size:{int(25 * k)}px;margin:{int(10 * k)}px 0;color:#f3ece0}}
li:before{{content:"\\2713";color:#a9b57a;margin-right:{int(12 * k)}px;font-weight:700}}
.shot{{flex:1;display:flex;align-items:center;justify-content:center;min-height:0;height:{(h - int(112 * k)) if not square else int(h * 0.52)}px}}
.shot img{{max-width:100%;max-height:100%;object-fit:contain;border-radius:{int(16 * k)}px;border:2px solid #3a3228;box-shadow:0 {int(20 * k)}px {int(50 * k)}px rgba(0,0,0,.55)}}
.foot{{position:absolute;bottom:{int(18 * k)}px;left:{int(56 * k)}px;font-size:{int(17 * k)}px;color:#a89c88}}
</style></head><body><div class="txt"><h1>Prop Eval Tracker</h1><div class="rule"></div>
<p>Know your drawdown left before every session.</p>
<ul><li>Excel + Google Sheets</li><li>Offline web app</li><li>EOD, intraday or static max loss</li><li>Daily limit, consistency, size helper</li></ul></div>
<div class="shot"><img src="data:image/jpeg;base64,{shot_b64}"></div>
<div class="foot">Tracks the rules you type. No signals, no promises. Not affiliated with any prop firm.</div></body></html>"""


def write_texts(price: float) -> list:
    files = {os.path.join(PROD, "LICENSE.txt"): LICENSE, os.path.join(PROD, "README.txt"): README, os.path.join(PROD, "listing.md"): listing_md(price)}
    lst = dict(LISTING, net_per_sale_usd=fees(price))
    files[os.path.join(PROD, "listing.json")] = json.dumps(lst, indent=1) + "\n"
    for p, t in files.items():
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(t)
    return list(files)


def make_zip() -> str:
    os.makedirs(OUT, exist_ok=True)
    z = os.path.join(OUT, f"prop_eval_tracker_v{VERSION}.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in LISTING["files"]:
            zi = zipfile.ZipInfo(name, date_time=(2026, 11, 14, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(PROD, name), "rb") as fh:
                zf.writestr(zi, fh.read())
    return z


def cache_values(path: str = XLSX) -> str:
    """openpyxl writes formulas without results, so previewers (Etsy/Gumroad file preview, Quick Look) show empty cells until Excel or
    Sheets opens the file. The xlsx skill's recalc.py (LibreOffice) stores the results while keeping our formatting: set XLSX_RECALC to
    its path, or it is looked up in the Claude skills folder. Excel and Google Sheets recompute on open either way."""
    cands = [os.environ.get("XLSX_RECALC", "")] + sorted(glob.glob(os.path.expanduser("~/.claude/skills/**/xlsx/scripts/recalc.py"), recursive=True))
    script = next((c for c in cands if c and os.path.exists(c)), None)
    if not script:
        return "note: results not cached (no recalc script); Excel and Google Sheets compute them on open"
    r = subprocess.run([sys.executable, script, path, "120"], capture_output=True, text=True, timeout=300)
    try:
        res = json.loads(r.stdout)
    except ValueError:
        return f"note: recalc did not run ({(r.stderr or r.stdout)[:200]})"
    if res.get("status") != "success":
        raise SystemExit(f"the spreadsheet has formula errors: {res}")
    return f"recalculated: {res['total_formulas']} formulas, {res['total_errors']} errors"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.products.build_eval_tracker")
    ap.add_argument("--zip", action="store_true", help="also write the upload zip to money_machines/out/products/")
    ap.add_argument("--verify", action="store_true", help="LibreOffice recomputes 3 scenarios; they must equal eval_math.py")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args(argv)
    if a.verify:
        probs = verify()
        print("\n".join(probs) if probs else "spreadsheet = eval_math in every scenario")
        return 1 if probs else 0
    price = LISTING["price_usd"]
    print(build_xlsx())
    print(cache_values())
    for p in write_texts(price):
        print(p)
    if not a.no_images:
        for p in build_media():
            print(p)
    if a.zip:
        print(make_zip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
