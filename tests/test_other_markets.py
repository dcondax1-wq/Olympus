"""LIT on other CME micros (docs/OTHER_MARKETS.md): importer, engine/lit_markets.py and tools/other_markets.py on SYNTHETIC
NinjaTrader exports (tests/synth_nt.py; no real MGC / MCL / M2K data exists yet).

    python -X utf8 -m tests.test_other_markets        # ~1 min

  a. NinjaTrader format: close stamp -> open stamp, the time zone found from the 17:00-18:00 ET halt (Chicago and New York
     exports), every bar back exactly, 5m / 15m / 1h built, the continuous export writes an empty rolls file
  b. per-contract exports: volume roll on the session after the new contract trades more, gap = new - old at the last
     common minute, back-adjusted series = the newest contract's prices everywhere, data/<SYM>_rolls.json written
  c. realized-vol band file: one row per trading date from the 21st on, known at that date's close only
  d. engine/lit_markets.use(): the market's numbers inside, NQ's back after (also after an error), refused in a live process;
     params(): stop 1 tick beyond the sweep, stops x k on the tick grid, breakeven = costs (NQ's own 1.25 reproduced)
  e. units(): MNQ-equivalent points give back each trade's own $ at any size (the commission difference folded in)
  f. NQ untouched: NQ setups + live-config trades on a 2026 slice identical before and after a gold run in the same process
  g. the whole proof on a synthetic MGC export (Chicago time, 2026 Jan-Oct): every span's numbers, correlation, the
     one-account test, a verdict; crude (MCL, per-contract files) and M2K (VIX band) run too
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import lit_markets as IN  # noqa: E402
from engine import lit  # noqa: E402
from tests import synth_nt as SN  # noqa: E402
from tools import nt_import as NI  # noqa: E402
from tools import other_markets as OM  # noqa: E402

RESULTS = []
QUIET = lambda *a, **k: None  # noqa: E731


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)


def t_import(tmp):
    b = SN.base_bars("2026-03-02", "2026-04-30", 2500.0, 0.10, seed=3)
    for tz in ("America/Chicago", "America/New_York"):
        d = os.path.join(tmp, "a_" + tz.split("/")[1])
        SN.write_nt(b, os.path.join(d, "exp", "MGC ##-##.Last.txt"), tz, 0.10)
        line = open(os.path.join(d, "exp", "MGC ##-##.Last.txt")).readline().strip()
        info = NI.build("MGC", [os.path.join(d, "exp")], os.path.join(d, "data"), log=QUIET)
        m1 = pd.read_csv(os.path.join(d, "data", "MGC_1m.csv"))
        check(f"a. {tz} export: zone found from the halt", info["tz"] == tz, info["tz_halt_share"])
        check(f"a. {tz}: every 1m bar back, open-stamped, same prices",
              len(m1) == len(b) and (m1["time"].values == b["time"].values).all()
              and np.abs(m1["close"].values - b["close"].values).max() < 1e-9, line)
    d = os.path.join(tmp, "a_Chicago", "data")
    ok = all(os.path.exists(os.path.join(d, f"MGC_{tf}.csv")) for tf in ("5m", "15m", "1h"))
    five = pd.read_csv(os.path.join(d, "MGC_5m.csv"))
    check("a. 5m / 15m / 1h written, 5m bars on the 5-minute grid", ok and (five["time"] % 300 == 0).all())
    r = json.load(open(os.path.join(d, "MGC_rolls.json")))
    check("a. continuous export: rolls file says NinjaTrader back-adjusted, no gaps", r["rolls"] == [] and "back adjusted" in r["method"])
    first = pd.Timestamp(int(five["time"].iloc[0]), unit="s", tz="UTC").tz_convert("America/New_York")
    check("a. the first bar opens 18:00 ET (Globex open), not at its close", (first.hour, first.minute) == (18, 0), str(first))
    return b


def t_rolls(tmp, b):
    old, new, rd = SN.contracts(b, "2026-04-10", 0.35, 0.01)
    for x in (old, new):
        for c in ("open", "high", "low", "close"):
            x[c] = np.round(x[c] / 30.0, 2)            # crude-like prices (tick 0.01)
    d = os.path.join(tmp, "b")
    SN.write_nt(old, os.path.join(d, "exp", "MCL 05-26.Last.txt"), "America/New_York", 0.01)
    SN.write_nt(new, os.path.join(d, "exp", "MCL 06-26.Last.txt"), "America/New_York", 0.01)
    SN.write_nt(old, os.path.join(d, "exp", "MCL ##-##.Last.txt"), "America/New_York", 0.01)   # ignored: per-contract wins
    info = NI.build("MCL", [os.path.join(d, "exp")], os.path.join(d, "data"), log=QUIET)
    r = json.load(open(os.path.join(d, "data", "MCL_rolls.json")))
    rl = r["rolls"]
    check("b. per-contract files win over the continuous one", info["kind"] == "per-contract" and len(info["files"]) == 2)
    check("b. one roll MCLK26 -> MCLM26 on the session after the volume flip", len(rl) == 1 and rl[0]["from"] == "MCLK26"
          and rl[0]["to"] == "MCLM26" and rl[0]["switch_day"] == "2026-04-13", rl)
    # crude-like prices: the new contract = (old + 0.35) / 30 rounded per bar; the gap is measured at the last common minute
    m1 = pd.read_csv(os.path.join(d, "data", "MCL_1m.csv"))
    newer = new.set_index("time")["close"]
    st = rl[0]["switch_t"] if rl else 0
    after = m1[m1["time"] >= st].set_index("time")["close"]
    before = m1[m1["time"] < st].set_index("time")["close"]
    oldc = old.set_index("time")["close"]
    check("b. after the switch = the new contract's own prices", np.abs(after - newer.reindex(after.index)).max() < 1e-9)
    check("b. before the switch = old contract + the gap (additive back-adjustment to the newest)",
          np.abs(before - (oldc.reindex(before.index) + rl[0]["gap"])).max() < 1e-9 and abs(rl[0]["gap"]) > 0, rl[0]["gap"] if rl else None)


def t_rv(tmp):
    d = os.path.join(tmp, "a_Chicago", "data")
    rv = pd.read_csv(os.path.join(d, "MGC_rv_1d.csv"))
    five = pd.read_csv(os.path.join(d, "MGC_5m.csv"))
    days = sorted(set(NI.tday_of(five["time"])))
    check("c. rv file: a row per trading date from the 21st date on", list(rv["date"]) == days[20:] and (rv["close"] > 0).all())
    cut = five[NI.tday_of(five["time"]) <= days[25]]
    rv2 = NI.rv_frame(cut)
    check("c. no look-ahead: a date's value uses closes up to that date only",
          np.allclose(rv2.set_index("date")["close"], rv.set_index("date")["close"].reindex(rv2["date"])))


def t_instruments():
    nq = (lit.TICK, lit.PV, lit.COMM, lit.SLIP, lit.MAX_MICROS, lit.BU_TOL_MIN, dict(lit.VOL_SRC), lit.SESSIONS)
    g = IN.spec("MGC")
    with IN.use(g, 0.1, vol_path="/x/MGC_rv_1d.csv"):
        inside = (lit.TICK, lit.PV, lit.COMM, lit.SLIP, lit.BU_TOL_MIN, lit.VOL_SRC.get("VIX"))
    check("d. inside use(MGC): tick 0.10, $10/pt, MGC commission, 1-tick slippage, own vol file",
          inside == (0.10, 10.0, g.comm, 0.10, 0.2, "/x/MGC_rv_1d.csv"), inside)
    back = (lit.TICK, lit.PV, lit.COMM, lit.SLIP, lit.MAX_MICROS, lit.BU_TOL_MIN, dict(lit.VOL_SRC), lit.SESSIONS)
    check("d. NQ's numbers back after the block", back == nq and lit.SESSIONS is nq[7])
    try:
        with IN.use(IN.spec("MCL"), 0.01, vol_path="/x"):
            raise KeyError("boom")
    except KeyError:
        pass
    check("d. NQ's numbers back after an error inside the block",
          (lit.TICK, lit.PV, lit.COMM, lit.SLIP, lit.BU_TOL_MIN, dict(lit.VOL_SRC)) == nq[:4] + nq[5:7])
    sys.modules["engine.live"] = type(sys)("engine.live")
    try:
        try:
            with IN.use(g, 0.1, vol_path="/x"):
                pass
            refused = False
        except RuntimeError:
            refused = True
    finally:
        del sys.modules["engine.live"]
    check("d. refused in a process with the live loop loaded", refused and lit.TICK == 0.25)
    check("d. breakeven = costs: NQ 1.25 (live), MGC 0.40, MCL 0.04, M2K 0.50",
          (IN.be_off(IN.spec("NQ", 1.90)), IN.be_off(g), IN.be_off(IN.spec("MCL")),
           IN.be_off(IN.spec("M2K"))) == (1.25, 0.4, 0.04, 0.5))
    p = IN.params(IN.spec("MCL"), 0.0061)
    check("d. MCL params: stop 1 tick beyond the sweep, 8 / 80 x k on the 0.01 grid",
          p["stop_buf"] == 0.01 and p["min_stop"] == 0.05 and p["max_stop"] == 0.49, p)
    pp = IN.params(g, 0.1, "pit")
    check("d. gold 'pit' variant: entries to 13:00 ET, flat 13:25 ET", pp["window"] == [[120, 780]] and pp["flat_mod"] == 805)
    check("d. --comm replaces the estimate", IN.spec("MGC", 1.5).comm == 1.5 and IN.SPECS["MGC"].comm != 1.5)


def t_units():
    s = IN.spec("MCL")
    T = [{"day": "2026-05-04", "entry_t": 1, "exit_t": 2, "dir": 1, "qty": 7, "risk_pts": 0.12, "target_px": 70.5, "entry_px": 70.1,
          "pnl": 0.31 * 100 * 7 - s.comm * 7, "low": -0.05 * 100 * 7 - s.comm * 7, "exit": "TARGET"}]
    u = OM.units(T, s)[0]
    ok = True
    for q in (1, 3, 7, 40):
        own = 0.31 * 100 * q - s.comm * q
        ok &= abs((u["pts"] * 2.0 * q - 1.90 * q) - own) < 1e-9
    check("e. MNQ-equivalent units give back the trade's own $ at any size", ok and abs(u["risk"] - 0.12 * 50) < 1e-9, u)


def nq_slice_hash():
    from engine.data import load
    b = load("NQ", "5m")
    i = int(np.searchsorted(np.asarray(b.date_str), "2026-05-01"))
    j = int(np.searchsorted(np.asarray(b.date_str), "2026-07-01"))
    M = lit.Market(bars=b.slice(i, j))
    C = lit.candidates(M, ref="cisd")
    P = dict(OM.L.LIVE, tf="5m")
    T = lit.run_x(M, C, P, None, B5=lit.bars_5m(M))
    return hashlib.sha256(pickle.dumps((C, T, M.ctx), protocol=4)).hexdigest(), len(T)


def t_proof(tmp, h0):
    d = os.path.join(tmp, "g", "data")
    b = SN.base_bars("2026-01-02", "2026-10-16", 2400.0, 0.10, seed=11)
    SN.write_nt(b, os.path.join(d, "MGC ##-##.Last.txt"), "America/Chicago", 0.10)
    ok = OM.ensure_data("MGC", d, log=QUIET)
    res = OM.proof("MGC", d, n_mc=20, out_dir=os.path.join(tmp, "g", "out"), log=QUIET)
    check("g. one command imports the export it finds in data/ and builds the files", ok and os.path.exists(os.path.join(d, "MGC_1m.csv")))
    v = res["variants"]
    check("g. every pre-registered variant ran (main, stops x0.8 / x1.25, pit, VIX band)", set(v) == {"main", "stop08", "stop125", "pit", "vix"})
    h1, h2 = v[res["pick"]].get("H1", {}), v[res["pick"]].get("H2", {})
    check("g. both 2026 halves scored: trades/week, PF, net $, $/month, max DD; trades happened",
          all(k in h1 and k in h2 for k in ("tpw", "pf", "net", "per_month", "dd")) and h1["n"] > 0 and h2["n"] > 0, (h1, h2))
    check("g. 2021-25 skipped when the export does not reach back", "2021-25" not in v["main"])
    tg = res["together"]
    check("g. correlation with LIT-NQ in [-1, 1] and the one-account test for both halves",
          all(-1 <= tg[s]["corr_daily"] <= 1 and "funded" in tg[s]["nq_plus_x"] and "eval" in tg[s]["x"] for s in ("H1", "H2")))
    check("g. costs are in (commission + 2 ticks as % of R reported)", v["main"]["cost_pct_of_R"] and v["main"]["cost_pct_of_R"] > 0)
    check("g. a verdict with reasons, written to research json", isinstance(res["verdict"]["pass"], bool) and res["verdict"]["text"]
          and os.path.exists(os.path.join(tmp, "g", "out", "MGC.json")))
    h1_, n1 = nq_slice_hash()
    check("f. NQ setups + trades identical before and after the gold run (same process)", h1_ == h0[0] and n1 == h0[1] and n1 > 0)
    # crude from per-contract files (crude-like prices) and M2K on the VIX band: they run end to end
    dc = os.path.join(tmp, "g2", "data")
    bc = SN.base_bars("2026-01-02", "2026-10-16", 72.0, 0.01, vol_year=0.35, seed=5)
    o, n, _ = SN.contracts(bc, "2026-05-15", 0.42, 0.01)
    SN.write_nt(o, os.path.join(dc, "nt_export", "MCL", "MCL 06-26.Last.txt"), "America/New_York", 0.01)
    SN.write_nt(n, os.path.join(dc, "nt_export", "MCL", "MCL 07-26.Last.txt"), "America/New_York", 0.01)
    OM.ensure_data("MCL", dc, log=QUIET)
    rc = OM.proof("MCL", dc, n_mc=10, out_dir=os.path.join(tmp, "g2", "out"), log=QUIET)
    check("g. MCL (per-contract files in data/nt_export/MCL) runs: 1 roll, trades in both halves",
          json.load(open(os.path.join(dc, "MCL_rolls.json")))["rolls"] and rc["variants"]["main"]["H1"]["n"] > 0
          and rc["variants"]["main"]["H2"]["n"] > 0)
    dr = os.path.join(tmp, "g3", "data")
    br = SN.base_bars("2026-01-02", "2026-10-16", 2300.0, 0.10, vol_year=0.22, seed=9)
    SN.write_nt(br, os.path.join(dr, "M2K ##-##.Last.txt"), "America/New_York", 0.10)
    OM.ensure_data("M2K", dr, log=QUIET)
    rr = OM.proof("M2K", dr, n_mc=10, out_dir=os.path.join(tmp, "g3", "out"), log=QUIET)
    check("g. M2K runs on the VIX band, no pit variant", set(rr["variants"]) == {"main", "stop08", "stop125"}
          and rr["variants"]["main"]["H1"]["n"] > 0)
    check("f. NQ still identical after crude and Russell", nq_slice_hash() == h0)


def main() -> int:
    h0 = nq_slice_hash()
    tmp = tempfile.mkdtemp(prefix="othermk-test-")
    try:
        b = t_import(tmp)
        t_rolls(tmp, b)
        t_rv(tmp)
        t_instruments()
        t_units()
        t_proof(tmp, h0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RESULTS)
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
