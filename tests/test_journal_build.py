"""tools/journal_build.py (the auto trade journal) on PC-style ledger rows made from the 2026-10 LIT replay (research/lab/backtest_live.json)
and the real CME NQ 1m bars (data/NQ_1m.csv). Temp folders only: tools/web_public/journal/ and research/journal/ are never written.

    python -X utf8 -m tests.test_journal_build      (~10 s)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import journal_build as J  # noqa: E402
import pngchart  # noqa: E402

RES = []


def check(name, ok, info=None):
    RES.append((name, bool(ok)))
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + ("" if ok or info is None else f"  {str(info)[:300]}"))


def rows_from_replay(n=12):
    d = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))
    T = [t for t in d["trades"] if "2026-09-01" <= t["day"] <= "2026-10-16"][:n]
    rows = []
    for k, t in enumerate(T):
        q = int(t.get("qty_total") or t["qty"])
        side = "buy" if t["side"] == "LONG" else "sell"
        mode = "paper" if k == 0 else "sim"
        rows.append({"t": t["entry_t"], "sym": "MNQ", "side": side, "qty": q, "stop": t["stop"], "target": t["target"], "entry": t["entry"],
                     "entry_t": t["entry_t"], "result": {"ok": True, "adapter": "ninjatrader"}, "src": "main", "bot": "zlarior",
                     "acct": "...1234", "mode": mode})
        ex = {"t": t["exit_t"], "sym": "MNQ", "side": "exit", "qty": q, "reason": t["exit"], "pnl": t["pnl"], "entry_t": t["entry_t"],
              "exit_t": t["exit_t"], "src": "main", "bot": "zlarior", "acct": "...1234", "mode": mode}
        rows.append(ex)
        if k == 1:
            rows.append(dict(ex))                         # a duplicate exit row (state file + archive)
    rows.append({"t": 1795000000, "side": "buy", "qty": 3, "stop": 1.0, "target": 2.0, "entry": 1.5, "entry_t": 1795000000, "src": "main",
                 "bot": "zlarior", "mode": "sim", "result": {"ok": True}})          # still open: no exit row
    rows.append({"t": 1795000100, "side": "sell", "qty": 3, "stop": 1.0, "target": 2.0, "entry": 1.5, "entry_t": 1795000100, "src": "main",
                 "bot": "zlarior", "mode": "sim", "result": {"ok": False, "error": "REFUSED"}})   # refused entry
    return T, rows


def main() -> int:
    check("glyphs: every PNG letter is 5x7", all(len(v) == 35 for v in pngchart._G.values()), [k for k, v in pngchart._G.items() if len(v) != 35])
    T, rows = rows_from_replay()
    with tempfile.TemporaryDirectory() as d:
        rf = os.path.join(d, "rows.jsonl")
        with open(rf, "w") as fh:
            fh.write("\n".join(json.dumps(r) for r in rows))
        out, wk = os.path.join(d, "journal"), os.path.join(d, "weeks")
        doc = J.build(rf, os.path.join(ROOT, "data", "NQ_1m.csv"), out, wk, include_paper=False)
        E = doc["trades"]
        check(f"pairing: {len(T) - 1} real trades (paper, open, refused left out; duplicate exit counted once)", len(E) == len(T) - 1,
              [x["id"] for x in E])
        by = {x["entry_et"]: x for x in E}
        bad_r, bad_u = [], []
        for t in T[1:]:
            x = [y for y in E if y["entry"] == t["entry"] and y["usd"] == round(t["pnl"], 2)]
            if not x:
                bad_u.append(t["day"])
                continue
            x = x[0]
            want = t["pnl"] / (int(t.get("qty_total") or t["qty"]) * t["risk_pts"] * 2.0)
            if abs((x["r"] or 0) - want) > 0.011:
                bad_r.append((t["day"], x["r"], round(want, 3)))
        check("$ = the ledger's exit pnl (duplicate exit not double-counted)", not bad_u, bad_u)
        check("R = $ / (micros x stop pts x $2)", not bad_r, bad_r)
        ok_mfe = [x for x in E if x["mfe_r"] is not None and x["mae_r"] is not None]
        check(f"MAE / MFE from 1m bars on {len(ok_mfe)}/{len(E)} trades, MFE >= the R banked by a winner",
              len(ok_mfe) == len(E) and all(x["mfe_r"] >= (x["r"] or 0) - 0.15 for x in E if x["usd"] > 0),
              [(x["id"], x["mfe_r"], x["r"]) for x in E if x["usd"] > 0 and x["mfe_r"] < x["r"] - 0.15])
        stp = [x for x in E if x["exit"] == "STOP"]
        check(f"a stopped trade went >= ~1R against ({len(stp)} stops)", all((x["mae_r"] or 0) >= 0.9 for x in stp),
              [(x["id"], x["mae_r"]) for x in stp])
        pngs = [os.path.join(out, x["chart"]) for x in E]
        check("one PNG chart per trade, valid PNG header", all(os.path.exists(p) and open(p, "rb").read(8) == b"\x89PNG\r\n\x1a\n" for p in pngs))
        tags = E[0]["tags"]
        check(f"tags: session / VIX band / TDO side / SB hour / weekday ({tags})",
              all(set(x["tags"]) == {"session", "vix", "tdo", "sb_hour", "weekday"} for x in E)
              and all(x["tags"]["vix"] in ("<15", "15-18", "18-22", "22+") for x in E)
              and all(x["tags"]["tdo"] in ("with", "against", "before 00:00", None) for x in E))
        check("setup steps + reasons on every entry", all(x["setup"] and x["why"] for x in E))
        W = doc["weeks"]
        check(f"weekly summaries ({len(W)}) add up to the trades and say 'small sample'",
              sum(w["trades"] for w in W) == len(E) and abs(sum(w["usd"] for w in W) - sum(x["usd"] for x in E)) < 0.05
              and all(any("Small sample" in s for s in w["learned"]) for w in W))
        check("week-<YYYY-Www>.md written per week", sorted(os.listdir(wk)) == sorted(f"week-{w['week']}.md" for w in W))
        doc2 = J.build(rf, os.path.join(ROOT, "data", "NQ_1m.csv"), os.path.join(d, "j2"), None, include_paper=True, charts=False)
        check("--all adds the paper trade", doc2["n"] == len(T))
        on = json.load(open(os.path.join(out, "entries.json")))
        check("entries.json: no account name beyond the masked '...1234', no balance field",
              all(x["acct"] == "...1234" for x in on["trades"]) and "balance" not in json.dumps(on))
    # the PC hook: weekdays from 17:20 ET, once a day, into its own (gitignored) folder; never raises
    import datetime as dt
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    with tempfile.TemporaryDirectory() as d:
        sp, od = os.path.join(d, "state.json"), os.path.join(d, "journal")
        t_early = dt.datetime(2026, 11, 24, 17, 0, tzinfo=ET).timestamp()
        t_ok = dt.datetime(2026, 11, 24, 17, 25, tzinfo=ET).timestamp()
        t_sat = dt.datetime(2026, 11, 28, 18, 0, tzinfo=ET).timestamp()
        r0 = J.maybe_run(t_early, sp, od)
        r1 = J.maybe_run(t_ok, sp, od)
        r2 = J.maybe_run(t_ok + 900, sp, od)
        r3 = J.maybe_run(t_sat, sp, od)
        check("PC hook: not before 17:20 ET, once a weekday (state file), never on a weekend, writes into its own folder",
              r0 is None and r1 is not None and r1.get("day") == "2026-11-24" and r2 is None and r3 is None
              and os.path.exists(os.path.join(od, "entries.json")), (r0, r1, r2, r3))
    gi = open(os.path.join(ROOT, ".gitignore")).read()
    check("data/journal/ and data/journal_build.json are gitignored (a tracked change would block the PC's auto-update)",
          "data/journal/" in gi and "data/journal_build.json" in gi)
    fails = [n for n, ok in RES if not ok]
    print(f"\n{len(RES) - len(fails)}/{len(RES)} OK" + (f"  FAIL: {fails}" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
