"""STRATEGY ROOMS data (day-strats 2026-11-27, owner: "complete charts of each strategy: Zlarior, ATLAS, BLITZ and order flow; I want to
see everything"). Builds tools/web_public/nq/strats/<s>.json (s = lit | atlas | blitz | poseidon) for nq/strat.html from files that
already exist (research/ is not on the site; this copies the parts the rooms show). Deterministic: the same inputs give the same bytes.
Run it in the site build (the lead wires it next to tools/trading_export.py); --check exits 1 when a file is stale.

Per strategy:  {v, s, name, alias, paper, color, what, status, data_to, sources[], cols[], trades[[...]], spans[], equity{}, research[]}
  trades   one row per trade, cols = src, day, t, xt, side, e, sl, tg, x, k, usd, r, q, acct, tag, why
           src: live (a REAL account), paper (the cloud / PC paper twin), backtest (the research replay, not money made)
           e / sl / tg / x = entry / stop / target / exit price (null when the source has none: BLITZ, POSEIDON targets)
  spans    computed here from the trade rows, the same way for every strategy: 2026 H1 (Jan-Jun), 2026 Jul-<data end>, 2021-25, and
           Live (real accounts): n, per week, win %, PF, avg R, $ / month, max drawdown, best / worst trade ($)
  equity   cumulative $ by exit day: backtest (2021 ->), each live account, paper
  research the research file's own period numbers (pillars-data.json spans), shown beside ours as the reference

Sources: LIT = research/lab/backtest_live.json (631 trades, prices + the written why) + tools/web_public/trading/trades.json (live,
paper); ATLAS = research/anatomy/trades_atlas.json (the combined book, 1,288 trades) + prices joined from research/second/{ema,md,sr}_best.json
+ trades.json live; BLITZ (PAPER, hidden on the dashboards) = research/runs/blitz_2026_backtest.json (no prices: risk points only) +
research/batch5/blitz_paper.json (a summary: the PC's paper ledger is not in the cloud); POSEIDON (the order-flow lane, PAPER) =
research/orderflow/real_verdict.json (93 real-tick signals, taken or skipped with why) + exec_results.json (fill / stop / level).

    python -X utf8 tools/build_strats.py [--check] [--out DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "nq", "strats")
ET = ZoneInfo("America/New_York")
COLS = ["src", "day", "t", "xt", "side", "e", "sl", "tg", "x", "k", "usd", "r", "q", "acct", "tag", "why"]
V = 1
ROOMS = {
    "lit": {"name": "Zlarior", "alias": "LIT", "paper": False, "color": "#f1c14b",
            "what": "Sweep, inducement, CISD: a stop 1 tick beyond the sweep, one VIX-band target. Live on the Zlarior evals."},
    "atlas": {"name": "ATLAS", "alias": "ATLAS", "paper": False, "color": "#b48cf2",
              "what": "Three members (London EMA pullback, MACD divergence at a sweep, NY sweep-and-reclaim of S/R). Live on the ATLAS funded 25K."},
    "blitz": {"name": "BLITZ", "alias": "BLITZ", "paper": True, "color": "#f472b6",
              "what": "The 1-minute noise-band scalp: a close outside the 14-day noise band, 11:00-15:30 ET, stop 1.5 ATR, trail after +1R. PAPER only."},
    "poseidon": {"name": "POSEIDON", "alias": "Order flow", "paper": True, "color": "#77db89",
                 "what": "The order-flow lane: fade a swept key level only when the footprint shows the push was absorbed. PAPER only."},
}


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def r2(v):
    return None if v is None else round(float(v), 2)


def short(s, n=170):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def side_of(v):
    s = str(v).lower()
    return "LONG" if s in ("1", "long", "buy") else "SHORT" if s in ("-1", "short", "sell") else s.upper()


def row(src, day, t, xt, side, e, sl, tg, x, k, usd, r, q, acct, tag, why):
    return [src, day, t, xt, side, r2(e), r2(sl), r2(tg), r2(x), k, r2(usd), None if r is None else round(float(r), 3),
            q, acct, tag, short(why) if why else ""]


# ------------------------------------------------------------------------------------------------ live / paper rows (trading/trades.json)
def site_rows(bot):
    T = load("tools/web_public/trading/trades.json")
    out = []
    for x in T["trades"]:
        if x.get("bot") != bot or x.get("src") not in ("live", "paper"):
            continue
        out.append(row(x["src"], x["day"], x.get("t"), x.get("xt"), x.get("side"), x.get("e"), x.get("s"), x.get("tg"), x.get("x"),
                       x.get("k"), x.get("usd"), x.get("r"), x.get("q"), x.get("an") or ("Paper twin" if x["src"] == "paper" else ""),
                       x.get("m") or "", ""))
    return out, T.get("upto") or {}


# ------------------------------------------------------------------------------------------------ the fresh replay (tools/refresh_backtests.py)
FRESH_WHY = "Fresh replay on the newest bars (tools/refresh_backtests.py, parity with the stored research checked). "


def fresh(s):
    """research/strats_refresh/<s>.json when its parity held, else None (the stored research alone)"""
    try:
        f = load(f"research/strats_refresh/{s}.json")
    except (OSError, ValueError):
        return None
    return f if f.get("ok") and f.get("trades") is not None else None


# ------------------------------------------------------------------------------------------------ the four rooms
def lit():
    bt = load("research/lab/backtest_live.json")
    F = fresh("lit")
    rows = []
    for x in bt["trades"] + (F["trades"] if F else []):
        rep = x.get("report") or {}
        why = ("" if x["day"] <= bt["trades"][-1]["day"] else FRESH_WHY) + "; ".join(rep.get("why") or [])
        rows.append(row("backtest", x["day"], x.get("entry_t"), x.get("exit_t"), x.get("side"), x.get("entry"), x.get("stop"), x.get("target"),
                        x.get("exit_price"), x.get("exit"), x.get("pnl"), x.get("r"), x.get("qty"), "", x.get("entry_kind") or "", why))
    live, upto = site_rows("LIT")
    to = {"backtest": F["data_to"] if F else bt["trades"][-1]["day"], "live": upto.get("live_lit"), "paper": upto.get("paper_lit")}
    if F:
        to["fresh"] = {"after": F["stored_end"], "to": F["data_to"], "n": F["n_new"]}
    return rows + live, to, ["research/lab/backtest_live.json (the live-settings replay, costs in)"] + \
        (["research/strats_refresh/lit.json (the same replay on the newest bars)"] if F else []) + ["tools/web_public/trading/trades.json (live + the paper twin)"]


def atlas():
    A = load("research/anatomy/trades_atlas.json")
    c = {k: i for i, k in enumerate(A["cols"])}
    px = {}
    for f, mem in (("ema_best", "EMA"), ("md_best", "MD"), ("sr_best", "SR")):
        for x in load(f"research/second/{f}.json")["trades"]:
            px[(mem, int(x["entry_t"]), int(x["dir"]))] = x
    rows, joined = [], 0
    for x in A["rows"]:
        g = lambda k: x[c[k]]  # noqa: E731
        p = px.get((g("src"), int(g("entry_t")), int(g("dir"))))
        joined += p is not None
        rows.append(row("backtest", g("day"), g("entry_t"), g("exit_t"), g("dir"), p and p.get("entry"), p and p.get("stop"), p and p.get("target"),
                        p and p.get("exit"), g("exit"), g("usd"), g("r"), p and p.get("qty"), "", g("member"),
                        (p or {}).get("setup") or g("s_setup") or ""))
    n_st = len(rows)
    F = fresh("atlas")
    for x in (F["trades"] if F else []):
        rows.append(row("backtest", x["day"], x["entry_t"], x["exit_t"], x["dir"], x.get("entry"), x.get("stop"), x.get("target"), x.get("exit"),
                        x.get("exit_kind"), x.get("usd"), x.get("r"), None, "", x.get("member") or "", FRESH_WHY + (x.get("setup") or "")))
    live, upto = site_rows("ATLAS")
    to = {"backtest": F["data_to"] if F else A["rows"][-1][c["day"]], "live": upto.get("live_atlas"), "prices_joined": f"{joined} of {n_st}"}
    if F:
        to["fresh"] = {"after": F["stored_end"], "to": F["data_to"], "n": F["n_new"], "note": F.get("armed_block")}
    return rows + live, to, \
        ["research/anatomy/trades_atlas.json (the combined ATLAS book, costs in)", "research/second/{ema,md,sr}_best.json (the members' prices)",
         "tools/web_public/trading/trades.json (live)"]


def blitz():
    B = load("research/runs/blitz_2026_backtest.json")
    c = {k: i for i, k in enumerate(B["trade_cols"])}
    rows = []
    for x in B["trades"]:
        g = lambda k: x[c[k]]  # noqa: E731
        why = f"stop {g('risk_pts'):.1f} pts" if g("risk_pts") is not None else ""
        rows.append(row("backtest", g("day"), g("entry_t"), g("exit_t"), g("dir"), None, None, None, None, str(g("exit") or "").upper(),
                        g("pnl"), g("r"), g("qty"), "", "", why))
    F = fresh("blitz")
    for x in (F["trades"] if F else []):
        g = lambda k: x[F["cols"].index(k)]  # noqa: E731
        rows.append(row("backtest", g("day"), g("entry_t"), g("exit_t"), g("dir"), None, None, None, None, str(g("exit") or "").upper(),
                        g("pnl"), g("r"), g("qty"), "", "", FRESH_WHY + (f"stop {g('risk_pts'):.1f} pts" if g("risk_pts") is not None else "")))
    P = load("research/batch5/blitz_paper.json")
    return rows, {"backtest": F["data_to"] if F else B["trades"][-1][c["day"]], **({"fresh": {"after": F["stored_end"], "to": F["data_to"], "n": F["n_new"]}} if F else {}), "paper": P.get("last_day"), "paper_summary": P.get("paper"),
                  "paper_note": "The PC's own BLITZ paper ledger is not in the cloud: only this summary (" + str(P.get("source", ""))[:120] + ")"}, \
        ["research/runs/blitz_2026_backtest.json (no entry / stop prices: risk points only)", "research/batch5/blitz_paper.json (paper summary)"]


def poseidon():
    V_ = load("research/orderflow/real_verdict.json")
    X = {x["id"]: x for x in load("research/orderflow/exec_results.json")["rows"]}
    rows = []
    for x in V_["rows"]:
        e = X.get(x["id"]) or {}
        f = e.get("E0+X0") or {}
        why = (x.get("why") or "") if x.get("taken") else "skipped: " + str(x.get("why_not") or "")
        lvl = {"onl": "overnight low", "onh": "overnight high", "pdl": "prior-day low", "pdh": "prior-day high", "orl": "opening-range low",
               "orh": "opening-range high", "asl": "Asia low", "ash": "Asia high", "lnl": "London low", "lnh": "London high"}.get(x.get("level"), x.get("level"))
        rows.append(row("paper" if x.get("taken") else "skip", x["day"], None, None, x.get("d"), f.get("fill") or e.get("c"), e.get("stop"), None,
                        None, str(x.get("why") or "").upper(), x.get("usd_1"), x.get("R"), 1, "", lvl,
                        f"{lvl} swept, {'absorbed' if x.get('absorbed') else 'not absorbed'}; {why}"))
    return rows, {"paper": V_.get("last"), "first": V_.get("first"), "verdict": short(V_.get("verdict_line"), 220)}, \
        ["research/orderflow/real_verdict.json (real NQ ticks, every signal taken or skipped)", "research/orderflow/exec_results.json (fill, stop)"]


# ------------------------------------------------------------------------------------------------ periods + equity (the same math for all)
def stats(rs, d0, d1):
    rs = [x for x in rs if d0 <= x[1] <= d1 and x[10] is not None]
    if not rs:
        return None
    usd = [x[10] for x in rs]
    rr = [x[11] for x in rs if x[11] is not None]
    win = sum(1 for v in usd if v > 0)
    gw, gl = sum(v for v in usd if v > 0), -sum(v for v in usd if v < 0)
    days = (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days + 1
    eq = peak = dd = 0.0
    for v in usd:
        eq += v; peak = max(peak, eq); dd = min(dd, eq - peak)
    return {"n": len(rs), "tpw": round(len(rs) / (days / 7), 2), "win": round(100 * win / len(rs), 1), "pf": round(gw / gl, 2) if gl else None,
            "avg_r": round(sum(rr) / len(rr), 3) if rr else None, "usd_mo": round(sum(usd) / (days / 30.4375)), "max_dd": round(dd),
            "net": round(sum(usd)), "best": round(max(usd)), "worst": round(min(usd))}


def spans(rows, data_to):
    src = "backtest" if any(x[0] == "backtest" for x in rows) else "paper"      # POSEIDON has no backtest: its real-tick paper signals
    bt = sorted([x for x in rows if x[0] == src], key=lambda x: (x[1], x[2] or 0))
    out = []
    if bt:
        first, last = bt[0][1], bt[-1][1]
        dto = (data_to or {}).get("backtest") if src == "backtest" else (data_to or {}).get("paper")
        if isinstance(dto, str) and len(dto) == 10 and dto > last:
            last = dto                          # quiet days count: the period runs to the data's end, not the last trade
        j0 = max(first, "2026-07-01")
        fmt = lambda d: dt.date.fromisoformat(d).strftime("%b %-d")  # noqa: E731
        jk = ("2026 Jul-" if j0 == "2026-07-01" else f"2026 {fmt(j0)}-") + fmt(max(last, j0))
        for k, a, b in (("2026 H1", max(first, "2026-01-01"), "2026-06-30"), (jk, j0, last), ("2021-25", max(first, "2021-01-01"), "2025-12-31")):
            if a <= b:
                s = stats(bt, a, b)
                if s:
                    out.append({"k": k, "src": src, "from": a, "to": b, **s})
    lv = sorted([x for x in rows if x[0] == "live"], key=lambda x: (x[1], x[2] or 0))
    if lv:
        s = stats(lv, lv[0][1], lv[-1][1])
        out.append({"k": "Live (real)", "from": lv[0][1], "to": lv[-1][1], **s})
    return out


def curve(rs):
    eq, out, byd = 0.0, [], {}
    for x in sorted(rs, key=lambda x: (x[1], x[3] or x[2] or 0)):
        if x[10] is None:
            continue
        eq += x[10]; byd[x[1]] = round(eq, 2)
    for d in sorted(byd):
        out.append([d, byd[d]])
    return out


def equity(rows):
    e = {"backtest": curve([x for x in rows if x[0] == "backtest"]), "paper": curve([x for x in rows if x[0] == "paper"]), "live": {}}
    for a in sorted({x[13] for x in rows if x[0] == "live"}):
        e["live"][a or "Live"] = curve([x for x in rows if x[0] == "live" and x[13] == a])
    return e


def research_spans(s):
    try:
        P = load("tools/web_public/pillars/pillars-data.json")
    except OSError:
        return []
    want = {"lit": "lit", "atlas": "atlas", "blitz": "blitz", "poseidon": "of"}[s]
    for p in P.get("pillars", []):
        if p.get("id") == want or p.get("bot") == want:
            return [{k: v for k, v in sp.items()} for sp in p.get("spans") or []]
    return []


def build(s):
    rows, data_to, sources = {"lit": lit, "atlas": atlas, "blitz": blitz, "poseidon": poseidon}[s]()
    rows.sort(key=lambda x: (x[1], x[2] or 0, x[0]))
    R = ROOMS[s]
    return {"v": V, "s": s, **R, "data_to": data_to, "sources": sources, "cols": COLS, "spans": spans(rows, data_to),
            "research": research_spans(s), "equity": equity(rows), "n": len(rows), "trades": rows,
            "note": "Backtest = the research replay on CME NQ futures bars, costs in: not money made. Live = the real MFFU accounts. "
                    "Paper = simulated trades." + (" This strategy trades on PAPER only." if R["paper"] else "")}


def dump(o) -> str:
    return json.dumps(o, separators=(",", ":"), ensure_ascii=False, sort_keys=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    stale = []
    for s in ROOMS:
        raw = dump(build(s))
        p = os.path.join(a.out, s + ".json")
        old = open(p, encoding="utf-8").read() if os.path.exists(p) else None
        if a.check:
            if old != raw:
                stale.append(s)
            continue
        if old != raw:
            with open(p + ".tmp", "w", encoding="utf-8") as fh:
                fh.write(raw)
            os.replace(p + ".tmp", p)
        print(f"{s}: {len(raw) / 1024:.0f} KB")
    if a.check and stale:
        print("stale:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
