"""engine/mffu_view.py: the PC's small "mf" block for the MFFU account center (tools/web_public/business/mffu.html). Offline, no
network, no browser.

  a. owner_name: the owner's names ("Zlarior 50K", "Zlarior 25K #2", "ATLAS 25K funded"), never a broker id; the same table the
     page's twin (business/mffucenter.js ownerName) runs in tests/test_mffu_center.py
  b. compact(L) on a busy day of the 3 real accounts: names, start, last traded day, trades / wins, the MFFU dashboard stats
     (profit factor, average win / loss, best / worst trade, contracts), best / worst day, equity, the funded payout tracker;
     last 4 digits only; ~200-280 bytes an account
  c. cut_eq: 4 points, then 0 = no equity line and no dashboard stats (the names, dates and the tracker stay)
  d. only trade / day news: a new live balance or an open position does not change mf (the ext post's news hash stays)
  e. the split (tools/pc_report.posts): every post under 3,900 bytes on a busy day, mf rides the ext post whole
  f. junk in -> None / no raise
  g. the trade alerts' names: save_names (data/pc_report/names.json: last 4 -> "Zlarior 50K") and push_name for an alert's label

    python -X utf8 -m tests.test_mffu_view
"""
from __future__ import annotations

import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import mffu_view as MV  # noqa: E402

RES: list = []
T0 = 1795044381                      # 2026-11-18 18:26 ET (the PC's real report time that evening)

# (id, name, plan, stage) -> the owner's name; tests/test_mffu_center.py runs the same table through mffucenter.js
NAME_CASES = [
    [["mffu50k_eval", "MFFU 50K Eval", "Builder 50K", "eval"], "Zlarior 50K"],
    [["lit", "Zlarior", "MFFU Builder 50K", "eval"], "Zlarior 50K"],
    [["b25k_2", "Zlarior Builder 25K #2", "Builder 25K", "eval"], "Zlarior 25K #2"],
    [["atlas", "ATLAS", "MFFU Builder 25K funded", "funded"], "ATLAS 25K funded"],
    [["atlas", "ATLAS", "MFFU Builder 25K", "eval"], "ATLAS 25K"],
    [["fresh25", "Zlarior 25K #2", "MFFU Builder 25K", "eval"], "Zlarior 25K #2"],
    [["zlarior", "Zlarior", "MFFU Builder 50K", "funded"], "Zlarior 50K funded"],
    [["rapid1", "Rapid EOD 25K (next)", "MFFU Rapid EOD 25K", "eval"], "Rapid EOD 25K"],
    [["x9", "MFFUEVBLDR000006016", "Builder 50K", "eval"], "Zlarior 50K"],
    [["acct_b", "ATLAS MFFUSFBLDR000006018", "", "payout_ready"], "ATLAS funded"],
    [["b50k_3", "Zlarior #3", "", "eval"], "Zlarior 50K #3"],
]


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:400]})" if info and not cond else ""))


def size(o) -> int:
    return len(json.dumps(o, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def trade(day, et, side, qty, pnl, exit_="STOP"):
    return {"day": day, "entry_t": et, "exit_t": et + 1800, "side": side, "qty": qty, "entry": 27400.0, "stop": 27380.0, "target": 27500.0,
            "exit_px": 27380.0, "exit": exit_, "r": round(pnl / 160.0, 2), "pnl": pnl}


def live_L():
    """The PC's full live.json on a busy day: Zlarior 50K eval (bot ledger: 4 days, 5 trades), the 25K #2 eval (2 trades today),
    ATLAS's FUNDED 25K (board card + its live trades)."""
    z_trades = [trade("2026-11-12", T0 - 6 * 86400, "LONG", 6, 640.0, "TARGET"), trade("2026-11-13", T0 - 5 * 86400, "SHORT", 5, -210.0),
                trade("2026-11-16", T0 - 2 * 86400, "LONG", 4, -129.4), trade("2026-11-16", T0 - 2 * 86400 + 3600, "SHORT", 4, 0.0, "BE"),
                trade("2026-11-18", T0 - 30000, "LONG", 6, 455.2, "TARGET")]
    n_trades = [trade("2026-11-18", T0 - 30000, "LONG", 3, 227.6, "TARGET"), trade("2026-11-18", T0 - 20000, "SHORT", 3, -98.1)]
    return {
        "t": T0, "price": 27387.5,
        "accounts": [
            {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "source": "pc", "badge": "LIVE",
             "broker_account": "MFFUEVBLDR000006016", "eval": {"start": "2026-10-19", "start_balance": 50000.0, "balance": 49647.98},
             "days": [["2026-11-12", 640.0], ["2026-11-13", -210.0], ["2026-11-16", -129.4], ["2026-11-18", 455.2]], "trades": z_trades,
             "stats": {"n": 5, "wins": 2, "pf": 3.18, "avg_win": 547.6, "avg_loss": -169.7},
             "position": {"entry_t": T0 - 600, "side": "LONG", "qty": 6, "entry": 27390.0, "stop": 27370.0, "target": 27480.0}},
            {"id": "b25k_2", "name": "Zlarior Builder 25K #2", "plan": "Builder 25K", "kind": "eval", "source": "pc", "badge": "LIVE",
             "broker_account": "MFFUEVBLDR000006019", "eval": {"start": "2026-11-18", "start_balance": 25000.0, "balance": 25129.5},
             "days": [["2026-11-18", 129.5]], "trades": n_trades, "stats": {}},
            {"id": "paper1", "kind": "eval", "source": "cloud", "eval": {"balance": 1}},          # a cloud paper ledger: never a row
            {"id": "acct_c", "kind": "eval", "source": "pc", "eval": {"balance": 1}},             # BLITZ's account C: never a row
        ],
        "board": {"t": T0, "data_t": T0,
                  "lit": {"id": "lit", "balance": 49647.98, "today_pnl": 455.2, "status": "open"},
                  "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K funded", "broker": "MFFUSFBLDR000006018", "balance": 24887.2,
                            "profit": -112.8, "today_pnl": -112.8, "status": "funded", "stage": "funded", "eval_start": "2026-11-17",
                            "funded": {"status": "building", "cycle_profit": -112.8, "best_day": -112.8, "cycle_days": 1, "eligible_from": "2026-11-20",
                                       "payouts_n": 0, "max_request": 0.0, "paid_to_you": 0.0, "text": "x" * 200, "why": ["y" * 100]}},
                  "trades": [{"acct": "atlas", "src": "live", "day": "2026-11-18", "entry_t": T0 - 49000, "exit_t": T0 - 47800, "side": "SHORT",
                              "qty": 2, "exit": "STOP", "r": -1.04, "usd": -112.8, "open": False},
                             {"acct": "atlas", "src": "paper", "day": "2026-11-17", "entry_t": T0 - 116000, "side": "LONG", "qty": 4, "usd": 2687.84},
                             {"acct": "atlas", "src": "live", "day": "2026-11-18", "entry_t": T0 - 9000, "side": "LONG", "qty": 2, "open": True}]},
    }


def part_a():
    got = [[c[0], MV.owner_name(*c[0]), c[1]] for c in NAME_CASES]
    bad = [g for g in got if g[1] != g[2]]
    check(f"a. owner_name: the owner's names on {len(NAME_CASES)} cases (Zlarior 50K, Zlarior 25K #2, ATLAS 25K funded, Rapid EOD 25K ...)",
          not bad, bad)
    check("a. owner_name never carries a broker id's digits; junk -> a plain word, never raises",
          "6016" not in MV.owner_name("x", "MFFUEVBLDR000006016", "", "eval") and "6018" not in MV.owner_name("atlas", "ATLAS MFFUSFBLDR000006018")
          and MV.owner_name() == "Zlarior" and isinstance(MV.owner_name(object(), 5, [1], {}), str))


def part_b():
    L = live_L()
    mf = MV.compact(L)
    rows = {r["id"]: r for r in (mf or {}).get("a") or []}
    z, n, a = rows.get("mffu50k_eval") or {}, rows.get("b25k_2") or {}, rows.get("atlas") or {}
    check("b. 3 real accounts (no cloud paper ledger, no BLITZ account C), the board time", list(rows) == ["mffu50k_eval", "b25k_2", "atlas"]
          and mf.get("t") == T0, list(rows))
    check("b. Zlarior 50K: name, ...6016, start Oct 19, 4 traded days, last traded Nov 18, 5 trades 2 won, best / worst day, equity",
          z.get("nm") == "Zlarior 50K" and z.get("l4") == "6016" and z.get("sd") == "2026-10-19" and z.get("td") == 4 and z.get("lt") == "2026-11-18"
          and z.get("n") == 5 and z.get("w") == 2 and z.get("bd") == ["2026-11-12", 640] and z.get("wd") == ["2026-11-13", -210]
          and z.get("eq") == [-1108, -468, -678, -807, -352], z)
    check("b. Zlarior 50K: MFFU's dashboard stats (the ledger's own PF / average win / loss; best / worst trade, 25 contracts)",
          z.get("pf") == 3.18 and z.get("aw") == 548 and z.get("al") == -170 and z.get("bt") == 640 and z.get("wt") == -210 and z.get("ct") == 25, z)
    check("b. Zlarior 25K #2: name, ...6019, started today, 1 day, 2 trades 1 won, PF 2.32 from its trades, last traded today",
          n.get("nm") == "Zlarior 25K #2" and n.get("l4") == "6019" and n.get("sd") == "2026-11-18" and n.get("td") == 1 and n.get("n") == 2
          and n.get("w") == 1 and n.get("pf") == 2.32 and n.get("aw") == 228 and n.get("al") == -98 and n.get("ct") == 6 and n.get("lt") == "2026-11-18", n)
    check("b. ATLAS 25K funded: name, ...6018, live trades only (no paper, no open), the payout tracker (status, eligible from Nov 20)",
          a.get("nm") == "ATLAS 25K funded" and a.get("l4") == "6018" and a.get("sd") == "2026-11-17" and a.get("n") == 1 and a.get("lt") == "2026-11-18"
          and a.get("wt") == -113 and a.get("ct") == 2 and a.get("f") == {"cp": -113, "bd": -113, "cd": 1, "ef": "2026-11-20", "pn": 0, "mr": 0, "st": "building"}, a)
    raw = json.dumps(mf)
    check("b. no broker id, no tracker text, last 4 only", "MFFUEVBLDR" not in raw and "MFFUSFBLDR" not in raw and "000006016" not in raw
          and "xxxx" not in raw and "yyyy" not in raw, raw[:300])
    per = [size(r) for r in mf["a"]]
    check("b. size: ~200-280 bytes an account (each under 300), the block under 800", max(per) <= 300 and size(mf) <= 800, (per, size(mf)))
    L2 = copy.deepcopy(L)
    L2["board"]["atlas"]["funded"].update(first_trade="2026-11-18", paid_to_you=800.0, payouts_n=1, status="eligible")
    f2 = [r for r in MV.compact(L2)["a"] if r["id"] == "atlas"][0]["f"]
    check("b. the tracker's first trade day and $ paid to you ride when there", f2.get("ft") == "2026-11-18" and f2.get("pt") == 800 and f2.get("pn") == 1
          and f2.get("st") == "eligible", f2)
    return L, mf


def part_c(mf):
    m4 = copy.deepcopy(mf)
    MV.cut_eq(m4, 4)
    z4 = m4["a"][0]
    m0 = copy.deepcopy(mf)
    MV.cut_eq(m0, 0)
    z0 = m0["a"][0]
    check("c. cut_eq(4): the last 4 equity points, the stats stay", z4.get("eq") == [-468, -678, -807, -352] and z4.get("pf") == 3.18)
    check("c. cut_eq(0): no equity line, no dashboard stats; names, dates, days, trades, best / worst day and the tracker stay",
          all("eq" not in r and not any(k in r for k in MV.STATS) for r in m0["a"]) and z0.get("nm") == "Zlarior 50K" and z0.get("lt") == "2026-11-18"
          and z0.get("n") == 5 and z0.get("bd") and m0["a"][2].get("f", {}).get("ef") == "2026-11-20" and size(m0) < size(mf) - 150, (z0, size(m0), size(mf)))
    MV.cut_eq(None, 0)
    MV.cut_eq({"a": [None, 3, {"eq": "x"}]}, 2)
    check("c. cut_eq on junk never raises", True)


def part_d(L, mf):
    L2 = copy.deepcopy(L)
    L2["board"]["lit"].update(today_pnl=-300.0)
    L2["accounts"][0]["position"] = {"entry_t": T0 - 60, "side": "SHORT", "qty": 4, "entry": 27410.0, "stop": 27430.0, "target": 27300.0}
    L2["accounts"][1]["position"] = None
    L2["price"] = 27000.0
    L2["board"]["t"] = L2["board"]["data_t"] = T0 + 900
    a, b = mf, MV.compact(L2)
    check("d. a new open position / today's live $ / price leave mf the same (only t moves): the ext post is not re-sent for it",
          a["a"] == b["a"] and b["t"] == T0 + 900)


def part_e(L):
    from tools import pc_report as R
    t = T0
    L = copy.deepcopy(L)
    for a in L["accounts"][:2]:                   # a busy day: 4 trades on each account (the "at" block full)
        a["trades"] = (a["trades"] * 2)[-4:]
    ev = [{"t": t - 60 * i, "stage": "eval", "title": "Zlarior 50K closed +$455 | day +$455 | room $1,480 " + "z" * 40} for i in range(6)]
    snap = {"t": t, "hb_t": t - 60, "live": L, "server": True, "nt": True, "market_open": True, "mode": "LIVE",
            "hb": {"life": {"acc": {"lit": {"label": "Zlarior 50K", "stage": "eval", "since": t - 86400, "bal": 49648},
                                    "atlas": {"label": "ATLAS 25K", "stage": "funded", "since": t - 86400, "bal": 24887.2},
                                    "x:b25k_2": {"label": "Zlarior Builder 25K #2", "stage": "eval", "since": t - 3600, "bal": 25129.5}},
                            "ev": ev}},
            "kalshi_rewards": {"net": 2.1, "days": 1.5, "updated": "2026-11-18"}}
    core, exts = R.posts(snap)
    sizes = [R._size(x) for x in [core, *exts]]
    merged = R.merged(snap)
    mfm = merged.get("mf") or {}
    full = MV.compact(L)
    check("e. busy day: every post under 3,900 bytes, mf rides an ext post (not the core), merged back whole (names, stats, equity)",
          all(s <= R.MAX_STATUS_BYTES for s in sizes) and "mf" not in core and any("mf" in e.get("x", {}) for e in exts)
          and mfm.get("a") == full.get("a") and not any("mf" in (e.get("cut") or []) for e in exts), (sizes, [e.get("cut") for e in exts]))
    raw = json.dumps([core, *exts])
    check("e. the public posts: no broker id", "MFFUEVBLDR0000" not in raw and "MFFUSFBLDR0000" not in raw)


def part_f():
    check("f. junk in -> None, never raises", MV.compact(None) is None and MV.compact({"accounts": "x", "board": 3}) is None
          and MV.compact({"accounts": [None, 5, {"id": "z", "kind": "eval", "error": "x"}]}) is None
          and MV.compact({"accounts": [{"id": "q", "kind": "funded", "source": "pc", "days": [["bad"], 5, ["2026-11-18", "x"]],
                                        "trades": [None, {"pnl": "x"}], "stats": "no", "funded": [1]}]})["a"][0]["id"] == "q")


def part_g(mf):
    """the trade alerts' names: names.json from the mf block, push_name for an alert's account label"""
    import tempfile
    d = tempfile.mkdtemp()
    path = os.path.join(d, "pc_report", "names.json")
    none = [MV.push_name(x, path=path) for x in ("MFFUEVBLDR123456016", "ATLAS 25K", "Zlarior Builder 25K #2", "MFFU 50K", "", None, "FLEET MFFU Builder 50K x")]
    check("g. no names file yet: an id label stays the caller's (None), a size label maps by words, junk -> None",
          none == [None, "ATLAS 25K", "Zlarior 25K #2", "Zlarior 50K", None, None, None], none)
    ok = MV.save_names(mf, path=path)
    saved = json.load(open(path, encoding="utf-8"))
    check("g. save_names: last 4 -> the owner's name, PC id -> name (no full id in the file)",
          ok and saved == {"l4": {"6016": "Zlarior 50K", "6019": "Zlarior 25K #2", "6018": "ATLAS 25K funded"},
                           "id": {"mffu50k_eval": "Zlarior 50K", "b25k_2": "Zlarior 25K #2", "atlas": "ATLAS 25K funded"}}, saved)
    got = [MV.push_name(x, path=path) for x in ("MFFUEVBLDR123456016", "ATLAS MFFUSFBLDR000006018", "ATLAS 25K", "Zlarior Builder 25K #2",
                                                 "MFFUEVBLDR000009999", "Zlarior ...6019")]
    check("g. push_name with the file: ...6016 -> Zlarior 50K, ATLAS's label -> ATLAS 25K funded, the 25K #2 by its words or ...6019, an unknown id -> None",
          got == ["Zlarior 50K", "ATLAS 25K funded", "ATLAS 25K funded", "Zlarior 25K #2", None, "Zlarior 25K #2"], got)
    t0 = os.path.getmtime(path)
    same = MV.save_names(copy.deepcopy(mf), path=path) and os.path.getmtime(path) == t0
    dup = copy.deepcopy(mf)
    dup["a"][1]["l4"] = "6016"                     # two accounts ending in 6016: that last 4 is left out
    MV.save_names(dup, path=path)
    d2 = json.load(open(path, encoding="utf-8"))
    check("g. unchanged -> not rewritten; a last 4 shared by two accounts is left out (never the wrong name)",
          same and "6016" not in d2["l4"] and MV.push_name("MFFUEVBLDR123456016", path=path) is None, d2)
    check("g. save_names / push_name never raise", MV.save_names(None, path=path) is False and MV.save_names({"a": [None, {"nm": 5}]}, path=os.path.join(d, "x", "\0bad")) in (True, False)
          and MV.push_name(object(), path=path) is None)


def main() -> int:
    part_a()
    L, mf = part_b()
    part_c(mf)
    part_d(L, mf)
    part_e(L)
    part_f()
    part_g(mf)
    print(f"mffu view: {sum(RES)}/{len(RES)} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
