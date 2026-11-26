"""ZEUS learned + the learn night (night-learnloop 2026-11-19): engine/zeus_learn.py (the PC's nightly per-strategy scorecard
inside the data pipe's child), tools/learn_night.py (the cloud's one command), the metals bars of the data feed, the ZEUS page
card. Offline: temp folders, fake pushes / steps, a fake clock; never the network, never a live file.

  a. pure pieces: one trade per signal ($ of every live account, R + slippage of the primary fill), the path (MFE / MAE in R on
     1-minute bars, capped at the target / stop), the anatomy words (losers up +0.5R first vs never, what winners kept), the RTH
     range + VIX band, the regime split, "tested and rejected" (break-even ideas are in docs/TESTED_AND_REJECTED.md)
  b. one strategy: an edge slipping over 40 trades -> a Decide proposal (let Claude test it), a calm-market split already
     rejected -> watching only, real slippage -> a cost proposal; the breaker's SIZE DOWN reported, never applied; K8 from its ledger
  c. the night on day folders: the line ("ZEUS learned Nov 19: Zlarior 1 trade +$156, edge GREEN, ..."), BLITZ hidden from the
     line / tiny / public cut, tiny <= 220 bytes, files written, ONE push a night (not twice), LE_LEARNED_PUSH=0 = none,
     no account name in the public cut, live_model*.json untouched
  d. the data pipe hook: DP.run(learn=True) learns after the review and puts learn.json in the day; a test run (work given,
     learn not asked) does not learn (the old suites see the same pushes)
  e. the PC status: gather reads logs/learn/tiny.json, the ext post carries "zl" under 3,900 bytes
  f. more data: GC / SI 1-minute bars only around 04:45-05:45 / 15:45-17:15 ET (+ London 09:45-10:45), no metals 5m, ES / NQ as
     before; the feed's zip stays under its 2 MB cap, the cloud's extract takes learn.json + GC bars, refuses other names;
     data_pull.import_metals appends to data/metals/<SYM>_1m.csv once (idempotent)
  g. the cloud: tools/learn_night.py plan (pull, edge, anatomy, lab, learned, decide), fake steps, the card learned.json from the
     PC's learn.json, the Decide card gets the proposal once (test_decide's schema), hidden bots never, dry run writes nothing
  h. the ZEUS page: node learned() (feed vs cloud, newer wins, old flag), the card section, text only, zeus.js?v>=4 (v=5 since 405abfad)
  i. faster thinking: the 15-minute report in a fresh process imports no numpy / pandas / openpyxl (the light calendar, atlas.json
     read directly, a lazy numpy in health_band, the business workbook cached on disk); pct_of = the numpy version; the data
     pipe's every-tick collect uses a key index (same rows); the ops tick's internet probes run side by side
    python -X utf8 -m tests.test_learn_night
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["LE_PR_NO_NET"] = "1"

from engine import zeus_learn as ZL  # noqa: E402

ET = ZoneInfo("America/New_York")
RES: list = []
DAY = "2026-11-19"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def ts(day, hh, mm=0, tz=ET):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hh, mm), tz).timestamp())


def wjson(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def gzlines(rows) -> bytes:
    return gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode(), mtime=0)


def bars_gz(rows) -> bytes:
    return gzip.compress(("time,open,high,low,close,volume\n" + "".join(f"{t},{o},{h},{l},{c},{v}\n" for t, o, h, l, c, v in rows)).encode(), mtime=0)


def day_bars(day, base=21000.0, step=0.25, wiggle=1.0):
    """09:00-16:00 ET 1-minute bars: a slow drift up by `step` a minute, +-wiggle."""
    out = []
    for i in range(420):
        t = ts(day, 9) + 60 * i
        p = base + step * i
        out.append((t, p, p + wiggle, p - wiggle, p + step / 2, 100))
    return out


def write_day(dd, day, trades, twin_rows=None, bars=None):
    d = os.path.join(dd, day)
    os.makedirs(os.path.join(d, "bars"), exist_ok=True)
    with open(os.path.join(d, "trades.jsonl.gz"), "wb") as fh:
        fh.write(gzlines(trades))
    with open(os.path.join(d, "twin.json.gz"), "wb") as fh:
        fh.write(gzip.compress(json.dumps({"day": day, "nightly": {"day": day, "verdict": "same", "text": "live = backtest",
                                                                     "rows": twin_rows or []}, "reviews": []}).encode(), mtime=0))
    if bars:
        with open(os.path.join(d, "bars", "NQ_1m.csv.gz"), "wb") as fh:
            fh.write(bars_gz(bars))
    wjson(os.path.join(d, "manifest.json"), {"v": 1, "day": day, "partial": False,
                                             "files": {"bars/NQ_1m.csv.gz": {"rows": len(bars or [])}} if bars else {}})


def trade(src, bot, mode, e_t, x_t, side, entry, stop, target, qty, pnl, reason, fill=None, acct="main"):
    res = {"ok": True, "adapter": "paper" if mode == "paper" else "ninjatrader"}
    if fill is not None:
        res["legs"] = [{"instrument": "MNQ 12-26", "qty": qty, "filled": qty, "fill_px": fill, "ok": True}]
    return [{"t": e_t + 3, "side": side, "qty": qty, "entry": entry, "stop": stop, "target": target, "entry_t": e_t, "src": src, "bot": bot,
             "acct": acct, "mode": mode, "result": res},
            {"t": x_t, "side": "exit", "qty": qty, "entry_t": e_t, "exit_t": x_t, "reason": reason, "pnl": pnl, "src": src, "bot": bot,
             "acct": acct, "mode": mode, "result": {"ok": True}}]


def make_root(tmp):
    """A fake bot folder: VIX, the PC's edge result, the hidden switch, the K8 ledger, the real registry + rejected list."""
    r = os.path.join(tmp, "root")
    os.makedirs(os.path.join(r, "data"), exist_ok=True)
    with open(os.path.join(r, "data", "VIX_1d.csv"), "w") as fh:
        fh.write("date,open,high,low,close\n2026-11-17,16,17,15,16.2\n2026-11-18,16,17,14,14.1\n2026-11-19,15,16,14,15.5\n")
    wjson(os.path.join(r, "data", "edge", "tiny.json"), {"d": "2026-11-18", "z": ["G", 3.8, 3.9], "a": ["A", 1.9, 2.8, "2026-11-18"],
                                                         "t": ts(DAY, 17, 1)})
    wjson(os.path.join(r, "dashboard_view.json"), {"hidden_bots": ["blitz"]})
    k8 = []
    for i in range(30):
        d = (dt.date(2026, 10, 20) + dt.timedelta(days=i)).isoformat()
        k8.append({"id": f"{d}:gold_1700_up", "day": d, "leg": "gold_1700_up", "open_t": ts(d, 16, 45), "result": "won" if i % 3 else "lost",
                   "pnl": 6.5 if i % 3 else -14.8, "price": 0.55, "cost": 14.8, "fee": 0.3, "n": 27, "status": "settled"})
    k8.append({"id": f"{DAY}:gold_1700_up", "day": DAY, "leg": "gold_1700_up", "open_t": ts(DAY, 16, 45), "result": "won", "pnl": 7.1,
               "price": 0.52, "cost": 14.6, "fee": 0.3, "n": 28, "status": "settled"})
    wjson(os.path.join(r, "data", "kalshi_live", "clock_paper.json"), {"v": 1, "rows": k8})
    for rel in ("research/lab/zeus_lab/registry.json", "docs/TESTED_AND_REJECTED.md"):
        os.makedirs(os.path.dirname(os.path.join(r, rel)), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), os.path.join(r, rel))
    return r


def make_days(dd):
    """3 sessions: Zlarior live on 2 accounts (+ a paper copy that must not count), ATLAS live, BLITZ paper."""
    days = ["2026-11-17", "2026-11-18", DAY]
    for i, day in enumerate(days):
        b = day_bars(day, 21000.0 + 30 * i)
        T = []
        if day == DAY:
            e = ts(day, 9, 45)
            base = 21000.0 + 30 * i + 0.25 * 45
            # Zlarior LONG: stop 10 pts under, target +27; 2 live accounts + 1 paper copy, fill 2 ticks worse than planned
            T += trade("main", "zlarior", "live", e, e + 900, "buy", base, base - 10, base + 27, 3, 156.3, "TARGET", fill=base + 0.5)
            T += trade("accounts/b25k_2", "zlarior", "live", e, e + 900, "buy", base, base - 10, base + 27, 1, 52.0, "TARGET", fill=base + 0.5, acct="b25k_2")
            T += trade("fleet", "zlarior", "paper", e, e + 900, "buy", base, base - 10, base + 27, 5, 999.0, "TARGET")
            # ATLAS SHORT that drifted against it (the bars go up): a loser that never worked
            a = ts(day, 10, 30)
            pa = 21000.0 + 30 * i + 0.25 * 90
            T += trade("acctb", "atlas", "live", a, a + 1200, "sell", pa, pa + 8, pa - 16, 2, -33.0, "STOP", fill=pa)
            # BLITZ paper (hidden)
            c = ts(day, 11, 0)
            T += trade("acctc", "blitz", "paper", c, c + 300, "buy", 21040.0, 21036.0, 21048.0, 1, 12.0, "TARGET")
        write_day(dd, day, T, [{"status": "matched", "day": day, "side": "LONG", "entry_t": ts(day, 9, 45), "entry_slip_ticks": 2.0,
                                "exit_slip_ticks": 0.0, "slip_usd": -3.0, "exec_usd": -3.0, "bt_pnl": 159.3, "live_pnl": 156.3}]
                  if day == DAY else [], b)
    return days


# ================================================================================================ a. pure pieces
def part_a(tmp):
    dd = os.path.join(tmp, "days_a")
    make_days(dd)
    from engine import datapipe as DP
    days = DP.load_days(dd)
    T = ZL.signals(days)
    z = [t for t in T if t["strat"] == "zlarior"]
    check("a. one Zlarior trade per signal: the 2 live accounts' $ summed, the paper copy left out",
          len(z) == 1 and abs(z[0]["usd"] - 208.3) < 0.01 and z[0]["accounts"] == 2 and z[0]["mode"] == "live", z)
    check("a. R from the primary fill (3 micros, fill 0.5 over plan: 10.5 pts risk), slippage +2 ticks", z and z[0]["slip_ticks"] == 2.0 and
          z[0]["risk_pts"] == 10.5 and abs(z[0]["r"] - round(156.3 / (10.5 * 2 * 3), 3)) < 1e-6, z)
    bars, secs = ZL.read_bars(os.path.join(dd, DAY))
    p = ZL.path(z[0], bars, secs)
    check("a. path: MFE / MAE in R on the 1-minute bars (capped at the target)", p.get("mfe_r") is not None and 0 < p["mfe_r"] <= 27 / 9.5 + 1e-9
          and p["mae_r"] <= (9.5 + 0.25) / 9.5 + 1e-9, p)
    at = [t for t in T if t["strat"] == "atlas"][0]
    pa = ZL.path(at, bars, secs)
    check("a. a short against a rising market: MFE small, MAE capped one tick past the stop", pa["mfe_r"] < ZL.TURN_R and pa["mae_r"] <= (8.25 / 8) + 1e-9, pa)
    rows = [{"day": DAY, "usd": -50.0, "r": -1.0, "mfe_r": 0.8}, {"day": DAY, "usd": -40.0, "r": -1.0, "mfe_r": 0.1},
            {"day": DAY, "usd": 120.0, "r": 2.0, "mfe_r": 2.5}]
    an = ZL.anatomy(rows)
    check("a. anatomy: 1 of 2 losers up +0.5R first, winners kept 80% of their best move", an["turned"] == 1 and an["never"] == 1 and an["kept_pct"] == 80
          and "1 of 2 losers were up +0.5R first" in an["say"], an)
    pts, pct = ZL.rth_range(bars)
    check("a. RTH range 09:30-16:00 ET only", pts is not None and 80 < pts < 100 and pct > 0, (pts, pct))
    v = ZL.vix_closes(make_root(os.path.join(tmp, "ra")))
    check("a. VIX: the prior close (known at the open) + its band", ZL.prior_vix(v, DAY) == ("2026-11-18", 14.1) and ZL.vix_band(14.1) == "VIX <15"
          and ZL.vix_band(22) == "VIX 20-25", ZL.prior_vix(v, DAY))
    facts = {f"d{i}": {"range": "calm" if i < 10 else "normal", "vix": 18} for i in range(40)}
    T2 = [{"day": f"d{i}", "usd": (-30.0 if i < 10 else 50.0), "r": (-0.4 if i < 10 else 0.6)} for i in range(40)]
    rg = ZL.regime_split(T2, facts)
    check("a. regime split: calm days lose, the rest win -> 'calm markets' named; VIX not named", rg["slipping"] == ["calm markets"], rg)
    check("a. tested and rejected: a break-even exit idea is found in docs/TESTED_AND_REJECTED.md (never proposed again)",
          (ZL.rejected_before("turned", "zlarior") or "").startswith("Tested and rejected"), ZL.rejected_before("turned", "zlarior"))
    check("a. ZEUS Lab rejected_forever: Zlarior by the VIX level is blocked", "ZEUS Lab" in (ZL.rejected_before("VIX under 15", "zlarior") or ""))


# ================================================================================================ b. one strategy
def part_b(tmp):
    empty = os.path.join(tmp, "empty_root")
    os.makedirs(os.path.join(empty, "docs"), exist_ok=True)
    open(os.path.join(empty, "docs", "TESTED_AND_REJECTED.md"), "w").write("# nothing\n")
    T = []
    for i in range(40):
        d = (dt.date(2026, 9, 1) + dt.timedelta(days=i)).isoformat()
        T.append({"day": d, "strat": "atlas", "mode": "live", "usd": (-60.0 if i % 2 else 40.0), "r": (-1.0 if i % 2 else 0.7),
                  "qty": 2, "slip_ticks": 2.5, "dir": 1, "reason": "STOP"})
    facts = {t["day"]: {"range": "calm" if i < 12 else "normal"} for i, t in enumerate(T)}
    for i, t in enumerate(T):
        if i < 12:
            t["usd"], t["r"] = -50.0, -0.8
        else:
            t["usd"], t["r"] = (90.0, 1.2) if i % 3 else (-40.0, -0.6)
    blk = ZL.futures_block("atlas", T, facts, T[-1]["day"], ("AMBER", "edge health", "x"), {"v": {"level": "size_down", "gap_usd": -410, "gap_r": -3.4, "n": 10}},
                           None, empty)
    kinds = sorted(p["kind"] for p in blk["proposals"])
    check("b. calm days lose (not rejected in this folder) + fills 2.5 ticks worse -> 2 Decide proposals (regime, cost)",
          kinds == ["cost", "regime"] and all(p["question"].startswith("ATLAS: let Claude") for p in blk["proposals"]), blk["proposals"])
    check("b. the breaker's SIZE DOWN is reported as advice already sent, never applied", blk["verdict"].startswith("breaker says HALF size")
          and blk["breaker"]["level"] == "size_down", blk["verdict"])
    blk2 = ZL.futures_block("atlas", T, facts, T[-1]["day"], ("AMBER", "edge health", "x"), None, None, ROOT)
    check("b. with the real rejected list: the calm-market rule is watched, not proposed (the AMBER calm dip was tested)",
          not any(p["kind"] == "regime" for p in blk2["proposals"]) and any("watching only" in n for n in blk2.get("notes") or []), blk2.get("notes"))
    L = [{"day": t["day"], "strat": "zlarior", "mode": "live", "usd": -50.0 if i % 3 else 60.0, "r": -1.0 if i % 3 else 1.0, "qty": 2,
          "slip_ticks": 0.0} for i, t in enumerate(T)]
    blk3 = ZL.futures_block("zlarior", L, {}, L[-1]["day"], ("RED", "edge health", "x"), None, None, empty)
    check("b. 40 trades PF < 1 with the light not GREEN -> 'let Claude re-test it on the newest bars?'",
          any(p["kind"] == "edge" and "re-test" in p["question"] for p in blk3["proposals"]), blk3["proposals"])
    blk4 = ZL.futures_block("zlarior", L[-5:], {}, L[-1]["day"], ("GREEN", "edge health", "x"), None, None, empty)
    check("b. a few trades, light GREEN: nothing to change", blk4["verdict"] == "nothing to change" and not blk4["proposals"], blk4["verdict"])
    k = ZL.k8_block(ZL.k8_rows(make_root(os.path.join(tmp, "rb"))), DAY)
    check("b. K8 from its paper ledger: today 1 bet +$7 (paper), win rate vs the kill rule, average price paid", k and k["today"]["n"] == 1
          and k["today"]["paper"] and k["fills"]["avg_price"] is not None and k["edge"]["light"] in ("GREEN", "AMBER", "RED"), k)
    check("b. no K8 ledger on this PC: no K8 block", ZL.k8_block({}, DAY) is None)


# ================================================================================================ c. the night
def part_c_real(tmp):
    root = make_root(os.path.join(tmp, "rc"))
    dd = os.path.join(tmp, "days_c")
    make_days(dd)
    out = os.path.join(tmp, "learn_c")
    live_before = {p: hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest() for p in ("live_model.json", "live_model_lit.json")}
    pushed = []
    r = ZL.nightly(DAY, dd, out_dir=out, now=ts(DAY, 17, 20), root=root, notify=lambda text, title: pushed.append((title, text)) or (True, "ok"),
                   brk={}, env={})
    S = r["learned"]
    ln = S["line"]
    check("c. the line: 'ZEUS learned Nov 19: Zlarior 1 trade +$208, edge GREEN, ...' then ATLAS (AMBER) and K8",
          ln.startswith("ZEUS learned Nov 19: Zlarior 1 trade +$208, edge GREEN") and "ATLAS 1 trade -$33, edge AMBER" in ln and "K8 1 bet +$7 (paper)" in ln, ln)
    check("c. BLITZ (hidden) is computed but never in the line / tiny / public cut", "blitz" in S["bots"] and "BLITZ" not in ln
          and "blitz" not in json.dumps(r["public"]).lower() and "BLITZ" not in json.dumps(ZL.tiny(S)), list(S["bots"]))
    tn = ZL._read_json(os.path.join(out, "tiny.json"))
    check("c. tiny.json <= 220 bytes, read back by read_tiny; stale after 4 days", tn and ZL._bytes(tn) <= ZL.TINY_MAX
          and ZL.read_tiny(os.path.join(out, "tiny.json"), now=ts(DAY, 18)) == tn and ZL.read_tiny(os.path.join(out, "tiny.json"), now=ts(DAY, 18) + 5 * 86400) is None, tn)
    check("c. files: logs/learn/<day>.json + latest.json, the day folder's learn.json", all(os.path.exists(os.path.join(out, f)) for f in (f"{DAY}.json", "latest.json"))
          and os.path.exists(os.path.join(dd, DAY, "learn.json")))
    check("c. the market tag: prior VIX 14.1 (band <15) + the range class", S["regime"]["vix_band"] == "VIX <15" and "VIX <15" in S["regime"]["tag"], S["regime"])
    zb = S["bots"]["zlarior"]
    check("c. Zlarior: twin from fill_audit (matched 1, slip -$3), fills +2 ticks, anatomy on its path, nothing changed automatically",
          zb["twin"]["matched"] == 1 and zb["twin"]["slip_usd"] == -3.0 and zb["fills"]["entry_slip_med"] == 2.0 and zb["anatomy"]["n"] == 1
          and S["auto_changes"] == [], (zb["twin"], zb["fills"], zb["anatomy"]))
    check("c. ONE push a night, title 'ZEUS learned', the line itself", len(pushed) == 1 and pushed[0] == ("ZEUS learned", ln), pushed)
    ZL.nightly(DAY, dd, out_dir=out, now=ts(DAY, 17, 40), root=root, notify=lambda text, title: pushed.append((title, text)) or (True, "ok"), brk={}, env={})
    check("c. a second run the same night: no second push", len(pushed) == 1, pushed)
    p2 = []
    ZL.nightly(DAY, dd, out_dir=os.path.join(tmp, "learn_c2"), now=ts(DAY, 17, 20), root=root, notify=lambda t, ti: p2.append(t) or (True, "ok"),
               brk={}, env={"LE_LEARNED_PUSH": "0"})
    check("c. LE_LEARNED_PUSH=0: no push", p2 == [])
    pub = json.dumps(r["public"])
    check("c. the public cut: no per-trade rows, no account key, no path", '"trades"' not in pub and "b25k_2" not in pub and "C:\\\\" not in pub)
    live_after = {p: hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest() for p in live_before}
    check("c. live_model.json / live_model_lit.json untouched", live_before == live_after)
    ok, why = ZL._push("x", "ZEUS learned", ts(DAY, 17, 20), env={"LE_PR_NO_NET": "1"})
    check("c. the real push path is off in tests (LE_PR_NO_NET=1) and never raises", ok is False and "network off" in why, why)
    return dd, root


# ================================================================================================ d. the data pipe hook
def part_d(tmp):
    from engine import datapipe as DP
    from tests import test_datapipe as TD
    root, nt = TD.make_pc(os.path.join(tmp, "dp"))
    os.makedirs(os.path.join(tmp, "dp"), exist_ok=True)
    w = os.path.join(tmp, "dp", "work")
    learned = []
    r = DP.run(now=TD.ts(TD.DAY, 17, 30), root=root, work=w, folder=nt, push=False, build_twin=False, archive_root=os.path.join(tmp, "dp", "arc"),
               edge={"light": "GREEN"}, emit=lambda *a: {"ok": 1}, notify=lambda *a, **k: (True, "ok"), learn=True,
               learn_notify=lambda text, title: learned.append(text) or (True, "ok"))
    check("d. DP.run(learn=True): learns after the review, the line in the result, learn.json in the day folder, one push",
          (r.get("learned") or "").startswith("ZEUS learned Nov 18") and os.path.exists(os.path.join(w, "days", TD.DAY, "learn.json"))
          and len(learned) == 1 and not [e for e in r["errors"] if e.startswith("learned")], (r.get("learned"), r["errors"], learned))
    w2 = os.path.join(tmp, "dp", "work2")
    r2 = DP.run(now=TD.ts(TD.DAY, 17, 30), root=root, work=w2, folder=nt, push=False, build_twin=False, archive_root=os.path.join(tmp, "dp", "arc2"),
                edge={"light": "GREEN"}, emit=lambda *a: {"ok": 1}, notify=lambda *a, **k: (True, "ok"))
    check("d. a test run (work given, learn not asked): no learning, nothing in logs/learn", r2.get("learned") is None
          and not os.path.exists(os.path.join(w2, "learn")), r2.get("learned"))
    src = open(os.path.join(ROOT, "engine", "datapipe.py"), encoding="utf-8").read()
    check("d. datapipe: learning only on the real run by default (learn None -> work None) and LE_LEARNED=0 turns it off",
          "learn if learn is not None else work is None" in src and "LE_LEARNED" in src)


# ================================================================================================ e. the PC status
def part_e(tmp):
    from tools import pc_report as PR
    root = os.path.join(tmp, "pcs")
    tn = {"d": DAY, "t": ts(DAY, 17, 20), "s": "Zlarior 1 trade +$208, edge GREEN, nothing to change · ATLAS 1 trade -$33, edge AMBER, nothing to change", "p": 0}
    wjson(os.path.join(root, "logs", "learn", "tiny.json"), tn)
    snap = PR.gather(now=ts(DAY, 17, 30), root=root, env={"LE_PR_T_NT": "1", "LE_PR_T_MARKET": "0"}, http=lambda *a, **k: (0, ""),
                     feed_problem=lambda: None)
    check("e. gather reads logs/learn/tiny.json as snap['zl']", snap.get("zl") == tn, snap.get("zl"))
    snap["hb"] = {"t": ts(DAY, 17, 29)}
    snap["hb_t"] = ts(DAY, 17, 29)
    core, exts = PR.posts(snap)
    x = {}
    for e in exts:
        x.update(e.get("x") or {})
    sizes = [len(json.dumps(e, separators=(",", ":"), default=str, ensure_ascii=False).encode()) for e in [core] + exts]
    check("e. the ext post carries 'zl' (the core does not), every post under 3,900 bytes", x.get("zl") == tn and "zl" not in core
          and max(sizes) <= PR.MAX_STATUS_BYTES, (list(x), sizes))
    from tools import pc_feed
    m = pc_feed.merge(core, exts)
    check("e. the site's merge lays zl into the status (pc_feed.merge)", m.get("zl") == tn)


# ================================================================================================ f. more data (metals)
def part_f(tmp):
    import pandas as pd
    from engine import datapipe as DP, datafeed as DF
    from tools import data_pull as PULL
    ok_in = [ts(DAY, 4, 45), ts(DAY, 5, 30), ts(DAY, 15, 45), ts(DAY, 16, 59)]
    ok_out = [ts(DAY, 4, 44), ts(DAY, 5, 45), ts(DAY, 12, 0), ts(DAY, 15, 44)]
    lon = ts("2027-03-16", 6, 0)                                  # US on summer time, UK not yet: London 10:00 = 06:00 ET
    check("f. metals window: 04:45-05:45 / 15:45-17:15 ET, edges right", all(DP.metal_minute_ok(t) for t in ok_in) and not any(DP.metal_minute_ok(t) for t in ok_out))
    check("f. metals window follows London in the March gap (06:00 ET = 10:00 London)", DP.metal_minute_ok(lon) and not DP.metal_minute_ok(ts("2026-11-19", 6, 0)))
    lo = ts("2026-11-18", 18)
    rows = [(lo + 60 * i, 4000.0 + i * 0.1, 4000.5 + i * 0.1, 3999.5 + i * 0.1, 4000.2 + i * 0.1, 5) for i in range(23 * 60)]
    gc = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    nq = pd.DataFrame([(t, 21000.0, 21001.0, 20999.0, 21000.5, 10) for t, *_ in rows], columns=gc.columns)
    frames = {("GC", "1m"): gc, ("GC", "5m"): gc.iloc[::5], ("NQ", "1m"): nq, ("SIL", "1m"): gc}
    fb = DP.day_bars(DAY, frames)
    from engine import pcbars
    g = pcbars.decode(fb.get("bars/GC_1m.csv.gz"))
    mins = {(DP._et(int(t)).hour * 60 + DP._et(int(t)).minute) for t in g["time"]}
    check("f. day_bars: GC 1m only in the windows (135 bars: 04:45-05:45 + 15:45-17:00, the CME day ends 17:00), no GC 5m, NQ whole day as before, SIL too",
          len(g) == 135 and min(mins) == 285 and max(mins) == 1019 and "bars/GC_5m.csv.gz" not in fb
          and len(pcbars.decode(fb["bars/NQ_1m.csv.gz"])) == 23 * 60 and "bars/SIL_1m.csv.gz" in fb, (len(g), sorted(fb)))
    pk = DF.pick_frames(frames)
    check("f. the feed picks GC 1m (not 5m) and SI from SIL; NQ as before", ("GC", "1m") in pk and ("GC", "5m") not in pk and pk[("SI", "1m")][0] == "SIL"
          and ("NQ", "1m") in pk, sorted(pk))
    check("f. DAY_FILE: learn.json + GC / MGC / SI / SIL bars accepted, other names refused",
          DF.DAY_FILE.match(f"days/{DAY}/learn.json") and DF.DAY_FILE.match(f"days/{DAY}/bars/MGC_1m.csv.gz")
          and not DF.DAY_FILE.match(f"days/{DAY}/bars/XAU_1m.csv.gz") and not DF.DAY_FILE.match(f"days/{DAY}/learn.py"))
    check("f. the caps stay: 2 MB a zip, 8 answers a day", DF.MAX_ZIP == 1_850_000 and DF.DAILY_CAP == 8)
    files = DF.pack_day(DAY, pk, [], (), {}, ts(DAY, 17, 30), None, os.path.join(tmp, "nolocal"))
    blob = DF.zip_days({DAY: files})
    out = os.path.join(tmp, "pulled")
    wrote = DF.extract(blob, out)
    check("f. a day with NQ + GC + SI packs small and the cloud extracts it", wrote == [(DAY, False)] and len(blob) < 200_000
          and os.path.exists(os.path.join(out, DAY, "bars", "GC_1m.csv.gz")), (wrote, len(blob)))
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr(f"days/{DAY}/manifest.json", json.dumps({"day": DAY}))
        z.writestr(f"days/{DAY}/bars/XAU_1m.csv.gz", b"x")
    try:
        DF.extract(bad.getvalue(), os.path.join(tmp, "bad"))
        refused = False
    except ValueError:
        refused = True
    check("f. extract refuses a name it does not know (XAU)", refused)
    md = os.path.join(tmp, "metals")
    l1 = PULL.import_metals(out, md)
    l2 = PULL.import_metals(out, md)
    txt = open(os.path.join(md, "GC_1m.csv")).read().splitlines()
    check("f. data_pull.import_metals: data/metals/GC_1m.csv + SI, 135 bars each with the contract column; a second pull adds nothing",
          len(txt) == 136 and txt[0] == "time,open,high,low,close,volume,contract" and txt[1].endswith(",GC")
          and any("+135 bars" in x for x in l1) and all("up to date" in x for x in l2) and os.path.exists(os.path.join(md, "SI_1m.csv")), (l1, l2, txt[:2]))


# ================================================================================================ g. the cloud command
def part_g(tmp, dd_c):
    from tools import learn_night as LN
    a = argparse.Namespace(no_pull=False, wait=0.0, skip="", full=False, fetch=False, dry_run=False)
    P = LN.plan(a)
    check("g. plan: pull (data_pull --latest), edge_health, cost_alarm, anatomy build/explain/page, zeus_lab run --publish, learned, decide",
          [s for s, _ in P] == ["pull", "livegap", "edge", "costs", "anatomy", "lab", "learned", "decide", "hub", "blitz", "forward", "oflearn"]
          and P[0][1] == [["tools/data_pull.py", "--latest", "--wait", "0.0"]] and P[5][1] == [["tools/zeus_lab.py", "run", "--publish"]]
          and P[1][1] == [["tools/livegap_daily.py"]] and P[3][1] == [["tools/cost_alarm.py"]] and [c[1] for c in P[4][1]] == ["build", "explain", "page"], P)
    root = os.path.join(tmp, "groot")
    for rel in ("tools/web_public/business/decisions.json", "live_model.json", "live_model_lit.json", "dashboard_view.json"):
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), os.path.join(root, rel))
    days = os.path.join(tmp, "g_days")
    shutil.copytree(dd_c, days)
    pub = ZL._read_json(os.path.join(days, DAY, "learn.json"))
    pub["proposals"] = [{"id": "learn-atlas-edge-2026w47", "kind": "edge", "bot": "atlas", "day": DAY,
                         "question": "ATLAS: let Claude re-test it on the newest bars (its last 40 trades lost)?",
                         "why": "Last 40 trades: PF 0.8, -$420.", "impact": "-$420 over those 40 trades."},
                        {"id": "learn-blitz-edge-2026w47", "kind": "edge", "bot": "blitz", "day": DAY, "question": "BLITZ: x?", "why": "y", "impact": "$0"}]
    wjson(os.path.join(days, DAY, "learn.json"), pub)
    calls = []
    fake = lambda cmd, lim: calls.append(cmd) or {"ok": True, "rc": 0, "s": 1.0, "tail": ["ok"]}   # noqa: E731
    card = os.path.join(root, "tools", "web_public", "hub", "learned.json")
    dec = os.path.join(root, "tools", "web_public", "business", "decisions.json")
    rep = os.path.join(tmp, "night_cloud.json")
    out = LN.run(a, runner=fake, say=lambda *_: None, root=root, days_dir=days, card_path=card, decisions=dec, report=rep)
    c = ZL._read_json(card, {})
    check("g. fake steps run in order (pull, edge, costs, 3 anatomy, lab, hub); the card learned.json = the PC's line + date, no BLITZ",
          [x[0] for x in calls] == ["tools/data_pull.py", "tools/livegap_daily.py", "tools/edge_health.py", "tools/cost_alarm.py"] + ["tools/win_loss_anatomy.py"] * 3
          + ["tools/zeus_lab.py", "tools/research_hub.py", "research/blitz/learn.py", "tools/forward_paper.py", "research/orderflow/of_learn.py"]
          and c.get("day") == DAY and c.get("line", "").startswith("ZEUS learned Nov 19") and "blitz" not in json.dumps(c).lower()
          and len(json.dumps(c).encode()) <= LN.CARD_MAX_BYTES, (calls, c.get("line")))
    D = ZL._read_json(dec, {})
    items = D.get("items") or []
    new = [i for i in items if i.get("id") == "learn-atlas-edge-2026w47"]
    bad = [d.get("id") for d in items if not (re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,39}", str(d.get("id"))) and d.get("question") and d.get("why")
                                              and "$" in str(d.get("impact")) and isinstance(d.get("impact_usd"), (int, float))
                                              and set(d.get("options") or []) <= {"yes", "no", "later"} and d.get("options")
                                              and d.get("status") in ("open", "yes", "no", "later", "done", "superseded", "waiting") and d.get("source"))]   # = test_decide (night-decide)
    check("g. Decide card: the ATLAS proposal added once (open, yes/no/later, test_decide's schema), BLITZ (hidden) never",
          len(new) == 1 and new[0]["status"] == "open" and not bad and not any(i.get("id", "").startswith("learn-blitz") for i in items)
          and out["decide_added"] == ["learn-atlas-edge-2026w47"], (out["decide_added"], bad))
    n_before = len(items)
    out2 = LN.run(a, runner=fake, say=lambda *_: None, root=root, days_dir=days, card_path=card, decisions=dec, report=rep)
    check("g. a second night: nothing added twice", len((ZL._read_json(dec, {}) or {}).get("items") or []) == n_before and out2["decide_added"] == [])
    check("g. the report: protected files unchanged, a what-changed table", out["protected_ok"] and any(r["what"] == "ZEUS learned" for r in out["changes"])
          and os.path.exists(rep) and "| What | Before | After |" in LN.table(out["changes"]))
    mt = os.path.getmtime(dec)
    dry = argparse.Namespace(**{**vars(a), "dry_run": True})
    o3 = LN.run(dry, runner=lambda *x: (_ for _ in ()).throw(AssertionError("ran")), say=lambda *_: None, root=root, days_dir=days,
                card_path=card, decisions=dec, report=rep)
    check("g. dry run: the plan only, nothing run or written", o3.get("plan") and os.path.getmtime(dec) == mt)
    skip = LN.plan(argparse.Namespace(**{**vars(a), "no_pull": True, "skip": "lab,anatomy,livegap", "full": True}))
    check("g. --no-pull --skip lab,anatomy,livegap: edge, costs, learned, decide, hub only", [s for s, _ in skip] == ["edge", "costs", "learned", "decide", "hub", "blitz", "forward", "oflearn"], skip)
    it = LN.decide_item({"id": "Bad Id!", "question": "q", "why": "w"})
    check("g. a proposal with a bad id never reaches the card", it is None)


# ================================================================================================ h. the ZEUS page
def part_h():
    html = open(os.path.join(ROOT, "tools", "web_public", "hub", "zeus.html"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "tools", "web_public", "hub", "zeus.js"), encoding="utf-8").read()
    # polish2 2026-11-19: the card stayed hidden when there was no nightly line yet; now a calm placeholder from the first paint
    sec = re.search(r'<section id="learned"[^>]*>', html)
    box = re.search(r'<div id="learnBox" class="zs-learn wait"[^>]*><p class="zs-goal">([^<]*)</p><p class="zs-src">([^<]*)</p></div>', html)
    check("h. zeus.html: the 'ZEUS learned' section is shown from the first paint with its box holding the calm placeholder; zeus.js?v>=4",
          sec and "hidden" not in sec.group(0) and box and box.group(1) == "First nightly report after today's close" and int((re.search(r"zeus\.js\?v=(\d+)", html) or [0, 0])[1]) >= 4, (sec and sec.group(0), box and box.groups()))
    check("h. zeus.js: no nightly line = the same placeholder words (LEARN_WAIT), never a hidden card",
          "if (!L) { box.className = 'zs-learn wait';" in js and "sec.hidden = true" not in js and box and "'First nightly report after today\\'s close'" in js)
    check("h. zeus.js: text only (no innerHTML / eval), reads learned.json next to the page", not re.search(r"innerHTML|insertAdjacentHTML|\beval\(", js)
          and "getJSON('learned.json')" in js)
    script = r"""
const Z = require(process.argv[1]);
const now = 1795140000;
const zl = {d: '2026-11-19', t: 1795130000, s: 'Zlarior 1 trade +$208, edge GREEN, nothing to change \u00b7 ATLAS no trade, edge AMBER, nothing to change', p: 1};
const cloudOld = {day: '2026-11-18', t: 1795000000, line: 'ZEUS learned Nov 18: Zlarior no trade, edge GREEN, nothing to change', built: 'x', proposals: 0};
const cloudNew = {day: '2026-11-20', t: 1795200000, line: 'ZEUS learned Nov 20: ATLAS 2 trades +$90, edge AMBER, nothing to change', built: 'y', proposals: 2};
const a = Z.learned({zl: zl}, cloudOld, now), b = Z.learned({zl: zl}, cloudNew, now), c = Z.learned(null, null, now);
const d = Z.learned({zl: {d: '2026-11-10', t: 1, s: 'ATLAS no trade', p: 0}}, null, now);
console.log(JSON.stringify({a: a, b: b, c: c, d: d, wait: Z.LEARN_WAIT}));
"""
    r = subprocess.run(["node", "-e", script, os.path.join(ROOT, "tools", "web_public", "hub", "zeus.js")], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {}
    a, b = o.get("a") or {}, o.get("b") or {}
    check("h. node: the PC's line when newer: 2 rows (Zlarior, ATLAS), 1 idea, date Nov 19, source the live feed",
          a.get("when") == "Nov 19" and [x["name"] for x in a.get("rows") or []] == ["Zlarior", "ATLAS"] and a.get("ideas") == 1
          and "live feed" in a.get("src", "") and not a.get("old"), (o, r.stderr[-300:]))
    check("h. node: the cloud copy when newer (prefix cut), nothing = null, a 9-day-old line is marked old",
          b.get("when") == "Nov 20" and b["rows"][0]["text"].startswith("2 trades +$90") and "Cloud copy" in b.get("src", "")
          and o.get("c") is None and (o.get("d") or {}).get("old") is True, o)
    check("h. node: the placeholder words match the page's first paint (nothing changes when zeus.js finds no line)",
          box and o.get("wait") == [box.group(1).replace("&#39;", "'"), box.group(2)], (o.get("wait"), box and box.groups()))


# ================================================================================================ i. faster thinking
SPEED_SCRIPT = r"""
import json, os, sys, tempfile, time
sys.path.insert(0, sys.argv[1]); os.chdir(sys.argv[1]); os.environ["LE_PR_NO_NET"] = "1"
tmp = sys.argv[2]
from tests.test_live_publish import hb_payload
now = time.time()
root, work = os.path.join(tmp, "root"), os.path.join(tmp, "work")
os.makedirs(os.path.join(root, "logs", "pc_hb"), exist_ok=True)
json.dump(hb_payload(now, n_trades=10), open(os.path.join(root, "logs", "pc_hb", "heartbeat.json"), "w"))
from tools import hub_data
hub_data.BIZ_DISK = os.path.join(tmp, "hub_business.json")
os.environ.update(OLYMPUS_HOME=os.path.join(tmp, "home"), LE_PR_T_NT="1", LE_PR_T_MARKET="1")
from tools import pc_report as PR
t0 = time.perf_counter()
rec = PR.run_once(work=work, dry=True, http=lambda *a, **k: (200, '{"ok": true}'), root=root, now=now, feed_problem=lambda: None, say=lambda *_: None)
print(json.dumps({"ms": round(1000 * (time.perf_counter() - t0)), "heavy": sorted(m for m in ("numpy", "pandas", "openpyxl") if m in sys.modules),
                  "ok": bool(rec.get("card"))}))
"""


def part_i(tmp):
    d = os.path.join(tmp, "speed")
    os.makedirs(d, exist_ok=True)
    runs = []
    for _ in range(2):                      # the 1st warms the business disk cache (a new workbook is parsed once)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", SPEED_SCRIPT, ROOT, d], capture_output=True, text=True, timeout=300, cwd=ROOT)
        try:
            runs.append(json.loads(r.stdout.strip().splitlines()[-1]))
        except Exception:
            runs.append({"err": (r.stdout + r.stderr)[-400:]})
    check("i. the PC's 15-minute report (a fresh process, warm business cache): no numpy / pandas / openpyxl import",
          runs[1].get("ok") and runs[1].get("heavy") == [], runs)
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import engine.health_band, engine.goals, "
                        "engine.live_board, engine.sizing; print(sorted(m for m in ('numpy', 'pandas') if m in sys.modules))", ROOT],
                       capture_output=True, text=True, timeout=120)
    check("i. health_band / goals / live_board / sizing import without numpy or pandas", r.stdout.strip() == "[]", r.stdout + r.stderr[-300:])
    import random
    import numpy as np
    from engine import health_band as HB, cme_calendar as CC, lit_live as LL, sizing as SZ

    def ref(qs, v):
        q = np.asarray(qs, float)
        if v is None or not len(q):
            return None
        if v < q[0]:
            return 0.5
        if v > q[-1]:
            return 99.5
        i = int(np.searchsorted(q, v, side="right"))
        if i >= len(q):
            return 99.0
        lo, hi = q[i - 1], q[i]
        f = 0.0 if hi == lo else (v - lo) / (hi - lo)
        j = int(np.searchsorted(q, v, side="left"))
        if hi == lo or (j < i - 1):
            return round(float((j + i) / 2.0 + 0.5), 1)
        return round(float(i + f), 1)
    rng = random.Random(11)
    bad = 0
    for _ in range(4000):
        q = sorted(rng.choice([rng.uniform(-300, 300), float(round(rng.uniform(-3, 3)))]) for _ in range(rng.choice([1, 3, 99])))
        v = rng.choice([rng.uniform(-400, 400), rng.choice(q), round(rng.uniform(-3, 3))])
        bad += ref(q, v) != HB.pct_of(q, v)
    check("i. health_band.pct_of in pure Python = the numpy version (4,000 random cases)", bad == 0, bad)
    days = [(dt.date(2021, 1, 1) + dt.timedelta(days=i)).isoformat() for i in range(0, 4000, 1)]
    check("i. the light calendar gives lit_live's early closes and Easter (2021-2031)", all(CC.early_close(x) == LL.early_close(x) for x in days)
          and all(CC._easter(y) == LL._easter(y) for y in range(2000, 2100)) and SZ.eval_session("2026-03-30", "2026-04-10") == 9)
    from engine import datapipe as DP
    w = os.path.join(tmp, "dpk")
    root = os.path.join(tmp, "dpk_root")
    wjson(os.path.join(root, "data", "live_state.json"), {"adapter": "paper", "ledger": [{"t": 10 + i, "side": "buy", "entry_t": 10 + i} for i in range(50)]})
    a1 = DP.collect(root, w)
    a2 = DP.collect(root, w)
    with open(os.path.join(w, DP.ARCHIVE), "a") as fh:                     # someone else wrote the archive: the index is rebuilt
        fh.write(json.dumps({"t": 99, "side": "buy", "entry_t": 99, "src": "main", "bot": "zlarior", "acct": "zlarior", "mode": "paper"}) + "\n")
    st = json.load(open(os.path.join(root, "data", "live_state.json")))
    st["ledger"] += [{"t": 99, "side": "buy", "entry_t": 99}, {"t": 100, "side": "exit", "entry_t": 99, "pnl": 1.0}]
    wjson(os.path.join(root, "data", "live_state.json"), st)
    a3 = DP.collect(root, w)
    rows = DP._jl_read(os.path.join(w, DP.ARCHIVE))
    check("i. datapipe.collect with its key index: 50 rows once, nothing twice, an outside append respected (+1 new only)",
          a1["added"] == 50 and a2["added"] == 0 and a3["added"] == 1 and len(rows) == 52 and len({DP._rkey(r) for r in rows}) == 52, (a1, a2, a3, len(rows)))
    from engine import ops_checks as OC
    import time as _t
    order = []

    def probe(u):
        t0 = _t.time()
        _t.sleep(0.25)
        order.append(u)
        return {"ok": True, "date": t0 + 2.125, "t0": t0, "t1": _t.time()}
    t0 = _t.perf_counter()
    res = OC.internet(probe=probe, urls=("a", "b", "c"))
    took = _t.perf_counter() - t0
    check("i. the ops tick's 3 internet probes run side by side (one round trip, same answer)", took < 0.6 and res["up"] and res["n"] == 3
          and abs(res["drift_s"] - 2.0) < 0.1, (took, res))


def main():
    tmp = tempfile.mkdtemp(prefix="le_learn_")
    try:
        part_a(tmp)
        part_b(tmp)
        dd_c, _root = part_c_real(tmp)
        part_d(tmp)
        part_e(tmp)
        part_f(tmp)
        part_g(tmp, dd_c)
        part_h()
        part_i(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nZEUS learned + learn night: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
