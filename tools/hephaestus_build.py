"""HEPHAESTUS build (2026-11-03): the data for tools/web_public/hephaestus/ from the STORED backtest runs. Read-only.

  python tools/hephaestus_build.py                  writes tools/web_public/hephaestus/data.json
  python tools/hephaestus_build.py --out <file>     writes somewhere else (the test does)

Nothing is recomputed about the strategy. Each setting on the page is one stored run in research/runs/ (written by
tools/runlib.py). This script only cuts a run's own stored trades and days into Jan-Jun and Jul-Oct 2026 and scores the
two cuts with runlib's own scorer (the same one that wrote the run's headline numbers, so the full-year 2026 line must equal
the run's stored 2026 line; the test checks that). A setting that has no stored run is simply not in the file, so the page
shows it as "not tested". Changes nothing in the bot: it reads research/runs/*.json and docs/CLAUDE_REFERENCE.md only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "tools", "web_public", "hephaestus", "data.json")
REF_MD = os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md")

H1 = ("2026-01-01", "2026-06-30")
H2 = ("2026-07-01", "2026-12-31")
Y26 = ("2026-01-01", "2026-12-31")

# The dials, in the order they are shown. v = the value the scenarios use, label = the owner's words. "live" marks today's value.
DIALS = [
    {"id": "target", "label": "Target (banked at)", "options": [
        {"v": "4R", "label": "4R"}, {"v": "6R", "label": "6R"}, {"v": "8R", "label": "8R", "live": True}, {"v": "10R", "label": "10R"},
        {"v": "none", "label": "No cap"}]},
    {"id": "be", "label": "Break-even at 1R", "options": [
        {"v": "on", "label": "On (+1.25 pts costs)", "live": True}, {"v": "nocost", "label": "On, no costs"}, {"v": "off", "label": "Off"}]},
    {"id": "cut", "label": "15-minute cut", "options": [{"v": "on", "label": "On", "live": True}, {"v": "off", "label": "Off"}]},
    {"id": "window", "label": "Entry window (ET)", "options": [
        {"v": "0200-1530", "label": "02:00-15:30", "live": True}, {"v": "0100-1555", "label": "01:00-15:55"}, {"v": "0000-1530", "label": "00:00-15:30"},
        {"v": "0930-1530", "label": "09:30-15:30"}]},
    {"id": "maxtr", "label": "Max trades a day", "options": [
        {"v": "1", "label": "1", "live": True}, {"v": "2", "label": "2"}, {"v": "3", "label": "3"}, {"v": "5", "label": "5"}]},
    {"id": "size", "label": "Size mode", "options": [
        {"v": "headline", "label": "Headline replay (live)", "live": True}, {"v": "two_week", "label": "Two-week (60%)"}, {"v": "uprisk", "label": "Uprisk (80%)"}]},
]
LIVE = {"target": "8R", "be": "on", "cut": "on", "window": "0200-1530", "maxtr": "1", "size": "headline"}


def D(**kw):
    return {**LIVE, **kw}


# One stored run per setting. "ref" is the run the setting is judged against. The one-change runs (abl_rm_*, "remove one rule")
# were stored when the 1m confirm window was 20 bars (today 22), so they are judged against their own twin hq_lit_live and
# the page says so. Every run id here must exist in research/runs/ (the build stops if one is missing).
SCENARIOS = [
    # id, run, dials, label, ref, selectable
    ("live", "lit_live", D(), "The live setting: the headline replay (cisd 22)", None, True),
    ("two_week", "abl_rec_cisd22_eval", D(size="two_week"), "Two-week sizing: 60% of the room", "live", True),
    ("uprisk", "lit_edge_eval_live", D(size="uprisk"), "Uprisk sizing: 80% of the room", "live", True),
    ("twin", "hq_lit_live", D(), "Twin of the one-change runs (confirm window 20)", None, False),
    ("no_cap", "abl_rm_max_rr", D(target="none"), "No target cap", "twin", True),
    ("no_be", "abl_rm_be", D(be="off"), "No break-even", "twin", True),
    ("be_nocost", "abl_rm_be_off", D(be="nocost"), "Break-even without the cost cushion", "twin", True),
    ("no_cut", "abl_rm_t_check", D(cut="off"), "No 15-minute cut", "twin", True),
    ("wide_window", "abl_rm_window", D(window="0100-1555"), "Wider entry window", "twin", True),
    ("five_trades", "abl_rm_one_day", D(maxtr="5"), "Up to 5 trades a day", "twin", True),
]


def _cut(run, a, z):
    cols, dcols = run["trade_cols"], run["day_cols"]
    T = [dict(zip(cols, t)) for t in run["trades"]]
    for t in T:
        t["half"] = bool(t["half"])
    Dd = [dict(zip(dcols, d)) for d in run["days"]]
    TT = [t for t in T if a <= t["day"] <= z]
    DD = [d for d in Dd if a <= d["date"] <= z]
    return rl._compact(TT, DD) if DD else {"n": 0}


KEEP = ("n", "tpw", "win", "pf", "net", "per_month", "dd", "p10", "f10", "dec10", "pass_med")


def _slim(c):
    return {k: c.get(k) for k in KEEP}


def _rejected():
    """The 'Tested and rejected' bullets of docs/CLAUDE_REFERENCE.md as [{title, text}], plain text, cut short."""
    try:
        md = open(REF_MD, encoding="utf-8").read()
    except OSError:
        return []
    m = re.search(r"^## Tested and rejected.*?\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    if not m:
        return []
    out, cur = [], None
    for ln in m.group(1).splitlines():
        if ln.startswith("- "):
            cur = [ln[2:].strip()]
            out.append(cur)
        elif cur is not None and ln.startswith("  ") and ln.strip():
            cur.append(ln.strip())
    rows = []
    for parts in out:
        t = " ".join(parts).replace("`", "")
        t = re.sub(r"\(([^()]*(?:\.md|\.py|\.json|runs? |tools/)[^()]*)\)", "", t)
        t = t.replace("**", "")
        t = re.sub(r"\s+", " ", t).strip()
        mm = re.match(r"^(.{8,110}?)\s*[:.;]\s+(.*)$", t)
        title, text = (mm.group(1), mm.group(2)) if mm else (t[:60], t)
        title = re.sub(r"\s*\([^)]*\)?", "", title).strip(" -:")[:60]
        text = re.sub(r"^-\s+", "", text)
        text = re.sub(r"^[^():]{0,60}\):\s*", "", text)
        text = text if len(text) <= 260 else text[:257].rsplit(" ", 1)[0] + "..."
        if title.lower().startswith("all variants") or len(text) < 12:
            continue
        rows.append({"title": title, "text": text})
    return rows


def build():
    scen, refs_needed = [], set()
    for sid, run_id, dials, label, ref, sel in SCENARIOS:
        path = os.path.join(rl.RUNS, run_id + ".json")
        if not os.path.exists(path):
            raise SystemExit(f"missing stored run {run_id} (research/runs/{run_id}.json)")
        run = rl.load(run_id)
        sp = run["spans"]
        scen.append({
            "id": sid, "run": run_id, "label": label, "dials": dials, "ref": ref, "selectable": sel,
            "base_confirm": (run["params"] or {}).get("cisd1m"),
            "h1": _slim(_cut(run, *H1)), "h2": _slim(_cut(run, *H2)), "y26": _slim(_cut(run, *Y26)),
            "stored26": _slim(sp["2026"]), "ref2125": {"net": sp["2021-25"].get("net"), "pf": sp["2021-25"].get("pf"), "tpw": sp["2021-25"].get("tpw")},
            "title": run.get("title"), "status": run.get("status"),
        })
    ids = {s["id"] for s in scen}
    for s in scen:
        if s["ref"] and s["ref"] not in ids:
            raise SystemExit(f"{s['id']}: unknown ref {s['ref']}")
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    sz = lm.get("lit_sizing") or {}
    live_note = f"live_model.json lit_sizing: {sz.get('mode')} room_f {(sz.get('two_week') or {}).get('room_f')}"
    return {
        "v": 1, "app": "hephaestus", "demo": False, "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "about": "Stored 2026 results of the LIT strategy settings that were really run (research/runs/). The page never runs the strategy.",
        "halves": {"h1": "Jan-Jun 2026 (pick)", "h2": "Jul-Oct 2026 (check)"},
        "dials": DIALS, "live": LIVE, "live_id": "live", "live_note": live_note, "scenarios": scen, "rejected": _rejected(),
        "sources": sorted({s["run"] for s in scen}) + ["docs/TESTED_AND_REJECTED.md"],
    }


def _siblings(doc):
    """fixture.json (a recorded sample, DEMO badge, used when data.json is missing) and jarvis.json (the Jarvis card), next to data.json."""
    folder = os.path.dirname(OUT)
    keep = {"live", "two_week", "uprisk", "no_cut", "twin"}
    fx = {**doc, "demo": True, "about": "A recorded sample of data.json (DEMO): " + doc["about"], "scenarios": [s for s in doc["scenarios"] if s["id"] in keep],
          "rejected": doc["rejected"][:4], "sources": []}
    with open(os.path.join(folder, "fixture.json"), "w", encoding="utf-8") as fh:
        json.dump(fx, fh, separators=(",", ":"))
    live = next(s for s in doc["scenarios"] if s["id"] == doc["live_id"])
    money = lambda v: ("-$" if v < 0 else "$") + f"{abs(round(v)):,}"
    card = {"v": 1, "name": "Hephaestus", "status": {"level": "ok", "label": "Read-only workshop"},
            "kpis": [{"label": "2026 net (live)", "value": money(live["y26"]["net"])}, {"label": "Jul-Oct PF", "value": f"{live['h2']['pf']:.2f}"},
                     {"label": "Trades / week", "value": f"{live['y26']['tpw']:.2f}"}],
            "lines": ["Turn a dial: stored 2026 results, Jan-Jun against Jul-Oct.", "It changes nothing in the bot."],
            "t": int(dt.datetime.now().timestamp()), "open": "#dials", "theme": "#0b0608", "stale_after": 2592000}
    with open(os.path.join(folder, "jarvis.json"), "w", encoding="utf-8") as fh:
        json.dump(card, fh, indent=1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    doc = build()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    if os.path.abspath(a.out) == os.path.abspath(OUT):
        _siblings(doc)
    print(f"hephaestus: {len(doc['scenarios'])} stored settings, {len(doc['rejected'])} rejected notes -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
