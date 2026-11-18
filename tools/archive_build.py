#!/usr/bin/env python3
"""ARCHIVE builder: the library of everything we ever tested. READ ONLY, OFFLINE, stdlib only.
Writes tools/web_public/archive/index.json (+ runs-<k>.json shards) for the Archive page.

    python tools/archive_build.py                 # repo -> tools/web_public/archive/
    python tools/archive_build.py --out DIR       # write somewhere else
    python tools/archive_build.py --check         # exit 1 when the files are not what this script writes now
    python tools/archive_build.py --selftest

What goes in (all from the repo, nothing invented, no network):
  * every research run (research/runs/*.json, ~2,300): id, title, family, verdict (adopted / rejected / open), the two periods
    the Lab judges (2026, 2021-25) with n, trades a week, PF, net $, $ a month, pass10 / fail10 when the run has them
  * every write-up (research/writeups/*.md front matter: title, date, status, summary, runs)
  * the "Tested and rejected" list of docs/CLAUDE_REFERENCE.md (+ every write-up whose status says rejected): the Don't-redo list
  * the datasets under data/ (name, span, rows, source, last bar)
Sharding: index.json (< 400 KB) carries the facets, the write-ups, the rejected list, the datasets and every adopted / open run;
the rejected runs live in runs-<k>.json shards the page loads after the first paint.
Money, not only R: every run row keeps net $ and $ a month next to PF. A run with no number for a period says null, never 0.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "research", "runs")
WRITEUPS = os.path.join(ROOT, "research", "writeups")
REF = os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md")   # the list moved out of CLAUDE_REFERENCE.md (2026-11-18)
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "tools", "web_public", "archive")
INDEX_MAX = 380_000            # bytes: the first load stays under 400 KB
SHARD_RUNS = 450
FAMILY_ORDER = ["baseline", "risk", "stops", "targets", "management", "bias", "filters", "timing", "sessions", "winrate"]
VERDICT = {"baseline": 0, "adopt-candidate": 0, "rejected": 1, "promising": 2, "info": 2}      # 0 adopted, 1 rejected, 2 open
STATUS_WORD = {"baseline": "live baseline", "adopt-candidate": "adopt candidate", "rejected": "rejected", "promising": "promising", "info": "information"}
PREFIX_FAMILY = {"lit": "LIT research", "hq": "LIT headquarters", "atlas": "ATLAS", "atw": "ATLAS", "atx": "ATLAS", "atxd": "ATLAS", "losscut": "LIT loss rules"}
RUN_COLS = ["id", "title", "family", "strategy", "verdict", "status", "built", "periods", "m26", "mold", "writeup", "note"]
METRIC_KEYS = ("n", "tpw", "pf", "net", "per_month", "p10", "f10")     # the order of an m26 / mold list
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")

DATA_SOURCES = [
    (r"^NQ_", "TradingView CME NQ1! export (futures, never CFD)"), (r"^ES_", "TradingView CME ES1! export (futures)"),
    (r"^(VIX|VXN)_", "CBOE's own volatility index file"), (r"^CBOE_vol", "CBOE's own index file (VIX9D, VIX3M, VIX1D, VVIX, SKEW)"),
    (r"^GEX_", "daily dark-pool index (DIX) and gamma exposure (GEX) file"), (r"^NQJ_", "NQ contract-by-contract import"),
    (r"^events", "scheduled US releases (BLS and the Federal Reserve calendars)"),
]


def _load(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _num(x, k=2):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return int(round(v)) if k == 0 else round(v, k)


def clean_text(s, n):
    s = re.sub(r"[`*_<>]", "", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:70] or "doc"


# ------------------------------------------------------------------------------------------------ runs
def strategy_of(rid, tags):
    return 1 if str(rid).lower().startswith("lit") or "lit" in [str(t).lower() for t in tags or []] else 0   # 1 = LIT, 0 = the older engine


def family_of(r):
    fam = str(r.get("family") or "other")
    if fam != "other":
        return fam
    pre = re.split(r"[_\-]", str(r.get("id")))[0].lower()
    return PREFIX_FAMILY.get(pre) or ("other tests")


def metrics(sp):
    """[n, trades a week, PF, net $, $ a month, pass10 %, fail10 %] of one period, or 0 when the run has no such period."""
    if not isinstance(sp, dict) or not sp.get("n"):
        return 0
    return [_num(sp.get("n"), 0), _num(sp.get("tpw")), _num(sp.get("pf")), _num(sp.get("net"), 0), _num(sp.get("per_month"), 0),
            _num(sp.get("p10"), 1), _num(sp.get("f10"), 1)]


def run_row(r, writeup_slugs):
    rid = str(r["id"])
    sp = r.get("spans") or {}
    status = r.get("status") if r.get("status") in VERDICT else "info"
    m26, mold = metrics(sp.get("2026")), metrics(sp.get("2021-25"))
    periods = (1 if m26 else 0) | (2 if mold else 0)
    wu = str(r.get("writeup") or "")
    if wu not in writeup_slugs:
        wu = ""
    built = str(r.get("built") or "")[:10]
    return [rid, clean_text(r.get("title"), 80), family_of(r), strategy_of(rid, r.get("tags")), VERDICT[status], status, built[2:] if len(built) == 10 else "",
            periods, m26, mold, wu, clean_text(r.get("verdict"), 110)]


def read_runs(runs_dir=RUNS, writeup_slugs=()):
    rows, skipped = [], []
    for p in sorted(glob.glob(os.path.join(runs_dir, "*.json"))):
        name = os.path.basename(p)
        if name == "index.json":
            continue
        r = _load(p)
        if not isinstance(r, dict) or not SAFE_ID.match(str(r.get("id") or "")) or str(r["id"]) + ".json" != name or not isinstance(r.get("spans"), dict):
            skipped.append(name)
            continue
        rows.append(run_row(r, writeup_slugs))
    return rows, skipped


# ------------------------------------------------------------------------------------------------ write-ups
def front(text):
    m = re.match(r"^﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|$)", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip():
            meta[k.strip().lower()] = v.strip().strip("\"'")
    return meta, text[m.end():]


def read_writeups(folder=WRITEUPS):
    out = []
    for p in sorted(glob.glob(os.path.join(folder, "*.md"))):
        stem = os.path.splitext(os.path.basename(p))[0]
        if stem.upper() == "INDEX":
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                raw = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        meta, body = front(raw)
        h1 = re.search(r"^#\s+(.+)$", body, re.M)
        date = meta.get("date") or (re.match(r"\d{4}-\d{2}-\d{2}", stem).group(0) if re.match(r"\d{4}-\d{2}-\d{2}", stem) else "")
        status = (meta.get("status") or "info").lower()
        word = re.split(r"[\s(;:,-]+", status)[0]
        word = word if word in ("rejected", "adopt-candidate", "promising", "info", "finding", "research") else "info"
        summary = meta.get("summary") or ""
        if not summary:
            para = next((x.strip() for x in re.split(r"\n\s*\n", body) if x.strip() and not x.lstrip().startswith(("#", "|", "-", ">"))), "")
            summary = para
        runs = [x for x in re.split(r"[,\s]+", meta.get("runs", "")) if x and SAFE_ID.match(x)]
        out.append({"slug": slugify(stem), "title": clean_text(meta.get("title") or (h1.group(1) if h1 else stem), 120), "date": date[:10], "status": word,
                    "verdict": 1 if word == "rejected" else (0 if word == "adopt-candidate" else 2), "family": meta.get("family", "other").lower(),
                    "summary": clean_text(summary, 230), "runs": runs[:6]})
    out.sort(key=lambda d: (d["date"], d["title"]), reverse=True)
    return out


# ------------------------------------------------------------------------------------------------ the rejected list
def rejected_list(ref=REF, slugs=()):
    """Top-level bullets of the 'Tested and rejected' section of docs/CLAUDE_REFERENCE.md."""
    try:
        with open(ref, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return []
    start = next((i for i, ln in enumerate(lines) if ln.startswith("## Tested and rejected")), None)
    if start is None:
        return []
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    items, cur = [], None
    for ln in lines[start + 1:end]:
        if ln.startswith("- "):
            if cur:
                items.append(cur)
            cur = [ln[2:]]
        elif cur is not None and (ln.startswith("  ") or not ln.strip()):
            cur.append(ln.strip())
        elif cur is not None:
            items.append(cur)
            cur = None
    if cur:
        items.append(cur)
    out = []
    for it in items:
        raw = " ".join(x for x in it if x)
        m = re.match(r"\*\*(.+?)\*\*", raw)
        title = m.group(1) if m else re.split(r"(?<=[.;:])\s", raw, maxsplit=1)[0]
        title = re.split(r"\s\(", title, maxsplit=1)[0] if len(re.split(r"\s\(", title, maxsplit=1)[0]) >= 12 else title
        title = title.strip(" :;,.")
        linked = []
        for s in re.findall(r"([a-z0-9][a-z0-9_.-]*)\.md", raw):
            k = slugify(s)
            if k in slugs and k not in linked:
                linked.append(k)
        out.append({"title": clean_text(title, 110), "text": clean_text(raw, 650), "writeups": linked[:4], "src": "docs/TESTED_AND_REJECTED.md"})
    return out


# ------------------------------------------------------------------------------------------------ datasets
def _tail(path, n=1):
    with open(path, "rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        back = min(size, 4096)
        fh.seek(size - back)
        lines = [x for x in fh.read().decode("utf-8", "replace").splitlines() if x.strip()]
    return lines[-n:]


def _stamp(v):
    """The date of a first column: epoch seconds or an ISO date."""
    v = v.strip()
    if re.match(r"^\d{9,11}$", v):
        return dt.datetime.fromtimestamp(int(v), dt.timezone.utc).strftime("%Y-%m-%d")
    return v[:10]


def datasets(folder=DATA):
    out = []
    files = sorted(glob.glob(os.path.join(folder, "*.csv"))) + sorted(glob.glob(os.path.join(folder, "news", "events.csv")))
    for p in files:
        name = os.path.basename(p)
        try:
            with open(p, encoding="utf-8", newline="") as fh:
                head = fh.readline().strip().split(",")
                first = fh.readline().split(",")[0]
                rows = 1 + sum(1 for _ in fh)
            last_line = _tail(p)[0]
        except (OSError, IndexError, UnicodeDecodeError):
            continue
        src = next((s for rx, s in DATA_SOURCES if re.search(rx, name)), "saved in data/")
        bar = re.search(r"_(\w+)\.csv$", name)
        last = last_line.split(",")[0]
        out.append({"name": name, "kind": (bar.group(1) if bar else "events"), "first": _stamp(first), "last": _stamp(last), "rows": rows,
                    "cols": [c for c in head if c][:8], "source": src, "file": "data/" + name if "events" not in name else "data/news/" + name})
    return out


# ------------------------------------------------------------------------------------------------ build
def build(runs_dir=RUNS, writeups_dir=WRITEUPS, ref=REF, data_dir=DATA):
    wu = read_writeups(writeups_dir)
    slugs = {w["slug"] for w in wu}
    rows, skipped = read_runs(runs_dir, slugs)
    rej = rejected_list(ref, slugs)
    rej += [{"title": w["title"], "text": w["summary"], "writeups": [w["slug"]], "src": "write-up " + w["slug"]} for w in wu if w["verdict"] == 1]
    ds = datasets(data_dir)
    fams = {}
    for r in rows:
        f = fams.setdefault(r[2], {"name": r[2], "runs": 0, "adopted": 0, "rejected": 0, "open": 0})
        f["runs"] += 1
        f[("adopted", "rejected", "open")[r[4]]] += 1
    order = {k: i for i, k in enumerate(FAMILY_ORDER)}
    families = sorted(fams.values(), key=lambda f: (-f["runs"], order.get(f["name"], 99)))
    dates = [r[6] for r in rows if r[6]] + [w["date"][2:] for w in wu if w["date"]]
    built = ("20" + max(dates)) if dates else ""
    rows.sort(key=lambda r: (r[4] if r[4] != 1 else 3, r[2], r[0]))
    first = [r for r in rows if r[4] != 1]
    rest = [r for r in rows if r[4] == 1]
    shards = [rest[i:i + SHARD_RUNS] for i in range(0, len(rest), SHARD_RUNS)]
    index = {"v": 1, "built": built, "label": "History, not a forecast. Money figures are after costs; 1 MNQ micro = $2 a point. A run is one stored backtest of the library.",
             "cols": RUN_COLS, "metric_cols": list(METRIC_KEYS), "counts": {"runs": len(rows), "writeups": len(wu), "rejected_ideas": len(rej), "datasets": len(ds),
             "adopted": sum(1 for r in rows if r[4] == 0), "rejected": len(rest), "open": sum(1 for r in rows if r[4] == 2)},
             "families": families, "verdicts": ["adopted", "rejected", "open"], "writeups": wu, "rejected": rej, "datasets": ds, "runs": first,
             "shards": [f"runs-{k}.json" for k in range(len(shards))], "skipped": skipped}
    return index, shards


def dump(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=False)


def files_of(index, shards):
    out = {"index.json": dump(index)}
    for k, s in enumerate(shards):
        out[f"runs-{k}.json"] = dump({"v": 1, "shard": k, "runs": s})
    return out


def write(out, **kw):
    index, shards = build(**kw)
    fs = files_of(index, shards)
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "runs-*.json")):
        os.remove(old)
    for n, text in fs.items():
        with open(os.path.join(out, n), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return index, fs


def check(out, **kw):
    index, shards = build(**kw)
    fs = files_of(index, shards)
    bad = []
    for n, text in fs.items():
        p = os.path.join(out, n)
        try:
            with open(p, encoding="utf-8", newline="") as fh:
                if fh.read() != text:
                    bad.append(n)
        except OSError:
            bad.append(n)
    have = {os.path.basename(p) for p in glob.glob(os.path.join(out, "runs-*.json"))}
    bad += sorted(have - set(fs))
    return bad, len(fs["index.json"].encode("utf-8"))


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    ok = True

    def t(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and bool(cond)
    tmp = tempfile.mkdtemp(prefix="archive-st-")
    runs, wdir, data = (os.path.join(tmp, x) for x in ("runs", "wu", "data"))
    for d in (runs, wdir, os.path.join(data, "news")):
        os.makedirs(d)
    span = {"n": 120, "tpw": 2.9, "pf": 4.19, "net": 43820, "per_month": 4467, "p10": 31.6, "f10": 1.0}
    for rid, st, fam, sp in (("lit_a", "adopt-candidate", "other", {"2026": span, "2021-25": {"n": 0}}), ("risk_b", "rejected", "risk", {"2021-25": {**span, "pf": float("inf")}}),
                             ("x_c", "weird", "zzz", {"2026": {"n": 5}})):
        with open(os.path.join(runs, rid + ".json"), "w") as fh:
            json.dump({"id": rid, "title": "T " + rid, "family": fam, "status": st, "verdict": "v <b>x</b>", "spans": sp, "built": "2026-11-01T10:00:00", "writeup": "w1" if rid == "lit_a" else ""}, fh)
    with open(os.path.join(runs, "bad.json"), "w") as fh:
        fh.write("{nope")
    with open(os.path.join(runs, "index.json"), "w") as fh:
        fh.write("{}")
    with open(os.path.join(wdir, "w1.md"), "w") as fh:
        fh.write("---\ntitle: First\ndate: 2026-11-02\nstatus: rejected (nothing to switch)\nsummary: It did not work.\nruns: lit_a, risk_b\n---\n# First\nbody\n")
    with open(os.path.join(wdir, "INDEX.md"), "w") as fh:
        fh.write("# index\n")
    ref = os.path.join(tmp, "ref.md")
    with open(ref, "w") as fh:
        fh.write("## Tested and rejected (don't redo)\n- Fixed 10-15 pt stops: wicked out. See `w1.md`.\n- **Big idea (2026-10-27, `w1.md`):** skip the trade.\n  more words\n\n## Next\n- not me\n")
    with open(os.path.join(data, "NQ_5m.csv"), "w") as fh:
        fh.write("time,open,high,low,close,volume\n1634508000,1,2,0,1,5\n1792184100,1,2,0,1,5\n")
    with open(os.path.join(data, "VIX_1d.csv"), "w") as fh:
        fh.write("date,open,high,low,close\n2021-10-15,1,2,0,1\n2026-10-16,1,2,0,1\n")
    with open(os.path.join(data, "news", "events.csv"), "w") as fh:
        fh.write("date,time_et,event,impact,source\n2021-01-27,14:00,FOMC,high,x\n")
    idx, shards = build(runs, wdir, ref, data)
    t("3 runs read, junk and index.json skipped", idx["counts"]["runs"] == 3 and idx["skipped"] == ["bad.json"])
    rows = {r[0]: r for r in idx["runs"] + [x for s in shards for x in s]}
    t("verdict map: adopt-candidate adopted, rejected rejected, unknown status open", rows["lit_a"][4] == 0 and rows["risk_b"][4] == 1 and rows["x_c"][4] == 2)
    t("a family 'other' with id prefix lit is LIT research; an unknown family stays as written", rows["lit_a"][2] == "LIT research" and rows["x_c"][2] == "zzz")
    t("money next to PF: net and $ a month kept; a missing period is 0 (never zeros); inf is null", rows["lit_a"][8][3] == 43820 and rows["lit_a"][8][4] == 4467 and rows["lit_a"][9] == 0 and rows["risk_b"][9][2] is None and rows["lit_a"][7] == 1)
    t("markup stripped from the verdict text; the write-up link is kept only when it exists", "<" not in rows["lit_a"][11] and rows["lit_a"][10] == "w1" and rows["risk_b"][10] == "")
    t("write-up front matter read, INDEX skipped, rejected status word", len(idx["writeups"]) == 1 and idx["writeups"][0]["status"] == "rejected" and idx["writeups"][0]["runs"] == ["lit_a", "risk_b"])
    t("rejected list: two bullets from the section only, the bold title, the linked write-up; plus the rejected write-up", len(idx["rejected"]) == 3 and idx["rejected"][1]["title"].startswith("Big idea") and idx["rejected"][1]["writeups"] == ["w1"])
    t("datasets: span, rows, source, last bar; the events file is found", {d["name"]: (d["first"], d["last"], d["rows"]) for d in idx["datasets"]} == {"NQ_5m.csv": ("2021-10-17", "2026-10-16", 2), "VIX_1d.csv": ("2021-10-15", "2026-10-16", 2), "events.csv": ("2021-01-27", "2021-01-27", 1)}
      and idx["datasets"][0]["source"].startswith("TradingView"))
    t("shards: rejected runs only, outside index.json", len(shards) == 1 and [r[0] for r in shards[0]] == ["risk_b"] and "risk_b" not in [r[0] for r in idx["runs"]])
    out = os.path.join(tmp, "out")
    write(out, runs_dir=runs, writeups_dir=wdir, ref=ref, data_dir=data)
    bad, _ = check(out, runs_dir=runs, writeups_dir=wdir, ref=ref, data_dir=data)
    t("--check passes on what write() wrote and fails after an edit", bad == [])
    with open(os.path.join(out, "index.json"), "a") as fh:
        fh.write(" ")
    bad2, _ = check(out, runs_dir=runs, writeups_dir=wdir, ref=ref, data_dir=data)
    t("--check sees a changed file", bad2 == ["index.json"])
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.check:
        bad, size = check(a.out)
        if bad:
            print("archive is stale: rebuild with `python tools/archive_build.py`:", ", ".join(bad))
            return 1
        print(f"archive is current (index.json {size / 1024:.0f} KB)")
        return 0
    index, fs = write(a.out)
    size = len(fs["index.json"].encode("utf-8"))
    c = index["counts"]
    print(f"archive: {c['runs']} runs ({c['adopted']} adopted, {c['rejected']} rejected, {c['open']} open), {c['writeups']} write-ups, "
          f"{c['rejected_ideas']} rejected ideas, {c['datasets']} datasets; index.json {size / 1024:.0f} KB + {len(index['shards'])} shards -> {a.out}")
    if size > INDEX_MAX:
        print(f"index.json is over {INDEX_MAX // 1000} KB", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
