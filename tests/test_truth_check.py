"""TRUTH CHECK (Olympus 2 "data truth", tools/truth_check.py + tools/web_public/age.js): offline, on the published feeds and the PC's post as they
were at 2026-11-20 ~10:20 ET (tests/fixtures/truth). ~2 s, no network, no browser.
  a. the truth from the PC post: ATLAS $25,401.38 / room $1,401.38 / today +$514.18 / last trade 2026-11-20 +$514.18; Zlarior 50K $49,192.78
  b. the feed checks: home.json's cloud paper twin ($49,900) under the real 50K id is flagged with shown vs right; the Rapid (buying) is a note;
     ATLAS's 2026-11-20 trade not in trades.json yet is a note; a stale PC post is flagged
  c. the page scanner's patterns: a wrong balance / room is caught, plan constants and backtest totals are not
  d. age.js = one format and one set of limits, the same as nq/nqdesk.js (updated / ageLevel)
    python -X utf8 -m tests.test_truth_check
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import truth_check as TC  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "truth")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:900]}"))


def main():
    post = json.load(open(os.path.join(FX, "pc_post.json"), encoding="utf-8"))
    now = post["reporter"]["t"] + 600                     # 10 minutes after the report
    T = TC.truth_of(post, now)
    a = T.get("atlas", {})
    check("a. the truth from the PC post: ATLAS $25,401.38, room $1,401.38, today +$514.18, last trade 2026-11-20 +$514.18 (TARGET)",
          a.get("balance") == 25401.38 and a.get("room") == 1401.38 and a.get("today") == 514.18 and a.get("last", {}).get("day") == "2026-11-20"
          and a["last"]["usd"] == 514.18 and a.get("funded") is True, a)
    check("a. ATLAS 'to payout' = the payout coach's need_more on the PC's tracker (the number pc_feed.js payoutLines gives every page): $948.62, not the PC's own $1,448.62 ping line",
          a.get("to_payout") == 948.62 and a.get("to_target") == 1448.62, (a.get("to_payout"), a.get("to_target")))
    pr = [float(m.group(1).replace(",", "")) for m in TC.PAYOUT_RX.finditer("ATLAS LIVE FUNDED $25,401 TODAY +$514 TO PAYOUT $1,449 ROOM LEFT $1,401 · To payout $949")]
    check("c. the 'to payout' scanner reads both pages' words (Glance $1,449 vs NQ / Board $949)", pr == [1449.0, 949.0], pr)
    check("a. ... Zlarior 50K $49,192.78 / $1,024.58, 25K #2 $25,000; no Rapid yet (not on the PC)", T["z50k"]["balance"] == 49192.78 and T["z50k"]["room"] == 1024.58
          and T["z25k2"]["balance"] == 25000 and "rapid" not in T, sorted(T))
    R = TC.feed_checks(os.path.join(FX, "site"), now, os.path.join(FX, "pc_post.json"))
    P = {(p["where"], p["wrong"], p["right"]) for p in R["problems"]}
    check("b. home.json's cloud paper twin under the real 50K id: flagged, shown $49,900 vs the PC's $49,192.78 (accounts[], board.lit, live.eval)",
          ("home.json accounts[id=mffu50k_eval]", "$49,900", "$49,192.78") in P and ("home.json board.lit", "$49,900", "$49,192.78") in P
          and ("home.json live.eval", "$49,900", "$49,192.78") in P, R["problems"])
    notes = " | ".join(p["what"] for p in R["info"])
    check("b. notes: the Rapid EOD 25K is not on the PC yet (plan 'buying'); ATLAS's 2026-11-20 +$514.18 is not in trades.json yet (pages add the PC's trades)",
          "Rapid EOD 25K is not in the PC's report (plan says 'buying')" in notes and "the 2026-11-20 trade ($514.18) is not in the file yet" in notes, notes)
    R2 = TC.feed_checks(os.path.join(FX, "site"), now + 3600, os.path.join(FX, "pc_post.json"))
    check("b. an hour later the PC post itself is flagged stale (it posts every 15 min)", any(p["where"] == "PC status post" and "old" in p["what"] for p in R2["problems"]), R2["problems"])
    # finder round 2026-11-20: a STOPPED bot (pc.running false / the paper adapter) posts its paper twin's numbers (the 50K's room $1,771 vs the
    # real $1,025): they are not the truth; the last LIVE balances (life.acc) are, and the report says why
    import copy
    stp = copy.deepcopy(post)
    stp["pc"]["running"] = False; stp["pc"]["adapter"] = "paper"
    for a0 in stp["accounts"]:
        if a0.get("id") == "mffu50k_eval":
            a0["eval"]["room"] = 1771.0; a0["eval"]["balance"] = 49938.2
    TS = TC.truth_of(stp, now)
    check("b. a stopped bot (running false, paper adapter): its paper $49,938 / room $1,771 are NOT the truth; the last LIVE balance $49,192.78 is, labelled 'bot stopped: paper numbers'",
          TC.bot_stopped(stp) == "bot stopped: paper numbers" and TS["z50k"]["balance"] == 49192.78 and TS["z50k"]["room"] is None and TS["z50k"]["stopped"]
          and TS["atlas"]["balance"] == 25401.38 and TC.bot_stopped(post) == "", TS)
    md = TC.report_md(R, now)
    check("b. the report: the truth table + problems with shown / should be", "| ATLAS 25K | $25,401.38 | $1,401.38 |" in md and "| warn | home.json accounts[id=mffu50k_eval]" in md, md[:600])
    # c. the scanner's patterns (no browser: the same regexes on text)
    def scan(txt):
        bal_ok = {round(r["balance"]) for r in T.values()} | TC.CONST
        bad = []
        for m in TC.MONEY_RX.finditer(txt):
            v = float(m.group(1).replace(",", ""))
            near = txt[max(0, m.start() - 40):m.end() + 12]
            if 23000 <= v <= 56000 and not any(abs(round(v) - c) <= 1 for c in bal_ok) and not TC.NOT_STATE.search(near):
                bad.append(v)
        rooms = [float(m.group(1).replace(",", "")) for m in TC.ROOM_RX.finditer(txt)]
        return bad, rooms
    b1, r1 = scan("MFFU 50K Eval  $49,900 · Drawdown left $1,900")
    b2, _ = scan("Net +$43,820 in 2026 H1 · target $53,000 · first payout when the profit is at least $1,350 (balance $26,350) · You wrote ATLAS · you  ATLAS balance $26,946.10")
    b3, _ = scan("ATLAS 25K funded $25,401 today +$514")
    check("c. the scanner: the twin's $49,900 + 'Drawdown left $1,900' are caught; backtest net, targets, payout lines and the owner's dated note are not; the truth is clean",
          b1 == [49900.0] and r1 == [1900.0] and b2 == [] and b3 == [], (b1, r1, b2, b3))
    # d. one age format and the same limits in age.js and nqdesk.js
    exe = shutil.which("node")
    if not exe:
        check("d. node skipped", True)
        return
    js = r"""
const A = require(process.argv[2]);
import(process.argv[3]).then((D) => {
  const S = [30, 240, 1500, 2 * 3600 + 600, 30 * 3600, 4 * 86400];
  console.log(JSON.stringify({ a: S.map(A.text), d: S.map(D.updated), la: S.map((s) => A.level(s, 'pc')), ld: S.map((s) => D.ageLevel(s, 'pc')),
    lim: [A.LIMITS.pc, D.AGE_LIMITS.pc, A.LIMITS.bars, D.AGE_LIMITS.bars, A.LIMITS.daily, D.AGE_LIMITS.daily], none: [A.text(null), A.level(null, 'pc')] }));
});
"""
    tmp = os.path.join(FX, "_h.cjs")
    mjs = os.path.join(FX, "_nqdesk.mjs")
    try:
        open(tmp, "w").write(js)
        shutil.copy(os.path.join(ROOT, "tools", "web_public", "nq", "nqdesk.js"), mjs)
        r = subprocess.run([exe, tmp, os.path.join(ROOT, "tools", "web_public", "age.js"), mjs], capture_output=True, text=True, timeout=30)
        o = json.loads(r.stdout) if r.returncode == 0 else {"err": r.stderr[-400:]}
    finally:
        for f in (tmp, mjs):
            if os.path.exists(f):
                os.remove(f)
    check("d. age.js: 'updated just now / 4 min / 25 min / 2 h 10 min / 30 h / 4 days ago'; nqdesk says the same words",
          o.get("a") == ["updated just now", "updated 4 min ago", "updated 25 min ago", "updated 2 h 10 min ago", "updated 30 h ago", "updated 4 days ago"]
          and o.get("d") == o.get("a"), o)
    check("d. one set of limits (PC report amber after 20 min, red after 1 h; candles 80 min / 3 h; nightly files 26 h / 3 days) in both; unknown age = amber",
          o.get("la") == o.get("ld") == ["ok", "ok", "warn", "bad", "bad", "bad"] and o["lim"][0] == o["lim"][1] == [1200, 3600]
          and o["lim"][2] == o["lim"][3] and o["lim"][4] == o["lim"][5] and o["none"] == ["age unknown", "warn"], o)


if __name__ == "__main__":
    main()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
