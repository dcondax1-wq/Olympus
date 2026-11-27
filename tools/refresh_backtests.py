"""Fresh backtests for the strategy rooms (day-strats 2026-11-27, lead: "make the backtests current"). Re-runs each engine through the
newest data/ bars (data/NQ_5m.csv, NQ_1m.csv, VIX_1d.csv: the cloud's nightly data pull) and writes ONLY the trades after each stored
research file's last day to research/strats_refresh/<s>.json. tools/build_strats.py appends them (src backtest, tagged "fresh replay").
The stored research files are never rewritten (other tools read them as they are).

A refresh is used only when its PARITY holds: the re-run over the stored file's dates must give the stored trades again.
  LIT    tools/lit_final.run(live_model.json "lit", sessions = every weekday with bars in data/NQ_5m.csv from the stored replay's first
         session; lit_final.SESS is a cached list that ends 2026-10-16, so it is not used) -> tools/export_backtest.lit_row, the
         research/lab/backtest_live.json shape. Parity: every stored trade (to its last day) byte-identical.
  ATLAS  engine/second.run (the live paper code, as tools/atlas_more.py fresh) cut at 17:00 ET of each session from 5 sessions before the
         stored book's end to the newest bar, the three members (EMA / MACD / S-R). The book = research/anatomy/trades_atlas.json's
         rule (tools/atlas.account_units): every member trade, skipped when LIT holds the opposite side, closed at LIT's opposite
         entry (at that minute's close); $ at a fixed $250 a trade. LIT's ARMED-setup block is not applied after the stored end
         (no record of armed windows in the cloud), as tools/atlas_edge_fresh.py. Parity: the overlap days' member trades = the
         stored research/second/*_best.json trades (same entry, direction, exit time).
  BLITZ  tools/blitz25k_lib.trades (numba) "lit+atlas" (never opposite LIT / ATLAS; the new days use the refreshed LIT / ATLAS
         trades) -> scalp_mo_lib.runlib_trades at $150, the research/runs/blitz_2026_backtest.json shape. Parity: every stored row
         to its last day identical (the trigger label aside, which the run library adds on save).
POSEIDON has no backtest to refresh: its rows are the real-tick paper signals (research/orderflow/*, rebuilt by the order-flow jobs).

    python -X utf8 tools/refresh_backtests.py [lit atlas blitz] [--check]     (learn_night's nqsite step runs it, then build_strats)
Research only: nothing here touches live_model*.json, second_model.json or any engine file.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time
import warnings
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "strats_refresh")
ET = ZoneInfo("America/New_York")
ATLAS_USD = 250.0
V = 1


def _load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def _dump(s, obj):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, s + ".json")
    raw = json.dumps(obj, separators=(",", ":"), default=lambda o: o.item() if hasattr(o, "item") else str(o))
    with open(p + ".tmp", "w", encoding="utf-8") as fh:
        fh.write(raw)
    os.replace(p + ".tmp", p)
    return p


def _canon(x):
    return json.dumps(x, sort_keys=True, default=lambda o: o.item() if hasattr(o, "item") else str(o))


# ------------------------------------------------------------------------------------------------ LIT
def lit():
    from engine import lit as L
    from tools import export_backtest as EB
    from tools import lit_final as F
    lm = _load("live_model.json")
    P = {**L.DEFAULTS, **(lm.get("lit") or {})}
    bt = _load("research/lab/backtest_live.json")
    stored, end = bt["trades"], bt["trades"][-1]["day"]
    first = (bt.get("meta", {}).get("data") or {}).get("first_session") or stored[0]["day"]
    M, C = F.market(P["ref"], P["extra_boxes"])
    sess = sorted({str(d) for d, w in zip(M.dates, M.dow) if w < 5 and str(d) >= first})
    T = sorted(F.run(P, sess), key=lambda t: t["entry_t"])
    cand = {(z["i"], z["dir"]): z for z in C}
    rows = [EB.lit_row(t, cand[(t["i"], t["dir"])], P, lm.get("label") or "LIT") for t in T]
    for r in rows:
        r.pop("low", None)
    old = [r for r in rows if r["day"] <= end]
    ok = _canon(old) == _canon(stored)
    new = [r for r in rows if r["day"] > end]
    return {"v": V, "s": "lit", "ok": ok, "stored_end": end, "data_to": sess[-1], "sessions": len(sess),
            "parity": {"stored": len(stored), "rerun_to_stored_end": len(old), "identical": ok, "params_match": bt["meta"]["params"] == json.loads(_canon(P))},
            "n_new": len(new), "usd_new": round(sum(r["pnl"] for r in new), 2), "trades": new if ok else []}


# ------------------------------------------------------------------------------------------------ ATLAS
KEYS = {"ema_lon_vix": "EMA", "macd_sweep": "MD", "sr_nyreclaim": "SR"}
FILES = {"EMA": "ema_best", "MD": "md_best", "SR": "sr_best"}


def _replay_atlas(days):
    import numpy as np
    import pandas as pd
    from engine import second
    from engine.data import load, load_ltf
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    cut0 = int(dt.datetime.combine(dt.date.fromisoformat(days[0]) - dt.timedelta(days=75), dt.time(0, 0), ET).timestamp())
    df5 = df5[df5["time"] >= cut0].reset_index(drop=True)
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
    T5 = df5["time"].values
    cfg = second.load_cfg()
    cfg = {**cfg, "strategies": {k: {**v, "on": True} for k, v in cfg["strategies"].items() if k in KEYS}}
    got, errs = collections.defaultdict(list), []
    for d in days:
        now = int(dt.datetime.combine(dt.date.fromisoformat(d), dt.time(17, 0), ET).timestamp())
        cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
        cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
        r = second.run(cut5, one_min=cut1, now=now, cfg=cfg, lit=[])
        for k, s in r["strategies"].items():
            if s.get("error"):
                errs.append((d, k, str(s["error"])[:120]))
            for t in s["trades"]:
                if t["day"] == d and t.get("exit_t"):
                    got[KEYS[k]].append(t)
    return got, errs


def _close_at(ts):
    """the 1m close of the minute that holds ts (data/NQ_1m.csv)"""
    import numpy as np
    import pandas as pd
    if "b" not in _C1:
        b = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        _C1["b"] = (b["time"].values, b["close"].values)
    t, c = _C1["b"]
    i = int(np.searchsorted(t, ts, side="right")) - 1
    return float(c[max(0, i)])


_C1: dict = {}


def atlas(lit_rows=None):
    A = _load("research/anatomy/trades_atlas.json")
    c = {k: i for i, k in enumerate(A["cols"])}
    end = max(r[c["day"]] for r in A["rows"])
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"), usecols=["time"])
    alld = sorted({dt.datetime.fromtimestamp(int(t) + 6 * 3600, ET).date().isoformat() for t in df["time"].values[-30000:]})
    alld = [d for d in alld if dt.date.fromisoformat(d).weekday() < 5]
    before = [d for d in alld if d <= end][-5:]
    days = before + [d for d in alld if d > end]
    got, errs = _replay_atlas(days)
    parity = {}
    ok = True
    for m, f in FILES.items():
        st = {(int(t["entry_t"]), int(t["dir"])): t for t in _load(f"research/second/{f}.json")["trades"] if t["day"] in before}
        g = {(int(t["entry_t"]), int(t["dir"])): t for t in got.get(m, []) if t["day"] in before}
        same = sum(1 for k in set(st) & set(g) if int(st[k]["exit_t"]) == int(g[k]["exit_t"]))
        parity[m] = {"stored": len(st), "replay": len(g), "same_entry_and_exit": same}
        ok = ok and same == len(st) == len(g)
    # the book on the new days: every member trade; LIT's opposite open trade skips it, LIT's opposite entry closes it
    lit_t = collections.defaultdict(list)
    for t in _load("research/lab/backtest_live.json")["trades"] + list(lit_rows or []):
        lit_t[t["day"]].append((int(t["entry_t"]), int(t["exit_t"] or t["entry_t"]), 1 if str(t["side"]).upper() == "LONG" else -1))
    pr = {"EMA": 0, "MD": 1, "SR": 2}
    U = sorted([(t, m) for m in ("EMA", "MD", "SR") for t in got.get(m, []) if t["day"] > end], key=lambda x: (int(x[0]["entry_t"]), pr[x[1]]))
    rows, skipped, cut = [], 0, 0
    for t, m in U:
        e, x, d = int(t["entry_t"]), int(t["exit_t"]), int(t["dir"])
        L = [z for z in lit_t.get(t["day"], ()) if z[2] != d]
        if any(a <= e < b for a, b, _ in L):
            skipped += 1
            continue
        r, xp, kind = float(t["r"]), t.get("exit"), t.get("exit_kind")
        nxt = min((a for a, _, _ in L if e < a < x), default=None)
        if nxt is not None:
            rp = float(t["risk_pts"]) or 1.0
            cost_r = r - (float(t["exit"]) - float(t["entry"])) * d / rp
            xp = _close_at(nxt)
            r = round((xp - float(t["entry"])) * d / rp + cost_r, 4)
            x, kind = nxt, "HEDGE"
            cut += 1
        rows.append({"day": t["day"], "entry_t": e, "exit_t": x, "dir": d, "entry": t.get("entry"), "stop": t.get("stop"),
                     "target": t.get("target"), "exit": xp, "exit_kind": kind, "r": round(r, 4), "usd": round(r * ATLAS_USD, 1),
                     "member": {"EMA": "EMA", "MD": "MACD", "SR": "S/R"}[m], "setup": t.get("setup") or ""})
    return {"v": V, "s": "atlas", "ok": ok, "stored_end": end, "data_to": days[-1], "parity": {"overlap_days": before, **parity},
            "errors": errs[:10], "skipped_lit_opposite": skipped, "closed_at_lit_entry": cut, "usd_rule": f"fixed ${ATLAS_USD:.0f} a trade (the stored book's)",
            "armed_block": "LIT's armed-setup block not applied after the stored end (no record in the cloud)",
            "n_new": len(rows), "usd_new": round(sum(r["usd"] for r in rows), 1), "trades": rows if ok else []}


# ------------------------------------------------------------------------------------------------ BLITZ
def blitz(lit_rows=None, atlas_rows=None):
    warnings.filterwarnings("ignore")
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    from tools import blitz25k_lib as K
    from tools import scalp_mo_lib as M
    from tools import scalp_na_combo as CB
    from tools import scalp_na_lib as N
    st = _load("research/runs/blitz_2026_backtest.json")
    cols, end = st["trade_cols"], st["trades"][-1][0]
    # the new days' LIT / ATLAS trades join what BLITZ must never be opposite to (the stored ones end mid-October)
    old_lit, old_atl = CB.lit_by_day, CB.atlas_by_day
    add_l, add_a = collections.defaultdict(list), collections.defaultdict(list)
    for t in lit_rows or []:
        add_l[t["day"]].append((int(t["entry_t"]), int(t["exit_t"] or t["entry_t"]), 1 if str(t["side"]).upper() == "LONG" else -1))
    for t in atlas_rows or []:
        add_a[t["day"]].append((int(t["entry_t"]), int(t["exit_t"]), int(t["dir"])))

    def lit_by_day():
        by = old_lit()
        for d, v in add_l.items():
            if d > end and d not in by:
                by[d] = list(v)
        return by

    def atlas_by_day():
        by = old_atl()
        for d, v in add_a.items():
            if d > end and d not in by:
                by[d] = list(v)
        return by
    CB.lit_by_day, CB.atlas_by_day = lit_by_day, atlas_by_day
    try:
        K._AC.clear()
        TT = K.trades({}, "lit+atlas")
    finally:
        CB.lit_by_day, CB.atlas_by_day = old_lit, old_atl
    B1, B5 = N.bars(1), N.bars(5)
    S1 = N.sessions(B1, "H1") + N.sessions(B1, "H2")
    R = N.sessions(B5, "R")
    Ts = M.runlib_trades(N.span_trades(TT[5], R) + [t for t in TT[1] if t["day"] >= S1[0]], 150.0, 20)
    for t in Ts:
        t["trigger"] = t.get("trigger") or "blitz"
        t.pop("low", None)
    def eq(a, b):                      # the stored file keeps 3 decimals: floats equal within 0.001, the rest exactly
        return len(a) == len(b) and all((abs(x - y) <= 1e-3) if isinstance(x, float) and isinstance(y, (int, float)) else x == y for x, y in zip(a, b))
    mine = [[t.get(k) for k in cols] for t in Ts if t["day"] <= end]
    same = sum(1 for a, b in zip(mine, st["trades"]) if eq(a, b))
    ok = same == len(st["trades"]) == len(mine)
    new = [[t.get(k) for k in cols] for t in Ts if t["day"] > end]
    return {"v": V, "s": "blitz", "ok": ok, "stored_end": end, "data_to": S1[-1], "cols": cols,
            "parity": {"stored": len(st["trades"]), "rerun_to_stored_end": len(mine), "identical": same},
            "blocks": f"never opposite LIT / ATLAS: the stored trades to {end}, the refreshed ones after",
            "n_new": len(new), "usd_new": round(sum(r[cols.index("pnl")] for r in new), 2), "trades": new if ok else []}


def main(argv=None) -> int:
    args = [a for a in (argv if argv is not None else sys.argv[1:]) if not a.startswith("--")]
    want = args or ["lit", "atlas", "blitz"]
    t0, out, rc = time.time(), {}, 0
    if "lit" in want or "atlas" in want or "blitz" in want:
        out["lit"] = lit()
    if "atlas" in want or "blitz" in want:
        out["atlas"] = atlas(out["lit"]["trades"])
    if "blitz" in want:
        out["blitz"] = blitz(out["lit"]["trades"], out["atlas"]["trades"])
    for s in want:
        o = out[s]
        o["built"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        p = _dump(s, o)
        print(f"{s}: parity {'OK' if o['ok'] else 'FAILED'} {json.dumps(o['parity'])[:200]} | {o['n_new']} new trades after {o['stored_end']} "
              f"to {o['data_to']}, ${o['usd_new']} -> {os.path.relpath(p, ROOT)}")
        rc |= 0 if o["ok"] else 1
    print(f"done in {time.time() - t0:.0f}s")
    return rc


if __name__ == "__main__":
    sys.exit(main())
