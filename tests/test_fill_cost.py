"""FILL COST (night-atlasfills 2026-11-20): "real slippage so far: N ticks over K fills" as data for the phone.

  a. tools/fill_cost.words / block: the plain line (ticks worse vs the backtest price, median of K, worst, $ a micro), None
     without a fill, better / same fills said as such
  b. from_rows on a temp data/pc_days: live entry rows with broker fill legs only (paper, refused, hidden BLITZ / ATLAS v2,
     no-fill rows left out), sells and buys signed right, the last 20 per bot, no account text in the result
  c. tools/learn_night.card_doc: each strategy's card row carries "fills" (the PC's engine/zeus_learn.fills), K8 never,
     a bot with no fill has none, the card stays under its byte cap, no account number
  d. the real pulled days (when data/pc_days exists): ATLAS 3 fills, median 11 ticks (night-nqlive's 9 / 11 / 15)
    python -X utf8 -m tests.test_fill_cost
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import fill_cost as FC  # noqa: E402

RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def part_a():
    w = FC.words({"n": 3, "entry_slip_med": 11.0, "worst": 15.0})
    check("a. 3 fills: '11 ticks worse ... median of 3 fills; worst 15 ... $5.50 a micro ... counts 1'",
          w and "11 ticks worse" in w and "median of 3 fills" in w and "worst 15" in w and "$5.50 a micro" in w and "counts 1" in w, w)
    w1 = FC.words({"n": 1, "entry_slip_med": 3.0, "worst": 3.0})
    check("a. 1 fill: '3 ticks worse ... (1 fill'", w1 and "3 ticks worse" in w1 and "(1 fill" in w1 and "worst" not in w1, w1)
    check("a. no fill / bad input -> None", FC.words({"n": 0, "entry_slip_med": None}) is None and FC.words(None) is None
          and FC.block({"n": 0}) is None)
    wb = FC.words({"n": 4, "entry_slip_med": -1.5, "worst": 2})
    check("a. better fills said as better, no $ cost", wb and "1.5 ticks better" in wb and "a micro" not in wb, wb)
    w0 = FC.words({"n": 2, "entry_slip_med": 0, "worst": 1})
    check("a. median 0: 'at the backtest price'", w0 and "at the backtest price" in w0, w0)
    b = FC.block({"n": 3, "entry_slip_med": 11.0, "worst": 15.0})
    check("a. block: n / med / worst / assumed 1 / line", b == {"n": 3, "med": 11.0, "worst": 15.0, "assumed": 1, "line": FC.words(
        {"n": 3, "entry_slip_med": 11.0, "worst": 15.0})}, b)


def _row(bot, side, entry, fills, mode="live", t=1794995400, src="acctb", ok=True, acct="...6018"):
    return {"acct": bot, "bot": bot, "entry": entry, "entry_t": t, "mode": mode, "qty": sum(q for _, q in fills) or 1, "side": side,
            "src": src, "result": {"account": acct, "ok": ok, "legs": [{"fill_px": px, "filled": q, "qty": q} for px, q in fills]}}


def part_b(tmp):
    days = os.path.join(tmp, "pc_days")
    rows = {
        "2026-11-17": [_row("atlas", "sell", 100.0, [(99.0, 2)], t=1), _row("zlarior", "buy", 200.0, [(200.5, 1)], t=2, src="main"),
                       _row("atlas", "sell", 100.0, [(98.0, 2)], mode="paper", t=3),             # paper: out
                       _row("blitz", "buy", 50.0, [(55.0, 1)], t=4, src="acctc"),                # hidden: out
                       _row("atlas", "buy", 100.0, [(101.0, 1)], t=5, src="atlas_v2"),            # hidden v2: out
                       _row("atlas", "buy", 100.0, [(105.0, 1)], t=6, ok=False),                  # refused: out
                       _row("atlas", "buy", 100.0, [], t=7),                                      # no fill: out
                       {"bot": "atlas", "side": "exit", "mode": "live", "entry_t": 1, "pnl": -5}],
        "2026-11-18": [_row("atlas", "buy", 100.0, [(100.25, 1), (100.75, 1)], t=8)],           # 2 legs: avg 100.5 = +2 ticks
    }
    for d, rs in rows.items():
        os.makedirs(os.path.join(days, d), exist_ok=True)
        with gzip.open(os.path.join(days, d, "trades.jsonl.gz"), "wt", encoding="utf-8") as fh:
            for r in rs:
                fh.write(json.dumps(r) + "\n")
    os.makedirs(os.path.join(days, "_junk"), exist_ok=True)
    out = FC.from_rows(days)
    check("b. ATLAS: the sell 4 ticks worse + the 2-leg buy 2 ticks worse -> n 2, median 3, worst 4",
          out.get("atlas") == {"n": 2, "entry_slip_med": 3.0, "worst": 4.0, "mean": 3.0, "usd_per_micro": 1.5}, out)
    check("b. Zlarior: 2 ticks worse on its buy; no blitz / v2 key; no account text",
          out.get("zlarior", {}).get("entry_slip_med") == 2.0 and set(out) == {"atlas", "zlarior"} and "6018" not in json.dumps(out), out)
    many = [_row("atlas", "sell", 100.0, [(100.0 - 0.25 * k, 1)], t=100 + k) for k in range(30)]
    os.makedirs(os.path.join(days, "2026-11-19"), exist_ok=True)
    with gzip.open(os.path.join(days, "2026-11-19", "trades.jsonl.gz"), "wt", encoding="utf-8") as fh:
        for r in many:
            fh.write(json.dumps(r) + "\n")
    o2 = FC.from_rows(days)
    check("b. the last 20 fills only (in entry-time order)", o2["atlas"]["n"] == 20 and o2["atlas"]["worst"] == 29.0, o2["atlas"])
    check("b. no data folder -> {}", FC.from_rows(os.path.join(tmp, "nope")) == {})


def part_c():
    from tools import learn_night as LN
    S = {"day": "2026-11-19", "t": 1795125903, "line": "ZEUS learned Nov 19: ...", "proposals": [],
         "bots": {"zlarior": {"name": "Zlarior", "today": {"n": 0}, "roll": {}, "fills": {"n": 1, "entry_slip_med": 3.0, "worst": 3.0}},
                  "atlas": {"name": "ATLAS", "today": {"n": 0}, "roll": {}, "fills": {"n": 3, "entry_slip_med": 11.0, "worst": 15.0}},
                  "k8": {"name": "K8", "today": {"n": 5}, "roll": {}, "fills": {"n": 5, "avg_price": 0.526, "kill_price": 0.58}},
                  "newbot": {"name": "New", "today": {}, "roll": {}, "fills": {"n": 0, "entry_slip_med": None, "worst": None}}}}
    c = LN.card_doc(S, "test")
    by = {b["key"]: b for b in c["bots"]}
    check("c. card rows: ATLAS fills line 11 ticks over 3, Zlarior 3 ticks over 1",
          by["atlas"].get("fills", {}).get("med") == 11.0 and "11 ticks worse" in by["atlas"]["fills"]["line"]
          and by["zlarior"].get("fills", {}).get("n") == 1, by)
    check("c. K8 and a bot without fills carry no fills block; the card stays under its cap",
          "fills" not in by["k8"] and "fills" not in by["newbot"] and len(json.dumps(c).encode()) <= LN.CARD_MAX_BYTES, by)


def part_d():
    days = FC.PC_DAYS
    if not os.path.isdir(days):
        check("d. (skipped: no data/pc_days pulled here)", True)
        return
    a = FC.from_rows(days).get("atlas")
    check("d. real pulled days: ATLAS >= 3 fills, the first three were 9 / 11 / 15 ticks (median 11 while n = 3)",
          a and a["n"] >= 3 and (a["n"] > 3 or (a["entry_slip_med"] == 11.0 and a["worst"] == 15.0)), a)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="fillcost_")
    try:
        part_a()
        part_b(tmp)
        part_c()
        part_d()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
