"""Three more products for prop-firm evaluation traders (night team B, 2026-11-16; owner: "find more to add"):

  risk_calculator/  Eval Risk Calculator ($12): one spreadsheet (works in the usual spreadsheet apps and free online ones):
                    room left, daily room, size that follows the stop, losses in a row before the max-loss level, a losing-streak table
                    (fixed size against "a share of what is left"), the instrument table. + LICENSE, README.
  rules_guide/      Prop Eval Rules Explained ($7): an 8-page cheat sheet (US Letter + A4): the max-loss types, daily limits, consistency,
                    payout rules, the other rules, a compare-before-you-buy worksheet and a pre-session checklist. No firm named.
  prop_bundle/      Prop Trader Bundle ($29): the eval tracker + the trader planner + these two in one zip (buyer/ holds only its README
                    and LICENSE; make_zip packs the other products' buyer files into sub-folders, plain Python).

    python -m money_machines.products.build_prop_kit --zip           the 3 upload zips (plain Python, works on the PC)
    python -m money_machines.products.build_prop_kit --build --zip   rebuild the files + covers (openpyxl, LibreOffice, Chromium, pdftoppm)

Honest rules (kit.py, tests.test_money_door): no firm, platform or index brand names, no results, no promises, the risk line, the AI line.
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from money_machines.products import kit as K  # noqa: E402

VERSION = "1.0"
RISK = "Education and organisation only, not financial advice. Trading involves substantial risk of loss. No results are shown or promised."
# tickers only (index and exchange names are trademarks): $ per 1.00 point, tick size (the exchanges' contract specs)
INSTR = [("MNQ", "micro equity index (100)", 2.0, 0.25), ("NQ", "e-mini equity index (100)", 20.0, 0.25), ("MES", "micro equity index (500)", 5.0, 0.25),
         ("ES", "e-mini equity index (500)", 50.0, 0.25), ("M2K", "micro small-cap index", 5.0, 0.1), ("RTY", "e-mini small-cap index", 50.0, 0.1),
         ("MYM", "micro blue-chip index", 0.5, 1.0), ("YM", "e-mini blue-chip index", 5.0, 1.0), ("MGC", "micro gold", 10.0, 0.1),
         ("GC", "gold", 100.0, 0.1), ("MCL", "micro crude oil", 100.0, 0.01), ("CL", "crude oil", 1000.0, 0.01)]
PER_POINT = {t: v for t, _, v, _ in INSTR}
DEFAULTS = {"start": 50000.0, "max_loss": 2000.0, "balance": 50000.0, "floor": 48000.0, "daily": 1000.0, "today": 0.0, "target": 3000.0,
            "instrument": "MNQ", "stop": 20.0, "costs": 1.5, "share": 0.10, "cap": 0}


# ------------------------------------------------------------------------------------------------ the math (= the spreadsheet formulas)
def calc(i: dict) -> dict:
    room = max(0.0, i["balance"] - i["floor"])
    daily = max(0.0, i["daily"] + min(0.0, i["today"])) if i["daily"] > 0 else room
    budget = min(room * i["share"], daily)
    per = i["stop"] * PER_POINT[i["instrument"]] + i["costs"]
    n = int(math.floor(budget / per + 1e-9)) if per > 0 else 0
    if i["cap"] > 0:
        n = min(n, int(i["cap"]))
    loss = n * per
    streak = int(math.floor(room / loss + 1e-9)) if loss > 0 else None
    status = "BREACHED" if room <= 0 else "DAILY LIMIT" if daily <= 0 else "CAREFUL" if room <= 0.25 * i["max_loss"] else "OK"
    fixed, shrink, left = [], [], room
    for k in range(1, 11):
        fixed.append(round(max(0.0, room - k * loss), 2))
        nk = int(math.floor(min(left * i["share"], daily) / per + 1e-9)) if per > 0 else 0
        if i["cap"] > 0:
            nk = min(nk, int(i["cap"]))
        left = max(0.0, left - nk * per)
        shrink.append((nk, round(left, 2)))
    return {"room": round(room, 2), "daily": round(daily, 2), "budget": round(budget, 2), "per": round(per, 2), "contracts": n,
            "loss": round(loss, 2), "streak": streak, "target_left": round(max(0.0, i["target"] - (i["balance"] - i["start"])), 2),
            "status": status, "fixed": fixed, "shrink": shrink}


# ------------------------------------------------------------------------------------------------ 1. the risk calculator
CALC = os.path.join(HERE, "risk_calculator")
CALC_XLSX = os.path.join(CALC, "buyer", "Eval_Risk_Calculator.xlsx")
INPUT_ROWS = [("start", "Account start balance ($)", "#,##0"), ("max_loss", "Max loss / drawdown allowed ($)", "#,##0"),
              ("balance", "Balance now ($)", "#,##0.00"), ("floor", "Max-loss level now ($): the balance you must stay above", "#,##0.00"),
              ("daily", "Daily loss limit ($, 0 = none)", "#,##0"), ("today", "Today's result so far ($, a loss is negative)", "#,##0.00"),
              ("target", "Profit target ($)", "#,##0"), ("instrument", "Instrument (pick from the list)", "@"), ("stop", "Stop distance (points)", "0.00"),
              ("costs", "Costs per contract, round trip ($)", "0.00"), ("share", "Risk per trade: share of the room left", "0%"),
              ("cap", "Contract cap of your rules (0 = none)", "0")]
ROW0 = 5                                                  # first input row on the Calculator sheet


def build_calculator(path: str = CALC_XLSX, inputs: dict | None = None) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    inputs = dict(DEFAULTS, **(inputs or {}))
    F = "Arial"
    title, bold, norm, small = Font(name=F, size=16, bold=True), Font(name=F, size=11, bold=True), Font(name=F, size=11), Font(name=F, size=10, color="56626A")
    blue, big = Font(name=F, size=11, color="0000FF"), Font(name=F, size=13, bold=True)
    inp, calc_f, head = PatternFill("solid", fgColor="FFF2CC"), PatternFill("solid", fgColor="F4F4F4"), PatternFill("solid", fgColor="E2ECEA")
    line = Border(bottom=Side(style="thin", color="BBBBBB"))
    wrap = Alignment(wrap_text=True, vertical="top")
    wb = Workbook()
    st = wb.active
    st.title = "Start here"
    st.column_dimensions["A"].width = 110
    for r, (t, f) in enumerate([
            (f"Eval Risk Calculator v{VERSION}: size follows the stop", title),
            ("Type your own rules and numbers in the yellow cells (blue text) on the Calculator tab. Grey cells are calculated.", norm), ("", norm),
            ("1. Room left = balance now - your max-loss level. That is the money between you and the end of the account.", norm),
            ("2. Daily room = what your daily loss limit still allows today (no limit: the room left).", norm),
            ("3. Risk budget = a share of the room (10% is a calm start), never more than the daily room.", norm),
            ("4. Contracts = risk budget / (stop in points x $ per point + costs), rounded down. A wider stop means fewer contracts.", norm),
            ("5. Losses in a row = how many full-size stops the room survives at this size.", norm),
            ("6. The Losing streak tab: the same size every time against a share of what is left after each loss.", norm), ("", norm),
            ("Check your own rule book for the max-loss type (static, end-of-day or intraday trailing) and type the level it shows today.", bold),
            ("Prices and contract values: the Instruments tab (from the exchanges' contract specifications; check yours).", norm), ("", norm),
            (RISK, small)], 1):
        c = st.cell(row=r, column=1, value=t)
        c.font, c.alignment = f, wrap

    ins = wb.create_sheet("Instruments")
    for j, (h, w) in enumerate([("Ticker", 10), ("What it is", 30), ("$ per 1.00 point", 16), ("Tick size", 10), ("$ per tick", 11)], 1):
        c = ins.cell(row=1, column=j, value=h)
        c.font, c.fill = bold, head
        ins.column_dimensions[c.column_letter].width = w
    for r, (t, what, v, tick) in enumerate(INSTR, 2):
        ins.cell(row=r, column=1, value=t).font = norm
        ins.cell(row=r, column=2, value=what).font = norm
        ins.cell(row=r, column=3, value=v).number_format = "#,##0.00"
        ins.cell(row=r, column=4, value=tick).number_format = "0.00"
        c = ins.cell(row=r, column=5, value=f"=C{r}*D{r}")
        c.number_format, c.fill = "#,##0.00", calc_f
    last = 1 + len(INSTR)

    s = wb.create_sheet("Calculator", 1)
    s.column_dimensions["A"].width = 58
    s.column_dimensions["B"].width = 18
    s.column_dimensions["C"].width = 54
    s["A1"], s["A1"].font = "Eval Risk Calculator", title
    s["A2"], s["A2"].font = "Your rules and today's numbers (yellow). The example values show how it works: type over them.", small
    s["A4"], s["A4"].font = "Your numbers", bold
    ref = {}
    for k, (key, label, fmt) in enumerate(INPUT_ROWS):
        r = ROW0 + k
        ref[key] = f"B{r}"
        s.cell(row=r, column=1, value=label).font = norm
        c = s.cell(row=r, column=2, value=inputs[key])
        c.font, c.fill, c.number_format, c.border = blue, inp, fmt, line
    dv = DataValidation(type="list", formula1=f"=Instruments!$A$2:$A${last}", allow_blank=False)
    s.add_data_validation(dv)
    dv.add(ref["instrument"])
    R = ref
    out0 = ROW0 + len(INPUT_ROWS) + 1
    s.cell(row=out0, column=1, value="What it means").font = bold
    outs = [("Room left ($)", f"=MAX(0,{R['balance']}-{R['floor']})", "#,##0.00", "between you and the end of the account"),
            ("Daily room left ($)", f"=IF({R['daily']}>0,MAX(0,{R['daily']}+MIN(0,{R['today']})),B{out0 + 1})", "#,##0.00", "what today's limit still allows"),
            ("Risk budget for the next trade ($)", f"=MIN(B{out0 + 1}*{R['share']},B{out0 + 2})", "#,##0.00", "a share of the room, capped by the daily room"),
            ("$ per point of the instrument", f"=VLOOKUP({R['instrument']},Instruments!$A$2:$C${last},3,FALSE)", "#,##0.00", "from the Instruments tab"),
            ("Risk per contract at your stop ($)", f"={R['stop']}*B{out0 + 4}+{R['costs']}", "#,##0.00", "stop x $ per point + costs"),
            ("CONTRACTS (size follows the stop)", f"=IF(B{out0 + 5}>0,IF({R['cap']}>0,MIN({R['cap']},INT(B{out0 + 3}/B{out0 + 5}+0.000000001)),INT(B{out0 + 3}/B{out0 + 5}+0.000000001)),0)", "0", "rounded down; 0 = the stop is too wide for today's budget"),
            ("Loss if the stop is hit ($)", f"=B{out0 + 6}*B{out0 + 5}", "#,##0.00", "what one full stop costs at this size"),
            ("Full-size losses in a row the room survives", f'=IF(B{out0 + 7}>0,INT(B{out0 + 1}/B{out0 + 7}+0.000000001),"-")', "0", "fewer than 5: think about a smaller share"),
            ("Profit target left ($)", f"=MAX(0,{R['target']}-({R['balance']}-{R['start']}))", "#,##0.00", "target minus profit so far"),
            ("Status", f'=IF(B{out0 + 1}<=0,"BREACHED",IF(B{out0 + 2}<=0,"DAILY LIMIT",IF(B{out0 + 1}<=0.25*{R["max_loss"]},"CAREFUL","OK")))', "@",
             "CAREFUL = a quarter of the max loss or less is left")]
    for k, (label, f, fmt, note) in enumerate(outs, 1):
        r = out0 + k
        a = s.cell(row=r, column=1, value=label)
        c = s.cell(row=r, column=2, value=f)
        a.font = bold if label.startswith(("CONTRACTS", "Status")) else norm
        c.font = big if label.startswith(("CONTRACTS", "Status")) else norm
        c.fill, c.number_format, c.border = calc_f, fmt, line
        s.cell(row=r, column=3, value=note).font = small
    s.cell(row=out0 + len(outs) + 2, column=1, value=RISK).font = small

    ls = wb.create_sheet("Losing streak", 2)
    for col, w in zip("ABCDE", (12, 26, 22, 26, 34)):
        ls.column_dimensions[col].width = w
    ls["A1"], ls["A1"].font = "Losing streak: what 10 stops in a row would do", title
    ls["A2"], ls["A2"].font = "Not a forecast: the arithmetic of losses at the size on the Calculator tab, so you can see the difference before it happens.", small
    for j, h in enumerate(["Loss #", "Room left: same size every time", "Contracts: share of what is left", "Room left: share of what is left"], 1):
        c = ls.cell(row=4, column=j, value=h)
        c.font, c.fill = bold, head
    C = "Calculator!"
    room, per, n, share, daily, cap = (f"{C}$B${out0 + 1}", f"{C}$B${out0 + 5}", f"{C}$B${out0 + 6}", f"{C}${R['share'].replace('B', 'B$')}",
                                       f"{C}$B${out0 + 2}", f"{C}${R['cap'].replace('B', 'B$')}")
    for k in range(1, 11):
        r = 4 + k
        prev = room if k == 1 else f"D{r - 1}"
        ls.cell(row=r, column=1, value=k).font = norm
        cells = [(2, f"=MAX(0,{room}-A{r}*{n}*{per})", "#,##0.00"),
                 (3, f"=IF({per}>0,IF({cap}>0,MIN({cap},INT(MIN({prev}*{share},{daily})/{per}+0.000000001)),INT(MIN({prev}*{share},{daily})/{per}+0.000000001)),0)", "0"),
                 (4, f"=MAX(0,{prev}-C{r}*{per})", "#,##0.00")]
        for col, f, fmt in cells:
            c = ls.cell(row=r, column=col, value=f)
            c.fill, c.number_format, c.font = calc_f, fmt, norm
    ls["A16"], ls["A16"].font = "Sizing from what is left shrinks each trade after a loss, so the account lasts longer; it also grows back more slowly.", small
    ls["A17"], ls["A17"].font = RISK, small
    for w in wb.worksheets:
        w.sheet_view.zoomScale = 110
    wb.active = 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path


def calc_cells() -> dict:
    """where the Calculator's outputs live (for the test that reads the cached values)"""
    out0 = ROW0 + len(INPUT_ROWS) + 1
    return {"room": f"B{out0 + 1}", "daily": f"B{out0 + 2}", "budget": f"B{out0 + 3}", "per": f"B{out0 + 5}", "contracts": f"B{out0 + 6}",
            "loss": f"B{out0 + 7}", "streak": f"B{out0 + 8}", "target_left": f"B{out0 + 9}", "status": f"B{out0 + 10}"}


CALC_LICENSE = f"""EVAL RISK CALCULATOR v{VERSION}: LICENCE

You may use and edit this spreadsheet for your own trading records on your own devices. You may not resell, share, upload or give
away the file or edited copies of it.

It does arithmetic on the numbers you type: it is not financial advice, gives no trade ideas or signals, predicts nothing and does
not promise any result. It is not affiliated with any broker, exchange, prop firm or trading platform. Always check your own rule
book: the calculator only knows what you type. Trading involves substantial risk of loss and is not suitable for everyone.

Provided as is, without warranty of any kind. If something does not work as described, message the seller through the shop where
you bought this within 14 days and we will help you or refund you.
"""
CALC_README = f"""EVAL RISK CALCULATOR v{VERSION}: QUICK START

Eval_Risk_Calculator.xlsx opens in the usual spreadsheet apps on a computer and in free online spreadsheets (import the file).

1. Start here tab: what each number means.
2. Calculator tab: type your rules and today's numbers in the yellow cells; read CONTRACTS, losses in a row and the status.
3. Losing streak tab: what 10 stops in a row would do at that size, fixed against a share of what is left.
4. Instruments tab: $ per point and per tick for 12 common futures (check your own contract specifications).

Before every session: update the balance and the max-loss level from your platform, then size every trade from its stop.
{RISK}
"""


# ------------------------------------------------------------------------------------------------ 2. the rules guide
GUIDE = os.path.join(HERE, "rules_guide")
GUIDE_SIZES = {"Letter": "Letter", "A4": "A4"}


def guide_pages() -> list:
    """(name, html body) for each page; plain words, worked examples marked Example only, no firm names"""
    ex = '<p class="ex">Example only: made-up round numbers to show the arithmetic.</p>'
    return [
        ("Cover", f"""<div class="cover"><p class="kick">Cheat sheet for evaluation traders</p><h1>Prop Eval Rules Explained</h1><div class="rule"></div>
<p class="lead">The rules that end most evaluations, in plain words, with the arithmetic and a worksheet to compare any rule book before you pay for it.</p>
<ol class="toc"><li>The max-loss level: static, end-of-day trailing, intraday trailing</li><li>Daily loss limits</li><li>Consistency rules</li>
<li>Payout rules</li><li>The other rules people miss</li><li>Compare before you buy (worksheet)</li><li>Pre-session checklist</li></ol>
<p class="small">Every firm writes its own rules and changes them. This sheet explains the common types so you can read yours; it names no firm and is not
affiliated with any. {RISK}</p></div>"""),
        ("Max-loss level", f"""<h2>1. The max-loss level</h2><p>Every evaluation has a balance you must stay above. Touch it and the account ends. The level moves
in one of three ways. Find which one your rule book uses: it decides how much room you really have.</p>
<table><tr><th>Type</th><th>How the level moves</th><th>What it means for you</th></tr>
<tr><td><b>Static</b></td><td>Fixed at start minus the max loss. Never moves.</td><td>Profit adds room. The friendliest type.</td></tr>
<tr><td><b>End-of-day trailing</b></td><td>Rises with your best <i>closing</i> balance, by the max-loss distance. Never falls.</td><td>Open profit inside the day does not move it; a strong close does.</td></tr>
<tr><td><b>Intraday trailing</b></td><td>Rises with your best balance <i>at any moment</i>, open trades included.</td><td>An open winner that comes back still raised the level. The strictest type.</td></tr>
<tr><td><b>The lock</b></td><td>Many trailing levels stop rising at a set point (often start + a small amount).</td><td>Once locked, it behaves like static.</td></tr></table>
{ex}<table><tr><th>Day</th><th>Close</th><th>Best inside the day</th><th>Static level</th><th>End-of-day level</th><th>Intraday level</th></tr>
<tr><td>Start</td><td>50,000</td><td>-</td><td>48,000</td><td>48,000</td><td>48,000</td></tr>
<tr><td>1</td><td>50,600</td><td>51,000</td><td>48,000</td><td>48,600</td><td>49,000</td></tr>
<tr><td>2</td><td>50,200</td><td>50,700</td><td>48,000</td><td>48,600</td><td>49,000</td></tr></table>
<p>Room left on day 2 at the close: static 2,200, end-of-day 1,600, intraday 1,200. <b>Same trades, very different room.</b></p>
<p class="tip">Rule of thumb: type the level your platform shows today into your tracker before the first trade, not the number you remember.</p>"""),
        ("Daily loss limit", f"""<h2>2. Daily loss limits</h2><p>Many rule books add a limit for one day. Read three things:</p>
<ul><li><b>Hard or soft.</b> A hard limit ends the account like the max loss. A soft limit only stops trading for the rest of the day.</li>
<li><b>What counts.</b> Closed trades only, or open trades too (equity). With equity, an open loser can hit the limit before you close it.</li>
<li><b>From where.</b> From the day's starting balance, or from the day's best balance. From the best balance means a morning profit raises the bar.</li></ul>
{ex}<p>Daily limit 1,000 from the day's start. You are -400 after two trades. Daily room left: 600. A trade that risks 700 could end the day (soft) or the
account (hard), even if the max-loss level is far away.</p>
<p class="tip">Size every trade from the smaller of the two rooms: the max-loss room and the daily room.</p>
<h3>Size follows the stop</h3><p>Contracts = risk budget / (stop in points x $ per point + costs), rounded down. A wider stop means fewer contracts, never a
wider loss.</p>{ex}<p>Budget 200, stop 20 points on a contract worth 2 per point, costs 1.50: 200 / (40 + 1.50) = 4.8, so 4 contracts, about 166 at risk.</p>"""),
        ("Consistency", f"""<h2>3. Consistency rules</h2><p>Some rule books cap how much of your profit one day may be. Usually: <b>best day / total profit
&le; a set share</b> (often 30%, 40% or 50%). Some apply it to passing, some only to payouts, some to both.</p>
<p>When the best day is too big, the answer is not a breach but more profitable days. The profit you still need:</p>
<p class="formula">more profit needed = best day / share - total profit</p>
{ex}<p>Total profit 2,000, best day 1,200, share 40%. 1,200 / 0.40 = 3,000, so 1,000 more profit is needed, made on other days, before the rule is met.</p>
<ul><li>Read whether the rule uses the whole evaluation or only the current payout cycle.</li><li>Read whether losing days count against the total.</li>
<li>A cap on one day's profit (some rules) is different: it limits the day, not the share.</li></ul>
<p class="tip">One big day early is a reason to trade smaller, not bigger: the rule needs many ordinary days.</p>"""),
        ("Payouts", f"""<h2>4. Payout rules (after you pass)</h2><table><tr><th>Rule</th><th>What to look for</th></tr>
<tr><td>Buffer</td><td>Profit that must stay in the account above a set level before anything can be withdrawn.</td></tr>
<tr><td>Minimum days</td><td>Traded days (sometimes profitable days of a minimum size) needed in each payout cycle.</td></tr>
<tr><td>First request</td><td>A waiting time after the first funded trade, or a number of days.</td></tr>
<tr><td>Minimum and maximum</td><td>The smallest and largest request per cycle; the maximum often rises with later payouts.</td></tr>
<tr><td>Split</td><td>Your share of what is withdrawn (for example 80% or 90%).</td></tr>
<tr><td>After a payout</td><td>Many trailing levels move up or lock after the first withdrawal: your room changes.</td></tr>
<tr><td>Number of payouts</td><td>Some programmes move you to another account type after a set number.</td></tr></table>
{ex}<p>Buffer 2,100 above the start, request minimum 500, split 80%. At 3,600 profit you could ask 1,500: about 1,200 reaches you before fees and taxes.</p>
<p class="tip">Write down the date you can first ask and the balance you need. Plan the request; do not chase it with bigger size.</p>"""),
        ("Other rules", f"""<h2>5. The other rules people miss</h2><ul>
<li><b>Contract caps</b> and scaling: a maximum size, sometimes lower until the profit grows.</li>
<li><b>News windows</b>: no trades, or no open positions, around listed reports.</li>
<li><b>Flat by a time</b>: every position closed before a set time; holding past it can end the account.</li>
<li><b>Inactivity</b>: an account with no trade for a set number of days may be closed.</li>
<li><b>Hedging across accounts</b>: long on one account and short on another is often banned, also across firms.</li>
<li><b>Automation and copying</b>: allowed, limited or banned; trade copiers between your own accounts are a separate line.</li>
<li><b>Fees</b>: one-time or monthly, activation fees after passing, reset prices, data fees.</li>
<li><b>Platform and data</b>: which platforms and data feeds are allowed, and who pays for them.</li>
<li><b>Overnight and weekends</b>: often not allowed at all.</li>
<li><b>Rule changes</b>: rules can change while you trade; save a copy of the rule page the day you buy.</li></ul>
<p class="tip">If a rule is unclear, ask support in writing and keep the answer.</p>"""),
        ("Compare worksheet", """<h2>6. Compare before you buy</h2><p class="small">Fill one column per offer from its own rule pages. Price is what you would really pay, with any code.</p>
<table class="ws"><tr><th>Rule</th><th>Offer A</th><th>Offer B</th><th>Offer C</th></tr>""" + "".join(
            f"<tr><td>{r}</td><td></td><td></td><td></td></tr>" for r in (
                "Price (one-time / monthly)", "Activation or reset fee", "Account size", "Profit target", "Max loss and its type", "Lock level",
                "Daily loss limit (hard / soft, closed / equity)", "Consistency rule (pass / payout)", "Minimum days", "Contract cap",
                "News and flat-by rules", "Automation / copying allowed", "Buffer before payouts", "First request after", "Request min / max",
                "Split to you", "Payouts before another account type", "Platforms and data")) + "</table>"),
        ("Checklist", f"""<h2>7. Pre-session checklist</h2><ul class="ck">""" + "".join(f"<li>{x}</li>" for x in (
            "Balance and max-loss level typed from the platform (not from memory)", "Room left and daily room written down",
            "Risk budget for the first trade: a share of the room, never more than the daily room", "Contracts worked out from the stop",
            "News times checked; flat-by time set as an alarm", "If-then plans read: after two losses, at the daily room, when rushed",
            "Size for the day written before the first trade, not changed after a loss", "A stop on every order, placed with the entry")) + """</ul>
<h3>If-then plans</h3><table class="ws"><tr><th>If</th><th>Then</th></tr>""" + "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in (
            ("Two losses in a row", "Stop for the day or halve the size (decide now, not then)"),
            ("Daily room below one full stop", "No new trades today"), ("A big winning day", "Next day: normal size, the consistency rule needs ordinary days"),
            ("I feel rushed or angry", "Ten minutes away from the screen before any order"), ("", ""), ("", ""))) + f"""</table>
<p class="small" style="margin-top:14px">{RISK} Made with the help of AI tools; written, checked and supported by me.</p>"""),
    ]


def guide_html(size: str) -> str:
    w, h = ("8.5in", "11in") if size == "Letter" else ("210mm", "297mm")
    css = f"""@page{{size:{w} {h};margin:0}}*{{box-sizing:border-box}}body{{margin:0;font-family:{K.SANS};color:#1d1a16;font-size:11pt;line-height:1.42}}
.pg{{width:{w};height:{h};padding:0.6in 0.65in;page-break-after:always;position:relative;overflow:hidden}}.pg:last-child{{page-break-after:auto}}
h1{{font-family:{K.SERIF};font-size:38pt;line-height:1.05;margin:0 0 14px}}h2{{font-family:{K.SERIF};font-size:22pt;margin:0 0 10px;color:#14110e}}
h3{{font-family:{K.SERIF};font-size:14pt;margin:16px 0 6px}}.kick{{color:#8a6a1e;font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:10pt}}
.rule{{width:90px;height:6px;background:#c8a24a;border-radius:3px;margin:8px 0 16px}}.lead{{font-size:14pt;color:#3d362d}}
.cover{{margin-top:1.4in}}.toc li{{margin:6px 0;font-size:12pt}}table{{border-collapse:collapse;width:100%;margin:10px 0;font-size:9.6pt}}
th,td{{border:1px solid #cfc6b6;padding:6px 7px;text-align:left;vertical-align:top}}th{{background:#efe8da}}.ws td{{height:26px}}
.ex{{display:inline-block;background:#fff6df;border:1px solid #e5cf93;border-radius:6px;padding:3px 9px;font-size:9pt;color:#6b5414;margin:8px 0 2px}}
.tip{{border-left:5px solid #c8a24a;background:#f7f2e8;padding:8px 12px;margin-top:12px}}.formula{{font-family:{K.SERIF};font-size:15pt;text-align:center;margin:12px 0}}
.small{{font-size:9pt;color:#5a5247}}ul.ck{{list-style:none;padding-left:0}}ul.ck li{{padding:7px 0 7px 34px;position:relative;border-bottom:1px solid #e3dccd}}
ul.ck li:before{{content:"";position:absolute;left:4px;top:7px;width:18px;height:18px;border:2px solid #8a6a1e;border-radius:4px}}
.foot{{position:absolute;bottom:0.35in;left:0.65in;right:0.65in;font-size:8pt;color:#8a8070;display:flex;justify-content:space-between}}"""
    pages = guide_pages()
    body = "".join(f'<section class="pg">{b}<div class="foot"><span>Prop Eval Rules Explained v{VERSION}</span><span>{i + 1} / {len(pages)}</span></div></section>'
                   for i, (_, b) in enumerate(pages))
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"


GUIDE_LICENSE = f"""PROP EVAL RULES EXPLAINED v{VERSION}: LICENCE

You may print and use this guide for yourself, as often as you like, on your own devices. You may not resell, share, upload or give
away the files or edited copies of them.

It explains common rule types in plain words: it is not financial or legal advice, names and represents no firm, and is not
affiliated with any broker, exchange, prop firm or trading platform. Rules differ and change: your own rule book always wins.
Trading involves substantial risk of loss and is not suitable for everyone.

Provided as is, without warranty of any kind. If something does not work as described, message the seller through the shop where
you bought this within 14 days and we will help you or refund you.
"""
GUIDE_README = f"""PROP EVAL RULES EXPLAINED v{VERSION}: QUICK START

Prop_Eval_Rules_Explained_Letter.pdf   US Letter, 8 pages
Prop_Eval_Rules_Explained_A4.pdf       A4, 8 pages

Read pages 2-6 once with your own rule book open. Print page 7 (the compare worksheet) before you buy an evaluation, and page 8
(the pre-session checklist) for your desk. {RISK}
"""


# ------------------------------------------------------------------------------------------------ 3. the bundle
BUNDLE = os.path.join(HERE, "prop_bundle")
BUNDLE_PARTS = [("1_Prop_Eval_Tracker", os.path.join(HERE, "eval_tracker"), ["Prop_Eval_Tracker.xlsx", "prop_eval_tracker.html", "How_to_use.pdf", "README.txt"]),
                ("2_Trader_Routine_Planner", os.path.join(HERE, "trader_planner", "buyer"), None),
                ("3_Eval_Risk_Calculator", os.path.join(CALC, "buyer"), None),
                ("4_Prop_Eval_Rules_Explained", os.path.join(GUIDE, "buyer"), None)]
BUNDLE_LICENSE = f"""PROP TRADER BUNDLE v{VERSION}: LICENCE

The four products in this bundle are for your own use on your own devices. You may not resell, share, upload or give away the files
or edited copies of them. Each folder keeps its own README with the details.

They organise your own rules, numbers and routine: not financial advice, no trade ideas, signals or predictions, no promised result.
Not affiliated with any broker, exchange, prop firm or trading platform. Trading involves substantial risk of loss and is not suitable
for everyone.

Provided as is, without warranty of any kind. If something does not work as described, message the seller through the shop where
you bought this within 14 days and we will help you or refund you.
"""
BUNDLE_README = f"""PROP TRADER BUNDLE v{VERSION}: WHAT IS INSIDE

1_Prop_Eval_Tracker            your evaluation's drawdown left, daily limit, consistency and size (spreadsheet + offline web page)
2_Trader_Routine_Planner       16 printable pages (Letter + A4) + a spreadsheet journal for your routine
3_Eval_Risk_Calculator         size follows the stop, losses in a row, a losing-streak table
4_Prop_Eval_Rules_Explained    the rule types in plain words, a compare-before-you-buy worksheet, a pre-session checklist

Start with 4 (read your rule book with it), then 1 every day, 3 before each session and 2 for your routine.
{RISK}
"""


def bundle_files() -> list:
    """(arcname inside the top folder, source path) for every file of the bundle zip"""
    out = [("LICENSE.txt", os.path.join(BUNDLE, "buyer", "LICENSE.txt")), ("README.txt", os.path.join(BUNDLE, "buyer", "README.txt"))]
    for sub, src, only in BUNDLE_PARTS:
        names = only if only else K.buyer_files(src)
        out += [(f"{sub}/{n}", os.path.join(src, n)) for n in names]
    lic = os.path.join(HERE, "eval_tracker", "LICENSE.txt")
    out.append(("1_Prop_Eval_Tracker/LICENSE.txt", lic))
    return sorted(out)


# ------------------------------------------------------------------------------------------------ listings
COMMON_RULES = ["Never show profits, P&L screenshots, win rates or 'pass your evaluation' wording in the listing, pictures or tags.",
                "No firm, broker, exchange, index or platform names (tickers only); keep the risk line at the end of the description.",
                "Gumroad reviews trading-related products more closely: keep the education-only wording.",
                "Etsy: 'I did', digital download; the description says AI tools helped."]
REFUND = "Digital download: files can't be returned, but if something does not work as described, message me within 14 days and I will fix it or refund you."

LISTINGS = {
    "calc": {
        "id": "eval-risk-calculator", "version": VERSION, "price_usd": 12, "top": "Eval-Risk-Calculator", "zip": f"eval_risk_calculator_v{VERSION}.zip",
        "title": "Prop Firm Eval Risk Calculator Spreadsheet: Position Size From Your Stop, Drawdown Room, Daily Limit, Losing Streak Table (Futures)",
        "short": "Size every trade from its stop and your room left. A spreadsheet for futures evaluation traders: contracts, losses in a row, daily room.",
        "description": [
            "The fastest way to end an evaluation is a size that the room left can't carry. This spreadsheet does the arithmetic before the trade.",
            "WHAT YOU GET",
            "- Calculator: type your balance, max-loss level, daily limit, stop and instrument; read the contracts, the loss if stopped and how many stops in a row the room survives",
            "- Daily room: never risk more than today's limit still allows",
            "- Losing streak table: 10 losses at a fixed size against sizing from what is left, side by side",
            "- Instruments: $ per point and per tick for 12 common futures (micro and full size)",
            "- A status line: OK, CAREFUL, DAILY LIMIT, BREACHED",
            "HOW IT HELPS",
            "- Size follows the stop: a wider stop gives fewer contracts, never a bigger loss",
            "- Works with static, end-of-day trailing and intraday trailing rules: you type the level your platform shows",
            "WHAT IT IS NOT",
            "- No signals, no strategy, no advice. It does arithmetic on your own numbers and promises no results.",
            "- Not affiliated with any broker, exchange, prop firm or trading platform.",
            "Pairs with my Prop Eval Tracker and the Prop Eval Rules Explained cheat sheet (or get all of them in the Prop Trader Bundle).",
            "Instant download. Made with the help of AI tools; designed, checked and supported by me.",
            "Trading involves substantial risk of loss and is not suitable for everyone. No results are shown or promised."],
        "tags_etsy": ["position size", "risk calculator", "prop firm", "futures trading", "trading spreadsheet", "day trading", "drawdown tracker",
                      "risk management", "trading tools", "funded trader", "eval calculator", "trader gift", "trading template"],
        "faq": [["Is this financial advice?", "No. It does arithmetic on the numbers you type. It gives no trade ideas and makes no predictions."],
                ["Which rules does it work with?", "Any: you type your max loss, the level your platform shows today and your daily limit."],
                ["Which markets?", "Futures with a fixed $ per point; 12 common contracts are listed and you can add your own."],
                ["What do I need?", "Any spreadsheet app that opens .xlsx, including free online ones (import the file)."],
                ["Will it help me pass?", "No tool can promise that. It shows the size your own numbers allow; results depend on you and the market."],
                ["Does it connect to my platform?", "No. You type your numbers. Nothing is sent anywhere."]],
        "refund": REFUND,
        "price_reasoning": ("$12: a forex position-size calculator spreadsheet sells for about GBP 15 on Gumroad and prop-firm rule-math spreadsheets are sold on "
                            "Payhip, while free single-purpose web calculators exist. Ours adds the daily room, the losing-streak table and the status for "
                            "futures evaluations, in one file the buyer owns, so $12 is fair for a new shop; $9 if views don't turn into sales."),
        "comparables": [
            {"what": "Excel position size calculator (editable spreadsheet)", "price": "GBP 15", "where": "Gumroad", "url": "https://unbiasedtrading.gumroad.com/l/hnzAG", "seen": "2026-11-16"},
            {"what": "Prop-firm rule math spreadsheet + documentation (daily loss, drawdown models)", "price": "price not shown in the search", "where": "Payhip", "url": "https://payhip.com/b/dQkV3", "seen": "2026-11-16"},
            {"what": "Prop firm position size calculator (web page)", "price": "free", "where": "a trading-journal site", "url": "https://onetradejournal.com/tools/prop-firm-position-size-calculator", "seen": "2026-11-16"},
            {"what": "Position sizing worksheet template", "price": "free", "where": "a journal-template site", "url": "https://journalplus.co/templates/position-sizing-worksheet", "seen": "2026-11-16"}],
        "image_notes": ["the calculator", "the losing streak table", "what it answers", "square 1", "square 2", "square 3"],
        "rules": COMMON_RULES},
    "guide": {
        "id": "eval-rules-explained", "version": VERSION, "price_usd": 7, "top": "Prop-Eval-Rules-Explained", "zip": f"prop_eval_rules_explained_v{VERSION}.zip",
        "title": "Prop Firm Evaluation Rules Explained Cheat Sheet PDF: Trailing Drawdown, Daily Loss, Consistency, Payouts + Compare Worksheet",
        "short": "The rules that end most evaluations, in plain words: trailing drawdown types, daily limits, consistency, payouts and a compare worksheet.",
        "description": [
            "Static, end-of-day trailing or intraday trailing? Hard or soft daily limit? A consistency rule on the pass or on the payout? These decide how much room you really have.",
            "WHAT YOU GET",
            "- 8 printable pages in US Letter and A4",
            "- The three max-loss types and the lock, with one worked table showing how the same trades leave different room",
            "- Daily loss limits: hard or soft, closed or open trades, from the start or from the best balance; size follows the stop",
            "- Consistency rules with the one formula for the profit you still need",
            "- Payout rules: buffer, minimum days, first request, minimum and maximum, split, what changes after a payout",
            "- The rules people miss: caps, news windows, flat-by times, inactivity, hedging, automation, fees",
            "- A compare-before-you-buy worksheet and a pre-session checklist with if-then plans",
            "WHAT IT IS NOT",
            "- It names no firm and is not affiliated with any broker, exchange, prop firm or trading platform. Rules change: your own rule book always wins.",
            "- No signals, no strategy, no advice; examples use made-up round numbers and are marked Example only.",
            "Instant download. Made with the help of AI tools; written, checked and supported by me.",
            "Trading involves substantial risk of loss and is not suitable for everyone. No results are shown or promised."],
        "tags_etsy": ["prop firm", "trading cheat sheet", "trailing drawdown", "futures trading", "day trading", "trading guide pdf", "funded trader",
                      "risk management", "trading checklist", "trader printable", "evaluation rules", "trading education", "consistency rule"],
        "faq": [["Which firms does it cover?", "None by name. It explains the common rule types so you can read any rule book, and has a worksheet to fill from yours."],
                ["Is it up to date?", "The rule types are general; numbers change by firm and over time, so the worksheet is filled from your own rule pages."],
                ["Is this financial advice?", "No. It is education about rule types, with made-up examples. It gives no trade ideas."],
                ["Which paper sizes?", "US Letter and A4. Print at 100% (actual size)."],
                ["Will it help me pass?", "No guide can promise that. It helps you understand the rules before you trade them."],
                ["Is there a spreadsheet?", "Not in this one: the Eval Risk Calculator and the Prop Eval Tracker are the spreadsheets (all four are in the Prop Trader Bundle)."]],
        "refund": REFUND,
        "price_reasoning": ("$7: plain-words drawdown explanations are free on many blogs, and a firm-specific playbook with a cheat sheet sells for about $27. "
                            "Ours is firm-neutral, printable, with a compare worksheet and a checklist, so a low impulse price fits; it is mostly the door "
                            "to the calculator, the tracker and the bundle."),
        "comparables": [
            {"what": "12-page playbook + cheat sheet for one firm's evaluations (PDF)", "price": "$27", "where": "a sales page", "url": "https://reaver1000.github.io/prop-firm-playbook/", "seen": "2026-11-16"},
            {"what": "Trailing drawdown explained (blog article)", "price": "free", "where": "a trading-journal blog", "url": "https://www.tradezella.com/blog/trailing-drawdown", "seen": "2026-11-16"},
            {"what": "Drawdown types explained (guide page)", "price": "free", "where": "a prop-firm comparison site", "url": "https://propfirmmap.com/learn/drawdown-types-explained", "seen": "2026-11-16"},
            {"what": "Trailing drawdown survival guide (article)", "price": "free", "where": "a trading-software site", "url": "https://crosstrade.io/learn/risk-management/trailing-drawdown-survival-guide", "seen": "2026-11-16"}],
        "image_notes": ["the pages", "the max-loss table", "the compare worksheet", "square 1", "square 2", "square 3"],
        "rules": COMMON_RULES},
    "bundle": {
        "id": "prop-trader-bundle", "version": VERSION, "price_usd": 29, "top": "Prop-Trader-Bundle", "zip": f"prop_trader_bundle_v{VERSION}.zip",
        "title": "Prop Firm Trader Bundle: Eval Tracker + Risk Calculator + Rules Cheat Sheet + Daily Routine Planner (Spreadsheets + Printable PDF)",
        "short": "Four tools for evaluation traders in one download: track the rules, size from the stop, read the rule book, keep a routine.",
        "description": [
            "Everything an evaluation trader needs on paper and in a spreadsheet, in one download, for less than the four separately.",
            "WHAT YOU GET",
            "- Prop Eval Tracker: drawdown left, daily limit, consistency, target, the next trade's size (spreadsheet + offline web page)",
            "- Eval Risk Calculator: size follows the stop, losses in a row, a losing-streak table",
            "- Prop Eval Rules Explained: the rule types in plain words, a compare-before-you-buy worksheet, a pre-session checklist (Letter + A4)",
            "- Trader's Daily Routine Planner: 16 printable pages (Letter + A4) + a spreadsheet journal",
            "WHAT IT IS NOT",
            "- No signals, no strategy, no advice; it organises your own rules and numbers and promises no results.",
            "- Not affiliated with any broker, exchange, prop firm or trading platform.",
            "Instant download. Made with the help of AI tools; designed, checked and supported by me.",
            "Trading involves substantial risk of loss and is not suitable for everyone. No results are shown or promised."],
        "tags_etsy": ["prop firm", "trading bundle", "trading journal", "position size", "futures trading", "day trading", "trader planner",
                      "drawdown tracker", "risk management", "funded trader", "trading spreadsheet", "trader gift", "trading printable"],
        "faq": [["What is inside?", "Four products: the Prop Eval Tracker, the Eval Risk Calculator, Prop Eval Rules Explained and the Trader's Daily Routine Planner."],
                ["Is this financial advice?", "No. The tools organise your own rules and numbers. They give no trade ideas and make no predictions."],
                ["What do I need?", "Any spreadsheet app that opens .xlsx (free online ones too), a browser for the offline page, a PDF reader for the printables."],
                ["Which rules does it work with?", "Any: you type your own rule book's numbers."],
                ["Will it help me pass?", "No tool can promise that. It helps you follow your own rules; results depend on you and the market."],
                ["Can I buy the parts alone?", "Yes, each is sold separately; the bundle costs less than the four together."]],
        "refund": REFUND,
        "price_reasoning": ("$29 for $50 of parts (17 + 12 + 7 + 14): bundles of a journal and a prop tracker list at about EUR 39, single prop trackers at about "
                            "$17-22 and printable workbooks up to $29.99. A bundle under $30 is the natural upsell from the $7 cheat sheet; try $25 if it does not sell."),
        "comparables": [
            {"what": "Prop firm challenge tracker spreadsheet", "price": "about $16.68 (sale from $22.24)", "where": "Etsy", "url": "https://www.etsy.com/listing/4606983180", "seen": "2026-11-14"},
            {"what": "Printable trading workbook: daily, weekly, monthly review", "price": "$29.99", "where": "Payhip", "url": "https://payhip.com/b/3sMFc", "seen": "2026-11-14"},
            {"what": "Excel position size calculator", "price": "GBP 15", "where": "Gumroad", "url": "https://unbiasedtrading.gumroad.com/l/hnzAG", "seen": "2026-11-16"},
            {"what": "Trading journal spreadsheets (range across listings, most $9-25)", "price": "about $1 to $80", "where": "Etsy", "url": "https://www.etsy.com/listing/1461681856", "seen": "2026-11-14"}],
        "image_notes": ["the four tools", "what is inside", "the price of the parts", "square 1", "square 2", "square 3"],
        "rules": COMMON_RULES},
}
DIRS = {"calc": CALC, "guide": GUIDE, "bundle": BUNDLE}


# ------------------------------------------------------------------------------------------------ zips (plain Python)
def make_zip(which: str, out: str | None = None) -> str:
    L = LISTINGS[which]
    if which != "bundle":
        return K.make_zip(os.path.join(DIRS[which], "buyer"), L["top"], L["zip"], out)
    out = out or K.OUT
    os.makedirs(out, exist_ok=True)
    z = os.path.join(out, L["zip"])
    with zipfile.ZipFile(z + ".tmp", "w", zipfile.ZIP_DEFLATED) as zf:
        for arc, src in bundle_files():
            zi = zipfile.ZipInfo(f"{L['top']}/{arc}", date_time=K.ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(src, "rb") as fh:
                zf.writestr(zi, fh.read())
    os.replace(z + ".tmp", z)
    return z


def zips(out: str | None = None) -> list:
    return [make_zip(w, out) for w in ("calc", "guide", "bundle")]


# ------------------------------------------------------------------------------------------------ pictures (build machine only)
def _png_b64(png: bytes, crop: float | None = None) -> str:
    from io import BytesIO

    from PIL import Image
    im = Image.open(BytesIO(png)).convert("RGB")
    if crop:
        im = im.crop((0, 0, im.width, int(im.width * crop)))
    o = BytesIO()
    im.save(o, "JPEG", quality=88)
    return K.b64(o.getvalue())


def covers(br, shop: str, chip: str, title: str, bullets: list, pics: list, foot: str, big_text: str) -> list:
    """3 wide + 3 square covers: 1 = title, bullets and fanned pages; 2 = the pictures in a row; 3 = one big line + one picture"""
    done = []
    bg, ink, soft, acc = "#14110e", "#f3ece0", "#cfc4b2", "#c8a24a"
    for name, w, h in K.COVERS:
        sq, k, n = w == h, w / 1280, name.split("_")[1][0]
        css = K.cover_css(w, h, bg=bg, ink=ink, soft=soft, accent=acc) + f"""
.pad{{position:absolute;inset:0;padding:{int(60 * k)}px}}.kick{{font-size:{int(21 * k)}px;padding:{int(7 * k)}px {int(18 * k)}px;margin-bottom:{int(22 * k)}px}}
h1{{font-size:{int((78 if sq else 54) * k)}px}}ul.checks li{{font-size:{int((30 if sq else 22) * k)}px;margin:{int(11 * k)}px 0}}
.foot{{position:absolute;left:{int(60 * k)}px;right:{int(60 * k)}px;bottom:{int(22 * k)}px;font-size:{int((18 if sq else 15) * k)}px;color:#a89c88}}
.pg{{position:absolute;background:#fff;border-radius:{max(3, int(5 * k))}px;box-shadow:0 {int(18 * k)}px {int(44 * k)}px rgba(0,0,0,.55)}}"""
        text = (f'<span class="chip kick">{chip}</span><h1>{title}</h1><div class="rule" style="margin-top:{int(22 * k)}px"></div>'
                f'<ul class="checks" style="margin-top:{int(16 * k)}px">' + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
        if n == "1":
            if sq:
                body = f'<div class="pad">{text}</div>'
                pos = [(760, 640, 7, 400), (600, 680, 1, 400), (440, 730, -6, 400)][:len(pics)]
            else:
                body = f'<div class="pad" style="width:{int(640 * k)}px">{text}</div>'
                pos = [(930, 110, 7, 300), (800, 150, 1, 300), (680, 200, -6, 300)][:len(pics)]
            body += "".join(f'<img class="pg" src="{pics[i]}" style="left:{int(x * k)}px;top:{int(y * k)}px;width:{int(pw * k)}px;transform:rotate({r}deg)">'
                            for i, (x, y, r, pw) in enumerate(pos))
        elif n == "2":
            tw = int((380 if sq else 360) * k) if len(pics) > 2 else int((560 if sq else 520) * k)
            cells = "".join(f'<img src="{p}" style="width:{tw}px;border-radius:6px;box-shadow:0 12px 30px rgba(0,0,0,.45);background:#fff">' for p in pics[:3])
            body = (f'<div class="pad" style="text-align:center"><h1 style="font-size:{int((66 if sq else 44) * k)}px">{big_text}</h1></div>'
                    f'<div style="position:absolute;top:{int((300 if sq else 170) * k)}px;left:0;right:0;display:flex;flex-wrap:wrap;gap:{int(24 * k)}px;justify-content:center;align-items:flex-start">{cells}</div>')
        else:
            jw = int((900 if sq else 640) * k)
            pic = K.window(pics[0], jw)
            if sq:
                body = f'<div class="pad">{text}</div><div style="position:absolute;left:{int(190 * k)}px;top:{int(600 * k)}px">{pic}</div>'
            else:
                body = f'<div class="pad" style="width:{int(560 * k)}px">{text}</div><div style="position:absolute;left:{int(600 * k)}px;top:{int(110 * k)}px">{pic}</div>'
        body += f'<div class="foot">{foot}</div>'
        html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"
        done.append(K.shoot(br, html, w, h, os.path.join(shop, name), quality=80 if sq else 84))
    return done


def build(images: bool = True, log=print) -> list:
    done = []
    os.makedirs(os.path.join(CALC, "buyer"), exist_ok=True)
    p = build_calculator()
    log(K.recalc_xlsx(p))
    done.append(K.clean_ooxml(p, "Eval Risk Calculator"))
    done.append(K.write_text(os.path.join(CALC, "buyer", "LICENSE.txt"), CALC_LICENSE))
    done.append(K.write_text(os.path.join(CALC, "buyer", "README.txt"), CALC_README))
    os.makedirs(os.path.join(GUIDE, "buyer"), exist_ok=True)
    done.append(K.write_text(os.path.join(GUIDE, "buyer", "LICENSE.txt"), GUIDE_LICENSE))
    done.append(K.write_text(os.path.join(GUIDE, "buyer", "README.txt"), GUIDE_README))
    os.makedirs(os.path.join(BUNDLE, "buyer"), exist_ok=True)
    done.append(K.write_text(os.path.join(BUNDLE, "buyer", "LICENSE.txt"), BUNDLE_LICENSE))
    done.append(K.write_text(os.path.join(BUNDLE, "buyer", "README.txt"), BUNDLE_README))
    if images:
        from playwright.sync_api import sync_playwright

        from money_machines.products.build_agency_kit import soffice_pdf
        tmp = tempfile.mkdtemp(prefix="nb_prop_")
        try:
            with sync_playwright() as pw:
                br = K.chromium(pw)
                for size in GUIDE_SIZES:
                    done.append(K.html_pdf(br, guide_html(size), os.path.join(GUIDE, "buyer", f"Prop_Eval_Rules_Explained_{size}.pdf"), size,
                                           f"Prop Eval Rules Explained ({size})"))
                gp = [open(x, "rb").read() for x in K.pdf_pages_png(os.path.join(GUIDE, "buyer", "Prop_Eval_Rules_Explained_Letter.pdf"), os.path.join(tmp, "g"), dpi=70)]
                cp = [open(x, "rb").read() for x in K.pdf_pages_png(soffice_pdf(CALC_XLSX, tmp), os.path.join(tmp, "c"), dpi=90)]
                g = [_png_b64(gp[i]) for i in (1, 6, 7)]
                c = [_png_b64(x, crop=0.62) for x in cp[:3]]
                tracker = os.path.join(HERE, "eval_tracker", "app_screenshot.jpg")
                tr = K.b64(open(tracker, "rb").read()) if os.path.isfile(tracker) else c[0]
                plan_cover = os.path.join(HERE, "trader_planner", "shop", "cover_2.jpg")
                pl = K.b64(open(plan_cover, "rb").read()) if os.path.isfile(plan_cover) else g[0]
                foot = "Arithmetic on your own numbers: no signals, no predictions, no results promised. Trading involves substantial risk of loss."
                done += covers(br, os.path.join(CALC, "shop"), "Spreadsheet calculator", "Eval Risk Calculator",
                               ["Size follows the stop", "Room left and daily room", "Losses in a row it survives", "A 10-loss streak table"],
                               [c[1] if len(c) > 1 else c[0], c[0]], foot, "Know the size before the trade")
                done += covers(br, os.path.join(GUIDE, "shop"), "8-page cheat sheet, Letter + A4", "Prop Eval Rules Explained",
                               ["Trailing drawdown types", "Daily limits and consistency", "Payout rules", "Compare-before-you-buy worksheet"],
                               g, "Education only: no firm named, no advice, no results promised. Your own rule book always wins.", "Read any rule book in 10 minutes")
                done += covers(br, os.path.join(BUNDLE, "shop"), "4 tools in one download", "Prop Trader Bundle",
                               ["Eval tracker", "Risk calculator", "Rules cheat sheet", "Daily routine planner"],
                               [tr, c[0], g[0], pl], foot, "Track. Size. Read the rules. Repeat.")
                br.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    for which, d in DIRS.items():
        files = [a for a, _ in bundle_files()] if which == "bundle" else K.buyer_files(os.path.join(d, "buyer"))
        done += K.write_listing(os.path.join(d, "shop"), dict(LISTINGS[which], files=files))
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.products.build_prop_kit")
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args(argv)
    if a.build or not a.zip:
        for p in build(images=not a.no_images):
            print(p)
    if a.zip:
        for z in zips():
            print(z)
    return 0


if __name__ == "__main__":
    sys.exit(main())
