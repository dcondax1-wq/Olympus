"""K8 dry run on the LAST REAL windows (Nov 16-19, 2026): the real executor (engine/kalshi_clock.ClockLoop) on a fake clock and a
fake Kalshi whose books are rebuilt from the PUBLIC tape at the moment the bot reads them (our side's real taker prices from +20 s),
and whose results are Kalshi's real ones. Two passes on the real $55 settings (research/lab/kalshi_clock.json):
  paper  not armed (what the PC does now): the paper ledger per leg;
  live   armed by the test typing the phrase into a temp folder, a FAKE key and the fake Kalshi (no network, no real order):
         the orders the bot would have sent (side, contracts, limit price, expiry) and the P&L from the fills.
Checks per leg-day: the right side, 4-5 contracts at $2.50, the price vs the study's +20 s walk (research/kalshi_k8_monday/k8m_data),
the settle = Kalshi's result, the $ = contracts x $1 - cost - the exact fee.

    python research/kalshi_k8_monday/dryrun.py    -> research/kalshi_k8_monday/dryrun.json
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile

import k8m_data as D

sys.path.insert(0, D.ROOT)
from engine import kalshi_clock as KC, kalshi_live as KL  # noqa: E402
from tests import test_kalshi_clock as T, test_kalshi_live as TL  # noqa: E402

OUT = os.path.join(D.HERE, "dryrun.json")
DAYS = [dt.date(2026, 11, 16), dt.date(2026, 11, 17), dt.date(2026, 11, 18), dt.date(2026, 11, 19)]
REAL = KC.CFG_PATH if not KC.CFG_PATH.endswith("clock_15.json") else T.REAL_CFG


def book_from_tape(tr, side, t_from, span=5.0):
    """Our side's ask levels at t_from s, from the PUBLIC tape: the prices takers of our side really paid in the next `span` seconds,
    in time order, each level at least as dear as the one before (a book is walked cheapest first, so a later cheaper print is
    NOT offered: the bot cannot buy what only appears later). -> the fake Kalshi's (yes bids, no bids)."""
    lv, top = [], 0.0
    for s, p, c in D.our_trades(tr, side):
        if t_from <= s <= min(45.0, t_from + span):
            top = max(top, p)
            if lv and abs(lv[-1][0] - top) < 1e-9:
                lv[-1][1] += c
            else:
                lv.append([top, c])
    if not lv:
        return [], []
    other = [(round(max(0.01, lv[0][0] - 0.02), 4), 50.0)]
    if side == "no":                                    # NO is bought from the YES bids: YES bid = 1 - NO ask
        return [(round(1 - p, 4), q) for p, q in lv], [(round(1 - x, 4), q) for x, q in other]
    return [(round(1 - x, 4), q) for x, q in other], [(round(1 - p, 4), q) for p, q in lv]


def run(mode, tmp):
    KC.CFG_PATH = KL.CLOCK_PATH = REAL
    cfg = KC.load_config(REAL)[0]
    w = T.World(tmp, mode, cash=55.0)
    tape = D.tape()
    f = w.fake
    w.clock.t = KC.london_epoch(DAYS[0], 10, 14)
    armed = w.arm() if mode == "live" else (False, "paper")
    loop = w.loop()
    for d in DAYS:
        for open_t, ids in KC.windows(d, cfg):
            recs = {}
            for lid in ids:
                leg = KC.LEG[lid]
                tk = KC.ticker(leg["series"], open_t)
                rec = tape.get(tk)
                f.markets[tk] = {"ticker": tk, "event_ticker": tk.rsplit("-", 1)[0], "status": "active", "result": "",
                                 "close_time": TL.iso(open_t + 900), "yes_sub_title": "Target", "price_ranges": []}
                recs[lid] = (tk, rec)
                f.books[tk] = book_from_tape(rec["tr"], leg["side"], 20.0) if rec else ([], [])
            w.clock.t = max(w.clock.t, open_t - 30)
            # tries at +20 / +30 / +40 s: the book is rebuilt from the tape at each try
            for k in (20, 30, 40, 50):
                w.run_until(loop, open_t + k - 0.5)
                for lid, (tk, rec) in recs.items():
                    if rec:
                        f.books[tk] = book_from_tape(rec["tr"], KC.LEG[lid]["side"], float(k))
            w.run_until(loop, open_t + 60)
            for lid, (tk, rec) in recs.items():
                if rec and f.markets[tk]["status"] == "active":
                    f.settle(tk, rec["res"])
            w.run_until(loop, open_t + 17 * 60)
    return w, armed, cfg


def main():
    tmp = tempfile.mkdtemp(prefix="k8dry-")
    study = {(r["leg"], str(r["day"])): r for r in D.bets(stake=2.5, delay=20.0, legs=list(KC.LEG), first=DAYS[0], last=DAYS[-1])}
    out = {"days": [str(d) for d in DAYS], "settings": "research/lab/kalshi_clock.json ($55 rule)", "paper": [], "live": [], "checks": {}}
    for mode in ("paper", "live"):
        w, armed, cfg = run(mode, tmp)
        rs = w.paper() if mode == "paper" else w.live()
        posts = [c[3] for c in w.posts()] if mode == "live" else []
        for r in rs:
            s = study.get((r["leg"], r["day"]))
            tape_res = D.tape().get(r["ticker"], {}).get("res")
            want_side = KC.LEG[r["leg"]]["side"]
            row = {"day": r["day"], "leg": r["leg"], "ticker": r["ticker"], "side": r["side"], "status": r.get("status"), "why": r.get("why"),
                   "n": r.get("n"), "price": r.get("price"), "fee": r.get("fee"), "result": r.get("result"), "pnl": r.get("pnl"),
                   "study_n": s.get("n") if s else None, "study_price": s.get("price") if s else None, "study_pnl": s.get("pnl") if s else None,
                   "kalshi_result": tape_res, "right_side": r["side"] == want_side,
                   "settled_right": (r.get("result") == ("won" if tape_res == want_side else "lost")) if r.get("result") in ("won", "lost") else None}
            if r.get("result") in ("won", "lost"):
                row["pnl_check"] = abs(((r["n"] if r["result"] == "won" else 0) - r["cost"] - r["fee"]) - r["pnl"]) < 0.006
                row["fee_check"] = abs(D.fee(r["cost"] / r["n"], r["n"]) - r["fee"]) < 1e-9 if mode == "paper" else True
            out[mode].append(row)
        settled = [x for x in out[mode] if x["result"] in ("won", "lost")]
        out["checks"][mode] = {"armed": armed[0], "rows": len(out[mode]), "settled": len(settled),
                               "right_side": all(x["right_side"] for x in out[mode]),
                               "settled_right": all(x["settled_right"] for x in settled),
                               "pnl_right": all(x.get("pnl_check") for x in settled), "fee_right": all(x.get("fee_check") for x in settled),
                               "size_ok": all(1 <= x["n"] and x["n"] * x["price"] <= 2.5 + 1e-9 for x in settled),
                               "price_gap_c": [round(100 * (x["price"] - x["study_price"]), 2) for x in settled if x["study_price"]],
                               "net": round(sum(x["pnl"] or 0 for x in settled), 2), "won": sum(1 for x in settled if x["result"] == "won"),
                               "orders": [{k: b.get(k) for k in ("ticker", "side", "count", "price", "expiration_time")} for b in posts if b]}
        print(mode, json.dumps({k: v for k, v in out["checks"][mode].items() if k != "orders"}))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    for x in out["live"]:
        print(x["day"], x["leg"], x["side"], x["status"], x["n"], x["price"], x["result"], x["pnl"], "| study", x["study_n"], x["study_price"], x["study_pnl"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
