"""Official Tier-1 calendar from free primary sources -> data/news/events.csv (future rows only).

MFFU's Tier-1 list (news trading policy, help center, checked 2026-11-17): FOMC meetings, FOMC minutes, Employment Report,
CPI. A restricted account (the Rapid sim funded) must be flat with no order from 2 min before to 2 min after each one
(the bot: -3 / +2.5 min, engine/multi_account NEWS_PRE_S / NEWS_POST_S). GDP / PCE (BEA) are NOT Tier-1 for MFFU, so
they are not fetched here. PPI is fetched as "medium" (useful on the calendar, not a Tier-1 window).

Sources (plain GETs, one per source per run, no key, no paid service)
  CPI                    https://www.bls.gov/schedule/news_release/cpi.htm      08:30 ET
  Employment Situation   https://www.bls.gov/schedule/news_release/empsit.htm   08:30 ET
  PPI                    https://www.bls.gov/schedule/news_release/ppi.htm      08:30 ET
  FOMC                   https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
                         decision 14:00, press conference 14:30, minutes 14:00 (the page's "Released" date, else 3 weeks
                         after the decision: every 2025-26 minutes release was 3 weeks after, labelled "derived")

What it writes
  data/news/events.csv          only rows dated from today on, only for a source that fetched AND parsed (sanity: enough
                                future dates, all weekdays); past rows (the backtest calendar) are never touched.
                                Each row's source says where it came from and the day it was fetched.
  data/news/official_meta.json  per source: url, ok, last good fetch, rows, coverage, last error.
  A source that fails (network, 403, a changed page) keeps its old rows: a failed run changes nothing.

    python -X utf8 -m engine.news_official                  fetch + merge (the PC ops task runs this once a day)
    python -X utf8 -m engine.news_official --dry-run        fetch + show what would change, write nothing
    python -X utf8 -m engine.news_official --from-dir DIR   read <slug>.htm files from DIR instead of the network
    python -X utf8 -m engine.news_official --blocked 2026-12 2027-12   minutes blocked per month on the Rapid funded lane
Tests: python -X utf8 -m tests.test_news_official (offline fixtures under tests/fixtures/news/official/).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as html_mod
import io
import json
import os
import re
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_DIR = os.path.join(ROOT, "data", "news")
EVENTS = os.path.join(NEWS_DIR, "events.csv")
META = os.path.join(NEWS_DIR, "official_meta.json")
RAW_DIR = os.path.join(NEWS_DIR, "raw", "official")          # gitignored (data/news/raw/)
ET_TZ = ZoneInfo("America/New_York")
TIMEOUT = 20
# an honest client name (BLS asks robots to identify themselves); LE_NEWS_UA on the PC can add a contact (never committed)
UA = os.environ.get("LE_NEWS_UA") or "Mozilla/5.0 (compatible; nq-liquidity-engine-calendar/1.0; 4 requests a day)"
COLS = ["date", "time_et", "event", "impact", "source"]

SOURCES = [
    {"slug": "bls_cpi", "kind": "cpi", "url": "https://www.bls.gov/schedule/news_release/cpi.htm",
     "event": "CPI (consumer inflation)", "impact": "high", "min_future": 3},
    {"slug": "bls_empsit", "kind": "nfp", "url": "https://www.bls.gov/schedule/news_release/empsit.htm",
     "event": "Non-Farm Payrolls (jobs report)", "impact": "high", "min_future": 3},
    {"slug": "bls_ppi", "kind": "ppi", "url": "https://www.bls.gov/schedule/news_release/ppi.htm",
     "event": "PPI (producer inflation)", "impact": "medium", "min_future": 3},
    {"slug": "fed_fomc", "kind": "fomc", "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
     "min_future": 2},
]

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"]
_MON = {m.lower(): i for i, m in enumerate(MONTHS, 1)}
_MON.update({m[:3].lower(): i for i, m in enumerate(MONTHS, 1)})
_MON["sept"] = 9


# ------------------------------------------------------------------------------------------------------------ helpers
def _today() -> str:
    return dt.datetime.now(ET_TZ).date().isoformat()


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _mon(name: str) -> int | None:
    n = name.strip().rstrip(".").lower()
    return _MON.get(n) or _MON.get(n[:3])


def kind_of(event: str) -> str | None:
    """Which official source owns a calendar row (by its event name), else None (left alone)."""
    ev = str(event or "")
    low = ev.lower()
    if "PPI" in ev:
        return "ppi"
    if "CPI" in ev:
        return "cpi"
    if ("Non-Farm Payrolls" in ev or ("Non-Farm Employment Change" in ev and "ADP" not in ev)
            or "Employment Report" in ev or "Employment Situation" in ev):
        return "nfp"
    if ev.startswith("FOMC") or ("minutes" in low and ("fed" in low or "fomc" in low)):
        return "fomc"
    return None


# ------------------------------------------------------------------------------------------------------------ parsers
_DATE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),\s*(\d{4})")
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*([AaPp])\.?[Mm]")


def parse_bls_schedule(html: str) -> list:
    """[(release date YYYY-MM-DD, HH:MM ET)] from a BLS per-release schedule page (a table: reference month, release date,
    release time). Rows without a full date are skipped; a row without a time gets 08:30 (every one of these is 08:30)."""
    out = []
    lists = re.findall(r'<table[^>]*class="release-list"[^>]*>(.*?)</table>', html, re.S | re.I)
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", "".join(lists) if lists else html, re.S | re.I):
        cells = [_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)]
        line = " | ".join(cells)
        m = _DATE.search(line)
        if not m:
            continue
        mon = _mon(m.group(1))
        try:
            day = dt.date(int(m.group(3)), mon, int(m.group(2)))
        except (TypeError, ValueError):
            continue
        hm = "08:30"
        t = _TIME.search(line[m.end():])
        if t:
            h = int(t.group(1)) % 12 + (12 if t.group(3).lower() == "p" else 0)
            hm = f"{h:02d}:{int(t.group(2)):02d}"
        out.append((day.isoformat(), hm))
    return sorted(set(out))


def parse_fomc(html: str) -> list:
    """[{decision, sep, minutes, minutes_derived, label}] from the Fed's FOMC calendar page: every scheduled meeting
    (notation votes / unscheduled / cancelled skipped), the decision on its last day."""
    out = []
    parts = re.split(r"(\d{4}) FOMC Meetings", html)
    for k in range(1, len(parts) - 1, 2):
        year, body = int(parts[k]), parts[k + 1]
        chunks = re.split(r"(?=<div[^>]*fomc-meeting__month)", body)
        for ch in chunks[1:]:
            mm = re.search(r"fomc-meeting__month[^>]*>\s*(?:<strong>)?([^<]+)", ch)
            dd = re.search(r"fomc-meeting__date[^>]*>([^<]+)<", ch)
            if not mm or not dd:
                continue
            mon_txt, day_txt = mm.group(1).strip(), dd.group(1).strip()
            low = day_txt.lower()
            if "notation" in low or "unscheduled" in low or "cancel" in low:
                continue
            nums = re.findall(r"\d+", day_txt)
            m = _mon(mon_txt.split("/")[-1])
            if not nums or not m:
                continue
            y = year + (1 if m == 1 and mon_txt.lower().startswith("dec") else 0)     # "Dec/Jan" spans a year end
            try:
                dec = dt.date(y, m, int(nums[-1]))
            except ValueError:
                continue
            rel = re.search(r"Released\s+([A-Za-z]+)\.?\s+(\d{1,2}),\s*(\d{4})", _text(ch))
            minutes, derived = None, True
            if rel and _mon(rel.group(1)):
                try:
                    minutes, derived = dt.date(int(rel.group(3)), _mon(rel.group(1)), int(rel.group(2))), False
                except ValueError:
                    minutes = None
            if minutes is None:
                minutes = dec + dt.timedelta(days=21)
            out.append({"decision": dec.isoformat(), "sep": "*" in day_txt, "minutes": minutes.isoformat(),
                        "minutes_derived": derived, "label": f"{MONTHS[dec.month - 1][:3]}"})
    seen, uniq = set(), []
    for e in sorted(out, key=lambda e: e["decision"]):
        if e["decision"] not in seen:
            seen.add(e["decision"])
            uniq.append(e)
    return uniq


def rows_for(src: dict, raw: str, fetched: str) -> list:
    """Calendar rows (dicts with COLS) one source's page gives."""
    if src["kind"] == "fomc":
        tag = f"federalreserve.gov FOMC calendar (fetched {fetched})"
        rows = []
        for e in parse_fomc(raw):
            rows.append({"date": e["decision"], "time_et": "14:00", "impact": "high", "source": tag,
                         "event": "FOMC rate decision" + (" + projections" if e["sep"] else "")})
            rows.append({"date": e["decision"], "time_et": "14:30", "impact": "high", "source": tag,
                         "event": "FOMC press conference"})
            rows.append({"date": e["minutes"], "time_et": "14:00", "impact": "high",
                         "event": f"FOMC minutes ({e['label']} meeting)",
                         "source": tag[:-1] + "; 3 weeks after the meeting, derived)" if e["minutes_derived"] else tag})
        return rows
    tag = f"bls.gov release schedule (fetched {fetched})"
    return [{"date": d, "time_et": hm, "event": src["event"], "impact": src["impact"], "source": tag}
            for d, hm in parse_bls_schedule(raw)]


def sane(src: dict, rows: list, today: str) -> str | None:
    """None when the parse looks right, else why not (then the old rows stay)."""
    fut = [r for r in rows if r["date"] >= today]
    days = {r["date"] for r in fut if not r["event"].startswith("FOMC press") and "minutes" not in r["event"]}
    if len(days) < src.get("min_future", 1):
        return f"only {len(days)} future dates parsed (page changed?)"
    for d in {r["date"] for r in fut}:
        if dt.date.fromisoformat(d).weekday() >= 5:
            return f"{d} is a weekend (bad parse)"
    return None


# ------------------------------------------------------------------------------------------------------------ fetch
def http_get(url: str, timeout: int = TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(3_000_000)
    text = raw.decode("utf-8", "ignore")
    if "Access Denied" in text[:3000] and "<table" not in text:
        raise RuntimeError("access denied page")
    return text


def _save_raw(slug: str, text: str, raw_dir: str):
    try:
        os.makedirs(raw_dir, exist_ok=True)
        with open(os.path.join(raw_dir, f"{slug}.htm"), "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        pass


# ------------------------------------------------------------------------------------------------------------ merge
def read_events(path: str = EVENTS) -> list:
    import csv
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return [{c: (r.get(c) or "") for c in COLS} for r in csv.DictReader(fh)]


def to_csv(rows: list) -> str:
    import csv
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in COLS})
    return buf.getvalue()


def coverage_end(kind: str, rows: list) -> str:
    """Last day a source speaks for: BLS its last listed release; the Fed page lists whole years, so a meeting that is
    not on it for that year (e.g. an old guess at a December meeting) is not one: Dec 31 of its last year."""
    last = max(r["date"] for r in rows)
    if kind == "fomc":
        dec = [r["date"] for r in rows if r["event"].startswith("FOMC rate decision")]
        return max(last, (max(dec)[:4] + "-12-31") if dec else last)
    return last


def merge(old: list, fresh_by_kind: dict, today: str) -> list:
    """Old rows, except a fetched kind's rows dated today .. coverage_end, which its fresh rows replace. Past rows and
    other kinds are kept as they are. Sorted by date, time; exact duplicates dropped."""
    ends = {k: coverage_end(k, rows) for k, rows in fresh_by_kind.items()}
    keep = []
    for r in old:
        k = kind_of(r["event"])
        if k in ends and today <= r["date"] <= ends[k]:
            continue
        keep.append(r)
    for rows in fresh_by_kind.values():
        keep += [r for r in rows if r["date"] >= today]
    seen, out = set(), []
    for r in sorted(keep, key=lambda r: (r["date"], r["time_et"])):
        key = (r["date"], r["time_et"], r["event"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _read_meta(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _write(path: str, text: str) -> bool:
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            if fh.read() == text:
                return False
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)
    return True


def refresh(fetch=http_get, from_dir: str | None = None, events_path: str = EVENTS, meta_path: str = META,
            raw_dir: str = RAW_DIR, today: str | None = None, dry_run: bool = False, log=print) -> dict:
    """Fetch every source, merge the good ones into events.csv. Never raises; returns a summary
    {"ok": n good sources, "changed": events.csv rewritten, "sources": {...}, "added": [...], "removed": [...]}."""
    today = today or _today()
    meta = _read_meta(meta_path)
    srcs_meta = meta.get("sources") or {}
    fresh, summary = {}, {"ok": 0, "changed": False, "sources": {}, "added": [], "removed": []}
    for src in SOURCES:
        m = dict(srcs_meta.get(src["slug"]) or {})
        m.update(url=src["url"], tried=today)
        try:
            if from_dir:
                with open(os.path.join(from_dir, f"{src['slug']}.htm"), encoding="utf-8") as fh:
                    raw = fh.read()
            else:
                raw = fetch(src["url"])
                _save_raw(src["slug"], raw, raw_dir)
            rows = rows_for(src, raw, today)
            why = sane(src, rows, today)
            if why:
                raise ValueError(why)
            fresh[src["kind"]] = rows
            fut = [r["date"] for r in rows if r["date"] >= today]
            m.update(ok=True, fetched=today, rows=len(fut), coverage=[min(fut), max(fut)], error=None)
            summary["ok"] += 1
        except Exception as e:                               # network, 403, changed page: this source keeps its old rows
            m.update(ok=False, error=f"{e.__class__.__name__}: {str(e)[:160]}")
        summary["sources"][src["slug"]] = m
        log(f"  {src['slug']:<11} {'OK ' if m.get('ok') else 'kept old rows: ' + str(m.get('error'))}"
            + (f" {m['rows']} future rows {m['coverage'][0]} .. {m['coverage'][1]}" if m.get("ok") else ""))
    try:
        old = read_events(events_path)
        new = merge(old, fresh, today) if fresh else old
        ok_key = lambda r: (r["date"], r["time_et"], r["event"])
        before, after = {ok_key(r) for r in old}, {ok_key(r) for r in new}
        summary["added"] = sorted(after - before)
        summary["removed"] = sorted(before - after)
        if not dry_run:
            if fresh:
                summary["changed"] = _write(events_path, to_csv(new))
            meta = {"updated": today, "note": "engine/news_official.py: official Tier-1 calendar (MFFU T1 = FOMC, minutes, "
                    "jobs report, CPI); a failed source keeps its old rows", "sources": summary["sources"]}
            _write(meta_path, json.dumps(meta, indent=1, sort_keys=True) + "\n")
    except Exception as e:
        summary["error"] = f"{e.__class__.__name__}: {e}"
    return summary


# ------------------------------------------------------------------------------------------------------------ report
def blocked_minutes(first: str, last: str) -> list:
    """Per month: Tier-1 releases, weekdays on the 08:30 fallback, minutes the Rapid funded lane may not hold / enter
    (engine/rapid RapidAtlas.news_at: [release - NEWS_PRE_S, release + NEWS_POST_S)), all and inside 09:30-16:00 ET."""
    from . import multi_account as MA
    MA._NEWS["key"] = None
    pre, post = MA.NEWS_PRE_S, MA.NEWS_POST_S
    d, end = dt.date.fromisoformat(first + "-01"), dt.date.fromisoformat(last + "-01")
    end = (end.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    rows = {}
    while d < end:
        day = d.isoformat()
        rel = MA.tier1_releases(day)
        fb = bool(MA._fallback_830(day)) and day >= MA.T1_FALLBACK_FROM and (
            day[:7] not in MA._NEWS["cpi"] or day[:7] not in MA._NEWS["nfp"])
        wins = sorted((r - pre, r + post) for r in rel)
        merged = []
        for a, b in wins:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        o = dt.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET_TZ).timestamp()
        c = dt.datetime(d.year, d.month, d.day, 16, 0, tzinfo=ET_TZ).timestamp()
        r = rows.setdefault(day[:7], {"month": day[:7], "releases": 0, "fallback_days": 0, "blocked_min": 0.0,
                                      "blocked_rth_min": 0.0})
        r["releases"] += len(MA._NEWS["rel"].get(day, ()))
        r["fallback_days"] += 1 if fb else 0
        r["blocked_min"] += sum(b - a for a, b in merged) / 60
        r["blocked_rth_min"] += sum(max(0, min(b, c) - max(a, o)) for a, b in merged) / 60
        d += dt.timedelta(days=1)
    return list(rows.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from-dir")
    ap.add_argument("--blocked", nargs=2, metavar=("FROM", "TO"))
    a = ap.parse_args(argv)
    if a.blocked:
        rows = blocked_minutes(*a.blocked)
        print(f"{'month':<8} {'T1 releases':>11} {'08:30 fallback days':>19} {'blocked min':>11} {'in 09:30-16:00':>14}")
        for r in rows:
            print(f"{r['month']:<8} {r['releases']:>11} {r['fallback_days']:>19} {r['blocked_min']:>11.1f} {r['blocked_rth_min']:>14.1f}")
        print(f"{'total':<8} {sum(r['releases'] for r in rows):>11} {sum(r['fallback_days'] for r in rows):>19} "
              f"{sum(r['blocked_min'] for r in rows):>11.1f} {sum(r['blocked_rth_min'] for r in rows):>14.1f}")
        return 0
    s = refresh(from_dir=a.from_dir, dry_run=a.dry_run)
    print(f"{s['ok']}/{len(SOURCES)} sources OK; events.csv {'rewritten' if s['changed'] else 'unchanged'}"
          f"; +{len(s['added'])} / -{len(s['removed'])} rows" + (" (dry run)" if a.dry_run else ""))
    for k in s["added"]:
        print("  +", *k)
    for k in s["removed"]:
        print("  -", *k)
    return 0 if "error" not in s else 1


if __name__ == "__main__":
    sys.exit(main())
