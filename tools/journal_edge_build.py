"""MNEMOSYNE EDGE DATA (night-botgap 2026-11-18, research/writeups/bot-gap-2026-11-18.md): the trade list behind the journal's
"The bot's edge" page (tools/web_public/journal/edge.html). Cloud side, stdlib only, read only: nothing here trades, sizes,
routes or touches live_model*.json.

What the best journals show and our journal apps did not (Tradervue / TradesViz / NinjaTrader / Edgewonk): the R of every trade,
how far it went against us before it ended (MAE) and how far it went our way (MFE), expectancy by setup and by time, the weekday x
hour map, the equity curve with its drawdowns and how long a losing run normally lasts. The page computes all of it in the phone
(journal/edgecore.js) from the rows this tool writes.

Input: the Why app's per-trade anatomy (tools/win_loss_anatomy.py -> research/anatomy/trades_{lit,atlas}.json): the repo's own
backtests, costs in, on CME NQ futures bars (never Yahoo / CFD), MAE / MFE already measured there (nothing is recomputed here):
  Zlarior (LIT)  run lit_live, 631 trades 2021-26 at the LIT size ($800 up to a 20-pt stop)
  ATLAS          the EMA / MACD / S-R members after the account-B rules, 1,288 trades 2021-26 at $250 a trade (the funded 25K size)
Output: tools/web_public/journal/edge.json (tracked, ~100 KB):
  {v, app, built, anatomy_built, upto {lit, atlas}, risk {L, A}, sources {L, A}, setups {L: [...], A: [...]}, exits [...], cols, rows}
  row = [day, entry ET "HH:MM", bot "L"|"A", setup index, side 1|-1, micros, risk $, R, $, MFE R, MAE R, exit index, minutes held]

    python -X utf8 tools/journal_edge_build.py            # rebuild edge.json (~1 s)
    python -X utf8 tools/journal_edge_build.py --check    # exit 1 when edge.json is older than the anatomy files
Tests: python -X utf8 -m tests.test_journal_edge (part a checks the file, part b the maths).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = {"L": os.path.join(ROOT, "research", "anatomy", "trades_lit.json"), "A": os.path.join(ROOT, "research", "anatomy", "trades_atlas.json")}
OUT = os.path.join(ROOT, "tools", "web_public", "journal", "edge.json")
VERSION = 1
LIT_SETUPS = ["Equal highs / lows (build-up)", "London box", "Asia box", "NY box", "Other levels"]
LIT_OF = {"build-up": 0, "London box": 1, "Asia box": 2, "NY box": 3}
ATLAS_SETUPS = ["EMA", "MACD", "S/R"]
EXITS = ["STOP", "TARGET", "BE", "FLAT", "CUT", "HEDGE"]
EXIT_OF = {"STOP": "STOP", "TARGET": "TARGET", "BE": "BE", "EOD": "FLAT", "TIME": "FLAT", "FLAT": "FLAT", "CUT": "CUT", "T15": "CUT", "CUT_T15": "CUT",
           "HEDGE": "HEDGE"}
COLS = ["d", "hm", "b", "s", "sd", "q", "k", "r", "u", "f", "a", "x", "m"]


def _f(v, nd=2):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if x == x and abs(x) != float("inf") else None


def exit_index(kind) -> int:
    return EXITS.index(EXIT_OF.get(str(kind or "").strip().upper(), "FLAT"))


def setup_index(bot: str, t: dict) -> int:
    if bot == "L":
        return LIT_OF.get(str(t.get("s_lvl_type") or ""), 4)
    m = str(t.get("member") or "")
    return ATLAS_SETUPS.index(m) if m in ATLAS_SETUPS else 0


def load(bot: str, path: str | None = None) -> tuple:
    """(rows of dicts, built) of one anatomy file; ([], None) when it is missing or odd"""
    try:
        D = json.load(open(path or SRC[bot], encoding="utf-8"))
        cols = D["cols"]
        return [dict(zip(cols, r)) for r in D["rows"] if isinstance(r, list)], D.get("built")
    except (OSError, ValueError, KeyError, TypeError):
        return [], None


def row(bot: str, t: dict) -> list | None:
    r, u = _f(t.get("r")), _f(t.get("usd"), 0)
    day, hm = str(t.get("day") or ""), str(t.get("hm") or "")
    if r is None or u is None or len(day) != 10 or len(hm) != 5:
        return None
    mfe, mae = _f(t.get("mfe_r")), _f(t.get("mae_r"))
    return [day, hm, bot, setup_index(bot, t), -1 if int(t.get("dir") or 1) < 0 else 1, int(t.get("qty") or 0) or None,
            _f(t.get("risk_usd"), 0), r, int(u), None if mfe is None else max(0.0, mfe), None if mae is None else max(0.0, min(mae, 1.5)),
            exit_index(t.get("exit")), int(t.get("mins")) if isinstance(t.get("mins"), (int, float)) else None]


def build(src: dict | None = None) -> dict:
    src = src or SRC
    rows, built = [], {}
    for b in ("L", "A"):
        R, built[b] = load(b, src.get(b))
        rows += [x for x in (row(b, t) for t in R) if x]
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    up = lambda b: max((x[0] for x in rows if x[2] == b), default=None)        # noqa: E731
    return {"v": VERSION, "app": "journal-edge", "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "anatomy_built": built, "upto": {"lit": up("L"), "atlas": up("A")},
            "risk": {"L": 800, "A": 250},
            "sources": {"L": "Zlarior (LIT) backtest of the live rules on CME NQ futures bars, at its normal size ($800 a trade up to a 20-pt stop), "
                             "costs in. History, not money made.",
                        "A": "ATLAS backtest (its EMA, MACD and S/R members under the account rules) on CME NQ futures bars, at $250 a trade "
                             "(the funded 25K size), costs in. History, not money made."},
            "setups": {"L": LIT_SETUPS, "A": ATLAS_SETUPS}, "exits": EXITS, "cols": COLS, "rows": rows}


def write(data: dict, path: str = OUT) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    os.replace(tmp, path)
    return path


def stale(path: str = OUT) -> bool:
    if not os.path.isfile(path):
        return True
    try:
        have = json.load(open(path, encoding="utf-8")).get("anatomy_built") or {}
    except (OSError, ValueError):
        return True
    return any(load(b)[1] != have.get(b) for b in ("L", "A"))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        s = stale()
        print("journal/edge.json is " + ("OLDER than research/anatomy: run python -X utf8 tools/journal_edge_build.py" if s else "current"))
        return 1 if s else 0
    data = build()
    p = write(data)
    n, nl = len(data["rows"]), sum(1 for x in data["rows"] if x[2] == "L")
    print(f"journal edge -> {os.path.relpath(p, ROOT)}: {n} trades (Zlarior {nl}, ATLAS {n - nl}), data to {data['upto']}, "
          f"{os.path.getsize(p) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
