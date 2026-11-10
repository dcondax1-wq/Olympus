#!/usr/bin/env python3
"""SIBYL's own paper ledger: it records the picks Sibyl made, one by one, and settles them later. SUGGESTIONS ONLY: it never places a bet, never calls Kalshi,
never touches the bot, and reads only two local files (sibyl.json from tools/money/sibyl.py and, optionally, a results file).

    python tools/money/sibyl_ledger.py --sibyl DIR/sibyl.json --state DIR/sibyl_forward.json                  # append today's picks (once each)
    python tools/money/sibyl_ledger.py --sibyl DIR/sibyl.json --state DIR/sibyl_forward.json --results results.json    # ... and settle what the results file knows
    python tools/money/sibyl_ledger.py --selftest

The state file IS the published file (the Sibyl page reads `money/sibyl_forward.json`):
  * start_day is frozen the first time the ledger runs; nothing before it is ever counted, nothing is back-filled (no look-ahead).
  * a pick is recorded once, on the day Sibyl made it, with its stake in $ and in R (1R = that paper stake), its price and what it would pay.
  * only a FRESH study (status "ok") is recorded: a stale or sample file adds nothing (--include-sample is for tests).
  * results file: {"results":[{"id":"2026-11-10|95-97c","outcome":"won"|"lost"|"void"}]} (id as in the ledger, or {"day","title"} instead of id).
    won = +win_usd, lost = -stake_usd (-1.0R), void = $0. A settled bet is never changed again.
  * the summary says "collecting" below MIN_N settled bets and makes no claim: n is always shown, and net / win rate are only stated at MIN_N or more.
A damaged state file is refused (exit 2) rather than restarted silently, because the start date must stay frozen. Writes are atomic (temp file + rename).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import tempfile

MIN_N = 30
KEEP_BETS = 400
OUTCOMES = ("won", "lost", "void")


def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    return None


def usd(x, sign=False):
    v = round(abs(x) + 1e-9, 2)
    return ("-" if x < 0 and v else "+" if sign and v else "") + f"${v:,.2f}"


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            j = json.load(fh)
        return j if isinstance(j, dict) else None
    except (OSError, ValueError):
        return None


def save(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sf-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def new_state(day):
    return {"v": 1, "kind": "sibyl-forward", "mode": "paper", "start_day": day, "min_n": MIN_N, "bets": []}


def valid_state(s):
    return (isinstance(s, dict) and s.get("v") == 1 and s.get("kind") == "sibyl-forward" and isinstance(s.get("bets"), list) and isinstance(s.get("start_day"), str)
            and all(isinstance(b, dict) and isinstance(b.get("id"), str) and b.get("status") in ("open", "won", "lost", "void") for b in s["bets"]))


def day_of(sib):
    a = str(sib.get("asof") or "")[:10]
    try:
        dt.date.fromisoformat(a)
        return a
    except ValueError:
        return None


def record(state, sib, include_sample=False):
    """append today's picks (once each). Returns the number added."""
    if not isinstance(sib, dict) or sib.get("id") != "sibyl":
        return 0
    if sib.get("status") != "ok" and not (include_sample and sib.get("status") == "sample"):
        return 0
    day = day_of(sib)
    if not day or day < state["start_day"]:
        return 0
    have = {b["id"] for b in state["bets"]}
    added = 0
    for it in sib.get("items", []):
        if not isinstance(it, dict) or not it.get("picked"):
            continue
        stake, win = num(it.get("stake_usd")), num(it.get("win_usd"))
        if not stake or stake <= 0 or win is None:
            continue
        bid = f"{day}|{str(it.get('title'))[:60]}"
        if bid in have:
            continue
        state["bets"].append({"id": bid, "day": day, "title": str(it.get("title"))[:60], "type": str(it.get("type"))[:24], "n_basis": int(num(it.get("n")) or 0),
                              "stake_usd": round(stake, 2), "stake_pct": num(it.get("stake_pct")) or 0.0, "win_usd": round(win, 2), "edge_c": num(it.get("edge_c")),
                              "status": "open", "pnl_usd": None, "r": None, "settled_day": None})
        have.add(bid)
        added += 1
    state["bets"] = state["bets"][-KEEP_BETS:]
    return added


def settle(state, results, today):
    """settle open bets from a results file ({"results":[...]}). Returns the number settled. A settled bet is never touched again."""
    rows = results.get("results") if isinstance(results, dict) else None
    if not isinstance(rows, list):
        return 0
    by = {b["id"]: b for b in state["bets"]}
    n = 0
    for r in rows:
        if not isinstance(r, dict) or r.get("outcome") not in OUTCOMES:
            continue
        bid = r.get("id") if isinstance(r.get("id"), str) else f"{r.get('day')}|{r.get('title')}"
        b = by.get(bid)
        if not b or b["status"] != "open":
            continue
        o = r["outcome"]
        b["status"] = o
        b["pnl_usd"] = round(b["win_usd"] if o == "won" else -b["stake_usd"] if o == "lost" else 0.0, 2)
        b["r"] = round(b["pnl_usd"] / b["stake_usd"], 2)
        b["settled_day"] = today
        n += 1
    return n


def summary(state):
    bets = state["bets"]
    done = [b for b in bets if b["status"] in ("won", "lost")]
    n = len(done)
    wins = sum(1 for b in done if b["status"] == "won")
    net = round(sum(b["pnl_usd"] for b in done), 2)
    staked = round(sum(b["stake_usd"] for b in done), 2)
    st = "collecting" if n < MIN_N else "early" if n < 100 else "building"
    s = {"n_bets": len(bets), "n_open": sum(1 for b in bets if b["status"] == "open"), "n_settled": n, "n_void": sum(1 for b in bets if b["status"] == "void"),
         "status": st, "claim": n >= MIN_N, "wins": wins, "losses": n - wins}
    if n >= MIN_N:
        s.update({"win_rate": round(wins / n, 4), "net_usd": net, "avg_stake_usd": round(staked / n, 2), "net_r": round(net / (staked / n), 1) if staked else 0.0})
        s["text"] = (f"{n} settled paper bets since {state['start_day']} (n={n}): {wins} won, {n - wins} lost, net {usd(net, True)} ({s['net_r']:+.1f}R at the average stake of {usd(staked / n)}). "
                     + ("Still a small sample: luck can look like skill." if n < 100 else "A bigger sample, but still a short stretch of one market."))
    else:
        s["text"] = (f"Collecting: {n} settled paper bets since {state['start_day']} ({s['n_open']} still open). n={n}, fewer than {MIN_N}: no claim is made, and net and win rate stay hidden until then.")
    return s


def publish(state):
    state["summary"] = summary(state)
    return state


def run(sibyl_path, state_path, results_path=None, include_sample=False, today=None):
    """-> (exit code, message). 2 = the state file is damaged (nothing written); 0 otherwise."""
    sib = load(sibyl_path)
    if sib is None:
        return 0, "no sibyl.json to record: nothing changed"
    state = None
    if os.path.exists(state_path):
        state = load(state_path)
        if not valid_state(state):
            return 2, "the ledger file is damaged: nothing changed (restore it, or delete it to start over; the start date is frozen)"
    day = day_of(sib) or (today or dt.date.today().isoformat())
    first = state is None
    if first:
        state = new_state(day)
    added = record(state, sib, include_sample)
    settled = 0
    if results_path:
        res = load(results_path)
        settled = settle(state, res, today or day) if res else 0
    publish(state)
    if first or added or settled or not os.path.exists(state_path):
        save(state_path, state)
    s = state["summary"]
    return 0, f"{'started ' + state['start_day'] + ': ' if first else ''}added {added}, settled {settled}. {s['text']}"


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    bad = []

    def ck(name, ok, info=""):
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"))
        if not ok:
            bad.append(name)

    def sib(day, status="ok", picks=(("95-97c", 3.41, 0.12),)):
        return {"id": "sibyl", "asof": day + "T12:00:00Z", "status": status,
                "items": [{"title": t, "type": "Price band", "picked": True, "n": 600, "stake_usd": s, "stake_pct": 2.0, "win_usd": w, "edge_c": 0.5} for t, s, w in picks] + [{"title": "x", "picked": False}]}
    d = tempfile.mkdtemp(prefix="sibyl-led-")
    sp, st = os.path.join(d, "sibyl.json"), os.path.join(d, "sibyl_forward.json")
    json.dump(sib("2026-11-10"), open(sp, "w"))
    code, msg = run(sp, st)
    s1 = load(st)
    ck("first run: the start day is frozen to the study's day, one pick is recorded open with its stake and win in $", code == 0 and s1["start_day"] == "2026-11-10" and len(s1["bets"]) == 1 and s1["bets"][0]["status"] == "open" and s1["bets"][0]["stake_usd"] == 3.41, msg)
    run(sp, st)
    ck("running again the same day adds nothing (each pick once)", len(load(st)["bets"]) == 1)
    json.dump(sib("2026-11-11", picks=(("95-97c", 3.41, 0.12), ("Bitcoin", 3.0, 0.1))), open(sp, "w"))
    run(sp, st)
    s2 = load(st)
    ck("next day: the new picks are appended, the start day does not move", len(s2["bets"]) == 3 and s2["start_day"] == "2026-11-10")
    json.dump(sib("2026-11-01"), open(sp, "w"))
    run(sp, st)
    ck("a study dated before the start is never back-filled", len(load(st)["bets"]) == 3)
    json.dump(sib("2026-11-12", status="stale"), open(sp, "w"))
    run(sp, st)
    json.dump(sib("2026-11-12", status="sample"), open(sp, "w"))
    run(sp, st)
    ck("a stale or sample study records nothing", len(load(st)["bets"]) == 3)
    rp = os.path.join(d, "results.json")
    json.dump({"results": [{"id": "2026-11-10|95-97c", "outcome": "won"}, {"day": "2026-11-11", "title": "95-97c", "outcome": "lost"}, {"id": "2026-11-11|Bitcoin", "outcome": "void"}, {"id": "nope", "outcome": "won"}, {"id": "2026-11-10|95-97c", "outcome": "lost"}, 5]}, open(rp, "w"))
    run(sp, st, rp)
    s3 = load(st)
    b = {x["id"]: x for x in s3["bets"]}
    ck("settling: won = +win_usd, lost = -stake (-1.0R), void = $0; unknown ids, junk rows and a second result for a settled bet are ignored",
       b["2026-11-10|95-97c"]["pnl_usd"] == 0.12 and b["2026-11-10|95-97c"]["status"] == "won" and b["2026-11-11|95-97c"]["pnl_usd"] == -3.41 and b["2026-11-11|95-97c"]["r"] == -1.0 and b["2026-11-11|Bitcoin"]["pnl_usd"] == 0.0, b)
    sm = s3["summary"]
    ck("under 30 settled: collecting, n shown, 'no claim', and no net or win rate in the file", sm["status"] == "collecting" and sm["n_settled"] == 2 and "no claim" in sm["text"] and "n=2" in sm["text"] and "net_usd" not in sm and sm["claim"] is False, sm)
    big = new_state("2026-01-01")
    for i in range(40):
        big["bets"].append({"id": f"d{i}|x", "day": "2026-01-01", "title": "x", "stake_usd": 2.0, "win_usd": 0.1, "status": "won" if i % 10 else "lost", "pnl_usd": 0.1 if i % 10 else -2.0, "r": 0.05})
    sb = summary(big)
    ck("at 30 or more settled: the claim is stated with its n, the net and the R; still called a small sample", sb["claim"] and sb["n_settled"] == 40 and sb["wins"] == 36 and "n=40" in sb["text"] and "small sample" in sb["text"] and "net_usd" in sb, sb)
    open(st, "w").write("{broken")
    code, msg = run(sp, st)
    ck("a damaged ledger is refused (exit 2) and left untouched, never restarted", code == 2 and open(st).read() == "{broken")
    ck("no sibyl.json: nothing happens, no crash", run(os.path.join(d, "none.json"), os.path.join(d, "x.json"))[0] == 0)
    src = open(os.path.abspath(__file__), encoding="utf-8").read().split("# ----", 1)[0]
    import re
    ck("never trades or phones out: no network, engine or bot import", not re.search(r"^\s*(import|from)\s+(urllib|requests|socket|http|ssl|engine|live)\b", src, re.M))
    print(f"\n{'ALL PASS' if not bad else str(len(bad)) + ' FAILED'}")
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sibyl's own paper ledger (suggestions only).")
    ap.add_argument("--sibyl", help="sibyl.json written by tools/money/sibyl.py")
    ap.add_argument("--state", help="sibyl_forward.json (read, appended, written)")
    ap.add_argument("--results", help="optional results file")
    ap.add_argument("--include-sample", action="store_true", help="tests only: record a sample study")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.sibyl or not a.state:
        ap.error("--sibyl and --state are required (or --selftest)")
    code, msg = run(a.sibyl, a.state, a.results, a.include_sample)
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
