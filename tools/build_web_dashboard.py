"""Build the PC-off web dashboard (static site) published to the public repo demetrades2000-coder/nq-dashboard (GitHub Pages).

The site is one page (tools/web_public/index.html) that reads everything from data.json; nothing runs on a server.
data.json holds:
  accounts  the Accounts page (engine/accounts.build_accounts): per account (the MFFU eval on the PC bot from its heartbeat,
            then "Paper (cloud)") the header, eval numbers, P&L today / week / since start, position, today's orders, closed
            trades, P&L per day and stats
  live      the cloud monitor's state (model state, eval tracker, cold-streak filter, paper ledger, recent bars, pools,
            `pc`: the always-on PC bot's heartbeat {present, t, age_s, silent, running, adapter, position, model_state, host, reason},
            `notices`: the last 80 phone notifications (fills, outcomes, PC silent, eval timing) for the app's Activity feed, and
            `push`: the public notification status {configured, vapid_public, devices, device_ids, sent_this_run, gone, ...})
  exec      execution quality of the live eval (engine/fill_audit.heartbeat_block from the PC heartbeat): slippage $ per trade /
            month against the backtest on the same bars, missed trades (why, backtest $) and extra trades; null before the
            PC's first audit
  results   the live-settings 5-year replay (periods, months, daily P&L, stop buckets, eval odds, lessons)
  trades    every replay trade with its report (why it entered / plan / result / lessons); 2026 with full detail
  replays   5m session bars for each replay trade day (tools/export_replays.py); LIT trade charts (bars + every marker of
            each trade) go to replays/<id>.json, loaded lazily by the trade sheet (tools/web_public/tradechart.js); each trade
            row and session names its chart id ("chart")
  variants  every tested variant (research/lab/variant_results.json)
  study     trades under review (research/study), charts copied to study/
  cold      the cold-streak filter config, state and its last-15 window
  sizing / strategy   the locked live settings (live_model.json: label, lock date, params, cold-streak filter)
  lab       the research run library index (research/runs, tools/runlib.py): one compact row per backtest run; every run
            file (all its trades, days, months, years) is copied to runs/<id>.json and fetched by the run page on demand
  docs      research write-ups (research/writeups/*.md, front matter + markdown) and an archive of the older result
            reports (research/*.md, research/lab/*.md); the text goes to writeups/<slug>.md, fetched by the reader
  hub       the Home / Strategy / Money pages (tools/web_public/hub.js): the tested upgrade combo (adopt_combo.json) with its
            live switches, the funded three-account plan (funded_firms.json), the research scoreboard (latest LIT write-ups,
            one line + verdict each), the changelog (commit titles of main) and the PC's auto-update / auto-resume line; the
            research files and git history are not in the cloud checkout, so tools/web_hub_snapshot.json carries them there
  props     prop-firm research (research/props/*.json when another study writes it: firms.json -> props.firms, other files
            by name: payouts, business, market ...) for the Prop Firms / Market pages; None until the files exist (also
            carried by the snapshot, since research/props is not in the cloud checkout)
home.json is the small first-paint file of the Home screen (live state without the long bar lists, accounts without their
trade lists, exec, hub, eval odds); data.json is loaded right after it.
Only results go public: no code (code blocks are dropped from every document), no secrets (a document that looks like it
holds one is skipped), no STRATEGY.md text.

  python tools/build_web_dashboard.py --state dash/state.json --chart dash/chart.png --out site
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import news_hub  # noqa: E402
from engine import lab_scope  # noqa: E402
WEB = os.path.join(ROOT, "tools", "web_public")
LAB = os.path.join(ROOT, "research", "lab")
STUDY = os.path.join(ROOT, "research", "study")
RUNS = os.path.join(ROOT, "research", "runs")
WRITEUPS = os.path.join(ROOT, "research", "writeups")
RESEARCH = os.path.join(ROOT, "research")
LIT_DOCS = os.path.join(ROOT, "research", "lit")                      # LIT research notes (masters.md, entry.md, ...): LIT write-ups
ARCHIVE = os.path.join(ROOT, *lab_scope.ARCHIVE_DIR.split("/"))       # the previous strategy (Liquidity Engine, Oct 17), archived
ICONS = os.path.join(ROOT, "web", "icons")

FULL = ("day", "entry_t", "exit_t", "side", "entry", "stop", "target", "exit_price", "exit", "trigger", "grade", "regime",
        "risk_pts", "qty", "risk_usd", "r", "pnl", "half", "pools", "sweep_ext", "zone", "target_label", "conf_tags", "mfe",
        "bars_held", "checklist", "smc", "report", "cisd_level", "entry_kind", "plan_rr")     # the last 3: LIT replay overlays
SLIM_DROP = ("conf_tags", "checklist", "smc", "zone", "pools")


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _charts(out, replays):
    """LIT trade chart records -> <out>/replays/<id>.json (one small file per trade, loaded when a chart is opened)."""
    recs = replays.pop("charts", None) or {}
    replays.pop("charts_source", None)
    d = os.path.join(out, "replays")
    if os.path.isdir(d):
        shutil.rmtree(d)
    if not recs:
        return {}
    os.makedirs(d, exist_ok=True)
    for k, r in recs.items():
        if SAFE_ID.match(k):
            with open(os.path.join(d, k + ".json"), "w", encoding="utf-8") as fh:
                json.dump(r, fh, separators=(",", ":"))
    return {(r["day"], int(r["entry"]["t"])): k for k, r in recs.items() if SAFE_ID.match(k)}


def _trades(bt, charts=None):
    out = []
    for t in reversed(bt.get("trades") or []):
        row = {k: t.get(k) for k in FULL}
        rep = dict(row.get("report") or {})
        rep.pop("strategy", None)
        row["report"] = rep
        if not str(row["day"]).startswith("2026"):
            for k in SLIM_DROP:
                row.pop(k, None)
        for k in ("mfe", "r", "risk_usd", "pnl"):
            if isinstance(row.get(k), float):
                row[k] = round(row[k], 3)
        ch = (charts or {}).get((t.get("day"), int(t.get("entry_t") or 0)))
        if ch:
            row["chart"] = ch
        out.append(row)
    return out


def _study(out):
    items = []
    if not os.path.isdir(STUDY):
        return items
    os.makedirs(os.path.join(out, "study"), exist_ok=True)
    stems = sorted({os.path.splitext(n)[0] for n in os.listdir(STUDY) if n.endswith((".json", ".png"))}, reverse=True)
    for stem in stems:
        png, js = os.path.join(STUDY, stem + ".png"), os.path.join(STUDY, stem + ".json")
        it = {"id": stem, "date": stem[:10], "title": stem[11:].replace("_", " "), "image": None, "trades": []}
        if os.path.exists(png):
            shutil.copy(png, os.path.join(out, "study", stem + ".png"))
            it["image"] = "study/" + stem + ".png"
        d = _load(js, {}) or {}
        it["trades"] = [{k: t.get(k) for k in ("day", "dir", "r", "pnl", "risk_pts", "qty", "exit", "trigger", "grade", "regime")}
                        for t in d.get("trades") or []]
        it["risk_usd"] = (d.get("params") or {}).get("risk_usd")
        items.append(it)
    return items


# ------------------------------------------------------------------------------------------------ research run library
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")
FAMILIES = ("baseline", "risk", "stops", "targets", "management", "bias", "filters", "timing", "other")
STATUSES = ("baseline", "adopt-candidate", "promising", "rejected", "info")
# what a public run file carries (tools/runlib.py save()); anything else a research script adds stays private
RUN_KEYS = ("id", "title", "family", "question", "status", "verdict", "notes", "writeup", "tags", "params", "sizing", "live_params",
            "live_equity_filter", "built", "data", "method", "spans", "years", "months", "trade_cols", "trades", "day_cols", "days")
INDEX_KEYS = ("id", "title", "family", "question", "status", "verdict", "writeup", "tags", "params", "sizing", "built", "spans")


def _runs(out, runs_dir, lm=None):
    """Index row per run into data.json; each run file copied to <out>/runs/<id>.json (fetched as runs/<id>.json?v=<hash>).
    Every row says which strategy it belongs to (`strategy`: lit | engine, engine/lab_scope.py). While live_model.json says
    lit, the Lab's reference run is lit_live and the engine's own baseline is kept as `archive_baseline` for the Archive."""
    dest = os.path.join(out, "runs")
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    idx = _load(os.path.join(runs_dir, "index.json"), {}) or {}
    rows, skipped, extra = [], [], set()
    for p in sorted(glob.glob(os.path.join(runs_dir, "*.json"))):        # top level only: research/runs/_cache is skipped
        name = os.path.basename(p)
        if name == "index.json" or name.endswith(".tmp"):
            continue
        r = _load(p)
        rid = str((r or {}).get("id") or "")
        if not isinstance(r, dict) or not SAFE_ID.match(rid) or rid + ".json" != name or not isinstance(r.get("spans"), dict):
            skipped.append(name)
            continue
        extra |= set(r) - set(RUN_KEYS)
        pub = {k: r.get(k) for k in RUN_KEYS}
        if lab_scope.strategy_of_run(pub) == "lit" and "cold-streak" in str(pub.get("method") or ""):
            pub["method"] = lab_scope.LIT_METHOD        # runlib's default text names the engine's cold-streak filter
        if pub["family"] not in FAMILIES:
            pub["family"] = "other"
        if pub["status"] not in STATUSES:
            pub["status"] = "info"
        blob = json.dumps(pub, separators=(",", ":"), default=str).encode("utf-8")
        with open(os.path.join(dest, name), "wb") as fh:
            fh.write(blob)
        row = {k: pub.get(k) for k in INDEX_KEYS}
        row["spans"] = {k: v for k, v in (pub.get("spans") or {}).items() if k in ("2026", "2021-25", "all")}
        row["v"] = hashlib.sha1(blob).hexdigest()[:10]
        row["kb"] = round(len(blob) / 1024)
        row["n_days"] = len(pub.get("days") or [])
        row["strategy"] = lab_scope.strategy_of_run(pub)
        rows.append(row)
    order = {s: i for i, s in enumerate(STATUSES)}
    rows.sort(key=lambda r: (order.get(r["status"], 9), r["family"], r["id"]))
    ids = {r["id"] for r in rows}
    base = lab_scope.live_baseline(lm, ids) or (idx.get("baseline") if idx.get("baseline") in ids else None)
    old = lab_scope.ENGINE_BASELINE if lab_scope.ENGINE_BASELINE in ids and base != lab_scope.ENGINE_BASELINE else None
    for r in rows:
        if r["id"] == base:                      # the live strategy's run reads as the reference on every page
            r["family"], r["status"] = "baseline", "baseline"
        elif old and r["id"] == old:
            r["status"] = "baseline"             # the reference of the archived engine experiments
    lit = lab_scope.is_lit_model(lm)
    lab = {"built": idx.get("built"), "baseline": base, "count": len(rows),
           "archive_baseline": old, "archive_prev": lab_scope.ENGINE_PREV if lab_scope.ENGINE_PREV in ids else None,
           "live_strategy": "lit" if lit else "engine", "archive_label": lab_scope.ARCHIVE_LABEL if lit else None,
           "columns": idx.get("columns") or {},
           "owner_rules": ("LIT is tuned and judged on 2026 only (picked on Jan-Jun, checked on Jul-Oct; 2021-25 is a reference line); "
                           "2-4 trades a week; evals decided within 2 weeks, no pass slower than 3 weeks") if lit else idx.get("owner_rules"),
           "families": list(FAMILIES), "statuses": list(STATUSES), "runs": rows}
    return lab, skipped, sorted(extra)


# ------------------------------------------------------------------------------------------------ write-ups + archive
# code is never published: a fenced block in a programming language, or one that reads like code, becomes a short note
CODE_LANGS = {"python", "py", "python3", "powershell", "ps1", "pwsh", "bash", "sh", "shell", "zsh", "console", "bat", "cmd", "js",
              "javascript", "mjs", "ts", "typescript", "jsx", "tsx", "pine", "pinescript", "c", "cpp", "c++", "java", "go", "rust", "sql",
              "html", "css", "yaml", "yml", "toml", "ini", "dockerfile", "make", "makefile", "r", "ruby", "php", "perl", "lua"}
CODEY = re.compile(r"^\s*(def |class |import |from \S+ import |return\b|for .+ in .+:|while .+:|if .+:\s*$|elif |else:|try:|except\b|"
                   r"with .+:|function |const |let |var |\$env:|python |pip |npm |node |git |cd |export |#include|select |//@version|"
                   r"strategy\(|indicator\(|[A-Za-z_][\w.]*\s*=\s*[\w\"'\[{(]|[A-Za-z_][\w.]*\(.*\)\s*;?\s*$)", re.I)
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*([^\s`]*)")
SECRET = re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
                    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|discord(?:app)?\.com/api/webhooks/\d+/[\w-]+|\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b|"
                    r"\bsk-[A-Za-z0-9]{20,}|(?i:(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"'])")
# research/*.md and research/lab/*.md that are not results: rulebooks, logs, code notes, setup, catalogs, briefs
ARCHIVE_SKIP = re.compile(r"(^STRATEGY|_LOG$|^NIGHT_LOG$|^DASHBOARD_|PINE|^MORNING_REPORT$|_RULES$|^PROTOCOL$|^CONFLUENCE_CATALOG$|"
                          r"^DOL_PLAYBOOK$|^WEEK_AHEAD$|^TRADER_HEURISTICS$)", re.I)
ARCHIVE_MAX = 80 * 1024
TRACKS = (("^ATM", "ATM model", "other"), ("^BIAS", "Daily bias", "bias"), ("^(COMBO|CONFLUENCE)", "Confluences", "filters"),
          ("^ICT", "ICT / SMC concepts", "filters"), ("^M22", "ICT 2022 model", "other"), ("^SB_", "Silver Bullet", "other"),
          ("^MECH", "Mechanical / IFVG model", "other"), ("^CONT", "Continuation model", "other"), ("^RISK", "Risk manager", "risk"),
          ("^TRADER_LAYER", "Trader layer", "management"), ("^PERSON", "Person-style management", "management"),
          ("^NARRATIVE", "Trader brain", "filters"), ("^DRAW", "Draw learner", "targets"), ("^REGIME", "Regime filter", "filters"),
          ("^ONE_MINUTE", "1-minute entries", "timing"), ("^FIVE_YEAR", "Five-year verdict", "baseline"), ("^DATA", "Data", "other"),
          ("^NIGHT", "Overnight research", "other"), ("^LEADERBOARD", "Strategy lab leaderboard", "other"), ("^EOD", "Paper test", "baseline"))
MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}


def _front(text):
    """YAML-ish front matter (key: value lines between --- fences) -> (meta, body)."""
    m = re.match(r"^﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|$)", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip():
            meta[k.strip().lower()] = v.strip().strip("\"'")
    return meta, text[m.end():]


def _clean(body):
    """Public copy of a markdown body: code blocks out. Returns (text, blocks dropped)."""
    out, block, fence, lang, dropped = [], None, "", "", 0
    for line in body.replace("\r\n", "\n").split("\n"):
        if block is None:
            m = FENCE.match(line)
            if m:
                block, fence, lang = [], m.group(1), m.group(2).lower().strip("{}.")
            else:
                out.append(line)
            continue
        s = line.strip()
        if s.startswith(fence[0] * len(fence)) and not s.strip(fence[0]):
            hits = sum(1 for x in block if x.strip() and CODEY.match(x))
            if lang in CODE_LANGS or hits >= max(1, len([x for x in block if x.strip()]) // 4):
                out.append("> _Code omitted on the public site._")
                dropped += 1
            else:
                out += [fence + lang] + block + [fence]
            block = None
        else:
            block.append(line)
    if block is not None:                       # unclosed fence: drop what is left
        out.append("> _Code omitted on the public site._")
        dropped += 1
    return "\n".join(out).strip() + "\n", dropped


def _plain(s):
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", s)
    s = re.sub(r"~~(.+?)~~", r"\1", s).replace("**", "")
    return re.sub(r"\s+", " ", s).strip()


META_PARA = re.compile(r"^(scripts?|built|written|generated|owned files|reproduce|raw output|re-run|command|files?)\b", re.I)


def _summary(body, limit=240):
    """First real paragraph (not a heading, table, code or a 'Scripts: / Built ... by' line), as plain text."""
    paras, cur = [], []
    for line in body.split("\n") + [""]:
        s = line.strip()
        if not s:
            if cur:
                paras.append(cur)
            cur = []
            continue
        if s.startswith(("#", "|", "```", "~~~", "---", "<")) and not cur:
            continue
        cur.append(s)
    pick = None
    for p in paras:
        if p[0].startswith(("|", "```", "~~~")):
            continue
        head = re.sub(r"^[>*_\s-]+", "", p[0])
        if META_PARA.match(head):
            continue
        pick = p
        break
    pick = pick or (paras[0] if paras else [])
    lines = [re.sub(r"^(>\s*)+", "", re.sub(r"^([-*+]|\d+[.)])\s+", "", x)) for x in pick[:6]]
    text = _plain(" ".join(lines))
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def _dates(t):
    out = [m.group(0) for m in re.finditer(r"\b20\d\d-[01]\d-[0-3]\d\b", t or "")]
    for m in re.finditer(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(20\d\d)\b", t or "", re.I):
        out.append(f"{m.group(3)}-{MONTHS[m.group(2)[:3].lower()]:02d}-{int(m.group(1)):02d}")
    today = dt.date.today().isoformat()
    return [d for d in out if d <= today]


def _date(title, body):
    """The report's own date: after 'Written / Built / Generated / Date', else the latest date in the title, else the latest
    date near the top."""
    m = re.search(r"(written|built|generated|date|updated)\W{0,3}(?:on\s+)?([^\n]{0,40})", body[:1500], re.I)
    for src in ((m.group(2) if m else ""), title, body[:1500]):
        ds = _dates(src)
        if ds:
            return max(ds)
    return ""


def _lit_rules_md():
    try:
        with open(os.path.join(ROOT, "STRATEGY.md"), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    m = re.search(r"^## Previous strategy", text, re.M)
    return text[:m.start()].rstrip() + "\n" if m else text


def _strategy_lines():
    try:
        with open(os.path.join(ROOT, "STRATEGY.md"), encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if len(ln.strip()) >= 50}
    except OSError:
        return set()


def _docs(out, writeups_dir):
    """research/writeups/*.md (front matter) + the archive of older result reports -> index + <out>/writeups/<slug>.md."""
    dest = os.path.join(out, "writeups")
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    strat = _strategy_lines()
    skipped, code_dropped, used = [], 0, set()

    def publish(path, slug, body):
        nonlocal code_dropped
        if SECRET.search(body):
            skipped.append(os.path.relpath(path, ROOT) + " (looks like it holds a secret)")
            return None
        if strat and sum(1 for ln in body.split("\n") if ln.strip() in strat) >= 3:
            skipped.append(os.path.relpath(path, ROOT) + " (quotes STRATEGY.md)")
            return None
        text, n = _clean(body)
        code_dropped += n
        blob = text.encode("utf-8")
        with open(os.path.join(dest, slug + ".md"), "wb") as fh:
            fh.write(blob)
        return {"slug": slug, "v": hashlib.sha1(blob).hexdigest()[:10], "words": len(re.findall(r"\w+", text)), "kb": round(len(blob) / 1024, 1),
                "src": os.path.relpath(path, ROOT).replace(os.sep, "/")}

    def slugify(s):
        s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:70] or "doc"
        k, i = s, 2
        while k in used:
            k, i = f"{s}-{i}", i + 1
        used.add(k)
        return k

    writeups = []
    extra = [(p, "lit-" + os.path.splitext(os.path.basename(p))[0]) for p in sorted(glob.glob(os.path.join(LIT_DOCS, "*.md")))]
    extra += [(p, "archive-engine-2026-10-17") for p in glob.glob(os.path.join(ARCHIVE, "README.md"))]
    for p, stem0 in [(p, None) for p in sorted(glob.glob(os.path.join(writeups_dir, "*.md"))) if os.path.basename(p).upper() != "INDEX.MD"] + extra:
        try:
            with open(p, encoding="utf-8") as fh:
                raw = fh.read()
        except (OSError, UnicodeDecodeError):
            skipped.append(os.path.relpath(p, ROOT))
            continue
        meta, body = _front(raw)
        stem = stem0 or os.path.splitext(os.path.basename(p))[0]
        h1 = re.search(r"^#\s+(.+)$", body, re.M)
        rec = publish(p, slugify(stem), body)
        if not rec:
            continue
        fam = meta.get("family", "other").lower()
        runs = [x for x in re.split(r"[,\s]+", meta.get("runs", "")) if x and SAFE_ID.match(x)]
        rec.update({"kind": "writeup", "title": meta.get("title") or (h1.group(1).strip() if h1 else stem.replace("_", " ")),
                    "family": fam if fam in FAMILIES else "other", "date": meta.get("date") or _date(stem, body),
                    "status": (meta.get("status") or "info").lower(), "summary": meta.get("summary") or _summary(body), "runs": runs,
                    "runs_linked": [], "track": meta.get("track") or "", "stem": stem.lower(),
                    "strategy": "archive" if stem0 and stem0.startswith("archive-") else lab_scope.strategy_of_doc(stem, rec["src"]),
                    "pin": lab_scope.pin_rank(stem)})
        if stem0 and stem0.startswith("archive-"):
            rec["status"] = "archive"
        writeups.append(rec)
    # LIT first (the pinned ones in their order, then the rest newest first), then the previous strategy's write-ups
    writeups.sort(key=lambda d: (d["date"], d["title"]), reverse=True)
    writeups.sort(key=lambda d: ({"lit": 0, "archive": 1}.get(d["strategy"], 2), d["pin"]))

    archive, left_out = [], []
    for p in sorted(glob.glob(os.path.join(RESEARCH, "*.md")) + glob.glob(os.path.join(LAB, "*.md"))):
        stem = os.path.splitext(os.path.basename(p))[0]
        if ARCHIVE_SKIP.search(stem) or os.path.getsize(p) > ARCHIVE_MAX:
            left_out.append(os.path.relpath(p, ROOT).replace(os.sep, "/"))
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                raw = fh.read()
        except (OSError, UnicodeDecodeError):
            skipped.append(os.path.relpath(p, ROOT))
            continue
        _, body = _front(raw)
        rec = publish(p, slugify("arc-" + stem.replace("_", "-")), body)
        if not rec:
            continue
        h1 = re.search(r"^#\s+(.+)$", body, re.M)
        title = _plain(h1.group(1)) if h1 else stem.replace("_", " ").title()
        track, fam = next(((t, f) for rx, t, f in TRACKS if re.search(rx, stem, re.I)), ("Other reports", "other"))
        rest = body[h1.end():] if h1 else body
        rec.update({"kind": "tables" if re.search(r"_(tables|diag)$", stem, re.I) else "report", "title": title, "family": fam,
                    "date": _date(title, body), "status": "archive", "summary": _summary(rest), "runs": [], "track": track})
        archive.append(rec)
    archive.sort(key=lambda d: (d["track"], d["kind"] != "report", d["date"]), reverse=False)
    return {"writeups": writeups, "archive": archive}, skipped, left_out, code_dropped


def _link(lab, docs):
    """Cross-links. A run's `writeup` field (a path or a file name) -> `writeup_slug` of the published write-up, and every
    write-up lists the runs that point at it (`runs_linked`, after the ones its front matter names). Unknown run ids are dropped."""
    by_stem = {d.pop("stem"): d for d in docs["writeups"]}
    ids = {r["id"] for r in lab["runs"]}
    for r in lab["runs"]:
        w = r.get("writeup")
        d = by_stem.get(os.path.splitext(os.path.basename(str(w)))[0].lower()) if w else None
        r["writeup_slug"] = d["slug"] if d else None
        if d and r["id"] not in d["runs"]:
            d["runs_linked"].append(r["id"])
    missing = 0
    for d in docs["writeups"]:
        missing += sum(1 for x in d["runs"] if x not in ids)
        d["runs"] = [x for x in d["runs"] if x in ids]
    return missing


def _archive(st, state_path, cfg_engine):
    """The previous strategy (Liquidity Engine, locked 2026-10-17) for the Archive pages: its lock, its last 5-year bundle
    (research/lab/backtest_engine.json: periods, months, days, stop buckets, lessons; no per-trade rows), the cold-streak
    filter's state (cloud shadow) and where its files are (research/archive/engine-2026-10-17/README.md)."""
    lm = _load(os.path.join(ROOT, "live_model_engine.json"), {}) or {}
    bt = _load(os.path.join(LAB, "backtest_engine.json"), {}) or {}
    res = None
    if bt:
        res = {"meta": {k: bt.get("meta", {}).get(k) for k in ("built", "strategy", "data", "costs", "method", "equity_filter")},
               "periods": bt.get("periods", {}), "months": bt.get("months", {}), "stop_buckets": bt.get("stop_buckets", []),
               "lessons": bt.get("lessons", {}), "days": [[d["date"], round(d["pnl"], 2), d.get("trades", 0)] for d in bt.get("days", [])],
               "trades": len(bt.get("trades") or [])}
    sh = (st or {}).get("shadow") or {}
    # its eval-timing verdict (GO / WAIT from the cold-streak filter), from the shadow ledger the cloud monitor keeps
    timing = None
    try:
        from engine import equity_filter as eqf
        led = os.path.join(os.path.dirname(state_path) or ".", "shadow_ledger.json")
        if not os.path.exists(led):
            led = os.path.join(ROOT, "data", "shadow_ledger_seed.json")
        if cfg_engine and os.path.exists(led):
            timing = eqf.eval_timing(sh.get("equity_filter") or eqf.status(cfg_engine, path=led), eqf.sessions_since_flip(cfg_engine, path=led))
    except Exception as e:                      # the archive must never break the build
        print("  archive: eval timing unavailable:", e.__class__.__name__, e)
    return {"label": lab_scope.ARCHIVE_LABEL, "readme": "archive-engine-2026-10-17", "dir": lab_scope.ARCHIVE_DIR,
            "strategy": {k: lm.get(k) for k in ("label", "chosen", "locked", "lock_note", "model", "sym", "params", "equity_filter", "sizing")},
            "results": res, "eval_timing": timing,
            "files": ["live_model_engine.json", "research/lab/backtest_engine.json", "tradingview/liquidity_engine.pine",
                      "STRATEGY.md (section: Previous strategy)", "research/runs/baseline.json", "research/runs/live_2026-10-17am.json",
                      lab_scope.ARCHIVE_DIR + "/montecarlo.json", lab_scope.ARCHIVE_DIR + "/intraday_heat.json"],
            "switch_back": ["cp live_model_engine.json live_model.json", "python tools/export_backtest.py",
                            "cp research/archive/engine-2026-10-17/montecarlo.json research/archive/engine-2026-10-17/intraday_heat.json research/lab/",
                            "python tools/export_replays.py, then python -X utf8 -m tests.test_live_dryrun --quick",
                            "commit and merge to the default branch (the cloud monitor reads live_model.json)"],
            "cold_config": cfg_engine}


def _lit_extra(st, lm):
    """The LIT panels' data (Day clock, Setup tracker, Levels, Eval cockpit, Week planner: tools/lit_dash_extra.py); None off LIT."""
    if not lab_scope.is_lit_model(lm):
        return None
    try:
        from tools import lit_dash_extra
        return lit_dash_extra.extra(st, lm)
    except Exception as e:                      # the panels must never break the build
        print("  lit_extra unavailable:", e.__class__.__name__, e)
        return None


def _learning_fallback():
    try:
        from engine import lit_learn
        L = lit_learn.load_learning()
        return lit_learn.summary(L, lit_learn.load_journal()) if L else None
    except Exception:
        return None


# ===================================================================================================== extras (extras.js)
# The phone app's extra pages (tools/web_public/extras.js: Eval HQ, Edge, P&L calendar, Ops check, MFFU rules). Everything
# here is read from files that are in the cloud checkout (.github/workflows/cloud-monitor.yml sparse-checkout); a missing
# file leaves its part out (None), and the whole block is None if anything unexpected happens: it never breaks the build.
EX_LEVELS = (("bu", "Equal highs / lows (build-up)"), ("asia18", "Asia 18-00"), ("asia19", "Tokyo"), ("asia20", "Asia 20-00"),
             ("lon23", "Frankfurt 02-03"), ("lon34", "London 03-04"), ("lon25", "London 02-05"), ("pre", "Premarket"),
             ("ny830", "NY 08:30"), ("ny89", "NY 08-09"), ("ny9301030", "NY 1st hour"), ("ny930", "NY 09:30-10"),
             ("pd", "Prior day"), ("pw", "Prior week"), ("pm", "Prior month"), ("nwog", "Weekly opening gap"),
             ("ndog", "Daily opening gap"))
EX_TCOLS = ["day", "min", "wd", "dir", "r", "pnl", "risk_pts", "qty", "exit", "mfe", "mae", "rr", "lv", "half"]


def _ex_family(key):
    """a swept-level key (engine/lit.py names: bu_h, asia19_l, pdh, nwog ...) -> its family id in EX_LEVELS"""
    k = str(key or "").lower()
    k = re.sub(r"_(h|l)$", "", k)
    if k in ("pdh", "pdl"):
        return "pd"
    if k in ("pwh", "pwl"):
        return "pw"
    if k in ("pmh", "pml"):
        return "pm"
    return k if any(k == f for f, _ in EX_LEVELS) else "other"


def _ex_stats(rows):
    """n, win %, avg R, net R, net $, PF ($) of trade rows (dicts with r, pnl)"""
    n = len(rows)
    if not n:
        return {"n": 0}
    won = sum(t["pnl"] for t in rows if t["pnl"] > 0)
    lost = -sum(t["pnl"] for t in rows if t["pnl"] < 0)
    return {"n": n, "win": round(100 * sum(1 for t in rows if t["pnl"] > 0) / n, 1),
            "avg_r": round(sum(t["r"] for t in rows) / n, 3), "net_r": round(sum(t["r"] for t in rows), 2),
            "net": round(sum(t["pnl"] for t in rows)), "pf": round(won / lost, 2) if lost > 0 else None}


def _extras(st, lm, bt):
    try:
        from zoneinfo import ZoneInfo
        NY = ZoneInfo("America/New_York")
        out = {"version": 1, "sources": {}}
        # ---- every LIT replay trade (backtest_live.json, live settings, normal sizing $800 / 20-pt) + MAE from run lit_live
        mae = {}
        rl = _load(os.path.join(RUNS, "lit_live.json"), None)
        if rl and rl.get("trade_cols"):
            c = rl["trade_cols"]
            for row in rl.get("trades") or []:
                t = dict(zip(c, row))
                if t.get("entry_t"):
                    mae[int(t["entry_t"])] = t.get("mae")
        rows = []
        for t in (bt or {}).get("trades") or []:
            if t.get("r") is None or not t.get("entry_t"):
                continue
            e = dt.datetime.fromtimestamp(int(t["entry_t"]), NY)
            fam = sorted({_ex_family(s) for s in (t.get("swept") or [])})
            rows.append({"day": t["day"], "min": e.hour * 60 + e.minute, "wd": e.weekday(), "dir": 1 if t.get("side") == "LONG" else -1,
                         "r": round(float(t["r"]), 3), "pnl": round(float(t.get("pnl") or 0), 2), "risk_pts": t.get("risk_pts"),
                         "qty": t.get("qty"), "exit": t.get("exit"), "mfe": t.get("mfe"), "mae": mae.get(int(t["entry_t"])),
                         "rr": t.get("plan_rr"), "lv": fam, "half": 1 if t.get("half") or t.get("weekly_stop") else 0})
        rows.sort(key=lambda x: (x["day"], x["min"]))
        out["tcols"] = EX_TCOLS
        out["trades"] = [[x[k] for k in EX_TCOLS] for x in rows]
        out["sources"]["trades"] = ("research/lab/backtest_live.json (LIT replay, live rules, normal sizing $800 up to a 20-pt stop; "
                                    f"built {(bt or {}).get('meta', {}).get('built')}) + MAE from research/runs/lit_live.json")
        # ---- level-type leaderboard: a trade that swept 2 families counts for both
        spans = {"2026": lambda d: d >= "2026", "H1": lambda d: "2026-01-01" <= d <= "2026-06-30", "H2": lambda d: d >= "2026-07-01",
                 "2021-25": lambda d: d < "2026"}
        names = dict(EX_LEVELS)
        board = {}
        for sp, f in spans.items():
            sub = [x for x in rows if f(x["day"])]
            fams = sorted({k for x in sub for k in x["lv"]})
            board[sp] = sorted(({"id": k, "name": names.get(k, "Other"), **_ex_stats([x for x in sub if k in x["lv"]])} for k in fams),
                               key=lambda r: -r.get("net", 0))
        out["levels"] = board
        # ---- eval odds under the live sizing (two_week, run lit_2wk_rec = config C; numbers from its notes' eval_path)
        r2 = _load(os.path.join(RUNS, "lit_2wk_rec.json"), None)
        if r2:
            ep = None
            n = r2.get("notes") or ""
            i = n.find("eval_path=")
            if i >= 0:
                try:
                    ep, _ = json.JSONDecoder().raw_decode(n[i + len("eval_path="):])
                except ValueError:
                    ep = None
            sp2 = r2.get("spans") or {}
            out["two_week"] = {"run": r2.get("id"), "title": r2.get("title"), "built": r2.get("built"), "sizing": r2.get("sizing"),
                               "eval": (ep or {}).get("50k"), "b2b_2026": (ep or {}).get("b2b_2026"), "b2b_2021_25": (ep or {}).get("b2b_2021_25"),
                               "money": {k: {kk: (sp2.get(k) or {}).get(kk) for kk in ("n", "tpw", "wk2", "pf", "net", "per_month", "dd", "worst_day", "risk")}
                                         for k in ("2026", "2021-25")}}
            out["sources"]["two_week"] = "research/runs/lit_2wk_rec.json (two-week sizing, MFFU Builder 50K, exact eval replay + Monte Carlo)"
        ev = _load(os.path.join(LIT_DOCS, "eventual.json"), None)       # local only unless the workflow checks it out
        if isinstance(ev, dict) and ev.get("C 10 sessions, then safe_eval"):
            out["eventual"] = {"label": "10 sessions two-week, then safe_eval (live rule)", **ev["C 10 sessions, then safe_eval"]}
            out["sources"]["eventual"] = "research/lit/eventual.json (tools/lit_eventual.py)"
        mc = _load(os.path.join(LAB, "montecarlo.json"), None)
        if mc:
            out["mc_normal"] = {"built": mc.get("built"), "strategy": mc.get("strategy"), "prob": mc.get("prob"), "halves": mc.get("halves"),
                                "exact": next((x for x in mc.get("exact") or [] if x.get("mode") == "live"), None)}
            out["sources"]["mc_normal"] = "research/lab/montecarlo.json (sizing mode normal, 2026 sessions)"
        # ---- MFFU rules (research/lit/mffu_rules.json), flattened for the rules card
        mr = _load(os.path.join(LIT_DOCS, "mffu_rules.json"), None)
        if mr:
            acct = mr.get(mr.get("account") or "builder_50k") or {}
            stages = []
            for stage in ("eval", "sim_funded", "live"):
                items = []
                for k, v in (acct.get(stage) or {}).items():
                    if isinstance(v, dict) and "value" in v:
                        items.append({"k": k, "value": v.get("value"), "status": v.get("status"), "note": v.get("note"), "checked": v.get("checked")})
                stages.append({"stage": stage, "items": items})
            out["mffu"] = {"title": mr.get("title"), "built": mr.get("built"), "method": mr.get("method"), "stages": stages}
            out["sources"]["mffu"] = "research/lit/mffu_rules.json"
        # ---- links (the repo this build runs in)
        repo = os.environ.get("GITHUB_REPOSITORY")
        if not repo:
            try:
                import subprocess
                u = subprocess.run(["git", "-C", ROOT, "remote", "get-url", "origin"], capture_output=True, text=True, timeout=5).stdout
                m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?\s*$", u)
                repo = m.group(1) if m else None
            except Exception:
                repo = None
        out["repo"] = repo
        return out
    except Exception as e:                          # extras must never break the build
        print("  extras unavailable:", e.__class__.__name__, e)
        return None


# ===================================================================================================== hub (hub.js)
# The phone app's Home / Strategy / Money pages (tools/web_public/hub.js): the tested upgrade combo, the funded plan, the
# research scoreboard and the changelog. research/lit/*.json and the git history are not in the cloud checkout (sparse,
# fetch-depth 1), so every local build that can read them refreshes tools/web_hub_snapshot.json and the cloud reads that.
HUB_SNAPSHOT = os.path.join(ROOT, "tools", "web_hub_snapshot.json")
COMBO = (("base", "LIT 2026-10-18 (no upgrades)"), ("t15", "15-minute check"), ("scale", "Scale-in after breakeven"), ("be_off", "Breakeven + 1.25 pts"),
         ("t15_be_off", "15-min check + BE + 1.25"), ("all3", "All three together"))
COMBO_KEYS = ("n", "tpw", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "pass_med", "pass_rate", "cost")
COMBO_PARAMS = (("t_check", "15-minute check: at 15 min, out if the trade is below +0.3R and never reached +0.5R"),
                ("scale_in", "Scale-in: one add on a 1m CISD after breakeven, stop moved to the add"),
                ("be_off", "Breakeven at entry + 1.25 pts (covers costs) instead of the entry"))
UPGRADES_ON_SINCE = "2026-10-20"   # owner switched t_check + be_off on in live_model.json (scale_in built, OFF until the Sim roundtrip)
# why a switch is off while the research says on (shown next to the chip on the phone's Strategy page)
UPGRADE_WAIT = {"scale_in": "waiting for the Sim check (python -m engine.ninjatrader --sim-roundtrip-add on Sim101)"}
COMBO_LIVE = {(): "base", ("t_check",): "t15", ("scale_in",): "scale", ("be_off",): "be_off", ("be_off", "t_check"): "t15_be_off",
              ("be_off", "scale_in", "t_check"): "all3"}   # the adopt_combo row that equals the live switch set
FUNDED_TRIO = ("mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k")
# the scoreboard: what the latest research found, in one line with its $ (write-up slug -> [verdict, line])
SCORE = {
    "lit-market-context": ["rejected", "2,520 market-context tilts (gamma, vanna, VIX term, OPEX): none held. The textbook gamma target idea loses $16.9k (Jan-Jun) / $5.3k (Jul-Oct)."],
    "lit-new-entries": ["rejected", "362 new entry types (MSNR, IDM into OB, stacked confluence): none adds money next to LIT. MSNR as a 2nd trade: -$1.6k Jan-Jun, 2-week fails 2.9% -> 10.1%."],
    "lit-money-batch2": ["candidate", "7 money ideas. One keeper, a habit: ask for a funded payout only once $1,500+ is above the buffer: +$29 / +$32 a month per account. Minis +$36 / +$12 a month (tiny)."],
    "lit-funded-firms": ["candidate", "MFFU Builder 50K + LucidPro 50K + FundedNext Rapid Daily 50K: ~$1,754 a month on Jul-Oct trades ($2,373 once all three are funded), ~$377 up front."],
    "lit-big-ideas": ["candidate", "Scale-in after breakeven: +$12.5k Jan-Jun / +$16.3k Jul-Oct, pass rate about flat. Needs the NinjaTrader add-order route before it can go live."],
    "lit-builder-25k": ["candidate", "Builder 25K ($63) on the same LIT signals: passes 54% / 48% in 2 weeks (Jan-Jun / Jul-Oct) at 50% of the room, ~79% / 77% in the end; 12-16% of evals can get stuck when the room falls under $100."],
    "lit-more-setups": ["rejected", "95 more setups (ES/MES, 15m/30m/1h, missed fills, looser filters): none beats LIT in both halves."],
    "lit-untested-targets": ["candidate", "Take the profit at 12:00 ET when the trade is +0.5R or better: a small candidate; every other target change rejected."],
    "lit-untested-stops": ["rejected", "Every other stop placement loses against 1 tick beyond the sweep extreme."],
    "lit-losses": ["adopted", "The loss pack (weekly stop + Monday rule) is live: 2026 PF 3.66, +$41.7k; Jul-Oct PF 2.46, +$9.0k."],
}
CHANGELOG_SKIP = re.compile(r"^(heartbeat|merge|wip|dashboard|bars|auto[- ]?update tick)\b", re.I)


def _git(*args):
    try:
        import subprocess
        r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=10)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def _changelog(n=24):
    """The bot's recent changes: commit titles of main (else HEAD), newest first; heartbeats, merges and WIP left out."""
    out, seen = [], set()
    for ref in ("origin/main", "main", "HEAD"):
        txt = _git("log", ref, "-n", "300", "--format=%ct\x1f%s")
        if txt:
            break
    for line in txt.splitlines():
        t, _, s = line.partition("\x1f")
        s = s.strip()
        if not s or CHANGELOG_SKIP.match(s) or s in seen or not t.isdigit():
            continue
        if re.search(r"(secret|token|password|api[_ -]?key|claude code plugin|\bplugins?\b|^(CLAUDE|AGENTS)\.md)", s, re.I):
            continue
        seen.add(s)
        out.append({"t": int(t), "date": dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m-%d"), "title": s[:160]})
        if len(out) >= n:
            break
    return out


PROPS = os.path.join(ROOT, "research", "props")
SECRETY = re.compile(r"(api[_-]?key|secret|password|token|bearer)", re.I)


def _props_norm(name, obj):
    """firms.json as tools/hub_data.py's study writes it (plan price {list: {v}, owner}, codes on the firm with "off" / "seen")
    -> also the flat fields hub.js planCard reads (price_owner, price_list, codes[{code, pct, source, date}]). Adds, never
    removes; anything else passes through."""
    if name == "business" and isinstance(obj, dict):    # the same source as the PC Business page: the tracker xlsx when here
        try:
            from tools import hub_data
            obj = hub_data.business_raw()
        except Exception as e:                  # noqa: BLE001
            print("  props: business tracker not read:", e.__class__.__name__, e)
        if "fees" not in obj:                   # hub.js bizPnl reads fees / payouts as {item, usd, date}
            obj = {**obj, "fees": [e for e in obj.get("expenses") or [] if not e.get("planned")]}
        return obj
    if name != "firms" or not isinstance(obj, dict):
        return obj
    def num(v):
        v = v.get("v") if isinstance(v, dict) else v
        return float(v) if isinstance(v, (int, float)) else None
    for f in obj.get("firms") or []:
        fc = []
        for c in f.get("codes") or []:
            if not isinstance(c, dict) or not c.get("code") or str(c["code"]).startswith("("):
                continue
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(c.get("off") or c.get("pct") or ""))
            fc.append({"code": c["code"], "pct": c.get("pct") if isinstance(c.get("pct"), (int, float)) else float(m.group(1)) if m else None,
                       "source": c.get("source") or c.get("applies") or c.get("n"), "date": c.get("date") or c.get("seen"), "st": c.get("st")})
        for p in f.get("plans") or []:
            pr = p.get("price") if isinstance(p.get("price"), dict) else {}
            if p.get("price_owner") is None and num(pr.get("owner")) is not None:
                p["price_owner"] = num(pr.get("owner"))
            if p.get("price_list") is None and num(pr.get("list")) is not None:
                p["price_list"] = num(pr.get("list"))
            if not p.get("codes") and fc:
                p["codes"] = fc
    return obj


def _props():
    """research/props/*.json (prop-firm research): firms.json -> "firms" (firms[].name, plans[].{name, price_list, price_owner,
    codes[{code, pct, source, date}], eval, funded, payouts, live, lit_fit}), every other small file under its own name
    (payouts, business, market ...). Files over 400 KB or that look like they hold a secret are left out. None when absent."""
    if not os.path.isdir(PROPS):
        return None
    out = {}
    for path in sorted(glob.glob(os.path.join(PROPS, "*.json"))):
        try:
            if os.path.getsize(path) > 400 * 1024:
                continue
            txt = open(path, encoding="utf-8").read()
            if SECRETY.search(txt) and not os.path.basename(path).startswith("firms"):
                print("  props: skipped (looks like it holds a secret):", os.path.basename(path))
                continue
            name = os.path.splitext(os.path.basename(path))[0]
            if name == "hub":                      # tools/hub_data.py's PC export: carried as data["hub"], not twice
                continue
            out["firms" if name == "firms" else name] = _props_norm(name, json.loads(txt))
        except Exception as e:
            print("  props: skipped", os.path.basename(path), e.__class__.__name__)
    return out or None


def _hub_research(lm):
    """combo (research/lit/adopt_combo.json), funded (research/lit/funded_firms.json), changelog (git): fresh when the files are
    here, else the snapshot. Never raises."""
    fresh = {}
    try:
        ac = _load(os.path.join(LIT_DOCS, "adopt_combo.json"), None)
        if isinstance(ac, dict) and ac.get("base"):
            rows = []
            for k, label in COMBO:
                v = ac.get(k) or {}
                if not v:
                    continue
                rows.append({"id": k, "label": label, "params": v.get("params") or {},
                             "lit": {s: {kk: (v.get("lit_rule") or {}).get(s, {}).get(kk) for kk in COMBO_KEYS} for s in ("H1", "H2", "2026", "2021-25")},
                             "eval": {s: {kk: (v.get("eval") or {}).get(s, {}).get(kk) for kk in COMBO_KEYS} for s in ("H1", "H2")},
                             "exits": v.get("exits_2026"), "adds": v.get("adds_2026")})
            fresh["combo"] = {"src": "research/lit/adopt_combo.json (tools/lit_adopt_combo.py)", "rows": rows}
        ff = _load(os.path.join(LIT_DOCS, "funded_firms.json"), None)
        if isinstance(ff, dict) and ff.get("combos"):
            plans = {p.get("id"): p for p in ff.get("plans") or []}
            trio = {}
            for c in ff["combos"]:
                if sorted(c.get("plans") or []) == sorted(FUNDED_TRIO):
                    trio[c.get("span")] = {k: c.get(k) for k in ("net_6m", "net_per_month", "net_med_6m", "neg_6m", "months4_6_per_month",
                                                                  "p_months4_6_ge_2000", "all_lost_one_funded")}
            fresh["funded"] = {"src": "research/lit/funded_firms.json (research/writeups/lit-funded-firms.md)", "built": ff.get("built"),
                               "plans": [{"id": i, "firm": (plans.get(i) or {}).get("firm"), "plan": (plans.get(i) or {}).get("plan"),
                                          "price": (plans.get(i) or {}).get("price"), "target": (plans.get(i) or {}).get("target"),
                                          "mll": (plans.get(i) or {}).get("mll")} for i in FUNDED_TRIO],
                               "trio": trio}
        cl = _changelog()
        if len(cl) >= 5:
            fresh["changelog"] = cl
        props = _props()
        if props:
            fresh["props"] = props
    except Exception as e:
        print("  hub research unavailable:", e.__class__.__name__, e)
    snap = _load(HUB_SNAPSHOT, {}) or {}
    if fresh and any(fresh.get(k) != snap.get(k) for k in fresh):      # a local build: keep the snapshot current for the cloud
        try:
            new = {**snap, **fresh}
            with open(HUB_SNAPSHOT, "w", encoding="utf-8") as fh:
                json.dump(new, fh, indent=1, ensure_ascii=False)
                fh.write("\n")
            print("  hub snapshot refreshed:", ", ".join(sorted(k for k in fresh if fresh.get(k) != snap.get(k))))
        except Exception as e:
            print("  hub snapshot not written:", e.__class__.__name__, e)
    out = {}
    for k in ("combo", "funded", "changelog", "props"):
        out[k] = fresh.get(k) or snap.get(k)
    L = (lm or {}).get("lit") or {}
    if out.get("combo"):
        sw = [{"key": k, "text": t, "on": (float(L.get(k) or 0.0) != 0.0) if k == "be_off" else bool(L.get(k))} for k, t in COMBO_PARAMS]
        for x in sw:
            if not x["on"] and UPGRADE_WAIT.get(x["key"]):
                x["wait"] = UPGRADE_WAIT[x["key"]]
        out["combo"] = {**out["combo"], "switches": sw, "all_on": all(x["on"] for x in sw), "any_on": any(x["on"] for x in sw),
                        "on_since": UPGRADES_ON_SINCE if any(x["on"] for x in sw) else None,
                        "live_id": COMBO_LIVE.get(tuple(sorted(x["key"] for x in sw if x["on"])))}
    return out


def _scoreboard(docs):
    """The research scoreboard: the latest LIT write-ups as short cards (curated line + verdict when known)."""
    rows = [w for w in (docs or {}).get("writeups") or [] if str(w.get("slug", "")).startswith("lit-") and w.get("strategy", "lit") == "lit"]
    rows.sort(key=lambda w: (w.get("date") or "", w.get("slug") in SCORE), reverse=True)
    out = []
    for w in rows:
        st = str(w.get("status") or "").lower()
        cur = SCORE.get(w["slug"])
        if not cur and st in ("knowledge", "finding", "info", "promising"):
            continue
        verdict = cur[0] if cur else ("rejected" if st.startswith("rejected") else "candidate" if "adopt" in st or "candidate" in st else "info")
        m = re.search(r"([\d,]{2,}) (?:\w+ )?variants", w.get("summary") or "")
        out.append({"slug": w["slug"], "title": w.get("title"), "date": w.get("date"), "verdict": verdict,
                    "line": cur[1] if cur else _plain(w.get("summary") or "")[:220], "tested": m.group(1) if m else None,
                    "status": str(w.get("status") or "")[:160]})
        if len(out) >= 12:
            break
    return out


def _hub(st, lm, docs):
    try:
        h = _hub_research(lm)
        h["scoreboard"] = _scoreboard(docs)
        pc = st.get("pc") if isinstance(st.get("pc"), dict) else {}
        hl = pc.get("health") if isinstance(pc.get("health"), dict) else None
        try:
            from engine import accounts as _a
            h["auto_text"] = _a.auto_text(hl) if hl else None
        except Exception:
            h["auto_text"] = None
        try:                                      # the business tools (tools/business.py): statement, payouts, tax, planner,
            from tools import business as _biz    # scaling calendar, goal, ROI; the watchers' last run from the PC heartbeat
            h["biz"] = _biz.view()
            ow = (pc.get("ops") or {}).get("watch") if isinstance(pc.get("ops"), dict) else None
            if ow:
                h["biz"]["watch_pc"] = ow
        except Exception as e:
            print("  business tools unavailable:", e.__class__.__name__, e)
        return h
    except Exception as e:
        print("  hub unavailable:", e.__class__.__name__, e)
        return None


def _intel(out, st, state_path):
    """Trade Intelligence (tools/trade_intel.py): research/lab/trade_intel.json (the backtest rows + win / loss signs, rebuilt
    on the PC when run lit_live changes) + the paper / live rows of now from the cloud state and the learning journal, written
    whole to intel.json (the phone's Trade intel page loads it lazily); data.json gets the compact cut. A few ms, no engine."""
    try:
        from tools import trade_intel as TI
        base = TI._load(TI.OUT)
        if not base:
            return None
        jp = os.path.join(os.path.dirname(state_path) or ".", "lit_journal.jsonl")
        full = TI.merge_live(base, st, TI._journal(jp) if os.path.exists(jp) else TI._journal(os.path.join(ROOT, "data", "lit_journal.jsonl")))
        with open(os.path.join(out, "intel.json"), "w", encoding="utf-8") as fh:
            json.dump(full, fh, separators=(",", ":"), default=str)
        return TI.compact(full)
    except Exception as e:
        print("  trade intel unavailable:", e.__class__.__name__, e)
        return None


def _perf(st, state_path):
    """Performance pages (engine/perf.py): expected range, live vs backtest (the PC's heartbeat exec curve), exit efficiency,
    robustness, months, status (state "uptime"), look-ahead audit. Reads research/lab/*.json; a few ms, no engine run."""
    try:
        from engine import perf as PF
        from tools import trade_intel as TI
        jp = os.path.join(os.path.dirname(state_path) or ".", "lit_journal.jsonl")
        J = TI._journal(jp) if os.path.exists(jp) else []
        base = TI._load(TI.OUT)
        full = TI.merge_live(base, st, J) if base else None
        return PF.view(st, J, None, st.get("uptime"), intel_full=full, compact=True)
    except Exception as e:
        print("  perf unavailable:", e.__class__.__name__, e)
        return None


HOME_LIVE = ("last_run", "runs", "health", "eval", "eval_2wk", "eval_life", "eval_timing", "model_state", "position", "strategy", "price", "today", "brain",
             "events", "pc", "pc_verdict", "pc_outage", "pc_checkin", "model", "lit_rules", "lit_sizing", "lit", "setups", "armed", "levels", "session", "notices")


def build(state_path, chart_path, out, runs_dir=RUNS, writeups_dir=WRITEUPS):
    os.makedirs(out, exist_ok=True)
    st = _load(state_path, {}) or {}
    bt = _load(os.path.join(LAB, "backtest_live.json"), {}) or {}
    # the ledger is keyed by entry time (epoch s): kept on each row as entry_t (the LIT day clock and week planner place trades by it)
    ledger = sorted(({**v, "entry_t": int(k)} if str(k).isdigit() else dict(v) for k, v in (st.get("ledger") or {}).items()),
                    key=lambda v: (v.get("day", ""), v.get("entry", "")), reverse=True)
    live = {k: st.get(k) for k in ("last_run", "first_run", "runs", "health", "eval", "model_state", "position", "strategy",
                                   "equity_filter", "eval_timing", "eval_2wk", "eval_life", "price", "today", "events", "engine_trades", "bars", "bars1", "pools", "pc",
                                   "pc_verdict",                        # engine/accounts.verdict: is the PC bot trading the eval
                                   "pc_outage", "pc_checkin",           # engine/push.pc_outage / pc_checkin_line: the Surface-offline line
                                   "model", "shadow", "lit_rules", "lit_sizing", "lit", "session", "levels", "setups",
                                   "push", "notices", "learning",       # learning: engine/lit_learn.py summary (the "What the bot learned" card)
                                   "armed", "watch",                   # armed: engine/lit_watch.py armed_line; watch: tools/lit_watch.py summary (Yahoo lag)
                                   "recaps", "weekly",                 # tools/recap.py: recap cards + brief image (PNGs in recaps/), weekly review
                                   "brain")}                           # the cloud paper bot's Bot Brain (engine/brain.py compact)
    try:                                   # LIT day analyst (engine/lit_brief.py): today's news re-read from the fresh hub
        from engine import lit_brief
        live["brief"] = lit_brief.with_news(st.get("brief"), _load(os.path.join(ROOT, "data", "news", "hub.json"), None))
    except Exception as e:
        print("  brief unavailable:", e.__class__.__name__, e)
        live["brief"] = st.get("brief")
    # phone notifications: the VAPID public key the app subscribes with (the cloud's, derived from the LE_VAPID_PRIVATE secret,
    # else tools/web_public/push_key.json from tools/push_keys.py) and the public push status (device ids, never endpoints)
    pk = (_load(os.path.join(WEB, "push_key.json"), {}) or {}).get("vapid_public")
    relay = _load(os.path.join(WEB, "push_relay.json"), {}) or {}
    live["push"] = {**(st.get("push") or {}), "vapid_public": (st.get("push") or {}).get("vapid_public") or pk}
    live["push"].setdefault("relay", {"ntfy": relay.get("ntfy"), "topic": relay.get("topic")} if relay.get("topic") else None)
    for k in ("private", "vapid_private", "subs", "push_subs", "box"):   # never public (status() has none of these; belt and braces)
        live["push"].pop(k, None)
    live["ledger"] = ledger[:200]
    # Accounts page: one section per account (live_model.json "accounts", default the MFFU 50K eval on the PC bot, from the
    # heartbeat's "acct" block) + the cloud paper ledger (engine/accounts.py); the raw block stays out of live.pc
    lm_acc = _load(os.path.join(ROOT, "live_model.json"), {}) or {}
    try:
        from engine import accounts as _accounts
        accounts = _accounts.build_accounts(st, lm_acc)
    except Exception as e:
        print("  accounts unavailable:", e.__class__.__name__, e)
        accounts = []
    if isinstance(live.get("pc"), dict):
        live["pc"] = {k: v for k, v in live["pc"].items() if k not in ("acct", "exec")}
        try:                       # the verdict again at build time (the heartbeat age grows between cloud runs)
            from engine import accounts as _acc_v
            live["pc_verdict"] = _acc_v.verdict(st.get("pc"), st.get("last_run") or None)
        except Exception as e:
            print("  pc verdict unavailable:", e.__class__.__name__, e)
    results = None
    if bt:
        results = {"meta": {k: bt.get("meta", {}).get(k) for k in ("built", "strategy", "data", "costs", "method", "equity_filter")},
                   "periods": bt.get("periods", {}), "months": bt.get("months", {}), "stop_buckets": bt.get("stop_buckets", []),
                   "lessons": bt.get("lessons", {}), "days": [[d["date"], round(d["pnl"], 2), d.get("trades", 0)] for d in bt.get("days", [])]}
    shadow = _load(os.path.join(os.path.dirname(state_path) or ".", "shadow_ledger.json"), None) \
        or _load(os.path.join(ROOT, "data", "shadow_ledger_seed.json"), []) or []
    lm = _load(os.path.join(ROOT, "live_model.json"), {}) or {}
    # the cold-streak filter belongs to the old engine: while LIT is live it is the archived lock's (shadow ledger)
    cfg = lm.get("equity_filter") or ((_load(os.path.join(ROOT, "live_model_engine.json"), {}) or {}).get("equity_filter")
                                      if lab_scope.is_lit_model(lm) else None) or {}
    lab, run_skipped, run_extra = _runs(out, runs_dir, lm)
    docs, doc_skipped, left_out, code_dropped = _docs(out, writeups_dir)
    unknown_runs = _link(lab, docs)
    replays = _load(os.path.join(LAB, "replays.json"), {}) or {}
    charts = _charts(out, replays)
    data = {
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "live": live,
        "news": news_hub.hub_for_dashboard(os.path.join(ROOT, "data", "news", "hub.json")),
        "results": results,
        "trades": _trades(bt, charts),
        "replays": replays,
        "variants": _load(os.path.join(LAB, "variant_results.json"), {}) or {},
        "study": _study(out),
        "cold": {"config": cfg, "now": st.get("equity_filter") if not lab_scope.is_lit_model(lm) else (st.get("shadow") or {}).get("equity_filter"),
                 "window": [{"day": x.get("day"), "r": x.get("r")} for x in sorted(shadow, key=lambda x: x.get("exit_t", 0))[-int(cfg.get("lookback", 15)):]]},
        "sizing": {"risk_usd": (lm.get("params") or {}).get("risk_usd"), "risk_ref_stop": (lm.get("params") or {}).get("risk_ref_stop"),
                   "max_trades_day": (lm.get("params") or {}).get("max_trades_day"), "label": lm.get("label"), "chosen": lm.get("chosen")},
        # the locked strategy for the Strategy page: label, lock date + note, the settings that differ from the engine defaults,
        # the cold-streak filter (cold_size) and the extra size rules (sizing: late_mult, press)
        "strategy": {**{k: lm.get(k) for k in ("label", "chosen", "locked", "lock_note", "model", "sym", "params", "equity_filter", "sizing",
                                               "lit", "lit_sizing", "size_rule")},
                     # LIT: the rules word for word (the LIT part of STRATEGY.md, before "## Previous strategy") for the Strategy page
                     "rules_md": _lit_rules_md() if lm.get("model") == "lit" else None},
        "lab": lab,
        "docs": docs,
        "archive": _archive(st, state_path, cfg) if lab_scope.is_lit_model(lm) else None,
        "lit_extra": _lit_extra(st, lm),
        "accounts": accounts,
    }
    data["intel"] = _intel(out, st, state_path)
    data["perf"] = _perf(st, state_path)
    try:                                   # second strategies, PAPER (engine/second.py): rules, backtest tables, state, trades
        from engine import second as _second
        data["second"] = _second.dashboard_block(st.get("second"), pc=(st.get("pc") or {}).get("second"))
    except Exception as e:
        data["second"] = {"error": f"{e.__class__.__name__}: {e}", "strategies": []}
    try:                                   # scaling plan (engine/scale_plan.py, read-only): step N, the next account, the ladder
        from engine import scale_plan as _scale
        data["scale"] = _scale.cloud_view(st)
    except Exception as e:
        data["scale"] = {"error": f"{e.__class__.__name__}: {e}"}
    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"), default=str)
    # research data files for the Lab's 3D views (Monte Carlo cloud, intraday heat, calendar): lab/<name>.json
    lab_dir = os.path.join(out, "lab"); os.makedirs(lab_dir, exist_ok=True)
    # live files from research/lab (LIT's while live_model.json says lit: tools/lit_dash_data.py); the previous strategy's
    # versions from the archive as <name>_engine (calendar_effects is an engine study, so it is archive-only)
    LAB_FILES = [(n, os.path.join(LAB, n + ".json")) for n in ("montecarlo", "intraday_heat", "rejections")]   # rejections: tools/lit_rejections.py
    if lab_scope.is_lit_model(lm):
        LAB_FILES += [(n + "_engine", os.path.join(ARCHIVE, n + ".json")) for n in ("montecarlo", "intraday_heat")]
        LAB_FILES += [("calendar_effects_engine", os.path.join(LAB, "calendar_effects.json"))]
    else:
        LAB_FILES += [("calendar_effects", os.path.join(LAB, "calendar_effects.json"))]
    have = []
    for name, src in LAB_FILES:
        if os.path.exists(src):
            shutil.copy(src, os.path.join(lab_dir, name + ".json")); have.append(name)
    data["lab_files"] = have
    # the learning loop (engine/lit_learn.py): the cloud's summary from state.json, else the repo's learning file + journal
    data["learning"] = st.get("learning") or _learning_fallback()
    # execution quality of the live eval (engine/fill_audit.py on the PC, carried by its heartbeat as "exec"): slippage $ per
    # trade / month against the backtest, missed and extra trades (live_panel.js execution card)
    data["exec"] = (st.get("pc") or {}).get("exec") if isinstance(st.get("pc"), dict) else None
    # Bot Brain (engine/brain.py): the plain-English explainers once here (the live cuts in live.pc.brain / live.brain skip them)
    try:
        from engine import brain as _brain
        data["brain_help"] = _brain.HELP
    except Exception as e:
        print("  brain help unavailable:", e.__class__.__name__, e)
    # the three LIT upgrades live (tools/upgrade_shadow.py via the cloud monitor's lit_base ledger): with vs without, per upgrade
    data["upgrades_live"] = st.get("upgrades_live")
    data["extras"] = _extras(st, lm, bt)          # extras.js pages (Eval HQ, Edge, Calendar, Ops, MFFU rules)
    hub = _hub(st, lm, docs)                      # hub.js pages (Home, LIT plan, Strategy upgrades + scoreboard, Money, changelog)
    data["props"] = (hub or {}).pop("props", None)   # Prop Firms / payouts / business / market (research/props/*.json)
    # the PC hub pages' data (prop firms, business, market, learn, system): research/props/hub.json, built by tools/hub_data.py;
    # its keys sit next to the phone's (combo / funded / changelog / scoreboard win on a clash), home.json keeps the phone's only
    data["hub"] = {**(_load(os.path.join(ROOT, "research", "props", "hub.json"), None) or {}), **(hub or {})}
    # trade pictures (engine/trade_chart.py): the cloud's paper-trade charts (<dash>/charts) + the backtest examples
    # (research/lab/chart_examples) -> site/charts/, data.json "charts" (per strategy: items newest first, examples)
    try:
        from engine import trade_chart
        data["charts"] = trade_chart.site_copy(os.path.join(os.path.dirname(state_path) or ".", "charts"), out)
        print(f"  charts: {data['charts']['counts']['live']} paper-trade pictures + {data['charts']['counts']['examples']} examples -> charts/")
    except Exception as e:
        print("  charts unavailable:", e.__class__.__name__, e)
        data["charts"] = None
    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"), default=str)
    # home.json: the small file the Home screen draws from first (~100 KB instead of the 4 MB data.json), same build
    ex = data.get("extras") or {}
    charts_home = None
    try:
        from engine import trade_chart
        charts_home = trade_chart.compact_view(data.get("charts")) if data.get("charts") else None
    except Exception:
        pass
    home = {"built": data["built"], "home_only": True,
            "live": {**{k: live.get(k) for k in HOME_LIVE}, "bars": (live.get("bars") or [])[-120:], "brief": live.get("brief"),
                     "ledger": (live.get("ledger") or [])[:20], "push": {k: (live.get("push") or {}).get(k) for k in ("configured", "devices")}},
            "accounts": [{k: v for k, v in a.items() if k not in ("trades", "days", "orders")} for a in accounts],
            "exec": data["exec"], "hub": hub,
            "strategy": {k: (data["strategy"] or {}).get(k) for k in ("label", "chosen", "model", "lit", "lit_sizing")},
            "lit_extra": {k: (data.get("lit_extra") or {}).get(k) for k in ("plan", "sizing")} if data.get("lit_extra") else None,
            "extras": {"two_week": ex.get("two_week"), "eventual": ex.get("eventual")},
            # ATLAS (data.json "second") for the Home card: state, brain, the last trades, account B, the scorecard
            "second": {**{k: v for k, v in (data.get("second") or {}).items() if k not in ("strategies", "atlas")},
                       "atlas": {"name": ((data.get("second") or {}).get("atlas") or {}).get("name"),
                                 "members": ((data.get("second") or {}).get("atlas") or {}).get("members")},
                       "strategies": [{**{k: v for k, v in s.items() if k not in ("backtest", "rules", "trades", "summary")},
                                       "trades": (s.get("trades") or [])[-12:]} for s in (data.get("second") or {}).get("strategies") or []]},
            "charts": charts_home,                  # the newest trade pictures per strategy (engine/trade_chart.compact_view)
            "results": {"periods": {k: v for k, v in ((results or {}).get("periods") or {}).items()
                                    if k in ("2026 YTD", "2026 H1 (picked on)", "2026 H2 (check)", "2021-25 (reference)")}}}
    with open(os.path.join(out, "home.json"), "w", encoding="utf-8") as fh:
        json.dump(home, fh, separators=(",", ":"), default=str)
    # the page, the home-screen app files and its icons
    for name in os.listdir(WEB):
        src = os.path.join(WEB, name)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(out, name))
    os.makedirs(os.path.join(out, "icons"), exist_ok=True)
    for name in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png", "icon.svg"):
        if os.path.exists(os.path.join(ICONS, name)):
            shutil.copy(os.path.join(ICONS, name), os.path.join(out, "icons", name))
    if chart_path and os.path.exists(chart_path):
        shutil.copy(chart_path, os.path.join(out, "chart.png"))
    # recap cards + the brief image (tools/recap.py, <dash>/recaps/*.png): the ones the state lists, nothing else
    rc_src = os.path.join(os.path.dirname(state_path) or ".", "recaps")
    rc_dst = os.path.join(out, "recaps")
    shutil.rmtree(rc_dst, ignore_errors=True)
    rc = live.get("recaps") or {}
    want = [c.get("png") for c in rc.get("cards") or [] if isinstance(c, dict)] + [(rc.get("brief") or {}).get("png")]
    n_rc = 0
    for rel in want:
        name = str(rel or "")[len("recaps/"):]
        if not str(rel or "").startswith("recaps/") or not name.endswith(".png") or "/" in name or "\\" in name or ".." in name:
            continue
        src = os.path.join(rc_src, name)
        if os.path.exists(src):
            os.makedirs(rc_dst, exist_ok=True)
            shutil.copy(src, os.path.join(rc_dst, name))
            n_rc += 1
    if n_rc:
        print(f"  recaps: {n_rc} PNGs -> recaps/")
    open(os.path.join(out, ".nojekyll"), "w").close()
    kb = os.path.getsize(os.path.join(out, "data.json")) // 1024
    print(f"site -> {out}: data.json {kb} KB, {len(ledger)} paper trades, {len(data['trades'])} replay trades, "
          f"{len(data['replays'].get('sessions', []))} replays, {len(charts)} trade charts -> replays/<id>.json, {len(data['variants'].get('rows', []))} variants, {len(data['study'])} study")
    print(f"  lab: {lab['count']} runs (baseline: {lab['baseline'] or 'missing'}) -> runs/<id>.json"
          + (f"; skipped {', '.join(run_skipped)}" if run_skipped else "") + (f"; private fields kept out: {', '.join(run_extra)}" if run_extra else ""))
    print(f"  docs: {len(docs['writeups'])} write-ups + archive of {len(docs['archive'])} older reports "
          f"({sum(1 for d in docs['archive'] if d['kind'] == 'tables')} of them tables) -> writeups/<slug>.md; "
          f"{code_dropped} code blocks dropped; {len(left_out)} research docs left out (rulebooks, logs, code notes, >80 KB)"
          + (f"; {unknown_runs} run ids named in write-ups are not stored runs" if unknown_runs else ""))
    for s in doc_skipped:
        print(f"  docs: SKIPPED {s}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="dash/state.json")
    ap.add_argument("--chart", default="dash/chart.png")
    ap.add_argument("--out", default="site")
    ap.add_argument("--runs", default=RUNS, help="run library folder (default research/runs)")
    ap.add_argument("--writeups", default=WRITEUPS, help="write-ups folder (default research/writeups)")
    a = ap.parse_args()
    build(a.state, a.chart, a.out, a.runs, a.writeups)
