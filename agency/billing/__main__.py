"""python -m agency.billing: the close-and-collect kit (team B6 "get paid", 2026-11-14). Run it from the bot folder.

The ones you use:
  python -m agency.billing setup --name "Your Web Co" --email you@example.com --phone "555-0100" --pay-link growth=https://buy.stripe.com/...
  python -m agency.billing kit "Rivera Plumbing" --open      proposal + agreement + first invoice for a client in your CRM file
  python -m agency.billing paid INV-2026-0001                they paid: invoice PAID, money in the ledger, their monthly plan starts
  python -m agency.billing import payments.csv               the monthly payments Stripe took by itself (Stripe > Payments > Export)
  python -m agency.billing plan cancel "Rivera Plumbing" --last-day 2027-01-31
  python -m agency.billing summary                           MRR, churn, cash; also writes money_out/agency.json for the money pages
More: proposal, agreement, invoice, payment, plan start / change, void, list, demo (sample documents, nothing saved to your data).
Every command: --data DIR (default data/agency, or AGENCY_DATA_DIR)  --clients FILE (default data/agency/clients.json, crm.json or
leads.json)  --today YYYY-MM-DD. Nothing here sends email, charges a card or talks to the internet: you send the files yourself.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time
import webbrowser

from . import core as C
from . import render as R
from . import store as S


def say(*a) -> None:
    print(*a, flush=True)


def ctx(a) -> tuple[S.Store, str]:
    today = a.today or os.environ.get("AGENCY_TODAY") or C.today_et(a.now)
    if not C.is_date(today):
        raise S.StoreError(f"--today must be YYYY-MM-DD, got {today!r}")
    return S.Store(a.data), today


def get_client(st: S.Store, a, key: str) -> dict:
    rows, src = st.clients(a.clients)
    c = C.find_client(rows, key)
    if not c:
        some = ", ".join(r["name"] for r in rows[:6])
        raise S.StoreError(f"no client '{key}' in {src}" + (f". Some names there: {some}" if some else
                           ". Save your CRM file as data/agency/clients.json or pass --clients FILE."))
    return c


def open_files(paths: list, a) -> None:
    if getattr(a, "pdf", False):
        for p in list(paths):
            pdf, msg = R.to_pdf(p)
            say(f"  {msg}: {pdf}" if pdf else f"  {msg}")
    if getattr(a, "open", False):
        for p in paths:
            webbrowser.open(pathlib.Path(p).resolve().as_uri())


def refresh(st: S.Store, today: str, a) -> None:
    """rebuild money_out/agency.json after a change (never stops the command)"""
    try:
        path, doc = S.write_summary(st, today, a.now or time.time(), out=a.summary_out or os.environ.get("AGENCY_SUMMARY_OUT"))
        say(f"  summary: MRR {C.usd(doc['mrr']['now'], whole=True)} from {doc['mrr']['clients']} clients -> {path}")
    except (OSError, S.StoreError) as e:
        say(f"  (summary not updated: {e})")


def doc_path(st: S.Store, client: dict, kind: str, today: str) -> str:
    return os.path.join(st.docs_dir, S.safe_name(client["id"]), f"{kind}-{today}.html")


def bill_to(c: dict) -> dict:
    return {k: c.get(k) or "" for k in ("name", "trade", "city", "email", "phone")}


def has_plan_history(st: S.Store, client_id: str) -> bool:
    return any(isinstance(p, dict) and p.get("client_id") == client_id for p in st.ledger()["plans"])


def draft_invoice(st: S.Store, a, client: dict, pkg: dict, biz: dict, today: str, setup: bool, monthly_line: bool) -> dict:
    led = st.ledger()
    run = st.running_plan(led, client["id"], today)
    monthly = C.cents(run["monthly_usd"]) if run else C.cents(pkg["monthly_usd"])
    ym = a.month or C.month_of(today)
    if not C.is_month(ym):
        raise S.StoreError(f"--month must be YYYY-MM, got {ym!r}")
    lines = []
    if setup:
        sd = C.cents(pkg["setup_usd"])
        lines.append(C.make_line(f"Website setup ({pkg['name']} plan)" + (": included" if sd == 0 else ""), 1, sd))
    if monthly_line:
        lines.append(C.make_line(f"{pkg['name']} website plan, {C.month_name(ym)}", 1, monthly))
    lines += [C.parse_item(s) for s in (a.item or [])]
    if not lines:
        raise S.StoreError("an invoice needs at least one line (the monthly plan, --setup or --item \"Description=Price\")")
    t = C.totals(lines, biz.get("tax_rate_pct") or 0)
    pay = a.pay_link or R.pay_link_for(biz, pkg["id"]) or ""
    if a.pay_link and not R.safe_url(a.pay_link):
        raise S.StoreError("--pay-link must be a full https:// link")
    td = C.dec(biz.get("terms_days"))
    due = C.add_days(today, int(a.due_days) if a.due_days is not None else int(td) if td is not None and 0 <= td <= 90 else 7)
    return {"client_id": client["id"], "client_name": client["name"], "bill_to": bill_to(client), "package": pkg["id"], "period": ym,
            "lines": lines, **t, "due": due, "pay_link": pay, "autopay": bool(a.autopay), "first": not has_plan_history(st, client["id"]),
            "monthly_usd": C.f2(monthly) if monthly_line else 0.0, "setup_usd": C.f2(pkg["setup_usd"]) if setup else 0.0}


def write_invoice(st: S.Store, inv: dict, biz: dict) -> str:
    return R.write(os.path.join(st.inv_dir, f"{inv['no']}.html"), R.invoice_html(inv, inv.get("bill_to") or {}, biz))


# ------------------------------------------------------------------------------------------------ commands
def cmd_setup(a) -> int:
    st, _ = ctx(a)
    up = {}
    for flag, key in (("name", "business_name"), ("owner", "owner_name"), ("email", "email"), ("phone", "phone"), ("city", "city"),
                      ("state", "state"), ("website", "website"), ("pay_note", "pay_note"), ("tagline", "tagline")):
        v = getattr(a, flag)
        if v is not None:
            up[key] = C.text(v, 160)
    if a.email is not None and a.email and not C.EMAIL_RE.match(a.email):
        raise S.StoreError(f"that email does not look right: {a.email!r}")
    if a.website and not R.safe_url(a.website):
        raise S.StoreError("--website must start with https://")
    if a.accent is not None:
        if not __import__("re").fullmatch(r"#[0-9a-fA-F]{6}", a.accent):
            raise S.StoreError("--accent must look like #1f5f55")
        up["accent"] = a.accent
    links = {}
    for s in a.pay_link or []:
        k, _, u = s.partition("=")
        if not k or not u.startswith("https://") or not R.safe_url(u):
            raise S.StoreError(f"--pay-link needs package=https://link, got {s!r}")
        links[k.strip().lower()] = u.strip()
    if links:
        up["pay_links"] = links
    for flag, key, lo, hi in (("tax_rate", "tax_rate_pct", 0, 25), ("goal_mrr", "goal_mrr", 1, 10 ** 7), ("terms_days", "terms_days", 0, 90),
                              ("invoice_start", "invoice_start", 1, 10 ** 6)):
        v = getattr(a, flag)
        if v is not None:
            d = C.dec(v)
            if d is None or not lo <= d <= hi:
                raise S.StoreError(f"--{flag.replace('_', '-')} must be between {lo} and {hi}")
            up[key] = float(d) if key == "tax_rate_pct" else int(d)
    if a.publish is not None:
        up["publish_summary"] = a.publish == "yes"
    biz = st.save_business(up) if up else st.business()
    say(f"Your agency: {biz.get('business_name') or '(no name yet)'} | {biz.get('email') or 'no email'} | {biz.get('phone') or 'no phone'}")
    say(f"  payment links: {', '.join(f'{k}={v}' for k, v in (biz.get('pay_links') or {}).items()) or 'none yet (see agency/billing/PAYMENTS.md)'}")
    say(f"  sales tax on invoices: {biz.get('tax_rate_pct') or 0}%   goal: ${biz.get('goal_mrr')} MRR   saved in {st.biz_path}")
    return 0


def cmd_doc(a, kind: str) -> int:
    st, today = ctx(a)
    c = get_client(st, a, a.client)
    pkg, biz = C.plan_for(c, st.packages(), a.package), st.business()
    html = R.proposal_html(c, pkg, biz, today) if kind == "proposal" else R.agreement_html(c, pkg, biz, today)
    p = R.write(doc_path(st, c, kind, today), html)
    say(f"{kind.title()} for {c['name']} ({pkg['name']}, {C.usd(pkg['setup_usd'], whole=True)} setup + {C.usd(pkg['monthly_usd'])}/month): {p}")
    open_files([p], a)
    return 0


def cmd_invoice(a) -> int:
    st, today = ctx(a)
    c = get_client(st, a, a.client)
    pkg, biz = C.plan_for(c, st.packages(), a.package), st.business()
    draft = draft_invoice(st, a, c, pkg, biz, today, setup=a.setup, monthly_line=not a.no_monthly)
    if a.dry_run:
        say(f"Dry run (no number used): total {C.usd(draft['total_usd'])}, due {draft['due']}, pay link {draft['pay_link'] or 'none'}")
        return 0
    inv = st.issue(draft, today, biz.get("invoice_prefix") or "INV", int(C.dec(biz.get("invoice_start")) or 1))
    p = write_invoice(st, inv, biz)
    say(f"Invoice {inv['no']} for {c['name']}: {C.usd(inv['total_usd'])}, due {inv['due']}: {p}")
    say(f"  when they pay: python -m agency.billing paid {inv['no']}")
    refresh(st, today, a)
    open_files([p], a)
    return 0


def cmd_kit(a) -> int:
    st, today = ctx(a)
    c = get_client(st, a, a.client)
    pkg, biz = C.plan_for(c, st.packages(), a.package), st.business()
    made = [("Proposal", R.write(doc_path(st, c, "proposal", today), R.proposal_html(c, pkg, biz, today))),
            ("Agreement (template)", R.write(doc_path(st, c, "agreement", today), R.agreement_html(c, pkg, biz, today)))]
    inv = None
    if not a.no_invoice:
        a.month, a.item, a.pay_link, a.due_days, a.autopay = a.month, [], None, None, False
        inv = st.issue(draft_invoice(st, a, c, pkg, biz, today, setup=True, monthly_line=True), today, biz.get("invoice_prefix") or "INV",
                       int(C.dec(biz.get("invoice_start")) or 1))
        made.append((f"Invoice {inv['no']} ({C.usd(inv['total_usd'])})", write_invoice(st, inv, biz)))
    say(f"Close-and-collect kit for {c['name']}: {pkg['name']} plan, {C.usd(pkg['setup_usd'], whole=True)} setup + {C.usd(pkg['monthly_usd'])}/month")
    for what, p in made:
        say(f"  {what}: {p}")
    if not biz.get("configured"):
        say("  ! Your business name is not set: python -m agency.billing setup --name \"Your Web Co\" --email you@example.com")
    if inv and not inv.get("pay_link"):
        say(f"  ! No payment link for the {pkg['id']} plan: python -m agency.billing setup --pay-link {pkg['id']}=https://buy.stripe.com/...")
    if inv:
        say(f"  Next: send the three files. When they pay: python -m agency.billing paid {inv['no']}")
        refresh(st, today, a)
    open_files([p for _, p in made], a)
    return 0


def cmd_paid(a) -> int:
    st, today = ctx(a)
    biz = st.business()
    inv, pay, plan = st.mark_paid(a.invoice, a.date or today, a.amount, a.fee, a.method, biz.get("fee_model"), start_plan=not a.no_plan)
    p = write_invoice(st, inv, biz)
    say(f"Paid: {inv['no']} {C.usd(pay['amount_usd'])} on {pay['date']} (fee {C.usd(pay['fee_usd'])}{', estimated' if pay.get('fee_estimated') else ''})."
        + (f" Balance left {C.usd(inv['balance_usd'])}." if inv["status"] != "paid" else " Paid in full."))
    if plan:
        say(f"  Plan started: {C.usd(plan['monthly_usd'])}/month from {plan['start']} (stop it with: plan cancel {inv['client_id']} --last-day YYYY-MM-DD)")
    say(f"  invoice page updated: {p}")
    refresh(st, today, a)
    return 0


def cmd_payment(a) -> int:
    st, today = ctx(a)
    c = get_client(st, a, a.client)
    biz = st.business()
    pay = st.add_payment(c["id"], a.amount, a.date or today, a.kind, a.fee, a.method, note=a.note or "", fee_model=biz.get("fee_model"))
    say(f"Recorded: {c['name']} {C.usd(pay['amount_usd'])} ({pay['kind']}) on {pay['date']}, fee {C.usd(pay['fee_usd'])}"
        + (" (estimated)" if pay.get("fee_estimated") else ""))
    refresh(st, today, a)
    return 0


def cmd_import(a) -> int:
    st, today = ctx(a)
    rows, _ = st.clients(a.clients)
    biz = st.business()
    res = st.import_csv(a.file, rows, today, biz.get("fee_model"), method=a.source)
    say(f"Imported {res['added']} payment(s) from {os.path.basename(a.file)}: {C.usd(res['in_usd'])} in, {C.usd(res['fees_usd'])} fees, "
        f"{C.usd(res['refunds_usd'])} refunds. Already had {res['dupes']}, skipped {res['skipped']} (failed / not USD / no amount).")
    if res["unmatched"]:
        say(f"  {res['unmatched']} payment(s) matched no client by email or name: they count as income under 'unmatched'.")
    if res["no_plan"]:
        say("  These clients paid but have no monthly plan in the ledger (MRR misses them): " + ", ".join(res["no_plan"][:8]))
        say("  -> python -m agency.billing plan start <client> --monthly <price> --date <first payment day>")
    refresh(st, today, a)
    return 0


def cmd_plan(a) -> int:
    st, today = ctx(a)
    c = get_client(st, a, a.client)
    if a.action == "start":
        price = a.monthly if a.monthly is not None else C.plan_for(c, st.packages(), a.package)["monthly_usd"]
        p = st.start_plan(c["id"], price, a.date or today, a.package or c.get("package") or "")
        say(f"Plan started: {c['name']} {C.usd(p['monthly_usd'])}/month from {p['start']}.")
    elif a.action == "change":
        if a.monthly is None:
            raise S.StoreError("plan change needs --monthly NEW_PRICE")
        old, new = st.change_plan(c["id"], a.monthly, a.date or today, a.package or "")
        say(f"Plan changed: {c['name']} {C.usd(old['monthly_usd'])} -> {C.usd(new['monthly_usd'])}/month from {new['start']} (old plan's last day {old['end']}).")
    else:
        if not a.last_day:
            raise S.StoreError("plan cancel needs --last-day YYYY-MM-DD (the last day they are paid up to)")
        p = st.cancel_plan(c["id"], a.last_day, a.reason or "")
        say(f"Plan cancelled: {c['name']} {C.usd(p['monthly_usd'])}/month, last day {p['end']}. Remember to cancel the subscription in Stripe too.")
    refresh(st, today, a)
    return 0


def cmd_void(a) -> int:
    st, today = ctx(a)
    inv = st.void(a.invoice, a.reason or "")
    p = write_invoice(st, inv, st.business())
    say(f"Void: {inv['no']} (its number is never used again): {p}")
    refresh(st, today, a)
    return 0


def cmd_list(a) -> int:
    st, today = ctx(a)
    inv = st.invoices()["invoices"]
    say("| Invoice | Client | Issued | Total | Balance | Status |")
    say("|---|---|---|---|---|---|")
    for i in inv[-40:]:
        if isinstance(i, dict):
            say(f"| {i.get('no')} | {i.get('client_name') or i.get('client_id')} | {i.get('issued')} | {C.usd(i.get('total_usd'))} | "
                f"{C.usd(i.get('balance_usd', i.get('total_usd')))} | {i.get('status')} |")
    led = st.ledger()
    say("")
    say("| Plan | $/month | From | Last day |")
    say("|---|---|---|---|")
    for p in led["plans"][-40:]:
        if isinstance(p, dict):
            say(f"| {p.get('client_id')} | {C.usd(p.get('monthly_usd'))} | {p.get('start')} | {p.get('end') or 'running'} |")
    return 0


def cmd_summary(a) -> int:
    st, today = ctx(a)
    path, s = S.write_summary(st, today, a.now or time.time(), out=a.out or a.summary_out or os.environ.get("AGENCY_SUMMARY_OUT"))
    m, g, cash, inv = s["mrr"], s["goal"], s["cash"], s["invoices"]
    lf = s["last_full_month"]
    rows = [("MRR (monthly recurring revenue)", f"{C.usd(m['now'], whole=True)} from {m['clients']} clients ({C.usd(m['arpa'], whole=True)} average)"),
            (f"Goal {C.usd(g['mrr'], whole=True)} MRR", "reached" if g["reached"] else f"{C.usd(g['left'], whole=True)} to go, about {g['clients_needed']} more clients"),
            ("Signed, starting later / cancelling", f"+{C.usd(m['scheduled_usd'], whole=True)} / -{C.usd(m['ending_usd'], whole=True)} a month")]
    if lf:
        rows.append((f"Churn in {C.month_name(lf['month'])}", f"{lf['churned_clients']} lost; logo {lf['logo_churn_pct'] if lf['logo_churn_pct'] is not None else '-'}%, "
                     f"MRR {lf['mrr_churn_pct'] if lf['mrr_churn_pct'] is not None else '-'}%"))
    rows += [("Cash this month", f"{C.usd(cash['month']['in'])} in, {C.usd(cash['month']['out'])} out (fees, refunds), net {C.usd(cash['month']['net'])}"),
             ("Cash all time", f"{C.usd(cash['all']['in'])} in, net {C.usd(cash['all']['net'])}"),
             ("Invoices open / overdue", f"{inv['open']} ({C.usd(inv['open_usd'])}) / {inv['overdue']} ({C.usd(inv['overdue_usd'])})")]
    say("| What | Result |")
    say("|---|---|")
    for k, v in rows:
        say(f"| {k} | {v} |")
    say(f"\nWritten: {path} (aggregates only, no client names)")
    return 0


def cmd_demo(a) -> int:
    """sample documents from the fixtures: nothing is read from or written to your data/agency files (no invoice number used)"""
    today = a.today or os.environ.get("AGENCY_TODAY") or C.today_et(a.now)
    out = os.path.abspath(a.out or os.path.join(S.data_dir(a.data), "demo"))
    clients, biz, pk = S.fixture_clients(), S.fixture_business(), S.Store.packages()
    c = C.find_client(clients, a.client or "c_demo_rivera") or clients[0]
    pkg = C.plan_for(c, pk)
    lines = [C.make_line(f"Website setup ({pkg['name']} plan): included", 1, pkg["setup_usd"]),
             C.make_line(f"{pkg['name']} website plan, {C.month_name(C.month_of(today))}", 1, pkg["monthly_usd"])]
    inv = {"no": "INV-" + today[:4] + "-SAMPLE", "issued": today, "due": C.add_days(today, 7), "period": C.month_of(today), "lines": lines,
           **C.totals(lines, 0), "status": "open", "pay_link": R.pay_link_for(biz, pkg["id"]) or ""}
    made = [R.write(os.path.join(out, "proposal-sample.html"), R.proposal_html(c, pkg, biz, today)),
            R.write(os.path.join(out, "agreement-sample.html"), R.agreement_html(c, pkg, biz, today)),
            R.write(os.path.join(out, "invoice-sample.html"), R.invoice_html(inv, c, biz))]
    say(f"Sample documents for {c['name']} (made-up data):")
    for p in made:
        say(f"  {p}")
    open_files(made, a)
    return 0


# ------------------------------------------------------------------------------------------------ the parser
def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data", help="the data folder (default data/agency, or AGENCY_DATA_DIR)")
    common.add_argument("--clients", help="the CRM file with the client records (default data/agency/clients.json, crm.json or leads.json)")
    common.add_argument("--today", help="YYYY-MM-DD (default: today in New York)")
    common.add_argument("--now", type=float, help=argparse.SUPPRESS)
    common.add_argument("--summary-out", dest="summary_out", help="where the summary JSON goes (default money_out/agency.json)")
    show = argparse.ArgumentParser(add_help=False)
    show.add_argument("--open", action="store_true", help="open the page(s) in your browser")
    show.add_argument("--pdf", action="store_true", help="also save a PDF next to each page (needs Edge or Chrome)")
    ap = argparse.ArgumentParser(prog="python -m agency.billing", description="Close and collect: proposal, agreement, invoices, payments, MRR.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n", 1)[1])
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("setup", parents=[common], help="your agency's name, contact, colour and payment links")
    for f in ("name", "owner", "email", "phone", "city", "state", "website", "accent", "tagline"):
        s.add_argument("--" + f)
    s.add_argument("--pay-note", dest="pay_note")
    s.add_argument("--pay-link", dest="pay_link", action="append", help="package=https://buy.stripe.com/... (repeat for each package)")
    s.add_argument("--tax-rate", dest="tax_rate", help="sales tax % added to invoices (0 if your state does not tax this service)")
    s.add_argument("--goal-mrr", dest="goal_mrr")
    s.add_argument("--terms-days", dest="terms_days")
    s.add_argument("--invoice-start", dest="invoice_start", help="the first invoice number (only moves numbers up, never back)")
    s.add_argument("--publish", choices=("yes", "no"), help="let the PUBLIC money scoreboard show agency totals (default no)")
    for k in ("proposal", "agreement"):
        d = sub.add_parser(k, parents=[common, show], help=f"the {k} for one client")
        d.add_argument("client", help="the client's id or name in your CRM file")
        d.add_argument("--package")
    k = sub.add_parser("kit", parents=[common, show], help="proposal + agreement + first invoice in one go")
    k.add_argument("client")
    k.add_argument("--package")
    k.add_argument("--month")
    k.add_argument("--no-invoice", dest="no_invoice", action="store_true")
    i = sub.add_parser("invoice", parents=[common, show], help="a numbered invoice")
    i.add_argument("client")
    i.add_argument("--package")
    i.add_argument("--month", help="the month the plan line is for, YYYY-MM (default this month)")
    i.add_argument("--setup", action="store_true", help="add the setup line")
    i.add_argument("--no-monthly", dest="no_monthly", action="store_true", help="no monthly plan line")
    i.add_argument("--item", action="append", help="\"Extra page=50\", \"Extra page=50x2\", \"Discount=-25\", \"Domain=15 notax\"")
    i.add_argument("--due-days", dest="due_days", type=int)
    i.add_argument("--pay-link", dest="pay_link")
    i.add_argument("--autopay", action="store_true", help="say it is charged automatically to the saved card (no pay button)")
    i.add_argument("--dry-run", dest="dry_run", action="store_true")
    p = sub.add_parser("paid", parents=[common], help="an invoice was paid")
    p.add_argument("invoice")
    p.add_argument("--date")
    p.add_argument("--amount", help="default: the whole balance")
    p.add_argument("--fee", help="the processor fee from your receipt (default: estimated)")
    p.add_argument("--method", default="stripe")
    p.add_argument("--no-plan", dest="no_plan", action="store_true", help="do not start the monthly plan")
    y = sub.add_parser("payment", parents=[common], help="a payment without an invoice (a monthly charge, a one-off job, a refund)")
    y.add_argument("client")
    y.add_argument("--amount", required=True)
    y.add_argument("--date")
    y.add_argument("--fee")
    y.add_argument("--kind", default="monthly", choices=C.PAY_KINDS)
    y.add_argument("--method", default="stripe")
    y.add_argument("--note")
    m = sub.add_parser("import", parents=[common], help="payments from a Stripe / Square / PayPal CSV export")
    m.add_argument("file")
    m.add_argument("--source", default="stripe")
    pl = sub.add_parser("plan", parents=[common], help="start, change or cancel a client's monthly plan")
    pl.add_argument("action", choices=("start", "change", "cancel"))
    pl.add_argument("client")
    pl.add_argument("--monthly")
    pl.add_argument("--date", help="start / change date (default today)")
    pl.add_argument("--last-day", dest="last_day", help="cancel: the last day they are paid up to")
    pl.add_argument("--package")
    pl.add_argument("--reason")
    v = sub.add_parser("void", parents=[common], help="cancel an unpaid invoice (its number is never reused)")
    v.add_argument("invoice")
    v.add_argument("--reason")
    sub.add_parser("list", parents=[common], help="invoices and plans")
    su = sub.add_parser("summary", parents=[common], help="MRR, churn and cash; writes the money pages' JSON")
    su.add_argument("--out")
    dm = sub.add_parser("demo", parents=[common, show], help="sample documents from the fixtures (nothing saved to your data)")
    dm.add_argument("client", nargs="?")
    dm.add_argument("--out")
    return ap


CMDS = {"setup": cmd_setup, "proposal": lambda a: cmd_doc(a, "proposal"), "agreement": lambda a: cmd_doc(a, "agreement"), "kit": cmd_kit,
        "invoice": cmd_invoice, "paid": cmd_paid, "payment": cmd_payment, "import": cmd_import, "plan": cmd_plan, "void": cmd_void,
        "list": cmd_list, "summary": cmd_summary, "demo": cmd_demo}


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")       # a Windows console never crashes on a character
    except (AttributeError, ValueError):
        pass
    ap = parser()
    a = ap.parse_args(argv)
    if not a.cmd:
        say(__doc__.strip())
        return 0
    try:
        return CMDS[a.cmd](a)
    except (S.StoreError, ValueError) as e:
        say(f"Stopped: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
