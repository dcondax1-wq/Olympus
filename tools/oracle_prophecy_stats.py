#!/usr/bin/env python3
"""ORACLE prophecy stats: how often each LIT level family started a trade, and how those trades ended (read-only).

Reads research/lab/backtest_live.json (the live-settings replay, costs in; tools/export_backtest.py) and writes
tools/web_public/oracle/prophecy.json, the file the Oracle's Prophecy panel reads. No network, no secrets, nothing traded.

    python tools/oracle_prophecy_stats.py            # rewrite prophecy.json
    python tools/oracle_prophecy_stats.py --check    # exit 1 when prophecy.json is not what the replay gives

Level families (the same ids oracle/prophecy.js maps a level's label to): asia_h, asia_l, frank_h, frank_l (Frankfurt 02-03),
lon34_h, lon34_l, lon25_h, lon25_l, ny830_h/_l, ny89_h/_l, ny930_h/_l, ny930b_h/_l (09:30-10:30), pre_h/_l, pd_h/_l (prior day),
pw_h/_l, pm_h/_l, bu_h/_l (equal highs / lows), nwog, ndog. A trade counts once for every family it swept.
Per family: n (trades), share (of all trades), win_pct (made money after costs, the replay's own rule), avg_r, plus the same for 2026 only
(n26, win26, avg_r26). Fewer than 30 trades = low_n (the page greys it).
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "research", "lab", "backtest_live.json")
OUT = os.path.join(ROOT, "tools", "web_public", "oracle", "prophecy.json")

KEY = [(r"^asia\d+_([hl])$", "asia_{0}"), (r"^lon23_([hl])$", "frank_{0}"), (r"^lon34_([hl])$", "lon34_{0}"), (r"^lon25_([hl])$", "lon25_{0}"),
       (r"^ny830_([hl])$", "ny830_{0}"), (r"^ny89_([hl])$", "ny89_{0}"), (r"^ny9301030_([hl])$", "ny930b_{0}"), (r"^ny930_([hl])$", "ny930_{0}"),
       (r"^pre_([hl])$", "pre_{0}"), (r"^pd([hl])$", "pd_{0}"), (r"^pw([hl])$", "pw_{0}"), (r"^pm([hl])$", "pm_{0}"), (r"^bu_([hl])$", "bu_{0}"),
       (r"^(nwog)$", "nwog"), (r"^(ndog)$", "ndog")]


def family(key: str):
    for pat, out in KEY:
        m = re.match(pat, key)
        if m:
            return out.format(*m.groups())
    return None


def is_win(t) -> bool:
    """the replay's own rule (export_backtest's win_pct): the trade made money after costs"""
    return (t.get("pnl") or 0) > 0


def build(src=SRC) -> dict:
    d = json.load(open(src, encoding="utf-8"))
    trades = [t for t in d["trades"] if t.get("swept")]
    allt = [t for t in d["trades"] if t.get("r") is not None]
    fam: dict[str, list] = {}
    for t in trades:
        for f in {family(k) for k in t["swept"]} - {None}:
            fam.setdefault(f, []).append(t)

    def stat(ts):
        n = len(ts)
        return n, (round(100 * sum(is_win(t) for t in ts) / n, 1) if n else None), (round(sum(t["r"] for t in ts) / n, 2) if n else None)

    out_f = {}
    for f, ts in sorted(fam.items(), key=lambda kv: -len(kv[1])):
        n, win, avg = stat(ts)
        t26 = [t for t in ts if t["day"] >= "2026"]
        n26, win26, avg26 = stat(t26)
        out_f[f] = {"n": n, "share": round(n / max(1, len(allt)), 4), "win_pct": win, "avg_r": avg, "n26": n26, "win26": win26, "avg_r26": avg26, "low_n": n < 30}
    n, win, avg = stat(allt)
    t26 = [t for t in allt if t["day"] >= "2026"]
    n26, win26, avg26 = stat(t26)
    hours = {}
    for t in allt:
        h = int(__import__("datetime").datetime.fromtimestamp(t["entry_t"], __import__("datetime").timezone.utc).strftime("%H"))
        hours.setdefault(h, []).append(t)
    return {"v": 1, "kind": "oracle-prophecy", "source": "research/lab/backtest_live.json (LIT, live settings, costs in)",
            "built_from": d.get("meta", {}).get("built"), "days": [allt[0]["day"], allt[-1]["day"]] if allt else [],
            "all": {"n": n, "win_pct": win, "avg_r": avg, "n26": n26, "win26": win26, "avg_r26": avg26},
            "families": out_f,
            "note": "A family's share = trades that swept it / all trades. One trade can sweep two families. Odds, not a forecast."}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    j = build()
    text = json.dumps(j, indent=1, ensure_ascii=False) + "\n"
    if "--check" in argv:
        return 0 if os.path.exists(OUT) and open(OUT, encoding="utf-8").read() == text else 1
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote", OUT, len(j["families"]), "families,", j["all"]["n"], "trades")
    return 0


if __name__ == "__main__":
    sys.exit(main())
