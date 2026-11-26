"""Market Learn, the weekly loop (Sunday after the Friday close; engine/market_learn.py says what and why).

Research only: hashes the live files before and after and fails loudly if one changed (it never writes them).

    python -X utf8 tools/market_learn_weekly.py --seed        # rebuild the backtests -> lessons + insights, NO fixes tested
    python -X utf8 tools/market_learn_weekly.py               # the weekly run: rebuild, add live/paper, lessons, <= 2 fixes a pillar
    python -X utf8 tools/market_learn_weekly.py --no-rebuild  # reuse research/learn/seed_trades (fast)
    python -X utf8 tools/market_learn_weekly.py --no-decide   # test, but put nothing on the Decide card
    python -X utf8 tools/market_learn_weekly.py --nightly     # LIGHT (< 2 min, no numba, no backtest): journal + brain state only
    python -X utf8 tools/market_learn_weekly.py --nightly --out logs/learning   # the PC: write outside the git tree
    python -X utf8 tools/market_learn_weekly.py --nightly --ideamill 200        # + 200 new idea-mill ideas (tools/ideamill.py)
Outputs: research/learn/lessons.jsonl.gz, knowledge.json, insights.json, trials.json, WHAT_WE_KNOW.md, weekly/<date>.json,
journal.json + brain_state.json (the Brain app feed, shape in research/learn/BRAIN_FEED.md; every run, weekly and nightly).
Tests: python -X utf8 -m tests.test_market_learn
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import market_learn as M  # noqa: E402

PC_DAYS = os.path.join(ROOT, "data", "pc_days")


def rebuild(seed_dir: str = M.SEED_DIR, say=print) -> bool:
    """The three backtests again (tools/win_loss_anatomy.build into research/learn/seed_trades). False if one failed."""
    try:
        import tools.win_loss_anatomy as W
        old = W.OUT_DIR
        W.OUT_DIR = seed_dir
        try:
            W.build(say=say)
        finally:
            W.OUT_DIR = old
        return True
    except Exception as ex:  # noqa: BLE001
        say(f"rebuild failed ({ex.__class__.__name__}: {str(ex)[:120]}); using the tables already in {seed_dir}")
        return False


def live(book: dict, days_dir: str = PC_DAYS, say=print) -> list:
    if not os.path.isdir(days_dir):
        say(f"no live / paper day folders here ({os.path.relpath(days_dir, ROOT)} missing): 0 live rows this week")
        return []
    from engine import datapipe, zeus_learn as Z
    rows = M.live_rows(datapipe.load_days(days_dir, n=400), book, Z.vix_closes(ROOT))
    say(f"live / paper rows from the PC's day folders: {len(rows)}")
    return rows


def run(a, say=print, root: str = ROOT) -> dict:
    before = M.hashes(root)
    if not a.no_rebuild:
        rebuild(say=say)
    book = M.daily_book(root)
    rows = M.seed_rows(book=book)
    if not rows:
        raise SystemExit("no backtest tables in research/learn/seed_trades: run without --no-rebuild")
    old_live = [r for r in M.load_lessons() if r.get("span") == "live"]
    rows = M.merge(rows, old_live)
    rows = M.merge(rows, live(book, say=say))
    M.structure_tags(rows)                              # the STRUCTURE lens (st_* tags), stored with the rows
    M.save_lessons(rows)
    doc = M.trials_doc()
    new = []
    if not a.seed:
        new = M.run_candidates(rows, doc)
        M._write_json(M.TRIALS, doc)                    # pre-registered BEFORE the test
        M.finish_trials(rows, doc, new)
    M._write_json(M.TRIALS, doc)
    K = M.build(rows, draws=a.draws, trials=doc, book=book)
    I = M.insights(K)
    I["phone_line"] = M.phone_line(new, K) if not a.seed else (M._read_json(M.INSIGHTS, {}) or {}).get("phone_line")
    M._write_json(M.KNOW, K)
    M._write_json(M.INSIGHTS, I)
    with open(M.SUMMARY_MD, "w", encoding="utf-8") as fh:
        fh.write(M.summary_md(K, I, doc))
    added = []
    props = M.decide_proposals(new)
    if props and not a.no_decide:
        from tools import learn_night as LN
        added = LN.step_decide(props, hide={"blitz"}).get("added", [])
    rep = {"day": dt.date.today().isoformat(), "seed": bool(a.seed), "rows": len(rows),
           "trials": [{k: t.get(k) for k in ("key", "status")} | {"why": (t.get("result") or {}).get("why")} for t in new],
           "decide_added": added, "phone_line": I["phone_line"]}
    br = M.nightly(root, out_dir=a.out, rows=rows, trials=doc, draws=0)
    rep["journal_added"] = len(br["added"])
    M._write_json(os.path.join(M.OUT, "weekly", f"{rep['day']}{'-seed' if a.seed else ''}.json"), rep)
    after = M.hashes(root)
    if after != before:
        raise SystemExit(f"A LIVE FILE CHANGED during the run: {[k for k in before if before[k] != after[k]]}")
    brain_words(br, say)
    for p in M.PILLARS:
        say(f"== {M.NAME[p]}")
        for s in M.knows_words(K, p):
            say("  " + s)
    for s in I["shared"]:
        say("  shared: " + s)
    for t in new:
        say(f"  fix {t['key']}: {t['status']} {'; '.join((t.get('result') or {}).get('why') or [])}")
    if I["phone_line"]:
        say(I["phone_line"])
    return rep


def brain_words(br: dict, say=print) -> None:
    S = br["brain"]
    say(f"MARKET NOW: {(S.get('market') or {}).get('words')}")
    for p, x in S["pillars"].items():
        say(f"  {x['name']}: confidence {x['confidence']}/100, {x['lessons']} confirmed, {x['watching']} watching, "
            f"{x['rejected']} rejected | next: {x['testing_next']}")
    for e in br["added"][:12]:
        say(f"  + {e['date']} [{e['status']}] {e['pillar']}: {e['noticed']}")
    say(f"journal: {len(br['journal'])} entries, {len(br['added'])} new or changed today")


def nightly(a, say=print, root: str = ROOT) -> dict:
    """Light mode: no backtest rebuild, no candidate tests, no numba; the stored rows + this week's live rows + the bars."""
    import time
    t0 = time.time()
    before = M.hashes(root)
    rows = M.load_lessons()
    if not rows:
        raise SystemExit("no research/learn/lessons.jsonl.gz yet: run the weekly seed first (tools/market_learn_weekly.py --seed)")
    book = M.daily_book(root)
    if getattr(a, "ideamill", 0):                       # optional: the idea mill's nightly batch (off by default; needs numba)
        try:
            from tools import ideamill as IM
            IM.batch(a.ideamill, cap_s=60 * a.ideamill_cap, say=say,
                     journal=os.path.join(a.out or M.OUT, "journal.json"))
        except Exception as ex:  # noqa: BLE001
            say(f"idea mill skipped ({ex.__class__.__name__}: {str(ex)[:120]})")
    if getattr(a, "forecast", False):                   # optional: eval pass forecaster (tools/forecast.py; numba + the board)
        try:
            from tools import forecast as FC
            if a.out:
                FC.OUT = os.path.join(a.out, "forecast.json")
            FC.run(n=1000, say=say)
        except Exception as ex:  # noqa: BLE001
            say(f"forecast skipped ({ex.__class__.__name__}: {str(ex)[:120]})")
    if getattr(a, "health", False):                     # optional: strategy health bands (tools/health_bands.py)
        try:
            from tools import health_bands as HB
            if a.out:
                HB.OUT = os.path.join(a.out, "bands.json")
            HB.run(say=say)
        except Exception as ex:  # noqa: BLE001
            say(f"health bands skipped ({ex.__class__.__name__}: {str(ex)[:120]})")
    br = M.nightly(root, out_dir=a.out, rows=rows, live_rows=live(book, say=say))
    if M.hashes(root) != before:
        raise SystemExit("A LIVE FILE CHANGED during the nightly run")
    brain_words(br, say)
    say(f"nightly done in {time.time() - t0:.0f} s -> {os.path.relpath(a.out or M.OUT, root)}")
    return br


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="lessons + insights only, no candidate fixes")
    ap.add_argument("--no-rebuild", action="store_true")
    ap.add_argument("--no-decide", action="store_true")
    ap.add_argument("--draws", type=int, default=M.CHANCE_DRAWS)
    ap.add_argument("--nightly", action="store_true", help="light: journal + brain state only (< 2 min, no numba)")
    ap.add_argument("--out", default=None, help="folder for journal.json + brain_state.json (default research/learn)")
    ap.add_argument("--ideamill", type=int, default=0, help="--nightly: also score N new idea-mill ideas (0 = off)")
    ap.add_argument("--ideamill-cap", type=float, default=20, help="minutes cap for the idea-mill step")
    ap.add_argument("--forecast", action="store_true", help="--nightly: also rebuild research/forecast/forecast.json")
    ap.add_argument("--health", action="store_true", help="--nightly: also rebuild research/health/bands.json")
    a = ap.parse_args(argv)
    if a.out:
        a.out = os.path.join(ROOT, a.out) if not os.path.isabs(a.out) else a.out
    nightly(a) if a.nightly else run(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
