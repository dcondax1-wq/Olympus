#!/usr/bin/env python3
"""PINAKES, the catalogue of every table OLYMPUS keeps (2026-11-11). Builds tools/web_public/pinakes/catalog.json: one small card per table.

It never copies data. Each card says where the table lives (its real URL on the site) and what is in it; the page loads the rows from that URL when you open it.

    python tools/pinakes_build.py                 rewrite tools/web_public/pinakes/catalog.json
    python tools/pinakes_build.py --check         exit 1 when catalog.json is not what this script writes now
    python tools/pinakes_build.py --selftest      the inference rules on tricky data (nulls, mixed types, unicode, maps, matrices)
    python tools/pinakes_build.py --web <site>    read another site folder (the BUILT site: then home.json, data.json, money/*.json ... are read too)
    python tools/pinakes_build.py --out <file>    write somewhere else

Three kinds of card:
  site      a JSON data file in the site folder (fixtures, city.json, edges.json, events.json, trades.json ...): rows, columns with types, 3 sample rows, freshness, size
  build     a file other apps read that only exists after the site build (home.json, data.json, intel.json, money/*.json ...): described here, measured when the
            builder is pointed at a built site (--web <site>), otherwise the page measures it when you open it
  research  the CSV datasets under data/ (futures bars, VIX, news): span and rows only, never published, never downloadable

Stdlib only, offline, read only. The inference rules here are the same ones as tools/web_public/pinakes/pinakescore.js (tests/test_pinakes_page.py checks they agree).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(WEB, "pinakes", "catalog.json")
DISTRICTS = ("Market", "Research", "Money", "Command", "Life")

# ------------------------------------------------------------------------------------------------ inference (mirrors pinakescore.js)
MAX_DEPTH, MAX_KEYS, SAMPLE_N, MAX_COLS, FLAT_KEYS = 4, 200, 500, 60, 12
DATE_RE = re.compile(r"^\d{4}-\d\d-\d\d(?:[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:?\d\d)?)?$")
NUMSTR_RE = re.compile(r"^-?\$?-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?$")
USD_RE = re.compile(r"(?:^|[_. ])(?:usd|pnl|net|dollars?|cost|costs|fee|fees|profit|balance|equity|payout|payouts|amount|cash|gross|revenue|income|spend|budget|per_month|usd_month)(?:$|[_. ])|\$")
R_RE = re.compile(r"(?:^|[_. ])(?:r|rr|rmult|r_mult|r_multiple)(?:$|[_. ])")
EPOCH_RE = re.compile(r"(?:^|[_. ])(?:t|ts|time|asof|updated|created|built|generated|at|when|epoch|stamp|timestamp)(?:$|[_. ])")
FRESH_KEYS = ("asof", "as_of", "built", "generated", "generated_at", "updated", "updated_at", "published", "t", "ts", "time", "date", "last", "when")


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def kind_of(v):
    """null | bool | num | numstr | date | str | json"""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num" if math.isfinite(v) else "null"
    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return "null"
        if DATE_RE.match(s):
            return "date"
        if NUMSTR_RE.match(s) and len(s) <= 24:
            return "numstr"
        return "str"
    return "json"


def is_epoch(v):
    return is_num(v) and (9.0e8 <= v <= 2.2e9 or 9.0e11 <= v <= 2.2e12)


def col_type(name, kinds, values=()):
    """kinds = the set of value kinds seen (without null); values = the numeric values (for the epoch test)."""
    k = set(kinds) - {"null"}
    low = str(name).lower()
    if not k:
        return "text"
    if k == {"bool"}:
        return "bool"
    if k == {"date"}:
        return "date"
    if k == {"json"}:
        return "json"
    if k <= {"num", "numstr"} and "num" in k:
        if EPOCH_RE.search(low) and values and all(is_epoch(v) for v in values):
            return "date"
        if R_RE.search(low):
            return "R"
        if USD_RE.search(low):
            return "usd"
        return "number"
    return "text"


def apply_opts(rows, opts):
    """The hand hints of a card: expand = {"m26": ["n", "pf"]} names the items of a list column; decode = {"verdict": ["adopted", "rejected"]} turns an index into its word."""
    expand, decode = (opts or {}).get("expand") or {}, (opts or {}).get("decode") or {}
    if not expand and not decode:
        return rows
    out = []
    for r in rows:
        n = {}
        for k, v in r.items():
            if k in expand and isinstance(v, list):
                for i, name in enumerate(expand[k]):
                    n[f"{k}.{name}"] = v[i] if i < len(v) else None
            elif k in decode and isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(decode[k]):
                n[k] = decode[k][v]
            else:
                n[k] = v
        out.append(n)
    return out


def to_rows(node, kind, cols=None):
    """Any table-like node as a list of plain dict rows."""
    if kind == "rows":
        return [x if isinstance(x, dict) else {"value": x} for x in node]
    if kind == "matrix":
        out = []
        for x in node:
            if isinstance(x, list):
                out.append({(cols[i] if cols and i < len(cols) else f"c{i + 1}"): v for i, v in enumerate(x)})
            else:
                out.append({"value": x})
        return out
    if kind == "map":
        out = []
        for k, v in node.items():
            row = {"key": k}
            if isinstance(v, dict):
                row.update({kk: vv for kk, vv in v.items() if kk != "key"})
            else:
                row["value"] = v
            out.append(row)
        return out
    if kind == "values":
        return [{"value": x} for x in node]
    if kind == "kv":
        return [{"key": k, "value": v} for k, v in node.items()] if isinstance(node, dict) else [{"key": "value", "value": node}]
    return []


def _share(seq, pred, n=200):
    head = seq[:n]
    return sum(1 for x in head if pred(x)) / len(head) if head else 0.0


def _header(parent, width):
    """A sibling list of column names for a list of lists (cols / columns / header / fields / keys)."""
    if isinstance(parent, dict):
        for k in ("cols", "columns", "header", "headers", "fields", "keys"):
            v = parent.get(k)
            if isinstance(v, list) and len(v) == width and all(isinstance(x, str) for x in v):
                return v
    return None


def find_tables(doc):
    """Every array (or map of records) in a JSON document that can be shown as a table: [{path, kind, rows}], biggest first. Paths are keys joined by '/'."""
    out = []

    def visit(node, path, depth, parent):
        if isinstance(node, list):
            if not node:
                return
            if _share(node, lambda x: isinstance(x, dict)) >= 0.6:
                out.append({"path": path, "kind": "rows", "rows": len(node)})
            elif _share(node, lambda x: isinstance(x, list)) >= 0.6:
                out.append({"path": path, "kind": "matrix", "rows": len(node)})
            elif depth == 0 and len(node) >= 2:
                out.append({"path": path, "kind": "values", "rows": len(node)})
            return
        if not isinstance(node, dict):
            return
        vals = list(node.values())
        if depth > 0 and len(vals) >= 3 and _share(vals, lambda x: isinstance(x, dict) and len(x) > 0) >= 0.8:
            keysets = [frozenset(v) for v in vals[:200] if isinstance(v, dict)]
            common = frozenset.intersection(*keysets) if keysets else frozenset()
            if common and len(common) * 2 >= max(len(s) for s in keysets):      # the records share their fields: it is a map of rows, not a settings tree
                out.append({"path": path, "kind": "map", "rows": len(vals)})
        if depth >= MAX_DEPTH:
            return
        for i, (k, v) in enumerate(node.items()):
            if i >= MAX_KEYS:
                break
            if "/" in k or not isinstance(v, (dict, list)):
                continue
            visit(v, (path + "/" + k) if path else k, depth + 1, node)

    visit(doc, "", 0, None)
    out.sort(key=lambda c: (-c["rows"], c["path"].count("/"), c["path"]))
    if not out:
        out.append({"path": "", "kind": "kv", "rows": len(doc) if isinstance(doc, dict) else 1})
    return out


def resolve(doc, path):
    """(node, parent) at a '/' path, or (None, None)."""
    node, parent = doc, None
    for k in [p for p in path.split("/") if p != ""]:
        if isinstance(node, dict) and k in node:
            parent, node = node, node[k]
        else:
            return None, None
    return node, parent


def table_at(doc, path, kind=None, opts=None):
    """The rows of the table at `path` (kind worked out when not given). opts = the card's hand hints (header / expand / decode)."""
    node, parent = resolve(doc, path)
    if node is None:
        return [], "kv"
    if kind is None:
        kind = next((c["kind"] for c in find_tables(doc) if c["path"] == path), None)
        if kind is None:
            kind = "rows" if isinstance(node, list) else "kv"
    cols = None
    if kind == "matrix" and node and isinstance(node[0], list):
        cols = (opts or {}).get("header") or _header(parent, len(node[0]))
    return apply_opts(to_rows(node, kind, cols), opts), kind


def flatten(row):
    """One level: {"a": {"b": 1}} -> {"a.b": 1} for small plain objects; lists and deeper objects stay as they are (shown as JSON)."""
    out = {}
    for k, v in row.items():
        if isinstance(v, dict) and 0 < len(v) <= FLAT_KEYS:
            for kk, vv in v.items():
                out[f"{k}.{kk}"] = vv
        else:
            out[k] = v
    return out


def sample_idx(n, cap=SAMPLE_N):
    if n <= cap:
        return list(range(n))
    step = n / cap
    return sorted({min(n - 1, int(i * step)) for i in range(cap)})


def infer_columns(rows):
    """[{k, t, mixed?}] in first-seen order, from an even sample of the rows."""
    order, kinds, nums = [], {}, {}
    for i in sample_idx(len(rows)):
        r = rows[i]
        if not isinstance(r, dict):
            continue
        for k, v in flatten(r).items():
            if k not in kinds:
                if len(order) >= MAX_COLS:
                    continue
                order.append(k)
                kinds[k] = set()
                nums[k] = []
            kd = kind_of(v)
            kinds[k].add(kd)
            if kd == "num":
                nums[k].append(v)
    cols = []
    for k in order:
        ks = kinds[k] - {"null"}
        c = {"k": k, "t": col_type(k, ks, nums[k])}
        if c["t"] == "text" and len(ks) > 1:
            c["mixed"] = True
        cols.append(c)
    return cols


def short(v, n=80):
    """A sample value small enough for the catalogue."""
    if isinstance(v, str):
        return v if len(v) <= n else v[:n - 1] + "\u2026"
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        return s if len(s) <= n else s[:n - 1] + "\u2026"
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def find_fresh(doc):
    """The field that says how old a file is: {field, value} (an ISO date / time or an epoch), looked for at the top and one level down."""
    def ok(v):
        return (isinstance(v, str) and DATE_RE.match(v.strip())) or is_epoch(v)
    if not isinstance(doc, dict):
        return None
    for k in FRESH_KEYS:
        if k in doc and ok(doc[k]):
            return {"field": k, "value": doc[k]}
    for outer in ("meta", "_meta", "header", "info", "status", "summary"):
        sub = doc.get(outer)
        if isinstance(sub, dict):
            for k in FRESH_KEYS:
                if k in sub and ok(sub[k]):
                    return {"field": f"{outer}/{k}", "value": sub[k]}
    return None


# ------------------------------------------------------------------------------------------------ the hand-written map
# app -> district (everything not listed: by its group in jarvis/apps.js: trading -> Market, money -> Money, life -> Life)
APP_DISTRICT = {
    "archive": "Research", "athena": "Research", "prometheus": "Research", "tree": "Research", "datacity": "Research", "hephaestus": "Research", "fates": "Research",
    "observatory": "Research", "labyrinth": "Research", "nemesis": "Research", "chronos": "Research", "moirai": "Research", "kratos": "Research", "writeups": "Research",
    "bridge": "Command", "ergasterion": "Command", "cronos": "Command", "pantheon": "Command", "jarvis": "Command", "site": "Command", "helios": "Command", "compass": "Command",
    "hermes": "Command", "arena": "Command", "argo": "Command", "kronos": "Command", "gallery": "Command", "cities": "Command",
    "money": "Money", "kalshicity": "Money", "sibyl": "Money", "plutus": "Money", "ledger": "Money", "mint": "Money", "mintcity": "Money", "mercury": "Money", "chrysos": "Money",
    "oikos": "Money", "arbiter": "Money", "pnyx": "Money", "ares": "Money", "stoa": "Money", "aegis": "Money", "nike": "Money", "forum": "Money",
    "mind": "Life", "lyceum": "Life", "planner": "Life", "journal": "Life", "hestia": "Life", "demeter": "Life", "apollo": "Life", "hera": "Life", "dionysus": "Life", "clio": "Life",
    "harmonia": "Life", "epilogue": "Life", "kairos": "Life",
    "odeon": "Market", "oracle": "Market", "pythia": "Market", "pheme": "Market", "delphi": "Market", "data": "Market",
}
GROUP_DISTRICT = {"trading": "Market", "money": "Money", "life": "Life", "more": "Command"}

# file (relative to the site) -> the tables in it. Each: path ('' = let the builder pick the biggest array), name, plain-words description. The first is the main one.
HAND = {
    "odeon/trades.json": [("", "Trades (Odeon)", "Every backtest trade of the live strategy, one row per trade: day, side, entry, stop, result in R and in $.")],
    "archive/index.json": [("runs", "Research runs (adopted and open)", "Every experiment that was kept or is still open: family, verdict, and for 2026 and 2021-25: trades, PF, net $, $ a month."),
                           ("writeups", "Research write-ups", "The plain-language write-up of each study: title, date, verdict."),
                           ("rejected", "Tested and rejected", "Ideas that were tried and dropped, with the reason, so they are not redone."),
                           ("datasets", "Research datasets (index)", "The futures and volatility files the research runs on: span and rows.")],
    "archive/runs-0.json": [("", "Rejected runs, part 1", "The rejected experiment runs (first quarter of the list).")],
    "archive/runs-1.json": [("", "Rejected runs, part 2", "The rejected experiment runs (second quarter).")],
    "archive/runs-2.json": [("", "Rejected runs, part 3", "The rejected experiment runs (third quarter).")],
    "archive/runs-3.json": [("", "Rejected runs, part 4", "The rejected experiment runs (last quarter).")],
    "datacity/city.json": [("buildings", "Data City buildings", "The strategy combinations that earned a building: what the rule is, its edge, win rate and trades, in 2026 and before."),
                           ("skyline/rows", "Data City skyline (every combo)", "Every combination that was tested, packed as numbers: 37,000 rows. The biggest table on the site.")],
    "fates/fates.json": [("", "Fates: eval paths", "Simulated eval outcomes: how often an eval passes or fails, and how fast.")],
    "tree/tree.json": [("", "Daphne strategy tree", "The strategy search tree: each node is a rule tried, with its score.")],
    "cities/cities.json": [("", "Cities", "The districts and buildings of the OLYMPUS cities.")],
    "bridge/jobs.json": [("", "Bridge jobs", "The work items sent between the phone and the PC, with their status.")],
    "prometheus/forge.json": [("", "Prometheus forge", "The self-research forge: ideas generated and how each scored.")],
    "athena/library.json": [("", "Athena library", "The trading library: concepts and lessons, one row each.")],
    "athena/drills.json": [("", "Athena drills", "Practice questions for the trading concepts.")],
    "pantheon/states.json": [("", "Pantheon states", "The state of every bot and agent over time.")],
    "pantheon/pantheon.json": [("", "Pantheon", "The roster of bots and agents and what each is doing.")],
    "ergasterion/queue.json": [("queue/tasks", "Workshop task queue", "The open and done tasks of the build queue, by priority."),
                               ("learnings", "Workshop lessons", "What the workers learned, dated, with the file each lesson came from.")],
    "kalshicity/edges.json": [("edges", "Kalshi edges", "Possible Kalshi edges that were tested out of sample, with fees in. Paper only."),
                              ("book/days", "Kalshi paper book by day", "The paper book's result for each day, in $.", {"header": ["day", "pnl"]})],
    "kalshicity/hypotheses.json": [("", "Kalshi hypotheses", "The Kalshi ideas waiting for a test, and their status.")],
    "kalshicity/suggestions.json": [("", "Kalshi suggestions", "Paper suggestions from the Kalshi study. Never an order.")],
    "kalshicity/ledger.json": [("", "Kalshi paper ledger", "The paper trades of the Kalshi study with their results in $.")],
    "kalshicity/learned.json": [("", "Kalshi lessons", "What the Kalshi study learned, dated.")],
    "kalshicity/learning_log.json": [("", "Kalshi learning log", "The dated log of the Kalshi study's learning steps.")],
    "arena/events.json": [("", "Arena events", "Verifiable trading events used for the Olympian ranks.")],
    "arena/rules.json": [("", "Arena rules", "The rules that turn events into rank points.")],
    "pythia/events.json": [("", "Economic calendar", "Dated market events (CPI, FOMC, jobs ...) with their importance.")],
    "pheme/stats.json": [("", "News reaction stats", "How NQ moved after each kind of news release.")],
    "plutus/plans.json": [("", "Prop-firm plans", "Prop-firm account plans with their real prices and rules.")],
    "plutus/roadmap.json": [("", "Money roadmap", "The steps of the money plan, in order.")],
    "hephaestus/data.json": [("", "Hephaestus builds", "What the tool forge built and tested.")],
    "ledger/rules.json": [("", "Ledger rules", "The categories and rules the Ledger uses to sort money entries.")],
    "ares/rules.json": [("", "Risk rules", "The risk rules of each prop firm.")],
    "hermes/wrapped.json": [("", "Wrapped", "The year-in-review numbers.")],
    "oracle/prophecy.json": [("", "Oracle prophecy", "The market radar's reading for the day.")],
    "oracle/demo_day.json": [("", "Oracle demo day", "A recorded example day for the market radar (demo).")],
    "bridge/status.json": [("", "Bridge status", "Whether the PC and the phone are talking, and when they last did.")],
    "mind/starter/starter_pack.json": [("", "Obsidian starter pack", "The notes of the starter vault, one row per note.")],
    # only there after the site build
    "home.json": [("", "Home (live summary)", "The live summary every app reads: accounts, today's plan, the bot's state. Written by the site build.")],
    "data.json": [("", "Dashboard data", "The full dashboard data: results, trades, eval scores. Written by the site build.")],
    "intel.json": [("", "Trade intel", "Trade intelligence for the day. Written by the site build.")],
    "kalshi.json": [("", "Kalshi feed", "The public Kalshi market feed the Kalshi apps read. Written by the site build.")],
    "alerts.json": [("", "Alerts", "The alert list shown on the phone. Written by the site build.")],
    "money/index.json": [("", "Money machines (index)", "The five paper money machines and their headline estimate. Sample data until the PC runs them.")],
    "money/chrysos.json": [("items", "Chrysos deals", "Dated deals and discounts found by Chrysos, with $ and an end date. Paper only.")],
    "money/mercury.json": [("items", "Mercury items", "Mercury's paper money ideas with $ and a risk level.")],
    "money/sibyl.json": [("items", "Sibyl items", "Sibyl's paper forecasts with a score. Never an order.")],
    "money/sibyl_forward.json": [("", "Sibyl forward test", "Sibyl's forward (out-of-sample) paper results.")],
    "money/oikos.json": [("items", "Oikos leaks", "Where the household money leaks, worst first.")],
    "money/arbiter.json": [("items", "Arbiter items", "Arbiter's paper comparisons with $ and risk.")],
    "cronos/status.json": [("", "Cronos status", "The scheduled jobs and when each last ran.")],
    "datacity/discoveries.json": [("", "Data City discoveries", "New findings from the combo search.")],
    "kalshicity/forward.json": [("", "Kalshi forward test", "The Kalshi paper results on unseen data.")],
    "kalshicity/scan.json": [("", "Kalshi scan", "The newest Kalshi market scan.")],
    "writeups/index.json": [("", "Write-ups index", "The list of research write-ups published on the site.")],
}
# files that only exist after the site build (other apps read them); the money ones follow the money data contract, so their columns are known
BUILD_ONLY = ("home.json", "data.json", "intel.json", "kalshi.json", "alerts.json", "money/index.json", "money/chrysos.json", "money/mercury.json", "money/sibyl.json",
              "money/sibyl_forward.json", "money/oikos.json", "money/arbiter.json", "cronos/status.json", "datacity/discoveries.json", "kalshicity/forward.json",
              "kalshicity/scan.json", "writeups/index.json")
MONEY_COLS = [{"k": "title", "t": "text"}, {"k": "detail", "t": "text"}, {"k": "usd", "t": "usd"}, {"k": "score", "t": "number"}, {"k": "risk", "t": "text"}, {"k": "expires", "t": "date"}]
SKIP_DIRS = ("icon_options", "pinakes", "fx", "node_modules", "three-addons", "icons", "brand")
SKIP_NAMES = ("jarvis.json", "push_relay.json", "push_key.json", "package.json", "package-lock.json", "info.json", "plugins.json", "deliveries.json")
RESEARCH_WORDS = {"NQ": "NQ futures", "ES": "ES futures", "VIX": "VIX", "VXN": "VXN", "GEX": "gamma exposure", "CBOE": "CBOE volatility indexes", "tv": "TradingView MNQ export", "events": "news events"}


def app_groups(web=WEB):
    """app id -> group, read from jarvis/apps.js (never written)."""
    try:
        with open(os.path.join(web, "jarvis", "apps.js"), encoding="utf-8") as fh:
            return dict(re.findall(r"app\('([a-z0-9_]+)',\s*'[^']*',\s*'([a-z]+)'", fh.read()))
    except OSError:
        return {}


def district_of(app, groups):
    return APP_DISTRICT.get(app) or GROUP_DISTRICT.get(groups.get(app, ""), "Command")


def label_of(rel, doc):
    """demo | sample | live: what the file itself says it is."""
    base = os.path.basename(rel).lower()
    if "fixture" in base or base.startswith("demo") or "_demo" in base or "sample" in base:
        return "demo"
    if isinstance(doc, dict):
        if doc.get("demo") is True:
            return "demo"
        if str(doc.get("status", "")).lower() == "sample" or doc.get("sample") is True:
            return "sample"
    return "live"


def nice(s):
    return re.sub(r"[_\-]+", " ", s).strip().capitalize()


def auto_name(rel, path, app):
    base = os.path.basename(rel)[:-5]
    tail = path.split("/")[-1] if path else base
    title = nice(app) if app not in ("site", "") else "Site"
    if "fixture" in base or base.startswith("demo"):
        return f"{title} demo data" + (f": {nice(tail)}" if path and tail != base else "")
    return f"{title}: {nice(tail)}" if nice(tail).lower() != title.lower() else title


def auto_desc(rel, path, cols, rows, kind, label):
    names = ", ".join(c["k"] for c in cols[:5])
    what = {"rows": "one row per record", "matrix": "a grid of values", "map": "one row per named record", "values": "a plain list", "kv": "the file's top-level fields, one per row"}[kind]
    where = f"the list \"{path}\" in {rel}" if path else rel
    lead = "Demo data (not real): " if label == "demo" else "Sample data: " if label == "sample" else ""
    return f"{lead}{where}: {what}. Fields: {names}{' ...' if len(cols) > 5 else ''}."[:240]


def slug(rel, path=""):
    s = rel[:-5] + ("~" + path if path else "")
    return re.sub(r"[^a-z0-9~]+", "-", s.lower()).strip("-")


def hand_opts(web):
    """Hints worked out from the files themselves: the Archive packs its runs as lists, and says what the items are in index.json (cols, metric_cols, verdicts)."""
    try:
        with open(os.path.join(web, "archive", "index.json"), encoding="utf-8") as fh:
            ix = json.load(fh)
        o = {"header": list(ix["cols"]), "expand": {"m26": list(ix["metric_cols"]), "mold": list(ix["metric_cols"])}, "decode": {"verdict": list(ix["verdicts"])}}
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {("archive/index.json", "runs"): o, **{(f"archive/runs-{i}.json", ""): o for i in range(8)}}


def card_for(rel, doc, path, kind, name, desc, groups, size, label, others, opts=None, first=True):
    rows, kind = table_at(doc, path, kind, opts)
    cols = infer_columns(rows)
    app = rel.split("/")[0] if "/" in rel else "site"
    keys = [c["k"] for c in cols[:8]]
    sample = [{k: short(flatten(r).get(k), 60) for k in keys} for r in rows[:2] if isinstance(r, dict)]
    card = {"id": slug(rel) if first else slug(rel, path), "name": name or auto_name(rel, path, app), "app": app, "district": district_of(app, groups), "url": "../" + rel, "path": path, "kind": kind,
            "desc": desc or auto_desc(rel, path, cols, len(rows), kind, label), "rows": len(rows), "bytes": size, "cols": cols, "sample": sample, "label": label, "source": "site"}
    fr = find_fresh(doc)
    if fr:
        card["fresh"] = fr
    if others:
        card["paths"] = others
    if opts:
        card["opts"] = opts
    return card


def site_cards(web=WEB, groups=None):
    groups = groups if groups is not None else app_groups(web)
    cards, skipped, hints = [], [], hand_opts(web)
    files = sorted(glob.glob(os.path.join(web, "**", "*.json"), recursive=True))
    for p in files:
        rel = os.path.relpath(p, web).replace(os.sep, "/")
        parts = rel.split("/")
        if any(d in SKIP_DIRS for d in parts[:-1]) or parts[-1] in SKIP_NAMES or parts[-1].endswith(".webmanifest") or parts[-1].startswith("."):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError, UnicodeDecodeError) as e:
            skipped.append({"file": rel, "why": f"not readable JSON ({type(e).__name__})"})
            continue
        size = os.path.getsize(p)
        found = find_tables(doc)
        label = label_of(rel, doc)
        others = [{"path": c["path"], "kind": c["kind"], "rows": c["rows"]} for c in found[:8]]
        hand = HAND.get(rel)
        if hand:
            for n, (path, name, desc, *more) in enumerate(hand):
                c = next((x for x in found if x["path"] == path), None) if path else found[0]
                if c is None:
                    if n:
                        continue
                    c, name, desc = found[0], None, None
                opts = (more[0] if more else None) or hints.get((rel, path))
                cards.append(card_for(rel, doc, c["path"], c["kind"], name, desc, groups, size, label, others if len(others) > 1 else None, opts, n == 0))
        else:
            c = found[0]
            cards.append(card_for(rel, doc, c["path"], c["kind"], None, None, groups, size, label, others if len(others) > 1 else None))
    return cards, skipped


def build_cards(web=WEB, groups=None, have=()):
    """The files that only exist after the site build and are not in this folder: described, not measured."""
    groups = groups if groups is not None else app_groups(web)
    out = []
    for rel in BUILD_ONLY:
        if rel in have or os.path.isfile(os.path.join(web, rel)):
            continue
        app = rel.split("/")[0] if "/" in rel else "site"
        for n, (path, name, desc, *_more) in enumerate(HAND.get(rel, [("", None, None)])):
            card = {"id": slug(rel) if n == 0 else slug(rel, path), "name": name or auto_name(rel, path, app), "app": app, "district": district_of(app, groups), "url": "../" + rel, "path": path, "kind": "rows" if path else "auto",
                    "desc": desc or f"{rel}: written by the site build.", "rows": None, "bytes": None, "cols": MONEY_COLS if rel.startswith("money/") and path == "items" else [], "sample": [],
                    "label": "build", "source": "build", "needs": "the site build (tools/build_web_dashboard.py); measured when you open it"}
            out.append(card)
    return out


def research_cards(data_dir=DATA):
    """The CSV datasets under data/: span and rows only. Not published, not downloadable."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import archive_build as AB
        sets = AB.datasets(data_dir)
    except Exception:
        sets = []
    out = []
    for d in sets:
        stem = d["name"][:-4]
        sym = stem.split("_")[0]
        what = RESEARCH_WORDS.get(sym, sym)
        out.append({"id": "research-" + re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-"), "name": f"{stem.replace('_', ' ')} ({what})", "app": "data", "district": "Research", "url": None, "path": "",
                    "kind": "csv", "desc": f"{d['source']}. {d['rows']:,} rows from {d['first']} to {d['last']}. Kept on the PC in {d['file']}; not published, so it cannot be opened or downloaded here.",
                    "rows": d["rows"], "bytes": None, "cols": [{"k": c, "t": "date" if c in ("time", "date") else "number"} for c in d["cols"]], "sample": [], "label": "research", "source": "research",
                    "span": {"first": d["first"], "last": d["last"]}, "file": d["file"]})
    return out


def build(web=WEB, data_dir=DATA):
    groups = app_groups(web)
    site, skipped = site_cards(web, groups)
    cards = site + build_cards(web, groups) + research_cards(data_dir)
    seen = {}
    for c in cards:                                           # ids must be unique (the share link uses them)
        n = seen.get(c["id"], 0)
        seen[c["id"]] = n + 1
        if n:
            c["id"] = f"{c['id']}-{n + 1}"
    order = {d: i for i, d in enumerate(DISTRICTS)}
    cards.sort(key=lambda c: (order.get(c["district"], 9), {"site": 0, "build": 1, "research": 2}[c["source"]], -(c["rows"] or 0), c["id"]))
    counts = {d: {"tables": 0, "rows": 0} for d in DISTRICTS}
    for c in cards:
        counts[c["district"]]["tables"] += 1
        counts[c["district"]]["rows"] += c["rows"] or 0
    newest = max((str(c["fresh"]["value"])[:10] for c in cards if isinstance((c.get("fresh") or {}).get("value"), str)), default="")
    return {"v": 1, "built": newest, "districts": list(DISTRICTS), "counts": counts,
            "totals": {"tables": len(cards), "rows": sum(c["rows"] or 0 for c in cards), "site_tables": sum(1 for c in cards if c["source"] == "site"),
                       "site_rows": sum(c["rows"] or 0 for c in cards if c["source"] == "site"), "build_tables": sum(1 for c in cards if c["source"] == "build"),
                       "research_tables": sum(1 for c in cards if c["source"] == "research"), "research_rows": sum(c["rows"] or 0 for c in cards if c["source"] == "research")},
            "note": "A card per table. The rows are never copied here: the page loads each table from its own URL when you open it.",
            "skipped": skipped, "tables": cards}


def dumps(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n"


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    res = []

    def t(name, ok, info=""):
        res.append(bool(ok))
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))

    t("value kinds: null, bool, number, numeric text, date, text, json; NaN and '' count as empty",
      [kind_of(v) for v in (None, "", " ", True, 3, 2.5, float("nan"), "$1,250.50", "-12", "45%", "2026-11-11", "2026-11-11T09:30:00Z", "héllo", "007x", {"a": 1}, [1])]
      == ["null", "null", "null", "bool", "num", "num", "null", "numstr", "numstr", "numstr", "date", "date", "str", "str", "json", "json"])
    rows = [{"day": "2026-01-05", "pnl": 120.5, "r": 1.2, "win": True, "note": "ok", "qty": 2, "t": 1793394000, "tags": ["a"], "mix": 1, "meta": {"a": 1, "b": "x"}},
            {"day": "2026-01-06", "pnl": None, "r": -1, "win": False, "note": None, "qty": "3", "t": 1793480400, "tags": [], "mix": "two", "meta": {"a": 2}},
            {"day": None, "pnl": -60, "r": 0, "win": None, "note": "日本語 ✓", "qty": 4, "t": None, "mix": None, "extra": ""}]
    cols = {c["k"]: c for c in infer_columns(rows)}
    t("column types: date, $, R, yes/no, text, a number with a numeric string in it, an epoch as a date, json, mixed -> text, one-level flatten, an all-empty column is text",
      [cols[k]["t"] for k in ("day", "pnl", "r", "win", "note", "qty", "t", "tags", "mix", "meta.a", "meta.b", "extra")]
      == ["date", "usd", "R", "bool", "text", "number", "date", "json", "text", "number", "text", "text"] and cols["mix"].get("mixed") is True, {k: c["t"] for k, c in cols.items()})
    t("$ and R are read from the column name only when the values are numbers", col_type("net_usd", {"num"}) == "usd" and col_type("avg_r", {"num"}) == "R" and col_type("rows", {"num"}) == "number" and col_type("r", {"num"}) == "R"
      and col_type("pnl", {"str"}) == "text" and col_type("price", {"num"}) == "number" and col_type("r_mult", {"num"}) == "R" and col_type("fees", {"num", "numstr"}) == "usd")
    doc = {"asof": "2026-11-10T12:00:00Z", "trades": [{"a": 1}] * 5, "small": [{"b": 1}], "grid": {"cols": ["x", "y"], "data": [[1, 2], [3, 4], [5, 6]]},
           "by_id": {"a": {"n": 1, "w": 2}, "b": {"n": 2, "w": 3}, "c": {"n": 3, "w": 1}}, "settings": {"x": {"a": 1}, "y": {"b": 2}, "z": {"c": 3}}, "notes": ["p", "q"], "deep": {"l2": {"l3": {"l4": {"l5": [{"z": 1}]}}}}}
    f = find_tables(doc)
    t("find_tables: the biggest array first, a matrix, a map of records (shared fields), not a settings tree, not a nested plain list, nothing deeper than 4 levels",
      [(c["path"], c["kind"], c["rows"]) for c in f] == [("trades", "rows", 5), ("by_id", "map", 3), ("grid/data", "matrix", 3), ("small", "rows", 1)], f)
    m, _ = table_at(doc, "grid/data")
    mp, _ = table_at(doc, "by_id")
    t("a matrix takes its column names from the 'cols' next to it; a map gets a 'key' column", m[0] == {"x": 1, "y": 2} and mp[1] == {"key": "b", "n": 2, "w": 3}, (m[:1], mp[:2]))
    ex = apply_opts(to_rows([["a", 1, [5, 2.5]], ["b", 0, [7]]], "matrix", ["id", "verdict", "m"]), {"expand": {"m": ["n", "pf"]}, "decode": {"verdict": ["adopted", "rejected"]}})
    t("hand hints: a packed list column is spread into named columns (short lists give empty cells) and an index becomes its word", ex == [{"id": "a", "verdict": "rejected", "m.n": 5, "m.pf": 2.5}, {"id": "b", "verdict": "adopted", "m.n": 7, "m.pf": None}], ex)
    t("a file with no table at all becomes a key / value table (never dropped)", find_tables({"a": 1, "b": "x"}) == [{"path": "", "kind": "kv", "rows": 2}] and table_at({"a": 1, "b": "x"}, "")[0][1] == {"key": "b", "value": "x"})
    t("a root list of records and a root list of plain values", find_tables([{"a": 1}, {"a": 2}])[0] == {"path": "", "kind": "rows", "rows": 2} and find_tables([1, 2, 3])[0]["kind"] == "values")
    t("freshness: an ISO stamp or an epoch at the top or under meta; none when there is none", find_fresh(doc) == {"field": "asof", "value": "2026-11-10T12:00:00Z"}
      and find_fresh({"meta": {"built": 1793394000}}) == {"field": "meta/built", "value": 1793394000} and find_fresh({"t": 5}) is None and find_fresh([1]) is None)
    t("labels: a fixture or demo file is 'demo', status sample is 'sample', the rest 'live'", [label_of("x/fixture.json", {}), label_of("x/demo_day.json", {}), label_of("x/a.json", {"demo": True}),
                                                                                           label_of("money/x.json", {"status": "sample"}), label_of("x/trades.json", {"status": "ok"})] == ["demo", "demo", "demo", "sample", "live"])
    big = [{"i": i, "v": i * 1.5} for i in range(10000)]
    t("10,000 rows: sampled evenly (500 rows looked at), still typed right", len(sample_idx(10000)) == 500 and sample_idx(10000)[-1] > 9900 and [c["t"] for c in infer_columns(big)] == ["number", "number"])
    t("sample values are kept short and unicode survives", short("x" * 200).endswith("\u2026") and len(short("x" * 200)) == 80 and short({"k": "日本"}) == '{"k":"日本"}' and short(float("inf")) is None)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "odeon"))
        os.makedirs(os.path.join(tmp, "zeta"))
        os.makedirs(os.path.join(tmp, "jarvis"))
        os.makedirs(os.path.join(tmp, "icon_options", "a"))
        json.dump({"asof": "2026-11-01", "trades": [{"day": "2026-01-05", "pnl": 10.0, "r": 1.0}, {"day": "2026-01-06", "pnl": -5.0, "r": -0.5}]}, open(os.path.join(tmp, "odeon", "trades.json"), "w"))
        json.dump({"demo": True, "note": "not real", "items": [{"title": "a", "usd": 5}], "more": [{"x": 1}, {"x": 2}]}, open(os.path.join(tmp, "zeta", "fixture.json"), "w"))
        json.dump({"v": 1}, open(os.path.join(tmp, "zeta", "jarvis.json"), "w"))
        json.dump({"x": 1}, open(os.path.join(tmp, "icon_options", "a", "info.json"), "w"))
        open(os.path.join(tmp, "zeta", "broken.json"), "w").write("{nope")
        open(os.path.join(tmp, "jarvis", "apps.js"), "w").write("app('zeta', 'Zeta', 'life', '#fff', 'x'),")
        os.makedirs(os.path.join(tmp, "data"))
        open(os.path.join(tmp, "data", "NQ_5m.csv"), "w").write("time,open,high,low,close,volume\n1700000000,1,2,0,1,5\n1700000300,1,2,0,1,5\n")
        doc = build(tmp, os.path.join(tmp, "data"))
        ids = [c["id"] for c in doc["tables"]]
        by = {c["id"]: c for c in doc["tables"]}
        t("build: the hand-named trades table, a demo fixture (biggest array, with a path picker), the build-only files, a research dataset; jarvis.json, icons and broken JSON are left out (broken is reported)",
          "odeon-trades" in ids and by["odeon-trades"]["name"] == "Trades (Odeon)" and by["odeon-trades"]["district"] == "Market" and by["odeon-trades"]["path"] == "trades" and by["odeon-trades"]["rows"] == 2
          and by["zeta-fixture"]["label"] == "demo" and by["zeta-fixture"]["path"] == "more" and len(by["zeta-fixture"]["paths"]) == 2 and by["zeta-fixture"]["id"] == "zeta-fixture" and by["zeta-fixture"]["district"] == "Life"
          and "home" in ids and by["home"]["source"] == "build" and by["home"]["rows"] is None and by["money-chrysos"]["cols"][2] == {"k": "usd", "t": "usd"}
          and by["research-nq-5m"]["rows"] == 2 and by["research-nq-5m"]["url"] is None and by["research-nq-5m"]["span"] == {"first": "2023-11-14", "last": "2023-11-14"}
          and not any("jarvis" in i or "icon" in i or "broken" in i for i in ids) and doc["skipped"] == [{"file": "zeta/broken.json", "why": "not readable JSON (JSONDecodeError)"}], (ids, doc["skipped"]))
        t("build: no rows are copied (3 short sample rows at most), counts add up, ids are unique, the file is small",
          all(len(c["sample"]) <= 3 for c in doc["tables"]) and doc["totals"]["tables"] == len(ids) == len(set(ids)) and sum(v["tables"] for v in doc["counts"].values()) == len(ids)
          and doc["totals"]["rows"] == sum(c["rows"] or 0 for c in doc["tables"]) and by["odeon-trades"]["fresh"] == {"field": "asof", "value": "2026-11-01"} and len(dumps(doc)) < 20000, doc["totals"])
        out = os.path.join(tmp, "catalog.json")
        open(out, "w", encoding="utf-8", newline="\n").write(dumps(doc))
        t("--check passes on what was written and fails after an edit", check(out, doc) and not check(out, {**doc, "v": 2}))
        # once the site is built, the build-only files are measured like any other
        os.makedirs(os.path.join(tmp, "money"))
        json.dump({"v": 1, "id": "chrysos", "asof": "2026-11-10T08:00:00Z", "status": "sample", "items": [{"title": "Deal", "detail": "d", "usd": 12.5, "score": 60, "risk": "low", "expires": "2026-11-14"}]},
                  open(os.path.join(tmp, "money", "chrysos.json"), "w"))
        by2 = {c["id"]: c for c in build(tmp, os.path.join(tmp, "data"))["tables"]}
        t("pointed at a built site, a build-only file is measured (rows, columns, 'sample' label, freshness) and listed once",
          by2["money-chrysos"]["rows"] == 1 and by2["money-chrysos"]["label"] == "sample" and by2["money-chrysos"]["source"] == "site"
          and [c["t"] for c in by2["money-chrysos"]["cols"]] == ["text", "text", "usd", "number", "text", "date"] and by2["money-chrysos"]["fresh"]["field"] == "asof"
          and sum(1 for i in by2 if i.startswith("money-chrysos")) == 1, by2.get("money-chrysos"))
    bad = res.count(False)
    print(f"\n{len(res) - bad}/{len(res)} passed")
    return 1 if bad else 0


def check(path, doc):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read() == dumps(doc)
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--web", default=WEB, help="the site folder to read (default: tools/web_public; point it at the built site to measure home.json, money/*.json ...)")
    ap.add_argument("--data", default=DATA, help="the research data folder (default: data/)")
    ap.add_argument("--out", default=None, help="where to write catalog.json (default: <web>/pinakes/catalog.json)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = a.out or os.path.join(a.web, "pinakes", "catalog.json")
    doc = build(a.web, a.data)
    if a.check:
        ok = check(out, doc)
        print("pinakes: catalog.json is up to date" if ok else "pinakes: catalog.json is STALE (run python tools/pinakes_build.py)")
        return 0 if ok else 1
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(doc))
    t = doc["totals"]
    print(f"pinakes: {t['tables']} tables, {t['rows']:,} rows ({t['site_tables']} on the site with {t['site_rows']:,} rows, {t['build_tables']} written by the site build, "
          f"{t['research_tables']} research datasets with {t['research_rows']:,} rows) -> {os.path.relpath(out, ROOT)} ({os.path.getsize(out):,} bytes)")
    for s in doc["skipped"]:
        print(f"  skipped {s['file']}: {s['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
