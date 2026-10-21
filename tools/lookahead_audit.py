"""Automatic look-ahead check on stored research runs (competitor-features #14, 2026-10-21).

For each stored LIT run (research/runs/<id>.json whose params carry the LIT "ref"), its top trades (largest $, default 3)
are re-checked the way tests/test_trade_intel.py and tests/test_lit_lookahead.py do it:
  1. replay  the run's params on a window (5 months before the trade's month to the end of the data); the trade must be
             there (same day, entry time, side). If not, the run used an executor beyond engine/lit.py run_x (a size tilt, a
             research-only option) and the trade is "not replayable": skipped, never flagged.
  2. cut     the 5m bars at the setup's entry bar (that bar reduced to its open: it has just started), rebuild the market +
             setups on the cut window, and compare every field of the setup (sweep, extreme, CISD level, inducement,
             displacement, targets, VIX room, ...) and the live signal (limit / stop / target / R:R) with the full window.
A run whose numbers change on the cut data is flagged (look-ahead). Results -> research/lab/lookahead_audit.json (a badge per
run in the Lab and the Performance page).

  python -X utf8 tools/lookahead_audit.py                 # every LIT run, top 3 trades each (cached per params + trade)
  python -X utf8 tools/lookahead_audit.py --runs a,b --top 5
  python -X utf8 tools/lookahead_audit.py --recent 40     # the 40 newest runs only
Hook: LE_LOOKAHEAD=1 makes tools/runlib.py save() check the run it just stored (sampled, 3 trades) and update the report.
Read-only research: changes no run and no engine code. One CPU process.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "lookahead_audit.json")
RUNS = os.path.join(ROOT, "research", "runs")
VERSION = 1
SIG_FIELDS = ("limit_px", "stop_px", "target_px", "risk_pts", "rr", "target_label", "swept", "how")

_W = {}          # (start, ref, boxes) -> (B, Mf, Cf, B1)
_BARS = {}


def _norm(z):
    return json.dumps(z, sort_keys=True, default=str)


def _bars():
    if "b" not in _BARS:
        from engine.data import load
        _BARS["b"] = load("NQ", "5m")
        _BARS["ds"] = np.array(_BARS["b"].date_str)
    return _BARS["b"], _BARS["ds"]


def _start_of(day):
    d = dt.date.fromisoformat(day)
    m = d.month - 5
    y = d.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}-01"


def window(day, P):
    from engine import lit
    st = _start_of(day)
    key = (st, P["ref"], tuple(P.get("extra_boxes") or ()))
    if key not in _W:
        b, ds = _bars()
        a = int(np.searchsorted(ds, st))
        B = b.slice(a, len(b))
        M = lit.Market(bars=B, extra_boxes=P["extra_boxes"])
        C = lit.candidates(M, ref=P["ref"])
        B1 = lit.bars_1m(M) if P.get("tf") == "1m" and day >= "2026-01-01" else None
        if len(_W) > 6:
            _W.pop(next(iter(_W)))
        _W[key] = (B, M, C, B1)
    return _W[key]


def params_of(run):
    from engine import lit
    p = run.get("params") or {}
    if "ref" not in p:
        return None
    return {**lit.DEFAULTS, **{k: v for k, v in p.items() if k in lit.DEFAULTS}}


def _phash(P):
    return hashlib.sha1(_norm(P).encode()).hexdigest()[:10]


def check_trade(P, day, entry_t, d, cache=None):
    """One trade: {"status": ok | changed | not_replayable, "diff": [...]}."""
    from engine import lit
    from tests.test_lit_lookahead import _cut
    ck = (_phash(P), day, int(entry_t), int(d))
    if cache is not None and f"{ck}" in cache:
        return cache[f"{ck}"]
    B, Mf, Cf, B1 = window(day, P)
    T = lit.run_x(Mf, Cf, P, [day], B1=B1, B5=lit.bars_5m(Mf))
    t = next((x for x in T if int(x["entry_t"]) == int(entry_t) and int(x["dir"]) == int(d)), None)
    if t is None:
        res = {"status": "not_replayable", "diff": ["the run's params do not give this trade on run_x (research executor)"]}
    else:
        z = next((z for z in Cf if z["i"] == t["i"] and z["dir"] == t["dir"]), None)
        if z is None:
            res = {"status": "not_replayable", "diff": ["setup not found"]}
        else:
            n = int(z["entry_i"])
            Mc = lit.Market(bars=_cut(B, n), extra_boxes=P["extra_boxes"])
            Cc = lit.candidates(Mc, ref=P["ref"])
            zc = next((x for x in Cc if x["i"] == z["i"] and x["dir"] == z["dir"]), None)
            diff = []
            if zc is None:
                diff.append("setup missing on the cut data")
            else:
                diff += [f"setup.{f}" for f in sorted(z) if _norm(z[f]) != _norm(zc.get(f))]
                P5 = {**P, "tf": "5m"}
                sf = {(x["t"], x["dir"]): x for x in lit.run_live(Mf, [z], P5)["signals"]}
                sc = {(x["t"], x["dir"]): x for x in lit.run_live(Mc, [zc], P5)["signals"]}
                for k, x in sf.items():
                    y = sc.get(k)
                    if y is None:
                        diff.append("signal missing on the cut data")
                        continue
                    diff += [f"signal.{f}" for f in SIG_FIELDS if _norm(x.get(f)) != _norm(y.get(f))]
            res = {"status": "changed" if diff else "ok", "diff": diff[:12], "fields": len(z) + len(SIG_FIELDS)}
    if cache is not None:
        cache[f"{ck}"] = res
    return res


def top_trades(run, top=3):
    c = run.get("trade_cols") or []
    if not run.get("trades") or "pnl" not in c:
        return []
    ix = {k: c.index(k) for k in ("day", "entry_t", "dir", "pnl")}
    rows = sorted(run["trades"], key=lambda r: -(r[ix["pnl"]] or 0))
    out, days = [], set()
    for r in rows:
        if r[ix["day"]] in days:
            continue
        days.add(r[ix["day"]])
        out.append({"day": r[ix["day"]], "entry_t": int(r[ix["entry_t"]]), "dir": int(r[ix["dir"]]), "pnl": r[ix["pnl"]]})
        if len(out) >= top:
            break
    return out


def check_run(rid, top=3, cache=None):
    run = json.load(open(os.path.join(RUNS, rid + ".json"), encoding="utf-8"))
    P = params_of(run)
    if P is None:
        return {"id": rid, "status": "not_lit", "checked": 0, "changed": 0, "skipped": 0}
    rows = []
    for t in top_trades(run, top):
        try:
            r = check_trade(P, t["day"], t["entry_t"], t["dir"], cache)
        except Exception as e:
            r = {"status": "error", "diff": [f"{e.__class__.__name__}: {str(e)[:120]}"]}
        rows.append({**t, **r})
    ok = sum(1 for r in rows if r["status"] == "ok")
    ch = sum(1 for r in rows if r["status"] == "changed")
    sk = sum(1 for r in rows if r["status"] in ("not_replayable", "error"))
    status = "flag" if ch else "ok" if ok else "skip"
    return {"id": rid, "status": status, "checked": ok + ch, "changed": ch, "skipped": sk, "built": run.get("built"),
            "title": run.get("title"), "trades": rows}


def badge(r):
    if not r:
        return None
    if r["status"] == "ok":
        return f"look-ahead check ok ({r['checked']} top trades, 0 changed)"
    if r["status"] == "flag":
        return f"look-ahead check FAILED: {r['changed']} of {r['checked']} top trades change on cut data"
    if r["status"] == "skip":
        return "look-ahead check skipped (the run's trades need a research executor beyond run_x)"
    return None


def load():
    try:
        with open(OUT, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write(rep):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    R = rep["runs"]
    rep["summary"] = {"runs": len(R), "ok": sum(1 for r in R.values() if r["status"] == "ok"),
                      "flag": sum(1 for r in R.values() if r["status"] == "flag"),
                      "skip": sum(1 for r in R.values() if r["status"] == "skip"),
                      "not_lit": sum(1 for r in R.values() if r["status"] == "not_lit"),
                      "trades_checked": sum(r["checked"] for r in R.values()),
                      "trades_changed": sum(r["changed"] for r in R.values()),
                      "flagged": sorted(k for k, r in R.items() if r["status"] == "flag")}
    s = rep["summary"]
    rep["summary"]["text"] = (f"{s['ok']} LIT runs pass the look-ahead check ({s['trades_checked']} top trades re-built on data cut at "
                              f"the entry bar, {s['trades_changed']} changed); {s['flag']} flagged, {s['skip']} skipped (research "
                              f"executor), {s['not_lit']} older engine runs not checked.")
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, separators=(",", ":"), default=str)
    os.replace(tmp, OUT)
    return rep


def hook(rid, top=3):
    """tools/runlib.py save() (LE_LOOKAHEAD=1): check the run just stored and update the report. Never raises."""
    try:
        rep = load() or {"v": VERSION, "runs": {}, "cache": {}}
        rep["runs"][rid] = check_run(rid, top, rep.setdefault("cache", {}))
        rep["built"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        write(rep)
        return rep["runs"][rid]
    except Exception as e:
        print(f"lookahead hook ({rid}): {e.__class__.__name__}: {e}")
        return None


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--recent", type=int, default=0)
    a = ap.parse_args(argv)
    t0 = time.time()
    ix = json.load(open(os.path.join(RUNS, "index.json"), encoding="utf-8"))
    rows = ix.get("runs") or []
    ids = [x.strip() for x in a.runs.split(",") if x.strip()] or [r["id"] for r in rows]
    if a.recent:
        ids = [r["id"] for r in sorted(rows, key=lambda r: r.get("built") or "", reverse=True) if r["id"] in set(ids)][:a.recent]
    rep = load() or {}
    if rep.get("v") != VERSION:
        rep = {}
    rep.setdefault("runs", {})
    cache = rep.setdefault("cache", {})
    # newest first, 2026 windows first (one window build serves most runs)
    for n, rid in enumerate(ids):
        try:
            rep["runs"][rid] = check_run(rid, a.top, cache)
        except Exception as e:
            rep["runs"][rid] = {"id": rid, "status": "skip", "checked": 0, "changed": 0, "skipped": 0, "error": str(e)[:160]}
        r = rep["runs"][rid]
        if r["status"] == "flag" or n % 50 == 0:
            print(f"[{n + 1}/{len(ids)}] {rid}: {r['status']} {r.get('checked')}/{r.get('changed')} {time.time() - t0:.0f}s", flush=True)
        if n % 100 == 99:
            rep.update({"v": VERSION, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
            write(rep)
    rep.update({"v": VERSION, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "top": a.top,
                "seconds": round(time.time() - t0),
                "method": "Top trades per run re-built on 5m data cut at the setup's entry bar (that bar reduced to its open); every "
                          "setup field and the live signal (limit / stop / target / R:R) must equal the full-data values. A trade the "
                          "run's params do not give on engine/lit.py run_x is skipped (research executor)."})
    write(rep)
    print(rep["summary"]["text"], f"({time.time() - t0:.0f}s)")
    return 1 if rep["summary"]["flag"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
