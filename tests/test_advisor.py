"""The discretion advisor (engine/advisor.py, read-only) + the playbook rules as data (engine/playbook.py): a synthetic long that
runs +1.9R, makes a 5m BOS up, then a 5m CHoCH down and stops at breakeven: the base walk = the strategy's own management
(BE exit), "exit on a 5m CHoCH" and "trail to the 5m protected swing" fire with a reason and score > $0, "BE on a CHoCH" is a
no-op (already at BE); the store (temp dir) is idempotent, the tally says "would have saved $X over N trades", the
suggestion cards carry no approve command, the trade dict is never changed, no broker / order import; advise_open on the
open trade; the 2026-10-28 live trade replayed on the heartbeat bars when that branch is there.

  python -X utf8 -m tests.test_advisor
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import advisor as AD  # noqa: E402
from engine import playbook as PB  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def T(h, m, day=(2026, 10, 14)):
    return int(dt.datetime(*day, h, m, tzinfo=ET).timestamp())


def path_rows(t0, points, step=1.0, wick=0.5):
    closes = [float(points[0])]
    for a, b in zip(points, points[1:]):
        n = max(1, int(round(abs(b - a) / step)))
        for i in range(1, n + 1):
            closes.append(a + (b - a) * i / n)
    rows, prev = [], closes[0]
    for i, c in enumerate(closes):
        rows.append([t0 + 60 * i, prev, max(prev, c) + wick, min(prev, c) - wick, c])
        prev = c
    return rows


def scenario():
    pre = path_rows(T(6, 0), [30100, 30060, 30075, 30030, 30045, 30000, 30008, 30000, 30004])
    t_entry = pre[-1][0] + 60
    post = path_rows(t_entry, [30004, 30060, 30036, 30080, 30050, 30070, 30020, 29990, 29995, 29980])
    rows = pre + post
    entry = post[0][1]
    trade = {"entry_t": t_entry, "exit_t": None, "dir": 1, "entry": entry, "stop": entry - 40, "target": entry + 300, "qty": 4,
             "usd": None, "exit_kind": None, "day": "2026-10-14"}
    return rows, trade


def t_advisor():
    rows, trade = scenario()
    base = AD.walk([r for r in rows if r[0] >= trade["entry_t"]], 0, 1, trade["entry"], trade["stop"], trade["target"],
                   AD._manage_spec("lit", trade))
    check("base walk = LIT management: breakeven exit at entry + 1.25 - 1 tick", base["kind"] == "BE" and abs(base["pts"] - 1.0) < 1e-6, base)
    trade.update(exit_t=base["t_exit"], exit_kind="BE", usd=round(base["pts"] * 2 * 4 - 1.9 * 4, 2))
    before = copy.deepcopy(trade)
    rec = AD.score_trade("lit", trade, rows)
    check("score_trade: a record with every rule", rec and {a["rule"] for a in rec["advice"]} == set(AD.RULES), rec and [a["rule"] for a in rec["advice"]])
    A = {a["rule"]: a for a in rec["advice"]}
    ex = A["exit_choch"]
    check("exit_choch fires on the 5m CHoCH down with a reason and saves $ vs the breakeven exit",
          ex["fired"] and ex["delta_usd"] > 0 and "CHoCH" in ex["events"][0]["why"], ex)
    tr = A["trail_5m"]
    check("trail_5m fires after the 5m BOS up (stop to the protected swing) and saves $", tr["fired"] and tr["delta_usd"] > 0
          and "protected swing" in tr["events"][0]["why"], tr)
    be = A["be_choch"]
    check("be_choch: no-op once the stop already sits at breakeven ($0)", be["delta_usd"] == 0, be)
    check("alt $ = real $ + delta (difference method)", all(abs(a["alt_usd"] - (trade["usd"] + a["delta_usd"])) < 0.01 for a in rec["advice"]))
    check("every fired rule names its playbook rule (Z-S1..Z-S4)", all(a["playbook"] in ("Z-S1", "Z-S2", "Z-S3", "Z-S4") for a in rec["advice"]))
    check("the trade dict is never changed", trade == before)
    # the store: temp dir, idempotent, tally + cards
    with tempfile.TemporaryDirectory() as tmp:
        u1 = AD.update("lit", [trade], rows, store=tmp)
        u2 = AD.update("lit", [trade], rows, store=tmp)
        recs = AD._jl_read(os.path.join(tmp, "lit.jsonl"))
        check("update(): one record, the second call adds nothing (idempotent by key)", u1["new"] == 1 and u2["new"] == 0 and len(recs) == 1, (u1, u2))
        tl = AD.load_tally(tmp)
        x = tl["lit"]["rules"]["exit_choch"]
        check("tally: 'would have saved $X over 1 trades (fired on 1 ...)'", x["fired"] == 1 and x["net"] > 0 and "would have saved $" in x["text"], x)
        C = AD.cards(store=tmp)
        check("suggestion cards: advisor kind, $ and text, never an approve command, nothing applied",
              C and all(c["kind"] == "advisor" and c["approve"] is None and not c["applied"] and c["would_text"] for c in C), C[:1])
        open_trade = {**trade, "exit_t": None, "exit_kind": "OPEN"}
        u3 = AD.update("lit", [open_trade, {**trade, "entry_t": trade["entry_t"] + 1, "exit_t": None}], rows, store=tmp)
        check("open / unfinished trades are not scored", u3["new"] == 0, u3)
        # live_learning.suggestions picks the advisor cards up from the store (read-only)
        from engine import live_learning as LL
        S = LL.suggestions(None, [], None, False, advisor_store=tmp)
        check("live_learning.suggestions includes the advisor cards", any(s.get("kind") == "advisor" for s in S), [s.get("kind") for s in S])
    # the open trade: advice right now (after the CHoCH, before the stop)
    now = trade["entry_t"] + 60 * 222
    adv = AD.advise_open("lit", {"entry_t": trade["entry_t"], "dir": 1, "entry": trade["entry"], "stop": trade["stop"] + 41.25,
                                 "stop0": trade["stop"], "target": trade["target"]}, [r for r in rows if r[0] + 60 <= now], now)
    check("advise_open: notes on the open trade (CHoCH exit / trail), newest first, each with a playbook id",
          adv and all(a.get("playbook") for a in adv) and adv == sorted(adv, key=lambda a: -a["t"]), adv[:2])
    # read-only: no broker / adapter / order import or file write outside the store
    src = open(os.path.join(ROOT, "engine", "advisor.py"), encoding="utf-8").read()
    bad = re.findall(r"^\s*(?:from|import)\s+[\w. ]*(ninjatrader|tradovate|adapter|live\b|accounts|guards|sizing)", src, re.M)
    check("advisor.py imports no broker / adapter / sizing / live module", not bad, bad)
    check("advisor.py never writes an order file (no 'oif' / 'outgoing' / '_route')", not re.search(r"oif|outgoing|_route\(", src))


def t_playbook():
    ids = [r["id"] for r in PB.RULES]
    check("playbook: rule ids unique", len(ids) == len(set(ids)))
    check("playbook: every rule has strategy / phase / title / text / an existing check function",
          all(r["strategy"] in PB.STRATEGIES and r["phase"] in PB.PHASES and r["title"] and r["text"] and PB.check_fn(r["check"]) for r in PB.RULES),
          [r["id"] for r in PB.RULES if not PB.check_fn(r["check"])])
    check("playbook: each strategy has setup, invalidation, management and structure rules",
          all({r["phase"] for r in PB.of(s)} == set(PB.PHASES) for s in PB.STRATEGIES))
    md = open(os.path.join(ROOT, "docs", "PLAYBOOK.md"), encoding="utf-8").read()
    missing = [i for i in ids if f"**{i} " not in md and f"**{i}**" not in md]
    check("docs/PLAYBOOK.md writes out every rule id", not missing, missing)
    check("advisor rules all point at playbook structure rules", all(PB.rule(v) and PB.rule(v)["phase"] == "structure"
                                                                     for R in AD.RULES.values() for v in R["playbook"].values()))
    b = {"stage": {"key": "limit", "waiting": "limit working at 29,945 until 04:12"}, "setups": [], "day_trades": 0}
    n = PB.now("lit", {"brain": b})
    check("now(lit): the Brain's limit stage -> Z6 with the Brain's sentence", n["id"] == "Z6" and "29,945" in n["why"], n)
    pos = {"entry": 30000.0, "stop": 29960.0, "dir": 1, "entry_t": 1000}
    check("now(lit): in a trade, first 15 minutes -> Z16; later before +1R -> Z15; stop at BE -> Z14",
          PB.now("lit", {"brain": b, "position": pos, "now": 1000 + 300})["id"] == "Z16"
          and PB.now("lit", {"brain": b, "position": pos, "now": 1000 + 3600})["id"] == "Z15"
          and PB.now("lit", {"brain": b, "position": {**pos, "stop": 30001.25}, "now": 1000 + 3600})["id"] == "Z14")
    check("applying(lit): the limit stage applies Z6 and Z7 (day free)", set(PB.applying("lit", {"brain": b})) >= {"Z6", "Z7"},
          PB.applying("lit", {"brain": b}))
    check("now(atlas): an armed EMA member -> A1", PB.now("atlas", {"members": {"ema_lon_vix": {"stage": "armed", "text": "x"}}})["id"] == "A1")
    check("now(scalp): BLITZ stages -> B1 filtered / B3 watching / B6 trade",
          [PB.now("scalp", {"stage": s})["id"] for s in ("filtered", "watching", "trade")] == ["B1", "B3", "B6"])
    check("now(): an unknown strategy / bad ctx never raises", PB.now("x")["id"] is None and PB.now("lit", {"brain": 5})["id"] in (None, "Z1"))


def t_real_trade():
    """2026-10-28: the first live LIT trade on the PC's NinjaTrader bars (heartbeat branch), when available."""
    import gzip
    import io
    import subprocess
    try:
        raw = subprocess.run(["git", "-C", ROOT, "show", "origin/heartbeat:bars_1m.csv.gz"], capture_output=True, check=True, timeout=60).stdout
        import pandas as pd
        df = pd.read_csv(io.BytesIO(gzip.decompress(raw)))
    except Exception as e:
        print(f"[SKIP] 2026-10-28 trade: heartbeat bars unavailable ({e.__class__.__name__})")
        return
    from engine import structure as ST
    rows = ST.as_rows(df)
    t_e = int(dt.datetime(2026, 10, 28, 3, 43, tzinfo=ET).timestamp())
    tr = {"entry_t": t_e, "exit_t": int(dt.datetime(2026, 10, 28, 4, 2, tzinfo=ET).timestamp()), "dir": -1, "entry": 29945.0,
          "stop": 29987.5, "target": 29665.75, "qty": 5, "usd": -437.0, "exit_kind": "STOP", "day": "2026-10-28"}
    rec = AD.score_trade("lit", tr, rows)
    if rec is None:
        print("[SKIP] 2026-10-28 trade: bars do not cover it")
        return
    A = {a["rule"]: a for a in rec["advice"]}
    print("   2026-10-28 live trade:", {k: (v["fired"], v["delta_usd"]) for k, v in A.items()}, "base", rec["base"])
    check("2026-10-28: the base walk = the live STOP (-42.75 pts)", rec["base"]["kind"] == "STOP" and abs(rec["base"]["pts"] + 42.75) < 0.01, rec["base"])
    check("2026-10-28: the 1h-trend skip would have saved the $437 (1h up against the short); the CHoCH rules do not fire",
          A["skip_htf"]["fired"] and A["skip_htf"]["delta_usd"] == 437.0 and not A["exit_choch"]["fired"], A)


def main():
    t_advisor()
    t_playbook()
    t_real_trade()
    n, ok = len(RES), sum(RES)
    print(f"\nadvisor + playbook: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
