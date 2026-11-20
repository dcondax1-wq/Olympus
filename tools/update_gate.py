"""Update gate (idea #11, day-speed 2026-11-20): replay the PC's last CME sessions through the CURRENT code and a CANDIDATE
commit, and flag any change in LIT / ATLAS entries, sizes, stops, targets or exits that no model / sizing file change
explains. REPORT ONLY: it never holds, merges, restarts or trades anything (engine/autoupdate.py may call it later).

    python -X utf8 tools/update_gate.py --candidate origin/pc                 # base = HEAD (the code the PC runs now)
    python -X utf8 tools/update_gate.py --base <sha> --candidate <sha> [--sessions 10] [--json out.json]

How: two scratch git worktrees (base, candidate), each runs research/speed/replay_harness.py (copied from THIS checkout, so
the harness is the same for both) with --atlas-funded on the SAME data dir (this checkout's data/: the TradingView exports +
the PC's imported NinjaTrader bars). The harness runs the real engine.live.LiveBot (paper, frozen clock, data_source
ninjatrader) on LE_BarFeed-format files that grow bar by bar, so the candidate's bar reading, merge, model, sizing and
routing are all exercised. Polls: every minute 01:30-12:00 ET, every 5 minutes otherwise.

Verdict (exit code):  0 SAME              no trade differs (route seconds may)
                      0 EXPLAINED         trades differ AND a model / sizing file changed (MODEL_FILES): expected, review
                      2 HOLD              trades differ and no model / sizing file changed: do not take this commit
                      1 ERROR             a replay failed (also: a poll raised in one version only)
Tests: python -X utf8 -m tests.test_update_gate
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(ROOT, "research", "speed")
ET = ZoneInfo("America/New_York")
# a change in one of these is a deliberate strategy / sizing change: trade differences are "explained" (still listed)
MODEL_FILES = ("live_model.json", "live_model_lit.json", "live_model_*.json", "second_model.json", "accounts/*.json",
               "engine/sizing.py")
TRADE_KEYS = ("side", "qty", "stop", "target", "pnl", "reason")


# ------------------------------------------------------------------------------------------------ pieces (unit-tested)
def model_files_changed(changed: list) -> list:
    return sorted(f for f in changed if any(fnmatch.fnmatch(f, pat) for pat in MODEL_FILES))


def last_sessions(times, n: int, end_day: str | None = None) -> list:
    """The last n CME weekday sessions (ET trading date of bars 01:30-12:00 ET) present in the 1m bar times."""
    days = set()
    for t in times:
        e = dt.datetime.fromtimestamp(int(t), ET)
        if e.weekday() < 5 and 90 <= e.hour * 60 + e.minute < 720:
            days.add(e.strftime("%Y-%m-%d"))
    out = sorted(d for d in days if end_day is None or d <= end_day)
    return out[-n:] if n > 0 else out


def _rows(ledger) -> dict:
    """(book, entry_t, side-kind) -> the trade fields (route time 't' left out: speed changes may move it)."""
    out = {}
    for book, rows in ledger.items():
        for r in rows or []:
            kind = "exit" if r.get("side") == "exit" else ("entry" if r.get("side") in ("buy", "sell") else str(r.get("side")))
            k = (book, int(r.get("entry_t") or 0), kind)
            out[k] = {f: r.get(f) for f in TRADE_KEYS}
    return out


def compare(base: dict, cand: dict) -> dict:
    """base / cand: replay_harness results. -> {"trades": [differences], "polls": n, "state_diff_polls": n, "errors": {...}}"""
    a = _rows({"LIT": base.get("ledger"), "ATLAS": base.get("ledger_atlas")})
    b = _rows({"LIT": cand.get("ledger"), "ATLAS": cand.get("ledger_atlas")})
    diffs = []
    for k in sorted(set(a) | set(b), key=lambda x: (x[1], x[0], x[2])):
        ra, rb = a.get(k), b.get(k)
        if ra == rb:
            continue
        et = dt.datetime.fromtimestamp(k[1], ET).strftime("%Y-%m-%d %H:%M ET") if k[1] else "?"
        what = "only in candidate" if ra is None else "only in base" if rb is None else \
            ", ".join(f"{f} {ra.get(f)} -> {rb.get(f)}" for f in TRADE_KEYS if ra.get(f) != rb.get(f))
        diffs.append({"book": k[0], "entry": et, "kind": k[2], "what": what, "base": ra, "candidate": rb})
    sa = [r.get("state") for r in base.get("rows") or []]
    sb = [r.get("state") for r in cand.get("rows") or []]
    state_diff = sum(1 for x, y in zip(sa, sb) if x != y) + abs(len(sa) - len(sb))
    return {"trades": diffs, "polls": len(sb), "state_diff_polls": state_diff,
            "errors": {"base": base.get("n_errors", 0), "candidate": cand.get("n_errors", 0)}}


def verdict(cmp: dict, model_changed: list) -> tuple:
    if cmp["errors"]["candidate"] > cmp["errors"]["base"]:
        return "ERROR", 1, f"the candidate's poll raised {cmp['errors']['candidate']} times (base {cmp['errors']['base']})"
    if not cmp["trades"]:
        extra = f"; LIT state differs on {cmp['state_diff_polls']} polls (no trade changed)" if cmp["state_diff_polls"] else ""
        return "SAME", 0, f"no trade differs on {cmp['polls']} polls{extra}"
    n = len(cmp["trades"])
    if model_changed:
        return "EXPLAINED", 0, f"{n} trade line(s) differ and model / sizing files changed ({', '.join(model_changed)}): review them"
    return "HOLD", 2, f"{n} trade line(s) differ with NO model / sizing file change: do not take this commit"


# ------------------------------------------------------------------------------------------------ git + replays
def git(*args, cwd=ROOT, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def worktree(sha: str, where: str) -> str:
    git("worktree", "add", "--detach", "--force", where, sha)
    dst = os.path.join(where, "research", "speed")
    os.makedirs(dst, exist_ok=True)
    for f in ("replay_harness.py", "speedups.py"):
        shutil.copy(os.path.join(HARNESS, f), os.path.join(dst, f))
    return where


def replay(wt: str, days: list, out: str, data_dir: str, max_polls=None, timeout=7200) -> dict:
    cmd = [sys.executable, "-X", "utf8", os.path.join(wt, "research", "speed", "replay_harness.py"), "--atlas-funded",
           "--days", ",".join(days), "--out", out]
    if max_polls:
        cmd += ["--max-polls", str(int(max_polls))]
    env = {**os.environ, "SPEED_DATA_DIR": data_dir, "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("LE_LIVE_MODEL", None)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=wt, env=env, capture_output=True, text=True, timeout=timeout)
    if r.returncode or not os.path.exists(out):
        raise RuntimeError(f"replay failed in {wt}: {(r.stderr or r.stdout)[-600:]}")
    with open(out, encoding="utf-8") as fh:
        res = json.load(fh)
    res["seconds"] = round(time.time() - t0)
    return res


def run_gate(base: str, cand: str, sessions: int = 10, days=None, max_polls=None, keep=False, data_dir=None) -> dict:
    import pandas as pd
    data_dir = data_dir or os.path.join(ROOT, "data")
    bsha, csha = git("rev-parse", base), git("rev-parse", cand)
    changed = [f for f in git("diff", "--name-only", bsha, csha).splitlines() if f]
    mchg = model_files_changed(changed)
    if days is None:
        t = pd.read_csv(os.path.join(data_dir, "NQ_1m.csv"), usecols=["time"])["time"].values
        days = last_sessions(t, sessions)
    tmp = tempfile.mkdtemp(prefix="update_gate_")
    out = {"base": bsha, "candidate": csha, "days": days, "files_changed": len(changed), "model_files_changed": mchg}
    try:
        wb, wc = worktree(bsha, os.path.join(tmp, "base")), worktree(csha, os.path.join(tmp, "cand"))
        with cf.ThreadPoolExecutor(2) as ex:
            fb = ex.submit(replay, wb, days, os.path.join(tmp, "base.json"), data_dir, max_polls)
            fc = ex.submit(replay, wc, days, os.path.join(tmp, "cand.json"), data_dir, max_polls)
            rb, rc = fb.result(), fc.result()
        cmp = compare(rb, rc)
        v, code, why = verdict(cmp, mchg)
        out.update({"verdict": v, "exit": code, "why": why, "trades": cmp["trades"], "polls": cmp["polls"],
                    "state_diff_polls": cmp["state_diff_polls"], "errors": cmp["errors"],
                    "base_trades": len(rb.get("ledger") or []) + len(rb.get("ledger_atlas") or []),
                    "seconds": {"base": rb.get("seconds"), "candidate": rc.get("seconds")},
                    "poll_ms_median": {"base": (rb.get("summary") or {}).get("wall_median_ms"),
                                       "candidate": (rc.get("summary") or {}).get("wall_median_ms")}})
    except Exception as e:                                       # noqa: BLE001
        out.update({"verdict": "ERROR", "exit": 1, "why": f"{e.__class__.__name__}: {e}"})
    finally:
        if not keep:
            for w in ("base", "cand"):
                git("worktree", "remove", "--force", os.path.join(tmp, w), check=False)
            git("worktree", "prune", check=False)
            shutil.rmtree(tmp, ignore_errors=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -X utf8 tools/update_gate.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--sessions", type=int, default=10)
    ap.add_argument("--days", help="comma list instead of the last --sessions sessions")
    ap.add_argument("--max-polls", type=int, help="tests only")
    ap.add_argument("--data-dir", help="bars to replay (default: this checkout's data/)")
    ap.add_argument("--json")
    ap.add_argument("--keep", action="store_true", help="keep the scratch worktrees (debugging)")
    a = ap.parse_args(argv)
    res = run_gate(a.base, a.candidate, a.sessions, a.days.split(",") if a.days else None, a.max_polls, a.keep, a.data_dir)
    print(f"  update gate: {res['verdict']}  {res.get('why', '')}")
    print(f"  base {res['base'][:10]} -> candidate {res['candidate'][:10]}, sessions {', '.join(res.get('days') or [])}")
    for d in res.get("trades") or []:
        print(f"    {d['book']:<5} {d['entry']}  {d['kind']:<5} {d['what']}")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, default=str)
    return int(res.get("exit", 1))


if __name__ == "__main__":
    raise SystemExit(main())
