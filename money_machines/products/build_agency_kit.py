"""Build the FIRST CLIENTS AGENCY STARTER KIT (team D2, 2026-11-14): 7 editable .docx documents (outreach scripts, discovery call,
proposal, service agreement marked NOT LEGAL ADVICE, onboarding, honest reviews and referrals, service checklists), 2 spreadsheets
(tracker with pricing, dashboard and invoice log; quote + invoice), the 30-day plan PDF, licence and readme.

    python -m money_machines.products.build_agency_kit --zip     # the owner: pack the committed files (plain Python)
                                                                 #   -> money_machines/out/products/first_clients_agency_kit_v1.0.zip
    python -m money_machines.products.build_agency_kit           # rebuild (python-docx, openpyxl, LibreOffice for cached values and page
                                                                 #   pictures, Chromium for the PDF and covers: run under the browser lock)

Content: agency_kit_data.py (docgen blocks). Folds in the catalogue's planned "Google profile checklist" and "review request kit" as
documents 06 and 07 (see catalog.json "folded").
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import shutil
import subprocess
import sys
import tempfile

from money_machines.products import agency_kit_data as A
from money_machines.products import docgen as G
from money_machines.products import kit as K

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.join(HERE, "agency_kit")
BUYER, SHOP = os.path.join(PROD, "buyer"), os.path.join(PROD, "shop")
VERSION = "1.0"
TOP = "First-Clients-Agency-Starter-Kit"
ZIP = f"first_clients_agency_kit_v{VERSION}.zip"
TRACKER = os.path.join(BUYER, "Agency_Tracker.xlsx")
INVOICE = os.path.join(BUYER, "Invoice_Template.xlsx")
STATUSES = ["To contact", "Contacted", "Replied", "Call booked", "Proposal sent", "Won", "Lost", "Not now"]
CHANNELS = ["Walk-in", "Phone", "Email", "Message", "Referral", "Event"]
P_FIRST, P_LAST = 5, 204          # Prospects rows
I_FIRST, I_LAST = 5, 104          # Invoice log rows


# ------------------------------------------------------------------------------------------------ spreadsheets
def _styles():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    F = "Arial"
    return {"title": Font(name=F, size=16, bold=True, color="1D1A16"), "bold": Font(name=F, size=11, bold=True), "norm": Font(name=F, size=11),
            "small": Font(name=F, size=10, color="5F574B"), "blue": Font(name=F, size=11, color="0000FF"), "big": Font(name=F, size=14, bold=True),
            "white": Font(name=F, size=11, bold=True, color="FFFFFF"),
            "head": PatternFill("solid", fgColor="EEEAE2"), "calc": PatternFill("solid", fgColor="F4F4F4"), "input": PatternFill("solid", fgColor="FFF2CC"),
            "accent": PatternFill("solid", fgColor="8A5A1C"), "line": Border(bottom=Side(style="thin", color="BBBBBB")),
            "box": Border(*(Side(style="thin", color="CFC6B6"),) * 4), "wrap": Alignment(wrap_text=True, vertical="top"), "center": Alignment(horizontal="center")}


MONEY = '$#,##0.00;-$#,##0.00;"-"'


def build_tracker(path: str = TRACKER) -> str:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.worksheet.datavalidation import DataValidation
    S = _styles()
    wb = Workbook()
    ws = wb.active
    ws.title = "Start here"
    ws.column_dimensions["A"].width = 112
    lines = [("Agency Tracker v" + VERSION, S["title"]),
             ("Your prospects, follow-ups, numbers, prices and invoices in one file. Yellow cells with blue text are yours to type in; grey cells are calculated.", S["norm"]),
             ("", S["norm"]),
             ("1. Prospects: one row per business. Set the Status from the list and a Follow-up date; the last column says DUE when it is time.", S["norm"]),
             ("2. Dashboard: counts by status, follow-ups due today, contacts this week. These are your own numbers, not a forecast.", S["norm"]),
             ("3. Pricing: your hourly rate and the hours per task give a suggested price for each package and the monthly plan.", S["norm"]),
             ("4. Invoices: log every invoice you send; the Status column says Paid, Due or Overdue.", S["norm"]),
             ("", S["norm"]),
             ("The rows that start with 'Example' are there to show how it works: type over them or delete them.", S["bold"]),
             ("Works in the usual spreadsheet apps on a computer, and in free online spreadsheets (import the file).", S["norm"]),
             ("", S["norm"]),
             ("Keep logins and passwords out of this file. Use a password manager.", S["small"]),
             ("Contact only businesses, by hand, and respect every 'no' (see 00_Start_Here.pdf for the email, call and text rules).", S["small"])]
    for i, (t, f) in enumerate(lines, 1):
        c = ws.cell(row=i, column=1, value=t)
        c.font, c.alignment = f, S["wrap"]

    # Prospects ---------------------------------------------------------------------------------------------------
    pr = wb.create_sheet("Prospects")
    pr["A1"], pr["A1"].font = "Prospects", S["title"]
    pr["A2"], pr["A2"].font = "One row per business, top to bottom. Status and channel come from the lists. 'DUE' appears when the follow-up date has come.", S["small"]
    heads = ["Business", "Type", "Town", "Contact name", "Phone", "Email", "Where you found it", "First contact", "Channel", "Status", "Next step",
             "Follow-up date", "Notes", "Follow up?"]
    widths = [26, 14, 13, 16, 15, 24, 20, 13, 11, 14, 26, 13, 30, 11]
    for j, (h, w) in enumerate(zip(heads, widths), 1):
        c = pr.cell(row=4, column=j, value=h)
        c.font, c.fill, c.border = S["bold"], S["head"], S["line"]
        pr.column_dimensions[c.column_letter].width = w
    examples = [["Example: Riverton Plumbing", "Plumber", "Riverton", "Sam", "(555) 010-0142", "", "Van sign + map listing", dt.date(2026, 11, 16), "Walk-in",
                 "Call booked", "Discovery call Thu 10:00", dt.date(2026, 11, 19), "No website; hours on the listing are wrong"],
                ["Example: Corner Table Cafe", "Cafe", "Oak Hill", "Ana", "(555) 010-0118", "", "Walked past", dt.date(2026, 11, 17), "Walk-in",
                 "Contacted", "Follow up by email", dt.date(2026, 11, 20), "Site is hard to read on a phone"],
                ["Example: Old Town Barbers", "Barber", "Fairview", "Marcus", "(555) 010-0190", "", "Friend's referral", dt.date(2026, 11, 18), "Referral",
                 "Proposal sent", "Check in Monday", dt.date(2026, 11, 23), "Wants online booking link"]]
    for rr in range(P_FIRST, P_LAST + 1):
        for j in range(1, 14):
            c = pr.cell(row=rr, column=j)
            c.fill, c.font = S["input"], S["blue"]
        pr.cell(row=rr, column=8).number_format = "yyyy-mm-dd"
        pr.cell(row=rr, column=12).number_format = "yyyy-mm-dd"
        f = pr.cell(row=rr, column=14, value=f'=IF(AND(L{rr}<>"",L{rr}<=TODAY(),J{rr}<>"Won",J{rr}<>"Lost",J{rr}<>"Not now"),"DUE","")')
        f.fill, f.font = S["calc"], S["bold"]
    for i, row in enumerate(examples):
        for j, v in enumerate(row, 1):
            pr.cell(row=P_FIRST + i, column=j, value=v)
    dvs = DataValidation(type="list", formula1=f"=Lists!$A$2:$A${1 + len(STATUSES)}", allow_blank=True)
    dvs.add(f"J{P_FIRST}:J{P_LAST}")
    dvc = DataValidation(type="list", formula1=f"=Lists!$B$2:$B${1 + len(CHANNELS)}", allow_blank=True)
    dvc.add(f"I{P_FIRST}:I{P_LAST}")
    dvd = DataValidation(type="date", operator="greaterThan", formula1="36526", allow_blank=True)
    dvd.add(f"H{P_FIRST}:H{P_LAST}")
    dvd.add(f"L{P_FIRST}:L{P_LAST}")
    for dv in (dvs, dvc, dvd):
        pr.add_data_validation(dv)
    pr.conditional_formatting.add(f"N{P_FIRST}:N{P_LAST}", CellIsRule(operator="equal", formula=['"DUE"'], fill=__import__("openpyxl").styles.PatternFill("solid", fgColor="FCE5CD")))
    pr.freeze_panes = "B5"
    pr.auto_filter.ref = f"A4:N{P_LAST}"

    # Dashboard ---------------------------------------------------------------------------------------------------
    db = wb.create_sheet("Dashboard", 1)
    db.column_dimensions["A"].width = 46
    db.column_dimensions["B"].width = 16
    db["A1"], db["A1"].font = "Your numbers", S["title"]
    db["A2"], db["A2"].font = "Counted from the Prospects and Invoices tabs. They show where you get stuck; they are not a forecast.", S["small"]
    rng = f"Prospects!$J${P_FIRST}:$J${P_LAST}"
    rows = [("Businesses on your list", f'=COUNTA(Prospects!$A${P_FIRST}:$A${P_LAST})', "0")]
    rows += [(f"Status: {s}", f'=COUNTIF({rng},"{s}")', "0") for s in STATUSES]
    rows += [("Reached so far (a status other than 'To contact')", f'=COUNTA({rng})-COUNTIF({rng},"To contact")', "0"),
             ("Follow-ups due today or earlier", f'=COUNTIF(Prospects!$N${P_FIRST}:$N${P_LAST},"DUE")', "0"),
             ("First contacts this week (Mon-Sun)", f'=COUNTIFS(Prospects!$H${P_FIRST}:$H${P_LAST},">="&(TODAY()-WEEKDAY(TODAY(),2)+1),Prospects!$H${P_FIRST}:$H${P_LAST},"<="&(TODAY()-WEEKDAY(TODAY(),2)+7))', "0"),
             ("Proposals that became clients (won / proposals sent, won or lost)", f'=IF((B8+B9+B10)=0,"",B9/(B8+B9+B10))', "0%"),
             ("Invoiced (total)", f"=SUM(Invoices!$E${I_FIRST}:$E${I_LAST})", MONEY),
             ("Paid", f'=SUMIF(Invoices!$G${I_FIRST}:$G${I_LAST},"Paid",Invoices!$E${I_FIRST}:$E${I_LAST})', MONEY),
             ("Waiting to be paid", f'=SUMIF(Invoices!$G${I_FIRST}:$G${I_LAST},"Due",Invoices!$E${I_FIRST}:$E${I_LAST})', MONEY),
             ("Overdue", f'=SUMIF(Invoices!$G${I_FIRST}:$G${I_LAST},"Overdue",Invoices!$E${I_FIRST}:$E${I_LAST})', MONEY)]
    for i, (lab, formula, fmt) in enumerate(rows, 3):
        a = db.cell(row=i, column=1, value=lab)
        c = db.cell(row=i, column=2, value=formula)
        a.font, a.border, c.border = S["norm"], S["line"], S["line"]
        c.number_format, c.fill = fmt, S["calc"]
        c.font = S["big"] if lab.startswith(("Follow-ups", "Overdue")) else S["norm"]

    # Pricing ----------------------------------------------------------------------------------------------------------
    pc = wb.create_sheet("Pricing")
    for col, w in zip("ABCDE", (40, 14, 14, 14, 50)):
        pc.column_dimensions[col].width = w
    pc["A1"], pc["A1"].font = "Package prices: hours x your rate + costs + a buffer", S["title"]
    pc["A2"], pc["A2"].font = "Type your rate and your honest hour estimates. The suggested price is rounded to the nearest $10; you decide the final price.", S["small"]
    inputs = [("Your hourly rate ($)", 50, MONEY), ("Buffer for surprises (%)", 0.15, "0%")]
    for i, (lab, v, fmt) in enumerate(inputs, 4):
        pc.cell(row=i, column=1, value=lab).font = S["bold"]
        c = pc.cell(row=i, column=2, value=v)
        c.number_format, c.fill, c.font = fmt, S["input"], S["blue"]
    for j, h in enumerate(["Task", "Starter (h)", "Standard (h)", "Plus (h)", "Note"], 1):
        c = pc.cell(row=7, column=j, value=h)
        c.font, c.fill, c.border = S["bold"], S["head"], S["line"]
    tasks = [("Discovery call and planning", 1, 1.5, 2, "The call, notes, the proposal"), ("Design", 2, 3, 4, "Layout, colours, fonts"),
             ("Building the pages", 2, 5, 6, "Including phone checks"), ("Content and photos", 1, 2, 5, "Plus includes help writing the text"),
             ("Local listing set-up", 0, 1.5, 1.5, "Owner verifies; you help with the details"), ("Changes (revision rounds)", 1, 2, 3, "As in the proposal"),
             ("Launch and handover", 1, 1, 1.5, "Final check, handover email"), ("Support after launch", 0.5, 1, 2, "7, 14 or 30 days")]
    r0 = 8
    for i, (t, a, b, c_, note) in enumerate(tasks):
        rr = r0 + i
        pc.cell(row=rr, column=1, value=t).font = S["norm"]
        for j, v in enumerate((a, b, c_), 2):
            cc = pc.cell(row=rr, column=j, value=v)
            cc.fill, cc.font, cc.number_format = S["input"], S["blue"], "0.0"
        pc.cell(row=rr, column=5, value=note).font = S["small"]
    last = r0 + len(tasks) - 1
    calc_rows = [("Total hours", [f"=SUM({c}{r0}:{c}{last})" for c in "BCD"], "0.0", False),
                 ("Costs for this package ($): tools, photos, fees", [0, 0, 0], MONEY, True),
                 ("SUGGESTED PRICE ($)", [f"=ROUND(({c}{last + 1}*$B$4+{c}{last + 2})*(1+$B$5),-1)" for c in "BCD"], MONEY, False),
                 ("Effective hourly rate if the hours are right ($)", [f'=IF({c}{last + 1}=0,"",{c}{last + 3}/{c}{last + 1})' for c in "BCD"], MONEY, False)]
    for i, (lab, vals, fmt, is_input) in enumerate(calc_rows, last + 1):
        pc.cell(row=i, column=1, value=lab).font = S["bold"]
        for j, v in enumerate(vals, 2):
            cc = pc.cell(row=i, column=j, value=v)
            cc.number_format = fmt
            cc.fill, cc.font = (S["input"], S["blue"]) if is_input else (S["calc"], S["big"] if lab.isupper() else S["norm"])
    m0 = last + 7
    pc.cell(row=m0, column=1, value="Monthly care plan").font = S["big"]
    mrows = [("Hours a month you include", 1, "0.0", True), ("Tool or hosting costs you pay each month ($)", 0, MONEY, True),
             ("SUGGESTED MONTHLY PRICE ($)", f"=ROUND((B{m0 + 1}*$B$4+B{m0 + 2})*(1+$B$5),0)", MONEY, False)]
    for i, (lab, v, fmt, is_input) in enumerate(mrows, m0 + 1):
        pc.cell(row=i, column=1, value=lab).font = S["bold"] if lab.isupper() else S["norm"]
        cc = pc.cell(row=i, column=2, value=v)
        cc.number_format = fmt
        cc.fill, cc.font = (S["input"], S["blue"]) if is_input else (S["calc"], S["big"])
    pc.cell(row=m0 + 5, column=1, value="Prices are yours to set. Check what similar services cost in your area, and raise prices as you gain experience and reviews.").font = S["small"]

    # Invoices -------------------------------------------------------------------------------------------------------
    iv = wb.create_sheet("Invoices")
    iv["A1"], iv["A1"].font = "Invoice log", S["title"]
    iv["A2"], iv["A2"].font = "One row per invoice you send. Type the Paid date when the money arrives; Status updates itself.", S["small"]
    ih = ["Invoice no.", "Client", "Sent", "Due", "Amount ($)", "Paid on", "Status", "Note"]
    for j, (h, w) in enumerate(zip(ih, (12, 28, 12, 12, 14, 12, 11, 30)), 1):
        c = iv.cell(row=4, column=j, value=h)
        c.font, c.fill, c.border = S["bold"], S["head"], S["line"]
        iv.column_dimensions[c.column_letter].width = w
    for rr in range(I_FIRST, I_LAST + 1):
        for j in (1, 2, 3, 4, 5, 6, 8):
            c = iv.cell(row=rr, column=j)
            c.fill, c.font = S["input"], S["blue"]
        for j in (3, 4, 6):
            iv.cell(row=rr, column=j).number_format = "yyyy-mm-dd"
        iv.cell(row=rr, column=5).number_format = MONEY
        g = iv.cell(row=rr, column=7, value=f'=IF(A{rr}="","",IF(F{rr}<>"","Paid",IF(AND(D{rr}<>"",D{rr}<TODAY()),"Overdue","Due")))')
        g.fill, g.font = S["calc"], S["bold"]
    ex = [["1001", "Example: Old Town Barbers (deposit)", dt.date(2026, 11, 10), dt.date(2026, 11, 24), 300, dt.date(2026, 11, 12), "50% deposit"],
          ["1002", "Example: Old Town Barbers (balance)", dt.date(2026, 12, 4), dt.date(2026, 12, 18), 300, None, "At launch"]]
    for i, row in enumerate(ex):
        for j, v in zip((1, 2, 3, 4, 5, 6, 8), row):
            iv.cell(row=I_FIRST + i, column=j, value=v)
    for txt, color in (("Paid", "D9EAD3"), ("Overdue", "F4CCCC"), ("Due", "FFF2CC")):
        iv.conditional_formatting.add(f"G{I_FIRST}:G{I_LAST}", CellIsRule(operator="equal", formula=[f'"{txt}"'], fill=__import__("openpyxl").styles.PatternFill("solid", fgColor=color)))
    iv.freeze_panes = "A5"

    ls = wb.create_sheet("Lists")
    ls["A1"], ls["B1"] = "Status", "Channel"
    for i, s in enumerate(STATUSES, 2):
        ls.cell(row=i, column=1, value=s)
    for i, s in enumerate(CHANNELS, 2):
        ls.cell(row=i, column=2, value=s)
    ls.column_dimensions["A"].width = ls.column_dimensions["B"].width = 16
    for w in wb.worksheets:
        w.sheet_view.zoomScale = 110
    wb.active = 0
    wb.save(path)
    return path


def build_invoice(path: str = INVOICE) -> str:
    from openpyxl import Workbook
    S = _styles()
    wb = Workbook()

    def sheet(ws, kind):
        for col, w in zip("ABCDE", (44, 21, 16, 16, 4)):
            ws.column_dimensions[col].width = w
        ws["A1"] = kind.upper()
        ws["A1"].font = __import__("openpyxl").styles.Font(name="Georgia", size=26, bold=True, color="8A5A1C")
        info = [("[Your business name]", True), ("[Street address, town, postcode]", False), ("[email] · [phone]", False), ("[Tax or business number, if you have one]", False)]
        for i, (t, b) in enumerate(info, 3):
            c = ws.cell(row=i, column=1, value=t)
            c.font, c.fill = (S["bold"] if b else S["norm"]), S["input"]
        labels = [(f"{kind} no.", "1001" if kind == "Invoice" else "Q-1001", "@"), ("Date", dt.date(2026, 11, 16), "yyyy-mm-dd"),
                  ("Payment terms (days)" if kind == "Invoice" else "Valid for (days)", 14, "0"),
                  ("Due date" if kind == "Invoice" else "Valid until", "=C4+C5", "yyyy-mm-dd")]
        for i, (lab, v, fmt) in enumerate(labels, 3):
            ws.cell(row=i, column=2, value=lab).font = S["small"]
            c = ws.cell(row=i, column=3, value=v)
            c.number_format = fmt
            c.fill, c.font = (S["calc"], S["bold"]) if str(v).startswith("=") else (S["input"], S["blue"])
        ws["A8"], ws["A8"].font = "Bill to" if kind == "Invoice" else "Prepared for", S["small"]
        for i, t in enumerate(["[Client business name]", "[Contact name]", "[Address]", "[Email]"], 9):
            c = ws.cell(row=i, column=1, value=t)
            c.fill, c.font = S["input"], S["blue"]
        hr = 14
        for j, h in enumerate(["Description", "Qty", "Rate ($)", "Amount ($)"], 1):
            c = ws.cell(row=hr, column=j, value=h)
            c.font, c.fill = S["white"], S["accent"]
        items = [("Example: one-page website (Starter package)", 1, 600), ("Example: local listing set-up", 1, 120)] if kind == "Invoice" else \
            [("Example: website (Standard package)", 1, 1200), ("Example: monthly care plan, first month", 1, 49)]
        first, last = hr + 1, hr + 12
        for rr in range(first, last + 1):
            for j in (1, 2, 3):
                c = ws.cell(row=rr, column=j)
                c.fill, c.font, c.border = S["input"], S["blue"], S["line"]
            ws.cell(row=rr, column=3).number_format = MONEY
            d = ws.cell(row=rr, column=4, value=f'=IF(OR(B{rr}="",C{rr}=""),"",B{rr}*C{rr})')
            d.number_format, d.fill, d.border = MONEY, S["calc"], S["line"]
        for i, (a, b, c_) in enumerate(items):
            ws.cell(row=first + i, column=1, value=a)
            ws.cell(row=first + i, column=2, value=b)
            ws.cell(row=first + i, column=3, value=c_)
        t0 = last + 2
        tot = [("Subtotal", f"=SUM(D{first}:D{last})", False), ("Discount ($)", 0, True), ("Tax rate", 0, True),
               ("Tax", f"=ROUND((D{t0}-D{t0 + 1})*D{t0 + 2},2)", False), ("TOTAL", f"=D{t0}-D{t0 + 1}+D{t0 + 3}", False)]
        if kind == "Invoice":
            tot += [("Paid so far", 0, True), ("BALANCE DUE", f"=D{t0 + 4}-D{t0 + 5}", False)]
        for i, (lab, v, is_input) in enumerate(tot):
            rr = t0 + i
            ws.cell(row=rr, column=3, value=lab).font = S["bold"] if lab.isupper() else S["norm"]
            c = ws.cell(row=rr, column=4, value=v)
            c.number_format = "0.0%" if "rate" in lab.lower() else MONEY
            c.fill, c.font = (S["input"], S["blue"]) if is_input else (S["calc"], S["big"] if lab.isupper() else S["norm"])
        n0 = t0 + len(tot) + 1
        notes = ["How to pay: [bank transfer details / card payment link / other]", "Thank you for your business!"] if kind == "Invoice" else \
            ["This quote is valid until the date above. Prices include: [what is included].", "To accept: reply to this email or sign below. Work starts after the signed agreement and the deposit."]
        for i, t in enumerate(notes):
            c = ws.cell(row=n0 + i, column=1, value=t)
            c.font, c.alignment = (S["norm"] if i else S["bold"]), S["wrap"]
            if i == 0:
                c.fill = S["input"]
        if kind == "Quote":
            ws.cell(row=n0 + 3, column=1, value="Accepted by: ______________________________   Date: ____________").font = S["norm"]
        ws.print_area = f"A1:D{n0 + 4}"
        ws.page_setup.orientation = "portrait"
        ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 1
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.sheet_view.showGridLines = False

    inv = wb.active
    inv.title = "Invoice"
    sheet(inv, "Invoice")
    sheet(wb.create_sheet("Quote"), "Quote")
    hw = wb.create_sheet("How to use")
    hw.column_dimensions["A"].width = 100
    for i, t in enumerate(["How to use the invoice and quote", "1. Save a copy of this file for each client (for example Invoice_1001_ClientName.xlsx).",
                           "2. Yellow cells with blue text are yours: your details, the client's details, the date, the lines (description, quantity, rate).",
                           "3. Amounts, tax, total and balance are calculated. Leave the tax rate at 0% if you do not charge tax; ask an accountant what applies to you.",
                           "4. Save or print as PDF and send it. Log it on the Invoices tab of Agency_Tracker.xlsx.",
                           "The lines that start with 'Example' are there to show how it works: type over them."], 1):
        c = hw.cell(row=i, column=1, value=t)
        c.font = S["title"] if i == 1 else S["norm"]
    wb.active = 0
    wb.save(path)
    return path


# ------------------------------------------------------------------------------------------------ text files
LICENSE = f"""FIRST CLIENTS AGENCY STARTER KIT v{VERSION}: LICENCE

What you may do
- Use, edit and send these documents and spreadsheets in your own business, with as many clients as you like.
- Put your own name and logo on them. Documents you send to clients are yours.

What you may not do
- Resell, share, upload or give away the kit, or edited copies of it, as templates or as part of another kit or course.

Important
- The service agreement, the proposal terms and the other legal-looking templates are NOT LEGAL ADVICE. They are plain-English
  starting points. Laws differ by state and country: have a qualified lawyer in your area review them before you use them.
- The kit does not promise clients, income or results. The example names, phone numbers (555-01xx) and prices are made up.
- Provided as is, without warranty of any kind. If something does not work as described, message the seller through the shop
  where you bought this within 14 days and we will help you or refund you.
"""

README = f"""FIRST CLIENTS AGENCY STARTER KIT v{VERSION}: QUICK START

1. Read 00_Start_Here.pdf (10 minutes): the 30-day plan and the rules for emails, calls and texts.
2. Open Agency_Tracker.xlsx: set your hourly rate on the Pricing tab and list your first 25 businesses on the Prospects tab.
3. Use 01_Outreach_Scripts.docx to contact them, 02 for the call, 03 for the proposal, 04 for the agreement (not legal advice:
   have it reviewed), 05 to start the project, 06 for honest reviews and referrals, 07 to deliver the work the same way each time.
4. Bill with Invoice_Template.xlsx and log each invoice on the tracker's Invoices tab.

The .docx files open in the usual word processors on a computer and in free online document editors (upload or import them).
The .xlsx files open in the usual spreadsheet apps and in free online spreadsheets.
Words in [brackets] (highlighted in yellow) are for you to replace.
"""


# ------------------------------------------------------------------------------------------------ pictures
def soffice_pdf(src: str, out_dir: str) -> str:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    prof = tempfile.mkdtemp(prefix="d2_lo_")
    try:
        subprocess.run([exe, f"-env:UserInstallation=file://{prof}/profile", "--headless", "--convert-to", "pdf", "--outdir", out_dir, src],
                       capture_output=True, timeout=240, check=True)
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    return os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + ".pdf")


def soffice_pdfs(srcs: list, out_dir: str) -> list:
    """Several files to PDF in one LibreOffice run (much faster than one run each)."""
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    prof = tempfile.mkdtemp(prefix="d2_lo_")
    try:
        subprocess.run([exe, f"-env:UserInstallation=file://{prof}/profile", "--headless", "--convert-to", "pdf", "--outdir", out_dir] + list(srcs),
                       capture_output=True, timeout=600, check=True)
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    return [os.path.join(out_dir, os.path.splitext(os.path.basename(x))[0] + ".pdf") for x in srcs]


def page_pictures(tmp: str) -> dict:
    """First pages of the real files (LibreOffice -> PDF -> PNG): {file name: [png bytes, ...]}"""
    out = {}
    names = [d[0] for d in A.DOCS] + ["Agency_Tracker.xlsx", "Invoice_Template.xlsx"]
    pdfs = soffice_pdfs([os.path.join(BUYER, n) for n in names], tmp)
    for name, pdf in zip(names, pdfs):
        pngs = K.pdf_pages_png(pdf, os.path.join(tmp, name.split(".")[0]), dpi=80)
        if name == "Agency_Tracker.xlsx":                     # show the Prospects page (with the example rows), not the instructions
            try:
                from pypdf import PdfReader
                at = next((i for i, p in enumerate(PdfReader(pdf).pages) if "Riverton" in (p.extract_text() or "")), 0)
                pngs = pngs[at:] + pngs[:at]
            except Exception:
                pass
        out[name] = [open(p, "rb").read() for p in pngs[:3]]
    pngs = K.pdf_pages_png(os.path.join(BUYER, "00_Start_Here.pdf"), os.path.join(tmp, "start"), dpi=80)
    out["00_Start_Here.pdf"] = [open(p, "rb").read() for p in pngs[:2]]
    return out


def covers(br, pics: dict) -> list:
    from io import BytesIO

    from PIL import Image

    def u(name, i=0, crop=None):
        im = Image.open(BytesIO(pics[name][i])).convert("RGB")
        if crop:
            im = im.crop((0, 0, im.width, int(im.width * crop)))
        b = BytesIO()
        im.save(b, "JPEG", quality=88)
        return K.b64(b.getvalue())
    done = []
    bg, ink, soft, acc = "#1b1814", "#f3ece0", "#cfc4b2", "#c8a24a"
    stack = [u("04_Service_Agreement.docx"), u("03_Proposal_Template.docx"), u("01_Outreach_Scripts.docx"), u("00_Start_Here.pdf")]
    files = [("00_Start_Here.pdf", "PDF", "The 30-day plan and the rules"), ("01_Outreach_Scripts.docx", "DOC", "Walk-in, phone, email, message, objections"),
             ("02_Discovery_Call.docx", "DOC", "A 20-minute call, the questions, notes"), ("03_Proposal_Template.docx", "DOC", "3 options, timeline, terms"),
             ("04_Service_Agreement.docx", "DOC", "Plain-English agreement*"), ("05_Client_Onboarding.docx", "DOC", "Welcome, content list, launch, handover"),
             ("06_Reviews_and_Referrals.docx", "DOC", "Honest review asks, replies, referrals"), ("07_Service_Checklists.docx", "DOC", "Launch, listing set-up, monthly care"),
             ("Agency_Tracker.xlsx", "XLS", "Prospects, follow-ups, pricing, invoices"), ("Invoice_Template.xlsx", "XLS", "Quote + invoice that add up")]
    for name, w, h in K.COVERS:
        sq, k, n = w == h, w / 1280, name.split("_")[1][0]
        css = K.cover_css(w, h, bg=bg, ink=ink, soft=soft, accent=acc) + f"""
.pad{{position:absolute;inset:0;padding:{int(60 * k)}px}}.kick{{font-size:{int(21 * k)}px;padding:{int(7 * k)}px {int(18 * k)}px;margin-bottom:{int(22 * k)}px}}
h1{{font-size:{int((78 if sq else 58) * k)}px}}.lead{{font-size:{int((30 if sq else 23) * k)}px;line-height:1.35;margin-top:{int(18 * k)}px;color:{soft}}}
ul.checks li{{font-size:{int((28 if sq else 22) * k)}px;margin:{int(11 * k)}px 0}}
.foot{{position:absolute;left:{int(60 * k)}px;bottom:{int(24 * k)}px;font-size:{int((18 if sq else 15) * k)}px;color:#a89c88}}
.pg{{position:absolute;background:#fff;border-radius:{max(3, int(5 * k))}px;box-shadow:0 {int(18 * k)}px {int(40 * k)}px rgba(0,0,0,.5)}}
.tile{{display:flex;gap:{int((22 if sq else 16) * k)}px;align-items:center;background:#26211b;border:1px solid #3a3228;border-radius:{int(14 * k)}px;padding:{int((26 if sq else 9) * k)}px {int((24 if sq else 14) * k)}px}}
.ic{{flex:none;width:{int((78 if sq else 46) * k)}px;height:{int((94 if sq else 56) * k)}px;border-radius:{int(6 * k)}px;display:grid;place-items:end center;padding-bottom:{int(8 * k)}px;font-weight:800;font-size:{int((19 if sq else 15) * k)}px;color:#1b1814;
clip-path:polygon(0 0,72% 0,100% 22%,100% 100%,0 100%)}}.ic.DOC{{background:#9fc0dd}}.ic.XLS{{background:#a9c98f}}.ic.PDF{{background:#e3a08a}}
.tile b{{display:block;font-size:{int((24 if sq else 17) * k)}px;color:{ink}}}.tile span{{display:block;font-size:{int((20 if sq else 14) * k)}px;color:{soft};margin-top:{int(4 * k)}px}}"""
        if n == "1":
            text = (f'<span class="chip kick">7 documents + 2 spreadsheets + the plan</span><h1>First Clients Agency Starter Kit</h1><div class="rule" style="margin-top:{int(22 * k)}px"></div>'
                    f'<p class="lead">For new web designers and local marketers: what to say, what to send, what to sign, how to bill.</p>'
                    f'<ul class="checks" style="margin-top:{int(14 * k)}px"><li>Outreach scripts that follow the rules</li><li>Proposal + service agreement*</li>'
                    f'<li>Onboarding, honest reviews, checklists</li><li>Tracker, pricing calculator, invoices</li></ul>')
            if sq:
                pos = [(830, 640, 9, 358), (650, 660, 3, 358), (470, 690, -4, 358), (290, 720, -10, 358)]
                body = f'<div class="pad">{text}</div>'
            else:
                pos = [(925, 110, 9, 285), (818, 140, 3, 285), (711, 180, -3, 285), (614, 225, -9, 285)]
                body = f'<div class="pad" style="width:{int(600 * k)}px">{text}</div>'
            body += "".join(f'<img class="pg" src="{s}" style="left:{int(x * k)}px;top:{int(y * k)}px;width:{int(pw * k)}px;transform:rotate({r}deg)">' for s, (x, y, r, pw) in zip(stack, pos))
            body += '<div class="foot">*Templates, not legal advice: have a lawyer in your area review the agreement. No client or income results promised.</div>'
        elif n == "2":
            cols = 2
            tiles = "".join(f'<div class="tile"><div class="ic {t}">{t}</div><div><b>{f}</b><span>{d}</span></div></div>' for f, t, d in files)
            body = (f'<div class="pad"><h1 style="font-size:{int((70 if sq else 46) * k)}px">What is inside</h1><div class="rule" style="margin-top:{int(16 * k)}px"></div></div>'
                    f'<div style="position:absolute;left:{int(60 * k)}px;right:{int(60 * k)}px;top:{int((260 if sq else 150) * k)}px;display:grid;grid-template-columns:repeat({cols},1fr);gap:{int((26 if sq else 12) * k)}px">{tiles}</div>'
                    '<div class="foot">Editable in the usual word processors and spreadsheet apps, or free online editors. *Not legal advice.</div>')
        else:
            steps = [("Find", "25 local businesses"), ("Reach out", "scripts, follow-ups"), ("Call", "20-minute discovery"), ("Propose", "3 clear options"),
                     ("Agree", "signed + deposit"), ("Deliver", "onboarding, checklists"), ("Bill + ask", "invoice, honest review")]
            sw = int((248 if sq else 160) * k)
            flow = "".join(f'<div style="width:{sw}px;text-align:center"><div style="width:{int(58 * k)}px;height:{int(58 * k)}px;margin:0 auto {int(10 * k)}px;border-radius:50%;background:{acc};color:#1b1814;display:grid;place-items:center;font-weight:800;font-size:{int(26 * k)}px">{i}</div>'
                           f'<b style="display:block;font-size:{int((26 if sq else 20) * k)}px">{t}</b><span class="soft" style="font-size:{int((19 if sq else 14) * k)}px">{d}</span></div>' for i, (t, d) in enumerate(steps, 1))
            tw = 1060 if sq else 470
            trk = u("Invoice_Template.xlsx", 0, crop=0.72)
            if sq:
                rows = f'<div style="position:absolute;top:{int(330 * k)}px;left:{int(60 * k)}px;right:{int(60 * k)}px;display:grid;grid-template-columns:repeat(4,1fr);row-gap:{int(40 * k)}px;justify-items:center">{flow}</div>'
                pic = f'<div style="position:absolute;left:470px;top:1000px">{K.window(trk, tw)}</div>'
            else:
                rows = f'<div style="position:absolute;top:{int(175 * k)}px;left:{int(40 * k)}px;right:{int(40 * k)}px;display:flex;justify-content:space-between">{flow}</div>'
                pic = f'<div style="position:absolute;left:405px;top:318px;height:350px;overflow:hidden;border-radius:10px">{K.window(trk, tw)}</div>'
            body = (f'<div class="pad"><h1 style="font-size:{int((66 if sq else 44) * k)}px">From first hello to paid invoice</h1><div class="rule" style="margin-top:{int(16 * k)}px"></div></div>{rows}{pic}'
                    '<div class="foot">The invoice adds itself up; the tracker counts your own numbers: contacts, replies, proposals, invoices.</div>')
        html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"
        done.append(K.shoot(br, html, w, h, os.path.join(SHOP, name), quality=80 if sq else 84))
    return done


def build_media(log=print) -> list:
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as pw:
        br = K.chromium(pw)
        out.append(K.html_pdf(br, G.to_html(A.START), os.path.join(BUYER, "00_Start_Here.pdf"), "Letter", A.START["title"]))
        tmp = tempfile.mkdtemp(prefix="d2_agency_")
        try:
            out += covers(br, page_pictures(tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        br.close()
    return out


def build(images: bool = True, log=print) -> list:
    os.makedirs(BUYER, exist_ok=True)
    done = []
    for fname, doc in A.DOCS:
        p = G.to_docx(doc, os.path.join(BUYER, fname))
        done.append(K.clean_ooxml(p, doc["title"]))
    for fn, title in ((build_tracker, "Agency Tracker"), (build_invoice, "Invoice and quote")):
        p = fn()
        log(K.recalc_xlsx(p))
        done.append(K.clean_ooxml(p, title))
    done.append(K.write_text(os.path.join(BUYER, "LICENSE.txt"), LICENSE))
    done.append(K.write_text(os.path.join(BUYER, "README.txt"), README))
    if images:
        done += build_media(log)
    done += K.write_listing(SHOP, dict(LISTING, files=K.buyer_files(BUYER)))
    return done


LISTING = {
    "id": "agency-kit", "version": VERSION, "price_usd": 19, "top": TOP, "zip": ZIP,
    "title": "Web Design Business Starter Kit: Client Outreach Scripts, Proposal, Service Agreement, Onboarding, Invoice and Client Tracker Templates",
    "short": "Everything a new web designer or local marketer sends in the first month: scripts, proposal, agreement, onboarding, invoices and a tracker.",
    "description": [
        "Starting a small web design or local marketing service? The hard part is often the paperwork and the words: what to say to a business owner, what to send after the call, what to sign, how to bill. This kit gives you all of it, editable.",
        "WHAT YOU GET",
        "- 00 Start Here (PDF): a 30-day plan from choosing your offer to your first invoice, with the rules for emails, calls and texts",
        "- 01 Outreach scripts: walk-in, phone opener and voicemail, a first email and two follow-ups, a short message, network asks, polite replies, honest answers to 6 objections",
        "- 02 Discovery call: a 20-minute plan, 17 questions, a notes page and the warning signs",
        "- 03 Proposal template: three options in a table, timeline, what is not included, payment terms",
        "- 04 Service agreement template: plain English, 12 sections (scope, payment, changes, ownership, liability, ending). Not legal advice: have it reviewed by a lawyer",
        "- 05 Client onboarding: welcome email, content checklist, kick-off agenda, launch check, handover email",
        "- 06 Reviews and referrals: honest review requests (no rewards, no gating), replies to good, mixed and bad reviews, a testimonial permission form",
        "- 07 Service checklists: website launch, local listing set-up, monthly care plan and the monthly note",
        "- Agency Tracker (spreadsheet): prospects with follow-up reminders, a dashboard of your own numbers, a package pricing calculator and an invoice log",
        "- Invoice and quote (spreadsheet): totals, tax and balance calculate themselves",
        "GOOD TO KNOW",
        "- Documents are .docx and spreadsheets .xlsx: they open in the usual office apps and in free online editors",
        "- The legal templates are not legal advice; laws differ by place. The kit does not promise clients or income",
        "- Written for the US first (CAN-SPAM email rules, call and text rules), with notes for other places",
        "Instant download. Written with the help of AI tools; checked, edited and supported by me.",
    ],
    "tags_etsy": ["web design business", "freelancer kit", "client onboarding", "proposal template", "contract template", "invoice template",
                  "client tracker", "small business kit", "cold email scripts", "agency templates", "web designer kit", "service agreement", "freelance forms"],
    "faq": [
        ["Is the service agreement legally binding where I live?", "It is a plain-English template, not legal advice. Laws differ by state and country, so have a local lawyer review it before you use it."],
        ["Which apps do I need?", "Any word processor that opens .docx and any spreadsheet app that opens .xlsx, including free online ones."],
        ["Will this get me clients?", "No kit can promise that. It gives you the words, documents and a plan, so your time goes into talking to businesses and doing good work."],
        ["Is it only for web designers?", "It is written for websites and local marketing (listings, social posts, care plans), but most of it works for any small service business."],
        ["Are the outreach scripts spam?", "No: they are personal messages you send by hand, a few a day, with the US email, call and text rules explained, and they respect every no."],
        ["Can I put my own brand on the documents?", "Yes. Use and edit them in your business with as many clients as you like; just don't resell the kit itself."],
    ],
    "refund": "Digital download: files can't be returned, but if something does not work as described, message me within 14 days and I will fix it or refund you.",
    "price_reasoning": ("$19: comparable bundles on Etsy list from $7.49 (a developer contract bundle on sale) and $9.99 (contract, brief, checklist, "
                        "invoice) to $14.25 (an onboarding kit, on sale from $19) and $16.73 (a VA onboarding toolkit); off Etsy $9.99-$49 (Getly, Payhip $17, "
                        "Gumroad $49) and a pro contract pack at $89. Ours is bigger than the $10 bundles (7 documents, 2 working spreadsheets, a 30-day "
                        "plan), so $19 sits at the top of the Etsy range and well under the off-Etsy top end. Try $15 if views don't turn into sales; $24 after 10 good reviews."),
    "comparables": [
        {"what": "Web developer contract bundle (contract, discovery brief, delivery log, invoice)", "price": "$7.49 (sale from $9.99)", "where": "Etsy", "url": "https://www.etsy.com/ca/listing/4511821405/web-developer-contract-bundle-full-stack", "seen": "2026-11-14"},
        {"what": "Developer bundle: contract, project brief, handoff checklist, invoice", "price": "$9.99", "where": "Etsy", "url": "https://www.etsy.com/listing/4509314444/wordpress-developer-contract-template", "seen": "2026-11-14"},
        {"what": "Freelancer onboarding kit generator", "price": "$14.25 (sale from $19.00)", "where": "Etsy", "url": "https://www.etsy.com/listing/4521034282/", "seen": "2026-11-14"},
        {"what": "Client onboarding kit", "price": "$17", "where": "Payhip", "url": "https://payhip.com/b/6WXB8", "seen": "2026-11-14"},
        {"what": "Web freelancer contract pack (professional software)", "price": "$89", "where": "the maker's own site", "url": "https://www.proposalkit.com/htm/web-freelancer-legal-contract-pack.htm", "seen": "2026-11-14"},
    ],
    "image_notes": ["the kit and its first pages", "every file and what it is for", "the path from hello to invoice + the tracker", "square 1", "square 2", "square 3"],
    "rules": [
        "Say 'not legal advice' in the description, the FAQ and on the agreement itself (done). Never call it a lawyer-approved contract.",
        "No client, income or 'fill your calendar' promises.",
        "No app or platform names in the title, tags or pictures.",
        "Etsy: 'I did', digital download; the description says AI tools helped.",
    ],
}


def make_zip(out: str | None = None) -> str:
    return K.make_zip(BUYER, TOP, ZIP, out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.products.build_agency_kit")
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args(argv)
    if a.zip and not a.build:
        print(make_zip())
        return 0
    for p in build(images=not a.no_images):
        print(p)
    if a.zip:
        print(make_zip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
