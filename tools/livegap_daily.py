"""Nightly LIVE-vs-TWIN audit (day-batch6, 2026-11-26). READ ONLY RESEARCH: never trades, routes, sizes or edits live code /
live_model*.json. Runs tools/livegap.audit() (the backtest twin on the PC's own bars vs the live rows: trades.json + the pulled
data/pc_days) and turns it into one row per account per day, so drift is caught the next morning:

  research/livegap/daily.json      every account x day since its start: twin trades / $ vs live trades / $, and the differences
  research/livegap/journal.jsonl   ONE line per difference, appended once (key = account | day | when | kind; re-runs never
                                   duplicate): MISSED (twin traded, live did not), SLIPPED ($ vs the twin at the live size, >= $5),
                                   SIZE (live micros != the twin's eval-path micros), EXTRA (a live trade with no twin trade)

    python -X utf8 tools/livegap_daily.py              # after tools/data_pull.py --latest (learn_night's "livegap" step)
    python -X utf8 tools/livegap_daily.py --dry-run    # print the new journal lines, write nothing
Tests: python -X utf8 -m tests.test_livegap_daily (fake audit, no data).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT_DIR = os.path.join(ROOT, "research", "livegap")
DAILY = os.path.join(OUT_DIR, "daily.json")
JOURNAL = os.path.join(OUT_DIR, "journal.jsonl")
SLIP_MIN = 5.0          # $: smaller entry / exit differences are inside the cost model (1 tick + $1.90 a micro)
BOT_ACCT = {"LIT": "z50k", "ATLAS": "atlas25"}
ACCT_OF_ROW = {"zlarior": "z50k", "acctb": "atlas25", "atlas": "atlas25"}


def diffs_of(key, r):
    """One audit trade row -> its differences [(kind, usd, detail)]."""
    parts = r.get("parts") or {}
    out = []
    for c, v in parts.items():
        if c.startswith("MISSED"):
            out.append(("MISSED", round(float(v), 2), r.get("cause", "")))
    if r.get("live_qty"):
        s = float(parts.get("SLIPPED") or 0.0)
        if abs(s) >= SLIP_MIN:
            out.append(("SLIPPED", round(s, 2), f"live ${r.get('live_usd')} vs twin at the live size; entry slip "
                                                f"${r.get('entry_slip_usd', 'n/a')}"))
        tq = r.get("twin_qty")
        if tq is not None and int(r["live_qty"]) != int(tq):
            out.append(("SIZE", round(float(parts.get("SIZE") or 0.0), 2), f"live {r['live_qty']} micros vs twin {tq}"))
        elif tq is None and "SIZE" in parts and abs(float(parts["SIZE"])) >= SLIP_MIN:
            out.append(("SIZE", round(float(parts["SIZE"]), 2), r.get("cause", "")))
    return out


def extras(live_rows, twins, window=900):
    """Live trades with no twin trade of the same bot and direction within `window` seconds of the entry."""
    out = []
    for r in live_rows:
        if r.get("src") != "live" or r.get("bot") not in twins:
            continue
        d = 1 if r.get("side") == "LONG" else -1
        if any(abs(int(r["t"]) - int(t["entry_t"])) <= window and t["dir"] == d for t in twins[r["bot"]]):
            continue
        out.append(r)
    return out


def build(R, live_rows, twins, today=None):
    """R = livegap.audit(); -> (daily dict, journal lines)."""
    days = collections.defaultdict(lambda: {"twin_trades": 0, "twin_usd": 0.0, "live_trades": 0, "live_usd": 0.0, "diffs": []})
    lines = []
    for key, a in R["accounts"].items():
        for r in a.get("trades", []):
            if r.get("one_position_skip"):
                continue
            D = days[(key, r["day"])]
            D["twin_trades"] += 1
            D["twin_usd"] += float(r.get("twin_usd", r.get("twin_usd_est")) or 0.0)
            if r.get("live_qty"):
                D["live_trades"] += 1
                D["live_usd"] += float(r.get("live_usd") or 0.0)
            for kind, usd, why in diffs_of(key, r):
                j = {"account": key, "day": r["day"], "when": r["when"], "kind": kind, "usd": usd,
                     "bot": r.get("member") or "LIT", "side": r.get("side"), "detail": why}
                D["diffs"].append(j)
                lines.append(j)
    for r in extras(live_rows, twins):
        key = ACCT_OF_ROW.get(str(r.get("acct", "")).lower(), BOT_ACCT.get(r["bot"], "?"))
        D = days[(key, r["day"])]
        D["live_trades"] += 1
        D["live_usd"] += float(r.get("usd") or 0.0)
        j = {"account": key, "day": r["day"], "when": r.get("hm", ""), "kind": "EXTRA", "usd": round(float(r.get("usd") or 0.0), 2),
             "bot": r["bot"], "side": r.get("side"), "detail": f"live {r.get('q')} micros, no twin trade within 15 min"}
        D["diffs"].append(j)
        lines.append(j)
    rows = []
    for (key, day), D in sorted(days.items(), key=lambda x: (x[0][1], x[0][0])):
        rows.append({"account": key, "day": day, "twin_trades": D["twin_trades"], "twin_usd": round(D["twin_usd"], 2),
                     "live_trades": D["live_trades"], "live_usd": round(D["live_usd"], 2),
                     "gap_usd": round(D["live_usd"] - D["twin_usd"], 2), "diffs": D["diffs"]})
    last = max((r["day"] for r in rows), default=None)
    tot = collections.Counter()
    for j in lines:
        tot[j["kind"]] += j["usd"]
    daily = {"made": (today or dt.datetime.now().isoformat(timespec="minutes")), "bars_to": R.get("bars_to"),
             "pc_days_pulled": len(R.get("pc_days_pulled") or []), "last_day": last,
             "totals_usd_by_kind": {k: round(v, 2) for k, v in tot.items()},
             "accounts": {k: a.get("name") for k, a in R["accounts"].items()}, "rows": rows,
             "note": "gap_usd = live - twin; MISSED $ = minus the twin's $; EXTRA $ = the live trade's $. Read only."}
    return daily, lines


def jkey(j):
    return f"{j['account']}|{j['day']}|{j['when']}|{j['kind']}"


def append_new(lines, path=JOURNAL, stamp=None):
    seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    seen.add(json.loads(ln)["key"])
                except (ValueError, KeyError):
                    pass
    new = []
    for j in lines:
        k = jkey(j)
        if k not in seen:
            seen.add(k)
            new.append({"key": k, "logged": stamp or dt.datetime.now().isoformat(timespec="minutes"), **j})
    return new


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from tools import livegap as G
    memo = {}
    for nm in ("lit_twin", "atlas_twin"):
        f = getattr(G, nm)
        setattr(G, nm, (lambda f, nm: lambda *x, **k: memo.setdefault(nm, f(*x, **k)))(f, nm))
    R = G.audit()
    lit = memo["lit_twin"][0] if isinstance(memo.get("lit_twin"), tuple) else memo.get("lit_twin", [])
    twins = {"LIT": list(lit), "ATLAS": list(memo.get("atlas_twin") or [])}
    live_rows, _ = G.live_rows()
    daily, lines = build(R, live_rows, twins)
    new = append_new(lines)
    for j in new:
        print(f"NEW {j['kind']:7s} {j['account']:8s} {j['day']} {j['when']:>16s} {j['bot']:5s} ${j['usd']:+,.2f}  {j['detail'][:90]}")
    print(f"livegap daily: {len(daily['rows'])} account-days to {daily['last_day']} (bars to {daily['bars_to']}), "
          f"{len(lines)} differences, {len(new)} new; by kind {daily['totals_usd_by_kind']}")
    if a.dry_run:
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DAILY, "w", encoding="utf-8") as fh:
        json.dump(daily, fh, indent=1, default=str)
    with open(JOURNAL, "a", encoding="utf-8") as fh:
        for j in new:
            fh.write(json.dumps(j, default=str) + "\n")
    print(f"-> {os.path.relpath(DAILY, ROOT)}, {os.path.relpath(JOURNAL, ROOT)} (+{len(new)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
