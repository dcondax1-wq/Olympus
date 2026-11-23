"""Multi-strategy books (2026-11-23), step 1: every strategy lane we have a trade list for -> ONE trade file in the format of
tools/money/combo_account.py (cols s, day, et, xt, d, risk, tgt, pts, w1, tf, src, lb, sm, x, n). PAPER ONLY: reads stored /
regenerated trades, writes research/books/*.json, changes nothing live.

Lanes (letter = the bot id in the account simulator):
  fixed rules (no choice made here)
    Z  LIT / Zlarior (live model)          combo_account_trades.json (account4_sim: 2026 1m live loop, 2021-25 5m)
    A  ATLAS as it trades (EMA+MACD+S/R, one position, max 2 a day)   combo_account_trades.json
    E / M / S  ATLAS members alone (EMA / MACD / S-R)                  tools/second_mix.units()
    B  BLITZ v2                                                        combo_account_trades.json
    P  post-close follow (third-strategy paper lead)                   combo_account_trades.json
    H  stop hunt: Asia resweep (tools/stophunt.FINAL, frozen 2026-10-23; = half of ATLAS v2 hunts)
    T  stop hunt: trend inducement 5m (tools/stophunt.FINAL; the other half of ATLAS v2 hunts)
    O  edge-a best cell, ORB-30 (branch edge-a-session daily.csv; entry time not stored -> 10:05 ET, held to 15:55)
    W  edge-c closest cell, Monday long 09:30-15:55 (branch edge-c-calendar daily.csv)
  grid families (one cell each, chosen HERE on 2026 Jan-Jun ONLY by net $ at $500 a trade after real fills; every cell
  tried is counted in the multiple-testing correction): new-strategy-hunt lsq / fav / d80 / lxf, E2 orb2 / pdx / rs / gapf /
  vwr / eod / news, diversifier NA / IB, ATLAS-plus vwp / odc / pva / ksq / poc, third-strategy cam / tds.
  (research/retest/cells_*.json from tools/retest/regen.py = each tool's own signal + execution code.)
Real fills (main): the live reconciliation (research/writeups/live-vs-model-2026-11-21.md, day-atlasedge): Zlarior entries
3 ticks late, ATLAS 9-15 (median 11). Stored trades already carry 1 tick a fill, so Z gets 2 MORE ticks on the entry and
every other lane (all enter at market on a bar close like ATLAS) 10 more. --fills model = the stored fills only.
    python -X utf8 tools/books/lanes.py [--fills real|model]
"""
import collections, csv, datetime as dt, io, json, os, subprocess, sys
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")]
import combo_account as CA
OUT = os.path.join(ROOT, "research", "books")
TICK, PV, COMM = 0.25, 2.0, 1.90
ET = ZoneInfo("America/New_York")
H1 = ("2026-01-01", "2026-06-30")
GRID = {"hunt": ("lsq", "fav", "d80", "lxf"), "e2": ("orb2", "pdx", "rs", "gapf", "vwr", "eod", "news"), "div": ("NA", "IB"),
        "plus": ("vwp", "odc", "pva", "ksq", "poc"), "third": ("cam", "tds")}
NAME = {"Z": "LIT (Zlarior)", "A": "ATLAS (as live)", "E": "ATLAS EMA", "M": "ATLAS MACD", "S": "ATLAS S/R", "B": "BLITZ",
        "P": "post-close follow", "H": "stop hunt Asia resweep", "T": "stop hunt trend idm5", "O": "edge-a ORB-30",
        "W": "edge-c Monday long"}
COLS = ["s", "day", "et", "xt", "d", "risk", "tgt", "pts", "w1", "tf", "src", "lb", "sm", "x", "n"]


def extra_ticks(s, fills):
    if fills == "model":
        return 0.0
    return 2.0 if s == "Z" else 10.0


def row(s, day, et, xt, d, risk, pts, w1, tgt=None, tf=5, src="", lb=1.0, sm=1.0, x=""):
    return {"s": s, "day": day, "et": int(et), "xt": int(xt), "d": int(d), "risk": round(float(risk), 4),
            "tgt": None if tgt is None else round(float(tgt), 4), "pts": round(float(pts), 4),
            "w1": round(float(min(0.0, w1, pts)), 4), "tf": tf, "src": src, "lb": lb, "sm": sm, "x": x, "n": None}


def et_epoch(day, hh, mm):
    y, m, d = map(int, day.split("-"))
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def combo_lanes():
    d = json.load(open(os.path.join(ROOT, "research", "lab", "combo_account_trades.json"), encoding="utf-8"))
    out = []
    for r in d["rows"]:
        r = dict(zip(d["cols"], r))
        if r["s"] in ("Z", "A", "B", "P"):
            r["n"] = None
            out.append(r)
    return out


def member_lanes():
    from tools import second_mix as M
    U = M.units()
    out = []
    for nm, s in (("EMA", "E"), ("MD", "M"), ("SR", "S")):
        for t in U[nm]:
            out.append(row(s, t["day"], t["entry_t"], t["exit_t"], t["dir"], t["risk"], t["pts"], t["w1"], tgt=t["tgt"],
                           src=nm, x=t["exit"]))
    return out


def stophunt_lanes():
    import stophunt as SH
    g = SH.base()
    out = []
    for nm, s in (("sh_asia_resweep", "H"), ("sh_trend_idm5", "T")):
        _, rows = SH.one(g, SH.FINAL[nm])
        for t in rows:
            q = t["qty"]
            pts = (t["pnl_usd"] / q + COMM) / PV
            out.append(row(s, t["day"], t["entry_t"], t["exit_t"], t["dir"], t["risk_pts"], pts, t["mae_r"] * t["risk_pts"],
                           tgt=abs(t["target"] - t["entry"]), src=nm, x=t["exit_kind"]))
    return out


def _git_csv(branch, path):
    txt = subprocess.run(["git", "show", f"origin/{branch}:{path}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return list(csv.DictReader(io.StringIO(txt)))


def edge_lanes():
    out = []
    for r in _git_csv("edge-a-session", "research/edge_hunt/a/daily.csv"):
        q = int(r["qty"])
        risk = (float(r["risk_usd"]) / q - COMM) / PV - TICK
        pts = (float(r["pnl_usd_per_1_micro"]) + COMM) / PV
        w1 = -(risk + TICK)                                    # worst open not stored: a full stop (harsher)
        out.append(row("O", r["date"], et_epoch(r["date"], 10, 5), et_epoch(r["date"], 15, 55), r["dir"], risk, pts, w1,
                       src="A30_orb30", x=r["exit"]))
    for r in _git_csv("edge-c-calendar", "research/edge_hunt/c/daily.csv"):
        m = int(r["micros"])
        if m < 1:
            continue
        dist = 400.0 / m if m >= 20 else (8000.0 / m) ** 0.5     # edge_c: $800 risk to a 20-pt stop, then 16,000 / stop
        pts = (float(r["pnl_usd_per_1_micro"]) + COMM) / PV
        out.append(row("W", r["date"], et_epoch(r["date"], 9, 30), et_epoch(r["date"], 15, 55), 1, dist, pts, -(dist + TICK),
                       src=r["cell"], x=""))
    return out


def grid_lanes(fills):
    """per grid family: the cell with the most net $ in 2026 Jan-Jun at $500 a trade after real fills (H1 ONLY)."""
    picks, tried, out = {}, {}, []
    adj = extra_ticks("x", "real") * TICK                       # cells are always picked at REAL fills (same cells in both files)
    for src, fams in GRID.items():
        cells = json.load(open(os.path.join(ROOT, "research", "retest", f"cells_{src}.json")))
        for fam in fams:
            best, scores = None, {}
            for k, rows in cells.items():
                if k.rsplit(":", 1)[0] != f"{src}:{fam}":
                    continue
                net, n = 0.0, 0
                for day, et, xt, d, risk, pts, w1, _ in rows:
                    if H1[0] <= day <= H1[1] and risk and risk > 0:
                        q = min(40, int(500.0 // ((risk + TICK) * PV + COMM)))
                        if q >= 1:
                            net += q * ((pts - adj) * PV - COMM)
                            n += 1
                scores[k] = (round(net), n)
                if n >= 5 and (best is None or net > scores[best][0]):
                    best = k
            lane = f"{fam}"
            tried[lane] = len(scores)
            if best is None:
                continue
            picks[lane] = {"cell": best, "h1_net_500": scores[best][0], "h1_trades": scores[best][1], "cells": len(scores)}
            for day, et, xt, d, risk, pts, w1, _ in cells[best]:
                if risk and risk > 0:
                    out.append(row(lane, day, et, xt, d, risk, pts, w1, src=best))
    return out, picks, tried


def main(fills="real"):
    rows = combo_lanes() + member_lanes() + stophunt_lanes() + edge_lanes()
    g, picks, tried = grid_lanes(fills)
    rows += g
    for r in rows:                                            # real fills: extra entry ticks on top of the stored fills
        k = extra_ticks(r["s"], fills) * TICK
        if k:
            r["pts"] = round(r["pts"] - k, 4)
            r["w1"] = round(min(r["w1"] - k, r["pts"]), 4)
        r["n"] = None
    rows = [r for r in rows if CA.SPAN["REF"][0] <= r["day"] <= CA.SPAN["H2"][1]]
    rows = CA._news(rows)                                     # Rapid funded Tier-1 news rule, per lane-day
    lanes = sorted({r["s"] for r in rows}, key=lambda s: (list(NAME).index(s) if s in NAME else 99, s))
    prio = {s: i for i, s in enumerate(lanes)}
    rows.sort(key=lambda r: (r["day"], r["et"], prio[r["s"]]))
    os.makedirs(OUT, exist_ok=True)
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "fills": fills, "cols": COLS, "lanes": lanes,
           "names": {s: NAME.get(s, f"grid {s} ({picks[s]['cell']})" if s in picks else s) for s in lanes},
           "grid_picks": picks, "grid_cells_tried": tried, "count": dict(collections.Counter(r["s"] for r in rows)),
           "rows": [[r.get(c) for c in COLS] for r in rows]}
    p = os.path.join(OUT, f"lanes_{fills}.json")
    json.dump(out, open(p, "w", encoding="utf-8"), separators=(",", ":"))
    print(p, out["count"], sum(tried.values()), "grid cells tried")
    for k, v in picks.items():
        print(" ", k, v)


if __name__ == "__main__":
    f = sys.argv[sys.argv.index("--fills") + 1] if "--fills" in sys.argv else "real"
    main(f)
