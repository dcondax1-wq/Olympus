"""The FIRST-DAY CHECKLIST (Monday launch kit, 2026-11-14): one source, two copies that never drift apart.
  docs/LAUNCH_DAY.md                        the page (for the owner and for Claude)
  tools/web_public/gate/launch_day.json     the same checklist as a card on the Gate (tools/web_public/gate/launch.js draws it under
                                            the Launch card when the PC serves the site)
What to look for at 01:45 ET, what each phone push means and the exact one-line action for each (FEED STALE, bot down, a fill
check flag ...). Every action is the owner's own (at the PC or in NinjaTrader); nothing here arms, trades or changes a bot.

  python tools/launch_day.py            write both files
  python tools/launch_day.py --check    exit 1 when either file differs from this source (tests/test_launch_kit.py runs it)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ROOT, "docs", "LAUNCH_DAY.md")
JS = os.path.join(ROOT, "tools", "web_public", "gate", "launch_day.json")

DAY = "2026-11-16"
TITLE = "Launch day: Monday Nov 16"
INTRO = ("Zlarior (MFFU 50K eval, LIT) and ATLAS (25K eval) trade for real from 02:00 ET. You arm them yourself at the PC "
         "(GO_LIVE_EVAL.bat, you type the phrase); nothing on the phone can trade, start or stop a bot.")
STEPS = [
    "At 01:45 ET open the Olympus link on the iPhone. The Launch card must say Ready: Zlarior and ATLAS \"LIVE, armed\", feed fresh, no flags.",
    "In the ntfy app the \"Ready for 02:00 ET\" push is there (silent). A loud \"NOT ready\" names what is wrong and its fix.",
    "Anything red: do the one action in its row below. Nothing red: you are done; every entry and exit sends a push.",
]
LOOK = {"id": "look", "title": "01:45 ET: what to look for", "cols": ["On the Launch card", "Good", "If not"], "rows": [
    ["Zlarior 50K", "LIVE, armed", "PC: double-click GO_LIVE_EVAL.bat and type the phrase"],
    ["ATLAS 25K", "LIVE, armed", "PC: double-click GO_LIVE_EVAL.bat and type the phrase"],
    ["Feed", "fresh (1-minute bar under 3 min old)", "NinjaTrader: open the MNQ 5-minute chart, right-click > Indicators > LE_BarFeed > Add"],
    ["Drawdown left", "the same as the MFFU dashboard", "send Claude a photo of both"],
    ["Flags", "none", "the action written under the flag"],
    ["Phone alerts", "\"Phone alerts on: last check ... min ago\"", "PC: double-click BOTS_BACK.bat"],
]}
PUSHES = {"id": "pushes", "title": "What each push means", "cols": ["Push (ntfy)", "What it means", "Do"], "rows": [
    ["Ready for 02:00 ET", "both bots running and armed, feed fresh, drawdown left per account", "nothing"],
    ["NOT ready for 02:00 ET", "something is wrong before the first entry", "the fix written in the push (fixed before 02:00: a Ready push follows)"],
    ["Zlarior 50K / ATLAS 25K trade opened", "an entry: side, micros, entry, stop, target, $ risk at the stop", "nothing"],
    ["Zlarior 50K / ATLAS 25K trade closed", "the exit: how, +/- $ and R, drawdown left, today's $", "nothing"],
    ["... fill check: ...", "NinjaTrader did something else than the bot planned", "see the fill check table"],
    ["FEED STALE", "no fresh NinjaTrader bars: no new entries", "NinjaTrader: open the MNQ 5-minute chart, right-click > Indicators > LE_BarFeed > Add"],
    ["Bot down", "the bot server on the PC does not answer or report", "PC: double-click GO_LIVE_EVAL.bat (it brings the bot back) and type the phrase"],
    ["Bot stopped", "the server runs but the bot is stopped in entry hours", "PC: double-click GO_LIVE_EVAL.bat and type the phrase"],
    ["NinjaTrader closed", "NinjaTrader is not running on the PC", "PC: open NinjaTrader and log in"],
    ["50% / 75% of the drawdown used", "the eval used half / three quarters of its room", "nothing: the bot sizes down by itself"],
    ["Daily loss limit near", "today's loss is at 70% of the daily limit", "nothing: the bot keeps its stops"],
    ["Day Mon Nov 16: +$...", "the 16:05 ET day summary per account", "nothing"],
    ["Back to normal", "the problem is gone", "nothing"],
]}
FILLS = {"id": "fills", "title": "Fill check flags (after a real trade)", "cols": ["Flag", "What it means", "Do"], "rows": [
    ["NO STOP at NinjaTrader", "the position has no stop order", "NinjaTrader now: no stop order on it -> Positions > right-click > Flatten"],
    ["wrong size", "NinjaTrader filled other micros than the bot sent, or the stop covers fewer", "NinjaTrader > Positions: not what the bot sent -> flatten it there"],
    ["entry slippage / stop slippage", "a fill more than 2 ticks worse than planned", "nothing; tell Claude if it repeats"],
    ["stop price off / target price off", "the bracket is more than 2 ticks from the plan", "NinjaTrader > Orders: check the stop and the target"],
    ["costs above plan", "slippage + commission more than 2 ticks a micro above the plan", "nothing; the Sunday review looks at it"],
    ["entry not filled", "NinjaTrader refused or never filled the entry: no position", "NinjaTrader: Control Center > Connections connected, MNQ chart with LE_BarFeed"],
]}
STOP = "Stop everything: double-click STOP_BOT.bat on the PC (orders at NinjaTrader keep their stop and target)."
SECTIONS = [LOOK, PUSHES, FILLS]


def data() -> dict:
    return {"v": 1, "kind": "le-launch-day", "day": DAY, "title": TITLE, "intro": INTRO, "steps": STEPS, "sections": SECTIONS, "stop": STOP,
            "src": "docs/LAUNCH_DAY.md (tools/launch_day.py)"}


def _cell(s: str) -> str:
    return str(s).replace("|", "/")


def markdown() -> str:
    out = [f"# {TITLE} (2026-11-16)", "", INTRO, "", "## Your 3 steps"]
    out += [f"{i}. {s}" for i, s in enumerate(STEPS, 1)]
    for sec in SECTIONS:
        out += ["", f"## {sec['title']}", "| " + " | ".join(sec["cols"]) + " |", "|" + "---|" * len(sec["cols"])]
        out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in sec["rows"]]
    out += ["", f"**{STOP}**", "",
            "## For Claude (how it is built)",
            "| Piece | File |", "|---|---|",
            "| The Launch card (per bot: armed, feed, trades, $, drawdown left, flags; phone alerts) | `tools/launch_card.py`, `GET /api/site/launch.json` in `engine/live_site.py`, `tools/web_public/gate/launch.js` (only when the PC serves the site) |",
            "| Entry / exit pushes per account, the fill check pushes | `tools/pc_report.py` (every 15 min), `tools/fill_check.py` (real fills vs the live loop's plan, read-only) |",
            "| The 01:45 ET ready push | `tools/launch_card.ready_push` through `tools/pc_guard.py` |",
            "| This page and its card | `tools/launch_day.py` writes `docs/LAUNCH_DAY.md` and `tools/web_public/gate/launch_day.json` (`--check` in the tests) |",
            "| Tests | `python -X utf8 -m tests.test_launch_kit` |", ""]
    return "\n".join(out)


def as_json() -> str:
    return json.dumps(data(), indent=1, ensure_ascii=False) + "\n"


def _read(p):
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Write (or --check) docs/LAUNCH_DAY.md and the Gate's launch_day.json.")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    want = {MD: markdown(), JS: as_json()}
    if a.check:
        bad = [os.path.relpath(p, ROOT) for p, txt in want.items() if _read(p) != txt]
        print("launch day checklist: " + ("in sync" if not bad else "OUT OF SYNC: " + ", ".join(bad) + " (run python tools/launch_day.py)"))
        return 1 if bad else 0
    for p, txt in want.items():
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        print("wrote", os.path.relpath(p, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
