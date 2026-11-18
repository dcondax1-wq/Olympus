"""CME micro futures specs + "run engine/lit.py on another market" (RESEARCH ONLY, docs/OTHER_MARKETS.md).

engine/lit.py was written for NQ: its tick, $ per point, costs, build-up tolerance and target-band vol index are module values
(lit.TICK, lit.PV, lit.COMM, lit.SLIP, lit.MAX_MICROS, lit.BU_TOL_MIN, lit.VOL_SRC, lit.SESSIONS). `use(spec)` swaps them for one
`with` block and always puts the NQ values back (also on an error). The live bot (server.py / engine/live.py) never calls it
and use() refuses to run inside a process that has the live loop loaded, so live NQ trading cannot see another market's
numbers. `params(spec, k)` gives the LIT settings that are in points, re-scaled for the market (pre-registered, nothing tuned):

  stop_buf      1 tick (the rule: stop 1 tick beyond the sweep extreme)
  min / max     NQ 8 / 80 pts x k, k = the market's median 5m ATR(14) / NQ's over the same trading days (a volatility ratio:
  stop          price ratios mislead across asset classes, e.g. crude at $70 vs NQ at 25,000), rounded to the tick
  be_off        the breakeven that still pays the costs: 1 tick of exit slippage + the commission rounded up to ticks
                (NQ: 0.25 + 4 ticks = 1.25, today's live value)
  build-up tol  NQ 1.5 pts x k (equal highs / lows), never under 1 tick
  target band   the 18:00 open +/- 1 implied daily move: NQ and M2K use VIX (equity index, as live LIT), gold and crude use
                their own 20-day realized vol (data/<SYM>_rv_1d.csv, built by tools/nt_import.py from the futures bars; there
                is no GVZ / OVX file and we never use non-futures web data)
Session boxes (Asia 20-24, London 03-04, NY 08-09 ... ET) stay NQ's for every market: they are clock-time liquidity pools
of the three regions and gold / crude trade all three (CME Globex 18:00-17:00 ET for metals, energy and equity alike). The
one market-specific choice, also pre-registered: a "pit" variant that stops new entries 30 min before the pit settle and goes
flat 5 min before it (gold 13:30 ET, crude 14:30 ET), reported next to the as-is run; the pick is made on 2026 H1 only.
"""
from __future__ import annotations

import contextlib
import math
import sys
from dataclasses import dataclass, field

from engine import lit

NQ_POINTS = {"min_stop": 8.0, "max_stop": 80.0, "bu_tol": 1.5}   # live_model.json lit min_stop / max_stop, lit.buildups tol_min
LIVE_MODULES = ("engine.live", "server")      # use() refuses while the live loop is loaded


@dataclass(frozen=True)
class Spec:
    sym: str            # data file prefix (data/<sym>_1m.csv) = the micro's root
    micro: str
    name: str
    exchange: str
    tick: float         # price increment
    pv: float           # $ per point per micro
    comm: float         # $ per micro round trip (MFFU); see comm_note
    comm_note: str
    vol: str            # target band: "VIX" (as NQ) or "rv20" (own 20-day realized vol file)
    months: str         # listed contract months used for rolls (CME month codes)
    pit: tuple = None   # (open, settle) ET minutes of the day session / pit, None = equity cash hours (NQ's)
    sessions: dict = field(default=None)   # None = lit.SESSIONS (NQ's boxes)

    @property
    def tick_usd(self):
        return round(self.tick * self.pv, 4)


SPECS = {
    "NQ": Spec("NQ", "MNQ", "Micro E-mini Nasdaq-100", "CME", 0.25, 2.0, 1.40, "engine research cost (live adds $0.50 = $1.90)",
               "VIX", "HMUZ"),
    "MGC": Spec("MGC", "MGC", "Micro Gold (10 oz)", "COMEX", 0.10, 10.0, 2.40,
                "ESTIMATE: MFFU's MNQ $1.90 + higher COMEX fees; check MFFU's commission table and pass --comm",
                "rv20", "GJMQVZ", pit=(500, 810)),          # COMEX gold day session 08:20-13:30 ET (settle 13:30)
    "MCL": Spec("MCL", "MCL", "Micro WTI Crude Oil (100 bbl)", "NYMEX", 0.01, 100.0, 2.40,
                "ESTIMATE: MFFU's MNQ $1.90 + higher NYMEX fees; check MFFU's commission table and pass --comm",
                "rv20", "FGHJKMNQUVXZ", pit=(540, 870)),    # NYMEX crude day session 09:00-14:30 ET (settle 14:30)
    "M2K": Spec("M2K", "M2K", "Micro E-mini Russell 2000", "CME", 0.10, 5.0, 1.90,
                "same CME equity-micro fees as MNQ (MFFU $1.90); check MFFU's commission table", "VIX", "HMUZ"),
}


def spec(sym: str, comm: float | None = None) -> Spec:
    s = SPECS[sym.upper()]
    if comm is not None:
        from dataclasses import replace
        s = replace(s, comm=float(comm), comm_note="given on the command line")
    return s


def to_tick(x: float, tick: float, up: bool = False) -> float:
    n = math.ceil(x / tick - 1e-9) if up else round(x / tick)
    return round(max(1, n) * tick, 10)


def be_off(s: Spec) -> float:
    """Breakeven offset that pays the costs: 1 tick of exit slippage + the commission in whole ticks (NQ 1.25)."""
    return round(s.tick + math.ceil(s.comm / s.pv / s.tick - 1e-9) * s.tick, 10)


def params(s: Spec, k: float, variant: str = "main") -> dict:
    """LIT overrides (on top of live_model.json "lit") for market s at volatility ratio k. variant: main | stop08 | stop125 |
    pit (gold / crude: entries end 30 min before the settle, flat 5 min before) | vix (gold / crude: VIX band instead of own vol)."""
    kk = k * {"stop08": 0.8, "stop125": 1.25}.get(variant, 1.0)
    P = {"stop_buf": s.tick, "min_stop": to_tick(NQ_POINTS["min_stop"] * kk, s.tick),
         "max_stop": to_tick(NQ_POINTS["max_stop"] * kk, s.tick), "be_off": be_off(s)}
    if variant == "pit":
        if not s.pit:
            raise ValueError(f"{s.sym} has no pit session (equity hours = NQ's)")
        P.update(window=[[120, s.pit[1] - 30]], flat_mod=s.pit[1] - 5)
    return P


def variants(s: Spec) -> list:
    v = ["main", "stop08", "stop125"]
    if s.pit:
        v += ["pit", "vix"]
    return v


@contextlib.contextmanager
def use(s: Spec, k: float = 1.0, vol_path: str | None = None, vol: str | None = None):
    """engine/lit.py on market s inside the block (research processes only). vol_path = the csv used for the target band
    (rv20 markets: data/<SYM>_rv_1d.csv); vol overrides s.vol ("VIX" = keep data/VIX_1d.csv)."""
    loaded = [m for m in LIVE_MODULES if m in sys.modules]
    if loaded:
        raise RuntimeError(f"lit_markets.use() is research only; refused in a process with {loaded} loaded")
    names = ("TICK", "PV", "COMM", "SLIP", "MAX_MICROS", "BU_TOL_MIN", "VOL_SRC", "SESSIONS", "SESSION_CLASS")
    saved = {n: getattr(lit, n) for n in names}
    try:
        lit.TICK, lit.PV, lit.COMM, lit.SLIP = s.tick, s.pv, s.comm, s.tick
        lit.BU_TOL_MIN = max(s.tick, to_tick(NQ_POINTS["bu_tol"] * k, s.tick))
        band = vol or s.vol
        if band != "VIX":
            if not vol_path:
                raise ValueError(f"{s.sym}: the {band} target band needs vol_path (data/{s.sym}_rv_1d.csv)")
            lit.VOL_SRC = {"VIX": vol_path, "VXN": vol_path}
        else:
            lit.VOL_SRC = {}
        if s.sessions:
            lit.SESSIONS = dict(s.sessions)
            lit.SESSION_CLASS = {n: ("asia" if n.startswith("asia") else "london" if n.startswith("lon") else "pre" if n == "pre"
                                     else "ny") for n in lit.SESSIONS}
        yield s
    finally:
        for n, v in saved.items():
            setattr(lit, n, v)
