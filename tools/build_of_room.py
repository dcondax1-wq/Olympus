"""The Order Flow LIVE ROOM's data (big-ofreal 2026-11-26) -> tools/web_public/nq/of_room.json. Data only: no page, no sw.js edit
(the lead wires the page). Paper research: nothing here trades.

Sources, newest first:
  live    data/of_paper.json (engine/of_paper.py, the pillar's paper bot on the PC) when its day = today ET
  replay  else the newest pulled real tick day (data/pc_days/<day>/of, logs/datapipe/days) through the same paper bot
          (engine/of_paper.replay_summary) = "last recorded day"
  + research/orderflow/real_verdict.json (tools/of_realday_verdict.py): the verdict line and the forward score n / 20.
Contents: today's levels with the absorption read at each (absorbed / not absorbed / untouched), the paper rows (lane A), Zlarior's
lane B decisions (take / skip + won / lost, NO dollar amounts or account names: the site is public), the forward score, one line.
    python -X utf8 tools/build_of_room.py [--out PATH] [--root DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "tools", "web_public", "nq", "of_room.json")
ET = ZoneInfo("America/New_York")
MAX_BYTES = 40_000
NAMES = {"pdh": "prior-day high", "pdl": "prior-day low", "onh": "overnight high", "onl": "overnight low", "orh": "opening-range high",
         "orl": "opening-range low"}


def _rj(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def _hm(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M") if t else None


def from_replay(root: str):
    """(state, day) of the newest pulled real tick day, replayed through the paper bot."""
    import importlib.util
    sp = importlib.util.spec_from_file_location("bor_v", os.path.join(ROOT, "tools", "of_realday_verdict.py"))
    V = importlib.util.module_from_spec(sp); sp.loader.exec_module(V)
    from engine import of_paper as P, ofsum
    dirs = {}
    for base in (os.path.join(root, "data", "pc_days"), os.path.join(root, "logs", "datapipe", "days")):
        if os.path.isdir(base):
            for d in sorted(os.listdir(base)):
                if len(d) == 10 and os.path.exists(os.path.join(base, d, "of", "NQ_meta.json")):
                    dirs.setdefault(d, os.path.join(base, d))
    days = sorted(dirs)
    for k in range(len(days) - 1, -1, -1):
        d = days[k]
        R = ofsum.read(dirs[d])
        if not R or int(R["meta"].get("rows", 0)) < 50_000:
            continue
        prev = days[k - 1] if k else None
        Rp = ofsum.read(dirs[prev]) if prev else None
        if prev and (dt.date.fromisoformat(d) - dt.date.fromisoformat(prev)).days > 4:
            prev, Rp = None, None
        return P.replay_summary(R, d, Rp, prev, lit=V.ledger_lit(dirs[d])), d
    return None, None


def shipped(root: str):
    """(state, day) of the newest PAPER state the PC shipped (data/pc_days/<day>/of/NQ_paper.json.gz, engine/of_paper.export_day)."""
    import gzip
    for base in (os.path.join(root, "data", "pc_days"), os.path.join(root, "logs", "datapipe", "days")):
        if not os.path.isdir(base):
            continue
        for d in sorted(os.listdir(base), reverse=True):
            p = os.path.join(base, d, "of", "NQ_paper.json.gz")
            if len(d) == 10 and os.path.exists(p):
                try:
                    with gzip.open(p, "rt", encoding="utf-8") as fh:
                        S = json.load(fh)
                    if S.get("paper") and S.get("day") == d:
                        return S, d
                except (OSError, ValueError):
                    continue
    return None, None


# ------------------------------------------------------------------------------------------------ day-ofroom2: the control room
OOS_PATHS = (("research", "orderflow", "oos", "result.json"), ("research", "orderflow", "oos_result.json"))
OOS_WHEN = "tonight 10:30 PM ET"


def _num(x):
    try:
        return float(str(x).replace("$", "").replace(",", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def v5_table(root: str = ROOT) -> list:
    """The ranked v5 families from research/orderflow/v5/SUMMARY.md's table (+ each family's oos_results.json when it exists)."""
    try:
        txt = open(os.path.join(root, "research", "orderflow", "v5", "SUMMARY.md"), encoding="utf-8").read()
    except OSError:
        return []
    out = []
    for ln in txt.splitlines():
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) < 10 or not c[0].isdigit():
            continue
        m = re.search(r"\*\*(.+?)\*\*", c[8])
        verdict = (m.group(1) if m else c[8].split(".")[0]).rstrip(".")
        usd = re.match(r"([+\-]?\$[\d,]+)", c[7].replace("−", "-"))
        row = {"rank": int(c[0]), "family": c[1], "variant": c[2].split(":")[0], "what": c[2].split(":", 1)[-1].strip()[:90],
               "per_week": _num(c[3]), "win_pct": _num(c[4]), "mean_R": _num(c[5]), "pf": _num(c[6]),
               "usd_1": _num(usd.group(1)) if usd else None, "verdict": verdict, "watch": int(c[0]) <= 2,
               "must": re.sub(r"\*\*", "", c[9])[:140] if len(c) > 9 else None}
        oo = _rj(os.path.join(root, "research", "orderflow", "v5", c[1], "oos_results.json"))
        if isinstance(oo, dict):
            row["oos"] = {k: oo.get(k) for k in ("days", "verdict", "line", "n", "mean_R") if oo.get(k) is not None} or {"ran": True}
        out.append(row)
    return out


def control(root: str = ROOT) -> dict:
    """Monday's order-flow control room: the ladder, the honest backtest, tonight's full-year slot, the v5 table, the lane."""
    out = {}
    L = _rj(os.path.join(root, "research", "evalplan", "ladder.json"))
    if isinstance(L, dict):
        st = L.get("stats") or {}
        sl = L.get("stats_later") or {}
        out["ladder"] = {"step": L.get("step"), "step_name": L.get("step_name"), "status": L.get("status"), "why": L.get("why"),
                         "n": st.get("n", 0), "need": 30, "won": st.get("won"), "mean_R": st.get("mean_R"), "pf": st.get("pf"),
                         "sum_R": st.get("sum_R"), "usd_1": st.get("usd_1"), "judged_on": L.get("judged_on") or "first trade of each day",
                         "later_n": sl.get("n"), "later_sum_R": sl.get("sum_R"), "cap_one_a_day": L.get("cap_one_a_day"),
                         "gates": [{"k": "mean R", "need": ">= +0.20R", "v": st.get("mean_R")}, {"k": "PF ($)", "need": ">= 1.30", "v": st.get("pf")},
                                   {"k": "both halves", "need": ">= 0R", "v": None}, {"k": "max drawdown", "need": "<= 6R", "v": None}],
                         "stopped": bool(L.get("stopped")), "line": L.get("line")}
    M = _rj(os.path.join(root, "research", "orderflow", "monfix", "results.json"))
    if isinstance(M, dict) and isinstance(M.get("books"), dict):
        b = M["books"].get("after|first|e5") or {}
        lt = M["books"].get("after|onepos_later_only|e5") or {}
        h = b.get("halves") or {}
        out["backtest"] = {"label": "first trade of the day, E5 entry, after the Monday fix", "days": M.get("trading_days"),
                           "weeks": M.get("weeks"), "trades": b.get("trades"), "per_week": b.get("per_week"), "win_pct": b.get("win_pct"),
                           "mean_R": b.get("mean_R"), "pf": b.get("pf"), "usd_1": b.get("usd_1_micro"), "max_dd": b.get("max_dd_usd"),
                           "half_old": (h.get("older") or {}).get("mean_R"), "half_new": (h.get("newer") or {}).get("mean_R"),
                           "later": {"trades": lt.get("trades"), "mean_R": lt.get("mean_R"), "usd_1": lt.get("usd_1_micro")} if lt else None,
                           "source": "research/orderflow/monfix/RESULT.md"}
    oos = None
    for parts in OOS_PATHS:
        oos = _rj(os.path.join(root, *parts))
        if isinstance(oos, dict):
            break
    # the contract (lead 2026-11-27): made, days, first, last, verdict pass|fail|weak, line, laneA {n, tpw, mean_R, pf, win_pct, usd_1,
    # max_dd, halves {h1_2026, h2_2026, dec_2025}}, books {first, one_at_a_time} (same keys), v5 [{family, verdict, n, mean_R, usd_1}]
    out["oos"] = ({"pending": False, **{k: oos.get(k) for k in ("made", "days", "first", "last", "verdict", "line") if oos.get(k) is not None},
                   "laneA": oos.get("laneA") if isinstance(oos.get("laneA"), dict) else None,
                   "books": oos.get("books") if isinstance(oos.get("books"), dict) else None}
                  if isinstance(oos, dict) else {"pending": True, "when": OOS_WHEN})
    out["v5"] = v5_table(root)
    if isinstance(oos, dict) and isinstance(oos.get("v5"), list):      # the full-year v5 results ride each family's row
        by = {str(x.get("family")): x for x in oos["v5"] if isinstance(x, dict)}
        for r in out["v5"]:
            x = by.get(r["family"])
            if x:
                r["oos"] = {k: x.get(k) for k in ("verdict", "n", "mean_R", "usd_1") if x.get(k) is not None}
    out["v5_line"] = "No new order-flow edge: 8 families, none a YES-candidate. Lane A's absorbed level fade is still the only one that works."
    cfg, lst = _rj(os.path.join(root, "data", "of_lane.json")), _rj(os.path.join(root, "data", "of_lane_state.json"))
    if isinstance(cfg, dict) or isinstance(lst, dict):        # only where the lane lives (the PC); the phone reads the live post
        out["lane"] = lane_block(cfg if isinstance(cfg, dict) else {}, lst if isinstance(lst, dict) else {})
    else:                                                     # the cloud: the day file the PC ships nightly (engine/of_lane.public_view)
        sh = shipped_lane(root)
        if sh:
            out["lane"] = sh
    return out


def shipped_lane(root: str):
    """The newest data/pc_days/<day>/of/NQ_lane.json.gz (engine/of_lane.public_view: R only, no $) in the page's lane shape, or None."""
    import gzip
    base = os.path.join(root, "data", "pc_days")
    if not os.path.isdir(base):
        return None
    for d in sorted(os.listdir(base), reverse=True):
        p = os.path.join(base, d, "of", "NQ_lane.json.gz")
        if len(d) != 10 or not os.path.exists(p):
            continue
        try:
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                V = json.load(fh)
        except (OSError, ValueError):
            continue
        tr = [{"t": x.get("t"), "dir": x.get("dir"), "status": x.get("status"), "why": x.get("why"), "R": x.get("R"), "how": x.get("how"),
               "level": x.get("level")} for x in V.get("trades") or [] if isinstance(x, dict)]
        td = V.get("today") or {}
        return {"on": V.get("on") is True, "account": str(V.get("account") or "Sim102")[:12], "cap": 1,
                "used": td.get("filled") if isinstance(td.get("filled"), int) else sum(1 for x in tr if x["status"] in ("open", "closed")),
                "day": V.get("day") or d, "trades": tr[-6:], "line": V.get("line")}
    return None


def lane_block(cfg: dict, S: dict) -> dict:
    """The practice lane in plain fields (engine/of_lane.py files). Sim only; no account id beyond its Sim name."""
    day = S.get("day")
    tr = [t for t in S.get("trades") or [] if t.get("day") == day]
    # engine/of_lane trade keys (day-ofready2): est / limit / fill_px / stop / target / exit_px, qty, d, status, why, pnl, R, how
    rows = [{"t": _hm(t.get("entry_t") or t.get("t")), "dir": "long" if t.get("d") == 1 else "short", "qty": t.get("qty"),
             "status": t.get("status"), "why": str(t.get("why") or "")[:120], "pnl": t.get("pnl"), "R": t.get("R"), "how": t.get("how"),
             "entry": t.get("fill_px") if t.get("fill_px") is not None else (t.get("limit") if t.get("limit") is not None else t.get("est")),
             "stop": t.get("stop"), "target": t.get("target"), "exit": t.get("exit_px")} for t in tr]
    cap = cfg.get("max_per_day", 1)
    used = sum(1 for t in tr if t.get("status") in ("sending", "open", "closed") and t.get("filled", True))
    return {"on": cfg.get("on") is True, "account": str(cfg.get("account") or "Sim102")[:12], "cap": cap if isinstance(cap, int) and cap >= 1 else 1,
            "used": used, "day": day, "trades": rows[-6:]}


def build(root: str = ROOT, now: float | None = None, state: dict | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc).timestamp()
    today = dt.datetime.fromtimestamp(now, ET).strftime("%Y-%m-%d")
    S = state if state is not None else _rj(os.path.join(root, "data", "of_paper.json"))
    source = "live"
    if not S or S.get("day") != today:
        S, sday = shipped(root)
        source = f"PC paper bot ({sday}, shipped)" if S else None
        if S is None:
            S, _ = from_replay(root)
            source = "last recorded day (replay)" if S else "none"
    out = {"v": 1, "made": int(now), "paper": True, "source": source, "day": (S or {}).get("day"),
           "what": "Order Flow pillar (paper): level sweeps read for absorption; Zlarior's entries read the same way. Nothing here trades."}
    if S:
        from engine import of_paper as P
        out["line"] = re.sub(r"(Zlarior[^;]*?\b(?:won|lost))\s*-?\$[\d,.]+", r"\1", S.get("line") or P.line(S) or "")   # no $ of a real trade (public)
        rows = [r for r in S.get("rows") or [] if r.get("lane") == "A" and r.get("day") == S.get("day")]
        lv = []
        for L in S.get("levels") or []:
            hit = next((r for r in rows if r["level"] == L["name"]), None)
            lv.append({"name": L["name"], "label": NAMES.get(L["name"], L["name"]), "px": L["px"], "side": "high" if L["side"] == 1 else "low",
                       "read": ("absorbed" if hit["absorbed"] else "not absorbed") if hit else "untouched",
                       "t": _hm(hit["t_sig"]) if hit else None, "vz": hit.get("vz") if hit else None, "dz": hit.get("dz") if hit else None})
        out["levels"] = lv
        out["rows"] = [{"t": _hm(r["t_sig"]), "level": NAMES.get(r["level"], r["level"]), "dir": "long" if r["d"] == 1 else "short",
                         "absorbed": r["absorbed"], "taken": r["taken"], "why_not": r.get("why_not"), "fill": r.get("fill"), "stop": r.get("stop"),
                         "target": r.get("target"), "exit": r.get("exit"), "why": r.get("why"), "R": r.get("R"), "usd_1": r.get("usd_1"),
                         "state": "open" if r.get("fill") is not None and not r.get("exit_t") else ("waiting for fill" if r.get("fill") is None and not r.get("exit_t") else "done")}
                        for r in rows]
        out["lit"] = [{"t": _hm(r["t"]), "dir": "long" if r["d"] == 1 else "short", "flow_says": r["decision"],
                       "result": r.get("result") if "result" in r else (None if r.get("pnl") is None else ("won" if r["pnl"] > 0 else "lost"))}
                      for r in S.get("lit") or []]
        out["today"] = {k: (S.get("today") or {}).get(k) for k in ("taken", "open", "R", "usd_1", "skipped", "skipped_R")}
    V = _rj(os.path.join(root, "research", "orderflow", "real_verdict.json"))
    if V:
        fw = V.get("forward") or {}
        out["forward"] = {"n": fw.get("taken_resolved", 0), "need": fw.get("need", 20), "sum_R": fw.get("sum_R"),
                          "line": f"forward score {fw.get('taken_resolved', 0)} of {fw.get('need', 20)} paper trades"}
        out["verdict"] = {"made": V.get("made"), "days": V.get("tick_days"), "label": V.get("label"), "line": V.get("verdict_line"),
                          "absorption": (V.get("laneA") or {}).get("verdict"), "of1_lit": V.get("of1_decider"),
                          "first": V.get("first"), "last": V.get("last"), "forward_days": V.get("forward_days"), "sides": V.get("side_note")}
        A = V.get("laneA") or {}
        if A.get("taken") and A.get("skipped"):              # the numbers behind lane A (paper; R and $ at 1 micro, costs in)
            pick = lambda x: {k: x.get(k) for k in ("n", "mean_R", "win%", "usd_1")}
            out["verdict"]["a"] = {"taken": pick(A["taken"]), "skipped": pick(A["skipped"]), "p": A.get("p"), "halves": A.get("halves_diff_R"),
                                   "resolved": A.get("resolved"), "need": A.get("need")}
        B = V.get("laneB_replay") or {}
        out["verdict"]["b"] = {"trades": B.get("trades"), "need": B.get("need"), "verdict": B.get("verdict")}
    else:
        out["forward"] = {"n": 0, "need": 20, "line": "forward score 0 of 20 paper trades (no real day scored yet)"}
    try:
        out["control"] = control(root)                       # day-ofroom2: never breaks the room if a research file is odd
    except Exception as e:  # noqa: BLE001
        out["control"] = {"error": f"{e.__class__.__name__}"}
    return out


# ------------------------------------------------------------------------------------------------ the footprint strip (nq/ofstrip.js)
STRIP_OUT = os.path.join(ROOT, "tools", "web_public", "nq", "of_strip.json")
STRIP_BUCKET_TICKS = 8          # 2 points a cell (8 x 0.25): ~15 cells a 5m bar, the whole RTH day < 40 KB
ZONE_TICKS, ABS_SHARE = 8, 0.20  # OF1 (research/orderflow/PREREG_ticks.md): zone at the bar extreme, absorbed share


def strip_from_summary(R: dict, day: str) -> dict:
    """One day's order-flow summary (engine.ofsum: bars5m + fp5m) -> the strip's data: RTH 5m bars, each with o/h/l/c, volume, delta,
    big prints (signed >= 20 lots), price cells [low price of the 2-pt cell, buy lots, sell lots] and the OF1 absorption read at
    both extremes ({side, who, px, vz, dz}). Market data only."""
    import pandas as pd
    b, fp = R["bars"].copy(), R["fp"]
    tick = float((R.get("meta") or {}).get("tick") or 0.25)
    et = pd.to_datetime(b.t, unit="s", utc=True).dt.tz_convert(ET)
    b["mod"] = et.dt.hour * 60 + et.dt.minute
    b["hm"] = et.dt.strftime("%H:%M")
    b["i"] = range(len(b))
    rth = b[(b["mod"] >= 570) & (b["mod"] < 960)]
    byb = {int(k): g for k, g in fp.groupby("bar")}
    bars = []
    for _, r in rth.iterrows():
        g = byb.get(int(r["i"]))
        lo, hi = float(r["l"]), float(r["h"])
        cells, absd = {}, []
        if g is not None:
            kmax = int(round((hi - lo) / tick))
            for k, a, bb in zip(g.k.to_numpy(), g.a.to_numpy(), g.b.to_numpy()):
                px = lo + int(k) * tick
                c = round((px // (STRIP_BUCKET_TICKS * tick)) * STRIP_BUCKET_TICKS * tick, 2)
                x = cells.setdefault(c, [c, 0, 0])
                x[1] += int(a); x[2] += int(bb)
            if int(r.get("n") or 0) >= 20:
                for side, z, d in (("low", g[g.k <= ZONE_TICKS], 1), ("high", g[g.k >= kmax - ZONE_TICKS], -1)):
                    vz = float((z.a + z.b + z.u).sum()); dz = float((z.a - z.b).sum())
                    if vz > 0 and dz * d < 0 and abs(dz) >= ABS_SHARE * vz:
                        absd.append({"side": side, "who": "buyers" if side == "low" else "sellers", "px": lo if side == "low" else hi,
                                     "vz": int(vz), "dz": int(dz)})
        big = r.get("b20")
        bars.append({"t": r["hm"], "o": float(r["o"]), "h": hi, "l": lo, "c": float(r["c"]), "v": int(r["vol"]),
                     "d": int(r["buy"] - r["sell"]), "big": int(big) if big not in ("", None) and pd.notna(big) else 0,
                     "cells": sorted(cells.values()), "abs": absd})
    return {"v": 1, "day": day, "tick": tick, "bucket": STRIP_BUCKET_TICKS * tick, "bars": bars, "paper": True,
            "what": "NQ footprint by 5-minute bar: aggressive buying vs selling at each 2-point cell, absorption at the bar's extremes, big prints"}


def strip_for(root: str, day: str | None):
    """The strip of `day` (or the newest pulled real tick day) from data/pc_days / logs/datapipe/days, or None."""
    from engine import ofsum
    dirs = {}
    for base in (os.path.join(root, "data", "pc_days"), os.path.join(root, "logs", "datapipe", "days")):
        if os.path.isdir(base):
            for d in sorted(os.listdir(base)):
                if len(d) == 10 and os.path.exists(os.path.join(base, d, "of", "NQ_meta.json")):
                    dirs.setdefault(d, os.path.join(base, d))
    for d in ([day] if day in dirs else []) + sorted(dirs, reverse=True):
        R = ofsum.read(dirs[d])
        if R and int(R["meta"].get("rows", 0)) >= 50_000:
            s_ = strip_from_summary(R, d)
            if s_["bars"]:
                return s_
    return None


def write(obj, path=OUT):
    raw = json.dumps(obj, separators=(",", ":"), default=float)
    if len(raw) > MAX_BYTES:                      # keep the page light: the newest paper rows only
        obj["rows"] = (obj.get("rows") or [])[-20:]
        raw = json.dumps(obj, separators=(",", ":"), default=float)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        fh.write(raw)
    os.replace(path + ".tmp", path)
    return len(raw)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT); ap.add_argument("--root", default=ROOT)
    a = ap.parse_args()
    o = build(a.root)
    n = write(o, a.out)
    try:                                                     # the footprint strip of the room's day (nq/ofstrip.js reads it)
        st = strip_for(a.root, o.get("day"))
        if st:
            sp = os.path.join(os.path.dirname(a.out), "of_strip.json")
            with open(sp + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(st, fh, separators=(",", ":"))
            os.replace(sp + ".tmp", sp)
            print(f"of_strip.json: {st['day']}, {len(st['bars'])} bars")
    except Exception as e:  # noqa: BLE001
        print(f"of_strip.json: skipped ({e.__class__.__name__})")
    print(f"of_room.json: {o['source']}, day {o.get('day')}, {len(o.get('rows') or [])} paper rows, {n} bytes | {o.get('line')}")
