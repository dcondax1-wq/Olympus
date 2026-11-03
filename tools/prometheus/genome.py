"""The ten knobs PROMETHEUS evolves, read from live_model_lit.json (never written).

A genome is a tuple of grid indices, one per knob: value = lo + index x step. The live value of every knob must sit on its
grid (checked at import), so the live strategy is itself a genome (`live_genome()`), and every genome stays inside the bounds
by construction (`clamp`). Bounds are "sane": wide enough to explore, never past what the engine or the owner's rules allow
(entries end before the 15:55 flat, the bank above the 1.5R minimum target, room share <= 100% of the eval room).
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = os.path.join(ROOT, "live_model_lit.json")


@dataclass(frozen=True)
class Knob:
    key: str            # short id (page, JSON)
    path: tuple         # where it lives in live_model_lit.json
    lo: float
    hi: float
    step: float
    label: str          # plain language (parameter card)
    unit: str = ""
    integer: bool = False

    @property
    def n(self) -> int:
        """Grid points."""
        return int(round((self.hi - self.lo) / self.step)) + 1

    def value(self, i: int):
        v = round(self.lo + int(i) * self.step, 6)
        return int(round(v)) if self.integer else v

    def index(self, v) -> int:
        i = (float(v) - self.lo) / self.step
        if abs(i - round(i)) > 1e-6 or not (0 <= round(i) < self.n):
            raise ValueError(f"{self.key}: {v} is not on the grid {self.lo}..{self.hi} step {self.step}")
        return int(round(i))


KNOBS: tuple[Knob, ...] = (
    Knob("cisd1m", ("lit", "cisd1m"), 10, 40, 2, "1m CISD confirmation window after the tap", "bars", integer=True),
    Knob("be_r", ("lit", "be_r"), 0.5, 2.0, 0.125, "Breakeven moves the stop at", "R"),
    Knob("be_off", ("lit", "be_off"), 0.0, 3.0, 0.25, "Breakeven stop above the entry", "pts"),
    Knob("t_at", ("lit", "t_check", "at"), 5, 40, 5, "Early check (cut a loser) after", "min", integer=True),
    Knob("max_rr", ("lit", "max_rr"), 4.0, 12.0, 0.5, "Target banked at", "R"),
    Knob("vix_k", ("lit", "vix_k"), 0.6, 1.6, 0.05, "Target = 18:00 open +/- VIX day move x", "x"),
    Knob("min_rr", ("lit", "min_rr"), 1.0, 2.5, 0.1, "Minimum target distance", "R"),
    Knob("disp", ("lit", "disp"), 0.5, 1.2, 0.05, "Displacement body at least", "ATR"),
    Knob("win_end", ("lit", "window", 0, 1), 600, 945, 15, "Last entry (ET)", "min", integer=True),
    Knob("room_f", ("lit_sizing", "two_week", "room_f"), 0.4, 1.0, 0.05, "Eval size: share of the room to the floor", "x"),
)
KEYS = tuple(k.key for k in KNOBS)


def load_model(path: str = MODEL) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _get(d, path):
    for p in path:
        d = d[p]
    return d


def _set(d, path, v):
    for p in path[:-1]:
        d = d[p]
    d[path[-1]] = v


def live_values(model: dict | None = None) -> dict:
    m = model or load_model()
    return {k.key: _get(m, k.path) for k in KNOBS}


def live_genome(model: dict | None = None) -> tuple:
    lv = live_values(model)
    return tuple(k.index(lv[k.key]) for k in KNOBS)


def clamp(g) -> tuple:
    return tuple(max(0, min(k.n - 1, int(i))) for k, i in zip(KNOBS, g))


def in_bounds(g) -> bool:
    return len(g) == len(KNOBS) and all(0 <= int(i) < k.n for k, i in zip(KNOBS, g))


def values(g) -> dict:
    return {k.key: k.value(i) for k, i in zip(KNOBS, g)}


def key(g) -> str:
    """Stable text key of a genome (cache, JSON)."""
    return "-".join(str(int(i)) for i in g)


def from_key(s: str) -> tuple:
    return tuple(int(x) for x in s.split("-"))


def to_model(g, model: dict | None = None) -> dict:
    """A deep copy of live_model_lit.json with this genome's values (in memory only, never written)."""
    m = copy.deepcopy(model or load_model())
    for k, i in zip(KNOBS, g):
        _set(m, k.path, k.value(i))
    return m


def lit_params(g, model: dict | None = None) -> dict:
    """The run_x parameter dict ("lit" block) of this genome."""
    return to_model(g, model)["lit"]


def diff(g, base=None) -> dict:
    """{knob: [base value, this value]} for every knob that differs from base (default: live)."""
    b = values(base if base is not None else live_genome())
    v = values(g)
    return {k: [b[k], v[k]] for k in KEYS if b[k] != v[k]}


def spec() -> list:
    """The knobs for the page / write-up."""
    lv = live_values()
    return [{"key": k.key, "label": k.label, "unit": k.unit, "lo": k.lo, "hi": k.hi, "step": k.step, "n": k.n,
             "live": lv[k.key], "path": ".".join(str(p) for p in k.path)} for k in KNOBS]


# every live value must be a grid point (else the live strategy would not be a genome)
live_genome()
