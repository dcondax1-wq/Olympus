"""Multi-strategy books, step 2: the repo's one-account simulator (tools/money/combo_account.py, UNCHANGED: MFFU eval +
funded rules, engine sizing for LIT / ATLAS / BLITZ, one net position, $1.90 a micro + fills, 6-month slots net of eval
fees, whole-day bootstrap) opened up to every lane of research/books/lanes_<fills>.json. Only monkeypatches in THIS process:
  - the lane list / tie order (LIT first, then ATLAS, members, BLITZ, the rest),
  - ATLAS members E / M / S size like ATLAS (engine/account_b), every non-engine lane sizes as a lane: min($125 a 25K plan,
    x2 on a 50K, 30% of the room, the soft day left), exactly like the post-close lane P.
Conflict rules (combo_account's own): "first" = one position at a time, first in keeps it; "adds" = a same-side signal may
stack (micros capped by the plan's max, sized from the room left after every open trade's full stop-out); an opposite
signal is ALWAYS skipped (never opposite positions). PAPER ONLY.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")]
import combo_account as CA

_ORIG_SIZE = CA.Book.size
LANES = []


def use(fills="real"):
    global LANES
    p = os.path.join(ROOT, "research", "books", f"lanes_{fills}.json")
    d = json.load(open(p, encoding="utf-8"))
    LANES = d["lanes"]
    CA.TRADES = p
    CA.STRATS = tuple(LANES)
    CA.PRIO.clear(); CA.PRIO.update({s: i for i, s in enumerate(LANES)})
    for s in LANES:
        CA.NAME.setdefault(s, d["names"][s])
        if s not in CA.LANE_USD:
            CA.LANE_USD[s] = 250.0 if s in ("E", "M", "S") else 125.0
    CA._D.clear()
    CA._patch_account_b()
    return d


def _size(self, t, room, cum, st):
    s = t["s"]
    if self.sizing == "lanes" and s != self.primary:
        return CA.lane_q(t, s, room, cum, self.dll, self.maxq, self.P["x"])
    if s in ("E", "M", "S"):
        return _ORIG_SIZE(self, {**t, "s": "A"}, room, cum, st)
    if s not in ("Z", "A", "B"):
        return CA.lane_q(t, s, room, cum, self.dll, self.maxq, self.P["x"])
    return _ORIG_SIZE(self, t, room, cum, st)


CA.Book.size = _size
