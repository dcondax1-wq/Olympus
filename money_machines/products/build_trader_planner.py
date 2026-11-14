"""Build the TRADER'S DAILY ROUTINE PLANNER (team D2, 2026-11-14): a 16-page printable planner (US Letter and A4 PDFs) and a
spreadsheet journal (daily log, routine ticks, rules and rule breaks, weekly review, a process dashboard). Process only: no
signals, no predictions, no performance claims; the example rows show no profit or loss.

    python -m money_machines.products.build_trader_planner --zip    # the owner: pack the committed files (plain Python)
                                                                    #   -> money_machines/out/products/trader_routine_planner_v1.0.zip
    python -m money_machines.products.build_trader_planner          # rebuild (openpyxl + LibreOffice for the journal; Chromium for the
                                                                    #   PDFs and covers: run under the browser lock)
Pairs with the Prop Eval Tracker (money_machines/products/eval_tracker) for the Eval Journal audience.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import sys
import tempfile

from money_machines.products import kit as K

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.join(HERE, "trader_planner")
BUYER, SHOP = os.path.join(PROD, "buyer"), os.path.join(PROD, "shop")
VERSION = "1.0"
TOP = "Trader-Daily-Routine-Planner"
ZIP = f"trader_routine_planner_v{VERSION}.zip"
JOURNAL = os.path.join(BUYER, "Trader_Journal.xlsx")
SIZES = {"Letter": (215.9, 279.4), "A4": (210.0, 297.0)}
RISK = "Education and organisation only, not financial advice. Trading involves substantial risk of loss. This planner gives no trade ideas and promises no results."
INK, ACC, SOFTF, LINE, MUTED = "#1d2329", "#2f6b66", "#eef4f3", "#c3cfcd", "#56626a"


# ------------------------------------------------------------------------------------------------ the printable pages
def rows(n: int, cls: str = "ln") -> str:
    return "".join(f'<div class="{cls}"></div>' for _ in range(n))


def boxrow(labels: list) -> str:
    return '<div class="boxes">' + "".join(f'<div class="bx"><span>{x}</span></div>' for x in labels) + "</div>"


def scale(label: str, n: int = 5) -> str:
    return f'<div class="scale"><b>{label}</b>' + "".join(f"<i>{i}</i>" for i in range(1, n + 1)) + "</div>"


def checks(items: list, cls: str = "ck") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


def table(head: list, n: int, widths: list | None = None, cls: str = "tb") -> str:
    cols = "".join(f'<col style="width:{w}%">' for w in (widths or []))
    return (f'<table class="{cls}"><colgroup>{cols}</colgroup><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr>" +
            ("<tr>" + "<td></td>" * len(head) + "</tr>") * n + "</table>")


def pages() -> list:
    """[(short name, inner html)] for the 16 pages."""
    P = []
    P.append(("Cover", f"""<div class="cover"><div class="ring"></div><div class="ct"><p class="kick">Process over predictions</p>
<h1 class="big">Trader's Daily<br>Routine Planner</h1><div class="rule"></div><p class="lead">Prepare. Trade your plan. Review. Repeat.</p>
<div class="fields"><div><span>Name</span></div><div><span>Started on</span></div><div><span>Markets I trade</span></div><div><span>Account or evaluation</span></div></div></div>
<p class="note">{RISK}</p></div>"""))
    P.append(("How to use this planner", """<h1>How to use this planner</h1><p class="sub">A routine you can repeat on good days and bad days. Print the pages you need, as many as you need.</p>
<div class="loop"><div><b>1</b><h3>Prepare</h3><p>Pre-market routine and the daily plan: levels, if-then scenarios, today's limits.</p></div>
<div><b>2</b><h3>Trade your plan</h3><p>The trade log: one line per trade, and an honest "plan followed?" for each.</p></div>
<div><b>3</b><h3>Review</h3><p>The daily review: what went well, what to change, a process grade, one lesson.</p></div></div>
<h2>The pages</h2><table class="tb plain"><tr><th>Page</th><th>When</th><th>Page</th><th>When</th></tr>
<tr><td>My trading plan</td><td>Once, then update monthly</td><td>Weekly review</td><td>Friday or the weekend</td></tr>
<tr><td>My rules</td><td>Once, then re-read daily</td><td>Monthly review</td><td>End of each month</td></tr>
<tr><td>Pre-market routine</td><td>Every trading day</td><td>Habit tracker</td><td>Daily tick, monthly page</td></tr>
<tr><td>Daily plan</td><td>Every trading day</td><td>Mistake log</td><td>When a rule breaks</td></tr>
<tr><td>Trade log</td><td>During the session</td><td>If-then plans</td><td>Once, then add to it</td></tr>
<tr><td>Daily review</td><td>After the session</td><td>Setup playbook</td><td>One page per setup</td></tr>
<tr><td>Emotion check-in</td><td>Any day that feels off</td><td>Notes</td><td>Anything else</td></tr></table>
<h2>Grade the process, not the money</h2><p>A good day is one where you followed your plan and your rules, whatever the result. Grade each day A to F on
process only: <b>A</b> everything as planned, <b>B</b> small slips, <b>C</b> one rule bent, <b>D</b> a rule broken, <b>F</b> the plan abandoned.
The spreadsheet journal (Trader_Journal.xlsx) keeps the same daily log on a computer and adds up your routine, rule breaks and grades.</p>
<div class="box">This planner is a place to write your own plan and rules. It contains no strategies, signals or predictions, and it cannot
make anyone profitable. Trading involves substantial risk of loss and is not suitable for everyone.</div>"""))
    P.append(("My trading plan", f"""<h1>My trading plan</h1><p class="sub">Write it once on a calm day. Update it monthly, not in the middle of a session.</p>
<div class="grid2"><div class="fld"><span>Markets I trade</span>{rows(2)}</div><div class="fld"><span>Days and hours I trade</span>{rows(2)}</div></div>
<h2>My setups (the only trades I take)</h2>
<div class="grid3">{''.join(f'<div class="card"><span class="tag">Setup {i}</span><span>Name</span>{rows(1)}<span>Conditions</span>{rows(2)}<span>Entry</span>{rows(1)}<span>Stop</span>{rows(1)}<span>Exit</span>{rows(1)}</div>' for i in (1, 2, 3))}</div>
<h2>My limits</h2>{boxrow(["Risk per trade", "Max loss per day", "Max trades per day", "I stop trading at (time)"])}
<div class="grid2"><div class="fld"><span>I stop for the day when...</span>{rows(3)}</div><div class="fld"><span>I never...</span>{rows(3)}</div></div>"""))
    P.append(("My rules", f"""<h1>My rules</h1><p class="sub">Short, clear and checkable. Re-read them before every session.</p>
<table class="tb rules"><colgroup><col style="width:6%"><col style="width:56%"><col style="width:38%"></colgroup><tr><th>#</th><th>Rule</th><th>Why it matters to me</th></tr>
{''.join(f'<tr><td class="n">{i}</td><td></td><td></td></tr>' for i in range(1, 11))}</table>
<div class="box">Good rules are things you can check with a yes or no, for example "I only trade my three setups" or "after two losses in a row I stop for 15 minutes".</div>
<div class="sign"><div>Signed</div><div>Date</div><div>Next review</div></div>"""))
    P.append(("Pre-market routine", f"""<h1>Pre-market routine</h1><p class="sub">Same steps, same order, every trading day. Date: ______________</p>
<div class="grid2"><div>{scale("Sleep quality")}{scale("Energy")}{scale("Focus")}{scale("Calm")}</div>
<div class="fld"><span>Anything unusual today? (news, events, how I feel)</span>{rows(4)}</div></div>
<h2>Checklist</h2>{checks(["Read my rules (page: My rules)", "Checked today's scheduled news and events", "Marked my key levels", "Wrote the daily plan and if-then scenarios",
    "Set today's max loss and max trades", "Checked my platform, data and order settings", "Phone away, notifications off", "Two minutes of slow breathing",
    "I accept today's risk of: $ __________", "I know when I will stop: ______"])}
<h2>Three things I am watching (not predicting)</h2><div class="nums">{''.join(f'<div><b>{i}</b>{rows(1)}</div>' for i in (1, 2, 3))}</div>"""))
    P.append(("Daily plan", f"""<h1>Daily plan</h1><div class="meta"><span>Date</span><span>Session</span><span>Market(s)</span></div>
<div class="fld"><span>Context: what is the market doing, in plain words?</span>{rows(3)}</div>
<h2>Key levels</h2>{table(["Level", "Why it matters", "What I will do there"], 5, [18, 41, 41])}
<h2>If-then scenarios</h2><div class="ifs">{''.join('<div><b>If</b><div class="ln"></div><b>then I</b><div class="ln"></div></div>' for _ in range(3))}</div>
<h2>Today's limits</h2>{boxrow(["Max loss today", "Max trades", "Stop time", "Risk per trade"])}
<div class="fld"><span>One process goal for today (for example: "only A+ setups", "wait for my entry signal")</span>{rows(2)}</div>"""))
    P.append(("Trade log", f"""<h1>Trade log</h1><div class="meta"><span>Date</span><span>Session</span><span>Account</span></div>
{table(["#", "Time", "Market", "Setup", "L / S", "Entry", "Stop", "Target", "Size", "Result", "Plan?", "Note"], 14, [4, 7, 8, 11, 5, 8, 8, 8, 6, 8, 6, 21], "tb log")}
<p class="small">Plan? = Y if the trade met every condition of a written setup and every rule; N if not. Result in your own units (R, points or money): it is your record, not a score.</p>
{boxrow(["Trades", "Plan followed (Y)", "Plan broken (N)", "Rules broken"])}"""))
    P.append(("Daily review", f"""<h1>Daily review</h1><div class="meta"><span>Date</span><span>Process grade (A-F)</span><span>Routine done? Y / N</span></div>
<div class="grid2"><div class="fld"><span>What went well (process)</span>{rows(4)}</div><div class="fld"><span>What I would do differently</span>{rows(4)}</div></div>
<h2>Rules kept today</h2><div class="rk">{''.join(f'<span><i></i>{i}</span>' for i in range(1, 11))}</div>
<h2>How I felt</h2>{scale("Before the session")}{scale("During the session")}{scale("After the session")}
<div class="fld"><span>The moment I felt the most pressure, and what I did</span>{rows(2)}</div>
<div class="grid2"><div class="fld"><span>One lesson</span>{rows(2)}</div><div class="fld"><span>Tomorrow's focus</span>{rows(2)}</div></div>"""))
    P.append(("Weekly review", f"""<h1>Weekly review</h1><div class="meta"><span>Week of</span><span>Days traded</span><span>Routine days</span></div>
{table(["Day", "Trades", "Plan followed", "Rules broken", "Grade", "Note"], 5, [14, 11, 15, 14, 10, 36])}
<div class="grid2"><div class="fld"><span>Best decision this week</span>{rows(3)}</div><div class="fld"><span>Worst decision this week</span>{rows(3)}</div></div>
<div class="fld"><span>A pattern I noticed (time of day, setup, mood, after wins or losses)</span>{rows(3)}</div>
<div class="grid2"><div class="fld"><span>One rule to focus on next week</span>{rows(2)}</div><div class="fld"><span>One process goal for next week</span>{rows(2)}</div></div>"""))
    P.append(("Monthly review", f"""<h1>Monthly review</h1><div class="meta"><span>Month</span><span>Days traded</span><span>Average grade</span></div>
<div class="cal">{''.join(f'<div><b>{d}</b><i></i></div>' for d in range(1, 32))}<div class="key">Write each day's process grade (A-F) in its box.</div></div>
<div class="grid2"><div class="fld"><span>Top 3 lessons</span>{rows(3)}</div><div class="fld"><span>Rules to add, change or remove</span>{rows(3)}</div></div>
<div class="grid2"><div class="fld"><span>What I will keep doing</span>{rows(2)}</div><div class="fld"><span>Process goals for next month</span>{rows(2)}</div></div>"""))
    habits = "".join(f'<tr><td class="hn"></td>{"<td></td>" * 31}</tr>' for _ in range(10))
    P.append(("Habit tracker", f"""<h1>Habit tracker</h1><p class="sub">Month: ______________ Tick a box each day you keep the habit. Examples: routine done, rules read, journal written,
stopped at my limit, slept 7 hours, no trading after my stop time.</p>
<table class="hab"><tr><th class="hn">Habit</th>{''.join(f'<th>{d}</th>' for d in range(1, 32))}</tr>{habits}</table>"""))
    P.append(("Mistake log", f"""<h1>Mistake log</h1><p class="sub">Mistakes are data. Write them down without judging, then write the fix.</p>
{table(["Date", "What happened", "Trigger", "Rule", "Fix for next time"], 17, [11, 29, 18, 9, 33])}"""))
    examples = [("I lose two trades in a row", "stop for 15 minutes and re-read my rules"), ("I feel the urge to win it back", "stand up, step away, and log the feeling"),
                ("price moves without me", "let it go and wait for my next setup"), ("I reach my max loss for the day", "close the platform and do my review")]
    ifs = "".join(f'<div class="ex"><b>If</b> {a} <b>then I</b> {b}</div>' for a, b in examples)
    P.append(("If-then plans", f"""<h1>If-then plans</h1><p class="sub">Decide now what you will do in the moments that are hard to think clearly. Examples, then your own.</p>
{ifs}<h2>My if-then plans</h2><div class="ifs">{''.join('<div><b>If</b><div class="ln"></div><b>then I</b><div class="ln"></div></div>' for _ in range(8))}</div>"""))
    P.append(("Setup playbook", f"""<h1>Setup playbook</h1><div class="meta"><span>Setup name</span><span>Market(s)</span><span>Time window</span></div>
<div class="grid2"><div class="fld"><span>Conditions (all must be true)</span>{checks(["", "", "", "", ""], "ck blank")}</div><div class="fld"><span>Entry trigger</span>{rows(2)}<span>Stop placement</span>{rows(2)}<span>Exit plan</span>{rows(2)}</div></div>
<h2>Sketch</h2><div class="sketch"></div>
<div class="grid2"><div class="fld"><span>When I do NOT take it</span>{rows(3)}</div><div class="fld"><span>Notes from my reviews</span>{rows(3)}</div></div>"""))
    P.append(("Emotion check-in", f"""<h1>Emotion check-in</h1><p class="sub">For the days that feel off. Notice it, name it, choose what to do.</p>
<div class="meta"><span>Date</span><span>Time</span><span>Session</span></div>
<h2>Right now I feel</h2><div class="words">{''.join(f'<span><i></i>{w}</span>' for w in ["calm", "focused", "tired", "rushed", "frustrated", "anxious", "overconfident", "bored", "distracted", "fearful", "impatient", "content"])}</div>
{scale("How strong (1 = barely, 5 = very)")}
<div class="grid2"><div class="fld"><span>What triggered it</span>{rows(3)}</div><div class="fld"><span>Where I feel it in my body</span>{rows(3)}</div></div>
<h2>My reset options</h2>{checks(["Step away for 10 minutes", "Slow breathing for 2 minutes", "Re-read my rules", "Stop trading for today", "Write it down and move on"])}
<div class="fld"><span>What I chose, and how it went</span>{rows(3)}</div>"""))
    P.append(("Notes", """<h1>Notes</h1><div class="dots"></div>"""))
    return P


def planner_html(size: str) -> str:
    w, h = SIZES[size]
    m = 11.0
    ph = h - 2 * m - 0.6
    out = []
    pg = pages()
    for i, (name, inner) in enumerate(pg, 1):
        foot = "" if i == 1 else f'<div class="foot"><span>{name}</span><span>Trader\'s Daily Routine Planner · process, not predictions · not financial advice</span><span>{i}</span></div>'
        out.append(f'<section class="page{" first" if i == 1 else ""}"><div class="in">{inner}</div>{foot}</section>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
@page{{size:{size};margin:{m}mm}}
*{{box-sizing:border-box}}html,body{{margin:0;padding:0}}
body{{font-family:Inter,'Segoe UI',Arial,sans-serif;color:{INK};font-size:9.6pt;line-height:1.35;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.page{{height:{ph:.1f}mm;display:flex;flex-direction:column;break-after:page;overflow:hidden}}.page:last-child{{break-after:auto}}
.in{{flex:1;display:flex;flex-direction:column;gap:2.6mm;min-height:0}}
h1{{font-family:{K.SERIF};font-size:21pt;line-height:1.05;margin:0;color:{INK}}}h1:after{{content:"";display:block;width:18mm;height:1.2mm;background:{ACC};border-radius:1mm;margin-top:2.2mm}}
h1.big:after{{display:none}}
h2{{font-family:{K.SERIF};font-size:12.5pt;margin:1.5mm 0 0;color:{ACC}}}h3{{margin:0 0 1mm;font-size:11pt}}
p{{margin:0}}.sub{{color:{MUTED};font-size:9.4pt}}.small{{color:{MUTED};font-size:8pt}}
.ln{{border-bottom:0.25mm solid {LINE};height:7.6mm;flex:none}}
.fld{{display:flex;flex-direction:column}}.fld>span,.card>span{{font-size:8.2pt;font-weight:700;color:{MUTED};margin-top:1.2mm}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:6mm}}.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm}}
.card{{border:0.3mm solid {LINE};border-radius:2.5mm;padding:2.5mm 3mm;display:flex;flex-direction:column}}.card .ln{{height:6.6mm}}
.tag{{color:#fff!important;background:{ACC};border-radius:5mm;padding:.6mm 3mm;align-self:flex-start;margin:0 0 1mm!important}}
.boxes{{display:grid;grid-template-columns:repeat(4,1fr);gap:3mm}}.bx{{border:0.3mm solid {LINE};border-radius:2.5mm;height:15mm;padding:1.6mm 2.5mm;background:{SOFTF}}}
.bx span{{font-size:8pt;font-weight:700;color:{MUTED}}}
.scale{{display:flex;align-items:center;gap:2.4mm;margin:1.3mm 0}}.scale b{{flex:1;font-size:9pt}}.scale i{{font-style:normal;width:7mm;height:7mm;border:0.3mm solid {LINE};border-radius:50%;display:grid;place-items:center;font-size:8pt;color:{MUTED}}}
ul.ck{{list-style:none;margin:0;padding:0;columns:2;column-gap:8mm}}ul.ck li{{break-inside:avoid;padding:1.6mm 0 1.6mm 7mm;position:relative;border-bottom:0.25mm solid {LINE};min-height:8mm}}
ul.ck li:before{{content:"";position:absolute;left:0;top:1.6mm;width:4.2mm;height:4.2mm;border:0.35mm solid {ACC};border-radius:1mm}}ul.ck.blank{{columns:1}}
.nums{{display:grid;gap:2mm}}.nums>div{{display:flex;gap:3mm;align-items:flex-end}}.nums b{{color:{ACC};font-family:{K.SERIF};font-size:13pt;width:5mm}}.nums .ln{{flex:1}}
.meta{{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm}}.meta span{{border-bottom:0.3mm solid {INK};padding:5mm 0 0.8mm;font-size:8pt;font-weight:700;color:{MUTED}}}
table.tb{{width:100%;border-collapse:collapse;table-layout:fixed}}.tb th{{background:{SOFTF};color:{INK};font-size:8.2pt;text-align:left;padding:1.4mm 1.6mm;border:0.3mm solid {LINE}}}
.tb td{{border:0.3mm solid {LINE};height:8.6mm}}.tb.log td{{height:9.6mm}}.tb.plain td{{height:auto;padding:1.4mm 1.6mm;font-size:8.8pt}}
.rules td{{height:13.5mm}}.rules td.n{{text-align:center;font-family:{K.SERIF};font-size:13pt;color:{ACC}}}
.ifs{{display:grid;gap:2.2mm}}.ifs>div{{display:grid;grid-template-columns:auto 1fr auto 1fr;gap:2.5mm;align-items:end}}.ifs b{{color:{ACC};font-size:9pt}}
.ex{{background:{SOFTF};border-radius:2mm;padding:2mm 3mm;font-size:9.4pt}}.ex b{{color:{ACC}}}
.rk{{display:flex;flex-wrap:wrap;gap:3mm}}.rk span,.words span{{display:inline-flex;align-items:center;gap:1.6mm;font-weight:700}}
.rk i,.words i{{width:4.6mm;height:4.6mm;border:0.35mm solid {ACC};border-radius:1mm}}.words{{display:grid;grid-template-columns:repeat(4,1fr);gap:2.6mm}}
.cal{{display:grid;grid-template-columns:repeat(7,1fr);gap:1.6mm}}.cal>div{{border:0.3mm solid {LINE};border-radius:1.6mm;height:15mm;padding:1mm 1.6mm;position:relative}}
.cal b{{font-size:8pt;color:{MUTED}}}.cal i{{position:absolute;right:1.6mm;bottom:1.6mm;width:6mm;height:6mm;border:0.3mm solid {ACC};border-radius:1mm}}
.cal .key{{grid-column:span 4;border:0!important;font-size:8pt;color:{MUTED};display:flex;align-items:center}}
table.hab{{width:100%;border-collapse:collapse;table-layout:fixed;font-size:7pt}}.hab th,.hab td{{border:0.25mm solid {LINE};text-align:center;padding:0}}
.hab th{{background:{SOFTF};height:6mm}}.hab td{{height:12mm}}.hab .hn{{width:24%;text-align:left;padding-left:1.5mm}}
.sketch{{flex:1;min-height:60mm;border:0.3mm solid {LINE};border-radius:2mm;background-image:linear-gradient({SOFTF} 0.3mm,transparent 0.3mm),linear-gradient(90deg,{SOFTF} 0.3mm,transparent 0.3mm);background-size:5mm 5mm}}
.dots{{flex:1;background-image:radial-gradient(circle,{LINE} 0.35mm,transparent 0.4mm);background-size:5mm 5mm;border-radius:2mm}}
.box{{background:{SOFTF};border-left:1.2mm solid {ACC};border-radius:1.5mm;padding:2.4mm 3.2mm;font-size:9pt}}
.loop{{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm}}.loop>div{{border:0.3mm solid {LINE};border-radius:3mm;padding:3mm}}.loop b{{display:inline-grid;place-items:center;width:8mm;height:8mm;border-radius:50%;background:{ACC};color:#fff;margin-bottom:1.5mm}}
.sign{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:6mm;margin-top:auto}}.sign div{{border-top:0.3mm solid {INK};padding-top:1mm;font-size:8pt;color:{MUTED};margin-top:10mm}}
.foot{{display:flex;justify-content:space-between;gap:4mm;font-size:7pt;color:{MUTED};border-top:0.25mm solid {LINE};padding-top:1.2mm;margin-top:2mm}}
.cover{{flex:1;display:flex;flex-direction:column;justify-content:space-between;position:relative;overflow:hidden;background:#14110e;color:#f3ece0;border-radius:3mm;padding:16mm 14mm 10mm}}
.cover .ring{{position:absolute;right:-40mm;top:-30mm;width:150mm;height:150mm;border-radius:50%;border:12mm solid rgba(200,162,74,.16);box-shadow:0 0 0 14mm rgba(200,162,74,.06)}}
.cover .ct{{position:relative}}.cover .kick{{color:#c8a24a;font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:9pt}}
.cover h1{{font-size:38pt;color:#f3ece0;margin-top:3mm}}.cover .rule{{width:22mm;height:1.6mm;background:#c8a24a;border-radius:1mm;margin:5mm 0}}
.cover .lead{{font-size:14pt;color:#cfc4b2}}.cover .fields{{display:grid;gap:4mm;margin-top:22mm;max-width:120mm}}
.cover .fields div{{border-bottom:0.3mm solid #6b6254;padding-top:7mm}}.cover .fields span{{font-size:8.5pt;color:#a89c88;font-weight:700}}.cover .note{{position:relative;font-size:8pt;color:#a89c88}}
</style></head><body>{''.join(out)}</body></html>"""


# ------------------------------------------------------------------------------------------------ the spreadsheet journal
D_FIRST, D_LAST = 5, 404
B_FIRST, B_LAST = 5, 304
R_FIRST, R_LAST = 5, 404
W_FIRST, W_LAST = 6, 57
ROUTINE = ["Rules read", "News checked", "Levels marked", "Plan written", "Limits set", "Platform checked", "Distractions off", "Breathing"]


def build_journal(path: str = JOURNAL) -> str:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    F = "Arial"
    title, bold, norm = Font(name=F, size=16, bold=True), Font(name=F, size=11, bold=True), Font(name=F, size=11)
    small, blue, big = Font(name=F, size=10, color="56626A"), Font(name=F, size=11, color="0000FF"), Font(name=F, size=14, bold=True)
    head, calc, inp = PatternFill("solid", fgColor="E2ECEA"), PatternFill("solid", fgColor="F4F4F4"), PatternFill("solid", fgColor="FFF2CC")
    line = Border(bottom=Side(style="thin", color="BBBBBB"))
    wrap = Alignment(wrap_text=True, vertical="top")
    wb = Workbook()

    st = wb.active
    st.title = "Start here"
    st.column_dimensions["A"].width = 112
    lines = [("Trader Journal v" + VERSION + ": process, not predictions", title),
             ("A computer version of the planner's daily log. Yellow cells with blue text are yours; grey cells are calculated.", norm), ("", norm),
             ("1. Daily: one row per trading day: sleep, energy, mood, routine done, plan written, trades, rule breaks, a process grade A-F, one lesson.", norm),
             ("2. Rules: type up to 10 rules. Rule breaks: log each break with the rule number; the Rules tab counts them.", norm),
             ("3. Routine: tick (type 1) each step of your pre-market routine; the % fills in.", norm),
             ("4. Weekly: type the Monday of each week; it adds up that week from the Daily tab.", norm),
             ("5. Dashboard: days journaled, routine and plan rates, rule breaks, the most broken rule, grades and your routine streak.", norm), ("", norm),
             ("Grade the PROCESS, not the money: A = all as planned, B = small slips, C = one rule bent, D = a rule broken, F = plan abandoned.", bold),
             ("The rows marked 'Example' show how it works: type over them or delete them.", norm),
             ("Opens in the usual spreadsheet apps on a computer, and in free online spreadsheets (import the file).", norm), ("", norm),
             (RISK, small)]
    for i, (t, f) in enumerate(lines, 1):
        c = st.cell(row=i, column=1, value=t)
        c.font, c.alignment = f, wrap

    # Daily -----------------------------------------------------------------------------------------------------------
    d = wb.create_sheet("Daily")
    d["A1"], d["A1"].font = "Daily log", title
    d["A2"], d["A2"].font = "One row per trading day, oldest first, no empty rows in between. The net result column is optional and only for your own records.", small
    heads = ["Date", "Session", "Sleep (h)", "Energy 1-5", "Mood before 1-5", "Routine done (Y/N)", "Plan written (Y/N)", "Trades", "Rule breaks",
             "Process grade (A-F)", "Net result (optional)", "Lesson", "Grade points", "Routine streak"]
    widths = [12, 12, 9, 9, 10, 11, 11, 8, 9, 11, 12, 40, 9, 10]
    for j, (h, w) in enumerate(zip(heads, widths), 1):
        c = d.cell(row=4, column=j, value=h)
        c.font, c.fill, c.border, c.alignment = bold, head, line, Alignment(wrap_text=True, vertical="bottom")
        d.column_dimensions[c.column_letter].width = w
    d.row_dimensions[4].height = 44
    for r in range(D_FIRST, D_LAST + 1):
        for j in range(1, 13):
            c = d.cell(row=r, column=j)
            c.fill, c.font = inp, blue
        d.cell(row=r, column=1).number_format = "yyyy-mm-dd"
        d.cell(row=r, column=11).number_format = '#,##0.00;-#,##0.00;"-"'
        gp = d.cell(row=r, column=13, value=f'=IF(J{r}="","",IFERROR(MATCH(UPPER(J{r}),{{"F","D","C","B","A"}},0)-1,""))')
        prev = f"N{r - 1}" if r > D_FIRST else "0"
        sk = d.cell(row=r, column=14, value=f'=IF(A{r}="","",IF(UPPER(F{r})="Y",{"0" if r == D_FIRST else f"N(" + prev + ")"}+1,0))')
        for c in (gp, sk):
            c.fill, c.font = calc, norm
    ex = [[dt.date(2026, 11, 16), "Morning", 7.5, 4, 4, "Y", "Y", 2, 0, "A", None, "Example: waited for my setup; stopped at my time"],
          [dt.date(2026, 11, 17), "Morning", 6, 3, 3, "Y", "Y", 3, 1, "C", None, "Example: third trade was outside my plan (rule 2)"],
          [dt.date(2026, 11, 18), "Morning", 7, 4, 4, "N", "Y", 1, 0, "B", None, "Example: skipped breathing; felt rushed at the open"]]
    for i, row in enumerate(ex):
        for j, v in enumerate(row, 1):
            d.cell(row=D_FIRST + i, column=j, value=v)
    yn = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
    yn.add(f"F{D_FIRST}:G{D_LAST}")
    gr = DataValidation(type="list", formula1='"A,B,C,D,F"', allow_blank=True)
    gr.add(f"J{D_FIRST}:J{D_LAST}")
    sc = DataValidation(type="whole", operator="between", formula1="1", formula2="5", allow_blank=True)
    sc.add(f"D{D_FIRST}:E{D_LAST}")
    for v in (yn, gr, sc):
        d.add_data_validation(v)
    d.freeze_panes = "B5"

    # Rules + rule breaks ------------------------------------------------------------------------------------------
    ru = wb.create_sheet("Rules")
    ru["A1"], ru["A1"].font = "My rules", title
    ru["A2"], ru["A2"].font = "Short and checkable. Breaks are counted from the Rule breaks tab.", small
    for j, (h, w) in enumerate(zip(["#", "Rule", "Why it matters to me", "Times broken", "Last broken"], (5, 52, 40, 13, 13)), 1):
        c = ru.cell(row=4, column=j, value=h)
        c.font, c.fill, c.border = bold, head, line
        ru.column_dimensions[c.column_letter].width = w
    ex_rules = ["Example: I only trade my written setups", "Example: I stop for 15 minutes after two losses in a row", "Example: I stop at my max loss for the day"]
    for i in range(10):
        r = 5 + i
        ru.cell(row=r, column=1, value=i + 1).font = bold
        for j in (2, 3):
            c = ru.cell(row=r, column=j, value=(ex_rules[i] if j == 2 and i < len(ex_rules) else None))
            c.fill, c.font = inp, blue
        c = ru.cell(row=r, column=4, value=f"=COUNTIF('Rule breaks'!$B${B_FIRST}:$B${B_LAST},A{r})")
        c.fill, c.font = calc, norm
        c = ru.cell(row=r, column=5, value=f'=IF(D{r}=0,"",_xlfn.MAXIFS(\'Rule breaks\'!$A${B_FIRST}:$A${B_LAST},\'Rule breaks\'!$B${B_FIRST}:$B${B_LAST},A{r}))')
        c.fill, c.font, c.number_format = calc, norm, "yyyy-mm-dd"
    rb = wb.create_sheet("Rule breaks")
    rb["A1"], rb["A1"].font = "Rule breaks", title
    rb["A2"], rb["A2"].font = "One row each time a rule breaks: no judging, just the facts and the fix.", small
    for j, (h, w) in enumerate(zip(["Date", "Rule #", "What happened", "Trigger", "Fix for next time"], (12, 8, 44, 26, 40)), 1):
        c = rb.cell(row=4, column=j, value=h)
        c.font, c.fill, c.border = bold, head, line
        rb.column_dimensions[c.column_letter].width = w
    for r in range(B_FIRST, B_LAST + 1):
        for j in range(1, 6):
            c = rb.cell(row=r, column=j)
            c.fill, c.font = inp, blue
        rb.cell(row=r, column=1).number_format = "yyyy-mm-dd"
    for j, v in enumerate([dt.date(2026, 11, 17), 1, "Example: took a trade that was not one of my setups", "Boredom after a slow hour", "If it is slow, I review my plan instead"], 1):
        rb.cell(row=B_FIRST, column=j, value=v)
    rv = DataValidation(type="whole", operator="between", formula1="1", formula2="10", allow_blank=True)
    rv.add(f"B{B_FIRST}:B{B_LAST}")
    rb.add_data_validation(rv)

    # Routine -------------------------------------------------------------------------------------------------------
    ro = wb.create_sheet("Routine")
    ro["A1"], ro["A1"].font = "Pre-market routine", title
    ro["A2"], ro["A2"].font = "Type 1 for each step you did. Rename the steps in row 4 to match your own routine.", small
    for j, h in enumerate(["Date"] + ROUTINE + ["% done"], 1):
        c = ro.cell(row=4, column=j, value=h)
        c.font, c.fill, c.border, c.alignment = bold, head, line, Alignment(wrap_text=True, vertical="bottom")
        ro.column_dimensions[c.column_letter].width = 12 if j > 1 else 12
    ro.row_dimensions[4].height = 32
    last_col = chr(ord("A") + len(ROUTINE))
    pct_col = chr(ord("A") + len(ROUTINE) + 1)
    for r in range(R_FIRST, R_LAST + 1):
        for j in range(1, len(ROUTINE) + 2):
            c = ro.cell(row=r, column=j)
            c.fill, c.font = inp, blue
        ro.cell(row=r, column=1).number_format = "yyyy-mm-dd"
        c = ro.cell(row=r, column=len(ROUTINE) + 2, value=f'=IF(A{r}="","",COUNTIF(B{r}:{last_col}{r},1)/{len(ROUTINE)})')
        c.fill, c.font, c.number_format = calc, norm, "0%"
    for i, ticks in enumerate([[1] * 8, [1] * 8, [1, 1, 1, 1, 1, 1, 1, 0]]):
        ro.cell(row=R_FIRST + i, column=1, value=dt.date(2026, 11, 16 + i))
        for j, t in enumerate(ticks, 2):
            ro.cell(row=R_FIRST + i, column=j, value=t if t else None)

    # Weekly ----------------------------------------------------------------------------------------------------------
    wk = wb.create_sheet("Weekly")
    wk["A1"], wk["A1"].font = "Weekly review", title
    wk["A2"], wk["A2"].font = "Type the Monday of each week in column A; the rest adds up that week (Monday to Sunday) from the Daily tab.", small
    wh = ["Week of (Monday)", "Days journaled", "Routine days", "Plan written days", "Trades", "Rule breaks", "Average grade", "Average energy", "Focus for next week"]
    for j, (h, w) in enumerate(zip(wh, (14, 11, 11, 12, 9, 10, 11, 11, 44)), 1):
        c = wk.cell(row=5, column=j, value=h)
        c.font, c.fill, c.border, c.alignment = bold, head, line, Alignment(wrap_text=True, vertical="bottom")
        wk.column_dimensions[c.column_letter].width = w
    wk.row_dimensions[5].height = 32
    DR = lambda col: f"Daily!${col}${D_FIRST}:${col}${D_LAST}"  # noqa: E731
    for r in range(W_FIRST, W_LAST + 1):
        a = wk.cell(row=r, column=1, value=(dt.date(2026, 11, 16) if r == W_FIRST else None))
        a.fill, a.font, a.number_format = inp, blue, "yyyy-mm-dd"
        win = f'{DR("A")},">="&$A{r},{DR("A")},"<="&$A{r}+6'
        f = {2: f'=IF($A{r}="","",COUNTIFS({win}))',
             3: f'=IF($A{r}="","",COUNTIFS({win},{DR("F")},"Y"))',
             4: f'=IF($A{r}="","",COUNTIFS({win},{DR("G")},"Y"))',
             5: f'=IF($A{r}="","",SUMIFS({DR("H")},{win}))',
             6: f'=IF($A{r}="","",SUMIFS({DR("I")},{win}))',
             7: f'=IF(OR($A{r}="",COUNTIFS({win},{DR("M")},">=0")=0),"",MID("FDCBA",ROUND(AVERAGEIFS({DR("M")},{win}),0)+1,1))',
             8: f'=IF(OR($A{r}="",COUNTIFS({win},{DR("D")},">=1")=0),"",ROUND(AVERAGEIFS({DR("D")},{win}),1))'}
        for j, formula in f.items():
            c = wk.cell(row=r, column=j, value=formula)
            c.fill, c.font = calc, norm
        c = wk.cell(row=r, column=9)
        c.fill, c.font = inp, blue

    # Dashboard -----------------------------------------------------------------------------------------------------
    db = wb.create_sheet("Dashboard", 1)
    db.column_dimensions["A"].width = 50
    db.column_dimensions["B"].width = 16
    db["A1"], db["A1"].font = "Your process at a glance", title
    db["A2"], db["A2"].font = "From your own Daily, Rules and Routine tabs. It measures habits, not results.", small
    gpr = DR("M")
    items = [("Days journaled", f'=COUNT({DR("A")})', "0"),
             ("Routine done (share of days)", f'=IF(B3=0,"",COUNTIF({DR("F")},"Y")/B3)', "0%"),
             ("Plan written (share of days)", f'=IF(B3=0,"",COUNTIF({DR("G")},"Y")/B3)', "0%"),
             ("Rule breaks logged", f"=COUNT('Rule breaks'!$B${B_FIRST}:$B${B_LAST})", "0"),
             ("Most broken rule", '=IF(MAX(Rules!$D$5:$D$14)=0,"None yet",INDEX(Rules!$B$5:$B$14,MATCH(MAX(Rules!$D$5:$D$14),Rules!$D$5:$D$14,0)))', "@"),
             ("Average process grade", f'=IF(COUNT({gpr})=0,"",MID("FDCBA",ROUND(AVERAGE({gpr}),0)+1,1))', "@"),
             ("Grade on days the routine was done", f'=IF(COUNTIFS({DR("F")},"Y",{gpr},">=0")=0,"",MID("FDCBA",ROUND(AVERAGEIFS({gpr},{DR("F")},"Y"),0)+1,1))', "@"),
             ("Grade on days the routine was skipped", f'=IF(COUNTIFS({DR("F")},"N",{gpr},">=0")=0,"",MID("FDCBA",ROUND(AVERAGEIFS({gpr},{DR("F")},"N"),0)+1,1))', "@"),
             ("Average sleep (hours)", f'=IF(COUNT({DR("C")})=0,"",ROUND(AVERAGE({DR("C")}),1))', "0.0"),
             ("Average energy (1-5)", f'=IF(COUNT({DR("D")})=0,"",ROUND(AVERAGE({DR("D")}),1))', "0.0"),
             ("Average mood before (1-5)", f'=IF(COUNT({DR("E")})=0,"",ROUND(AVERAGE({DR("E")}),1))', "0.0"),
             ("Current routine streak (days in a row)", f'=IF(B3=0,0,INDEX({DR("N")},B3))', "0"),
             ("Routine steps done (share, from the Routine tab)", f"=IF(COUNT(Routine!$A${R_FIRST}:$A${R_LAST})=0,\"\",AVERAGE(Routine!${pct_col}${R_FIRST}:${pct_col}${R_LAST}))", "0%")]
    for i, (lab, formula, fmt) in enumerate(items, 3):
        a = db.cell(row=i, column=1, value=lab)
        c = db.cell(row=i, column=2, value=formula)
        a.font, a.border, c.border = norm, line, line
        c.number_format, c.fill = fmt, calc
        c.font = big if lab.startswith(("Routine done", "Average process", "Current routine")) else norm
    g0 = 3 + len(items) + 1
    db.cell(row=g0, column=1, value="Process grades").font = bold
    for i, g in enumerate("ABCDF"):
        db.cell(row=g0 + 1 + i, column=1, value=f"Days graded {g}").font = norm
        c = db.cell(row=g0 + 1 + i, column=2, value=f'=COUNTIF({DR("J")},"{g}")')
        c.fill, c.font = calc, norm
    db.cell(row=g0 + 7, column=1, value="The grade comparison is about your own habits on your own days; it is not a prediction of anything.").font = small
    for txt, color in (("A", "D9EAD3"), ("B", "E2ECEA"), ("D", "FCE5CD"), ("F", "F4CCCC")):
        d.conditional_formatting.add(f"J{D_FIRST}:J{D_LAST}", CellIsRule(operator="equal", formula=[f'"{txt}"'], fill=PatternFill("solid", fgColor=color)))
    for w in wb.worksheets:
        w.sheet_view.zoomScale = 110
    wb.active = 0
    wb.save(path)
    return path


# ------------------------------------------------------------------------------------------------ text files
LICENSE = f"""TRADER'S DAILY ROUTINE PLANNER v{VERSION}: LICENCE

You may print and use these pages and the spreadsheet for your own trading records, as often as you like, on your own devices.
You may not resell, share, upload or give away the files or edited copies of them.

The planner is for organising your own plan, rules and reviews. It is not financial advice, contains no trade ideas, signals or
predictions, and does not promise any result. It is not affiliated with any broker, exchange, prop firm or trading platform.
Trading involves substantial risk of loss and is not suitable for everyone.

Provided as is, without warranty of any kind. If something does not work as described, message the seller through the shop
where you bought this within 14 days and we will help you or refund you.
"""

README = f"""TRADER'S DAILY ROUTINE PLANNER v{VERSION}: QUICK START

Printable planner (16 pages, undated, print as many copies of a page as you need):
  Trader_Planner_Letter.pdf   US Letter (8.5 x 11 in)
  Trader_Planner_A4.pdf       A4 (210 x 297 mm)
  Print at 100% ("actual size"). Pages 1-4 once; pre-market routine, daily plan, trade log and daily review every trading day;
  weekly review on Fridays; monthly review and habit tracker each month.

Spreadsheet journal: Trader_Journal.xlsx
  Opens in the usual spreadsheet apps on a computer and in free online spreadsheets (import the file).
  Start on the "Start here" tab. The Daily, Rules, Rule breaks, Routine and Weekly tabs feed the Dashboard.

Grade the process, not the money. {RISK}
"""


# ------------------------------------------------------------------------------------------------ pictures
def page_pngs(pdf: str, tmp: str, dpi: int = 70) -> list:
    return [open(p, "rb").read() for p in K.pdf_pages_png(pdf, tmp, dpi=dpi)]


def journal_png(tmp: str) -> bytes:
    """The Dashboard and Daily tabs as LibreOffice prints them (page found by its title text)."""
    from money_machines.products.build_agency_kit import soffice_pdf
    from pypdf import PdfReader
    pdf = soffice_pdf(JOURNAL, tmp)
    r = PdfReader(pdf)
    idx = next((i for i, p in enumerate(r.pages) if "Your process at a glance" in (p.extract_text() or "")), 1)
    pngs = K.pdf_pages_png(pdf, os.path.join(tmp, "j"), dpi=90)
    return open(pngs[idx], "rb").read()


def covers(br, pngs: list, journal: bytes) -> list:
    from io import BytesIO

    from PIL import Image

    def u(b, crop=None):
        im = Image.open(BytesIO(b)).convert("RGB")
        if crop:
            im = im.crop((0, 0, im.width, int(im.width * crop)))
        o = BytesIO()
        im.save(o, "JPEG", quality=88)
        return K.b64(o.getvalue())
    names = [n for n, _ in pages()]
    done = []
    bg, ink, soft, acc = "#14110e", "#f3ece0", "#cfc4b2", "#c8a24a"
    fan_idx = [6, 4, 5, 7]          # trade log, pre-market, daily plan, daily review
    for name, w, h in K.COVERS:
        sq, k, n = w == h, w / 1280, name.split("_")[1][0]
        css = K.cover_css(w, h, bg=bg, ink=ink, soft=soft, accent=acc) + f"""
.pad{{position:absolute;inset:0;padding:{int(60 * k)}px}}.kick{{font-size:{int(21 * k)}px;padding:{int(7 * k)}px {int(18 * k)}px;margin-bottom:{int(22 * k)}px}}
h1{{font-size:{int((80 if sq else 58) * k)}px}}.lead{{font-size:{int((30 if sq else 23) * k)}px;line-height:1.35;margin-top:{int(18 * k)}px;color:{soft}}}
ul.checks li{{font-size:{int((28 if sq else 22) * k)}px;margin:{int(11 * k)}px 0}}
.foot{{position:absolute;left:{int(60 * k)}px;right:{int(60 * k)}px;bottom:{int(22 * k)}px;font-size:{int((18 if sq else 15) * k)}px;color:#a89c88}}
.pg{{position:absolute;background:#fff;border-radius:{max(3, int(5 * k))}px;box-shadow:0 {int(18 * k)}px {int(44 * k)}px rgba(0,0,0,.55)}}
.lbl{{font-size:{int((17 if sq else 12) * k)}px;color:{soft};text-align:center;margin-top:{int(6 * k)}px}}"""
        if n == "1":
            text = (f'<span class="chip kick">Printable planner + spreadsheet journal</span><h1>Trader\'s Daily Routine Planner</h1><div class="rule" style="margin-top:{int(22 * k)}px"></div>'
                    f'<p class="lead">Prepare. Trade your plan. Review. A routine you can repeat on good days and bad days.</p>'
                    f'<ul class="checks" style="margin-top:{int(14 * k)}px"><li>16 undated pages, US Letter + A4</li><li>Pre-market routine, daily plan, trade log</li>'
                    f'<li>Daily, weekly and monthly reviews</li><li>Spreadsheet journal with a process dashboard</li></ul>')
            if sq:
                pos = [(1030, 960, 8, 640), (800, 1000, 2, 640), (560, 1040, -4, 640), (330, 1090, -10, 640)]
                body = f'<div class="pad">{text}</div>'
            else:
                pos = [(1010, 120, 9, 300), (900, 150, 3, 300), (790, 190, -3, 300), (690, 240, -9, 300)]
                body = f'<div class="pad" style="width:{int(600 * k)}px">{text}</div>'
            body += "".join(f'<img class="pg" src="{u(pngs[i])}" style="left:{int(x * k)}px;top:{int(y * k)}px;width:{int(pw * k)}px;transform:rotate({r}deg)">'
                            for i, (x, y, r, pw) in zip(fan_idx, pos))
            body += '<div class="foot">Process only: no signals, no predictions, no results promised. Trading involves substantial risk of loss.</div>'
        elif n == "2":
            cols = 4 if sq else 8
            tw = int((400 if sq else 136) * k)
            cells = "".join(f'<div><img src="{u(b)}" style="width:{tw}px;border-radius:{max(3, int(4 * k))}px;box-shadow:0 {int(8 * k)}px {int(20 * k)}px rgba(0,0,0,.45);background:#fff;display:block"><div class="lbl">{names[i]}</div></div>' for i, b in enumerate(pngs))
            top = int((280 if sq else 150) * k)
            body = (f'<div class="pad" style="text-align:center"><h1 style="font-size:{int((70 if sq else 44) * k)}px">16 pages for your routine</h1></div>'
                    f'<div style="position:absolute;top:{top}px;left:0;right:0;display:grid;grid-template-columns:repeat({cols},{tw}px);gap:{int((26 if sq else 12) * k)}px {int((34 if sq else 14) * k)}px;justify-content:center">{cells}</div>')
        else:
            text = (f'<span class="chip kick">Included: the spreadsheet journal</span><h1>Track your habits, not just trades</h1><div class="rule" style="margin-top:{int(22 * k)}px"></div>'
                    f'<ul class="checks" style="margin-top:{int(16 * k)}px"><li>Daily log: sleep, energy, routine, plan, grade</li><li>Rules and rule breaks, counted for you</li>'
                    f'<li>Weekly review that adds itself up</li><li>A dashboard of your process</li></ul>')
            jw = int((1180 if sq else 600) * k)
            if sq:
                body = f'<div class="pad">{text}</div><div style="position:absolute;left:{int(410 * k)}px;top:{int(900 * k)}px">{K.window(u(journal, crop=0.78), jw)}</div>'
            else:
                body = f'<div class="pad" style="width:{int(560 * k)}px">{text}</div><div style="position:absolute;left:{int(620 * k)}px;top:{int(90 * k)}px">{K.window(u(journal, crop=0.78), jw)}</div>'
            body += '<div class="foot">The journal measures your own habits. It gives no trade ideas and makes no predictions.</div>'
        html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"
        done.append(K.shoot(br, html, w, h, os.path.join(SHOP, name), quality=80 if sq else 84))
    return done


def build_media(log=print) -> list:
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as pw:
        br = K.chromium(pw)
        for size in SIZES:
            out.append(K.html_pdf(br, planner_html(size), os.path.join(BUYER, f"Trader_Planner_{size}.pdf"), size, "Trader's Daily Routine Planner (" + size + ")"))
        tmp = tempfile.mkdtemp(prefix="d2_planner_")
        try:
            pngs = page_pngs(os.path.join(BUYER, "Trader_Planner_Letter.pdf"), os.path.join(tmp, "p"))
            out += covers(br, pngs, journal_png(tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        br.close()
    return out


def build(images: bool = True, log=print) -> list:
    os.makedirs(BUYER, exist_ok=True)
    p = build_journal()
    log(K.recalc_xlsx(p))
    done = [K.clean_ooxml(p, "Trader Journal")]
    done.append(K.write_text(os.path.join(BUYER, "LICENSE.txt"), LICENSE))
    done.append(K.write_text(os.path.join(BUYER, "README.txt"), README))
    if images:
        done += build_media(log)
    done += K.write_listing(SHOP, dict(LISTING, files=K.buyer_files(BUYER)))
    return done


LISTING = {
    "id": "trader-planner", "version": VERSION, "price_usd": 14, "top": TOP, "zip": ZIP,
    "title": "Trader's Daily Routine Planner and Journal, Printable PDF (US Letter + A4) + Spreadsheet, Pre-Market Checklist, Trade Log, Weekly Review",
    "short": "A calm daily routine for traders: prepare, trade your plan, review. 16 printable pages plus a spreadsheet journal. Process only, no signals.",
    "description": [
        "Most trading mistakes are routine mistakes: no plan, no limits, no review. This planner gives you the same simple steps every day, on paper and in a spreadsheet.",
        "WHAT YOU GET",
        "- 16 undated printable pages in US Letter and A4: cover, how to use, my trading plan, my rules, pre-market routine, daily plan, trade log, daily review, weekly review, monthly review, habit tracker, mistake log, if-then plans, setup playbook, emotion check-in, notes",
        "- A spreadsheet journal: daily log (sleep, energy, mood, routine, plan, trades, rule breaks, a process grade), your rules with break counts, a routine checklist, a weekly review that adds itself up and a process dashboard",
        "- Print what you need, as many times as you need",
        "HOW IT HELPS",
        "- Grade your process (did you follow your plan and rules?), not the money",
        "- See which rule you break most, and how your routine days compare with your skipped days, from your own records",
        "- Decide in advance what you do after two losses, at your daily limit or when you feel rushed (if-then plans)",
        "WHAT IT IS NOT",
        "- No strategies, signals, predictions or advice. It organises your own plan and rules and promises no results.",
        "- Not affiliated with any broker, exchange, prop firm or trading platform. Works for futures, stocks, options, forex or crypto traders.",
        "Pairs with my Prop Eval Tracker if you trade an evaluation.",
        "Instant download. Made with the help of AI tools; designed, checked and supported by me.",
        "Trading involves substantial risk of loss and is not suitable for everyone. No results are shown or promised.",
    ],
    "tags_etsy": ["trading journal", "trader planner", "day trading log", "trading routine", "pre market checklist", "trade log", "trading planner pdf",
                  "printable planner", "habit tracker", "trading psychology", "weekly review", "journal spreadsheet", "risk management"],
    "faq": [
        ["Is this financial advice?", "No. It is a planner for your own plan, rules and reviews. It gives no trade ideas and makes no predictions."],
        ["Which markets does it work for?", "Any: futures, stocks, options, forex or crypto. You write your own markets, setups and rules."],
        ["Which paper sizes are included?", "US Letter and A4, both undated. Print at 100% (actual size)."],
        ["What do I need for the spreadsheet?", "Any spreadsheet app that opens .xlsx, including free online ones (import the file)."],
        ["Will it make me profitable?", "No planner can promise that. It helps you prepare, follow your own rules and review honestly; results depend on you and the market."],
        ["Does it connect to my broker?", "No. You write or type your own entries. Nothing is sent anywhere."],
    ],
    "refund": "Digital download: files can't be returned, but if something does not work as described, message me within 14 days and I will fix it or refund you.",
    "price_reasoning": ("$14: printable trading planners and journals list from about $7 (a one-page checklist, CHF 7) and $9.89 (a 1-page journal in "
                        "A4 + Letter) up to $29.99 (a printable workbook with daily, weekly and monthly reviews); Etsy trading journal spreadsheets "
                        "mostly sit between $9 and $25. Ours has 16 pages in two sizes plus a working spreadsheet, so $14 is fair for a new shop "
                        "with no reviews, and $17 with the eval tracker makes a natural $25 bundle later. Try $12 if views don't turn into sales; $17 after 10 good reviews."),
    "comparables": [
        {"what": "1-page fillable + printable trading journal (A4 and Letter)", "price": "$9.89", "where": "Gumroad", "url": "https://phoenixreverie.gumroad.com/l/kstdk", "seen": "2026-11-14"},
        {"what": "Printable trading workbook: daily, weekly, monthly review, pre-market planning", "price": "$29.99", "where": "Payhip", "url": "https://payhip.com/b/3sMFc", "seen": "2026-11-14"},
        {"what": "Daily trading checklist: pre-market routine, pre-trade check, post-trade review (1 page)", "price": "CHF 7", "where": "Whop", "url": "https://whop.com/dawinchy/dawinchy-daily-trading-checklist/", "seen": "2026-11-14"},
        {"what": "Trading journal spreadsheets (range across listings, most $9-25)", "price": "about $1 to $80", "where": "Etsy", "url": "https://www.etsy.com/listing/1461681856", "seen": "2026-11-14"},
    ],
    "image_notes": ["the planner pages", "all 16 pages", "the spreadsheet journal's dashboard", "square 1", "square 2", "square 3"],
    "rules": [
        "Never show profits, P&L screenshots, win rates or 'pass your evaluation' wording in the listing, pictures or tags.",
        "No firm, broker or platform names; keep the risk line at the end of the description.",
        "Gumroad reviews trading-related products more closely: keep the education-only wording.",
        "Etsy: 'I did', digital download; the description says AI tools helped.",
    ],
}


def make_zip(out: str | None = None) -> str:
    return K.make_zip(BUYER, TOP, ZIP, out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.products.build_trader_planner")
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
