"""REPLAY THEATER data (night 2026-11-27): one file per recent trading day for tools/web_public/nq/replay.html.
READ ONLY research: runs the bots' own engines on the bars on disk (the backtest twins, = what the PC bot runs), never trades or
touches a live file. Futures bars only (data/NQ_5m.csv: TradingView NQ1! + the PC's NinjaTrader bars).

    python -X utf8 tools/build_replay.py                       # the last 35 days -> the last session on disk (nightly: forward_paper's end)
    python -X utf8 tools/build_replay.py --since 2026-11-01 --until 2026-11-26
Out: tools/web_public/nq/replay/index.json (the days + their event counts) and replay/<YYYY-MM-DD>.json:
  bars    [[t, o, h, l, c], ...] 5-minute bars of the CME session (18:00 ET the evening before -> 16:55 ET)
  events  [{t, kind, bot, text, step?, side?, px?, stop?, target?, r?, usd?, id?}] sorted by time:
          LIT (the live model's twin): sweep (step 2) -> inducement (3) -> displacement + 5m CISD (4-5) -> entry (8) -> exit; every other
          LIT setup of the day where it stopped (tools/lit_setups_learn.funnel: the step + why, and what it would have made);
          ATLAS members EMA / MACD / S/R (engine/second, the account's one-position rule) entry -> exit
  notes   day-level facts without a time: the live accounts vs the twin (research/livegap/daily.json), order-flow paper rows
          (research/orderflow/real_verdict.json lane A: absorbed or not at a swept level)
  totals  LIT $ at its real size (the twin's micros), ATLAS $ at a fixed $250 risk a trade (labelled so)
Tests: python -X utf8 -m tests.test_replay
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
OUT = os.path.join(ROOT, "tools", "web_public", "nq", "replay")
NY = ZoneInfo("America/New_York")
PV, ATLAS_USD = 2.0, 250.0
ATLAS = {"ema_lon_vix": "EMA", "macd_sweep": "MACD", "sr_nyreclaim": "S/R"}
STEP_WORD = {0: "outside hours", 2: "sweep too shallow", 3: "no inducement", 4: "displacement too small", 6: "limit not armed",
             7: "never filled", 8: "taken", 9: "blocked by a day rule"}
LEVEL = {"pdh": "prior-day high", "pdl": "prior-day low", "onh": "overnight high", "onl": "overnight low", "orh": "opening-range high",
         "orl": "opening-range low", "ndog": "new-day gap", "nwog": "new-week gap"}


def hm(t) -> str:
    return dt.datetime.fromtimestamp(int(t), NY).strftime("%H:%M")


def sess_day(t) -> str:
    return (dt.datetime.fromtimestamp(int(t), NY) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def px(v) -> str:
    return f"{float(v):,.2f}"


def level_words(names) -> str:
    try:
        from engine.lit_live import _sweep_names
        w = _sweep_names(list(names or []))
        if isinstance(w, (list, tuple)):
            w = ", ".join(str(x) for x in w)
        return str(w or "a level")
    except Exception:  # noqa: BLE001
        return ", ".join(LEVEL.get(str(n).lower(), str(n)) for n in (names or [])[:3]) or "a level"


# ------------------------------------------------------------------------------------------------ sources
def bars(since: str, until: str):
    import pandas as pd
    d = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    lo = int(dt.datetime.fromisoformat(since).replace(tzinfo=NY).timestamp()) - 86400
    d = d[d.time >= lo].drop_duplicates("time").sort_values("time")
    out = {}
    for r in d.itertuples(index=False):
        day = sess_day(r.time)
        if since <= day <= until and dt.date.fromisoformat(day).weekday() < 5:
            out.setdefault(day, []).append([int(r.time), round(float(r.open), 2), round(float(r.high), 2), round(float(r.low), 2), round(float(r.close), 2)])
    return {k: v for k, v in out.items() if len(v) >= 60}


def lit_events(days: list):
    logging.disable(logging.WARNING)
    from engine import lit
    from tools import lit_final as F
    from tools import lit_rev_exit as R
    c = R.cx()
    M = c["M"]
    P = {**lit.DEFAULTS, **R.LIVE}
    Mm, Cm = F.market(P["ref"], P["extra_boxes"])
    T = lit.run_x(Mm, Cm, P, days, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    tt = Mm.t
    ev = []
    for k, t in enumerate(T):
        q = int(t.get("qty") or 0)
        if q <= 0:
            continue
        d = int(t["dir"])
        side = "long" if d > 0 else "short"
        sid = f"lit{k}"
        risk = abs(float(t["entry_px"]) - float(t["stop_px"]))
        rr = abs(float(t["target_px"]) - float(t["entry_px"])) / risk if risk else None
        si, ri = t.get("sweep_i"), t.get("i")              # i = the 5m CISD bar (ref_i is the swing it closed through)
        if si is not None:
            ev.append({"t": int(tt[int(si)]) + 300, "kind": "step", "bot": "LIT", "step": 2, "id": sid, "side": side,
                       "text": f"swept {level_words(t.get('swept'))}: the sweep a {side} needs (LIT step 2)"})
            ev.append({"t": int(tt[int(si)]) + 300, "kind": "step", "bot": "LIT", "step": 3, "id": sid, "side": side,
                       "text": f"inducement: {int(t.get('ind_n') or 0)} swing{'s' if int(t.get('ind_n') or 0) != 1 else ''} taken before the sweep (LIT step 3)"})
        if ri is not None:
            ev.append({"t": int(tt[int(ri)]) + 300, "kind": "step", "bot": "LIT", "step": 5, "id": sid, "side": side,
                       "text": "displacement + the 5m CISD closed back through: the setup is on (LIT steps 4-5)"})
        ev.append({"t": int(t["entry_t"]), "kind": "entry", "bot": "LIT", "step": 8, "id": sid, "side": side, "px": round(float(t["entry_px"]), 2),
                   "stop": round(float(t["stop_px"]), 2), "target": round(float(t["target_px"]), 2), "qty": q,
                   "text": f"entered {side} {q} MNQ at {px(t['entry_px'])}, stop {px(t['stop_px'])} ({risk:.1f} pts), target {px(t['target_px'])}"
                           + (f" ({rr:.1f}R)" if rr else "") + " (LIT step 8)"})
        if t.get("exit_t"):
            ev.append({"t": int(t["exit_t"]), "kind": "exit", "bot": "LIT", "id": sid, "side": side, "r": round(float(t["r"]), 2),
                       "usd": round(float(t["pnl"]), 2), "how": str(t.get("exit") or ""),
                       "text": f"out: {str(t.get('exit') or 'exit').replace('_', ' ').lower()} {float(t['r']):+.2f}R ({'+' if t['pnl'] >= 0 else '-'}${abs(t['pnl']):,.0f} at {q} MNQ)"})
    return ev


def lit_setups(days: set):
    """Every other LIT setup of the day: where it stopped (step + why) and what it would have made (lit_setups_learn.funnel)."""
    logging.disable(logging.WARNING)
    from tools import lit_setups_learn as LS
    E = LS.Engine()
    rows = LS.funnel(E, E.run(), E.run(LS.OPEN_ALL))
    ev = []
    for r in rows:
        if r["day"] not in days or r.get("step") == 8:
            continue
        side = "long" if int(r["dir"]) > 0 else "short"
        would = r.get("r")
        ev.append({"t": int(r["t"]) + 300, "kind": "setup", "bot": "LIT", "step": int(r["step"]), "side": side,
                   "text": f"{side} setup (sweep {float(r.get('depth') or 0):.1f} ATR, displacement {float(r.get('disp') or 0):.1f} ATR) stopped: "
                           f"{STEP_WORD.get(int(r['step']), r.get('why') or '?')}" + (f"; it would have made {float(would):+.2f}R" if would is not None else "")})
    return ev


def atlas_events(since: str, until: str):
    import pandas as pd
    logging.disable(logging.WARNING)
    from engine import second
    d5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    d1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    lo = int(dt.datetime.fromisoformat(since).replace(tzinfo=NY).timestamp())
    d5 = d5[d5.time >= lo - 86400 * 45].reset_index(drop=True)
    d1 = d1[d1.time >= lo - 86400 * 3].reset_index(drop=True)
    r = second.run(d5, one_min=d1, now=int(d5.time.max()) + 300, cfg=second.load_cfg(), lit=[])
    T = []
    for k, nm in ATLAS.items():
        for t in r["strategies"][k]["trades"]:
            if since <= t["day"] <= until and t.get("exit_kind"):
                T.append((nm, t))
    T.sort(key=lambda x: x[1]["entry_t"])
    ev, busy = [], 0
    for j, (nm, t) in enumerate(T):
        if t["entry_t"] < busy:                       # ATLAS's one position on the account: a member that starts while another is open is skipped
            continue
        busy = t["exit_t"]
        d = int(t["dir"])
        side = "long" if d > 0 else "short"
        sid = f"atl{j}"
        R_ = float(t["r"])
        ev.append({"t": int(t["entry_t"]), "kind": "entry", "bot": "ATLAS", "member": nm, "id": sid, "side": side, "px": round(float(t["entry"]), 2),
                   "stop": round(float(t["stop"]), 2), "target": round(float(t["target"]), 2) if t.get("target") else None,
                   "text": f"ATLAS {nm} entered {side} at {px(t['entry'])}, stop {px(t['stop'])}" + (f", target {px(t['target'])}" if t.get("target") else "")})
        ev.append({"t": int(t["exit_t"]), "kind": "exit", "bot": "ATLAS", "member": nm, "id": sid, "side": side, "r": round(R_, 2),
                   "usd": round(R_ * ATLAS_USD, 2), "how": str(t.get("exit_kind") or ""),
                   "text": f"ATLAS {nm} out: {str(t.get('exit_kind') or 'exit').replace('_', ' ').lower()} {R_:+.2f}R ({'+' if R_ >= 0 else '-'}${abs(R_ * ATLAS_USD):,.0f} at $250 risk)"})
    return ev


def notes_for(day: str, live: dict, of_rows: list) -> list:
    out = []
    for r in live.get(day, []):
        nm = {"z50k": "Zlarior 50K", "atlas25": "ATLAS 25K", "z25k2": "Zlarior 25K #2", "rapid25k": "Rapid EOD 25K"}.get(r.get("account"), "an account")
        lt, lu, tw = int(r.get("live_trades") or 0), float(r.get("live_usd") or 0), int(r.get("twin_trades") or 0)
        out.append({"kind": "live", "text": f"Live {nm}: {lt} trade{'s' if lt != 1 else ''} ({'+' if lu >= 0 else '-'}${abs(lu):,.0f}) vs the twin's {tw}"
                                           + (f"; gap {', '.join(sorted({d.get('kind') for d in r.get('diffs') or [] if d.get('kind')}))}" if r.get("diffs") else "")})
    for r in of_rows:
        if r.get("day") == day:
            out.append({"kind": "of", "text": f"Order flow (paper): {LEVEL.get(str(r.get('level')), str(r.get('level')))} swept "
                                             f"{'long' if r.get('d', 1) > 0 else 'short'} side, {'absorbed' if r.get('absorbed') else 'not absorbed'}"
                                             f" -> {'taken' if r.get('taken') else 'skipped'}, {float(r.get('R') or 0):+.2f}R"})
    return out


def build(since: str, until: str, say=print) -> dict:
    B = bars(since, until)
    days = sorted(B)
    if not days:
        return {"days": []}
    E = lit_events(days)
    try:
        E += lit_setups(set(days))
    except Exception as e:  # noqa: BLE001
        say(f"lit setups skipped: {e.__class__.__name__}: {e}")
    try:
        E += atlas_events(days[0], days[-1])
    except Exception as e:  # noqa: BLE001
        say(f"ATLAS skipped: {e.__class__.__name__}: {e}")
    live = {}
    try:
        for r in (json.load(open(os.path.join(ROOT, "research", "livegap", "daily.json"), encoding="utf-8")).get("rows") or []):
            live.setdefault(r.get("day"), []).append(r)
    except Exception:  # noqa: BLE001
        pass
    try:
        of_rows = json.load(open(os.path.join(ROOT, "research", "orderflow", "real_verdict.json"), encoding="utf-8")).get("rows") or []
    except Exception:  # noqa: BLE001
        of_rows = []
    os.makedirs(OUT, exist_ok=True)
    idx = []
    for day in days:
        ev = sorted([e for e in E if sess_day(e["t"]) == day], key=lambda e: (e["t"], {"step": 0, "setup": 1, "entry": 2, "exit": 3}.get(e["kind"], 4)))
        for e in ev:
            e["hm"] = hm(e["t"])
        lit_usd = round(sum(e.get("usd") or 0 for e in ev if e["kind"] == "exit" and e["bot"] == "LIT"), 2)
        atl_usd = round(sum(e.get("usd") or 0 for e in ev if e["kind"] == "exit" and e["bot"] == "ATLAS"), 2)
        doc = {"v": 1, "kind": "nq-replay-day", "day": day, "tz": "America/New_York", "tf": "5m", "bars": B[day], "events": ev,
               "notes": notes_for(day, live, of_rows),
               "totals": {"lit_usd": lit_usd, "lit_r": round(sum(e.get("r") or 0 for e in ev if e["kind"] == "exit" and e["bot"] == "LIT"), 2),
                          "atlas_usd": atl_usd, "atlas_r": round(sum(e.get("r") or 0 for e in ev if e["kind"] == "exit" and e["bot"] == "ATLAS"), 2)},
               "note": "The bots' backtest twins on the PC's own bars (what the PC bot runs). Read only: nothing here trades."}
        with open(os.path.join(OUT, f"{day}.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, separators=(",", ":"))
        idx.append({"day": day, "bars": len(B[day]), "trades": sum(1 for e in ev if e["kind"] == "entry"),
                    "setups": sum(1 for e in ev if e["kind"] == "setup") + len({e.get("id") for e in ev if e["kind"] == "entry" and e["bot"] == "LIT"}),
                    "lit_usd": lit_usd, "atlas_usd": atl_usd, "events": len(ev)})
    keep = {f"{x['day']}.json" for x in idx}
    for f in os.listdir(OUT):                     # old day files outside the window go
        if f.endswith(".json") and f != "index.json" and f not in keep:
            os.remove(os.path.join(OUT, f))
    out = {"v": 1, "kind": "nq-replay-index", "from": days[0], "to": days[-1], "days": idx[::-1]}
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    say(f"replay: {len(idx)} days {days[0]} -> {days[-1]}, {sum(x['trades'] for x in idx)} trades, {sum(x['events'] for x in idx)} events -> {os.path.relpath(OUT, ROOT)}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=(dt.date.today() - dt.timedelta(days=35)).isoformat())
    ap.add_argument("--until", default="2099-12-31")
    a = ap.parse_args(argv)
    build(a.since, a.until)
    return 0


if __name__ == "__main__":
    sys.exit(main())
