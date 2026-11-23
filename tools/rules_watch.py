"""MFFU RULE-CHANGE WATCHER (night-rulewatch 2026-11-23, lead: "if MFFU changes a rule and our mffu_rules.json is stale, the bot can
breach an account"). Read-only: it NEVER changes a live rule, a config or research/lit/mffu_rules.json. Stdlib only, no paid service.

What it does, once a day (maybe_run, from tools/pc_report.py's 15-minute task, weekdays from 17:05 ET, like engine/datapipe):
  1. fetch the public MFFU help-center pages that research/lit/mffu_rules.json already cites (WATCH below: one row per rule)
  2. read the rule's value from the page: a label -> value table row ("Soft Daily Loss Limit" / "$600"; `col` = the column on
     two-column tables) or a sentence pattern ("for 7 consecutive calendar days")
  3. compare it with the value WE store (`path` into mffu_rules.json, so a Claude update of the file moves the watcher with it)
  -> per rule: ok | changed (the page shows another value) | missing (the page loads but the label / sentence is gone: a layout
     change, never called a rule change) | unreachable (HTTP error, timeout, an empty page: never called a change either)
  4. a real change -> ONE phone alert per rule and new value (engine/alert_bus.send_critical): "MFFU rule changed: <rule> was X now
     Y, source <url>; the bot still uses X until Claude updates it" + one board line (engine/board_events "risk_alert").
     missing / unreachable -> logged in the report only (data/rules_watch.json), at most one quiet digest line a day.
Report: data/rules_watch.json (gitignored): {"t", "day", "rows": [{id, what, status, stored, seen, url}]}.

    python -X utf8 tools/rules_watch.py            check now (network), print the table, send nothing
    python -X utf8 tools/rules_watch.py --alert    check now and alert on real changes (what maybe_run does)
Tests: python -X utf8 -m tests.test_rules_watch (saved pages in tests/fixtures/mffu_pages/, no network)
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
RULES_PATH = os.path.join(ROOT, "research", "lit", "mffu_rules.json")
REPORT_PATH = os.path.join(ROOT, "data", "rules_watch.json")       # gitignored
HELP = "https://help.myfundedfutures.com/en/articles/"
UA = "Mozilla/5.0 (compatible; olympus-rules-watch/1)"
TIMEOUT_S = 12
MIN_TEXT = 400                    # a page with less readable text than this = unreachable (an error page, a login wall)
RETRY_S = 3600                    # red team 2: all pages down -> the next try an hour later
MAX_ALERTS = 3                    # red team 2: more real changes than this in one run = ONE digest alert (a page layout change
                                  # that still parses as numbers must not send a storm of "rule changed" alerts)
RUN_FROM = 17 * 60 + 5            # ET minutes, weekdays: after the close, once a day

P = {"b25": HELP + "17036130-builder-plan-25k-a-comprehensive-look", "b50": HELP + "14290805-builder-plan-50k-a-comprehensive-guide",
     "r25": HELP + "16727601-rapid-eod-25k-a-comprehensive-look", "r50": HELP + "16158363-rapid-eod-50k-a-comprehensive-look",
     "rdll": HELP + "18337038-rapid-eod-with-dll-a-detailed-look", "idle": HELP + "16596524-inactivity-rule-one-time-payment-model",
     "news": HELP + "8230009-news-trading-policy", "rlive": HELP + "13134718-understanding-rapid-live",
     "cons": HELP + "11994562-consistency-rule-at-my-fundedfutures"}

# one row per rule: page, what (plain words), path (the stored value in mffu_rules.json), and how to read the page:
#   label + n (the n-th time the label shows, 1 = first) + col (0 = the first value column) + kind (money | micros | pct | int)
#   or rx (a sentence pattern; group 1 = the value) + kind
WATCH = (
    # Builder 25K (eval + sim funded)
    {"id": "b25_target", "page": "b25", "what": "Builder 25K profit target", "path": "limits.builder_25k.target", "label": "Profit Target", "kind": "money"},
    {"id": "b25_mll", "page": "b25", "what": "Builder 25K max loss (MLL)", "path": "limits.builder_25k.mll", "label": r"Max EOD Drawdown \(MLL\)", "kind": "money"},
    {"id": "b25_dll", "page": "b25", "what": "Builder 25K daily loss limit (soft)", "path": "limits.builder_25k.dll", "label": r"Soft Daily Loss Limit.*", "kind": "money"},
    {"id": "b25_micros", "page": "b25", "what": "Builder 25K max micros", "path": "limits.builder_25k.max_micros", "label": "Max Contracts", "kind": "micros"},
    {"id": "b25_cons", "page": "b25", "what": "Builder 25K funded consistency (best day %)", "path": "limits.builder_25k.cons", "label": "Consistency Rule", "n": 2, "kind": "pct"},
    {"id": "b25_buffer", "page": "b25", "what": "Builder 25K payout buffer", "path": "limits.builder_25k.buffer", "label": r"Buffer \(Must Be Cleared.*", "kind": "money"},
    {"id": "b25_pay_min", "page": "b25", "what": "Builder 25K minimum payout", "path": "limits.builder_25k.pay_min", "label": "Minimum Payout Amount", "kind": "money"},
    {"id": "b25_pay_max", "page": "b25", "what": "Builder 25K maximum payout per cycle", "path": "limits.builder_25k.pay_max", "label": "Maximum Payout Per Cycle", "kind": "money"},
    {"id": "b25_days", "page": "b25", "what": "Builder 25K traded days per payout cycle", "path": "limits.builder_25k.cycle_days", "label": r"Minimum Qualifying Days.*", "kind": "int"},
    {"id": "b25_payouts", "page": "b25", "what": "Builder 25K sim payouts before live", "path": "limits.builder_25k.max_payouts", "label": "Max Sim Payouts", "kind": "int"},
    {"id": "b25_accounts", "page": "b25", "what": "Builder 25K sim funded accounts per user", "path": "builder_25k.funded.value.sim_funded_active", "label": "Active Accounts Allowed", "kind": "int"},
    {"id": "b25_idle", "page": "b25", "what": "Builder 25K inactivity days", "path": "limits.builder_25k.inactivity_days", "label": "Inactivity Rule", "kind": "int"},
    # Builder 50K (the "Default" column)
    {"id": "b50_target", "page": "b50", "what": "Builder 50K profit target", "path": "limits.builder_50k.target", "label": "Profit Target", "kind": "money"},
    {"id": "b50_mll", "page": "b50", "what": "Builder 50K max loss (MLL)", "path": "limits.builder_50k.mll", "label": r"Max EOD Drawdown \(MLL\)", "kind": "money"},
    {"id": "b50_dll", "page": "b50", "what": "Builder 50K daily loss limit (soft)", "path": "limits.builder_50k.dll", "label": "Daily Loss Limit", "kind": "money"},
    {"id": "b50_micros", "page": "b50", "what": "Builder 50K max micros", "path": "limits.builder_50k.max_micros", "label": "Max Contracts", "kind": "micros"},
    {"id": "b50_cons", "page": "b50", "what": "Builder 50K funded consistency (best day %)", "path": "limits.builder_50k.cons", "label": "Consistency Rule", "n": 2, "kind": "pct"},
    {"id": "b50_buffer", "page": "b50", "what": "Builder 50K payout buffer", "path": "limits.builder_50k.buffer", "label": r"Buffer \(Must Be Cleared.*", "kind": "money"},
    {"id": "b50_pay_min", "page": "b50", "what": "Builder 50K minimum payout", "path": "limits.builder_50k.pay_min", "label": "Minimum Payout Amount", "kind": "money"},
    {"id": "b50_pay_max", "page": "b50", "what": "Builder 50K maximum payout per cycle", "path": "limits.builder_50k.pay_max", "label": "Maximum Payout Per Cycle", "kind": "money"},
    {"id": "b50_payouts", "page": "b50", "what": "Builder 50K sim payouts before live", "path": "limits.builder_50k.max_payouts", "label": "Max Sim Payouts", "kind": "int"},
    {"id": "b50_idle", "page": "b50", "what": "Builder 50K inactivity days", "path": "limits.builder_50k.inactivity_days", "label": "Inactivity Rule", "kind": "int"},
    # Rapid EOD 25K
    {"id": "r25_target", "page": "r25", "what": "Rapid EOD 25K profit target", "path": "rapid_eod_25k.eval.value.target", "label": "Profit Target", "kind": "money"},
    {"id": "r25_mll", "page": "r25", "what": "Rapid EOD 25K max loss (MLL)", "path": "rapid_eod_25k.eval.value.mll", "label": r"Maximum Loss Limit.*", "kind": "money"},
    {"id": "r25_micros", "page": "r25", "what": "Rapid EOD 25K max micros", "path": "rapid_eod_25k.eval.value.max_contracts.micros", "label": "Max Contract", "kind": "micros"},
    {"id": "r25_cons", "page": "r25", "what": "Rapid EOD 25K eval consistency (best day %)", "path": "rapid_eod_25k.eval.value.consistency", "label": "Consistency", "kind": "pct"},
    {"id": "r25_days", "page": "r25", "what": "Rapid EOD 25K minimum trading days", "path": "rapid_eod_25k.eval.value.min_days", "label": "Minimum Trading Days", "kind": "int"},
    {"id": "r25_buffer", "page": "r25", "what": "Rapid EOD 25K payout buffer", "path": "rapid_eod_25k.sim_funded.value.buffer", "rx": r"Required Buffer:\s*\$([\d,]+)", "kind": "money"},
    {"id": "r25_pay_min", "page": "r25", "what": "Rapid EOD 25K minimum payout", "path": "rapid_eod_25k.sim_funded.value.payout_min", "rx": r"Minimum Payout Request:\s*\$([\d,]+)", "kind": "money"},
    {"id": "r25_funded_max", "page": "r25", "what": "Rapid EOD 25K sim funded accounts per user", "path": "=3", "label": r"Max # of (?:Sim )?Funded Accounts", "kind": "int"},
    # Rapid EOD 50K
    {"id": "r50_target", "page": "r50", "what": "Rapid EOD 50K profit target", "path": "rapid_eod_50k.eval.value.target", "label": "Profit Target", "kind": "money"},
    {"id": "r50_mll", "page": "r50", "what": "Rapid EOD 50K max loss (MLL)", "path": "rapid_eod_50k.eval.value.mll", "label": r"Maximum Loss Limit.*", "kind": "money"},
    {"id": "r50_micros", "page": "r50", "what": "Rapid EOD 50K max micros", "path": "rapid_eod_50k.eval.value.max_contracts.micros", "label": "Max Contract", "kind": "micros"},
    {"id": "r50_cons", "page": "r50", "what": "Rapid EOD 50K eval consistency (best day %)", "path": "rapid_eod_50k.eval.value.consistency", "label": "Consistency", "kind": "pct"},
    {"id": "r50_days", "page": "r50", "what": "Rapid EOD 50K minimum trading days", "path": "rapid_eod_50k.eval.value.min_days", "label": "Minimum Trading Days", "kind": "int"},
    {"id": "r50_buffer", "page": "r50", "what": "Rapid EOD 50K payout buffer", "path": "rapid_eod_50k.sim_funded.value.buffer", "rx": r"Required Buffer:\s*\$([\d,]+)", "kind": "money"},
    {"id": "r50_pay_min", "page": "r50", "what": "Rapid EOD 50K minimum payout", "path": "rapid_eod_50k.sim_funded.value.payout_min", "rx": r"Minimum Payout Request:\s*\$([\d,]+)", "kind": "money"},
    {"id": "r50_funded_max", "page": "r50", "what": "Rapid EOD 50K sim funded accounts per user", "path": "rapid_eod_50k.sim_funded.value.max_funded", "label": r"Max # of (?:Sim )?Funded Accounts", "kind": "int"},
    {"id": "r50_idle", "page": "r50", "what": "Rapid EOD 50K inactivity days", "path": "rapid_eod_50k.eval.value.inactivity_days", "label": "Inactivity Rule", "kind": "int"},
    # Rapid EOD with the DLL option (the owner's Rapid 25K was bought with it)
    {"id": "r25_dll", "page": "rdll", "what": "Rapid EOD 25K daily loss limit (DLL version, soft)", "path": "rapid_eod_25k.dll_option.value.amount", "label": r"Daily Loss Limit \(DLL Version\)", "col": 0, "kind": "money"},
    {"id": "r50_dll", "page": "rdll", "what": "Rapid EOD 50K daily loss limit (DLL version, soft)", "path": "=1000", "label": r"Daily Loss Limit \(DLL Version\)", "col": 1, "kind": "money"},
    # sentences
    {"id": "inactivity", "page": "idle", "what": "Inactivity: days without a trade before an account can be closed", "path": "limits.builder_25k.inactivity_days",
     "rx": r"for (\d+) consecutive calendar days", "kind": "int"},
    {"id": "news_window", "page": "news", "what": "T1 news: minutes flat before / after", "path": "=2", "rx": r"(\d+) minutes before and after", "kind": "int"},
    {"id": "rapid_live", "page": "rlive", "what": "Rapid live trigger: net profit in one day", "path": "=10000",
     "rx": r"\$([\d,]+) (?:in )?net profit (?:achieved )?(?:in|within) a single trading (?:day|session)", "kind": "money"},
    {"id": "cons_rapid", "page": "cons", "what": "Rapid EOD consistency (help article)", "path": "rapid_eod_50k.eval.value.consistency", "rx": r"(\d+)% on our Rapid EOD plans", "kind": "pct"},
    {"id": "cons_builder", "page": "cons", "what": "Builder funded consistency (help article)", "path": "limits.builder_50k.cons", "rx": r"Builder plans have a (\d+)% consistency", "kind": "pct"},
)


# ------------------------------------------------------------------------------------------------ pure parts
def page_text(raw: str) -> str:
    """The article's readable text, one block per line (Intercom help pages: the <article> element)."""
    h = str(raw or "")
    m = re.search(r"<article[^>]*>(.*?)</article>", h, re.S | re.I)
    h = m.group(1) if m else h
    h = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>|</(p|li|h\d|tr|td|th|div)>", "\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h).replace("​", " ")
    h = re.sub(r"[ \t ]+", " ", h)
    return "\n".join(ln.strip() for ln in h.split("\n") if ln.strip())


def parse_value(s: str, kind: str):
    """A number from one cell / match. None when the text has none (e.g. 'None', a layout change)."""
    s = str(s or "")
    if kind == "micros":
        m = re.search(r"(\d+)\s*micro", s, re.I)
    elif kind == "pct":
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", s) or re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", s)
    elif kind == "money":
        m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", s) or re.fullmatch(r"\s*([\d,]+(?:\.\d+)?)\s*", s)
    else:
        m = re.search(r"\((\d+)\)", s) or re.search(r"(\d+)", s)
        if not m:
            words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
            w = re.search(r"\b(" + "|".join(words) + r")\b", s, re.I)
            return float(words[w.group(1).lower()]) if w else None
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return v / 100.0 if kind == "pct" else v


def read_rule(text: str, row: dict):
    """(value | None, the cell / sentence it came from) from one page's text."""
    if row.get("rx"):
        m = re.search(row["rx"], text, re.I)
        return (parse_value(m.group(1), row["kind"]) if m else None), (m.group(0)[:120] if m else "")
    lines = text.split("\n")
    rx = re.compile(r"^\s*" + row["label"] + r"\s*$", re.I)
    hits = [i for i, ln in enumerate(lines) if rx.match(ln)]
    n = int(row.get("n") or 1)
    if len(hits) < n:
        return None, ""
    j = hits[n - 1] + 1 + int(row.get("col") or 0)
    cell = lines[j] if j < len(lines) else ""
    return parse_value(cell, row["kind"]), cell[:120]


def stored(rules: dict, path: str):
    """The value WE store: a dotted path into mffu_rules.json, or '=<number>' (a value the file keeps only in words). None = gone."""
    if str(path).startswith("="):
        return float(path[1:])
    cur = rules
    for k in str(path).split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    if isinstance(cur, dict) and "days" in cur:
        cur = cur["days"]
    try:
        return float(cur)
    except (TypeError, ValueError):
        return None


def same(a, b) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) < 1e-6


def check(pages: dict, rules: dict) -> list:
    """pages = {page key: (status, text)} -> one row per rule. Pure."""
    out = []
    for r in WATCH:
        st, txt = pages.get(r["page"], ("unreachable", ""))
        base = {"id": r["id"], "what": r["what"], "url": P[r["page"]], "stored": stored(rules, r["path"])}
        if st != "ok":
            out.append({**base, "status": "unreachable", "seen": None, "cell": st})
            continue
        v, cell = read_rule(txt, r)
        if v is None:
            out.append({**base, "status": "missing", "seen": None, "cell": cell})
        elif base["stored"] is None:
            out.append({**base, "status": "missing", "seen": v, "cell": "no stored value in mffu_rules.json"})
        else:
            out.append({**base, "status": "ok" if same(v, base["stored"]) else "changed", "seen": v, "cell": cell})
    return out


def fmt(row: dict, v) -> str:
    if v is None:
        return "?"
    k = next((r["kind"] for r in WATCH if r["id"] == row["id"]), "int")
    if k == "pct":
        return f"{v * 100:.0f}%"
    if k == "money":
        return f"${v:,.0f}"
    return f"{v:,.0f}"


def alert_text(row: dict) -> tuple:
    was, now = fmt(row, row["stored"]), fmt(row, row["seen"])
    return (f"MFFU rule changed: {row['what']}"[:120],
            f"{row['what']} was {was}, now {now} (source {row['url']}). The bot still uses {was} until Claude updates it. "
            "Check the page; tell Claude.")


# ------------------------------------------------------------------------------------------------ the network + the run
def fetch(url: str, http=None) -> tuple:
    """(status, text): ("ok", text) | ("http 404", "") | ("timeout", "") ... Never raises."""
    try:
        if http is not None:
            code, raw = http(url)
        else:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                code, raw = r.status, r.read(2_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return f"http {e.code}", ""
    except Exception as e:  # noqa: BLE001
        return e.__class__.__name__, ""
    if int(code or 0) != 200:
        return f"http {code}", ""
    t = page_text(raw)
    return ("ok", t) if len(t) >= MIN_TEXT else ("empty page", "")


def run(http=None, rules: dict | None = None, now=None) -> dict:
    rules = rules if rules is not None else json.load(open(RULES_PATH, encoding="utf-8"))
    pages = {k: fetch(u, http) for k, u in P.items()}
    rows = check(pages, rules)
    t = time.time() if now is None else now
    n = {s: sum(1 for x in rows if x["status"] == s) for s in ("ok", "changed", "missing", "unreachable")}
    return {"t": int(t), "day": dt.datetime.fromtimestamp(t, ET).date().isoformat(), "counts": n, "rows": rows}


def _read(path) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def report(res: dict, path: str | None = None, sender=None, board=None) -> list:
    """Write the report; ONE alert + one board line per (rule, new value) never told before. -> the alerts sent."""
    path = path or REPORT_PATH
    old = _read(path)
    told = dict(old.get("told") or {})
    sent = []
    new = [r for r in res["rows"] if r["status"] == "changed" and f"rulewatch:{r['id']}:{r['seen']}" not in told]
    if len(new) > MAX_ALERTS:
        keys = [f"rulewatch:{r['id']}:{r['seen']}" for r in new]
        key = "rulewatch:digest:" + str(res.get("day") or res["t"])
        title = f"MFFU help pages: {len(new)} rules read differently today"[:120]
        body = ("Too many at once to be real rule changes: likely MFFU changed its page layout. The bot still uses the stored "
                "rules. Tell Claude to check: " + "; ".join(f"{r['what']} {fmt(r, r['stored'])} -> {fmt(r, r['seen'])}"
                                                            for r in new))[:600]
        if key not in told and (sender or _send)({"key": key, "title": title, "body": body}):
            for k in keys + [key]:
                told[k] = res["t"]
            sent.append(key)
        new = []
    for r in new:
        key = f"rulewatch:{r['id']}:{r['seen']}"
        title, body = alert_text(r)
        ok = (sender or _send)({"key": key, "title": title, "body": body})
        if ok:
            told[key] = res["t"]
            sent.append(key)
            try:
                (board or _board)(f"{title}: was {fmt(r, r['stored'])}, now {fmt(r, r['seen'])} ({r['url']})")
            except Exception:
                pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump({**res, "told": told}, fh, indent=1)
    os.replace(path + ".tmp", path)
    return sent


def _send(a: dict) -> bool:
    try:
        from engine import alert_bus as AB
        r = AB.send_critical({"kind": "problem", "key": a["key"], "title": a["title"], "body": a["body"], "notify_type": "problems",
                              "report": True}, wait=True)
        return r in ("sent", "queued", "dup")
    except Exception:
        return False


def _board(text: str):
    from engine import board_events as BE
    BE.emit("risk_alert", "pc", text[:300], {"src": "rules_watch"})


def due(now, path: str | None = None) -> bool:
    """Weekdays from 17:05 ET, once a day (the report's day)."""
    e = dt.datetime.fromtimestamp(now, ET)
    if e.weekday() >= 5 or e.hour * 60 + e.minute < RUN_FROM:
        return False
    rep = _read(path or REPORT_PATH)
    if rep.get("day") == e.date().isoformat():
        return False
    # red team 2: no page answered last time (PC offline / MFFU down): retry hourly, not every 15 min (each try can take
    # 9 pages x 12 s = ~2 min of tools/pc_report's run)
    return not (rep.get("day") is None and rep.get("t") and now - float(rep["t"]) < RETRY_S)


def maybe_run(now=None, http=None, sender=None, path: str | None = None) -> dict | None:
    """tools/pc_report.py's hook: one check a day after the close. Never raises."""
    try:
        now = time.time() if now is None else now
        if os.environ.get("LE_RULES_WATCH") == "0" or os.environ.get("LE_SELFTEST_CHILD") == "1" or not due(now, path):
            return None
        res = run(http=http, now=now)
        if not (res["counts"]["ok"] or res["counts"]["changed"]):
            res["day"] = None                 # no page answered (the PC offline, MFFU down): not "done", the next run tries again
        res["alerts"] = report(res, path=path, sender=sender)
        return res
    except Exception:
        return None


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    res = run()
    for r in res["rows"]:
        print(f"{r['status']:<12} {r['what']:<55} stored {fmt(r, r['stored']):>8}  page {fmt(r, r['seen']):>8}")
    print(json.dumps(res["counts"]))
    if "--alert" in a:
        print("alerts:", report(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
