"""Build the PC-off web dashboard (static site) published to the public repo demetrades2000-coder/nq-dashboard (GitHub Pages).

The site is one page (tools/web_public/index.html) that reads everything from data.json; nothing runs on a server.
data.json holds:
  live      the cloud monitor's state (model state, eval tracker, cold-streak filter, paper ledger, recent bars, pools, and
            `pc`: the always-on PC bot's heartbeat {present, t, age_s, silent, running, adapter, position, model_state, host, reason})
  results   the live-settings 5-year replay (periods, months, daily P&L, stop buckets, eval odds, lessons)
  trades    every replay trade with its report (why it entered / plan / result / lessons); 2026 with full detail
  replays   5m session bars for each replay trade day (tools/export_replays.py)
  variants  every tested variant (research/lab/variant_results.json)
  study     trades under review (research/study), charts copied to study/
  cold      the cold-streak filter config, state and its last-15 window
  sizing / strategy   the locked live settings (live_model.json: label, lock date, params, cold-streak filter)
  lab       the research run library index (research/runs, tools/runlib.py): one compact row per backtest run; every run
            file (all its trades, days, months, years) is copied to runs/<id>.json and fetched by the run page on demand
  docs      research write-ups (research/writeups/*.md, front matter + markdown) and an archive of the older result
            reports (research/*.md, research/lab/*.md); the text goes to writeups/<slug>.md, fetched by the reader
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
        "bars_held", "checklist", "smc", "report")
SLIM_DROP = ("conf_tags", "checklist", "smc", "zone", "pools")


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _trades(bt):
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
    for p, stem0 in [(p, None) for p in sorted(glob.glob(os.path.join(writeups_dir, "*.md")))] + extra:
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


def build(state_path, chart_path, out, runs_dir=RUNS, writeups_dir=WRITEUPS):
    os.makedirs(out, exist_ok=True)
    st = _load(state_path, {}) or {}
    bt = _load(os.path.join(LAB, "backtest_live.json"), {}) or {}
    ledger = sorted((st.get("ledger") or {}).values(), key=lambda v: (v.get("day", ""), v.get("entry", "")), reverse=True)
    live = {k: st.get(k) for k in ("last_run", "first_run", "runs", "health", "eval", "model_state", "position", "strategy",
                                   "equity_filter", "eval_timing", "price", "today", "events", "engine_trades", "bars", "pools", "pc",
                                   "model", "shadow", "lit_rules", "lit_sizing")}
    live["ledger"] = ledger[:200]
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
    data = {
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "live": live,
        "news": news_hub.hub_for_dashboard(os.path.join(ROOT, "data", "news", "hub.json")),
        "results": results,
        "trades": _trades(bt),
        "replays": (_load(os.path.join(LAB, "replays.json"), {}) or {}),
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
    }
    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"), default=str)
    # research data files for the Lab's 3D views (Monte Carlo cloud, intraday heat, calendar): lab/<name>.json
    lab_dir = os.path.join(out, "lab"); os.makedirs(lab_dir, exist_ok=True)
    # live files from research/lab (LIT's while live_model.json says lit: tools/lit_dash_data.py); the previous strategy's
    # versions from the archive as <name>_engine (calendar_effects is an engine study, so it is archive-only)
    LAB_FILES = [(n, os.path.join(LAB, n + ".json")) for n in ("montecarlo", "intraday_heat")]
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
    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"), default=str)
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
    open(os.path.join(out, ".nojekyll"), "w").close()
    kb = os.path.getsize(os.path.join(out, "data.json")) // 1024
    print(f"site -> {out}: data.json {kb} KB, {len(ledger)} paper trades, {len(data['trades'])} replay trades, "
          f"{len(data['replays'].get('sessions', []))} replays, {len(data['variants'].get('rows', []))} variants, {len(data['study'])} study")
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
