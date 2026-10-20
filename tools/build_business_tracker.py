"""Build the owner's prop-firm business tracker: research/business/prop_business.xlsx (openpyxl, live formulas).

Sheets: Summary, Settings, Accounts, Fees, Payouts, Monthly P&L, Tax set-aside, Z06 goal. Pre-filled with the MFFU Builder
50K eval ($91.80, start 2026-10-19). The owner keeps the file by hand after that, so this script never overwrites an
existing file unless --force (it would wipe what he typed). Docs: docs/BUSINESS_TRACKER.md.

    python tools/build_business_tracker.py [--out research/business/prop_business.xlsx] [--force]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "business", "prop_business.xlsx")

F = "Arial"
BLUE, GREEN, BLACK = "0000FF", "008000", "000000"
YELLOW = PatternFill("solid", fgColor="FFFF00")
HEAD = PatternFill("solid", fgColor="1F2937")
BAND = PatternFill("solid", fgColor="F3F4F6")
THIN = Border(bottom=Side(style="thin", color="D1D5DB"))
USD = '$#,##0.00;($#,##0.00);"-"'
USD0 = '$#,##0;($#,##0);"-"'
PCT = '0.0%;(0.0%);"-"'
DATE = "yyyy-mm-dd"
MONTH = "mmm yyyy"
N_ROWS = 200          # input rows with formulas / validation ready on Accounts, Fees, Payouts
MONTHS = 36           # Monthly P&L: Oct 2026 .. Sep 2029


def font(color=BLACK, bold=False, size=10, italic=False):
    return Font(name=F, color=color, bold=bold, size=size, italic=italic)


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = font(bold=True, size=14)
    if sub:
        ws["A2"] = sub
        ws["A2"].font = font(italic=True, size=9, color="4B5563")


def header(ws, row, names, widths=None):
    for j, n in enumerate(names, 1):
        c = ws.cell(row=row, column=j, value=n)
        c.font = Font(name=F, bold=True, color="FFFFFF", size=10)
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def inp(c, v, fmt=None, key=False):
    """An input cell: blue text (yellow fill for a key assumption)."""
    c.value = v
    c.font = font(BLUE)
    if fmt:
        c.number_format = fmt
    if key:
        c.fill = YELLOW
    return c


def fx(c, v, fmt=None, link=False, bold=False):
    """A formula cell: black, green when it only links to another sheet."""
    c.value = v
    c.font = font(GREEN if link else BLACK, bold=bold)
    if fmt:
        c.number_format = fmt
    return c


def legend(ws, row, col=1):
    rows = [("Legend", None), ("Blue text = you type it", BLUE), ("Black = formula (leave it)", BLACK),
            ("Green = linked from another sheet", GREEN), ("Yellow fill = key setting", None)]
    for i, (t, colr) in enumerate(rows):
        c = ws.cell(row=row + i, column=col, value=t)
        c.font = font(colr or BLACK, bold=i == 0, size=9)
        if t.startswith("Yellow"):
            c.fill = YELLOW


def build(out):
    wb = Workbook()
    S = wb.active
    S.title = "Summary"

    # ---------------- Settings
    st = wb.create_sheet("Settings")
    title(st, "Settings", "The few numbers the other sheets use. Change the yellow cells.")
    st.column_dimensions["A"].width = 40
    st.column_dimensions["B"].width = 16
    st.column_dimensions["C"].width = 90
    rows = [
        ("Tax set-aside (% of positive net)", 0.30, PCT,
         "Your own pick. A simple savings rule, NOT tax advice: ask a tax professional what you really owe."),
        ("Goal name", "Corvette Z06", None, "Your goal."),
        ("Goal price ($)", 115000, USD0,
         "Placeholder near the 2026 Corvette Z06 base price (~$115k with destination); put in your real out-the-door quote."),
        ("Monthly rate used for the goal ($ per month, per account)", 2400, USD0,
         "LIT H2 2026 check-half rate, ~$2,400/mo (CLAUDE.md, run lit_live, H2 PF 2.46 +$8,962, paper backtest, "
         "costs in). A backtest rate on paper, not a promise: replace it with your real average once payouts arrive. "
         "Funded payouts are smaller: the funded sizing study pays ~$740-770/mo per account (lit-funded-sizing.md)."),
        ("Funded accounts earning at that rate", 1, "0",
         "How many accounts pay at the rate above (1 today: one bot routes to one account)."),
        ("Payouts you keep (% of the rate)", 0.90, PCT,
         "MFFU funded payouts: you keep 90% (verify your plan's split). Applied to the rate above for the goal."),
        ("Money already saved toward the goal ($)", 0, USD0, "Anything set aside outside this tracker."),
    ]
    for i, (lbl, v, fmt, note) in enumerate(rows, 4):
        st.cell(row=i, column=1, value=lbl).font = font(bold=True)
        inp(st.cell(row=i, column=2), v, fmt, key=True)
        st.cell(row=i, column=3, value=note).font = font(size=9, italic=True, color="4B5563")
    st["A12"] = "Status choices (Accounts sheet)"
    st["A12"].font = font(bold=True)
    statuses = ["Eval - active", "Eval - passed", "Eval - failed", "Funded - active", "Funded - lost", "Closed"]
    for i, s in enumerate(statuses, 13):
        st.cell(row=i, column=1, value=s).font = font(BLUE)
    st["A20"] = "Fee types (Fees sheet)"
    st["A20"].font = font(bold=True)
    ftypes = ["Eval purchase", "Reset", "Activation", "Monthly subscription", "Data / platform", "Other"]
    for i, s in enumerate(ftypes, 21):
        st.cell(row=i, column=1, value=s).font = font(BLUE)
    legend(st, 28)
    TAX, GOALN, GOAL, RATE, NACC, KEEP, SAVED = ("Settings!$B$4", "Settings!$B$5", "Settings!$B$6", "Settings!$B$7",
                                                 "Settings!$B$8", "Settings!$B$9", "Settings!$B$10")

    # ---------------- Accounts
    ac = wb.create_sheet("Accounts")
    title(ac, "Accounts", "One row per account you buy (an eval, a reset that starts a new account, a funded account). "
                         "Row 4 is the current MFFU eval; add yours below it.")
    header(ac, 3, ["Firm", "Plan", "Account / nickname", "List price ($)", "Price paid ($)", "Saved by codes ($)",
                   "Discount codes used", "Start date", "Status", "End date", "Days open", "Fees on it ($)",
                   "Payouts from it ($)", "Net on it ($)", "Notes"],
           [16, 16, 20, 13, 13, 14, 22, 12, 16, 12, 10, 13, 15, 13, 50])
    dv = DataValidation(type="list", formula1="=Settings!$A$13:$A$18", allow_blank=True)
    ac.add_data_validation(dv)
    for r in range(4, 4 + N_ROWS):
        for col, fmt in ((4, USD), (5, USD), (8, DATE), (10, DATE)):
            inp(ac.cell(row=r, column=col), None, fmt)
        for col in (1, 2, 3, 7, 9, 15):
            ac.cell(row=r, column=col).font = font(BLUE)
        fx(ac.cell(row=r, column=6), f'=IF(AND(D{r}<>"",E{r}<>""),D{r}-E{r},"")', USD)
        fx(ac.cell(row=r, column=11), f'=IF(H{r}="","",IF(J{r}="",TODAY(),J{r})-H{r})', "0")
        fx(ac.cell(row=r, column=12), f'=IF(C{r}="","",SUMIFS(Fees!$F:$F,Fees!$C:$C,C{r}))', USD)
        fx(ac.cell(row=r, column=13), f'=IF(C{r}="","",SUMIFS(Payouts!$E:$E,Payouts!$C:$C,C{r}))', USD)
        fx(ac.cell(row=r, column=14), f'=IF(C{r}="","",M{r}-L{r})', USD)
        dv.add(f"I{r}")
    pre = ["MyFundedFutures (MFFU)", "Builder 50K", "MFFU 50K eval #1", None, 91.80, None, "owner's MFFU discount code",
           dt.date(2026, 10, 19), "Eval - active", None]
    for j, v in enumerate(pre, 1):
        if v is not None:
            ac.cell(row=4, column=j, value=v)
    ac["O4"] = ("One-time price, $0 activation (owner, 2026-10-18). Type the list price in D4 to see what the code saved. "
                "Eval balance was -$100 when the bot went live.")
    ac["E4"].comment = Comment("Owner's real price, 2026-10-18 (CLAUDE.md): Builder 50K $91.80 one-time with a discount code.", "tracker")

    # ---------------- Fees
    fe = wb.create_sheet("Fees")
    title(fe, "Fees", "Every dollar paid to a firm or for tools: eval purchases, resets, activation, subscriptions, data.")
    header(fe, 3, ["Date", "Firm", "Account / nickname", "Type", "Description", "Amount ($)", "Code used", "Notes"],
           [12, 22, 20, 20, 30, 12, 22, 40])
    dvf = DataValidation(type="list", formula1="=Settings!$A$21:$A$26", allow_blank=True)
    fe.add_data_validation(dvf)
    for r in range(4, 4 + N_ROWS):
        inp(fe.cell(row=r, column=1), None, DATE)
        inp(fe.cell(row=r, column=6), None, USD)
        for col in (2, 3, 4, 5, 7, 8):
            fe.cell(row=r, column=col).font = font(BLUE)
        dvf.add(f"D{r}")
    for j, v in enumerate([dt.date(2026, 10, 19), "MyFundedFutures (MFFU)", "MFFU 50K eval #1", "Eval purchase",
                           "Builder 50K eval, one-time", 91.80, "owner's MFFU discount code", "$0 activation"], 1):
        fe.cell(row=4, column=j, value=v)

    # ---------------- Payouts
    po = wb.create_sheet("Payouts")
    title(po, "Payouts", "Money that reached your bank. Requested = what you asked for; Received = what arrived after the split.")
    header(po, 3, ["Date received", "Firm", "Account / nickname", "Requested ($)", "Received ($)", "Split kept",
                   "Method", "Notes"], [14, 22, 20, 14, 14, 11, 16, 40])
    for r in range(4, 4 + N_ROWS):
        inp(po.cell(row=r, column=1), None, DATE)
        inp(po.cell(row=r, column=4), None, USD)
        inp(po.cell(row=r, column=5), None, USD)
        for col in (2, 3, 7, 8):
            po.cell(row=r, column=col).font = font(BLUE)
        fx(po.cell(row=r, column=6), f'=IF(AND(D{r}>0,E{r}<>""),E{r}/D{r},"")', PCT)
    po["H4"] = "Example of the format (delete this note): 2026-12-15 | MyFundedFutures (MFFU) | MFFU 50K funded | 1000 | 900"
    po["H4"].font = font(size=9, italic=True, color="4B5563")

    # ---------------- Monthly P&L
    mp = wb.create_sheet("Monthly P&L")
    title(mp, "Monthly P&L", "Built from Fees and Payouts by date. Nothing to type here.")
    header(mp, 3, ["Month", "Fees ($)", "Payouts received ($)", "Net ($)", "Tax set-aside ($)", "Net after set-aside ($)",
                   "Cumulative net ($)", "Cumulative after set-aside ($)"], [12, 13, 18, 13, 16, 20, 17, 24])
    for i in range(MONTHS):
        r = 4 + i
        if i == 0:
            inp(mp.cell(row=r, column=1), dt.date(2026, 10, 1), MONTH)
        else:
            fx(mp.cell(row=r, column=1), f"=DATE(YEAR(A{r - 1}),MONTH(A{r - 1})+1,1)", MONTH)
        nxt = f"DATE(YEAR(A{r}),MONTH(A{r})+1,1)"
        fx(mp.cell(row=r, column=2), f'=SUMIFS(Fees!$F$4:$F${3 + N_ROWS},Fees!$A$4:$A${3 + N_ROWS},">="&A{r},'
                                     f'Fees!$A$4:$A${3 + N_ROWS},"<"&{nxt})', USD)
        fx(mp.cell(row=r, column=3), f'=SUMIFS(Payouts!$E$4:$E${3 + N_ROWS},Payouts!$A$4:$A${3 + N_ROWS},">="&A{r},'
                                     f'Payouts!$A$4:$A${3 + N_ROWS},"<"&{nxt})', USD)
        fx(mp.cell(row=r, column=4), f"=C{r}-B{r}", USD)
        fx(mp.cell(row=r, column=5), f"=MAX(0,D{r})*{TAX}", USD)
        fx(mp.cell(row=r, column=6), f"=D{r}-E{r}", USD)
        fx(mp.cell(row=r, column=7), f"=D{r}" if i == 0 else f"=G{r - 1}+D{r}", USD)
        fx(mp.cell(row=r, column=8), f"=F{r}" if i == 0 else f"=H{r - 1}+F{r}", USD)
        if i % 2:
            for col in range(1, 9):
                mp.cell(row=r, column=col).fill = BAND
    last = 3 + MONTHS
    tr = last + 1
    mp.cell(row=tr, column=1, value="Total").font = font(bold=True)
    for col in "BCDEF":
        fx(mp[f"{col}{tr}"], f"=SUM({col}4:{col}{last})", USD, bold=True)
    mp["A1"].comment = Comment("Row 4's month (A4) is an input: change it to start the table elsewhere.", "tracker")

    # ---------------- Tax set-aside
    tx = wb.create_sheet("Tax set-aside")
    title(tx, "Tax set-aside estimate - NOT tax advice",
          "A savings rule only: the % from Settings on each month's positive net. Real tax depends on your country, "
          "income, expenses and how payouts are reported. Ask a tax professional.")
    header(tx, 4, ["Year", "Fees ($)", "Payouts ($)", "Net ($)", "Set-aside rate", "Set aside so far ($)",
                   "Simple year estimate ($)"], [10, 13, 13, 13, 14, 20, 24])
    tx.freeze_panes = None
    for i, y in enumerate((2026, 2027, 2028, 2029)):
        r = 5 + i
        inp(tx.cell(row=r, column=1), y, "0")
        rng = f"'Monthly P&L'!$A$4:$A${last}"
        for col, src in ((2, "B"), (3, "C"), (4, "D"), (6, "E")):
            fx(tx.cell(row=r, column=col), f"=SUMPRODUCT((YEAR({rng})=A{r})*'Monthly P&L'!${src}$4:${src}${last})", USD)
        fx(tx.cell(row=r, column=5), f"={TAX}", PCT, link=True)
        fx(tx.cell(row=r, column=7), f"=MAX(0,D{r})*E{r}", USD)
    tx["A10"] = ("'Set aside so far' adds the rate on each winning month (a losing month sets nothing aside); 'Simple year "
                 "estimate' is the rate on the year's net. Keep the larger one in a separate savings account.")
    tx["A10"].font = font(size=9, italic=True, color="4B5563")

    # ---------------- Z06 goal
    gz = wb.create_sheet("Z06 goal")
    title(gz, "Z06 goal", "Progress from this tracker's net after the tax set-aside, and months to go at the H2 rate (Settings).")
    gz.column_dimensions["A"].width = 46
    gz.column_dimensions["B"].width = 18
    gz.column_dimensions["C"].width = 70
    g = [("Goal", f"={GOALN}", None, True, ""),
         ("Goal price", f"={GOAL}", USD0, True, ""),
         ("Saved so far (net after set-aside + already saved)", f"='Monthly P&L'!H{last}+{SAVED}", USD0, False,
          "From Monthly P&L (all months) plus Settings 'already saved'."),
         ("Still needed", "=MAX(0,B5-B6)", USD0, False, ""),
         ("Progress", "=IF(B5>0,MAX(0,MIN(1,B6/B5)),0)", PCT, False, ""),
         ("Rate per month (Settings: per account x accounts x split kept)", f"={RATE}*{NACC}*{KEEP}", USD0, False,
          "H2 2026 paper rate by default."),
         ("Rate after the tax set-aside", f"=B9*(1-{TAX})", USD0, False, ""),
         ("Months to the goal at that rate", '=IF(B10>0,ROUNDUP(B7/B10,0),"no rate")', "0", False,
          "Whole months, rounded up."),
         ("Estimated date", '=IF(ISNUMBER(B11),DATE(YEAR(TODAY()),MONTH(TODAY())+B11,1),"-")', MONTH, False,
          "From today. Only as good as the rate: a backtest rate is not a promise.")]
    for i, (lbl, f, fmt, link, note) in enumerate(g, 4):
        gz.cell(row=i, column=1, value=lbl).font = font(bold=True)
        fx(gz.cell(row=i, column=2), f, fmt, link=link, bold=i in (7, 11))
        gz.cell(row=i, column=3, value=note).font = font(size=9, italic=True, color="4B5563")
    gz["A14"] = "Months to goal at other rates ($ per month before the set-aside; $750 ~ the funded-payout estimate):"
    gz["A14"].font = font(bold=True)
    for i, rate in enumerate((750, 1500, 2400, 4000)):
        r = 15 + i
        inp(gz.cell(row=r, column=1), rate, USD0)
        fx(gz.cell(row=r, column=2), f'=IF(A{r}>0,ROUNDUP($B$7/(A{r}*(1-{TAX})),0),"-")', '0" months"')

    # ---------------- Summary
    title(S, "Prop-firm business - summary", "Everything below is a formula. Type into Accounts, Fees and Payouts; "
                                             "settings on Settings. Paper backtest numbers are not promises.")
    S.column_dimensions["A"].width = 44
    S.column_dimensions["B"].width = 18
    S.column_dimensions["C"].width = 60
    A = f"Accounts!$I$4:$I${3 + N_ROWS}"
    sm = [("Money in and out", None, None),
          ("Total paid in fees", f"=SUM(Fees!$F$4:$F${3 + N_ROWS})", USD),
          ("Total payouts received", f"=SUM(Payouts!$E$4:$E${3 + N_ROWS})", USD),
          ("Net (payouts - fees)", "=B6-B5", USD),
          ("Return on fees", '=IF(B5>0,B7/B5,"-")', PCT),
          ("Saved by discount codes", f"=SUM(Accounts!$F$4:$F${3 + N_ROWS})", USD),
          ("This month's net", "=INDEX('Monthly P&L'!$D$4:$D$" + str(last) +
           ",MATCH(DATE(YEAR(TODAY()),MONTH(TODAY()),1),'Monthly P&L'!$A$4:$A$" + str(last) + ",0))", USD),
          ("Accounts", None, None),
          ("Accounts bought", f'=COUNTA(Accounts!$C$4:$C${3 + N_ROWS})', "0"),
          ("Evals active", f'=COUNTIF({A},"Eval - active")', "0"),
          ("Evals passed", f'=COUNTIF({A},"Eval - passed")', "0"),
          ("Evals failed", f'=COUNTIF({A},"Eval - failed")', "0"),
          ("Funded active", f'=COUNTIF({A},"Funded - active")', "0"),
          ("Pass rate (passed / decided)", '=IF(B14+B15>0,B14/(B14+B15),"-")', PCT),
          ("Average cost per passed eval (all fees / evals passed)", '=IF(B14>0,B5/B14,"-")', USD),
          ("Tax set-aside (not tax advice)", None, None),
          ("Set-aside rate", f"={TAX}", PCT),
          ("Set aside so far", f"='Monthly P&L'!E{tr}", USD),
          ("Goal", None, None),
          ("Goal", "='Z06 goal'!B4", None),
          ("Progress", "='Z06 goal'!B8", PCT),
          ("Still needed", "='Z06 goal'!B7", USD0),
          ("Months to goal at the H2 rate", "='Z06 goal'!B11", "0"),
          ("Estimated date", "='Z06 goal'!B12", MONTH)]
    for i, (lbl, f, fmt) in enumerate(sm, 4):
        a = S.cell(row=i, column=1, value=lbl)
        if f is None:
            a.font = font(bold=True, size=11)
            a.border = THIN
            continue
        a.font = font()
        link = f.startswith("='") or f.startswith("=Settings") or f.startswith(f"={TAX}")
        fx(S.cell(row=i, column=2), f, fmt, link=link)
    S["C18"] = "Every fee (purchases, resets, subscriptions) divided by the evals passed."
    S["C18"].font = font(size=9, italic=True, color="4B5563")
    S["C10"] = "Needs this month's row on Monthly P&L (Oct 2026 - Sep 2029)."
    S["C10"].font = font(size=9, italic=True, color="4B5563")
    S.conditional_formatting.add("B7", FormulaRule(formula=["B7<0"], font=Font(name=F, color="B91C1C")))
    legend(S, 30)
    S["A36"] = "Rebuilt by tools/build_business_tracker.py (never overwrites without --force). Help: docs/BUSINESS_TRACKER.md"
    S["A36"].font = font(size=8, italic=True, color="6B7280")

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.font is None or c.font.name != F:
                    c.font = Font(name=F, size=c.font.size if c.font else 10, bold=c.font.bold if c.font else False,
                                  italic=c.font.italic if c.font else False, color=c.font.color if c.font else None)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    wb.save(out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--force", action="store_true", help="overwrite an existing tracker (wipes what was typed in it)")
    a = ap.parse_args()
    if os.path.exists(a.out) and not a.force:
        sys.exit(f"{a.out} exists: it may hold your entries. Use --force to rebuild it from scratch.")
    print("wrote", build(a.out))
