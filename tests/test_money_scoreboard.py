"""MONEY SCOREBOARD (tools/money_scoreboard.py, 2026-11-13): one file with every money source, read-only. Checks:
  a. the accounts are read by the SAME rules as tools/web_public/olympus/truth.js accountsOf (node runs truth.js on the same home.json)
  b. the maths by hand: auto eval fees at the owner's real prices, a ledger fee replacing the auto one, a hidden auto key, recurring
     costs, payouts received vs requested, Kalshi (deposits / the bot's own total / none), week / month / all time, ROI on eval fees,
     the run-rate (too early under 28 days), milestones and ETAs, bot-recorded payouts not counted twice
  c. honesty: a missing source is listed as missing and adds nothing; paper P&L and money-machine estimates are never cash; the
     ledger stays out of a written file unless --private or "publish": true; notes are never written
  d. the CLI: --site writes <site>/money/scoreboard.json, falls back to data.json, junk files do not crash it, --print writes nothing;
     no network, no secrets, the CLAUDE.md prices
    python -X utf8 -m tests.test_money_scoreboard
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import money_scoreboard as MS  # noqa: E402

HOME_REAL = os.path.join(ROOT, "tests", "fixtures", "argus", "home_real.json")
TRUTH = os.path.join(ROOT, "tools", "web_public", "olympus", "truth.js")
RES = []
NOW = 1794762000          # 2026-11-15 17:00 UTC = Sunday 12:00 ET


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def near(a, b, tol=0.005):
    return a is not None and b is not None and abs(a - b) <= tol


def led(entries, hidden=(), publish=False):
    return {"state": "ok", "entries": [MS.clean_entry(e) for e in entries], "hidden": list(hidden), "publish": publish, "t": NOW - 3600}


def rules():
    with open(os.path.join(ROOT, "tools", "web_public", "ledger", "rules.json"), encoding="utf-8") as fh:
        return json.load(fh)


def plans():
    with open(os.path.join(ROOT, "tools", "web_public", "plutus", "plans.json"), encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------------------------------------ a. truth.js parity
def part_a():
    with open(HOME_REAL, encoding="utf-8") as fh:
        home = json.load(fh)
    variants = {"real": home,
                "no_board": {k: v for k, v in home.items() if k != "board"},
                "cloud_only": {"accounts": [{"id": "cloud_paper", "name": "Paper (cloud)", "source": "cloud", "eval": {"balance": 1, "room": 5}}]},
                "funded": {"accounts": [{"id": "mffu50k", "name": "MFFU 50K", "kind": "funded", "eval": {"balance": 52100, "room": 1800, "start_balance": 50000}, "conn": {"t": 1793000000}}]},
                "junk": {"board": "x", "accounts": "junk", "second": 3}}
    node = shutil.which("node")
    if not node:
        check("a. node is here for the truth.js parity check", False, "no node")
        return
    tmp = tempfile.mkdtemp(prefix="msb_truth_")
    try:
        src = os.path.join(tmp, "homes.json")
        with open(src, "w", encoding="utf-8") as fh:
            json.dump(variants, fh)
        js = ("import fs from 'fs'; import * as T from " + json.dumps("file://" + TRUTH) + ";"
              "const V = JSON.parse(fs.readFileSync(" + json.dumps(src) + ", 'utf8')); const out = {};"
              "for (const k of Object.keys(V)) out[k] = T.accountsOf(V[k]); console.log('@@' + JSON.stringify(out));")
        p = subprocess.run([node, "--input-type=module", "-e", js], capture_output=True, text=True, timeout=60)
        line = [x for x in p.stdout.splitlines() if x.startswith("@@")]
        if not line:
            check("a. truth.js ran in node", False, p.stderr[-400:])
            return
        want = json.loads(line[-1][2:])
        bad = []
        for name, h in variants.items():
            got = MS.accounts_of(h)
            for key in ("lit", "atlas", "blitz"):
                g, w = got[key], want[name][key]
                for f in ("has", "balance", "profit", "today", "week", "room", "mll", "kind", "status", "t", "src"):
                    gv, wv = g.get(f), w.get(f)
                    same = (near(gv, wv, 1e-6) if isinstance(wv, (int, float)) and not isinstance(wv, bool) and gv is not None else gv == wv or (gv in (None, "") and wv in (None, "")))
                    if not same:
                        bad.append((name, key, f, gv, wv))
        check("a. the accounts (has, balance, profit, today, week, room, mll, kind, status, report time, published field) equal truth.js accountsOf on 5 homes "
              "(the real home.json, no board, only the cloud paper twin, a funded row, junk)", not bad, bad[:6])
        r = MS.accounts_of(home)
        check("a. on the real home.json: LIT from board.lit (-$699.10, room $1,132.70 of $2,000), ATLAS from board.atlas (room capped at its $1,000 max loss), BLITZ paper from live.pc.blitz",
              r["lit"]["src"] == "board.lit" and near(r["lit"]["profit"], -699.1) and near(r["lit"]["room"], 1132.7) and r["atlas"]["src"] == "board.atlas"
              and r["atlas"]["room"] == 1000 and r["blitz"]["src"] == "live.pc.blitz" and r["blitz"]["paper"], r)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ b. the maths by hand
def part_b():
    R, P = rules(), plans()
    today = MS.today_et(NOW)
    check("b. the clock: 2026-11-15 17:00 UTC is Sunday 15 Nov in New York; its week starts Monday 9 Nov", today == "2026-11-15" and MS.week_start(today) == "2026-11-09", (today, MS.week_start(today)))
    check("b. dates: 31 Jan + 1 month = 28 Feb (29 in 2028), across a year, junk dates refused",
          MS.add_months("2026-01-31", 1) == "2026-02-28" and MS.add_months("2028-01-31", 1) == "2028-02-29" and MS.add_months("2026-11-15", 3) == "2027-02-15"
          and not MS.is_date("2026-02-30") and not MS.is_date("x") and MS.is_date("2028-02-29"))

    # 1. nothing but the prices: the two real purchases, $91.80 (2026-10-18) + $43 (2026-10-26)
    sb = MS.build({"rules": R, "plans": P}, NOW)
    fees = sorted((r["id"], r["fees"]) for r in sb["by_source"])
    check("b. no other source: the eval fees the owner really paid are filled in from ledger/rules.json (Builder 50K $91.80, ATLAS 25K $43); net -$134.80; nothing else invented",
          fees == [("atlas25k", 43.0), ("lit50k", 91.8)] and near(sb["totals"]["all"]["net"], -134.8) and sb["totals"]["all"]["cash_in"] == 0 and not sb["paper"]
          and sb["machines"] is None and all(r["auto_fee"] for r in sb["by_source"]), (fees, sb["totals"]["all"]))
    sb0 = MS.build({}, NOW)
    check("b. without rules.json the CLAUDE.md prices are used (the same two fees) and the prices source says so",
          sorted((r["id"], r["fees"]) for r in sb0["by_source"]) == [("atlas25k", 43.0), ("lit50k", 91.8)] and "CLAUDE.md" in [s for s in sb0["sources"] if s["id"] == "prices"][0]["note"])

    # 2. the owner's ledger
    E = [{"kind": "fee", "amount": 91.8, "date": "2026-10-18", "acct": "lit50k", "note": "secret note"},       # his own fee: replaces the auto one
         {"kind": "reset", "amount": 80, "date": "2026-11-10", "acct": "lit50k"},
         {"kind": "payout_req", "amount": 1000, "date": "2026-11-05", "acct": "lit50k"},
         {"kind": "payout_in", "amount": 800, "date": "2026-11-12", "acct": "lit50k"},                          # the 80% split of the request: not pending
         {"kind": "payout_req", "amount": 500, "date": "2026-11-13", "acct": "atlas25k"},                      # still pending
         {"kind": "expense", "amount": 12, "date": "2026-09-04", "acct": "general", "rec": {"every": "month"}},  # Sep 4, Oct 4, Nov 4 = 36
         {"kind": "income", "amount": 50, "date": "2026-11-14"},
         {"kind": "deposit", "amount": 100, "date": "2026-10-01", "acct": "kalshi"},
         {"kind": "tax", "amount": 4, "date": "2026-11-03"}]
    feed = {"v": 3, "kind": "kalshi", "t": NOW - 600, "balance": 128.4, "total_pnl": -81.77, "week_pnl": 2.0,
            "days": [["2026-11-14", 5.0], ["2026-11-09", -3.0], ["2026-11-02", -2.0], ["2026-10-30", 6.87]]}
    sb = MS.build({"rules": R, "plans": P, "kalshi": feed, "ledger": led(E)}, NOW, include_ledger=True)
    T, by = sb["totals"], {r["id"]: r for r in sb["by_source"]}
    # all time: in 800 + 50 = 850, Kalshi result 128.40 - 100 = +28.40 (deposits recorded); out 91.80 + 43 + 80 + 36 = 250.80
    check("b. all time by hand: cash in 850 + Kalshi +28.40 = 878.40; out 91.80 + 43 (auto ATLAS fee) + 80 reset + 3 x 12 = 250.80; net +627.60; pending 500 (the 1,000 request is matched by the 800 = 80% split)",
          near(T["all"]["cash_in"], 878.4) and near(T["all"]["cash_out"], 250.8) and near(T["all"]["net"], 627.6) and near(T["all"]["pending"], 500), T["all"])
    check("b. his own fee for lit50k replaces the auto one (counted once); the ATLAS fee stays auto", by["lit50k"]["fees"] == 91.8 and not by["lit50k"]["auto_fee"] and by["atlas25k"]["auto_fee"], by["lit50k"])
    # this week (Mon 9 - Sun 15 Nov): payout 800 + income 50, reset 80; Kalshi days 5 - 3 = +2  -> in 852, out 80, net 772
    check("b. this week (Mon 9 to Sun 15 Nov): in 800 + 50 + Kalshi days (+5 - 3) = 852, out 80 (the reset), net +772",
          near(T["week"]["cash_in"], 852) and near(T["week"]["cash_out"], 80) and near(T["week"]["net"], 772), T["week"])
    # this month (1 - 15 Nov): in 850, out 80 + 12 (Nov 4), Kalshi 5 - 3 - 2 = 0 -> net 758
    check("b. this month (1 to 15 Nov): in 850, out 80 + 12 (the Nov 4 copy of the monthly cost), Kalshi 5 - 3 - 2 = 0, net +758",
          near(T["month"]["net"], 758) and near(T["month"]["kalshi"], 0) and near(T["month"]["cash_out"], 92), T["month"])
    check("b. Kalshi row: balance basis (balance + withdrawals - deposits = +28.40), the week from its days (+2)",
          by["kalshi"]["basis"] == "balance" and near(by["kalshi"]["net"], 28.4) and near(by["kalshi"]["week"], 2), by["kalshi"])
    check("b. ROI on eval fees: fees + reset 91.80 + 43 + 80 = 214.80, 800 back: +272.4%",
          near(sb["roi"]["fees"], 214.8) and near(sb["roi"]["back"], 800) and near(sb["roi"]["pct"], 272.44), sb["roi"])
    # run-rate: first cash date 2026-09-04 -> 73 days -> 627.60 / (73 / 30.4375)
    check("b. run-rate: 73 days since the first entry (4 Sep), +$627.60 -> $261.68 a month; the plan estimate = LIT $771 + ATLAS $519 (Plutus H2) = $1,290",
          sb["run_rate"]["days"] == 73 and near(sb["run_rate"]["cash_per_month"], round(627.6 / (73 / 30.4375), 2)) and sb["run_rate"]["plan"]["per_month"] == 1290, sb["run_rate"])
    nx = sb["next"]
    check("b. next milestone $10,000: $9,372.40 to go, 36 months at the cash pace (ceil 9,372.40 / 261.68), 8 at the plan estimate; dates from today",
          nx["usd"] == 10000 and near(nx["left"], 9372.4) and nx["eta_cash"]["months"] == 36 and nx["eta_cash"]["date"] == "2029-11-15" and nx["eta_plan"]["months"] == 8
          and [m["usd"] for m in sb["milestones"]] == [10000, 100000, 1000000], nx)
    check("b. Kalshi without recorded deposits = the bot's own total P&L; without a feed = nothing (basis none, adds 0)",
          MS.kalshi_result([], feed)["basis"] == "bot" and MS.kalshi_result([], feed)["result"] == -81.77 and MS.kalshi_result([], None)["basis"] == "none"
          and MS.kalshi_in(MS.kalshi_result([], None), "2026-11-01", "2026-11-15", "month") == 0)
    k2 = MS.kalshi_result([], {"kind": "kalshi", "t": NOW - 60, "total_pnl": 10, "week_pnl": 4, "month_pnl": 9})
    check("b. a feed without days: its own week / month figures when its report is inside the window",
          MS.kalshi_in(k2, "2026-11-09", "2026-11-15", "week") == 4 and MS.kalshi_in(k2, "2026-11-01", "2026-11-15", "month") == 9 and MS.kalshi_in(k2, "2026-10-01", "2026-10-31", "month") == 0)
    sbh = MS.build({"rules": R, "ledger": led(E, hidden=["auto:fee:atlas25k"])}, NOW)
    check("b. a hidden auto key (the Ledger's 'Not mine') drops that auto fee", not any(r["id"] == "atlas25k" and r.get("fees") for r in sbh["by_source"]), [r["id"] for r in sbh["by_source"]])
    sbs = MS.build({"rules": R}, MS.to_s("2026-10-30T16:00:00Z"))
    check("b. a cash run-rate needs 28 days: 13 days after the first fee it says too early, no ETA at the cash pace",
          sbs["run_rate"]["cash_per_month"] is None and "Too early" in sbs["run_rate"]["text"] and sbs["next"]["eta_cash"] is None, sbs["run_rate"])

    # 3. payouts recorded with the bot (home.json goals.money.payouts)
    home = {"goals": {"money": {"payouts": [{"day": "2026-11-12", "gross": 1000, "to_you": 800, "type": "mffu_b50", "name": "Zlarior 50K"},
                                              {"day": "2026-11-13", "gross": 500, "to_you": 400, "type": "atlas", "name": "ATLAS 25K"},
                                              {"day": "2026-12-01", "gross": 9, "to_you": 9, "name": "future"}, {"day": "bad", "to_you": 5}]}}}
    sbp = MS.build({"rules": R, "home": home, "ledger": led(E)}, NOW, include_ledger=True)
    byp = {r["id"]: r for r in sbp["by_source"]}
    check("b. payouts recorded with the bot count (what reached you: 400 for ATLAS); the 50K one the ledger already has (same day, $800) is not counted twice; future / junk ones are dropped",
          near(byp["lit50k"]["payouts"], 800) and near(byp["atlas25k"]["payouts"], 400) and [s for s in sbp["sources"] if s["id"] == "payouts"][0]["status"] == "ok", (byp["lit50k"]["payouts"], byp["atlas25k"]["payouts"]))


# ------------------------------------------------------------------------------------------------ c. honesty
def part_c():
    R, P = rules(), plans()
    with open(HOME_REAL, encoding="utf-8") as fh:
        home = json.load(fh)
    sb = MS.build({"rules": R, "plans": P, "home": home}, NOW)
    miss = {m["id"] for m in sb["missing"]}
    check("c. every source is listed with a status and an age; the ones not given (Kalshi, ledger, money machines) are listed as missing",
          {"kalshi", "ledger", "machines"} <= miss and all({"id", "status", "age", "note"} <= set(s) for s in sb["sources"]), [(s["id"], s["status"]) for s in sb["sources"]])
    check("c. a missing source adds nothing: with no Kalshi feed and no ledger the net is only the two eval fees (-$134.80)", near(sb["totals"]["all"]["net"], -134.8), sb["totals"]["all"])
    paper = {p["id"]: p for p in sb["paper"]}
    check("c. paper P&L (BLITZ, the second strategies, the eval accounts' simulated profit) is shown but never counted as cash",
          "blitz" in paper and "second" in paper and paper["second"]["profit"] > 0 and sb["totals"]["all"]["cash_in"] == 0
          and all("not cash" in r["paper"]["text"] for r in sb["by_source"] if r.get("paper")), list(paper))
    check("c. the accounts' age is the PC report time (live.pc.t), 'stale' past 36 hours", [s for s in sb["sources"] if s["id"] == "accounts"][0]["t"] == home["live"]["pc"]["t"]
          and [s for s in sb["sources"] if s["id"] == "accounts"][0]["status"] == "stale")
    mi = {"v": 1, "asof": "2026-11-15T16:00:00Z", "total": {"base": 1493.81, "real_base": 0.0}, "counts": {"streams": 2, "ok": 0, "sample": 2},
          "streams": [{"id": "chrysos", "name": "Chrysos", "status": "sample", "usd_month": {"base": 1339.01}}, {"id": "sibyl", "name": "Sibyl", "status": "sample", "usd_month": {"base": 7.5}}]}
    sbm = MS.build({"rules": R, "machines": mi}, NOW)
    check("c. the money machines are estimates: listed with their status (sample), never added to the totals", sbm["machines"]["status"] == "sample" and sbm["machines"]["usd_month"] == 1493.81
          and near(sbm["totals"]["all"]["net"], -134.8) and [s for s in sbm["sources"] if s["id"] == "machines"][0]["status"] == "sample", sbm["machines"])
    L = led([{"kind": "payout_in", "amount": 800, "date": "2026-11-12", "acct": "lit50k", "note": "my bank"}])
    priv, pub, forced = MS.build({"rules": R, "ledger": L}, NOW, include_ledger=False), MS.build({"rules": R, "ledger": {**L, "publish": True}}, NOW, include_ledger=False), MS.build({"rules": R, "ledger": L}, NOW, include_ledger=True)
    check("c. the ledger is private by default: kept out of the written copy (status 'private', a note says how to show it); \"publish\": true or --private counts it",
          not priv["ledger_included"] and near(priv["totals"]["all"]["cash_in"], 0) and [s for s in priv["sources"] if s["id"] == "ledger"][0]["status"] == "private"
          and pub["ledger_included"] and near(pub["totals"]["all"]["cash_in"], 800) and forced["ledger_included"], [s for s in priv["sources"] if s["id"] == "ledger"])
    check("c. notes are never written (the entry's text stays in the owner's file)", "my bank" not in json.dumps(forced) and "note" not in L["entries"][0])
    junk = MS.build({"home": {"board": [], "accounts": [1, None, "x"], "goals": {"money": {"payouts": "x"}}, "second": {"strategies": [1, {"paper": "x"}]}},
                     "kalshi": {"kind": "other", "balance": 5}, "machines": {"streams": "x"}, "rules": {"accounts": {"x": {"price": "junk"}}}, "plans": [], "ledger": led([])}, NOW)
    check("c. junk everywhere does not crash it and invents nothing (a Kalshi file of another kind is not the feed)", junk["v"] == 1 and not any(r["id"] == "kalshi" for r in junk["by_source"]), junk["totals"]["all"])


# ------------------------------------------------------------------------------------------------ d. the CLI and the files
def part_d():
    tmp = tempfile.mkdtemp(prefix="msb_cli_")
    try:
        site = os.path.join(tmp, "site")
        os.makedirs(os.path.join(site, "money"))
        shutil.copy(HOME_REAL, os.path.join(site, "data.json"))           # only data.json: the fallback
        with open(os.path.join(site, "kalshi.json"), "w", encoding="utf-8") as fh:
            json.dump({"v": 3, "kind": "kalshi", "t": NOW - 120, "balance": 55.81, "total_pnl": -81.77, "days": [["2026-11-14", -1.5]]}, fh)
        with open(os.path.join(site, "money", "index.json"), "w", encoding="utf-8") as fh:
            fh.write("{broken")
        ledger = os.path.join(tmp, "money_ledger.json")
        with open(ledger, "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "app": "ledger", "entries": [{"kind": "payout_in", "amount": 400, "date": "2026-11-12", "acct": "atlas25k", "note": "n"}, {"kind": "nope"}]}, fh)
        env = {**os.environ, "OLYMPUS_HOME": os.path.join(tmp, "olympus")}
        p = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "money_scoreboard.py"), "--site", site, "--ledger", ledger, "--now", str(NOW)],
                           capture_output=True, text=True, timeout=60, env=env)
        out = os.path.join(site, "money", "scoreboard.json")
        sb = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else {}
        src = {s["id"]: s for s in sb.get("sources", [])}
        check("d. --site writes <site>/money/scoreboard.json from data.json when there is no home.json; the Kalshi feed is read; a broken money/index.json is listed missing",
              p.returncode == 0 and sb.get("kind") == "olympus-money-scoreboard" and src["accounts"]["file"] == "data.json" and src["kalshi"]["status"] == "ok" and src["machines"]["status"] == "missing",
              (p.stdout[-300:], p.stderr[-300:], {k: v["status"] for k, v in src.items()}))
        check("d. ... and the ledger stays private in that public copy (no --private, no \"publish\": true)", sb.get("ledger_included") is False and src["ledger"]["status"] == "private"
              and not any(r.get("payouts") for r in sb.get("by_source", [])), src.get("ledger"))
        p2 = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "money_scoreboard.py"), "--site", site, "--ledger", ledger, "--now", str(NOW), "--print"],
                            capture_output=True, text=True, timeout=60, env=env)
        check("d. --print shows the plain table (cash in / out / net, each source, ROI, run-rate, milestone, missing) and counts the ledger (local view)",
              "| Cash in |" in p2.stdout and "ROI on eval fees" in p2.stdout and "Next milestone" in p2.stdout and "$400" in p2.stdout and "Missing:" in p2.stdout, p2.stdout[-800:])
        p3 = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "money_scoreboard.py"), "--site", os.path.join(tmp, "nothing"), "--ledger", os.path.join(tmp, "none.json"),
                             "--out", os.path.join(tmp, "o", "sb.json"), "--now", str(NOW)], capture_output=True, text=True, timeout=60, env=env)
        sb3 = json.load(open(os.path.join(tmp, "o", "sb.json"), encoding="utf-8"))
        check("d. an empty site: exit 0, a file with the fees only and every other source missing", p3.returncode == 0 and near(sb3["totals"]["all"]["net"], -134.8)
              and {"kalshi", "ledger", "machines"} <= {m["id"] for m in sb3["missing"]}, [m["id"] for m in sb3["missing"]])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    code = open(os.path.join(ROOT, "tools", "money_scoreboard.py"), encoding="utf-8").read()
    check("d. read-only and offline: no network module, no subprocess, no order / arm / route word in code, writes only the scoreboard file",
          not re.search(r"^\s*(import|from)\s+(urllib|http|socket|requests|subprocess)", code, re.M) and "place_order" not in code and code.count("open(tmp, \"w\"") == 1)
    check("d. no key, token or secret in the file", not re.search(r"api[_-]?key|password|access[_-]?token|bearer|\bsk-[A-Za-z0-9]{10}", code, re.I))
    with open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as fh:
        cm = fh.read()
    check("d. the fallback prices are the CLAUDE.md prices ($91.80 50K, $63 25K, $43 ATLAS 25K, $0 activation) and equal ledger/rules.json",
          "Builder 50K $91.80" in cm and "Builder 25K $63" in cm and "$43" in cm and MS.PRICES == {"builder_50k": 91.8, "builder_25k": 63.0, "atlas_25k": 43.0, "activation": 0.0}
          and {k: v["price"] for k, v in rules()["accounts"].items()} == {k: v["price"] for k, v in MS.FALLBACK_ACCOUNTS.items()})
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("d. the owner's ledger, the local scoreboard copy and the Sunday reports are gitignored", all(x in gi for x in ("data/money_ledger.json", "tools/web_public/money/", "docs/reports/money_week_*.md")))


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
