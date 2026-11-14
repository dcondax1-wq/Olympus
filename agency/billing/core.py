"""AGENCY BILLING core (team B6 "get paid", 2026-11-14): the pure parts of the close-and-collect kit. No file, no clock, no network.

  money      Decimal, rounded half-up to the cent (an invoice never shows 0.1 + 0.2 = 0.30000000000000004)
  clients    the shared client record {"id","name","trade","city","phone","email","site_url","demo_url","status","package",
             "setup_usd","monthly_usd","notes"}; a record's own prices win over the package's
  invoices   line items -> subtotal, tax (only on taxable lines), total, paid, balance; numbers look like INV-2026-0001
             (prefix, year of issue, ONE global sequence that never resets and never repeats: store.py hands them out)
  MRR        monthly recurring revenue from the plans in the ledger. A plan is {client_id, monthly_usd, start, end}; "end" is the
             LAST day of service (inclusive), null while it runs. A client's MRR on day D = the plans running on D, except a plan
             that ends on D with nothing starting on D + 1 (it will not renew). Each month: MRR at the start (the day before the
             1st) and at the end (the last day, or today for this month), split into new, reactivation, expansion, contraction and
             churn per client, so start + new + reactivation + expansion - contraction - churn = end, always.
  churn      logo churn % = clients lost / clients at the start of the month; MRR churn % = (churned + contraction) / MRR at the
             start; net MRR churn % = (churned + contraction - expansion) / MRR at the start (negative = growth from existing clients)
  summary    the JSON the OLYMPUS money pages read (kind "olympus-agency-income"): MRR, churn by month, cash in / out by week,
             month and all time, daily cash rows for the money scoreboard, invoice counts. Aggregates ONLY: no client name, id,
             email or phone ever goes in it.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0")
CLIENT_FIELDS = ("id", "name", "trade", "city", "phone", "email", "site_url", "demo_url", "status", "package", "setup_usd", "monthly_usd", "notes")
PAY_KINDS = ("monthly", "setup", "one_time", "refund")
NO_RE = re.compile(r"^([A-Z]{2,8})-(\d{4})-(\d{4,})$")
EMAIL_RE = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+$")
SUMMARY_KIND = "olympus-agency-income"
GOAL_MRR = 1000
GENERIC_INCLUDES = ["A mobile website built for your business", "Hosting, security certificate (https) and backups",
                    "Small edits each month", "Help by email or text"]


# ------------------------------------------------------------------------------------------------ numbers and text
def dec(v) -> Decimal | None:
    """A finite number as Decimal, else None. '$1,234.50' -> 1234.50, '(12.50)' -> -12.50; bool, None, nan, inf and junk -> None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, Decimal):
        d = v
    elif isinstance(v, int):
        d = Decimal(v)
    elif isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            return None
        d = Decimal(repr(v))
    elif isinstance(v, str):
        s = v.strip().replace("$", "").replace(",", "").replace("USD", "").strip()
        neg = s.startswith("(") and s.endswith(")")
        s = s[1:-1].strip() if neg else s
        if not s:
            return None
        try:
            d = Decimal(s)
        except InvalidOperation:
            return None
        d = -d if neg else d
    else:
        return None
    return d if d.is_finite() else None


def cents(v) -> Decimal:
    d = dec(v)
    return (d if d is not None else ZERO).quantize(CENT, rounding=ROUND_HALF_UP)


def f2(v) -> float:
    """a cent amount for JSON (0.0 for nothing)"""
    return float(cents(v)) + 0.0


def dsum(xs) -> Decimal:
    return sum((cents(x) for x in xs), ZERO)


def usd(v, signed=False, whole=False) -> str:
    """$1,234.50 (whole=True: $1,235); signed adds + to a gain; '-' when not a number"""
    d = dec(v)
    if d is None:
        return "-"
    q = d.quantize(Decimal("1") if whole else CENT, rounding=ROUND_HALF_UP)
    s = ("${:,.0f}" if whole else "${:,.2f}").format(abs(q))
    if q == 0:
        return s
    return ("-" if q < 0 else "+" if signed else "") + s


def pct(n, d) -> float | None:
    """n / d as a percentage with 2 decimals, None when d is 0"""
    n, d = dec(n) or ZERO, dec(d) or ZERO
    if d == 0:
        return None
    return float((n / d * 100).quantize(CENT, rounding=ROUND_HALF_UP)) + 0.0


def text(v, n=200) -> str:
    if isinstance(v, bool) or v is None:
        return ""
    s = v if isinstance(v, str) else str(v) if isinstance(v, (int, float, Decimal)) else ""
    return " ".join(s.split())[:n]


# ------------------------------------------------------------------------------------------------ dates (ISO strings)
def is_date(s) -> bool:
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    try:
        dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def is_month(s) -> bool:
    return isinstance(s, str) and bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", s))


def d_of(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def add_days(s: str, n: int) -> str:
    return (d_of(s) + dt.timedelta(days=n)).isoformat()


def month_of(s: str) -> str:
    return s[:7]


def month_first(ym: str) -> str:
    return ym + "-01"


def month_last(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    return (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).isoformat()


def add_months_ym(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7]) - 1 + n
    return f"{y + m // 12:04d}-{m % 12 + 1:02d}"


def add_months(s: str, n: int) -> str:
    """the same day n months later, clamped (31 Jan + 1 month = 28/29 Feb)"""
    ym = add_months_ym(s[:7], n)
    return min(ym + s[7:], month_last(ym))


def week_start(s: str) -> str:
    """Monday of the week of s"""
    return add_days(s, -d_of(s).weekday())


def month_name(ym: str) -> str:
    return dt.date(int(ym[:4]), int(ym[5:7]), 1).strftime("%B %Y")


def nice_date(s: str) -> str:
    d = d_of(s)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def today_et(now_s: float | None = None) -> str:
    """today in New York (the owner's day), a plain fallback when the time zone data is missing"""
    t = dt.datetime.now(dt.timezone.utc).timestamp() if now_s is None else float(now_s)
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(t, ZoneInfo("America/New_York")).date().isoformat()
    except Exception:  # noqa: BLE001 (Windows without tzdata)
        return dt.datetime.fromtimestamp(t - 5 * 3600, dt.timezone.utc).date().isoformat()


# ------------------------------------------------------------------------------------------------ clients and packages
def norm_client(rec) -> dict | None:
    """the shared client record, cleaned: every field a short string except the two prices (float or None). No id or name -> None."""
    if not isinstance(rec, dict):
        return None
    cid, name = text(rec.get("id"), 64), text(rec.get("name"), 120)
    if not cid or not name:
        return None
    out = {k: text(rec.get(k), 400 if k == "notes" else 160) for k in CLIENT_FIELDS if k not in ("setup_usd", "monthly_usd")}
    out["id"], out["name"] = cid, name
    out["package"] = out["package"].lower()
    for k in ("setup_usd", "monthly_usd"):
        d = dec(rec.get(k))
        out[k] = f2(d) if d is not None and d >= 0 else None
    return out


def clients_from(doc) -> list:
    """the records of a CRM file: a list, {"clients" | "leads" | "records" | "items": [...]}, or {id: record}. Bad rows are dropped."""
    rows = []
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        for k in ("clients", "leads", "records", "items"):
            if isinstance(doc.get(k), list):
                rows = doc[k]
                break
        else:
            rows = [dict(v, id=v.get("id") or k) for k, v in doc.items() if isinstance(v, dict)]
    out = []
    for r in rows[:20000]:
        c = norm_client(r)
        if c:
            out.append(c)
    return out


def find_client(clients: list, key: str) -> dict | None:
    """by id (exact), else by name (case-insensitive, exact), else a unique name that contains the key"""
    k = text(key, 120)
    if not k:
        return None
    for c in clients:
        if c["id"] == k:
            return c
    low = k.lower()
    for c in clients:
        if c["name"].lower() == low:
            return c
    hits = [c for c in clients if low in c["name"].lower()]
    return hits[0] if len(hits) == 1 else None


def packages_from(doc) -> dict:
    out = {}
    for p in (doc.get("packages") if isinstance(doc, dict) else doc) or []:
        if not isinstance(p, dict) or not text(p.get("id"), 40):
            continue
        pid = text(p["id"], 40).lower()
        inc = [text(x, 160) for x in (p.get("includes") or []) if text(x, 160)][:12]
        out[pid] = {"id": pid, "name": text(p.get("name"), 60) or pid.title(), "tagline": text(p.get("tagline"), 200),
                    "setup_usd": f2(p.get("setup_usd")), "monthly_usd": f2(p.get("monthly_usd")), "includes": inc or list(GENERIC_INCLUDES),
                    "edits_per_month": int(dec(p.get("edits_per_month")) or 1), "live_days": int(dec(p.get("live_days")) or 7),
                    "support_days": int(dec(p.get("support_days")) or 2), "min_term_months": int(dec(p.get("min_term_months")) or 0),
                    "notice_days": int(dec(p.get("notice_days")) or 30)}
    return out


def plan_for(client: dict, packages: dict, override: str | None = None) -> dict:
    """the package a document is about. The client's own setup / monthly price wins, unless another package is asked for."""
    pid = text(override or client.get("package") or "", 40).lower()
    base = packages.get(pid)
    if base is None:
        base = {"id": pid or "custom", "name": (pid.replace("_", " ").title() or "Website plan"), "tagline": "", "setup_usd": 0.0,
                "monthly_usd": 0.0, "includes": list(GENERIC_INCLUDES), "edits_per_month": 1, "live_days": 7, "support_days": 2,
                "min_term_months": 0, "notice_days": 30}
    out = dict(base)
    own = not override or pid == (client.get("package") or "").lower()
    if own:
        for k in ("setup_usd", "monthly_usd"):
            if client.get(k) is not None:
                out[k] = client[k]
    return out


# ------------------------------------------------------------------------------------------------ invoices
def make_line(desc, qty=1, unit=0, taxable=True) -> dict:
    """one invoice line; raises ValueError on a bad one (no text, qty not above 0, a silly amount)"""
    d = text(desc, 200)
    q, u = dec(qty), dec(unit)
    if not d:
        raise ValueError("an invoice line needs a description")
    if q is None or q <= 0 or q > 10000:
        raise ValueError(f"bad quantity for '{d}': {qty!r}")
    if u is None or abs(u) > 1_000_000:
        raise ValueError(f"bad price for '{d}': {unit!r}")
    q = q.quantize(CENT, rounding=ROUND_HALF_UP)
    return {"desc": d, "qty": float(q) + 0.0, "unit_usd": f2(u), "amount_usd": f2(q * cents(u)), "taxable": bool(taxable)}


def parse_item(s: str) -> dict:
    """the CLI's --item "Extra page=50", "Extra page=50x2", "Discount=-25", "Domain=15 notax" -> a line"""
    raw = text(s, 240)
    if "=" not in raw:
        raise ValueError(f"--item needs 'description=price', got {s!r}")
    desc, rest = raw.rsplit("=", 1)
    parts = rest.split()
    taxable = "notax" not in [p.lower() for p in parts[1:]]
    amt = parts[0] if parts else ""
    qty = "1"
    if "x" in amt.lower():
        amt, qty = re.split(r"[xX]", amt, maxsplit=1)
    return make_line(desc, qty, amt, taxable)


def totals(lines: list, tax_rate_pct=0, paid=0) -> dict:
    """subtotal, tax on the taxable lines (half-up to the cent), total, paid, balance. Raises ValueError for a total below $0."""
    rate = dec(tax_rate_pct)
    if rate is None or rate < 0 or rate > 25:
        raise ValueError(f"tax rate must be 0-25%, got {tax_rate_pct!r}")
    sub = dsum(l["amount_usd"] for l in lines)
    base = dsum(l["amount_usd"] for l in lines if l.get("taxable", True))
    tax = cents(max(base, ZERO) * rate / 100)
    total = sub + tax
    if total < 0:
        raise ValueError("an invoice total cannot be below $0")
    p = cents(paid)
    return {"subtotal_usd": f2(sub), "taxable_usd": f2(base), "tax_rate_pct": float(rate) + 0.0, "tax_usd": f2(tax), "total_usd": f2(total),
            "paid_usd": f2(p), "balance_usd": f2(max(total - p, ZERO))}


def fmt_no(prefix: str, year: int, seq: int) -> str:
    return f"{prefix}-{int(year):04d}-{int(seq):04d}"


def seq_of(no) -> int | None:
    m = NO_RE.match(no or "") if isinstance(no, str) else None
    return int(m.group(3)) if m else None


def est_fee(amount, model: dict | None) -> Decimal:
    """the processor fee of one payment by the business's fee model (default 2.9% + $0.30 + 0.7% = a Stripe subscription link)"""
    m = model if isinstance(model, dict) else {}
    a = dec(amount) or ZERO
    if a <= 0:
        return ZERO
    p, x, f = dec(m.get("pct")), dec(m.get("extra_pct")), dec(m.get("fixed"))
    p, x, f = (Decimal("2.9") if p is None else p), (Decimal("0.7") if x is None else x), (Decimal("0.30") if f is None else f)
    return cents(a * (p + x) / 100 + f)


# ------------------------------------------------------------------------------------------------ the ledger: plans and payments
def norm_plan(p) -> dict | None:
    if not isinstance(p, dict):
        return None
    cid, m = text(p.get("client_id"), 64), dec(p.get("monthly_usd"))
    start, end = p.get("start"), p.get("end")
    if not cid or m is None or m <= 0 or m > 100_000 or not is_date(start) or (end is not None and not is_date(end)):
        return None
    if end is not None and end < start:
        return None
    return {"client_id": cid, "monthly": cents(m), "start": start, "end": end, "package": text(p.get("package"), 40)}


def norm_payment(p) -> dict | None:
    if not isinstance(p, dict):
        return None
    a, fee = dec(p.get("amount_usd")), dec(p.get("fee_usd"))
    kind = text(p.get("kind"), 20) or "monthly"
    if a is None or a <= 0 or a > 1_000_000 or not is_date(p.get("date")) or kind not in PAY_KINDS:
        return None
    if fee is not None and (fee < 0 or fee > a):
        return None
    return {"id": text(p.get("id"), 80), "date": p["date"], "client_id": text(p.get("client_id"), 64), "amount": cents(a),
            "fee": cents(fee) if fee is not None else ZERO, "kind": kind, "invoice": text(p.get("invoice"), 40),
            "method": text(p.get("method"), 30), "est": bool(p.get("fee_estimated"))}


def by_client(plans: list) -> dict:
    out: dict = {}
    for p in plans:
        out.setdefault(p["client_id"], []).append(p)
    return out


def client_amt(ps: list, day: str) -> Decimal:
    """one client's MRR on a day: its plans running that day, minus a plan that ends that day with nothing starting the next day"""
    nxt = add_days(day, 1)
    tot = ZERO
    for p in ps:
        if p["start"] <= day and (p["end"] is None or p["end"] >= day):
            if p["end"] == day and not any(q["start"] == nxt for q in ps):
                continue
            tot += p["monthly"]
    return tot


def mrr_on(plans: list, day: str) -> tuple[Decimal, int]:
    """(MRR, paying clients) on a day"""
    tot, n = ZERO, 0
    for ps in by_client(plans).values():
        a = client_amt(ps, day)
        if a > 0:
            tot += a
            n += 1
    return tot, n


def movement(plans: list, ym: str, today: str) -> dict:
    """one month of MRR movement (this month: up to today)"""
    first, last = month_first(ym), min(month_last(ym), today)
    prev = add_days(first, -1)
    c = {k: ZERO for k in ("mrr_start", "mrr_end", "new", "reactivation", "expansion", "contraction", "churned")}
    n = {k: 0 for k in ("clients_start", "clients_end", "new_clients", "reactivated_clients", "churned_clients")}
    for ps in by_client(plans).values():
        a, b = client_amt(ps, prev), client_amt(ps, last)
        c["mrr_start"] += a
        c["mrr_end"] += b
        n["clients_start"] += a > 0
        n["clients_end"] += b > 0
        if a == 0 and b > 0:
            if any(p["start"] < first for p in ps):
                c["reactivation"] += b
                n["reactivated_clients"] += 1
            else:
                c["new"] += b
                n["new_clients"] += 1
        elif a > 0 and b == 0:
            c["churned"] += a
            n["churned_clients"] += 1
        elif a > 0 and b > 0:
            if b > a:
                c["expansion"] += b - a
            elif b < a:
                c["contraction"] += a - b
    out = {"month": ym, "partial": last < month_last(ym)}
    out.update({k: f2(v) for k, v in c.items()})
    out.update(n)
    out["net_change"] = f2(c["mrr_end"] - c["mrr_start"])
    out["logo_churn_pct"] = pct(n["churned_clients"], n["clients_start"])
    out["mrr_churn_pct"] = pct(c["churned"] + c["contraction"], c["mrr_start"])
    out["net_mrr_churn_pct"] = pct(c["churned"] + c["contraction"] - c["expansion"], c["mrr_start"])
    return out


def cash(pays: list, start: str, end: str) -> dict:
    sel = [p for p in pays if start <= p["date"] <= end]
    cin = sum((p["amount"] for p in sel if p["kind"] != "refund"), ZERO)
    ref = sum((p["amount"] for p in sel if p["kind"] == "refund"), ZERO)
    fees = sum((p["fee"] for p in sel), ZERO)
    return {"in": f2(cin), "refunds": f2(ref), "fees": f2(fees), "out": f2(ref + fees), "net": f2(cin - ref - fees), "payments": len(sel)}


def day_rows(pays: list) -> list:
    """[[date, cash in, cash out]] per day: in = client payments, out = refunds + processor fees (the scoreboard hook reads these)"""
    days: dict = {}
    for p in pays:
        row = days.setdefault(p["date"], [ZERO, ZERO])
        if p["kind"] == "refund":
            row[1] += p["amount"] + p["fee"]
        else:
            row[0] += p["amount"]
            row[1] += p["fee"]
    return [[d, f2(v[0]), f2(v[1])] for d, v in sorted(days.items())]


# ------------------------------------------------------------------------------------------------ a payments export (CSV) -> payments
CSV_COLS = {
    "id": ("id", "charge id", "payment id", "transaction id", "transaction_id", "payment_id"),
    "date": ("created date (utc)", "created (utc)", "created", "created_at", "date", "transaction date", "payment date"),
    "amount": ("amount", "gross", "gross amount", "amount (usd)", "total collected", "gross sales"),
    "refunded": ("amount refunded", "refunded amount", "amount_refunded", "refunds"),
    "fee": ("fee", "fees", "processing fee", "fee amount", "fee (usd)"),
    "status": ("status",),
    "currency": ("currency",),
    "email": ("customer email", "email", "from email address", "customer_email", "receipt email", "buyer email"),
    "name": ("customer name", "customer description", "name", "customer", "buyer name"),
    "desc": ("description", "item title", "subject", "note", "statement descriptor"),
}
OK_STATUS = ("", "paid", "succeeded", "completed", "complete", "captured", "settled", "success")


def csv_col(header, key: str):
    low = {h.strip().lower(): h for h in (header or []) if isinstance(h, str)}
    return next((low[c] for c in CSV_COLS[key] if c in low), None)


def any_date(v) -> str | None:
    """2026-11-14, 2026-11-14 15:30:00, 2026-11-14T15:30:00Z, 11/14/2026, 11/14/26 3:30 PM, Nov 14, 2026 -> 2026-11-14"""
    s = text(v, 40)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0) if is_date(m.group(0)) else None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b", s)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        iso = f"{y:04d}-{mo:02d}-{d:02d}"
        return iso if is_date(iso) else None
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y"):
        try:
            return dt.datetime.strptime(s[:20].strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def csv_payments(header, rows: list, clients: list) -> tuple[list, int]:
    """rows of a Stripe / Square / PayPal payments export -> ([{ext_id, date, client_id, amount, fee, refunded, matched}], skipped).
    Failed, pending or non-USD rows and rows without a date or a positive amount are skipped. A client is found by email, then name."""
    col = {k: csv_col(header, k) for k in CSV_COLS}
    if not col["date"] or not col["amount"]:
        raise ValueError("this file has no date or amount column: export the payments list (Stripe: Payments > Export)")
    by_mail = {c["email"].lower(): c for c in clients if c.get("email")}
    out, skipped = [], 0
    for r in rows:
        g = (lambda k: r.get(col[k]) if col[k] else None)  # noqa: E731
        status = text(g("status"), 30).lower()
        cur = text(g("currency"), 5).lower()
        a, d = dec(g("amount")), any_date(g("date"))
        if status not in OK_STATUS or (cur and cur != "usd") or a is None or a <= 0 or not d:
            skipped += 1
            continue
        fee = dec(g("fee"))
        ref = dec(g("refunded"))
        email, name, desc = text(g("email"), 160).lower(), text(g("name"), 120), text(g("desc"), 200).lower()
        c = by_mail.get(email) or (find_client(clients, name) if name else None)
        if not c and desc:
            hits = [x for x in clients if x["name"].lower() in desc or (len(x["id"]) >= 5 and re.search(r"\b" + re.escape(x["id"].lower()) + r"\b", desc))]
            c = hits[0] if len(hits) == 1 else None
        rid = text(g("id"), 80)
        out.append({"ext_id": ("csv:" + rid) if rid else f"row:{d}:{cents(a)}:{email or name.lower()}", "date": d,
                    "client_id": c["id"] if c else "unmatched", "amount": cents(a), "fee": cents(abs(fee)) if fee is not None else None,
                    "refunded": cents(abs(ref)) if ref is not None and ref != 0 else ZERO, "matched": bool(c)})
    return out, skipped


def invoice_stats(inv_doc, today: str) -> dict:
    s = {"issued": 0, "open": 0, "open_usd": ZERO, "overdue": 0, "overdue_usd": ZERO, "paid": 0, "void": 0}
    for i in (inv_doc.get("invoices") if isinstance(inv_doc, dict) else None) or []:
        if not isinstance(i, dict):
            continue
        s["issued"] += 1
        st = i.get("status")
        if st == "void":
            s["void"] += 1
        elif st == "paid":
            s["paid"] += 1
        else:
            bal = cents(i.get("balance_usd", i.get("total_usd")))
            s["open"] += 1
            s["open_usd"] += bal
            if is_date(i.get("due")) and i["due"] < today:
                s["overdue"] += 1
                s["overdue_usd"] += bal
    s["open_usd"], s["overdue_usd"] = f2(s["open_usd"]), f2(s["overdue_usd"])
    return s


def summary(ledger, invoices, today: str, now_s: float, goal_mrr=GOAL_MRR, publish=False, sample=False, default_price=149, months_max=24) -> dict:
    """the money pages' file (kind olympus-agency-income). Pure: the caller passes today and the clock. Aggregates only."""
    led = ledger if isinstance(ledger, dict) else {}
    raw_plans, raw_pays = led.get("plans") or [], led.get("payments") or []
    plans = [p for p in (norm_plan(x) for x in raw_plans[:20000]) if p]
    pays_all = [p for p in (norm_payment(x) for x in raw_pays[:100000]) if p]
    pays = [p for p in pays_all if p["date"] <= today]
    started = [p for p in plans if p["start"] <= today]
    mrr, clients = mrr_on(plans, today)
    arpa = cents(mrr / clients) if clients else ZERO
    nxt = add_days(today, 1)
    future = [p for p in plans if p["start"] > today]
    grouped = by_client(plans)
    ending = []
    for cid, ps in grouped.items():
        for p in ps:
            runs_now = p["start"] <= today and p["end"] is not None and p["end"] >= nxt
            if runs_now and not any(q["start"] == add_days(p["end"], 1) for q in ps):
                ending.append(p)
    # the months from the first plan or payment to this one (at most months_max)
    firsts = [p["start"] for p in started] + [p["date"] for p in pays]
    months = []
    if firsts:
        ym, last_ym = month_of(min(firsts)), month_of(today)
        span = []
        while ym <= last_ym:
            span.append(ym)
            ym = add_months_ym(ym, 1)
        for ym in span[-months_max:]:
            m = movement(plans, ym, today)
            m.update({("cash_" + k if k in ("in", "out", "net") else k): v for k, v in cash(pays, month_first(ym), min(month_last(ym), today)).items()})
            months.append(m)
    full = [m for m in months if not m["partial"]]
    lastfull = full[-1] if full else None
    goal = dec(goal_mrr) or Decimal(GOAL_MRR)
    left = max(goal - mrr, ZERO)
    price = arpa if clients else cents(default_price)
    need = int(math.ceil(float(left / price))) if left > 0 and price > 0 else 0
    wk, mo = week_start(today), month_first(month_of(today))
    inv = invoice_stats(invoices, today)
    words = [f"MRR {usd(mrr, whole=True)} from {clients} paying client{'' if clients == 1 else 's'}"
             + (f" ({usd(arpa, whole=True)} average)" if clients else "") + "."]
    words.append(f"Goal {usd(goal, whole=True)} MRR: " + ("reached." if left <= 0 else f"{usd(left, whole=True)} to go, about {need} more client{'' if need == 1 else 's'}."))
    if lastfull:
        lc = "-" if lastfull["logo_churn_pct"] is None else f"{lastfull['logo_churn_pct']:g}%"
        rc = "-" if lastfull["mrr_churn_pct"] is None else f"{lastfull['mrr_churn_pct']:g}%"
        words.append(f"{month_name(lastfull['month'])}: {lastfull['churned_clients']} lost, logo churn {lc}, MRR churn {rc}.")
    if inv["overdue"]:
        words.append(f"{inv['overdue']} invoice{'' if inv['overdue'] == 1 else 's'} overdue ({usd(inv['overdue_usd'], whole=True)}).")
    est = sum(1 for p in pays if p["est"])
    return {
        "v": 1, "kind": SUMMARY_KIND, "id": "agency", "mode": "real", "status": "sample" if sample else "ok",
        "built": dt.datetime.fromtimestamp(now_s, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "t": int(now_s), "today": today,
        "currency": "USD", "private": True, "publish": bool(publish),
        "headline": {"text": " ".join(words[:2]), "usd_month": f2(mrr)},
        "mrr": {"now": f2(mrr), "arr": f2(mrr * 12), "clients": clients, "arpa": f2(arpa),
                "scheduled_usd": f2(sum((p["monthly"] for p in future), ZERO)), "scheduled_clients": len({p["client_id"] for p in future}),
                "ending_usd": f2(sum((p["monthly"] for p in ending), ZERO)), "ending_clients": len({p["client_id"] for p in ending})},
        "goal": {"mrr": f2(goal), "left": f2(left), "pct": min(100.0, pct(mrr, goal) or 0.0), "clients_needed": need, "reached": left <= 0,
                 "price_used": f2(price)},
        "last_full_month": lastfull,
        "months": months,
        "cash": {"week": dict(cash(pays, wk, today), **{"from": wk}), "month": dict(cash(pays, mo, today), **{"from": mo}),
                 "all": cash(pays, "0000-01-01", today)},
        "days": day_rows(pays),
        "invoices": inv,
        "counts": {"plans": len(plans), "plans_skipped": len(raw_plans) - len(plans), "payments": len(pays),
                   "payments_skipped": len(raw_pays) - len(pays_all), "future_payments_ignored": len(pays_all) - len(pays), "fees_estimated": est},
        "text": " ".join(words),
        "notes": ["Real money from client payments you recorded (data/agency/ledger.json); nothing here is an estimate except fees marked estimated.",
                  "Aggregates only: no client name, id, email or phone is in this file.",
                  "Cash out = refunds + payment processor fees. Your own business costs (domain, hosting, tools) belong in the Ledger app."],
    }
