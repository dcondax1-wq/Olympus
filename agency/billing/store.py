"""AGENCY BILLING store (team B6, 2026-11-14): the kit's files. Everything real lives in data/agency/ (gitignored; the folder also gets
its own .gitignore with "*" the first time the kit writes there, so nothing in it can be committed by mistake).

  data/agency/business.json    your agency's name, contact, colour, payment links (python -m agency.billing setup ...)
  data/agency/invoices.json    every invoice ever issued + "last", the highest number used. Numbers come from ONE sequence that never
                               resets and never repeats: the next number is 1 + the highest of "last", every invoice in the file, the
                               high-water mark in invoices.last (written BEFORE the invoice, so a crash leaves a gap, never a repeat), the
                               invoice files on disk (data/agency/invoices/INV-....html) and invoices.json.bak (a copy of the last good
                               state, rewritten with every change). Any one of them surviving keeps the sequence; a hand edit of the JSON
                               cannot lower it. A voided invoice keeps its number. A damaged file is REFUSED (restore invoices.json.bak)
                               rather than guessed, because guessing could hand out a number twice. A lock makes two commands wait in turn.
  data/agency/ledger.json      the income ledger: payments received (amount, processor fee, kind) and plans (who pays how much a month,
                               from when, until when). core.summary turns it into MRR and churn.
  data/agency/docs/<client>/   proposals and agreements; data/agency/invoices/ the invoice pages (and PDFs).
  money_out/agency.json        the summary for the money pages and the money scoreboard (gitignored, aggregates only).
  The client records are READ from the CRM (data/agency/clients.json, crm.json or leads.json, or --clients FILE); never written here.
"""
from __future__ import annotations

import contextlib
import glob
import json
import os
import re
import time

from . import core as C

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data", "agency")
FIXTURES = os.path.join(HERE, "fixtures")
PACKAGES = os.path.join(HERE, "packages.json")
SUMMARY_OUT = os.path.join(ROOT, "money_out", "agency.json")
CRM_NAMES = ("clients.json", "crm.json", "leads.json")
PREFIX_RE = re.compile(r"^[A-Z]{2,8}$")
FILE_NO_RE = re.compile(r"^([A-Z]{2,8})-(\d{4})-(\d{4,})\.(?:html|pdf)$")
LOCK_STALE_S = 120

DEFAULT_BUSINESS = {"business_name": "", "owner_name": "", "email": "", "phone": "", "city": "", "state": "", "website": "",
                    "accent": "#1f5f55", "pay_links": {}, "pay_note": "Card or bank transfer (ACH) through secure online checkout.",
                    "terms_days": 7, "tax_rate_pct": 0, "goal_mrr": 1000, "fee_model": {"pct": 2.9, "fixed": 0.30, "extra_pct": 0.7},
                    "late_days": 10, "liability_months": 3, "buyout_months": 6, "invoice_prefix": "INV", "invoice_start": 1,
                    "publish_summary": False}


class StoreError(Exception):
    """a file the kit will not touch as it is (damaged, locked, unknown invoice): the message says what to do"""


def data_dir(path: str | None = None) -> str:
    return os.path.abspath(path or os.environ.get("AGENCY_DATA_DIR") or DATA)


def read_json(path: str):
    """-> (doc, 'ok' | 'missing' | 'bad')"""
    if not path or not os.path.exists(path):
        return None, "missing"
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), "ok"
    except (OSError, ValueError):
        return None, "bad"


def write_json(path: str, doc, backup: bool = False, mirror: bool = False) -> str:
    """atomic write (temp file + replace). backup=True first keeps the current file as <path>.bak (the version before: an undo);
    mirror=True writes the new content to <path>.bak too (a copy of the last good state: the invoice numbers survive a bad hand edit)"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if backup and os.path.isfile(path):
        with open(path, "rb") as src, open(path + ".bak.tmp", "wb") as dst:
            dst.write(src.read())
        os.replace(path + ".bak.tmp", path + ".bak")
    for target in ([path, path + ".bak"] if mirror else [path]):
        tmp = f"{target}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, target)
    return path


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", C.text(s, 64)).strip("._") or "client"


class Store:
    LOCK_TIMEOUT = 20.0          # seconds a command waits for another one to finish

    def __init__(self, root: str | None = None):
        self.root = data_dir(root)
        self.inv_path = os.path.join(self.root, "invoices.json")
        self.counter_path = os.path.join(self.root, "invoices.last")
        self.ledger_path = os.path.join(self.root, "ledger.json")
        self.biz_path = os.path.join(self.root, "business.json")
        self.inv_dir = os.path.join(self.root, "invoices")
        self.docs_dir = os.path.join(self.root, "docs")

    # ---------------------------------------------------------------------------------------------- the folder and the lock
    def ensure(self) -> None:
        os.makedirs(self.root, exist_ok=True)
        gi = os.path.join(self.root, ".gitignore")
        if not os.path.exists(gi):
            with open(gi, "w", encoding="utf-8") as fh:
                fh.write("# the agency's real data (clients, invoices, payments): never committed\n*\n")

    @contextlib.contextmanager
    def lock(self, timeout: float | None = None):
        self.ensure()
        path = os.path.join(self.root, ".lock")
        timeout = self.LOCK_TIMEOUT if timeout is None else timeout
        t0 = time.time()
        while True:
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                break
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(path) > LOCK_STALE_S:     # left behind by a crashed command
                        os.remove(path)
                        continue
                except OSError:
                    pass
                if time.time() - t0 > timeout:
                    raise StoreError("another billing command is running (data/agency/.lock). Wait a minute and try again.")
                time.sleep(0.02)
        try:
            yield
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    # ---------------------------------------------------------------------------------------------- business profile, packages, clients
    def business(self) -> dict:
        doc, st = read_json(self.biz_path)
        if st == "bad":
            raise StoreError(f"{self.biz_path} is not valid JSON: fix it or delete it and run setup again.")
        out = json.loads(json.dumps(DEFAULT_BUSINESS))
        if isinstance(doc, dict):
            for k, v in doc.items():
                if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                    out[k] = {**out[k], **v}
                elif k in out:
                    out[k] = v
        if not PREFIX_RE.match(str(out.get("invoice_prefix") or "")):
            out["invoice_prefix"] = "INV"
        out["configured"] = bool(isinstance(doc, dict) and C.text(doc.get("business_name")))
        return out

    def save_business(self, updates: dict) -> dict:
        with self.lock():
            doc, st = read_json(self.biz_path)
            if st == "bad":
                raise StoreError(f"{self.biz_path} is not valid JSON: fix it or delete it first.")
            doc = doc if isinstance(doc, dict) else {}
            for k, v in updates.items():
                if k == "pay_links":
                    doc["pay_links"] = {**(doc.get("pay_links") or {}), **v}
                else:
                    doc[k] = v
            write_json(self.biz_path, doc, backup=True)
        return self.business()

    @staticmethod
    def packages() -> dict:
        """the plans: the wording from packages.json, the PRICES from the one source (agency.config.prices(): agency/config.json
        over agency/config.example.json), so the pitch, storefront, Agency page and these documents always quote the same price"""
        doc, _ = read_json(PACKAGES)
        try:
            from agency import config as CFG
            pr = CFG.prices()
        except Exception:                                   # a broken settings file must not stop an invoice: wording only
            pr = {}
        plans = []
        for p in (doc or {}).get("packages") or []:
            if isinstance(p, dict):
                q, src = dict(p), pr.get(str(p.get("id"))) or {}
                for k_doc, k_src in (("setup_usd", "setup"), ("monthly_usd", "monthly")):
                    if k_src in src:
                        q[k_doc] = src[k_src]
                plans.append(q)
        return C.packages_from({"packages": plans})

    def clients(self, path: str | None = None, demo: bool = False) -> tuple[list, str]:
        """(records, where from). --clients FILE, else the CRM files in data/agency/, else nothing (or the fixtures with demo)."""
        paths = [path] if path else [os.path.join(self.root, n) for n in CRM_NAMES]
        for p in paths:
            doc, st = read_json(p)
            if st == "bad":
                raise StoreError(f"{p} is not valid JSON.")
            if st == "ok":
                rows = C.clients_from(doc)
                if demo:
                    rows += [c for c in fixture_clients() if c["id"] not in {r["id"] for r in rows}]
                return rows, os.path.relpath(p, ROOT) if p.startswith(ROOT) else p
        if path:
            raise StoreError(f"{path} not found.")
        return (fixture_clients(), "the sample clients (agency/billing/fixtures)") if demo else ([], "no CRM file yet")

    # ---------------------------------------------------------------------------------------------- invoices and numbering
    def invoices(self) -> dict:
        doc, st = read_json(self.inv_path)
        if st == "bad" or (st == "ok" and not (isinstance(doc, dict) and isinstance(doc.get("invoices"), list))):
            raise StoreError(f"{self.inv_path} is damaged. The kit will not guess invoice numbers (a guess could repeat one). "
                             "Restore invoices.json.bak (a copy of the last good state) or fix the file, then run again.")
        if st == "missing":
            doc = {"v": 1, "kind": "agency-invoices", "last": 0, "invoices": []}
        return doc

    def counter(self) -> int:
        """the high-water mark (invoices.last): the highest invoice number ever handed out"""
        if not os.path.exists(self.counter_path):
            return 0
        try:
            with open(self.counter_path, encoding="utf-8") as fh:
                s = fh.read().strip()
            return int(s) if s else 0
        except (OSError, ValueError):
            raise StoreError(f"{self.counter_path} is damaged: it holds one whole number, the highest invoice number you have used. "
                             "Put that number in it (look at your last invoice) and run again.")

    def _set_counter(self, n: int) -> None:
        tmp = f"{self.counter_path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(f"{int(n)}\n")
        os.replace(tmp, self.counter_path)

    def highest_seq(self, doc: dict) -> int:
        seqs = [int(C.dec(doc.get("last")) or 0), self.counter()]
        seqs += [C.seq_of(i.get("no")) or 0 for i in doc["invoices"] if isinstance(i, dict)]
        for f in glob.glob(os.path.join(self.inv_dir, "*")):
            m = FILE_NO_RE.match(os.path.basename(f))
            if m:
                seqs.append(int(m.group(3)))
        bak, st = read_json(self.inv_path + ".bak")
        if st == "ok" and isinstance(bak, dict):
            seqs.append(int(C.dec(bak.get("last")) or 0))
            seqs += [C.seq_of(i.get("no")) or 0 for i in bak.get("invoices") or [] if isinstance(i, dict)]
        return max(seqs)

    def issue(self, draft: dict, today: str, prefix: str = "INV", start_at: int = 1) -> dict:
        """give the draft the next number and save it (the number is taken even if writing the page fails later: a gap, never a repeat)"""
        if not PREFIX_RE.match(prefix or ""):
            raise StoreError(f"invoice prefix must be 2-8 capital letters, got {prefix!r}")
        with self.lock():
            doc = self.invoices()
            seq = max(self.highest_seq(doc), int(start_at or 1) - 1) + 1
            rec = dict(draft, no=C.fmt_no(prefix, int(today[:4]), seq), seq=seq, issued=today, status="open")
            self._set_counter(seq)                       # first the high-water mark: a crash after this is a gap, never a repeat
            doc["invoices"].append(rec)
            doc["last"] = seq
            write_json(self.inv_path, doc, mirror=True)
        return rec

    def find_invoice(self, no: str) -> dict:
        for i in self.invoices()["invoices"]:
            if isinstance(i, dict) and i.get("no") == no:
                return i
        raise StoreError(f"no invoice {no} in {self.inv_path}")

    def update_invoice(self, no: str, fn) -> dict:
        with self.lock():
            doc = self.invoices()
            for i in doc["invoices"]:
                if isinstance(i, dict) and i.get("no") == no:
                    fn(i)
                    write_json(self.inv_path, doc, mirror=True)
                    return i
        raise StoreError(f"no invoice {no} in {self.inv_path}")

    def void(self, no: str, reason: str = "") -> dict:
        def f(i):
            if i.get("status") == "paid":
                raise StoreError(f"{no} is paid: record a refund instead of voiding it.")
            i["status"], i["void_reason"] = "void", C.text(reason, 160)
        return self.update_invoice(no, f)

    # ---------------------------------------------------------------------------------------------- the ledger
    def ledger(self) -> dict:
        doc, st = read_json(self.ledger_path)
        if st == "bad" or (st == "ok" and not isinstance(doc, dict)):
            raise StoreError(f"{self.ledger_path} is damaged: restore ledger.json.bak (the copy from before the last change) or fix it.")
        doc = doc if isinstance(doc, dict) else {"v": 1, "kind": "agency-ledger", "plans": [], "payments": []}
        doc.setdefault("plans", [])
        doc.setdefault("payments", [])
        return doc

    def _save_ledger(self, doc: dict) -> None:
        write_json(self.ledger_path, doc, backup=True)

    @staticmethod
    def _next_pay_id(doc: dict) -> str:
        n = 0
        for p in doc["payments"]:
            m = re.match(r"^p_(\d+)$", str(p.get("id") if isinstance(p, dict) else ""))
            n = max(n, int(m.group(1))) if m else n
        return f"p_{n + 1:05d}"

    def add_payment(self, client_id: str, amount, date: str, kind: str = "monthly", fee=None, method: str = "", invoice: str = "",
                    note: str = "", fee_model: dict | None = None, ext_id: str = "") -> dict:
        with self.lock():
            doc = self.ledger()
            p = self._payment(doc, client_id, amount, date, kind, fee, method, invoice, note, fee_model, ext_id)
            self._save_ledger(doc)
        return p

    def _payment(self, doc, client_id, amount, date, kind, fee, method, invoice, note, fee_model, ext_id="") -> dict:
        a = C.dec(amount)
        if a is None or a <= 0:
            raise StoreError(f"a payment needs an amount above $0, got {amount!r}")
        if not C.is_date(date):
            raise StoreError(f"a payment needs a date YYYY-MM-DD, got {date!r}")
        if kind not in C.PAY_KINDS:
            raise StoreError(f"kind must be one of {', '.join(C.PAY_KINDS)}")
        est = fee is None
        f = min(C.est_fee(a, fee_model), C.cents(a)) if est and kind != "refund" else C.cents(fee if fee is not None else 0)
        if f < 0 or f > a:
            raise StoreError(f"the fee must be between $0 and the amount, got {fee!r}")
        p = {"id": self._next_pay_id(doc), "date": date, "client_id": C.text(client_id, 64), "amount_usd": C.f2(a), "fee_usd": C.f2(f),
             "kind": kind, "method": C.text(method, 30), "invoice": C.text(invoice, 40), "note": C.text(note, 160)}
        if est and kind != "refund":
            p["fee_estimated"] = True
        if ext_id:
            p["ext_id"] = C.text(ext_id, 80)
        doc["payments"].append(p)
        return p

    def running_plan(self, doc: dict, client_id: str, day: str):
        """the plan of this client that runs on day or starts later and has no end (the one a change or cancel acts on)"""
        hits = [p for p in doc["plans"] if isinstance(p, dict) and p.get("client_id") == client_id and C.norm_plan(p)
                and (p.get("end") is None or p["end"] >= day)]
        return sorted(hits, key=lambda p: p["start"])[-1] if hits else None

    def start_plan(self, client_id: str, monthly, start: str, package: str = "") -> dict:
        with self.lock():
            doc = self.ledger()
            p = self._start(doc, client_id, monthly, start, package)
            self._save_ledger(doc)
        return p

    def _start(self, doc, client_id, monthly, start, package) -> dict:
        m = C.dec(monthly)
        if m is None or m <= 0:
            raise StoreError(f"a plan needs a monthly price above $0, got {monthly!r}")
        if not C.is_date(start):
            raise StoreError(f"a plan needs a start date YYYY-MM-DD, got {start!r}")
        cur = self.running_plan(doc, client_id, start)
        if cur:
            raise StoreError(f"{client_id} already has a plan running ({C.usd(cur['monthly_usd'])}/month from {cur['start']}). "
                             "Use: plan change (new price) or plan cancel.")
        p = {"client_id": C.text(client_id, 64), "monthly_usd": C.f2(m), "start": start, "end": None, "package": C.text(package, 40)}
        doc["plans"].append(p)
        return p

    def change_plan(self, client_id: str, monthly, start: str, package: str = "") -> tuple[dict, dict]:
        """a new price from `start`: the running plan ends the day before, the new one starts that day"""
        with self.lock():
            doc = self.ledger()
            cur = self.running_plan(doc, client_id, start)
            if not cur:
                raise StoreError(f"{client_id} has no running plan to change: use plan start.")
            if cur["start"] >= start:
                raise StoreError(f"the change date must be after the plan's start ({cur['start']}).")
            cur["end"] = C.add_days(start, -1)
            new = self._start(doc, client_id, monthly, start, package or cur.get("package") or "")
            self._save_ledger(doc)
        return cur, new

    def cancel_plan(self, client_id: str, last_day: str, reason: str = "") -> dict:
        """the plan's LAST day of service (with 30 days notice: the day 30 days after the email, or the end of the paid month)"""
        if not C.is_date(last_day):
            raise StoreError(f"cancel needs the last day YYYY-MM-DD, got {last_day!r}")
        with self.lock():
            doc = self.ledger()
            cur = self.running_plan(doc, client_id, last_day)
            if not cur:
                raise StoreError(f"{client_id} has no plan running on {last_day}.")
            if last_day < cur["start"]:
                raise StoreError(f"the last day is before the plan's start ({cur['start']}).")
            cur["end"] = last_day
            if reason:
                cur["cancel_reason"] = C.text(reason, 160)
            self._save_ledger(doc)
        return cur

    def import_csv(self, path: str, clients: list, today: str, fee_model: dict | None = None, method: str = "stripe") -> dict:
        """a payments export -> ledger payments, each once (the export's id, else date + amount + email, is remembered as ext_id)"""
        import csv
        try:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                rd = csv.DictReader(fh)
                rows = [r for _, r in zip(range(50000), rd)]
                header = rd.fieldnames or []
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            raise StoreError(f"could not read {path}: {e}")
        parsed, skipped = C.csv_payments(header, rows, clients)
        res = {"added": 0, "dupes": 0, "skipped": skipped, "unmatched": 0, "in_usd": C.ZERO, "fees_usd": C.ZERO, "refunds_usd": C.ZERO, "no_plan": []}
        with self.lock():
            doc = self.ledger()
            seen = {p.get("ext_id") for p in doc["payments"] if isinstance(p, dict) and p.get("ext_id")}
            plans = {p.get("client_id") for p in doc["plans"] if isinstance(p, dict)}
            names = {c["id"]: c["name"] for c in clients}
            for r in parsed:
                if r["date"] > today:
                    res["skipped"] += 1
                    continue
                if r["ext_id"] in seen:
                    res["dupes"] += 1
                    continue
                p = self._payment(doc, r["client_id"], r["amount"], r["date"], "monthly", r["fee"], method, "", "imported", fee_model, r["ext_id"])
                seen.add(r["ext_id"])
                res["added"] += 1
                res["in_usd"] += C.cents(p["amount_usd"])
                res["fees_usd"] += C.cents(p["fee_usd"])
                res["unmatched"] += not r["matched"]
                if r["refunded"] > 0:
                    self._payment(doc, r["client_id"], min(r["refunded"], r["amount"]), r["date"], "refund", 0, method, "", "refund in the export",
                                  fee_model, r["ext_id"] + ":refund")
                    res["refunds_usd"] += min(r["refunded"], r["amount"])
                if r["matched"] and r["client_id"] not in plans and names.get(r["client_id"]) not in res["no_plan"]:
                    res["no_plan"].append(names.get(r["client_id"]) or r["client_id"])
            if res["added"]:
                self._save_ledger(doc)
        for k in ("in_usd", "fees_usd", "refunds_usd"):
            res[k] = C.f2(res[k])
        return res

    def mark_paid(self, no: str, date: str, amount=None, fee=None, method: str = "stripe", fee_model: dict | None = None,
                  start_plan: bool = True) -> tuple[dict, dict, dict | None]:
        """an invoice is paid: the invoice says so, the ledger gets the payment, and the client's plan starts with its first payment"""
        if not C.is_date(date):
            raise StoreError(f"the payment date must be YYYY-MM-DD, got {date!r}")
        with self.lock():
            inv_doc = self.invoices()
            inv = next((i for i in inv_doc["invoices"] if isinstance(i, dict) and i.get("no") == no), None)
            if inv is None:
                raise StoreError(f"no invoice {no} in {self.inv_path}")
            if inv.get("status") == "void":
                raise StoreError(f"{no} is void.")
            bal = C.cents(inv.get("balance_usd", inv.get("total_usd")))
            if inv.get("status") == "paid" or bal <= 0:
                raise StoreError(f"{no} is already paid.")
            amt = C.cents(amount) if amount is not None else bal
            if amt <= 0 or amt > bal:
                raise StoreError(f"the amount must be above $0 and at most the balance {C.usd(bal)}.")
            led = self.ledger()
            monthly = C.cents(inv.get("monthly_usd"))
            kind = "monthly" if monthly > 0 else "setup" if C.cents(inv.get("setup_usd")) > 0 else "one_time"
            pay = self._payment(led, inv.get("client_id"), amt, date, kind, fee, method, no, "", fee_model)
            inv["paid_usd"] = C.f2(C.cents(inv.get("paid_usd")) + amt)
            inv["balance_usd"] = C.f2(bal - amt)
            inv["status"] = "paid" if bal - amt <= 0 else "open"
            inv["paid_on"], inv["method"] = date, C.text(method, 30)
            plan = None
            if start_plan and monthly > 0 and inv.get("first", False) and not self.running_plan(led, inv.get("client_id"), date):
                plan = self._start(led, inv.get("client_id"), monthly, date, inv.get("package") or "")
            write_json(self.inv_path, inv_doc, mirror=True)
            self._save_ledger(led)
        return inv, pay, plan


# ------------------------------------------------------------------------------------------------ fixtures and the summary file
def fixture_clients() -> list:
    doc, _ = read_json(os.path.join(FIXTURES, "clients.json"))
    return C.clients_from(doc or {})


def fixture_business() -> dict:
    doc, _ = read_json(os.path.join(FIXTURES, "business.json"))
    out = json.loads(json.dumps(DEFAULT_BUSINESS))
    out.update({k: v for k, v in (doc or {}).items() if k in out})
    out["configured"] = True
    return out


def fixture_ledger() -> dict:
    doc, _ = read_json(os.path.join(FIXTURES, "ledger.json"))
    return doc or {}


def write_summary(store: Store, today: str, now_s: float, out: str | None = None, sample: bool = False) -> tuple[str, dict]:
    biz = fixture_business() if sample else store.business()
    led = fixture_ledger() if sample else store.ledger()
    inv = {"invoices": []} if sample else store.invoices()
    pk = Store.packages()
    default_price = C.dec((pk.get("growth") or {}).get("monthly_usd")) or 149
    doc = C.summary(led, inv, today, now_s, goal_mrr=biz.get("goal_mrr") or C.GOAL_MRR, publish=bool(biz.get("publish_summary")) and not sample,
                    sample=sample, default_price=default_price)
    path = out or SUMMARY_OUT
    write_json(path, doc)
    return path, doc
