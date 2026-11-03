"""One run of the data machine: new bars -> event table (incremental) -> grid + guard -> the study -> the files.

Outputs (research/datacity/, small JSON; the page gets a copy of city.json + jarvis.json):
  city.json         every building the page draws (districts, LIT tower, top 10, discoveries, lift, guard)
  leaderboard.json  the top 60 with every number, sparkline and history
  discoveries.json  plain-language findings, new / rising / decaying flags, today's fired setups, strategies
  summary.json      counts, guard (FDR, placebo, holdout), timings, data range
  history.json      one compact row per day of data (the top 100 ids with their R, $ and n): what rises and what decays
plus run datacity_holdout_portfolio in research/runs/ (tools/runlib.py).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time

import numpy as np

from . import bars as B
from . import features as F
from . import grid as G
from . import report as RP
from . import skyline as SK
from . import store

OUT = B.OUT
WEB = os.path.join(B.ROOT, "tools", "web_public", "datacity")
HIST_KEEP = 120                    # ~6 months of nightly rows (~0.5 MB): research/datacity JSON stays <= 3 MB
RUN_ID = "datacity_holdout_portfolio"


def _json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not JSON: {type(o).__name__}")


def write_json(path, obj):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"), default=_json_default)
    os.replace(tmp, path)


def load_history(out) -> dict:
    try:
        with open(os.path.join(out, "history.json"), encoding="utf-8") as fh:
            h = json.load(fh)
        return h if isinstance(h.get("runs"), list) else {"runs": []}
    except (OSError, ValueError):
        return {"runs": []}


def add_history(history, row) -> dict:
    """Append a run; a rerun on the same day of data replaces that day's row."""
    runs = [r for r in history["runs"] if r.get("last_day") != row["last_day"]] + [row]
    return {"runs": runs[-HIST_KEEP:]}


def heartbeat_bars(out, log) -> dict:
    """Append the PC's NinjaTrader 5m bars (heartbeat / dashboard branches) to the extra store; never fails the run."""
    try:
        base = B.read_csv(B.NQ_5M)
        info = B.append_extra(B.fetch_pc_bars(), int(base["time"].max()), path=os.path.join(out, "bars_extra.csv.gz"))
    except Exception as e:                                 # a git / network problem only means no new bars this run
        info = {"error": str(e)[:200]}
    log(f"heartbeat bars: {info}")
    return info


def save_run(T, S, members, log):
    """The holdout portfolio as a run in research/runs (paper, status info)."""
    from tools import runlib as rl
    try:
        rl.save(RUN_ID, "Data city: the 2021-24 FDR picks as one portfolio (paper)", "other",
                "Do the data city's 2021-24 discoveries still make money in 2025-26?", params={"members": members},
                trades=T, scored=S, status="info",
                verdict=(f"Picked on 2021-24 only (BH FDR there), 1 trade a day at ${RP.RISK_USD:.0f} risk. "
                         f"{rl.line(S, '2026')}. {rl.line(S, '2021-25')}.")[:900],
                notes="tools/datacity (research only, never routed)", writeup="datacity", tags=["datacity"])
    except Exception as e:                                 # the run library is a side output
        log(f"runlib save skipped: {e}")


def run(full=False, heartbeat=False, out=OUT, web=WEB, store_run=True, df=None, src=None, log=print, now=None):
    """Run the machine; returns {file name: object} of what it wrote."""
    t0 = time.time()
    now = now or t0
    os.makedirs(out, exist_ok=True)
    hb = heartbeat_bars(out, log) if heartbeat else None
    if df is None:
        df = B.load_nq(extra_path=os.path.join(out, "bars_extra.csv.gz"))
    feat, how = store.event_table(df, full=full, cache=os.path.join(out, "_cache"), src=src, log=log)
    t1 = time.time()
    grid = G.Grid(feat)
    combos = G.enumerate_combos()
    rows = grid.score_all(combos)
    guard = G.guard(combos, rows)
    t2 = time.time()
    log(f"grid: {guard['tried']} tried, {guard['tested']} tested, {guard['fdr_pos']} pass FDR (placebo {guard['placebo_fdr']}), "
        f"{t2 - t1:.1f}s")

    history = load_history(out)
    st = RP.Study(grid, combos, rows, guard, history)
    leaderboard = st.leaderboard()
    discoveries = st.discoveries()
    strategies, port_T, port_S = st.strategies()
    if store_run and port_T:
        save_run(port_T, port_S, strategies[-1]["members"], log)
    today = st.today()
    tl = SK.Today(grid)
    plugins = SK.collect_plugins(os.path.join(out, "plugins"))
    buildings = st.buildings()
    for b in buildings:                                   # the Today layer on the full cards
        i = st.index[b["id"]]
        f = tl.flag(combos[i], rows[i])
        if f:
            b["td"] = 2 if f == SK.FL_FIRED else 1
    shown = SK.tested(st)
    history = add_history(history, st.history_row(now))
    built = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = {"v": 1, "built": built, "t": int(now),
               "data": {"source": "TradingView CME NQ1! 5m (data/NQ_5m.csv) + PC NinjaTrader MNQ 5m (heartbeat)",
                        "first_day": str(grid.days[0]), "last_day": st.last_day, "days": len(grid.days),
                        "events": len(grid.ev["t"])},
               "cost": {"commission": F.COMM, "slippage_ticks": F.SLIP_TICKS, "per_micro_rt": F.COST},
               "method": {"entry": "next 5m bar open", "stop": f"structure, 1 tick beyond (min {F.MIN_STOP:g} / max {F.MAX_STOP:g} pts)",
                          "target": f"{F.TGT_R:g}R, else the close after {F.H * 5} min or at the day's end", "one_a_day": True,
                          "test": f"two-sided t on R after costs (equal $ risk), BH FDR q={G.FDR_Q}, sign-flip placebo, "
                                  "2021-24 -> 2025-26 holdout"},
               "guard": guard, "run": how, "heartbeat": hb,
               "seconds": {"events": round(t1 - t0, 1), "grid": round(t2 - t1, 1), "total": round(time.time() - t0, 1)}}
    city = {"v": 1, "built": built, "t": int(now), "last_day": st.last_day, "summary": summary, "lit": RP.lit_tower(),
            "buildings": buildings, "strategies": strategies,
            "top10": [{k: d[k] for k in ("id", "lab", "e", "w", "tpw", "cls", "tr")} for d in leaderboard[:10]],
            "discoveries": discoveries, "today": today, "lift": st.lift(),
            "districts": list(G.DISTRICTS) + ["strategies", "discoveries", "harbor"],
            "sections": SK.sections(guard), "dict": SK.dictionary(RP.WIN_LABEL),
            "skyline": SK.skyline(st, tl, skip={st.index[b["id"]] for b in buildings}),
            "today_layer": tl.summary(combos, rows, shown), "weather": SK.weather(), "harbor": SK.harbor(),
            "plugins": [name for name, _ in plugins]}
    files = {"city.json": city, "leaderboard.json": {"v": 1, "built": built, "rows": leaderboard},
             "discoveries.json": {"v": 1, "built": built, "last_day": st.last_day, "items": discoveries, "today": today,
                                  "strategies": strategies},
             "summary.json": summary, "history.json": history,
             "jarvis.json": RP.jarvis_card(guard, leaderboard, st.last_day, built, now)}
    for name, obj in files.items():
        write_json(os.path.join(out, name), obj)
    for name, obj in plugins:                              # plug-in districts ride along with city.json (datacity branch)
        write_json(os.path.join(out, name), obj)
    if web:
        os.makedirs(web, exist_ok=True)
        for name in ("city.json", "jarvis.json"):
            write_json(os.path.join(web, name), files[name])
        for name, obj in plugins:                          # plug-in districts next to the page (city.json lists them)
            write_json(os.path.join(web, name), obj)
    log(f"datacity: {len(city['buildings'])} buildings, {len(leaderboard)} on the leaderboard, {len(today)} fired on "
        f"{st.last_day}, {time.time() - t0:.1f}s")
    return files
