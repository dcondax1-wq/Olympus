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


def build(root: str = ROOT, now: float | None = None, state: dict | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc).timestamp()
    today = dt.datetime.fromtimestamp(now, ET).strftime("%Y-%m-%d")
    S = state if state is not None else _rj(os.path.join(root, "data", "of_paper.json"))
    source = "live"
    if not S or S.get("day") != today:
        S, _ = from_replay(root)
        source = "last recorded day (replay)" if S else "none"
    out = {"v": 1, "made": int(now), "paper": True, "source": source, "day": (S or {}).get("day"),
           "what": "Order Flow pillar (paper): level sweeps read for absorption; Zlarior's entries read the same way. Nothing here trades."}
    if S:
        from engine import of_paper as P
        out["line"] = S.get("line") or P.line(S)
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
                       "result": None if r.get("pnl") is None else ("won" if r["pnl"] > 0 else "lost")} for r in S.get("lit") or []]
        out["today"] = {k: (S.get("today") or {}).get(k) for k in ("taken", "open", "R", "usd_1", "skipped", "skipped_R")}
    V = _rj(os.path.join(root, "research", "orderflow", "real_verdict.json"))
    if V:
        fw = V.get("forward") or {}
        out["forward"] = {"n": fw.get("taken_resolved", 0), "need": fw.get("need", 20), "sum_R": fw.get("sum_R"),
                          "line": f"forward score {fw.get('taken_resolved', 0)} of {fw.get('need', 20)} paper trades"}
        out["verdict"] = {"made": V.get("made"), "days": V.get("tick_days"), "label": V.get("label"), "line": V.get("verdict_line"),
                          "absorption": (V.get("laneA") or {}).get("verdict"), "of1_lit": V.get("of1_decider")}
    else:
        out["forward"] = {"n": 0, "need": 20, "line": "forward score 0 of 20 paper trades (no real day scored yet)"}
    return out


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
    print(f"of_room.json: {o['source']}, day {o.get('day')}, {len(o.get('rows') or [])} paper rows, {n} bytes | {o.get('line')}")
